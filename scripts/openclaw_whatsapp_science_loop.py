#!/usr/bin/env python3
"""Summarize OpenClaw/Zantara WhatsApp readiness from eval evidence."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger("openclaw_whatsapp_science_loop")
DEFAULT_TEAM_FILE = Path(__file__).with_name("openclaw_whatsapp_science_team.json")
DEFAULT_CASE_FILE = Path(__file__).with_name("openclaw_whatsapp_eval_cases.json")
DEFAULT_OUTPUT_DIR = Path(".openclaw-evals")
NLM_REPORT_GLOB = "openclaw-whatsapp-nlm-validation-*.json"


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _latest_report_path(output_dir: Path) -> Path | None:
    if not output_dir.exists():
        return None
    reports = sorted(
        output_dir.glob("openclaw-whatsapp-eval-*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return reports[0] if reports else None


def _latest_nlm_report_path(output_dir: Path) -> Path | None:
    if not output_dir.exists():
        return None
    reports = sorted(
        output_dir.glob(NLM_REPORT_GLOB),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return reports[0] if reports else None


def _case_items(cases_doc: dict[str, Any]) -> list[dict[str, Any]]:
    cases = cases_doc.get("cases")
    if not isinstance(cases, list):
        raise ValueError("case file must contain a 'cases' list")
    items: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("each case must be a JSON object")
        items.append(case)
    return items


def _case_categories(cases: list[dict[str, Any]]) -> set[str]:
    categories: set[str] = set()
    for case in cases:
        category = case.get("category")
        if isinstance(category, str) and category:
            categories.add(category)
    return categories


def _required_tools_from_cases(cases: list[dict[str, Any]]) -> set[str]:
    tools: set[str] = set()
    for case in cases:
        raw_tools = case.get("required_tool_any")
        if not isinstance(raw_tools, list):
            continue
        for tool in raw_tools:
            if isinstance(tool, str) and tool:
                tools.add(tool)
    return tools


def _tool_required_case_count(cases: list[dict[str, Any]]) -> int:
    count = 0
    for case in cases:
        raw_tools = case.get("required_tool_any")
        if isinstance(raw_tools, list) and any(isinstance(tool, str) and tool for tool in raw_tools):
            count += 1
    return count


def _history_context_case_count(cases: list[dict[str, Any]]) -> int:
    count = 0
    for case in cases:
        context = case.get("context")
        if not isinstance(context, dict):
            continue
        history = context.get("conversation_history")
        if isinstance(history, list) and history:
            count += 1
    return count


def _tools_called(report: dict[str, Any]) -> set[str]:
    tools: set[str] = set()
    for result in report.get("results") or []:
        if not isinstance(result, dict):
            continue
        trace = result.get("tool_trace")
        if not isinstance(trace, dict):
            continue
        for tool in trace.get("called_tools") or []:
            if isinstance(tool, str) and tool:
                tools.add(tool)
    return tools


def _result_categories(report: dict[str, Any]) -> set[str]:
    categories: set[str] = set()
    for result in report.get("results") or []:
        if not isinstance(result, dict):
            continue
        category = result.get("category")
        if isinstance(category, str) and category:
            categories.add(category)
    return categories


def _tool_error_count(report: dict[str, Any]) -> int:
    total = 0
    for result in report.get("results") or []:
        if not isinstance(result, dict):
            continue
        trace = result.get("tool_trace")
        if not isinstance(trace, dict):
            continue
        error_count = trace.get("error_count")
        if isinstance(error_count, int):
            total += error_count
    return total


def _latencies(report: dict[str, Any]) -> list[int]:
    values: list[int] = []
    for result in report.get("results") or []:
        if not isinstance(result, dict):
            continue
        elapsed_ms = result.get("elapsed_ms")
        if isinstance(elapsed_ms, int):
            values.append(elapsed_ms)
    return values


def _p95(values: list[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * 0.95))))
    return ordered[index]


def _gate(
    gate_id: str,
    passed: bool,
    detail: str,
    actual: Any | None = None,
    expected: Any | None = None,
) -> dict[str, Any]:
    gate: dict[str, Any] = {
        "id": gate_id,
        "passed": passed,
        "detail": detail,
    }
    if actual is not None:
        gate["actual"] = actual
    if expected is not None:
        gate["expected"] = expected
    return gate


def _summary_counts(report: dict[str, Any]) -> tuple[int, int, int]:
    summary = report.get("summary")
    if isinstance(summary, dict):
        total = summary.get("total")
        passed = summary.get("passed")
        failed = summary.get("failed")
        if isinstance(total, int) and isinstance(passed, int) and isinstance(failed, int):
            return total, passed, failed

    results = [result for result in report.get("results") or [] if isinstance(result, dict)]
    total = len(results)
    passed = sum(1 for result in results if result.get("passed") is True)
    failed = total - passed
    return total, passed, failed


def _summary_int(summary: dict[str, Any], key: str) -> int:
    value = summary.get(key)
    if isinstance(value, int):
        return value
    return 0


def _nlm_counts(report: dict[str, Any]) -> dict[str, int]:
    summary = report.get("summary")
    if isinstance(summary, dict):
        return {
            "domains": _summary_int(summary, "domains"),
            "cases": _summary_int(summary, "cases"),
            "failed_domains": _summary_int(summary, "failed_domains"),
            "warning_domains": _summary_int(summary, "warning_domains"),
            "error_domains": _summary_int(summary, "error_domains"),
            "failed_cases": _summary_int(summary, "failed_cases"),
            "warning_cases": _summary_int(summary, "warning_cases"),
            "missing_review_cases": _summary_int(summary, "missing_review_cases"),
        }

    domains = [domain for domain in report.get("domains") or [] if isinstance(domain, dict)]
    failed_cases = report.get("failed_case_ids")
    warning_cases = report.get("warning_case_ids")
    missing_review_cases = report.get("missing_review_case_ids")
    return {
        "domains": len(domains),
        "cases": len(
            {
                case_id
                for domain in domains
                for case_id in domain.get("case_ids", [])
                if isinstance(case_id, str)
            }
        ),
        "failed_domains": sum(1 for domain in domains if domain.get("verdict") == "fail"),
        "warning_domains": sum(1 for domain in domains if domain.get("verdict") == "warn"),
        "error_domains": sum(1 for domain in domains if domain.get("status") == "error"),
        "failed_cases": len(failed_cases) if isinstance(failed_cases, list) else 0,
        "warning_cases": len(warning_cases) if isinstance(warning_cases, list) else 0,
        "missing_review_cases": (
            len(missing_review_cases) if isinstance(missing_review_cases, list) else 0
        ),
    }


def _same_report_source(nlm_report: dict[str, Any], report_path: Path | None) -> bool:
    if report_path is None:
        return True
    source = nlm_report.get("source_report_path")
    if not isinstance(source, str) or not source:
        return False
    return Path(source).name == report_path.name


def build_science_report(
    team: dict[str, Any],
    cases_doc: dict[str, Any],
    eval_report: dict[str, Any] | None,
    *,
    report_path: Path | None = None,
    nlm_report: dict[str, Any] | None = None,
    nlm_report_path: Path | None = None,
) -> dict[str, Any]:
    gates_config = team.get("readiness_gates")
    if not isinstance(gates_config, dict):
        raise ValueError("team file must contain readiness_gates")

    cases = _case_items(cases_doc)
    categories = _case_categories(cases)
    case_required_tools = _required_tools_from_cases(cases)
    required_categories = set(gates_config.get("required_categories") or [])
    required_tools = set(gates_config.get("required_tools") or [])
    min_eval_cases = int(gates_config.get("min_eval_cases", 1))
    min_tool_required_cases = int(gates_config.get("min_tool_required_cases", 0))
    min_history_context_cases = int(gates_config.get("min_history_context_cases", 0))
    min_pass_rate = float(gates_config.get("min_pass_rate", 1.0))
    max_failed_cases = int(gates_config.get("max_failed_cases", 0))
    max_tool_errors = int(gates_config.get("max_tool_errors", 0))
    max_p95_latency_ms = int(gates_config.get("max_p95_latency_ms", 90_000))
    nlm_validation_required = bool(gates_config.get("nlm_validation_required", False))
    max_nlm_failed_domains = int(gates_config.get("max_nlm_failed_domains", 0))
    max_nlm_error_domains = int(gates_config.get("max_nlm_error_domains", 0))
    max_nlm_failed_cases = int(gates_config.get("max_nlm_failed_cases", 0))
    max_nlm_missing_review_cases = int(gates_config.get("max_nlm_missing_review_cases", 0))

    missing_categories = sorted(required_categories - categories)
    missing_case_tools = sorted(required_tools - case_required_tools)
    gates: list[dict[str, Any]] = [
        _gate(
            "case_count",
            len(cases) >= min_eval_cases,
            "eval suite has enough cases",
            actual=len(cases),
            expected=f">= {min_eval_cases}",
        ),
        _gate(
            "tool_required_case_count",
            _tool_required_case_count(cases) >= min_tool_required_cases,
            "eval suite has enough cases that require tool traces",
            actual=_tool_required_case_count(cases),
            expected=f">= {min_tool_required_cases}",
        ),
        _gate(
            "history_context_case_count",
            _history_context_case_count(cases) >= min_history_context_cases,
            "eval suite has enough WhatsApp history/follow-up context cases",
            actual=_history_context_case_count(cases),
            expected=f">= {min_history_context_cases}",
        ),
        _gate(
            "category_coverage",
            not missing_categories,
            "all required risk categories are covered by cases",
            actual=sorted(categories),
            expected=sorted(required_categories),
        ),
        _gate(
            "case_tool_coverage",
            not missing_case_tools,
            "required tools are represented by case expectations",
            actual=sorted(case_required_tools),
            expected=sorted(required_tools),
        ),
    ]

    if eval_report is None:
        gates.extend(
            [
                _gate("eval_report_available", False, "no live eval report found"),
                _gate("live_eval_count", False, "live case count cannot be calculated without a report"),
                _gate(
                    "live_category_coverage",
                    False,
                    "live category coverage cannot be calculated without a report",
                ),
                _gate("pass_rate", False, "pass rate cannot be calculated without a report"),
                _gate("failed_cases", False, "failed cases cannot be calculated without a report"),
                _gate("tool_errors", False, "tool errors cannot be calculated without a report"),
                _gate("live_tool_coverage", False, "live tool calls cannot be scored without a report"),
                _gate("p95_latency", False, "latency cannot be calculated without a report"),
            ]
        )
    else:
        total, passed, failed = _summary_counts(eval_report)
        pass_rate = (passed / total) if total else 0.0
        tool_errors = _tool_error_count(eval_report)
        live_tools = _tools_called(eval_report)
        live_categories = _result_categories(eval_report)
        missing_live_tools = sorted(required_tools - live_tools)
        missing_live_categories = sorted(required_categories - live_categories)
        p95_latency = _p95(_latencies(eval_report))
        gates.extend(
            [
                _gate(
                    "eval_report_available",
                    True,
                    "latest live eval report loaded",
                    actual=str(report_path) if report_path else None,
                ),
                _gate(
                    "live_eval_count",
                    total >= min_eval_cases,
                    "latest live eval report has enough cases",
                    actual=total,
                    expected=f">= {min_eval_cases}",
                ),
                _gate(
                    "live_category_coverage",
                    not missing_live_categories,
                    "latest live eval report covers all required risk categories",
                    actual=sorted(live_categories),
                    expected=sorted(required_categories),
                ),
                _gate(
                    "pass_rate",
                    pass_rate >= min_pass_rate,
                    "live eval pass rate meets readiness threshold",
                    actual=round(pass_rate, 4),
                    expected=f">= {min_pass_rate}",
                ),
                _gate(
                    "failed_cases",
                    failed <= max_failed_cases,
                    "live eval has no excess failed cases",
                    actual=failed,
                    expected=f"<= {max_failed_cases}",
                ),
                _gate(
                    "tool_errors",
                    tool_errors <= max_tool_errors,
                    "tool traces have no excess tool errors",
                    actual=tool_errors,
                    expected=f"<= {max_tool_errors}",
                ),
                _gate(
                    "live_tool_coverage",
                    not missing_live_tools,
                    "latest live run exercised required tools",
                    actual=sorted(live_tools),
                    expected=sorted(required_tools),
                ),
                _gate(
                    "p95_latency",
                    p95_latency is not None and p95_latency <= max_p95_latency_ms,
                    "p95 latency stays within readiness budget",
                    actual=p95_latency,
                    expected=f"<= {max_p95_latency_ms}",
                ),
            ]
        )

    if nlm_validation_required:
        if nlm_report is None:
            gates.extend(
                [
                    _gate("nlm_validation_available", False, "no NLM validation report found"),
                    _gate(
                        "nlm_validation_source",
                        False,
                        "NLM validation source cannot be matched without a report",
                    ),
                    _gate(
                        "nlm_validation_errors",
                        False,
                        "NLM validation error count cannot be calculated without a report",
                    ),
                    _gate(
                        "nlm_validation_failures",
                        False,
                        "NLM validation failure count cannot be calculated without a report",
                    ),
                ]
            )
        else:
            nlm_summary = _nlm_counts(nlm_report)
            source_matches = _same_report_source(nlm_report, report_path)
            gates.extend(
                [
                    _gate(
                        "nlm_validation_available",
                        True,
                        "latest NLM validation report loaded",
                        actual=str(nlm_report_path) if nlm_report_path else None,
                    ),
                    _gate(
                        "nlm_validation_source",
                        source_matches,
                        "NLM validation was run against this live eval report",
                        actual=nlm_report.get("source_report_path"),
                        expected=str(report_path) if report_path else None,
                    ),
                    _gate(
                        "nlm_validation_errors",
                        nlm_summary["error_domains"] <= max_nlm_error_domains,
                        "NLM validation has no excess domain query errors",
                        actual=nlm_summary["error_domains"],
                        expected=f"<= {max_nlm_error_domains}",
                    ),
                    _gate(
                        "nlm_validation_failures",
                        nlm_summary["failed_domains"] <= max_nlm_failed_domains
                        and nlm_summary["failed_cases"] <= max_nlm_failed_cases,
                        "NLM validation has no excess failed domains or cases",
                        actual={
                            "failed_domains": nlm_summary["failed_domains"],
                            "failed_cases": nlm_summary["failed_cases"],
                            "warning_domains": nlm_summary["warning_domains"],
                            "warning_cases": nlm_summary["warning_cases"],
                        },
                        expected={
                            "failed_domains": f"<= {max_nlm_failed_domains}",
                            "failed_cases": f"<= {max_nlm_failed_cases}",
                        },
                    ),
                    _gate(
                        "nlm_review_coverage",
                        nlm_summary["missing_review_cases"] <= max_nlm_missing_review_cases,
                        "NLM validation reviewed every live eval response explicitly",
                        actual=nlm_summary["missing_review_cases"],
                        expected=f"<= {max_nlm_missing_review_cases}",
                    ),
                ]
            )

    ready = all(gate["passed"] for gate in gates)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "program": team.get("program"),
        "deadline_wita": team.get("deadline_wita"),
        "ready": ready,
        "report_path": str(report_path) if report_path else None,
        "gates": gates,
        "next_actions": [
            gate["detail"] for gate in gates if not gate["passed"]
        ],
    }


def _science_report_path(output_dir: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return output_dir / f"openclaw-whatsapp-science-{timestamp}.json"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team-file", type=Path, default=DEFAULT_TEAM_FILE)
    parser.add_argument("--case-file", type=Path, default=DEFAULT_CASE_FILE)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--nlm-report", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--require-report", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _parse_args()
    team = _load_json(args.team_file)
    cases_doc = _load_json(args.case_file)
    report_path = args.report or _latest_report_path(args.output_dir)
    eval_report = _load_json(report_path) if report_path is not None else None
    nlm_report_path = args.nlm_report or _latest_nlm_report_path(args.output_dir)
    nlm_report = _load_json(nlm_report_path) if nlm_report_path is not None else None

    science_report = build_science_report(
        team,
        cases_doc,
        eval_report,
        report_path=report_path,
        nlm_report=nlm_report,
        nlm_report_path=nlm_report_path,
    )
    if not args.no_write:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = _science_report_path(args.output_dir)
        output_path.write_text(
            json.dumps(science_report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        LOGGER.info("Science report written: %s", output_path)

    failed = [gate for gate in science_report["gates"] if not gate["passed"]]
    LOGGER.info(
        "OpenClaw WhatsApp science readiness: %s (%d/%d gates passed)",
        "READY" if science_report["ready"] else "NOT READY",
        len(science_report["gates"]) - len(failed),
        len(science_report["gates"]),
    )
    for gate in failed:
        LOGGER.info("Gate failed: %s - %s", gate["id"], gate["detail"])

    if args.require_report and not science_report["ready"]:
        raise SystemExit(1)
    raise SystemExit(0)


if __name__ == "__main__":
    main()
