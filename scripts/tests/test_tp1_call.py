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
    """Minimal stand-in for urlopen's return: a context manager that iterates
    raw SSE lines, exactly as urllib yields them (bytes, newline-terminated)."""

    status = 200

    def __init__(self, lines):
        self._lines = [ln.encode("utf-8") for ln in lines]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        return iter(self._lines)


def _frame(**delta):
    return "data: " + json.dumps({"choices": [{"delta": delta}]}) + "\n"


def _stream(monkeypatch, lines, budget=60.0):
    import tp1_call

    monkeypatch.setattr(
        tp1_call.urllib.request,
        "urlopen",
        lambda req, timeout=None: _FakeResponse(lines),
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
            "data: [DONE]\n",
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
            "data: [DONE]\n",
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
            "data: [DONE]\n",
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
            "data: [DONE]\n",
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
            "data: [DONE]\n",
        ],
    )
    assert extract_answer(full)[0] == "x"


def test_budget_expiry_raises_still_generating_carrying_the_evidence(monkeypatch):
    """The whole reason exit 4 exists. A seat that is demonstrably streaming
    when the clock runs out must NOT be reported the way a dead one is: that
    conflation is what wrote ok:false for this live seat in PR #5494."""
    import tp1_call

    # t0, then one reading per loop iteration: two frames arrive comfortably
    # inside the budget, and only then does the clock jump past it.
    ticks = iter([0.0, 1.0, 2.0, 999.0])
    monkeypatch.setattr(tp1_call.time, "monotonic", lambda: next(ticks))

    with pytest.raises(StillGenerating) as caught:
        _stream(
            monkeypatch,
            [_frame(content="partial"), _frame(content=" more"), "data: [DONE]\n"],
            budget=50.0,
        )
    err = caught.value
    assert err.chunks == 2, "must prove chunks arrived — that is the ALIVE evidence"
    assert err.content_len == len("partial more")
    assert "NOT a dead seat" in str(err)


def test_a_seat_that_never_speaks_is_not_reported_as_still_generating(monkeypatch):
    """The other side of the same distinction: no frames at all is the shape
    of a dead seat, and it must come back as a normal transport failure
    (status None), never as StillGenerating."""
    status, full, _ = _stream(monkeypatch, ["data: [DONE]\n"])
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

    status, full, tail = _stream(monkeypatch, [_frame(content="x")], budget=50.0)
    assert status is None
    assert "never started responding" in full
    assert tail == "never responded"
