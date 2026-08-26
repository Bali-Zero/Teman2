"""Handlers for `garuda_order_outbox` jobs. Starts with the one a paying
customer actually notices: the payment confirmation email.

Before this module, `payment_paid_email` rows accumulated with no consumer and
no sender. PR #5019 built the drain; this is the first thing it can route to.

THE TRAP THIS MODULE EXISTS TO AVOID, stated first because copying the obvious
neighbour reintroduces it. `garuda_portal/magic_link_store.py::
_default_send_magic_link_email` wraps its whole send in `try/except Exception`
and only logs — correctly, because it is fire-and-forget from inside an HTTP
request path that must return an enumeration-safe 202 whether or not Brevo is
up. A handler behind the outbox has the OPPOSITE obligation: `drain_once`
reads success as "return" and failure as "raise", so a handler that swallows a
failed send marks the job `dispatched_at` and the email is lost with a green
log line. That is precisely the disease the outbox consumer was written to
cure, reintroduced one layer further in. **Everything here raises.**

WHAT IS AND IS NOT IN THE OUTBOX ROW. `repository.py` enqueues
`payment_paid_email` with NO payload — the row carries an order id and nothing
else. That is a privacy property worth keeping, not an omission to fix: the
queue never stores the customer's address, and the handler reads it from
`garuda_orders` at send time. Do not "optimise" the lookup away by denormalising
the email into the payload.

WHAT IS NEVER LOGGED. The recipient address, the applicant name and the
passport number never reach a log line here — order id only (SYMBIOSIS Law 2 /
UU PDP: the frontier is what gets PERSISTED, and a log is persisted).

MONEY SHAPE. `price_idr` is rendered as ONE all-inclusive figure, exactly as
stored. This product must never show a customer a fee/PNBP split (SM-G04: the
price is written once at OP-00 and never recomputed or decomposed), so there is
deliberately no arithmetic anywhere in this file.
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone

import asyncpg
import httpx

from backend.services.garuda_ops.adapters_pg import (
    PostgresCrmWriter,
    PostgresOrderSnapshotProvider,
)
from backend.services.garuda_ops.crm_handoff import CrmHandoffService, HandoffOutcome
from backend.services.garuda_ops.ports import EventEnvelope, IdempotencyIdentity
from backend.services.garuda_orders.outbox_consumer import OutboxJob
from backend.services.portal.invite_service import InviteService
from backend.services.portal.portal_profile_service import PortalProfileService

logger = logging.getLogger("garuda.orders.outbox_handlers")

#: Same env-with-default convention as `GARUDA_MAGIC_LINK_BASE_URL` next door,
#: and the same caveat: a proposed default, not a ratified canonical URL.
TRACKER_BASE_URL_ENV = "GARUDA_TRACKER_BASE_URL"
DEFAULT_TRACKER_BASE_URL = "https://balizero.com/visa/voa/orders"

EMAIL_API_URL_ENV = "INTERNAL_EMAIL_API_URL"
DEFAULT_EMAIL_API_URL = "https://nuzantara-rag.fly.dev/api/notifications/send-email"
EMAIL_API_KEY_ENV = "NUZANTARA_API_KEY"

#: States in which a "we received your payment" email is still the truth.
#: An order that has since been refunded must not be told its payment
#: succeeded — see `PaymentPaidEmailHandler.__call__` for why that is a
#: resolved-not-sent outcome rather than a failure.
_STATES_WORTH_CONFIRMING = frozenset({"paid"})


class EmailSendFailed(RuntimeError):
    """The send did not happen. Raised so the outbox records the attempt."""


@dataclass(frozen=True, slots=True)
class OrderEmailFacts:
    order_id: str
    email: str
    case_type: str
    price_idr: int
    state: str


class BrevoEmailSender:
    """Posts to the internal notifications endpoint. Raises on any failure.

    The sender is `zantara@balizero.com` by fixed rule and is applied by the
    endpoint itself — this class never names a from-address, so there is no
    second place for that rule to drift out of sync.

    The `httpx.AsyncClient` is INJECTED, never built per call: this runs in a
    worker loop, and Golden Rule #10 exists because a client per iteration
    leaks connections. Ownership (and `aclose`) belongs to whatever wires the
    worker.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        api_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._client = client
        self._api_url = api_url or os.getenv(EMAIL_API_URL_ENV, DEFAULT_EMAIL_API_URL)
        self._api_key = api_key if api_key is not None else os.getenv(EMAIL_API_KEY_ENV, "")

    async def send(self, *, to: str, subject: str, html_body: str) -> None:
        if not self._api_key:
            # Raising beats sending unauthenticated: the endpoint would reject
            # it anyway, and a missing key is a deployment fault that should
            # surface as an exhausted job, not as silence.
            raise EmailSendFailed(f"{EMAIL_API_KEY_ENV} is empty; refusing to send unauthenticated")
        try:
            response = await self._client.post(
                self._api_url,
                headers={"X-API-Key": self._api_key},
                json={"to": to, "subject": subject, "body": html_body},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # No response body in the message: it can echo the recipient.
            raise EmailSendFailed(
                f"notifications endpoint returned {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise EmailSendFailed(
                f"notifications endpoint unreachable: {type(exc).__name__}"
            ) from exc


class PaymentPaidEmailHandler:
    """Sends one payment confirmation per `payment_paid_email` outbox job.

    A callable class rather than a closure so the pool and sender are explicit
    dependencies; it satisfies `outbox_consumer.Handler` as-is.
    """

    def __init__(self, pool: asyncpg.Pool, sender: BrevoEmailSender) -> None:
        self._pool = pool
        self._sender = sender

    async def __call__(self, job: OutboxJob) -> None:
        facts = await self._load(job.order_id)

        if facts is None:
            # The outbox row has an FK to garuda_orders, so this is not a
            # normal missing-row case — it means something removed an order
            # out from under a queued job. Raise: it should exhaust and be
            # visible in `count_undrained`, never be marked delivered.
            raise EmailSendFailed(f"order {job.order_id} not found for a queued confirmation")

        if facts.state not in _STATES_WORTH_CONFIRMING:
            # RESOLVED, NOT SENT. The payment genuinely happened — the journal
            # event that produced this job is immutable proof of it — but the
            # order has since moved on (refunded, most plausibly), and telling
            # the customer "your payment succeeded" now would be false.
            #
            # Returning marks the job dispatched. That is the honest reading:
            # the job is finished, not failed, and raising instead would retry
            # a decision that cannot change. It is logged at WARNING because
            # `garuda_order_outbox` has only two terminal shapes — dispatched
            # or not — with no column for "deliberately not sent", so the log
            # is the only place this outcome can be seen. If that ever needs
            # to be countable rather than greppable, it needs a schema change,
            # not a silent convention.
            logger.warning(
                "outbox payment_paid_email resolved WITHOUT sending: order %s is in state %r, "
                "not %s — a payment confirmation would be untrue",
                facts.order_id,
                facts.state,
                sorted(_STATES_WORTH_CONFIRMING),
            )
            return

        await self._sender.send(
            to=facts.email,
            subject="Your Bali Zero Visa on Arrival — payment received",
            html_body=self._body(facts),
        )
        # order id only: never the address, the name or the passport number.
        logger.info("outbox payment_paid_email sent for order %s", facts.order_id)

    async def _load(self, order_id: str) -> OrderEmailFacts | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT order_id, applicant_email, case_type, price_idr, state
                  FROM garuda_orders
                 WHERE order_id = $1
                """,
                order_id,
            )
        if row is None:
            return None
        return OrderEmailFacts(
            order_id=row["order_id"],
            email=row["applicant_email"],
            case_type=row["case_type"],
            price_idr=row["price_idr"],
            state=row["state"],
        )

    @staticmethod
    def _body(facts: OrderEmailFacts) -> str:
        base = os.getenv(TRACKER_BASE_URL_ENV, DEFAULT_TRACKER_BASE_URL).rstrip("/")
        tracker = f"{base}/{facts.order_id}"
        # One figure, no split, no arithmetic — see this module's docstring.
        amount = f"IDR {facts.price_idr:,}".replace(",", ".")
        return (
            "Hello,<br><br>"
            "We've received your payment for your Bali Zero Visa on Arrival "
            f"({facts.case_type}).<br><br>"
            f"<b>Amount paid: {amount}</b><br><br>"
            "Our team is preparing your application now. You can follow its "
            "progress at any time here:<br><br>"
            f'<a href="{tracker}">Track my application</a><br><br>'
            "We'll email you again when there is news.<br><br>"
            "— Bali Zero"
        )


class PracticeNotMinted(RuntimeError):
    """No `garuda_practices` row for this payment event. Raised, never swallowed."""


class PracticeReleaseHandler:
    """Routes the `practice_release` outbox job into the CRM.

    THIS IS THE WELD, and until it existed the chain stopped one link short.
    `repository.py` already does everything up to here in the SAME transaction
    as `payment.paid` (OP-02): it appends the journal event, enqueues BOTH
    `payment_paid_email` and `practice_release`, and calls
    `mint_received_practice` so the `garuda_practices` row exists eagerly.
    `PostgresOrderSnapshotProvider` and `PostgresCrmWriter` have existed since
    the L7 adapters landed. What did not exist was any entry for
    `practice_release` in `build_handlers` — so that job was reported
    `unroutable` on every drain pass, forever, while `payment_paid_email`
    beside it was routed. Superscar #2 exactly: every part built, the last one
    never armed.

    STATED PLAINLY, BECAUSE THE OBVIOUS READING OF THE ABOVE IS WRONG: this does
    NOT yet mean a real customer gets a CRM practice. Measured across the whole
    repository — every `.py`, `.sh`, `.plist`, `.yml`, `.toml` — the ONLY
    references to `drain_once` / `build_handlers` are this module,
    `outbox_consumer.py` and their tests. No cron, no LaunchAgent, no worker and
    no router invokes the drain, so `garuda_order_outbox` is not consumed in
    production AT ALL, and the confirmation email is as undelivered as the
    practice was. Registering this handler removes the last MISSING PART; it
    does not START the machine. Arming a scheduler is a separate, deliberate
    act, and `is_consumer_enabled()` fails closed so that act stays explicit.

    IDENTITY, AND WHY IT IS NOT THE ORDER ID. `garuda_practices.
    source_paid_journal_event_id` is UNIQUE and holds the very
    `journal_event_id` this job carries, so the practice aggregate is looked up
    by the payment event itself — no order->practice correlation is invented,
    and the lookup cannot drift from the thing that authorized the practice.

    THE DIGEST IS DETERMINISTIC ON PURPOSE. `events.yaml` types
    `IdempotencyIdentity.key_digest` as a SHA-256 of the scoped key and never
    the raw key, and `PostgresCrmWriter` stores exactly that digest in
    `practices.source_idempotency_key` under a partial UNIQUE index. Hashing
    the same journal event id always yields the same digest, so a redelivered
    job dedups AT THE DATABASE rather than in this handler's head. Anything
    random or clock-derived here would mint a second practice per retry.
    """

    def __init__(self, pool: asyncpg.Pool, handoff: CrmHandoffService) -> None:
        self._pool = pool
        self._handoff = handoff

    async def __call__(self, job: OutboxJob) -> None:
        practice_id = await self._practice_id_for(job.journal_event_id)
        if practice_id is None:
            # `mint_received_practice` runs in the SAME transaction that
            # enqueued this job, so the row is committed or the job does not
            # exist. Its absence means something deleted a practice out from
            # under a queued release. Raise: it must exhaust and show up under
            # `count_undrained`, never be marked delivered.
            raise PracticeNotMinted(
                f"no garuda_practices row for journal event {job.journal_event_id}"
            )

        result = await self._handoff.handle_practice_received(
            self._envelope(job, practice_id)
        )

        if result.outcome is HandoffOutcome.ORDER_SNAPSHOT_MISSING:
            # The provider already logged WHY (missing order, or an eligibility
            # check lost to retention). Returning would mark this delivered and
            # the order would never reach the CRM at all, so this raises even
            # though a retry may not help: an unworked paid order has to stay
            # countable.
            raise PracticeNotMinted(
                f"no order snapshot behind practice for journal event {job.journal_event_id}"
            )

        # practice id only — never the applicant, the address or the passport.
        logger.info(
            "outbox practice_release %s for order %s (crm practice %s)",
            result.outcome.value,
            job.order_id,
            result.crm_practice_id,
        )

    async def _practice_id_for(self, journal_event_id: str) -> str | None:
        async with self._pool.acquire() as conn:
            return await conn.fetchval(
                """
                SELECT practice_id
                  FROM garuda_practices
                 WHERE source_paid_journal_event_id = $1
                """,
                journal_event_id,
            )

    @staticmethod
    def _envelope(job: OutboxJob, practice_id: str) -> EventEnvelope:
        digest = hashlib.sha256(job.journal_event_id.encode()).hexdigest()
        return EventEnvelope(
            schema_version="1.0.0",
            event_name="practice.received",
            # The outbox row is not the journal event; it is the delivery of
            # one. `event_id` therefore names THIS delivery, while the
            # idempotency identity below names the payment that authorized the
            # practice — which is the distinction ports.py gap 1 exists for.
            event_id=f"outbox:{job.id}",
            occurred_at=datetime.now(tz=timezone.utc),
            aggregate_type="practice",
            aggregate_id=practice_id,
            transition_id="PR-01",
            customer_visible=True,
            idempotency_identity=IdempotencyIdentity(
                kind="DOMAIN_EVENT",
                key_digest=digest,
                # SPEC-CONFORMANCE PLACEHOLDER, not a working conflict detector.
                # `events.yaml` gives this field the job of distinguishing an
                # exact replay from a CONFLICT, which it can only do if it
                # digests the payload. Here it repeats `key_digest`, so it can
                # never tell those apart. Harmless today — nothing downstream
                # reads it; `crm_handoff.py` dedups on `key_digest` alone — but
                # anything that starts reading it must compute it from the
                # payload first, or it will read equality as agreement.
                canonical_payload_digest=digest,
            ),
        )


#: `created_by` on the invitation row. A human email would be a lie — no team
#: member sent this — and the column is audited, so it names the machine path.
INVITE_CREATED_BY = "garuda-voa-outbox"


class CrmPracticeNotWrittenYet(RuntimeError):
    """No `practices` row carries this payment's digest yet."""


class PortalProfileNotCreated(RuntimeError):
    """`ensure_portal_profile` reported failure the only way it can: None."""


class PortalInviteUndeliverable(RuntimeError):
    """The CRM client for this payment has no address to invite."""


class PortalInviteHandler:
    """Routes `portal_invite`: turns a paid order into a portal ACCOUNT.

    THE GAP THIS CLOSES. After `practice_release`, a paying customer has a
    `clients` row (`adapters_pg.py::_ensure_client` upserts it on
    `LOWER(BTRIM(email))`) and a CRM practice. What they did NOT have is any way
    in: measured across the repository, nothing in the GARUDA chain called
    `ensure_portal_profile`, so no `my.balizero.com` account was ever born from
    a payment. The invite machinery itself already existed and is reused whole —
    `InviteService.create_invitation` mints the token, `send_portal_invite_email`
    sends it through the canonical Brevo adapter.

    WHY IT KEYS ON THE PRACTICE AND NOT THE ORDER. The lookup is
    `practices.source_idempotency_key = sha256(journal_event_id)` — the same
    identity chain `PracticeReleaseHandler` writes. That is deliberate: it makes
    the ordering dependency STRUCTURAL instead of hoped-for. Both jobs are
    enqueued by the one `payment.paid` transaction and `drain_once` claims rows
    with `SKIP LOCKED`, so this one can be claimed FIRST. When it is, the row is
    absent and this raises — the job keeps its budget (`DEFAULT_MAX_ATTEMPTS`
    is 5, and `exclude_ids` spreads attempts over passes rather than burning
    them in one) and succeeds on a later pass, after the release landed.

    THE TRAP THAT SHAPED THIS HANDLER. `PortalProfileService.
    ensure_portal_profile` documents itself as "Non-blocking: DB errors are
    caught and logged, never raised" and returns `None` on failure. Behind the
    outbox that behaviour inverts its meaning: `drain_once` reads a plain return
    as delivery, so calling it and returning would stamp `dispatched_at` on a
    job that created NOTHING, and the customer would be permanently accountless
    with a green log line. Hence the explicit `None` check below. Note also its
    `ON CONFLICT (email) DO UPDATE ... WHERE team_members.role = 'client'`: an
    address already present as STAFF matches nothing, returns `None`, and lands
    here as a raise rather than a silent skip — which is the honest outcome,
    because a staff mailbox must not be converted into a client login.

    THE SEND IS LAST, AND NOTHING MAY BE ADDED AFTER IT. `create_invitation` is
    NOT idempotent: it expires any live unused invitation and mints a fresh
    token every call. That is correct while the previous token was never
    delivered, and harmful once it was — a retry would invalidate a link the
    customer already holds. Keeping the send as the final statement bounds that
    window to a failure of the send itself.

    WHAT IS NEVER LOGGED HERE. The invitation token and any URL embedding it are
    the credential that completes registration through a PUBLIC, unauthenticated
    endpoint. They travel to the Brevo email and nowhere else — not a log line,
    not an exception message. The address and the applicant name stay out of
    THIS class's logs too, per the module's standing rule.

    ONE HONEST LIMIT. The canonical transport does not keep that bargain:
    `app/services/internal_email.py:133` logs `"Internal email sent: to=%s ..."`
    on every successful send. So the applicant's address DOES reach a persisted
    log once the email goes out — as it already does for every other caller of
    that helper. Reusing the canonical sender was still the right call over
    re-implementing it, but the property is weaker than this docstring would
    otherwise imply, and it is not this handler's to fix.
    """

    def __init__(
        self,
        pool: asyncpg.Pool,
        *,
        profiles: PortalProfileService,
        invites: InviteService,
        send_invite_email: Callable[..., Awaitable[None]],
        portal_base_url: str,
    ) -> None:
        self._pool = pool
        self._profiles = profiles
        self._invites = invites
        self._send_invite_email = send_invite_email
        self._portal_base_url = portal_base_url

    async def __call__(self, job: OutboxJob) -> None:
        digest = hashlib.sha256(job.journal_event_id.encode()).hexdigest()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT c.id AS client_id, c.full_name, c.email
                  FROM practices p
                  JOIN clients c ON c.id = p.client_id
                 WHERE p.source_idempotency_key = $1
                """,
                digest,
            )

        if row is None:
            raise CrmPracticeNotWrittenYet(
                f"no practices row for the payment behind outbox job {job.id}; "
                "practice_release has not drained yet"
            )

        client_id = int(row["client_id"])
        email = (row["email"] or "").strip()
        if not email:
            raise PortalInviteUndeliverable(
                f"clients row {client_id} has no email; cannot invite"
            )

        member_id = await self._profiles.ensure_portal_profile(
            client_id=client_id,
            email=email,
            full_name=row["full_name"],
        )
        if member_id is None:
            raise PortalProfileNotCreated(
                f"ensure_portal_profile returned None for client {client_id}"
            )

        invitation = await self._invites.create_invitation(
            client_id=client_id,
            email=email,
            created_by=INVITE_CREATED_BY,
        )
        # The DIGEST, not `job.order_id`: STATE-MACHINE.md SM-G03 bans opaque
        # result identifiers from logs regardless of PII status, and
        # `crm_handoff.py` — same package — already logs only this digest for
        # exactly that reason. A first draft of this line logged the order id.
        logger.info("portal invite minted (key=%s)", digest[:12])

        await self._send_invite_email(
            to=email,
            client_name=invitation["client_name"],
            invite_url=f"{self._portal_base_url}{invitation['invite_url']}",
            db_pool=self._pool,
            client_id=client_id,
        )


def build_handlers(pool: asyncpg.Pool, sender: BrevoEmailSender) -> dict[str, object]:
    """The registry `drain_once` consumes.

    Three job types are routed: `payment_paid_email` (what the customer sees),
    `practice_release` (what the team sees) and `portal_invite` (how the
    customer gets IN). All three are enqueued by the SAME transaction in
    `repository.py` when a payment is confirmed, and routing only the first is
    what produced a paying customer with a confirmation email and no work item.

    THE ROUTER IMPORT IS LAZY ON PURPOSE. `send_portal_invite_email` lives in
    `app/routers/portal_invite.py` — the canonical sender, reused whole rather
    than re-implemented — but a service module importing a router at load time
    invites an import cycle through the router package. Binding it here, inside
    the function, keeps the dependency at call time where it is harmless.

    Every other job_type the repository enqueues — `refund_email`,
    `payment_failed_email`, `checkout_ready_email`, `payment_expired_email` and
    the five `staff_page_*` — deliberately has NO entry, so the consumer
    reports them as `unroutable` and logs them by name rather than pretending
    they were delivered. That is the intended state, not an oversight: an
    unrouted job keeps its full attempt budget and is picked up unharmed when
    its handler is written.
    """

    from backend.app.core.config import settings
    from backend.app.routers.portal_invite import send_portal_invite_email

    handoff = CrmHandoffService(
        order_snapshots=PostgresOrderSnapshotProvider(pool),
        crm_writer=PostgresCrmWriter(pool),
    )
    return {
        "payment_paid_email": PaymentPaidEmailHandler(pool, sender),
        "practice_release": PracticeReleaseHandler(pool, handoff),
        "portal_invite": PortalInviteHandler(
            pool,
            profiles=PortalProfileService(pool),
            invites=InviteService(pool),
            send_invite_email=send_portal_invite_email,
            portal_base_url=settings.frontend_portal_url,
        ),
    }


__all__ = [
    "INVITE_CREATED_BY",
    "BrevoEmailSender",
    "CrmPracticeNotWrittenYet",
    "EmailSendFailed",
    "OrderEmailFacts",
    "PaymentPaidEmailHandler",
    "PortalInviteHandler",
    "PortalInviteUndeliverable",
    "PortalProfileNotCreated",
    "PracticeNotMinted",
    "PracticeReleaseHandler",
    "build_handlers",
]
