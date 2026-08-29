#!/usr/bin/env python3
"""lint_queue_field_verdict.py — guard against deriving an armed/disarmed
verdict from a null-comparison on `autoMergeRequest` in isolation.

WHY THIS EXISTS (measured this session, 2026-08-29, against this repo).
The GitHub merge queue has a documented, live-measured trap (cicatrix
W111/W123, `.claude/rules/cicatrix-scars.md` and `-superscar.md` family
#2): `autoMergeRequest` reads `null` for TWO opposite reasons — (1) the
request was never armed, or (2) the queue just ACCEPTED it (the field is
consumed on entry). A file that compares `autoMergeRequest` to null/None
and concludes "disarmed, re-arm needed" from that alone is right in case 1
and wrong — silently — in case 2, because the field that would
disambiguate (`mergeQueueEntry` / `isInMergeQueue`) was never read. Two
separate live probes in this repo's history alarmed exactly that false
"AUTO-MERGE DISARMED / re-arm needed" while the PR was position 1 in the
queue.

The disease is not "a file mentions the field" — 22 tracked files do,
harmlessly. It is: a file derives an armed/disarmed verdict from a
null-comparison on `autoMergeRequest` while showing no awareness ANYWHERE
in that file that the queue consumes the field.

WHAT IT CHECKS: for every in-scope tracked file (`.py .sh .yml .yaml .js
.mjs .ts`), does it contain either shape below? If so, does the SAME file
also show queue-awareness (`mergeQueueEntry`, `isInMergeQueue`,
`mergeQueue(`, `mergeQueue{`, "already queued", "mq state", or the
explicit waiver `queue-field-verdict-lint: aware`)? Matched-without-
awareness is a VIOLATION.

  Shape A — a direct null-comparison: `autoMergeRequest` (optionally
  followed by a GraphQL `{...}` selection, or the closing punctuation of a
  `.get("...")`/dict-subscript call), then, allowing whitespace (which
  includes a bare newline — the one already-aware in-repo match,
  `scripts/queue_unstick.py`, spells this exact comparison across a
  line-wrapped docstring sentence, and it still clears via awareness
  below), `==` / `!=` / `is` / `is not`, then `null` or `None`.

  Shape B — a `not`-prefixed or `!`-prefixed truthiness test whose operand
  reaches `autoMergeRequest`, e.g. `not pr.get("autoMergeRequest")`,
  `!node.autoMergeRequest`.

MEASURED ON THE LIVE TREE (2026-08-29): 22 tracked files mention the
field. Exactly 2 match shape A: `scripts/queue_unstick.py` (its own
docstring names this exact ambiguity and cites W111 — aware) and
`scripts/ci/queue_rearm_population.sh` (a pure jq-filter file with no
awareness of its own — allowlisted below, because its awareness lives one
file up in its orchestrator).

ALLOWLIST — SHRINK-ONLY. Remove an entry once a file grows its own
awareness marker. Never ADD one to silence a genuinely new violation —
cure it instead. Each entry's justification is re-checked on every run
(check_allowlist_tripwire): an allowlist that stops verifying its own
reason is a violation wearing a green light (superscar #2, "esiste ≠
armato").

Exit codes: 0 clean · 1 one or more violations · 3 cannot-verify (git
unavailable, or zero files scanned — an empty sweep is not a pass, W84).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_IN_SCOPE_SUFFIXES = (".py", ".sh", ".yml", ".yaml", ".js", ".mjs", ".ts")

# SHRINK-ONLY. An entry's `reason` names the file where the awareness
# actually lives; `orchestrator` + `orchestrator_requires` are the
# tripwire re-checked every run so the waiver cannot silently outlive the
# fact that justified it.
ALLOWLIST: dict[str, dict[str, object]] = {
    "scripts/ci/queue_rearm_population.sh": {
        "reason": (
            "pure jq-filter file, no network/awareness of its own by "
            "design (split out for a guilt+innocence corpus without a "
            "live queue). Awareness lives one file up: its caller "
            "scripts/ci/queue_rearm.sh fetches the merge-queue snapshot "
            "and subtracts every PR already inside it BEFORE acting on "
            "anything this file marks as a null-autoMergeRequest "
            "candidate — measured 2026-08-29."
        ),
        "orchestrator": "scripts/ci/queue_rearm.sh",
        "orchestrator_requires": ("mergeQueue(", "already in the queue"),
    },
}

_AWARENESS_MARKERS = (
    "mergeQueueEntry",
    "isInMergeQueue",
    "mergeQueue(",
    "mergeQueue{",
    "already queued",
    "mq state",
)
WAIVER_MARKER = "queue-field-verdict-lint: aware"

# `_CLOSER` tolerates the punctuation trailing a `.get("autoMergeRequest")`
# / `["autoMergeRequest"]` call, or a GraphQL `{...}` selection, or
# neither (bare attribute access).
_CLOSER = r'(?:\s*\{[^{}]*\}|["\'\)\]]{0,3})?'
NULL_COMPARISON_RE = re.compile(
    r"\bautoMergeRequest" + _CLOSER + r"\s*(?:==|!=|\bis\b(?:\s+not\b)?)\s*(?:null|None)\b"
)
# Same-line only (unlike shape A): a truthiness test is a code idiom, not
# prose that legitimately wraps across a sentence. The filler between the
# negation and the field is deliberately a NO-BARE-SPACE character class
# (identifier/dot/bracket/paren/quote chars only) rather than "any
# character" — measured live 2026-08-29: an "any character" filler false-
# matched two harmless strings, `_die "... not armed after gh pr merge
# --auto (autoMergeRequest..."` in scripts/lane_ship.sh and `! grep -qi
# "autoMergeRequest"` in a test fixture — English prose and a shell
# absence-check, neither a truthiness test on the field's own value. A
# real code idiom (`not pr.get("autoMergeRequest")`, `!node.autoMergeRequest`)
# never has a bare space between the negation and the field; prose always
# does. Superscar #3 (guard over-match via bare substring) is this
# repo's single most common bug class (nine prior instances) — this
# filler exists specifically not to become its tenth.
_COMPACT = r"[A-Za-z0-9_.\[\]\"'(),?]{0,60}?"
NEGATED_TRUTHY_RE = re.compile(r"(?:\bnot\b\s+|!\s*)" + _COMPACT + r"autoMergeRequest\b")


def in_scope(path: Path) -> bool:
    return path.suffix in _IN_SCOPE_SUFFIXES


def is_matched(text: str) -> re.Match | None:
    return NULL_COMPARISON_RE.search(text) or NEGATED_TRUTHY_RE.search(text)


def is_aware(text: str) -> bool:
    if WAIVER_MARKER in text:
        return True
    return any(marker in text for marker in _AWARENESS_MARKERS)


def line_of(text: str, match: re.Match) -> int:
    return text.count("\n", 0, match.start()) + 1


def snippet_of(text: str, match: re.Match, width: int = 100) -> str:
    """Collapsed to one line — shape A can legitimately span a wrap."""
    return " ".join(match.group(0).split())[:width]


def check_allowlist_tripwire(path: str, repo_root: Path) -> tuple[bool, str]:
    """Re-verifies an allowlist entry's stated justification on every run.
    Missing entry / missing orchestrator / missing required substring all
    mean the waiver does NOT apply — the entry never silences a violation
    it can no longer justify."""
    entry = ALLOWLIST.get(path)
    if entry is None:
        return (False, f"{path} is not allowlisted")
    orchestrator = entry.get("orchestrator")
    if not orchestrator:
        return (True, "no orchestrator declared — waiver holds unconditionally")
    orch_path = repo_root / str(orchestrator)
    try:
        orch_text = orch_path.read_text(encoding="utf-8")
    except OSError:
        return (False, f"orchestrator {orchestrator} is missing (checked {orch_path})")
    required = entry.get("orchestrator_requires") or ()
    missing = [needle for needle in required if needle not in orch_text]
    if missing:
        return (False, f"orchestrator {orchestrator} no longer contains: {', '.join(missing)}")
    return (True, f"orchestrator {orchestrator} still carries: {', '.join(required)}")


def resolve_display_path(raw: str, repo_root: Path) -> tuple[Path, str]:
    """(on_disk_path, display_path). display_path is repo-root-relative
    with forward slashes (what ALLOWLIST is keyed on, what a human reads),
    falling back to the raw string for anything outside repo_root."""
    p = Path(raw)
    on_disk = p if p.is_absolute() else (repo_root / p)
    try:
        rel = on_disk.resolve().relative_to(repo_root.resolve())
        return on_disk, rel.as_posix()
    except ValueError:
        return on_disk, raw.replace(os.sep, "/")


def git_tracked_files(repo_root: Path) -> list[str] | None:
    """None means the probe failed — never an empty list standing in for
    'nothing to scan' (W84: an unreadable set is never an empty one)."""
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=repo_root, capture_output=True, text=True, check=False
        )
    except OSError:
        return None
    if out.returncode != 0:
        return None
    return [line for line in out.stdout.splitlines() if line]


def evaluate(paths: list[str], repo_root: Path) -> dict:
    violations: list[dict] = []
    allowlisted: list[dict] = []
    scanned = 0

    for raw in paths:
        on_disk, display = resolve_display_path(raw, repo_root)
        if not in_scope(on_disk):
            continue
        try:
            text = on_disk.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"lint_queue_field_verdict: WARN unreadable {display}: {exc}", file=sys.stderr)
            continue

        scanned += 1
        match = is_matched(text)
        if match is None:
            continue  # not in scope for this lint at all — silent skip

        if is_aware(text):
            continue  # clean: file shows its own queue-awareness

        holds, detail = check_allowlist_tripwire(display, repo_root)
        if display in ALLOWLIST and holds:
            allowlisted.append({"path": display, "reason": detail})
            continue

        cure = 'read `mergeQueueEntry` jointly, or call `mq state <PR>` — never null-comparison alone'
        if display in ALLOWLIST:
            reason = f"allowlist reason no longer holds ({detail}) — {cure}"
        else:
            reason = f"no queue-awareness in file — {cure}"

        violations.append(
            {"path": display, "line": line_of(text, match), "snippet": snippet_of(text, match), "reason": reason}
        )

    return {"scanned": scanned, "violations": violations, "allowlisted": allowlisted}


def _write(tmp: Path, name: str, content: str) -> None:
    target = tmp / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def run_selftest() -> bool:
    """Guilt+innocence fixtures, self-contained so `--selftest` needs no
    pytest (mirrors scripts/tests/test_lint_queue_field_verdict.py)."""
    ok = True
    with tempfile.TemporaryDirectory() as tmp_s:
        tmp = Path(tmp_s)
        cases = [
            ("guilt-null-comparison", "guilt_a.py",
             'if pr.get("autoMergeRequest") is None:\n    print("AUTO-MERGE DISARMED / re-arm needed")\n',
             False),
            ("guilt-negated-truthy", "guilt_b.py",
             'if not pr.get("autoMergeRequest"):\n    alarm("disarmed")\n',
             False),
            ("guilt-trap10-shape", "guilt_c.py",
             'if pr.get("autoMergeRequest") == None:\n    print("ARM CONSUMED, re-arm needed")\n',
             False),
            ("innocent-aware-marker", "innocent_a.py",
             'if pr.get("autoMergeRequest") is None:\n'
             '    if pr.get("mergeQueueEntry") is None:\n        alarm("truly disarmed")\n',
             True),
            ("innocent-waiver-marker", "innocent_b.py",
             "# queue-field-verdict-lint: aware\n"
             'if pr.get("autoMergeRequest") is None:\n    alarm("disarmed")\n',
             True),
            ("innocent-docstring-mention-only", "innocent_c.py",
             '"""Mentions autoMergeRequest only in prose, never compares it."""\n',
             True),
        ]
        for label, name, content, expect_clean in cases:
            _write(tmp, name, content)
            report = evaluate([str(tmp / name)], tmp)
            got_clean = len(report["violations"]) == 0
            status = "PASS" if got_clean == expect_clean else "FAIL"
            ok = ok and status == "PASS"
            print(f"[{status}] {label}: expected_clean={expect_clean} got_clean={got_clean}")

        _write(tmp, "scripts/ci/queue_rearm_population.sh", 'jq -r "select(.autoMergeRequest==null)"\n')
        _write(
            tmp, "scripts/ci/queue_rearm.sh",
            'inq=$(gh api graphql -f query="{mergeQueue(branch:\\"main\\"){entries}}")\n'
            'case " $inq " in *" $n "*) echo "already in the queue" ;; esac\n',
        )
        report = evaluate(["scripts/ci/queue_rearm_population.sh"], tmp)
        got_clean = len(report["violations"]) == 0
        ok = ok and got_clean
        print(f"[{'PASS' if got_clean else 'FAIL'}] allowlist-tripwire-holds: expected_clean=True got_clean={got_clean}")

        _write(
            tmp, "scripts/ci/queue_rearm.sh",
            'inq=$(gh api graphql -f query="{mergeQueue(branch:\\"main\\"){entries}}")\n'
            "# the subtraction line was removed\n",
        )
        report = evaluate(["scripts/ci/queue_rearm_population.sh"], tmp)
        got_violation = len(report["violations"]) == 1
        ok = ok and got_violation
        print(f"[{'PASS' if got_violation else 'FAIL'}] allowlist-tripwire-broken: expected_violation=True got_violation={got_violation}")

    return ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--paths", nargs="*", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return 0 if run_selftest() else 1

    repo_root = Path(args.repo_root).resolve()

    if args.paths is not None:
        paths = args.paths
    else:
        tracked = git_tracked_files(repo_root)
        if tracked is None:
            print(
                "lint_queue_field_verdict: CANNOT VERIFY — `git ls-files` failed or "
                "git is unavailable; a broken scan is never a clean one",
                file=sys.stderr,
            )
            return 3
        paths = tracked

    report = evaluate(paths, repo_root)

    if report["scanned"] == 0:
        print(
            "lint_queue_field_verdict: CANNOT VERIFY — the scan covered zero in-scope "
            "files; an empty file set is a broken probe, not a pass (W84 'esiste ≠ armato')",
            file=sys.stderr,
        )
        return 3

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(
            f"lint_queue_field_verdict: {report['scanned']} in-scope file(s) scanned, "
            f"{len(report['violations'])} violation(s), {len(report['allowlisted'])} allowlisted"
        )
        for v in report["violations"]:
            print(f"  ✗ {v['path']}:{v['line']}: {v['snippet']!r}")
            print(f"      {v['reason']}")
        for a in report["allowlisted"]:
            print(f"  ~ {a['path']} (allowlisted): {a['reason']}")
        if not report["violations"]:
            print("  ✓ every matched file shows its own queue-awareness or a live allowlist tripwire")

    return 1 if report["violations"] else 0


if __name__ == "__main__":
    sys.exit(main())
