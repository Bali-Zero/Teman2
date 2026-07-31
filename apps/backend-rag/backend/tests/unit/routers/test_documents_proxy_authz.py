"""The Drive proxy must not hand out files it cannot place in a client folder.

THE DEFECT (CodeQL #791/#792, triaged 2026-07-31, confirmed by an independent
cross-family review that OVERTURNED the first analyst's "not exploitable").

`GET /api/documents/proxy/{file_id}` took an arbitrary Drive ID straight off the
URL, interpolated it into `https://www.googleapis.com/drive/v3/files/{file_id}`,
fetched it with the SERVICE ACCOUNT's token, and returned the bytes. The only
guard was `Depends(get_current_user)` — "any authenticated user". `db_pool` was
injected into both handlers and never queried: the module contained no SELECT at
all. The service account carries the full `drive` scope, so any holder of a valid
JWT could read any file it can see — client folders included (KTP, passports,
akta).

WHAT IS PINNED HERE:
  * shape — a file id that can rewrite the API path is refused before any network
    call happens (the SSRF half);
  * provenance — a file that is neither registered in the CRM nor sitting in a
    folder the CRM registered is refused (the IDOR half);
  * innocence — a registered document still passes EVEN WITH NO USABLE PARENT.
    That is not a nicety: client documents live in
    `<client folder>/01_Immigration/…`, so their immediate parent is an
    unregistered subfolder. A parents-only guard would 403 nearly every document
    in the viewer, and a guard that breaks the viewer gets reverted within a day.

DELIBERATELY NOT PINNED — per-user access. Measured 2026-07-31: of 12,037 rows in
`clients`, only 2,061 carry `assigned_to` (17%). Gating on the assignee would
revoke document access for the other 83% and break the CRM for every non-admin.
That gate needs an `assigned_to` backfill first, which is an owner decision about
who holds those clients. A test asserting it today would be asserting a policy
the data cannot support.

ALSO NOT CLOSED, and named in the guard's own docstring: the registry is
self-authorising for a caller who can already write a document row.
"""

from __future__ import annotations

import importlib
from typing import Any

import pytest
from fastapi import HTTPException


@pytest.fixture()
def mod():
    return importlib.import_module("backend.app.routers.documents_proxy")


class _FakeConn:
    """Returns `hit` for the authorisation probe, whatever the SQL."""

    def __init__(self, hit: Any) -> None:
        self._hit = hit
        self.calls: list[tuple] = []

    async def fetchrow(self, sql: str, *args):
        self.calls.append((sql, args))
        return self._hit


class _FakeAcquire:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


class _FakePool:
    def __init__(self, hit):
        self.conn = _FakeConn(hit)

    def acquire(self):
        return _FakeAcquire(self.conn)


# --- shape: the SSRF half ----------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "short",
        "../../../etc/passwd",
        "abcdefghij/permissions",
        "abcdefghij?alt=media",
        "abcdefghij:export",
        "abcdefghij#frag",
        "abc defghij",
        "a" * 300,
    ],
)
def test_a_file_id_that_could_rewrite_the_api_path_is_refused(mod, bad):
    """These do not name a FILE — interpolated into the Drive URL they reach a
    different endpoint entirely. Refused before any token is minted."""
    with pytest.raises(HTTPException) as exc:
        mod._assert_file_id_shape(bad)
    assert exc.value.status_code == 400


@pytest.mark.parametrize(
    "good",
    ["1MUzGL73pcbY", "abcdefghij", "1a2b3c4d5e-_ABC", "A" * 256],
)
def test_a_real_looking_drive_id_passes_the_shape_check(mod, good):
    """Accepting returns None; refusing raises. Asserting the return value is
    what makes "it did not raise" an assertion rather than an absence of one."""
    assert mod._assert_file_id_shape(good) is None


# --- provenance: the IDOR half ----------------------------------------------


@pytest.mark.asyncio
async def test_guilt_a_file_neither_registered_nor_in_a_known_folder_is_refused(mod):
    pool = _FakePool(hit=None)
    with pytest.raises(HTTPException) as exc:
        await mod._assert_file_is_ours("someFileId1", ["folder-we-do-not-know"], pool)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_guilt_an_unknown_file_with_no_parents_is_refused(mod):
    pool = _FakePool(hit=None)
    with pytest.raises(HTTPException) as exc:
        await mod._assert_file_is_ours("someFileId1", [], pool)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_innocence_a_registered_document_passes_even_with_no_usable_parent(mod):
    """THE regression that would break the CRM viewer, pinned.

    Client documents do not sit directly in the client folder — the Drive layout
    is `<client folder>/01_Immigration/Actual Visa/…`, so a document's immediate
    parent is a SUBFOLDER that is registered nowhere. An earlier draft of this
    guard refused on empty/unknown parents *before* consulting the database; that
    would have 403'd nearly every real document. The registry is what answers for
    them, so it must be consulted regardless of what `parents` holds."""
    pool = _FakePool(hit=(1,))
    await mod._assert_file_is_ours("someFileId1", [], pool)
    assert pool.conn.calls, "the registry must be consulted even with no parents"


@pytest.mark.asyncio
async def test_innocence_a_file_under_a_known_client_folder_is_served(mod):
    pool = _FakePool(hit=(1,))
    await mod._assert_file_is_ours("someFileId1", ["known-client-folder"], pool)
    assert pool.conn.calls, "the authorisation query must actually run"
    _sql, args = pool.conn.calls[0]
    assert args[0] == "someFileId1" and args[1] == ["known-client-folder"]


@pytest.mark.asyncio
async def test_the_query_consults_every_registry_that_holds_a_drive_id(mod):
    """Dropping any one of these silently blinds the guard to a whole class of
    legitimate document and 403s it."""
    pool = _FakePool(hit=(1,))
    await mod._assert_file_is_ours("someFileId1", ["f"], pool)
    sql = pool.conn.calls[0][0]
    for table in (
        "documents",
        "company_documents",
        "invoices",
        "lkpm_receipts",
        "clients",
        "companies",
    ):
        assert table in sql, f"{table} missing from the authorisation query"


def test_the_url_fallback_matches_literally_not_with_like_wildcards(mod):
    """A Drive ID legitimately contains `_`, which LIKE reads as a
    single-character wildcard: `LIKE '%' || $1 || '%'` would let a crafted ID
    match a *different* registered one. `strpos` has no wildcards."""
    assert "strpos(" in mod._AUTHORISED_FILE_SQL
    assert "LIKE" not in mod._AUTHORISED_FILE_SQL.upper()


# --- the handlers actually call the guards ----------------------------------


def test_both_handlers_request_parents_from_drive(mod):
    """`parents` is what ties a file to its client. If a future edit trims the
    `fields` list back to mimeType/name, the guard silently starts refusing
    everything (or, worse, someone 'fixes' that by allowing empty parents)."""
    import inspect

    src = inspect.getsource(mod)
    assert "parents" in mod._METADATA_FIELDS
    assert "thumbnailLink,mimeType,parents" in src


def test_both_handlers_are_guarded(mod):
    """A guard defined and not called is the failure mode this whole triage was
    about. Assert both call sites by name."""
    import inspect

    src = inspect.getsource(mod)
    assert src.count("_assert_file_id_shape(file_id)") >= 2
    assert src.count("await _assert_file_is_ours(") >= 2


# --- the twin: same defect, id arriving from a JSON body ---------------------
#
# `crm_enhanced._download_drive_file` interpolates `file_id` into the very same
# Drive URL, and its `file_id` comes from `DocumentCreate.file_id` in a request
# body. It is reached from background tasks and the Drive-poll cron, so it
# signals with RuntimeError rather than HTTPException.


@pytest.mark.asyncio
async def test_twin_guilt_a_path_rewriting_id_never_reaches_the_network(monkeypatch):
    from backend.app.routers import crm_enhanced

    def _explode():  # pragma: no cover - must never run
        raise AssertionError("the Drive service was built for a malformed id")

    monkeypatch.setattr(crm_enhanced, "ServiceAccountDriveService", _explode)
    with pytest.raises(RuntimeError, match="Malformed Drive file id"):
        await crm_enhanced._download_drive_file("../../../etc/passwd")


@pytest.mark.asyncio
async def test_twin_innocence_a_real_looking_id_gets_past_the_shape_check(monkeypatch):
    from backend.app.routers import crm_enhanced

    class _Marker(Exception):
        pass

    def _reached():
        raise _Marker

    monkeypatch.setattr(crm_enhanced, "ServiceAccountDriveService", _reached)
    with pytest.raises(_Marker):
        await crm_enhanced._download_drive_file("1MUzGL73pcbY")
