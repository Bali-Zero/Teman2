"""Sandboxed run of scripts/mailbox_janitor_cron.sh: fake HOME, stub repo root
pointing at the real janitor, mailbox fixture under the fake HOME. Proves the
G2/G5 contract (heartbeat on every path, kill switch visible) and the exit map."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
WRAPPER = REPO / "scripts" / "mailbox_janitor_cron.sh"


def _sandbox(tmp_path: Path) -> tuple[Path, Path, dict]:
    home = tmp_path / "home"
    (home / ".nuzantara-mailbox" / "broadcast").mkdir(parents=True)
    stub_repo = tmp_path / "repo"
    (stub_repo / "scripts" / "lib").mkdir(parents=True)
    shutil.copy(REPO / "scripts" / "mailbox_janitor.py", stub_repo / "scripts" / "mailbox_janitor.py")
    shutil.copy(REPO / "scripts" / "lib" / "heartbeat.sh", stub_repo / "scripts" / "lib" / "heartbeat.sh")
    env = {
        "HOME": str(home),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "MAILBOX_JANITOR_REPO_ROOT": str(stub_repo),
        "MAILBOX_JANITOR_ORGAN_ID": "test.mailbox_janitor",
        "ORGANISM_LAST_SEEN_DIR": str(home / "last_seen"),
    }
    return home, stub_repo, env


def _run(env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(WRAPPER)], env=env, capture_output=True, text=True)


def _heartbeat(home: Path) -> dict:
    return json.loads((home / "last_seen" / "test.mailbox_janitor.json").read_text())


def test_apply_run_prunes_writes_receipt_and_ok_heartbeat(tmp_path):
    home, _, env = _sandbox(tmp_path)
    sess = home / ".nuzantara-mailbox" / "sess-old"
    sess.mkdir()
    old = time.strftime("%Y%m%dT%H%M%S", time.gmtime(time.time() - 30 * 86400))
    (sess / f"dead.md.delivered-{old}").write_text("x")
    stamp = time.time() - 10 * 86400
    os.utime(sess, (stamp, stamp))

    proc = _run(env)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "mailbox-janitor: APPLIED" in proc.stdout
    assert not sess.exists()
    receipts = (home / "logs" / "mailbox-janitor.receipts.jsonl").read_text().splitlines()
    assert len(receipts) == 1 and json.loads(receipts[0])["pruned_marked"] == 1
    hb = _heartbeat(home)
    assert hb["status"] == "ok" and hb["note"].startswith("mailbox-janitor: APPLIED")
    assert (home / "logs" / "mailbox-janitor.log").exists()


def test_kill_switch_exits_2_with_disabled_heartbeat(tmp_path):
    home, _, env = _sandbox(tmp_path)
    env["MAILBOX_JANITOR_ENABLED"] = "false"

    proc = _run(env)

    assert proc.returncode == 2
    assert "kill switch" in proc.stdout
    assert _heartbeat(home)["status"] == "disabled"


def test_missing_root_is_refused_with_fail_heartbeat(tmp_path):
    home, _, env = _sandbox(tmp_path)
    shutil.rmtree(home / ".nuzantara-mailbox")

    proc = _run(env)

    assert proc.returncode == 1
    assert "REFUSED" in proc.stdout
    assert _heartbeat(home)["status"] == "error"


def test_dry_run_env_touches_nothing(tmp_path):
    home, _, env = _sandbox(tmp_path)
    env["MAILBOX_JANITOR_DRY_RUN"] = "1"
    sess = home / ".nuzantara-mailbox" / "sess-old"
    sess.mkdir()
    old = time.strftime("%Y%m%dT%H%M%S", time.gmtime(time.time() - 30 * 86400))
    (sess / f"dead.md.expired-{old}").write_text("x")
    stamp = time.time() - 10 * 86400
    os.utime(sess, (stamp, stamp))

    proc = _run(env)

    assert proc.returncode == 0
    assert "mailbox-janitor: DRY-RUN" in proc.stdout
    assert sess.exists()
    assert _heartbeat(home)["status"] == "ok"


def test_deletion_error_maps_to_exit_3_and_warning_heartbeat(tmp_path):
    home, _, env = _sandbox(tmp_path)
    sess = home / ".nuzantara-mailbox" / "sess-locked"
    sess.mkdir()
    old = time.strftime("%Y%m%dT%H%M%S", time.gmtime(time.time() - 30 * 86400))
    (sess / f"dead.md.delivered-{old}").write_text("x")
    stamp = time.time() - 10 * 86400
    os.utime(sess, (stamp, stamp))
    sess.chmod(0o500)
    try:
        proc = _run(env)
    finally:
        sess.chmod(0o700)

    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert "WARN" in proc.stdout
    assert _heartbeat(home)["status"] == "warning"
    assert (sess / f"dead.md.delivered-{old}").exists()


def test_installer_render_on_m5_shaped_home(tmp_path):
    import plistlib

    home = tmp_path / "Users" / "balizero"
    home.mkdir(parents=True)
    env = {"HOME": str(home), "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    installer = REPO / "infra" / "launchagents" / "install_mailbox_janitor.sh"

    proc = subprocess.run(["bash", str(installer), "render"], env=env, capture_output=True, text=True)

    assert proc.returncode == 0, proc.stderr
    assert "/Users/nuzantara" not in proc.stdout
    d = plistlib.loads(proc.stdout.encode())
    assert d["Label"] == "com.nuzantara.mailbox-janitor.daily"
    assert d["ProgramArguments"][-1] == f"{home}/nuzantara/scripts/mailbox_janitor_cron.sh"
    assert d["EnvironmentVariables"]["HOME"] == str(home)
    assert "MAILBOX_JANITOR_ENABLED" not in d["EnvironmentVariables"]
    assert isinstance(d["StartCalendarInterval"], dict)
    assert d.get("KeepAlive") is False and d.get("RunAtLoad") is False
