"""Tests for the 7 Leggi admission test framework — Sprint 0 Track C1."""

from __future__ import annotations

import pytest

from cell_core.admission_test import (
    AdmissionResult,
    AdmissionTest,
    Legge,
    Violation,
)


def _passing_cell() -> dict:
    """Minimal cell definition that passes all 7 Leggi."""
    return {
        "name": "system-doctor-cell",
        "level": "L1",
        "exposes_gui": False,
        "llm_invocation": "ollama",
        "external_sources": ["fly-api"],
        "client_data_access": False,
        "publishes_via": "pg_notify",
        "fallback_modes": ["redis_down", "llm_provider_down"],
        "kill_switch": True,
        "auto_publishes": False,
        "depends_on_other_cell_decisions": False,
        "metrics": ["ttr", "error_rate", "throughput"],
    }


def test_passing_cell_passes_all_seven_laws() -> None:
    cell = _passing_cell()
    result = AdmissionTest().run_all(cell)
    assert result.passed is True, result.summary()
    assert result.cell_name == "system-doctor-cell"
    blockers = [v for v in result.violations if v.severity == "blocker"]
    assert blockers == [], f"expected no blockers, got: {blockers}"


def test_cli_only_blocks_gui_exposure() -> None:
    """A cell that exposes a GUI fails Law 1 (CLI-only)."""
    cell = _passing_cell()
    cell["exposes_gui"] = True
    result = AdmissionTest().run_all(cell)
    assert result.passed is False
    blockers = [v for v in result.violations if v.severity == "blocker"]
    assert any(v.legge == Legge.CLI_ONLY for v in blockers), result.summary()


def test_osint_blindato_blocks_external_plus_client() -> None:
    """A cell that mixes OSINT external sources with client PII access fails Law 2."""
    cell = _passing_cell()
    cell["external_sources"] = ["intel-scraper"]
    cell["client_data_access"] = True
    result = AdmissionTest().run_all(cell)
    assert result.passed is False
    osint_violations = [
        v for v in result.violations
        if v.legge == Legge.OSINT_BLINDATO and v.severity == "blocker"
    ]
    assert osint_violations, result.summary()


def test_event_driven_blocks_filesystem_publish() -> None:
    """A cell that publishes via filesystem fails Law 3 (Event-driven)."""
    cell = _passing_cell()
    cell["publishes_via"] = "filesystem"
    result = AdmissionTest().run_all(cell)
    assert result.passed is False
    event_violations = [
        v for v in result.violations
        if v.legge == Legge.EVENT_DRIVEN and v.severity == "blocker"
    ]
    assert event_violations, result.summary()


def test_local_sovereignty_blocks_dependency_on_other_cell_decisions() -> None:
    """A cell whose decisions depend on another cell's reasoning fails Law 6.

    Example: a hypothetical 'oracle L4 cell' that bypassed war-room — DeepSeek
    round-2 risk callout. The right classification for such a unit is
    'organelle inside the parent cell', not a free-standing cell.
    """
    cell = _passing_cell()
    cell["name"] = "oracle-bypass-attempt"
    cell["depends_on_other_cell_decisions"] = True
    result = AdmissionTest().run_all(cell)
    assert result.passed is False
    local_violations = [
        v for v in result.violations
        if v.legge == Legge.LOCAL_SOVEREIGNTY and v.severity == "blocker"
    ]
    assert local_violations, result.summary()


def test_numbers_first_blocks_under_three_metrics() -> None:
    """A cell that declares fewer than 3 metrics fails Law 7."""
    cell = _passing_cell()
    cell["metrics"] = ["ttr"]
    result = AdmissionTest().run_all(cell)
    assert result.passed is False
    numbers_violations = [
        v for v in result.violations
        if v.legge == Legge.NUMBERS_FIRST and v.severity == "blocker"
    ]
    assert numbers_violations, result.summary()


def test_summary_format_passing() -> None:
    cell = _passing_cell()
    result = AdmissionTest().run_all(cell)
    summary = result.summary()
    assert "PASS" in summary
    assert "system-doctor-cell" in summary
    assert "BLOCKER" not in summary


def test_summary_format_failing() -> None:
    cell = _passing_cell()
    cell["kill_switch"] = False
    result = AdmissionTest().run_all(cell)
    summary = result.summary()
    assert "FAIL" in summary
    assert "BLOCKER" in summary
    assert Legge.ZERO_FINAL_INSTANCE.value in summary


def test_graceful_degradation_blocks_no_fallbacks() -> None:
    """A cell with empty fallback_modes fails Law 4."""
    cell = _passing_cell()
    cell["fallback_modes"] = []
    result = AdmissionTest().run_all(cell)
    assert result.passed is False
    grace_violations = [
        v for v in result.violations
        if v.legge == Legge.GRACEFUL_DEGRADATION and v.severity == "blocker"
    ]
    assert grace_violations, result.summary()


# ── round-2 review fixes (4-LLM cross-review of PR #426) ──────────────


def test_registry_has_all_seven_leggi_populated() -> None:
    """Round-2 review (Claude): protect the 7 Leggi registry from a future
    refactor accidentally dropping a check. Without this assert, a missing
    check silently surfaces as a warning ("no check registered") and the
    cell still PASSES — defeating the point of the gate.
    """
    assert len(AdmissionTest.CHECKS) == 7
    assert set(AdmissionTest.CHECKS.keys()) == set(Legge)


def test_publishes_via_none_blocks_when_cell_class_is_cell() -> None:
    """Round-2 review (Claude/GPT-5.5): publishes_via='none' is reserved for
    substrate-only organelles. A cell setting it bypasses Law 3 entirely.
    Now blocks unless cell_class='organelle' is also declared.
    """
    cell = _passing_cell()
    cell["publishes_via"] = "none"   # cell_class defaults to 'cell'
    result = AdmissionTest().run_all(cell)
    assert result.passed is False
    event_violations = [
        v for v in result.violations
        if v.legge == Legge.EVENT_DRIVEN and v.severity == "blocker"
    ]
    assert event_violations, result.summary()


def test_publishes_via_none_passes_for_organelle() -> None:
    """A substrate-only organelle (e.g. pg-proxy) explicitly opts out of
    publishing — declaring cell_class='organelle' makes publishes_via='none'
    valid.
    """
    cell = _passing_cell()
    cell["name"] = "pg-proxy-organelle"
    cell["publishes_via"] = "none"
    cell["cell_class"] = "organelle"
    result = AdmissionTest().run_all(cell)
    assert result.passed is True, result.summary()


def test_publishes_via_unknown_value_blocks() -> None:
    """Round-2 review (Claude/GPT-5.5): unknown publishes_via values were
    only WARNING — silent admission. Now they BLOCK.
    """
    cell = _passing_cell()
    cell["publishes_via"] = "rabbitmq"   # not in allowlist
    result = AdmissionTest().run_all(cell)
    assert result.passed is False
    event_violations = [
        v for v in result.violations
        if v.legge == Legge.EVENT_DRIVEN and v.severity == "blocker"
    ]
    assert event_violations, result.summary()


def test_llm_invocation_anthropic_api_blocks() -> None:
    """Round-2 review (Gemini): Law 1 specifically bans the Anthropic paid
    API. Verify a cell declaring llm_invocation='anthropic_api' fails.
    """
    cell = _passing_cell()
    cell["llm_invocation"] = "anthropic_api"
    result = AdmissionTest().run_all(cell)
    assert result.passed is False
    cli_violations = [
        v for v in result.violations
        if v.legge == Legge.CLI_ONLY and v.severity == "blocker"
    ]
    assert cli_violations, result.summary()


def test_auto_publishes_true_blocks() -> None:
    """Round-2 review (Gemini/GPT-5.5): Law 5 forbids auto-publishing to
    externally-visible channels. Verify auto_publishes=True triggers a
    blocker even with kill_switch=True.
    """
    cell = _passing_cell()
    cell["auto_publishes"] = True   # kill_switch already True
    result = AdmissionTest().run_all(cell)
    assert result.passed is False
    zero_violations = [
        v for v in result.violations
        if v.legge == Legge.ZERO_FINAL_INSTANCE and v.severity == "blocker"
    ]
    assert zero_violations, result.summary()
