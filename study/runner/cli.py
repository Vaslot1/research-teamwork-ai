"""CLI: python study/run.py <validate|pilot|run|resume|annotate|analyze|report|status>
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import coding
from .analysis import write_outputs
from .budget import BudgetLedger
from .env import STUDY, env_status, get_key, max_budget, paid_gate
from .pipeline import Pipeline, reconcile_costs
from .schedule import (build_main_schedule, build_pilot_schedule,
                       load_selected_models, load_stimuli, save_schedule)
from .storage import data_dir, read_json, read_jsonl


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def cmd_validate():
    checks = []

    def chk(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    st = env_status()
    chk("env.key_present", st["OPENROUTER_API_KEY"] == "set")
    chk("env.allow_paid", st["ALLOW_PAID_RUN"].lower() == "true",
        st["ALLOW_PAID_RUN"])
    try:
        cap = float(st["MAX_BUDGET_USD"]); ok = cap > 0
    except Exception:
        cap, ok = None, False
    chk("env.max_budget_positive", ok, st["MAX_BUDGET_USD"])

    stim = load_stimuli()
    chk("stimuli.6_scenarios", len(stim["scenarios"]) == 6)
    chk("stimuli.pilot", stim["pilot"]["id"] == "CASE-PILOT")
    for s in stim["scenarios"]:
        for blk, txt in [("first", s["first_request"])] + \
                        list(s["second_requests"].items()):
            h = hashlib.sha256(txt["text"].encode("utf-8")).hexdigest()
            chk(f"stimuli.sha256.{s['id']}.{blk}", h == txt["sha256"])
    models = load_selected_models()
    chk("models.7_families", len(models) == 7,
        ",".join(m["family"] for m in models))
    for m in models:
        ep = m["endpoint"]
        chk(f"endpoint.tag.{m['family']}", bool(ep.get("tag")), ep.get("tag"))
        chk(f"endpoint.max_tokens.{m['family']}",
            "max_tokens" in (ep.get("endpoint_supported_parameters") or []))
    est = STUDY / "budget" / "estimate_draft.json"
    chk("estimate.exists", est.exists())
    ok_all = all(c["ok"] for c in checks)
    print(json.dumps({"validate": "PASS" if ok_all else "FAIL",
                      "ts": utcnow(), "env": st, "checks": checks},
                     ensure_ascii=False, indent=2))
    return 0 if ok_all else 1


def cmd_pilot():
    ok, why = paid_gate()
    if not ok:
        print(f"BLOCKED: {why}")
        return 2
    models = load_selected_models()
    trials = build_pilot_schedule(models)
    save_schedule("pilot", trials)
    ledger = BudgetLedger(max_budget())
    pipe = Pipeline("pilot", ledger=ledger)
    print(f"pilot: {len(trials)} trials / {len(trials)*2} generations")
    res = pipe.run(trials)
    out = {"ts": utcnow(), "result": res,
           "costs": reconcile_costs("pilot"),
           "ledger": ledger.totals()}
    (STUDY / "data" / "pilot" / "pilot_run_result.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "result"},
                     ensure_ascii=False, indent=2))
    print("progress:", res.get("progress"))
    return 0 if res["status"] == "finished" else 3


def cmd_run(split="main"):
    ok, why = paid_gate()
    if not ok:
        print(f"BLOCKED: {why}")
        return 2
    # frozen-plan gate: manifest must exist and hashes must match
    man = read_json(STUDY / "frozen" / "manifest.json")
    if not man:
        print("BLOCKED: no frozen manifest (stage 04 incomplete)")
        return 2
    mism = []
    for rel, h in man["files"].items():
        if rel == "_code_snapshot":
            continue  # aggregate code hash is audited, not a file path
        p = STUDY / rel
        if not p.exists() or sha256_file(p) != h:
            mism.append(rel)
    if mism:
        print(f"BLOCKED: frozen-hash mismatch: {mism}")
        return 2
    sched = read_json(STUDY / "schedules" / f"schedule_{split}.json")
    if not sched:
        sched = build_main_schedule()
        save_schedule(split, sched)
    ledger = BudgetLedger(max_budget())
    # gate: expected cost of the REMAINING plan vs remaining budget
    est = read_json(STUDY / "budget" / "estimate_frozen.json") or \
        read_json(STUDY / "budget" / "estimate_draft.json")
    tot = ledger.totals()
    avail = float(tot["available"])
    if est:
        totals = est.get("totals") or est.get("totals_usd") or {}
        if "per_model" in est:   # main-run portion only (pilot excluded)
            need = sum(float(pm["expected"]["main_usd"])
                       for pm in est["per_model"].values())
        else:
            need = float(totals["expected"])
        planned_gens = len(sched) * 2
        done_n = len([t for t in read_jsonl(data_dir(split) / "responses.jsonl")
                      if t.get("ok")])
        frac_left = 1 - done_n / max(1, planned_gens)
        need_left = need * frac_left
        if need_left > avail:
            print(f"BLOCKED: estimated remaining cost ${need_left:.2f} "
                  f"> available ${avail:.2f}")
            return 2
    pipe = Pipeline(split, ledger=ledger)
    res = pipe.run(sched)
    print(json.dumps({"status": res["status"], "stop": res.get("stop_reason"),
                      "progress": res.get("progress"),
                      "costs": reconcile_costs(split)},
                     ensure_ascii=False, indent=2))
    return 0 if res["status"] == "finished" else 3


def cmd_annotate(split="main"):
    """Idempotent: regenerates coding_auto.jsonl fully (derived artifact)."""
    from .storage import atomic_write_json
    prog = read_json(data_dir(split) / "progress.json", {"trials": {}})
    rows = []
    for tid, rec in sorted(prog["trials"].items()):
        if rec.get("status") != "done":
            continue
        scen = "CASE-PILOT" if "PILOT" in tid else \
            "-".join(tid.split("-")[2:4])
        c = coding.code_trial(
            scen, rec.get("turn1_text"), rec.get("turn2_text"),
            rec.get("turn1_finish"), rec.get("turn2_finish"))
        c["trial_id"] = tid
        c["model_index"] = int(tid.split("-")[0][1:])
        c["condition"] = tid.split("-")[-1]
        rows.append(c)
    out = data_dir(split) / "coding_auto.jsonl"
    tmp = out.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for c in rows:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    tmp.replace(out)
    print(f"annotated {len(rows)} trials -> data/{split}/coding_auto.jsonl")
    return 0


def cmd_analyze(split="main"):
    res = write_outputs(split)
    print(f"analysis_{split}.json: n_coded={res['n_coded']} "
          f"done={res['n_trials_done']}")
    return 0


def cmd_status():
    prog = {}
    for split in ("pilot", "main", "mock"):
        p = data_dir(split) / "progress.json"
        if p.exists():
            tr = read_json(p)["trials"]
            c = {}
            for t in tr.values():
                c[t.get("status", "?")] = c.get(t.get("status", "?"), 0) + 1
            prog[split] = {"trials": len(tr), "by_status": c}
    led = read_json(STUDY / "budget" / "ledger.json", {})
    spent = led.get("spent", "0")
    uncertain = led.get("uncertain", {})
    state = read_json(STUDY / "STATE.json", {})
    print(json.dumps({
        "ts": utcnow(), "env": env_status(),
        "stages": {k: v.get("status") for k, v in
                   state.get("stages", {}).items()},
        "progress": prog,
        "spent_usd": spent, "uncertain_usd": uncertain,
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_report():
    return cmd_status()


COMMANDS = {
    "validate": cmd_validate,
    "pilot": cmd_pilot,
    "run": lambda: cmd_run("main"),
    "resume": lambda: cmd_run(sys.argv[2] if len(sys.argv) > 2 else "main"),
    "annotate": lambda: cmd_annotate(sys.argv[2] if len(sys.argv) > 2 else "main"),
    "analyze": lambda: cmd_analyze(sys.argv[2] if len(sys.argv) > 2 else "main"),
    "report": cmd_report,
    "status": cmd_status,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("commands:", ", ".join(COMMANDS))
        return 64
    return COMMANDS[sys.argv[1]]()
