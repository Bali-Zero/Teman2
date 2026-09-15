"""Unit tests for LKPMAssignBody's allowlist validator
(backend/app/routers/lkpm.py) — the write path for lkpm_reports.lkpm_assigned_to.

Same shape as test_client_update_tax_consultant_* in
test_crm_clients_coverage.py: direct Pydantic-model instantiation, no
TestClient. Covers the migration-319 legacy-alias normalization (Round 2,
SAETTA-20260915 / W-C slice R-C) on the LKPM side.
"""

import pytest


def test_lkpm_assign_body_valid_assignee():
    from backend.app.routers.lkpm import LKPMAssignBody

    body = LKPMAssignBody(lkpm_assigned_to="tax@balizero.com")
    assert body.lkpm_assigned_to == "tax@balizero.com"


def test_lkpm_assign_body_none_stays_none():
    from backend.app.routers.lkpm import LKPMAssignBody

    body = LKPMAssignBody(lkpm_assigned_to=None)
    assert body.lkpm_assigned_to is None


def test_lkpm_assign_body_empty_string_becomes_none():
    from backend.app.routers.lkpm import LKPMAssignBody

    body = LKPMAssignBody(lkpm_assigned_to="")
    assert body.lkpm_assigned_to is None


def test_lkpm_assign_body_legacy_alias_normalizes_to_real():
    """The kita dropdown still SENDS the retired address (migration 319) —
    assigning an LKPM report to it must be ACCEPTED and the value actually
    stored (what `assign_lkpm_report` writes via `body.lkpm_assigned_to`)
    must be the real replacement, not the ghost."""
    from backend.app.core.constants import TaxConsultantConstants
    from backend.app.routers.lkpm import LKPMAssignBody

    ghost, real = list(TaxConsultantConstants.LEGACY_ALIASES.items())[1]
    body = LKPMAssignBody(lkpm_assigned_to=ghost)
    assert body.lkpm_assigned_to == real


def test_lkpm_assign_body_unknown_address_still_rejected():
    """An address outside both the real allowlist and the legacy-alias map
    must still be rejected exactly as before normalize() existed."""
    from backend.app.routers.lkpm import LKPMAssignBody

    with pytest.raises(ValueError, match="lkpm_assigned_to must be one of"):
        LKPMAssignBody(lkpm_assigned_to="unknown.consultant@balizero.com")


def test_lkpm_assign_body_krisna_still_allowed():
    """Krisna (110_lkpm_allowlist_krisna.sql) has no .tax@ sub-alias and is
    not in LEGACY_ALIASES — normalize() must pass him through unchanged."""
    from backend.app.routers.lkpm import LKPMAssignBody

    body = LKPMAssignBody(lkpm_assigned_to="krisna@balizero.com")
    assert body.lkpm_assigned_to == "krisna@balizero.com"
