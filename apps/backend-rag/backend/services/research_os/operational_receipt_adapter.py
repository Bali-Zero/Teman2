"""Adapt one Magazine `ops_receipts` row (+ its parent `ops_intents` row) into
a canonical `OperationalReceipt` (CONTRACTS.md §13.5).

BLOCKED as of 2026-08-24 (team-lead ruling, verified directly against
`operational_receipt.py`): every `ops_receipts` row can only produce
`receipt_type="execution.result"` -- there is no other v1 OperationalReceipt
receipt_type this legacy source can express (queue-only/team/routing
receipts have no `ops_receipts` analogue at all -- matrix §1.5).
`execution.result` REQUIRES a real `execution_attempt_ref`
(`operational_receipt.py:170-175`), and
`EXECUTION_ATTEMPT_CAPABLE_RECEIPT_TYPES` (`operational_receipt.py:101-103`)
has EXACTLY ONE member -- `execution.result` itself -- so no other
receipt_type may carry this ref either, even optionally
(`operational_receipt.py:181-188`).

An earlier version of this adapter synthesized `execution_attempt_ref` via
`synthetic_uuid`+`unbacked_object_hash` (the same SYNTHESIZED_UNBACKED
pattern this package uses for purely descriptive/provenance refs elsewhere)
and shipped it. That version was WRONG, not merely disclosed-risky:
`close_execution_attempt()` (`operational_receipt.py:224-249`) compares the
ref's `execution_attempt_id`/`object_hash` against a REAL `ExecutionAttempt`
object -- a synthetic ref can never match a real object that was never
constructed, so every receipt this adapter produced would be PERMANENTLY
unclosable. Worse, this specific shape is exactly what
`EXECUTION_ATTEMPT_CAPABLE_RECEIPT_TYPES` exists to stop:
`operational_receipt.py`'s own 2026-08-23 revision comment (lines 84-100)
records that a Kimi K3 adversarial review broke the PRIOR blocklist-shaped
guard this same way (a synthetic `execution_attempt_ref` sailed through on
an unregistered `queue.closed` receipt_type). Shipping a synthesized ref on
the one type that IS registered walks the same cargo in the front door
instead of a side one.

The two honest paths from here (team-lead ruling, 2026-08-24): (a) this
adapter does not emit `execution.result` from the Magazine source at all --
implemented below, every row is rejected -- or (b) an S9-C0 freeze-change
ruling decides how a legacy execution result can be represented without a
canonical `ExecutionAttempt`. (b) is not this lane's, or team-lead's, to
decide unilaterally. This file implements (a): the adapter still performs
every row-level validity check a future, unblocked version would need
(pairing, sibling-item admissibility, terminal status, clock skew) so that
work is not thrown away, but the final step -- once all of those pass -- is
an unconditional, disclosed rejection rather than a fabricated receipt.
"Reject rather than fabricate" is the same discipline `action_item_adapter
.py`'s own Sla check and this package's `synthesis.py` module docstring
already establish for every other adapter in this deliverable.

See `.claude/skills/modus/PENDING-ARMS.md` for the open S9-C0 question this
leaves; do not resolve it by re-adding a synthesized `execution_attempt_ref`
without that ruling landing first.
"""

from __future__ import annotations

from research_os.models.operational_receipt import OperationalReceipt

from backend.services.research_os import _core_path  # noqa: F401  (sys.path bootstrap)
from backend.services.research_os.action_item_adapter import adapt_ops_intent_to_action_item
from backend.services.research_os.legacy_magazine import (
    OPS_INTENT_TERMINAL_STATUSES,
    OpsIntentRow,
    OpsReceiptRow,
)
from backend.services.research_os.loss_report import (
    AdapterLossReport,
    AdapterResult,
    LegacyFieldFate,
    LegacyFieldReport,
    assert_every_legacy_field_accounted_for,
)
from backend.services.research_os.synthesis import parse_legacy_timestamp

SOURCE_SYSTEM = "bali-zero-magazine"
SOURCE_KIND = "ops_receipts"
CANONICAL_KIND = "operational_receipt"

_BLOCKED_REASON = (
    "BLOCKED pending an S9-C0 freeze-change ruling (team-lead, 2026-08-24): "
    "every ops_receipts row can only produce receipt_type='execution.result' "
    "(no other v1 OperationalReceipt receipt_type is expressible from this "
    "legacy source), and execution.result requires a REAL execution_attempt_ref "
    "(operational_receipt.py:170-175) -- EXECUTION_ATTEMPT_CAPABLE_RECEIPT_TYPES "
    "has exactly one member (operational_receipt.py:101-103), so no other "
    "receipt_type may carry the ref either. This deliverable's three slices "
    "never construct a real ExecutionAttempt object, so no execution_attempt_ref "
    "this adapter could produce would ever be real -- and close_execution_attempt() "
    "(operational_receipt.py:224-249) compares the ref against a REAL "
    "ExecutionAttempt, meaning a synthesized ref would make the receipt "
    "permanently unclosable. This is precisely the failure shape "
    "operational_receipt.py's own 2026-08-23 revision (lines 84-100) was "
    "hardened against, after a Kimi K3 adversarial review broke the prior "
    "blocklist-shaped guard the same way. No ops_receipts row is adoptable as "
    "an OperationalReceipt until that ruling lands."
)


def _reject(source_id: str, row: OpsReceiptRow, reason: str) -> AdapterResult[OperationalReceipt]:
    report = AdapterLossReport(
        source_system=SOURCE_SYSTEM,
        source_kind=SOURCE_KIND,
        source_id=source_id,
        canonical_kind=CANONICAL_KIND,
        fields=tuple(LegacyFieldReport(k, LegacyFieldFate.REJECTED, None, reason) for k in row),
    )
    assert_every_legacy_field_accounted_for(dict(row), report)
    return AdapterResult(canonical=None, loss_report=report, accepted=False)


def adapt_ops_receipt_to_operational_receipt(
    receipt_row: OpsReceiptRow, intent_row: OpsIntentRow
) -> AdapterResult[OperationalReceipt]:
    receipt_id = receipt_row["receipt_id"]

    if receipt_row["intent_id"] != intent_row["intent_id"]:
        return _reject(
            receipt_id,
            receipt_row,
            f"receipt_row.intent_id ({receipt_row['intent_id']!r}) does not match the "
            f"supplied intent_row.intent_id ({intent_row['intent_id']!r}) -- mismatched pairing",
        )

    item_result = adapt_ops_intent_to_action_item(intent_row)
    if not item_result.accepted:
        shared_reason = (
            item_result.loss_report.fields[0].reason
            if item_result.loss_report.fields
            else "action_item adaptation rejected the parent intent row"
        )
        return _reject(
            receipt_id,
            receipt_row,
            f"parent ops_intents row rejected by action_item adaptation: {shared_reason}",
        )

    status = receipt_row["status"]
    if status not in OPS_INTENT_TERMINAL_STATUSES:
        return _reject(receipt_id, receipt_row, f"non-terminal status {status!r} on a receipt row")

    recorded_at = parse_legacy_timestamp(receipt_row["created_at"])
    # `observed_at`: the parent intent's own completion instant when present,
    # falling back to this receipt's own created_at when the parent has none
    # -- same disclosed split the pre-block version of this adapter used.
    completed_at = intent_row.get("completed_at")
    observed_at = parse_legacy_timestamp(completed_at) if completed_at else recorded_at
    if observed_at > recorded_at:
        return _reject(
            receipt_id,
            receipt_row,
            "parent intent's completed_at postdates this receipt's own created_at (clock skew)",
        )

    # Every row-level validity check above passed -- this row WOULD be a
    # legitimate candidate once the architectural blocker below is lifted.
    # It is rejected here, not constructed, per the module docstring.
    return _reject(receipt_id, receipt_row, _BLOCKED_REASON)
