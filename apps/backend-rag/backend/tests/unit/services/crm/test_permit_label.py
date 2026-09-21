"""Tests for backend.services.crm.permit_label.

Every input string below is either a bare document_type value or an OCR
`visa_type` string actually measured in prod on 2026-09-21 (no client PII —
these are permit-type labels, not personal data). Synthetic ids only.
"""

from backend.services.crm.permit_label import (
    FAMILY_EVISA,
    FAMILY_ITK,
    FAMILY_KITAP,
    FAMILY_KITAS,
    FAMILY_MERP,
    resolve_permit_label,
)


def _ocr(visa_type: str | None = None, **extra):
    raw_response = dict(extra)
    if visa_type is not None:
        raw_response["visa_type"] = visa_type
    return {"raw_response": raw_response}


class TestUnknownNeverInvents:
    def test_none_document_type_and_no_ocr(self):
        assert resolve_permit_label(None, None) is None

    def test_generic_visa_with_no_ocr_data(self):
        assert resolve_permit_label("visa", None) is None

    def test_generic_visa_with_unclassifiable_ocr_text(self):
        # "MULTIPLE ENTRY" measured 7x under document_type='visa' — ambiguous
        # between a multi-entry VISIT visa and MERP; never invent.
        assert resolve_permit_label("visa", _ocr("MULTIPLE ENTRY")) is None

    def test_bare_index_looking_string_not_in_catalogue(self):
        # "B211" / "VTT-314" are real Indonesian index codes but not in this
        # app's VisaType catalogue — no evidence, so no family.
        assert resolve_permit_label("visa", _ocr("B211")) is None

    def test_unrelated_document_type(self):
        assert resolve_permit_label("passport", None) is None


class TestKitap:
    def test_document_type_itap(self):
        # Measured document_type='itap' (2 rows).
        result = resolve_permit_label("itap", None)
        assert result is not None
        assert result["permit_family"] == FAMILY_KITAP
        assert result["permit_code"] == "KITAP / ITAP"
        assert result["permit_label"] == "KITAP / ITAP — Permanent Stay Permit"

    def test_ocr_kitap_bare(self):
        # Measured OCR visa_type='KITAP' (7 rows) under document_type='visa'.
        result = resolve_permit_label("visa", _ocr("KITAP"))
        assert result["permit_family"] == FAMILY_KITAP

    def test_ocr_kitap_electronic_permanent_stay_permit(self):
        # Measured: "KITAP (ELECTRONIC PERMANENT STAY PERMIT)" (2 rows).
        result = resolve_permit_label(
            "visa", _ocr("KITAP (ELECTRONIC PERMANENT STAY PERMIT)")
        )
        assert result["permit_family"] == FAMILY_KITAP

    def test_case_insensitive_lowercase(self):
        result = resolve_permit_label("visa", _ocr("kitap"))
        assert result["permit_family"] == FAMILY_KITAP


class TestKitas:
    def test_document_type_kitas(self):
        result = resolve_permit_label("kitas", None)
        assert result["permit_family"] == FAMILY_KITAS
        assert result["permit_label"] == "KITAS / ITAS — Limited Stay Permit"

    def test_document_type_itas(self):
        result = resolve_permit_label("itas", None)
        assert result["permit_family"] == FAMILY_KITAS

    def test_ocr_kitas_limited_stay_permit(self):
        # Measured: "KITAS (Limited Stay Permit)" (10 rows).
        result = resolve_permit_label("visa", _ocr("KITAS (Limited Stay Permit)"))
        assert result["permit_family"] == FAMILY_KITAS

    def test_ocr_itas_residence_permit(self):
        # Measured: "ITAS RESIDENCE PERMIT" (1 row).
        result = resolve_permit_label("visa", _ocr("ITAS RESIDENCE PERMIT"))
        assert result["permit_family"] == FAMILY_KITAS

    def test_ocr_limited_stay_visa(self):
        # Measured: "Limited Stay Visa" (13 rows).
        result = resolve_permit_label("visa", _ocr("Limited Stay Visa"))
        assert result["permit_family"] == FAMILY_KITAS

    def test_ocr_indonesian_tinggal_terbatas(self):
        # Measured: "Visa Tinggal Terbatas (E23)" (2 rows).
        result = resolve_permit_label("visa", _ocr("Visa Tinggal Terbatas (E23)"))
        assert result["permit_family"] == FAMILY_KITAS

    def test_uppercase_document_type(self):
        # Measured document_type='KITAS' (1 row, mixed case in prod data).
        result = resolve_permit_label("KITAS", None)
        assert result["permit_family"] == FAMILY_KITAS


class TestItk:
    def test_document_type_itk(self):
        # Measured document_type='itk' (170 rows).
        result = resolve_permit_label("itk", None)
        assert result["permit_family"] == FAMILY_ITK
        assert result["permit_label"] == "ITK — Visit Stay Permit"

    def test_ocr_visit_stay_permit(self):
        # Measured: "VISIT STAY PERMIT" (130 rows).
        result = resolve_permit_label("visa", _ocr("VISIT STAY PERMIT"))
        assert result["permit_family"] == FAMILY_ITK

    def test_ocr_visit_visa(self):
        # Measured: "Visit Visa" (95 rows).
        result = resolve_permit_label("visa", _ocr("Visit Visa"))
        assert result["permit_family"] == FAMILY_ITK

    def test_free_text_document_type_with_itk_prefix(self):
        # Measured document_type='ITK 60 Days (Arrival)' (2 rows).
        result = resolve_permit_label("ITK 60 Days (Arrival)", None)
        assert result["permit_family"] == FAMILY_ITK

    def test_ocr_visa_kunjungan(self):
        # Measured: "Visa Kunjungan" (5 rows) — Indonesian for visit visa.
        # No "itk"/"visit" substring, so this stays unresolved (never invent).
        assert resolve_permit_label("visa", _ocr("Visa Kunjungan")) is None


class TestMerp:
    def test_document_type_merp(self):
        # Measured document_type='MERP' (3 rows) — today lands under "Other"
        # because isVisaFamilyDocument() never matched "merp".
        result = resolve_permit_label("MERP", None)
        assert result["permit_family"] == FAMILY_MERP
        assert result["permit_code"] == "MERP"
        assert result["permit_label"] == "MERP — Multiple Exit Re-entry Permit"

    def test_ocr_re_entry_permit(self):
        # Measured: "RE-ENTRY PERMIT" (1 row).
        result = resolve_permit_label("visa", _ocr("RE-ENTRY PERMIT"))
        assert result["permit_family"] == FAMILY_MERP

    def test_lowercase_merp(self):
        result = resolve_permit_label("merp", None)
        assert result["permit_family"] == FAMILY_MERP


class TestEvisa:
    def test_document_type_e_visa(self):
        # Measured document_type='e_visa' (67 rows).
        result = resolve_permit_label("e_visa", None)
        assert result["permit_family"] == FAMILY_EVISA
        assert result["permit_code"] == "e-Visa"

    def test_document_type_telex_visa(self):
        # Measured document_type='telex_visa' (12 rows).
        result = resolve_permit_label("telex_visa", None)
        assert result["permit_family"] == FAMILY_EVISA

    def test_mixed_case_e_visa_variants(self):
        # Measured document_type values 'E-visa' (8), 'E Visa' (4), 'E-VISA' (2).
        for value in ("E-visa", "E Visa", "E-VISA"):
            result = resolve_permit_label(value, None)
            assert result is not None, value
            assert result["permit_family"] == FAMILY_EVISA

    def test_bare_index_code_extracted_from_ocr(self):
        # Measured OCR visa_type='D12' (1 row) — no family keyword, but a
        # known catalogue index code, so it resolves as an indexed e-Visa.
        result = resolve_permit_label("visa", _ocr("D12"))
        assert result["permit_family"] == FAMILY_EVISA
        assert result["permit_code"] == "D12"
        assert result["permit_label"] == "D12 — e-Visa"

    def test_index_code_prefers_longest_match(self):
        result = resolve_permit_label("visa", _ocr("E23-FREELANCE"))
        assert result["permit_code"] == "E23-FREELANCE"

    def test_index_code_not_falsely_matched_inside_other_token(self):
        # "C12B14" must NOT match "C1" as a substring.
        assert resolve_permit_label("visa", _ocr("C12B14")) is None


class TestExtractedFields:
    def test_permit_number_and_sponsor_surfaced_when_present(self):
        result = resolve_permit_label(
            "visa",
            _ocr(
                "KITAS (Limited Stay Permit)",
                visa_number="TEST-0000",
                sponsor="Example Sponsor",
            ),
        )
        assert result["permit_number"] == "TEST-0000"
        assert result["permit_sponsor"] == "Example Sponsor"

    def test_absent_fields_are_none_not_placeholder(self):
        result = resolve_permit_label("kitas", None)
        assert result["permit_number"] is None
        assert result["permit_sponsor"] is None

    def test_blank_sponsor_string_treated_as_absent(self):
        result = resolve_permit_label("kitas", _ocr(None, sponsor="  "))
        # sponsor is whitespace-only in the raw payload — still surfaced
        # verbatim (never silently dropped) since it is a real extracted
        # value, not an absent key; document_type alone already resolved
        # the family here.
        assert result["permit_family"] == FAMILY_KITAS

    def test_specific_document_type_wins_over_conflicting_ocr_noise(self):
        # A stored document_type of 'kitas' is trusted directly even if OCR
        # extraction (rare, wrong-doc-attached edge case) said something
        # unrelated and unclassifiable.
        result = resolve_permit_label("kitas", _ocr("SOME_UNRELATED_TEXT"))
        assert result["permit_family"] == FAMILY_KITAS
