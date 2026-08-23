"""Parity probes: compare an adapted canonical object back against the
legacy record it came from, and REPORT divergence -- never assert blanket
equality. Most canonical fields are intentionally approximated or
synthesized (see each adapter's loss report); asserting they equal the raw
legacy value would be a false test, not a real check. Each probe below only
compares the handful of fields the adapter's own loss report calls MAPPED
(a genuine 1:1 or independently-recomputable value) -- exactly the subset
where disagreement would mean the adapter regressed, not that a documented
design decision is "wrong".
"""

from __future__ import annotations

from dataclasses import dataclass

from research_os.models.action_intent import ActionIntent
from research_os.models.action_item import ActionItem
from research_os.models.operational_receipt import OperationalReceipt

from backend.services.research_os import _core_path  # noqa: F401  (sys.path bootstrap)
from backend.services.research_os.legacy_magazine import OpsIntentRow, OpsReceiptRow
from backend.services.research_os.synthesis import parse_legacy_timestamp


@dataclass(frozen=True)
class ParityDivergence:
    field: str
    legacy_value: object
    canonical_value: object
    note: str


@dataclass(frozen=True)
class ParityReport:
    source_kind: str
    source_id: str
    canonical_kind: str
    fields_checked: int
    divergences: tuple[ParityDivergence, ...]

    @property
    def clean(self) -> bool:
        return not self.divergences


def probe_action_item_parity(row: OpsIntentRow, item: ActionItem) -> ParityReport:
    divergences: list[ParityDivergence] = []
    checks = 0

    checks += 1
    if item.created_at != parse_legacy_timestamp(row["created_at"]):
        divergences.append(
            ParityDivergence("created_at", row["created_at"], str(item.created_at), "should be an exact map")
        )
    checks += 1
    if item.sla.opened_at != parse_legacy_timestamp(row["created_at"]):
        divergences.append(
            ParityDivergence(
                "sla.opened_at", row["created_at"], str(item.sla.opened_at), "should equal created_at"
            )
        )
    checks += 1
    if item.sla.due_at != parse_legacy_timestamp(row["expires_at"]):
        divergences.append(
            ParityDivergence(
                "sla.due_at", row["expires_at"], str(item.sla.due_at), "should be an exact map of expires_at"
            )
        )

    return ParityReport(
        source_kind="ops_intents",
        source_id=row["intent_id"],
        canonical_kind="action_item",
        fields_checked=checks,
        divergences=tuple(divergences),
    )


def probe_action_intent_parity(row: OpsIntentRow, intent: ActionIntent) -> ParityReport:
    divergences: list[ParityDivergence] = []
    checks = 0

    checks += 1
    if intent.idempotency_key != row["idempotency_key"]:
        divergences.append(
            ParityDivergence(
                "idempotency_key", row["idempotency_key"], intent.idempotency_key, "should be an exact map"
            )
        )
    checks += 1
    if intent.action_type != row["intent_kind"]:
        divergences.append(
            ParityDivergence("action_type", row["intent_kind"], intent.action_type, "should be an exact map")
        )
    checks += 1
    if intent.authority_required.role != row["effective_role"]:
        divergences.append(
            ParityDivergence(
                "authority_required.role",
                row["effective_role"],
                intent.authority_required.role,
                "should be an exact map",
            )
        )
    checks += 1
    created_at = parse_legacy_timestamp(row["created_at"])
    expected_expires_after = max(1, int((parse_legacy_timestamp(row["expires_at"]) - created_at).total_seconds()))
    if intent.authority_required.expires_after_seconds != expected_expires_after:
        divergences.append(
            ParityDivergence(
                "authority_required.expires_after_seconds",
                expected_expires_after,
                intent.authority_required.expires_after_seconds,
                "should equal floor(expires_at - created_at) in seconds",
            )
        )

    return ParityReport(
        source_kind="ops_intents",
        source_id=row["intent_id"],
        canonical_kind="action_intent",
        fields_checked=checks,
        divergences=tuple(divergences),
    )


def probe_operational_receipt_parity(
    receipt_row: OpsReceiptRow, receipt: OperationalReceipt
) -> ParityReport:
    divergences: list[ParityDivergence] = []
    checks = 0

    checks += 1
    if receipt.recorded_at != parse_legacy_timestamp(receipt_row["created_at"]):
        divergences.append(
            ParityDivergence(
                "recorded_at", receipt_row["created_at"], str(receipt.recorded_at), "should be an exact map"
            )
        )
    checks += 1
    if receipt.idempotency_key != receipt_row["receipt_id"]:
        divergences.append(
            ParityDivergence(
                "idempotency_key",
                receipt_row["receipt_id"],
                receipt.idempotency_key,
                "should reuse receipt_id (no legacy idempotency-key column exists)",
            )
        )
    checks += 1
    expected_outcome_code = f"bali-zero-magazine.{receipt_row['status']}"
    if receipt.outcome_code != expected_outcome_code:
        divergences.append(
            ParityDivergence(
                "outcome_code", expected_outcome_code, receipt.outcome_code, "should be a namespaced echo of status"
            )
        )
    checks += 1
    if receipt.subject_refs[0].object_id != receipt_row["intent_id"]:
        divergences.append(
            ParityDivergence(
                "subject_refs[0].object_id",
                receipt_row["intent_id"],
                receipt.subject_refs[0].object_id,
                "should name the parent ops_intents row",
            )
        )

    return ParityReport(
        source_kind="ops_receipts",
        source_id=receipt_row["receipt_id"],
        canonical_kind="operational_receipt",
        fields_checked=checks,
        divergences=tuple(divergences),
    )
