"""Tests for dependency_graph cross-NB matcher."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.evaluator.nlm_deep_research.dependency_graph import (
    _matches_key,
    find_dependencies_for_claim,
    load_dependencies,
    summarize_dependency_graph,
)


# ── _matches_key ─────────────────────────────────────────────────────────────


def test_matches_key_exact_nb_and_category() -> None:
    assert _matches_key("nb4", "FEE_CHANGE", "nb4.FEE_CHANGE.BPHTB") is True
    assert _matches_key("nb4", "FEE_CHANGE", "nb4.FEE_CHANGE") is True


def test_matches_key_wrong_nb_rejected() -> None:
    assert _matches_key("nb5", "FEE_CHANGE", "nb4.FEE_CHANGE.BPHTB") is False


def test_matches_key_wrong_category_rejected() -> None:
    assert _matches_key("nb4", "LEGAL_CHANGE", "nb4.FEE_CHANGE.BPHTB") is False


def test_matches_key_truncated_rejected() -> None:
    assert _matches_key("nb4", "FEE_CHANGE", "nb4") is False


# ── load_dependencies ────────────────────────────────────────────────────────


def test_load_dependencies_from_file(tmp_path: Path) -> None:
    data = {
        "_meta": {"version": 1},
        "dependencies": {
            "nb4.FEE_CHANGE.X": {"keywords": ["x"], "requires_context_from": []},
        },
    }
    f = tmp_path / "nb_dependency.json"
    f.write_text(json.dumps(data))

    deps = load_dependencies(path=f, force_reload=True)
    assert len(deps) == 1
    assert "nb4.FEE_CHANGE.X" in deps


def test_load_dependencies_missing_file_returns_empty(tmp_path: Path) -> None:
    deps = load_dependencies(path=tmp_path / "nonexistent.json", force_reload=True)
    assert deps == {}


def test_load_dependencies_malformed_json_returns_empty(tmp_path: Path) -> None:
    f = tmp_path / "bad.json"
    f.write_text("not-json{{{")
    deps = load_dependencies(path=f, force_reload=True)
    assert deps == {}


def test_load_dependencies_missing_dependencies_key_returns_empty(tmp_path: Path) -> None:
    f = tmp_path / "nb_dependency.json"
    f.write_text(json.dumps({"_meta": {}}))
    deps = load_dependencies(path=f, force_reload=True)
    assert deps == {}


# ── find_dependencies_for_claim ──────────────────────────────────────────────


def _fixture_deps() -> dict:
    return {
        "nb4.FEE_CHANGE.BPHTB": {
            "requires_context_from": ["nb5.PROCEDURAL_STEP.AJB_process"],
            "enriches": ["nb5.FEE_CHANGE.property_transfer_cost"],
            "keywords": ["bphtb", "bea perolehan hak atas tanah"],
            "gloss": "BPHTB",
        },
        "nb4.FEE_CHANGE.PPh_21": {
            "requires_context_from": ["nb10.ELIGIBILITY_RULE.foreign_hire_status"],
            "enriches": [],
            "keywords": ["pph 21", "withholding"],
            "gloss": "Income tax withholding",
        },
        "nb5.LEGAL_CHANGE.HGB_rules": {
            "requires_context_from": [],
            "enriches": ["nb4.FEE_CHANGE.BPHTB"],
            "keywords": ["hgb", "hak guna bangunan"],
            "gloss": "HGB",
        },
    }


def test_find_dependencies_matches_keyword() -> None:
    deps = _fixture_deps()
    matches = find_dependencies_for_claim(
        claim_text="The BPHTB rate changed in 2026.",
        category="FEE_CHANGE",
        nb="nb4",
        deps=deps,
    )
    assert len(matches) == 1
    assert matches[0]["key"] == "nb4.FEE_CHANGE.BPHTB"
    assert matches[0]["matched_keywords"] == ["bphtb"]


def test_find_dependencies_case_insensitive() -> None:
    deps = _fixture_deps()
    matches = find_dependencies_for_claim(
        claim_text="HGB rules updated per PP 28/2025.",
        category="LEGAL_CHANGE",
        nb="nb5",
        deps=deps,
    )
    assert len(matches) == 1
    assert matches[0]["matched_keywords"] == ["hgb"]


def test_find_dependencies_wrong_nb_no_match() -> None:
    deps = _fixture_deps()
    matches = find_dependencies_for_claim(
        claim_text="BPHTB for land transfer.",
        category="FEE_CHANGE",
        nb="nb5",  # wrong
        deps=deps,
    )
    assert matches == []


def test_find_dependencies_wrong_category_no_match() -> None:
    deps = _fixture_deps()
    matches = find_dependencies_for_claim(
        claim_text="BPHTB regulation.",
        category="LEGAL_CHANGE",  # wrong; BPHTB dep is FEE_CHANGE
        nb="nb4",
        deps=deps,
    )
    assert matches == []


def test_find_dependencies_ranks_by_match_count() -> None:
    deps = _fixture_deps()
    # BPHTB has 2 keywords — if both appear, match_score=2
    matches = find_dependencies_for_claim(
        claim_text="BPHTB (bea perolehan hak atas tanah) changed.",
        category="FEE_CHANGE",
        nb="nb4",
        deps=deps,
    )
    assert len(matches) == 1
    assert matches[0]["match_score"] == 2


def test_find_dependencies_no_keyword_no_match() -> None:
    deps = _fixture_deps()
    matches = find_dependencies_for_claim(
        claim_text="Nothing relevant in this text.",
        category="FEE_CHANGE",
        nb="nb4",
        deps=deps,
    )
    assert matches == []


def test_find_dependencies_empty_inputs_safe() -> None:
    deps = _fixture_deps()
    assert find_dependencies_for_claim("", "FEE_CHANGE", "nb4", deps) == []
    assert find_dependencies_for_claim("bphtb", "", "nb4", deps) == []
    assert find_dependencies_for_claim("bphtb", "FEE_CHANGE", "", deps) == []


def test_find_dependencies_no_deps_map_loads_canonical(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When deps=None passed, load_dependencies is called."""
    # Point to empty dir so load_dependencies returns {}
    monkeypatch.setattr(
        "apps.evaluator.nlm_deep_research.dependency_graph.DEPENDENCIES_FILE",
        tmp_path / "nonexistent.json",
    )
    # Also clear cache so previous tests don't bleed in
    monkeypatch.setattr("apps.evaluator.nlm_deep_research.dependency_graph._cache", {})
    matches = find_dependencies_for_claim(
        claim_text="BPHTB changes",
        category="FEE_CHANGE",
        nb="nb4",
        deps=None,
    )
    assert matches == []


# ── summarize_dependency_graph ───────────────────────────────────────────────


def test_summarize_counts_entries_and_nbs() -> None:
    deps = _fixture_deps()
    s = summarize_dependency_graph(deps)
    assert s["entry_count"] == 3
    assert "nb4" in s["source_nbs"]
    assert "nb5" in s["source_nbs"]
    assert "nb5" in s["target_nbs"]
    assert "nb10" in s["target_nbs"]
    # Edges
    assert s["total_requires_context_edges"] >= 2
    assert s["total_enriches_edges"] >= 2


def test_summarize_empty_map() -> None:
    s = summarize_dependency_graph({})
    assert s == {"entry_count": 0, "source_nbs": [], "target_nbs": []}


# ── Canonical nb_dependency.json is valid ────────────────────────────────────


def test_real_nb_dependency_json_loads_and_is_nonempty() -> None:
    """Smoke test: the curated file in-tree is parseable + nonzero entries."""
    deps = load_dependencies(force_reload=True)
    # Should have at least 10 curated entries
    assert len(deps) >= 10
    # Every entry must have keywords list
    for key, entry in deps.items():
        assert "keywords" in entry, f"entry {key} missing keywords"
        assert isinstance(entry["keywords"], list)


def test_real_nb_dependency_json_matches_canonical_bphtb() -> None:
    matches = find_dependencies_for_claim(
        claim_text="BPHTB rate 2.5% per PP 28/2025",
        category="FEE_CHANGE",
        nb="nb4",
    )
    assert any(m["key"] == "nb4.FEE_CHANGE.BPHTB" for m in matches)
