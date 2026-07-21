"""Fail-closed, PII-free Visa Oracle SHADOW gate evidence collector.

This module measures only the two gates that can be derived from the
``visa_decisions`` audit log: G-a (volume/breadth) and G-c (grounding).
G-b (the independently graded 20-persona replay) and G-d (the recorded live
rollback drill) are always reported as unmeasured here.  Consequently this
collector can never, by itself, declare ENFORCE ready.

No applicant facts, Match tokens, decision IDs, or request fingerprints are
returned.  The collector reads the PII-free audit projection and emits only
counts, dates, categories, and product codes.
"""

from __future__ import annotations

import json
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta, timezone
from typing import Any

import asyncpg
from pydantic import ValidationError

from backend.services.visa_check.match_tree import Purpose
from backend.services.visa_engine.enums import DecisionState
from backend.services.visa_engine.models import RulePackPayload, SourceRecord

MIN_DISTINCT_REQUESTS = 1_000
MIN_CONSECUTIVE_DAYS = 7
MIN_DISTINCT_VISA_CODES = 30
REQUIRED_INTERVIEW_CATEGORIES = frozenset(
    purpose.value for purpose in Purpose if purpose is not Purpose.OTHER
)

_VALID_CATEGORIES = frozenset(purpose.value for purpose in Purpose)
_CITATIONLESS_ABSTENTION_STATES = frozenset({DecisionState.NEEDS_INPUT.value})


def _json_array(value: object) -> list[object] | None:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, list) else None


def _json_object(value: object) -> dict[str, Any] | None:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None


def _uuid(value: object) -> uuid.UUID | None:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _utc(value: object) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    return value.astimezone(timezone.utc)


def _longest_consecutive_day_streak(days: set[date]) -> int:
    longest = 0
    current = 0
    previous: date | None = None
    for day in sorted(days):
        current = current + 1 if previous is not None and day - previous == timedelta(days=1) else 1
        longest = max(longest, current)
        previous = day
    return longest


def _period_contains(source: SourceRecord, moment: datetime, *, recorded: bool) -> bool:
    period = source.recorded_period if recorded else source.legal_period
    return period.from_ <= moment and (period.to is None or moment < period.to)


def _gate(status: bool, **details: object) -> dict[str, object]:
    return {"status": "GREEN" if status else "RED", "green": status, **details}


def evaluate_shadow_evidence(
    rows: Sequence[Mapping[str, object]],
    packs: Mapping[uuid.UUID, RulePackPayload],
    *,
    window_start: datetime,
    window_end: datetime,
    invalid_pack_count: int = 0,
) -> dict[str, object]:
    """Aggregate safe audit rows into the objective gate report.

    ``rows`` must contain only migration-255's PII-free projection.  Any
    missing/malformed field is counted and makes the relevant gate red.
    """

    if window_start.tzinfo is None or window_end.tzinfo is None:
        raise ValueError("window_start/window_end must be timezone-aware")
    if window_start >= window_end:
        raise ValueError("window_start must be before window_end")

    window_duration = window_end.astimezone(timezone.utc) - window_start.astimezone(timezone.utc)
    fingerprints: set[bytes] = set()
    categories: Counter[str] = Counter()
    candidate_codes: set[str] = set()
    active_days: set[date] = set()
    missing_request_fingerprints = 0
    missing_or_invalid_categories = 0
    malformed_candidate_summaries = 0
    invalid_candidate_bindings = 0
    missing_ruleset_activations = 0
    missing_rule_pack_digests = 0
    malformed_grounding_summaries = 0
    decisions_without_citations = 0
    ungrounded_claims = 0
    malformed_citations = 0
    citations_not_claimed = 0
    claimed_sources_not_cited = 0
    unresolved_or_invalid_sources = 0

    source_indexes: dict[uuid.UUID, dict[uuid.UUID, SourceRecord]] = {
        pack_id: {source.source_record_id: source for source in pack.source_records}
        for pack_id, pack in packs.items()
    }
    product_indexes: dict[uuid.UUID, set[tuple[uuid.UUID, str]]] = {
        pack_id: {
            (product.product_version_id, str(product.product_code)) for product in pack.products
        }
        for pack_id, pack in packs.items()
    }

    for row in rows:
        pack_id = _uuid(row.get("rule_pack_id"))
        if _uuid(row.get("ruleset_activation_id")) is None:
            missing_ruleset_activations += 1

        rule_pack_sha256 = row.get("rule_pack_sha256")
        if isinstance(rule_pack_sha256, memoryview):
            rule_pack_sha256 = rule_pack_sha256.tobytes()
        elif isinstance(rule_pack_sha256, bytearray):
            rule_pack_sha256 = bytes(rule_pack_sha256)
        if not isinstance(rule_pack_sha256, bytes) or len(rule_pack_sha256) != 32:
            missing_rule_pack_digests += 1

        fingerprint = row.get("request_fingerprint")
        if isinstance(fingerprint, memoryview):
            fingerprint = fingerprint.tobytes()
        elif isinstance(fingerprint, bytearray):
            fingerprint = bytes(fingerprint)
        if isinstance(fingerprint, bytes) and len(fingerprint) == 32:
            fingerprints.add(fingerprint)
        else:
            missing_request_fingerprints += 1

        category = row.get("request_category")
        if isinstance(category, str) and category in _VALID_CATEGORIES:
            categories[category] += 1
        else:
            missing_or_invalid_categories += 1

        evaluated_at = _utc(row.get("evaluated_at"))
        if evaluated_at is not None:
            active_days.add(evaluated_at.date())

        candidate_summary = _json_array(row.get("candidate_summary"))
        if candidate_summary is None:
            malformed_candidate_summaries += 1
        else:
            candidate_shape_ok = True
            for candidate in candidate_summary:
                if not isinstance(candidate, dict):
                    candidate_shape_ok = False
                    continue
                product_code = candidate.get("product_code")
                product_version_id = _uuid(candidate.get("product_version_id"))
                product_binding = (product_version_id, product_code)
                if (
                    product_version_id is not None
                    and isinstance(product_code, str)
                    and product_binding in product_indexes.get(pack_id, set())
                ):
                    candidate_codes.add(product_code)
                else:
                    candidate_shape_ok = False
                    invalid_candidate_bindings += 1
            if not candidate_shape_ok:
                malformed_candidate_summaries += 1

        citations = _json_array(row.get("citations"))
        citation_refs: set[uuid.UUID] = set()
        if citations is None:
            malformed_citations += 1
        else:
            citation_shape_ok = True
            for citation in citations:
                if not isinstance(citation, dict):
                    citation_shape_ok = False
                    continue
                ref = _uuid(citation.get("source_record_id"))
                if ref is None:
                    citation_shape_ok = False
                else:
                    citation_refs.add(ref)
            if not citation_shape_ok:
                malformed_citations += 1

        grounding_summary = _json_array(row.get("grounding_summary"))
        claimed_refs: set[uuid.UUID] = set()
        citationless_abstention = False
        if grounding_summary is None or not grounding_summary:
            malformed_grounding_summaries += 1
            ungrounded_claims += 1
        else:
            grounding_shape_ok = True
            verdict_claim_count = 0
            row_verdict = row.get("verdict")
            for claim in grounding_summary:
                if not isinstance(claim, dict):
                    grounding_shape_ok = False
                    ungrounded_claims += 1
                    continue
                claim_kind = claim.get("claim_kind")
                claim_code = claim.get("claim_code")
                raw_refs = claim.get("source_record_ids")
                if not isinstance(claim_kind, str) or not isinstance(claim_code, str):
                    grounding_shape_ok = False
                if claim_kind == "VERDICT":
                    verdict_claim_count += 1
                    if claim_code != row_verdict:
                        grounding_shape_ok = False
                if not isinstance(raw_refs, list):
                    grounding_shape_ok = False
                    ungrounded_claims += 1
                    continue
                refs = {_uuid(value) for value in raw_refs}
                claim_is_citationless_abstention = (
                    claim_kind == "VERDICT"
                    and claim_code in _CITATIONLESS_ABSTENTION_STATES
                    and claim_code == row_verdict
                    and raw_refs == []
                )
                if claim_is_citationless_abstention:
                    citationless_abstention = True
                elif None in refs or not refs:
                    grounding_shape_ok = False
                    ungrounded_claims += 1
                claimed_refs.update(ref for ref in refs if ref is not None)
            if verdict_claim_count != 1:
                grounding_shape_ok = False
            if not grounding_shape_ok:
                malformed_grounding_summaries += 1

        if not citation_refs and not citationless_abstention:
            decisions_without_citations += 1

        citations_not_claimed += len(citation_refs - claimed_refs)
        claimed_sources_not_cited += len(claimed_refs - citation_refs)

        effective_at = _utc(row.get("effective_at"))
        observed_at = _utc(row.get("observed_at"))
        sources = source_indexes.get(pack_id, {}) if pack_id is not None else {}
        for ref in citation_refs:
            source = sources.get(ref)
            if (
                source is None
                or source.status.value != "VERIFIED"
                or not source.canonical_url.strip()
                or effective_at is None
                or observed_at is None
                or not _period_contains(source, effective_at, recorded=False)
                or not _period_contains(source, observed_at, recorded=True)
            ):
                unresolved_or_invalid_sources += 1

    longest_streak = _longest_consecutive_day_streak(active_days)
    missing_categories = sorted(REQUIRED_INTERVIEW_CATEGORIES - categories.keys())
    gate_a_green = (
        window_duration >= timedelta(days=MIN_CONSECUTIVE_DAYS)
        and len(fingerprints) >= MIN_DISTINCT_REQUESTS
        and longest_streak >= MIN_CONSECUTIVE_DAYS
        and not missing_categories
        and len(candidate_codes) >= MIN_DISTINCT_VISA_CODES
        and missing_request_fingerprints == 0
        and missing_or_invalid_categories == 0
        and malformed_candidate_summaries == 0
        and invalid_candidate_bindings == 0
    )
    gate_c_green = (
        bool(rows)
        and invalid_pack_count == 0
        and missing_ruleset_activations == 0
        and missing_rule_pack_digests == 0
        and malformed_grounding_summaries == 0
        and decisions_without_citations == 0
        and ungrounded_claims == 0
        and malformed_citations == 0
        and citations_not_claimed == 0
        and claimed_sources_not_cited == 0
        and unresolved_or_invalid_sources == 0
    )

    gate_a = _gate(
        gate_a_green,
        total_audit_rows=len(rows),
        window_duration_hours=window_duration.total_seconds() / 3600,
        minimum_window_duration_hours=MIN_CONSECUTIVE_DAYS * 24,
        distinct_requests=len(fingerprints),
        minimum_distinct_requests=MIN_DISTINCT_REQUESTS,
        duplicate_evaluations=max(0, len(rows) - len(fingerprints)),
        active_utc_days=len(active_days),
        longest_consecutive_utc_day_streak=longest_streak,
        minimum_consecutive_days=MIN_CONSECUTIVE_DAYS,
        category_counts=dict(sorted(categories.items())),
        missing_required_categories=missing_categories,
        required_categories=sorted(REQUIRED_INTERVIEW_CATEGORIES),
        distinct_visa_codes=len(candidate_codes),
        minimum_distinct_visa_codes=MIN_DISTINCT_VISA_CODES,
        visa_codes=sorted(candidate_codes),
        missing_request_fingerprints=missing_request_fingerprints,
        missing_or_invalid_categories=missing_or_invalid_categories,
        malformed_candidate_summaries=malformed_candidate_summaries,
        invalid_candidate_bindings=invalid_candidate_bindings,
    )
    gate_c = _gate(
        gate_c_green,
        invalid_rule_pack_payloads=invalid_pack_count,
        missing_ruleset_activations=missing_ruleset_activations,
        missing_rule_pack_digests=missing_rule_pack_digests,
        malformed_grounding_summaries=malformed_grounding_summaries,
        decisions_without_citations=decisions_without_citations,
        ungrounded_claims=ungrounded_claims,
        malformed_citations=malformed_citations,
        citations_not_claimed=citations_not_claimed,
        claimed_sources_not_cited=claimed_sources_not_cited,
        unresolved_or_invalid_sources=unresolved_or_invalid_sources,
    )

    return {
        "schema_version": "visa-shadow-evidence/1.0.0",
        "window": {
            "start": window_start.astimezone(timezone.utc).isoformat(),
            "end_exclusive": window_end.astimezone(timezone.utc).isoformat(),
        },
        "enforce_ready": False,
        "gate_status": "RED",
        "gates": {
            "G-a": gate_a,
            "G-b": {
                "status": "UNMEASURED",
                "green": False,
                "reason": "requires independent canonical 20-persona replay evidence",
            },
            "G-c": gate_c,
            "G-d": {
                "status": "UNMEASURED",
                "green": False,
                "reason": "requires a recorded live ENFORCE-to-OFF rollback drill",
            },
        },
        "blockers": [
            gate
            for gate, evidence in (("G-a", gate_a), ("G-c", gate_c))
            if evidence["green"] is False
        ]
        + ["G-b", "G-d"],
    }


async def collect_shadow_evidence(
    db_pool: asyncpg.Pool,
    *,
    window_start: datetime,
    window_end: datetime,
    environment: str = "PRODUCTION",
) -> dict[str, object]:
    """Read the SHADOW audit projection and return an aggregate gate report."""

    if window_start.tzinfo is None or window_end.tzinfo is None:
        raise ValueError("window_start/window_end must be timezone-aware")
    if window_start >= window_end:
        raise ValueError("window_start must be before window_end")

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                request_fingerprint,
                request_category,
                candidate_summary,
                grounding_summary,
                citations,
                verdict,
                rule_pack_id,
                ruleset_activation_id,
                rule_pack_sha256,
                effective_at,
                observed_at,
                evaluated_at
            FROM public.visa_decisions
            WHERE environment = $1
              AND engine_surface = 'MATCH'
              AND engine_mode = 'SHADOW'
              AND evaluated_at >= $2
              AND evaluated_at < $3
            ORDER BY evaluated_at
            """,
            environment,
            window_start,
            window_end,
        )

        pack_ids = sorted(
            {pack_id for row in rows if (pack_id := _uuid(row["rule_pack_id"])) is not None},
            key=str,
        )
        pack_rows = (
            await conn.fetch(
                "SELECT id, payload FROM public.visa_rule_packs WHERE id = ANY($1::uuid[])",
                pack_ids,
            )
            if pack_ids
            else []
        )

    packs: dict[uuid.UUID, RulePackPayload] = {}
    invalid_pack_ids: set[uuid.UUID] = set(pack_ids)
    for row in pack_rows:
        row_id = _uuid(row["id"])
        if row_id is None:
            continue
        payload = _json_object(row["payload"])
        if payload is None:
            continue
        try:
            parsed = RulePackPayload.model_validate(payload)
        except ValidationError:
            continue
        packs[row_id] = parsed
        invalid_pack_ids.discard(row_id)

    return evaluate_shadow_evidence(
        rows,
        packs,
        window_start=window_start,
        window_end=window_end,
        invalid_pack_count=len(invalid_pack_ids),
    )


__all__ = [
    "MIN_CONSECUTIVE_DAYS",
    "MIN_DISTINCT_REQUESTS",
    "MIN_DISTINCT_VISA_CODES",
    "REQUIRED_INTERVIEW_CATEGORIES",
    "collect_shadow_evidence",
    "evaluate_shadow_evidence",
]
