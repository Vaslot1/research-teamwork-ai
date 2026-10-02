"""Environment / secrets handling and paid-run gates.

Rules enforced here:
- OPENROUTER_API_KEY value is loaded but NEVER printed or persisted.
- Paid calls require ALLOW_PAID_RUN=true AND user-set positive MAX_BUDGET_USD.
- We never assign a budget ourselves.
"""
import os
from decimal import Decimal
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[2]      # openrouter_experiment_agent/
WS_ROOT = PKG_ROOT.parent                            # hse-online-team/
STUDY = PKG_ROOT / "study"

_ENV_CANDIDATES = [WS_ROOT / ".env", PKG_ROOT / ".env", STUDY / ".env"]


def load_dotenv():
    """Load KEY=VALUE pairs from the first existing .env (no override of real env)."""
    for p in _ENV_CANDIDATES:
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                os.environ.setdefault(k, v)
            return str(p)
    return None


def get_key():
    """Return the API key or None. Never logs/prints the value."""
    load_dotenv()
    k = os.environ.get("OPENROUTER_API_KEY", "").strip()
    return k or None


def env_status():
    """Flag-only status — safe to print."""
    load_dotenv()
    return {
        "OPENROUTER_API_KEY": "set" if get_key() else "missing",
        "ALLOW_PAID_RUN": os.environ.get("ALLOW_PAID_RUN", ""),
        "MAX_BUDGET_USD": os.environ.get("MAX_BUDGET_USD", ""),
        "REPETITIONS": os.environ.get("REPETITIONS", ""),
        "MAX_CONCURRENCY": os.environ.get("MAX_CONCURRENCY", ""),
        "ALLOW_INCOMPLETE_FAMILIES": os.environ.get("ALLOW_INCOMPLETE_FAMILIES", ""),
    }


def paid_gate():
    """(ok, reason). Paid calls allowed only if ALL conditions hold."""
    st = env_status()
    if st["OPENROUTER_API_KEY"] != "set":
        return False, "OPENROUTER_API_KEY missing"
    if st["ALLOW_PAID_RUN"].strip().lower() != "true":
        return False, f"ALLOW_PAID_RUN!=true (got {st['ALLOW_PAID_RUN']!r})"
    try:
        cap = Decimal(st["MAX_BUDGET_USD"])
    except Exception:
        return False, f"MAX_BUDGET_USD not a number: {st['MAX_BUDGET_USD']!r}"
    if cap <= 0:
        return False, f"MAX_BUDGET_USD must be positive (got {cap})"
    return True, "ok"


def max_budget():
    load_dotenv()
    try:
        return Decimal(os.environ.get("MAX_BUDGET_USD", "0"))
    except Exception:
        return Decimal("0")


def max_concurrency():
    load_dotenv()
    try:
        return max(1, min(2, int(os.environ.get("MAX_CONCURRENCY", "2"))))
    except Exception:
        return 2
