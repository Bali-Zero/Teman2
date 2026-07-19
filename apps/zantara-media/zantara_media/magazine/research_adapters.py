"""Production research adapters over sanitized public projections and NotebookLM."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Literal, Protocol
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from zantara_media.magazine.adapters import StoryCandidate
from zantara_media.magazine.loaders import LoadedProjection, load_named_projection
from zantara_media.magazine.research_sources import ResearchSourceRegistry, ResearchSubject
from zantara_media.magazine.research_worker import (
    ResearchAdapter,
    ResearchClaim,
    ResearchEvidence,
    ResearchMode,
    ResearchWorkerError,
)
from zantara_media.security.dlp import INDONESIAN_PII_PATTERNS


class NotebookQueryClient(Protocol):
    async def query(self, notebook_ref: str, prompt: str) -> str: ...


class ResearchSourceUnavailableError(RuntimeError):
    """Content-free adapter error safe for worker classification."""


_PII = tuple(re.compile(pattern) for pattern in INDONESIAN_PII_PATTERNS.values())
_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)
_PRIVATE_MARKER = re.compile(
    r"(?i)(?:passport\s+[a-z0-9]{6,}|api[_-]?key|bearer\s+[a-z0-9._-]+|"
    r"password\s*[:=]|secret\s*[:=]|\[raw\]|raw[_ -](?:payload|document|content))"
)
_DECIMAL = re.compile(r"^-?(?:0|[1-9]\d*)(?:\.\d+)?$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MAX_NOTEBOOK_ANSWER_BYTES = 64_000


def _instant(value: str) -> datetime:
    if not value.endswith("Z"):
        raise ValueError("timestamp must use canonical UTC")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed


def _opaque_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:32]
    return f"{prefix}:{digest}"


def _subject_ids(request: Mapping[str, Any]) -> tuple[str, ...]:
    topics = request.get("topic_ids")
    entities = request.get("entity_ids")
    tokens = request.get("index_tokens")
    if not isinstance(topics, list) or not isinstance(entities, list) or tokens != []:
        raise ResearchWorkerError("production research requires stable public subjects")
    if any(not isinstance(value, str) for value in topics + entities):
        raise ResearchWorkerError("invalid stable public subject")
    return tuple(sorted(topics + entities))


def _request_facets(request: Mapping[str, Any]) -> Mapping[str, Any]:
    facets = request.get("facets")
    if not isinstance(facets, Mapping):
        raise ResearchWorkerError("invalid research facets")
    return facets


def _candidate_text(candidate: StoryCandidate) -> str:
    values = (
        candidate.public_id,
        candidate.slug,
        candidate.title,
        candidate.deck,
        candidate.summary,
        candidate.why_it_matters,
        candidate.curiosity_text or "",
        *(claim.normalized_text for claim in candidate.claims),
    )
    return "\n".join(values).casefold()


def _matches(candidate: StoryCandidate, subject: ResearchSubject) -> bool:
    haystack = _candidate_text(candidate)
    return any(term.casefold() in haystack for term in subject.search_terms)


def _candidate_is_allowed(
    candidate: StoryCandidate, projection: LoadedProjection, facets: Mapping[str, Any]
) -> bool:
    try:
        if _instant(candidate.updated_at) > _instant(projection.cutoff):
            return False
    except ValueError:
        return False
    domains = facets.get("domains")
    languages = facets.get("languages")
    confidence = facets.get("confidence")
    lifecycle_states = facets.get("lifecycle_states")
    if not all(
        isinstance(selected, list)
        for selected in (domains, languages, confidence, lifecycle_states)
    ):
        return False
    return (
        (not domains or candidate.domain in domains)
        and (not languages or candidate.language in languages)
        and (
            not confidence
            or candidate.research_confidence is not None
            and candidate.research_confidence in confidence
        )
        and (
            not lifecycle_states
            or candidate.research_lifecycle_state is not None
            and candidate.research_lifecycle_state in lifecycle_states
        )
    )


def _claims_for_candidate(
    *,
    candidate: StoryCandidate,
    system_id: str,
    subject_id: str,
    evidence_types: set[str],
) -> list[ResearchClaim]:
    evidence_by_id = {item.evidence_id: item for item in candidate.evidence_refs}
    result: list[ResearchClaim] = []
    for claim in candidate.claims:
        evidence: list[ResearchEvidence] = []
        for upstream_id in claim.evidence_ids:
            item = evidence_by_id.get(upstream_id)
            if item is None or item.source_type not in evidence_types:
                continue
            citation = item.document_citation or item.evidence_note
            if citation is None or item.canonical_url is None or item.published_at is None:
                continue
            evidence.append(
                ResearchEvidence(
                    evidence_id=_opaque_id(
                        "evidence", system_id, candidate.public_id, subject_id, item.evidence_id
                    ),
                    publisher=item.publisher,
                    citation=citation,
                    canonical_url=item.canonical_url,
                    source_type=item.source_type,
                    published_at=item.published_at,
                )
            )
        if not evidence:
            continue
        if claim.claim_kind == "numeric" and (
            claim.numeric_value is None or claim.numeric_unit is None or claim.as_of is None
        ):
            continue
        result.append(
            ResearchClaim(
                claim_id=_opaque_id(
                    "claim", system_id, candidate.public_id, subject_id, claim.claim_id
                ),
                kind=claim.claim_kind,
                text=claim.normalized_text,
                evidence=tuple(evidence[:12]),
                numeric_value=claim.numeric_value,
                numeric_unit=claim.numeric_unit,
                as_of=claim.as_of,
            )
        )
    return result


class PublicProjectionResearchAdapter:
    """Search, compare, or timeline over four named public projection files only."""

    def __init__(
        self, *, mode: Literal["search", "compare", "timeline"], registry: ResearchSourceRegistry
    ) -> None:
        self._mode = mode
        self._registry = registry

    async def execute(self, request: Mapping[str, Any]) -> tuple[str, Sequence[ResearchClaim]]:
        if request.get("mode") != self._mode:
            raise ResearchWorkerError("research adapter mode mismatch")
        subject_ids = _subject_ids(request)
        if not subject_ids:
            raise ResearchWorkerError("research request has no public subject")
        if self._mode == "compare" and len(subject_ids) != 2:
            raise ResearchWorkerError("compare requires two public subjects")
        if self._mode == "timeline" and len(subject_ids) != 1:
            raise ResearchWorkerError("timeline requires one public subject")
        try:
            subjects = [
                (subject_id, self._registry.subject(subject_id)) for subject_id in subject_ids
            ]
        except ValueError as exc:
            raise ResearchWorkerError("unknown public research subject") from exc

        facets = _request_facets(request)
        systems = facets.get("source_system_ids")
        evidence_types_raw = facets.get("evidence_types")
        if (
            not isinstance(systems, list)
            or not systems
            or not isinstance(evidence_types_raw, list)
            or not evidence_types_raw
        ):
            raise ResearchWorkerError("invalid public research filters")
        try:
            projections = [
                await load_named_projection(system_id, self._registry.projection_path(system_id))
                for system_id in sorted(systems)
            ]
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ResearchSourceUnavailableError("public research source unavailable") from exc

        rows: list[tuple[str, str, str, str, ResearchClaim]] = []
        evidence_types = set(evidence_types_raw)
        for subject_id, subject in subjects:
            for projection in projections:
                for candidate in projection.candidates:
                    if not _candidate_is_allowed(candidate, projection, facets) or not _matches(
                        candidate, subject
                    ):
                        continue
                    date_key = candidate.event_occurred_at or candidate.updated_at
                    for claim in _claims_for_candidate(
                        candidate=candidate,
                        system_id=projection.system_id,
                        subject_id=subject_id,
                        evidence_types=evidence_types,
                    ):
                        rows.append(
                            (
                                subject_id,
                                date_key,
                                projection.system_id,
                                candidate.public_id,
                                claim,
                            )
                        )
        if self._mode == "timeline":
            rows.sort(key=lambda row: (row[1], row[2], row[3], row[4].claim_id))
        else:
            rows.sort(key=lambda row: (row[0], row[2], row[3], row[4].claim_id))
        claims = [row[4] for row in rows[:50]]
        labels = ", ".join(subject.label for _, subject in subjects)
        summaries = {
            "search": f"Found {len(claims)} evidence-bound public findings for {labels}.",
            "compare": f"Compared evidence-bound public findings for {labels}.",
            "timeline": f"Ordered {len(claims)} evidence-bound public findings for {labels}.",
        }
        return summaries[self._mode], claims


class NotebookEvidencePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    publisher: str = Field(min_length=1, max_length=200)
    citation: str = Field(min_length=1, max_length=500)
    canonical_url: str
    source_type: Literal["official", "journalism", "research", "dataset"]
    published_at: str

    @field_validator("canonical_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("notebook evidence URL must be public HTTPS")
        return value

    @field_validator("published_at")
    @classmethod
    def validate_published_at(cls, value: str) -> str:
        _instant(value)
        return value


class NotebookClaimPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["fact", "numeric", "analysis"]
    text: str = Field(min_length=1, max_length=2000)
    numeric_value: str | None
    numeric_unit: str | None
    as_of: str | None
    evidence: tuple[NotebookEvidencePayload, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def validate_numeric_metadata(self) -> NotebookClaimPayload:
        if self.kind == "numeric":
            if (
                self.numeric_value is None
                or _DECIMAL.fullmatch(self.numeric_value) is None
                or self.numeric_unit is None
                or self.as_of is None
                or _DATE.fullmatch(self.as_of) is None
            ):
                raise ValueError("notebook numeric claim lacks normalized metadata")
        elif self.numeric_value is not None or self.numeric_unit is not None:
            raise ValueError("non-numeric notebook claim contains numeric metadata")
        if self.as_of is not None and _DATE.fullmatch(self.as_of) is None:
            raise ValueError("notebook claim as_of must be an ISO date")
        return self


class NotebookResultPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["magazine-notebook-result.v1"]
    summary: str = Field(min_length=1, max_length=2000)
    claims: tuple[NotebookClaimPayload, ...] = Field(min_length=1, max_length=20)


def _assert_sanitized_notebook_payload(value: Any) -> None:
    if isinstance(value, Mapping):
        for item in value.values():
            _assert_sanitized_notebook_payload(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _assert_sanitized_notebook_payload(item)
        return
    if isinstance(value, str) and (
        _UUID.search(value)
        or _PRIVATE_MARKER.search(value)
        or any(pattern.search(value) for pattern in _PII)
    ):
        raise ResearchSourceUnavailableError("notebook source unavailable")


_NOTEBOOK_TASKS = {
    "explain": "Explain the current public position and why it matters.",
    "compare": "Compare the public positions found in the cited sources.",
    "timeline": "Order the public developments chronologically.",
}
_NOTEBOOK_EVIDENCE_TYPES = frozenset({"official", "journalism", "research", "dataset"})
_NOTEBOOK_UNSUPPORTED_FACETS = ("domains", "confidence", "lifecycle_states", "languages")


def _notebook_evidence_types(facets: Mapping[str, Any]) -> tuple[str, ...]:
    if facets.get("source_system_ids") != ["notebooklm"]:
        raise ResearchWorkerError("invalid notebook insight request")
    for key in _NOTEBOOK_UNSUPPORTED_FACETS:
        selected = facets.get(key)
        if not isinstance(selected, list) or selected:
            raise ResearchWorkerError("unsupported notebook insight facet")
    selected_evidence = facets.get("evidence_types")
    if (
        not isinstance(selected_evidence, list)
        or any(
            not isinstance(source_type, str) or source_type not in _NOTEBOOK_EVIDENCE_TYPES
            for source_type in selected_evidence
        )
        or len(set(selected_evidence)) != len(selected_evidence)
    ):
        raise ResearchWorkerError("invalid notebook insight evidence filter")
    return tuple(sorted(selected_evidence or _NOTEBOOK_EVIDENCE_TYPES))


def _notebook_prompt(label: str, template: str, evidence_types: Sequence[str]) -> str:
    task = _NOTEBOOK_TASKS[template]
    allowed_evidence = ", ".join(evidence_types)
    return (
        "Use only public, citable sources already present in this notebook. "
        f"Subject: {label}. Task: {task} "
        f"Allowed evidence types: {allowed_evidence}. "
        "Return JSON only with this exact closed schema: "
        '{"schema_version":"magazine-notebook-result.v1","summary":"...",'
        '"claims":[{"kind":"fact|numeric|analysis","text":"...",'
        '"numeric_value":null,"numeric_unit":null,"as_of":"YYYY-MM-DD",'
        '"evidence":[{"publisher":"...","citation":"...",'
        '"canonical_url":"https://...","source_type":"official|journalism|research|dataset",'
        '"published_at":"YYYY-MM-DDTHH:MM:SSZ"}]}]}. '
        "Every claim must include at least one public citation and URL. "
        "Do not include notebook identifiers, source identifiers, private data, or raw excerpts."
    )


class NotebookInsightResearchAdapter:
    """Closed NotebookLM insight path using only server-held subjects and templates."""

    def __init__(self, *, registry: ResearchSourceRegistry, client: NotebookQueryClient) -> None:
        self._registry = registry
        self._client = client

    async def execute(self, request: Mapping[str, Any]) -> tuple[str, Sequence[ResearchClaim]]:
        subject_ids = _subject_ids(request)
        template = request.get("template")
        facets = _request_facets(request)
        if (
            request.get("mode") != "notebook_insight"
            or len(subject_ids) != 1
            or template not in _NOTEBOOK_TASKS
        ):
            raise ResearchWorkerError("invalid notebook insight request")
        evidence_types = _notebook_evidence_types(facets)
        allowed_evidence_types = set(evidence_types)
        try:
            subject = self._registry.subject(subject_ids[0])
        except ValueError as exc:
            raise ResearchWorkerError("unknown public research subject") from exc
        if subject.notebook_ref is None:
            raise ResearchWorkerError("notebook insight is not configured for subject")
        try:
            answer = await self._client.query(
                subject.notebook_ref.get_secret_value(),
                _notebook_prompt(subject.label, str(template), evidence_types),
            )
            if not isinstance(answer, str) or len(answer.encode()) > _MAX_NOTEBOOK_ANSWER_BYTES:
                raise ValueError("invalid notebook answer")
            payload = NotebookResultPayload.model_validate_json(answer)
            dumped = payload.model_dump(mode="json")
            _assert_sanitized_notebook_payload(dumped)
        except ResearchWorkerError:
            raise
        except Exception as exc:
            raise ResearchSourceUnavailableError("notebook source unavailable") from exc

        claims: list[ResearchClaim] = []
        for claim_index, claim in enumerate(payload.claims):
            evidence = tuple(
                ResearchEvidence(
                    evidence_id=_opaque_id(
                        "evidence",
                        subject_ids[0],
                        str(claim_index),
                        str(evidence_index),
                        item.publisher,
                        item.citation,
                    ),
                    publisher=item.publisher,
                    citation=item.citation,
                    canonical_url=item.canonical_url,
                    source_type=item.source_type,
                    published_at=item.published_at,
                )
                for evidence_index, item in enumerate(claim.evidence)
                if item.source_type in allowed_evidence_types
            )
            if not evidence:
                continue
            claims.append(
                ResearchClaim(
                    claim_id=_opaque_id(
                        "claim", subject_ids[0], str(claim_index), claim.kind, claim.text
                    ),
                    kind=claim.kind,
                    text=claim.text,
                    evidence=evidence,
                    numeric_value=claim.numeric_value,
                    numeric_unit=claim.numeric_unit,
                    as_of=claim.as_of,
                )
            )
        if not claims:
            raise ResearchSourceUnavailableError("notebook source unavailable")
        summary = (
            f"Notebook Insight returned {len(claims)} evidence-bound public findings "
            f"for {subject.label}."
        )
        return summary, claims


def build_production_adapters(
    *, registry: ResearchSourceRegistry, nlm_client: NotebookQueryClient
) -> dict[ResearchMode, ResearchAdapter]:
    """Build the complete, closed production adapter map required by ResearchWorker."""

    return {
        "search": PublicProjectionResearchAdapter(mode="search", registry=registry),
        "compare": PublicProjectionResearchAdapter(mode="compare", registry=registry),
        "timeline": PublicProjectionResearchAdapter(mode="timeline", registry=registry),
        "notebook_insight": NotebookInsightResearchAdapter(registry=registry, client=nlm_client),
    }
