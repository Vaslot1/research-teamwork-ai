"""Stage 02: build model_candidates.csv and selected_models.json from
catalog_raw.json + endpoints_raw.json + manually verified release facts."""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = ROOT / "study" / "models"

catalog = json.loads((MODELS_DIR / "catalog_raw.json").read_text(encoding="utf-8"))["data"]
cat = {m["id"]: m for m in catalog}
eps_raw = json.loads((MODELS_DIR / "endpoints_raw.json").read_text(encoding="utf-8"))
eps = {k: (v["data"]["endpoints"] if "data" in v else [])
       for k, v in eps_raw["endpoints"].items()}


def cdate(mid):
    c = cat[mid].get("created")
    return (datetime.fromtimestamp(c, timezone.utc).date().isoformat()
            if c else None)


# candidate rows: (family, model_id, decision, reason)
CAND = [
    ("OpenAI", "openai/gpt-6-sol", "SELECTED",
     "Newest OpenAI general-purpose release (OpenAI announcement 2026-09-22); "
     "main full-size tier of the Sol/Luna pair; Astra is flagship but older "
     "release (catalog 2026-09-04)."),
    ("OpenAI", "openai/gpt-6-sol-pro", "excluded",
     "Same underlying model with reasoning.mode=pro serving config; not a "
     "separate size."),
    ("OpenAI", "openai/gpt-6-luna", "excluded",
     "Compact high-volume tier of the same release; policy picks main "
     "full-size of simultaneous sizes."),
    ("OpenAI", "openai/gpt-6-luna-pro", "excluded",
     "Compact tier + pro reasoning serving variant."),
    ("OpenAI", "openai/gpt-6-astra", "excluded",
     "Flagship tier but earlier release (catalog 2026-09-04, OpenAI early "
     "Sept 2026); 'newest' rule applies."),
    ("OpenAI", "openai/gpt-6-astra-pro", "excluded", "Older release; pro serving variant."),
    ("OpenAI", "openai/gpt-5.6-sol", "excluded", "Previous generation (2026-07-09)."),
    ("OpenAI", "openai/gpt-chat-latest", "excluded", "Floating alias; 'latest' aliases banned."),
    ("OpenAI", "openai/gpt-5.3-codex", "excluded", "Coding-specialized line."),
    ("OpenAI", "openai/gpt-audio", "excluded", "Audio-specialized."),

    ("Anthropic", "anthropic/claude-opus-5.5", "SELECTED",
     "Anthropic 'Latest' release 2026-09-22, first of Claude 5.5 family; "
     "official docs confirm model id claude-opus-5-5."),
    ("Anthropic", "anthropic/claude-fable-5.1", "excluded",
     "Earlier release (catalog 2026-09-01)."),
    ("Anthropic", "anthropic/claude-opus-5", "excluded", "2026-07-24, superseded by 5.5."),
    ("Anthropic", "anthropic/claude-sonnet-5", "excluded", "2026-06-30, older line."),
    ("Anthropic", "anthropic/claude-haiku-4.5", "excluded", "2025-10-15, older."),

    ("Google", "google/gemini-3.8-flash", "SELECTED",
     "GA release 2026-09-02 (Google blog + model card); newest general "
     "Gemini; no 3.8 Pro in catalog. Flash = main general tier of 3.8 line."),
    ("Google", "google/gemini-3.7-flash", "excluded", "2026-08-13, superseded by 3.8."),
    ("Google", "google/gemini-3.6-flash", "excluded", "2026-07-21, older."),
    ("Google", "google/gemini-3.1-pro-preview", "excluded",
     "Preview, 2026-02-19, older than 3.8 Flash GA."),
    ("Google", "google/gemini-3.5-flash-lite", "excluded", "Lite compact tier, older."),
    ("Google", "google/gemini-3.1-flash-image", "excluded", "Image-generation specialized (Nano Banana)."),
    ("Google", "google/lyria-3-pro-preview", "excluded", "Audio-specialized."),
    ("Google", "google/gemma-4-31b-it", "excluded", "Open-weight Gemma line, 2026-04-02, older."),

    ("Kimi", "moonshotai/kimi-k3", "SELECTED",
     "Moonshot release 2026-07-16 (official GitHub/HF repo, 'most capable "
     "model to date'); newest general Moonshot entry."),
    ("Kimi", "moonshotai/kimi-k2.7-code", "excluded", "Coding-only specialized (2026-06-12)."),
    ("Kimi", "moonshotai/kimi-k2.6", "excluded", "2026-04-20, older."),
    ("Kimi", "moonshotai/kimi-k2.5", "excluded", "2026-01-27, older."),
    ("Kimi", "moonshotai/kimi-k2-thinking", "excluded", "2025-11-06, older."),

    ("GLM", "z-ai/glm-5.3-flashx", "SELECTED",
     "Newest Z.ai release (2026-09-18). NOTE: serving tier of GLM-5.3-Flash "
     "(identical weights, ~200 tok/s), not new weights — recorded as "
     "limitation; still the newest available general multimodal entry."),
    ("GLM", "z-ai/glm-5.3-flash", "excluded",
     "2026-08-26; same weights as FlashX, earlier serving tier."),
    ("GLM", "z-ai/glm-5.3", "excluded",
     "2026-08-18; flagship text-only of 5.3 line, earlier than FlashX."),
    ("GLM", "z-ai/glm-5.2", "excluded", "2026-06-16, older."),
    ("GLM", "z-ai/glm-5v-turbo", "excluded", "2026-04-01, older."),
    ("GLM", "z-ai/glm-4.7-flash", "excluded", "2026-01-19, older."),

    ("DeepSeek", "deepseek/deepseek-v4.1-flash", "SELECTED",
     "DeepSeek official release 2026-09-10; smallest of new CED family but "
     "V4.1-Pro not yet released; older V4 Flash/Pro retired or rerouted to "
     "V4.1-Flash upstream."),
    ("DeepSeek", "deepseek/deepseek-v4-pro-0813", "excluded",
     "2026-08-12; upstream API routes v4-pro traffic to V4.1-Flash since "
     "2026-09-14; deprecated path."),
    ("DeepSeek", "deepseek/deepseek-v4-flash-vision-exp", "excluded",
     "2026-08-21; retired upstream, name reroutes to V4.1-Flash."),
    ("DeepSeek", "deepseek/deepseek-v4-flash-0731", "excluded",
     "2026-07-31; retired upstream."),
    ("DeepSeek", "deepseek/deepseek-v4-flash", "excluded",
     "2026-04-24; retired upstream, reroutes to V4.1-Flash."),
    ("DeepSeek", "deepseek/deepseek-v3.2", "excluded", "2025-12-01, older line."),

    ("Qwen", "qwen/qwen3.8-omni-flash", "SELECTED",
     "Newest Qwen release (Alibaba docs updated 2026-09-17/18; catalog "
     "2026-09-21). Omni-modal general model; text dialog works without "
     "media input."),
    ("Qwen", "qwen/qwen3.8-max-0902", "excluded", "2026-09-03, flagship snapshot but older."),
    ("Qwen", "qwen/qwen3.8-flash", "excluded", "2026-08-26, older."),
    ("Qwen", "qwen/qwen3.8-27b", "excluded", "2026-08-14, older."),
    ("Qwen", "qwen/qwen3.8-2.4t-a95b", "excluded", "2026-08-12, older."),
    ("Qwen", "qwen/qwen3.7-flash", "excluded", "2026-07-27, older."),
    ("Qwen", "qwen/qwen3-coder-plus", "excluded", "Coding-specialized line."),
]

CHOSEN = {
    "OpenAI":    ("openai/gpt-6-sol",            "openai"),
    "Anthropic": ("anthropic/claude-opus-5.5",   "anthropic"),
    "Google":    ("google/gemini-3.8-flash",     "google-ai-studio"),
    "Kimi":      ("moonshotai/kimi-k3",          "moonshotai/mxfp4"),
    "GLM":       ("z-ai/glm-5.3-flashx",         "z-ai/fp8"),
    "DeepSeek":  ("deepseek/deepseek-v4.1-flash", "deepseek"),
    "Qwen":      ("qwen/qwen3.8-omni-flash",     "alibaba"),
}

# --- candidates CSV -------------------------------------------------------
with open(MODELS_DIR / "model_candidates.csv", "w", newline="",
          encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["family", "model_id", "catalog_created", "decision", "reason"])
    for fam, mid, dec, why in CAND:
        w.writerow([fam, mid, cdate(mid) if mid in cat else "n/a", dec, why])

# --- selected_models.json --------------------------------------------------
sel = {"selected_utc": eps_raw["retrieved_utc"],
       "catalog_snapshot": "study/models/catalog_raw.json",
       "endpoints_snapshot": "study/models/endpoints_raw.json",
       "policy": "study/models/selection_policy.json",
       "verification_status": "found in catalog + official sources; NOT yet "
                              "verified by generation (pilot = stage 04)",
       "models": []}

order = ["OpenAI", "Anthropic", "Google", "Kimi", "GLM", "DeepSeek", "Qwen"]
for i, fam in enumerate(order, start=1):
    mid, tag = CHOSEN[fam]
    m = cat[mid]
    arch = m.get("architecture", {})
    ep = next(e for e in eps[mid] if e.get("tag") == tag)
    pr = ep["pricing"]
    sel["models"].append({
        "family": fam,
        "index": i,
        "model_id": mid,
        "canonical_slug": mid,
        "display_name": m.get("name"),
        "catalog_created": cdate(mid),
        "endpoint": {
            "provider_name": ep.get("provider_name"),
            "tag": tag,
            "underlying_version": ep.get("name", "").split("|")[-1].strip(),
            "quantization": ep.get("quantization"),
            "context_length": ep.get("context_length"),
            "max_completion_tokens": ep.get("max_completion_tokens"),
            "max_prompt_tokens": ep.get("max_prompt_tokens"),
            "pricing_usd_per_token": {"prompt": pr.get("prompt"),
                                      "completion": pr.get("completion"),
                                      "input_cache_read": pr.get("input_cache_read")},
            "endpoint_supported_parameters": ep.get("supported_parameters"),
            "status": ep.get("status"),
        },
        "modalities": {"in": arch.get("input_modalities"),
                       "out": arch.get("output_modalities")},
        "model_supported_parameters": m.get("supported_parameters"),
        "all_endpoint_tags": [e.get("tag") for e in eps[mid]],
        "developer": {"OpenAI": "OpenAI", "Anthropic": "Anthropic",
                      "Google": "Google DeepMind", "Kimi": "Moonshot AI",
                      "GLM": "Z.ai (Zhipu)", "DeepSeek": "DeepSeek",
                      "Qwen": "Alibaba Qwen"}[fam],
    })

(MODELS_DIR / "selected_models.json").write_text(
    json.dumps(sel, ensure_ascii=False, indent=2), encoding="utf-8")
print("wrote model_candidates.csv:", len(CAND), "rows")
print("wrote selected_models.json:", len(sel["models"]), "models")
for mm in sel["models"]:
    print(f"  M{mm['index']} {mm['family']:9} {mm['model_id']:36} -> {mm['endpoint']['tag']} ({mm['endpoint']['underlying_version']})")
