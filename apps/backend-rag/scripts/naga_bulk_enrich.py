#!/usr/bin/env python3
"""Naga Bulk Enrichment — runs hundreds of curated queries to populate the Claims DB.

Runs LOCALLY (not via Fly.io) using the real orchestrator + PostgreSQL tunnel.
Claims are saved to naga_claims, naga_sessions, naga_sources via persist.py.

Usage:
    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. python scripts/naga_bulk_enrich.py
    PYTHONPATH=. python scripts/naga_bulk_enrich.py --tier flash --limit 20
    PYTHONPATH=. python scripts/naga_bulk_enrich.py --category visa --dry-run

Requirements:
    - PostgreSQL tunnel: ssh -L 15432:localhost:5432 air (or dev-local alias)
    - DATABASE_URL env var pointing to tunnel
    - BRAVE_API_KEY for web search
    - gemini CLI installed (for deep tier)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import asyncpg
import httpx

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("naga.bulk_enrich")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Query corpus — curated Indonesian legal/business/immigration topics
# ---------------------------------------------------------------------------

QUERY_CORPUS: dict[str, list[str]] = {
    "visa": [
        "KITAS requirements Indonesia 2025",
        "KITAS vs KITAP differences Indonesia",
        "Investor KITAS requirements PT PMA 2025",
        "Retirement KITAS requirements Indonesia age",
        "Family KITAS spouse dependent requirements",
        "KITAS renewal process timeline Indonesia",
        "KITAP permanent stay permit conversion requirements",
        "Golden visa Indonesia requirements 2025",
        "B211A visa social budaya Indonesia requirements",
        "E31A digital nomad visa Indonesia",
        "E23A investor visa Indonesia requirements",
        "Visit visa extension Indonesia 2025",
        "Visa on arrival Indonesia duration extension",
        "Work permit IMTA requirements Indonesia",
        "RPTKA foreign worker quota Indonesia",
        "KITAS sponsor requirements employer Indonesia",
        "ITAS social kemanusiaan requirements Indonesia",
        "Ministry of Immigration Indonesia digital services",
        "Imigrasi online application Indonesia 2025",
        "Blacklist deportation Indonesia visa consequences",
    ],
    "company": [
        "PT PMA requirements minimum capital 2025",
        "PT PMA vs CV vs PT differences Indonesia",
        "PT PMA foreign ownership restrictions Indonesia",
        "Negative investment list Indonesia DNI 2025",
        "KBLI codes allowed for foreign companies Indonesia",
        "PT PMA establishment process OSS Indonesia",
        "NIB business registration Indonesia OSS requirements",
        "Perseroan Terbatas founding requirements Indonesia",
        "PT PMA director requirements Indonesia foreign nationals",
        "PT PMA commissioner requirements Indonesia",
        "Virtual office requirements Indonesia legal address",
        "PT PMA minimum employees requirement Indonesia",
        "PT PMA annual reporting obligations Indonesia",
        "OSS RBA risk-based approach Indonesia business license",
        "BKPM investment requirements Indonesia 2025",
        "PT PMA tax obligations Indonesia corporate tax",
        "PT PMA import export license Indonesia",
        "Nominee director illegal Indonesia consequences",
        "PT PMA bank account requirements Indonesia",
        "Foreign company representative office KPPA Indonesia",
    ],
    "property": [
        "Foreigners buying property Indonesia rules 2025",
        "Hak Pakai foreigners Indonesia land rights",
        "Hak Milik Indonesian citizen only property",
        "Property ownership via PT PMA Indonesia pros cons",
        "Leasehold vs freehold property Bali Indonesia",
        "Strata title apartment foreigners Indonesia",
        "Property notary requirements Indonesia akta jual beli",
        "Land certificate types Indonesia SHM SHGB",
        "Property tax Indonesia PPN BPHTB",
        "Inheritance property foreigners Indonesia",
        "Nominee arrangement property Indonesia illegal",
        "HGB land rights duration renewal Indonesia",
        "Property investment minimum value foreigners Indonesia",
        "AJB akta jual beli process Indonesia property",
        "PPJB pre-sale agreement Indonesia property risks",
    ],
    "tax": [
        "Indonesian personal income tax rates 2025",
        "Indonesian corporate tax rate PT PMA 2025",
        "VAT PPN Indonesia rate 11% services",
        "Indonesian tax residency requirements 183 days",
        "NPWP tax number foreigners Indonesia requirements",
        "Annual tax return SPT Indonesia deadline",
        "Withholding tax PPh 21 23 26 Indonesia",
        "Tax treaty Indonesia countries double taxation",
        "BPJS health insurance contributions Indonesia",
        "BPJS ketenagakerjaan social security Indonesia employers",
        "PT PMA tax holidays incentives Indonesia",
        "Transfer pricing rules Indonesia related party",
        "Dividend tax Indonesia foreign shareholders",
        "Capital gains tax property Indonesia",
        "Import duty Indonesia customs tariff rates",
    ],
    "kbli": [
        "KBLI 68120 real estate own property Indonesia",
        "KBLI 55110 hotel accommodation Indonesia",
        "KBLI 56101 restaurant food beverage Indonesia",
        "KBLI 62019 software development Indonesia",
        "KBLI 70200 management consulting Indonesia",
        "KBLI 74909 professional services Indonesia",
        "KBLI 47 retail trade Indonesia requirements",
        "KBLI 68200 property rental leasing Indonesia",
        "KBLI 82990 business support services Indonesia",
        "KBLI codes tourism hospitality Bali Indonesia",
        "KBLI 2025 changes updates classification",
        "PMA allowed KBLI sectors Indonesia investment",
        "KBLI risk categories low medium high Indonesia",
        "KBLI 63 IT services digital economy Indonesia",
        "KBLI agriculture farming foreigners Indonesia restrictions",
    ],
    "banking": [
        "Opening bank account Indonesia foreigner requirements",
        "Bank Central Asia BCA account foreigners",
        "Bank Mandiri account opening requirements foreigners",
        "Indonesian bank transfer limits international",
        "SWIFT wire transfer Indonesia banks",
        "Foreign currency account Indonesia requirements",
        "Bank account requirements PT PMA Indonesia",
        "Mobile banking Indonesia digital banks",
        "OVO GoPay e-wallet foreigners Indonesia",
        "Bitcoin cryptocurrency regulations Indonesia 2025",
    ],
    "employment": [
        "Hiring local employees Indonesia regulations",
        "Employment contract requirements Indonesia",
        "Minimum wage Indonesia UMR UMK 2025",
        "Severance pay Indonesia calculation rules",
        "Notice period termination Indonesia employment law",
        "Work permit process expats Indonesia IMTA",
        "Expatriate ratio local workers Indonesia",
        "Omnibus law employment changes Indonesia 2025",
        "Freelancer contract Indonesia tax implications",
        "Remote work Indonesia employment regulations",
    ],
    "bali_specific": [
        "Bali zoning regulations tourism villa",
        "Bali IMB building permit requirements",
        "Bali villa rental license requirements",
        "Bali region investment restrictions",
        "Ngurah Rai airport arrival procedures Indonesia",
        "Bali cultural zone property restrictions",
        "Seminyak Canggu Ubud property market",
        "Bali coworking space digital nomad requirements",
        "Bali environmental regulations business",
        "Denpasar city regulations business license",
    ],
    "compliance": [
        "AML anti-money laundering Indonesia regulations",
        "PPATK financial intelligence unit Indonesia",
        "KYC know your customer requirements Indonesia banks",
        "Data privacy regulations Indonesia UU PDP",
        "Beneficial ownership disclosure Indonesia",
        "FCPA UKBA anti-corruption compliance Indonesia",
        "Environmental compliance AMDAL Indonesia business",
        "Consumer protection law Indonesia e-commerce",
        "Intellectual property trademark registration Indonesia",
        "Copyright protection Indonesia creative works",
    ],
    "immigration_processes": [
        "Telex visa approval Indonesia process",
        "Visa extension overstay fines Indonesia",
        "Emergency exit permit Indonesia surat jalan",
        "Multiple entry visa Indonesia eligibility",
        "Exit reentry permit KITAS Indonesia",
        "Lost passport replacement Indonesia process",
        "Marriage to Indonesian citizen visa benefits",
        "Divorce Indonesia foreigner legal process",
        "Child birth registration Indonesia foreigner",
        "Adoption regulations Indonesia foreign nationals",
    ],
}


# ---------------------------------------------------------------------------
# Tool implementations (reuse deps.py pattern)
# ---------------------------------------------------------------------------

_http: httpx.AsyncClient | None = None
BACKEND_URL = os.getenv("BACKEND_URL", "https://nuzantara-rag.fly.dev")
BACKEND_API_KEY = os.getenv("SCRAPER_API_KEY", "internal-scraper-key")
GEMINI_MODEL = os.getenv("NAGA_GEMINI_MODEL", "gemini-3.1-pro-preview")


async def _get_http() -> httpx.AsyncClient:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(timeout=90.0)
    return _http


async def ask_legal(**kwargs: Any) -> dict:
    query = kwargs.get("query", "")
    client = await _get_http()
    try:
        resp = await client.post(
            f"{BACKEND_URL}/api/agentic-rag/query",
            json={"query": query, "language": "en"},
            headers={"X-API-Key": BACKEND_API_KEY},
            timeout=90.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "answer": data.get("answer", data.get("response", "")),
                "sources": data.get("sources", []),
                "confidence": data.get("confidence", 0.7),
            }
    except Exception as e:
        logger.debug("ask_legal failed: %s", e)
    return {"answer": "", "sources": [], "confidence": 0.0}


async def search_intel(**kwargs: Any) -> dict:
    query = kwargs.get("query", "")
    client = await _get_http()
    try:
        resp = await client.get(
            f"{BACKEND_URL}/api/intel/search",
            params={"q": query, "limit": 5},
            headers={"X-API-Key": BACKEND_API_KEY},
            timeout=15.0,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.debug("search_intel failed: %s", e)
    return {"results": []}


async def exa_search(**kwargs: Any) -> dict:
    query = kwargs.get("query", "")
    num_results = kwargs.get("numResults", 5)
    include_domains = kwargs.get("includeDomains", [])

    client = await _get_http()
    search_query = query
    if include_domains:
        domain_filter = " OR ".join(f"site:{d}" for d in include_domains[:3])
        search_query = f"{query} ({domain_filter})"

    brave_key = os.getenv("BRAVE_API_KEY", "")
    if not brave_key:
        return {"results": []}

    try:
        resp = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": search_query, "count": min(num_results, 10)},
            headers={"Accept": "application/json", "X-Subscription-Token": brave_key},
            timeout=10.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            results = []
            for item in data.get("web", {}).get("results", [])[:num_results]:
                results.append({
                    "url": item.get("url", ""),
                    "title": item.get("title", ""),
                    "text": item.get("description", ""),
                    "score": 0.7,
                })
            return {"results": results}
    except Exception as e:
        logger.debug("exa_search failed: %s", e)
    return {"results": []}


async def brave_search(**kwargs: Any) -> dict:  # noqa: ARG001
    return {"web": {"results": []}}


async def fetch_url(**kwargs: Any) -> dict:
    url = kwargs.get("url", "")
    max_length = kwargs.get("max_length", 50000)
    client = await _get_http()
    try:
        resp = await client.get(url, follow_redirects=True, timeout=15.0)
        return {"content": resp.text[:max_length]}
    except Exception as e:
        logger.debug("fetch failed for %s: %s", url[:60], e)
        return {"content": ""}


async def gemini_generate(prompt: str = "", **kwargs: Any) -> dict:  # noqa: ARG001
    logger.debug("gemini_generate: %d chars", len(prompt))
    try:
        proc = await asyncio.create_subprocess_exec(
            "gemini", "-m", GEMINI_MODEL,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(
            proc.communicate(input=prompt.encode("utf-8")),
            timeout=120.0,
        )
        output = stdout.decode("utf-8", errors="replace")
        clean_lines = [
            line for line in output.split("\n")
            if not any(s in line for s in [
                "Scheduling MCP", "Executing MCP", "MCP context",
                "Policy file error", "Pattern:", "Suggestion:",
                "Loaded cached", "Registering notification",
                "Server '", "capabilities", "experimental",
                "GOOGLE_API_KEY", "GEMINI_API_KEY", "Both ",
            ])
        ]
        return {"text": "\n".join(clean_lines).strip()}
    except asyncio.TimeoutError:
        return {"text": "{}"}
    except Exception as e:
        logger.debug("gemini_generate failed: %s", e)
        return {"text": "{}"}


async def notebook_query(**kwargs: Any) -> dict:  # noqa: ARG001
    return {"status": "success", "answer": "", "sources_used": []}


async def recall_similar(**kwargs: Any) -> dict:  # noqa: ARG001
    return {"episodes": []}


# ---------------------------------------------------------------------------
# DB connection
# ---------------------------------------------------------------------------

async def get_db_pool() -> asyncpg.Pool | None:
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        # Try local tunnel default
        db_url = "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag"
        logger.info("DATABASE_URL not set, trying tunnel default: localhost:15432")

    try:
        pool = await asyncpg.create_pool(
            db_url,
            min_size=1,
            max_size=3,
            command_timeout=30.0,
        )
        # Verify connection
        async with pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM naga_sessions")
            logger.info("DB connected. Existing naga_sessions: %d", count)
        return pool
    except Exception as e:
        logger.error("DB connection failed: %s", e)
        logger.error("Run: ssh -L 15432:localhost:5432 air  (or use dev-local alias)")
        return None


# ---------------------------------------------------------------------------
# Progress tracking
# ---------------------------------------------------------------------------

def load_progress(progress_file: Path) -> dict:
    if progress_file.exists():
        return json.loads(progress_file.read_text())
    return {"completed": [], "failed": [], "total_claims": 0, "started_at": datetime.utcnow().isoformat()}


def save_progress(progress_file: Path, progress: dict) -> None:
    progress_file.write_text(json.dumps(progress, indent=2))


# ---------------------------------------------------------------------------
# Main enrichment loop
# ---------------------------------------------------------------------------

async def run_enrichment(
    tier: str = "flash",
    categories: list[str] | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    delay_seconds: float = 2.0,
) -> None:
    """Run bulk enrichment queries against Naga orchestrator."""
    from backend.services.naga.orchestrator import NagaOrchestrator

    # 1. Build query list
    if categories:
        queries = []
        for cat in categories:
            if cat in QUERY_CORPUS:
                queries.extend([(cat, q) for q in QUERY_CORPUS[cat]])
            else:
                logger.warning("Unknown category: %s", cat)
    else:
        queries = [(cat, q) for cat, qs in QUERY_CORPUS.items() for q in qs]

    if limit:
        queries = queries[:limit]

    total = len(queries)
    logger.info(
        "Bulk enrichment: %d queries, tier=%s, dry_run=%s",
        total, tier, dry_run,
    )

    if dry_run:
        for i, (cat, q) in enumerate(queries, 1):
            print(f"  [{i:3d}/{total}] [{cat}] {q}")
        return

    # 2. Connect to DB
    db_pool = await get_db_pool()
    if db_pool is None:
        logger.error("Cannot proceed without DB connection")
        sys.exit(1)

    # 3. Load progress (resume from checkpoint)
    progress_file = Path(__file__).parent / ".naga_bulk_progress.json"
    progress = load_progress(progress_file)
    completed_queries = set(progress["completed"])
    logger.info(
        "Progress loaded: %d already completed, %d failed previously",
        len(completed_queries),
        len(progress["failed"]),
    )

    # 4. Build deps
    deps = SimpleNamespace(
        exa_search=exa_search,
        brave_search=brave_search,
        fetch=fetch_url,
        ask_legal=ask_legal,
        search_intel=search_intel,
        notebook_query=notebook_query,
        recall_similar=recall_similar,
        gemini_generate=gemini_generate,
        db_pool=db_pool,
    )

    orch = NagaOrchestrator(deps=deps)

    # 5. Run queries
    session_claims = 0
    session_errors = 0
    session_skipped = 0

    for i, (category, query) in enumerate(queries, 1):
        query_key = f"{category}::{query}"

        if query_key in completed_queries:
            session_skipped += 1
            continue

        logger.info(
            "[%d/%d] [%s] %s",
            i, total, category, query[:80],
        )

        start = time.monotonic()
        try:
            result = await orch.research(
                query=query,
                tier=tier,
                domain="indonesia" if category in ("visa", "company", "property", "tax", "kbli", "bali_specific") else "general",
                mode="oneshot",
                channel="bulk_enrich",
            )

            elapsed = time.monotonic() - start
            claims = result.get("claims_extracted", 0)
            sources = len(result.get("search_results", []))
            status = result.get("status", "?")
            conf = result.get("avg_confidence", 0.0)

            session_claims += claims
            progress["total_claims"] = progress.get("total_claims", 0) + claims
            progress["completed"].append(query_key)
            completed_queries.add(query_key)

            logger.info(
                "  → %s | claims=%d sources=%d conf=%.2f elapsed=%.1fs",
                status, claims, sources, conf, elapsed,
            )

        except Exception as e:
            elapsed = time.monotonic() - start
            session_errors += 1
            progress["failed"].append({"query": query_key, "error": str(e)})
            logger.error("  → FAILED after %.1fs: %s", elapsed, e)

        finally:
            # Save progress after every query
            save_progress(progress_file, progress)

        # Rate limit between queries
        if i < total and delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

    # 6. Final summary
    await db_pool.close()
    if _http:
        await _http.aclose()

    done = len(progress["completed"])
    failed = len(progress["failed"])
    total_claims = progress.get("total_claims", 0)

    print(f"\n{'='*70}")
    print("  NAGA BULK ENRICHMENT COMPLETE")
    print(f"{'='*70}")
    print(f"  Queries completed:  {done} ({session_skipped} skipped, already done)")
    print(f"  Queries failed:     {failed} ({session_errors} this session)")
    print(f"  Claims this run:    {session_claims}")
    print(f"  Total claims in DB: {total_claims}")
    print(f"  Progress saved to:  {progress_file}")
    print(f"{'='*70}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Naga Bulk Enrichment — populate Claims DB")
    parser.add_argument(
        "--tier",
        default="flash",
        choices=["flash", "deep", "exhaustive"],
        help="Research tier (flash=fast, deep=slower but richer)",
    )
    parser.add_argument(
        "--category",
        action="append",
        dest="categories",
        help="Category to run (can repeat). Default: all categories",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max queries to run (useful for testing)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print queries without running",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Seconds between queries (default: 2.0)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset progress checkpoint and start fresh",
    )
    args = parser.parse_args()

    if args.reset:
        progress_file = Path(__file__).parent / ".naga_bulk_progress.json"
        if progress_file.exists():
            progress_file.unlink()
            print(f"Progress reset: {progress_file}")

    asyncio.run(run_enrichment(
        tier=args.tier,
        categories=args.categories,
        limit=args.limit,
        dry_run=args.dry_run,
        delay_seconds=args.delay,
    ))


if __name__ == "__main__":
    main()
