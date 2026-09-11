"""Vision quota-burn circuit breaker (2026-08-20): persistent chain-wide
rate-limit cooldown + content-addressed no-op fingerprint cache in
claude_vision.py::_run_claude_json.

Ground truth measured the same day: with every OAuth seat rate-limited, the
one-shot apply-worker correctly released each draft without burning an
attempt, but launchd re-fired the WHOLE process on a schedule and walked the
full seat chain again every tick — ~1,262 `claude --print` vision sessions/
day, ~690M cache-write tokens/7d, against a quota window already known dead.

These tests exercise `_run_claude_json` directly (private, but the intended
unit-test surface per its own module docstring / test_critic_calibration_
rubric.py precedent) with `_run_process_group` mocked out — no real
subprocess, no real Claude CLI, no network.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS_DIR))

import wr2_html_renderer.claude_vision as cv  # noqa: E402

_SCHEMA = {"type": "object", "properties": {}}


def _success_proc(payload: dict) -> subprocess.CompletedProcess[str]:
    envelope = {"type": "result", "subtype": "success", "structured_output": payload}
    return subprocess.CompletedProcess(["claude"], 0, json.dumps(envelope), "")


def _rate_limited_proc() -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["claude"], 1, "", "rate limit exceeded")


def _isolate_state(monkeypatch, tmp_path: Path) -> None:
    """Point both state files at a fresh tmp dir and give the token chain a
    predictable, fixed length (2 numbered seats + the always-present keychain
    fallback) regardless of what's configured on the machine running the test."""
    monkeypatch.setenv("WR2_VISION_COOLDOWN_STATE", str(tmp_path / "cooldown.json"))
    monkeypatch.setenv("WR2_VISION_FINGERPRINT_CACHE", str(tmp_path / "fingerprints.json"))
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "tok1")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_2", "tok2")
    for key in (
        "CLAUDE_CODE_OAUTH_TOKEN_3", "CLAUDE_CODE_OAUTH_TOKEN_4",
        "CLAUDE_CODE_OAUTH_TOKEN_5",
        # Slot 6 exists since the 2026-08-23 remap and claude_vision.py now
        # iterates to it. This helper builds the subprocess env from ambient
        # os.environ, so leaving 6 set here makes the chain one attempt longer
        # than the mocks are sized for — green on a clean runner, red on every
        # fleet machine, which is the docstring's "regardless of what's
        # configured on the machine" promise broken.
        "CLAUDE_CODE_OAUTH_TOKEN_6", "CLAUDE_CODE_OAUTH_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)


# ── chain-wide cooldown: GUILT ───────────────────────────────────────────────


def test_full_chain_rate_limited_arms_cooldown_and_next_call_spawns_nothing(
    monkeypatch, tmp_path
):
    """GUILT: every seat in the chain (token_1, token_2, keychain) reports
    rate-limit -> VisionRateLimited raised AND a cooldown is persisted. The
    VERY NEXT call, while the cooldown is active, must raise immediately
    WITHOUT invoking _run_process_group at all (zero subprocess spawned)."""
    _isolate_state(monkeypatch, tmp_path)
    monkeypatch.setenv("WR2_VISION_COOLDOWN_S", "3600")

    with patch.object(cv, "_run_process_group", side_effect=[
        _rate_limited_proc(), _rate_limited_proc(), _rate_limited_proc(),
    ]) as mocked:
        with pytest.raises(cv.VisionRateLimited):
            cv._run_claude_json("prompt", _SCHEMA)
        assert mocked.call_count == 3  # walked the whole chain once to prove it's dead

    assert cv._cooldown_remaining_s() > 0

    # second call: cooldown is armed — must short-circuit before any subprocess
    with patch.object(cv, "_run_process_group") as mocked_second:
        with pytest.raises(cv.VisionRateLimited):
            cv._run_claude_json("prompt", _SCHEMA)
        mocked_second.assert_not_called()


def test_cooldown_expired_resumes_normal_calls(monkeypatch, tmp_path):
    """A cooldown whose window has already elapsed must not block — the call
    proceeds and spawns a subprocess exactly like a fresh (never-cooled-down)
    call would."""
    _isolate_state(monkeypatch, tmp_path)
    # write an ALREADY-EXPIRED cooldown directly (simulates "tick N later")
    cv._cooldown_state_path().parent.mkdir(parents=True, exist_ok=True)
    cv._cooldown_state_path().write_text(json.dumps({
        "cooldown_until": time.time() - 10,
        "set_at": time.time() - 3610,
        "reason": "rate_limit",
    }))
    assert cv._cooldown_remaining_s() == 0.0

    with patch.object(cv, "_run_process_group", return_value=_success_proc({"ok": True})) as mocked:
        out = cv._run_claude_json("prompt", _SCHEMA)
        assert out == {"ok": True}
        mocked.assert_called_once()


# ── chain-wide cooldown: INNOCENCE ───────────────────────────────────────────


def test_single_seat_rate_limited_fails_over_without_arming_cooldown(monkeypatch, tmp_path):
    """INNOCENCE: seat 1 is rate-limited, seat 2 succeeds — normal failover,
    the call returns the successful verdict, and NO cooldown is armed (the
    chain was never proven fully dead)."""
    _isolate_state(monkeypatch, tmp_path)

    with patch.object(cv, "_run_process_group", side_effect=[
        _rate_limited_proc(), _success_proc({"passes": True}),
    ]) as mocked:
        out = cv._run_claude_json("prompt", _SCHEMA)
        assert out == {"passes": True}
        assert mocked.call_count == 2

    assert cv._cooldown_remaining_s() == 0.0


# ── fingerprint no-op cache ───────────────────────────────────────────────────


def test_identical_slide_prompt_image_skips_second_call(monkeypatch, tmp_path):
    """GUILT: same fingerprint_key + a prior SUCCESSFUL parse -> the second
    call is served from cache, no subprocess spawned."""
    _isolate_state(monkeypatch, tmp_path)

    with patch.object(cv, "_run_process_group", return_value=_success_proc({"passes": True})) as mocked:
        first = cv._run_claude_json("prompt", _SCHEMA, fingerprint_key="fp-1")
        assert first == {"passes": True}
        mocked.assert_called_once()

    with patch.object(cv, "_run_process_group") as mocked_second:
        second = cv._run_claude_json("prompt", _SCHEMA, fingerprint_key="fp-1")
        assert second == {"passes": True}
        mocked_second.assert_not_called()


def test_changed_input_does_not_skip_from_fingerprint(monkeypatch, tmp_path):
    """INNOCENCE: a DIFFERENT fingerprint_key (input changed — different slide,
    prompt template, or rendered pixels) must always call through."""
    _isolate_state(monkeypatch, tmp_path)

    with patch.object(cv, "_run_process_group", side_effect=[
        _success_proc({"passes": True}), _success_proc({"passes": False}),
    ]) as mocked:
        first = cv._run_claude_json("prompt", _SCHEMA, fingerprint_key="fp-1")
        second = cv._run_claude_json("prompt", _SCHEMA, fingerprint_key="fp-2")
        assert first == {"passes": True}
        assert second == {"passes": False}
        assert mocked.call_count == 2


def test_failed_call_never_seeds_the_fingerprint_cache(monkeypatch, tmp_path):
    """A call that never produces a parsed verdict (rate-limited, here) must
    NOT populate the cache — the next call with the SAME fingerprint_key
    still calls through instead of permanently reusing the missing verdict."""
    _isolate_state(monkeypatch, tmp_path)

    with patch.object(cv, "_run_process_group", side_effect=[
        _rate_limited_proc(), _rate_limited_proc(), _rate_limited_proc(),
    ]):
        with pytest.raises(cv.VisionRateLimited):
            cv._run_claude_json("prompt", _SCHEMA, fingerprint_key="fp-1")

    # cooldown is now active — clear it so this second call isn't short-circuited
    # by the (correctly-armed) cooldown instead of the fingerprint cache, which
    # is the specific thing this test is isolating.
    cv._cooldown_state_path().unlink(missing_ok=True)

    with patch.object(cv, "_run_process_group", return_value=_success_proc({"passes": True})) as mocked:
        out = cv._run_claude_json("prompt", _SCHEMA, fingerprint_key="fp-1")
        assert out == {"passes": True}
        mocked.assert_called_once()  # NOT a cache hit — the failed run never cached


# ── caller wiring: claude_design_critic / claude_brand_verifier fingerprints ──


def test_critic_and_verifier_fingerprints_differ_for_same_png(monkeypatch, tmp_path):
    """The critic and verifier use different prompt templates against the same
    PNG — their fingerprint keys must differ (role-scoped), else the verifier
    could be served the critic's cached verdict (wrong schema/shape)."""
    from wr2_html_renderer.claude_vision import _fingerprint_key
    png = tmp_path / "loop-01" / "iter-01.png"
    png.parent.mkdir(parents=True)
    png.write_bytes(b"\x89PNG-fake-bytes")
    critic_key = _fingerprint_key(png, cv._CRITIC_PROMPT, f"critic:{png.parent.name}")
    verifier_key = _fingerprint_key(png, cv._VERIFIER_PROMPT, f"brand:{png.parent.name}")
    assert critic_key != verifier_key
