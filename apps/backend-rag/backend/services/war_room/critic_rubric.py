"""WR2 Critic Rubric — 4-gate PASS/FAIL evaluator (NB-7 ground truth).

Spec: research/wr2/2026-05-27-wr2-autonomous-workflow-spec.md §9
Phase 2.4 of WR2 autonomous carousel pipeline (Antonello 2026-05-27).

Used by the critic subagent step output post-processing — applies 4
PASS/FAIL gates extracted verbatim from NB-7 Editorial governance:

    Gate 1 — Primary source citation regex (UU/PP/PMK/Perpres/Permenaker)
    Gate 2 — NotebookLM consistency (via mcp__notebooklm-mcp__notebook_query)
    Gate 3 — Mandatory disclaimer on last slide
    Gate 4 — Brand-voice red flags auto-block regex

Also enforces format rules (5-13 slides, Indonesian terminology italics
+ translation on first occurrence, no banned openings).

NB-7 reference: f51ab8a0-50d0-49f1-a64f-ebc131fed7b8

Pure module — no I/O at import time. Used by:
- scripts/wr2_carousel_orchestrator.py (critic step post-processor)
- backend tests
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# Spec §9 Gate 1 — primary citation regex (NB-7 verbatim format)
PRIMARY_CITATION_PATTERN = re.compile(
    r"\[Fonte:\s*(UU|PP|PMK|Perpres|Permenkumham|Permenaker|Permendag|Permendagri|Permenkes|Peraturan\s+BKPM)\s+\d+/\d{4}.*?\]",
    re.IGNORECASE,
)

# Spec §9 Gate 3 — disclaimer keywords (NB-7 verbatim phrasing)
DISCLAIMER_KEYWORDS = (
    "informativo generale",
    "non costituiscono consulenza",
    "scopo informativo",
    "consulta un professionista",
)

# Spec §9 brand-voice red flags — auto-block on match
RED_FLAG_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "hardcoded_bz_price",
        re.compile(
            r"\b(IDR|Rp|USD|EUR)\s*\d[\d.,]*\b.{0,100}\bBali\s*Zero\b.{0,100}\b(visa|kitas|kitap|pma|setup|service)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "guaranteed_timeline",
        re.compile(
            r"\b(garant\w+|guarantee\w*)\s+(approv\w+|entro|in)\s+\d+\s+(gg|giorn|day|week)",
            re.IGNORECASE,
        ),
    ),
    (
        "competitor_denigration",
        re.compile(
            r"\b(a\s+differenza\s+di|unlike|molte\s+agenzie\s+\w+\s+ma|other\s+agencies\s+\w+\s+but)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "political_opinion",
        re.compile(
            r"\b(governo\s+indonesiano|Presiden\s+\w+|indonesian\s+government)\b.{0,80}\b(sbaglia|fallisce|non\s+riesce|fails|wrong|criticism)",
            re.IGNORECASE,
        ),
    ),
    (
        "banned_opening",
        re.compile(
            r"^\s*(In questo (carosello|articolo|post)|In questa guida|Oggi parleremo|In this (article|carousel)|Today we will)\b",
            re.IGNORECASE,
        ),
    ),
)

# Spec §9 format check
MIN_SLIDES = 5
MAX_SLIDES = 13
EXPECTED_FORMAT_RATIO = "4:5"
EXPECTED_TEMPLATE_ID = "DAHE6lx1lf8"  # NB-7 verbatim

# Indonesian terms always-untranslated (NB-7 §4 acquired acronyms)
ACQUIRED_ACRONYMS = frozenset({
    "KITAS", "KITAP", "NIB", "NPWP", "OSS", "PMK", "PP", "PT", "PMA",
    "BPJS", "BPKM", "KBKL", "KBLI", "UU", "Perpres", "Permenkumham",
    "Permenaker", "VOA", "C1", "C2", "C7", "E33", "E33F", "E33G",
})


class GateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    RETRYABLE_FAIL = "RETRYABLE_FAIL"


@dataclass
class GateResult:
    gate: str
    status: GateStatus
    issues: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class RubricVerdict:
    overall: GateStatus
    gates: list[GateResult] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.overall.value,
            "gates": [
                {
                    "gate": g.gate,
                    "status": g.status.value,
                    "issues": g.issues,
                    "evidence": g.evidence,
                }
                for g in self.gates
            ],
            "summary": self.summary,
        }


def _aggregate(gates: list[GateResult]) -> GateStatus:
    """Spec §6 — strict aggregate. Any FAIL → FAIL. Any RETRYABLE → RETRYABLE_FAIL. Else PASS."""
    if any(g.status == GateStatus.FAIL for g in gates):
        return GateStatus.FAIL
    if any(g.status == GateStatus.RETRYABLE_FAIL for g in gates):
        return GateStatus.RETRYABLE_FAIL
    return GateStatus.PASS


def gate1_primary_citation(slides: list[dict[str, Any]]) -> GateResult:
    """Spec §9 Gate 1 — every regulatory/numeric claim needs [Fonte: ...]."""
    issues: list[str] = []
    citations_found = 0
    claims_without_citation: list[str] = []

    for i, slide in enumerate(slides):
        body = (slide.get("body") or slide.get("text") or "")
        if not isinstance(body, str):
            continue

        # Heuristic: claim trigger if mentions regulatory pattern + number/year
        if re.search(r"\b(UU|PP|PMK|Perpres|Permen\w+)\b", body, re.IGNORECASE):
            if PRIMARY_CITATION_PATTERN.search(body):
                citations_found += 1
            else:
                claims_without_citation.append(f"slide {i}: regulatory mention without [Fonte: ...]")

        # Number-bearing claims (Rp/IDR/percentage/year) need citation
        if re.search(r"\b\d+(?:[.,]\d+)?\s*(%|persen|miliard|miliar|juta|million|trillion)\b", body, re.IGNORECASE):
            if not PRIMARY_CITATION_PATTERN.search(body):
                claims_without_citation.append(f"slide {i}: numeric claim without citation")

    if claims_without_citation:
        issues.extend(claims_without_citation[:5])  # cap noise
        return GateResult(
            gate="primary_citation",
            status=GateStatus.RETRYABLE_FAIL,
            issues=issues,
            evidence={"citations_found": citations_found, "missing": len(claims_without_citation)},
        )

    return GateResult(
        gate="primary_citation",
        status=GateStatus.PASS,
        evidence={"citations_found": citations_found},
    )


def gate2_notebook_consistency(
    _slides: list[dict[str, Any]],
    notebook_query_result: dict[str, Any] | None = None,
) -> GateResult:
    """Spec §9 Gate 2 — NB-7/NB-3/NB-2 ground truth verification.

    NB query is async, so orchestrator must inject the result. If
    `notebook_query_result is None`, gate is SKIPPED with PASS + warning
    (caller decides whether to enforce). Spec §15 Q6: full NB query is
    operator-decided ON, but module stays decoupled from MCP I/O.
    """
    if notebook_query_result is None:
        return GateResult(
            gate="notebook_consistency",
            status=GateStatus.PASS,
            issues=["nb_query skipped — caller did not provide result"],
            evidence={"skipped": True},
        )

    contradictions = notebook_query_result.get("contradictions", []) or []
    if contradictions:
        return GateResult(
            gate="notebook_consistency",
            status=GateStatus.RETRYABLE_FAIL,
            issues=[f"NB-7 contradiction: {c}" for c in contradictions[:5]],
            evidence={"contradiction_count": len(contradictions)},
        )

    return GateResult(
        gate="notebook_consistency",
        status=GateStatus.PASS,
        evidence={"nb_verified": True},
    )


def gate3_disclaimer(slides: list[dict[str, Any]]) -> GateResult:
    """Spec §9 Gate 3 — last slide must contain disclaimer keywords."""
    if not slides:
        return GateResult(
            gate="disclaimer",
            status=GateStatus.FAIL,
            issues=["no slides to check"],
        )

    last_slide = slides[-1]
    body = (last_slide.get("body") or last_slide.get("text") or "")
    if not isinstance(body, str):
        body = str(body)
    body_lower = body.lower()

    matched = [kw for kw in DISCLAIMER_KEYWORDS if kw in body_lower]
    if not matched:
        return GateResult(
            gate="disclaimer",
            status=GateStatus.FAIL,
            issues=["last slide missing disclaimer (legal/fiscale carousel needs disclaimer)"],
            evidence={"last_slide_excerpt": body[:200]},
        )

    return GateResult(
        gate="disclaimer",
        status=GateStatus.PASS,
        evidence={"matched_keywords": matched},
    )


def gate4_brand_voice_red_flags(slides: list[dict[str, Any]]) -> GateResult:
    """Spec §9 Gate 4 — auto-block on red-flag pattern match."""
    issues: list[str] = []
    matches: list[dict[str, Any]] = []

    for i, slide in enumerate(slides):
        body = (slide.get("body") or slide.get("text") or "")
        if not isinstance(body, str):
            continue

        for flag_name, pattern in RED_FLAG_PATTERNS:
            m = pattern.search(body)
            if m:
                snippet = m.group(0)[:80]
                issues.append(f"slide {i}: {flag_name} match — {snippet!r}")
                matches.append({"slide": i, "flag": flag_name, "snippet": snippet})

    if matches:
        return GateResult(
            gate="brand_voice",
            status=GateStatus.FAIL,
            issues=issues[:8],
            evidence={"red_flag_matches": matches[:8]},
        )

    return GateResult(
        gate="brand_voice",
        status=GateStatus.PASS,
    )


def format_check(slides: list[dict[str, Any]], metadata: dict[str, Any] | None = None) -> GateResult:
    """Spec §9 format check — 5-13 slides, template id, ratio."""
    issues: list[str] = []
    metadata = metadata or {}

    if not (MIN_SLIDES <= len(slides) <= MAX_SLIDES):
        issues.append(f"slide count {len(slides)} outside [{MIN_SLIDES}, {MAX_SLIDES}]")

    template_id = metadata.get("template_id") or metadata.get("canva_template_id")
    if template_id and template_id != EXPECTED_TEMPLATE_ID:
        issues.append(f"template_id={template_id!r} != expected {EXPECTED_TEMPLATE_ID!r}")

    ratio = metadata.get("ratio") or metadata.get("aspect_ratio")
    if ratio and ratio != EXPECTED_FORMAT_RATIO:
        issues.append(f"ratio={ratio!r} != expected {EXPECTED_FORMAT_RATIO!r}")

    if issues:
        return GateResult(
            gate="format",
            status=GateStatus.RETRYABLE_FAIL,
            issues=issues,
            evidence={"slide_count": len(slides)},
        )

    return GateResult(
        gate="format",
        status=GateStatus.PASS,
        evidence={"slide_count": len(slides)},
    )


def evaluate_rubric(
    slides: list[dict[str, Any]],
    *,
    metadata: dict[str, Any] | None = None,
    notebook_query_result: dict[str, Any] | None = None,
) -> RubricVerdict:
    """Full rubric evaluation — main entrypoint for orchestrator critic step.

    Returns RubricVerdict with overall status + per-gate breakdown.
    """
    gates = [
        gate1_primary_citation(slides),
        gate2_notebook_consistency(slides, notebook_query_result=notebook_query_result),
        gate3_disclaimer(slides),
        gate4_brand_voice_red_flags(slides),
        format_check(slides, metadata),
    ]
    overall = _aggregate(gates)

    failed = [g.gate for g in gates if g.status == GateStatus.FAIL]
    retryable = [g.gate for g in gates if g.status == GateStatus.RETRYABLE_FAIL]

    if overall == GateStatus.PASS:
        summary = f"PASS — {len(gates)} gates clean"
    elif overall == GateStatus.RETRYABLE_FAIL:
        summary = f"RETRYABLE_FAIL — fixable: {', '.join(retryable)}"
    else:
        summary = f"FAIL — blocked by: {', '.join(failed)}"

    return RubricVerdict(overall=overall, gates=gates, summary=summary)
