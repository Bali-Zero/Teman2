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
loader, secret scrubber and HTTP helper (all stdlib-only with no import-time
side effects — safe to import, unlike scripts/ai-dispatch.sh which changes
directory and dispatches at top level, the documented reason
scripts/lib/seat_watchdog.sh duplicates instead of importing). A future fix to
credential redaction or to the thinking-model response shape (content vs
reasoning_content vs a finish_reason="length" truncation — see
arsenal_probe.py's _tp1_has_live_answer docstring) lands in one place, not two
drifting copies. The ONE deliberate exception is stream_chat_completion below:
it lives here and not in arsenal_probe.py because the liveness probe is a
256-token 1-shot that has no use for streaming, and adding a second transport
to that module would put the fleet-wide liveness path at risk to serve a
caller it does not have. It still funnels its result through extract_answer,
so exactly one parser decides what counts as an answer.

WHY IT STREAMS BY DEFAULT (measured 2026-09-01 against qwen3.8-max, the live
TP1 gateway, on the real 3196-prompt-token refuter task that had been failing):

  transport   effort   TTFB    max silence   total     outcome
  no-stream   medium   --      --            193.9s    9020 completion tokens
  no-stream   (unset)  --      --            180.0s    TIMED OUT at the old default
  stream      (unset)  1.5s    1.5s          805.4s    finish=stop, 9315 chunks

The old default (--timeout 180.0, non-streaming) is BELOW the measured cost of
one real task at its cheapest usable setting, so the seat timed out on work it
was perfectly capable of. Worse, it timed out INVISIBLY: urlopen's timeout is
per-socket-operation, and with a non-streaming request the gateway sends
nothing at all until generation completes, so the very first recv() blocks for
the whole generation and raises. The resulting `tp1_call: timed out` is
byte-identical to what a genuinely dead gateway produces — which is exactly
how this seat came to be journalled ok:false in PR #5494's evidence pack while
being fully alive. Streaming removes the ambiguity at the root: the seat's
first byte arrives in 1.5s and it never goes quiet for longer than 1.5s across
a 13-minute generation, so "has not answered in 90 seconds" becomes a claim
about the SEAT rather than about the task's length.

TWO MEASURED FACTS THAT CONTRADICT THE OBVIOUS GUESS, recorded because both
cost a wrong inference during the investigation:

  1. reasoning_effort is NOT a token budget; it scales with task difficulty.
     On a toy prompt, medium spent 540 completion tokens. On the real task,
     medium spent 9020 — 16.7x. Do not size a timeout by measuring a small
     prompt and multiplying.
  2. Omitting reasoning_effort on qwen3.8-max is strictly worse on EVERY axis,
     not merely more expensive. On the real task, unset took 805.4s and
     returned 1388 chars of answer; medium took 193.9s and returned 2446 chars
     of a sharper answer. That is why MEASURED_DEFAULT_EFFORT exists and why
     it holds exactly one entry: the model that was actually measured.

Exit codes:
  0 = got a usable answer (written to stdout, newline-terminated)
  1 = HTTP/network/transport error, unknown model, or unparseable response
  2 = TP1 credential unavailable (see load_tp1_settings_key in arsenal_probe.py)
  3 = HTTP 200 but no usable content (thinking budget exhausted before an
      answer, or the answer never arrived — never SILENTLY treated as success)
  4 = the seat was ALIVE and still generating when the budget ran out. Split
      out of exit 1 deliberately: a caller that folds "slow" into "dead" writes
      ok:false into a council journal for a seat that simply needed longer, and
      a quorum gate then under-counts the seats it actually has.

Usage:
    python3 scripts/tp1_call.py --model deepseek-v4-flash-0731 -p "task text"
    python3 scripts/tp1_call.py --model qwen3.7-plus --task-file /tmp/task.txt \\
        --effort medium --max-tokens 4096
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arsenal_probe import (  # noqa: E402  (sibling import, see module docstring)
    TP1_CHAT_COMPLETIONS_URL,
    TP1_SEAT_MODELS,
    http_post_json,
    load_tp1_settings_key,
    scrub,
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


# MEASURED, not guessed, and deliberately one entry per model actually probed.
#
# Omitting `reasoning_effort` is not a neutral default on a thinking model: on
# qwen3.8-max it is the WORST cell measured, losing on both axes at once. On
# the real 3196-prompt-token refuter task (2026-09-01, live gateway):
#
#     unset  -> 805.4s, answer 1388 chars
#     medium -> 193.9s, answer 2446 chars, and the sharper review of the two
#
# so the caller who passes nothing gets 4.2x the wall time for a shorter, worse
# answer. A default that only ever costs the caller is worth fixing.
#
# It stays a per-model table with a single row because a single row is what was
# measured. The other six TP1 slugs were never probed for this, and sending
# them a field their backend might reject would trade a known-slow seat for a
# newly-broken one (the gateway answers HTTP 400 on a value it dislikes — see
# EFFORT_TO_REASONING_EFFORT above, learned exactly that way). Add a row here
# when, and only when, a model has been measured; an explicit --effort always
# wins over this table.
MEASURED_DEFAULT_EFFORT = {
    "qwen3.8-max": "medium",
}

# How long the seat may stay SILENT before we call it dead, in seconds. This is
# not the task budget (--timeout is); it is the gap between two bytes. Measured
# on qwen3.8-max over a 13-minute, 9315-chunk generation: first byte at 1.5s,
# largest gap between consecutive chunks 1.5s. 90s is 60x the observed worst
# gap — generous enough that a slow network hiccup is not a verdict, tight
# enough that a genuinely dead socket is named in under two minutes instead of
# being indistinguishable from a long think.
SILENCE_TIMEOUT_SECONDS = 90.0


class StillGenerating(Exception):
    """The budget ran out while the seat was demonstrably alive and streaming.

    Carries the evidence that distinguishes this from a dead seat, because that
    distinction is the entire reason this class exists: a caller that cannot
    tell "slow" from "dead" journals ok:false for a working seat, and a council
    quorum gate then under-counts the seats it has. That is not hypothetical —
    it is what happened to this seat in PR #5494."""

    def __init__(
        self, elapsed: float, chunks: int, content_len: int, reasoning_len: int
    ):
        self.elapsed = elapsed
        self.chunks = chunks
        self.content_len = content_len
        self.reasoning_len = reasoning_len
        super().__init__(
            f"seat ALIVE but still generating when the {elapsed:.0f}s budget ran out "
            f"({chunks} chunks received, {reasoning_len} chars of reasoning, "
            f"{content_len} chars of answer so far). This is NOT a dead seat: raise "
            f"--timeout, or pass --effort medium (measured 4.2x faster than unset "
            f"on qwen3.8-max)."
        )


def resolve_effort(model: str, explicit: Optional[str]) -> Optional[str]:
    """Pick the reasoning_effort to send: the caller's choice, else the measured
    default for THIS model, else nothing.

    A function rather than an inline `or` so the precedence is testable without
    standing up a transport, and so the "unmeasured models are left alone" rule
    has somewhere to be asserted."""
    if explicit:
        return explicit
    return MEASURED_DEFAULT_EFFORT.get(model)


def stream_chat_completion(
    url: str, headers: dict, body: dict, budget: float, secret_values: list[str]
) -> tuple[Optional[int], str, str]:
    """Stream a chat completion and re-assemble it into the SAME response shape
    the non-streaming path returns, so extract_answer stays the single judge of
    what counts as an answer. Returns http_post_json's contract exactly —
    (status_code_or_None, full_body, evidence_tail) — so main() does not branch
    on transport.

    Raises StillGenerating if the wall-clock budget expires while chunks are
    still arriving. Every other failure is folded into the (None, msg, msg)
    shape, scrubbed, never raised past this boundary.

    The socket timeout here is SILENCE_TIMEOUT_SECONDS, not the budget: with a
    streamed response urlopen's per-read timeout finally measures what its name
    suggests. That is the whole point of streaming this call — see the module
    docstring's table.

    WHY A THIRD SSE PARSER AND NOT A REUSED ONE: this repo already parses
    OpenAI-style SSE in two places — openrouter_client.py's stream() and
    llm/providers/mlx.py — and the framing logic below is deliberately the same
    shape as theirs (strip `data:`, honour the `[DONE]` sentinel, tolerate a
    malformed frame, read `choices[0].delta`). Neither is importable here: both
    are `async` generators built on `httpx.AsyncClient.stream`, living in the
    backend service package, while this is a synchronous stdlib-only CLI whose
    whole reuse contract (module docstring) is that it imports nothing that has
    import-time side effects. Porting ~20 lines of framing was the smaller debt
    than making a one-shot script async or dragging httpx into it — recorded
    here so the next reader knows the duplication was measured, not missed."""

    def _scrub(raw: str) -> tuple[str, str]:
        full = scrub((raw or "").strip().replace("\n", " "), secret_values)
        return full, full[-160:]

    streamed = dict(body)
    streamed["stream"] = True
    data = json.dumps(streamed).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    content: list[str] = []
    reasoning: list[str] = []
    finish_reason: Optional[str] = None
    chunks = 0
    started = time.monotonic()

    try:
        with urllib.request.urlopen(req, timeout=SILENCE_TIMEOUT_SECONDS) as resp:
            if resp.status != 200:  # pragma: no cover — urllib raises HTTPError first
                raw = resp.read().decode("utf-8", errors="replace")
                full, tail = _scrub(raw)
                return resp.status, full, tail
            for raw_line in resp:
                elapsed = time.monotonic() - started
                if elapsed > budget:
                    if chunks == 0:
                        # No frame has arrived, so there is NO evidence of life
                        # and StillGenerating would assert one. Claiming a dead
                        # seat is alive is the same conflation as claiming a
                        # live one is dead, only pointed the other way — it
                        # would keep a broken seat in the dispatch rotation.
                        # Report it the way any other transport failure is.
                        return (
                            None,
                            f"no data at all within the {budget:.0f}s budget "
                            f"— the seat never started responding",
                            "never responded",
                        )
                    raise StillGenerating(
                        elapsed, chunks, len("".join(content)), len("".join(reasoning))
                    )
                line = raw_line.decode("utf-8", errors="replace").strip()
                # Skip blank separators, SSE comments (":..."), and non-data
                # fields ("event:", "id:", "retry:") — only `data:` carries payload.
                if not line.startswith("data:"):
                    continue
                payload = line[len("data:") :].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except ValueError:
                    # One malformed frame must not discard a generation that is
                    # otherwise arriving fine; a truly broken stream ends with
                    # no content and is reported by the caller as exit 3.
                    continue
                chunks += 1
                # `choices` is [] on the terminal usage-only frame that some
                # OpenAI-compatible gateways emit. Indexing it blindly raises
                # IndexError at the very last chunk, discarding a COMPLETE
                # answer — measured live while building this, and the reason
                # this expression is written the long way.
                choice = (chunk.get("choices") or [{}])[0]
                delta = choice.get("delta") or {}
                piece = delta.get("content")
                if isinstance(piece, str):
                    content.append(piece)
                think = delta.get("reasoning_content")
                if isinstance(think, str):
                    reasoning.append(think)
                if choice.get("finish_reason"):
                    finish_reason = choice["finish_reason"]
    except StillGenerating:
        raise
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if e.fp else ""
        full, tail = _scrub(raw)
        return e.code, full, tail
    except urllib.error.URLError as e:
        full, tail = _scrub(f"{type(e).__name__}: {e.reason}")
        return None, full, tail
    except TimeoutError:
        # Distinguishable by construction: with a streamed response this can
        # only mean SILENCE_TIMEOUT_SECONDS elapsed between two bytes, which
        # is a statement about the seat, not about the task's length.
        return (
            None,
            (
                f"no data for {SILENCE_TIMEOUT_SECONDS:.0f}s after {chunks} chunks "
                f"— the seat stopped responding mid-stream"
            ),
            "silent mid-stream",
        )
    except Exception as e:  # never crash a caller that only wanted an answer
        full, tail = _scrub(f"{type(e).__name__}: {e}")
        return None, full, tail

    reassembled = {
        "choices": [
            {
                "message": {
                    "content": "".join(content),
                    "reasoning_content": "".join(reasoning),
                },
                "finish_reason": finish_reason,
            }
        ]
    }
    full = scrub(json.dumps(reassembled), secret_values)
    return 200, full, full[-160:]


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
        return (
            None,
            None,
            f"unparseable response ({type(e).__name__}): {full_body[-200:]}",
        )
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
    ap = argparse.ArgumentParser(
        description="One-shot TP1 chat completion (see module docstring)."
    )
    ap.add_argument(
        "--model", required=True, help="TP1 model slug, e.g. deepseek-v4-flash-0731"
    )
    ap.add_argument(
        "-p", "--prompt", help="task text (mutually exclusive with --task-file)"
    )
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
    ap.add_argument(
        "--max-tokens",
        type=int,
        default=4096,
        help="upper bound on generated tokens. NOTE, measured 2026-09-01: on "
        "qwen3.8-max this does NOT bound the reasoning stream — a call with "
        "max_tokens=8000 emitted ~125k characters of reasoning_content and still "
        "finished with finish_reason='stop', not 'length'. Size --timeout for "
        "the task; do not expect this flag to cap it.",
    )
    ap.add_argument(
        "--timeout",
        type=float,
        default=900.0,
        help="total wall-clock budget for the whole call, in seconds. Raised from "
        "180.0 on 2026-09-01: 180 was BELOW the measured cost of one real refuter "
        "task at its cheapest usable setting (193.9s), so the seat timed out on "
        "work it could do. Silence between bytes is a separate, internal limit "
        "(SILENCE_TIMEOUT_SECONDS) — this flag never has to absorb a long think.",
    )
    ap.add_argument(
        "--no-stream",
        dest="stream",
        action="store_false",
        default=True,
        help="use the single-shot non-streaming transport instead of SSE. Streaming "
        "is the default because it is what makes a slow seat distinguishable from a "
        "dead one (module docstring). Kept as an escape hatch for any TP1 model whose "
        "backend rejects `stream: true` — only qwen3.8-max was measured.",
    )
    args = ap.parse_args(argv)

    if bool(args.prompt) == bool(args.task_file):
        ap.error("pass exactly one of -p/--prompt or --task-file")
    prompt = (
        args.prompt
        if args.prompt is not None
        else Path(args.task_file).read_text(encoding="utf-8")
    )
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

    # An explicit --effort always wins; the table only fills a silence that
    # would otherwise cost the caller 4.2x the wall time for a worse answer.
    effort = resolve_effort(args.model, args.effort)

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = build_body(args.model, prompt, args.max_tokens, effort)
    try:
        if args.stream:
            status_code, full_body, ev = stream_chat_completion(
                TP1_CHAT_COMPLETIONS_URL, headers, body, args.timeout, [token]
            )
        else:
            status_code, full_body, ev = http_post_json(
                TP1_CHAT_COMPLETIONS_URL, headers, body, args.timeout, [token]
            )
    except StillGenerating as e:
        sys.stderr.write(f"tp1_call: {e}\n")
        return 4
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
