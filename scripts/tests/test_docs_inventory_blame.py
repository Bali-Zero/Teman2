"""Tests for scripts/docs_inventory_blame.py — the blame-scoping half of the
docs inventory gate.

Both guilt cases are taken from real 2026-07-26 incidents rather than invented:

  * #3106 changed docs without regenerating, so the NEXT docs PR (#3149)
    inherited a red it did not earn. A PR in #3106's position must still FAIL.
  * The refresh organ's PR #3203 failed on a single counter line
    (`**Orphans:** 65` vs `64`) because main moved between its regeneration and
    the check. A PR in #3203's position must PASS.

The two must hold at once — which is the whole point: the old rule could not
tell them apart, because it compared the absolute state instead of the delta.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "docs_inventory_blame.py"

sys.path.insert(0, str(SCRIPT.parent))
import docs_inventory_blame as blame  # noqa: E402


def _table(rows: dict[str, str], *, orphans: int = 10) -> str:
    """Build an inventory-shaped table: summary block + one row per doc."""
    body = "\n".join(f"| {p} | {cells} |" for p, cells in rows.items())
    return (
        "# Docs Inventory\n\n"
        "| Status   | Count | % |\n"
        "| -------- | ----: | -: |\n"
        f"| LIVE     |   {len(rows)} | 67% |\n"
        "| STALE    |     6 | 1% |\n"
        "| ARCHIVED |   307 | 33% |\n\n"
        f"**Drift:** 0 · **Broken links:** 2 · **Orphans:** {orphans}\n\n"
        "| Doc | Status |\n| --- | --- |\n" + body + "\n"
    )


BASE_ROWS = {
    "docs/A.md": "LIVE | 3 | 2026-07-01",
    "docs/B.md": "LIVE | 9 | 2026-07-02",
    "docs/C.md": "ARCHIVED | 99 | 2026-01-05",
}


def _run(tmp_path: Path, cb: str, gb: str, ch: str, gh: str) -> subprocess.CompletedProcess:
    paths = {}
    for name, content in (
        ("committed_base", cb),
        ("generated_base", gb),
        ("committed_head", ch),
        ("generated_head", gh),
    ):
        p = tmp_path / f"{name}.md"
        p.write_text(content, encoding="utf-8")
        paths[name] = str(p)
    return subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--committed-base", paths["committed_base"],
            "--generated-base", paths["generated_base"],
            "--committed-head", paths["committed_head"],
            "--generated-head", paths["generated_head"],
        ],
        capture_output=True, text=True,
    )


# --------------------------------------------------------------------------
# GUILT — the PR really did make the inventory worse
# --------------------------------------------------------------------------


def test_guilt_pr_changes_a_doc_without_regenerating(tmp_path):
    """#3106's shape: docs edited, table left untouched. Must FAIL.

    Base is fully consistent, so every drifting row at head is this PR's doing.
    """
    clean = _table(BASE_ROWS)
    head_generated = _table({**BASE_ROWS, "docs/B.md": "STALE | 40 | 2026-07-02"})
    r = _run(tmp_path, clean, clean, clean, head_generated)
    assert r.returncode == 1, r.stdout
    assert "docs/B.md" in r.stdout
    assert "makes STALE" in r.stdout


def test_guilt_pr_adds_a_doc_without_adding_its_row(tmp_path):
    """A brand-new doc missing from the table is drift of the loudest kind."""
    clean = _table(BASE_ROWS)
    head_generated = _table({**BASE_ROWS, "docs/NEW.md": "LIVE | 0 | 2026-07-26"})
    r = _run(tmp_path, clean, clean, clean, head_generated)
    assert r.returncode == 1
    assert "docs/NEW.md" in r.stdout


def test_guilt_new_drift_is_charged_even_when_the_base_already_drifts(tmp_path):
    """Inheriting drift must not become a licence to add more.

    Base already drifts on A; the PR additionally breaks B. A is reported as
    inherited, B is charged, and the run fails.
    """
    committed_base = _table(BASE_ROWS)
    generated_base = _table({**BASE_ROWS, "docs/A.md": "STALE | 91 | 2026-07-01"})
    generated_head = _table(
        {**BASE_ROWS, "docs/A.md": "STALE | 91 | 2026-07-01",
         "docs/B.md": "ARCHIVED | 91 | 2026-07-02"}
    )
    r = _run(tmp_path, committed_base, generated_base, committed_base, generated_head)
    assert r.returncode == 1
    assert "docs/B.md" in r.stdout
    assert "NOT charged to this PR" in r.stdout and "docs/A.md" in r.stdout


# --------------------------------------------------------------------------
# INNOCENCE — the drift is real but not this PR's fault
# --------------------------------------------------------------------------


def test_innocence_pr_inherits_the_bases_drift_unchanged(tmp_path):
    """#3149's shape: someone else left main dirty; this PR touched docs for
    unrelated reasons. Identical drift at base and head ⇒ PASS."""
    committed = _table(BASE_ROWS)
    generated = _table({**BASE_ROWS, "docs/A.md": "STALE | 91 | 2026-07-01"})
    r = _run(tmp_path, committed, generated, committed, generated)
    assert r.returncode == 0, r.stdout
    assert "PASS" in r.stdout


def test_innocence_counter_only_difference_does_not_fail(tmp_path):
    """#3203's shape, and the exact line it died on: `**Orphans:** 65` vs `64`.

    Aggregate counters are consequences of the rows. A counter that moves
    because some OTHER PR archived a doc can never be this PR's fault, so a
    difference confined to the summary block must not fail anyone.
    """
    committed = _table(BASE_ROWS, orphans=65)
    generated = _table(BASE_ROWS, orphans=64)
    r = _run(tmp_path, committed, committed, committed, generated)
    assert r.returncode == 0, r.stdout + r.stderr


def test_innocence_the_refresh_organ_repairing_drift_passes(tmp_path):
    """The organ's whole job is to REMOVE drift. Fewer drifting rows at head
    than at base must pass — punishing the repair is how the organ starved."""
    stale_committed = _table(BASE_ROWS)
    fresh = _table({**BASE_ROWS, "docs/A.md": "STALE | 91 | 2026-07-01"})
    # base drifts on A; the organ commits the regenerated table, so head is clean
    r = _run(tmp_path, stale_committed, fresh, fresh, fresh)
    assert r.returncode == 0, r.stdout
    assert "REPAIRS" in r.stdout and "docs/A.md" in r.stdout


# --------------------------------------------------------------------------
# Shape pins
# --------------------------------------------------------------------------


def test_summary_block_rows_are_never_treated_as_documents(tmp_path):
    """`| LIVE | 625 | 67% |` is a summary line, not a doc named "LIVE"."""
    m = blame.row_map(_table(BASE_ROWS))
    assert set(m) == set(BASE_ROWS)
    assert not any(k in m for k in ("LIVE", "STALE", "ARCHIVED", "Status", "Doc"))


def test_parser_reads_every_row_of_the_real_inventory(tmp_path):
    """Anchor to the real artifact: the row count must equal the summary block's
    own LIVE+STALE+ARCHIVED total. A parser that silently reads half the table
    would make the subset test pass by seeing no drift at all."""
    import re

    content = (REPO_ROOT / "docs" / "DOCS_INVENTORY.md").read_text(encoding="utf-8")
    counts = {
        s: int(n)
        for s, n in re.findall(r"^\|\s*(LIVE|STALE|ARCHIVED)\s*\|\s*(\d+)", content, re.M)
    }
    assert counts, "could not read the summary block — has the table shape changed?"
    assert len(blame.row_map(content)) == sum(counts.values())


def test_added_and_removed_rows_both_count_as_drift(tmp_path):
    """Symmetry: a row only in `generated` and a row only in `committed` are
    both drift. Testing one direction would leave deletions invisible."""
    a = _table(BASE_ROWS)
    b = _table({k: v for k, v in BASE_ROWS.items() if k != "docs/C.md"})
    assert blame.drifting_keys(a, b) == {"docs/C.md"}
    assert blame.drifting_keys(b, a) == {"docs/C.md"}
