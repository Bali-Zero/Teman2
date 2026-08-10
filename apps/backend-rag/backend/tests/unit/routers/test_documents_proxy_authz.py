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


# --- the write-side twin: registering a NEW file_id, not reading one --------
#
# THE DEFECT (PENDING-ARMS 2026-08-01, named in `_assert_file_is_ours`'s own
# docstring as the gap it deliberately does not close). `POST
# .../clients/{client_id}/documents` (+ its bulk and company twins) stored the
# caller-supplied Drive `file_id` verbatim, no provenance check at all. The
# read guard above bounds a LOOKUP to "any client/company the CRM already
# holds" — correct there, because the caller already holds a row that put the
# file there. It is the wrong question for a WRITE: a caller with access to
# client A could register a file belonging to client B and then read it back
# through the proxy above, since the registry itself would now vouch for it.
#
# What is pinned here is the one property the read guard's `_FOLDER_REGISTERED_SQL`
# cannot express: SCOPED ownership. A file registered to (or owned by) ANY
# client is not enough — it must resolve to the ONE client/company being
# written to.


class _FakeDriveFileClient:
    """Answers Drive `GET .../files/{id}` from a small id -> parents world,
    for BOTH the top-level metadata fetch and the ancestor-walk's per-folder
    lookups — same shape as `_tree_fetcher` above, but as an httpx.AsyncClient
    substitute since the write guard opens its own client rather than
    accepting one."""

    def __init__(
        self,
        world: dict[str, list[str]],
        statuses: dict[str, int] | None = None,
        transport_errors: set[str] | None = None,
    ):
        self._world = world
        self._statuses = statuses or {}
        self._transport_errors = transport_errors or set()
        self.calls: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, params=None, headers=None, **_kwargs):
        fid = url.rsplit("/", 1)[-1]
        self.calls.append(fid)
        if fid in self._transport_errors:
            import httpx

            raise httpx.ConnectError("simulated transport failure")
        status = self._statuses.get(fid, 200)
        if status != 200:
            return _FakeResponse(status, {})
        return _FakeResponse(200, {"parents": self._world.get(fid, [])})


class _FakeAcquireSelf:
    def __init__(self, target):
        self._target = target

    async def __aenter__(self):
        return self._target

    async def __aexit__(self, *exc):
        return False


class _FakeOwnerPool:
    """Answers the client/company SCOPED-ownership queries — the whole point
    of the write guard is that this predicate takes an owner id, unlike the
    read guard's `_FOLDER_REGISTERED_SQL`.

    Despite the name, this doubles as the ALREADY-OPEN CONNECTION the guard
    now takes directly (2026-08-09, adversarial review finding: a nested
    `db_pool.acquire()` while the caller already holds one from the same
    bounded pool is a real deadlock at pool saturation, not just latency —
    see `_assert_file_descends_from_owner`'s docstring). `acquire_calls`
    proves the guard never re-acquires: every call site now passes its own
    `conn` straight through."""

    def __init__(
        self,
        mod,
        client_folders: dict[int, set[str]] | None = None,
        company_folders: dict[int, set[str]] | None = None,
    ):
        self._mod = mod
        self._client_folders = client_folders or {}
        self._company_folders = company_folders or {}
        self.calls: list[tuple[str, tuple]] = []
        self.acquire_calls = 0

    def acquire(self):  # pragma: no cover - must never be called by the guard
        self.acquire_calls += 1
        return _FakeAcquireSelf(self)

    async def fetchrow(self, sql, *args):
        self.calls.append((sql, args))
        owner_id, folder_ids = args
        if sql is self._mod._CLIENT_OWNS_FOLDER_SQL:
            owned = self._client_folders.get(owner_id, set())
        elif sql is self._mod._COMPANY_OWNS_FOLDER_SQL:
            owned = self._company_folders.get(owner_id, set())
        else:
            raise AssertionError(f"unexpected query: {sql[:60]}")
        return (1,) if owned.intersection(folder_ids) else None


def _patch_drive_client(monkeypatch, mod, fake_client):
    async def _token():
        return "tok"

    monkeypatch.setattr(mod, "_get_drive_access_token", _token)
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda **_k: fake_client)


@pytest.mark.asyncio
async def test_write_guard_innocence_a_file_directly_under_the_owning_client_passes(
    mod, monkeypatch
):
    fake_client = _FakeDriveFileClient({"fileA0001Z": ["client-1-folder"]})
    _patch_drive_client(monkeypatch, mod, fake_client)
    conn = _FakeOwnerPool(mod, client_folders={1: {"client-1-folder"}})
    await mod.assert_drive_file_belongs_to_client("fileA0001Z", 1, conn)
    assert conn.acquire_calls == 0


@pytest.mark.asyncio
async def test_write_guard_innocence_a_file_nested_under_the_owning_client_passes(
    mod, monkeypatch
):
    """Mirrors the read guard's own two-level test: a fresh upload/browser file
    sitting in `<client>/01_Immigration/Actual Visa/…` must still be provable —
    the write guard cannot be stricter than the thing it authorises for."""
    fake_client = _FakeDriveFileClient(
        {"fileA0001Z": ["actual-visa"], "actual-visa": ["immigration"], "immigration": ["client-1-folder"]}
    )
    _patch_drive_client(monkeypatch, mod, fake_client)
    pool = _FakeOwnerPool(mod, client_folders={1: {"client-1-folder"}})
    await mod.assert_drive_file_belongs_to_client("fileA0001Z", 1, pool)
    assert fake_client.calls == ["fileA0001Z", "actual-visa", "immigration"]


@pytest.mark.asyncio
async def test_write_guard_guilt_a_file_under_a_different_clients_folder_is_refused(
    mod, monkeypatch
):
    """THE case the read guard's own registry check cannot express: this file
    IS a legitimately client-owned Drive file — just not THIS client's."""
    fake_client = _FakeDriveFileClient({"fileA0001Z": ["client-2-folder"]})
    _patch_drive_client(monkeypatch, mod, fake_client)
    pool = _FakeOwnerPool(
        mod, client_folders={1: {"client-1-folder"}, 2: {"client-2-folder"}}
    )
    with pytest.raises(HTTPException) as exc:
        await mod.assert_drive_file_belongs_to_client("fileA0001Z", 1, pool)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_write_guard_guilt_a_registry_hit_for_another_client_still_refuses(
    mod, monkeypatch
):
    """The strongest version of the case above: prove the write guard does NOT
    fall back to "is this file registered ANYWHERE" the way the read guard's
    `_file_is_registered` half does. A file with no discoverable parents at all
    (the exact shape that legitimately passes the READ guard once it is
    registered) must still be refused here — nothing registers it for THIS
    client, and the write guard never consults `_REGISTERED_FILE_SQL`."""
    fake_client = _FakeDriveFileClient({"fileA0001Z": []})
    _patch_drive_client(monkeypatch, mod, fake_client)
    pool = _FakeOwnerPool(mod, client_folders={1: {"client-1-folder"}})
    with pytest.raises(HTTPException) as exc:
        await mod.assert_drive_file_belongs_to_client("fileA0001Z", 1, pool)
    assert exc.value.status_code == 403
    assert not any(sql is mod._REGISTERED_FILE_SQL for sql, _ in getattr(pool, "calls", []))


@pytest.mark.asyncio
async def test_write_guard_guilt_a_failed_metadata_fetch_denies_rather_than_permits(
    mod, monkeypatch
):
    fake_client = _FakeDriveFileClient({}, statuses={"fileA0001Z": 404})
    _patch_drive_client(monkeypatch, mod, fake_client)
    pool = _FakeOwnerPool(mod, client_folders={1: {"client-1-folder"}})
    with pytest.raises(HTTPException) as exc:
        await mod.assert_drive_file_belongs_to_client("fileA0001Z", 1, pool)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_write_guard_guilt_a_transport_error_denies_rather_than_500s(mod, monkeypatch):
    """The top-level metadata fetch previously had no `try/except` around it
    (unlike `_drive_parent_fetcher._fetch`, which already caught
    `httpx.HTTPError`) — a timeout/connect-error there propagated uncaught
    past the guard's intended fail-closed 403, surfacing as a raw 500 in
    `create_document` (no local try/except) instead of a clean refusal."""
    fake_client = _FakeDriveFileClient({}, transport_errors={"fileA0001Z"})
    _patch_drive_client(monkeypatch, mod, fake_client)
    pool = _FakeOwnerPool(mod, client_folders={1: {"client-1-folder"}})
    with pytest.raises(HTTPException) as exc:
        await mod.assert_drive_file_belongs_to_client("fileA0001Z", 1, pool)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_write_guard_guilt_a_malformed_id_never_reaches_the_network(mod, monkeypatch):
    async def _explode():  # pragma: no cover - must never run
        raise AssertionError("a token was minted for a malformed id")

    monkeypatch.setattr(mod, "_get_drive_access_token", _explode)
    pool = _FakeOwnerPool(mod, client_folders={1: {"client-1-folder"}})
    with pytest.raises(HTTPException) as exc:
        await mod.assert_drive_file_belongs_to_client("../../../etc/passwd", 1, pool)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_write_guard_company_variant_scopes_to_the_specific_company(mod, monkeypatch):
    fake_client = _FakeDriveFileClient({"fileA0001Z": ["company-2-folder"]})
    _patch_drive_client(monkeypatch, mod, fake_client)
    pool = _FakeOwnerPool(
        mod, company_folders={1: {"company-1-folder"}, 2: {"company-2-folder"}}
    )
    with pytest.raises(HTTPException) as exc:
        await mod.assert_drive_file_belongs_to_company("fileA0001Z", 1, pool)
    assert exc.value.status_code == 403

    # And the matching company IS authorised.
    await mod.assert_drive_file_belongs_to_company("fileA0001Z", 2, pool)


class _BareConn:
    """A connection with `fetchrow` and deliberately NO `acquire` at all — the
    strongest proof the guard treats its third argument as an already-open
    connection, not a pool: a real `asyncpg.Connection` has no `.acquire()`
    either, so if the guard ever called it, this fake would raise
    `AttributeError` instead of silently degrading."""

    def __init__(self, mod, client_folders: dict[int, set[str]]):
        self._mod = mod
        self._client_folders = client_folders

    async def fetchrow(self, sql, *args):
        owner_id, folder_ids = args
        assert sql is self._mod._CLIENT_OWNS_FOLDER_SQL
        owned = self._client_folders.get(owner_id, set())
        return (1,) if owned.intersection(folder_ids) else None


@pytest.mark.asyncio
async def test_write_guard_never_acquires_a_second_connection_from_the_pool(
    mod, monkeypatch
):
    """Guilt-shaped regression for the adversarial-review finding: a guard
    that still called `db_pool.acquire()` while the caller already holds a
    connection from the same bounded pool would deadlock at pool saturation
    (every in-flight request holding its outer connection idle across the
    Drive round-trip, with no free slot left for the guard's own acquire).
    A bare connection object with no `acquire` proves the call never
    happens — an `AttributeError` here means the regression came back."""
    fake_client = _FakeDriveFileClient({"fileA0001Z": ["client-1-folder"]})
    _patch_drive_client(monkeypatch, mod, fake_client)
    conn = _BareConn(mod, client_folders={1: {"client-1-folder"}})
    await mod.assert_drive_file_belongs_to_client("fileA0001Z", 1, conn)


def test_write_guard_queries_scope_by_owner_id_unlike_the_read_guards_registry(mod):
    """The one structural property that makes this a different guard, not a
    copy: both new queries filter on the owner's own primary key."""
    assert "id = $1" in mod._CLIENT_OWNS_FOLDER_SQL
    assert "google_drive_folder_id" in mod._CLIENT_OWNS_FOLDER_SQL
    assert "drive_folder_id" in mod._CLIENT_OWNS_FOLDER_SQL
    assert "id = $1" in mod._COMPANY_OWNS_FOLDER_SQL
    assert "tax_dept_folder_id" in mod._COMPANY_OWNS_FOLDER_SQL


def test_write_guard_is_actually_wired_into_all_four_call_sites():
    """A guard defined and not called is the failure mode this whole triage was
    about (see `test_both_handlers_are_guarded` above) — same check for the
    write side's four sites: client create, client bulk create, client PATCH
    (added 2026-08-09 — the adversarial review found this one unguarded:
    `PATCH .../documents/{doc_id}` writes `documents.file_id` through the same
    column the original three sites protect), company create."""
    import inspect

    from backend.app.modules.crm import company_router
    from backend.app.routers import crm_enhanced_documents

    client_src = inspect.getsource(crm_enhanced_documents)
    assert client_src.count("await assert_drive_file_belongs_to_client(") >= 3

    company_src = inspect.getsource(company_router)
    assert "await assert_drive_file_belongs_to_company(" in company_src
