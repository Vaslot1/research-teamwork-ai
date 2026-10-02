"""Trial schedules. Deterministic; seeds never appear inside prompts.

Main: 7 models x 6 scenarios x 4 conditions x 3 reps = 504 trials.
Per protocol: seed = 220926 + 100*model_index + wave_index, shuffle the
24 (scenario x condition) pairs per model x wave; waves are sequential,
models interleaved evenly inside each wave.
Pilot: 4 trials per model (one per condition) on CASE-PILOT = 28 trials.
"""
import json
import random
from pathlib import Path

from .env import STUDY

CONDITIONS = ["S0", "S1", "P0", "P1"]
SCENARIOS = ["CASE-S1", "CASE-S2", "CASE-S3", "CASE-S4", "CASE-S5", "CASE-S6"]
SEED_BASE = 220926
MAX_TOKENS = 8192  # completion cap per generation; bounds reserved cost


def repetitions():
    """Repetition waves per model. User-set via env REPETITIONS (default 3);
    reduced to 1 on 2026-09-22 per user directive (budget <= $5), the
    protocol's pre-sanctioned reduced variant (DOCX-02 P0030)."""
    import os
    from .env import load_dotenv
    load_dotenv()
    try:
        return max(1, min(3, int(os.environ.get("REPETITIONS", "3"))))
    except Exception:
        return 3


def load_stimuli():
    return json.loads(
        (STUDY / "protocol" / "stimuli.json").read_text(encoding="utf-8"))


def load_selected_models():
    return json.loads(
        (STUDY / "models" / "selected_models.json").read_text(
            encoding="utf-8"))["models"]


def provider_prefs(model_entry):
    """Exact-endpoint pinning from the endpoint tag.

    tag 'prov/quant' -> only=['prov'], quantizations=['quant']
    tag 'prov'       -> only=['prov']
    """
    tag = model_entry["endpoint"]["tag"]
    if "/" in tag:
        prov, quant = tag.split("/", 1)
        prefs = {"only": [prov], "quantizations": [quant]}
    else:
        prefs = {"only": [tag]}
    prefs["allow_fallbacks"] = False
    prefs["require_parameters"] = True
    return prefs


def load_generation_settings():
    p = STUDY / "models" / "generation_settings.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"per_model": {}}


def build_payload(model_entry, messages):
    """Exact-endpoint payload; temperature=0.7 only where the endpoint
    supports it (per generation_settings.json); usage.include for cost."""
    pay = {
        "model": model_entry["model_id"],
        "messages": messages,
        "max_tokens": MAX_TOKENS,
        "usage": {"include": True},
        "provider": provider_prefs(model_entry),
    }
    st = load_generation_settings()["per_model"].get(f"M{model_entry['index']}")
    if st and st.get("temperature") is not None:
        pay["temperature"] = st["temperature"]
    return pay


def build_pilot_schedule(models=None):
    models = models or load_selected_models()
    trials = []
    order = 0
    for cond in CONDITIONS:                      # interleave models evenly
        for m in models:
            trials.append({
                "trial_id": f"M{m['index']}-PILOT-{cond}",
                "split": "pilot",
                "model_index": m["index"], "model_id": m["model_id"],
                "scenario": "CASE-PILOT", "condition": cond,
                "wave": 0, "rep": 0, "order": order})
            order += 1
    return trials


def build_main_schedule(models=None):
    models = models or load_selected_models()
    waves = list(range(1, repetitions() + 1))
    per_mw = {}
    for m in models:
        for wave in waves:
            pairs = [(s, c) for s in SCENARIOS for c in CONDITIONS]
            rng = random.Random(SEED_BASE + 100 * m["index"] + wave)
            rng.shuffle(pairs)
            per_mw[(m["index"], wave)] = pairs
    trials = []
    order = 0
    for wave in waves:
        for pos in range(24):
            for m in models:
                sc, cond = per_mw[(m["index"], wave)][pos]
                trials.append({
                    "trial_id": f"M{m['index']}-R{wave}-{sc}-{cond}",
                    "split": "main",
                    "model_index": m["index"], "model_id": m["model_id"],
                    "scenario": sc, "condition": cond,
                    "wave": wave, "rep": wave,
                    "seed": SEED_BASE + 100 * m["index"] + wave,
                    "order": order})
                order += 1
    return trials


def trial_prompts(trial, stimuli):
    """(first_text, second_text) for a trial."""
    if trial["scenario"] == "CASE-PILOT":
        block = stimuli["pilot"]
    else:
        block = next(s for s in stimuli["scenarios"]
                     if s["id"] == trial["scenario"])
    first = block["first_request"]["text"]
    second = block["second_requests"][trial["condition"]]["text"]
    return first, second


def save_schedule(split, trials):
    p = STUDY / "schedules"
    p.mkdir(exist_ok=True)
    out = p / f"schedule_{split}.json"
    out.write_text(json.dumps(trials, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    return out
