"""Event bridge for crm-cell — durable run trace via mig 153 outbox.

Sprint 3 W2 deliverable. Reference:
  docs/sprint3/crm-cell-design.md
  docs/sprint3/review-synthesis-2026-05-04.md (I5 — stubs landed 2026-05-04)

Wraps the trigger-emitted ``crm_welcome_completed`` event (mig 153) so
the cell adapter records both the audit row in ``crm_welcome_runs`` AND
a cell-level pulse via the cell-core observatory. The trigger does the
heavy lifting (events_outbox + pg_notify with mig 146 pattern); this
bridge is the call site that issues the INSERT INTO crm_welcome_runs.

W2 status: STUB. The methods accept the canonical inputs and log the
INSERT statement that would run. Wiring into welcome_practice_service
lands in Sprint 4.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger("crm_cell.event_bridge")


@dataclass(frozen=True)
class WelcomeRunResult:
    """Outcome of one welcome flow attempt."""

    client_id: int
    practice_id: int | None
    drive_folder_id: str | None
    channels_sent: list[str]    # subset of ['email', 'whatsapp', 'telegram']
    success: bool
    started_at: datetime
    completed_at: datetime | None = None
    metadata: dict | None = None


class CrmEventBridge:
    """Pro-side event bridge for the CRM cell.

    Sprint 3 W2 stub. The eventual Sprint 4 implementation will call
    into asyncpg with the ON CONFLICT DO UPDATE UPSERT pattern that
    works correctly with the mig 153 trigger's WHEN clause
    (false→true transition fires once per success).
    """

    def __init__(self, *, db_pool=None) -> None:
        # asyncpg pool is optional in Sprint 3 W2; Sprint 4 requires it.
        self._db_pool = db_pool

    async def record_welcome_run(self, result: WelcomeRunResult) -> int | None:
        """UPSERT a welcome run audit row.

        Returns the row id (or None if pool unavailable in stub mode).
        The mig 153 trigger fires automatically on the false→true
        success transition (or fresh INSERT(success=true)).
        """
        if result.completed_at is None:
            result = WelcomeRunResult(
                client_id=result.client_id,
                practice_id=result.practice_id,
                drive_folder_id=result.drive_folder_id,
                channels_sent=list(result.channels_sent),
                success=result.success,
                started_at=result.started_at,
                completed_at=datetime.now(tz=timezone.utc),
                metadata=result.metadata,
            )
        logger.info(
            "[STUB] crm_welcome_runs UPSERT: client_id=%s practice_id=%s "
            "success=%s channels=%s",
            result.client_id, result.practice_id, result.success,
            result.channels_sent,
        )
        # Sprint 4: ON CONFLICT (client_id, practice_id) DO UPDATE SET
        # success=EXCLUDED.success, channels_sent=EXCLUDED.channels_sent,
        # completed_at=NOW(), metadata=EXCLUDED.metadata
        # The mig 153 trigger WHEN clause filters spurious re-emits.
        return None
