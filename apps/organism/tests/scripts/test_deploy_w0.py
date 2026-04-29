"""Tests for `apps/organism/scripts/deploy_w0.sh`.

The script wraps `launchctl bootstrap` with five abort triggers (P0-3
plist-corruption guard, see 99c_w0a_bis_kickoff.md §3.3). We exercise it
end-to-end against a synthetic environment:

  - $TARGET                — a temporary `LaunchAgents/` dir we create
  - $REPO/launchd/         — temporary copies of the three real plists
  - PATH-prepended bin/    — fake `launchctl`, `plutil`, `curl` shims that
                             write what they were called with into a log
                             file so we can assert the script took (or
                             skipped) the expected step

This way:
  * we do NOT touch the real ~/Library/LaunchAgents
  * we do NOT call the real launchctl (which would mutate user state)
  * we DO drive the actual bash logic — every `if` / `trap` / loop is
    really executed; only the leaf binaries are stubbed.

Six test cases total: one happy-path dry-run + five trigger cases (one per
abort condition).
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import textwrap
from pathlib import Path

import pytest


ORGANISM_APP = Path(__file__).resolve().parents[2]  # apps/organism/
SCRIPT = ORGANISM_APP / "scripts" / "deploy_w0.sh"
REAL_PLIST_DIR = ORGANISM_APP / "organism" / "launchd"
PLIST_NAMES = [
    "com.nuzantara.organism.supervisor.plist",
    "com.nuzantara.organism.control-panel.plist",
    "com.nuzantara.organism.scheduled-tick.plist",
]


# ---------- harness -----------------------------------------------------------


def _write_stub(path: Path, body: str, *, mode: int = 0o755) -> None:
    path.write_text(body)
    path.chmod(mode)


def _make_env(
    tmp_path: Path,
    *,
    launchctl_body: str | None = None,
    plutil_body: str | None = None,
    curl_body: str | None = None,
    quarantine_after_cp: bool = False,
) -> tuple[Path, dict[str, str], Path]:
    """Build a synthetic environment for the deploy script.

    Returns (organism_repo_path, env_dict_for_subprocess, call_log_path).
    """
    repo = tmp_path / "organism_repo"
    launchd_src = repo / "organism" / "launchd"
    launchd_src.mkdir(parents=True)
    for name in PLIST_NAMES:
        shutil.copyfile(REAL_PLIST_DIR / name, launchd_src / name)

    # The script reads $HOME/Library/LaunchAgents — keep the dir creation
    # below in sync with that path.
    target = tmp_path / "Library" / "LaunchAgents"
    target.mkdir(parents=True)

    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "calls.log"

    # Default stubs always succeed.
    default_launchctl = textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        echo "launchctl $@" >> {log}
        case "$1" in
          bootout)   exit 0 ;;
          bootstrap) exit 0 ;;
          print)
            # `launchctl print gui/<uid>/<label>` — $2 is the path. Emit a
            # realistic steady-state line per plist type so trigger 5 passes:
            #   - daemon (supervisor, control-panel): state = running
            #   - cron   (scheduled-tick): state = not running + last exit = 0
            case "$2" in
              *scheduled-tick*)
                echo "state = not running"
                echo "last exit code = 0"
                ;;
              *)
                echo "state = running"
                ;;
            esac
            exit 0
            ;;
        esac
        exit 0
        """
    )
    default_plutil = textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        echo "plutil $@" >> {log}
        # Reuse the real plutil to actually validate so happy-path is honest.
        /usr/bin/plutil "$@"
        """
    )
    default_curl = textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        echo "curl $@" >> {log}
        exit 0
        """
    )
    _write_stub(bindir / "launchctl", launchctl_body or default_launchctl)
    _write_stub(bindir / "plutil", plutil_body or default_plutil)
    _write_stub(bindir / "curl", curl_body or default_curl)

    if quarantine_after_cp:
        # `install` is invoked by the script during cp. We override it with
        # a stub that copies the file AND drops a quarantine sibling, so the
        # snapshot delta inside deploy_w0.sh fires trigger #4.
        install_stub = textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            echo "install $@" >> {log}
            # Mimic real install: last arg is destination.
            dst="${{!#}}"
            # Find the source — second-to-last arg.
            args=("$@")
            src="${{args[$(( ${{#args[@]}} - 2 ))]}}"
            cp "$src" "$dst"
            # Drop a quarantine file alongside.
            touch "{target}/com.nuzantara.bogus.bak-stamp"
            exit 0
            """
        )
        _write_stub(bindir / "install", install_stub)

    env = os.environ.copy()
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["ORGANISM_REPO"] = str(repo)
    env["HOME"] = str(tmp_path)
    # Fast verify so trigger-5 tests don't sit 30s.
    env["VERIFY_TIMEOUT_SECONDS"] = "2"
    return repo, env, log


def _run(env: dict[str, str], *, dry_run: bool = False) -> subprocess.CompletedProcess:
    cmd = ["bash", str(SCRIPT)]
    if dry_run:
        env = {**env, "DRY_RUN": "1"}
    return subprocess.run(
        cmd, env=env, capture_output=True, text=True, timeout=60
    )


# ---------- tests -------------------------------------------------------------


@pytest.mark.allow_real_subprocess
def test_dry_run_validates_repo_plists_without_touching_launchctl(tmp_path):
    """Happy-path dry-run: lints the three plists, never invokes launchctl."""
    _, env, log = _make_env(tmp_path)
    result = _run(env, dry_run=True)

    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "W0-B deploy complete (3 plist deployed)" in result.stdout
    # plutil was called (one per plist). launchctl/install/curl were NOT.
    log_text = log.read_text() if log.exists() else ""
    assert log_text.count("plutil ") >= 3
    assert "launchctl bootout" not in log_text
    assert "launchctl bootstrap" not in log_text


@pytest.mark.allow_real_subprocess
def test_trigger_1_plutil_lint_failure_aborts(tmp_path):
    """Trigger 1: plutil -lint exit != 0 → abort."""
    plutil_body = textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        echo "plutil $@" >> {tmp_path}/calls.log
        echo "plist parse error: synthetic" >&2
        exit 1
        """
    )
    _, env, log = _make_env(tmp_path, plutil_body=plutil_body)
    result = _run(env)

    assert result.returncode != 0
    assert "trigger=1_plutil_lint" in result.stderr
    # No bootstrap should ever have run.
    log_text = log.read_text() if log.exists() else ""
    assert "launchctl bootstrap" not in log_text


@pytest.mark.allow_real_subprocess
def test_trigger_2_undersized_file_aborts(tmp_path):
    """Trigger 2: deployed file < 500 bytes → abort.

    We override `install` with a stub that writes a 10-byte placeholder,
    so the size check kicks in *after* lint (we use a permissive plutil
    stub that always succeeds).
    """
    install_body = textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        echo "install $@" >> {tmp_path}/calls.log
        dst="${{!#}}"
        printf 'tiny' > "$dst"
        exit 0
        """
    )
    plutil_permissive = textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        echo "plutil $@" >> {tmp_path}/calls.log
        exit 0
        """
    )
    _, env, log = _make_env(tmp_path, plutil_body=plutil_permissive)
    _write_stub(Path(env["PATH"].split(":")[0]) / "install", install_body)
    result = _run(env)

    assert result.returncode != 0
    assert "trigger=2_size" in result.stderr
    log_text = log.read_text() if log.exists() else ""
    assert "launchctl bootstrap" not in log_text


@pytest.mark.allow_real_subprocess
def test_trigger_3_bootstrap_failure_aborts(tmp_path):
    """Trigger 3: launchctl bootstrap exit != 0 → abort."""
    launchctl_body = textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        echo "launchctl $@" >> {tmp_path}/calls.log
        case "$1" in
          bootstrap)
            echo "Bootstrap failed: 5: Input/output error" >&2
            exit 5
            ;;
          *) exit 0 ;;
        esac
        """
    )
    _, env, log = _make_env(tmp_path, launchctl_body=launchctl_body)
    result = _run(env)

    assert result.returncode != 0
    assert "trigger=3_bootstrap" in result.stderr


@pytest.mark.allow_real_subprocess
def test_trigger_4_quarantine_artifact_aborts(tmp_path):
    """Trigger 4: a new .bak/.disabled/.backup file appearing during cp."""
    _, env, log = _make_env(tmp_path, quarantine_after_cp=True)
    result = _run(env)

    assert result.returncode != 0
    assert "trigger=4_quarantine" in result.stderr


@pytest.mark.allow_real_subprocess
def test_trigger_5_state_running_timeout_aborts(tmp_path):
    """Trigger 5: launchctl print never shows 'state = running' → abort.

    Daemon-path failure: the first plist in PLISTS is supervisor (KeepAlive=true).
    With set -euo pipefail, abort on supervisor exits before scheduled-tick is
    even reached, so this test exercises only the daemon branch.
    """
    launchctl_body = textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        echo "launchctl $@" >> {tmp_path}/calls.log
        case "$1" in
          print)
            # Never emit "state = running" → trigger 5 fires.
            echo "state = waiting"
            exit 0
            ;;
          *) exit 0 ;;
        esac
        """
    )
    _, env, log = _make_env(tmp_path, launchctl_body=launchctl_body)
    result = _run(env)

    assert result.returncode != 0
    assert "trigger=5_state_running" in result.stderr


@pytest.mark.allow_real_subprocess
def test_trigger_5_cron_never_fired_accepted(tmp_path):
    """Trigger 5 cron-branch: scheduled-tick never ran yet → state=not running
    with NO 'last exit code' line is the bootstrap-fresh steady-state and
    must be accepted (no abort).

    The default stub already emits "state = not running" + "last exit code = 0"
    for scheduled-tick. To exercise the never-fired path we override print to
    omit the last-exit line for that label only.
    """
    launchctl_body = textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        echo "launchctl $@" >> {tmp_path}/calls.log
        case "$1" in
          bootout)   exit 0 ;;
          bootstrap) exit 0 ;;
          print)
            case "$2" in
              *scheduled-tick*)
                # Bootstrap-fresh: never fired yet, no last-exit line.
                echo "state = not running"
                ;;
              *)
                echo "state = running"
                ;;
            esac
            exit 0
            ;;
        esac
        exit 0
        """
    )
    _, env, log = _make_env(tmp_path, launchctl_body=launchctl_body)
    result = _run(env)

    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "W0-B deploy complete (3 plist deployed)" in result.stdout


@pytest.mark.allow_real_subprocess
def test_trigger_5_cron_last_exit_nonzero_aborts(tmp_path):
    """Trigger 5 cron-branch: scheduled-tick ran and crashed (last exit != 0)
    → trigger 5 must fire. Cron-pattern accept is steady-state OK only when
    last exit code is 0 or absent."""
    launchctl_body = textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        echo "launchctl $@" >> {tmp_path}/calls.log
        case "$1" in
          bootout)   exit 0 ;;
          bootstrap) exit 0 ;;
          print)
            case "$2" in
              *scheduled-tick*)
                echo "state = not running"
                echo "last exit code = 78"
                ;;
              *)
                echo "state = running"
                ;;
            esac
            exit 0
            ;;
        esac
        exit 0
        """
    )
    _, env, log = _make_env(tmp_path, launchctl_body=launchctl_body)
    result = _run(env)

    assert result.returncode != 0
    assert "trigger=5_state_running" in result.stderr
    # Error message must reference cron-specific phrasing so triage is fast.
    assert "cron plist" in result.stderr
