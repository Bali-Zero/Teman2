"""
Mata Garuda — NLM Feeder Worker.

Reads harvested items from KB, adds their URLs to the appropriate
NLM notebook. This is how NLM accumulates context over time —
after 30 days it has 300+ sources and becomes a real analytical brain.

Layer 3 Nexus.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from mata_garuda.config import NLM_NOTEBOOKS
from mata_garuda.runtime.knowledge import KnowledgeBase

logger = logging.getLogger("mata_garuda.workers")


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
    tmp = Path(f"/tmp/nlm_feed_{hash(title) & 0xFFFF:04x}.txt")
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
    """Route a source type to the appropriate NLM notebook ID."""
    routing = {
        "arxiv": "ai_research",
        "github": "ai_research",
        "youtube": "ai_research",
        "rss": "ai_research",
        "peraturan.go.id": "regulation",
    }
    nb_key = routing.get(source_type, "ai_research")
    return NLM_NOTEBOOKS.get(nb_key, "")


def run_nlm_feeder(kb: KnowledgeBase, max_items: int = 30) -> dict:
    """Feed harvested items to NLM notebooks.

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

        # Check if already fed
        already = kb.search(f"nlm_fed {url}", limit=1)
        if already:
            stats["skipped"] += 1
            continue

        # Determine source type from content
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

        # Try URL first, fallback to text
        if url.startswith("http://arxiv.org") or url.startswith("https://"):
            success = _nlm_add_url(notebook_id, url)
        else:
            title = content.split("\n")[0][:100]
            success = _nlm_add_text(notebook_id, title, content[:2000])

        if success:
            # Mark as fed
            kb.store("nlm_feeder", "nlm_fed", f"nlm_fed {url}", url, 1.0)
            stats["fed"] += 1
            logger.info(f"[nlm_feeder] Fed to NLM: {url[:80]}")
        else:
            stats["errors"] += 1

    logger.info(
        f"[nlm_feeder] Done: {stats['processed']} processed, "
        f"{stats['fed']} fed, {stats['skipped']} skipped, {stats['errors']} errors"
    )
    return stats
