#!/usr/bin/env python3
"""check_adversarial_review.py — R1 "generator != grader" CI gate.

Mission (docs/specs/rules-as-harness-and-simulation-chamber-v1.md, section 2/R1):
research/audit deliverables must carry an adversarial review by a seat != author.
An LLM that graded its own homework is not a review — it is an echo. This script
is the T-GATE that makes that rule mechanical: every new/changed `research/**/*.md`
in a PR must declare, in its own frontmatter + body, who refuted it and survived.

Scar refs (why this is shaped the way it is):
  - Superscar #3 (guard over-match/under-match, cicatrix-superscar.md): a guard
    without BOTH a guilt test and an innocence test is half a guard. --selftest
    below proves both arms before this gate ever runs in CI.
  - W81 (Esiste != Armato / Armamento Sospeso): a gate that exists in the repo but
    is never invoked by any workflow is theater, not enforcement. This script is
    designed to be invoked either explicitly (--files) or from the PR diff
    (--diff), and a git failure in --diff mode is a hard exit(2), never a silent
    pass (a blind scan must never look identical to a clean one).
  - W86 (state-schema mutation drift / DOCSYNC stale): the frontmatter contract
    here is intentionally simple (one key, one section heading) so the fix for a
    FAIL is always "edit THIS file in THIS commit", never a follow-up PR that can
    drift out of sync with the artifact it certifies.

Scope: only files under `research/` ending in `.md`. Everything else is ignored
(machine-produced JSON deltas, non-research docs, etc. are out of scope by
construction, not by an exemption list).

PASS conditions per in-scope file:
  1. YAML frontmatter (the first `---`...`---` block) contains a line
     `adversarial_review: <value>` with a non-empty value, AND
  2a. <value> is (case-insensitively) one of the known seat tokens, or matches
      `human-<something>`, AND the body contains a heading matching
      `^##+\\s+Adversarial review` (case-insensitive) — OR —
  2b. <value> starts with `exempt-` (any reason after the dash) — no section
      required, but a NOTICE line is printed for visibility (an exemption is a
      greppable escape hatch, never a silent one).

FAIL conditions: missing frontmatter key, empty value, unknown seat token (not
matching the known list, not `human-*`, not `exempt-*`), or a known/human seat
with no matching "Adversarial review" section.

Usage:
    python3 scripts/check_adversarial_review.py --files a.md b.md ...
    python3 scripts/check_adversarial_review.py --diff origin/main
    python3 scripts/check_adversarial_review.py --selftest

Exit codes:
    0   all in-scope files pass (including the "zero files in scope" case)
    1   >=1 in-scope file fails
    2   git failure in --diff mode, or a CLI argument error
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, NamedTuple, Optional, Sequence

# Known adversarial-review seats (case-insensitive). A seat must be a DIFFERENT
# model/tool family than the presumed author to count as "generator != grader" —
# this list is the census of what the fleet actually has (CLAUDE.md §Agent/LLM
# Routing, ~/.claude/CLAUDE.md §External LLM arsenal). `human-<anything>` is
# always accepted (a person reviewing is never a self-grade). `exempt-<reason>`
# skips the section requirement entirely (see PASS 2b above).
KNOWN_SEATS = {
    "glm-5.2",
    "glm",
    "deepseek-v4-pro",
    "deepseek",
    "codex",
    "gpt-5.5",
    "gemini-3.1-pro",
    "gemini",
    "agy",
    "grok",
    "nlm",
    "notebooklm",
}

FRONTMATTER_KEY_RE = re.compile(r"^adversarial_review\s*:\s*(.*)$", re.IGNORECASE)
SECTION_HEADING_RE = re.compile(r"^#{2,}\s+Adversarial review\b", re.IGNORECASE | re.MULTILINE)
HUMAN_SEAT_RE = re.compile(r"^human-.+$", re.IGNORECASE)
EXEMPT_PREFIX_RE = re.compile(r"^exempt-.+$", re.IGNORECASE)

FRONTMATTER_DELIM = "---"


class FileVerdict(NamedTuple):
    path: Path
    ok: bool
    reason: str
    notice: Optional[str] = None


def _extract_frontmatter(text: str) -> Optional[str]:
    """Return the text between the first two '---' delimiter lines, or None.

    The frontmatter block must open on line 1 (allowing leading blank lines is
    NOT supported — research/*.md convention, verified against live files in
    research/operations/, always opens on line 1).
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_DELIM:
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == FRONTMATTER_DELIM:
            return "\n".join(lines[1:i])
    return None


def _find_adversarial_review_value(frontmatter: str) -> Optional[str]:
    """Return the raw value of the `adversarial_review:` key, or None if absent.

    Returns "" (empty string) if the key is present but its value is empty —
    callers must distinguish "absent" (None) from "present-but-empty" ("").
    """
    for line in frontmatter.splitlines():
        m = FRONTMATTER_KEY_RE.match(line.strip())
        if m:
            # Strip a wrapping quote pair if present (YAML scalar quoting).
            value = m.group(1).strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1].strip()
            return value
    return None


def _is_known_seat(value: str) -> bool:
    return value.lower() in KNOWN_SEATS or bool(HUMAN_SEAT_RE.match(value))


def evaluate_file(path: Path) -> FileVerdict:
    """Evaluate one in-scope file against the R1 contract. Never raises."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return FileVerdict(path, False, f"could not read file: {exc}")

    frontmatter = _extract_frontmatter(text)
    if frontmatter is None:
        return FileVerdict(
            path,
            False,
            "no YAML frontmatter block found (file must open with '---' ... '---')"
            " — fix: add frontmatter with an `adversarial_review:` key",
        )

    value = _find_adversarial_review_value(frontmatter)
    if value is None:
        return FileVerdict(
            path,
            False,
            "frontmatter missing `adversarial_review:` key"
            " — fix: add `adversarial_review: <seat>` naming a reviewer != author",
        )
    if value == "":
        return FileVerdict(
            path,
            False,
            "`adversarial_review:` key present but value is empty"
            " — fix: name a reviewing seat (e.g. `deepseek-v4-pro`, `codex`, `human-zero`)",
        )

    if EXEMPT_PREFIX_RE.match(value):
        return FileVerdict(
            path,
            True,
            "exempt",
            notice=f"NOTICE: {path} is exempt (adversarial_review: {value})",
        )

    if not _is_known_seat(value):
        known = ", ".join(sorted(KNOWN_SEATS))
        return FileVerdict(
            path,
            False,
            f"`adversarial_review: {value}` is not a known seat"
            f" — fix: use one of [{known}], `human-<name>`, or `exempt-<reason>`",
        )

    if not SECTION_HEADING_RE.search(text):
        return FileVerdict(
            path,
            False,
            f"seat `{value}` declared but no `## Adversarial review` heading found in body"
            " — fix: add a section with the refuter's surviving objections"
            ' (or "none survived, N raised")',
        )

    return FileVerdict(path, True, f"seat={value}, section present")


def is_in_scope(path: Path) -> bool:
    """Only paths under research/ ending in .md are in scope (path-string check,
    tolerant of both absolute and repo-relative inputs)."""
    if path.suffix != ".md":
        return False
    parts = path.parts
    return "research" in parts


def _git_diff_files(base_ref: str, cwd: Optional[Path] = None) -> List[str]:
    """Return files added/modified between base_ref and HEAD, scoped to
    research/**/*.md via git's own pathspec (belt-and-suspenders with
    is_in_scope, which re-checks every returned path independently).

    Raises subprocess.CalledProcessError on git failure — callers must NOT
    swallow this into an empty list (a git failure must never look like "zero
    files in scope", which is a legitimate, different outcome — W84: a blind
    scan must never pass silently).
    """
    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=AM",
            f"{base_ref}...HEAD",
            "--",
            "research/**/*.md",
        ],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def run_diff_mode(base_ref: str, repo_root: Optional[Path] = None) -> List[Path]:
    files = _git_diff_files(base_ref, cwd=repo_root)
    root = repo_root or Path.cwd()
    return [root / f for f in files]


def run_check(files: Sequence[Path]) -> int:
    in_scope = [f for f in files if is_in_scope(f)]

    if not in_scope:
        print("no research files in scope")
        return 0

    verdicts = [evaluate_file(f) for f in in_scope]

    for v in verdicts:
        if v.notice:
            print(v.notice)

    failures = [v for v in verdicts if not v.ok]
    if failures:
        print(f"FAIL — {len(failures)} of {len(in_scope)} research file(s) missing adversarial review:")
        for v in failures:
            print(f"  {v.path}: {v.reason}")
        return 1

    print(f"PASS — {len(in_scope)} research file(s) carry a valid adversarial review")
    return 0


# --------------------------------------------------------------------------- #
# --selftest: guilt + innocence fixtures (superscar #3 discipline)
# --------------------------------------------------------------------------- #

def _write(tmp: Path, name: str, content: str) -> Path:
    p = tmp / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def run_selftest() -> int:
    checks = 0
    failures: List[str] = []

    def expect(label: str, condition: bool) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(label)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # ---- GUILT: each of these must FAIL ----

        missing_key = _write(
            tmp,
            "research/operations/missing-key.md",
            "---\ndate: 2026-07-06\ndomain: operations\n---\n\n# Title\n\nBody.\n",
        )
        v = evaluate_file(missing_key)
        expect("GUILT missing_key -> fails", v.ok is False)
        expect("GUILT missing_key -> reason names the key", "adversarial_review" in v.reason)

        unknown_seat = _write(
            tmp,
            "research/operations/unknown-seat.md",
            "---\ndate: 2026-07-06\nadversarial_review: my-cousin\n---\n\n"
            "# Title\n\n## Adversarial review\n\nnone survived, 0 raised\n",
        )
        v = evaluate_file(unknown_seat)
        expect("GUILT unknown_seat -> fails", v.ok is False)
        expect("GUILT unknown_seat -> reason flags unknown seat", "not a known seat" in v.reason)

        no_section = _write(
            tmp,
            "research/operations/no-section.md",
            "---\ndate: 2026-07-06\nadversarial_review: codex\n---\n\n# Title\n\nBody, no review section.\n",
        )
        v = evaluate_file(no_section)
        expect("GUILT no_section -> fails", v.ok is False)
        expect("GUILT no_section -> reason names missing heading", "Adversarial review" in v.reason)

        empty_value = _write(
            tmp,
            "research/operations/empty-value.md",
            "---\ndate: 2026-07-06\nadversarial_review:\n---\n\n# Title\n\nBody.\n",
        )
        v = evaluate_file(empty_value)
        expect("GUILT empty_value -> fails", v.ok is False)

        no_frontmatter = _write(
            tmp,
            "research/operations/no-frontmatter.md",
            "# Title\n\nBody with no frontmatter at all.\n",
        )
        v = evaluate_file(no_frontmatter)
        expect("GUILT no_frontmatter -> fails", v.ok is False)

        # ---- INNOCENCE: each of these must PASS ----

        valid = _write(
            tmp,
            "research/operations/valid.md",
            "---\ndate: 2026-07-06\nadversarial_review: deepseek-v4-pro\n---\n\n"
            "# Title\n\n## Adversarial review\n\nnone survived, 3 raised\n",
        )
        v = evaluate_file(valid)
        expect("INNOCENCE valid seat+section -> passes", v.ok is True)

        valid_human = _write(
            tmp,
            "research/operations/valid-human.md",
            "---\ndate: 2026-07-06\nadversarial_review: human-zero\n---\n\n"
            "# Title\n\n### Adversarial review\n\nZero reviewed in person.\n",
        )
        v = evaluate_file(valid_human)
        expect("INNOCENCE human-<name> seat -> passes", v.ok is True)

        valid_case_insensitive = _write(
            tmp,
            "research/operations/valid-case.md",
            "---\ndate: 2026-07-06\nadversarial_review: CODEX\n---\n\n"
            "# Title\n\n## ADVERSARIAL REVIEW\n\nnone survived.\n",
        )
        v = evaluate_file(valid_case_insensitive)
        expect("INNOCENCE case-insensitive seat+heading -> passes", v.ok is True)

        exempt = _write(
            tmp,
            "research/regulatory/2026-07-06-delta.md",
            "---\ndate: 2026-07-06\nadversarial_review: exempt-machine-generated\n---\n\n"
            "# Delta\n\nMachine-produced, no section needed.\n",
        )
        v = evaluate_file(exempt)
        expect("INNOCENCE exempt-<reason> -> passes", v.ok is True)
        expect("INNOCENCE exempt-<reason> -> emits notice", v.notice is not None)

        outside_research = _write(
            tmp,
            "docs/specs/some-spec.md",
            "# Not research, no frontmatter at all\n",
        )
        expect("INNOCENCE outside research/ -> out of scope", is_in_scope(outside_research) is False)

        # ---- zero-in-scope end-to-end: run_check on a file list with nothing
        #      under research/ must exit 0 and say so, not silently pass on an
        #      empty verdict list that could be confused with "all passed".
        code = run_check([outside_research])
        expect("zero-in-scope run_check exits 0", code == 0)

        # ---- end-to-end guilt run: run_check on the fail fixtures exits 1
        code = run_check([missing_key, unknown_seat, no_section])
        expect("end-to-end guilt run_check exits 1", code == 1)

        # ---- end-to-end innocence run: run_check on the pass fixtures exits 0
        code = run_check([valid, valid_human, exempt])
        expect("end-to-end innocence run_check exits 0", code == 0)

    if failures:
        print(f"SELFTEST FAILED — {len(failures)}/{checks} checks failed:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print(f"SELFTEST OK — {checks} checks")
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_adversarial_review.py",
        description=(
            "R1 generator!=grader gate: research/**/*.md in scope must declare an "
            "adversarial_review seat != author + an '## Adversarial review' section."
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--files",
        nargs="+",
        metavar="FILE",
        help="Explicit list of files to check (non-matching paths are silently out of scope).",
    )
    mode.add_argument(
        "--diff",
        metavar="BASE_REF",
        help="Compute scope from `git diff --name-only --diff-filter=AM BASE_REF...HEAD -- research/**/*.md`.",
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="Run built-in guilt+innocence fixtures and exit (ignores --files/--diff).",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.selftest:
        return run_selftest()

    if args.diff:
        try:
            files = run_diff_mode(args.diff)
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            print(
                f"check_adversarial_review: git diff failed against base '{args.diff}': {stderr or exc}",
                file=sys.stderr,
            )
            return 2
        except FileNotFoundError:
            print("check_adversarial_review: git executable not found", file=sys.stderr)
            return 2
        return run_check(files)

    if args.files:
        return run_check([Path(f) for f in args.files])

    print("check_adversarial_review: no mode selected — use --files, --diff, or --selftest", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
