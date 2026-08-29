"""Guilt+innocence+replay corpus for scripts/ci/pr_collision_check.py (PR-3,
L06-ci-merge-queue-ship-pipeline.md).

The mandate for this PR posed a CONTRADICTION between the spec's Acceptance
line ("replay of the #4783/#4782 pair ... does NOT flag") and
MEMORY_MERGE_QUEUE_TRAPS.md's trap #11, which measured that pair's SECOND
hunk as a genuine add/add overlap that SURVIVES merge-base anchoring. This
file resolves it by measurement, not by obedience:
`test_replay_4783_4782_flags_contradicting_spec_acceptance_line` below uses
the ACTUAL hunk headers fetched live on 2026-08-29 via
`gh api repos/Bali-Zero/Teman2/pulls/{4783,4782}/files --jq
'.[] | select(.filename==".claude/skills/modus/PENDING-ARMS.md") | .patch'`
— `@@ -1271,6 +1271,7 @@` (PR #4783) and `@@ -1272,6 +1272,7 @@` (PR #4782)
— and asserts the tool FLAGS. It does. The spec's Acceptance line is
imprecise; the trap corpus (and this replay) are the ground truth this tool
follows. Body text in the fixtures below is trimmed (only the hunk header
line numbers are load-bearing for this discriminator) but the header VALUES
are copy-pasted verbatim from that live API call, not invented.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import pr_collision_check as pcc  # noqa: E402

PENDING_ARMS = ".claude/skills/modus/PENDING-ARMS.md"
EVIDENCE_PACK = "evidence/pack.yml"


# ── pure-function unit tests ────────────────────────────────────────────────


def test_pure_insert_hunk_yields_one_window() -> None:
    patch = "@@ -18,3 +18,4 @@\n line18\n line19\n line20\n+new line\n"
    assert pcc.parse_add_windows_for_hunks(patch) == [(18, 21)]


def test_pure_deletion_hunk_yields_no_window() -> None:
    """delete/delete is out of scope by design — no '+' line, no window."""
    patch = "@@ -5,3 +5,1 @@\n line5\n-line6\n-line7\n"
    assert pcc.parse_add_windows_for_hunks(patch) == []


def test_context_only_hunk_yields_no_window() -> None:
    patch = "@@ -5,3 +5,3 @@\n line5\n line6\n line7\n"
    assert pcc.parse_add_windows_for_hunks(patch) == []


def test_windows_overlap_true_and_false() -> None:
    assert pcc.windows_overlap((10, 20), (15, 25)) is True
    assert pcc.windows_overlap((10, 20), (20, 30)) is False  # half-open, touching = no overlap
    assert pcc.windows_overlap((10, 20), (5, 10)) is False
    assert pcc.windows_overlap((10, 20), (12, 14)) is True  # fully contained


def test_multi_file_diff_splits_on_diff_git_boundary() -> None:
    patch = (
        "diff --git a/x.txt b/x.txt\n--- a/x.txt\n+++ b/x.txt\n"
        "@@ -1,1 +1,2 @@\n line1\n+added-x\n"
        "diff --git a/y.txt b/y.txt\n--- a/y.txt\n+++ b/y.txt\n"
        "@@ -9,1 +9,2 @@\n line9\n+added-y\n"
    )
    result = pcc.parse_multi_file_diff(patch)
    assert result == {"x.txt": [(1, 2)], "y.txt": [(9, 10)]}


# ── zero-width windows: pure-addition hunks (new-file / -U0 insert) ────────
# `old_len` is 0 for BOTH shapes below: a brand-new file's `@@ -0,0 ...@@`
# and a `-U0` pure insertion into an existing file. Without `max(old_len,
# 1)` clamping the old-side span to nonempty, both degrade to a zero-width
# window that `windows_overlap`'s strict `<` can never report as True.


def test_new_file_hunk_yields_nonempty_window_not_zero_width() -> None:
    """A brand-new file (`@@ -0,0 +1,N @@`) has old_len=0 -- exactly the
    W125 shape (two Gear>=2 PRs each adding evidence/brief.yml)."""
    patch = "@@ -0,0 +1,3 @@\n+a\n+b\n+c\n"
    assert pcc.parse_add_windows_for_hunks(patch) == [(0, 1)]


def test_pure_u0_insertion_hunk_yields_nonempty_window_not_zero_width() -> None:
    """A `-U0` pure insertion into an EXISTING file also has old_len=0 --
    a different input shape guarded by the same max(old_len, 1) clamp."""
    patch = "@@ -1271,0 +1272,1 @@\n+new line\n"
    assert pcc.parse_add_windows_for_hunks(patch) == [(1271, 1272)]


def test_two_new_file_additions_of_same_path_flag_the_w125_shape(tmp_path: Path) -> None:
    """W125's real shape: two PRs each ADDING evidence/brief.yml wholesale.
    Zero-width windows can never overlap, so an unclamped old_len makes
    this canonical collision silently invisible to find_collisions/main."""
    fixture = tmp_path / "w125_new_file.json"
    fixture.write_text(json.dumps({
        "prs": {
            "PR #100": {"evidence/brief.yml": "@@ -0,0 +1,3 @@\n+objective: one\n+l_level: L2\n+status: draft\n"},
            "PR #200": {"evidence/brief.yml": "@@ -0,0 +1,3 @@\n+objective: two\n+l_level: L1\n+status: draft\n"},
        }
    }))
    assert pcc.main(["--fixture", str(fixture)]) == 1
    windows = pcc.gather_fixture_pr_windows(fixture)
    collisions = pcc.find_collisions(windows)
    assert len(collisions) == 1
    assert collisions[0].path == "evidence/brief.yml"


# ── guilt: add/add overlapping windows on the same file ────────────────────


def test_add_add_overlap_flags_naming_both_prs_and_file() -> None:
    pr_files = {
        "PR #100": {PENDING_ARMS: [(1271, 1277)]},
        "PR #200": {PENDING_ARMS: [(1272, 1278)]},
    }
    collisions = pcc.find_collisions(pr_files)
    assert len(collisions) == 1
    c = collisions[0]
    assert c.path == PENDING_ARMS
    assert {c.pr_a, c.pr_b} == {"PR #100", "PR #200"}


# ── innocence: same file, modify/modify or add/add on DISJOINT lines ───────


def test_modify_modify_disjoint_lines_same_file_does_not_flag() -> None:
    """trap #11's own framing of the discriminator: two PRs touching the
    SAME file at lines far enough apart that their windows never overlap
    must NOT flag, regardless of same-file membership."""
    pr_files = {
        "PR #100": {"f.txt": [(5, 8)]},
        "PR #200": {"f.txt": [(55, 58)]},
    }
    assert pcc.find_collisions(pr_files) == []


def test_same_file_nonoverlapping_additions_far_apart_does_not_flag() -> None:
    pr_files = {
        "PR #100": {"f.txt": [(2, 5)]},
        "PR #200": {"f.txt": [(50, 53)]},
    }
    assert pcc.find_collisions(pr_files) == []


def test_single_file_touched_by_only_one_pr_never_a_candidate() -> None:
    pr_files = {"PR #100": {"f.txt": [(1271, 1277)]}}
    assert pcc.find_collisions(pr_files) == []


# ── CLI: open-PR set of one -> no output, exit 0 ───────────────────────────


def test_fixture_single_pr_exits_clean(tmp_path: Path) -> None:
    fixture = tmp_path / "one_pr.json"
    fixture.write_text(json.dumps({"prs": {"PR #1": {"f.txt": "@@ -1,1 +1,2 @@\n l1\n+x\n"}}}))
    assert pcc.main(["--fixture", str(fixture)]) == 0


def test_fixture_empty_prs_exits_clean(tmp_path: Path) -> None:
    fixture = tmp_path / "empty.json"
    fixture.write_text(json.dumps({"prs": {}}))
    assert pcc.main(["--fixture", str(fixture)]) == 0


# ── CANNOT-VERIFY: gh/git unreachable never reads as "0 collisions" ────────


def test_gh_unreachable_yields_cannot_verify_not_clean(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    def fake_run(cmd, cwd, check=True):
        if cmd[0] == "gh":
            raise pcc.CollisionCheckError("simulated: gh api unreachable")
        return "deadbeef\n"

    monkeypatch.setattr(pcc, "_run", fake_run)
    rc = pcc.main(["--repo-root", str(tmp_path)])
    captured = capsys.readouterr()
    assert rc == 2
    assert "CANNOT VERIFY" in captured.err
    # never silence, never a clean-looking pass on stdout
    assert captured.out == ""


def test_run_missing_binary_raises_collision_check_error_not_oserror(tmp_path: Path) -> None:
    """A missing `gh` binary (or any subprocess launch failure) must land as
    CollisionCheckError -- caught by main() as exit 2 -- never escape as a
    raw OSError that crashes with exit 1, the same exit code as "collision
    found". Exercises the REAL `_run()`, not a monkeypatched stand-in."""
    with pytest.raises(pcc.CollisionCheckError):
        pcc._run(["definitely-not-a-real-binary-xyz123"], tmp_path)


# ── replay: the real #4783/#4782 pair (trap #11), header values verbatim ──


def test_replay_4783_4782_flags_contradicting_spec_acceptance_line(tmp_path: Path) -> None:
    """Ground truth measured 2 ways, both agreeing with trap #11 and against
    the spec's Acceptance-line paraphrase: (1) MEMORY_MERGE_QUEUE_TRAPS.md
    #11 itself documents the second hunk as a real add/add conflict; (2) a
    live `gh api .../pulls/{n}/files` call on 2026-08-29 reproduced the
    exact same header values independently. This tool follows the measured
    ground truth, not the spec's paraphrase of it."""
    fixture = tmp_path / "trap11.json"
    fixture.write_text(json.dumps({
        "prs": {
            "PR #4783": {PENDING_ARMS: "@@ -1271,6 +1271,7 @@\n"
                         " l1\n l2\n l3\n l4\n l5\n l6\n+opened 2026-08-24 (P04-D4 ...)\n"},
            "PR #4782": {PENDING_ARMS: "@@ -1272,6 +1272,7 @@\n"
                         " l1\n l2\n l3\n l4\n l5\n l6\n+opened 2026-08-24 (P04-D3 slice 3a ...)\n"},
        }
    }))
    assert pcc.main(["--fixture", str(fixture)]) == 1
    windows = pcc.gather_fixture_pr_windows(fixture)
    collisions = pcc.find_collisions(windows)
    assert len(collisions) == 1
    assert collisions[0].path == PENDING_ARMS
    assert {collisions[0].pr_a, collisions[0].pr_b} == {"PR #4783", "PR #4782"}


def test_replay_c1_w125_evidence_pack_flags_serialize_the_second(tmp_path: Path) -> None:
    """#4673 and #4678 both regenerate evidence/pack.yml wholesale from line
    1 (measured: #4673 -64+/-206 lines, #4678 -80+/-121 lines against their
    own merge-bases) — collision by construction. Hunk shapes below mirror
    that: both start at old line 1, both span nearly the whole prior file."""
    fixture = tmp_path / "c1_w125.json"
    fixture.write_text(json.dumps({
        "prs": {
            "PR #4673": {EVIDENCE_PACK: "@@ -1,206 +1,64 @@\n" + "-old\n" * 3 + "+new-4673\n"},
            "PR #4678": {EVIDENCE_PACK: "@@ -1,121 +1,80 @@\n" + "-old\n" * 3 + "+new-4678\n"},
        }
    }))
    assert pcc.main(["--fixture", str(fixture)]) == 1


# ── the "merely behind" trap: a synthetic 3-branch git fixture ─────────────


def _git(cwd: Path, *args: str) -> None:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stderr}"


def _write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_being_behind_repo(repo: Path) -> dict[str, str]:
    """ancestor A (20 lines, L10='SHARED-OLD') -> main advances to B (L10
    changed, an unrelated third-party PR) while feature-a/feature-b branch
    off A and each ONLY append a new line 21 -- neither touches L10 at all.
    Returns {"main": B_sha, "feature_a": C_sha, "feature_b": D_sha}."""
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "pr-collision-e2e@test.invalid")
    _git(repo, "config", "user.name", "pr-collision e2e")
    f = repo / "f.txt"
    base_lines = [f"L{i}" if i != 10 else "SHARED-OLD" for i in range(1, 21)]
    _write_lines(f, base_lines)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "A: ancestor, 20 lines")
    _git(repo, "branch", "feature-a")
    _git(repo, "branch", "feature-b")

    _write_lines(f, [line if i != 10 else "SHARED-NEW" for i, line in enumerate(base_lines, start=1)])
    _git(repo, "commit", "-am", "B: main-only, unrelated PR changes L10")
    main_sha = subprocess.run(["git", "rev-parse", "main"], cwd=repo, capture_output=True, text=True).stdout.strip()

    _git(repo, "checkout", "feature-a")
    _write_lines(f, base_lines + ["feature-a-addition"])
    _git(repo, "commit", "-am", "C: feature-a appends line 21")
    fa_sha = subprocess.run(["git", "rev-parse", "feature-a"], cwd=repo, capture_output=True, text=True).stdout.strip()

    _git(repo, "checkout", "feature-b")
    _write_lines(f, base_lines + ["feature-b-addition"])
    _git(repo, "commit", "-am", "D: feature-b appends line 21")
    fb_sha = subprocess.run(["git", "rev-parse", "feature-b"], cwd=repo, capture_output=True, text=True).stdout.strip()

    return {"main": main_sha, "feature_a": fa_sha, "feature_b": fb_sha}


def test_merge_base_anchoring_defuses_being_behind_and_catches_real_overlap(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    shas = _build_being_behind_repo(repo)

    # CORRECT (merge-base-anchored): feature-a vs main shows ONLY its own
    # append -- no phantom hunk near the L10 line it never touched.
    merge_base_a, windows_a = pcc.pr_windows_from_git(repo, shas["main"], shas["feature_a"])
    # merge-base(main, feature-a) is ancestor A, NOT main's tip B -- feature_a
    # branched off A before B (main-only, unrelated PR) landed.
    assert merge_base_a != shas["main"]
    assert len(merge_base_a) == 40
    assert windows_a.keys() == {"f.txt"}
    assert len(windows_a["f.txt"]) == 1
    # 20-line file, default 3-line context around a pure trailing append:
    # old-side window is [18, 21) -- nowhere near line 10.
    assert windows_a["f.txt"][0] == (18, 21)

    # Sibling feature-b's real overlap with feature-a IS caught (both anchor
    # to the same merge-base A, both append at the identical position).
    merge_base_b, windows_b = pcc.pr_windows_from_git(repo, shas["main"], shas["feature_b"])
    assert merge_base_b == merge_base_a  # both branched off the SAME ancestor A
    found = pcc.find_collisions({"PR feature-a": windows_a, "PR feature-b": windows_b})
    assert len(found) == 1
    assert found[0].path == "f.txt"

    # MUTATION-SHAPED CONTROL, run inline: a NAIVE two-dot diff (main's tip,
    # not the merge-base) against the SAME feature-a DOES resurrect the
    # phantom L10 hunk -- this is exactly what pr_windows_from_git's
    # `resolve_merge_base()` call exists to defuse. Proven here without
    # touching the module's source (see the mutation-testing note in the
    # module docstring for the source-level version of this same check).
    naive_patch = pcc._run(["git", "diff", "--no-renames", shas["main"], shas["feature_a"]], repo)
    naive_windows = pcc.parse_multi_file_diff(naive_patch)
    assert len(naive_windows["f.txt"]) == 2, (
        "naive two-dot diff should show BOTH the phantom L10 hunk and the "
        "real append -- if this drops to 1, git's diff algorithm merged the "
        "hunks and the test needs a wider gap, not that the trap disappeared"
    )


# ── FIX 2: a malformed --fixture must be CANNOT VERIFY, never "collision
# found" ─────────────────────────────────────────────────────────────────


def test_malformed_fixture_json_yields_cannot_verify_not_collision_found(
    tmp_path: Path, capsys
) -> None:
    """A truncated/malformed --fixture must raise json.JSONDecodeError
    inside gather_fixture_pr_windows and land as exit 2 (CANNOT VERIFY) --
    never exit 1, which is documented to mean 'collisions found'. Before
    the FIX-2 patch, this escaped main()'s bare `except CollisionCheckError`
    as a raw traceback that happened to exit 1 -- the same code as a real
    finding."""
    fixture = tmp_path / "broken.json"
    fixture.write_text('{"prs": {"PR #1": {"f.txt": "@@ -1,1 +1,2')  # truncated JSON
    rc = pcc.main(["--fixture", str(fixture)])
    captured = capsys.readouterr()
    assert rc == 2
    assert "CANNOT VERIFY" in captured.err
    assert captured.out == ""


def test_valid_fixture_with_real_collision_still_returns_one(tmp_path: Path) -> None:
    """Innocence guard on the FIX-2 patch: a well-formed fixture that DOES
    collide must still exit 1 -- the json.JSONDecodeError catch must not
    swallow a real finding into a false CANNOT VERIFY."""
    fixture = tmp_path / "valid_collision.json"
    fixture.write_text(json.dumps({
        "prs": {
            "PR #100": {PENDING_ARMS: "@@ -1271,6 +1271,7 @@\n" + " l\n" * 6 + "+x\n"},
            "PR #200": {PENDING_ARMS: "@@ -1272,6 +1272,7 @@\n" + " l\n" * 6 + "+y\n"},
        }
    }))
    assert pcc.main(["--fixture", str(fixture)]) == 1


# ── K7: "shared by 2+ PRs" must count genuinely-shared files, not every
# file touched by anyone. Measured pre-fix: 2 PRs on 2 DISJOINT files
# reported "2 file(s) shared" (the union), true value is 0 -- every clean
# run overstated its own scan coverage ──────────────────────────────────


def test_clean_run_shared_files_count_excludes_files_touched_by_only_one_pr(
    tmp_path: Path, capsys
) -> None:
    fixture = tmp_path / "k7.json"
    fixture.write_text(json.dumps({
        "prs": {
            "PR #1": {"a.txt": "@@ -1,1 +1,2 @@\n l1\n+x\n"},
            "PR #2": {"b.txt": "@@ -1,1 +1,2 @@\n l1\n+y\n"},
        }
    }))
    rc = pcc.main(["--fixture", str(fixture)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "0 file(s) genuinely shared" in captured.out


def test_report_shared_files_count_matches_files_touched_by_2plus_prs_end_to_end(
    tmp_path: Path, capsys
) -> None:
    """Sibling of the above with a nonzero, non-trivial count: 4 files
    total, only ONE ('shared.txt') touched by both PRs -- the reported
    count must be 1, not 4 (old union bug) and not 0 (undercounting a
    genuinely-shared-but-disjoint file)."""
    fixture = tmp_path / "k7b.json"
    fixture.write_text(json.dumps({
        "prs": {
            "PR #1": {
                "shared.txt": "@@ -1,1 +1,2 @@\n l1\n+x\n",
                "only-pr1.txt": "@@ -1,1 +1,2 @@\n l1\n+x\n",
            },
            "PR #2": {
                "shared.txt": "@@ -50,1 +50,2 @@\n l50\n+y\n",  # disjoint window, same file
                "only-pr2.txt": "@@ -1,1 +1,2 @@\n l1\n+y\n",
            },
        }
    }))
    rc = pcc.main(["--fixture", str(fixture)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "1 file(s) genuinely shared" in captured.out


# ── FIX 3: PRs with DIFFERENT merge-bases are NOT COMPARED, never folded
# into a silent "no collision" -- the tool must not claim a negative it
# has not earned (module docstring, COMPARABILITY) ─────────────────────


def test_different_merge_base_pair_is_not_compared_not_silently_clean(
    tmp_path: Path, capsys
) -> None:
    """Two PRs share PENDING_ARMS with windows that WOULD overlap if their
    merge-bases agreed -- but they declare DIFFERENT merge-bases, so this
    tool must record the pair as NOT COMPARED: not flagged (their windows
    are not in the same coordinate space, so "overlap" is not even a
    meaningful question), but also not silently folded into a confident
    '0 collisions'."""
    fixture = tmp_path / "diff_mb.json"
    fixture.write_text(json.dumps({
        "prs": {
            "PR #100": {
                "merge_base": "aaaaaaa",
                PENDING_ARMS: "@@ -10,4 +10,5 @@\n l\n l\n l\n l\n+x\n",
            },
            "PR #200": {
                "merge_base": "bbbbbbb",
                PENDING_ARMS: "@@ -11,4 +11,5 @@\n l\n l\n l\n l\n+y\n",
            },
        }
    }))
    rc = pcc.main(["--fixture", str(fixture)])
    captured = capsys.readouterr()
    assert rc == 0  # NOT flagged -- incomparable is not a finding
    assert "NOT COMPARED — 1 pair(s)" in captured.out
    assert "PR #100" in captured.out and "PR #200" in captured.out


def test_same_merge_base_overlapping_windows_still_flags_as_collision(
    tmp_path: Path,
) -> None:
    """Innocence guard on the FIX-3 patch: two PRs that DO share a
    merge-base and genuinely overlap must still be FLAGGED (exit 1) -- the
    comparability partition must not turn a real finding into a
    not-compared entry, and must not swallow it."""
    fixture = tmp_path / "same_mb_overlap.json"
    fixture.write_text(json.dumps({
        "prs": {
            "PR #100": {
                "merge_base": "shared-sha",
                PENDING_ARMS: "@@ -1271,6 +1271,7 @@\n" + " l\n" * 6 + "+x\n",
            },
            "PR #200": {
                "merge_base": "shared-sha",
                PENDING_ARMS: "@@ -1272,6 +1272,7 @@\n" + " l\n" * 6 + "+y\n",
            },
        }
    }))
    assert pcc.main(["--fixture", str(fixture)]) == 1


def test_same_merge_base_disjoint_windows_does_not_flag(tmp_path: Path, capsys) -> None:
    """Innocence guard, other direction: two PRs sharing a merge-base with
    genuinely disjoint windows must NOT flag, and must NOT be counted as
    not-compared either -- they WERE compared (comparably) and found
    disjoint, which is a different thing from never having been looked
    at."""
    fixture = tmp_path / "same_mb_disjoint.json"
    fixture.write_text(json.dumps({
        "prs": {
            "PR #100": {"merge_base": "shared-sha", "f.txt": "@@ -5,3 +5,4 @@\n l\n l\n l\n+x\n"},
            "PR #200": {"merge_base": "shared-sha", "f.txt": "@@ -55,3 +55,4 @@\n l\n l\n l\n+y\n"},
        }
    }))
    rc = pcc.main(["--fixture", str(fixture)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "NOT COMPARED — 0 pair(s)" in captured.out


def test_clean_report_wording_is_qualified_not_a_bare_guarantee(
    tmp_path: Path, capsys
) -> None:
    """A fully-clean run (0 collisions, 0 not-compared) must not print the
    OLD bare 'No add/add collisions found' sentence -- it must be
    qualified so a skim-reader cannot mistake it for an unconditional
    guarantee. Exact wording asserted here is the wording this PR ships;
    if it drifts, this test names what must still be true of it."""
    fixture = tmp_path / "fully_clean.json"
    fixture.write_text(json.dumps({"prs": {"PR #1": {"f.txt": "@@ -1,1 +1,2 @@\n l1\n+x\n"}}}))
    rc = pcc.main(["--fixture", str(fixture)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "No add/add collisions found (" not in captured.out  # the OLD unqualified phrase
    assert "genuinely shared" in captured.out
    assert "not a guarantee" in captured.out
    assert "NOT COMPARED — 0 pair(s)" in captured.out


def test_gather_fixture_pr_merge_base_defaults_and_declares(tmp_path: Path) -> None:
    fixture = tmp_path / "mb.json"
    fixture.write_text(json.dumps({
        "prs": {
            "PR #1": {"f.txt": "@@ -1,1 +1,2 @@\n l1\n+x\n"},  # no merge_base key
            "PR #2": {"merge_base": "deadbeef", "f.txt": "@@ -1,1 +1,2 @@\n l1\n+x\n"},
        }
    }))
    result = pcc.gather_fixture_pr_merge_base(fixture)
    assert result["PR #1"] == pcc.NO_MERGE_BASE_DECLARED
    assert result["PR #2"] == "deadbeef"


def test_gather_fixture_pr_merge_base_malformed_json_is_cannot_verify(tmp_path: Path) -> None:
    fixture = tmp_path / "broken_mb.json"
    fixture.write_text('{"prs": {"PR #1": {"merge_base": "x"')  # truncated
    with pytest.raises(pcc.CollisionCheckError):
        pcc.gather_fixture_pr_merge_base(fixture)


def test_find_collisions_and_uncompared_backward_compat_when_all_same_sentinel() -> None:
    """When every PR shares the SAME merge-base value (what every fixture
    that omits the key gets, via NO_MERGE_BASE_DECLARED), the partition-
    and-compare path must reproduce find_collisions's plain output exactly
    -- the backward-compat guarantee find_collisions_and_uncompared's own
    docstring makes."""
    pr_files = {
        "PR #100": {PENDING_ARMS: [(1271, 1277)]},
        "PR #200": {PENDING_ARMS: [(1272, 1278)]},
    }
    same_mb = {"PR #100": "x", "PR #200": "x"}
    collisions, not_compared = pcc.find_collisions_and_uncompared(pr_files, same_mb)
    assert collisions == pcc.find_collisions(pr_files)
    assert not_compared == []


# ── K9: `gh pr list --limit` truncation must be reported, never silently
# folded into "clean" -- the module docstring's own promise ────────────


def test_pr_list_truncated_at_limit_is_reported_not_silently_clean(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    limit = pcc.PR_LIST_LIMIT
    fake_prs = json.dumps([{"number": i} for i in range(1, limit + 1)])

    def fake_run(cmd, cwd, check=True):
        if cmd[:3] == ["gh", "pr", "list"]:
            return fake_prs
        if cmd[:2] == ["git", "rev-parse"]:
            return "deadbeef\n"
        if cmd[:2] == ["git", "fetch"]:
            return ""
        if cmd[:2] == ["git", "merge-base"]:
            return "deadbeef\n"
        if cmd[:2] == ["git", "diff"]:
            return ""  # no add hunks -- this test is about truncation, not windows
        raise AssertionError(f"unexpected command in fake_run: {cmd}")

    monkeypatch.setattr(pcc, "_run", fake_run)
    rc = pcc.main(["--repo-root", str(tmp_path)])
    captured = capsys.readouterr()
    assert rc == 0  # no collisions found -- but must not read as confident clean
    assert "SCAN TRUNCATED" in captured.out
    assert str(limit) in captured.out


def test_pr_list_below_limit_is_not_reported_as_truncated(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    """Innocence guard: a scan that returns FEWER PRs than the limit must
    NOT print the truncation line -- the heuristic must not fire on an
    ordinary small open-PR count."""
    fake_prs = json.dumps([{"number": 1}, {"number": 2}])

    def fake_run(cmd, cwd, check=True):
        if cmd[:3] == ["gh", "pr", "list"]:
            return fake_prs
        if cmd[:2] == ["git", "rev-parse"]:
            return "deadbeef\n"
        if cmd[:2] == ["git", "fetch"]:
            return ""
        if cmd[:2] == ["git", "merge-base"]:
            return "deadbeef\n"
        if cmd[:2] == ["git", "diff"]:
            return ""
        raise AssertionError(f"unexpected command in fake_run: {cmd}")

    monkeypatch.setattr(pcc, "_run", fake_run)
    rc = pcc.main(["--repo-root", str(tmp_path)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "SCAN TRUNCATED" not in captured.out
