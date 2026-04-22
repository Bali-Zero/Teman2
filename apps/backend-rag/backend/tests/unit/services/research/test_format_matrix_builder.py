"""Tests for format_matrix_builder — 294-cell matrix (14 channels × 3 obj × 7 reg)."""

from __future__ import annotations

from backend.services.research.format_matrix_builder import (
    FormatMatrixBuilder,
    CHANNELS,
    OBJECTIVES,
    REGISTERS,
)


def test_constants_have_expected_cardinality():
    assert len(CHANNELS) == 14
    assert len(OBJECTIVES) == 3
    assert len(REGISTERS) == 7


def test_matrix_has_exactly_294_cells():
    b = FormatMatrixBuilder()
    cells = b.build_empty_matrix()
    assert len(cells) == 294


def test_cell_keys_are_unique_and_canonical():
    b = FormatMatrixBuilder()
    cells = b.build_empty_matrix()
    keys = [c["cell_key"] for c in cells]
    assert len(set(keys)) == 294
    assert "instagram:lead:pedagogico" in keys
    assert "newsletter:audience:militante" in keys
    assert "tiktok:authority:poetico" in keys


def test_cell_has_required_shape():
    b = FormatMatrixBuilder()
    cells = b.build_empty_matrix()
    sample = cells[0]
    required = {
        "cell_key", "channel", "objective", "register",
        "recommended_format", "hook_pattern", "cadence_note",
        "expected_engagement_rate_range", "confidence",
    }
    assert set(sample.keys()) >= required


def test_empty_matrix_has_null_confidence_and_format():
    b = FormatMatrixBuilder()
    cells = b.build_empty_matrix()
    for c in cells[:5]:
        assert c["recommended_format"] is None
        assert c["confidence"] is None


def test_stub_populate_fills_all_cells():
    b = FormatMatrixBuilder()
    cells = b.populate_from_playbook_stub(b.build_empty_matrix())
    assert all(c["recommended_format"] is not None for c in cells)
    assert all(c["confidence"] is not None for c in cells)
    assert all(c["hook_pattern"] is not None for c in cells)
    # Stub confidence must be low so Consiglio v1 can overwrite
    assert all(c["confidence"] <= 0.5 for c in cells)


def test_stub_populate_respects_channel_specific_formats():
    b = FormatMatrixBuilder()
    cells = b.populate_from_playbook_stub(b.build_empty_matrix())
    ig_cells = [c for c in cells if c["channel"] == "instagram"]
    li_cells = [c for c in cells if c["channel"] == "linkedin"]
    nl_cells = [c for c in cells if c["channel"] == "newsletter"]
    # IG format should never be "long_post" or "thread" (wrong platform)
    for c in ig_cells:
        assert c["recommended_format"] not in ("long_post", "thread")
    # LinkedIn authority cells should be long_post
    li_auth = [c for c in li_cells if c["objective"] == "authority"]
    assert all(c["recommended_format"] == "long_post" for c in li_auth)
    # Newsletter cells should be long_form regardless
    assert all(c["recommended_format"] == "long_form" for c in nl_cells)
