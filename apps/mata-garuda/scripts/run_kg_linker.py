#!/usr/bin/env python3
"""Mata Garuda — KG Linker runner (Layer 3 Nexus).

Drains garuda:enriched through the KG linker to populate local SQLite KG
(entities + co-occurrence relations + temporal observations).

W4 cicatrix 2026-05-22: detect upstream entity-extraction failure
(every item processed has `entities=null/[]` → kg_linker skips all).
After KG_LINKER_DEAD_UPSTREAM_RUNS (default 5) consecutive runs that
processed >0 items but extracted 0 entities, log a STDERR warning so
the launchd error log surfaces the chronic upstream gap. Reset on any
run that extracts entities.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mata_garuda.runtime.kg_sqlite import KnowledgeGraph
from mata_garuda.heartbeat import run_with_heartbeat
from mata_garuda.workers.kg_linker import run_kg_linker


_STREAK_PATH = Path.home() / ".agent" / "decisions" / "kg-linker-dead-upstream-runs.json"
_STREAK_THRESHOLD = int(os.getenv("KG_LINKER_DEAD_UPSTREAM_RUNS", "5"))

logger = logging.getLogger("kg_linker_runner")


def _track_dead_upstream(total: dict[str, int]) -> None:
    """Increment counter when processed>0 but entities_total==0.

    Reset on a healthy run (entities_total>0) OR a fully-idle run
    (processed==0 → nothing to judge, but don't accumulate either).
    File read/write failures are non-fatal.
    """
    try:
        if total["processed"] > 0 and total["entities_total"] == 0:
            count = 0
            if _STREAK_PATH.exists():
                try:
                    count = int(json.loads(_STREAK_PATH.read_text()).get("count", 0))
                except (json.JSONDecodeError, ValueError, KeyError):
                    count = 0
            count += 1
            if count >= _STREAK_THRESHOLD:
                logger.warning(
                    "KG-linker dead-upstream alert: %d consecutive runs processed items "
                    "but extracted 0 entities (skipped_no_entities=%d/%d this run). "
                    "Upstream entity extractor missing or broken — investigate ner_worker pipeline.",
                    count, total["skipped_no_entities"], total["processed"],
                )
            _STREAK_PATH.parent.mkdir(parents=True, exist_ok=True)
            tmp = _STREAK_PATH.with_suffix(_STREAK_PATH.suffix + ".tmp")
            tmp.write_text(json.dumps({"count": count}))
            os.replace(tmp, _STREAK_PATH)
        elif total["entities_total"] > 0:
            if _STREAK_PATH.exists():
                _STREAK_PATH.unlink(missing_ok=True)
    except Exception as e:
        logger.debug("Dead-upstream tracker error (non-fatal): %s", e)


def main() -> int:
    # Configure logging to stderr so launchd's StandardErrorPath captures it.
    if not logger.handlers:
        h = logging.StreamHandler(sys.stderr)
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(h)
        logger.setLevel(logging.INFO)

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

    _track_dead_upstream(total)

    print(json.dumps({
        "run": total,
        "kg_total": stats,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run_with_heartbeat("mata_garuda.kg_linker.pro", main))
