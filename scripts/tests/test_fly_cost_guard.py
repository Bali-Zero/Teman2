"""Guilt / innocence tests for scripts/fly_cost_guard.py.

Innocence: the inventory captured live on 2026-09-10 passes the ceilings the
workflow ships with. Guilt: every ceiling, breached by exactly one unit, turns
into a named finding AND a non-zero exit — a guard that only warns is not a
guard (cicatrix #2).
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "fly_cost_guard.py"
WORKFLOW = ROOT / ".github" / "workflows" / "cron-fly-cost-alert.yml"
FIXTURE = ROOT / "scripts" / "tests" / "fixtures" / "fly_inventory_2026-09-10.json"

sys.path.insert(0, str(ROOT / "scripts"))

import fly_cost_guard  # noqa: E402

EXPECTED = {"nuzantara-rag", "nuzantara-postgres"}


def _inventory() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _workflow_limits() -> dict[str, int]:
    env = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["run"]["env"]
    return fly_cost_guard.limits_from_env({k: str(v) for k, v in env.items()})


def test_workflow_ceilings_match_script_defaults() -> None:
    assert _workflow_limits() == fly_cost_guard.DEFAULT_LIMITS


def test_workflow_calls_the_script_and_checks_it_out() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "python3 scripts/fly_cost_guard.py" in text
    assert "actions/checkout@" in text
    assert "python3 <<'PY'" not in text, "inline guard resurrected"
    assert "flyctl bills view" not in text
    assert "Current month cost" not in text


def test_live_fixture_is_innocent_under_workflow_ceilings() -> None:
    report, findings = fly_cost_guard.evaluate(
        _inventory(), EXPECTED, _workflow_limits()
    )
    assert findings == []
    assert report.startswith("Apps: 2 | Machines: 6/7 started (limit 6/7)")
    assert "Started RAM: 12288 MB (limit 12288)" in report
    assert "Started CPUs: 11 (limit 11) [shared=11]" in report
    assert "Volumes: 77 GB (limit 77)" in report
    assert "Dedicated IPv4: 0 (limit 0)" in report
    assert all(
        m["cpu_kind"] == "shared"
        for entry in _inventory()["apps"].values()
        for m in entry["machines"]
    ), "the live fixture must carry cpu_kind on every machine"


def test_one_more_machine_is_guilty() -> None:
    inv = _inventory()
    inv["apps"]["nuzantara-rag"]["machines"].append(
        {
            "id": "extra",
            "state": "stopped",
            "memory_mb": 256,
            "cpus": 1,
            "cpu_kind": "shared",
            "group": "api",
        }
    )
    _, findings = fly_cost_guard.evaluate(inv, EXPECTED, _workflow_limits())
    assert findings == ["machines 8>7"]


def test_performance_cpu_is_guilty() -> None:
    """A performance CPU at the SAME core count breaches no counter — it is a
    finding on its own. Guilt: switch the rag machine's kind; then strip the
    kind entirely (None is not shared until proven so). Innocence is the live
    fixture above: 7/7 shared, no finding."""
    inv = _inventory()
    rag = next(
        m for m in inv["apps"]["nuzantara-rag"]["machines"] if m["group"] == "rag"
    )
    rag["cpu_kind"] = "performance"
    report, findings = fly_cost_guard.evaluate(inv, EXPECTED, _workflow_limits())
    assert findings == ["non-shared cpu=1781e5eda03438:performance"]
    assert "Started CPUs: 11 (limit 11) [performance=2,shared=9]" in report

    del rag["cpu_kind"]
    report, findings = fly_cost_guard.evaluate(inv, EXPECTED, _workflow_limits())
    assert findings == ["non-shared cpu=1781e5eda03438:None"]
    assert "[shared=9,unknown=2]" in report


def test_started_standby_is_guilty_on_count_and_memory() -> None:
    inv = _inventory()
    standby = next(
        m for m in inv["apps"]["nuzantara-rag"]["machines"] if m["state"] == "stopped"
    )
    standby["state"] = "started"
    _, findings = fly_cost_guard.evaluate(inv, EXPECTED, _workflow_limits())
    assert findings == [
        "started machines 7>6",
        "started memory 13312MB>12288MB",
        "started cpus 12>11",
    ]


def test_one_more_gb_of_ram_is_guilty() -> None:
    inv = _inventory()
    rag = next(
        m for m in inv["apps"]["nuzantara-rag"]["machines"] if m["group"] == "rag"
    )
    rag["memory_mb"] += 1024
    _, findings = fly_cost_guard.evaluate(inv, EXPECTED, _workflow_limits())
    assert findings == ["started memory 13312MB>12288MB"]


def test_one_more_started_cpu_is_guilty() -> None:
    inv = _inventory()
    rag = next(
        m for m in inv["apps"]["nuzantara-rag"]["machines"] if m["group"] == "rag"
    )
    rag["cpus"] += 1
    _, findings = fly_cost_guard.evaluate(inv, EXPECTED, _workflow_limits())
    assert findings == ["started cpus 12>11"]


def test_missing_sizes_fail_closed_only_on_what_is_billed() -> None:
    """A started machine or a volume with no readable size is a finding.

    Innocence: the stopped standby carries no size and stays silent — a
    stopped machine is not billed for compute. Guilt: strip the size from a
    started machine and from a volume; neither may read as 0 (= savings).
    """
    inv = _inventory()
    standby = next(
        m for m in inv["apps"]["nuzantara-rag"]["machines"] if m["state"] == "stopped"
    )
    standby["memory_mb"] = None
    del standby["cpus"]
    _, findings = fly_cost_guard.evaluate(inv, EXPECTED, _workflow_limits())
    assert findings == []

    api = next(
        m for m in inv["apps"]["nuzantara-rag"]["machines"] if m["group"] == "api"
    )
    api["memory_mb"] = None
    del api["cpus"]
    volume = inv["apps"]["nuzantara-postgres"]["volumes"][0]
    volume["size_gb"] = "25"  # a string is not a size the guard will add up
    report, findings = fly_cost_guard.evaluate(inv, EXPECTED, _workflow_limits())
    assert findings == [
        "inventory errors="
        f"nuzantara-postgres:volume {volume['id']}:size_gb missing,"
        f"nuzantara-rag:machine {api['id']}:memory_mb missing,"
        f"nuzantara-rag:machine {api['id']}:cpus missing"
    ]
    assert "Started RAM: 9216 MB" in report  # 12288 minus the unreadable 3072
    assert "Volumes: 52 GB" in report


def test_extended_volume_is_guilty() -> None:
    inv = _inventory()
    inv["apps"]["nuzantara-postgres"]["volumes"][0]["size_gb"] += 1
    _, findings = fly_cost_guard.evaluate(inv, EXPECTED, _workflow_limits())
    assert findings == ["volumes 78GB>77GB"]


def test_paid_ipv4_is_guilty_but_shared_ipv4_is_not() -> None:
    inv = _inventory()
    assert any(ip["type"] == "shared_v4" for ip in inv["apps"]["nuzantara-rag"]["ips"])
    _, findings = fly_cost_guard.evaluate(inv, EXPECTED, _workflow_limits())
    assert findings == []
    inv["apps"]["nuzantara-rag"]["ips"].append({"type": "v4"})
    _, findings = fly_cost_guard.evaluate(inv, EXPECTED, _workflow_limits())
    assert findings == ["dedicated IPv4 1>0"]


def test_unexpected_missing_apps_and_inventory_errors_are_findings() -> None:
    inv = _inventory()
    inv["apps"]["fly-builder-legacy"] = {"machines": [], "volumes": [], "ips": []}
    del inv["apps"]["nuzantara-postgres"]
    inv["errors"] = ["nuzantara-rag:ips:CalledProcessError"]
    _, findings = fly_cost_guard.evaluate(inv, EXPECTED, _workflow_limits())
    assert findings == [
        "unexpected apps=fly-builder-legacy",
        "missing apps=nuzantara-postgres",
        "inventory errors=nuzantara-rag:ips:CalledProcessError",
    ]


def _run(
    args: list[str], env_extra: dict[str, str], cwd: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env={**os.environ, **env_extra},
        cwd=cwd,
    )


def test_cli_exit_code_is_the_verdict(tmp_path: Path) -> None:
    output = tmp_path / "github-output"
    env = {"GITHUB_OUTPUT": str(output)}
    innocent = _run(["--inventory-json", str(FIXTURE)], env, tmp_path)
    assert innocent.returncode == 0, innocent.stderr
    assert "within limits" in innocent.stdout

    guilty_inv = copy.deepcopy(_inventory())
    guilty_inv["apps"]["nuzantara-postgres"]["volumes"][0]["size_gb"] = 26
    guilty_path = tmp_path / "guilty.json"
    guilty_path.write_text(json.dumps(guilty_inv), encoding="utf-8")
    guilty = _run(["--inventory-json", str(guilty_path)], env, tmp_path)
    assert guilty.returncode == 1
    assert "::error::Fly resource guard: volumes 78GB>77GB" in guilty.stdout
    github_output = output.read_text(encoding="utf-8")
    assert "alert<<EOF\n\nEOF" in github_output  # innocent run wrote an empty alert
    assert "alert<<EOF\nvolumes 78GB>77GB\nEOF" in github_output


def test_env_ceilings_override_defaults_and_flags_override_env(tmp_path: Path) -> None:
    tight = _run(
        ["--inventory-json", str(FIXTURE)], {"MAX_TOTAL_VOLUME_GB": "76"}, tmp_path
    )
    assert tight.returncode == 1
    assert "volumes 77GB>76GB" in tight.stdout
    relaxed = _run(
        ["--inventory-json", str(FIXTURE), "--max-volume-gb", "77"],
        {"MAX_TOTAL_VOLUME_GB": "76"},
        tmp_path,
    )
    assert relaxed.returncode == 0, relaxed.stdout


FAKE_FLYCTL = """#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
app = args[args.index("--app") + 1] if "--app" in args else None
if args[:2] == ["apps", "list"]:
    if os.environ.get("FAKE_FLYCTL_APPS_LIST_FAILS"):
        raise SystemExit(2)
    data = [{"Name": "nuzantara-rag"}, {"Name": "nuzantara-postgres"}, {"Name": "fly-builder-legacy"}]
elif args[0] == "status":
    counts = {
        "nuzantara-rag": ["started", "started", "started", "stopped"],
        "nuzantara-postgres": ["started", "started"],
        "fly-builder-legacy": ["stopped"],
    }
    data = {"Machines": [
        {"id": f"{app}-{i}", "state": state,
         "config": {"guest": {"memory_mb": 2048, "cpus": 2, "cpu_kind": "shared"},
                    "metadata": {"fly_process_group": "app"}}}
        for i, state in enumerate(counts[app])
    ]}
    for machine in data["Machines"]:
        if machine["id"] == os.environ.get("FAKE_FLYCTL_DROP_MEMORY_MB_ON"):
            del machine["config"]["guest"]["memory_mb"]
elif args[:2] == ["volumes", "list"]:
    sizes = {"nuzantara-rag": [1, 1], "nuzantara-postgres": [25, 25], "fly-builder-legacy": [50]}
    data = [{"id": f"vol{i}", "size_gb": size} for i, size in enumerate(sizes[app])]
    for volume in data:
        if f"{app}:{volume['id']}" == os.environ.get("FAKE_FLYCTL_DROP_SIZE_GB_ON"):
            del volume["size_gb"]
elif args[:2] == ["ips", "list"]:
    data = [{"Type": "v4"}, {"Type": "shared_v4"}] if app == "nuzantara-rag" else []
else:
    raise SystemExit(f"unexpected flyctl args: {args}")
print(json.dumps(data))
"""


def _install_fake_flyctl(tmp_path: Path) -> None:
    fake_flyctl = tmp_path / "flyctl"
    fake_flyctl.write_text(FAKE_FLYCTL, encoding="utf-8")
    fake_flyctl.chmod(fake_flyctl.stat().st_mode | stat.S_IXUSR)


def test_collection_through_a_fake_flyctl_replaying_the_observed_json_shapes(
    tmp_path: Path,
) -> None:
    """A FAKE flyctl on PATH, replaying the shapes observed 2026-09-10.

    This proves the collector's parsing of those shapes and the end-to-end
    exit code — it does not prove flyctl still emits them (only the live
    weekly run does). Shapes: `status` nests guest memory/cpus under
    config.guest, `ips list` reports the free shared IPv4 as Type "shared_v4"
    and a paid one as "v4".
    """
    _install_fake_flyctl(tmp_path)
    env = {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "MAX_TOTAL_MACHINES": "6",
        "MAX_TOTAL_VOLUME_GB": "60",
    }
    result = _run([], env, tmp_path)
    assert result.returncode == 1
    assert "Apps: 3 | Machines: 5/7 started" in result.stdout
    assert "Started RAM: 10240 MB" in result.stdout
    assert "Started CPUs: 10 (limit 11) [shared=10]" in result.stdout
    assert "Volumes: 102 GB" in result.stdout
    for finding in (
        "unexpected apps=fly-builder-legacy",
        "machines 7>6",
        "volumes 102GB>60GB",
        "dedicated IPv4 1>0",
    ):
        assert finding in result.stdout
    # `--dump-inventory` is a bare flag: the inventory goes to stdout and the
    # run does not judge (exit 0 on the same guilty footprint), so the script's
    # argument surface never names a file to write (bites-observable marker).
    dump = _run(["--dump-inventory"], env, tmp_path)
    assert dump.returncode == 0, dump.stderr
    captured = json.loads(dump.stdout)
    assert "::error::" not in dump.stdout
    assert captured["apps"]["nuzantara-rag"]["ips"] == [
        {"type": "v4"},
        {"type": "shared_v4"},
    ]
    assert captured["apps"]["nuzantara-rag"]["machines"][0]["cpu_kind"] == "shared"
    assert captured["errors"] == []


def test_missing_billable_field_is_an_inventory_error_not_zero(tmp_path: Path) -> None:
    """flyctl JSON without a field the guard bills on drops that app's listing
    for that resource WHOLE and names the field — never a 0 that reads as
    savings. Guilt: no memory_mb on a started Postgres machine, no size_gb on
    a rag volume. Innocence: the untouched fake above records no error."""
    _install_fake_flyctl(tmp_path)
    env = {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "FAKE_FLYCTL_DROP_MEMORY_MB_ON": "nuzantara-postgres-0",
        "FAKE_FLYCTL_DROP_SIZE_GB_ON": "nuzantara-rag:vol0",
    }
    result = _run([], env, tmp_path)
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert (
        "nuzantara-postgres:status:InventoryShapeError:"
        "missing memory_mb on machine nuzantara-postgres-0" in result.stdout
    )
    assert (
        "nuzantara-rag:volumes:InventoryShapeError:missing size_gb on volume vol0"
        in result.stdout
    )
    # rag 4 machines (3 started) + legacy 1 stopped; the 2 pg machines are gone.
    assert "Machines: 3/5 started" in result.stdout
    # pg 25+25 + legacy 50; the two 1 GB rag volumes are gone.
    assert "Volumes: 100 GB" in result.stdout
    captured = json.loads(_run(["--dump-inventory"], env, tmp_path).stdout)
    assert captured["apps"]["nuzantara-postgres"]["machines"] == []
    assert captured["apps"]["nuzantara-rag"]["volumes"] == []
    assert len(captured["errors"]) == 2


def test_failed_app_listing_is_a_finding_with_a_report(tmp_path: Path) -> None:
    """`flyctl apps list` failing must not crash past the report: every expected
    app reads as missing, the error is named, exit is 1 and the Telegram step
    still gets a report line."""
    _install_fake_flyctl(tmp_path)
    output = tmp_path / "github-output"
    result = _run(
        [],
        {
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "FAKE_FLYCTL_APPS_LIST_FAILS": "1",
            "GITHUB_OUTPUT": str(output),
        },
        tmp_path,
    )
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "missing apps=nuzantara-postgres,nuzantara-rag" in result.stdout
    assert "inventory errors=apps:list:CalledProcessError" in result.stdout
    assert "report<<EOF\nApps: 0 | Machines: 0/0 started" in output.read_text(
        encoding="utf-8"
    )
