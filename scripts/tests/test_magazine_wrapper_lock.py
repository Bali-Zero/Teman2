from __future__ import annotations

import fcntl
import shutil
import subprocess
from pathlib import Path

import pytest


WRAPPER = (
    Path(__file__).resolve().parents[2]
    / "infra/launchagents/wrappers/bali-zero-magazine-publish.sh"
)


def test_magazine_wrapper_uses_process_held_advisory_lock() -> None:
    source = WRAPPER.read_text(encoding="utf-8")

    assert 'LOCKFILE="$STATE_DIR/${MODE}.flock"' in source
    assert '[[ -e "$LOCKFILE" && ! -f "$LOCKFILE" ]]' in source
    assert "zmodload zsh/system" in source
    assert "zsystem flock -t 0.001 -i 0.001 -f" in source
    assert 'lock_rc="$?"' in source
    assert 'case "$lock_rc" in' in source
    assert '2)' in source
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
                    'zmodload zsh/system; zsystem flock -t 0.001 -i 0.001 '
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
                'zmodload zsh/system; zsystem flock -t 0.001 -i 0.001 '
                '-f fd "$1" 2>/dev/null; exit $?'
            ),
            "flock-invalid",
            str(invalid_path),
        ],
        check=False,
        timeout=2,
    )
    assert invalid.returncode == 1
