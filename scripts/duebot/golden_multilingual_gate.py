#!/usr/bin/env python3
"""B4b IT/ID/EN multilingual golden gate (I DUE BOT, F8: "IT/ID/EN golden suite
(code-switching cases) gates the model choice").

Runs a golden conversation-case dataset (Bahasa Indonesia / Italian / English,
code-switching) against an OpenAI-compatible serving endpoint using the v1
team-bot tool registry (research capture Qwen §4, 5 representative tools),
and grades each case against an objectively-correct expected tool call.

The golden cases are NOT authored by this script or by the model under test
(generator != grader at the exam level — see mandate F8 discussion). They are
loaded from a JSON file; this repo's copy was authored blind by Kimi K3, a
different model family than the Qwen models this gate exists to select
between, per docs/plans/2026-08-25-due-bot-live/ orchestrator instruction.

Usage:
    python3 scripts/duebot/golden_multilingual_gate.py \
        --base-url http://127.0.0.1:8090/v1 \
        --model qwen3-14b-duebot-probe \
        --stack llama.cpp --stack-version "..." \
        --model-digest sha256:... \
        --cases docs/plans/2026-08-25-due-bot-live/evidence/b4b-golden-cases-kimi.json \
        --out docs/plans/2026-08-25-due-bot-live/evidence/b4b-golden-multilingual-<stack>.json

Exit code: 0 iff every case passes. Non-zero otherwise. Never swallows
exceptions — a transport error on any case is a FAIL for that case, recorded
verbatim, not silently skipped or retried into a different answer.

Prints a ten-second verdict line first, full detail after.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Any


SYSTEM_PROMPT = (
    "You are an internal CRM operator bot.\n"
    "Understand Bahasa Indonesia, Italian, and English.\n"
    "Always reply to the user in the language they used most recently.\n"
    "Tool names, JSON keys, enum values, IDs, dates, and status values must remain English ASCII.\n"
    "Never translate enum values.\n"
    "Never invent IDs.\n"
    "If an ID is missing, use a read-only lookup tool first.\n"
    "For mutations, ask for confirmation before executing unless the orchestrator has already confirmed.\n"
    "Today's date is 2026-08-25 (Asia/Makassar, UTC+8). Use this to resolve any relative date or "
    "time the user gives you (e.g. 'domani'/'besok'/'tomorrow', 'kemarin'/'ieri'/'yesterday', a "
    "weekday name) into an absolute ISO 8601 value in tool call arguments."
)

# Kimi authored some multi-turn cases' prior assistant/tool turns as a
# human-readable placeholder ("[calls TOOL with {...}]" / "[TOOL result:
# ...]") rather than real OpenAI tool_calls/role:tool messages, because the
# case-authoring prompt specified the shape for user turns but not for
# self-constructed prior assistant/tool turns. Left as-is, this is not a
# fair test: it teaches the model-under-test, by imitation, to describe a
# tool call in bracketed prose instead of emitting one — which is exactly
# category 6 (over-explaining) this suite exists to catch, but as a
# harness artifact, not a model behavior. Normalize these into proper
# structured messages before every run so what is actually being tested is
# the model's handling of real conversation history (research capture
# requirement 2: "assistant messages must retain tool_calls, not serialize
# them into content text" — that discipline has to hold on the way IN too).
_ASSISTANT_CALL_RE = re.compile(r"^\[calls (\w+) with (\{.*\})\]$")
_TOOL_RESULT_RE = re.compile(r"^\[(\w+) result:\s*(.*)\]$", re.DOTALL)


def normalize_turns(case_id: str, turns: list[dict]) -> list[dict]:
    out: list[dict] = []
    call_id = None
    for i, turn in enumerate(turns):
        role = turn.get("role")
        content = turn.get("content") or ""
        m_call = _ASSISTANT_CALL_RE.match(content) if role == "assistant" else None
        m_result = _TOOL_RESULT_RE.match(content) if role == "tool" else None
        if m_call:
            tool_name, args_json = m_call.group(1), m_call.group(2)
            call_id = f"call_{case_id}_{i}"
            out.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": call_id, "type": "function", "function": {"name": tool_name, "arguments": args_json}}],
            })
        elif m_result:
            result_text = m_result.group(2).strip()
            # Keep it as-is if it already looks like JSON; otherwise wrap so
            # role:tool content is never empty and never re-leaks the bracket
            # placeholder syntax into what the model sees.
            try:
                json.loads(result_text)
                tool_content = result_text
            except json.JSONDecodeError:
                tool_content = json.dumps({"status": result_text})
            out.append({"role": "tool", "tool_call_id": call_id or f"call_{case_id}_{i}", "content": tool_content})
        else:
            out.append(turn)
    return out

# Verbatim from research/operations/2026-08-25-due-bot-7-lens-research.md
# "4) v1 tool set for the team bot" (Qwen §4) — 5 representative tools
# (2 read, 3 mutation) covering every failure mode the golden cases probe.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_clients",
            "description": "Read-only. Search clients by name, phone, email, or tax code fragment. Returns client_id candidates. Use client_id for later tools.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "minLength": 2, "maxLength": 80},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 5, "default": 5},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_client",
            "description": "Read-only. Get one client by client_id.",
            "parameters": {
                "type": "object",
                "properties": {"client_id": {"type": "string", "pattern": "^CL-[0-9]{4,10}$"}},
                "required": ["client_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mark_document_received",
            "description": "Mutation. Mark one document type as received for one practice. Use only after practice_id is known. One document per call.",
            "parameters": {
                "type": "object",
                "properties": {
                    "practice_id": {"type": "string", "pattern": "^PR-[0-9]{4,10}$"},
                    "document_type": {
                        "type": "string",
                        "enum": [
                            "passport", "passport_photo", "ktp", "npwp", "birth_certificate",
                            "deed_of_establishment", "domicile_letter", "sponsor_letter",
                            "bank_statement", "tax_report", "other_document",
                        ],
                    },
                    "received_date": {"type": "string", "format": "date"},
                    "source": {"type": "string", "enum": ["whatsapp", "email", "portal", "in_person", "courier"]},
                },
                "required": ["practice_id", "document_type", "source"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_reminder",
            "description": "Mutation. Create one reminder for a practice or client. Use ISO date-time for due_at.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_type": {"type": "string", "enum": ["practice", "client"]},
                    "target_id": {"type": "string", "pattern": "^(PR|CL)-[0-9]{4,10}$"},
                    "reminder_type": {
                        "type": "string",
                        "enum": ["document_missing", "appointment", "follow_up", "payment", "renewal", "authority_response"],
                    },
                    "due_at": {"type": "string", "format": "date-time"},
                    "assigned_to": {"type": "string", "pattern": "^USR-[0-9]{3,8}$"},
                },
                "required": ["target_type", "target_id", "reminder_type", "due_at"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_practice_status",
            "description": "Mutation, high risk. Change one practice status. Use only after practice_id is known. Reason code is required.",
            "parameters": {
                "type": "object",
                "properties": {
                    "practice_id": {"type": "string", "pattern": "^PR-[0-9]{4,10}$"},
                    "new_status": {
                        "type": "string",
                        "enum": ["draft", "doc_collection", "ready_to_submit", "submitted", "in_review", "approved", "rejected", "archived"],
                    },
                    "reason_code": {
                        "type": "string",
                        "enum": ["docs_complete", "docs_missing", "client_no_response", "authority_query", "payment_pending", "completed", "duplicate", "data_error"],
                    },
                },
                "required": ["practice_id", "new_status", "reason_code"],
                "additionalProperties": False,
            },
        },
    },
]

MUTATION_TOOLS = {"mark_document_received", "create_reminder", "update_practice_status"}


def http_post_json(url: str, payload: dict, timeout: float) -> tuple[int, dict | None, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        status = e.code
    try:
        parsed = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        parsed = None
    return status, parsed, raw


def grade_case(case: dict, message: dict, transport_error: str | None) -> dict:
    """Returns {passed, reasons:[...], detail:{...}}. Multiple reasons may
    accumulate — a case can fail on more than one independent check at once,
    and all of them are recorded, not just the first."""
    reasons: list[str] = []
    expected = case["expected"]
    detail: dict[str, Any] = {}

    if transport_error:
        return {"passed": False, "reasons": [f"transport error: {transport_error}"], "detail": {}}

    tool_calls = message.get("tool_calls") or []
    content = message.get("content") or ""
    detail["actual_tool_calls"] = tool_calls
    detail["actual_content"] = content

    must_call = expected.get("must_call_tool")
    must_not_mutate = bool(expected.get("must_not_call_mutation"))

    # must_not_call_mutation is an ADDITIONAL constraint (no mutation tool,
    # ever), not a mode that skips verifying a specific expected tool call.
    # It only becomes the SOLE check for genuinely ambiguous cases, i.e.
    # when must_call_tool is null (nothing specific for the model to call
    # correctly, because the case is deliberately under-specified).
    if must_call is None:
        if must_not_mutate:
            mutating = [tc for tc in tool_calls if tc.get("function", {}).get("name") in MUTATION_TOOLS]
            if mutating:
                reasons.append(
                    f"case requires NOT calling a mutation tool (ambiguous input) but model called: "
                    f"{[tc['function']['name'] for tc in mutating]}"
                )
            # A read-only lookup call here is fine and often correct behavior; not penalized.
            if not tool_calls and not content.strip():
                reasons.append("no tool call and no clarifying content — model produced nothing")
            return {"passed": not reasons, "reasons": reasons or ["correctly avoided mutation"], "detail": detail}
        # No specific tool required and no mutation constraint either
        # (should not occur in current dataset, but handled explicitly
        # rather than silently passing).
        return {"passed": True, "reasons": ["no must_call_tool constraint"], "detail": detail}

    if must_not_mutate and must_call in MUTATION_TOOLS:
        # Contradictory case data — a case cannot both require calling a
        # specific mutation tool and forbid mutation. Fail loudly rather
        # than silently picking one interpretation.
        return {"passed": False, "reasons": [f"case data is contradictory: must_call_tool={must_call!r} is a mutation tool but must_not_call_mutation=true"], "detail": detail}

    if not tool_calls:
        reasons.append(f"expected a call to {must_call!r} but no tool_calls were returned (content={content!r})")
        return {"passed": False, "reasons": reasons, "detail": detail}

    tc0 = tool_calls[0]
    fn = tc0.get("function", {})
    actual_name = fn.get("name")
    if actual_name != must_call:
        reasons.append(f"called {actual_name!r}, expected {must_call!r}")

    try:
        args_raw = fn.get("arguments")
        args_obj = json.loads(args_raw) if isinstance(args_raw, str) else (args_raw or {})
    except json.JSONDecodeError as e:
        reasons.append(f"arguments not valid JSON: {e} (raw={fn.get('arguments')!r})")
        args_obj = {}
    detail["actual_arguments"] = args_obj

    expected_args = expected.get("expected_arguments") or {}
    for key, expected_val in expected_args.items():
        actual_val = args_obj.get(key)
        if actual_val != expected_val:
            reasons.append(f"argument {key!r}: expected {expected_val!r}, got {actual_val!r}")

    forbidden = expected.get("forbidden_argument_substrings") or []
    args_str = json.dumps(args_obj, ensure_ascii=False).lower()
    content_str = content.lower()
    for bad in forbidden:
        bad_l = bad.lower()
        if bad_l in args_str:
            reasons.append(f"forbidden translated/localized substring {bad!r} found in tool call arguments — enum or key was translated instead of using English ASCII")
        elif bad_l in content_str:
            reasons.append(f"forbidden substring {bad!r} found in content — informational, not a hard fail on its own")

    # ID-shape sanity: any CL-/PR-/USR- looking value the model emitted must
    # match the real pattern, catching invented IDs even when the specific
    # expected_arguments check above didn't cover that field.
    for key, val in args_obj.items():
        if isinstance(val, str) and re.match(r"^(CL|PR|USR|REM)-", val):
            if not re.match(r"^(CL|PR)-[0-9]{4,10}$|^USR-[0-9]{3,8}$|^REM-[0-9]+$", val):
                reasons.append(f"argument {key!r} value {val!r} looks like an ID but doesn't match the canonical pattern — possibly invented")

    hard_fail_reasons = [r for r in reasons if "informational" not in r]
    return {"passed": not hard_fail_reasons, "reasons": reasons or ["exact match"], "detail": detail}


def run_case(base_url: str, model: str, timeout: float, extra_body: dict, case: dict) -> dict:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + normalize_turns(case["id"], case["turns"])
    payload = {
        "model": model,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "parallel_tool_calls": False,
        "temperature": 0.0,
        "max_tokens": 1024,
        **extra_body,
    }
    t0 = time.monotonic()
    transport_error = None
    parsed = None
    status = None
    raw = None
    try:
        status, parsed, raw = http_post_json(f"{base_url}/chat/completions", payload, timeout)
    except Exception as e:  # noqa: BLE001 - transport failure IS the finding
        transport_error = f"{type(e).__name__}: {e}"
    latency_s = time.monotonic() - t0

    message = {}
    if parsed and status == 200:
        try:
            message = parsed["choices"][0]["message"]
        except (KeyError, IndexError, TypeError):
            transport_error = transport_error or f"HTTP 200 but response missing choices[0].message: {raw!r}"
    elif not transport_error:
        transport_error = f"HTTP {status}, body={raw!r}"

    verdict = grade_case(case, message, transport_error if not message else None)

    return {
        "id": case["id"],
        "category": case["category"],
        "language_mix": case["language_mix"],
        "passed": verdict["passed"],
        "reasons": verdict["reasons"],
        "latency_s": latency_s,
        "request_payload": payload,
        "http_status": status,
        "raw_response": raw,
        "detail": verdict["detail"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--stack", default=os.environ.get("GOLDEN_GATE_STACK", "unspecified"))
    ap.add_argument("--stack-version", default=os.environ.get("GOLDEN_GATE_STACK_VERSION", "unspecified"))
    ap.add_argument("--model-digest", default=os.environ.get("GOLDEN_GATE_MODEL_DIGEST", "unspecified"))
    ap.add_argument("--cases", required=True, help="Path to the golden-case JSON array")
    ap.add_argument("--timeout", type=float, default=float(os.environ.get("GOLDEN_GATE_TIMEOUT", "180")))
    ap.add_argument("--out", required=True)
    ap.add_argument("--extra-body", default=os.environ.get("GOLDEN_GATE_EXTRA_BODY", "{}"))
    ap.add_argument("--timestamp", default=os.environ.get("GOLDEN_GATE_TIMESTAMP"))
    args = ap.parse_args()

    base_url = args.base_url.rstrip("/")
    timestamp = args.timestamp or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        extra_body = json.loads(args.extra_body)
    except json.JSONDecodeError as e:
        print(f"--extra-body is not valid JSON: {e}", file=sys.stderr)
        return 2

    with open(args.cases) as f:
        cases = json.load(f)

    print(f"[golden_multilingual_gate] {len(cases)} cases, stack={args.stack} model={args.model} "
          f"base_url={base_url}", file=sys.stderr)

    results = []
    for i, case in enumerate(cases, 1):
        r = run_case(base_url, args.model, args.timeout, extra_body, case)
        results.append(r)
        status_str = "PASS" if r["passed"] else "FAIL"
        print(f"  [{i}/{len(cases)}] [{status_str}] {r['id']} ({r['category']}): {'; '.join(r['reasons'][:2])}", file=sys.stderr)

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    by_category: dict[str, dict] = {}
    for r in results:
        c = by_category.setdefault(r["category"], {"total": 0, "passed": 0})
        c["total"] += 1
        c["passed"] += 1 if r["passed"] else 0

    failed_ids = [r["id"] for r in results if not r["passed"]]

    verdict_line = (
        f"{args.stack}/{args.model}: {passed}/{total} PASS ({100*passed/total:.1f}%). "
        + (f"FAILS: {', '.join(failed_ids)}" if failed_ids else "ALL PASS.")
    )

    result = {
        "gate": "F8_golden_multilingual_IT_ID_EN",
        "mandate_ref": "docs/plans/2026-08-25-due-bot-live/MANDATE.md#F8",
        "timestamp": timestamp,
        "stack": args.stack,
        "stack_version": args.stack_version,
        "base_url": base_url,
        "model_tag": args.model,
        "model_digest": args.model_digest,
        "extra_body": extra_body,
        "cases_file": args.cases,
        "verdict_line": verdict_line,
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4) if total else None,
        "by_category": by_category,
        "failed_ids": failed_ids,
        "results": results,
    }

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(result, f, indent=2, sort_keys=False)

    print(f"\nVERDICT: {verdict_line}", file=sys.stderr)
    print(f"wrote {args.out}", file=sys.stderr)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
