"""The GARUDA outbox counters, read over HTTP instead of over Telegram.

Every case here is one sentence from the endpoint's own contract, and the
three GUILT cases exist because a probe that has never gone red on a real
defect proves nothing about the day it stays green.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.routers.health as health_module
from backend.app.setup.route_walk import iter_leaf_routes


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(health_module.router)
    application.state = SimpleNamespace()
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _pool() -> object:
    """A pool whose `acquire()` is an async context manager, like asyncpg's."""

    class _Pool:
        @asynccontextmanager
        async def acquire(self):  # noqa: ANN202
            yield object()

    return _Pool()


def _with_counts(counts: dict[str, int]):
    return patch(
        "backend.services.garuda_orders.outbox_consumer.count_undrained",
        AsyncMock(return_value=counts),
    )


@pytest.mark.unit
def test_the_route_exists_where_the_receptor_looks_for_it() -> None:
    paths = {route.path for route in iter_leaf_routes(health_module.router)}
    assert "/health/garuda-outbox" in paths


@pytest.mark.unit
def test_a_clean_queue_is_not_degraded(app: FastAPI, client: TestClient) -> None:
    app.state.db_pool = _pool()
    with _with_counts({"undispatched": 0, "exhausted": 0, "older_than_1h": 0, "older_than_24h": 0}):
        body = client.get("/health/garuda-outbox").json()
    assert body["status"] == "ok"
    assert body["degraded"] is False
    assert body["counts"]["exhausted"] == 0


@pytest.mark.unit
def test_GUILT_one_exhausted_row_is_degraded(app: FastAPI, client: TestClient) -> None:
    """The shape that cost a day on 2026-09-20: row 36, five attempts, unseen."""
    app.state.db_pool = _pool()
    with _with_counts({"undispatched": 1, "exhausted": 1, "older_than_1h": 1, "older_than_24h": 0}):
        body = client.get("/health/garuda-outbox").json()
    assert body["degraded"] is True


@pytest.mark.unit
def test_GUILT_a_row_stuck_a_day_is_degraded_before_it_exhausts(
    app: FastAPI, client: TestClient
) -> None:
    app.state.db_pool = _pool()
    with _with_counts({"undispatched": 2, "exhausted": 0, "older_than_1h": 2, "older_than_24h": 2}):
        body = client.get("/health/garuda-outbox").json()
    assert body["degraded"] is True


@pytest.mark.unit
def test_GUILT_no_pool_reads_unknown_not_healthy(app: FastAPI, client: TestClient) -> None:
    """"I could not look" must never be spelled like "nothing is wrong"."""
    body = client.get("/health/garuda-outbox").json()
    assert body["status"] == "unknown"
    assert body["degraded"] is None


@pytest.mark.unit
def test_a_failing_query_answers_unknown_and_names_only_the_exception_type(
    app: FastAPI, client: TestClient
) -> None:
    app.state.db_pool = _pool()
    with patch(
        "backend.services.garuda_orders.outbox_consumer.count_undrained",
        AsyncMock(side_effect=RuntimeError("connection string root:hunter2@db")),
    ):
        body = client.get("/health/garuda-outbox").json()
    assert body["status"] == "unknown"
    assert body["error"] == "RuntimeError"
    assert "hunter2" not in str(body)


@pytest.mark.unit
def test_the_public_payload_carries_counts_only(app: FastAPI, client: TestClient) -> None:
    """Aggregate only: no id, no job_type, nothing that narrates which job fails."""
    app.state.db_pool = _pool()
    with _with_counts({"undispatched": 3, "exhausted": 1, "older_than_1h": 3, "older_than_24h": 0}):
        body = client.get("/health/garuda-outbox").json()
    assert set(body["counts"]) == {"undispatched", "exhausted", "older_than_1h", "older_than_24h"}
    rendered = str(body).lower()
    for leak in ("job_type", "staff_page", "payload", "recipient", "email"):
        assert leak not in rendered
