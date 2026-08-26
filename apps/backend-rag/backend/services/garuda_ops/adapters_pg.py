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
hence `_IdempotencyRaceLost`, which says exactly that instead of pretending a
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


class MissingCustomerName(ValueError):
    """The snapshot had no `customer_full_name` and the CRM requires one."""


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
    """

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
        if not snapshot.customer_full_name or not snapshot.customer_full_name.strip():
            raise MissingCustomerName(
                f"order {snapshot.order_aggregate_id} has no customer_full_name; "
                "refusing to write a CRM client with a fabricated name"
            )

        async with self._pool.acquire() as conn, conn.transaction():
            client_id = await self._ensure_client(conn, snapshot)

            practice_id = await conn.fetchval(
                """
                INSERT INTO practices
                    (client_id, practice_type_code, title, quoted_price,
                     currency, source_idempotency_key)
                VALUES ($1, $2, $3, $4, 'IDR', $5)
                ON CONFLICT (source_idempotency_key)
                    WHERE source_idempotency_key IS NOT NULL
                    DO NOTHING
                RETURNING id
                """,
                client_id,
                practice_type_code,
                self._title_for(snapshot),
                snapshot.price_idr,
                source_idempotency_key,
            )
            if practice_id is not None:
                return int(practice_id)

            # Lost the race — the database, not this code, decided who won.
            existing = await conn.fetchval(
                "SELECT id FROM practices WHERE source_idempotency_key = $1",
                source_idempotency_key,
            )

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
            raise MissingCustomerName(
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
    "IdempotencyRaceLost",
    "MissingCustomerName",
    "PostgresCrmWriter",
    "PostgresOrderSnapshotProvider",
]
