#!/usr/bin/env python3
"""
Gemini AI Studio Response Parser

Parses batch responses from Gemini AI Studio (CSV export) and converts
to structured conversation variations for Phase 2.

Author: Nuzantara Team
Date: 2026-02-09
Reference: docs/caching/WORKFLOW_GUIDE.md (Phase 2)
"""

import csv
import json
import re
from pathlib import Path
from typing import Dict, List

import click


@click.group()
def cli():
    """Gemini AI Studio Response Parser."""
    pass


@cli.command()
@click.argument("csv_file", type=click.Path(exists=True))
@click.option("--output-dir", default="data/variations", help="Output directory for parsed variations")
@click.option("--seed-id", required=True, help="Golden seed ID this batch came from")
def parse_csv(csv_file: str, output_dir: str, seed_id: str):
    """
    Parse Gemini AI Studio CSV export into structured variations.

    CSV_FILE: Exported CSV from Gemini AI Studio batch prompts
    SEED_ID: Golden seed ID (e.g., seed_001_pt_pma_setup)

    Expected CSV format:
    - Column 1: Prompt text (ignored)
    - Column 2: Response text (extracted)
    - No header row
    """
    csv_path = Path(csv_file)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    variations = []
    skipped = 0

    click.echo(f"📄 Parsing {csv_path.name}...")

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)

        for i, row in enumerate(reader, 1):
            if len(row) < 2:
                click.echo(f"⚠️ Row {i}: Incomplete ({len(row)} columns), skipping")
                skipped += 1
                continue

            prompt_text = row[0]
            response_text = row[1]

            # Extract Q&A from response
            parsed = _extract_qa_structure(response_text)

            if not parsed["query"]:
                click.echo(f"⚠️ Row {i}: No query found, skipping")
                skipped += 1
                continue

            variation = {
                "variation_id": f"{seed_id}_var_{i:03d}",
                "seed_id": seed_id,
                "query": parsed["query"],
                "response": parsed["response"],
                "citations_count": parsed["citations_count"],
                "quality_score": 0,  # To be filled by Phase 3
                "verified": False,
                "status": "pending_verification",
                "raw_gemini_output": response_text[:500],  # First 500 chars for debugging
            }

            variations.append(variation)

    output_file = output_path / f"{seed_id}_variations.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "metadata": {
                "seed_id": seed_id,
                "source_file": csv_path.name,
                "total_variations": len(variations),
                "skipped_rows": skipped,
                "created_at": "2026-02-09"
            },
            "variations": variations
        }, f, indent=2)

    click.echo(f"\n✅ Parsed {len(variations)} variations from {csv_path.name}")
    click.echo(f"⚠️ Skipped {skipped} rows (incomplete/invalid)")
    click.echo(f"📁 Output: {output_file}")


def _extract_qa_structure(response_text: str) -> Dict:
    """
    Extract query and response from Gemini AI Studio output.

    Expected format:
    ## Query
    [question text]

    ## Response
    [answer text with citations]

    Returns:
        dict with query, response, citations_count
    """
    query_match = re.search(r"##\s*Query\s*\n(.+?)(?=\n##|\Z)", response_text, re.DOTALL | re.IGNORECASE)
    response_match = re.search(r"##\s*Response\s*\n(.+)", response_text, re.DOTALL | re.IGNORECASE)

    query = query_match.group(1).strip() if query_match else ""
    response = response_match.group(1).strip() if response_match else response_text

    # Count citations: [Source: ...]
    citations_count = len(re.findall(r"\[Source:\s*[^\]]+\]", response))

    return {
        "query": query,
        "response": response,
        "citations_count": citations_count
    }


@cli.command()
@click.argument("variations_dir", type=click.Path(exists=True))
@click.option("--output", default="data/all_variations.json", help="Consolidated output file")
def consolidate(variations_dir: str, output: str):
    """
    Consolidate all variation files into single dataset.

    VARIATIONS_DIR: Directory containing *_variations.json files
    """
    var_path = Path(variations_dir)
    var_files = list(var_path.glob("*_variations.json"))

    if not var_files:
        click.echo(f"❌ No *_variations.json files found in {variations_dir}")
        return

    click.echo(f"📦 Consolidating {len(var_files)} variation files...")

    all_variations = []
    total_citations = 0

    for var_file in var_files:
        with open(var_file, "r") as f:
            data = json.load(f)

        variations = data.get("variations", [])
        all_variations.extend(variations)

        for var in variations:
            total_citations += var.get("citations_count", 0)

        click.echo(f"   ✅ {var_file.name}: {len(variations)} variations")

    consolidated = {
        "metadata": {
            "total_variations": len(all_variations),
            "total_seeds": len(var_files),
            "total_citations": total_citations,
            "average_citations": total_citations / len(all_variations) if all_variations else 0,
            "created_at": "2026-02-09",
            "status": "pending_verification"
        },
        "variations": all_variations
    }

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(consolidated, f, indent=2)

    click.echo(f"\n✅ Consolidated {len(all_variations)} variations")
    click.echo(f"📊 Average citations: {consolidated['metadata']['average_citations']:.1f}")
    click.echo(f"📁 Output: {output_path}")


@cli.command()
@click.argument("variations_file", type=click.Path(exists=True))
def stats(variations_file: str):
    """
    Show statistics for variation dataset.

    VARIATIONS_FILE: JSON file with variations
    """
    with open(variations_file, "r") as f:
        data = json.load(f)

    variations = data.get("variations", [])

    if not variations:
        click.echo("❌ No variations found in file")
        return

    click.echo(f"\n📊 Statistics for {Path(variations_file).name}")
    click.echo("="*70)

    # Citation distribution
    citation_counts = [v.get("citations_count", 0) for v in variations]
    avg_citations = sum(citation_counts) / len(citation_counts)

    click.echo(f"\n📚 Citations:")
    click.echo(f"   Total: {sum(citation_counts):,}")
    click.echo(f"   Average: {avg_citations:.1f}")
    click.echo(f"   Min: {min(citation_counts)}")
    click.echo(f"   Max: {max(citation_counts)}")

    # Query length distribution
    query_lengths = [len(v.get("query", "").split()) for v in variations]
    avg_query_length = sum(query_lengths) / len(query_lengths)

    click.echo(f"\n❓ Query Length (words):")
    click.echo(f"   Average: {avg_query_length:.1f}")
    click.echo(f"   Min: {min(query_lengths)}")
    click.echo(f"   Max: {max(query_lengths)}")

    # Response length distribution
    response_lengths = [len(v.get("response", "").split()) for v in variations]
    avg_response_length = sum(response_lengths) / len(response_lengths)

    click.echo(f"\n💬 Response Length (words):")
    click.echo(f"   Average: {avg_response_length:.1f}")
    click.echo(f"   Min: {min(response_lengths)}")
    click.echo(f"   Max: {max(response_lengths)}")

    # Verification status
    verified_count = sum(1 for v in variations if v.get("verified", False))
    pending_count = len(variations) - verified_count

    click.echo(f"\n✅ Verification Status:")
    click.echo(f"   Verified: {verified_count} ({verified_count/len(variations)*100:.1f}%)")
    click.echo(f"   Pending: {pending_count} ({pending_count/len(variations)*100:.1f}%)")

    click.echo(f"\n📈 Total Variations: {len(variations)}")
    click.echo("="*70)


if __name__ == "__main__":
    cli()
