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
from pathlib import Path

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


def row_map(content: str) -> dict[str, str]:
    """Map doc path -> full row line, for every table row naming a document."""
    out: dict[str, str] = {}
    for line in content.splitlines():
        m = _ROW_RE.match(line)
        if not m:
            continue
        key = m.group("key").strip().strip("`[]")
        # `[`docs/x.md`](docs/x.md)` style cells: take the link text.
        key = re.sub(r"^\[(.*?)\]\(.*\)$", r"\1", key).strip("`")
        if _is_doc_key(key):
            out[key] = line.strip()
    return out


def drifting_keys(committed: str, generated: str) -> set[str]:
    """Keys whose row differs between the committed and generated tables.

    Includes rows added or removed, not only rows whose cells changed — a doc
    that appears in one table and not the other is drift of the loudest kind.
    """
    a, b = row_map(committed), row_map(generated)
    changed = {k for k in a.keys() & b.keys() if a[k] != b[k]}
    return changed | (a.keys() ^ b.keys())


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
    args = ap.parse_args(argv)

    base = drifting_keys(_read(args.committed_base), _read(args.generated_base))
    head = drifting_keys(_read(args.committed_head), _read(args.generated_head))

    introduced = sorted(head - base)
    inherited = sorted(head & base)
    repaired = sorted(base - head)

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
