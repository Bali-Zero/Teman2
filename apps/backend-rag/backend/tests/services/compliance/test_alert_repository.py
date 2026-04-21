"""
AlertRepository: asyncpg CRUD on compliance_alerts.

Uses db_tx fixture (rollback on teardown). Requires migrations 114/115 applied
to the test database (run `python -m backend.db.migrate apply-all` once before
the test session).
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
import asyncpg

from backend.services.compliance.alert_repository import AlertRepository, AlertRow


pytestmark = pytest.mark.integration


async def _insert_client(conn: asyncpg.Connection) -> int:
    return await conn.fetchval(
        "INSERT INTO clients (full_name, email, created_at) VALUES ($1, $2, NOW()) RETURNING id",
        "Repo Test Client", "repo-test@example.com",
    )


@pytest.mark.asyncio
async def test_insert_alert_persists(db_tx: asyncpg.Connection) -> None:
    client_id = await _insert_client(db_tx)
    repo = AlertRepository.with_connection(db_tx)
    row = AlertRow(
        alert_id="alert_visa_1",
        client_id=client_id,
        category="visa_expiry",
        severity="urgent",
        status="pending",
        deadline=date.today() + timedelta(days=7),
        days_until=7,
        compliance_item_ref="doc_42",
        dedup_key="visa:1:doc_42",
        message_it="x", message_en="x", message_id="x",
        suggested_action="renew",
        estimated_cost_idr=None,
        evidence_refs=[],
        nb2_ref=None,
    )
    inserted = await repo.insert(row)
    assert inserted.alert_id == "alert_visa_1"
    assert inserted.upgrade_count == 0


@pytest.mark.asyncio
async def test_insert_duplicate_dedup_raises_unique_violation(
    db_tx: asyncpg.Connection,
) -> None:
    client_id = await _insert_client(db_tx)
    repo = AlertRepository.with_connection(db_tx)
    base = AlertRow(
        alert_id="a1", client_id=client_id, category="visa_expiry", severity="urgent",
        status="pending",
        deadline=date.today() + timedelta(days=7), days_until=7,
        compliance_item_ref="doc_x", dedup_key="visa:1:doc_x",
        message_it="", message_en="", message_id="",
        suggested_action="", estimated_cost_idr=None, evidence_refs=[], nb2_ref=None,
    )
    await repo.insert(base)
    dup = AlertRow(**{**base.__dict__, "alert_id": "a2"})
    with pytest.raises(asyncpg.UniqueViolationError):
        await repo.insert(dup)


@pytest.mark.asyncio
async def test_find_active_by_dedup_key_returns_existing(
    db_tx: asyncpg.Connection,
) -> None:
    client_id = await _insert_client(db_tx)
    repo = AlertRepository.with_connection(db_tx)
    row = AlertRow(
        alert_id="a3", client_id=client_id, category="visa_expiry", severity="urgent",
        status="pending",
        deadline=date.today() + timedelta(days=7), days_until=7,
        compliance_item_ref="doc_y", dedup_key="visa:1:doc_y",
        message_it="", message_en="", message_id="",
        suggested_action="", estimated_cost_idr=None, evidence_refs=[], nb2_ref=None,
    )
    await repo.insert(row)
    found = await repo.find_active_by_dedup_key("visa:1:doc_y")
    assert found is not None and found.alert_id == "a3"


@pytest.mark.asyncio
async def test_find_active_ignores_resolved(db_tx: asyncpg.Connection) -> None:
    client_id = await _insert_client(db_tx)
    repo = AlertRepository.with_connection(db_tx)
    row = AlertRow(
        alert_id="a4", client_id=client_id, category="visa_expiry", severity="urgent",
        status="resolved",
        deadline=date.today() + timedelta(days=7), days_until=7,
        compliance_item_ref="doc_z", dedup_key="visa:1:doc_z",
        message_it="", message_en="", message_id="",
        suggested_action="", estimated_cost_idr=None, evidence_refs=[], nb2_ref=None,
    )
    await repo.insert(row)
    assert await repo.find_active_by_dedup_key("visa:1:doc_z") is None


@pytest.mark.asyncio
async def test_promote_updates_severity_and_increments_counter(
    db_tx: asyncpg.Connection,
) -> None:
    client_id = await _insert_client(db_tx)
    repo = AlertRepository.with_connection(db_tx)
    row = AlertRow(
        alert_id="a5", client_id=client_id, category="visa_expiry", severity="warning",
        status="pending",
        deadline=date.today() + timedelta(days=30), days_until=30,
        compliance_item_ref="doc_w", dedup_key="visa:1:doc_w",
        message_it="", message_en="", message_id="",
        suggested_action="", estimated_cost_idr=None, evidence_refs=[], nb2_ref=None,
    )
    await repo.insert(row)
    promoted = await repo.promote("a5", new_severity="urgent", new_days_until=7)
    assert promoted.severity == "urgent"
    assert promoted.upgrade_count == 1
    assert promoted.days_until == 7


@pytest.mark.asyncio
async def test_update_status_to_resolved(db_tx: asyncpg.Connection) -> None:
    client_id = await _insert_client(db_tx)
    repo = AlertRepository.with_connection(db_tx)
    row = AlertRow(
        alert_id="a6", client_id=client_id, category="visa_expiry", severity="urgent",
        status="pending",
        deadline=date.today() + timedelta(days=7), days_until=7,
        compliance_item_ref="doc_r", dedup_key="visa:1:doc_r",
        message_it="", message_en="", message_id="",
        suggested_action="", estimated_cost_idr=None, evidence_refs=[], nb2_ref=None,
    )
    await repo.insert(row)
    updated = await repo.update_status("a6", new_status="resolved")
    assert updated.status == "resolved"
    assert updated.resolved_at is not None


@pytest.mark.asyncio
async def test_list_by_client_ordered(db_tx: asyncpg.Connection) -> None:
    client_id = await _insert_client(db_tx)
    repo = AlertRepository.with_connection(db_tx)
    for i, cat in enumerate(["visa_expiry", "tax_filing", "lkpm"]):
        await repo.insert(AlertRow(
            alert_id=f"a7_{i}", client_id=client_id, category=cat, severity="urgent",
            status="pending",
            deadline=date.today() + timedelta(days=7+i), days_until=7+i,
            compliance_item_ref=f"ref_{i}",
            dedup_key=f"{cat}:{client_id}:{i}",
            message_it="", message_en="", message_id="",
            suggested_action="", estimated_cost_idr=None, evidence_refs=[], nb2_ref=None,
        ))
    rows = await repo.list_by_client(client_id, limit=50, offset=0)
    assert len(rows) == 3
