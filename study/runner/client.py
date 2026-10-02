"""OpenRouter Chat Completions client.

- POST https://openrouter.ai/api/v1/chat/completions only (HTTPS).
- X-OpenRouter-Cache: false disables ready-response caching (OR7).
- Max MAX_ATTEMPTS transport attempts per turn; Retry-After honoured on 429;
  jittered backoff on 5xx/network/timeout; no endless retry on 400/401/402/403.
- `transport` is injectable for mock tests (signature below); no network needed.
"""
import json
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

API_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_ATTEMPTS = 3
CONNECT_TIMEOUT = 15
READ_TIMEOUT = 300

NO_RETRY_STATUSES = {400, 401, 402, 403, 404, 422}


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


@dataclass
class Attempt:
    n: int
    ts: str
    outcome: str            # ok|http_429|http_5xx|http_4xx|timeout|net_error
    http_status: int = None
    detail: str = ""
    retry_after_s: float = None


@dataclass
class ChatResult:
    ok: bool
    status: int = None
    body: dict = None
    text: str = None
    reasoning_text: str = None
    finish_reason: str = None
    generation_id: str = None
    model_returned: str = None
    provider_returned: str = None
    usage: dict = None
    cost_usd: str = None
    error: str = None
    outcome_unknown: bool = False     # timeout/etc: charge may exist upstream
    attempts: list = field(default_factory=list)


def _extract(resp_body):
    """Pull visible text + metadata out of a chat.completion body."""
    out = {"text": None, "reasoning_text": None, "finish_reason": None}
    try:
        ch = resp_body["choices"][0]
        msg = ch.get("message") or {}
        out["text"] = msg.get("content")
        # reasoning may appear in several fields depending on provider
        for k in ("reasoning", "reasoning_content", "reasoning_details"):
            v = msg.get(k)
            if v:
                out["reasoning_text"] = v if isinstance(v, str) else json.dumps(
                    v, ensure_ascii=False)
                break
        out["finish_reason"] = ch.get("finish_reason")
    except Exception:
        pass
    return out


class ORClient:
    def __init__(self, api_key, transport=None, sleep=time.sleep):
        self.api_key = api_key
        self.transport = transport or self._http
        self.sleep = sleep
        self.rng = random.Random()

    # ---- real transport ----------------------------------------------------
    def _http(self, payload):
        import requests
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-OpenRouter-Cache": "false",
        }
        r = requests.post(API_URL, headers=headers, json=payload,
                          timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        body = None
        try:
            body = r.json()
        except Exception:
            pass
        return r.status_code, body, dict(r.headers)

    # ---- retry loop ---------------------------------------------------------
    def chat(self, payload):
        attempts = []
        for n in range(1, MAX_ATTEMPTS + 1):
            ts = utcnow()
            try:
                status, body, headers = self.transport(payload)
            except Exception as e:  # requests Timeout / ConnectionError
                kind = ("timeout" if "timeout" in type(e).__name__.lower()
                        or "timeout" in str(e).lower() else "net_error")
                attempts.append(Attempt(n, ts, kind, detail=str(e)[:300]))
                if n < MAX_ATTEMPTS:
                    self.sleep(self._backoff(n))
                continue

            # HTTP 200 can still carry an upstream/content-filter error:
            # choices[0].error or finish_reason=='error' with null content.
            ch0 = None
            try:
                ch0 = (body or {}).get("choices", [{}])[0]
            except Exception:
                pass
            embedded_err = bool(ch0 and ch0.get("error"))
            err_finish = bool(ch0 and ch0.get("finish_reason") == "error")

            if status is not None and 200 <= status < 300 and body \
                    and not embedded_err and not err_finish:
                res = ChatResult(ok=True, status=status, body=body,
                                 attempts=attempts + [
                                     Attempt(n, ts, "ok", http_status=status)])
                ext = _extract(body)
                res.text = ext["text"]
                res.reasoning_text = ext["reasoning_text"]
                res.finish_reason = ext["finish_reason"]
                res.generation_id = body.get("id")
                res.model_returned = body.get("model")
                res.provider_returned = body.get("provider") or (
                    body.get("provider_name"))
                res.usage = body.get("usage")
                cost = (body.get("usage") or {}).get("cost")
                if cost is None:
                    cost = body.get("cost")
                res.cost_usd = None if cost is None else str(cost)
                return res

            # embedded provider error in a 200 body -> treat as 5xx (retryable,
            # sampling-dependent), not as a successful response
            if embedded_err or err_finish:
                emsg = ""
                try:
                    emsg = (ch0.get("error") or {}).get("message", "")
                except Exception:
                    pass
                attempts.append(Attempt(
                    n, ts, "provider_error", http_status=status,
                    detail=emsg[:300] or "finish_reason=error"))
                if n < MAX_ATTEMPTS:
                    self.sleep(self._backoff(n))
                continue

            outcome = ("http_429" if status == 429 else
                       "http_5xx" if status and status >= 500 else
                       "http_4xx")
            ra = None
            if status == 429:
                try:
                    ra = float((headers or {}).get("Retry-After", ""))
                except Exception:
                    ra = None
            attempts.append(Attempt(n, ts, outcome, http_status=status,
                                    detail=json.dumps(body, ensure_ascii=False,
                                                      default=str)[:300],
                                    retry_after_s=ra))
            if status in NO_RETRY_STATUSES:
                break
            if n < MAX_ATTEMPTS:
                self.sleep(ra if ra else self._backoff(n))

        last = attempts[-1]
        unknown = last.outcome in ("timeout", "net_error", "http_5xx")
        return ChatResult(
            ok=False, status=last.http_status,
            error=f"{last.outcome}: {last.detail[:200]}",
            outcome_unknown=unknown, attempts=attempts)

    def _backoff(self, n):
        return min(8.0, (2 ** (n - 1)) + self.rng.uniform(0, 0.5))
