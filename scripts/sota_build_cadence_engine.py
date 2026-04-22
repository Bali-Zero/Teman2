#!/usr/bin/env python3
"""Fase 0 Day 7 driver — emit 06_cadence_engine.json (14 × 3 × 24)."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "apps" / "backend-rag"))

from backend.services.research.cadence_engine import build_cadence_matrix  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sota.day7.cadence")

OUT = _REPO_ROOT / "research" / "sota-social-2026-v1" / "06_cadence_engine.json"


def main() -> int:
    data = build_cadence_matrix()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.info(
        "wrote %s (%d channels × %d timezones × 24 hours)",
        OUT,
        len(data["channels"]),
        len(data["timezones"]),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
