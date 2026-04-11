"""CLI entry point for OSINT anomaly scan.

Runs all 5 detectors against a local Neo4j instance and prints
ranked alerts as JSON to stdout. Entity names never appear in the
output — only opaque IDs.

Usage
-----
    python scripts/run_anomaly_scan.py [--config config/anomaly_thresholds.yaml]
                                       [--dry-run]
                                       [--detector NAME]
                                       [--output path.json]

``--dry-run`` short-circuits the session connection and exits 0 after
validating config + detector wiring. Useful for CI smoke checks.

OPSEC
-----
* Refuses to run against any URI that is not localhost / 127.0.0.1 /
  tailscale (100.x) unless ``--allow-remote`` is passed. OSINT data
  is blindato per ``feedback_osint_blindato.md``.
* Never writes to the graph.
* Never opens outbound non-neo4j connections.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# Make sure we can import osint_nexus when run from the app root
_HERE = Path(__file__).resolve()
_APP_ROOT = _HERE.parent.parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from osint_nexus.anomaly import AnomalyRunner, load_thresholds  # noqa: E402
from osint_nexus.anomaly.detectors import (  # noqa: E402
    AngkatanDisjointDetector,
    BridgeOutlierDetector,
    CentralityJumpDetector,
    EigenvectorReverseDetector,
    TemporalBurstDetector,
)
from osint_nexus.utils.logging import get_logger  # noqa: E402

logger = get_logger("anomaly.cli")

_DETECTOR_REGISTRY: dict[str, Any] = {
    "centrality_jump": CentralityJumpDetector,
    "bridge_outlier": BridgeOutlierDetector,
    "temporal_burst": TemporalBurstDetector,
    "angkatan_disjoint": AngkatanDisjointDetector,
    "eigenvector_reverse": EigenvectorReverseDetector,
}


def _is_local_uri(uri: str) -> bool:
    lowered = uri.lower()
    for host in ("localhost", "127.0.0.1", "::1"):
        if host in lowered:
            return True
    # Tailscale CGNAT range 100.64.0.0/10
    if "bolt://100." in lowered or "neo4j://100." in lowered:
        return True
    return False


def _build_detectors(thresholds, selected: list[str] | None):
    selected = selected or list(_DETECTOR_REGISTRY.keys())
    for name in selected:
        if name not in _DETECTOR_REGISTRY:
            raise SystemExit(f"Unknown detector: {name}. Valid: {sorted(_DETECTOR_REGISTRY)}")
    return [
        _DETECTOR_REGISTRY[name](thresholds=thresholds.for_detector(name))
        for name in selected
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run OSINT anomaly scan (local only)")
    parser.add_argument("--config", type=Path, default=None, help="YAML thresholds file")
    parser.add_argument(
        "--detector",
        action="append",
        help="Run only a specific detector (can be repeated). Default: all.",
    )
    parser.add_argument("--output", type=Path, default=None, help="Write JSON to this file")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config + wiring, do not open a Neo4j session",
    )
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="Permit a non-local NEO4J_URI (USE WITH CARE)",
    )
    args = parser.parse_args(argv)

    # 1. Load thresholds
    try:
        thresholds = load_thresholds(args.config)
    except FileNotFoundError as exc:
        logger.error("config not found: %s", exc)
        return 2
    except Exception as exc:
        logger.error("failed to load thresholds: %s", type(exc).__name__)
        return 2

    # 2. Build detectors (also validates the --detector flag values)
    try:
        detectors = _build_detectors(thresholds, args.detector)
    except SystemExit as exc:
        logger.error("detector wiring failure: %s", exc)
        return 2

    logger.info("detectors active: %s", [d.name for d in detectors])
    runner = AnomalyRunner(detectors=detectors)

    if args.dry_run:
        logger.info("dry-run ok (session not opened)")
        _emit({"dry_run": True, "detectors": [d.name for d in detectors]}, args.output)
        return 0

    # 3. Open Neo4j session
    uri = os.getenv("NEO4J_URI", "bolt://localhost:17687")
    if not args.allow_remote and not _is_local_uri(uri):
        logger.error(
            "refusing to run against non-local NEO4J_URI (%s). Use --allow-remote to override.",
            uri,
        )
        return 3

    try:
        from neo4j import GraphDatabase  # type: ignore[import-not-found]
    except ImportError:
        logger.error("neo4j driver not installed")
        return 4

    user = os.getenv("NEO4J_USER", "neo4j")
    pwd = os.getenv("NEO4J_PASSWORD", "osint-nexus-2026")
    database = os.getenv("NEO4J_DATABASE", "neo4j")

    alerts: list[dict[str, Any]] = []
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    try:
        with driver.session(database=database) as session:
            result = runner.run(session)
            alerts = [a.to_dict() for a in result]
    finally:
        driver.close()

    logger.info("scan complete: %d alerts", len(alerts))
    _emit({"alerts": alerts, "count": len(alerts)}, args.output)
    return 0


def _emit(payload: dict[str, Any], output: Path | None) -> None:
    blob = json.dumps(payload, indent=2, sort_keys=True)
    if output:
        output.write_text(blob)
    else:
        sys.stdout.write(blob + "\n")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
