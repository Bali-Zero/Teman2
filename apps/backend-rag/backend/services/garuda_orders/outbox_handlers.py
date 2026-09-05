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

THE FIVE `staff_page_*` HANDLERS (added after the email/CRM/portal weld). Every
money-anomaly page — a duplicate charge, a payment arriving after the order
was already refunded or already terminal, a payment failure worth a human's
attention, a refund issued before any charge existed — goes to **Telegram, to
`TELEGRAM_OWNER_CHAT_ID`**, never WhatsApp. That is not a style choice: SYMBIOSIS
Law 2's one named WhatsApp-to-assigned-team-member derogation caps its payload
at name+initial, `client_id` and a deadline, and a money-anomaly page needs an
order id, an amount and a provider charge id — it does not fit inside that cap.
Telegram to the owner chat carries none of that name+initial shape and needs no
derogation at all. See `_StaffPageHandler` below for the shared load/guard/send
shape and each subclass's docstring for its own paging condition.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

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
from backend.services.wa_copilot.telegram_notifier import send_telegram_message

logger = logging.getLogger("garuda.orders.outbox_handlers")

#: Same env-with-default convention as `GARUDA_MAGIC_LINK_BASE_URL` next door,
#: and the same caveat: a proposed default, not a ratified canonical URL.
TRACKER_BASE_URL_ENV = "GARUDA_TRACKER_BASE_URL"
DEFAULT_TRACKER_BASE_URL = "https://balizero.com/visa/voa/orders"

EMAIL_API_URL_ENV = "INTERNAL_EMAIL_API_URL"
DEFAULT_EMAIL_API_URL = "https://nuzantara-rag.fly.dev/api/notifications/send-email"
EMAIL_API_KEY_ENV = "NUZANTARA_API_KEY"

#: Same env pair `infra/eventbus/meta_dispatcher.py` and this repo's other
#: Telegram alerters already use — no new secret name to provision.
TELEGRAM_BOT_TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
TELEGRAM_OWNER_CHAT_ID_ENV = "TELEGRAM_OWNER_CHAT_ID"

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


@dataclass(frozen=True, slots=True)
class LateRefundFacts:
    """What the late-refund confirmation is built from.

    `resolution` comes from the TRIGGERING journal event, never from
    `garuda_orders.late_case_resolution`. That column is ONE value per order
    and migration 284 allows a second case to open once the first is closed
    ("exactly one open case per order AT A TIME"), so a delayed retry of case
    A's job would read case B's resolution and tell the customer about money
    that is not theirs. The journal is append-only, so the event this job was
    enqueued from cannot drift.
    """

    order_id: str
    email: str
    case_type: str
    resolution: str


class LateRefundConfirmationEmailHandler:
    """Sends one "the extra payment came back" email per
    `late_refund_confirmation_email` job — the FOURTEENTH job type, and the
    last one production enqueued with no handler.

    WHY IT WAS MISSED THREE TIMES, which is the part worth keeping. Every
    count of these job types was taken by grepping ``job_type="`` — a LITERAL.
    This one is enqueued at `repository.py:799-805` as

        job_type = ("practice_release" if resolution == "honoured"
                    else "late_refund_confirmation_email")
        await journal.enqueue_outbox(..., job_type=job_type)

    a VARIABLE, invisible to any literal-shaped search. The ledger's own
    prescribed antidote said to widen the search DIRECTORY, and widening the
    directory finds nothing here: the missing half was widening from TEXT to
    SYNTAX (superscar #3, under-match). The coverage test that ships with this
    handler therefore reads the `job_type=` argument from the AST and FAILS
    LOUDLY on a non-literal rather than skipping it.

    NOT A COPY OF `RefundEmailHandler`, and the difference is the guard.
    `RefundEmailHandler` keys on `state == 'refunded'`. `resolve_late_order`
    sets `late_case_open = FALSE` and `late_case_resolution` and leaves `state`
    UNCHANGED, so the order behind this job may be `refunded`, `failed` or
    `expired` — a state guard would be reading a column this transition never
    writes.

    WHAT THIS MAIL MAY AND MAY NOT SAY. Three transitions open a late-payment
    case, and they are not the same story: OP-08 (a real duplicate charge on an
    already-`paid` order), OP-F04 (a payment arriving after the order was
    REFUNDED) and OP-F05 (a payment arriving on a `failed`/`expired` order,
    which has NO earlier successful payment — see that branch's own comment,
    "`provider_charge_id` is NULL here"). The triggering `order.late_resolved`
    event carries only `{"resolution": ...}`, so this handler cannot tell them
    apart. The copy is therefore written to be true on all three and claims
    nothing it cannot know — in particular it does NOT say "a second payment",
    which the first draft did and which is false for OP-F05.

    FAIL-CLOSED, AND DELIBERATELY IN THE OPPOSITE DIRECTION FROM THE STAFF
    PAGES. A missing triggering event RAISES: the journal is append-only, so a
    job whose event does not exist is a contradiction, not a stale read, and
    the one fact this mail asserts would be unverifiable. A resolution that is
    not `refunded_in_full` resolves WITHOUT sending and logs at WARNING naming
    the value read. For a staff page the ambiguous direction is "page anyway"
    — a money anomaly nobody hears about is worse. For a customer email that
    ASSERTS money moved it is the reverse: withholding is the safe side, so
    the log line is the thing that has to be loud.

    NO AMOUNT, for a harder reason than `RefundEmailHandler`'s. There the
    objection was that `price_idr` is the ORDER price rather than a refunded
    amount. Here the sum returned is the EXTRA charge, and nothing in
    `garuda_orders` records what that charge was — `late_case_charge_id` is a
    provider id, not a figure. Naming `price_idr` would name a number that is
    wrong rather than merely unproven.
    """

    _RESOLUTION_WORTH_CONFIRMING = "refunded_in_full"

    def __init__(self, pool: asyncpg.Pool, sender: BrevoEmailSender) -> None:
        self._pool = pool
        self._sender = sender

    async def __call__(self, job: OutboxJob) -> None:
        facts = await self._load(job.order_id, job.journal_event_id)
        if facts is None:
            raise EmailSendFailed(
                f"order {job.order_id} not found for a queued late refund confirmation"
            )

        if facts.resolution != self._RESOLUTION_WORTH_CONFIRMING:
            logger.warning(
                "outbox late_refund_confirmation_email resolved WITHOUT sending: "
                "order %s, triggering event %s recorded resolution %r, not %r — "
                "a refund confirmation would be untrue",
                facts.order_id,
                job.journal_event_id,
                facts.resolution,
                self._RESOLUTION_WORTH_CONFIRMING,
            )
            return

        await self._sender.send(
            to=facts.email,
            # Subject carries the same constraint as the body: it may not
            # commit to "extra"/"second"/"duplicate", which is false on the
            # OP-F05 path (a payment on a failed/expired order, where no
            # earlier one exists). The first draft said "the extra payment"
            # here while the body had already been corrected — the guard
            # test reads the whole request, which is how that was caught.
            subject="Your Bali Zero Visa on Arrival — a payment has been returned",
            html_body=self._body(facts),
        )
        logger.info(
            "outbox late_refund_confirmation_email sent for order %s", facts.order_id
        )

    async def _load(self, order_id: str, journal_event_id: str) -> LateRefundFacts | None:
        async with self._pool.acquire() as conn:
            order_row = await conn.fetchrow(
                """
                SELECT order_id, applicant_email, case_type
                  FROM garuda_orders
                 WHERE order_id = $1
                """,
                order_id,
            )
            if order_row is None:
                return None
            event_row = await conn.fetchrow(
                "SELECT detail FROM garuda_order_journal WHERE event_id = $1",
                journal_event_id,
            )
        if event_row is None:
            raise EmailSendFailed(
                f"journal event {journal_event_id} not found for a queued late "
                f"refund confirmation on order {order_id}"
            )
        raw_detail = event_row["detail"]
        detail = json.loads(raw_detail) if isinstance(raw_detail, str) else (raw_detail or {})
        resolution = detail.get("resolution")
        return LateRefundFacts(
            order_id=order_row["order_id"],
            email=order_row["applicant_email"],
            case_type=order_row["case_type"],
            # Not `str(resolution)`: a dict/list under the key would serialise
            # whole and then merely fail the equality check below — same class
            # of shape `_detail_scalar` refuses for the staff pages. Anything
            # that is not a string is not the sentinel, and "" never equals it.
            resolution=resolution if isinstance(resolution, str) else "",
        )

    @staticmethod
    def _body(facts: LateRefundFacts) -> str:
        base = os.getenv(TRACKER_BASE_URL_ENV, DEFAULT_TRACKER_BASE_URL).rstrip("/")
        tracker = f"{base}/{facts.order_id}"
        # "A SECOND PAYMENT" WOULD BE FALSE ON ONE OF THE THREE PATHS, and the
        # first draft of this copy said exactly that. Three transitions open a
        # late-payment case (repository.py): OP-08, a genuine duplicate charge
        # on an already-`paid` order; OP-F04, a payment landing after the order
        # was REFUNDED; and OP-F05, a payment landing on a `failed`/`expired`
        # order. That third one has NO earlier successful payment at all — the
        # branch's own comment says so, "`provider_charge_id` is NULL here (a
        # failed/expired order never reached OP-02)". Telling that customer a
        # second payment was taken asserts something untrue about their money.
        #
        # The handler cannot tell the three apart: it is triggered by the
        # `order.late_resolved` event, whose `detail` carries only
        # `{"resolution": ...}`, not which case was opened. So the copy is
        # written to be true on ALL THREE rather than guessing — "a payment
        # that should not have been taken" holds for a duplicate, for one after
        # a refund, and for one on a closed order.
        #
        # It also does NOT say "your application is not affected". True for
        # OP-08; misleading for OP-F05, where the application really is failed
        # or expired and the tracker is the honest place to look.
        return (
            "Hello,<br><br>"
            "A payment was taken for your Bali Zero Visa on Arrival "
            f"({facts.case_type}) that should not have been, and we have "
            "returned it.<br><br>"
            "The money goes back to the payment method you used, and follows "
            "your card provider's own timeline to appear on your "
            "statement.<br><br>"
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


# ---------------------------------------------------------------------------
# practice_*_email — the seven staff-transition customer emails (step 8,
# STATE-MACHINE.md rows PR-02..PR-11, garuda_staff_router.py::
# transition_practice via staff_transitions.py::apply_transition)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PracticeTransitionEmailFacts:
    order_id: str
    email: str
    case_type: str
    state: str
    customer_reason_key: str | None
    required_action_key: str | None
    artifact_available: bool


class PracticeTransitionEmailHandler:
    """One instance per PR-02..PR-11 customer-facing transition email —
    `practice_in_review_email` / `_blocked_email` / `_submitted_email` /
    `_approved_email` / `_rejected_email` / `_resumed_email` /
    `_delivered_email` (`staff_transitions.py::apply_transition`'s own
    `job_type` if/elif chain). One class, not seven, because the shape is
    identical: load the practice+order facts by `order_id`, render one
    subject/body pair for THIS instance's transition, send.

    NO PAYLOAD ON THE OUTBOX ROW, same privacy property `PracticeReceivedEmailHandler`
    documents above — `apply_transition` enqueues no payload, so this reads
    `garuda_practices` FRESH at send time rather than trusting anything
    captured when the job was queued. That also means a later transition
    overtaking a still-queued earlier one (retry backlog drains out of
    order) sends the mail matching the practice's CURRENT state, never a
    stale one describing a state the practice has already moved past.

    NO STATE GUARD, unlike `PaymentPaidEmailHandler`'s `_STATES_WORTH_
    CONFIRMING`: every state this handler can be asked to announce
    (`In_review`/`Blocked`/`Submitted`/`Approved`/`Rejected`/`Delivered`) is
    reached only through a staff-driven CAS transition on an already-`paid`
    order (`garuda_practices` rows only exist for paid orders — `practice.py`'s
    own module docstring), so there is no "order refunded out from under
    this practice" race the way `PracticeReceivedEmailHandler` guards
    against on intake — nothing in this codebase moves a practice's state
    on refund.
    """

    def __init__(
        self,
        pool: asyncpg.Pool,
        sender: BrevoEmailSender,
        *,
        job_type: str,
        subject: str,
        body: Callable[[PracticeTransitionEmailFacts], str],
    ) -> None:
        self._pool = pool
        self._sender = sender
        self._job_type = job_type
        self._subject = subject
        self._body = body

    async def __call__(self, job: OutboxJob) -> None:
        facts = await self._load(job.order_id)
        if facts is None:
            raise EmailSendFailed(
                f"order {job.order_id} (or its practice) not found for a queued "
                f"{self._job_type}"
            )
        await self._sender.send(to=facts.email, subject=self._subject, html_body=self._body(facts))
        # order id only — never the address, the name or the passport number.
        logger.info("outbox %s sent for order %s", self._job_type, facts.order_id)

    async def _load(self, order_id: str) -> PracticeTransitionEmailFacts | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT o.order_id, o.applicant_email, o.case_type, p.state,
                       p.customer_reason_key, p.required_action_key, p.artifact_available
                  FROM garuda_orders o
                  JOIN garuda_practices p ON p.order_id = o.order_id
                 WHERE o.order_id = $1
                """,
                order_id,
            )
        if row is None:
            return None
        return PracticeTransitionEmailFacts(
            order_id=row["order_id"],
            email=row["applicant_email"],
            case_type=row["case_type"],
            state=row["state"],
            customer_reason_key=row["customer_reason_key"],
            required_action_key=row["required_action_key"],
            artifact_available=row["artifact_available"],
        )


def _practice_transition_body(message: str) -> Callable[[PracticeTransitionEmailFacts], str]:
    """Same tracker-link body shape `PracticeReceivedEmailHandler._body`
    uses above, parameterized only by the one sentence that differs per
    transition."""

    def _body(facts: PracticeTransitionEmailFacts) -> str:
        base = os.getenv(TRACKER_BASE_URL_ENV, DEFAULT_TRACKER_BASE_URL).rstrip("/")
        tracker = f"{base}/{facts.order_id}"
        return (
            "Hello,<br><br>"
            f"Your Bali Zero Visa on Arrival application ({facts.case_type}) {message}<br><br>"
            "You can follow its progress at any time here:<br><br>"
            f'<a href="{tracker}">Track my application</a><br><br>'
            "— Bali Zero"
        )

    return _body


#: (job_type, subject, message) — the message completes "...application
#: (<case_type>) {message}". Order matches `staff_transitions.py::
#: apply_transition`'s if/elif chain (PR-02, PR-03/05/08, PR-04, PR-06,
#: PR-07, PR-09/10, PR-11).
_PRACTICE_TRANSITION_EMAILS: tuple[tuple[str, str, str], ...] = (
    (
        "practice_in_review_email",
        "Your VOA application is now in review",
        "is now being reviewed by our team.",
    ),
    (
        "practice_blocked_email",
        "Action needed on your VOA application",
        "needs your attention before we can continue — please check your tracker for details.",
    ),
    (
        "practice_submitted_email",
        "Your VOA application has been submitted",
        "has been submitted to immigration.",
    ),
    (
        "practice_approved_email",
        "Your VOA application has been approved",
        "has been approved.",
    ),
    (
        "practice_rejected_email",
        "Update on your VOA application",
        "was not approved — please check your tracker for details.",
    ),
    (
        "practice_resumed_email",
        "Your VOA application is moving again",
        "is being processed again.",
    ),
    (
        "practice_delivered_email",
        "Your VOA document is ready",
        "is complete — your document is ready.",
    ),
)


# ---------------------------------------------------------------------------
# staff_page_* — money-anomaly pages, Telegram to the owner chat
# ---------------------------------------------------------------------------


class StaffPageSendFailed(RuntimeError):
    """The page did not reach Telegram. Raised so the outbox records the attempt."""


class StaffPageOrderMissing(RuntimeError):
    """The outbox row has an FK to `garuda_orders`; its absence means something
    removed an order out from under a queued page. Raised, never swallowed."""


#: Telegram Markdown V1 (the same `parse_mode` `telegram_notifier.py` uses)
#: reserves these four characters. Free-text enum values below (`outcome`,
#: `customer_action`) are machine-generated SCREAMING_SNAKE_CASE and may
#: contain `_`, which an un-escaped message turns into a "can't parse
#: entities" 400 from Telegram — a page that would then fail for a
#: formatting reason having nothing to do with whether Telegram is reachable.
#: NOT applied to order/charge/refund ids below: those are wrapped in
#: backtick code spans instead, and Markdown V1 does not re-parse entities
#: inside a code span — escaping there would only print a stray backslash.
#: Same char set as `telegram_notifier._MARKDOWN_ESCAPE_RE`, reimplemented as
#: a two-line regex rather than imported: that helper is named `_md_escape`
#: (leading underscore, module-private) and the thing worth reusing whole
#: from that module is its retry loop, not this one-liner.
_MARKDOWN_ESCAPE_RE = re.compile(r"([_*`\[])")


def _escape_markdown(text: str) -> str:
    return _MARKDOWN_ESCAPE_RE.sub(r"\\\1", text)


class TelegramStaffPageSender:
    """Posts one money-anomaly page to `TELEGRAM_OWNER_CHAT_ID`. Raises on any
    failure — same invariant as `BrevoEmailSender` next door, for the same
    reason: a handler behind the outbox that swallows a failed send marks the
    job delivered and the page is lost with a green log line.

    WHY `send_telegram_message` IS REUSED, NOT RE-IMPLEMENTED. `wa_copilot/
    telegram_notifier.py::send_telegram_message` already is the exact
    primitive this needs: an injected `httpx.AsyncClient` (Golden Rule #10 —
    built once by whoever wires the worker, never per call), the W55 3-attempt
    backoff (1s/3s/7s), 4xx-no-retry / 5xx-retry semantics, and a plain
    `(bool, error)` return with no side effects. Copying that loop into this
    file would drift the two send paths apart the first time one gets a
    bugfix the other doesn't.

    WHY THE REST OF THAT MODULE IS **NOT** REUSED. `telegram_notifier.py` is a
    scheduled CLI: it SELECTs `action_queue` JOIN `team_members`, dedups
    through Redis, and fans out one DM per owner across many rows in one run.
    None of that fits here — a `staff_page_*` handler is ONE outbox job, ONE
    fixed destination (`TELEGRAM_OWNER_CHAT_ID`, not a per-owner lookup), and
    its failure contract is the *opposite* of that module's sibling
    `owner_cashout/telegram_alert.py::send_alert`, which is explicitly
    "best-effort... never raises". Importing the whole module and only using
    its low-level send function is the correct amount of reuse; wiring this
    handler through its CLI/DB/Redis machinery would be adopting a shape
    built for a different job.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        bot_token: str | None = None,
        chat_id: str | None = None,
    ) -> None:
        self._client = client
        self._bot_token = bot_token if bot_token is not None else os.getenv(TELEGRAM_BOT_TOKEN_ENV, "")
        self._chat_id = chat_id if chat_id is not None else os.getenv(TELEGRAM_OWNER_CHAT_ID_ENV, "")

    async def send(self, *, text: str) -> None:
        if not self._bot_token or not self._chat_id:
            # Raising beats sending nowhere: an unset destination is a
            # deployment fault that should surface as an exhausted job, not
            # as silence — same posture as `BrevoEmailSender`'s empty-key check.
            raise StaffPageSendFailed(
                f"{TELEGRAM_BOT_TOKEN_ENV}/{TELEGRAM_OWNER_CHAT_ID_ENV} not both set; "
                "refusing to page nowhere"
            )
        ok, err = await send_telegram_message(self._client, self._bot_token, self._chat_id, text)
        if not ok:
            raise StaffPageSendFailed(f"telegram send failed: {self._scrub(err)}")

    def _scrub(self, err: str | None) -> str:
        """Strip the bot token out of a borrowed error string before it becomes
        durable text.

        `send_telegram_message` builds its URL as
        `<telegram-api-host>/bot<TOKEN>/sendMessage` — the host is written as a
        placeholder ON PURPOSE: `lint_tg_direct_senders.py` scans TEXTUALLY for
        the real host string and deliberately over-matches a mention in a
        comment, because its rule is "keep that string out of non-gateway files
        entirely" — and its error strings
        from `f"{type(e).__name__}: {e}"` and `resp.text[:200]`. Measured on the
        installed httpx, none of the exceptions that path can raise put the URL
        in their `str()`, and Telegram's own 4xx bodies do not echo the token —
        so this is not a leak being fixed, it is a class being closed. The
        reason it is worth one method: this message does not stay in memory. It
        travels as the raised `StaffPageSendFailed`, `drain_once` catches it and
        calls `logger.exception`, and the traceback — message included — lands in
        the process's log stream, which on Fly is retained and readable by anyone
        with log access.

        CORRECTED 2026-08-28 (cross-family seat, Kimi K3, then verified against
        migration 284): an earlier version of this paragraph said the message
        "becomes the outbox job's `last_error` COLUMN — durable, world-readable
        to anyone with DB read". **There is no such column.**
        `garuda_order_outbox` has exactly `id, order_id, journal_event_id,
        job_type, payload, created_at, dispatched_at, attempts`, and `drain_once`
        writes no error text to the row at all — it only logs. The requirement
        this method serves is unchanged and the durable surface is real; the
        justification named a database column that does not exist, which is the
        worse kind of wrong, because the next reader would have gone looking for
        it. A future httpx or a future error string is still exactly the kind of
        change nobody would think to re-audit from here.
        """

        text = err or "unknown error"
        if self._bot_token:
            # The CHAT ID is deliberately not scrubbed. It is not a secret:
            # `TELEGRAM_OWNER_CHAT_ID` is the owner's own chat id, recorded in
            # this repo's own instructions, and knowing it grants nothing —
            # sending to it requires the bot token, which is what this method
            # exists to protect. Scrubbing it would only make a failed page
            # harder for a human to trace back to a destination.
            bot_id, _, secret = self._bot_token.partition(":")
            # ONE pattern, then one literal — and that is ALL, because every
            # other form was measured DEAD. An exact `replace` of the whole
            # token and a `quote()` replace of its URL-encoded form were both
            # here; removing either changed no test, because this pattern
            # already matches the raw token, the '%3A' form, and a token cut in
            # half by `resp.text[:200]`. What it does NOT match is a body that
            # echoes only the half after the colon — the pattern is anchored on
            # the bot id, which is public and may simply be absent. That is the
            # literal below, and it is the half that actually matters.
            if len(bot_id) >= 8:
                text = re.sub(
                    re.escape(bot_id) + r"(?::|%3A)[A-Za-z0-9_%-]*",
                    "<redacted>",
                    text,
                )
            if len(secret) >= 8:
                text = text.replace(secret, "<redacted>")
            elif not secret and len(self._bot_token) >= 8:
                # No colon at all. The pattern above is anchored on `<id>:` and
                # matches nothing, and there is no "secret half" to replace, so
                # without this the whole token would survive. Telegram tokens
                # always carry the colon, so this guards a FORMAT CHANGE rather
                # than a shape that exists today — it costs one branch.
                text = text.replace(self._bot_token, "<redacted>")
        return text


@dataclass(frozen=True, slots=True)
class OrderAnomalyFacts:
    """What a staff page is built from. `detail` is the triggering journal
    event's own `detail` JSONB — `garuda_order_journal.detail` is documented
    PII-free by construction (284_garuda_orders.sql: "only enums, ids,
    amounts, and dates that are already public per the contract... never
    applicant fields").

    That documented guarantee is NOT what makes this safe, and the handlers do
    not rely on it: each `_compose` reads NAMED keys out of `detail`
    (`second_charge_id`, `outcome`, `customer_action`, ...) and never folds the
    dict itself into the message. So a future transition that puts an applicant
    field in `detail` — the one way that SQL comment could stop being true —
    cannot reach a Telegram message through here without someone also adding
    the key by hand. `test_a_poisoned_journal_detail_does_not_reach_a_page`
    pins exactly that, and pins it the only way it can be pinned: by writing
    applicant fields INTO a real journal `detail` and asserting they do not
    come out the other end. The three PII tests that came before it all seeded
    a PII-FREE `detail`, so folding the whole dict into a page left every one
    of them green — measured, not supposed."""

    order_id: str
    case_type: str
    price_idr: int
    state: str
    late_case_open: bool
    late_case_charge_id: str | None
    #: TRUE when an `order.late_resolved` event exists at or after the event
    #: that triggered THIS job. `late_case_open` is ONE boolean per order and
    #: the contract allows a SECOND case to open after the first is closed
    #: (migration 284: "exactly one open case per order AT A TIME"), so the
    #: flag alone cannot tell "my case is still open" from "my case was closed
    #: and a different one is open now" — and in the second reading a delayed
    #: retry of this job would page about case A while rendering case B's
    #: `late_case_charge_id`. This is derived from the append-only journal, so
    #: it needs no new column and cannot drift from what actually happened.
    case_resolved_since_trigger: bool
    detail: dict[str, Any] = field(default_factory=dict)


def _detail_scalar(detail: dict, key: str) -> str:
    """Render ONE named key of a journal `detail` as a bounded scalar.

    Reading named keys stops an UNREAD key from reaching a page; it does not
    bound what a READ key contains. `str()` of a dict or a list serialises the
    whole structure, so a nested object under `second_charge_id` would go to
    Telegram in full — and `detail` is JSONB, which admits any shape. This
    refuses non-scalars outright and caps the length: a page is for a human to
    act on, and an id that is not an id is itself the anomaly worth seeing.
    """

    value = detail.get(key)
    if value is None or isinstance(value, (dict, list)):
        return "—"
    text = str(value)
    # A BACKTICK IN THE VALUE ENDS THE CODE SPAN THAT WRAPS IT (cross-family
    # seat, Kimi K3, 2026-08-28). Every caller interpolates this into
    # `` `{value}` `` on the theory that Markdown V1 does not re-parse inside a
    # code span — true, but only while the value contains no backtick of its
    # own. One backtick closes the span early, Telegram re-parses the tail,
    # answers 400 "can't parse entities", and `send_telegram_message` treats
    # 4xx as NON-retryable: the handler raises every attempt until the job
    # exhausts, so the page NEVER goes out. That inverts this function's own
    # stated purpose — "an id that is not an id is itself the anomaly worth
    # seeing" — because the malformed value is precisely what makes it unseeable.
    # Stripped, not escaped: a visible marker keeps the anomaly legible while
    # making a breakout structurally impossible.
    text = text.replace("`", "<backtick>")
    return text[:120] if len(text) <= 120 else text[:120] + "…"


def _amount(price_idr: int) -> str:
    # One figure, no split, no arithmetic — see this module's docstring.
    return f"IDR {price_idr:,}".replace(",", ".")


class _StaffPageHandler:
    """Shared load → guard → compose → send shape for all five `staff_page_*`
    handlers. Every subclass overrides `_should_page` (the state-guard
    question) and `_compose` (the message), and carries its own docstring
    explaining both.

    THE ROW NEVER HAS A PAYLOAD. `repository.py` enqueues every one of the
    five with `journal.enqueue_outbox(..., job_type="staff_page_...")` and no
    `payload=` argument, so `job.payload` is always `{}`. Every fact a page
    needs — the amount, the case type, the second/late charge id, the failure
    outcome — is read here from `garuda_orders` (current, mutable state) and
    `garuda_order_journal` (the immutable event that triggered THIS job).
    """

    #: The `job_type` this instance was registered under — used only for
    #: log lines, so a subclass never has to repeat its own name in every
    #: log call.
    job_type: str = ""

    def __init__(self, pool: asyncpg.Pool, sender: TelegramStaffPageSender) -> None:
        self._pool = pool
        self._sender = sender

    async def __call__(self, job: OutboxJob) -> None:
        facts = await self._load(job.order_id, job.journal_event_id)
        if facts is None:
            raise StaffPageOrderMissing(
                f"order {job.order_id} not found for a queued {self.job_type} page"
            )

        if not self._should_page(facts):
            logger.warning(
                "outbox %s resolved WITHOUT paging: order %s late_case_open=%s "
                "resolved_since_trigger=%s — the case behind this page was already "
                "closed (a second case may be open now; this job is not about it)",
                self.job_type,
                facts.order_id,
                facts.late_case_open,
                facts.case_resolved_since_trigger,
            )
            return

        await self._sender.send(text=self._compose(facts))
        # order id only — never the applicant, the address or the passport.
        logger.info("outbox %s paged for order %s", self.job_type, facts.order_id)

    def _should_page(self, facts: OrderAnomalyFacts) -> bool:  # pragma: no cover - overridden
        raise NotImplementedError

    def _compose(self, facts: OrderAnomalyFacts) -> str:  # pragma: no cover - overridden
        raise NotImplementedError

    async def _load(self, order_id: str, journal_event_id: str) -> OrderAnomalyFacts | None:
        async with self._pool.acquire() as conn:
            order_row = await conn.fetchrow(
                """
                SELECT order_id, case_type, price_idr, state,
                       late_case_open, late_case_charge_id
                  FROM garuda_orders
                 WHERE order_id = $1
                """,
                order_id,
            )
            if order_row is None:
                return None
            event_row = await conn.fetchrow(
                "SELECT detail, occurred_at FROM garuda_order_journal WHERE event_id = $1",
                journal_event_id,
            )
            # Was THIS job's case already closed? A resolution recorded at or
            # after the triggering event can only be the resolution OF that
            # event's case or of a later one — either way, this page is about a
            # case a human has already handled. The triggering event's own name
            # is never `order.late_resolved`, so `>=` cannot match itself.
            if event_row is None:
                # FAIL CLOSED. The journal is append-only, so a queued job whose
                # triggering event does not exist is not a stale read — it is a
                # contradiction, and every fact this page would carry
                # (`second_charge_id`, `outcome`, and crucially whether THIS
                # job's case is still open) is then unverifiable. The previous
                # version left `resolved_since = False` and paged anyway, which
                # is precisely the shape that renders the CURRENTLY open case's
                # charge id under an older case's headline.
                raise StaffPageOrderMissing(
                    f"journal event {journal_event_id} not found for a queued "
                    f"{self.job_type} page on order {order_id}"
                )
            resolved_since = bool(
                    await conn.fetchval(
                        """
                        SELECT EXISTS (
                            SELECT 1 FROM garuda_order_journal
                             WHERE aggregate_type = 'order'
                               AND aggregate_id = $1
                               AND event_name = 'order.late_resolved'
                               -- STRICT '>' , not '>=' . There is no monotonic
                               -- column on this journal (`event_id` is TEXT),
                               -- so two events CAN in principle share an
                               -- `occurred_at`. With '>=' a tie suppresses the
                               -- page; with '>' it sends one. Suppressing is
                               -- the worse direction by this lane's own rule —
                               -- a money anomaly nobody is told about beats a
                               -- duplicate page — so the tie is resolved
                               -- toward paging. The triggering event's own name
                               -- is never `order.late_resolved`, so strict '>'
                               -- gives up nothing real.
                               AND occurred_at > $2
                        )
                        """,
                        order_id,
                        event_row["occurred_at"],
                    )
                )
        raw_detail = event_row["detail"] if event_row is not None else None
        detail = json.loads(raw_detail) if isinstance(raw_detail, str) else (raw_detail or {})
        return OrderAnomalyFacts(
            order_id=order_row["order_id"],
            case_type=order_row["case_type"],
            price_idr=order_row["price_idr"],
            state=order_row["state"],
            late_case_open=order_row["late_case_open"],
            late_case_charge_id=order_row["late_case_charge_id"],
            detail=detail,
            case_resolved_since_trigger=resolved_since,
        )

    @staticmethod
    def _tracker_link(order_id: str) -> str:
        # Same tracker the customer email points to (`PaymentPaidEmailHandler.
        # _body`) — there is no separate staff-only order surface in this
        # codebase yet. If one is built, point this at it instead.
        base = os.getenv(TRACKER_BASE_URL_ENV, DEFAULT_TRACKER_BASE_URL).rstrip("/")
        return f"{base}/{order_id}"


class StaffPageDuplicateChargeHandler(_StaffPageHandler):
    """OP-08: a SECOND successful charge landed on an order already `paid`.

    GUARD: `late_case_open`. `repository.py`'s OP-08 branch sets it TRUE the
    same transaction this job is enqueued in; `resolveLateOrder` is the only
    thing that ever sets it back to FALSE. If it is already FALSE by the time
    this job drains, a human already closed the case (through this same page,
    most plausibly) — paging again would be re-reporting a solved problem,
    not lying, but still noise a human learns to ignore. RESOLVED, NOT SENT.

    WHAT IS NOT ON THE ORDER ROW. Unlike OP-F04/OP-F05, the OP-08 branch never
    writes `late_case_charge_id` — only `late_case_open`. The second charge id
    lives ONLY in this event's journal `detail` (`second_charge_id`), which is
    why `_StaffPageHandler._load` reads the journal at all.

    WHY THIS PAGE WARNS AGAINST THE CLOSE PATH (cross-family seat, Kimi K3,
    2026-08-28 — confirmed on disk). An earlier version of this copy said
    "refund the duplicate charge, then close via resolveLateOrder". That
    instruction is actively harmful for OP-08: `resolveLateOrder`'s
    `refunded_in_full` resolution calls the provider against
    `late_case_charge_id`, this branch never writes it, and `resolveLateOrder`
    does not CLEAR it when closing a case — so on a duplicate charge that column
    is NULL (fresh order) or a STALE, already-refunded id from a previous
    OP-F04/OP-F05 case. Following the instruction refunded the wrong money or
    nothing at all.

    The page therefore names the charge and says the automated refund path must
    not be used here. That is the honest thing a page can do; the underlying gap
    is a PRODUCT gap — OP-08 has no complete remediation path, because neither
    `honoured` (semantically "we kept it") nor `refunded_in_full` (refunds the
    wrong id) is a correct close for a duplicate charge. It is ledgered, not
    papered over with copy.
    """

    job_type = "staff_page_duplicate_charge"

    def _should_page(self, facts: OrderAnomalyFacts) -> bool:
        # BOTH halves, not just the flag — see `case_resolved_since_trigger`.
        return facts.late_case_open and not facts.case_resolved_since_trigger

    def _compose(self, facts: OrderAnomalyFacts) -> str:
        second_charge = _detail_scalar(facts.detail, "second_charge_id")
        return (
            "DUPLICATE CHARGE\n\n"
            f"Order: `{facts.order_id}`\n"
            f"Case: {_escape_markdown(facts.case_type)}\n"
            f"Amount already paid once: {_amount(facts.price_idr)}\n"
            f"Second (duplicate) charge id: `{second_charge}`\n\n"
            "A second successful payment landed on an order already marked "
            "paid. Refund the charge named above.\n\n"
            "DO NOT close this one with resolveLateOrder's refund resolution. "
            "It refunds the order's `late_case_charge_id`, and OP-08 never "
            "writes that column — it is either empty or still holds an "
            "already-refunded charge from an earlier case. Refunding through it "
            "would target the wrong money.\n\n"
            f"Order: {self._tracker_link(facts.order_id)}"
        )


def _late_charge_lines(facts: OrderAnomalyFacts) -> str:
    """The charge id of the EVENT that triggered this job, plus a divergence
    warning when the order row records a different one.

    `late_case_charge_id` is ONE column and OP-F04/OP-F05's UPDATE is guarded by
    `AND late_case_open = FALSE`, so a second late payment on the same order
    leaves the column holding the FIRST charge while writing its own event and
    its own page job. Rendering the column alone therefore misidentifies which
    money to give back — see StaffPageLatePaidAfterRefundHandler's docstring.
    """

    event_charge = _detail_scalar(facts.detail, "charge_id")
    row_charge = facts.late_case_charge_id or "—"
    lines = f"Late charge id (this event): `{event_charge}`\n"
    if event_charge != "—" and row_charge != event_charge:
        lines += (
            f"Open case on the order records: `{row_charge}`\n\n"
            "TWO LATE CHARGES. The open remediation case was opened by an "
            "EARLIER late payment, and resolveLateOrder refunds the id it "
            "recorded — so it will NOT refund the charge named above. Refund "
            "that one separately."
        )
    return lines


class StaffPageLatePaidAfterRefundHandler(_StaffPageHandler):
    """OP-F04: a `paid` webhook arrived for an order that had already moved to
    `refunded` (a late Xendit delivery racing a refund, most plausibly).

    GUARD: `late_case_open`, same reasoning as duplicate-charge — the case
    is opened by this same transaction and closed only by `resolveLateOrder`.
    If already closed, RESOLVED, NOT SENT.

    `late_case_charge_id` is used from the ORDER ROW, not the journal detail
    — `repository.py`'s OP-F04 branch writes it there specifically because it
    is NOT `provider_charge_id` (which, on a refunded order, still names the
    ORIGINAL already-refunded charge).

    WHY THIS PAGE RENDERS **TWO** IDS (cross-family seat, Kimi K3, 2026-08-28 —
    confirmed on disk). An earlier version rendered only the ORDER ROW's
    `late_case_charge_id`, arguing that it kept the page and
    `resolveLateOrder`'s refund path pointed at the same id. That argument is
    exactly backwards for the second late payment on the same order.
    `repository.py`'s OP-F04 UPDATE carries `AND late_case_open = FALSE`, so a
    SECOND late `paid` webhook does NOT overwrite the column — but it still
    appends its own journal event (`detail.charge_id` = the second charge) and
    still enqueues its own page job. That job would then have rendered the
    FIRST case's charge id: staff refund a charge already being handled, the
    second charge is never refunded, and the job is marked dispatched so it
    never pages again. Money kept, nobody ever told the right id.

    So the page names the charge of the EVENT THAT TRIGGERED IT (the only place
    the second charge is recorded) and, when that differs from the order row,
    says so and names the consequence — because `resolveLateOrder` refunds the
    ROW's id, so a divergence means its automated refund will miss this charge.
    """

    job_type = "staff_page_late_paid_after_refund"

    def _should_page(self, facts: OrderAnomalyFacts) -> bool:
        # BOTH halves, not just the flag — see `case_resolved_since_trigger`.
        return facts.late_case_open and not facts.case_resolved_since_trigger

    def _compose(self, facts: OrderAnomalyFacts) -> str:
        return (
            "LATE PAYMENT AFTER REFUND\n\n"
            f"Order: `{facts.order_id}`\n"
            f"Case: {_escape_markdown(facts.case_type)}\n"
            f"Amount: {_amount(facts.price_idr)}\n"
            f"{_late_charge_lines(facts)}\n\n"
            "This order was already refunded when a payment for it succeeded. "
            "The customer paid for something already refunded — refund this "
            "late charge too, then close via resolveLateOrder.\n\n"
            f"Order: {self._tracker_link(facts.order_id)}"
        )


class StaffPageLatePaidAfterTerminalHandler(_StaffPageHandler):
    """OP-F05: a `paid` webhook arrived for an order already `failed` or
    `expired` — the customer completed a checkout the system had already
    given up on.

    GUARD: `late_case_open`, identical reasoning to the two handlers above.
    """

    job_type = "staff_page_late_paid_after_terminal"

    def _should_page(self, facts: OrderAnomalyFacts) -> bool:
        # BOTH halves, not just the flag — see `case_resolved_since_trigger`.
        return facts.late_case_open and not facts.case_resolved_since_trigger

    def _compose(self, facts: OrderAnomalyFacts) -> str:
        return (
            "LATE PAYMENT AFTER TERMINAL STATE\n\n"
            f"Order: `{facts.order_id}`\n"
            f"Case: {_escape_markdown(facts.case_type)}\n"
            f"Order state: {_escape_markdown(facts.state)}\n"
            f"Amount: {_amount(facts.price_idr)}\n"
            f"{_late_charge_lines(facts)}\n\n"
            "This order was already failed/expired when a payment for it "
            "succeeded. The customer paid for a checkout the system had "
            "already given up on — decide whether to honour it or refund via "
            "resolveLateOrder.\n\n"
            f"Order: {self._tracker_link(facts.order_id)}"
        )


class StaffPagePaymentFailureHandler(_StaffPageHandler):
    """OP-03: `repository.py` pages only when `event.failure.should_page` is
    true (a subset of failures worth a human's attention, decided upstream in
    `handle_failure_event` — not this handler's call to second-guess).

    NO GUARD — always pages. `handle_failure_event` only fires for an order in
    `awaiting_payment`, moves it to `failed`, and nothing in this repository
    ever moves an order OUT of `failed` again (the DB trigger
    `guard_garuda_order_state_transition` forbids every transition out of a
    terminal state; a late `paid` webhook for a `failed` order takes the
    SEPARATE `staff_page_late_paid_after_terminal` path and never touches
    `state`). There is no "already resolved" reading of this state to guard
    against — the order cannot have moved on.
    """

    job_type = "staff_page_payment_failure"

    def _should_page(self, facts: OrderAnomalyFacts) -> bool:
        # ALWAYS. A cross-family gate read this as a missing suppression
        # ("no mechanism to stop paging after a human closes the case") and it
        # is a misreading worth writing down so it is not re-opened: these two
        # pages report an event that HAPPENED, not a case that is OPEN. There
        # is no closure flag for them to consult — `late_case_open` belongs to
        # the OP-F04/OP-F05/OP-08 remediation cases only — and the outbox marks
        # a job dispatched on success, so a second page can only follow a
        # FAILED send, which is precisely when a human still has not been told.
        return True

    def _compose(self, facts: OrderAnomalyFacts) -> str:
        outcome = _escape_markdown(_detail_scalar(facts.detail, "outcome"))
        customer_action = _escape_markdown(_detail_scalar(facts.detail, "customer_action"))
        return (
            "PAYMENT FAILURE\n\n"
            f"Order: `{facts.order_id}`\n"
            f"Case: {_escape_markdown(facts.case_type)}\n"
            f"Amount: {_amount(facts.price_idr)}\n"
            f"Outcome: {outcome}\n"
            f"Customer action: {customer_action}\n\n"
            "This failure was flagged as worth a human look.\n\n"
            f"Order: {self._tracker_link(facts.order_id)}"
        )


class StaffPageRefundOutOfOrderHandler(_StaffPageHandler):
    """OP-05: a refund event arrived for an order still `awaiting_payment` —
    a refund with no successful charge behind it on our side.

    NO GUARD — always pages. `handle_refund_event`'s OP-05 branch does NOT set
    `late_case_open` (unlike OP-08/OP-F04/OP-F05): there is no charge on this
    order to refund, so `resolveLateOrder`'s refund path has nothing to do
    here and never touches this case. The order moves to `refunded`, which
    `guard_garuda_order_state_transition` treats as a dead end (no transition
    out of `refunded` is ever permitted), so there is nothing for this page to
    have gone stale against.
    """

    job_type = "staff_page_refund_out_of_order"

    def _should_page(self, facts: OrderAnomalyFacts) -> bool:
        # ALWAYS. A cross-family gate read this as a missing suppression
        # ("no mechanism to stop paging after a human closes the case") and it
        # is a misreading worth writing down so it is not re-opened: these two
        # pages report an event that HAPPENED, not a case that is OPEN. There
        # is no closure flag for them to consult — `late_case_open` belongs to
        # the OP-F04/OP-F05/OP-08 remediation cases only — and the outbox marks
        # a job dispatched on success, so a second page can only follow a
        # FAILED send, which is precisely when a human still has not been told.
        return True

    def _compose(self, facts: OrderAnomalyFacts) -> str:
        refund_id = _detail_scalar(facts.detail, "refund_id")
        return (
            "REFUND OUT OF ORDER\n\n"
            f"Order: `{facts.order_id}`\n"
            f"Case: {_escape_markdown(facts.case_type)}\n"
            f"Amount: {_amount(facts.price_idr)}\n"
            f"Refund id: `{refund_id}`\n\n"
            "A refund was issued for an order that was still awaiting "
            "payment — there was no successful charge on our side to refund. "
            "Reconcile with the provider before treating this order as closed.\n\n"
            f"Order: {self._tracker_link(facts.order_id)}"
        )


def build_handlers(
    pool: asyncpg.Pool,
    sender: BrevoEmailSender,
    staff_page_sender: TelegramStaffPageSender | None = None,
) -> dict[str, object]:
    """The registry `drain_once` consumes.

    ALL TWENTY-ONE job types production enqueues are routed: the original
    fourteen (below), plus the SEVEN `practice_*_email` types step 8's
    `staff_transitions.py::apply_transition` enqueues via its own inline
    if/elif `job_type` assignment — `practice_in_review_email`,
    `_blocked_email`, `_submitted_email`, `_approved_email`,
    `_rejected_email`, `_resumed_email`, `_delivered_email`
    (`PracticeTransitionEmailHandler`, one class parameterized seven times
    below, not seven classes). The fourteenth of the original set,
    `late_refund_confirmation_email`, is computed at `repository.py:799-805`
    (`"practice_release" if resolution == "honoured" else
    "late_refund_confirmation_email"`) when a staff member resolves a
    late-payment case by giving the money back.

    THE COUNT IN THIS DOCSTRING WAS WRONG TWICE, and the reason is load-bearing
    for whoever changes it next. Every count of these types was taken by
    grepping `job_type="`, a LITERAL, and that one call site passes a VARIABLE
    — invisible to any literal-shaped search, in three separate artifacts. The
    ledger's own prescribed antidote said to widen the search DIRECTORY, which
    finds nothing here: the missing half was widening from TEXT to SYNTAX
    (superscar #3, under-match). Do not re-derive this number with a grep.
    `test_every_enqueued_job_type_has_a_handler` reads the `job_type=` argument
    from the AST and fails loudly on a non-literal, and that test is the only
    thing entitled to assert the count.

    Nine always: `checkout_ready_email` and `payment_paid_email` (what the
    customer sees while paying), `payment_failed_email` and
    `payment_expired_email` (what the customer sees when paying goes wrong),
    `refund_email` (what the customer sees when money comes back),
    `late_refund_confirmation_email` (what the customer sees when a SECOND
    charge comes back), `practice_release` (what the team sees),
    `portal_invite` (how the customer gets IN) and `practice_received_email`
    (what the customer sees once their application is open with the team).
    `payment_paid_email`,
    `practice_release` and `portal_invite` are enqueued by the SAME transaction
    in `repository.py` when a payment is confirmed; routing only the first of
    those three is what originally produced a paying customer with a
    confirmation email and no work item.

    THE ROUTER IMPORT IS LAZY ON PURPOSE. `send_portal_invite_email` lives in
    `app/routers/portal_invite.py` — the canonical sender, reused whole rather
    than re-implemented — but a service module importing a router at load time
    invites an import cycle through the router package. Binding it here, inside
    the function, keeps the dependency at call time where it is harmless.

    THE FIVE `staff_page_*` JOB TYPES ARE ROUTED ONLY WHEN `staff_page_sender`
    IS GIVEN — the remaining five of the thirteen, the money anomalies (OP-08
    duplicate charge, OP-F04/OP-F05 late payment, OP-03 failure, OP-05
    out-of-order refund). It defaults to `None` so a caller that does not wire
    it keeps the previous behaviour exactly: those five report as `unroutable`,
    are logged by name, keep their full attempt budget, and are picked up
    unharmed once a sender is passed. Pass a `TelegramStaffPageSender` (e.g.
    from `_run_garuda_outbox_scheduler` in `main_api.py`, reusing the SAME
    injected `httpx.AsyncClient` the email sender already owns) to arm them.

    THE CATEGORY OF DELIBERATELY-UNHANDLED JOB TYPES IS NOW EMPTY, and that is
    what finally makes the alarm simple. While one known type was unrouted, an
    `unroutable > 0` alarm would have fired on EVERY drain pass forever for it
    — an unroutable job is never dispatched and its attempt bump is rolled
    back, so it is re-claimed every pass, which is how a real signal gets muted
    (superscar #2). With nothing left on the allowlist the predicate collapses
    to plain `unroutable > 0`, meaning "a NEW job_type nobody routed". Arming
    it is a separate change in `_run_garuda_outbox_scheduler`; it is not this
    one. Note the ordering claim carefully: EMPTY here is asserted by the AST
    coverage test, not by this sentence.

    A ROUTED HANDLER IS STILL NOT AN ARMED ONE. `_run_garuda_outbox_scheduler`
    only spawns if `GARUDA_OUTBOX_CONSUMER_ENABLED` is exactly the string
    "true" (`outbox_consumer.is_consumer_enabled`), and it spawns via
    `asyncio.create_task`, so a failure inside it kills the task alone and
    leaves `/health` answering 200. Nothing routed here is observable from
    outside the process until that changes.
    """

    from backend.app.core.config import settings
    from backend.app.routers.portal_invite import send_portal_invite_email

    handoff = CrmHandoffService(
        order_snapshots=PostgresOrderSnapshotProvider(pool),
        crm_writer=PostgresCrmWriter(pool),
    )
    handlers: dict[str, object] = {
        "checkout_ready_email": CheckoutReadyEmailHandler(pool, sender),
        "payment_paid_email": PaymentPaidEmailHandler(pool, sender),
        "payment_failed_email": PaymentFailedEmailHandler(pool, sender),
        "payment_expired_email": PaymentExpiredEmailHandler(pool, sender),
        "refund_email": RefundEmailHandler(pool, sender),
        "late_refund_confirmation_email": LateRefundConfirmationEmailHandler(
            pool, sender
        ),
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
    for job_type, subject, message in _PRACTICE_TRANSITION_EMAILS:
        handlers[job_type] = PracticeTransitionEmailHandler(
            pool,
            sender,
            job_type=job_type,
            subject=subject,
            body=_practice_transition_body(message),
        )
    if staff_page_sender is not None:
        handlers.update(
            {
                "staff_page_duplicate_charge": StaffPageDuplicateChargeHandler(
                    pool, staff_page_sender
                ),
                "staff_page_late_paid_after_refund": StaffPageLatePaidAfterRefundHandler(
                    pool, staff_page_sender
                ),
                "staff_page_late_paid_after_terminal": StaffPageLatePaidAfterTerminalHandler(
                    pool, staff_page_sender
                ),
                "staff_page_payment_failure": StaffPagePaymentFailureHandler(
                    pool, staff_page_sender
                ),
                "staff_page_refund_out_of_order": StaffPageRefundOutOfOrderHandler(
                    pool, staff_page_sender
                ),
            }
        )
    return handlers


__all__ = [
    "INVITE_CREATED_BY",
    "BrevoEmailSender",
    "CheckoutReadyEmailHandler",
    "CrmPracticeNotWrittenYet",
    "EmailSendFailed",
    "LateRefundConfirmationEmailHandler",
    "LateRefundFacts",
    "OrderAnomalyFacts",
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
    "PracticeTransitionEmailFacts",
    "PracticeTransitionEmailHandler",
    "RefundEmailHandler",
    "StaffPageDuplicateChargeHandler",
    "StaffPageLatePaidAfterRefundHandler",
    "StaffPageLatePaidAfterTerminalHandler",
    "StaffPageOrderMissing",
    "StaffPagePaymentFailureHandler",
    "StaffPageRefundOutOfOrderHandler",
    "StaffPageSendFailed",
    "TelegramStaffPageSender",
    "build_handlers",
]
