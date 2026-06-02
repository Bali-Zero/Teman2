"""Tests for the OpenClaw WhatsApp science readiness loop."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType


def _load_science_module() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[6]
    script_path = repo_root / "scripts" / "openclaw_whatsapp_science_loop.py"
    spec = importlib.util.spec_from_file_location("openclaw_whatsapp_science_loop_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


science_script = _load_science_module()


def _team() -> dict[str, object]:
    return {
        "program": "OpenClaw/Zantara WhatsApp Scientific Team",
        "deadline_wita": "2026-05-31T23:59:00+08:00",
        "readiness_gates": {
            "min_eval_cases": 2,
            "min_tool_required_cases": 2,
            "min_history_context_cases": 0,
            "min_pass_rate": 1.0,
            "max_failed_cases": 0,
            "max_tool_errors": 0,
            "max_p95_latency_ms": 90_000,
            "required_categories": ["kbli_kb", "pricing_tool_safety"],
            "required_tools": [
                "nuzantara-mcp.search_kbli",
                "nuzantara-mcp.search_service_pricing",
            ],
        },
    }


def _cases() -> dict[str, object]:
    return {
        "cases": [
            {
                "id": "kbli",
                "category": "kbli_kb",
                "message": "KBLI?",
                "required_tool_any": ["nuzantara-mcp.search_kbli"],
            },
            {
                "id": "pricing",
                "category": "pricing_tool_safety",
                "message": "Price?",
                "required_tool_any": ["nuzantara-mcp.search_service_pricing"],
            },
        ]
    }


def _report() -> dict[str, object]:
    return {
        "summary": {"total": 2, "passed": 2, "failed": 0},
        "results": [
            {
                "id": "kbli",
                "category": "kbli_kb",
                "passed": True,
                "elapsed_ms": 1000,
                "tool_trace": {
                    "called_tools": ["nuzantara-mcp.search_kbli"],
                    "error_count": 0,
                },
            },
            {
                "id": "pricing",
                "category": "pricing_tool_safety",
                "passed": True,
                "elapsed_ms": 1200,
                "tool_trace": {
                    "called_tools": ["nuzantara-mcp.search_service_pricing"],
                    "error_count": 0,
                },
            },
        ],
    }


def _nlm_report(**summary_overrides: int) -> dict[str, object]:
    summary = {
        "domains": 2,
        "cases": 2,
        "failed_domains": 0,
        "warning_domains": 0,
        "error_domains": 0,
        "failed_cases": 0,
        "warning_cases": 0,
    }
    summary.update(summary_overrides)
    return {
        "source_report_path": "/tmp/openclaw-whatsapp-eval-20260530T010000Z.json",
        "summary": summary,
        "domains": [],
    }


def test_build_science_report_ready_when_all_gates_pass() -> None:
    report = science_script.build_science_report(_team(), _cases(), _report())

    assert report["ready"] is True
    assert all(gate["passed"] for gate in report["gates"])


def test_build_science_report_includes_passing_nlm_gate_when_required() -> None:
    team = _team()
    team["readiness_gates"]["nlm_validation_required"] = True

    report = science_script.build_science_report(
        team,
        _cases(),
        _report(),
        report_path=Path("openclaw-whatsapp-eval-20260530T010000Z.json"),
        nlm_report=_nlm_report(),
        nlm_report_path=Path("openclaw-whatsapp-nlm-validation-20260530T010500Z.json"),
    )

    assert report["ready"] is True
    gate_ids = {gate["id"] for gate in report["gates"]}
    assert "nlm_validation_failures" in gate_ids


def test_build_science_report_fails_nlm_validation_errors() -> None:
    team = _team()
    team["readiness_gates"]["nlm_validation_required"] = True

    report = science_script.build_science_report(
        team,
        _cases(),
        _report(),
        report_path=Path("openclaw-whatsapp-eval-20260530T010000Z.json"),
        nlm_report=_nlm_report(error_domains=1),
    )

    assert report["ready"] is False
    failed_gate_ids = {gate["id"] for gate in report["gates"] if not gate["passed"]}
    assert "nlm_validation_errors" in failed_gate_ids


def test_build_science_report_fails_missing_category() -> None:
    cases = _cases()
    cases["cases"] = [cases["cases"][0]]

    report = science_script.build_science_report(_team(), cases, _report())

    assert report["ready"] is False
    failed_gate_ids = {gate["id"] for gate in report["gates"] if not gate["passed"]}
    assert "case_count" in failed_gate_ids
    assert "category_coverage" in failed_gate_ids
    assert "tool_required_case_count" in failed_gate_ids


def test_build_science_report_fails_without_history_context_when_required() -> None:
    team = _team()
    team["readiness_gates"]["min_history_context_cases"] = 1

    report = science_script.build_science_report(team, _cases(), _report())

    assert report["ready"] is False
    failed_gate_ids = {gate["id"] for gate in report["gates"] if not gate["passed"]}
    assert "history_context_case_count" in failed_gate_ids


def test_build_science_report_fails_live_tool_errors() -> None:
    live_report = _report()
    live_report["summary"] = {"total": 2, "passed": 1, "failed": 1}
    live_report["results"][1]["passed"] = False
    live_report["results"][1]["tool_trace"]["error_count"] = 1

    report = science_script.build_science_report(_team(), _cases(), live_report)

    assert report["ready"] is False
    failed_gate_ids = {gate["id"] for gate in report["gates"] if not gate["passed"]}
    assert "pass_rate" in failed_gate_ids
    assert "failed_cases" in failed_gate_ids
    assert "tool_errors" in failed_gate_ids


def test_latest_report_path_picks_newest_file(tmp_path: Path) -> None:
    old_report = tmp_path / "openclaw-whatsapp-eval-20260530T010000Z.json"
    new_report = tmp_path / "openclaw-whatsapp-eval-20260530T020000Z.json"
    old_report.write_text("{}", encoding="utf-8")
    new_report.write_text("{}", encoding="utf-8")
    os.utime(old_report, (1, 1))
    os.utime(new_report, (2, 2))

    assert science_script._latest_report_path(tmp_path) == new_report
