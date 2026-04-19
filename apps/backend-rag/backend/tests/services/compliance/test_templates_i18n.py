"""
templates_i18n: TEMPLATE_REGISTRY + Jinja interpolation with IT/EN/ID + fallback chain.
"""
from __future__ import annotations

import pytest

from backend.services.compliance.templates_i18n import (
    TEMPLATE_REGISTRY,
    render_template,
    TemplateCategory,
    TemplateField,
)


class TestRegistryShape:
    def test_all_categories_have_all_three_langs(self) -> None:
        required_langs = {"it", "en", "id"}
        for category, fields in TEMPLATE_REGISTRY.items():
            for field, per_lang in fields.items():
                missing = required_langs - set(per_lang.keys())
                assert not missing, f"{category}.{field} missing: {missing}"

    def test_visa_expiry_has_required_fields(self) -> None:
        required = {"title", "body", "action"}
        assert required <= set(TEMPLATE_REGISTRY["visa_expiry"].keys())


class TestRender:
    def test_render_italian(self) -> None:
        out = render_template(
            "visa_expiry", "body", "it",
            days_until=7, visa_type="C1",
        )
        assert "7" in out

    def test_render_missing_lang_falls_back_to_en(self, monkeypatch) -> None:
        # Simulate a category/field with only 'en' + 'it'
        test_reg = {
            "fake_cat": {
                "msg": {"en": "Hello", "it": "Ciao"},
            },
        }
        monkeypatch.setattr(
            "backend.services.compliance.templates_i18n.TEMPLATE_REGISTRY",
            test_reg,
        )
        out = render_template("fake_cat", "msg", "id")  # id missing → en fallback
        assert out == "Hello"

    def test_render_missing_en_falls_back_to_it(self, monkeypatch) -> None:
        test_reg = {"fake_cat": {"msg": {"it": "Ciao"}}}
        monkeypatch.setattr(
            "backend.services.compliance.templates_i18n.TEMPLATE_REGISTRY",
            test_reg,
        )
        out = render_template("fake_cat", "msg", "id")
        assert out == "Ciao"

    def test_render_unknown_category_raises(self) -> None:
        with pytest.raises(KeyError):
            render_template("nope", "body", "it")

    def test_render_unknown_field_raises(self) -> None:
        with pytest.raises(KeyError):
            render_template("visa_expiry", "nope", "it")

    def test_render_injects_jinja_variables(self) -> None:
        # The visa_expiry body template uses {{ days_until }}.
        out = render_template(
            "visa_expiry", "body", "en",
            days_until=14, visa_type="B211A",
        )
        assert "14" in out
        assert "B211A" in out
