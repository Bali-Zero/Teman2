"""Unit tests for backend.prompts.business_rules_i18n."""

import pytest

from backend.prompts.business_rules_i18n import (
    BUSINESS_PHRASES_I18N,
    all_languages_for,
    get_phrase,
)


class TestSchemaCompleteness:
    """Every phrase must have all three language variants populated."""

    @pytest.mark.parametrize("key", sorted(BUSINESS_PHRASES_I18N.keys()))
    def test_every_phrase_has_en_it_id(self, key: str) -> None:
        entry = BUSINESS_PHRASES_I18N[key]
        for lang in ("en", "it", "id"):
            assert lang in entry, f"{key} missing {lang}"
            assert isinstance(entry[lang], str)
            assert entry[lang].strip(), f"{key}.{lang} is empty"


class TestGetPhrase:
    """Localized retrieval with graceful fallbacks."""

    def test_returns_requested_language(self) -> None:
        assert "verificare con il team" in get_phrase("verify_with_team", "it")
        assert "verified with the team" in get_phrase("verify_with_team", "en")
        assert "diverifikasi dengan tim" in get_phrase("verify_with_team", "id")

    def test_unknown_language_falls_back_to_english(self) -> None:
        # Russian is not registered — we should still get the English variant.
        assert get_phrase("verify_with_team", "ru") == get_phrase(
            "verify_with_team", "en",
        )

    def test_unknown_key_returns_key_for_debug(self) -> None:
        assert get_phrase("not_a_real_key", "en") == "not_a_real_key"
        assert get_phrase("not_a_real_key", "it") == "not_a_real_key"

    def test_default_language_is_english(self) -> None:
        assert get_phrase("verify_with_team") == get_phrase(
            "verify_with_team", "en",
        )


class TestAllLanguagesFor:
    """Bulk retrieval used when injecting all variants into a prompt."""

    def test_returns_full_variant_map(self) -> None:
        variants = all_languages_for("redirect_to_indonesia")
        assert set(variants) == {"en", "it", "id"}

    def test_unknown_key_returns_empty_dict(self) -> None:
        assert all_languages_for("not_a_real_key") == {}

    def test_returns_a_copy_not_a_reference(self) -> None:
        variants = all_languages_for("verify_with_team")
        variants["en"] = "MUTATED"
        assert get_phrase("verify_with_team", "en") != "MUTATED"
