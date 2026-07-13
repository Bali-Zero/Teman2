"""Unit tests for the profil_perseroan (Company Profile) doc-type.

Locks the full intake chain for the new company doc-type:
  * classify_document() surfaces profil_perseroan above the unknown floor
    on genuine boilerplate phrases;
  * canonical_doc_type() no longer drops it to None (it is now a
    DOC_TYPE_FIELDS member) and resolves common alias spellings;
  * routing groups it as subject_kind="company";
  * the CRM writer files it into the "pma" category (-> 02_Company folder).
"""

from __future__ import annotations

import pytest

from backend.services.intake import classify as cls
from backend.services.intake import extract, routing, writer

# --------------------------------------------------------------------------- #
# classify — evidence surfaces the type                                       #
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_profil_perseroan_classified_from_text():
    text = (
        "PROFIL PERSEROAN\n"
        "PT NUSANTARA JAYA ABADI\n"
        "Bidang Usaha: konsultan manajemen\n"
        "Struktur Permodalan: Rp 10.000.000.000\n"
        "Susunan Pengurus: Direktur, Komisaris\n"
    )
    r = await cls.classify_document(text)
    assert r["type"] == "profil_perseroan"
    assert r["confidence"] >= 0.30  # clears the anti-hallucination floor


@pytest.mark.asyncio
async def test_company_profile_english_title_classified():
    text = "COMPANY PROFILE\nPT NUSANTARA JAYA ABADI\nStruktur Permodalan ...\n"
    r = await cls.classify_document(text)
    assert r["type"] == "profil_perseroan"


def test_profil_perseroan_is_a_doc_type():
    assert "profil_perseroan" in cls.DOC_TYPES


# --------------------------------------------------------------------------- #
# canonicalization — no longer dropped to None; aliases resolve               #
# --------------------------------------------------------------------------- #

def test_canonical_doc_type_keeps_profil_perseroan():
    # regression: before adding the DOC_TYPE_FIELDS schema this returned None,
    # which made stages.py drop the doc-type entirely.
    assert extract.canonical_doc_type("profil_perseroan") == "profil_perseroan"


@pytest.mark.parametrize(
    "variant",
    ["company_profile", "profil_pt", "profile_perseroan", "PROFIL_PERSEROAN"],
)
def test_canonical_doc_type_resolves_aliases(variant):
    assert extract.canonical_doc_type(variant) == "profil_perseroan"


def test_profil_perseroan_has_extraction_schema():
    assert "profil_perseroan" in extract.DOC_TYPE_FIELDS
    field_names = {spec[0] for spec in extract.DOC_TYPE_FIELDS["profil_perseroan"]}
    assert "company_name" in field_names


# --------------------------------------------------------------------------- #
# routing — grouped as a company doc                                          #
# --------------------------------------------------------------------------- #

def test_profil_perseroan_is_company_doc_type():
    assert "profil_perseroan" in routing._COMPANY_DOC_TYPES
    assert "profil_perseroan" not in routing._PERSON_DOC_TYPES


# --------------------------------------------------------------------------- #
# writer — filed into the pma (company) CRM folder                            #
# --------------------------------------------------------------------------- #

def test_profil_perseroan_maps_to_pma_category():
    payload = writer._document_payload(
        routing={"doc_type": "profil_perseroan", "fields": {}},
        stage_output={"file_name": "Profil Perseroan.pdf"},
        source_ref="test-ref",
    )
    assert payload["document_category"] == "pma"
    assert payload["document_type"] == "profil_perseroan"
