#!/usr/bin/env python3
"""CLI entry point for running anomaly scans.

OPSEC: This script runs LOCALLY ONLY. Never deploy to cloud.
Output contains only Neo4j element IDs — no entity names.

Usage:
    python scripts/run_anomaly_scan.py
    python scripts/run_anomaly_scan.py --config thresholds.yaml
    python scripts/run_anomaly_scan.py --output alerts.json
    python scripts/run_anomaly_scan.py --detectors centrality_jump,temporal_burst
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from osint_nexus.anomaly.runner import AnomalyRunner
from osint_nexus.anomaly.thresholds import load_thresholds
from osint_nexus.config import NEO4J_DATABASE, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from osint_nexus.utils.logging import get_logger

logger = get_logger("anomaly.cli")


async def main(args: argparse.Namespace) -> int:
    """Run anomaly scan and output results."""
    from neo4j import AsyncGraphDatabase

    config_path = Path(args.config) if args.config else None
    thresholds = load_thresholds(config_path)

    # Filter detectors if --detectors specified
    runner = AnomalyRunner(config_path=config_path)
    if args.detectors:
        requested = set(args.detectors.split(","))
        runner._detectors = [
            d for d in runner._detectors if d.pattern_name in requested
        ]
        if not runner._detectors:
            logger.error("No matching detectors for: %s", args.detectors)
            return 1

    # Connect to Neo4j
    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        await driver.verify_connectivity()
        logger.info("Connected to Neo4j: %s", NEO4J_URI)
    except Exception as e:
        logger.error("Cannot connect to Neo4j: %s", e)
        return 1

    try:
        async with driver.session(database=NEO4J_DATABASE) as session:
            alerts = await runner.run_all(session)
    finally:
        await driver.close()

    # Output results
    output = runner.to_dict(alerts)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
        logger.info("Wrote %d alerts to %s", len(output), output_path)
    else:
        print(json.dumps(output, indent=2, ensure_ascii=False))

    # Summary
    by_pattern: dict[str, int] = {}
    for a in alerts:
        by_pattern[a.pattern] = by_pattern.get(a.pattern, 0) + 1

    logger.info("=== Scan Summary ===")
    logger.info("Total alerts: %d", len(alerts))
    for pattern, count in sorted(by_pattern.items()):
        logger.info("  %s: %d", pattern, count)

    if alerts:
        top = alerts[0]
        logger.info(
            "Top alert: pattern=%s score=%.3f confidence=%.3f",
            top.pattern,
            top.score,
            top.confidence,
        )

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="OSINT Nexus Anomaly Scanner — local use only",
    )
    parser.add_argument(
        "--config",
        help="Path to YAML threshold config file",
    )
    parser.add_argument(
        "--output",
        help="Write alerts to JSON file (default: stdout)",
    )
    parser.add_argument(
        "--detectors",
        help="Comma-separated list of detector names to run",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    exit_code = asyncio.run(main(args))
    raise SystemExit(exit_code)
