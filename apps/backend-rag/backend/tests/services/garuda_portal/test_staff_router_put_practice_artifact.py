"""Real-database integration tests for `putPracticeArtifact`
(`garuda_staff_router.py`, W3A phase 2, PR A).

Fixtures below are a verbatim copy of `test_staff_router_transitions.py`'s
own `pool`/`order_repository`/`_bearer`/`_create_and_pay_order`/
`_practice_id_for` -- see that file for the full self-heal/fixture
reasoning. Kept as a separate file (not appended to that one) for the same
file-ownership discipline `test_staff_router_transitions.py` itself names:
`putPracticeArtifact` is PR A's own route, wired to a real
`GarudaArtifactService` this file constructs, which `transitionPractice`'s
suite does not need.

The object store is `InMemoryArtifactObjectStore` (fakes.py) -- real
Postgres for the row, no real Tigris credentials needed for this test.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

asyncpg = pytest.importorskip("asyncpg")

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from jose import jwt as jose_jwt

from backend.app.core.database import init_asyncpg_connection
from backend.app.routers import garuda_staff_router
from backend.services.garuda_artifacts.fakes import InMemoryArtifactObjectStore
from backend.services.garuda_artifacts.postgres_repository import PostgresArtifactRepository
from backend.services.garuda_artifacts.service import GarudaArtifactService
from backend.services.garuda_flow.intake import CaseType
from backend.services.garuda_orders.idempotency import canonical_payload_sha256, scoped_key_sha256
from backend.services.garuda_orders.models import Applicant
from backend.services.garuda_orders.ports import ReviewedCheckSnapshot
from backend.services.garuda_orders.repository import GarudaOrderRepository
from backend.services.payments.port import CheckoutSession, NormalizedPaidEvent

_DSN = (
    os.environ.get("GARUDA_L3_TEST_DSN")
    or os.environ.get("INTAKE_TEST_DSN")
    or "postgresql://localhost:5432/nuzantara_test"
)
_JWT_SECRET = "staff-router-artifact-test-secret-do-not-use-in-prod"
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
    """Verbatim copy of `test_practice.py`'s own helper (via
    `test_staff_router_transitions.py`) -- PR-01 needs a live GARUDA_ORDER
    policy to mint a practice at all."""
    await conn.execute(
        """
        UPDATE public.visa_decision_retention_policies
           SET effective_period = tstzrange(lower(effective_period), clock_timestamp(), '[)')
         WHERE environment = 'TEST' AND policy_scope = 'GARUDA_ORDER'
           AND upper(effective_period) IS NULL
        """
    )
    policy_version = f"artifact-test-fixture-{uuid.uuid4().hex[:16]}"
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


async def _ensure_garuda_document_test_policy(conn: asyncpg.Connection) -> str:
    """The retention binder `putPracticeArtifact` writes through
    (migration 312, `bind_garuda_practice_artifact_retention_policy`) needs
    a live `GARUDA_DOCUMENT` policy. `ON CONFLICT DO NOTHING` keyed on the
    table's own `UNIQUE (environment, policy_scope, policy_version)` makes
    this safe to call once per test module."""
    # Self-heal first, the same shape `test_garuda_orders_ownership.py`'s
    # `_ensure_garuda_order_test_policy` uses for GARUDA_ORDER. An
    # `ON CONFLICT (environment, policy_scope, policy_version)` target only
    # absorbs an IDENTICAL version: a second, differently-named open-ended
    # policy for the same (environment, scope) violates the EXCLUDE constraint
    # `visa_decision_retention_policies_scope_period_excl` instead, which no
    # ON CONFLICT target covers. Measured, not assumed: run in ONE process
    # (as CI does) with the migration-312 suite, the previous fixture's
    # policy was still open and 8 tests errored on exactly that constraint.
    await conn.execute(
        """
        UPDATE public.visa_decision_retention_policies
           SET effective_period = tstzrange(lower(effective_period), clock_timestamp(), '[)')
         WHERE environment = 'TEST' AND policy_scope = 'GARUDA_DOCUMENT'
           AND upper(effective_period) IS NULL
        """
    )
    policy_version = f"artifact-put-fixture-{uuid.uuid4().hex[:16]}"
    await conn.execute(
        """
        INSERT INTO visa_decision_retention_policies (
            environment, policy_scope, policy_version, retention_interval,
            idempotency_retention_interval, legal_hold_review_interval,
            retention_anchor, effective_period, approved_by, approval_reference
        ) VALUES (
            'TEST', 'GARUDA_DOCUMENT', $1, INTERVAL '30 days',
            INTERVAL '1 hour', INTERVAL '30 days',
            'CREATED_AT', tstzrange(clock_timestamp(), NULL, '[)'),
            'zero-test-approver', 'ZERO-GARUDA-DOCUMENT-RETENTION-TEST-APPROVAL'
        )
        """,
        policy_version,
    )
    return policy_version


async def _close_garuda_document_test_policy(conn: asyncpg.Connection, policy_version: str) -> None:
    """Teardown twin: close the policy this module opened, so the next module's
    self-heal has nothing left to close and no open row outlives the run."""
    await conn.execute(
        """
        UPDATE public.visa_decision_retention_policies
           SET effective_period = tstzrange(lower(effective_period), clock_timestamp(), '[)')
         WHERE environment = 'TEST' AND policy_scope = 'GARUDA_DOCUMENT'
           AND policy_version = $1 AND upper(effective_period) IS NULL
        """,
        policy_version,
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
                f"This surface creates rows for a paid order; it must never "
                f"silently pass by skipping."
            )
        pytest.skip(f"no local Postgres reachable at {_DSN}: {exc}")
    assert p is not None
    async with p.acquire() as conn:
        await conn.execute(
            "TRUNCATE garuda_practice_artifacts, garuda_practices, garuda_order_outbox, "
            "garuda_order_journal, garuda_payment_inbox, garuda_order_idempotency, "
            "garuda_orders CASCADE"
        )
        order_policy_version = await _ensure_garuda_order_test_policy(conn)
        document_policy_version = await _ensure_garuda_document_test_policy(conn)
    yield p
    async with p.acquire() as conn:
        await _close_garuda_order_test_policy(conn, order_policy_version)
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


def _make_app(pool, *, artifact_service: GarudaArtifactService | None) -> FastAPI:
    app = FastAPI()
    app.include_router(garuda_staff_router.router)
    app.state.garuda_db_pool = pool
    app.state.garuda_artifact_service = artifact_service
    return app


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


@pytest.fixture
def artifact_service() -> GarudaArtifactService:
    return GarudaArtifactService(
        repository=PostgresArtifactRepository(),
        object_store=InMemoryArtifactObjectStore(),
        environment="TEST",
    )


@pytest.mark.asyncio
class TestPutPracticeArtifactAuth:
    async def test_no_credential_is_401_session_required(self, pool, artifact_service) -> None:
        app = _make_app(pool, artifact_service=artifact_service)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                "/api/visa/voa/staff/practices/prc_doesnotmatter0000/artifact",
                headers={"Idempotency-Key": "no-cred-key-0000000000001"},
                content=_SYNTHETIC_PDF,
            )
        assert resp.status_code == 401
        assert resp.json()["code"] == "SESSION_REQUIRED"

    async def test_team_member_on_unassigned_practice_is_403(
        self, pool, order_repository, artifact_service
    ) -> None:
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-put403-000000000", provider_event_id="evt-put403-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        app = _make_app(pool, artifact_service=artifact_service)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                f"/api/visa/voa/staff/practices/{practice_id}/artifact",
                headers={
                    "Authorization": _bearer(_TEAM_A, "Team Leader"),
                    "Idempotency-Key": "put403-key-0000000000001",
                },
                content=_SYNTHETIC_PDF,
            )
        assert resp.status_code == 403
        assert resp.json()["code"] == "ACCESS_DENIED"

    async def test_visibility_is_checked_before_the_body_is_read(
        self, pool, order_repository, artifact_service
    ) -> None:
        """Authorization must run before validation. A staff actor with no
        visibility on the practice sends a body that would ALSO fail
        validation (non-PDF bytes) -- if the body were read/validated first,
        this would 422; the router must 403 instead, proving `visible_or_403`
        runs before `request.body()` is ever awaited."""
        order_id = await _create_and_pay_order(
            order_repository,
            result_id="result-putorder403-0000",
            provider_event_id="evt-putorder403-1",
        )
        practice_id = await _practice_id_for(pool, order_id)
        app = _make_app(pool, artifact_service=artifact_service)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                f"/api/visa/voa/staff/practices/{practice_id}/artifact",
                headers={
                    "Authorization": _bearer(_TEAM_A, "Team Leader"),
                    "Idempotency-Key": "putorder403-key-0000000001",
                },
                content=b"not a pdf at all -- would also fail validation",
            )
        assert resp.status_code == 403
        assert resp.json()["code"] == "ACCESS_DENIED"

    async def test_service_unavailable_without_a_wired_artifact_service(
        self, pool, order_repository
    ) -> None:
        """`get_artifact_service`'s own fail-closed shape (garuda_staff_
        router.py) -- absent wiring must 503, never crash with an
        AttributeError deep in a handler."""
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-put503-000000000", provider_event_id="evt-put503-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        app = _make_app(pool, artifact_service=None)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                f"/api/visa/voa/staff/practices/{practice_id}/artifact",
                headers={
                    "Authorization": _bearer(_ADMIN, "admin"),
                    "Idempotency-Key": "put503-key-0000000000001",
                },
                content=_SYNTHETIC_PDF,
            )
        assert resp.status_code == 503
        assert resp.json()["code"] == "SERVICE_UNAVAILABLE"


@pytest.mark.asyncio
class TestPutPracticeArtifactHappyPathAndValidation:
    async def test_happy_path_returns_generated_id_and_digest(
        self, pool, order_repository, artifact_service
    ) -> None:
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-puthappy-00000000", provider_event_id="evt-puthappy-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        app = _make_app(pool, artifact_service=artifact_service)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                f"/api/visa/voa/staff/practices/{practice_id}/artifact",
                headers={
                    "Authorization": _bearer(_ADMIN, "admin"),
                    "Idempotency-Key": "puthappy-key-0000000001",
                },
                content=_SYNTHETIC_PDF,
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body["artifact_id"]) >= 16
        assert len(body["artifact_digest"]) == 64

    async def test_missing_idempotency_key_is_400(
        self, pool, order_repository, artifact_service
    ) -> None:
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-putnoidem-0000000", provider_event_id="evt-putnoidem-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        app = _make_app(pool, artifact_service=artifact_service)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                f"/api/visa/voa/staff/practices/{practice_id}/artifact",
                headers={"Authorization": _bearer(_ADMIN, "admin")},
                content=_SYNTHETIC_PDF,
            )
        assert resp.status_code == 400
        assert resp.json()["code"] == "IDEMPOTENCY_KEY_REQUIRED"

    async def test_non_pdf_body_is_422(self, pool, order_repository, artifact_service) -> None:
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-putbadpdf-0000000", provider_event_id="evt-putbadpdf-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        app = _make_app(pool, artifact_service=artifact_service)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                f"/api/visa/voa/staff/practices/{practice_id}/artifact",
                headers={
                    "Authorization": _bearer(_ADMIN, "admin"),
                    "Idempotency-Key": "putbadpdf-key-0000000001",
                },
                content=b"not a pdf at all",
            )
        assert resp.status_code == 422
        assert resp.json()["code"] == "INVALID_REQUEST"

    async def test_a_second_put_while_a_live_artifact_exists_supersedes_it(
        self, pool, order_repository, artifact_service
    ) -> None:
        """(6a) Decision #13-revision: "always supersede, never 409, made
        observable" -- a second put (a DIFFERENT Idempotency-Key, not a
        replay of the first) replaces the live artifact instead of being
        refused. Old row: both `superseded_at`/`superseded_by` set, the new
        artifact_id. New row: live. ZERO outbox rows (no email on
        supersession, decision #13-revision item 3)."""
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-putdup-000000000", provider_event_id="evt-putdup-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        app = _make_app(pool, artifact_service=artifact_service)
        transport = ASGITransport(app=app)
        second_pdf = _SYNTHETIC_PDF + b"\n%v2-corrected-document"
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.put(
                f"/api/visa/voa/staff/practices/{practice_id}/artifact",
                headers={
                    "Authorization": _bearer(_ADMIN, "admin"),
                    "Idempotency-Key": "putdup-key-0000000000001",
                },
                content=_SYNTHETIC_PDF,
            )
            assert first.status_code == 200, first.text
            async with pool.acquire() as conn:
                outbox_count_before = await conn.fetchval(
                    "SELECT count(*) FROM garuda_order_outbox WHERE order_id = $1", order_id
                )
                journal_count_before = await conn.fetchval(
                    "SELECT count(*) FROM garuda_order_journal "
                    "WHERE aggregate_type = 'practice' AND aggregate_id = $1",
                    practice_id,
                )
            second = await client.put(
                f"/api/visa/voa/staff/practices/{practice_id}/artifact",
                headers={
                    "Authorization": _bearer(_ADMIN, "admin"),
                    # A DIFFERENT key -- a same-key replay is idempotency's
                    # job (tested separately below), not this guard's.
                    "Idempotency-Key": "putdup-key-0000000000002",
                },
                content=second_pdf,
            )
        assert second.status_code == 200, second.text
        assert second.json()["artifact_id"] != first.json()["artifact_id"]
        assert second.json()["artifact_digest"] != first.json()["artifact_digest"]

        async with pool.acquire() as conn:
            old_row = await conn.fetchrow(
                "SELECT superseded_at, superseded_by FROM garuda_practice_artifacts "
                "WHERE artifact_id = $1",
                first.json()["artifact_id"],
            )
            live_row = await conn.fetchrow(
                "SELECT artifact_id, superseded_at FROM garuda_practice_artifacts "
                "WHERE practice_id = $1 AND superseded_at IS NULL",
                practice_id,
            )
            outbox_count_after = await conn.fetchval(
                "SELECT count(*) FROM garuda_order_outbox WHERE order_id = $1", order_id
            )
            journal_count_after = await conn.fetchval(
                "SELECT count(*) FROM garuda_order_journal "
                "WHERE aggregate_type = 'practice' AND aggregate_id = $1",
                practice_id,
            )
        assert old_row["superseded_at"] is not None
        assert old_row["superseded_by"] == second.json()["artifact_id"]
        assert live_row is not None
        assert live_row["artifact_id"] == second.json()["artifact_id"]
        # Supersession enqueues NOTHING -- the pre-existing OP-01/OP-02
        # lifecycle outbox rows from order creation/payment are untouched,
        # not zero in absolute terms.
        assert outbox_count_after == outbox_count_before
        # Dux ruling (2026-09-12, Option 3): no `garuda_order_journal` row
        # for supersession -- the superseded row itself (both columns set,
        # once, immutable) IS the persisted ids-only record; a DB-only
        # transition_id would break 284's CHECK<->events.yaml invariant,
        # and events.yaml is out of this window's scope. This asserts the
        # negative: supersession must not add ANY practice-scoped journal
        # row, proving no DB-only vocabulary snuck in.
        assert journal_count_after == journal_count_before

    async def test_idempotent_replay_returns_the_same_artifact(
        self, pool, order_repository, artifact_service
    ) -> None:
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-putreplay-00000000", provider_event_id="evt-putreplay-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        app = _make_app(pool, artifact_service=artifact_service)
        transport = ASGITransport(app=app)
        key = "putreplay-key-0000000000001"
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.put(
                f"/api/visa/voa/staff/practices/{practice_id}/artifact",
                headers={"Authorization": _bearer(_ADMIN, "admin"), "Idempotency-Key": key},
                content=_SYNTHETIC_PDF,
            )
            assert first.status_code == 200, first.text
            replay = await client.put(
                f"/api/visa/voa/staff/practices/{practice_id}/artifact",
                headers={"Authorization": _bearer(_ADMIN, "admin"), "Idempotency-Key": key},
                content=_SYNTHETIC_PDF,
            )
        assert replay.status_code == 200, replay.text
        assert replay.json() == first.json()
        assert replay.headers.get("Idempotency-Replayed") == "true"

    async def test_idempotent_replay_does_not_supersede_again(
        self, pool, order_repository, artifact_service
    ) -> None:
        """(6d) An exact replay (SAME Idempotency-Key, SAME body) short-
        circuits at `idempotency.reserve`'s own outcome check -- BEFORE
        `artifact_service.put_practice_artifact` is ever called -- so it
        can never supersede a SECOND time. Multiple replays leave exactly
        the ONE row this endpoint ever wrote."""
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-putreplaysup-0000", provider_event_id="evt-putreplaysup-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        app = _make_app(pool, artifact_service=artifact_service)
        transport = ASGITransport(app=app)
        key = "putreplaysup-key-0000000001"
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.put(
                f"/api/visa/voa/staff/practices/{practice_id}/artifact",
                headers={"Authorization": _bearer(_ADMIN, "admin"), "Idempotency-Key": key},
                content=_SYNTHETIC_PDF,
            )
            assert first.status_code == 200, first.text
            for _ in range(2):
                replay = await client.put(
                    f"/api/visa/voa/staff/practices/{practice_id}/artifact",
                    headers={"Authorization": _bearer(_ADMIN, "admin"), "Idempotency-Key": key},
                    content=_SYNTHETIC_PDF,
                )
                assert replay.status_code == 200, replay.text
                assert replay.json()["artifact_id"] == first.json()["artifact_id"]

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT artifact_id, superseded_at, superseded_by FROM garuda_practice_artifacts "
                "WHERE practice_id = $1",
                practice_id,
            )
        assert len(rows) == 1
        assert rows[0]["artifact_id"] == first.json()["artifact_id"]
        assert rows[0]["superseded_at"] is None
        assert rows[0]["superseded_by"] is None

    async def test_concurrent_puts_serialize_and_never_create_two_live_rows(
        self, pool, order_repository, artifact_service
    ) -> None:
        """Two genuinely concurrent puts (DIFFERENT Idempotency-Keys, real
        DB, `max_size=2` pool -- both requests can be in flight against
        real connections at once) must serialize through `lock_practice_
        for_artifact_write`'s advisory lock: exactly one wins the race and
        stays live, the other's row is properly superseded by it, and the
        partial unique index is never violated."""
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-putrace-00000000000", provider_event_id="evt-putrace-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        app = _make_app(pool, artifact_service=artifact_service)
        transport = ASGITransport(app=app)

        async def _put(key: str, body: bytes):
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.put(
                    f"/api/visa/voa/staff/practices/{practice_id}/artifact",
                    headers={"Authorization": _bearer(_ADMIN, "admin"), "Idempotency-Key": key},
                    content=body,
                )

        first_resp, second_resp = await asyncio.gather(
            _put("putrace-key-a-000000000001", _SYNTHETIC_PDF),
            _put("putrace-key-b-000000000001", _SYNTHETIC_PDF + b"\n%v2"),
        )
        assert first_resp.status_code == 200, first_resp.text
        assert second_resp.status_code == 200, second_resp.text
        ids = {first_resp.json()["artifact_id"], second_resp.json()["artifact_id"]}
        assert len(ids) == 2, "both concurrent puts must have created a DIFFERENT artifact_id"

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT artifact_id, superseded_at, superseded_by FROM garuda_practice_artifacts "
                "WHERE practice_id = $1",
                practice_id,
            )
        assert len(rows) == 2
        live = [r for r in rows if r["superseded_at"] is None]
        superseded = [r for r in rows if r["superseded_at"] is not None]
        assert len(live) == 1, "the partial unique index must leave exactly ONE live row"
        assert len(superseded) == 1
        assert superseded[0]["superseded_by"] == live[0]["artifact_id"]
