import json

import pytest

from backend.services.monitoring.activity_logger import ActivityLogger


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
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.executed: list[tuple[str, tuple[object, ...]]] = []

    async def execute(self, query: str, *args: object) -> str:
        if self.fail:
            raise RuntimeError("db down")
        self.executed.append((query, args))
        return "INSERT 0 1"


def test_sanitize_data_redacts_sensitive_values_and_truncates_large_payloads() -> None:
    logger = ActivityLogger()

    sanitized = logger._sanitize_data(
        {
            "api_key": "secret",
            "nested": {"authorization": "Bearer token", "safe": "value"},
            "items": [{"token": "x"}] * 120,
            "text": "x" * 1200,
        },
        max_length=100,
    )

    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["nested"]["authorization"] == "[REDACTED]"
    assert sanitized["nested"]["safe"] == "value"
    assert len(sanitized["items"]) == 100
    assert sanitized["text"].endswith("[truncated]")


@pytest.mark.asyncio
async def test_initialize_sets_pool_and_allows_activity_logging() -> None:
    conn = FakeConn()
    logger = ActivityLogger()

    await logger.initialize(FakePool(conn))
    result = await logger.log_activity(
        user_email="operator@example.com",
        action_type="client_created",
        resource_type="client",
        resource_id="42",
        description="Created client",
        details={"password": "hidden", "safe": "visible"},
    )

    assert result is True
    assert logger._initialized is True
    saved_details = json.loads(conn.executed[0][1][5])
    assert saved_details == {"password": "[REDACTED]", "safe": "visible"}


@pytest.mark.asyncio
async def test_log_methods_return_false_when_uninitialized_or_db_fails() -> None:
    logger = ActivityLogger()

    assert not await logger.log_activity("user@example.com", "action")
    assert not await logger.log_api_call("GET", "/health", 200, 10)

    await logger.initialize(FakePool(FakeConn(fail=True)))

    assert not await logger.log_interaction("user@example.com", "chat", "outbound")


@pytest.mark.asyncio
async def test_log_interaction_stores_preview_and_sanitized_metadata() -> None:
    conn = FakeConn()
    logger = ActivityLogger()
    await logger.initialize(FakePool(conn))

    result = await logger.log_interaction(
        user_email="team@example.com",
        interaction_type="email",
        direction="outbound",
        client_email="client@example.com",
        message_content="a" * 600,
        attachments=[{"token": "secret", "name": "file.pdf"}],
        metadata={"jwt": "hidden", "topic": "visa"},
        conversation_id=1,
        practice_id=2,
        response_time_seconds=30,
    )

    assert result is True
    args = conn.executed[0][1]
    assert args[7] == "a" * 500
    assert json.loads(args[8]) == [{"token": "[REDACTED]", "name": "file.pdf"}]
    assert json.loads(args[9]) == {"jwt": "[REDACTED]", "topic": "visa"}


@pytest.mark.asyncio
async def test_log_api_call_sanitizes_query_request_and_response_payloads() -> None:
    conn = FakeConn()
    logger = ActivityLogger()
    await logger.initialize(FakePool(conn))

    result = await logger.log_api_call(
        method="POST",
        endpoint="/api/clients",
        response_status=201,
        response_time_ms=45,
        query_params={"token": "hidden"},
        request_body={"password": "hidden", "name": "Client"},
        response_body={"secret": "hidden"},
    )

    assert result is True
    args = conn.executed[0][1]
    assert json.loads(args[3]) == {"token": "[REDACTED]"}
    assert json.loads(args[4]) == {"password": "[REDACTED]", "name": "Client"}
    assert json.loads(args[6]) == {"secret": "[REDACTED]"}


@pytest.mark.asyncio
async def test_log_session_writes_login_logout_and_activity_events() -> None:
    conn = FakeConn()
    logger = ActivityLogger()
    await logger.initialize(FakePool(conn))

    assert await logger.log_session("s-1", "user@example.com", "login")
    assert await logger.log_session("s-1", "user@example.com", "activity")
    assert await logger.log_session("s-1", "user@example.com", "logout")

    assert len(conn.executed) == 3
    assert "INSERT INTO session_tracking" in conn.executed[0][0]
    assert "actions_count = actions_count + 1" in conn.executed[1][0]
    assert "SET logout_at = NOW()" in conn.executed[2][0]
