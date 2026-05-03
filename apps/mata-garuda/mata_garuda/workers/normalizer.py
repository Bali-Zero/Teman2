"""
Mata Garuda — Normalizer Worker.

Reads from garuda:raw, deduplicates (SHA256 hash), normalizes to common schema,
stores in KB, publishes to garuda:enriched.

Layer 2 Kognitif — first worker in the pipeline.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from mata_garuda.config import STREAM_ENRICHED, STREAM_RAW
from mata_garuda.runtime.knowledge import KnowledgeBase
from mata_garuda.workers.base_worker import (
    content_hash,
    redis_cmd,
    stream_ack,
    stream_publish,
    stream_read_new,
)

logger = logging.getLogger("mata_garuda.workers")

CONSUMER_GROUP = "normalizer"
CONSUMER_NAME = "normalizer-1"


def normalize_item(raw_data: dict) -> dict:
    """Normalize a raw harvested item to a standard schema."""
    title = raw_data.get("title", "").strip()
    content = raw_data.get("content", "").strip()
    url = raw_data.get("url", "").strip()
    source = raw_data.get("source", "unknown")

    return {
        "title": title,
        "content": content,
        "url": url,
        "source": source,
        "source_type": raw_data.get("source_type", source),
        "content_hash": content_hash(f"{title}{url}"),
        "normalized_at": datetime.now().isoformat(timespec="seconds"),
        "agent": raw_data.get("agent", "unknown"),
        "timestamp": raw_data.get("timestamp", datetime.now().isoformat(timespec="seconds")),
    }


def is_duplicate(kb: KnowledgeBase, hash_value: str) -> bool:
    """Check if we've already processed an item with this hash."""
    results = kb.search(hash_value, limit=1)
    return len(results) > 0


def run_normalizer(kb: KnowledgeBase, max_items: int = 50) -> dict:
    """Run one pass of the normalizer worker.

    Returns stats dict: {processed, duplicates, published, errors}
    """
    stats = {"processed": 0, "duplicates": 0, "published": 0, "errors": 0}

    items = stream_read_new(STREAM_RAW, CONSUMER_GROUP, CONSUMER_NAME, count=max_items)

    if not items:
        logger.info("[normalizer] No new items in garuda:raw")
        return stats

    for item in items:
        msg_id = item["id"]
        raw_data = item["data"]
        stats["processed"] += 1

        try:
            normalized = normalize_item(raw_data)

            if is_duplicate(kb, normalized["content_hash"]):
                stats["duplicates"] += 1
                stream_ack(STREAM_RAW, CONSUMER_GROUP, msg_id)
                continue

            # Store hash for dedup tracking
            kb.store(
                agent="normalizer",
                entry_type="hash",
                content=normalized["content_hash"],
                source=normalized["url"],
                confidence=1.0,
            )

            # Store the FULL item in KB so downstream agents can search it
            kb.store(
                agent=normalized["agent"],
                entry_type="harvested_item",
                content=f"[{normalized['source_type']}] {normalized['title']}\n{normalized['content'][:800]}",
                source=normalized["url"],
                confidence=0.5,
            )

            # Publish to enriched stream
            stream_publish(STREAM_ENRICHED, normalized)
            stats["published"] += 1

            stream_ack(STREAM_RAW, CONSUMER_GROUP, msg_id)

        except Exception as e:
            logger.error(f"[normalizer] Error processing {msg_id}: {e}")
            stats["errors"] += 1

    logger.info(
        f"[normalizer] Done: {stats['processed']} processed, "
        f"{stats['published']} published, {stats['duplicates']} dupes"
    )
    return stats
