"""Guilt+innocence tests for scripts/jules_dispatch.py (offline — no network, no Keychain).

The module's own --selftest covers the same ground for humans; this file makes the
proofs CI-visible via the immune-enforcement unit-test loop (W81: an untested guard
arm is theater). Network calls are exercised against a local stub of urllib, never
the real API.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import urllib.error
from pathlib import Path

import pytest

SPEC_PATH = Path(__file__).resolve().parent.parent / "jules_dispatch.py"
spec = importlib.util.spec_from_file_location("jules_dispatch", SPEC_PATH)
jd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jd)


# ------------------------------------------------------------------ scrub
def test_scrub_removes_exact_key():
    fake = "AIzaFAKEFAKEFAKEFAKEFAKEFAKEfakefake"  # pragma: allowlist secret — fixture
    assert "<REDACTED-KEY>" in jd.scrub(f"error body {fake} tail", fake)
    assert fake not in jd.scrub(f"error body {fake} tail", fake)


def test_scrub_removes_aiza_shaped_strays_without_known_key():
    stray = "AIzaSTRAYSTRAYSTRAYSTRAYSTRAYstray1"  # pragma: allowlist secret — fixture
    assert stray not in jd.scrub(f"has {stray} inline", "")


def test_scrub_innocence_plain_text_untouched():
    assert jd.scrub("plain error, nothing secret", "some-key") == "plain error, nothing secret"


# ------------------------------------------------------------------ session_path
def test_session_path_adds_prefix():
    assert jd.session_path("12345") == "sessions/12345"


def test_session_path_idempotent():
    assert jd.session_path("sessions/12345") == "sessions/12345"


# ------------------------------------------------------------------ credentials
def test_env_key_override_wins(monkeypatch):
    monkeypatch.setenv("JULES_API_KEY", "env-key-for-test")
    assert jd.get_api_key() == "env-key-for-test"


def test_missing_key_exits_2(monkeypatch):
    monkeypatch.delenv("JULES_API_KEY", raising=False)

    def fake_run(*a, **k):
        class P:
            returncode = 1
            stdout = ""
        return P()

    monkeypatch.setattr(jd.subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as exc:
        jd.get_api_key()
    assert exc.value.code == 2


# ------------------------------------------------------------------ api_call
class _FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_api_call_success_parses_json(monkeypatch):
    def fake_urlopen(req, timeout=0):
        assert req.get_header("X-goog-api-key") == "k"
        return _FakeResp(json.dumps({"ok": True}).encode())

    monkeypatch.setattr(jd.urllib.request, "urlopen", fake_urlopen)
    assert jd.api_call("GET", "sources", "k") == {"ok": True}


def test_api_call_4xx_no_retry_exits_1_scrubbed(monkeypatch, capsys):
    calls = {"n": 0}

    def fake_urlopen(req, timeout=0):
        calls["n"] += 1
        raise urllib.error.HTTPError(
            "u", 403, "forbidden", None, io.BytesIO(b"denied for key k-secret")
        )

    monkeypatch.setattr(jd.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(SystemExit) as exc:
        jd.api_call("GET", "sources", "k-secret")
    assert exc.value.code == 1
    assert calls["n"] == 1  # innocence: a 4xx must NOT be retried
    assert "k-secret" not in capsys.readouterr().err


def test_api_call_5xx_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_urlopen(req, timeout=0):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.HTTPError("u", 503, "unavailable", None, io.BytesIO(b""))
        return _FakeResp(json.dumps({"after": "retry"}).encode())

    monkeypatch.setattr(jd.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(jd.time, "sleep", lambda *_: None)
    assert jd.api_call("GET", "sources", "k") == {"after": "retry"}
    assert calls["n"] == 2
