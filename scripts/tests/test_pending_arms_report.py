"""Tests for scripts/pending_arms_report.py — the W81 PENDING-ARMS reconciliation report.

Module is imported via importlib.util.spec_from_file_location (not a package import)
because scripts/ is a flat bag of standalone tools, not a Python package.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

MODULE_PATH = Path(__file__).resolve().parent.parent / "pending_arms_report.py"
REAL_LEDGER_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / ".claude"
    / "skills"
    / "modus"
    / "PENDING-ARMS.md"
)


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("pending_arms_report", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


par = _load_module()

NOW = "2026-07-05"


# ---------------------------------------------------------------------------
# Synthetic ledger fixture
# ---------------------------------------------------------------------------

LEDGER_TEMPLATE = """\
# modus — PENDING-ARMS (the W81 ledger: built != armed)

> Format: `opened YYYY-MM-DD | artifact | missing arming step | owner (me|operator[<category>]) | proof-of-armed`

- opened 2026-06-25 | overdue tech debt artifact | wire the hook into settings.json | me | a live session shows the block
- opened 2026-07-05 | fresh me artifact | needs a restart to pick up | me | next restart log shows it
- opened 2026-06-20 | overdue operator artifact | waiting on operator GO | operator[business] | operator GO recorded
- opened 2026-06-01 | firebreak artifact | DELIBERATE FIREBREAK, not tech debt: waiting for signal quality before flip | operator[business] | operator GO + probe
- opened 2026-07-04 | phantom operator artifact | repo work parked behind a human lane that does not exist | operator | never

- opened 2026-07-01 | wrapped artifact spanning lines
  and continuing artifact description | missing step first part
  missing step continued | me | proof text starts
  proof continues here
- opened 2026-06-15 completely malformed line describing something broken with no pipe characters at all
- opened 2026-07-04 | boundary age one artifact | some step | me | some proof
- opened 2026-07-03 | boundary age two artifact | some step | me | some proof

## closed (proof recorded)

- closed 2026-01-01 | ancient closed artifact that would be a giant overdue tech-debt entry if the parser leaked past the heading | me | this line must NEVER be counted
- closed 2026-07-04 | some other closed thing | operator | PROVEN: irrelevant to open parsing
"""


@pytest.fixture()
def ledger_path(tmp_path: Path) -> Path:
    p = tmp_path / "PENDING-ARMS.md"
    p.write_text(LEDGER_TEMPLATE, encoding="utf-8")
    return p


@pytest.fixture()
def entries(ledger_path: Path):
    now = par._parse_now(NOW)
    return par.load_entries(ledger_path, now)


def _by_artifact(entries, needle: str):
    matches = [e for e in entries if needle in e.artifact]
    assert matches, f"no entry with artifact containing {needle!r} (have: {[e.artifact for e in entries]})"
    return matches[0]


# ---------------------------------------------------------------------------
# Parsing scope: only the open section, closed section never touched
# ---------------------------------------------------------------------------


def test_total_entry_count_excludes_closed_section(entries):
    assert len(entries) == 9


def test_closed_section_never_parsed(entries):
    for e in entries:
        assert "closed" not in e.artifact.lower()
        assert "ancient closed artifact" not in e.raw
    counts = par.compute_counts(entries)
    # If the closed ancient line leaked in, it would add another overdue tech-debt entry.
    assert counts["tech_debt_overdue"] == 3


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def test_overdue_tech_debt_classification(entries):
    e = _by_artifact(entries, "overdue tech debt artifact")
    assert e.cls == par.CLASS_TECH_DEBT
    assert e.owner == "me"
    assert e.overdue is True
    assert e.age_days == 10
    assert e.bucket == "TECH-DEBT-OVERDUE"


def test_fresh_me_classification(entries):
    e = _by_artifact(entries, "fresh me artifact")
    assert e.cls == par.CLASS_TECH_DEBT
    assert e.age_days == 0
    assert e.overdue is False
    assert e.bucket == "FRESH"


def test_overdue_operator_classification(entries):
    e = _by_artifact(entries, "overdue operator artifact")
    assert e.cls == par.CLASS_OPERATOR_GATED
    assert e.owner == "operator[business]"
    assert e.overdue is True
    assert e.bucket == "OPERATOR-GATED-OVERDUE"


def test_overdue_firebreak_classification(entries):
    e = _by_artifact(entries, "firebreak artifact")
    assert e.cls == par.CLASS_FIREBREAK
    assert e.owner == "operator[business]"
    assert e.overdue is True  # still objectively overdue by age...
    assert e.bucket == par.CLASS_FIREBREAK  # ...but bucketed as informational, not an alarm


def test_multiline_wrapped_entry_concatenated_and_classified(entries):
    e = _by_artifact(entries, "wrapped artifact spanning lines")
    assert "and continuing artifact description" in e.artifact
    assert e.owner == "me"
    assert "missing step first part" in e.missing_step
    assert "missing step continued" in e.missing_step
    assert "proof text starts" in e.proof
    assert "proof continues here" in e.proof
    assert e.cls == par.CLASS_TECH_DEBT
    assert e.overdue is True  # opened 2026-07-01, now 2026-07-05 => age 4


def test_malformed_line_reported_not_crashed(entries):
    malformed = [e for e in entries if e.malformed]
    assert len(malformed) == 1
    e = malformed[0]
    assert e.cls == par.CLASS_MALFORMED
    assert e.bucket == par.CLASS_MALFORMED
    assert any("pipe-segment" in r for r in e.malformed_reasons)
    # opened-date still parses fine for this one; only the pipe count is the defect.
    assert e.opened_date is not None


# ---------------------------------------------------------------------------
# PHANTOM-OPERATOR — "io sono te, non c'è nessun operatore" (Zero, 2026-07-06)
# Guilt: untagged/unknown/Italian operator owners must be flagged.
# Innocence: every true-operator category and 'me' owners must NOT be flagged.
# ---------------------------------------------------------------------------


def _single_entry(tmp_path: Path, line: str):
    p = tmp_path / "PENDING-ARMS.md"
    p.write_text(line + "\n\n## closed (proof recorded)\n", encoding="utf-8")
    now = par._parse_now(NOW)
    entries = par.load_entries(p, now)
    assert len(entries) == 1
    return entries[0]


def test_guilt_untagged_operator_is_phantom(entries):
    e = _by_artifact(entries, "phantom operator artifact")
    assert e.cls == par.CLASS_PHANTOM_OPERATOR
    # never FRESH even at age 1: a phantom is wrong the moment it is written.
    assert e.age_days == 1
    assert e.bucket == par.CLASS_PHANTOM_OPERATOR


def test_guilt_unknown_category_is_phantom(tmp_path):
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | unknown tag artifact | some step | operator[vibes] | proof",
    )
    assert e.cls == par.CLASS_PHANTOM_OPERATOR


def test_guilt_italian_operatore_is_phantom(tmp_path):
    # W82 under-match guard: Italian prose must not slip through as TECH-DEBT.
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | italian artifact | qualche passo | operatore o sessione Pro | prova",
    )
    assert e.cls == par.CLASS_PHANTOM_OPERATOR


def test_guilt_mixed_valid_and_unknown_tags_is_phantom(tmp_path):
    # ALL declared tags must be true-operator categories; one bad tag poisons the claim.
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | mixed tags artifact | step | operator[gui] + operator[vibes] | proof",
    )
    assert e.cls == par.CLASS_PHANTOM_OPERATOR


def test_innocence_every_true_category_is_operator_gated(tmp_path):
    for cat in sorted(par.TRUE_OPERATOR_CATEGORIES):
        e = _single_entry(
            tmp_path,
            f"- opened 2026-07-05 | {cat} artifact | step | operator[{cat}] | proof",
        )
        assert e.cls == par.CLASS_OPERATOR_GATED, f"category {cat!r} wrongly flagged"


def test_innocence_mixed_owner_with_tag_is_operator_gated(tmp_path):
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | mixed owner artifact | step | operator[secret] (env review) + me (prune patch) | proof",
    )
    assert e.cls == par.CLASS_OPERATOR_GATED


def test_innocence_me_owner_is_never_phantom(entries):
    e = _by_artifact(entries, "fresh me artifact")
    assert e.cls == par.CLASS_TECH_DEBT


def test_innocence_operator_word_only_in_proof_not_flagged(tmp_path):
    # The owner field decides — 'operator' appearing in proof text must not trip the flag.
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | proof mention artifact | step | me | operator GO recorded in log",
    )
    assert e.cls == par.CLASS_TECH_DEBT


def test_firebreak_precedence_over_phantom_documented(tmp_path):
    # Pre-existing precedence: an explicit 'firebreak' in the raw text wins the
    # classification even with an untagged operator owner. Documented, not accidental.
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | firebreak precedence artifact | DELIBERATE FIREBREAK by design | operator | n/a",
    )
    assert e.cls == par.CLASS_FIREBREAK


def test_strict_exits_1_on_fresh_phantom_alone(tmp_path, capsys):
    ledger = "- opened 2026-07-05 | lone phantom artifact | step | operator | proof\n\n## closed\n"
    p = tmp_path / "PENDING-ARMS.md"
    p.write_text(ledger, encoding="utf-8")
    code = par.main(["--ledger", str(p), "--now", NOW, "--strict"])
    assert code == 1  # regardless of age (entry is fresh, age 0)


def test_strict_phantom_exits_1_on_phantom_only(tmp_path, capsys):
    ledger = "- opened 2026-07-05 | lone phantom artifact | step | operator | proof\n\n## closed\n"
    p = tmp_path / "PENDING-ARMS.md"
    p.write_text(ledger, encoding="utf-8")
    code = par.main(["--ledger", str(p), "--now", NOW, "--strict-phantom"])
    assert code == 1


def test_strict_phantom_ignores_overdue_tech_debt(tmp_path, capsys):
    # The narrow CI gate: pre-existing overdue debt never blocks an innocent PR.
    ledger = "- opened 2026-06-01 | old debt artifact | step | me | proof\n\n## closed\n"
    p = tmp_path / "PENDING-ARMS.md"
    p.write_text(ledger, encoding="utf-8")
    assert par.main(["--ledger", str(p), "--now", NOW, "--strict-phantom"]) == 0
    assert par.main(["--ledger", str(p), "--now", NOW, "--strict"]) == 1


# ---------------------------------------------------------------------------
# Overdue boundary: age 1 day = fresh, age 2 days = overdue
# ---------------------------------------------------------------------------


def test_overdue_boundary_age_one_is_fresh(entries):
    e = _by_artifact(entries, "boundary age one artifact")
    assert e.age_days == 1
    assert e.overdue is False
    assert e.bucket == "FRESH"


def test_overdue_boundary_age_two_is_overdue(entries):
    e = _by_artifact(entries, "boundary age two artifact")
    assert e.age_days == 2
    assert e.overdue is True
    assert e.bucket == "TECH-DEBT-OVERDUE"


# ---------------------------------------------------------------------------
# counts()
# ---------------------------------------------------------------------------


def test_compute_counts_matches_expected_distribution(entries):
    counts = par.compute_counts(entries)
    assert counts == {
        "total": 9,
        "phantom_operator": 1,
        "tech_debt_overdue": 3,  # overdue-tech-debt, wrapped, boundary-age-two
        "operator_gated_overdue": 1,
        "firebreak": 1,
        "natural_wait": 0,
        "fresh": 2,  # fresh-me, boundary-age-one
        "malformed": 1,
    }


# ---------------------------------------------------------------------------
# CLI: --strict exit codes
# ---------------------------------------------------------------------------


def test_strict_exits_1_when_overdue_tech_debt_present(ledger_path, capsys):
    code = par.main(["--ledger", str(ledger_path), "--now", NOW, "--strict"])
    assert code == 1


def test_strict_exits_0_without_overdue_tech_debt(tmp_path, capsys):
    only_firebreak_and_operator = """\
- opened 2026-06-01 | firebreak only artifact | DELIBERATE FIREBREAK not tech debt | operator[business] | operator GO
- opened 2026-06-10 | operator only artifact | waiting on operator | operator[gui] | operator GO recorded

## closed (proof recorded)
"""
    p = tmp_path / "PENDING-ARMS.md"
    p.write_text(only_firebreak_and_operator, encoding="utf-8")
    code = par.main(["--ledger", str(p), "--now", NOW, "--strict"])
    assert code == 0


def test_non_strict_always_exits_0_even_with_overdue_tech_debt(ledger_path, capsys):
    code = par.main(["--ledger", str(ledger_path), "--now", NOW])
    assert code == 0


# ---------------------------------------------------------------------------
# CLI: default markdown report
# ---------------------------------------------------------------------------


def test_report_sections_present_and_populated(ledger_path, capsys):
    code = par.main(["--ledger", str(ledger_path), "--now", NOW])
    assert code == 0
    out = capsys.readouterr().out
    assert "## PHANTOM-OPERATOR" in out
    assert "## TECH-DEBT overdue (>48h)" in out
    assert "## OPERATOR-GATED overdue" in out
    assert "## FIREBREAK (legitimate, informational)" in out
    assert "## Fresh (<48h)" in out
    assert "## MALFORMED" in out
    assert "overdue tech debt artifact" in out
    assert "phantom operator artifact" in out
    assert "ancient closed artifact" not in out
    # PHANTOM-OPERATOR is the loudest bucket: its section comes first.
    assert out.index("## PHANTOM-OPERATOR") < out.index("## TECH-DEBT overdue")


def test_report_empty_section_says_none(tmp_path, capsys):
    only_fresh = """\
- opened 2026-07-05 | only fresh artifact | some step | me | some proof

## closed (proof recorded)
"""
    p = tmp_path / "PENDING-ARMS.md"
    p.write_text(only_fresh, encoding="utf-8")
    code = par.main(["--ledger", str(p), "--now", NOW])
    assert code == 0
    out = capsys.readouterr().out
    # every non-Fresh section should say "none"
    for heading in (
        "## PHANTOM-OPERATOR",
        "## TECH-DEBT overdue (>48h)",
        "## OPERATOR-GATED overdue",
        "## FIREBREAK (legitimate, informational)",
        "## MALFORMED",
    ):
        section = out.split(heading, 1)[1].splitlines()[1].strip()
        assert section == "none"


# ---------------------------------------------------------------------------
# CLI: --json structure
# ---------------------------------------------------------------------------


def test_json_output_structure(ledger_path, capsys):
    code = par.main(["--ledger", str(ledger_path), "--now", NOW, "--json"])
    assert code == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["now"] == NOW
    assert payload["counts"] == {
        "total": 9,
        "phantom_operator": 1,
        "tech_debt_overdue": 3,
        "operator_gated_overdue": 1,
        "firebreak": 1,
        "natural_wait": 0,
        "fresh": 2,
        "malformed": 1,
    }
    assert len(payload["entries"]) == 9
    fields = {"opened", "age_days", "artifact", "owner", "class", "overdue", "raw_head"}
    for entry in payload["entries"]:
        assert fields.issubset(entry.keys())

    firebreak_entries = [e for e in payload["entries"] if e["class"] == "FIREBREAK"]
    assert len(firebreak_entries) == 1
    assert firebreak_entries[0]["overdue"] is True


# ---------------------------------------------------------------------------
# CLI: missing ledger file
# ---------------------------------------------------------------------------


def test_missing_ledger_exits_2(tmp_path, capsys):
    missing = tmp_path / "does-not-exist.md"
    code = par.main(["--ledger", str(missing), "--now", NOW])
    assert code == 2
    err = capsys.readouterr().err
    assert "not found" in err


# ---------------------------------------------------------------------------
# Smoke test against the REAL ledger
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not REAL_LEDGER_PATH.exists(),
    reason=f"real ledger not found at {REAL_LEDGER_PATH} (CI checkout may not have it)",
)
def test_smoke_real_ledger_parses_without_exception():
    now = par._parse_now(NOW)
    entries = par.load_entries(REAL_LEDGER_PATH, now)
    assert len(entries) >= 1
    # never crashes even on malformed entries; every entry has a bucket.
    for e in entries:
        assert e.bucket in {
            par.CLASS_MALFORMED,
            par.CLASS_PHANTOM_OPERATOR,
            par.CLASS_NATURAL_WAIT,
            par.CLASS_FIREBREAK,
            "TECH-DEBT-OVERDUE",
            "OPERATOR-GATED-OVERDUE",
            "FRESH",
        }


@pytest.mark.skipif(
    not REAL_LEDGER_PATH.exists(),
    reason=f"real ledger not found at {REAL_LEDGER_PATH} (CI checkout may not have it)",
)
def test_real_ledger_has_zero_phantom_operator():
    """The living enforcement of 'non c'è nessun operatore' (Zero, 2026-07-06).

    Every open entry whose owner claims an operator lane must declare a
    true-operator category as operator[<cat>]. This test turns any new phantom
    line in the REAL ledger into a red CI check the moment it is written.
    """
    now = par._parse_now(NOW)
    entries = par.load_entries(REAL_LEDGER_PATH, now)
    phantoms = [e for e in entries if e.cls == par.CLASS_PHANTOM_OPERATOR]
    assert not phantoms, (
        "PHANTOM-OPERATOR entries in the real ledger (owner says 'operator' with no "
        "true-operator category — re-own to a session or tag operator[<cat>]): "
        + "; ".join(e.artifact or e.raw[:80] for e in phantoms)
    )


# ---- NATURAL-WAIT: passive owner waiting on a dated calendar trigger ---------
# Born 2026-07-06: two `me (passivo — verifica 07-12)` lines classified TECH-DEBT
# overdue kept healer receptor 1 actionable EVERY tick, starving the genome
# convergence idle branch for the whole wait week.


def test_guilt_passivo_owner_is_natural_wait_not_overdue(tmp_path):
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-02 | yield proof artifact | wait for sunday trigger "
        "| me (passivo — verifica 07-12) | log entry post 07-12",
    )
    assert e.cls == par.CLASS_NATURAL_WAIT
    assert e.age_days == 3  # would be overdue as TECH-DEBT...
    assert e.bucket == par.CLASS_NATURAL_WAIT  # ...but never buckets -OVERDUE


def test_guilt_strict_exit_0_on_natural_wait_alone(tmp_path, capsys):
    p = tmp_path / "PENDING-ARMS.md"
    p.write_text(
        "- opened 2026-07-02 | waiting artifact | wait | me (passivo) | proof at trigger\n"
        "\n## closed (proof recorded)\n",
        encoding="utf-8",
    )
    assert par.main(["--ledger", str(p), "--now", NOW, "--strict"]) == 0


def test_guilt_english_passive_owner_is_natural_wait(tmp_path):
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-02 | en artifact | wait | me (passive — monday run) | proof",
    )
    assert e.cls == par.CLASS_NATURAL_WAIT


def test_innocence_bare_me_stays_overdue_tech_debt(tmp_path, capsys):
    p = tmp_path / "PENDING-ARMS.md"
    p.write_text(
        "- opened 2026-07-02 | plain artifact | do the work | me | proof\n"
        "\n## closed (proof recorded)\n",
        encoding="utf-8",
    )
    now = par._parse_now(NOW)
    (e,) = par.load_entries(p, now)
    assert e.cls == par.CLASS_TECH_DEBT
    assert e.bucket == f"{par.CLASS_TECH_DEBT}-OVERDUE"
    assert par.main(["--ledger", str(p), "--now", NOW, "--strict"]) == 1


def test_innocence_impassivo_is_not_natural_wait(tmp_path):
    # word boundary (#3): "impassivo" must not open the passive lane
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-02 | boundary artifact | step | me (impassivo) | proof",
    )
    assert e.cls == par.CLASS_TECH_DEBT


def test_innocence_passivo_in_body_not_owner_stays_tech_debt(tmp_path):
    # only the OWNER field declares the wait; prose quoting "passivo" must not
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-02 | body artifact | il log dice watch passivo del receptor | me | proof",
    )
    assert e.cls == par.CLASS_TECH_DEBT


def test_innocence_operator_tag_with_passive_note_stays_operator_gated(tmp_path):
    # operator[gui] + passive wording: the operator category is the stronger claim?
    # NO — the wait is declared, and a passive wait is not actionable either way;
    # but the owner names a true category, so keep the OPERATOR-GATED class:
    # classification order puts NATURAL-WAIT first, so document the actual outcome.
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-02 | tagged artifact | step | operator[gui] (passivo) | proof",
    )
    assert e.cls == par.CLASS_NATURAL_WAIT  # declared passive wait wins: not actionable


# ---------------------------------------------------------------------------
# "open" vs "opened" verb-tense drift (real ledger has 14 lines missing "-ed",
# silently discarded by a bare "- opened " prefix check as an unrelated list
# item — family #3 under-match: the guard watched one literal spelling).
# ---------------------------------------------------------------------------


def test_guilt_open_without_ed_is_parsed_as_entry(tmp_path):
    e = _single_entry(
        tmp_path,
        "- open 2026-07-01 | dropped-ed artifact | some step | me | some proof",
    )
    assert e.cls == par.CLASS_TECH_DEBT
    assert e.artifact == "dropped-ed artifact"
    assert e.age_days == 4  # NOW (fixed in _single_entry) is 2026-07-05
    assert e.overdue is True
    assert e.bucket == "TECH-DEBT-OVERDUE"


def test_guilt_open_without_ed_continuation_lines_concatenated(tmp_path):
    p = tmp_path / "PENDING-ARMS.md"
    p.write_text(
        "- open 2026-07-02 | wrapped dropped-ed artifact\n"
        "  continuation line | missing step | me | proof\n"
        "\n## closed (proof recorded)\n",
        encoding="utf-8",
    )
    now = par._parse_now(NOW)
    (e,) = par.load_entries(p, now)
    assert "continuation line" in e.artifact or "continuation line" in e.raw
    assert e.cls == par.CLASS_TECH_DEBT
    assert e.overdue is True


def test_guilt_open_without_ed_operator_gated_classified(tmp_path):
    e = _single_entry(
        tmp_path,
        "- open 2026-07-05 | dropped-ed operator artifact | step | operator[secret] | proof",
    )
    assert e.cls == par.CLASS_OPERATOR_GATED


def test_innocence_opened_still_parses_unaffected(entries):
    # pre-existing "- opened " entries must be completely unaffected by the change.
    e = _by_artifact(entries, "overdue tech debt artifact")
    assert e.cls == par.CLASS_TECH_DEBT
    assert e.overdue is True


def test_innocence_open_prose_without_date_not_swallowed_as_entry(tmp_path):
    # unrelated "- open ..." prose (no YYYY-MM-DD immediately after) must NOT be
    # mistaken for a ledger entry — the date anchor in ENTRY_START_RE prevents this.
    p = tmp_path / "PENDING-ARMS.md"
    p.write_text(
        "- opened 2026-07-05 | real artifact | step | me | proof\n"
        "- open source library consideration, not a ledger line\n"
        "\n## closed (proof recorded)\n",
        encoding="utf-8",
    )
    now = par._parse_now(NOW)
    parsed = par.load_entries(p, now)
    assert len(parsed) == 1
    assert parsed[0].artifact == "real artifact"
    assert "open source library" not in parsed[0].raw


# ---------------------------------------------------------------------------
# Backtick-quoted pipes & trailing "**UPDATE**" notes (2026-07-11/13 field-parser
# fix). A naive raw.split("|") breaks the moment free-text quotes a shell pipe or
# regex alternation in backticks, AND separately breaks when a session appends a
# "| **UPDATE ...**" progress note after proof — both silently shift owner/proof
# extraction onto a code fragment or the appended note instead of the real fields
# (found live: 4 real ledger entries, incl. "WR2 legacy Canva lane zombies").
# ---------------------------------------------------------------------------


def test_guilt_backtick_quoted_regex_pipes_do_not_corrupt_owner(tmp_path):
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | quoted pipe artifact | some step "
        "| me (follow-up) + operator[business] on scope "
        '| `launchctl list \\| grep -E "svc-(oauth|renderer|apply)"` shows only kept labels',
    )
    assert e.owner == "me (follow-up) + operator[business] on scope"
    assert "renderer" not in e.owner
    assert e.cls == par.CLASS_OPERATOR_GATED


def test_guilt_trailing_update_note_does_not_shift_owner(tmp_path):
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | update note artifact | some step | me (follow-up PR) "
        "| original proof text | **UPDATE 2026-07-12: progress note appended later, "
        "PR #9999 merged, re-verified live**",
    )
    assert e.owner == "me (follow-up PR)"
    assert e.proof.startswith("original proof text")
    assert "**UPDATE 2026-07-12" in e.proof


def test_innocence_middle_extra_field_still_resolves_via_back_anchor(tmp_path):
    # 'codex-redteam MCP server'-style: a session inserts an EXTRA field between
    # missing_step and owner (not a "**UPDATE**"-prefixed trailing note) — back
    # anchoring from the outside-in must still land on the real owner/proof, not
    # front-anchor onto the inserted field (the earlier draft of this fix did that
    # and broke this exact shape).
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | mid-growth artifact | first step note "
        "| BLOCCO discovered later: an inserted blocker note, not the owner "
        "| me (real owner) + operator[control-plane] | real proof text",
    )
    assert e.owner == "me (real owner) + operator[control-plane]"
    assert e.proof == "real proof text"
    assert e.cls == par.CLASS_OPERATOR_GATED


def test_innocence_backticks_without_pipes_parse_normally(tmp_path):
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | backtick artifact `code_ref.py:42` | step | me | proof `value`",
    )
    assert e.artifact == "backtick artifact `code_ref.py:42`"
    assert e.owner == "me"
    assert e.proof == "proof `value`"


def test_innocence_unbalanced_backtick_falls_back_to_naive_split(tmp_path):
    # Malformed markdown (odd backtick count) degrades to the naive split rather
    # than treating the rest of the line as one giant quoted span.
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | odd backtick artifact ` | step | me | proof",
    )
    assert e.owner == "me"


@pytest.mark.skipif(
    not REAL_LEDGER_PATH.exists(),
    reason=f"real ledger not found at {REAL_LEDGER_PATH} (CI checkout may not have it)",
)
def test_real_ledger_wr2_canva_owner_not_corrupted_by_quoted_pipes():
    """Regression for the exact bug the real ledger documented (age 2d, 2026-07-11):
    a backtick-quoted regex-alternation shell command inside the 'WR2 legacy Canva
    lane zombies' entry corrupted owner extraction to a bare code fragment.
    """
    now = par._parse_now(NOW)
    entries = par.load_entries(REAL_LEDGER_PATH, now)
    e = next(x for x in entries if "WR2 legacy Canva lane zombies" in x.artifact)
    assert "renderer" != e.owner
    assert "me" in e.owner or "operator" in e.owner.lower()
