#!/usr/bin/env python3
"""Decide whether a PR is to BLAME for docs/DOCS_INVENTORY.md being out of date.

Why this exists
---------------
`docs_audit.py --check` compares the committed inventory byte-for-byte against a
freshly generated one and fails on ANY difference. For a table derived from the
WHOLE repository, in a repo where main moves every ~20 minutes, that asks each
PR to make a global artifact exactly correct at merge time — including drift it
did not cause.

Measured consequences of that rule, both on 2026-07-26:

  * PR #3106 redacted a key in two `docs/superpowers/**` files without
    regenerating. It merged (this gate is not a required context). The NEXT
    docs-touching PR, #3149, inherited the red it did not earn.
  * The refresh organ's own PR #3203 failed its own gate on a ONE-LINE
    difference — `**Orphans:** 65` committed vs `64` generated — because main
    moved between the 09:13Z regeneration and the 15:11Z check. The organ
    cannot win a race it is structurally guaranteed to lose.

The rule this implements
------------------------
    A PR fails only if it makes the inventory MORE inconsistent than the base
    already is.

Concretely: compute the set of drifting KEYS at the base and at the head. A key
present at head but not at base is the PR's fault. A key present at both is
pre-existing main drift, reported but not charged to this PR. Fewer keys at head
than base means the PR is repairing drift — which is exactly what the refresh
organ does, and it must not be punished for it.

This is the "compare the PR-CAUSED delta, never the absolute state" cure that
`.claude/skills/modus/PENDING-ARMS.md` has carried as open since 2026-07-16.

What a KEY is
-------------
One per table row, keyed by the document path — the unit a human can act on.
Aggregate lines (`| LIVE | 625 | 67% |`, `**Drift:** 0 · ... · **Orphans:** 65`)
are deliberately NOT keys: they are consequences of the rows, so a counter that
moves because some other PR archived a doc is never this PR's fault. If a PR
genuinely changes rows, those rows are charged to it and the counters follow.

Deliberately NOT parsing `--check`'s printed diff
-------------------------------------------------
`docs_audit.print_check_delta()` truncates its output at 200 lines and appends
"... diff truncated after N lines ...". Parsing that would silently under-count
drift keys on a large diff and let a guilty PR pass — a display cap read as a
complete list (scar W97). This compares the FILES.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# The orphan-flip rule is NOT re-derived here — it is imported. See
# `orphan_flip_claim_is_legitimate`'s docstring for what happened the one time
# this file wrote its own copy.
from docs_audit import (  # noqa: E402
    _parse_inventory_table,
    _trusted_ref_tip_date,
    archive_orphan_action,
    orphan_flip_claim_is_legitimate,
    parse_prev_flipped,
)

# A table row: `| docs/FOO.md | LIVE | 12 | 2026-07-01 | ... |`
# The key is the first cell. Rows whose first cell is a header/among the status
# summary block are excluded by _is_doc_key below.
_ROW_RE = re.compile(r"^\|\s*(?P<key>[^|]+?)\s*\|")

# First-cell values that appear in the summary block or the header, not as docs.
_NON_DOC_KEYS = frozenset(
    {"Status", "Count", "LIVE", "STALE", "ARCHIVED", "Doc", "Path", "File"}
)


def _is_doc_key(key: str) -> bool:
    """True when the first cell names a document rather than a summary label."""
    if not key or key in _NON_DOC_KEYS:
        return False
    if set(key) <= set("-: "):  # markdown separator row `| ------- | :--- |`
        return False
    return key.endswith(".md")


_LINK_RE = re.compile(r"^\[(?P<text>.+?)\]\(.*\)$")


def _row_key(cell: str) -> str:
    """The document path a first cell names, undecorated.

    ONE definition, called by every scanner below. It used to be inlined twice —
    identically, which is exactly how the bug survived: `.strip("`[]")` ran
    BEFORE the link regex, so it ate the leading `[` and `[docs/x.md](docs/x.md)`
    became `docs/x.md](docs/x.md)`, which fails `_is_doc_key` and made the whole
    row INVISIBLE to the comparison while `_parse_inventory_table` still saw it.
    The link normalisation this file advertised had never once fired. Measured
    2026-07-29, found by a cross-family refuter.
    """
    cell = cell.strip()
    m = _LINK_RE.match(cell)
    if m:
        cell = m.group("text")
    return cell.strip("`").strip()


def _scan_rows(content: str) -> list[tuple[str, str]]:
    """(path, raw line) for every table row naming a document, in file order."""
    out: list[tuple[str, str]] = []
    for line in content.splitlines():
        m = _ROW_RE.match(line)
        if not m:
            continue
        key = _row_key(m.group("key"))
        if _is_doc_key(key):
            out.append((key, line.strip()))
    return out


def row_map(content: str) -> dict[str, str]:
    """Map doc path -> full row line, for every table row naming a document.

    Last row wins on a duplicated path — deliberately NOT resolved here, because
    a duplicate is not a thing to resolve. `_duplicate_keys` reports it and
    `drifting_keys` charges it.
    """
    return dict(_scan_rows(content))


def table_header(content: str) -> str:
    """The inventory table's header line, or '' if there isn't one.

    Compared between the two tables because everything else in this file reads
    ROWS, and a PR that renames `| File |` to `| Files |` leaves every row
    untouched: `_parse_inventory_table` then returns {} while `row_map` still
    finds all the rows, no row differs, and the gate passes on a table whose
    schema has been broken. Measured — the probe returned `set()`.

    Anchored on the SAME prefix `_parse_inventory_table` looks for, deliberately.
    Two functions that must agree on "where the table starts" cannot be allowed
    two answers, or this one reports a header the other never read.
    """
    for line in content.splitlines():
        if line.startswith("| File "):
            return line.strip()
    return ""


# The three cells an orphan flip legitimately moves, BY HEADER NAME — never by
# positional index. `_parse_inventory_table` matches on the header row, so a
# future column reorder cannot silently make this exempt the wrong cell.
_FLIP_MOVES = frozenset({"Status", "orphan_flipped_on", "action"})

# What the generated (pre-flip) side of a legitimate flip must say. Measured on
# the live table 2026-07-29: all 118 flip-eligible rows (LIVE, refs_in == 0)
# carry exactly this pair. Pinning `action` here is what closes the whitelist
# gap the shared predicate cannot see: a whitelisted doc renders
# `action = "whitelist"` (docs_audit.classify), never the em-dash.
_UNFLIPPED = ("", "—")


def _duplicate_keys(content: str) -> set[str]:
    """Paths that appear on more than one row of the same table.

    `row_map` is a dict, so a duplicated path silently keeps the LAST row and
    the earlier one vanishes — a PR could hide a corrupt row behind a clean
    one and the comparison would never see it. A duplicate is not something to
    resolve; it is drift by itself.
    """
    seen: dict[str, int] = {}
    for key, _line in _scan_rows(content):
        seen[key] = seen.get(key, 0) + 1
    return {k for k, n in seen.items() if n > 1}


def _is_earned_flip(
    committed_cells: dict[str, str],
    generated_cells: dict[str, str],
    *,
    prior_flips: dict[str, str],
    ceiling,
) -> bool:
    """True when the only difference is an orphan flip the row itself justifies.

    THE DEFECT THIS EXISTS FOR (measured 2026-07-29). P3-prime deliberately moved
    the wall-clock decision "has this doc's orphan_eligible_on passed?" INTO the
    scheduled refresh organ: `docs_inventory_regen.sh --organ` advances flips,
    and the bare/default invocation the GATE uses is `--gate-consistent`, which
    never invents one. But the comparison below was on the whole row, so the
    three cells a flip moves — Status, orphan_flipped_on, action — read as drift.
    Every flip the organ exists to advance was charged to the organ's own PR.

    Not theoretical. Of the six refresh PRs the organ has opened, the two that
    merged (#3411, #3425) carried ZERO flips; every one that carried a flip died
    (#3405 with 65, #3456 and #3463 with 9). The organ could only ever deliver
    the half of its job that did not matter.

    WHY THE LEGITIMACY TEST IS IMPORTED, NOT WRITTEN HERE. The first version of
    this function (same day, before a cross-family red-team) decided legitimacy
    on its own: it ignored `refs_in`, so ANY live doc — including a whitelisted
    one with four inbound references — could be hand-marked ARCHIVED and walk
    through; and it bounded the flip date only from BELOW, so `2099-12-31`
    passed. Both holes were already closed, and argued at length, in
    `docs_audit.orphan_flip_claim_is_legitimate` — hardened by the 2026-07-25
    round against a live `GIT_COMMITTER_DATE` forgery. Writing a second, weaker
    copy of a guard does not double the protection: it publishes the weaker one
    as the way in.

    What this function still owns is what only a RENDERED pair can check, and
    it is deliberately the strict half:

      * every non-flip cell identical, matched BY HEADER NAME;
      * the generated side genuinely un-flipped (`orphan_flipped_on` and
        `action` both em-dash) — which is also what excludes a whitelisted doc,
        since whitelisting renders `action = "whitelist"`;
      * the committed `action` equal to `archive_orphan_action(last_touched)`,
        i.e. a pure function of a cell that is itself compared verbatim — so
        the exemption cannot be used to smuggle arbitrary text into a row.

    Not clock-free, and the earlier claim that it was is withdrawn: the ceiling
    that blocks future-dating is `max(origin/main tip, now)`, exactly as
    `docs_audit --check` computes it. The core decision stays clock-free (both
    dates are cells); the ceiling is a sanity bound that can only ever turn a
    REJECTED claim into a tolerated one as real time passes, never the reverse.
    """
    if not committed_cells or not generated_cells:
        return False
    if committed_cells.keys() != generated_cells.keys():
        return False
    if any(
        committed_cells[h] != generated_cells[h]
        for h in committed_cells
        if h not in _FLIP_MOVES
    ):
        return False
    if committed_cells.get("Status") != "ARCHIVED":
        return False
    if generated_cells.get("Status") != "LIVE":
        return False
    if generated_cells.get("orphan_flipped_on", "").strip() not in _UNFLIPPED:
        return False
    if generated_cells.get("action", "").strip() not in _UNFLIPPED:
        return False
    if committed_cells.get("action") != archive_orphan_action(
        committed_cells.get("last_touched_date", "")
    ):
        return False
    return orphan_flip_claim_is_legitimate(
        trusted_ref_has_prior_flip=committed_cells.get("File", "") in prior_flips,
        generated_refs_in=generated_cells.get("refs_in", ""),
        generated_eligible_on=generated_cells.get("orphan_eligible_on", ""),
        committed_flipped_on=committed_cells.get("orphan_flipped_on", ""),
        committed_refs_in=committed_cells.get("refs_in", ""),
        trusted_ref_ceiling_date=ceiling,
    )


# Not a document path, so it can never collide with one (`_is_doc_key` requires
# a `.md` suffix). Names the table itself as the thing that drifted.
TABLE_KEY = "<inventory table header>"


def drifting_keys(
    committed: str,
    generated: str,
    *,
    prior_flips: dict[str, str] | None = None,
    ceiling=None,
) -> dict[str, str]:
    """Drifting key -> a SIGNATURE of how it drifts.

    Returns a mapping, not a set, and that is the point. The gate passes when
    head introduces no drift the base did not already have, and comparing only
    the KEYS made "already drifting" a licence: a doc drifting LIVE->STALE on
    the base could be worsened to LIVE->ARCHIVED, or have unrelated cells
    corrupted, and the key stayed in both sets so `head - base` was empty and
    the PR passed. The signature makes "the same drift" mean the same drift.

    A key is drifting when any of these hold:

      * its row differs between the two tables and the difference is not an
        earned orphan flip (see `_is_earned_flip`);
      * it appears in one table and not the other — drift of the loudest kind;
      * it is duplicated within a table, which a dict comparison would swallow;
      * the two parsers in this file disagree about whether the row exists.
        `row_map` scans raw lines while `_parse_inventory_table` matches the
        header row and drops any line whose cell count is wrong, so a row that
        only one of them sees is a row the exemption cannot be trusted about.

    `TABLE_KEY` is reported when the header lines themselves differ. Everything
    else here reads rows, and a renamed header leaves every row untouched.

    With no `ceiling` the exemption cannot fire at all: the shared predicate
    fails closed, which is the right default for a caller that has established
    no trustworthy upper bound on a claimed date.
    """
    a, b = row_map(committed), row_map(generated)
    ca, cb = _parse_inventory_table(committed), _parse_inventory_table(generated)
    prior_flips = prior_flips or {}
    dupes = _duplicate_keys(committed) | _duplicate_keys(generated)
    # A path one parser sees and the other does not: the cells the exemption
    # would reason about are missing or belong to a different row.
    unreconciled = (a.keys() ^ ca.keys()) | (b.keys() ^ cb.keys())

    out: dict[str, str] = {}
    if table_header(committed) != table_header(generated):
        out[TABLE_KEY] = f"header {table_header(committed)!r} != {table_header(generated)!r}"
    for k in a.keys() | b.keys():
        # ORDER MATTERS, and getting it wrong is how the first build of this
        # loop hid the very drift it was meant to expose: the reconciliation
        # marker was tested FIRST, so an unparseable row got a CONSTANT
        # signature — identical at base and at head — and a genuine row
        # difference underneath it read as "inherited". A marker must never
        # replace a real difference; it only speaks when there is none.
        if k in dupes:
            out[k] = "duplicated row"
        elif k not in a or k not in b:
            out[k] = f"present only in {'committed' if k in a else 'generated'}"
        elif a[k] != b[k] and not _is_earned_flip(
            ca.get(k, {}), cb.get(k, {}), prior_flips=prior_flips, ceiling=ceiling
        ):
            out[k] = f"{a[k]} != {b[k]}"
        elif k in unreconciled:
            out[k] = "row visible to only one parser"
    return out


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"docs_inventory_blame: cannot read {p}: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--committed-base", type=Path, required=True)
    ap.add_argument("--generated-base", type=Path, required=True)
    ap.add_argument("--committed-head", type=Path, required=True)
    ap.add_argument("--generated-head", type=Path, required=True)
    ap.add_argument(
        "--max-listed",
        type=int,
        default=40,
        help="cap on keys PRINTED per bucket; counts are always reported in full",
    )
    ap.add_argument("--repo", type=Path, default=Path("."))
    ap.add_argument("--trusted-ref", default="origin/main")
    args = ap.parse_args(argv)

    committed_base = _read(args.committed_base)

    # The upper bound on a claimed flip date, computed exactly as
    # `docs_audit --check` computes it: the LATER of the trusted ref's own tip
    # commit date and real "now", neither of which the PR branch controls.
    # Never a commit date read from the PR's own branch — that is forgeable via
    # GIT_COMMITTER_DATE, demonstrated live against the first version of the
    # --check fix (2026-07-25).
    tip = _trusted_ref_tip_date(args.repo.resolve(), args.trusted_ref)
    now_date = datetime.now(tz=timezone.utc).date()
    ceiling = max(tip, now_date) if tip else now_date
    # Say which source was accepted. A guard that silently degrades to its
    # fallback is a guard nobody can tell is degraded (W106).
    print(
        f"docs_inventory_blame: flip-date ceiling {ceiling.isoformat()} "
        + (
            f"(later of {args.trusted_ref} tip {tip.isoformat()} and now)"
            if tip
            else f"(now only — {args.trusted_ref} did not resolve)"
        )
    )

    # Prior flip provenance comes from the BASE's committed table, which is the
    # tip this PR is measured against — the same trust boundary
    # `read_trusted_prev_flipped()` established. A path already flipped there
    # can never be exempted again (anti-resurrection).
    prior_flips = parse_prev_flipped(committed_base)

    base = drifting_keys(
        committed_base,
        _read(args.generated_base),
        prior_flips=prior_flips,
        ceiling=ceiling,
    )
    head = drifting_keys(
        _read(args.committed_head),
        _read(args.generated_head),
        prior_flips=prior_flips,
        ceiling=ceiling,
    )

    # Compared by SIGNATURE, not by key. A key drifting at both ends is only
    # "inherited" when it drifts the SAME WAY; drift the PR changed on a
    # already-broken row is drift the PR introduced.
    introduced = sorted(k for k, sig in head.items() if base.get(k) != sig)
    inherited = sorted(k for k, sig in head.items() if base.get(k) == sig)
    repaired = sorted(k for k in base if k not in head)

    def show(label: str, keys: list[str]) -> None:
        # Never print a truncated list as if it were whole (W97): the count is
        # stated first and the elision is explicit.
        print(f"{label}: {len(keys)}")
        for k in keys[: args.max_listed]:
            print(f"    {k}")
        if len(keys) > args.max_listed:
            print(f"    … {len(keys) - args.max_listed} more not listed above")

    if repaired:
        show("inventory rows this PR REPAIRS", repaired)
    if inherited:
        show("pre-existing drift on the base (NOT charged to this PR)", inherited)

    if not introduced:
        print(
            "docs_inventory_blame: PASS — this PR introduces no new inventory drift."
        )
        return 0

    show("inventory rows this PR makes STALE", introduced)
    print(
        "::error::This PR changes docs in ways the committed "
        "docs/DOCS_INVENTORY.md does not reflect. Regenerate it in THIS commit "
        "(`bash scripts/docs_inventory_regen.sh`) — a derived artifact must land "
        "with the change that derives it, never in a follow-up (scar W86). Rows "
        "already drifting on the base are listed separately above and are not "
        "your responsibility.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
