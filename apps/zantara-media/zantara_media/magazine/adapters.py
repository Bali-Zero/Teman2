"""Deny-by-default adapters from collector projections to public story candidates."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any, Protocol

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
    operational_impact: float = Field(ge=0, le=1)
    adapter_version: str
    expected_current_version: int = Field(default=0, ge=0)


class CollectorAdapter(Protocol):
    system_id: str

    def candidates(self, rows: Iterable[Mapping[str, Any]]) -> list[StoryCandidate]: ...

    def collector_run(self, manifest: Mapping[str, Any]) -> CollectorRunProjectionV1: ...


def _sanitize_mapping(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize_mapping(item)
            for key, item in value.items()
            if str(key).lower().replace("-", "_") not in _DENIED_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize_mapping(item) for item in value]
    return value


def _assert_public_copy(row: Mapping[str, Any]) -> None:
    for field in _COPY_FIELDS:
        value = row.get(field)
        if not isinstance(value, str):
            continue
        if any(pattern.search(value) for pattern in _PII):
            raise SanitizationError(f"PII detected in allowlisted field {field}")


def _assert_projection_has_no_pii(value: Any, path: str = "candidate") -> None:
    if isinstance(value, str):
        if any(pattern.search(value) for pattern in _PII):
            raise SanitizationError(f"PII detected in public {path}")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            _assert_projection_has_no_pii(item, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_projection_has_no_pii(item, f"{path}[{index}]")


class BasePublicAdapter:
    """Allowlist projection shared by all federated collector adapters."""

    system_id = "base"
    adapter_version = "magazine-adapter.v1"

    def collector_run(self, manifest: Mapping[str, Any]) -> CollectorRunProjectionV1:
        public = _sanitize_mapping(manifest)
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
            raise SanitizationError(f"collector manifest missing public field {exc.args[0]}") from exc
        projection["system_id"] = self.system_id
        return CollectorRunProjectionV1.model_validate(projection)

    def candidates(self, rows: Iterable[Mapping[str, Any]]) -> list[StoryCandidate]:
        result: list[StoryCandidate] = []
        for original in rows:
            row = self._normalize(_sanitize_mapping(original))
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
            asset_digests=tuple(row.get("asset_digests", ())),
            legal_effect_claim_ids=tuple(row.get("legal_effect_claim_ids", ())),
            novelty=row.get("novelty", 0.5),
            operational_impact=row.get("operational_impact", 0.5),
            adapter_version=self.adapter_version,
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
