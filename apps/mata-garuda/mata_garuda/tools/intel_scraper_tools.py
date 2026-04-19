"""
Mata Garuda — Intel Scraper bridge tools.

Reads curated articles persisted by apps/bali-intel-scraper/ (609 sources)
from its local data directory. Mata Garuda does NOT touch the scraper code
or data; it consumes the already-written published_articles.json.

Contract:
- Input source: published_articles.json with {"articles": [{url,title,
  published_at,source?}, ...]}
- Env override: BALI_INTEL_SCRAPER_DATA_DIR — absolute path to the data dir.
  When unset, fall back to the repo-relative default
  apps/bali-intel-scraper/data/.
- OSINT blindato: file is read-only; no writes, no network.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("mata_garuda.tools.intel_scraper")

DEFAULT_REL_PATH = Path("apps") / "bali-intel-scraper" / "data"
PUBLISHED_FILE = "published_articles.json"


def _resolve_data_dir() -> Path:
    """Pick data dir from env or fall back to monorepo default.

    Env `BALI_INTEL_SCRAPER_DATA_DIR` wins when set. Otherwise we walk up
    from this file until we hit a monorepo root containing `apps/` and
    append the relative path.
    """
    env = os.environ.get("BALI_INTEL_SCRAPER_DATA_DIR")
    if env:
        return Path(env).expanduser()

    # Walk up from this file to find monorepo root (contains `apps/`)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "apps" / "bali-intel-scraper").is_dir():
            return parent / DEFAULT_REL_PATH

    # Last resort: cwd-relative
    return Path.cwd() / DEFAULT_REL_PATH


def read_published_articles(data_dir: Path | None = None) -> list[dict[str, Any]]:
    """Load the published articles list. Returns [] on missing/invalid file.

    Does NOT raise on missing file — harvester treats absence as
    case_not_resolved rather than crash.
    """
    base = data_dir if data_dir is not None else _resolve_data_dir()
    path = Path(base) / PUBLISHED_FILE
    if not path.is_file():
        logger.warning("published_articles file missing: %s", path)
        return []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("failed to parse %s: %s", path, exc)
        return []

    articles = payload.get("articles") if isinstance(payload, dict) else None
    if not isinstance(articles, list):
        logger.warning("published_articles shape unexpected in %s", path)
        return []

    # Defensive filter: keep only dicts with a usable url
    return [a for a in articles if isinstance(a, dict) and a.get("url")]


def filter_recent(
    articles: list[dict[str, Any]],
    since_iso: str | None,
) -> list[dict[str, Any]]:
    """Return articles whose published_at is >= since_iso (lexicographic).

    ISO-8601 strings sort correctly. When `since_iso` is None, returns all.
    Items without `published_at` are dropped — we only publish dated items
    to avoid duplicates across runs.
    """
    if since_iso is None:
        return list(articles)

    out: list[dict[str, Any]] = []
    for art in articles:
        ts = art.get("published_at")
        if isinstance(ts, str) and ts >= since_iso:
            out.append(art)
    return out
