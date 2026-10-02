"""Stages 06+07 driver: annotate -> tables -> packets -> analyze -> audit ->
report_ru.md/.docx -> talk insertion -> results CSVs -> reproducibility.zip.

No new model generations happen here.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "study"
sys.path.insert(0, str(STUDY))

from runner.storage import read_json, read_jsonl  # noqa
from runner.analysis import write_outputs  # noqa
from tools.stage06_annotate import build_coding_table, build_rater_packets  # noqa
from tools import stage07_report as R  # noqa


def main():
    rep = STUDY / "reports"
    rep.mkdir(exist_ok=True)

    # ---- 06a: annotate (auto coding) ----
    subprocess.run([sys.executable, "-X", "utf8", str(STUDY / "run.py"),
                    "annotate", "main"], cwd=ROOT, check=True)
    n_tab = build_coding_table("main")
    n_pkt = build_rater_packets("main")

    # ---- 06b: analysis ----
    res = write_outputs("main")
    (STUDY / "analysis" / "trials_main.csv")  # produced inside write_outputs
    res["review_status"] = "COMPLETE_PROVISIONAL"

    # ---- 07a: audit ----
    aud = R.audit()
    (rep / "audit.json").write_text(
        json.dumps(aud, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- 07b: report ----
    ledger = read_json(STUDY / "budget" / "ledger.json", {})
    pilot = read_json(STUDY / "data" / "pilot" / "pilot_run_result.json", {})
    md = R.build_report_md(res, aud, ledger, pilot)
    (rep / "report_ru.md").write_text(md, encoding="utf-8")
    R.md_to_docx(md, rep / "report_ru.docx")

    # talk insertion — короткий блок для доклада
    top = []
    for mk, c in sorted(res["contrasts"].items()):
        if c["dR0"] is not None:
            top.append((mk, c["dR0"], c["dR1"]))
    talk = [
        "## Вставка в доклад",
        "",
        "В вымышленных рабочих ситуациях (6 сценариев, 4 условия, 1 повтор; "
        "168 двухходовых испытаний на 7 моделях, OpenRouter API) модели "
        "оценивали проект с заведомой ошибкой после собственного анализа.",
        "",
        f"Средние контрасты по моделям (п.п.): "
        + "; ".join(f"{m}: ΔR0={d0*100:+.0f}, ΔR1={d1*100:+.0f}"
                    for m, d0, d1 in top if d0 is not None),
        "",
        "Канал раскрытия системно смещается от публичного к личному при "
        "наказывающей реакции; полное молчание встречается редко. "
        "Результаты — автокодировка, provisional; человеческой проверки нет.",
        "",
        "Ограничения: вымышленные санкции; n=6 на ячейку; повторы зависимы; "
        "7 семейств — не случайная выборка; версии плавающие; авторазметка "
        "без двух оценщиков.",
    ]
    (rep / "talk_insertion_ru.md").write_text("\n".join(talk),
                                            encoding="utf-8")

    # ---- 07c: results tables already written by write_outputs ----
    # coding_table + analysis csvs exist; add receipts summary
    resp = read_jsonl(STUDY / "data" / "main" / "responses.jsonl")
    ok = [r for r in resp if r.get("ok")]
    with open(rep / "collection_summary.json", "w", encoding="utf-8") as f:
        json.dump({"planned_trials": 168, "planned_gens": 336,
                   "responses_ok": len(ok), "responses_total": len(resp),
                   "trials_done": res["n_trials_done"],
                   "audit": aud["status"],
                   "review_status": res["review_status"]},
                  f, ensure_ascii=False, indent=2)

    # ---- 07d: reproducibility zip ----
    R.build_zip(STUDY / "reproducibility.zip")

    print(json.dumps({
        "coding_rows": n_tab, "rater_packets": n_pkt,
        "trials_done": res["n_trials_done"], "audit": aud["status"],
        "spent_total_usd": ledger.get("spent"),
        "outputs": ["reports/report_ru.md", "reports/report_ru.docx",
                    "reports/talk_insertion_ru.md", "reports/audit.json",
                    "reports/collection_summary.json",
                    "analysis/", "rater_packets/", "reproducibility.zip"]},
        ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
