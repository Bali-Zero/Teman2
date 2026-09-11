#!/usr/bin/env python3
"""lint_arm_probe.py — executable antidote for the autoMergeRequest null-ambiguity trap.

THE FINDING (measured 2026-08-29/30, PR #5275): GitHub's `autoMergeRequest` GraphQL
field reads null in (at least) three different states — a PR the merge queue has
ACCEPTED and is now processing (the request is CONSUMED, not disarmed), a PR the
queue EJECTED, and a PR that was genuinely never armed — and non-null in only one.
`mergeQueueEntry` (the per-PR authoritative field), its sibling boolean
`isInMergeQueue`, and the branch-level `mergeQueue(branch:...){entries}` snapshot
are the only POSITIVE probes: a PR is IN the queue *because* the request is live.
Reading `autoMergeRequest == null` as "disarmed, needs re-arming" therefore fires
precisely when arming SUCCEEDED — confirmed live on PR #5275 (`autoMergeRequest:
null` simultaneously with `mergeQueueEntry {state: QUEUED, position: 3}`, and
`gh pr merge --auto` on it refusing with "already queued to merge") and, per the
mandate that produced this lint, twice before in production (#4756, #5012: a
sentinel announced "ARM CONSUMED / re-arm needed" against a PR that was actually
`mergeQueueEntry.state = AWAITING_CHECKS, position 1`).

THE ANTIDOTE: this lint. A file that TESTS `autoMergeRequest` for truthiness/
nullness (a "decision position" — a `.get` lookup or bracket subscript keyed
on the literal field name, or a jq `== null` / `select(...)` filter on it)
must also reference one of the positive-probe markers — `mergeQueueEntry`,
`isInMergeQueue`, or `mergeQueue(` — somewhere in the SAME FILE. A file that only
REQUESTS the field (a `--json ...,autoMergeRequest` field list, or a GraphQL
mutation's return-selection) without ever testing it is not flagged — nothing
decides on it, so there is nothing to protect (mq.sh's confirm-step echo,
github_publisher.py's `_enable_auto_merge` mutation selection).

Detection classes:
  FAIL   — a decision-position `autoMergeRequest` line with NO positive-probe
           marker anywhere in the file, and no inline suppression marker on
           that line.
  (clean) — decision-position usage WITH a positive-probe marker in the same
           file, OR no decision-position usage at all.

Suppression marker (CONTENT-based, not a directory exemption — cicatrix #3/
W109, "an exemption keyed to where a file sits, rather than what it is, is
itself a scar"): a source line carrying the literal string
`lint-arm-probe:fixture` is a synthetic guilt/innocence sample embedded in
this lint's OWN test file, not real decision code, and is excluded entirely
(from both findings AND positive-probe detection). The marker sits on the
Python SOURCE line that DEFINES a fixture string constant — as a trailing
`#` comment, which Python discards at parse time and which therefore never
becomes part of the fixture TEXT a test hands to `scan_text()`. That is what
lets the guilt fixture still register as a finding *inside the unit test*
(the runtime string has no marker) while the static .py file that defines it
is invisible to this lint's own repo-wide scan (the source line does).
Nothing else may carry this marker — `scripts/tests/test_lint_arm_probe.py`
is the only tracked file that does
(`test_marker_appears_only_in_this_lints_own_test_file`).

Scope notes (deliberate): file-level, not function-level, co-occurrence. A
file whose own decision logic is safe only because a DIFFERENT file checks
queue membership before ever acting on its output (a "candidates" filter
piped into a caller that cross-references `mergeQueue(...)` before acting)
still reads `autoMergeRequest == null` as part of its own predicate, with
nothing in ITS file proving that null here means anything narrower than "not
armed" — so it FAILS this lint even when the full pipeline is safe today.
That is intentional, not a false positive: the safety property in that shape
lives in a caller/callee CONTRACT, not in the file itself, and a future
caller that skips the cross-check reintroduces the exact bug this lint
exists to catch. `scripts/ci/queue_rearm_population.sh` was exactly this
shape until 2026-08-31 (its awareness lived one file up, in
`scripts/ci/queue_rearm.sh`'s `mergeQueue(...)` cross-check) — it now carries
its own `mergeQueueEntry` co-occurrence and is no longer allowlisted;
see `scripts/ci/lint_queue_field_verdict.py`'s sibling ALLOWLIST (SHRINK-ONLY)
for the same file's now-obsolete waiver in that lint.

ALLOWLIST (path-keyed, distinct from SUPPRESSION_MARKER above): a handful of
real, tracked files match a decision pattern by TEXT alone while never
actually deriving an armed/disarmed verdict from it — a regex has no way to
tell "extracted and returned" from "compared to null and branched on".
SUPPRESSION_MARKER cannot be used for these: it is reserved, by policy and by
`test_marker_appears_only_in_this_lints_own_test_file_and_its_definition`,
for this lint's OWN synthetic test fixtures — spending it on a real file
would be exactly the "silently exempting real decision code, not a fixture"
failure that test exists to catch. ALLOWLIST is the general-purpose
equivalent for real files, modeled on `lint_queue_field_verdict.py`'s own
(this repo's other autoMergeRequest-hazard lint): SHRINK-ONLY, one written
`reason` per path. Unlike that sibling's ALLOWLIST, no entry here needs an
`orchestrator` tripwire, because neither current reason is CONTINGENT on
another file's content — both are permanent facts about what the flagged
line IS (a data extraction, or prose quoting a fixture), not about what
currently protects it.

LINE-SCOPED, not file-scoped (cross-family adversarial review, 2026-08-31,
agy/Gemini 3.1 Pro — first-draft bug, fixed same session, never shipped): a
path-only allowlist that swallows `result["findings"]` wholesale the moment
ANY finding exists in that path is itself a guard-over-match hole — a
GENUINELY NEW violation landing later in an already-allowlisted file (a
different line, a different decision, nothing to do with the documented
reason) would be silently absorbed under the old reason text and never
surface. Each entry therefore carries `lines: (N, ...)` — the exact
decision-line number(s) verified harmless when the entry was written — and
`run()` waives ONLY findings whose line number is in that set; a finding at
any other line in the same file is a real finding, allowlist or not. What
`run()` DOES re-verify every call: whether each declared line is still doing
anything at all — a documented line that no longer matches any decision
pattern this run (rewritten, or the file's decision logic moved) has nothing
left to waive, and is reported back as `stale_allowlist` per-line rather
than kept as silent dead weight forever (the same "esiste ≠ armato"
discipline this lint itself exists to enforce, turned on its own
bookkeeping); a path absent from the walk entirely is reported as
file-missing, a distinct reason from line-cured.

Exit code (bitmask): 0 = clean · 1 = one or more FAIL findings · 2 = a
stale ALLOWLIST entry (hygiene — the scanned code itself is clean, but the
ledger names a line that no longer needs the waiver; SHRINK-ONLY says
remove it) · 4 = operational error (unreadable file — a scan that cannot
see is not clean, W84 fail-visible discipline). Bits combine (e.g. 5 = FAIL
findings AND an unrelated operational error). `--selftest` runs a
self-contained guilt+innocence subset (no pytest) and exits 0/1 on whether
it still discriminates — the same "prove the guard, then scan" CI shape as
lint_queue_field_verdict.py.

Tests: scripts/tests/test_lint_arm_probe.py (authoritative, exhaustive) ·
`--selftest` (this file, CI-cheap subset).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional


def _canonical_repo_root() -> Path:
    """Repo root, worktree-hardened (same discipline as lint_home_fork.py):
    running from .worktrees/<lane>/ must lint against the MAIN checkout — a
    worktree is ephemeral, treating it as the source of truth would replay
    W81."""
    root = Path(__file__).resolve().parent.parent
    parts = root.parts
    if ".worktrees" in parts:
        idx = parts.index(".worktrees")
        return Path(*parts[:idx])
    return root


REPO_ROOT = _canonical_repo_root()

_SCAN_EXTS = {".py", ".sh", ".bash", ".yml", ".yaml"}
_PRUNE_DIRS = {
    "node_modules", ".venv", "venv", ".git", "__pycache__",
    ".worktrees", "dist", "build", ".next",
}

SUPPRESSION_MARKER = "lint-arm-probe:fixture"

# ALLOWLIST (SHRINK-ONLY, line-scoped) — real, tracked files whose flagged
# line matches a decision pattern by TEXT alone but never actually derives
# an armed/disarmed verdict from the field. See module docstring for why
# SUPPRESSION_MARKER cannot be used for these, and for why `lines` (not just
# `path`) is part of the key space. Never add an entry to silence a
# genuinely new violation — cure it instead. `run()` re-verifies every call
# that each declared line is still matching something (`stale_allowlist`).
# `lines` are the exact 1-indexed decision-line numbers verified harmless —
# from `scan_text()` run directly against each file, not guessed:
#   scripts/queue_baseline_probe.py -> decision_lines == [(651, ...)]
#   .../pack.yml                    -> decision_lines == [(61, ...), (172, ...)]
ALLOWLIST: dict[str, dict[str, Any]] = {
    "scripts/queue_baseline_probe.py": {
        "lines": (651,),
        "reason": (
            'fetch_automerge_enabled_at() reads the bracket-subscript '
            'autoMergeRequest field only to extract and return its enabledAt '
            'value (`return enabled_at.get("enabledAt"), None`) — it never '
            'compares the field to null/None to derive an armed/disarmed '
            'verdict. The surrounding `except (KeyError, TypeError)` and '
            '`isinstance(enabled_at, dict)` are defensive JSON-shape parsing, '
            'not a queue-membership decision. Verified 2026-08-31.'
        ),
    },
    "evidence/2026-08/agent-nuzantara-craft-w-queue-field-lint-f5503848/pack.yml": {
        "lines": (61, 172),
        "reason": (
            'an evidence-pack RECEIPT for scripts/ci/lint_queue_field_verdict.py '
            '(a different, sibling lint) — its `cmd:`/`objection:` YAML blocks '
            'quote that lint\'s own guilt-fixture Python source '
            '(`pr.get("autoMergeRequest")`) as prose/heredoc DATA describing a '
            'past test run, never code this repo executes. This lint\'s '
            '`.get("autoMergeRequest")` pattern (Pattern 0) matches on sight, '
            'with no requirement — unlike lint_queue_field_verdict.py\'s own '
            'regex — that a null-comparison operator follow it on the same '
            'line, so it catches inert prose that lint\'s own audit already '
            'proved harmless. Verified 2026-08-31.'
        ),
    },
}

_FIELD_TOKEN = "autoMergeRequest"

# The three positive-probe shapes this repo's consumers actually use (audit,
# 2026-08-29): PullRequest.mergeQueueEntry, PullRequest.isInMergeQueue, and
# the branch-level repository.mergeQueue(branch:"main"){entries...} snapshot.
_POSITIVE_PROBE_RE = re.compile(r"mergeQueueEntry|isInMergeQueue|mergeQueue\(")

# Decision-position patterns: autoMergeRequest being TESTED/FILTERED, not
# merely requested as a field. Anchored on how this repo's own consumers
# actually read the field (measured across 17 files) — not a generic
# "field appears" match, which would flag `--json ...,autoMergeRequest`
# field-selection lines and GraphQL query-declaration lines that are never
# parsed downstream (guard-over-match, cicatrix #3).
_DECISION_PATTERNS = [
    # dict.get("autoMergeRequest") / dict.get('autoMergeRequest')
    re.compile(r"""\.get\(\s*["']""" + _FIELD_TOKEN + r"""["']"""),
    # dict["autoMergeRequest"] / dict['autoMergeRequest']
    re.compile(r"""\[\s*["']""" + _FIELD_TOKEN + r"""["']\s*\]"""),
    # jq: .autoMergeRequest==null / .autoMergeRequest != null
    re.compile(r"""\.""" + _FIELD_TOKEN + r"""\s*(==|!=)\s*null"""),
    # jq: select(...autoMergeRequest...)
    re.compile(r"""select\([^)]*""" + _FIELD_TOKEN + r"""[^)]*\)"""),
]


# ---------------------------------------------------------------- scanning


def _is_full_comment_line(line: str) -> bool:
    """First non-whitespace char is `#` — a whole-line comment in Python,
    bash and YAML alike. A trailing inline `code  # comment` is NOT stripped
    (this lint does not attempt a string-literal-aware tokenizer); a comment
    mentioning autoMergeRequest AFTER real code on the same line could in
    principle still match, but no consumer in this repo's audit does that —
    documented limitation, not a silent gap."""
    return line.lstrip().startswith("#")


def _has_decision_pattern(line: str) -> bool:
    return any(p.search(line) for p in _DECISION_PATTERNS)


def scan_text(text: str, relpath: str) -> dict[str, Any]:
    """Pure function, no file I/O — the unit-testable core. Returns
    {"findings": [str], "has_positive_probe": bool, "decision_lines": [(int, str)]}.
    """
    lines = text.splitlines()
    has_positive_probe = False
    decision_lines: list[tuple[int, str]] = []

    for line_no, line in enumerate(lines, start=1):
        if SUPPRESSION_MARKER in line:
            continue
        if _is_full_comment_line(line):
            continue
        if _POSITIVE_PROBE_RE.search(line):
            has_positive_probe = True
        if _FIELD_TOKEN in line and _has_decision_pattern(line):
            decision_lines.append((line_no, line.strip()))

    findings: list[str] = []
    if decision_lines and not has_positive_probe:
        for line_no, snippet in decision_lines:
            findings.append(
                f"{relpath}:{line_no}: autoMergeRequest tested in a decision "
                f"position with no mergeQueueEntry/isInMergeQueue/mergeQueue( "
                f"probe anywhere in this file — null here can mean queued, "
                f"ejected, or never-armed, and this file cannot tell them "
                f"apart. {snippet[:160]}"
            )

    return {
        "findings": findings,
        "has_positive_probe": has_positive_probe,
        "decision_lines": decision_lines,
    }


# ---------------------------------------------------------------- discovery


def _walk_files(root: Path, errors: list[str]) -> list[Path]:
    """os.walk with the standard vendored/ephemeral prune list; unreadable
    dirs become operational errors (fail-visible), never a silent skip."""
    found: list[Path] = []
    if not root.exists():
        return found

    def _onerror(exc: OSError) -> None:
        errors.append(f"root unreadable ({type(exc).__name__}): {exc.filename or root}")

    for dirpath, dirnames, filenames in os.walk(root, onerror=_onerror):
        dirnames[:] = [d for d in dirnames if d not in _PRUNE_DIRS]
        for fn in filenames:
            if Path(fn).suffix.lower() in _SCAN_EXTS:
                found.append(Path(dirpath) / fn)
    return found


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path)


def run(root_paths: list[Path], repo_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    findings: list[str] = []
    allowlisted: list[dict[str, Any]] = []
    allowlist_seen: set[str] = set()
    allowlist_lines_hit: dict[str, set[int]] = {}

    seen: set[Path] = set()
    files: list[Path] = []
    for root in root_paths:
        for path in _walk_files(root, errors):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            files.append(path)
    files.sort()

    for path in files:
        relpath = _rel(path, repo_root)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            errors.append(f"file unreadable ({type(exc).__name__}): {relpath}")
            continue

        # Recorded unconditionally (before the token/decision check below) —
        # the file WAS scanned merely by being walked and read, regardless
        # of whether autoMergeRequest still appears in it at all. Deferring
        # this past the `_FIELD_TOKEN not in text` early-exit used to mean a
        # fully-cured file (token removed entirely) reported "file no longer
        # scanned (missing, moved, or pruned)" — false; it was scanned, the
        # hazard just isn't there anymore. Cross-family adversarial review,
        # 2026-08-31 (agy/Gemini 3.1 Pro).
        if relpath in ALLOWLIST:
            allowlist_seen.add(relpath)

        if _FIELD_TOKEN not in text:
            continue
        result = scan_text(text, relpath)

        if relpath in ALLOWLIST:
            allowed_lines = set(ALLOWLIST[relpath]["lines"])
            waived_lines: list[int] = []
            # decision_lines and findings are index-aligned — scan_text()
            # builds findings by iterating decision_lines in the same order,
            # one finding per line, only when has_positive_probe is False
            # (file-wide). When has_positive_probe is True, findings is []
            # and this zip produces nothing at all — every declared line is
            # then correctly untracked below, which is what makes it read as
            # "no longer matches any decision pattern" (the file gained a
            # probe, so the line is no longer a live finding to waive) as
            # opposed to "file no longer scanned" (the path is gone).
            for (line_no, _snippet), finding in zip(result["decision_lines"], result["findings"]):
                if line_no in allowed_lines:
                    waived_lines.append(line_no)
                else:
                    # A genuinely different violation in an allowlisted
                    # file — NOT waived. Fixes the file-level blanket
                    # suppression a cross-family review caught 2026-08-31:
                    # any finding used to be swallowed the moment the path
                    # matched ALLOWLIST at all, with no check that it was
                    # the SAME finding the entry actually documents.
                    findings.append(finding)
            # Recorded unconditionally, even when empty — an allowlisted
            # file that produced ZERO waivable findings this run (probe
            # added, or has_positive_probe otherwise True) must leave an
            # empty set here, not a missing key, so every declared line
            # falls out of `declared_lines - hit` below and is correctly
            # reported stale rather than silently treated as still live.
            allowlist_lines_hit[relpath] = set(waived_lines)
            if waived_lines:
                allowlisted.append({
                    "path": relpath,
                    "reason": ALLOWLIST[relpath]["reason"],
                    "lines": waived_lines,
                })
        else:
            findings.extend(result["findings"])

    stale_allowlist: list[str] = []
    for relpath in sorted(ALLOWLIST):
        if relpath not in allowlist_seen:
            stale_allowlist.append(
                f"{relpath}: file no longer scanned (missing, moved, or pruned) "
                f"— SHRINK-ONLY: remove this ALLOWLIST entry"
            )
            continue
        declared_lines = set(ALLOWLIST[relpath]["lines"])
        missing_lines = sorted(declared_lines - allowlist_lines_hit.get(relpath, set()))
        if missing_lines:
            singular = len(missing_lines) == 1
            noun = "line" if singular else "lines"
            verb = "matches" if singular else "match"
            pronoun = "it" if singular else "them"
            stale_allowlist.append(
                f"{relpath}: {noun} {missing_lines} no longer {verb} any decision "
                f"pattern — SHRINK-ONLY: remove {pronoun} from the entry"
            )

    exit_code = (1 if findings else 0) | (2 if stale_allowlist else 0) | (4 if errors else 0)
    return {
        "schema": 1,
        "findings": findings,
        "allowlisted": allowlisted,
        "stale_allowlist": stale_allowlist,
        "errors": errors,
        "files_scanned": len(files),
        "exit": exit_code,
    }


# ---------------------------------------------------------------- selftest


def run_selftest() -> bool:
    """Guilt+innocence fixtures, self-contained so `--selftest` needs no
    pytest (mirrors scripts/ci/lint_queue_field_verdict.py and
    scripts/lint_tg_direct_senders.py) — this is what lets a CI step run
    "prove the guard, then scan every tracked file" as one unconditional
    unit: a clean verdict from a scanner that has lost the ability to fail
    is the exact green-but-dead shape this battery exists to catch.
    Mirrors (a representative subset of) scripts/tests/test_lint_arm_probe.py
    — that pytest file remains the authoritative, exhaustive corpus."""
    ok = True

    def _check(label: str, text: str, relpath: str, expect_clean: bool) -> None:
        nonlocal ok
        result = scan_text(text, relpath)
        got_clean = not result["findings"]
        status = "PASS" if got_clean == expect_clean else "FAIL"
        ok = ok and status == "PASS"
        print(f"[{status}] {label}: expected_clean={expect_clean} got_clean={got_clean}")

    _check(
        "guilt-dict-get-no-probe",
        'def order_queue(prs):\n    return [p for p in prs if p.get("autoMergeRequest")]\n',
        "fake.py", False,
    )
    _check(
        "guilt-bracket-subscript-no-probe",
        'enabled_at = payload["data"]["repository"]["pullRequest"]["autoMergeRequest"]\n',
        "fake.py", False,
    )
    _check(
        "guilt-jq-select-no-probe",
        'jq -r \'.[]|select(.mergeable=="MERGEABLE" and .autoMergeRequest==null)|.number\'\n',
        "fake.sh", False,
    )
    _check(
        "innocent-mergequeueentry-probe-same-file",
        'eligible = [p for p in prs if p.get("mergeQueueEntry") or p.get("autoMergeRequest")]\n',
        "fake.py", True,
    )
    _check(
        "innocent-isinmergequeue-probe-alone",
        'amr = pr.get("autoMergeRequest")\n'
        'if amr and amr.get("enabledAt") and not pr.get("isInMergeQueue"):\n    alert("stuck")\n',
        "fake.py", True,
    )
    _check(
        "innocent-field-requested-never-tested",
        'gh pr view "$pr" --json autoMergeRequest,mergeStateStatus\necho "confirm: $OUT"\n',
        "fake.sh", True,
    )
    _check(
        "innocent-full-comment-line-not-a-decision",
        '# example: `if pr.get("autoMergeRequest"): reroll(pr)` is the anti-pattern this file avoids\n',
        "fake.py", True,
    )
    _check(
        "innocent-suppression-marker-hides-the-line",
        f'x = pr.get("autoMergeRequest")  # {SUPPRESSION_MARKER}\n',
        "fake.py", True,
    )

    # ALLOWLIST mechanism — the WHOLE dict is swapped for a synthetic
    # single-entry one for this check, not merely appended to: `run()`
    # iterates `sorted(ALLOWLIST)` to compute stale_allowlist, and the two
    # REAL entries point at real-repo paths that do not exist under the tiny
    # synthetic `tmp` tree used below — left in place, every run() call here
    # would report them "file no longer scanned" and set exit bit 2
    # regardless of what this check is actually exercising. A real repo scan
    # (the CLI's default `--root .`) never hits this, since both real paths
    # genuinely are under the walked root there.
    _subject = "scripts/_selftest_allowlist_subject.py"
    _saved_allowlist = dict(ALLOWLIST)
    ALLOWLIST.clear()
    ALLOWLIST[_subject] = {"lines": (1,), "reason": "synthetic subject for this selftest only"}
    try:
        with tempfile.TemporaryDirectory() as tmp_s:
            tmp = Path(tmp_s)
            guilty_text = 'x = pr.get("autoMergeRequest")\n'
            (tmp / "scripts").mkdir(parents=True)
            (tmp / _subject).write_text(guilty_text, encoding="utf-8")
            report = run([tmp], tmp)
            got_clean = report["exit"] == 0
            status = "PASS" if got_clean else "FAIL"
            ok = ok and got_clean
            print(f"[{status}] allowlist-mechanism-suppresses-allowlisted-path: expected_clean=True got_clean={got_clean}")
            got_allowlisted = len(report["allowlisted"]) == 1 and report["allowlisted"][0]["path"] == _subject
            status = "PASS" if got_allowlisted else "FAIL"
            ok = ok and got_allowlisted
            print(f"[{status}] allowlist-mechanism-reports-the-path: expected=True got={got_allowlisted}")

            (tmp / "scripts" / "other_bad.py").write_text(guilty_text, encoding="utf-8")
            report2 = run([tmp], tmp)
            got_violation = report2["exit"] & 1 and any("other_bad.py" in f for f in report2["findings"])
            status = "PASS" if got_violation else "FAIL"
            ok = ok and bool(got_violation)
            print(f"[{status}] allowlist-does-not-blanket-suppress-a-different-file: expected=True got={bool(got_violation)}")
            (tmp / "scripts" / "other_bad.py").unlink()  # clean debris before the checks below

            # Axis-2 regression check (cross-family review, 2026-08-31): a
            # SECOND, genuinely different decision line inside the SAME
            # allowlisted file — not just a different file — must still
            # surface. The old file-level `if result["findings"]: continue`
            # would have swallowed this alongside the waived line-1 finding.
            two_line_text = 'x = pr.get("autoMergeRequest")\ny = other.get("autoMergeRequest")\n'
            (tmp / _subject).write_text(two_line_text, encoding="utf-8")
            report3 = run([tmp], tmp)
            line1_waived = any(
                a["path"] == _subject and a["lines"] == [1] for a in report3["allowlisted"]
            )
            line2_surfaced = any(f"{_subject}:2:" in f for f in report3["findings"])
            got_line_scoped = line1_waived and line2_surfaced
            status = "PASS" if got_line_scoped else "FAIL"
            ok = ok and got_line_scoped
            print(f"[{status}] allowlist-is-line-scoped-not-file-scoped: expected=True got={got_line_scoped}")
            (tmp / _subject).write_text(guilty_text, encoding="utf-8")  # restore for the checks below

            # Axis-6.1 regression check (cross-family review, 2026-08-31): a
            # file that still EXISTS but had its hazard token fully removed
            # must report "no longer matches" (the cure worked), never
            # "file no longer scanned" (which implies deletion/move — the
            # old code path skipped `allowlist_seen.add()` before this
            # early-exit, so it could never tell the two apart).
            (tmp / _subject).write_text("x = 1  # token fully removed\n", encoding="utf-8")
            report4 = run([tmp], tmp)
            stale4 = next((s for s in report4["stale_allowlist"] if s.startswith(_subject)), "")
            got_cured_reason = "no longer match" in stale4 and "no longer scanned" not in stale4
            status = "PASS" if got_cured_reason else "FAIL"
            ok = ok and got_cured_reason
            print(f"[{status}] stale-allowlist-distinguishes-cured-from-missing (cured case): expected=True got={got_cured_reason} ({stale4!r})")

            (tmp / _subject).unlink()
            report5 = run([tmp], tmp)
            stale5 = next((s for s in report5["stale_allowlist"] if s.startswith(_subject)), "")
            got_missing_reason = "no longer scanned" in stale5
            status = "PASS" if got_missing_reason else "FAIL"
            ok = ok and got_missing_reason
            print(f"[{status}] stale-allowlist-distinguishes-cured-from-missing (missing case): expected=True got={got_missing_reason} ({stale5!r})")

            got_stale_exit_bit = bool(report5["exit"] & 2) and not (report5["exit"] & 1)
            status = "PASS" if got_stale_exit_bit else "FAIL"
            ok = ok and got_stale_exit_bit
            print(f"[{status}] stale-allowlist-sets-exit-bit-2-not-bit-1: expected=True got={got_stale_exit_bit}")
    finally:
        ALLOWLIST.clear()
        ALLOWLIST.update(_saved_allowlist)

    return ok


# ---------------------------------------------------------------- main


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root", action="append", default=None,
        help="repeatable; default: repo root (whole tracked tree, standard prunes)",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--selftest", action="store_true", help="guilt+innocence fixtures, no pytest needed")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.selftest:
        return 0 if run_selftest() else 1

    repo_root = args.repo_root.resolve()
    roots = args.root if args.root else ["."]
    root_paths = [
        (Path(r) if Path(r).is_absolute() else repo_root / r) for r in roots
    ]

    result = run(root_paths, repo_root)

    if args.json:
        print(json.dumps(result, indent=2))
        return result["exit"]

    print(f"[arm-probe-lint] scanned {result['files_scanned']} file(s) under "
          f"{', '.join(str(_rel(r, repo_root)) for r in root_paths)}")
    print(f"[findings] {len(result['findings'])}")
    for f in result["findings"]:
        print(f"  - {f}")
    if result["allowlisted"]:
        print(f"[allowlisted] {len(result['allowlisted'])} (not a violation — written reason each):")
        for a in result["allowlisted"]:
            print(f"  ~ {a['path']}: {a['reason']}")
    if result["stale_allowlist"]:
        print(f"[stale_allowlist] {len(result['stale_allowlist'])} (scanned code is clean — the ledger is not):")
        for s in result["stale_allowlist"]:
            print(f"  ! {s}")
    if result["errors"]:
        print(f"[errors] {len(result['errors'])} operational error(s) — scan is PARTIAL, not clean:")
        for e in result["errors"]:
            print(f"  - {e}")
    if not result["findings"] and not result["errors"] and not result["stale_allowlist"]:
        print("  clean — every decision-position autoMergeRequest read is co-located "
              "with a mergeQueueEntry/isInMergeQueue/mergeQueue( probe")
    if result["exit"]:
        print(
            f"ARM-PROBE LINT FAIL (exit {result['exit']}: bits 1=unsafe-decision "
            f"2=stale-allowlist-entry 4=scan-error) — autoMergeRequest reads null "
            f"while QUEUED, EJECTED, and NEVER-ARMED alike; cross-check "
            f"mergeQueueEntry/isInMergeQueue/mergeQueue( before treating null as "
            f"disarmed, or prune the ALLOWLIST entry the ledger no longer needs"
        )
    return result["exit"]


if __name__ == "__main__":
    sys.exit(main())
