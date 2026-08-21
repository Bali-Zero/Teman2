"""Sibling of test_probe_a.py — see that file's docstring for the full
rationale. Under `--dist loadfile`, pairing two files (never one file with
two test functions, which `--dist loadfile` would keep on a single worker)
is what forces this onto a DIFFERENT xdist worker than test_probe_a.py.
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
def test_probe_b_writes_and_sees_only_its_own_rows() -> None:
    result = asyncio.run(_run())
    # Assert directly in the test function (not just inside the awaited
    # helper) so this probe fails loudly at its own source, not only
    # indirectly via the outer nested-subprocess test's `returncode == 0` +
    # b.json read (RH005 anti-reward-hacking gate scans the `test_` function
    # body itself, not its full call graph).
    assert result["sources_seen"] == ["B"], (
        f"worker B saw rows from the other worker: {result['sources_seen']!r} — "
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
            "B",
            os.environ.get("PYTEST_XDIST_WORKER", "?"),
        )
        await asyncio.sleep(1.5)
        rows = await conn.fetch("SELECT source FROM _xdist_isolation_probe")
    finally:
        await conn.close()

    assert _OUT_DIR is not None  # guarded by skipif above
    result = {"db": db_name, "sources_seen": sorted(r["source"] for r in rows)}
    Path(_OUT_DIR, "b.json").write_text(json.dumps(result))
    return result
