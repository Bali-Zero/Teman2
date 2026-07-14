"""Tests for scripts/lint_doc_executable_refs.py.

W82/guard-conformance discipline applied to the lint itself: every arm gets
a GUILT case (a doc citing a ghost file IS caught) and an INNOCENCE case (a
doc citing a real file, or a deliberately-historical doc citing a ghost, is
NOT flagged). No repo-tree dependence — everything runs against tmp_path
fixtures shaped like a miniature repo.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "lint_doc_executable_refs.py"
_spec = importlib.util.spec_from_file_location("lint_doc_executable_refs", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
ldr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ldr)


# ---------------------------------------------------------------- helpers


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "docs" / "wr2").mkdir(parents=True)
    return repo


def default_config() -> dict:
    return {
        "include_globs": ["docs/wr2/*.md"],
        "exclude_prefixes": ["research/", ".claude/rules/cicatrix", "docs/superpowers/plans/"],
        "exclude_dated_filenames": True,
    }


# ---------------------------------------------------------------- regex extraction


def test_exec_ref_regex_matches_py_and_sh() -> None:
    text = "run `scripts/foo_bar.py` then `scripts/sub/dir-name.sh` and prose."
    refs = {m.group(0) for m in ldr.EXEC_REF_RE.finditer(text)}
    assert refs == {"scripts/foo_bar.py", "scripts/sub/dir-name.sh"}


def test_dated_basename_regex() -> None:
    assert ldr.DATED_BASENAME_RE.search("2026-05-08-sprint-b-to-f-detailed-plan.md")
    assert ldr.DATED_BASENAME_RE.search("pipeline-architecture-2026-05-10.md")
    assert not ldr.DATED_BASENAME_RE.search("SUPERVISOR.md")
    assert not ldr.DATED_BASENAME_RE.search("flowkit-integration.md")


# ---------------------------------------------------------------- scan_file


def test_scan_file_guilt_ghost_reference(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    doc = repo / "docs" / "wr2" / "SUPERVISOR.md"
    doc.write_text("Entry point: `scripts/wr2_carousel_orchestrator.py` (does not exist).\n")
    ghosts = ldr.scan_file(doc, repo)
    assert ghosts == ["scripts/wr2_carousel_orchestrator.py"]


def test_scan_file_innocence_real_reference(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / "scripts" / "wr2_supervisor.py").write_text("# real\n")
    doc = repo / "docs" / "wr2" / "SUPERVISOR.md"
    doc.write_text("Code: `scripts/wr2_supervisor.py`.\n")
    ghosts = ldr.scan_file(doc, repo)
    assert ghosts == []


def test_scan_file_innocence_no_refs_at_all(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    doc = repo / "docs" / "wr2" / "prose-only.md"
    doc.write_text("This document mentions scripts in prose but no scripts/ path.\n")
    ghosts = ldr.scan_file(doc, repo)
    assert ghosts == []


# ---------------------------------------------------------------- is_excluded


def test_is_excluded_dated_filename() -> None:
    assert ldr.is_excluded(
        "docs/wr2/2026-05-08-sprint-b-to-f-detailed-plan.md",
        "2026-05-08-sprint-b-to-f-detailed-plan.md",
        [],
        True,
    )


def test_is_excluded_directory_prefix() -> None:
    assert ldr.is_excluded(
        "research/operations/2026-07-14-wr2-deep-audit.md",
        "2026-07-14-wr2-deep-audit.md",
        ["research/"],
        False,
    )


def test_is_excluded_innocence_living_doc_not_excluded() -> None:
    assert not ldr.is_excluded(
        "docs/wr2/SUPERVISOR.md",
        "SUPERVISOR.md",
        ["research/", ".claude/rules/cicatrix", "docs/superpowers/plans/"],
        True,
    )


# ---------------------------------------------------------------- run_lint (integration)


def test_run_lint_guilt_ghost_in_living_doc(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / "docs" / "wr2" / "SUPERVISOR.md").write_text(
        "Entry: `scripts/wr2_telegram_publish_gate.py` (ghost).\n"
    )
    ghosts_by_file, scanned, errors = ldr.run_lint(default_config(), repo)
    assert scanned == ["docs/wr2/SUPERVISOR.md"]
    assert ghosts_by_file == {"docs/wr2/SUPERVISOR.md": ["scripts/wr2_telegram_publish_gate.py"]}
    assert errors == []


def test_run_lint_innocence_real_ref_passes(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / "scripts" / "wr2_supervisor.py").write_text("# real\n")
    (repo / "docs" / "wr2" / "SUPERVISOR.md").write_text("Code: `scripts/wr2_supervisor.py`.\n")
    ghosts_by_file, scanned, errors = ldr.run_lint(default_config(), repo)
    assert ghosts_by_file == {}
    assert scanned == ["docs/wr2/SUPERVISOR.md"]
    assert errors == []


def test_run_lint_innocence_historical_dated_doc_exempted(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    hist = repo / "docs" / "wr2" / "2026-05-08-sprint-b-to-f-detailed-plan.md"
    hist.write_text("Back then: `scripts/wr2_canva_apply.py` (retired since).\n")
    ghosts_by_file, scanned, errors = ldr.run_lint(default_config(), repo)
    # dated file is matched by include_globs but excluded from scanning
    assert hist.relative_to(repo).as_posix() not in scanned
    assert ghosts_by_file == {}
    assert errors == []


def test_run_lint_innocence_directory_prefix_exempted(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / "research" / "operations").mkdir(parents=True)
    (repo / "research" / "operations" / "audit.md").write_text(
        "`scripts/does_not_exist.py` cited in an audit report.\n"
    )
    config = dict(default_config())
    config["include_globs"] = ["research/operations/*.md"]
    ghosts_by_file, scanned, errors = ldr.run_lint(config, repo)
    assert ghosts_by_file == {}
    assert scanned == []
    assert errors == []


def test_run_lint_error_when_no_files_matched(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    config = dict(default_config())
    config["include_globs"] = ["docs/nonexistent-dir/*.md"]
    ghosts_by_file, scanned, errors = ldr.run_lint(config, repo)
    assert ghosts_by_file == {}
    assert scanned == []
    assert len(errors) == 1
    assert "zero files matched" in errors[0]


# ---------------------------------------------------------------- main() exit codes


def test_main_exit_0_clean(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    repo = make_repo(tmp_path)
    (repo / "scripts" / "wr2_supervisor.py").write_text("# real\n")
    (repo / "docs" / "wr2" / "SUPERVISOR.md").write_text("Code: `scripts/wr2_supervisor.py`.\n")
    config_path = repo / "config.json"
    config_path.write_text(json.dumps(default_config()))
    rc = ldr.main(["--config", str(config_path), "--repo-root", str(repo)])
    assert rc == 0
    assert "clean" in capsys.readouterr().out


def test_main_exit_1_ghost_found(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    repo = make_repo(tmp_path)
    (repo / "docs" / "wr2" / "SUPERVISOR.md").write_text(
        "Entry: `scripts/wr2_carousel_orchestrator.py`.\n"
    )
    config_path = repo / "config.json"
    config_path.write_text(json.dumps(default_config()))
    rc = ldr.main(["--config", str(config_path), "--repo-root", str(repo)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "wr2_carousel_orchestrator.py" in out
    assert "LINT FAIL" in out


def test_main_exit_4_blind_scan(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    repo = make_repo(tmp_path)
    config = dict(default_config())
    config["include_globs"] = ["docs/nothing-here/*.md"]
    config_path = repo / "config.json"
    config_path.write_text(json.dumps(config))
    rc = ldr.main(["--config", str(config_path), "--repo-root", str(repo)])
    assert rc == 4


def test_main_json_output(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    repo = make_repo(tmp_path)
    (repo / "docs" / "wr2" / "SUPERVISOR.md").write_text(
        "Entry: `scripts/wr2_carousel_orchestrator.py`.\n"
    )
    config_path = repo / "config.json"
    config_path.write_text(json.dumps(default_config()))
    rc = ldr.main(["--config", str(config_path), "--repo-root", str(repo), "--json"])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["exit"] == 1
    assert "docs/wr2/SUPERVISOR.md" in payload["ghosts_by_file"]


def test_load_config_defaults_applied(tmp_path: Path) -> None:
    config_path = tmp_path / "minimal.json"
    config_path.write_text(json.dumps({"include_globs": ["x/*.md"]}))
    config = ldr.load_config(config_path)
    assert config["exclude_prefixes"] == []
    assert config["exclude_dated_filenames"] is True


def test_load_config_missing_file_raises_systemexit(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        ldr.load_config(tmp_path / "does-not-exist.json")
