#!/usr/bin/env python3
"""Fail-closed preflight for the Visa Oracle analytics 365-day (12-month) TTL attestation.

The frontend destination is intentionally opaque in this repository.  This
tool therefore does not guess a vendor or mutate a dataset. It validates the
closed shape of a fresh, machine-readable, PII-free operator attestation.
The attestation is not direct provider proof: the independent grader must
reproduce its provider export and synthetic probe before product ENFORCE.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("visa_oracle.analytics_retention_preflight")

# 12 months, per Zero's 2026-08-20 retention ruling (DPIA V2 §A, signed at
# DPIA V2 §8 — docs/audits/2026-08-20-visa-oracle-dpia-v2.md). Expressed as a
# day count (365, not a separate months field) because the attestation schema
# below is day-granular throughout (`retention.ttl_days`, `MAX_EVIDENCE_AGE`
# in days) and the destination's automatic-TTL setting is itself configured
# in days by every provider this repo has surveyed — introducing a parallel
# months unit would need its own conversion and its own bug class for zero
# benefit. Supersedes the old provisional 90-day placeholder this constant
# held before the ruling.
EXPECTED_TTL_DAYS = 365
MAX_EVIDENCE_AGE = timedelta(days=7)
MAX_ATTESTATION_BYTES = 16_384
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
ROOT_KEYS = frozenset({"schema_version", "status", "destination", "retention", "verification"})
DESTINATION_KEYS = frozenset({"provider", "destination_id_sha256", "event_scope"})
RETENTION_KEYS = frozenset({"ttl_days", "mode"})
VERIFICATION_KEYS = frozenset(
    {
        "method",
        "observed_at",
        "synthetic_expired_event_was_present",
        "synthetic_expired_ingestion_receipt_sha256",
        "synthetic_expired_event_absent",
        "synthetic_control_event_present",
        "production_rows_deleted",
        "provider_export_sha256",
    }
)


class PreflightError(RuntimeError):
    """The supplied evidence cannot authorize retention ENFORCE."""


@dataclass(frozen=True, slots=True)
class AnalyticsRetentionAttestation:
    """Safe summary of a shape-valid destination attestation."""

    provider: str
    destination_id_sha256: str
    observed_at: datetime
    evidence_sha256: str


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PreflightError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _require_mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PreflightError(f"{field} must be an object")
    return value


def _require_exact_keys(value: dict[str, Any], expected: frozenset[str], field: str) -> None:
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise PreflightError(
            f"{field} has invalid keys; missing={missing} unexpected={unexpected}"
        )


def _parse_observed_at(value: Any) -> datetime:
    if not isinstance(value, str):
        raise PreflightError("verification.observed_at must be an ISO-8601 string")
    try:
        observed_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PreflightError("verification.observed_at is not valid ISO-8601") from exc
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise PreflightError("verification.observed_at must include a timezone")
    return observed_at.astimezone(timezone.utc)


def load_attestation(
    path: Path,
    *,
    now: datetime | None = None,
) -> AnalyticsRetentionAttestation:
    """Load a closed-shape attestation without logging its contents."""

    if not path.is_file():
        raise PreflightError("analytics retention attestation file is missing")
    try:
        with path.open("rb") as handle:
            raw_document = handle.read(MAX_ATTESTATION_BYTES + 1)
        if len(raw_document) > MAX_ATTESTATION_BYTES:
            raise PreflightError("analytics retention attestation exceeds 16384 bytes")
        document = json.loads(
            raw_document.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except PreflightError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PreflightError("analytics retention attestation is unreadable") from exc

    root = _require_mapping(document, "root")
    _require_exact_keys(root, ROOT_KEYS, "root")
    if type(root.get("schema_version")) is not int or root["schema_version"] != 1:
        raise PreflightError("unsupported analytics retention attestation schema")
    if root.get("status") != "ATTESTED":
        raise PreflightError("analytics destination is not ATTESTED")

    destination = _require_mapping(root.get("destination"), "destination")
    _require_exact_keys(destination, DESTINATION_KEYS, "destination")
    provider = destination.get("provider")
    if not isinstance(provider, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{1,63}", provider):
        raise PreflightError("destination.provider is missing or invalid")
    destination_hash = destination.get("destination_id_sha256")
    if not isinstance(destination_hash, str) or SHA256_RE.fullmatch(destination_hash) is None:
        raise PreflightError("destination_id_sha256 must be a SHA-256 hex digest")
    if destination.get("event_scope") != "visa_oracle_v2_*":
        raise PreflightError("TTL evidence is not scoped to Visa Oracle V2 events")

    retention = _require_mapping(root.get("retention"), "retention")
    _require_exact_keys(retention, RETENTION_KEYS, "retention")
    if type(retention.get("ttl_days")) is not int or retention["ttl_days"] != EXPECTED_TTL_DAYS:
        raise PreflightError("analytics TTL must equal 365 days (12 months, DPIA V2 §A)")
    if retention.get("mode") != "AUTOMATIC_TTL":
        raise PreflightError("analytics retention must be enforced by automatic TTL")

    verification = _require_mapping(root.get("verification"), "verification")
    _require_exact_keys(verification, VERIFICATION_KEYS, "verification")
    if verification.get("method") != "PROVIDER_READ_ONLY_EXPORT_AND_SYNTHETIC_PROBE":
        raise PreflightError("verification method is not the approved read-only export/probe")
    if verification.get("synthetic_expired_event_was_present") is not True:
        raise PreflightError("expired synthetic event prior ingestion is not proven")
    ingestion_receipt_hash = verification.get("synthetic_expired_ingestion_receipt_sha256")
    if not isinstance(ingestion_receipt_hash, str) or SHA256_RE.fullmatch(ingestion_receipt_hash) is None:
        raise PreflightError("synthetic expired ingestion receipt must be a SHA-256 hex digest")
    if verification.get("synthetic_expired_event_absent") is not True:
        raise PreflightError("expired synthetic event deletion is not proven")
    if verification.get("synthetic_control_event_present") is not True:
        raise PreflightError("unexpired synthetic control is not proven")
    if verification.get("production_rows_deleted") is not False:
        raise PreflightError("verification must not delete production rows")
    evidence_hash = verification.get("provider_export_sha256")
    if not isinstance(evidence_hash, str) or SHA256_RE.fullmatch(evidence_hash) is None:
        raise PreflightError("provider_export_sha256 must be a SHA-256 hex digest")

    observed_at = _parse_observed_at(verification.get("observed_at"))
    checked_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age = checked_at - observed_at
    if age < timedelta(0):
        raise PreflightError("analytics retention attestation is future-dated")
    if age > MAX_EVIDENCE_AGE:
        raise PreflightError("analytics retention attestation is older than 7 days")

    return AnalyticsRetentionAttestation(
        provider=provider,
        destination_id_sha256=destination_hash,
        observed_at=observed_at,
        evidence_sha256=evidence_hash,
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--attestation", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    try:
        attestation = load_attestation(args.attestation)
    except PreflightError as exc:
        logger.error("analytics_retention_preflight status=BLOCKED reason=%s", exc)
        return 2
    logger.info(
        "analytics_retention_preflight status=ATTESTED provider=%s "
        "destination_id_sha256=%s observed_at=%s provider_export_sha256=%s",
        attestation.provider,
        attestation.destination_id_sha256,
        attestation.observed_at.isoformat(),
        attestation.evidence_sha256,
    )
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    sys.exit(main(sys.argv[1:]))
