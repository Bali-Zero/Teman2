from __future__ import annotations

from datetime import datetime, timezone

import pytest

from zantara_media.magazine.adapters import StoryCandidate
from zantara_media.magazine.composer import ComposerConfig, compose_breaking, compose_edition
from zantara_media.magazine.contracts import (
    ClaimV1,
    CollectorRunProjectionV1,
    EvidenceRefV1,
)
from zantara_media.magazine.ranking import resolve_independence, score_candidate, select_diverse


def evidence(
    evidence_id: str,
    root: str,
    *,
    syndication: str,
    source_type: str = "journalism",
    primary: str = "not-primary",
    upstream: tuple[str, ...] = (),
) -> EvidenceRefV1:
    return EvidenceRefV1(
        evidence_id=evidence_id,
        root_source_id=root,
        canonical_url=f"https://example.com/{evidence_id}",
        publisher=f"Publisher {evidence_id}",
        document_citation="Regulation 1/2026" if source_type == "official" else None,
        published_at="2026-07-17T20:00:00Z",
        retrieved_at="2026-07-17T21:00:00Z",
        source_type=source_type,
        primary_document_status=primary,
        root_resolution_status="resolved",
        independence_verdict="independent",
        evidence_note="Sanitized evidence note.",
        upstream_root_source_ids=upstream,
        syndication_group_fingerprint=syndication,
        independence_ruleset_version="independence.v1",
        independence_reason="resolved-original-work",
        counts_toward_breaking=True,
    )


def candidate(
    *,
    public_id: str = "signal-1",
    domain: str = "compliance",
    severity: str = "high",
    evidences: tuple[EvidenceRefV1, ...] | None = None,
    gate: str | None = "official-primary",
    legal_effect: bool = True,
    impact: float = 0.9,
) -> StoryCandidate:
    refs = evidences or (
        evidence(
            "evidence-1",
            "root-1",
            syndication="official-1",
            source_type="official",
            primary="verified",
        ),
    )
    claim = ClaimV1(
        claim_id=f"claim-{public_id}",
        claim_kind="fact",
        legal_effect="changes-legal-effect",
        normalized_text="The regulation is effective.",
        numeric_value=None,
        numeric_unit=None,
        as_of="2026-07-18",
        evidence_ids=tuple(item.evidence_id for item in refs),
        breaking_gate=gate,
    )
    return StoryCandidate(
        public_id=public_id,
        slug=public_id,
        language="en",
        domain=domain,
        severity=severity,
        first_seen_at="2026-07-17T20:00:00Z",
        event_occurred_at=None,
        updated_at="2026-07-17T21:00:00Z",
        title=f"Title {public_id}",
        deck="Verified deck.",
        summary="Verified summary.",
        why_it_matters="Operational consequence.",
        curiosity_text=None,
        claims=(claim,),
        evidence_refs=refs,
        contributing_system_ids=("regulatory-watcher",),
        asset_digests=(),
        legal_effect_claim_ids=(claim.claim_id,) if legal_effect else (),
        novelty=0.8,
        operational_impact=impact,
        adapter_version="adapter.v1",
    )


def collector_run(system_id: str, status: str = "healthy") -> CollectorRunProjectionV1:
    return CollectorRunProjectionV1(
        schema_version="collector-run.v1",
        run_id=f"run-{system_id}",
        system_id=system_id,
        collector_id="default",
        started_at="2026-07-17T21:55:00Z",
        completed_at="2026-07-17T22:05:00Z",
        status=status,
        freshness="fresh",
        items_seen=1,
        items_eligible=1,
        source_count=1,
        unreachable_source_count=0,
        watermark="public-watermark",
        verified_at="2026-07-17T22:05:01Z",
    )


def test_official_high_impact_candidate_qualifies_breaking() -> None:
    result = score_candidate(candidate())
    assert result.breaking_eligible is True
    assert result.breaking_reason == "official-primary"


def test_two_mirrors_of_one_wire_story_do_not_form_quorum() -> None:
    first = evidence("evidence-a", "root-a", syndication="wire-1")
    second = evidence("evidence-b", "root-b", syndication="wire-1")
    result = resolve_independence((first, second))
    assert result.independent_root_count == 1
    scored = score_candidate(
        candidate(
            evidences=(first, second),
            gate="two-independent-root-sources",
            legal_effect=False,
        )
    )
    assert scored.breaking_eligible is False


def test_legal_effect_requires_official_primary_even_with_two_roots() -> None:
    refs = (
        evidence("evidence-a", "root-a", syndication="publisher-a"),
        evidence("evidence-b", "root-b", syndication="publisher-b"),
    )
    scored = score_candidate(
        candidate(evidences=refs, gate="two-independent-root-sources", legal_effect=True)
    )
    assert scored.breaking_eligible is False
    assert scored.breaking_reason == "legal-effect-requires-official-primary"


def test_diversity_selects_five_domains_before_second_story_from_one_domain() -> None:
    candidates = [
        candidate(public_id="compliance-1", domain="compliance", impact=1.0),
        candidate(public_id="compliance-2", domain="compliance", impact=0.99),
        candidate(public_id="immigration-1", domain="immigration", impact=0.7),
        candidate(public_id="company-1", domain="company", impact=0.7),
        candidate(public_id="tax-1", domain="tax", impact=0.7),
        candidate(public_id="property-1", domain="property", impact=0.7),
    ]
    selected = select_diverse([score_candidate(item) for item in candidates], limit=5)
    assert {item.candidate.domain for item in selected} == {
        "immigration",
        "company",
        "tax",
        "property",
        "compliance",
    }


def test_composer_emits_quiet_partial_and_deterministic_packet() -> None:
    config = ComposerConfig(
        required_system_ids=("intel-lake", "regulatory-watcher"),
        editor_version="editor.v1",
        ruleset_version="rules.v1",
    )
    cutoff = datetime(2026, 7, 17, 22, 15, tzinfo=timezone.utc)
    first = compose_edition(
        candidates=(),
        collector_runs=(collector_run("intel-lake"),),
        cutoff=cutoff,
        expected_current_revision=4,
        expected_breaking_revision=3,
        config=config,
    )
    second = compose_edition(
        candidates=(),
        collector_runs=(collector_run("intel-lake"),),
        cutoff=cutoff,
        expected_current_revision=4,
        expected_breaking_revision=3,
        config=config,
    )
    assert first == second
    assert first.edition_kind == "quiet"
    assert first.coverage_state == "partial"
    assert first.coverage_gaps == ("regulatory-watcher",)


def test_composer_rejects_unqualified_breaking() -> None:
    with pytest.raises(ValueError, match="not eligible"):
        compose_breaking(
            score_candidate(candidate(severity="medium")),
            expected_breaking_revision=1,
        )
