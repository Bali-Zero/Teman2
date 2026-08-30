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


def test_innocence_negated_operator_disclaimer_is_not_phantom(tmp_path):
    # Live 2026-08-30 (healer tick): owner text explicitly DENIES claiming an
    # operator lane ("not operator-gated") — plain substring matching on
    # "operator" cannot see the negation and misread this as a phantom claim.
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | negated disclaimer artifact | step | "
        "next BUILD session (repo-side; not operator-gated) | proof",
    )
    assert e.cls == par.CLASS_TECH_DEBT


def test_guilt_negation_does_not_rescue_a_real_operator_tag(tmp_path):
    # A negated aside elsewhere in the owner must NOT rescue a genuinely
    # untagged/mis-tagged operator claim living alongside it.
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | mixed negation artifact | step | "
        "operator[vibes] (not operator-gated for the other half) | proof",
    )
    assert e.cls == par.CLASS_PHANTOM_OPERATOR


def test_guilt_bare_operator_word_unaffected_by_negation_regex(tmp_path):
    # Regression pin: bare "operator" (no "not" nearby) must still phantom.
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | bare operator artifact | step | operator | proof",
    )
    assert e.cls == par.CLASS_PHANTOM_OPERATOR


def test_innocence_negated_operator_with_hedge_words_is_not_phantom(tmp_path):
    # Live 2026-08-30 (round 2): PR #5233's own PENDING-ARMS row — "NOT a bare
    # operator" — was flagged PHANTOM-OPERATOR because the original
    # NEGATED_OPERATOR_RE required "not" immediately adjacent to "operator"
    # with zero words of slack, and "a bare" sits between them here. This
    # pins the exact reported text (not a paraphrase) so the regression
    # cannot silently reopen on a rewording of the fix.
    e = _single_entry(
        tmp_path,
        "- opened 2026-08-29 | pr5233 evidence pack artifact | step | "
        "the independently-dispatched Gear-3 gate session (harness/fable-gate "
        "poster) — NOT this implementer session, NOT a bare operator | proof",
    )
    assert e.cls == par.CLASS_TECH_DEBT


def test_guilt_negated_operator_with_wide_gap_still_phantom(tmp_path):
    # The hedge-word gap is a small CLOSED vocabulary, not an open wildcard:
    # an unrelated "not" several ordinary words upstream of a genuinely bare
    # "operator" must NOT rescue it — that would be the exact over-correction
    # the fix was warned against (a fix that lets real phantom rows through
    # is worse than the false positive it replaces).
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | wide gap artifact | step | "
        "not yet resolved — assign to operator | proof",
    )
    assert e.cls == par.CLASS_PHANTOM_OPERATOR


def test_guilt_mixed_naked_mentions_only_one_negated_is_phantom(tmp_path):
    # Second latent gap closed alongside the widening: the original call site
    # was NEGATED_OPERATOR_RE.search(owner), a bare EXISTENCE check — an
    # owner naming two "operator" mentions where only the first is negated
    # would have been waved through on the strength of that one match. Every
    # naked mention must now be individually covered.
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | mixed mentions artifact | step | "
        "not operator, but flag for operator eventually | proof",
    )
    assert e.cls == par.CLASS_PHANTOM_OPERATOR


def test_guilt_negation_gap_wider_than_closed_vocabulary_still_phantom(tmp_path):
    # Independently verified 2026-08-30 (team-lead, re-exercising
    # _all_operator_mentions_negated directly rather than taking the PR's
    # report on trust). A 4-word gap of ordinary words ("a completely
    # unrelated distant") falls outside the closed hedge-word vocabulary, so
    # this reads as PHANTOM-OPERATOR even though a human would parse it as a
    # denial. That is a false positive, and it fails in the SAFE direction
    # for this guard (see the docstring on _all_operator_mentions_negated):
    # a row a human would call innocent still surfaces for a manual reword,
    # it never lets a genuine bare-operator claim through unflagged. Do not
    # widen the vocabulary to rescue this specific phrasing unless it
    # actually blocks a real PR — see the WIDENED history in the code for
    # why open-ended widening is the failure mode this bounds against.
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | wide-gap-vocab artifact | step | "
        "not a completely unrelated distant operator | proof",
    )
    assert e.cls == par.CLASS_PHANTOM_OPERATOR


def test_guilt_trailing_naked_mention_after_negation_still_phantom(tmp_path):
    # Independently verified 2026-08-30 (team-lead). A second, bare, un-
    # negated "operator" trailing after a negated one is not rescued by the
    # negated mention earlier in the field — this is exactly what
    # _all_operator_mentions_negated's "EVERY mention" check (not a bare
    # existence check) exists to catch. Also a false positive in the SAFE
    # direction: a human might read "NOT a human, operator" as a single
    # disclaiming clause, but the classifier cannot tell that from a
    # genuine trailing bare claim, and refusing to guess is the correct
    # bias for a guard whose failure mode is a vanished obligation.
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | trailing-mention artifact | step | "
        "NOT a human, operator | proof",
    )
    assert e.cls == par.CLASS_PHANTOM_OPERATOR


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


# ---------------------------------------------------------------------------
# Trailing-pipe residual (2026-07-13, found the day AFTER the splitter fix
# landed): a stray '|' at the END of a line yields an EMPTY last field, so the
# back-anchor reads proof='' and owner=<the real proof> — the 'secrets audit
# Pro enrichment' entry (owner operator[secret]) landed in TECH-DEBT this way.
# ---------------------------------------------------------------------------


def test_guilt_trailing_pipe_empty_field_does_not_shift_owner(tmp_path):
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | trailing pipe artifact | some step "
        "| operator[secret] (env review) | PR #2081 merged + rerun exit 0 |",
    )
    assert e.owner == "operator[secret] (env review)"
    assert e.proof.startswith("PR #2081 merged")
    assert e.cls == par.CLASS_OPERATOR_GATED


def test_guilt_multiple_trailing_pipes_all_stripped(tmp_path):
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | double pipe artifact | some step "
        "| me (session) | real proof ||",
    )
    assert e.owner == "me (session)"
    assert e.proof == "real proof"


def test_innocence_five_field_entry_with_empty_proof_not_eaten(tmp_path):
    """A 5-field entry whose PROOF is genuinely empty ('... | owner |') keeps its
    owner anchored — the trailing-empty strip is guarded by len > 5, so it only
    eats SURPLUS residue, never a field a well-formed entry needs."""
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | empty proof artifact | some step | me (session M5) |",
    )
    assert e.owner == "me (session M5)"
    assert e.proof == ""
    assert e.cls == par.CLASS_TECH_DEBT


@pytest.mark.skipif(
    not REAL_LEDGER_PATH.exists(),
    reason=f"real ledger not found at {REAL_LEDGER_PATH} (CI checkout may not have it)",
)
def test_real_ledger_secrets_audit_owner_not_shifted_by_trailing_pipe():
    """The live mis-bucket this fix cures: the 'secrets audit Pro enrichment'
    entry ends with a stray '|' — its operator[secret] owner must classify
    OPERATOR-GATED, not TECH-DEBT with the proof text as owner."""
    now = par._parse_now(NOW)
    entries = par.load_entries(REAL_LEDGER_PATH, now)
    e = next(x for x in entries if "secrets audit Pro enrichment" in x.artifact)
    assert "operator[secret]" in e.owner
    assert e.cls == par.CLASS_OPERATOR_GATED


# ---------------------------------------------------------------------------
# Stray conflict-marker corruption (found live 2026-07-26: `||||||| ebfbd71019`
# baked as origin/main's own committed last line silently blanked the owner of
# the entry above it — TECH-DEBT/FRESH, invisible to both --strict and
# --strict-phantom, because an unparseable owner never tripped the pipe-count
# malformed check (still >=3 fields, just mostly empty) and never contained
# the substring "operator"). Two-layer cure: (1) extract_open_entries refuses
# to absorb a conflict-marker-shaped line into the entry being built, and
# instead surfaces the marker as its own MALFORMED entry; (2) parse_entry
# flags ANY empty/unparseable owner as MALFORMED regardless of how it got
# that way — a backstop for corruption vectors other than this exact marker.
# Both --strict and --strict-phantom now exit 1 on >=1 MALFORMED entry.
#
# Cross-family review (2026-07-26, same day) found two more gaps in the
# first pass of this fix. (P1) a 4-field entry with NO owner segment at all
# (`| artifact | missing step | proof`) silently assigns the missing_step
# text as owner instead of being flagged malformed — raising the pipe-count
# floor from `< 3` to `< 5` would catch it, but measured against the real
# ledger that floor flagged 45/225 (20%) legitimate entries that use a
# DIFFERENT 4-field shape (artifact + owner + proof, no missing_step —
# mostly FIREBREAK-style) with correctly-extracted real owners. That
# regression is worse than the gap it would close, so the floor fix was
# REJECTED and the gap is deliberately left open and pinned by a test below
# (test_known_gap_four_field_entry_missing_owner_segment_not_caught). (P2,
# FIXED) CONFLICT_MARKER_RE alone could not tell a REAL orphaned marker from
# one deliberately quoted inside a ``` fenced code block to illustrate it —
# extract_open_entries now tracks fence state and treats everything between
# a ``` pair as opaque literal content, exempt from every structural check.
# Also narrowed the marker set from 4 shapes to 3 (dropped bare `=======`,
# which is also valid Markdown Setext-underline/divider syntax and was never
# the shape either live orphaned marker actually took).
# ---------------------------------------------------------------------------


def test_guilt_empty_owner_field_is_malformed_not_tech_debt(tmp_path):
    # Directly exercises the parse_entry-level backstop, independent of the
    # extract-level marker guard: an explicitly empty owner field between two
    # real pipes must never resolve to ordinary TECH-DEBT.
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | empty owner artifact | some step | | some proof",
    )
    assert e.cls == par.CLASS_MALFORMED
    assert e.bucket == par.CLASS_MALFORMED
    assert any("owner" in r.lower() for r in e.malformed_reasons)


def test_guilt_trailing_conflict_marker_becomes_its_own_malformed_entry(tmp_path):
    # The exact live shape: a well-formed entry immediately followed (no
    # blank line) by a stray `|||||||` marker with no matching
    # <<<<<<</=======/>>>>>>> anywhere in the file.
    ledger = (
        "- opened 2026-07-05 | marker artifact | some step | me (session) | some proof\n"
        "||||||| ebfbd71019\n"
        "\n## closed\n"
    )
    p = tmp_path / "PENDING-ARMS.md"
    p.write_text(ledger, encoding="utf-8")
    now = par._parse_now(NOW)
    entries = par.load_entries(p, now)
    assert len(entries) == 2

    real = next(e for e in entries if e.artifact == "marker artifact")
    assert real.owner == "me (session)"
    assert real.proof == "some proof"
    assert real.cls == par.CLASS_TECH_DEBT  # protected from corruption, not malformed

    marker = next(e for e in entries if e is not real)
    assert marker.cls == par.CLASS_MALFORMED
    assert "ebfbd71019" in marker.raw


@pytest.mark.parametrize("marker", ["<<<<<<<", ">>>>>>>", "|||||||"])
def test_guilt_all_three_detected_conflict_marker_shapes_are_malformed(tmp_path, marker):
    ledger = (
        "- opened 2026-07-05 | pre-marker artifact | some step | me | some proof\n"
        f"{marker} some-ref-or-hash\n"
        "\n## closed\n"
    )
    p = tmp_path / "PENDING-ARMS.md"
    p.write_text(ledger, encoding="utf-8")
    now = par._parse_now(NOW)
    entries = par.load_entries(p, now)
    assert len(entries) == 2
    real = next(e for e in entries if e.artifact == "pre-marker artifact")
    assert real.owner == "me"
    assert real.cls == par.CLASS_TECH_DEBT
    marker_entry = next(e for e in entries if e is not real)
    assert marker_entry.cls == par.CLASS_MALFORMED


def test_guilt_strict_phantom_exits_1_on_conflict_marker_alone(tmp_path, capsys):
    ledger = (
        "- opened 2026-07-05 | marker-only artifact | some step | me | some proof\n"
        "||||||| deadbeef1234\n"
        "\n## closed\n"
    )
    p = tmp_path / "PENDING-ARMS.md"
    p.write_text(ledger, encoding="utf-8")
    assert par.main(["--ledger", str(p), "--now", NOW, "--strict-phantom"]) == 1
    assert par.main(["--ledger", str(p), "--now", NOW, "--strict"]) == 1


def test_innocence_clean_ledger_strict_phantom_exits_0(tmp_path, capsys):
    ledger = "- opened 2026-07-05 | clean artifact | some step | me | some proof\n\n## closed\n"
    p = tmp_path / "PENDING-ARMS.md"
    p.write_text(ledger, encoding="utf-8")
    assert par.main(["--ledger", str(p), "--now", NOW, "--strict-phantom"]) == 0


def test_innocence_short_equals_run_not_treated_as_marker(tmp_path):
    # 4 '=' characters, well under the 7-char conflict-marker threshold — a
    # legitimate continuation line using '====' as a text divider must still
    # concatenate normally, not be mistaken for a stray '=======' marker.
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | divider artifact | first step part\n"
        "==== continued after a short divider ==== | me | proof",
    )
    assert "continued after a short divider" in e.missing_step
    assert e.owner == "me"
    assert e.cls == par.CLASS_TECH_DEBT


def test_innocence_bare_seven_equals_not_treated_as_marker(tmp_path):
    # Deliberate design choice (cross-family review, 2026-07-26): a bare
    # `=======` run is ALSO valid Markdown Setext-heading-underline/divider
    # syntax, and neither live orphaned marker found in this ledger was ever
    # this shape (both were `|||||||`) — excluded from CONFLICT_MARKER_RE, so
    # a continuation line using it as a divider must still concatenate.
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | equals divider artifact | first step part\n"
        "======= continued after a bare divider | me | proof",
    )
    assert "continued after a bare divider" in e.missing_step
    assert e.owner == "me"
    assert e.cls == par.CLASS_TECH_DEBT


def test_known_gap_four_field_entry_missing_owner_segment_not_caught(tmp_path):
    # P1 raised by cross-family review (2026-07-26), then DELIBERATELY NOT
    # fixed the way first proposed. A 4-field entry omitting the owner
    # segment entirely (`| artifact | missing step | proof`, no separate
    # owner) back-anchors the missing_step TEXT into owner instead of being
    # flagged. Raising the pipe-count floor from `< 3` to `< 5` WOULD catch
    # this shape — but measured against the real ledger, 45/225 open entries
    # (20%) use a DIFFERENT, legitimate 4-field shape (artifact + owner +
    # proof, no separate missing_step — mostly FIREBREAK-style), every one
    # with a correctly-extracted real owner; a `< 5` floor flagged all 45 as
    # MALFORMED. That regression is far worse than this narrower, unobserved
    # gap, so the floor stays at `< 3` and this shape is a documented,
    # accepted miss — pinned here so it isn't silently "fixed" again without
    # re-checking against the real corpus first.
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | four field artifact | missing step | proof",
    )
    assert e.cls == par.CLASS_TECH_DEBT  # known gap: NOT malformed
    assert e.owner == "missing step"  # wrong, but this is the accepted trade-off


def test_innocence_marker_example_inside_code_fence_not_treated_as_real(tmp_path):
    # P2 found by cross-family review (2026-07-26): a marker-shaped line
    # deliberately quoted inside a fenced code block to ILLUSTRATE a marker
    # (e.g. documentation of this very fix) must not be mistaken for a real
    # orphaned one — and, more importantly, must not silently truncate the
    # entry and drop everything after the fence with no trace.
    ledger = (
        "- opened 2026-07-05 | fenced example artifact | see below for an example\n"
        "```text\n"
        "||||||| deadbeef1234\n"
        "```\n"
        "continued after the fence | me (session) | real proof survives\n\n"
        "## closed\n"
    )
    p = tmp_path / "PENDING-ARMS.md"
    p.write_text(ledger, encoding="utf-8")
    now = par._parse_now(NOW)
    entries = par.load_entries(p, now)
    assert len(entries) == 1
    e = entries[0]
    assert e.artifact == "fenced example artifact"
    assert "deadbeef1234" in e.missing_step  # preserved as literal fenced content
    assert "continued after the fence" in e.missing_step
    assert e.owner == "me (session)"
    assert e.proof == "real proof survives"


def test_innocence_unclosed_fence_does_not_swallow_the_rest_of_the_ledger(tmp_path):
    # Round-2 finding (cross-family review, 2026-07-26): an EARLIER draft of
    # the fence guard exempted ALL structural checks while in_fence, not just
    # the marker check — a fence that never closes (a stray lone ``` line, or
    # any odd fence-delimiter count anywhere below it) would then silently
    # absorb every subsequent line, including every later real entry, until
    # EOF, with zero MALFORMED signal (--strict-phantom stays green while the
    # rest of the ledger vanishes from the parse). The shipped design only
    # exempts the MARKER check while fenced — entry-start/list-item/blank/
    # heading detection stay active regardless, so an unclosed fence degrades
    # safely: later entries still parse correctly.
    ledger = (
        "- opened 2026-07-05 | before fence artifact | step one\n"
        "```text\n"
        "an accidentally-unclosed fence starts here, never closes\n"
        "- opened 2026-07-06 | after unclosed fence artifact | step two | me | proof two\n"
        "\n## closed\n"
    )
    p = tmp_path / "PENDING-ARMS.md"
    p.write_text(ledger, encoding="utf-8")
    now = par._parse_now(NOW)
    entries = par.load_entries(p, now)
    after = next(
        (e for e in entries if e.artifact == "after unclosed fence artifact"), None
    )
    assert after is not None, (
        "the second real entry must still be recognized even though the "
        "fence above it never closed — got entries: "
        + "; ".join(e.artifact or e.raw[:60] for e in entries)
    )
    assert after.owner == "me"
    assert after.proof == "proof two"
    assert after.cls == par.CLASS_TECH_DEBT


def test_innocence_multiline_entry_still_concatenates_after_marker_guard(entries):
    # Regression for the pre-existing continuation-line feature: the
    # conflict-marker guard must not disturb ordinary multi-line wrapping.
    e = _by_artifact(entries, "wrapped artifact")
    assert "continuing artifact description" in e.artifact
    assert "missing step first part" in e.missing_step
    assert "missing step continued" in e.missing_step
    assert e.owner == "me"
    assert e.proof.startswith("proof text starts")
    assert "proof continues here" in e.proof


@pytest.mark.skipif(
    not REAL_LEDGER_PATH.exists(),
    reason=f"real ledger not found at {REAL_LEDGER_PATH} (CI checkout may not have it)",
)
def test_real_ledger_has_zero_malformed_after_conflict_marker_cure():
    """The live defect this fix closes: origin/main's own PENDING-ARMS.md
    carried a stray `||||||| ebfbd71019` last line that blanked the owner of
    the 'Bali disclosure is hover-only' entry (measured before this fix:
    owner='', proof='ebfbd71019', cls=TECH-DEBT, bucket=FRESH — invisible to
    both --strict and --strict-phantom). After curing the marker off the
    ledger AND landing the structural fix, the real ledger must carry zero
    MALFORMED entries and --strict-phantom must exit 0.
    """
    now = par._parse_now(NOW)
    entries = par.load_entries(REAL_LEDGER_PATH, now)
    malformed = [e for e in entries if e.cls == par.CLASS_MALFORMED]
    assert not malformed, (
        "unexpected MALFORMED entries in the real ledger: "
        + "; ".join(e.raw[:80] for e in malformed)
    )
    # The 'Bali disclosure' row was only ever a convenient MARKER — the entry
    # the stray conflict-marker happened to corrupt at the time this test was
    # written — not an invariant the ledger owes forever: it was legitimately
    # closed 2026-08-21 (arming proven live, per the ledger's own removal
    # rule). Check it only while still open; the real regression this test
    # guards (zero MALFORMED + --strict-phantom exit 0) doesn't need it.
    disclosure = next(
        (e for e in entries if "Bali disclosure is hover-only" in e.artifact),
        None,
    )
    if disclosure is not None:
        assert disclosure.owner == "me (apps/mouth lane)"
        assert disclosure.cls == par.CLASS_TECH_DEBT
    assert par.main(["--ledger", str(REAL_LEDGER_PATH), "--now", NOW, "--strict-phantom"]) == 0
# -----------------------------------------------------------------------------
# Ledger freshness — guilt AND innocence
# -----------------------------------------------------------------------------
#
# The defect this cures was found by using the tool: the reporter was run in a
# checkout 64 commits behind origin/main and read out rows as "open" that main
# had closed days earlier. It reported a stale world with no hint that it had.
# Guilt: a behind checkout must say STALE. Innocence: an ordinary PR branch that
# ADDS a ledger line is ahead, not behind, and must NOT be accused — otherwise
# the banner cries wolf on every ledger PR and stops being read.


def _git(repo: Path, *args: str) -> str:
    import subprocess

    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _make_repo_with_origin(tmp_path: Path) -> tuple[Path, Path, Path]:
    """origin (bare) + a clone. Returns (clone, ledger_path_in_clone, origin)."""
    import subprocess

    origin = tmp_path / "origin.git"
    seed = tmp_path / "seed"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], check=True, capture_output=True)
    subprocess.run(["git", "init", "-b", "main", str(seed)], check=True, capture_output=True)
    _git(seed, "config", "user.email", "t@t.t")
    _git(seed, "config", "user.name", "t")
    led = seed / "PENDING-ARMS.md"
    led.write_text("- opened 2026-07-01 | seed | step | me | proof\n")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-m", "seed")
    _git(seed, "remote", "add", "origin", str(origin))
    _git(seed, "push", "-u", "origin", "main")

    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", str(origin), str(clone)], check=True, capture_output=True)
    _git(clone, "config", "user.email", "t@t.t")
    _git(clone, "config", "user.name", "t")
    return clone, clone / "PENDING-ARMS.md", seed


def test_guilt_freshness_reports_stale_when_origin_main_is_ahead(tmp_path):
    """The lived failure: origin/main gained ledger commits this checkout lacks."""
    clone, led, seed = _make_repo_with_origin(tmp_path)
    (seed / "PENDING-ARMS.md").write_text(
        "- opened 2026-07-01 | seed | step | me | proof\n"
        "- closed 2026-07-26 | seed | landed on main\n"
    )
    _git(seed, "commit", "-am", "close it on main")
    _git(seed, "push")
    _git(clone, "fetch", "origin")  # ref updated, working tree deliberately NOT pulled

    f = par._ledger_freshness(led)
    assert f["state"] == "stale", f
    assert f["behind"] == 1
    assert "STALE" in par._freshness_line(f)


def test_innocence_a_branch_that_adds_a_ledger_line_is_not_accused(tmp_path):
    """Every ledger PR differs from origin/main on purpose. Ahead != behind."""
    clone, led, _seed = _make_repo_with_origin(tmp_path)
    led.write_text(led.read_text() + "- opened 2026-07-27 | my new row | step | me | proof\n")
    _git(clone, "commit", "-am", "add a row, like every ledger PR does")

    f = par._ledger_freshness(led)
    assert f["state"] == "current", f
    assert f["behind"] == 0


def test_freshness_unknown_is_not_current_when_it_cannot_look(tmp_path):
    """A scan that could not look is not a clean scan (W84). No repo -> UNKNOWN."""
    led = tmp_path / "PENDING-ARMS.md"
    led.write_text("- opened 2026-07-01 | x | step | me | proof\n")
    f = par._ledger_freshness(led)
    assert f["state"] == "unknown", f
    assert f["behind"] is None
    line = par._freshness_line(f)
    assert "UNKNOWN" in line and "not 'current'" in line


def test_strict_fails_on_stale_but_strict_phantom_does_not(tmp_path, capsys):
    """--strict is 'I rely on this verdict' -> stale must fail it.
    --strict-phantom is the CI gate -> freshness must never redden an innocent PR."""
    clone, led, seed = _make_repo_with_origin(tmp_path)
    (seed / "PENDING-ARMS.md").write_text(
        "- opened 2026-07-01 | seed | step | me | proof\n- closed 2026-07-26 | seed | done\n"
    )
    _git(seed, "commit", "-am", "advance main")
    _git(seed, "push")
    _git(clone, "fetch", "origin")

    # The one open row here is fresh at --now and owned by `me`, so neither
    # overdue-tech-debt nor phantom can be what fails --strict: only staleness.
    assert par.main(["--ledger", str(led), "--now", "2026-07-01", "--strict"]) == 1
    assert "STALE" in capsys.readouterr().out
    assert par.main(["--ledger", str(led), "--now", "2026-07-01", "--strict-phantom"]) == 0


def test_freshness_appears_in_json_payload(tmp_path, capsys):
    led = tmp_path / "PENDING-ARMS.md"
    led.write_text("- opened 2026-07-01 | x | step | me | proof\n")
    assert par.main(["--ledger", str(led), "--now", "2026-07-05", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["freshness"]["state"] in {"current", "stale", "unknown"}


# -----------------------------------------------------------------------------
# PR-ALREADY-MERGED (megatopics-1-5 action plan #1, 2026-08-03) — OPT-IN via
# --check-pr-refs. gh is always mocked here (subprocess.run monkeypatched, the
# established pattern in scripts/tests/test_arsenal_probe.py) — no test in
# this file ever needs real network/gh auth.
# -----------------------------------------------------------------------------


class _FakeProc:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_extract_pr_refs_finds_refs_across_all_three_fields(tmp_path):
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | artifact PR #111 | step referencing PR #222 "
        "| me | proof mentions PR #333 and PR #222 again",
    )
    assert par.extract_pr_refs(e) == ["111", "222", "333"]


def test_extract_pr_refs_rejects_too_short_and_too_long_numbers(tmp_path):
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | short PR #12 ref | long PR #123456789 ref | me | proof",
    )
    assert par.extract_pr_refs(e) == []


def test_extract_pr_refs_empty_when_no_hash_present(entries):
    e = _by_artifact(entries, "fresh me artifact")
    assert par.extract_pr_refs(e) == []


def test_extract_pr_refs_ignores_bare_hash_numbers_without_pr_prefix(tmp_path):
    # Guilt-of-the-guard regression (measured live 2026-08-03 on the real
    # ledger): CodeQL alert numbers cited next to a file:line list —
    # "telegram_webhook.py:147,155,174 (#6860, #2837, #2836)" — are NOT pull
    # requests. Without the `PR` anchor these were extracted and (because gh
    # happens to report some coincidentally-numbered real PR as MERGED)
    # falsely flagged the entry as PR-ALREADY-MERGED.
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | telegram_webhook.py:147,155,174 (#6860, #2837, #2836) "
        "| me | intel_scraper.py:1217,1218 (#7798, #7799)",
    )
    assert par.extract_pr_refs(e) == []


def test_extract_pr_refs_accepts_lowercase_pr_prefix(tmp_path):
    e = _single_entry(
        tmp_path,
        "- opened 2026-07-05 | artifact pr #444 | step | me | proof",
    )
    assert par.extract_pr_refs(e) == ["444"]


def test_guilt_pr_ref_already_merged_is_flagged(tmp_path, monkeypatch):
    seen_cmds = []

    def fake_run(cmd, **kwargs):
        seen_cmds.append(cmd)
        assert cmd[:3] == ["gh", "pr", "view"]
        assert cmd[3] == "3552"
        return _FakeProc(0, '{"state":"MERGED","mergedAt":"2026-08-01T00:00:00Z"}', "")

    monkeypatch.setattr(par.subprocess, "run", fake_run)

    e = _single_entry(
        tmp_path,
        "- opened 2026-07-20 | stale pr ref artifact "
        "| merge PR #3552 to unblock this | me | pending merge of #3552",
    )
    par.annotate_pr_refs([e])
    assert e.pr_refs == ["3552"]
    assert e.merged_pr_refs == ["3552"]
    assert e.bucket == par.CLASS_PR_ALREADY_MERGED
    assert len(seen_cmds) == 1  # deduplicated: #3552 appears in both fields


def test_innocence_pr_ref_still_open_is_not_flagged(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        return _FakeProc(0, '{"state":"OPEN","mergedAt":null}', "")

    monkeypatch.setattr(par.subprocess, "run", fake_run)

    e = _single_entry(
        tmp_path,
        "- opened 2026-06-20 | genuinely open pr artifact "
        "| merge PR #4001 to unblock | me | still under review",
    )
    par.annotate_pr_refs([e])
    assert e.merged_pr_refs == []
    assert e.bucket != par.CLASS_PR_ALREADY_MERGED
    assert e.bucket == par.CLASS_TECH_DEBT + "-OVERDUE"


def test_innocence_entry_with_no_pr_ref_is_unaffected(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _FakeProc(0, '{"state":"MERGED"}', "")

    monkeypatch.setattr(par.subprocess, "run", fake_run)

    e = _single_entry(
        tmp_path,
        "- opened 2026-07-20 | no pr ref artifact | some step | me | some proof",
    )
    par.annotate_pr_refs([e])
    assert calls == []  # never even called gh: nothing to check
    assert e.merged_pr_refs == []
    assert e.bucket != par.CLASS_PR_ALREADY_MERGED


def test_guilt_gh_missing_degrades_to_cannot_verify_never_merged(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("gh: command not found")

    monkeypatch.setattr(par.subprocess, "run", fake_run)

    e = _single_entry(
        tmp_path,
        "- opened 2026-07-20 | unverifiable pr artifact | merge PR #5005 | me | proof",
    )
    par.annotate_pr_refs([e])
    assert e.merged_pr_refs == []  # NEVER silently treated as merged
    assert e.bucket != par.CLASS_PR_ALREADY_MERGED


def test_guilt_gh_non_zero_exit_degrades_to_cannot_verify(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        return _FakeProc(1, "", "gh: pull request not found\n")

    monkeypatch.setattr(par.subprocess, "run", fake_run)

    e = _single_entry(
        tmp_path,
        "- opened 2026-07-20 | notfound pr artifact | merge PR #9999 | me | proof",
    )
    par.annotate_pr_refs([e])
    assert e.merged_pr_refs == []
    assert e.bucket != par.CLASS_PR_ALREADY_MERGED


def test_guilt_gh_unparseable_json_degrades_to_cannot_verify(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        return _FakeProc(0, "not json at all", "")

    monkeypatch.setattr(par.subprocess, "run", fake_run)

    e = _single_entry(
        tmp_path,
        "- opened 2026-07-20 | garbled pr artifact | merge PR #6006 | me | proof",
    )
    par.annotate_pr_refs([e])
    assert e.merged_pr_refs == []


def test_guilt_gh_timeout_degrades_to_cannot_verify(tmp_path, monkeypatch):
    import subprocess as real_subprocess

    def fake_run(cmd, **kwargs):
        raise real_subprocess.TimeoutExpired(cmd, 15)

    monkeypatch.setattr(par.subprocess, "run", fake_run)

    e = _single_entry(
        tmp_path,
        "- opened 2026-07-20 | timeout pr artifact | merge PR #7007 | me | proof",
    )
    par.annotate_pr_refs([e])
    assert e.merged_pr_refs == []


def test_default_off_check_pr_refs_never_calls_gh(ledger_path, monkeypatch, capsys):
    """The core byte-for-byte-identical-when-off requirement: without
    --check-pr-refs, annotate_pr_refs is never invoked at all (main() still
    calls _ledger_freshness via `git` regardless — this only spies on the
    gh-calling path, so it must not intercept that unrelated subprocess use)."""
    calls = []
    monkeypatch.setattr(par, "annotate_pr_refs", lambda entries, **kwargs: calls.append(entries))
    code = par.main(["--ledger", str(ledger_path), "--now", NOW])
    assert code == 0
    assert calls == []


def test_default_off_counts_dict_has_no_pr_already_merged_key(ledger_path):
    now = par._parse_now(NOW)
    entries = par.load_entries(ledger_path, now)
    counts = par.compute_counts(entries)
    assert "pr_already_merged" not in counts


def test_default_off_json_entries_have_no_pr_ref_fields(ledger_path, capsys):
    code = par.main(["--ledger", str(ledger_path), "--now", NOW, "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert "pr_already_merged" not in payload["counts"]
    for entry in payload["entries"]:
        assert "pr_refs" not in entry
        assert "merged_pr_refs" not in entry


def test_default_off_report_has_no_pr_already_merged_section(ledger_path, capsys):
    code = par.main(["--ledger", str(ledger_path), "--now", NOW])
    assert code == 0
    out = capsys.readouterr().out
    assert "PR-ALREADY-MERGED" not in out


def test_check_pr_refs_cli_end_to_end_flags_merged_pr(tmp_path, monkeypatch, capsys):
    def fake_run(cmd, **kwargs):
        return _FakeProc(0, '{"state":"MERGED","mergedAt":"2026-08-01T00:00:00Z"}', "")

    monkeypatch.setattr(par.subprocess, "run", fake_run)

    ledger = (
        "- opened 2026-07-20 | cli merged pr artifact | merge PR #3552 | me | pending\n"
        "\n## closed\n"
    )
    p = tmp_path / "PENDING-ARMS.md"
    p.write_text(ledger, encoding="utf-8")

    code = par.main(["--ledger", str(p), "--now", NOW, "--check-pr-refs", "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["counts"]["pr_already_merged"] == 1
    entry = payload["entries"][0]
    assert entry["merged_pr_refs"] == ["3552"]


def test_check_pr_refs_report_section_appears_and_lists_entry(tmp_path, monkeypatch, capsys):
    def fake_run(cmd, **kwargs):
        return _FakeProc(0, '{"state":"MERGED","mergedAt":"2026-08-01T00:00:00Z"}', "")

    monkeypatch.setattr(par.subprocess, "run", fake_run)

    ledger = (
        "- opened 2026-07-20 | report merged pr artifact | merge PR #3552 | me | pending\n"
        "\n## closed\n"
    )
    p = tmp_path / "PENDING-ARMS.md"
    p.write_text(ledger, encoding="utf-8")

    code = par.main(["--ledger", str(p), "--now", NOW, "--check-pr-refs"])
    assert code == 0
    out = capsys.readouterr().out
    assert "## PR-ALREADY-MERGED" in out
    assert "report merged pr artifact" in out
    assert out.index("## PHANTOM-OPERATOR") < out.index("## PR-ALREADY-MERGED")
    assert out.index("## PR-ALREADY-MERGED") < out.index("## TECH-DEBT overdue")


# ---------------------------------------------------------------------------
# Label-anchored owner/proof extraction (2026-08-23, v2-d12) — the fix for a
# proven-live fail-open blind spot: `parts[-2]`/`parts[-1]` assumes owner and
# proof are the LAST two fields, true only for the canonical unlabeled 5-field
# shape. A trailing extra field (most commonly a hand-added `| source: ...`
# provenance note) shifted that anchor, and the REAL, explicitly `owner:`-
# labeled field sat unexamined — so a bare-phantom owner in that shape could
# resolve TECH-DEBT instead of PHANTOM-OPERATOR. Proven exploitable against a
# scratch copy of the real ledger before this fix landed (see the PR body for
# the full empirical trail); one guilt test per shape found, per team-lead's
# explicit instruction that a mutation-guard proven on one shape is not proven
# on the class.
# ---------------------------------------------------------------------------


def test_guilt_trailing_source_field_no_longer_hides_bare_phantom(tmp_path):
    """THE exploit, reproduced as a permanent regression guard. Before this fix:
    parts = [date, artifact, missing_step, 'owner: operator', 'proof: ...',
    'source: ...'] — parts[-2] read the PROOF text as owner (no 'operator'
    substring in it), so this parsed to TECH-DEBT and made --strict-phantom
    exit 0 on a bare, untagged phantom. The label-anchored owner: field is now
    found regardless of position.
    """
    e = _single_entry(
        tmp_path,
        "- opened 2026-08-23 | trailing-source phantom artifact | some step "
        "| owner: operator | proof: this proof text does not contain the word phantom "
        "| source: research/operations/some-audit.md",
    )
    assert e.owner == "operator"
    assert e.cls == par.CLASS_PHANTOM_OPERATOR


def test_innocence_trailing_source_field_with_valid_category_stays_operator_gated(tmp_path):
    """Same trailing-field shape, but the labeled owner declares a real
    true-operator category — must resolve OPERATOR-GATED, not phantom and not
    misfiled as TECH-DEBT the way the pre-fix parser did for this exact shape
    (8 real ledger entries were measured in this state before this fix).
    """
    e = _single_entry(
        tmp_path,
        "- opened 2026-08-23 | trailing-source operator-gated artifact | some step "
        "| owner: operator[gui] | proof: the login is a browser device-code flow "
        "| source: research/operations/some-audit.md",
    )
    assert e.owner == "operator[gui]"
    assert e.cls == par.CLASS_OPERATOR_GATED
    assert e.proof == "the login is a browser device-code flow"


def test_guilt_proof_labeled_text_in_owner_slot_no_label_anywhere_is_malformed(tmp_path):
    """Defense-in-depth for a shape not yet observed live but structurally
    possible once a 6th field is appended after proof with no 'owner:' label
    anywhere to rescue it: position-based fallback (parts[-2]) then lands on
    text that is ITSELF explicitly labeled proof-of-armed: — an unambiguous
    anchor-collision tell, not a phrasing choice. Must be a loud MALFORMED,
    never silently accepted as ordinary TECH-DEBT. 5 fields, no 'owner:'
    label: [date, artifact, missing_step, 'proof-of-armed: ...', trailing] —
    parts[-2] lands exactly on the mislabeled field.
    """
    e = _single_entry(
        tmp_path,
        "- opened 2026-08-23 | anchor collision artifact | some step "
        "| proof-of-armed: re-run the same measurement and confirm the fix holds "
        "| a trailing final field with no label",
    )
    assert e.cls == par.CLASS_MALFORMED
    assert any("anchor collision" in r for r in e.malformed_reasons)


def test_guilt_bare_status_word_in_owner_slot_is_malformed(tmp_path):
    """Third real shape: no 'owner:' label anywhere, and position-based
    fallback lands on a bare status word lifted from a closure note elsewhere
    in the entry — 'closed' cannot legitimately BE an owner under any
    phrasing. Must be MALFORMED (this entry is NOT firebreak-worded, unlike
    its real-ledger counterpart — see the innocence test below for that
    exemption).
    """
    e = _single_entry(
        tmp_path,
        "- opened 2026-08-23 | bare status word artifact | some step "
        "| a note about the resolution | closed | some final proof text",
    )
    assert e.cls == par.CLASS_MALFORMED
    assert any("bare status word" in r for r in e.malformed_reasons)


def test_innocence_bare_status_word_exempted_when_entry_is_firebreak(tmp_path):
    """Real-ledger regression guard (found 2026-08-23 while shipping the fix
    above): a genuine, pre-existing, harmless FIREBREAK entry
    ('INTERACTIVE-DEFAULT RULING') has this exact bare-'closed'-in-owner-slot
    shape, left over from its own closure prose. FIREBREAK is informational
    only by design (never alarmed, never blocks a merge) — the unguarded
    version of the bare-status-word backstop newly flagged this real entry as
    MALFORMED, which fails --strict-phantom unconditionally and would have
    shipped this fix CI-red against the real, UNCHANGED ledger. The backstop
    must stay silent here; fixing the row's own prose is separate, future,
    optional work — not a precondition of this fix landing.
    """
    e = _single_entry(
        tmp_path,
        "- opened 2026-08-23 | bare status word firebreak artifact | some step "
        "| This is a FIREBREAK (Legge 5 / business), not tech debt: a closure note "
        "| closed | some final proof text",
    )
    assert e.cls == par.CLASS_FIREBREAK
    assert e.malformed is False


def test_innocence_legitimately_phrased_owner_without_label_not_flagged(tmp_path):
    """Guards against over-tightening: a real ledger entry's owner value is
    'next war-room-lane session' — no 'owner:' label present, starts with
    neither me/operator/session, but is a perfectly legitimate (if unusual)
    owner phrasing, not corruption. An earlier draft of this fix's audit
    heuristic flagged this as 'broken' and was itself a false positive — this
    test pins that the shipped backstop (unlike that draft heuristic) does
    NOT fire on mere unusual phrasing, only on the two unambiguous tells
    (proof-of-armed:/proof: mislabeling, or an exact bare status word).
    """
    e = _single_entry(
        tmp_path,
        "- opened 2026-08-23 | unusual phrasing artifact | some step "
        "| next war-room-lane session | some proof text",
    )
    assert e.owner == "next war-room-lane session"
    assert e.cls == par.CLASS_TECH_DEBT
    assert e.malformed is False


def test_innocence_multiple_owner_labels_last_one_wins(tmp_path):
    """The fourth real shape (2 real entries found: '77 phantom KBLI-2020
    codes' and 'queue_rearm.sh scheduling'): a session appends a full restated
    `owner: ... | proof: ...` pair after a progress-note paragraph, when the
    update narrows or reassigns scope rather than just adding commentary (a
    second full pair, not the `**UPDATE ...**`-only shape
    `_split_trailing_update_notes` already handles). The LATEST restatement is
    the current truth — same "latest wins" reading a human gives the line —
    never flagged as an ambiguous/malformed entry: both real occurrences were
    this legitimate growth pattern, not corruption.
    """
    e = _single_entry(
        tmp_path,
        "- opened 2026-08-23 | growing scope artifact | some step "
        "| owner: me (original scope) | proof: original proof text "
        "| UPDATE 2026-08-20: PR #1 merged for part of the scope, narrowing what remains "
        "| owner: me (remaining scope only) | proof: remap PR closing the rest",
    )
    assert e.owner == "me (remaining scope only)"
    assert e.proof == "remap PR closing the rest"
    assert e.cls == par.CLASS_TECH_DEBT
    assert e.malformed is False


def test_innocence_canonical_unlabeled_five_field_entry_unaffected(tmp_path):
    """Regression guard: the vast majority of the real ledger has NO 'owner:'/
    'proof:' label at all — just the canonical positional 5-field shape. The
    label-anchor fix must fall back to position exactly as before when no
    label is present anywhere, byte-for-byte, for both the me-owner and the
    operator[<category>]-owner cases.
    """
    e_me = _single_entry(
        tmp_path,
        "- opened 2026-08-23 | canonical me artifact | some step | me | some proof",
    )
    assert e_me.owner == "me"
    assert e_me.cls == par.CLASS_TECH_DEBT

    e_op = _single_entry(
        tmp_path,
        "- opened 2026-08-23 | canonical operator artifact | some step "
        "| operator[secret] | some proof",
    )
    assert e_op.owner == "operator[secret]"
    assert e_op.cls == par.CLASS_OPERATOR_GATED


@pytest.mark.skipif(
    not REAL_LEDGER_PATH.exists(),
    reason=f"real ledger not found at {REAL_LEDGER_PATH} (CI checkout may not have it)",
)
def test_real_ledger_has_zero_malformed():
    """The living enforcement half of the 2026-08-23 fix: an entry the parser
    cannot confidently anchor (empty owner, anchor-collision, bare status
    word) is exactly as untrustworthy as a phantom-operator entry and must
    turn any new occurrence in the REAL ledger into a red CI check the moment
    it is written — same construction as test_real_ledger_has_zero_phantom_operator
    just above.
    """
    now = par._parse_now(NOW)
    entries = par.load_entries(REAL_LEDGER_PATH, now)
    malformed = [e for e in entries if e.cls == par.CLASS_MALFORMED]
    assert not malformed, (
        "MALFORMED entries in the real ledger (owner field could not be "
        "confidently anchored — see e.malformed_reasons for why): "
        + "; ".join(
            f"{e.artifact or e.raw[:80]!r} ({'; '.join(e.malformed_reasons)})"
            for e in malformed
        )
    )
