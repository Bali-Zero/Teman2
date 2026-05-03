"""Tests for EventBus handlers writing to bridge_outbox."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


class _AcquireCM:
    """Async context manager wrapper for pool.acquire() mocking."""
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *a):
        return False


def _build_bus_and_pool():
    """Build a bus stub and a pool that yields a mock conn from acquire()."""
    bus_stub = MagicMock()
    bus_stub.subscribe = MagicMock()
    fake_conn = MagicMock()
    fake_pool = MagicMock()
    fake_pool.acquire = MagicMock(return_value=_AcquireCM(fake_conn))
    return bus_stub, fake_pool, fake_conn


def _get_handler(bus_stub, event_name):
    """Extract the registered handler function for the given event name."""
    for call in bus_stub.subscribe.call_args_list:
        if call.args[0] == event_name:
            return call.args[1]
    raise AssertionError(f"No handler registered for {event_name!r}")


@pytest.mark.asyncio
async def test_on_client_changed_insert_writes_outbox(monkeypatch):
    """INSERT operation triggers crm.client_created in outbox."""
    from backend.services.events import handlers as h

    insert_mock = AsyncMock(return_value=42)
    monkeypatch.setattr(
        "backend.services.events.handlers._core.insert_outbox_event",
        insert_mock,
    )

    bus_stub, fake_pool, _ = _build_bus_and_pool()
    h.register_handlers(bus_stub, fake_pool)
    on_client = _get_handler(bus_stub, "client.changed")

    h._recent_events.clear()
    await on_client({
        "client_id": 7,
        "operation": "INSERT",
        "email": "a@b",
        "sector": "PMA-Tax",
    })

    insert_mock.assert_called_once()
    # signature: insert_outbox_event(conn, event_type=..., payload=...)
    call_kwargs = insert_mock.call_args.kwargs
    assert call_kwargs["event_type"] == "crm.client_created"
    assert call_kwargs["payload"]["client_id"] == 7
    assert call_kwargs["payload"]["email"] == "a@b"
    assert call_kwargs["payload"]["sector"] == "PMA-Tax"


@pytest.mark.asyncio
async def test_on_client_changed_sector_update_writes_outbox(monkeypatch):
    """UPDATE with sector in changed_fields triggers crm.client_sector_changed."""
    from backend.services.events import handlers as h

    insert_mock = AsyncMock(return_value=43)
    monkeypatch.setattr("backend.services.events.handlers._core.insert_outbox_event", insert_mock)

    bus_stub, fake_pool, _ = _build_bus_and_pool()
    h.register_handlers(bus_stub, fake_pool)
    on_client = _get_handler(bus_stub, "client.changed")

    h._recent_events.clear()
    await on_client({
        "client_id": 7,
        "operation": "UPDATE",
        "email": "a@b",
        "changed_fields": ["sector"],
        "sector": "Tax",
        "old_sector": "Visa",
    })

    insert_mock.assert_called_once()
    call_kwargs = insert_mock.call_args.kwargs
    assert call_kwargs["event_type"] == "crm.client_sector_changed"
    assert call_kwargs["payload"]["sector"] == "Tax"
    assert call_kwargs["payload"]["old_sector"] == "Visa"


@pytest.mark.asyncio
async def test_on_client_changed_update_without_sector_no_outbox(monkeypatch):
    """UPDATE without sector field does NOT trigger outbox write."""
    from backend.services.events import handlers as h

    insert_mock = AsyncMock(return_value=44)
    monkeypatch.setattr("backend.services.events.handlers._core.insert_outbox_event", insert_mock)

    bus_stub, fake_pool, _ = _build_bus_and_pool()
    h.register_handlers(bus_stub, fake_pool)
    on_client = _get_handler(bus_stub, "client.changed")

    h._recent_events.clear()
    await on_client({
        "client_id": 7,
        "operation": "UPDATE",
        "email": "a@b",
        "changed_fields": ["phone"],  # not sector
    })

    insert_mock.assert_not_called()


@pytest.mark.asyncio
async def test_on_practice_status_changed_completed_writes_outbox(monkeypatch):
    """new_status == 'completed' triggers crm.practice_completed."""
    from backend.services.events import handlers as h

    insert_mock = AsyncMock(return_value=45)
    monkeypatch.setattr("backend.services.events.handlers._core.insert_outbox_event", insert_mock)

    bus_stub, fake_pool, _ = _build_bus_and_pool()
    h.register_handlers(bus_stub, fake_pool)
    on_practice = _get_handler(bus_stub, "practice.status_changed")

    h._recent_events.clear()
    await on_practice({
        "practice_id": 100,
        "client_id": 7,
        "old_status": "in_progress",
        "new_status": "completed",
        "completed_at": "2026-04-14T10:00:00",
    })

    insert_mock.assert_called_once()
    call_kwargs = insert_mock.call_args.kwargs
    assert call_kwargs["event_type"] == "crm.practice_completed"
    assert call_kwargs["payload"]["practice_id"] == 100


@pytest.mark.asyncio
async def test_on_practice_status_changed_created_writes_outbox(monkeypatch):
    """old_status None + new_status created triggers crm.practice_created."""
    from backend.services.events import handlers as h

    insert_mock = AsyncMock(return_value=46)
    monkeypatch.setattr("backend.services.events.handlers._core.insert_outbox_event", insert_mock)

    bus_stub, fake_pool, _ = _build_bus_and_pool()
    h.register_handlers(bus_stub, fake_pool)
    on_practice = _get_handler(bus_stub, "practice.status_changed")

    h._recent_events.clear()
    await on_practice({
        "practice_id": 100,
        "client_id": 7,
        "old_status": None,
        "new_status": "created",
        "practice_type": "VISA",
    })

    insert_mock.assert_called_once()
    call_kwargs = insert_mock.call_args.kwargs
    assert call_kwargs["event_type"] == "crm.practice_created"
    assert call_kwargs["payload"]["practice_type"] == "VISA"


@pytest.mark.asyncio
async def test_on_compliance_alert_critical_within_7d_writes_outbox(monkeypatch):
    """severity=critical AND days_until_expiry <= 7 → outbox write."""
    from backend.services.events import handlers as h

    insert_mock = AsyncMock(return_value=47)
    monkeypatch.setattr("backend.services.events.handlers._core.insert_outbox_event", insert_mock)

    bus_stub, fake_pool, _ = _build_bus_and_pool()
    h.register_handlers(bus_stub, fake_pool)
    on_compliance = _get_handler(bus_stub, "compliance.alert")

    h._recent_events.clear()
    await on_compliance({
        "alert_id": "alert-1",
        "client_id": 7,
        "severity": "critical",
        "alert_type": "visa_expiry",
        "message": "Visa expires soon",
        "document_type": "VITAS",
        "days_until_expiry": 3,
        "expires_at": "2026-04-17",
    })

    insert_mock.assert_called_once()
    call_kwargs = insert_mock.call_args.kwargs
    assert call_kwargs["event_type"] == "compliance.critical_alert"
    assert call_kwargs["payload"]["days_until_expiry"] == 3


@pytest.mark.asyncio
async def test_on_compliance_alert_high_does_not_write(monkeypatch):
    """severity=high (not critical) does NOT trigger outbox."""
    from backend.services.events import handlers as h

    insert_mock = AsyncMock(return_value=48)
    monkeypatch.setattr("backend.services.events.handlers._core.insert_outbox_event", insert_mock)

    bus_stub, fake_pool, _ = _build_bus_and_pool()
    h.register_handlers(bus_stub, fake_pool)
    on_compliance = _get_handler(bus_stub, "compliance.alert")

    h._recent_events.clear()
    await on_compliance({
        "alert_id": "alert-2",
        "client_id": 7,
        "severity": "high",
        "alert_type": "visa_expiry",
        "days_until_expiry": 3,
    })

    insert_mock.assert_not_called()


@pytest.mark.asyncio
async def test_on_compliance_alert_critical_far_future_does_not_write(monkeypatch):
    """severity=critical but days > 7 does NOT trigger outbox (filter)."""
    from backend.services.events import handlers as h

    insert_mock = AsyncMock(return_value=49)
    monkeypatch.setattr("backend.services.events.handlers._core.insert_outbox_event", insert_mock)

    bus_stub, fake_pool, _ = _build_bus_and_pool()
    h.register_handlers(bus_stub, fake_pool)
    on_compliance = _get_handler(bus_stub, "compliance.alert")

    h._recent_events.clear()
    await on_compliance({
        "alert_id": "alert-3",
        "client_id": 7,
        "severity": "critical",
        "alert_type": "visa_expiry",
        "days_until_expiry": 30,
    })

    insert_mock.assert_not_called()


@pytest.mark.asyncio
async def test_outbox_write_failure_does_not_raise(monkeypatch):
    """If insert_outbox_event raises, handler must NOT propagate (defensive)."""
    from backend.services.events import handlers as h

    insert_mock = AsyncMock(side_effect=RuntimeError("DB down"))
    monkeypatch.setattr("backend.services.events.handlers._core.insert_outbox_event", insert_mock)

    bus_stub, fake_pool, _ = _build_bus_and_pool()
    h.register_handlers(bus_stub, fake_pool)
    on_client = _get_handler(bus_stub, "client.changed")

    h._recent_events.clear()
    # Must NOT raise
    await on_client({"client_id": 7, "operation": "INSERT", "email": "x@y"})


@pytest.mark.asyncio
async def test_on_compliance_alert_critical_zero_days_writes_outbox(monkeypatch):
    """severity=critical AND days_until_expiry=0 (expires TODAY) MUST write outbox."""
    from backend.services.events import handlers as h

    insert_mock = AsyncMock(return_value=50)
    monkeypatch.setattr("backend.services.events.handlers._core.insert_outbox_event", insert_mock)

    bus_stub, fake_pool, _ = _build_bus_and_pool()
    h.register_handlers(bus_stub, fake_pool)
    on_compliance = _get_handler(bus_stub, "compliance.alert")

    h._recent_events.clear()
    await on_compliance({
        "alert_id": "alert-zero",
        "client_id": 7,
        "severity": "critical",
        "alert_type": "visa_expiry",
        "days_until_expiry": 0,
    })

    insert_mock.assert_called_once()
    call_kwargs = insert_mock.call_args.kwargs
    assert call_kwargs["event_type"] == "compliance.critical_alert"
    assert call_kwargs["payload"]["days_until_expiry"] == 0


@pytest.mark.asyncio
async def test_on_compliance_alert_critical_no_days_field_does_not_write(monkeypatch):
    """severity=critical but days_until_expiry missing (None) does NOT write."""
    from backend.services.events import handlers as h

    insert_mock = AsyncMock(return_value=51)
    monkeypatch.setattr("backend.services.events.handlers._core.insert_outbox_event", insert_mock)

    bus_stub, fake_pool, _ = _build_bus_and_pool()
    h.register_handlers(bus_stub, fake_pool)
    on_compliance = _get_handler(bus_stub, "compliance.alert")

    h._recent_events.clear()
    await on_compliance({
        "alert_id": "alert-no-days",
        "client_id": 7,
        "severity": "critical",
        "alert_type": "general",
        # NO days_until_expiry
    })

    insert_mock.assert_not_called()
