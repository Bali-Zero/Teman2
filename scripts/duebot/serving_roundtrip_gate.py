#!/usr/bin/env python3
"""B4a serving round-trip gate (I DUE BOT, F8 binding gate).

Empirical probe against an OpenAI-compatible /v1/chat/completions endpoint. It
proves — or refutes — that the serving layer round-trips native `tools` /
`tool_calls` / `role:"tool"` WITHOUT flattening them into prompt text, per
docs/plans/2026-08-25-due-bot-live/MANDATE.md F8 and
research/operations/2026-08-25-due-bot-7-lens-research.md ("What llama.cpp /
MLX / Ollama must get right", items 1,2,3,5).

Usage:
    python3 scripts/duebot/serving_roundtrip_gate.py \
        --base-url http://127.0.0.1:8090/v1 \
        --model qwen3-8b-duebot-probe \
        --stack llama.cpp \
        --stack-version "0.2.0 (build 10566, commit bb4caa754)" \
        --model-digest sha256:a3de86cd1c132c822487ededd47a324c50491393e6565cd14bafa40d0b8e686f \
        --out docs/plans/2026-08-25-due-bot-live/evidence/b4a-serving-roundtrip.json

Env vars mirror every --flag as SERVING_GATE_<FLAG> (upper snake) for cron/CI use.

Exit code: 0 iff every property passes. Non-zero otherwise, with the failing
property names printed to stderr. Never swallows exceptions — a transport
error on any probe is a FAIL for that property, recorded with its exception
text, not silently skipped.

This script does not judge model INTELLIGENCE. It judges whether the wire
format is preserved. A model that calls the wrong tool but does so via a
structured tool_calls object still PASSES this gate; a model that calls the
right tool but the server hands it back as a text blob inside `content`
FAILS it — because that is exactly the failure mode F8 is gating against.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any


TOOL_GET_WEATHER = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name, e.g. Denpasar"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
            },
            "required": ["city"],
            "additionalProperties": False,
        },
    },
}

TOOL_GET_TIME = {
    "type": "function",
    "function": {
        "name": "get_time",
        "description": "Get the current time for a timezone.",
        "parameters": {
            "type": "object",
            "properties": {
                "timezone": {"type": "string", "description": "IANA timezone, e.g. Asia/Makassar"},
            },
            "required": ["timezone"],
            "additionalProperties": False,
        },
    },
}


def http_post_json(url: str, payload: dict, timeout: float) -> tuple[int, dict | None, str]:
    """POST JSON, return (status_code, parsed_json_or_None, raw_text).

    Never raises on HTTP-level errors (4xx/5xx) — those are recorded as a
    result, not an exception. Only genuine transport failures (connection
    refused, DNS, timeout) propagate as an exception to the caller, which is
    exactly what a FAIL-with-verbatim-error should look like: it is not
    something to catch-and-guess about.
    """
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
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


class Property:
    """One named pass/fail gate property with its evidence."""

    def __init__(self, name: str):
        self.name = name
        self.passed: bool | None = None
        self.reason: str = ""
        self.evidence: dict[str, Any] = {}
        self.latency_s: float | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "reason": self.reason,
            "latency_s": self.latency_s,
            "evidence": self.evidence,
        }


def probe_a_native_tool_calls(base_url: str, model: str, timeout: float, extra_body: dict) -> Property:
    """(a) native `tools` accepted, reply carries structured `tool_calls` —
    NOT a JSON blob inside `content`."""
    p = Property("a_native_tool_calls_structured")
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "What is the weather in Denpasar right now? Use the get_weather tool.",
            }
        ],
        "tools": [TOOL_GET_WEATHER],
        "tool_choice": "auto",
        "parallel_tool_calls": False,
        "temperature": 0.0,
        "max_tokens": 1024,
        **extra_body,
    }
    t0 = time.monotonic()
    try:
        status, parsed, raw = http_post_json(f"{base_url}/chat/completions", payload, timeout)
    except Exception as e:  # noqa: BLE001 - transport failure IS the finding
        p.passed = False
        p.reason = f"transport error: {type(e).__name__}: {e}"
        p.latency_s = time.monotonic() - t0
        return p
    p.latency_s = time.monotonic() - t0
    p.evidence["request"] = payload
    p.evidence["http_status"] = status
    p.evidence["raw_response"] = raw
    p.evidence["parsed_response"] = parsed

    if status != 200 or not parsed:
        p.passed = False
        p.reason = f"HTTP {status}, body not valid JSON or empty"
        return p

    try:
        choice0 = parsed["choices"][0]
        message = choice0["message"]
    except (KeyError, IndexError, TypeError) as e:
        p.passed = False
        p.reason = f"response missing choices[0].message: {e}"
        return p

    tool_calls = message.get("tool_calls")
    content = message.get("content")
    reasoning = message.get("reasoning") or message.get("reasoning_content")
    finish_reason = choice0.get("finish_reason")

    if not tool_calls:
        # Did the model try to call the tool anyway, but as text? That is
        # precisely the failure this property exists to catch — name it.
        if content and ("get_weather" in str(content) or "tool_call" in str(content).lower()):
            p.passed = False
            p.reason = (
                "tool_calls is empty/absent but content contains what looks like a "
                "flattened tool-call — the server serialized the call into prompt "
                "text instead of returning a structured tool_calls object"
            )
        elif finish_reason == "length" and reasoning:
            p.passed = False
            p.reason = (
                f"NOT a round-trip failure — generation hit max_tokens ({finish_reason!r}) "
                f"while still inside the reasoning/thinking trace, before emitting any "
                f"tool_calls or content. This is a token-budget/thinking-mode confound, "
                f"not evidence the wire format flattens tools. reasoning_len={len(str(reasoning))} chars. "
                f"Retest with thinking disabled and/or a larger max_tokens."
            )
        else:
            p.passed = False
            p.reason = f"tool_calls is empty/absent and content shows no tool-call attempt at all (finish_reason={finish_reason!r})"
        return p

    # tool_calls present — verify it is a structured object, not a string
    # containing JSON (which some proxies do to "look" compliant).
    if not isinstance(tool_calls, list) or not isinstance(tool_calls[0], dict):
        p.passed = False
        p.reason = f"tool_calls is present but not a list[dict]: {type(tool_calls)}"
        return p

    tc0 = tool_calls[0]
    fn = tc0.get("function", {})
    name = fn.get("name")
    arguments = fn.get("arguments")
    call_id = tc0.get("id")

    if name != "get_weather":
        p.passed = False
        p.reason = f"tool_calls[0].function.name = {name!r}, expected 'get_weather'"
        return p

    if not call_id:
        p.passed = False
        p.reason = "tool_calls[0].id is missing/empty — cannot be referenced by a role:tool reply"
        return p

    try:
        args_obj = json.loads(arguments) if isinstance(arguments, str) else arguments
    except json.JSONDecodeError as e:
        p.passed = False
        p.reason = f"tool_calls[0].function.arguments is not valid JSON: {e}"
        return p

    if not isinstance(args_obj, dict) or "city" not in args_obj:
        p.passed = False
        p.reason = f"tool_calls[0].function.arguments parsed but missing 'city': {args_obj!r}"
        return p

    p.passed = True
    p.reason = (
        f"structured tool_calls[0] = name={name!r} id={call_id!r} "
        f"arguments={args_obj!r}; finish_reason={choice0.get('finish_reason')!r}"
    )
    p.evidence["tool_call_id"] = call_id
    p.evidence["tool_call_name"] = name
    p.evidence["tool_call_arguments"] = args_obj
    return p


def probe_b_history_roundtrip(base_url: str, model: str, timeout: float, tool_call_id: str | None, extra_body: dict) -> Property:
    """(b) feeding history back with an assistant message carrying
    `tool_calls` is preserved, not re-serialized into content text.

    We construct a synthetic prior turn (assistant tool_calls + tool result)
    and ask the model a follow-up that can ONLY be answered correctly if the
    server actually fed the structured history back to the model rather than
    dropping/mangling it. We also inspect whether the server's own history
    handling silently rewrites the tool_calls we sent.
    """
    p = Property("b_history_tool_calls_preserved")
    synth_call_id = tool_call_id or "call_probe_b_0001"
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "What is the weather in Denpasar? Use get_weather."},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": synth_call_id,
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": json.dumps({"city": "Denpasar", "unit": "celsius"}),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": synth_call_id,
                "content": json.dumps({"city": "Denpasar", "temp_c": 31, "condition": "humid, partly cloudy"}),
            },
            {
                "role": "user",
                "content": "Given that result, tell me the temperature in Celsius in one short sentence. Do not call any more tools.",
            },
        ],
        "tools": [TOOL_GET_WEATHER],
        "tool_choice": "auto",
        "parallel_tool_calls": False,
        "temperature": 0.0,
        "max_tokens": 512,
        **extra_body,
    }
    t0 = time.monotonic()
    try:
        status, parsed, raw = http_post_json(f"{base_url}/chat/completions", payload, timeout)
    except Exception as e:  # noqa: BLE001
        p.passed = False
        p.reason = f"transport error: {type(e).__name__}: {e}"
        p.latency_s = time.monotonic() - t0
        return p
    p.latency_s = time.monotonic() - t0
    p.evidence["request"] = payload
    p.evidence["http_status"] = status
    p.evidence["raw_response"] = raw
    p.evidence["parsed_response"] = parsed

    if status != 200 or not parsed:
        p.passed = False
        p.reason = f"server REJECTED a history containing assistant.tool_calls + role:tool — HTTP {status}"
        return p

    try:
        message = parsed["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as e:
        p.passed = False
        p.reason = f"response missing choices[0].message: {e}"
        return p

    content = (message.get("content") or "")
    tool_calls = message.get("tool_calls")

    # PASS condition: the server accepted the structured history (200, well
    # formed) AND the model actually used the injected tool result (mentions
    # 31, or "31°C"/"31 c" style) rather than either refusing or re-calling
    # the tool because it never actually saw the prior turn.
    mentions_result = "31" in content
    if tool_calls:
        p.passed = False
        p.reason = (
            "model re-called a tool instead of answering from the fed-back "
            "history — either it never received the prior tool_calls/tool "
            "turns intact, or the server dropped them"
        )
        return p

    if not mentions_result:
        p.passed = False
        p.reason = (
            f"HTTP 200 but the answer does not reference the injected tool "
            f"result (31°C) — content={content!r}. The server accepted the "
            f"structured history but the model output suggests it was not "
            f"actually conditioned on it."
        )
        return p

    p.passed = True
    p.reason = f"HTTP 200, structured history round-tripped, answer references injected result: content={content!r}"
    return p


def probe_c_tool_role_accepted(base_url: str, model: str, timeout: float, extra_body: dict) -> Property:
    """(c) role:"tool" messages with a matching tool_call_id are accepted."""
    p = Property("c_tool_role_accepted")
    call_id = "call_probe_c_0001"
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "What time is it in Asia/Makassar? Use get_time."},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": "get_time",
                            "arguments": json.dumps({"timezone": "Asia/Makassar"}),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": call_id,
                "content": json.dumps({"timezone": "Asia/Makassar", "iso_time": "2026-08-25T09:41:00+08:00"}),
            },
        ],
        "tools": [TOOL_GET_TIME],
        "tool_choice": "auto",
        "parallel_tool_calls": False,
        "temperature": 0.0,
        "max_tokens": 512,
        **extra_body,
    }
    t0 = time.monotonic()
    try:
        status, parsed, raw = http_post_json(f"{base_url}/chat/completions", payload, timeout)
    except Exception as e:  # noqa: BLE001
        p.passed = False
        p.reason = f"transport error: {type(e).__name__}: {e}"
        p.latency_s = time.monotonic() - t0
        return p
    p.latency_s = time.monotonic() - t0
    p.evidence["request"] = payload
    p.evidence["http_status"] = status
    p.evidence["raw_response"] = raw
    p.evidence["parsed_response"] = parsed

    if status == 200 and parsed:
        p.passed = True
        p.reason = f"HTTP 200 — role:tool with matching tool_call_id={call_id!r} accepted without error"
    else:
        p.passed = False
        p.reason = f"role:tool message rejected — HTTP {status}, body={raw[:500]!r}"
    return p


def probe_d_parallel_tool_calls_honored(base_url: str, model: str, timeout: float, extra_body: dict) -> Property:
    """(d) parallel_tool_calls=false is honored (one call per turn)."""
    p = Property("d_parallel_tool_calls_false_honored")
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": (
                    "I need two things at once: the weather in Denpasar AND the "
                    "current time in Asia/Makassar. Call whichever tool(s) you need."
                ),
            }
        ],
        "tools": [TOOL_GET_WEATHER, TOOL_GET_TIME],
        "tool_choice": "auto",
        "parallel_tool_calls": False,
        "temperature": 0.0,
        "max_tokens": 768,
        **extra_body,
    }
    t0 = time.monotonic()
    try:
        status, parsed, raw = http_post_json(f"{base_url}/chat/completions", payload, timeout)
    except Exception as e:  # noqa: BLE001
        p.passed = False
        p.reason = f"transport error: {type(e).__name__}: {e}"
        p.latency_s = time.monotonic() - t0
        return p
    p.latency_s = time.monotonic() - t0
    p.evidence["request"] = payload
    p.evidence["http_status"] = status
    p.evidence["raw_response"] = raw
    p.evidence["parsed_response"] = parsed

    if status != 200 or not parsed:
        p.passed = False
        p.reason = f"HTTP {status}, body not valid JSON or empty"
        return p

    try:
        message = parsed["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as e:
        p.passed = False
        p.reason = f"response missing choices[0].message: {e}"
        return p

    tool_calls = message.get("tool_calls") or []
    n = len(tool_calls)
    if n == 0:
        # No tool call at all is not what this property tests (that's (a)'s
        # job) — but it is not evidence parallel_tool_calls=false was
        # violated either. Record as inconclusive-fail with a distinct
        # reason so it is never conflated with an actual honoring failure.
        p.passed = False
        p.reason = "model made zero tool calls on a prompt designed to invite two — cannot judge whether parallel_tool_calls=false is honored"
        return p

    if n == 1:
        p.passed = True
        p.reason = f"exactly 1 tool_call returned despite a two-tool-worthy prompt: {tool_calls[0].get('function', {}).get('name')!r}"
    else:
        p.passed = False
        p.reason = f"parallel_tool_calls=false was sent but server returned {n} tool_calls in one turn: {[tc.get('function', {}).get('name') for tc in tool_calls]!r}"
    return p


def run_gate(base_url: str, model: str, timeout: float, extra_body: dict) -> list[Property]:
    props: list[Property] = []
    a = probe_a_native_tool_calls(base_url, model, timeout, extra_body)
    props.append(a)
    b = probe_b_history_roundtrip(base_url, model, timeout, a.evidence.get("tool_call_id"), extra_body)
    props.append(b)
    c = probe_c_tool_role_accepted(base_url, model, timeout, extra_body)
    props.append(c)
    d = probe_d_parallel_tool_calls_honored(base_url, model, timeout, extra_body)
    props.append(d)
    return props


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default=os.environ.get("SERVING_GATE_BASE_URL", "http://127.0.0.1:11434/v1"))
    ap.add_argument("--model", default=os.environ.get("SERVING_GATE_MODEL", "qwen3:8b"))
    ap.add_argument("--stack", default=os.environ.get("SERVING_GATE_STACK", "unspecified"))
    ap.add_argument("--stack-version", default=os.environ.get("SERVING_GATE_STACK_VERSION", "unspecified"))
    ap.add_argument("--model-digest", default=os.environ.get("SERVING_GATE_MODEL_DIGEST", "unspecified"))
    ap.add_argument("--timeout", type=float, default=float(os.environ.get("SERVING_GATE_TIMEOUT", "120")))
    ap.add_argument("--out", default=os.environ.get("SERVING_GATE_OUT"))
    ap.add_argument("--timestamp", default=os.environ.get("SERVING_GATE_TIMESTAMP"), help="ISO8601 UTC; if omitted, uses wall clock at run time (recorded, not computed by the script's own notion of 'now' for reproducibility across re-runs).")
    ap.add_argument(
        "--extra-body",
        default=os.environ.get("SERVING_GATE_EXTRA_BODY", "{}"),
        help='Extra JSON object merged into every request payload (e.g. \'{"think": false}\' '
             'for Ollama to disable Qwen3 thinking mode per research-capture requirement #9 — '
             'llama.cpp is controlled server-side via --reasoning off at launch instead).',
    )
    args = ap.parse_args()

    base_url = args.base_url.rstrip("/")
    timestamp = args.timestamp or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        extra_body = json.loads(args.extra_body)
    except json.JSONDecodeError as e:
        print(f"--extra-body is not valid JSON: {e}", file=sys.stderr)
        return 2
    if not isinstance(extra_body, dict):
        print("--extra-body must decode to a JSON object", file=sys.stderr)
        return 2

    print(f"[serving_roundtrip_gate] stack={args.stack} version={args.stack_version} "
          f"base_url={base_url} model={args.model} digest={args.model_digest} "
          f"extra_body={extra_body}", file=sys.stderr)

    props = run_gate(base_url, args.model, args.timeout, extra_body)

    result = {
        "gate": "F8_serving_roundtrip",
        "mandate_ref": "docs/plans/2026-08-25-due-bot-live/MANDATE.md#F8",
        "timestamp": timestamp,
        "stack": args.stack,
        "stack_version": args.stack_version,
        "base_url": base_url,
        "model_tag": args.model,
        "model_digest": args.model_digest,
        "extra_body": extra_body,
        "properties": [p.to_dict() for p in props],
        "overall_pass": all(p.passed for p in props),
    }

    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w") as f:
            json.dump(result, f, indent=2, sort_keys=False)
        print(f"[serving_roundtrip_gate] wrote {args.out}", file=sys.stderr)
    else:
        print(json.dumps(result, indent=2))

    failed = [p for p in props if not p.passed]
    for p in props:
        status = "PASS" if p.passed else "FAIL"
        print(f"  [{status}] {p.name}: {p.reason}", file=sys.stderr)

    if failed:
        print(f"\nGATE FAIL — {len(failed)}/{len(props)} properties failed: "
              f"{[p.name for p in failed]}", file=sys.stderr)
        return 1
    print(f"\nGATE PASS — {len(props)}/{len(props)} properties passed", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
