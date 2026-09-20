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

SCOPE. `--staged` judges the ADDED lines of the staged diff, never whole files:
a pre-existing line in a file you touched is not yours to answer for, and two
such lines live in this very workflow. Given explicit paths instead, it judges
those files whole — that is the mode the corpus and CI use.

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
P2_PATTERN = r"""export[[:space:]]+ANTHROPIC_API_KEY=[^"'[:space:]]|setenv\([[:space:]]*["']ANTHROPIC_API_KEY"""
P2_SUFFIXES = (".py", ".sh")
P2_EXCLUDE = r"\.venv/|node_modules/|/\.git/|tests/|test_|examples/|vendor/"


def _posix_bracket_to_python(pattern: str) -> str:
    """grep -E POSIX classes -> the Python equivalent, nothing else changed."""
    return pattern.replace("[[:space:]]", r"\s").replace("[:space:]", r"\s")


def _excluded(path: str, exclude: str) -> bool:
    # grep walks from `.`, so its exclusion regex sees a leading "./".
    return re.search(exclude, "./" + path.lstrip("./")) is not None


def _in_scope(path: str, suffixes: tuple[str, ...], exclude: str) -> bool:
    return path.endswith(suffixes) and not _excluded(path, exclude)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    ).stdout


def staged_files() -> list[str]:
    out = _git("diff", "--cached", "--name-only", "--diff-filter=d")
    return [line for line in out.splitlines() if line.strip()]


def staged_added_lines() -> list[tuple[str, int, str]]:
    """(path, line number in the new file, text) for every ADDED line."""
    diff = _git("diff", "--cached", "-U0", "--diff-filter=d")
    entries: list[tuple[str, int, str]] = []
    path = ""
    lineno = 0
    for raw in diff.splitlines():
        if raw.startswith("+++ b/"):
            path = raw[6:]
            continue
        if raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            lineno = int(m.group(1)) if m else 0
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            if path:
                entries.append((path, lineno, raw[1:]))
            lineno += 1
    return entries


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
            if not _in_scope(path, suffixes, exclude):
                continue
            if rx.search(text):
                findings.append(f"{label}\n     {path}:{lineno}")
    return findings


def detect_secrets_predicate(paths: list[str]) -> tuple[list[str], str | None]:
    """(findings, skip-reason). Mirrors security.yml's diff-scoped job."""
    if not paths:
        return [], None
    if len(paths) > SCAN_CAP:
        return [], f"{len(paths)} staged files is over the {SCAN_CAP}-file cap"
    if shutil.which("detect-secrets") is None:
        return [], "detect-secrets is not installed"
    if not BASELINE.exists():
        return [], f"{BASELINE.name} is missing"

    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp) / "baseline.json"
        scratch.write_text(BASELINE.read_text())
        scan = subprocess.run(
            ["detect-secrets", "scan", "--baseline", str(scratch), *paths],
            cwd=REPO_ROOT, capture_output=True, text=True, check=False,
        )
        if scan.returncode != 0:
            return [], f"detect-secrets scan exited {scan.returncode}"
        subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "detect_secrets_auto_triage.py"),
             "--apply", "--baseline", str(scratch)],
            cwd=REPO_ROOT, capture_output=True, text=True, check=False,
        )
        try:
            data = json.loads(scratch.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            return [], f"baseline copy unreadable ({exc.__class__.__name__})"

    wanted = set(paths)
    findings = []
    for path, hits in data.get("results", {}).items():
        if path not in wanted:
            continue
        for hit in hits:
            if "is_secret" not in hit:
                findings.append(
                    f"P3 detect-secrets  {hit.get('type', '?')}\n"
                    f"     {path}:{hit.get('line_number', 0)}"
                )
    return findings, None


def main() -> int:
    if os.environ.get("BAN_PREDICATES_ENFORCEMENT", "true") == "false":
        print("⚠️  [ban-predicates] DISABLED by BAN_PREDICATES_ENFORCEMENT=false")
        return 0

    argv = sys.argv[1:]
    if not argv:
        print(__doc__.strip().splitlines()[-4], file=sys.stderr)
        return 2

    if argv[0] == "--staged":
        paths = staged_files()
        entries = staged_added_lines()
        what = "staged diff"
    else:
        paths = argv
        entries = whole_file_lines(paths)
        what = f"{len(paths)} file(s)"

    if not paths:
        print("🔎 [ban-predicates] nothing staged to judge.")
        return 0

    findings = grep_predicates(entries)
    ds_findings, skipped = detect_secrets_predicate(paths)
    findings.extend(ds_findings)

    if skipped:
        # ONE line, deliberately. This prints on every commit on a machine
        # without the scanner, and a three-line notice on every commit is
        # wallpaper within a week — which is how a warning stops being read.
        print(
            f"⚠️  [ban-predicates] scanner half NOT run ({skipped}); "
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
