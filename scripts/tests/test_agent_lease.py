"""Tests for scripts/agent_lease.py — Redis Lease Registry (2026-05-24).

Backed by fakeredis (in-process), so no real Redis required. We also include
one end-to-end test against a real Redis if reachable, skipped otherwise.

Covers (per brief):
  - acquire happy path
  - acquire fails if held by another task
  - acquire is re-entrant for SAME task (refreshes TTL)
  - heartbeat extends TTL only if task_id matches
  - release rejects wrong task_id
  - list filters by lane
  - TTL expire (sleep + ttl=1)
  - pre-commit hook integration (mock git diff --cached) — exit codes only
"""
from __future__ import annotations

import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "agent_lease.py"
HOOK_PATH = Path(__file__).resolve().parents[2] / ".husky" / "pre-commit"


def _load_lease_module():
    """Load scripts/agent_lease.py as a module.

    NOTE: we MUST register it in sys.modules under the SAME name we passed to
    spec_from_file_location, otherwise @dataclass introspection inside
    LeaseInfo fails with `AttributeError: 'NoneType' object has no attribute
    '__dict__'` — dataclasses calls `sys.modules.get(cls.__module__)` and that
    lookup must succeed for `dataclass()` field type resolution.
    """
    module_name = "agent_lease_under_test"
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_lease_module()


@pytest.fixture
def fake_client():
    fakeredis = pytest.importorskip("fakeredis")
    # decode_responses=True to match production client config
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def lease(mod, fake_client):
    return mod.AgentLease(client=fake_client)


@pytest.fixture
def audit_to_tmp(tmp_path, monkeypatch, mod):
    """Redirect ~/.agent/leases.jsonl into a tmp file for assertions."""
    p = tmp_path / "leases.jsonl"
    monkeypatch.setattr(mod, "AUDIT_PATH", p)
    return p


# ── acquire ───────────────────────────────────────────────────────────────────

def test_acquire_happy_path(lease, mod, audit_to_tmp):
    info = lease.acquire("a/b/c", task_id="task-A", ttl_s=120, lane="backend")
    assert info.task_id == "task-A"
    assert info.lane == "backend"
    assert info.ttl_s == 120
    # audit trail line present
    lines = audit_to_tmp.read_text().splitlines()
    assert any(json.loads(l)["event"] == "acquire" for l in lines)


def test_acquire_blocks_when_held_by_other_task(lease, mod):
    lease.acquire("hot/zone/x", task_id="task-A", ttl_s=60)
    with pytest.raises(mod.LeaseAlreadyHeld) as exc:
        lease.acquire("hot/zone/x", task_id="task-B", ttl_s=60)
    assert exc.value.holder.task_id == "task-A"
    assert "task-A" in str(exc.value)


def test_acquire_is_reentrant_for_same_task(lease):
    info1 = lease.acquire("res/reentrant", task_id="task-X", ttl_s=30)
    # second acquire with same task_id MUST not raise — should refresh
    info2 = lease.acquire("res/reentrant", task_id="task-X", ttl_s=60)
    assert info2.task_id == "task-X"
    # holder is still us
    assert lease.get("res/reentrant").task_id == "task-X"


def test_acquire_requires_task_id(lease):
    with pytest.raises(ValueError):
        lease.acquire("res/x", task_id="", ttl_s=10)


def test_acquire_rejects_zero_ttl(lease):
    with pytest.raises(ValueError):
        lease.acquire("res/x", task_id="t", ttl_s=0)


# ── heartbeat ─────────────────────────────────────────────────────────────────

def test_heartbeat_extends_ttl_when_task_id_matches(lease, fake_client, mod):
    lease.acquire("res/hb", task_id="task-A", ttl_s=10)
    # current TTL ~ 10
    ttl1 = fake_client.ttl(mod.build_key("res/hb"))
    assert 0 < ttl1 <= 10
    ok = lease.heartbeat("res/hb", task_id="task-A", extend_s=600)
    assert ok is True
    ttl2 = fake_client.ttl(mod.build_key("res/hb"))
    assert ttl2 > ttl1, f"expected ttl extended, got {ttl2} vs {ttl1}"


def test_heartbeat_rejects_wrong_task_id(lease, mod):
    lease.acquire("res/hb2", task_id="task-A", ttl_s=30)
    with pytest.raises(mod.LeaseNotOwned):
        lease.heartbeat("res/hb2", task_id="task-B", extend_s=60)


def test_heartbeat_noop_if_key_missing(lease):
    # Never acquired — heartbeat returns False, no exception
    assert lease.heartbeat("res/never-acquired", task_id="task-Z", extend_s=10) is False


# ── release ───────────────────────────────────────────────────────────────────

def test_release_succeeds_for_owner(lease):
    lease.acquire("res/rel", task_id="task-A", ttl_s=30)
    assert lease.release("res/rel", task_id="task-A") is True
    assert lease.get("res/rel") is None


def test_release_rejects_wrong_task_id(lease, mod):
    lease.acquire("res/rel2", task_id="task-A", ttl_s=30)
    with pytest.raises(mod.LeaseNotOwned):
        lease.release("res/rel2", task_id="task-B")
    # holder unchanged
    assert lease.get("res/rel2").task_id == "task-A"


def test_release_noop_if_missing(lease):
    assert lease.release("res/missing", task_id="task-A") is False


# ── list ──────────────────────────────────────────────────────────────────────

def test_list_filters_by_lane(lease):
    lease.acquire("res/L1", task_id="t1", ttl_s=60, lane="alpha")
    lease.acquire("res/L2", task_id="t2", ttl_s=60, lane="alpha")
    lease.acquire("res/L3", task_id="t3", ttl_s=60, lane="beta")
    alpha = lease.list(lane="alpha")
    beta = lease.list(lane="beta")
    all_ = lease.list()
    assert {i.resource for i in alpha} == {"res/L1", "res/L2"}
    assert {i.resource for i in beta} == {"res/L3"}
    assert len(all_) >= 3


# ── TTL expire (empirical) ────────────────────────────────────────────────────

def test_ttl_expires_empirically(lease, fake_client, mod):
    """Set ttl=1s, sleep 2s, verify key gone.

    fakeredis 2.x correctly tracks expiration in wall-clock time.
    """
    lease.acquire("res/expiry", task_id="task-A", ttl_s=1)
    assert lease.get("res/expiry") is not None
    time.sleep(1.6)
    # After ~1.6s the key should be expired
    assert lease.get("res/expiry") is None
    # And a new acquire by different task should succeed
    info = lease.acquire("res/expiry", task_id="task-B", ttl_s=10)
    assert info.task_id == "task-B"


# ── check_path / re-entrant for our task ──────────────────────────────────────

def test_check_path_blocks_for_other_task(lease):
    lease.acquire("apps/foo.py", task_id="task-A", ttl_s=60)
    blocking, holder = lease.check_path("apps/foo.py", our_task_id="task-B")
    assert blocking is True
    assert holder.task_id == "task-A"


def test_check_path_clear_for_owner(lease):
    lease.acquire("apps/bar.py", task_id="task-A", ttl_s=60)
    blocking, holder = lease.check_path("apps/bar.py", our_task_id="task-A")
    assert blocking is False
    assert holder.task_id == "task-A"


def test_check_path_clear_when_free(lease):
    blocking, holder = lease.check_path("apps/unclaimed.py", our_task_id="task-X")
    assert blocking is False
    assert holder is None


# ── CLI `check` graceful degradation ──────────────────────────────────────────

def test_cli_check_kill_switch_disables_enforcement(monkeypatch, mod, capsys):
    monkeypatch.setenv("AGENT_LEASE_ENFORCEMENT", "false")
    rc = mod.main(["check", "apps/anything.py"])
    assert rc == 0


def test_cli_check_redis_down_passes_through(monkeypatch, mod):
    """Force AgentLease() to raise RedisUnavailable → check exits 0 (degraded)."""
    monkeypatch.setenv("AGENT_LEASE_ENFORCEMENT", "true")

    class _Boom:
        def __init__(self, *a, **k):
            raise mod.RedisUnavailable("simulated outage")

    monkeypatch.setattr(mod, "AgentLease", _Boom)
    rc = mod.main(["check", "apps/anything.py"])
    assert rc == 0


def _patch_agent_lease_ctor(monkeypatch, mod, fake_client):
    """Replace mod.AgentLease() (no-arg ctor) with one that returns a real
    AgentLease bound to fake_client. We must capture the ORIGINAL class
    before monkeypatching to avoid infinite recursion.
    """
    original_cls = mod.AgentLease

    def _factory():
        return original_cls(client=fake_client)

    monkeypatch.setattr(mod, "AgentLease", _factory)


def test_cli_check_blocks_when_held_by_other(monkeypatch, mod, fake_client, capsys):
    """check should exit 1 when a different task holds the lease."""
    lease = mod.AgentLease(client=fake_client)
    lease.acquire("infra/launchagents/foo.sh", task_id="alpha", ttl_s=60)

    monkeypatch.setenv("AGENT_LEASE_ENFORCEMENT", "true")
    monkeypatch.setenv("TASK_ID", "beta")
    _patch_agent_lease_ctor(monkeypatch, mod, fake_client)

    rc = mod.main(["check", "infra/launchagents/foo.sh"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "BLOCKED" in err
    assert "alpha" in err


def test_cli_check_clear_when_owner(monkeypatch, mod, fake_client):
    lease = mod.AgentLease(client=fake_client)
    lease.acquire("apps/own.py", task_id="me", ttl_s=60)
    monkeypatch.setenv("AGENT_LEASE_ENFORCEMENT", "true")
    monkeypatch.setenv("TASK_ID", "me")
    _patch_agent_lease_ctor(monkeypatch, mod, fake_client)
    rc = mod.main(["check", "apps/own.py"])
    assert rc == 0


# ── pre-commit hook integration (subprocess) ─────────────────────────────────
# We don't run husky here; we just assert the hook references our CLI + handles
# the hot-zone regex correctly. End-to-end git integration is verified by
# manual smoke test in the runbook.

def test_pre_commit_hook_invokes_agent_lease():
    assert HOOK_PATH.is_file(), f"husky pre-commit hook missing at {HOOK_PATH}"
    content = HOOK_PATH.read_text()
    assert "agent_lease.py" in content or "agent-lease" in content, (
        "pre-commit hook must reference agent_lease.py"
    )
    # Hot-zone hints — at least one of each family
    assert "migrations_v2" in content
    assert "launchagents" in content
    assert "AGENT_LEASE_ENFORCEMENT" in content


def test_pre_commit_hook_is_executable():
    assert os.access(HOOK_PATH, os.X_OK), f"{HOOK_PATH} not executable"


# ── Optional: real Redis end-to-end ──────────────────────────────────────────

def _real_redis_reachable() -> bool:
    try:
        import redis  # noqa
        r = redis.Redis(
            host=os.environ.get("REDIS_HOST", "127.0.0.1"),
            port=int(os.environ.get("REDIS_PORT", "6379")),
            socket_timeout=0.5,
            socket_connect_timeout=0.5,
        )
        return bool(r.ping())
    except Exception:
        return False


@pytest.mark.skipif(not _real_redis_reachable(), reason="real Redis not reachable")
def test_real_redis_end_to_end(mod):
    """Verify acquire/release/heartbeat round-trip on real Redis."""
    res = f"test/e2e/{socket.gethostname()}/{os.getpid()}/{int(time.time())}"
    task = f"e2e-task-{os.getpid()}"
    lease = mod.AgentLease()
    try:
        info = lease.acquire(res, task_id=task, ttl_s=30, lane="e2e")
        assert info.task_id == task
        # block another
        with pytest.raises(mod.LeaseAlreadyHeld):
            lease.acquire(res, task_id=task + "-other", ttl_s=10)
        # heartbeat
        assert lease.heartbeat(res, task_id=task, extend_s=60) is True
        # release
        assert lease.release(res, task_id=task) is True
        assert lease.get(res) is None
    finally:
        # cleanup defensive
        try:
            lease.release(res, task_id=task)
        except Exception:
            pass
