#!/usr/bin/env python3
"""Fase 0 Day 7 driver — emit `05_format_matrix.json` (294 cells).

Initial fill uses stub heuristics (confidence=0.3); Consiglio v1 (Task 19-20)
overwrites cells where the 4-LLM consensus has higher confidence.
"""

from __future__ import annotations

import json
import logging
import sys
from collections import Counter
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "apps" / "backend-rag"))

from backend.services.research.format_matrix_builder import (  # noqa: E402
    FormatMatrixBuilder,
    CHANNELS,
    OBJECTIVES,
    REGISTERS,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sota.day7.format_matrix")

OUT = _REPO_ROOT / "research" / "sota-social-2026-v1" / "05_format_matrix.json"


def main() -> int:
    builder = FormatMatrixBuilder()
    cells = builder.build_empty_matrix()
    cells = builder.populate_from_playbook_stub(cells)

    format_dist = Counter(c["recommended_format"] for c in cells)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps({
            "sample_size": len(cells),
            "channels_count": len(CHANNELS),
            "objectives_count": len(OBJECTIVES),
            "registers_count": len(REGISTERS),
            "stub_format_distribution": dict(format_dist),
            "avg_confidence": round(
                sum(c["confidence"] or 0 for c in cells) / len(cells), 3
            ),
            "cells": cells,
        }, indent=2),
        encoding="utf-8",
    )

    logger.info(
        "wrote %s (%d cells = %d × %d × %d)",
        OUT,
        len(cells),
        len(CHANNELS),
        len(OBJECTIVES),
        len(REGISTERS),
    )
    logger.info("stub format distribution: %s", dict(format_dist))
    return 0


if __name__ == "__main__":
    sys.exit(main())
