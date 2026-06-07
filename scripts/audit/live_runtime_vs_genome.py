#!/usr/bin/env python3
"""Compare live launchd/cron runtime snapshots against the organism genome.

Read-only by design: the script never bootstraps, unloads, kickstarts, or edits
launchd jobs. It can run locally or consume remote snapshots captured over SSH.
"""
from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - exercised only outside repo venv
    yaml = None


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = ROOT / "apps/organism/organism/organs_registry.yaml"
DEFAULT_PREFIXES = (
    "com.balizero.",
    "com.nuzantara.",
    "com.cell.",
    "com.matagaruda.",
    "homebrew.mxcl.",
)
SCRIPT_EXTENSIONS = (".py", ".sh", ".cjs", ".mjs", ".js", ".rb")
CRON_NICKNAMES = {
    "@reboot",
    "@yearly",
    "@annually",
    "@monthly",
    "@weekly",
    "@daily",
    "@midnight",
    "@hourly",
}


def _matches_prefix(label: str, prefixes: tuple[str, ...]) -> bool:
    return any(label.startswith(prefix) for prefix in prefixes)


def _parse_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_launchctl_list(
    text: str, prefixes: tuple[str, ...] = DEFAULT_PREFIXES
) -> dict[str, dict[str, Any]]:
    """Parse `launchctl list` output keyed by label."""
    entries: dict[str, dict[str, Any]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.lower().startswith("pid"):
            continue
        parts = line.split(None, 2)
        if len(parts) != 3:
            continue
        pid_s, status_s, label = parts
        if not _matches_prefix(label, prefixes):
            continue
        entries[label] = {
            "pid": None if pid_s == "-" else _parse_int(pid_s),
            "status": _parse_int(status_s),
        }
    return entries


def parse_plist_label_listing(
    text: str, prefixes: tuple[str, ...] = DEFAULT_PREFIXES
) -> dict[str, dict[str, str]]:
    """Parse lines of `label<TAB>file` or plist paths into label records."""
    labels: dict[str, dict[str, str]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if "\t" in line:
            label, source = line.split("\t", 1)
        else:
            source = line
            name = Path(line).name
            label = name[:-6] if name.endswith(".plist") else name
        if not _matches_prefix(label, prefixes):
            continue
        labels[label] = {"source": source}
    return labels


def parse_local_plists(
    plist_dir: Path, prefixes: tuple[str, ...] = DEFAULT_PREFIXES
) -> dict[str, dict[str, str]]:
    """Read local plist files and return launchd labels."""
    labels: dict[str, dict[str, str]] = {}
    if not plist_dir.is_dir():
        return labels
    for path in sorted(plist_dir.glob("*.plist")):
        name = path.name
        if ".disabled-" in name or ".backup-" in name:
            continue
        try:
            with path.open("rb") as fh:
                data = plistlib.load(fh)
            label = str(data.get("Label") or name[:-6])
        except Exception:
            label = name[:-6]
        if _matches_prefix(label, prefixes):
            labels[label] = {"source": str(path)}
    return labels


def _split_cron_line(line: str) -> tuple[str, str] | None:
    parts = line.split()
    if not parts:
        return None
    if parts[0] in CRON_NICKNAMES and len(parts) >= 2:
        return parts[0], " ".join(parts[1:])
    if len(parts) >= 6:
        return " ".join(parts[:5]), " ".join(parts[5:])
    return None


def _script_tokens(command: str) -> list[str]:
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    scripts: list[str] = []
    for token in tokens:
        clean = token.strip("'\"")
        if clean.startswith("-"):
            continue
        if clean.endswith(SCRIPT_EXTENSIONS):
            scripts.append(clean)
    return scripts


def parse_crontab(text: str) -> list[dict[str, Any]]:
    """Parse active crontab lines into schedule/command records."""
    entries: list[dict[str, Any]] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", line):
            continue
        parsed = _split_cron_line(line)
        if not parsed:
            continue
        schedule, command = parsed
        entries.append(
            {
                "line": lineno,
                "schedule": schedule,
                "command": command,
                "script_tokens": _script_tokens(command),
            }
        )
    return entries


def load_registry(
    path: Path = DEFAULT_REGISTRY,
    runtimes: set[str] | None = None,
) -> dict[str, Any]:
    """Load registry labels and owner modules from organs_registry.yaml.

    When ``runtimes`` is provided, only organs assigned to one of those
    runtime scopes are considered. This lets a Pro snapshot ignore Mini
    launchd labels that are valid elsewhere but absent on the current host.
    """
    if yaml is None:
        raise RuntimeError("PyYAML is required; run inside the repo virtualenv")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    organs = data.get("organs", data) if isinstance(data, dict) else data
    if not isinstance(organs, list):
        raise ValueError(f"Unsupported registry shape: {path}")

    labels: dict[str, dict[str, Any]] = {}
    modules: dict[str, dict[str, Any]] = {}
    cron_matches: dict[str, dict[str, Any]] = {}
    for organ in organs:
        if not isinstance(organ, dict):
            continue
        if runtimes and str(organ.get("runtime", "")) not in runtimes:
            continue
        organ_id = str(organ.get("id", ""))
        owner_module = str(organ.get("owner_module", "") or "")
        enabled = organ.get("enabled", True)
        if owner_module:
            modules[owner_module] = {
                "id": organ_id,
                "owner_module": owner_module,
                "enabled": enabled,
            }
            modules[Path(owner_module).name] = {
                "id": organ_id,
                "owner_module": owner_module,
                "enabled": enabled,
            }
        raw_cron_match = organ.get("cron_match") or []
        if isinstance(raw_cron_match, str):
            raw_cron_match = [raw_cron_match]
        if isinstance(raw_cron_match, list):
            for match in raw_cron_match:
                if not isinstance(match, str) or not match:
                    continue
                cron_matches[match] = {
                    "id": organ_id,
                    "owner_module": owner_module,
                    "enabled": enabled,
                }
        recovery_params = organ.get("recovery_params") or {}
        label = recovery_params.get("label") if isinstance(recovery_params, dict) else None
        if label:
            labels[str(label)] = {
                "id": organ_id,
                "owner_module": owner_module,
                "runtime": organ.get("runtime"),
                "type": organ.get("type"),
                "enabled": organ.get("enabled", True),
            }
    return {
        "labels": labels,
        "modules": modules,
        "cron_matches": cron_matches,
        "organs": organs,
    }


def _cron_is_covered(
    entry: dict[str, Any],
    registry_labels: dict[str, dict[str, Any]],
    registry_modules: dict[str, dict[str, Any]],
    registry_cron_matches: dict[str, dict[str, Any]] | None = None,
) -> bool:
    command = entry["command"]
    if any(label in command for label in registry_labels):
        return True
    if registry_cron_matches and any(
        match in command for match in registry_cron_matches
    ):
        return True
    for token in entry.get("script_tokens", []):
        token_name = Path(token).name
        if token in registry_modules or token_name in registry_modules:
            return True
        for module in registry_modules:
            if module and (token == module or token.endswith(f"/{module}")):
                return True
    return False


def compare_runtime(
    registry: dict[str, Any],
    launchctl: dict[str, dict[str, Any]],
    plists: dict[str, dict[str, str]],
    cron: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return unmanaged/missing runtime records."""
    registry_labels = registry["labels"]
    registry_modules = registry["modules"]
    registry_cron_matches = registry.get("cron_matches", {})
    enabled_registry_labels = {
        label: value
        for label, value in registry_labels.items()
        if value.get("enabled", True)
    }
    disabled_registry_labels = {
        label: value
        for label, value in registry_labels.items()
        if not value.get("enabled", True)
    }
    enabled_registry_modules = {
        module: value
        for module, value in registry_modules.items()
        if value.get("enabled", True)
    }
    enabled_registry_cron_matches = {
        match: value
        for match, value in registry_cron_matches.items()
        if value.get("enabled", True)
    }
    disabled_registry_modules = {
        module: value
        for module, value in registry_modules.items()
        if not value.get("enabled", True)
    }
    disabled_registry_cron_matches = {
        match: value
        for match, value in registry_cron_matches.items()
        if not value.get("enabled", True)
    }

    unmanaged_launchctl = {
        label: value
        for label, value in sorted(launchctl.items())
        if label not in enabled_registry_labels and label not in disabled_registry_labels
    }
    unmanaged_plists = {
        label: value
        for label, value in sorted(plists.items())
        if label not in enabled_registry_labels and label not in disabled_registry_labels
    }
    disabled_registry_launchctl = {
        label: value
        for label, value in sorted(launchctl.items())
        if label in disabled_registry_labels
    }
    disabled_registry_plists = {
        label: value for label, value in sorted(plists.items()) if label in disabled_registry_labels
    }
    missing_loaded_labels = {
        label: value
        for label, value in sorted(enabled_registry_labels.items())
        if label not in launchctl
    }
    unmanaged_cron = [
        entry
        for entry in cron
        if not _cron_is_covered(
            entry,
            enabled_registry_labels,
            enabled_registry_modules,
            enabled_registry_cron_matches,
        )
        and not _cron_is_covered(
            entry,
            disabled_registry_labels,
            disabled_registry_modules,
            disabled_registry_cron_matches,
        )
    ]
    disabled_registry_cron = [
        entry
        for entry in cron
        if _cron_is_covered(
            entry,
            disabled_registry_labels,
            disabled_registry_modules,
            disabled_registry_cron_matches,
        )
        and not _cron_is_covered(
            entry,
            enabled_registry_labels,
            enabled_registry_modules,
            enabled_registry_cron_matches,
        )
    ]
    unmanaged_launchctl_running = {
        label: value for label, value in unmanaged_launchctl.items() if value.get("pid")
    }
    unmanaged_launchctl_failed = {
        label: value
        for label, value in unmanaged_launchctl.items()
        if not value.get("pid") and value.get("status") not in (None, 0)
    }
    unmanaged_launchctl_scheduled_ok = {
        label: value
        for label, value in unmanaged_launchctl.items()
        if not value.get("pid") and value.get("status") == 0
    }
    unmanaged_plist_only = {
        label: value for label, value in unmanaged_plists.items() if label not in launchctl
    }
    return {
        "summary": {
            "registry_labels": len(registry_labels),
            "launchctl_labels": len(launchctl),
            "plist_labels": len(plists),
            "cron_entries": len(cron),
            "unmanaged_launchctl": len(unmanaged_launchctl),
            "unmanaged_launchctl_running": len(unmanaged_launchctl_running),
            "unmanaged_launchctl_failed": len(unmanaged_launchctl_failed),
            "unmanaged_launchctl_scheduled_ok": len(unmanaged_launchctl_scheduled_ok),
            "unmanaged_plists": len(unmanaged_plists),
            "unmanaged_plist_only": len(unmanaged_plist_only),
            "unmanaged_cron": len(unmanaged_cron),
            "disabled_registry_launchctl": len(disabled_registry_launchctl),
            "disabled_registry_plists": len(disabled_registry_plists),
            "disabled_registry_cron": len(disabled_registry_cron),
            "missing_loaded_labels": len(missing_loaded_labels),
        },
        "unmanaged_launchctl": unmanaged_launchctl,
        "unmanaged_launchctl_running": unmanaged_launchctl_running,
        "unmanaged_launchctl_failed": unmanaged_launchctl_failed,
        "unmanaged_launchctl_scheduled_ok": unmanaged_launchctl_scheduled_ok,
        "unmanaged_plists": unmanaged_plists,
        "unmanaged_plist_only": unmanaged_plist_only,
        "unmanaged_cron": unmanaged_cron,
        "disabled_registry_launchctl": disabled_registry_launchctl,
        "disabled_registry_plists": disabled_registry_plists,
        "disabled_registry_cron": disabled_registry_cron,
        "missing_loaded_labels": missing_loaded_labels,
    }


def _run_text(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        return ""
    return result.stdout


def _read_text(path: str | None) -> str:
    if not path:
        return ""
    return Path(path).read_text(encoding="utf-8")


def _load_snapshot(args: argparse.Namespace) -> tuple[
    dict[str, dict[str, Any]], dict[str, dict[str, str]], list[dict[str, Any]]
]:
    launchctl_text = _read_text(args.launchctl_file)
    crontab_text = _read_text(args.crontab_file)
    plist_text = _read_text(args.plist_label_file)

    if not launchctl_text and not args.no_local_probe:
        launchctl_text = _run_text(["launchctl", "list"])
    if not crontab_text and not args.no_local_probe:
        crontab_text = _run_text(["crontab", "-l"])

    prefixes = tuple(args.prefix)
    launchctl = parse_launchctl_list(launchctl_text, prefixes)
    cron = parse_crontab(crontab_text)
    if plist_text:
        plists = parse_plist_label_listing(plist_text, prefixes)
    elif args.no_local_probe:
        plists = {}
    else:
        plists = parse_local_plists(Path(args.plist_dir).expanduser(), prefixes)
    return launchctl, plists, cron


def _limited_items(items: list[Any], limit: int) -> list[Any]:
    if limit < 0:
        return items
    return items[:limit]


def emit_markdown(diff: dict[str, Any], source: str, limit: int) -> str:
    lines = [f"# Live runtime vs organism genome - {source}", ""]
    lines.append("| Metric | Count |")
    lines.append("| --- | ---: |")
    for key, value in diff["summary"].items():
        lines.append(f"| {key} | {value} |")

    lines.extend(["", "## Unmanaged launchctl labels"])
    launch_items = [
        (label, value) for label, value in diff["unmanaged_launchctl"].items()
    ]
    if launch_items:
        for label, value in _limited_items(launch_items, limit):
            lines.append(
                f"- `{label}` pid={value.get('pid')} status={value.get('status')}"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## Unmanaged launchctl classification"])
    class_groups = [
        ("running", diff["unmanaged_launchctl_running"]),
        ("failed", diff["unmanaged_launchctl_failed"]),
        ("scheduled_ok", diff["unmanaged_launchctl_scheduled_ok"]),
    ]
    for name, group in class_groups:
        sample = ", ".join(f"`{label}`" for label in _limited_items(list(group), 10))
        lines.append(f"- {name}: {len(group)}" + (f" ({sample})" if sample else ""))

    lines.extend(["", "## Unmanaged plist labels"])
    plist_items = [(label, value) for label, value in diff["unmanaged_plists"].items()]
    if plist_items:
        for label, value in _limited_items(plist_items, limit):
            lines.append(f"- `{label}` source=`{value.get('source')}`")
    else:
        lines.append("- none")

    lines.extend(["", "## Unmanaged cron entries"])
    cron_items = diff["unmanaged_cron"]
    if cron_items:
        for entry in _limited_items(cron_items, limit):
            lines.append(
                f"- line {entry['line']} `{entry['schedule']}` -> `{entry['command']}`"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## Disabled registry entries still live"])
    disabled_launch_items = [
        (label, value) for label, value in diff["disabled_registry_launchctl"].items()
    ]
    disabled_plist_items = [
        (label, value) for label, value in diff["disabled_registry_plists"].items()
    ]
    disabled_cron_items = diff["disabled_registry_cron"]
    if not disabled_launch_items and not disabled_plist_items and not disabled_cron_items:
        lines.append("- none")
    for label, value in _limited_items(disabled_launch_items, limit):
        lines.append(
            f"- launchctl `{label}` pid={value.get('pid')} status={value.get('status')}"
        )
    for label, value in _limited_items(disabled_plist_items, limit):
        lines.append(f"- plist `{label}` source=`{value.get('source')}`")
    for entry in _limited_items(disabled_cron_items, limit):
        lines.append(
            f"- cron line {entry['line']} `{entry['schedule']}` -> `{entry['command']}`"
        )

    lines.extend(["", "## Registry labels not loaded in snapshot"])
    missing_items = [
        (label, value) for label, value in diff["missing_loaded_labels"].items()
    ]
    if missing_items:
        for label, value in _limited_items(missing_items, limit):
            lines.append(
                f"- `{label}` organ=`{value.get('id')}` runtime=`{value.get('runtime')}`"
            )
    else:
        lines.append("- none")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--source", default=os.uname().nodename)
    parser.add_argument("--launchctl-file")
    parser.add_argument("--crontab-file")
    parser.add_argument("--plist-label-file")
    parser.add_argument("--plist-dir", default=str(Path.home() / "Library/LaunchAgents"))
    parser.add_argument("--prefix", action="append", default=list(DEFAULT_PREFIXES))
    parser.add_argument("--no-local-probe", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--fail-on-drift", action="store_true")
    parser.add_argument(
        "--runtime",
        action="append",
        help=(
            "Limit registry comparison to one runtime scope; repeat for "
            "multiple runtimes, e.g. --runtime pro_launchd"
        ),
    )
    args = parser.parse_args(argv)

    runtimes = set(args.runtime or []) or None
    registry = load_registry(Path(args.registry), runtimes=runtimes)
    launchctl, plists, cron = _load_snapshot(args)
    diff = compare_runtime(registry, launchctl, plists, cron)

    if args.json:
        print(json.dumps(diff, indent=2, sort_keys=True))
    else:
        print(emit_markdown(diff, args.source, args.limit))

    drift = (
        diff["summary"]["unmanaged_launchctl"]
        + diff["summary"]["unmanaged_plists"]
        + diff["summary"]["unmanaged_cron"]
        + diff["summary"]["disabled_registry_launchctl"]
        + diff["summary"]["disabled_registry_plists"]
        + diff["summary"]["disabled_registry_cron"]
    )
    return 1 if args.fail_on_drift and drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
