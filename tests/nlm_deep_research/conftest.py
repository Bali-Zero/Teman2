"""Shared fixtures for NLM Deep Research Pipeline tests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

import pytest

from apps.evaluator.nlm_deep_research.source_management import (
    LifecycleStage,
    Source,
    SourceDates,
    SourceDedup,
    SourceFlags,
    SourceScores,
    SourceType,
    SVSClassification,
)
from apps.evaluator.nlm_deep_research.circuit_breaker import (
    CBName,
    CBState,
    CircuitBreaker,
    CircuitBreakerRegistry,
    CB_NLM_FAILURE_THRESHOLD,
    CB_NLM_TIMEOUT_HOURS,
    CB_SOURCE_FAILURE_THRESHOLD,
    CB_SOURCE_TIMEOUT_HOURS,
    CB_INTEGRATION_FAILURE_THRESHOLD,
    CB_INTEGRATION_TIMEOUT_HOURS,
)
from apps.evaluator.nlm_deep_research.claim_extractor import ClaimRecord


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 3, 28, 10, 0, 0, tzinfo=timezone.utc)


def days_ago(n: int) -> datetime:
    """Return a timezone-aware datetime n days before NOW."""
    return NOW - timedelta(days=n)


# ---------------------------------------------------------------------------
# Source factory
# ---------------------------------------------------------------------------


def make_source(
    source_id: str = "SRC-001",
    stage: LifecycleStage = LifecycleStage.ACTIVE,
    category: str = "canonical",
    source_type: SourceType = SourceType.REGULATION,
    title: str = "Test Source",
    url: str | None = "https://example.com/test",
    language: str = "id",
    tier: int = 2,
    tier_label: str = "T2",
    published: datetime | None = None,
    ingested: datetime | None = None,
    last_confirmed_valid: datetime | None = None,
    claims: list[str] | None = None,
    times_cited: int = 0,
    pinned: bool = False,
    enforcement_divergence: bool = False,
    url_hash: str | None = None,
) -> Source:
    """Factory to create Source instances with sensible defaults."""
    if published is None:
        published = days_ago(10)
    if ingested is None:
        ingested = days_ago(9)

    return Source(
        nlm_source_id=source_id,
        stage=stage,
        category=category,
        source_type=source_type,
        title=title,
        url=url,
        language=language,
        tier=tier,
        tier_label=tier_label,
        dates=SourceDates(
            published=published,
            ingested=ingested,
            last_confirmed_valid=last_confirmed_valid,
        ),
        scores=SourceScores(times_cited=times_cited),
        claims=claims or [],
        dedup=SourceDedup(url_hash=url_hash),
        flags=SourceFlags(
            pinned=pinned,
            enforcement_divergence=enforcement_divergence,
        ),
    )


# ---------------------------------------------------------------------------
# Circuit breaker factory
# ---------------------------------------------------------------------------


def make_cb(
    name: CBName = CBName.CB_NLM,
    state: CBState = CBState.CLOSED,
    failure_count: int = 0,
    opened_at: str | None = None,
) -> CircuitBreaker:
    """Factory for CircuitBreaker instances."""
    thresholds = {
        CBName.CB_NLM: (CB_NLM_FAILURE_THRESHOLD, CB_NLM_TIMEOUT_HOURS),
        CBName.CB_SOURCE: (CB_SOURCE_FAILURE_THRESHOLD, CB_SOURCE_TIMEOUT_HOURS),
        CBName.CB_INTEGRATION: (CB_INTEGRATION_FAILURE_THRESHOLD, CB_INTEGRATION_TIMEOUT_HOURS),
    }
    ft, th = thresholds[name]
    return CircuitBreaker(
        name=name,
        failure_threshold=ft,
        timeout_hours=th,
        state=state,
        failure_count=failure_count,
        opened_at=opened_at,
    )


# ---------------------------------------------------------------------------
# Claim factory
# ---------------------------------------------------------------------------


def make_claim(
    claim_id: str = "NB2-test0001",
    claim_text: str = "Test claim text exceeding fifty characters for extraction filtering",
    category: str = "LEGAL_CHANGE",
    confidence_score: float = 0.80,
    source_ids: list[str] | None = None,
) -> ClaimRecord:
    """Factory for ClaimRecord instances."""
    return ClaimRecord(
        claim_id=claim_id,
        claim_text=claim_text,
        category=category,
        confidence_class="VERIFIED" if confidence_score >= 0.75 else "PROVISIONAL",
        confidence_score=confidence_score,
        source_ids=source_ids or ["SRC-001"],
        extracted=NOW.isoformat(),
    )


# ---------------------------------------------------------------------------
# Pipeline state factory
# ---------------------------------------------------------------------------


def make_pipeline_state(
    version: int = 1,
    consecutive_failures: int = 0,
    weekly_api_calls: int = 5,
    current_time_wita: str = "2026-03-28T01:30:00+08:00",
    previous_claims_count: int = 10,
    claims_before_consolidation: int = 100,
    claims_after_consolidation: int = 99,
) -> dict:
    """Factory for pipeline_state dicts consumed by invariants."""
    return {
        "schema_version": version,
        "version": version,
        "consecutive_failures": consecutive_failures,
        "weekly_api_calls": weekly_api_calls,
        "current_time_wita": current_time_wita,
        "previous_claims_count": previous_claims_count,
        "claims_before_consolidation": claims_before_consolidation,
        "claims_after_consolidation": claims_after_consolidation,
    }


# ---------------------------------------------------------------------------
# Sources dict factory (for invariants)
# ---------------------------------------------------------------------------


def make_sources_dict(
    active: int = 10,
    quarantine: int = 2,
    archive: int = 3,
    master_digests: int = 5,
    denied_urls: list[str] | None = None,
) -> dict:
    """Create a dict of sources in the format expected by invariants."""
    sources = {}
    idx = 0
    for i in range(active):
        sid = f"SRC-A-{idx:03d}"
        sources[sid] = {
            "status": "ACTIVE",
            "url": f"https://imigrasi.go.id/page-{idx}",
            "source_type": "MASTER_DIGEST" if i < master_digests else "REGULATION",
        }
        idx += 1
    for i in range(quarantine):
        sid = f"SRC-Q-{idx:03d}"
        sources[sid] = {
            "status": "QUARANTINE",
            "url": f"https://kemenkumham.go.id/page-{idx}",
            "source_type": "REGULATION",
        }
        idx += 1
    for i in range(archive):
        sid = f"SRC-R-{idx:03d}"
        sources[sid] = {
            "status": "ARCHIVE",
            "url": f"https://archive.example.com/page-{idx}",
            "source_type": "NEWS",
        }
        idx += 1

    if denied_urls:
        for j, url in enumerate(denied_urls):
            sid = f"SRC-D-{idx:03d}"
            sources[sid] = {
                "status": "ACTIVE",
                "url": url,
                "source_type": "NEWS",
            }
            idx += 1

    return sources


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def now():
    """Fixed reference time for deterministic tests."""
    return NOW


@pytest.fixture
def sample_source(now):
    """A single well-formed Source."""
    return make_source(published=days_ago(10))


@pytest.fixture
def active_sources():
    """List of 5 active sources with varying properties."""
    return [
        make_source(
            source_id=f"SRC-{i:03d}",
            tier=i,
            tier_label=f"T{i}",
            published=days_ago(i * 10),
            claims=[f"claim-{i}"] if i < 3 else [],
            times_cited=i,
        )
        for i in range(5)
    ]


@pytest.fixture
def fresh_registry(tmp_path):
    """CircuitBreakerRegistry backed by a temporary state file."""
    state_path = tmp_path / "pipeline_state.json"
    return CircuitBreakerRegistry(state_path=state_path)


@pytest.fixture
def claims_file(tmp_path) -> Path:
    """Temporary JSONL claims file."""
    return tmp_path / "claims.jsonl"


@pytest.fixture
def handoff_dir(tmp_path) -> Path:
    """Temporary handoff directory."""
    d = tmp_path / "handoff"
    d.mkdir()
    return d
