#!/usr/bin/env python3
"""`docs/DOCS_INVENTORY.md` must not change just because a day passed.

THE DEFECT THIS PINS, measured on PR #3405 (2026-07-28). The inventory is a
GENERATED file that is also TRACKED, and it rendered `mtime_days` — an integer
derived from `time.time()`. So every row's cell went up by one every day with
no documentation having changed at all:

    699 doc rows changed in that PR
      633 of them (90.6%) differed ONLY in mtime_days   66 -> 67
       66 had a real difference

Two symptoms, one root:

  * `docs-inventory-refresh.yml` runs twice daily and decides whether to open a
    PR with `git diff --quiet` on the RAW file. So it opened one on essentially
    every run — 1558 lines of diff, ~90% of it clock churn. #3334 was closed as
    "cannot merge by construction, and its entire content is the churn line
    itself"; #3405 is the same PR one day later.
  * Any two branches that both regenerated collided on those 633 lines. That is
    the conflict treadmill, and it is why a docs-touching PR could be blocked by
    a file nobody had meaningfully edited.

An earlier fix (#3341) cured the `Last run:` stamp — `%Y-%m-%d %H:%M %Z` also
embedded the RUNNING MACHINE's timezone, so fleet regens wrote WITA and runner
regens wrote UTC and each rewrote the other. That was one line out of 634.
The remaining 633 were the same disease in the dominant term.

WHY THE `--check` GATE NEVER SAW IT: `strip_volatile()` normalized mtime_days
away before comparing. That silenced the GATE while leaving the FILE churning —
which is the half that actually hurt. A masker is not a cure; it just moves who
notices.

WHAT THIS TEST ASSERTS: the rendered inventory is a pure function of tree facts.
Advance every row's `mtime_days` by an absurd amount and the bytes must not
move. The property is deliberately stated over the RENDER, not over the column:
it stays true if someone adds a different clock-derived cell tomorrow, which a
test named after `mtime_days` would not catch.

`mtime_days` still exists on DocRow and still drives the orphan RULE in
classify(). This is about what gets WRITTEN, not what gets DECIDED.

Run: python3 scripts/tests/test_docs_inventory_render_is_clock_free.py
     (also collected by pytest)
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_AUDIT = REPO_ROOT / "scripts" / "docs_audit.py"


def _load_audit():
    spec = importlib.util.spec_from_file_location("_docs_audit_under_test", _AUDIT)
    assert spec and spec.loader, f"cannot load {_AUDIT}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_docs_audit_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def _sample_rows(audit):
    """A corpus that exercises every branch that ever printed an age.

    Includes an orphan row specifically: the `action` string and the "Orphans"
    section BOTH used to embed `mtime=<N>d`, so a fix that only dropped the
    table column would still churn on these two surfaces.
    """
    return [
        audit.DocRow(
            path="docs/ALIVE.md",
            status="LIVE",
            mtime_days=3,
            refs_in=7,
            last_touched_date="2026-07-25",
            orphan_eligible_on="2026-10-23",
        ),
        audit.DocRow(
            path="docs/ORPHANED.md",
            status="ARCHIVED",
            mtime_days=123,
            refs_in=0,
            last_touched_date="2026-03-26",
            orphan_eligible_on="2026-06-24",
            orphan_flipped_on="2026-07-19",
            action="archive: orphan, last_touched=2026-03-26, refs=0",
        ),
        audit.DocRow(
            path="docs/BROKEN.md",
            status="LIVE",
            mtime_days=40,
            refs_in=2,
            broken=3,
            drift=True,
            last_touched_date="2026-06-18",
            orphan_eligible_on="2026-09-16",
        ),
    ]


def test_the_render_is_not_vacuous() -> None:
    """Non-vacuity FIRST. Every assertion below is 'two renders are equal'; an
    empty or constant render satisfies all of them while proving nothing."""
    audit = _load_audit()
    text = audit.render_inventory(_sample_rows(audit), [])
    assert len(text) > 200, f"render is {len(text)} bytes — suspiciously empty"
    for path in ("docs/ALIVE.md", "docs/ORPHANED.md", "docs/BROKEN.md"):
        assert path in text, f"{path} missing from the render — the corpus is not reaching the table"
    assert "| File | Status |" in text, "table header missing — this is not an inventory"
    assert "### Orphans" in text, (
        "the Orphans section did not render — that section is one of the two "
        "places that used to embed an age, so a corpus that never reaches it "
        "would leave half the property untested"
    )


def test_advancing_the_clock_does_not_change_one_byte() -> None:
    """GUILT. The whole defect, in one assertion."""
    audit = _load_audit()

    before = audit.render_inventory(_sample_rows(audit), [])

    later = _sample_rows(audit)
    for r in later:
        r.mtime_days += 1000  # ~3 years pass; no doc is touched
    after = audit.render_inventory(later, [])

    assert after == before, (
        "the rendered inventory changed when only the wall clock moved.\n"
        "That is the #3405 defect: a generated-but-TRACKED file rewriting "
        "itself nightly, which (a) makes the twice-daily refresh open a churn "
        "PR on every run, and (b) collides with every branch that also "
        "regenerated. Render tree facts (dates), never ages.\n"
        "First differing line:\n  before: "
        + next(
            (b for b, a in zip(before.splitlines(), after.splitlines()) if a != b),
            "<none — lengths differ>",
        )
        + "\n  after:  "
        + next(
            (a for b, a in zip(before.splitlines(), after.splitlines()) if a != b),
            "<none — lengths differ>",
        )
    )


def test_no_age_token_is_rendered_anywhere() -> None:
    """GUILT, second face. Equality above is blind to an age that happens to be
    equal in the corpus; this catches the shape directly, wherever it hides."""
    audit = _load_audit()
    text = audit.render_inventory(_sample_rows(audit), [])
    hits = re.findall(r"mtime=\d+d|\(mtime[^)]*\)|\b\d+ days ago\b", text)
    assert not hits, (
        f"the render still emits an age token: {hits}. These were the "
        "`action` string and the Orphans bullet — both fed by mtime_days, both "
        "changing daily. Use the absolute `last_touched_date` instead."
    )


def test_a_real_documentation_change_still_moves_the_file() -> None:
    """INNOCENCE. Without this, deleting the whole table would pass every test
    above. The file must still be sensitive to the facts it exists to report."""
    audit = _load_audit()

    before = audit.render_inventory(_sample_rows(audit), [])

    touched = _sample_rows(audit)
    touched[0].last_touched_date = "2026-07-26"  # a real commit, one day later
    assert audit.render_inventory(touched, []) != before, (
        "last_touched_date changed and the render did not — the inventory has "
        "gone blind to the tree facts it reports"
    )

    relinked = _sample_rows(audit)
    relinked[0].refs_in = 99
    assert audit.render_inventory(relinked, []) != before, (
        "refs_in changed and the render did not"
    )

    broke = _sample_rows(audit)
    broke[0].broken = 5
    assert audit.render_inventory(broke, []) != before, (
        "broken-link count changed and the render did not"
    )


def test_the_header_and_the_row_width_agree() -> None:
    """The column count is asserted in two places (the header string and
    EXPECTED_COLUMNS). #3405's fix removed a column; a stale count in either
    place silently mis-anchors every positional reader downstream — which is
    exactly how strip_volatile() would have started blanking last_touched_date
    while believing it was blanking mtime_days."""
    audit = _load_audit()
    text = audit.render_inventory(_sample_rows(audit), [])

    header = next(line for line in text.splitlines() if line.startswith("| File | Status |"))
    header_cols = len([c for c in header.split("|")[1:-1]])

    row = next(line for line in text.splitlines() if line.startswith("| docs/ALIVE.md |"))
    row_cols = len([c for c in row.split("|")[1:-1]])

    assert header_cols == row_cols, (
        f"header declares {header_cols} columns, a data row renders {row_cols}"
    )
    src = _AUDIT.read_text(encoding="utf-8")
    declared = re.search(r"EXPECTED_COLUMNS\s*=\s*(\d+)", src)
    assert declared, "EXPECTED_COLUMNS not found — the pipe-smuggling guard moved"
    assert int(declared.group(1)) == header_cols, (
        f"EXPECTED_COLUMNS={declared.group(1)} but the header renders "
        f"{header_cols} columns"
    )


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {name}: {exc}")
    print(f"\n{'FAILED' if failures else 'OK'} — {failures} failure(s)")
    raise SystemExit(1 if failures else 0)
