"""PR3f (2026-09-20, resumption of the skill lineage suspended after dw-gate-18 per mandate §S)
— tests for the dynamic-workflow skill + brief template.

Shape: 13 single-assertion-family test functions, no `@pytest.mark.parametrize` anywhere — 4
carried from #6779, 3 from #6802, 2 from #6804 and 4 new here (§S S1's frozen-count ban, the
flag-coverage converse, and the two that make SKILL.md's Source map evidence: set equality with
the curated launcher map, and the keyword actually present at each cited launcher line). Read the
count from `--collect-only`, never from this docstring.

NOTE ON SKILL.md's SOURCE MAP: it cites the launcher by SYMBOL (`scripts/dynamic_workflow.py::
<keyword>`), not by `path:line`. No line of the mandate requires line numbers there — every
pointer/line-number rule in it is scoped to `brief.template.md` (addendum A3 (i)/(ii) and
Amendment A3(ii), all phrased against `_VERIFIED_POINTER_KEYWORDS` and "POINTER_RE finds in
brief.template.md"), while the SKILL.md requirement is that "every step is a launcher subcommand".
Citing by symbol means a launcher PR that shifts lines cannot make this skill stale, while a
renamed or deleted enforcement point still goes red — which is the drift actually worth catching.

Verifies: every subcommand SKILL.md names is real (doc/code drift guard, e.g. the judge/jury
split); the CONVERSE (obs 11) — every real subcommand is named in SKILL.md, the direction a
"delete `reveal` from SKILL.md" mutation turns red, which the first check alone would miss; the
same converse for every FLAG the launcher's own `--help` screens expose, so a flag added to the
launcher and never documented (`r1 --register` was exactly that) goes red instead of drifting;
every F-line (F1..F15) in brief.template.md carries a source pointer, real or the exact
"(source: session 2026-09-18, unverified)" literal, never a bare claim; every "(source:
path:line[-line])" pointer names a file that exists (obs 10: no prior test opened one); a
curated subset of those pointers — the ones dw-gate-11 flagged wrong (F1, F14) or missing (F6,
F9, F10) — contains the keyword the fact declares, at the CURRENTLY cited line(s); and F2 states
its two commands WITHOUT their output (dw-gate-11 obs 5, dw-gate-18 obs 1: the same count was
copied forward twice and did not reproduce either time — a count that grows daily is stale by
construction, so the template may not carry one at all).
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

# A long-form date first, so the alternation cannot consume "26-09" out of "2026-09-12" and leave
# "12" looking like a bare count. Only digits INSIDE one of these two shapes are allowed in F2.
DATE_TOKEN_RE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{2}-\d{2}")
DIGIT_RUN_RE = re.compile(r"\d+")

# argparse writes flags as "--slug SLUG" / "-h, --help"; long form only — the launcher has no
# single-letter flag of its own, and "-h" is argparse's, not the launcher's contract.
LONG_FLAG_RE = re.compile(r"--[a-z][a-z0-9-]*")
FLAGS_NOT_THE_LAUNCHERS_OWN = {"--help"}

# SKILL.md's own "## Source map": every CLI fact in the skill, named by the launcher SYMBOL that
# enforces it. A symbol, not a line — see the module docstring for why the mandate allows it and
# why it is the better guard here. This set is the curated half: it must equal what SKILL.md's
# table cites (both directions) and every member must still occur in the launcher.
LAUNCHER_SYMBOL_RE = re.compile(r"\(source:\s*scripts/dynamic_workflow\.py::([^)]+)\)")

_LAUNCHER_SYMBOLS = {
    "DEFAULT_TEMPLATE",
    "PROBE_TIMEOUT_S",
    "_ARSENAL_UNKNOWN_NOTE",
    "SEAT_TIMEOUTS",
    "_arsenal_liveness_block",
    "latency_ms",
    "_ledger_lock",
    "_is_md_separator_row",
    "validate_answer",
    "_normalise_seat_output",
    "_ensure_outside_repo",
    "template not found",
    "_SEALED_SENTENCE",
    "_launch_seat",
    "_seat_key",
    "already claimed by seat",
    "_cmd_r1_register",
    "_R2_PROMPT_PREFIX",
    "_filter_objection_paragraph",
    "r2-dead",
    "_check_c1",
    "_check_c5",
    "_check_c8",
    "JURY_AXES",
    "0 surviving formations",
    "_CAPTURE_REQUIRED",
    "_OUTCOME_KEYS",
}

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


def _help_text(*argv: str) -> str:
    return subprocess.run(
        [sys.executable, str(LAUNCHER), *argv, "--help"],
        capture_output=True, text=True, timeout=30, check=True,
    ).stdout


def _real_flags() -> dict[str, set[str]]:
    """{"": top-level flags} plus one entry per subcommand, read from the launcher's OWN --help
    screens rather than from a list kept here — a list would drift exactly the way SKILL.md did."""
    found = {"": set(LONG_FLAG_RE.findall(_help_text())) - FLAGS_NOT_THE_LAUNCHERS_OWN}
    for sub in sorted(_real_subcommands()):
        found[sub] = set(LONG_FLAG_RE.findall(_help_text(sub))) - FLAGS_NOT_THE_LAUNCHERS_OWN
    return found


def _fact_blocks(text: str) -> list[str]:
    """F1..F15's bodies, in order, as the two older tests split them — same split, one place."""
    section = text.split("## 1. Scouting report", 1)[1].split("## 2.", 1)[0]
    return re.split(r"\nF\d+\.", section)[1:]


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


def test_f2_carries_no_frozen_count():
    """§S S1. F2's two commands count commits, so their output grows every day the ledger is
    touched. The count was copied forward into the template twice and failed to reproduce both
    times (dw-gate-11 obs 5: 88/6 written, 86/4 measured; dw-gate-18 obs 1: 107 written, 104
    measured) — three reds on this deliverable, two of them this one line. The cure is not a
    fresher number, it is no number: F2 prints the commands, the convener runs them at brief time
    and the OUTPUT lives in the kit's own BRIEF.md. Enforced by shape, not by a blocklist of the
    counts that were wrong before: inside the F2 block, every digit run must be part of a date
    token, so any bare integer fails and names itself."""
    blocks = _fact_blocks(BRIEF_TEMPLATE.read_text(encoding="utf-8"))
    assert len(blocks) == 15, f"expected 15 fact blocks, split found {len(blocks)}"
    f2 = blocks[1]
    allowed = [m.span() for m in DATE_TOKEN_RE.finditer(f2)]
    for run in DIGIT_RUN_RE.finditer(f2):
        inside = any(lo <= run.start() and run.end() <= hi for lo, hi in allowed)
        assert inside, (
            f"F2 carries the digit run {run.group()!r} at char {run.start()} of its block, "
            f"outside any date token — a count in this template is stale by construction (§S "
            f"S1); print the command and let the convener paste its output into BRIEF.md"
        )


def test_every_launcher_flag_is_named_in_skill_md():
    """Converse of the subcommand check, one level down: a flag the launcher grew and the skill
    never learned is silent drift, and `r1 --register` was exactly that — the only path that
    turns a hand-pasted window answer into an `answered` row, absent from the skill for two PRs.
    Read from the launcher's own --help screens, so a new flag fails here the day it lands."""
    skill_text = SKILL_MD.read_text(encoding="utf-8")
    missing: list[str] = []
    for scope, flags in _real_flags().items():
        for flag in sorted(flags):
            if flag not in skill_text:
                missing.append(f"{scope or '<top-level>'} {flag}")
    assert not missing, (
        f"the launcher's --help exposes flag(s) SKILL.md never names: {missing} — document the "
        f"flag or the skill is describing a launcher that no longer exists"
    )


def test_curated_map_covers_every_launcher_symbol_in_skill_md():
    """SKILL.md's "## Source map" and `_LAUNCHER_SYMBOLS` must name the same set, both ways. A fact
    added to the table without curation, or a curated entry whose row was deleted, are the two
    halves of the same rot — a map nobody compares to the document it describes is decoration."""
    cited_now = set(LAUNCHER_SYMBOL_RE.findall(SKILL_MD.read_text(encoding="utf-8")))
    assert cited_now, "SKILL.md's Source map cites no launcher symbol — the section is missing"
    assert not cited_now - _LAUNCHER_SYMBOLS, (
        f"SKILL.md's Source map cites symbol(s) with no _LAUNCHER_SYMBOLS entry: "
        f"{sorted(cited_now - _LAUNCHER_SYMBOLS)}"
    )
    assert not _LAUNCHER_SYMBOLS - cited_now, (
        f"_LAUNCHER_SYMBOLS has entry/entries SKILL.md's Source map no longer cites: "
        f"{sorted(_LAUNCHER_SYMBOLS - cited_now)}"
    )


def test_every_launcher_symbol_occurs_in_the_launcher():
    """The half that makes the Source map evidence: each symbol must appear in the launcher at
    least once, as an exact substring. This is what goes red when an enforcement point is renamed
    or removed — i.e. when the skill has started describing a launcher that no longer exists —
    and it stays green through a line shift, which is the churn this repo actually produces."""
    assert _LAUNCHER_SYMBOLS, "launcher symbol map is empty — nothing to check"
    assert LAUNCHER.exists(), f"launcher missing: {LAUNCHER}"
    source = LAUNCHER.read_text(encoding="utf-8")
    absent = sorted(s for s in _LAUNCHER_SYMBOLS if s not in source)
    assert not absent, (
        f"SKILL.md's Source map names symbol(s) absent from {LAUNCHER.name}: {absent} — the fact's "
        f"enforcement point was renamed or deleted, so the skill is describing a launcher that is "
        f"no longer there; re-point the row to the symbol that enforces it now, or drop the claim"
    )
