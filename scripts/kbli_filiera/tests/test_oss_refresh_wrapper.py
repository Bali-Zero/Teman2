"""Sandboxed runs of infra/launchagents/wrappers/kbli-oss-refresh-run.sh.

Fake HOME, stub loop / gateway / gtimeout, the real scripts/lib/heartbeat.py.
Proves the heartbeat is written on the OUTCOME (report present, parseable and
agreeing with the exit code), never on the exit code alone, on every path."""

from __future__ import annotations

import json
import os
import plistlib
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
WRAPPER = REPO / "infra" / "launchagents" / "wrappers" / "kbli-oss-refresh-run.sh"
PLIST = REPO / "infra" / "launchagents" / "com.nuzantara.kbli-oss-refresh.weekly.plist"
ORGAN = "test.kbli_oss_refresh"

STUB_LOOP = r'''
import json, os, sys
from pathlib import Path
Path(os.environ["STUB_MARK"]).write_text(" ".join(sys.argv[1:]))
out = Path(sys.argv[sys.argv.index("--out-root") + 1]) / "data/kbli-filiera/oss-refresh/2026-09-22.json"
rc = int(os.environ.get("STUB_RC", "0"))
if os.environ.get("STUB_NO_REPORT") != "1":
    out.parent.mkdir(parents=True, exist_ok=True)
    proposed = int(os.environ.get("STUB_PROPOSED", "0"))
    out.write_text(json.dumps({
        "exit_code": int(os.environ.get("STUB_REPORT_RC", rc)),
        "coverage": {"errors": int(os.environ.get("STUB_ERRORS", "0")), "deferred": 0},
        "counts": {"published": proposed, "changed": 0},
    }))
    print(f"OSS_REFRESH_REPORT={out}")
sys.exit(rc)
'''

STUB_GATEWAY = r'''
import os, sys
from pathlib import Path
Path(os.environ["STUB_GATEWAY_ARGV"]).write_text("\n".join(sys.argv[1:]))
print("tg_notify: logged")
'''


def _sandbox(tmp_path: Path) -> tuple[Path, dict]:
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "loop.py").write_text(STUB_LOOP)
    (bin_dir / "gateway.py").write_text(STUB_GATEWAY)
    gtimeout = bin_dir / "gtimeout"
    gtimeout.write_text('#!/bin/bash\nshift 3\nexec "$@"\n')  # drops `-k 30 <seconds>`
    gtimeout.chmod(0o755)
    env = {
        "HOME": str(home),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "KBLI_OSS_REFRESH_HOSTNAME": "mini-pro2",
        "KBLI_OSS_REFRESH_ORGAN_ID": ORGAN,
        "KBLI_OSS_REFRESH_LOOP_PY": sys.executable,
        "KBLI_OSS_REFRESH_LOOP": str(bin_dir / "loop.py"),
        "KBLI_OSS_REFRESH_HEARTBEAT_PY": sys.executable,
        "KBLI_OSS_REFRESH_HEARTBEAT": str(REPO / "scripts" / "lib" / "heartbeat.py"),
        "KBLI_OSS_REFRESH_REPORT_PY": sys.executable,
        "KBLI_OSS_REFRESH_GATEWAY_PY": sys.executable,
        "KBLI_OSS_REFRESH_GATEWAY": str(bin_dir / "gateway.py"),
        "KBLI_OSS_REFRESH_GTIMEOUT": str(gtimeout),
        "ORGANISM_LAST_SEEN_DIR": str(home / "last_seen"),
        "STUB_MARK": str(tmp_path / "loop.argv"),
        "STUB_GATEWAY_ARGV": str(tmp_path / "gateway.argv"),
    }
    return home, env


def _run(env: dict, **stub: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(WRAPPER)], env={**env, **stub}, capture_output=True, text=True)


def _heartbeat(home: Path) -> dict:
    return json.loads((home / "last_seen" / f"{ORGAN}.json").read_text())


def _gateway(tmp_path: Path) -> list[str]:
    """Gateway argv, or [] when the gateway was never invoked."""
    path = tmp_path / "gateway.argv"
    return path.read_text().splitlines() if path.exists() else []


def test_nothing_new_is_healthy_silence(tmp_path):
    home, env = _sandbox(tmp_path)
    proc = _run(env, STUB_RC="0")
    assert proc.returncode == 0, proc.stderr
    hb = _heartbeat(home)
    assert hb["status"] == "ok" and "result=nothing_new" in hb["note"]
    assert _gateway(tmp_path) == []
    argv = (tmp_path / "loop.argv").read_text()
    assert "--apply" in argv and f"--out-root {home}/nuzantara-vault-evidence/oss-refresh" in argv


def test_new_scopes_heartbeat_ok_and_digest(tmp_path):
    home, env = _sandbox(tmp_path)
    proc = _run(env, STUB_RC="1", STUB_PROPOSED="2")
    assert proc.returncode == 0, proc.stderr
    assert "result=new_scopes" in _heartbeat(home)["note"] and _heartbeat(home)["status"] == "ok"
    argv = _gateway(tmp_path)
    assert argv[argv.index("--tier") + 1] == "digest"
    assert any("NEW SCOPES PUBLISHED" in line for line in argv) and any("for 2 licensing-gap" in line for line in argv)


def test_partial_run_is_a_warning(tmp_path):
    home, env = _sandbox(tmp_path)
    _run(env, STUB_RC="0", STUB_ERRORS="3")
    hb = _heartbeat(home)
    assert hb["status"] == "warning" and "result=partial" in hb["note"]
    assert any("PARTIAL RUN" in line for line in _gateway(tmp_path))


@pytest.mark.parametrize("no_report", ["0", "1"])
def test_cannot_verify_is_a_warning_with_or_without_report(tmp_path, no_report):
    home, env = _sandbox(tmp_path)
    _run(env, STUB_RC="4", STUB_NO_REPORT=no_report)
    hb = _heartbeat(home)
    assert hb["status"] == "warning" and "result=cannot_verify" in hb["note"]


@pytest.mark.parametrize("stub", [
    {"STUB_RC": "0", "STUB_NO_REPORT": "1"},    # green exit, no report: the Esiste≠Armato shape
    {"STUB_RC": "0", "STUB_REPORT_RC": "1"},    # report disagrees with the exit code
    {"STUB_RC": "3"},                           # crash
])
def test_loop_failure_is_an_error_and_p0(tmp_path, stub):
    home, env = _sandbox(tmp_path)
    proc = _run(env, **stub)
    assert proc.returncode == 0, proc.stderr
    hb = _heartbeat(home)
    assert hb["status"] == "error" and "result=loop_failure" in hb["note"]
    argv = _gateway(tmp_path)
    assert argv[argv.index("--tier") + 1] == "p0"


def test_wrong_host_never_runs_the_loop(tmp_path):
    home, env = _sandbox(tmp_path)
    env["KBLI_OSS_REFRESH_HOSTNAME"] = "Nuzantara"
    _run(env)
    assert not (tmp_path / "loop.argv").exists()
    hb = _heartbeat(home)
    assert hb["status"] == "warning" and "result=cannot_verify" in hb["note"]


def test_kill_switch_writes_a_disabled_heartbeat(tmp_path):
    home, env = _sandbox(tmp_path)
    proc = _run(env, KBLI_OSS_REFRESH_ENABLED="false")
    assert proc.returncode == 0
    assert _heartbeat(home)["status"] == "disabled"
    assert not (tmp_path / "loop.argv").exists()


def test_the_log_names_key_presence_never_its_value(tmp_path):
    home, env = _sandbox(tmp_path)
    _run(env, STUB_RC="0", OSS_RBA_USER_KEY="sentinel-not-a-real-key")
    log = next((home / "logs" / "kbli-oss-refresh").glob("kbli-oss-refresh-*.log")).read_text()
    assert "user_key=present" in log and "sentinel-not-a-real-key" not in log


def test_plist_is_a_weekly_one_shot_through_cron_runner():
    d = plistlib.loads(PLIST.read_bytes())
    assert d["Label"] == "com.nuzantara.kbli-oss-refresh.weekly"
    assert d["ProgramArguments"][1:] == [
        "/Users/nuzantara/nuzantara/scripts/cron-runner.sh",
        "/Users/nuzantara/nuzantara/infra/launchagents/wrappers/kbli-oss-refresh-run.sh",
    ]
    assert set(d["StartCalendarInterval"]) == {"Weekday", "Hour", "Minute"}
    assert d["KeepAlive"] is False and d["RunAtLoad"] is False
    assert d["EnvironmentVariables"]["CRON_RUNNER_JOB_NAME"] == "kbli_oss_refresh"
    assert "OSS_RBA_USER_KEY" not in d["EnvironmentVariables"]
