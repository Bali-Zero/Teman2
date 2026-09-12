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


async def _put_artifact(
    client: AsyncClient, practice_id: str, key: str, *, body: bytes = _SYNTHETIC_PDF
) -> dict:
    key = key.ljust(16, "0")
    resp = await client.put(
        f"/api/visa/voa/staff/practices/{practice_id}/artifact",
        headers={"Authorization": _bearer(_ADMIN, "admin"), "Idempotency-Key": key},
        content=body,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _transition(client: AsyncClient, practice_id: str, key: str, payload: dict) -> dict:
    """Same shape as `test_staff_router_transitions.py`'s own `_post`
    helper (not imported -- per-file-copy discipline this tree already
    uses). Pads `key` out to the router's 16-char `_idempotency_key`
    minimum -- short, readable test-local prefixes stay short."""
    key = key.ljust(16, "0")
    resp = await client.post(
        f"/api/visa/voa/staff/practices/{practice_id}/transitions",
        headers={"Authorization": _bearer(_ADMIN, "admin"), "Idempotency-Key": key},
        json=payload,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _deliver(client: AsyncClient, practice_id: str, *, key_prefix: str) -> dict:
    """PR-02 -> PR-04 -> PR-06 -> PR-11, the same chain `test_staff_router_
    transitions.py::test_happy_path_pr02_pr04_pr06_pr11` drives, ending with
    a putPracticeArtifact + PR-11 deliver. Returns the artifact dict PR-11
    was delivered with."""
    await _transition(client, practice_id, f"{key_prefix}-pr02", {"transition_id": "PR-02"})
    await _transition(
        client,
        practice_id,
        f"{key_prefix}-pr04",
        {"transition_id": "PR-04", "evidence_id": f"evidence_filing_{key_prefix}"},
    )
    await _transition(
        client,
        practice_id,
        f"{key_prefix}-pr06",
        {"transition_id": "PR-06", "evidence_id": f"evidence_approval_{key_prefix}"},
    )
    artifact = await _put_artifact(client, practice_id, f"{key_prefix}-put")
    await _transition(
        client,
        practice_id,
        f"{key_prefix}-pr11",
        {
            "transition_id": "PR-11",
            "artifact_id": artifact["artifact_id"],
            "artifact_digest": artifact["artifact_digest"],
        },
    )
    return artifact


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
        # F1 (Sol O1 refutation, 2026-09-11): the customer read now REQUIRES
        # Delivered + artifact_available + the practice's own pointer to
        # match the live row -- a bare `_put_artifact` leaves the practice
        # Approved, which is exactly the premature-download scenario F1
        # forbids. Drive the real PR-02 -> PR-11 chain so this "happy path"
        # actually proves the state the route is meant to serve.
        await _deliver(client, practice_id, key_prefix="getok")

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
        # F1: deliver first, so this 404 proves "not your order" and not
        # merely "not delivered yet" -- a negative test whose subject is
        # unreachable for a SECOND, unrelated reason proves nothing.
        await _deliver(client, practice_id, key_prefix="getfor")
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
        """A row marked superseded with no live row that the PRACTICE'S OWN
        POINTER resolves to reads as gone to the customer. The Dux is
        concurrently constraining `superseded_by` to reference an artifact
        on the SAME practice (finding F7) -- unlike the old version of this
        test, whose `superseded_by` pointed at an artifact belonging to an
        UNRELATED practice, which F7 forbids. The successor row below is
        therefore inserted directly at the SQL layer on THIS practice
        (real `putPracticeArtifact` supersession always does the same --
        one row superseded, one inserted, same transaction, same practice,
        decision #13-revision -- but it would ALSO move the Delivered
        practice's own artifact_id/artifact_digest pointer onto the
        successor, which `TestArtifactSupersession` below covers
        end-to-end; this test is about the raw invariant, not that flow).
        Because the practice's pointer here still names the FIRST
        (now-superseded) pair, `get_live_for_order`'s join finds no row:
        the superseded row fails `a.superseded_at IS NULL`, and the live
        successor fails `a.artifact_id = p.artifact_id` -- gone either
        way."""
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-getsup-000000000000", provider_event_id="evt-getsup-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        await _seed_session(pool, raw_secret="secret-getsup-0000000000000000", result_id="result-getsup-000000000000")
        artifact = await _deliver(client, practice_id, key_prefix="getsup")

        # `ux_garuda_practice_artifacts_live` allows only one LIVE row per
        # practice_id -- inserting the successor before marking the first
        # row superseded would transiently give the practice two live rows
        # and fail immediately (measured: `UniqueViolationError`). Same
        # ORDER `insert_superseding` itself uses (postgres_repository.py):
        # UPDATE the old row's superseded_at/superseded_by FIRST, inside
        # ONE transaction, THEN INSERT the successor -- `superseded_by`'s
        # FK is DEFERRABLE INITIALLY DEFERRED exactly so this order is
        # legal (the referenced row does not exist yet when the UPDATE
        # runs, only by the time the transaction commits).
        successor_artifact_id = f"getsup-successor-{uuid.uuid4().hex[:16]}"
        async with pool.acquire() as conn, conn.transaction():
            await conn.execute(
                "UPDATE garuda_practice_artifacts SET superseded_at = clock_timestamp(), superseded_by = $2 "
                "WHERE artifact_id = $1",
                artifact["artifact_id"],
                successor_artifact_id,
            )
            await conn.execute(
                """
                INSERT INTO garuda_practice_artifacts
                    (artifact_id, practice_id, storage_key, artifact_digest,
                     byte_length, content_type, produced_by, environment)
                VALUES ($1, $2, $3, $4, $5, 'application/pdf', 'zero-test-approver', 'TEST')
                """,
                successor_artifact_id,
                practice_id,
                f"artifacts/TEST/{practice_id}/{successor_artifact_id}",
                hashlib.sha256(b"getsup-successor-placeholder-bytes").hexdigest(),
                len(_SYNTHETIC_PDF),
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
            # Replace the fixture's 30-day GARUDA_DOCUMENT policy with a
            # short one. Migration 313's own INSERT trigger
            # (`bind_garuda_practice_artifact_retention_policy`) REFUSES to
            # insert a row whose computed `retention_until` is already in
            # the past ("retention deadline has already elapsed") -- so a
            # microsecond interval cannot be used to manufacture an
            # already-expired row at insert time; the row must be inserted
            # while still live and then actually age past it, which is what
            # the sleep below does.
            #
            # 9 seconds, not the original 2: F3's cure (`get_live_for_
            # practice_locked` now also filters `retention_until >
            # clock_timestamp()`) means PR-11 itself refuses an expired pair
            # (see `test_pr11_refuses_expired_pair_and_leaves_practice_
            # approved` below) -- so THIS test must drive the whole
            # PR-02 -> PR-04 -> PR-06 -> put -> PR-11 chain to completion,
            # over real HTTP through the ASGI transport, BEFORE the row
            # ages out. 9s is comfortable margin over that chain's five
            # round-trips; 2s was already margin-free for a single PUT and
            # would flake constantly for five sequential calls.
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
                retention_interval="INTERVAL '9 seconds'",
                idempotency_retention_interval="INTERVAL '1 second'",
            )
        # Deliver (not just put) BEFORE the row ages -- F3 means an expired
        # pair never reaches Delivered at all, so the expired-but-Delivered
        # row this test wants to exercise only exists if PR-11 lands first.
        await _deliver(client, practice_id, key_prefix="getexp")
        async with pool.acquire() as conn:
            await _close_garuda_document_test_policy(conn, tiny_policy_version)
        await asyncio.sleep(9.5)

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
        # F1: deliver first so the row actually resolves through
        # `get_live_for_order` -- PR-11 itself verifies the digest at
        # delivery time, so the corruption below must happen AFTER
        # delivery, never before it.
        artifact = await _deliver(client, practice_id, key_prefix="getmis")
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

    async def test_put_without_pr11_is_404_not_the_old_200(
        self, pool, order_repository, client
    ) -> None:
        """Guilt test for finding F1 (Sol O1 refutation, 2026-09-11): a
        magic-link session could download the grant right after the staff
        PUT, while the practice was still Approved and nothing had been
        released. BEFORE the cure, `get_live_for_order` carried only
        ownership + liveness -- this exact sequence (PUT, no PR-11, owning
        session GETs) answered 200 with the PDF right here. AFTER the cure
        (`p.state = 'Delivered'` AND `p.artifact_available` required in the
        same query), it is 404."""
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-getf1-0000000000000", provider_event_id="evt-getf1-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        await _seed_session(
            pool, raw_secret="secret-getf1-00000000000000000", result_id="result-getf1-0000000000000"
        )
        await _transition(client, practice_id, "getf1-pr02", {"transition_id": "PR-02"})
        await _transition(
            client,
            practice_id,
            "getf1-pr04",
            {"transition_id": "PR-04", "evidence_id": "evidence_filing_getf1_0001"},
        )
        await _transition(
            client,
            practice_id,
            "getf1-pr06",
            {"transition_id": "PR-06", "evidence_id": "evidence_approval_getf1_0001"},
        )
        # PR-11 deliberately NOT run -- the practice stays Approved, exactly
        # the window F1 named.
        await _put_artifact(client, practice_id, "getf1-put-key-00000000001")

        resp = await client.get(
            f"/api/visa/voa/orders/{order_id}/artifact",
            cookies={_SESSION_COOKIE: "secret-getf1-00000000000000000"},
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == "ORDER_NOT_FOUND"

    async def test_practice_pointer_digest_mismatch_is_404(
        self, pool, order_repository, client
    ) -> None:
        """Guilt test: the bytes served must be the EXACT pair PR-11
        verified, not merely "the live row for this practice". BEFORE the
        cure, `get_live_for_order` never compared `a.artifact_digest`
        against `p.artifact_digest` -- a practice pointer corrupted (or
        left stale by an unrelated bug) would still resolve to whatever
        live row existed for the practice. AFTER the cure, a mismatched
        pointer is 404, never a fallback resolution onto the live row."""
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-getf1b-000000000000", provider_event_id="evt-getf1b-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        await _seed_session(
            pool, raw_secret="secret-getf1b-00000000000000000", result_id="result-getf1b-000000000000"
        )
        await _deliver(client, practice_id, key_prefix="getf1b")

        # Break the practice's own pointer directly at the SQL layer --
        # state stays Delivered, artifact_available stays true, but
        # artifact_digest no longer names the pair PR-11 actually verified.
        bogus_digest = hashlib.sha256(b"getf1b-bogus-pointer-digest").hexdigest()
        await pool.execute(
            "UPDATE garuda_practices SET artifact_digest = $2 WHERE practice_id = $1",
            practice_id,
            bogus_digest,
        )

        resp = await client.get(
            f"/api/visa/voa/orders/{order_id}/artifact",
            cookies={_SESSION_COOKIE: "secret-getf1b-00000000000000000"},
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == "ORDER_NOT_FOUND"

    async def test_pr11_refuses_expired_pair_and_leaves_practice_approved(
        self, pool, order_repository, client
    ) -> None:
        """Guilt test for finding F3 (Sol O1 refutation, 2026-09-11): put
        while Approved, let the artifact age past a short retention
        interval (same manufacturing technique `test_past_retention_is_404`
        uses -- migration 313's INSERT trigger refuses to insert an
        already-expired row, so the row must age after insert), then submit
        PR-11 with the ORIGINAL, correct pair. BEFORE the cure (`get_live_
        for_practice_locked` had no `retention_until > clock_timestamp()`
        filter), this delivered SUCCESSFULLY -- the practice reached
        Delivered, a delivery mail went out promising a download, and
        `get_live_for_order` (which DOES filter retention) answered 404 on
        that same order from the very next request. AFTER the cure, PR-11
        itself is refused -- 422 INVALID_REQUEST, the same `ArtifactDelivery
        Rejected` path B3/B4 already cover for a fabricated pair -- and the
        practice never leaves Approved."""
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-getf3-0000000000000", provider_event_id="evt-getf3-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        await _transition(client, practice_id, "getf3-pr02", {"transition_id": "PR-02"})
        await _transition(
            client,
            practice_id,
            "getf3-pr04",
            {"transition_id": "PR-04", "evidence_id": "evidence_filing_getf3_0001"},
        )
        await _transition(
            client,
            practice_id,
            "getf3-pr06",
            {"transition_id": "PR-06", "evidence_id": "evidence_approval_getf3_0001"},
        )

        async with pool.acquire() as conn:
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
                retention_interval="INTERVAL '9 seconds'",
                idempotency_retention_interval="INTERVAL '1 second'",
            )
        artifact = await _put_artifact(client, practice_id, "getf3-put-key-00000000001")
        async with pool.acquire() as conn:
            await _close_garuda_document_test_policy(conn, tiny_policy_version)
        await asyncio.sleep(9.5)

        resp = await client.post(
            f"/api/visa/voa/staff/practices/{practice_id}/transitions",
            headers={
                "Authorization": _bearer(_ADMIN, "admin"),
                "Idempotency-Key": "getf3-pr11-with-expired-pair-01",
            },
            json={
                "transition_id": "PR-11",
                "artifact_id": artifact["artifact_id"],
                "artifact_digest": artifact["artifact_digest"],
            },
        )
        assert resp.status_code == 422, resp.text
        assert resp.json()["code"] == "INVALID_REQUEST"

        # The practice never became Delivered off the expired pair.
        row = await pool.fetchrow(
            "SELECT state, artifact_available FROM garuda_practices WHERE practice_id = $1",
            practice_id,
        )
        assert row["state"] == "Approved"
        assert row["artifact_available"] is False


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


@pytest.mark.asyncio
class TestArtifactSupersession:
    """S7 (Imperatore decision #13-revision, 2026-09-11: "always supersede,
    never 409, made observable"). `test_staff_router_put_practice_
    artifact.py` covers the row-level shape (old row's two columns, ZERO
    outbox rows, idempotent replay, concurrent puts) -- this class covers
    the two cross-router consequences that need BOTH routers wired
    together: the Delivered practice's own pointer, and PR-11's stale-pair
    rejection."""

    async def test_supersede_on_delivered_practice_moves_pointer_and_customer_sees_new_bytes(
        self, pool, order_repository, client
    ) -> None:
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-supdeliv-00000000000", provider_event_id="evt-supdeliv-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        await _seed_session(
            pool, raw_secret="secret-supdeliv-000000000000000", result_id="result-supdeliv-00000000000"
        )
        first = await _deliver(client, practice_id, key_prefix="supdeliv")

        before = await client.get(
            f"/api/visa/voa/orders/{order_id}/artifact",
            cookies={_SESSION_COOKIE: "secret-supdeliv-000000000000000"},
        )
        assert before.status_code == 200, before.text
        assert before.content == _SYNTHETIC_PDF

        # Deliberately NOT a superset of `_SYNTHETIC_PDF` (only the
        # mandatory `%PDF-` magic prefix is shared) -- so "the old bytes
        # are gone" below is a real substring check, not trivially true.
        second_pdf = b"%PDF-1.4\n%replacement-document-v2\n%%EOF"
        second = await _put_artifact(
            client, practice_id, "supdeliv-put-key-v2-0000001", body=second_pdf
        )
        assert second["artifact_id"] != first["artifact_id"]

        # (6b) the Delivered practice's own pointer moved to the new pair,
        # in the SAME transaction as the row swap -- 287's CHECK still
        # holds (both columns stay non-NULL, only their values move) and
        # artifact_available is untouched.
        row = await pool.fetchrow(
            "SELECT state, artifact_id, artifact_digest, artifact_available "
            "FROM garuda_practices WHERE practice_id = $1",
            practice_id,
        )
        assert row["state"] == "Delivered"
        assert row["artifact_id"] == second["artifact_id"]
        assert row["artifact_digest"] == second["artifact_digest"]
        assert row["artifact_available"] is True

        # Delivered always resolves to retrievable bytes -- the customer
        # now gets the NEW pdf, never the superseded one.
        after = await client.get(
            f"/api/visa/voa/orders/{order_id}/artifact",
            cookies={_SESSION_COOKIE: "secret-supdeliv-000000000000000"},
        )
        assert after.status_code == 200, after.text
        assert after.content == second_pdf
        assert after.content != before.content
        assert before.content not in after.content

    async def test_pr11_with_the_superseded_pair_is_422(self, pool, order_repository, client) -> None:
        """(6c) Approved practice, artifact put once then superseded BEFORE
        delivery -- attempting PR-11 with the now-stale pair is 422, the
        SAME `ArtifactDeliveryRejected` path B3/B4 already cover for a
        fabricated or foreign pair (`resolve_for_delivery` checks the
        submitted pair against the CURRENT live row, and the superseded id
        no longer matches it)."""
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-suppr11-000000000000", provider_event_id="evt-suppr11-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        await _transition(client, practice_id, "suppr11-pr02", {"transition_id": "PR-02"})
        await _transition(
            client,
            practice_id,
            "suppr11-pr04",
            {"transition_id": "PR-04", "evidence_id": "evidence_filing_suppr11_0001"},
        )
        await _transition(
            client,
            practice_id,
            "suppr11-pr06",
            {"transition_id": "PR-06", "evidence_id": "evidence_approval_suppr11_0001"},
        )
        first = await _put_artifact(client, practice_id, "suppr11-put-key-v1-00000001")
        second = await _put_artifact(
            client, practice_id, "suppr11-put-key-v2-00000001", body=_SYNTHETIC_PDF + b"\n%v2"
        )
        assert second["artifact_id"] != first["artifact_id"]

        resp = await client.post(
            f"/api/visa/voa/staff/practices/{practice_id}/transitions",
            headers={
                "Authorization": _bearer(_ADMIN, "admin"),
                "Idempotency-Key": "suppr11-pr11-with-old-pair-0001",
            },
            json={
                "transition_id": "PR-11",
                "artifact_id": first["artifact_id"],
                "artifact_digest": first["artifact_digest"],
            },
        )
        assert resp.status_code == 422, resp.text
        assert resp.json()["code"] == "INVALID_REQUEST"

        # The practice never became Delivered off the stale pair.
        state = await pool.fetchval(
            "SELECT state FROM garuda_practices WHERE practice_id = $1", practice_id
        )
        assert state == "Approved"


@pytest.mark.asyncio
class TestPracticePointerIntegrity:
    async def test_the_pointer_cannot_be_moved_to_another_practices_artifact(
        self, pool, order_repository, client
    ) -> None:
        """Sol O2 new finding 1 (BLOCKER, 2026-09-12).

        F7 constrained `garuda_practice_artifacts.superseded_by` to the
        practice's own rows, and `garuda_practices`' pointer had no
        equivalent: `move_practice_pointer_if_delivered` wrote whatever
        pair it was handed. Today's only caller passes the successor it
        just inserted for the same practice, so nothing reaches it -- but
        that is the shape of guarantee F7 was cured for assuming, and a
        practice pointed at a stranger's artifact is a permanent 404 to its
        customer, because `get_live_for_order`'s equality predicates can
        never be satisfied.

        Drives the repository method directly: the defect is not reachable
        through the routers, which is exactly why only a direct call can
        hold the line.
        """
        own_order_id = await _create_and_pay_order(
            order_repository, result_id="result-ptrown-00000000000", provider_event_id="evt-ptrown-1"
        )
        own_practice_id = await _practice_id_for(pool, own_order_id)
        await _deliver(client, own_practice_id, key_prefix="ptrown")

        stranger_order_id = await _create_and_pay_order(
            order_repository, result_id="result-ptrstr-00000000000", provider_event_id="evt-ptrstr-1"
        )
        stranger_practice_id = await _practice_id_for(pool, stranger_order_id)
        stranger = await _deliver(client, stranger_practice_id, key_prefix="ptrstr")

        before = await pool.fetchrow(
            "SELECT artifact_id, artifact_digest FROM garuda_practices WHERE practice_id = $1",
            own_practice_id,
        )

        repository = PostgresArtifactRepository()
        async with pool.acquire() as conn:
            moved = await repository.move_practice_pointer_if_delivered(
                conn,
                practice_id=own_practice_id,
                artifact_id=stranger["artifact_id"],
                artifact_digest=stranger["artifact_digest"],
            )
        assert moved is False, "a stranger's artifact must not become this practice's pointer"

        after = await pool.fetchrow(
            "SELECT artifact_id, artifact_digest FROM garuda_practices WHERE practice_id = $1",
            own_practice_id,
        )
        assert dict(after) == dict(before)

        # The customer read is unaffected -- still the practice's own grant.
        await _seed_session(
            pool,
            raw_secret="secret-ptrown-000000000000000",
            result_id="result-ptrown-00000000000",
        )
        resp = await client.get(
            f"/api/visa/voa/orders/{own_order_id}/artifact",
            cookies={_SESSION_COOKIE: "secret-ptrown-000000000000000"},
        )
        assert resp.status_code == 200, resp.text
