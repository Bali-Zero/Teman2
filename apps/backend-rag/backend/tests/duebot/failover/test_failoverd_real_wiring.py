"""Unit tests for the small pieces of ``failoverd.py``'s real-deployment
wiring that ARE plain, testable logic — env-var parsing and the
``tailscale status --json`` peer lookup — as opposed to
``build_real_deps``/``FailoverdRunner``/``main`` themselves, which glue
together real ``httpx``/``asyncpg``/subprocess calls this package's own
no-real-network policy (``network_guard.py``) deliberately does not
exercise end-to-end (see ``waba_override.py``'s own disclosure on the
same point).

``subprocess.run`` is monkeypatched here, never actually invoked — this
package forbids real egress, and shelling out to the real ``tailscale``
binary is exactly the kind of thing that would make this suite
non-deterministic across machines/CI anyway.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

import pytest

from backend.services.team_bot_ingress.failoverd import (
    FailoverdConfig,
    _find_tailscale_peer_online,
)

_REQUIRED_ENV = {
    "TEAM_BOT_WABA_ID": "waba-123",
    "TEAM_BOT_FAILOVER_CALLBACK_URI": "https://pro.example.ts.net/webhooks/team-wa",
    "TEAM_BOT_FAILOVER_CALLBACK_URI_SHA256": "a" * 64,
    "TEAM_BOT_WABA_VERIFY_TOKEN": "vt",
    "TEAM_BOT_WABA_ACCESS_TOKEN": "token",
    "TEAM_BOT_FAILOVER_DATABASE_URL": "postgresql://user@host/db",
    "TEAM_BOT_MINI_READYZ_URL": "https://mini.example.ts.net/readyz",
    "TEAM_BOT_BACKEND_HEALTH_URL": "https://nuzantara-rag.fly.dev/health",
}


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in _REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)


def test_from_env_parses_all_required_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    config = FailoverdConfig.from_env()
    assert config.waba_id == "waba-123"
    assert config.node_id == "pro"  # default
    assert config.auto_enabled is False  # default
    assert config.poll_seconds == 5.0  # default


def test_from_env_honors_explicit_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("TEAM_BOT_FAILOVER_NODE_ID", "pro-secondary")
    monkeypatch.setenv("TEAM_BOT_FAILOVER_AUTO_ENABLED", "true")
    monkeypatch.setenv("TEAM_BOT_FAILOVER_POLL_SECONDS", "2.5")
    config = FailoverdConfig.from_env()
    assert config.node_id == "pro-secondary"
    assert config.auto_enabled is True
    assert config.poll_seconds == 2.5


@pytest.mark.parametrize("missing_key", sorted(_REQUIRED_ENV))
def test_from_env_raises_on_each_missing_required_var(
    monkeypatch: pytest.MonkeyPatch, missing_key: str
) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.delenv(missing_key)
    with pytest.raises(RuntimeError, match=missing_key):
        FailoverdConfig.from_env()


def test_auto_enabled_only_true_for_literal_true_case_insensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_env(monkeypatch)
    for truthy_typo in ("1", "yes", "on", "True "):
        monkeypatch.setenv("TEAM_BOT_FAILOVER_AUTO_ENABLED", truthy_typo)
        assert FailoverdConfig.from_env().auto_enabled is False, truthy_typo
    monkeypatch.setenv("TEAM_BOT_FAILOVER_AUTO_ENABLED", "TRUE")
    assert FailoverdConfig.from_env().auto_enabled is True
    monkeypatch.setenv("TEAM_BOT_FAILOVER_AUTO_ENABLED", "true")
    assert FailoverdConfig.from_env().auto_enabled is True


# ---------------------------------------------------------------------
# _find_tailscale_peer_online
# ---------------------------------------------------------------------


@dataclass
class _FakeCompletedProcess:
    stdout: str


def _tailscale_status_json(*, peers: list[dict]) -> str:
    return json.dumps({"Peer": {f"peer-{i}": p for i, p in enumerate(peers)}})


def test_finds_online_peer_case_insensitive_hostname(monkeypatch: pytest.MonkeyPatch) -> None:
    stdout = _tailscale_status_json(
        peers=[{"HostName": "Mini-Pro2", "Online": True}, {"HostName": "Other", "Online": False}]
    )
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: _FakeCompletedProcess(stdout=stdout)
    )
    assert _find_tailscale_peer_online("mini-pro2") is True


def test_finds_offline_peer(monkeypatch: pytest.MonkeyPatch) -> None:
    stdout = _tailscale_status_json(peers=[{"HostName": "Mini-Pro2", "Online": False}])
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: _FakeCompletedProcess(stdout=stdout)
    )
    assert _find_tailscale_peer_online("Mini-Pro2") is False


def test_returns_none_when_peer_not_in_tailnet_map(monkeypatch: pytest.MonkeyPatch) -> None:
    stdout = _tailscale_status_json(peers=[{"HostName": "SomeoneElse", "Online": True}])
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: _FakeCompletedProcess(stdout=stdout)
    )
    assert _find_tailscale_peer_online("mini-pro2") is None


def test_returns_none_on_subprocess_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*a: object, **kw: object) -> None:
        raise subprocess.CalledProcessError(1, ["tailscale"])

    monkeypatch.setattr(subprocess, "run", _raise)
    assert _find_tailscale_peer_online("mini-pro2") is None


def test_returns_none_on_malformed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: _FakeCompletedProcess(stdout="not json{{{")
    )
    assert _find_tailscale_peer_online("mini-pro2") is None
