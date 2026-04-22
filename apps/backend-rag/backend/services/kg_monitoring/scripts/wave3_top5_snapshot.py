"""Wave 3 top-5 authoritative domain snapshot.

Scrapes one canonical landing page per KG-critical .go.id domain using the
wave 2 LegalScraper's UA-rotation + Playwright-fallback primitives, then
writes each response under
``apps/backend-rag/backend/kb/raw/top5_wave3/<domain>/``. Intentionally
single-page per domain — this run is preparatory for wave 4 KG ingestion,
NOT a full crawl. Rate limits are respected (per-source ``rate_limit_delay``)
and only one domain at a time fetches.

Usage:
    PYTHONPATH=apps/backend-rag python -m backend.services.kg_monitoring.scripts.wave3_top5_snapshot

The script exits 0 on full success (5/5), 1 otherwise so operators can
notice partial runs.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from backend.services.kg_monitoring.scraper import (
    LegalScraper,
    SourceConfig,
    SourceType,
)

logger = logging.getLogger(__name__)

# Repo-root-relative location where snapshots land. Resolved at runtime so
# the script is portable between Pro and Air worktrees.
_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[6]  # .../nuzantara-wave3-kg/
RAW_ROOT = _REPO_ROOT / "apps/backend-rag/backend/kb/raw/top5_wave3"


TOP5_SOURCES: dict[str, SourceConfig] = {
    "imigrasi": SourceConfig(
        source_id="imigrasi",
        name="Direktorat Jenderal Imigrasi (KITAS/KITAP)",
        base_url="https://www.imigrasi.go.id/",
        source_type=SourceType.GOVERNMENT_SITE,
        search_paths=[""],  # landing page only — non-paginated snapshot
        rate_limit_delay=3.0,
        timeout=30,
        max_retries=3,
        rotate_user_agent=True,
        use_playwright_fallback=False,  # wave 1 confirmed httpx-friendly
        http2=True,
    ),
    "oss": SourceConfig(
        source_id="oss",
        name="OSS-RBA (PT PMA / NIB)",
        base_url="https://oss.go.id/",
        source_type=SourceType.GOVERNMENT_SITE,
        search_paths=["id"],  # OSS redirects / → /id, follow directly
        rate_limit_delay=3.0,
        timeout=30,
        max_retries=3,
        rotate_user_agent=True,
        # Wave 1 flagged JS-rendered; we still try httpx first because the
        # /id endpoint may serve static HTML shell. Fallback only triggers
        # on block-status responses, per scraper._BLOCK_STATUSES.
        use_playwright_fallback=True,
        http2=True,
    ),
    "pajak": SourceConfig(
        source_id="pajak",
        name="Direktorat Jenderal Pajak (CoreTax)",
        base_url="https://pajak.go.id/",
        source_type=SourceType.GOVERNMENT_SITE,
        search_paths=[""],
        rate_limit_delay=3.0,
        timeout=45,  # wave 1 reported timeouts — give it more slack
        max_retries=3,
        rotate_user_agent=True,
        use_playwright_fallback=True,
        http2=True,
    ),
    "tarubali": SourceConfig(
        source_id="tarubali",
        name="Dinas Tata Ruang Bali (RTRW)",
        base_url="https://tarubali.baliprov.go.id/",
        source_type=SourceType.GOVERNMENT_SITE,
        search_paths=[""],
        rate_limit_delay=3.0,
        timeout=30,
        max_retries=3,
        rotate_user_agent=True,
        use_playwright_fallback=False,
        http2=True,
    ),
    "bpjs_ketenagakerjaan": SourceConfig(
        source_id="bpjs_ketenagakerjaan",
        name="BPJS Ketenagakerjaan",
        base_url="https://www.bpjsketenagakerjaan.go.id/",
        source_type=SourceType.GOVERNMENT_SITE,
        search_paths=[""],
        rate_limit_delay=3.0,
        timeout=30,
        max_retries=3,
        rotate_user_agent=True,
        use_playwright_fallback=False,
        http2=True,
    ),
}


def _safe_filename(url: str) -> str:
    """Derive a flat, writable filename from a URL."""
    return (
        url.replace("https://", "")
        .replace("http://", "")
        .replace("/", "_")
        .replace("?", "_")
        .strip("_")
        or "landing"
    )


async def snapshot_one(
    scraper: LegalScraper,
    source_id: str,
    source: SourceConfig,
    out_dir: Path,
) -> dict:
    """Fetch the configured landing page(s) and persist raw HTML + meta."""
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "source_id": source_id,
        "name": source.name,
        "base_url": source.base_url,
        "pages": [],
        "errors": [],
        "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
        "used_playwright_at_start": scraper.scrape_stats.get(
            "playwright_fallback_invocations", 0,
        ),
    }
    client = scraper._get_client()
    for path in source.search_paths:
        url = source.base_url.rstrip("/") + ("/" + path.lstrip("/") if path else "")
        logger.info("[%s] fetching %s", source_id, url)
        response = await scraper._fetch_with_retry(client, url, source)
        if response is None:
            result["errors"].append({"url": url, "reason": "fetch_returned_none"})
            continue
        try:
            text = response.text
        except Exception as e:
            result["errors"].append({"url": url, "reason": f"decode_failed:{e}"})
            continue
        fname = _safe_filename(url)
        (out_dir / f"{fname}.html").write_text(text, encoding="utf-8")
        result["pages"].append(
            {
                "url": url,
                "status": response.status_code,
                "bytes": len(text),
                "file": f"{fname}.html",
            },
        )
    # Delta in playwright invocations tells us whether the fallback was
    # needed for this specific source.
    pw_end = scraper.scrape_stats.get("playwright_fallback_invocations", 0)
    result["playwright_invocations_for_source"] = pw_end - result.pop(
        "used_playwright_at_start",
    )
    (out_dir / "meta.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8",
    )
    return result


async def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [wave3-top5] %(message)s",
        datefmt="%H:%M:%S",
    )
    RAW_ROOT.mkdir(parents=True, exist_ok=True)
    scraper = LegalScraper(custom_sources=TOP5_SOURCES)

    overall: dict = {"started": datetime.now(tz=timezone.utc).isoformat(), "runs": []}
    ok = 0
    for source_id, source in TOP5_SOURCES.items():
        out_dir = RAW_ROOT / source_id
        res = await snapshot_one(scraper, source_id, source, out_dir)
        overall["runs"].append(res)
        if res["pages"] and not res["errors"]:
            ok += 1
            logger.info(
                "[%s] OK — %d page(s) saved to %s",
                source_id,
                len(res["pages"]),
                out_dir,
            )
        else:
            logger.warning(
                "[%s] PARTIAL/FAIL — pages=%d errors=%d",
                source_id,
                len(res["pages"]),
                len(res["errors"]),
            )

    await scraper.close()

    overall["ended"] = datetime.now(tz=timezone.utc).isoformat()
    overall["successful_sources"] = ok
    overall["total_sources"] = len(TOP5_SOURCES)
    overall["scrape_stats"] = scraper.get_stats()
    (RAW_ROOT / "index.json").write_text(
        json.dumps(overall, indent=2, default=str), encoding="utf-8",
    )
    logger.info(
        "Wave 3 snapshot: %d/%d sources successful — index.json written.",
        ok,
        len(TOP5_SOURCES),
    )
    return 0 if ok == len(TOP5_SOURCES) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
