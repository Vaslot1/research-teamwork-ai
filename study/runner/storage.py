"""Durable storage: append-only JSONL (immutable raw records) and atomic JSON."""
import json
import os
import threading
from pathlib import Path

from .env import STUDY

_locks = {}
_locks_guard = threading.Lock()


def _lock_for(path):
    with _locks_guard:
        return _locks.setdefault(str(path), threading.Lock())


def append_jsonl(path, obj):
    """Append one JSON line, flush+fsync. Raw records are append-only."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, ensure_ascii=False, default=str)
    with _lock_for(path):
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                out.append(json.loads(ln))
    return out


def atomic_write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str),
                   encoding="utf-8")
    os.replace(tmp, path)


def read_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def data_dir(split):
    """split: 'pilot' | 'main' | 'mock'."""
    d = STUDY / "data" / split
    d.mkdir(parents=True, exist_ok=True)
    return d


class Progress:
    """Durable per-trial status, atomically rewritten."""

    def __init__(self, split):
        self.path = data_dir(split) / "progress.json"
        self.state = read_json(self.path, {"trials": {}})

    def get(self, trial_id):
        return self.state["trials"].get(trial_id, {"status": "pending"})

    def set(self, trial_id, **fields):
        rec = self.state["trials"].setdefault(trial_id, {})
        rec.update(fields)
        self.save()

    def save(self):
        atomic_write_json(self.path, self.state)

    def done_turn(self, trial_id, turn):
        rec = self.get(trial_id)
        return rec.get(f"turn{turn}_status") == "ok"

    def counts(self):
        c = {}
        for t in self.state["trials"].values():
            c[t.get("status", "?")] = c.get(t.get("status", "?"), 0) + 1
        return c
