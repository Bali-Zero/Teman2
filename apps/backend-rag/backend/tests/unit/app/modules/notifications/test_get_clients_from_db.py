"""Regression test for ``get_clients_from_db`` — the visa-expiry subquery
repointed from ``client_documents`` (never provisioned in prod) to
``documents`` (the live table, 2026-08-08), PLUS a second schema mismatch
found by the post-#3798 prove-live pass the same day: the SELECT/WHERE
referenced ``c.preferred_language`` (no such column exists on ``clients``
at all — ground: ``information_schema.columns`` on the live table) and
``c.is_active`` (the live boolean-ish column is ``status``, a varchar with
values 'lead'/'active'/'prospect'/'inactive'). Both raised
``asyncpg.UndefinedColumnError`` and were unreachable from CI because every
test here mocks the DB connection — nothing in this suite ever validated the
SQL text against a real schema.

Both live callers share this one function:
    - ``POST /api/notifications/check`` (router.py) — 500'd on every call
      (``UndefinedColumnError``: ``column c.preferred_language does not exist``).
    - ``NotificationScheduler._daily_check`` (scheduler.py, APScheduler cron
      09:00 WITA, started at boot) — the same exception was swallowed by a
      bare ``except Exception`` in ``_daily_check``, so the daily visa/passport
      expiry sweep has silently generated zero alerts since this endpoint was
      introduced (cicatrix-superscar family #2, "Esiste ≠ Armato").

GUILT: the query text no longer references ``client_documents`` anywhere,
and does reference ``documents`` with the ``document_category='immigration'``
filter that makes the visa-expiry join meaningful. It also must not
reference ``c.preferred_language`` or ``c.is_active`` (columns absent from
the live ``clients`` table), and must filter on ``c.status = 'active'``
instead.

INNOCENCE: a client row with no matching immigration document (LEFT JOIN
produces NULLs for ``expiry_date``/``document_type``) does not crash
``get_clients_from_db`` — the missing visa data is just absent on the
resulting ``ClientInfo``. And a plain 'active'-status client still maps
cleanly onto ``ClientInfo`` with the honest default ``preferred_language``.
"""

from __future__ import annotations

import ast
import inspect
import re
from unittest.mock import AsyncMock

import pytest

from backend.app.modules.notifications.router import get_clients_from_db


def _source_without_docstring(func) -> str:
    """``inspect.getsource`` includes the function's own docstring — and this
    function's docstring, by design, MENTIONS the old bad column references
    (``c.preferred_language``) as changelog prose explaining what was fixed.
    A guard that scans raw source text would over-match on that prose and
    "find" the bug in the very comment documenting its absence (cicatrix
    superscar family #3, guard-over-match: match the entity, never the
    text). Strip the docstring statement via AST before scanning so the
    guards below see only the live SQL body."""
    source = inspect.getsource(func)
    tree = ast.parse(source)
    func_node = tree.body[0]
    body = getattr(func_node, "body", [])
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        lines = source.splitlines(keepends=True)
        start, end = body[0].lineno - 1, body[0].end_lineno
        source = "".join(lines[:start] + lines[end:])
    return source

# Whitelist of `clients` columns this query is allowed to reference, derived
# from the live schema (information_schema.columns, ground 2026-08-08).
# `preferred_language` and `is_active` are deliberately ABSENT — they do not
# exist on the live table and must never reappear in this query.
_LIVE_CLIENTS_COLUMNS = {
    "id",
    "uuid",
    "full_name",
    "email",
    "phone",
    "whatsapp",
    "nationality",
    "passport_number",
    "assigned_to",
    "status",
    "tags",
    "metadata",
    "created_at",
    "created_by",
    "updated_at",
    "updated_by",
    "deleted_at",
    "deleted_by",
    "client_type",
    "first_contact_date",
    "last_interaction_date",
    "address",
    "notes",
    "custom_fields",
    "avatar_url",
    "google_drive_folder_id",
    "date_of_birth",
    "passport_expiry",
    "company_name",
    "lead_source",
    "service_interest",
    "gender",
    "birthplace",
    "passport_ocr_data",
    "birthplace_enrichment_date",
    "phone_normalized",
    "tax_id",
    "npwp",
    "nib",
    "current_visa_type",
    "current_visa_sponsor",
    "visa_expiry_date",
    "kitas_expiry_date",
    "geo_point",
    "rdtr_zone_code",
    "geocoded_at",
    "tax_consultant",
    "referrer_url",
    "landing_page",
    "first_touch_at",
    "ai_summary",
    "ai_summary_generated_at",
    "ai_summary_file_hash",
    "ai_summary_schema_version",
    "drive_folder_id",
    "drive_folder_url",
    "strategic_recap",
    "strategic_recap_updated_at",
    "strategic_recap_source",
    "birth_date",
    "kitas_number",
    "lead_metadata",
    "origin",
}


class _PoolCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_a):
        return False


class _Pool:
    """Minimal asyncpg.Pool stand-in — no live DB, no network."""

    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _PoolCtx(self._conn)


def test_query_no_longer_references_client_documents() -> None:
    """GUILT: ``client_documents`` was never provisioned in prod — the
    subquery must not reference it anywhere in the function source."""
    source = inspect.getsource(get_clients_from_db)
    assert "client_documents" not in source, (
        "get_clients_from_db still references the never-provisioned "
        "client_documents table — every call raises asyncpg.UndefinedTableError"
    )
    assert "FROM documents" in source, (
        "get_clients_from_db must join against the live `documents` table "
        "for the visa-expiry subquery"
    )
    assert "document_category = 'immigration'" in source


def test_query_only_references_columns_that_exist_on_live_clients() -> None:
    """GUILT: every `c.<column>` token in the query source must be a column
    that actually exists on the live `clients` table (whitelist derived from
    information_schema.columns, ground 2026-08-08). This is the general form
    of the ``is_active``/``preferred_language`` bug — it fails on ANY future
    reference to a `clients` column that isn't real, not just those two."""
    source = _source_without_docstring(get_clients_from_db)
    referenced = set(re.findall(r"\bc\.([a-z_]+)\b", source))
    unknown = referenced - _LIVE_CLIENTS_COLUMNS
    assert not unknown, (
        f"get_clients_from_db references clients columns that do not exist "
        f"on the live table: {sorted(unknown)} — every such reference raises "
        f"asyncpg.UndefinedColumnError at query time"
    )


def test_query_does_not_reference_removed_columns() -> None:
    """GUILT (explicit): the two columns that caused the 2026-08-08 500 —
    ``c.preferred_language`` (column absent entirely) and ``c.is_active``
    (renamed/replaced by ``status``) — must never reappear in the SQL text,
    and the active-client filter must use the real ``status`` column."""
    source = _source_without_docstring(get_clients_from_db)
    assert "c.preferred_language" not in source, (
        "clients has no preferred_language column — this raises "
        "asyncpg.UndefinedColumnError on every call"
    )
    assert "c.is_active" not in source, (
        "clients has no is_active column — the live column is `status` "
        "(character varying: lead/active/prospect/inactive)"
    )
    assert "c.status = 'active'" in source, (
        "get_clients_from_db must filter on the real `status` column"
    )


@pytest.mark.asyncio
async def test_single_client_query_returns_expected_shape() -> None:
    """GUILT (behavioral): for a single client_id, the query executes against
    `documents` and the row shape maps cleanly onto ClientInfo."""
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [
        {
            "id": 42,
            "email": "client@example.com",
            "full_name": "Test Client",
            "preferred_language": "en",
            "team_leader_email": "ari@balizero.com",
            "date_of_birth": None,
            "passport_expiry": None,
            "passport_number": "X1234567",
            "visa_expiry": None,
            "visa_type": "C1",
        }
    ]

    clients = await get_clients_from_db(_Pool(mock_conn), client_id=42)

    assert len(clients) == 1
    assert clients[0].id == 42
    assert clients[0].visa_type == "C1"

    # The SQL actually sent must target `documents`, not `client_documents`,
    # and filter on the real `status` column, not the nonexistent `is_active`.
    sql_sent = mock_conn.fetch.call_args[0][0]
    assert "client_documents" not in sql_sent
    assert "FROM documents" in sql_sent
    assert "c.is_active" not in sql_sent
    assert "c.status = 'active'" in sql_sent
    mock_conn.fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_all_clients_query_returns_expected_shape() -> None:
    """GUILT (behavioral): the no-client_id (all active clients) branch also
    targets `documents`."""
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = []

    clients = await get_clients_from_db(_Pool(mock_conn), client_id=None)

    assert clients == []
    sql_sent = mock_conn.fetch.call_args[0][0]
    assert "client_documents" not in sql_sent
    assert "FROM documents" in sql_sent
    assert "c.is_active" not in sql_sent
    assert "c.status = 'active'" in sql_sent


@pytest.mark.asyncio
async def test_client_with_no_immigration_documents_does_not_crash() -> None:
    """INNOCENCE: a client with zero matching rows in `documents` (LEFT JOIN
    miss) must not crash — visa_expiry/visa_type simply come back None."""
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [
        {
            "id": 7,
            "email": "no-docs@example.com",
            "full_name": "No Docs Client",
            "preferred_language": "en",
            "team_leader_email": None,
            "date_of_birth": None,
            "passport_expiry": None,
            "passport_number": None,
            "visa_expiry": None,
            "visa_type": None,
        }
    ]

    clients = await get_clients_from_db(_Pool(mock_conn), client_id=7)

    assert len(clients) == 1
    assert clients[0].visa_expiry is None
    assert clients[0].visa_type is None


@pytest.mark.asyncio
async def test_active_status_client_maps_cleanly_with_honest_default_language() -> None:
    """INNOCENCE: an 'active'-status client (the population this query is
    scoped to via `c.status = 'active'`) still maps cleanly onto ClientInfo,
    and the literal `'en' as preferred_language` the query now selects (there
    being no such column to read) round-trips as the model's own documented
    default — no crash, no silent data loss."""
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [
        {
            "id": 99,
            "email": "active-client@example.com",
            "full_name": "Active Client",
            "preferred_language": "en",
            "team_leader_email": "ari@balizero.com",
            "date_of_birth": None,
            "passport_expiry": None,
            "passport_number": "Y7654321",
            "visa_expiry": None,
            "visa_type": None,
        }
    ]

    clients = await get_clients_from_db(_Pool(mock_conn), client_id=None)

    assert len(clients) == 1
    assert clients[0].id == 99
    assert clients[0].preferred_language == "en"


@pytest.mark.asyncio
async def test_active_client_with_null_email_does_not_crash() -> None:
    """GUILT (fix-3 of the notifications lane, third layer of the same
    disease): on the live DB, 369 of 741 active clients have `email IS NULL`
    (measured 2026-08-08, post-#3798+#3822 prove-live). `get_clients_from_db`
    now executes the corrected query cleanly — but `ClientInfo(**client_data)`
    (models.py) declared `email: str` (non-nullable), so pydantic raised
    `ValidationError` on the FIRST active client without an email, taking down
    the whole sweep for the other 372 clients that DO have one behind it in
    the same result set.

    The downstream already tolerates a missing email: `expiry_checker.py`
    never references `.email` at all, and the send path resolves the address
    via `get_client_email_func(alert.client_id)` and explicitly skips sending
    when `if not client_email:` — plus alerts also reach the team leader via
    `assigned_to`. So the correct fix is the model (`email: str | None =
    None`), not an SQL filter that would silently amputate half the active
    book from every notification sweep.

    INNOCENCE (email present) is already covered by
    ``test_active_status_client_maps_cleanly_with_honest_default_language``
    above (asserts a normal active client with a real email maps through
    intact) and by ``test_single_client_query_returns_expected_shape``
    (asserts ``clients[0].id == 42`` off a row with a real email) — not
    duplicated here.
    """
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [
        {
            "id": 123,
            "email": None,
            "full_name": "No Email Client",
            "preferred_language": "en",
            "team_leader_email": "ari@balizero.com",
            "date_of_birth": None,
            "passport_expiry": None,
            "passport_number": None,
            "visa_expiry": None,
            "visa_type": None,
        }
    ]

    clients = await get_clients_from_db(_Pool(mock_conn), client_id=123)

    assert len(clients) == 1
    assert clients[0].id == 123
    assert clients[0].email is None


def test_query_excludes_soft_deleted_clients() -> None:
    """GUILT (fix-4 of the notifications lane, found by the prove-live pass
    after the sweep started running clean post-#3822/#3827): a `status =
    'active'` scan alone returned 1238 rows against 741 actually-active
    (non-deleted) clients, measured live 2026-08-08. The 497-row gap is
    soft-deleted clients whose `status` was never flipped off 'active' —
    `deleted_at IS NOT NULL` for all of them. Sending a birthday/passport/
    visa-expiry alert to an ex-client is noise for the team at best, and an
    unwanted contact with a former client at worst.

    The query text must filter on `c.deleted_at IS NULL` in BOTH branches
    (single-client and all-active-clients), not just one — a partial fix
    would still amputate the wrong half of the book depending on call site.
    """
    source = _source_without_docstring(get_clients_from_db)
    assert source.count("c.deleted_at IS NULL") == 2, (
        "get_clients_from_db must exclude soft-deleted clients "
        "(c.deleted_at IS NULL) in BOTH the single-client and "
        "all-active-clients query branches — found "
        f"{source.count('c.deleted_at IS NULL')} occurrence(s)"
    )


@pytest.mark.asyncio
async def test_single_client_sql_excludes_soft_deleted() -> None:
    """GUILT (behavioral, single-client branch): the actual SQL text sent to
    the connection for a specific client_id must carry the soft-delete
    filter alongside the existing status filter."""
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = []

    await get_clients_from_db(_Pool(mock_conn), client_id=42)

    sql_sent = mock_conn.fetch.call_args[0][0]
    assert "c.deleted_at IS NULL" in sql_sent
    assert "c.status = 'active'" in sql_sent


@pytest.mark.asyncio
async def test_all_clients_sql_excludes_soft_deleted() -> None:
    """GUILT (behavioral, all-active-clients branch): same filter must be
    present in the no-client_id branch's SQL text."""
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = []

    await get_clients_from_db(_Pool(mock_conn), client_id=None)

    sql_sent = mock_conn.fetch.call_args[0][0]
    assert "c.deleted_at IS NULL" in sql_sent
    assert "c.status = 'active'" in sql_sent
