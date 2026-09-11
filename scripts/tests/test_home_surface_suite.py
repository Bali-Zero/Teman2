"""Guilt + innocence for scripts/home_surface_suite.sh.

The suite tests the machine-local Claude surface (~/.claude). CI has no such surface,
so every case here points HOME at a fixture: a clean one must PASS, and each of the
two structural gates (tool search deferred, agent frontmatter intact) must FAIL when
its fixture is broken. The hooks/budget sections run against the real repo checkout
with the fixture HOME, which is the shape a fresh machine presents.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SUITE = REPO_ROOT / "scripts" / "home_surface_suite.sh"


def _fixture_home(tmp_path: Path, *, tool_search: str = "true", agent_body: str | None = None) -> Path:
    home = tmp_path / "home"
    (home / ".claude" / "agents").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text(
        json.dumps({"env": {"ENABLE_TOOL_SEARCH": tool_search}, "permissions": {"deny": ["Artifact"]}})
    )
    (home / ".claude.json").write_text(json.dumps({"claudeInChromeDefaultEnabled": False}))
    body = agent_body if agent_body is not None else "---\nname: probe\ndescription: fixture agent\n---\nbody\n"
    (home / ".claude" / "agents" / "probe.md").write_text(body)
    return home


def _run(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "HOME": str(home),
        # never spawn the background arsenal probe from a test
        "ORGANISM_ARSENAL_REFRESH_ENABLED": "false",
    }
    return subprocess.run(
        ["bash", str(SUITE), "--repo-root", str(REPO_ROOT), *args],
        capture_output=True, text=True, env=env, timeout=300, check=False,
    )


def test_clean_fixture_passes_structural_sections(tmp_path: Path) -> None:
    res = _run(_fixture_home(tmp_path), "--only", "settings,agents")
    assert res.returncode == 0, res.stdout + res.stderr
    assert "SUITE_RESULT=PASS" in res.stdout
    assert "deny_entries=1" in res.stdout


def test_tool_search_not_deferred_fails(tmp_path: Path) -> None:
    res = _run(_fixture_home(tmp_path, tool_search="auto:5"), "--only", "settings")
    assert res.returncode == 1
    assert "ENABLE_TOOL_SEARCH" in res.stdout
    assert "SUITE_RESULT=FAIL" in res.stdout


def test_agent_without_frontmatter_name_fails(tmp_path: Path) -> None:
    res = _run(_fixture_home(tmp_path, agent_body="---\ndescription: nameless\n---\nbody\n"), "--only", "agents")
    assert res.returncode == 1
    assert "probe.md(no-name)" in res.stdout


def test_budget_ceiling_gates(tmp_path: Path) -> None:
    res = _run(_fixture_home(tmp_path), "--only", "budget", "--max-tokens", "1")
    assert res.returncode == 1
    assert "FAIL  budget:" in res.stdout


@pytest.mark.skipif(not (REPO_ROOT / "scripts" / "hooks" / "memory_recall_sessionstart.sh").exists(), reason="hooks absent")
def test_hooks_and_budget_pass_on_fresh_home(tmp_path: Path) -> None:
    res = _run(_fixture_home(tmp_path), "--only", "hooks,homefork,budget")
    assert res.returncode == 0, res.stdout + res.stderr
    assert res.stdout.count("ok    hooks:") == 4
    assert "ok    budget:" in res.stdout


def test_unknown_flag_is_usage_error(tmp_path: Path) -> None:
    res = _run(_fixture_home(tmp_path), "--bogus")
    assert res.returncode == 2
