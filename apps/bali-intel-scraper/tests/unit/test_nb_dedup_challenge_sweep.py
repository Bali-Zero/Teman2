"""Tests for the --challenge-sweep mode of nb_dedup_exact_url.

Covers the deterministic challenge-page garbage sweep that unblocks an NB-INTEL
notebook stuck at NotebookLM's hard 500-source ceiling. The load-bearing test is
`test_find_challenge_pages_innocence` (cicatrix superscar #3 guard-over-match):
the exact-title allowlist must NOT fire on a legitimate article whose title merely
contains "moment" / "security" / "vercel".
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts" / "nb_dedup_exact_url.py"
)
_spec = importlib.util.spec_from_file_location("nb_dedup_exact_url", SCRIPT)
nbd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nbd)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Just a moment...", "just a moment"),
        ("Just a moment…", "just a moment"),  # unicode ellipsis
        ("  JUST A MOMENT ", "just a moment"),
        ("Vercel Security Checkpoint", "vercel security checkpoint"),
        ("Attention Required! | Cloudflare", "attention required! | cloudflare"),
    ],
)
def test_norm_title_folds_variants(raw, expected):
    assert nbd._norm_title(raw) == expected


def test_find_challenge_pages_matches_garbage():
    sources = [
        {"id": "a", "title": "Just a moment..."},
        {"id": "b", "title": "Vercel Security Checkpoint"},
        {"id": "c", "title": "Attention Required! | Cloudflare"},
        {"id": "d", "title": "Indonesia raises corporate tax to 22%"},  # real
    ]
    assert sorted(nbd.find_challenge_pages(sources)) == ["a", "b", "c"]


def test_find_challenge_pages_innocence():
    """superscar #3: exact-title only — substring lookalikes must NOT match."""
    legit = [
        {"id": "1", "title": "A moment of reckoning for crypto regulation"},
        {"id": "2", "title": "Security checkpoint delays at Ngurah Rai airport"},
        {"id": "3", "title": "Vercel raises Series E at $9B valuation"},
        {"id": "4", "title": "Just a moment in the life of a notary"},  # trailing words
        {"id": "5", "title": "Cloudflare outage post-mortem"},
    ]
    assert nbd.find_challenge_pages(legit) == []


def test_find_challenge_pages_skips_missing_id_or_title():
    sources = [
        {"title": "Just a moment..."},          # no id
        {"id": "x"},                             # no title
        {"id": "y", "title": None},              # null title
    ]
    assert nbd.find_challenge_pages(sources) == []


def test_select_challenge_deletions_gated_below_cap():
    """A notebook BELOW near_cap is left alone even if it has garbage."""
    small_nb = [{"id": "g", "title": "Just a moment..."}] + [
        {"id": f"s{i}", "title": f"Article {i}", "url": f"https://x/{i}"} for i in range(10)
    ]
    plan = nbd.select_challenge_deletions({"ai_research": small_nb}, near_cap=480)
    assert plan == []


def test_select_challenge_deletions_fires_at_cap():
    """A notebook AT/ABOVE near_cap gets its garbage planned for deletion."""
    big_nb = [{"id": "g1", "title": "Just a moment..."}, {"id": "g2", "title": "Vercel Security Checkpoint"}]
    big_nb += [{"id": f"s{i}", "title": f"Article {i}"} for i in range(498)]  # total 500
    plan = nbd.select_challenge_deletions({"ai_research": big_nb}, near_cap=480)
    assert sorted(sid for _, sid in plan) == ["g1", "g2"]
    assert all(key == "ai_research" for key, _ in plan)


def test_select_challenge_deletions_multi_nb_mixed():
    """Only near-cap notebooks contribute; below-cap ones (even with garbage) don't."""
    at_cap = [{"id": "bad", "title": "Just a moment..."}] + [
        {"id": f"a{i}", "title": f"A{i}"} for i in range(499)
    ]
    below = [{"id": "alsobad", "title": "Just a moment..."}] + [
        {"id": f"b{i}", "title": f"B{i}"} for i in range(50)
    ]
    plan = nbd.select_challenge_deletions(
        {"ai_research": at_cap, "press": below}, near_cap=480
    )
    assert plan == [("ai_research", "bad")]
