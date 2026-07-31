"""The Drive proxy must not hand out files it cannot place in a client folder.

THE DEFECT (CodeQL #791/#792, triaged 2026-07-31, confirmed by an independent
cross-family review that OVERTURNED the first analyst's "not exploitable").

`GET /api/documents/proxy/{file_id}` took an arbitrary Drive ID straight off the
URL, interpolated it into `https://www.googleapis.com/drive/v3/files/{file_id}`,
fetched it with the SERVICE ACCOUNT's token, and returned the bytes. The only
guard was `Depends(get_current_user)` — "any authenticated user". `db_pool` was
injected into both handlers and never queried: the module contained no SELECT at
all. The service account carries the full `drive` scope, so any holder of a valid
JWT could read any file it can see — client folders included.

WHAT IS PINNED HERE:
  * shape — a file id that can rewrite the API path is refused before any network
    call happens, proven at the HANDLER, not just on the helper;
  * provenance — a file that is neither registered in the CRM nor descended from
    a folder the CRM registered is refused;
  * innocence — a registered document passes with NO usable parent, and an
    unregistered file passes when an ANCESTOR folder is registered. Neither is a
    nicety: client documents live in `<client folder>/01_Immigration/…`, and the
    Drive browser and fresh uploads have no registry row at all. A guard that
    breaks those gets reverted within a day, and then the hole is back;
  * no existence oracle — for an unregistered id, "absent from Drive" and "not
    yours" must be the same answer.

The fake connection below ANSWERS FROM A FAKE WORLD rather than returning a
canned hit: an earlier version returned the same row whatever the SQL and
whatever the arguments, so the folder branch could have been semantically broken
and every test would still have passed. A test double that cannot say no cannot
witness anything.

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
    """Answers the two authorisation queries from a small fake world."""

    def __init__(self, module, registered_ids: set[str], registered_folders: set[str]) -> None:
        self._mod = module
        self._ids = registered_ids
        self._folders = registered_folders
        self.calls: list[tuple[str, tuple]] = []

    async def fetchrow(self, sql: str, *args):
        self.calls.append((sql, args))
        if sql is self._mod._REGISTERED_FILE_SQL:
            return (1,) if args[0] in self._ids else None
        if sql is self._mod._FOLDER_REGISTERED_SQL:
            return (1,) if self._folders.intersection(args[0]) else None
        raise AssertionError(f"unexpected query: {sql[:60]}")


class _FakeAcquire:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


class _FakePool:
    def __init__(self, module, registered_ids=(), registered_folders=()):
        self.conn = _FakeConn(module, set(registered_ids), set(registered_folders))

    def acquire(self):
        return _FakeAcquire(self.conn)


def _tree_fetcher(tree: dict[str, list[str]], log: list[str]):
    """`async (folder_id) -> parents` over a fake folder tree."""

    async def _fetch(folder_id: str) -> list[str]:
        log.append(folder_id)
        return tree.get(folder_id, [])

    return _fetch


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
    different endpoint entirely."""
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


@pytest.mark.asyncio
async def test_the_handler_refuses_a_malformed_id_before_minting_a_token(mod, monkeypatch):
    """The helper being correct is not the claim; the ORDER inside the handler
    is. Nothing may touch Google before the shape is anchored."""

    async def _explode():  # pragma: no cover - must never run
        raise AssertionError("a token was minted for a malformed id")

    monkeypatch.setattr(mod, "_get_drive_access_token", _explode)
    for handler in (mod.proxy_drive_file, mod.get_drive_thumbnail):
        with pytest.raises(HTTPException) as exc:
            await handler("../../../etc/passwd", db_pool=_FakePool(mod))
        assert exc.value.status_code == 400


# --- provenance: the IDOR half ----------------------------------------------


@pytest.mark.asyncio
async def test_guilt_a_file_neither_registered_nor_under_a_known_folder_is_refused(mod):
    pool = _FakePool(mod, registered_ids={"otherFileId"}, registered_folders={"known-folder"})
    with pytest.raises(HTTPException) as exc:
        await mod._assert_file_is_ours("someFileId1", ["folder-we-do-not-know"], pool)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_guilt_an_unknown_file_with_no_parents_is_refused(mod):
    pool = _FakePool(mod, registered_ids={"otherFileId"})
    with pytest.raises(HTTPException) as exc:
        await mod._assert_file_is_ours("someFileId1", [], pool)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_innocence_a_registered_document_passes_with_no_usable_parent(mod):
    """THE regression that would break the CRM viewer, pinned.

    Client documents do not sit directly in the client folder — the layout is
    `<client folder>/01_Immigration/Actual Visa/…`, so a document's immediate
    parent is a SUBFOLDER registered nowhere. The registry is what answers for
    them, and it must answer without needing `parents` at all."""
    pool = _FakePool(mod, registered_ids={"someFileId1"})
    log: list[str] = []
    await mod._assert_file_is_ours("someFileId1", [], pool, _tree_fetcher({}, log))
    assert not log, "a registered document must cost zero extra Drive calls"


@pytest.mark.asyncio
async def test_innocence_a_file_directly_under_a_known_client_folder_is_served(mod):
    pool = _FakePool(mod, registered_folders={"client-folder"})
    await mod._assert_file_is_ours("someFileId1", ["client-folder"], pool)
    assert any(sql is mod._FOLDER_REGISTERED_SQL for sql, _ in pool.conn.calls)


@pytest.mark.asyncio
async def test_innocence_an_unregistered_file_two_levels_deep_is_served(mod):
    """The Drive BROWSER and a fresh UPLOAD both hand out a proxy URL for a file
    that no registry knows, sitting in `01_Immigration/Actual Visa`. Without the
    ancestor walk both features return 403."""
    pool = _FakePool(mod, registered_folders={"client-folder"})
    tree = {"actual-visa": ["immigration"], "immigration": ["client-folder"]}
    log: list[str] = []
    await mod._assert_file_is_ours("someFileId1", ["actual-visa"], pool, _tree_fetcher(tree, log))
    assert log == ["actual-visa", "immigration"], "the walk must stop as soon as it lands"


@pytest.mark.asyncio
async def test_guilt_the_walk_is_bounded_and_a_cycle_cannot_hang_it(mod):
    pool = _FakePool(mod, registered_folders={"never-reached"})
    tree = {"a": ["b"], "b": ["a"]}
    log: list[str] = []
    with pytest.raises(HTTPException) as exc:
        await mod._assert_file_is_ours("someFileId1", ["a"], pool, _tree_fetcher(tree, log))
    assert exc.value.status_code == 403
    assert len(log) <= mod._MAX_ANCESTOR_LOOKUPS


@pytest.mark.asyncio
async def test_guilt_a_drive_lookup_that_fails_denies_rather_than_permits(mod):
    """`_drive_parent_fetcher` answers "no parents" on any error. That must read
    as "cannot place it" — an API blip is not permission."""
    pool = _FakePool(mod, registered_folders={"client-folder"})
    log: list[str] = []
    with pytest.raises(HTTPException) as exc:
        await mod._assert_file_is_ours("someFileId1", ["orphan"], pool, _tree_fetcher({}, log))
    assert exc.value.status_code == 403


# --- the queries themselves --------------------------------------------------


def test_the_registry_query_consults_every_table_that_holds_a_drive_id(mod):
    for table in (
        "documents",
        "company_documents",
        "invoices",
        "lkpm_receipts",
        "weekly_cashout",
    ):
        assert table in mod._REGISTERED_FILE_SQL, f"{table} missing from the registry query"


def test_the_folder_query_includes_the_tax_department_folder(mod):
    """`companies.tax_dept_folder_id` was missed by the first version because the
    column enumeration filtered names on `drive`/`file_id`/`file_url` and that one
    matches none of the three. SPT/PPN/LKPM files hang off it."""
    assert "tax_dept_folder_id" in mod._FOLDER_REGISTERED_SQL
    assert "drive_folder_id" in mod._FOLDER_REGISTERED_SQL


def test_the_url_fallback_is_anchored_to_a_drive_url_boundary(mod):
    """A bare `strpos(url, $1)` authorises any id that merely OCCURS inside a
    stored URL — a shorter id riding on a longer one. Anchoring to the two forms
    the frontend itself parses removes that. And never LIKE: a Drive id contains
    `_`, which LIKE reads as a single-character wildcard."""
    sql = mod._REGISTERED_FILE_SQL
    assert "'/d/' || $1" in sql and "'id=' || $1" in sql
    assert "), $1)" not in sql, "an unanchored substring branch is still present"
    assert "LIKE" not in sql.upper()


# --- no existence oracle -----------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code: int, payload: Any = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class _FakeHttpClient:
    def __init__(self, response: _FakeResponse):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, *_a, **_k):
        return self._response


@pytest.mark.parametrize(
    ("registered", "expected"),
    [(True, 404), (False, 403)],
)
@pytest.mark.asyncio
async def test_drive_404_is_only_disclosed_for_an_id_the_crm_already_knows(
    mod, monkeypatch, registered, expected
):
    """Otherwise the endpoint answers "does this file exist?" for every id in the
    Workspace, to anyone holding a JWT."""

    async def _token():
        return "tok"

    monkeypatch.setattr(mod, "_get_drive_access_token", _token)
    monkeypatch.setattr(
        mod.httpx, "AsyncClient", lambda **_k: _FakeHttpClient(_FakeResponse(404))
    )
    pool = _FakePool(mod, registered_ids={"knownFileId1"} if registered else set())
    with pytest.raises(HTTPException) as exc:
        await mod.proxy_drive_file("knownFileId1", db_pool=pool)
    assert exc.value.status_code == expected


# --- the handlers actually call the guards ----------------------------------


def test_both_handlers_request_parents_from_drive(mod):
    """`parents` is what ties a file to its client. If a future edit trims the
    `fields` list back to mimeType/name, the ancestor walk silently starts
    refusing everything the registry does not already know."""
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
    assert src.count("await _file_is_registered(file_id, db_pool)") >= 2
    assert src.count("await _assert_folder_ancestry_is_ours(") >= 2


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


def test_twin_does_not_block_the_event_loop_on_a_cold_token(monkeypatch):
    """google-auth's `refresh()` is synchronous; called bare inside an async
    function it stalls the loop for a whole TLS handshake. The proxy already
    offloaded it, this twin did not."""
    import inspect

    from backend.app.routers import crm_enhanced

    src = inspect.getsource(crm_enhanced._download_drive_file)
    assert "asyncio.to_thread" in src
    assert "drive_service.credentials.refresh(" not in src
