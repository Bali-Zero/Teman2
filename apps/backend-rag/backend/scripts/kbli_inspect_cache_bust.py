"""
kbli_inspect_cache_bust.py — evict `inspect_kbli`'s per-code Redis cache entries
so a data-plane cure actually reaches WhatsApp/webchat.

WHY THIS EXISTS (2026-07-24). `inspect_kbli`
(`GET /api/v1/kbli-notebook/inspect/{code}`, `kbli_notebook.py:352`) caches the
whole assembled `KBLIDetail` under `kbli_inspect_v2_{code}`, with a TTL from
`get_kbli_ttl()` that is **30 days** for most codes (12h only for 471/472/563/
661/62, 7d for 55/41/86/05..09). Every KBLI cure so far — the 8-code pilot, the
86-code `kbli_documents` cure, the 18-code 4th-surface cure, the 4-code phantom
cure — has had to evict this cache afterwards, and every one of them did it with
an ad-hoc snippet that left no trace. This script is that step, tracked.

Concrete failure it prevents (observed live, 2026-07-24): the phantom-row cure
detached all 53 REQUIRES edges for 26120/60111/82920/85598 and marked the nodes
`NOT_IN_KBLI_2025`; the DB was independently re-verified clean; and
`inspect_kbli` still served the FULL pre-cure payload — `TERBUKA`, `REGULATED`,
`Menengah Rendah`, 27 licences including plantation requirements under a
packaging code — because a diagnostic call made BEFORE the cure had populated a
30-day cache entry. Curing the store is not curing the surface (see memory
`feedback_merged_is_not_live_consumer_map_first_2026_07_16`).

WHAT IT DOES: for each `--only` code, reports whether `kbli_inspect_v2_{code}`
is currently present, and with `--apply` deletes it and RE-READS to confirm the
key is actually gone. The re-read matters: `CacheService.delete()` returning
True is the client's claim, not evidence, and a Redis-unavailable fallback path
silently degrades to an in-process LRU that a different worker process does not
share. Reporting present/deleted/still lets a caller see a lie.

SCOPE DISCIPLINE: `--only` is MANDATORY — there is no sweep. Evicting the whole
keyspace would cost a full cold rebuild of every code page on the next request
for no benefit; a cure knows exactly which codes it touched.

USAGE (dry-run is the default; nothing is evicted without --apply):
    PYTHONPATH=. python backend/scripts/kbli_inspect_cache_bust.py --only 82920
    fly ssh console -a nuzantara-rag -C \\
        "python /app/backend/scripts/kbli_inspect_cache_bust.py --only 26120,60111,82920,85598 --apply"
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("kbli_inspect_cache_bust")

# Must stay in lockstep with kbli_notebook.py:352. If that key format changes,
# this script silently evicts nothing and every cure after it ships a live lie —
# so the format is pinned by a test rather than trusted to stay in sync.
CACHE_KEY_TEMPLATE = "kbli_inspect_v2_{code}"


def cache_key(code: str) -> str:
    """Pure — the exact key `inspect_kbli` writes for a code."""
    return CACHE_KEY_TEMPLATE.format(code=code)


def parse_codes(raw: str) -> list[str]:
    """Pure — split/clean `--only`, preserving caller order, dropping blanks."""
    return [c.strip() for c in (raw or "").split(",") if c.strip()]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="evict (default: report only)")
    ap.add_argument(
        "--only",
        required=True,
        help="comma-separated 5-digit codes whose cache entry to evict (never a sweep)",
    )
    args = ap.parse_args()

    codes = parse_codes(args.only)
    if not codes:
        logger.error("--only produced an empty code list, nothing to do")
        raise SystemExit(2)

    # A one-shot process is NOT the app: `RedisManager` is initialized in the
    # FastAPI lifespan, so without this call `get_cache_service()` finds no
    # manager and silently degrades to a per-process in-memory LRU — which is
    # EMPTY here and would make every key look absent. That is a false clean:
    # the live web workers hold the poisoned entry in the SHARED Redis this
    # process never connected to. (Observed 2026-07-24: the first cut of this
    # script reported "0/4 had a cache entry" while Redis held all 4.)
    from backend.core.redis_manager import RedisManager

    RedisManager.get_instance().initialize()

    from backend.core.cache import get_cache_service

    cache = get_cache_service()
    if cache is None:
        logger.error("no cache service available — cannot verify or evict")
        raise SystemExit(2)

    # Force the lazy connect, then FAIL LOUD if Redis is configured but we did
    # not reach it. Reporting "nothing to evict" against a degraded in-memory
    # cache is the exact false-success this tool exists to prevent, so a
    # configured-but-unreachable Redis is an error, never a clean result.
    cache._try_connect_redis()  # the public cache API has no eager-connect hook
    redis_configured = bool(RedisManager.get_instance()._redis_url)
    if redis_configured and not cache.redis_available:
        logger.error(
            "REDIS_URL is configured but this process could not connect — refusing to "
            "report eviction against a per-process in-memory cache the web workers do not "
            "share. Run this where Redis is reachable."
        )
        raise SystemExit(3)
    logger.info(
        "cache backend: %s", "shared Redis" if cache.redis_available else "in-memory (no Redis configured)"
    )

    present = 0
    evicted = 0
    survived: list[str] = []

    for code in codes:
        key = cache_key(code)
        before = await cache.get(key)
        if before is None:
            logger.info("  %s: no cache entry (nothing to evict)", code)
            continue
        present += 1
        if not args.apply:
            logger.info("  %s: cache entry PRESENT — would evict %s", code, key)
            continue

        await cache.delete(key)
        # Re-read rather than trusting delete()'s return: that is the client's
        # claim, and a Redis-unavailable fallback silently uses a per-process
        # LRU another worker does not share.
        after = await cache.get(key)
        if after is None:
            evicted += 1
            logger.info("  %s: EVICTED (re-read confirms gone)", code)
        else:
            survived.append(code)
            logger.error("  %s: delete reported success but the key is STILL READABLE", code)

    mode = "APPLIED" if args.apply else "DRY-RUN"
    logger.info(
        "%s: %d/%d code(s) had a cache entry | %d evicted | %d survived",
        mode,
        present,
        len(codes),
        evicted,
        len(survived),
    )
    if survived:
        logger.error("keys that survived eviction: %s", ", ".join(survived))
        raise SystemExit(1)
    if not args.apply and present:
        logger.info("dry-run complete — rerun with --apply to evict")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
