"""Guilt + innocence for scripts/evidence/pii_receipt.py (S6 R6.7/R6.8).

Every fixture is a throwaway git repo built at runtime by the module's own
_synthetic_repo(); the "names" in it are assembled from lowercase fragments,
so no name-shaped literal exists in this file or in the module.

Executed on every PR that touches either file by guard-conformance.yml
("PII receipt generator guilt+innocence"): scripts-tests-sweep.yml is
continue-on-error and would never turn a check red.
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "evidence" / "pii_receipt.py"
_spec = importlib.util.spec_from_file_location("pii_receipt", _MODULE_PATH)
if _spec is None or _spec.loader is None:
    raise ImportError(f"cannot load {_MODULE_PATH}")
pr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pr)


def run(*argv: str) -> tuple[int, str, str]:
    proc = subprocess.run([sys.executable, str(_MODULE_PATH), *argv], capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def search1(pattern: str, text: str, flags: int = 0) -> str:
    match = re.search(pattern, text, flags)
    assert match is not None, pattern
    return match.group(1)


class Fx(NamedTuple):
    tmp: Path
    repo: Path
    private: Path
    names: list[str]
    tree: list[str]


@pytest.fixture()
def fx(tmp_path: Path) -> Fx:
    repo, private, names = pr._synthetic_repo(tmp_path)
    tree = ["tree", "--repo", str(repo), "--patterns", str(private / "names.txt"),
            "--categories", str(private / "cats.txt")]
    return Fx(tmp_path, repo, private, names, tree)


def paste(block: str, where: Path) -> None:
    where.write_text("receipts:\n  - result: |\n" + "".join("      " + ln + "\n" for ln in block.splitlines()))


def test_selftest_passes():
    assert run("--selftest")[0] == 0


def test_innocence_rerun_is_byte_identical_and_check_in_matches(fx):
    tmp, tree = fx.tmp, fx.tree
    rc, first, _ = run(*tree)
    assert rc == 0 and run(*tree)[1] == first
    paste(first, tmp / "pack.yml")
    assert run(*tree, "--check-in", str(tmp / "pack.yml"))[0] == 0


def test_guilt_hand_typed_count_is_a_mismatch_even_when_plausible(fx):
    tmp, tree = fx.tmp, fx.tree
    block = run(*tree)[1]
    paste(block.replace("files: 3", "files: 2"), tmp / "pack.yml")
    rc, _out, err = run(*tree, "--check-in", str(tmp / "pack.yml"))
    assert rc == 1 and "MISMATCH" in err


def test_guilt_other_invocation_has_no_block(fx):
    tmp, tree = fx.tmp, fx.tree
    paste(run(*tree)[1], tmp / "pack.yml")
    assert run(*tree, "--ignore-case", "--check-in", str(tmp / "pack.yml"))[0] == 4


def test_counts_are_the_documented_metrics(fx):
    out = run(*fx[4])[1]
    for line in ("files: 3", "hits: 5", "lines_any: 4", "occurrences: 6",
                 "patterns_present: 2", "patterns_absent: 1", "binary_files: 0",
                 "code: {files: 2, hits: 4, per_file: [2, 2]}",
                 "uncategorized: {files: 1, hits: 1, per_file: [1]}"):
        assert line in out.splitlines() or f"  {line}" in out.splitlines(), line


def test_binary_blobs_are_counted_apart_from_the_line_metrics(fx):
    repo, names, tree = fx.repo, fx.names, fx.tree
    (repo / "src/image.bin").write_bytes(b"\0" + names[2].encode() + b"\n")
    pr._commit(repo)
    out = run(*tree)[1].splitlines()
    assert "binary_files: 1" in out and "files: 3" in out and "hits: 5" in out
    assert "patterns_present: 3" in out


def test_salt_readable_by_others_is_refused(fx):
    private, tree = fx.private, fx.tree
    assert run(*tree)[0] == 0
    (private / pr.SALT_NAME).chmod(0o644)
    rc, _out, err = run(*tree)
    assert rc == 2 and "chmod 600" in err


def test_private_inputs_of_one_invocation_share_one_lane_dir(fx):
    tmp, private, tree = fx.tmp, fx.private, fx.tree
    other = tmp / "elsewhere"
    other.mkdir(mode=0o700)
    (other / "cats.txt").write_text((private / "cats.txt").read_text())
    rc, _out, err = run(*tree[:-1], str(other / "cats.txt"))
    assert rc == 2 and "same lane directory" in err


def test_pattern_lines_split_on_lf_like_grep_f_on_lf_input(fx):
    repo, private = fx.repo, fx.private
    (private / "ff.txt").write_bytes(b"a\rb\r\nc\n")
    out = run("tree", "--repo", str(repo), "--patterns", str(private / "ff.txt"))[1]
    assert "lines: 2}" in out


def test_block_never_carries_a_pattern_a_matched_path_or_a_private_path(fx):
    private, names, tree = fx.private, fx.names, fx.tree
    out = run(*tree)[1]
    for needle in names + ["src/one.py", "src/two.py", "tests/fixtures", str(private), "names.txt"]:
        assert needle not in out
    assert re.search(r"--patterns @hmac:[0-9a-f]{16} ", out)


def test_private_tokens_are_keyed_and_never_a_reversible_plain_hash(fx):
    import hashlib
    private, tree = fx.private, fx.tree
    out = run(*tree, "--path", "src/two.py")[1]
    salt = private / pr.SALT_NAME
    assert salt.exists() and (salt.stat().st_mode & 0o777) == 0o600
    assert "src/two.py" not in out and re.search(r"--path @hmac:[0-9a-f]{16}", out)
    plain = hashlib.sha256((private / "cats.txt").read_bytes()).hexdigest()[:16]
    before = run(*tree)[1]
    assert plain not in before
    salt.write_text("another-lane-salt")
    after = run(*tree)[1]
    assert after != before and plain not in after


def test_empty_pattern_lines_never_match_everything(fx):
    repo, private = fx.repo, fx.private
    (private / "blank.txt").write_text("\n\n")
    assert run("tree", "--repo", str(repo), "--patterns", str(private / "blank.txt"))[0] == 2


def test_tree_digest_ignores_evidence_and_moves_on_anything_else(fx):
    repo, tree = fx.repo, fx.tree
    before = run(*tree)[1]
    (repo / "evidence/x/journal.jsonl").write_text("{}\n")
    pr._commit(repo)
    assert run(*tree)[1] == before
    (repo / "docs/clean.md").write_text("edited\n")
    pr._commit(repo)
    assert run(*tree)[1] != before


def test_tree_digest_covers_the_whole_tree_even_under_a_path_scope(fx):
    repo, tree = fx.repo, fx.tree
    digest = lambda out: search1(r"^tree_digest: (\w+)$", out, re.M)
    assert digest(run(*tree, "--path", "src/two.py")[1]) == digest(run(*tree)[1])
    before = run(*tree, "--path", "src/two.py")[1]
    (repo / "docs/clean.md").write_text("outside the scope\n")
    pr._commit(repo)
    assert run(*tree, "--path", "src/two.py")[1] != before


def test_ignore_case_refuses_non_ascii_patterns(fx):
    repo, private = fx.repo, fx.private
    (private / "accent.txt").write_bytes(("caf" + chr(0xE9)).encode() + b"\n")
    rc, _out, err = run("tree", "--repo", str(repo), "--patterns", str(private / "accent.txt"), "--ignore-case")
    assert rc == 2 and "ASCII" in err


def test_redaction_probe_discriminates_a_no_op_redaction(fx):
    repo, private = fx.repo, fx.private
    probe = ["tree", "--repo", str(repo), "--patterns", str(private / "names.txt"), "--path", "src/two.py"]
    assert "files: 1" in run(*probe)[1]
    mb = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    (repo / "src/two.py").write_text("y = 'CLIENT-A' + 'CLIENT-B'\n")
    pr._commit(repo)
    assert "files: 0" in run(*probe)[1]
    assert "files: 1" in run(*probe[:5], "--rev", mb, "--path", "src/two.py")[1]


def test_r66_line_shape_hedges_and_host_independent_argv(tmp_path: Path):
    (tmp_path / "res.txt").write_text("one.py\n")
    (tmp_path / "brief.yml").write_text("measured 3 files\n~30 to 36 by two detectors\n")
    (tmp_path / "pack.yml").write_text("cites one.py once\nsomething unrelated\n")
    (tmp_path / "body.md").write_text("some files\nhandsome\n")
    rc, out, _ = run("r66", "--patterns", str(tmp_path / "res.txt"), "--brief", str(tmp_path / "brief.yml"),
                     "--pack", str(tmp_path / "pack.yml"), "--body", str(tmp_path / "body.md"))
    assert rc == 0
    line = search1(r'r66_line: "(.*)"', out)
    assert re.fullmatch(r"r66: hmac=[0-9a-f]{12} lines=1 residual_hits=1 hedge_hits=2", line)
    import hashlib
    assert hashlib.sha256((tmp_path / "res.txt").read_bytes()).hexdigest()[:12] not in out
    assert "hedge_hit_lines: [brief:2, body:1]" in out
    assert str(tmp_path) not in out
    assert re.search(r"--brief @text:[0-9a-f]{16} --pack PACK --body @text:[0-9a-f]{16}", out)


def test_r66_guilt_a_stale_block_after_a_brief_edit_has_no_matching_block(tmp_path: Path):
    (tmp_path / "res.txt").write_text("one.py\n")
    for name, body in (("brief.yml", "measured\n"), ("pack.yml", "\n"), ("body.md", "text\n")):
        (tmp_path / name).write_text(body)
    argv = ["r66", "--patterns", str(tmp_path / "res.txt"), "--brief", str(tmp_path / "brief.yml"),
            "--pack", str(tmp_path / "pack.yml"), "--body", str(tmp_path / "body.md")]
    paste(run(*argv)[1], tmp_path / "pack.yml")
    assert run(*argv, "--check-in", str(tmp_path / "pack.yml"))[0] == 0
    (tmp_path / "brief.yml").write_text("measured again, same counts\n")
    assert run(*argv, "--check-in", str(tmp_path / "pack.yml"))[0] == 4
    (tmp_path / "body.md").write_bytes(b"text\r\n\n")
    (tmp_path / "brief.yml").write_text("measured\n")
    assert run(*argv, "--check-in", str(tmp_path / "pack.yml"))[0] == 0


def test_r66_companion_id_check_is_word_bounded(tmp_path: Path):
    (tmp_path / "res.txt").write_text("nothing-matches\n")
    (tmp_path / "ids.txt").write_text("70\n")
    (tmp_path / "brief.yml").write_text("id 70 twice: 70\n")
    (tmp_path / "pack.yml").write_text("1970 and 703 are not ids\n")
    (tmp_path / "body.md").write_text("\n")
    out = run("r66", "--patterns", str(tmp_path / "res.txt"), "--ids", str(tmp_path / "ids.txt"),
              "--brief", str(tmp_path / "brief.yml"), "--pack", str(tmp_path / "pack.yml"),
              "--body", str(tmp_path / "body.md"))[1]
    assert "id_lines: 1, id_occurrences: 2}" in out


def test_descriptor_innocence_two_files_cover_their_category(fx):
    repo, private = fx.repo, fx.private
    rc, out, _ = run("descriptor", "--repo", str(repo), "--label", "code", "--categories",
                     str(private / "cats.txt"), "--category", "code", "--path", r"\.py$")
    assert rc == 0 and "files: 2" in out and "covers_category: 2/2" in out and "verdict: OK" in out


def test_descriptor_guilt_a_conjunction_that_narrows_to_one_file(fx):
    repo = fx.repo
    rc, out, _ = run("descriptor", "--repo", str(repo), "--label", "b", "--path", r"\.py$", "--text", " and ")
    assert rc == 3 and "progressive_files: [2, 1]" in out and "verdict: ISOLATING" in out


def test_guilt_a_pasted_isolating_block_still_fails_check_in(fx):
    tmp, repo = fx.tmp, fx.repo
    desc = ["descriptor", "--repo", str(repo), "--label", "b", "--path", r"\.py$", "--text", " and "]
    paste(run(*desc)[1], tmp / "pack.yml")
    rc, _out, err = run(*desc, "--check-in", str(tmp / "pack.yml"))
    assert rc == 3 and "MATCH" in err


def test_descriptor_guilt_a_two_file_predicate_that_misses_its_category(fx):
    repo, private = fx.repo, fx.private
    rc, out, _ = run("descriptor", "--repo", str(repo), "--label", "code",
                     "--categories", str(private / "cats.txt"), "--category", "code",
                     "--not-path", "^src/")
    assert rc == 3 and "files: 2" in out and "covers_category: 0/2" in out
    assert "verdict: NOT-COVERING\n" in out


@pytest.mark.parametrize("floor", ["1", "0", "-3"])
def test_descriptor_refuses_min_files_below_two(fx, floor):
    repo, private = fx.repo, fx.private
    rc, out, err = run("descriptor", "--repo", str(repo), "--label", "code", "--min-files", floor,
                       "--categories", str(private / "cats.txt"), "--category", "code", "--path", r"\.py$")
    assert rc == 2 and out == "" and "never below 2" in err


def test_descriptor_innocence_min_files_above_the_floor_is_accepted(fx):
    repo, private = fx.repo, fx.private
    rc, out, _ = run("descriptor", "--repo", str(repo), "--label", "code", "--min-files", "2",
                     "--categories", str(private / "cats.txt"), "--category", "code", "--path", r"\.py$")
    assert rc == 0 and "min_files: 2" in out and "verdict: OK\n" in out


def test_descriptor_without_categories_is_unmeasured_and_red_even_when_pasted(fx):
    tmp, repo = fx.tmp, fx.repo
    desc = ["descriptor", "--repo", str(repo), "--label", "code", "--path", r"\.py$"]
    rc, out, _ = run(*desc)
    assert rc == 3 and "files: 2" in out and "covers_category: n/a" in out
    assert "verdict: UNMEASURED\n" in out
    paste(out, tmp / "pack.yml")
    rc, _out, err = run(*desc, "--check-in", str(tmp / "pack.yml"))
    assert rc == 3 and "MATCH" in err


def test_descriptor_category_must_be_a_label_not_free_text(fx):
    repo, private = fx.repo, fx.private
    rc, out, err = run("descriptor", "--repo", str(repo), "--label", "code",
                       "--categories", str(private / "cats.txt"), "--category", "code files",
                       "--path", r"\.py$")
    assert rc == 2 and out == "" and "--category must match" in err


def test_descriptor_binary_blobs_leave_the_universe_and_are_counted(fx):
    repo = fx.repo
    (repo / "src/blob.py").write_bytes(b"x\0 and ")
    pr._commit(repo)
    out = run("descriptor", "--repo", str(repo), "--label", "b", "--path", r"\.py$", "--text", " and ")[1]
    assert "progressive_files: [2, 1]" in out and "binary_skipped: 1" in out
    out = run("descriptor", "--repo", str(repo), "--label", "b", "--path", r"\.py$")[1]
    assert "files: 2" in out and "binary_skipped: 1" in out


def test_descriptor_terms_are_evaluated_in_the_order_given(fx):
    repo = fx.repo
    path_first = run("descriptor", "--repo", str(repo), "--label", "o", "--path", r"\.py$", "--text", " and ")[1]
    text_first = run("descriptor", "--repo", str(repo), "--label", "o", "--text", " and ", "--path", r"\.py$")[1]
    assert "progressive_files: [2, 1]" in path_first and "progressive_files: [1, 1]" in text_first


def test_descriptor_digest_covers_files_outside_the_predicate(fx):
    repo = fx.repo
    desc = ["descriptor", "--repo", str(repo), "--label", "c", "--path", r"\.py$"]
    before = run(*desc)[1]
    (repo / "docs/clean.md").write_text("not a .py file\n")
    pr._commit(repo)
    after = run(*desc)[1]
    assert after != before and "files: 2" in after
    (repo / "evidence/x/pack.yml").write_text("an evidence-only edit\n")
    pr._commit(repo)
    assert run(*desc)[1] == after


def test_tree_digest_moves_on_a_mode_only_change(fx):
    repo, tree = fx.repo, fx.tree
    before = run(*tree)[1]
    (repo / "docs/clean.md").chmod(0o755)
    pr._commit(repo)
    assert run(*tree)[1] != before


def test_lane_directory_must_be_private(fx):
    private, tree = fx.private, fx.tree
    private.chmod(0o755)
    rc, _out, err = run(*tree)
    private.chmod(0o700)
    assert rc == 2 and "chmod 700" in err


def test_descriptor_excludes_evidence_from_its_universe(fx):
    repo = fx.repo
    out = run("descriptor", "--repo", str(repo), "--label", "e", "--path", r"\.yml$")[1]
    assert "files: 0" in out
