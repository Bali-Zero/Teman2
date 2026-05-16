"""Tests for CEP run_cep — golden integrity + scoring logic."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from apps.evaluator.cep import run_cep


GOLDEN_PATH = Path(__file__).parent / "golden_v20260425.json"


# ── Golden integrity ─────────────────────────────────────────────────────────

def test_golden_loads_with_50_queries():
    g = run_cep.load_golden(GOLDEN_PATH)
    total = sum(len(qs) for qs in g["domains"].values())
    assert total == 50
    assert len(g["domains"]) == 5


def test_golden_each_domain_has_10_queries():
    g = run_cep.load_golden(GOLDEN_PATH)
    for domain, queries in g["domains"].items():
        assert len(queries) == 10, f"{domain} has {len(queries)} queries"


def test_golden_each_query_has_required_fields():
    g = run_cep.load_golden(GOLDEN_PATH)
    for _, q in run_cep.iter_queries(g):
        assert "id" in q
        assert "query" in q and len(q["query"]) > 5
        assert "required_facts" in q and isinstance(q["required_facts"], list)
        assert len(q["required_facts"]) >= 1
        assert q.get("tier") in (1, 2)


def test_golden_query_ids_are_unique():
    g = run_cep.load_golden(GOLDEN_PATH)
    ids = [q["id"] for _, q in run_cep.iter_queries(g)]
    assert len(ids) == len(set(ids)), "duplicate query ids in golden set"


# ── run_cep dry-run path ─────────────────────────────────────────────────────

def test_run_cep_dry_run_returns_zero_hits(tmp_path):
    report = tmp_path / "report.csv"
    summary = run_cep.run_cep(GOLDEN_PATH, dry_run=True, report_path=report)
    assert summary["total"] == 50
    assert summary["hits"] == 0
    assert summary["hit_rate"] == 0.0
    assert report.exists()
    csv_lines = report.read_text().splitlines()
    assert len(csv_lines) == 51  # header + 50 rows


def test_run_cep_no_answers_marks_all_miss(tmp_path):
    report = tmp_path / "report.csv"
    # No answers map, no DeepSeek key → falls through to dry_run-like behavior
    summary = run_cep.run_cep(
        GOLDEN_PATH, answers={}, dry_run=False,
        deepseek_key="",  # explicit empty triggers dry_run promotion
        report_path=report,
    )
    assert summary["hits"] == 0


# ── grading ────────────────────────────────────────────────────────────────

def test_grade_with_deepseek_handles_evaluator_error():
    # No network call — patch urlopen to raise
    with patch("apps.evaluator.cep.run_cep.urllib.request.urlopen", side_effect=Exception("boom")):
        result = run_cep.grade_with_deepseek(
            "Q?", "A.", ["fact1"], api_key="fake-key"
        )
    assert result["hit"] is False
    assert "evaluator error" in result["notes"]
    assert result["evaluator_error"] is not None


def test_run_cep_with_supplied_answers_uses_evaluator(tmp_path):
    """When answers are present and evaluator returns hit, hit_rate increases."""
    report = tmp_path / "report.csv"

    def fake_grade(query, answer, required_facts, *, api_key, timeout=60):
        # Always say HIT for tests
        return {
            "hit": True,
            "facts_covered": len(required_facts),
            "facts_total": len(required_facts),
            "contradiction": False,
            "notes": "fake-grader",
            "evaluator_error": None,
        }

    answers = {
        q["id"]: f"answer for {q['id']}"
        for _, q in run_cep.iter_queries(run_cep.load_golden(GOLDEN_PATH))
    }

    with patch.object(run_cep, "grade_with_deepseek", side_effect=fake_grade):
        summary = run_cep.run_cep(
            GOLDEN_PATH, answers=answers, dry_run=False,
            deepseek_key="fake-key", report_path=report,
        )

    assert summary["hits"] == 50
    assert summary["hit_rate"] == 1.0
    for domain_summary in summary["per_domain"].values():
        assert domain_summary["hit_rate"] == 1.0
