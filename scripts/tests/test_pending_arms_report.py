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

> Format: `opened YYYY-MM-DD | artifact | missing arming step | owner (me|operator) | proof-of-armed`

- opened 2026-06-25 | overdue tech debt artifact | wire the hook into settings.json | me | a live session shows the block
- opened 2026-07-05 | fresh me artifact | needs a restart to pick up | me | next restart log shows it
- opened 2026-06-20 | overdue operator artifact | waiting on operator GO | operator | operator GO recorded
- opened 2026-06-01 | firebreak artifact | DELIBERATE FIREBREAK, not tech debt: waiting for signal quality before flip | operator | operator GO + probe

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
    assert len(entries) == 8


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
    assert e.overdue is True
    assert e.bucket == "OPERATOR-GATED-OVERDUE"


def test_overdue_firebreak_classification(entries):
    e = _by_artifact(entries, "firebreak artifact")
    assert e.cls == par.CLASS_FIREBREAK
    assert e.owner == "operator"
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
        "total": 8,
        "tech_debt_overdue": 3,  # overdue-tech-debt, wrapped, boundary-age-two
        "operator_gated_overdue": 1,
        "firebreak": 1,
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
- opened 2026-06-01 | firebreak only artifact | DELIBERATE FIREBREAK not tech debt | operator | operator GO
- opened 2026-06-10 | operator only artifact | waiting on operator | operator | operator GO recorded

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
    assert "## TECH-DEBT overdue (>48h)" in out
    assert "## OPERATOR-GATED overdue" in out
    assert "## FIREBREAK (legitimate, informational)" in out
    assert "## Fresh (<48h)" in out
    assert "## MALFORMED" in out
    assert "overdue tech debt artifact" in out
    assert "ancient closed artifact" not in out


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
        "total": 8,
        "tech_debt_overdue": 3,
        "operator_gated_overdue": 1,
        "firebreak": 1,
        "fresh": 2,
        "malformed": 1,
    }
    assert len(payload["entries"]) == 8
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
            par.CLASS_FIREBREAK,
            "TECH-DEBT-OVERDUE",
            "OPERATOR-GATED-OVERDUE",
            "FRESH",
        }
