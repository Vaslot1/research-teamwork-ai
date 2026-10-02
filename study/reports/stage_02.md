# Отчёт этапа 02 — поиск моделей, endpoints, смета

Статус: **DONE** (с зафиксированным бюджетным предупреждением — см. ниже)
Выполнено: 2026-09-22T21:47Z (UTC) / 2026-09-22 23:47 CEST

## Что сделано

1. Правило отбора записано до сбора кандидатов:
   `study/models/selection_policy.json` (`latest_general_purpose`).
2. Каталог OpenRouter получен через `GET /api/v1/models` — **требуется
   Authorization** (анонимно — 403 «Access denied by security policy»;
   проверено, ключ использован только для официального API по HTTPS, значение
   нигде не сохранено). Снимок: `catalog_raw.json` (453 модели,
   2026-09-22T21:41Z).
3. По каждой из 7 выбранных моделей получены endpoints
   (`GET /api/v1/models/{id}/endpoints`) → `endpoints_raw.json`.
4. Официальные источники подтвердили новизну всех 7 выборов (ссылки в
   `model_selection.md`): OpenAI 22.09, Anthropic 22.09, Google 02.09,
   Moonshot 16.07, Z.ai 18.09, DeepSeek 10.09, Alibaba ~18.09.2026.
5. Реестр: `model_candidates.csv` (47 строк с причинами вкл/искл),
   `selected_models.json` (7 моделей с версией за endpoint, квантованием,
   модальностями, параметрами, ценами), `model_selection.md`.
6. Смета: `study/budget/estimate_draft.json` (Decimal, раздельные сценарии
   reasoning, +10% технический резерв).

## Выбранные модели (status: found in catalog + официальные источники)

| # | Семейство | model_id | Версия | Endpoint |
|---|---|---|---|---|
| M1 | OpenAI | openai/gpt-6-sol | 20260922 | openai (standard) |
| M2 | Anthropic | anthropic/claude-opus-5.5 | 20260921 | anthropic |
| M3 | Google | google/gemini-3.8-flash | 20260902 | google-ai-studio |
| M4 | Kimi | moonshotai/kimi-k3 | 20260715 | moonshotai/mxfp4 |
| M5 | GLM | z-ai/glm-5.3-flashx | 20260918 | z-ai/fp8 |
| M6 | DeepSeek | deepseek/deepseek-v4.1-flash | 20260910 | deepseek |
| M7 | Qwen | qwen/qwen3.8-omni-flash | 20260918 | alibaba |

Пользовательская таблица совпала с выбором по правилу во всех 7 случаях.
Все семейства покрыты; замен и неполноты нет.

## Важные факты для этапов 03–04

- `temperature` поддерживается: Anthropic, Google, Kimi, GLM, DeepSeek, Qwen;
  НЕ поддерживается у OpenAI gpt-6-sol (нет в supported_parameters) — для M1
  применяется штатный режим, параметр не отправляется.
- `seed` поддерживается у части моделей, но по протоколу seed генерации
  не задаётся.
- Opus 5.5: thinking нельзя отключить (официальный breaking change) —
  reasoning-расход неизбежен.
- GLM FlashX = те же веса, что GLM-5.3-Flash (serving tier) — ограничение
  зафиксировано.
- DeepSeek: старшие V4-линии сняты/роутятся в V4.1-Flash у разработчика.
- Endpoint-квантование: kimi mxfp4 (офиц.), glm fp8, deepseek unknown у
  официального; версии за endpoint зафиксированы (`…-2026MMDD`).

## ⚠ Бюджет

`MAX_BUDGET_USD=6`. Оценка полного плана (пилот 56 + основной 1008
генераций, +10% тех. резерв): **low $6.98 / expected $16.38 / high $37.72**.
Даже оптимистичный сценарий не вписывается в лимит из-за расценок Opus 5.5
($4/$20) и Kimi K3 ($3/$15) на прямых официальных endpoint'ах.

По правилам выборка/повторы молча не сокращаются. Пилот (~$0.36 low /
~$0.84 expected) вписывается и измерит фактический расход reasoning; после
него смета станет фактической, и при недостаточном остатке этап 05 будет
остановлен с сохранённым состоянием до решения пользователя (поднять
`MAX_BUDGET_USD` или явно изменить параметры объёма). Дешевле за счёт
flex/сторонних endpoint'ов — документированная опция (~$5.6 в low-сценарии),
но она меняет квантование/сервисный уровень и оставлена на решение
пользователя, не применена.

## Файлы этапа

`study/models/{selection_policy.json, catalog_raw.json, endpoints_raw.json,
model_candidates.csv, selected_models.json, model_selection.md}`;
`study/budget/estimate_draft.json`; `study/tools/stage02_estimate.py`,
`stage02_registry.py`.

Списано: $0 (только бесплатные GET-запросы метаданных). Резерв: $0.

## Следующий этап

03 — реализация исполнителя OpenRouter и mock-тесты (без сетевых генераций).
