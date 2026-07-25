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
    assert "telegram:p0:sent" in job._side_effects


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
    the job name alone, never on the message text (which embeds duration_s
    and would defeat dedup on every retry — the exact lesson job_health.py
    already learned, 2026-07-11). tier is p0: a job that stopped working is
    actionable — see agent_job.py's own comment at the call site."""
    import agent_job
    import importlib
    importlib.reload(agent_job)

    calls = []

    class _FailingJob(agent_job.AgentJob):
        name = "test-fake-job-failure"

        async def run(self):
            raise RuntimeError("boom")

        async def send_telegram(self, msg, chat_id=None, tier="p0", dedup_key=""):
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
    assert calls[0]["tier"] == "p0"
    assert calls[0]["dedup_key"] == "cron-job-failed:test-fake-job-failure"
    assert "duration_s" not in calls[0]["dedup_key"]
    assert "<b>" not in calls[0]["msg"] and "<code>" not in calls[0]["msg"]


class _FakeAsyncProc:
    """Stands in for asyncio.subprocess.Process — the gateway subprocess is
    now spawned via asyncio.create_subprocess_exec (async-regression fix,
    2026-07-26: subprocess.run inside an `async def` blocked the event loop
    for up to the call's timeout; main's #3142 fixed this in send_telegram,
    curiosity_batch.py carried the same defect independently until this
    branch)."""

    def __init__(self, stderr: bytes = b""):
        self._stderr = stderr
        self.returncode = 0

    async def communicate(self, input=None):
        return b"", self._stderr


def test_send_telegram_unparseable_gateway_output_is_not_ok(monkeypatch):
    """The gateway exits 0 by contract even on its own internal failures
    ("NEVER fails the caller") — returncode alone can't distinguish a real
    send from a swallowed one. A run whose stderr never carries a
    `tg_notify: <outcome>` line is the one case that must come back False."""
    import agent_job
    import importlib
    importlib.reload(agent_job)

    class _FakeJob(agent_job.AgentJob):
        name = "test-fake-job-unparseable"

    async def _fake_create_subprocess_exec(*args, **kwargs):
        return _FakeAsyncProc(stderr=b"")

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_create_subprocess_exec)

    job = _FakeJob()
    ok = _run(job.send_telegram("hello", tier="p0"))

    assert ok is False
    assert job._side_effects == []  # no false side_effect recorded either


def test_send_telegram_recognizes_every_gateway_outcome(monkeypatch):
    """Every real outcome tg_notify.py can print is treated as delivery
    custody taken, not just 'sent' — mirrors sentinel_lib/alerter.py's own
    parsing (established 2026-07-07)."""
    import agent_job
    import importlib
    importlib.reload(agent_job)

    class _FakeJob(agent_job.AgentJob):
        name = "test-fake-job-outcomes"

    def _make_fake_create(stderr: bytes):
        async def _fake_create_subprocess_exec(*args, **kwargs):
            return _FakeAsyncProc(stderr=stderr)
        return _fake_create_subprocess_exec

    for outcome in ("sent", "spooled", "logged", "deduped", "p0_overflow_spooled", "p0_unsent_spooled"):
        monkeypatch.setattr(
            "asyncio.create_subprocess_exec",
            _make_fake_create(f"tg_notify: {outcome}\n".encode()),
        )
        job = _FakeJob()
        assert _run(job.send_telegram("hello", tier="p0")) is True, outcome


def test_log_anomaly_tier_follows_alert_severity():
    """RED (FATAL/OOM/502/503/CRM-down) escalates to p0; an all-YELLOW batch
    (circuit-breaker, timeouts) stays digest. Any RED in a mixed batch wins."""
    import log_anomaly_detector as lad
    import importlib
    importlib.reload(lad)

    red = [{"severity": "RED", "label": "fatal_error"}]
    yellow = [{"severity": "YELLOW", "label": "job_timeout"}]

    assert lad._tier_for(red) == "p0"
    assert lad._tier_for(yellow) == "digest"
    assert lad._tier_for(red + yellow) == "p0"


def test_log_anomaly_compose_alert_is_plain_text():
    """The gateway sends without parse_mode — a message built with HTML tags
    would show up literally, especially damaging now that RED alerts go out
    immediate+untruncated via tier=p0 (no digest-flush truncation to hide it)."""
    import log_anomaly_detector as lad
    import importlib
    importlib.reload(lad)

    job = lad.LogAnomalyDetectorJob()
    msg = job._compose_alert([
        {"severity": "RED", "label": "fatal_error", "source": "x", "sample": "boom"}
    ])
    assert "<b>" not in msg and "<code>" not in msg and "<i>" not in msg


def test_curiosity_batch_send_telegram_batch_reaches_dry_run_delivery(monkeypatch, tmp_path):
    """curiosity_batch.py's own gateway call (this branch's async-regression
    fix, mirrors agent_job.py's pattern) actually reaches the gateway's
    spool path, not just exit-0 — same proof standard as the p0/digest tests
    above. tier=digest spools to pending.jsonl, never sends immediately."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake/fake")  # read at import time
    import curiosity_batch as cb
    import importlib
    importlib.reload(cb)

    monkeypatch.setenv("TG_SPOOL_DIR", str(tmp_path))
    monkeypatch.setenv("TG_DRY_RUN", "1")
    monkeypatch.setenv("TG_SECRETS_FILE", "/dev/null")

    findings = [{
        "source": "pattern_mining", "question": "why does X happen?",
        "finding": "because Y", "actionable": True,
        "information_gain": 0.9, "created_at": None,
    }]
    stats = {"total": 1, "actionable_cnt": 1, "last_finding_at": None}

    _run(cb.send_telegram_batch(findings, stats))

    pending = (tmp_path / "pending.jsonl").read_text().strip().splitlines()
    assert len(pending) == 1
    assert "why does X happen?" in json.loads(pending[0])["text"]
    assert not (tmp_path / "sent-dry.jsonl").exists()


def test_intel_radar_compose_message_is_plain_text():
    """Same gateway constraint as log-anomaly — no parse_mode support."""
    import intel_radar_daily_digest as ird
    import importlib
    importlib.reload(ird)

    job = ird.IntelRadarDailyDigestJob()
    msg = job._compose_message([
        {"query_tier": "L1", "title": "<script>x</script>", "source_domain": "example.com"}
    ])
    assert "<b>" not in msg and "<i>" not in msg
    # No HTML-entity leakage either — plain text should show the raw title,
    # not an escaped-then-never-unescaped "&lt;script&gt;".
    assert "&lt;" not in msg
