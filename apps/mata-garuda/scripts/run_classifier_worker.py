#!/usr/bin/env python3
"""Mata Garuda — Classifier Worker runner (Layer 2 enrichment).

Reads garuda:enriched without classification, runs qwen3:8b classifier via
Ollama (with keyword fallback when Ollama fails), republishes items with
{domain, priority, keywords, relevance_score} fields populated. This is
parallel to NER worker (W6 cicatrix 2026-05-22) — both consume the same
stream via distinct consumer groups (`classifier` and `ner`).

W9 cicatrix 2026-05-22: classifier consumer group on garuda:enriched had
been stuck for 32 days (consumer `classifier-1` idle=2760607955ms),
lag=1570 + pending=0 — the library existed but no runner script and no
LaunchAgent ever invoked it. Mirror of NER recovery (W6+W7).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mata_garuda.workers.classifier_worker import run_classifier


def main() -> int:
    total = {"processed": 0, "classified_llm": 0, "classified_fallback": 0}

    # Drain in batches of 20 (classifier is lighter than NER — qwen3:8b ~3-8s);
    # cap 400/run (10 batches of 40 each? Actually use 20 batch x cap 10 = 200).
    for _ in range(10):
        r = run_classifier(max_items=20)
        if r.get("processed", 0) == 0:
            break
        for k in total:
            total[k] += r.get(k, 0)

    print(json.dumps({"run": total}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
