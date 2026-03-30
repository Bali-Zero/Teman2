"""
Tests for PII Scanner — UU PDP Compliance

Tests Indonesian PII detection: KTP (16 digits), NPWP (old + new 16-digit),
Passport, Phone (+62), Email, Person names.
"""

import pytest
from backend.middleware.pii_scanner import scan_text, redact_text


class TestScanText:
    """Test PII detection across Indonesian formats."""

    def test_detect_ktp_16_digits(self):
        entities = scan_text("NIK: 3504011203950001")
        types = [e["entity_type"] for e in entities]
        assert "ID_KTP" in types

    def test_detect_npwp_old_format(self):
        entities = scan_text("NPWP: 02.123.456.7-890.000")
        types = [e["entity_type"] for e in entities]
        assert "ID_NPWP" in types

    def test_detect_npwp_new_16_digit_foreigner(self):
        entities = scan_text("NPWP baru: 0123456789012345")
        types = [e["entity_type"] for e in entities]
        assert any(t in ("ID_NPWP", "ID_KTP") for t in types)

    def test_detect_indonesian_passport(self):
        entities = scan_text("Passport number: AB1234567")
        types = [e["entity_type"] for e in entities]
        assert "ID_PASSPORT" in types

    def test_detect_phone_plus62(self):
        entities = scan_text("Call me at +6281234567890")
        types = [e["entity_type"] for e in entities]
        assert any(t in ("PHONE_ID", "PHONE_NUMBER") for t in types)

    def test_detect_phone_08(self):
        entities = scan_text("HP: 081234567890")
        types = [e["entity_type"] for e in entities]
        assert any(t in ("PHONE_ID", "PHONE_NUMBER") for t in types)

    def test_detect_email(self):
        entities = scan_text("Email: john@example.com")
        types = [e["entity_type"] for e in entities]
        assert "EMAIL_ADDRESS" in types

    def test_detect_person_name(self):
        entities = scan_text("The applicant John Doe submitted documents")
        types = [e["entity_type"] for e in entities]
        assert "PERSON" in types

    def test_no_pii_in_clean_text(self):
        entities = scan_text("The weather is nice today in the office")
        # spaCy may detect PERSON in some texts, so we check for Indonesian PII specifically
        indonesian_pii = [e for e in entities if e["entity_type"] in ("ID_KTP", "ID_NPWP", "ID_PASSPORT", "PHONE_ID")]
        assert len(indonesian_pii) == 0

    def test_multiple_pii_in_one_text(self):
        text = "KTP 3504011203950001, NPWP 02.123.456.7-890.000, phone +6281234567890"
        entities = scan_text(text)
        assert len(entities) >= 3

    def test_entity_has_required_fields(self):
        entities = scan_text("KTP: 3504011203950001")
        assert len(entities) > 0
        entity = entities[0]
        assert "entity_type" in entity
        assert "start" in entity
        assert "end" in entity
        assert "score" in entity
        assert "text" in entity


class TestRedactText:
    """Test PII redaction."""

    def test_redact_ktp(self):
        redacted, count = redact_text("NIK: 3504011203950001")
        assert count > 0
        assert "3504011203950001" not in redacted

    def test_redact_npwp_old(self):
        redacted, count = redact_text("NPWP: 02.123.456.7-890.000")
        assert count > 0
        assert "02.123.456.7-890.000" not in redacted

    def test_redact_passport(self):
        redacted, count = redact_text("Passport: AB1234567")
        assert count > 0
        assert "AB1234567" not in redacted

    def test_redact_phone(self):
        redacted, count = redact_text("Phone: +6281234567890")
        assert count > 0
        assert "+6281234567890" not in redacted

    def test_redact_preserves_clean_text(self):
        text = "The system is working fine today"
        redacted, count = redact_text(text)
        # spaCy may detect PERSON, but no Indonesian PII should be found
        assert "ID_KTP" not in redacted
        assert "ID_NPWP" not in redacted

    def test_redact_returns_tuple(self):
        result = redact_text("test 3504011203950001")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], int)
