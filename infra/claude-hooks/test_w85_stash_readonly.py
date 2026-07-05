#!/usr/bin/env python3
"""W85 pin — BLOCKED_SUBCMD_RE `stash` over-match, documented-broken contract.

W85 (cicatrix-scars.md, superscar #3): `BLOCKED_SUBCMD_RE` carries a bare
`stash`, so read-only `git stash list` / `git stash show` are blocked exactly
like the mutating `stash push` / `stash pop`. Third consecutive over-match of
the SAME guard in two days (after W83, W84) — the scar itself says the family
"non si chiude con un fix puntuale". The fix (enumerate mutating stash verbs,
or allow-list `stash (list|show)`) is tracked as a PENDING-ARMS line; it is
NOT applied here because patching the repo copy alone would fork it from the
live ~/.claude/hooks copy (superscar #1, W83 GOTCHA-d: patch BOTH or neither),
and the live copy governs the very session that would edit it.

W82-TRIPWIRE SEMANTICS (same as infra/scar-gates/test_W82_*): this test is
GREEN while the documented contract HOLDS — bug present and captured:
  GUILT  (guard still catches real danger): `git stash push` IS blocked.
  PINNED OVER-MATCH (the W85 hole, asserted PRESENT): `git stash list` and
         `git stash show` are ALSO blocked today.
The moment someone fixes the regex, the pinned assertions FAIL loudly →
update this pin to a plain innocence test + flip the registry note + close
the PENDING-ARMS line. A silent fix would otherwise leave the conformance
registry lying about the guard's contract.

    python3 infra/claude-hooks/test_w85_stash_readonly.py
Exit 0 = contract holds (guilt caught, over-match still present & documented).
Exit 1 = contract changed (either the guard went blind, or the W85 fix landed).

Reference: cicatrix-superscar.md #3 · registry: infra/guard-conformance/registry.json
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def _load_regex():
    spec = importlib.util.spec_from_file_location("wi_w85", str(HERE / "worktree_isolation.py"))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.BLOCKED_SUBCMD_RE


def main() -> int:
    regex = _load_regex()
    failures: list[str] = []

    # GUILT — the guard must still catch genuinely mutating stash commands.
    for cmd in ("git stash", "git stash push", "git stash pop"):
        if not regex.search(cmd):
            failures.append(f"GUILT MISS: `{cmd}` no longer blocked — guard went blind")

    # PINNED W85 OVER-MATCH — read-only stash queries are blocked TODAY.
    # These assertions document the bug; their failure means the fix landed.
    for cmd in ("git stash list", "git stash show"):
        if not regex.search(cmd):
            failures.append(
                f"W85 CONTRACT CHANGED: `{cmd}` is no longer blocked — the over-match "
                f"fix landed. Update this pin to a plain innocence test, flip the "
                f"registry.json note, close the W85 PENDING-ARMS line."
            )

    if failures:
        print("W85 PIN FAILED — the documented contract changed:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print(
        "OK (W85 pin) — guard catches mutating stash; read-only stash over-match "
        "still present and DOCUMENTED (fix tracked in PENDING-ARMS, not silent)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
