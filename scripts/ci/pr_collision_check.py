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

FIXTURE (`--fixture PATH`): `{"prs": {"<label>": {"<path>": "<patch>"}}}`,
each patch a bare GitHub `.patch` field or a full per-file diff slice.

Exit: 0 clean · 1 collision(s) · 2 operational error (never confused with
"0 collisions" — superscar #2 discipline).
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


def find_collisions(pr_files: dict[str, dict[str, list[Window]]]) -> list[Collision]:
    """pr_files: {pr_label: {path: [windows]}}. A file on <2 PRs is never a
    candidate — necessary but not sufficient (trap #11)."""
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


def format_report(collisions: list[Collision], scanned_prs: int, scanned_shared_files: int) -> str:
    lines = ["## PR collision check (advisory — gates nothing)", ""]
    if collisions:
        lines.append(f"COLLISION — {len(collisions)} add/add overlap(s) across {scanned_prs} open PR(s):")
        for c in collisions:
            lines.append(
                f"  - `{c.path}`: {c.pr_a} (lines {c.window_a[0]}-{c.window_a[1]}) "
                f"vs {c.pr_b} (lines {c.window_b[0]}-{c.window_b[1]}) — serialize "
                "these two; the merge queue runs no merge driver."
            )
    else:
        lines.append(
            f"No add/add collisions found ({scanned_prs} open PR(s) scanned, "
            f"{scanned_shared_files} file(s) shared by 2+ PRs — modify/modify "
            "on disjoint lines does not count)."
        )
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

def pr_windows_from_git(repo_root: Path, base_sha: str, head_ref: str) -> dict[str, list[Window]]:
    """The one merge-base-anchored diff call this whole tool stands on:
    `merge_base = resolve_merge_base(base_sha, head_ref)`, then
    `git diff merge_base head_ref`. Swap `merge_base` for `base_sha` here
    and every "merely behind" fixture goes red (see test file)."""
    merge_base = resolve_merge_base(repo_root, base_sha, head_ref)
    patch = _run(["git", "diff", "--no-renames", merge_base, head_ref], repo_root)
    return parse_multi_file_diff(patch)

def gather_live_pr_windows(
    repo_root: Path, repo_slug: str, base_ref: str = DEFAULT_BASE_REF
) -> dict[str, dict[str, list[Window]]]:
    pr_list = json.loads(
        _run(["gh", "pr", "list", "--repo", repo_slug, "--state", "open",
              "--json", "number", "--limit", "500"], repo_root)
    )
    base_sha = _run(["git", "rev-parse", base_ref], repo_root).strip()
    result: dict[str, dict[str, list[Window]]] = {}
    for entry in pr_list:
        label = f"PR #{entry['number']}"
        head_sha = fetch_pr_head(repo_root, entry["number"])
        windows = pr_windows_from_git(repo_root, base_sha, head_sha)
        if windows:
            result[label] = windows
    return result

def gather_fixture_pr_windows(fixture_path: Path) -> dict[str, dict[str, list[Window]]]:
    data = json.loads(fixture_path.read_text())
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

    try:
        if args.fixture:
            pr_windows = gather_fixture_pr_windows(args.fixture)
        else:
            pr_windows = gather_live_pr_windows(args.repo_root, args.repo, args.base_ref)
    except CollisionCheckError as exc:
        print(f"CANNOT VERIFY — collision scan could not be assembled:\n{exc}", file=sys.stderr)
        return 2

    collisions = find_collisions(pr_windows)
    shared_files = (
        len({c.path for c in collisions})
        if collisions
        else len({p for files in pr_windows.values() for p in files})
    )
    print(format_report(collisions, len(pr_windows), shared_files))
    return 1 if collisions else 0


if __name__ == "__main__":
    sys.exit(main())
