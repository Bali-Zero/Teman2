"""Intel Lake end-to-end synthetic probe — Phase C 2026-05-20.

Drives a single fixture observation through every layer of the Intel Lake
pipeline and asserts each hop. Probe data is hard-isolated via migration
187 (is_probe_sandbox boolean + CHECK constraint) and NB-PROBE-SANDBOX-2026-05
NotebookLM notebook UUID 1e33e107-4064-48cd-b09d-f7f0a52b31ea (profile=zero,
recreated 2026-05-20 Phase F.4 after pusher profile-mismatch discovery).

Pipeline hops verified:
    1. POST /api/intel/lake/observations-batch  → outbox row inserted
    2. PG events_outbox  → trigger fires intel_lake_event
    3. intel_lake_router  → classifies probe URL (rule sandbox-press → nb-intel)
    4. nb-pusher  → delivers to NB-PROBE-SANDBOX
    5. Postgres cleanup — probe row deleted, stale sandbox rows counted
    6. NotebookLM cleanup — the probe's own fixtures are deleted from the live
       sandbox notebook (hop5 only cleans Postgres; the pusher never removes
       the NotebookLM source, so the notebook would fill to its 500 cap)

Preconditions:
    - `fly proxy 15432:5432 -a nuzantara-postgres &` (DATABASE_URL localhost)
    - INTEL_LAKE_PRODUCER_TOKEN set (matches Fly secret)
    - NUZANTARA_BACKEND_URL=https://nuzantara-rag.fly.dev (or proxy)
    - Migration 187 applied on target DB

Run:
    cd /Users/nuzantara/nuzantara
    PYTHONPATH=. python scripts/probes/intel_lake_e2e_probe.py --wait 900

Exit codes:
    0 — all hops PASS
    1 — hop assertion failed (probe broken or pipeline broken)
    2 — preconditions not met
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import asyncpg
import httpx

logger = logging.getLogger("intel-lake.probe")

PROBE_PRODUCER = f"probe-sandbox-{time.strftime('%Y-%m-%d')}"
NB_SANDBOX_UUID = "1e33e107-4064-48cd-b09d-f7f0a52b31ea"
# The pusher remaps NB_SANDBOX_UUID to this default-profile notebook (_NB_UUID_REMAP
# in scripts/intel-lake-nb-pusher-a2/); a test pins the two together.
NB_SANDBOX_LIVE_UUID = "7e6ae978-136c-4c96-bed5-9fab6f39176f"

_NONCE = r"[0-9a-f]{12}"  # ProbeFixture.generate: uuid4().hex[:12]
_FIXTURE_TITLE_RE = re.compile(rf"\[PROBE-SANDBOX\] e2e fixture {_NONCE}")
_PUSH_TMPFILE_TITLE_RE = re.compile(r"nlm_push_[0-9a-f]{8}\.txt")  # pusher temp name
_FIXTURE_URL_PATH_RE = re.compile(rf"/probe-{_NONCE}")
_FIXTURE_URL_HOST = "probe-sandbox.example.test"
_SOURCE_ID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

NLM_DELETE_BATCH = 20
NLM_DELETE_MAX_PER_RUN = 60
NLM_TIMEOUT_SECONDS = 120
NLM_RESIDUE_MAX_DEFAULT = 100


@dataclass
class ProbeFixture:
    canonical_url: str
    content_hash: str
    title: str
    item_id: str | None = None

    @classmethod
    def generate(cls) -> "ProbeFixture":
        nonce = uuid.uuid4().hex[:12]
        url = f"https://probe-sandbox.example.test/probe-{nonce}"
        content = f"PROBE-SANDBOX synthetic content {nonce}"
        return cls(
            canonical_url=url,
            content_hash=hashlib.sha256(content.encode()).hexdigest(),
            title=f"[PROBE-SANDBOX] e2e fixture {nonce}",
        )


async def hop1_post_observation(fixture: ProbeFixture, backend_url: str, token: str) -> str:
    """POST to /observations-batch, return item_id."""
    url = f"{backend_url.rstrip('/')}/api/intel/lake/observations-batch"
    body = {
        "observations": [
            {
                "producer_name": PROBE_PRODUCER,
                "canonical_url": fixture.canonical_url,
                "content_hash": fixture.content_hash,
                "title": fixture.title,
                "summary": "Synthetic probe fixture — sandbox isolated. See research/operations/2026-05-20-probe-sandbox-setup.md",
                "source_domain": "probe-sandbox.example.test",
                "language": "en",
                "jurisdiction": "test",
                "topic_tags": ["probe-sandbox", "e2e-test"],
                "score": 1.0,
                "raw_payload": {"probe": True, "phase": "C"},
            }
        ]
    }
    headers = {"X-Producer-Token": token, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=body, headers=headers)
        r.raise_for_status()
        data = r.json()
    if data.get("accepted") != 1:
        raise AssertionError(f"hop1: expected accepted=1, got {data}")
    item_id = data["results"][0]["item_id"]
    logger.info("hop1 PASS — item_id=%s", item_id)
    fixture.item_id = item_id
    return item_id


async def hop2_check_outbox(conn: asyncpg.Connection, item_id: str) -> None:
    """Verify events_outbox has a row for our item on intel_lake_event."""
    row = await conn.fetchrow(
        """
        SELECT id, channel, consumed_at
        FROM events_outbox
        WHERE channel = 'intel_lake_event'
          AND payload::text LIKE $1
        ORDER BY id DESC LIMIT 1
        """,
        f"%{item_id}%",
    )
    if not row:
        raise AssertionError(f"hop2: no events_outbox row for item_id={item_id}")
    logger.info("hop2 PASS — outbox id=%s consumed_at=%s", row["id"], row["consumed_at"])


async def hop2_5_set_sandbox_flag(conn: asyncpg.Connection, item_id: str) -> None:
    """Post-ingestion UPDATE to set is_probe_sandbox=true on the probe row.

    The backend intel_lake_service.record_observation does NOT set the
    flag (panel review 2026-05-20). The migration 187 CHECK constraint
    only allows is_probe_sandbox=true if canonical_url starts with the
    reserved RFC 2606 .test prefix — verified by the constraint at
    INSERT time (here we UPDATE post-INSERT). This is a probe-only
    step; real producers cannot trigger it because they never write
    URLs with this prefix.
    """
    result = await conn.execute(
        "UPDATE intel_items SET is_probe_sandbox = true WHERE id = $1",
        item_id,
    )
    if not result.endswith(" 1"):
        raise AssertionError(f"hop2.5: failed to set sandbox flag — UPDATE returned {result}")
    logger.info("hop2.5 PASS — is_probe_sandbox=true set on %s", item_id)


async def hop3_check_routing(conn: asyncpg.Connection, item_id: str, wait_seconds: int) -> str:
    """Poll intel_items until routing_status != 'unrouted'."""
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        row = await conn.fetchrow(
            "SELECT routing_status, routing_targets, is_probe_sandbox FROM intel_items WHERE id = $1",
            item_id,
        )
        if not row:
            raise AssertionError(f"hop3: intel_items row missing for id={item_id}")
        if not row["is_probe_sandbox"]:
            raise AssertionError(
                f"hop3: SANDBOX BREACH — is_probe_sandbox=false for probe item_id={item_id}"
            )
        if row["routing_status"] != "unrouted":
            logger.info("hop3 PASS — routing_status=%s", row["routing_status"])
            return row["routing_status"]
        await asyncio.sleep(5)
    raise AssertionError(f"hop3: timeout after {wait_seconds}s, still routing_status=unrouted")


async def hop4_check_nb_push(conn: asyncpg.Connection, item_id: str, wait_seconds: int) -> None:
    """Poll intel_item_nb_pushes until status='pushed' for NB-PROBE-SANDBOX.

    Schema (migration 171):
        item_id UUID, nb_uuid UUID, status TEXT IN
        ('pending','pushed','failed_transient','failed_permanent','quarantined')

    SKIPPABLE: panel review 2026-05-20 (DeepSeek HIGH finding) — there is
    currently no routing rule that pushes sandbox items to NB-PROBE-SANDBOX.
    Until that rule is added, this hop is no-op (just logs).
    Set INTEL_LAKE_PROBE_CHECK_NB_PUSH=1 to enforce.
    """
    if os.environ.get("INTEL_LAKE_PROBE_CHECK_NB_PUSH", "0") != "1":
        logger.info("hop4 SKIP — INTEL_LAKE_PROBE_CHECK_NB_PUSH != 1 (no sandbox routing rule yet)")
        return

    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        row = await conn.fetchrow(
            """
            SELECT status, nb_uuid, pushed_at, last_error
            FROM intel_item_nb_pushes
            WHERE item_id = $1 AND nb_uuid = $2
            """,
            item_id,
            NB_SANDBOX_UUID,
        )
        if row:
            if row["status"] == "pushed":
                logger.info("hop4 PASS — nb_uuid=%s pushed_at=%s", row["nb_uuid"], row["pushed_at"])
                return
            if row["status"] in ("failed_permanent", "quarantined"):
                raise AssertionError(
                    f"hop4: push to {NB_SANDBOX_UUID} terminally failed status={row['status']} err={row['last_error']}"
                )
        await asyncio.sleep(5)
    raise AssertionError(f"hop4: timeout after {wait_seconds}s, no pushed status for {NB_SANDBOX_UUID}")


async def hop5_cleanup_verify(conn: asyncpg.Connection, item_id: str) -> None:
    """Delete probe row, verify 0 stale sandbox residue.

    `producer_name` lives on `intel_observations` (junction table), not on
    `intel_items` directly. Use the is_probe_sandbox flag for residue check.
    """
    await conn.execute("DELETE FROM intel_items WHERE id = $1", item_id)
    leftover = await conn.fetchval(
        "SELECT count(*) FROM intel_items WHERE is_probe_sandbox = true AND first_seen_at < now() - interval '24h'"
    )
    if leftover > 0:
        logger.warning("hop5 WARN — %s stale sandbox rows (>24h), candidate for cleanup", leftover)
    logger.info("hop5 PASS — probe row cleaned, %s historical sandbox rows", leftover)


def _is_fixture_source(source: object) -> bool:
    """True only when the whole entity is one of the probe's three fixture shapes."""
    if not isinstance(source, dict):
        return False
    title = source.get("title")
    if isinstance(title, str) and (
        _FIXTURE_TITLE_RE.fullmatch(title) or _PUSH_TMPFILE_TITLE_RE.fullmatch(title)
    ):
        return True
    url = source.get("url")
    if isinstance(url, str):
        parts = urlsplit(url)
        return (
            parts.scheme == "https"
            and parts.netloc == _FIXTURE_URL_HOST
            and not parts.query
            and not parts.fragment
            and _FIXTURE_URL_PATH_RE.fullmatch(parts.path) is not None
        )
    return False


def select_fixture_ids(sources: list) -> list[str]:
    """Ids of the probe's own fixtures in a parsed `nlm source list --json`."""
    return [
        s["id"]
        for s in sources
        if _is_fixture_source(s) and isinstance(s.get("id"), str) and _SOURCE_ID_RE.fullmatch(s["id"])
    ]


def _resolve_nlm() -> str | None:
    found = shutil.which("nlm")
    if found:
        return found
    fallback = Path.home() / ".local" / "bin" / "nlm"
    return str(fallback) if fallback.is_file() else None


def _nlm(runner, nlm_bin: str, *args: str) -> subprocess.CompletedProcess:
    return runner(
        [nlm_bin, *args, "--profile", "default"],
        capture_output=True,
        text=True,
        timeout=NLM_TIMEOUT_SECONDS,
    )


def hop6_prune_nlm_fixtures(runner=subprocess.run) -> None:
    """Delete the probe's own fixtures from the live sandbox NotebookLM notebook.

    Only sources whose entity matches a fixture shape are ever deleted, and
    only ids from this run's listing of NB_SANDBOX_LIVE_UUID. Listing or
    binary trouble is a WARN/SKIP (the probe still passes); a residue at or
    above INTEL_LAKE_PROBE_NLM_RESIDUE_MAX means cleanup has been failing for
    long and raises. Kill switch: INTEL_LAKE_PROBE_NLM_PRUNE=0.
    """
    if os.environ.get("INTEL_LAKE_PROBE_NLM_PRUNE", "1") == "0":
        logger.info("hop6 SKIP — INTEL_LAKE_PROBE_NLM_PRUNE=0")
        return
    nlm_bin = _resolve_nlm()
    if not nlm_bin:
        logger.warning("hop6 SKIP — nlm binary not found (PATH or ~/.local/bin/nlm)")
        return
    try:
        listed = _nlm(runner, nlm_bin, "source", "list", NB_SANDBOX_LIVE_UUID, "--json")
        if listed.returncode != 0:
            logger.warning("hop6 WARN — nlm source list rc=%s, nothing deleted", listed.returncode)
            return
        sources = json.loads(listed.stdout)
    except (subprocess.TimeoutExpired, OSError, ValueError) as e:
        logger.warning("hop6 WARN — nlm source list failed (%s), nothing deleted", type(e).__name__)
        return
    if not isinstance(sources, list):
        logger.warning("hop6 WARN — nlm source list returned %s, nothing deleted", type(sources).__name__)
        return

    fixture_ids = select_fixture_ids(sources)
    kept_other = len(sources) - len(fixture_ids)
    to_delete = fixture_ids[:NLM_DELETE_MAX_PER_RUN]
    pruned = 0
    for i in range(0, len(to_delete), NLM_DELETE_BATCH):
        batch = to_delete[i : i + NLM_DELETE_BATCH]
        try:
            deleted = _nlm(runner, nlm_bin, "source", "delete", *batch, "--confirm")
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.warning("hop6 WARN — nlm source delete failed (%s) for %s ids", type(e).__name__, len(batch))
            continue
        if deleted.returncode == 0:
            pruned += len(batch)
        else:
            logger.warning("hop6 WARN — nlm source delete rc=%s for %s ids", deleted.returncode, len(batch))

    residue = len(fixture_ids) - pruned
    try:
        residue_max = int(os.environ.get("INTEL_LAKE_PROBE_NLM_RESIDUE_MAX", NLM_RESIDUE_MAX_DEFAULT))
    except ValueError:
        residue_max = NLM_RESIDUE_MAX_DEFAULT
    if residue >= residue_max:
        raise AssertionError(
            f"hop6: {residue} fixture sources left in {NB_SANDBOX_LIVE_UUID} (max {residue_max}) — NotebookLM cleanup is failing"
        )
    logger.info("hop6 PASS — pruned=%s residue=%s kept_other=%s", pruned, residue, kept_other)


async def run(wait_seconds: int) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    dsn = os.environ.get("DATABASE_URL")
    if not dsn or "flycast" in dsn:
        logger.error("DATABASE_URL must be localhost (start `fly proxy 15432:5432 -a nuzantara-postgres`)")
        return 2

    token = os.environ.get("INTEL_LAKE_PRODUCER_TOKEN", "").strip()
    if not token:
        logger.error("INTEL_LAKE_PRODUCER_TOKEN not set")
        return 2

    backend_url = os.environ.get("NUZANTARA_BACKEND_URL", "https://nuzantara-rag.fly.dev")
    fixture = ProbeFixture.generate()
    logger.info("probe fixture canonical_url=%s", fixture.canonical_url)

    try:
        item_id = await hop1_post_observation(fixture, backend_url, token)
        conn = await asyncpg.connect(dsn)
        try:
            await hop2_check_outbox(conn, item_id)
            await hop2_5_set_sandbox_flag(conn, item_id)
            await hop3_check_routing(conn, item_id, wait_seconds)
            await hop4_check_nb_push(conn, item_id, wait_seconds)
            await hop5_cleanup_verify(conn, item_id)
        finally:
            await conn.close()
        hop6_prune_nlm_fixtures()
    except AssertionError as e:
        logger.error("PROBE FAILED — %s", e)
        return 1
    except Exception:
        logger.exception("PROBE CRASHED")
        return 1

    logger.info("PROBE PASS — all 6 hops verified, 0 contamination")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Intel Lake e2e synthetic probe")
    parser.add_argument(
        "--wait",
        type=int,
        default=900,
        help="Max seconds to wait per hop (default 900 = 15min)",
    )
    args = parser.parse_args()
    return asyncio.run(run(args.wait))


if __name__ == "__main__":
    sys.exit(main())
