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
allowlist does not recognize runs the full suite.

ROUND-1 RED-TEAM HARDENING (2026-07-18, PR #2642, two independent seats —
Codex Sol xhigh on the diff + a live-execution tester with 33 adversarial
inputs, CONVERGED findings):

  MUST-FIX (both seats, load-bearing): the allowlist was EXTENSION-BLIND.
  `docs/**`/`research/**`/`.claude/{skills,rules,commands,agents}/**` were
  bare directory prefixes admitting ANY file underneath — `docs/a/b.sh`,
  `.claude/skills/x/run.sh`, `.claude/skills/x/deploy.py` all read as
  "skip-backend" on pathname alone. Verified LIVE (not hypothetical): this
  repo's docs/ tree has 7 real `.sh` files and 8 real `.py` files today;
  research/ has 14 real `.py` files. Fix: EVERY allowlist entry is now
  suffix-scoped through the single `ALLOWLIST_PREFIX_SUFFIX_PAIRS`
  mechanism — a path must match prefix AND end in an explicitly-listed
  extension. docs/research/.claude-content-dirs are scoped to `.md` ONLY
  (verified: 100% of files under .claude/{skills,rules,commands,agents}
  are already .md: 12/12, 7/7, 5/5, 15/15; docs/research are dominated by
  .md with the aforementioned executable outliers now correctly excluded).
  `infra/launchagents/**` keeps `.plist`/`.sh` as a DECLARED, deliberate
  choice (these launchd wrapper scripts never touch the pytest backend
  suite) — not an accident of a bare-prefix glob, the same suffix-scoped
  mechanism as everything else. There is no bare-prefix-only entry left
  anywhere in this module.

  HARDENING-1 (Sol, cheap): the diff-range computation hardcoded
  "origin/main" throughout, but the remote pre-push actually pushes to is
  `$1` (git's documented pre-push hook contract: $1=remote name, $2=remote
  URL) — pushing to any OTHER remote could silently diff against the wrong
  origin/main and under-count files. Fixed on the BASH side
  (`.husky/pre-push`): fail-closed to `full` if `$1 != origin`. This
  script has no visibility into the remote name (it only ever sees a file
  list) — noted here because it is the other half of the same finding.

  HARDENING-2 (tester, SSOT robustness — not reachable via the real git-diff
  caller today, but this module is a reusable pure function and its input
  contract should hold regardless of caller): `_normalize()` did not resolve
  or reject `..` path segments (`docs/../apps/backend-rag/x.md` would
  suffix-match `.md` and read as innocent despite escaping the allowlisted
  directory by traversal), and `_read_input()`'s argv branch did not split
  on embedded newlines the way stdin does (a single argv entry containing
  an embedded `\n` was treated as one opaque path instead of the multiple
  paths it actually encodes). Both fixed below + locked with tests.

  KNOWN LIMIT, documented not fixed (both seats agree: Low severity,
  screened by CI regardless — see "VETTORE PROFONDO" below): the classifier
  only ever sees path STRINGS from `git diff --name-only`, never the git
  diff MODE (file type / executable bit / symlink / gitlink). A symlink or
  chmod-executable file living under an allowlisted directory with an
  allowlisted extension (e.g. an executable `docs/build.md` — contrived,
  but not impossible) would still read as innocent on pathname alone.
  Properly closing this requires enriching the hook's input contract with
  `git diff --raw` (or `--name-status` + a mode probe) instead of plain
  `--name-only`, which is a bigger architectural change than this finding's
  severity warrants (the required CI suite runs in full on every PR
  regardless — worst case here is "CI catches it a few minutes later", never
  "backend ships untested on main"). Tracked in
  `.claude/skills/modus/PENDING-ARMS.md`, owner = orchestrator session,
  non-blocking.

CONTRACT
--------
Input:  a list of repo-relative file paths, one per line, via:
          - argv (positional args) when any are given — convenience for
            tests/manual invocation, e.g. `prepush_classify.py foo.py bar.py`.
            Each argv entry is ALSO split on embedded `\n` (HARDENING-2),
            so argv and stdin modes have the identical splitting contract.
          - stdin (newline-separated) otherwise — the hook's real usage,
            piping the unioned `git diff --no-renames --name-only` output
            straight through.
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
- ERROR_SENTINEL present anywhere in the input -> "full".
- Empty input (zero non-blank lines, no sentinel) -> "skip-backend",
  LOGGED. This is the legitimate delete-only-push case.
- A path containing a `..` segment -> never innocent (HARDENING-2).
- A path containing an embedded `\n`/`\r` (a caller contract violation,
  belt-and-suspenders even though `_read_input` now prevents it from ever
  reaching here in the real CLI path) -> never innocent (HARDENING-2).
- Any file NOT provably matched by the allowlist -> contributes to "full".
- Any exception while reading/decoding stdin -> caught in `main()`,
  logged to stderr, verdict forced to "full" (fail-closed), exit 0.

RENAME SAFETY (verified empirically 2026-07-17)
--------------------------------------------------------------------
`git diff --name-only` (WITHOUT `--no-renames`) collapses a detected
rename to a SINGLE line — the DESTINATION path only, hiding the source. Fix
lives on the BASH side: every `git diff` invocation in `.husky/pre-push`
uses `--no-renames`, so a rename is always delete+add (both paths visible).

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

# Bump whenever ALLOWLIST_PREFIX_SUFFIX_PAIRS / NEVER_INNOCENT_* change, so a
# skip-banner log line ("allowlist vN") is attributable to a specific
# version of the rules that approved it (mandate point 5: "elenca i file E
# la allowlist-version che li ha approvati").
# v2 (2026-07-18): round-1 red-team hardening on PR #2642 — collapsed the
# old bare-prefix ALLOWLIST_INNOCENT_PREFIXES into the suffix-scoped
# ALLOWLIST_PREFIX_SUFFIX_PAIRS mechanism (MUST-FIX: extension-blindness),
# added `..`-traversal + embedded-newline rejection (HARDENING-2).
ALLOWLIST_VERSION = 2

# ---------------------------------------------------------------------------
# NEVER_INNOCENT_EXACT_PATHS — checked FIRST, unconditionally, before any
# allowlist matching. Belt-and-suspenders self-paranoia (mandate, explicit):
# these three MUST always force `full` even if a future edit accidentally
# broadens an allowlist entry to swallow one of them.
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
# ovunque". Redundant with the (suffix-scoped) allowlist below in the
# common case — kept as an explicit, directory-independent net.
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
# ALLOWLIST_PREFIX_SUFFIX_PAIRS — the ONE, UNIFORM allowlist mechanism.
# Every entry is (dir-prefix, allowed-suffixes) — a path is innocent ONLY if
# it matches the prefix AND ends in one of the listed suffixes. There is NO
# bare-prefix-only entry anywhere in this module (round-1 MUST-FIX: v1 had
# one — `ALLOWLIST_INNOCENT_PREFIXES` — and it is exactly what let
# `docs/a/b.sh` / `.claude/skills/x/run.sh` / `.claude/skills/x/deploy.py`
# read as innocent on pathname alone).
#
# Every entry re-verified against the actual repo tree 2026-07-18 (never
# assumed — "verify against actual data, never presume", CLAUDE.md golden
# rule #9 — this is the SECOND verification pass: the first one, 2026-07-17,
# only checked directory *purpose*, not actual file extensions, which is
# exactly the gap round-1 red-team caught):
#
#   docs/**               940 .md but ALSO 8 .py + 7 .sh among the
#                         outliers today -> scoped to `.md` ONLY.
#   research/**           602 .md but ALSO 14 .py among the outliers
#                         today -> scoped to `.md` ONLY.
#   .claude/skills/**     12/12 files are .md -> scoped to `.md`.
#   .claude/rules/**       7/7 files are .md -> scoped to `.md`.
#   .claude/commands/**    5/5 files are .md -> scoped to `.md`.
#   .claude/agents/**     15/15 files are .md -> scoped to `.md`.
#   infra/launchagents/**  DECLARED choice (not a glob accident): scoped to
#                         `.plist` (LaunchAgent config) + `.sh` (wrapper
#                         scripts) ONLY — neither format is ever imported by
#                         or executed as part of the backend/tests/ pytest
#                         suite; both are launchd-consumed config/shell, not
#                         Python. The 2 real .py utility scripts verified
#                         living in this SAME directory
#                         (chronic_failure_digest.py,
#                         add_repomap_sessionstart_hook.py) are correctly
#                         EXCLUDED by this suffix scoping — they are not on
#                         the allowed-suffix list, so they fall to
#                         "unknown -> full" like any other .py change would.
#
# Deliberately NOT `.claude/**` wholesale: `.claude/hooks/` (control-plane —
# contains codex-spalla-trigger.sh, verified on disk), `.claude/scripts/`,
# `.claude/settings.json` + `.claude/settings.local.json` (+ .bak-*
# variants), `.claude/worktrees/`, `.claude/worktrees-week0/` are none of
# them content-only, so none are allowlisted at all — not even
# suffix-scoped — they fall to "unknown -> full" like everything else not
# listed here.
#
# `memory/**` (from the panel's original example list) remains omitted: it
# does not exist as a repo-tracked path (verified). `.gitmodules` does not
# exist either — Sol's submodule concern is currently moot; structurally
# safe if one is added later, since a submodule path is just another string
# that must match an allowlist entry (prefix AND suffix) to be skipped.
# ---------------------------------------------------------------------------
ALLOWLIST_PREFIX_SUFFIX_PAIRS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("docs", (".md",)),
    ("research", (".md",)),
    (".claude/skills", (".md",)),
    (".claude/rules", (".md",)),
    (".claude/commands", (".md",)),
    (".claude/agents", (".md",)),
    ("infra/launchagents", (".plist", ".sh")),
)


def _normalize(path: str) -> str:
    """Strip whitespace + an optional leading './' + one layer of git's
    C-style quoting (added by `core.quotepath=true`, the default, whenever a
    path contains a byte that needs escaping — e.g. non-ASCII).

    Only the OUTER quote layer is stripped; the escaped bytes inside are
    left as-is. That is sufficient for prefix matching here because every
    entry in ALLOWLIST_PREFIX_SUFFIX_PAIRS is a plain-ASCII leading path
    component, which git's quoting never mangles — only the specific
    special byte further into the filename gets escaped.

    Does NOT resolve `..` segments or reject embedded newlines — those are
    deliberately checked downstream in `_innocent_reason()`, where "found a
    dangerous shape" and "therefore not innocent" live next to each other
    (HARDENING-2, round-1 red-team) rather than being silently rewritten
    here (rewriting a `..` away would be guessing at a resolution this
    module has no cwd/filesystem context to perform safely).
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

    # HARDENING-2 (round-1 red-team, tester): an embedded newline/carriage
    # return means this single list entry actually encodes MULTIPLE lines —
    # a caller contract violation. `_read_input()` now splits both argv and
    # stdin on `\n` before anything reaches `classify()`/`_innocent_reason()`
    # (so this should never fire via the real CLI path), but `classify()` is
    # a public, reusable SSOT function; a caller that bypasses
    # `_read_input()` and hands it a pre-split list still gets the safe
    # default if one entry is malformed. Checked BEFORE the `..`-segment
    # check below since `"\n" in path` must short-circuit prior to any
    # `.split("/")` reasoning about segments.
    if "\n" in path or "\r" in path:
        return None

    # HARDENING-2 (round-1 red-team, tester): a path-traversal segment can
    # make a suffix-matched path escape its allowlisted directory entirely
    # (`docs/../apps/backend-rag/x.md` ends in `.md` and starts with
    # `docs/` as a STRING, but does not actually resolve to anywhere under
    # docs/). Reject outright rather than attempt to resolve it — this
    # module has no filesystem/cwd context to resolve against safely, and
    # guessing would be exactly the kind of cleverness cicatrix-superscar.md
    # #3 punishes.
    if ".." in path.split("/"):
        return None

    basename = path.rsplit("/", 1)[-1]
    if basename in NEVER_INNOCENT_BASENAMES:
        return None
    if "/" not in path and path.endswith(".md"):
        return "root-level *.md"
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
        # HARDENING-2 (round-1 red-team, tester): stdin mode already splits
        # on every newline via `.splitlines()`; argv mode used to treat each
        # positional arg as exactly one path, so a single arg containing an
        # embedded `\n` was smuggled through as one opaque, unmatchable
        # blob instead of the multiple paths it actually encodes. Split
        # every argv entry the same way, so both entry points share one
        # splitting contract (the module IS the SSOT — its two call shapes
        # must not silently disagree).
        result: list[str] = []
        for a in argv:
            result.extend(a.split("\n"))
        return result
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
