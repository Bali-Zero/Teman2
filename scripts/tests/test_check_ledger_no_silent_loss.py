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
