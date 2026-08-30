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

  Shape C — an ALIASED verdict (added 2026-08-31, PR #5218 rescue review).
  The actual historical incident went through an intermediate variable —
  `auto = pr.get("autoMergeRequest")` on one line, then, later, `if auto
  is None: print("ARM CONSUMED, re-arm needed")` — never comparing the
  literal token itself at the comparison site. Shapes A/B require that
  literal token at the comparison site and would MISS this exact shape.
  This is a single-hop, BOUNDED alias tracker — NOT real dataflow
  analysis: it matches a bare-identifier assignment (`name = <expr
  mentioning autoMergeRequest>` on one line, optionally type-annotated
  and/or `const|let|var`-prefixed), then scans forward for a null-
  comparison (`==`/`!=`/`===`/`!==`/`is`/`is not`) or negated-truthy test
  on that SAME name, stopping at whichever comes first: (1) a dedent below
  the assignment line's own indentation — an INDENTATION heuristic, not
  real scope analysis: it approximates "still the same enclosing block",
  and a realistic Python variant (assigned inside an `if`, used after it
  in the same function) is a known, undeclared-until-now miss rather than
  a modeled scope boundary; (2) a later rebinding of the same name — an
  assignment whose RHS no longer mentions the field, a `for <name> in`
  loop target, or a `def`/`function` parameter — past which the alias can
  no longer be blamed on `autoMergeRequest` (single-hop only; a `x = x or
  {}` re-derivation is explicitly NOT tracked as "still the same alias");
  or (3) a hard cap of `_ALIAS_WINDOW` lines. A blank or comment-only line
  (`#`/`//`) is transparent to all of the above — it ends nothing and it
  is never itself read as a usage (a comment merely discussing the trap
  is prose, not a verdict). Deliberately NOT covered — real dataflow-
  analysis territory, a declared scope boundary rather than a silent gap:
  a container/attribute assignment target (`d["auto"] = ...`, `self.auto =
  ...`), a second-hop alias (`x = auto` then `x is None`), a JS/TS arrow-
  function parameter (`(auto) => ...`, only `def`/`function` parameter
  lists are recognized as rebindings), or a multi-line assignment (the
  field's literal token must appear on the SAME line as the `name =`).

MEASURED ON THE LIVE TREE (2026-08-29, re-verified 2026-08-31 against
Shape C, and again after the 2026-08-31 cross-family hardening round):
22 tracked files mention the field. Exactly 2 match shape A:
`scripts/queue_unstick.py` (its own docstring names this exact ambiguity
and cites W111 — aware) and `scripts/ci/queue_rearm_population.sh` (a
pure jq-filter file with no awareness of its own — allowlisted below,
because its awareness lives one file up in its orchestrator). Shape C's
alias-ASSIGNMENT regex also textually matches the single-line idiom
(`amr = pr.get(...)` / `amr = pr.get(...) or {}`) in
`.github/workflows/merge-queue-watch.yml` and `scripts/lane_ship.sh` —
but `find_aliased_hit()` returns no hit on either: the only later use of
`amr` in both is a plain truthy check (`if amr and amr.get(...):`), never
a null-comparison or negated-truthy test, so Shape C never actually
matches these two files at all. An earlier revision of this docstring
claimed they "match but clear via awareness" — measured false (a prior
cross-family review reproduced `find_aliased_hit()` returning `None` on
both and this session independently re-ran the same check before
believing it); corrected here rather than left standing, per this
codebase's own "measured, not asserted" discipline (W84).

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

# --- Shape C: aliased verdict (single-hop, bounded — see module docstring) --
# `name = <expr mentioning autoMergeRequest>` on one line, tolerating a type
# annotation between the name and `=` (`name: Type = ...` — golden rule #5
# mandates type hints in this repo, so the incident shape written idiomatically
# for this codebase must not be invisible to the annotation-free form alone).
# Deliberately NOT `self.name`/`d["name"]` targets and NOT `const|let|var`
# repeated on a reassignment — bare identifier only, matching the real
# incident shape.
_OPTIONAL_ANNOTATION = r"(?:\s*:\s*[^=\n]+?)?"
ALIAS_ASSIGN_RE = re.compile(
    r"^[ \t]*(?:(?:const|let|var)\s+)?([A-Za-z_][A-Za-z0-9_]*)" + _OPTIONAL_ANNOTATION + r"\s*=(?!=)"
    r"[^\n]*\bautoMergeRequest\b[^\n]*$",
    re.MULTILINE,
)
_ALIAS_WINDOW = 40  # lines — bounded fallback where indentation gives no dedent signal


def _leading_width(line: str) -> int:
    expanded = line.expandtabs()
    return len(expanded) - len(expanded.lstrip(" "))


def _is_transparent(line: str) -> bool:
    """Blank or comment-only (`#.../..`. — the two comment markers this
    lint's in-scope suffixes actually use). Transparent lines carry no
    scope signal (a dedent stop on a column-0 comment is not a real
    function-boundary exit — 2026-08-31 cross-family review, reproduced)
    and no usage signal either (a comment/docstring line *mentioning* the
    null-check idiom is prose, not a verdict — the same reasoning Shape
    B's `_COMPACT` filler already applies against prose false-positives)."""
    stripped = line.strip()
    return not stripped or stripped.startswith("#") or stripped.startswith("//")


def _alias_regexes(
    alias: str,
) -> tuple[re.Pattern[str], re.Pattern[str], re.Pattern[str], re.Pattern[str], re.Pattern[str]]:
    """(null_check, negated_truthy, stale_reassignment, for_rebind, param_rebind)
    regexes for one tracked alias name.

    `stale_reassignment` matches a LATER `alias = ...` (annotation-tolerant,
    same as ALIAS_ASSIGN_RE) line whose RHS no longer mentions the field —
    the point past which this alias can no longer be blamed on
    `autoMergeRequest` (single-hop only).

    `for_rebind` / `param_rebind` (added 2026-08-31, cross-family review
    finding): a bare name is rebound just as much by becoming a LOOP TARGET
    (`for auto in ...`) or a FUNCTION PARAMETER (`def helper(auto):`) as by
    an explicit `=` — a short, common alias name (`auto`, `state`, `amr`) is
    exactly the kind that collides with an unrelated loop/parameter of the
    same name a few lines later, and superscar #3 (guard over-match) is
    this repo's largest bug class. `for_rebind` requires the name in LOOP-
    TARGET position specifically (before `in`), not merely mentioned
    anywhere on a `for` line — `for x in auto:` READS the alias and must
    NOT be treated as a rebinding. `param_rebind` covers `def`/`function`
    parameter lists only (not JS/TS arrow-function params `(auto) => ...`
    — a further, undeclared gap, out of this pass's modest scope)."""
    esc = re.escape(alias)
    null_check = re.compile(
        r"\b" + esc + r"\b\s*(?:==|!=|===|!==|\bis\b(?:\s+not\b)?)\s*(?:null|None)\b"
    )
    negated_truthy = re.compile(r"(?:\bnot\b\s+|!\s*)" + _COMPACT + r"\b" + esc + r"\b")
    stale_reassignment = re.compile(
        r"^[ \t]*\b" + esc + r"\b" + _OPTIONAL_ANNOTATION + r"\s*=(?!=)(?!.*\bautoMergeRequest\b).*$"
    )
    for_rebind = re.compile(
        r"^[ \t]*for\s+(?:[A-Za-z_][A-Za-z0-9_]*\s*,\s*)*\b" + esc + r"\b\s*(?:,|in\b)"
    )
    param_rebind = re.compile(
        r"^[ \t]*(?:async\s+)?(?:def|function)\s+[A-Za-z_][A-Za-z0-9_]*\s*\([^)]*\b" + esc + r"\b"
    )
    return null_check, negated_truthy, stale_reassignment, for_rebind, param_rebind


def find_aliased_hit(text: str) -> tuple[int, str, str] | None:
    """Returns (1-indexed line, snippet, alias_name) for the first Shape C
    hit, or None. See module docstring "Shape C" for exactly what this does
    and does not track — single-hop, bounded, not dataflow analysis."""
    if "autoMergeRequest" not in text:
        return None  # cheap exit before paying for a line split

    lines = text.split("\n")
    for assign in ALIAS_ASSIGN_RE.finditer(text):
        alias = assign.group(1)
        assign_line_idx = text.count("\n", 0, assign.start())
        indent_width = _leading_width(lines[assign_line_idx])
        null_check, negated_truthy, stale_reassignment, for_rebind, param_rebind = _alias_regexes(alias)

        for offset in range(1, _ALIAS_WINDOW + 1):
            idx = assign_line_idx + offset
            if idx >= len(lines):
                break
            line = lines[idx]
            if _is_transparent(line):
                continue  # blank/comment — no scope signal, no usage signal
            if _leading_width(line) < indent_width:
                break  # dedent — left the assignment's enclosing block
            if stale_reassignment.match(line) or for_rebind.match(line) or param_rebind.match(line):
                break  # alias rebound away from the field — stop tracking
            usage = null_check.search(line) or negated_truthy.search(line)
            if usage:
                return (idx + 1, " ".join(line.split())[:100], alias)
    return None


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
        alias_name: str | None = None
        if match is not None:
            line, snippet = line_of(text, match), snippet_of(text, match)
        else:
            aliased = find_aliased_hit(text)
            if aliased is None:
                continue  # not in scope for this lint at all — silent skip
            line, snippet, alias_name = aliased

        if is_aware(text):
            continue  # clean: file shows its own queue-awareness

        holds, detail = check_allowlist_tripwire(display, repo_root)
        if display in ALLOWLIST and holds:
            allowlisted.append({"path": display, "reason": detail})
            continue

        cure = 'read `mergeQueueEntry` jointly, or call `mq state <PR>` — never null-comparison alone'
        if display in ALLOWLIST:
            reason = f"allowlist reason no longer holds ({detail}) — {cure}"
        elif alias_name is not None:
            reason = f"verdict derived via intermediate variable `{alias_name}`, no queue-awareness in file — {cure}"
        else:
            reason = f"no queue-awareness in file — {cure}"

        violations.append({"path": display, "line": line, "snippet": snippet, "reason": reason})

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
            ("guilt-aliased-trap10-intermediate-variable", "guilt_d.py",
             'auto = pr.get("autoMergeRequest")\n'
             'if auto is None:\n    print("ARM CONSUMED, re-arm needed")\n',
             False),
            ("innocent-aliased-usage-after-dedent", "innocent_d.py",
             'def f():\n'
             '    auto = pr.get("autoMergeRequest")\n'
             '    do_a()\n'
             'def g():\n'
             '    auto = "unrelated"\n'
             '    if not auto:\n        handle()\n',
             True),
            ("innocent-aliased-usage-after-reassignment", "innocent_e.py",
             'auto = pr.get("autoMergeRequest")\n'
             'do_a()\n'
             'auto = compute_something_else()\n'
             'if not auto:\n    handle_something_else()\n',
             True),
            ("guilt-aliased-type-annotated", "guilt_e.py",
             'auto: dict | None = pr.get("autoMergeRequest")\n'
             'if auto is None:\n    print("ARM CONSUMED, re-arm needed")\n',
             False),
            ("innocent-aliased-annotated-reassignment", "innocent_f.py",
             'auto = pr.get("autoMergeRequest")\n'
             'auto: str = "unrelated"\n'
             'if not auto:\n    handle()\n',
             True),
            ("innocent-aliased-for-loop-shadow", "innocent_g.py",
             'state = pr.get("autoMergeRequest")\n'
             'for state in other_states:\n'
             '    if not state:\n        continue\n',
             True),
            ("innocent-aliased-def-param-shadow", "innocent_h.py",
             'def f(pr):\n'
             '    auto = pr.get("autoMergeRequest")\n'
             '    def helper(auto):\n'
             '        if not auto:\n            return\n',
             True),
            ("guilt-aliased-usage-past-dedented-comment", "guilt_f.py",
             'def f(pr):\n'
             '    auto = pr.get("autoMergeRequest")\n'
             '# TODO: rearm check happens below\n'
             '    if auto is None:\n        print("ARM CONSUMED, re-arm needed")\n',
             False),
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
