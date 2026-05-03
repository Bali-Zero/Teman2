"""
Mata Garuda — Sprint 3 tests for Lamarckian system.

Tests:
- case_resolved / case_not_resolved tools
- Feedback logging to feedback/{agent}.md
- GENOME read/write/mutation/revert
- Fitness tracking (success rate, auto-revert)
- Lamarckian case status parsing
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.runtime.fitness import (
    DEGRADATION_THRESHOLD,
    _fitness_path,
    check_and_auto_revert,
    get_fitness_summary,
    get_mutation_version,
    get_recent_runs,
    get_success_rate,
    record_run,
)
from mata_garuda.runtime.genome import (
    AGENTS_DIR,
    apply_mutation,
    get_feedback_path,
    get_genome_path,
    log_feedback,
    read_feedback,
    read_genome,
    revert_last_mutation,
)
from mata_garuda.runtime.lamarckian import _parse_case_status


# ─── Fixtures ──────────────────────────────────────────────────────────

FEEDBACK_DIR = Path(__file__).parent.parent / "feedback"
TEST_AGENT = "Lamarckian Test Agent"
TEST_SAFE = "lamarckian_test_agent"


@pytest.fixture(autouse=True)
def cleanup_test_files():
    """Clean up test agent files after each test."""
    yield
    # Cleanup GENOME
    genome = AGENTS_DIR / f"{TEST_SAFE}_GENOME.md"
    genome.unlink(missing_ok=True)

    # Cleanup feedback
    feedback = FEEDBACK_DIR / f"{TEST_SAFE}.md"
    feedback.unlink(missing_ok=True)

    # Cleanup fitness
    fitness = FEEDBACK_DIR / f"{TEST_SAFE}_fitness.jsonl"
    fitness.unlink(missing_ok=True)


@pytest.fixture
def test_genome():
    """Create a test GENOME.md file."""
    genome_path = AGENTS_DIR / f"{TEST_SAFE}_GENOME.md"
    content = """\
# GENOME — Lamarckian Test Agent

## Identity
Test agent for Lamarckian system.

## Constraints
- Must validate input before processing
- NEVER make external API calls

## Fitness
- Success rate: N/A
- Mutations: 0
"""
    genome_path.write_text(content)
    return genome_path


# ─── Case Status Tests ────────────────────────────────────────────────


class TestCaseStatus:
    def test_case_resolved(self):
        result = case_resolved("Task completed successfully")
        assert "Case resolved" in result
        assert "Task completed successfully" in result

    def test_case_not_resolved(self):
        result = case_not_resolved("Input invalid", "Validate range first")
        assert "Case not resolved" in result
        assert "Input invalid" in result
        assert "Validate range first" in result

    def test_case_resolved_registered(self):
        from mata_garuda.registry import registry

        assert "case_resolved" in registry.tools

    def test_case_not_resolved_registered(self):
        from mata_garuda.registry import registry

        assert "case_not_resolved" in registry.tools


# ─── Parse Case Status ────────────────────────────────────────────────


class TestParseCaseStatus:
    def test_parse_resolved(self):
        text = "Case resolved. The result is: Found 3 items"
        status, details = _parse_case_status(text)
        assert status == "resolved"
        assert "Found 3 items" in details["result"]

    def test_parse_not_resolved(self):
        text = "Case not resolved. Reason: timeout. Insight: retry with shorter query"
        status, details = _parse_case_status(text)
        assert status == "not_resolved"
        assert "timeout" in details["reason"]
        assert "retry" in details["insight"]

    def test_parse_no_status(self):
        text = "Just a regular response without case status"
        status, details = _parse_case_status(text)
        assert status is None
        assert details is None


# ─── Feedback Logging Tests ───────────────────────────────────────────


class TestFeedbackLogging:
    def test_log_feedback_creates_file(self):
        path = log_feedback(
            TEST_AGENT, attempt=1,
            failure_reason="test failure",
            take_away="test insight",
        )
        assert path.exists()
        content = path.read_text()
        assert "attempt 1" in content
        assert "test failure" in content
        assert "test insight" in content

    def test_log_feedback_appends(self):
        log_feedback(TEST_AGENT, 1, "first failure", "first insight")
        log_feedback(TEST_AGENT, 2, "second failure", "second insight")

        content = read_feedback(TEST_AGENT)
        assert "attempt 1" in content
        assert "attempt 2" in content
        assert "first failure" in content
        assert "second failure" in content

    def test_read_feedback_missing(self):
        result = read_feedback("Nonexistent Agent")
        assert result == ""

    def test_feedback_path(self):
        path = get_feedback_path(TEST_AGENT)
        assert path.name == f"{TEST_SAFE}.md"


# ─── GENOME Tests ─────────────────────────────────────────────────────


class TestGenome:
    def test_read_genome(self, test_genome):
        content = read_genome(TEST_AGENT)
        assert "Lamarckian Test Agent" in content
        assert "## Constraints" in content

    def test_read_genome_missing(self):
        content = read_genome("Nonexistent Agent")
        assert content == ""

    def test_genome_path(self):
        path = get_genome_path(TEST_AGENT)
        assert path.name == f"{TEST_SAFE}_GENOME.md"

    def test_apply_mutation(self, test_genome):
        result = apply_mutation(
            TEST_AGENT,
            "Always validate KBLI code range 01-96",
            "KBLI 99999 caused failure",
        )
        assert result is True

        content = read_genome(TEST_AGENT)
        assert "Always validate KBLI code range 01-96" in content
        assert "Mutations: 1" in content

    def test_apply_mutation_missing_genome(self):
        result = apply_mutation(
            "Nonexistent Agent",
            "constraint",
            "reason",
        )
        assert result is False

    def test_revert_mutation(self, test_genome):
        # Apply then revert
        apply_mutation(TEST_AGENT, "Temp constraint", "temp reason")
        content_after = read_genome(TEST_AGENT)
        assert "Temp constraint" in content_after

        result = revert_last_mutation(TEST_AGENT)
        assert result is True

        content_reverted = read_genome(TEST_AGENT)
        assert "Temp constraint" not in content_reverted

    def test_revert_nothing(self, test_genome):
        result = revert_last_mutation(TEST_AGENT)
        assert result is False  # No mutations to revert

    def test_revert_missing_genome(self):
        result = revert_last_mutation("Nonexistent Agent")
        assert result is False


# ─── Fitness Tracker Tests ────────────────────────────────────────────


class TestFitness:
    def test_record_run_success(self):
        record_run(TEST_AGENT, success=True, mutation_version=0)
        runs = get_recent_runs(TEST_AGENT)
        assert len(runs) == 1
        assert runs[0]["success"] is True

    def test_record_run_failure(self):
        record_run(TEST_AGENT, success=False, mutation_version=0)
        runs = get_recent_runs(TEST_AGENT)
        assert len(runs) == 1
        assert runs[0]["success"] is False

    def test_success_rate(self):
        record_run(TEST_AGENT, True, 0)
        record_run(TEST_AGENT, True, 0)
        record_run(TEST_AGENT, False, 0)

        rate = get_success_rate(TEST_AGENT)
        assert rate == pytest.approx(2 / 3, rel=0.01)

    def test_success_rate_no_runs(self):
        rate = get_success_rate(TEST_AGENT)
        assert rate is None

    def test_mutation_version(self):
        record_run(TEST_AGENT, True, 3)
        version = get_mutation_version(TEST_AGENT)
        assert version == 3

    def test_fitness_summary(self):
        record_run(TEST_AGENT, True, 0)
        record_run(TEST_AGENT, False, 0)

        summary = get_fitness_summary(TEST_AGENT)
        assert TEST_AGENT in summary
        assert "50%" in summary

    def test_fitness_summary_no_runs(self):
        summary = get_fitness_summary(TEST_AGENT)
        assert "no runs recorded" in summary

    def test_auto_revert_on_degradation(self, test_genome):
        # Apply mutation
        apply_mutation(TEST_AGENT, "Bad constraint", "test reason")

        # Record mostly failures at mutation v1
        for _ in range(4):
            record_run(TEST_AGENT, success=False, mutation_version=1)

        reverted = check_and_auto_revert(TEST_AGENT)
        assert reverted is True

        # Verify constraint removed
        content = read_genome(TEST_AGENT)
        assert "Bad constraint" not in content

        # Check revert event logged
        runs = get_recent_runs(TEST_AGENT, window=20)
        revert_events = [r for r in runs if r.get("event") == "auto_revert"]
        assert len(revert_events) == 1

    def test_no_revert_when_healthy(self, test_genome):
        apply_mutation(TEST_AGENT, "Good constraint", "test reason")

        # Record mostly successes
        for _ in range(5):
            record_run(TEST_AGENT, success=True, mutation_version=1)

        reverted = check_and_auto_revert(TEST_AGENT)
        assert reverted is False

    def test_no_revert_at_v0(self):
        # No mutations — nothing to revert
        for _ in range(5):
            record_run(TEST_AGENT, success=False, mutation_version=0)

        reverted = check_and_auto_revert(TEST_AGENT)
        assert reverted is False


# ─── Agent Wiring Tests ───────────────────────────────────────────────


class TestAgentWiring:
    def test_dummy_agent_has_case_tools(self):
        from mata_garuda.agents.dummy_agent import get_dummy_agent

        agent = get_dummy_agent()
        tool_names = [f.__name__ for f in agent.functions]
        assert "case_resolved" in tool_names
        assert "case_not_resolved" in tool_names

    def test_meta_agent_has_case_tools(self):
        from mata_garuda.agents.meta_agent import get_meta_agent

        agent = get_meta_agent()
        tool_names = [f.__name__ for f in agent.functions]
        assert "case_resolved" in tool_names
        assert "case_not_resolved" in tool_names
