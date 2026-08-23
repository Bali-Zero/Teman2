"""Guilt+innocence for claude_seat_quota.py — no Keychain, no network.

The three behaviours worth defending are the ones that were measured the hard way on
2026-08-23 (see the module docstring): a rate-limited answer must not be reported as a
dead seat, an empty run must never exit 0, and a token must never reach stdout.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import urllib.error
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "claude_seat_quota.py"


def load_module():
    spec = importlib.util.spec_from_file_location("claude_seat_quota", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def mod():
    return load_module()


USAGE_OK = {
    "five_hour": {"utilization": 5.0, "resets_at": "2026-08-23T09:20:00+00:00"},
    "seven_day": {"utilization": 94.0, "resets_at": "2026-08-25T00:00:00+00:00"},
    "seven_day_opus": None,
    "seven_day_sonnet": None,
}


def test_rate_limited_answer_is_retried_not_reported_as_dead(mod, monkeypatch):
    """A 429 is transient. Reporting it as an unreadable seat would call a healthy
    account dead and flip the exit code — the exact false alarm this guards."""
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.HTTPError(
                req.full_url, 429, "Too Many Requests", {},
                io.BytesIO(b'{"error":{"message":"Rate limited."}}'),
            )

        class Resp:
            status = 200

            def read(self):
                return json.dumps(USAGE_OK).encode()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return Resp()

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)
    code, payload = mod.api_get("/api/oauth/usage", "tok")
    assert code == 200, "a 429 must be retried, not surfaced"
    assert payload["seven_day"]["utilization"] == 94.0
    assert calls["n"] == 2, "expected exactly one retry after the 429"


def test_non_retryable_status_returns_immediately(mod, monkeypatch):
    """403-no-scope is the answer a cron token gets. It is terminal: retrying it would
    only slow the run down and hide the real cause."""
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        raise urllib.error.HTTPError(
            req.full_url, 403, "Forbidden", {},
            io.BytesIO(b'{"error":{"message":"OAuth token does not meet scope '
                       b'requirement user:profile"}}'),
        )

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)
    code, payload = mod.api_get("/api/oauth/usage", "tok")
    assert code == 403
    assert calls["n"] == 1, "a 403 must not be retried"
    assert "user:profile" in payload["error"]["message"]


def test_zero_profiles_exits_2_never_0(mod, monkeypatch):
    """An empty run is an infrastructure failure masquerading as calm. The predecessor
    watcher exited 0 for months while reporting nothing — that is the disease."""
    monkeypatch.setattr(mod, "keychain_services", lambda: [])
    monkeypatch.setattr(mod, "warm_profiles", lambda deep: None)
    monkeypatch.setattr(sys, "argv", ["claude_seat_quota.py"])
    monkeypatch.setattr(sys, "platform", "darwin")
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        rc = mod.main()
    assert rc == 2, "no profiles discovered must never be a green run"


def test_all_readable_exits_0_and_prints_no_token(mod, monkeypatch, capsys):
    monkeypatch.setattr(mod, "keychain_services", lambda: ["Claude Code-credentials"])
    monkeypatch.setattr(mod, "access_token", lambda svc: "sk-ant-oat0-SECRET-DO-NOT-PRINT")
    monkeypatch.setattr(mod, "warm_profiles", lambda deep: None)

    def fake_api_get(path, token, attempts=3):
        if path == mod.PROFILE_PATH:
            return 200, {"account": {"email_address": "someone@example.com"}}
        return 200, USAGE_OK

    monkeypatch.setattr(mod, "api_get", fake_api_get)
    monkeypatch.setattr(sys, "argv", ["claude_seat_quota.py"])
    monkeypatch.setattr(sys, "platform", "darwin")
    rc = mod.main()
    out = capsys.readouterr()
    assert rc == 0
    assert "someone@example.com" in out.out
    assert "94%" in out.out
    assert "SECRET-DO-NOT-PRINT" not in out.out + out.err, "a token must never be printed"
    assert "sk-ant-oat" not in out.out + out.err


def test_warn_at_flags_a_saturated_seat(mod, monkeypatch):
    monkeypatch.setattr(mod, "keychain_services", lambda: ["Claude Code-credentials"])
    monkeypatch.setattr(mod, "access_token", lambda svc: "tok")
    monkeypatch.setattr(mod, "warm_profiles", lambda deep: None)
    monkeypatch.setattr(mod, "api_get", lambda path, token, attempts=3: (
        (200, {"account": {"email_address": "hot@example.com"}})
        if path == mod.PROFILE_PATH else (200, USAGE_OK)
    ))
    monkeypatch.setattr(sys, "platform", "darwin")

    monkeypatch.setattr(sys, "argv", ["claude_seat_quota.py", "--warn-at", "85"])
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        assert mod.main() == 1, "94% weekly must trip a --warn-at 85 threshold"

    monkeypatch.setattr(sys, "argv", ["claude_seat_quota.py", "--warn-at", "99"])
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        assert mod.main() == 0, "94% weekly must NOT trip a --warn-at 99 threshold"


def test_same_account_on_two_profiles_counts_once(mod, monkeypatch):
    """Two config dirs can hold the same seat (measured: .claude-acct4 and .claude-kaiser
    were both kaiser1987@). The table must count SEATS, not Keychain entries."""
    monkeypatch.setattr(mod, "keychain_services",
                        lambda: ["Claude Code-credentials", "Claude Code-credentials-abc123"])
    monkeypatch.setattr(mod, "access_token", lambda svc: "tok")
    monkeypatch.setattr(mod, "api_get", lambda path, token, attempts=3: (
        (200, {"account": {"email_address": "dup@example.com"}})
        if path == mod.PROFILE_PATH else (200, USAGE_OK)
    ))
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)
    rows = mod.collect(pace=0)
    assert len(rows) == 1, f"one account across two profiles must collapse to one row: {rows}"
    assert rows[0]["account"] == "dup@example.com"


def test_stale_entry_does_not_flip_the_exit_code(mod, monkeypatch):
    """An old login left in the Keychain has no account name and no live credential.
    Counting it as a failed seat would make the tool cry wolf on every run — which is
    how the predecessor watcher became unreadable noise."""
    monkeypatch.setattr(mod, "keychain_services",
                        lambda: ["Claude Code-credentials", "Claude Code-credentials-dead"])
    monkeypatch.setattr(mod, "access_token",
                        lambda svc: None if svc.endswith("dead") else "tok")
    monkeypatch.setattr(mod, "warm_profiles", lambda deep: None)
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)
    monkeypatch.setattr(mod, "api_get", lambda path, token, attempts=3: (
        (200, {"account": {"email_address": "live@example.com"}})
        if path == mod.PROFILE_PATH else (200, USAGE_OK)
    ))
    monkeypatch.setattr(sys, "argv", ["claude_seat_quota.py"])
    monkeypatch.setattr(sys, "platform", "darwin")
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        assert mod.main() == 0, "a stale leftover must not be reported as a seat failure"


def test_named_seat_that_cannot_be_read_does_flip_the_exit_code(mod, monkeypatch):
    """Guilt side of the pair above: a seat we CAN name but cannot read is a real
    failure and must be loud."""
    monkeypatch.setattr(mod, "keychain_services",
                        lambda: ["Claude Code-credentials", "Claude Code-credentials-x"])
    monkeypatch.setattr(mod, "access_token", lambda svc: "tok")
    monkeypatch.setattr(mod, "warm_profiles", lambda deep: None)
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)

    def fake(path, token, attempts=3):
        if path == mod.PROFILE_PATH:
            return 200, {"account": {"email_address": "named@example.com"}}
        return 401, {"error": {"message": "OAuth access token has expired."}}

    monkeypatch.setattr(mod, "api_get", fake)
    monkeypatch.setattr(sys, "argv", ["claude_seat_quota.py"])
    monkeypatch.setattr(sys, "platform", "darwin")
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        # every row unreadable -> rc 2 (nothing at all could be read)
        assert mod.main() == 2
