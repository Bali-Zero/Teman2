"""Batch LHKPN scraper — scrape + parse + load for all Officials without LHKPN data.

Usage:
    cd apps/osint-nexus
    PYTHONPATH=. python scripts/batch_lhkpn_scrape.py [--dry-run]
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from neo4j import AsyncGraphDatabase

from osint_nexus.config import NEO4J_DATABASE, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from osint_nexus.graph.loader import GraphLoader
from osint_nexus.graph.schema import init_schema
from osint_nexus.parsers.lhkpn_parser import parse_lhkpn_pdf
from osint_nexus.scrapers.lhkpn import LHKPNScraper
from osint_nexus.utils.logging import get_logger

logger = get_logger("batch_lhkpn")

# Names that won't return useful results on elhkpn.kpk.go.id
SKIP_NAMES = {
    # Deceased / historical
    "Abdurrahman Wahid", "B. J. Habibie", "Soeharto", "Suharto",
    "Soemitro Djojohadikoesoemo", "Margono Djojohadikoesoemo",
    # Generic / partial names
    "Agus", "Ganjar", "Mahfud", "Muhaimin", "Anies", "Yusril",
    "Menko Yusril", "Sekjen",
    # Roles not persons
    "Staf Ahli", "Staf Ahli Menteri Bidang Pelayanan Publik",
    "Staf Ahli Menteri Bidang Reformasi Hukum", "Kemenko Kumham Imipas",
    # Non-officials
    "Japanese national", "mother", "Anak Yusril",
    "Anissa Zulaikha Mahendra", "Ishmael Zacharias Mahendra",
    "Kessy Sukaesih", "Rika Tolentino Kato",
    # Duplicates (search under canonical name)
    "Prabowo Subianto Djojohadikusumo",  # use "Prabowo Subianto"
    "Mahfud MD",  # use "Mohammad Mahfud Mahmodin"
    "Gatot Eddy Pramono",  # police, unlikely in LHKPN by this name
    "Teddy Indra Wijaya",  # Cabinet Secretary, unlikely
    "RAJA ULUL AZMI SYAHWAL",  # already scraped under Syahwali
}

PDF_DIR = Path("data/raw/lhkpn/pdfs")


async def get_targets() -> list[str]:
    """Get Officials without LHKPN assets from Neo4j."""
    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    names = []
    async with driver.session(database=NEO4J_DATABASE) as s:
        r = await s.run("""
            MATCH (o:Official)
            WHERE NOT (o)-[:OWNS]->()
            AND size(split(o.name, " ")) >= 2
            RETURN o.name ORDER BY o.name
        """)
        async for rec in r:
            name = rec[0]
            if name not in SKIP_NAMES:
                names.append(name)
    await driver.close()
    return names


async def scrape_and_load(name: str, dry_run: bool = False) -> int:
    """Scrape LHKPN for a name, parse PDFs, load into Neo4j."""
    logger.info("Scraping LHKPN for: %s", name)

    scraper = LHKPNScraper()
    try:
        results = await scraper.scrape(name, download_pdf=True, pdf_dir=str(PDF_DIR))
    except Exception as e:
        logger.error("Scraper failed for %s: %s", name, e)
        return 0

    if not results:
        logger.warning("No LHKPN results for: %s", name)
        return 0

    logger.info("Found %d LHKPN records for %s", len(results), name)

    # Find downloaded PDFs matching this name
    safe_name = name.upper().replace(" ", "_")
    pdfs = sorted(PDF_DIR.glob(f"LHKPN_{safe_name}_*.pdf"))
    # Also try partial match
    if not pdfs:
        pdfs = sorted(PDF_DIR.glob(f"LHKPN_*{safe_name.split('_')[0]}*.pdf"))

    if not pdfs:
        logger.warning("No PDFs found for %s after scraping", name)
        return 0

    if dry_run:
        for pdf in pdfs:
            report = parse_lhkpn_pdf(pdf)
            print(f"  [DRY] {report.nama} ({report.tahun}): "
                  f"{len(report.tanah_bangunan)} props, {len(report.kendaraan)} vehicles, "
                  f"total=Rp {report.total_harta:,}")
        return len(pdfs)

    # Load into Neo4j
    loader = GraphLoader()
    await loader.verify_connectivity()
    await init_schema(loader._driver)

    total = 0
    for pdf in pdfs:
        try:
            report = parse_lhkpn_pdf(pdf)
            count = await loader.load_lhkpn_report(report)
            total += count
            logger.info("Loaded %s (%d): %d assets", report.nama, report.tahun, count)
        except Exception as e:
            logger.error("Failed to parse/load %s: %s", pdf.name, e)

    await loader.close()
    return total


async def main() -> None:
    dry_run = "--dry-run" in sys.argv

    targets = await get_targets()
    print(f"{'[DRY RUN] ' if dry_run else ''}Targets: {len(targets)} officials")
    for t in targets:
        print(f"  {t}")

    if not targets:
        print("No targets to scrape.")
        return

    total_assets = 0
    scraped = 0
    failed = 0

    for i, name in enumerate(targets, 1):
        print(f"\n[{i}/{len(targets)}] {name}")
        try:
            count = await scrape_and_load(name, dry_run=dry_run)
            if count > 0:
                scraped += 1
                total_assets += count
            else:
                failed += 1
        except Exception as e:
            logger.error("Fatal error for %s: %s", name, e)
            failed += 1

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Done: "
          f"{scraped} scraped, {failed} no results, {total_assets} total assets")


if __name__ == "__main__":
    asyncio.run(main())
