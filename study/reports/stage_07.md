# Этап 07 — аудит, отчёт, воспроизводимость

**Статус: DONE** | завершён 2026-09-23 UTC | итог аудита: **PASS**

## Аудит (`study/reports/audit.json`, 12 проверок — все PASS)

| Проверка | Результат |
|---|---|
| frozen_hashes_match | совпадают |
| schedule_168 | 168 записей |
| trials_done | 168/168 |
| trial_ids_unique | да |
| gens_ok_ge_planned | 340 ≥ 336 (+4 документированных ретрая) |
| done_trials_nonempty | все непустые |
| embedded_errors_documented | 4 записи Alibaba content-filter, все перекрыты успешными ретраями |
| every_response_registered | да |
| no_pilot_in_main_coding | да |
| coding_rows_eq_done | 168=168 |
| 7_models_coded | M1–M7 |
| spend_within_cap | $1.9026 ≤ $5.0 |

## Артефакты

- `study/reports/report_ru.md` + `report_ru.docx` — полный отчёт (RU): дизайн, модели, эндпоинты, расход, результаты, ограничения. Статус **COMPLETE_PROVISIONAL** — авто-разметка без независимой проверки двумя людьми.
- `study/reports/talk_insertion_ru.md` — краткая вставка для доклада.
- `study/reports/collection_summary.json` — сводка сбора.
- `study/analysis/` — JSON/CSV анализа и таблицы.
- `study/rater_packets/` — слепые пакеты + инструкция + секретный маппинг.
- `study/reproducibility.zip` — протокол, модели, расписания, сырые данные пилота и основного сбора, разметка, код раннера, отчёты (97 файлов).
- `study/STATE.json` — финальное состояние; `study/budget/ledger.json` — леджер расходов.

## Фиксация ограничений в отчёте

Повторные прогоны моделей ≠ независимые участники; доли описательные (n=6/ячейка); NA не приравнены к нулю; приватное сообщение = V=1/P=0; W не интерпретируется как мотив; расхождения эндпоинтов и параметров (temperature/reasoning/quantization) задокументированы; сокращение до 1 повтора — заранее разрешённый вариант протокола по директиве пользователя.
