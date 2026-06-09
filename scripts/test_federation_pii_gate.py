#!/usr/bin/env python3
"""Integration test for the P2 confine-PII gate wired into federation's
``run_dispatch`` chokepoint (CRITICO-2 Step C).

Proves the air-gap is REAL: a prompt carrying synthetic PII never reaches the
cloud subprocess (``asyncio.create_subprocess_exec`` is NOT called), while a
clean prompt does. All PII here is SYNTHETIC (Law 2).

Run (from scripts/, backend venv)::

    ../apps/backend-rag/.venv/bin/python -m pytest test_federation_pii_gate.py -q
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# scripts/ + apps/backend-rag on path (mirror test_federation_parallelize_gate).
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "backend-rag"))

import federation_orchestrator as fo  # noqa: E402

SYNTH_KTP = "3171234567890123"  # invented 16-digit KTP
PAD = " analyse the dispatch routing layer and summarise the trade-offs " * 3


class _FakeProc:
    returncode = 0

    async def communicate(self):
        return (b"cloud agent output", b"")


def _patch_subprocess(monkeypatch):
    calls: list = []

    async def _fake_exec(*args, **kwargs):
        calls.append(args)
        return _FakeProc()

    monkeypatch.setattr(fo.asyncio, "create_subprocess_exec", _fake_exec)
    return calls


def test_run_dispatch_blocks_pii_prompt_no_cloud_call(monkeypatch):
    calls = _patch_subprocess(monkeypatch)
    out = asyncio.run(fo.run_dispatch("search", f"fix the case, KTP {SYNTH_KTP} {PAD}"))
    assert out.startswith("[PII-BLOCKED")
    assert calls == []  # the cloud subprocess was NEVER invoked (air-gap)


def test_run_dispatch_allows_clean_prompt(monkeypatch):
    calls = _patch_subprocess(monkeypatch)
    out = asyncio.run(
        fo.run_dispatch(
            "search",
            "Compare consumer-group durability vs listen-notify for the bus. " + PAD,
        )
    )
    assert "PII-BLOCKED" not in out
    assert out == "cloud agent output"
    assert len(calls) == 1  # the clean prompt reached the cloud subprocess


def test_run_dispatch_blocks_bare_crm_name_with_context(monkeypatch):
    # panel F1 at the chokepoint: a CRM name with PG out of scope (degraded
    # redactor) is still blocked by the STRATO B+ context backstop because the
    # prompt carries the "client" context word — NO cloud call.
    calls = _patch_subprocess(monkeypatch)
    out = asyncio.run(
        fo.run_dispatch("explore", f"summarise our client Budi Santoso's case {PAD}")
    )
    assert out.startswith("[PII-BLOCKED")
    assert calls == []


def test_run_dispatch_residual_context_free_bare_name_documented(monkeypatch):
    # HONEST residual (Codex #2 — pin it, don't hide it): a context-free bare
    # name with PG out of scope is the documented best-effort floor. With the
    # default degraded posture it reaches CLOUD. This test ENCODES the known
    # gap; flipping PRIVACY_PREFLIGHT_STRICT + wiring PG (or the deferred
    # Qwen-NER) is what closes it. If this ever starts BLOCKING, the floor
    # improved — update the test, don't assume regression.
    calls = _patch_subprocess(monkeypatch)
    out = asyncio.run(
        fo.run_dispatch("search", f"fix the failing retry test for Budi {PAD}")
    )
    # documents current behavior: no structured ID, no context word → CLOUD.
    assert out == "cloud agent output"
    assert len(calls) == 1
