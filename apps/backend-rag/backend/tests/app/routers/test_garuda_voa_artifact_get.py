"""HTTP-level tests for the two delivered-artifact GET routes added in W3A
phase 2 commit B: `getPracticeArtifact` (customer, `garuda_orders_router.py`)
and `getStaffPracticeArtifact` (staff, `garuda_staff_router.py`). Both wired
into ONE FastAPI app here (no path collision -- `/api/visa/voa` vs
`/api/visa/voa/staff`), so a single `client` fixture drives both lanes.

Fixture shapes are a deliberate merge of two existing siblings, not a new
invention: the magic-session/ownership machinery (`magic_link_store`,
`_seed_session`, `garuda_orders_router` wiring) is
`test_garuda_orders_ownership.py`'s own; the staff bearer/policy/artifact-
service machinery (`_bearer`, the two retention-policy fixtures,
`artifact_service`) is `test_staff_router_put_practice_artifact.py`'s own.
Neither file is imported from -- per-file-copy discipline, same reasoning
both cite in their own docstrings.

Real Postgres required, same DSN resolution and CI-fails-loud-not-skip
posture as every other GARUDA VOA integration suite in this tree.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

asyncpg = pytest.importorskip("asyncpg")

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from jose import jwt as jose_jwt

from backend.app.core.database import init_asyncpg_connection
from backend.app.routers import garuda_orders_router, garuda_staff_router
from backend.services.garuda_artifacts.fakes import InMemoryArtifactObjectStore
from backend.services.garuda_artifacts.postgres_repository import PostgresArtifactRepository
from backend.services.garuda_artifacts.service import GarudaArtifactService
from backend.services.garuda_flow.intake import CaseType
from backend.services.garuda_orders.idempotency import canonical_payload_sha256, scoped_key_sha256
from backend.services.garuda_orders.models import Applicant
from backend.services.garuda_orders.ports import ReviewedCheckSnapshot
from backend.services.garuda_orders.repository import GarudaOrderRepository
from backend.services.garuda_portal.magic_link_store import PostgresMagicLinkStore
from backend.services.payments.port import CheckoutSession, NormalizedPaidEvent

_DSN = (
    os.environ.get("GARUDA_L3_TEST_DSN")
    or os.environ.get("INTAKE_TEST_DSN")
    or "postgresql://localhost:5432/nuzantara_test"
)
_JWT_SECRET = "artifact-get-test-secret-do-not-use-in-prod"
_SESSION_COOKIE = "garuda_session"
_ADMIN = "zero@balizero.com"
_TEAM_A = "teama@balizero.com"
_SYNTHETIC_PDF = b"%PDF-1.4\n%synthetic-test-fixture-no-real-document\n%%EOF"


class _FakeLookup:
    async def get_reviewed_check(self, result_id: str) -> ReviewedCheckSnapshot | None:
        return ReviewedCheckSnapshot(
            result_id=result_id, case_type=CaseType.ISSUANCE, review_confirmed=True
        )


class _FakeProvider:
    async def create_checkout_session(self, *, order_id, price_idr, idempotency_key):
        return CheckoutSession(
            provider_session_id=f"sess-{order_id}",
            checkout_url="https://sandbox.xendit.co/checkout/fake",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

    def verify_signature(self, *, raw_body, headers):
        return None

    def parse_event(self, *, raw_body, headers):
        raise NotImplementedError

    async def confirm_no_successful_charge(self, *, provider_session_id: str) -> bool:
        return True

    async def refund(self, *, provider_charge_id: str, idempotency_key: str) -> str:
        raise NotImplementedError


async def _ensure_garuda_order_test_policy(conn: asyncpg.Connection) -> str:
    await conn.execute(
        """
        UPDATE public.visa_decision_retention_policies
           SET effective_period = tstzrange(lower(effective_period), clock_timestamp(), '[)')
         WHERE environment = 'TEST' AND policy_scope = 'GARUDA_ORDER'
           AND upper(effective_period) IS NULL
        """
    )
    policy_version = f"artifact-get-order-fixture-{uuid.uuid4().hex[:16]}"
    await conn.execute(
        """
        INSERT INTO public.visa_decision_retention_policies (
            environment, policy_scope, policy_version, retention_interval,
            idempotency_retention_interval, legal_hold_review_interval,
            retention_anchor, effective_period, approved_by, approval_reference
        ) VALUES (
            'TEST', 'GARUDA_ORDER', $1, INTERVAL '90 days',
            INTERVAL '1 hour', INTERVAL '30 days',
            'CREATED_AT', tstzrange(clock_timestamp(), NULL, '[)'),
            'zero-test-approver', 'ZERO-GARUDA-ORDER-RETENTION-TEST-APPROVAL'
        )
        ON CONFLICT DO NOTHING
        """,
        policy_version,
    )
    return policy_version


async def _close_garuda_order_test_policy(conn: asyncpg.Connection, policy_version: str) -> None:
    await conn.execute(
        """
        UPDATE public.visa_decision_retention_policies
           SET effective_period = tstzrange(lower(effective_period), clock_timestamp(), '[)')
         WHERE policy_scope = 'GARUDA_ORDER'
           AND policy_version = $1
           AND upper(effective_period) IS NULL
        """,
        policy_version,
    )


async def _ensure_garuda_document_test_policy(
    conn: asyncpg.Connection,
    *,
    retention_interval: str = "INTERVAL '30 days'",
    idempotency_retention_interval: str = "INTERVAL '1 hour'",
) -> str:
    """Same self-heal shape as the sibling files' own copy. `retention_
    interval` is overridable ONLY for the past-retention test below, which
    needs a freshly-inserted row to already read as expired -- the table's
    own CHECK (`idempotency_retention_interval <= retention_interval`,
    264's `visa_decision_retention_policies_check`) means shrinking one
    below `idempotency_retention_interval`'s default requires shrinking
    both together."""
    await conn.execute(
        """
        UPDATE public.visa_decision_retention_policies
           SET effective_period = tstzrange(lower(effective_period), clock_timestamp(), '[)')
         WHERE environment = 'TEST' AND policy_scope = 'GARUDA_DOCUMENT'
           AND upper(effective_period) IS NULL
        """
    )
    policy_version = f"artifact-get-document-fixture-{uuid.uuid4().hex[:16]}"
    await conn.execute(
        f"""
        INSERT INTO visa_decision_retention_policies (
            environment, policy_scope, policy_version, retention_interval,
            idempotency_retention_interval, legal_hold_review_interval,
            retention_anchor, effective_period, approved_by, approval_reference
        ) VALUES (
            'TEST', 'GARUDA_DOCUMENT', $1, {retention_interval},
            {idempotency_retention_interval}, INTERVAL '30 days',
            'CREATED_AT', tstzrange(clock_timestamp(), NULL, '[)'),
            'zero-test-approver', 'ZERO-GARUDA-DOCUMENT-RETENTION-TEST-APPROVAL'
        )
        """,
        policy_version,
    )
    return policy_version


async def _close_garuda_document_test_policy(conn: asyncpg.Connection, policy_version: str) -> None:
    await conn.execute(
        """
        UPDATE public.visa_decision_retention_policies
           SET effective_period = tstzrange(lower(effective_period), clock_timestamp(), '[)')
         WHERE environment = 'TEST' AND policy_scope = 'GARUDA_DOCUMENT'
           AND policy_version = $1 AND upper(effective_period) IS NULL
        """,
        policy_version,
    )


@pytest.fixture(autouse=True)
def _garuda_public_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")


@pytest.fixture(autouse=True)
def _jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.core.config import settings

    monkeypatch.setattr(settings, "jwt_secret_key", _JWT_SECRET)
    monkeypatch.setattr(
        "backend.services.garuda_portal.staff_auth.is_session_revoked_sync",
        lambda payload: False,
    )


@pytest.fixture
async def pool():
    p: asyncpg.Pool | None = None
    try:
        p = await asyncpg.create_pool(
            dsn=_DSN, min_size=1, max_size=2, init=init_asyncpg_connection
        )
    except (OSError, asyncpg.PostgresError) as exc:
        if os.environ.get("CI"):
            pytest.fail(
                f"CI has no reachable Postgres for INTAKE_TEST_DSN "
                f"(or GARUDA_L3_TEST_DSN override) -- {_DSN!r} unreachable: {exc}. "
                f"This surface serves a paid customer's document; it must never "
                f"silently pass by skipping."
            )
        pytest.skip(f"no local Postgres reachable at {_DSN}: {exc}")
    assert p is not None
    async with p.acquire() as conn:
        await conn.execute(
            "TRUNCATE garuda_practice_artifacts, garuda_practices, garuda_order_outbox, "
            "garuda_order_journal, garuda_payment_inbox, garuda_order_idempotency, "
            "garuda_orders, garuda_account_sessions CASCADE"
        )
        order_policy_version = await _ensure_garuda_order_test_policy(conn)
        document_policy_version = await _ensure_garuda_document_test_policy(conn)
    yield p
    async with p.acquire() as conn:
        await _close_garuda_order_test_policy(conn, order_policy_version)
        # Idempotent no-op if a test (the past-retention one) already closed
        # this specific version itself.
        await _close_garuda_document_test_policy(conn, document_policy_version)
    await p.close()


@pytest.fixture
def order_repository(pool, monkeypatch):
    import backend.services.garuda_orders.repository as repository_module

    monkeypatch.setattr(
        repository_module.pricing,
        "price_for_case",
        lambda case_type, *, today: (790_000, "B1 Visa on Arrival (VOA)"),
    )
    return GarudaOrderRepository(
        pool, eligibility_lookup=_FakeLookup(), provider=_FakeProvider(), environment="TEST"
    )


@pytest.fixture
def magic_link_store(pool) -> PostgresMagicLinkStore:
    return PostgresMagicLinkStore(pool, environment="TEST")


@pytest.fixture
def object_store() -> InMemoryArtifactObjectStore:
    return InMemoryArtifactObjectStore()


@pytest.fixture
def artifact_service(object_store: InMemoryArtifactObjectStore) -> GarudaArtifactService:
    return GarudaArtifactService(
        repository=PostgresArtifactRepository(), object_store=object_store, environment="TEST"
    )


@pytest.fixture
def app(
    pool,
    order_repository: GarudaOrderRepository,
    magic_link_store: PostgresMagicLinkStore,
    artifact_service: GarudaArtifactService,
) -> FastAPI:
    application = FastAPI()
    application.include_router(garuda_orders_router.router)
    application.include_router(garuda_staff_router.router)
    application.state.garuda_order_repository = order_repository
    application.state.garuda_db_pool = pool
    application.state.garuda_magic_session_verifier = magic_link_store.verify_session
    application.state.garuda_artifact_service = artifact_service
    return application


@pytest.fixture
def client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _hash_hex(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _seed_session(pool, *, raw_secret: str, result_id: str) -> None:
    expires_at = datetime.now(UTC) + timedelta(days=30)
    await pool.execute(
        """
        INSERT INTO garuda_account_sessions
            (session_secret_hash, result_id, email, created_at, expires_at)
        VALUES ($1, $2, 'visitor@example.com', $3, $4)
        """,
        _hash_hex(raw_secret),
        result_id,
        expires_at - timedelta(days=30),
        expires_at,
    )


def _bearer(email: str, role: str) -> str:
    payload = {
        "email": email,
        "sub": email,
        "role": role,
        "type": "access",
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "iat": datetime.now(UTC),
    }
    token = jose_jwt.encode(payload, _JWT_SECRET, algorithm="HS256")
    return f"Bearer {token}"


async def _create_and_pay_order(order_repository, *, result_id: str, provider_event_id: str) -> str:
    key_digest = scoped_key_sha256(
        actor=result_id, operation="createOrderFromCheck", raw_key=f"idem-{provider_event_id}"
    )
    payload_digest = canonical_payload_sha256({"result_id": result_id, "applicant": {"e": 1}})
    body, _replayed = await order_repository.create_order_and_checkout(
        result_id=result_id,
        applicant=Applicant(
            full_name="Test User",
            email="t@example.com",
            phone="+10000000",
            passport_number="P1234567",
        ),
        review_confirmed=True,
        idempotency_key_sha256=key_digest,
        canonical_payload_sha256=payload_digest,
    )
    order_id = body["order_id"]
    event = NormalizedPaidEvent(
        provider_event_id=provider_event_id,
        provider_charge_id=f"charge-{provider_event_id}",
        provider_session_id=f"sess-{order_id}",
        amount_idr=body["price_idr"],
        currency="IDR",
    )
    transition = await order_repository.handle_paid_event(
        event, canonical_payload_sha256=b"\x00" * 32
    )
    assert transition == "OP-02"
    return order_id


async def _practice_id_for(pool, order_id: str) -> str:
    return await pool.fetchval(
        "SELECT practice_id FROM garuda_practices WHERE order_id = $1", order_id
    )


async def _put_artifact(client: AsyncClient, practice_id: str, key: str) -> dict:
    resp = await client.put(
        f"/api/visa/voa/staff/practices/{practice_id}/artifact",
        headers={"Authorization": _bearer(_ADMIN, "admin"), "Idempotency-Key": key},
        content=_SYNTHETIC_PDF,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
class TestGetPracticeArtifactCustomer:
    async def test_happy_path_200_with_exact_bytes_and_headers(
        self, pool, order_repository, client
    ) -> None:
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-getok-00000000000", provider_event_id="evt-getok-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        await _seed_session(pool, raw_secret="secret-getok-0000000000000000", result_id="result-getok-00000000000")
        await _put_artifact(client, practice_id, "getok-put-key-00000000001")

        resp = await client.get(
            f"/api/visa/voa/orders/{order_id}/artifact",
            cookies={_SESSION_COOKIE: "secret-getok-0000000000000000"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.content == _SYNTHETIC_PDF
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.headers["content-disposition"] == f'attachment; filename="voa-{order_id}.pdf"'
        assert resp.headers["cache-control"] in ("no-store", "no-store, private")

    async def test_different_magic_session_is_404(self, pool, order_repository, client) -> None:
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-getfor-00000000000", provider_event_id="evt-getfor-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        await _seed_session(pool, raw_secret="secret-getfor-000000000000000", result_id="result-getfor-00000000000")
        await _put_artifact(client, practice_id, "getfor-put-key-00000000001")
        await _seed_session(pool, raw_secret="secret-getstranger-00000000000", result_id="result-getstranger-0000000")

        resp = await client.get(
            f"/api/visa/voa/orders/{order_id}/artifact",
            cookies={_SESSION_COOKIE: "secret-getstranger-00000000000"},
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == "ORDER_NOT_FOUND"

    async def test_no_session_is_401(self, pool, order_repository, client) -> None:
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-getnosess-0000000000", provider_event_id="evt-getnosess-1"
        )
        resp = await client.get(f"/api/visa/voa/orders/{order_id}/artifact")
        assert resp.status_code == 401
        assert resp.json()["code"] == "SESSION_REQUIRED"

    async def test_not_yet_produced_is_404(self, pool, order_repository, client) -> None:
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-getnotyet-000000000", provider_event_id="evt-getnotyet-1"
        )
        await _seed_session(pool, raw_secret="secret-getnotyet-00000000000000", result_id="result-getnotyet-000000000")

        resp = await client.get(
            f"/api/visa/voa/orders/{order_id}/artifact",
            cookies={_SESSION_COOKIE: "secret-getnotyet-00000000000000"},
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == "ORDER_NOT_FOUND"

    async def test_superseded_is_404(self, pool, order_repository, client) -> None:
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-getsup-000000000000", provider_event_id="evt-getsup-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        await _seed_session(pool, raw_secret="secret-getsup-0000000000000000", result_id="result-getsup-000000000000")
        artifact = await _put_artifact(client, practice_id, "getsup-put-key-00000000001")
        # The guard trigger permits exactly this ONE column change.
        await pool.execute(
            "UPDATE garuda_practice_artifacts SET superseded_at = clock_timestamp() WHERE artifact_id = $1",
            artifact["artifact_id"],
        )

        resp = await client.get(
            f"/api/visa/voa/orders/{order_id}/artifact",
            cookies={_SESSION_COOKIE: "secret-getsup-0000000000000000"},
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == "ORDER_NOT_FOUND"

    async def test_past_retention_is_404(self, pool, order_repository, client) -> None:
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-getexp-000000000000", provider_event_id="evt-getexp-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        await _seed_session(pool, raw_secret="secret-getexp-0000000000000000", result_id="result-getexp-000000000000")

        async with pool.acquire() as conn:
            # Replace the fixture's 30-day GARUDA_DOCUMENT policy with one
            # whose interval is 2 seconds. Migration 312's own INSERT
            # trigger (`bind_garuda_practice_artifact_retention_policy`)
            # REFUSES to insert a row whose computed `retention_until` is
            # already in the past ("retention deadline has already
            # elapsed") -- so a microsecond interval cannot be used to
            # manufacture an already-expired row at insert time; the row
            # must be inserted while still live and then actually age past
            # it, which is what the sleep below does.
            await conn.execute(
                """
                UPDATE public.visa_decision_retention_policies
                   SET effective_period = tstzrange(lower(effective_period), clock_timestamp(), '[)')
                 WHERE environment = 'TEST' AND policy_scope = 'GARUDA_DOCUMENT'
                   AND upper(effective_period) IS NULL
                """
            )
            tiny_policy_version = await _ensure_garuda_document_test_policy(
                conn,
                retention_interval="INTERVAL '2 seconds'",
                idempotency_retention_interval="INTERVAL '1 second'",
            )
        await _put_artifact(client, practice_id, "getexp-put-key-00000000001")
        async with pool.acquire() as conn:
            await _close_garuda_document_test_policy(conn, tiny_policy_version)
        await asyncio.sleep(2.5)

        resp = await client.get(
            f"/api/visa/voa/orders/{order_id}/artifact",
            cookies={_SESSION_COOKIE: "secret-getexp-0000000000000000"},
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == "ORDER_NOT_FOUND"

    async def test_digest_mismatch_is_503_through_the_normal_contract_error_envelope(
        self, pool, order_repository, client, object_store: InMemoryArtifactObjectStore
    ) -> None:
        """Dux correction: "zero body bytes" (spec §5) means zero bytes of
        the UNVERIFIED PDF -- it does not mean an empty HTTP body in place
        of the contract's error envelope. Every error in this lane goes
        through `_ContractErrorRoute` -> `_error()` and carries the same
        three fields (code, retryable, message_key) every sibling error
        does; a raw empty `Response` built directly would have been the
        one error on this route that broke that shape."""
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-getmis-000000000000", provider_event_id="evt-getmis-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        await _seed_session(pool, raw_secret="secret-getmis-0000000000000000", result_id="result-getmis-000000000000")
        artifact = await _put_artifact(client, practice_id, "getmis-put-key-00000000001")
        storage_key = await pool.fetchval(
            "SELECT storage_key FROM garuda_practice_artifacts WHERE artifact_id = $1",
            artifact["artifact_id"],
        )
        object_store.corrupt(storage_key)

        resp = await client.get(
            f"/api/visa/voa/orders/{order_id}/artifact",
            cookies={_SESSION_COOKIE: "secret-getmis-0000000000000000"},
        )
        assert resp.status_code == 503
        assert resp.headers["content-type"].startswith("application/json")
        body = resp.json()
        assert body["code"] == "SERVICE_UNAVAILABLE"
        assert body["retryable"] is True
        # No byte of the (unverified, or tampered-replacement) PDF ever
        # reaches the wire.
        assert "%PDF" not in resp.text
        assert "tampered" not in resp.text


@pytest.mark.asyncio
class TestGetStaffPracticeArtifact:
    async def test_unassigned_staff_is_403(self, pool, order_repository, client) -> None:
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-staffget403-00000", provider_event_id="evt-staffget403-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        await _put_artifact(client, practice_id, "staffget403-put-key-0000001")

        resp = await client.get(
            f"/api/visa/voa/staff/practices/{practice_id}/artifact",
            headers={"Authorization": _bearer(_TEAM_A, "Team Leader")},
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == "ACCESS_DENIED"

    async def test_staff_ok_is_200(self, pool, order_repository, client) -> None:
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-staffget200-00000", provider_event_id="evt-staffget200-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        await _put_artifact(client, practice_id, "staffget200-put-key-0000001")

        resp = await client.get(
            f"/api/visa/voa/staff/practices/{practice_id}/artifact",
            headers={"Authorization": _bearer(_ADMIN, "admin")},
        )
        assert resp.status_code == 200, resp.text
        assert resp.content == _SYNTHETIC_PDF
        assert resp.headers["content-type"] == "application/pdf"
