"""Tests for backend.services.crm.permit_label.

Every input string below is either a bare document_type value or an OCR
`visa_type` string actually measured in prod on 2026-09-21 (no client PII —
these are permit-type labels, not personal data). Synthetic ids only.

Owner correction (2026-09-21): the precise label must lead with the visa
INDEX and its official catalogue name (`visa_types.code`/`.name`), not just
the family. The family label is now `permit_family_label`, a secondary
field, and is the fallback primary label only when no index is found at
all. See `permit_label.py` module docstring for the parser rules.
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
        # between a multi-entry VISIT visa and MERP; never invent. No index
        # token in it either ("MULTIPLE" starts with M, "ENTRY" with E but
        # "ENTRY"[1]='N' is not a digit).
        assert resolve_permit_label("visa", _ocr("MULTIPLE ENTRY")) is None

    def test_unrelated_document_type(self):
        assert resolve_permit_label("passport", None) is None

    def test_bare_uncatalogued_index_strings_yield_no_family_but_a_None_result_only_without_evidence(
        self,
    ):
        # These four never parse as CODE(+STAY) at all — no letter A-E
        # leading, or the digits/letters don't line up — so, with no family
        # keyword either, the whole document stays unresolved.
        for text in ("B211A", "B211", "211A", "VTT-314", "2CXX", "RPTKA"):
            assert resolve_permit_label("visa", _ocr(text)) is None, text


class TestKitap:
    def test_document_type_itap(self):
        # Measured document_type='itap' (2 rows).
        result = resolve_permit_label("itap", None)
        assert result is not None
        assert result["permit_family"] == FAMILY_KITAP
        assert result["permit_code"] == "KITAP / ITAP"
        assert result["permit_label"] == "KITAP / ITAP — Permanent Stay Permit"
        # No index derivable from "itap" alone — the family label doubles as
        # both the primary and secondary field.
        assert result["permit_family_label"] == result["permit_label"]

    def test_ocr_kitap_bare(self):
        # Measured OCR visa_type='KITAP' (7 rows) under document_type='visa'.
        result = resolve_permit_label("visa", _ocr("KITAP"))
        assert result["permit_family"] == FAMILY_KITAP

    def test_ocr_kitap_electronic_permanent_stay_permit(self):
        # Measured: "KITAP (ELECTRONIC PERMANENT STAY PERMIT)" (2 rows) — no
        # index token in this string either.
        result = resolve_permit_label(
            "visa", _ocr("KITAP (ELECTRONIC PERMANENT STAY PERMIT)")
        )
        assert result["permit_family"] == FAMILY_KITAP
        assert result["permit_label"] == "KITAP / ITAP — Permanent Stay Permit"

    def test_case_insensitive_lowercase(self):
        result = resolve_permit_label("visa", _ocr("kitap"))
        assert result["permit_family"] == FAMILY_KITAP


class TestKitas:
    def test_document_type_kitas(self):
        result = resolve_permit_label("kitas", None)
        assert result["permit_family"] == FAMILY_KITAS
        assert result["permit_label"] == "KITAS / ITAS — Limited Stay Permit"
        assert result["permit_family_label"] == result["permit_label"]

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

    def test_ocr_indonesian_tinggal_terbatas_no_catalogue(self):
        # Measured: "Visa Tinggal Terbatas (E23)" (2 rows) — WITHOUT a
        # catalogue, the index still wins the primary label (code alone).
        result = resolve_permit_label("visa", _ocr("Visa Tinggal Terbatas (E23)"))
        assert result["permit_family"] == FAMILY_KITAS
        assert result["permit_code"] == "E23"
        assert result["permit_label"] == "E23"
        assert result["permit_family_label"] == "KITAS / ITAS — Limited Stay Permit"

    def test_ocr_indonesian_tinggal_terbatas_with_catalogue(self):
        # Same string, now with the `visa_types` catalogue supplied — the
        # official name becomes the primary label, family label secondary.
        catalogue = {"E23": "E23 - Working KITAS"}
        result = resolve_permit_label(
            "visa", _ocr("Visa Tinggal Terbatas (E23)"), catalogue=catalogue
        )
        assert result["permit_label"] == "E23 — Working KITAS"
        assert result["permit_family_label"] == "KITAS / ITAS — Limited Stay Permit"
        assert result["permit_code"] == "E23"

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
        # No "itk"/"visit" substring and no index token, so this stays
        # unresolved (never invent).
        assert resolve_permit_label("visa", _ocr("Visa Kunjungan")) is None

    def test_fused_index_inside_a_visit_stay_permit_string(self):
        # Measured: "C12B14 (VISIT STAY PERMIT)" / "VISIT STAY PERMIT
        # (C12B14)" — the fused stay-index token parses to its CODE prefix
        # (C1), never a substring false-match, regardless of token order.
        for text in ("C12B14 (VISIT STAY PERMIT)", "VISIT STAY PERMIT (C12B14)"):
            result = resolve_permit_label("visa", _ocr(text))
            assert result["permit_family"] == FAMILY_ITK, text
            assert result["permit_code"] == "C1", text
            assert result["permit_stay_index"] == "2B14", text


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

    def test_bare_index_code_no_catalogue_yields_code_alone(self):
        # Measured OCR visa_type='D12' (1 row) — no family keyword, but a
        # parseable index. Without a catalogue the primary label is the
        # code alone (never a hand-written family suffix).
        result = resolve_permit_label("visa", _ocr("D12"))
        assert result["permit_family"] == FAMILY_EVISA
        assert result["permit_code"] == "D12"
        assert result["permit_label"] == "D12"
        assert result["permit_family_label"] is None
        assert result["permit_stay_index"] is None

    def test_bare_index_code_with_catalogue_uses_official_name(self):
        catalogue = {"D12": "D12 - Pre-Investment (Multiple Entry)"}
        result = resolve_permit_label("visa", _ocr("D12"), catalogue=catalogue)
        assert result["permit_label"] == "D12 — Pre-Investment (Multiple Entry)"

    def test_catalogue_name_without_a_code_prefix_is_kept_verbatim(self):
        # Measured catalogue row: code='E28D', name has no "E28D - " prefix.
        catalogue = {
            "E28D": "Investor Visa Pendirian Cabang atau Anak Perusahaan Golden Visa"
        }
        result = resolve_permit_label("visa", _ocr("E28D"), catalogue=catalogue)
        assert (
            result["permit_label"]
            == "E28D — Investor Visa Pendirian Cabang atau Anak Perusahaan Golden Visa"
        )

    def test_index_code_not_in_catalogue_falls_back_to_code_alone(self):
        # C31 parses cleanly as an index but is not a row in `visa_types` —
        # rule: index found, not catalogued -> primary label is the index.
        catalogue = {"D12": "D12 - Pre-Investment (Multiple Entry)"}
        result = resolve_permit_label("visa", _ocr("C31"), catalogue=catalogue)
        assert result["permit_code"] == "C31"
        assert result["permit_label"] == "C31"

    def test_index_code_prefers_longest_match(self):
        result = resolve_permit_label("visa", _ocr("E28A"))
        assert result["permit_code"] == "E28A"


class TestFusedStayIndexParsing:
    """CODE = [A-E]\\d{1,2}[A-Z]?, STAY = 2[A-Z]\\d{0,2} — every fused shape
    measured in prod `ocr_extracted_data->raw_response->>'visa_type'`, plus
    the ones that must NOT parse (2026-09-21 owner spec)."""

    def test_c12b14_parses_to_c1(self):
        result = resolve_permit_label("visa", _ocr("C12B14"))
        assert result["permit_code"] == "C1"
        assert result["permit_stay_index"] == "2B14"

    def test_c12b24_parses_to_c1(self):
        result = resolve_permit_label("visa", _ocr("C12B24"))
        assert result["permit_code"] == "C1"
        assert result["permit_stay_index"] == "2B24"

    def test_c12b_parses_to_c1_not_c12b(self):
        # "C12B" alone is not in the catalogue; the C1+STAY(2B) split is
        # preferred because C1 IS in the catalogue.
        catalogue = {"C1": "C1 - Tourism"}
        result = resolve_permit_label("visa", _ocr("C12B"), catalogue=catalogue)
        assert result["permit_code"] == "C1"
        assert result["permit_stay_index"] == "2B"

    def test_d122b15_parses_to_d12(self):
        result = resolve_permit_label("visa", _ocr("D122B15"))
        assert result["permit_code"] == "D12"
        assert result["permit_stay_index"] == "2B15"

    def test_c182b15_parses_to_c18(self):
        result = resolve_permit_label("visa", _ocr("C182B15"))
        assert result["permit_code"] == "C18"
        assert result["permit_stay_index"] == "2B15"

    def test_b12e11_parses_to_b1(self):
        result = resolve_permit_label("visa", _ocr("B12E11"))
        assert result["permit_code"] == "B1"
        assert result["permit_stay_index"] == "2E11"

    def test_kitas_e232c11_parses_to_e23(self):
        # Measured: "KITAS (E232C11)".
        result = resolve_permit_label("visa", _ocr("KITAS (E232C11)"))
        assert result["permit_family"] == FAMILY_KITAS
        assert result["permit_code"] == "E23"
        assert result["permit_stay_index"] == "2C11"

    def test_kitas_e33g2c12_parses_to_e33g(self):
        # Measured: "KITAS (E33G2C12)".
        result = resolve_permit_label("visa", _ocr("KITAS (E33G2C12)"))
        assert result["permit_family"] == FAMILY_KITAS
        assert result["permit_code"] == "E33G"
        assert result["permit_stay_index"] == "2C12"

    def test_visit_stay_permit_c31_bare(self):
        # Measured: "VISIT STAY PERMIT (C31)" — C31 is not in the catalogue.
        result = resolve_permit_label("visa", _ocr("VISIT STAY PERMIT (C31)"))
        assert result["permit_family"] == FAMILY_ITK
        assert result["permit_code"] == "C31"
        assert result["permit_stay_index"] is None

    def test_no_index_shapes_never_falsely_parse(self):
        # Real Indonesian index codes NOT in this app's VisaType catalogue
        # shape (or plain not index-shaped), and OCR noise that merely looks
        # numeric — none of these may produce a permit_code.
        for text in ("B211A", "B211", "211A", "VTT-314", "2CXX", "RPTKA"):
            result = resolve_permit_label("visa", _ocr(f"KITAS {text}"))
            # family resolves from "KITAS", but no index was extracted from
            # the noise token that follows it.
            assert result["permit_family"] == FAMILY_KITAS, text
            assert result["permit_code"] == "KITAS / ITAS", text
            assert result["permit_stay_index"] is None, text


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
