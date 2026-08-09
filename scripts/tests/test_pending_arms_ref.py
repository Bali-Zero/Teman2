"""`--ref`: read the ledger from a git ref without mutating anything.

Why this exists (2026-08-08): the report's freshness line used to end in "pull
before trusting this report". On m5 the main checkout is deliberately behind
origin/main, and `worktree_isolation.py` refuses any mutating git there for an
agent session — so the only documented way to follow that advice was to disarm
the guard. A prescription whose only executor is a lane that does not exist
teaches its reader to ignore the probe.

The corpus is built around the one failure that would be worse than the disease:
asking for a ref, not getting it, and being handed the working tree anyway. A
caller in that position believes it is reading main and is reading its own stale
copy — so `--ref` is fatal on failure, and `test_unreadable_ref_never_falls_back`
is the load-bearing case here.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "pending_arms_report.py"

OLD_LINE = (
    "- opened 2026-01-01 | **only on the old commit** | missing arming step: none "
    "| owner: me (test) | proof-of-armed: none\n"
)
NEW_LINE = (
    "- opened 2026-01-02 | **only in the working tree** | missing arming step: none "
    "| owner: me (test) | proof-of-armed: none\n"
)


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=120
    )


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, timeout=60
    )


@pytest.fixture()
def repo_with_two_ledgers(tmp_path: Path) -> tuple[Path, Path]:
    """A throwaway repo whose committed ledger differs from its working tree.

    Committed on `oldref`: OLD_LINE. Working tree: NEW_LINE. Anything that
    confuses the two is visible as a wrong entry title, not as a subtle count.
    """
    repo = tmp_path / "repo"
    (repo / ".claude" / "skills" / "modus").mkdir(parents=True)
    ledger = repo / ".claude" / "skills" / "modus" / "PENDING-ARMS.md"
    _git(repo.parent, "init", "-q", str(repo))
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    ledger.write_text(OLD_LINE, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "old ledger")
    _git(repo, "branch", "-f", "oldref")
    ledger.write_text(NEW_LINE, encoding="utf-8")  # uncommitted: working tree only
    return repo, ledger


def test_guilt_ref_reads_the_committed_ledger_not_the_working_tree(repo_with_two_ledgers):
    """--ref must answer with the REF's content, or it is decoration."""
    _, ledger = repo_with_two_ledgers
    proc = _run("--ledger", str(ledger), "--ref", "oldref", "--now", "2026-02-01")
    assert proc.returncode == 0, proc.stderr
    assert "only on the old commit" in proc.stdout
    assert "only in the working tree" not in proc.stdout


def test_innocence_no_ref_still_reads_the_working_tree(repo_with_two_ledgers):
    """The default must not move.

    A session that has just written its own ledger line has to keep seeing it —
    switching the default to origin/main would make its own work vanish from the
    report, which is the twin bug of the one being fixed.
    """
    _, ledger = repo_with_two_ledgers
    proc = _run("--ledger", str(ledger), "--now", "2026-02-01")
    assert proc.returncode == 0, proc.stderr
    assert "only in the working tree" in proc.stdout
    assert "only on the old commit" not in proc.stdout


def test_unreadable_ref_never_falls_back(repo_with_two_ledgers):
    """The case that would be worse than the disease.

    Silently serving the working tree after being asked for a ref lets a caller
    conclude things about main from its own stale checkout. Must be fatal, must
    name the ref, and must not print a report.
    """
    _, ledger = repo_with_two_ledgers
    proc = _run("--ledger", str(ledger), "--ref", "no/such/ref", "--now", "2026-02-01")
    assert proc.returncode == 2, f"expected fatal, got {proc.returncode}: {proc.stdout}"
    assert "no/such/ref" in proc.stderr
    assert "only in the working tree" not in proc.stdout
    assert "only on the old commit" not in proc.stdout


def test_empty_ledger_at_ref_is_refused_not_reported_as_zero_entries(tmp_path: Path):
    """Zero entries is a claim; an empty read is not evidence for it."""
    repo = tmp_path / "repo"
    (repo / ".claude" / "skills" / "modus").mkdir(parents=True)
    ledger = repo / ".claude" / "skills" / "modus" / "PENDING-ARMS.md"
    _git(repo.parent, "init", "-q", str(repo))
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    ledger.write_text("", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "empty ledger")
    _git(repo, "branch", "-f", "emptyref")
    ledger.write_text(NEW_LINE, encoding="utf-8")

    proc = _run("--ledger", str(ledger), "--ref", "emptyref", "--now", "2026-02-01")
    assert proc.returncode == 2, proc.stdout
    assert "empty" in proc.stderr.lower()


def test_ref_run_writes_nothing(repo_with_two_ledgers):
    """`git show` reads; it must not touch the tree, the index, or the branch.

    Asserted on observable state rather than trusted from the docstring: the
    working-tree bytes, `git status --porcelain` and HEAD are all unchanged.
    """
    repo, ledger = repo_with_two_ledgers
    before_bytes = ledger.read_bytes()
    before_status = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True
    ).stdout
    before_head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout

    assert _run("--ledger", str(ledger), "--ref", "oldref", "--now", "2026-02-01").returncode == 0

    assert ledger.read_bytes() == before_bytes
    after_status = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True
    ).stdout
    after_head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout
    assert after_status == before_status
    assert after_head == before_head


def test_stale_advice_no_longer_prescribes_a_pull():
    """The prescription itself is the finding — assert on the shipped string.

    Read from the module rather than from a run, because reproducing a stale
    checkout in a fixture would test the fixture. What must never come back is
    advice a session is forbidden to follow.
    """
    src = SCRIPT.read_text(encoding="utf-8")
    start = src.index('"state": "stale"')
    detail = src[start : start + 1200]
    assert "pull before trusting" not in detail
    assert "--ref origin/main" in detail


def test_report_names_its_source_when_a_ref_is_used(repo_with_two_ledgers):
    """A reader must never have to guess which ledger produced the rows."""
    _, ledger = repo_with_two_ledgers
    proc = _run("--ledger", str(ledger), "--ref", "oldref", "--now", "2026-02-01")
    assert "@ `oldref`" in proc.stdout
    assert "read at `oldref`" in proc.stdout
