#!/usr/bin/env python3
"""tp1_call.py — one-shot text completion through the TP1 (Alibaba Token Plan)
OpenAI-compatible door, for use as a scripts/seat_build.sh implementer/refuter seat.

WHY THIS EXISTS: MODEL_ROSTER.md documents seven live TP1 text models
(deepseek-v4-pro, deepseek-v4-flash-0731, glm-5.2, qwen3.8-max, qwen3.7-max,
qwen3.7-plus, qwen3.6-flash) with strengths and effort notes, but before this
change none of them had an invocation path a caller could actually run for a
real task. scripts/arsenal_probe.py proves LIVENESS (a fixed "Reply with
exactly: PONG" 1-shot, judged and thrown away) but is not shaped for this: a
fixed prompt, a 256-token ceiling sized only for "did it answer at all", and a
verdict taxonomy (LIVE/AUTH_DEAD/...) rather than the answer text itself. This
script is the missing door: give it a real task, get the model's text back.

REUSE, NOT DUPLICATION: this module imports arsenal_probe.py's credential
loader and HTTP helper (both are stdlib-only with no import-time side effects
— safe to import, unlike scripts/ai-dispatch.sh which changes directory and
dispatches at top level, the documented reason scripts/lib/seat_watchdog.sh
duplicates instead of importing). A future fix to credential redaction or to
the thinking-model response shape (content vs reasoning_content vs a
finish_reason="length" truncation — see arsenal_probe.py's
_tp1_has_live_answer docstring) lands in one place, not two drifting copies.

EFFORT PASSTHROUGH IS UNVERIFIED PROVIDER BEHAVIOR: MODEL_ROSTER.md's TP1
section is explicit that its effort column is "an orchestration-routing
recommendation, not a claim that this door accepts a provider-side
reasoning_effort parameter". --effort therefore only adds a `reasoning_effort`
field when the caller opts in; it is never invented on this script's own
initiative.

Exit codes:
  0 = got a usable answer (written to stdout, newline-terminated)
  1 = HTTP/network/transport error, unknown model, or unparseable response
  2 = TP1 credential unavailable (see load_tp1_settings_key in arsenal_probe.py)
  3 = HTTP 200 but no usable content (thinking budget exhausted before an
      answer, or the answer never arrived — never SILENTLY treated as success)

Usage:
    python3 scripts/tp1_call.py --model deepseek-v4-flash-0731 -p "task text"
    python3 scripts/tp1_call.py --model qwen3.7-plus --task-file /tmp/task.txt \\
        --effort medium --max-tokens 4096
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arsenal_probe import (  # noqa: E402  (sibling import, see module docstring)
    TP1_CHAT_COMPLETIONS_URL,
    TP1_SEAT_MODELS,
    http_post_json,
    load_tp1_settings_key,
)

TP1_LIVE_SLUGS = frozenset(TP1_SEAT_MODELS.values())

# Empirically confirmed live (2026-08-27, HTTP 400 on the rejected value):
# the TP1-OAI gateway's `reasoning_effort` field accepts exactly
# 'none'|'minimal'|'low'|'medium'|'high'|'xhigh' — NOT 'max'. seat_build.sh
# (PR #5044) validates --effort globally against low|medium|high|xhigh|max,
# a set shared across all seats, so 'max' is a value this script's CLI must
# accept without erroring — it just cannot be forwarded to the provider
# field literally. 'max' in MODEL_ROSTER.md's TP1 effort notes was always an
# orchestration-routing recommendation ("route the hardest tasks here"), not
# a claim about the literal API parameter value — this mapping is what makes
# that distinction operationally real instead of just a docstring caveat.
EFFORT_TO_REASONING_EFFORT = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "xhigh": "xhigh",
    "max": "xhigh",  # clamp: the provider's ceiling, not a distinct level
}


def build_body(model: str, prompt: str, max_tokens: int, effort: Optional[str]) -> dict:
    body: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if effort:
        body["reasoning_effort"] = EFFORT_TO_REASONING_EFFORT.get(effort, effort)
    return body


def extract_answer(
    full_body: str,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Returns (answer_text, warning, error) for an HTTP-200 response body —
    callers must check status_code == 200 themselves before calling this (a
    non-200 status is a transport-level error, exit code 1, never routed
    through here: kimi refuter round 1 caught an earlier version that folded
    both cases into this function and returned exit 3 for a bare 401/500,
    contradicting this script's own documented exit-code contract). Never a
    bare LIVE/dead bool — a build seat needs the ANSWER, a probe
    (arsenal_probe.py) only needs a verdict. Mirrors _tp1_has_live_answer's
    content/reasoning_content/finish_reason="length" handling; ports the
    reasoning, not the boolean."""
    try:
        parsed = json.loads(full_body)
        choice = parsed["choices"][0]
        message = choice["message"]
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
        return None, None, f"unparseable response ({type(e).__name__}): {full_body[-200:]}"
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content, None, None
    reasoning = message.get("reasoning_content")
    if isinstance(reasoning, str) and reasoning.strip():
        if choice.get("finish_reason") == "length":
            return (
                None,
                None,
                "reasoning-only response truncated by finish_reason=length "
                "(thinking budget exhausted before an answer — raise --max-tokens)",
            )
        return (
            reasoning,
            "reasoning-only content (model returned no final `content`; "
            "this is the model's chain-of-thought, not a direct answer)",
            None,
        )
    return None, None, "HTTP 200 with both content and reasoning_content empty"


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="One-shot TP1 chat completion (see module docstring).")
    ap.add_argument("--model", required=True, help="TP1 model slug, e.g. deepseek-v4-flash-0731")
    ap.add_argument("-p", "--prompt", help="task text (mutually exclusive with --task-file)")
    ap.add_argument("--task-file", help="read task text from this file")
    ap.add_argument(
        "--effort",
        choices=["low", "medium", "high", "xhigh", "max"],
        default=None,
        help="opt-in reasoning_effort passthrough to the TP1 gateway, mapped through "
        "EFFORT_TO_REASONING_EFFORT ('max' clamps to 'xhigh' — the gateway rejects 'max' "
        "literally with HTTP 400, confirmed live 2026-08-27). Accepted here so seat_build.sh's "
        "global --effort set (low|medium|high|xhigh|max, PR #5044) never breaks this seat.",
    )
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--timeout", type=float, default=180.0)
    args = ap.parse_args(argv)

    if bool(args.prompt) == bool(args.task_file):
        ap.error("pass exactly one of -p/--prompt or --task-file")
    prompt = args.prompt if args.prompt is not None else Path(args.task_file).read_text(encoding="utf-8")
    if not prompt.strip():
        sys.stderr.write("tp1_call: empty task text\n")
        return 1

    if args.model not in TP1_LIVE_SLUGS:
        sys.stderr.write(
            f"tp1_call: {args.model!r} is not one of the 7 live TP1 text slugs: "
            f"{sorted(TP1_LIVE_SLUGS)}\n"
        )
        return 1

    token, cred_note = load_tp1_settings_key()
    if token is None:
        sys.stderr.write(f"tp1_call: credential unavailable: {cred_note}\n")
        return 2

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = build_body(args.model, prompt, args.max_tokens, args.effort)
    status_code, full_body, ev = http_post_json(
        TP1_CHAT_COMPLETIONS_URL, headers, body, args.timeout, [token]
    )
    if status_code is None:
        sys.stderr.write(f"tp1_call: {ev}\n")
        return 1
    if status_code != 200:
        sys.stderr.write(f"tp1_call: HTTP {status_code}: {full_body[-200:]}\n")
        return 1

    answer, warning, error = extract_answer(full_body)
    if error:
        sys.stderr.write(f"tp1_call: {error}\n")
        return 3
    if warning:
        sys.stderr.write(f"tp1_call: warning: {warning}\n")
    assert answer is not None
    sys.stdout.write(answer if answer.endswith("\n") else answer + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
