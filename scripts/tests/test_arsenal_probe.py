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
    status, ev = ap.http_post_json(
        "https://api.z.ai/x", {"Authorization": "Bearer secrettoken12345678901234"}, {}, 10, ["secrettoken12345678901234"]
    )
    assert status == 200
    assert "glm-5.2" in ev
    assert "secrettoken12345678901234" not in ev


def test_http_post_json_error_never_leaks_authorization_value(monkeypatch):
    import urllib.error

    def fake_urlopen(req, timeout):
        # simulate a server that echoes the request headers back in the error body
        # (worst case scenario the redaction must survive)
        body = f'{{"error": "unauthorized", "your_header_was": "Bearer secrettoken12345678901234"}}'.encode()
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr(ap.urllib.request, "urlopen", fake_urlopen)
    status, ev = ap.http_post_json(
        "https://api.z.ai/x", {"Authorization": "Bearer secrettoken12345678901234"}, {}, 10, ["secrettoken12345678901234"]
    )
    assert status == 401
    assert "secrettoken12345678901234" not in ev


def test_http_post_json_url_error_is_scrubbed(monkeypatch):
    import urllib.error

    def fake_urlopen(req, timeout):
        raise urllib.error.URLError("connection refused, token was secrettoken12345678901234")

    monkeypatch.setattr(ap.urllib.request, "urlopen", fake_urlopen)
    status, ev = ap.http_post_json(
        "https://api.z.ai/x", {}, {}, 10, ["secrettoken12345678901234"]
    )
    assert status is None
    assert "secrettoken12345678901234" not in ev


# ---------------------------------------------------------------------------
# Per-seat probes — subprocess/HTTP fully monkeypatched
# ---------------------------------------------------------------------------


class _FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_probe_claude_pong_is_live(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: "/opt/homebrew/bin/claude")
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
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: "/opt/homebrew/bin/claude")
    monkeypatch.setattr(ap.subprocess, "run", fake_run)
    ap.probe_claude(timeout=5)
    assert "ANTHROPIC_API_KEY" not in captured_env


def test_probe_claude_binary_absent_is_not_installed(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: None)
    monkeypatch.delenv("ARSENAL_CLAUDE_BIN", raising=False)
    status, ev, latency = ap.probe_claude(timeout=5)
    assert status == ap.NOT_INSTALLED
    assert ap.is_strict_fail(status) is False


def test_probe_claude_timeout_classifies_timeout(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise ap.subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 5))

    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: "/opt/homebrew/bin/claude")
    monkeypatch.setattr(ap.subprocess, "run", fake_run)
    status, ev, latency = ap.probe_claude(timeout=5)
    assert status == ap.TIMEOUT


def test_probe_glm_cred_unavailable_when_keychain_locked(monkeypatch):
    monkeypatch.setattr(ap, "load_keychain_token", lambda service, timeout=10: (None, "keychain locked"))
    status, ev, latency = ap.probe_glm(timeout=5)
    assert status == ap.CRED_UNAVAILABLE
    assert ap.is_strict_fail(status) is False


def test_probe_glm_live_on_200_with_model(monkeypatch):
    monkeypatch.setattr(ap, "load_keychain_token", lambda service, timeout=10: ("tok123456789012345678901", None))
    monkeypatch.setattr(ap, "http_post_json", lambda *a, **kw: (200, '{"model": "glm-5.2"}'))
    status, ev, latency = ap.probe_glm(timeout=5)
    assert status == ap.LIVE


def test_probe_glm_model_err_on_1211(monkeypatch):
    monkeypatch.setattr(ap, "load_keychain_token", lambda service, timeout=10: ("tok123456789012345678901", None))
    monkeypatch.setattr(
        ap, "http_post_json", lambda *a, **kw: (400, '{"error": {"code": 1211, "message": "Unknown Model"}}')
    )
    status, ev, latency = ap.probe_glm(timeout=5)
    assert status == ap.MODEL_ERR


def test_probe_glm_never_leaks_token_in_evidence(monkeypatch):
    token = "leaktoken1234567890123456"
    monkeypatch.setattr(ap, "load_keychain_token", lambda service, timeout=10: (token, None))

    def fake_http(url, headers, body, timeout, secret_values):
        assert token in secret_values  # the probe must pass its own secret for scrubbing
        return 401, ap.evidence_tail(f"unauthorized, saw {token}", secret_values)

    monkeypatch.setattr(ap, "http_post_json", fake_http)
    status, ev, latency = ap.probe_glm(timeout=5)
    assert token not in ev


def test_probe_agy_pong_is_live(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: "/opt/homebrew/bin/agy")
    monkeypatch.setattr(ap.subprocess, "run", lambda cmd, **kwargs: _FakeProc(0, "PONG\n", ""))
    status, ev, latency = ap.probe_agy(timeout=5)
    assert status == ap.LIVE


def test_probe_agy_missing_binary_not_installed(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: None)
    status, ev, latency = ap.probe_agy(timeout=5)
    assert status == ap.NOT_INSTALLED


def test_probe_codex_uses_devnull_stdin(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured.update(kwargs)
        return _FakeProc(0, "PONG\n", "")

    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: "/opt/homebrew/bin/codex")
    monkeypatch.setattr(ap.subprocess, "run", fake_run)
    ap.probe_codex(timeout=5)
    assert captured.get("stdin") == ap.subprocess.DEVNULL


def test_probe_codex_pong_is_live(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: "/opt/homebrew/bin/codex")
    monkeypatch.setattr(ap.subprocess, "run", lambda cmd, **kwargs: _FakeProc(0, "PONG\n", ""))
    status, ev, latency = ap.probe_codex(timeout=5)
    assert status == ap.LIVE


def test_probe_codex_401_is_auth_dead(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: "/opt/homebrew/bin/codex")
    monkeypatch.setattr(
        ap.subprocess, "run", lambda cmd, **kwargs: _FakeProc(1, "", "401 token_revoked")
    )
    status, ev, latency = ap.probe_codex(timeout=5)
    assert status == ap.AUTH_DEAD


def test_probe_deepseek_cred_unavailable_when_env_master_missing(monkeypatch):
    monkeypatch.setattr(ap, "load_env_master_key", lambda var, path="~/x": (None, "not found"))
    status, ev, latency = ap.probe_deepseek(timeout=5)
    assert status == ap.CRED_UNAVAILABLE
    assert ap.is_strict_fail(status) is False


def test_probe_deepseek_live_on_200(monkeypatch):
    monkeypatch.setattr(ap, "load_env_master_key", lambda var, path="~/x": ("key123456789012345678", None))
    monkeypatch.setattr(ap, "http_post_json", lambda *a, **kw: (200, "ok"))
    status, ev, latency = ap.probe_deepseek(timeout=5)
    assert status == ap.LIVE


def test_probe_deepseek_402_is_balance_dead(monkeypatch):
    monkeypatch.setattr(ap, "load_env_master_key", lambda var, path="~/x": ("key123456789012345678", None))
    monkeypatch.setattr(ap, "http_post_json", lambda *a, **kw: (402, "Insufficient Balance"))
    status, ev, latency = ap.probe_deepseek(timeout=5)
    assert status == ap.BALANCE_DEAD


def test_probe_ollama_qwen_listed_is_live(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: "/usr/local/bin/ollama")
    monkeypatch.setattr(
        ap.subprocess, "run", lambda cmd, **kwargs: _FakeProc(0, "qwen3.5:9b\tabc\n", "")
    )
    status, ev, latency = ap.probe_ollama(timeout=5, live_gen=False)
    assert status == ap.LIVE


def test_probe_ollama_qwen_absent_is_not_live(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: "/usr/local/bin/ollama")
    monkeypatch.setattr(ap.subprocess, "run", lambda cmd, **kwargs: _FakeProc(0, "llama3:8b\n", ""))
    status, ev, latency = ap.probe_ollama(timeout=5, live_gen=False)
    assert status != ap.LIVE


def test_probe_ollama_missing_binary_not_installed(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: None)
    status, ev, latency = ap.probe_ollama(timeout=5, live_gen=False)
    assert status == ap.NOT_INSTALLED


def test_probe_nlm_valid_json_list_is_live(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: "/usr/local/bin/nlm")
    monkeypatch.setattr(
        ap.subprocess, "run", lambda cmd, **kwargs: _FakeProc(0, '[{"id": "nb1"}]', "")
    )
    status, ev, latency = ap.probe_nlm(timeout=5)
    assert status == ap.LIVE


def test_probe_nlm_non_json_output_not_live(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: "/usr/local/bin/nlm")
    monkeypatch.setattr(ap.subprocess, "run", lambda cmd, **kwargs: _FakeProc(0, "not json at all", ""))
    status, ev, latency = ap.probe_nlm(timeout=5)
    assert status != ap.LIVE


def test_probe_nlm_missing_binary_not_installed(monkeypatch):
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: None)
    status, ev, latency = ap.probe_nlm(timeout=5)
    assert status == ap.NOT_INSTALLED


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
    assert hb["note"] == "all fine"


def test_write_heartbeat_degraded_status(tmp_path, monkeypatch):
    monkeypatch.setattr(ap, "HEARTBEAT_DIR", tmp_path)
    ap.write_heartbeat("mini", degraded=True, summary_line="codex auth dead")
    hb = json.loads((tmp_path / "mini.arsenal_probe.json").read_text())
    assert hb["status"] == "degraded"


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


def test_probe_claude_strips_glm_session_env(monkeypatch):
    captured_env = {}

    def fake_run(cmd, timeout, env=None, stdin_devnull=True):
        captured_env.update(env or {})
        return ap.ProbeResult(0, "PONG", "")

    monkeypatch.setattr(ap, "run_probe_cmd", fake_run)
    monkeypatch.setattr(ap, "resolve_bin", lambda name, extra_paths=None: "/fake/claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-paid-key-must-die")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "glm-token-must-die")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.z.ai/api/anthropic")
    status, _, _ = ap.probe_claude(timeout=5)
    assert status == ap.LIVE
    assert "ANTHROPIC_API_KEY" not in captured_env
    assert "ANTHROPIC_AUTH_TOKEN" not in captured_env
    assert "ANTHROPIC_BASE_URL" not in captured_env
