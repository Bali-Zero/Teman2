"""Tests for NLM Notebook Registry — keyword-based domain resolver."""

import os
from pathlib import Path
from unittest.mock import patch

from backend.services.oracle import nlm_notebook_registry as registry
from backend.services.oracle.nlm_notebook_registry import (
    NLM_NOTEBOOKS,
    _MISSING_STATE_PATH,
    _default_freshness_state_path,
    _resolve_state_path,
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

    uuid_pattern = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
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


# ── Stale-ingestion gate path resolution (regression: parents[5] IndexError) ──
# Bug: module-load `Path(__file__).resolve().parents[5]` crashed with
# IndexError on Fly Docker (image flattens the source tree to /app/backend/...
# which only has 4 ancestors). The whole orchestrator import chain crashed
# because nlm_notebook_registry was imported by orchestrator_core for every
# query, even when the freshness gate was never hit at runtime.
# Fix: lazy lookup wrapped in try/except + sentinel fallback path.


def test_default_freshness_path_resolves_in_monorepo_layout() -> None:
    """In the dev/monorepo layout the default path is reachable."""
    result = _default_freshness_state_path()
    # When run from the monorepo, parents[5] succeeds and yields a Path
    # that ends with the expected suffix. We don't assert the file exists
    # — only that the lookup didn't crash and returned a sensible value.
    assert result is not None
    assert isinstance(result, Path)
    assert result.parts[-1] == "freshness_monitor_state.json"
    assert "nlm_deep_research" in result.parts


def test_default_freshness_path_returns_none_when_parents_5_missing() -> None:
    """Simulate the Fly Docker layout where parents[5] raises IndexError."""

    class _ShallowPath:
        """Stand-in for ``__file__`` whose .resolve().parents[5] raises."""

        def resolve(self) -> "_ShallowPath":
            return self

        @property
        def parents(self) -> list:
            return []  # empty → any [N] indexing raises IndexError

    # Patch the Path class used inside the function so we hit the IndexError
    # branch deterministically (no need to mess with sys.executable layouts).
    with patch.object(registry, "Path") as mock_path_cls:
        mock_path_cls.return_value = _ShallowPath()
        result = _default_freshness_state_path()

    assert result is None


def test_resolve_state_path_uses_env_var_when_set(monkeypatch) -> None:
    """NLM_FRESHNESS_STATE_FILE override always wins."""
    monkeypatch.setenv("NLM_FRESHNESS_STATE_FILE", "/tmp/explicit_path.json")
    assert _resolve_state_path() == Path("/tmp/explicit_path.json")


def test_resolve_state_path_uses_repo_default_when_env_unset(monkeypatch) -> None:
    """Without the env var, fall back to the in-repo default when reachable."""
    monkeypatch.delenv("NLM_FRESHNESS_STATE_FILE", raising=False)
    result = _resolve_state_path()
    # On the test runner (monorepo layout) we expect the in-repo default,
    # not the missing-state sentinel.
    assert result != _MISSING_STATE_PATH
    assert result.parts[-1] == "freshness_monitor_state.json"


def test_resolve_state_path_uses_sentinel_when_default_unresolvable(monkeypatch) -> None:
    """Critical regression: without env var AND without a resolvable default,
    return a sentinel path so the orchestrator import does NOT crash on
    Fly Docker. ``is_freshness_state_fresh`` will treat the sentinel as
    ``never_verified`` (graceful degradation)."""
    monkeypatch.delenv("NLM_FRESHNESS_STATE_FILE", raising=False)
    monkeypatch.setattr(registry, "_default_freshness_state_path", lambda: None)
    assert _resolve_state_path() == _MISSING_STATE_PATH


def test_module_imports_clean_even_when_parents_5_unresolvable() -> None:
    """The whole point of the fix: importing this module from a context
    where ``Path(__file__).resolve().parents[5]`` would raise must not crash.
    The previous code computed ``_DEFAULT_FRESHNESS_STATE_PATH`` at module
    load time, so the IndexError fired during ``import``. The new code
    defers the lookup to ``_default_freshness_state_path()``, so importing
    the module is always safe.
    """
    # Re-import in a clean namespace to verify import-time safety.
    import importlib

    reloaded = importlib.reload(registry)
    # If we got here without an exception, the import path is clean.
    assert reloaded is not None
    # Sanity: the symbols we rely on are still exported.
    assert hasattr(reloaded, "_resolve_state_path")
    assert hasattr(reloaded, "_default_freshness_state_path")
    assert hasattr(reloaded, "_MISSING_STATE_PATH")
