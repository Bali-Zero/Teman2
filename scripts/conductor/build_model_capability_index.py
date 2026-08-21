#!/usr/bin/env python3
"""Build or verify the deterministic checked-in MIR capability projection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MIR = ROOT / "infra" / "conductor"
CARD_DIR = MIR / "model_cards"
ENDPOINT_DIR = MIR / "endpoint_profiles"
INDEX_PATH = MIR / "model_capability_index.v1.json"
GENERATED_AT = "2026-08-21"
GENERATION_EVIDENCE = [
    {
        "level": "declared",
        "ref": "research/operations/2026-08-21-universal-conductor-control-plane-design.md#4",
        "observed_at": "2026-08-21",
    }
]


def load_records(directory: Path) -> list[dict[str, Any]]:
    """Load records in filename order so equivalent inputs produce equivalent bytes."""
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]


def build_index(
    cards: list[dict[str, Any]], endpoints: list[dict[str, Any]]
) -> dict[str, Any]:
    """Return the router projection without interpreting availability or quality."""
    return {
        "schema_version": "model-capability-index.v1",
        "generated_at": GENERATED_AT,
        "generation": {
            "style": "deterministic checked-in projection",
            "inputs": [
                "capability_ontology.v1.json",
                "task_profiles.v1.json",
                "model_cards/*.json",
                "endpoint_profiles/*.json",
                "inventory_observations.v1.json",
            ],
            "evidence": GENERATION_EVIDENCE,
        },
        "model_count": len(cards),
        "endpoint_count": len(endpoints),
        "models": [
            {
                "model_card_id": card["id"],
                "family": card["identity"]["family"],
                "kind": card["identity"]["kind"],
                "routing_status": card["routing"]["status"],
                "automated_routing": card["routing"]["automated_routing"],
                "evidence": card["evidence"],
            }
            for card in cards
        ],
        "endpoints": [
            {
                "endpoint_id": endpoint["id"],
                "model_card_id": endpoint["model_card_id"],
                "engine": endpoint["invocation"]["engine"],
                "model_identifier": endpoint["invocation"]["model_identifier"],
                "auth_surface": endpoint["auth_surface"],
                "routing_status": endpoint["routing"]["status"],
                "automated_routing": endpoint["routing"]["automated_routing"],
                "machine_allowlist": endpoint["machine_constraints"]["allowlist"],
                "evidence": endpoint["evidence"],
            }
            for endpoint in endpoints
        ],
    }


def render(index: dict[str, Any]) -> str:
    """Return deterministic JSON in the repository's enforced Prettier shape."""
    canonical_json = json.dumps(index, ensure_ascii=False, indent=2, sort_keys=False)
    result = subprocess.run(
        ["npx", "--no-install", "prettier", "--parser", "json"],
        cwd=ROOT,
        input=canonical_json,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Prettier could not format the deterministic MIR projection: "
            + result.stderr.strip()
        )
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the checked-in projection is stale",
    )
    parser.add_argument(
        "--write", action="store_true", help="replace the checked-in projection"
    )
    args = parser.parse_args()
    if args.check and args.write:
        parser.error("--check and --write are mutually exclusive")

    output = render(build_index(load_records(CARD_DIR), load_records(ENDPOINT_DIR)))
    if args.check:
        return 0 if INDEX_PATH.read_text(encoding="utf-8") == output else 1
    if args.write:
        INDEX_PATH.write_text(output, encoding="utf-8")
        return 0
    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
