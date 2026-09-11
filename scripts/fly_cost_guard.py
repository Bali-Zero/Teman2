#!/usr/bin/env python3
"""Fly.io weekly resource guard — billable inventory against hard ceilings.

Fly exposes no supported billing API, so spend is guarded by INVENTORY: machine
count, started machine count, started memory and started CPUs (the compute cost
drivers), CPU kind (a performance CPU costs ~4x a shared one at equal core
count), provisioned volume GB and dedicated IPv4s across the expected apps.
Any finding makes the process exit non-zero so the workflow run goes RED — a
`::warning::` that leaves the job green is a guard that cannot sound (cicatrix
#2, Esiste≠Armato: the previous inline version had breached thresholds for
weeks and every run was "success").

The guard fails CLOSED on what it cannot read: a machine whose config, guest,
state, memory, CPU count or CPU kind is missing from flyctl's JSON, a volume
without a size, an IP without a type, a status without a machine list, or a
flyctl call that errors, is a finding — never a silent 0 that reads as savings.

Usage:
    fly_cost_guard.py                       # live: shells out to flyctl
    fly_cost_guard.py --inventory-json f    # offline: evaluate a captured inventory
    fly_cost_guard.py --dump-inventory      # live: print the inventory, no verdict
                                            # (fixture capture: redirect stdout)

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

# bites-observable — an `observe:` line may point at this script. Its arguments
# are integer ceilings, app names, a JSON path it only READS (--inventory-json)
# and a bare flag that prints to stdout (--dump-inventory): none can name a
# program to run (the only subprocess is the fixed `flyctl` on PATH), a file to
# write, or a database to reach. Keep it that way, or drop this marker.

DEFAULT_EXPECTED_APPS = "nuzantara-rag,nuzantara-postgres"
SHARED_CPU_KIND = "shared"

# Measured live 2026-09-10 (fly machine list / volumes list / ips list):
#   nuzantara-rag      4 machines (api 3072MB/2cpu, rag 2048MB/2cpu, drive
#                      1024MB/1cpu x2 — one stopped standby), 2x1GB volumes,
#                      0 dedicated IPv4
#   nuzantara-postgres 3 machines x 2048MB/2cpu, 3x25GB volumes (77 GB total
#                      with the two 1 GB rag volumes), 0 dedicated IPv4
#   all 7 machines shared-cpu (re-probed 2026-09-09T19:45Z)
# Ceilings sit AT today's footprint: one more machine, one started standby, one
# extra GB of RAM, one extra shared CPU (a shared-cpu-4x upgrade keeps the RAM
# figure and doubles the compute bill), one extended volume or one paid IPv4
# turns the run red. CPU kind has no ceiling: any machine that is not
# shared-cpu is a finding on its own, because a performance CPU at the SAME
# core count is invisible to every other counter.
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


class InventoryShapeError(ValueError):
    """flyctl's JSON lacks a field the guard bills on — a finding, never a 0."""


def fly_json(*args: str) -> Any:
    result = subprocess.run(
        ["flyctl", *args, "--json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _require(container: Any, key: str, where: str) -> Any:
    """The field must be present and non-null; anything else names itself."""
    if not isinstance(container, dict) or container.get(key) is None:
        raise InventoryShapeError(f"missing {key} on {where}")
    return container[key]


def _int_or_none(value: Any) -> int | None:
    """An unparsable field stays None so evaluate() can name it."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _machine_row(machine: dict[str, Any]) -> dict[str, Any]:
    where = f"machine {machine.get('id')}"
    config = _require(machine, "config", where)
    guest = _require(config, "guest", where)
    metadata = config.get("metadata") or {}
    return {
        "id": machine.get("id"),
        "state": _require(machine, "state", where),
        "memory_mb": _int_or_none(_require(guest, "memory_mb", where)),
        "cpus": _int_or_none(_require(guest, "cpus", where)),
        "cpu_kind": _require(guest, "cpu_kind", where),
        "group": metadata.get("fly_process_group"),
    }


def _volume_row(volume: dict[str, Any]) -> dict[str, Any]:
    where = f"volume {volume.get('id')}"
    return {
        "id": volume.get("id"),
        "size_gb": _int_or_none(_require(volume, "size_gb", where)),
    }


def _ip_row(ip: dict[str, Any]) -> dict[str, Any]:
    # Type is "v4" for a paid dedicated IPv4, "shared_v4" for the free one.
    return {"type": _require(ip, "Type", f"ip {ip.get('ID')}")}


def _named(app: str, resource: str, exc: Exception) -> str:
    text = f"{app}:{resource}:{type(exc).__name__}"
    if isinstance(exc, InventoryShapeError):
        text += f":{exc}"
    return text


def collect_inventory() -> dict[str, Any]:
    """Shell out to flyctl once per app/resource; errors are recorded, never fatal.

    A partial inventory must still be judged: a flyctl hiccup on one app is a
    FINDING (inventory errors), not a silent "0 machines" that reads as savings.
    The same holds for the app listing itself: when it fails, every expected app
    is reported missing and the error is named, instead of a traceback that
    leaves the Telegram step with no report. A shape error (a billable field
    missing from the JSON) drops that app's listing for that resource WHOLE and
    names the field, so the report cannot quietly under-count.
    """
    inventory: dict[str, Any] = {"apps": {}, "errors": []}
    try:
        apps = fly_json("apps", "list")
    except Exception as exc:  # noqa: BLE001 — a failed listing is a finding
        inventory["errors"].append(_named("apps", "list", exc))
        return inventory
    app_names = sorted({app.get("Name") or app.get("ID") for app in apps} - {None})
    for app in app_names:
        entry: dict[str, Any] = {"machines": [], "volumes": [], "ips": []}
        try:
            status = fly_json("status", "--app", app)
            machines = _require(status, "Machines", f"status of {app}")
            entry["machines"] = [_machine_row(m) for m in machines]
        except Exception as exc:  # noqa: BLE001 — flyctl/JSON/shape failures are findings
            entry["machines"] = []
            inventory["errors"].append(_named(app, "status", exc))
        try:
            entry["volumes"] = [
                _volume_row(v) for v in fly_json("volumes", "list", "--app", app)
            ]
        except Exception as exc:  # noqa: BLE001
            entry["volumes"] = []
            inventory["errors"].append(_named(app, "volumes", exc))
        try:
            entry["ips"] = [_ip_row(ip) for ip in fly_json("ips", "list", "--app", app)]
        except Exception as exc:  # noqa: BLE001
            entry["ips"] = []
            inventory["errors"].append(_named(app, "ips", exc))
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
    started_cpus_by_kind: dict[str, int] = {}
    non_shared: list[str] = []
    errors = list(inventory.get("errors") or [])
    for app, entry in apps.items():
        for m in entry.get("machines") or []:
            machine_count += 1
            kind = m.get("cpu_kind")
            # None counts: a machine whose kind cannot be read is not shared-cpu
            # until proven so — the kind is what a same-core-count upgrade changes.
            if kind != SHARED_CPU_KIND:
                non_shared.append(f"{m.get('id')}:{kind}")
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
                    label = kind if isinstance(kind, str) else "unknown"
                    started_cpus_by_kind[label] = (
                        started_cpus_by_kind.get(label, 0) + value
                    )
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
    if non_shared:
        findings.append("non-shared cpu=" + ",".join(non_shared))
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

    kinds = ",".join(f"{k}={n}" for k, n in sorted(started_cpus_by_kind.items()))
    report = (
        f"Apps: {len(app_names)} | Machines: {started_count}/{machine_count} started "
        f"(limit {limits['started_machines']}/{limits['machines']}) | "
        f"Started RAM: {started_memory_mb} MB (limit {limits['started_memory_mb']}) | "
        f"Started CPUs: {started_cpus} (limit {limits['started_cpus']}) [{kinds}] | "
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
        "--dump-inventory",
        action="store_true",
        help="print the inventory JSON to stdout and exit 0 without judging it",
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
        print(json.dumps(inventory, indent=2, sort_keys=True))
        return 0

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
