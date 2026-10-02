"""Entry point: python study/run.py <command> [split]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runner.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
