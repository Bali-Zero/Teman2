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
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "docs_inventory_blame.py"

sys.path.insert(0, str(SCRIPT.parent))
import docs_inventory_blame as blame  # noqa: E402
from docs_audit import _parse_inventory_table as _parse_table  # noqa: E402


def _table(rows: dict[str, str], *, orphans: int = 10) -> str:
    """Build an inventory-shaped table: summary block + one row per doc.

    The header must have as many columns as the rows do. Its first build
    declared two (`| Doc | Status |`) while every row carried four, so
    `_parse_inventory_table` — which matches by header and drops any row whose
    cell count disagrees — silently returned NOTHING for these fixtures. That is
    a table no generator can emit, and it made five tests measure a parser
    failure instead of the drift they were written for.
    """
    body = "\n".join(f"| {p} | {cells} |" for p, cells in rows.items())
    return (
        "# Docs Inventory\n\n"
        "| Status   | Count | % |\n"
        "| -------- | ----: | -: |\n"
        f"| LIVE     |   {len(rows)} | 67% |\n"
        "| STALE    |     6 | 1% |\n"
        "| ARCHIVED |   307 | 33% |\n\n"
        f"**Drift:** 0 · **Broken links:** 2 · **Orphans:** {orphans}\n\n"
        "| File | Status | refs_in | last_touched_date |\n"
        "| --- | --- | --- | --- |\n" + body + "\n"
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


def test_tracked_inventory_pointer_is_not_parsed_as_derived_rows():
    """The retired blame judge must not mistake pointer prose for table state."""
    content = (REPO_ROOT / "docs" / "DOCS_INVENTORY.md").read_text(encoding="utf-8")
    assert "docs-derived-state CI artifact" in content
    assert blame.row_map(content) == {}


def test_added_and_removed_rows_both_count_as_drift(tmp_path):
    """Symmetry: a row only in `generated` and a row only in `committed` are
    both drift. Testing one direction would leave deletions invisible."""
    a = _table(BASE_ROWS)
    b = _table({k: v for k, v in BASE_ROWS.items() if k != "docs/C.md"})
    assert set(blame.drifting_keys(a, b)) == {"docs/C.md"}
    assert set(blame.drifting_keys(b, a)) == {"docs/C.md"}


# ---------------------------------------------------------------------------
# The earned-flip exemption (2026-07-29, rebuilt after a cross-family red-team).
#
# Rows carry the REAL column layout and header row of docs/DOCS_INVENTORY.md,
# because the exemption reads its cells BY HEADER NAME via
# docs_audit._parse_inventory_table — a fixture with a different header row is
# not merely unrealistic here, it parses to nothing and would make every
# assertion below vacuously true.
#
# CEILING is fixed rather than "today": the upper bound on a claimed flip date
# is an input to the rule, so the corpus must be able to assert BOTH sides of
# it (a claim inside it, a claim beyond it) without waiting for the calendar.
# ---------------------------------------------------------------------------

CEILING = date(2026, 7, 29)

_LIVE = "LIVE | 2026-04-29 | 2026-07-28 | — | 0 | 0 | no | — | —"
_ARCHIVED = (
    "ARCHIVED | 2026-04-29 | 2026-07-28 | 2026-07-29 | 0 | 0 | no | — | "
    "archive: orphan, last_touched=2026-04-29, refs=0"
)


def _full_table(rows: dict[str, str]) -> str:
    """An inventory-shaped table whose counters are DERIVED from its rows.

    `render_inventory` computes every aggregate from the rows it renders, so a
    fixture that hardcodes a count is a table the generator could never emit —
    and a corpus built on impossible inputs proves nothing about the real one.
    """
    live = sum(1 for c in rows.values() if c.startswith("LIVE"))
    archived = sum(1 for c in rows.values() if c.startswith("ARCHIVED"))
    total = max(len(rows), 1)
    body = "\n".join(f"| {p} | {cells} |" for p, cells in rows.items())
    return (
        "# Documentation Inventory\n\n"
        "| Status   | Count | % |\n"
        "| -------- | ----: | -: |\n"
        f"| LIVE     |   {live} | {round(100 * live / total)}% |\n"
        f"| ARCHIVED |   {archived} | {round(100 * archived / total)}% |\n\n"
        "| File | Status | last_touched_date | orphan_eligible_on | "
        "orphan_flipped_on | refs_in | broken | drift | cluster | action |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        + body
        + "\n"
    )


def _drift(committed: str, generated: str, **kw) -> set[str]:
    kw.setdefault("ceiling", CEILING)
    return set(blame.drifting_keys(committed, generated, **kw))


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
    assert _drift(committed, generated) == set()


def test_guilt_a_flip_dated_before_its_eligibility_is_still_drift() -> None:
    """The exemption is earned by the row's own facts, not by its shape.

    A flip stamped EARLIER than `orphan_eligible_on` is the organ (or a PR)
    archiving a doc before it was eligible — the deterministic fact says no.
    """
    early = _ARCHIVED.replace("2026-07-29", "2026-07-01", 1)
    committed = _full_table({"docs/audits/x.md": early})
    generated = _full_table({"docs/audits/x.md": _LIVE})
    assert _drift(committed, generated) == {"docs/audits/x.md"}


def test_guilt_a_backwards_flip_is_still_drift() -> None:
    """ARCHIVED -> LIVE is not a flip this organ advances; it is a regression."""
    committed = _full_table({"docs/audits/x.md": _LIVE})
    generated = _full_table({"docs/audits/x.md": _ARCHIVED})
    assert _drift(committed, generated) == {"docs/audits/x.md"}


def test_guilt_a_flip_that_also_edits_another_cell_is_still_drift() -> None:
    """Only Status, orphan_flipped_on and action are exempt.

    This is what makes the justification unforgeable: a PR that back-dates
    `orphan_eligible_on` to license its own flip changes a cell outside the
    exempt three, so the row is charged in full rather than waved through.
    """
    forged = _ARCHIVED.replace("| 2026-07-28 |", "| 2026-01-01 |", 1)
    committed = _full_table({"docs/audits/x.md": forged})
    generated = _full_table({"docs/audits/x.md": _LIVE})
    assert _drift(committed, generated) == {"docs/audits/x.md"}


def test_guilt_a_docs_edit_without_a_regen_is_untouched_by_the_exemption() -> None:
    """The gate's whole reason to exist must survive the new exemption.

    A row whose ref count moved (a PR added a link and did not regenerate) has
    nothing to do with flips and must stay charged.
    """
    stale = _LIVE.replace("| 0 | 0 | no |", "| 4 | 0 | no |", 1)
    committed = _full_table({"docs/audits/x.md": stale})
    generated = _full_table({"docs/audits/x.md": _LIVE})
    assert _drift(committed, generated) == {"docs/audits/x.md"}


def test_a_malformed_or_short_row_is_never_waved_through() -> None:
    """Fail closed: a row this parser cannot read is drift, not an exemption."""
    committed = _full_table({"docs/audits/x.md": "ARCHIVED | 2026-04-29"})
    generated = _full_table({"docs/audits/x.md": _LIVE})
    assert _drift(committed, generated) == {"docs/audits/x.md"}


# --- what the first version of the exemption let through -------------------
# Every case below was found by a cross-family refuter (Codex GPT-5.6, 2026-07-29)
# against the first build, which decided legitimacy on its own instead of asking
# docs_audit. Each one PASSED that version.


def test_guilt_a_live_doc_with_inbound_refs_cannot_be_hand_archived() -> None:
    """BLOCKER-1 as reported: the exemption ignored `refs_in` entirely.

    `classify()` only ever archives a doc that is structurally orphan-eligible —
    `refs_in == 0`. The first version checked neither side's ref count, so a
    real, referenced, whitelisted document (the refuter used docs/API_REFERENCE.md,
    four inbound refs) could be hand-marked ARCHIVED in the committed table and
    the gate would wave it through.
    """
    live4 = "LIVE | 2026-04-29 | 2026-07-28 | — | 4 | 0 | no | — | —"
    arch4 = (
        "ARCHIVED | 2026-04-29 | 2026-07-28 | 2026-07-29 | 4 | 0 | no | — | "
        "archive: orphan, last_touched=2026-04-29, refs=0"
    )
    committed = _full_table({"docs/API_REFERENCE.md": arch4})
    generated = _full_table({"docs/API_REFERENCE.md": live4})
    assert _drift(committed, generated) == {"docs/API_REFERENCE.md"}


def test_guilt_a_whitelisted_doc_is_never_an_earned_flip() -> None:
    """Structural eligibility is `refs_in == 0` AND not whitelisted.

    The shared predicate cannot see the whitelist — it has no repo access. A
    RENDERED row can: `classify()` writes `action = "whitelist"` for a
    whitelisted doc, never the em-dash. So the generated side's action carries
    the fact, and pinning it closes the half the predicate must leave open.

    FIXTURE NOTE (2026-08-07, re-derived): this used `docs/README.md`, which
    is now ALSO refused as a directory index. The assertion would have stayed
    green with the whitelist half of the rule deleted — a test that passes for
    two reasons discriminates on neither. The path is now a doc that is
    whitelisted and nothing else, so the assertion still names one mechanism.
    """
    wl = "LIVE | 2026-04-29 | 2026-07-28 | — | 0 | 0 | no | — | whitelist"
    committed = _full_table({"docs/GUIDE.md": _ARCHIVED})
    generated = _full_table({"docs/GUIDE.md": wl})
    assert _drift(committed, generated) == {"docs/GUIDE.md"}


def test_guilt_a_future_dated_flip_is_drift() -> None:
    """BLOCKER-2 as reported: the first version bounded the date only BELOW.

    `2099-12-31 >= eligible` was true, so it passed — the same forgery the
    --check path had already been hardened against on 2026-07-25, where a
    claim of 2099 kept a live doc pinned ARCHIVED for 73 years and would have
    had the organ physically `git mv` it into docs/archive/.
    """
    future = _ARCHIVED.replace("2026-07-29", "2099-12-31", 1)
    committed = _full_table({"docs/audits/x.md": future})
    generated = _full_table({"docs/audits/x.md": _LIVE})
    assert _drift(committed, generated) == {"docs/audits/x.md"}


def test_guilt_a_date_shaped_string_that_is_not_a_date_is_drift() -> None:
    """`\\d{4}-\\d{2}-\\d{2}` accepts 2099-99-99; `date.fromisoformat` does not.

    The first version validated the SHAPE of the two dates with a regex and then
    compared them as strings — so a non-date that looks like one sorted its way
    past the lower bound. The rule now parses.
    """
    bogus = _ARCHIVED.replace("2026-07-29", "2099-99-99", 1)
    committed = _full_table({"docs/audits/x.md": bogus})
    generated = _full_table({"docs/audits/x.md": _LIVE})
    assert _drift(committed, generated) == {"docs/audits/x.md"}


def test_guilt_the_action_cell_is_not_free_text() -> None:
    """`action` is exempt from the identity check, so it must be pinned instead.

    An archived orphan's action is a pure function of its own `last_touched_date`
    (`docs_audit.archive_orphan_action`) — a cell that IS compared verbatim. So
    the exemption cannot be used as a hole to write arbitrary text into a row.
    """
    lying = _ARCHIVED.replace(
        "archive: orphan, last_touched=2026-04-29, refs=0", "anything at all", 1
    )
    committed = _full_table({"docs/audits/x.md": lying})
    generated = _full_table({"docs/audits/x.md": _LIVE})
    assert _drift(committed, generated) == {"docs/audits/x.md"}


def test_guilt_a_path_already_flipped_on_the_base_is_never_re_exempted() -> None:
    """Anti-resurrection: the tolerance is only for a flip not yet on the base.

    If the base's committed table already records a flip for this path, any
    mismatch is a potential resurrection/hiding attempt and is never tolerated —
    condition 1 of the 2026-07-18 round, inherited here through the same
    predicate.
    """
    committed = _full_table({"docs/audits/x.md": _ARCHIVED})
    generated = _full_table({"docs/audits/x.md": _LIVE})
    prior = {"docs/audits/x.md": "2026-07-20"}
    assert _drift(committed, generated, prior_flips=prior) == {"docs/audits/x.md"}


def test_guilt_a_duplicated_path_is_drift_not_a_silent_last_wins() -> None:
    """A dict keeps the LAST row, so a corrupt row can hide BEHIND a clean one.

    Order is the whole point of this case, and getting it wrong is how the
    first version of the test proved nothing: with the corrupt row LAST it is
    the corrupt row that survives the dict, the comparison sees it, and the row
    is charged for ordinary reasons — the duplicate logic is never consulted.
    The attack is the other way round. The corrupt row goes FIRST and the
    exemptable row LAST, so `row_map` keeps the clean one, the exemption fires,
    and a row asserting nine broken links vanishes from the gate's view
    entirely. Mutation-checked: with `_duplicate_keys` disabled this assertion
    fails, and with the two rows swapped it does not.
    """
    header, _, rows = _full_table({"docs/audits/x.md": _ARCHIVED}).rpartition("| --- |\n")
    corrupt = "| docs/audits/x.md | ARCHIVED | 1999-01-01 | — | — | 9 | 9 | yes | — | ? |\n"
    committed = header + "| --- |\n" + corrupt + rows
    generated = _full_table({"docs/audits/x.md": _LIVE})
    assert _drift(committed, generated) == {"docs/audits/x.md"}


def test_guilt_a_generated_row_that_is_live_yet_already_flipped_is_impossible() -> None:
    """A defence against a state the generator cannot produce — asserted anyway.

    `classify()` sets `status = "ARCHIVED"` the moment `orphan_flipped_on` is
    non-empty, so a LIVE row carrying a flip date cannot come out of a real
    regeneration. The exemption checks for it regardless, because "the generator
    would never" is an argument about today's generator, and this table is also
    read from files a human can edit.

    Without this case the check is unpinned: the mutation sweep found it GREEN
    when disabled, precisely because every other test feeds it states the
    generator really does produce.
    """
    impossible = _LIVE.replace("| — | 0 | 0 |", "| 2026-07-20 | 0 | 0 |", 1)
    assert impossible != _LIVE, "the fixture edit did not apply"
    committed = _full_table({"docs/audits/x.md": _ARCHIVED})
    generated = _full_table({"docs/audits/x.md": impossible})
    assert _drift(committed, generated) == {"docs/audits/x.md"}


def test_without_a_trustworthy_ceiling_nothing_is_ever_exempt() -> None:
    """Fail closed. A caller that has established no upper bound gets no tolerance.

    This is the same `if trusted_ref_ceiling_date is None: return` the --check
    path has, and it is why the exemption cannot be activated by simply calling
    the function without arguments.
    """
    committed = _full_table({"docs/audits/x.md": _ARCHIVED})
    generated = _full_table({"docs/audits/x.md": _LIVE})
    assert set(blame.drifting_keys(committed, generated)) == {"docs/audits/x.md"}


# --- round 2: what the FIRST cure still let through -------------------------


def test_guilt_renaming_the_table_header_is_drift() -> None:
    """Every other check in this file reads ROWS, so a broken schema was free.

    `| File |` -> `| Files |` leaves every document row byte-identical.
    `_parse_inventory_table` then returns {} — it matches on the header — while
    `row_map` still finds all the rows, so nothing differed and the gate passed
    on a table whose schema had been broken. Measured: the probe returned
    `set()`.
    """
    good = _full_table({"docs/a.md": _LIVE})
    bad = good.replace("| File |", "| Files |", 1)
    assert bad != good, "the fixture edit did not apply"
    assert blame.TABLE_KEY in _drift(bad, good)


def test_guilt_a_markdown_linked_row_cannot_hide_a_duplicate() -> None:
    """The link normalisation this file advertised had never once fired.

    `.strip("`[]")` ran BEFORE the link regex, eating the leading `[`, so
    `[docs/x.md](docs/x.md)` became `docs/x.md](docs/x.md)` — rejected for not
    ending in `.md`, and therefore INVISIBLE to both `row_map` and
    `_duplicate_keys` while `_parse_inventory_table` still saw it. A corrupt row
    wearing link syntax could sit beside a clean exemptable one and neither
    scanner would count a duplicate.
    """
    assert blame._row_key("[docs/x.md](docs/x.md)") == "docs/x.md"
    header, _, rows = _full_table({"docs/x.md": _ARCHIVED}).rpartition("| --- |\n")
    linked = "| [docs/x.md](docs/x.md) | ARCHIVED | 1999-01-01 | — | — | 9 | 9 | yes | — | ? |\n"
    committed = header + "| --- |\n" + linked + rows
    generated = _full_table({"docs/x.md": _LIVE})
    assert _drift(committed, generated) == {"docs/x.md"}


def test_guilt_a_row_only_one_parser_can_read_is_drift_even_when_identical() -> None:
    """The two parsers in this file must agree about which rows exist.

    `row_map` scans raw lines; `_parse_inventory_table` matches the header and
    DROPS any row whose cell count disagrees with it. A row only one of them
    sees is a row the exemption cannot be trusted about — and if it is identical
    on both sides, the ordinary difference test says nothing at all, so without
    the reconciliation check it passes in silence.
    """
    short = "| docs/broken.md | LIVE | 2026-04-29 |"
    header, _, rows = _full_table({"docs/a.md": _LIVE}).rpartition("| --- |\n")
    both = header + "| --- |\n" + short + "\n" + rows
    assert blame.row_map(both).keys() == {"docs/broken.md", "docs/a.md"}
    assert "docs/broken.md" not in _parse_table(both), "fixture no longer malformed"
    assert _drift(both, both) == {"docs/broken.md"}


def test_an_unreadable_row_reports_its_difference_not_just_its_unreadability() -> None:
    """A marker must never REPLACE a real difference — order of the checks.

    The first build tested "only one parser can read this" FIRST, so an
    unparseable row got a CONSTANT signature. Identical at base and at head, it
    made a genuine row difference underneath read as inherited drift, and the
    gate passed on it. The signature must carry the rows themselves.
    """
    header, _, rows = _full_table({"docs/a.md": _LIVE}).rpartition("| --- |\n")
    a = header + "| --- |\n" + "| docs/broken.md | LIVE | 2026-04-29 |\n" + rows
    b = header + "| --- |\n" + "| docs/broken.md | STALE | 1999-01-01 |\n" + rows
    sig = blame.drifting_keys(a, b, ceiling=CEILING)["docs/broken.md"]
    assert "only one parser" not in sig, f"the marker masked the difference: {sig!r}"
    assert "LIVE" in sig and "STALE" in sig


def test_guilt_worsening_an_already_drifting_row_is_not_inherited(tmp_path) -> None:
    """"Already drifting" was a licence, because only KEYS were compared.

    `introduced = head - base` over sets of paths: a row drifting on the base
    could be worsened at head — different status, corrupted cells, anything —
    and the key stayed in both sets, so the difference vanished and the PR
    passed. Drift is now compared by SIGNATURE, so the same key drifting a
    DIFFERENT way is drift this PR introduced.
    """
    committed = _table(BASE_ROWS)
    generated_base = _table({**BASE_ROWS, "docs/A.md": "STALE | 91 | 2026-07-01"})
    # same key, worse drift: STALE -> ARCHIVED with a different date
    generated_head = _table({**BASE_ROWS, "docs/A.md": "ARCHIVED | 91 | 1999-01-01"})
    r = _run(tmp_path, committed, generated_base, committed, generated_head)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "docs/A.md" in r.stdout
    assert "makes STALE" in r.stdout


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
    assert _drift(committed, generated) == set()


# ---------------------------------------------------------------------------
# Round 3 (cross-family refuter, 2026-07-30). Three ways a REAL change could
# leave the signature it is compared by unmoved — and one of them is this PR's
# own lesson (one identity, two spellings) arriving a level down.
# ---------------------------------------------------------------------------


def test_guilt_rewriting_the_alignment_row_is_drift() -> None:
    """Nothing else in this module looks at the Markdown alignment row.

    `_parse_inventory_table` skips it by index and `_scan_rows` drops it (its
    first cell is not a `.md` path), so a PR could replace it with anything,
    break the table's rendering, and every parser here would report an
    identical inventory: `--check` red, blame "no key drifted", PR exonerated.
    """
    good = _full_table({"docs/audits/x.md": _LIVE})
    bad = good.replace(
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        "| whatever goes here | x | x | x | x | x | x | x | x | x |",
        1,
    )
    assert bad != good, "the fixture no longer contains the alignment row"
    assert blame.ALIGN_KEY in _drift(bad, good)
    assert blame.ALIGN_KEY in _drift(good, bad)


def test_innocence_an_intact_alignment_row_is_not_drift() -> None:
    """The new key must fire on a rewrite, never on a table that is fine."""
    t = _full_table({"docs/audits/x.md": _LIVE})
    assert blame.ALIGN_KEY not in _drift(t, t)
    assert blame.ALIGN_KEY not in _drift(_table(BASE_ROWS), _table(BASE_ROWS))


def test_guilt_a_duplicate_row_signature_moves_when_the_duplicate_changes() -> None:
    """A category label is not a signature.

    `"duplicated row"` was a CONSTANT: a base that already carried a duplicate
    could have one of its two rows rewritten at head and `main()` — which calls
    a key inherited when `base[k] == head[k]` — read the rewrite as
    pre-existing. The signature now carries the rows it signs.
    """
    dup = "# Docs Inventory\n\n"
    header = (
        "| File | Status | refs_in | last_touched_date |\n| --- | --- | --- | --- |\n"
    )
    before = dup + header + "| docs/A.md | LIVE | 3 | 2026-07-01 |\n| docs/A.md | LIVE | 3 | 2026-07-02 |\n"
    after = dup + header + "| docs/A.md | LIVE | 3 | 2026-07-01 |\n| docs/A.md | ARCHIVED | 0 | 2026-07-02 |\n"
    clean = _table({"docs/A.md": "LIVE | 3 | 2026-07-01"})
    sig_before = blame.drifting_keys(before, clean, ceiling=CEILING)["docs/A.md"]
    sig_after = blame.drifting_keys(after, clean, ceiling=CEILING)["docs/A.md"]
    assert sig_before != sig_after, "the duplicate changed and its signature did not"


def test_guilt_a_one_sided_row_signature_moves_when_that_row_changes() -> None:
    """Same defect, other arm: `"present only in generated"` was constant too."""
    committed = _table({"docs/A.md": "LIVE | 3 | 2026-07-01"})
    gen_v1 = _table(
        {"docs/A.md": "LIVE | 3 | 2026-07-01", "docs/B.md": "LIVE | 9 | 2026-07-02"}
    )
    gen_v2 = _table(
        {"docs/A.md": "LIVE | 3 | 2026-07-01", "docs/B.md": "STALE | 0 | 2026-01-01"}
    )
    s1 = blame.drifting_keys(committed, gen_v1, ceiling=CEILING)["docs/B.md"]
    s2 = blame.drifting_keys(committed, gen_v2, ceiling=CEILING)["docs/B.md"]
    assert s1 != s2, "the only-on-one-side row changed and its signature did not"


def test_guilt_a_prior_flip_written_with_a_decorated_path_still_blocks_re_exemption() -> None:
    """One document, two spellings — the lesson this PR was built on, one level down.

    `prior_flips` is keyed by the RAW `File` cell (`docs_audit.parse_prev_flipped`)
    while every identity in this module is the undecorated path. A base row
    written `` `docs/x.md` `` and a head row written `docs/x.md` are ONE document
    to the drift comparison and TWO to the anti-resurrection lookup, so a flip
    the base had already spent could be stamped again and exempted.
    """
    committed = _full_table({"docs/audits/x.md": _ARCHIVED})
    generated = _full_table({"docs/audits/x.md": _LIVE})
    assert _drift(committed, generated) == set(), "the innocence baseline moved"
    charged = _drift(
        committed, generated, prior_flips={"`docs/audits/x.md`": "2026-07-20"}
    )
    assert charged == {"docs/audits/x.md"}


def test_guilt_a_directory_index_flip_is_never_earned() -> None:
    """A directory index can never be orphan-flipped by an honest run, so a
    committed ARCHIVED claim for one is drift, not a tolerated flip.

    Both spellings of the class, because they are one rule and would regress
    together: plain `README.md` and the numeric-ordering `00_README.md` the
    wave directories use.

    MEASURED, not assumed (2026-08-07): the first version of this test wrote
    the `File` cell DECORATED, to also pin that the call site normalises with
    `_row_key`. Its innocence control went red — a decorated row is charged as
    drift for ANY basename, so the guilt assertion was passing on decoration
    and would have stayed green with the directory-index rule deleted. The
    normalisation at the call site is therefore belt-and-braces rather than
    load-bearing, and is not claimed here as something this corpus proves.
    """
    for path in ("docs/topic/README.md", "docs/topic/00_README.md"):
        committed = _full_table({path: _ARCHIVED})
        generated = _full_table({path: _LIVE})
        assert _drift(committed, generated) == {path}, path


def test_innocence_an_earned_flip_on_a_non_index_doc_is_still_exempt() -> None:
    """The control for the test above, sharing its mechanism.

    Identical rows, identical dates — only the BASENAME differs. If these went
    red too, the directory-index refusal would be swallowing every earned flip
    rather than the class it names, and the guilt test alone could not tell the
    two apart.

    `INDEX.md` and `READMEISH.md` are here on purpose: they are the DECLARED
    LIMITS of `_is_directory_index` (only README, only with a numeric ordering
    prefix). Pinning them means a future widening of that regex — to other
    index-ish names, or to any name CONTAINING "README" — cannot land quietly.
    """
    for path in (
        "docs/topic/GUIDE.md",
        "docs/topic/INDEX.md",
        "docs/topic/READMEISH.md",
    ):
        committed = _full_table({path: _ARCHIVED})
        generated = _full_table({path: _LIVE})
        assert _drift(committed, generated) == set(), path
