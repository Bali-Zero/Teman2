#!/usr/bin/env python3
"""lint_scar_number_collision.py — executable antidote for W128 (scar-number collision).

THE DEFECT (W128, sibling of W40's migration-number collision in a new
domain): a `W<n>` scar number is only CLAIMED when a PR opens and only
RESOLVED when it merges. Reading the highest `W<n>` heading on `origin/main`
tells you nothing about a number sitting in an OPEN, unmerged PR — so two
lanes can silently pick the same integer. Measured 2026-08-23: a Mini session
broadcast "start at W126" at 15:20Z; PR #4713 claimed W126 at 16:03:33Z; PR
#4714 claimed W126 independently at 16:06:32Z (renumbered to W127 after the
fact). Throughout, `origin/main` topped out at W125, so a naive
`git show origin/main:... | grep -oE 'W[0-9]+' | sort -n | tail -1` would have
said W126 was free — and it WAS, for the three minutes between the two claims.

TWO TRAPS baked into the check below because both have drawn blood:
  1. `sort -n`, never plain `sort` — lexically "W99" sorts after "W124", so a
     taken number reads as free.
  2. `origin/main` alone is not the corpus. The claim set is the union of
     main's headings and every OPEN PR's *added* scar headings.
  3. Heading lines are `### <emoji> W<n> (...)` — an emoji sits between the
     `#`s and the `W`, so anchoring a regex on `^#+\\s*W` matches NOTHING (the
     mandate's own first grep failed exactly this way). This script detects a
     heading by its `#`/`##`... prefix alone, then searches the whole line
     for the first `W<digits>` token.

THE CLAIM SET, precisely: every W-number that leads its own `###`/`####`
heading on `origin/main`'s `.claude/rules/cicatrix-scars.md`, unioned with
every W-number introduced by a `+`-added heading line in the diff of that
same file across every currently OPEN pull request. A number is a COLLISION
when 2+ sources OTHER THAN `origin/main` both add it (two open PRs picked the
same free number — the W126/W126 incident), or when an open PR adds a number
`origin/main` already carries (claiming an already-merged number). Multiple
historical entries sharing a base number that already coexist on
`origin/main` alone (W81 / W81-armamento-sospeso / W81b-dlq-blind-heal-loop —
deliberately suffix-disambiguated, cicatrix-superscar.md #1) are ONE source
here and never collide with themselves; suffix-disambiguation is the accepted
resolution once a number is known-taken, not a new defect.

USAGE — two arms:
  --next-only   Pre-flight: "what number do I take?" Prints `W<n>` to stdout.
                Still exits 1 (with the collision detail on stderr) if the
                claim set is already contested — a caller that only wanted
                the number must not silently trust it in that case.
  (default)     Check: full report on stdout, exit 0 clean / 1 collision.

Exit codes: 0 = clean · 1 = collision found · 2 = operational error (git/gh
call failed — the claim set could not even be assembled, which is NOT the
same as clean; fail-visible, not fail-silent).

`--fixture PATH` swaps the live `git show`/`gh api` calls for a local JSON
file (`{"main": "<markdown>", "prs": {"<label>": "<unified diff patch>"}}`) —
this is what makes the guilt/innocence tests real subprocess runs instead of
calling private functions, and lets anyone dry-run the exact parsing logic
offline.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO = "Bali-Zero/Teman2"
DEFAULT_FILE = ".claude/rules/cicatrix-scars.md"

# Heading lines: `### 🐛 W127 (...)`, `#### W67b — ...`, `## W94 — ...`. The
# emoji (or nothing at all) between the `#`s and the `W` is why this anchors
# on the `#` prefix alone rather than on `^#+\s*W`.
_HEADING_PREFIX = ("## ", "### ", "#### ")
# No trailing \b: a suffixed id like "W67b" or "W81-armamento-sospeso" must
# still yield the number 67/81 — only a *leading* word boundary matters, so
# "SW123" (mid-token) is correctly rejected while "W67b" is correctly kept.
_WNUM_RE = re.compile(r"\bW(\d+)")

ClaimMap = dict[int, list[str]]


class LintOperationalError(RuntimeError):
    """A git/gh call failed — the claim set could not be assembled at all.

    Distinct from "clean": a scan that could not see the corpus must never
    report as if it did (superscar #2 discipline — fail-visible, not
    fail-silent).
    """


def parse_heading_numbers(markdown_text: str) -> list[int]:
    """Every W<n> that leads its own heading line, in encounter order (dupes kept)."""
    numbers: list[int] = []
    for line in markdown_text.splitlines():
        if not line.startswith(_HEADING_PREFIX):
            continue
        m = _WNUM_RE.search(line)
        if m:
            numbers.append(int(m.group(1)))
    return numbers


def parse_added_heading_numbers_from_patch(patch_text: str | None) -> list[int]:
    """Every W<n> on a `+`-added heading line inside a unified diff patch.

    `patch_text` is the `.patch` field GitHub's `pulls/{n}/files` API returns
    for one file in one PR (`None`/empty when GitHub omitted it, e.g. a
    diff too large to render — or when the PR never touched the file).
    """
    if not patch_text:
        return []
    numbers: list[int] = []
    for line in patch_text.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        content = line[1:]
        if not content.startswith(_HEADING_PREFIX):
            continue
        m = _WNUM_RE.search(content)
        if m:
            numbers.append(int(m.group(1)))
    return numbers


def compute_claim_map(main_numbers: list[int], pr_claims: dict[str, list[int]]) -> ClaimMap:
    """Map W-number -> sorted list of sources that claim it (`origin/main` first)."""
    claim_map: ClaimMap = {}
    for n in sorted(set(main_numbers)):
        claim_map.setdefault(n, []).append("origin/main")
    for source in sorted(pr_claims):
        for n in sorted(set(pr_claims[source])):
            claim_map.setdefault(n, []).append(source)
    return claim_map


def find_collisions(claim_map: ClaimMap) -> ClaimMap:
    collisions: ClaimMap = {}
    for n, sources in claim_map.items():
        non_main = [s for s in sources if s != "origin/main"]
        if len(non_main) >= 2:
            collisions[n] = sources
        elif non_main and "origin/main" in sources:
            collisions[n] = sources
    return collisions


def next_free_number(claim_map: ClaimMap) -> int:
    """Monotonic counter convention: smallest number strictly above every claim seen."""
    return (max(claim_map) + 1) if claim_map else 1


def format_report(claim_map: ClaimMap, collisions: ClaimMap, free: int) -> str:
    lines = [f"Next free scar number: W{free}"]
    if collisions:
        lines.append("")
        lines.append(f"COLLISION — {len(collisions)} number(s) claimed by more than one source:")
        for n in sorted(collisions):
            lines.append(f"  W{n}: {', '.join(collisions[n])}")
    else:
        claimed = ", ".join(f"W{n}" for n in sorted(claim_map)[-5:]) or "(none)"
        lines.append(f"No collisions. Most recent claimed numbers: {claimed}")
    return "\n".join(lines)


def run_lint(main_numbers: list[int], pr_claims: dict[str, list[int]]) -> tuple[int, str]:
    """Pure orchestration: claim set -> (exit_code, human report). No I/O."""
    claim_map = compute_claim_map(main_numbers, pr_claims)
    collisions = find_collisions(claim_map)
    free = next_free_number(claim_map)
    report = format_report(claim_map, collisions, free)
    exit_code = 1 if collisions else 0
    return exit_code, report


def _run(cmd: list[str], **kwargs) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        raise LintOperationalError(
            f"command failed (rc={result.returncode}): {' '.join(cmd)}\n{result.stderr.strip()}"
        )
    return result.stdout


def gather_live_claim_data(repo: str, file: str) -> tuple[list[int], dict[str, list[int]]]:
    """origin/main headings + every open PR's added headings for `file`, via git+gh."""
    main_text = _run(["git", "show", f"origin/main:{file}"], cwd=REPO_ROOT)
    main_numbers = parse_heading_numbers(main_text)

    pr_list = json.loads(
        _run(
            [
                "gh", "pr", "list", "--repo", repo,
                "--state", "open", "--json", "number", "--limit", "500",
            ]
        )
    )

    pr_claims: dict[str, list[int]] = {}
    for entry in pr_list:
        n = entry["number"]
        # gh pr diff does not accept a pathspec ("accepts at most 1 arg(s)");
        # the files API's per-file .patch is the scoped equivalent.
        patch = _run(
            [
                "gh", "api", f"repos/{repo}/pulls/{n}/files",
                "--jq", f'.[] | select(.filename == "{file}") | .patch',
            ]
        )
        numbers = parse_added_heading_numbers_from_patch(patch)
        if numbers:
            pr_claims[f"PR #{n}"] = numbers
    return main_numbers, pr_claims


def gather_fixture_claim_data(fixture_path: Path) -> tuple[list[int], dict[str, list[int]]]:
    """Offline/test path: `{"main": "<markdown>", "prs": {"<label>": "<patch>"}}`."""
    data = json.loads(fixture_path.read_text())
    main_numbers = parse_heading_numbers(data.get("main", ""))
    pr_claims = {
        source: parse_added_heading_numbers_from_patch(patch)
        for source, patch in data.get("prs", {}).items()
    }
    return main_numbers, pr_claims


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"default {DEFAULT_REPO}")
    parser.add_argument("--file", default=DEFAULT_FILE, help=f"default {DEFAULT_FILE}")
    parser.add_argument(
        "--fixture", type=Path, default=None,
        help="JSON fixture ({'main':..., 'prs':{...}}) — bypasses git/gh entirely",
    )
    parser.add_argument(
        "--next-only", action="store_true",
        help="print only 'W<n>' to stdout (report still goes to stderr on collision)",
    )
    args = parser.parse_args(argv)

    try:
        if args.fixture:
            main_numbers, pr_claims = gather_fixture_claim_data(args.fixture)
        else:
            main_numbers, pr_claims = gather_live_claim_data(args.repo, args.file)
    except LintOperationalError as exc:
        print(f"OPERATIONAL ERROR — claim set incomplete, cannot trust a result:\n{exc}", file=sys.stderr)
        return 2

    exit_code, report = run_lint(main_numbers, pr_claims)

    if args.next_only:
        claim_map = compute_claim_map(main_numbers, pr_claims)
        print(f"W{next_free_number(claim_map)}")
        if exit_code:
            print(report, file=sys.stderr)
    else:
        print(report)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
