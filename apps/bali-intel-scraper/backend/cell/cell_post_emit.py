"""Phase 3 TICKET B — IntelScraperHGTBridge post-pipeline emit.

Wires the existing IntelScraperHGTBridge (from
``apps/bali-intel-scraper/backend/cell/hgt_publisher.py:116``) into the
nightly cron entry script ``apps/bali-intel-scraper/scripts/run_intel_pipeline.py``
via async post-emit sidecar.

ARCHITECTURAL PIVOT (post 4-panel review): uses HGT-only path,
NOT ``IntelScraperCellRunner``. Reasons (see spec v2 §"Pivot"):
- ``IntelScraperCellRunner`` requires ``event_bridge: IntelScraperEventBridge``
- ``IntelScraperEventBridge`` constructor needs ``ObservedShellBus``
  (lives in ``backend-rag``, cross-package import smell)
- ``DATABASE_URL`` NOT in ``com.balizero.intel.nightly.plist`` (verified
  via ``plutil -extract EnvironmentVariables``)
- HGT-only path sidesteps both dependencies

Best-effort: any failure (Redis unreachable, wrong instance, import
error, runner exception) results in graceful no-op. Caller wraps with
``asyncio.wait_for(..., timeout=60.0)`` for cron safety.

Refusals respected (Phase 3 spec v2 §14):
- No edits to ``com.balizero.intel.nightly.plist``
- No new PG_CHANNEL_MAP entries
- No edits to ``packages/cell-core/cell_core/hgt/*`` (TICKET A.0 only)
- No edits to ``runner.py`` or ``event_bridge.py`` (HGT-only sidesteps)
- No HGT kill-switch lift
- No synchronous Redis calls
- No edits to ``apps/backend-rag/backend/services/events/observed_shell.py``

Reference:
- Spec v2: ``research/symbiosis/2026-05-13-ticket-b-narrow-spec.md``
- Brainstorm: ``docs/audits/2026-05-13-ticket-b-spec-brainstorm/``
- Parent Phase 3 spec v2: ``docs/superpowers/specs/2026-05-12-phase3-hgt-execution-spec.md``
"""
from __future__ import annotations

import contextlib
import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


async def _build_hgt_bridge() -> Any:
    """Build ``IntelScraperHGTBridge`` with Redis preflight + fallback.

    Returns bridge instance on success, ``None`` on any failure.
    Mandatory ``XLEN cell:skills >= 18`` signature check (Phase 2.5
    seed) confirms canonical Pro localhost Redis vs Mini split-brain.

    Best-effort: cleanly closes the redis client on any exception path.
    """
    import os

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    client = None
    try:
        import redis.asyncio as redis_async

        from backend.cell.hgt_publisher import IntelScraperHGTBridge

        client = redis_async.from_url(redis_url, decode_responses=False)
        cell_skills_len = await client.xlen("cell:skills")
        if cell_skills_len < 18:
            logger.error(
                "intel_scraper.preflight_failed cell_skills_len=%d expected_min=18 "
                "redis_url=%s — likely WRONG Redis instance. Aborting cell emit.",
                cell_skills_len,
                redis_url,
            )
            await client.aclose()
            return None
        logger.info(
            "intel_scraper.preflight_ok cell_skills_len=%d redis_url=%s",
            cell_skills_len,
            redis_url,
        )

        bridge = IntelScraperHGTBridge.from_redis(
            redis_client=client,
            cell_name="intel-scraper-cell",
            maxlen=1000,
        )
        return bridge
    except Exception as exc:  # noqa: BLE001 — defense in depth
        logger.error(
            "intel_scraper.hgt_bridge_assembly_failed err=%r — fallback to no-op",
            exc,
        )
        if client is not None:
            async with contextlib.suppress(Exception):
                await client.aclose()
        return None


def _extract_source(article: dict[str, Any]) -> str:
    """Extract canonical source name with schema-drift fallback chain.

    Empirical (verified 2026-05-13 00:55 WITA): articles in
    ``pipeline.state['articles']`` use ``'source_name'`` as primary
    (5 grep matches in ``run_intel_pipeline.py`` at lines
    429/959/1169/1475/1750), ``'source'`` as fallback. Final fallback
    to URL string, then literal ``'unknown'``.
    """
    return (
        article.get("source_name")
        or article.get("source")
        or article.get("url", "unknown")
    )


async def emit_pipeline_run(pipeline_state: dict[str, Any]) -> None:
    """Post-pipeline emit: compute ``rss_feed_stable`` pattern + publish via HGT.

    Best-effort: any exception swallowed with log. Single structural
    pattern v1: ``intel.source.rss_feed_stable_<source>_<run_id>``
    emitted when ≥1 source yielded ≥3 articles in this nightly run.

    Args:
        pipeline_state: ``IntelPipeline.state`` dict with ``articles`` list
            and ``run_id`` string. Tolerates missing keys via ``.get()``.
    """
    bridge = await _build_hgt_bridge()
    if bridge is None:
        return

    articles = pipeline_state.get("articles", [])
    if not articles:
        logger.info(
            "intel_scraper.hgt_emit_skipped reason=no_articles "
            "pipeline_state_keys=%s",
            list(pipeline_state.keys()),
        )
        return

    # Aggregate articles per canonical source
    source_counts: dict[str, int] = defaultdict(int)
    for article in articles:
        src = _extract_source(article)
        source_counts[src] += 1

    # Emit pattern only for strong sources (>= 3 articles)
    strong_sources = [
        (src, n) for src, n in source_counts.items() if n >= 3
    ]
    if not strong_sources:
        max_count = max(source_counts.values()) if source_counts else 0
        logger.info(
            "intel_scraper.hgt_emit_no_strong_sources articles=%d "
            "unique_sources=%d max_count=%d",
            len(articles),
            len(source_counts),
            max_count,
        )
        return

    try:
        from backend.cell.hgt_publisher import StructuralPattern
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "intel_scraper.structural_pattern_import_failed err=%r", exc,
        )
        return

    published_count = 0
    run_id = pipeline_state.get("run_id", "unknown")
    for source_name, article_count in strong_sources:
        pattern = StructuralPattern(
            pattern_id=f"rss_feed_stable_{source_name}_{run_id}",
            source=source_name,
            procedure=(
                f"Source {source_name} consistently yields articles "
                f"({article_count} in nightly run {run_id})"
            ),
            precondition="nightly intel-scraper crawl",
            success_criterion=(
                f"source {source_name} yields ≥3 articles in next "
                "nightly run"
            ),
            confidence=0.8,
            domain="news",
        )
        try:
            published = await bridge.publish(pattern)
            if published:
                published_count += 1
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "intel_scraper.pattern_publish_failed source=%s err=%r",
                source_name,
                exc,
            )

    logger.info(
        "intel_scraper.hgt_emit_complete strong_sources=%d "
        "published=%d run_id=%s",
        len(strong_sources),
        published_count,
        run_id,
    )


__all__ = [
    "emit_pipeline_run",
    "_extract_source",
]
