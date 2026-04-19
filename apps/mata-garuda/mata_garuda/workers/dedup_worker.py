"""
Mata Garuda — URL-level Dedup Worker.

Reads from garuda:raw and drops items whose canonicalised URL has already
been seen in the last 30 days. Complements `normalizer.is_duplicate`
(which hashes title+url against KB): this worker is faster (Redis SET,
O(1)) and catches the case where two harvesters pick up the same URL
from different sources before the normalizer runs.

Optional semantic near-duplicate check (title + first 500 chars of
content) via Gemma Ollama is wired behind a flag — disabled by default
because it adds ~400ms/item. Enable only after benchmarking.

Layer 2 Kognitif — pre-enrichment dedup stage.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Callable
from urllib.parse import urlparse, urlunparse

from mata_garuda.config import STREAM_ENRICHED, STREAM_RAW
from mata_garuda.workers.base_worker import (
    content_hash,
    redis_cmd,
    stream_ack,
    stream_publish,
    stream_read_new,
)

logger = logging.getLogger("mata_garuda.workers.dedup")

CONSUMER_GROUP = "dedup"
CONSUMER_NAME = "dedup-1"

REDIS_DEDUP_SET = "garuda:dedup:urls"
DEDUP_TTL_SECONDS = 30 * 24 * 3600  # 30 days

_TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "_hsmi",
    "_hsenc",
}


def normalize_url(url: str) -> str:
    """Canonicalise a URL for dedup purposes.

    Strips scheme (http vs https), leading `www.`, trailing slash,
    fragment (`#...`), and known tracking query parameters.
    Returns the original string if parsing fails.
    """
    if not url:
        return ""

    url = url.strip()
    try:
        parsed = urlparse(url)
    except (ValueError, AttributeError):
        return url

    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]

    path = parsed.path or ""
    if path.endswith("/") and len(path) > 1:
        path = path[:-1]

    query_pairs = []
    if parsed.query:
        for pair in parsed.query.split("&"):
            if not pair:
                continue
            key = pair.split("=", 1)[0].lower()
            if key in _TRACKING_PARAMS:
                continue
            query_pairs.append(pair)
    query = "&".join(sorted(query_pairs))

    # Drop scheme (http:// vs https:// shouldn't diverge) and fragment
    return urlunparse(("", host, path, parsed.params, query, ""))


def url_fingerprint(url: str) -> str:
    """Stable short hash of the normalised URL for use as a SET member."""
    normalised = normalize_url(url)
    return content_hash(normalised) if normalised else ""


def is_seen(fingerprint: str, *, redis: Callable[..., str] = redis_cmd) -> bool:
    """True iff the fingerprint is already in the dedup SET."""
    if not fingerprint:
        return False
    result = redis("SISMEMBER", REDIS_DEDUP_SET, fingerprint)
    return result.strip() == "1"


def mark_seen(fingerprint: str, *, redis: Callable[..., str] = redis_cmd) -> None:
    """Add fingerprint to the dedup SET and refresh the 30-day TTL."""
    if not fingerprint:
        return
    redis("SADD", REDIS_DEDUP_SET, fingerprint)
    redis("EXPIRE", REDIS_DEDUP_SET, str(DEDUP_TTL_SECONDS))


def title_similarity(a: str, b: str) -> float:
    """Cheap token-overlap similarity for near-dupe detection.

    Jaccard over lowercase word tokens, stripping punctuation. Returns
    0.0 if either side is empty. Used only as a fast pre-filter before
    any optional LLM semantic check.
    """
    if not a or not b:
        return 0.0
    tokens_a = set(re.findall(r"\w+", a.lower()))
    tokens_b = set(re.findall(r"\w+", b.lower()))
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def run_dedup(
    max_items: int = 50,
    *,
    redis: Callable[..., str] = redis_cmd,
    publish: Callable[..., str] | None = None,
    ack: Callable[..., None] | None = None,
) -> dict:
    """Run one pass of the URL-dedup worker.

    Items with a new URL are forwarded to garuda:enriched with a
    `dedup_passed=true` field. Duplicates are ack'd without being
    republished, so downstream workers never see them.
    """
    publish = publish or (lambda stream, data: stream_publish(stream, data))
    ack = ack or (lambda stream, group, msg_id: stream_ack(stream, group, msg_id))

    stats = {"processed": 0, "duplicates": 0, "forwarded": 0, "skipped_no_url": 0}

    items = stream_read_new(STREAM_RAW, CONSUMER_GROUP, CONSUMER_NAME, count=max_items)
    if not items:
        return stats

    for item in items:
        msg_id = item["id"]
        data = dict(item["data"])
        stats["processed"] += 1

        url = data.get("url", "").strip()
        if not url:
            stats["skipped_no_url"] += 1
            ack(STREAM_RAW, CONSUMER_GROUP, msg_id)
            continue

        fp = url_fingerprint(url)
        if is_seen(fp, redis=redis):
            stats["duplicates"] += 1
            ack(STREAM_RAW, CONSUMER_GROUP, msg_id)
            continue

        mark_seen(fp, redis=redis)

        data["dedup_passed"] = "true"
        data["dedup_url_fingerprint"] = fp
        data["dedup_checked_at"] = datetime.now().isoformat(timespec="seconds")
        publish(STREAM_ENRICHED, data)
        stats["forwarded"] += 1

        ack(STREAM_RAW, CONSUMER_GROUP, msg_id)

    logger.info(
        f"[dedup] Done: {stats['processed']} processed, "
        f"{stats['forwarded']} forwarded, {stats['duplicates']} duplicates"
    )
    return stats
