#!/usr/bin/env python3
"""
ChatGPT Verification Analysis

Analyzes verification results from ChatGPT Plus (Phase 3) and generates
pass/fail reports for quality gates.

Author: Nuzantara Team
Date: 2026-02-09
Reference: docs/caching/WORKFLOW_GUIDE.md (Phase 3)
"""

import json
from collections import Counter
from pathlib import Path
from typing import Dict, List

import click


@click.group()
def cli():
    """ChatGPT Verification Analysis."""
    pass


@cli.command()
@click.argument("verified_file", type=click.Path(exists=True))
@click.option("--threshold", default=70, help="Minimum quality score for pass (default: 70)")
@click.option("--output", default="data/verification_report.json", help="Output report file")
def analyze(verified_file: str, threshold: int, output: str):
    """
    Analyze verification results and generate pass/fail report.

    VERIFIED_FILE: JSON file with verified variations from ChatGPT

    Expected structure:
    {
      "variations": [
        {
          "variation_id": "...",
          "verified": true,
          "quality_score": 85,
          "verification_notes": "..."
        }
      ]
    }
    """
    with open(verified_file, "r") as f:
        data = json.load(f)

    variations = data.get("variations", [])

    if not variations:
        click.echo("❌ No variations found in file")
        return

    click.echo(f"\n📊 Analyzing {len(variations)} verified variations...")
    click.echo("="*70)

    # Calculate statistics
    scores = [v.get("quality_score", 0) for v in variations if v.get("verified", False)]
    passed = [v for v in variations if v.get("quality_score", 0) >= threshold]
    failed = [v for v in variations if v.get("quality_score", 0) < threshold]

    avg_score = sum(scores) / len(scores) if scores else 0
    pass_rate = len(passed) / len(variations) * 100 if variations else 0

    click.echo(f"\n✅ Pass/Fail Summary:")
    click.echo(f"   Passed (≥{threshold}): {len(passed)} ({pass_rate:.1f}%)")
    click.echo(f"   Failed (<{threshold}): {len(failed)} ({100-pass_rate:.1f}%)")
    click.echo(f"   Average Score: {avg_score:.1f}")

    # Score distribution
    score_buckets = {
        "90-100 (Excellent)": 0,
        "80-89 (Good)": 0,
        "70-79 (Acceptable)": 0,
        "60-69 (Needs Work)": 0,
        "0-59 (Poor)": 0
    }

    for score in scores:
        if score >= 90:
            score_buckets["90-100 (Excellent)"] += 1
        elif score >= 80:
            score_buckets["80-89 (Good)"] += 1
        elif score >= 70:
            score_buckets["70-79 (Acceptable)"] += 1
        elif score >= 60:
            score_buckets["60-69 (Needs Work)"] += 1
        else:
            score_buckets["0-59 (Poor)"] += 1

    click.echo(f"\n📈 Score Distribution:")
    for bucket, count in score_buckets.items():
        pct = count / len(scores) * 100 if scores else 0
        click.echo(f"   {bucket}: {count} ({pct:.1f}%)")

    # Common issues analysis
    all_notes = []
    for v in variations:
        notes = v.get("verification_notes", "")
        if notes:
            all_notes.extend(notes.split(". "))

    issue_keywords = {
        "citation": 0,
        "hallucination": 0,
        "incomplete": 0,
        "unclear": 0,
        "factual error": 0,
        "missing": 0
    }

    for note in all_notes:
        note_lower = note.lower()
        for keyword in issue_keywords:
            if keyword in note_lower:
                issue_keywords[keyword] += 1

    if any(issue_keywords.values()):
        click.echo(f"\n⚠️ Common Issues:")
        for issue, count in sorted(issue_keywords.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                click.echo(f"   {issue.title()}: {count}")

    # Generate report
    report = {
        "metadata": {
            "source_file": Path(verified_file).name,
            "total_variations": len(variations),
            "threshold": threshold,
            "analyzed_at": "2026-02-09"
        },
        "summary": {
            "passed_count": len(passed),
            "failed_count": len(failed),
            "pass_rate": pass_rate,
            "average_score": avg_score
        },
        "score_distribution": score_buckets,
        "common_issues": issue_keywords,
        "passed_ids": [v["variation_id"] for v in passed],
        "failed_ids": [v["variation_id"] for v in failed]
    }

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    click.echo(f"\n✅ Report generated: {output_path}")
    click.echo("="*70)


@cli.command()
@click.argument("verified_file", type=click.Path(exists=True))
@click.option("--threshold", default=70, help="Minimum quality score")
@click.option("--output", default="data/cache_ready.json", help="Output file for cache-ready variations")
def filter_passed(verified_file: str, threshold: int, output: str):
    """
    Filter only passed variations ready for Redis cache.

    VERIFIED_FILE: JSON file with verified variations
    """
    with open(verified_file, "r") as f:
        data = json.load(f)

    variations = data.get("variations", [])
    passed = [
        v for v in variations
        if v.get("verified", False) and v.get("quality_score", 0) >= threshold
    ]

    click.echo(f"✅ Filtered {len(passed)}/{len(variations)} passed variations (≥{threshold})")

    cache_ready = {
        "metadata": {
            "source_file": Path(verified_file).name,
            "total_variations": len(passed),
            "quality_threshold": threshold,
            "created_at": "2026-02-09",
            "status": "ready_for_cache"
        },
        "conversations": []
    }

    for v in passed:
        cache_ready["conversations"].append({
            "id": v["variation_id"],
            "query": v["query"],
            "response": v["response"],
            "quality_score": v["quality_score"],
            "ttl_hours": 24  # Redis cache TTL
        })

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(cache_ready, f, indent=2)

    click.echo(f"📁 Cache-ready file: {output_path}")


@cli.command()
@click.argument("report_file", type=click.Path(exists=True))
def show_report(report_file: str):
    """
    Display verification report in human-readable format.

    REPORT_FILE: JSON verification report from analyze command
    """
    with open(report_file, "r") as f:
        report = json.load(f)

    metadata = report.get("metadata", {})
    summary = report.get("summary", {})
    distribution = report.get("score_distribution", {})
    issues = report.get("common_issues", {})

    click.echo("\n" + "="*70)
    click.echo("📊 VERIFICATION REPORT")
    click.echo("="*70)

    click.echo(f"\n📁 Source: {metadata.get('source_file')}")
    click.echo(f"🎯 Threshold: {metadata.get('threshold')}")
    click.echo(f"📅 Analyzed: {metadata.get('analyzed_at')}")

    click.echo(f"\n✅ Summary:")
    click.echo(f"   Total: {metadata.get('total_variations')}")
    click.echo(f"   Passed: {summary.get('passed_count')} ({summary.get('pass_rate', 0):.1f}%)")
    click.echo(f"   Failed: {summary.get('failed_count')}")
    click.echo(f"   Average Score: {summary.get('average_score', 0):.1f}")

    click.echo(f"\n📈 Score Distribution:")
    for bucket, count in distribution.items():
        pct = count / metadata.get('total_variations', 1) * 100
        click.echo(f"   {bucket}: {count} ({pct:.1f}%)")

    if any(issues.values()):
        click.echo(f"\n⚠️ Common Issues:")
        for issue, count in sorted(issues.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                click.echo(f"   {issue.title()}: {count}")

    click.echo("\n" + "="*70)


@cli.command()
@click.argument("verified_file", type=click.Path(exists=True))
@click.option("--count", default=5, help="Number of top/bottom examples to show")
def show_examples(verified_file: str, count: int):
    """
    Show top and bottom scoring examples for quality review.

    VERIFIED_FILE: JSON file with verified variations
    """
    with open(verified_file, "r") as f:
        data = json.load(f)

    variations = data.get("variations", [])
    verified = [v for v in variations if v.get("verified", False)]

    if not verified:
        click.echo("❌ No verified variations found")
        return

    # Sort by quality score
    sorted_vars = sorted(verified, key=lambda x: x.get("quality_score", 0), reverse=True)

    click.echo("\n" + "="*70)
    click.echo(f"🏆 TOP {count} SCORING EXAMPLES")
    click.echo("="*70)

    for i, v in enumerate(sorted_vars[:count], 1):
        click.echo(f"\n{i}. {v.get('variation_id')} - Score: {v.get('quality_score', 0)}")
        click.echo(f"   Query: {v.get('query', '')[:80]}...")
        click.echo(f"   Notes: {v.get('verification_notes', 'N/A')[:100]}...")

    click.echo("\n" + "="*70)
    click.echo(f"❌ BOTTOM {count} SCORING EXAMPLES")
    click.echo("="*70)

    for i, v in enumerate(sorted_vars[-count:], 1):
        click.echo(f"\n{i}. {v.get('variation_id')} - Score: {v.get('quality_score', 0)}")
        click.echo(f"   Query: {v.get('query', '')[:80]}...")
        click.echo(f"   Notes: {v.get('verification_notes', 'N/A')[:100]}...")

    click.echo("\n" + "="*70)


if __name__ == "__main__":
    cli()
