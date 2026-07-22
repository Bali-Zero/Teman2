#!/usr/bin/env python3
"""token_lint.py — CI gate: no NEW hardcoded brand hex colors in redesigned surfaces.

Mandate (WS1 token-SSOT, GARUDA OS car 2): WS1 established ONE token source of
truth in `packages/core` (semantic tokens like `--surface-*`, `--accent-funnel`,
`--fact-badge-*`). ~600 legacy hardcoded hexes exist repo-wide; this gate stops
NEW ones from entering the two route groups being redesigned. It deliberately
judges ONLY added lines in the PR diff — existing violations on untouched lines
are NOT flagged (a full-repo lint would wedge every PR behind a 600-item
cleanup that belongs to the redesign lanes, not to this gate).

Model / doctrine: this module follows the `scripts/prepush_classify.py`
pattern — a pure, importable, stdlib-only core (PyYAML is NOT guaranteed in
the gate environment) with guilt AND innocence tests at
`scripts/tests/test_token_lint.py` (cicatrix-superscar.md #3: "nessuna
guardia mergiata senza un test di innocenza E di colpevolezza"). The pure
core owns ZERO git/subprocess state — everything it judges comes in as
function arguments, which is what makes it fast to test and impossible to
fool with a crafted cwd.

SCOPE (verified against the actual repo tree 2026-07-19 — golden rule #9,
"verify against actual data, never presume"):
  - `apps/mouth/src/app/(workspace)/`  — EXISTS on disk -> encoded.
  - `apps/mouth/src/app/portal/`       — EXISTS on disk -> encoded.
  - `apps/mouth/src/app/(authenticated)/` — does NOT exist on disk ->
    deliberately NOT encoded. If this route group appears later, add its
    prefix to SCOPED_PREFIXES below (one line) and extend the tests.

EXEMPTIONS (each one has a dedicated innocence test):
  1. Comment lines — a line whose left-trimmed content starts with `//`,
     `/*`, `<!--`, or the JSX block shape `{/*` (round-6, k3 — the gate's
     main target is .tsx), plus block-comment CONTINUATION lines matching
     `^\\*\\s`
     (`*` + whitespace) that do NOT contain any of `{`, `:`, `;`
     (Tri-LLM hardening, PR #2987 round-2: a bare-`*` prefix test let the
     CSS universal selector `* { color: #fff; }` masquerade as a comment —
     a continuation line carrying CSS-rule characters is judged as code,
     even when it is a commented-out rule inside a real comment block;
     exemption 3's reasoned marker covers legitimate doc cases). Known
     limit, documented not fixed: a block-comment continuation line NOT
     starting with `* ` is judged as code. Tracking true comment state
     would require the whole file, and this gate only ever sees added lines.
     Round-3 refinement (codex RED, PR #2987): an opener CLOSED on the
     same line no longer exempts the WHOLE line — `/* legacy */ color:
     #fff;` is judged on the text after the closer (see
     `effective_code()`); only an opener with NO same-line closer still
     exempts the whole line (it swallows the rest of the line, and this
     gate only ever sees one line).
  2. Token-source paths — ONLY the two declared SSOT roots: (a) anything
     under `packages/core/tokens/`, (b) anything under
     `apps/mouth/src/styles/`, (c) nothing else. Hexes LIVE there by
     design (that is the SSOT the gate protects). Hardening history: the
     v1 rule matched BASENAMES (`tokens*.css`, `*.tokens.*` — a
     route-local `portal/tokens.css` got a free pass); the round-2 rule
     matched any `tokens/` path SEGMENT (a route-local
     `portal/tokens/component.tsx` still bypassed — codex RED on
     PR #2987). Both generic rules are gone: exemption is by SSOT
     LOCATION, never by name-shape.
  3. `token-lint-ok` marker — a line carrying `token-lint-ok:` followed by a
     NON-EMPTY reason (e.g. `// token-lint-ok: brand logo asset`). A bare
     `token-lint-ok` without colon+reason does NOT exempt — the reason is
     the audit trail, and requiring it is what keeps the marker honest.

WHAT IS FLAGGED: `#` followed by 3, 4, 6, or 8 hex digits, word-boundary
aware (longest-match first; `#d4845a00` matches once as 8 digits; `#fffff`
(5 digits) and `##ffffff` (markdown heading) do NOT match; HTML entities
like `&#039;` are excluded via the lookbehind). Deliberately simple per
spec: all matches are flagged, then the exemptions above apply. Rare false
positives (e.g. an SVG `url(#abc123)` gradient reference in a scoped file)
are handled by exemption 3 with its mandatory reason.

RELATION TO brand_token_lint.py (the OTHER color gate — do not drift)
----------------------------------------------------------------------
`scripts/brand_token_lint.py` (pre-existing, consumed by
`.github/workflows/p8-brand-api.yml`) guards GENERATED surfaces: the
brand-api build artifacts (`packages/design-system/brand-api/**`) and the
agent-authored tool modules (`apps/admin-dashboard/**/tools/**`). It scans
whole FILES on disk for any raw color literal (hex, rgb/hsl functions) —
its promise is "the generator never emits raw colors" (P8 FASE-5 gate G2).
THIS gate (`token_lint.py`) guards the human-edited REDESIGN surfaces —
the `(workspace)` + `portal` route groups — and judges only ADDED lines in
a PR diff (hex only, no rgb/hsl): its promise is "no NEW hardcoded brand
hex enters the redesigned routes" (WS1 token SSOT). Different surfaces,
different units of judgment (whole file vs diff-added lines), different
escape hatches (`brand-token-lint: allow` vs `token-lint-ok: <reason>`).
If you change one gate's scope, do NOT assume the other follows.

CONTRACT
--------
Input (two modes, mutually exclusive):
  --base REF      Compute the changed-file list via
                  `git diff --name-only REF...HEAD` and the added lines via
                  `git diff --unified=0 --no-color --text REF...HEAD`, run
                  with cwd = the repo root derived from this file's location
                  (the script is immune to the caller's cwd). Git rename
                  detection stays ON (DELIBERATE): a pure rename produces no
                  hunks, so an IN-SCOPE -> IN-SCOPE rename's untouched
                  legacy hexes are not re-flagged as "new". Round-5
                  refinement (codex RED P0): a rename whose DESTINATION is
                  in scope and whose SOURCE is not (cross-scope ingress) is
                  NOT invisible — the destination file's full HEAD content
                  is judged (`git show HEAD:<path>`), because that content
                  is new to the gate's scope even though no lines are
                  "added".
  --stdin         Read a unified diff from stdin (git format), so tests and
                  manual checks never need git. REQUIRES --files. A rename
                  INTO a scoped prefix cannot be content-verified in this
                  mode (no filesystem) — it is reported as a
                  `(rename-unverified)` violation (exit 1, fail-hostile).
  --files A,B,C   Comma-separated changed-file list (the `git diff
                  --name-only` contract). Only files in this list are
                  judged; added lines attributed by the diff to any other
                  path are ignored.

Output (stdout): one line per violation —
  `path:line: #hex — hardcoded color in redesigned surface; use a semantic
  token from packages/core (see PLAN §WS1)`
  then a one-line summary with the violation count. With --json, stdout
  instead carries a single JSON object
  {ok, violationCount, scannedFileCount, scopedPrefixes, violations[]}
  for CI annotation. All diagnostics about ERRORS go to stderr.

Exit code: 0 = clean (no violations). 1 = violations found. 2 = scanner
error (malformed diff input, git failure, bad CLI combination) — FAIL-CLOSED:
a gate that cannot see must block, never wave through.

Run:
    python3 scripts/token_lint.py --base origin/main
    git diff --unified=0 origin/main...HEAD | \\
        python3 scripts/token_lint.py --stdin --files "$(git diff --name-only origin/main...HEAD | paste -sd, -)"
    python3 -m pytest scripts/tests/test_token_lint.py -q
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

# ---------------------------------------------------------------------------
# Constants — see module docstring for the verification notes behind each.
# ---------------------------------------------------------------------------

# Scoped route groups. EXACTLY the prefixes verified to exist on disk
# (2026-07-19). `(authenticated)` was checked and does NOT exist — do not add
# prefixes speculatively; an over-broad scope would flag innocent surfaces,
# an over-narrow one would silently unguard a redesigned one.
SCOPED_PREFIXES: tuple[str, ...] = (
    "apps/mouth/src/app/(workspace)/",
    "apps/mouth/src/app/portal/",
)

# Token-source paths — where hexes are SUPPOSED to live (WS1 SSOT).
# Hardened 2026-07-19 (PR #2987 round-3, codex RED): ONLY these two SSOT
# roots exempt. The v1 basename globs (tokens*.css, *.tokens.*) and the
# round-2 generic `tokens/` path-segment rule were BOTH bypasses (a
# route-local portal/tokens/component.tsx slipped through round-2).
TOKEN_SOURCE_PREFIXES: tuple[str, ...] = (
    "packages/core/tokens/",
    "apps/mouth/src/styles/",
)

# `#` + 3/4/6/8 hex digits, longest-first so `#aabbccdd` is ONE 8-digit match.
# Lookbehind excludes alphanumerics, a second `#` (markdown `## Heading`) and
# `&` (HTML entities like `&#039;`). Lookahead excludes a trailing
# alphanumeric, so 5/7-digit non-colors never match a shorter prefix.
HEX_RE = re.compile(
    r"(?<![0-9A-Za-z#&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![0-9A-Za-z])"
)

# Marker requires a colon AND a non-empty reason: `token-lint-ok: <reason>`.
OK_MARKER_RE = re.compile(r"token-lint-ok\s*:\s*\S+")

COMMENT_PREFIXES: tuple[str, ...] = ("//", "/*", "<!--", "{/*")

# Block-comment continuation = `*` + whitespace (so `*/` and `* {` are NOT
# comments) AND no CSS-rule characters anywhere on the line (PR #2987
# round-2: the universal selector `* { color: ... }` must not read as a
# block-comment continuation).
BLOCK_COMMENT_CONT_RE = re.compile(r"^\*\s")
CSS_RULE_CHARS_RE = re.compile(r"[{:;]")

VIOLATION_MESSAGE = (
    "hardcoded color in redesigned surface; use a semantic token from "
    "packages/core (see PLAN §WS1)"
)

EXIT_CLEAN = 0
EXIT_VIOLATIONS = 1
EXIT_ERROR = 2

# Round-5 (codex RED P0): cross-scope rename ingress. In --stdin mode the
# destination content cannot be read (no filesystem), so a rename INTO a
# scoped prefix is reported with this marker as a violation (fail-hostile).
UNVERIFIED_RENAME_HEX = "(rename-unverified)"
UNVERIFIED_RENAME_NOTE = (
    "rename into scoped surface; full content not verifiable in --stdin "
    "mode — treated as violation (fail-hostile)"
)


class DiffParseError(Exception):
    """The unified-diff input is structurally malformed -> fail-closed exit 2."""


class GitError(Exception):
    """The --base git subprocess failed -> fail-closed exit 2."""


@dataclass(frozen=True)
class AddedLine:
    path: str
    line: int
    content: str  # the added line WITHOUT its leading '+'


@dataclass(frozen=True)
class Rename:
    """A `rename from`/`rename to` pair from the diff (paths normalized)."""

    old: str
    new: str


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    hex: str
    note: str | None = None  # audit context appended to the standard message


@dataclass(frozen=True)
class ScanResult:
    violations: list[Violation]
    scanned_file_count: int  # scoped, non-token-source files with >=1 added line judged


# ---------------------------------------------------------------------------
# Pure core — no I/O, no git, no filesystem. Everything below is a function
# of its arguments only (this is what makes the guilt+innocence doctrine
# testable, scripts/tests/test_token_lint.py imports these directly).
# ---------------------------------------------------------------------------

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _normalize_path(path: str) -> str:
    """Strip whitespace + an optional leading './' + one layer of git's
    C-style quoting (same normalization contract as prepush_classify)."""
    p = path.strip()
    if p.startswith("./"):
        p = p[2:]
    if len(p) >= 2 and p[0] == '"' and p[-1] == '"':
        p = p[1:-1]
    return p


def _git_lines(text: str) -> list[str]:
    """Split git output into lines on "\\n" ONLY (PR #2987 round-7, codex
    RED P0). `str.splitlines()` also splits on U+2028/U+2029 and other
    Unicode separators that git does NOT treat as line breaks — a single
    git record carrying a U+2028 before a payload would be mis-accounted as
    two lines: the hunk counts would consume the safe prefix and the
    payload suffix would land OUTSIDE the hunk (false clean). A trailing
    "\\r" is stripped per line for CRLF tolerance; Unicode separators are
    never split on. A trailing "\\n" is a terminator, not a line, so the
    final empty element is dropped."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def _file_header_path(line: str) -> str | None:
    """Extract the path from a `+++ ` header line. Returns None for
    `/dev/null` (deleted file — its hunks carry no added lines)."""
    rest = line[len("+++ ") :].split("\t", 1)[0].strip()
    if rest == "/dev/null":
        return None
    rest = _normalize_path(rest)
    if rest.startswith("b/"):
        rest = rest[len("b/") :]
    return rest


def parse_unified_diff(text: str) -> list[AddedLine]:
    """Parse a unified diff (git format) into the list of ADDED lines with
    their new-file line numbers. Stdlib-only, deterministic.

    State machine: outside a hunk, `diff --git` is a per-file STATE BOUNDARY
    (resets current_path / have_file_header — PR #2987 round-3, codex RED:
    without the reset, a malformed second file with hunks but no `+++`
    header INHERITED the previous file's path, so its added lines were
    attributed to the wrong, possibly out-of-scope, file and the gate could
    exit clean), `+++ ` headers and well-formed `@@` hunk headers matter —
    everything else (`index`, `---`, `new file mode`, `Binary files ...`,
    blank noise) is ignored, liberally. INSIDE a hunk the parser is STRICT:
    every line must start with `+`, `-`, ` `, or `\\` (the no-newline
    marker), and the body must consume exactly the line counts the header
    declared. The hunk-count tracking (not a naive startswith) is what
    keeps an added line that literally begins with `++` from being mistaken
    for a `+++` file header, and vice versa.

    Raises DiffParseError on: a hunk header that does not parse, a hunk
    header before any `+++` file header, an added line with no current file
    path (deleted files never carry additions), a hunk-body line with an
    unknown sigil, a hunk body that overruns its declared counts, a
    diff-content line outside any hunk, or EOF arriving before a hunk has
    consumed its declared counts (truncated diff — PR #2987 round-2). All
    of these mean "the scanner cannot trust what it saw" -> caller fails
    closed.
    """
    added: list[AddedLine] = []
    current_path: str | None = None
    have_file_header = False
    in_hunk = False
    remaining_old = 0
    remaining_new = 0
    new_lineno = 0

    for raw in _git_lines(text):
        if not in_hunk:
            if raw.startswith("diff --git "):
                # Per-file state boundary (PR #2987 round-3, codex RED):
                # without this reset a malformed second file (hunks but no
                # `+++` header) INHERITED the previous file's path — its
                # added lines could be attributed to the wrong (possibly
                # out-of-scope) file and the gate would exit clean.
                current_path = None
                have_file_header = False
                continue
            if raw.startswith("+++ "):
                current_path = _file_header_path(raw)
                have_file_header = True
                continue
            if raw.startswith("@@"):
                match = _HUNK_RE.match(raw)
                if match is None:
                    raise DiffParseError(f"malformed hunk header: {raw!r}")
                if not have_file_header:
                    raise DiffParseError(
                        f"hunk header before any +++ file header: {raw!r}"
                    )
                old_count = int(match.group(2)) if match.group(2) else 1
                new_count = int(match.group(4)) if match.group(4) else 1
                remaining_old = old_count
                remaining_new = new_count
                new_lineno = int(match.group(3))
                in_hunk = (old_count + new_count) > 0
                continue
            # Fail-closed: a diff-content line OUTSIDE any hunk means the
            # input is not trustworthy git-diff output (in real git output
            # `+`/`-` lines only ever occur inside hunks; `--- a/...` is the
            # old-file header and is ignored). Silently ignoring a stray
            # `+` line here would be fail-OPEN — a crafted diff could park
            # violations after a deliberately short hunk.
            if raw.startswith("+"):
                raise DiffParseError(f"added line outside any hunk: {raw!r}")
            if raw.startswith("-") and not raw.startswith("--- "):
                raise DiffParseError(f"removed line outside any hunk: {raw!r}")
            continue  # liberal: ignore anything else outside hunks

        # Inside a hunk body — strict sigil discipline.
        if raw.startswith("\\"):  # "\ No newline at end of file"
            continue
        if raw.startswith("+"):
            remaining_new -= 1
            if current_path is None:
                # `+++ /dev/null` (deleted file) never carries additions, so
                # a `+` line here means the file header was missing/garbled
                # (PR #2987 round-3) — fail closed rather than drop the line.
                raise DiffParseError(
                    "added line with no current file path (missing +++ header?)"
                )
            added.append(AddedLine(current_path, new_lineno, raw[1:]))
            new_lineno += 1
        elif raw.startswith("-"):
            remaining_old -= 1
        elif raw.startswith(" "):
            remaining_old -= 1
            remaining_new -= 1
            new_lineno += 1
        else:
            raise DiffParseError(
                f"hunk-body line without a valid sigil (+/-/space/\\\\): {raw!r}"
            )
        if remaining_old < 0 or remaining_new < 0:
            raise DiffParseError(
                f"hunk body overruns its declared counts near new-file line {new_lineno}"
            )
        if remaining_old == 0 and remaining_new == 0:
            in_hunk = False

    # Fail-closed (PR #2987 round-2): EOF with a hunk still open means the
    # diff was truncated mid-body — line numbers beyond this point are
    # unknowable, so the input cannot be trusted and must not exit clean.
    if in_hunk:
        raise DiffParseError(
            "EOF inside a hunk — declared line counts not consumed "
            "(truncated diff)"
        )

    return added


# `Binary files <a-side> and <b-side> differ` — emitted when git considers a
# file binary (e.g. a `.gitattributes -diff` rule). In --base mode `--text`
# prevents these; a marker reaching the parser means crafted/manual input.
BINARY_MARKER_RE = re.compile(r"^Binary files (.+) and (.+) differ$")


def binary_marked_paths(text: str) -> set[str]:
    """Paths (b-side, normalized) of files git reported as binary in this
    diff. Deleted binaries (b-side `/dev/null`) carry no content and are
    skipped. A `Binary files` line that does not parse cannot be attributed
    to any path -> DiffParseError (fail-closed: it MIGHT be scoped)."""
    paths: set[str] = set()
    for raw in _git_lines(text):
        if not raw.startswith("Binary files "):
            continue
        match = BINARY_MARKER_RE.match(raw)
        if match is None:
            raise DiffParseError(f"unparseable binary marker line: {raw!r}")
        b_side = _normalize_path(match.group(2))
        if b_side == "/dev/null":
            continue
        if b_side.startswith("b/"):
            b_side = b_side[len("b/") :]
        paths.add(b_side)
    return paths


def parse_renames(text: str) -> list[Rename]:
    """Extract `rename from`/`rename to` pairs from a git diff.

    Only COMPLETE pairs register (a `rename from` left dangling at the next
    `diff --git` boundary is dropped, liberally — an incomplete pair cannot
    hide content on its own: its destination still appears as a new file
    with full added-line hunks, which the normal scan judges). Similarity
    is irrelevant: ANY rename into scope brings unscanned content (round-5),
    so pairs are recorded regardless of the similarity index."""
    renames: list[Rename] = []
    pending_old: str | None = None
    for raw in _git_lines(text):
        if raw.startswith("diff --git "):
            pending_old = None
            continue
        if raw.startswith("rename from "):
            pending_old = _normalize_path(raw[len("rename from ") :])
            continue
        if raw.startswith("rename to ") and pending_old is not None:
            renames.append(
                Rename(pending_old, _normalize_path(raw[len("rename to ") :]))
            )
            pending_old = None
    return renames


def is_scoped(path: str) -> bool:
    """True iff `path` lives inside one of the redesigned route groups."""
    return any(path.startswith(prefix) for prefix in SCOPED_PREFIXES)


def is_token_source(path: str) -> bool:
    """True iff `path` lives under one of the two declared token-SSOT roots
    (TOKEN_SOURCE_PREFIXES) — nowhere else. No basename globs, no generic
    `tokens/` segment rule: both were bypasses (PR #2987 rounds 2-3, codex
    RED — a route-local `portal/tokens/component.tsx` slipped through the
    segment rule)."""
    return any(path.startswith(prefix) for prefix in TOKEN_SOURCE_PREFIXES)


def is_comment_line(content: str) -> bool:
    """True iff the (added) line is a full-line comment (`//`, `/*`, `<!--`)
    or a block-comment continuation line: `*` + whitespace AND no CSS-rule
    characters (`{`, `:`, `;`) on the line. The conjunction is what keeps
    the CSS universal selector `* { color: #fff; }` from bypassing the gate
    as a "comment" (PR #2987 round-2); the cost — a commented-out CSS rule
    like `* color: #fff;` inside a real comment block is now judged as code
    — is accepted and documented in the module docstring (exemption 1)."""
    stripped = content.lstrip()
    if stripped.startswith(COMMENT_PREFIXES):
        return True
    return (
        BLOCK_COMMENT_CONT_RE.match(stripped) is not None
        and CSS_RULE_CHARS_RE.search(stripped) is None
    )


# Inline comment opener/closer pairs for effective_code(): an opener that is
# CLOSED on the same line exempts only the comment part, not the whole line.
# `{/* ... */}` is the JSX block-comment shape (PR #2987 round-6, k3) — the
# gate's main target is .tsx; its closer INCLUDES the closing brace.
INLINE_COMMENT_PAIRS: tuple[tuple[str, str], ...] = (
    ("{/*", "*/}"),
    ("/*", "*/"),
    ("<!--", "-->"),
)


def effective_code(content: str) -> str:
    """The portion of an added line that is JUDGED for hexes (PR #2987
    rounds 3-4, codex RED).

    A line beginning with a comment opener (`/*`, `<!--`, or the JSX `{/*`)
    used to be exempt WHOLESALE — so `/* legacy */ color: #fff;` bypassed
    the gate:
    the opener made the entire line "a comment". Round-4 refinement: the
    strip LOOPS over chained leading closed comments — `/* first */
    /* second */ color: #d4845a;` strips BOTH comments and judges
    `color: #d4845a;` (the round-3 single-strip let the remainder start
    with `/*` again and re-exempt the whole line). Rules: when the
    matching closer (`*/` resp. `-->`) appears later on the SAME line,
    strip through it and repeat; when no closer appears on the same line,
    the whole line is a comment (unchanged — an unclosed opener swallows
    the rest of the line, and this gate only ever sees one line). Lines
    not starting with an opener are judged whole. Only LEADING comments
    are stripped: `/* a */ code /* b */ tail` judges `code /* b */ tail`.
    """
    remainder = content.lstrip()
    saw_comment = False
    while True:
        pair = next(
            (p for p in INLINE_COMMENT_PAIRS if remainder.startswith(p[0])),
            None,
        )
        if pair is None:
            return remainder if saw_comment else content
        opener, closer = pair
        idx = remainder.find(closer, len(opener))
        if idx == -1:
            return ""
        remainder = remainder[idx + len(closer) :].lstrip()
        saw_comment = True


def has_ok_marker(content: str) -> bool:
    """True iff the line carries `token-lint-ok:` + a non-empty reason."""
    return OK_MARKER_RE.search(content) is not None


def find_hexes(content: str) -> list[str]:
    """All hex-color matches on the line, first-occurrence order, deduped
    (a repeated identical hex on one line is ONE reported violation)."""
    seen: list[str] = []
    for match in HEX_RE.finditer(content):
        value = match.group(0)
        if value not in seen:
            seen.append(value)
    return seen


def scan(
    diff_text: str,
    files: Iterable[str] | None,
    *,
    read_head_file: Callable[[str], str] | None = None,
) -> ScanResult:
    """The gate itself — pure.

    Judges every added line in `diff_text` that is attributed to a path in
    `files` (None = judge every path the diff names), inside the scoped
    route groups, outside token sources, and not exempted at line level.
    Line-level judgment runs on `effective_code(content)` — the text after
    any same-line-closed leading comment (PR #2987 round-3).

    `read_head_file(path) -> str` reads a file's content at HEAD (--base
    mode wires it to `git show HEAD:<path>`). It exists ONLY for cross-scope
    rename ingress (round-5): a rename whose destination is in scope and
    whose source is not brings content that is new to the gate's regime yet
    produces no added-line hunks. With a reader, the destination's full
    content is judged line-by-line with the same exemptions. Without one
    (--stdin mode, no filesystem), the rename is reported as an
    UNVERIFIED_RENAME violation (fail-hostile).
    """
    allowed = None if files is None else {_normalize_path(f) for f in files if f.strip()}
    # Fail-closed (PR #2987 round-4, codex RED): a binary marker for a
    # SCOPED file means the diff carries no readable content for a surface
    # this gate must see (in --base mode `--text` prevents these; reaching
    # here means crafted/manual input). Never exit clean on a blind spot.
    for binary_path in sorted(binary_marked_paths(diff_text)):
        if allowed is not None and binary_path not in allowed:
            continue
        if is_scoped(binary_path):
            raise DiffParseError(
                f"binary-marked scoped file {binary_path!r}: the diff carries "
                "no readable content for it — fail-closed"
            )
    violations: list[Violation] = []
    scanned_files: set[str] = set()
    for added in parse_unified_diff(diff_text):
        path = added.path
        if allowed is not None and path not in allowed:
            continue
        if not is_scoped(path):
            continue
        if is_token_source(path):
            continue
        scanned_files.add(path)
        effective = effective_code(added.content)
        if not effective.strip():
            continue
        if is_comment_line(effective):
            continue
        if has_ok_marker(effective):
            continue
        for hex_value in find_hexes(effective):
            violations.append(Violation(path, added.line, hex_value))

    # Cross-scope rename ingress (PR #2987 round-5, codex RED P0): a pure
    # rename produces no added-line hunks, so a hex-filled file renamed
    # from OUTSIDE the scoped prefixes INTO them would be invisible to the
    # added-line scan above. IN-SCOPE -> IN-SCOPE pure renames stay
    # invisible BY DESIGN: their content was already inside the gate's
    # regime (legacy stays legacy) — only cross-scope ingress is judged.
    for ren in parse_renames(diff_text):
        if not is_scoped(ren.new) or is_scoped(ren.old):
            continue
        if allowed is not None and ren.new not in allowed:
            continue
        if read_head_file is None:
            violations.append(
                Violation(ren.new, 0, UNVERIFIED_RENAME_HEX, UNVERIFIED_RENAME_NOTE)
            )
            continue
        try:
            content = read_head_file(ren.new)
        except Exception as exc:  # noqa: BLE001 - any read failure fails closed
            raise DiffParseError(
                f"could not read HEAD content of renamed-into-scope file "
                f"{ren.new!r}: {exc}"
            ) from exc
        scanned_files.add(ren.new)
        for lineno, text_line in enumerate(_git_lines(content), start=1):
            effective = effective_code(text_line)
            if not effective.strip():
                continue
            if is_comment_line(effective):
                continue
            if has_ok_marker(effective):
                continue
            for hex_value in find_hexes(effective):
                violations.append(
                    Violation(
                        ren.new,
                        lineno,
                        hex_value,
                        f"rename into scope from {ren.old}",
                    )
                )

    # Dedupe exact (path, line, hex) triples — a sub-100% similarity rename
    # into scope can surface the same hex once via its added-line hunks and
    # once via the full-content ingress scan.
    seen: set[tuple[str, int, str]] = set()
    unique_violations: list[Violation] = []
    for violation in violations:
        key = (violation.path, violation.line, violation.hex)
        if key in seen:
            continue
        seen.add(key)
        unique_violations.append(violation)
    return ScanResult(unique_violations, len(scanned_files))


# ---------------------------------------------------------------------------
# CLI — the only place git/subprocess/stdin state exists.
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _git_diff(base: str) -> tuple[list[str], str]:
    """Return (changed-file list, unified=0 diff text) for REF...HEAD.

    Runs with cwd = repo root derived from this file's location, so the
    result does not depend on the caller's cwd. Any git failure raises
    GitError -> main() fails closed with exit 2.

    `--text` on the patch call is LOAD-BEARING (PR #2987 round-4, codex
    RED): without it, a `.gitattributes` rule marking scoped files as
    `-diff`/binary makes git emit only `Binary files ... differ` — no
    hunks, no additions, and hardcoded hex changes would pass clean. With
    `--text` git treats every file as text and emits real hunks. The
    parser-level binary-marker check in scan() is the belt-and-suspenders
    second layer for crafted/manual stdin that never went through --text.
    """

    def run(args: list[str]) -> str:
        proc = subprocess.run(
            ["git", *args],
            cwd=_repo_root(),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise GitError(
                f"git {' '.join(args)} failed (exit {proc.returncode}): "
                f"{proc.stderr.strip() or '<no stderr>'}"
            )
        return proc.stdout

    names = _git_lines(run(["diff", "--name-only", f"{base}...HEAD"]))
    text = run(["diff", "--unified=0", "--no-color", "--text", f"{base}...HEAD"])
    return names, text


def _read_head_file(path: str) -> str:
    """Read a file's content at HEAD via `git show HEAD:<path>` (--base mode
    only — backs the round-5 cross-scope rename ingress scan). Any failure
    raises GitError -> main() fails closed with exit 2."""
    proc = subprocess.run(
        ["git", "show", f"HEAD:{path}"],
        cwd=_repo_root(),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise GitError(
            f"git show HEAD:{path} failed (exit {proc.returncode}): "
            f"{proc.stderr.strip() or '<no stderr>'}"
        )
    return proc.stdout


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="token_lint.py",
        description=(
            "CI gate: block NEW hardcoded brand hex colors in the redesigned "
            "route groups (added lines only). Exits 0 clean, 1 violations, "
            "2 scanner error (fail-closed)."
        ),
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--base",
        metavar="REF",
        help="git ref to diff against as REF...HEAD (computes file list + added lines)",
    )
    source.add_argument(
        "--stdin",
        action="store_true",
        help="read a unified diff from stdin (requires --files)",
    )
    parser.add_argument(
        "--files",
        metavar="A,B,C",
        help="comma-separated changed-file list (the git diff --name-only contract)",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="emit a JSON report on stdout for CI annotation",
    )
    return parser


def _format_violation(violation: Violation) -> str:
    """The standard `path:line: #hex — ...` contract line, with the optional
    audit note appended in brackets (round-5 rename-ingress context)."""
    line = f"{violation.path}:{violation.line}: {violation.hex} — {VIOLATION_MESSAGE}"
    if violation.note:
        line += f" [{violation.note}]"
    return line


def _emit_human(result: ScanResult) -> None:
    for violation in result.violations:
        print(_format_violation(violation))
    if result.violations:
        file_count = len({v.path for v in result.violations})
        print(
            f"token-lint: {len(result.violations)} violation(s) in "
            f"{file_count} file(s) — new hardcoded hex colors are blocked in "
            "redesigned surfaces; use semantic tokens from packages/core (WS1)."
        )
    else:
        print(
            "token-lint: clean — no new hardcoded hex colors in scoped "
            f"surfaces ({result.scanned_file_count} scoped file(s) with added "
            "lines scanned)."
        )


def _emit_json(result: ScanResult) -> None:
    payload = {
        "ok": not result.violations,
        "violationCount": len(result.violations),
        "scannedFileCount": result.scanned_file_count,
        "scopedPrefixes": list(SCOPED_PREFIXES),
        "violations": [
            {
                "path": v.path,
                "line": v.line,
                "hex": v.hex,
                "message": _format_violation(v),
                **({"note": v.note} if v.note else {}),
            }
            for v in result.violations
        ],
    }
    print(json.dumps(payload, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)  # argparse usage errors exit 2 — fail-closed

    try:
        if args.base is not None:
            files, diff_text = _git_diff(args.base)
        else:
            if args.files is None:
                # parser.error() prints usage to stderr and exits 2.
                parser.error("--stdin requires --files A,B,C")
            files = [f.strip() for f in args.files.split(",") if f.strip()]
            diff_text = sys.stdin.read()
        result = scan(
            diff_text,
            files,
            read_head_file=_read_head_file if args.base is not None else None,
        )
    except DiffParseError as exc:
        print(
            f"token-lint: ERROR: could not parse diff input ({exc}) — "
            "fail-closed (exit 2).",
            file=sys.stderr,
        )
        return EXIT_ERROR
    except GitError as exc:
        print(
            f"token-lint: ERROR: {exc} — fail-closed (exit 2).",
            file=sys.stderr,
        )
        return EXIT_ERROR
    except Exception as exc:  # noqa: BLE001 - any scanner failure fails closed
        print(
            f"token-lint: ERROR: unexpected scanner failure ({exc!r}) — "
            "fail-closed (exit 2).",
            file=sys.stderr,
        )
        return EXIT_ERROR

    if args.as_json:
        _emit_json(result)
    else:
        _emit_human(result)
    return EXIT_VIOLATIONS if result.violations else EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
