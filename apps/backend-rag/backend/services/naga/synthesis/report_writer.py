"""Tier-appropriate Markdown report writer for Naga research pipeline.

Generates flash / deep / exhaustive reports from verified ``ClaimRecord``
objects, evidence maps, and identified gaps.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from backend.core.claims.models import ClaimRecord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_report(
    query: str,
    tier: str,  # flash / deep / exhaustive
    claims: list[ClaimRecord],
    evidence_map: dict,
    sources_count: int = 0,
    duration_ms: int = 0,
    gaps: list[str] | None = None,
) -> str:
    """Generate a Markdown report appropriate for *tier*.

    Parameters
    ----------
    query:
        The original research question.
    tier:
        One of ``flash``, ``deep``, ``exhaustive``.
    claims:
        Verified / provisional / low-confidence claims from the pipeline.
    evidence_map:
        Arbitrary dict that may contain ``data_points`` and ``gaps`` keys.
    sources_count:
        Total sources consulted.
    duration_ms:
        Wall-clock duration of the research run in milliseconds.
    gaps:
        Explicit gap descriptions passed by the caller.  These are merged
        with any ``gaps`` key found inside *evidence_map*.
    """
    merged_gaps = _merge_gaps(gaps, evidence_map)

    if tier == "flash":
        return _flash_report(query, claims, merged_gaps)
    if tier == "exhaustive":
        return _exhaustive_report(
            query, claims, evidence_map, merged_gaps, sources_count, duration_ms
        )
    # default to deep
    return _deep_report(
        query, claims, evidence_map, merged_gaps, sources_count, duration_ms
    )


# ---------------------------------------------------------------------------
# Tier builders
# ---------------------------------------------------------------------------


def _flash_report(
    query: str,
    claims: list[ClaimRecord],
    gaps: list[str],
) -> str:
    """1-3 paragraph flash report."""
    timestamp = _now_iso()
    lines: list[str] = [f"**{query}** — {timestamp}", ""]

    trustworthy = [
        c for c in claims if c.confidence_class in ("VERIFIED", "PROVISIONAL")
    ]
    low_claims = [c for c in claims if c.confidence_class == "LOW"]

    if not claims:
        lines.append("No verifiable claims were found for this query.")
        return "\n".join(lines)

    if trustworthy:
        for claim in trustworthy:
            lines.append(f"- {claim.claim_text}")
        lines.append("")

    if low_claims:
        lines.append(
            f"**Contested / low-confidence ({len(low_claims)}):** "
            + "; ".join(c.claim_text for c in low_claims)
        )

    if gaps:
        lines.append("")
        lines.append("**Gaps:** " + "; ".join(gaps))

    return "\n".join(lines)


def _deep_report(
    query: str,
    claims: list[ClaimRecord],
    _evidence_map: dict,
    gaps: list[str],
    sources_count: int,
    duration_ms: int,
) -> str:
    """Structured deep report with executive summary and evidence bar.

    *_evidence_map* is consumed by the exhaustive tier; deep ignores it
    but accepts it to keep the call signature uniform.
    """
    sections: list[str] = []

    # Title + metadata
    sections.append(f"# Research Report: {query}")
    sections.append("")
    sections.append(
        f"*Generated {_now_iso()} — {sources_count} sources — {duration_ms} ms*"
    )
    sections.append("")

    # Evidence bar
    sections.append(_evidence_status_bar(claims))
    sections.append("")

    # Executive summary
    sections.append("## Executive Summary")
    sections.append("")
    trustworthy = [
        c for c in claims if c.confidence_class in ("VERIFIED", "PROVISIONAL")
    ]
    if not trustworthy:
        sections.append("No verifiable claims were found for this query.")
    else:
        for idx, claim in enumerate(trustworthy, 1):
            sections.append(_format_claim(claim, idx))
    sections.append("")

    # Contradictions
    sections.append("## Contradictions and Uncertainty")
    sections.append("")
    contested = [c for c in claims if c.confidence_class == "LOW"]
    if contested:
        for claim in contested:
            sections.append(
                f"- **{claim.claim_text}** — confidence {claim.confidence_score:.2f}. "
                "Resolution: seek additional primary sources."
            )
    else:
        sections.append("No contradictions detected.")
    sections.append("")

    # Research limitations
    sections.append("## Research Limitations")
    sections.append("")
    if gaps:
        for gap in gaps:
            sections.append(f"- {gap}")
    else:
        sections.append("No significant gaps identified.")

    return "\n".join(sections)


def _exhaustive_report(
    query: str,
    claims: list[ClaimRecord],
    evidence_map: dict,
    gaps: list[str],
    sources_count: int,
    duration_ms: int,
) -> str:
    """Full exhaustive report — deep + data points + low-confidence appendix."""
    # Start with everything from deep
    base = _deep_report(query, claims, evidence_map, gaps, sources_count, duration_ms)
    extra: list[str] = [""]

    # Key data points
    data_points: list[dict] = evidence_map.get("data_points", [])
    extra.append("## Key Data Points")
    extra.append("")
    if data_points:
        for dp in data_points:
            label = dp.get("label", "—")
            value = dp.get("value", "—")
            extra.append(f"| {label} | {value} |")
    else:
        extra.append("No structured data points extracted.")
    extra.append("")

    # Appendix: low-confidence claims
    low_claims = [c for c in claims if c.confidence_class == "LOW"]
    extra.append("## Appendix: Low-Confidence Claims")
    extra.append("")
    if low_claims:
        for idx, claim in enumerate(low_claims, 1):
            extra.append(_format_claim(claim, idx))
    else:
        extra.append("None.")

    return base + "\n".join(extra)


# ---------------------------------------------------------------------------
# Helpers (exported for testing)
# ---------------------------------------------------------------------------


def _evidence_status_bar(claims: list[ClaimRecord]) -> str:
    """Return a one-line status bar: ``VERIFIED: N | PROVISIONAL: N | LOW: N``."""
    counts: dict[str, int] = {"VERIFIED": 0, "PROVISIONAL": 0, "LOW": 0}
    for claim in claims:
        key = claim.confidence_class if claim.confidence_class in counts else "LOW"
        counts[key] += 1
    return (
        f"VERIFIED: {counts['VERIFIED']} | "
        f"PROVISIONAL: {counts['PROVISIONAL']} | "
        f"LOW: {counts['LOW']}"
    )


def _format_claim(claim: ClaimRecord, index: int) -> str:
    """Format a single claim line with verification level and source count."""
    n_sources = len(claim.source_ids)
    source_label = f"{n_sources} source{'s' if n_sources != 1 else ''}"
    parts = [
        f"{index}. [{claim.confidence_class}]",
        claim.claim_text,
        f"({source_label}",
    ]
    if claim.extracted:
        parts[-1] += f", valid_as_of {claim.extracted}"
    parts[-1] += ")"
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """UTC timestamp in ISO-8601 format (date only)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _merge_gaps(explicit: list[str] | None, evidence_map: dict) -> list[str]:
    """Merge explicit gaps with those found in evidence_map['gaps']."""
    result: list[str] = list(explicit or [])
    map_gaps = evidence_map.get("gaps", [])
    if isinstance(map_gaps, list):
        for gap in map_gaps:
            if gap not in result:
                result.append(gap)
    return result
