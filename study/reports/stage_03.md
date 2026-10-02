# Отчёт этапа 03 — исполнитель OpenRouter и mock-тесты

Статус: **DONE** · Выполнено: 2026-09-22 ~22:00 UTC
Сетевых генераций не выполнялось; платных вызовов не было.

## Реализация (`study/runner/`)

| Модуль | Содержание |
|---|---|
| `env.py` | Загрузка `.env`, флаговый статус (ключ нигде не выводится/не сохраняется), гейты: `OPENROUTER_API_KEY` + `ALLOW_PAID_RUN=true` + `MAX_BUDGET_USD>0`. Бюджет не назначается. |
| `storage.py` | Append-only JSONL (fsync) — неизменяемые сырые записи; атомарные JSON-записи; `Progress` — durable-статусы испытаний. |
| `budget.py` | `BudgetLedger`: атомарный резерв до вызова, `settle` фактической стоимостью, `uncertain` для таймаутов (зарезервированная сумма продолжает считаться против лимита до сверки). |
| `client.py` | POST `/api/v1/chat/completions` по HTTPS; заголовок `X-OpenRouter-Cache: false` (OR7); максимум 3 транспортных попытки; `Retry-After` для 429; джиттерованный backoff для 5xx/timeout/net; без ретраев на 400/401/402/403; транспорт инъектируемый для тестов. |
| `schedule.py` | Детерминированные расписания. Main: 7×6×4×3=504, seed=`220926+100·M+wave`, перемешивание 24 пар внутри модели×волны, волны последовательны, модели чередуются равномерно. Pilot: 28 (4 условия × 7 моделей на CASE-PILOT). Seed не входит в промпты. `provider.only`+`allow_fallbacks=false`+`require_parameters=true` (+`quantizations` для tag-ов вида `prov/quant`). |
| `pipeline.py` | Двухходовое испытание: turn1 = один user-промпт; turn2 = `[user:first, assistant:фактический ответ 1, user:second]`. Регистрация запроса ДО отправки; сырой ответ целиком в `responses.jsonl`; проверка возвращённых `model`/`provider`; завершённый ход не перезапускается; при сбое turn2 повторяется только turn2 с тем же payload. Concurrency ≤2 глобально, ≤1 на модель. Гейты перед каждым вызовом. |
| `coding.py` | `coding_auto` v1: разбор полей `Рабочий вывод/Действие/Сообщение`, per-scenario regex-правила для B/F/G/A/V/P/W, цитаты-доказательства и id сработавшего правила; NA ≠ 0; «не сообщать»+текст → NA; refusal/timeout/truncation сохраняются. |
| `analysis.py` | Таблицы по модели×условию и сценарий×условию: N, валидные, NA, отказы, усечения, доли V/P/B/F/G/W с видимыми знаменателями, границы чувствительности к пропускам (low/high), контрасты ΔR(0), ΔR(1), ΔM(S), ΔM(P), I. Без p-value. |
| `cli.py` | Команды `validate / pilot / run / resume / annotate / analyze / report / status`. Гейт `run`: сверка хэшей frozen-манифеста + остаток бюджета vs expected-оценка оставшегося плана. |

## Параметры генерации (зафиксировано до пилота)

- Отправляется `model`, `messages`, `max_tokens=8192`, `usage.include`,
  `provider` — и `temperature=0.7` только там, где endpoint её поддерживает
  (по `prompts/03`); у OpenAI/Anthropic/Kimi `temperature` в endpoint не
  поддерживается → штатный режим, задокументировано в
  `study/models/generation_settings.json`.
- `top_p`, `seed`, `reasoning` не отправляются — дефолты провайдера.
- Системный промпт отсутствует.
- Резерв на вызов = 3000 prompt + 8192 completion токенов по цене endpoint'а
  (консервативная верхняя граница; сверка по факту `usage.cost`).

## Mock-тесты (`study/tests/test_runner_mock.py`) — 21 шт, все PASS

Отказы, B=0, ambiguous-формат→NA, пустой/усечённый вывод, 429+Retry-After,
таймаут (unknown-расход), ретрай только второго хода, resume без повторов,
отсутствие ключа, конкурентный бюджетный лимит, pinning без fallback,
разделение pilot/main, утечка ключа/гипотез/seed в промптах, 504 уникальных
trial_id, 18 на модель×условие, формула seed.

`python study/run.py validate` → **PASS** (env, sha256 стимулов, 7 моделей,
endpoints, `max_tokens`, смета).

## Файлы

`study/runner/{__init__,env,storage,budget,client,schedule,pipeline,coding,analysis,cli}.py`,
`study/run.py`, `study/tests/test_runner_mock.py`.

## Следующий этап

04 — платный пилот (28 испытаний / 56 генераций): env-гейты готовы,
смета пилота ~$0.36–0.84 вписывается в `MAX_BUDGET_USD=6`.
