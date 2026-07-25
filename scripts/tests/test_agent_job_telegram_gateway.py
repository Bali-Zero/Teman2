"""Tests for AgentJob.send_telegram routing through the notification gateway
(scripts/tg_notify.py) instead of calling the raw Telegram HTTP API directly.

Closes the cicatrix-superscar #3 anti-regrowth violation lint_tg_direct_senders.py
flagged on origin/main (scripts/cron-agent-python/agent_job.py, landed via PR
#3115 "promote the cron-agent-python core to canon", 2026-07-26 fix).
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CRON_AGENT_PYTHON = REPO / "scripts" / "cron-agent-python"

sys.path.insert(0, str(CRON_AGENT_PYTHON))


def _run(coro):
    return asyncio.run(coro)


def test_agent_job_never_calls_telegram_api_directly():
    """GUILT-side pin on the exact violation the lint flagged."""
    src = (CRON_AGENT_PYTHON / "agent_job.py").read_text()
    assert "api.telegram.org" not in src


def test_curiosity_batch_never_calls_telegram_api_directly():
    """The sibling in the same tree, cured in the same PR (was grandfathered)."""
    src = (CRON_AGENT_PYTHON / "curiosity_batch.py").read_text()
    assert "api.telegram.org" not in src


def test_send_telegram_p0_reaches_dry_run_delivery(monkeypatch, tmp_path):
    """A p0 call actually reaches the gateway's send path (not just exit 0)."""
    import agent_job
    import importlib
    importlib.reload(agent_job)

    class _FakeJob(agent_job.AgentJob):
        name = "test-fake-job-p0"

    monkeypatch.setenv("TG_SPOOL_DIR", str(tmp_path))
    monkeypatch.setenv("TG_DRY_RUN", "1")
    monkeypatch.setenv("TG_SECRETS_FILE", "/dev/null")

    job = _FakeJob()
    ok = _run(job.send_telegram("hello from test", tier="p0", dedup_key="test-key-p0"))

    assert ok is True
    sent = (tmp_path / "sent-dry.jsonl").read_text().strip().splitlines()
    assert len(sent) == 1
    assert "hello from test" in json.loads(sent[0])["text"]
    state = json.loads((tmp_path / "state.json").read_text())
    assert "test-key-p0" in state["dedup"]
    assert f"telegram:p0" in job._side_effects


def test_send_telegram_digest_spools_instead_of_sending(monkeypatch, tmp_path):
    """digest tier is spooled for the twice-daily flush, not sent immediately —
    this is the tier run_job() and curiosity_batch.py both use."""
    import agent_job
    import importlib
    importlib.reload(agent_job)

    class _FakeJob(agent_job.AgentJob):
        name = "test-fake-job-digest"

    monkeypatch.setenv("TG_SPOOL_DIR", str(tmp_path))
    monkeypatch.setenv("TG_DRY_RUN", "1")
    monkeypatch.setenv("TG_SECRETS_FILE", "/dev/null")

    job = _FakeJob()
    ok = _run(job.send_telegram("digest msg", tier="digest", dedup_key="test-key-digest"))

    assert ok is True
    pending = (tmp_path / "pending.jsonl").read_text().strip().splitlines()
    assert len(pending) == 1
    assert json.loads(pending[0])["text"] == "digest msg"
    assert not (tmp_path / "sent-dry.jsonl").exists()  # digest never sends immediately


def test_run_job_failure_alert_uses_stable_dedup_key(monkeypatch, tmp_path):
    """run_job()'s own failure path (the flagged call site) must key dedup on
    job+status, never on the message text (which embeds duration_s and would
    defeat dedup on every retry — the exact lesson job_health.py already
    learned, 2026-07-11)."""
    import agent_job
    import importlib
    importlib.reload(agent_job)

    calls = []

    class _FailingJob(agent_job.AgentJob):
        name = "test-fake-job-failure"

        async def run(self):
            raise RuntimeError("boom")

        async def send_telegram(self, msg, tier, chat_id=None, dedup_key=""):
            calls.append({"msg": msg, "tier": tier, "dedup_key": dedup_key})
            return True

        def acquire_lock(self):
            return True

        def release_lock(self):
            pass

        async def _publish_redis_event(self, result):
            pass

        def _reflect(self, result):
            pass

    monkeypatch.setenv("TG_SPOOL_DIR", str(tmp_path))
    monkeypatch.setenv("TG_DRY_RUN", "1")

    job = _FailingJob()
    _run(agent_job.run_job(job, send_alerts=True))

    assert len(calls) == 1
    assert calls[0]["tier"] == "digest"
    assert calls[0]["dedup_key"] == "cron-agent-python:test-fake-job-failure:error"
    assert "duration_s" not in calls[0]["dedup_key"]
