"""Validate `apps/organism/organism/genome.yaml`.

Authoritative spec: docs/innervation-2026-04-29/07_innervation_protocol.md §2.

The validator parses the YAML, enforces the documented invariants, and
returns a list of human-readable error strings. Empty list = valid.

Invocation:

    python -m organism.tools.validate_genome [PATH] [--bootstrap] [--update-checksum]

Exit code 0 on success, 1 on validation errors. Designed for use as a
pre-commit hook AND a standalone CI step.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Iterable

import yaml


# Allowed enum values per 07_innervation_protocol.md §2.2.
_RUNTIMES = frozenset({
    "pro_launchd",
    "mini_launchd",  # 2026-05-07 — Modo B 2-node topology (Pro+Mini)
    "air_launchd",
    "air_cron",
    "fly_machine",
    "vercel_function",
    "github_actions",
    "mcp_session",
    "backend_internal",
})

_TYPES = frozenset({
    "daemon",
    "cron",
    "webhook",
    "agent",
    "channel",
    "evaluator",
})

_RECOVERY_ACTIONS = frozenset({
    "fly_machines_start",
    "launchctl_kickstart",
    "vercel_redeploy",
    "github_actions_rerun",
    "human_only",
    "noop",
})

_SEVERITIES = frozenset({"info", "warning", "error", "critical"})

_REQUIRED_FIELDS = (
    "id",
    "runtime",
    "type",
    "expected_hb_seconds",
    "owner_module",
    "dependencies",
    "recovery_action",
    "severity_on_silence",
)


def compute_checksum(organs: Iterable[dict]) -> str:
    """SHA256 over the canonical JSON of the organ list.

    Canonical form = JSON with sorted keys + no whitespace, so logically
    identical structures hash identically regardless of YAML formatting or
    Python dict insertion order.
    """
    canonical = json.dumps(list(organs), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_organ(organ: dict, idx: int) -> list[str]:
    errors: list[str] = []
    label = organ.get("id", f"<organ #{idx}>")

    for field in _REQUIRED_FIELDS:
        if field not in organ:
            errors.append(f"{label}: missing required field '{field}'")

    runtime = organ.get("runtime")
    if runtime is not None and runtime not in _RUNTIMES:
        errors.append(
            f"{label}: invalid runtime '{runtime}' "
            f"(allowed: {sorted(_RUNTIMES)})"
        )

    organ_type = organ.get("type")
    if organ_type is not None and organ_type not in _TYPES:
        errors.append(
            f"{label}: invalid type '{organ_type}' (allowed: {sorted(_TYPES)})"
        )

    recovery = organ.get("recovery_action")
    if recovery is not None and recovery not in _RECOVERY_ACTIONS:
        errors.append(
            f"{label}: invalid recovery_action '{recovery}' "
            f"(allowed: {sorted(_RECOVERY_ACTIONS)})"
        )

    severity = organ.get("severity_on_silence")
    if severity is not None and severity not in _SEVERITIES:
        errors.append(
            f"{label}: invalid severity_on_silence '{severity}' "
            f"(allowed: {sorted(_SEVERITIES)})"
        )

    expected = organ.get("expected_hb_seconds")
    if expected is not None and (
        not isinstance(expected, int) or expected < 0
    ):
        errors.append(
            f"{label}: expected_hb_seconds must be a non-negative integer "
            f"(got {expected!r})"
        )

    return errors


def _detect_duplicate_ids(organs: list[dict]) -> list[str]:
    seen: dict[str, int] = {}
    errors: list[str] = []
    for idx, organ in enumerate(organs):
        oid = organ.get("id")
        if oid is None:
            continue
        if oid in seen:
            errors.append(
                f"duplicate id '{oid}' at organ #{idx} "
                f"(first seen at #{seen[oid]})"
            )
        else:
            seen[oid] = idx
    return errors


def _detect_dependency_errors(organs: list[dict]) -> list[str]:
    """Validate every dependency resolves to a known id and the graph is acyclic."""
    errors: list[str] = []
    ids = {o["id"] for o in organs if "id" in o}
    deps_by_id: dict[str, list[str]] = {}

    for organ in organs:
        oid = organ.get("id")
        if oid is None:
            continue
        deps = organ.get("dependencies") or []
        if not isinstance(deps, list):
            errors.append(f"{oid}: dependencies must be a list")
            continue
        deps_by_id[oid] = deps
        for dep in deps:
            if dep not in ids:
                errors.append(f"{oid}: unknown dependency '{dep}'")

    # Detect cycles via DFS three-color marking.
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {oid: WHITE for oid in ids}

    def dfs(node: str, stack: list[str]) -> None:
        color[node] = GRAY
        stack.append(node)
        for dep in deps_by_id.get(node, []):
            if dep not in color:
                continue
            if color[dep] == GRAY:
                cycle_start = stack.index(dep)
                cycle = " → ".join(stack[cycle_start:] + [dep])
                errors.append(f"dependency cycle detected: {cycle}")
                return
            if color[dep] == WHITE:
                dfs(dep, stack)
        stack.pop()
        color[node] = BLACK

    for oid in list(ids):
        if color.get(oid) == WHITE:
            dfs(oid, [])

    return errors


def validate_data(data: dict, *, bootstrap: bool = False) -> list[str]:
    """Validate parsed YAML data; return errors or [] when valid."""
    errors: list[str] = []

    if not isinstance(data, dict):
        return ["genome must be a mapping at the top level"]

    if data.get("version") != 1:
        errors.append(
            f"unsupported version {data.get('version')!r} (only version 1 is recognised)"
        )

    if data.get("checksum_algo") != "sha256":
        errors.append(
            f"unsupported checksum_algo {data.get('checksum_algo')!r} "
            f"(only sha256 is recognised)"
        )

    organs = data.get("organs")
    if not isinstance(organs, list):
        return errors + ["genome.organs must be a list"]

    for idx, organ in enumerate(organs):
        if not isinstance(organ, dict):
            errors.append(f"organ #{idx} is not a mapping")
            continue
        errors.extend(_validate_organ(organ, idx))

    errors.extend(_detect_duplicate_ids(organs))
    errors.extend(_detect_dependency_errors(organs))

    expected_checksum = compute_checksum(organs)
    recorded = data.get("checksum", "")
    if recorded == "":
        if not bootstrap:
            errors.append(
                "checksum is empty — refusing to validate (use --bootstrap "
                "for the very first commit, or run --update-checksum to "
                f"compute it now: {expected_checksum})"
            )
    elif recorded != expected_checksum:
        errors.append(
            f"checksum mismatch: recorded={recorded!r} expected={expected_checksum!r}"
        )

    return errors


def validate_file(path: Path, *, bootstrap: bool = False) -> list[str]:
    """Read YAML at `path` and validate. Missing-file / parse-error are surfaced as errors."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return [f"genome file not found: {path}"]

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return [f"YAML parse error: {exc}"]

    return validate_data(data or {}, bootstrap=bootstrap)


def update_checksum(path: Path) -> str:
    """Rewrite `path` with the canonical checksum filled in. Returns the new digest."""
    text = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    organs = data.get("organs") or []
    digest = compute_checksum(organs)
    data["checksum"] = digest
    Path(path).write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return digest


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate genome.yaml")
    parser.add_argument(
        "path",
        nargs="?",
        default=str(
            Path(__file__).resolve().parent.parent / "genome.yaml"
        ),
        help="Path to genome.yaml (default: <package>/genome.yaml)",
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Allow empty checksum (use only for the very first commit)",
    )
    parser.add_argument(
        "--update-checksum",
        action="store_true",
        help="Rewrite the file with the canonical checksum and exit",
    )
    args = parser.parse_args(argv)

    path = Path(args.path)
    if args.update_checksum:
        digest = update_checksum(path)
        print(f"checksum updated: {digest}")
        return 0

    errors = validate_file(path, bootstrap=args.bootstrap)
    if errors:
        for err in errors:
            print(f"✗ {err}", file=sys.stderr)
        return 1
    print(f"✓ genome.yaml valid ({path})")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
