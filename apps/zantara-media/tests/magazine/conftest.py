from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest


HASH = "a" * 64
ZERO_HASH = "0" * 64


@pytest.fixture
def evidence_factory() -> Callable[..., dict[str, Any]]:
    def build(**overrides: Any) -> dict[str, Any]:
        value: dict[str, Any] = {
            "evidence_id": "evidence-1",
            "root_source_id": "root-1",
            "canonical_url": "https://example.go.id/regulation",
            "publisher": "Example Authority",
            "document_citation": "Regulation 1/2026",
            "published_at": "2026-07-17T20:00:00Z",
            "retrieved_at": "2026-07-17T21:00:00Z",
            "source_type": "official",
            "primary_document_status": "verified",
            "root_resolution_status": "resolved",
            "independence_verdict": "independent",
            "evidence_note": "The authority published the effective date.",
            "upstream_root_source_ids": [],
            "syndication_group_fingerprint": "sg-1",
            "independence_ruleset_version": "independence.v1",
            "independence_reason": "issuing-authority-primary-document",
            "counts_toward_breaking": True,
        }
        value.update(overrides)
        return value

    return build


@pytest.fixture
def story_factory(
    evidence_factory: Callable[..., dict[str, Any]],
) -> Callable[..., dict[str, Any]]:
    def build(**overrides: Any) -> dict[str, Any]:
        value: dict[str, Any] = {
            "story_id": "story-1",
            "version": 2,
            "expected_current_version": 1,
            "slug": "important-regulation",
            "language": "en",
            "domain": "compliance",
            "severity": "high",
            "lifecycle_state": "verified",
            "first_seen_at": "2026-07-17T20:00:00Z",
            "event_occurred_at": None,
            "updated_at": "2026-07-17T21:00:00Z",
            "title": "An important regulation changed",
            "deck": "The official source confirms the effective date.",
            "summary": "A concise sanitized summary.",
            "why_it_matters": "Operators should review affected deadlines.",
            "curiosity_text": None,
            "score_components": {
                "editorial": 0.9,
                "impact": 0.9,
                "freshness": 0.8,
                "evidence": 1.0,
                "diversity": 0.5,
            },
            "claims": [
                {
                    "claim_id": "claim-1",
                    "claim_kind": "fact",
                    "legal_effect": "changes-legal-effect",
                    "normalized_text": "The regulation has an effective date.",
                    "numeric_value": None,
                    "numeric_unit": None,
                    "as_of": "2026-07-18",
                    "evidence_ids": ["evidence-1"],
                    "breaking_gate": "official-primary",
                }
            ],
            "evidence_refs": [evidence_factory()],
            "contributing_system_ids": ["regulatory-watcher"],
            "coverage_state": "full",
            "confidence": "high",
            "asset_digests": [HASH],
            "adapter_version": "adapter.v1",
            "ruleset_version": "rules.v1",
        }
        value.update(overrides)
        return value

    return build


@pytest.fixture
def breaking_factory(
    story_factory: Callable[..., dict[str, Any]],
) -> Callable[..., dict[str, Any]]:
    def build(**overrides: Any) -> dict[str, Any]:
        value: dict[str, Any] = {
            "schema_version": "story.v1",
            "packet_id": "packet-breaking-1",
            "publication_target": "breaking",
            "expected_breaking_revision": 4,
            "publication_state": "building",
            "verified_at": "2026-07-17T21:01:00Z",
            "story": story_factory(),
        }
        value.update(overrides)
        return value

    return build


@pytest.fixture
def edition_factory(
    story_factory: Callable[..., dict[str, Any]],
) -> Callable[..., dict[str, Any]]:
    def build(**overrides: Any) -> dict[str, Any]:
        story = story_factory(severity="medium")
        value: dict[str, Any] = {
            "schema_version": "edition.v1",
            "packet_id": "packet-edition-1",
            "editor_version": "editor.v1",
            "ruleset_version": "rules.v1",
            "edition_date": "2026-07-18",
            "edition_revision": 5,
            "expected_current_revision": 4,
            "expected_breaking_revision": 4,
            "edition_kind": "standard",
            "publication_state": "building",
            "coverage_state": "complete",
            "readiness_cutoff": "2026-07-17T22:15:00Z",
            "verified_at": "2026-07-17T22:16:00Z",
            "collector_run_ids": ["run-1"],
            "stories": [story],
            "placements": [
                {
                    "story_id": "story-1",
                    "version": 2,
                    "section": "compliance",
                    "order": 1,
                    "lead": True,
                }
            ],
            "breaking_story_ids": [],
            "referenced_claim_ids": ["claim-1"],
            "referenced_evidence_ids": ["evidence-1"],
            "asset_digests": [HASH],
            "coverage_gaps": [],
            "reader_notices": [],
        }
        value.update(overrides)
        return value

    return build
