"""
AlertFeedback.retrain — weekly threshold autotune (decision #2).

For each category with outcomes in the window:
  if precision < LOW_PRECISION   and n >= MIN_SAMPLES_UP   → threshold += 1
  elif precision > HIGH_PRECISION and n >= MIN_SAMPLES_DOWN → threshold -= 1
  else                                                      → no change
threshold clamped to [THRESHOLD_MIN, THRESHOLD_MAX]

Gated by system_settings.compliance_alert_autotune_enabled == 'true'.
Audit log to guardian_decisions (m098b) when changes are applied;
gracefully skipped if the table does not exist (local dev).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import asyncpg

from backend.services.compliance.alert_metrics import compute_metrics_all

logger = logging.getLogger(__name__)


# ── Decision constants ────────────────────────────────────────────────────
LOW_PRECISION: float = 0.6
HIGH_PRECISION: float = 0.9
MIN_SAMPLES_UP: int = 20
MIN_SAMPLES_DOWN: int = 50
THRESHOLD_MIN: int = 1
THRESHOLD_MAX: int = 30

_WINDOW_KEY = "compliance_alert_autotune_window_days"
_ENABLED_KEY = "compliance_alert_autotune_enabled"


@dataclass
class ThresholdChange:
    category: str
    old: int
    new: int
    precision: float
    sample_size: int


class AlertFeedback:
    """Threshold autotune feedback loop driven by alert outcome data.

    Can be constructed with either a connection pool (production) or a
    pre-acquired connection (test fixture / transaction scope).

    Args:
        db_pool: asyncpg.Pool for production use.
        connection: Pre-acquired asyncpg.Connection for test / tx scope.
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool | None = None,
        *,
        connection: asyncpg.Connection | None = None,
    ) -> None:
        self._pool = db_pool
        self._conn = connection

    # ── Internal helpers ────────────────────────────────────────────────

    async def _exec(self, fn: str, query: str, *args: Any) -> Any:
        """Execute a single asyncpg call on the connection or pool."""
        if self._conn is not None:
            return await getattr(self._conn, fn)(query, *args)
        async with self._pool.acquire() as c:  # type: ignore[union-attr]
            return await getattr(c, fn)(query, *args)

    async def _get_conn(self) -> asyncpg.Connection:
        """Return the bound connection (tests) or raise — callers manage pool scope."""
        if self._conn is not None:
            return self._conn
        raise RuntimeError("Call within pool.acquire() context when using pool mode")

    # ── Public API ──────────────────────────────────────────────────────

    async def retrain(self, *, category: str | None = None) -> dict[str, Any]:
        """Run one autotune cycle.

        Args:
            category: If given, only retrain this category; else all.

        Returns:
            Dict with keys:
              changed: list of {category, old, new, precision, sample_size}
              reason:  "applied" | "no_change" | "autotune_disabled"
        """
        enabled = await self._exec(
            "fetchval",
            "SELECT value FROM system_settings WHERE key = $1",
            _ENABLED_KEY,
        )
        if (enabled or "").lower() != "true":
            logger.info("autotune disabled; skipping retrain")
            return {"changed": [], "reason": "autotune_disabled"}

        window_val = await self._exec(
            "fetchval",
            "SELECT value FROM system_settings WHERE key = $1",
            _WINDOW_KEY,
        )
        window_days: int = int(window_val) if window_val else 90

        # compute_metrics_all / compute_metrics need a Connection object
        if self._conn is not None:
            metrics_map = await compute_metrics_all(self._conn, window_days=window_days)
        else:
            async with self._pool.acquire() as c:  # type: ignore[union-attr]
                metrics_map = await compute_metrics_all(c, window_days=window_days)

        # Filter to requested category when specified
        if category is not None:
            metrics_map = {k: v for k, v in metrics_map.items() if k == category}

        changes: list[ThresholdChange] = []
        for cat, m in metrics_map.items():
            denom = m.acted + m.dismissed
            if denom == 0:
                continue

            current = m.threshold_current
            if current is None:
                continue  # no threshold row exists → skip

            p = m.precision
            new_threshold = current

            if p < LOW_PRECISION and denom >= MIN_SAMPLES_UP:
                new_threshold = min(THRESHOLD_MAX, current + 1)
            elif p > HIGH_PRECISION and denom >= MIN_SAMPLES_DOWN:
                new_threshold = max(THRESHOLD_MIN, current - 1)

            if new_threshold != current:
                await self._apply_change(cat, current, new_threshold, p, denom)
                changes.append(
                    ThresholdChange(
                        category=cat,
                        old=current,
                        new=new_threshold,
                        precision=p,
                        sample_size=denom,
                    )
                )

        return {
            "changed": [
                {
                    "category": c.category,
                    "old": c.old,
                    "new": c.new,
                    "precision": c.precision,
                    "sample_size": c.sample_size,
                }
                for c in changes
            ],
            "reason": "applied" if changes else "no_change",
        }

    async def _apply_change(
        self,
        category: str,
        old: int,
        new: int,
        precision: float,
        sample_size: int,
    ) -> None:
        """Persist threshold update and write audit row."""
        key = f"compliance_alert_threshold_urgent_{category}"
        result = await self._exec(
            "execute",
            "UPDATE system_settings SET value = $1, updated_at = NOW() WHERE key = $2",
            str(new),
            key,
        )
        if result == "UPDATE 0":
            logger.warning(
                "system_settings key %r not found — threshold not saved (seeding missed?)",
                key,
            )

        # guardian_decisions audit (table may not exist in local dev).
        # Use a savepoint so that a missing-table error doesn't abort the outer
        # transaction (asyncpg marks txn aborted on any PostgresError).
        conn = self._conn
        if conn is None:
            # pool mode — we're already inside a pool.acquire() block above;
            # re-acquire for the audit insert so it's isolated
            try:
                async with self._pool.acquire() as audit_conn:  # type: ignore[union-attr]
                    await audit_conn.execute(
                        """
                        INSERT INTO guardian_decisions (decision_type, context, decision, metadata)
                        VALUES ('compliance_threshold_autotune',
                                'category=' || $1,
                                'threshold ' || $2 || '->' || $3,
                                $4::jsonb)
                        """,
                        category,
                        str(old),
                        str(new),
                        f'{{"precision":{precision},"sample_size":{sample_size}}}',
                    )
            except asyncpg.PostgresError as exc:  # noqa: BLE001 — table missing is non-fatal
                logger.warning("guardian_decisions insert failed (non-fatal): %s", exc)
        else:
            # connection / tx mode (tests) — use a savepoint to protect the outer tx
            try:
                async with conn.transaction():  # savepoint — isolation inherited from outer TX
                    await conn.execute(
                        """
                        INSERT INTO guardian_decisions (decision_type, context, decision, metadata)
                        VALUES ('compliance_threshold_autotune',
                                'category=' || $1,
                                'threshold ' || $2 || '->' || $3,
                                $4::jsonb)
                        """,
                        category,
                        str(old),
                        str(new),
                        f'{{"precision":{precision},"sample_size":{sample_size}}}',
                    )
            except asyncpg.PostgresError as exc:  # noqa: BLE001 — table missing is non-fatal
                logger.warning("guardian_decisions insert failed (non-fatal): %s", exc)


__all__ = ["AlertFeedback", "ThresholdChange"]
