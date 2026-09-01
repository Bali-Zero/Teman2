#!/usr/bin/env python3
"""consumer_map.py — enumerate live consumers of DELETED or RENAMED files.

MOTIVATION (2026-08-21, PR #4459): deleting `apps/backend-rag/tests/` (an
orphan tree) went CI-red TWICE because two consumers were invisible to a
search anchored on the deleted PATH:

  - `.github/workflows/sonarqube.yml` names the files as `tests/...` AFTER a
    `cd apps/backend-rag` step in the job — the string in the YAML never
    contains the deleted directory's path at all, only its suffix.
  - `apps/backend-rag/scripts/backend_stability_gate.py:41` lists
    `tests/test_migrations.py` inside a plain Python argument list — same
    shape: a string relative to a `cd`, not to repo root, that a required
    check later reads (`backend_stability_gate.py`'s own required-CI step).

A consumer search keyed on the deleted PATH is under-match by construction
(cicatrix-superscar.md #3 — the guard sees the FORM of a path, not the
ENTITY a reader actually types). This tool searches by BASENAME instead
(and, for `.py` modules, ALSO by the bare import-stem — `test_migrations`
for `test_migrations.py`, since a Python `import` never carries the
extension) — the string every one of the shapes above actually contains.

CONTRACT
--------
Input: either
  - `--base <ref>` (default `origin/main`) — every DELETED or RENAMED file
    between `git merge-base <ref> HEAD` and `HEAD` is a target. Rename
    detection is deliberately ON here (`git diff -M`) — the OPPOSITE of
    `.husky/pre-push`'s own path-aware gate, which forces `--no-renames` so
    BOTH the old and new path are visible to its allowlist classifier. This
    tool wants the old->new PAIR specifically (see RENAME SAFETY below), so
    it needs rename detection to get one.
  - explicit `paths...` (positional) — each treated as a DELETED target
    directly, bypassing git diff entirely (manual invocation / composition
    with another tool that already knows the deleted set). No rename pairing
    is available in this mode.

For each target, this tool:
  1. Skips it (with a SKIPPED-common-basename row) if its basename is a
     COMMON_BASENAME (conftest.py, __init__.py) and `--include-common` was
     not passed — nearly every hit on a name that common would be an
     unrelated file of the same name, not a real consumer.
  2. `git grep -n -F` (fixed-string, one call per basename/stem, never a
     Python tree-walk — this is what keeps the whole tool well under the
     10s budget) for the basename, and — for `.py` targets — again for the
     bare stem, against `HEAD` (the commit about to be pushed, not whatever
     the working tree happens to hold, so a dirty tree cannot hide or
     fabricate a finding).
  3. Drops a hit if: its path IS one of the deleted/renamed targets
     themselves (self-reference, not a consumer — "the deleted tree
     itself"); its path is excluded (see EXCLUSIONS below); OR — for a
     RENAME — the SAME LINE already contains the full NEW path (a consumer
     that has already been repointed is not a finding: RENAME SAFETY).
  4. Classifies every surviving hit by CONSUMER KIND (the file that mentions
     it, not the target) and by verdict: `.md` hits are `docs-mention`
     (reported, never a blocking finding — CLAUDE.md §15 research docs and
     README prose legitimately NAME files without executing them); every
     other kind is `LIVE`.

EXCLUSIONS (never scanned as consumers, regardless of kind)
  - `docs/archive/**`, `research/**` — historical/ad-hoc capture, not code.
  - `.secrets.baseline`, `infra/tcc-desktop-paths/allowlist.txt` — content
    hash/allowlist files that mention paths as DATA, never as references.
  - `*.jsonl` — append-only event/escalation logs; a basename appearing
    inside a historical JSON line is a record, not a live reference.

PROXY WARNING (declared, not hidden — cicatrix-superscar.md #3): basename
matching OVER-matches. Two different files sharing a common name will
collide; `git grep -F` also matches the basename as a plain substring, so a
longer name containing it as a fragment will show up too. This is
DELIBERATE and safe-by-construction for this tool's purpose: an over-match
costs a human 10 seconds reading one extra row in the printed table; an
UNDER-match (the actual #4459 defect) ships a red required check. Only the
COMMON_BASENAMES skip-list narrows the search, and only for names common
enough that scanning them would be pure noise.

PROSE-MENTION FILTER (2026-08-21, real-corpus replay finding — a SECOND
over-match, distinct from the common-basename one above): a REAL replay
against this repo's own `apps/backend-rag/tests/test_sentry_lazy_import.py`
found 3 of 20 "LIVE" hits that name the file only in PROSE, never consume
it — a `#` comment line, and two Python module docstrings, all three
narrating the exact incident this tool's own #4459 motivation section
describes. A guard that blocks a legitimate push on prose is the guard
getting disabled (cicatrix-superscar.md #3 / W105 — an over-match annoying
enough turns into a #2 "esiste ≠ armato" via the escape hatch). Two
independent filters, applied in this order, downgrade such a hit to
`docs-mention`:
  1. Any hit whose line, after `.lstrip()`, starts with `#` — a whole-line
     comment — in a kind where `#` is the comment marker (python, shell,
     workflow, docker-compose, makefile, husky, pyproject, pytest.ini,
     other). A TRAILING end-of-line comment does NOT qualify (the line
     does not start with `#`) — that shape still carries a real code
     statement earlier on the same line.
  2. For `.py` targets specifically: a hit whose line falls inside a
     DOCSTRING's line range (module/class/function/async-function, the
     first statement, an `Expr` wrapping a string `Constant`) — found via
     `ast.parse` + `ast.walk`, never a heuristic guess at where a
     docstring "probably" ends. An `import`/`from` of the stem, or a
     string literal OUTSIDE any docstring range (list/tuple/call
     args — the actual #4459 `backend_stability_gate.py` shape) is
     UNCHANGED by this filter and stays LIVE; that is the guilt tripwire
     this filter must never swallow (scripts/tests/test_consumer_map.py).
     If `ast.parse` fails (the file does not parse as Python — a template,
     a deliberately-broken fixture, a Python-2-only script), this tool
     fails CLOSED: the hit stays LIVE and a one-line note goes to stderr
     naming the file — silently skipping the filter would be silently
     TRUSTING an unreadable file's structure, which is backwards.

BARE-BASENAME FILTER (2026-09-02, ledger row 2026-08-31 SQUAD H — the class
PR #5373 named and deliberately left uncured): PR #5373 fixed 9 of 72 false
LIVE hits on the real scar-corpus move (#5331) — every consumer that spelled
the destination in path SEGMENTS instead of one literal string. Re-measured
on that same real move, the remaining findings are a different question, not
a smaller version of the same one: a BARE BASENAME with no directory at all,
used as DATA —

    CORPUS_FILES = ("cicatrix-scars.md", "cicatrix-scars-archive.md")
    "# cicatrix-scars-archive.md\n\n"          # a header string being written
    LEGACY = {"scars": "cicatrix-scars.md"}    # a mapping value
    git commit -m "chore: update cicatrix-scars.md"   # inside a shell script
    See cicatrix-scars.md for the incident.    # a line of prose

A line naming ONLY a basename names no location, so it cannot be pointing at
the OLD one either — treating it as a stale consumer is a category error.
Measured on the #5331 corpus: 73 LIVE hits before this filter, 24 after (49
downgraded). The remaining 24 split into two groups, both intentional and
neither a defect: the genuinely-stale literal-old-path mentions (e.g.
`LEGACY_FILE = "vendor/legacy/report.md"`), and hits this filter
declares out of scope on purpose — the "declared, NOT-cured residual"
paragraph below, plus a handful of `assert "basename" in x` / `x ==
"basename"` `Compare` shapes the per-kind precision below deliberately
leaves conservative rather than risk an under-match.

The test is the ENTITY question again (cicatrix-superscar.md #3): does this
line COMPOSE a path around the basename, or merely CONTAIN it? Composition
leaves a signature immediately to the LEFT of the basename occurrence (past
its own quote character and whitespace) — either a literal `/` (a pathlib
`/` operator, or the tail of a longer path string like
`"vendor/legacy/report.md"`) or an earlier `join(`/`joinpath(` call
on the same line. Absent both, the line is data, not a path.

Deliberately LINE-scoped, not file-scoped: a consumer that composes the path
from a directory constant defined on an EARLIER line (`SCARS_DIR = ... /
"docs" / "scars"` on one line, `SCARS_DIR / "cicatrix-scars.md"` on another)
still reads as directory-adjacent on ITS OWN line (the `/` operator is right
there) and stays LIVE — correctly, by the same logic that made PR #5373's
segment check line-scoped: a hit this filter cannot itself verify as
already-repointed must stay on the safe (over-match) side, never be waved
through. This is also this filter's declared, NOT-cured residual: when that
directory constant IS already correctly repointed, the hit is an over-match
this filter cannot resolve — a THIRD, distinct question ("does an
elsewhere-defined constant already point at the new path") that stays a
`data:location-dependent-consumer` risk this filter does not attempt, per
the same fix-of-a-fix discipline that kept this filter itself out of #5373.

GUILT CORPUS, THE OTHER RISK (the one this filter must NOT create): a real
consumer where directory context lives entirely off the hit's own line — the
existing `test_guilt_segments_OUT_OF_ORDER_do_not_count_as_a_repoint`
fixture assigns `NAME = "cicatrix-scars.md"` on one line and later opens
`".claude/rules/" + NAME` on another. `NAME`'s own line has no `/` at all,
and per-kind precision is what keeps this filter from swallowing it anyway:

  - **python**: the basename's immediate AST parent at that exact line must
    be a collection literal or a call argument (`Tuple`/`List`/`Dict`/
    `Set`/`Call`) — never a bare `Assign` RHS, which is exactly the
    "could be composed into a path via this name, elsewhere" shape and
    stays conservatively LIVE. Fails CLOSED (no downgrade attempted) when
    the file will not parse, same discipline as the docstring filter right
    below it, reusing the same cached AST.
  - **shell/workflow/husky/docker-compose/makefile/pyproject/pytest.ini/
    package.json/plist**: the occurrence must sit inside a QUOTED string
    (an odd count of `"` or `'` before it on the line) — `git commit -m
    "chore: update cicatrix-scars.md"` qualifies, `cat conftest.py` (a bare,
    unquoted command-line word — the tool's own pre-existing, intentional
    over-match example) does not, and is therefore left untouched.
  - **other** (the catch-all for prose/data formats with neither an AST nor
    a shell-quoting convention — `.txt`, `.yaml`, `.json`, `.sql`
    comments): directory-adjacency alone decides, no quote requirement —
    the real `docs/army-prompts/S15.txt` line this filter exists to catch
    has no quotes around it at all. Declared, un-mitigated residual risk
    this asymmetry accepts: an "other"-kind file with a genuine bare-word
    reference (e.g. a `.gitignore`-style exact-basename pattern) would be
    downgraded too — not observed in the measured corpus, and "other" was
    already this tool's least-precise bucket before this filter existed.

This filter ONLY applies when the search used the FULL basename (with its
extension) — never to a `.py` target's bare import-stem search (`import
test_migrations` never contains `test_migrations.py` at all, so it is not
"bare basename data", it is a real import naming a real dependency
regardless of directory context; running this filter against it would be a
straightforward under-match).

Exit codes: 0 = clean (no LIVE consumer found for any target). 1 = at least
one LIVE consumer found — this diff is not safe to push as-is. 2 = usage
error (not a git repo, bad `--base` ref, git itself unavailable).

Run:
    python3 scripts/consumer_map.py --base origin/main
    python3 scripts/consumer_map.py --base origin/main --include-common
    python3 scripts/consumer_map.py apps/backend-rag/tests/test_foo.py
"""
from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Basenames common enough that a bare-basename search is pure noise (every
# hit is an unrelated file of the same name, not a real consumer). Kept
# deliberately short and explicit — an entry here silently narrows the
# search, so it must be a name this repo has actually measured as noisy, not
# a defensive guess. `--include-common` forces the scan anyway.
# ---------------------------------------------------------------------------
COMMON_BASENAMES: frozenset[str] = frozenset(
    {
        "conftest.py",
        "__init__.py",
        # Next.js App Router convention filenames (2026-08-21, measured on
        # PR #4344): deleting apps/mouth/src/app/visa/voa/page.tsx flagged
        # 414 "LIVE" hits, every one of them an unrelated page.tsx in a
        # different route directory of a different app (kbli-navigator,
        # admin-dashboard, bali-zero-magazine, ...). Repo-wide counts at
        # the time of this fix: page.tsx=188, route.ts=113, layout.tsx=39
        # — same noise class as conftest.py/__init__.py, just framework
        # convention instead of test/package convention.
        "page.tsx",
        "route.ts",
        "layout.tsx",
    }
)

# Kinds where "#" is the comment marker — a hit whose line, after lstrip(),
# starts with "#" is a comment naming the file, not a consumer of it (module
# docstring "PROSE-MENTION FILTER" item 1). Excludes "package.json" (JSON has
# no comments — a leading "#" there is not valid JSON and would never be a
# real hit) and "plist" (XML, comments are `<!-- -->`). "docs-mention" is
# already handled upstream and never reaches this check.
HASH_COMMENT_KINDS: frozenset[str] = frozenset(
    {
        "python",
        "shell",
        "workflow",
        "docker-compose",
        "makefile",
        "husky",
        "pyproject",
        "pytest.ini",
        "other",
    }
)

# AST parent-node type names that mean "this string literal is a collection
# element or a call argument" — the BARE-BASENAME FILTER's python branch
# (module docstring). Deliberately excludes "Assign"/"AnnAssign"/"BinOp" —
# a bare `Assign` RHS could be composed into a real path on ANOTHER line
# (the filter's own guilt corpus), and a `/`-BinOp is already caught, same
# line, by `_line_has_directory_adjacent` before this ever runs.
DATA_CONTAINER_PARENT_KINDS: frozenset[str] = frozenset({"Tuple", "List", "Dict", "Set", "Call"})

# Kinds where the BARE-BASENAME FILTER (module docstring) requires the
# occurrence to sit inside a QUOTED string before downgrading — shell/config
# formats where a bare, UNQUOTED word is a command-line argument (a genuine,
# if imprecise, file reference: `cat conftest.py`) and must stay untouched,
# distinct from a quoted string's contents (`git commit -m "...basename..."`,
# safely DATA). "other" is deliberately excluded — see the module docstring.
QUOTE_REQUIRED_KINDS: frozenset[str] = frozenset(
    {
        "shell",
        "workflow",
        "husky",
        "docker-compose",
        "makefile",
        "pyproject",
        "pytest.ini",
        "package.json",
        "plist",
    }
)

EXCLUDE_DIR_PREFIXES: tuple[str, ...] = ("docs/archive/", "research/")
EXCLUDE_EXACT_PATHS: frozenset[str] = frozenset(
    {".secrets.baseline", "infra/tcc-desktop-paths/allowlist.txt"}
)
EXCLUDE_SUFFIXES: tuple[str, ...] = (".jsonl",)


def _is_excluded(path: str) -> bool:
    if path in EXCLUDE_EXACT_PATHS:
        return True
    if path.endswith(EXCLUDE_SUFFIXES):
        return True
    return any(path.startswith(prefix) for prefix in EXCLUDE_DIR_PREFIXES)


def _classify_kind(path: str) -> str:
    """Classify the CONSUMING file (not the target) by kind, for the table.

    `.md` returns "docs-mention" deliberately — the caller uses this single
    return value both to label the row AND to decide LIVE vs docs-mention,
    so there is exactly one place that decision is made.
    """
    if path.startswith(".github/workflows/") and path.endswith(".yml"):
        return "workflow"
    basename = path.rsplit("/", 1)[-1]
    if basename == "Makefile":
        return "makefile"
    if basename == "package.json":
        return "package.json"
    if basename in ("pyproject.toml", "setup.cfg"):
        return "pyproject"
    if basename == "pytest.ini":
        return "pytest.ini"
    if path.startswith(".husky/"):
        return "husky"
    if basename in ("docker-compose.yml", "docker-compose.yaml") or (
        basename.startswith("docker-compose.") and basename.endswith((".yml", ".yaml"))
    ):
        return "docker-compose"
    if path.startswith("infra/") and path.endswith(".plist"):
        return "plist"
    if path.endswith(".sh"):
        return "shell"
    if path.endswith(".py"):
        return "python"
    if path.endswith(".md"):
        return "docs-mention"
    return "other"


def _git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True
    )


def _deleted_or_renamed_from_diff(base: str, cwd: Path | None) -> list[tuple[str, str | None]]:
    """[(old_path, new_path_or_None), ...] for every D/R entry between
    merge-base(base, HEAD) and HEAD. Raises RuntimeError (caller turns this
    into exit 2) on any git failure — a silent empty result here would read
    as "nothing to check" instead of "could not check", exactly the
    fail-OPEN shape cicatrix-superscar.md #2 warns about for a guard that
    exists to block something.
    """
    mb = _git(["merge-base", base, "HEAD"], cwd=cwd)
    if mb.returncode != 0:
        raise RuntimeError(
            f"git merge-base {base} HEAD failed: {mb.stderr.strip() or mb.stdout.strip()}"
        )
    merge_base = mb.stdout.strip()
    if not merge_base:
        raise RuntimeError(f"git merge-base {base} HEAD returned no sha")

    diff = _git(["diff", "--name-status", "-M", merge_base, "HEAD"], cwd=cwd)
    if diff.returncode != 0:
        raise RuntimeError(
            f"git diff --name-status {merge_base} HEAD failed: "
            f"{diff.stderr.strip() or diff.stdout.strip()}"
        )

    out: list[tuple[str, str | None]] = []
    for line in diff.stdout.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        status = fields[0]
        if status == "D" and len(fields) >= 2:
            out.append((fields[1], None))
        elif status.startswith("R") and len(fields) >= 3:
            out.append((fields[1], fields[2]))
    return out


def _line_names_new_path(content: str, new_path: str) -> bool:
    """Has this line already been repointed at `new_path`?

    The literal path is the easy case and was the only one this recognised. But
    almost nothing in this repo writes a path as one string: consumers build it
    from SEGMENTS, and every idiomatic form spells the destination without ever
    containing it —

        ACTIVE = REPO_ROOT / "docs" / "scars" / "cicatrix-scars.md"
        CICATRIX_FILE = os.path.join(ROOT, "docs", "scars", "cicatrix-scars.md")
        SCAR_LEDGER = REPO_ROOT / 'docs/scars' / 'cicatrix-scars.md'

    Measured 2026-08-31 on the scar-corpus move (PR #5331): all SIX code files
    that mention a moved basename without the literal new path were ALREADY
    repointed, in exactly these shapes, and every one of them was reported as a
    live consumer of a deleted file. 72 findings, zero real. A guard that fires
    on every correctly-repointed consumer of a MOVE — the change class it exists
    to protect — teaches its readers to reach for the kill switch, which is how a
    guard-over-match (superscar #3) turns into a disarmed guard (#2).

    So the question asked here is the ENTITY — does this line name that
    destination — rather than the FORM in which it happens to be written. The
    test is ORDERED and ANCHORED on the basename: every segment of `new_path`
    must appear, in order, and the basename must be the last one matched. Order
    is what keeps it from being a bag of words: a line mentioning `docs` and
    `scars` and some other file does not pass, because the segments must line up
    left to right ending at the right name.

    DELIBERATELY NOT a substring test on each segment independently, and
    deliberately not a regex over the whole line: both let an unrelated sentence
    containing the same words launder a stale reference, which is the under-match
    twin this cure would otherwise create (W94 — a fix for an over-match births
    the under-match unless the corpus covers composition).
    """
    if new_path in content:
        return True
    segments = [seg for seg in new_path.split("/") if seg]
    if len(segments) < 2:
        # A destination at the repo root has no segments to line up, so the
        # ordered test degenerates to "does the basename appear" — which is the
        # grep that found this hit in the first place. Refuse rather than
        # pass everything.
        return False
    cursor = 0
    for seg in segments:
        idx = content.find(seg, cursor)
        if idx < 0:
            return False
        cursor = idx + len(seg)
    return True


_JOIN_CALL_RE = re.compile(r"\bjoin\s*\(")


def _line_has_directory_adjacent(content: str, basename: str) -> bool:
    """Does `content` COMPOSE a path around `basename`, or merely CONTAIN it
    as a bare string ("BARE-BASENAME FILTER" above)?

    For every occurrence of `basename` on the line, look immediately to its
    LEFT — past its own opening quote character and any whitespace — for
    either a literal `/` (a pathlib `/` operator: `X / "cicatrix-scars.md"`;
    or the tail of one longer literal path string:
    `"vendor/legacy/report.md"`, where the `/` sits INSIDE the same
    quotes) or an earlier `join(`/`joinpath(` call on the same line
    (`os.path.join(ROOT, "vendor", "legacy", "report.md")`). Either
    signature means this occurrence is one segment of a path being built;
    finding it on ANY occurrence is enough — a line can mix a real reference
    with an unrelated bare mention, and the real one must not be missed.

    Absent both signatures on every occurrence, the basename sits in a
    tuple/list/dict/call-arg/comment/prose with no directory context at
    all — data, not a location.
    """
    idx = content.find(basename)
    while idx != -1:
        before = content[:idx].rstrip()
        if before.endswith(('"', "'")):
            before = before[:-1].rstrip()
        if before.endswith("/"):
            return True
        if _JOIN_CALL_RE.search(content[:idx]):
            return True
        idx = content.find(basename, idx + 1)
    return False


def _line_has_quoted_occurrence(content: str, basename: str) -> bool:
    """Is `basename` — at least once on this line — inside a quoted string,
    as opposed to a bare, unquoted command-line word ("BARE-BASENAME
    FILTER", shell branch, module docstring)? Approximated by parity: an ODD
    count of `"` (or of `'`) before the occurrence means it sits inside an
    open quote of that kind. Simple and line-scoped like the rest of this
    module — no escaping/nesting awareness, which the measured corpus never
    needed.
    """
    idx = content.find(basename)
    while idx != -1:
        before = content[:idx]
        if before.count('"') % 2 == 1 or before.count("'") % 2 == 1:
            return True
        idx = content.find(basename, idx + 1)
    return False


def _python_basename_parent_kinds_at_line(
    tree: ast.AST, basename: str, lineno: int
) -> set[str]:
    """The AST node-TYPE-NAMEs of the immediate parent of every string
    `Constant` in `tree` whose value == `basename` AND whose own `.lineno`
    equals `lineno` — i.e. "what syntactic role does the literal at THIS
    grep hit's line play" ("BARE-BASENAME FILTER", python branch, module
    docstring). Matching on `lineno` too (not just the value) keeps this
    precise when the same basename string appears more than once in a file
    with different roles.
    """
    kinds: set[str] = set()
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            if (
                isinstance(child, ast.Constant)
                and isinstance(child.value, str)
                and child.value == basename
                and getattr(child, "lineno", None) == lineno
            ):
                kinds.add(type(node).__name__)
    return kinds


def _git_grep_basename(needle: str, cwd: Path | None) -> list[tuple[str, int, str]]:
    """[(path, line_no, line_text), ...] for every tracked-file hit of
    `needle` at HEAD — the commit about to be pushed, robust to a dirty
    working tree in either direction (a stray local edit can neither hide
    nor fabricate a finding). `-F` = fixed string (never a regex — a
    basename can contain `.`/`+`/etc that would otherwise be metacharacters
    git-grep exit 1 = zero hits, NOT an error: for an already-migrated
    rename this is exactly the innocence signal (RENAME SAFETY above).
    """
    result = _git(["grep", "-n", "-F", "-e", needle, "HEAD", "--"], cwd=cwd)
    if result.returncode == 1:
        return []
    if result.returncode != 0:
        raise RuntimeError(f"git grep -F {needle!r} HEAD failed: {result.stderr.strip()}")
    hits: list[tuple[str, int, str]] = []
    for line in result.stdout.splitlines():
        # Format: "HEAD:path:lineno:content" — split on ':' with maxsplit=3
        # so a ':' inside the matched CONTENT never truncates it.
        parts = line.split(":", 3)
        if len(parts) < 4:
            continue
        _rev, path, lineno, content = parts
        try:
            lineno_int = int(lineno)
        except ValueError:
            continue
        hits.append((path, lineno_int, content))
    return hits


def _read_file_at_head(path: str, cwd: Path | None) -> str | None:
    """The consuming FILE's own full content at HEAD (not the target's) —
    needed to compute docstring line ranges, since a single grep hit line has
    no idea whether it sits inside one. Returns None on any git failure
    (unreadable, binary, path vanished between grep and here) — callers treat
    that the same as an unparseable file: fail closed, stay LIVE, note it.
    """
    result = _git(["show", f"HEAD:{path}"], cwd=cwd)
    if result.returncode != 0:
        return None
    return result.stdout


def _python_docstring_line_ranges(tree: ast.AST) -> list[tuple[int, int]]:
    """[(start_line, end_line), ...] (1-indexed, inclusive) for every
    docstring in `tree` — module, class, function, and async-function, at
    every nesting depth (`ast.walk` visits the whole tree, not just the top
    level). A docstring is a node's first body statement, an `Expr` wrapping
    a string `Constant` — the same shape Python itself uses to recognize one.
    Takes an already-PARSED tree, not source: `find_consumers` shares one
    parse per consuming file between this and the BARE-BASENAME FILTER's
    `_python_basename_parent_kinds_at_line` (module docstring), both of
    which need the same AST.
    """
    ranges: list[tuple[int, int]] = []
    docstring_owners = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for node in ast.walk(tree):
        if not isinstance(node, docstring_owners):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            end = getattr(first, "end_lineno", first.lineno)
            ranges.append((first.lineno, end))
    return ranges


def _in_any_range(lineno: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= lineno <= end for start, end in ranges)


def find_consumers(
    targets: list[tuple[str, str | None]],
    include_common: bool,
    cwd: Path | None = None,
) -> list[tuple[str, str, str, str]]:
    """Pure(ish) core: given the target list, return rows
    (location, kind, basename, verdict). The only I/O is `git grep`, which
    is why this takes `targets` already resolved rather than a `--base` —
    the git-diff resolution step and the grep step are separable, and
    keeping them separate is what lets scripts/tests/test_consumer_map.py
    assert on `find_consumers` a set of already-known targets without also
    having to fabricate a realistic diff for every case.
    """
    all_target_paths = {p for old, new in targets for p in (old, new) if p}
    rows: list[tuple[str, str, str, str]] = []
    # Per-CALL caches (not per-target — the same consuming file can be hit by
    # multiple targets, e.g. two deleted files both mentioned in one
    # README): a parsed Python AST keyed by the CONSUMING file's path
    # (shared between the docstring filter and the BARE-BASENAME FILTER's
    # python branch — one parse serves both), docstring ranges derived from
    # it, and a set of paths already warned about (unparseable-Python note
    # printed once per file, never once per hit).
    python_tree_cache: dict[str, ast.AST | None] = {}
    docstring_ranges_cache: dict[str, list[tuple[int, int]]] = {}
    warned_unparseable: set[str] = set()

    def _get_python_tree(path: str) -> ast.AST | None:
        if path not in python_tree_cache:
            source = _read_file_at_head(path, cwd)
            if source is None:
                python_tree_cache[path] = None
            else:
                try:
                    python_tree_cache[path] = ast.parse(source)
                except SyntaxError:
                    python_tree_cache[path] = None
            if python_tree_cache[path] is None and path not in warned_unparseable:
                print(
                    f"consumer_map: could not read/parse {path} as Python "
                    "at HEAD — docstring/bare-basename filters skipped for "
                    "it, hit(s) stay LIVE (fail-closed).",
                    file=sys.stderr,
                )
                warned_unparseable.add(path)
        return python_tree_cache[path]

    def _get_docstring_ranges(path: str, tree: ast.AST) -> list[tuple[int, int]]:
        if path not in docstring_ranges_cache:
            docstring_ranges_cache[path] = _python_docstring_line_ranges(tree)
        return docstring_ranges_cache[path]

    for old_path, new_path in targets:
        basename = old_path.rsplit("/", 1)[-1]
        if basename in COMMON_BASENAMES and not include_common:
            rows.append(
                (f"{old_path} (skipped)", "-", basename, "SKIPPED-common-basename")
            )
            continue

        stems = [basename]
        if basename.endswith(".py"):
            stems.append(basename[:-3])

        seen_locations: set[str] = set()
        for stem in stems:
            for path, lineno, content in _git_grep_basename(stem, cwd):
                if path in all_target_paths:
                    continue  # the deleted/renamed tree itself, not a consumer
                if _is_excluded(path):
                    continue
                if new_path and _line_names_new_path(content, new_path):
                    continue  # RENAME SAFETY — already points at the new path
                loc = f"{path}:{lineno}"
                if loc in seen_locations:
                    continue
                seen_locations.add(loc)
                kind = _classify_kind(path)
                verdict = "docs-mention" if kind == "docs-mention" else "LIVE"

                # PROSE-MENTION FILTER (module docstring, same name) — a hit
                # that only NAMES the file in prose is not a consumer. Runs
                # BEFORE the bare-basename filter deliberately: a docstring
                # is, syntactically, "a basename mentioned inside a larger
                # string constant" — the exact shape the bare-basename
                # filter's own python substring-fallback branch would also
                # claim, and "docs-mention" is the more specific, correct
                # label for it.
                if verdict == "LIVE" and kind in HASH_COMMENT_KINDS and content.lstrip().startswith("#"):
                    verdict = "docs-mention"
                elif verdict == "LIVE" and kind == "python":
                    tree = _get_python_tree(path)
                    if tree is not None and _in_any_range(lineno, _get_docstring_ranges(path, tree)):
                        verdict = "docs-mention"

                # BARE-BASENAME FILTER (module docstring, same name) — only
                # for the FULL-basename search (never the bare python
                # import-stem variant, where "directory-adjacent" is not a
                # meaningful question), and only on a hit still LIVE after
                # the two filters above. Per-KIND precision — see the module
                # docstring's guilt corpus paragraph for why each branch is
                # shaped this way.
                if verdict == "LIVE" and stem == basename:
                    if kind == "python":
                        tree = _get_python_tree(path)
                        if tree is not None:
                            exact_parents = _python_basename_parent_kinds_at_line(
                                tree, basename, lineno
                            )
                            if exact_parents:
                                # The literal IS exactly the basename
                                # somewhere on this line — judge by its
                                # syntactic role (container/call-arg vs an
                                # Assign RHS or a `/`-BinOp, either of which
                                # stays conservatively LIVE).
                                if (
                                    exact_parents <= DATA_CONTAINER_PARENT_KINDS
                                    and not _line_has_directory_adjacent(content, basename)
                                ):
                                    verdict = "bare-basename"
                            elif not _line_has_directory_adjacent(content, basename):
                                # The basename is only a SUBSTRING of a
                                # larger string constant (prose embedded in
                                # a string being written/asserted/matched,
                                # never a docstring — that path already
                                # returned above) — no syntactic role to
                                # judge; fall back to plain
                                # directory-adjacency, same as "other".
                                verdict = "bare-basename"
                        # tree is None (unparseable) -> fail CLOSED, no
                        # downgrade attempted, same discipline as the
                        # docstring filter above.
                    elif kind == "other":
                        if not _line_has_directory_adjacent(content, basename):
                            verdict = "bare-basename"
                    elif kind in QUOTE_REQUIRED_KINDS:
                        if _line_has_quoted_occurrence(
                            content, basename
                        ) and not _line_has_directory_adjacent(content, basename):
                            verdict = "bare-basename"

                rows.append((loc, kind, basename, verdict))

    return rows


def _print_table(rows: list[tuple[str, str, str, str]]) -> None:
    if not rows:
        # Reached only when targets existed but every git-grep hit was
        # filtered out (self-reference, exclusion, or an already-repointed
        # rename) — NOT the same as "no targets" (that's main()'s own,
        # differently-worded, earlier-return message). Do not conflate the
        # two: one says "nothing to check", this says "checked, all clean".
        print("consumer_map: targets checked, zero surviving hits (all clean).")
        return
    print("location | kind | basename | verdict")
    for loc, kind, basename, verdict in rows:
        print(f"{loc} | {kind} | {basename} | {verdict}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="consumer_map.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Enumerate live consumers of DELETED or RENAMED files, matched by "
            "BASENAME (and by bare import-stem for .py targets) across "
            ".github/workflows/*.yml, shell scripts, Python files (string "
            "literals and imports), Makefiles, package.json, pyproject.toml/"
            "pytest.ini, .husky/ hooks, docker-compose files, and infra/*.plist.\n\n"
            "PROXY WARNING: basename matching OVER-matches by design — two "
            "unrelated files sharing a name will collide, and -F does a plain "
            "substring match (a longer name containing this one as a fragment "
            "shows up too). A common basename (conftest.py, __init__.py) is "
            "skipped by default for exactly this reason (--include-common to "
            "force it). This is a deliberate safety asymmetry: an over-match "
            "costs a human one extra row to read; an under-match is the actual "
            "PR #4459 defect this tool exists to close. Read the printed table "
            "before trusting the verdict — same discipline cicatrix-superscar.md "
            "#3 asks of every substring-matching guard in this repo."
        ),
    )
    parser.add_argument(
        "--base",
        default="origin/main",
        help="Diff base ref (default: origin/main). Ignored if PATHS are given.",
    )
    parser.add_argument(
        "--include-common",
        action="store_true",
        help="Do not skip common basenames (conftest.py, __init__.py).",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Explicit deleted-file paths to check, bypassing git diff (no rename pairing available in this mode).",
    )
    args = parser.parse_args(argv)

    try:
        if args.paths:
            targets: list[tuple[str, str | None]] = [(p, None) for p in args.paths]
        else:
            targets = _deleted_or_renamed_from_diff(args.base, cwd=None)
    except RuntimeError as exc:
        print(f"consumer_map: {exc}", file=sys.stderr)
        return 2

    if not targets:
        print("consumer_map: no deleted/renamed files in scope — nothing to check.")
        print("CONSUMER_MAP_LIVE_COUNT=0")
        return 0

    try:
        rows = find_consumers(targets, args.include_common, cwd=None)
    except RuntimeError as exc:
        print(f"consumer_map: {exc}", file=sys.stderr)
        return 2

    _print_table(rows)
    live_count = sum(1 for row in rows if row[3] == "LIVE")
    # Machine-parseable summary line, always printed (even 0), always LAST —
    # a caller (the pre-push wiring) greps this one line instead of counting
    # table rows, so a future change to the table's human-readable format
    # cannot silently break the count it reports.
    print(f"CONSUMER_MAP_LIVE_COUNT={live_count}")
    return 1 if live_count else 0


if __name__ == "__main__":
    sys.exit(main())
