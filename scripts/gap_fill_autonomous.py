#!/usr/bin/env python3
"""Curiosity Loop — Autonomous gap fill cron script.

# Organo: scripts → produce kg_proposals + Telegram report → consuma coverage_matrix.json

Runs a single Curiosity Loop cycle:
1. Load gaps from coverage_matrix.json
2. Research via tier dispatchers (Ollama/HyDE/deep research)
3. Grade evidence (CuriosityGrader)
4. Create proposals in kg_proposals (NEVER direct KG write)
5. Send Telegram report to Zero

LaunchAgent: com.graph.curiosity-loop.plist (04:30 WITA, Air)
Safety: max 20 gaps/cycle, propose-only, Zero approves via kg-propose CLI.

Usage:
    python3 scripts/gap_fill_autonomous.py [--max-gaps 20] [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add graph-engine to path
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "graph-engine" / "src"))

from nuzantara_graph.curiosity.models import CycleResult
from nuzantara_graph.curiosity.orchestrator import CuriosityOrchestrator
from nuzantara_graph.curiosity.proposals import KGProposalStore

logger = logging.getLogger(__name__)

# Paths
COVERAGE_MATRIX = str(
    Path(__file__).parent.parent / "apps" / "evaluator" / "nlm_deep_research" / "coverage_matrix.json"
)
LOG_DIR = Path.home() / "logs"
LOG_FILE = LOG_DIR / "curiosity_loop.log"

# Telegram
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")


def _get_database_url() -> str:
    """Resolve database URL from environment."""
    return os.environ.get(
        "DATABASE_URL",
        os.environ.get(
            "NUZANTARA_DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/nuzantara_rag",
        ),
    )


def _send_telegram(message: str) -> None:
    """Send Telegram notification to Zero."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set, skipping notification")
        return

    try:
        import urllib.request
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = json.dumps({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
        }).encode()
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30):
            pass
        logger.info("Telegram notification sent")
    except Exception as e:
        logger.warning("Telegram send failed: %s", e)


def _format_report(result: CycleResult, stats: dict) -> str:
    """Format Telegram report."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"*Curiosity Loop Report* — {now}",
        "",
        f"*Gap scanned:* {result.gaps_scanned}",
    ]

    if result.proposals_by_domain:
        for domain, count in sorted(result.proposals_by_domain.items(), key=lambda x: -x[1]):
            lines.append(f"  {domain}: {count}")

    lines.append(f"\n*Proposals created:* {result.proposals_created}")

    if result.proposals_by_tier:
        for tier, count in sorted(result.proposals_by_tier.items()):
            lines.append(f"  {tier}: {count}")

    if result.skipped_dedup > 0:
        lines.append(f"Skipped (dedup): {result.skipped_dedup}")
    if result.skipped_blacklisted > 0:
        lines.append(f"Skipped (blacklisted): {result.skipped_blacklisted}")
    if result.errors > 0:
        lines.append(f"Errors: {result.errors}")

    # Stats from store
    status_counts = stats.get("status_counts", {})
    pending = status_counts.get("pending", 0)
    applied = status_counts.get("applied", 0)
    rejected = status_counts.get("rejected", 0)

    lines.append(f"\n*Queue:* {pending} pending Zero review")
    if applied:
        lines.append(f"Applied: {applied}")
    if rejected:
        lines.append(f"Rejected: {rejected}")

    density = stats.get("ontological_density", 0.0)
    nodes = stats.get("node_count", 0)
    edges = stats.get("edge_count", 0)
    lines.append(f"\n*KG density:* {density:.3f} ({nodes:,} nodes, {edges:,} edges)")
    lines.append(f"Duration: {result.duration_seconds:.1f}s")

    return "\n".join(lines)


async def run(max_gaps: int = 20, dry_run: bool = False) -> None:
    """Run a single curiosity cycle."""
    store = KGProposalStore(database_url=_get_database_url())

    try:
        orch = CuriosityOrchestrator(
            proposal_store=store,
            coverage_matrix_path=COVERAGE_MATRIX,
        )

        if dry_run:
            gaps = orch._load_gaps()
            prioritized = orch._prioritize(gaps)[:max_gaps]
            logger.info("DRY RUN: would process %d gaps (of %d total)", len(prioritized), len(gaps))
            for g in prioritized:
                tier = orch.classify_tier(g)
                logger.info("  [%s] %s — %s (severity=%.1f)", tier.value, g.domain, g.topic, g.severity)
            return

        result = await orch.run_cycle(max_gaps=max_gaps)
        stats = await store.stats()

        # Send Telegram report
        report = _format_report(result, stats)
        logger.info("Cycle complete:\n%s", report)
        _send_telegram(report)

    finally:
        await store.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Curiosity Loop autonomous gap fill")
    parser.add_argument("--max-gaps", type=int, default=20, help="Max gaps per cycle")
    parser.add_argument("--dry-run", action="store_true", help="Preview without executing")
    args = parser.parse_args()

    # Setup logging
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(str(LOG_FILE), mode="a"),
        ],
    )

    logger.info("Starting Curiosity Loop cycle (max_gaps=%d, dry_run=%s)", args.max_gaps, args.dry_run)
    asyncio.run(run(max_gaps=args.max_gaps, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
