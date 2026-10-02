"""Stage 02: cost estimate for pilot (56 gen) + main (1008 gen) + retries.

Token model per generation (Decimal; prices USD/token from endpoints_raw.json
chosen endpoint):
  turn1: in = REQ1 ; out = VIS1 + REAS
  turn2: in = REQ1 + VIS1 + REQ2 ; out = VIS2 + REAS
REAS = reasoning tokens billed as completion (cannot be measured until pilot;
modelled in low/expected/high scenarios).
"""
import json
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# token assumptions (Russian ~2.5 chars/token; measured stimuli: req1 ~744 chars,
# req2 ~1161 chars; visible outputs capped at ~50 and ~105 words)
REQ1 = Decimal("350")
REQ2 = Decimal("500")
VIS1 = Decimal("200")
VIS2 = Decimal("350")
REAS = {"low": Decimal("400"), "expected": Decimal("1500"),
        "high": Decimal("4000")}   # per generation
RETRY_FACTOR = Decimal("1.10")      # technical retries reserve

MODELS = {
    # family: (model_id, chosen tag, prompt$/tok, completion$/tok)
    "OpenAI":    ("openai/gpt-6-sol",           "openai",       "0.000002",   "0.00001"),
    "Anthropic": ("anthropic/claude-opus-5.5",  "anthropic",    "0.000004",   "0.00002"),
    "Google":    ("google/gemini-3.8-flash",    "google-ai-studio", "0.00000075", "0.00000375"),
    "Kimi":      ("moonshotai/kimi-k3",         "moonshotai/mxfp4", "0.000003", "0.000015"),
    "GLM":       ("z-ai/glm-5.3-flashx",        "z-ai/fp8",     "0.00000037", "0.00000125"),
    "DeepSeek":  ("deepseek/deepseek-v4.1-flash", "deepseek",   "0.00000015", "0.0000006"),
    "Qwen":      ("qwen/qwen3.8-omni-flash",    "alibaba",      "0.00000015", "0.00000047"),
}

import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner.env import load_dotenv  # noqa: E402
load_dotenv()

REPS = int(os.environ.get("REPETITIONS", "3"))
TRIALS_MAIN_PER_MODEL = 24 * REPS   # 6 scen x 4 cond x REPS
TRIALS_PILOT_PER_MODEL = 4
BUDGET = Decimal(os.environ.get("MAX_BUDGET_USD", "0"))


def trial_cost(p, c, reas):
    in_tok = REQ1 + (REQ1 + VIS1 + REQ2)          # 2 generations
    out_tok = (VIS1 + reas) + (VIS2 + reas)
    return in_tok * p + out_tok * c


report = {"assumptions": {
    "REQ1": str(REQ1), "REQ2": str(REQ2), "VIS1": str(VIS1), "VIS2": str(VIS2),
    "reasoning_per_generation": {k: str(v) for k, v in REAS.items()},
    "retry_factor": str(RETRY_FACTOR),
    "note": "turn-2 input = turn-1 request + real turn-1 visible response + "
            "turn-2 request; reasoning billed once as completion tokens"},
    "per_model": {}, "totals": {}}

tot = {k: Decimal("0") for k in REAS}
for fam, (mid, tag, p, c) in MODELS.items():
    p, c = Decimal(p), Decimal(c)
    row = {"model_id": mid, "endpoint_tag": tag,
           "price_prompt_per_tok": str(p), "price_completion_per_tok": str(c)}
    for scen, reas in REAS.items():
        t = trial_cost(p, c, reas)
        pilot = t * TRIALS_PILOT_PER_MODEL * RETRY_FACTOR
        main = t * TRIALS_MAIN_PER_MODEL * RETRY_FACTOR
        row[scen] = {"per_trial": str(t.quantize(Decimal("0.000001"))),
                     "pilot_usd": str(pilot.quantize(Decimal("0.0001"))),
                     "main_usd": str(main.quantize(Decimal("0.0001"))),
                     "total_usd": str((pilot + main).quantize(Decimal("0.0001")))}
        tot[scen] += pilot + main
    report["per_model"][fam] = row

for k, v in tot.items():
    report["totals"][k] = str(v.quantize(Decimal("0.01")))

report["budget_usd"] = str(BUDGET)
report["repetitions"] = REPS
report["planned_main_generations"] = TRIALS_MAIN_PER_MODEL * 7 * 2
report["fits_budget"] = {k: (v <= BUDGET) for k, v in tot.items()}

out = ROOT / "study" / "budget"
out.mkdir(parents=True, exist_ok=True)
(out / "estimate_draft.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"{'family':10} {'low':>8} {'expected':>9} {'high':>8}  (USD total incl. pilot+main+retries)")
for fam, row in report["per_model"].items():
    print(f"{fam:10} {row['low']['total_usd']:>8} {row['expected']['total_usd']:>9} {row['high']['total_usd']:>8}")
print("TOTALS:", {k: v for k, v in report['totals'].items()})
print(f"reps={REPS} planned_main_gens={report['planned_main_generations']}")
print(f"fits ${BUDGET}:", report["fits_budget"])
