"""Promotion gate tests (T6)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from mata_garuda.domains.setup_team.promotion_gate import (
    ALERT_THRESHOLD_DAYS,
    DEFAULT_SLA_DAYS,
    auto_approve_tier1_after_sla,
    check_sla_and_alert,
    manual_decide,
    propose_promotion,
)


@pytest.fixture
def db(tmp_path):
    return tmp_path / "setup_team.sqlite"


@pytest.fixture
def t0():
    return datetime(2026, 5, 8, 12, 0, 0, tzinfo=timezone.utc)


def test_propose_promotion_inserts_pending_row(db, t0):
    qid = propose_promotion(
        intel_source_id="pasal-id:test-1",
        target_authority_nb="NB-AUTHORITY-Regulation",
        owner="Adit",
        tier=1,
        db_path=db,
        now=t0,
    )
    assert qid > 0
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM promotion_queue WHERE queue_id=?", (qid,)).fetchone()
    conn.close()
    assert row["decision"] == "pending"
    assert row["owner"] == "Adit"
    assert row["tier"] == 1
    sla = datetime.fromisoformat(row["sla_deadline"])
    assert (sla - t0).days == DEFAULT_SLA_DAYS


def test_propose_promotion_idempotent_on_same_pair(db, t0):
    """Same (intel_source_id, target_authority_nb) → returns existing id, no clock reset."""
    q1 = propose_promotion(
        "pasal-id:x", "NB-AUTHORITY-Regulation", "Adit", db_path=db, now=t0
    )
    later = t0 + timedelta(days=5)
    q2 = propose_promotion(
        "pasal-id:x", "NB-AUTHORITY-Regulation", "Adit", db_path=db, now=later
    )
    assert q1 == q2
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT proposed_at, sla_deadline FROM promotion_queue").fetchone()
    conn.close()
    # Original SLA preserved (not advanced by 5 days)
    sla = datetime.fromisoformat(row["sla_deadline"])
    assert (sla - t0).days == DEFAULT_SLA_DAYS


def test_check_sla_and_alert_emits_warning_3_days_before(db, t0):
    propose_promotion(
        "pasal-id:near", "NB-AUTHORITY-Regulation", "Adit", tier=2, db_path=db, now=t0
    )
    # Move clock to SLA - 2 days
    now = t0 + timedelta(days=DEFAULT_SLA_DAYS - 2)
    alerts = check_sla_and_alert(db_path=db, now=now)
    assert len(alerts) == 1
    assert alerts[0].kind == "sla_warning"
    assert alerts[0].days_remaining == 2


def test_check_sla_and_alert_emits_tier1_auto_approve_signal_when_sla_passed(db, t0):
    propose_promotion(
        "pasal-id:t1", "NB-AUTHORITY-Regulation", "Adit", tier=1, db_path=db, now=t0
    )
    now = t0 + timedelta(days=DEFAULT_SLA_DAYS + 1)
    alerts = check_sla_and_alert(db_path=db, now=now)
    assert len(alerts) == 1
    assert alerts[0].kind == "sla_reached_tier1_auto_approve"
    assert alerts[0].tier == 1
    assert alerts[0].days_remaining < 0


def test_check_sla_and_alert_emits_tier2_escalate_when_sla_passed(db, t0):
    propose_promotion(
        "pasal-id:t2", "NB-AUTHORITY-Regulation", "Veronika", tier=2, db_path=db, now=t0
    )
    now = t0 + timedelta(days=DEFAULT_SLA_DAYS + 5)
    alerts = check_sla_and_alert(db_path=db, now=now)
    assert len(alerts) == 1
    assert alerts[0].kind == "sla_reached_tier2_escalate"


def test_check_sla_and_alert_quiet_when_sla_far_away(db, t0):
    propose_promotion("pasal-id:fresh", "NB-AUTHORITY-Regulation", "Adit", db_path=db, now=t0)
    # 1 day after proposal → 13 days remaining → no warning yet
    now = t0 + timedelta(days=1)
    alerts = check_sla_and_alert(db_path=db, now=now)
    assert alerts == []


def test_check_sla_and_alert_skips_already_decided_rows(db, t0):
    qid = propose_promotion(
        "pasal-id:x", "NB-AUTHORITY-Regulation", "Adit", tier=1, db_path=db, now=t0
    )
    manual_decide(qid, "approved", db_path=db, now=t0)
    now = t0 + timedelta(days=DEFAULT_SLA_DAYS + 5)
    alerts = check_sla_and_alert(db_path=db, now=now)
    assert alerts == []


def test_auto_approve_tier1_after_sla_transitions_only_tier1(db, t0):
    propose_promotion(
        "src1", "NB-AUTHORITY-Regulation", "Adit", tier=1, db_path=db, now=t0
    )
    propose_promotion(
        "src2", "NB-AUTHORITY-Regulation", "Veronika", tier=2, db_path=db, now=t0
    )
    propose_promotion(
        "src3", "NB-AUTHORITY-Regulation", "Adit", tier=1, db_path=db, now=t0
    )
    now = t0 + timedelta(days=DEFAULT_SLA_DAYS + 1)
    n = auto_approve_tier1_after_sla(db_path=db, now=now)
    assert n == 2

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    rows = {r["intel_source_id"]: r for r in conn.execute("SELECT * FROM promotion_queue").fetchall()}
    conn.close()
    assert rows["src1"]["decision"] == "approved"
    assert rows["src1"]["decided_at"] is not None
    assert rows["src2"]["decision"] == "pending"  # tier 2 stays pending
    assert rows["src3"]["decision"] == "approved"


def test_auto_approve_skips_tier1_before_sla(db, t0):
    propose_promotion(
        "src1", "NB-AUTHORITY-Regulation", "Adit", tier=1, db_path=db, now=t0
    )
    now = t0 + timedelta(days=DEFAULT_SLA_DAYS - 1)
    n = auto_approve_tier1_after_sla(db_path=db, now=now)
    assert n == 0


def test_manual_decide_transitions_to_approved(db, t0):
    qid = propose_promotion(
        "x", "NB-AUTHORITY-Regulation", "Adit", db_path=db, now=t0
    )
    ok = manual_decide(qid, "approved", db_path=db, now=t0)
    assert ok is True
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM promotion_queue WHERE queue_id=?", (qid,)).fetchone()
    conn.close()
    assert row["decision"] == "approved"


def test_manual_decide_rejects_invalid_target_decision(db, t0):
    qid = propose_promotion("x", "NB-AUTHORITY-Regulation", "Adit", db_path=db, now=t0)
    with pytest.raises(ValueError):
        manual_decide(qid, "pending", db_path=db, now=t0)  # type: ignore[arg-type]


def test_manual_decide_no_op_when_already_decided(db, t0):
    qid = propose_promotion("x", "NB-AUTHORITY-Regulation", "Adit", db_path=db, now=t0)
    manual_decide(qid, "approved", db_path=db, now=t0)
    second = manual_decide(qid, "rejected", db_path=db, now=t0)
    assert second is False  # already decided, no-op


def test_alert_threshold_constant_is_3_days():
    assert ALERT_THRESHOLD_DAYS == 3


def test_default_sla_is_14_days():
    assert DEFAULT_SLA_DAYS == 14
