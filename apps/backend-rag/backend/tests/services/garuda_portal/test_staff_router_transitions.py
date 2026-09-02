"""Real-database integration tests for `garuda_staff_router.py` (step 8,
STATE-MACHINE.md rows PR-02..PR-11).

Same DSN resolution, same CI-fails-loud-not-skip posture, and the same
"drive a real order through `GarudaOrderRepository` to `paid`, never a
hand-rolled row" discipline as `test_practice.py` (L4 practice-serving) —
this file reuses that sibling's fixtures verbatim rather than re-deriving
them, so both suites exercise `garuda_practices` against the SAME shape of
rows production code produces.

Auth is tested here (not via a fake pool) because every guilt/innocence
case this file needs — a real `Received` practice, a real `Blocked` one
with a private note, a real assignment — is cheapest to build through the
actual repository/router path against a real Postgres, and this file
already pays that fixture cost for the transition-matrix tests below.
"""

from __future__ import annotations

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
_JWT_SECRET = "staff-router-test-secret-do-not-use-in-prod"


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
    """Verbatim copy of `test_practice.py`'s own helper — see that file for
    the full self-heal reasoning."""
    await conn.execute(
        """
        UPDATE public.visa_decision_retention_policies
           SET effective_period = tstzrange(lower(effective_period), clock_timestamp(), '[)')
         WHERE environment = 'TEST' AND policy_scope = 'GARUDA_ORDER'
           AND upper(effective_period) IS NULL
        """
    )
    policy_version = f"staff-router-test-fixture-{uuid.uuid4().hex[:16]}"
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


@pytest.fixture
async def pool():
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
    async with p.acquire() as conn:
        await conn.execute(
            "TRUNCATE garuda_practices, garuda_order_outbox, garuda_order_journal, "
            "garuda_payment_inbox, garuda_order_idempotency, garuda_orders CASCADE"
        )
        policy_version = await _ensure_garuda_order_test_policy(conn)
    yield p
    async with p.acquire() as conn:
        await _close_garuda_order_test_policy(conn, policy_version)
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
    # No Redis in this test environment — the revocation check must not
    # need one for these tests to exercise the auth logic under test.
    monkeypatch.setattr(
        "backend.services.garuda_portal.staff_auth.is_session_revoked_sync",
        lambda payload: False,
    )


def _make_app(pool) -> FastAPI:
    app = FastAPI()
    app.include_router(garuda_staff_router.router)
    app.state.garuda_db_pool = pool
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


# zero@balizero.com is in `settings.admin_emails_set`'s local-dev fallback
# (config.py `_ADMIN_EMAILS_FALLBACK`) — used here rather than the previous
# `admin@balizero.com` because `staff_auth.can_manage_garuda_practices` /
# `_staff_principal_from_role` (refuter finding #6) grants `is_admin` from
# the explicit GARUDA-practice admin allowlist (global admins + Asya), never
# from a self-reported `role="admin"` JWT claim alone -- `admin@balizero.com`
# is `crm_utils.CRM_EXTRA_ADMIN_EMAILS`-admin (a wider, CRM-only set this
# module deliberately does not reuse), not a GARUDA-practice admin.
_ADMIN = "zero@balizero.com"
_TEAM_A = "teama@balizero.com"
_TEAM_B = "teamb@balizero.com"


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


@pytest.mark.asyncio
class TestStaffAuthGuiltAndInnocence:
    async def test_no_credential_is_401_session_required(self, pool) -> None:
        app = _make_app(pool)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/visa/voa/staff/practices/prc_doesnotmatter0000")
        assert resp.status_code == 401
        assert resp.json()["code"] == "SESSION_REQUIRED"

    async def test_customer_magic_link_cookie_is_401_session_required(self, pool) -> None:
        """A customer's `garuda_session` magic-link cookie must NEVER
        authorize a staff route — `require_garuda_staff` never reads that
        cookie, only `request.state.user` (CRM cookie session) or a bearer
        CRM JWT."""
        app = _make_app(pool)
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", cookies={"garuda_session": "customer-session-value"}
        ) as client:
            resp = await client.get("/api/visa/voa/staff/practices/prc_doesnotmatter0000")
        assert resp.status_code == 401
        assert resp.json()["code"] == "SESSION_REQUIRED"

    async def test_team_member_on_unassigned_practice_is_403(
        self, pool, order_repository
    ) -> None:
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-403-0000000000", provider_event_id="evt-403-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        app = _make_app(pool)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/visa/voa/staff/practices/{practice_id}",
                headers={"Authorization": _bearer(_TEAM_A, "user")},
            )
        assert resp.status_code == 403
        assert resp.json()["code"] == "ACCESS_DENIED"

    async def test_admin_gets_200_on_any_practice(self, pool, order_repository) -> None:
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-admin-0000000000", provider_event_id="evt-admin-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        app = _make_app(pool)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/visa/voa/staff/practices/{practice_id}",
                headers={"Authorization": _bearer(_ADMIN, "admin")},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["practice_id"] == practice_id
        assert body["state"] == "Received"


@pytest.mark.asyncio
class TestPracticeViewNeverLeaksPrivateNote:
    async def test_transition_practice_response_omits_private_staff_note(
        self, pool, order_repository
    ) -> None:
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-leak-0000000000", provider_event_id="evt-leak-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        app = _make_app(pool)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/visa/voa/staff/practices/{practice_id}/transitions",
                headers={
                    "Authorization": _bearer(_ADMIN, "admin"),
                    "Idempotency-Key": "leak-check-key-0000000001",
                },
                json={
                    "transition_id": "PR-03",
                    "customer_reason_key": "garuda_voa.practice.missing_document",
                    "required_action_key": "garuda_voa.action.upload_document",
                    "private_staff_note": "passport number 1234 — never customer-visible",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "private_staff_note" not in body
        assert "resume_target" not in body
        assert "assigned_to" not in body


@pytest.mark.asyncio
class TestTransitionMatrixAndReplay:
    async def _post(self, client, practice_id, key, payload, *, actor=_ADMIN, role="admin"):
        return await client.post(
            f"/api/visa/voa/staff/practices/{practice_id}/transitions",
            headers={"Authorization": _bearer(actor, role), "Idempotency-Key": key},
            json=payload,
        )

    async def test_happy_path_pr02_pr04_pr06_pr11(self, pool, order_repository) -> None:
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-happy-0000000000", provider_event_id="evt-happy-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        app = _make_app(pool)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r02 = await self._post(
                client, practice_id, "happy-key-pr02-0000000001", {"transition_id": "PR-02"}
            )
            assert r02.status_code == 200, r02.text
            assert r02.json()["state"] == "In review"

            r04 = await self._post(
                client,
                practice_id,
                "happy-key-pr04-0000000001",
                {"transition_id": "PR-04", "evidence_id": "evidence_filing_0000000001"},
            )
            assert r04.status_code == 200, r04.text
            assert r04.json()["state"] == "Submitted"

            r06 = await self._post(
                client,
                practice_id,
                "happy-key-pr06-0000000001",
                {"transition_id": "PR-06", "evidence_id": "evidence_approval_000000001"},
            )
            assert r06.status_code == 200, r06.text
            assert r06.json()["state"] == "Approved"

            r11 = await self._post(
                client,
                practice_id,
                "happy-key-pr11-0000000001",
                {
                    "transition_id": "PR-11",
                    "artifact_id": "artifact_id_0000000000001",
                    "artifact_digest": "a" * 64,
                },
            )
            assert r11.status_code == 200, r11.text
            assert r11.json()["state"] == "Delivered"
            assert r11.json()["artifact_available"] is True

    async def test_block_then_resume_pr03_pr09(self, pool, order_repository) -> None:
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-block-0000000000", provider_event_id="evt-block-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        app = _make_app(pool)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r03 = await self._post(
                client,
                practice_id,
                "block-key-pr03-0000000001",
                {
                    "transition_id": "PR-03",
                    "customer_reason_key": "garuda_voa.practice.missing_document",
                    "required_action_key": "garuda_voa.action.upload_document",
                },
            )
            assert r03.status_code == 200, r03.text
            assert r03.json()["state"] == "Blocked"
            assert r03.json()["customer_reason_key"] == "garuda_voa.practice.missing_document"

            r09 = await self._post(
                client,
                practice_id,
                "block-key-pr09-0000000001",
                {"transition_id": "PR-09", "resolved_block_id": "resolved_block_id_00000001"},
            )
            assert r09.status_code == 200, r09.text
            assert r09.json()["state"] == "In review"
            assert "customer_reason_key" not in r09.json()

    async def test_forbidden_transition_is_409(self, pool, order_repository) -> None:
        """A `Received` practice cannot jump straight to PR-04 (submit) —
        the CAS `WHERE state = ANY(from_states)` guard must reject it."""
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-forbid-0000000000", provider_event_id="evt-forbid-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        app = _make_app(pool)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await self._post(
                client,
                practice_id,
                "forbid-key-pr04-0000000001",
                {"transition_id": "PR-04", "evidence_id": "evidence_filing_0000000002"},
            )
        assert resp.status_code == 409
        assert resp.json()["code"] == "INVALID_STATE_TRANSITION"

    async def test_exact_replay_returns_same_body_and_header(
        self, pool, order_repository
    ) -> None:
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-replay-0000000000", provider_event_id="evt-replay-1"
        )
        practice_id = await _practice_id_for(pool, order_id)
        app = _make_app(pool)
        transport = ASGITransport(app=app)
        payload = {"transition_id": "PR-02"}
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            first = await self._post(client, practice_id, "replay-key-0000000000001", payload)
            assert first.status_code == 200
            second = await self._post(client, practice_id, "replay-key-0000000000001", payload)
        assert second.status_code == 200
        assert second.json() == first.json()
        assert second.headers.get("Idempotency-Replayed") == "true"
        assert "Idempotency-Replayed" not in first.headers


@pytest.mark.asyncio
class TestAssignmentAndListVisibility:
    async def test_non_admin_cannot_assign(self, pool, order_repository) -> None:
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-assign-403-000000", provider_event_id="evt-assign-403"
        )
        practice_id = await _practice_id_for(pool, order_id)
        app = _make_app(pool)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/visa/voa/staff/practices/{practice_id}/assignment",
                headers={
                    "Authorization": _bearer(_TEAM_A, "user"),
                    "Idempotency-Key": "assign-403-key-00000000001",
                },
                json={"assigned_to": _TEAM_A},
            )
        assert resp.status_code == 403
        assert resp.json()["code"] == "ACCESS_DENIED"

    async def test_admin_assigns_then_assignee_can_see_it_others_cannot(
        self, pool, order_repository
    ) -> None:
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-assign-ok-0000000", provider_event_id="evt-assign-ok"
        )
        practice_id = await _practice_id_for(pool, order_id)
        app = _make_app(pool)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            assign_resp = await client.post(
                f"/api/visa/voa/staff/practices/{practice_id}/assignment",
                headers={
                    "Authorization": _bearer(_ADMIN, "admin"),
                    "Idempotency-Key": "assign-ok-key-000000000001",
                },
                json={"assigned_to": _TEAM_B},
            )
            assert assign_resp.status_code == 200, assign_resp.text
            assert assign_resp.json()["assigned_to"] == _TEAM_B

            assignee_resp = await client.get(
                f"/api/visa/voa/staff/practices/{practice_id}",
                headers={"Authorization": _bearer(_TEAM_B, "user")},
            )
            assert assignee_resp.status_code == 200

            other_resp = await client.get(
                f"/api/visa/voa/staff/practices/{practice_id}",
                headers={"Authorization": _bearer(_TEAM_A, "user")},
            )
            assert other_resp.status_code == 403

    async def test_list_filters_non_admin_to_assigned_only(
        self, pool, order_repository
    ) -> None:
        order_a = await _create_and_pay_order(
            order_repository, result_id="result-list-a-00000000", provider_event_id="evt-list-a"
        )
        order_b = await _create_and_pay_order(
            order_repository, result_id="result-list-b-00000000", provider_event_id="evt-list-b"
        )
        practice_a = await _practice_id_for(pool, order_a)
        practice_b = await _practice_id_for(pool, order_b)
        await pool.execute(
            "UPDATE garuda_practices SET assigned_to = $2, assigned_at = statement_timestamp(), "
            "assigned_by = $3 WHERE practice_id = $1",
            practice_a,
            _TEAM_A,
            _ADMIN,
        )

        app = _make_app(pool)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/visa/voa/staff/practices",
                headers={"Authorization": _bearer(_TEAM_A, "user")},
            )
        assert resp.status_code == 200
        ids = {row["practice_id"] for row in resp.json()["items"]}
        assert practice_a in ids
        assert practice_b not in ids


@pytest.mark.asyncio
class TestMigration305Idempotent:
    async def test_apply_twice_is_a_no_op(self, pool) -> None:
        sql_path = (
            "backend/db/migrations_v2/305_garuda_practices_assignment.sql"
        )
        with open(sql_path, encoding="utf-8") as fh:
            content = fh.read()
        forward_sql = content.split("-- === ROLLBACK ===")[0]
        async with pool.acquire() as conn:
            await conn.execute(forward_sql)
            await conn.execute(forward_sql)
            columns = await conn.fetch(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'garuda_practices' AND column_name IN "
                "('assigned_to', 'assigned_at', 'assigned_by')"
            )
        assert {r["column_name"] for r in columns} == {
            "assigned_to",
            "assigned_at",
            "assigned_by",
        }
