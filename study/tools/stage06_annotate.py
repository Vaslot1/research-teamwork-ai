"""Stage 06 helpers: blinded rater packets + coding table assembly.

Packets for two human raters: random blind_id, scenario facts + both answers,
coding fields; model/condition hidden; mapping stored separately.
"""
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "study"
sys.path.insert(0, str(STUDY))
from runner.storage import read_json, read_jsonl  # noqa


def build_rater_packets(split="main"):
    """blinded packets -> study/rater_packets/{rater_packet.jsonl, mapping.json}
    """
    prog = read_json(STUDY / "data" / split / "progress.json",
                     {"trials": {}})["trials"]
    sched = {t["trial_id"]: t for t in
             read_json(STUDY / "schedules" / f"schedule_{split}.json")}
    stim = json.loads((STUDY / "protocol" / "stimuli.json")
                      .read_text(encoding="utf-8"))
    scen = {s["id"]: s for s in stim["scenarios"]}
    codings = {r["trial_id"]: r for r in
               read_jsonl(STUDY / "data" / split / "coding_auto.jsonl")}

    rng = random.Random(20260922)
    packets, mapping = [], {}
    for tid, rec in sorted(prog.items()):
        if rec.get("status") != "done":
            continue
        tr = sched.get(tid, {})
        s = scen.get(tr.get("scenario"))
        bid = "B" + hashlib.sha256(
            (tid + "rater-blind").encode()).hexdigest()[:10]
        packets.append({
            "blind_id": bid,
            "scenario_facts": {
                "scenario_id": tr.get("scenario"),
                "title": s["title"] if s else None,
                "key": s["key"]["key"] if s else None,
                "min_disclosure": s["key"]["min_disclosure"] if s else None,
                "first_request": s["first_request"]["text"] if s else None,
                "second_request": (s["second_requests"]
                                   [tr.get("condition")]["text"] if s else None),
            },
            "turn1_answer": rec.get("turn1_text"),
            "turn2_answer": rec.get("turn2_text"),
            "coding_fields": {
                "B": None, "F": None, "G": None, "A": None,
                "V": None, "P": None, "W": None,
                "na_reason": None, "format_flag": None},
            "auto_reference": {k: codings.get(tid, {}).get(k)
                               for k in ("B", "F", "G", "A", "V", "P", "W")},
        })
        mapping[bid] = {"trial_id": tid, "model_index": tr.get("model_index"),
                        "model_id": tr.get("model_id"),
                        "condition": tr.get("condition"),
                        "scenario": tr.get("scenario")}
    rng.shuffle(packets)
    out = STUDY / "rater_packets"
    out.mkdir(exist_ok=True)
    with open(out / "rater_packet.jsonl", "w", encoding="utf-8") as f:
        for p in packets:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    (out / "mapping_SECRET.json").write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(packets)


def build_coding_table(split="main"):
    """coding_table.csv: per-trial auto + empty human columns."""
    import csv
    codings = read_jsonl(STUDY / "data" / split / "coding_auto.jsonl")
    out = STUDY / "analysis"
    out.mkdir(exist_ok=True)
    cols = ["trial_id", "model_index", "condition", "scenario",
            "B_auto", "F_auto", "G_auto", "A_auto", "V_auto", "P_auto",
            "W_auto", "format_ok", "truncated", "refusal",
            "human_1", "human_2", "consensus", "review_status"]
    with open(out / f"coding_table_{split}.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for c in sorted(codings, key=lambda x: x["trial_id"]):
            w.writerow({
                "trial_id": c["trial_id"],
                "model_index": c.get("model_index"),
                "condition": c.get("condition"),
                "scenario": c.get("scenario"),
                "B_auto": c.get("B"), "F_auto": c.get("F"),
                "G_auto": c.get("G"), "A_auto": c.get("A"),
                "V_auto": c.get("V"), "P_auto": c.get("P"),
                "W_auto": c.get("W"),
                "format_ok": c.get("format_ok"),
                "truncated": c.get("truncated"),
                "refusal": c.get("refusal"),
                "human_1": "", "human_2": "", "consensus": "",
                "review_status": "auto_only"})
    return len(codings)


if __name__ == "__main__":
    n1 = build_coding_table("main")
    n2 = build_rater_packets("main")
    print(f"coding_table rows={n1}; rater packets={n2}")
