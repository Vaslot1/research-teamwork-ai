"""Generate study/protocol/source_map.md from study/protocol/stimuli.json."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROTO = ROOT / "study" / "protocol"

stimuli = json.loads((PROTO / "stimuli.json").read_text(encoding="utf-8"))

rows = []
for scen in stimuli["scenarios"]:
    sid = scen["id"]
    fr = scen["first_request"]
    rows.append((sid, "first", "—", fr["paragraphs"], fr["sha256"]))
    for cond, d in scen["second_requests"].items():
        rows.append((sid, "second", cond, d["paragraphs"], d["sha256"]))
p = stimuli["pilot"]
rows.append((p["id"], "first", "—", p["first_request"]["paragraphs"],
             p["first_request"]["sha256"]))
for cond, d in p["second_requests"].items():
    rows.append((p["id"], "second", cond, d["paragraphs"], d["sha256"]))

lines = []
lines.append("# Source map — происхождение стимулов\n")
lines.append(
    "Источник основных стимулов: `inputs/02_Протокол_эксперимента_LLM.docx` "
    f"(SHA-256 `{stimuli['source']['sha256']}`).\n")
lines.append(
    "Индексация параграфов: только верхнеуровневые `w:p` тела документа, "
    "0-based; таблицы в счётчик не входят (дамп: `study/_scratch/doc02_dump.txt`). "
    "Извлечение: `study/tools/stage01_extract.py`, текст строго между маркерами "
    "«НАЧАЛО … ЗАПРОСА» / «КОНЕЦ … ЗАПРОСА», без правок и перевода.\n")
lines.append("## Таблица соответствия\n")
lines.append("| stimulus | ход | условие | параграфы DOCX-02 | SHA-256 текста |")
lines.append("|---|---|---|---|---|")
for sid, turn, cond, pr, h in rows:
    lines.append(f"| {sid} | {turn} | {cond} | {pr} | `{h}` |")
lines.append("")
lines.append("## Пилот\n")
lines.append(
    "`CASE-PILOT` составлен на этапе 01 по факт-паттерну файла 02 (P0021: "
    "«В январе обработано 90 из 100 обращений, в феврале 95 из 200; проект "
    "утверждает, что доля обработанных выросла»). Инвариантные блоки "
    "(продолжение, история реакции руководителя S/P, коллеги, каналы, поля "
    "ответа) переиспользованы дословно из извлечённых основных стимулов; "
    "сочинены только абзац фактов и формулировка проекта решения. Пилот не "
    "входит в шесть основных сценариев и в основной анализ.\n")
lines.append("## Происхождение дизайна (файл 01)\n")
lines.append(
    "- Человеческие исследования: H1 (Franzen & Mader 2023, репликация Asch; "
    "приложение с изображениями по ссылке не раскрылось — материал "
    "неподтверждён) и H2 (Sowden et al. 2018, публичный/приватный ответ). "
    "Это описания процедур с людьми, а не источники наших стимулов.\n"
    "- LLM-тесты: L1 (Zhu et al. 2025, ACL), L2 (Weng et al. 2025, ICLR/"
    "BenchForm), L3 (Bito et al. 2026, препринт), L4 (Bajaj & Tiganj 2026, "
    "препринт), L5 (Sharma et al. 2024, ICLR), L6 (Shoval et al. 2025, BMC "
    "Psychiatry — полный комплект изображений не подтверждён, в наш протокол "
    "не переносится).\n"
    "- X1 (Westover 2026, препринт): заявлены люди и LLM, но в проверенном "
    "тексте есть заглушки и арифметическая ошибка в описании дизайна; "
    "не используется как подтверждённое основание и источник численных "
    "эффектов.\n"
    "- Наши шесть рабочих ситуаций (CASE-S1…S6) — авторская разработка файла "
    "02; это адаптация отдельных экспериментальных принципов, не репликация "
    "одной статьи и не человеческие стимулы. Существование ссылки в каталоге "
    "не считается проверкой полного текста.\n")
lines.append("## Границы проверки\n")
lines.append(
    "Полные тексты статей и доступные шаблоны в файле 01 просмотрены его "
    "автором; автоматический запуск авторского кода не выполнялся. Отмеченные "
    "в каталоге сомнительные/недоступные материалы (приложение H1, изображения "
    "L6, пробелы X1) не превращаются в подтверждённые доказательства.\n")

(PROTO / "source_map.md").write_text("\n".join(lines), encoding="utf-8")
print(f"wrote {PROTO / 'source_map.md'}: {len(rows)} stimulus rows")
