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
from datetime import datetime, timedelta, timezone

import asyncpg
import httpx
import pytest

from backend.services.team_bot_ingress.failoverd import (
    ActionKind,
    FailoverdConfig,
    FailoverdDeps,
    MiniFailureTracker,
    _create_pool_with_retry,
    _find_tailscale_peer_online,
    _run_self_prechecks_not_fully_wired,
    evaluate_and_act_once,
)
from backend.services.team_bot_ingress.ingress_leader import (
    DEFAULT_RECORD_ID,
    IngressLeaderState,
    InMemoryIngressLeaderStore,
)
from backend.services.team_bot_ingress.waba_override import WABAOverrideClient

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


# ---------------------------------------------------------------------
# _run_self_prechecks_not_fully_wired — THE PRODUCTION function, not a
# test double. Every other test in this package injects a fake
# ``run_self_prechecks`` into ``FailoverdDeps`` (by design — most of
# this suite is testing the DECISION logic, not the wiring). These two
# close a real gap orchestrator review found: nothing anywhere exercised
# the actual function that ships, so nothing would go red the day
# someone flips ``ollama_reachable=False`` to a placeholder ``True`` in
# failoverd.py without having actually wired B4's Ollama check behind
# it. "Can be run TODAY, even armed, and can never promote" was true and
# guarded by nothing before these two tests.
# ---------------------------------------------------------------------


def _real_wiring_config() -> FailoverdConfig:
    return FailoverdConfig(
        node_id="pro",
        waba_id="waba-123",
        callback_uri="https://pro.example.ts.net/webhooks/team-wa",
        callback_uri_sha256="a" * 64,
        verify_token="vt",
        waba_access_token="token",
        database_url="postgresql://user@host/db",
        mini_readyz_url="https://mini.example.ts.net/readyz",
        mini_tailscale_hostname="Mini-Pro2",
        backend_health_url="https://nuzantara-rag.fly.dev/health",
        funnel_local_url="http://127.0.0.1:8765/livez",
        poll_seconds=5.0,
        auto_enabled=True,
    )


def _always_200(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200)


async def test_run_self_prechecks_not_fully_wired_pins_the_three_unwired_fields() -> None:
    """Best case for the TWO fields this lane actually owns
    (``backend_crm_healthy``/``funnel_reachable`` — both real HTTP calls,
    both answering 200 here): even then, ``ollama_reachable`` /
    ``replication_lag_ok`` / ``identity_snapshot_valid`` must stay
    False. Each is asserted BY NAME, not folded into ``all_pass`` alone
    — a future correctly-wired ``backend_crm_healthy`` must never let
    one of the other two hide behind it going forward.
    """
    config = _real_wiring_config()
    async with httpx.AsyncClient(transport=httpx.MockTransport(_always_200)) as http_client:
        report = await _run_self_prechecks_not_fully_wired(http_client=http_client, config=config)

    assert report.backend_crm_healthy is True  # this lane's own check — correctly wired
    assert report.funnel_reachable is True  # this lane's own check — correctly wired
    assert report.ollama_reachable is False, (
        "ollama_reachable is B4's Ollama-serving substance, not wired here. If this ever reads "
        "True without B4 having replaced _run_self_prechecks_not_fully_wired's body, "
        "TEAM_BOT_FAILOVER_AUTO_ENABLED would be arming a promotion path nobody actually built — "
        "fix the wiring in failoverd.py, then this assertion should fail on purpose, not be deleted quietly."
    )
    assert report.replication_lag_ok is False, (
        "replication_lag_ok is B3's sqlite-replication substance, not wired here — same arming "
        "condition as ollama_reachable: must go red on purpose when B3 wires it, never evaporate silently."
    )
    assert report.identity_snapshot_valid is False, (
        "identity_snapshot_valid is B3's F7 identity substance, not wired here — same arming "
        "condition: must go red on purpose when B3 wires it, never evaporate silently."
    )
    assert report.all_pass is False, (
        "all three fields above are False by design — team-bot-failoverd must refuse to promote "
        "today even when fully armed and even when this lane's own two checks are healthy"
    )


async def test_evaluate_and_act_once_with_real_prechecks_never_promotes_today() -> None:
    """Ties the pin above to the actual safety property, through the
    REAL decision function (``evaluate_and_act_once``), fully armed
    (``auto_enabled=True``), with the REAL precheck function injected —
    not a test double. Mini down for 3 ticks, Pro's own two checks both
    healthy: must still refuse. This is what makes "can be run TODAY
    even armed and can never promote" (the production function's own
    docstring claim) a tested property instead of a comment nobody
    checks.
    """
    config = _real_wiring_config()
    t0 = datetime(2026, 8, 25, 0, 0, 0, tzinfo=timezone.utc)
    store = InMemoryIngressLeaderStore(
        IngressLeaderState(
            record_id=DEFAULT_RECORD_ID,
            active_node_id="mini-pro2",
            leader_epoch=1,
            lease_expires_at=t0 + timedelta(seconds=120),
            callback_uri_sha256="a" * 64,
            changed_at=t0,
        )
    )

    async def mini_never_ready() -> bool:
        return False

    async def mini_unavailable_in_tailscale() -> bool:
        return True

    async with httpx.AsyncClient(transport=httpx.MockTransport(_always_200)) as http_client:
        async def run_real_prechecks():
            return await _run_self_prechecks_not_fully_wired(http_client=http_client, config=config)

        deps = FailoverdDeps(
            node_id="pro",
            store=store,
            waba_client=WABAOverrideClient(http_client, access_token="fake-token"),
            waba_id=config.waba_id,
            callback_uri=config.callback_uri,
            callback_uri_sha256=config.callback_uri_sha256,
            verify_token=config.verify_token,
            check_mini_ready=mini_never_ready,
            check_mini_tailscale_unavailable=mini_unavailable_in_tailscale,
            run_self_prechecks=run_real_prechecks,
            auto_enabled=True,
        )

        tracker = MiniFailureTracker()
        action = None
        for i in range(3):
            action = await evaluate_and_act_once(
                tracker=tracker, deps=deps, now=t0 + timedelta(seconds=i)
            )

    assert action is not None
    assert action.kind is ActionKind.REFUSED_SELF_UNHEALTHY, (
        "a fully-armed failoverd (auto_enabled=True) using the REAL, not-yet-wired precheck "
        "function must still refuse to promote — this is the property that makes it safe to run "
        "today. If this ever returns PROMOTED_AND_CONFIRMED without B3/B4 having replaced "
        "_run_self_prechecks_not_fully_wired's body first, someone armed a promotion path that "
        "was never actually built."
    )


# ---------------------------------------------------------------------
# _create_pool_with_retry — refutation finding #8. See
# F9-CALLBACK-WRITE-FENCE-SPEC.md.
# ---------------------------------------------------------------------


async def test_create_pool_with_retry_recovers_from_transient_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transient Postgres-unavailable-at-BOOT condition (2 failures,
    then success) must be absorbed inside the process, never raised.
    """
    attempts: list[str] = []
    sentinel_pool = object()

    async def _flaky_create_pool(dsn: str, **kwargs: object) -> object:
        attempts.append(dsn)
        if len(attempts) < 3:
            raise OSError("connection refused (simulated transient)")
        return sentinel_pool

    monkeypatch.setattr(asyncpg, "create_pool", _flaky_create_pool)
    pool = await _create_pool_with_retry(
        "postgresql://user@host/db", max_attempts=5, initial_delay=0.001, max_delay=0.001
    )
    assert pool is sentinel_pool
    assert len(attempts) == 3


async def test_create_pool_with_retry_gives_up_after_max_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A PERMANENTLY broken DSN must still fail -- bounded retry buys time
    for ordinary boot-ordering races, it does not paper over a genuine
    misconfiguration forever.
    """

    async def _always_fails(dsn: str, **kwargs: object) -> object:
        raise OSError("connection refused (simulated permanent)")

    monkeypatch.setattr(asyncpg, "create_pool", _always_fails)
    with pytest.raises(RuntimeError, match="could not create Postgres pool"):
        await _create_pool_with_retry(
            "postgresql://user@host/db", max_attempts=3, initial_delay=0.001, max_delay=0.001
        )
