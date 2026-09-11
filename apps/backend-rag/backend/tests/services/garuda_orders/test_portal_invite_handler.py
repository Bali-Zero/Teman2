"""`PortalInviteHandler` — a paid order must produce a portal ACCOUNT.

WHY THIS FILE IS MOSTLY ABOUT RAISING. `drain_once` reads a plain return as
delivery. Every collaborator this handler calls has a DIFFERENT failure
convention, and one of them — `ensure_portal_profile` — documents itself as
"never raised". Wiring it naively would stamp `dispatched_at` on a job that
created nothing. So the tests that matter here are the ones that prove the
handler converts each quiet failure into a raise; the happy path is the easy
one.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import logging
import os
import textwrap
import uuid

import asyncpg
import pytest

from backend.services.garuda_orders.outbox_consumer import OutboxJob
from backend.services.garuda_orders.outbox_handlers import (
    INVITE_CREATED_BY,
    CrmPracticeNotWrittenYet,
    PortalInviteHandler,
    PortalInviteUndeliverable,
    PortalProfileNotCreated,
)
from backend.tests.fixtures.prod_shaped_pool import create_prod_shaped_pool

pytestmark = pytest.mark.asyncio

_DSN = os.environ.get("INTAKE_TEST_DSN", "postgresql:///nuzantara_test")

#: Looks like a credential on purpose: several tests assert it never appears.
TOKEN = "tok-NEVERLOGTHIS-000"
EMAIL = "voa.applicant@example.invalid"


# --------------------------------------------------------------------------
# fixtures + doubles
# --------------------------------------------------------------------------


@pytest.fixture
async def pool():
    try:
        p = await create_prod_shaped_pool(_DSN, min_size=1, max_size=4)
    except (OSError, asyncpg.PostgresError) as exc:
        if os.environ.get("CI"):
            pytest.fail(f"no reachable Postgres in CI at {_DSN}: {exc}")
        pytest.skip(f"no reachable Postgres at {_DSN}: {exc}")
        # Unreachable in practice: pytest.fail/skip are NoReturn, so `p` is
        # always bound below. CodeQL can't see that through the pytest API;
        # this `raise` terminates the branch provably and re-raises the
        # connection error if that assumption ever stops being true.
        raise
    try:
        async with p.acquire() as conn:
            await conn.execute(
                "DELETE FROM practices WHERE client_id IN "
                "(SELECT id FROM clients WHERE email LIKE '%@example.invalid')"
            )
            await conn.execute("DELETE FROM clients WHERE email LIKE '%@example.invalid'")
        yield p
    finally:
        await p.close()


class _FakeProfiles:
    """Mirrors `PortalProfileService.ensure_portal_profile`, INCLUDING its
    contract of reporting failure by returning None instead of raising."""

    def __init__(self, member_id: str | None = "member-uuid") -> None:
        self.member_id = member_id
        self.calls: list[tuple] = []

    async def ensure_portal_profile(self, *, client_id, email, full_name):
        self.calls.append((client_id, email, full_name))
        return self.member_id


class _FakeInvites:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def create_invitation(self, *, client_id, email, created_by):
        self.calls.append(
            {"client_id": client_id, "email": email, "created_by": created_by}
        )
        return {
            "client_name": "Voa Applicant",
            "email": email,
            "token": TOKEN,
            "invite_url": f"/portal/register?token={TOKEN}",
        }


class _FakeSend:
    def __init__(self, boom: Exception | None = None) -> None:
        self.boom = boom
        self.calls: list[dict] = []

    async def __call__(self, *, to, client_name, invite_url, db_pool, client_id):
        self.calls.append(
            {"to": to, "client_name": client_name, "invite_url": invite_url,
             "client_id": client_id}
        )
        if self.boom is not None:
            raise self.boom


def _job(journal_event_id: str) -> OutboxJob:
    return OutboxJob(
        id=1,
        order_id="ord_test",
        journal_event_id=journal_event_id,
        job_type="portal_invite",
        payload={},
        attempts=1,
    )


def _digest(journal_event_id: str) -> str:
    return hashlib.sha256(journal_event_id.encode()).hexdigest()


async def _seed(pool, *, email: str | None = EMAIL) -> str:
    """A `clients` row plus the `practices` row the handler keys on."""
    journal_event_id = f"evt_{uuid.uuid4().hex}"
    async with pool.acquire() as conn:
        client_id = await conn.fetchval(
            "INSERT INTO clients (full_name, email) VALUES ($1, $2) RETURNING id",
            "Voa Applicant",
            email,
        )
        await conn.execute(
            "INSERT INTO practices (client_id, source_idempotency_key) VALUES ($1, $2)",
            client_id,
            _digest(journal_event_id),
        )
    return journal_event_id


def _handler(pool, *, profiles=None, invites=None, send=None) -> PortalInviteHandler:
    return PortalInviteHandler(
        pool,
        profiles=profiles or _FakeProfiles(),
        invites=invites or _FakeInvites(),
        send_invite_email=send or _FakeSend(),
        portal_base_url="https://my.balizero.com",
    )


# --------------------------------------------------------------------------
# the quiet failures — the reason this handler exists in this shape
# --------------------------------------------------------------------------


async def test_a_profile_that_was_not_created_raises_instead_of_returning(pool):
    """RED if the None check is dropped. `ensure_portal_profile` swallows its
    own DB errors and returns None, so without this the job is marked
    dispatched and the customer is permanently accountless — with a green log
    line, which is the exact disease the outbox was built to cure."""

    journal_event_id = await _seed(pool)
    profiles = _FakeProfiles(member_id=None)
    invites = _FakeInvites()
    send = _FakeSend()

    with pytest.raises(PortalProfileNotCreated):
        await _handler(pool, profiles=profiles, invites=invites, send=send)(
            _job(journal_event_id)
        )

    # And it must stop there: no token minted, no email sent.
    assert invites.calls == []
    assert send.calls == []


async def test_an_invite_before_its_practice_raises_and_does_not_invent_a_client(pool):
    """Both jobs are enqueued by one transaction and claimed SKIP LOCKED, so
    this one can be claimed FIRST. RED if the handler ever proceeds without the
    practice row — it would have to guess a client, and guessing would attach a
    stranger's payment to an account."""

    profiles, invites, send = _FakeProfiles(), _FakeInvites(), _FakeSend()
    with pytest.raises(CrmPracticeNotWrittenYet):
        await _handler(pool, profiles=profiles, invites=invites, send=send)(
            _job("evt_never_released")
        )

    assert profiles.calls == []
    assert invites.calls == []
    assert send.calls == []


async def test_a_client_with_no_address_raises(pool):
    journal_event_id = await _seed(pool, email=None)
    with pytest.raises(PortalInviteUndeliverable):
        await _handler(pool)(_job(journal_event_id))


async def test_a_failed_send_raises_so_the_job_is_retried(pool):
    journal_event_id = await _seed(pool)
    send = _FakeSend(boom=RuntimeError("brevo down"))
    with pytest.raises(RuntimeError, match="brevo down"):
        await _handler(pool, send=send)(_job(journal_event_id))


# --------------------------------------------------------------------------
# the happy path
# --------------------------------------------------------------------------


async def test_a_paid_order_gets_a_profile_then_an_invitation_then_the_email(pool):
    journal_event_id = await _seed(pool)
    profiles, invites, send = _FakeProfiles(), _FakeInvites(), _FakeSend()

    await _handler(pool, profiles=profiles, invites=invites, send=send)(
        _job(journal_event_id)
    )

    assert len(profiles.calls) == 1
    assert len(invites.calls) == 1
    assert len(send.calls) == 1

    client_id, email, full_name = profiles.calls[0]
    assert email == EMAIL
    assert full_name == "Voa Applicant"

    # The invitation is attributed to the machine path, not to a person who
    # never sent it — `created_by` is an audited column.
    assert invites.calls[0]["created_by"] == INVITE_CREATED_BY
    assert invites.calls[0]["client_id"] == client_id

    sent = send.calls[0]
    assert sent["to"] == EMAIL
    assert sent["client_id"] == client_id
    # The service returns a PATH; the handler is what makes it reachable.
    assert sent["invite_url"] == f"https://my.balizero.com/portal/register?token={TOKEN}"


async def test_the_send_is_the_last_statement_in_the_handler():
    """`create_invitation` expires the previous unused invitation and mints a
    fresh token on every call, so a retry after a DELIVERED email would kill a
    link the customer already holds. Keeping the send last bounds that window
    to a failure of the send itself. RED if anything is appended after it."""

    # Parsed, not grepped: the first version of this guard used a regex and
    # flagged the send call's OWN closing parenthesis as a following statement.
    # The AST knows what a statement is.
    tree = ast.parse(textwrap.dedent(inspect.getsource(PortalInviteHandler.__call__)))
    last = tree.body[0].body[-1]
    assert isinstance(last, ast.Expr), f"last statement is {type(last).__name__}, not the send"
    assert isinstance(last.value, ast.Await)
    call = last.value.value
    assert isinstance(call, ast.Call)
    assert isinstance(call.func, ast.Attribute)
    assert call.func.attr == "_send_invite_email", (
        f"the handler now ends with {call.func.attr}; see this test's docstring"
    )


# --------------------------------------------------------------------------
# the credential must not become an artefact
# --------------------------------------------------------------------------


async def test_no_log_line_carries_the_token_or_the_address(pool, caplog):
    """The token completes registration through a PUBLIC unauthenticated
    endpoint, so a log line holding it is a credential at rest. The address is
    PII (SYMBIOSIS Law 2). Not even the ORDER ID may be logged: SM-G03 bans
    opaque result identifiers from logs regardless of PII status, so the
    handler emits the idempotency digest, as `crm_handoff.py` does.

    SCOPE, STATED SO THIS TEST DOES NOT CLAIM MORE THAN IT PROVES: the sender
    here is a double, so what is asserted is that THIS HANDLER logs neither
    value. It says nothing about the real transport — and the real transport
    does log the address: `app/services/internal_email.py:133` emits
    `"Internal email sent: to=%s ..."` on every successful send, for every
    caller in this codebase, not just this one. That is pre-existing behaviour
    with a blast radius far wider than this PR, so it is reported rather than
    changed here. Do not read a green run of this test as "the address never
    reaches a log".
    """

    journal_event_id = await _seed(pool)
    with caplog.at_level(logging.DEBUG):
        await _handler(pool)(_job(journal_event_id))

    blob = "\n".join(r.getMessage() for r in caplog.records)
    assert TOKEN not in blob
    assert EMAIL not in blob
    assert "Voa Applicant" not in blob


async def test_an_exception_message_never_carries_the_address(pool):
    """A raise travels to logs and to Sentry. RED if a message interpolates
    the applicant's address instead of the client id."""

    journal_event_id = await _seed(pool)
    with pytest.raises(PortalProfileNotCreated) as caught:
        await _handler(pool, profiles=_FakeProfiles(member_id=None))(
            _job(journal_event_id)
        )
    assert EMAIL not in str(caught.value)


# --------------------------------------------------------------------------
# arming — a handler nobody routes to is superscar #2
# --------------------------------------------------------------------------


def test_build_handlers_routes_portal_invite():
    """RED if the class exists but no job_type maps to it. That is precisely
    how `practice_release` sat `unroutable` on every drain pass: every part
    built, the last one never armed."""

    from backend.services.garuda_orders import outbox_handlers

    src = textwrap.dedent(inspect.getsource(outbox_handlers.build_handlers))
    assert '"portal_invite": PortalInviteHandler(' in src


def test_the_paid_transaction_enqueues_portal_invite():
    """The handler is unreachable unless the payment transaction enqueues the
    job. RED if the enqueue is dropped, or moved out of the `payment.paid`
    branch that also enqueues `practice_release`."""

    from backend.services.garuda_orders import repository

    src = inspect.getsource(repository)
    paid_branch = src.split('job_type="payment_paid_email"', 1)[1]
    # Both siblings must be enqueued after it, in the same branch, before the
    # next state's handling begins.
    nxt = paid_branch.split("elif state ==", 1)[0]
    assert 'job_type="practice_release"' in nxt
    assert 'job_type="portal_invite"' in nxt


# --------------------------------------------------------------------------
# the doubles cannot see these — so they are asserted on the SOURCE
# --------------------------------------------------------------------------


def _logged_arg_names(func_or_src) -> set[str]:
    """Every bare name passed as an argument to a `logger.*(...)` call."""
    src = func_or_src if isinstance(func_or_src, str) else inspect.getsource(func_or_src)
    tree = ast.parse(textwrap.dedent(src))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name)):
            continue
        if fn.value.id != "logger":
            continue
        for arg in node.args:
            for sub in ast.walk(arg):
                if isinstance(sub, ast.Name):
                    names.add(sub.id)
                elif isinstance(sub, ast.Attribute):
                    names.add(sub.attr)
    return names


def test_the_invite_service_does_not_log_the_applicants_address():
    """The double in this file never logs, so no test above can see this.

    `InviteService.create_invitation` was written for the human-triggered
    `/api/portal/invite/send` endpoint and logged the address, which was
    unremarkable while a staff member with the address on screen was the only
    caller. The outbox made it UNATTENDED and per-paid-order — a steady stream
    of client PII into a persisted log that no Sentry scrubber touches
    (`_before_send` filters events, not log sinks). RED if it comes back.
    """

    from backend.services.portal.invite_service import InviteService

    assert "email" not in _logged_arg_names(InviteService.create_invitation)


def test_the_handler_logs_the_digest_and_never_the_order_id():
    """SM-G03 bans opaque result identifiers from logs regardless of PII
    status, and `crm_handoff.py` in this same package already complies by
    logging only the idempotency digest. RED if `job.order_id` returns."""

    from backend.services.garuda_orders.outbox_handlers import PortalInviteHandler

    logged = _logged_arg_names(PortalInviteHandler.__call__)
    assert "order_id" not in logged
    assert "digest" in logged
