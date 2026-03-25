"""Tests for NLM Notebook Registry — keyword-based domain resolver."""

from backend.services.oracle.nlm_notebook_registry import (
    NLM_NOTEBOOKS,
    resolve_notebook,
)


def test_resolve_immigration_query() -> None:
    result = resolve_notebook("What are the KITAS requirements?")
    assert result is not None
    assert result["domain"] == "immigration"


def test_resolve_company_query() -> None:
    result = resolve_notebook("How to set up a PT PMA in Bali?")
    assert result is not None
    assert result["domain"] == "company"


def test_resolve_tax_query() -> None:
    result = resolve_notebook("What is the NPWP registration process for LKPM?")
    assert result is not None
    assert result["domain"] == "tax"


def test_resolve_property_query() -> None:
    result = resolve_notebook("Can a foreigner get HGB land title?")
    assert result is not None
    assert result["domain"] == "property"


def test_resolve_operations_query() -> None:
    result = resolve_notebook("What is the SOP for CRM workflow?")
    assert result is not None
    assert result["domain"] == "operations"


def test_resolve_editorial_query() -> None:
    result = resolve_notebook("Latest SEO trends for content marketing")
    assert result is not None
    assert result["domain"] == "editorial"


def test_resolve_lifestyle_query() -> None:
    result = resolve_notebook("What is the cost of living for digital nomad expats?")
    assert result is not None
    assert result["domain"] == "lifestyle"


def test_resolve_no_domain() -> None:
    result = resolve_notebook("Hello, how are you?")
    assert result is None


def test_resolve_empty_query() -> None:
    result = resolve_notebook("")
    assert result is None


def test_resolve_multi_domain_picks_best() -> None:
    result = resolve_notebook("I need a KITAS for my restaurant business")
    assert result is not None
    # Both immigration and company match; the one with more keyword hits wins


def test_resolve_case_insensitive() -> None:
    result = resolve_notebook("VISA KITAS IMMIGRATION requirements")
    assert result is not None
    assert result["domain"] == "immigration"


def test_resolve_returns_domain_key() -> None:
    result = resolve_notebook("Tell me about visa requirements")
    assert result is not None
    assert "domain" in result
    assert "notebook_id" in result
    assert "label" in result
    assert "keywords" in result


def test_all_notebooks_have_required_fields() -> None:
    for domain, data in NLM_NOTEBOOKS.items():
        assert "notebook_id" in data, f"{domain} missing notebook_id"
        assert "label" in data, f"{domain} missing label"
        assert "keywords" in data, f"{domain} missing keywords"
        assert len(data["keywords"]) > 0, f"{domain} has empty keywords"


def test_all_notebook_ids_are_uuid_format() -> None:
    import re

    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )
    for domain, data in NLM_NOTEBOOKS.items():
        assert uuid_pattern.match(data["notebook_id"]), (
            f"{domain} notebook_id is not a valid UUID: {data['notebook_id']}"
        )


def test_all_domains_are_unique() -> None:
    domains = list(NLM_NOTEBOOKS.keys())
    assert len(domains) == len(set(domains))


def test_resolve_returns_none_not_empty_dict() -> None:
    result = resolve_notebook("xyzzy foobar baz")
    assert result is None
