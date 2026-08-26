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
    `unroutable` on every drain pass, forever, and a paying customer got a
    confirmation email and NO work item in the CRM. Superscar #2 exactly: every
    part built, the last one never armed.

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
                canonical_payload_digest=digest,
            ),
        )


def build_handlers(pool: asyncpg.Pool, sender: BrevoEmailSender) -> dict[str, object]:
    """The registry `drain_once` consumes.

    Two job types are routed: `payment_paid_email` (what the customer sees) and
    `practice_release` (what the team sees). Both are enqueued by the SAME
    transaction in `repository.py` when a payment is confirmed, and routing
    only the first is what produced a paying customer with a confirmation email
    and no work item.

    Every other job_type the repository enqueues — `refund_email`,
    `payment_failed_email`, `checkout_ready_email`, `payment_expired_email` and
    the five `staff_page_*` — deliberately has NO entry, so the consumer
    reports them as `unroutable` and logs them by name rather than pretending
    they were delivered. That is the intended state, not an oversight: an
    unrouted job keeps its full attempt budget and is picked up unharmed when
    its handler is written.
    """

    handoff = CrmHandoffService(
        order_snapshots=PostgresOrderSnapshotProvider(pool),
        crm_writer=PostgresCrmWriter(pool),
    )
    return {
        "payment_paid_email": PaymentPaidEmailHandler(pool, sender),
        "practice_release": PracticeReleaseHandler(pool, handoff),
    }


__all__ = [
    "BrevoEmailSender",
    "EmailSendFailed",
    "OrderEmailFacts",
    "PaymentPaidEmailHandler",
    "PracticeNotMinted",
    "PracticeReleaseHandler",
    "build_handlers",
]
