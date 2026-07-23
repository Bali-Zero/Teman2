"""E33 Second Home — runtime forbidden-claim guard.

Single source of pattern truth for claims that MUST NOT appear in generated
answers about the E33 Second Home visa vertical. Patterns are derived from
the E33 fact registry (``research/secondhome/e33-fact-registry.json`` v1.0.0,
branch ``backend-rag-e33-fact-registry`` pending merge): facts whose notes
say FORBIDDEN (BSI sharia equivalence, split deposits, ITAP-after-3-years)
plus the legacy error list (``USD 1,500/month`` superseded figure, ``IDR
2,000,000`` 1000x fee error, "LPS fully covers the deposit", "approval
guaranteed", "automatic KITAP", "E33 permits local work", any-bank
placement, ``5-10 years`` first-grant phrasing).

Wiring: ``guard_e33_answer`` is called once in
``backend/services/rag/agentic/orchestrator_core.py`` (``process_query_core``,
right before the final ``return result``) — the single finalization point of
the ReAct-generated answer path. It is log-only and non-blocking: violations
are logged and a safe fallback note is appended; the answer is never
rewritten or suppressed. Cached answers (FAQ/semantic) are pre-vetted and
intentionally not re-checked; KG fast-path answers are covered by the static
surface tests in
``backend/tests/services/visa_check/test_e33_forbidden_claims.py``.

The module is stdlib-only on purpose: importing it can never create import
cycles or I/O, so it is safe to call on the hot path.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Registry fact ids live in research/secondhome/e33-fact-registry.json.
# Legacy errors are not registry facts; they use this sentinel ref.
LEGACY_ERROR_REF = "legacy_error_list"

# Context gate: patterns flagged ``requires_e33_context`` only fire when the
# text is actually about the E33 / Second Home vertical, so unrelated answers
# mentioning e.g. "USD 1,500" are not flagged.
_E33_CONTEXT_RE = re.compile(
    r"\bE33[A-Z]?\b|second[- ]home|rumah\s+kedua|silver\s+hair",
    re.IGNORECASE,
)

E33_SAFE_FALLBACK_NOTE = (
    "Note: some details of the E33 Second Home visa are still pending written "
    "confirmation from the Indonesian immigration authority (Ditjen Imigrasi) "
    "and the state-owned banks. Please verify specific figures and conditions "
    "with the Bali Zero team before making any decision."
)


@dataclass(frozen=True)
class ForbiddenPattern:
    """A claim that must never be stated about the E33 vertical."""

    pattern_id: str
    regex: re.Pattern[str]
    description: str
    registry_ref: str
    requires_e33_context: bool = True


@dataclass(frozen=True)
class ClaimViolation:
    """One forbidden-claim match inside a generated answer."""

    pattern_id: str
    description: str
    matched_text: str
    start: int
    end: int
    registry_ref: str = field(default=LEGACY_ERROR_REF)


# Negation guard: fixed-width lookbehinds so that CORRECT cautionary phrasing
# ("does NOT authorize employment", "approval is not guaranteed", "LPS does not
# fully cover") is not flagged. Heuristic by design — the guard is log-only.
_NEG = r"(?<!not\s)(?<!never\s)(?<!cannot\s)(?<!can't\s)(?<!doesn't\s)"


def _p(
    pattern_id: str, raw: str, description: str, registry_ref: str, *, ctx: bool = True
) -> ForbiddenPattern:
    return ForbiddenPattern(
        pattern_id=pattern_id,
        regex=re.compile(raw, re.IGNORECASE),
        description=description,
        registry_ref=registry_ref,
        requires_e33_context=ctx,
    )


E33_FORBIDDEN_PATTERNS: tuple[ForbiddenPattern, ...] = (
    _p(
        "e33f_superseded_income_usd1500",
        r"\bUSD\s*1[.,]?500\b",
        "USD 1,500/month is the SUPERSEDED pre-2024 E33F figure; current is USD 3,000/month",
        "e33f_requirements",
    ),
    _p(
        "second_home_any_bank",
        r"\bany\s+(?:Indonesian\s+)?bank\b",
        "Deposit must be at a state-owned (BUMN) Indonesian bank, not 'any bank'",
        "e33_base_deposit_amount",
    ),
    _p(
        "e33_itap_kitap_automatic_promise",
        r"\bautomatic(?:ally)?\b(?!\s+included)[^.\n]{0,25}\b(?:KITAP|ITAP)\b"
        r"|\b(?:KITAP|ITAP)\b[^.\n]{0,40}\bautomatic(?:ally)?\b(?!\s+included)"
        r"|\bafter\s+3\s+years\b[^.\n]{0,50}\b(?:eligible|convert\w*|automatic\w*)\b[^.\n]{0,30}\b(?:KITAP|ITAP)\b",
        "ITAP/KITAP conversion after 3 years is pending confirmation — never promise it",
        "itap_after_3y_criteria",
    ),
    _p(
        "e33_permits_local_work",
        rf"\bE33[A-Z]?\b[^.\n]{{0,60}}\b{_NEG}(?<!residence\s)(?<!stay\s)(?:allows?|permits?|authoriz\w*|entitle\w*)\b[^.\n]{{0,40}}\b(?:work|employment)\b"
        rf"|\b{_NEG}work(?:ing)?\s+(?:legally\s+)?(?:in\s+Indonesia\s+)?on\s+(?:the\s+|an\s+)?E33",
        "Base E33 is a pure residence permit — it does NOT authorize local employment",
        "e33_not_work_visa",
        ctx=False,
    ),
    _p(
        "bsi_sharia_equivalence",
        r"\b(?:BSI|Bank\s+Syariah\s+Indonesia)\b[^.\n]{0,80}\b(?:qualif\w*|accept\w*|state[- ]owned|BUMN|equivalent|counts?\s+as)\b",
        "BSI (sharia) placement as qualifying state-bank deposit is unconfirmed — forbidden to claim",
        "bsi_sharia_accepted",
    ),
    _p(
        "split_deposit_accepted",
        r"\bsplit\b[^.\n]{0,40}\bdeposit\b|\bdeposit\b(?:(?!not|never|cannot|can't)[^.\n]){0,40}\bsplit\b"
        r"|\bmultiple\s+(?:BUMN\s+|state[- ]owned\s+)?banks\b[^.\n]{0,50}\bdeposit\b",
        "Splitting the USD 130,000 deposit across multiple banks is unconfirmed — forbidden to claim",
        "split_deposit_accepted",
    ),
    _p(
        "lps_full_coverage",
        rf"\bLPS\b[^.\n]{{0,60}}\b{_NEG}(?:full(?:y)?|100\s*%|entire(?:ly)?|whole)\b"
        rf"|\b{_NEG}(?:full(?:y)?|100\s*%|entire(?:ly)?)\b[^.\n]{{0,40}}\b(?:covered|guaranteed|insured)\b[^.\n]{{0,30}}\b(?:by\s+)?LPS\b",
        "LPS deposit insurance has a cap — never claim it fully covers the E33 deposit",
        "usd_deposit_rates_and_lps_cap_confirmation",
    ),
    _p(
        "approval_guaranteed",
        rf"\b(?:approval|approved|application|visa)\b[^.\n]{{0,30}}\b(?:is\s+|are\s+)?{_NEG}guaranteed\b"
        rf"|\b{_NEG}guaranteed\s+(?:approval|visa)\b",
        "Visa approval is never guaranteed",
        LEGACY_ERROR_REF,
    ),
    _p(
        "idr_2m_fee_error",
        r"\bIDR\s*2[.,]?000[.,]?000\b",
        "IDR 2,000,000 is the 1000x legacy fee error for the E33 vertical",
        LEGACY_ERROR_REF,
    ),
    _p(
        "second_home_first_grant_5_10_years",
        r"\b5\s*[-–]\s*10\s*years?\b",
        "Base E33 first grant is up to 5 years; '5-10 years' mixes in other first-grant categories",
        "e33_first_grant_duration",
    ),
)


def check_e33_claims(text: str) -> list[ClaimViolation]:
    """Flag registry-forbidden E33 claims in ``text``.

    Deterministic regex scan, no I/O. Patterns that require E33 context are
    skipped when the text does not mention the E33 / Second Home vertical.
    """
    if not text:
        return []
    has_context = bool(_E33_CONTEXT_RE.search(text))
    violations: list[ClaimViolation] = []
    for pattern in E33_FORBIDDEN_PATTERNS:
        if pattern.requires_e33_context and not has_context:
            continue
        for match in pattern.regex.finditer(text):
            violations.append(
                ClaimViolation(
                    pattern_id=pattern.pattern_id,
                    description=pattern.description,
                    matched_text=match.group(0),
                    start=match.start(),
                    end=match.end(),
                    registry_ref=pattern.registry_ref,
                )
            )
    return violations


def guard_e33_answer(answer: str) -> str:
    """Log E33 forbidden-claim violations and append a safe fallback note.

    Non-blocking by contract: never raises, never rewrites or suppresses the
    answer. Returns the original answer unchanged when no violation is found.
    """
    try:
        violations = check_e33_claims(answer)
    except Exception:  # pragma: no cover - defensive; guard must never break the hot path
        logger.exception("[E33Guard] check failed — returning answer unguarded")
        return answer
    if not violations:
        return answer
    logger.warning(
        "[E33Guard] %d forbidden E33 claim(s) in generated answer: %s",
        len(violations),
        [(v.pattern_id, v.matched_text[:80]) for v in violations],
    )
    return answer.rstrip() + "\n\n" + E33_SAFE_FALLBACK_NOTE
