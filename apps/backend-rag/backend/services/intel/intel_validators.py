"""
Intel 3-tier validators (decision #3).

Tier 1 (regex_schema) — hard gate, 0.3 score contribution.
Tier 2 (citation_check) — retry-aware HTTP HEAD check, 0.4 contribution.
Tier 3 (kg_crossref) — soft signal via kg_auto_expansion, 0.3 contribution.

Final status:
  score >= 0.6 and not needs_review → 'valid'
  0.3 ≤ score < 0.6                 → 'needs_review'
  score < 0.3                       → 'rejected'

Non-whitelisted source domains force needs_review=True regardless of score,
which prevents 'valid' status (score >= 0.6 threshold requires not needs_review).

Golden Rule #4: httpx (async) only — never requests.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

from backend.services.intel.intel_source_whitelist import is_whitelisted

logger = logging.getLogger(__name__)


_URL_RE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(T.*)?$")

_MIN_BODY_LEN = 50

TIER_REGEX_SCORE = 0.3
TIER_CITATION_SCORE = 0.4
TIER_KG_SCORE = 0.3

VALID_THRESHOLD = 0.6
REVIEW_THRESHOLD = 0.3


# Golden Rule #10: module-level lazy singleton AsyncClient (citation_check
# fallback when no client is injected). Lifespan-closed via
# close_intel_validators_client() in app_factory.lifespan().
_module_client: httpx.AsyncClient | None = None


def _get_module_client() -> httpx.AsyncClient:
    global _module_client  # noqa: PLW0603 — singleton by design
    if _module_client is None or _module_client.is_closed:
        _module_client = httpx.AsyncClient(follow_redirects=True, timeout=10.0)
    return _module_client


async def close_intel_validators_client() -> None:
    """Release the module-level AsyncClient (lifespan shutdown hook)."""
    global _module_client  # noqa: PLW0603
    if _module_client is not None and not _module_client.is_closed:
        await _module_client.aclose()
    _module_client = None


# ── Dataclasses ─────────────────────────────────────────────────────────


@dataclass
class IntelDoc:
    """Input document for validation."""

    title: str
    url: str
    published_at: str
    body_text: str
    source_domain: str


@dataclass
class TierResult:
    """Per-tier validation output."""

    tier: str
    result: str  # pass | fail | soft_fail | skip
    score: float
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Final aggregated validation output."""

    status: str  # valid | needs_review | rejected
    score: float
    tiers: list[TierResult]
    needs_review: bool = False


class CitationResult(str, Enum):
    PASS = "pass"
    DEFINITIVE_FAIL = "definitive_fail"
    SOFT_FAIL = "soft_fail"


# ── Tier 1 ──────────────────────────────────────────────────────────────


def regex_schema(doc: IntelDoc) -> bool:
    """Tier 1: syntactic validation. Hard gate.

    Checks: non-empty title, valid URL, ISO date, body >= 50 chars.
    """
    if not doc.title:
        return False
    if not _URL_RE.match(doc.url):
        return False
    if not _ISO_DATE_RE.match(doc.published_at):
        return False
    if len(doc.body_text) < _MIN_BODY_LEN:
        return False
    return True


# ── Tier 2 ──────────────────────────────────────────────────────────────

_DEFINITIVE_CODES = frozenset({400, 401, 403, 404, 410})


async def citation_check(
    url: str,
    *,
    http_client: Any | None = None,
    max_retries: int = 3,
    backoff_base: float = 0.5,
) -> CitationResult:
    """Tier 2: HTTP HEAD to confirm URL resolves.

    2xx → PASS.
    4xx in {400, 401, 403, 404, 410} → DEFINITIVE_FAIL (no retry).
    5xx / timeout → retry with exponential backoff, finally SOFT_FAIL.

    Accepts injected http_client for testing. If None, creates one and closes it.
    """
    # Golden Rule #10: when no client is injected, reuse the module-level
    # singleton so concurrent citation checks don't each open a new TCP
    # connection. Lifespan closes the singleton on shutdown.
    client: Any = http_client if http_client is not None else _get_module_client()
    for attempt in range(max_retries):
        try:
            r = await client.head(url)
            if 200 <= r.status_code < 300:
                return CitationResult.PASS
            if r.status_code in _DEFINITIVE_CODES:
                return CitationResult.DEFINITIVE_FAIL
            # 5xx or unexpected — retry
            logger.info(
                "citation_check %s: status=%s, retry %d/%d",
                url, r.status_code, attempt + 1, max_retries,
            )
        except httpx.TimeoutException:
            logger.info(
                "citation_check %s: timeout, retry %d/%d",
                url, attempt + 1, max_retries,
            )
        except httpx.HTTPError as exc:
            logger.info(
                "citation_check %s: %s, retry %d/%d",
                url, exc, attempt + 1, max_retries,
            )

        if attempt + 1 < max_retries:
            await asyncio.sleep(backoff_base * (2 ** attempt))

    return CitationResult.SOFT_FAIL


# ── Tier 3 ──────────────────────────────────────────────────────────────


async def kg_crossref(text: str, *, kg: Any) -> list[dict[str, Any]]:
    """Tier 3: ask kg_auto_expansion.find_entities for any KG match.

    Never raises — timeout/errors return empty list (soft signal).
    Timeout hardcoded at 3s.
    """
    try:
        entities = await asyncio.wait_for(kg.find_entities(text), timeout=3.0)
        return list(entities) if entities else []
    except (asyncio.TimeoutError, Exception) as exc:  # noqa: BLE001 — soft signal
        logger.info("kg_crossref failed (non-fatal): %s", exc)
        return []


# ── Orchestrator ────────────────────────────────────────────────────────


async def validate(
    doc: IntelDoc,
    *,
    http_client: Any | None = None,
    kg: Any | None = None,
    max_retries: int = 3,
) -> ValidationResult:
    """Run all three tiers in sequence, short-circuit on regex fail.

    Returns ValidationResult with status, score, and per-tier breakdown.
    """
    tiers: list[TierResult] = []
    score = 0.0

    # Tier 1 — hard gate
    if regex_schema(doc):
        tiers.append(TierResult("regex", "pass", TIER_REGEX_SCORE))
        score += TIER_REGEX_SCORE
    else:
        tiers.append(TierResult("regex", "fail", 0.0, {"reason": "schema"}))
        return ValidationResult(status="rejected", score=0.0, tiers=tiers)

    # Tier 2 — citation check
    if http_client is not None:
        cr = await citation_check(doc.url, http_client=http_client, max_retries=max_retries)
        if cr == CitationResult.PASS:
            tiers.append(TierResult("citation", "pass", TIER_CITATION_SCORE))
            score += TIER_CITATION_SCORE
        elif cr == CitationResult.DEFINITIVE_FAIL:
            tiers.append(TierResult("citation", "fail", 0.0))
        else:
            tiers.append(TierResult("citation", "soft_fail", 0.0))
    else:
        tiers.append(TierResult("citation", "skip", 0.0))

    # Tier 3 — KG cross-reference
    if kg is not None:
        entities = await kg_crossref(doc.body_text, kg=kg)
        if entities:
            tiers.append(
                TierResult(
                    "kg_crossref",
                    "pass",
                    TIER_KG_SCORE,
                    {"entities": entities[:5]},
                )
            )
            score += TIER_KG_SCORE
        else:
            tiers.append(TierResult("kg_crossref", "skip", 0.0))
    else:
        tiers.append(TierResult("kg_crossref", "skip", 0.0))

    # Whitelist override — non-whitelisted sources always need human review
    needs_review = not is_whitelisted(doc.url)

    if score >= VALID_THRESHOLD and not needs_review:
        status = "valid"
    elif score >= REVIEW_THRESHOLD:
        status = "needs_review"
    else:
        status = "rejected"

    return ValidationResult(
        status=status,
        score=round(score, 2),
        tiers=tiers,
        needs_review=needs_review,
    )


__all__ = [
    "IntelDoc",
    "ValidationResult",
    "TierResult",
    "CitationResult",
    "regex_schema",
    "citation_check",
    "kg_crossref",
    "validate",
]
