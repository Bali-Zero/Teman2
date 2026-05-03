"""
Migration 087: Normalize legacy practice states to 5-state model.

Maps deprecated states to their canonical equivalents:
- quotation_sent, payment_pending, waiting_payment → sending_invoice
- in_progress, submitted_to_gov, approved → on_process

This is required before deploying the Practice State Machine (Blocco A).
"""

import logging

logger = logging.getLogger(__name__)

LEGACY_MAPPINGS = {
    "sending_invoice": ("quotation_sent", "payment_pending", "waiting_payment"),
    "on_process": ("in_progress", "submitted_to_gov", "approved"),
}


async def apply(conn) -> None:
    for target_state, legacy_states in LEGACY_MAPPINGS.items():
        placeholders = ", ".join(f"'{s}'" for s in legacy_states)
        result = await conn.execute(
            f"UPDATE practices SET status = '{target_state}' WHERE status IN ({placeholders})"
        )
        count = int(result.split()[-1]) if result else 0
        if count > 0:
            logger.info(
                f"Migration 087: Mapped {count} practices from {legacy_states} → '{target_state}'"
            )

    # Log final state distribution
    rows = await conn.fetch(
        "SELECT status, COUNT(*) as cnt FROM practices GROUP BY status ORDER BY cnt DESC"
    )
    dist = {r["status"]: r["cnt"] for r in rows}
    logger.info(f"Migration 087: Final state distribution: {dist}")


async def rollback(conn) -> None:
    logger.warning("Migration 087: No rollback possible — original states not preserved.")
