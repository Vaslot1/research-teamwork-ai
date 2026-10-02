"""Stage state updater: python study/tools/update_state.py"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

STUDY = Path(__file__).resolve().parents[1]
STATE = STUDY / "STATE.json"


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def set_stage(n, status, reason, outputs=None, resume=None):
    s = json.loads(STATE.read_text(encoding="utf-8"))
    s["stages"][n] = {**s["stages"].get(n, {}), "status": status,
                      "updated_utc": utcnow(), "reason": reason}
    if outputs:
        s["stages"][n]["outputs"] = outputs
    if resume:
        s["stages"][n]["resume"] = resume
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    print(f"stage {n} -> {status}")


if __name__ == "__main__":
    set_stage(sys.argv[1], sys.argv[2], sys.argv[3])
