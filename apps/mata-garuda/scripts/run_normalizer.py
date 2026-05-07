#!/usr/bin/env python3
"""Mata Garuda — Normalizer runner (Layer 2 Kognitif).

Drains garuda:raw through the normalizer worker to populate
garuda:enriched with deduplicated, schema-normalized items.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mata_garuda.runtime.knowledge import KnowledgeBase
from mata_garuda.workers.normalizer import run_normalizer


def main() -> int:
    kb = KnowledgeBase()
    total = {"processed": 0, "duplicates": 0, "published": 0, "errors": 0}

    # Drain in batches of 50; cap 1000 items/run
    for _ in range(20):
        r = run_normalizer(kb, max_items=50)
        if r.get("processed", 0) == 0:
            break
        for k in total:
            total[k] += r.get(k, 0)

    kb.close()
    print(json.dumps({"run": total}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
