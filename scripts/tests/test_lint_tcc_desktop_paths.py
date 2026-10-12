"""Tests for scripts/lint_tcc_desktop_paths.py (superscar #1, W84/TCC variant).

Scar #3 discipline: the standing CI guard ships with its own guilt AND
innocence proof.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "lint_tcc_desktop_paths.py"
_spec = importlib.util.spec_from_file_location("lint_tcc_desktop_paths", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
lint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lint)


# ---------------------------------------------------------------- helpers


def make_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    return repo


def git_add(repo: Path, *relpaths: str) -> None:
    subprocess.run(["git", "add", *relpaths], cwd=repo, check=True)


# ---------------------------------------------------------------- guilt/innocence


def test_guilt_tracked_shell_payload_with_desktop_path_is_caught(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path)
    (repo / "wrapper.sh").write_text("REPO=\"$HOME/Desktop/nuzantara\"\n")
    git_add(repo, "wrapper.sh")
    rc = lint.main(["--repo-root", str(repo), "--allowlist", str(tmp_path / "absent-allowlist.txt")])
    assert rc == 1


def test_innocence_clean_payload_exits_zero(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path)
    (repo / "wrapper.sh").write_text("REPO=\"$HOME/nuzantara\"\n")
    git_add(repo, "wrapper.sh")
    rc = lint.main(["--repo-root", str(repo), "--allowlist", str(tmp_path / "absent-allowlist.txt")])
    assert rc == 0


def test_innocence_allowlisted_path_never_flagged(tmp_path: Path) -> None:
    """A file with a genuine hit is silent when declared in the allowlist —
    the guard-test-corpus / historical-record exception mechanism."""
    repo = make_git_repo(tmp_path)
    (repo / "legacy_test.py").write_text('MARKER = "/Users/x/Desktop/nuzantara/scripts/x.sh"\n')
    git_add(repo, "legacy_test.py")
    allowlist = tmp_path / "allowlist.txt"
    allowlist.write_text("# deliberate exception\nlegacy_test.py\n")
    rc = lint.main(["--repo-root", str(repo), "--allowlist", str(allowlist)])
    assert rc == 0


def test_innocence_out_of_scope_extension_not_flagged(tmp_path: Path) -> None:
    """A .md/.json file citing the old path is NOT in this lint's scope
    (deliberately narrower than the one-time sweep) — only *.sh/*.py/*.plist."""
    repo = make_git_repo(tmp_path)
    (repo / "notes.md").write_text("cd ~/Desktop/nuzantara\n")
    (repo / "data.json").write_text('{"path": "~/Desktop/nuzantara"}\n')
    git_add(repo, "notes.md", "data.json")
    rc = lint.main(["--repo-root", str(repo), "--allowlist", str(tmp_path / "absent-allowlist.txt")])
    assert rc == 0


def test_guilt_plist_payload_caught() -> None:
    assert ".plist" in lint.LINT_EXTENSIONS
    assert ".sh" in lint.LINT_EXTENSIONS
    assert ".py" in lint.LINT_EXTENSIONS
    assert ".md" not in lint.LINT_EXTENSIONS
    assert ".json" not in lint.LINT_EXTENSIONS


# ---------------------------------------------------------------- symlinks


def test_symlink_guilt_target_crossing_desktop_is_caught(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path)
    real = repo / "infra" / "launchagents"
    real.mkdir(parents=True)
    (real / "x.plist").write_text("<plist/>\n")
    link_target = "/Users/nuzantara/Desktop/nuzantara/infra/launchagents/x.plist"
    link = repo / "linked.plist"
    link.symlink_to(link_target)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    rc = lint.main(["--repo-root", str(repo), "--allowlist", str(tmp_path / "absent-allowlist.txt")])
    assert rc == 1


def test_symlink_innocence_target_elsewhere_not_flagged(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path)
    real = repo / "infra" / "launchagents"
    real.mkdir(parents=True)
    (real / "x.plist").write_text("<plist/>\n")
    link = repo / "linked.plist"
    link.symlink_to(str((real / "x.plist").resolve()))
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    rc = lint.main(["--repo-root", str(repo), "--allowlist", str(tmp_path / "absent-allowlist.txt")])
    assert rc == 0


# ---------------------------------------------------------------- exit contract


def test_blind_scan_git_failure_returns_two(tmp_path: Path) -> None:
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()
    rc = lint.main(["--repo-root", str(not_a_repo), "--allowlist", str(tmp_path / "absent-allowlist.txt")])
    assert rc == 2


def test_allowlist_unreadable_returns_four(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path)
    (repo / "wrapper.sh").write_text("REPO=\"$HOME/nuzantara\"\n")
    git_add(repo, "wrapper.sh")
    bad_allowlist = tmp_path / "allowlist-dir-not-file"
    bad_allowlist.mkdir()  # a directory where a file is expected -> OSError on read
    rc = lint.main(["--repo-root", str(repo), "--allowlist", str(bad_allowlist)])
    assert rc == 4


def test_allowlist_malformed_invalid_utf8_returns_four_not_crash(tmp_path: Path) -> None:
    """DEFECT found 2026-07-16 alongside DEFECT 1 (default-allowlist-not-loaded):
    _load_exclude's read_text(encoding="utf-8") raises UnicodeDecodeError on
    genuinely malformed content, which is NOT an OSError subclass — the
    original except OSError clause let it propagate as an uncaught traceback
    instead of the documented fail-visible exit 4. A crash is an even more
    silent failure mode than a wrong exit code (CI systems treat crash vs.
    "exit 4 with a clear message" very differently)."""
    repo = make_git_repo(tmp_path)
    (repo / "wrapper.sh").write_text("REPO=\"$HOME/nuzantara\"\n")
    git_add(repo, "wrapper.sh")
    bad_allowlist = tmp_path / "malformed-allowlist.txt"
    bad_allowlist.write_bytes(b"\xff\xfe\x00\x01not valid utf-8 \x80\x81\n")
    rc = lint.main(["--repo-root", str(repo), "--allowlist", str(bad_allowlist)])
    assert rc == 4


# ---------------------------------------------------------------- default-path resolution (DEFECT 1+2, 2026-07-16)
#
# Every test above explicitly overrides BOTH --repo-root and --allowlist,
# which is exactly why the two defects the coordinator found in final-gate
# review (default allowlist never loads; wrong-tree root resolution) shipped
# with "22/22 tests passing" — none of them ever exercised the CLI's default
# argument resolution. These tests close that gap: they invoke with argv that
# deliberately leaves --repo-root and/or --allowlist unset, so the tool's own
# defaulting logic is what's under test, not a value the test handed it.


def test_default_allowlist_relative_to_repo_root_loads_without_override(tmp_path: Path) -> None:
    """--allowlist omitted entirely: the tool must derive
    <repo-root>/infra/tcc-desktop-paths/allowlist.txt from whatever
    --repo-root resolved to (default OR overridden) and actually load it —
    not print "(allowlist: none)" while silently treating every declared
    exception as absent (DEFECT 1)."""
    repo = make_git_repo(tmp_path)
    (repo / "legacy_test.py").write_text('MARKER = "/Users/x/Desktop/nuzantara/scripts/x.sh"\n')
    git_add(repo, "legacy_test.py")
    allowlist_dir = repo / "infra" / "tcc-desktop-paths"
    allowlist_dir.mkdir(parents=True)
    (allowlist_dir / "allowlist.txt").write_text("# deliberate exception\nlegacy_test.py\n")
    git_add(repo, "infra/tcc-desktop-paths/allowlist.txt")

    rc = lint.main(["--repo-root", str(repo)])  # NOTE: no --allowlist at all
    assert rc == 0


def test_default_allowlist_relative_to_repo_root_still_catches_undeclared(tmp_path: Path) -> None:
    """Same fixture shape as above, but the violation is NOT declared —
    proves the previous test's RC==0 is a real suppression, not the guard
    going blind."""
    repo = make_git_repo(tmp_path)
    (repo / "legacy_test.py").write_text('MARKER = "/Users/x/Desktop/nuzantara/scripts/x.sh"\n')
    git_add(repo, "legacy_test.py")
    allowlist_dir = repo / "infra" / "tcc-desktop-paths"
    allowlist_dir.mkdir(parents=True)
    (allowlist_dir / "allowlist.txt").write_text("# no exceptions declared\n")
    git_add(repo, "infra/tcc-desktop-paths/allowlist.txt")

    rc = lint.main(["--repo-root", str(repo)])
    assert rc == 1


def test_canonical_root_resolves_to_wherever_this_file_lives_not_worktree_hardened(tmp_path: Path) -> None:
    """Regression test for DEFECT 2: copy the lint + its migrator sibling into
    a fixture path that nests them under a `.worktrees/<lane>/` ancestor (the
    exact shape of a real agent worktree, e.g.
    .worktrees/infra-tcc-repo-paths/scripts/lint_tcc_desktop_paths.py) and
    import THAT copy. Its computed REPO_ROOT must be the fixture's own
    worktree-shaped root — NOT jump out of .worktrees/ to some ancestor —
    because this tool does a single self-contained tree scan and must always
    lint the tree it was invoked from."""
    fake_worktree = tmp_path / ".worktrees" / "some-lane"
    fake_scripts = fake_worktree / "scripts"
    fake_scripts.mkdir(parents=True)
    real_scripts = _MODULE_PATH.resolve().parent
    for name in ("lint_tcc_desktop_paths.py", "tcc_migrate_desktop_paths.py"):
        (fake_scripts / name).write_text((real_scripts / name).read_text(encoding="utf-8"))

    spec = importlib.util.spec_from_file_location(
        "lint_tcc_desktop_paths_worktree_copy", fake_scripts / "lint_tcc_desktop_paths.py"
    )
    assert spec is not None and spec.loader is not None
    fake_lint = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fake_lint)

    assert fake_lint.REPO_ROOT == fake_worktree, (
        f"expected worktree-local root {fake_worktree}, got {fake_lint.REPO_ROOT} "
        "(DEFECT 2 regressed: root jumped out of .worktrees/)"
    )


def test_triple_proof_clean_dirty_clean_again(tmp_path: Path) -> None:
    """The coordinator's canonical final-gate probe, automated: a guard that
    reports FAIL regardless of whether the regression is present or absent
    proves nothing. This walks all three states in one fixture and asserts
    each transition explicitly."""
    repo = make_git_repo(tmp_path)
    (repo / "existing.sh").write_text("echo hi\n")
    git_add(repo, "existing.sh")
    absent_allowlist = tmp_path / "absent-allowlist.txt"

    rc_clean = lint.main(["--repo-root", str(repo), "--allowlist", str(absent_allowlist)])
    assert rc_clean == 0, "state 1 (clean repo) must be RC 0"

    regression = repo / "scripts"
    regression.mkdir()
    (regression / "bad.sh").write_text('REPO="$HOME/Desktop/nuzantara"\n')
    git_add(repo, "scripts/bad.sh")
    rc_dirty = lint.main(["--repo-root", str(repo), "--allowlist", str(absent_allowlist)])
    assert rc_dirty == 1, "state 2 (regression present) must be RC 1"

    subprocess.run(["git", "rm", "-q", "-f", "scripts/bad.sh"], cwd=repo, check=True)
    rc_clean_again = lint.main(["--repo-root", str(repo), "--allowlist", str(absent_allowlist)])
    assert rc_clean_again == 0, "state 3 (regression removed) must be RC 0 again"


# ---------------------------------------------------------------- real repo smoke (documents current state)


def test_real_repo_allowlist_file_parses_and_scan_is_clean() -> None:
    """The actual allowlist shipped in this PR: every declared path must exist
    (no phantom entries — scar #6 discipline) and the real repo tree must be
    clean under it. Runs through main() with NO overrides (subprocess, real
    CLI defaults) rather than calling scan() directly — this is the actual
    dogfood check that DEFECT 1+2 slipped past, because the original version
    of this test computed repo_root via _MODULE_PATH.resolve().parents[2],
    which is ONE LEVEL TOO HIGH (parents[1] is the repo root; parents[2] is
    its parent) — the allowlist path it built never existed, so the test
    always hit the early "nothing to dogfood yet" return and silently
    no-op'd on every run, real repo or not. Fixed to run the actual script as
    a subprocess against the tree that contains it, so a future refactor
    can't reintroduce the same off-by-one without a visible RC mismatch."""
    real_repo_root = _MODULE_PATH.resolve().parents[1]
    allowlist_path = real_repo_root / "infra" / "tcc-desktop-paths" / "allowlist.txt"
    if not allowlist_path.exists():
        return  # nothing to dogfood yet in this checkout (pre-merge worktree without the file)
    proc = subprocess.run(
        [sys.executable, str(_MODULE_PATH)],
        cwd=real_repo_root, capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, (
        f"expected clean (RC 0) against the real tree, got RC {proc.returncode}\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "(allowlist: none)" not in proc.stdout, (
        "default allowlist path failed to load against the real tree — DEFECT 1 regressed\n"
        f"stdout:\n{proc.stdout}"
    )


# ---------------------------------------------------------------- mutation-sweep pins (2026-10-12)
#
# Each test below asserts a documented contract (module docstring + scan()
# docstring) with a guilt fixture and an innocence twin; expected numbers are
# counted by hand from the fixture, never read back from the implementation.

import json

NO_ALLOW = "absent-allowlist.txt"


def _run_json(repo: Path, tmp_path: Path, capsys, *extra: str) -> tuple[int, dict]:
    rc = lint.main(["--repo-root", str(repo), "--allowlist", str(tmp_path / NO_ALLOW), "--json", *extra])
    return rc, json.loads(capsys.readouterr().out)


def _run_text(repo: Path, tmp_path: Path, capsys, allowlist: Path | None = None) -> tuple[int, str, str]:
    al = allowlist if allowlist is not None else tmp_path / NO_ALLOW
    rc = lint.main(["--repo-root", str(repo), "--allowlist", str(al)])
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


def test_json_report_counts_walked_scope_files_and_occurrences(tmp_path: Path, capsys) -> None:
    repo = make_git_repo(tmp_path)
    # two occurrences on one file (guilt), a clean in-scope file, an out-of-scope file
    (repo / "bad.sh").write_text("a=~/Desktop/nuzantara/x\nb=~/Desktop/nuzantara-deploy/y\n")
    (repo / "good.py").write_text("print('hi')\n")
    (repo / "notes.md").write_text("Desktop/nuzantara\n")
    git_add(repo, "bad.sh", "good.py", "notes.md")
    rc, doc = _run_json(repo, tmp_path, capsys)
    assert rc == 1
    assert doc["schema"] == 1
    assert doc["walked"] == 2  # bad.sh + good.py; notes.md is out of scope
    assert doc["tracked_total"] == 3
    assert doc["git_failed"] is False
    assert doc["allowlist_error"] is None
    assert doc["violations"] == [{"path": "bad.sh", "detail": "2 occurrence(s)", "kind": "file"}]


def test_json_output_is_indented_two_spaces(tmp_path: Path, capsys) -> None:
    repo = make_git_repo(tmp_path)
    (repo / "good.sh").write_text("echo hi\n")
    git_add(repo, "good.sh")
    lint.main(["--repo-root", str(repo), "--allowlist", str(tmp_path / NO_ALLOW), "--json"])
    assert capsys.readouterr().out.startswith('{\n  "schema": 1,')


def test_text_mode_is_not_json(tmp_path: Path, capsys) -> None:
    repo = make_git_repo(tmp_path)
    (repo / "good.sh").write_text("echo hi\n")
    git_add(repo, "good.sh")
    rc, out, _ = _run_text(repo, tmp_path, capsys)
    assert rc == 0
    assert out.startswith("[tcc-desktop-paths] scanned 1 tracked")
    assert "clean — no tracked payload hardcodes Desktop/nuzantara" in out
    assert "FAIL" not in out and "[error]" not in out


def test_text_mode_violation_prints_fail_and_not_clean(tmp_path: Path, capsys) -> None:
    repo = make_git_repo(tmp_path)
    (repo / "bad.sh").write_text('R="$HOME/Desktop/nuzantara"\n')
    git_add(repo, "bad.sh")
    rc, out, _ = _run_text(repo, tmp_path, capsys)
    assert rc == 1
    assert "  - bad.sh: 1 occurrence(s)" in out
    assert "TCC-DESKTOP-PATHS LINT FAIL" in out
    assert "clean —" not in out


def test_allowlist_error_prints_error_never_clean(tmp_path: Path, capsys) -> None:
    repo = make_git_repo(tmp_path)
    (repo / "good.sh").write_text("echo hi\n")
    git_add(repo, "good.sh")
    bad = tmp_path / "al-dir"
    bad.mkdir()
    rc, out, _ = _run_text(repo, tmp_path, capsys, allowlist=bad)
    assert rc == 4
    assert "[error] allowlist unreadable" in out
    assert "clean —" not in out
    assert "FAIL" not in out


def test_git_failure_reports_blind_scan_with_zero_counts(tmp_path: Path, capsys) -> None:
    not_a_repo = tmp_path / "plain-dir"
    not_a_repo.mkdir()
    rc, doc = _run_json(not_a_repo, tmp_path, capsys)
    assert rc == 2
    assert doc["git_failed"] is True
    assert doc["walked"] == 0
    assert doc["tracked_total"] == 0
    assert doc["violations"] == []


def test_git_failure_text_mode_says_so_and_never_clean(tmp_path: Path, capsys) -> None:
    not_a_repo = tmp_path / "plain-dir"
    not_a_repo.mkdir()
    rc, out, err = _run_text(not_a_repo, tmp_path, capsys)
    assert rc == 2
    assert "[error] git ls-files failed" in out
    assert "clean —" not in out
    assert "BLIND SCAN" in err


def test_empty_repo_with_no_tracked_files_is_blind_not_clean(tmp_path: Path, capsys) -> None:
    """git works, tracked_total == 0: wrong/empty root is a blind scan (rc 2)."""
    repo = make_git_repo(tmp_path)
    rc, out, err = _run_text(repo, tmp_path, capsys)
    assert rc == 2
    assert "BLIND SCAN" in err


def test_tracked_files_all_out_of_scope_is_clean_not_blind(tmp_path: Path, capsys) -> None:
    """Innocence twin of the previous test: tracked_total > 0 but nothing in
    scope (walked == 0) is a legitimate clean state, rc 0."""
    repo = make_git_repo(tmp_path)
    (repo / "README.md").write_text("Desktop/nuzantara\n")
    git_add(repo, "README.md")
    rc, doc = _run_json(repo, tmp_path, capsys)
    assert rc == 0
    assert doc["walked"] == 0
    assert doc["tracked_total"] == 1


def test_uppercase_extension_is_in_scope(tmp_path: Path, capsys) -> None:
    repo = make_git_repo(tmp_path)
    (repo / "RUN.SH").write_text("cd ~/Desktop/nuzantara\n")
    git_add(repo, "RUN.SH")
    rc, doc = _run_json(repo, tmp_path, capsys)
    assert rc == 1
    assert [v["path"] for v in doc["violations"]] == ["RUN.SH"]


def test_binary_in_scope_file_is_skipped_without_crash_and_still_walked(tmp_path: Path, capsys) -> None:
    repo = make_git_repo(tmp_path)
    (repo / "blob.py").write_bytes(b"\xff\xfe\x00Desktop/nuzantara\x80")
    git_add(repo, "blob.py")
    rc, doc = _run_json(repo, tmp_path, capsys)
    assert rc == 0
    assert doc["violations"] == []
    assert doc["walked"] == 1


def test_tracked_file_missing_from_disk_is_not_walked(tmp_path: Path, capsys) -> None:
    repo = make_git_repo(tmp_path)
    (repo / "gone.sh").write_text("cd ~/Desktop/nuzantara\n")
    (repo / "kept.sh").write_text("echo ok\n")
    git_add(repo, "gone.sh", "kept.sh")
    (repo / "gone.sh").unlink()
    rc, doc = _run_json(repo, tmp_path, capsys)
    assert rc == 0
    assert doc["walked"] == 1
    assert doc["tracked_total"] == 2


def test_symlink_violation_is_reported_once_with_kind_symlink(tmp_path: Path, capsys) -> None:
    """A symlink whose raw target crosses Desktop is one 'symlink' violation —
    and the file behind it must NOT be scanned a second time as the link."""
    repo = make_git_repo(tmp_path)
    real_dir = repo / "Desktop" / "nuzantara"
    real_dir.mkdir(parents=True)
    (real_dir / "x.sh").write_text("echo clean\n")
    (repo / "link.sh").symlink_to("Desktop/nuzantara/x.sh")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    rc, doc = _run_json(repo, tmp_path, capsys)
    assert rc == 1
    assert doc["walked"] == 2  # x.sh and link.sh, each exactly once
    assert doc["violations"] == [
        {
            "path": "link.sh",
            "detail": "symlink target crosses Desktop: 'Desktop/nuzantara/x.sh'",
            "kind": "symlink",
        }
    ]


def test_clean_symlink_is_walked_but_not_a_violation(tmp_path: Path, capsys) -> None:
    repo = make_git_repo(tmp_path)
    (repo / "x.sh").write_text("echo ok\n")
    (repo / "link.sh").symlink_to("x.sh")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    rc, doc = _run_json(repo, tmp_path, capsys)
    assert rc == 0
    assert doc["walked"] == 2
    assert doc["violations"] == []


def test_symlink_with_nonscope_extension_is_ignored(tmp_path: Path, capsys) -> None:
    repo = make_git_repo(tmp_path)
    (repo / "doc.txt").symlink_to("Desktop/nuzantara/x")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    (repo / "keep.sh").write_text("echo ok\n")
    git_add(repo, "keep.sh")
    rc, doc = _run_json(repo, tmp_path, capsys)
    assert rc == 0
    assert doc["walked"] == 1


def test_dangling_symlink_is_still_walked_and_flagged(tmp_path: Path, capsys) -> None:
    repo = make_git_repo(tmp_path)
    (repo / "dangling.plist").symlink_to("/Users/x/Desktop/nuzantara/missing.plist")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    rc, doc = _run_json(repo, tmp_path, capsys)
    assert rc == 1
    assert doc["walked"] == 1
    assert doc["violations"][0]["kind"] == "symlink"


def test_deploy_variant_flagged_but_longer_names_are_not(tmp_path: Path, capsys) -> None:
    repo = make_git_repo(tmp_path)
    (repo / "deploy.sh").write_text("cd ~/Desktop/nuzantara-deploy\n")
    (repo / "other.sh").write_text("cd ~/Desktop/nuzantara-archive\ncd ~/Desktop/nuzantara_x\n")
    git_add(repo, "deploy.sh", "other.sh")
    rc, doc = _run_json(repo, tmp_path, capsys)
    assert rc == 1
    assert [v["path"] for v in doc["violations"]] == ["deploy.sh"]
