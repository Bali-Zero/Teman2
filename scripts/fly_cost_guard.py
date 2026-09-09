#!/usr/bin/env python3
"""Fly.io weekly resource guard — billable inventory against hard ceilings.

Fly exposes no supported billing API, so spend is guarded by INVENTORY: machine
count, started machine count, started memory and started CPUs (the compute cost
drivers), provisioned volume GB and dedicated IPv4s across the expected apps.
Any finding makes the process exit non-zero so the workflow run goes RED — a
`::warning::` that leaves the job green is a guard that cannot sound (cicatrix
#2, Esiste≠Armato: the previous inline version had breached thresholds for
weeks and every run was "success").

The guard fails CLOSED on what it cannot read: a started machine whose memory
or CPU count is missing from flyctl's JSON, a volume without a size, or a
flyctl call that errors, is a finding — never a silent 0 that reads as savings.

Usage:
    fly_cost_guard.py                       # live: shells out to flyctl
    fly_cost_guard.py --inventory-json f    # offline: evaluate a captured inventory
    fly_cost_guard.py --dump-inventory f    # live: also write the inventory (fixture capture)

Thresholds come from env (MAX_*), matching the workflow's `env:` block, or from
the --max-* flags. The report/alert lines are appended to $GITHUB_OUTPUT when
set, so the Telegram step keeps working unchanged.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Any

DEFAULT_EXPECTED_APPS = "nuzantara-rag,nuzantara-postgres"

# Measured live 2026-09-10 (fly machine list / volumes list / ips list):
#   nuzantara-rag      4 machines (api 3072MB/2cpu, rag 2048MB/2cpu, drive
#                      1024MB/1cpu x2 — one stopped standby), 2x1GB volumes,
#                      0 dedicated IPv4
#   nuzantara-postgres 3 machines x 2048MB/2cpu, 3x25GB volumes (77 GB total
#                      with the two 1 GB rag volumes), 0 dedicated IPv4
# Ceilings sit AT today's footprint: one more machine, one started standby, one
# extra GB of RAM, one extra shared CPU (a shared-cpu-4x upgrade keeps the RAM
# figure and doubles the compute bill), one extended volume or one paid IPv4
# turns the run red.
DEFAULT_LIMITS: dict[str, int] = {
    "machines": 7,
    "started_machines": 6,
    "started_memory_mb": 12288,
    "started_cpus": 11,
    "volume_gb": 77,
    "dedicated_ipv4": 0,
}

LIMIT_ENV = {
    "machines": "MAX_TOTAL_MACHINES",
    "started_machines": "MAX_STARTED_MACHINES",
    "started_memory_mb": "MAX_STARTED_MEMORY_MB",
    "started_cpus": "MAX_STARTED_CPUS",
    "volume_gb": "MAX_TOTAL_VOLUME_GB",
    "dedicated_ipv4": "MAX_DEDICATED_IPV4",
}


def fly_json(*args: str) -> Any:
    result = subprocess.run(
        ["flyctl", *args, "--json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _int_or_none(value: Any) -> int | None:
    """A missing or unparsable field stays None so evaluate() can name it."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _machine_row(machine: dict[str, Any]) -> dict[str, Any]:
    config = machine.get("config") or {}
    guest = config.get("guest") or {}
    metadata = config.get("metadata") or {}
    return {
        "id": machine.get("id"),
        "state": machine.get("state"),
        "memory_mb": _int_or_none(guest.get("memory_mb")),
        "cpus": _int_or_none(guest.get("cpus")),
        "group": metadata.get("fly_process_group"),
    }


def collect_inventory() -> dict[str, Any]:
    """Shell out to flyctl once per app/resource; errors are recorded, never fatal.

    A partial inventory must still be judged: a flyctl hiccup on one app is a
    FINDING (inventory errors), not a silent "0 machines" that reads as savings.
    The same holds for the app listing itself: when it fails, every expected app
    is reported missing and the error is named, instead of a traceback that
    leaves the Telegram step with no report.
    """
    inventory: dict[str, Any] = {"apps": {}, "errors": []}
    try:
        apps = fly_json("apps", "list")
    except Exception as exc:  # noqa: BLE001 — a failed listing is a finding
        inventory["errors"].append(f"apps:list:{type(exc).__name__}")
        return inventory
    app_names = sorted({app.get("Name") or app.get("ID") for app in apps} - {None})
    for app in app_names:
        entry: dict[str, Any] = {"machines": [], "volumes": [], "ips": []}
        try:
            status = fly_json("status", "--app", app)
            entry["machines"] = [_machine_row(m) for m in status.get("Machines") or []]
        except Exception as exc:  # noqa: BLE001 — flyctl/JSON failures are findings
            inventory["errors"].append(f"{app}:status:{type(exc).__name__}")
        try:
            volumes = fly_json("volumes", "list", "--app", app)
            entry["volumes"] = [
                {"id": v.get("id"), "size_gb": _int_or_none(v.get("size_gb"))}
                for v in volumes
            ]
        except Exception as exc:  # noqa: BLE001
            inventory["errors"].append(f"{app}:volumes:{type(exc).__name__}")
        try:
            addresses = fly_json("ips", "list", "--app", app)
            # Type is "v4" for a paid dedicated IPv4, "shared_v4" for the free one.
            entry["ips"] = [{"type": ip.get("Type")} for ip in addresses]
        except Exception as exc:  # noqa: BLE001
            inventory["errors"].append(f"{app}:ips:{type(exc).__name__}")
        inventory["apps"][app] = entry
    return inventory


def evaluate(
    inventory: dict[str, Any],
    expected_apps: set[str],
    limits: dict[str, int],
) -> tuple[str, list[str]]:
    """Pure judgement: (report line, findings). Empty findings == innocent."""
    apps = inventory.get("apps") or {}
    app_names = set(apps)
    machine_count = started_count = started_memory_mb = started_cpus = 0
    volume_gb = dedicated_ipv4 = 0
    errors = list(inventory.get("errors") or [])
    for app, entry in apps.items():
        for m in entry.get("machines") or []:
            machine_count += 1
            if m.get("state") != "started":
                continue
            started_count += 1
            # Fail closed: a started machine with no readable size is a finding,
            # not a free machine. `or 0` here would let a flyctl schema change
            # report every started machine as costing nothing.
            for field in ("memory_mb", "cpus"):
                value = m.get(field)
                if not isinstance(value, int) or value <= 0:
                    errors.append(f"{app}:machine {m.get('id')}:{field} missing")
                    continue
                if field == "memory_mb":
                    started_memory_mb += value
                else:
                    started_cpus += value
        for v in entry.get("volumes") or []:
            size = v.get("size_gb")
            if not isinstance(size, int) or size <= 0:
                errors.append(f"{app}:volume {v.get('id')}:size_gb missing")
                continue
            volume_gb += size
        dedicated_ipv4 += sum(ip.get("type") == "v4" for ip in entry.get("ips") or [])

    findings: list[str] = []
    unexpected_apps = sorted(app_names - expected_apps)
    missing_apps = sorted(expected_apps - app_names)
    if unexpected_apps:
        findings.append("unexpected apps=" + ",".join(unexpected_apps))
    if missing_apps:
        findings.append("missing apps=" + ",".join(missing_apps))
    if machine_count > limits["machines"]:
        findings.append(f"machines {machine_count}>{limits['machines']}")
    if started_count > limits["started_machines"]:
        findings.append(
            f"started machines {started_count}>{limits['started_machines']}"
        )
    if started_memory_mb > limits["started_memory_mb"]:
        findings.append(
            f"started memory {started_memory_mb}MB>{limits['started_memory_mb']}MB"
        )
    if started_cpus > limits["started_cpus"]:
        findings.append(f"started cpus {started_cpus}>{limits['started_cpus']}")
    if volume_gb > limits["volume_gb"]:
        findings.append(f"volumes {volume_gb}GB>{limits['volume_gb']}GB")
    if dedicated_ipv4 > limits["dedicated_ipv4"]:
        findings.append(f"dedicated IPv4 {dedicated_ipv4}>{limits['dedicated_ipv4']}")
    if errors:
        findings.append("inventory errors=" + ",".join(errors))

    report = (
        f"Apps: {len(app_names)} | Machines: {started_count}/{machine_count} started "
        f"(limit {limits['started_machines']}/{limits['machines']}) | "
        f"Started RAM: {started_memory_mb} MB (limit {limits['started_memory_mb']}) | "
        f"Started CPUs: {started_cpus} (limit {limits['started_cpus']}) | "
        f"Volumes: {volume_gb} GB (limit {limits['volume_gb']}) | "
        f"Dedicated IPv4: {dedicated_ipv4} (limit {limits['dedicated_ipv4']})"
    )
    return report, findings


def limits_from_env(environ: dict[str, str]) -> dict[str, int]:
    return {
        key: int(environ.get(env_name, DEFAULT_LIMITS[key]))
        for key, env_name in LIMIT_ENV.items()
    }


def write_github_output(report: str, alert: str, path: str | None) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as output:
        output.write("report<<EOF\n" + report + "\nEOF\n")
        output.write("alert<<EOF\n" + alert + "\nEOF\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--inventory-json", help="evaluate this captured inventory instead of flyctl"
    )
    parser.add_argument(
        "--dump-inventory", help="write the live inventory to this path"
    )
    parser.add_argument(
        "--expected-apps",
        default=os.environ.get("EXPECTED_APPS", DEFAULT_EXPECTED_APPS),
        help="comma-separated app names that must exist and be the only ones",
    )
    for key, env_name in LIMIT_ENV.items():
        parser.add_argument(
            f"--max-{key.replace('_', '-')}",
            type=int,
            dest=key,
            help=f"overrides ${env_name}",
        )
    args = parser.parse_args(argv)

    limits = limits_from_env(dict(os.environ))
    for key in LIMIT_ENV:
        value = getattr(args, key)
        if value is not None:
            limits[key] = value
    expected = {name.strip() for name in args.expected_apps.split(",") if name.strip()}

    if args.inventory_json:
        with open(args.inventory_json, encoding="utf-8") as handle:
            inventory = json.load(handle)
    else:
        inventory = collect_inventory()
        if args.dump_inventory:
            with open(args.dump_inventory, "w", encoding="utf-8") as handle:
                json.dump(inventory, handle, indent=2, sort_keys=True)
                handle.write("\n")

    report, findings = evaluate(inventory, expected, limits)
    alert = "\n".join(findings)
    write_github_output(report, alert, os.environ.get("GITHUB_OUTPUT"))
    print(report)
    if findings:
        print("::error::Fly resource guard: " + "; ".join(findings))
        return 1
    print("Fly resource guard: within limits")
    return 0


if __name__ == "__main__":
    sys.exit(main())
