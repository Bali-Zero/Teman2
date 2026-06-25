"""Unit tests for worker.main() stage-handler wiring (FASE 2↔3/4 bridge).

DB-free + Ollama-free: _build_pool, IntakeWorker, and run_forever are stubbed.
Verifies that the production entrypoint wires the REAL stage handler by default
(so a deployed worker actually does OCR + creates document_routing_proposal),
and falls back to the stub ONLY when INTAKE_WORKER_STUB is set.

Regression guard for the blocker found 2026-06-07: main() built IntakeWorker
WITHOUT stage_handler → silent _stub_stage passthrough → rows reached 'done'
with no OCR and no routing proposal.
"""

from __future__ import annotations

import pytest

import backend.services.intake.worker as worker_mod


class _FakePool:
    async def close(self):
        return None


@pytest.fixture
def captured(monkeypatch):
    """Patch out I/O; capture the kwargs main() passes to IntakeWorker."""
    seen: dict = {}

    async def fake_build_pool():
        return _FakePool()

    class _FakeWorker:
        def __init__(self, pool, *, config=None, stage_handler=None, **kw):
            seen["pool"] = pool
            seen["config"] = config
            seen["stage_handler"] = stage_handler

        async def run_forever(self):
            return None

    monkeypatch.setattr(worker_mod, "_build_pool", fake_build_pool)
    monkeypatch.setattr(worker_mod, "IntakeWorker", _FakeWorker)
    return seen


@pytest.mark.asyncio
async def test_main_wires_real_handler_by_default(captured, monkeypatch):
    monkeypatch.delenv("INTAKE_WORKER_STUB", raising=False)

    # Capture what build_real_stage_handler returns so we can assert identity.
    import backend.services.intake.stages as stages_mod

    sentinel = object()
    monkeypatch.setattr(stages_mod, "build_real_stage_handler", lambda pool: sentinel)

    await worker_mod.main()

    assert captured["stage_handler"] is sentinel, (
        "main() must wire the REAL stage handler by default — otherwise the worker "
        "stub-processes rows (no OCR, no routing proposal)."
    )


@pytest.mark.asyncio
async def test_main_uses_stub_when_env_set(captured, monkeypatch):
    monkeypatch.setenv("INTAKE_WORKER_STUB", "1")
    await worker_mod.main()
    # Stub path: main() does NOT pass stage_handler → IntakeWorker default (None here).
    assert captured["stage_handler"] is None


@pytest.mark.asyncio
async def test_claim_prioritizes_pending_whatsapp_before_drive_backfill():
    """WA mirror attachments must not sit behind the historical Drive backlog."""

    class _FakeConn:
        sql: str | None = None
        args: tuple | None = None

        async def fetchrow(self, sql, *args):  # noqa: ANN001, ANN202
            self.sql = sql
            self.args = args
            return None

    conn = _FakeConn()
    worker = worker_mod.IntakeWorker(_FakePool())

    await worker._claim_with_inbound(conn)

    assert conn.sql is not None
    assert "WHEN status = 'pending' AND source = 'whatsapp' THEN 0" in conn.sql
    assert "WHEN status = 'pending'                         THEN 1" in conn.sql
    assert conn.sql.index("WHEN 'ocr_done'") < conn.sql.index(
        "WHEN status = 'pending' AND source = 'whatsapp' THEN 0"
    )
