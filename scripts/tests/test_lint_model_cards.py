"""PR3a (2026-09-18) — tests for lint_model_cards.py.

Verifies the linter correctly:
- Flags an untagged claim bullet (RULE 1)
- Flags a MEASURED: bullet whose path is neither in the repo nor memory-slug shaped
  (RULE 2)
- Flags a frontmatter date more than FRESHNESS_DAYS (30) old (RULE 3), including the
  exact 30-vs-31-day boundary computed against real wall-clock "today" (not a pinned
  calendar date, which could only ever prove one moment of that boundary)
- Flags a roles_allowed: value outside ALLOWED_ROLES (RULE 4)
- Flags a seat: that does not resolve via dynamic_workflow.py's FAMILY_MAP/_SEAT_ALIASES
  (RULE 5)
- Stays quiet on a fixture that satisfies all five rules (innocence)
- Is green against the LIVE docs/arsenal/cards/*.md tree (this repo's own convention,
  see test_lint_asyncpg_except_completeness.py's test_main_exit_0_on_clean)
- Refuses to report clean on a blind (zero-file) sweep, and does not over-match that
  guard onto an explicit non-.md argv or a single clean in-scope file
- Refuses to report clean when an explicit blind target (nonexistent path or
  zero-yield directory) is masked by a SIBLING target that scans cleanly in the
  same invocation (PR3c cure round, 2026-09-19) — judged per-target, not by a
  global scanned-count gate
"""
from __future__ import annotations

import importlib.util
from datetime import date, timedelta
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "lint_model_cards.py"
REPO_ROOT = SCRIPT_PATH.parents[1]
FIXTURES_DIR = (
    Path(__file__).resolve().parent
    / "fixtures" / "lint_model_cards" / "repo" / "docs" / "arsenal" / "cards"
)
# The day the pinned-date fixtures below (untagged_bullet.md, measured_bad_path.md,
# bad_roles.md, bad_seat.md, clean.md — all `date: 2026-09-18`) were authored. RULE 3 is
# calendar-relative: without pinning `today` to this date, those fixtures would start
# tripping RULE 3 ("expired") too, the moment real wall-clock time passes them 30 days,
# breaking the "exactly one violation" isolation each one exists to prove. See
# fixtures/lint_model_cards/README.md.
FIXTURE_TODAY = date(2026, 9, 18)


def _load_lint_module():
    spec = importlib.util.spec_from_file_location("lint_model_cards_mod", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def lint():
    return _load_lint_module()


@pytest.fixture(scope="module")
def dw(lint):
    return lint._load_dynamic_workflow()


def test_untagged_bullet_is_violation(lint, dw):
    violations = lint.find_violations(
        FIXTURES_DIR / "untagged_bullet.md", dw, today=FIXTURE_TODAY
    )
    assert len(violations) == 1
    assert "tagged" in violations[0][1]


def test_measured_bad_path_is_violation(lint, dw):
    violations = lint.find_violations(
        FIXTURES_DIR / "measured_bad_path.md", dw, today=FIXTURE_TODAY
    )
    assert len(violations) == 1
    assert "MEASURED:" in violations[0][1]


def test_expired_is_violation(lint, dw):
    violations = lint.find_violations(FIXTURES_DIR / "expired.md", dw, today=FIXTURE_TODAY)
    assert len(violations) == 1
    assert "expired" in violations[0][1]


def test_bad_roles_is_violation(lint, dw):
    violations = lint.find_violations(FIXTURES_DIR / "bad_roles.md", dw, today=FIXTURE_TODAY)
    assert len(violations) == 1
    assert "roles_allowed" in violations[0][1]


def test_bad_seat_is_violation(lint, dw):
    violations = lint.find_violations(FIXTURES_DIR / "bad_seat.md", dw, today=FIXTURE_TODAY)
    assert len(violations) == 1
    assert "does not resolve" in violations[0][1]


def test_clean_fixture_is_clean(lint, dw):
    assert lint.find_violations(FIXTURES_DIR / "clean.md", dw, today=FIXTURE_TODAY) == []


# --------------------------------------------------------------------------
# RULE 3 boundary — computed against real "today", not a pinned calendar date.
# --------------------------------------------------------------------------


def test_freshness_31_days_old_is_expired(lint, dw, tmp_path):
    card_date = date.today() - timedelta(days=31)
    path = tmp_path / "old.md"
    path.write_text(
        "seat: kimi-code/kimi-for-coding-highspeed\n"
        f"date: {card_date.isoformat()}\n"
        "roles_allowed: grunt\n\n"
        "# old\n\n"
        "- SELF: this card is exactly 31 days old at test time\n",
        encoding="utf-8",
    )
    violations = lint.find_violations(path, dw)
    msgs = [m for _, m in violations]
    assert any("expired" in m for m in msgs), msgs


def test_freshness_30_days_old_is_not_expired(lint, dw, tmp_path):
    card_date = date.today() - timedelta(days=30)
    path = tmp_path / "boundary.md"
    path.write_text(
        "seat: kimi-code/kimi-for-coding-highspeed\n"
        f"date: {card_date.isoformat()}\n"
        "roles_allowed: grunt\n\n"
        "# boundary\n\n"
        "- SELF: this card is exactly 30 days old at test time (not expired)\n",
        encoding="utf-8",
    )
    violations = lint.find_violations(path, dw)
    msgs = [m for _, m in violations]
    assert not any("expired" in m for m in msgs), msgs


def test_main_exit_0_on_clean(capsys):
    """Run on the live docs/arsenal/cards/*.md — must be green (the example card)."""
    mod = _load_lint_module()
    rc = mod.main([])
    captured = capsys.readouterr()
    assert rc == 0, f"linter should be green on the live repo; output:\n{captured.out}"
    assert "no violations" in captured.out


# --------------------------------------------------------------------------
# BLIND-SCAN GUARD (cicatrix #2/#4 — "0 files traversed != clean").
# --------------------------------------------------------------------------


def test_guilt_blind_sweep_refuses_to_report_clean(lint, monkeypatch, capsys):
    monkeypatch.setattr(
        lint, "DEFAULT_GLOB_DIR", "scripts/tests/fixtures/__no_such_dir_for_blind_scan__"
    )
    rc = lint.main([])
    captured = capsys.readouterr()
    assert rc == 2, "a blind sweep must not exit 0 — it proves nothing"
    assert "BLIND SCAN" in captured.err
    assert "no violations" not in captured.out


def test_innocence_explicit_non_md_file_is_still_green(lint, tmp_path, capsys):
    not_md = tmp_path / "notes.txt"
    not_md.write_text("nothing to see here\n", encoding="utf-8")
    rc = lint.main([str(not_md)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "no violations" in captured.out
    assert "BLIND SCAN" not in captured.err


def test_innocence_one_clean_in_scope_file_is_enough(lint, tmp_path, capsys):
    """The guard fires at EXACTLY zero — a single swept file must satisfy it.

    PR3c cure round (2026-09-19, Kimi finding): clean.md's frontmatter `date:` is a
    STATIC fixture value, and lint.main() (unlike find_violations) takes no `today=`
    override to pin against — pointing main() straight at the fixture file would go
    stale and start tripping RULE 3 the moment real wall-clock time passes it 30 days.
    Interpolate today's date into a tmp_path copy instead, same cure as the sibling
    directory-expansion test below.
    """
    fresh = tmp_path / "clean.md"
    fresh.write_text(
        FIXTURES_DIR.joinpath("clean.md").read_text(encoding="utf-8").replace(
            "date: 2026-09-18", f"date: {date.today().isoformat()}"
        ),
        encoding="utf-8",
    )
    rc = lint.main([str(fresh)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "BLIND SCAN" not in captured.err


def test_guilt_explicit_nonexistent_target_is_a_blind_scan(lint, tmp_path, capsys):
    """OBSERVATION 6 (PR3a', 2026-09-18): a nonexistent explicit path must refuse, not
    silently report '0 file(s) scanned, no violations, exit 0'."""
    ghost = tmp_path / "does_not_exist.md"
    rc = lint.main([str(ghost)])
    captured = capsys.readouterr()
    assert rc == 2, "a nonexistent explicit target must not exit 0 — it proves nothing"
    assert "BLIND SCAN" in captured.err
    assert str(ghost) in captured.err
    assert "no violations" not in captured.out


def test_guilt_explicit_empty_dir_is_a_blind_scan(lint, tmp_path, capsys):
    """PR3c blind-scan closure (2026-09-19): an explicit directory that exists but
    yields zero .md files is the same defect as a nonexistent path — must refuse,
    not silently report '0 file(s) scanned, no violations, exit 0'."""
    empty_dir = tmp_path / "renamed_or_emptied"
    empty_dir.mkdir()
    rc = lint.main([str(empty_dir)])
    captured = capsys.readouterr()
    assert rc == 2, "an explicit empty directory must not exit 0 — it proves nothing"
    assert "BLIND SCAN" in captured.err
    assert str(empty_dir) in captured.err
    assert "no violations" not in captured.out


def test_innocence_explicit_dir_with_one_clean_file_exits_0(lint, tmp_path, capsys):
    """The directory-expansion guard fires at EXACTLY zero — a directory containing
    one clean .md file must be swept and pass, not treated as another blind scan.

    Interpolates today's date (see test_innocence_one_clean_in_scope_file_is_enough's
    docstring) rather than copying clean.md's static frontmatter date verbatim.
    """
    scoped_dir = tmp_path / "one_clean_file"
    scoped_dir.mkdir()
    (scoped_dir / "clean.md").write_text(
        FIXTURES_DIR.joinpath("clean.md").read_text(encoding="utf-8").replace(
            "date: 2026-09-18", f"date: {date.today().isoformat()}"
        ),
        encoding="utf-8",
    )
    rc = lint.main([str(scoped_dir)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "no violations (1 file(s) scanned)" in captured.out
    assert "BLIND SCAN" not in captured.err


def test_guilt_mixed_targets_empty_dir_not_masked_by_productive_sibling(lint, tmp_path, capsys):
    """PR3c cure round (2026-09-19, Kimi finding): a global scanned-count gate let one
    productive target mask a SIBLING blind one in the same invocation. Each explicit
    target must be judged on its own — an empty directory stays guilty even when
    another argv target in the same invocation scans cleanly."""
    empty_dir = tmp_path / "renamed_or_emptied"
    empty_dir.mkdir()
    productive_dir = tmp_path / "one_clean_file"
    productive_dir.mkdir()
    (productive_dir / "clean.md").write_text(
        FIXTURES_DIR.joinpath("clean.md").read_text(encoding="utf-8").replace(
            "date: 2026-09-18", f"date: {date.today().isoformat()}"
        ),
        encoding="utf-8",
    )
    rc = lint.main([str(empty_dir), str(productive_dir)])
    captured = capsys.readouterr()
    assert rc == 2, "a sibling target scanning cleanly must not mask a blind one"
    assert "BLIND SCAN" in captured.err
    assert str(empty_dir) in captured.err
    assert "no violations" not in captured.out


# --------------------------------------------------------------------------
# DEFECT 1 (PR3a', 2026-09-18) — relative_to(REPO_ROOT) must not traceback on an
# out-of-root explicit target.
# --------------------------------------------------------------------------


def test_guilt_out_of_root_violation_prints_absolute_path_no_traceback(lint, tmp_path, capsys):
    guilty = tmp_path / "guilty.md"
    guilty.write_text(
        "seat: kimi-code/kimi-for-coding-highspeed\n"
        "date: 2026-09-18\n"
        "roles_allowed: grunt\n\n"
        "# guilty\n\n"
        "- this bullet has no SELF/MEASURED/PUBLIC tag, triggering RULE 1\n",
        encoding="utf-8",
    )
    rc = lint.main([str(guilty)])
    captured = capsys.readouterr()
    assert rc == 1
    assert "tagged" in captured.out
    assert str(guilty) in captured.out
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out


def test_innocence_in_root_violation_still_prints_relative_path(lint, capsys):
    rc = lint.main([str(FIXTURES_DIR / "untagged_bullet.md")])
    captured = capsys.readouterr()
    assert rc == 1
    assert str(REPO_ROOT) not in captured.out
