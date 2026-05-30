#!/usr/bin/env python3
"""Run repeatable WhatsApp OpenClaw KB and tool-discipline probes.

The script is intentionally conservative: without --live it only validates the
case file. With --live it calls a local OpenClaw WhatsApp bridge and stores a
JSON report that can be used for the next fix loop.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx


LOGGER = logging.getLogger("openclaw_whatsapp_eval")
DEFAULT_CASE_FILE = Path(__file__).with_name("openclaw_whatsapp_eval_cases.json")
DEFAULT_OUTPUT_DIR = Path(".openclaw-evals")
DEFAULT_SECRET_FILE = Path("~/.openclaw/secrets/whatsapp-openclaw-bridge-secret").expanduser()
DEFAULT_TRACE_DIR = Path("~/.openclaw/agents/wa/sessions").expanduser()


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    category: str
    message: str
    context: dict[str, Any]
    must_contain_all: tuple[str, ...]
    must_contain_any: tuple[str, ...]
    must_not_contain_any: tuple[str, ...]
    max_words: int | None
    plain_text: bool
    required_tool_any: tuple[str, ...]
    max_tool_errors: int | None
    repair_hint: str


def _tuple_of_strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError("expected a list of strings")
    if not all(isinstance(item, str) for item in value):
        raise ValueError("expected a list of strings")
    return tuple(value)


def _load_cases(path: Path) -> list[EvalCase]:
    data = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = data.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError(f"{path} must contain a non-empty 'cases' list")

    cases: list[EvalCase] = []
    for raw in raw_cases:
        if not isinstance(raw, dict):
            raise ValueError("each eval case must be an object")
        case_id = raw.get("id")
        category = raw.get("category")
        message = raw.get("message")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("case id is required")
        if not isinstance(category, str) or not category:
            raise ValueError(f"{case_id}: category is required")
        if not isinstance(message, str) or not message:
            raise ValueError(f"{case_id}: message is required")
        context = raw.get("context") or {}
        if not isinstance(context, dict):
            raise ValueError(f"{case_id}: context must be an object")
        max_words = raw.get("max_words")
        if max_words is not None and not isinstance(max_words, int):
            raise ValueError(f"{case_id}: max_words must be an integer")
        max_tool_errors = raw.get("max_tool_errors")
        if max_tool_errors is not None and not isinstance(max_tool_errors, int):
            raise ValueError(f"{case_id}: max_tool_errors must be an integer")
        repair_hint = raw.get("repair_hint") or "Review prompt, KB routing, and tool policy."
        if not isinstance(repair_hint, str):
            raise ValueError(f"{case_id}: repair_hint must be a string")
        cases.append(
            EvalCase(
                case_id=case_id,
                category=category,
                message=message,
                context=context,
                must_contain_all=_tuple_of_strings(raw.get("must_contain_all")),
                must_contain_any=_tuple_of_strings(raw.get("must_contain_any")),
                must_not_contain_any=_tuple_of_strings(raw.get("must_not_contain_any")),
                max_words=max_words,
                plain_text=bool(raw.get("plain_text", True)),
                required_tool_any=_tuple_of_strings(raw.get("required_tool_any")),
                max_tool_errors=max_tool_errors,
                repair_hint=repair_hint,
            )
        )
    return cases


def _load_secret(secret_file: Path, secret_value: str | None) -> str:
    if secret_value:
        return secret_value.strip()
    secret = secret_file.read_text(encoding="utf-8").strip()
    if not secret:
        raise ValueError(f"{secret_file} is empty")
    return secret


def _word_count(reply: str) -> int:
    return len([word for word in reply.replace("\n", " ").split(" ") if word.strip()])


def _normalize_text(value: str) -> str:
    return (
        value.lower()
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )


def _score_reply(case: EvalCase, reply: str) -> list[str]:
    normalized = _normalize_text(reply)
    failures: list[str] = []

    for phrase in case.must_contain_all:
        if _normalize_text(phrase) not in normalized:
            failures.append(f"missing required phrase: {phrase}")

    if case.must_contain_any and not any(
        _normalize_text(phrase) in normalized for phrase in case.must_contain_any
    ):
        failures.append("missing one of: " + ", ".join(case.must_contain_any))

    forbidden = [
        phrase for phrase in case.must_not_contain_any if _normalize_text(phrase) in normalized
    ]
    if forbidden:
        failures.append("forbidden phrase present: " + ", ".join(forbidden))

    if case.max_words is not None and _word_count(reply) > case.max_words:
        failures.append(f"too long: {_word_count(reply)} words > {case.max_words}")

    if case.plain_text and ("```" in reply or "<tool" in normalized or "<system" in normalized):
        failures.append("not plain client-safe text")

    return failures


def _message_slug(message_id: str) -> str:
    slug = "".join(ch if ch.isalnum() else "-" for ch in message_id.strip())
    slug = "-".join(part for part in slug.split("-") if part)
    return slug[:64] or "message"


def _session_key(agent: str, phone: str, message_id: str | None = None) -> str:
    if not message_id:
        return f"agent:{agent}:whatsapp-meta-{phone}"
    return f"agent:{agent}:whatsapp-meta-{phone}-{_message_slug(message_id)}"


def _parse_trace_ts(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _tool_error_message(data: dict[str, Any]) -> str | None:
    output = data.get("output")
    if isinstance(output, str) and output:
        return output[:500]
    result = data.get("result")
    if result is None:
        return None
    try:
        return json.dumps(result, ensure_ascii=False)[:500]
    except TypeError:
        return str(result)[:500]


def _collect_tool_trace(
    trace_dir: Path,
    session_key: str,
    since: datetime,
) -> dict[str, Any]:
    if not trace_dir.exists():
        return {
            "available": False,
            "session_key": session_key,
            "called_tools": [],
            "call_count": 0,
            "result_count": 0,
            "error_count": 0,
            "errors": [],
        }

    called_tools: list[str] = []
    result_count = 0
    errors: list[dict[str, Any]] = []
    mtime_cutoff = since - timedelta(minutes=5)

    for path in trace_dir.glob("*.trajectory.jsonl"):
        if datetime.fromtimestamp(path.stat().st_mtime, UTC) < mtime_cutoff:
            continue
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("sessionKey") != session_key:
                    continue
                event_ts = _parse_trace_ts(event.get("ts"))
                if event_ts is None or event_ts < since:
                    continue
                data = event.get("data")
                if not isinstance(data, dict):
                    continue
                name = data.get("name")
                if not isinstance(name, str):
                    continue
                event_type = event.get("type")
                if event_type == "tool.call":
                    called_tools.append(name)
                    continue
                if event_type != "tool.result":
                    continue
                result_count += 1
                if data.get("isError") or data.get("status") == "failed":
                    errors.append(
                        {
                            "name": name,
                            "status": data.get("status"),
                            "message": _tool_error_message(data),
                        }
                    )

    return {
        "available": True,
        "session_key": session_key,
        "called_tools": sorted(set(called_tools)),
        "call_count": len(called_tools),
        "result_count": result_count,
        "error_count": len(errors),
        "errors": errors[:10],
    }


def _score_tool_trace(case: EvalCase, trace: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if not trace.get("available"):
        if case.required_tool_any or case.max_tool_errors is not None:
            failures.append("tool trace unavailable")
        return failures

    called_tools = set(trace.get("called_tools") or [])
    if case.required_tool_any and not any(
        tool in called_tools for tool in case.required_tool_any
    ):
        failures.append("missing required tool call: " + ", ".join(case.required_tool_any))

    raw_errors = trace.get("errors") or []
    ignored_errors = _ignored_tool_errors(case, trace, raw_errors)
    effective_error_count = max(0, len(raw_errors) - len(ignored_errors))
    trace["ignored_error_count"] = len(ignored_errors)
    trace["effective_error_count"] = effective_error_count

    if (
        case.max_tool_errors is not None
        and effective_error_count > case.max_tool_errors
    ):
        failures.append(f"tool errors: {effective_error_count} > {case.max_tool_errors}")

    return failures


def _ignored_tool_errors(
    case: EvalCase,
    trace: dict[str, Any],
    raw_errors: list[Any],
) -> list[dict[str, Any]]:
    """Classify controlled negative lookups that prove an obsolete code is absent."""
    if case.category != "kbli_kb":
        return []

    called_tools = set(trace.get("called_tools") or [])
    if "nuzantara-mcp.search_kbli" not in called_tools:
        return []

    ignored: list[dict[str, Any]] = []
    for raw_error in raw_errors:
        if not isinstance(raw_error, dict):
            continue
        if raw_error.get("name") != "nuzantara-mcp.inspect_kbli":
            continue
        message = str(raw_error.get("message") or "").lower()
        if "http 404" in message and "kbli code" in message and "not found" in message:
            ignored.append(raw_error)
    return ignored


def _is_transient_tool_transport_failure(result: dict[str, Any]) -> bool:
    failures = result.get("failures") or []
    if not failures:
        return False
    if any(not str(failure).startswith("tool errors:") for failure in failures):
        return False

    trace = result.get("tool_trace") or {}
    errors = trace.get("errors") or []
    return any("Transport closed" in str(error.get("message", "")) for error in errors)


def _payload_for_case(case: EvalCase, args: argparse.Namespace) -> dict[str, Any]:
    message_id = f"eval.{case.case_id}.{int(time.time())}"
    return {
        "agent": args.agent,
        "model": args.model,
        "thinking": args.thinking,
        "persona": args.persona,
        "autonomy_mode": args.autonomy_mode,
        "channel": "whatsapp",
        "phone": args.phone,
        "sender_name": "Codex Eval",
        "message_id": message_id,
        "text": case.message,
        "context": case.context,
    }


async def _call_bridge(
    client: httpx.AsyncClient,
    bridge_url: str,
    secret: str,
    case: EvalCase,
    args: argparse.Namespace,
) -> dict[str, Any]:
    started_at = datetime.now(UTC)
    started = time.perf_counter()
    payload = _payload_for_case(case, args)
    response = await client.post(
        bridge_url,
        json=payload,
        headers={
            "Authorization": f"Bearer {secret}",
            "X-Request-ID": f"openclaw-eval-{case.case_id}",
        },
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    if response.status_code >= 400:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:1000]}")
    data = response.json()
    reply = data.get("reply")
    if not isinstance(reply, str) or not reply.strip():
        raise ValueError(f"{case.case_id}: bridge returned no reply")
    failures = _score_reply(case, reply.strip())
    tool_trace: dict[str, Any] | None = None
    if args.trace_tools:
        tool_trace = _collect_tool_trace(
            args.trace_dir,
            _session_key(args.agent, args.phone, payload["message_id"]),
            started_at,
        )
        failures.extend(_score_tool_trace(case, tool_trace))
    return {
        "id": case.case_id,
        "category": case.category,
        "passed": not failures,
        "failures": failures,
        "repair_hint": case.repair_hint if failures else None,
        "elapsed_ms": elapsed_ms,
        "reply": reply.strip(),
        "tool_trace": tool_trace,
    }


def _report_path(output_dir: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return output_dir / f"openclaw-whatsapp-eval-{timestamp}.json"


async def _run_live(args: argparse.Namespace, cases: list[EvalCase]) -> dict[str, Any]:
    secret = _load_secret(args.secret_file, args.secret)
    selected_cases = _select_cases(cases, case_ids=set(args.case_id or ()), max_cases=args.max_cases)
    timeout = httpx.Timeout(args.timeout_seconds)
    results: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=timeout) as client:
        for case in selected_cases:
            LOGGER.info("Running %s (%s)", case.case_id, case.category)
            try:
                result = await _call_bridge(client, args.bridge_url, secret, case, args)
            except Exception as exc:
                result = {
                    "id": case.case_id,
                    "category": case.category,
                    "passed": False,
                    "failures": [f"bridge error: {exc}"],
                    "repair_hint": case.repair_hint,
                    "elapsed_ms": None,
                    "reply": None,
                    "tool_trace": None,
                }
            for retry_index in range(args.transient_tool_retries):
                if not _is_transient_tool_transport_failure(result):
                    break
                LOGGER.warning(
                    "Retrying %s after transient tool transport error (%d/%d)",
                    case.case_id,
                    retry_index + 1,
                    args.transient_tool_retries,
                )
                try:
                    result = await _call_bridge(client, args.bridge_url, secret, case, args)
                except Exception as exc:
                    result = {
                        "id": case.case_id,
                        "category": case.category,
                        "passed": False,
                        "failures": [f"bridge error: {exc}"],
                        "repair_hint": case.repair_hint,
                        "elapsed_ms": None,
                        "reply": None,
                        "tool_trace": None,
                    }
                result["transient_retry_count"] = retry_index + 1
            results.append(result)

    passed = sum(1 for result in results if result["passed"])
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "bridge_url": args.bridge_url,
        "agent": args.agent,
        "model": args.model,
        "thinking": args.thinking,
        "persona": args.persona,
        "autonomy_mode": args.autonomy_mode,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
        },
        "results": results,
    }


def _select_cases(
    cases: list[EvalCase],
    *,
    case_ids: set[str],
    max_cases: int | None,
) -> list[EvalCase]:
    selected_cases = cases
    if case_ids:
        available = {case.case_id for case in cases}
        missing = sorted(case_ids - available)
        if missing:
            raise ValueError("unknown case id: " + ", ".join(missing))
        selected_cases = [case for case in cases if case.case_id in case_ids]
    if max_cases:
        selected_cases = selected_cases[:max_cases]
    return selected_cases


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Call the bridge instead of dry-run validation")
    parser.add_argument("--case-file", type=Path, default=DEFAULT_CASE_FILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--bridge-url", default="http://127.0.0.1:8789/reply")
    parser.add_argument("--secret-file", type=Path, default=DEFAULT_SECRET_FILE)
    parser.add_argument("--secret", default=None, help="Bridge secret override; prefer --secret-file")
    parser.add_argument("--agent", default="wa")
    parser.add_argument("--model", default="openai/gpt-5.5")
    parser.add_argument("--thinking", default="high")
    parser.add_argument("--persona", default="zantara_whatsapp_v1")
    parser.add_argument("--autonomy-mode", default="supervised_autonomous")
    parser.add_argument("--phone", default="6280000000000")
    parser.add_argument("--case-id", action="append", default=None, help="Run only this case id; repeatable")
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--transient-tool-retries", type=int, default=1)
    parser.add_argument("--trace-dir", type=Path, default=DEFAULT_TRACE_DIR)
    parser.add_argument(
        "--trace-tools",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Score OpenClaw trajectory tool calls in addition to reply text",
    )
    return parser.parse_args()


async def _async_main() -> int:
    args = _parse_args()
    cases = _load_cases(args.case_file)
    LOGGER.info("Loaded %d eval cases from %s", len(cases), args.case_file)

    if not args.live:
        LOGGER.info("Dry run only. Add --live to call %s", args.bridge_url)
        return 0

    report = await _run_live(args, cases)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = _report_path(args.output_dir)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    summary = report["summary"]
    LOGGER.info(
        "OpenClaw WhatsApp eval: %s/%s passed, report=%s",
        summary["passed"],
        summary["total"],
        output_path,
    )
    return 0 if summary["failed"] == 0 else 1


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    raise SystemExit(asyncio.run(_async_main()))


if __name__ == "__main__":
    main()
