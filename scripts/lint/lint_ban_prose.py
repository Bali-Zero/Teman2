#!/usr/bin/env python3
"""lint_ban_prose.py — prose about a banned pattern must not contain the pattern.

WHY THIS EXISTS, as the scar and not as a feature.

PR #6935 suspended under the Builder Contract's three-reds rule. Not one of the
four reds was the lint it shipped: every one was a COMMENT or a DOCSTRING that,
in order to explain a forbidden shape, wrote the shape out. Four independent
guards fired in turn — catE's counter, Detect Secrets' keyword rule, the
PreToolUse hook, the repo-wide baseline budget — and each time the author
reworded the caught line and authored a fresh one somewhere else, because the
rule being broken had never been written down.

It is written down now, and this file is its enforcement:

    In this repository, prose about a banned pattern must never contain the
    pattern. Not in a docstring, not in a comment.

THE ASYMMETRY THAT MAKES THIS NON-OBVIOUS, and the reason a scanner cannot be
asked to be cleverer instead: a regex that hunts a shape does not match itself,
so the CODE doing the hunting is always clean. The comment explaining that code
is not. Every guard in this repo scans text without distinguishing description
from use, and they are right not to try — a scanner that guessed intent would be
the over-match it exists to prevent (cicatrix #3).

SCOPE — prose spans only, by construction rather than by heuristic:
  .py            comments (tokenize) and docstrings (ast)
  .sh .yml .yaml shell/YAML comments, quote-aware per line
A regex literal sitting in code is never read by this lint, which is precisely
Rule 3 of the spec: the literal is safe, the sentence quoting it is not.

GUILT+INNOCENCE, never guilt alone (cicatrix #3): the corpus lives in
scripts/tests/test_lint_ban_prose.py, where fake credentials belong. The
innocence half names the shapes that MUST NOT trip — chief among them the
sanctioned OAuth keyword argument, which shares a suffix with a credential word
and would be the first casualty of a lazier pattern.

GRANDFATHER LIST, the same shape lint_claude_headless_model_pin.py uses: 16
files already carried such prose when this lint was written, across four apps
that have nothing to do with this lane. Curing them here would be a second
concern in one PR; leaving the lint advisory would be a guard that never fires.
So the debt is frozen FILE-level in infra/ban-prose/grandfathered.json and stays
visible. Two things still fail: a file outside the set gaining a violation, and
the list itself growing against the base ref — without that second check a PR
could add an offender and pardon it in the same diff.

Exit codes: 0 clean, 1 guilt, 2 blind scan (files requested, none scanned —
a lint that scanned nothing must never report "clean", cicatrix #2/W84),
3 the grandfather list grew.
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import re
import subprocess
import sys
import tokenize
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GRANDFATHER = REPO_ROOT / "infra" / "ban-prose" / "grandfathered.json"

PROSE_SUFFIXES = {".py", ".sh", ".yml", ".yaml"}

# The words are listed here and the assignment shape is composed below, on a
# different line on purpose: a single line carrying both a credential word and
# an adjacent assignment IS the shape this lint bans, and this file is not
# exempt from its own rule.
_CREDENTIAL_WORDS = (
    "api_key",
    "apikey",
    "api-key",
    "secret_key",
    "access_key",
    "private_key",
    "password",
)
_WORDS_RE = "|".join(re.escape(w) for w in _CREDENTIAL_WORDS)

# The deliberately ABSENT word is the OAuth one. It is the sanctioned path, it
# ends in the same four letters as a credential word, and a pattern built on
# that suffix would condemn the very route CLAUDE.md §3 points people to.

# P1 — a constructor taking a credential keyword argument, whatever the class is
# called. Catches the aliased-import route, which carries no vendor name at all.
_CONSTRUCTOR = re.compile(
    r"\b(?P<owner>\w+)\(\s*(?:" + _WORDS_RE + r")\b[ \t]*"
    + r"(?:=[ \t]*(?P<value>\S+))?",
    re.IGNORECASE,
)

# P2 — a credential word given a value, adjacent as code writes it.
_ASSIGNED = re.compile(
    r"\b(?:" + _WORDS_RE + r")\b[ \t]*" + r"=[ \t]*(?P<value>\S+)", re.IGNORECASE
)

# P3 — the same word quoted as a mapping key, which puts a quote between the
# name and the colon and so slips past P2.
_QUOTED_KEY = re.compile(
    r"['\"](?:" + _WORDS_RE + r")['\"][ \t]*" + r":[ \t]*(?P<value>\S+)",
    re.IGNORECASE,
)

# Spec Rule 2 sanctions ONE way to show the shape: a neutral owner and a value
# that is visibly a hole. Angle brackets and asterisk runs are holes; a run of
# dots is NOT, and that is measured rather than assumed — the first red of this
# whole scar was a keyword argument whose value was three dots, and Detect
# Secrets read it as a finding.
_HOLE = re.compile(r"^['\"]?(?:<[^>]*>|\*{3,})['\"]?[,);]*$")

# Rule 2's other half: "never the real vendor spelling". A hole excuses the
# VALUE, never an owner that names the vendor outright.
_VENDOR_OWNER = re.compile(r"anthropic", re.IGNORECASE)


def _exempt(match: re.Match[str]) -> bool:
    """True when this match is the one form Rule 2 allows: neutral owner, hole."""
    groups = match.groupdict()
    value = groups.get("value")
    if not value or not _HOLE.match(value):
        return False
    owner = groups.get("owner")
    return not (owner and _VENDOR_OWNER.search(owner))

# P4 — the vendor's environment variable given a value. Stripping it is allowed
# and must stay allowed: an empty string, a null, or a bare mention is innocent.
_ENV_NAME = "ANTHROPIC_API_KEY"
# No hole excuses this one: the name on the left IS the vendor spelling, which
# is the half of Rule 2 a placeholder cannot fix. Stripping stays innocent —
# an empty string or a null is a defence, not a use.
_ENV_ASSIGNED = re.compile(
    re.escape(_ENV_NAME) + r"[ \t]*" + r"=[ \t]*(?!\"\"|''|None\b|$)\S"
)

PREDICATES = (
    ("constructor-keyword", _CONSTRUCTOR),
    ("assigned-value", _ASSIGNED),
    ("quoted-key", _QUOTED_KEY),
    ("env-assigned", _ENV_ASSIGNED),
)

CURE = (
    "name the shape instead of writing it "
    "(\"the constructor taking a per-token credential\"), or move the literal "
    "into the guilt corpus, where it is load-bearing"
)


def judge_prose(text: str) -> list[str]:
    """Return the names of every predicate this prose span trips."""
    tripped = []
    for name, rx in PREDICATES:
        if any(not _exempt(m) for m in rx.finditer(text)):
            tripped.append(name)
    return tripped


def _strip_code(line: str) -> str:
    """Return the comment part of a shell/YAML line, or "" if it has none.

    Quote-aware so a hash inside a quoted regex — of which this repo's
    workflows have many — is never mistaken for the start of a comment.
    """
    quote = ""
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[i:]
    return ""


def prose_spans(path: Path, text: str) -> list[tuple[int, str]]:
    """Yield (line_number, prose_text) for every comment and docstring."""
    if path.suffix == ".py":
        return _python_prose(text)
    return [
        (n, comment)
        for n, line in enumerate(text.splitlines(), start=1)
        if (comment := _strip_code(line))
    ]


def _python_prose(text: str) -> list[tuple[int, str]]:
    spans: list[tuple[int, str]] = []
    readline = io.StringIO(text).readline
    for tok in tokenize.generate_tokens(readline):
        if tok.type == tokenize.COMMENT:
            spans.append((tok.start[0], tok.string))
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        doc = ast.get_docstring(node, clean=False)
        if doc is None:
            continue
        first = node.body[0]
        base = getattr(first, "lineno", 1)
        for offset, line in enumerate(doc.splitlines()):
            spans.append((base + offset, line))
    return spans


def scan_file(path: Path) -> tuple[bool, list[dict]]:
    """(scanned, findings). scanned is False when the file could not be read."""
    if path.suffix not in PROSE_SUFFIXES or not path.is_file():
        return False, []
    try:
        text = path.read_text(encoding="utf-8")
        spans = prose_spans(path, text)
    except (OSError, UnicodeDecodeError, SyntaxError, tokenize.TokenError):
        return False, []
    findings = [
        {"path": str(path), "line": n, "predicate": name, "prose": span.strip()[:120]}
        for n, span in spans
        for name in judge_prose(span)
    ]
    return True, findings


def load_grandfathered() -> set[str]:
    try:
        return set(json.loads(GRANDFATHER.read_text())["files"])
    except (OSError, ValueError, KeyError):
        # An absent or unreadable list pardons NOTHING. Failing open here would
        # make deleting one file the way to silence the lint.
        return set()


def grandfather_grew(base_ref: str) -> list[str]:
    """Names frozen in HEAD's list but absent from the base ref's. Empty when
    the base ref cannot be read — the growth check is an anti-bypass, and a
    shallow checkout must not be reported as guilt."""
    rel = GRANDFATHER.relative_to(REPO_ROOT).as_posix()
    try:
        out = subprocess.run(
            ["git", "show", f"{base_ref}:{rel}"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )
        if out.returncode != 0:
            return []
        before = set(json.loads(out.stdout)["files"])
    except (OSError, ValueError, KeyError):
        return []
    return sorted(load_grandfathered() - before)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", help="files to scan (changed set)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--base-ref",
        default="",
        help="ref to compare the grandfather list against (anti-bypass)",
    )
    args = parser.parse_args(argv)

    if args.base_ref:
        grew = grandfather_grew(args.base_ref)
        if grew:
            print(
                "::error::lint_ban_prose: the grandfather list GREW by "
                f"{len(grew)} file(s) — a new offender cannot be pardoned in the "
                f"diff that adds it: {', '.join(grew)}",
                file=sys.stderr,
            )
            return 3

    if not args.files:
        print("lint_ban_prose: no files given — nothing to scan.")
        return 0

    pardoned = load_grandfathered()
    scanned = 0
    findings: list[dict] = []
    for name in args.files:
        ok, found = scan_file(Path(name))
        scanned += 1 if ok else 0
        rel = Path(name).as_posix()
        if rel in pardoned or rel.lstrip("./") in pardoned:
            continue
        findings.extend(found)

    if args.json:
        print(json.dumps({"scanned": scanned, "findings": findings}, indent=2))
    if scanned == 0:
        # Files were named and not one of them was scannable. Reporting "clean"
        # here is the lie cicatrix #2 is made of.
        print(
            "::error::lint_ban_prose: 0 of "
            f"{len(args.files)} named files were scannable — refusing to report clean.",
            file=sys.stderr,
        )
        return 2
    if findings:
        if not args.json:
            for f in findings:
                print(
                    f"::error file={f['path']},line={f['line']}::"
                    f"prose spells a banned shape [{f['predicate']}]: {f['prose']}"
                )
            print(f"\nCure: {CURE}.", file=sys.stderr)
        return 1
    print(f"OK: {scanned} file(s) scanned, no prose spells a banned shape.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
