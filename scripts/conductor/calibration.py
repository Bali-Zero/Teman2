"""Pure records and aggregation helpers for MIR calibration artifacts.

This module never invokes a model.  It accepts blinded sample hashes and scores,
then emits the versioned overlay consumed by :mod:`model_registry`.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from math import sqrt
from statistics import fmean, pvariance
from typing import Any, Mapping, Sequence

from scripts.conductor.contracts import TaskProfile


class CalibrationError(ValueError):
    """Raised when a calibration artifact is internally inconsistent."""


@dataclass(frozen=True)
class CalibrationRecord:
    """One blinded, endpoint-specific task-profile calibration result."""

    benchmark_id: str
    benchmark_version: str
    endpoint_id: str
    endpoint_profile_hash: str
    task_profile_id: str
    score: float
    conservative_score: float
    sample_count: int
    sample_hashes: tuple[str, ...]
    scorer_id: str
    scorer_version: str
    measured_at: str
    expires_at: str
    dispersion: float

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> CalibrationRecord:
        """Build a record after JSON Schema validation and check cross-fields."""
        scorer = raw["scorer"]
        dispersion = raw["dispersion"]
        record = cls(
            benchmark_id=str(raw["benchmark_id"]),
            benchmark_version=str(raw["benchmark_version"]),
            endpoint_id=str(raw["endpoint_id"]),
            endpoint_profile_hash=str(raw["endpoint_profile_hash"]),
            task_profile_id=str(raw["task_profile_id"]),
            score=float(raw["score"]),
            conservative_score=float(raw["conservative_score"]),
            sample_count=int(raw["sample_count"]),
            sample_hashes=tuple(str(item) for item in raw["sample_hashes"]),
            scorer_id=str(scorer["id"]),
            scorer_version=str(scorer["version"]),
            measured_at=str(raw["measured_at"]),
            expires_at=str(raw["expires_at"]),
            dispersion=float(dispersion["value"]),
        )
        record.validate()
        return record

    def validate(self) -> None:
        """Reject artifacts whose aggregate cannot be traced to unique samples."""
        if self.sample_count != len(self.sample_hashes):
            raise CalibrationError("sample_count does not match sample_hashes")
        if len(set(self.sample_hashes)) != len(self.sample_hashes):
            raise CalibrationError("sample_hashes must be unique")
        if self.conservative_score > self.score:
            raise CalibrationError("conservative_score cannot exceed score")
        measured = parse_timestamp(self.measured_at)
        expires = parse_timestamp(self.expires_at)
        if measured is None or expires is None:
            raise CalibrationError(
                "calibration timestamps must be timezone-aware ISO-8601"
            )
        if expires <= measured:
            raise CalibrationError("calibration expires_at must follow measured_at")

    def rejection(
        self,
        *,
        endpoint_profile_hash: str,
        profile: TaskProfile,
        as_of: datetime | None,
    ) -> str | None:
        """Return the single stable reason this record cannot open a route."""
        if self.endpoint_profile_hash != endpoint_profile_hash:
            return "endpoint_profile_mismatch"
        if self.benchmark_id != profile.benchmark_id:
            return "benchmark_id_mismatch"
        if self.benchmark_version != profile.benchmark_version:
            return "benchmark_version_mismatch"
        if self.sample_count < profile.minimum_sample_count:
            return "low_sample"
        if profile.maximum_dispersion is not None and (
            self.dispersion > profile.maximum_dispersion
        ):
            return "high_variance"
        if profile.minimum_task_score is not None and (
            self.conservative_score < profile.minimum_task_score
        ):
            return "below_floor"
        if as_of is None:
            return "clock_missing"
        measured = parse_timestamp(self.measured_at)
        expires = parse_timestamp(self.expires_at)
        if measured is None or expires is None:
            return "timestamp_invalid"
        if measured > as_of:
            return "timestamp_future"
        if expires < as_of:
            return "stale"
        return None

    def as_mapping(self) -> dict[str, Any]:
        """Return the canonical JSON shape for the checked-in overlay schema."""
        return {
            "benchmark_id": self.benchmark_id,
            "benchmark_version": self.benchmark_version,
            "endpoint_id": self.endpoint_id,
            "endpoint_profile_hash": self.endpoint_profile_hash,
            "task_profile_id": self.task_profile_id,
            "score": self.score,
            "conservative_score": self.conservative_score,
            "sample_count": self.sample_count,
            "sample_hashes": list(self.sample_hashes),
            "scorer": {"id": self.scorer_id, "version": self.scorer_version},
            "measured_at": self.measured_at,
            "expires_at": self.expires_at,
            "dispersion": {"metric": "sample_variance", "value": self.dispersion},
        }


@dataclass(frozen=True)
class EndpointHostObservation:
    """Fresh evidence for an exact endpoint model on one allowed fleet host."""

    endpoint_id: str
    endpoint_profile_hash: str
    host: str
    model_identifier: str
    available: bool
    healthy: bool
    latency_ms: int
    context_tokens: int
    output_tokens: int
    enforcement_mode: str
    identity_verified: bool
    probe_id: str
    probe_version: str
    observed_at: str
    expires_at: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> EndpointHostObservation:
        """Build an observation after JSON Schema validation and check its clock."""
        probe = raw["probe"]
        observation = cls(
            endpoint_id=str(raw["endpoint_id"]),
            endpoint_profile_hash=str(raw["endpoint_profile_hash"]),
            host=str(raw["host"]),
            model_identifier=str(raw["model_identifier"]),
            available=bool(raw["available"]),
            healthy=bool(raw["healthy"]),
            latency_ms=int(raw["latency_ms"]),
            context_tokens=int(raw["context_tokens"]),
            output_tokens=int(raw["output_tokens"]),
            enforcement_mode=str(raw["enforcement_mode"]),
            identity_verified=bool(raw["identity_verified"]),
            probe_id=str(probe["id"]),
            probe_version=str(probe["version"]),
            observed_at=str(raw["observed_at"]),
            expires_at=str(raw["expires_at"]),
        )
        observation.validate()
        return observation

    def validate(self) -> None:
        observed = parse_timestamp(self.observed_at)
        expires = parse_timestamp(self.expires_at)
        if observed is None or expires is None:
            raise CalibrationError(
                "observation timestamps must be timezone-aware ISO-8601"
            )
        if expires <= observed:
            raise CalibrationError("observation expires_at must follow observed_at")

    def rejection(
        self,
        *,
        endpoint_profile_hash: str,
        model_identifier: str,
        machine_allowlist: Sequence[str],
        as_of: datetime | None,
    ) -> str | None:
        """Return why an observation cannot be merged into the exact endpoint."""
        if self.endpoint_profile_hash != endpoint_profile_hash:
            return "endpoint_profile_mismatch"
        if self.model_identifier != model_identifier:
            return "model_identifier_mismatch"
        if self.host not in machine_allowlist:
            return "host_not_allowed"
        if as_of is None:
            return "clock_missing"
        observed = parse_timestamp(self.observed_at)
        expires = parse_timestamp(self.expires_at)
        if observed is None or expires is None:
            return "timestamp_invalid"
        if observed > as_of:
            return "timestamp_future"
        if expires < as_of:
            return "stale"
        if not self.identity_verified:
            return "identity_unverified"
        return None


def parse_timestamp(value: str | None) -> datetime | None:
    """Parse only timezone-aware ISO timestamps and normalize them to UTC."""
    if not isinstance(value, str) or not value:
        return None
    normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def aggregate_blinded_samples(
    samples: Sequence[Mapping[str, Any]],
    *,
    endpoint_hashes: Mapping[str, str],
    benchmark_id: str,
    benchmark_version: str,
    scorer_id: str,
    scorer_version: str,
    measured_at: str,
    expires_at: str,
) -> tuple[CalibrationRecord, ...]:
    """Aggregate score-only samples without retaining prompts or model outputs."""
    grouped: dict[tuple[str, str], list[tuple[str, float]]] = defaultdict(list)
    for sample in samples:
        if set(sample) != {"endpoint_id", "task_profile_id", "sample_hash", "score"}:
            raise CalibrationError(
                "sample fields must be endpoint_id, task_profile_id, sample_hash, score"
            )
        endpoint_id = sample["endpoint_id"]
        task_profile_id = sample["task_profile_id"]
        sample_hash = sample["sample_hash"]
        score = sample["score"]
        if not all(
            isinstance(item, str) and item
            for item in (endpoint_id, task_profile_id, sample_hash)
        ):
            raise CalibrationError("sample identifiers must be non-empty strings")
        if len(sample_hash) != 64 or any(
            character not in "0123456789abcdef" for character in sample_hash
        ):
            raise CalibrationError("sample_hash must be a lowercase SHA-256 digest")
        if (
            not isinstance(score, (int, float))
            or isinstance(score, bool)
            or not 0 <= score <= 1
        ):
            raise CalibrationError("sample score must be between 0 and 1")
        grouped[(endpoint_id, task_profile_id)].append((sample_hash, float(score)))

    records: list[CalibrationRecord] = []
    for (endpoint_id, task_profile_id), values in sorted(grouped.items()):
        if endpoint_id not in endpoint_hashes:
            raise CalibrationError(f"unknown endpoint_id: {endpoint_id}")
        hashes = tuple(sorted(item[0] for item in values))
        if len(set(hashes)) != len(hashes):
            raise CalibrationError(
                f"duplicate sample_hash for {endpoint_id}/{task_profile_id}"
            )
        scores = [item[1] for item in values]
        mean = fmean(scores)
        variance = pvariance(scores)
        conservative = max(0.0, mean - sqrt(variance / len(scores)))
        record = CalibrationRecord(
            benchmark_id=benchmark_id,
            benchmark_version=benchmark_version,
            endpoint_id=endpoint_id,
            endpoint_profile_hash=endpoint_hashes[endpoint_id],
            task_profile_id=task_profile_id,
            score=mean,
            conservative_score=conservative,
            sample_count=len(scores),
            sample_hashes=hashes,
            scorer_id=scorer_id,
            scorer_version=scorer_version,
            measured_at=measured_at,
            expires_at=expires_at,
            dispersion=variance,
        )
        record.validate()
        records.append(record)
    return tuple(records)
