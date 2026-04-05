#!/usr/bin/env python3
"""Naga Bali Bureaucracy Session — 100 curated queries on local Bali admin/regulatory topics.

Usage:
    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. python scripts/naga_bali_enrich.py
    PYTHONPATH=. python scripts/naga_bali_enrich.py --dry-run
    PYTHONPATH=. python scripts/naga_bali_enrich.py --limit 10
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("naga.bali_enrich")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# 100 Bali bureaucracy queries
# ---------------------------------------------------------------------------

BALI_QUERIES: list[tuple[str, str]] = [
    # --- Permits & Licenses ---
    ("permits", "IMB izin mendirikan bangunan Bali requirements 2025"),
    ("permits", "PBG persetujuan bangunan gedung Bali replace IMB"),
    ("permits", "SLF sertifikat laik fungsi bangunan Bali"),
    ("permits", "villa construction permit Bali residential zone"),
    ("permits", "Bali commercial building permit requirements"),
    ("permits", "SIUP surat izin usaha perdagangan Bali"),
    ("permits", "izin usaha pariwisata Bali villa homestay"),
    ("permits", "TDUP tanda daftar usaha pariwisata Bali"),
    ("permits", "Bali restaurant cafe operating license"),
    ("permits", "izin ganguan HO Bali neighborhood disturbance permit"),
    ("permits", "SIPA surat izin pengambilan air Bali water permit"),
    ("permits", "Bali swimming pool construction permit requirements"),
    ("permits", "izin reklame billboard signage Bali permit"),
    ("permits", "Bali event organizer permit requirements"),
    ("permits", "wedding venue license requirements Bali"),

    # --- Zoning & Land Use ---
    ("zoning", "Bali tata ruang spatial planning zones 2025"),
    ("zoning", "RTRW Bali regional spatial plan regulations"),
    ("zoning", "Bali green zone hijau agricultural land restrictions"),
    ("zoning", "Bali tourism zone pariwisata building rules"),
    ("zoning", "Bali residential zone perumahan permitted uses"),
    ("zoning", "Bali coastal setback rules sempadan pantai"),
    ("zoning", "Bali river setback sempadan sungai regulations"),
    ("zoning", "Bali height restriction bangunan tinggi"),
    ("zoning", "Bali heritage zone kawasan warisan budaya"),
    ("zoning", "Bali mangrove protected zone restrictions"),
    ("zoning", "FAR floor area ratio KDB KLB Bali"),
    ("zoning", "Bali adat village tanah desa rights restrictions"),
    ("zoning", "Bali airport noise zone IMB restrictions Ngurah Rai"),
    ("zoning", "Bali Seminyak Canggu villa development rules"),
    ("zoning", "Bali Ubud cultural zone building restrictions"),

    # --- Property & Land Registration ---
    ("land", "sertifikat hak milik SHM process Bali BPN"),
    ("land", "SHGB sertifikat hak guna bangunan conversion Bali"),
    ("land", "BPN Bali land registration office process"),
    ("land", "tanah girik letter C conversion to certificate Bali"),
    ("land", "PPAT notaris pejabat pembuat akta tanah Bali"),
    ("land", "land splitting pemecahan sertifikat Bali"),
    ("land", "land consolidation penggabungan tanah Bali"),
    ("land", "PBB pajak bumi bangunan property tax Bali"),
    ("land", "BPHTB bea perolehan hak tanah bangunan Bali"),
    ("land", "Bali land auction lelang tanah process"),
    ("land", "tanah adat communal land Bali desa pakraman"),
    ("land", "Bali land dispute resolution process"),
    ("land", "letter C girik verification process Bali"),
    ("land", "Bali land measurement survey kadaster"),
    ("land", "Bali property inheritance process foreigners"),

    # --- Local Tax & Retribusi ---
    ("tax_local", "pajak hotel Bali provincial hotel tax rate"),
    ("tax_local", "pajak restoran Bali restaurant tax 10%"),
    ("tax_local", "retribusi daerah Bali local fees types"),
    ("tax_local", "BPHTB calculation Bali property transfer"),
    ("tax_local", "Bali tourist levy tourism retribution 2025"),
    ("tax_local", "pajak hiburan Bali entertainment tax"),
    ("tax_local", "pajak reklame Bali advertisement tax"),
    ("tax_local", "retribusi parkir Bali parking fee"),
    ("tax_local", "Bali provincial tax office Bapenda address"),
    ("tax_local", "pajak air tanah Bali groundwater extraction tax"),

    # --- Utilities & Infrastructure ---
    ("utilities", "PLN electricity connection new building Bali"),
    ("utilities", "PLN Bali electricity tariff rates 2025"),
    ("utilities", "PDAM Bali water connection requirements"),
    ("utilities", "Bali water supply shortage tanah air bor"),
    ("utilities", "Bali septic tank IPAL wastewater regulations"),
    ("utilities", "Bali internet fiber optic providers"),
    ("utilities", "LPG gas connection Bali commercial kitchen"),
    ("utilities", "Bali solar panel installation permit"),
    ("utilities", "Bali garbage waste management retribusi sampah"),
    ("utilities", "Bali sewage connection requirements villa"),

    # --- Business Operations Bali ---
    ("business_ops", "Bali villa rental short term airbnb regulations"),
    ("business_ops", "OTA online travel agent regulations Bali villa"),
    ("business_ops", "Bali surf school instructor license requirements"),
    ("business_ops", "Bali diving operator license requirements PADI"),
    ("business_ops", "Bali spa wellness center license requirements"),
    ("business_ops", "Bali food hygiene certificate PIRT requirements"),
    ("business_ops", "Bali alcohol license permit requirements"),
    ("business_ops", "Bali co-working space permit requirements"),
    ("business_ops", "Bali gym fitness center license requirements"),
    ("business_ops", "Bali tour guide license requirements Bali"),
    ("business_ops", "Bali money changer license requirements"),
    ("business_ops", "Bali retail shop toko permit requirements"),
    ("business_ops", "Bali driver ojek gojek regulations"),
    ("business_ops", "Bali construction contractor license SIUJK"),
    ("business_ops", "Bali healthcare clinic izin klinik requirements"),

    # --- Environment & Sustainability ---
    ("environment", "AMDAL environmental impact assessment Bali"),
    ("environment", "UKL UPL Bali environmental management plan"),
    ("environment", "Bali plastic bag ban regulation enforcement"),
    ("environment", "Bali single use plastic regulation 2025"),
    ("environment", "Bali mangrove conservation regulations"),
    ("environment", "Bali coral reef protection regulations"),
    ("environment", "Bali rice field subak UNESCO protection rules"),
    ("environment", "Bali noise pollution regulations nightlife"),
    ("environment", "Bali construction waste disposal regulations"),
    ("environment", "Bali green building certification requirements"),

    # --- Local Government & Admin ---
    ("government", "Bali banjar community organization role"),
    ("government", "Bali desa adat customary village rules foreigners"),
    ("government", "Bali subak irrigation system rights"),
    ("government", "kelurahan desa office Bali resident registration"),
    ("government", "surat keterangan domisili Bali address certificate"),
    ("government", "Bali local government DPRD regulations business"),
    ("government", "Bali governor regulation pergub requirements"),
    ("government", "Bali regency kabupaten permit vs provincial"),
    ("government", "Denpasar city mayor regulation business"),
    ("government", "Badung regency Bali investment requirements"),
]

# ---------------------------------------------------------------------------
# Tools (same as bulk_enrich)
# ---------------------------------------------------------------------------

BACKEND_URL = os.getenv("BACKEND_URL", "https://nuzantara-rag.fly.dev")
BACKEND_API_KEY = os.getenv("SCRAPER_API_KEY", "internal-scraper-key")
_http: httpx.AsyncClient | None = None


async def _get_http() -> httpx.AsyncClient:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(timeout=90.0)
    return _http


async def ask_legal(**kw: Any) -> dict:
    client = await _get_http()
    try:
        r = await client.post(
            f"{BACKEND_URL}/api/agentic-rag/query",
            json={"query": kw.get("query", ""), "language": "en"},
            headers={"X-API-Key": BACKEND_API_KEY},
            timeout=90.0,
        )
        if r.status_code == 200:
            d = r.json()
            return {"answer": d.get("answer", d.get("response", "")),
                    "sources": d.get("sources", []),
                    "confidence": d.get("confidence", 0.7)}
    except Exception as e:
        logger.debug("ask_legal: %s", e)
    return {"answer": "", "sources": [], "confidence": 0.0}


async def search_intel(**kw: Any) -> dict:
    client = await _get_http()
    try:
        r = await client.get(
            f"{BACKEND_URL}/api/intel/search",
            params={"q": kw.get("query", ""), "limit": 5},
            headers={"X-API-Key": BACKEND_API_KEY},
            timeout=15.0,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.debug("search_intel: %s", e)
    return {"results": []}


async def exa_search(**kw: Any) -> dict:
    brave_key = os.getenv("BRAVE_API_KEY", "")
    if not brave_key:
        return {"results": []}
    client = await _get_http()
    try:
        r = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": kw.get("query", ""), "count": min(kw.get("numResults", 5), 10)},
            headers={"Accept": "application/json", "X-Subscription-Token": brave_key},
            timeout=10.0,
        )
        if r.status_code == 200:
            return {"results": [
                {"url": i.get("url",""), "title": i.get("title",""),
                 "text": i.get("description",""), "score": 0.7}
                for i in r.json().get("web",{}).get("results",[])[:kw.get("numResults",5)]
            ]}
    except Exception as e:
        logger.debug("exa_search: %s", e)
    return {"results": []}


async def brave_search(**kw: Any) -> dict:  # noqa: ARG001
    return {"web": {"results": []}}


async def fetch_url(**kw: Any) -> dict:
    client = await _get_http()
    try:
        r = await client.get(kw.get("url", ""), follow_redirects=True, timeout=15.0)
        return {"content": r.text[:50000]}
    except Exception as e:
        logger.debug("fetch: %s", e)
        return {"content": ""}


async def gemini_generate(prompt: str = "", **kw: Any) -> dict:  # noqa: ARG001
    return {"text": "{}"}


async def notebook_query(**kw: Any) -> dict:  # noqa: ARG001
    return {"status": "success", "answer": "", "sources_used": []}


async def recall_similar(**kw: Any) -> dict:  # noqa: ARG001
    return {"episodes": []}


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------

PROGRESS_FILE = Path(__file__).parent / ".naga_bali_progress.json"


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {"completed": [], "failed": [], "total_claims": 0,
            "started_at": datetime.utcnow().isoformat()}


def save_progress(p: dict) -> None:
    PROGRESS_FILE.write_text(json.dumps(p, indent=2))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run(limit: int | None, dry_run: bool, delay: float) -> None:
    from backend.services.naga.orchestrator import NagaOrchestrator

    queries = BALI_QUERIES[:limit] if limit else BALI_QUERIES
    total = len(queries)

    if dry_run:
        print(f"\n  {total} Bali queries planned:\n")
        for i, (cat, q) in enumerate(queries, 1):
            print(f"  [{i:3d}/{total}] [{cat}] {q}")
        return

    db_url = os.getenv("DATABASE_URL",
        "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag")
    try:
        pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3)
        async with pool.acquire() as conn:
            existing = await conn.fetchval("SELECT COUNT(*) FROM naga_sessions")
            logger.info("DB connected. Existing sessions: %d", existing)
    except Exception as e:
        logger.error("DB connection failed: %s", e)
        sys.exit(1)

    progress = load_progress()
    completed_set = set(progress["completed"])
    logger.info("Progress: %d already done, %d failed", len(completed_set), len(progress["failed"]))

    deps = SimpleNamespace(
        exa_search=exa_search, brave_search=brave_search, fetch=fetch_url,
        ask_legal=ask_legal, search_intel=search_intel,
        notebook_query=notebook_query, recall_similar=recall_similar,
        gemini_generate=gemini_generate, db_pool=pool,
    )
    orch = NagaOrchestrator(deps=deps)

    session_claims = 0
    session_errors = 0
    session_skipped = 0

    for i, (category, query) in enumerate(queries, 1):
        key = f"{category}::{query}"
        if key in completed_set:
            session_skipped += 1
            continue

        logger.info("[%d/%d] [%s] %s", i, total, category, query[:80])
        start = time.monotonic()

        try:
            result = await orch.research(
                query=query,
                tier="flash",
                domain="indonesia",
                mode="oneshot",
                channel="bali_enrich",
            )
            elapsed = time.monotonic() - start
            claims = result.get("claims_extracted", 0)
            sources = len(result.get("search_results", []))
            conf = result.get("avg_confidence", 0.0)
            session_claims += claims
            progress["total_claims"] = progress.get("total_claims", 0) + claims
            progress["completed"].append(key)
            completed_set.add(key)
            logger.info("  → %s | claims=%d sources=%d conf=%.2f %.1fs",
                        result.get("status"), claims, sources, conf, elapsed)

        except Exception as e:
            elapsed = time.monotonic() - start
            session_errors += 1
            progress["failed"].append({"query": key, "error": str(e)})
            logger.error("  → FAILED %.1fs: %s", elapsed, e)

        save_progress(progress)

        if i < total and delay > 0:
            await asyncio.sleep(delay)

    await pool.close()
    if _http:
        await _http.aclose()

    print(f"\n{'='*65}")
    print("  BALI ENRICHMENT COMPLETE")
    print(f"{'='*65}")
    print(f"  Queries completed:  {len(progress['completed'])} ({session_skipped} skipped)")
    print(f"  Queries failed:     {len(progress['failed'])} ({session_errors} this session)")
    print(f"  Claims this run:    {session_claims}")
    print(f"  Total Bali claims:  {progress.get('total_claims', 0)}")
    print(f"{'='*65}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Naga Bali Bureaucracy — 100 query session")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    if args.reset and PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()
        print("Progress reset.")

    asyncio.run(run(limit=args.limit, dry_run=args.dry_run, delay=args.delay))


if __name__ == "__main__":
    main()
