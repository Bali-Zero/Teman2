"""
Test email templates and localization.
"""

import pytest

from backend.app.modules.notifications.models import AlertType
from backend.app.modules.notifications.templates import (
    INDONESIAN_BLESSINGS,
    format_template,
    get_template,
)


class TestTemplateRetrieval:
    """Test template retrieval by language and alert type."""

    def test_get_english_template(self):
        """Retrieve English template."""
        template = get_template("en", AlertType.PASSPORT_WARNING)

        assert "subject" in template
        assert "body" in template
        assert "Passport" in template["subject"]

    def test_get_italian_template(self):
        """Retrieve Italian template."""
        template = get_template("it", AlertType.PASSPORT_WARNING)

        assert "subject" in template
        assert "Passaporto" in template["subject"] or "passaporto" in template["body"]

    def test_get_indonesian_template(self):
        """Retrieve Indonesian template."""
        template = get_template("id", AlertType.PASSPORT_WARNING)

        assert "subject" in template
        assert "Paspor" in template["subject"] or "paspor" in template["body"]

    def test_fallback_to_english(self):
        """Fallback to English if language not found."""
        template = get_template("xx", AlertType.PASSPORT_WARNING)  # Invalid language

        assert "subject" in template
        assert "Passport" in template["subject"]  # Should be English

    def test_fallback_to_english_alert_type(self):
        """Fallback to English if alert type not found in language."""
        template = get_template("it", AlertType.PASSPORT_EXPIRED)

        assert "subject" in template
        assert len(template["body"]) > 0


class TestTemplateFormatting:
    """Test template variable substitution."""

    def test_format_passport_warning(self):
        """Format passport warning template."""
        template = get_template("en", AlertType.PASSPORT_WARNING)

        result = format_template(
            template["body"],
            full_name="John Doe",
            months_remaining="13",
            expiry_date="15 January 2025",
        )

        assert "John Doe" in result
        assert "13 months" in result
        assert "15 January 2025" in result

    def test_format_birthday(self):
        """Format birthday template with Indonesian blessing."""
        template = get_template("en", AlertType.BIRTHDAY)
        blessing = INDONESIAN_BLESSINGS[0]

        result = format_template(
            template["body"],
            full_name="Jane Doe",
            indonesian_blessing=blessing,
        )

        assert "Jane Doe" in result
        assert blessing in result
        assert "Selamat ulang tahun" in result

    def test_format_visa_critical(self):
        """Format visa critical template."""
        template = get_template("en", AlertType.VISA_CRITICAL)

        result = format_template(
            template["body"],
            full_name="John Doe",
            days_remaining="45",
            expiry_date="15 March 2025",
            visa_type="KITAS",
        )

        assert "John Doe" in result
        assert "45 days" in result
        assert "KITAS" in result
        assert "URGENT" in result

    def test_format_visa_warning(self):
        """Format visa warning template."""
        template = get_template("en", AlertType.VISA_WARNING)

        result = format_template(
            template["body"],
            full_name="John Doe",
            days_remaining="100",
            expiry_date="15 June 2025",
            visa_type="KITAS",
        )

        assert "John Doe" in result
        assert "100 days" in result
        assert "KITAS" in result

    def test_format_visa_expired(self):
        """Format visa expired template."""
        template = get_template("en", AlertType.VISA_EXPIRED)

        result = format_template(
            template["body"],
            full_name="John Doe",
            days_remaining="0",
            expiry_date="15 January 2025",
            visa_type="KITAS",
        )

        assert "John Doe" in result
        assert "KITAS" in result
        assert "CRITICAL" in result or "expired" in result.lower()

    def test_format_missing_variable_graceful(self):
        """Missing template variable should not crash."""
        template = get_template("en", AlertType.PASSPORT_WARNING)

        # Missing months_remaining and expiry_date
        result = format_template(
            template["body"],
            full_name="John Doe",
        )

        assert "John Doe" in result
        # Should not raise KeyError


_LANGUAGES = ["en", "it", "id"]
_ALERT_TYPES = [
    AlertType.PASSPORT_WARNING,
    AlertType.PASSPORT_CRITICAL,
    AlertType.PASSPORT_EXPIRED,
    AlertType.VISA_WARNING,
    AlertType.VISA_CRITICAL,
    AlertType.VISA_EXPIRED,
    AlertType.BIRTHDAY,
]


class TestAllAlertTypesCovered:
    """Ensure all alert types have templates for major languages."""

    @pytest.mark.parametrize(
        "lang,alert_type", [(lang, alert) for lang in _LANGUAGES for alert in _ALERT_TYPES],
    )
    def test_template_exists(self, lang: str, alert_type: AlertType):
        """Every language and alert type combination should have a template."""
        template = get_template(lang, alert_type)

        assert template is not None
        assert "subject" in template
        assert "body" in template
        assert len(template["subject"]) > 0
        assert len(template["body"]) > 0


class TestItalianTemplatesNoBlessing:
    """Verify Italian non-birthday templates don't contain {indonesian_blessing}."""

    NON_BIRTHDAY_TYPES = [
        AlertType.PASSPORT_WARNING,
        AlertType.PASSPORT_CRITICAL,
        AlertType.VISA_CRITICAL,
        AlertType.VISA_WARNING,
        AlertType.VISA_EXPIRED,
    ]

    @pytest.mark.parametrize("alert_type", NON_BIRTHDAY_TYPES)
    def test_no_indonesian_blessing_in_non_birthday(self, alert_type: AlertType):
        """Non-birthday Italian templates must not reference {indonesian_blessing}."""
        template = get_template("it", alert_type)

        assert "{indonesian_blessing}" not in template["body"]
        assert "{indonesian_blessing}" not in template["subject"]


class TestIndonesianBlessings:
    """Test Indonesian blessing phrases."""

    def test_blessings_not_empty(self):
        """Blessings list should not be empty."""
        assert len(INDONESIAN_BLESSINGS) > 0

    def test_blessings_are_indonesian(self):
        """Blessings should contain Indonesian text."""
        indonesian_words = [
            "selamat",
            "semoga",
            "tahun",
            "panjang",
            "umur",
            "dirgahayu",
            "semangat",
            "ultah",
            "menyerah",
            "harapan",
        ]
        for blessing in INDONESIAN_BLESSINGS:
            assert len(blessing) > 0
            # Should contain common Indonesian words
            assert any(word in blessing.lower() for word in indonesian_words), (
                f"Blessing does not contain Indonesian words: {blessing}"
            )


class TestTemplateContent:
    """Test template content quality."""

    def test_critical_alerts_have_urgent_keywords(self):
        """Critical alerts should contain urgent language."""
        template = get_template("en", AlertType.PASSPORT_CRITICAL)

        assert any(word in template["subject"].upper() for word in ["URGENT", "CRITICAL"])

    def test_expired_alerts_have_critical_keywords(self):
        """Expired alerts should contain critical language."""
        template = get_template("en", AlertType.PASSPORT_EXPIRED)

        assert "EXPIRED" in template["subject"].upper() or "CRITICAL" in template["subject"].upper()

    def test_visa_expired_has_critical_keywords(self):
        """Visa expired template should contain critical language."""
        template = get_template("en", AlertType.VISA_EXPIRED)

        assert "EXPIRED" in template["subject"].upper() or "CRITICAL" in template["subject"].upper()

    def test_birthday_has_celebratory_tone(self):
        """Birthday template should be celebratory."""
        template = get_template("en", AlertType.BIRTHDAY)

        assert "Happy Birthday" in template["subject"]

    def test_warning_alerts_have_reminder_tone(self):
        """Warning alerts should be informative, not urgent."""
        template = get_template("en", AlertType.VISA_WARNING)

        assert "Reminder" in template["subject"] or "Plan" in template["subject"]
