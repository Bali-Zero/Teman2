"""Trend-Hunter — Intel sensory layer for War Room 2.0.

Cron cadence: 2h on Pro (fallback Air degraded mode). Sources:
- xAI Grok search (OSINT, Pro-only, Law 2)
- RSS compliance/visa/KBLI feeds (feedparser, no auth)
- Bali Post / Antara (Playwright MCP scraping, deferred)
- Reddit r/bali r/indonesia (PRAW OAuth, deferred)
- Google Trends (pytrends, deferred)

Output: trend_signals rows + pg_notify('intel_event', ...) per signal.
Reference: docs/war-room-2.0-design.md §6, §15.5.
"""

from backend.services.intel.trend_hunter.orchestrator import TrendHunterOrchestrator
from backend.services.intel.trend_hunter.types import (
    NormalizedSignal,
    SourceAdapterResult,
)

__all__ = [
    "NormalizedSignal",
    "SourceAdapterResult",
    "TrendHunterOrchestrator",
]
