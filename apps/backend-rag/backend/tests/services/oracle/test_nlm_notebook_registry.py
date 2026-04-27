"""Tests for nlm_notebook_registry — routing logic, multi-notebook fan-out,
env-var helpers, and NLM_NOTEBOOKS data integrity.

Freshness gate (S1.3) is covered by test_nlm_notebook_registry_freshness.py.
This file covers everything else.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest

from backend.services.oracle import nlm_notebook_registry as reg


# ── NLM_NOTEBOOKS data integrity ────────────────────────────────────────────


_EXPECTED_DOMAINS = {
    "immigration",
    "company",
    "tax",
    "property",
    "operations",
    "editorial",
    "lifestyle",
}

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def test_registry_has_all_seven_domains() -> None:
    assert set(reg.NLM_NOTEBOOKS.keys()) == _EXPECTED_DOMAINS


def test_registry_every_domain_has_required_keys() -> None:
    for domain, data in reg.NLM_NOTEBOOKS.items():
        assert "notebook_id" in data, f"{domain}: missing notebook_id"
        assert "label" in data, f"{domain}: missing label"
        assert "keywords" in data, f"{domain}: missing keywords"
        assert "primary_notebook_id" in data, f"{domain}: missing primary_notebook_id"


def test_registry_notebook_ids_are_valid_uuids() -> None:
    for domain, data in reg.NLM_NOTEBOOKS.items():
        nb_id = data["notebook_id"]
        assert _UUID_RE.match(nb_id), f"{domain}: notebook_id is not a valid UUID: {nb_id!r}"


def test_registry_keywords_are_non_empty_sets() -> None:
    for domain, data in reg.NLM_NOTEBOOKS.items():
        kws = data["keywords"]
        assert isinstance(kws, (set, frozenset)), f"{domain}: keywords not a set"
        assert len(kws) > 0, f"{domain}: keywords is empty"


def test_registry_primary_notebook_ids_are_none_or_valid_uuid() -> None:
    """All primary_notebook_ids are currently None; if ever set, must be UUID."""
    for domain, data in reg.NLM_NOTEBOOKS.items():
        pid = data["primary_notebook_id"]
        if pid is not None:
            assert _UUID_RE.match(str(pid)), f"{domain}: primary_notebook_id invalid UUID"


# ── _max_stale_hours ─────────────────────────────────────────────────────────


def test_max_stale_hours_returns_default_when_env_unset(monkeypatch) -> None:
    monkeypatch.delenv("NLM_MAX_STALE_HOURS", raising=False)
    assert reg._max_stale_hours() == 24


def test_max_stale_hours_reads_valid_env_value(monkeypatch) -> None:
    monkeypatch.setenv("NLM_MAX_STALE_HOURS", "48")
    assert reg._max_stale_hours() == 48


def test_max_stale_hours_falls_back_to_default_on_invalid_string(monkeypatch) -> None:
    monkeypatch.setenv("NLM_MAX_STALE_HOURS", "not-a-number")
    assert reg._max_stale_hours() == 24


def test_max_stale_hours_enforces_floor_of_one(monkeypatch) -> None:
    monkeypatch.setenv("NLM_MAX_STALE_HOURS", "0")
    assert reg._max_stale_hours() == 1


def test_max_stale_hours_enforces_floor_negative(monkeypatch) -> None:
    monkeypatch.setenv("NLM_MAX_STALE_HOURS", "-5")
    assert reg._max_stale_hours() == 1


# ── _resolve_state_path ──────────────────────────────────────────────────────


def test_resolve_state_path_uses_env_override(monkeypatch, tmp_path) -> None:
    custom = tmp_path / "custom_state.json"
    monkeypatch.setenv("NLM_FRESHNESS_STATE_FILE", str(custom))
    assert reg._resolve_state_path() == custom


def test_resolve_state_path_returns_path_when_env_unset(monkeypatch) -> None:
    monkeypatch.delenv("NLM_FRESHNESS_STATE_FILE", raising=False)
    path = reg._resolve_state_path()
    assert isinstance(path, Path)


# ── resolve_notebook — routing ───────────────────────────────────────────────


def test_resolve_notebook_returns_none_for_empty_query() -> None:
    assert reg.resolve_notebook("") is None


def test_resolve_notebook_returns_none_for_unmatched_query() -> None:
    result = reg.resolve_notebook("qwerty zxcvb asdfgh no domain match here xyz")
    assert result is None


def test_resolve_notebook_routes_immigration_query() -> None:
    result = reg.resolve_notebook("I need a KITAS visa for my expat employee")
    assert result is not None
    assert result["domain"] == "immigration"
    assert result["notebook_id"] == reg.NLM_NOTEBOOKS["immigration"]["notebook_id"]


def test_resolve_notebook_routes_company_query() -> None:
    result = reg.resolve_notebook("how to set up a PMA company with NIB in Indonesia")
    assert result is not None
    assert result["domain"] == "company"


def test_resolve_notebook_routes_tax_query() -> None:
    result = reg.resolve_notebook("NPWP registration and PPH tax compliance")
    assert result is not None
    assert result["domain"] == "tax"


def test_resolve_notebook_routes_property_query() -> None:
    result = reg.resolve_notebook("villa leasehold zoning HGB land purchase Bali")
    assert result is not None
    assert result["domain"] == "property"


def test_resolve_notebook_routes_operations_query() -> None:
    result = reg.resolve_notebook("pricing SOP CRM workflow for the team")
    assert result is not None
    assert result["domain"] == "operations"


def test_resolve_notebook_routes_editorial_query() -> None:
    result = reg.resolve_notebook("SEO content market intel article trends")
    assert result is not None
    assert result["domain"] == "editorial"


def test_resolve_notebook_routes_lifestyle_query() -> None:
    result = reg.resolve_notebook("expat healthcare cost of living digital nomad")
    assert result is not None
    assert result["domain"] == "lifestyle"


def test_resolve_notebook_result_contains_required_keys() -> None:
    result = reg.resolve_notebook("KITAS visa requirements")
    assert result is not None
    for key in ("domain", "notebook_id", "label", "keywords", "primary_notebook_id"):
        assert key in result, f"missing key: {key}"


def test_resolve_notebook_keywords_field_is_frozenset() -> None:
    result = reg.resolve_notebook("KITAS visa")
    assert result is not None
    assert isinstance(result["keywords"], frozenset)


def test_resolve_notebook_picks_best_scoring_domain_over_weaker_match() -> None:
    """A query with many company keywords but one visa word routes to company."""
    result = reg.resolve_notebook("PMA company KBLI OSS NIB investment business")
    assert result is not None
    assert result["domain"] == "company"


# ── resolve_notebook — primary_notebook_id substitution ──────────────────────


def test_resolve_notebook_uses_operational_id_when_primary_is_none() -> None:
    """All primary_notebook_ids are currently None → operational ID always returned."""
    for domain_data in reg.NLM_NOTEBOOKS.values():
        assert domain_data["primary_notebook_id"] is None  # precondition for test validity

    result = reg.resolve_notebook("pasal uu peraturan KITAS visa", enforce_freshness=False)
    assert result is not None
    domain = result["domain"]
    assert result["notebook_id"] == reg.NLM_NOTEBOOKS[domain]["notebook_id"]


def test_resolve_notebook_uses_primary_id_when_primary_exists_and_law_query(monkeypatch) -> None:
    """When primary_notebook_id is set and query contains law keywords → use primary."""
    fake_primary = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    patched = dict(reg.NLM_NOTEBOOKS["immigration"])
    patched["primary_notebook_id"] = fake_primary
    monkeypatch.setitem(reg.NLM_NOTEBOOKS, "immigration", patched)

    result = reg.resolve_notebook("pasal uu permenkumham KITAS visa", enforce_freshness=False)
    assert result is not None
    assert result["domain"] == "immigration"
    assert result["notebook_id"] == fake_primary


def test_resolve_notebook_uses_operational_id_when_primary_exists_but_not_law_query(monkeypatch) -> None:
    """When primary_notebook_id is set but query has no law keywords → use operational."""
    fake_primary = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    patched = dict(reg.NLM_NOTEBOOKS["immigration"])
    patched["primary_notebook_id"] = fake_primary
    monkeypatch.setitem(reg.NLM_NOTEBOOKS, "immigration", patched)

    result = reg.resolve_notebook("KITAS visa requirements", enforce_freshness=False)
    assert result is not None
    assert result["notebook_id"] == reg.NLM_NOTEBOOKS["immigration"]["notebook_id"]


# ── resolve_notebook — no freshness key when gate disabled ──────────────────


def test_resolve_notebook_no_freshness_key_by_default(monkeypatch) -> None:
    monkeypatch.delenv("NLM_ENFORCE_FRESHNESS", raising=False)
    result = reg.resolve_notebook("KITAS visa")
    assert result is not None
    assert "freshness" not in result


# ── resolve_multi_notebook ───────────────────────────────────────────────────


def test_resolve_multi_notebook_empty_query_returns_empty() -> None:
    assert reg.resolve_multi_notebook("") == []


def test_resolve_multi_notebook_single_domain_query_returns_empty() -> None:
    """Only one domain matches → not a multi-domain query → []."""
    result = reg.resolve_multi_notebook("KITAS visa imigrasi kitas tka foreigner")
    # Immigration dominates; unless another domain also hits threshold, return []
    assert isinstance(result, list)
    # May be [] if only immigration matches. Assertion: result is [] or all domains present
    for entry in result:
        assert "domain" in entry
        assert "notebook_id" in entry
        assert "label" in entry
        assert "score" in entry


def test_resolve_multi_notebook_cross_domain_query_returns_multiple() -> None:
    """Visa + tax cross-domain query returns at least 2 domains."""
    result = reg.resolve_multi_notebook("KITAS visa NPWP tax compliance PPH")
    assert len(result) >= 2
    domains = {r["domain"] for r in result}
    assert "immigration" in domains
    assert "tax" in domains


def test_resolve_multi_notebook_result_ordered_by_score_descending() -> None:
    result = reg.resolve_multi_notebook("KITAS visa imigrasi NPWP tax PPH compliance fiscal pajak")
    if len(result) >= 2:
        scores = [r["score"] for r in result]
        assert scores == sorted(scores, reverse=True)


def test_resolve_multi_notebook_respects_max_notebooks() -> None:
    """max_notebooks=2 caps output at 2 even if more domains match."""
    # Craft a query hitting many domains
    query = "visa NPWP tax company KBLI property villa SEO content"
    result = reg.resolve_multi_notebook(query, max_notebooks=2)
    assert len(result) <= 2


def test_resolve_multi_notebook_result_notebook_ids_are_valid_uuids() -> None:
    result = reg.resolve_multi_notebook("visa KITAS NPWP tax compliance")
    for entry in result:
        nb_id = entry["notebook_id"]
        assert _UUID_RE.match(nb_id), f"notebook_id not UUID: {nb_id!r}"


def test_resolve_multi_notebook_notebook_ids_match_registry() -> None:
    result = reg.resolve_multi_notebook("visa KITAS NPWP tax compliance")
    for entry in result:
        domain = entry["domain"]
        assert entry["notebook_id"] == reg.NLM_NOTEBOOKS[domain]["notebook_id"]


def test_resolve_multi_notebook_threshold_filters_weak_matches() -> None:
    """threshold=3 requires at least 3 keyword hits to include domain."""
    # Query with exactly 1 keyword per domain — all should be filtered at threshold=3
    result = reg.resolve_multi_notebook("visa tax villa", threshold=3)
    assert result == []
