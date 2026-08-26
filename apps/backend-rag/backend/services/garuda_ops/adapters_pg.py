"""Concrete Postgres adapters for the two L7 handoff ports.

Until this module existed, `OrderSnapshotProvider` and `CrmWriter` had exactly
one kind of implementation anywhere in the repository: in-memory fakes inside
`tests/services/garuda_ops/test_crm_handoff.py`. `garuda_ops` was reachable
from no router, no worker and no script — a protocol-only island. Nothing that
happens to a paying customer produced a CRM row, because no code existed that
could write one.

THE ONE THING THAT MAKES THIS ADAPTER DIFFERENT FROM THE FAKE.
`ports.py::CrmWriter` spells out, at length, that `CrmHandoffService` calls
`find_practice_by_source_idempotency_key` and then `create_client_and_practice`
as two separate awaits — check-then-act, not atomic — and that a REAL adapter
must therefore move the idempotency authority into the database rather than
inherit the safety of a single-threaded fake. That is not decoration: an
adapter that merely mirrored the fake would pass every existing test and still
create two CRM practices for one payment under an ordinary outbox retry.

So `create_client_and_practice` never trusts its own prior SELECT. It runs one
transaction that ends in `INSERT ... ON CONFLICT DO NOTHING RETURNING id`
against the partial unique index added by migration 288, and on conflict it
re-reads. The re-read is safe under READ COMMITTED (asyncpg's default, and the
only level this adapter is written for): `ON CONFLICT DO NOTHING` waits on a
concurrent inserter's speculative lock rather than skipping past it blindly, and
the following statement takes a fresh snapshot, so the committed winner IS
visible. Under REPEATABLE READ the re-read could legitimately find nothing —
hence `IdempotencyRaceLost`, which says exactly that instead of pretending a
row vanished.

WHAT IT WILL NOT DO. `clients.full_name` is NOT NULL. If the snapshot carries
no name, this adapter RAISES rather than writing a placeholder: a CRM row
named after an email local-part is worse than a loud failure, because it looks
like data. Likewise a practice whose originating eligibility check has gone
(retention deletion, or an order whose soft `result_id_ref` points nowhere)
yields `None` with an error log naming the missing id, never a half-built
snapshot with invented fields.

NOT WIRED. Nothing constructs these classes yet. Building the adapter and
arming the path are separate acts.
"""

from __future__ import annotations

import logging
from typing import Any

import asyncpg

from backend.services.garuda_ops.ports import OrderSnapshot

logger = logging.getLogger("garuda.ops.adapters_pg")

#: `created_by` on a practice this adapter writes. Not a human address: the
#: CRM's RBAC reads this column, and attributing an automated write to a person
#: would put a name on work they did not do while also handing them the row.
#: It is a real @balizero.com address so the domain-shaped filters elsewhere in
#: the CRM keep working.
CREATED_BY_GARUDA = "garuda@balizero.com"


class MissingCustomerIdentity(ValueError):
    """The snapshot lacks a field the CRM needs to identify the customer.

    Split into cause-specific subclasses on purpose. A single exception raised
    for BOTH a missing name and a missing email cannot be branched on: a caller
    or an alert would have to parse the message string to learn which field was
    absent, and the class name itself would be lying about half its raise sites.
    Catch this base to mean "the snapshot is not identifiable"; catch a subclass
    to act on the specific gap.
    """


class MissingCustomerName(MissingCustomerIdentity):
    """The snapshot had no `customer_full_name` and the CRM requires one."""


class MissingCustomerEmail(MissingCustomerIdentity):
    """The snapshot had no usable `customer_email` to key the CRM client on.

    "Usable" is what migration 166's partial unique index accepts: a non-NULL,
    non-blank address. A snapshot failing that cannot be deduplicated against an
    existing client, so it is refused rather than written as a fresh row that
    would silently double the customer.
    """


class UnknownPracticeType(ValueError):
    """`practice_type_code` matches no row in the `practice_types` catalogue.

    Refused rather than written with a NULL `practice_type_id`, because a
    practice with no type id is not a degraded CRM row — it is an INVISIBLE
    one. Fifteen-odd CRM list, analytics and dashboard queries join
    `practice_types` on `p.practice_type_id = pt.id` with an INNER join
    (crm_practices, crm_clients, crm_analytics, crm_enhanced,
    crm_interactions, crm_shared_memory, ...), so such a row is silently
    dropped from every one of them. The customer would have paid, the row
    would exist, and no surface in the product would show it — the exact
    failure this adapter was written to end.
    """


class IdempotencyRaceLost(RuntimeError):
    """`ON CONFLICT DO NOTHING` skipped the insert and the winner is invisible.

    Under READ COMMITTED this should be unreachable. It is raised rather than
    swallowed so that an adapter accidentally run inside a REPEATABLE READ
    transaction fails loudly instead of silently returning the wrong practice.
    """


def _normalized_email(raw: str) -> str:
    """Match the CRM's own uniqueness expression.

    `migrations_v2/166` created `uq_clients_email_lower_not_blank` over
    `LOWER(BTRIM(email))`, and `crm/assignment.py::find_client_by_email`
    compares against the same expression with the parameter normalized in
    Python. This adapter normalizes identically so the three agree; a lookup
    that used bare `LOWER(email)` would miss a stored address with trailing
    whitespace and cheerfully create a duplicate client.

    `raw` is typed `str`, and `garuda_orders.applicant_email` is `TEXT NOT NULL`
    (migration 284), so today's only real caller cannot pass None. The guard is
    here anyway because `OrderSnapshot.customer_email: str` is a hint rather than
    an enforced invariant: without it a None would surface as a bare
    `AttributeError` from deep inside the adapter, which the caller could not
    distinguish from a genuine bug in the SQL. Returning "" routes it to the same
    `MissingCustomerEmail` a blank address gets — one failure, one name.
    """

    if raw is None:
        return ""
    return raw.strip().lower()


class PostgresOrderSnapshotProvider:
    """Resolves a PR-01 **practice** aggregate id to the CRM prefill data.

    The join is `garuda_practices -> garuda_orders -> garuda_voa_check_results`.
    The middle hop exists because a PR-01 envelope carries only the practice id
    (the port's docstring is explicit that this is not a bare order lookup); the
    last hop exists because purpose, nationality and entry date live on the
    eligibility check, not on the order. `garuda_orders.result_id_ref` is a
    deliberate SOFT reference across lanes (no FK — see migration 284), so that
    hop is a LEFT JOIN and its absence is a real, reportable condition rather
    than a crash.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get(self, practice_aggregate_id: str) -> OrderSnapshot | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT o.order_id,
                       o.applicant_email,
                       o.applicant_full_name,
                       o.case_type,
                       o.price_idr,
                       r.result_id,
                       r.purpose,
                       r.nationality,
                       r.entry_date
                  FROM garuda_practices AS p
                  JOIN garuda_orders    AS o ON o.order_id = p.order_id
             LEFT JOIN garuda_voa_check_results AS r ON r.result_id = o.result_id_ref
                 WHERE p.practice_id = $1
                """,
                practice_aggregate_id,
            )

        if row is None:
            logger.warning(
                "no practice/order found for practice_aggregate_id=%s",
                practice_aggregate_id,
            )
            return None

        if row["result_id"] is None:
            # The order survives but its eligibility check does not. Retention
            # deletion is the expected cause. Returning a snapshot with guessed
            # purpose/nationality/entry_date would put fiction in the CRM.
            logger.error(
                "practice %s has an order whose eligibility check is gone; "
                "cannot build a snapshot without inventing fields",
                practice_aggregate_id,
            )
            return None

        return OrderSnapshot(
            order_aggregate_id=row["order_id"],
            customer_email=row["applicant_email"],
            customer_full_name=row["applicant_full_name"],
            case_type=row["case_type"],
            purpose=row["purpose"],
            nationality=row["nationality"],
            entry_date=row["entry_date"],
            price_idr=row["price_idr"],
            # `garuda_voa_check_results` (migration 286) does NOT carry
            # submit_by_date — only the legacy `garuda_voa_checks` table does,
            # and this flow writes the former. It is left None rather than
            # re-derived from `published_filing_deadline`: the two are
            # different dates (the published D-7 checkpoint versus the internal
            # operating-calendar commitment computed by `intake.build_verdict`),
            # and asserting an equivalence nobody has verified is how a
            # plausible invention becomes a fact downstream.
            submit_by_date=None,
            assigned_to=None,
        )


class PostgresCrmWriter:
    """Creates the CRM client + practice for one GARUDA order, exactly once."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def find_practice_by_source_idempotency_key(
        self, source_idempotency_key: str
    ) -> int | None:
        async with self._pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT id FROM practices WHERE source_idempotency_key = $1",
                source_idempotency_key,
            )

    async def create_client_and_practice(
        self,
        snapshot: OrderSnapshot,
        *,
        source_idempotency_key: str,
        practice_type_code: str,
    ) -> int:
        # `source_idempotency_key: str` is a HINT, not a check, and a falsy key
        # is wrong in TWO different directions — which is why this is a runtime
        # raise and not a comment. Measured against the real partial index
        # (`WHERE source_idempotency_key IS NOT NULL`):
        #
        #   NULL  -> outside the index, arbitrates against nothing, so one
        #            payment retried N times becomes N practices.
        #   ""    -> INSIDE the index (a blank string is NOT NULL), so it DOES
        #            arbitrate — and every blank-key order in the system
        #            collapses onto ONE shared practice.
        #
        # An earlier version of this comment asserted only the first and
        # claimed a blank string "inserts every single time". That is false,
        # and the collision case it missed is the worse of the two: it is
        # silent AND lossy. Neither is acceptable, so both are refused here.
        if not source_idempotency_key or not source_idempotency_key.strip():
            raise ValueError(
                f"order {snapshot.order_aggregate_id}: source_idempotency_key is "
                "empty; a NULL key escapes the partial unique index and duplicates, "
                "a blank string sits inside it and collides with every other blank "
                "key — refusing before either can happen"
            )

        if not snapshot.customer_full_name or not snapshot.customer_full_name.strip():
            raise MissingCustomerName(
                f"order {snapshot.order_aggregate_id} has no customer_full_name; "
                "refusing to write a CRM client with a fabricated name"
            )

        async with self._pool.acquire() as conn, conn.transaction():
            # BOTH columns, resolved the same way `crm_practices.py` resolves
            # them for a human-created practice. Writing only the CODE and
            # leaving `practice_type_id` NULL was the first draft, and it was
            # wrong twice over: `crm/models.py` declares the column NOT NULL
            # (only `scripts/ci_bootstrap_schema.py` drops that for CI, so no
            # test in this suite could ever have seen the violation), and even
            # where it is nullable the row would be invisible — see
            # `UnknownPracticeType` for the INNER-join census.
            practice_type_id = await conn.fetchval(
                "SELECT id FROM practice_types WHERE code = $1", practice_type_code
            )
            if practice_type_id is None:
                raise UnknownPracticeType(
                    f"practice_type_code={practice_type_code!r} is not in the "
                    "practice_types catalogue; refusing to write a practice that "
                    "every CRM list query would silently drop"
                )

            # The type lookup runs BEFORE the client is created, deliberately:
            # an unknown code then leaves nothing behind at all, not even an
            # orphan client whose only practice was refused.
            client_id = await self._ensure_client(conn, snapshot)

            # THE COLUMN SET IS NOT A CHOICE — it is read from the canonical
            # writer, `app/routers/crm_practices.py::create_practice`, which is
            # what a real CRM practice looks like. Discovering these one gate
            # finding at a time is how the first version shipped a row that was
            # invisible for a different reason each round; enumerating them
            # against the one writer that defines the contract ends that.
            #
            # `assigned_to` and `created_by` are the two that matter most, and
            # their absence was the same defect as the missing type id wearing
            # a different column: `crm_practices.py` gates every NON-ADMIN read
            # and write on `created_by = me OR assigned_to = me` (:1225, :1749,
            # :2259, :2357, :2422, and the list filter at :1834). A practice
            # with both NULL is reachable by the three CRM admins and by nobody
            # else — so the team member who has to act on the order cannot see
            # it. `assigned_to` follows the canonical fallback chain: the
            # snapshot's own value, else whoever the CLIENT is assigned to.
            #
            # `inquiry_date` is set explicitly rather than left to its DEFAULT
            # now(): that default exists in CI only because
            # `scripts/ci_bootstrap_schema.py` adds it, so relying on it is
            # relying on the test harness.
            #
            # NOT set here, deliberately, because both are business calls and
            # not this adapter's to invent — see PENDING-ARMS: `status` (a paid
            # VOA is not an "inquiry", but which state the ops workflow wants it
            # to enter at is Zero's call) and `payment_status` (defaults to
            # 'unpaid' on a row created FROM a committed payment.paid event).
            assigned_to = snapshot.assigned_to or await conn.fetchval(
                "SELECT assigned_to FROM clients WHERE id = $1", client_id
            )

            practice_id = await conn.fetchval(
                """
                INSERT INTO practices
                    (client_id, practice_type_id, practice_type_code, title,
                     quoted_price, currency, assigned_to, created_by,
                     inquiry_date, source_idempotency_key)
                VALUES ($1, $2, $3, $4, $5, 'IDR', $6, $7, now(), $8)
                ON CONFLICT (source_idempotency_key)
                    WHERE source_idempotency_key IS NOT NULL
                    DO NOTHING
                RETURNING id
                """,
                client_id,
                practice_type_id,
                practice_type_code,
                self._title_for(snapshot),
                snapshot.price_idr,
                assigned_to,
                CREATED_BY_GARUDA,
                source_idempotency_key,
            )
            if practice_id is not None:
                return int(practice_id)

            # Lost the race — the database, not this code, decided who won.
            existing = await conn.fetchval(
                "SELECT id FROM practices WHERE source_idempotency_key = $1",
                source_idempotency_key,
            )

            # This check MUST stay inside the transaction. It sat one indent
            # level out, which meant the `async with` exited — COMMITTING the
            # client created above — and only then raised, leaving a committed
            # client with no practice. An orphan customer record, produced by
            # the one path this exception exists for, three lines under a
            # comment promising a refusal "leaves nothing behind at all".
            if existing is None:
                raise IdempotencyRaceLost(
                    "INSERT ... ON CONFLICT DO NOTHING skipped the row for "
                    f"source_idempotency_key={source_idempotency_key!r} but the "
                    "conflicting practice is not visible; this adapter requires "
                    "READ COMMITTED isolation"
                )
        logger.info(
            "practice %s already existed for this payment event; no duplicate created",
            existing,
        )
        return int(existing)

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _title_for(snapshot: OrderSnapshot) -> str:
        """No PII: case type and nationality only, never the applicant."""

        return f"GARUDA VOA {snapshot.case_type} ({snapshot.nationality})"

    async def _ensure_client(self, conn: asyncpg.Connection, snapshot: OrderSnapshot) -> int:
        """Find-or-create the client, with the DATABASE deciding the winner.

        Same shape as the practice insert and for the same reason: two payments
        by the same person arriving together must not create two clients. The
        conflict target is migration 166's partial unique index over
        `LOWER(BTRIM(email))`, which is why the inserted value is normalized
        here rather than compared case-insensitively at read time.
        """

        email = _normalized_email(snapshot.customer_email)
        if not email:
            raise MissingCustomerEmail(
                f"order {snapshot.order_aggregate_id} has no usable customer email"
            )

        client_id: Any = await conn.fetchval(
            """
            INSERT INTO clients (full_name, email)
            VALUES ($1, $2)
            ON CONFLICT (LOWER(BTRIM(email)))
                WHERE email IS NOT NULL AND BTRIM(email) <> ''
                DO NOTHING
            RETURNING id
            """,
            snapshot.customer_full_name,
            email,
        )
        if client_id is not None:
            return int(client_id)

        client_id = await conn.fetchval(
            "SELECT id FROM clients WHERE LOWER(BTRIM(email)) = $1", email
        )
        if client_id is None:
            raise IdempotencyRaceLost(
                "client insert was skipped by ON CONFLICT but no client with "
                "that email is visible; this adapter requires READ COMMITTED"
            )
        return int(client_id)


__all__ = [
    "CREATED_BY_GARUDA",
    "IdempotencyRaceLost",
    "MissingCustomerEmail",
    "MissingCustomerIdentity",
    "MissingCustomerName",
    "PostgresCrmWriter",
    "UnknownPracticeType",
    "PostgresOrderSnapshotProvider",
]
