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
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS _xdist_serial_probe (marker text NOT NULL)"
        )
        await conn.execute("DELETE FROM _xdist_serial_probe")
        await conn.execute(
            "INSERT INTO _xdist_serial_probe (marker) VALUES ($1)", "serial-innocence"
        )
        count = await conn.fetchval("SELECT count(*) FROM _xdist_serial_probe")
        await conn.execute("DROP TABLE _xdist_serial_probe")
    finally:
        await conn.close()
    assert count == 1


async def test_two_xdist_workers_do_not_share_a_database(
    _require_local_postgres, tmp_path
) -> None:
    """Guilt: under `-n 2 --dist loadfile`, two workers' writes to a
    same-named table never collide — because they are two different
    Postgres databases, not one shared one (the #4477/c92ed801 bug this
    fixture exists to close).
    """
    out_dir = tmp_path / "xdist-probe-out"
    out_dir.mkdir()
    base_db = _base_db_name(os.environ["TEST_DATABASE_URL"])

    env = dict(os.environ)
    env["XDIST_PROBE_OUT"] = str(out_dir)
    # The probe files resolve their own DSN from TEST_DATABASE_URL — pass
    # the same base URL this test itself is using (the nested pytest_configure
    # in the CHILD process will repoint it per-worker exactly like it does
    # for the real suite).
    env["TEST_DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    env.pop("PYTEST_XDIST_WORKER", None)  # this is the OUTER (possibly already-a-worker) run

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
            "-q",
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
