"""PR3b (2026-09-18) — tests for the dynamic-workflow skill + brief template.

Verifies:
- Every `dynamic_workflow.py <subcommand>` name referenced in SKILL.md is a real subcommand
  of the shipped CLI's --help output (catches doc/code drift like the judge/jury split — the
  ORIGINAL mandate prose implied "judge" covered jury tabulation too; the shipped CLI splits
  them into two separate subcommands, and SKILL.md must document both, in order).
- Every F-line (F1..F15) in brief.template.md carries a source pointer — either a real
  "(source: ...)" grep-found pointer or the literal "(source: session 2026-09-18, unverified)"
  mark — never a bare, unsourced claim (mandate: find them with grep, never invent one).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = REPO_ROOT / ".claude" / "skills" / "dynamic-workflow" / "SKILL.md"
BRIEF_TEMPLATE = REPO_ROOT / ".claude" / "skills" / "dynamic-workflow" / "brief.template.md"
LAUNCHER = REPO_ROOT / "scripts" / "dynamic_workflow.py"

SUBCOMMAND_SET_RE = re.compile(r"\{([a-z0-9,\-]+)\}")
SKILL_SUBCOMMAND_RE = re.compile(r"dynamic_workflow\.py\s+([a-z][a-z0-9\-]*)")
F_LINE_RE = re.compile(r"^F(\d+)\.", re.MULTILINE)
SOURCE_RE = re.compile(r"\(source:\s*[^)]+\)")
UNVERIFIED_RE = re.compile(r"\(source:[^)]*unverified[^)]*\)")
CANONICAL_UNVERIFIED = "(source: session 2026-09-18, unverified)"


def _real_subcommands() -> set[str]:
    assert LAUNCHER.exists(), f"launcher missing: {LAUNCHER}"
    out = subprocess.run(
        [sys.executable, str(LAUNCHER), "--help"],
        capture_output=True, text=True, timeout=30, check=True,
    ).stdout
    match = SUBCOMMAND_SET_RE.search(out)
    assert match, f"could not find a {{...}} subcommand set in --help output:\n{out}"
    return set(match.group(1).split(","))


def _skill_named_subcommands() -> set[str]:
    text = SKILL_MD.read_text(encoding="utf-8")
    return set(SKILL_SUBCOMMAND_RE.findall(text))


def test_every_skill_named_subcommand_is_real():
    real = _real_subcommands()
    named = _skill_named_subcommands()
    assert named, "SKILL.md named no dynamic_workflow.py subcommands — nothing to check"
    unknown = named - real
    assert not unknown, (
        f"SKILL.md names subcommand(s) {sorted(unknown)} that --help does not list "
        f"(real subcommands: {sorted(real)})"
    )


def test_judge_and_jury_are_two_separate_documented_steps():
    """Regression guard: the ORIGINAL mandate prose conflated judge+jury into one step;
    the shipped CLI splits them. SKILL.md must show both as separate commands, in order."""
    text = SKILL_MD.read_text(encoding="utf-8")
    judge_idx = text.find("dynamic_workflow.py judge")
    jury_idx = text.find("dynamic_workflow.py jury")
    assert judge_idx != -1, "SKILL.md does not mention 'dynamic_workflow.py judge'"
    assert jury_idx != -1, "SKILL.md does not mention 'dynamic_workflow.py jury'"
    assert judge_idx < jury_idx, "SKILL.md must document judge before jury"


def test_every_fact_line_in_template_carries_a_source_pointer():
    text = BRIEF_TEMPLATE.read_text(encoding="utf-8")
    fact_numbers = sorted(int(n) for n in F_LINE_RE.findall(text))
    assert fact_numbers == list(range(1, 16)), (
        f"expected F1..F15 in brief.template.md, found {fact_numbers}"
    )
    section = text.split("## 1. Scouting report", 1)[1].split("## 2.", 1)[0]
    blocks = re.split(r"\nF\d+\.", section)[1:]
    assert len(blocks) == 15, f"expected 15 fact blocks, split found {len(blocks)}"
    for i, block in enumerate(blocks, start=1):
        assert SOURCE_RE.search(block), f"F{i} has no (source: ...) pointer:\n{block[:200]}"


def test_unverified_marks_use_the_exact_literal():
    """Anything not grep-confirmed must use the mandate's exact literal, not a paraphrase —
    so a reader can grep for it and know every hit is a genuine gap, not a typo."""
    text = BRIEF_TEMPLATE.read_text(encoding="utf-8")
    for hit in UNVERIFIED_RE.findall(text):
        assert hit == CANONICAL_UNVERIFIED, f"non-canonical unverified mark: {hit!r}"
