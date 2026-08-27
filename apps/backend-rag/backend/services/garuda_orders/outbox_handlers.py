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
    # OP-F04/OP-F05: a late `paid` webhook on a terminal order raises this flag
    # and leaves `state` UNCHANGED (migration 284, repository.py:487/517). So a
    # `failed`/`expired` reading alone does NOT mean "no money was taken" — the
    # two handlers that say so in as many words must read this too. No default:
    # a `_load` that forgets the column must fail loudly, not send a lie.
    late_case_open: bool


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
                SELECT order_id, applicant_email, case_type, price_idr, state, late_case_open
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
            late_case_open=row["late_case_open"],
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


class CheckoutReadyEmailHandler:
    """Sends one "your payment link is ready" email per `checkout_ready_email` job.

    ENQUEUED FROM. `repository.py`'s OP-01 transition (`created -> awaiting_payment`)
    enqueues this in the SAME transaction that writes the `checkout_url` into the
    outbox `payload` — the URL is a provider capability, never persisted on
    `garuda_orders` itself (see that call site's own comment), so the payload is
    the ONLY place this handler can read it from.

    STATE GUARD, AND WHY IT DIFFERS FROM THE PAID HANDLER'S. A checkout link is
    true only while the order is still, in fact, awaiting payment: the session
    it points at is provider-side and time-boxed (`checkout_expires_at`), and if
    the order has already moved on — paid, failed, expired, refunded — the link
    is either redundant (a `payment_paid_email` job for the same order is on its
    way) or actively wrong (offering to pay something that can no longer be
    paid). Unlike `PaymentPaidEmailHandler`, whose guard names the ONE state the
    email is a durable receipt of, this guard names the ONE state during which
    the invitation is still live.
    """

    _STATES_WORTH_LINKING = frozenset({"awaiting_payment"})

    def __init__(self, pool: asyncpg.Pool, sender: BrevoEmailSender) -> None:
        self._pool = pool
        self._sender = sender

    async def __call__(self, job: OutboxJob) -> None:
        facts = await self._load(job.order_id)
        if facts is None:
            raise EmailSendFailed(f"order {job.order_id} not found for a queued checkout link")

        if facts.state not in self._STATES_WORTH_LINKING:
            logger.warning(
                "outbox checkout_ready_email resolved WITHOUT sending: order %s is in state %r, "
                "not %s — the checkout link is no longer live",
                facts.order_id,
                facts.state,
                sorted(self._STATES_WORTH_LINKING),
            )
            return

        checkout_url = (job.payload or {}).get("checkout_url")
        if not checkout_url:
            # The enqueue call always carries this key (repository.py OP-01).
            # Its absence means the payload was written or read wrong — raise
            # rather than send a customer an email with no way to pay.
            raise EmailSendFailed(
                f"checkout_ready_email job for order {job.order_id} carries no checkout_url"
            )

        await self._sender.send(
            to=facts.email,
            subject="Your Bali Zero Visa on Arrival — complete your payment",
            html_body=self._body(facts, checkout_url),
        )
        logger.info("outbox checkout_ready_email sent for order %s", facts.order_id)

    async def _load(self, order_id: str) -> OrderEmailFacts | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT order_id, applicant_email, case_type, price_idr, state, late_case_open
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
            late_case_open=row["late_case_open"],
        )

    @staticmethod
    def _body(facts: OrderEmailFacts, checkout_url: str) -> str:
        base = os.getenv(TRACKER_BASE_URL_ENV, DEFAULT_TRACKER_BASE_URL).rstrip("/")
        tracker = f"{base}/{facts.order_id}"
        amount = f"IDR {facts.price_idr:,}".replace(",", ".")
        return (
            "Hello,<br><br>"
            "Your Bali Zero Visa on Arrival application "
            f"({facts.case_type}) is ready for payment.<br><br>"
            f"<b>Amount due: {amount}</b><br><br>"
            f'<a href="{checkout_url}">Complete my payment</a><br><br>'
            "You can also follow this order's status here:<br><br>"
            f'<a href="{tracker}">Track my application</a><br><br>'
            "— Bali Zero"
        )


class PaymentFailedEmailHandler:
    """Sends one "your payment did not go through" email per `payment_failed_email` job.

    STATE GUARD. `handle_failure_event` (repository.py) writes `state = 'failed'`
    only from `awaiting_payment`, and nothing in this codebase ever moves an
    order OUT of `failed` again (a late webhook that pays a failed order sets
    `late_case_open` on the SAME `failed`/`expired` state — see OP-F05 — it
    never flips `state` back).

    CORRECTED after a cross-family gate on this same commit: the paragraph above
    is true and was the WRONG conclusion to draw from it. Precisely BECAUSE a
    late `paid` leaves `state = 'failed'`, the state alone cannot distinguish
    "never charged" from "charged late" — and this email's body says "Amount not
    charged" in as many words. The state guard is therefore not sufficient on
    its own; `late_case_open` is the second, load-bearing half of it.

    CUSTOMER ACTION COPY. The payload carries `customer_action` — one of the
    three values `services/payments/terminal_taxonomy.py::CustomerAction`
    classifies every failure into. This handler renders that closed vocabulary
    into a short next step; an unrecognised value (schema drift, a future enum
    member) falls back to the same generic guidance rather than raising, since
    a slightly generic email is better than a lost one.
    """

    _STATES_WORTH_EXPLAINING = frozenset({"failed"})

    _CUSTOMER_ACTION_COPY: dict[str, str] = {
        "TRY_A_DIFFERENT_CARD": "Please try again with a different card or payment method.",
        "TRY_AGAIN_LATER": "Please try again later.",
        "NONE_ORDER_CLOSED": (
            "This order is now closed. If you still need a Visa on Arrival, "
            "please start a new application."
        ),
    }
    _DEFAULT_ACTION_COPY = "Please try again, or start a new application if the issue continues."

    def __init__(self, pool: asyncpg.Pool, sender: BrevoEmailSender) -> None:
        self._pool = pool
        self._sender = sender

    async def __call__(self, job: OutboxJob) -> None:
        facts = await self._load(job.order_id)
        if facts is None:
            raise EmailSendFailed(f"order {job.order_id} not found for a queued failure email")

        if facts.state not in self._STATES_WORTH_EXPLAINING:
            logger.warning(
                "outbox payment_failed_email resolved WITHOUT sending: order %s is in state %r, "
                "not %s — a failure notice would be stale",
                facts.order_id,
                facts.state,
                sorted(self._STATES_WORTH_EXPLAINING),
            )
            return

        if facts.late_case_open:
            # OP-F05: a late `paid` webhook arrived on this terminal order. The
            # customer WAS charged; `state` stays `failed` by design. Sending
            # "your payment did not go through / Amount not charged" here tells
            # a paying customer their money was not taken. Staff already hold
            # this case (`staff_page_late_paid_after_terminal`) and close it via
            # resolveLateOrder, which sends its own notice — so this job resolves
            # silently rather than racing that with a contradiction.
            logger.warning(
                "outbox payment_failed_email resolved WITHOUT sending: order %s has an OPEN "
                "late-payment case — the customer was charged, a failure notice would be false",
                facts.order_id,
            )
            return

        customer_action = (job.payload or {}).get("customer_action")
        guidance = self._CUSTOMER_ACTION_COPY.get(customer_action, self._DEFAULT_ACTION_COPY)

        await self._sender.send(
            to=facts.email,
            subject="Your Bali Zero Visa on Arrival — payment did not go through",
            html_body=self._body(facts, guidance),
        )
        logger.info("outbox payment_failed_email sent for order %s", facts.order_id)

    async def _load(self, order_id: str) -> OrderEmailFacts | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT order_id, applicant_email, case_type, price_idr, state, late_case_open
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
            late_case_open=row["late_case_open"],
        )

    @staticmethod
    def _body(facts: OrderEmailFacts, guidance: str) -> str:
        base = os.getenv(TRACKER_BASE_URL_ENV, DEFAULT_TRACKER_BASE_URL).rstrip("/")
        tracker = f"{base}/{facts.order_id}"
        amount = f"IDR {facts.price_idr:,}".replace(",", ".")
        return (
            "Hello,<br><br>"
            "We were unable to process your payment for your Bali Zero Visa on "
            f"Arrival ({facts.case_type}).<br><br>"
            f"<b>Amount not charged: {amount}</b><br><br>"
            f"{guidance}<br><br>"
            "You can follow this order's status here:<br><br>"
            f'<a href="{tracker}">Track my application</a><br><br>'
            "— Bali Zero"
        )


class PaymentExpiredEmailHandler:
    """Sends one "your payment session expired" email per `payment_expired_email` job.

    STATE GUARD. `expire_if_unpaid` (repository.py, reconciliation-driven OP-04)
    writes `state = 'expired'` only from `awaiting_payment`, and — same as
    `failed` above — nothing in this codebase ever moves an order back out of
    `expired` (a late payment after expiry sets `late_case_open`, never
    `state`) — which is exactly why the state guard alone is not enough here
    either: this body says "no payment was taken". `late_case_open` is checked
    for the same reason, and with the same consequence, as in
    `PaymentFailedEmailHandler`.
    """

    _STATES_WORTH_EXPLAINING = frozenset({"expired"})

    def __init__(self, pool: asyncpg.Pool, sender: BrevoEmailSender) -> None:
        self._pool = pool
        self._sender = sender

    async def __call__(self, job: OutboxJob) -> None:
        facts = await self._load(job.order_id)
        if facts is None:
            raise EmailSendFailed(f"order {job.order_id} not found for a queued expiry email")

        if facts.state not in self._STATES_WORTH_EXPLAINING:
            logger.warning(
                "outbox payment_expired_email resolved WITHOUT sending: order %s is in state %r, "
                "not %s — an expiry notice would be stale",
                facts.order_id,
                facts.state,
                sorted(self._STATES_WORTH_EXPLAINING),
            )
            return

        if facts.late_case_open:
            # OP-F05, same as the failure handler above: the late `paid` webhook
            # left `state = 'expired'` and raised this flag. The body below says
            # "no payment was taken" — for this order that is untrue.
            logger.warning(
                "outbox payment_expired_email resolved WITHOUT sending: order %s has an OPEN "
                "late-payment case — the customer was charged, an expiry notice would be false",
                facts.order_id,
            )
            return

        await self._sender.send(
            to=facts.email,
            subject="Your Bali Zero Visa on Arrival — payment session expired",
            html_body=self._body(facts),
        )
        logger.info("outbox payment_expired_email sent for order %s", facts.order_id)

    async def _load(self, order_id: str) -> OrderEmailFacts | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT order_id, applicant_email, case_type, price_idr, state, late_case_open
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
            late_case_open=row["late_case_open"],
        )

    @staticmethod
    def _body(facts: OrderEmailFacts) -> str:
        base = os.getenv(TRACKER_BASE_URL_ENV, DEFAULT_TRACKER_BASE_URL).rstrip("/")
        tracker = f"{base}/{facts.order_id}"
        return (
            "Hello,<br><br>"
            "The payment session for your Bali Zero Visa on Arrival application "
            f"({facts.case_type}) expired before it was completed, so no payment "
            "was taken.<br><br>"
            "If you still need a Visa on Arrival, please start a new "
            "application.<br><br>"
            "You can follow this order's status here:<br><br>"
            f'<a href="{tracker}">Track my application</a><br><br>'
            "— Bali Zero"
        )


class RefundEmailHandler:
    """Sends one "your payment was refunded" email per `refund_email` job.

    STATE GUARD. `handle_refund_event` (repository.py) writes `state =
    'refunded'` from either `awaiting_payment` (OP-05, refunded out of order)
    or `paid` (OP-06). Once `refunded`, nothing in this codebase moves the
    state again — a late paid webhook after a refund (OP-F04) sets
    `late_case_open`/`late_case_charge_id`, never `state`. So, as with the
    failed/expired handlers above, `refunded` is a stable terminal reading, and
    the guard is still named rather than assumed.
    """

    _STATES_WORTH_CONFIRMING = frozenset({"refunded"})

    def __init__(self, pool: asyncpg.Pool, sender: BrevoEmailSender) -> None:
        self._pool = pool
        self._sender = sender

    async def __call__(self, job: OutboxJob) -> None:
        facts = await self._load(job.order_id)
        if facts is None:
            raise EmailSendFailed(f"order {job.order_id} not found for a queued refund email")

        if facts.state not in self._STATES_WORTH_CONFIRMING:
            logger.warning(
                "outbox refund_email resolved WITHOUT sending: order %s is in state %r, "
                "not %s — a refund confirmation would be untrue",
                facts.order_id,
                facts.state,
                sorted(self._STATES_WORTH_CONFIRMING),
            )
            return

        await self._sender.send(
            to=facts.email,
            subject="Your Bali Zero Visa on Arrival — payment refunded",
            html_body=self._body(facts),
        )
        logger.info("outbox refund_email sent for order %s", facts.order_id)

    async def _load(self, order_id: str) -> OrderEmailFacts | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT order_id, applicant_email, case_type, price_idr, state, late_case_open
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
            late_case_open=row["late_case_open"],
        )

    @staticmethod
    def _body(facts: OrderEmailFacts) -> str:
        # NO AMOUNT LINE, deliberately. `price_idr` is the ORDER price, not a
        # refunded amount — nothing in `garuda_orders` records what the provider
        # actually returned, and OP-05 refunds an order that reached `refunded`
        # from `awaiting_payment`, i.e. one this flow never marked as charged.
        # Printing `price_idr` here would assert a figure the code cannot know.
        base = os.getenv(TRACKER_BASE_URL_ENV, DEFAULT_TRACKER_BASE_URL).rstrip("/")
        tracker = f"{base}/{facts.order_id}"
        return (
            "Hello,<br><br>"
            "We've refunded your payment for your Bali Zero Visa on Arrival "
            f"({facts.case_type}).<br><br>"
            "The refund goes back to the payment method you used, and follows "
            "your card provider's own timeline to appear on your statement.<br><br>"
            "You can follow this order's status here:<br><br>"
            f'<a href="{tracker}">Track my application</a><br><br>'
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

    STATED PLAINLY, BECAUSE THE OBVIOUS READING OF THE ABOVE IS WRONG — and
    corrected 2026-08-27, because the previous version of this paragraph had
    itself gone stale and misled a repo-wide ground pass that day: registering
    this handler removes the last MISSING PART; it does not START the machine.
    Until #5035 (63bfa19ec) nothing in the repository invoked the drain at all.
    Since #5035 the machine EXISTS: the api lifespan defines
    `_run_garuda_outbox_scheduler` (`backend/app/main_api.py`) and spawns it
    with `asyncio.create_task` at startup — but it ships DARK.
    `is_consumer_enabled()` fails closed on anything but the exact string
    "true" in `GARUDA_OUTBOX_CONSUMER_ENABLED`, so with the variable unset the
    scheduler exits disarmed and `garuda_order_outbox` is still not consumed in
    production. Arming is a separate, deliberate act — one env var, set on
    purpose — and that explicitness is the design, not an accident.

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


class PracticeReceivedEmailHandler:
    """Sends one "your application is now with the team" email per
    `practice_received_email` job.

    ENQUEUED FROM A DIFFERENT MODULE THAN THE OTHER FOUR. This job is written
    by `garuda_portal/practice.py::mint_received_practice`, not
    `garuda_orders/repository.py` — either from L3's eager path (inside the
    SAME transaction as `payment.paid`, OP-02) or from the lazy PR-01
    fallback on a customer's first tracker read. Either way, by the time this
    handler is claimable the `garuda_practices` row it announces is already
    committed: the outbox row and the practice row are written in the same
    transaction (`journal.enqueue_outbox` right after the `INSERT ...
    RETURNING practice_id`), so "queued but no practice row" is the same
    "something deleted state out from under a queued job" shape the other
    handlers in this module raise on, never a race to tolerate.

    NO STATE GUARD ON THE *PRACTICE's* STATE. `garuda_practices.state` only
    ever moves FORWARD from `Received` (module docstring: no PR-02..PR-11
    transition code ships yet, and even once it does the enum has no path
    back to "never happened"). The message here is a receipt of intake, not
    a claim about current PROCESSING status — "we received your application"
    stays true whatever the practice's own state becomes later, the same way
    a shipping "we received your order" notice does not need retracting once
    the order ships.

    THE GUARD IS ON THE *ORDER's* STATE INSTEAD, AND ONLY ON `refunded`'S
    NEIGHBOURHOOD. A practice, once created, is never deleted by anything in
    this codebase — `handle_refund_event` only ever touches `garuda_orders`,
    never `garuda_practices` — so the row this handler reads about is real
    and permanent regardless of what happens to the order next. But telling a
    customer "your application is now open with our team" right after they
    were refunded is a different kind of false than the practice row itself:
    it is not a fact about intake, it reads as an active-service promise, and
    that promise is exactly what a refund closes out. Since a paid order that
    later refunds moves through `paid -> refunded` and never back (same
    terminal-once-reached shape the failed/expired/refunded handlers above
    rely on), the guard names the one state — `paid` — during which the
    "we're on it" framing is still honest, mirroring
    `PaymentPaidEmailHandler`'s own `_STATES_WORTH_CONFIRMING` rather than
    reusing its frozenset object.
    """

    _STATES_WORTH_NOTIFYING = frozenset({"paid"})

    def __init__(self, pool: asyncpg.Pool, sender: BrevoEmailSender) -> None:
        self._pool = pool
        self._sender = sender

    async def __call__(self, job: OutboxJob) -> None:
        facts = await self._load(job.order_id)
        if facts is None:
            # Covers both a missing order and a missing practice row — either
            # way something the outbox row's own transaction should have
            # guaranteed is gone. Raise, exhaust visibly, never mark delivered.
            raise EmailSendFailed(
                f"order {job.order_id} (or its practice) not found for a queued "
                "receipt confirmation"
            )

        if facts.state not in self._STATES_WORTH_NOTIFYING:
            logger.warning(
                "outbox practice_received_email resolved WITHOUT sending: order %s is in "
                "state %r, not %s — the application-is-with-the-team framing is no longer "
                "honest",
                facts.order_id,
                facts.state,
                sorted(self._STATES_WORTH_NOTIFYING),
            )
            return

        await self._sender.send(
            to=facts.email,
            subject="Your Bali Zero Visa on Arrival — application received",
            html_body=self._body(facts),
        )
        # order id only — never the address, the name or the passport number.
        logger.info("outbox practice_received_email sent for order %s", facts.order_id)

    async def _load(self, order_id: str) -> OrderEmailFacts | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT o.order_id, o.applicant_email, o.case_type, o.price_idr, o.state,
                       o.late_case_open
                  FROM garuda_orders o
                  JOIN garuda_practices p ON p.order_id = o.order_id
                 WHERE o.order_id = $1
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
            late_case_open=row["late_case_open"],
        )

    @staticmethod
    def _body(facts: OrderEmailFacts) -> str:
        base = os.getenv(TRACKER_BASE_URL_ENV, DEFAULT_TRACKER_BASE_URL).rstrip("/")
        tracker = f"{base}/{facts.order_id}"
        return (
            "Hello,<br><br>"
            "Your Bali Zero Visa on Arrival application "
            f"({facts.case_type}) has been received and is now open with our "
            "team.<br><br>"
            "You can follow its progress at any time here:<br><br>"
            f'<a href="{tracker}">Track my application</a><br><br>'
            "We'll email you again when there is news.<br><br>"
            "— Bali Zero"
        )


def build_handlers(pool: asyncpg.Pool, sender: BrevoEmailSender) -> dict[str, object]:
    """The registry `drain_once` consumes.

    Eight job types are routed: `checkout_ready_email` and `payment_paid_email`
    (what the customer sees while paying), `payment_failed_email` and
    `payment_expired_email` (what the customer sees when paying goes wrong),
    `refund_email` (what the customer sees when money comes back),
    `practice_release` (what the team sees), `portal_invite` (how the customer
    gets IN) and `practice_received_email` (what the customer sees once their
    application is open with the team). `payment_paid_email`,
    `practice_release` and `portal_invite` are enqueued by the SAME
    transaction in `repository.py` when a payment is confirmed; routing only
    the first of those three is what originally produced a paying customer
    with a confirmation email and no work item.

    THE ROUTER IMPORT IS LAZY ON PURPOSE. `send_portal_invite_email` lives in
    `app/routers/portal_invite.py` — the canonical sender, reused whole rather
    than re-implemented — but a service module importing a router at load time
    invites an import cycle through the router package. Binding it here, inside
    the function, keeps the dependency at call time where it is harmless.

    Every other job_type the repository enqueues — the five `staff_page_*`
    jobs — deliberately has NO entry, so the consumer reports them as
    `unroutable` and logs them by name rather than pretending they were
    delivered. That is the intended state, not an oversight: an unrouted job
    keeps its full attempt budget and is picked up unharmed when its handler
    is written.
    """

    from backend.app.core.config import settings
    from backend.app.routers.portal_invite import send_portal_invite_email

    handoff = CrmHandoffService(
        order_snapshots=PostgresOrderSnapshotProvider(pool),
        crm_writer=PostgresCrmWriter(pool),
    )
    return {
        "checkout_ready_email": CheckoutReadyEmailHandler(pool, sender),
        "payment_paid_email": PaymentPaidEmailHandler(pool, sender),
        "payment_failed_email": PaymentFailedEmailHandler(pool, sender),
        "payment_expired_email": PaymentExpiredEmailHandler(pool, sender),
        "refund_email": RefundEmailHandler(pool, sender),
        "practice_release": PracticeReleaseHandler(pool, handoff),
        "practice_received_email": PracticeReceivedEmailHandler(pool, sender),
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
    "CheckoutReadyEmailHandler",
    "CrmPracticeNotWrittenYet",
    "EmailSendFailed",
    "OrderEmailFacts",
    "PaymentExpiredEmailHandler",
    "PaymentFailedEmailHandler",
    "PaymentPaidEmailHandler",
    "PortalInviteHandler",
    "PortalInviteUndeliverable",
    "PortalProfileNotCreated",
    "PracticeNotMinted",
    "PracticeReceivedEmailHandler",
    "PracticeReleaseHandler",
    "RefundEmailHandler",
    "build_handlers",
]
