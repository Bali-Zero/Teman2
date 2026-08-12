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


# --------------------------------------------- source pre-flight (2026-08-12)
# Why this guard exists: the repo was transferred from the personal account
# `Balizero1987` to the `Bali-Zero` org. A GitHub App installation does NOT
# follow a transfer, so Jules silently lost sight of the repo while the arm
# stayed healthy. Six weeks of dispatches aimed at nothing, no alarm, because
# the only symptom was an opaque API error nobody was there to read.


def _new_args(**over):
    import argparse
    base = dict(prompt="p", source=jd.DEFAULT_SOURCE, branch="main", title="",
                require_plan_approval=False, skip_source_check=False, json=False)
    base.update(over)
    return argparse.Namespace(**base)


def _recording_api(sources, post_result=None, sources_raises=False):
    """Stub api_call; returns (fn, calls) so a test can assert what was sent."""
    calls = []

    def fake(method, path, key, body=None):
        calls.append((method, path))
        if path == "sources":
            if sources_raises:
                raise SystemExit(1)  # what the real api_call does on HTTP/network failure
            return {"sources": [{"name": s} for s in sources]}
        return post_result or {"name": "sessions/x", "state": "QUEUED"}

    return fake, calls


def test_guilt_refuses_source_jules_cannot_see(monkeypatch, capsys):
    fake, calls = _recording_api(["sources/github/Someone/Else"])
    monkeypatch.setattr(jd, "api_call", fake)
    rc = jd.cmd_new("k", _new_args(source="sources/github/Balizero1987/Teman2"))
    assert rc == 3, "a source Jules cannot see must be refused, not dispatched"
    assert ("POST", "sessions") not in calls, "refusal must happen BEFORE the POST"
    err = capsys.readouterr().err
    assert "REFUSING" in err and "sources/github/Someone/Else" in err, \
        "the refusal must name what Jules CAN see, or it is not actionable"


def test_innocence_visible_source_dispatches(monkeypatch):
    fake, calls = _recording_api([jd.DEFAULT_SOURCE])
    monkeypatch.setattr(jd, "api_call", fake)
    rc = jd.cmd_new("k", _new_args())
    assert rc == 0
    assert ("POST", "sessions") in calls, "a visible source must still dispatch"


def test_cannot_verify_warns_and_still_dispatches(monkeypatch, capsys):
    # W106b: "I could not check" is not "it is wrong". A network blip on an
    # advisory pre-flight must not become a refusal to work.
    fake, calls = _recording_api([], sources_raises=True)
    monkeypatch.setattr(jd, "api_call", fake)
    rc = jd.cmd_new("k", _new_args())
    assert rc == 0
    assert ("POST", "sessions") in calls
    assert "UNVERIFIED" in capsys.readouterr().err, \
        "an unverifiable pre-flight must say so out loud, never pass silently"


def test_skip_flag_does_not_even_look(monkeypatch):
    fake, calls = _recording_api([])
    monkeypatch.setattr(jd, "api_call", fake)
    rc = jd.cmd_new("k", _new_args(skip_source_check=True))
    assert rc == 0
    assert ("GET", "sources") not in calls, "--skip-source-check must skip the lookup"


def test_default_source_names_the_org_not_the_personal_account():
    # Pins the 2026-08-12 transfer. If this ever reads Balizero1987 again the
    # arm is aimed at a repo Jules cannot see.
    assert jd.DEFAULT_SOURCE == "sources/github/Bali-Zero/Teman2"
