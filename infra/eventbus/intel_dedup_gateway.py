#!/usr/bin/env python3
"""W3.2 — Intel Deduplication Gateway.

Subscribes to bz:intel.collected. For each event:
1. Compute content_hash (URL + title + entity + date + jurisdiction)
2. Check Redis SET bz:intel:seen for hash collision
3. If novel: SADD to seen set + emit bz:intel.deduped (preserve trace_id)
4. If duplicate: log + ack (no downstream propagation)

This collapses the 3-source duplication (intel-scraper, regulatory-watcher,
NB feeder) into a single canonical event stream.
"""
from __future__ import annotations
import os
import sys
import json
import logging
import hashlib
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from eventbus import EventSubscriber, publish, beat, start_background_beater
from eventbus.publisher import _client

LOG_PATH = Path.home() / "logs" / "intel-dedup-gateway.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger("intel-dedup-gateway")

SEEN_SET = "bz:intel:seen"
SEEN_TTL = 90 * 86400  # 90 days


def _content_hash(payload: dict) -> str:
    """Stable hash on (URL or citation, title, entity, date, jurisdiction)."""
    parts = [
        str(payload.get("citation_or_url", "")).strip().lower(),
        str(payload.get("source", "")).strip().lower(),
        # raw_payload may have title/entity/date — best-effort extraction
    ]
    rp = payload.get("raw_payload") or {}
    if isinstance(rp, dict):
        parts.extend([
            str(rp.get("title", "")).strip().lower(),
            str(rp.get("entity", "")).strip().lower(),
            str(rp.get("date", "")).strip(),
            str(rp.get("jurisdiction", "")).strip().lower(),
        ])
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]  # 64-bit truncated


def main() -> int:
    log.info("Intel Dedup Gateway starting.")
    start_background_beater("intel-dedup-gateway", interval=30)
    sub = EventSubscriber(
        agent_name="intel-dedup-gateway",
        event_types=["intel.collected"],
        start_from="$",
    )
    r = _client()

    n_seen = 0
    n_dup = 0
    n_new = 0

    for env in sub.listen(block_ms=10000, count=20):
        beat("intel-dedup-gateway")
        # Poison-pill: if event has been redelivered too many times, park to DLQ
        attempts = sub.get_delivery_count(env)
        if attempts > sub.MAX_DELIVERY_ATTEMPTS:
            sub.park_to_dlq(env, f"intel-dedup: exceeded {sub.MAX_DELIVERY_ATTEMPTS} attempts")
            continue
        n_seen += 1
        try:
            content_hash = _content_hash(env.payload)
            dedup_key = f"hash:{content_hash}"

            # Check + atomically claim
            already = r.sismember(SEEN_SET, dedup_key)
            if already:
                n_dup += 1
                log.info(
                    "DUPLICATE event=%s emitted_by=%s hash=%s (total dup=%d/%d)",
                    env.event_id, env.emitted_by, content_hash, n_dup, n_seen,
                )
                sub.ack(env)
                continue

            # Atomic add (race-safe vs concurrent dedup workers)
            added = r.sadd(SEEN_SET, dedup_key)
            r.expire(SEEN_SET, SEEN_TTL)

            if added == 0:
                # Race: another worker added it between our check and add
                n_dup += 1
                log.info("RACE-DUPLICATE event=%s hash=%s", env.event_id, content_hash)
                sub.ack(env)
                continue

            n_new += 1
            normalized_payload = {
                "source": env.payload.get("source"),
                "citation_or_url": env.payload.get("citation_or_url"),
                "raw_payload": env.payload.get("raw_payload"),
                "agent_name": env.payload.get("agent_name"),
                "collected_at": env.payload.get("collected_at"),
            }

            # Emit deduped event (PROPAGATE trace_id from source — causal chain)
            new_eid = publish(
                "intel.deduped",
                {
                    "original_event_id": env.event_id,
                    "content_hash": content_hash,
                    "dedup_key": dedup_key,
                    "normalized_payload": normalized_payload,
                    "deduped_at": datetime.now(timezone.utc).isoformat(),
                },
                emitted_by="intel-dedup-gateway",
                trace_id=env.trace_id,  # KEEP causal chain
            )
            log.info(
                "NEW event=%s -> deduped=%s hash=%s emitted_by=%s",
                env.event_id, new_eid, content_hash, env.emitted_by,
            )
        except Exception as e:
            log.exception("dedup processing failed for event %s: %s", env.event_id, e)
        finally:
            sub.ack(env)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log.info("Intel Dedup Gateway interrupted")
        sys.exit(0)
