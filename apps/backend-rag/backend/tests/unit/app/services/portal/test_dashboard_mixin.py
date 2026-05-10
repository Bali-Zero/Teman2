"""Unit tests for PortalService dashboard mixin branches."""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.portal.portal_service import PortalService


class _AsyncCtx:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_args: object) -> None:
        return None


class UndefinedColumnError(Exception):
    sqlstate = "42703"


def _service_with_conn() -> tuple[PortalService, AsyncMock]:
    conn = AsyncMock()
    conn.transaction = MagicMock(return_value=_AsyncCtx())

    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    return PortalService(pool), conn


def _ctx(client_id: int = 1) -> dict[str, Any]:
    return {"client_id": client_id, "email": f"client-{client_id}@example.com"}


@pytest.mark.asyncio
async def test_get_dashboard_handles_optional_query_failures() -> None:
    service, conn = _service_with_conn()
    conn.fetchrow.side_effect = [
        {"id": 1, "full_name": "Client One", "email": "client@example.com"},
        RuntimeError("visa table unavailable"),
        RuntimeError("documents table unavailable"),
    ]
    conn.fetch.side_effect = [
        RuntimeError("companies table unavailable"),
        RuntimeError("practices table unavailable"),
    ]
    conn.fetchval.side_effect = RuntimeError("messages table unavailable")

    result = await service.get_dashboard(1, current_user=_ctx())

    assert result["visa"]["status"] == "none"
    assert result["company"] == {
        "status": "none",
        "primaryCompanyName": None,
        "totalCompanies": 0,
    }
    assert result["documents"] == {"total": 0, "pending": 0}
    assert result["messages"] == {"unread": 0}
    assert result["actions"] == []


def test_build_visa_dashboard_data_completed_without_expiry_is_active() -> None:
    service, _conn = _service_with_conn()

    result = service._build_visa_dashboard_data({
        "status": "completed",
        "expiry_date": None,
        "code": None,
        "name": "KITAS",
    })

    assert result["status"] == "active"
    assert result["type"] == "KITAS"
    assert result["expiryDate"] is None
    assert result["daysRemaining"] is None


def test_build_visa_dashboard_data_unknown_status_is_pending() -> None:
    service, _conn = _service_with_conn()

    result = service._build_visa_dashboard_data({
        "status": "blocked",
        "expiry_date": datetime.now(timezone.utc) + timedelta(days=200),
        "code": "E33",
        "name": "KITAS",
    })

    assert result["status"] == "pending"


@pytest.mark.asyncio
async def test_get_visa_status_shapes_current_history_and_documents() -> None:
    service, conn = _service_with_conn()
    now = datetime(2026, 5, 10, tzinfo=timezone.utc)
    future = now + timedelta(days=180)
    past = now - timedelta(days=120)
    conn.fetchrow.side_effect = [
        {"id": 1},
        {
            "id": 7,
            "status": "completed",
            "start_date": past,
            "completion_date": past,
            "expiry_date": future,
            "notes": "Current visa",
            "code": "E33",
            "type_name": "Investor KITAS",
        },
    ]
    conn.fetch.side_effect = [
        [
            {
                "id": 7,
                "code": "E33",
                "name": "Investor KITAS",
                "start_date": past,
                "completion_date": past,
                "expiry_date": future,
                "status": "completed",
            },
            {
                "id": 8,
                "code": None,
                "name": "Old Visa",
                "start_date": None,
                "completion_date": past,
                "expiry_date": None,
                "status": "cancelled",
            },
        ],
        [
            {
                "id": 20,
                "document_type": "passport",
                "file_name": "passport.pdf",
                "status": "verified",
                "expiry_date": future,
                "file_url": None,
                "file_id": "drive_doc_20",
                "file_size_kb": 128,
                "created_at": past,
            },
            {
                "id": 21,
                "document_type": "unknown",
                "file_name": "note.txt",
                "status": "unknown",
                "expiry_date": None,
                "file_url": None,
                "file_id": None,
                "file_size_kb": None,
                "created_at": None,
            },
        ],
    ]

    result = await service.get_visa_status(1, current_user=_ctx())

    assert result["current"]["type"] == "E33 - Investor KITAS"
    assert result["current"]["status"] in {"active", "expired"}
    assert result["current"]["permitNumber"] == "KITAS-000007"
    assert result["history"][0]["status"] == "completed"
    assert result["history"][1]["type"] == "Old Visa"
    assert result["documents"][0]["category"] == "Identity"
    assert result["documents"][0]["downloadUrl"] == "/api/portal/documents/20/download"
    assert result["documents"][1]["category"] == "Other"
    assert result["documents"][1]["status"] == "pending"
    assert result["documents"][1]["downloadUrl"] is None


@pytest.mark.asyncio
async def test_get_visa_status_falls_back_when_client_visible_column_missing() -> None:
    service, conn = _service_with_conn()
    now = datetime(2026, 5, 10, tzinfo=timezone.utc)
    conn.fetchrow.side_effect = [
        {"id": 1},
        UndefinedColumnError("client_visible missing"),
        None,
    ]
    conn.fetch.side_effect = [
        UndefinedColumnError("client_visible missing"),
        [
            {
                "id": 9,
                "code": "B211",
                "name": "Visit Visa",
                "start_date": now,
                "completion_date": None,
                "expiry_date": None,
                "status": "in_progress",
            },
        ],
        [],
    ]

    result = await service.get_visa_status(1, current_user=_ctx())

    assert result["current"] is None
    assert result["history"] == [
        {
            "id": "9",
            "type": "B211 - Visit Visa",
            "period": "May 2026",
            "status": "expired",
        },
    ]
    assert result["documents"] == []


@pytest.mark.asyncio
async def test_get_visa_status_raises_on_unexpected_current_query_error() -> None:
    service, conn = _service_with_conn()
    conn.fetchrow.side_effect = [
        {"id": 1},
        RuntimeError("database unavailable"),
    ]

    with pytest.raises(RuntimeError, match="database unavailable"):
        await service.get_visa_status(1, current_user=_ctx())


@pytest.mark.asyncio
async def test_get_visa_status_raises_on_unexpected_history_query_error() -> None:
    service, conn = _service_with_conn()
    conn.fetchrow.side_effect = [
        {"id": 1},
        None,
    ]
    conn.fetch.side_effect = RuntimeError("history query failed")

    with pytest.raises(RuntimeError, match="history query failed"):
        await service.get_visa_status(1, current_user=_ctx())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expiry_delta", "expected_status"),
    [
        ("completed", -1, "expired"),
        ("in_progress", 60, "pending"),
    ],
)
async def test_get_visa_status_current_status_edges(
    status: str,
    expiry_delta: int,
    expected_status: str,
) -> None:
    service, conn = _service_with_conn()
    now = datetime.now(timezone.utc)
    conn.fetchrow.side_effect = [
        {"id": 1},
        {
            "id": 7,
            "status": status,
            "start_date": now - timedelta(days=30),
            "completion_date": now - timedelta(days=20),
            "expiry_date": now + timedelta(days=expiry_delta),
            "notes": None,
            "code": None,
            "type_name": "KITAS",
        },
    ]
    conn.fetch.side_effect = [[], []]

    result = await service.get_visa_status(1, current_user=_ctx())

    assert result["current"]["status"] == expected_status


@pytest.mark.asyncio
async def test_get_company_detail_shapes_payload() -> None:
    service, conn = _service_with_conn()
    created = datetime(2026, 1, 2, tzinfo=timezone.utc)
    expiry = datetime(2027, 1, 2, tzinfo=timezone.utc)
    conn.fetchrow.side_effect = [
        {"role": "director", "is_primary": True, "ownership_percentage": 75},
        {
            "id": 10,
            "company_name": "PT Test",
            "company_type": "PMA",
            "nib": "123",
            "npwp_company": "01.234",
            "kbli_code": "62010",
            "status": "active",
            "registered_address": "Jl Test",
            "company_email": "pt@example.com",
            "company_phone": "+62",
            "akta_pendirian_no": "AKTA-1",
            "akta_pendirian_date": created,
            "sk_menhumkam_no": "SK-1",
            "custom_fields": '{"tax_office": "KPP", "company_status": "valid", "investment_type": "foreign"}',
        },
    ]
    conn.fetch.side_effect = [
        [
            {
                "id": 1,
                "code": "NIB",
                "name": "Business License",
                "status": "completed",
                "expiry_date": expiry,
                "completion_date": created,
            },
        ],
        [
            {
                "id": 30,
                "document_type": "nib",
                "file_name": "nib.pdf",
                "status": "verified",
                "file_url": None,
                "file_id": "drive_doc_30",
            },
        ],
        [
            {"full_name": "Alice", "role": "director", "ownership_percentage": 75},
            {"full_name": "Bob", "role": "shareholder", "ownership_percentage": 25},
        ],
    ]

    result = await service.get_company_detail(1, 10, current_user=_ctx())

    assert result["id"] == 10
    assert result["name"] == "PT Test"
    assert result["tax_office"] == "KPP"
    assert result["ownership"] == {"role": "director", "is_primary": True, "pct": 75.0}
    assert result["licenses"][0]["expiry_date"] == expiry.isoformat()
    assert result["documents"][0]["downloadable"] is True
    assert result["directors"] == ["Alice"]
    assert result["shareholders"] == [
        {"name": "Alice", "pct": 75.0},
        {"name": "Bob", "pct": 25.0},
    ]


@pytest.mark.asyncio
async def test_get_company_detail_falls_back_for_missing_client_visible_column() -> None:
    service, conn = _service_with_conn()
    conn.fetchrow.side_effect = [
        {"role": "director", "is_primary": False, "ownership_percentage": None},
        {
            "id": 10,
            "company_name": "PT Test",
            "company_type": "PMA",
            "nib": None,
            "npwp_company": None,
            "kbli_code": None,
            "status": "active",
            "registered_address": None,
            "company_email": None,
            "company_phone": None,
            "akta_pendirian_no": None,
            "akta_pendirian_date": None,
            "sk_menhumkam_no": None,
            "custom_fields": "{not json",
        },
    ]
    conn.fetch.side_effect = [
        UndefinedColumnError("client_visible missing"),
        [
            {
                "id": 1,
                "code": None,
                "name": "License",
                "status": "pending",
                "expiry_date": None,
                "completion_date": None,
            },
        ],
        [],
        [],
    ]

    result = await service.get_company_detail(1, 10, current_user=_ctx())

    assert result["tax_office"] is None
    assert result["ownership"] == {"role": "director", "is_primary": False, "pct": None}
    assert result["licenses"] == [
        {
            "id": 1,
            "code": None,
            "name": "License",
            "status": "pending",
            "expiry_date": None,
        },
    ]


@pytest.mark.asyncio
async def test_get_company_detail_sanitizes_non_dict_custom_fields() -> None:
    service, conn = _service_with_conn()
    conn.fetchrow.side_effect = [
        {"role": "shareholder", "is_primary": False, "ownership_percentage": None},
        {
            "id": 10,
            "company_name": "PT Test",
            "company_type": "PMA",
            "nib": None,
            "npwp_company": None,
            "kbli_code": None,
            "status": "active",
            "registered_address": None,
            "company_email": None,
            "company_phone": None,
            "akta_pendirian_no": None,
            "akta_pendirian_date": None,
            "sk_menhumkam_no": None,
            "custom_fields": ["not", "a", "dict"],
        },
    ]
    conn.fetch.side_effect = [[], [], []]

    result = await service.get_company_detail(1, 10, current_user=_ctx())

    assert result["tax_office"] is None
    assert result["company_status"] is None
    assert result["investment_type"] is None


@pytest.mark.asyncio
async def test_get_company_detail_raises_on_unexpected_practice_query_error() -> None:
    service, conn = _service_with_conn()
    conn.fetchrow.side_effect = [
        {"role": "director", "is_primary": True, "ownership_percentage": 50},
        {"id": 10, "custom_fields": {}, "company_name": "PT Test"},
    ]
    conn.fetch.side_effect = RuntimeError("practices unavailable")

    with pytest.raises(RuntimeError, match="practices unavailable"):
        await service.get_company_detail(1, 10, current_user=_ctx())


@pytest.mark.asyncio
async def test_set_primary_company_success_and_not_found() -> None:
    service, conn = _service_with_conn()
    conn.execute.side_effect = ["UPDATE 1", "UPDATE 1"]

    result = await service.set_primary_company(1, 10, current_user=_ctx())

    assert result == {"success": True, "primary_company_id": 10}
    assert conn.execute.await_count == 2

    service, conn = _service_with_conn()
    conn.execute.side_effect = ["UPDATE 1", "UPDATE 0"]

    with pytest.raises(ValueError, match="Company not found"):
        await service.set_primary_company(1, 99, current_user=_ctx())


@pytest.mark.asyncio
async def test_get_tax_overview_shapes_obligations_and_history() -> None:
    service, conn = _service_with_conn()
    created = datetime(2026, 4, 1, tzinfo=timezone.utc)
    conn.fetch.return_value = [
        {
            "id": 1,
            "code": "SPT",
            "name": "Annual Tax Filing",
            "status": "completed",
            "expiry_date": None,
            "created_at": created,
        },
    ]

    result = await service.get_tax_overview(1, current_user=_ctx())

    assert result["summary"]["status"] in {"compliant", "attention", "overdue"}
    assert result["summary"]["totalDue"] == 0
    assert len(result["obligations"]) == 3
    assert result["history"] == [
        {
            "id": "1",
            "name": "Annual Tax Filing",
            "period": "Apr 2026",
            "filedDate": created.isoformat(),
            "amount": 0,
        },
    ]


@pytest.mark.asyncio
async def test_get_tax_overview_handles_query_failure_and_overdue_deadline() -> None:
    service, conn = _service_with_conn()
    conn.fetch.side_effect = RuntimeError("tax practices unavailable")
    service._get_standard_tax_deadlines = MagicMock(return_value=[
        {
            "type": "PPh",
            "period": "May 2026",
            "due_date": "2026-05-01T00:00:00+00:00",
            "days_until": -3,
            "urgency": "urgent",
        },
    ])

    result = await service.get_tax_overview(1, current_user=_ctx())

    assert result["summary"]["status"] == "overdue"
    assert result["history"] == []


@pytest.mark.asyncio
async def test_get_tax_overview_marks_near_deadline_attention() -> None:
    service, conn = _service_with_conn()
    conn.fetch.return_value = []
    service._get_standard_tax_deadlines = MagicMock(return_value=[
        {
            "type": "PPh",
            "period": "May 2026",
            "due_date": "2026-05-17T00:00:00+00:00",
            "days_until": 7,
            "urgency": "urgent",
        },
    ])

    result = await service.get_tax_overview(1, current_user=_ctx())

    assert result["summary"]["status"] == "attention"


def test_get_standard_tax_deadlines_uses_december_vat_deadline() -> None:
    service, _conn = _service_with_conn()

    deadlines = service._get_standard_tax_deadlines(datetime(2026, 11, 20, tzinfo=timezone.utc))

    ppn = next(deadline for deadline in deadlines if deadline["type"] == "PPN (VAT)")
    assert ppn["due_date"].startswith("2026-12-31")


@pytest.mark.asyncio
async def test_get_timeline_merges_persisted_and_derived_entries() -> None:
    service, conn = _service_with_conn()
    now = datetime.now(timezone.utc)
    conn.fetch.side_effect = [
        [
            {
                "id": 1,
                "practice_id": 10,
                "event_type": "document_received",
                "title": "Document received",
                "description": "Passport uploaded",
                "event_date": now,
            },
            {
                "id": 2,
                "practice_id": None,
                "event_type": "payment_due",
                "title": "Payment due",
                "description": "Invoice due",
                "event_date": now + timedelta(days=1),
            },
            {
                "id": 3,
                "practice_id": 11,
                "event_type": "status_change",
                "title": "Status changed",
                "description": "Practice updated",
                "event_date": now - timedelta(days=1),
            },
        ],
        [
            {
                "id": 4,
                "subject": None,
                "content": "A" * 120,
                "direction": "team_to_client",
                "created_at": now,
                "read_at": None,
            },
        ],
        [
            {
                "id": 5,
                "document_type": "passport",
                "file_name": "passport.pdf",
                "status": "received",
                "created_at": now,
            },
        ],
        [
            {
                "id": 6,
                "name": "KITAS",
                "category": "visa",
                "status": "in_progress",
                "updated_at": None,
            },
        ],
    ]

    result = await service.get_timeline(1, limit=20, current_user=_ctx())

    ids = {entry["id"] for entry in result["entries"]}
    assert {"event-1", "event-2", "event-3", "msg-4", "doc-5", "practice-6"}.issubset(ids)
    message = next(entry for entry in result["entries"] if entry["id"] == "msg-4")
    assert message["title"] == "New Message"
    assert message["description"].endswith("...")
    assert message["unread"] is True
    practice = next(entry for entry in result["entries"] if entry["id"] == "practice-6")
    assert practice["entity"] == {"practiceId": 6, "practiceCategory": "visa"}


@pytest.mark.asyncio
async def test_get_timeline_continues_when_optional_sources_fail() -> None:
    service, conn = _service_with_conn()
    conn.fetch.side_effect = [
        RuntimeError("timeline unavailable"),
        RuntimeError("messages unavailable"),
        RuntimeError("documents unavailable"),
        RuntimeError("practices unavailable"),
    ]

    result = await service.get_timeline(1, limit=10, current_user=_ctx())

    assert result["scope"] == "portal"
    assert result["entries"]
    assert all(entry["type"] == "deadline" for entry in result["entries"])
