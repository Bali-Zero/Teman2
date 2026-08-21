#!/usr/bin/env python3
"""Offline CLI for planning and aggregating the MIR priority calibration pilot.

No command in this module invokes a provider.  An operator or separate benchmark
runner supplies blinded JSONL scores and exact host observations as artifacts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from scripts.conductor.calibration import (  # noqa: E402
    CalibrationError,
    aggregate_blinded_samples,
)
from scripts.conductor.model_registry import (  # noqa: E402
    ModelIntelligenceRegistry,
    RegistryError,
    load_registry,
)


def _json_text(value: Mapping[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def _load_pilot(root: Path, registry: ModelIntelligenceRegistry) -> dict[str, Any]:
    path = root / "infra" / "conductor" / "priority_calibration_pilot.v1.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {
        "schema_version",
        "benchmark_id",
        "benchmark_version",
        "roster",
    }:
        raise CalibrationError("priority pilot has an unexpected top-level shape")
    if raw["schema_version"] != "priority-calibration-pilot.v1":
        raise CalibrationError("priority pilot schema_version is unsupported")
    if not all(
        isinstance(raw.get(field), str) and raw[field]
        for field in ("benchmark_id", "benchmark_version")
    ):
        raise CalibrationError("priority pilot benchmark identity is incomplete")
    roster = raw["roster"]
    if not isinstance(roster, list) or not roster:
        raise CalibrationError("priority pilot roster must be a non-empty array")
    seen: set[str] = set()
    for item in roster:
        if not isinstance(item, dict) or set(item) != {
            "endpoint_id",
            "task_profile_ids",
        }:
            raise CalibrationError("priority pilot roster item shape is invalid")
        endpoint_id = item["endpoint_id"]
        task_profile_ids = item["task_profile_ids"]
        if endpoint_id in seen:
            raise CalibrationError(f"duplicate priority endpoint: {endpoint_id}")
        seen.add(endpoint_id)
        if endpoint_id not in registry.endpoint_profiles:
            raise CalibrationError(f"unknown priority endpoint: {endpoint_id}")
        if (
            not isinstance(task_profile_ids, list)
            or not task_profile_ids
            or len(task_profile_ids) != len(set(task_profile_ids))
        ):
            raise CalibrationError(
                f"priority endpoint {endpoint_id} needs unique task profiles"
            )
        for profile_id in task_profile_ids:
            profile = registry.profile(profile_id)
            if (
                profile.benchmark_id != raw["benchmark_id"]
                or profile.benchmark_version != raw["benchmark_version"]
            ):
                raise CalibrationError(
                    f"priority profile {profile_id} does not bind the pilot benchmark"
                )
    return raw


def _plan(root: Path) -> dict[str, Any]:
    registry = load_registry(root)
    pilot = _load_pilot(root, registry)
    entries: list[dict[str, Any]] = []
    for item in sorted(pilot["roster"], key=lambda value: value["endpoint_id"]):
        endpoint_id = item["endpoint_id"]
        candidate = registry.endpoint(endpoint_id)
        for profile_id in sorted(item["task_profile_ids"]):
            profile = registry.profile(profile_id)
            entries.append(
                {
                    "endpoint_id": endpoint_id,
                    "endpoint_profile_hash": candidate.endpoint_profile_hash,
                    "task_profile_id": profile_id,
                    "minimum_task_score": profile.minimum_task_score,
                    "minimum_sample_count": profile.minimum_sample_count,
                    "maximum_dispersion": profile.maximum_dispersion,
                    "minimum_context_tokens": profile.minimum_context_tokens,
                    "minimum_output_tokens": profile.minimum_output_tokens,
                    "source_routing_status": registry.endpoint_profiles[endpoint_id][
                        "routing"
                    ]["status"],
                    "auth_surface": candidate.auth_surface.value,
                }
            )
    return {
        "schema_version": "priority-calibration-plan.v1",
        "benchmark_id": pilot["benchmark_id"],
        "benchmark_version": pilot["benchmark_version"],
        "execution": "not_implemented_no_provider_calls",
        "entries": entries,
    }


def _read_samples(path: Path) -> tuple[Mapping[str, Any], ...]:
    samples: list[Mapping[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise CalibrationError(
                f"invalid sample JSON on line {line_number}: {error.msg}"
            ) from error
        if not isinstance(value, dict):
            raise CalibrationError(f"sample line {line_number} must be an object")
        samples.append(value)
    if not samples:
        raise CalibrationError("sample file is empty")
    return tuple(samples)


def _aggregate(args: argparse.Namespace) -> dict[str, Any]:
    root = args.root.resolve()
    registry = load_registry(root)
    records = aggregate_blinded_samples(
        _read_samples(args.samples),
        endpoint_hashes={
            endpoint_id: registry.endpoint(endpoint_id).endpoint_profile_hash
            for endpoint_id in registry.endpoint_profiles
        },
        benchmark_id=args.benchmark_id,
        benchmark_version=args.benchmark_version,
        scorer_id=args.scorer_id,
        scorer_version=args.scorer_version,
        measured_at=args.measured_at,
        expires_at=args.expires_at,
    )
    return {
        "schema_version": "calibration-overlay.v1",
        "generated_at": args.measured_at,
        "records": [record.as_mapping() for record in records],
    }


def _validate(args: argparse.Namespace) -> dict[str, Any]:
    registry = load_registry(
        args.root,
        as_of=args.as_of,
        calibration_path=args.calibration,
        host_observation_paths=tuple(args.observations),
    )
    return {
        "schema_version": "calibration-validation.v1",
        "as_of": args.as_of,
        "operational": registry.operational,
        "eligible_endpoint_ids": [
            candidate.endpoint_id for candidate in registry.endpoints()
        ],
        "diagnostics": list(registry.overlay_diagnostics),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="render the offline priority roster")
    plan.add_argument("--root", type=Path, default=ROOT)

    aggregate = subparsers.add_parser(
        "aggregate", help="aggregate blinded JSONL samples into an overlay"
    )
    aggregate.add_argument("--root", type=Path, default=ROOT)
    aggregate.add_argument("--samples", type=Path, required=True)
    aggregate.add_argument("--output", type=Path, required=True)
    aggregate.add_argument("--benchmark-id", required=True)
    aggregate.add_argument("--benchmark-version", required=True)
    aggregate.add_argument("--scorer-id", required=True)
    aggregate.add_argument("--scorer-version", required=True)
    aggregate.add_argument("--measured-at", required=True)
    aggregate.add_argument("--expires-at", required=True)

    validate = subparsers.add_parser(
        "validate", help="validate overlay joins without invoking endpoints"
    )
    validate.add_argument("--root", type=Path, default=ROOT)
    validate.add_argument("--as-of", required=True)
    validate.add_argument("--calibration", type=Path, required=True)
    validate.add_argument("--observations", type=Path, action="append", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            output = _plan(args.root.resolve())
            sys.stdout.write(_json_text(output))
            return 0
        if args.command == "aggregate":
            output = _aggregate(args)
            args.output.write_text(_json_text(output), encoding="utf-8")
            return 0
        if args.command == "validate":
            sys.stdout.write(_json_text(_validate(args)))
            return 0
    except (CalibrationError, RegistryError, OSError) as error:
        sys.stderr.write(f"calibration error: {error}\n")
        return 2
    parser.error("unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
