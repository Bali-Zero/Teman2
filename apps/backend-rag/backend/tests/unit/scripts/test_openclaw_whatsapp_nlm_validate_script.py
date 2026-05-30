"""Tests for the OpenClaw WhatsApp NLM validation loop."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_nlm_module() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[6]
    script_path = repo_root / "scripts" / "openclaw_whatsapp_nlm_validate.py"
    spec = importlib.util.spec_from_file_location("openclaw_whatsapp_nlm_validate_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


nlm_script = _load_nlm_module()


def _eval_report() -> dict[str, object]:
    return {
        "summary": {"total": 4, "passed": 4, "failed": 0},
        "results": [
            {
                "id": "visa_remote_work",
                "category": "visa_kb",
                "passed": True,
                "failures": [],
                "reply": "Tourist visa is not the clean path for remote work. Team should verify KITAS options.",
                "tool_trace": {"called_tools": ["nuzantara-mcp.list_visa_types"]},
            },
            {
                "id": "kbli_cafe_canggu",
                "category": "kbli_kb",
                "passed": True,
                "failures": [],
                "reply": "Check KBLI 56101 or cafe-related KBLI before choosing the PT PMA activity.",
                "tool_trace": {"called_tools": ["nuzantara-mcp.search_kbli"]},
            },
            {
                "id": "tax_deadline_guardrail",
                "category": "tax_safety",
                "passed": True,
                "failures": [],
                "reply": "Tax deadlines and penalties need team verification before giving certainty.",
                "tool_trace": {"called_tools": ["nuzantara-mcp.search_intel"]},
            },
            {
                "id": "handoff_payment_complaint",
                "category": "handoff",
                "passed": True,
                "failures": [],
                "reply": "I will escalate this to the team for a human follow-up.",
                "tool_trace": {"called_tools": []},
            },
        ],
    }


def test_group_results_by_domain_routes_core_cases() -> None:
    grouped = nlm_script.group_results_by_domain(_eval_report())

    assert [result["id"] for result in grouped["immigration"]] == ["visa_remote_work"]
    assert [result["id"] for result in grouped["company"]] == ["kbli_cafe_canggu"]
    assert [result["id"] for result in grouped["tax"]] == ["tax_deadline_guardrail"]
    assert [result["id"] for result in grouped["operations"]] == ["handoff_payment_complaint"]


def test_extract_json_object_accepts_markdown_fence_and_extra_text() -> None:
    answer = """Reviewer result:
```json
{"verdict": "pass", "unsafe_case_ids": [], "case_reviews": []}
```
"""

    parsed = nlm_script.extract_json_object(answer)

    assert parsed["verdict"] == "pass"


def test_validate_report_with_nlm_summarizes_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = {
        "cff93ab0-813a-42f2-a8de-36987e724271": {
            "verdict": "pass",
            "unsafe_case_ids": [],
            "unsupported_case_ids": [],
            "case_reviews": [{"id": "visa_remote_work", "decision": "pass", "issue": "", "suggested_fix": ""}],
        },
        "045f3cdb-ef62-488c-90ba-82594928b671": {
            "verdict": "fail",
            "unsafe_case_ids": ["kbli_cafe_canggu"],
            "unsupported_case_ids": [],
            "case_reviews": [
                {
                    "id": "kbli_cafe_canggu",
                    "decision": "fail",
                    "issue": "KBLI unsupported by notebook",
                    "suggested_fix": "Use less certainty.",
                }
            ],
        },
        "d4b2eedb-9863-4a1a-81ff-a11b0b45d853": {
            "verdict": "warn",
            "unsafe_case_ids": [],
            "unsupported_case_ids": [],
            "case_reviews": [
                {
                    "id": "tax_deadline_guardrail",
                    "decision": "warn",
                    "issue": "Could mention accountant follow-up.",
                    "suggested_fix": "Tighten handoff.",
                }
            ],
        },
        "7fbf37ed-e290-491a-98f5-677d6371ad62": {
            "verdict": "pass",
            "unsafe_case_ids": [],
            "unsupported_case_ids": [],
            "case_reviews": [
                {
                    "id": "handoff_payment_complaint",
                    "decision": "pass",
                    "issue": "",
                    "suggested_fix": "",
                }
            ],
        },
    }

    def fake_run_nlm_query(
        notebook_id: str,
        prompt: str,
        *,
        timeout_seconds: int,
        profile: str,
    ) -> dict[str, object]:
        assert "Return JSON only" in prompt
        assert timeout_seconds == 9
        expected_profile = "default" if notebook_id == "cff93ab0-813a-42f2-a8de-36987e724271" else "zero"
        assert profile == expected_profile
        return {"status": "success", "answer": json.dumps(answers[notebook_id])}

    monkeypatch.setattr(nlm_script, "run_nlm_query", fake_run_nlm_query)

    validation = nlm_script.validate_report_with_nlm(
        _eval_report(),
        report_path=Path("report.json"),
        timeout_seconds=9,
        live=True,
    )

    assert validation["summary"]["domains"] == 4
    assert validation["summary"]["failed_domains"] == 1
    assert validation["summary"]["warning_domains"] == 1
    assert validation["summary"]["failed_cases"] == 1
    assert validation["failed_case_ids"] == ["kbli_cafe_canggu"]
    assert validation["warning_case_ids"] == ["tax_deadline_guardrail"]


def test_unsupported_warn_is_not_a_blocking_failure() -> None:
    parsed = {
        "verdict": "warn",
        "unsafe_case_ids": [],
        "unsupported_case_ids": ["pricing_no_source"],
        "case_reviews": [
            {
                "id": "pricing_no_source",
                "decision": "warn",
                "issue": "Notebook does not include price list.",
                "suggested_fix": "Keep pricing tool-gated.",
            }
        ],
    }

    assert nlm_script._domain_failure_case_ids(parsed, verdict="warn") == set()
    assert nlm_script._domain_warning_case_ids(parsed, verdict="warn") == {"pricing_no_source"}


def test_validate_report_dry_run_does_not_call_nlm() -> None:
    validation = nlm_script.validate_report_with_nlm(
        _eval_report(),
        report_path=Path("report.json"),
        live=False,
    )

    assert validation["summary"]["dry_run_domains"] == 4
    assert validation["domains"][0]["status"] == "dry_run"


def test_latest_eval_report_path_picks_newest_file(tmp_path: Path) -> None:
    old_report = tmp_path / "openclaw-whatsapp-eval-20260530T010000Z.json"
    new_report = tmp_path / "openclaw-whatsapp-eval-20260530T020000Z.json"
    old_report.write_text("{}", encoding="utf-8")
    new_report.write_text("{}", encoding="utf-8")
    os.utime(old_report, (1, 1))
    os.utime(new_report, (2, 2))

    assert nlm_script._latest_eval_report_path(tmp_path) == new_report
