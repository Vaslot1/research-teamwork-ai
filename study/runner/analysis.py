"""Analysis tables + contrasts for stage 06.

Reads trials (progress) + coding_auto; computes planned/observed/valid/NA/
refusal/technical-loss, V/P/channel/B/F/G/W shares with visible denominators,
contrast formulas from the codebook, and missingness sensitivity bounds.
Trials are NOT independent people — no significance tests.
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

from .env import STUDY
from .storage import data_dir, read_jsonl

FIELDS = ["B", "F", "G", "A", "V", "P", "W"]
CONTRASTS = {
    "dR0": ("S0", "P0"),   # ΔR(0) = V(S0) - V(P0)
    "dR1": ("S1", "P1"),   # ΔR(1) = V(S1) - V(P1)
    "dMS": ("S1", "S0"),   # ΔM(S) = V(S1) - V(S0)
    "dMP": ("P1", "P0"),   # ΔM(P) = V(P1) - V(P0)
}


def load_trials(split):
    prog = (data_dir(split) / "progress.json")
    if not prog.exists():
        return {}
    return json.loads(prog.read_text(encoding="utf-8"))["trials"]


def load_codings(split):
    out = {}
    for r in read_jsonl(data_dir(split) / "coding_auto.jsonl"):
        out[r["trial_id"]] = r
    return out


def cell_stats(recs):
    """recs: list of coding dicts (may be empty)."""
    n = len(recs)
    st = {"N": n}
    for f in ["V", "P", "B", "F", "G", "W"]:
        vals = [r.get(f) for r in recs]
        valid = [v for v in vals if v in (0, 1)]
        st[f] = {"n_valid": len(valid),
                 "n_1": sum(v for v in valid if v == 1),
                 "share": (sum(v for v in valid) / len(valid)
                          if valid else None),
                 "na": sum(1 for v in vals if v == "NA")}
    ch = defaultdict(int)
    for r in recs:
        ch[str(r.get("A"))] += 1
    st["channels"] = dict(ch)
    st["refusals"] = sum(1 for r in recs if r.get("refusal"))
    st["format_bad"] = sum(1 for r in recs if not r.get("format_ok"))
    st["truncated"] = sum(1 for r in recs if r.get("truncated"))
    # missingness bounds for V
    v = st["V"]
    lo = v["n_1"] / n if n else None                      # all NA/missing -> 0
    hi = (v["n_1"] + v["na"] + (n - len(recs))) / n if n else None
    hi = (v["n_1"] + v["na"]) / n if n else None          # all NA -> 1
    st["V_bounds"] = {"low": lo, "high": hi}
    return st


def analyze(split="main"):
    trials = load_trials(split)
    codings = load_codings(split)

    # attach metadata from schedule-side trial ids
    def meta(tid):
        parts = tid.split("-")
        # M{i}-R{w}-CASE-S{n}-{cond}  or  M{i}-PILOT-{cond}
        return {"model_index": int(parts[0][1:]),
                "scenario": parts[2] if parts[1] == "PILOT" else "-".join(parts[2:4]),
                "condition": parts[-1] if parts[1] == "PILOT" else parts[-1]}

    cells = defaultdict(list)
    trial_rows = []
    for tid, c in codings.items():
        m = meta(tid)
        cells[(m["model_index"], m["condition"])].append(c)
        cells[(m["model_index"], "ALL")].append(c)
        trial_rows.append({"trial_id": tid, **m, **{f: c.get(f) for f in FIELDS},
                           "refusal": c.get("refusal"),
                           "truncated": c.get("truncated"),
                           "format_ok": c.get("format_ok")})

    per_mc = {}
    for (mi, cond), recs in sorted(cells.items()):
        per_mc[f"M{mi}|{cond}"] = cell_stats(recs)

    # contrasts per model
    contrasts = {}
    for mi in sorted({m["model_index"] for m in map(meta, codings)} | set()):
        row = {}
        for name, (a, b) in CONTRASTS.items():
            sa = per_mc.get(f"M{mi}|{a}", {}).get("V", {}).get("share")
            sb = per_mc.get(f"M{mi}|{b}", {}).get("V", {}).get("share")
            row[name] = (sa - sb) if (sa is not None and sb is not None) else None
            row[f"{name}_terms"] = {a: sa, b: sb}
        i = (row["dMS"] - row["dMP"]) if (row["dMS"] is not None
                                        and row["dMP"] is not None) else None
        row["I"] = i
        contrasts[f"M{mi}"] = row

    # per scenario x condition (all models pooled — descriptive only)
    sc_cells = defaultdict(list)
    for tid, c in codings.items():
        m = meta(tid)
        sc_cells[(m["scenario"], m["condition"])].append(c)
    per_sc = {f"{s}|{c}": cell_stats(r) for (s, c), r in sorted(sc_cells.items())}

    return {"split": split,
            "n_coded": len(codings),
            "n_trials_done": sum(1 for t in trials.values()
                                 if t.get("status") == "done"),
            "per_model_condition": per_mc,
            "per_scenario_condition": per_sc,
            "contrasts": contrasts,
            "trials_table": trial_rows}


def write_outputs(split="main", out_dir=None):
    res = analyze(split)
    out_dir = Path(out_dir or STUDY / "analysis")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"analysis_{split}.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")

    def flat_stats(d):
        row = {"N": d["N"], "refusals": d["refusals"],
               "truncated": d["truncated"], "format_bad": d["format_bad"]}
        for f in ["V", "P", "B", "F", "G", "W"]:
            row[f"{f}_n"], row[f"{f}_1"] = d[f]["n_valid"], d[f]["n_1"]
            row[f"{f}_share"] = d[f]["share"]
            row[f"{f}_na"] = d[f]["na"]
        row["V_low"], row["V_high"] = d["V_bounds"]["low"], d["V_bounds"]["high"]
        for k, v in d["channels"].items():
            row[f"ch_{k}"] = v
        return row

    with open(out_dir / f"by_model_condition_{split}.csv", "w", newline="",
              encoding="utf-8") as f:
        keys = sorted(res["per_model_condition"])
        if keys:
            fieldnames = ["cell"]
            for k in keys:
                for col in flat_stats(res["per_model_condition"][k]):
                    if col not in fieldnames:
                        fieldnames.append(col)
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for k in keys:
                w.writerow({"cell": k,
                            **flat_stats(res["per_model_condition"][k])})

    with open(out_dir / f"contrasts_{split}.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["model", "dR0", "dR1", "dMS", "dMP", "I",
                    "S0", "P0", "S1", "P1"])
        for mk, row in sorted(res["contrasts"].items()):
            w.writerow([mk, row["dR0"], row["dR1"], row["dMS"], row["dMP"],
                        row["I"],
                        row["dR0_terms"]["S0"], row["dR0_terms"]["P0"],
                        row["dR1_terms"]["S1"], row["dR1_terms"]["P1"]])
    return res
