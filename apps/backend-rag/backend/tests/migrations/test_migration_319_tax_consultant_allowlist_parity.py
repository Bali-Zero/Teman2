"""Migration 319's two CHECK allowlists must PARSE to exactly the shared
constant, `TaxConsultantConstants` (backend/app/core/constants.py).

The defect migration 319 cured (SAETTA-20260915 / W-C, slice R-C) was
exactly this class of drift: four independent Python copies of a 5-address
allowlist and two DB CHECK constraints, all supposed to agree, silently
didn't. Restating the migration's own list by hand in a test would just add
a SEVENTH copy that could drift the same way. This test PARSES the .sql
file's CHECK clauses instead, so the migration and the shared constant are
compared directly — a one-character divergence in either fails the build.
"""

from __future__ import annotations

import re
from pathlib import Path

from backend.app.core.constants import TaxConsultantConstants

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "319_align_tax_consultant_allowlist_to_team_members.sql"
)

_EMAIL_RE = re.compile(r"'([\w.+-]+@balizero\.com)'")


def _forward_sql() -> str:
    """Only the FORWARD section — the rollback section legitimately restores
    the old ghost-laced lists, and must not be mistaken for the live ones."""
    text = MIGRATION.read_text(encoding="utf-8")
    forward, rollback = text.split("-- === ROLLBACK ===", 1)
    assert rollback.strip(), "rollback section must not be empty"
    return forward


def _constraint_email_list(forward_sql: str, constraint_name: str) -> list[str]:
    marker = f"ADD CONSTRAINT {constraint_name}"
    start = forward_sql.index(marker)
    end = forward_sql.index(");", start)
    return _EMAIL_RE.findall(forward_sql[start:end])


def test_clients_check_matches_shared_canonical() -> None:
    emails = _constraint_email_list(_forward_sql(), "clients_tax_consultant_check")
    assert emails == list(TaxConsultantConstants.CANONICAL)


def test_lkpm_check_matches_shared_lkpm_assignees() -> None:
    emails = _constraint_email_list(_forward_sql(), "lkpm_reports_assigned_to_check")
    assert emails == list(TaxConsultantConstants.LKPM_ASSIGNEES)


def test_one_character_drift_in_the_migration_is_caught() -> None:
    """Guilt control: mutate ONE character of the parsed migration text and
    prove the comparison against the shared constant actually breaks."""
    drifted = _forward_sql().replace(
        "'dewaayu.tax@balizero.com'", "'dewaayu.tax@balizeroo.com'", 1
    )
    emails = _constraint_email_list(drifted, "clients_tax_consultant_check")
    assert emails != list(TaxConsultantConstants.CANONICAL)


def test_migration_file_itself_carries_no_stray_check_constraint() -> None:
    """Sanity: exactly one ADD CONSTRAINT per allowlist name in the forward
    section, so `_constraint_email_list`'s first-`);`-after-marker slice
    can't accidentally straddle two statements."""
    forward = _forward_sql()
    assert forward.count("ADD CONSTRAINT clients_tax_consultant_check") == 1
    assert forward.count("ADD CONSTRAINT lkpm_reports_assigned_to_check") == 1
