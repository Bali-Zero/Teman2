"""Tests for the WA broker router (/api/wa-broker/claim, /api/wa-broker/complete),
BOT-V4 S2, #4333.

Auth pattern mirrors test_wa_inbox_auth.py: a bare FastAPI app mounts the
router, get_database_pool is overridden with a mock pool, and
settings.wa_broker_key is monkeypatched per test. The dependency reads
settings at call time, so patching the live settings object is enough.

Unlike the auth suite, most tests here also monkeypatch the service-layer
functions (`wa_broker.claim_job` / `wa_broker.complete_job` as imported into
the router module) so the router's own logic — response mapping, the 422
XOR validation, the CompleteStatus -> HTTP status table, and the in-process
rate limiter — is exercised without any real SQL.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.deps.database import get_database_pool
from backend.app.routers import wa_broker as wa_broker_router
from backend.services.integrations.wa_broker import CompleteStatus

BROKER_KEY = "wa-broker-secret-test-key-0001"


@pytest.fixture(autouse=True)
def _reset_rate_limit_window():
    """Module-level rate-limit globals must not leak state between tests
    (order-independence)."""
    wa_broker_router._rate_window_start = 0.0
    wa_broker_router._rate_window_count = 0
    yield
    wa_broker_router._rate_window_start = 0.0
    wa_broker_router._rate_window_count = 0


@pytest.fixture
def mock_db_pool() -> MagicMock:
    pool = MagicMock()
    conn = AsyncMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acquire_cm)
    pool._mock_conn = conn
    return pool


@pytest.fixture
def client(mock_db_pool: MagicMock):
    app = FastAPI()
    app.include_router(wa_broker_router.router)
    app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
    return TestClient(app)


@pytest.fixture
def configured_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "wa_broker_key", BROKER_KEY)
    yield BROKER_KEY


def _complete_body(**overrides: object) -> dict:
    body: dict = {
        "job_id": str(uuid.uuid4()),
        "fence_token": str(uuid.uuid4()),
        "completion_key": "completion-key-00001",
        "result_text": "the generated reply",
    }
    body.update(overrides)
    return body


# ── auth ─────────────────────────────────────────────────────────────────


def test_claim_rejects_without_key(client: TestClient, configured_key: str) -> None:
    resp = client.post("/api/wa-broker/claim", json={})
    assert resp.status_code == 401


def test_claim_rejects_wrong_key(client: TestClient, configured_key: str) -> None:
    resp = client.post(
        "/api/wa-broker/claim", json={}, headers={"X-API-Key": "some-other-admin-secret"}
    )
    assert resp.status_code == 401


def test_rejects_when_server_key_unconfigured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If wa_broker_key is None server-side, every request is denied —
    even one that presents a plausible-looking key."""
    monkeypatch.setattr(settings, "wa_broker_key", None)
    resp = client.post(
        "/api/wa-broker/claim", json={}, headers={"X-API-Key": BROKER_KEY}
    )
    assert resp.status_code == 401


def test_claim_accepts_exact_key_with_no_job_available(
    client: TestClient, configured_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(wa_broker_router.wa_broker, "claim_job", AsyncMock(return_value=None))

    resp = client.post(
        "/api/wa-broker/claim", json={}, headers={"X-API-Key": configured_key}
    )

    assert resp.status_code == 200
    assert resp.json() == {
        "job_id": None,
        "fence_token": None,
        "package": None,
        "package_hash": None,
        "deadline_at": None,
        "server_now": None,
    }


def test_complete_also_gated_by_the_same_key(
    client: TestClient, configured_key: str
) -> None:
    """Mutating route must enforce the same scoped key as /claim."""
    resp = client.post("/api/wa-broker/complete", json=_complete_body())
    assert resp.status_code == 401


# ── claim ────────────────────────────────────────────────────────────────


def test_claim_returns_leased_job_with_isoformat_clocks(
    client: TestClient, configured_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = uuid.uuid4()
    fence_token = uuid.uuid4()
    deadline_at = datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)
    server_now = datetime(2026, 8, 19, 11, 59, 50, tzinfo=timezone.utc)
    fake_row = {
        "job_id": job_id,
        "fence_token": fence_token,
        "package": '{"messages": []}',
        "package_hash": "hash-abc123",
        "deadline_at": deadline_at,
        "server_now": server_now,
    }
    monkeypatch.setattr(
        wa_broker_router.wa_broker, "claim_job", AsyncMock(return_value=fake_row)
    )

    resp = client.post(
        "/api/wa-broker/claim",
        json={"in_flight": 1, "last_exec_ms": 4200},
        headers={"X-API-Key": configured_key},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"] == str(job_id)
    assert body["fence_token"] == str(fence_token)
    assert body["package"] == '{"messages": []}'
    assert body["package_hash"] == "hash-abc123"
    assert body["deadline_at"] == deadline_at.isoformat()
    assert body["server_now"] == server_now.isoformat()


# ── complete ─────────────────────────────────────────────────────────────


def test_complete_rejects_both_result_text_and_error_class(
    client: TestClient, configured_key: str
) -> None:
    body = _complete_body(error_class="codex_timeout")  # result_text also present
    resp = client.post(
        "/api/wa-broker/complete", json=body, headers={"X-API-Key": configured_key}
    )
    assert resp.status_code == 422


def test_complete_rejects_neither_result_text_nor_error_class(
    client: TestClient, configured_key: str
) -> None:
    body = _complete_body(result_text=None)  # no error_class either
    resp = client.post(
        "/api/wa-broker/complete", json=body, headers={"X-API-Key": configured_key}
    )
    assert resp.status_code == 422


def test_complete_accepts_exactly_one_of_the_two_fields(
    client: TestClient, configured_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """INNOCENCE for the 422 XOR guard: a legitimate typed-failure
    completion (error_class only, no result_text) must pass validation."""
    monkeypatch.setattr(
        wa_broker_router.wa_broker, "complete_job", AsyncMock(return_value=CompleteStatus.ACCEPTED)
    )
    body = _complete_body(result_text=None, error_class="codex_timeout")
    resp = client.post(
        "/api/wa-broker/complete", json=body, headers={"X-API-Key": configured_key}
    )
    assert resp.status_code == 200


@pytest.mark.parametrize(
    ("status", "expected_http", "expected_body"),
    [
        (CompleteStatus.ACCEPTED, 200, {"status": "accepted"}),
        (CompleteStatus.REPLAY, 200, {"status": "replay"}),
        (CompleteStatus.CONFLICT, 409, None),
        (CompleteStatus.GONE, 410, None),
    ],
)
def test_complete_status_mapping(
    client: TestClient,
    configured_key: str,
    monkeypatch: pytest.MonkeyPatch,
    status: CompleteStatus,
    expected_http: int,
    expected_body: dict | None,
) -> None:
    monkeypatch.setattr(
        wa_broker_router.wa_broker, "complete_job", AsyncMock(return_value=status)
    )

    resp = client.post(
        "/api/wa-broker/complete",
        json=_complete_body(),
        headers={"X-API-Key": configured_key},
    )

    assert resp.status_code == expected_http
    if expected_body is not None:
        assert resp.json() == expected_body


# ── rate limit ───────────────────────────────────────────────────────────


def test_rate_limit_blocks_after_threshold_then_a_fresh_window_passes(
    client: TestClient, configured_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(wa_broker_router, "_RATE_LIMIT_PER_MINUTE", 3)
    monkeypatch.setattr(wa_broker_router.wa_broker, "claim_job", AsyncMock(return_value=None))

    fake_now = {"t": 1_000.0}
    monkeypatch.setattr(wa_broker_router.time, "monotonic", lambda: fake_now["t"])

    headers = {"X-API-Key": configured_key}
    for _ in range(3):
        resp = client.post("/api/wa-broker/claim", json={}, headers=headers)
        assert resp.status_code == 200

    fourth = client.post("/api/wa-broker/claim", json={}, headers=headers)
    assert fourth.status_code == 429

    # a fresh 60s window resets the count and lets the next call through
    fake_now["t"] += 61.0
    fifth = client.post("/api/wa-broker/claim", json={}, headers=headers)
    assert fifth.status_code == 200


def test_rate_limit_counts_failed_auth_attempts_too(
    client: TestClient, configured_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Credential guessing must hit the same ceiling as legitimate traffic.

    The first version of this gate incremented the counter only AFTER a
    successful auth, so wrong-key attempts could be retried forever without a
    single 429 — the opposite of the brute-force bound the limiter exists for
    (found by the S2 test lane's adversarial pass). Guilt: wrong-key attempts
    beyond the ceiling get 429, not another free 401.
    """
    monkeypatch.setattr(wa_broker_router, "_RATE_LIMIT_PER_MINUTE", 3)
    fake_now = {"t": 1_000.0}
    monkeypatch.setattr(wa_broker_router.time, "monotonic", lambda: fake_now["t"])

    wrong = {"X-API-Key": "guess-attempt-not-the-key"}
    for _ in range(3):
        assert (
            client.post("/api/wa-broker/claim", json={}, headers=wrong).status_code == 401
        )

    fourth = client.post("/api/wa-broker/claim", json={}, headers=wrong)
    assert fourth.status_code == 429

    # The throttle bounds the whole surface: inside the exhausted window even
    # the right key is throttled; a fresh window lets the legitimate caller
    # straight back through (innocence: the ordering change cannot starve it).
    right = {"X-API-Key": configured_key}
    assert client.post("/api/wa-broker/claim", json={}, headers=right).status_code == 429
    fake_now["t"] += 61.0
    monkeypatch.setattr(wa_broker_router.wa_broker, "claim_job", AsyncMock(return_value=None))
    assert client.post("/api/wa-broker/claim", json={}, headers=right).status_code == 200
