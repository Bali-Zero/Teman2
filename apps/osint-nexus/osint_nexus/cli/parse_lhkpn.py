"""CLI for parsing LHKPN PDFs and optionally loading into Neo4j.

Usage:
    # Dry-run: parse and print JSON, no Neo4j
    python -m osint_nexus.cli.parse_lhkpn --dry-run --file path/to/file.pdf

    # Dry-run all PDFs in default directory
    python -m osint_nexus.cli.parse_lhkpn --dry-run

    # Parse and load into Neo4j
    python -m osint_nexus.cli.parse_lhkpn --file path/to/file.pdf
"""
from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

import click

from osint_nexus.config import RAW_DIR
from osint_nexus.parsers.lhkpn_parser import parse_lhkpn_pdf
from osint_nexus.utils.logging import get_logger

logger = get_logger("cli.parse_lhkpn")

DEFAULT_PDF_DIR = RAW_DIR / "lhkpn" / "pdfs"


@click.command()
@click.option("--dry-run", is_flag=True, help="Parse only, print JSON — no Neo4j.")
@click.option("--file", "file_path", type=click.Path(exists=True), help="Single PDF to parse.")
def main(dry_run: bool, file_path: str | None) -> None:
    """Parse LHKPN PDF files and optionally load into Neo4j."""
    # Collect PDF files
    if file_path:
        pdfs = [Path(file_path)]
    else:
        if not DEFAULT_PDF_DIR.exists():
            click.echo(f"PDF directory not found: {DEFAULT_PDF_DIR}", err=True)
            sys.exit(1)
        pdfs = sorted(DEFAULT_PDF_DIR.glob("*.pdf"))
        if not pdfs:
            click.echo(f"No PDFs found in {DEFAULT_PDF_DIR}", err=True)
            sys.exit(1)

    click.echo(f"Found {len(pdfs)} PDF(s) to process.")

    reports = []
    for pdf in pdfs:
        click.echo(f"\nParsing: {pdf.name}")
        try:
            report = parse_lhkpn_pdf(pdf)
            reports.append(report)
            click.echo(
                f"  {report.nama} ({report.tahun}) — "
                f"{len(report.tanah_bangunan)} properties, "
                f"{len(report.kendaraan)} vehicles, "
                f"kas={report.kas:,}, total={report.total_harta:,}"
            )
        except Exception as e:
            click.echo(f"  ERROR: {e}", err=True)
            continue

    if dry_run:
        click.echo("\n--- Dry-run output (JSON) ---")
        for report in reports:
            data = asdict(report)
            click.echo(json.dumps(data, indent=2, ensure_ascii=False))
        click.echo(f"\nDry-run complete: {len(reports)} report(s) parsed.")
        return

    # Load into Neo4j — import only when needed
    from osint_nexus.graph.loader import GraphLoader
    from osint_nexus.graph.schema import init_schema

    async def _load() -> None:
        loader = GraphLoader()
        if not await loader.verify_connectivity():
            click.echo("Neo4j connection failed. Aborting.", err=True)
            sys.exit(1)

        await init_schema(loader._driver)
        click.echo("Schema initialized.")

        total_assets = 0
        for report in reports:
            count = await loader.load_lhkpn_report(report)
            total_assets += count
            click.echo(f"  Loaded {report.nama} ({report.tahun}): {count} assets")

        await loader.close()
        click.echo(f"\nDone: {len(reports)} report(s), {total_assets} total assets loaded.")

    asyncio.run(_load())


if __name__ == "__main__":
    main()
