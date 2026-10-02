"""Two-turn trial execution with durable resume semantics.

Guarantees:
- A turn is registered (requests.jsonl) BEFORE it is sent.
- A completed turn is never rerun; turn 1 is never repeated because turn 2
  failed; retries always reuse the same payload+endpoint.
- Raw request payloads and raw API responses are immutable JSONL records.
- Model/provider returned in the response is verified against the request.
- Reserve-before-call budget accounting; uncertain outcomes keep their reserve.
"""
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from . import client as cl
from .budget import BudgetExceeded, BudgetLedger
from .env import STUDY, get_key, paid_gate, max_concurrency
from .schedule import (MAX_TOKENS, build_payload, load_selected_models,
                       load_stimuli, trial_prompts)
from .storage import Progress, append_jsonl, data_dir, read_jsonl

# estimated prompt tokens per turn for the reservation bound (conservative)
RESERVE_PROMPT_TOKENS = 3000


class Pipeline:
    def __init__(self, split, client=None, ledger=None):
        assert split in ("pilot", "main", "mock")
        self.split = split
        self.dir = data_dir(split)
        self.progress = Progress(split)
        self.stimuli = load_stimuli()
        self.models = {m["index"]: m for m in load_selected_models()}
        self.ledger = ledger
        self._client = client
        self._model_locks = {i: threading.Lock() for i in self.models}
        self._stop = threading.Event()
        self.stop_reason = None

    # ---- cost reservation ---------------------------------------------------
    def reserve_amount(self, model_entry):
        pr = model_entry["endpoint"]["pricing_usd_per_token"]
        return (Decimal(str(RESERVE_PROMPT_TOKENS)) * Decimal(str(pr["prompt"]))
                + Decimal(str(MAX_TOKENS)) * Decimal(str(pr["completion"])))

    # ---- one API turn --------------------------------------------------------
    def _do_turn(self, trial, turn, payload, first_text, second_text):
        """Returns dict outcome. Never raises BudgetExceeded upward silently."""
        request_id = f"{trial['trial_id']}#t{turn}"
        m = self.models[trial["model_index"]]
        reserve = self.reserve_amount(m)
        gate_ok, gate_why = paid_gate()
        if not gate_ok:
            return {"request_id": request_id, "status": "blocked",
                    "error": f"paid gate: {gate_why}"}
        if self.ledger:
            try:
                self.ledger.reserve(request_id, reserve)
            except BudgetExceeded as e:
                return {"request_id": request_id, "status": "blocked",
                        "error": f"budget: {e}"}
        rec = {"request_id": request_id, "trial_id": trial["trial_id"],
               "split": self.split, "turn": turn, "ts_registered": cl.utcnow(),
               "model_requested": m["model_id"],
               "endpoint_tag": m["endpoint"]["tag"],
               "reserved_usd": str(reserve), "payload": payload}
        append_jsonl(self.dir / "requests.jsonl", rec)
        try:
            res = self._client.chat(payload)
        except Exception as e:  # transport-level crash
            if self.ledger:
                self.ledger.mark_uncertain(request_id)
            append_jsonl(self.dir / "attempts.jsonl",
                         {"request_id": request_id, "ts": cl.utcnow(),
                          "outcome": "client_crash", "detail": str(e)[:300]})
            return {"request_id": request_id, "status": "error",
                    "error": f"client_crash: {e}", "uncertain": True}

        for a in res.attempts:
            append_jsonl(self.dir / "attempts.jsonl", {
                "request_id": request_id, "n": a.n, "ts": a.ts,
                "outcome": a.outcome, "http_status": a.http_status,
                "retry_after_s": a.retry_after_s, "detail": a.detail})

        cost = res.cost_usd if res.cost_usd is not None else None
        if res.ok:
            if self.ledger:
                self.ledger.settle(request_id, cost or "0")
        elif res.outcome_unknown:
            if self.ledger:
                self.ledger.mark_uncertain(request_id)
        else:
            if self.ledger:
                self.ledger.release(request_id, res.error or "failed")

        # verify returned identity (provider comes back as a display name —
        # normalize both sides before comparing)
        ident_ok = None
        if res.ok:
            ident_ok = (res.model_returned in (None, m["model_id"])
                        or str(res.model_returned).startswith(m["model_id"]))
            if res.provider_returned:
                norm = lambda s: "".join(
                    ch for ch in str(s).lower() if ch.isalnum())
                ident_ok = ident_ok and (
                    norm(res.provider_returned)
                    == norm(m["endpoint"]["tag"].split("/")[0]))

        rrec = {"request_id": request_id, "trial_id": trial["trial_id"],
                "turn": turn, "split": self.split, "ts": cl.utcnow(),
                "ok": res.ok, "http_status": res.status,
                "generation_id": res.generation_id,
                "model_returned": res.model_returned,
                "provider_returned": res.provider_returned,
                "identity_ok": ident_ok,
                "finish_reason": res.finish_reason,
                "text": res.text, "reasoning_text": res.reasoning_text,
                "usage": res.usage, "cost_usd": cost,
                "raw_response": res.body, "error": res.error,
                "outcome_unknown": res.outcome_unknown}
        append_jsonl(self.dir / "responses.jsonl", rrec)
        return {"request_id": request_id, "status": "ok" if res.ok else "error",
                "response": rrec}

    # ---- one trial ------------------------------------------------------------
    def run_trial(self, trial):
        tid = trial["trial_id"]
        rec = self.progress.get(tid)
        if rec.get("status") == "done":
            return {"trial_id": tid, "status": "skipped_done"}
        if self._stop.is_set():
            return {"trial_id": tid, "status": "skipped_stop"}
        first_text, second_text = trial_prompts(trial, self.stimuli)
        m = self.models[trial["model_index"]]

        # --- turn 1 ---
        if rec.get("turn1_status") == "ok":
            t1_text = rec.get("turn1_text")
        else:
            payload = build_payload(
                m, [{"role": "user", "content": first_text}])
            out = self._do_turn(trial, 1, payload, first_text, second_text)
            if out["status"] == "blocked":
                self._stop.set()
                self.stop_reason = out["error"]
                self.progress.set(tid, status="blocked",
                                  blocked_reason=out["error"])
                return {"trial_id": tid, "status": "blocked",
                        "error": out["error"]}
            if out["status"] != "ok":
                self.progress.set(
                    tid, status="failed_turn1",
                    turn1_status="error", turn1_error=out.get("error"),
                    turn1_request_id=out["request_id"])
                return {"trial_id": tid, "status": "failed_turn1",
                        "error": out.get("error")}
            t1_text = out["response"]["text"]
            self.progress.set(
                tid, status="turn1_done", turn1_status="ok",
                turn1_request_id=out["request_id"], turn1_text=t1_text,
                turn1_finish=out["response"]["finish_reason"],
                turn1_cost=out["response"]["cost_usd"])

        # --- turn 2 (same conversation; actual first response verbatim) ---
        if rec.get("turn2_status") == "ok":
            self.progress.set(tid, status="done")
            return {"trial_id": tid, "status": "skipped_done"}
        payload = build_payload(m, [
            {"role": "user", "content": first_text},
            {"role": "assistant", "content": t1_text},
            {"role": "user", "content": second_text}])
        out = self._do_turn(trial, 2, payload, first_text, second_text)
        if out["status"] == "blocked":
            self._stop.set()
            self.stop_reason = out["error"]
            self.progress.set(tid, status="blocked",
                              blocked_reason=out["error"])
            return {"trial_id": tid, "status": "blocked",
                    "error": out["error"]}
        if out["status"] != "ok":
            self.progress.set(tid, status="failed_turn2",
                              turn2_status="error",
                              turn2_error=out.get("error"),
                              turn2_request_id=out["request_id"])
            return {"trial_id": tid, "status": "failed_turn2",
                    "error": out.get("error")}
        self.progress.set(
            tid, status="done", turn2_status="ok",
            turn2_request_id=out["request_id"],
            turn2_text=out["response"]["text"],
            turn2_finish=out["response"]["finish_reason"],
            turn2_cost=out["response"]["cost_usd"],
            identity_ok=out["response"]["identity_ok"])
        return {"trial_id": tid, "status": "done"}

    # ---- split runner ---------------------------------------------------------
    def run(self, trials):
        """Execute a schedule; concurrency <=2 globally, <=1 per model."""
        gate_ok, why = paid_gate()
        if not gate_ok:
            return {"status": "blocked", "reason": f"paid gate: {why}"}
        if self._client is None:
            self._client = cl.ORClient(get_key())
        results = []
        with ThreadPoolExecutor(max_workers=max_concurrency()) as pool:
            def guarded(trial):
                lock = self._model_locks[trial["model_index"]]
                with lock:
                    return self.run_trial(trial)
            futs = [pool.submit(guarded, t) for t in trials]
            for f in futs:
                results.append(f.result())
        return {"status": "stopped" if self._stop.is_set() else "finished",
                "stop_reason": self.stop_reason,
                "results": results,
                "progress": self.progress.counts()}


def reconcile_costs(split):
    """Sum settled costs from responses.jsonl (authoritative actuals)."""
    total = Decimal("0")
    n = 0
    for r in read_jsonl(data_dir(split) / "responses.jsonl"):
        if r.get("ok") and r.get("cost_usd"):
            total += Decimal(str(r["cost_usd"]))
            n += 1
    return {"requests_with_cost": n, "total_usd": str(total)}
