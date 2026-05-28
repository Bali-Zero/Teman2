"""Unit tests for `scripts/wr2_carousel_orchestrator.py` (WR2 Phase 2.1).

Covers the 9 pure / easily-mockable functions identified in the spec:
- topic_hash
- validate_subagent_exists
- build_env_for_claude
- critic_verdict
- write_artifact
- get_or_create_run (idempotent create-or-resume)
- acquire_carousel_lock / release_carousel_lock
- transition_state
- call_subagent

The orchestrator script has a hyphen-free name, but the package directory is
`scripts/` (no `__init__.py` at the project root for it). To stay self-contained
we load the module via `importlib.util.spec_from_file_location`.
"""
from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import os
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Module loading — bypass the hyphen-free-but-no-__init__ issue.
# ---------------------------------------------------------------------------
ORCH_PATH = (
    Path(__file__).resolve().parent.parent / "wr2_carousel_orchestrator.py"
)
_spec = importlib.util.spec_from_file_location("wr2_orchestrator_mod", ORCH_PATH)
assert _spec and _spec.loader, f"could not build spec for {ORCH_PATH}"
orch = importlib.util.module_from_spec(_spec)
# Register in sys.modules so any internal `from __future__ import annotations`
# re-imports do not race; harmless even if unused.
sys.modules["wr2_orchestrator_mod"] = orch
_spec.loader.exec_module(orch)


# ===========================================================================
# 1. topic_hash — pure
# ===========================================================================
def test_topic_hash_deterministic_lowercase_strip():
    """`topic_hash` must lowercase + strip BEFORE hashing (spec)."""
    expected = hashlib.sha256(b"hello world").hexdigest()
    assert orch.topic_hash("Hello World") == expected
    assert orch.topic_hash("  hello world  ") == expected
    assert orch.topic_hash("HELLO WORLD") == expected


def test_topic_hash_distinct_inputs():
    assert orch.topic_hash("foo") != orch.topic_hash("bar")


# ===========================================================================
# 2. validate_subagent_exists — raises FatalOrchestratorError on missing
# ===========================================================================
def test_validate_subagent_exists_raises_when_missing(tmp_path, monkeypatch):
    """Spec §2.3 Pitfall #1 — missing .md must raise FatalOrchestratorError."""
    monkeypatch.setattr(orch, "_SUBAGENTS_DIR", tmp_path)
    with pytest.raises(orch.FatalOrchestratorError, match=r"subagent .md not found"):
        orch.validate_subagent_exists("does-not-exist")


def test_validate_subagent_exists_passes_when_present(tmp_path, monkeypatch):
    monkeypatch.setattr(orch, "_SUBAGENTS_DIR", tmp_path)
    (tmp_path / "wr2-brief-interpreter.md").write_text("# stub", encoding="utf-8")
    # Should NOT raise
    orch.validate_subagent_exists("wr2-brief-interpreter")


# ===========================================================================
# 3. build_env_for_claude — strips ANTHROPIC_API_KEY (CLAUDE.md §5 ban)
# ===========================================================================
def test_build_env_strips_anthropic_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-paid-token-banned")
    monkeypatch.setenv("HARMLESS_VAR", "ok")
    env = orch.build_env_for_claude()
    assert "ANTHROPIC_API_KEY" not in env, (
        "ANTHROPIC_API_KEY must be stripped (paid-endpoint ban CLAUDE.md §5)"
    )
    assert env.get("HARMLESS_VAR") == "ok"


def test_build_env_when_anthropic_key_absent(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    env = orch.build_env_for_claude()
    assert "ANTHROPIC_API_KEY" not in env


# ===========================================================================
# 4. critic_verdict — strict enum parse
# ===========================================================================
def test_critic_verdict_pass():
    assert orch.critic_verdict({"verdict": "PASS"}) == "PASS"


def test_critic_verdict_fail():
    assert orch.critic_verdict({"verdict": "FAIL"}) == "FAIL"


def test_critic_verdict_retryable_fail():
    assert orch.critic_verdict({"verdict": "RETRYABLE_FAIL"}) == "RETRYABLE_FAIL"


def test_critic_verdict_case_and_whitespace_normalised():
    assert orch.critic_verdict({"verdict": " pass "}) == "PASS"
    assert orch.critic_verdict({"verdict": "Retryable_Fail"}) == "RETRYABLE_FAIL"


def test_critic_verdict_unknown_defaults_to_fail():
    """Unknown verdict must default to FAIL (spec §6 strict enum)."""
    assert orch.critic_verdict({"verdict": "MAYBE"}) == "FAIL"
    assert orch.critic_verdict({"verdict": ""}) == "FAIL"
    assert orch.critic_verdict({}) == "FAIL"


def test_critic_verdict_non_dict_defaults_to_fail():
    assert orch.critic_verdict("PASS") == "FAIL"
    assert orch.critic_verdict(None) == "FAIL"
    assert orch.critic_verdict([1, 2, 3]) == "FAIL"


# ===========================================================================
# 5. write_artifact — fsync + JSON / str handling
# ===========================================================================
def test_write_artifact_dict_serialised_json(tmp_path):
    out = orch.write_artifact(tmp_path, "step.json", {"k": "v", "n": 1})
    assert out == tmp_path / "step.json"
    assert out.is_file()
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded == {"k": "v", "n": 1}


def test_write_artifact_list_serialised_json(tmp_path):
    out = orch.write_artifact(tmp_path, "list.json", [1, 2, "three"])
    assert json.loads(out.read_text(encoding="utf-8")) == [1, 2, "three"]


def test_write_artifact_string_written_as_text(tmp_path):
    out = orch.write_artifact(tmp_path, "note.txt", "hello fsync")
    assert out.read_text(encoding="utf-8") == "hello fsync"


def test_write_artifact_creates_parent_dirs(tmp_path):
    nested = tmp_path / "a" / "b" / "c"
    assert not nested.exists()
    out = orch.write_artifact(nested, "x.json", {"ok": True})
    assert out.is_file()
    assert nested.is_dir()


# ===========================================================================
# 6. acquire_carousel_lock / release_carousel_lock — advisory lock
# ===========================================================================
def _expected_lock_key(carousel_id: str) -> int:
    return int(hashlib.sha256(carousel_id.encode()).hexdigest()[:15], 16)


@pytest.mark.asyncio
async def test_acquire_carousel_lock_returns_true(monkeypatch):
    conn = MagicMock()
    conn.fetchval = AsyncMock(return_value=True)
    cid = str(uuid.uuid4())

    got = await orch.acquire_carousel_lock(conn, cid)

    assert got is True
    conn.fetchval.assert_awaited_once()
    args, _ = conn.fetchval.call_args
    assert args[0] == "SELECT pg_try_advisory_lock($1)"
    assert args[1] == _expected_lock_key(cid)


@pytest.mark.asyncio
async def test_acquire_carousel_lock_returns_false_when_held():
    conn = MagicMock()
    conn.fetchval = AsyncMock(return_value=False)
    got = await orch.acquire_carousel_lock(conn, "does-not-matter")
    assert got is False


@pytest.mark.asyncio
async def test_release_carousel_lock_uses_same_key():
    conn = MagicMock()
    conn.execute = AsyncMock(return_value=None)
    cid = str(uuid.uuid4())

    await orch.release_carousel_lock(conn, cid)

    conn.execute.assert_awaited_once()
    args, _ = conn.execute.call_args
    assert args[0] == "SELECT pg_advisory_unlock($1)"
    assert args[1] == _expected_lock_key(cid)


# ===========================================================================
# 7. get_or_create_run — idempotent: same topic_hash + non-terminal = resume
# ===========================================================================
@pytest.mark.asyncio
async def test_get_or_create_run_resumes_active_run_by_topic_hash():
    """Same topic + non-terminal state ⇒ resume (no INSERT)."""
    cid_existing = uuid.uuid4()
    active_row = {
        "carousel_id": cid_existing,
        "topic": "Test topic",
        "topic_hash": orch.topic_hash("Test topic"),
        "state": "brief_done",
        "session_id": "sess-1",
        "output_dir": "/tmp/x",
        "publish_mode": "manual",
    }
    conn = MagicMock()
    # No carousel_id passed → first call SHOULD NOT be the by-id fetchrow;
    # second call hits the topic_hash query. We model both via side_effect.
    conn.fetchrow = AsyncMock(side_effect=[active_row])

    run = await orch.get_or_create_run(
        conn, carousel_id=None, topic="Test topic", session_id="sess-1"
    )

    assert run["carousel_id"] == cid_existing
    assert run["state"] == "brief_done"
    # Single fetchrow (the active-by-topic-hash query), no INSERT
    assert conn.fetchrow.await_count == 1


@pytest.mark.asyncio
async def test_get_or_create_run_creates_new_when_no_active(tmp_path, monkeypatch):
    """No prior run for the topic ⇒ INSERT a new drafted row."""
    monkeypatch.setattr(orch, "_OUTPUT_BASE", tmp_path)
    monkeypatch.setenv("WR2_PUBLISH_MODE", "manual")

    new_cid = uuid.uuid4()
    new_row = {
        "carousel_id": new_cid,
        "topic": "Fresh topic",
        "topic_hash": orch.topic_hash("Fresh topic"),
        "state": "drafted",
        "session_id": "sess-new",
        "output_dir": str(tmp_path / "sess-new"),
        "publish_mode": "manual",
    }
    conn = MagicMock()
    # 1) active lookup returns None  2) INSERT RETURNING returns new_row
    conn.fetchrow = AsyncMock(side_effect=[None, new_row])

    run = await orch.get_or_create_run(
        conn, carousel_id=None, topic="Fresh topic", session_id="sess-new"
    )

    assert run["carousel_id"] == new_cid
    assert run["state"] == "drafted"
    assert conn.fetchrow.await_count == 2
    # Output dir must exist post-call
    assert (tmp_path / "sess-new").is_dir()


# ===========================================================================
# 8. transition_state — ACID transition + terminal completed_at handling
# ===========================================================================
class _FakeTxn:
    """Minimal async context manager mirroring asyncpg.Connection.transaction()."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_transition_state_executes_update():
    conn = MagicMock()
    conn.transaction = MagicMock(return_value=_FakeTxn())
    conn.execute = AsyncMock(return_value=None)

    cid = uuid.uuid4()
    await orch.transition_state(conn, cid, "brief_done")

    conn.execute.assert_awaited_once()
    args, _ = conn.execute.call_args
    assert "UPDATE wr2_carousel_runs" in args[0]
    assert "SET state = $1" in args[0]
    assert args[1] == "brief_done"
    assert args[2] is None  # error
    assert args[3] == cid


@pytest.mark.asyncio
async def test_transition_state_to_terminal_passes_state_to_completed_at_clause():
    """The SQL must contain the CASE that flips completed_at on terminal states."""
    conn = MagicMock()
    conn.transaction = MagicMock(return_value=_FakeTxn())
    conn.execute = AsyncMock(return_value=None)

    cid = uuid.uuid4()
    await orch.transition_state(conn, cid, "failed_cascade", error="boom")

    args, _ = conn.execute.call_args
    sql = args[0]
    assert "completed_at = CASE" in sql, (
        "terminal-state CASE clause missing — completed_at never gets stamped"
    )
    assert "'published'" in sql
    assert "'failed_cascade'" in sql
    assert args[1] == "failed_cascade"
    assert args[2] == "boom"


# ===========================================================================
# 9. call_subagent — subprocess wrapper
# ===========================================================================
@pytest.mark.asyncio
async def test_call_subagent_happy_path(tmp_path, monkeypatch):
    """Returncode 0 + valid JSON ⇒ payload returned with _agent / _model / _elapsed_ms."""
    # Make subagent existence check pass
    monkeypatch.setattr(orch, "_SUBAGENTS_DIR", tmp_path)
    (tmp_path / "wr2-brief-interpreter.md").write_text("# stub", encoding="utf-8")

    # Mock the asyncio subprocess
    fake_proc = MagicMock()
    fake_proc.returncode = 0
    fake_proc.communicate = AsyncMock(
        return_value=(b'{"ok": true, "k": "v"}', b"")
    )
    fake_create = AsyncMock(return_value=fake_proc)

    monkeypatch.setattr(orch.asyncio, "create_subprocess_exec", fake_create)

    payload = await orch.call_subagent(
        "wr2-brief-interpreter", "claude-opus-4-7", "hello"
    )

    assert payload["ok"] is True
    assert payload["k"] == "v"
    assert payload["_agent"] == "wr2-brief-interpreter"
    assert payload["_model"] == "claude-opus-4-7"
    assert isinstance(payload["_elapsed_ms"], int)
    assert payload["_elapsed_ms"] >= 0


@pytest.mark.asyncio
async def test_call_subagent_nonzero_exit_raises_orchestrator_error(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(orch, "_SUBAGENTS_DIR", tmp_path)
    (tmp_path / "wr2-critic.md").write_text("# stub", encoding="utf-8")

    fake_proc = MagicMock()
    fake_proc.returncode = 2
    fake_proc.communicate = AsyncMock(return_value=(b"", b"boom\n"))
    monkeypatch.setattr(
        orch.asyncio, "create_subprocess_exec", AsyncMock(return_value=fake_proc)
    )

    with pytest.raises(orch.OrchestratorError, match=r"exit 2"):
        await orch.call_subagent("wr2-critic", "claude-opus-4-7", "x")


@pytest.mark.asyncio
async def test_call_subagent_bad_json_raises_orchestrator_error(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(orch, "_SUBAGENTS_DIR", tmp_path)
    (tmp_path / "wr2-storyboarder.md").write_text("# stub", encoding="utf-8")

    fake_proc = MagicMock()
    fake_proc.returncode = 0
    fake_proc.communicate = AsyncMock(return_value=(b"not valid json {[}", b""))
    monkeypatch.setattr(
        orch.asyncio, "create_subprocess_exec", AsyncMock(return_value=fake_proc)
    )

    with pytest.raises(orch.OrchestratorError, match=r"JSON decode failed"):
        await orch.call_subagent("wr2-storyboarder", "claude-opus-4-7", "x")


@pytest.mark.asyncio
async def test_call_subagent_payload_is_error_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(orch, "_SUBAGENTS_DIR", tmp_path)
    (tmp_path / "wr2-layout-composer.md").write_text("# stub", encoding="utf-8")

    fake_proc = MagicMock()
    fake_proc.returncode = 0
    fake_proc.communicate = AsyncMock(
        return_value=(
            json.dumps(
                {"is_error": True, "error_message": "rate_limited"}
            ).encode(),
            b"",
        )
    )
    monkeypatch.setattr(
        orch.asyncio, "create_subprocess_exec", AsyncMock(return_value=fake_proc)
    )

    with pytest.raises(orch.OrchestratorError, match=r"is_error"):
        await orch.call_subagent("wr2-layout-composer", "claude-sonnet-4-6", "x")


@pytest.mark.asyncio
async def test_call_subagent_missing_subagent_raises_fatal(tmp_path, monkeypatch):
    """validate_subagent_exists runs FIRST — subprocess never spawned."""
    monkeypatch.setattr(orch, "_SUBAGENTS_DIR", tmp_path)
    # Track that create_subprocess_exec is NEVER awaited
    create_mock = AsyncMock()
    monkeypatch.setattr(orch.asyncio, "create_subprocess_exec", create_mock)

    with pytest.raises(orch.FatalOrchestratorError):
        await orch.call_subagent(
            "wr2-nonexistent-agent", "claude-opus-4-7", "x"
        )

    create_mock.assert_not_awaited()
