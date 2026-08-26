"""test_lint_roster_dispatch.py — guilt + innocence fixtures for lint_roster_dispatch.py.

Runs the script as a real subprocess against `--fixture` JSON files (never calls
private functions directly) — same pattern as test_lint_scar_number_collision.py
and test_lint_home_fork.py: the CLI/argparse boundary is part of what's under
test, not just the internal logic.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "lint_roster_dispatch.py"


def run_lint(fixture: dict, tmp_path: Path) -> subprocess.CompletedProcess:
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--fixture", str(fixture_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )


def roster_row(model_id: str, note: str = "role text") -> str:
    return f"| `{model_id}` | {note} | effort |"


# ---------------------------------------------------------------- innocence

def test_claude_alias_has_a_door(tmp_path):
    result = run_lint({"roster": roster_row("claude-opus-5")}, tmp_path)
    assert result.returncode == 0, result.stderr
    assert "clean" in result.stdout


def test_tp1_slug_with_route_file_has_a_door(tmp_path):
    fixture = {
        "roster": roster_row("deepseek-v4-flash-0731"),
        "route_files": ["deepseek-v4-flash-0731"],
    }
    result = run_lint(fixture, tmp_path)
    assert result.returncode == 0, result.stderr


def test_gemini_and_kimi_and_imagegen_have_doors(tmp_path):
    fixture = {
        "roster": "\n".join(
            [
                roster_row("gemini-3.1-pro"),
                roster_row("k3"),
                roster_row("kimi-for-coding"),
                roster_row("$imagegen"),
            ]
        ),
    }
    result = run_lint(fixture, tmp_path)
    assert result.returncode == 0, result.stderr


def test_ollama_role_value_has_a_door(tmp_path):
    fixture = {"roster": roster_row("qwen3.5:9b"), "ollama_roles": ["qwen3.5:9b"]}
    result = run_lint(fixture, tmp_path)
    assert result.returncode == 0, result.stderr


def test_dead_codex_slug_marked_unreachable_is_clean(tmp_path):
    fixture = {"roster": roster_row("sol", "Red-team seat. UNREACHABLE (dead 2026-07-21).")}
    result = run_lint(fixture, tmp_path)
    assert result.returncode == 0, result.stderr


def test_any_doorless_row_marked_unreachable_is_clean(tmp_path):
    fixture = {"roster": roster_row("some-gui-only-tool", "GUI only. UNREACHABLE (no CLI).")}
    result = run_lint(fixture, tmp_path)
    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------- guilt

def test_dead_codex_slug_without_marker_is_an_offender(tmp_path):
    """The exact defect MODEL_ROSTER.md carried before this PR's fix: `sol`
    documented with strengths and effort notes, no working `-m` door, no
    honest label saying so."""
    result = run_lint({"roster": roster_row("sol")}, tmp_path)
    assert result.returncode == 1
    assert "`sol`" in result.stderr


def test_tp1_slug_without_route_file_is_an_offender(tmp_path):
    fixture = {"roster": roster_row("qwen3.8-max"), "route_files": []}
    result = run_lint(fixture, tmp_path)
    assert result.returncode == 1
    assert "`qwen3.8-max`" in result.stderr


def test_unknown_id_without_marker_is_an_offender(tmp_path):
    result = run_lint({"roster": roster_row("mystery-model-9000")}, tmp_path)
    assert result.returncode == 1
    assert "`mystery-model-9000`" in result.stderr


def test_offender_and_clean_row_together_reports_only_the_offender(tmp_path):
    fixture = {
        "roster": "\n".join([roster_row("claude-sonnet-5"), roster_row("terra")]),
    }
    result = run_lint(fixture, tmp_path)
    assert result.returncode == 1
    assert "`terra`" in result.stderr
    assert "`claude-sonnet-5`" not in result.stderr


# ---------------------------------------------------------------- blind-scan guard (W84)

def test_zero_rows_parsed_is_an_operational_error_not_a_clean_pass(tmp_path):
    """A doc with no `| \\`id\\`` rows at all must never read as 'nothing wrong'
    — that is the blind-scan disease this whole family of lints exists to
    avoid (scar W84: a run that checked 0 things is not the same as clean)."""
    result = run_lint({"roster": "# Just prose, no table rows here.\n"}, tmp_path)
    assert result.returncode == 2


def test_unreadable_fixture_is_an_operational_error(tmp_path):
    bad_path = tmp_path / "does-not-exist.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--fixture", str(bad_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2


# ---------------------------------------------------------------- drift guard (kimi refuter round 1)

def test_route_files_base_url_matches_arsenal_probe_constant():
    """kimi refuter round 1: the review_routes/*.json files and tp1_call.py
    (via its arsenal_probe import) are two independently-editable sources for
    the same TP1 endpoint. The lint only proves a route FILE exists, never
    that its content agrees with the constant the actual door uses — so a
    future edit to one could silently drift from the other with nothing red.
    This closes that gap directly: every live TP1 slug's route file must
    declare the exact base_url arsenal_probe.py (and therefore tp1_call.py)
    actually calls."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from arsenal_probe import TP1_BASE_URL, TP1_SEAT_MODELS  # noqa: E402

    route_dir = REPO_ROOT / "scripts" / "review_routes"
    for slug in TP1_SEAT_MODELS.values():
        route_path = route_dir / f"{slug}-v1.json"
        assert route_path.exists(), f"missing route file for live TP1 slug {slug}"
        doc = json.loads(route_path.read_text(encoding="utf-8"))
        assert doc.get("base_url") == TP1_BASE_URL, (
            f"{route_path.name} base_url {doc.get('base_url')!r} has drifted "
            f"from arsenal_probe.TP1_BASE_URL {TP1_BASE_URL!r}"
        )


# ---------------------------------------------------------------- ground truth: the real repo file

def test_real_model_roster_is_clean():
    """Integration check against the actual on-disk MODEL_ROSTER.md and
    scripts/review_routes/ — proves the roster edits and the new route JSONs
    in this PR actually satisfy the lint together, not just in isolation."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
