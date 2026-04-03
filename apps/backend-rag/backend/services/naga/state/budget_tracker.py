"""BudgetTracker — resource consumption guard for Naga research sessions.

Tracks search API calls used and enforces a wall-clock TTL so the
LangGraph orchestrator can decide when to stop iterating.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class BudgetTracker:
    """Immutable-config, mutable-counter tracker for a single research run.

    Parameters
    ----------
    max_search_calls:
        Hard ceiling on search API invocations.
    ttl_seconds:
        Wall-clock time budget for the research session.
    """

    max_search_calls: int
    ttl_seconds: int

    # --- internal counters (not part of the public init signature) ----------
    _search_calls_used: int = field(default=0, init=False, repr=False)
    _start_time: float = field(default_factory=time.monotonic, init=False, repr=False)

    # --- properties ---------------------------------------------------------

    @property
    def search_calls_remaining(self) -> int:
        """Number of search calls still available (floors at 0)."""
        return max(0, self.max_search_calls - self._search_calls_used)

    @property
    def seconds_remaining(self) -> float:
        """Wall-clock seconds left before TTL expires."""
        elapsed = time.monotonic() - self._start_time
        return max(0.0, self.ttl_seconds - elapsed)

    @property
    def is_timed_out(self) -> bool:
        """True when TTL has been exceeded."""
        return self.seconds_remaining <= 0.0

    @property
    def can_search(self) -> bool:
        """True only when both call budget AND time budget remain."""
        return self.search_calls_remaining > 0 and not self.is_timed_out

    # --- mutations ----------------------------------------------------------

    def record_search(self, count: int = 1) -> None:
        """Record *count* search API calls consumed."""
        self._search_calls_used += count

    # --- reporting ----------------------------------------------------------

    def summary(self) -> dict:
        """Snapshot dict suitable for logging / LangGraph state."""
        return {
            "max_search_calls": self.max_search_calls,
            "search_calls_used": self._search_calls_used,
            "search_calls_remaining": self.search_calls_remaining,
            "ttl_seconds": self.ttl_seconds,
            "seconds_remaining": self.seconds_remaining,
            "is_timed_out": self.is_timed_out,
            "can_search": self.can_search,
        }
