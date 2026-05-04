"""
Mata Garuda — NLM Feeder Worker.

Two modes:

1. KB-scan mode (legacy): `run_nlm_feeder(kb)` reads harvested_item entries
   from the SQLite KB and feeds them to the AI-research NB.

2. Stream mode (W3): `run_nlm_feeder_from_stream(kb)` consumes items from
   `garuda:enriched` and routes each to the domain-matched NLM notebook:
     - immigration_visa       → immigration NB
     - tax_fiscal             → tax NB
     - investment_licensing   → regulation NB
     - labor_manpower         → regulation NB
     - political_risk         → press NB
     - provincial_bali        → press NB
     - ai_research            → ai_research NB
     - other                  → skip (no feed)

Rate limit: max 10 items per run, 5s sleep between calls (NLM rate limits).
On MCP/CLI error: case_not_resolved logged, item NOT retried aggressively.

Layer 3 Nexus.
"""
from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path
from uuid import uuid4

from mata_garuda.config import (
    NLM_DOMAIN_ROUTING,
    NLM_FEEDER_BATCH_SIZE,
    NLM_FEEDER_SLEEP_BETWEEN_S,
    NLM_NOTEBOOKS,
    STREAM_ENRICHED,
)
from mata_garuda.runtime.knowledge import KnowledgeBase
from mata_garuda.workers.base_worker import (
    stream_ack,
    stream_read_new,
)

logger = logging.getLogger("mata_garuda.workers")

STREAM_CONSUMER_GROUP = "nlm_feeder"
STREAM_CONSUMER_NAME = "nlm_feeder-1"


def _nlm_add_url(notebook_id: str, url: str) -> bool:
    """Add a URL source to NLM notebook. Returns True on success."""
    if not notebook_id:
        return False
    try:
        result = subprocess.run(
            ["nlm", "source", "add", notebook_id, "--url", url],
            capture_output=True, text=True, timeout=60,
        )
        return result.returncode == 0
    except Exception as e:
        logger.warning(f"[nlm_feeder] Failed to add {url}: {e}")
        return False


def _nlm_add_text(notebook_id: str, title: str, text: str) -> bool:
    """Add text content to NLM notebook via temp file."""
    if not notebook_id:
        return False
    tmp = Path(f"/tmp/nlm_feed_{uuid4().hex[:8]}.txt")
    try:
        tmp.write_text(f"# {title}\n\n{text}")
        result = subprocess.run(
            ["nlm", "source", "add", notebook_id, "--file", str(tmp)],
            capture_output=True, text=True, timeout=60,
        )
        return result.returncode == 0
    except Exception as e:
        logger.warning(f"[nlm_feeder] Failed to add text '{title}': {e}")
        return False
    finally:
        tmp.unlink(missing_ok=True)


def _route_to_notebook(source_type: str) -> str:
    """Route a source type to the appropriate NLM notebook ID (legacy KB mode)."""
    routing = {
        "arxiv": "ai_research",
        "github": "ai_research",
        "youtube": "ai_research",
        "rss": "ai_research",
        "peraturan.go.id": "regulation",
    }
    nb_key = routing.get(source_type, "ai_research")
    return NLM_NOTEBOOKS.get(nb_key, "")


def route_domain_to_notebook(domain: str) -> tuple[str, str]:
    """Route an enriched item's domain/topic to an NLM notebook.

    Resolution order:
      1. If `domain` is a business-domain key (e.g. "tax_fiscal") in
         NLM_DOMAIN_ROUTING, follow the mapping to nb_key.
      2. If `domain` is itself a notebook key (e.g. "ai_research",
         "press") present in NLM_NOTEBOOKS, treat it as already-resolved.
         This handles items whose `domain` was inferred directly from
         source_type (sentinel/intel_scraper) without an intermediate
         business-domain label.

    Returns (nb_key, notebook_id). Either can be empty string if unrouted
    or notebook not configured.
    """
    key = (domain or "").strip()
    if not key:
        return ("", "")

    nb_key = NLM_DOMAIN_ROUTING.get(key, "")
    if not nb_key and key in NLM_NOTEBOOKS:
        nb_key = key

    if not nb_key:
        return ("", "")
    return (nb_key, NLM_NOTEBOOKS.get(nb_key, ""))


# Heuristic source→domain map for items that arrive without a `domain`
# field. Producers like sentinel (arxiv/rss/github/youtube) and
# intel_scraper_bridge (bali-intel-scraper) write `source` and
# `source_type` but not `domain`; without a fallback every enriched
# item gets skipped.
_SOURCE_TO_DOMAIN: dict[str, str] = {
    "arxiv": "ai_research",
    "github": "ai_research",
    "youtube": "ai_research",
    "rss": "ai_research",  # AI-research RSS feeds (jack-clark.net, hf blog, etc)
    "intel_scraper": "press",  # bali-intel-scraper articles → press feed
}


def infer_domain_from_item(data: dict) -> str:
    """Best-effort domain inference when the item has none.

    Order:
      1. data["domain"] / data["topic"] if non-empty
      2. data["source_type"] mapped via _SOURCE_TO_DOMAIN
      3. data["source"] mapped via _SOURCE_TO_DOMAIN
      4. "" (caller should treat as unrouted → skip)
    """
    explicit = (data.get("domain") or data.get("topic") or "").strip()
    if explicit:
        return explicit

    source_type = (data.get("source_type") or "").strip().lower()
    if source_type in _SOURCE_TO_DOMAIN:
        return _SOURCE_TO_DOMAIN[source_type]

    source = (data.get("source") or "").strip().lower()
    if source in _SOURCE_TO_DOMAIN:
        return _SOURCE_TO_DOMAIN[source]

    return ""


def _nlm_fed_marker(url_or_hash: str) -> str:
    return f"nlm_fed {url_or_hash}"


def _already_fed(kb: KnowledgeBase, dedup_key: str) -> bool:
    """Check if we've previously fed this dedup_key.

    Uses a direct SQL lookup on (type='nlm_fed', source=dedup_key) instead of
    FTS5 search — FTS5 tokenization doesn't handle URLs reliably.
    """
    try:
        cursor = kb._conn.execute(
            "SELECT 1 FROM knowledge WHERE type = 'nlm_fed' AND source = ? LIMIT 1",
            (dedup_key,),
        )
        return cursor.fetchone() is not None
    except Exception:
        return False


def run_nlm_feeder(kb: KnowledgeBase, max_items: int = 30) -> dict:
    """Feed harvested items to NLM notebooks (legacy KB-scan mode).

    Reads items from KB, adds URLs to appropriate NLM notebook.
    Tracks what's been fed via KB entry type 'nlm_fed'.

    Returns stats: {processed, fed, skipped, errors}
    """
    stats = {"processed": 0, "fed": 0, "skipped": 0, "errors": 0}

    items = kb.get_by_type("harvested_item", limit=max_items)
    if not items:
        logger.info("[nlm_feeder] No harvested items in KB")
        return stats

    for item in items:
        stats["processed"] += 1
        url = item.get("source", "")

        if not url or not url.startswith("http"):
            stats["skipped"] += 1
            continue

        already = kb.search(f"nlm_fed {url}", limit=1)
        if already:
            stats["skipped"] += 1
            continue

        content = item.get("content", "")
        source_type = "arxiv"
        if "[github]" in content.lower():
            source_type = "github"
        elif "[rss]" in content.lower():
            source_type = "rss"
        elif "[youtube]" in content.lower():
            source_type = "youtube"

        notebook_id = _route_to_notebook(source_type)
        if not notebook_id:
            stats["skipped"] += 1
            continue

        if url.startswith("http://arxiv.org") or url.startswith("https://"):
            success = _nlm_add_url(notebook_id, url)
        else:
            title = content.split("\n")[0][:100]
            success = _nlm_add_text(notebook_id, title, content[:2000])

        if success:
            kb.store("nlm_feeder", "nlm_fed", _nlm_fed_marker(url), url, 1.0)
            stats["fed"] += 1
            logger.info(f"[nlm_feeder] Fed to NLM: {url[:80]}")
        else:
            stats["errors"] += 1

    logger.info(
        f"[nlm_feeder] Done: {stats['processed']} processed, "
        f"{stats['fed']} fed, {stats['skipped']} skipped, {stats['errors']} errors"
    )
    return stats


def run_nlm_feeder_from_stream(
    kb: KnowledgeBase,
    max_items: int = NLM_FEEDER_BATCH_SIZE,
    sleep_s: float = NLM_FEEDER_SLEEP_BETWEEN_S,
) -> dict:
    """Consume garuda:enriched and feed domain-routed items to NLM.

    Each enriched item is routed via its ``domain`` (or fallback ``topic``)
    field. Unrouted domains are skipped (NOT an error). ACK happens for
    every consumed message — success OR skip OR error — so the stream
    doesn't back up on persistent problems (we log via ``case_not_resolved``).

    Rate-limited: max ``max_items`` per run, ``sleep_s`` between NLM calls.

    Returns stats: {processed, fed, skipped, errors}
    """
    stats = {"processed": 0, "fed": 0, "skipped": 0, "errors": 0}

    items = stream_read_new(
        STREAM_ENRICHED, STREAM_CONSUMER_GROUP, STREAM_CONSUMER_NAME,
        count=max_items,
    )
    if not items:
        logger.info("[nlm_feeder] No new items in garuda:enriched")
        return stats

    for idx, item in enumerate(items):
        stats["processed"] += 1
        msg_id = item["id"]
        data = item.get("data") or {}

        title = data.get("title", "") or ""
        content = data.get("content", "") or ""
        url = data.get("url", "") or data.get("source_url", "") or data.get("source", "")
        domain = infer_domain_from_item(data)

        nb_key, notebook_id = route_domain_to_notebook(domain)
        if not nb_key:
            stats["skipped"] += 1
            stream_ack(STREAM_ENRICHED, STREAM_CONSUMER_GROUP, msg_id)
            continue
        if not notebook_id:
            # Domain is mapped but NB ID is unset — treat as skip, log warning.
            logger.warning(
                f"[nlm_feeder] domain={domain} mapped to nb_key={nb_key} "
                f"but no notebook_id configured; skipping"
            )
            stats["skipped"] += 1
            stream_ack(STREAM_ENRICHED, STREAM_CONSUMER_GROUP, msg_id)
            continue

        # Dedup: if we've already fed this URL, skip. Look up by (type, source)
        # directly — FTS5 doesn't tokenize URLs reliably.
        dedup_key = url or f"title:{title}"
        already = _already_fed(kb, dedup_key)
        if already:
            stats["skipped"] += 1
            stream_ack(STREAM_ENRICHED, STREAM_CONSUMER_GROUP, msg_id)
            continue

        # Feed as text (title + content) so NLM gets context even if URL
        # is paywalled. Matches briefing spec.
        text_body = content[:4000] if content else title
        effective_title = (title or dedup_key)[:200]
        success = _nlm_add_text(notebook_id, effective_title, text_body)

        if success:
            kb.store(
                "nlm_feeder",
                "nlm_fed",
                _nlm_fed_marker(dedup_key),
                dedup_key,
                1.0,
            )
            stats["fed"] += 1
            logger.info(
                f"[nlm_feeder] Fed to {nb_key}: "
                f"{effective_title[:60]} (domain={domain})"
            )
        else:
            stats["errors"] += 1
            kb.store(
                "nlm_feeder",
                "case_not_resolved",
                f"nlm_feed_fail {effective_title[:80]} nb={nb_key}",
                dedup_key,
                0.3,
            )

        stream_ack(STREAM_ENRICHED, STREAM_CONSUMER_GROUP, msg_id)

        # Rate limit between NLM calls (skip sleep after last item).
        if idx + 1 < len(items) and sleep_s > 0:
            time.sleep(sleep_s)

    logger.info(
        f"[nlm_feeder] Stream done: {stats['processed']} processed, "
        f"{stats['fed']} fed, {stats['skipped']} skipped, {stats['errors']} errors"
    )
    return stats
