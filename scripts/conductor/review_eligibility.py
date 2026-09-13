"""Pure reviewer-independence validator for the "dual-consul army" mission.

No installed check today rejects a contributor acting as its own grader:
`evidence_pack_lint.py` enforces build-lane FAMILY diversity and nothing
about reviewer independence, and this module does not touch that concern —
family membership is informational here, never a rejection basis. This is
the missing check: a contributor (A17) must not be its own reviewer, and a
review of a since-changed artifact (A18) is stale.

`evaluate` is pure, deterministic, and stdlib-only: no I/O, no clock, no
randomness, no mutation of its input. Rank confers no exemption — a reviewer
named "opus" or "sol" is judged by the exact same rule as any other name.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

try:
    from scripts.conductor.contracts import Decision
except ImportError:  # pragma: no cover - exercised when imported standalone
    class Decision(StrEnum):
        """An outcome of pure planning, including a visible abstention."""

        ALLOW = "allow"
        DELEGATE_REQUIRED = "delegate_required"
        BLOCK = "block"
        DEGRADED = "degraded"
        ABSTAIN = "abstain"


SCHEMA_VERSION = "review-eligibility/1"


@dataclass(frozen=True)
class ReviewRecord:
    """The typed shape of one review event: an artifact, its contributors,

    and the reviewer who judged it.
    """

    artifact_hash: str
    contributors: tuple[str, ...]
    reviewer: str
    reviewed_hash: str
    reviewer_family: str
    contributor_families: tuple[str, ...]


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of `evaluate`: a decision plus stable, sorted reason codes."""

    decision: Decision
    reason_codes: tuple[str, ...]


def _is_missing(value: object) -> bool:
    """True when a required field is absent, None, or an empty string."""
    return value is None or value == ""


def _block(reason_codes: set[str]) -> ValidationResult:
    return ValidationResult(decision=Decision.BLOCK, reason_codes=tuple(sorted(reason_codes)))


def _normalize(name: str) -> str:
    """Case-fold and strip surrounding whitespace for identity comparison."""
    return name.strip().casefold()


def evaluate(record: dict) -> ValidationResult:
    """Validate that `reviewer` is independent of `contributors` for one review.

    Pure and deterministic: the same `record` always yields an equal
    `ValidationResult`, with `reason_codes` sorted so ordering never depends
    on set iteration order. `record` is never mutated.
    """
    if not isinstance(record, dict):
        return _block({"missing_required_field"})

    reason_codes: set[str] = set()

    schema_version = record.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        reason_codes.add("unknown_schema_version")

    artifact_hash = record.get("artifact_hash")
    reviewer = record.get("reviewer")
    reviewed_hash = record.get("reviewed_hash")
    reviewer_family = record.get("reviewer_family")
    raw_contributors = record.get("contributors")
    raw_contributor_families = record.get("contributor_families")

    for value in (artifact_hash, reviewer, reviewed_hash, reviewer_family):
        if _is_missing(value):
            reason_codes.add("missing_required_field")

    if raw_contributors is None or not isinstance(raw_contributors, (list, tuple)):
        reason_codes.add("missing_required_field")
        contributors: tuple[object, ...] = ()
    else:
        contributors = tuple(raw_contributors)
        if len(contributors) == 0:
            reason_codes.add("no_contributor_recorded")

    if raw_contributor_families is None or not isinstance(raw_contributor_families, (list, tuple)):
        reason_codes.add("missing_required_field")

    # Rank confers no exemption (A17): the SAME normalized-identity comparison
    # applies to a reviewer named "opus" or "sol" as to any other name — no
    # branch here treats any name specially. An exact match survives
    # strip+casefold trivially, so one comparison covers both table rows
    # ("appears in contributors" and "matches after case/whitespace folding").
    if isinstance(reviewer, str) and contributors:
        normalized_reviewer = _normalize(reviewer)
        for contributor in contributors:
            if isinstance(contributor, str) and _normalize(contributor) == normalized_reviewer:
                reason_codes.add("reviewer_is_contributor")
                break

    if not _is_missing(artifact_hash) and not _is_missing(reviewed_hash):
        if reviewed_hash != artifact_hash:
            reason_codes.add("stale_review_hash")

    if reason_codes:
        return _block(reason_codes)

    return ValidationResult(decision=Decision.ALLOW, reason_codes=())
