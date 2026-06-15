#!/usr/bin/env python3
"""Drift sentinel for the guardrails BLOCK_PATTERNS (superscar #1 antidote).

THE PROBLEM. There are THREE copies of the dangerous-command pattern list:
  1. scripts/guardrails_static_core.py  — the CI-tested SOURCE OF TRUTH (repo).
  2. ~/.claude/hooks/guardrails-static.py "VENDORED FALLBACK" — a hand-copied
     duplicate used only when the repo core is unreachable (HOME-only, off-repo).
  3. the LIVE behavior of the hook on this machine.
The docstring claims (2) is "byte-identical" to (1) — but it is enforced by HOPE,
not by code. The opus-mythos hooks TAC (2026-06-16) found the vendored fallback
is a PATCHWORK: the python-c pattern was updated, but the force-push and
curl/wget pipe patterns were left STALE. Nobody knew which was current.

THIS TOOL closes the loop:
  - default / --check : compare the core's BLOCK_PATTERNS (regex source + reason)
    against the vendored fallback in the live hook. Exit 1 + a readable diff if
    they drift. This is the heartbeat — run it in CI (repo side can't see the
    HOME file, so this is an OPERATOR/cron gate per machine) and on session start.
  - --apply : regenerate the vendored fallback's BLOCK_PATTERNS block IN PLACE
    from the core, so the duplicate is DERIVED, never hand-edited. Backs up first.

Reason-keyed comparison: a pattern is identified by its human reason string
(stable across regex edits), so a regex change to a known reason is reported as a
MODIFY, an added/removed reason as ADD/REMOVE.

Usage:
  python3 scripts/guardrails_sync_check.py            # check, exit 1 on drift
  python3 scripts/guardrails_sync_check.py --apply     # regenerate vendored block
  python3 scripts/guardrails_sync_check.py --hook PATH # explicit live hook path
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
CORE = HERE / "guardrails_static_core.py"
DEFAULT_HOOK = pathlib.Path(os.path.expanduser("~")) / ".claude" / "hooks" / "guardrails-static.py"


def _load_core_patterns() -> list[tuple[str, str, int]]:
    """Return [(regex_source, reason, flags)] from the core's BLOCK_PATTERNS."""
    spec = importlib.util.spec_from_file_location("gcore", str(CORE))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = []
    for pat, reason in mod.BLOCK_PATTERNS:
        out.append((pat.pattern, reason, pat.flags))
    return out


# Matches the assignment header in BOTH forms:
#   BLOCK_PATTERNS = [                       (vendored fallback)
#   BLOCK_PATTERNS: list[...] = [            (core, type-annotated)
_BLOCK_HEADER = re.compile(r"^BLOCK_PATTERNS\b[^\n=]*=\s*\[", re.MULTILINE)


def _extract_vendored_block(hook_src: str) -> tuple[int, int] | None:
    """Locate the start/end char offsets of the `BLOCK_PATTERNS ... = [ ... ]`
    literal in the source (with or without a type annotation). Returns
    (start_idx, end_idx_exclusive) or None. The returned text starts at
    `BLOCK_PATTERNS` and ends just after the matching `]`."""
    m = _BLOCK_HEADER.search(hook_src)
    if not m:
        return None
    start = m.start()
    i = m.end() - 1  # index of the opening '['
    depth = 0
    while i < len(hook_src):
        c = hook_src[i]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return (start, i + 1)
        i += 1
    return None


def _load_vendored_patterns(hook_path: pathlib.Path):
    """Load the vendored fallback's BLOCK_PATTERNS by importing the WHOLE hook as
    a module (robust — no text slicing of code). The hook is import-safe: its
    main() runs only under `if __name__ == "__main__"`, and _load_repo_core() is
    lazy (called inside main), so importing it just defines the module-level
    BLOCK_PATTERNS we want. Returns [(regex_source, reason, flags)] or None."""
    try:
        spec = importlib.util.spec_from_file_location("gstatic_vendored", str(hook_path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as e:  # pragma: no cover
        print(f"  ! could not import vendored hook: {e}", file=sys.stderr)
        return None
    patterns = getattr(mod, "BLOCK_PATTERNS", None)
    if patterns is None:
        return None
    out = []
    for pat, reason in patterns:
        out.append((pat.pattern, reason, pat.flags))
    return out


def _diff(core, vendored) -> list[str]:
    """Reason-keyed diff. Returns human lines; empty = in sync."""
    cmap = {r: (p, f) for p, r, f in core}
    vmap = {r: (p, f) for p, r, f in vendored}
    lines = []
    for reason in cmap:
        if reason not in vmap:
            lines.append(f"  ADD (in core, missing in vendored): {reason!r}")
        elif cmap[reason][0] != vmap[reason][0]:
            lines.append(f"  MODIFY {reason!r}\n      core    : {cmap[reason][0]}\n      vendored: {vmap[reason][0]}")
    for reason in vmap:
        if reason not in cmap:
            lines.append(f"  REMOVE (in vendored, gone from core): {reason!r}")
    return lines


def _core_block_text() -> str:
    """Return the EXACT `BLOCK_PATTERNS = [ ... ]` literal text from the core
    source, verbatim. We splice this text into the vendored fallback rather than
    re-rendering regexes from parsed objects — re-rendering regex sources back
    into Python string literals is a backslash/quote-escaping minefield (raw
    strings can't hold mixed quotes cleanly). The core literal is already valid,
    correctly-escaped Python; copying its text preserves it byte-for-byte."""
    src = CORE.read_text()
    span = _extract_vendored_block(src)  # same delimiter logic; finds the literal
    if not span:
        raise RuntimeError(f"could not find BLOCK_PATTERNS literal in {CORE}")
    return src[span[0]:span[1]]


def main() -> int:
    ap = argparse.ArgumentParser(description="guardrails core<->vendored drift sentinel")
    ap.add_argument("--apply", action="store_true", help="regenerate vendored block from core")
    ap.add_argument("--hook", default=str(DEFAULT_HOOK), help="path to live guardrails-static.py")
    args = ap.parse_args()

    hook_path = pathlib.Path(args.hook)
    if not CORE.is_file():
        print(f"FATAL: core not found at {CORE}", file=sys.stderr)
        return 2
    core = _load_core_patterns()

    if not hook_path.is_file():
        # No live hook on this machine (e.g. CI runner) — the core is the only
        # copy; nothing to drift against. Report and pass (sentinel is per-machine).
        print(f"NO LIVE HOOK at {hook_path} — core has {len(core)} patterns, nothing to compare. PASS (sentinel is per-machine).")
        return 0

    vendored = _load_vendored_patterns(hook_path)
    if vendored is None:
        print(f"FATAL: could not extract vendored BLOCK_PATTERNS from {hook_path}", file=sys.stderr)
        return 2

    drift = _diff(core, vendored)

    if args.apply:
        if not drift:
            print("Already in sync — nothing to regenerate.")
            return 0
        src = hook_path.read_text()
        span = _extract_vendored_block(src)
        backup = hook_path.with_suffix(hook_path.suffix + ".bak-sync")
        backup.write_text(src)
        new_src = src[:span[0]] + _core_block_text() + src[span[1]:]
        hook_path.write_text(new_src)
        print(f"Regenerated vendored BLOCK_PATTERNS from core ({len(core)} patterns).")
        print(f"Backup: {backup}")
        print("Re-run without --apply to confirm 0 drift, and run the innocence vaccine.")
        return 0

    if drift:
        print(f"DRIFT: core ({len(core)}) vs vendored ({len(vendored)}) in {hook_path}:")
        print("\n".join(drift))
        print("\nFix: python3 scripts/guardrails_sync_check.py --apply")
        return 1

    print(f"IN SYNC: {len(core)} patterns identical (core <-> vendored).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
