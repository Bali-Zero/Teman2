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


# ---------------------------------------------------------------------------
# The earned-flip exemption (2026-07-29).
#
# Rows here carry the REAL column layout of docs/DOCS_INVENTORY.md, because the
# exemption is positional:
#   File | Status | last_touched_date | orphan_eligible_on | orphan_flipped_on |
#   refs_in | broken | drift | cluster | action
# ---------------------------------------------------------------------------

_LIVE = "LIVE | 2026-04-29 | 2026-07-28 | — | 0 | 0 | no | — | —"
_ARCHIVED = (
    "ARCHIVED | 2026-04-29 | 2026-07-28 | 2026-07-29 | 0 | 0 | no | — | "
    "archive: orphan, last_touched=2026-04-29, refs=0"
)


def _full_table(rows: dict[str, str]) -> str:
    body = "\n".join(f"| {p} | {cells} |" for p, cells in rows.items())
    return (
        "# Documentation Inventory\n\n"
        "| Status   | Count | % |\n"
        "| -------- | ----: | -: |\n"
        "| LIVE     |   620 | 66% |\n\n"
        "| File | Status | last_touched_date | orphan_eligible_on | "
        "orphan_flipped_on | refs_in | broken | drift | cluster | action |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        + body
        + "\n"
    )


def test_innocence_an_earned_orphan_flip_is_not_drift() -> None:
    """The exact shape of PR #3463, which this exemption exists for.

    The organ regenerates with `--organ` (advances flips); the gate regenerates
    gate-consistent (never invents one). Comparing whole rows charged the organ
    for the one decision P3-prime deliberately moved into it — measured across
    all six refresh PRs: the two that merged carried zero flips, every one that
    carried a flip died.
    """
    committed = _full_table({"docs/audits/x.md": _ARCHIVED})
    generated = _full_table({"docs/audits/x.md": _LIVE})
    assert blame.drifting_keys(committed, generated) == set()


def test_guilt_a_flip_dated_before_its_eligibility_is_still_drift() -> None:
    """The exemption is earned by the row's own facts, not by its shape.

    A flip stamped EARLIER than `orphan_eligible_on` is the organ (or a PR)
    archiving a doc before it was eligible — the deterministic fact says no.
    """
    early = _ARCHIVED.replace("2026-07-29", "2026-07-01", 1)
    committed = _full_table({"docs/audits/x.md": early})
    generated = _full_table({"docs/audits/x.md": _LIVE})
    assert blame.drifting_keys(committed, generated) == {"docs/audits/x.md"}


def test_guilt_a_backwards_flip_is_still_drift() -> None:
    """ARCHIVED -> LIVE is not a flip this organ advances; it is a regression."""
    committed = _full_table({"docs/audits/x.md": _LIVE})
    generated = _full_table({"docs/audits/x.md": _ARCHIVED})
    assert blame.drifting_keys(committed, generated) == {"docs/audits/x.md"}


def test_guilt_a_flip_that_also_edits_another_cell_is_still_drift() -> None:
    """Only Status, orphan_flipped_on and action are exempt.

    This is what makes the justification unforgeable: a PR that back-dates
    `orphan_eligible_on` to license its own flip changes a cell outside the
    exempt three, so the row is charged in full rather than waved through.
    """
    forged = _ARCHIVED.replace("| 2026-07-28 |", "| 2026-01-01 |", 1)
    committed = _full_table({"docs/audits/x.md": forged})
    generated = _full_table({"docs/audits/x.md": _LIVE})
    assert blame.drifting_keys(committed, generated) == {"docs/audits/x.md"}


def test_guilt_a_docs_edit_without_a_regen_is_untouched_by_the_exemption() -> None:
    """The gate's whole reason to exist must survive the new exemption.

    A row whose ref count moved (a PR added a link and did not regenerate) has
    nothing to do with flips and must stay charged.
    """
    stale = _LIVE.replace("| 0 | 0 | no |", "| 4 | 0 | no |", 1)
    committed = _full_table({"docs/audits/x.md": stale})
    generated = _full_table({"docs/audits/x.md": _LIVE})
    assert blame.drifting_keys(committed, generated) == {"docs/audits/x.md"}


def test_a_malformed_or_short_row_is_never_waved_through() -> None:
    """Fail closed: a row this parser cannot read is drift, not an exemption."""
    committed = _full_table({"docs/audits/x.md": "ARCHIVED | 2026-04-29"})
    generated = _full_table({"docs/audits/x.md": _LIVE})
    assert blame.drifting_keys(committed, generated) == {"docs/audits/x.md"}


def test_scar_pin_the_eight_rows_of_pr_3463() -> None:
    """The measured incident, kept as data.

    These are the eight documents `inventory-check` charged to #3463 on
    2026-07-29 — the run said "inventory rows this PR makes STALE: 8" and named
    them. With the exemption they are not drift; without it they all are.
    """
    paths = [
        "docs/audits/2026-04-29-zero-crash-audit/11_brainstorms/00_INDEX.md",
        "docs/audits/2026-04-29-zero-crash-audit/_codex_iteration_1_section.md",
        "docs/audits/2026-04-29-zero-crash-audit/_codex_iteration_2.md",
        "docs/audits/2026-04-29-zero-crash-audit/_codex_iteration_3_final.md",
        "docs/audits/2026-04-29-zero-crash-audit/prompts/wave1/kakuro-S4-final.md",
        "docs/innervation-2026-04-29/99c_w0a_bis_kickoff.md",
        "docs/ops/2026-04-30-followup-cell-cron-sensor.md",
        "docs/ops/2026-04-30-followup-heartbeat-telegram-html.md",
    ]
    committed = _full_table({p: _ARCHIVED for p in paths})
    generated = _full_table({p: _LIVE for p in paths})
    assert len(blame.row_map(committed)) == 8, "the fixture itself stopped parsing"
    assert blame.drifting_keys(committed, generated) == set()
