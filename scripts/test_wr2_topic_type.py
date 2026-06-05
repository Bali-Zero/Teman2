#!/usr/bin/env python3
"""Tests for wr2_topic_type derivation helpers + the image_mode normalise survival.

Run (from scripts/, with the backend venv active):
    PYTHONPATH=<repo>/apps/backend-rag:<repo>/scripts \
        python -m pytest test_wr2_topic_type.py -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# scripts/ on path so the sibling pure module imports regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import wr2_topic_type as tt  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────
# derive_domain
# ─────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "topic,expected",
    [
        ("New KITAS rules for sham investors", "visa"),
        ("E33G Golden Visa explained", "visa"),
        ("Digital nomad visa Indonesia", "visa"),
        ("Coretax and the new PPN rate", "tax"),
        ("How PPh 21 withholding works", "tax"),
        ("NPWP for foreign founders", "tax"),
        ("Hak Pakai land rights for foreigners", "property"),
        ("Nominee villa ownership risks", "property"),
        ("Leasehold vs freehold in Bali", "property"),
        ("Permenaker labor changes 2025", "regulatory"),
        ("KBLI codes for a PT PMA", "regulatory"),
        ("LKPM reporting obligations", "regulatory"),
        ("BPJS Kesehatan for expats", "health"),  # must beat the regulatory bucket
        ("Layanan kesehatan di Bali", "health"),
        ("Bali Zero: our story so far", "brand"),
    ],
)
def test_derive_domain_buckets(topic: str, expected: str) -> None:
    assert tt.derive_domain(topic) == expected


@pytest.mark.parametrize(
    "topic",
    ["Bali sunset photography", "A random unrelated headline", "", "   "],
)
def test_derive_domain_unknown(topic: str) -> None:
    assert tt.derive_domain(topic) == "unknown"


def test_derive_domain_none_and_nonstr() -> None:
    assert tt.derive_domain(None) == "unknown"
    assert tt.derive_domain(12345) == "unknown"  # type: ignore[arg-type]


def test_derive_domain_case_insensitive() -> None:
    assert tt.derive_domain("KITAS RULES") == "visa"
    assert tt.derive_domain("kitas rules") == "visa"


def test_derive_domain_regulatory_bpjs_specificity() -> None:
    # bare "BPJS" with no "kesehatan" should NOT be claimed as health by accident,
    # and the labor-specific token routes to regulatory.
    assert tt.derive_domain("BPJS Ketenagakerjaan contributions") == "regulatory"


# ─────────────────────────────────────────────────────────────────────────
# derive_dominant_mode
# ─────────────────────────────────────────────────────────────────────────
def test_dominant_mode_simple_majority() -> None:
    slides = {
        "slides": [
            {"image_mode": "desk-document"},
            {"image_mode": "desk-document"},
            {"image_mode": "event-photo"},
        ]
    }
    assert tt.derive_dominant_mode(slides) == "desk-document"


def test_dominant_mode_case_normalised() -> None:
    slides = {"slides": [{"image_mode": "Desk-Document"}, {"image_mode": "desk-document"}]}
    assert tt.derive_dominant_mode(slides) == "desk-document"


def test_dominant_mode_tie_is_unknown() -> None:
    slides = {"slides": [{"image_mode": "a"}, {"image_mode": "b"}]}
    assert tt.derive_dominant_mode(slides) == "unknown"


def test_dominant_mode_empty_is_unknown() -> None:
    assert tt.derive_dominant_mode({"slides": []}) == "unknown"
    assert tt.derive_dominant_mode({}) == "unknown"
    assert tt.derive_dominant_mode(None) == "unknown"


def test_dominant_mode_no_mode_field_is_unknown() -> None:
    slides = {"slides": [{"headline": "x"}, {"headline": "y"}]}
    assert tt.derive_dominant_mode(slides) == "unknown"


def test_dominant_mode_malformed_string_is_unknown() -> None:
    assert tt.derive_dominant_mode("{not valid json") == "unknown"
    assert tt.derive_dominant_mode("[1,2,3") == "unknown"


def test_dominant_mode_accepts_json_string() -> None:
    raw = json.dumps({"slides": [{"image_mode": "cultural-photo"}, {"image_mode": "cultural-photo"}]})
    assert tt.derive_dominant_mode(raw) == "cultural-photo"


def test_dominant_mode_accepts_bare_list() -> None:
    slides = [{"image_mode": "calendar-photo"}, {"image_mode": "calendar-photo"}]
    assert tt.derive_dominant_mode(slides) == "calendar-photo"


def test_dominant_mode_alt_field_name() -> None:
    slides = {"slides": [{"image_style_mode": "data-visualization"}, {"image_style_mode": "data-visualization"}]}
    assert tt.derive_dominant_mode(slides) == "data-visualization"


# ─────────────────────────────────────────────────────────────────────────
# distinct_mode_count
# ─────────────────────────────────────────────────────────────────────────
def test_distinct_mode_count() -> None:
    slides = {
        "slides": [
            {"image_mode": "desk-document"},
            {"image_mode": "event-photo"},
            {"image_mode": "desk-document"},
            {"image_mode": "cultural-photo"},
        ]
    }
    assert tt.distinct_mode_count(slides) == 3


def test_distinct_mode_count_malformed() -> None:
    assert tt.distinct_mode_count("garbage") == 0
    assert tt.distinct_mode_count({"slides": []}) == 0


# ─────────────────────────────────────────────────────────────────────────
# derive_layout_family / extract_archetype
# ─────────────────────────────────────────────────────────────────────────
def test_layout_family_from_per_slide() -> None:
    slides = {
        "slides": [
            {"layout_family": "Grid"},
            {"layout_family": "grid"},
            {"layout_family": "stack"},
        ]
    }
    assert tt.derive_layout_family(slides) == "grid"


def test_layout_family_falls_back_to_archetype() -> None:
    slides = {"archetype": "Timeline", "slides": [{"headline": "x"}]}
    assert tt.derive_layout_family(slides) == "timeline"


def test_layout_family_none_when_absent() -> None:
    assert tt.derive_layout_family({"slides": [{"headline": "x"}]}) is None
    assert tt.derive_layout_family("garbage") is None


def test_extract_archetype() -> None:
    assert tt.extract_archetype({"archetype": "Manifesto"}) == "manifesto"
    assert tt.extract_archetype({"slides": []}) is None
    assert tt.extract_archetype("garbage") is None
    assert tt.extract_archetype(None) is None


# ─────────────────────────────────────────────────────────────────────────
# Collision logic (the anti-sameness rule: differ in EITHER register OR mode)
# ─────────────────────────────────────────────────────────────────────────
def test_collision_matches_both_is_collision() -> None:
    assert tt.is_same_combo("analitico", "desk-document", "analitico", "desk-document") is True


def test_collision_differs_in_mode_is_ok() -> None:
    assert tt.is_same_combo("analitico", "desk-document", "analitico", "event-photo") is False


def test_collision_differs_in_register_is_ok() -> None:
    assert tt.is_same_combo("analitico", "desk-document", "tecnico", "desk-document") is False


def test_collision_unknown_mode_falls_back_to_register_only() -> None:
    # mode unknown on one side -> register-only comparison -> same register collides
    assert tt.is_same_combo("analitico", "unknown", "analitico", "desk-document") is True
    assert tt.is_same_combo("analitico", "unknown", "tecnico", "desk-document") is False


def test_collision_unknown_mode_both_sides() -> None:
    assert tt.is_same_combo("analitico", "unknown", "analitico", "unknown") is True


def test_collision_register_none_never_collides() -> None:
    assert tt.is_same_combo(None, "desk-document", "analitico", "desk-document") is False
    assert tt.is_same_combo("analitico", "desk-document", None, "desk-document") is False


def test_collides_with_recent_empty_history_is_ok() -> None:
    assert tt.collides_with_recent("analitico", "desk-document", []) is False


def test_collides_with_recent_hit_on_second() -> None:
    recent = [
        {"register": "tecnico", "dominant_mode": "event-photo"},
        {"register": "analitico", "dominant_mode": "desk-document"},
    ]
    assert tt.collides_with_recent("analitico", "desk-document", recent) is True


def test_collides_with_recent_no_hit() -> None:
    recent = [
        {"register": "tecnico", "dominant_mode": "event-photo"},
        {"register": "poetico", "dominant_mode": "cultural-photo"},
    ]
    assert tt.collides_with_recent("analitico", "desk-document", recent) is False


def test_collides_with_recent_differs_in_mode_only_is_ok() -> None:
    # same register as a recent row, but different mode -> allowed (differ-in-either)
    recent = [{"register": "analitico", "dominant_mode": "event-photo"}]
    assert tt.collides_with_recent("analitico", "desk-document", recent) is False


# ─────────────────────────────────────────────────────────────────────────
# image_mode survives _normalise_slides (panel-critical, §3.0)
# ─────────────────────────────────────────────────────────────────────────
def _make_parsed(extra_first: dict) -> dict:
    first = {
        "slide_number": 1,
        "is_cover": True,
        "is_hero_image": True,
        "headline": "H",
        "body": "B",
        "image_prompt": "P",
    }
    first.update(extra_first)
    rest = [
        {
            "slide_number": n,
            "is_hero_image": False,
            "headline": f"h{n}",
            "body": "b",
            "image_prompt": "p",
        }
        for n in range(2, 12)
    ]
    return {"register": "analitico", "slides": [first] + rest}


def test_normalise_image_mode_survives_lowercased() -> None:
    import wr2_draft_generator as g

    register, slides = g._normalise_slides(_make_parsed({"image_mode": "Desk-Document"}))
    assert register == "analitico"
    assert slides[0]["image_mode"] == "desk-document"


def test_normalise_image_mode_absent_is_none() -> None:
    import wr2_draft_generator as g

    _register, slides = g._normalise_slides(_make_parsed({}))
    # absent on slide 1
    assert slides[0]["image_mode"] is None
    # present (as a key) on every slide
    assert all("image_mode" in s for s in slides)


def test_normalise_image_mode_blank_is_none() -> None:
    import wr2_draft_generator as g

    _register, slides = g._normalise_slides(_make_parsed({"image_mode": "   "}))
    assert slides[0]["image_mode"] is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
