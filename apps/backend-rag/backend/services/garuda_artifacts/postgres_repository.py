"""The one real reader/writer of `garuda_practice_artifacts` (migration 312).

`retention_policy_id` / `retention_until` are never supplied by this module
-- the migration's `BEFORE INSERT` trigger
(`bind_garuda_practice_artifact_retention_policy`) derives both from the
active `GARUDA_DOCUMENT` policy and fails the INSERT closed
(`asyncpg.RaiseError`) when none covers the transaction clock. A caller
that wants a friendlier `SERVICE_UNAVAILABLE` before attempting the write
should pre-check `active_garuda_practice_artifact_policy_available` itself
(same two-layer pattern `postgres_store.py` uses for `garuda_documents`);
this repository does not pre-check on the caller's behalf, so its `insert`
can raise a raw `asyncpg.PostgresError` on a policy gap -- callers map that
the same way `garuda_orders_router.py` maps `PersistencePolicyUnavailable`.
"""

from __future__ import annotations

import asyncpg

from backend.services.garuda_artifacts.models import ArtifactRecord
from backend.services.garuda_artifacts.ports import ArtifactAlreadyExists

_SELECT_COLUMNS = """
    artifact_id, practice_id, storage_key, artifact_digest, byte_length,
    content_type, produced_by, environment, created_at, retention_until,
    superseded_at, superseded_by
"""


def _row_to_record(row: asyncpg.Record) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=row["artifact_id"],
        practice_id=row["practice_id"],
        storage_key=row["storage_key"],
        artifact_digest=row["artifact_digest"],
        byte_length=row["byte_length"],
        content_type=row["content_type"],
        produced_by=row["produced_by"],
        environment=row["environment"],
        created_at=row["created_at"],
        retention_until=row["retention_until"],
        superseded_at=row["superseded_at"],
        superseded_by=row["superseded_by"],
    )


class PostgresArtifactRepository:
    """Implements `ArtifactRepositoryPort` (structurally -- no inheritance,
    same convention as this codebase's other Postgres repositories)."""

    async def insert(
        self,
        conn: asyncpg.Connection,
        *,
        artifact_id: str,
        practice_id: str,
        storage_key: str,
        artifact_digest: str,
        byte_length: int,
        content_type: str,
        produced_by: str,
        environment: str,
    ) -> ArtifactRecord:
        try:
            row = await conn.fetchrow(
                f"""
                INSERT INTO garuda_practice_artifacts
                    (artifact_id, practice_id, storage_key, artifact_digest,
                     byte_length, content_type, produced_by, environment)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING {_SELECT_COLUMNS}
                """,
                artifact_id,
                practice_id,
                storage_key,
                artifact_digest,
                byte_length,
                content_type,
                produced_by,
                environment,
            )
        except asyncpg.UniqueViolationError as exc:
            # `artifact_id`'s PK (astronomically unlikely -- 128 random bits
            # from journal.new_opaque_id) or `storage_key`'s UNIQUE. The
            # THIRD historical cause -- `ux_garuda_practice_artifacts_live`'s
            # partial unique index, i.e. a live artifact already exists for
            # this practice -- can no longer reach this method: the service
            # calls `insert_superseding` instead whenever a live row exists
            # (decision #13-revision, "always supersede, never 409"). Both
            # remaining causes are genuine anomalies, not a business
            # conflict -- the router maps this to 500, not 409.
            raise ArtifactAlreadyExists(practice_id) from exc
        return _row_to_record(row)

    async def lock_practice_for_artifact_write(
        self, conn: asyncpg.Connection, *, practice_id: str
    ) -> None:
        """Advisory xact-lock keyed on `practice_id` -- SAME
        `pg_advisory_xact_lock(hashtext($1))` convention `contact_
        autocreate.py`/`crm_delivery.py` already use for this exact class of
        race. Makes two concurrent `putPracticeArtifact` calls for the SAME
        practice mutually exclusive for the transaction's duration.

        Without it: caller B's `get_live_for_practice_locked` can block on
        the SAME physical row caller A is about to supersede; once A
        commits, Postgres re-checks THAT row's new state under EvalPlanQual
        (it does not rescan for a sibling row) and finds `superseded_at IS
        NOT NULL` now, so B's query returns no rows at all -- B would then
        believe no live artifact exists and attempt a plain `insert`, which
        collides with the live row A just inserted. Taking this lock first
        means B's very first statement blocks until A fully commits, so by
        the time B runs `get_live_for_practice_locked` it is a fresh index
        scan that correctly finds A's new live row.
        """
        await conn.execute("SELECT pg_advisory_xact_lock(hashtext($1))", practice_id)

    async def insert_superseding(
        self,
        conn: asyncpg.Connection,
        *,
        old_artifact_id: str,
        artifact_id: str,
        practice_id: str,
        storage_key: str,
        artifact_digest: str,
        byte_length: int,
        content_type: str,
        produced_by: str,
        environment: str,
    ) -> ArtifactRecord:
        """Supersede `old_artifact_id` and insert its replacement, in the
        ORDER `ux_garuda_practice_artifacts_live` (partial, NOT deferrable)
        requires: mark the OLD row superseded FIRST, THEN insert the new
        live row. Inserting first would transiently give the index two live
        rows for the same `practice_id` and fail immediately.

        Caller must already hold `old_artifact_id`'s row lock (via
        `get_live_for_practice_locked`) and the practice's advisory lock
        (via `lock_practice_for_artifact_write`) before calling this.
        """
        await conn.execute(
            """
            UPDATE garuda_practice_artifacts
               SET superseded_at = NOW(), superseded_by = $2
             WHERE artifact_id = $1
            """,
            old_artifact_id,
            artifact_id,
        )
        try:
            row = await conn.fetchrow(
                f"""
                INSERT INTO garuda_practice_artifacts
                    (artifact_id, practice_id, storage_key, artifact_digest,
                     byte_length, content_type, produced_by, environment)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING {_SELECT_COLUMNS}
                """,
                artifact_id,
                practice_id,
                storage_key,
                artifact_digest,
                byte_length,
                content_type,
                produced_by,
                environment,
            )
        except asyncpg.UniqueViolationError as exc:
            # Same residual causes as `insert`'s own catch (PK/storage_key
            # collision) -- `ux_garuda_practice_artifacts_live` cannot fire
            # here since the UPDATE above already cleared the old live row
            # before this INSERT runs.
            raise ArtifactAlreadyExists(practice_id) from exc
        return _row_to_record(row)

    async def move_practice_pointer_if_delivered(
        self, conn: asyncpg.Connection, *, practice_id: str, artifact_id: str, artifact_digest: str
    ) -> bool:
        tag = await conn.execute(
            """
            UPDATE garuda_practices
               SET artifact_id = $2, artifact_digest = $3
             WHERE practice_id = $1 AND artifact_id IS NOT NULL
            """,
            practice_id,
            artifact_id,
            artifact_digest,
        )
        # asyncpg's command tag for UPDATE is "UPDATE <n>" -- n is 1 when
        # the WHERE matched (practice was Delivered), 0 otherwise.
        return tag.split()[-1] != "0"

    async def get_live_for_order(
        self, conn: asyncpg.Connection, *, order_id: str, result_id_ref: str
    ) -> ArtifactRecord | None:
        row = await conn.fetchrow(
            """
            SELECT a.artifact_id, a.practice_id, a.storage_key, a.artifact_digest,
                   a.byte_length, a.content_type, a.produced_by, a.environment,
                   a.created_at, a.retention_until, a.superseded_at, a.superseded_by
              FROM garuda_orders o
              JOIN garuda_practices p ON p.order_id = o.order_id
              JOIN garuda_practice_artifacts a ON a.practice_id = p.practice_id
             WHERE o.order_id = $1
               AND o.result_id_ref = $2
               AND a.superseded_at IS NULL
               AND a.retention_until > clock_timestamp()
            """,
            order_id,
            result_id_ref,
        )
        return _row_to_record(row) if row is not None else None

    async def get_live_for_practice(
        self, conn: asyncpg.Connection, *, practice_id: str
    ) -> ArtifactRecord | None:
        row = await conn.fetchrow(
            f"""
            SELECT {_SELECT_COLUMNS} FROM garuda_practice_artifacts
             WHERE practice_id = $1
               AND superseded_at IS NULL
               AND retention_until > clock_timestamp()
            """,
            practice_id,
        )
        return _row_to_record(row) if row is not None else None

    async def get_live_for_practice_locked(
        self, conn: asyncpg.Connection, *, practice_id: str
    ) -> ArtifactRecord | None:
        # No `retention_until` filter here, deliberately: PR-11 delivers the
        # artifact `putPracticeArtifact` just produced (spec SS3's ordering
        # -- put, THEN deliver), so an artifact freshly inserted is never
        # already past its 30-day retention. Filtering here would just be a
        # second place the same rule could drift from (2)'s trigger.
        row = await conn.fetchrow(
            f"""
            SELECT {_SELECT_COLUMNS} FROM garuda_practice_artifacts
             WHERE practice_id = $1 AND superseded_at IS NULL
             FOR UPDATE
            """,
            practice_id,
        )
        return _row_to_record(row) if row is not None else None
