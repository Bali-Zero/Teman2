"""Shared loss-report shape for every legacy-to-canonical adapter in this package.

Work Packet 04 Deliverable 4: "Legacy-to-canonical adapters with loss
reports; no silent field dropping." The exit criterion this satisfies:
"Adapter parity tests showing every legacy field is mapped, intentionally
omitted with a reason, or rejected."

The ledger below is keyed on the LEGACY field, not the canonical one --
every column of the source row must appear exactly once with a stated fate.
`assert_every_legacy_field_accounted_for` turns that requirement into a
runnable check rather than a convention someone can silently forget.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, TypeVar

T = TypeVar("T")


class LegacyFieldFate(str, Enum):
    """What happened to one legacy column when adapting a row."""

    MAPPED = "mapped"
    # Direct or near-direct semantic match onto a canonical field.
    APPROXIMATED = "approximated"
    # Carried over, but the transform is lossy, a value-set mismatch, or a
    # repurposing the packet's own compatibility matrix flagged as needing
    # a ruling -- disclosed here rather than silently treated as exact.
    SYNTHESIZED_UNBACKED = "synthesized_unbacked"
    # The canonical field is non-optional and there is no legacy source at
    # all; the adapter fabricates a deterministic, clearly-marked reference
    # or default so the object can be constructed. It does not resolve to
    # any independently materialized object or fact.
    OMITTED = "omitted"
    # Intentionally not carried onto the canonical object; a reason is
    # required. This is the "genuine information loss" case (packet
    # Deliverable 4) -- e.g. `ActionItem.priority` -- not a bug to fix later.
    REJECTED = "rejected"
    # The legacy field's value made this particular row inadmissible for
    # adaptation altogether (see `AdapterResult.accepted`).


@dataclass(frozen=True)
class LegacyFieldReport:
    legacy_field: str
    fate: LegacyFieldFate
    canonical_field: str | None
    reason: str


@dataclass(frozen=True)
class AdapterLossReport:
    """One adapter run's full accounting: source identity, canonical kind
    produced, per-legacy-field fate ledger, and adapter-level warnings that
    do not belong to any single field (e.g. a design decision affecting the
    whole object).
    """

    source_system: str
    source_kind: str
    source_id: str
    canonical_kind: str
    fields: tuple[LegacyFieldReport, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def fates(self) -> dict[str, LegacyFieldFate]:
        return {f.legacy_field: f.fate for f in self.fields}


@dataclass(frozen=True)
class AdapterResult(Generic[T]):
    """What every adapter function in this package returns. `canonical` is
    `None` exactly when `accepted` is `False` -- a rejected row still gets a
    full loss report explaining why, never a bare exception.
    """

    canonical: T | None
    loss_report: AdapterLossReport
    accepted: bool


class LossReportIncompleteError(ValueError):
    """Raised when a loss report does not account for every legacy field
    that was actually present on the source row -- the guard against the
    "no silent field dropping" rule regressing silently.
    """


def assert_every_legacy_field_accounted_for(
    legacy_row: dict[str, object],
    report: AdapterLossReport,
) -> None:
    """Fail loudly if any key of `legacy_row` has no entry in `report.fields`,
    or if `report` names a field the row does not have. Intended to run
    inside every adapter before it returns, and again from adapter tests
    against real fixture-shaped rows -- the two independent checks the
    packet's exit criterion implies (adapter self-check, and a parity test
    that does not simply trust the adapter's own bookkeeping).
    """

    reported = {f.legacy_field for f in report.fields}
    row_fields = set(legacy_row.keys())
    missing = row_fields - reported
    extra = reported - row_fields
    if missing:
        raise LossReportIncompleteError(
            f"{report.canonical_kind} adapter for {report.source_kind}:{report.source_id} "
            f"never accounted for legacy field(s) {sorted(missing)}"
        )
    if extra:
        raise LossReportIncompleteError(
            f"{report.canonical_kind} adapter for {report.source_kind}:{report.source_id} "
            f"reported field(s) {sorted(extra)} that do not exist on the source row"
        )
