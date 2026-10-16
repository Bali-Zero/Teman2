"""NLM recovery contract; no real login, browser, credential or network access."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import auth_sentinel as auth


def run_probe(monkeypatch, responses):
    calls = []
    pending = iter(responses)

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd == ["which", "nlm"]:
            return 0, "/synthetic/nlm"
        return next(pending)

    monkeypatch.setenv("NLM_PROFILE", "research")
    monkeypatch.setattr(auth, "_run", fake_run)
    return auth.probe_nlm(), calls


def test_valid_session_needs_no_refresh(monkeypatch):
    result, calls = run_probe(monkeypatch, [(0, "Authentication valid! Notebooks found: 401")])
    assert result.status == auth.OK
    assert len(calls) == 2
    assert calls[-1][-2:] == ["--profile", "research"]


def test_invalid_is_not_valid_and_refreshes_once(monkeypatch):
    result, calls = run_probe(monkeypatch, [
        (0, "Authentication invalid"), (0, "Refreshed"), (0, "Authentication valid!"),
    ])
    assert result.status == auth.REFRESHED
    assert calls[2] == ["nlm", "auth", "refresh", "--http-only", "--profile", "research"]
    assert len(calls) == 4


@pytest.mark.parametrize("initial", ["Authentication expired", "Not logged in", "HTTP 401 Unauthorized"])
def test_expired_login_escalates_without_clearing(monkeypatch, initial):
    result, calls = run_probe(monkeypatch, [(1, initial), (1, "sign-in required")])
    assert result.status == auth.ACTION
    assert "--clear" not in result.fix_cmd
    assert len(calls) == 3
    assert all("--clear" not in call for call in calls)


@pytest.mark.parametrize("response", [(124, "TIMEOUT"), (1, "network unavailable"), (0, "unrecognized")])
def test_inconclusive_network_never_triggers_refresh_or_raw_output(monkeypatch, response):
    result, calls = run_probe(monkeypatch, [response])
    assert result.status == auth.UNKNOWN
    assert len(calls) == 2
    assert result.detail == "auth check inconclusive (network, timeout or unknown response)"


def test_successful_refresh_requires_successful_revalidation(monkeypatch):
    result, calls = run_probe(monkeypatch, [
        (1, "Authentication expired"), (0, "Refreshed"), (124, "TIMEOUT"),
    ])
    assert result.status == auth.UNKNOWN
    assert len(calls) == 4
