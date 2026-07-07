import pytest

from backend.services.crm import assignment as assignment_module
from backend.services.crm.lead_assignment_agent import (
    assign_lead,
    check_duplicates,
    send_telegram_notification,
    trigger_lead_assignment,
)


class FakeAcquire:
    def __init__(self, conn: object) -> None:
        self.conn = conn

    async def __aenter__(self) -> object:
        return self.conn

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class FakePool:
    def __init__(self, conn: object) -> None:
        self.conn = conn

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.conn)


class FakeConn:
    def __init__(self, fetchrows: list[dict | None] | None = None) -> None:
        self.fetchrows = fetchrows or []
        self.executed: list[tuple[str, tuple[object, ...]]] = []

    async def fetchrow(self, query: str, *args: object) -> dict | None:
        self.last_fetchrow = (query, args)
        return self.fetchrows.pop(0) if self.fetchrows else None

    async def execute(self, query: str, *args: object) -> str:
        self.executed.append((query, args))
        return "UPDATE 1"


class FakeTelegramService:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.messages: list[dict[str, object]] = []

    async def send_message(self, **kwargs: object) -> None:
        if self.fail:
            raise RuntimeError("telegram down")
        self.messages.append(kwargs)


def base_state() -> dict:
    return {
        "client_id": 10,
        "client_data": {
            "email": "new@example.com",
            "phone": "+6281234567890",
            "full_name": "New Client",
            "practice_type_code": "kitas",
        },
        "is_duplicate": False,
        "matched_client_id": None,
        "assigned_lead": None,
        "assigned_lead_name": None,
        "assignment_reason": "",
        "telegram_chat_id": None,
        "notification_sent": False,
        "success": True,
        "errors": [],
    }


@pytest.mark.asyncio
async def test_check_duplicates_marks_email_match_and_reuses_assignment() -> None:
    conn = FakeConn(fetchrows=[{"id": 7, "assigned_to": "lead@example.com"}])
    state = base_state()

    result = await check_duplicates(state, FakePool(conn))

    assert result["is_duplicate"] is True
    assert result["matched_client_id"] == 7
    assert result["assigned_lead"] == "lead@example.com"


@pytest.mark.asyncio
async def test_assign_lead_keeps_existing_duplicate_assignment() -> None:
    state = base_state()
    state.update(
        {
            "is_duplicate": True,
            "matched_client_id": 7,
            "assigned_lead": "lead@example.com",
        }
    )

    result = await assign_lead(state, FakePool(FakeConn()))

    assert result["assigned_lead"] == "lead@example.com"
    assert "Duplicate client" in result["assignment_reason"]


@pytest.mark.asyncio
async def test_assign_lead_updates_client_with_department_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_invalidate_crm_stats() -> None:
        return None

    monkeypatch.setattr(assignment_module, "invalidate_crm_stats", fake_invalidate_crm_stats)
    conn = FakeConn(
        fetchrows=[
            {
                "email": "consultant@example.com",
                "full_name": "Consultant Name",
                "department": "setup",
                "active_practices": 2,
            }
        ]
    )

    result = await assign_lead(base_state(), FakePool(conn))

    assert result["assigned_lead"] == "consultant@example.com"
    assert result["assigned_lead_name"] == "Consultant Name"
    assert "Department: setup" in result["assignment_reason"]
    assert conn.executed[0][1] == ("consultant@example.com", 10)


@pytest.mark.asyncio
async def test_send_telegram_notification_records_missing_chat_id() -> None:
    state = base_state()
    state["assigned_lead"] = "lead@example.com"
    conn = FakeConn(fetchrows=[None])

    result = await send_telegram_notification(state, FakePool(conn), FakeTelegramService())

    assert result["notification_sent"] is False
    assert "No Telegram chat_id" in result["errors"][0]


@pytest.mark.asyncio
async def test_send_telegram_notification_sends_markdown_message() -> None:
    state = base_state()
    state["assigned_lead"] = "lead@example.com"
    state["assignment_reason"] = "Least workload"
    conn = FakeConn(fetchrows=[{"telegram_chat_id": 12345, "full_name": "Lead Name"}])
    telegram = FakeTelegramService()

    result = await send_telegram_notification(state, FakePool(conn), telegram)

    assert result["notification_sent"] is True
    assert result["telegram_chat_id"] == 12345
    assert telegram.messages[0]["chat_id"] == 12345
    assert "New Client" in telegram.messages[0]["text"]
    assert telegram.messages[0]["parse_mode"] == "Markdown"


@pytest.mark.asyncio
async def test_trigger_lead_assignment_returns_failure_state_when_workflow_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenWorkflow:
        async def ainvoke(self, state: dict) -> dict:
            raise RuntimeError("workflow failed")

    monkeypatch.setattr(
        assignment_module,
        "create_lead_assignment_workflow",
        lambda db_pool, telegram_service: BrokenWorkflow(),
    )

    result = await trigger_lead_assignment(
        client_id=10,
        client_data={"full_name": "Client"},
        db_pool=object(),
        telegram_service=object(),
    )

    assert result["success"] is False
    assert result["assigned_lead"] is None
    assert result["errors"] == ["workflow failed"]
