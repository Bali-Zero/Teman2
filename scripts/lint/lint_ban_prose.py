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

A VALUE IS REQUIRED, ALWAYS. Every predicate below needs a credential word AND
something assigned to it. `rotate(api_key)` and `see generate(access_key)` are
sentences an engineer legitimately writes; a blocking step that reddened them
would teach people to route around it, which is the only way a guard truly dies.
A null value is innocent for the same reason a stripping export is.

SCOPE — prose spans only, by construction rather than by heuristic:
  .py                         comments and every bare string literal (tokenize +
                              ast, so an attribute docstring is read too)
  .sh .yml .yaml              comments, quote- and escape-aware per line
  .ts .tsx .js .jsx .mjs      line and block comments
Markdown is NOT in scope, and that is a measurement rather than an oversight:
reading documents as prose produced 335 findings across 47 files, and reading
only their narrative — fences and indented blocks excluded — still produced 60
across 12, in plans and archives that have nothing to do with any ban. Documents
are a second concern and belong to a second PR.
A regex literal sitting in code is never read, which is precisely Rule 3 of the
spec: the literal is safe, the sentence quoting it is not.

A file whose suffix is NOT in that list is reported as OUT OF SCOPE and never as
scanned. The distinction is the whole of cicatrix #2/W84: a run that covered
none of the diff must not print a number that reads like coverage.

GRANDFATHER LIST, the same shape lint_claude_headless_model_pin.py uses: 16
files already carried such prose when this lint was written, across four apps
that have nothing to do with this lane. Curing them here would be a second
concern in one PR; leaving the lint advisory would be a guard that never fires.
So the debt is frozen FILE-level in infra/ban-prose/grandfathered.json and stays
visible. Two things still fail: a file outside the set gaining a violation, and
the list itself growing against the base ref — without that second check a PR
could add an offender and pardon it in the same diff.

KNOWN LIMITS, measured by an adversarial seat rather than guessed:
  - A homoglyph (Cyrillic а for Latin a) defeats every predicate. The author of
    a comment is not an adversary of their own comment, so this guard is built
    against honest description, not against someone smuggling a credential past
    themselves. Named here so the next reader does not mistake silence for
    coverage.
  - A credential word whose value is unquoted prose is only judged when that
    value carries a digit or runs long — otherwise "the password: never printed"
    would red, and that sentence must stay writable.

Exit codes: 0 clean, 1 guilt, 2 blind scan (a file that exists, is in scope and
could not be read — a lint that scanned nothing must never report "clean"),
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

PY_SUFFIX = ".py"
LINE_COMMENT_SUFFIXES = {".sh", ".yml", ".yaml"}
SLASH_COMMENT_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".mjs"}
ALL_PROSE_SUFFIXES = {PY_SUFFIX} | LINE_COMMENT_SUFFIXES | SLASH_COMMENT_SUFFIXES

# The words are listed here and the assignment shapes are composed below, on
# different lines on purpose: a single line carrying both a credential word and
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

_VALUE = r"(?P<value>\S+)"

# P1 — a constructor or call given a credential keyword argument WITH a value,
# whatever the callable is called. Catches the aliased-import route, which
# carries no vendor name at all.
_CONSTRUCTOR = re.compile(
    r"\b(?P<owner>\w+)\([ \t]*(?:" + _WORDS_RE + r")\b[ \t]*" + r"[=:][ \t]*" + _VALUE,
    re.IGNORECASE,
)

# P2 — a credential word given a value, adjacent as code writes it.
_ASSIGNED = re.compile(
    r"\b(?:" + _WORDS_RE + r")\b[ \t]*" + r"=[ \t]*" + _VALUE, re.IGNORECASE
)

# P3 — the same word QUOTED as a mapping key, which puts a quote between the
# name and the colon and so slips past P2. Any value counts: a quoted key is
# unambiguously code quoted inside prose.
_QUOTED_KEY = re.compile(
    r"['\"](?:" + _WORDS_RE + r")['\"][ \t]*" + r":[ \t]*" + _VALUE, re.IGNORECASE
)

# P4 — the bare mapping form, where neither side is quoted. Judged only when the
# value LOOKS like a credential rather than like the rest of a sentence, because
# this is the one predicate an ordinary English clause can reach.
_BARE_KEY = re.compile(
    r"\b(?:" + _WORDS_RE + r")\b[ \t]*" + r":[ \t]*" + _VALUE, re.IGNORECASE
)
_CREDENTIAL_LOOKING = re.compile(r"^(?=.*\d)[\w./+=-]{8,}$|^[\w./+=-]{16,}$")

# P5 — the vendor's environment variable given a value. Stripping it is allowed
# and must stay allowed: an empty string, a null, or a bare mention is innocent.
# No hole excuses this one: the name on the left IS the vendor spelling, which
# is the half of Rule 2 a placeholder cannot fix.
_ENV_NAME = "ANTHROPIC_API_KEY"
_ENV_ASSIGNED = re.compile(re.escape(_ENV_NAME) + r"[ \t]*" + r"=[ \t]*" + _VALUE)

PREDICATES = (
    ("constructor-keyword", _CONSTRUCTOR),
    ("assigned-value", _ASSIGNED),
    ("quoted-key", _QUOTED_KEY),
    ("bare-key", _BARE_KEY),
    ("env-assigned", _ENV_ASSIGNED),
)

# Spec Rule 2 sanctions ONE way to show the shape: a neutral owner and a value
# that is visibly a hole. Angle brackets and asterisk runs are holes; a run of
# dots is NOT, and that is measured rather than assumed — the first red of this
# whole scar was a keyword argument whose value was three dots, and Detect
# Secrets read it as a finding.
_HOLE = re.compile(r"""^(?:<[^>]*>|\*{3,})$""")

# A null is not a credential. It is what a stripping defence looks like, and
# what a schema writes for "absent" — both sentences must stay writable.
_NULLISH = re.compile(r"^(?:None|null|nil|undefined|NULL|NONE|)$")

# Punctuation a value picks up from the sentence around it, and the quotes that
# say "this is code" rather than "this is the next word of my sentence".
_TRAILING = ",);.}]:"


def _value_core(value: str) -> tuple[str, bool]:
    """(the value without its wrapping, whether it was quoted)."""
    core = value.rstrip(_TRAILING)
    quoted = len(core) >= 2 and core[0] in "'\"" and core[-1] == core[0]
    if quoted:
        core = core[1:-1]
    elif core[:1] in ("'", '"'):
        core, quoted = core[1:], True
    return core, quoted

# Rule 2's other half: "never the real vendor spelling". A hole excuses the
# VALUE, and it excuses neither an owner nor a value that names the vendor.
_VENDOR = re.compile(r"anthropic", re.IGNORECASE)

CURE = (
    "name the shape instead of writing it "
    '("the constructor taking a per-token credential"), or move the literal '
    "into the guilt corpus, where it is load-bearing"
)


def _exempt(name: str, match: re.Match[str]) -> bool:
    """True when this match is innocent: a null value, or the one neutral
    placeholder form Rule 2 allows."""
    groups = match.groupdict()
    raw = groups.get("value") or ""
    owner = groups.get("owner") or ""
    core, quoted = _value_core(raw)
    if _VENDOR.search(owner) or _VENDOR.search(core):
        # Rule 2 cannot be satisfied by a hole that still names the vendor.
        return False
    if _NULLISH.match(core):
        return True
    if name == "env-assigned":
        # The name on the left IS the vendor spelling. A hole excuses a value,
        # and Rule 2's other half — "never the real vendor spelling" — is the
        # part a placeholder cannot buy back. Only a strip is innocent here,
        # and a strip is already a null.
        return False
    if name == "bare-key" and not quoted and not _CREDENTIAL_LOOKING.match(core):
        # An unquoted value that reads like the next word of a sentence, not
        # like a credential — "the password: never printed" must stay writable.
        return True
    return bool(_HOLE.match(core))


def judge_prose(text: str) -> list[str]:
    """Return the names of every predicate this prose span trips."""
    return [
        name
        for name, rx in PREDICATES
        if any(not _exempt(name, m) for m in rx.finditer(text))
    ]


def _strip_code(line: str) -> str:
    """Return the comment part of a shell/YAML line, or "" if it has none.

    Quote- AND escape-aware: this repo's workflows are full of quoted regexes
    carrying a hash, and of shell lines carrying a backslash-escaped apostrophe
    that a naive quote toggle reads as an unterminated string (found by an
    adversarial seat, which checked against bash itself).
    """
    quote = ""
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and quote != "'":
            i += 2
            continue
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[i:]
        i += 1
    return ""


def _slash_comments(text: str) -> list[tuple[int, str]]:
    """Line and block comments in a C-family source file."""
    spans: list[tuple[int, str]] = []
    in_block = False
    for n, line in enumerate(text.splitlines(), start=1):
        if in_block:
            spans.append((n, line))
            if "*/" in line:
                in_block = False
            continue
        idx = line.find("//")
        block = line.find("/*")
        if block != -1 and (idx == -1 or block < idx):
            spans.append((n, line[block:]))
            if "*/" not in line[block + 2 :]:
                in_block = True
        elif idx != -1:
            spans.append((n, line[idx:]))
    return spans


def _python_prose(text: str) -> list[tuple[int, str]]:
    """Comments plus EVERY bare string literal — a module, class or function
    docstring, and equally the attribute docstring that `ast.get_docstring`
    cannot see because it only ever reads the first statement of a body."""
    spans: list[tuple[int, str]] = []
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type == tokenize.COMMENT:
            spans.append((tok.start[0], tok.string))
    for node in ast.walk(ast.parse(text)):
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Constant):
            continue
        if not isinstance(node.value.value, str):
            continue
        base = node.lineno
        for offset, line in enumerate(node.value.value.splitlines()):
            spans.append((base + offset, line))
    return spans


def prose_spans(path: Path, text: str) -> list[tuple[int, str]]:
    """Every (line_number, prose_text) this file carries."""
    if path.suffix == PY_SUFFIX:
        return _python_prose(text)
    if path.suffix in SLASH_COMMENT_SUFFIXES:
        return _slash_comments(text)
    return [
        (n, comment)
        for n, line in enumerate(text.splitlines(), start=1)
        if (comment := _strip_code(line))
    ]


def _windowed(spans: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Adjacent prose lines, joined. A credential word on one line and its value
    on the next is one sentence to a reader and two spans to a scanner; without
    this, splitting the line is all it takes to walk past every predicate."""
    pairs = []
    for (n, a), (m, b) in zip(spans, spans[1:]):
        if m == n + 1:
            # The comment markers go: a reader does not see them between the
            # word and its value, and neither should a predicate.
            pairs.append((n, f"{_unmark(a)} {_unmark(b)}"))
    return pairs


_MARKER = re.compile(r"^[ \t]*(?:#+|//+|/\*+|\*+)[ \t]*")


def _unmark(span: str) -> str:
    return _MARKER.sub("", span).strip()


SCANNED, OUT_OF_SCOPE, MISSING, UNREADABLE = "scanned", "out_of_scope", "missing", "bad"


def scan_file(path: Path) -> tuple[bool, list[dict]]:
    """(scanned, findings) — the shape every caller wants. See scan_status for
    the reason a file was not scanned."""
    status, findings = scan_status(path)
    return status == SCANNED, findings


def scan_status(path: Path) -> tuple[str, list[dict]]:
    if path.suffix not in ALL_PROSE_SUFFIXES:
        return OUT_OF_SCOPE, []
    if not path.is_file():
        # Deleted by this diff, most likely. A deletion cannot introduce prose.
        return MISSING, []
    try:
        text = path.read_text(encoding="utf-8")
        spans = prose_spans(path, text)
    except (OSError, UnicodeDecodeError, SyntaxError, tokenize.TokenError):
        return UNREADABLE, []
    seen: set[tuple[int, str]] = set()
    findings = []
    for n, span in spans + _windowed(spans):
        for name in judge_prose(span):
            if (n, name) in seen:
                continue
            seen.add((n, name))
            findings.append(
                {
                    "path": str(path),
                    "line": n,
                    "predicate": name,
                    "prose": span.strip()[:120],
                }
            )
    return SCANNED, findings


def load_grandfathered() -> set[str]:
    try:
        return set(json.loads(GRANDFATHER.read_text())["files"])
    except (OSError, ValueError, KeyError):
        # An absent or unreadable list pardons NOTHING. Failing open here would
        # make deleting one file the way to silence the lint.
        return set()


def grandfather_grew(base_ref: str) -> tuple[list[str], str]:
    """(names frozen in HEAD but not at the base ref, a note when the check
    could not run). The note exists because an anti-bypass that fails open in
    silence is indistinguishable from one that passed."""
    rel = GRANDFATHER.relative_to(REPO_ROOT).as_posix()
    ref_ok = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"{base_ref}^{{commit}}"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    if ref_ok.returncode != 0:
        return [], f"base ref {base_ref} does not resolve here"
    out = subprocess.run(
        ["git", "show", f"{base_ref}:{rel}"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    if out.returncode != 0:
        return [], f"{rel} does not exist at {base_ref} — growth unmeasurable"
    try:
        before = set(json.loads(out.stdout)["files"])
    except (ValueError, KeyError):
        return [], f"{rel} at {base_ref} did not parse — growth unmeasurable"
    return sorted(load_grandfathered() - before), ""


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
        grew, note = grandfather_grew(args.base_ref)
        if grew:
            print(
                "::error::lint_ban_prose: the grandfather list GREW by "
                f"{len(grew)} file(s) — a new offender cannot be pardoned in the "
                f"diff that adds it: {', '.join(grew)}",
                file=sys.stderr,
            )
            return 3
        if note:
            print(f"::warning::lint_ban_prose: growth check did not run — {note}")

    if not args.files:
        print("lint_ban_prose: no files given — nothing to scan.")
        return 0

    pardoned = load_grandfathered()
    counts = {SCANNED: 0, OUT_OF_SCOPE: 0, MISSING: 0, UNREADABLE: 0}
    unreadable: list[str] = []
    findings: list[dict] = []
    for name in args.files:
        status, found = scan_status(Path(name))
        counts[status] += 1
        if status == UNREADABLE:
            unreadable.append(name)
        rel = Path(name).as_posix()
        if rel in pardoned or rel.removeprefix("./") in pardoned:
            continue
        findings.extend(found)

    if args.json:
        print(json.dumps({"counts": counts, "findings": findings}, indent=2))

    if unreadable:
        print(
            "::warning::lint_ban_prose: could not read "
            f"{len(unreadable)} in-scope file(s): {', '.join(unreadable[:5])}"
        )
    if unreadable and counts[SCANNED] == 0:
        # Every in-scope file failed to read. THAT is the shape of "scanned
        # nothing and said clean" that cicatrix #2/W84 is made of. A deleted
        # file and an out-of-scope suffix are neither, and four Python files
        # already on main do not parse — blocking every push on them would be
        # this lane adopting someone else's defect.
        print(
            "::error::lint_ban_prose: every in-scope file was unreadable — "
            "refusing to report clean.",
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
    print(
        f"OK: {counts[SCANNED]} file(s) scanned "
        f"({counts[OUT_OF_SCOPE]} out of scope, {counts[MISSING]} not on disk), "
        "no prose spells a banned shape."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
