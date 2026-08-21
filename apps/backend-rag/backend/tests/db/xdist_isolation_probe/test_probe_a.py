"""Probe used ONLY by test_xdist_worker_isolation.py's guilt test.

Standalone by design (never imported by anything else): the main suite
collects this file too (nothing here is hidden from normal collection —
`norecursedirs` in pytest.ini does not exclude this directory), but every
test below no-ops unless `XDIST_PROBE_OUT` is set, which only happens when
`test_two_xdist_workers_do_not_share_a_database` spawns a NESTED
`pytest -n 2 --dist loadfile` run against this directory. `--dist loadfile`
sends a whole file to one worker, never splitting it — pairing this file
with its sibling `test_probe_b.py` is what forces the two onto DIFFERENT
xdist workers (gw0/gw1), which is the actual thing under test: does each
worker end up talking to a different Postgres database.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import asyncpg
import pytest

_OUT_DIR = os.environ.get("XDIST_PROBE_OUT")


@pytest.mark.skipif(
    not _OUT_DIR, reason="only meaningful under the nested xdist guilt-test spawn"
)
def test_probe_a_writes_and_sees_only_its_own_rows() -> None:
    result = asyncio.run(_run())
    # Assert directly in the test function (not just inside the awaited
    # helper) so this probe fails loudly at its own source, not only
    # indirectly via the outer nested-subprocess test's `returncode == 0` +
    # a.json read (RH005 anti-reward-hacking gate scans the `test_` function
    # body itself, not its full call graph).
    assert result["sources_seen"] == ["A"], (
        f"worker A saw rows from the other worker: {result['sources_seen']!r} — "
        "shared-Postgres pollution (the #4477 bug)"
    )


async def _run() -> dict[str, object]:
    dsn = os.environ["TEST_DATABASE_URL"]
    conn = await asyncpg.connect(dsn)
    try:
        db_name = await conn.fetchval("SELECT current_database()")
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS _xdist_isolation_probe "
            "(source text NOT NULL, worker text NOT NULL)"
        )
        await conn.execute(
            "INSERT INTO _xdist_isolation_probe (source, worker) VALUES ($1, $2)",
            "A",
            os.environ.get("PYTEST_XDIST_WORKER", "?"),
        )
        # Force overlap with the sibling worker's own insert+read: if (and
        # only if) isolation is broken and both workers share one database,
        # this sleep guarantees B's row is already there by the time we
        # SELECT below — turning "shared DB" into a deterministic failure
        # rather than a timing-dependent maybe.
        await asyncio.sleep(1.5)
        rows = await conn.fetch("SELECT source FROM _xdist_isolation_probe")
    finally:
        await conn.close()

    assert _OUT_DIR is not None  # guarded by skipif above
    result = {"db": db_name, "sources_seen": sorted(r["source"] for r in rows)}
    Path(_OUT_DIR, "a.json").write_text(json.dumps(result))
    return result
