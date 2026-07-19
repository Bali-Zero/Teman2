"""Pure deterministic composition of morning and breaking publication packets."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field

from zantara_media.magazine.adapters import StoryCandidate
from zantara_media.magazine.contracts import (
    CollectorRunProjectionV1,
    EditionPacketV1,
    EditionPlacementV1,
    StoryPacketV1,
    StoryVersionV1,
)
from zantara_media.magazine.ranking import ScoredCandidate, score_candidate, select_diverse


class ComposerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    required_system_ids: tuple[str, ...]
    editor_version: str
    ruleset_version: str
    story_limit: int = Field(default=10, ge=1, le=50)
    adapter_version: str = "magazine-composer.v1"


def _timestamp(value: datetime) -> str:
    normalized = value.astimezone(timezone.utc).replace(microsecond=0)
    return normalized.isoformat().replace("+00:00", "Z")


def _packet_id(prefix: str, payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{prefix}-{hashlib.sha256(encoded.encode()).hexdigest()[:24]}"


def _story(scored: ScoredCandidate, ruleset_version: str) -> StoryVersionV1:
    candidate = scored.candidate
    return StoryVersionV1(
        story_id=candidate.public_id,
        version=candidate.expected_current_version + 1,
        expected_current_version=candidate.expected_current_version,
        slug=candidate.slug,
        language=candidate.language,
        domain=candidate.domain,
        severity=candidate.severity,
        lifecycle_state="verified",
        first_seen_at=candidate.first_seen_at,
        event_occurred_at=candidate.event_occurred_at,
        updated_at=candidate.updated_at,
        title=candidate.title,
        deck=candidate.deck,
        summary=candidate.summary,
        why_it_matters=candidate.why_it_matters,
        curiosity_text=candidate.curiosity_text,
        score_components=scored.score_components,
        claims=candidate.claims,
        evidence_refs=candidate.evidence_refs,
        contributing_system_ids=candidate.contributing_system_ids,
        coverage_state="full",
        confidence="high" if scored.score_components.evidence >= 1 else "medium",
        asset_digests=candidate.asset_digests,
        adapter_version=candidate.adapter_version,
        ruleset_version=ruleset_version,
    )


def compose_edition(
    *,
    candidates: Iterable[StoryCandidate],
    collector_runs: Iterable[CollectorRunProjectionV1],
    cutoff: datetime,
    expected_current_revision: int,
    expected_breaking_revision: int,
    config: ComposerConfig,
) -> EditionPacketV1:
    if cutoff.tzinfo is None:
        raise ValueError("cutoff must be timezone-aware")
    runs = tuple(sorted(collector_runs, key=lambda item: (item.system_id, item.run_id)))
    healthy = {item.system_id for item in runs if item.status == "healthy"}
    gaps = tuple(sorted(set(config.required_system_ids) - healthy))
    scored = tuple(score_candidate(item) for item in candidates)
    selected = select_diverse(scored, limit=config.story_limit)
    stories = tuple(_story(item, config.ruleset_version) for item in selected)
    edition_kind = "standard" if stories else "quiet"
    placements = tuple(
        EditionPlacementV1(
            story_id=story.story_id,
            version=story.version,
            section=story.domain,
            order=index,
            lead=index == 1 and edition_kind == "standard",
        )
        for index, story in enumerate(stories, start=1)
    )
    breaking_ids = tuple(
        item.candidate.public_id for item in selected if item.breaking_eligible
    )
    claim_ids = tuple(sorted({claim.claim_id for story in stories for claim in story.claims}))
    evidence_ids = tuple(
        sorted({evidence.evidence_id for story in stories for evidence in story.evidence_refs})
    )
    asset_digests = tuple(sorted({digest for story in stories for digest in story.asset_digests}))
    edition_date = (cutoff.astimezone(timezone.utc) + timedelta(hours=8)).date().isoformat()
    seed = {
        "date": edition_date,
        "revision": expected_current_revision + 1,
        "breaking_revision": expected_breaking_revision,
        "stories": [(story.story_id, story.version) for story in stories],
        "runs": [run.run_id for run in runs],
        "gaps": gaps,
    }
    return EditionPacketV1(
        schema_version="edition.v1",
        packet_id=_packet_id("edition", seed),
        editor_version=config.editor_version,
        ruleset_version=config.ruleset_version,
        edition_date=edition_date,
        edition_revision=expected_current_revision + 1,
        expected_current_revision=expected_current_revision,
        expected_breaking_revision=expected_breaking_revision,
        edition_kind=edition_kind,
        publication_state="building",
        coverage_state="partial" if gaps else "complete",
        readiness_cutoff=_timestamp(cutoff),
        verified_at=_timestamp(cutoff),
        collector_run_ids=tuple(run.run_id for run in runs),
        stories=stories,
        placements=placements,
        breaking_story_ids=breaking_ids,
        referenced_claim_ids=claim_ids,
        referenced_evidence_ids=evidence_ids,
        asset_digests=asset_digests,
        coverage_gaps=gaps,
        reader_notices=("Some required collector projections were unavailable at cutoff.",)
        if gaps
        else (),
    )


def compose_breaking(
    scored: ScoredCandidate,
    *,
    expected_breaking_revision: int,
    ruleset_version: str = "rules.v1",
) -> StoryPacketV1:
    if not scored.breaking_eligible:
        raise ValueError(f"candidate is not eligible for Breaking: {scored.breaking_reason}")
    story = _story(scored, ruleset_version)
    seed = {
        "story": story.story_id,
        "version": story.version,
        "breaking_revision": expected_breaking_revision,
        "updated_at": story.updated_at,
    }
    return StoryPacketV1(
        schema_version="story.v1",
        packet_id=_packet_id("breaking", seed),
        publication_target="breaking",
        expected_breaking_revision=expected_breaking_revision,
        publication_state="building",
        verified_at=story.updated_at,
        story=story,
    )
