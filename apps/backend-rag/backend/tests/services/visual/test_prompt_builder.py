"""Unit tests for build_imagen_prompt + brand/negative constants."""

from __future__ import annotations

import pytest

from backend.services.visual.prompt_builder import (
    BRAND_SUFFIX,
    DEFAULT_STYLE_MODIFIERS,
    NEGATIVE_PROMPT,
    build_imagen_prompt,
)


def test_scene_core_required():
    with pytest.raises(ValueError):
        build_imagen_prompt("")


def test_default_layers_assembled():
    prompt = build_imagen_prompt("officer at desk reviewing KBLI documents")
    assert "officer at desk" in prompt
    assert BRAND_SUFFIX in prompt
    for modifier in DEFAULT_STYLE_MODIFIERS:
        assert modifier in prompt


def test_custom_style_modifiers():
    prompt = build_imagen_prompt(
        "sunrise over Ngurah Rai",
        style_modifiers=("neutral news photography", "soft color grading"),
    )
    assert "sunrise over Ngurah Rai" in prompt
    assert "neutral news photography" in prompt
    assert "soft color grading" in prompt
    # default modifiers must NOT be present when explicit ones passed
    assert "macrografia editoriale" not in prompt


def test_extra_hints_appended():
    prompt = build_imagen_prompt(
        "visa stamp close-up",
        extra_hints="shallow depth of field, --ar 4:5",
    )
    assert "visa stamp close-up" in prompt
    assert "shallow depth of field" in prompt


def test_negative_prompt_includes_scars():
    """NEGATIVE_PROMPT must block the failure modes we've seen in War Room v1."""
    neg = NEGATIVE_PROMPT
    assert "deformed hands" in neg
    assert "extra fingers" in neg
    assert "watermark" in neg
    assert "stock" in neg.lower()
