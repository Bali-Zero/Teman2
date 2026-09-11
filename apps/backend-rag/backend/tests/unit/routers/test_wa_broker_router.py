"""Tests for the WA broker router (/api/wa-broker/claim, /api/wa-broker/complete),
BOT-V4 S2, #4333.

Auth pattern mirrors test_wa_inbox_auth.py: a bare FastAPI app mounts the
router, get_database_pool is overridden with a mock pool, and
settings.wa_broker_key is monkeypatched per test. The dependency reads
settings at call time, so patching the live settings object is enough.

Unlike the auth suite, most tests here also monkeypatch the service-layer
functions (`wa_broker.claim_job` / `wa_broker.complete_job` as imported into
the router module) so the router's own logic — response mapping, the 422
XOR validation, the error_class vocabulary gate, the Postgres-int ceiling,
the CompleteStatus -> HTTP status table, and the two-bucket rate limiter —
is exercised without any real SQL.

Updated for the S2 cross-family review fixes (2 BLOCKER + 7 MAJOR): the
rate limiter is now TWO buckets split by auth outcome (finding 1, the
BLOCKER — a single pre-auth bucket let unauthenticated flooding starve the
legitimate broker), CompleteRequest.error_class must be a member of
wa_broker.ALLOWED_ERROR_CLASSES (finding 7), and exec_ms/last_exec_ms are
bounded to the Postgres INT ceiling so an out-of-range value 422s here
instead of 500ing in asyncpg (finding 10).
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
def _reset_rate_limit_state():
    """Module-level rate-limit globals must not leak state between tests
    (order-independence): both the authenticated-bucket window and the
    per-source failed-auth dict."""
    wa_broker_router._auth_window_start = 0.0
    wa_broker_router._auth_window_count = 0
    wa_broker_router._fail_windows.clear()
    yield
    wa_broker_router._auth_window_start = 0.0
    wa_broker_router._auth_window_count = 0
    wa_broker_router._fail_windows.clear()


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
    resp = client.post("/api/wa-broker/claim", json={}, headers={"X-API-Key": BROKER_KEY})
    assert resp.status_code == 401


def test_claim_accepts_exact_key_with_no_job_available(
    client: TestClient, configured_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(wa_broker_router.wa_broker, "claim_job", AsyncMock(return_value=None))

    resp = client.post("/api/wa-broker/claim", json={}, headers={"X-API-Key": configured_key})

    assert resp.status_code == 200
    assert resp.json() == {
        "job_id": None,
        "fence_token": None,
        "package": None,
        "package_hash": None,
        "deadline_at": None,
        "server_now": None,
    }


def test_complete_also_gated_by_the_same_key(client: TestClient, configured_key: str) -> None:
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
    monkeypatch.setattr(wa_broker_router.wa_broker, "claim_job", AsyncMock(return_value=fake_row))

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


def test_claim_rejects_last_exec_ms_above_postgres_int_ceiling(
    client: TestClient, configured_key: str
) -> None:
    """finding 10: an unbounded field passes Pydantic and then 500s in
    asyncpg (INT overflow) instead of 422ing here."""
    resp = client.post(
        "/api/wa-broker/claim",
        json={"last_exec_ms": 2**31},
        headers={"X-API-Key": configured_key},
    )
    assert resp.status_code == 422


def test_claim_accepts_last_exec_ms_at_postgres_int_ceiling(
    client: TestClient, configured_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """INNOCENCE: the ceiling value itself must still be accepted."""
    monkeypatch.setattr(wa_broker_router.wa_broker, "claim_job", AsyncMock(return_value=None))
    resp = client.post(
        "/api/wa-broker/claim",
        json={"last_exec_ms": 2**31 - 1},
        headers={"X-API-Key": configured_key},
    )
    assert resp.status_code == 200


# ── complete: result_text / error_class XOR ────────────────────────────────


def test_complete_rejects_both_result_text_and_error_class(
    client: TestClient, configured_key: str
) -> None:
    body = _complete_body(error_class="exec_timeout")  # result_text also present
    resp = client.post("/api/wa-broker/complete", json=body, headers={"X-API-Key": configured_key})
    assert resp.status_code == 422


def test_complete_rejects_neither_result_text_nor_error_class(
    client: TestClient, configured_key: str
) -> None:
    body = _complete_body(result_text=None)  # no error_class either
    resp = client.post("/api/wa-broker/complete", json=body, headers={"X-API-Key": configured_key})
    assert resp.status_code == 422


def test_complete_accepts_exactly_one_of_the_two_fields(
    client: TestClient, configured_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """INNOCENCE for the 422 XOR guard: a legitimate typed-failure
    completion (error_class only, no result_text) must pass validation."""
    monkeypatch.setattr(
        wa_broker_router.wa_broker, "complete_job", AsyncMock(return_value=CompleteStatus.ACCEPTED)
    )
    body = _complete_body(result_text=None, error_class="exec_timeout")
    resp = client.post("/api/wa-broker/complete", json=body, headers={"X-API-Key": configured_key})
    assert resp.status_code == 200


# ── complete: error_class vocabulary (finding 7) ────────────────────────────


def test_complete_rejects_error_class_outside_allowed_vocabulary(
    client: TestClient, configured_key: str
) -> None:
    """GUILT: free text in error_class must never reach a terminal row —
    it is retained OUTSIDE the payload-NULL guarantee."""
    body = _complete_body(result_text=None, error_class="totally_made_up_reason")
    resp = client.post("/api/wa-broker/complete", json=body, headers={"X-API-Key": configured_key})
    assert resp.status_code == 422


def test_complete_accepts_error_class_inside_allowed_vocabulary(
    client: TestClient, configured_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """INNOCENCE: every value the router validator accepts is one of the
    module's own ALLOWED_ERROR_CLASSES — SSOT, no drift between the two."""
    monkeypatch.setattr(
        wa_broker_router.wa_broker, "complete_job", AsyncMock(return_value=CompleteStatus.ACCEPTED)
    )
    body = _complete_body(result_text=None, error_class="oversized_output")
    resp = client.post("/api/wa-broker/complete", json=body, headers={"X-API-Key": configured_key})
    assert resp.status_code == 200


def test_complete_accepts_quota_exhausted_error_class(
    client: TestClient, configured_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B2b: the daemon now reports `quota_exhausted` as its own wire value
    (instead of folding it into `cli_failure`) — the router must accept it,
    not 422 it, or the daemon's typed report never reaches a terminal row."""
    monkeypatch.setattr(
        wa_broker_router.wa_broker, "complete_job", AsyncMock(return_value=CompleteStatus.ACCEPTED)
    )
    body = _complete_body(result_text=None, error_class="quota_exhausted")
    resp = client.post("/api/wa-broker/complete", json=body, headers={"X-API-Key": configured_key})
    assert resp.status_code == 200


# ── complete: exec_ms Postgres int ceiling (finding 10) ─────────────────────


def test_complete_rejects_exec_ms_above_postgres_int_ceiling(
    client: TestClient, configured_key: str
) -> None:
    body = _complete_body(exec_ms=2**31)
    resp = client.post("/api/wa-broker/complete", json=body, headers={"X-API-Key": configured_key})
    assert resp.status_code == 422


def test_complete_accepts_exec_ms_at_postgres_int_ceiling(
    client: TestClient, configured_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        wa_broker_router.wa_broker, "complete_job", AsyncMock(return_value=CompleteStatus.ACCEPTED)
    )
    body = _complete_body(exec_ms=2**31 - 1)
    resp = client.post("/api/wa-broker/complete", json=body, headers={"X-API-Key": configured_key})
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
    monkeypatch.setattr(wa_broker_router.wa_broker, "complete_job", AsyncMock(return_value=status))

    resp = client.post(
        "/api/wa-broker/complete",
        json=_complete_body(),
        headers={"X-API-Key": configured_key},
    )

    assert resp.status_code == expected_http
    if expected_body is not None:
        assert resp.json() == expected_body


# ── rate limit — two buckets split by auth outcome (S2 finding 1, BLOCKER) ──


def test_unauthenticated_flood_does_not_starve_the_authenticated_bucket(
    client: TestClient, configured_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BLOCKER fix (S2 cross-family review, finding 1): the first build
    shared ONE pre-auth bucket across every caller, so 121 bad-key requests
    exhausted the same ceiling the legitimate broker needed — starving
    completion delivery for the rest of the window. Unauthenticated traffic
    must only ever be able to touch the FAIL bucket; the AUTH bucket a
    valid-key caller draws from must stay untouched by any amount of
    bad-key flooding."""
    monkeypatch.setattr(wa_broker_router.wa_broker, "claim_job", AsyncMock(return_value=None))

    for _ in range(150):  # comfortably over the OLD shared 120/min ceiling
        client.post("/api/wa-broker/claim", json={}, headers={"X-API-Key": "wrong-key"})

    ok = client.post("/api/wa-broker/claim", json={}, headers={"X-API-Key": configured_key})
    assert ok.status_code == 200


def test_auth_bucket_rate_limits_the_authenticated_caller(
    client: TestClient, configured_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(wa_broker_router, "_AUTH_LIMIT_PER_MINUTE", 3)
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


def test_fail_bucket_rate_limits_one_source_without_blocking_others(
    client: TestClient, configured_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(wa_broker_router, "_FAIL_LIMIT_PER_MINUTE", 3)
    monkeypatch.setattr(wa_broker_router.wa_broker, "claim_job", AsyncMock(return_value=None))

    wrong = {"X-API-Key": "guess-attempt-not-the-key"}
    for _ in range(3):
        resp = client.post("/api/wa-broker/claim", json={}, headers=wrong)
        assert resp.status_code == 401

    damped = client.post("/api/wa-broker/claim", json={}, headers=wrong)
    assert damped.status_code == 429

    # INNOCENCE: the damped source presenting the VALID key still gets 200 —
    # the fail bucket only ever damps that source's 401 response rate, it
    # can never block a legitimate authenticated request from the same
    # source (TestClient always presents as one host, so this is also the
    # in-test proof that FAIL and AUTH are genuinely separate buckets).
    ok = client.post("/api/wa-broker/claim", json={}, headers={"X-API-Key": configured_key})
    assert ok.status_code == 200


def test_broker_paths_are_armed_in_the_public_endpoints_registry() -> None:
    """Codex re-verdict F1 armed-check (W81: built != armed).

    The auth model for these two routes is handler-owned (require_wa_broker_key
    inside the router), which is only legal if the global API-key middleware is
    told to stand down via PUBLIC_ENDPOINTS. This pins the two entries so a
    registry cleanup cannot silently re-arm the global middleware in front of
    the router (double-auth → every codex-daemon call 401s), and equally so the
    router's own gate stays the one that answers.
    """
    from backend.app.auth.public_endpoints import PUBLIC_ENDPOINTS

    broker_entries = {
        ep.prefix: ep for ep in PUBLIC_ENDPOINTS if ep.prefix.startswith("/api/wa-broker")
    }
    assert set(broker_entries) == {"/api/wa-broker/claim", "/api/wa-broker/complete"}

    # Both must be EXACT matches — a prefix/template entry would also exempt
    # any FUTURE broker route from the middleware before its handler-owned
    # auth exists.
    assert all(ep.match == "exact" for ep in broker_entries.values())

    # And the exemption actually fires for the real request paths.
    assert any(ep.matches("/api/wa-broker/claim") for ep in PUBLIC_ENDPOINTS)
    assert any(ep.matches("/api/wa-broker/complete") for ep in PUBLIC_ENDPOINTS)
    # Innocence: a sibling path the router does NOT own stays behind auth.
    assert not any(ep.matches("/api/wa-broker/other") for ep in PUBLIC_ENDPOINTS)


def test_non_ascii_key_is_a_401_not_an_unthrottled_500(
    client: TestClient, configured_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GUILT (Codex re-verdict r3): hmac.compare_digest on two str objects
    refuses non-ASCII with a TypeError, and Starlette exposes raw header
    bytes as latin-1 text — so an unauthenticated `X-API-Key: \\xff` ("ÿ")
    raised BEFORE _fail_bucket_take, turning the auth gate into an
    unthrottled 500 amplifier. Cured by comparing encoded bytes: the probe
    must be an ordinary 401, charged to the fail bucket like any other
    wrong key (the damping proves the charge)."""
    monkeypatch.setattr(wa_broker_router, "_FAIL_LIMIT_PER_MINUTE", 3)
    monkeypatch.setattr(wa_broker_router.wa_broker, "claim_job", AsyncMock(return_value=None))

    # httpx refuses non-ASCII in a str header value — send the raw byte the
    # way the wire would carry it (latin-1), which Starlette decodes to "ÿ".
    evil = {b"X-API-Key": "ÿ".encode("latin-1")}
    for _ in range(3):
        resp = client.post("/api/wa-broker/claim", json={}, headers=evil)
        assert resp.status_code == 401

    damped = client.post("/api/wa-broker/claim", json={}, headers=evil)
    assert damped.status_code == 429

    # INNOCENCE: the real key (ASCII) still authenticates.
    ok = client.post(
        "/api/wa-broker/claim", json={}, headers={"X-API-Key": configured_key}
    )
    assert ok.status_code == 200


def test_complete_rejects_blank_result_text(client: TestClient, configured_key: str) -> None:
    """Codex re-verdict r6, finding 1 (GUILT): '' and whitespace pass the
    XOR shape but are failures — accepting one would mint a completion with
    nothing to send AND fold success into the breaker (a half_open canary
    returning nothing would close it). 422 at the edge; complete_job
    enforces the same for direct callers."""
    for blank in ("", "   ", "\n\t"):
        resp = client.post(
            "/api/wa-broker/complete",
            json=_complete_body(result_text=blank),
            headers={"X-API-Key": configured_key},
        )
        assert resp.status_code == 422, f"blank {blank!r} was accepted"


# ── auth-before-body + bounded body (Codex re-verdict r7) ─────────────────


def test_unauthenticated_malformed_json_is_a_401_charged_to_the_fail_bucket(
    client: TestClient, configured_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GUILT: with a Pydantic body parameter FastAPI parsed the COMPLETE
    body before resolving dependencies — malformed JSON answered 422
    without the auth dependency ever running (proven by probe:
    dependency_called=False), so an unauthenticated prober was never
    charged to the failed-auth bucket. Auth now genuinely runs first: the
    body is not even read for an unauthenticated caller, and the probes
    are damped like any other wrong-key traffic."""
    monkeypatch.setattr(wa_broker_router, "_FAIL_LIMIT_PER_MINUTE", 3)
    wrong = {"X-API-Key": "not-the-key"}
    for _ in range(3):
        resp = client.post(
            "/api/wa-broker/complete",
            content=b'{"broken json',
            headers={**wrong, "content-type": "application/json"},
        )
        assert resp.status_code == 401  # not 422 — auth answered first
    damped = client.post(
        "/api/wa-broker/complete",
        content=b'{"broken json',
        headers={**wrong, "content-type": "application/json"},
    )
    assert damped.status_code == 429


def test_authenticated_malformed_json_is_a_422(
    client: TestClient, configured_key: str
) -> None:
    """INNOCENCE: a legitimate broker with a bug still gets the 422 it
    needs to debug — after auth, from the handler's own bounded parse."""
    resp = client.post(
        "/api/wa-broker/complete",
        content=b'{"broken json',
        headers={"X-API-Key": configured_key, "content-type": "application/json"},
    )
    assert resp.status_code == 422


def test_oversize_body_is_cut_off_at_the_cap(
    client: TestClient, configured_key: str
) -> None:
    """GUILT: the handler reads the body under a hard cap — a huge ignored
    extra field can no longer force unbounded allocation (the legit max
    complete body is ~64KiB of result_text; the cap is 128KiB)."""
    huge = '{"padding": "' + "x" * (wa_broker_router._MAX_BODY_BYTES + 1024) + '"}'
    resp = client.post(
        "/api/wa-broker/complete",
        content=huge.encode(),
        headers={"X-API-Key": configured_key, "content-type": "application/json"},
    )
    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_single_giant_chunk_is_rejected_before_buffering() -> None:
    """GUILT (Codex re-verdict r8): ASGI does not bound chunk size — a
    cached-body middleware or transport may hand the ENTIRE request over as
    ONE chunk, and a cap checked after body.extend() would copy a
    multi-hundred-MB body into the buffer before the 413 fired. The spy
    proves the oversize chunk is refused UNCONSUMED: iterating it (what
    bytearray.extend does) flips the flag, so a check-after-extend mutant
    turns this red."""
    from fastapi import HTTPException

    class SpyChunk:
        def __init__(self, size: int) -> None:
            self._size = size
            self.iterated = False

        def __len__(self) -> int:
            return self._size

        def __iter__(self):
            self.iterated = True
            return iter(b"")

    spy = SpyChunk(wa_broker_router._MAX_BODY_BYTES + 1)

    class FakeRequest:
        async def stream(self):
            yield spy

    with pytest.raises(HTTPException) as excinfo:
        await wa_broker_router._read_bounded_body(
            FakeRequest(),  # type: ignore[arg-type]
            wa_broker_router.CompleteRequest,
        )
    assert excinfo.value.status_code == 413
    assert spy.iterated is False, "oversize chunk was buffered before the cap check"


def test_complete_rejects_nul_in_result_text_and_key(
    client: TestClient, configured_key: str
) -> None:
    """GUILT (Codex re-verdict r9): PostgreSQL TEXT cannot store U+0000, and
    the JSON escape backslash-u0000 passes plain string validation — without
    the _no_nul validator the completion UPDATE itself 500'd, retried
    identically by the broker until the lease deadline (stuck job + breaker
    fold). It must die here as a 422 the broker can act on. Raw JSON bodies
    so the real model_validate_json path decodes the escape."""
    nul_text_body = (
        '{"job_id":"11111111-1111-1111-1111-111111111111",'
        '"fence_token":"22222222-2222-2222-2222-222222222222",'
        '"completion_key":"key-12345","result_text":"answer\\u0000tail"}'
    )
    resp = client.post(
        "/api/wa-broker/complete",
        content=nul_text_body.encode(),
        headers={"X-API-Key": configured_key, "content-type": "application/json"},
    )
    assert resp.status_code == 422

    nul_key_body = (
        '{"job_id":"11111111-1111-1111-1111-111111111111",'
        '"fence_token":"22222222-2222-2222-2222-222222222222",'
        '"completion_key":"key-123\\u000045","result_text":"a real answer"}'
    )
    resp = client.post(
        "/api/wa-broker/complete",
        content=nul_key_body.encode(),
        headers={"X-API-Key": configured_key, "content-type": "application/json"},
    )
    assert resp.status_code == 422
