"""Tests for scripts/arsenal_probe.py — empirical AI-seat liveness prober.

Module is imported via importlib.util.spec_from_file_location (not a package import)
because scripts/ is a flat bag of standalone tools, not a Python package (mirrors
scripts/tests/test_pending_arms_report.py).

NO live network/LLM calls anywhere in this file — every subprocess/HTTP boundary is
monkeypatched. Guilt AND innocence per classifier, per scar #3 (guard-over-match):
every positive-match test has a paired negative-match test on adjacent input.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import textwrap
import time
from pathlib import Path
from types import ModuleType
from typing import Optional

import pytest

MODULE_PATH = Path(__file__).resolve().parent.parent / "arsenal_probe.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("arsenal_probe", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ap = _load_module()


# ---------------------------------------------------------------------------
# classify_generic() — guilt AND innocence per status class (scar #3)
# ---------------------------------------------------------------------------


def test_pong_classifies_live():
    assert ap.classify_generic("PONG", live_signal=True, seat="claude", ssh_context=False) == ap.LIVE


def test_pong_never_auth_dead_even_with_stray_digits():
    # innocence: a live signal wins regardless of what other substrings are present
    ev = "PONG (request id 401999 latency 129ms)"
    assert ap.classify_generic(ev, live_signal=True, seat="claude", ssh_context=False) == ap.LIVE


def test_401_classifies_auth_dead():
    ev = "Error 401: authentication failed"
    assert ap.classify_generic(ev, live_signal=False, seat="codex", ssh_context=False) == ap.AUTH_DEAD


def test_token_revoked_classifies_auth_dead():
    ev = "token_revoked: please re-authenticate"
    assert ap.classify_generic(ev, live_signal=False, seat="codex", ssh_context=False) == ap.AUTH_DEAD


def test_refresh_token_reused_classifies_auth_dead():
    ev = "refresh_token_reused error from oauth server"
    assert ap.classify_generic(ev, live_signal=False, seat="codex", ssh_context=False) == ap.AUTH_DEAD


def test_recovered_codex_401_string_classifies_auth_dead():
    # #29 (2026-07-26): the exact terminal error recovered from Codex's own
    # rollout log for the real, transient AUTH_DEAD incident — a regression
    # guard on the specific string, not just the general 401 shape.
    ev = (
        "unexpected status 401 Unauthorized: Missing bearer or basic authentication "
        "in header, url: https://api.openai.com/v1/responses, cf-ray: "
        "a20b72431db49185-DPS, request id: 0f06c28b-a836-478c-ac86-4259815da99b"
    )
    assert ap.classify_generic(ev, live_signal=False, seat="codex", ssh_context=False) == ap.AUTH_DEAD


def test_real_observed_oauth_token_silently_revoked_classifies_auth_dead():
    # guilt, ROUND 2 (#34, 2026-07-26): the first version of this test used
    # "oauth token expired"/"invalid"/"revoked" — authored to fit the regex,
    # vacuous by construction (a strict-adjacent pattern trivially matches a
    # string built to be strict-adjacent). This is the real exemplar that
    # replaces it: Pro's logs/cron-agent/learning-pipeline.log:701, an actual
    # observed incident ("Tier-3 OAuth token silently revoked mid-cron, caught
    # post-facto"). It is an AI-summarized retrospective line, not a raw
    # captured stderr string — no raw exemplar for this shape was found on any
    # of the three machines — but it is a genuine description of a real event,
    # not text written to satisfy this test. The interposed "silently" is
    # exactly the failure-direction risk: under strict adjacency this seat
    # would have read as alive through a real auth death.
    ev = "Tier-3 OAuth token silently revoked mid-cron, caught post-facto"
    assert ap.classify_generic(ev, live_signal=False, seat="codex", ssh_context=False) == ap.AUTH_DEAD


def test_oauth_token_interposed_verb_shapes_classify_auth_dead():
    # guilt: bounded-proximity (not strict-adjacent) survives the verb a real
    # failure message routinely interposes between "oauth token" and the
    # failure word — "has expired", "is invalid", "was revoked". These three
    # are representative phrasings, not captured exemplars (the one real
    # exemplar we have is pinned separately above); kept as their own test so
    # a future regression to strict adjacency fails on the general shape too,
    # not only on the one sentence we happened to observe.
    for phrase in ["oauth token has expired", "oauth token is invalid", "oauth token was revoked"]:
        assert (
            ap.classify_generic(phrase, live_signal=False, seat="codex", ssh_context=False)
            == ap.AUTH_DEAD
        ), f"failed on: {phrase}"


def test_benign_oauth_token_mention_is_not_auth_dead():
    # innocence (#34, scar #3 guard-over-match): a bare mention of "oauth
    # token" with NO failure word present must not classify AUTH_DEAD — the
    # pre-fix pattern matched this exact shape of benign, healthy-operation
    # prose, which would have declared a live seat dead.
    ev = "Checking oauth token cache for refresh eligibility (routine)."
    status = ap.classify_generic(ev, live_signal=False, seat="codex", ssh_context=False)
    assert status != ap.AUTH_DEAD
    assert status == ap.UNKNOWN_ERR


def test_glm_1211_classifies_model_err_never_shed():
    ev = 'HTTP 400 {"error": {"code": 1211, "message": "Unknown Model"}}'
    status = ap.classify_generic(ev, live_signal=False, seat="glm", ssh_context=False)
    assert status == ap.MODEL_ERR
    assert status != ap.SHED


def test_unknown_model_text_classifies_model_err():
    ev = "Unknown Model requested: glm-99"
    assert ap.classify_generic(ev, live_signal=False, seat="glm", ssh_context=False) == ap.MODEL_ERR


def test_529_classifies_shed_never_model_err():
    ev = "HTTP 529 the server is overloaded, please retry"
    status = ap.classify_generic(ev, live_signal=False, seat="glm", ssh_context=False)
    assert status == ap.SHED
    assert status != ap.MODEL_ERR


def test_overloaded_text_classifies_shed():
    ev = "service overloaded right now"
    assert ap.classify_generic(ev, live_signal=False, seat="glm", ssh_context=False) == ap.SHED


def test_402_classifies_balance_dead():
    ev = "HTTP 402 Insufficient Balance"
    assert ap.classify_generic(ev, live_signal=False, seat="deepseek", ssh_context=False) == ap.BALANCE_DEAD


def test_insufficient_balance_text_classifies_balance_dead():
    ev = "Insufficient Balance on this account"
    assert ap.classify_generic(ev, live_signal=False, seat="deepseek", ssh_context=False) == ap.BALANCE_DEAD


def test_quota_strings_classify_quota_dead():
    for ev in [
        "out of extra usage for this session",
        "usage limit reached, try later",
        "429 too many requests",
        "rate limit exceeded",
        "quota exhausted",
        "You've hit your weekly limit · resets 9am (Asia/Makassar)",
    ]:
        assert (
            ap.classify_generic(ev, live_signal=False, seat="claude", ssh_context=False) == ap.QUOTA_DEAD
        ), f"failed on: {ev}"


def test_quota_dead_never_matches_401_evidence():
    # innocence: an auth-class string must not fall through to quota-dead
    ev = "401 Authentication Failed"
    status = ap.classify_generic(ev, live_signal=False, seat="codex", ssh_context=False)
    assert status == ap.AUTH_DEAD
    assert status != ap.QUOTA_DEAD


def test_unrecognized_evidence_classifies_unknown_err():
    ev = "connection reset by peer, no idea why"
    assert ap.classify_generic(ev, live_signal=False, seat="claude", ssh_context=False) == ap.UNKNOWN_ERR


def test_weekly_word_alone_does_not_classify_quota_dead():
    # innocence: "weekly" in an unrelated sentence must not fall through to
    # quota-dead — only the "weekly limit" phrase (the real claude CLI wording) does.
    ev = "weekly digest job completed successfully"
    assert ap.classify_generic(ev, live_signal=False, seat="claude", ssh_context=False) == ap.UNKNOWN_ERR


def test_empty_evidence_classifies_unknown_err_not_live():
    assert ap.classify_generic("", live_signal=False, seat="claude", ssh_context=False) == ap.UNKNOWN_ERR


# ---------------------------------------------------------------------------
# agy CONTEXT_AUTH vs AUTH_DEAD — context differs the cure (spec-explicit split)
# ---------------------------------------------------------------------------


def test_agy_auth_failure_under_ssh_is_context_auth():
    ev = "OAuth token invalid, authentication failed"
    status = ap.classify_generic(ev, live_signal=False, seat="agy", ssh_context=True)
    assert status == ap.CONTEXT_AUTH


def test_agy_auth_failure_without_ssh_is_auth_dead():
    ev = "OAuth token invalid, authentication failed"
    status = ap.classify_generic(ev, live_signal=False, seat="agy", ssh_context=False)
    assert status == ap.AUTH_DEAD


def test_non_agy_seat_auth_failure_ignores_ssh_context():
    # innocence: the ssh-context carve-out is agy-specific, not global
    ev = "401 authentication failed"
    status_ssh = ap.classify_generic(ev, live_signal=False, seat="codex", ssh_context=True)
    status_no_ssh = ap.classify_generic(ev, live_signal=False, seat="codex", ssh_context=False)
    assert status_ssh == ap.AUTH_DEAD
    assert status_no_ssh == ap.AUTH_DEAD


# ---------------------------------------------------------------------------
# healthy() / context_limited() / is_strict_fail()
# ---------------------------------------------------------------------------


def test_healthy_true_only_for_live():
    assert ap.healthy(ap.LIVE) is True
    for status in [ap.AUTH_DEAD, ap.QUOTA_DEAD, ap.TIMEOUT, ap.CRED_UNAVAILABLE, ap.NOT_INSTALLED]:
        assert ap.healthy(status) is False


def test_context_limited_set():
    for status in [ap.CONTEXT_AUTH, ap.CRED_UNAVAILABLE, ap.NOT_INSTALLED]:
        assert ap.context_limited(status) is True
    for status in [ap.LIVE, ap.AUTH_DEAD, ap.QUOTA_DEAD, ap.SHED, ap.TIMEOUT]:
        assert ap.context_limited(status) is False


def test_strict_fail_set():
    for status in [ap.AUTH_DEAD, ap.BALANCE_DEAD, ap.MODEL_ERR, ap.UNKNOWN_ERR]:
        assert ap.is_strict_fail(status) is True
    # transient statuses are alarm-worthy but never strict-fail (spec explicit)
    for status in [ap.QUOTA_DEAD, ap.SHED, ap.TIMEOUT, ap.LIVE]:
        assert ap.is_strict_fail(status) is False
    # host limitations never strict-fail either
    for status in [ap.CRED_UNAVAILABLE, ap.NOT_INSTALLED, ap.CONTEXT_AUTH]:
        assert ap.is_strict_fail(status) is False


# ---------------------------------------------------------------------------
# scrub() — redaction (scar #4, non-negotiable)
# ---------------------------------------------------------------------------


def test_scrub_removes_bearer_token():
    text = "request failed: Authorization: Bearer abcdefghijklmnopqrstuvwxyz1234567890 rejected"
    scrubbed = ap.scrub(text)
    assert "abcdefghijklmnopqrstuvwxyz1234567890" not in scrubbed
    assert "<REDACTED>" in scrubbed


def test_scrub_removes_sk_prefixed_token():
    text = "key sk-abc123def456ghi789jkl0mno leaked in log"
    scrubbed = ap.scrub(text)
    assert "sk-abc123def456ghi789jkl0mno" not in scrubbed


def test_scrub_removes_long_alnum_token():
    text = "token value AbCdEf0123456789AbCdEf0123456789 was used"
    scrubbed = ap.scrub(text)
    assert "AbCdEf0123456789AbCdEf0123456789" not in scrubbed


def test_scrub_removes_exact_extra_secret_even_if_short():
    text = "the loaded value shortsecret123 was rejected"
    scrubbed = ap.scrub(text, extra_secrets=["shortsecret123"])
    assert "shortsecret123" not in scrubbed


def test_scrub_leaves_normal_prose_untouched():
    # innocence: scrub must not eat ordinary text that merely resembles nothing secret
    text = "the request timed out after 45 seconds with no response"
    assert ap.scrub(text) == text


def test_scrub_leaves_short_status_words_untouched():
    text = "HTTP 200 OK model glm-5.2 responded"
    assert ap.scrub(text) == text


def test_evidence_tail_truncates_and_scrubs():
    long_secret = "x" * 40
    text = f"prefix {long_secret} suffix " + ("padding " * 40)
    tail = ap.evidence_tail(text, limit=160)
    assert len(tail) <= 160
    assert long_secret not in tail


def test_evidence_tail_keeps_the_tail_not_the_head():
    # guilt (#34): the diagnostic part — the actual error — lives past the
    # first 160 chars of a real Codex startup banner; a head-truncation
    # (the pre-fix behavior) drops it entirely. This is the exact shape
    # #29 needed a second data source to recover.
    head = "Reading additional input from stdin... OpenAI Codex v0.145.0 -------- " * 3
    error_tail = (
        "unexpected status 401 Unauthorized: Missing bearer or basic "
        "authentication in header, url: https://api.openai.com/v1/responses"
    )
    text = head + error_tail
    result = ap.evidence_tail(text, limit=160)
    assert error_tail[-100:] in result
    assert len(result) <= 160


def test_evidence_tail_short_text_returned_whole():
    # innocence: text already within the cap is untouched either way — the
    # fix changes which end survives truncation, not the untruncated case.
    text = "PONG all good"
    assert ap.evidence_tail(text, limit=160) == text


# ---------------------------------------------------------------------------
# Credential loaders — CRED_UNAVAILABLE never strict-fails, never logs secrets
# ---------------------------------------------------------------------------


def test_keychain_locked_returns_cred_unavailable_reason(monkeypatch):
    class FakeCompleted:
        returncode = 36
        stdout = ""
        stderr = ""

    def fake_run(cmd, **kwargs):
        return FakeCompleted()

    monkeypatch.setattr(ap.subprocess, "run", fake_run)
    monkeypatch.setattr(ap.shutil, "which", lambda name: "/usr/bin/security" if name == "security" else None)
    token, note = ap.load_keychain_token("glm-coding-plan-token")
    assert token is None
    assert note is not None
    assert "36" in note or "locked" in note.lower() or "absent" in note.lower()


def test_keychain_success_returns_token_never_in_note(monkeypatch):
    class FakeCompleted:
        returncode = 0
        stdout = "supersecrettoken123\n"
        stderr = ""

    monkeypatch.setattr(ap.subprocess, "run", lambda cmd, **kwargs: FakeCompleted())
    monkeypatch.setattr(ap.shutil, "which", lambda name: "/usr/bin/security" if name == "security" else None)
    token, note = ap.load_keychain_token("glm-coding-plan-token")
    assert token == "supersecrettoken123"
    assert note is None


def test_keychain_binary_absent_is_cred_unavailable(monkeypatch):
    monkeypatch.setattr(ap.shutil, "which", lambda name: None)
    token, note = ap.load_keychain_token("glm-coding-plan-token")
    assert token is None
    assert note is not None


def test_env_master_missing_file_is_cred_unavailable(tmp_path):
    missing = tmp_path / "does-not-exist" / ".env.master"
    key, note = ap.load_env_master_key("DEEPSEEK_API_KEY", path=str(missing))
    assert key is None
    assert "not found" in (note or "")


def test_env_master_parses_value_never_logs_full_line(tmp_path):
    envfile = tmp_path / ".env.master"
    envfile.write_text("OTHER_VAR=irrelevant\nDEEPSEEK_API_KEY=sk-realvalue999\nMORE=stuff\n")
    key, note = ap.load_env_master_key("DEEPSEEK_API_KEY", path=str(envfile))
    assert key == "sk-realvalue999"
    assert note is None


def test_env_master_key_absent_from_present_file(tmp_path):
    envfile = tmp_path / ".env.master"
    envfile.write_text("OTHER_VAR=irrelevant\n")
    key, note = ap.load_env_master_key("DEEPSEEK_API_KEY", path=str(envfile))
    assert key is None
    assert "not set" in (note or "")


def test_tp1_settings_loader_reads_only_named_env_key(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps(
            {
                "env": {
                    "UNRELATED_SETTING": "leave-alone",
                    "BAILIAN_TOKEN_PLAN_API_KEY": "test-only-placeholder",
                },
                "other": {"nested": "ignored"},
            }
        )
    )
    key, note = ap.load_tp1_settings_key(path=str(settings))
    assert key == "test-only-placeholder"
    assert note is None


def test_tp1_settings_loader_missing_named_key_is_cred_unavailable(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"env": {"UNRELATED_SETTING": "leave-alone"}}))
    key, note = ap.load_tp1_settings_key(path=str(settings))
    assert key is None
    assert "BAILIAN_TOKEN_PLAN_API_KEY" in (note or "")


def test_tp1_settings_loader_undecodable_bytes_is_cred_unavailable_not_raised(tmp_path):
    """GUILT (Kimi round-2 finding #1): a stray non-UTF-8 byte in
    ~/.qwen/settings.json raises UnicodeDecodeError from read_text() itself,
    BEFORE json.loads ever runs. The old except clause only caught
    (OSError, json.JSONDecodeError) — UnicodeDecodeError is neither, so it
    propagated uncaught out of load_tp1_settings_key. Since all seven TP1
    seats read this SAME file independently, that would mis-tag all seven
    UNKNOWN_ERR (strict-fail) instead of the honest CRED_UNAVAILABLE
    (context-limited, non-strict). Must not raise."""
    settings = tmp_path / "settings.json"
    settings.write_bytes(b'{"env": {"BAILIAN_TOKEN_PLAN_API_KEY": "\xff\xfe not valid utf-8"}}')
    key, note = ap.load_tp1_settings_key(path=str(settings))
    assert key is None
    assert note is not None
    assert "UnicodeDecodeError" in note


# ---------------------------------------------------------------------------
# HTTP layer — monkeypatched urlopen, exceptions never leak Authorization header
# ---------------------------------------------------------------------------


class _FakeHTTPResponse:
    def __init__(self, status: int, body: bytes):
        self.status = status
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_http_post_json_200_returns_scrubbed_evidence(monkeypatch):
    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(200, b'{"model": "glm-5.2", "id": "abc"}')

    monkeypatch.setattr(ap.urllib.request, "urlopen", fake_urlopen)
    status, full, tail = ap.http_post_json(
        "https://api.z.ai/x", {"Authorization": "Bearer secrettoken12345678901234"}, {}, 10, ["secrettoken12345678901234"]
    )
    assert status == 200
    assert "glm-5.2" in full
    assert "glm-5.2" in tail
    assert "secrettoken12345678901234" not in full
    assert "secrettoken12345678901234" not in tail


def test_http_post_json_full_body_is_untruncated_past_160_chars(monkeypatch):
    # scar (2026-08-21): the live-check marker must survive even when it sits
    # BEFORE the last 160 chars of a long body — `full` is not tail-truncated.
    # Padding uses short SPACED words, not one long run: any 24+-char contiguous
    # alnum/._- run is itself redacted as token-shaped by scrub() (scar #4), which
    # would shrink the body back under the tail window and hide the exact defect
    # this test exists to pin.
    padding = " ".join(["lorem"] * 40)
    long_body = ('{"model": "glm-5.2", "padding": "' + padding + '"}').encode()

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(200, long_body)

    monkeypatch.setattr(ap.urllib.request, "urlopen", fake_urlopen)
    status, full, tail = ap.http_post_json("https://api.z.ai/x", {}, {}, 10, [])
    assert status == 200
    assert '"model": "glm-5.2"' in full  # present in the untruncated body
    assert '"model": "glm-5.2"' not in tail  # and absent from the 160-char tail
    assert len(tail) <= 160


def test_http_post_json_error_never_leaks_authorization_value(monkeypatch):
    import urllib.error

    def fake_urlopen(req, timeout):
        # simulate a server that echoes the request headers back in the error body
        # (worst case scenario the redaction must survive)
        body = f'{{"error": "unauthorized", "your_header_was": "Bearer secrettoken12345678901234"}}'.encode()
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr(ap.urllib.request, "urlopen", fake_urlopen)
    status, full, tail = ap.http_post_json(
        "https://api.z.ai/x", {"Authorization": "Bearer secrettoken12345678901234"}, {}, 10, ["secrettoken12345678901234"]
    )
    assert status == 401
    assert "secrettoken12345678901234" not in full
    assert "secrettoken12345678901234" not in tail


def test_http_post_json_url_error_is_scrubbed(monkeypatch):
    import urllib.error

    def fake_urlopen(req, timeout):
        raise urllib.error.URLError("connection refused, token was secrettoken12345678901234")

    monkeypatch.setattr(ap.urllib.request, "urlopen", fake_urlopen)
    status, full, tail = ap.http_post_json(
        "https://api.z.ai/x", {}, {}, 10, ["secrettoken12345678901234"]
    )
    assert status is None
    assert "secrettoken12345678901234" not in full
    assert "secrettoken12345678901234" not in tail


# ---------------------------------------------------------------------------
# Per-seat probes — subprocess/HTTP fully monkeypatched
# ---------------------------------------------------------------------------


class _FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_probe_claude_pong_is_live(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/opt/homebrew/bin/claude", True))
    monkeypatch.setattr(ap.subprocess, "run", lambda cmd, **kwargs: _FakeProc(0, "PONG\n", ""))
    status, ev, latency = ap.probe_claude(timeout=5)
    assert status == ap.LIVE
    assert latency >= 0


def test_probe_claude_strips_anthropic_api_key_from_env(monkeypatch):
    captured_env = {}

    def fake_run(cmd, **kwargs):
        captured_env.update(kwargs.get("env") or {})
        return _FakeProc(0, "PONG\n", "")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "should-never-be-passed-through")
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/opt/homebrew/bin/claude", True))
    monkeypatch.setattr(ap.subprocess, "run", fake_run)
    ap.probe_claude(timeout=5)
    assert "ANTHROPIC_API_KEY" not in captured_env


def test_probe_claude_falls_back_to_oauth_token_slot_1(monkeypatch):
    # guilt: bare CLAUDE_CODE_OAUTH_TOKEN absent, slotted _1 present (the real
    # headless/cron shape) — probe_claude must promote it so the claude binary
    # can actually authenticate instead of reporting a false UNKNOWN_ERR.
    captured_env = {}

    def fake_run(cmd, **kwargs):
        captured_env.update(kwargs.get("env") or {})
        return _FakeProc(0, "PONG\n", "")

    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "slot1-token-value")
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/opt/homebrew/bin/claude", True))
    monkeypatch.setattr(ap.subprocess, "run", fake_run)
    ap.probe_claude(timeout=5)
    assert captured_env.get("CLAUDE_CODE_OAUTH_TOKEN") == "slot1-token-value"


def test_probe_claude_strips_ambient_oauth_token_2026_08_08(monkeypatch):
    # guilt: this is the live incident. A bare CLAUDE_CODE_OAUTH_TOKEN already
    # present in the environment (the shape of an interactive Claude Code
    # session probing its own seat) must be STRIPPED, not preserved — it may
    # be stale from an earlier /login cycle and shadow a perfectly valid
    # on-disk credential. Without stripping it, the calling shell's own token
    # reaches the claude binary verbatim and a revoked one produces a false
    # AUTH_DEAD read of a live seat (measured 2026-08-08 on M5: unsetting the
    # var and re-probing flipped AUTH_DEAD -> LIVE with no other change).
    captured_env = {}

    def fake_run(cmd, **kwargs):
        captured_env.update(kwargs.get("env") or {})
        return _FakeProc(0, "PONG\n", "")

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "ambient-session-token-possibly-stale")
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN_1", raising=False)
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/opt/homebrew/bin/claude", True))
    monkeypatch.setattr(ap.subprocess, "run", fake_run)
    ap.probe_claude(timeout=5)
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in captured_env


def test_probe_claude_explicit_override_still_wins(monkeypatch):
    # innocence: a caller that deliberately wants to test ONE specific token
    # still can, via the env_overrides parameter — the only sanctioned
    # injection path (nothing in the codebase calls it today, but the
    # capability must survive the ambient-token strip above).
    captured_env = {}

    def fake_run(cmd, **kwargs):
        captured_env.update(kwargs.get("env") or {})
        return _FakeProc(0, "PONG\n", "")

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "ambient-token-must-be-ignored")
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/opt/homebrew/bin/claude", True))
    monkeypatch.setattr(ap.subprocess, "run", fake_run)
    ap.probe_claude(timeout=5, env_overrides={"CLAUDE_CODE_OAUTH_TOKEN": "deliberately-injected-token"})
    assert captured_env.get("CLAUDE_CODE_OAUTH_TOKEN") == "deliberately-injected-token"


def test_probe_claude_binary_absent_is_not_installed(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: (None, False))
    monkeypatch.delenv("ARSENAL_CLAUDE_BIN", raising=False)
    status, ev, latency = ap.probe_claude(timeout=5)
    assert status == ap.NOT_INSTALLED
    assert ap.is_strict_fail(status) is False


def test_probe_claude_timeout_classifies_timeout(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise ap.subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 5))

    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/opt/homebrew/bin/claude", True))
    monkeypatch.setattr(ap.subprocess, "run", fake_run)
    status, ev, latency = ap.probe_claude(timeout=5)
    assert status == ap.TIMEOUT


def test_probe_claude_not_logged_in_classifies_auth_dead(monkeypatch):
    # guilt: real exemplar captured in ~/.organism/arsenal/last.json on Mini
    # (2026-08-05T04:53:56Z) — the claude CLI's unauthenticated shape has no
    # 401/oauth-token marker, only this short prose, and previously fell
    # through classify_generic() to a bare UNKNOWN_ERR. Same shape as kimi's
    # "No providers configured" (probe_kimi) — mirrored locally here so the
    # shared _AUTH_DEAD_PAT keeps its existing guilt+innocence corpus untouched.
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/opt/homebrew/bin/claude", True))
    monkeypatch.setattr(
        ap.subprocess,
        "run",
        lambda cmd, **kwargs: _FakeProc(1, "", "Not logged in · Please run /login"),
    )
    status, ev, latency = ap.probe_claude(timeout=5)
    assert status == ap.AUTH_DEAD


def test_probe_claude_pong_mentioning_login_stays_live(monkeypatch):
    # innocence: a LIVE answer that happens to mention login in prose must
    # never be reclassified as a credential death (mirrors
    # test_probe_kimi_pong_with_provider_prose_stays_live).
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/opt/homebrew/bin/claude", True))
    monkeypatch.setattr(
        ap.subprocess,
        "run",
        lambda cmd, **kwargs: _FakeProc(0, "PONG (session resumed, not logged in again today)\n", ""),
    )
    status, ev, latency = ap.probe_claude(timeout=5)
    assert status == ap.LIVE


def test_probe_glm_cred_unavailable_when_keychain_locked(monkeypatch):
    monkeypatch.setattr(ap, "load_keychain_token", lambda service, timeout=10: (None, "keychain locked"))
    status, ev, latency = ap.probe_glm(timeout=5)
    assert status == ap.CRED_UNAVAILABLE
    assert ap.is_strict_fail(status) is False


def test_probe_glm_live_on_200_with_model(monkeypatch):
    monkeypatch.setattr(ap, "load_keychain_token", lambda service, timeout=10: ("tok123456789012345678901", None))
    monkeypatch.setattr(ap, "http_post_json", lambda *a, **kw: (200, '{"model": "glm-5.2"}', '{"model": "glm-5.2"}'))
    status, ev, latency = ap.probe_glm(timeout=5)
    assert status == ap.LIVE


def test_probe_glm_live_when_model_marker_only_survives_in_full_body(monkeypatch):
    # GUILT case (2026-08-21 scar): a genuinely LIVE 200 response whose "model" field
    # sits before the 160-char tail must still classify LIVE — this is exactly the
    # shape z.ai's Anthropic-compatible envelope produces (model near the start,
    # content/usage padding pushes it out of any tail window). Before the fix this
    # read UNKNOWN_ERR — a live seat silently misread as dead.
    monkeypatch.setattr(ap, "load_keychain_token", lambda service, timeout=10: ("tok123456789012345678901", None))
    full_body = '{"model": "glm-5.2", "id": "abc", "content": "' + ("y" * 300) + '"}'
    tail_only = full_body[-160:]
    assert '"model"' not in tail_only  # premise: the marker really is outside the tail
    monkeypatch.setattr(ap, "http_post_json", lambda *a, **kw: (200, full_body, tail_only))
    status, ev, latency = ap.probe_glm(timeout=5)
    assert status == ap.LIVE


def test_probe_glm_not_live_when_model_absent_from_full_body(monkeypatch):
    # INNOCENCE case: a genuinely dead/malformed 200 with no "model" field anywhere
    # (not even truncated away) must NOT read LIVE — the fix widens WHERE the check
    # looks, it must not widen WHAT counts as a positive marker.
    monkeypatch.setattr(ap, "load_keychain_token", lambda service, timeout=10: ("tok123456789012345678901", None))
    full_body = '{"id": "abc", "content": "' + ("y" * 300) + '"}'
    monkeypatch.setattr(ap, "http_post_json", lambda *a, **kw: (200, full_body, full_body[-160:]))
    status, ev, latency = ap.probe_glm(timeout=5)
    assert status != ap.LIVE


def test_probe_glm_model_err_on_1211(monkeypatch):
    monkeypatch.setattr(ap, "load_keychain_token", lambda service, timeout=10: ("tok123456789012345678901", None))
    body = '{"error": {"code": 1211, "message": "Unknown Model"}}'
    monkeypatch.setattr(ap, "http_post_json", lambda *a, **kw: (400, body, body))
    status, ev, latency = ap.probe_glm(timeout=5)
    assert status == ap.MODEL_ERR


def test_probe_glm_never_leaks_token_in_evidence(monkeypatch):
    token = "leaktoken1234567890123456"
    monkeypatch.setattr(ap, "load_keychain_token", lambda service, timeout=10: (token, None))

    def fake_http(url, headers, body, timeout, secret_values):
        assert token in secret_values  # the probe must pass its own secret for scrubbing
        scrubbed = ap.evidence_tail(f"unauthorized, saw {token}", secret_values)
        return 401, scrubbed, scrubbed

    monkeypatch.setattr(ap, "http_post_json", fake_http)
    status, ev, latency = ap.probe_glm(timeout=5)
    assert token not in ev


def _tp1_live_body(model: str, content: str = "PONG") -> str:
    return json.dumps(
        {
            "model": model,
            "choices": [{"message": {"role": "assistant", "content": content}}],
        }
    )


def test_probe_tp1_missing_credential_is_cred_unavailable(monkeypatch):
    monkeypatch.setattr(
        ap,
        "load_tp1_settings_key",
        lambda: (None, "env.BAILIAN_TOKEN_PLAN_API_KEY not set"),
    )
    status, ev, latency = ap.probe_tp1_model("qwen3.8-max", timeout=5)
    assert status == ap.CRED_UNAVAILABLE
    assert status != ap.UNKNOWN_ERR
    assert ap.is_strict_fail(status) is False


def test_probe_tp1_http_error_does_not_abort_remaining_models(monkeypatch):
    monkeypatch.setattr(
        ap,
        "load_tp1_settings_key",
        lambda: ("test-only-placeholder", None),
    )
    called = []

    def fake_http(url, headers, body, timeout, secret_values):
        model = body["model"]
        called.append(model)
        if model == "deepseek-v4-pro":
            error = '{"error":{"message":"provider failure"}}'
            return 500, error, error
        live = _tp1_live_body(model)
        return 200, live, live

    monkeypatch.setattr(ap, "http_post_json", fake_http)
    monkeypatch.setattr(ap, "load_last_report", lambda: None)
    seats = ["tp1-deepseek-v4-pro", "tp1-qwen3.8-max"]
    report = ap.run(seats, timeout_mult=1.0, live_gen=False, machine="m5")
    statuses = {row["seat"]: row["status"] for row in report["seats"]}
    assert statuses["tp1-deepseek-v4-pro"] == ap.UNKNOWN_ERR
    assert statuses["tp1-qwen3.8-max"] == ap.LIVE
    assert set(called) == {"deepseek-v4-pro", "qwen3.8-max"}


def test_probe_tp1_401_is_auth_dead(monkeypatch):
    monkeypatch.setattr(
        ap,
        "load_tp1_settings_key",
        lambda: ("test-only-placeholder", None),
    )
    body = '{"error":{"message":"unauthorized"}}'
    monkeypatch.setattr(ap, "http_post_json", lambda *a, **kw: (401, body, body))
    status, ev, latency = ap.probe_tp1_model("glm-5.2", timeout=5)
    assert status == ap.AUTH_DEAD


def test_probe_tp1_429_quota_wording_is_quota_dead_not_unknown_err(monkeypatch):
    """Kimi round-2 finding #5: quota classification for TP1 was unpinned —
    only 401 had a test. This is the exact failure mode that killed the OLD
    per-token DeepSeek door (silent balance/quota exhaustion misreported as a
    generic error): pin it so a regression here is caught the same way."""
    monkeypatch.setattr(
        ap,
        "load_tp1_settings_key",
        lambda: ("test-only-placeholder", None),
    )
    body = '{"error":{"message":"Requests rate limit exceeded, please try again later.","code":"Throttling.RateQuota"}}'
    monkeypatch.setattr(ap, "http_post_json", lambda *a, **kw: (429, body, body))
    status, ev, latency = ap.probe_tp1_model("qwen3.6-flash", timeout=5)
    assert status == ap.QUOTA_DEAD
    assert status != ap.UNKNOWN_ERR


def test_probe_tp1_402_insufficient_balance_is_balance_dead(monkeypatch):
    """Companion to the 429 pin — the 402/insufficient-balance wording (the
    exact shape of the retired old DeepSeek per-token door) must classify
    BALANCE_DEAD through the same "tp1" classify_generic path."""
    monkeypatch.setattr(
        ap,
        "load_tp1_settings_key",
        lambda: ("test-only-placeholder", None),
    )
    body = '{"error":{"message":"insufficient balance","code":"402"}}'
    monkeypatch.setattr(ap, "http_post_json", lambda *a, **kw: (402, body, body))
    status, ev, latency = ap.probe_tp1_model("deepseek-v4-flash-0731", timeout=5)
    assert status == ap.BALANCE_DEAD


def test_probe_tp1_model_mismatch_is_noted_but_not_fatal(monkeypatch):
    """Kimi round-2 finding #4: a gateway silently rerouting to a fallback
    model must not be invisible — note the mismatch, but a mismatch alone is
    NOT grounds to call the seat dead (the gateway may legitimately omit or
    normalize the echoed model field)."""
    monkeypatch.setattr(
        ap,
        "load_tp1_settings_key",
        lambda: ("test-only-placeholder", None),
    )
    body = _tp1_live_body("qwen3.8-max-fallback-v2", "PONG")
    monkeypatch.setattr(ap, "http_post_json", lambda *a, **kw: (200, body, body))
    status, ev, latency = ap.probe_tp1_model("qwen3.8-max", timeout=5)
    assert status == ap.LIVE
    assert "qwen3.8-max-fallback-v2" in ev
    assert "requested qwen3.8-max" in ev


def test_probe_tp1_content_mentioning_api_key_phrase_stays_live(monkeypatch):
    """The PHRASE 'api key' inside a model's own answer must not be misread as
    an auth-dead signal (guard-over-match, scar family #3) — this is about the
    classifier's word-boundary discipline, NOT about leak-safety of the real
    credential (see test_probe_tp1_never_leaks_token_in_evidence for that)."""
    monkeypatch.setattr(
        ap,
        "load_tp1_settings_key",
        lambda: ("test-only-placeholder", None),
    )
    body = _tp1_live_body("qwen3.7-plus", "PONG — api key hygiene is enabled")
    monkeypatch.setattr(ap, "http_post_json", lambda *a, **kw: (200, body, body))
    status, ev, latency = ap.probe_tp1_model("qwen3.7-plus", timeout=5)
    assert status == ap.LIVE


def test_probe_tp1_never_leaks_token_in_evidence(monkeypatch):
    """Kimi round-2 finding #3: every other TP1 test mocks http_post_json
    entirely, so the real scrub()/redaction path for THIS door was never
    exercised — in the shape of test_probe_glm_never_leaks_token_in_evidence."""
    token = "tp1-leaktoken1234567890123456"
    monkeypatch.setattr(
        ap,
        "load_tp1_settings_key",
        lambda: (token, None),
    )

    def fake_http(url, headers, body, timeout, secret_values):
        assert token in secret_values  # the probe must pass its own secret for scrubbing
        scrubbed = ap.evidence_tail(f"unauthorized, saw {token}", secret_values)
        return 401, scrubbed, scrubbed

    monkeypatch.setattr(ap, "http_post_json", fake_http)
    status, ev, latency = ap.probe_tp1_model("glm-5.2", timeout=5)
    assert token not in ev


def _tp1_reasoning_only_body(model: str, reasoning_tokens: int = 8, finish_reason=None) -> str:
    choice: dict = {
        "message": {
            "role": "assistant",
            "content": "",
            "reasoning_content": "thinking about the reply...",
        }
    }
    if finish_reason is not None:
        choice["finish_reason"] = finish_reason
    return json.dumps(
        {
            "model": model,
            "choices": [choice],
            "usage": {
                "completion_tokens_details": {"reasoning_tokens": reasoning_tokens}
            },
        }
    )


def test_probe_tp1_thinking_model_empty_content_with_reasoning_is_live(monkeypatch):
    """GUILT: the exact 2026-08-23 live regression.

    HTTP 200, message.content == "", message.reasoning_content non-empty,
    reasoning_tokens == 8 (the whole old max_tokens=8 budget spent on
    reasoning). This is a live, answering model — the empty content is a
    budget artifact, not a dead seat. Must NOT be UNKNOWN_ERR.
    """
    monkeypatch.setattr(
        ap,
        "load_tp1_settings_key",
        lambda: ("test-only-placeholder", None),
    )
    body = _tp1_reasoning_only_body("deepseek-v4-pro", reasoning_tokens=8)
    monkeypatch.setattr(ap, "http_post_json", lambda *a, **kw: (200, body, body))
    status, ev, latency = ap.probe_tp1_model("deepseek-v4-pro", timeout=5)
    assert status == ap.LIVE
    assert status != ap.UNKNOWN_ERR


def test_probe_tp1_empty_content_no_reasoning_stays_unknown_err(monkeypatch):
    """INNOCENCE: HTTP 200 with nothing in content AND nothing in
    reasoning_content has no positive proof of life — stays UNKNOWN_ERR."""
    monkeypatch.setattr(
        ap,
        "load_tp1_settings_key",
        lambda: ("test-only-placeholder", None),
    )
    body = json.dumps(
        {
            "model": "glm-5.2",
            "choices": [{"message": {"role": "assistant", "content": ""}}],
        }
    )
    monkeypatch.setattr(ap, "http_post_json", lambda *a, **kw: (200, body, body))
    status, ev, latency = ap.probe_tp1_model("glm-5.2", timeout=5)
    assert status == ap.UNKNOWN_ERR


def test_probe_tp1_reasoning_only_truncated_by_length_is_not_live(monkeypatch):
    """GUILT (Kimi round-2 finding #2): my own round-1 fix reintroduced a
    false-GREEN on the same axis. A degraded/throttled thinking model that
    burns the WHOLE 256-token budget on reasoning returns content: "",
    truncated reasoning_content, and finish_reason: "length" — this produced
    NOTHING usable for a real caller and must not be LIVE forever just
    because reasoning_content happened to be non-empty."""
    monkeypatch.setattr(
        ap,
        "load_tp1_settings_key",
        lambda: ("test-only-placeholder", None),
    )
    body = _tp1_reasoning_only_body(
        "deepseek-v4-pro", reasoning_tokens=256, finish_reason="length"
    )
    monkeypatch.setattr(ap, "http_post_json", lambda *a, **kw: (200, body, body))
    status, ev, latency = ap.probe_tp1_model("deepseek-v4-pro", timeout=5)
    assert status != ap.LIVE
    assert status == ap.UNKNOWN_ERR


def test_probe_tp1_reasoning_only_with_finish_reason_stop_stays_live(monkeypatch):
    """INNOCENCE: same reasoning-only shape, but finish_reason: "stop" means
    the model genuinely finished its turn without ever writing to `content`
    (some thinking models do this) — that is still a live, working seat."""
    monkeypatch.setattr(
        ap,
        "load_tp1_settings_key",
        lambda: ("test-only-placeholder", None),
    )
    body = _tp1_reasoning_only_body(
        "deepseek-v4-pro", reasoning_tokens=40, finish_reason="stop"
    )
    monkeypatch.setattr(ap, "http_post_json", lambda *a, **kw: (200, body, body))
    status, ev, latency = ap.probe_tp1_model("deepseek-v4-pro", timeout=5)
    assert status == ap.LIVE


def test_probe_tp1_pong_content_stays_live_already_covered(monkeypatch):
    """INNOCENCE (already covered by test_probe_tp1_content_mentioning_api_key_phrase_stays_live
    above, checked here explicitly for the plain PONG case)."""
    monkeypatch.setattr(
        ap,
        "load_tp1_settings_key",
        lambda: ("test-only-placeholder", None),
    )
    body = _tp1_live_body("qwen3.8-max", "PONG")
    monkeypatch.setattr(ap, "http_post_json", lambda *a, **kw: (200, body, body))
    status, ev, latency = ap.probe_tp1_model("qwen3.8-max", timeout=5)
    assert status == ap.LIVE


def test_tp1_probe_max_tokens_budget_is_at_least_256():
    """Pin the budget constant.

    Measured live 2026-08-23: at max_tokens=8, three thinking models
    (deepseek-v4-pro, deepseek-v4-flash-0731, glm-5.2) spent the whole
    budget on reasoning_tokens and returned empty content — three live
    seats misreported UNKNOWN_ERR. Reasoning ran as long as 171 tokens on
    qwen3.7-max before it answered. If this test goes red because someone
    lowered TP1_PROBE_MAX_TOKENS back toward 8, re-measure reasoning_tokens
    on all seven TP1 models before touching it again.
    """
    assert ap.TP1_PROBE_MAX_TOKENS >= 256


def test_probe_agy_pong_is_live(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/opt/homebrew/bin/agy", True))
    monkeypatch.setattr(ap.subprocess, "run", lambda cmd, **kwargs: _FakeProc(0, "PONG\n", ""))
    status, ev, latency = ap.probe_agy(timeout=5)
    assert status == ap.LIVE


def test_probe_agy_missing_binary_not_installed(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: (None, False))
    status, ev, latency = ap.probe_agy(timeout=5)
    assert status == ap.NOT_INSTALLED


def test_probe_kimi_pong_is_live(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/Users/x/.kimi-code/bin/kimi", True))
    monkeypatch.setattr(ap.subprocess, "run", lambda cmd, **kwargs: _FakeProc(0, "• PONG\n", ""))
    status, ev, latency = ap.probe_kimi(timeout=5)
    assert status == ap.LIVE


def test_probe_kimi_missing_binary_not_installed(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: (None, False))
    status, ev, latency = ap.probe_kimi(timeout=5)
    assert status == ap.NOT_INSTALLED


def test_probe_kimi_no_providers_is_auth_dead(monkeypatch):
    # guilt: the unauthenticated kimi-code shape has no 401 marker, only prose
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/Users/x/.kimi-code/bin/kimi", True))
    monkeypatch.setattr(
        ap.subprocess, "run", lambda cmd, **kwargs: _FakeProc(1, "No providers configured.\n", "")
    )
    status, ev, latency = ap.probe_kimi(timeout=5)
    assert status == ap.AUTH_DEAD


def test_probe_kimi_billing_cycle_403_is_quota_dead_not_auth_dead(monkeypatch):
    # guilt: the real-world Allegro billing-cycle cap (PENDING-ARMS 2026-07-27,
    # "Kimi seat quota-exhausted") has no 401/no-providers marker — it must fall
    # through the kimi-specific AUTH_DEAD guard clause and land on QUOTA_DEAD via
    # classify_generic's "usage limit" match, so the cascade can skip-not-retry it
    # (a quota-dead seat needs wait/upgrade, not re-login).
    # `resolve_bin` returns (path, via_path) — every sibling test in this file
    # fakes the PAIR. Returning the bare string made `binp, via_path = ...`
    # unpack the path's characters instead, so the test died inside probe_kimi
    # with "too many values to unpack" before reaching a single assertion.
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/Users/x/.kimi-code/bin/kimi", True))
    monkeypatch.setattr(
        ap.subprocess,
        "run",
        lambda cmd, **kwargs: _FakeProc(
            1,
            "",
            "403 You've reached your usage limit for this billing cycle. "
            "To continue now, purchase extra usage or upgrade your plan: "
            "https://www.kimi.com/code/#pricing",
        ),
    )
    status, ev, latency = ap.probe_kimi(timeout=5)
    assert status == ap.QUOTA_DEAD
    assert status != ap.AUTH_DEAD


def test_probe_kimi_pong_with_provider_prose_stays_live(monkeypatch):
    # innocence: a LIVE answer that happens to mention providers/login in prose
    # must never be reclassified as a credential death
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/Users/x/.kimi-code/bin/kimi", True))
    monkeypatch.setattr(
        ap.subprocess,
        "run",
        lambda cmd, **kwargs: _FakeProc(0, "PONG (managed provider kimi-code, logged in)\n", ""),
    )
    status, ev, latency = ap.probe_kimi(timeout=5)
    assert status == ap.LIVE


def test_probe_kimi_uses_devnull_stdin(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured.update(kwargs)
        return _FakeProc(0, "PONG\n", "")

    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/Users/x/.kimi-code/bin/kimi", True))
    monkeypatch.setattr(ap.subprocess, "run", fake_run)
    ap.probe_kimi(timeout=5)
    assert captured.get("stdin") == ap.subprocess.DEVNULL


def test_probe_codex_uses_devnull_stdin(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured.update(kwargs)
        return _FakeProc(0, "PONG\n", "")

    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/opt/homebrew/bin/codex", True))
    monkeypatch.setattr(ap.subprocess, "run", fake_run)
    ap.probe_codex(timeout=5)
    assert captured.get("stdin") == ap.subprocess.DEVNULL


def test_probe_codex_pong_is_live(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/opt/homebrew/bin/codex", True))
    monkeypatch.setattr(ap.subprocess, "run", lambda cmd, **kwargs: _FakeProc(0, "PONG\n", ""))
    status, ev, latency = ap.probe_codex(timeout=5)
    assert status == ap.LIVE


def test_probe_codex_401_is_auth_dead(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/opt/homebrew/bin/codex", True))
    monkeypatch.setattr(
        ap.subprocess, "run", lambda cmd, **kwargs: _FakeProc(1, "", "401 token_revoked")
    )
    status, ev, latency = ap.probe_codex(timeout=5)
    assert status == ap.AUTH_DEAD



def test_probe_codex_spark_pong_is_live(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/opt/homebrew/bin/codex", True))
    monkeypatch.setattr(ap.subprocess, "run", lambda cmd, **kwargs: _FakeProc(0, "PONG\n", ""))
    status, ev, latency = ap.probe_codex_spark(timeout=5)
    assert status == ap.LIVE


def test_probe_codex_spark_401_is_auth_dead(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/opt/homebrew/bin/codex", True))
    monkeypatch.setattr(
        ap.subprocess, "run", lambda cmd, **kwargs: _FakeProc(1, "", "401 token_revoked")
    )
    status, ev, latency = ap.probe_codex_spark(timeout=5)
    assert status == ap.AUTH_DEAD


def test_probe_jules_sources_is_live(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/usr/bin/python3", True))
    monkeypatch.setattr(ap.subprocess, "run", lambda cmd, **kwargs: _FakeProc(0, "source1\nsource2\n", ""))
    status, ev, latency = ap.probe_jules(timeout=5)
    assert status == ap.LIVE


def test_probe_jules_no_sources_is_unknown_err(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/usr/bin/python3", True))
    monkeypatch.setattr(ap.subprocess, "run", lambda cmd, **kwargs: _FakeProc(0, "", ""))
    status, ev, latency = ap.probe_jules(timeout=5)
    assert status == ap.UNKNOWN_ERR


def test_probe_jules_no_api_key_is_cred_unavailable(monkeypatch):
    # guilt: real exemplar (2026-08-21, ~/.organism/arsenal/last.json on Mini) —
    # jules_dispatch.py's get_api_key() prints "no API key" + a
    # security add-generic-password recipe to stderr and exits 2 when the
    # jules-api-key Keychain item was never provisioned (verified on Mini:
    # `security find-generic-password -s jules-api-key` -> item not found).
    # This shape carries no 401/oauth marker and previously fell through
    # classify_generic() to a bare UNKNOWN_ERR — indistinguishable from the
    # genuinely ambiguous empty-output case above.
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/usr/bin/python3", True))
    monkeypatch.setattr(
        ap.subprocess,
        "run",
        lambda cmd, **kwargs: _FakeProc(
            2,
            "",
            "jules_dispatch: no API key — add it with:\n"
            "  security add-generic-password -a balizero -s jules-api-key -w '<KEY>'",
        ),
    )
    status, ev, latency = ap.probe_jules(timeout=5)
    assert status == ap.CRED_UNAVAILABLE


def test_probe_jules_live_output_mentioning_api_key_stays_live(monkeypatch):
    # innocence: a LIVE answer (real source lines) that happens to mention
    # "API key" in a source name must never be reclassified as credential-dead.
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/usr/bin/python3", True))
    monkeypatch.setattr(
        ap.subprocess,
        "run",
        lambda cmd, **kwargs: _FakeProc(0, "sources/github/org/api-key-rotator\n", ""),
    )
    status, ev, latency = ap.probe_jules(timeout=5)
    assert status == ap.LIVE


def test_retired_standalone_deepseek_door_does_not_return_as_own_seat():
    """Pin the owner ruling without banning TP1's subscription models.

    Zero's 2026-07-19 ruling retired the old standalone per-token DeepSeek door
    (pre-auth revoked; never top up). Zero's 2026-08-22 ruling explicitly allows
    DeepSeek through the Alibaba plan, so only the bare legacy `deepseek` seat is
    forbidden; the namespaced TP1 seats are valid and must remain probeable.
    """
    assert "deepseek" not in ap.ALL_SEATS
    assert "deepseek" not in ap.PROBE_FUNCS
    assert "deepseek" not in ap.DEFAULT_TIMEOUTS
    assert not hasattr(ap, "probe_deepseek")
    for machine, seats in ap.REQUIRED_SEATS.items():
        assert "deepseek" not in seats, f"deepseek still required on {machine}"
    assert "tp1-deepseek-v4-pro" in ap.ALL_SEATS
    assert "tp1-deepseek-v4-flash-0731" in ap.ALL_SEATS


def test_tp1_verified_text_roster_is_wired_but_not_required():
    expected = {
        "tp1-deepseek-v4-pro": "deepseek-v4-pro",
        "tp1-deepseek-v4-flash-0731": "deepseek-v4-flash-0731",
        "tp1-glm-5.2": "glm-5.2",
        "tp1-qwen3.8-max": "qwen3.8-max",
        "tp1-qwen3.7-max": "qwen3.7-max",
        "tp1-qwen3.7-plus": "qwen3.7-plus",
        "tp1-qwen3.6-flash": "qwen3.6-flash",
    }
    assert ap.TP1_SEAT_MODELS == expected
    for seat in expected:
        assert seat in ap.ALL_SEATS
        assert seat in ap.PROBE_FUNCS
        assert ap.DEFAULT_TIMEOUTS[seat] == 15
        assert all(seat not in seats for seats in ap.REQUIRED_SEATS.values())


def test_probe_ollama_qwen_listed_is_live(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/usr/local/bin/ollama", True))
    monkeypatch.setattr(
        ap.subprocess, "run", lambda cmd, **kwargs: _FakeProc(0, "qwen3.5:9b\tabc\n", "")
    )
    status, ev, latency = ap.probe_ollama(timeout=5, live_gen=False)
    assert status == ap.LIVE


def test_probe_ollama_qwen_absent_is_not_live(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/usr/local/bin/ollama", True))
    monkeypatch.setattr(ap.subprocess, "run", lambda cmd, **kwargs: _FakeProc(0, "llama3:8b\n", ""))
    status, ev, latency = ap.probe_ollama(timeout=5, live_gen=False)
    assert status != ap.LIVE


def test_probe_ollama_missing_binary_not_installed(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: (None, False))
    status, ev, latency = ap.probe_ollama(timeout=5, live_gen=False)
    assert status == ap.NOT_INSTALLED


def test_probe_ollama_live_gen_passes_prompt_as_argv_not_stdin(monkeypatch):
    # 2026-08-07: a bare `ollama run <model>` with no prompt arg drops into an
    # interactive REPL reading stdin — under the now-unconditional stdin=DEVNULL
    # contract that would read immediate EOF and generate nothing, silently
    # turning every --live-gen probe into a false-dead reading. The prompt must
    # travel as an argv token, never depend on stdin.
    calls = []

    def fake_run_probe_cmd(cmd, timeout, **kwargs):
        calls.append(cmd)
        if "list" in cmd:
            return ap.ProbeResult(0, "qwen3.5:9b\tabc\n", "")
        return ap.ProbeResult(0, "PONG\n", "")

    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/usr/local/bin/ollama", True))
    monkeypatch.setattr(ap, "run_probe_cmd", fake_run_probe_cmd)
    status, ev, latency = ap.probe_ollama(timeout=5, live_gen=True)
    assert status == ap.LIVE
    run_call = calls[1]
    assert run_call[:3] == ["/usr/local/bin/ollama", "run", "qwen3.5:9b"]
    assert ap.PONG_PROMPT in run_call


def test_probe_ollama_live_gen_timeout_with_no_output_stays_timeout(monkeypatch):
    # innocence: a live-gen call that times out with truly nothing produced must
    # stay TIMEOUT, not be misread as live.
    def fake_run_probe_cmd(cmd, timeout, **kwargs):
        if "list" in cmd:
            return ap.ProbeResult(0, "qwen3.5:9b\tabc\n", "")
        return ap.ProbeResult(-1, "", "", timed_out=True)

    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/usr/local/bin/ollama", True))
    monkeypatch.setattr(ap, "run_probe_cmd", fake_run_probe_cmd)
    status, ev, latency = ap.probe_ollama(timeout=5, live_gen=True)
    assert status == ap.TIMEOUT


def test_probe_ollama_live_gen_recovers_partial_output_on_timeout(monkeypatch):
    # the same judge-the-reply-not-the-timeout fix applied to the live-gen path.
    def fake_run_probe_cmd(cmd, timeout, **kwargs):
        if "list" in cmd:
            return ap.ProbeResult(0, "qwen3.5:9b\tabc\n", "")
        return ap.ProbeResult(-1, "PONG partial\n", "", timed_out=True)

    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/usr/local/bin/ollama", True))
    monkeypatch.setattr(ap, "run_probe_cmd", fake_run_probe_cmd)
    status, ev, latency = ap.probe_ollama(timeout=5, live_gen=True)
    assert status == ap.LIVE


def test_probe_nlm_valid_json_list_is_live(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/usr/local/bin/nlm", True))
    monkeypatch.setattr(
        ap.subprocess, "run", lambda cmd, **kwargs: _FakeProc(0, '[{"id": "nb1"}]', "")
    )
    status, ev, latency = ap.probe_nlm(timeout=5)
    assert status == ap.LIVE


def test_probe_nlm_non_json_output_not_live(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/usr/local/bin/nlm", True))
    monkeypatch.setattr(ap.subprocess, "run", lambda cmd, **kwargs: _FakeProc(0, "not json at all", ""))
    status, ev, latency = ap.probe_nlm(timeout=5)
    assert status != ap.LIVE


def test_probe_nlm_missing_binary_not_installed(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: (None, False))
    status, ev, latency = ap.probe_nlm(timeout=5)
    assert status == ap.NOT_INSTALLED


def test_probe_nlm_login_to_reauthenticate_classifies_auth_dead(monkeypatch):
    # guilt: real exemplar (tail-truncated, the substring is genuine) captured
    # in ~/.organism/arsenal/last.json on Mini (2026-08-05T04:53:56Z) — nlm's
    # expired-credential shape carries no 401/oauth-token marker, only
    # "Run nlm login to re-authenticate", and previously fell through
    # classify_generic() to a bare UNKNOWN_ERR despite docs/runbooks/
    # arsenal-probe.md documenting "nlm AUTH_DEAD -> `nlm login` on Pro" as
    # the expected cure. Mirrored locally (kimi/claude pattern) so the shared
    # _AUTH_DEAD_PAT keeps its existing guilt+innocence corpus untouched.
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/usr/local/bin/nlm", True))
    monkeypatch.setattr(
        ap.subprocess,
        "run",
        lambda cmd, **kwargs: _FakeProc(
            1,
            "",
            "Your credentials have expired. Please run `nlm login` in a terminal to "
            "re-authenticate.  MCP users: the server should auto-detect the new credentials; "
            "if not, call the refresh_auth tool.  → Run nlm login to re-authenticate",
        ),
    )
    status, ev, latency = ap.probe_nlm(timeout=5)
    assert status == ap.AUTH_DEAD


def test_probe_nlm_valid_json_mentioning_login_stays_live(monkeypatch):
    # innocence: a LIVE answer (valid JSON notebook list) that happens to
    # mention "login" inside a notebook title must never be reclassified as a
    # credential death.
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/usr/local/bin/nlm", True))
    monkeypatch.setattr(
        ap.subprocess,
        "run",
        lambda cmd, **kwargs: _FakeProc(0, '[{"id": "nb1", "title": "nlm login flow research"}]', ""),
    )
    status, ev, latency = ap.probe_nlm(timeout=5)
    assert status == ap.LIVE


# ---------------------------------------------------------------------------
# Transitions vs prev report
# ---------------------------------------------------------------------------


def test_compute_transitions_detects_status_change():
    prev = {"seats": [{"seat": "codex", "status": "LIVE"}]}
    current = [{"seat": "codex", "status": "AUTH_DEAD"}]
    transitions = ap.compute_transitions(prev, current)
    assert transitions == [{"seat": "codex", "from": "LIVE", "to": "AUTH_DEAD"}]


def test_compute_transitions_no_change_is_empty():
    prev = {"seats": [{"seat": "codex", "status": "LIVE"}]}
    current = [{"seat": "codex", "status": "LIVE"}]
    assert ap.compute_transitions(prev, current) == []


def test_compute_transitions_no_prev_report_is_empty():
    current = [{"seat": "codex", "status": "AUTH_DEAD"}]
    assert ap.compute_transitions(None, current) == []


def test_compute_transitions_new_seat_not_in_prev_is_not_a_transition():
    prev = {"seats": [{"seat": "codex", "status": "LIVE"}]}
    current = [{"seat": "codex", "status": "LIVE"}, {"seat": "glm", "status": "AUTH_DEAD"}]
    transitions = ap.compute_transitions(prev, current)
    assert transitions == []


# ---------------------------------------------------------------------------
# Atomic write + prev.json retention
# ---------------------------------------------------------------------------


def test_write_report_creates_last_json(tmp_path, monkeypatch):
    monkeypatch.setattr(ap, "REPORT_DIR", tmp_path)
    report = {"schema": 1, "machine": "m5", "seats": []}
    ap.write_report(report)
    last = tmp_path / "last.json"
    assert last.exists()
    assert json.loads(last.read_text()) == report


def test_write_report_retains_prev_json(tmp_path, monkeypatch):
    monkeypatch.setattr(ap, "REPORT_DIR", tmp_path)
    first = {"schema": 1, "machine": "m5", "seats": [{"seat": "codex", "status": "LIVE"}]}
    ap.write_report(first)
    second = {"schema": 1, "machine": "m5", "seats": [{"seat": "codex", "status": "AUTH_DEAD"}]}
    ap.write_report(second)
    prev = tmp_path / "prev.json"
    last = tmp_path / "last.json"
    assert json.loads(prev.read_text()) == first
    assert json.loads(last.read_text()) == second


def test_write_report_first_run_has_no_prev_json(tmp_path, monkeypatch):
    monkeypatch.setattr(ap, "REPORT_DIR", tmp_path)
    ap.write_report({"schema": 1, "machine": "m5", "seats": []})
    assert not (tmp_path / "prev.json").exists()


def test_write_report_no_tmp_file_left_behind(tmp_path, monkeypatch):
    monkeypatch.setattr(ap, "REPORT_DIR", tmp_path)
    ap.write_report({"schema": 1, "machine": "m5", "seats": []})
    leftover_tmp = list(tmp_path.glob("*.tmp"))
    assert leftover_tmp == []


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------


def test_write_heartbeat_ok_status_when_not_degraded(tmp_path, monkeypatch):
    monkeypatch.setattr(ap, "HEARTBEAT_DIR", tmp_path)
    ap.write_heartbeat("m5", degraded=False, summary_line="all fine")
    hb = json.loads((tmp_path / "m5.arsenal_probe.json").read_text())
    assert hb["organ"] == "m5.arsenal_probe"
    assert hb["status"] == "ok"
    assert hb["degraded"] is False
    assert hb["note"] == "all fine"


def test_write_heartbeat_status_stays_ok_when_arsenal_degraded(tmp_path, monkeypatch):
    """The sidecar's status is the PROBE's own liveness, never the observed
    arsenal's health (TAC 2026-07-03, same fix as pro.fly_restart_loop_detector
    PR #1924) — a dead AI seat must not flip organs_heartbeat's UNHEALTHY_STATUSES
    gate. The finding still travels via the `degraded` field + note, and via the
    dedicated arsenal_seats proprioception probe."""
    monkeypatch.setattr(ap, "HEARTBEAT_DIR", tmp_path)
    ap.write_heartbeat("mini", degraded=True, summary_line="codex auth dead")
    hb = json.loads((tmp_path / "mini.arsenal_probe.json").read_text())
    assert hb["status"] == "ok"
    assert hb["degraded"] is True
    assert hb["note"] == "codex auth dead"


# ---------------------------------------------------------------------------
# --read-last: ok-set filtering, NEVER_RAN
# ---------------------------------------------------------------------------


def test_read_last_never_ran_when_no_report(tmp_path, monkeypatch):
    monkeypatch.setattr(ap, "REPORT_DIR", tmp_path)
    result = ap.read_last()
    assert result == {"findings": [{"seat": "(all)", "status": "NEVER_RAN"}]}


def test_read_last_filters_to_non_ok_seats(tmp_path, monkeypatch):
    monkeypatch.setattr(ap, "REPORT_DIR", tmp_path)
    fixture = {
        "schema": 1,
        "machine": "m5",
        "ts": "x",
        "context": {},
        "seats": [
            {"seat": "claude", "status": "LIVE", "healthy": True, "latency_ms": 1, "evidence": "", "required": True},
            {"seat": "glm", "status": "QUOTA_DEAD", "healthy": False, "latency_ms": 1, "evidence": "", "required": True},
            {"seat": "codex", "status": "AUTH_DEAD", "healthy": False, "latency_ms": 1, "evidence": "", "required": True},
        ],
        "transitions": [],
        "summary": {"live": 1, "dead_strict": 1, "context_limited": 0, "transient": 1},
    }
    ap._atomic_write_json(tmp_path / "last.json", fixture)
    result = ap.read_last()
    assert result == {
        "findings": [
            {"seat": "glm", "status": "QUOTA_DEAD"},
            {"seat": "codex", "status": "AUTH_DEAD"},
        ]
    }


def test_read_last_all_live_gives_empty_findings(tmp_path, monkeypatch):
    monkeypatch.setattr(ap, "REPORT_DIR", tmp_path)
    fixture = {
        "schema": 1,
        "machine": "m5",
        "ts": "x",
        "context": {},
        "seats": [
            {"seat": "claude", "status": "LIVE", "healthy": True, "latency_ms": 1, "evidence": "", "required": True},
        ],
        "transitions": [],
        "summary": {"live": 1, "dead_strict": 0, "context_limited": 0, "transient": 0},
    }
    ap._atomic_write_json(tmp_path / "last.json", fixture)
    assert ap.read_last() == {"findings": []}


def test_read_last_seats_filter_applies(tmp_path, monkeypatch):
    monkeypatch.setattr(ap, "REPORT_DIR", tmp_path)
    fixture = {
        "schema": 1,
        "machine": "m5",
        "ts": "x",
        "context": {},
        "seats": [
            {"seat": "glm", "status": "AUTH_DEAD", "healthy": False, "latency_ms": 1, "evidence": "", "required": True},
            {"seat": "codex", "status": "AUTH_DEAD", "healthy": False, "latency_ms": 1, "evidence": "", "required": True},
        ],
        "transitions": [],
        "summary": {"live": 0, "dead_strict": 2, "context_limited": 0, "transient": 0},
    }
    ap._atomic_write_json(tmp_path / "last.json", fixture)
    result = ap.read_last(seats_filter=["glm"])
    assert result == {"findings": [{"seat": "glm", "status": "AUTH_DEAD"}]}


def test_read_last_corrupted_report_treated_as_never_ran(tmp_path, monkeypatch):
    monkeypatch.setattr(ap, "REPORT_DIR", tmp_path)
    (tmp_path / "last.json").write_text("{not valid json")
    result = ap.read_last()
    assert result == {"findings": [{"seat": "(all)", "status": "NEVER_RAN"}]}


# ---------------------------------------------------------------------------
# Strict exit semantics — required AUTH_DEAD -> 1, CRED_UNAVAILABLE -> 0
# ---------------------------------------------------------------------------


def _report_with_seat(status: str, required: bool = True) -> dict:
    return {
        "schema": 1,
        "machine": "m5",
        "ts": "x",
        "seats": [
            {"seat": "codex", "status": status, "healthy": status == ap.LIVE, "latency_ms": 1, "evidence": "", "required": required}
        ],
        "transitions": [],
        "summary": {"live": 0, "dead_strict": 0, "context_limited": 0, "transient": 0},
    }


def test_exit_code_strict_required_auth_dead_is_1():
    report = _report_with_seat(ap.AUTH_DEAD, required=True)
    assert ap.exit_code_for(report, strict=True, probed_count=1) == 1


def test_exit_code_strict_required_cred_unavailable_is_0():
    report = _report_with_seat(ap.CRED_UNAVAILABLE, required=True)
    assert ap.exit_code_for(report, strict=True, probed_count=1) == 0


def test_exit_code_strict_required_not_installed_is_0():
    report = _report_with_seat(ap.NOT_INSTALLED, required=True)
    assert ap.exit_code_for(report, strict=True, probed_count=1) == 0


def test_exit_code_strict_non_required_auth_dead_is_0():
    report = _report_with_seat(ap.AUTH_DEAD, required=False)
    assert ap.exit_code_for(report, strict=True, probed_count=1) == 0


def test_exit_code_strict_transient_statuses_never_fail():
    for status in [ap.QUOTA_DEAD, ap.SHED, ap.TIMEOUT]:
        report = _report_with_seat(status, required=True)
        assert ap.exit_code_for(report, strict=True, probed_count=1) == 0


def test_exit_code_non_strict_always_0_even_with_dead_required_seat():
    report = _report_with_seat(ap.AUTH_DEAD, required=True)
    assert ap.exit_code_for(report, strict=False, probed_count=1) == 0


def test_exit_code_blind_scan_zero_probed_is_2_regardless_of_strict():
    report = {"seats": [], "summary": {}}
    assert ap.exit_code_for(report, strict=False, probed_count=0) == 2
    assert ap.exit_code_for(report, strict=True, probed_count=0) == 2


# ---------------------------------------------------------------------------
# run() orchestration — all probes monkeypatched, no thread/network flakiness
# ---------------------------------------------------------------------------


def test_run_empty_seats_produces_empty_seats_list(tmp_path, monkeypatch):
    monkeypatch.setattr(ap, "REPORT_DIR", tmp_path)
    report = ap.run(seats=[], timeout_mult=1.0, live_gen=False, machine="m5")
    assert report["seats"] == []
    assert report["summary"]["live"] == 0


def test_run_marks_required_seats_for_machine(tmp_path, monkeypatch):
    monkeypatch.setattr(ap, "REPORT_DIR", tmp_path)
    monkeypatch.setitem(ap.PROBE_FUNCS, "claude", lambda timeout: (ap.LIVE, "PONG", 10))
    monkeypatch.setitem(ap.PROBE_FUNCS, "codex", lambda timeout: (ap.LIVE, "PONG", 20))
    report = ap.run(seats=["claude", "codex"], timeout_mult=1.0, live_gen=False, machine="m5")
    by_seat = {s["seat"]: s for s in report["seats"]}
    assert by_seat["claude"]["required"] is True  # m5 requires claude
    assert by_seat["codex"]["required"] is True  # m5 requires codex


def test_run_computes_summary_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(ap, "REPORT_DIR", tmp_path)
    monkeypatch.setitem(ap.PROBE_FUNCS, "claude", lambda timeout: (ap.LIVE, "PONG", 10))
    monkeypatch.setitem(ap.PROBE_FUNCS, "codex", lambda timeout: (ap.AUTH_DEAD, "401", 10))
    monkeypatch.setitem(ap.PROBE_FUNCS, "glm", lambda timeout: (ap.CRED_UNAVAILABLE, "locked", 5))
    monkeypatch.setitem(ap.PROBE_FUNCS, "agy", lambda timeout: (ap.QUOTA_DEAD, "429", 5))
    report = ap.run(seats=["claude", "codex", "glm", "agy"], timeout_mult=1.0, live_gen=False, machine="m5")
    summ = report["summary"]
    assert summ["live"] == 1
    assert summ["dead_strict"] == 1
    assert summ["context_limited"] == 1
    assert summ["transient"] == 1


def test_run_a_single_seat_exception_does_not_crash_others(tmp_path, monkeypatch):
    monkeypatch.setattr(ap, "REPORT_DIR", tmp_path)

    def boom(timeout):
        raise RuntimeError("simulated probe crash")

    monkeypatch.setitem(ap.PROBE_FUNCS, "claude", lambda timeout: (ap.LIVE, "PONG", 10))
    monkeypatch.setitem(ap.PROBE_FUNCS, "codex", boom)
    report = ap.run(seats=["claude", "codex"], timeout_mult=1.0, live_gen=False, machine="m5")
    by_seat = {s["seat"]: s for s in report["seats"]}
    assert by_seat["claude"]["status"] == ap.LIVE
    assert by_seat["codex"]["status"] == ap.UNKNOWN_ERR


def test_run_preserves_requested_seat_order(tmp_path, monkeypatch):
    monkeypatch.setattr(ap, "REPORT_DIR", tmp_path)
    for seat in ap.ALL_SEATS:
        monkeypatch.setitem(ap.PROBE_FUNCS, seat, (lambda s: (lambda timeout: (ap.LIVE, "ok", 1)))(seat))
    requested = ["ollama", "claude", "nlm", "glm"]
    report = ap.run(seats=requested, timeout_mult=1.0, live_gen=False, machine="m5")
    assert [s["seat"] for s in report["seats"]] == requested


# ---------------------------------------------------------------------------
# machine_label() / is_ssh_context()
# ---------------------------------------------------------------------------


def test_machine_label_air_m5(monkeypatch):
    monkeypatch.setattr(ap.socket, "gethostname", lambda: "Air-M5.local")
    assert ap.machine_label() == "m5"


def test_machine_label_mini(monkeypatch):
    monkeypatch.setattr(ap.socket, "gethostname", lambda: "Mini-Pro2.local")
    assert ap.machine_label() == "mini"


def test_machine_label_pro(monkeypatch):
    monkeypatch.setattr(ap.socket, "gethostname", lambda: "Nuzantara")
    assert ap.machine_label() == "pro"


def test_machine_label_unknown_host_falls_back_to_lowercase(monkeypatch):
    monkeypatch.setattr(ap.socket, "gethostname", lambda: "SomeOtherBox")
    assert ap.machine_label() == "someotherbox"


def test_is_ssh_context_true_when_ssh_connection_set(monkeypatch):
    monkeypatch.setenv("SSH_CONNECTION", "1.2.3.4 1 5.6.7.8 22")
    monkeypatch.delenv("SSH_TTY", raising=False)
    assert ap.is_ssh_context() is True


def test_is_ssh_context_false_when_neither_set(monkeypatch):
    monkeypatch.delenv("SSH_CONNECTION", raising=False)
    monkeypatch.delenv("SSH_TTY", raising=False)
    assert ap.is_ssh_context() is False


# ---------------------------------------------------------------------------
# CLI: --json / --quiet / --table smoke, and unknown seat rejection
# ---------------------------------------------------------------------------


def test_main_rejects_unknown_seat(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ap, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(ap, "HEARTBEAT_DIR", tmp_path)
    code = ap.main(["--seats", "claude,not-a-real-seat"])
    assert code == 2
    err = capsys.readouterr().err
    assert "not-a-real-seat" in err


def test_main_json_output_is_valid_json(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ap, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(ap, "HEARTBEAT_DIR", tmp_path)
    monkeypatch.setitem(ap.PROBE_FUNCS, "claude", lambda timeout: (ap.LIVE, "PONG", 5))
    code = ap.main(["--seats", "claude", "--json"])
    assert code == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["machine"] == ap.machine_label()
    assert payload["seats"][0]["seat"] == "claude"


def test_main_quiet_output_is_one_line(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ap, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(ap, "HEARTBEAT_DIR", tmp_path)
    monkeypatch.setitem(ap.PROBE_FUNCS, "claude", lambda timeout: (ap.LIVE, "PONG", 5))
    code = ap.main(["--seats", "claude", "--quiet"])
    assert code == 0
    out = capsys.readouterr().out.strip()
    assert len(out.splitlines()) == 1
    assert "arsenal_probe" in out


def test_main_read_last_never_ran_exit_0(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ap, "REPORT_DIR", tmp_path)
    code = ap.main(["--read-last", "--json"])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"findings": [{"seat": "(all)", "status": "NEVER_RAN"}]}


def test_main_writes_heartbeat_file(tmp_path, monkeypatch):
    monkeypatch.setattr(ap, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(ap, "HEARTBEAT_DIR", tmp_path)
    monkeypatch.setitem(ap.PROBE_FUNCS, "claude", lambda timeout: (ap.LIVE, "PONG", 5))
    ap.main(["--seats", "claude", "--quiet"])
    hb_files = list(tmp_path.glob("*.arsenal_probe.json"))
    assert len(hb_files) == 1


def test_main_report_never_contains_secret_after_full_run(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ap, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(ap, "HEARTBEAT_DIR", tmp_path)
    secret = "sk-verysecretvaluethatmustnotleak"

    def fake_glm(timeout):
        # simulate a probe that saw the secret internally but must not report it
        return ap.AUTH_DEAD, ap.evidence_tail(f"401 saw {secret}", [secret]), 5

    monkeypatch.setitem(ap.PROBE_FUNCS, "glm", fake_glm)
    code = ap.main(["--seats", "glm", "--json"])
    out = capsys.readouterr().out
    assert secret not in out
    report_on_disk = (tmp_path / "last.json").read_text()
    assert secret not in report_on_disk


# ---------------------------------------------------------------------------
# --selftest
# ---------------------------------------------------------------------------


def test_selftest_passes_and_exits_0(capsys):
    code = ap.selftest()
    out = capsys.readouterr().out
    assert code == 0
    assert "SELFTEST OK" in out


def test_selftest_classifier_helper_returns_no_failures():
    assert ap._selftest_classifier() == []


def test_selftest_scrub_helper_returns_no_failures():
    assert ap._selftest_scrub() == []


def test_selftest_blind_scan_helper_returns_no_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(ap, "REPORT_DIR", tmp_path)
    assert ap._selftest_blind_scan() == []


def test_main_selftest_flag_routes_to_selftest(capsys):
    code = ap.main(["--selftest"])
    assert code == 0
    assert "SELFTEST OK" in capsys.readouterr().out


# ---- request-id digit-run innocence (scar #3, added at Fable review) ----------

def test_request_id_digit_run_never_false_matches_numeric_codes():
    # z.ai request ids are long digit runs; one minted at 12:11 embeds "1211",
    # one at 14:01 embeds "401", one at 04:29 embeds "429". None may classify.
    ev = "API Error: 529 overloaded [20260706121155c8877b89100e44a6]"
    assert ap.classify_generic(ev, False, "glm", False) == ap.SHED

    ev2 = "temporary failure [2026070614015500aa] retry later"
    assert ap.classify_generic(ev2, False, "codex", False) == ap.UNKNOWN_ERR

    ev3 = "gateway note [2026070604295500bb] nothing else"
    assert ap.classify_generic(ev3, False, "codex", False) == ap.UNKNOWN_ERR


def test_bracketed_numeric_codes_still_match():
    assert ap.classify_generic("HTTP 400 [1211] Unknown Model", False, "glm", False) == ap.MODEL_ERR
    assert ap.classify_generic("HTTP 401 Authentication Failed", False, "glm", False) == ap.AUTH_DEAD
    assert ap.classify_generic("HTTP 429 too many requests", False, "codex", False) == ap.QUOTA_DEAD



# ---------------------------------------------------------------------------
# 2026-08-07 incident: arsenal_probe could hang forever and print zero bytes.
# `timeout 60 python3 scripts/arsenal_probe.py --table` produced 0 bytes on
# stdout+stderr on Pro (live seats claude/agy/kimi/codex/ollama/nlm all answered
# fine interactively). Root cause, found empirically (not guessed): agy's own
# process exits in ~1s but a detached grandchild keeps stdout's pipe fd open,
# so subprocess.run's communicate() never sees EOF — the probe ALWAYS ate its
# FULL per-seat timeout (verified at 12s/15s/45s cutoffs, PONG present in
# partial stdout every single time) even though the seat is genuinely LIVE.
# Since all seats probe concurrently and nothing prints until every future
# resolves, agy's old 120s timeout alone explained the reported hang under any
# outer wrapper shorter than that. Fixed by: (1) judging partial stdout for a
# live signal BEFORE accepting TIMEOUT, generically, in every subprocess-backed
# probe; (2) collapsing all per-seat timeouts from 30-180s down to ~15s; (3) a
# fail-visible header printed+flushed to stderr before any probe fires; (4)
# stdin=DEVNULL unconditional on every subprocess; (5) resolve_bin() enriched
# with common install-root fallbacks (claude/nlm/ollama had a wrong or absent
# fallback, causing false NOT_INSTALLED under a PATH-poor hook/launchd context).
# ---------------------------------------------------------------------------


def test_run_probe_cmd_stdin_devnull_prevents_stdin_read_hang(tmp_path):
    # innocence-of-the-fix, REAL subprocess (not mocked): a fake seat that reads
    # stdin would block forever on an inherited open pipe — exactly the shape a
    # hook/launchd/agent-harness caller can hand this process. With stdin=DEVNULL
    # wired unconditionally, the read() gets immediate EOF and the process exits
    # fast, well inside a generous timeout — it must never even approach TIMEOUT.
    script = tmp_path / "fake_seat_reads_stdin.py"
    script.write_text(textwrap.dedent("""
        import sys
        data = sys.stdin.read()  # hangs forever on an open, unclosed pipe
        print("SEAT_OK")
    """))
    t0 = time.monotonic()
    res = ap.run_probe_cmd([sys.executable, str(script)], timeout=10)
    elapsed = time.monotonic() - t0
    assert res.timed_out is False
    assert "SEAT_OK" in res.stdout
    assert elapsed < 5  # nowhere near the 10s timeout — proves no hang occurred


def test_run_probe_cmd_stdin_devnull_is_the_default(monkeypatch):
    # guilt-of-the-old-bug: stdin_devnull used to default to False, and only
    # kimi/codex opted in explicitly — claude/agy/ollama/nlm inherited whatever
    # stdin this process had. The contract is now unconditional (mandate:
    # "stdin=subprocess.DEVNULL su OGNI subprocess").
    captured = {}

    def fake_run(cmd, **kwargs):
        captured.update(kwargs)
        return _FakeProc(0, "ok", "")

    monkeypatch.setattr(ap.subprocess, "run", fake_run)
    ap.run_probe_cmd(["irrelevant"], timeout=5)  # no stdin_devnull kwarg passed
    assert captured.get("stdin") == ap.subprocess.DEVNULL


def test_run_probe_cmd_recovers_partial_output_when_process_hangs_after_replying(tmp_path):
    # THE bug, reproduced with a REAL subprocess: prints PONG almost instantly,
    # then never exits — the agy pipe-leak shape. run_probe_cmd must still return
    # within its own timeout budget (never inherit the child's indefinite hang)
    # and must hand back the partial stdout so a caller can judge the reply.
    script = tmp_path / "fake_seat_hangs_after_reply.py"
    script.write_text(textwrap.dedent("""
        import time
        print("PONG", flush=True)
        time.sleep(30)
    """))
    t0 = time.monotonic()
    res = ap.run_probe_cmd([sys.executable, str(script)], timeout=2)
    elapsed = time.monotonic() - t0
    assert res.timed_out is True
    assert "PONG" in res.stdout  # the reply IS there — a caller must judge it
    assert elapsed < 10  # bounded by the probe's own timeout, never the child's 30s sleep


def test_probe_agy_classifies_live_when_pong_arrives_before_hard_timeout(monkeypatch):
    # end-to-end regression for the 2026-08-07 incident: probe_agy must not
    # report TIMEOUT for a seat that already answered PONG, even though
    # run_probe_cmd itself hit its timeout (the live agy pipe-leak shape).
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/opt/homebrew/bin/agy", True))
    monkeypatch.setattr(
        ap, "run_probe_cmd",
        lambda cmd, timeout, **kw: ap.ProbeResult(-1, "PONG\n", "", timed_out=True),
    )
    status, ev, latency = ap.probe_agy(timeout=2)
    assert status == ap.LIVE


def test_probe_agy_genuine_hang_with_no_reply_still_classifies_timeout(monkeypatch):
    # innocence: a seat that timed out AND never said anything must still be
    # TIMEOUT, not silently promoted to LIVE — the recovery only applies when a
    # real live signal is present in the partial output.
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/opt/homebrew/bin/agy", True))
    monkeypatch.setattr(
        ap, "run_probe_cmd",
        lambda cmd, timeout, **kw: ap.ProbeResult(-1, "", "", timed_out=True),
    )
    status, ev, latency = ap.probe_agy(timeout=2)
    assert status == ap.TIMEOUT


def test_probe_claude_classifies_live_when_pong_arrives_before_hard_timeout(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/opt/homebrew/bin/claude", True))
    monkeypatch.setattr(
        ap, "run_probe_cmd",
        lambda cmd, timeout, env=None: ap.ProbeResult(-1, "PONG\n", "", timed_out=True),
    )
    status, ev, latency = ap.probe_claude(timeout=2)
    assert status == ap.LIVE


def test_probe_codex_classifies_live_when_pong_arrives_before_hard_timeout(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/opt/homebrew/bin/codex", True))
    monkeypatch.setattr(
        ap, "run_probe_cmd",
        lambda cmd, timeout, **kw: ap.ProbeResult(-1, "PONG\n", "", timed_out=True),
    )
    status, ev, latency = ap.probe_codex(timeout=2)
    assert status == ap.LIVE


def test_probe_kimi_classifies_live_when_pong_arrives_before_hard_timeout(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/Users/x/.kimi-code/bin/kimi", True))
    monkeypatch.setattr(
        ap, "run_probe_cmd",
        lambda cmd, timeout, **kw: ap.ProbeResult(-1, "PONG\n", "", timed_out=True),
    )
    status, ev, latency = ap.probe_kimi(timeout=2)
    assert status == ap.LIVE


def test_probe_nlm_genuine_timeout_with_truncated_json_stays_timeout(monkeypatch):
    # innocence: truncated/incomplete JSON on timeout must not be misread as a
    # live signal (json.loads legitimately fails) — TIMEOUT is still correct.
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/usr/local/bin/nlm", True))
    monkeypatch.setattr(
        ap, "run_probe_cmd",
        lambda cmd, timeout, **kw: ap.ProbeResult(-1, '[{"id": "nb1"', "", timed_out=True),
    )
    status, ev, latency = ap.probe_nlm(timeout=2)
    assert status == ap.TIMEOUT


# ---------------------------------------------------------------------------
# resolve_bin() — enriched fallback + found_via_path signal (2026-08-07)
# ---------------------------------------------------------------------------


def test_resolve_bin_prefers_path_when_available(monkeypatch):
    monkeypatch.setattr(ap.shutil, "which", lambda name: f"/usr/bin/{name}" if name == "foo" else None)
    path, via_path = ap.resolve_bin("foo")
    assert path == "/usr/bin/foo"
    assert via_path is True


def test_resolve_bin_falls_back_to_common_dirs_when_path_thin(monkeypatch, tmp_path):
    # guilt: reproduces the real 2026-08-07 bug shape — a hook/launchd context's
    # $PATH lacks ~/.local/bin even though the binary is genuinely installed
    # there. found_via_path=False signals "PATH-poor context", not "absent".
    monkeypatch.setattr(ap.shutil, "which", lambda name: None)
    fake_bin_dir = tmp_path / ".local" / "bin"
    fake_bin_dir.mkdir(parents=True)
    fake_bin = fake_bin_dir / "claude"
    fake_bin.write_text("#!/bin/sh\necho fake\n")
    real_expanduser = ap.os.path.expanduser
    monkeypatch.setattr(
        ap.os.path, "expanduser",
        lambda p: str(tmp_path) + p[1:] if p.startswith("~") else real_expanduser(p),
    )
    path, via_path = ap.resolve_bin("claude")
    assert path == str(fake_bin)
    assert via_path is False


def test_resolve_bin_genuinely_absent_returns_none_and_false(monkeypatch, tmp_path):
    # innocence: nothing anywhere (not $PATH, not extra_paths, not common dirs)
    # must still cleanly report absent, never crash or false-positive.
    monkeypatch.setattr(ap.shutil, "which", lambda name: None)
    real_expanduser = ap.os.path.expanduser
    monkeypatch.setattr(
        ap.os.path, "expanduser",
        lambda p: str(tmp_path) + p[1:] if p.startswith("~") else real_expanduser(p),
    )
    path, via_path = ap.resolve_bin("totally-not-a-real-binary-xyz")
    assert path is None
    assert via_path is False


def test_probe_claude_notes_not_on_path_when_resolved_via_fallback(monkeypatch):
    # the distinguishing signal the mandate asked for: NOT_ON_PATH (binary present,
    # this process's $PATH was thin) must be visibly different from a plain LIVE
    # resolved normally — surfaced in the evidence, not a new top-level status
    # (avoids growing the taxonomy for what is fundamentally a context footnote).
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/some/fallback/claude", False))
    monkeypatch.setattr(ap.subprocess, "run", lambda cmd, **kwargs: _FakeProc(0, "PONG\n", ""))
    status, ev, latency = ap.probe_claude(timeout=5)
    assert status == ap.LIVE
    assert "NOT_ON_PATH" in ev


def test_probe_claude_no_path_note_when_resolved_via_path(monkeypatch):
    # innocence: the normal case (found via $PATH) must carry no such note.
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/opt/homebrew/bin/claude", True))
    monkeypatch.setattr(ap.subprocess, "run", lambda cmd, **kwargs: _FakeProc(0, "PONG\n", ""))
    status, ev, latency = ap.probe_claude(timeout=5)
    assert status == ap.LIVE
    assert "NOT_ON_PATH" not in ev


# ---------------------------------------------------------------------------
# Fail-visible contract: header before probing, output never empty (2026-08-07)
# ---------------------------------------------------------------------------


def test_main_prints_header_to_stderr_before_any_probe_result(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ap, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(ap, "HEARTBEAT_DIR", tmp_path)
    monkeypatch.setitem(ap.PROBE_FUNCS, "claude", lambda timeout: (ap.LIVE, "PONG", 5))
    code = ap.main(["--seats", "claude", "--table"])
    assert code == 0
    err = capsys.readouterr().err
    assert "probing 1 seat(s)" in err
    assert "claude" in err


def test_main_output_never_empty_even_with_every_seat_dead(tmp_path, monkeypatch, capsys):
    # (c) from the mandate: even with ALL seats dead, output must never be
    # empty — the header alone (stderr, printed before any probe fires)
    # guarantees this regardless of what every individual probe returns.
    monkeypatch.setattr(ap, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(ap, "HEARTBEAT_DIR", tmp_path)
    for seat in ap.ALL_SEATS:
        monkeypatch.setitem(ap.PROBE_FUNCS, seat, lambda timeout: (ap.UNKNOWN_ERR, "dead", 1))
    code = ap.main([])
    out, err = capsys.readouterr()
    assert (out + err).strip() != ""
    assert f"0 of {len(ap.ALL_SEATS)} seats OK" in out


def test_main_header_printed_even_if_every_probe_crashes(tmp_path, monkeypatch, capsys):
    # the header is printed BEFORE run() is even called — it must survive a
    # probe function that raises, not just one that returns a dead status.
    monkeypatch.setattr(ap, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(ap, "HEARTBEAT_DIR", tmp_path)

    def boom(timeout):
        raise RuntimeError("simulated probe crash")

    for seat in ap.ALL_SEATS:
        monkeypatch.setitem(ap.PROBE_FUNCS, seat, boom)
    code = ap.main([])
    err = capsys.readouterr().err
    assert f"probing {len(ap.ALL_SEATS)} seat(s)" in err


def test_render_table_includes_n_of_m_seats_ok_line():
    report = {
        "machine": "pro",
        "ts": "x",
        "seats": [
            {"seat": "claude", "status": ap.LIVE, "healthy": True, "latency_ms": 1, "evidence": "PONG", "required": True},
            {"seat": "codex", "status": ap.AUTH_DEAD, "healthy": False, "latency_ms": 1, "evidence": "401", "required": True},
        ],
        "transitions": [],
        "summary": {"live": 1, "dead_strict": 1, "context_limited": 0, "transient": 0},
    }
    table = ap.render_table(report)
    assert "1 of 2 seats OK" in table


def test_summary_line_includes_n_of_m_seats_ok():
    report = {
        "machine": "pro",
        "seats": [{"seat": "claude"}, {"seat": "codex"}, {"seat": "glm"}],
        "summary": {"live": 1, "dead_strict": 1, "context_limited": 1, "transient": 0},
    }
    line = ap.summary_line(report)
    assert "1 of 3 seats OK" in line


def test_probe_claude_strips_glm_session_env(monkeypatch):
    captured_env = {}

    def fake_run(cmd, timeout, env=None, stdin_devnull=True):
        captured_env.update(env or {})
        return ap.ProbeResult(0, "PONG", "")

    monkeypatch.setattr(ap, "run_probe_cmd", fake_run)
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: ("/fake/claude", True))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-paid-key-must-die")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "glm-token-must-die")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.z.ai/api/anthropic")
    status, _, _ = ap.probe_claude(timeout=5)
    assert status == ap.LIVE
    assert "ANTHROPIC_API_KEY" not in captured_env
    assert "ANTHROPIC_AUTH_TOKEN" not in captured_env
    assert "ANTHROPIC_BASE_URL" not in captured_env
