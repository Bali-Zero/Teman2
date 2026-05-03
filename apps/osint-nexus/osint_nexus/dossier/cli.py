"""CLI entry point — dossier generation and scraper commands."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from osint_nexus.config import DOSSIER_DIR, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER

console = Console()


def _run(coro):
    """Run async coroutine from sync CLI."""
    return asyncio.run(coro)


@click.group()
def main():
    """OSINT Nexus — Graph-based Intelligence System."""
    pass


# ── Dossier Commands ──


@main.command()
@click.argument("target")
@click.option("--output", "-o", default=None, help="Output file path")
@click.option("--format", "fmt", type=click.Choice(["md", "json", "both"]), default="both")
def dossier(target: str, output: str | None, fmt: str):
    """Generate a target dossier.

    Example: nexus dossier "Raja Ulul Azmi Syahwali"
    """
    _run(_dossier_async(target, output, fmt))


async def _dossier_async(target: str, output: str | None, fmt: str):
    from neo4j import AsyncGraphDatabase

    from osint_nexus.dossier.generator import DossierGenerator
    from osint_nexus.graph.queries import TacticalQueries

    console.print(f"[bold cyan]Generating dossier for:[/] {target}")

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        queries = TacticalQueries(driver)
        gen = DossierGenerator(queries)
        markdown, structured = await gen.generate(target)

        # Determine output paths
        DOSSIER_DIR.mkdir(parents=True, exist_ok=True)
        slug = target.lower().replace(" ", "_")[:40]

        if fmt in ("md", "both"):
            md_path = Path(output) if output and output.endswith(".md") else DOSSIER_DIR / f"{slug}.md"
            md_path.write_text(markdown, encoding="utf-8")
            console.print(f"[green]✓[/] Markdown: {md_path}")

        if fmt in ("json", "both"):
            import orjson
            json_path = DOSSIER_DIR / f"{slug}.json"
            json_path.write_bytes(orjson.dumps(structured, option=orjson.OPT_INDENT_2))
            console.print(f"[green]✓[/] JSON: {json_path}")

        # Print summary
        console.print(f"\n[bold]Power Score:[/] {structured.get('power', {}).get('power_score', 'N/A')}")
        net = structured.get("network", {})
        console.print(f"[bold]Network:[/] {len(net.get('nodes', []))} nodes, {len(net.get('edges', []))} edges")
        console.print(f"[bold]Anomalies:[/] {len(structured.get('financial_anomalies', []))}")
    finally:
        await driver.close()


# ── Scraper Commands ──


@main.command()
@click.argument(
    "source",
    type=click.Choice(["lhkpn", "lpse", "ahu", "putusan", "news", "wiki", "opentender"]),
)
@click.argument("query")
@click.option("--max-pages", default=3, help="Max pages to scrape")
def scrape(source: str, query: str, max_pages: int):
    """Run a scraper.

    Example: nexus scrape news "kanim ngurah rai"
    """
    _run(_scrape_async(source, query, max_pages))


async def _scrape_async(source: str, query: str, max_pages: int):
    scraper_map = {
        "lhkpn": "osint_nexus.scrapers.lhkpn:LHKPNScraper",
        "lpse": "osint_nexus.scrapers.lpse:LPSEScraper",
        "ahu": "osint_nexus.scrapers.ahu:AHUScraper",
        "putusan": "osint_nexus.scrapers.putusan:PutusanMAScraper",
        "news": "osint_nexus.scrapers.news:NewsScraper",
        "wiki": "osint_nexus.scrapers.wiki:WikiScraper",
        "opentender": "osint_nexus.scrapers.opentender:OpenTenderScraper",
    }
    module_path, class_name = scraper_map[source].rsplit(":", 1)

    import importlib
    mod = importlib.import_module(module_path)
    scraper_cls = getattr(mod, class_name)
    scraper = scraper_cls()

    console.print(f"[bold cyan]Scraping {source}:[/] '{query}'")
    records = await scraper.scrape(query, max_pages=max_pages)
    console.print(f"[green]✓[/] {len(records)} records collected")

    if records:
        table = Table(title=f"{source.upper()} Results")
        table.add_column("Entity Type")
        table.add_column("Key Data", max_width=60)
        table.add_column("URL", max_width=40)

        for r in records[:10]:
            key = _summarize(r.raw_data)
            table.add_row(r.entity_type, key, r.url[:40])

        console.print(table)


def _summarize(data: dict) -> str:
    """One-line summary of record data."""
    parts = []
    for key in ["nama", "nama_paket", "judul", "instansi", "jabatan"]:
        if key in data and data[key]:
            parts.append(f"{key}={data[key][:30]}")
    return ", ".join(parts[:3]) or str(data)[:60]


# ── Graph Commands ──


@main.command()
@click.argument("from_name")
@click.argument("to_name")
@click.option("--hops", default=6, help="Max path hops")
def path(from_name: str, to_name: str, hops: int):
    """Find shortest path between two entities.

    Example: nexus path "PT Acme" "Raja Ulul Azmi Syahwali"
    """
    _run(_path_async(from_name, to_name, hops))


async def _path_async(from_name: str, to_name: str, hops: int):
    from neo4j import AsyncGraphDatabase

    from osint_nexus.graph.queries import TacticalQueries

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        queries = TacticalQueries(driver)
        paths = await queries.shortest_path(from_name, to_name, hops)

        if not paths:
            console.print("[yellow]No path found[/]")
            return

        for p in paths:
            nodes = p.get("nodes", [])
            rels = p.get("rels", [])
            chain = " → ".join(n.get("name", "?") for n in nodes)
            console.print(f"[green]Path ({p.get('hops', '?')} hops):[/] {chain}")
    finally:
        await driver.close()


@main.command()
@click.argument("name")
def score(name: str):
    """Show power score for an official.

    Example: nexus score "Raja Ulul Azmi Syahwali"
    """
    _run(_score_async(name))


async def _score_async(name: str):
    from neo4j import AsyncGraphDatabase

    from osint_nexus.graph.queries import TacticalQueries

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        queries = TacticalQueries(driver)
        result = await queries.power_score(name)

        if not result:
            console.print(f"[yellow]'{name}' not found in graph[/]")
            return

        table = Table(title=f"Power Score: {name}")
        table.add_column("Metric")
        table.add_column("Value", justify="right")

        for key in ["jabatan", "kantor", "degree", "positions", "social", "assets", "power_score"]:
            val = result.get(key, "N/A")
            table.add_row(key, str(val))

        console.print(table)
    finally:
        await driver.close()


@main.command()
def stats():
    """Show graph statistics."""
    _run(_stats_async())


async def _stats_async():
    from osint_nexus.graph.loader import GraphLoader

    loader = GraphLoader()
    try:
        connected = await loader.verify_connectivity()
        if not connected:
            console.print("[red]Cannot connect to Neo4j[/]")
            return

        counts = await loader.get_node_count()
        table = Table(title="Graph Statistics")
        table.add_column("Node Type")
        table.add_column("Count", justify="right")

        total = 0
        for label, count in counts.items():
            table.add_row(label, str(count))
            total += count

        table.add_row("[bold]TOTAL[/]", f"[bold]{total}[/]")
        console.print(table)
    finally:
        await loader.close()


@main.command()
def anomalies():
    """Detect financial anomalies in the graph."""
    _run(_anomalies_async())


async def _anomalies_async():
    from neo4j import AsyncGraphDatabase

    from osint_nexus.graph.queries import TacticalQueries

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        queries = TacticalQueries(driver)
        results = await queries.financial_anomaly()

        if not results:
            console.print("[green]No financial anomalies detected[/]")
            return

        table = Table(title="Financial Anomalies")
        table.add_column("Official")
        table.add_column("Asset")
        table.add_column("Value")
        table.add_column("Declared")
        table.add_column("Ratio", justify="right")

        for r in results:
            table.add_row(
                str(r.get("official", "")),
                str(r.get("asset", "")),
                str(r.get("asset_value", "")),
                str(r.get("declared", "")),
                f"{r.get('ratio', 0):.1f}x",
            )

        console.print(table)
    finally:
        await driver.close()


@main.command()
@click.argument("query")
@click.option("--sources", "-s", default="lhkpn,lpse,putusan", help="Comma-separated sources")
def pipeline(query: str, sources: str):
    """Run full pipeline: scrape → NER → resolve → graph.

    Example: nexus pipeline "Kantor Imigrasi Ngurah Rai" -s lhkpn,lpse
    """
    _run(_pipeline_async(query, sources))


async def _pipeline_async(query: str, sources: str):
    from osint_nexus.pipeline import run_full_pipeline

    source_list = [s.strip() for s in sources.split(",")]
    console.print(f"[bold cyan]Pipeline:[/] '{query}' → {source_list}")

    stats = await run_full_pipeline(source_list, query)

    table = Table(title="Pipeline Results")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    for k, v in stats.items():
        table.add_row(k.replace("_", " ").title(), str(v))
    console.print(table)


@main.command()
def init_db():
    """Initialize Neo4j schema (constraints + indexes)."""
    _run(_init_db_async())


async def _init_db_async():
    from neo4j import AsyncGraphDatabase

    from osint_nexus.graph.schema import init_schema

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        await init_schema(driver)
        console.print("[green]✓[/] Neo4j schema initialized")
    finally:
        await driver.close()


if __name__ == "__main__":
    main()
