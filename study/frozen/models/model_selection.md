# Выбор моделей — этап 02

Дата проверки каталога: 2026-09-22 ~21:41 UTC (снимок `catalog_raw.json`,
453 модели; endpoints — `endpoints_raw.json`). Правило отбора:
`selection_policy.json` (`latest_general_purpose`). Статус: **«найдено в
каталоге и подтверждено официальными источниками»** — работоспособность
endpoint проверит пилот (этап 04). Выборка не заморожена до конца пилота.

## Итог выбора (индексы M1–M7 в порядке пользователя)

| # | Семейство | model_id | Версия за endpoint | Релиз разработчика | Endpoint tag | Цена $/1M in/out |
|---|---|---|---|---|---|---|
| M1 | OpenAI | `openai/gpt-6-sol` | `openai/gpt-6-sol-20260922` | 2026-09-22 | `openai` | 2.00 / 10.00 |
| M2 | Anthropic | `anthropic/claude-opus-5.5` | `anthropic/claude-opus-5.5-20260921` | 2026-09-22 | `anthropic` | 4.00 / 20.00 |
| M3 | Google | `google/gemini-3.8-flash` | `google/gemini-3.8-flash-20260902` | 2026-09-02 | `google-ai-studio` | 0.75 / 3.75 |
| M4 | Kimi | `moonshotai/kimi-k3` | `moonshotai/kimi-k3-20260715` | 2026-07-16 | `moonshotai/mxfp4` | 3.00 / 15.00 |
| M5 | GLM | `z-ai/glm-5.3-flashx` | `z-ai/glm-5.3-flashx-20260918` | 2026-09-18 | `z-ai/fp8` | 0.37 / 1.25 |
| M6 | DeepSeek | `deepseek/deepseek-v4.1-flash` | `deepseek/deepseek-v4.1-flash-20260910` | 2026-09-10 | `deepseek` | 0.15 / 0.60 |
| M7 | Qwen | `qwen/qwen3.8-omni-flash` | `qwen/qwen3.8-omni-flash-20260918` | ~2026-09-18 | `alibaba` | 0.15 / 0.47 |

Все 7 идентификаторов из пользовательской таблицы подтвердились как новейшие
подходящие релизы своих семейств — совпадение зафиксировано, выбор сделан по
правилу, а не по таблице.

## Обоснование и источники по семействам

**M1 OpenAI — `openai/gpt-6-sol`.** OpenAI 22.09.2026 выпустила GPT-6 Sol и
Luna (community.openai.com announcement; TechCrunch 22.09.2026;
developers.openai.com model page). Sol — основной полноразмерный уровень
новой пары (ниже флагмана Astra, выше компактной Luna); `gpt-6-sol-pro` и
`gpt-6-luna-pro` — те же веса с `reasoning.mode=pro`, т.е. конфигурация
сервинга, а не отдельный размер. Astra (каталог 04.09) — более ранний
флагманский релиз; правило «новейшая» выбирает релиз 22.09, а из него —
полноразмерный Sol. Endpoint: прямой `openai` (standard tier; доступны также
`openai/flex` дешевле и `openai/fast` дороже, Amazon Bedrock). Параметры:
`temperature` НЕ поддерживается — применять штатный режим; `seed`,
`reasoning`, `max_tokens` поддерживаются.

**M2 Anthropic — `anthropic/claude-opus-5.5`.** Anthropic: «Latest. Released
September 22, 2026» (platform.claude.com; anthropic.com/claude-opus-5-5;
TechCrunch 22.09). Первый релиз семейства 5.5; Fable 5.1 (01.09) и Opus 5
(24.07) старше. Thinking у Opus 5.5 не отключается (официально задокументирован
breaking change) — reasoning-расход обязателен, учтён в смете. Endpoint:
прямой `anthropic` ($4/$20); `anthropic/fast` дороже, Bedrock/Azure/Vertex —
совместимые сторонние. `temperature` поддерживается, `seed` — нет.

**M3 Google — `google/gemini-3.8-flash`.** Google blog 02.09.2026 + Model Card
DeepMind + ai.google.dev: GA, «most intelligent Flash model», $0.75/$3.75
(вводная цена до 31.12.2026; стандартная $1.50/$7.50 с 01.01.2027). В каталоге
нет 3.8 Pro — Flash является основной универсальной моделью линии 3.8;
3.8 Flash Cyber — кибер-специализированная и в каталоге отсутствует.
Endpoint: `google-ai-studio` standard (`google-vertex/global` на момент снимка
имел status=-2 — деградация). Модальности text/image/video/file/audio→text.

**M4 Kimi — `moonshotai/kimi-k3`.** Moonshot AI, релиз 16.07.2026
(github.com/moonshotai/Kimi-K3, HuggingFace, NVIDIA modelcard). 2.8T MoE
open-weight, «most capable model to date». `kimi-k2.7-code` — coding-only,
исключён по правилу. Endpoint: прямой `moonshotai/mxfp4` ($3/$15,
квантование mxfp4) — предпочтён официальный; дешевле есть сторонние fp4
(Sail Research $1.4/$13, InferenceNet $1.5/$7.5), оставлены как документированная
альтернатива, но квантование fp4 ≠ официальному mxfp4.

**M5 GLM — `z-ai/glm-5.3-flashx`.** Z.ai, 18.09.2026 (Vercel AI Gateway
changelog; z.ai API; CNMO/Sina; orcarouter). ВАЖНО: FlashX — это
высокоскоростной serving-tier GLM-5.3-Flash (те же веса 320B-A18B, до
200 tok/s, цена ×2.5) — зафиксировано как ограничение «не новые веса»; это
новейшая доступная универсальная запись семейства. `glm-5.3` (18.08) —
текстовый флагман линии, но релиз раньше. Endpoint единственный:
`z-ai/fp8` ($0.37/$1.25, fp8).

**M6 DeepSeek — `deepseek/deepseek-v4.1-flash`.** DeepSeek, 10.09.2026
(api-docs.deepseek.com/news/news260910; deepseek.com/news; arXiv
2609.19969). «Наименьшая модель нового семейства архитектур» (CED, 552B
MoE, мультимодальная) — V4.1-Pro ещё не выпущен; V4-Flash и
V4-Flash-Vision-Exp сняты и роутятся в V4.1-Flash; трафик `deepseek-v4-pro`
с 14.09 также переведён на V4.1-Flash. Фактически текущая основная модель
API. Endpoint: прямой `deepseek` ($0.15/$0.60); 23 сторонних endpoint'а
задокументированы. Постоянное имя `deepseek-flash` у разработчика —
плавающий алиас; в сборе фиксируется `deepseek/deepseek-v4.1-flash` +
endpoint `deepseek`, версия за endpoint `…-20260910`.

**M7 Qwen — `qwen/qwen3.8-omni-flash`.** Alibaba Qwen, анонс 17–18.09.2026
(Model Studio docs обновлены 17.09; community blog 20.09; TechNode 18.09).
Омни-модальная: text/image/audio/video → text; текстовый диалог без медиа
поддерживается (Chat Completions). `qwen3.8-max-0902` (03.09) — флагманский
снапшот, но релиз раньше. Endpoint единственный: `alibaba` ($0.15/$0.47).
Caveat: модель ориентирована на аудио-видео агентные задачи; для нашего
текстового протокола пригодна, различие зафиксировано.

## Сводка рисков выборки

- Все 7 семейств покрыты, замен не потребовалось. `ALLOW_INCOMPLETE_FAMILIES=false`.
- «Постоянное» имя модели не гарантирует неизменность весов; зафиксированы
  версии за endpoint (`*-2026MMDD`) — проверять `model`/`provider` в ответах.
- GLM: FlashX = веса Flash (дубликат-риск с точки зрения «нового релиза»
  снят правилом «новейшая доступная»).
- Стоимость: смета `study/budget/estimate_draft.json` — low $6.98 /
  expected $16.38 / high $37.72 против бюджета $6. **План не вписывается в
  лимит** — решение за пользователем (лимит или явные параметры объёма);
  пилот (~$0.36–0.84) даст фактический расход reasoning для уточнения.
