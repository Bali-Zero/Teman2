"""intel-scraper-cell — light cell wrapping for the bali-intel-scraper.

Sprint 1 W1 deliverable. Reference:
  docs/audits/2026-05-02-cell-openclaw-brainstorm/99b_synthesis_v2.md
  § "Sprint 1 — Intel Scraper light + HGT quarantine (1 settimana)"

The intel scraper is wrapped — NOT rewritten. This package adds 3 lateral
concerns around the existing scraping logic:

* :mod:`scar_recorder` — recurring failure patterns (rate limit, paywall,
  schema drift) land in ``packages/cell-core`` Genome as scars so future
  runs can back off / quarantine the offending source.
* :mod:`hgt_publisher` — high-confidence STRUCTURAL discoveries (e.g.
  "regulator X publishes a stable RSS feed at /api/v2/news") are broadcast
  to sibling cells via the cell-core HGT stream. Article CONTENT stays
  scoped to UU PDP (never published).
* :mod:`event_bridge` — every run emits one durable
  ``intel.scraper.run`` row via :class:`ObservedShellBus`, with JSONL
  fallback when the DB pool is unavailable.

The :class:`IntelScraperCellRunner` ties the three together so a scraper
adapter only needs to call ``runner.start_run()`` /
``runner.record_failure()`` / ``runner.record_pattern()`` /
``runner.finish_run()`` — implementation in :mod:`runner`.
"""
from __future__ import annotations

from .event_bridge import IntelScraperEventBridge
from .hgt_publisher import IntelScraperHGTBridge, StructuralPattern
from .runner import IntelScraperCellRunner, RunSummary
from .scar_recorder import FailureKind, IntelScraperScarRecorder

CELL_NAME = "intel-scraper-cell"
CELL_VERSION = "0.1.0"

__all__ = [
    "CELL_NAME",
    "CELL_VERSION",
    "IntelScraperEventBridge",
    "IntelScraperHGTBridge",
    "StructuralPattern",
    "IntelScraperCellRunner",
    "RunSummary",
    "FailureKind",
    "IntelScraperScarRecorder",
]
