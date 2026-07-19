#!/usr/bin/env python3
"""Docs Audit — generate DOCS_INVENTORY.md from a walk of docs/**/*.md.

Rules (first match wins):
  1. ARCHIVED if path starts with docs/archive/
  2. ARCHIVED (orphan) — split into a structural half and a time-crossing half:
     2a. structurally eligible: refs_in == 0 AND not in whitelist (pure tree fact)
     2b. TIME-CROSSING (`as_of > orphan_eligible_on`, strict — reproduces the
         pre-P3-prime `mtime_days > orphan_days` threshold exactly) — ONLY evaluated in write
         modes (--regen-only/--apply/default), NEVER in --check. --check carries
         forward a PRIOR flip (recorded as `orphan_flipped_on` in the previously
         committed inventory) but never invents a new one — see P3-prime below.
  3. STALE if broken_links > 0 OR DOCSYNC drift OR member of a duplicate cluster
  4. LIVE otherwise

Mtime is derived from `git log` (last commit touching the file), not from
`os.stat().st_mtime`, because filesystem mtime is reset by git checkout and
CI `actions/checkout`. Untracked files fall back to stat.

P3-prime (2026-07-17, research/operations/2026-07-17-push-pipeline-optimization-spec.md
§P3): the `inventory-check` PR gate used to flip a doc LIVE->ARCHIVED purely on
wall-clock (`mtime_days > orphan_days`, evaluated fresh against `datetime.now()`
on every run) — so an UNRELATED PR could turn red the day a totally different
doc's age crossed the 90-day mark (2x on #2509, again on #2592; docs-guardian
inventory-check "marcisce col calendario"). The cure: `--check` NEVER calls
`date.today()`/`datetime.now()` for classification purposes — it verifies only
DETERMINISTIC per-tree facts (`last_touched_date`, `orphan_eligible_on`, both
pure functions of git history + orphan_days arithmetic — no "today" anywhere).
The actual TIME-CROSSING decision (has a doc's `orphan_eligible_on` passed?) is
made ONLY by write-mode callers (the scheduled `docs-inventory-refresh.yml`
organ), which stamp `orphan_flipped_on` the first time a doc crosses — a
provenance marker `--check` can verify by DATE-vs-DATE comparison (both stored,
zero wall-clock) rather than by re-deriving "is it archived yet" itself. A doc
whose eligibility passed but was never organ-flipped stays at its last known
STATUS forever under `--check` — never a source of PR-gate drift.

See docs/superpowers/specs/2026-04-24-docs-hygiene-design.md for the full spec.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
DOCSYNC_BLOCK_RE = re.compile(
    r"<!--\s*DOCSYNC:([A-Z_]+)_START\s*-->(.*?)<!--\s*DOCSYNC:\1_END\s*-->",
    re.DOTALL,
)


@dataclass
class DocRow:
    path: str
    status: str = "LIVE"
    mtime_days: int = 0
    refs_in: int = 0
    broken: int = 0
    drift: bool = False
    cluster: str | None = None
    action: str = "—"
    # P3-prime deterministic facts (pure functions of git tree history + orphan_days
    # arithmetic — never of "today"). Empty string for rows that short-circuit before
    # fact computation (Rule 1: already under docs/archive/).
    last_touched_date: str = ""
    orphan_eligible_on: str = ""
    # Provenance marker: set ONLY by a write-mode run (the refresh organ) the first
    # time a doc crosses eligibility, then carried forward unchanged by every later
    # run (including --check). None means "never organ-flipped" — a doc showing
    # STATUS=ARCHIVED via the orphan rule WITHOUT this set is inconsistent (guilt).
    orphan_flipped_on: str | None = None


@dataclass
class ClusterDef:
    key: str
    members: List[str]
    canonical: str


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", default=".", help="Repo root (default: .)")
    p.add_argument(
        "--orphan-days",
        type=int,
        default=90,
        help="Orphan threshold in days (default 90).",
    )
    p.add_argument(
        "--whitelist",
        action="append",
        default=[],
        help="Repo-relative path exempt from orphan archival. Repeatable.",
    )
    p.add_argument(
        "--cluster",
        action="append",
        default=[],
        help="Cluster definition: key:member1,member2,...:canonical. Repeatable.",
    )
    p.add_argument(
        "--docsync-key",
        action="append",
        default=[],
        help="Override DOCSYNC key expected value: KEY:value. Repeatable.",
    )
    p.add_argument(
        "--check",
        action="store_true",
        help="Compare with committed inventory; exit 1 on drift.",
    )
    p.add_argument(
        "--as-of",
        default=None,
        metavar="YYYY-MM-DD",
        help=(
            "Override 'today' for the orphan-eligibility TIME-CROSSING decision "
            "in write modes (--regen-only/--apply/default); defaults to the real "
            "date when omitted. Deterministic-testing knob only — mutually "
            "exclusive with --check, which NEVER consults wall-clock (P3-prime: "
            "the merge gate verifies only tree-deterministic facts — the "
            "scheduled refresh organ owns the time-crossing decision)."
        ),
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="Physically git mv orphans to docs/archive/. Default: dry-run.",
    )
    p.add_argument(
        "--regen-only",
        action="store_true",
        help=(
            "Explicit, self-documenting alias for the default (no --apply) "
            "inventory-regeneration mode: rewrites docs/DOCS_INVENTORY.md "
            "content only, never touches docs/archive/. Mutually exclusive "
            "with --apply and --check. Use this when you only want the "
            "table refreshed and do NOT want orphan git-mv side effects."
        ),
    )
    p.add_argument("--quiet", action="store_true", help="No stdout on success.")
    p.add_argument("--json", action="store_true", help="Emit stats JSON on stdout.")
    p.add_argument(
        "--trusted-ref",
        default="origin/main",
        metavar="REMOTE/BRANCH",
        help=(
            "Where --check reads PRIOR orphan-flip provenance from (P3-prime "
            "BLOCKER-2 fix, red-team 2026-07-18). NEVER the working tree in "
            "--check mode: that file IS the PR candidate's own content, so a "
            "PR could forge or delete orphan_flipped_on markers and a gate "
            "that only re-derives its own self-consistency would pass. "
            "Ignored outside --check (write modes trust the local working "
            "tree, which in the organ's context is a fresh checkout of main "
            "anyway). Default origin/main; override only for testing."
        ),
    )
    args = p.parse_args()
    if args.regen_only and args.apply:
        raise SystemExit("--regen-only and --apply are mutually exclusive.")
    if args.regen_only and args.check:
        raise SystemExit(
            "--regen-only and --check are mutually exclusive "
            "(--check never writes; --regen-only always writes)."
        )
    if args.check and args.as_of:
        raise SystemExit(
            "--check and --as-of are mutually exclusive: --check NEVER consults "
            "wall-clock (P3-prime), so overriding 'today' for it is a contradiction "
            "in terms — it would smuggle a time-crossing decision back into the "
            "merge gate. Use --as-of only with a write mode."
        )
    if args.as_of:
        try:
            date.fromisoformat(args.as_of)
        except ValueError:
            raise SystemExit(f"--as-of must be YYYY-MM-DD, got: {args.as_of!r}")
    return args


def parse_clusters(raw: List[str]) -> List[ClusterDef]:
    clusters: List[ClusterDef] = []
    for r in raw:
        parts = r.split(":")
        if len(parts) != 3:
            raise SystemExit(
                f"Invalid --cluster spec (need key:members:canonical): {r}"
            )
        key, members_csv, canonical = parts
        members = [m.strip() for m in members_csv.split(",") if m.strip()]
        if canonical not in members:
            raise SystemExit(
                f"Cluster {key}: canonical {canonical} not in members {members}"
            )
        clusters.append(ClusterDef(key=key, members=members, canonical=canonical))
    return clusters


def parse_docsync_keys(raw: List[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for r in raw:
        if ":" not in r:
            raise SystemExit(f"Invalid --docsync-key (need KEY:value): {r}")
        k, v = r.split(":", 1)
        out[k] = v
    return out


def print_check_delta(
    inventory_path: Path,
    old_content: str,
    new_content: str,
    *,
    diff_limit: int = 200,
) -> None:
    """Emit a compact diff when --check finds inventory drift."""
    print(
        "docs_audit: docs/DOCS_INVENTORY.md is out of date; "
        f"regenerate with python {Path(__file__).as_posix()}",
        file=sys.stderr,
    )
    diff = list(
        difflib.unified_diff(
            old_content.splitlines(),
            new_content.splitlines(),
            fromfile=f"committed/{inventory_path.as_posix()}",
            tofile=f"generated/{inventory_path.as_posix()}",
            lineterm="",
        )
    )
    if len(diff) > diff_limit:
        diff = diff[:diff_limit]
        diff.append(f"... diff truncated after {diff_limit} lines ...")
    for line in diff:
        print(line, file=sys.stderr)


def walk_docs(repo: Path) -> List[Path]:
    """Return docs/**/*.md files visible to git, excluding DOCS_INVENTORY.md.

    "Visible to git" = tracked OR untracked-but-not-gitignored. Files matched
    by .gitignore are excluded so that local dev machines (which may carry
    historical .md leftovers from pre-current-gitignore eras) match CI's
    fresh clone exactly. Falls back to filesystem rglob when git is missing.
    """
    docs_root = repo / "docs"
    if not docs_root.is_dir():
        return []
    try:
        tracked = subprocess.run(
            ["git", "ls-files", "docs/"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "docs/"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return sorted(
            p for p in docs_root.rglob("*.md") if p.name != "DOCS_INVENTORY.md"
        )
    seen: set[str] = set()
    paths: List[Path] = []
    for line in (tracked + untracked).splitlines():
        rel = line.strip()
        if (
            not rel
            or not rel.endswith(".md")
            or rel.endswith("DOCS_INVENTORY.md")
            or rel in seen
        ):
            continue
        seen.add(rel)
        paths.append(repo / rel)
    return sorted(paths)


def compute_refs_in(repo: Path, target: Path) -> int:
    """Count other .md files (in docs/ + reference root files) that contain target's basename."""
    basename = target.name
    # Scan roots: docs/** and a handful of root files. Skip the file itself + archive dest.
    # Use walk_docs() (git-aware) so candidates match local↔CI exactly.
    candidates: List[Path] = [p for p in walk_docs(repo) if p != target]
    for root_name in (
        "CLAUDE.md",
        "INDEX.md",
        "SYMBIOSIS.md",
        "VADEMECUM.md",
        "AGENTS.md",
        "GEMINI.md",
        "AUTONOMOUS_OPS.md",
    ):
        rp = repo / root_name
        if rp.is_file() and rp != target:
            candidates.append(rp)
    apps_root = repo / "apps"
    if apps_root.is_dir():
        for p in apps_root.glob("*/README.md"):
            if p != target:
                candidates.append(p)
    count = 0
    for c in candidates:
        try:
            if basename in c.read_text(encoding="utf-8", errors="ignore"):
                count += 1
        except OSError:
            continue
    return count


INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def _strip_code_regions(content: str) -> str:
    """Remove fenced code blocks (```...```) and inline backtick spans
    (`...`) so example links inside code samples are not treated as real
    markdown links. Cheap and good-enough for our audit — not a full parser.
    """
    out: List[str] = []
    in_fence = False
    for line in content.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            # Strip inline `code` spans within the line.
            out.append(INLINE_CODE_RE.sub("", line))
    return "\n".join(out)


def compute_broken_links(repo: Path, doc: Path) -> int:
    """Count markdown links to local files that do not exist. URLs/anchors skipped.
    Links inside fenced code blocks are ignored (they are examples, not real).
    """
    try:
        raw = doc.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return 0
    content = _strip_code_regions(raw)
    broken = 0
    for match in LINK_RE.finditer(content):
        target = match.group(1).strip()
        # Skip URLs and pure anchors
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        # Strip anchor part
        target_path = target.split("#", 1)[0].split("?", 1)[0]
        if not target_path:
            continue
        resolved = (doc.parent / target_path).resolve()
        try:
            resolved.relative_to(repo.resolve())
        except ValueError:
            # Outside repo → skip
            continue
        if not resolved.exists():
            broken += 1
    return broken


def ensure_full_git_history(repo: Path) -> None:
    """Expand shallow clones before deriving semantic mtimes from git history."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--is-shallow-repository"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (subprocess.SubprocessError, OSError):
        return
    if result.returncode != 0 or result.stdout.strip() != "true":
        return
    fetch = subprocess.run(
        ["git", "-C", str(repo), "fetch", "--unshallow", "--quiet", "--no-tags"],
        capture_output=True,
        text=True,
        check=False,
    )
    if fetch.returncode != 0:
        details = fetch.stderr.strip() or fetch.stdout.strip() or "unknown error"
        raise SystemExit(
            "docs_audit: repository has shallow git history, so path mtimes "
            "are unreliable. Run `git fetch --unshallow --no-tags` before "
            f"`scripts/docs_audit.py`. git fetch said: {details}"
        )


def compute_last_commit_date(repo: Path, doc: Path) -> date:
    """The date `doc` was last touched, preferring git history over os.stat().

    This is the P3-prime SHARED PRIMITIVE: a PURE function of the git tree (or,
    for an untracked file, of that file's own stat mtime — inherent to "when was
    this new/uncommitted file last modified", not a "today" lookup). It never
    calls `datetime.now()`/`date.today()` itself, so both `compute_mtime_days()`
    (cosmetic, wall-clock-relative) and `orphan_eligible_on` (deterministic,
    tree-only) can share ONE git-log call while staying independently correct
    for their very different purposes — see module docstring.

    Filesystem mtime is reset by `git checkout`, `git worktree add`, and CI
    `actions/checkout` — so `os.stat().st_mtime` lies inside a worktree. Use
    `git log -1 --format=%ct` on the file for the true semantic date. Fall back
    to `os.stat()` when the file is untracked (new, uncommitted) or git is
    absent.
    """
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "log",
                "-1",
                "--format=%ct",
                "--",
                str(doc.relative_to(repo)),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        stdout = result.stdout.strip()
        if result.returncode == 0 and stdout:
            commit_ts = int(stdout)
            return datetime.fromtimestamp(commit_ts, tz=timezone.utc).date()
    except (subprocess.SubprocessError, ValueError, OSError):
        pass
    # Fallback for untracked files or when git is unavailable.
    return datetime.fromtimestamp(doc.stat().st_mtime, tz=timezone.utc).date()


def compute_mtime_days(repo: Path, doc: Path) -> int:
    """Age of `doc` in days, relative to the REAL current date.

    Cosmetic/informational column only (rendered in the table for humans, and
    masked as `<mtime>` by `strip_volatile()` before any `--check` comparison —
    see render_inventory()/main()). Classification NEVER uses this value —
    orphan eligibility is decided from `orphan_eligible_on` (deterministic,
    tree-only) instead. Safe to keep wall-clock-relative because it is never
    compared for gate purposes.
    """
    return (
        datetime.now(tz=timezone.utc).date() - compute_last_commit_date(repo, doc)
    ).days


def compute_drift(doc: Path, expected_keys: Dict[str, str]) -> bool:
    """True if doc contains a DOCSYNC block whose enclosed value != expected_keys[key]."""
    if not expected_keys:
        return False
    try:
        content = doc.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    for match in DOCSYNC_BLOCK_RE.finditer(content):
        key = match.group(1)
        body = match.group(2).strip()
        if key in expected_keys and expected_keys[key] not in body:
            return True
    return False


def _parse_inventory_table(content: str) -> Dict[str, Dict[str, str]]:
    """Parse the '## Files' markdown table into {path: {header_name: cell_value}}.

    Matches columns by HEADER NAME (not positional index), so it survives future
    column reordering/additions without silently misreading a cell. Tolerant by
    design: returns {} if the table is missing/malformed (first-ever run, or a
    hand-edit that broke structure) — callers must treat that as "no prior
    state to carry forward", never crash the gate on an unparseable table (the
    regular content-diff in --check still catches a genuinely broken table).
    """
    lines = content.splitlines()
    header_idx = None
    headers: List[str] = []
    for i, line in enumerate(lines):
        if line.startswith("| File "):
            headers = [h.strip() for h in line.strip().strip("|").split("|")]
            header_idx = i
            break
    if header_idx is None:
        return {}
    out: Dict[str, Dict[str, str]] = {}
    for line in lines[header_idx + 2 :]:  # skip header row + alignment row
        if not line.startswith("| "):
            break  # table ended
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        row = dict(zip(headers, cells))
        path = row.get("File")
        if path:
            out[path] = row
    return out


def parse_prev_flipped(content: str) -> Dict[str, str]:
    """{path: orphan_flipped_on} for every row in `content` that has a real
    (non-placeholder) flip date. This is the sole channel through which a
    PRIOR organ-flip survives into the next run (write OR --check) — see
    classify()'s Rule 2 and the module docstring's P3-prime note. An empty/
    missing table (first run) yields {} — the deliberately fail-closed "no doc
    is archived-via-orphan until the organ has actually said so" bootstrap.
    """
    table = _parse_inventory_table(content)
    out: Dict[str, str] = {}
    for path, row in table.items():
        flipped = row.get("orphan_flipped_on", "—")
        if flipped and flipped != "—":
            out[path] = flipped
    return out


def read_trusted_prev_flipped(repo: Path, trusted_ref: str = "origin/main") -> Dict[str, str]:
    """Read prior orphan-flip provenance from a TRUSTED ref — NEVER the PR's
    own working-tree copy of docs/DOCS_INVENTORY.md.

    P3-prime BLOCKER-2 (red-team 2026-07-18, generator!=grader, gate-gameable
    finding): `main()` used to build `prev_flipped` via
    `parse_prev_flipped(old_content)` where `old_content` was read straight
    from `repo/docs/DOCS_INVENTORY.md` — under `--check` in CI, THAT FILE IS
    THE PR CANDIDATE'S OWN CHECKOUT. Because `--check`'s final verdict is
    "does a fresh render match old_content", and `prev_flipped` was ALSO
    derived from that same `old_content`, the gate only ever verified
    SELF-consistency: a PR author could hand-edit the table to invent a flip
    that never happened (prematurely archiving/timestamp-forging a doc) or
    delete one that did (silently resurrecting a doc the organ legitimately
    archived) and a fresh render would reproduce the forged/deleted state
    right back — `--check` would pass either way. This function closes that
    hole: provenance for `--check` is re-derived from `trusted_ref` (a ref
    the PR branch does not control), independent of whatever the working
    tree currently says.

    Write modes (--regen-only/--apply/default) do NOT call this — see
    classify()'s docstring: there, the local working tree IS trusted (the
    scheduled organ always runs from a fresh checkout of main, so
    docs/DOCS_INVENTORY.md at invocation time already equals `trusted_ref`'s
    content, before this run's own regen overwrites it in place).

    Explicitly `git fetch` before resolving `trusted_ref` — a plain
    `actions/checkout` with `fetch-depth: 0` does NOT reliably leave
    `origin/main` resolvable in THIS repo's CI: empirically hit before
    (.github/workflows/adversarial-review-gate.yml:40, "merge-base with HEAD
    is unreachable -> fatal: no merge base ... seen live"); the proven fix
    pattern already used elsewhere in this repo is an explicit
    `git fetch origin main` (.github/workflows/organ-conformance.yml:94).

    Fail-closed by design: if `trusted_ref` cannot be resolved at all (bad
    remote, unreachable network, wrong branch name), this raises
    RuntimeError — it NEVER silently returns {} as a fallback. {} looks
    IDENTICAL to the legitimate "no docs/DOCS_INVENTORY.md exists on that ref
    yet" bootstrap case (see below) and would incorrectly tell every already
    -organ-ARCHIVED doc "no prior flip on record", letting Rule 2 fall
    through and silently resurrect it — exactly the forgery this function
    exists to prevent, just via infrastructure failure instead of malice.

    A *resolvable* ref whose docs/DOCS_INVENTORY.md doesn't exist yet (first
    run ever, before that file was first committed to main) legitimately
    returns {} — indistinguishable in effect from parse_prev_flipped()'s own
    "empty/missing table" bootstrap contract.

    NOT fail-closed for "this directory isn't a git checkout at all" — that
    is legitimate {} too, matching this file's existing "git preferred, no-
    git/stat-fallback tolerated" philosophy (module docstring: "Untracked
    files fall back to stat"). This can never happen in real CI (a genuine
    `actions/checkout` always produces a real git repo — an attacker
    controls file CONTENT, never whether the workflow's own checkout step
    ran), so it is not an exploitable escape hatch; it only matches plain-
    directory test fixtures elsewhere in this file that deliberately avoid
    git to exercise the stat-mtime fallback path.
    """
    is_git = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if is_git.returncode != 0:
        return {}
    remote, sep, branch = trusted_ref.partition("/")
    if not sep or not remote or not branch:
        raise RuntimeError(
            f"docs_audit: --trusted-ref {trusted_ref!r} must be shaped "
            "REMOTE/BRANCH (e.g. origin/main)."
        )
    fetch = subprocess.run(
        ["git", "-C", str(repo), "fetch", remote, branch, "--quiet"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    # Fetch failure is not automatically fatal by itself — a ref that already
    # resolves locally (prior fetch, offline dev repo with a tracked
    # origin/main) is still trustworthy. The rev-parse below is the real
    # gate: it is what actually determines fail-closed vs proceed.
    resolve = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"{trusted_ref}^{{commit}}"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if resolve.returncode != 0:
        fetch_err = fetch.stderr.strip() or fetch.stdout.strip() or "(no output)"
        raise RuntimeError(
            f"docs_audit --check: cannot resolve trusted ref {trusted_ref!r} "
            f"for orphan-flip provenance (git fetch said: {fetch_err}). "
            "Refusing to silently fall back to the PR's own working-tree "
            "copy of docs/DOCS_INVENTORY.md — that would defeat the "
            "anti-forgery gate (P3-prime BLOCKER-2). Ensure the checkout "
            f"step can reach {remote!r} and that branch {branch!r} exists."
        )
    show = subprocess.run(
        ["git", "-C", str(repo), "show", f"{trusted_ref}:docs/DOCS_INVENTORY.md"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if show.returncode != 0:
        # Ref resolves fine; the FILE just doesn't exist on it (yet). Legit
        # {} — matches parse_prev_flipped()'s own bootstrap contract.
        return {}
    return parse_prev_flipped(show.stdout)


def _flip_is_still_valid(carried: str, last_touched: date) -> bool:
    """MAJOR-5 fix (red-team 2026-07-18, semantic regression): a carried-
    forward `orphan_flipped_on` is valid ONLY if the doc has not been
    touched since that flip — `last_touched_date <= orphan_flipped_on`. A
    doc archived on day X, then edited/resurrected on day Y > X (still
    zero inbound refs at classify()-time, e.g. mid-edit before new
    references land), must NOT stay ARCHIVED forever just because a stale
    provenance marker says so — that is exactly the wall-clock-independent
    "pure tree fact" the P3-prime design promises: a flip's validity is
    itself re-derived from tree state (last_touched vs. the flip date),
    never re-asserted blindly. No wall-clock consulted here at all — both
    sides of the comparison are already-computed tree facts.

    Fail CLOSED on a malformed `carried` value (unparseable date): treat it
    as invalid rather than raising and aborting the whole run over one bad
    row — the safe direction is "don't blindly trust it", matching
    BLOCKER-2's philosophy. The outer --check diff still catches this case
    generally (a malformed carried date changes this doc's rendered row,
    which the stale_delta comparison in main() will flag).
    """
    try:
        carried_date = date.fromisoformat(carried)
    except ValueError:
        return False
    return last_touched <= carried_date


_AS_OF_UNSET = object()  # sentinel: "caller didn't specify" != "caller wants None"


def classify(
    doc: Path,
    repo: Path,
    orphan_days: int,
    whitelist: List[str],
    clusters: List[ClusterDef],
    expected_keys: Dict[str, str],
    *,
    as_of: date | None = _AS_OF_UNSET,  # type: ignore[assignment]  # sentinel, see below
    prev_flipped: Dict[str, str] | None = None,
) -> DocRow:
    """Classify one doc. `as_of` and `prev_flipped` govern the ONLY wall-clock-
    sensitive branch (orphan time-crossing, Rule 2b below):

      - `as_of` OMITTED entirely (legacy/direct callers — e.g. apply_moves()'s
        own test harness, which calls classify() outside of main()'s CLI
        dispatch): resolves to the REAL current date. Preserves this
        function's pre-P3-prime behavior byte-for-byte for any caller that
        doesn't know about the new --check contract, so tests exercising
        apply_moves()/classify() directly need no changes.
      - `as_of=None` EXPLICITLY (the --check / merge-gate contract, set ONLY
        by main() when args.check is true): the time-crossing decision is
        NEVER evaluated. A doc can only be ARCHIVED-via-orphan here by
        CARRYING FORWARD a flip already recorded in `prev_flipped` — i.e.
        already committed by a prior write-mode (organ) run. No new flip is
        ever invented by this call shape, so nothing that changes only because
        calendar time passed can flip a `--check` verdict (P3-prime). This is
        a DELIBERATE, explicit opt-in by main() — never the silent default —
        so the merge-gate safety property is a conscious choice at the one
        call site that matters, not something a refactor could accidentally
        drop by trimming an "unused" default argument.
      - `as_of=<a real date>` (write modes — --regen-only/--apply/default,
        called by the scheduled refresh organ): if a doc is structurally
        orphan-eligible and NOT already in `prev_flipped`, and
        `as_of > orphan_eligible_on` (strict — see Rule 2b above), this call
        stamps a FRESH `orphan_flipped_on = as_of` — the one and only place
        in this file that turns "today" into a status change.

    `prev_flipped` should be sourced from the CURRENTLY-COMMITTED
    docs/DOCS_INVENTORY.md (parse_prev_flipped() on its content) BEFORE this
    run overwrites it — see main().
    """
    if as_of is _AS_OF_UNSET:
        as_of = datetime.now(tz=timezone.utc).date()
    prev_flipped = prev_flipped or {}
    rel = str(doc.relative_to(repo))
    row = DocRow(path=rel)

    # Rule 1: already archived
    if rel.startswith("docs/archive/"):
        row.status = "ARCHIVED"
        return row

    last_touched = compute_last_commit_date(repo, doc)
    row.last_touched_date = last_touched.isoformat()
    eligible_on = last_touched + timedelta(days=orphan_days)
    row.orphan_eligible_on = eligible_on.isoformat()
    row.mtime_days = compute_mtime_days(repo, doc)
    row.refs_in = compute_refs_in(repo, doc)
    row.broken = compute_broken_links(repo, doc)
    row.drift = compute_drift(doc, expected_keys)

    # Cluster membership
    for cl in clusters:
        if rel in cl.members:
            row.cluster = cl.key
            if rel == cl.canonical:
                row.action = f"keep (canonical of {cl.key})"
            else:
                row.action = f"archive (superseded by {cl.canonical})"
            row.status = "STALE"
            # Cluster membership always wins over LIVE — short-circuit after setting
            return row

    # Rule 2: orphan — split (see docstring above + module docstring P3-prime).
    # 2a. Structural eligibility is a pure tree fact: no inbound refs, not
    #     whitelisted. Deterministic, safe to evaluate in --check too.
    structurally_eligible = row.refs_in == 0 and rel not in whitelist
    if structurally_eligible:
        carried = prev_flipped.get(rel)
        if carried and _flip_is_still_valid(carried, last_touched):
            # 2b-carry: a prior write-mode run already flipped this doc, AND
            # the doc has not been re-touched since (MAJOR-5 fix) —
            # reproduce that fact unchanged. No wall-clock read here at all.
            row.orphan_flipped_on = carried
        elif as_of is not None and as_of > eligible_on:
            # 2b-fresh: TIME-CROSSING, write-mode only (as_of is None under
            # --check, so this branch is structurally unreachable from the
            # merge gate — see classify()'s docstring). Strict `>`, not `>=`,
            # is DELIBERATE: it exactly reproduces the pre-P3-prime rule
            # (`mtime_days > orphan_days`, i.e. strictly-more-than-N-days-old)
            # bit-for-bit — `(as_of - last_touched).days > orphan_days` ⟺
            # `as_of > last_touched + orphan_days days` ⟺ `as_of > eligible_on`.
            # Using `>=` here would silently move the trigger one calendar
            # day earlier than before — an unintended behavior drift outside
            # this change's scope (P3-prime is about DETERMINISM, not about
            # redefining the threshold).
            row.orphan_flipped_on = as_of.isoformat()
        if row.orphan_flipped_on:
            row.status = "ARCHIVED"
            row.action = f"archive: orphan, mtime={row.mtime_days}d, refs=0"
            return row
    # else: not (yet) archived via the orphan rule. Any `orphan_flipped_on`
    # from an earlier run is correctly NOT carried here (row keeps the
    # dataclass default None) — a doc that regained an inbound reference or
    # got whitelisted is "resurrected" purely from tree state, falling through
    # to Rule 3/4 below. No wall-clock needed for that direction either.

    # Rule 3: stale (broken links OR drift)
    if row.broken > 0 or row.drift:
        row.status = "STALE"
        reasons = []
        if row.broken > 0:
            reasons.append(f"{row.broken} broken link(s)")
        if row.drift:
            reasons.append("DOCSYNC drift")
        row.action = "fix: " + "; ".join(reasons)
        return row

    # Rule 4: LIVE
    if rel in whitelist:
        row.action = "whitelist"
    return row


def render_inventory(rows: List[DocRow], clusters: List[ClusterDef]) -> str:
    """Produce DOCS_INVENTORY.md content."""
    total = len(rows)
    by_status: Dict[str, int] = {"LIVE": 0, "STALE": 0, "ARCHIVED": 0}
    for r in rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1

    drift_n = sum(1 for r in rows if r.drift)
    broken_n = sum(1 for r in rows if r.broken > 0)
    orphan_n = sum(1 for r in rows if r.action.startswith("archive: orphan"))

    ts = time.strftime("%Y-%m-%d %H:%M %Z")

    out: List[str] = []
    out.append("# Documentation Inventory")
    out.append("")
    out.append(f"_Auto-generated by `scripts/docs_audit.py`. Last run: {ts}_")
    out.append("")
    out.append("## Summary")
    out.append("")
    out.append("| Status   | Count | % |")
    out.append("|----------|-------|---|")
    for st in ("LIVE", "STALE", "ARCHIVED"):
        cnt = by_status.get(st, 0)
        pct = (100 * cnt / total) if total else 0
        out.append(f"| {st:<8} | {cnt:>5} | {pct:.0f}% |")
    out.append("")
    out.append(
        f"**Drift:** {drift_n} · **Broken links:** {broken_n} · **Orphans:** {orphan_n}"
    )
    out.append("")
    out.append("## Files")
    out.append("")
    out.append(
        "_`last_touched_date` / `orphan_eligible_on` / `orphan_flipped_on` are P3-prime "
        "deterministic facts (pure functions of git tree history — never of 'today'). "
        "`inventory-check` verifies these; only the scheduled `docs-inventory-refresh.yml` "
        "organ ever writes a fresh `orphan_flipped_on`. See docs_audit.py module docstring._"
    )
    out.append("")
    out.append(
        "| File | Status | mtime_days | last_touched_date | orphan_eligible_on | orphan_flipped_on | refs_in | broken | drift | cluster | action |"
    )
    out.append(
        "|------|--------|-----------:|--------------------|---------------------|--------------------|--------:|-------:|-------|---------|--------|"
    )
    # MAJOR-7 fix (red-team 2026-07-18): a doc path containing a literal '|'
    # corrupts the Markdown row it's written into (an extra cell), and the
    # symmetric parser (_parse_inventory_table) silently `continue`s past any
    # row whose cell-count doesn't match the header — the row, and any
    # orphan-flip provenance it carried, simply vanishes from
    # parse_prev_flipped() on the next run. That's not a one-time glitch: it
    # makes --check PERMANENTLY red for that doc (fresh classify() can no
    # longer see its own prior flip). Refused LOUD at generation instead of
    # silently escaped: no doc in this repo legitimately needs a literal pipe
    # in its path, and a hand-rolled escape/unescape pair is itself exactly
    # the kind of parser surface this repo's guard-over/under-match superscar
    # (#3) keeps re-biting on — simpler to make the input impossible.
    EXPECTED_COLUMNS = 11  # File|Status|mtime_days|last_touched_date|orphan_eligible_on|orphan_flipped_on|refs_in|broken|drift|cluster|action
    for r in rows:
        if "|" in r.path:
            raise SystemExit(
                f"docs_audit: doc path contains a literal '|' — {r.path!r}. "
                "This would corrupt the Markdown inventory table (MAJOR-7, "
                "red-team 2026-07-18) and is refused rather than escaped: "
                "rename the file."
            )
        drift_s = "yes" if r.drift else "no"
        cluster_s = r.cluster or "—"
        action_s = r.action
        last_touched_s = r.last_touched_date or "—"
        eligible_s = r.orphan_eligible_on or "—"
        flipped_s = r.orphan_flipped_on or "—"
        row_line = (
            f"| {r.path} | {r.status} | {r.mtime_days} | {last_touched_s} | "
            f"{eligible_s} | {flipped_s} | {r.refs_in} | {r.broken} | "
            f"{drift_s} | {cluster_s} | {action_s} |"
        )
        # Defense-in-depth: catch ANY cell (not just r.path) that smuggled a
        # pipe in — e.g. action_s can embed another doc's path
        # (f"archive (superseded by {cl.canonical})") via a --cluster arg.
        if row_line.count("|") != EXPECTED_COLUMNS + 1:
            raise SystemExit(
                "docs_audit: internal error — rendered row for "
                f"{r.path!r} has {row_line.count('|')} pipe-delimited "
                f"boundaries, expected {EXPECTED_COLUMNS + 1}. Refusing to "
                "emit a corrupted table row (MAJOR-7 defense-in-depth)."
            )
        out.append(row_line)
    out.append("")

    # Details sections (only if relevant)
    stale_by_cluster: Dict[str, List[DocRow]] = {}
    for r in rows:
        if r.cluster:
            stale_by_cluster.setdefault(r.cluster, []).append(r)
    if stale_by_cluster:
        out.append("## STALE details")
        out.append("")
        for cl in clusters:
            members_in_cluster = stale_by_cluster.get(cl.key, [])
            if not members_in_cluster:
                continue
            out.append(f"### `{cl.key}` cluster")
            out.append(f"Canonical: `{cl.canonical}`")
            archive_candidates = [m for m in cl.members if m != cl.canonical]
            if archive_candidates:
                out.append(
                    f"Archive candidates: {', '.join('`' + a + '`' for a in archive_candidates)}"
                )
            out.append("")

    broken_rows = [r for r in rows if r.broken > 0]
    if broken_rows:
        out.append("### Broken links")
        for r in broken_rows:
            out.append(f"- `{r.path}`: {r.broken} broken link(s)")
        out.append("")

    orphan_rows = [r for r in rows if r.action.startswith("archive: orphan")]
    if orphan_rows:
        out.append(f"### Orphans (mtime>{0}d AND refs_in==0)")
        for r in orphan_rows:
            out.append(f"- `{r.path}` (mtime={r.mtime_days}d, zero inbound refs)")
        out.append("")

    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


def apply_moves(repo: Path, rows: List[DocRow], use_git: bool = True) -> int:
    """Move files whose action starts with 'archive' into docs/archive/YYYY-MM-<slug>/. Return moved count.

    Sources are grouped by their original subdirectory under docs/ (root
    docs/*.md files form their own group) and each group is issued as ONE
    batched `git mv <sources...> <dest-subdir>` call, rather than one
    subprocess per file. This closes the interruption window that produced
    the 2026-07-07 near-miss: a mid-loop timeout on a per-file subprocess
    left some `git mv` calls applied and others not, and — because the
    working tree was already dirty from earlier moves — a subsequent partial
    `git add` staged byte-duplicate copies under docs/archive/ instead of
    clean renames (fixed in commit e6c5526696). Batching per group means the
    operation is all-or-nothing per group at the git-mv step.

    Preserving the subdirectory under the archive slug (rather than a single
    flat destination directory for every source) avoids a fatal `git mv`
    collision when two orphans from different docs/ subdirectories share a
    basename — e.g. docs/FOO.md and docs/architecture/FOO.md both moving
    into one flat docs/archive/<slug>/ would collide on FOO.md. Confirmed by
    a failed --apply run and fixed by hand (preserving subpaths) in #2309;
    this closes the gap so future runs don't need a manual workaround.
    """
    slug = time.strftime("%Y-%m-orphans")
    dest_root = repo / "docs" / "archive" / slug
    docs_root = repo / "docs"

    groups: Dict[Path, List[Path]] = {}
    for r in rows:
        if not r.action.startswith("archive: orphan"):
            continue
        src = repo / r.path
        if not src.exists():
            continue
        try:
            rel_dir = src.parent.relative_to(docs_root)
        except ValueError:
            rel_dir = Path(".")
        groups.setdefault(rel_dir, []).append(src)

    if not groups:
        return 0

    moved = 0
    for rel_dir, sources in groups.items():
        dest = dest_root if rel_dir == Path(".") else dest_root / rel_dir
        dest.mkdir(parents=True, exist_ok=True)
        if use_git:
            subprocess.run(
                ["git", "-C", str(repo), "mv", *[str(s) for s in sources], str(dest)],
                check=True,
            )
        else:
            for src in sources:
                src.rename(dest / src.name)
        moved += len(sources)
    return moved


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    ensure_full_git_history(repo)
    whitelist = args.whitelist
    clusters = parse_clusters(args.cluster)
    expected_keys = parse_docsync_keys(args.docsync_key)

    # P3-prime: read the CURRENTLY-COMMITTED inventory (if any) BEFORE
    # regenerating — needed for the post-hoc diff (`old_content` below,
    # unconditionally the working tree: --check's whole job is to compare a
    # fresh render against exactly what's checked in, forgery-detection
    # included).
    inventory_path = repo / "docs" / "DOCS_INVENTORY.md"
    old_content = (
        inventory_path.read_text(encoding="utf-8") if inventory_path.exists() else ""
    )

    # `prev_flipped` (orphan-flip PROVENANCE fed into classify()) is a
    # DIFFERENT read, deliberately NOT always the same as `old_content` above
    # — BLOCKER-2 fix (red-team 2026-07-18): under --check, sourcing
    # provenance from the working tree let a PR forge/delete its own
    # orphan_flipped_on markers and pass, because the gate only ever
    # re-derived self-consistency against that same file. --check MUST read
    # provenance from a ref the PR branch does not control
    # (read_trusted_prev_flipped, fail-closed — see its docstring). Write
    # modes keep trusting the local working tree (the organ's own fresh
    # checkout of main, already equal to the trusted ref at this point).
    if args.check:
        prev_flipped = read_trusted_prev_flipped(repo, args.trusted_ref)
    else:
        prev_flipped = parse_prev_flipped(old_content)

    # `as_of` is the ONLY place `main()` decides whether "today" may be
    # consulted at all. `--check` is the merge gate: it NEVER gets an as_of,
    # full stop — structurally incapable of inventing a fresh orphan flip
    # (parse_args() already rejects `--check --as-of` as a contradiction).
    # Write modes get either the caller's `--as-of` override (deterministic
    # testing) or the real date (production default).
    as_of: date | None
    if args.check:
        as_of = None
    elif args.as_of:
        as_of = date.fromisoformat(args.as_of)
    else:
        as_of = datetime.now(tz=timezone.utc).date()

    docs = walk_docs(repo)
    rows = [
        classify(
            d,
            repo,
            args.orphan_days,
            whitelist,
            clusters,
            expected_keys,
            as_of=as_of,
            prev_flipped=prev_flipped,
        )
        for d in docs
    ]

    # A "flip this run" = a row whose orphan_flipped_on is now set AND differs
    # from what was previously recorded for that path (i.e. brand new this
    # run — carried-forward flips are, by construction, identical to
    # prev_flipped and never appear here). Deliberately NOT rendered into
    # docs/DOCS_INVENTORY.md itself (see docs_inventory_regen.sh / workflow
    # comment) — a session-relative counter embedded in the COMPARED content
    # would reintroduce exactly the instability this design eliminates: a
    # --check regen always computes 0 flips (as_of=None), so if the last
    # write-mode regen had baked "N>0" into the committed file, --check would
    # forever disagree with it. Surfaced only via stderr + --json instead.
    flips_this_run = [
        r.path for r in rows if r.orphan_flipped_on and prev_flipped.get(r.path) != r.orphan_flipped_on
    ]
    if flips_this_run and not args.check:
        print(
            f"docs_audit: advanced {len(flips_this_run)} flip(s), eligibility "
            "recomputed: " + ", ".join(flips_this_run),
            file=sys.stderr,
        )

    new_content = render_inventory(rows, clusters)

    # Normalise volatile fields before comparing committed vs. rendered:
    #   * "Last run: …" — wall-clock timestamp, changes every run
    #   * mtime_days column in the file table — increments daily for every
    #     row because git commit-mtime grows with calendar time, even if
    #     no doc was touched. Without stripping this, `--check` returns 1
    #     on every PR touching docs/** the day after the last regen.
    # P3-prime note: last_touched_date / orphan_eligible_on / orphan_flipped_on
    # (columns 4-6, added alongside mtime_days) are DELIBERATELY NOT stripped
    # here — they are stable/deterministic (pure functions of git history, or
    # a carried-forward provenance date), so any real difference in them IS
    # meaningful drift the gate must catch. Only mtime_days (wall-clock-
    # relative, cosmetic) gets masked.
    def strip_volatile(s: str) -> str:
        out: List[str] = []
        for line in s.splitlines():
            if "Last run:" in line:
                continue
            line = re.sub(r"mtime=\d+d", "mtime=<mtime>d", line)
            # File table rows look like:
            #   | path | STATUS | <int> | <date> | <date> | <date-or-—> | <int> | <int> | yes/no | cluster | action |
            # mtime_days is column 3 (1-indexed, UNCHANGED position — the new
            # P3-prime columns were inserted AFTER it) — replace with a
            # placeholder so daily drift doesn't trip the comparison. Header
            # row ("File | Status | mtime_days | …") is preserved verbatim.
            if line.startswith("| ") and "|" in line[2:] and "mtime_days" not in line:
                parts = line.split("|")
                # Expected layout: ['', ' path ', ' STATUS ', ' mtime_days ',
                #                   ' last_touched_date ', ' orphan_eligible_on ',
                #                   ' orphan_flipped_on ', ' refs_in ', ' broken ',
                #                   ' drift ', ' cluster ', ' action ', ''].
                # Skip the alignment row "|------|...".
                if len(parts) >= 9 and "---" not in line:
                    parts[3] = " <mtime> "
                    line = "|".join(parts)
            out.append(line)
        return "\n".join(out)

    old_normalized = strip_volatile(old_content)
    new_normalized = strip_volatile(new_content)
    stale_delta = new_normalized != old_normalized

    if args.json:
        payload = {
            "total": len(rows),
            "live": sum(1 for r in rows if r.status == "LIVE"),
            "stale": sum(1 for r in rows if r.status == "STALE"),
            "archived": sum(1 for r in rows if r.status == "ARCHIVED"),
            "drift": sum(1 for r in rows if r.drift),
            "broken": sum(1 for r in rows if r.broken > 0),
            "orphans": sum(1 for r in rows if r.action.startswith("archive: orphan")),
            # P3-prime: ephemeral, session-relative — NEVER written into
            # docs/DOCS_INVENTORY.md itself (see comment above flips_this_run).
            "flips_this_run": len(flips_this_run),
            "flipped_paths": flips_this_run,
            "files": [
                {
                    "path": r.path,
                    "status": r.status,
                    "mtime_days": r.mtime_days,
                    "last_touched_date": r.last_touched_date,
                    "orphan_eligible_on": r.orphan_eligible_on,
                    "orphan_flipped_on": r.orphan_flipped_on,
                    "refs_in": r.refs_in,
                    "broken": r.broken,
                    "drift": r.drift,
                    "cluster": r.cluster,
                    "action": r.action,
                }
                for r in rows
            ],
        }
        print(json.dumps(payload, indent=2))

    if args.check:
        if stale_delta and not args.quiet:
            print_check_delta(inventory_path, old_normalized, new_normalized)
        return 1 if stale_delta else 0

    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_path.write_text(new_content, encoding="utf-8")

    if args.apply:
        moved = apply_moves(repo, rows)
        if not args.quiet:
            print(f"Moved {moved} orphan files to docs/archive/", file=sys.stderr)

    if not args.quiet and stale_delta:
        print(f"Inventory updated: {inventory_path}", file=sys.stderr)

    return 1 if stale_delta else 0


def _run_and_map_exit_code(main_fn=main) -> int:
    """BLOCKER-3 fix (red-team 2026-07-18): exit code 1 was OVERLOADED to
    mean two different things — "ran fine, content changed" (main()'s own
    `return 1 if stale_delta else 0`, intentional) and "crashed" (any
    uncaught exception, which Python's default top-level handler also turns
    into exit 1). Callers that swallow "expected drift" via `|| true`
    (scripts/docs_inventory_regen.sh) could not tell those apart and
    silently swallowed genuine crashes too — an audit that raises becomes a
    silent 0-flips no-op, workflow stays green, the inventory rots with a
    green liveness guardian on top. Fix: a genuine crash now maps to exit 2,
    a code `main()` itself never returns — SystemExit (the
    argparse/parse_args()/ensure_full_git_history() usage-error path, which
    already carries its own deliberate code) is re-raised UNCHANGED, never
    remapped.

    Factored out of the `if __name__ == "__main__":` guard specifically so
    it is unit-testable with an injected `main_fn` (a real crash via
    subprocess would work too, but has no clean trigger via legitimate CLI
    inputs alone — this keeps the exit-code CONTRACT itself directly
    testable without needing to manufacture one).
    """
    try:
        return main_fn()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — top-level crash boundary; must not vanish
        print(f"docs_audit: CRASHED — {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(_run_and_map_exit_code())
