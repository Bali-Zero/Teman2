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
COMMON_BASENAMES: frozenset[str] = frozenset({"conftest.py", "__init__.py"})

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
                if new_path and new_path in content:
                    continue  # RENAME SAFETY — already points at the new path
                loc = f"{path}:{lineno}"
                if loc in seen_locations:
                    continue
                seen_locations.add(loc)
                kind = _classify_kind(path)
                verdict = "docs-mention" if kind == "docs-mention" else "LIVE"
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
