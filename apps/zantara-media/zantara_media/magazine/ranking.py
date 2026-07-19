"""Deterministic evidence resolution, ranking, and domain-diverse selection."""

from __future__ import annotations

from dataclasses import dataclass

from zantara_media.magazine.adapters import StoryCandidate
from zantara_media.magazine.contracts import EvidenceRefV1, ScoreComponentsV1


@dataclass(frozen=True, slots=True)
class IndependenceResolution:
    independent_root_count: int
    collapsed_groups: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    candidate: StoryCandidate
    score_components: ScoreComponentsV1
    total: float
    breaking_eligible: bool
    breaking_reason: str


def resolve_independence(evidence_refs: tuple[EvidenceRefV1, ...]) -> IndependenceResolution:
    eligible = tuple(
        item
        for item in evidence_refs
        if item.counts_toward_breaking
        and item.root_resolution_status == "resolved"
        and item.independence_verdict == "independent"
    )
    parent = list(range(len(eligible)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for left, left_item in enumerate(eligible):
        left_lineage = {left_item.root_source_id, *left_item.upstream_root_source_ids}
        for right in range(left + 1, len(eligible)):
            right_item = eligible[right]
            right_lineage = {right_item.root_source_id, *right_item.upstream_root_source_ids}
            same_feed = (
                left_item.syndication_group_fingerprint
                == right_item.syndication_group_fingerprint
            )
            if same_feed or left_lineage & right_lineage:
                left_root, right_root = find(left), find(right)
                if left_root != right_root:
                    parent[right_root] = left_root
    grouped: dict[int, list[str]] = {}
    for index, item in enumerate(eligible):
        grouped.setdefault(find(index), []).append(item.root_source_id)
    groups = tuple(sorted(tuple(sorted(set(items))) for items in grouped.values()))
    return IndependenceResolution(len(groups), groups)


def _official_primary(items: tuple[EvidenceRefV1, ...]) -> bool:
    return any(
        item.source_type == "official"
        and item.primary_document_status == "verified"
        and item.root_resolution_status == "resolved"
        and item.independence_verdict == "independent"
        and item.counts_toward_breaking
        and (item.canonical_url is not None or item.document_citation is not None)
        for item in items
    )


def _breaking_verdict(candidate: StoryCandidate) -> tuple[bool, str]:
    if candidate.severity not in {"high", "critical"}:
        return False, "severity-below-high"
    evidence_by_id = {item.evidence_id: item for item in candidate.evidence_refs}
    for claim in candidate.claims:
        if claim.claim_kind == "analysis":
            continue
        supporting = tuple(
            evidence_by_id[item]
            for item in claim.evidence_ids
            if item in evidence_by_id
        )
        if claim.claim_id in candidate.legal_effect_claim_ids and not _official_primary(supporting):
            return False, "legal-effect-requires-official-primary"
        if claim.breaking_gate == "official-primary":
            if not _official_primary(supporting):
                return False, "official-primary-unresolved"
        elif claim.breaking_gate == "two-independent-root-sources":
            if resolve_independence(supporting).independent_root_count < 2:
                return False, "insufficient-independent-roots"
        else:
            return False, "missing-breaking-gate"
    if not candidate.claims:
        return False, "no-material-claims"
    has_official = any(
        _official_primary(tuple(
            evidence_by_id[item]
            for item in claim.evidence_ids
            if item in evidence_by_id
        ))
        for claim in candidate.claims
        if claim.claim_kind != "analysis"
    )
    return True, "official-primary" if has_official else "two-independent-root-sources"


def score_candidate(candidate: StoryCandidate) -> ScoredCandidate:
    resolved = resolve_independence(candidate.evidence_refs)
    official = _official_primary(candidate.evidence_refs)
    evidence_score = 1.0 if official else min(1.0, resolved.independent_root_count / 2)
    editorial = min(1.0, 0.2 * sum(bool(value) for value in (
        candidate.title,
        candidate.deck,
        candidate.summary,
        candidate.why_it_matters,
        candidate.slug,
    )))
    components = ScoreComponentsV1(
        editorial=editorial,
        impact=candidate.operational_impact,
        freshness=candidate.novelty,
        evidence=evidence_score,
        diversity=0.5,
    )
    total = round(
        components.editorial * 0.2
        + components.impact * 0.3
        + components.freshness * 0.2
        + components.evidence * 0.25
        + components.diversity * 0.05,
        8,
    )
    eligible, reason = _breaking_verdict(candidate)
    return ScoredCandidate(candidate, components, total, eligible, reason)


def select_diverse(
    candidates: list[ScoredCandidate] | tuple[ScoredCandidate, ...],
    *,
    limit: int,
) -> tuple[ScoredCandidate, ...]:
    """Take one best story per core domain before filling remaining slots."""

    ordered = sorted(candidates, key=lambda item: (-item.total, item.candidate.public_id))
    core_domains = ("immigration", "company", "tax", "property", "compliance")
    selected: list[ScoredCandidate] = []
    selected_ids: set[str] = set()
    for domain in core_domains:
        match = next((item for item in ordered if item.candidate.domain == domain), None)
        if match is not None and len(selected) < limit:
            selected.append(match)
            selected_ids.add(match.candidate.public_id)
    for item in ordered:
        if len(selected) >= limit:
            break
        if item.candidate.public_id not in selected_ids:
            selected.append(item)
            selected_ids.add(item.candidate.public_id)
    return tuple(selected)
