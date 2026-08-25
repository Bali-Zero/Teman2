"""Token-plan depletion probe — F8/directive#1§1's "alarms at 30% and 10%".

**Load-bearing architectural fact, verified twice, not assumed**: TP1 exposes
NO live credits/balance/usage API. `research/operations/2026-08-14-probe1-tp1-burn-rate.md`
Part 2 tried 20 plausible paths (`/usage`, `/credits`, `/quota`, `/billing`,
`/account/usage`, `/dashboard/usage`, `/balance`, `/tokens/usage`,
`/aigc/usage`, across two base URLs) — 20/20 HTTP 404. This session's own
live probe (2026-08-25) confirms the response headers carry no
`x-ratelimit-*` family either (only Envoy/gRPC transport headers). So
**there is nothing to poll**: this probe cannot ask TP1 "how much is left".

What it does instead: track every call THIS client makes (`usage.total_tokens`
from each response) in a local rolling-window store, and compare that local
sum against an OWNER-CONFIGURED quota budget. There is no safe default for
that budget — the TP1 door is a SHARED pool across the whole fleet (DeepSeek
refuter calls, the Qwen strategy panel, GLM refuter hops, ... all draw from
the same account), so "how many of the pool's tokens are team-bot's to
spend" is a business allocation decision, not a technical fact this module
can derive. Baking in a guessed number would silently misrepresent someone
else's headroom as team-bot's. `TEAM_BOT_TP1_QUOTA_TOKENS_7D` is therefore
**unset by default** — the probe stays in `unconfigured` state (logs once,
`remaining_fraction()` returns `None`, no alarms ever fire) until an owner
sets it explicitly.

**A concrete anchor for that decision**, derived from the one real
measurement available (`2026-08-14-probe1-tp1-burn-rate.md` Part 4 console
read), shown here as arithmetic, not asserted as a default:
`217,060,000 tokens == 56.31% of the 7-day rolling quota` for the WHOLE
account across ALL models that day, so the full-account 7-day pool was
approximately `217_060_000 / 0.5631 ≈ 385,564,900` tokens. Team-bot's own
budget is some fraction of that the owner assigns, not this figure itself.

Author: Claude (lane B4-tp1 — team-bot TP1 brain adapter).
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from time import time

__all__ = [
    "DEFAULT_ALARM_THRESHOLDS",
    "DEFAULT_WINDOW_SECONDS",
    "DepletionAlarm",
    "DepletionProbe",
    "UsageSample",
]

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_SECONDS = 7 * 86400.0  # TP1's own quota window (console-confirmed, Part 4)
# Remaining-HEADROOM thresholds, checked high-to-low (30% remaining fires
# before 10% remaining). "depletion alarms at 30% and 10%" (directive#1§1) —
# read as headroom crossing DOWN through these fractions, mirroring a
# low-battery warning, not "30% used".
DEFAULT_ALARM_THRESHOLDS: tuple[float, ...] = (0.30, 0.10)


@dataclass(frozen=True, slots=True)
class UsageSample:
    """One call's token cost, taken verbatim from the OpenAI-compatible
    `usage` object TP1 returns on every 2xx response (see tp1_client.py).
    Never carries prompt/completion CONTENT — token counts only, so this
    struct is safe to persist and log in full (no PII boundary concern)."""

    ts: float
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True, slots=True)
class DepletionAlarm:
    threshold: float  # the headroom fraction just crossed, e.g. 0.30
    remaining_fraction: float  # the actual measured remaining fraction at fire time
    used_tokens: int
    quota_tokens: int
    window_seconds: float


class DepletionProbe:
    """Sqlite-backed rolling-window token accounting + edge-triggered
    alarms. `db_path=":memory:"` for tests; a real path (team-bot's shared
    sqlite state store, per directive §3) in production so alarm state
    survives a process restart — re-alarming on every boot would be exactly
    the "cron theater" false-comfort/false-alarm pattern this repo's own
    cicatrix family #2 warns about.
    """

    def __init__(
        self,
        db_path: str = ":memory:",
        quota_tokens_7d: int | None = None,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
        alarm_thresholds: tuple[float, ...] = DEFAULT_ALARM_THRESHOLDS,
        clock: Callable[[], float] = time,
    ) -> None:
        if quota_tokens_7d is not None and quota_tokens_7d <= 0:
            raise ValueError("quota_tokens_7d must be > 0 when set")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
        if any(not (0.0 < t < 1.0) for t in alarm_thresholds):
            raise ValueError("alarm_thresholds must each be in (0, 1)")
        # Fire highest-headroom threshold first (descending) so alarms
        # escalate 30% -> 10%, never fire out of order.
        self._thresholds = tuple(sorted(set(alarm_thresholds), reverse=True))
        self._quota = quota_tokens_7d
        self._window_seconds = window_seconds
        self._clock = clock
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS usage_samples ("
            " ts REAL NOT NULL, model TEXT NOT NULL,"
            " prompt_tokens INTEGER NOT NULL, completion_tokens INTEGER NOT NULL,"
            " total_tokens INTEGER NOT NULL)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS alarm_state (id INTEGER PRIMARY KEY CHECK (id = 0),"
            " last_threshold_fired REAL)"
        )
        self._conn.execute(
            "INSERT OR IGNORE INTO alarm_state (id, last_threshold_fired) VALUES (0, NULL)"
        )
        self._conn.commit()
        if self._quota is None:
            logger.warning(
                "DepletionProbe unconfigured: TEAM_BOT_TP1_QUOTA_TOKENS_7D not set — "
                "local usage is still recorded, but remaining_fraction()/check_alarms() "
                "are permanently inert until an owner sets a quota budget."
            )

    @property
    def configured(self) -> bool:
        return self._quota is not None

    def record(self, sample: UsageSample) -> None:
        self._conn.execute(
            "INSERT INTO usage_samples (ts, model, prompt_tokens, completion_tokens, total_tokens)"
            " VALUES (?, ?, ?, ?, ?)",
            (sample.ts, sample.model, sample.prompt_tokens, sample.completion_tokens, sample.total_tokens),
        )
        self._conn.commit()
        self._prune(now=self._clock())

    def _prune(self, now: float) -> None:
        cutoff = now - self._window_seconds
        self._conn.execute("DELETE FROM usage_samples WHERE ts < ?", (cutoff,))
        self._conn.commit()

    def used_tokens(self, now: float | None = None) -> int:
        now = now if now is not None else self._clock()
        cutoff = now - self._window_seconds
        row = self._conn.execute(
            "SELECT COALESCE(SUM(total_tokens), 0) FROM usage_samples WHERE ts >= ?",
            (cutoff,),
        ).fetchone()
        return int(row[0])

    def remaining_fraction(self, now: float | None = None) -> float | None:
        """`None` iff unconfigured (no quota set) — never a fabricated
        number. Clamped to `[0.0, 1.0]`: usage can exceed a manually-set
        quota (the owner under-estimated, or the shared pool moved), and a
        negative fraction would be a confusing/wrong signal to callers that
        only care "how close to empty".
        """
        if self._quota is None:
            return None
        used = self.used_tokens(now=now)
        remaining = (self._quota - used) / self._quota
        return max(0.0, min(1.0, remaining))

    def check_alarms(self, now: float | None = None) -> list[DepletionAlarm]:
        """Edge-triggered: returns only NEWLY crossed thresholds since the
        last check (persisted in `alarm_state`, so a process restart does
        not re-fire an already-acknowledged alarm). Returns `[]` when
        unconfigured — never alarms on a fabricated budget."""
        if self._quota is None:
            return []
        now = now if now is not None else self._clock()
        remaining = self.remaining_fraction(now=now)
        assert remaining is not None  # quota is set in this branch

        row = self._conn.execute(
            "SELECT last_threshold_fired FROM alarm_state WHERE id = 0"
        ).fetchone()
        last_fired = row[0]

        fired: list[DepletionAlarm] = []
        for threshold in self._thresholds:  # descending: 0.30 before 0.10
            already_fired_this_or_lower = last_fired is not None and last_fired <= threshold
            if remaining <= threshold and not already_fired_this_or_lower:
                fired.append(
                    DepletionAlarm(
                        threshold=threshold,
                        remaining_fraction=remaining,
                        used_tokens=self.used_tokens(now=now),
                        quota_tokens=self._quota,
                        window_seconds=self._window_seconds,
                    )
                )
                last_fired = threshold

        if remaining > (self._thresholds[0] if self._thresholds else 1.0):
            # Headroom recovered above the highest alarm tier (rolling
            # window aged old usage out) — rearm for the next depletion
            # cycle rather than staying permanently "already alarmed".
            last_fired = None

        self._conn.execute(
            "UPDATE alarm_state SET last_threshold_fired = ? WHERE id = 0", (last_fired,)
        )
        self._conn.commit()
        return fired

    def close(self) -> None:
        self._conn.close()
