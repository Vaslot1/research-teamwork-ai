"""Stage 04 freeze: actualized estimate + frozen manifest + main schedule.

After a successful pilot. Copies the exact artifacts that main collection
must not change into study/frozen/ and writes manifest.json with SHA-256.
"""
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "study"
sys.path.insert(0, str(STUDY))
from runner.schedule import build_main_schedule, save_schedule, repetitions  # noqa
from runner.storage import read_jsonl  # noqa


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------- 1. actualized estimate from real pilot usage --------------------
sel = json.loads((STUDY / "models" / "selected_models.json")
                 .read_text(encoding="utf-8"))["models"]
pilot_resp = read_jsonl(STUDY / "data" / "pilot" / "responses.jsonl")

per_model = {}
for m in sel:
    idx = m["index"]
    rs = [r for r in pilot_resp
          if r.get("ok") and r["trial_id"].startswith(f"M{idx}-")]
    n_gen = len(rs)
    tot = sum(Decimal(str(r.get("cost_usd") or 0)) for r in rs)
    pin = sum((r.get("usage") or {}).get("prompt_tokens", 0) for r in rs)
    pout = sum((r.get("usage") or {}).get("completion_tokens", 0) for r in rs)
    reas = sum(((r.get("usage") or {}).get("completion_tokens_details") or {})
               .get("reasoning_tokens", 0) for r in rs)
    n_trials = len({r["trial_id"] for r in rs}) or 1
    per_trial = tot / n_trials
    reps = repetitions()
    main24 = 24 * reps
    per_model[m["family"]] = {
        "model_id": m["model_id"], "endpoint_tag": m["endpoint"]["tag"],
        "pilot_generations": n_gen,
        "pilot_prompt_tokens": pin, "pilot_completion_tokens": pout,
        "pilot_reasoning_tokens": reas,
        "pilot_cost_usd": str(tot.quantize(Decimal("0.000001"))),
        "measured_cost_per_trial": str(per_trial.quantize(Decimal("0.000001"))),
        # main estimate: measured per-trial cost x 24*reps x 1.15 retry reserve
        "expected": {"main_usd": str(
            (per_trial * main24 * Decimal("1.15")).quantize(
                Decimal("0.0001")))},
        "low": {"main_usd": str(
            (per_trial * main24 * Decimal("1.0")).quantize(
                Decimal("0.0001")))},
        "high": {"main_usd": str(
            (per_trial * main24 * Decimal("3.0")).quantize(
                Decimal("0.0001")))},  # 3x measured = stress bound
    }

main_expected = sum(Decimal(v["expected"]["main_usd"])
                    for v in per_model.values())
main_low = sum(Decimal(v["low"]["main_usd"]) for v in per_model.values())
main_high = sum(Decimal(v["high"]["main_usd"]) for v in per_model.values())
spent = Decimal("0")
ledger = STUDY / "budget" / "ledger.json"
if ledger.exists():
    lg = json.loads(ledger.read_text(encoding="utf-8"))
    spent = Decimal(lg.get("spent", "0"))
    unc = sum(Decimal(v) for v in lg.get("uncertain", {}).values())
    spent += unc
cap = Decimal(os.environ.get("MAX_BUDGET_USD", "0"))
est = {
    "frozen_utc": utcnow(),
    "basis": "measured pilot usage per model (56 generations)",
    "cap_usd": str(cap), "spent_so_far_usd": str(spent),
    "remaining_usd": str(cap - spent),
    "main_plan": {"trials": 168 * repetitions() // repetitions() * repetitions(),
                  "generations": 336 * repetitions() // repetitions() * repetitions()},
    "per_model": per_model,
    "totals": {"low": str(main_low.quantize(Decimal("0.01"))),
               "expected": str(main_expected.quantize(Decimal("0.01"))),
               "high": str(main_high.quantize(Decimal("0.01")))},
    "fits_remaining": {
        "low": bool(main_low <= cap - spent),
        "expected": bool(main_expected <= cap - spent),
        "high": bool(main_high <= cap - spent)},
}
(STUDY / "budget").mkdir(exist_ok=True)
(STUDY / "budget" / "estimate_frozen.json").write_text(
    json.dumps(est, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------- 2. main schedule ------------------------------------------------
trials = build_main_schedule()
save_schedule("main", trials)

# ---------- 3. freeze manifest ----------------------------------------------
FREEZE = [
    "protocol/stimuli.json", "protocol/codebook.json",
    "protocol/protocol_draft.md", "protocol/amendments.md",
    "protocol/source_map.md",
    "models/selected_models.json", "models/generation_settings.json",
    "models/model_selection.md", "models/selection_policy.json",
    "budget/estimate_frozen.json",
    "schedules/schedule_main.json", "schedules/schedule_pilot.json",
]
frozen_dir = STUDY / "frozen"
frozen_dir.mkdir(exist_ok=True)
files = {}
for rel in FREEZE:
    src = STUDY / rel
    if not src.exists():
        continue
    files[rel] = sha(src)
    dst = frozen_dir / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

# code snapshot: collection code only (runner + run.py). tools/ evolve
# legitimately after collection (analysis/reporting) and are not frozen.
code_files = sorted((STUDY / "runner").glob("*.py")) + [STUDY / "run.py"]
code_hash = hashlib.sha256()
for cf in code_files:
    code_hash.update(cf.name.encode())
    code_hash.update(cf.read_bytes())
files["_code_snapshot"] = code_hash.hexdigest()

manifest = {
    "frozen_utc": utcnow(),
    "frozen_europe_amsterdam": "2026-09-22",
    "repetitions": repetitions(),
    "main_trials": len(trials),
    "main_generations": len(trials) * 2,
    "files": files,
    "code_files": [cf.name for cf in code_files],
    "python": sys.version.split()[0],
    "note": "pre-fixation manifest; main run must reproduce identical hashes",
}
(frozen_dir / "manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

print(json.dumps({
    "spent": str(spent), "remaining": str(cap - spent),
    "main_est": est["totals"], "fits": est["fits_remaining"],
    "trials": len(trials), "manifest_files": len(files)},
    ensure_ascii=False, indent=2))
