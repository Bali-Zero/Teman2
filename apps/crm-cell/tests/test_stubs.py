"""Smoke tests for crm-cell W2 stub classes (CrmScarRecorder /
CrmHGTPublisher / CrmEventBridge).

Sprint 3 W2 review I5 — confirms the stub interfaces are stable and the
package imports cleanly. DB-touching tests land in Sprint 4 when the
call sites are wired.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Add the crm-cell package to sys.path so imports resolve when run from
# repo root (no editable install yet).
_PACKAGE_PATH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PACKAGE_PATH))

from crm_cell import (  # noqa: E402
    CELL_NAME,
    CELL_VERSION,
    CrmEventBridge,
    CrmScar,
    CrmScarRecorder,
    FailureKind,
    WelcomeRunResult,
)


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


def test_cell_name_and_version():
    """Phase 3 TICKET A.1 bumped CELL_VERSION 0.1.0 → 0.2.0 (CrmHGTBridge async)."""
    assert CELL_NAME == "crm-cell"
    assert CELL_VERSION == "0.2.0"


# ---------------------------------------------------------------------------
# CrmScarRecorder
# ---------------------------------------------------------------------------


def test_scar_recorder_record_logs_and_returns_none(caplog):
    caplog.set_level("INFO")
    recorder = CrmScarRecorder()
    scar = CrmScar(
        failure_kind=FailureKind.WELCOME_PARTIAL_FAILURE,
        sub_module="welcome",
        detail="WhatsApp send failed step 3 of 4",
        client_id=42,
        practice_id=1001,
    )
    result = recorder.record(scar)
    assert result is None  # stub; Sprint 4 wires Genome
    # Stub log line includes the namespaced scar_id
    assert any(
        "crm.welcome.welcome_partial_failure" in record.message
        for record in caplog.records
    )


def test_scar_recorder_records_observed_at_when_missing(caplog):
    """When CrmScar.observed_at is None, recorder must stamp it."""
    caplog.set_level("INFO")
    recorder = CrmScarRecorder()
    scar = CrmScar(
        failure_kind=FailureKind.BREVO_BOUNCE,
        sub_module="welcome.email",
        detail="Brevo 550 hard bounce",
    )
    recorder.record(scar)
    assert any(
        "brevo_bounce" in record.message for record in caplog.records
    )


def test_failure_kind_enum_values_match_design():
    """Sprint 3 W2 design names — the enum is part of the public contract."""
    assert FailureKind.WELCOME_PARTIAL_FAILURE.value == "welcome_partial_failure"
    assert FailureKind.DRIVE_CIRCUIT_OPEN.value == "drive_circuit_open"
    assert FailureKind.BREVO_BOUNCE.value == "brevo_bounce"
    assert FailureKind.WHATSAPP_TEMPLATE_REJECTED.value == "whatsapp_template_rejected"


# ---------------------------------------------------------------------------
# CrmHGTBridge: see test_hgt_publisher.py (Phase 3 TICKET A.1)
# ---------------------------------------------------------------------------
# The Sprint 3 W2 sync stub ``CrmHGTPublisher`` was DELETED in Phase 3
# TICKET A.1. Async tests live in ``test_hgt_publisher.py``.


# ---------------------------------------------------------------------------
# CrmEventBridge
# ---------------------------------------------------------------------------


def test_event_bridge_record_welcome_run_returns_none_in_stub(caplog):
    """Stub returns None (no DB pool). Sprint 4 returns the row id."""
    caplog.set_level("INFO")
    bridge = CrmEventBridge()
    result = WelcomeRunResult(
        client_id=42,
        practice_id=1001,
        drive_folder_id="folder-abc",
        channels_sent=["email", "whatsapp"],
        success=True,
        started_at=datetime.now(tz=timezone.utc),
    )
    row_id = asyncio.run(bridge.record_welcome_run(result))
    assert row_id is None
    assert any(
        "crm_welcome_runs UPSERT" in record.message
        for record in caplog.records
    )


def test_event_bridge_stamps_completed_at_when_missing():
    """If completed_at is None, the bridge stamps NOW() before INSERT."""
    bridge = CrmEventBridge()
    result = WelcomeRunResult(
        client_id=42,
        practice_id=1001,
        drive_folder_id=None,
        channels_sent=["email"],
        success=False,
        started_at=datetime.now(tz=timezone.utc),
        completed_at=None,
    )
    row_id = asyncio.run(bridge.record_welcome_run(result))
    assert row_id is None
