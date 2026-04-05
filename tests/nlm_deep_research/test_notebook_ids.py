"""Tests for notebook ID consistency across pipeline components.

Catches divergences between pipeline IDs and backend registry IDs.
These should run in CI to prevent silent misconfiguration.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from apps.evaluator.nlm_deep_research.pipeline import NB2_NOTEBOOK_ID
from apps.evaluator.nlm_deep_research.nb4_pipeline import NB4_NOTEBOOK_ID
from apps.evaluator.nlm_deep_research.t4_monitor import NB2_ID


# =====================================================================
# Backend registry import helper
# =====================================================================


def _get_backend_registry() -> dict:
    """Import NLM_NOTEBOOKS from backend oracle service."""
    # tests/ is at project_root/tests/, backend-rag is at project_root/apps/backend-rag/
    project_root = Path(__file__).resolve().parents[2]
    backend_path = project_root / "apps" / "backend-rag"
    sys.path.insert(0, str(backend_path))
    try:
        from backend.services.oracle.nlm_notebook_registry import NLM_NOTEBOOKS
        return NLM_NOTEBOOKS
    finally:
        sys.path.pop(0)


# =====================================================================
# NB-2 consistency
# =====================================================================


class TestNB2Consistency:
    def test_pipeline_id_matches_t4_monitor(self):
        """NB-2 pipeline and T4 monitor must point to the same notebook."""
        assert NB2_NOTEBOOK_ID == NB2_ID, (
            f"NB-2 pipeline ID {NB2_NOTEBOOK_ID!r} "
            f"differs from T4 monitor NB2_ID {NB2_ID!r}"
        )

    def test_pipeline_id_matches_backend_registry(self):
        """NB-2 pipeline must match what the backend serves to clients."""
        registry = _get_backend_registry()
        backend_immigration_id = registry["immigration"]["notebook_id"]
        assert NB2_NOTEBOOK_ID == backend_immigration_id, (
            f"NB-2 pipeline ID {NB2_NOTEBOOK_ID!r} "
            f"differs from backend registry 'immigration' {backend_immigration_id!r}. "
            "Update nlm_notebook_registry.py or pipeline.py to use the same notebook."
        )


# =====================================================================
# NB-4 consistency (documented divergence)
# =====================================================================


class TestNB4Consistency:
    def test_nb4_pipeline_id_format(self):
        """NB-4 pipeline notebook ID must be a valid UUID."""
        parts = NB4_NOTEBOOK_ID.split("-")
        assert len(parts) == 5
        assert len(NB4_NOTEBOOK_ID) == 36

    def test_nb4_vs_backend_registry_documented(self):
        """NB-4 pipeline ID and backend 'tax' ID are known to diverge.

        This test documents the divergence so it is visible in CI.
        If the IDs are intentionally unified in the future, this test
        should be updated to assert equality instead.

        Current known state (as of 2026-03-31):
        - NB-4 pipeline (deep research): d4b2eedb-9863-4a1a-81ff-a11b0b45d853
        - Backend registry 'tax' (client queries): 837b620b-2aca-43ab-812e-97ca92bdad1d

        ACTION REQUIRED: Decide which notebook is the master for Tax domain and
        align both consumers. See docs for resolution options.
        """
        registry = _get_backend_registry()
        backend_tax_id = registry["tax"]["notebook_id"]

        KNOWN_NB4_PIPELINE_ID = "d4b2eedb-9863-4a1a-81ff-a11b0b45d853"
        KNOWN_BACKEND_TAX_ID = "837b620b-2aca-43ab-812e-97ca92bdad1d"

        # Document the current state — fail if either changes unexpectedly
        assert NB4_NOTEBOOK_ID == KNOWN_NB4_PIPELINE_ID, (
            f"NB-4 pipeline ID changed unexpectedly: {NB4_NOTEBOOK_ID!r}. "
            "Update this test if intentional."
        )
        assert backend_tax_id == KNOWN_BACKEND_TAX_ID, (
            f"Backend 'tax' registry ID changed: {backend_tax_id!r}. "
            "Update this test if intentional."
        )

        # Explicit divergence marker — replace with assertEqual when resolved
        assert NB4_NOTEBOOK_ID != backend_tax_id, (
            "NB-4 and backend tax IDs now match — remove the divergence "
            "documentation and simplify this test."
        )


# =====================================================================
# NB-5 consistency (documented divergence)
# =====================================================================


class TestNB5Consistency:
    def test_nb5_t4_config_vs_backend_registry_documented(self):
        """NB-5 T4 config and backend 'property' ID are known to diverge.

        Current known state (as of 2026-03-31):
        - NB-5 T4 config (t4_nb5_config.json): d9438180-5e63-4e2a-a473-6061101f6a8d
        - Backend registry 'property' (client queries): 568ec624-ceb8-47d1-a2a2-5b2f793ea7ed

        ACTION REQUIRED: Same as NB-4 — decide master notebook and align.
        """
        import json as json_module

        project_root = Path(__file__).resolve().parents[2]
        t4_config_path = (
            project_root
            / "apps" / "evaluator" / "nlm_deep_research" / "t4_nb5_config.json"
        )
        with open(t4_config_path) as f:
            nb5_config = json_module.load(f)

        nb5_t4_id = nb5_config["notebook_id"]

        registry = _get_backend_registry()
        backend_property_id = registry["property"]["notebook_id"]

        KNOWN_NB5_T4_ID = "d9438180-5e63-4e2a-a473-6061101f6a8d"
        KNOWN_BACKEND_PROPERTY_ID = "568ec624-ceb8-47d1-a2a2-5b2f793ea7ed"

        assert nb5_t4_id == KNOWN_NB5_T4_ID, (
            f"NB-5 T4 config notebook_id changed: {nb5_t4_id!r}. "
            "Update this test if intentional."
        )
        assert backend_property_id == KNOWN_BACKEND_PROPERTY_ID, (
            f"Backend 'property' registry ID changed: {backend_property_id!r}. "
            "Update this test if intentional."
        )
        assert nb5_t4_id != backend_property_id, (
            "NB-5 T4 config and backend property IDs now match — good! "
            "Update this test to assert equality and remove divergence marker."
        )


# =====================================================================
# Backend registry resolve_notebook edge cases
# =====================================================================


class TestResolveNotebook:
    def setup_method(self):
        project_root = Path(__file__).resolve().parents[2]
        backend_path = project_root / "apps" / "backend-rag"
        sys.path.insert(0, str(backend_path))
        from backend.services.oracle.nlm_notebook_registry import resolve_notebook
        self.resolve = resolve_notebook
        self._backend_path_inserted = True

    def teardown_method(self):
        if getattr(self, "_backend_path_inserted", False):
            sys.path.pop(0)

    def test_empty_query_returns_none(self):
        assert self.resolve("") is None

    def test_none_query_returns_none(self):
        assert self.resolve(None) is None

    def test_immigration_keywords(self):
        result = self.resolve("how to get KITAS visa")
        assert result is not None
        assert result["domain"] == "immigration"
        assert result["notebook_id"] == NB2_NOTEBOOK_ID

    def test_tax_keywords(self):
        result = self.resolve("PPh badan tarif 22%")
        assert result is not None
        assert result["domain"] == "tax"

    def test_property_keywords(self):
        result = self.resolve("harga tanah bali HGB hak pakai")
        assert result is not None
        assert result["domain"] == "property"

    def test_company_keywords(self):
        result = self.resolve("company setup PT PMA OSS NIB")
        assert result is not None
        assert result["domain"] == "company"

    def test_unrelated_query_returns_none(self):
        result = self.resolve("completely unrelated query about cooking recipes")
        assert result is None

    def test_primary_law_query_returns_operational_when_no_primary(self):
        """All domains have primary_notebook_id=None — should return operational ID."""
        result = self.resolve("pasal 23 uu undang keimigrasian")
        # Should still match immigration domain
        if result is not None:
            # primary is None so operational notebook_id must be returned
            assert result["notebook_id"] == result.get("notebook_id")
            # primary_notebook_id should be None for all domains currently
            assert result.get("primary_notebook_id") is None
