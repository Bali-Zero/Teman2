"""Strict loader for the Zero-approved Visa Oracle privacy authority.

The JSON approval record is the sole repository authority for durations and
policy identifiers. Database registration and operator tooling import this
loader instead of copying those values into application code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ApprovedPrivacyPolicy:
    """Validated subset needed by the database and retention boundary."""

    policy_id: str
    approved_by: str
    approved_on: str
    status: str
    decision_retention_days: int
    idempotency_retention_hours: int
    retention_anchor: str
    telemetry_retention_days: int
    dsr_service_level_hours: int
    legal_hold_review_interval_days: int
    dpia_required_before_enforce: bool


def default_policy_path() -> Path:
    """Return the checked-in machine-readable approval path."""

    return (
        Path(__file__).resolve().parents[5]
        / "docs"
        / "policies"
        / "visa-oracle-privacy-policy-v1.json"
    )


def _mapping(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _positive_int(value: object, *, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def load_approved_privacy_policy(path: Path | None = None) -> ApprovedPrivacyPolicy:
    """Load and validate the approved policy; reject drift fail-closed."""

    policy_path = path or default_policy_path()
    raw = _mapping(json.loads(policy_path.read_text(encoding="utf-8")), label="policy")
    decision = _mapping(raw.get("decision_processing"), label="decision_processing")
    idempotency = _mapping(raw.get("idempotency"), label="idempotency")
    telemetry = _mapping(raw.get("telemetry"), label="telemetry")
    dsr = _mapping(raw.get("data_subject_requests"), label="data_subject_requests")
    legal_hold = _mapping(raw.get("legal_hold"), label="legal_hold")
    activation = _mapping(raw.get("activation_conditions"), label="activation_conditions")

    policy_id = _string(raw.get("policy_id"), label="policy_id")
    status = _string(raw.get("status"), label="status")
    retention_anchor = _string(decision.get("retention_anchor"), label="retention_anchor")
    pii_free = telemetry.get("pii_free")
    dpia_required = activation.get("dpia_required_before_enforce")

    if policy_id != "visa-oracle-privacy-v1":
        raise ValueError("policy_id is not the approved Visa Oracle V1 authority")
    if status != "APPROVED_PRE_ENFORCE":
        raise ValueError("privacy policy is not approved for implementation")
    if retention_anchor != "EVALUATED_AT":
        raise ValueError("Visa Oracle Privacy Policy V1 requires EVALUATED_AT")
    if pii_free is not True:
        raise ValueError("Visa Oracle telemetry must remain PII-free")
    if dpia_required is not True:
        raise ValueError("DPIA must remain mandatory before ENFORCE")

    return ApprovedPrivacyPolicy(
        policy_id=policy_id,
        approved_by=_string(raw.get("approved_by"), label="approved_by").lower(),
        approved_on=_string(raw.get("approved_on"), label="approved_on"),
        status=status,
        decision_retention_days=_positive_int(
            decision.get("retention_days"), label="decision_processing.retention_days"
        ),
        idempotency_retention_hours=_positive_int(
            idempotency.get("retention_hours"), label="idempotency.retention_hours"
        ),
        retention_anchor=retention_anchor,
        telemetry_retention_days=_positive_int(
            telemetry.get("retention_days"), label="telemetry.retention_days"
        ),
        dsr_service_level_hours=_positive_int(
            dsr.get("service_level_hours"), label="data_subject_requests.service_level_hours"
        ),
        legal_hold_review_interval_days=_positive_int(
            legal_hold.get("review_interval_days"), label="legal_hold.review_interval_days"
        ),
        dpia_required_before_enforce=dpia_required,
    )


__all__ = ["ApprovedPrivacyPolicy", "default_policy_path", "load_approved_privacy_policy"]
