#!/usr/bin/env python3
"""Docs Audit — generate DOCS_INVENTORY.md from a walk of docs/**/*.md.

Rules (first match wins):
  1. ARCHIVED if path starts with docs/archive/
  2. ARCHIVED (orphan) — split into a structural half and a time-crossing half:
     2a. structurally eligible: refs_in == 0 AND not in whitelist AND not a
         directory index (pure tree fact — see _is_directory_index)
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
from pathlib import Path, PurePosixPath
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
            "date when omitted (see --gate-consistent for a safer omitted-case "
            "default in PR-side contexts). Deterministic-testing knob only — "
            "mutually exclusive with --check, which NEVER consults wall-clock "
            "(P3-prime: the merge gate verifies only tree-deterministic facts — "
            "the scheduled refresh organ owns the time-crossing decision), and "
            "with --gate-consistent (pick one: a specific date, or 'never "
            "invent one')."
        ),
    )
    p.add_argument(
        "--gate-consistent",
        action="store_true",
        help=(
            "Write-mode (--regen-only/--apply/default) opt-in that reproduces "
            "--check's exact verdict-producing computation (as_of=None, "
            "provenance from --trusted-ref) but WRITES the result instead of "
            "comparing — i.e. 'regenerate exactly what the gate itself expects', "
            "never a fresh wall-clock-driven flip. Footgun fix (2026-07-19, PR "
            "#2626 landing incident): a write-mode regen run with NO --as-of "
            "used to silently default to real 'today', so a contributor running "
            "the plain PR-side regen path could commit fresh orphan_flipped_on "
            "stamps that --check (always as_of=None) would then reject as drift "
            "on the SAME PR. scripts/docs_inventory_regen.sh now passes this by "
            "default; the scheduled refresh organ (docs-inventory-refresh.yml) "
            "opts OUT via its own --organ flag, which passes --as-of instead — "
            "it is the one caller that IS supposed to invent fresh flips from "
            "real wall-clock. Mutually exclusive with --check (already "
            "definitionally this) and --as-of (pick one). docs_audit.py's own "
            "bare CLI default is UNCHANGED by this flag's existence — "
            "scripts/docs_guardian.sh and any other direct caller that doesn't "
            "pass it keeps the pre-existing real-'today' behavior."
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
            "Ignored outside --check/--gate-consistent (plain write modes "
            "trust the local working tree, which in the organ's context is "
            "a fresh checkout of main anyway). Default origin/main; override "
            "only for testing."
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
    if args.check and args.gate_consistent:
        raise SystemExit(
            "--check and --gate-consistent are mutually exclusive: --check "
            "already IS the gate-consistent computation (as_of=None, "
            "trusted-ref provenance) — --gate-consistent is the write-mode "
            "counterpart that reproduces the same thing but writes the file."
        )
    if args.as_of and args.gate_consistent:
        raise SystemExit(
            "--as-of and --gate-consistent are mutually exclusive: pick a "
            "specific date to invent fresh flips from (--as-of), or 'never "
            "invent one, carry forward from --trusted-ref' (--gate-consistent) "
            "— not both."
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
        "docs_audit: docs/DOCS_INVENTORY.md is out of date; regenerate with "
        "bash scripts/docs_inventory_regen.sh (gate-consistent by default — "
        "safe to run and commit on a PR branch; see --gate-consistent's "
        f"--help text for why a bare `python {Path(__file__).as_posix()}` "
        "invocation without it can commit content this same gate then rejects).",
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


REF_DELIM_CHARS = ("/", "`", "(")
# ASCII-tree box-drawing characters (U+251C/2514/2502/2500 — distinct from the
# ASCII pipe "|" used in Markdown tables, so a table cell never false-matches
# this). Verified live 2026-08-07: docs/wr3/README.md and
# docs/superpowers/specs/nlm-deep-research/PROGRESS.md both cite a sibling
# file this way inside a fenced ``` listing, e.g. "├── runbook-supervisor.md".
BOX_DRAWING_CHARS = "├└│─"

# Corpus-wide basename frequency, computed once per repo. Used ONLY by the
# uniqueness escape in `_has_bare_delimited_mention` (see there for why).
# Keyed by str(repo) rather than Path so the cache survives equal-but-distinct
# Path objects; process-lifetime only, and every caller in this file audits a
# single repo per run.
_BASENAME_COUNTS: Dict[str, Dict[str, int]] = {}


def _basename_is_unique(repo: Path, basename: str) -> bool:
    """True iff exactly one document in `reference_universe(repo)` carries
    `basename`.

    CORRECTED before shipping (2026-08-07). The first version counted
    `walk_docs(repo)` alone and defended it in this docstring: root reference
    files and `apps/*/README.md` "are only ever citers, never archival
    targets, so they cannot make a target ambiguous." That argument is wrong,
    and wrong in the same way as the bug this whole change exists to fix.
    Ambiguity is not a property of what can be ARCHIVED — it is a property of
    what a mention can MEAN. A root `GEMINI.md` is never an archival target
    and a reader still means it when they write `` `GEMINI.md` ``; counting
    only docs/** made `docs/ai/GEMINI.md` measure as the sole GEMINI.md in the
    tree, so every anchored mention of the ROOT file would have credited the
    docs one. Measured on the live corpus: exactly one basename has that
    shape — which is why the narrow count could look right indefinitely.

    Why this exists: the sibling rule (below) resolves a bare `` `X.md` ``
    against the citing file's own directory, which is correct when two
    different directories both contain an `X.md` — but WRONG when only one
    `X.md` exists anywhere, because then the mention is unambiguous no matter
    where it was written. Measured 2026-08-07: requiring siblinghood
    unconditionally dropped 15 LIVE documents to refs_in==0 whose only citer
    names them from another directory, e.g.
    `docs/archive/2026-07-orphans/NOTEBOOKLM_NOTEBOOK_ARCHITECTURE.md:4`
    ("> Dipende da: `NOTEBOOKLM_STRATEGY_4LLM_BRAINSTORM.md`" — a DECLARED
    dependency) and `docs/archive/2026-07-orphans/nlm-sources/STEERING_PROMPTS.md:5`
    ("Upload `KBLI_2025_VIDEO_SOURCE.md` as a source").

    This cannot reopen the over-match it sits next to, and the reason is
    structural rather than lucky: the over-match this guard exists to kill is
    a bare `README.md` crediting every README in the tree — and `README.md` is
    precisely the NON-unique case. Disease and cure separate on the same
    property. The anchor requirement (backtick / paren / box-drawing) still
    applies on top, so an undelimited prose mention is still rejected even
    when the basename is unique.
    """
    key = str(repo)
    counts = _BASENAME_COUNTS.get(key)
    if counts is None:
        counts = {}
        # reference_universe, NOT walk_docs: the question is "could this
        # mention mean a DIFFERENT document", and the citer set includes the
        # root reference files and apps/*/README.md. See its docstring for the
        # one basename that made the difference measurable.
        for p in reference_universe(repo):
            counts[p.name] = counts.get(p.name, 0) + 1
        _BASENAME_COUNTS[key] = counts
    return counts.get(basename, 0) == 1


# Marker used to recover a repo-relative path out of a home-relative one
# (`~/Desktop/nuzantara/docs/x.md` or `~/nuzantara/docs/x.md` — both forms
# occur in this repo's prose, depending on which machine's home layout the
# writer had). Text-based, not filesystem-based — this repo's own directory
# name, not the CWD at audit time.
_HOME_REPO_MARKER = "nuzantara/"


def _resolve_link_target(citing_file: Path, raw_target: str, repo: Path) -> str | None:
    """Resolve a markdown link's `(...)` target relative to the CITING file's
    own directory into a repo-relative POSIX path, or None for a URL/anchor-
    only/outside-repo target.

    Corrected 2026-08-07 (Defect D(iii), post-#3737 review): this function's
    own path-resolution ALGORITHM is the same one `compute_broken_links()`
    applies inline (join against `citing_file.parent`, `.resolve()`, then
    require containment under `repo`) — the two never disagree about what a
    GIVEN raw href string resolves to. But the two top-level CALLERS do not
    scan the same candidate text: `compute_broken_links()` runs
    `_strip_code_regions()` first, so a link written as a syntax EXAMPLE
    inside a fenced block or inline-code span is never even considered a
    real link there. `compute_refs_in()` deliberately does NOT strip code
    regions before scanning (see its own docstring) — this repo's real
    citations commonly live inside fenced ASCII-tree diagrams and backtick
    spans, and stripping them would silently re-open the exact under-match
    this file's `_has_bare_delimited_mention()` exists to close. So a link
    inside a fenced example CAN be treated as a real citation by
    `compute_refs_in()` while `compute_broken_links()` ignores the same text
    entirely — a deliberate, asymmetric divergence between the two
    functions' candidate sets, not a bug in this function's own resolution
    logic. The previous docstring claimed the two "never disagree about
    what a link points at" — true only for THIS function's own algorithm in
    isolation, false as a description of the two callers' overall behavior.
    Corrected outright rather than reworded into something vaguer: a
    weakened claim is still a claim, and this one was checked against both
    call sites, not just re-read for tone.
    """
    target = raw_target.strip()
    if not target or target.startswith(("http://", "https://", "mailto:", "#")):
        return None
    target_path = target.split("#", 1)[0].split("?", 1)[0]
    if not target_path:
        return None
    resolved = (citing_file.parent / target_path).resolve()
    try:
        rel = resolved.relative_to(repo.resolve())
    except ValueError:
        return None
    return rel.as_posix()


def _strip_home_prefix(token: str) -> str | None:
    """`~/Desktop/nuzantara/docs/x.md` / `~/nuzantara/docs/x.md` -> `docs/x.md`,
    or None if `token` isn't home-relative or names no repo-root marker.

    Live regression (2026-08-07): docs/audits/2026-05-02-cell-openclaw-
    brainstorm/00b_briefing_v2.md cites its 3 sibling response files by a
    fully-qualified `` `~/Desktop/nuzantara/docs/audits/.../NN_x_response.md` ``
    path. Neither the repo-root-relative nor the citing-file-relative
    resolution in `_has_bare_delimited_mention()` recognises a leading `~` —
    pathlib's `/` operator treats a value starting with `/` as an ABSOLUTE
    replacement of the left operand, not a join, so
    `(citing_file.parent / "/Desktop/nuzantara/...")` silently discards
    `citing_file.parent` entirely and resolves to a real filesystem path
    outside `repo`, which `relative_to(repo)` then rejects — a citation lost
    with no error. `rfind` (not `find`) picks the LAST `nuzantara/` segment,
    so a path with an incidental earlier occurrence of that word still
    resolves on the segment nearest the actual repo-relative suffix.
    """
    if not token.startswith("~/"):
        return None
    rest = token[2:]
    idx = rest.rfind(_HOME_REPO_MARKER)
    if idx == -1:
        return None
    return rest[idx + len(_HOME_REPO_MARKER) :]


def _trailing_boundary_ok(content: str, end: int) -> bool:
    """True if the text immediately after a basename match does not continue
    what looks like a longer filename (`README.mdx`, `README.md.bak`).

    A trailing "." is special-cased rather than rejected outright (Defect C
    fix, post-#3737 review, 2026-08-07): `README.md.bak` (period followed by
    more word characters — a real, different file) must still be rejected,
    but `docs/a/TARGET.md.` at the end of a sentence (period followed by
    whitespace/punctuation/end-of-string) must not — that period belongs to
    the SENTENCE, not the filename. The pre-fix rule rejected any trailing
    period unconditionally, so a bare (non-backticked) mention ending a
    sentence silently lost its citation while the identical backticked form
    (where a closing backtick, not a period, supplies the boundary) did not
    — an asymmetry with no basis in what a real citation looks like, caught
    by re-deriving this function's OWN guarantee against real prose rather
    than trusting the prior implementation's inline comment.
    """
    n = len(content)
    if end >= n:
        return True
    c = content[end]
    if c.isalnum() or c in "_-":
        return False
    if c == ".":
        nxt = content[end + 1] if end + 1 < n else ""
        return not nxt.isalnum()
    return True


def _enclosed_in_open_paren_same_line(content: str, idx: int) -> bool:
    """True if position `idx` sits inside an OPEN, unclosed "(" that starts
    earlier on the SAME LINE — e.g. "(see X.md)" or "(vedi X.md)": the
    basename is not immediately preceded by "(" (there is lead-in text like
    "see "/"vedi " in between), but it is still structurally inside a
    parenthetical — a real anchor, not accidental prose. Requires an actual
    open paren, so the guilt case ("the file README.md is a common
    convention", no parens anywhere on the line) still correctly returns
    False. Bounded to the current line only — a paren opened on a prior
    line is not "the same parenthetical" for this purpose.

    Live regression (2026-08-07): docs/superpowers/reviews/2026-04-21-
    partners-v1/POST-MERGE-deploy-runbook.md cites its sibling via
    "(see ASYA-withholding-rates-runbook.md)" and docs/superpowers/sessions/
    2026-04-17-strategic-8/MERGE-STRATEGY.md via "(vedi DOCKER-CLAUDE-
    CLI.md)" — in both, the character immediately before the basename is a
    plain space (from "see "/"vedi "), not "(" — the immediate-adjacency
    check alone does not see them. A hardcoded phrase list ("see"/"vedi")
    was deliberately rejected in favour of this structural check — this
    repo's guard-over-match superscar (#3, cicatrix-superscar.md) calls out
    exactly that shape ("escape-clause che tiene/scusa solo su UNA frase
    esatta") as its own recurring disease.
    """
    line_start = content.rfind("\n", 0, idx) + 1
    depth = 0
    for c in content[line_start:idx]:
        if c == "(":
            depth += 1
        elif c == ")" and depth > 0:
            depth -= 1
    return depth > 0


def _has_bare_delimited_mention(
    content: str,
    citing_file: Path,
    repo: Path,
    basename: str,
    target_rel_posix: str,
) -> bool:
    """Fallback for non-link citations: True iff `content` contains an
    occurrence of `basename` that is reference-anchored rather than an
    accidental substring.

    Anchoring rule (guard-over-match family #3 — see cicatrix-superscar.md
    §3 — every substring guard eventually needs both a guilt AND an
    innocence corpus, pinned here in test_docs_audit.py):
      - the character immediately BEFORE the match must be a real delimiter
        (`/`, a backtick, `(`, a box-drawing character, or whitespace that
        itself leads back to one of those — see below); this alone rejects
        the basename-inside-basename hole (ANTHROPIC_API_REFERENCE.md must
        never credit API_REFERENCE.md: the char before "API_REFERENCE.md"
        there is "_", not a delimiter).
      - the character immediately AFTER the match must not be a word
        character, and a trailing "." only survives if what follows it is
        NOT a word character either (`_trailing_boundary_ok` — Defect C fix,
        2026-08-07): "README.mdx" / "README.md.bak" still can't credit
        "README.md" by mere prefix, but a bare, non-backticked citation that
        happens to end a SENTENCE ("...docs/a/TARGET.md.") is no longer
        punished for it just because the backticked form isn't.
      - when the leading delimiter is "/", the full contiguous path token
        walked backward from the match (e.g. "docs/sub/README.md",
        "../sub/README.md", or "~/Desktop/nuzantara/docs/sub/README.md")
        must resolve to `target_rel_posix` under ONE of three conventions
        actually observed in this repo's prose: (a) repo-root-relative
        (writers paste the "docs/..." path they'd type from the repo root,
        regardless of where the citing file lives), (b) citing-file-
        relative, exactly like a real markdown link (so a backticked
        "../sibling.md" resolves against the CITING file's own directory,
        not the repo root — this is what makes a genuine sibling reference
        like `` `../assignment-mismatches-2026-04-20.md` `` count; a naive
        trailing-segment string match does NOT handle ".." and was measured
        to silently drop this exact real citation before the original
        #3737 fix), or (c) home-relative (`_strip_home_prefix` — a fully-
        qualified `~/Desktop/nuzantara/...` or `~/nuzantara/...` path, the
        form this repo's own audit-brainstorm docs use to cross-reference
        their siblings). Two different docs/**/README.md files must still
        not credit each other purely because both happen to end in
        "README.md" preceded by a slash — none of the three resolutions
        makes that happen, since none produces the OTHER file's actual
        path.
      - a BARE basename (no path prefix at all) is credited only if it
        resolves, SIBLING-style, against the CITING file's own directory
        (`_resolve_link_target(citing_file, basename, repo)` — i.e.
        `citing_file.parent / basename` must literally BE `target`). This
        replaces the #3737 original's "accept with no further check" for a
        backtick/`(`-preceded bare basename, which was an over-match found
        live 2026-08-07: a `` `README.md` `` mention anywhere in the repo,
        about ANY README, credited EVERY docs/**/README.md target
        regardless of directory (measured: all 14 docs/**/README.md rows
        sitting at near-identical refs_in, entirely from this hole — see
        compute_refs_in's docstring). The sibling requirement is what a
        bare mention actually means in this repo's prose: a doc names its
        OWN neighbour without spelling out the shared directory. Reached
        from four surface shapes, all sibling-anchored the same way:
          * immediately after a backtick or "(" (the original two, now
            resolved instead of blindly accepted);
          * immediately after (or, skipping whitespace, preceded by) a box-
            drawing character (`BOX_DRAWING_CHARS`) — an ASCII-tree child
            listing, e.g. "├── runbook-supervisor.md";
          * inside an unclosed "(" earlier on the same line
            (`_enclosed_in_open_paren_same_line` — "(see X.md)", "(vedi
            X.md)"), gated to when the immediately-preceding character is
            whitespace, so it only ever widens the two directly-adjacent
            cases to tolerate a short lead-in word, never bare undelimited
            prose (the guilt case has no enclosing paren at all).
        A bare, wholly UNDELIMITED prose mention ("the file README.md is a
        common convention") still matches none of these and is rejected —
        the one shape this fix exists to kill (see compute_refs_in's
        docstring for the measured impact of the broadening as a whole).
    """
    blen = len(basename)
    idx = 0
    while True:
        idx = content.find(basename, idx)
        if idx == -1:
            return False
        end = idx + blen
        if idx == 0 or not _trailing_boundary_ok(content, end):
            idx = end
            continue
        prev = content[idx - 1]

        if prev == "/":
            # Walk backward through path-token characters (incl. "." so a
            # leading "../" or "./" is captured whole, and "~" so a home-
            # relative prefix is captured whole too) to recover the full
            # cited path, then try all three resolutions described above.
            start = idx - 1
            while start > 0 and (
                content[start - 1].isalnum() or content[start - 1] in "_-./~"
            ):
                start -= 1
            token = content[start:end]
            # (a) repo-root-relative: the token IS the repo-relative path.
            if token.lstrip("/") == target_rel_posix:
                return True
            # (b) citing-file-relative: resolve against the citing file's
            # own directory, exactly like a real markdown link.
            if _resolve_link_target(citing_file, token, repo) == target_rel_posix:
                return True
            # (c) home-relative: strip a leading "~/.../nuzantara/" prefix.
            stripped = _strip_home_prefix(token)
            if stripped is not None and stripped == target_rel_posix:
                return True
            idx = end
            continue

        # Bare basename (no path prefix): find whether there is a real
        # anchor immediately before it — backtick, "(", or a box-drawing
        # character reached directly or by skipping back over whitespace
        # (tree indentation), or (whitespace-gated) an unclosed "(" earlier
        # on the line. Anything else (alnum, "_", punctuation with no
        # enclosing paren) is not an anchor — rejected, matching the
        # pre-#3737 guilt cases unchanged.
        bare_anchor = False
        if prev in ("`", "(") or prev in BOX_DRAWING_CHARS:
            bare_anchor = True
        elif prev in (" ", "\t"):
            j = idx - 1
            while j >= 0 and content[j] in " \t":
                j -= 1
            if j >= 0 and content[j] in BOX_DRAWING_CHARS:
                bare_anchor = True
            elif _enclosed_in_open_paren_same_line(content, idx):
                bare_anchor = True

        if bare_anchor:
            # (i) sibling: the bare name resolves, citing-file-relative, to
            # the target — the unambiguous case regardless of uniqueness.
            if _resolve_link_target(citing_file, basename, repo) == target_rel_posix:
                return True
            # (ii) entity escape: the name occurs exactly ONCE in the corpus,
            # so an anchored mention of it cannot mean anything else, even
            # written from another directory. See _basename_is_unique.
            if _basename_is_unique(repo, basename):
                return True
        idx = end
    return False


_ROOT_REFERENCE_FILES = (
    "CLAUDE.md",
    "INDEX.md",
    "SYMBIOSIS.md",
    "VADEMECUM.md",
    "AGENTS.md",
    "GEMINI.md",
    "AUTONOMOUS_OPS.md",
)

_UNIVERSE_CACHE: Dict[str, List[Path]] = {}


def reference_universe(repo: Path) -> List[Path]:
    """Every document this module can see: docs/** + the root reference files
    + apps/*/README.md.

    ONE definition, for the two questions that must agree about it:

      * `compute_refs_in` scans this set for CITERS of a target.
      * `_basename_is_unique` counts this set to decide whether a bare
        basename can mean anything but the target.

    They were written separately and diverged immediately: the uniqueness
    count used `walk_docs` alone (948 rows), so `docs/ai/GEMINI.md` measured
    as the only GEMINI.md in the corpus while a ROOT `GEMINI.md` sat right
    there in the citer set — an anchored `` `GEMINI.md` `` mention meaning the
    root file would have credited the docs one. Measured 2026-08-07: exactly
    one basename in the tree has that shape, which is precisely why a
    second definition could look correct for a long time.

    DECLARED LIMIT: `.md` files elsewhere in the repo (packages/, infra/,
    research/, .claude/) are NOT here, so a bare mention that means one of
    THOSE still reads as unique. That is the same universe `compute_refs_in`
    has always scanned — widening it is a separate, measurable change, not a
    thing to do silently while fixing the count.

    Cached per repo: both callers ask once per target, O(1000) times per run.
    """
    key = str(repo)
    cached = _UNIVERSE_CACHE.get(key)
    if cached is not None:
        return cached
    docs: List[Path] = list(walk_docs(repo))
    for root_name in _ROOT_REFERENCE_FILES:
        rp = repo / root_name
        if rp.is_file():
            docs.append(rp)
    apps_root = repo / "apps"
    if apps_root.is_dir():
        docs.extend(sorted(apps_root.glob("*/README.md")))
    _UNIVERSE_CACHE[key] = docs
    return docs


def compute_refs_in(repo: Path, target: Path) -> int:
    """Count other .md files (in docs/ + reference root files) that CITE
    `target` via a reference-anchored match: either (a) a markdown link
    `[...](...)` that resolves — exact repo-relative path equality — to
    `target`, or (b) a bare (non-link) mention delimiter-anchored per
    `_has_bare_delimited_mention` (see its docstring for the exact rule).

    Deliberately NOT a `basename in text` substring test: that inflated
    refs_in on any doc whose basename happens to be a SUFFIX of a longer
    basename or of an ordinary prose word — e.g. docs/API_REFERENCE.md was
    credited by every doc that merely wrote ANTHROPIC_API_REFERENCE.md,
    which never links or otherwise cites API_REFERENCE.md at all — and
    because refs_in==0 is half of orphan-archival eligibility (see
    classify()'s `structurally_eligible`), that inflation could mask a doc
    that should already be orphan-eligible, or — the sharper failure mode —
    the FIX for it could flip a large slice of genuinely-cited docs to
    refs_in==0 overnight if done too strictly.

    DECISION, pinned by the guilt/innocence corpus in test_docs_audit.py:
    an UNLINKED backticked/parenthesized/box-drawing/enclosed-paren bare
    filename (`` `README.md` ``, "├── README.md", "(see README.md)" — no
    path, no `[text](...)` syntax) DOES count as a citation, but ONLY when
    it resolves SIBLING-style against the citing file's own directory (see
    `_has_bare_delimited_mention`'s docstring for the exact rule and why —
    corrected 2026-08-07, post-#3737 review: the original "accept with no
    further check" for this shape was itself an over-match, measured live —
    a `` `README.md` `` mention anywhere in the repo credited EVERY
    docs/**/README.md target regardless of directory).

    UNIVERSE, corrected 2026-08-07 (Defect D(i), post-#3737 review): the
    prior text here said "979-file universe" for a refs_in>0/==0 count —
    979 is the CANDIDATE set size (row targets + the extra root reference
    files + apps/*/README.md, which are only ever CITERS, never targets
    themselves). The count that actually matters — how many of the ROWS
    `classify()` acts on sit at refs_in>0 — is over the ROW set, measured
    at 948 (`len(walk_docs(repo))`) on the same day. Re-measured on THIS
    exact implementation, same day, same row universe (948): the pre-#3737
    substring scan (`basename in text`, no anchoring at all) gives 530 rows
    at refs_in>0; this implementation gives 471. The fix, LIKE #3737's
    original, is a pure NARROWING of the substring scan — every anchored
    match (link-resolution, path-form, or sibling-resolved bare mention)
    necessarily contains `basename` as a literal substring too, so refs_in
    under this rule can never exceed the substring count for the same
    target: 0 rows moved OFF refs_in==0 relative to the substring scan,
    verified empirically on this exact 948-row run. See the PR body for the
    corpus-level archival-impact list (which specific docs newly sit at
    refs_in==0, and which of those are past their own orphan_eligible_on) —
    a point-in-time report, deliberately not duplicated as a number in this
    docstring, where it would go stale the next time the corpus changes
    without anyone re-measuring it (the exact failure this correction
    exists to fix). A bare, UNDELIMITED prose mention ("the file README.md
    is a common convention") does NOT count — that is the one shape this
    fix exists to kill.
    """
    basename = target.name
    target_rel_posix = target.relative_to(repo).as_posix()
    candidates: List[Path] = [p for p in reference_universe(repo) if p != target]
    count = 0
    for c in candidates:
        try:
            content = c.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        # Cheap pre-filter, safe under BOTH matching mechanisms below: a
        # markdown link can only resolve to `target` if its raw target text
        # contains `basename` as a literal substring (the resolved path's
        # own final component), and the delimited-mention fallback requires
        # a literal `basename` occurrence by construction. Skipping the
        # regex scan + path resolution for the (vast majority of) candidates
        # that don't even contain the substring is a pure speed win — this
        # repo's docs/** is O(1000) files, so compute_refs_in is called
        # O(files) times and each call previously re-scanned every OTHER
        # file; regex+resolve() on every pair measured ~3x slower than the
        # substring-only predecessor across the full corpus (2026-08-07).
        if basename not in content:
            continue
        cited = False
        for match in LINK_RE.finditer(content):
            if _resolve_link_target(c, match.group(1), repo) == target_rel_posix:
                cited = True
                break
        if not cited:
            cited = _has_bare_delimited_mention(content, c, repo, basename, target_rel_posix)
        if cited:
            count += 1
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


_DIRECTORY_INDEX_RE = re.compile(r"^(?:\d+[_-])?README\.md$")


def _is_directory_index(rel: str) -> bool:
    """True iff this doc is the INDEX of the directory it sits in.

    A directory index is reachable by its LOCATION, not by an inbound link:
    a reader who opens `docs/audits/<case>/` finds it without anyone having
    linked it. `refs_in == 0` is therefore the NORMAL state for this class,
    not evidence of orphanhood — and archiving one moves a folder's index out
    of the folder it documents, leaving the contents behind.

    Why this exemption exists NOW (2026-08-07): before the bare-mention fix
    (#3737 + the uniqueness escape next to it), every README in the tree was
    accidentally credited by any prose token `README.md` anywhere. Closing
    that substring hole removes an ACCIDENTAL protection from 13 docs. This
    function makes the protection explicit and intentional instead of letting
    a counter fix quietly endanger a class of doc it was never about.

    DECLARED LIMITS (what this deliberately does NOT recognise):
      - Only `README.md`, optionally carrying the repo's numeric ORDERING
        prefix (`00_README.md` in the wave dirs, where siblings are `01_*`,
        `02_*`). Nothing else: `INDEX.md`, `_index.md`, `OVERVIEW.md` are NOT
        treated as indexes here — if one of them ever needs it, it gets its
        own measurement and its own corpus row, not a widened regex.
      - Case-sensitive. This repo writes README uppercase; a lowercase
        `readme.md` would fall through and be judged like any other doc.
      - This exempts from ORPHAN archival only. A directory index with broken
        links or DOCSYNC drift is still STALE (Rule 3) and still reported.
    """
    return bool(_DIRECTORY_INDEX_RE.match(PurePosixPath(rel).name))


def archive_orphan_action(last_touched_date: str) -> str:
    """The `action` cell an orphan-archived row carries.

    Extracted so the string has exactly ONE author. `docs_inventory_blame.py`
    needs to recognise this cell to tell a real orphan flip from a hand-written
    one, and a second copy of the format there would be a second definition of
    the same fact — the divergence would be silent, because nothing compares
    the two spellings (scar #9: two writers of one field ⇒ the rule lives in
    one module).
    """
    return f"archive: orphan, last_touched={last_touched_date}, refs=0"


def orphan_flip_claim_is_legitimate(
    *,
    path: str,
    trusted_ref_has_prior_flip: bool,
    generated_refs_in: object,
    generated_eligible_on: str,
    committed_flipped_on: str,
    committed_refs_in: object,
    trusted_ref_ceiling_date: "date | None",
) -> bool:
    """Is a committed `orphan_flipped_on` claim one an honest run could produce?

    THE ONE definition of that question, called by both gates that ask it:
    `_tolerated_orphan_flip_paths()` below (the `--check` byte-diff path) and
    `docs_inventory_blame.py::_is_earned_flip` (the `inventory-check` blame
    path). It was extracted, not copied: the blame path's first version
    (2026-07-29) re-derived the rule from scratch and a cross-family red-team
    took it apart — it ignored `refs_in`, so ANY doc could be hand-marked
    ARCHIVED, and it had no upper bound, so `2099-12-31` passed. Everything it
    was missing was already solved here, hardened by the 2026-07-25 round. A
    weaker second copy of a guard is worse than no second guard, because the
    weaker one is the one an attacker uses.

    The four conditions are unchanged from that round — see
    `_tolerated_orphan_flip_paths`'s docstring for why each exists and which
    forgery direction it closes. Arguments are plain cells/flags so a caller
    holding only rendered markdown can ask the same question as a caller
    holding parsed `DocRow`s. Behaviour is preserved AT THE `--check` CALL SITE,
    which is what was verified (55/55): the helper's own contract is
    deliberately broader, because it stringifies and strips every value so a
    caller holding rendered cells can use it. Old code rejected a STRING
    `generated_refs_in="0"` and an INT `committed_refs_in=0`; this accepts both.
    Neither is reachable from `--check`, which passes an int and a stripped
    string respectively — but "behaviour-preserving" is a claim about the call
    site, not about the function, and the difference is written down rather than
    left for the next reader to discover.

    DECLARED LIMITS (true of this predicate at both call sites, recorded rather
    than silently inherited):

      * `eligible_on <= claimed` ALLOWS a flip dated exactly on the eligibility
        date, while `classify()` only flips when `as_of > eligible_on`
        (strict, deliberately — see its comment). So a claim one day early is
        tolerated. Tightening it is a semantic change to the 2026-07-25 round
        and is tracked separately; it is NOT silently altered here.
      * Whitelisting is not consulted. `classify()`'s structural eligibility is
        `refs_in == 0 AND not whitelisted AND not a directory index`; the
        whitelist half is not checkable from a rendered row. Measured on the
        live table 2026-07-29: zero whitelisted docs have `refs_in == 0`, so
        THAT gap is latent, not open.
        The directory-index half is NOT latent — measured 2026-08-07, 13 docs
        have `refs_in == 0` and are indexes — so it is consulted here rather
        than declared and left open: callers pass `path` and the predicate asks
        `_is_directory_index` itself. This was added WITH the exemption, not
        after it: a rule that stops `classify()` from producing a flip must
        also stop the gate from tolerating that flip when it is hand-written,
        or the exemption silently becomes a forgery surface for 13 docs.
      * THE LOWER BOUND IS TREE-DERIVED, AND THE TREE IS THE PR'S. The 2026-07-25
        round hardened the UPPER bound against `GIT_COMMITTER_DATE` forgery, and
        left the floor where it was: `orphan_eligible_on` is
        `last_touched + orphan_days`, and `last_touched` comes from
        `git log --format=%ct` on the branch under test. So an author who
        backdates the commit that adds an unreferenced doc can make it eligible
        immediately and claim a flip today; the claim is then genuinely below
        the trusted ceiling and every other cell agrees, so it is tolerated.
        Reachable from BOTH call sites, and pre-dating the extraction — closing
        it means giving eligibility a trusted source, which changes `classify()`
        itself. Recorded here, not fixed under a different mandate. Blast radius
        is bounded by `refs_in == 0`: the doc must be one nothing links to.
    """
    if trusted_ref_ceiling_date is None:
        return False  # no trustworthy ceiling — fail closed
    if trusted_ref_has_prior_flip:
        return False  # trusted-ref already records a flip here (direction b)
    if str(generated_refs_in).strip() != "0" or not str(generated_eligible_on).strip():
        return False  # not structurally orphan-eligible
    if _is_directory_index(str(path).strip()):
        # `classify()` can never flip a directory index, so no honest run could
        # have produced this claim. Asked HERE rather than at the two call
        # sites so the rule keeps one author (scar #9) — the callers supply an
        # identity, not a verdict.
        return False
    try:
        eligible_on = date.fromisoformat(str(generated_eligible_on).strip())
    except ValueError:
        return False
    claimed_raw = str(committed_flipped_on or "").strip()
    if claimed_raw in ("", "—"):
        return False  # nothing claimed — ordinary strict comparison applies
    try:
        claimed_date = date.fromisoformat(claimed_raw)
    except ValueError:
        return False  # unparseable claim — fail closed
    if not (eligible_on <= claimed_date <= trusted_ref_ceiling_date):
        return False  # premature or future-dated (direction a)
    if str(committed_refs_in).strip() != "0":
        return False  # committed side disagrees on the structural fact itself
    return True


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
    #     whitelisted, and not a directory index (reachable by LOCATION, so
    #     refs_in == 0 is its normal state — see _is_directory_index).
    #     Deterministic, safe to evaluate in --check too.
    structurally_eligible = (
        row.refs_in == 0 and rel not in whitelist and not _is_directory_index(rel)
    )
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
            # Absolute date, never a days-ago count: this string is RENDERED
            # into the tracked inventory, and "94d" becomes "95d" tomorrow with
            # no documentation having changed. See render_inventory()'s header
            # comment for the churn this caused.
            row.action = archive_orphan_action(row.last_touched_date)
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
    elif row.refs_in == 0 and _is_directory_index(rel):
        # Say WHY it survived with zero inbound refs, so a reader of the
        # inventory isn't left to guess whether the counter is broken.
        row.action = "keep (directory index)"
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

    # UTC date only — no clock time, no local %Z. The prior "%Y-%m-%d %H:%M %Z"
    # embedded the RUNNING MACHINE's timezone (fleet writes WITA, GitHub
    # runners write UTC) AND changed on every regen regardless of machine, so
    # any two branches that regenerated this generated-but-tracked file
    # collided on this line — a recurring conflict-treadmill (one whole PR,
    # #3334, was nothing but this line flipping WITA<->UTC). A same-day UTC
    # date makes two regenerations on the same day, on any machine, produce a
    # byte-identical file. `--check`'s strip_volatile() below already drops
    # the entire "Last run:" line unconditionally, so this format change is
    # invisible to the drift comparison.
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

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
    # NO clock-derived cell is rendered here. `mtime_days` used to be column 3
    # and it is why this generated-but-TRACKED file changed every single day:
    # measured on PR #3405, 633 of the 699 changed rows (90.6%) differed ONLY
    # in that integer going up by one, with no documentation having changed at
    # all. Two consequences, one root:
    #   * the scheduled refresh (twice daily) opened a PR on every run, because
    #     it decides with `git diff --quiet` on the RAW file — 1558 lines of
    #     which ~90% was clock churn;
    #   * any two branches that both regenerated collided on those 633 lines,
    #     the "conflict treadmill" #3334 was closed over.
    # `mtime_days` is also pure redundancy: `last_touched_date` right beside it
    # is the same fact in absolute form, and `orphan_eligible_on` is the
    # deadline it fed. A reader wanting "how old" subtracts; a file does not
    # have to rewrite itself nightly to tell them.
    # It stays on DocRow and still drives the orphan RULE (classify()) — this
    # is about what gets WRITTEN, not about what gets decided.
    out.append(
        "| File | Status | last_touched_date | orphan_eligible_on | orphan_flipped_on | refs_in | broken | drift | cluster | action |"
    )
    out.append(
        "|------|--------|--------------------|---------------------|--------------------|--------:|-------:|-------|---------|--------|"
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
    EXPECTED_COLUMNS = 10  # File|Status|last_touched_date|orphan_eligible_on|orphan_flipped_on|refs_in|broken|drift|cluster|action
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
            f"| {r.path} | {r.status} | {last_touched_s} | "
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
        out.append("### Orphans (past orphan_eligible_on AND refs_in==0)")
        for r in orphan_rows:
            # Absolute again — same reason as the table above.
            out.append(
                f"- `{r.path}` (last touched {r.last_touched_date}, zero inbound refs)"
            )
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
    if moved:
        # `reference_universe` and `_basename_is_unique` memoise the TREE, and
        # the tree just changed. Today nothing re-classifies after this call
        # (main() moves last), so this is not fixing a live bug — it is
        # refusing to make the caches depend on that call order staying true.
        # A stale universe would under-count citers and a stale uniqueness
        # count would credit a name that just became ambiguous, both silently.
        _UNIVERSE_CACHE.clear()
        _BASENAME_COUNTS.clear()
    return moved


def _read_committed_orphan_claims(content: str) -> Dict[str, Dict[str, str]]:
    """Parse the COMMITTED (old, working-tree/PR) inventory table into the
    handful of per-path fields the P3-prime-1a-surgical tolerance check
    (see `_tolerated_orphan_flip_paths` below) needs: `orphan_flipped_on`
    and `refs_in`.

    Deliberately a SEPARATE reader from `_parse_inventory_table()` (:524) —
    that helper serves an existing caller (DOCSYNC/prev-flip parsing) with
    a different contract; changing its behavior to also serve this new,
    narrower need was judged riskier than a second small reader (design
    discussion 2026-07-25, option 1a-surgical). Malformed/missing rows are
    simply absent from the returned dict — callers must treat an absent
    path as "nothing to tolerate", never as "tolerate by default" (fail
    toward strict comparison, matching this file's existing fail-closed
    posture elsewhere).
    """
    # Read by COLUMN NAME, never by index. The first version of this reader was
    # positional (`parts[6]`, `parts[7]`) and skipped the header row by testing
    # `"mtime_days" in line`. When the mtime_days column was removed (it made
    # this tracked file rewrite itself nightly — see render_inventory), BOTH of
    # those silently re-aimed: every index shifted by one, and the header row,
    # no longer containing the word, stopped being skipped and was parsed as a
    # data row. Neither failure raises; the function just answers about the
    # wrong columns, and this one feeds a TOLERANCE decision — the direction in
    # which being wrong is quietest.
    #
    # This still does NOT reuse _parse_inventory_table(): that helper serves a
    # different caller with a different contract, and the 2026-07-25
    # option-1a-surgical discussion judged changing it riskier than a second
    # small reader. What changes here is only HOW this reader addresses a cell.
    claims: Dict[str, Dict[str, str]] = {}
    lines = content.splitlines()
    header_idx: int | None = None
    headers: List[str] = []
    for i, line in enumerate(lines):
        if line.startswith("| File "):
            headers = [h.strip() for h in line.strip().strip("|").split("|")]
            header_idx = i
            break
    if header_idx is None:
        return claims  # no file table (or a hand-edit broke it) — tolerate nothing
    for line in lines[header_idx + 2 :]:  # skip the header row + alignment row
        if not line.startswith("| "):
            break  # table ended
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        row = dict(zip(headers, cells))
        path = row.get("File", "")
        # Fail toward strict comparison (docstring above): a row missing either
        # field yields no claim rather than an empty-string claim.
        if not path or "orphan_flipped_on" not in row or "refs_in" not in row:
            continue
        claims[path] = {
            "orphan_flipped_on": row["orphan_flipped_on"],
            "refs_in": row["refs_in"],
        }
    return claims


def _trusted_ref_tip_date(repo: Path, trusted_ref: str) -> date | None:
    """The commit date of `trusted_ref`'s own tip — NOT the PR's own commit
    metadata. One of two independent floors combined (via `max`) into
    Refinement 1's upper bound at the call site — see that combination's
    docstring in `main()` for why neither floor is used alone.

    `trusted_ref`'s tip is not under the PR's control: the PR branch cannot
    rewrite origin/main's history, and this run fetches `trusted_ref` fresh
    from the remote — the identical trust boundary `read_trusted_prev_
    flipped()` already established for flip provenance (BLOCKER-2,
    2026-07-18). Deliberately does NOT reuse `compute_last_commit_date()`
    (that helper reads the WORKING TREE's checked-out branch — see the
    cross-family finding this replaced, below).

    Returns None (never raises) if `trusted_ref` cannot be resolved; the
    call site falls back to the OTHER floor (real "now") rather than
    treating a resolution failure as fatal — this function only ever
    TIGHTENS the combined ceiling relative to "now alone" when it
    succeeds, so a failure degrading to "now alone" loses tightening, not
    safety.
    """
    remote, sep, branch = trusted_ref.partition("/")
    if not sep or not remote or not branch:
        return None
    subprocess.run(
        ["git", "-C", str(repo), "fetch", remote, branch, "--quiet"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    resolve = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"{trusted_ref}^{{commit}}"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if resolve.returncode != 0:
        return None
    result = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%ct", trusted_ref],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return datetime.fromtimestamp(int(result.stdout.strip()), tz=timezone.utc).date()
    except (ValueError, OSError):
        return None


def _tolerated_orphan_flip_paths(
    rows: List[DocRow],
    prev_flipped: Dict[str, str],
    committed_claims: Dict[str, Dict[str, str]],
    trusted_ref_ceiling_date: date | None,
) -> set:
    """Paths where `--check` tolerates a STATUS/`orphan_flipped_on`/action
    mismatch between the committed table and this run's fresh computation
    — P3-prime option 1a-surgical (2026-07-25).

    Mechanism A (proved on PR #3126, 2026-07-25): under `--check`,
    `classify()` can only carry an orphan flip FORWARD from `prev_flipped`
    (trusted-ref, `read_trusted_prev_flipped()`) — it never invents one.
    A PR introducing a genuinely NEW, never-before-recorded flip can
    therefore never match `--check`'s fresh computation, no matter how
    correctly it was produced or how fast the PR is checked: trusted-ref
    (main, pre-merge) cannot already contain a flip only that PR proposes.
    This is the ONE case this function tolerates.

    It does NOT touch `classify()` or `read_trusted_prev_flipped()` — the
    BLOCKER-2 anti-forgery carry-forward logic (2026-07-18 red-team) is
    completely unchanged. This function only widens what `--check`'s DIFF
    accepts as equivalent, and only for a path that passes ALL of:

      1. `prev_flipped` has NO entry for this path — trusted-ref has never
         recorded a flip here at all. If trusted-ref DOES have an entry,
         any mismatch is a potential resurrection/hiding attempt (BLOCKER-2
         direction b) and is NEVER tolerated, regardless of what the PR's
         own table claims.
      2. The fresh (this-run) row is structurally orphan-eligible:
         `refs_in == 0` AND `orphan_eligible_on` is set. A doc that isn't
         structurally eligible (e.g. `refs_in > 0`) must never reach this
         branch BY CONSTRUCTION — not via an incidental empty-string date
         comparison that could pass vacuously.
      3. The committed table's claimed `orphan_flipped_on` for this path is
         date-plausible: `orphan_eligible_on <= claimed <= trusted_ref_ceiling_date`.
         The upper bound blocks future-dating; the lower bound blocks
         premature-archival forgery (BLOCKER-2 direction a). Deliberately
         `trusted_ref_ceiling_date` — NOT a commit date read from the PR's
         own branch (see `_trusted_ref_tip_date()`'s docstring: a PR-branch
         commit date is exactly as attacker-controlled as the claim it
         would be bounding, via `GIT_COMMITTER_DATE` — a cross-family
         red-team finding against the first version of this fix,
         2026-07-25). A missing/unparseable claim, or a missing
         `trusted_ref_ceiling_date`, is never tolerated (fail closed).
      4. The committed table's claimed `refs_in` for this path is exactly
         "0" — the PR's own row must agree with the structural fact, not
         just assert a flip while disagreeing on why it would be eligible.

    Row PRESENCE (has this path been deleted from, or added to, one side
    only) is NOT decided here — main()'s comparison remains a whole-string
    diff over ALL rows, so a path missing from one side still produces a
    length/content mismatch regardless of anything in this set (verified
    empirically, see the accompanying tests: a deleted or fabricated row
    is caught independently of this tolerance list).
    """
    tolerated: set = set()
    if trusted_ref_ceiling_date is None:
        return tolerated
    for r in rows:
        claim = committed_claims.get(r.path)
        if claim is None:
            continue  # no row on the committed side — never tolerate (refinement 3)
        # The four refinements themselves now live in one place, shared with
        # the `inventory-check` blame path — see orphan_flip_claim_is_legitimate.
        if orphan_flip_claim_is_legitimate(
            path=r.path,
            trusted_ref_has_prior_flip=r.path in prev_flipped,
            generated_refs_in=r.refs_in,
            generated_eligible_on=r.orphan_eligible_on or "",
            committed_flipped_on=claim.get("orphan_flipped_on", ""),
            committed_refs_in=claim.get("refs_in", ""),
            trusted_ref_ceiling_date=trusted_ref_ceiling_date,
        ):
            tolerated.add(r.path)
    return tolerated


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
    # checkout of main, already equal to the trusted ref at this point) —
    # UNLESS --gate-consistent asks for the same trusted-ref provenance
    # --check itself uses (footgun fix, 2026-07-19: see --gate-consistent's
    # own --help text and PENDING-ARMS.md for the PR #2626 incident this
    # cures).
    #
    # `as_of` is the OTHER place `main()` decides whether "today" may be
    # consulted at all. `--check` is the merge gate: it NEVER gets an as_of,
    # full stop — structurally incapable of inventing a fresh orphan flip
    # (parse_args() already rejects `--check --as-of` as a contradiction).
    # `--gate-consistent` is the write-mode twin of that same guarantee:
    # deliberately, explicitly opted INTO (never a silent default swap for
    # EVERY write-mode caller — see docs_guardian.sh, which never asked for
    # this and must keep its pre-existing real-'today' behavior byte-for-
    # byte). Plain write modes with neither flag get either the caller's
    # `--as-of` override (deterministic testing / the scheduled organ) or
    # the real date (unchanged production default for any caller that
    # predates/doesn't know about --gate-consistent).
    as_of: date | None
    if args.check or args.gate_consistent:
        as_of = None
        prev_flipped = read_trusted_prev_flipped(repo, args.trusted_ref)
    elif args.as_of:
        as_of = date.fromisoformat(args.as_of)
        prev_flipped = parse_prev_flipped(old_content)
    else:
        as_of = datetime.now(tz=timezone.utc).date()
        prev_flipped = parse_prev_flipped(old_content)

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

    # P3-prime option 1a-surgical (2026-07-25, PR #3126 postmortem): the ONE
    # case Mechanism A makes categorically unsatisfiable by --check is a
    # genuinely NEW orphan flip trusted-ref has never recorded — see
    # `_tolerated_orphan_flip_paths()`'s own docstring for the full
    # mechanism and the 4 conditions that gate it. Computed ONLY under
    # --check (write modes never compare against old_content for pass/fail
    # purposes the way --check does, and never need this).
    #
    # `check_content` defaults to the ordinary strict `new_content` and is
    # ONLY replaced when --check finds a tolerable path. It is deliberately
    # a full RE-RENDER via classify() (below), not a hand-patch of the file
    # table's 3 columns — a per-cell mask was tried first and left the
    # Status Count/% summary table, the "**Orphans:** N" inline count, and
    # the "### Orphans" candidate-list section (all independently derived
    # from `rows` by render_inventory()) internally inconsistent with the
    # masked row, producing a real byte-diff there even though the specific
    # row was correctly tolerated — caught by
    # test_p3prime_1a_innocence_earned_unlanded_flip_passes_check on the
    # first build (2026-07-25). Re-deriving through classify()'s own
    # carry-forward branch (the same path P3F / MAJOR-5 already exercise)
    # keeps every derived field, and every aggregate render_inventory()
    # computes from them, correct BY CONSTRUCTION instead of asking this
    # function to separately reimplement each rendering surface.
    tolerated_orphan_paths: set = set()
    check_content = new_content
    if args.check:
        committed_claims = _read_committed_orphan_claims(old_content)
        # Refinement 1's upper bound is the LATER of two floors, NEITHER of
        # which the PR branch controls:
        #
        #   1. trusted_ref's own tip commit date (`_trusted_ref_tip_date`) —
        #      guards against a skewed/broken CI-runner clock.
        #   2. real "now" at check-time.
        #
        # Cross-family red-team finding (2026-07-25, Kimi K3) against the
        # FIRST version of this fix: using `compute_last_commit_date(repo,
        # inventory_path)` alone — `git log --format=%ct` against the PR's
        # OWN checked-out branch — is fully attacker-controlled via
        # `GIT_COMMITTER_DATE`. Demonstrated live: a PR claiming
        # `orphan_flipped_on=2099-01-01`, committed with
        # `GIT_COMMITTER_DATE=2099-06-01`, passed `--check` outright, and
        # the forged flip then survived as trusted provenance post-merge —
        # `_flip_is_still_valid()` has no upper bound, so the doc stayed
        # pinned ARCHIVED (immune to MAJOR-5 resurrection-by-edit) for 73
        # years, and the organ's `--apply` would physically `git mv` an
        # actively-edited doc into `docs/archive/` on the strength of it.
        #
        # `datetime.now()` closes this: it is the CI runner's own real
        # clock, never PR-branch-derived, so no commit-date forgery can
        # touch it. Using it here does NOT reintroduce the wall-clock
        # dependence P3-prime eliminates from `--check`'s CORE decision
        # (classify() still runs with as_of=None throughout — this value
        # only feeds a strictly ADDITIONAL widening-layer's sanity bound).
        # It is also provably monotonic-safe in the one direction P3-prime
        # actually forbids: a claim already `<= now` stays `<= now`
        # forever as real time advances, so this can only ever turn a
        # REJECTED claim into a TOLERATED one later (the date catching up
        # to an honest near-future claim) — never the reverse. The exact
        # instability P3-prime removes is a PASSING check going RED for
        # UNCHANGED content purely because time passed; this addition can
        # only go the other way (RED -> GREEN), which is benign by
        # construction, not a reintroduction of that bug.
        # Residual (team-lead, 2026-07-25, endorsing the fix): a PR could
        # still claim a date a few days into the real future and have it
        # rejected today, only to pass on a later re-check once real time
        # catches up. That is harmless BY CONSTRUCTION, not a narrower
        # version of the hole: it fails CI today and therefore never
        # merges today — there is no window in which a still-future claim
        # is ever accepted before its date has actually arrived.
        # `max()` with the trusted-ref floor costs nothing (real "now" is
        # never earlier than any past commit under a sane clock) and only
        # helps in the degenerate case of a broken CI-runner clock.
        trusted_ref_tip = _trusted_ref_tip_date(repo, args.trusted_ref)
        now_date = datetime.now(tz=timezone.utc).date()
        trusted_ref_ceiling_date = (
            max(trusted_ref_tip, now_date) if trusted_ref_tip else now_date
        )
        tolerated_orphan_paths = _tolerated_orphan_flip_paths(
            rows, prev_flipped, committed_claims, trusted_ref_ceiling_date
        )
        if tolerated_orphan_paths:
            print(
                f"docs_audit: tolerating {len(tolerated_orphan_paths)} unlanded "
                "orphan flip(s) not yet on trusted-ref: "
                + ", ".join(sorted(tolerated_orphan_paths)),
                file=sys.stderr,
            )
            # `tolerant_prev_flipped` only ever ADDS entries this run's
            # `_tolerated_orphan_flip_paths()` already proved tolerable on
            # top of the REAL trusted-ref provenance (`prev_flipped`) — it
            # never removes or alters an existing trusted entry. as_of stays
            # None, so Mechanism A (classify() can only carry a flip
            # FORWARD, never invent one) still holds unchanged: this cannot
            # be used to introduce a flip `_tolerated_orphan_flip_paths()`
            # itself would not already have validated.
            tolerant_prev_flipped = dict(prev_flipped)
            for p in tolerated_orphan_paths:
                tolerant_prev_flipped[p] = committed_claims[p]["orphan_flipped_on"]
            tolerant_rows = [
                classify(
                    d,
                    repo,
                    args.orphan_days,
                    whitelist,
                    clusters,
                    expected_keys,
                    as_of=None,
                    prev_flipped=tolerant_prev_flipped,
                )
                for d in docs
            ]
            check_content = render_inventory(tolerant_rows, clusters)

    # Normalise the one remaining volatile field before comparing committed
    # vs. rendered: "Last run: …", the generation stamp.
    #
    # There used to be a second entry here — the `mtime_days` column, which
    # incremented daily for every row and made `--check` return 1 on any PR
    # touching docs/** the day after the last regen. That was cured at the
    # SOURCE instead of here: render_inventory() no longer emits a
    # clock-derived cell at all, so there is nothing left to neutralize.
    # Masking it downstream was always the weaker half — the gate stopped
    # complaining, but the FILE still changed every day, which is what fed
    # both the twice-daily churn PR and the cross-branch conflicts.
    # P3-prime note: last_touched_date / orphan_eligible_on / orphan_flipped_on
    # are DELIBERATELY NOT stripped
    # here — they are stable/deterministic (pure functions of git history, or
    # a carried-forward provenance date), so any real difference in them IS
    # meaningful drift the gate must catch. STATUS/orphan_flipped_on/action
    # for a tolerated path are made to compare equal by rendering
    # `check_content` from `tolerant_rows` above, not by masking here — this
    # function only ever neutralizes wall-clock cosmetics, exactly as before
    # option 1a-surgical, so ordinary drift and both BLOCKER-2 forgery
    # directions are still caught byte-for-byte.
    def strip_volatile(s: str) -> str:
        # Only "Last run:" is dropped now, and even that is a same-day-stable
        # UTC date rather than a clock time.
        #
        # The two mtime normalizers that used to live here are GONE because
        # render_inventory() no longer emits anything for them to hide: the
        # `mtime_days` column and the `mtime=<N>d` fragments in the action /
        # Orphans lines were all replaced by absolute `last_touched_date`.
        # Removing the positional one is NOT cosmetic — it is required for
        # correctness. It blanked `parts[3]`, and with the column gone
        # `parts[3]` is now `last_touched_date`: leaving it would have made
        # this gate silently blind to every change in a column the comment
        # right above deliberately calls out as meaningful drift the gate must
        # catch. A masker that outlives the value it masked stops being dead
        # code the moment the layout shifts under it — it starts hiding its
        # neighbour (superscar #3, the UNDER-match direction).
        out: List[str] = []
        for line in s.splitlines():
            if "Last run:" in line:
                continue
            out.append(line)
        return "\n".join(out)

    old_normalized = strip_volatile(old_content)
    new_normalized = strip_volatile(check_content)
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
