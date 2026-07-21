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
     `/*`, `*`, or `<!--`. This covers full-line comments AND the interior
     of block comments (whose lines conventionally start with `*`). Known
     limit, documented not fixed: a block-comment continuation line NOT
     starting with `*` is judged as code. Tracking true comment state would
     require the whole file, and this gate only ever sees added lines.
  2. Token-source paths — files under `packages/core/tokens/` or
     `apps/mouth/src/styles/`, and any file whose basename matches
     `tokens*.css` or `*.tokens.*`. Hexes LIVE there by design (that is the
     SSOT the gate protects).
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

CONTRACT
--------
Input (two modes, mutually exclusive):
  --base REF      Compute the changed-file list via
                  `git diff --name-only REF...HEAD` and the added lines via
                  `git diff --unified=0 --no-color REF...HEAD`, run with
                  cwd = the repo root derived from this file's location (the
                  script is immune to the caller's cwd). Default git rename
                  detection is DELIBERATE: a pure rename produces no hunks,
                  so a renamed file's untouched legacy hexes are not
                  re-flagged as "new".
  --stdin         Read a unified diff from stdin (git format), so tests and
                  manual checks never need git. REQUIRES --files.
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
import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

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
TOKEN_SOURCE_PREFIXES: tuple[str, ...] = (
    "packages/core/tokens/",
    "apps/mouth/src/styles/",
)
TOKEN_SOURCE_BASENAME_GLOBS: tuple[str, ...] = ("tokens*.css", "*.tokens.*")

# `#` + 3/4/6/8 hex digits, longest-first so `#aabbccdd` is ONE 8-digit match.
# Lookbehind excludes alphanumerics, a second `#` (markdown `## Heading`) and
# `&` (HTML entities like `&#039;`). Lookahead excludes a trailing
# alphanumeric, so 5/7-digit non-colors never match a shorter prefix.
HEX_RE = re.compile(
    r"(?<![0-9A-Za-z#&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![0-9A-Za-z])"
)

# Marker requires a colon AND a non-empty reason: `token-lint-ok: <reason>`.
OK_MARKER_RE = re.compile(r"token-lint-ok\s*:\s*\S+")

COMMENT_PREFIXES: tuple[str, ...] = ("//", "/*", "*", "<!--")

VIOLATION_MESSAGE = (
    "hardcoded color in redesigned surface; use a semantic token from "
    "packages/core (see PLAN §WS1)"
)

EXIT_CLEAN = 0
EXIT_VIOLATIONS = 1
EXIT_ERROR = 2


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
class Violation:
    path: str
    line: int
    hex: str


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

    State machine: outside a hunk, only `+++ ` headers and well-formed `@@`
    hunk headers matter — everything else (`diff --git`, `index`, `---`,
    `new file mode`, `Binary files ...`, blank noise) is ignored, liberally.
    INSIDE a hunk the parser is STRICT: every line must start with `+`, `-`,
    ` `, or `\\` (the no-newline marker), and the body must consume exactly
    the line counts the header declared. The hunk-count tracking (not a
    naive startswith) is what keeps an added line that literally begins with
    `++` from being mistaken for a `+++` file header, and vice versa.

    Raises DiffParseError on: a hunk header that does not parse, a hunk
    header before any `+++` file header, a hunk-body line with an unknown
    sigil, or a hunk body that overruns its declared counts. All of these
    mean "the scanner cannot trust what it saw" -> caller fails closed.
    """
    added: list[AddedLine] = []
    current_path: str | None = None
    have_file_header = False
    in_hunk = False
    remaining_old = 0
    remaining_new = 0
    new_lineno = 0

    for raw in text.splitlines():
        if not in_hunk:
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
            if current_path is not None:
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

    return added


def is_scoped(path: str) -> bool:
    """True iff `path` lives inside one of the redesigned route groups."""
    return any(path.startswith(prefix) for prefix in SCOPED_PREFIXES)


def is_token_source(path: str) -> bool:
    """True iff `path` is a place where hexes are the SSOT, not a violation."""
    if any(path.startswith(prefix) for prefix in TOKEN_SOURCE_PREFIXES):
        return True
    basename = path.rsplit("/", 1)[-1]
    return any(
        fnmatch.fnmatchcase(basename, glob) for glob in TOKEN_SOURCE_BASENAME_GLOBS
    )


def is_comment_line(content: str) -> bool:
    """True iff the (added) line is a full-line comment or a block-comment
    interior line (left-trimmed content starts with //, /*, *, or <!--)."""
    stripped = content.lstrip()
    return stripped.startswith(COMMENT_PREFIXES)


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


def scan(diff_text: str, files: Iterable[str] | None) -> ScanResult:
    """The gate itself — pure.

    Judges every added line in `diff_text` that is attributed to a path in
    `files` (None = judge every path the diff names), inside the scoped
    route groups, outside token sources, and not exempted at line level.
    """
    allowed = None if files is None else {_normalize_path(f) for f in files if f.strip()}
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
        if is_comment_line(added.content):
            continue
        if has_ok_marker(added.content):
            continue
        for hex_value in find_hexes(added.content):
            violations.append(Violation(path, added.line, hex_value))
    return ScanResult(violations, len(scanned_files))


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

    names = run(["diff", "--name-only", f"{base}...HEAD"]).splitlines()
    text = run(["diff", "--unified=0", "--no-color", f"{base}...HEAD"])
    return names, text


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


def _emit_human(result: ScanResult) -> None:
    for violation in result.violations:
        print(
            f"{violation.path}:{violation.line}: {violation.hex} — "
            f"{VIOLATION_MESSAGE}"
        )
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
                "message": f"{v.path}:{v.line}: {v.hex} — {VIOLATION_MESSAGE}",
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
        result = scan(diff_text, files)
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
