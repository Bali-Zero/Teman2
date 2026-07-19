"""Deny-by-default adapters from collector projections to public story candidates."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from math import isfinite
from typing import Any, Literal, Protocol

from pydantic import ConfigDict, BaseModel, Field

from zantara_media.magazine.contracts import (
    ClaimV1,
    CollectorRunProjectionV1,
    EvidenceRefV1,
)
from zantara_media.security.dlp import INDONESIAN_PII_PATTERNS

_DENIED_KEYS = {
    "raw",
    "raw_payload",
    "payload",
    "body",
    "content",
    "document_text",
    "full_text",
    "source_content",
    "osint",
    "pii",
    "passport",
    "passport_number",
    "nik",
    "npwp",
    "kitas",
    "phone",
    "email",
    "client_name",
    "person_name",
    "notebook_uuid",
    "notebook_id",
    "source_uuid",
    "source_id_raw",
    "credential",
    "secret",
    "token",
    "api_key",
}
_COPY_FIELDS = (
    "public_id",
    "slug",
    "title",
    "deck",
    "summary",
    "why_it_matters",
    "curiosity_text",
)
_PII = tuple(re.compile(pattern) for pattern in INDONESIAN_PII_PATTERNS.values())
_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)
_CREDENTIAL = re.compile(
    r"(?i)(?:api[_-]?key|authorization|bearer\s+[a-z0-9._-]+|password\s*[:=]|secret\s*[:=])"
)
_RAW_MARKER = re.compile(
    r"(?i)(?:\[raw\]|-----begin [^-]+-----|raw[_ -](?:payload|document|content))"
)
_CONFIDENCE_LABELS: dict[str, Literal["normal", "cautious", "abstain"]] = {
    "high": "normal",
    "medium": "cautious",
    "low": "abstain",
}
_LIFECYCLE_STATES: dict[str, Literal["published", "amended", "superseded"] | None] = {
    "developing": None,
    "verified": "published",
    "published": "published",
    "amended": "amended",
    "superseded": "superseded",
}


class SanitizationError(ValueError):
    """Raised when an upstream row cannot cross the public-data boundary."""


class StoryCandidate(BaseModel):
    """Sanitized, immutable input to ranking and composition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    public_id: str
    slug: str
    language: str = "en"
    domain: str
    severity: str
    first_seen_at: str
    event_occurred_at: str | None
    updated_at: str
    title: str
    deck: str
    summary: str
    why_it_matters: str
    curiosity_text: str | None
    claims: tuple[ClaimV1, ...]
    evidence_refs: tuple[EvidenceRefV1, ...]
    contributing_system_ids: tuple[str, ...]
    asset_digests: tuple[str, ...]
    legal_effect_claim_ids: tuple[str, ...]
    novelty: float = Field(ge=0, le=1)
    recency: float = Field(default=0.5, ge=0, le=1)
    operational_impact: float = Field(ge=0, le=1)
    adapter_version: str
    research_confidence: Literal["normal", "cautious", "abstain"] | None = None
    research_lifecycle_state: Literal["published", "amended", "superseded"] | None = None
    expected_current_version: int = Field(default=0, ge=0)


class CollectorAdapter(Protocol):
    system_id: str

    def candidates(self, rows: Iterable[Mapping[str, Any]]) -> list[StoryCandidate]: ...

    def collector_run(self, manifest: Mapping[str, Any]) -> CollectorRunProjectionV1: ...


def _assert_clean_input(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower().replace("-", "_") in _DENIED_KEYS:
                raise SanitizationError("SANITIZATION_DENIED_KEY")
            _assert_clean_input(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _assert_clean_input(item)
        return
    if isinstance(value, str):
        if _UUID.search(value):
            raise SanitizationError("SANITIZATION_UUID")
        if _CREDENTIAL.search(value):
            raise SanitizationError("SANITIZATION_CREDENTIAL")
        if _RAW_MARKER.search(value):
            raise SanitizationError("SANITIZATION_RAW_MARKER")
        if any(pattern.search(value) for pattern in _PII):
            raise SanitizationError("SANITIZATION_PII")


def _assert_public_copy(row: Mapping[str, Any]) -> None:
    for field in _COPY_FIELDS:
        value = row.get(field)
        if not isinstance(value, str):
            continue
        if any(pattern.search(value) for pattern in _PII):
            raise SanitizationError("SANITIZATION_PII")


def _assert_projection_has_no_pii(value: Any, path: str = "candidate") -> None:
    if isinstance(value, str):
        if any(pattern.search(value) for pattern in _PII):
            raise SanitizationError("SANITIZATION_PII")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            _assert_projection_has_no_pii(item, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_projection_has_no_pii(item, f"{path}[{index}]")


def _research_confidence(
    row: Mapping[str, Any],
) -> Literal["normal", "cautious", "abstain"] | None:
    label_value = row.get("confidence")
    score_value = row.get("confidence_score")
    label: Literal["normal", "cautious", "abstain"] | None = None
    score: Literal["normal", "cautious", "abstain"] | None = None
    if label_value is not None:
        if not isinstance(label_value, str) or label_value not in _CONFIDENCE_LABELS:
            raise SanitizationError("SANITIZATION_INVALID_CONFIDENCE")
        label = _CONFIDENCE_LABELS[label_value]
    if score_value is not None:
        if (
            isinstance(score_value, bool)
            or not isinstance(score_value, (int, float))
            or not isfinite(score_value)
            or not 0 <= score_value <= 1
        ):
            raise SanitizationError("SANITIZATION_INVALID_CONFIDENCE_SCORE")
        if score_value > 0.60:
            score = "normal"
        elif score_value >= 0.15:
            score = "cautious"
        else:
            score = "abstain"
    if label is not None and score is not None and label != score:
        raise SanitizationError("SANITIZATION_CONFLICTING_CONFIDENCE")
    return label or score


def _research_lifecycle_state(
    row: Mapping[str, Any],
) -> Literal["published", "amended", "superseded"] | None:
    value = row.get("lifecycle_state")
    if value is None:
        return None
    if not isinstance(value, str) or value not in _LIFECYCLE_STATES:
        raise SanitizationError("SANITIZATION_INVALID_LIFECYCLE")
    return _LIFECYCLE_STATES[value]


class BasePublicAdapter:
    """Allowlist projection shared by all federated collector adapters."""

    system_id = "base"
    adapter_version = "magazine-adapter.v1"

    def collector_run(self, manifest: Mapping[str, Any]) -> CollectorRunProjectionV1:
        _assert_clean_input(manifest)
        public = manifest
        fields = (
            "schema_version",
            "run_id",
            "collector_id",
            "started_at",
            "completed_at",
            "status",
            "freshness",
            "items_seen",
            "items_eligible",
            "source_count",
            "unreachable_source_count",
            "watermark",
            "verified_at",
        )
        try:
            projection = {field: public[field] for field in fields}
        except KeyError as exc:
            raise SanitizationError(
                f"collector manifest missing public field {exc.args[0]}"
            ) from exc
        projection["system_id"] = self.system_id
        return CollectorRunProjectionV1.model_validate(projection)

    def candidates(self, rows: Iterable[Mapping[str, Any]]) -> list[StoryCandidate]:
        result: list[StoryCandidate] = []
        for original in rows:
            _assert_clean_input(original)
            row = self._normalize(original)
            if self._exclude(row):
                continue
            _assert_public_copy(row)
            try:
                candidate = self._candidate(row)
                _assert_projection_has_no_pii(candidate.model_dump(mode="json"))
                result.append(candidate)
            except (KeyError, TypeError, ValueError) as exc:
                if isinstance(exc, SanitizationError):
                    raise
                public_id = row.get("public_id", "unknown")
                raise SanitizationError(
                    f"invalid sanitized {self.system_id} row {public_id!r}: {exc}"
                ) from exc
        return result

    def _normalize(self, row: Mapping[str, Any]) -> Mapping[str, Any]:
        return row

    def _exclude(self, row: Mapping[str, Any]) -> bool:
        return False

    def _candidate(self, row: Mapping[str, Any]) -> StoryCandidate:
        if row.get("asset_digests"):
            raise SanitizationError("SANITIZATION_UNBOUND_ASSET")
        return StoryCandidate(
            public_id=row["public_id"],
            slug=row["slug"],
            language=row.get("language", "en"),
            domain=row["domain"],
            severity=row["severity"],
            first_seen_at=row["first_seen_at"],
            event_occurred_at=row.get("event_occurred_at"),
            updated_at=row["updated_at"],
            title=row["title"],
            deck=row["deck"],
            summary=row["summary"],
            why_it_matters=row["why_it_matters"],
            curiosity_text=row.get("curiosity_text"),
            claims=tuple(ClaimV1.model_validate(item) for item in row.get("claims", ())),
            evidence_refs=tuple(
                EvidenceRefV1.model_validate(item) for item in row.get("evidence_refs", ())
            ),
            contributing_system_ids=(self.system_id,),
            asset_digests=(),
            legal_effect_claim_ids=tuple(row.get("legal_effect_claim_ids", ())),
            novelty=row.get("novelty", 0.5),
            recency=row.get("recency", 0.5),
            operational_impact=row.get("operational_impact", 0.5),
            adapter_version=self.adapter_version,
            research_confidence=_research_confidence(row),
            research_lifecycle_state=_research_lifecycle_state(row),
            expected_current_version=row.get("expected_current_version", 0),
        )


class IntelLakeAdapter(BasePublicAdapter):
    system_id = "intel-lake"

    def _exclude(self, row: Mapping[str, Any]) -> bool:
        return row.get("is_probe_sandbox") is True


class MataGarudaAdapter(BasePublicAdapter):
    system_id = "mata-garuda"


class RegulatoryWatcherAdapter(BasePublicAdapter):
    system_id = "regulatory-watcher"

    def _normalize(self, row: Mapping[str, Any]) -> Mapping[str, Any]:
        normalized = dict(row)
        if "title" not in normalized and "headline" in normalized:
            normalized["title"] = normalized["headline"]
        if "severity" not in normalized and "impact" in normalized:
            normalized["severity"] = normalized["impact"]
        return normalized


class NotebookLMAdapter(BasePublicAdapter):
    system_id = "notebooklm"

    def _exclude(self, row: Mapping[str, Any]) -> bool:
        kind = row.get("record_kind", "insight")
        if kind == "health":
            return True
        if kind != "insight":
            raise SanitizationError("NotebookLM record_kind must be health or insight")
        return False


class AdapterRegistry:
    """Explicit registry; unknown collectors cannot silently publish."""

    def __init__(self) -> None:
        self._adapters: dict[str, CollectorAdapter] = {}

    def register(self, system_id: str, adapter: CollectorAdapter) -> None:
        if system_id in self._adapters:
            raise ValueError(f"adapter already registered for {system_id}")
        self._adapters[system_id] = adapter

    def get(self, system_id: str) -> CollectorAdapter:
        return self._adapters[system_id]

    def system_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))


def default_adapter_registry() -> AdapterRegistry:
    registry = AdapterRegistry()
    for adapter in (
        IntelLakeAdapter(),
        MataGarudaAdapter(),
        NotebookLMAdapter(),
        RegulatoryWatcherAdapter(),
    ):
        registry.register(adapter.system_id, adapter)
    return registry
