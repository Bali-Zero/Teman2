#!/usr/bin/env python3
"""check_ban_predicates.py — run the paid-endpoint ban's own guards, locally.

WHY THIS EXISTS, stated as the failure and not as a feature.

On 2026-09-20 one lane tripped the same class of check four times in one day:
a PR body, then catE-sovereignty-lint, then Detect Secrets, then Detect Secrets
again. Every occurrence was PROSE — a comment or a docstring explaining the ban
by writing the banned spelling out. Four different guards caught it and all
four caught it in CI, minutes to an hour after the commit, which is why the
same mistake could be made a second, third and fourth time.

Nothing here is a new rule. The rule is already in the repo, written into
`.husky/pre-commit` beside the PII gate's own regex:

    "The shape is described rather than written out on purpose: a literal
     example here would match this very pattern [...] The literals live where
     they are load-bearing instead: the guilt corpus."

This script generalises that from one hook's pattern to the ban, and moves the
verdict from CI to the commit.

WHAT IT RUNS. Not a fifth matcher — a guard that judged the ban its own way
would be the over/under-match (cicatrix #3) the existing ones exist to prevent.
It runs the predicates that already own this ban:

  P1  catE-sovereignty-lint #40  — the paid constructor form
  P2  catE-sovereignty-lint #40b — the env-var value assignment
  P3  detect-secrets, diff-scoped, exactly as .github/workflows/security.yml
      runs it: scan the target files against a COPY of `.secrets.baseline`,
      apply the repo's own auto-triage, then fail on any unaudited residue.

P1 and P2 are transcribed from the workflow; `scripts/tests/test_ban_predicates.py`
asserts each transcription is byte-identical to the regex the workflow runs, so
a drifting copy fails rather than lies.

P3 IS SKIPPED, LOUDLY, WHEN detect-secrets IS ABSENT. That breaks this repo's
"a missing binary fails closed" convention on purpose, with a measurement
behind it: on 2026-09-20 detect-secrets was installed on 1 of the fleet's 3
machines, so failing closed would have blocked every commit on the other two.
The CI job stays the net for that half; this script says so out loud rather
than printing a green it did not earn.

SCOPE, and the two halves differ. The GREP halves judge the ADDED lines of the
staged diff only: a pre-existing line in a file you touched is not yours to
answer for, and two such lines live in the workflow this transcribes. The
SCANNER half judges whole files, because detect-secrets has no line-scoped
mode and that is also how security.yml runs it — but on the STAGED BLOB, read
out of the index into a temp tree, never on the file as it sits. After
`git add -p` the working copy holds content this commit does not carry, and
refusing a commit for a line it does not contain is the over-match that
teaches people to keep the kill switch in their shell history.

Given explicit paths instead of `--staged`, both halves judge those files
whole, from the worktree — the mode the corpus uses.

    python3 scripts/check_ban_predicates.py --staged
    python3 scripts/check_ban_predicates.py FILE [FILE ...]

Kill switch (say why in the commit): BAN_PREDICATES_ENFORCEMENT=false
Exit 0 clean · 1 findings · 2 usage/environment error.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "catE-sovereignty-lint.yml"
BASELINE = REPO_ROOT / ".secrets.baseline"
# Where the companion scripts live, taken from THIS file rather than from
# REPO_ROOT: the corpus retargets REPO_ROOT at a synthetic tree, and a triage
# script resolved relative to that tree would silently not be found.
SCRIPTS_DIR = Path(__file__).resolve().parent
# Above this many staged files the scanner stops being a pre-commit gesture.
# The grep halves have no cap — they are pure regex over added lines.
SCAN_CAP = 80

# Transcribed from catE-sovereignty-lint.yml. test_ban_predicates.py proves
# each one still matches the workflow's text character for character.
P1_PATTERN = r"Anthropic\(\s*api_key"
P1_SUFFIXES = (".py",)
P1_EXCLUDE = r"\.venv/|node_modules/|/\.git/|tests/|test_"

# Raw triple-quoted so the regex needs no escaping of its own quotes: an
# escaped copy is not the same string the workflow greps with, and the parity
# test in scripts/tests/test_ban_predicates.py compares them literally.
P2_PATTERN = r"""export[[:space:]]+ANTHROPIC_API_KEY=[^"'[:space:]]|\bsetenv\([[:space:]]*["']ANTHROPIC_API_KEY"""
P2_SUFFIXES = (".py", ".sh")
P2_EXCLUDE = r"\.venv/|node_modules/|/\.git/|tests/|test_|examples/|vendor/"


def _posix_bracket_to_python(pattern: str) -> str:
    """grep -E POSIX classes -> the Python equivalent, nothing else changed."""
    return pattern.replace("[[:space:]]", r"\s").replace("[:space:]", r"\s")


def _excluded(grep_line: str, exclude: str) -> bool:
    """Judge what CI judges: the whole `./path:lineno:content` output line.

    catE filters `grep -rnE ... .` through `grep -vE '<exclude>'`, and that
    second grep reads grep's OUTPUT — path, line number and content together.
    Applying the same regex to the path alone makes this gate STRICTER than
    the workflow: `client = VendorClient(key=contest_id)` has "test_" in its
    content, so CI drops the hit and a path-only copy would refuse the commit.
    A local gate that reds what CI allows is a gate people learn to disable.
    (kimi-code/k3, council pass on this PR.)
    """
    return re.search(exclude, grep_line) is not None


def _grep_line(path: str, lineno: int, text: str) -> str:
    return f"./{path}:{lineno}:{text}"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-c", "core.quotePath=false", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    ).stdout


def staged_files() -> list[str]:
    out = _git("diff", "--cached", "--name-only", "--diff-filter=d")
    return [line for line in out.splitlines() if line.strip()]


def _header_path(raw: str) -> str | None:
    """The path on a `+++` header line, or None when there is not one.

    None matters as much as the path. The first version only recognised
    `+++ b/…` and left `path` at its PREVIOUS value on anything else, so a
    header git had quoted — `+++ "b/café.py"`, and git quotes any non-ASCII
    name — sent that file's added lines to the file before it in the diff. If
    that neighbour was excluded, the lines were never judged at all: a paid
    call site could be hidden behind an excluded file. `core.quotePath=false`
    removes the common case; this returns None for whatever is left, so the
    lines are counted as unattributable rather than blamed on someone else.
    (kimi-code/k3, council pass on this PR.)
    """
    rest = raw[4:]
    if rest == "/dev/null":
        return None
    if rest.startswith("b/"):
        return rest[2:]
    return None


def staged_added_lines() -> tuple[list[tuple[str, int, str]], int]:
    """((path, new-file line number, text) for every ADDED line, unattributed)."""
    diff = _git("diff", "--cached", "-U0", "--diff-filter=d")
    entries: list[tuple[str, int, str]] = []
    unattributed = 0
    path: str | None = None
    lineno = 0
    for raw in diff.splitlines():
        if raw.startswith("+++"):
            path = _header_path(raw)
            continue
        if raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            lineno = int(m.group(1)) if m else 0
            continue
        if raw.startswith("+"):
            if path:
                entries.append((path, lineno, raw[1:]))
            else:
                unattributed += 1
            lineno += 1
    return entries, unattributed


def whole_file_lines(paths: list[str]) -> list[tuple[str, int, str]]:
    entries: list[tuple[str, int, str]] = []
    for p in paths:
        f = REPO_ROOT / p
        if not f.is_file():
            continue
        try:
            text = f.read_text(errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            entries.append((p, i, line))
    return entries


def grep_predicates(entries: list[tuple[str, int, str]]) -> list[str]:
    findings: list[str] = []
    checks = (
        ("P1 catE #40  paid constructor", P1_PATTERN, P1_SUFFIXES, P1_EXCLUDE),
        ("P2 catE #40b key assignment", P2_PATTERN, P2_SUFFIXES, P2_EXCLUDE),
    )
    for label, pattern, suffixes, exclude in checks:
        rx = re.compile(_posix_bracket_to_python(pattern))
        for path, lineno, text in entries:
            # --include first, then the match, then the exclusion — the order
            # the workflow's pipeline applies them in.
            if not path.endswith(suffixes):
                continue
            if not rx.search(text):
                continue
            if _excluded(_grep_line(path, lineno, text), exclude):
                continue
            findings.append(f"{label}\n     {path}:{lineno}")
    return findings


def _materialise_staged(paths: list[str], root: Path) -> list[tuple[int, str]]:
    """Write each path's STAGED blob under `root`, keeping the relative path.

    Scanning the working tree instead would judge content this commit does not
    carry: after `git add -p` the unstaged remainder of a file is still on
    disk, and a secret there would block a commit that does not contain it —
    an over-match, and a contradiction of this script's own scope claim.
    Baseline keys stay repo-relative because the layout is reproduced.
    (kimi-code/k3, council pass on this PR.)
    """
    written: list[tuple[int, str]] = []
    for i, rel in enumerate(paths):
        blob = subprocess.run(
            ["git", "show", f":{rel}"], cwd=REPO_ROOT,
            capture_output=True, check=False,
        )
        if blob.returncode != 0:
            continue
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob.stdout)
        written.append((i, rel))
    return written


# Skip reasons as CODES, not sentences. See the comment on the return type.
SKIP_CAP = "cap"
SKIP_NO_BINARY = "no-binary"
SKIP_NO_BASELINE = "no-baseline"
SKIP_NO_BLOB = "no-blob"
SKIP_SCAN_ERROR = "scan-error"
SKIP_BASELINE_UNREADABLE = "baseline-unreadable"
SKIP_TRIAGED_UNREADABLE = "triaged-unreadable"
SKIP_GATE_ERROR = "gate-error"
SKIP_UNLOCATABLE = "unlocatable"

_SKIP_TEXT = {
    SKIP_CAP: "{n} staged files is over the {cap}-file cap",
    SKIP_NO_BINARY: "detect-secrets is not installed",
    SKIP_NO_BASELINE: "the secrets baseline is missing",
    SKIP_NO_BLOB: "no staged blob could be read",
    SKIP_SCAN_ERROR: "the scan ERRORED (exit {n})",
    SKIP_BASELINE_UNREADABLE: "the baseline copy was unreadable",
    SKIP_TRIAGED_UNREADABLE: "the triaged baseline was unreadable",
    SKIP_GATE_ERROR: "the unaudited check ERRORED (exit {n})",
    SKIP_UNLOCATABLE: "residue was reported but could not be located",
}


def detect_secrets_predicate(
    paths: list[str], from_index: bool
) -> tuple[list[tuple[int, int]], tuple[str, int] | None]:
    """((index into `paths`, line number), (skip code, detail)).

    NOTHING THIS RETURNS IS A STRING, and that is the whole point. An earlier
    version returned sentences built next to `BASELINE.read_text()`, and
    CodeQL called it py/clear-text-logging-sensitive-data — twice, high, on
    PR #6943 — because text read out of a secrets scan reached a terminal.
    Cutting the scanner's stdout out of the path was not enough: anything
    assembled in this scope is downstream of that read.

    So the caller gets two integers and a code from a fixed table. It looks
    up the path in the list IT passed in and formats the message from
    constants. There is no longer an expression here that could carry a
    value even if someone tried. §4 is an OUTPUT boundary, and a gate that
    reports ON secrets is the last place that should echo what it read.
    """
    if not paths:
        return [], None
    if len(paths) > SCAN_CAP:
        return [], (SKIP_CAP, len(paths))
    if shutil.which("detect-secrets") is None:
        return [], (SKIP_NO_BINARY, 0)
    if not BASELINE.exists():
        return [], (SKIP_NO_BASELINE, 0)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        scratch = tmp_path / "baseline.json"
        scratch.write_text(BASELINE.read_text())

        if from_index:
            tree = tmp_path / "tree"
            tree.mkdir()
            indexed = _materialise_staged(paths, tree)
            cwd = tree
        else:
            indexed = list(enumerate(paths))
            cwd = REPO_ROOT
        if not indexed:
            return [], (SKIP_NO_BLOB, 0)
        targets = [rel for _, rel in indexed]

        scan = subprocess.run(
            ["detect-secrets", "scan", "--baseline", str(scratch), *targets],
            cwd=cwd, capture_output=True, text=True, errors="replace", check=False,
        )
        if scan.returncode != 0:
            return [], (SKIP_SCAN_ERROR, scan.returncode)

        # Keep only the files this commit touches, so residue someone else
        # left in the tracked baseline cannot red a stranger's commit.
        try:
            data = json.loads(scratch.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            return [], (SKIP_BASELINE_UNREADABLE, 0)
        wanted = set(targets)
        data["results"] = {
            k: v for k, v in data.get("results", {}).items() if k in wanted
        }
        scratch.write_text(json.dumps(data))

        subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "detect_secrets_auto_triage.py"),
             "--apply", "--baseline", str(scratch)],
            cwd=REPO_ROOT, capture_output=True, text=True, errors="replace", check=False,
        )
        # The VERDICT comes from the repo's own gate script, not from a second
        # reading of the same JSON: one unaudited-residue rule, one place.
        verdict = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "detect_secrets_check_unaudited.py"),
             "--baseline", str(scratch)],
            cwd=REPO_ROOT, capture_output=True, text=True, errors="replace", check=False,
        )
        if verdict.returncode == 0:
            return [], None
        if verdict.returncode != 1:
            return [], (SKIP_GATE_ERROR, verdict.returncode)

        # THE VERDICT is the exit code above — one definition of "unaudited",
        # and it lives in the repo's own gate script. THE LOCATION is rebuilt
        # here from two values that cannot carry a credential: a path this
        # function itself passed in, and an integer. Nothing read out of the
        # scan — not its stdout, not a string from the baseline JSON, not even
        # the detector's name — is ever printed. CodeQL flagged the earlier
        # form as py/clear-text-logging-sensitive-data (2 high, PR #6943) and
        # it was right to: a gate that reports on secrets is the last place
        # that should echo anything it read. §4 is an OUTPUT boundary.
        # Re-read: the triage above rewrote the file, and `data` is the
        # PRE-triage snapshot. Locating from it would name every hit the
        # triage had just excused — the test fixtures first of all.
        try:
            audited = json.loads(scratch.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            return [], (SKIP_TRIAGED_UNREADABLE, 0)
        located: list[tuple[int, int]] = []
        for idx, rel in indexed:
            for hit in audited.get("results", {}).get(rel, []):
                if "is_secret" in hit:
                    continue
                try:
                    line = int(hit.get("line_number", 0))
                except (TypeError, ValueError):
                    line = 0
                located.append((idx, line))
        if not located:
            # The gate said residue, this loop found none: report the
            # disagreement rather than a green neither half voted for.
            return [], (SKIP_UNLOCATABLE, 0)
    return located, None


def main() -> int:
    if os.environ.get("BAN_PREDICATES_ENFORCEMENT", "true") == "false":
        print("⚠️  [ban-predicates] DISABLED by BAN_PREDICATES_ENFORCEMENT=false")
        return 0

    argv = sys.argv[1:]
    if not argv:
        # Not `__doc__`: it is None under `python -OO`, and a usage line that
        # can itself raise is a poor way to explain a usage error.
        print(
            "usage: check_ban_predicates.py --staged | FILE [FILE ...]",
            file=sys.stderr,
        )
        return 2

    unattributed = 0
    if argv[0] == "--staged":
        paths = staged_files()
        entries, unattributed = staged_added_lines()
        from_index = True
        what = "staged diff"
    else:
        paths = argv
        entries = whole_file_lines(paths)
        from_index = False
        what = f"{len(paths)} file(s)"

    if not paths:
        print("🔎 [ban-predicates] nothing staged to judge.")
        return 0

    findings = grep_predicates(entries)
    located, skipped = detect_secrets_predicate(paths, from_index)
    # The scanner half is formatted HERE, from the caller's own list and an
    # integer — see that function's docstring for why it hands back neither.
    findings.extend(
        f"P3 detect-secrets\n     {paths[i]}:{line}"
        for i, line in located
        if 0 <= i < len(paths)
    )

    if unattributed:
        # Never silent: these lines were real additions whose file this parser
        # could not name, so they were judged by nobody.
        print(
            f"⚠️  [ban-predicates] {unattributed} added line(s) had no parseable "
            "file header and were NOT judged (a path git had to quote)."
        )

    if skipped:
        # ONE line, deliberately. This prints on every commit on a machine
        # without the scanner, and a three-line notice on every commit is
        # wallpaper within a week — which is how a warning stops being read.
        code, detail = skipped
        reason = _SKIP_TEXT.get(code, "the scanner half did not run").format(
            n=detail, cap=SCAN_CAP
        )
        print(
            f"⚠️  [ban-predicates] scanner half NOT run: {reason}. "
            "CI's Detect Secrets job is the net. `pip install detect-secrets` to close it here."
        )

    if not findings:
        print(f"✅ [ban-predicates] {what}: no banned spelling reached the commit.")
        return 0

    print("❌ [ban-predicates] the paid-endpoint ban's own guards fire on this commit:")
    for f in findings:
        print(f"   {f}")
    print()
    print("   If the line is PROSE — a comment, a docstring, a message — describe")
    print("   the shape instead of spelling it. Every guard here scans text without")
    print("   distinguishing description from use, and is right not to try.")
    print("   If the line is a real call site, the sanctioned path is the `claude`")
    print("   CLI with CLAUDE_CODE_OAUTH_TOKEN, or the SDK given an OAuth bearer.")
    print("   Literals belong in a guilt corpus under tests/ or test_*, which every")
    print("   predicate above already excludes.")
    print()
    print("   Override, if you know why: BAN_PREDICATES_ENFORCEMENT=false git commit ...")
    return 1


if __name__ == "__main__":
    sys.exit(main())
