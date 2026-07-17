#!/usr/bin/env python3
"""prepush_classify.py — SSOT classifier for the path-aware `.husky/pre-push` gate.

Mandate (2026-07-17, Zero GO): a PR that does not touch the backend should
not pay for the full Python suite (17,384 tests, 11-32min) on every push.
This script is the ONLY place that decides `full` vs `skip-backend` — the
decision logic is deliberately NOT inline bash (cicatrix-superscar.md #3:
"nessuna guardia mergiata senza un test di innocenza E di colpevolezza";
a pure, importable function is what makes that test possible). The bash
hook (`.husky/pre-push`) owns git-plumbing only: reading the pre-push
stdin protocol, computing per-ref diff ranges, and unioning the changed
files across all pushed refs. THIS script owns zero git/subprocess state —
it is a pure function of a file list, which is what makes it fast to test
and impossible to fool with a crafted cwd.

DESIGN INVERSION (2026-07-17, same day, 3-LLM adversarial panel — GPT-5.6-Sol
ultra + GLM 5.2 + Gemini 3.1 Pro, unanimous verdict on the mother spec): the
FIRST version of this script was a DENYLIST — enumerate backend-relevant
paths, default to skip. The panel rejected that shape: an incomplete
denylist fails SILENTLY (a forgotten backend-relevant path just... skips —
exactly the W82 under-match failure mode, cicatrix-superscar.md #3). This
version is an ALLOWLIST instead — enumerate known-INNOCENT paths, default
to full. An incomplete allowlist now fails LOUD and SAFE: any path the
allowlist does not recognize runs the full suite. The failure mode is
inverted into the safe direction on purpose. See ALLOWLIST_INNOCENT_PREFIXES
below for the (deliberately narrow, individually verified) list.

CONTRACT
--------
Input:  a list of repo-relative file paths, one per line, via:
          - argv (positional args) when any are given — convenience for
            tests/manual invocation, e.g. `prepush_classify.py foo.py bar.py`
          - stdin (newline-separated) otherwise — the hook's real usage,
            piping the unioned `git diff --no-renames --name-only` output
            straight through (the `--no-renames` on the BASH side is
            load-bearing — see "RENAME SAFETY" below; this script has no
            opinion on it, it just trusts every line it receives is a real
            path this push touched).
        A line equal to the literal sentinel ERROR_SENTINEL means "the
        caller could not safely compute the diff" — see FAIL-CLOSED below.

Output: **stdout** carries EXACTLY one line, one of the two verdict
        strings — `full` or `skip-backend` — and nothing else. This is
        the machine-readable contract; a caller does a plain string
        comparison, no parsing. All human-readable diagnostics (file
        counts, which allowlist rule approved which file, the LOUD skip
        banner, the CI reminder) go to **stderr**, so stdout stays
        trivially parseable even under `set -x` / verbose shells.

Exit code: 0 for every DELIBERATE verdict (including a fail-closed `full`
        triggered by the sentinel — that is a successful decision, not a
        crash). An uncaught exception exits non-zero with a traceback,
        by design: the bash hook is REQUIRED to treat "non-zero exit" OR
        "stdout is not exactly 'full' or 'skip-backend'" as an
        independent, second-layer fail-closed signal — this script's own
        internal care is belt, the hook's exit/output check is suspenders
        (mandate point 4: "FAIL-CLOSED ovunque").

FAIL-CLOSED SEMANTICS
----------------------
- ERROR_SENTINEL present anywhere in the input -> "full". The hook emits
  this when it could not safely compute a diff range for some pushed ref
  (merge-base failed, `git fetch origin main` failed, `git diff` failed, a
  malformed pre-push stdin line, or zero ref lines read at all) — see
  `.husky/pre-push` for the emitting side.
- Empty input (zero non-blank lines, no sentinel) -> "skip-backend",
  LOGGED. This is the legitimate delete-only-push case (a ref deletion
  contributes no files to the union) and is NOT an error.
- Any file NOT provably matched by the allowlist -> contributes to "full".
  This is the load-bearing inversion above: unknown is never innocent.
- Any exception while reading/decoding stdin -> caught in `main()`,
  logged to stderr, verdict forced to "full" (fail-closed), exit 0 (a
  handled, deliberate decision — see exit-code note above).

RENAME SAFETY (verified empirically 2026-07-17, Sol's panel point)
--------------------------------------------------------------------
`git diff --name-only` (WITHOUT `--no-renames`) collapses a detected
rename to a SINGLE line — the DESTINATION path only. Reproduced live in a
throwaway repo: renaming `srcdir/thing.py` -> `dstdir/thing.py.bak` made
plain `git diff --name-only HEAD~1 HEAD` print only `dstdir/thing.py.bak`;
the source path `srcdir/thing.py` never appeared. If `srcdir` had been
`apps/backend-rag/...` and `dstdir` had been an allowlisted directory, a
file LEAVING the backend entirely would be invisible to this classifier —
exactly the under-match the panel is worried about. Fix lives on the BASH
side: every `git diff` invocation in `.husky/pre-push` uses `--no-renames`,
which always reports a rename as delete+add (BOTH paths present in the
union). This module has no rename awareness of its own — it is a
consequence of the input contract being trustworthy, not something this
script re-derives.

Run:
    python3 scripts/prepush_classify.py <<< "$FILES"
    python3 scripts/prepush_classify.py apps/backend-rag/backend/foo.py
"""
from __future__ import annotations

import sys
from typing import Iterable

# ---------------------------------------------------------------------------
# Sentinel — see "FAIL-CLOSED SEMANTICS" above. Deliberately shaped so it can
# never collide with a real git path (dunder-wrapped, uppercase, no slash).
# ---------------------------------------------------------------------------
ERROR_SENTINEL = "__PREPUSH_DIFF_ERROR__"

VERDICT_FULL = "full"
VERDICT_SKIP = "skip-backend"

# Bump whenever ALLOWLIST_INNOCENT_PREFIXES / ALLOWLIST_PREFIX_SUFFIX_PAIRS /
# NEVER_INNOCENT_* change, so a skip-banner log line ("allowlist vN") is
# attributable to a specific version of the rules that approved it (mandate
# point 5: "elenca i file E la allowlist-version che li ha approvati").
ALLOWLIST_VERSION = 1

# ---------------------------------------------------------------------------
# NEVER_INNOCENT_EXACT_PATHS — checked FIRST, unconditionally, before any
# allowlist matching. Belt-and-suspenders self-paranoia (mandate, explicit):
# these three MUST always force `full` even if a future edit accidentally
# broadens an allowlist entry to swallow one of them. The first two are
# structurally redundant already (neither is under any allowlisted prefix
# below) — kept anyway because "self-change -> full" must never depend on
# the allowlist staying correctly narrow. tests.yml is likewise already
# covered for free (no .github/** path is ever allowlisted, see below) —
# kept as the same defense-in-depth.
# ---------------------------------------------------------------------------
NEVER_INNOCENT_EXACT_PATHS: frozenset[str] = frozenset(
    {
        ".husky/pre-push",
        "scripts/prepush_classify.py",
        ".github/workflows/tests.yml",
    }
)

# Any file with one of these BASENAMES is never innocent, in ANY directory —
# panel point 4, verbatim concern: "conftest.py/plugin pytest A QUALSIASI
# livello... Dockerfile/compose... pyproject/setup.cfg/pytest.ini/tox.ini
# ovunque". Redundant with the narrow allowlist below in the common case
# (none of these basenames plausibly live under docs/, research/, or the
# allowlisted .claude/ content dirs) — kept as an explicit,
# directory-independent net so a future allowlist entry cannot silently
# reintroduce this exact class of bug.
NEVER_INNOCENT_BASENAMES: frozenset[str] = frozenset(
    {
        "conftest.py",
        "pytest.ini",
        "pyproject.toml",
        "setup.cfg",
        "tox.ini",
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        ".env.example",
    }
)

# ---------------------------------------------------------------------------
# ALLOWLIST_INNOCENT_PREFIXES — deliberately NARROW. Every entry verified
# against the actual repo tree 2026-07-17 (never assumed — "verify against
# actual data, never presume", CLAUDE.md golden rule #9):
#
#   docs/**              documentation only.
#   research/**          ad-hoc research captures (CLAUDE.md §15), never
#                         auto-promoted into apps/backend-rag/backend/kb/.
#   .claude/skills/**    skill markdown — verified: pure content.
#   .claude/rules/**     rule markdown (e.g. cicatrix-superscar.md) —
#                         verified: pure content.
#   .claude/commands/**  slash-command markdown — verified: pure content.
#   .claude/agents/**    vendored agent persona markdown — verified:
#                         content, no execution semantics.
#
# Deliberately NOT `.claude/**` wholesale, even though an earlier draft of
# the panel's example list said ".claude/** non-hook": `ls .claude/` also
# shows .claude/hooks/ (control-plane — contains codex-spalla-trigger.sh,
# verified on disk), .claude/scripts/, .claude/settings.json +
# .claude/settings.local.json (+ several .bak-* variants), .claude/
# worktrees/, .claude/worktrees-week0/. None of those are content-only, so
# NONE of them are allowlisted — a change under any of them falls to the
# "unknown -> full" default like everything else not explicitly listed
# here. A narrow allowlist that requires no exception-carve-outs is safer
# than a broad one riddled with them (cicatrix-superscar.md #3, W91: "anche
# un'eccezione è una guardia a segno invertito, vuole guilt+innocence
# propri" — every carve-out is itself a guard that needs its own proof;
# zero carve-outs needed here is a feature, not an oversight).
#
# `memory/**` (from the panel's example list) is deliberately OMITTED: it
# does not exist as a repo-tracked path (verified — `ls memory/` at repo
# root: No such file or directory). The user's actual memory store lives
# under `~/.claude/projects/.../memory/`, outside the repo entirely, so a
# `git diff` could never show it changing anyway. Adding a dead rule for a
# path that cannot appear would be presuming, not verifying.
# ---------------------------------------------------------------------------
ALLOWLIST_INNOCENT_PREFIXES: tuple[str, ...] = (
    "docs",
    "research",
    ".claude/skills",
    ".claude/rules",
    ".claude/commands",
    ".claude/agents",
)

# (prefix, allowed suffixes) pairs. infra/launchagents/ is scoped to
# plist+wrapper(.sh) files ONLY, never the bare directory: 2 real Python
# utility scripts verified living in that SAME directory
# (chronic_failure_digest.py, add_repomap_sessionstart_hook.py) must NOT be
# swept in by a directory-only rule — panel: "infra/launchagents/**
# plist/wrapper NON-backend" is a qualified claim, not a blanket one.
ALLOWLIST_PREFIX_SUFFIX_PAIRS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("infra/launchagents", (".plist", ".sh")),
)

# No .gitmodules exists in this repo (verified 2026-07-17) — Sol's
# submodule concern is currently moot, and structurally safe if one is
# added later: a submodule path is just another string that must match an
# allowlist entry to be skipped, same as any other path. None of the
# entries above plausibly cover a submodule mount point.


def _normalize(path: str) -> str:
    """Strip whitespace + an optional leading './' + one layer of git's
    C-style quoting (added by `core.quotepath=true`, the default, whenever a
    path contains a byte that needs escaping — e.g. non-ASCII).

    Only the OUTER quote layer is stripped; the escaped bytes inside are
    left as-is. That is sufficient for prefix matching here because every
    entry in ALLOWLIST_INNOCENT_PREFIXES is a plain-ASCII leading path
    component, which git's quoting never mangles — only the specific
    special byte further into the filename gets escaped.
    """
    p = path.strip()
    if p.startswith("./"):
        p = p[2:]
    if len(p) >= 2 and p[0] == '"' and p[-1] == '"':
        p = p[1:-1]
    return p


def _innocent_reason(path: str) -> str | None:
    """Return the allowlist rule that PROVES `path` innocent, or None if it
    is not provably innocent (an "unknown" path — contributes to `full`).

    Returning the matched RULE (not just a bool) is what lets the loud skip
    banner name "the file AND the allowlist entry that approved it"
    (mandate point 5).
    """
    if path in NEVER_INNOCENT_EXACT_PATHS:
        return None
    basename = path.rsplit("/", 1)[-1]
    if basename in NEVER_INNOCENT_BASENAMES:
        return None
    if "/" not in path and path.endswith(".md"):
        return "root-level *.md"
    for prefix in ALLOWLIST_INNOCENT_PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            return f"{prefix}/**"
    for prefix, suffixes in ALLOWLIST_PREFIX_SUFFIX_PAIRS:
        if (path == prefix or path.startswith(prefix + "/")) and path.endswith(suffixes):
            return f"{prefix}/** ({'/'.join(suffixes)})"
    return None


def classify(files: Iterable[str]) -> tuple[str, list[str]]:
    """Pure decision function — the SSOT this whole module exists to expose.

    Returns (verdict, unknown) where:
      - verdict is VERDICT_FULL or VERDICT_SKIP.
      - unknown is the list of input entries that DROVE a full verdict, in
        input order:
          * [ERROR_SENTINEL] if the sentinel was present (fail-closed);
          * every entry NOT provably matched by the allowlist, if verdict
            is full (the "unknown -> full" inversion — see module
            docstring);
          * [] if verdict is skip-backend (every entry matched the
            allowlist, or the normalized input was empty).

    No I/O, no git, no filesystem access — everything this function needs
    is its argument, which is exactly what makes it trivially unit-testable
    (scripts/tests/test_prepush_classify.py imports and calls it directly).
    """
    normalized = [_normalize(f) for f in files]
    normalized = [f for f in normalized if f]  # drop blank lines

    if ERROR_SENTINEL in normalized:
        return VERDICT_FULL, [ERROR_SENTINEL]

    if not normalized:
        return VERDICT_SKIP, []

    unknown = [f for f in normalized if _innocent_reason(f) is None]
    if unknown:
        return VERDICT_FULL, unknown
    return VERDICT_SKIP, []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _read_input(argv: list[str]) -> list[str]:
    if argv:
        return list(argv)
    # `.read().splitlines()` (not `for line in sys.stdin`) so a completely
    # empty stdin cleanly yields [] rather than depending on iterator
    # semantics at EOF, and so a stream with no trailing newline still
    # yields its last entry.
    data = sys.stdin.read()
    return data.splitlines()


def _log_skip(innocent_files: list[str]) -> None:
    print(
        f"⏭️  backend suite SKIPPED (path-aware, allowlist v{ALLOWLIST_VERSION}): "
        f"{len(innocent_files)} changed file(s), ALL match the innocent allowlist:",
        file=sys.stderr,
    )
    for f in innocent_files[:20]:
        print(f"     {f}  <-  {_innocent_reason(f)}", file=sys.stderr)
    if len(innocent_files) > 20:
        print(f"     ... +{len(innocent_files) - 20} more", file=sys.stderr)
    print(
        "   Reminder: CI required checks (Backend Tests etc.) still run the "
        "FULL suite on the PR — this is a local early-warning gate only.",
        file=sys.stderr,
    )


def _log_full(unknown: list[str], total: int) -> None:
    if unknown == [ERROR_SENTINEL]:
        print(
            "🧭 path-aware: upstream diff computation reported an error "
            "(sentinel present) — fail-closed to FULL suite.",
            file=sys.stderr,
        )
        return
    shown = unknown[:20]
    more = f" (+{len(unknown) - 20} more)" if len(unknown) > 20 else ""
    print(
        f"🧭 path-aware (allowlist v{ALLOWLIST_VERSION}): {len(unknown)}/{total} changed "
        f"file(s) are NOT on the innocent allowlist — running FULL suite. "
        f"Not-allowlisted: {shown}{more}",
        file=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    try:
        files = _read_input(args)
    except Exception as exc:  # noqa: BLE001 - fail-closed on ANY read error
        print(
            f"⚠️  prepush_classify: could not read input ({exc}) — "
            "fail-closed to FULL suite.",
            file=sys.stderr,
        )
        print(VERDICT_FULL)
        return 0

    normalized = [f for f in (_normalize(x) for x in files) if f]
    verdict, unknown = classify(files)

    if verdict == VERDICT_SKIP:
        _log_skip(normalized)
    else:
        _log_full(unknown, len(normalized))

    print(verdict)
    return 0


if __name__ == "__main__":
    sys.exit(main())
