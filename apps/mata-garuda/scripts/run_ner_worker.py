#!/usr/bin/env python3
"""Mata Garuda — NER Worker runner (Layer 2.5 Pre-KG).

Reads garuda:enriched without entities, runs qwen3.5:9b NER extraction
via Ollama, republishes items with entities JSON populated. This is
the upstream prerequisite for run_kg_linker.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mata_garuda.workers.ner_worker import run_ner


def main() -> int:
    total = {"processed": 0, "extracted": 0, "empty": 0}

    # Drain in batches of 20 (NER is heavier than normalize); cap 200/run
    for _ in range(10):
        r = run_ner(max_items=20)
        if r.get("processed", 0) == 0:
            break
        for k in total:
            total[k] += r.get(k, 0)

    print(json.dumps({"run": total}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
