from __future__ import annotations

import fcntl
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest


WRAPPER = (
    Path(__file__).resolve().parents[2]
    / "infra/launchagents/wrappers/bali-zero-magazine-publish.sh"
)


def _write_fake_magazine_python(path: Path) -> None:
    path.write_text(
        """\
#!/usr/bin/env python3
from pathlib import Path
import os
import signal
import subprocess
import sys
import time

if sys.argv[1] == "-":
    os.execv(sys.executable, [sys.executable, *sys.argv[1:]])

pid_file = Path(os.environ["MAGAZINE_TREE_PID_FILE"])
command_marker = Path(os.environ["MAGAZINE_COMMAND_MARKER"])
command_marker.write_text("started", encoding="utf-8")
mode = sys.argv[1]
if mode == "grandchild":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    with pid_file.open("a", encoding="utf-8") as stream:
        stream.write(f"{os.getpid()}\\n")
    time.sleep(60)
elif mode == "child":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    with pid_file.open("a", encoding="utf-8") as stream:
        stream.write(f"{os.getpid()}\\n")
    subprocess.Popen([sys.executable, __file__, "grandchild"])
    time.sleep(60)
else:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    pid_file.write_text(f"{os.getpid()}\\n", encoding="utf-8")
    subprocess.Popen([sys.executable, __file__, "child"])
    time.sleep(60)
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _wrapper_environment(
    tmp_path: Path,
    *,
    fake_python: Path,
    input_path: Path,
) -> dict[str, str]:
    return {
        **os.environ,
        "HOME": str(tmp_path),
        "MAGAZINE_ALLOW_NON_PRO": "true",
        "MAGAZINE_AUTOMATION_ENABLED": "true",
        "MAGAZINE_BREAKING_INPUT": str(input_path),
        "MAGAZINE_COMMAND_MARKER": str(tmp_path / "command-started"),
        "MAGAZINE_INPUT_DIR": str(tmp_path / "inputs"),
        "MAGAZINE_KILL_GRACE_SECONDS": "1",
        "MAGAZINE_LOG_DIR": str(tmp_path / "logs"),
        "MAGAZINE_OUTPUT_DIR": str(tmp_path / "packets"),
        "MAGAZINE_PROCESS_LAUNCHER_PYTHON": sys.executable,
        "MAGAZINE_PUBLISH_ENABLED": "false",
        "MAGAZINE_PYTHON": str(fake_python),
        "MAGAZINE_ROOT": str(WRAPPER.parents[3]),
        "MAGAZINE_STATE_DIR": str(tmp_path / "state"),
        "MAGAZINE_TIMEOUT_SECONDS": "1",
        "MAGAZINE_TREE_PID_FILE": str(tmp_path / "tree-pids.txt"),
    }


def _assert_processes_exit(pids: list[int]) -> None:
    remaining = set(pids)
    for _ in range(60):
        for pid in tuple(remaining):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                remaining.remove(pid)
        if not remaining:
            return
        time.sleep(0.05)
    raise AssertionError(f"processes survived termination: {sorted(remaining)}")


def test_magazine_wrapper_uses_process_held_advisory_lock() -> None:
    source = WRAPPER.read_text(encoding="utf-8")

    assert 'LOCKFILE="$STATE_DIR/${MODE}.flock"' in source
    assert '[[ -e "$LOCKFILE" && ! -f "$LOCKFILE" ]]' in source
    assert "zmodload zsh/system" in source
    assert "zsystem flock -t 0.001 -i 0.001 -f" in source
    assert 'lock_rc="$?"' in source
    assert 'case "$lock_rc" in' in source
    assert "2)" in source
    assert "advisory_lock_failed rc=$lock_rc" in source
    assert "if ! zsystem flock" not in source
    assert "zsystem flock -u" in source
    assert 'mkdir "$LOCKDIR"' not in source
    assert 'rm -rf "$LOCKDIR"' not in source


@pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh is unavailable")
def test_zsh_flock_distinguishes_contention_from_open_error(tmp_path: Path) -> None:
    lock_file = tmp_path / "publisher.flock"
    lock_file.touch()
    with lock_file.open("r+", encoding="utf-8") as held:
        fcntl.lockf(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        contended = subprocess.run(
            [
                "zsh",
                "-fc",
                (
                    "zmodload zsh/system; zsystem flock -t 0.001 -i 0.001 "
                    '-f fd "$1" 2>/dev/null; exit $?'
                ),
                "flock-contender",
                str(lock_file),
            ],
            check=False,
            timeout=2,
        )
        assert contended.returncode == 2

    invalid_path = tmp_path / "not-a-file"
    invalid_path.mkdir()
    invalid = subprocess.run(
        [
            "zsh",
            "-fc",
            (
                "zmodload zsh/system; zsystem flock -t 0.001 -i 0.001 "
                '-f fd "$1" 2>/dev/null; exit $?'
            ),
            "flock-invalid",
            str(invalid_path),
        ],
        check=False,
        timeout=2,
    )
    assert invalid.returncode == 1


@pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh is unavailable")
def test_wrapper_timeout_kills_parent_child_and_grandchild(tmp_path: Path) -> None:
    fake_python = tmp_path / "fake-magazine-python"
    _write_fake_magazine_python(fake_python)
    input_path = tmp_path / "breaking.json"
    input_path.write_text("{}", encoding="utf-8")
    env = _wrapper_environment(
        tmp_path,
        fake_python=fake_python,
        input_path=input_path,
    )

    result = subprocess.run(
        ["zsh", str(WRAPPER), "breaking"],
        check=False,
        env=env,
        timeout=10,
    )

    assert result.returncode == 124
    pid_file = Path(env["MAGAZINE_TREE_PID_FILE"])
    pids = [int(item) for item in pid_file.read_text(encoding="utf-8").splitlines()]
    assert len(pids) == 3
    _assert_processes_exit(pids)


@pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh is unavailable")
def test_wrapper_stops_before_command_when_manifest_preflight_fails(
    tmp_path: Path,
) -> None:
    fake_python = tmp_path / "fake-magazine-python"
    _write_fake_magazine_python(fake_python)
    input_path = tmp_path / "breaking.json"
    input_path.write_text(
        '{"projection_input":{"system_id":"missing","projection_path":"/does/not/exist"}}',
        encoding="utf-8",
    )
    env = _wrapper_environment(
        tmp_path,
        fake_python=fake_python,
        input_path=input_path,
    )

    result = subprocess.run(
        ["zsh", str(WRAPPER), "breaking"],
        check=False,
        env=env,
        timeout=10,
    )

    assert result.returncode == 65
    assert not Path(env["MAGAZINE_COMMAND_MARKER"]).exists()
