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
async def test_log_api_call_failure_returns_false_and_logs_exception_type(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = ActivityLogger()
    await logger.initialize(FakePool(FakeConn(fail=True)))

    with caplog.at_level("WARNING", logger="backend.services.monitoring.activity_logger"):
        result = await logger.log_api_call("GET", "/api/clients/42", 200, 10)

    assert result is False
    assert len(caplog.records) == 1
    assert "RuntimeError" in caplog.records[0].message


@pytest.mark.asyncio
async def test_log_api_call_success_emits_no_failure_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    conn = FakeConn()
    logger = ActivityLogger()
    await logger.initialize(FakePool(conn))

    with caplog.at_level("WARNING", logger="backend.services.monitoring.activity_logger"):
        result = await logger.log_api_call("GET", "/api/clients/42", 500, 10)

    assert result is True
    assert caplog.records == []


@pytest.mark.asyncio
async def test_log_api_call_failure_is_damped_under_repeated_failures(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = ActivityLogger()
    await logger.initialize(FakePool(FakeConn(fail=True)))

    with caplog.at_level("WARNING", logger="backend.services.monitoring.activity_logger"):
        for _ in range(50):
            assert await logger.log_api_call("GET", "/health", 200, 10) is False

    # Only the first occurrence is emitted; the rest are suppressed within
    # the damping interval (time-based reset hasn't elapsed, count-based
    # reset needs 500 occurrences).
    assert len(caplog.records) == 1
    assert "total_failures=1" in caplog.records[0].message
    assert "suppressed_since_last=0" in caplog.records[0].message

    # Force a second emission via the count-based threshold and check the
    # suppressed counter is reported.
    caplog.clear()
    logger._api_log_failure_suppressed = 500
    with caplog.at_level("WARNING", logger="backend.services.monitoring.activity_logger"):
        assert await logger.log_api_call("GET", "/health", 200, 10) is False

    assert len(caplog.records) == 1
    assert "total_failures=51" in caplog.records[0].message
    assert "suppressed_since_last=500" in caplog.records[0].message


@pytest.mark.asyncio
async def test_log_api_call_failure_never_leaks_pii_into_the_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = ActivityLogger()
    await logger.initialize(FakePool(FakeConn(fail=True)))

    secret_ip = "203.0.113.77"
    secret_email = "client-42@example.com"
    secret_agent = "SuperSecretBrowser/9.9"
    secret_query = {"token": "abc123-should-never-appear"}

    with caplog.at_level("WARNING", logger="backend.services.monitoring.activity_logger"):
        result = await logger.log_api_call(
            method="GET",
            endpoint="/api/clients/987654",
            response_status=200,
            response_time_ms=10,
            user_email=secret_email,
            ip_address=secret_ip,
            user_agent=secret_agent,
            query_params=secret_query,
        )

    assert result is False
    logged_text = " ".join(r.message for r in caplog.records)
    assert secret_ip not in logged_text
    assert secret_email not in logged_text
    assert secret_agent not in logged_text
    assert "abc123-should-never-appear" not in logged_text
    # The numeric client ID in the endpoint must be masked, not passed through.
    assert "987654" not in logged_text
    assert "/api/clients/:id" in logged_text


@pytest.mark.asyncio
async def test_log_api_call_failure_never_propagates_to_the_caller() -> None:
    logger = ActivityLogger()
    await logger.initialize(FakePool(FakeConn(fail=True)))

    # Must not raise — a broken audit-log write must never break the
    # request it is trying to observe.
    result = await logger.log_api_call("POST", "/api/clients", 201, 10)
    assert result is False


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
