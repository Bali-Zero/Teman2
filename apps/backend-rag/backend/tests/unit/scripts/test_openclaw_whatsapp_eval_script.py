"""Tests for the OpenClaw WhatsApp eval loop."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType


def _load_eval_module() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[6]
    script_path = repo_root / "scripts" / "openclaw_whatsapp_eval.py"
    spec = importlib.util.spec_from_file_location("openclaw_whatsapp_eval_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


eval_script = _load_eval_module()


def _case(**overrides: object) -> eval_script.EvalCase:
    values = {
        "case_id": "kbli_probe",
        "category": "kbli",
        "message": "Which KBLI for a cafe?",
        "context": {},
        "must_contain_all": (),
        "must_contain_any": (),
        "must_not_contain_any": (),
        "max_words": None,
        "plain_text": True,
        "required_tool_any": ("nuzantara-mcp.search_kbli",),
        "max_tool_errors": 0,
        "repair_hint": "fix tools",
    }
    values.update(overrides)
    return eval_script.EvalCase(**values)


def test_session_key_scopes_to_message_id() -> None:
    assert (
        eval_script._session_key("wa", "628123", "eval.kbli.123")
        == "agent:wa:whatsapp-meta-628123-eval-kbli-123"
    )


def test_collect_tool_trace_counts_calls_and_errors(tmp_path: Path) -> None:
    since = datetime(2026, 5, 30, 1, 0, tzinfo=UTC)
    session_key = "agent:wa:whatsapp-meta-6280000000000"
    path = tmp_path / "trace.trajectory.jsonl"
    events = [
        {
            "type": "tool.call",
            "ts": (since + timedelta(seconds=1)).isoformat().replace("+00:00", "Z"),
            "sessionKey": session_key,
            "data": {"name": "nuzantara-mcp.search_kbli"},
        },
        {
            "type": "tool.result",
            "ts": (since + timedelta(seconds=2)).isoformat().replace("+00:00", "Z"),
            "sessionKey": session_key,
            "data": {
                "name": "nuzantara-mcp.search_kbli",
                "status": "failed",
                "isError": True,
                "output": "structured content failed",
            },
        },
    ]
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")

    trace = eval_script._collect_tool_trace(tmp_path, session_key, since)

    assert trace["available"] is True
    assert trace["called_tools"] == ["nuzantara-mcp.search_kbli"]
    assert trace["call_count"] == 1
    assert trace["result_count"] == 1
    assert trace["error_count"] == 1
    assert trace["errors"][0]["message"] == "structured content failed"


def test_score_tool_trace_requires_clean_tool_call() -> None:
    case = _case()
    clean_trace = {
        "available": True,
        "called_tools": ["nuzantara-mcp.search_kbli"],
        "error_count": 0,
    }

    assert eval_script._score_tool_trace(case, clean_trace) == []

    dirty_trace = {
        "available": True,
        "called_tools": ["nuzantara-mcp.search_kbli"],
        "error_count": 1,
    }
    assert eval_script._score_tool_trace(case, dirty_trace) == ["tool errors: 1 > 0"]


def test_score_tool_trace_flags_missing_required_tool() -> None:
    trace = {
        "available": True,
        "called_tools": ["nuzantara-mcp.search_service_pricing"],
        "error_count": 0,
    }

    failures = eval_script._score_tool_trace(_case(), trace)

    assert failures == ["missing required tool call: nuzantara-mcp.search_kbli"]


def test_transient_tool_transport_failure_is_retryable() -> None:
    result = {
        "passed": False,
        "failures": ["tool errors: 2 > 0"],
        "tool_trace": {
            "errors": [
                {
                    "name": "nuzantara-mcp.search_intel",
                    "message": "tool call failed: Transport closed",
                }
            ]
        },
    }

    assert eval_script._is_transient_tool_transport_failure(result) is True


def test_transient_tool_transport_failure_does_not_mask_content_failure() -> None:
    result = {
        "passed": False,
        "failures": ["missing required tool call: nuzantara-mcp.search_kbli", "tool errors: 1 > 0"],
        "tool_trace": {"errors": [{"message": "Transport closed"}]},
    }

    assert eval_script._is_transient_tool_transport_failure(result) is False


def test_select_cases_filters_by_case_id() -> None:
    cases = [
        _case(case_id="kbli_probe"),
        _case(case_id="visa_probe", category="visa"),
        _case(case_id="pricing_probe", category="pricing"),
    ]

    selected = eval_script._select_cases(cases, case_ids={"visa_probe"}, max_cases=None)

    assert [case.case_id for case in selected] == ["visa_probe"]


def test_select_cases_rejects_unknown_case_id() -> None:
    cases = [_case(case_id="kbli_probe")]

    try:
        eval_script._select_cases(cases, case_ids={"missing_probe"}, max_cases=None)
    except ValueError as exc:
        assert str(exc) == "unknown case id: missing_probe"
    else:
        raise AssertionError("expected ValueError")
