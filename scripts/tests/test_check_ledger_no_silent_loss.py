"""Guilt AND innocence for check_ledger_no_silent_loss.py.

Every test runs against a throwaway git repo under tmp_path — never the
real PENDING-ARMS.md (W96: tests must not touch production state, and this
repo's own conftest/immune-organ discipline exists precisely because of
that class of bug).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from check_ledger_no_silent_loss import check  # noqa: E402
from pending_arms_report import _parse_now  # noqa: E402

NOW = _parse_now("2026-08-08")

ENTRY_A = "- opened 2026-08-01 | **Entry A** | missing step A | me (sessione test) | proof A"
ENTRY_B = "- opened 2026-08-01 | **Entry B** | missing step B | me (sessione test) | proof B"
ENTRY_C = "- opened 2026-08-03 | **Entry C** | missing step C | me (sessione test) | proof C"


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-q", "-b", "main"], repo)
    _git(["config", "user.email", "test@example.com"], repo)
    _git(["config", "user.name", "Test"], repo)
    return repo


def _write_ledger(repo: Path, entries: list[str]) -> Path:
    ledger = repo / "PENDING-ARMS.md"
    ledger.write_text("\n\n".join(entries) + "\n", encoding="utf-8")
    return ledger


def _commit(repo: Path, message: str) -> None:
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", message], repo)


def _mark_as_origin_main(repo: Path) -> None:
    """Simulate a fetched origin/main ref without a real remote."""
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()
    _git(["update-ref", "refs/remotes/origin/main", sha], repo)


def test_guilt_a_bad_resolution_silently_drops_an_untouched_row(tmp_path):
    """The exact incident: main advances (another PR adds C), this branch's
    'resolution' keeps only its own view of the file and drops A — A was
    never touched by anyone, so its disappearance can only be the
    resolution itself, not a legitimate closure.
    """
    repo = _init_repo(tmp_path)
    ledger = _write_ledger(repo, [ENTRY_A, ENTRY_B])
    _commit(repo, "seed A+B")
    _mark_as_origin_main(repo)
    _git(["checkout", "-q", "-b", "feature"], repo)

    _git(["checkout", "-q", "main"], repo)
    _write_ledger(repo, [ENTRY_A, ENTRY_B, ENTRY_C])
    _commit(repo, "main: add C")
    _mark_as_origin_main(repo)

    _git(["checkout", "-q", "feature"], repo)
    _write_ledger(repo, [ENTRY_B])  # bad "resolution": drops A, never picks up C
    _commit(repo, "feature: bad hand-resolution")

    assert check(ledger, NOW) == 1


def test_innocence_a_clean_local_merge_carries_everything_forward(tmp_path):
    """The correct, documented procedure (`git merge origin/main`) picks up
    C automatically and leaves A+B untouched — no loss, no false alarm.
    """
    repo = _init_repo(tmp_path)
    ledger = _write_ledger(repo, [ENTRY_A, ENTRY_B])
    _commit(repo, "seed A+B")
    _mark_as_origin_main(repo)
    _git(["checkout", "-q", "-b", "feature"], repo)

    _git(["checkout", "-q", "main"], repo)
    _write_ledger(repo, [ENTRY_A, ENTRY_B, ENTRY_C])
    _commit(repo, "main: add C")
    _mark_as_origin_main(repo)

    _git(["checkout", "-q", "feature"], repo)
    _git(["merge", "-q", "main", "-m", "merge main"], repo)

    assert check(ledger, NOW) == 0


def test_innocence_a_legitimate_edit_in_place_is_not_a_removal(tmp_path):
    """Editing an entry's body (status/proof text) while keeping its
    (opened_date, title) identical must not read as a removal — this is the
    exact shape of PR #3831's own ledger update, same session: the
    ReDoS-timing entry's status text changed without the row being a
    'different' entry.
    """
    repo = _init_repo(tmp_path)
    ledger = _write_ledger(repo, [ENTRY_A, ENTRY_B])
    _commit(repo, "seed A+B")
    _mark_as_origin_main(repo)
    _git(["checkout", "-q", "-b", "feature"], repo)

    edited_a = (
        "- opened 2026-08-01 | **Entry A** | UPDATED missing step | "
        "me (sessione test) | UPDATED proof"
    )
    _write_ledger(repo, [edited_a, ENTRY_B])
    _commit(repo, "feature: update A's status text")

    assert check(ledger, NOW) == 0


def test_guilt_the_prescribed_merge_duplicates_a_row_both_sides_edited(tmp_path):
    """The incident of 2026-08-11, reproduced end-to-end through the REAL
    `git merge` with the REAL union driver — not a hand-written double line.

    Both sides edit entry A in place (the ordinary shape of this ledger: a
    row's body is updated as work progresses). Union keeps both versions,
    so the branch lands 3 rows where main and base have 2. The loss check
    is happy — nothing disappeared — and that is exactly why it cannot see
    this.
    """
    repo = _init_repo(tmp_path)
    (repo / ".gitattributes").write_text("PENDING-ARMS.md merge=union\n", encoding="utf-8")
    ledger = _write_ledger(repo, [ENTRY_A, ENTRY_B])
    _commit(repo, "seed A+B")
    _mark_as_origin_main(repo)
    _git(["checkout", "-q", "-b", "feature"], repo)

    _git(["checkout", "-q", "main"], repo)
    _write_ledger(repo, [ENTRY_A + " — amended on main", ENTRY_B])
    _commit(repo, "main: edit A in place")
    _mark_as_origin_main(repo)

    _git(["checkout", "-q", "feature"], repo)
    _write_ledger(repo, [ENTRY_A + " — amended on the branch", ENTRY_B])
    _commit(repo, "feature: edit A in place too")
    _git(["merge", "-q", "main", "-m", "merge main"], repo)

    # Precondition: the union driver really did duplicate A (if this ever
    # stops being true the test below would pass vacuously — W116).
    assert ledger.read_text(encoding="utf-8").count("**Entry A**") == 2

    assert check(ledger, NOW) == 2


def test_guilt_a_branch_that_lands_the_same_new_row_twice(tmp_path):
    """Two open rows with one identity are indistinguishable to every
    reader and counted twice by pending_arms_report — flag it even though
    no merge was involved and nothing was lost.
    """
    repo = _init_repo(tmp_path)
    ledger = _write_ledger(repo, [ENTRY_A])
    _commit(repo, "seed A")
    _mark_as_origin_main(repo)
    _git(["checkout", "-q", "-b", "feature"], repo)

    _write_ledger(repo, [ENTRY_A, ENTRY_C, ENTRY_C + " (second copy)"], )
    _commit(repo, "feature: adds C twice")

    assert check(ledger, NOW) == 2


def test_guilt_both_defects_at_once_report_both(tmp_path):
    """A branch can lose one row and duplicate another in the same tree;
    the bitmask must not hide either behind the other.
    """
    repo = _init_repo(tmp_path)
    ledger = _write_ledger(repo, [ENTRY_A, ENTRY_B])
    _commit(repo, "seed A+B")
    _mark_as_origin_main(repo)
    _git(["checkout", "-q", "-b", "feature"], repo)

    _write_ledger(repo, [ENTRY_B, ENTRY_B + " (duplicated)"])  # A lost, B doubled
    _commit(repo, "feature: loses A and doubles B")

    assert check(ledger, NOW) == 3


def test_innocence_a_row_already_duplicated_on_main_is_not_this_branch_s_fault(tmp_path):
    """main carries 3 such pairs TODAY (measured 2026-08-12). A baseline of
    zero would paint every ledger-touching PR red for someone else's
    duplication and the signal would be ignored within a week.
    """
    repo = _init_repo(tmp_path)
    ledger = _write_ledger(repo, [ENTRY_A, ENTRY_A + " (stale copy)", ENTRY_B])
    _commit(repo, "seed with a pre-existing duplicate")
    _mark_as_origin_main(repo)
    _git(["checkout", "-q", "-b", "feature"], repo)

    _write_ledger(repo, [ENTRY_A, ENTRY_A + " (stale copy)", ENTRY_B, ENTRY_C])
    _commit(repo, "feature: adds C, leaves the inherited duplicate alone")

    assert check(ledger, NOW) == 0


def test_innocence_adding_a_brand_new_row_is_the_ordinary_case(tmp_path):
    """1 copy > 0 on both references, and it must NEVER flag — this is what
    every ledger PR does. Without the `>= 2` clause the guard would fail
    100% of legitimate uses.
    """
    repo = _init_repo(tmp_path)
    ledger = _write_ledger(repo, [ENTRY_A, ENTRY_B])
    _commit(repo, "seed A+B")
    _mark_as_origin_main(repo)
    _git(["checkout", "-q", "-b", "feature"], repo)

    _write_ledger(repo, [ENTRY_A, ENTRY_B, ENTRY_C])
    _commit(repo, "feature: appends one new row")

    assert check(ledger, NOW) == 0


def test_innocence_removing_a_duplicate_copy_is_the_cure_not_the_disease(tmp_path):
    """Landing the fix — collapsing an inherited pair back to one live row —
    must read clean on BOTH invariants: the identity is still present (no
    loss) and its copies went down, not up.
    """
    repo = _init_repo(tmp_path)
    ledger = _write_ledger(repo, [ENTRY_A, ENTRY_A + " (stale copy)", ENTRY_B])
    _commit(repo, "seed with a pre-existing duplicate")
    _mark_as_origin_main(repo)
    _git(["checkout", "-q", "-b", "feature"], repo)

    _write_ledger(repo, [ENTRY_A, ENTRY_B])
    _commit(repo, "feature: keeps the live copy only")

    assert check(ledger, NOW) == 0


def test_innocence_a_frozen_base_sha_would_false_flag_a_legitimate_merge(tmp_path):
    """CI passes `pull_request.base.sha` — the PR's frozen fork point — to
    `--base-ref`. That SHA is structurally an ancestor of HEAD, so `check()`'s
    own `git merge-base(base_ref, head)` always resolves back to that SAME
    frozen commit and `main_entries` (loaded FROM `base_ref`) never reflects
    anything main did after this branch diverged.

    Reproduces the gap the CI workflow's original `--base-ref "$BASE_SHA"`
    invocation had (fixed 2026-08-30, second pass): main legitimately closes
    A after this branch forked, and this branch does the documented correct
    thing — `git merge origin/main` — which faithfully picks up that
    closure. Passing the FROZEN fork-point SHA as base_ref calls that a
    'loss'; passing a ref that reflects CURRENT main (this test's default —
    `_mark_as_origin_main` keeps `refs/remotes/origin/main` live, exactly
    matching a real CI checkout's fetched `origin/main`) correctly reads it
    as clean. Both invocations are exercised explicitly so a future change
    to either code path is caught by name, not just by the passing case.
    """
    repo = _init_repo(tmp_path)
    ledger = _write_ledger(repo, [ENTRY_A, ENTRY_B])
    _commit(repo, "seed A+B")
    fork_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()
    _mark_as_origin_main(repo)
    _git(["checkout", "-q", "-b", "feature"], repo)

    _git(["checkout", "-q", "main"], repo)
    _write_ledger(repo, [ENTRY_B])  # main: legitimately closes A
    _commit(repo, "main: legitimately closes A")
    _mark_as_origin_main(repo)

    _git(["checkout", "-q", "feature"], repo)
    _write_ledger(repo, [ENTRY_A, ENTRY_B, ENTRY_C])
    _commit(repo, "feature: adds C")
    _git(["merge", "-q", "main", "-m", "feature: merge origin/main"], repo)  # picks up A's closure

    # The CI workflow's OLD, buggy shape: --base-ref <frozen pull_request.base.sha>.
    assert check(ledger, NOW, base_ref=fork_sha) == 1

    # The fix, and this test's default: --base-ref <a ref reflecting CURRENT main>.
    assert check(ledger, NOW) == 0


def test_innocence_a_pr_that_never_touches_the_ledger_is_skipped(tmp_path):
    """Main independently closing A after this branch diverged must not be
    read as THIS branch's loss — the branch never touched the file at all.
    """
    repo = _init_repo(tmp_path)
    ledger = _write_ledger(repo, [ENTRY_A, ENTRY_B])
    _commit(repo, "seed A+B")
    _mark_as_origin_main(repo)
    _git(["checkout", "-q", "-b", "feature"], repo)

    (repo / "unrelated.txt").write_text("hi\n", encoding="utf-8")
    _commit(repo, "feature: unrelated change")

    _git(["checkout", "-q", "main"], repo)
    _write_ledger(repo, [ENTRY_B])
    _commit(repo, "main: legitimately closes A")
    _mark_as_origin_main(repo)
    _git(["checkout", "-q", "feature"], repo)

    assert check(ledger, NOW) == 0
