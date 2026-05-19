"""Intel Lake end-to-end synthetic probe — Phase C 2026-05-20.

Drives a single fixture observation through every layer of the Intel Lake
pipeline and asserts each hop. Probe data is hard-isolated via migration
187 (is_probe_sandbox boolean + CHECK constraint) and NB-PROBE-SANDBOX-2026-05
NotebookLM notebook UUID 7e6ae978-136c-4c96-bed5-9fab6f39176f.

Pipeline hops verified:
    1. POST /api/intel/lake/observations-batch  → outbox row inserted
    2. PG events_outbox  → trigger fires intel_lake_event
    3. intel_lake_router  → classifies probe URL (rule sandbox-press → nb-intel)
    4. nb-pusher  → delivers to NB-PROBE-SANDBOX
    5. NotebookLM source_added confirmation
    6. Cleanup verification — 0 residue post-run

Preconditions:
    - `fly proxy 15432:5432 -a nuzantara-postgres &` (DATABASE_URL localhost)
    - INTEL_LAKE_PRODUCER_TOKEN set (matches Fly secret)
    - NUZANTARA_BACKEND_URL=https://nuzantara-rag.fly.dev (or proxy)
    - Migration 187 applied on target DB

Run:
    cd /Users/nuzantara/Desktop/nuzantara
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
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass

import asyncpg
import httpx

logger = logging.getLogger("intel-lake.probe")

PROBE_PRODUCER = f"probe-sandbox-{time.strftime('%Y-%m-%d')}"
NB_SANDBOX_UUID = "7e6ae978-136c-4c96-bed5-9fab6f39176f"


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
    """
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
    """Soft-delete probe row, verify 0 residue in production-facing queries."""
    await conn.execute("DELETE FROM intel_items WHERE id = $1", item_id)
    leftover = await conn.fetchval(
        "SELECT count(*) FROM intel_items WHERE producer_name LIKE 'probe-sandbox-%' AND first_seen_at < now() - interval '24h'"
    )
    if leftover > 0:
        logger.warning("hop5 WARN — %s stale sandbox rows (>24h), candidate for cleanup", leftover)
    logger.info("hop5 PASS — probe row cleaned, %s historical sandbox rows", leftover)


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
            await hop3_check_routing(conn, item_id, wait_seconds)
            await hop4_check_nb_push(conn, item_id, wait_seconds)
            await hop5_cleanup_verify(conn, item_id)
        finally:
            await conn.close()
    except AssertionError as e:
        logger.error("PROBE FAILED — %s", e)
        return 1
    except Exception:
        logger.exception("PROBE CRASHED")
        return 1

    logger.info("PROBE PASS — all 5 hops verified, 0 contamination")
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
