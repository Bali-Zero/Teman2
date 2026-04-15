"""Unit tests for backend.services.experience.service.

Covers the service-layer wrapper around cell-core Genome: record + query
Pydantic contract, outcome normalisation, graceful degradation when the
Genome dependency is missing, idempotency.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.services.experience.models import (
    TrajectoryQuery,
    TrajectoryRecord,
)
from backend.services.experience.service import ExperienceService


@pytest.fixture
def service(tmp_path):
    return ExperienceService(db_path=str(tmp_path / "experience.db"))


# ─── Pydantic contract ──────────────────────────────────────────────


def test_trajectory_record_validates_outcome():
    with pytest.raises(ValidationError):
        TrajectoryRecord(
            trajectory_id="t1",
            cell="c1",
            outcome="maybe",  # invalid
            procedure="x",
        )


def test_trajectory_record_accepts_tags_default_empty():
    rec = TrajectoryRecord(
        trajectory_id="t1", cell="c1", outcome="success", procedure="x",
    )
    assert rec.tags == []


def test_trajectory_query_limit_has_upper_bound():
    # Sanity: forbid unbounded queries from the API layer.
    with pytest.raises(ValidationError):
        TrajectoryQuery(query="x", limit=10_000)


@pytest.mark.parametrize("bad_tag", ['weird"quote', 'back\\slash', "with space", "semi;colon"])
def test_trajectory_record_rejects_non_slug_tags(bad_tag):
    """Post-review 2026-04-15: tag slug validation at the boundary prevents
    silent LIKE-pattern misses when a tag contains JSON-unsafe characters."""
    with pytest.raises(ValidationError):
        TrajectoryRecord(
            trajectory_id="t", cell="c", outcome="success",
            procedure="p", tags=["ok", bad_tag],
        )


def test_trajectory_query_rejects_non_slug_tag_filter():
    with pytest.raises(ValidationError):
        TrajectoryQuery(query="x", tag='weird"quote')


@pytest.mark.parametrize("good_tag", ["ig", "wa", "visa_expired", "kbli-70209", "ABC123"])
def test_trajectory_record_accepts_slug_tags(good_tag):
    rec = TrajectoryRecord(
        trajectory_id="t", cell="c", outcome="success",
        procedure="p", tags=[good_tag],
    )
    assert good_tag in rec.tags


# ─── record() ───────────────────────────────────────────────────────


def test_record_stores_trajectory(service):
    rec = TrajectoryRecord(
        trajectory_id="run_a", cell="curator", outcome="success",
        procedure="published ig carousel",
        tokens=1200, duration_ms=7000, tags=["ig"],
    )
    result = service.record(rec)
    assert result["action"] == "inserted"
    assert result["trajectory_id"] == "run_a"


def test_record_is_idempotent(service):
    rec = TrajectoryRecord(
        trajectory_id="dup", cell="c1", outcome="success", procedure="x",
    )
    first = service.record(rec)
    second = service.record(rec)
    assert first["action"] == "inserted"
    assert second["action"] == "updated"


def test_record_failure_stored_as_personal_scope(service):
    rec = TrajectoryRecord(
        trajectory_id="bad", cell="c1", outcome="failure",
        procedure="DLP blocked publish",
    )
    service.record(rec)
    stats = service.stats(cell="c1")
    assert stats["by_outcome"]["failure"] == 1


# ─── query() ────────────────────────────────────────────────────────


def test_query_returns_matching_trajectory(service):
    service.record(TrajectoryRecord(
        trajectory_id="t1", cell="c1", outcome="success",
        procedure="DLP scan detected PII in draft caption.",
    ))
    service.record(TrajectoryRecord(
        trajectory_id="t2", cell="c1", outcome="success",
        procedure="Selected morning photo from GARUDA folder.",
    ))
    results = service.query(TrajectoryQuery(query="DLP"))
    assert len(results) == 1
    assert results[0].trajectory_id == "t1"
    assert results[0].outcome == "success"


def test_query_filters_by_outcome(service):
    service.record(TrajectoryRecord(
        trajectory_id="ok", cell="c1", outcome="success", procedure="published prose",
    ))
    service.record(TrajectoryRecord(
        trajectory_id="ko", cell="c1", outcome="failure", procedure="published prose",
    ))
    failures = service.query(TrajectoryQuery(query="published", outcome="failure"))
    assert len(failures) == 1
    assert failures[0].trajectory_id == "ko"


def test_query_filters_by_cell(service):
    service.record(TrajectoryRecord(
        trajectory_id="a", cell="cell_a", outcome="success", procedure="shared prose",
    ))
    service.record(TrajectoryRecord(
        trajectory_id="b", cell="cell_b", outcome="success", procedure="shared prose",
    ))
    only_a = service.query(TrajectoryQuery(query="shared", cell="cell_a"))
    assert len(only_a) == 1
    assert only_a[0].cell == "cell_a"


def test_query_filters_by_tag(service):
    service.record(TrajectoryRecord(
        trajectory_id="ig1", cell="c", outcome="success",
        procedure="caption prose", tags=["ig"],
    ))
    service.record(TrajectoryRecord(
        trajectory_id="wa1", cell="c", outcome="success",
        procedure="caption prose", tags=["wa"],
    ))
    ig_only = service.query(TrajectoryQuery(query="caption", tag="ig"))
    assert len(ig_only) == 1
    assert ig_only[0].trajectory_id == "ig1"


def test_query_limit_is_respected(service):
    for i in range(5):
        service.record(TrajectoryRecord(
            trajectory_id=f"t{i}", cell="c", outcome="success",
            procedure=f"sample prose iteration",
        ))
    results = service.query(TrajectoryQuery(query="prose", limit=2))
    assert len(results) <= 2


# ─── stats() ────────────────────────────────────────────────────────


def test_stats_aggregates_by_outcome(service):
    for i, oc in enumerate(("success", "success", "failure", "partial")):
        service.record(TrajectoryRecord(
            trajectory_id=f"t_{i}_{oc}", cell="c", outcome=oc, procedure="p",
        ))
    stats = service.stats(cell="c")
    assert stats["total"] == 4
    assert stats["by_outcome"]["success"] == 2
    assert stats["by_outcome"]["failure"] == 1
    assert stats["by_outcome"]["partial"] == 1


# ─── Graceful degradation ───────────────────────────────────────────


def test_service_reports_unavailable_when_genome_missing(tmp_path, monkeypatch):
    """If cell_core.genome.Genome import fails, service.is_available is False
    and record/query return a degraded response instead of crashing."""
    import backend.services.experience.service as svc_mod

    monkeypatch.setattr(svc_mod, "_GENOME_AVAILABLE", False)
    monkeypatch.setattr(svc_mod, "Genome", None)

    svc = ExperienceService(db_path=str(tmp_path / "x.db"))
    assert svc.is_available is False

    rec = TrajectoryRecord(
        trajectory_id="t", cell="c", outcome="success", procedure="p",
    )
    result = svc.record(rec)
    assert result["action"] == "skipped"
    assert result["reason"] == "genome_unavailable"

    results = svc.query(TrajectoryQuery(query="x"))
    assert results == []
