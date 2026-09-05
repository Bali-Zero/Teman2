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
    # `pytest.fail`/`pytest.skip` both raise, but a static analyser cannot
    # know that (CodeQL py/uninitialized-local-variable on PR #5584): keep the
    # binding explicit so the control flow is provable, not just true.
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


async def _seed_team_member(pool, email: str, *, role: str = "Team Leader") -> None:
    """`assignPractice`'s target-operator check (round-4 disposition item 2,
    Codex finding #2) queries `team_members` directly -- the same table
    `services/crm/assignment.py::assign_lead` already queries for
    department-based routing -- so a target the test wants to be a valid
    assignee must be a real, active row there."""
    await pool.execute(
        "INSERT INTO team_members (id, name, email, pin_hash, role, active) "
        "VALUES ($1, $2, $3, 'test-pin-hash', $4, TRUE) "
        "ON CONFLICT (email) DO UPDATE SET active = TRUE, role = $4",
        uuid.uuid4().hex[:32],  # team_members.id is VARCHAR(36) -- a full email is too long
        email,
        email,
        role,
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
                # A colleague carries a role the team allow-list knows; "user" is
                # the role-less default and is no longer anyone (PENDING-ARMS 88).
                headers={"Authorization": _bearer(_TEAM_A, "Team Leader")},
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

            detail = await client.get(
                f"/api/visa/voa/staff/practices/{practice_id}",
                headers={"Authorization": _bearer(_ADMIN, "admin")},
            )
            assert detail.json()["artifact_id"] == "artifact_id_0000000000001"
            assert detail.json()["artifact_digest"] == "a" * 64

        # Evidence rows (round-2 disposition #8): one per submit/approve
        # transition, `kind` matching `_EVIDENCE_KIND_BY_TRANSITION_KIND`,
        # inserted in the SAME transaction as the CAS UPDATE above.
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT transition_id, evidence_id, kind FROM garuda_practice_evidence"
                " WHERE practice_id = $1 ORDER BY transition_id",
                practice_id,
            )
        assert [(r["transition_id"], r["evidence_id"], r["kind"]) for r in rows] == [
            ("PR-04", "evidence_filing_0000000001", "filing"),
            ("PR-06", "evidence_approval_000000001", "approval"),
        ]

    async def test_evidence_id_reused_on_another_practice_is_422(
        self, pool, order_repository
    ) -> None:
        """An evidence_id already bound to a DIFFERENT practice is rejected
        (round-2 disposition item B) -- never silently accepted, never a
        409 (that's reserved for a genuine idempotency-key/payload
        conflict, a different failure class)."""
        order_a = await _create_and_pay_order(
            order_repository, result_id="result-evid-a-0000000000", provider_event_id="evt-evid-a"
        )
        order_b = await _create_and_pay_order(
            order_repository, result_id="result-evid-b-0000000000", provider_event_id="evt-evid-b"
        )
        practice_a = await _practice_id_for(pool, order_a)
        practice_b = await _practice_id_for(pool, order_b)
        app = _make_app(pool)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            for practice_id, key_prefix in ((practice_a, "evid-a"), (practice_b, "evid-b")):
                r02 = await self._post(
                    client, practice_id, f"{key_prefix}-key-pr02-0000000001", {"transition_id": "PR-02"}
                )
                assert r02.status_code == 200, r02.text

            r04_a = await self._post(
                client,
                practice_a,
                "evid-a-key-pr04-0000000001",
                {"transition_id": "PR-04", "evidence_id": "shared_evidence_id_00000001"},
            )
            assert r04_a.status_code == 200, r04_a.text

            r04_b = await self._post(
                client,
                practice_b,
                "evid-b-key-pr04-0000000001",
                {"transition_id": "PR-04", "evidence_id": "shared_evidence_id_00000001"},
            )
            assert r04_b.status_code == 422, r04_b.text
            assert r04_b.json()["code"] == "INVALID_REQUEST"

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

            # `active_block_id` is server-generated (the PR-03 journal
            # event's own id) -- resume must echo the REAL value, not an
            # arbitrary client-chosen string, per the round-2 disposition's
            # resolved_block_id == active_block_id identity check.
            detail = await client.get(
                f"/api/visa/voa/staff/practices/{practice_id}",
                headers={"Authorization": _bearer(_ADMIN, "admin")},
            )
            active_block_id = detail.json()["active_block_id"]
            assert active_block_id

            wrong = await self._post(
                client,
                practice_id,
                "block-key-pr09-wrong-0000000001",
                {"transition_id": "PR-09", "resolved_block_id": "not-the-real-block-0000001"},
            )
            assert wrong.status_code == 422, wrong.text
            assert wrong.json()["code"] == "INVALID_REQUEST"

            r09 = await self._post(
                client,
                practice_id,
                "block-key-pr09-0000000001",
                {"transition_id": "PR-09", "resolved_block_id": active_block_id},
            )
            assert r09.status_code == 200, r09.text
            assert r09.json()["state"] == "In review"
            assert "customer_reason_key" not in r09.json()

            detail_after = await client.get(
                f"/api/visa/voa/staff/practices/{practice_id}",
                headers={"Authorization": _bearer(_ADMIN, "admin")},
            )
            assert detail_after.json()["active_block_id"] is None

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

    async def test_exact_replay_enqueues_no_second_outbox_row(
        self, pool, order_repository
    ) -> None:
        """`apply_transition` only reaches `journal.enqueue_outbox` inside
        the transaction it runs in -- a replayed command returns from
        `idempotency.reserve`'s replay outcome in the router BEFORE
        `apply_transition` (and therefore the outbox enqueue) ever runs
        again. `UNIQUE(journal_event_id, job_type)` on `garuda_order_outbox`
        is defense-in-depth for that same fact, not the only thing
        preventing a second customer email on retry."""
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-replay-ob-000000", provider_event_id="evt-replay-ob"
        )
        practice_id = await _practice_id_for(pool, order_id)
        app = _make_app(pool)
        transport = ASGITransport(app=app)
        payload = {"transition_id": "PR-02"}
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await self._post(client, practice_id, "replay-ob-key-000000000001", payload)
            await self._post(client, practice_id, "replay-ob-key-000000000001", payload)
        rows = await pool.fetch(
            "SELECT job_type FROM garuda_order_outbox WHERE order_id = $1 "
            "AND job_type = 'practice_in_review_email'",
            order_id,
        )
        assert len(rows) == 1


@pytest.mark.asyncio
class TestIdempotencyCompletionIsAtomicWithTheBusinessTransaction:
    """Cross-family refuter (Codex) MAJOR finding #5: the business
    transaction (state UPDATE + journal append + outbox enqueue, all inside
    `apply_transition`) could commit, and `idempotency.complete()` run as a
    SEPARATE, later statement -- a crash (or any exception) between those two
    points left a permanently "reserved but never completed" idempotency row
    even though the business effect had already happened. A retry then read
    `completed_at IS NULL` as "still in flight, resume" (per
    `idempotency.reserve`'s own docstring), re-ran `apply_transition`, and
    the CAS UPDATE's `WHERE state = ANY(from_states)` failed against the
    already-transitioned state -> 409 INVALID_STATE_TRANSITION, never the
    committed 200 the command actually produced.

    Fault-injection: force `idempotency.complete` to raise AFTER
    `apply_transition` has run inside the same `async with pool.acquire()`.
    If completion is atomic with the business transaction (the fix), the
    forced failure rolls back the business writes too -- state, journal and
    outbox all revert, proving one transaction, not two. Against the
    pre-fix code, the business writes stay committed because
    `apply_transition`'s own `async with conn.transaction():` block had
    already exited before `complete()` ran."""

    async def test_forced_completion_failure_rolls_back_the_business_writes_too(
        self, pool, order_repository, monkeypatch
    ) -> None:
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-atomic-0000000000", provider_event_id="evt-atomic-1"
        )
        practice_id = await _practice_id_for(pool, order_id)

        from backend.services.garuda_orders import idempotency as idempotency_module

        real_complete = idempotency_module.complete

        async def _boom(*args, **kwargs):
            raise RuntimeError("simulated crash between business commit and idempotency completion")

        monkeypatch.setattr(garuda_staff_router.idempotency, "complete", _boom)

        app = _make_app(pool)
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/visa/voa/staff/practices/{practice_id}/transitions",
                headers={
                    "Authorization": _bearer(_ADMIN, "admin"),
                    "Idempotency-Key": "atomic-key-000000000001",
                },
                json={"transition_id": "PR-02"},
            )
        assert resp.status_code == 500

        row = await pool.fetchrow(
            "SELECT state FROM garuda_practices WHERE practice_id = $1", practice_id
        )
        assert row["state"] == "Received", (
            "the business write must roll back together with the failed "
            "idempotency completion -- state must NOT have advanced to "
            "In_review from a transaction that never fully committed"
        )
        # `garuda_order_journal` already carries one LEGITIMATE, already-
        # committed row for this aggregate_id: `_create_and_pay_order` ->
        # `handle_paid_event` writes a `practice.received` / PR-01 event
        # when the practice row is first created, entirely before this
        # test's own PR-02 attempt. Only a SECOND row (PR-02's own
        # `practice.in_review`) would prove the forced failure failed to
        # roll back -- asserting `== []` here would be asserting a fact
        # this test never set up and never claimed.
        journal_rows = await pool.fetch(
            "SELECT 1 FROM garuda_order_journal WHERE aggregate_id = $1 AND transition_id = $2",
            practice_id,
            "PR-02",
        )
        assert journal_rows == [], "PR-02's journal append must roll back with the rest of the transaction"
        outbox_rows = await pool.fetch(
            "SELECT 1 FROM garuda_order_outbox WHERE order_id = $1 AND job_type = $2",
            order_id,
            "practice_in_review_email",
        )
        assert outbox_rows == [], "PR-02's outbox enqueue must roll back with the rest of the transaction"

        # Restore and prove the SAME command now succeeds cleanly (not
        # permanently wedged by the reservation row from the failed attempt).
        monkeypatch.setattr(garuda_staff_router.idempotency, "complete", real_complete)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            retry = await client.post(
                f"/api/visa/voa/staff/practices/{practice_id}/transitions",
                headers={
                    "Authorization": _bearer(_ADMIN, "admin"),
                    "Idempotency-Key": "atomic-key-000000000002",
                },
                json={"transition_id": "PR-02"},
            )
        assert retry.status_code == 200, retry.text
        assert retry.json()["state"] == "In review"

    async def test_assign_practice_forced_completion_failure_rolls_back_the_assignment(
        self, pool, order_repository, monkeypatch
    ) -> None:
        """Same atomicity fix, same fault-injection shape, for
        `assignPractice`'s own idempotency.complete call site."""
        await _seed_team_member(pool, _TEAM_A)
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-atomic-assign00", provider_event_id="evt-atomic-assign"
        )
        practice_id = await _practice_id_for(pool, order_id)

        async def _boom(*args, **kwargs):
            raise RuntimeError("simulated crash")

        monkeypatch.setattr(garuda_staff_router.idempotency, "complete", _boom)

        app = _make_app(pool)
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/visa/voa/staff/practices/{practice_id}/assignment",
                headers={
                    "Authorization": _bearer(_ADMIN, "admin"),
                    "Idempotency-Key": "atomic-assign-key-00000001",
                },
                json={"assigned_to": _TEAM_A},
            )
        assert resp.status_code == 500
        row = await pool.fetchrow(
            "SELECT assigned_to FROM garuda_practices WHERE practice_id = $1", practice_id
        )
        assert row["assigned_to"] is None, (
            "the assignment write must roll back together with the failed "
            "idempotency completion"
        )


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

    async def test_assign_to_unknown_email_is_422(self, pool, order_repository) -> None:
        """Round-4 disposition item 2 (Codex finding #2): the ASSIGNMENT
        TARGET must satisfy the same operator registry check as a staff
        caller -- an arbitrary string (typo, client email, ex-employee) must
        never silently succeed."""
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-assign-4220000000", provider_event_id="evt-assign-422"
        )
        practice_id = await _practice_id_for(pool, order_id)
        app = _make_app(pool)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/visa/voa/staff/practices/{practice_id}/assignment",
                headers={
                    "Authorization": _bearer(_ADMIN, "admin"),
                    "Idempotency-Key": "assign-422-key-00000000001",
                },
                json={"assigned_to": "not-a-real-staff-member@balizero.com"},
            )
        assert resp.status_code == 422
        assert resp.json()["code"] == "INVALID_REQUEST"

    async def test_assign_to_inactive_team_member_is_422(
        self, pool, order_repository
    ) -> None:
        """A `team_members` row with `active = FALSE` (departed staff) must
        never become a valid GARUDA assignment target -- guilt+innocence
        pair for `test_assign_to_unknown_email_is_422` (a row that exists
        but is inactive, not merely absent)."""
        inactive_email = "departed-staff@balizero.com"
        await pool.execute(
            "INSERT INTO team_members (id, name, email, pin_hash, role, active) "
            "VALUES ($1, $2, $3, 'test-pin-hash', 'Team Leader', FALSE) "
            "ON CONFLICT (email) DO UPDATE SET active = FALSE",
            uuid.uuid4().hex[:32],
            inactive_email,
            inactive_email,
        )
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-assign-inact0000", provider_event_id="evt-assign-inact"
        )
        practice_id = await _practice_id_for(pool, order_id)
        app = _make_app(pool)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/visa/voa/staff/practices/{practice_id}/assignment",
                headers={
                    "Authorization": _bearer(_ADMIN, "admin"),
                    "Idempotency-Key": "assign-inact-key-000000001",
                },
                json={"assigned_to": inactive_email},
            )
        assert resp.status_code == 422
        assert resp.json()["code"] == "INVALID_REQUEST"

    async def test_assign_to_accounting_full_view_role_is_422(
        self, pool, order_repository
    ) -> None:
        """tp1-qwen3.8-max council finding #1 (final-diff review): the
        accounting full-view role (`crm_utils.PRACTICES_EXTRA_VIEW_EMAILS`)
        is READ-only by doctrine, but an ACTIVE `team_members` row with a
        staff role for that email passed the operator-registry check --
        so an admin could assign a practice to accounting, after which the
        accounting user could transition it. The exclusion must hold on the
        TARGET side too, not only on the admin set."""
        from backend.app.utils.crm_utils import PRACTICES_EXTRA_VIEW_EMAILS

        accounting_email = next(iter(PRACTICES_EXTRA_VIEW_EMAILS))
        await _seed_team_member(pool, accounting_email, role="Accounting")
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-assign-acct00000", provider_event_id="evt-assign-acct"
        )
        practice_id = await _practice_id_for(pool, order_id)
        app = _make_app(pool)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/visa/voa/staff/practices/{practice_id}/assignment",
                headers={
                    "Authorization": _bearer(_ADMIN, "admin"),
                    "Idempotency-Key": "assign-acct-key-0000000001",
                },
                json={"assigned_to": accounting_email},
            )
        assert resp.status_code == 422
        assert resp.json()["code"] == "INVALID_REQUEST"

    async def test_accounting_full_view_role_cannot_transition_even_when_assigned(
        self, pool, order_repository
    ) -> None:
        """Guilt half of the same finding: even if a practice row ends up
        with `assigned_to` = the accounting email (legacy data, a direct
        SQL write), the accounting identity must still be refused on every
        staff write -- `can_manage_garuda_practices` excludes it outright,
        it does not merely drop it from the admin set. The refusal lands at
        eligibility time (`_staff_principal_from_role` -> None), so the
        answer is the same 401 `SESSION_REQUIRED` a client-role JWT gets,
        never a practice-scoped 403 that would confirm the identity is a
        recognised staff principal."""
        from backend.app.utils.crm_utils import PRACTICES_EXTRA_VIEW_EMAILS

        accounting_email = next(iter(PRACTICES_EXTRA_VIEW_EMAILS))
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-acct-transit0000", provider_event_id="evt-acct-transit"
        )
        practice_id = await _practice_id_for(pool, order_id)
        await pool.execute(
            "UPDATE garuda_practices SET assigned_to = $1 WHERE practice_id = $2",
            accounting_email,
            practice_id,
        )
        app = _make_app(pool)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/visa/voa/staff/practices/{practice_id}/transitions",
                headers={
                    "Authorization": _bearer(accounting_email, "user"),
                    "Idempotency-Key": "acct-transit-key-000000001",
                },
                json={"transition_id": "PR-02"},
            )
        assert resp.status_code == 401
        assert resp.json()["code"] == "SESSION_REQUIRED"

    async def test_assigned_to_key_absent_is_422_not_unassign(
        self, pool, order_repository
    ) -> None:
        """Cross-family refuter (Gemini) MAJOR finding #2: `body.get(
        "assigned_to")` treats a completely OMITTED key identically to an
        explicit `{"assigned_to": null}` -- both evaluate to `None`. The
        contract's `PracticeAssignmentRequest` declares `assigned_to`
        `required`, so an omitted key must 422, never silently unassign."""
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-assign-omit0000", provider_event_id="evt-assign-omit"
        )
        practice_id = await _practice_id_for(pool, order_id)
        app = _make_app(pool)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/visa/voa/staff/practices/{practice_id}/assignment",
                headers={
                    "Authorization": _bearer(_ADMIN, "admin"),
                    "Idempotency-Key": "assign-omit-key-0000000001",
                },
                json={},
            )
        assert resp.status_code == 422
        assert resp.json()["code"] == "INVALID_REQUEST"

    async def test_assigned_to_explicit_null_still_unassigns(
        self, pool, order_repository
    ) -> None:
        """Guilt+innocence pair for the previous test: an EXPLICIT
        `{"assigned_to": null}` is the real unassign command and must still
        succeed with 200 -- only the OMITTED key is a 422."""
        await _seed_team_member(pool, _TEAM_A)
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-assign-null0000", provider_event_id="evt-assign-null"
        )
        practice_id = await _practice_id_for(pool, order_id)
        app = _make_app(pool)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.post(
                f"/api/visa/voa/staff/practices/{practice_id}/assignment",
                headers={
                    "Authorization": _bearer(_ADMIN, "admin"),
                    "Idempotency-Key": "assign-null-key-0000000001",
                },
                json={"assigned_to": _TEAM_A},
            )
            assert first.status_code == 200, first.text
            resp = await client.post(
                f"/api/visa/voa/staff/practices/{practice_id}/assignment",
                headers={
                    "Authorization": _bearer(_ADMIN, "admin"),
                    "Idempotency-Key": "assign-null-key-0000000002",
                },
                json={"assigned_to": None},
            )
        assert resp.status_code == 200, resp.text
        assert resp.json()["assigned_to"] is None

    async def test_admin_assigns_then_assignee_can_see_it_others_cannot(
        self, pool, order_repository
    ) -> None:
        await _seed_team_member(pool, _TEAM_B)
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

    async def test_assignment_log_never_contains_the_raw_staff_email(
        self, pool, order_repository, caplog
    ) -> None:
        """Cross-family refuter (Codex) MINOR finding #8: `assignPractice`
        logged the target's plaintext email (only log-injection-sanitized,
        never PII-redacted) -- every `logger.*` call here is also a Sentry
        breadcrumb whose PII redaction is per-KEY, not per-VALUE."""
        await _seed_team_member(pool, _TEAM_A)
        order_id = await _create_and_pay_order(
            order_repository, result_id="result-assign-log00000", provider_event_id="evt-assign-log"
        )
        practice_id = await _practice_id_for(pool, order_id)
        app = _make_app(pool)
        transport = ASGITransport(app=app)
        with caplog.at_level("INFO", logger="backend.app.routers.garuda_staff_router"):
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    f"/api/visa/voa/staff/practices/{practice_id}/assignment",
                    headers={
                        "Authorization": _bearer(_ADMIN, "admin"),
                        "Idempotency-Key": "assign-log-key-0000000001",
                    },
                    json={"assigned_to": _TEAM_A},
                )
        assert resp.status_code == 200, resp.text
        for record in caplog.records:
            assert _TEAM_A not in str(record.msg)
            assert _TEAM_A not in str(getattr(record, "assigned_to", ""))

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


@pytest.mark.asyncio
class TestEvidenceIdGloballyUnique:
    """Round-4 disposition item 3 (Codex finding #4 / Gemini finding #3):
    `garuda_practice_evidence`'s composite `UNIQUE(practice_id,
    evidence_id)` never stopped the SAME evidence_id being reused across
    DIFFERENT practices; only the application's own pre-INSERT SELECT did,
    and that SELECT is a TOCTOU check a genuine race can defeat."""

    async def test_db_constraint_rejects_cross_practice_reuse(
        self, pool, order_repository
    ) -> None:
        """Proves the NEW global index exists and is enforced at the
        database layer directly, independent of any application code path
        (including the pre-check `apply_transition` itself runs). Uses two
        real practices from the fixture repository -- `garuda_practices`
        FK-references `garuda_orders`/`garuda_order_journal`, so a
        hand-rolled row would need to satisfy those too."""
        order_a = await _create_and_pay_order(
            order_repository, result_id="result-evid-db-a0000000", provider_event_id="evt-evid-db-a"
        )
        order_b = await _create_and_pay_order(
            order_repository, result_id="result-evid-db-b0000000", provider_event_id="evt-evid-db-b"
        )
        practice_a = await _practice_id_for(pool, order_a)
        practice_b = await _practice_id_for(pool, order_b)
        # Guarantee the NEW index exists on this test database regardless of
        # whether the local migration runner has already applied 305's
        # current form — same self-heal pattern TestMigration305Idempotent
        # uses; the forward SQL is idempotent (IF NOT EXISTS throughout).
        sql_path = "backend/db/migrations_v2/305_garuda_practices_assignment.sql"
        with open(sql_path, encoding="utf-8") as fh:
            forward_sql = fh.read().split("-- === ROLLBACK ===")[0]
        async with pool.acquire() as conn:
            await conn.execute(forward_sql)
            await conn.execute(
                "INSERT INTO garuda_practice_evidence "
                "(practice_id, transition_id, evidence_id, kind, recorded_by) "
                "VALUES ($1, 'PR-04', $2, 'filing', 'tester@balizero.com')",
                practice_a,
                "shared_evidence_id_00001",
            )
            with pytest.raises(asyncpg.UniqueViolationError):
                await conn.execute(
                    "INSERT INTO garuda_practice_evidence "
                    "(practice_id, transition_id, evidence_id, kind, recorded_by) "
                    "VALUES ($1, 'PR-04', $2, 'filing', 'tester@balizero.com')",
                    practice_b,
                    "shared_evidence_id_00001",
                )

    async def test_router_maps_the_raced_insert_to_422_not_500(
        self, pool, order_repository
    ) -> None:
        """A genuine race: two concurrent PR-04 submissions on two
        DIFFERENT practices, same evidence_id, both dispatched before either
        commits so both pass `apply_transition`'s sequential pre-check.
        Exactly one must succeed (200); the other must get the contract's
        422 INVALID_REQUEST from the caught `UniqueViolationError`, never an
        unhandled 500."""
        sql_path = "backend/db/migrations_v2/305_garuda_practices_assignment.sql"
        with open(sql_path, encoding="utf-8") as fh:
            forward_sql = fh.read().split("-- === ROLLBACK ===")[0]
        async with pool.acquire() as conn:
            await conn.execute(forward_sql)
        order_a = await _create_and_pay_order(
            order_repository, result_id="result-evid-race-a0000", provider_event_id="evt-evid-race-a"
        )
        order_b = await _create_and_pay_order(
            order_repository, result_id="result-evid-race-b0000", provider_event_id="evt-evid-race-b"
        )
        practice_a = await _practice_id_for(pool, order_a)
        practice_b = await _practice_id_for(pool, order_b)

        app = _make_app(pool)
        shared_evidence_id = "raced_evidence_id_000001"

        async def _submit(practice_id: str, idem_key: str):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # PR-02 first, both practices independently -- not part of
                # the race, just getting each to `In_review` so PR-04 is a
                # legal transition.
                await client.post(
                    f"/api/visa/voa/staff/practices/{practice_id}/transitions",
                    headers={
                        "Authorization": _bearer(_ADMIN, "admin"),
                        "Idempotency-Key": f"{idem_key}-pr02",
                    },
                    json={"transition_id": "PR-02"},
                )
                return await client.post(
                    f"/api/visa/voa/staff/practices/{practice_id}/transitions",
                    headers={
                        "Authorization": _bearer(_ADMIN, "admin"),
                        "Idempotency-Key": f"{idem_key}-pr04",
                    },
                    json={"transition_id": "PR-04", "evidence_id": shared_evidence_id},
                )

        import asyncio

        resp_a, resp_b = await asyncio.gather(
            _submit(practice_a, "race-key-a-0000001"), _submit(practice_b, "race-key-b-0000001")
        )
        statuses = sorted([resp_a.status_code, resp_b.status_code])
        assert statuses == [200, 422], (resp_a.status_code, resp_a.text, resp_b.status_code, resp_b.text)
        loser = resp_a if resp_a.status_code == 422 else resp_b
        assert loser.json()["code"] == "INVALID_REQUEST"
