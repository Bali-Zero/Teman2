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

from tp1_call import EFFORT_TO_REASONING_EFFORT, build_body, extract_answer  # noqa: E402


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
        {"choices": [{"finish_reason": "stop", "message": {"reasoning_content": "thinking..."}}]}
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
        {"choices": [{"finish_reason": "length", "message": {"reasoning_content": "still thinking"}}]}
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
