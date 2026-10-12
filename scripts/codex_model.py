#!/usr/bin/env python3
"""One source for the codex model slug passed as `codex exec -m`.

Precedence: env CODEX_MODEL (non-empty) > FLEET_TOPOLOGY.json `codex_model`
> DEFAULT_MODEL. Callers must not inherit ~/.codex/config.toml's default: it
can name a slug absent from models_cache.json (MODEL_ERR, seat dead).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

DEFAULT_MODEL = "gpt-5.6-sol"
TOPOLOGY = Path(__file__).resolve().parents[1] / "FLEET_TOPOLOGY.json"


def resolve_codex_model(topology: Path | None = None) -> str:
    env = os.environ.get("CODEX_MODEL", "").strip()
    if env:
        return env
    try:
        value = json.loads((topology or TOPOLOGY).read_text(encoding="utf-8")).get("codex_model")
    except (OSError, ValueError, AttributeError):
        value = None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return DEFAULT_MODEL


def main() -> int:
    sys.stdout.write(resolve_codex_model() + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
