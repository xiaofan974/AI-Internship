"""Explicitly apply sql/memory/0001_init.sql. Not used on import."""

from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv

from aeacus_agent.memory_schema import apply_memory_schema

THIS_DIR = Path(__file__).resolve().parent


def main() -> int:
    load_dotenv(THIS_DIR / ".env", override=False, interpolate=False)
    result = apply_memory_schema()
    print(json.dumps({k: result[k] for k in result if k != "dsn"}, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
