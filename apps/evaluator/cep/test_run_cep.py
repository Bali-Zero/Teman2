"""Tests for CEP run_cep — golden integrity + scoring logic."""

import json
from pathlib import Path
from unittest.mock import patch

import httpx

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
    # No answers map, no evaluator enabled → all misses without paid calls.
    summary = run_cep.run_cep(
        GOLDEN_PATH, answers={}, dry_run=False,
        report_path=report,
    )
    assert summary["hits"] == 0


def test_run_cep_dry_run_does_not_call_backend_or_evaluator(tmp_path):
    """Dry-run stays fully local even if a backend URL is configured."""
    report = tmp_path / "report.csv"

    def fail_backend(request):
        raise AssertionError(f"backend should not be called in dry-run: {request.url}")

    with patch.object(run_cep, "grade_with_deepseek") as grade:
        summary = run_cep.run_cep(
            GOLDEN_PATH,
            dry_run=True,
            report_path=report,
            backend_url="https://rag.example.test",
            backend_transport=httpx.MockTransport(fail_backend),
        )

    grade.assert_not_called()
    assert summary["total"] == 50
    assert summary["source_errors"] == 0
    assert {row["evaluator_error"] for row in summary["rows"]} == {"dry_run"}


def test_run_cep_answers_file_remains_backward_compatible(tmp_path):
    """The existing JSON answer map path remains a valid answer source."""
    answers_path = tmp_path / "answers.json"
    report = tmp_path / "report.csv"
    answers_path.write_text(json.dumps({"imm-01": "KITAS E23 is valid for one year."}))

    with patch.object(run_cep, "grade_with_deepseek") as grade:
        summary = run_cep.run_cep(
            GOLDEN_PATH,
            answers_file=answers_path,
            report_path=report,
        )

    grade.assert_not_called()
    first = summary["rows"][0]
    assert first["id"] == "imm-01"
    assert first["answer_source"] == "answers_file"
    assert first["answer_excerpt"] == "KITAS E23 is valid for one year."
    assert first["evaluator_error"] == "evaluator_disabled"


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


def test_run_cep_backend_answer_source_success(tmp_path, monkeypatch):
    """Backend mode collects answers through a thin HTTP client."""
    report = tmp_path / "report.csv"
    monkeypatch.setenv("CEP_BACKEND_KEY", "test-backend-key")

    def handler(request):
        assert request.url == httpx.URL("https://rag.example.test/api/agentic-rag/query")
        assert request.headers["authorization"] == "Bearer test-backend-key"
        assert request.headers["x-api-key"] == "test-backend-key"
        payload = json.loads(request.content)
        assert payload["user_id"] == "cep_eval"
        return httpx.Response(200, json={"answer": f"backend answer: {payload['query']}"})

    def fake_grade(query, answer, required_facts, *, api_key, timeout=60):
        return {
            "hit": True,
            "facts_covered": len(required_facts),
            "facts_total": len(required_facts),
            "contradiction": False,
            "notes": "fake-grader",
            "evaluator_error": None,
        }

    with patch.object(run_cep, "grade_with_deepseek", side_effect=fake_grade) as grade:
        summary = run_cep.run_cep(
            GOLDEN_PATH,
            backend_url="https://rag.example.test",
            backend_endpoint="/api/agentic-rag/query",
            backend_api_key_env="CEP_BACKEND_KEY",
            backend_transport=httpx.MockTransport(handler),
            deepseek_key="fake-key",
            enable_evaluator=True,
            report_path=report,
        )

    assert grade.call_count == 50
    assert summary["hits"] == 50
    assert summary["source_errors"] == 0
    assert summary["rows"][0]["answer_source"] == "backend"
    assert summary["rows"][0]["source_error"] is None


def test_run_cep_backend_failure_is_per_query_and_skips_evaluator(tmp_path):
    """A backend error records source_error for that row without stopping CEP."""
    report = tmp_path / "report.csv"
    calls = {"backend": 0}

    def handler(request):
        calls["backend"] += 1
        if calls["backend"] == 1:
            return httpx.Response(503, text="backend unavailable")
        payload = json.loads(request.content)
        return httpx.Response(200, json={"answer": f"answer for {payload['query']}"})

    def fake_grade(query, answer, required_facts, *, api_key, timeout=60):
        return {
            "hit": True,
            "facts_covered": len(required_facts),
            "facts_total": len(required_facts),
            "contradiction": False,
            "notes": "fake-grader",
            "evaluator_error": None,
        }

    with patch.object(run_cep, "grade_with_deepseek", side_effect=fake_grade) as grade:
        summary = run_cep.run_cep(
            GOLDEN_PATH,
            backend_url="https://rag.example.test",
            backend_transport=httpx.MockTransport(handler),
            deepseek_key="fake-key",
            enable_evaluator=True,
            report_path=report,
        )

    assert calls["backend"] == 50
    assert grade.call_count == 49
    assert summary["total"] == 50
    assert summary["hits"] == 49
    assert summary["source_errors"] == 1
    assert summary["rows"][0]["source_error"].startswith("HTTP 503")
    assert summary["rows"][0]["evaluator_error"] is None


def test_run_cep_does_not_call_paid_evaluator_without_explicit_enable(
    tmp_path, monkeypatch
):
    """An env key alone is not enough to spend evaluator budget."""
    report = tmp_path / "report.csv"
    monkeypatch.setenv("DEEPSEEK_API_KEY", "real-looking-env-key")

    answers = {
        q["id"]: f"answer for {q['id']}"
        for _, q in run_cep.iter_queries(run_cep.load_golden(GOLDEN_PATH))
    }

    with patch.object(run_cep, "grade_with_deepseek") as grade:
        summary = run_cep.run_cep(
            GOLDEN_PATH,
            answers=answers,
            dry_run=False,
            report_path=report,
        )

    grade.assert_not_called()
    assert summary["hits"] == 0
    assert summary["evaluator_errors"] == 50
    assert {row["evaluator_error"] for row in summary["rows"]} == {"evaluator_disabled"}
