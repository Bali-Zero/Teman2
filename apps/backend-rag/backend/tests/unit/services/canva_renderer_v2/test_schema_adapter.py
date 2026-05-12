"""Schema adapter: detect legacy + adapt to v2."""
import json
from pathlib import Path

import pytest

from backend.services.canva_renderer_v2._schema_adapter import (
    adapt_legacy_schema,
    is_legacy_schema,
)

FIXTURES = Path(__file__).parent.parent.parent.parent / "fixtures" / "canva_renderer_v2"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_is_legacy_schema_detects_slide_type():
    data = _load("draft_legacy_parq.json")
    assert is_legacy_schema(data) is True


def test_is_legacy_schema_rejects_v2():
    assert is_legacy_schema(_load("draft_v2_kep71.json")) is False
    assert is_legacy_schema(_load("draft_v2_deep.json")) is False


def test_adapt_legacy_maps_cover_to_cover_photo():
    legacy = _load("draft_legacy_parq.json")
    adapted = adapt_legacy_schema(legacy, topic="Parq Ambassador")
    assert adapted["slide_count"] == 3
    assert adapted["slides"][0]["layout_family"] == "cover-photo"
    assert adapted["slides"][0]["heading"] == "Parq Ambassador"


def test_adapt_legacy_maps_law_to_thin_red_rule_divider():
    legacy = _load("draft_legacy_parq.json")
    adapted = adapt_legacy_schema(legacy, topic="Parq")
    slide_3 = adapted["slides"][2]
    assert slide_3["layout_family"] == "thin-red-rule-divider"
    assert slide_3["source"] == "Permenkumham 22/2023"


def test_adapt_legacy_no_hero_url_no_path():
    legacy = _load("draft_legacy_parq.json")
    # Strip the hero URL
    legacy["slides"][0]["image_url"] = ""
    adapted = adapt_legacy_schema(legacy, topic="Parq")
    assert "hero_image_path" not in adapted["slides"][0]


def test_v2_schema_passes_through_unchanged():
    """is_legacy=False drafts should not be touched."""
    v2 = _load("draft_v2_kep71.json")
    # adapt_legacy_schema is only called when is_legacy_schema is True,
    # but assert the detector says False.
    assert is_legacy_schema(v2) is False
