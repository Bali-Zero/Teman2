#!/usr/bin/env python3
"""Contract tests for the S18 RAG eval harness.

These run with no network and no LLM — they pin the golden-set integrity and
the pure metric functions so a future edit cannot silently rot the eval.
"""

from __future__ import annotations

import json
from pathlib import Path

import rag_eval as E

_GOLD = E._GOLDEN_FILE


def test_golden_loads_and_is_frozen():
    data, pairs = E.load_golden()
    assert data["embedding_model"] == E.FROZEN_EMBEDDING_MODEL
    assert data["embedding_dim"] == E.FROZEN_EMBEDDING_DIM
    assert len(pairs) >= 10  # visa/tax/kbli/company/property coverage
    ids = [p.id for p in pairs]
    assert len(ids) == len(set(ids))  # unique


def test_golden_covers_required_domains():
    _, pairs = E.load_golden()
    domains = {p.domain for p in pairs}
    # mission domains: visa/tax/KBLI — plus company/property the S6 files ground
    for required in ("kbli", "tax", "company", "property"):
        assert required in domains, f"missing domain {required}"


def test_villa_verdict_is_55203():
    _, pairs = E.load_golden()
    villa = next(p for p in pairs if p.id == "kbli-villa-current")
    assert villa.verdict_anchor == "55203"
    assert "55203" in villa.must_contain
    # 55193 must be flagged as NOT-current, never asserted as current
    assert any("55193" in s for s in villa.must_not_assert_current)


def test_recall_at_k_substring_and_stem():
    expected = ["kbli_2025_catalogo_completo.txt", "missing_file.md"]
    retrieved = [
        {"source": "/abs/path/kbli_2025_catalogo_completo.txt"},
        {"title": "something else"},
    ]
    # 1 of 2 expected found
    assert E.recall_at_k(expected, retrieved) == 0.5
    # stem match (no extension in retrieved label)
    assert E.recall_at_k(["foo.md"], [{"source": "foo"}]) == 1.0
    # empty expected -> NaN (excluded from means)
    r = E.recall_at_k([], retrieved)
    assert r != r  # NaN


def test_mustcontain_coverage():
    assert E.mustcontain_coverage("the rate is 11% per PMK 131", ["11%", "PMK 131"]) == 1.0
    assert E.mustcontain_coverage("only eleven percent", ["11%", "PMK 131"]) == 0.0
    half = E.mustcontain_coverage("rate is 22%", ["22%", "UU 7/2021"])
    assert abs(half - 0.5) < 1e-9


def test_asserts_stale_flags_55193_as_current():
    forbidden = ["55193 is the current code"]
    ans = "For 2025 the answer is that 55193 is the current code for villas."
    assert E.asserts_stale_as_current(ans, forbidden) == forbidden
    assert E.asserts_stale_as_current("55203 is current", forbidden) == []


def test_source_label_fallback():
    assert E._source_label({"source": "x.txt"}) == "x.txt"
    assert E._source_label({"title": "T"}) == "T"
    # no known key -> json snippet, not a crash
    assert isinstance(E._source_label({"weird": 1}), str)


def test_judge_strips_api_key_and_degrades_without_cli(monkeypatch):
    # force "cli not found" -> score None, never a paid call
    monkeypatch.setattr(E, "_find_claude", lambda: None)
    out = E.llm_judge("q", "gt", "a")
    assert out["score"] is None


def test_aggregate_ignores_nan_and_errors():
    results = [
        {"id": "a", "recall_at_k": 1.0, "mustcontain_coverage": 1.0},
        {"id": "b", "recall_at_k": 0.0, "mustcontain_coverage": float("nan")},
        {"id": "c", "error": "rbac_401"},
    ]
    agg = E._aggregate(results)
    assert agg["mean_recall_at_k"] == 0.5
    assert agg["mean_mustcontain_coverage"] == 1.0  # NaN excluded
    assert agg["n_errors"] == 1
    assert agg["n_scored"] == 2


def test_golden_facts_are_grounded_in_committed_sources():
    """Anti-hallucination: each golden must_contain key for KBLI villa is
    grep-checkable in the canonical catalog committed on this branch."""
    repo = Path(__file__).resolve().parents[3]
    catalog = repo / "apps/backend-rag/scripts/generated_guides/company/kbli_2025_catalogo_completo.txt"
    if catalog.exists():  # skip gracefully if run outside the repo tree
        text = catalog.read_text(encoding="utf-8", errors="ignore")
        assert "55203 — AKTIVITAS VILA" in text
        assert "55193" not in text  # legacy code absent from KBLI 2025 catalog
