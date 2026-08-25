"""Synthetic, non-PII fixtures for the Magazine action-chain adapters.

Every row below is fabricated for this test suite -- no real Intel Lake /
NAGA / CRM / Magazine row is ever pasted into this repo (CLAUDE.md hard
rule). `sys.path` bootstrap mirrors
`apps/backend-rag/backend/tests/unit/research_os/conftest.py`'s existing
convention exactly (this directory is new and does not inherit that one).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "packages" / "research-os-core").is_dir():
            return candidate
    raise RuntimeError("cannot locate repository root from research_os test path")


_PACKAGE_ROOT = _repo_root() / "packages" / "research-os-core"
if str(_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_ROOT))

_VALID_SHA256 = "a" * 64


def make_ops_intent_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "intent_id": "0198f3a1-0000-7000-8000-000000000001",
        "actor_key": "operator:zero",
        "effective_role": "operator",
        "policy_version": "v1",
        "idempotency_key": "idem-key-0001",
        "intent_kind": "rerun_collector",
        "params_json": '{"collector": "regulatory-watcher"}',
        "request_hash": _VALID_SHA256,
        "reason_code": "manual_retrigger",
        "status": "succeeded",
        "attempt_limit": 3,
        "attempt_count": 1,
        "worker_id": "worker-1",
        "claim_token": "claim-token-1",
        "fencing_token": 1,
        "heartbeat_at": "2026-08-20T10:05:00+00:00",
        "lease_deadline": "2026-08-20T10:10:00+00:00",
        "effect_token": None,
        "pre_effect_attested_at": None,
        "attested_policy_version": None,
        "attestation_expires_at": None,
        "effect_consumed_at": None,
        "expires_at": "2026-08-20T12:00:00+00:00",
        "started_at": "2026-08-20T10:00:00+00:00",
        "completed_at": "2026-08-20T10:06:00+00:00",
        "failure_code": None,
        "created_at": "2026-08-20T10:00:00+00:00",
    }
    row.update(overrides)
    return row


def make_ops_receipt_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "receipt_id": "0198f3a1-0000-7000-8000-0000000000f1",
        "intent_id": "0198f3a1-0000-7000-8000-000000000001",
        "status": "succeeded",
        "receipt_json": '{"code": "effect_acknowledged"}',
        "receipt_hash": _VALID_SHA256,
        "request_hash": _VALID_SHA256,
        "key_id": "server-terminal",
        "body_hash": _VALID_SHA256,
        "fencing_token": 1,
        "attested_policy_version": None,
        "created_at": "2026-08-20T10:06:30+00:00",
    }
    row.update(overrides)
    return row


@pytest.fixture
def ops_intent_row() -> dict[str, Any]:
    return make_ops_intent_row()


@pytest.fixture
def ops_receipt_row() -> dict[str, Any]:
    return make_ops_receipt_row()
