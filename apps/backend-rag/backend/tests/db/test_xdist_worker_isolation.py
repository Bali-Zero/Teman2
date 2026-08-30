"""Guilt + innocence for conftest.py's per-xdist-worker Postgres isolation
(`pytest_configure`, added 2026-08-21 — see that function's docstring for
the full design rationale: world-practice import map §1.3,
research/operations/2026-08-21-world-patterns-import-map.md).

GUILT (`test_two_xdist_workers_do_not_share_a_database`): spawns a NESTED
`pytest -n 2 --dist loadfile` run against the two sibling files in
`xdist_isolation_probe/` and proves, from the OUTSIDE, that the two workers
never touched the same Postgres database — each only ever saw the row it
itself inserted, even though both processes overlap in wall-clock time
(each probe sleeps mid-transaction specifically to force that overlap; see
that file's docstring for why this makes the check deterministic, not a
timing-dependent maybe).

INNOCENCE (`test_serial_run_still_sees_its_own_rows`): runs directly, no
subprocess, no `-n` — proves a plain single-worker run is completely
unaffected: `pytest_configure` returns immediately when `PYTEST_XDIST_WORKER`
is unset (see that function), so ordinary CRUD against `TEST_DATABASE_URL`
must behave exactly as it always has.

Both skip gracefully (never ERROR) when no local Postgres is reachable —
same convention `.husky/pre-push` and this directory's other DB-integration
tests already use.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio

_BACKEND_RAG_DIR = Path(__file__).resolve().parents[3]
_PROBE_DIR = Path(__file__).resolve().parent / "xdist_isolation_probe"

_TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_test",
)


def _base_db_name(dsn: str) -> str:
    return dsn.rsplit("/", 1)[-1].split("?", 1)[0]


def _xdist_swap_db_name(dsn: str, new_db: str) -> str:
    """Same shape as conftest's `_xdist_swap_db`, kept local on purpose.

    Importing it would drag in conftest's module-level xdist block, which is
    exactly what `_load_conftest_module` below goes to lengths to neutralize.
    """
    base_part, sep, db_and_query = dsn.rpartition("/")
    if not sep:
        raise RuntimeError(f"cannot parse a database name out of DSN {dsn!r}")
    _, _, query = db_and_query.partition("?")
    return f"{base_part}/{new_db}" + (f"?{query}" if query else "")


@pytest_asyncio.fixture
async def _require_local_postgres() -> None:
    try:
        conn = await asyncpg.connect(_TEST_DATABASE_URL, timeout=3)
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"no reachable local Postgres at TEST_DATABASE_URL ({exc})")
    else:
        await conn.close()


async def test_serial_run_still_sees_its_own_rows(_require_local_postgres) -> None:
    """Innocence: a single-worker (non-xdist) run behaves exactly as before.

    Not gated on PYTEST_XDIST_WORKER being unset — if this file happens to
    run INSIDE an xdist worker (e.g. this whole suite run under `-n auto`),
    `pytest_configure` will already have repointed TEST_DATABASE_URL at that
    worker's own clone, and this is then a same-shape self-consistency
    check on that clone. Either way the assertion is identical: a plain
    insert-then-count sees exactly what it wrote, nothing phantom.
    """
    conn = await asyncpg.connect(os.environ["TEST_DATABASE_URL"])
    try:
        await conn.execute("CREATE TABLE IF NOT EXISTS _xdist_serial_probe (marker text NOT NULL)")
        await conn.execute("DELETE FROM _xdist_serial_probe")
        await conn.execute(
            "INSERT INTO _xdist_serial_probe (marker) VALUES ($1)", "serial-innocence"
        )
        count = await conn.fetchval("SELECT count(*) FROM _xdist_serial_probe")
        await conn.execute("DROP TABLE _xdist_serial_probe")
    finally:
        await conn.close()
    assert count == 1


_PROBE_BASE_DB_RE = re.compile(r"^[A-Za-z0-9_]+_nestedprobe[0-9]+$")


def _pristine_dsn() -> str:
    """The DSN as it was BEFORE conftest repointed it at a worker clone.

    `pytest_configure` stashes it as `"{pid}:{dsn}"` and only trusts the
    marker when the pid matches, deliberately, so it does not leak into a
    child process. Inside the worker process itself the pid DOES match, which
    is exactly the case this helper needs: it wants the base name the whole
    run started from, not this worker's private clone.
    """
    marker = os.environ.get("_XDIST_PRISTINE_TEST_DATABASE_URL", "")
    pid, _, dsn = marker.partition(":")
    if pid == str(os.getpid()) and dsn:
        return dsn
    return os.environ["TEST_DATABASE_URL"]


async def _create_nested_probe_database(admin_dsn: str, probe_db: str) -> None:
    if not _PROBE_BASE_DB_RE.fullmatch(probe_db):
        raise RuntimeError(f"refusing to operate on unsafe database name {probe_db!r}")
    conn = await asyncpg.connect(admin_dsn)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{probe_db}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{probe_db}"')
    finally:
        await conn.close()


async def _drop_nested_probe_databases(admin_dsn: str, probe_db: str) -> None:
    """Drop the probe base and everything the nested run derived from it.

    Each name is re-checked against a regex before the FORCE drop rather than
    trusted because it came back from a LIKE (cicatrix-superscar #3: a guard
    that decides on a prefix is not a guard that decides on a name).
    """
    conn = await asyncpg.connect(admin_dsn)
    try:
        rows = await conn.fetch(
            r"SELECT datname FROM pg_database WHERE datname = $1 OR datname LIKE $1 || '\_%'",
            probe_db,
        )
        for row in rows:
            name = row["datname"]
            if not re.fullmatch(rf"{re.escape(probe_db)}(_gw\d+|_xdist_template)?", name):
                continue
            await conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    finally:
        await conn.close()


async def test_two_xdist_workers_do_not_share_a_database(_require_local_postgres, tmp_path) -> None:
    """Guilt: under `-n 2 --dist loadfile`, two workers' writes to a
    same-named table never collide — because they are two different
    Postgres databases, not one shared one (the #4477/c92ed801 bug this
    fixture exists to close).
    """
    out_dir = tmp_path / "xdist-probe-out"
    out_dir.mkdir()

    # CORRECTED 2026-08-27: this used to hand the child the DSN this test
    # itself is using, with the comment "pass the same base URL". Under CI's
    # `-n auto` that URL is NOT a base URL — conftest's `pytest_configure`
    # already repointed it at THIS worker's private clone
    # (`nuzantara_test_gw0`), and this process holds live sessions on it. The
    # child then re-derived its own isolation from that name and ran
    # `CREATE DATABASE ..._xdist_template TEMPLATE "nuzantara_test_gw0"`
    # against the database its own parent was using: `ObjectInUseError:
    # source database is being accessed by other users`, gw node down, zero
    # tests collected, rc=5, and this test reporting "nested xdist probe run
    # failed". Measured on run 33045801564 (2026-08-27), where it reddened a
    # docs-only PR while main was green — whether the parent happens to hold
    # a session at that instant is a race, which is what made it look flaky
    # rather than broken.
    #
    # Handing down the PRISTINE base URL instead does not fix it: the child's
    # worker clones would then be named `<base>_gw0`/`_gw1`, which ARE the
    # outer run's own live worker databases. Both failures are the same
    # mistake — deriving the child's namespace from a name the parent owns.
    #
    # So the child gets a base database of its own, named per-pid, created
    # here and dropped after. Nothing the outer run owns is ever a template,
    # a drop target, or a collision.
    admin_dsn = _admin_dsn(_pristine_dsn())
    probe_db = f"{_base_db_name(_pristine_dsn())}_nestedprobe{os.getpid()}"
    await _create_nested_probe_database(admin_dsn, probe_db)
    base_db = probe_db

    env = dict(os.environ)
    env["XDIST_PROBE_OUT"] = str(out_dir)
    # The probe files resolve their own DSN from TEST_DATABASE_URL; the
    # nested `pytest_configure` will clone per-worker off THIS name.
    env["TEST_DATABASE_URL"] = _xdist_swap_db_name(_pristine_dsn(), probe_db)
    env.pop("PYTEST_XDIST_WORKER", None)  # this is the OUTER (possibly already-a-worker) run
    # Do not let the parent's pristine marker reach the child: it is
    # pid-guarded, so the child would ignore it anyway, but leaving a stale
    # `pid:dsn` naming the OUTER base database in the child's environment is
    # exactly the kind of thing a future reader would trust.
    env.pop("_XDIST_PRISTINE_TEST_DATABASE_URL", None)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(_PROBE_DIR),
            "-n",
            "2",
            "--dist",
            "loadfile",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        cwd=_BACKEND_RAG_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    try:
        assert result.returncode == 0, (
            f"nested xdist probe run failed (rc={result.returncode}):\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
        )

        a = json.loads((out_dir / "a.json").read_text())
        b = json.loads((out_dir / "b.json").read_text())

        worker_db_re = re.compile(rf"^{re.escape(base_db)}_gw\d+$")
        assert worker_db_re.match(a["db"]), a
        assert worker_db_re.match(b["db"]), b
        assert a["db"] != b["db"], (
            f"both xdist workers used the SAME database ({a['db']!r}) — "
            "per-worker isolation is broken"
        )
        assert a["sources_seen"] == ["A"], (
            f"worker A saw rows from the other worker: {a['sources_seen']!r} — "
            "shared-Postgres pollution (the #4477 bug)"
        )
        assert b["sources_seen"] == ["B"], (
            f"worker B saw rows from the other worker: {b['sources_seen']!r} — "
            "shared-Postgres pollution (the #4477 bug)"
        )
    finally:
        # Always, including on the assertion failures above: a leaked probe
        # database would make the NEXT run's `DROP ... WITH (FORCE)` the only
        # thing standing between it and a name collision.
        await _drop_nested_probe_databases(admin_dsn, probe_db)


def _load_conftest_module():
    """Import backend/tests/conftest.py's helpers as a plain module.

    A fresh `importlib` load (not pytest's own conftest machinery) keeps
    this test independent of whatever name pytest's own plugin manager
    registered the real conftest module under. This whole test suite may
    itself be running INSIDE a real xdist worker (e.g. under `-n auto` in
    CI, or this file's own directory run under `-n 10` locally) — a plain
    re-exec of the file would then re-trigger its module-level xdist block
    using `PYTEST_XDIST_WORKER`/`TEST_DATABASE_URL` from THIS environment,
    silently repointing `TEST_DATABASE_URL`/`INTAKE_TEST_DSN`/`DATABASE_URL`
    to yet another nested clone and polluting every OTHER test that runs in
    this same worker afterward. Hide `PYTEST_XDIST_WORKER` for the duration
    of the exec so that block's own `if _xdist_worker_id:` guard is False
    here, exactly like a genuine serial run — this loader only wants the
    plain function objects, never that side effect.
    """
    import importlib.util

    conftest_path = Path(__file__).resolve().parents[1] / "conftest.py"
    spec = importlib.util.spec_from_file_location("_xdist_race_conftest_probe", conftest_path)
    module = importlib.util.module_from_spec(spec)
    saved_worker_id = os.environ.pop("PYTEST_XDIST_WORKER", None)
    try:
        spec.loader.exec_module(module)
    finally:
        if saved_worker_id is not None:
            os.environ["PYTEST_XDIST_WORKER"] = saved_worker_id
    return module


def _admin_dsn(dsn: str) -> str:
    return dsn.rsplit("/", 1)[0] + "/postgres"


def _scratch_source_db() -> str:
    """The database these probes may safely name as a CREATE DATABASE TEMPLATE.

    SCAR (2026-08-28, job 98762263195): every probe below derived ONE name
    from `TEST_DATABASE_URL` and then used it for two incompatible jobs --
    the NAMESPACE its scratch databases are named in, and the SOURCE they are
    cloned from. Under xdist `pytest_configure` has already repointed that
    variable at the worker's OWN clone, so the source became
    `nuzantara_test_gw1`: the database the worker is running its tests in.
    Postgres refuses `CREATE DATABASE ... TEMPLATE` off a database holding
    live sessions, so the probe died in its own SETUP with the very
    `ObjectInUseError` it exists to demonstrate -- outside any
    `pytest.raises`, so as a failure and not as the assertion.

    It stayed green whenever the worker happened to hold no open session at
    that instant, which is why this reads as a flake and is not one. The
    35s runtime of the old shape was `_xdist_clone_worker_database`'s bounded
    retry loop already losing the same fight.

    The namespace must STAY worker-derived: that is what keeps a probe's
    scratch names from colliding with a live sibling worker's database, whose
    `finally` would then DROP it out from under a running sibling. Only the
    SOURCE moves, to the pristine base the whole run started from -- the one
    database no worker ever connects to.
    """
    return _base_db_name(_pristine_dsn())


async def test_old_shape_templating_off_a_live_worker_database_fails(
    _require_local_postgres,
) -> None:
    """GUILT (2026-08-25, job 97847958574): reproduces the CI failure's
    MECHANISM, not just its symptom.

    Before the fix, `_xdist_clone_worker_database` templated every worker's
    clone directly off `base_db` — and `base_db` was derived from
    `TEST_DATABASE_URL`, the exact variable this file overwrites with a
    worker-specific DSN a few lines later. Any re-derivation of `base_db`
    AFTER that overwrite (the SCAR comment in conftest.py names the
    concrete triggers) picks up a WORKER'S OWN LIVE DATABASE as the
    template name. This reproduces exactly that shape directly against
    the (still-present, now demoted to an internal helper) old call
    contract: open a live connection to a worker's own database — mirroring
    "gw0 must connect to it, to run its own tests" — then try to clone off
    THAT database as if it were the base. Postgres must refuse with the
    same `ObjectInUseError` CI hit.
    """
    conftest = _load_conftest_module()
    namespace = _base_db_name(os.environ["TEST_DATABASE_URL"])
    admin_dsn = _admin_dsn(os.environ["TEST_DATABASE_URL"])

    # The database this probe is about to make busy is itself cloned through a
    # private connectionless template -- named inside THIS worker's namespace
    # so it can never be a sibling's, sourced from the pristine base so the
    # setup cannot die of the very error the assertion below is for.
    scratch_template = conftest._xdist_template_db_name(namespace)
    busy_worker_db = f"{namespace}_gw0"
    busy_conn = None
    try:
        await conftest._xdist_ensure_template_database(
            admin_dsn, _scratch_source_db(), scratch_template
        )
        await conftest._xdist_clone_worker_database(admin_dsn, scratch_template, busy_worker_db)

        busy_dsn = conftest._xdist_swap_db(os.environ["TEST_DATABASE_URL"], busy_worker_db)
        busy_conn = await asyncpg.connect(busy_dsn)

        # This is the OLD call shape: templating off a worker's own live
        # database (`busy_worker_db`), exactly what a wrong `base_db`
        # re-derivation would have handed to `_xdist_clone_worker_database`.
        with pytest.raises(RuntimeError, match="could not CREATE DATABASE"):
            await conftest._xdist_clone_worker_database(
                admin_dsn, busy_worker_db, f"{busy_worker_db}_gw1"
            )
    finally:
        if busy_conn is not None:
            await busy_conn.close()
        await conftest._xdist_drop_worker_database(admin_dsn, busy_worker_db)
        await conftest._xdist_drop_worker_database(admin_dsn, f"{busy_worker_db}_gw1")
        await conftest._xdist_drop_template_database(admin_dsn, scratch_template)


async def test_new_shape_clones_succeed_while_a_sibling_worker_is_busy(
    _require_local_postgres,
) -> None:
    """INNOCENCE for the fix: `_xdist_ensure_template_database` builds a
    connectionless template, and cloning a NEW worker database from it
    succeeds even while a SIBLING worker database (built from the same
    template, holding a live connection exactly like gw0 mid-test) is busy
    — because the clone never touches the sibling's database, only the
    dedicated template.
    """
    conftest = _load_conftest_module()
    namespace = _base_db_name(os.environ["TEST_DATABASE_URL"])
    admin_dsn = _admin_dsn(os.environ["TEST_DATABASE_URL"])
    template_db = conftest._xdist_template_db_name(namespace)

    await conftest._xdist_ensure_template_database(admin_dsn, _scratch_source_db(), template_db)

    worker0_db = f"{namespace}_gw0"
    worker1_db = f"{namespace}_gw1"
    await conftest._xdist_clone_worker_database(admin_dsn, template_db, worker0_db)

    worker0_dsn = conftest._xdist_swap_db(os.environ["TEST_DATABASE_URL"], worker0_db)
    busy_conn = await asyncpg.connect(worker0_dsn)
    try:
        # Must succeed: templates off `template_db`, never off worker0_db.
        await conftest._xdist_clone_worker_database(admin_dsn, template_db, worker1_db)
    finally:
        await busy_conn.close()
        await conftest._xdist_drop_worker_database(admin_dsn, worker0_db)
        await conftest._xdist_drop_worker_database(admin_dsn, worker1_db)

    # The template itself must refuse ordinary connections — the guarantee
    # that makes it immune to ever being "busy".
    with pytest.raises(asyncpg.PostgresError):
        await asyncpg.connect(conftest._xdist_swap_db(os.environ["TEST_DATABASE_URL"], template_db))

    conn = await asyncpg.connect(admin_dsn)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{template_db}" WITH (FORCE)')
    finally:
        await conn.close()


async def test_template_build_is_race_free_under_concurrent_workers(
    _require_local_postgres,
) -> None:
    """The one-time template build is guarded by a Postgres ADVISORY LOCK
    (not a Python lock — real xdist workers are separate OS processes), so
    N workers calling `_xdist_ensure_template_database` at the same moment
    must not race each other. Simulates that with 8 concurrent asyncio
    tasks (each its own asyncpg connection, same as 8 separate processes
    would have) hitting the SAME template name at once.
    """
    import asyncio

    conftest = _load_conftest_module()
    namespace = _base_db_name(os.environ["TEST_DATABASE_URL"])
    admin_dsn = _admin_dsn(os.environ["TEST_DATABASE_URL"])
    template_db = conftest._xdist_template_db_name(namespace)

    conn = await asyncpg.connect(admin_dsn)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{template_db}" WITH (FORCE)')
    finally:
        await conn.close()

    try:
        results = await asyncio.gather(
            *[
                conftest._xdist_ensure_template_database(
                    admin_dsn, _scratch_source_db(), template_db
                )
                for _ in range(8)
            ],
            return_exceptions=True,
        )
        failures = [r for r in results if isinstance(r, Exception)]
        assert not failures, f"concurrent template build raced: {failures}"

        conn = await asyncpg.connect(admin_dsn)
        try:
            allow_conn = await conn.fetchval(
                "SELECT datallowconn FROM pg_database WHERE datname = $1", template_db
            )
        finally:
            await conn.close()
        assert allow_conn is False, "template must end up with ALLOW_CONNECTIONS false"
    finally:
        conn = await asyncpg.connect(admin_dsn)
        try:
            await conn.execute(f'DROP DATABASE IF EXISTS "{template_db}" WITH (FORCE)')
        finally:
            await conn.close()


async def test_probe_setup_survives_live_sessions_on_the_workers_own_database(
    _require_local_postgres,
) -> None:
    """GUILT for `_scratch_source_db` (2026-08-28, job 98762263195).

    CI died with `ObjectInUseError: source database "nuzantara_test_gw1" is
    being accessed by other users -- There are 2 other sessions using the
    database`, raised out of the SETUP of the probes above rather than out of
    their assertions, because they cloned their scratch database off the
    worker's own live database. Locally a worker often holds no open session
    at that instant, so the defect hid as an intermittent red; this pins the
    condition open instead of waiting for it.

    What makes this a probe and not a restatement: revert `_scratch_source_db`
    to reading `TEST_DATABASE_URL` and this test goes red, because the two
    sessions it holds are open against exactly the database the old shape
    would name as its template.
    """
    if not os.environ.get("PYTEST_XDIST_WORKER"):
        pytest.skip("only meaningful once conftest has repointed TEST_DATABASE_URL")

    conftest = _load_conftest_module()
    namespace = _base_db_name(os.environ["TEST_DATABASE_URL"])
    admin_dsn = _admin_dsn(os.environ["TEST_DATABASE_URL"])
    scratch_template = conftest._xdist_template_db_name(namespace)
    # Nested under this worker's own name, so it can never be a real worker
    # slot -- `nuzantara_test_gw1_gw9`, never `nuzantara_test_gw9`.
    scratch_db = f"{namespace}_gw9"

    assert namespace != _base_db_name(_pristine_dsn()), (
        "under xdist the worker's database must differ from the pristine base; "
        "if they are equal this probe proves nothing"
    )

    held = [await asyncpg.connect(os.environ["TEST_DATABASE_URL"]) for _ in range(2)]
    try:
        # Revert `_scratch_source_db` to the repointed variable and this line
        # is the CI failure again: `namespace` is what those two sessions are
        # open against. Deliberately NOT re-proving that the old shape fails --
        # `test_old_shape_templating_off_a_live_worker_database_fails` already
        # does, and its ~36s is the retry loop losing that fight once per run.
        await conftest._xdist_ensure_template_database(
            admin_dsn, _scratch_source_db(), scratch_template
        )
        await conftest._xdist_clone_worker_database(admin_dsn, scratch_template, scratch_db)
    finally:
        for conn in held:
            await conn.close()
        await conftest._xdist_drop_worker_database(admin_dsn, scratch_db)
        await conftest._xdist_drop_template_database(admin_dsn, scratch_template)
