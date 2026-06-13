"""Tests for the LaunchAgent wrapper around scripts/agent_start.py --cleanup.

The broker intentionally returns rc=1 when it skips dirty WIP worktrees. In an
interactive run that is useful operator signal; in the daily LaunchAgent it must
not become a launchd bad-exit, because WIP-safe skipping is expected behavior.
"""
from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = REPO_ROOT / "scripts" / "agent_worktree_cleanup_cron.sh"


def _write_stub_broker(stub_repo: Path, body: str) -> None:
    scripts_dir = stub_repo / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "agent_start.py").write_text(
        textwrap.dedent(body).lstrip(),
        encoding="utf-8",
    )


def _run_wrapper(tmp_path: Path, stub_repo: Path) -> subprocess.CompletedProcess[str]:
    home = tmp_path / "home"
    home.mkdir()
    env = dict(os.environ)
    env.update(
        {
            "AGENT_WORKTREE_CLEANUP_REPO_ROOT": str(stub_repo),
            "HOME": str(home),
        }
    )
    return subprocess.run(
        ["/bin/bash", str(WRAPPER)],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_cleanup_cron_maps_wip_skip_to_success(tmp_path: Path) -> None:
    stub_repo = tmp_path / "repo"
    _write_stub_broker(
        stub_repo,
        """
        #!/usr/bin/env python3
        import sys

        assert sys.argv[1:] == ["--cleanup"]
        print(
            "WARN: skip dirty-wip (WIP). Commit or stash inside "
            "/tmp/dirty-wip, then re-run --cleanup."
        )
        raise SystemExit(1)
        """,
    )

    proc = _run_wrapper(tmp_path, stub_repo)

    assert proc.returncode == 0
    combined = proc.stdout + proc.stderr
    assert "WARN: skip dirty-wip" in combined
    log = (tmp_path / "home" / "logs" / "agent-worktree-cleanup.log").read_text(
        encoding="utf-8"
    )
    assert "WIP worktree(s) skipped" in log
    assert "expected guard, not a failure" in log
    assert "done (broker rc=1, exit 0)" in log


def test_cleanup_cron_preserves_real_broker_error(tmp_path: Path) -> None:
    stub_repo = tmp_path / "repo"
    _write_stub_broker(
        stub_repo,
        """
        #!/usr/bin/env python3
        import sys

        assert sys.argv[1:] == ["--cleanup"]
        print("ERROR: synthetic broker failure")
        raise SystemExit(42)
        """,
    )

    proc = _run_wrapper(tmp_path, stub_repo)

    assert proc.returncode == 42
    combined = proc.stdout + proc.stderr
    assert "ERROR: synthetic broker failure" in combined
    log = (tmp_path / "home" / "logs" / "agent-worktree-cleanup.log").read_text(
        encoding="utf-8"
    )
    assert "done (broker rc=42, exit 42)" in log
