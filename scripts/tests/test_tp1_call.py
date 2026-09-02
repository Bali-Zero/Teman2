"""test_tp1_call.py — unit tests for tp1_call.py's pure functions.

No network, no credentials — these test build_body()'s effort-clamping and
extract_answer()'s content/reasoning_content/finish_reason=length split
in isolation. Both were touched by real findings during this PR's own
lifecycle (kimi refuter round 1 on the exit-code conflation; the team-lead's
requested PR #5044 coordination check, which found the TP1 gateway rejects
`reasoning_effort: max` with HTTP 400 — confirmed live 2026-08-27) and had
zero test coverage before either fix, so a regression here would be silent.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import pytest  # noqa: E402

from tp1_call import (  # noqa: E402
    EFFORT_TO_REASONING_EFFORT,
    MEASURED_DEFAULT_EFFORT,
    StillGenerating,
    build_body,
    extract_answer,
    resolve_effort,
)
from arsenal_probe import TP1_SEAT_MODELS  # noqa: E402


# ---------------------------------------------------------------- build_body / effort clamp


def test_max_effort_clamps_to_xhigh_not_sent_literally():
    """The TP1 gateway's `reasoning_effort` field accepts only
    none|minimal|low|medium|high|xhigh — 'max' is rejected with HTTP 400
    (confirmed live). seat_build.sh (PR #5044) validates --effort globally
    against low|medium|high|xhigh|max shared across all seats, so this
    script's CLI must accept 'max' without erroring, but must never forward
    it to the provider unclamped."""
    body = build_body("qwen3.7-plus", "hi", 64, "max")
    assert body["reasoning_effort"] == "xhigh"
    assert body["reasoning_effort"] != "max"


def test_known_effort_values_pass_through_unchanged():
    for value in ["low", "medium", "high", "xhigh"]:
        assert EFFORT_TO_REASONING_EFFORT[value] == value
        assert build_body("qwen3.7-plus", "hi", 64, value)["reasoning_effort"] == value


def test_no_effort_omits_the_field_entirely():
    """None is the CLI default — an omitted --effort must not send an empty
    or fabricated reasoning_effort field."""
    body = build_body("qwen3.7-plus", "hi", 64, None)
    assert "reasoning_effort" not in body


# ---------------------------------------------------------------- extract_answer


def test_extract_answer_returns_direct_content():
    body = json.dumps({"choices": [{"message": {"content": "pong"}}]})
    answer, warning, error = extract_answer(body)
    assert answer == "pong"
    assert warning is None
    assert error is None


def test_extract_answer_reasoning_only_returns_a_warning_not_an_error():
    body = json.dumps(
        {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"reasoning_content": "thinking..."},
                }
            ]
        }
    )
    answer, warning, error = extract_answer(body)
    assert answer == "thinking..."
    assert warning is not None
    assert error is None


def test_extract_answer_length_truncated_reasoning_is_an_error_not_success():
    """kimi refuter round 1 / the thinking-model quirk arsenal_probe.py
    documents: a reasoning-only reply cut off by finish_reason=length before
    any answer must never be reported as a usable answer."""
    body = json.dumps(
        {
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {"reasoning_content": "still thinking"},
                }
            ]
        }
    )
    answer, warning, error = extract_answer(body)
    assert answer is None
    assert error is not None
    assert "length" in error


def test_extract_answer_both_empty_is_an_error():
    body = json.dumps({"choices": [{"message": {}}]})
    answer, warning, error = extract_answer(body)
    assert answer is None
    assert error is not None


def test_extract_answer_unparseable_body_is_an_error_not_a_crash():
    answer, warning, error = extract_answer("not json at all")
    assert answer is None
    assert error is not None


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))


# ---------------------------------------------------------------- resolve_effort


def test_explicit_effort_always_beats_the_measured_default():
    """The table fills a silence; it never overrides a caller who spoke.

    seat_build.sh:455 passes --effort on EVERY tp1 dispatch, so if the table
    could win, one script's measurement would silently retune the repo's only
    production caller."""
    assert resolve_effort("qwen3.8-max", "high") == "high"
    assert resolve_effort("qwen3.8-max", "low") == "low"


def test_measured_default_applies_to_the_model_that_was_measured():
    """Measured 2026-09-01: unset costs 805.4s/1388 chars against medium's
    193.9s/2446 chars on the same real task. A caller who passes nothing must
    not land in the worse cell."""
    assert resolve_effort("qwen3.8-max", None) == "medium"


def test_unmeasured_models_are_left_exactly_as_they_were():
    """The reason this is a per-model table and not a global default.

    Only qwen3.8-max was probed. Sending `reasoning_effort` to a backend that
    rejects it turns a known-slow seat into a newly-broken one (the gateway
    answers HTTP 400 on a value it dislikes — EFFORT_TO_REASONING_EFFORT was
    learned exactly that way). Asserted over the LIVE slug list rather than a
    hardcoded set, so adding a measured row is allowed and only an UNMEASURED
    model silently acquiring a default fails."""
    for slug in TP1_SEAT_MODELS.values():
        if slug not in MEASURED_DEFAULT_EFFORT:
            assert resolve_effort(slug, None) is None, (
                f"{slug} has no measured default but resolve_effort invented one"
            )


def test_every_measured_default_names_a_real_slug_and_a_sendable_value():
    """A typo'd key is a row that never fires; an unmappable value is an HTTP 400."""
    live = set(TP1_SEAT_MODELS.values())
    for slug, effort in MEASURED_DEFAULT_EFFORT.items():
        assert slug in live, f"{slug!r} is not one of the live TP1 slugs"
        assert effort in EFFORT_TO_REASONING_EFFORT, (
            f"{effort!r} is not a sendable effort"
        )


# ---------------------------------------------------------------- stream_chat_completion


class _FakeResponse:
    """Serves the SSE body the way urllib actually does — as byte blocks from
    read1() — NOT as a list of pre-split lines.

    The first version of this fake yielded whole lines, which quietly assumed
    away the very thing the parser has to get right. `block_size` therefore
    defaults to something that CUTS FRAMES IN HALF, so every test here
    exercises the reassembly buffer instead of trusting it."""

    status = 200

    def __init__(self, lines, block_size=7):
        self._data = "".join(lines).encode("utf-8")
        self._pos = 0
        self._block = block_size

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read1(self, n=-1):
        if self._pos >= len(self._data):
            return b""
        block = self._data[self._pos : self._pos + self._block]
        self._pos += len(block)
        return block


def _frame(**delta):
    return "data: " + json.dumps({"choices": [{"delta": delta}]}) + "\n"


_DONE = "data: [DONE]\n"


def _stream(monkeypatch, lines, budget=60.0, block_size=7):
    import tp1_call

    monkeypatch.setattr(
        tp1_call.urllib.request,
        "urlopen",
        lambda req, timeout=None: _FakeResponse(lines, block_size),
    )
    return tp1_call.stream_chat_completion(
        "https://example.invalid/v1/chat/completions",
        {},
        {"model": "m"},
        budget,
        ["tok"],
    )


def test_stream_survives_a_terminal_frame_carrying_no_choices(monkeypatch):
    """The bug this parser was written around, hit live while measuring.

    Several OpenAI-compatible gateways close with a usage-only frame whose
    `choices` is []. Indexing it blindly raises IndexError on the LAST chunk —
    discarding an answer that had already arrived in full."""
    status, full, _ = _stream(
        monkeypatch,
        [
            _frame(content="hello "),
            _frame(content="world"),
            'data: {"choices": [], "usage": {"completion_tokens": 9020}}\n',
            _DONE,
        ],
    )
    assert status == 200
    answer, warning, error = extract_answer(full)
    assert error is None and warning is None
    assert answer == "hello world"


def test_stream_reassembles_into_the_shape_extract_answer_consumes(monkeypatch):
    """The single-parser property: streaming must not introduce a second
    opinion about what counts as an answer. Whatever the SSE path returns goes
    through the same extract_answer as the non-streaming path."""
    _, full, _ = _stream(
        monkeypatch,
        [
            _frame(content="ans"),
            'data: {"choices":[{"finish_reason":"stop"}]}\n',
            _DONE,
        ],
    )
    assert json.loads(full)["choices"][0]["finish_reason"] == "stop"
    assert extract_answer(full)[0] == "ans"


def test_stream_keeps_reasoning_out_of_the_answer(monkeypatch):
    """125,239 chars of reasoning_content arrived alongside 1388 chars of
    answer in one measured call. Concatenating them would hand the caller the
    model's chain-of-thought as if it were the deliverable."""
    _, full, _ = _stream(
        monkeypatch,
        [
            _frame(reasoning_content="thinking..."),
            _frame(content="VERDICT"),
            _DONE,
        ],
    )
    parsed = json.loads(full)["choices"][0]["message"]
    assert parsed["content"] == "VERDICT"
    assert parsed["reasoning_content"] == "thinking..."
    assert extract_answer(full)[0] == "VERDICT"


def test_stream_tolerates_one_malformed_frame(monkeypatch):
    """A single unparseable frame must not discard a generation that is
    otherwise arriving fine — same tolerance openrouter_client.py and mlx.py
    already apply to this framing."""
    _, full, _ = _stream(
        monkeypatch,
        [
            _frame(content="a"),
            "data: {not json\n",
            _frame(content="b"),
            _DONE,
        ],
    )
    assert extract_answer(full)[0] == "ab"


def test_stream_ignores_sse_comments_and_non_data_fields(monkeypatch):
    _, full, _ = _stream(
        monkeypatch,
        [
            ": keep-alive\n",
            "event: message\n",
            "\n",
            _frame(content="x"),
            _DONE,
        ],
    )
    assert extract_answer(full)[0] == "x"


def test_budget_expiry_raises_still_generating_carrying_the_evidence(monkeypatch):
    """The whole reason exit 4 exists. A seat that is demonstrably streaming
    when the clock runs out must NOT be reported the way a dead one is: that
    conflation is what wrote ok:false for this live seat in PR #5494."""
    import tp1_call

    # t0, then one reading per read-block iteration. Small blocks mean the
    # frames need several reads to arrive, so the clock can jump past the
    # budget mid-generation with chunks already banked.
    ticks = iter([0.0, 1.0, 2.0, 3.0, 999.0])
    monkeypatch.setattr(tp1_call.time, "monotonic", lambda: next(ticks))

    with pytest.raises(StillGenerating) as caught:
        _stream(
            monkeypatch,
            [_frame(content="partial"), _frame(content=" more"), _DONE],
            budget=50.0,
            block_size=40,
        )
    err = caught.value
    assert err.chunks >= 1, "must prove chunks arrived — that is the ALIVE evidence"
    assert err.content_len > 0
    assert "NOT a dead seat" in str(err)


def test_a_seat_that_never_speaks_is_not_reported_as_still_generating(monkeypatch):
    """The other side of the same distinction: no frames at all is the shape
    of a dead seat, and it must come back as a normal transport failure
    (status None), never as StillGenerating."""
    status, full, _ = _stream(monkeypatch, [_DONE])
    assert status == 200
    assert extract_answer(full)[2] is not None, (
        "empty generation must be an error, not silence"
    )


def test_budget_expiry_with_zero_frames_is_reported_as_a_dead_seat(monkeypatch):
    """The mirror of the test above, and a defect this suite actually caught:
    the first version raised StillGenerating — asserting "seat ALIVE" — before
    a single frame had arrived. Claiming a dead seat is alive keeps a broken
    seat in the dispatch rotation, which is the same conflation as the bug
    being fixed, only pointed the other way."""
    import tp1_call

    ticks = iter([0.0, 999.0])
    monkeypatch.setattr(tp1_call.time, "monotonic", lambda: next(ticks))

    status, full, tail = _stream(
        monkeypatch, [_frame(content="x")], budget=50.0, block_size=5
    )
    assert status is None
    assert "never started responding" in full
    assert tail == "never responded"


# ------------------------------------- defects found by qwen3.8-max reviewing this diff


def test_a_dropped_connection_is_not_reported_as_a_complete_answer(monkeypatch):
    """Q4, found by the qwen3.8-max seat reviewing the very diff that repaired it.

    The stream stops with content already banked but no `[DONE]` and no
    finish_reason on any frame — a killed pod or a reset load balancer. The
    first version returned HTTP 200 with the partial text, so the caller got a
    truncated review that looked complete and exit 0. This script's own
    exit-code contract says an answer that never arrived is 'never SILENTLY
    treated as success'. The non-streaming path cannot have this failure (a cut
    body fails json.loads); streaming introduced it, so streaming must close it."""
    status, full, tail = _stream(
        monkeypatch, [_frame(content="half an ans"), _frame(content="wer that stops")]
    )
    assert status is None, "a truncated stream must not come back as HTTP 200"
    assert "truncated" in full
    assert tail == "truncated stream"


def test_a_stream_that_declares_finish_reason_but_no_done_is_complete(monkeypatch):
    """The other side of the same line: some gateways close the socket right
    after the last content frame without sending the `[DONE]` sentinel. If the
    server DECLARED completion via finish_reason, that is a finished answer and
    must not be rejected as truncated."""
    status, full, _ = _stream(
        monkeypatch,
        [_frame(content="done"), 'data: {"choices":[{"finish_reason":"stop"}]}\n'],
    )
    assert status == 200
    assert extract_answer(full)[0] == "done"


def test_the_wall_clock_budget_is_checked_between_reads_not_between_frames(monkeypatch):
    """Q2, found by the same review. The first version iterated `for line in
    resp`, so the deadline could only be tested once a whole newline-terminated
    frame had arrived. A server trickling bytes without a newline keeps every
    recv() inside the socket timeout while readline() never returns, and
    --timeout — documented as a wall-clock budget — is then unenforceable.

    Here the body is served in blocks that never complete a frame. If the
    deadline were still checked per-FRAME it would never fire and this test
    would hang or read to EOF; checked per-READ it fires."""
    import tp1_call

    ticks = iter([0.0, 1.0, 2.0, 5000.0])
    monkeypatch.setattr(tp1_call.time, "monotonic", lambda: next(ticks))

    # One enormous frame with no newline until the very end: no line ever
    # completes within the first few reads.
    huge = (
        "data: "
        + json.dumps({"choices": [{"delta": {"content": "x" * 100000}}]})
        + "\n"
    )
    status, full, tail = _stream(monkeypatch, [huge], budget=50.0, block_size=8)
    assert status is None, "the budget must be enforced even mid-frame"
    assert tail == "never responded", (
        "no frame completed, so there is no evidence of life"
    )


def test_a_final_frame_without_a_trailing_newline_is_not_lost(monkeypatch):
    """Servers are not obliged to newline-terminate the last frame before
    closing. The buffer only emits on '\\n', so without an explicit flush at EOF
    that frame — often the one carrying finish_reason — vanishes, and a
    complete answer is then misreported as a truncated stream."""
    status, full, _ = _stream(
        monkeypatch,
        [_frame(content="body"), 'data: {"choices":[{"finish_reason":"stop"}]}'],
    )
    assert status == 200, "the unterminated final frame carried finish_reason"
    assert extract_answer(full)[0] == "body"


# ------------------------------------- scrub-before-parse regression (2026-09-02)
#
# scrub() is applied to RAW HTTP transport text — a JSON transport envelope —
# BEFORE json.loads() ever sees it. scrub()'s generic 24+-char pattern rewrites
# a JSON KEY in place (a live TP1 "usage" object's "completion_tokens_details"
# is 26 chars) and its Bearer-plus-nonspace clause has no notion of JSON
# syntax: it eats straight through a closing quote and the next field's key
# the moment an answer merely CONTAINS the word "Bearer" — a plausible thing
# for a technical answer to say. GUILT tests below prove such a body still
# parses post-fix; the INNOCENCE test proves a real secret value still never
# reaches an emitted string.


def test_stream_success_body_is_raw_not_prescrubbed(monkeypatch):
    """GUILT: an answer ending in "Bearer <word>" is the exact shape that
    broke json.loads() pre-fix. scrub()'s Bearer-plus-nonspace clause is
    greedy and \\S includes '"' and ',' — it does not stop at the closing
    quote of "content", it eats straight through it and the following
    ", "reasoning_content"" boundary too, corrupting the JSON envelope
    (confirmed live: pre-fix this exact body raises
    `json.JSONDecodeError: Expecting ',' delimiter`). Post-fix it must still
    parse, and extract_answer must return the answer text UNCHANGED — parsing
    is not an output boundary, so no redaction happens here."""
    status, full, _ = _stream(
        monkeypatch,
        [_frame(content="Use a Bearer token"), _DONE],
    )
    assert status == 200
    json.loads(full)  # must not raise — this is what broke pre-fix
    answer, warning, error = extract_answer(full)
    assert error is None
    assert answer == "Use a Bearer token"


class _FakeNoStreamResponse:
    """Serves a complete, non-streamed HTTP response — no read1()/SSE framing,
    just .status and a single .read()."""

    def __init__(self, body_bytes: bytes, status: int = 200):
        self._body = body_bytes
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


def test_no_stream_success_body_is_raw_not_prescrubbed(monkeypatch):
    """GUILT, --no-stream transport: a real TP1 response shape — a "usage"
    object carrying "completion_tokens_details" (26 chars, past scrub()'s
    generic 24-char threshold) AND an answer ending in "Bearer token" (the
    exact shape confirmed live to raise `json.JSONDecodeError: Expecting ','
    delimiter` pre-fix, scrub()'s Bearer clause eating through the closing
    quote of "content") — must still parse via no_stream_chat_completion +
    extract_answer, with the answer text coming back unchanged."""
    import tp1_call

    payload = {
        "choices": [
            {
                "message": {
                    "content": "Use a Bearer token",
                    "reasoning_content": "",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 55,
            "completion_tokens_details": {"reasoning_tokens": 5, "text_tokens": 10},
        },
    }
    raw = json.dumps(payload).encode("utf-8")
    monkeypatch.setattr(
        tp1_call.urllib.request,
        "urlopen",
        lambda req, timeout=None: _FakeNoStreamResponse(raw),
    )
    status, full, _ = tp1_call.no_stream_chat_completion(
        "https://example.invalid/v1/chat/completions", {}, {"model": "m"}, 60.0, ["tok"]
    )
    assert status == 200
    json.loads(full)  # must not raise — this is what broke pre-fix
    answer, warning, error = extract_answer(full)
    assert error is None
    assert answer == "Use a Bearer token"


def test_no_stream_error_path_is_still_scrubbed(monkeypatch):
    """A non-200 body is never parsed as JSON, so it keeps the old
    always-scrubbed contract — the fix only changes the HTTP-200 case."""
    import tp1_call

    monkeypatch.setattr(
        tp1_call.urllib.request,
        "urlopen",
        lambda req, timeout=None: _FakeNoStreamResponse(
            b'{"error": "token sk-abcdefgh12345678 is invalid"}', status=500
        ),
    )
    status, full, tail = tp1_call.no_stream_chat_completion(
        "https://example.invalid/v1/chat/completions", {}, {"model": "m"}, 60.0, []
    )
    assert status == 500
    assert "sk-abcdefgh12345678" not in full
    assert "sk-abcdefgh12345678" not in tail
    assert "<REDACTED>" in full


def test_secret_value_never_reaches_stdout_or_stderr(monkeypatch, capsys):
    """INNOCENCE, end-to-end via main(): a secret VALUE present in the body —
    here the loaded credential itself, echoed back into the answer, the
    single most damaging leak this script could produce — must never survive
    to stdout or stderr, even though full_body is now RAW through the parse.
    Assert on what actually leaves the process, not on an internal variable."""
    import tp1_call

    SECRET = "sk-totally-fake-secret-value-1234567890"  # pragma: allowlist secret
    monkeypatch.setattr(tp1_call, "load_tp1_settings_key", lambda: (SECRET, None))
    monkeypatch.setattr(
        tp1_call.urllib.request,
        "urlopen",
        lambda req, timeout=None: _FakeResponse(
            [_frame(content=f"the task is done, credential was {SECRET}"), _DONE]
        ),
    )
    exit_code = tp1_call.main(
        ["--model", "qwen3.8-max", "-p", "hi", "--effort", "low"]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert SECRET not in captured.out
    assert SECRET not in captured.err
    assert "the task is done" in captured.out
