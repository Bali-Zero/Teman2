"""infra/vcr/records.py — the 4-axis claim vocabulary (VCR spec §3 / R1).

A claim is never a boolean. Every observation carries four ORTHOGONAL axes:
truth (is it correct, right now), freshness (how old is the last real check),
coverage (does an expected observation exist at all), verifier (is the checker
itself healthy). Collapsing these into one `status` field was the single
largest defect the council found in the pre-pilot draft — do not re-collapse it.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Optional

# ---------------------------------------------------------------- truth_state
TRUE = "TRUE"
FALSE = "FALSE"
UNVERIFIED = "UNVERIFIED"
INCONCLUSIVE = "INCONCLUSIVE"
TRUTH_STATES = {TRUE, FALSE, UNVERIFIED, INCONCLUSIVE}

# ------------------------------------------------------------- freshness_state
CURRENT = "CURRENT"
STALE = "STALE"
EXPIRED = "EXPIRED"
FRESHNESS_STATES = {CURRENT, STALE, EXPIRED}

# -------------------------------------------------------------- coverage_state
PRESENT = "PRESENT"
MISSING = "MISSING"
PARTIAL = "PARTIAL"
UNEXPECTED = "UNEXPECTED"
COVERAGE_STATES = {PRESENT, MISSING, PARTIAL, UNEXPECTED}

# -------------------------------------------------------------- verifier_state
HEALTHY = "HEALTHY"
DEGRADED = "DEGRADED"
FAILED = "FAILED"
DRIFTED = "DRIFTED"
VERIFIER_STATES = {HEALTHY, DEGRADED, FAILED, DRIFTED}


@dataclasses.dataclass(frozen=True)
class ClaimContext:
    """The claim subject is (seat, host, auth_context) — never seat alone (R1).

    A context-free verdict is provably wrong for at least one caller whenever a
    seat is alive in one context and dead in another at the same instant (GLM:
    CRED_UNAVAILABLE under sshd, LIVE in an interactive keychain-unlocked
    session, both observed the same day — VCR draft §0.1).
    """

    host: str
    auth_context: str  # interactive | ssh | launchd | cron-token-N

    def key(self) -> str:
        return f"{self.host}::{self.auth_context}"


@dataclasses.dataclass(frozen=True)
class ClaimObservation:
    """One append-only record (VCR spec §3). Never mutated after creation."""

    claim_id: str  # f"{seat}::{context.key()}"
    claim_type: str  # "seat_health" for this pilot
    subject_id: str  # the seat name
    context: ClaimContext
    observed_at: str  # ISO-8601 UTC
    raw_status: str  # the arsenal_probe status string (LIVE/AUTH_DEAD/...)
    raw_evidence: str  # evidence_tail from arsenal_probe (already scrubbed)
    latency_ms: int
    truth_state: str
    truth_reason: str
    source_report_ts: str = ""  # the underlying arsenal_probe report's own `ts`
    # field (NOT observed_at, which is when the accessor recorded this). Used
    # to dedup: a cache-only read of an UNCHANGED report must never append a
    # second observation, or repeated reads of one flaky probe would fake the
    # "2 consecutive observations" hysteresis confirms (accessor.py).

    def __post_init__(self) -> None:
        if self.truth_state not in TRUTH_STATES:
            raise ValueError(f"invalid truth_state: {self.truth_state!r}")

    def to_dict(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d["context"] = {"host": self.context.host, "auth_context": self.context.auth_context}
        return d

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "ClaimObservation":
        ctx = d["context"]
        return ClaimObservation(
            claim_id=d["claim_id"],
            claim_type=d["claim_type"],
            subject_id=d["subject_id"],
            context=ClaimContext(host=ctx["host"], auth_context=ctx["auth_context"]),
            observed_at=d["observed_at"],
            raw_status=d["raw_status"],
            raw_evidence=d["raw_evidence"],
            latency_ms=d["latency_ms"],
            truth_state=d["truth_state"],
            truth_reason=d["truth_reason"],
            source_report_ts=d.get("source_report_ts", ""),
        )


@dataclasses.dataclass(frozen=True)
class MaterializedState:
    """What the accessor returns — a materialized VIEW, never hand-set (R1/§3)."""

    seat: str
    context: ClaimContext
    truth_state: str
    freshness_state: str
    coverage_state: str
    verifier_state: str
    reason: str
    observed_at: Optional[str]

    def __post_init__(self) -> None:
        for field_name, value, allowed in (
            ("truth_state", self.truth_state, TRUTH_STATES),
            ("freshness_state", self.freshness_state, FRESHNESS_STATES),
            ("coverage_state", self.coverage_state, COVERAGE_STATES),
            ("verifier_state", self.verifier_state, VERIFIER_STATES),
        ):
            if value not in allowed:
                raise ValueError(f"invalid {field_name}: {value!r}")

    def all_healthy(self) -> bool:
        return (
            self.truth_state == TRUE
            and self.freshness_state == CURRENT
            and self.coverage_state == PRESENT
            and self.verifier_state == HEALTHY
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "seat": self.seat,
            "context": {"host": self.context.host, "auth_context": self.context.auth_context},
            "truth_state": self.truth_state,
            "freshness_state": self.freshness_state,
            "coverage_state": self.coverage_state,
            "verifier_state": self.verifier_state,
            "reason": self.reason,
            "observed_at": self.observed_at,
        }
