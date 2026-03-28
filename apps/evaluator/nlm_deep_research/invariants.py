"""
NLM Deep Research Pipeline — Invariant Checks

10 critical invariants that guard the pipeline against drift, budget overrun,
data contamination, and silent failures. Each check returns a typed
InvariantResult so the caller can decide whether to halt, warn, or continue.

All checks use Python stdlib only (no external deps).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPECTED_STATE_VERSION: int = 1

MAX_ACTIVE_SOURCES: int = 70
MAX_QUARANTINE_SOURCES: int = 30
ILM_THRESHOLD: float = 0.05
MIN_MASTER_DIGEST_SOURCES: int = 4
MAX_CONSECUTIVE_FAILURES: int = 3
MAX_WEEKLY_API_CALLS: int = 40

# WITA = UTC+8
WITA_OFFSET = timezone(timedelta(hours=8))
PIPELINE_DEADLINE_HOUR: int = 2
PIPELINE_DEADLINE_MINUTE: int = 30

DOMAIN_DENYLIST: list[str] = [
    "tripadvisor.com",
    "expat.com/forum",
    "kaskus.co.id",
    "nomadicmatt.com",
    "reddit.com",
    "quora.com",
    "medium.com/@",
    "youtube.com",
    "tiktok.com",
    "pinterest.com",
    "booking.com",
    "agoda.com",
    "skyscanner.com",
    "lonelyplanet.com",
    "thepointsguy.com",
    "balizero.com",
]


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class InvariantSeverity(Enum):
    """How the pipeline should react to a failed invariant."""

    CRITICAL = "CRITICAL"  # Pipeline MUST halt
    WARNING = "WARNING"    # Log and continue
    INFO = "INFO"          # Informational


@dataclass(frozen=True)
class InvariantResult:
    """Outcome of a single invariant check."""

    invariant_id: str
    passed: bool
    severity: InvariantSeverity
    message: str
    current_value: Optional[float] = None
    threshold: Optional[float] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count_by_status(sources: dict, status: str) -> int:
    """Count sources whose ``status`` field matches *status* (case-insensitive).

    *sources* is expected to be ``{source_id: {…metadata…}, …}``.
    A source dict without a ``status`` key is silently skipped.
    """
    return sum(
        1
        for src in sources.values()
        if isinstance(src, dict) and src.get("status", "").upper() == status.upper()
    )


def _extract_urls(sources: dict) -> list[str]:
    """Return a flat list of every ``url`` value found in *sources*."""
    urls: list[str] = []
    for src in sources.values():
        if isinstance(src, dict):
            url = src.get("url", "")
            if url:
                urls.append(url)
    return urls


# ---------------------------------------------------------------------------
# Individual invariant checks
# ---------------------------------------------------------------------------

def check_active_count(sources: dict) -> InvariantResult:
    """INV_ACTIVE_COUNT: ACTIVE sources must be <= 70.

    Exceeding the limit risks hitting NLM notebook source caps and
    degrading retrieval quality through dilution.
    """
    count = _count_by_status(sources, "ACTIVE")
    passed = count <= MAX_ACTIVE_SOURCES
    return InvariantResult(
        invariant_id="INV_ACTIVE_COUNT",
        passed=passed,
        severity=InvariantSeverity.CRITICAL,
        message=(
            f"ACTIVE source count {count} within limit ({MAX_ACTIVE_SOURCES})"
            if passed
            else f"ACTIVE source count {count} exceeds limit ({MAX_ACTIVE_SOURCES})"
        ),
        current_value=float(count),
        threshold=float(MAX_ACTIVE_SOURCES),
    )


def check_quarantine_count(sources: dict) -> InvariantResult:
    """INV_QUARANTINE_COUNT: QUARANTINE sources must be <= 30.

    Too many quarantined sources indicates systemic quality issues
    in the ingestion pipeline.
    """
    count = _count_by_status(sources, "QUARANTINE")
    passed = count <= MAX_QUARANTINE_SOURCES
    return InvariantResult(
        invariant_id="INV_QUARANTINE_COUNT",
        passed=passed,
        severity=InvariantSeverity.WARNING,
        message=(
            f"QUARANTINE source count {count} within limit ({MAX_QUARANTINE_SOURCES})"
            if passed
            else f"QUARANTINE source count {count} exceeds limit ({MAX_QUARANTINE_SOURCES})"
        ),
        current_value=float(count),
        threshold=float(MAX_QUARANTINE_SOURCES),
    )


def check_ilm(claims_before: int, claims_after: int) -> InvariantResult:
    """INV_ILM: Information Loss Metric must be < 0.05 on any consolidation.

    ILM is defined as ``1 - (claims_after / claims_before)`` when
    *claims_before* > 0.  A value >= 0.05 means more than 5% of
    factual claims were lost during a source consolidation step.
    """
    if claims_before <= 0:
        return InvariantResult(
            invariant_id="INV_ILM",
            passed=True,
            severity=InvariantSeverity.INFO,
            message="No claims before consolidation; ILM check not applicable",
            current_value=0.0,
            threshold=ILM_THRESHOLD,
        )

    ilm = 1.0 - (claims_after / claims_before)
    passed = ilm < ILM_THRESHOLD
    return InvariantResult(
        invariant_id="INV_ILM",
        passed=passed,
        severity=InvariantSeverity.CRITICAL,
        message=(
            f"ILM {ilm:.4f} is below threshold ({ILM_THRESHOLD})"
            if passed
            else (
                f"ILM {ilm:.4f} exceeds threshold ({ILM_THRESHOLD}) — "
                f"{claims_before} claims before, {claims_after} after"
            )
        ),
        current_value=ilm,
        threshold=ILM_THRESHOLD,
    )


def check_no_balizero(sources: dict) -> InvariantResult:
    """INV_NO_BALIZERO: No source URL may contain any denied domain.

    Prevents self-referential content and low-quality UGC from
    polluting the research notebook.  Checks every URL against the
    full ``DOMAIN_DENYLIST`` (which includes balizero.com).
    """
    urls = _extract_urls(sources)
    violations: list[str] = []

    for url in urls:
        url_lower = url.lower()
        for denied in DOMAIN_DENYLIST:
            if denied in url_lower:
                violations.append(f"{url} (matched {denied})")
                break  # one match per URL is enough

    passed = len(violations) == 0
    return InvariantResult(
        invariant_id="INV_NO_BALIZERO",
        passed=passed,
        severity=InvariantSeverity.CRITICAL,
        message=(
            "No denied-domain URLs found in sources"
            if passed
            else f"Found {len(violations)} denied-domain URL(s): {'; '.join(violations[:5])}"
        ),
        current_value=float(len(violations)),
        threshold=0.0,
    )


def check_master_digest_count(sources: dict) -> InvariantResult:
    """INV_MASTER_DIGEST_COUNT: Master Digest sources must be >= 4.

    Master Digests are the backbone of each notebook — fewer than 4
    means the research base is dangerously thin.
    """
    count = sum(
        1
        for src in sources.values()
        if isinstance(src, dict) and src.get("source_type", "").upper() == "MASTER_DIGEST"
    )
    passed = count >= MIN_MASTER_DIGEST_SOURCES
    return InvariantResult(
        invariant_id="INV_MASTER_DIGEST_COUNT",
        passed=passed,
        severity=InvariantSeverity.CRITICAL,
        message=(
            f"Master Digest count {count} meets minimum ({MIN_MASTER_DIGEST_SOURCES})"
            if passed
            else (
                f"Master Digest count {count} below minimum ({MIN_MASTER_DIGEST_SOURCES}) — "
                "research base is too thin"
            )
        ),
        current_value=float(count),
        threshold=float(MIN_MASTER_DIGEST_SOURCES),
    )


def check_consecutive_failures(failure_count: int) -> InvariantResult:
    """INV_CONSECUTIVE_FAILURES: Consecutive NLM failures must be < 3.

    Three or more consecutive failures strongly suggest a systemic
    issue (auth expiry, API outage) rather than transient flakiness.
    """
    passed = failure_count < MAX_CONSECUTIVE_FAILURES
    return InvariantResult(
        invariant_id="INV_CONSECUTIVE_FAILURES",
        passed=passed,
        severity=InvariantSeverity.CRITICAL,
        message=(
            f"Consecutive failure count {failure_count} within limit ({MAX_CONSECUTIVE_FAILURES})"
            if passed
            else (
                f"Consecutive failure count {failure_count} reached limit "
                f"({MAX_CONSECUTIVE_FAILURES}) — likely systemic issue"
            )
        ),
        current_value=float(failure_count),
        threshold=float(MAX_CONSECUTIVE_FAILURES),
    )


def check_weekly_budget(calls_this_week: int) -> InvariantResult:
    """INV_WEEKLY_BUDGET: Weekly API calls must be <= 40.

    NLM API usage is metered.  Exceeding 40 calls/week risks
    unexpected cost spikes and potential rate-limiting.
    """
    passed = calls_this_week <= MAX_WEEKLY_API_CALLS
    return InvariantResult(
        invariant_id="INV_WEEKLY_BUDGET",
        passed=passed,
        severity=InvariantSeverity.WARNING,
        message=(
            f"Weekly API calls {calls_this_week} within budget ({MAX_WEEKLY_API_CALLS})"
            if passed
            else (
                f"Weekly API calls {calls_this_week} exceed budget "
                f"({MAX_WEEKLY_API_CALLS})"
            )
        ),
        current_value=float(calls_this_week),
        threshold=float(MAX_WEEKLY_API_CALLS),
    )


def check_pipeline_deadline(current_time_wita: str) -> InvariantResult:
    """INV_PIPELINE_DEADLINE: Pipeline must complete by 02:30 WITA.

    *current_time_wita* should be an ISO-8601 string (with or without
    timezone info).  If timezone-naive, it is assumed to be WITA (UTC+8).

    The pipeline runs in the early-morning maintenance window.
    Overrunning 02:30 risks colliding with other scheduled jobs
    (intel scraper at 03:00, backup at 03:00).
    """
    try:
        dt = datetime.fromisoformat(current_time_wita)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=WITA_OFFSET)
        else:
            dt = dt.astimezone(WITA_OFFSET)
    except (ValueError, TypeError) as exc:
        return InvariantResult(
            invariant_id="INV_PIPELINE_DEADLINE",
            passed=False,
            severity=InvariantSeverity.WARNING,
            message=f"Cannot parse time '{current_time_wita}': {exc}",
            current_value=None,
            threshold=float(PIPELINE_DEADLINE_HOUR * 60 + PIPELINE_DEADLINE_MINUTE),
        )

    current_minutes = dt.hour * 60 + dt.minute
    deadline_minutes = PIPELINE_DEADLINE_HOUR * 60 + PIPELINE_DEADLINE_MINUTE
    passed = current_minutes <= deadline_minutes
    return InvariantResult(
        invariant_id="INV_PIPELINE_DEADLINE",
        passed=passed,
        severity=InvariantSeverity.WARNING,
        message=(
            f"Pipeline time {dt.strftime('%H:%M')} WITA is before deadline "
            f"({PIPELINE_DEADLINE_HOUR:02d}:{PIPELINE_DEADLINE_MINUTE:02d})"
            if passed
            else (
                f"Pipeline time {dt.strftime('%H:%M')} WITA has overrun deadline "
                f"({PIPELINE_DEADLINE_HOUR:02d}:{PIPELINE_DEADLINE_MINUTE:02d})"
            )
        ),
        current_value=float(current_minutes),
        threshold=float(deadline_minutes),
    )


def check_state_version(version: int) -> InvariantResult:
    """INV_STATE_VERSION: state_file.version must match EXPECTED_STATE_VERSION.

    A version mismatch means the state file was produced by an
    incompatible pipeline version and should not be consumed.
    """
    passed = version == EXPECTED_STATE_VERSION
    return InvariantResult(
        invariant_id="INV_STATE_VERSION",
        passed=passed,
        severity=InvariantSeverity.CRITICAL,
        message=(
            f"State version {version} matches expected ({EXPECTED_STATE_VERSION})"
            if passed
            else (
                f"State version {version} does NOT match expected "
                f"({EXPECTED_STATE_VERSION}) — incompatible state file"
            )
        ),
        current_value=float(version),
        threshold=float(EXPECTED_STATE_VERSION),
    )


def check_claims_append_only(
    previous_count: int,
    current_count: int,
) -> InvariantResult:
    """INV_CLAIMS_APPEND_ONLY: Claims registry count must never decrease.

    The claims registry is append-only by design.  A decrease signals
    data corruption or an accidental truncation.
    """
    passed = current_count >= previous_count
    return InvariantResult(
        invariant_id="INV_CLAIMS_APPEND_ONLY",
        passed=passed,
        severity=InvariantSeverity.CRITICAL,
        message=(
            f"Claims count {current_count} >= previous {previous_count} (append-only OK)"
            if passed
            else (
                f"Claims count DECREASED from {previous_count} to {current_count} — "
                "append-only invariant violated"
            )
        ),
        current_value=float(current_count),
        threshold=float(previous_count),
    )


# ---------------------------------------------------------------------------
# Aggregate runner
# ---------------------------------------------------------------------------

def check_all_invariants(
    sources: dict,
    pipeline_state: dict,
    claims_count: int,
) -> list[InvariantResult]:
    """Run all 10 invariants and return their results.

    Parameters
    ----------
    sources:
        Dict of ``{source_id: {status, url, source_type, …}}``.
    pipeline_state:
        Dict with keys consumed by individual checks:
        - ``version`` (int): state file schema version
        - ``consecutive_failures`` (int): recent consecutive NLM call failures
        - ``weekly_api_calls`` (int): API calls made this ISO week
        - ``current_time_wita`` (str): ISO-8601 timestamp (current pipeline time)
        - ``previous_claims_count`` (int): claims count from the prior run
        - ``claims_before_consolidation`` (int): claims before latest merge
        - ``claims_after_consolidation`` (int): claims after latest merge
    claims_count:
        Current total claims in the registry.

    Returns
    -------
    list[InvariantResult]
        One result per invariant, in canonical order (INV_ACTIVE_COUNT first).
    """
    results: list[InvariantResult] = [
        check_active_count(sources),
        check_quarantine_count(sources),
        check_ilm(
            claims_before=pipeline_state.get("claims_before_consolidation", 0),
            claims_after=pipeline_state.get("claims_after_consolidation", 0),
        ),
        check_no_balizero(sources),
        check_master_digest_count(sources),
        check_consecutive_failures(
            failure_count=pipeline_state.get("consecutive_failures", 0),
        ),
        check_weekly_budget(
            calls_this_week=pipeline_state.get("weekly_api_calls", 0),
        ),
        check_pipeline_deadline(
            current_time_wita=pipeline_state.get(
                "current_time_wita",
                datetime.now(tz=WITA_OFFSET).isoformat(),
            ),
        ),
        check_state_version(
            version=pipeline_state.get("schema_version", pipeline_state.get("version", -1)),
        ),
        check_claims_append_only(
            previous_count=pipeline_state.get("previous_claims_count", 0),
            current_count=claims_count,
        ),
    ]

    # Log summary
    failed = [r for r in results if not r.passed]
    critical_failures = [
        r for r in failed if r.severity == InvariantSeverity.CRITICAL
    ]

    if critical_failures:
        logger.error(
            "Invariant check: %d CRITICAL failure(s) — pipeline MUST halt: %s",
            len(critical_failures),
            ", ".join(r.invariant_id for r in critical_failures),
        )
    elif failed:
        logger.warning(
            "Invariant check: %d warning(s): %s",
            len(failed),
            ", ".join(r.invariant_id for r in failed),
        )
    else:
        logger.info("Invariant check: all 10 invariants passed")

    return results
