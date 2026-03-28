"""Tests for handoff.py — TRS, handoff generation, schema validation, save."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.evaluator.nlm_deep_research.handoff import (
    MAX_HANDOFF_FINDINGS,
    MODE_ENRICH,
    MODE_IGNORE,
    MODE_PRIORITIZE,
    SCHEMA_VERSION,
    TRS_CANDIDATE,
    TRS_HANDOFF,
    calculate_trs,
    classify_trs,
    determine_integration_mode,
    generate_handoff,
    save_handoff,
    select_handoff_topics,
    validate_handoff_schema,
)


# =====================================================================
# TRS — Topic Relevance Score
# =====================================================================


class TestCalculateTRS:
    """Tests for the Topic Relevance Score formula."""

    def test_high_confidence_new_topic(self):
        trs = calculate_trs(
            claim_confidence=0.90,
            source_count=3,
            is_new_topic=True,
            geographic_relevance=1.0,
            days_since_extraction=0,
        )
        assert trs >= TRS_HANDOFF
        assert 0.0 <= trs <= 1.0

    def test_low_confidence_old_topic(self):
        trs = calculate_trs(
            claim_confidence=0.30,
            source_count=1,
            is_new_topic=False,
            geographic_relevance=1.0,
            days_since_extraction=60,
        )
        assert trs < TRS_HANDOFF

    def test_freshness_decay(self):
        trs_fresh = calculate_trs(
            claim_confidence=0.70,
            source_count=2,
            is_new_topic=True,
            days_since_extraction=0,
        )
        trs_stale = calculate_trs(
            claim_confidence=0.70,
            source_count=2,
            is_new_topic=True,
            days_since_extraction=60,
        )
        assert trs_fresh > trs_stale

    def test_novelty_boost(self):
        trs_new = calculate_trs(
            claim_confidence=0.70,
            source_count=2,
            is_new_topic=True,
        )
        trs_old = calculate_trs(
            claim_confidence=0.70,
            source_count=2,
            is_new_topic=False,
        )
        assert trs_new > trs_old

    def test_clamped_to_unit(self):
        trs = calculate_trs(
            claim_confidence=1.0,
            source_count=100,
            is_new_topic=True,
            geographic_relevance=1.0,
            days_since_extraction=0,
        )
        assert trs <= 1.0

    def test_bali_specific_slightly_lower(self):
        trs_national = calculate_trs(
            claim_confidence=0.70,
            source_count=2,
            is_new_topic=True,
            geographic_relevance=1.0,
        )
        trs_bali = calculate_trs(
            claim_confidence=0.70,
            source_count=2,
            is_new_topic=True,
            geographic_relevance=0.9,
        )
        assert trs_bali < trs_national


class TestClassifyTRS:
    """Tests for TRS classification."""

    def test_handoff(self):
        assert classify_trs(0.70) == "HANDOFF"
        assert classify_trs(0.65) == "HANDOFF"
        assert classify_trs(1.0) == "HANDOFF"

    def test_candidate(self):
        assert classify_trs(0.50) == "CANDIDATE"
        assert classify_trs(0.45) == "CANDIDATE"

    def test_skip(self):
        assert classify_trs(0.20) == "SKIP"
        assert classify_trs(0.0) == "SKIP"


# =====================================================================
# Integration mode
# =====================================================================


class TestDetermineIntegrationMode:
    """Tests for integration mode determination."""

    def test_empty_claims_ignore(self):
        assert determine_integration_mode([]) == MODE_IGNORE

    def test_high_confidence_prioritize(self):
        claims = [
            {"confidence_score": 0.90},
            {"confidence_score": 0.80},
        ]
        assert determine_integration_mode(claims) == MODE_PRIORITIZE

    def test_low_confidence_enrich(self):
        claims = [
            {"confidence_score": 0.60},
            {"confidence_score": 0.50},
        ]
        assert determine_integration_mode(claims) == MODE_ENRICH

    def test_boundary_at_075(self):
        claims = [{"confidence_score": 0.75}]
        assert determine_integration_mode(claims) == MODE_PRIORITIZE


# =====================================================================
# Topic selection
# =====================================================================


class TestSelectHandoffTopics:
    """Tests for selecting top claims for handoff."""

    def test_selects_top_by_trs(self):
        claims = [
            {"confidence_score": 0.90, "source_ids": ["A", "B", "C"], "geographic_scope": "NATIONAL"},
            {"confidence_score": 0.40, "source_ids": ["A"], "geographic_scope": "NATIONAL"},
            {"confidence_score": 0.80, "source_ids": ["A", "B"], "geographic_scope": "NATIONAL"},
        ]
        selected = select_handoff_topics(claims, max_topics=2)
        assert len(selected) <= 2
        # First selected should have highest TRS
        if len(selected) >= 2:
            assert selected[0]["trs"] >= selected[1]["trs"]

    def test_respects_max_topics(self):
        claims = [
            {"confidence_score": 0.90, "source_ids": ["A", "B", "C"], "geographic_scope": "NATIONAL"}
            for _ in range(10)
        ]
        selected = select_handoff_topics(claims, max_topics=3)
        assert len(selected) <= 3

    def test_falls_back_to_candidates(self):
        """If not enough HANDOFF-class, includes CANDIDATE-class."""
        claims = [
            {"confidence_score": 0.50, "source_ids": ["A"], "geographic_scope": "NATIONAL"},
            {"confidence_score": 0.45, "source_ids": ["A"], "geographic_scope": "NATIONAL"},
        ]
        selected = select_handoff_topics(claims, max_topics=5)
        # Should include candidates since not enough handoff
        assert len(selected) >= 1

    def test_empty_claims(self):
        selected = select_handoff_topics([], max_topics=5)
        assert len(selected) == 0

    def test_trs_class_in_output(self):
        claims = [
            {"confidence_score": 0.90, "source_ids": ["A", "B"], "geographic_scope": "NATIONAL"},
        ]
        selected = select_handoff_topics(claims, max_topics=5)
        assert "trs" in selected[0]
        assert "trs_class" in selected[0]


# =====================================================================
# Handoff generation
# =====================================================================


class TestGenerateHandoff:
    """Tests for generating the complete handoff package."""

    def _make_claims(self, n: int = 3) -> list[dict]:
        return [
            {
                "claim_text": f"Claim number {i} about immigration regulation changes in Indonesia 2026",
                "category": "LEGAL_CHANGE",
                "confidence_score": 0.80,
                "confidence_class": "VERIFIED",
                "source_ids": [f"SRC-{i}"],
                "geographic_scope": "NATIONAL",
                "affected_visa_types": ["KITAS_E23"],
            }
            for i in range(n)
        ]

    def test_basic_structure(self):
        package = generate_handoff(
            claims=self._make_claims(),
            pipeline_run_id="test-run-001",
            notebook_id="NB-2",
            query_cluster="A",
            queries_executed=2,
        )
        assert package["schema_version"] == SCHEMA_VERSION
        assert package["pipeline_run_id"] == "test-run-001"
        assert package["notebook_id"] == "NB-2"
        assert "key_findings" in package
        assert "suggested_topics" in package
        assert "scraper_hints" in package

    def test_findings_count_within_limit(self):
        package = generate_handoff(
            claims=self._make_claims(20),
            pipeline_run_id="test-run-002",
            notebook_id="NB-2",
            query_cluster="B",
            queries_executed=2,
        )
        assert len(package["key_findings"]) <= MAX_HANDOFF_FINDINGS

    def test_domain_denylist_in_hints(self):
        deny = ["tripadvisor.com", "reddit.com"]
        package = generate_handoff(
            claims=self._make_claims(),
            pipeline_run_id="test-run-003",
            notebook_id="NB-2",
            query_cluster="C",
            queries_executed=2,
            domain_denylist=deny,
        )
        assert package["scraper_hints"]["avoid_urls"] == deny

    def test_empty_claims_produces_ignore_mode(self):
        package = generate_handoff(
            claims=[],
            pipeline_run_id="test-run-004",
            notebook_id="NB-2",
            query_cluster="D",
            queries_executed=2,
        )
        assert package["integration_mode"] == MODE_IGNORE
        assert len(package["key_findings"]) == 0

    def test_finding_ids_are_unique(self):
        package = generate_handoff(
            claims=self._make_claims(5),
            pipeline_run_id="test-run-005",
            notebook_id="NB-2",
            query_cluster="E",
            queries_executed=2,
        )
        ids = [f["finding_id"] for f in package["key_findings"]]
        assert len(ids) == len(set(ids))


# =====================================================================
# Schema validation
# =====================================================================


class TestValidateHandoffSchema:
    """Tests for validating the handoff package schema."""

    def test_valid_package_passes(self):
        package = generate_handoff(
            claims=[{
                "claim_text": "Test claim text for immigration regulation",
                "category": "LEGAL_CHANGE",
                "confidence_score": 0.80,
                "confidence_class": "VERIFIED",
                "source_ids": ["SRC-1"],
                "geographic_scope": "NATIONAL",
                "affected_visa_types": [],
            }],
            pipeline_run_id="test-valid",
            notebook_id="NB-2",
            query_cluster="A",
            queries_executed=2,
        )
        is_valid, errors = validate_handoff_schema(package)
        assert is_valid is True
        assert len(errors) == 0

    def test_missing_required_field_fails(self):
        package = {"schema_version": SCHEMA_VERSION}
        is_valid, errors = validate_handoff_schema(package)
        assert is_valid is False
        assert len(errors) > 0

    def test_wrong_schema_version_fails(self):
        package = {
            "schema_version": "99.0",
            "generated_at": "2026-03-28",
            "pipeline_run_id": "r1",
            "notebook_id": "NB-2",
            "query_cluster": "A",
            "queries_executed": 2,
            "integration_mode": MODE_ENRICH,
            "key_findings": [],
        }
        is_valid, errors = validate_handoff_schema(package)
        assert is_valid is False

    def test_invalid_mode_fails(self):
        package = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": "2026-03-28",
            "pipeline_run_id": "r1",
            "notebook_id": "NB-2",
            "query_cluster": "A",
            "queries_executed": 2,
            "integration_mode": "INVALID_MODE",
            "key_findings": [],
        }
        is_valid, errors = validate_handoff_schema(package)
        assert is_valid is False

    def test_too_many_findings_fails(self):
        package = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": "2026-03-28",
            "pipeline_run_id": "r1",
            "notebook_id": "NB-2",
            "query_cluster": "A",
            "queries_executed": 2,
            "integration_mode": MODE_ENRICH,
            "key_findings": [{"id": i} for i in range(MAX_HANDOFF_FINDINGS + 5)],
        }
        is_valid, errors = validate_handoff_schema(package)
        assert is_valid is False


# =====================================================================
# save_handoff — file I/O
# =====================================================================


class TestSaveHandoff:
    """Tests for atomic handoff save with latest.json symlink."""

    def _make_package(self) -> dict:
        return generate_handoff(
            claims=[{
                "claim_text": "Test claim for handoff save testing with enough length",
                "category": "LEGAL_CHANGE",
                "confidence_score": 0.85,
                "confidence_class": "VERIFIED",
                "source_ids": ["SRC-1"],
                "geographic_scope": "NATIONAL",
                "affected_visa_types": [],
            }],
            pipeline_run_id="save-test",
            notebook_id="NB-2",
            query_cluster="A",
            queries_executed=2,
        )

    def test_creates_dated_file(self, handoff_dir):
        package = self._make_package()
        result = save_handoff(package, output_dir=str(handoff_dir))
        assert result.exists()
        assert result.suffix == ".json"

    def test_creates_latest_symlink(self, handoff_dir):
        package = self._make_package()
        save_handoff(package, output_dir=str(handoff_dir))
        latest = handoff_dir / "latest.json"
        assert latest.exists() or latest.is_symlink()

    def test_latest_symlink_points_to_dated_file(self, handoff_dir):
        package = self._make_package()
        dated = save_handoff(package, output_dir=str(handoff_dir))
        latest = handoff_dir / "latest.json"
        # Read both and compare
        dated_content = json.loads(dated.read_text())
        latest_content = json.loads(latest.read_text())
        assert dated_content == latest_content

    def test_saved_content_matches_package(self, handoff_dir):
        package = self._make_package()
        result = save_handoff(package, output_dir=str(handoff_dir))
        saved = json.loads(result.read_text())
        assert saved["schema_version"] == SCHEMA_VERSION
        assert saved["pipeline_run_id"] == "save-test"

    def test_creates_output_dir_if_missing(self, tmp_path):
        new_dir = tmp_path / "nested" / "handoff"
        package = self._make_package()
        result = save_handoff(package, output_dir=str(new_dir))
        assert result.exists()
