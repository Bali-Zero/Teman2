#!/usr/bin/env python3
"""pr_collision_check.py — advisory: open-PR add/add collision check (PR-3,
L06-ci-merge-queue-ship-pipeline.md).

Generalizes lint_scar_number_collision.py's claim-set technique from
"W-number" to "file + hunk-window": every open PR's merge-base-anchored
added hunks per file are intersected against every other open PR's, on
files touched by 2+ of them. Advisory only — gates nothing, no workflow
job may `needs:` this.

DISCRIMINATOR = add/add in OVERLAPPING WINDOWS, never bare "same file"
(trap #11): two PRs modifying disjoint lines of one file must NOT flag.

COMPARABILITY (the second half of the discriminator, added post-review —
see NOT COMPARED below): "overlapping windows" only means anything between
two PRs that share the SAME merge-base. A window is `[old_start, old_end)`
in THAT merge-base's coordinate space (see WINDOW below); two PRs anchored
to DIFFERENT merge-bases have windows in coordinate spaces that are not
comparable AT ALL, not "probably fine" -- comparing them would be comparing
apples in one repo's history to oranges in another's. This tool therefore
compares a PR-pair on a shared file ONLY when their merge-bases agree, and
records every pair it could NOT compare for that reason rather than
folding it silently into "no collision found". The only sound GENERAL
oracle for "would these two conflict" regardless of merge-base is
`git merge-tree` (a real three-way merge simulation) -- that is a known,
deliberate future redesign, out of scope here; this tool's whole value is
being cheap and advisory, not a merge-tree replacement.

MERGE-BASE ANCHORING (W102's antidote, same class as
scripts/ci/hotzone_changed_files.sh): a two-dot diff (origin/main tip vs
branch) cannot tell "this branch changed this line" from "this branch is
merely BEHIND on this line" (an unrelated PR landed since the merge-base
and touched a line this branch never touched). Trap #11 measured this
live on PENDING-ARMS.md: a two-dot diff showed a spurious
`@@ -1202,7 +1202,7 @@` on both #4783/#4782 that vanished once anchored on
the real merge-base, while a second hunk (`@@ -1271,6 +1271,7 @@` vs
`@@ -1272,6 +1272,7 @@`) survived as a genuine add/add overlap.
`resolve_merge_base()` is the ONLY thing between those two readings.

WINDOW = a hunk's old-side (merge-base-relative) span
`[old_start, old_start + max(old_len, 1))` — the coordinate space two
sibling branches sharing a merge-base agree on. A hunk contributes a
window only if it has >=1 '+' line; pure-deletion hunks contribute
nothing (delete/delete resolves cleanly on its own, out of scope here).
NOTE ON TEST COVERAGE: every window-clamp test in this tool's corpus is
built from hand-written `-U0`-shaped hunk headers (zero context lines).
Real `git diff` output defaults to `-U3` (3 lines of context on each
side), whose old_start/old_len already fold that context in -- the corpus
does not independently exercise whether context-line inflation changes
window math; it only pins the `-U0` degenerate case (new-file and pure
insertion) that `max(old_len, 1)` exists for.

KNOWN BLIND SPOTS (declared, not cured -- each one was looked at and left
as-is, not missed):
  - RENAME/RENAME on the SAME source path: `git diff --no-renames` is used
    throughout so a rename shows as delete+add rather than a rename hunk.
    Two review seats disagreed on whether that flag is the right call here
    (one called it a miss -- a renamed-away source path's collision is
    invisible either way; the other called `--no-renames` the safer of two
    bad options, since WITH rename detection the add-side window can shift
    unpredictably too). Neither changes the code: with or without the
    flag, a rename/rename conflict on the SOURCE path is not detected by
    this tool. Recorded so the next reader does not have to re-derive it.
  - BINARY / SUBMODULE add/add: a binary file's diff carries no `@@` hunk
    line at all, so `parse_multi_file_diff` silently contributes zero
    windows for it -- two PRs both replacing the same binary asset collide
    for real and this tool will not see it.
  - `gh pr list --limit N` truncation: see PR_LIST_LIMIT / the
    scan-truncated report line below -- reported explicitly, not silently
    folded into "clean".

FIXTURE (`--fixture PATH`): `{"prs": {"<label>": {"<path>": "<patch>"}}}`,
each patch a bare GitHub `.patch` field or a full per-file diff slice. An
optional `"merge_base": "<sha-or-name>"` entry inside a PR's file map is a
reserved key (never a real file path in practice — a bare SHA/name string
never matches a hunk header, so `gather_fixture_pr_windows` silently
contributes zero windows for it even without knowing the key exists) that
declares that PR's merge-base for comparability purposes. A PR that omits
it gets NO_MERGE_BASE_DECLARED, the SAME sentinel for every PR that omits
it — so every fixture written before this key existed still puts all its
PRs in one comparable group, exactly as it behaved before COMPARABILITY
was added. Backward-compatible by construction, not by special-casing old
fixtures.

Exit: 0 clean · 1 collision(s) · 2 operational error (never confused with
"0 collisions" — superscar #2 discipline). Exit code reflects ONLY
add/add collisions found; NOT COMPARED pairs and a truncated scan never
flip it to 2 (they are not operational failures, the scan itself
succeeded) and never flip a clean 0 to 1 (they are not findings) — they
are reported as prose so a reader cannot mistake incomplete coverage for
a positive result, without this advisory tool's exit code lying about
which of those two very different things happened.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPO = "Bali-Zero/Teman2"
DEFAULT_BASE_REF = "origin/main"
PR_LIST_LIMIT = 500  # K9: `gh pr list --limit` — see gather_live_pr_windows.
# Sentinel merge-base for a fixture PR that declares none — every PR that
# omits the key shares this SAME value, so they're all mutually comparable
# (matches this tool's pre-COMPARABILITY behavior for every old fixture).
NO_MERGE_BASE_DECLARED = "<fixture: no merge_base declared>"
# `@@ -oldstart[,oldlen] +newstart[,newlen] @@` — a missing count means 1.
_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
Window = tuple[int, int]  # [start, end) in OLD-FILE (merge-base) coordinates

# Printed on every report regardless of live overlap this run (PR-3
# acceptance: "a table of known hot files"). mdx batches are a glob, so
# named rather than matched.
HOT_FILES = (
    ("evidence/brief.yml", "fixed root path — collides by construction until "
     "the 2026-09-05 per-PR-path deprecation (scripts/ci/evidence_paths.py)"),
    ("evidence/pack.yml", "same fixed-root-path class as brief.yml above"),
    (".claude/skills/modus/PENDING-ARMS.md", "append-only; `merge=union` "
     "resolves it locally but the queue runs no merge driver (trap #11)"),
    ("organs_registry.yaml", "shared genome registry, frequent concurrent edits"),
    ("infra/required.d/contexts.json", "regenerated snapshot, frequent regen races"),
    ("content/**/*.mdx", "editorial batch imports on shared MDX files (glob)"),
)


class CollisionCheckError(RuntimeError):
    """A git/gh call failed mid-scan. Never report clean on a partial scan."""


def parse_add_windows_for_hunks(patch_text: str) -> list[Window]:
    """Windows from ONE file's patch text. Header lines, if present, are
    ignored — only `@@` hunks matter, so this parses both a bare GitHub
    `.patch` field and one file's slice of a full diff alike."""
    windows: list[Window] = []
    in_hunk = False
    old_start = old_len = 0
    has_addition = False

    def flush() -> None:
        nonlocal in_hunk, has_addition
        if in_hunk and has_addition:
            windows.append((old_start, old_start + max(old_len, 1)))
        in_hunk = False
        has_addition = False

    for line in patch_text.splitlines():
        m = _HUNK_RE.match(line)
        if m:
            flush()
            in_hunk = True
            old_start = int(m.group(1))
            old_len = int(m.group(2)) if m.group(2) is not None else 1
            has_addition = False
            continue
        if in_hunk and line.startswith("+") and not line.startswith("+++"):
            has_addition = True
    flush()
    return windows


def parse_multi_file_diff(patch_text: str) -> dict[str, list[Window]]:
    """Split a real `git diff` (multi-file) unified diff on `diff --git`
    boundaries, parse each file's slice via parse_add_windows_for_hunks."""
    result: dict[str, list[Window]] = {}
    current_path: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if current_path is not None and buffer:
            windows = parse_add_windows_for_hunks("\n".join(buffer))
            if windows:
                result[current_path] = windows

    for line in patch_text.splitlines():
        if line.startswith("diff --git "):
            flush()
            current_path, buffer = None, []
            continue
        if line.startswith("+++ b/"):
            current_path = line[len("+++ b/"):]
            continue
        if line.startswith("+++ /dev/null"):
            current_path = None
            continue
        buffer.append(line)
    flush()
    return result


def windows_overlap(a: Window, b: Window) -> bool:
    return a[0] < b[1] and b[0] < a[1]


@dataclass(frozen=True)
class Collision:
    path: str
    pr_a: str
    pr_b: str
    window_a: Window
    window_b: Window


@dataclass(frozen=True)
class NotCompared:
    """A file shared by two PRs whose merge-bases DIFFER — their windows
    live in incomparable coordinate spaces (see module docstring,
    COMPARABILITY), so this pair was never checked for overlap on this
    file at all. This is a gap in coverage, not a clean bill of health:
    a pair recorded here may still conflict for real."""
    path: str
    pr_a: str
    pr_b: str
    merge_base_a: str
    merge_base_b: str


def find_collisions(pr_files: dict[str, dict[str, list[Window]]]) -> list[Collision]:
    """pr_files: {pr_label: {path: [windows]}}. A file on <2 PRs is never a
    candidate — necessary but not sufficient (trap #11). Callers that must
    also account for merge-base comparability (main() does) call
    find_collisions_and_uncompared instead; this function stays exactly as
    it was so its whole existing test corpus keeps meaning what it always
    meant."""
    by_path: dict[str, list[tuple[str, list[Window]]]] = {}
    for pr_label in sorted(pr_files):
        for path, windows in pr_files[pr_label].items():
            by_path.setdefault(path, []).append((pr_label, windows))
    collisions: list[Collision] = []
    for path in sorted(by_path):
        entries = by_path[path]
        if len(entries) < 2:
            continue
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                label_a, windows_a = entries[i]
                label_b, windows_b = entries[j]
                for wa in windows_a:
                    for wb in windows_b:
                        if windows_overlap(wa, wb):
                            collisions.append(Collision(path, label_a, label_b, wa, wb))
    return collisions


def find_collisions_and_uncompared(
    pr_files: dict[str, dict[str, list[Window]]],
    pr_merge_base: dict[str, str],
) -> tuple[list[Collision], list[NotCompared]]:
    """The COMPARABILITY-aware entry point (module docstring). Partitions
    PRs into groups by merge-base; runs the UNCHANGED find_collisions only
    within each group (so a same-merge-base pair is compared exactly as
    before); every PR-pair that shares a file but sits in DIFFERENT groups
    is recorded as NotCompared instead of silently skipped. Every PR
    missing from `pr_merge_base` falls back to NO_MERGE_BASE_DECLARED, so
    a caller that never populates merge-base info at all (every PR gets
    the same sentinel) reproduces find_collisions's old global behavior
    exactly — the backward-compat guarantee the module docstring makes."""
    by_path: dict[str, list[str]] = {}
    for pr_label in sorted(pr_files):
        for path in pr_files[pr_label]:
            by_path.setdefault(path, []).append(pr_label)

    not_compared: list[NotCompared] = []
    for path in sorted(by_path):
        labels = by_path[path]
        if len(labels) < 2:
            continue
        for i in range(len(labels)):
            for j in range(i + 1, len(labels)):
                a, b = labels[i], labels[j]
                mb_a = pr_merge_base.get(a, NO_MERGE_BASE_DECLARED)
                mb_b = pr_merge_base.get(b, NO_MERGE_BASE_DECLARED)
                if mb_a != mb_b:
                    not_compared.append(NotCompared(path, a, b, mb_a, mb_b))

    groups: dict[str, list[str]] = {}
    for label in sorted(pr_files):
        groups.setdefault(pr_merge_base.get(label, NO_MERGE_BASE_DECLARED), []).append(label)

    collisions: list[Collision] = []
    for group_labels in groups.values():
        sub = {label: pr_files[label] for label in group_labels}
        collisions.extend(find_collisions(sub))
    collisions.sort(key=lambda c: (c.path, c.pr_a, c.pr_b))

    return collisions, not_compared


def format_report(
    collisions: list[Collision],
    scanned_prs: int,
    scanned_shared_files: int,
    not_compared: list[NotCompared],
    truncated_scan: bool = False,
) -> str:
    lines = ["## PR collision check (advisory — gates nothing)", ""]
    if truncated_scan:
        # K9: `gh pr list --limit` hit -- PRs beyond it were NEVER scanned,
        # and are indistinguishable from scanned-and-clean unless this line
        # says so. Printed first, before any verdict, so it cannot be missed.
        lines.append(
            f"SCAN TRUNCATED — the open-PR list hit the {PR_LIST_LIMIT}-PR "
            "fetch limit; PR(s) beyond it were never scanned. Raising the "
            "limit only moves this same gap one order of magnitude later — "
            "treat this run as a PARTIAL scan, not a clean one."
        )
        lines.append("")
    if collisions:
        lines.append(f"COLLISION — {len(collisions)} add/add overlap(s) across {scanned_prs} open PR(s):")
        for c in collisions:
            lines.append(
                f"  - `{c.path}`: {c.pr_a} (lines {c.window_a[0]}-{c.window_a[1]}) "
                f"vs {c.pr_b} (lines {c.window_b[0]}-{c.window_b[1]}) — serialize "
                "these two; the merge queue runs no merge driver."
            )
    else:
        # Deliberately NOT "No add/add collisions found" full stop (former
        # wording) -- that reads as a guarantee this tool has not earned.
        # Qualified by "genuinely shared" (K7: the count below now really
        # is files touched by 2+ PRs, not every file touched by anyone) and
        # by the NOT COMPARED line right under it, always printed, even at
        # zero, so a fully-uncomparable run cannot pass as a confident
        # clean by omission.
        lines.append(
            f"No add/add overlap found among the {scanned_shared_files} file(s) "
            f"genuinely shared by 2+ of the {scanned_prs} open PR(s) scanned "
            "(modify/modify on disjoint lines does not count). This is not a "
            "guarantee across every pair — see NOT COMPARED below."
        )
    lines.append("")
    lines.append(
        f"NOT COMPARED — {len(not_compared)} pair(s) shared a file but had "
        "DIFFERENT merge-bases, so their windows are not in the same "
        "coordinate space and could not be checked for overlap at all (see "
        "module docstring, COMPARABILITY). 0 collisions above is not a "
        "guarantee these pairs are safe — only that this tool did not look."
    )
    for nc in not_compared:
        lines.append(f"  - `{nc.path}`: {nc.pr_a} vs {nc.pr_b} — different merge-bases, not compared")
    lines.append("")
    lines.append("Known hot files (reference — flagged above only on a live overlap):")
    for path, note in HOT_FILES:
        lines.append(f"  - `{path}` — {note}")
    lines.append("")
    lines.append(
        "Advisory only: gates nothing. Reinstate-by-catch to a required check "
        "needs two clean advisory weeks first (PR-3 acceptance)."
    )
    return "\n".join(lines)


def _run(cmd: list[str], cwd: Path, check: bool = True) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    except OSError as exc:
        # e.g. `gh` missing from PATH -- must land as CANNOT VERIFY (exit 2),
        # never an uncaught traceback that happens to exit 1 and collide
        # with "collision found" in a consumer's exit-code check.
        raise CollisionCheckError(f"command could not even start: {' '.join(cmd)}\n{exc}") from exc
    if check and result.returncode != 0:
        raise CollisionCheckError(
            f"command failed (rc={result.returncode}): {' '.join(cmd)}\n{result.stderr.strip()}"
        )
    return result.stdout


def resolve_merge_base(repo_root: Path, base_ref: str, head_ref: str) -> str:
    return _run(["git", "merge-base", base_ref, head_ref], repo_root).strip()

def fetch_pr_head(repo_root: Path, pr_number: int) -> str:
    """Fetch `refs/pull/<n>/head` into a scratch ref, return its SHA."""
    scratch_ref = f"refs/prcollision/{pr_number}"
    _run(["git", "fetch", "--no-tags", "origin", f"+refs/pull/{pr_number}/head:{scratch_ref}"], repo_root)
    return _run(["git", "rev-parse", scratch_ref], repo_root).strip()

def pr_windows_from_git(repo_root: Path, base_sha: str, head_ref: str) -> tuple[str, dict[str, list[Window]]]:
    """The one merge-base-anchored diff call this whole tool stands on:
    `merge_base = resolve_merge_base(base_sha, head_ref)`, then
    `git diff merge_base head_ref`. Swap `merge_base` for `base_sha` here
    and every "merely behind" fixture goes red (see test file). Returns
    `(merge_base, windows)` — the merge-base is plumbed OUT here (not
    recomputed by a caller) because this is the one place that already
    pays for computing it."""
    merge_base = resolve_merge_base(repo_root, base_sha, head_ref)
    patch = _run(["git", "diff", "--no-renames", merge_base, head_ref], repo_root)
    return merge_base, parse_multi_file_diff(patch)

def gather_live_pr_windows(
    repo_root: Path, repo_slug: str, base_ref: str = DEFAULT_BASE_REF
) -> tuple[dict[str, dict[str, list[Window]]], dict[str, str], bool]:
    """Returns `(pr_windows, pr_merge_base, truncated_scan)`. truncated_scan
    is True iff `gh pr list` returned exactly PR_LIST_LIMIT entries — the
    only signal available that more open PRs may exist beyond the fetch
    window (K9); it can never be told apart from "exactly the limit, no
    more" from here, so it is reported as a possibility, not a certainty."""
    raw = _run(["gh", "pr", "list", "--repo", repo_slug, "--state", "open",
                "--json", "number", "--limit", str(PR_LIST_LIMIT)], repo_root)
    try:
        pr_list = json.loads(raw)
    except json.JSONDecodeError as exc:
        # A parse failure is an OPERATIONAL failure (truncated/malformed
        # `gh` output), never a finding -- must land as exit 2, not exit 1
        # ("collision found"). See test_pr_collision_check.py FIX-2 tests.
        raise CollisionCheckError(f"gh pr list returned unparseable JSON: {exc}") from exc
    truncated_scan = len(pr_list) >= PR_LIST_LIMIT

    base_sha = _run(["git", "rev-parse", base_ref], repo_root).strip()
    result: dict[str, dict[str, list[Window]]] = {}
    pr_merge_base: dict[str, str] = {}
    for entry in pr_list:
        label = f"PR #{entry['number']}"
        head_sha = fetch_pr_head(repo_root, entry["number"])
        merge_base, windows = pr_windows_from_git(repo_root, base_sha, head_sha)
        if windows:
            result[label] = windows
            pr_merge_base[label] = merge_base
    return result, pr_merge_base, truncated_scan

def gather_fixture_pr_windows(fixture_path: Path) -> dict[str, dict[str, list[Window]]]:
    try:
        data = json.loads(fixture_path.read_text())
    except json.JSONDecodeError as exc:
        # Same rule as the live path above: a malformed --fixture is an
        # OPERATIONAL failure (exit 2), never exit 1 ("collision found").
        raise CollisionCheckError(f"--fixture {fixture_path} is not valid JSON: {exc}") from exc
    result: dict[str, dict[str, list[Window]]] = {}
    for label, files in data.get("prs", {}).items():
        by_file: dict[str, list[Window]] = {}
        for path, patch in files.items():
            windows = parse_add_windows_for_hunks(patch)
            if windows:
                by_file[path] = windows
        if by_file:
            result[label] = by_file
    return result

def gather_fixture_pr_merge_base(fixture_path: Path) -> dict[str, str]:
    """The optional per-PR `merge_base` fixture key (module docstring,
    FIXTURE). A PR entry that omits it gets NO_MERGE_BASE_DECLARED — the
    SAME sentinel for every PR that omits it, so a fixture written before
    this key existed puts all its PRs in one comparable group, exactly as
    find_collisions behaved before COMPARABILITY was added. Reads the
    fixture file independently of gather_fixture_pr_windows (which stays
    completely unaware of this key) so that function's contract, and every
    existing test built on it, is untouched by this addition."""
    try:
        data = json.loads(fixture_path.read_text())
    except json.JSONDecodeError as exc:
        raise CollisionCheckError(f"--fixture {fixture_path} is not valid JSON: {exc}") from exc
    return {
        label: files.get("merge_base", NO_MERGE_BASE_DECLARED)
        for label, files in data.get("prs", {}).items()
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"default {DEFAULT_REPO}")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help="local git checkout to operate in")
    parser.add_argument("--base-ref", default=DEFAULT_BASE_REF, help=f"default {DEFAULT_BASE_REF}")
    parser.add_argument(
        "--fixture", type=Path, default=None,
        help="JSON fixture ({'prs':{'<label>':{'<path>':'<patch>'}}}) — bypasses git/gh entirely",
    )
    args = parser.parse_args(argv)

    truncated_scan = False
    try:
        if args.fixture:
            pr_windows = gather_fixture_pr_windows(args.fixture)
            pr_merge_base = gather_fixture_pr_merge_base(args.fixture)
        else:
            pr_windows, pr_merge_base, truncated_scan = gather_live_pr_windows(
                args.repo_root, args.repo, args.base_ref
            )
    except CollisionCheckError as exc:
        print(f"CANNOT VERIFY — collision scan could not be assembled:\n{exc}", file=sys.stderr)
        return 2

    collisions, not_compared = find_collisions_and_uncompared(pr_windows, pr_merge_base)

    # K7: "shared by 2+ PRs" means exactly that -- a path's touch-count
    # across ALL scanned PRs, not the count of paths that happened to
    # collide (which undercounts: a shared-but-disjoint file was never
    # counted at all) and not every path touched by anyone (which the
    # former no-collision branch used, overcounting on every clean run).
    touch_counts: dict[str, int] = {}
    for files in pr_windows.values():
        for path in files:
            touch_counts[path] = touch_counts.get(path, 0) + 1
    shared_files = sum(1 for n in touch_counts.values() if n >= 2)

    print(format_report(collisions, len(pr_windows), shared_files, not_compared, truncated_scan))
    # Exit code reflects ONLY collisions found -- not_compared and
    # truncated_scan never flip it (see module docstring, Exit:). They are
    # surfaced in the report text above instead, printed unconditionally
    # and prominently, precisely so a reader cannot mistake "exit 0" for
    # "fully verified clean" when either of those is nonzero/True.
    return 1 if collisions else 0


if __name__ == "__main__":
    sys.exit(main())
