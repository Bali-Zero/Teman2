"""PR3b'' (2026-09-19, rework of PR3b' #6779 per dw-gate-11 REWORK-BUILD) — tests for the
dynamic-workflow skill + brief template.

Verifies: every subcommand SKILL.md names is real (doc/code drift guard, e.g. the judge/jury
split); the CONVERSE (obs 11) — every real subcommand is named in SKILL.md, the direction a
"delete `reveal` from SKILL.md" mutation turns red, which the first check alone would miss;
every F-line (F1..F15) in brief.template.md carries a source pointer, real or the exact
"(source: session 2026-09-18, unverified)" literal, never a bare claim; every "(source:
path:line[-line])" pointer names a file that exists (obs 10: no prior test opened one); and a
curated subset of those pointers — the ones dw-gate-11 flagged wrong (F1, F14) or missing (F6,
F9, F10) — contains the keyword the fact declares, at the CURRENTLY cited line(s).
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

# Matches "path:line", "path:line-line" or "path:line,line,line". A pointer that line-wraps
# mid-path resolves to a nonexistent repo-root file instead of matching across the newline —
# that is by design, the exact failure mode this test exists to catch, not a regex to relax.
POINTER_RE = re.compile(r"([A-Za-z0-9_./-]+\.(?:md|py)):(\d+(?:[-,]\d+)*)")

# A bare "path.md" / "path.py" mention, with or without a trailing ":line" — superset of
# POINTER_RE's path group, used to catch a repo pointer that DROPPED its line number (obs 6).
BARE_FILE_TOKEN_RE = re.compile(r"[A-Za-z0-9_./-]+\.(?:md|py)")

# Curated (path, line-spec) -> keyword the fact declares, re-verified by opening each pointer
# 2026-09-19 (PR3b''' addendum A2/A3; Amendment A3(ii), 05:20Z, builder-reported). Full set
# equality with every POINTER_RE match in brief.template.md is the point of
# test_curated_map_covers_every_line_pointer — all 15 (path, spec) pairs the template cites
# have an entry below, including F4 and F8's two pre-existing, previously-uncurated pointers.
_VERIFIED_POINTER_KEYWORDS = {
    ("docs/rules/RULINGS.md", "106"): "60/300",
    ("research/design/2026-08-31-web-design-sixteen-lane-corpus/SYNTHESIS.md", "9"): "secs=848",
    ("research/agent-craft/cc-meta-loop/BACKLOG.md", "206"): "36,322",
    ("research/agent-craft/cc-meta-loop/BACKLOG.md", "208"): "15,064",
    (".claude/skills/workflow/SKILL.md", "36-42"): "25 s",
    ("docs/rules/RULINGS.md", "69"): "2-3 minutes",
    ("docs/architecture/dual-consul/army-map.md", "276"): "2–3 minutes",
    ("docs/architecture/dual-consul/army-map.md", "147-151"): "no native",
    ("research/operations/2026-09-10-fable-max-sessions/README.md", "69"):
        "published, not delivered",
    ("docs/rules/RULINGS.md", "85"): "RULED 2026-09-10",
    ("research/operations/2026-09-07-astra-operative-workflow-audit.md", "25"): "106 refuters",
    ("MODEL_ROSTER.md", "70"): "gemini-3.1-pro",
    ("MODEL_ROSTER.md", "90"): "kimi-code/k3",
    (".claude/skills/workflow/SKILL.md", "49"): "7 false-clean",
    ("docs/architecture/dual-consul/army-map.md", "72,74,76"): "400-dead",
}


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


def test_every_real_subcommand_is_named_in_skill_md():
    """Converse of the test above (obs 11, PASS condition a): deleting every "reveal" mention
    from SKILL.md must go red here, even though the one-directional test stays green."""
    real = _real_subcommands()
    named = _skill_named_subcommands()
    missing = real - named
    assert not missing, (
        f"--help lists subcommand(s) {sorted(missing)} that SKILL.md never mentions as "
        f"'dynamic_workflow.py <subcommand>' (named: {sorted(named)})"
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


def test_every_source_pointer_resolves_to_a_real_file():
    """dw-gate-11 obs 10 on #6779: no test previously opened a single pointer. This one opens
    every "path:line" pointer in the template and asserts the named file exists."""
    text = BRIEF_TEMPLATE.read_text(encoding="utf-8")
    pointers = POINTER_RE.findall(text)
    assert pointers, "no (source: path:line) pointers found in brief.template.md"
    for rel, spec in pointers:
        target = REPO_ROOT / rel
        assert target.exists(), f"source pointer names a file that does not exist: {rel}:{spec}"


def _lines_for_spec(path: Path, spec: str) -> str:
    """spec is "106", "36-42" or "72,74,76" (1-indexed, inclusive on a range)."""
    all_lines = path.read_text(encoding="utf-8").splitlines()
    numbers: set[int] = set()
    for part in spec.split(","):
        if "-" in part:
            start, end = part.split("-", 1)
            numbers.update(range(int(start), int(end) + 1))
        else:
            numbers.add(int(part))
    return "\n".join(all_lines[n - 1] for n in sorted(numbers) if 0 < n <= len(all_lines))


def test_curated_source_pointers_contain_their_declared_keyword():
    """Curated subset dw-gate-11 flagged wrong or missing on #6779 (F1, F6, F9, F10, F14),
    re-verified 2026-09-19. Checked against what brief.template.md cites RIGHT NOW — a
    citation that moves without updating this map goes red on the membership check below,
    it does not silently pass against a stale spec."""
    assert _VERIFIED_POINTER_KEYWORDS, "curated pointer map is empty — nothing to check"
    text = BRIEF_TEMPLATE.read_text(encoding="utf-8")
    cited_now = set(POINTER_RE.findall(text))
    for (rel, spec), keyword in _VERIFIED_POINTER_KEYWORDS.items():
        assert (rel, spec) in cited_now, (
            f"brief.template.md no longer cites {rel}:{spec} — the citation moved, was "
            f"removed, or its line spec changed; update this map or fix the template"
        )
        target = REPO_ROOT / rel
        assert target.exists(), f"{rel} does not exist"
        cited = _lines_for_spec(target, spec)
        assert keyword in cited, (
            f"{rel}:{spec} does not contain {keyword!r} — pointer is stale or the source moved"
        )


def test_every_repo_pointer_carries_a_line_number():
    """Obs 6 turned into a rule (PR3b''' A3i): a bare "path.md"/"path.py" mention with no line
    number can't be opened at an exact span. Checked per F-block so two non-repo-path
    exemptions apply narrowly: F2 cites shell commands (one of them contains the substring
    "PENDING-ARMS.md" inside a backtick command, not a source pointer) and F15 cites memory
    slugs, not repo paths. Both are exempted by fact number, not by loosening the pattern."""
    text = BRIEF_TEMPLATE.read_text(encoding="utf-8")
    section = text.split("## 1. Scouting report", 1)[1].split("## 2.", 1)[0]
    blocks = re.split(r"\nF\d+\.", section)[1:]
    assert len(blocks) == 15, f"expected 15 fact blocks, split found {len(blocks)}"
    EXEMPT_FACT_NUMBERS = {2, 15}
    for i, block in enumerate(blocks, start=1):
        if i in EXEMPT_FACT_NUMBERS:
            continue
        pointer_starts = {m.start() for m in POINTER_RE.finditer(block)}
        for m in BARE_FILE_TOKEN_RE.finditer(block):
            assert m.start() in pointer_starts, (
                f"F{i} cites {m.group()!r} at char {m.start()} of the block with no line "
                f"number immediately after it — every repo pointer must carry :line so a "
                f"reader (and test_curated_source_pointers_contain_their_declared_keyword) "
                f"can open the exact span"
            )


def test_curated_map_covers_every_line_pointer():
    """Obs 6 turned into a rule (PR3b''' A3ii): the curated map must name every "path:line"
    pointer POINTER_RE finds in the template, in both directions — a real pointer missing a
    map entry, or a map entry for a pointer that moved or was removed, both go red here."""
    text = BRIEF_TEMPLATE.read_text(encoding="utf-8")
    cited_now = set(POINTER_RE.findall(text))
    mapped = set(_VERIFIED_POINTER_KEYWORDS.keys())
    missing_from_map = cited_now - mapped
    stale_in_map = mapped - cited_now
    assert not missing_from_map, (
        f"brief.template.md cites pointer(s) with no _VERIFIED_POINTER_KEYWORDS entry: "
        f"{sorted(missing_from_map)}"
    )
    assert not stale_in_map, (
        f"_VERIFIED_POINTER_KEYWORDS has entry/entries for pointer(s) brief.template.md no "
        f"longer cites: {sorted(stale_in_map)}"
    )
