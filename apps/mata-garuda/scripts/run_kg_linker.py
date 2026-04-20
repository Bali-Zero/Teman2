#!/usr/bin/env python3
"""Mata Garuda — KG Linker runner (Layer 3 Nexus).

Drains garuda:enriched through the KG linker to populate local SQLite KG
(entities + co-occurrence relations + temporal observations).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mata_garuda.runtime.kg_sqlite import KnowledgeGraph
from mata_garuda.workers.kg_linker import run_kg_linker


def main() -> int:
    kg = KnowledgeGraph()
    # Drain in batches of 100; stop when empty
    total: dict[str, int] = {
        "processed": 0, "linked": 0, "skipped_no_entities": 0,
        "entities_total": 0, "relations_total": 0,
    }
    for _ in range(20):  # cap 2000 items/run
        r = run_kg_linker(max_items=100, kg=kg)
        if r["processed"] == 0:
            break
        for k in total:
            total[k] += r.get(k, 0)

    stats = kg.stats()
    kg.close()

    print(json.dumps({
        "run": total,
        "kg_total": stats,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
