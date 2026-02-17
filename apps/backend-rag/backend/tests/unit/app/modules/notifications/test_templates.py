"""
Test email templates and localization.
"""

import pytest
from backend.app.modules.notifications.templates import (
    get_template,
    format_template,
    EMAIL_TEMPLATES,
    INDONESIAN_BLESSINGS,
)
from backend.app.modules.notifications.models import AlertType


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
        # Should have some content
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


class TestAllAlertTypesCovered:
    """Ensure all alert types have templates for major languages."""

    LANGUAGES = ["en", "it", "id"]
    ALERT_TYPES = [
        AlertType.PASSPORT_WARNING,
        AlertType.PASSPORT_CRITICAL,
        AlertType.PASSPORT_EXPIRED,
        AlertType.VISA_WARNING,
        AlertType.VISA_CRITICAL,
        AlertType.BIRTHDAY,
    ]

    @pytest.mark.parametrize("lang,alert_type", [
        (lang, alert) for lang in LANGUAGES for alert in ALERT_TYPES
    ])
    def test_template_exists(self, lang, alert_type):
        """Every language and alert type combination should have a template."""
        template = get_template(lang, alert_type)
        
        assert template is not None
        assert "subject" in template
        assert "body" in template
        assert len(template["subject"]) > 0
        assert len(template["body"]) > 0


class TestIndonesianBlessings:
    """Test Indonesian blessing phrases."""

    def test_blessings_not_empty(self):
        """Blessings list should not be empty."""
        assert len(INDONESIAN_BLESSINGS) > 0

    def test_blessings_are_indonesian(self):
        """Blessings should contain Indonesian text."""
        for blessing in INDONESIAN_BLESSINGS:
            assert len(blessing) > 0
            # Should contain common Indonesian words
            assert any(word in blessing.lower() for word in [
                "selamat", "semoga", "tahun", "panjang", "umur"
            ])


class TestTemplateContent:
    """Test template content quality."""

    def test_critical_alerts_have_urgent_keywords(self):
        """Critical alerts should contain urgent language."""
        template = get_template("en", AlertType.PASSPORT_CRITICAL)
        
        assert any(word in template["subject"].upper() for word in ["URGENT", "CRITICAL"])
        assert "🚨" in template["body"] or "URGENT" in template["body"]

    def test_expired_alerts_have_critical_keywords(self):
        """Expired alerts should contain critical language."""
        template = get_template("en", AlertType.PASSPORT_EXPIRED)
        
        assert "EXPIRED" in template["subject"].upper() or "CRITICAL" in template["subject"].upper()

    def test_birthday_has_celebratory_tone(self):
        """Birthday template should be celebratory."""
        template = get_template("en", AlertType.BIRTHDAY)
        
        assert "🎂" in template["subject"] or "🎉" in template["subject"]
        assert "Happy Birthday" in template["subject"]
