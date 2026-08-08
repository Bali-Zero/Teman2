"""Shared archive helpers for the kbli_documents cure scripts.

Single source of truth for the ``kbli_documents_archive`` table DDL and
the versioned INSERT. Both ``kbli_documents_cure.py`` and
``kbli_documents_phantom_cure.py`` previously carried identical copies of the
DDL + INSERT — that duplication is how schemas drift (one script upgrades, the
other does not). This module consolidates them.

Versioning model
----------------
The archive was originally ONE-SHOT per code: ``UNIQUE(kode_kbli)`` +
``ON CONFLICT (kode_kbli) DO NOTHING`` meant a second cure of the same code
silently preserved nothing. Migration ``269_kbli_archive_versioning`` adds a
``cure_run`` column and replaces the constraint with
``UNIQUE(kode_kbli, cure_run)`` so each successive cure snapshot survives.

``cure_run`` must be a STABLE per-cure identifier (script name + cure scope /
spec date) — never a wall-clock timestamp, which would make every re-run
"new" and defeat ``ON CONFLICT`` idempotency within the same cure pass.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger("kbli_archive")

#: The migration that upgraded the archive from one-shot to versioned.
_VERSIONING_MIGRATION = "269_kbli_archive_versioning"

#: DDL for a FRESH environment — includes the versioning column and the
#: composite unique constraint that migration 269 introduced. Existing prod
#: tables are upgraded by the migration runner; ``CREATE TABLE IF NOT EXISTS``
#: is a no-op on them (the column/constraint are already there).
ARCHIVE_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS kbli_documents_archive (
    id SERIAL PRIMARY KEY,
    kode_kbli VARCHAR NOT NULL,
    judul TEXT,
    content TEXT,
    metadata JSONB,
    original_created_at TIMESTAMP,
    original_updated_at TIMESTAMP,
    archived_at TIMESTAMP NOT NULL DEFAULT now(),
    archived_reason TEXT NOT NULL DEFAULT
        'kbli_documents_cure: pre-cure fabricated-content snapshot (2026-07-19)',
    cure_run TEXT NOT NULL DEFAULT 'pre-versioning-baseline',
    CONSTRAINT kbli_documents_archive_code_run_key UNIQUE (kode_kbli, cure_run)
)
"""


class _Conn(Protocol):
    """Minimal asyncpg.Connection surface used by the archive helpers."""

    async def execute(self, query: str, *args: Any, **kwargs: Any) -> str: ...

    async def fetchval(self, query: str, *args: Any, **kwargs: Any) -> Any: ...


async def ensure_archive_schema(conn: _Conn) -> None:
    """Create the archive table if absent and verify the live table carries the
    ``cure_run`` column added by migration 269.

    ``CREATE TABLE IF NOT EXISTS`` cannot upgrade an old table — if the table
    was created before migration 269 ran, it will lack ``cure_run`` and the
    composite constraint. Falling back to one-shot semantics in that case is
    exactly the disease being cured, so we fail loud (``RuntimeError`` naming
    the migration) rather than degrade silently.
    """

    await conn.execute(ARCHIVE_TABLE_DDL)

    has_cure_run = await conn.fetchval(
        "SELECT EXISTS ("
        "  SELECT 1 FROM information_schema.columns"
        "  WHERE table_name = 'kbli_documents_archive'"
        "    AND column_name = 'cure_run'"
        ")"
    )
    if not has_cure_run:
        raise RuntimeError(
            "kbli_documents_archive exists but lacks the 'cure_run' column "
            f"(added by migration {_VERSIONING_MIGRATION}). "
            "CREATE TABLE IF NOT EXISTS cannot upgrade an old table — "
            f"run migration {_VERSIONING_MIGRATION} before this script."
        )


async def archive_row(
    conn: _Conn,
    code: str,
    row_params: tuple,
    cure_run: str,
    archived_reason: str | None = None,
) -> None:
    """Insert a versioned archive snapshot of ``code``.

    Parameters
    ----------
    conn:
        An ``asyncpg.Connection`` (or mock with a compatible ``execute``).
    code:
        The KBLI code being archived (informational — ``row_params[0]`` is the
        one actually written; they should match).
    row_params:
        ``(kode, judul, content, metadata_json_str, original_created_at,
        original_updated_at)`` — the byte-exact pre-cure values produced by the
        calling script's own ``archive_params``.
    cure_run:
        Stable per-cure identifier (script name + cure scope/date). Never a
        wall-clock timestamp.
    archived_reason:
        Optional reason override; if ``None`` the table default applies.
    """
    if archived_reason is not None:
        await conn.execute(
            "INSERT INTO kbli_documents_archive "
            "(kode_kbli, judul, content, metadata, original_created_at, "
            " original_updated_at, archived_reason, cure_run) "
            "VALUES ($1, $2, $3, $4::text::jsonb, $5, $6, $7, $8) "
            "ON CONFLICT (kode_kbli, cure_run) DO NOTHING",
            *row_params,
            archived_reason,
            cure_run,
        )
    else:
        await conn.execute(
            "INSERT INTO kbli_documents_archive "
            "(kode_kbli, judul, content, metadata, original_created_at, "
            " original_updated_at, cure_run) "
            "VALUES ($1, $2, $3, $4::text::jsonb, $5, $6, $7) "
            "ON CONFLICT (kode_kbli, cure_run) DO NOTHING",
            *row_params,
            cure_run,
        )
    logger.debug("archive_row %s cure_run=%s", code, cure_run)


__all__ = [
    "ARCHIVE_TABLE_DDL",
    "archive_row",
    "ensure_archive_schema",
]
