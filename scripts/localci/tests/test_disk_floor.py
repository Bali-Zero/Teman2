"""B6-4: pro.disk_floor — the organ that reads Pro's free space every 30 min and pages under the floor (scripts/ops/)."""
from __future__ import annotations

import json
import plistlib
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
ORGAN = ROOT / "scripts" / "ops" / "pro_disk_floor_tick.sh"
PLIST = ROOT / "infra" / "launchagents" / "com.nuzantara.disk-floor.plist"


def tick(tmp_path: Path, free_gb: float | None, host: str = "Nuzantara", **env) -> tuple[subprocess.CompletedProcess, dict, str]:
    bin_ = tmp_path / "bin"
    bin_.mkdir(exist_ok=True)
    kib = "" if free_gb is None else str(-(-int(free_gb * 1e9) // 1024))
    fakes = {"hostname": f"#!/bin/sh\necho {host}\n",
             "df": "#!/bin/sh\necho 'Filesystem 1024-blocks Used Available Capacity Mounted on'\n"
                   + (f"echo '/dev/disk3s5 1952560000 1000000000 {kib} 60% /System/Volumes/Data'\n" if kib else ""),
             "du": f'#!/bin/sh\necho "$*" >> {tmp_path / "du.calls"}\n'
                   f'printf "45020512\\t$HOME/.colima\\n44653328\\t$HOME/nuzantara\\n31567704\\t$HOME/Desktop\\n1024\\t$HOME/small\\n"\n'}
    for name, body in fakes.items():
        (bin_ / name).write_text(body)
        (bin_ / name).chmod(0o755)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    res = subprocess.run(["/bin/bash", str(ORGAN)], capture_output=True, text=True, timeout=60,
                         env={"HOME": str(home), "TMPDIR": str(tmp_path), "PATH": f"{bin_}:/usr/bin:/bin", **env})
    hb = json.loads((home / ".organism" / "last_seen" / "pro.disk_floor.json").read_text())
    return res, hb, (tmp_path / "du.calls").read_text() if (tmp_path / "du.calls").exists() else ""


@pytest.mark.parametrize("free,status", [(59, "error"), (59.9, "error"), (60, "warning"), (99, "warning"), (100, "warning"),
                                         (100.5, "ok"), (101, "ok")])
def test_ok_above_100_warning_from_60_to_100_failed_under_60(tmp_path, free, status):
    res, hb, du = tick(tmp_path, free)
    assert res.returncode == 0 and hb["status"] == status
    assert f"free_gb={free:.1f} on /System/Volumes/Data (ok > 100, failed < 60)" in hb["note"]
    assert hb["note"].startswith("failed: ") == (status == "error")
    if status == "ok":
        assert du == "" and "biggest" not in hb["note"]   # the 94-second walk only when the organ pages
    else:
        assert hb["note"].endswith("biggest: ~/.colima 46.1GB, ~/nuzantara 45.7GB, ~/Desktop 32.3GB")


def test_unreadable_free_space_is_an_error_never_ok(tmp_path):
    _, hb, _ = tick(tmp_path, None)
    assert hb["status"] == "error" and hb["note"].startswith("free space unreadable")


@pytest.mark.parametrize("host,env,note", [("Air-M5", {}, "wrong-node Air-M5"), ("Nuzantara", {"PRO_DISK_FLOOR_ENABLED": "false"}, "kill switch")])
def test_the_wrong_node_and_the_kill_switch_exit_visibly_disabled(tmp_path, host, env, note):
    _, hb, du = tick(tmp_path, 10, host=host, **env)
    assert hb["status"] == "disabled" and hb["note"] == note and du == ""


def test_the_plist_runs_the_live_copy_every_30_minutes_at_load_with_no_keepalive():
    pl = plistlib.loads(PLIST.read_bytes())
    assert pl["StartInterval"] == 1800 and pl["RunAtLoad"] is True and "KeepAlive" not in pl
    assert pl["ProgramArguments"] == ["/bin/bash", "/Users/nuzantara/.nuzantara-cron/pro_disk_floor_tick.sh"]
    pairs = json.loads((ROOT / "infra" / "home-fork" / "declared-pairs.json").read_text())["pairs"]
    assert {"~/.nuzantara-cron/pro_disk_floor_tick.sh", "~/Library/LaunchAgents/com.nuzantara.disk-floor.plist"} <= {
        p["live"] for p in pairs if p["repo"] in ("scripts/ops/pro_disk_floor_tick.sh", "infra/launchagents/com.nuzantara.disk-floor.plist")}


def test_a_previous_run_still_alive_is_a_warning_never_an_unread_ok(tmp_path):
    alive = subprocess.Popen(["sleep", "30"])
    (tmp_path / "nuzantara-pro-disk_floor.pid").write_text(str(alive.pid))
    try:
        _, hb, _ = tick(tmp_path, 200)
    finally:
        alive.kill()
        alive.wait()
    assert hb["status"] == "warning" and hb["note"].startswith("skipped: previous run alive")
