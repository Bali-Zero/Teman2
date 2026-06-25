"""Tests for the intake extraction stage (FASE 3 β).

Two layers:
  * Fast/CI: inject a fake ``generate_fn`` so no Ollama call is made — tests the
    Maybe-pattern coercion, the GOLDEN RULE (illegible field -> null + 0.0), the
    schema-per-doc-type, and the worker stage-handler contract deterministically.
  * ``slow``: hit the REAL SEA-LION model on local Ollama and assert the golden
    rule holds on real output. Deselect with ``-m "not slow"``.
"""

from __future__ import annotations

import json

import pytest

from backend.llm.ollama_client import is_ollama_available
from backend.services.intake import extract, model_roles

# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _fake_gen(payload: dict):
    """Return a generate_fn that always yields ``payload`` as JSON."""
    async def _gen(model: str, prompt: str) -> str:  # noqa: ARG001
        return json.dumps(payload)
    return _gen


# --------------------------------------------------------------------------- #
# Schema / doc-type mapping                                                    #
# --------------------------------------------------------------------------- #


def test_resolve_extraction_model_reads_model_topology(tmp_path, monkeypatch):
    topology = {"roles": {"intake_extraction": "registry-sealion:q4"}}
    (tmp_path / "MODEL_TOPOLOGY.json").write_text(json.dumps(topology), encoding="utf-8")
    monkeypatch.delenv("INTAKE_EXTRACTION_MODEL", raising=False)
    monkeypatch.setenv("INTAKE_REPO_ROOT", str(tmp_path))
    model_roles.clear_model_role_cache()
    try:
        assert extract._resolve_extraction_model() == "registry-sealion:q4"
    finally:
        model_roles.clear_model_role_cache()


def test_extraction_model_env_override_wins(monkeypatch):
    monkeypatch.setenv("INTAKE_EXTRACTION_MODEL", "override-model:q4")
    assert extract._resolve_extraction_model() == "override-model:q4"


def test_canonical_doc_type_aliases():
    assert extract.canonical_doc_type("nib") == "nib"
    assert extract.canonical_doc_type("NIB_OSS") == "nib"
    assert extract.canonical_doc_type("oss") == "nib"
    assert extract.canonical_doc_type("skt") == "skt"
    assert extract.canonical_doc_type("akta") == "akta_pendirian"
    assert extract.canonical_doc_type("sk_menkumham") == "sk_kemenkumham"
    assert extract.canonical_doc_type("paspor") == "passport"
    assert extract.canonical_doc_type("e-visa") == "visa"
    assert extract.canonical_doc_type("voa") == "visa"
    assert extract.canonical_doc_type("kitap") == "itap"
    assert extract.canonical_doc_type("itk_card") == "itk"
    assert extract.canonical_doc_type("e_ktp") == "ktp"
    assert extract.canonical_doc_type("kk") == "family_card"
    assert extract.canonical_doc_type("akta_kelahiran") == "birth_certificate"
    assert extract.canonical_doc_type("buku_nikah") == "marriage_certificate"
    assert extract.canonical_doc_type("proof_of_payment") == "payment_receipt"
    assert extract.canonical_doc_type("boarding_pass") == "travel_ticket"
    assert extract.canonical_doc_type("rekening_koran") == "bank_statement"
    assert extract.canonical_doc_type("travel_insurance") == "medical_insurance"
    assert extract.canonical_doc_type("unknown_thing") is None
    assert extract.canonical_doc_type(None) is None


async def test_unsupported_doc_type_raises():
    with pytest.raises(ValueError):
        await extract.extract_fields("drivers_license", ["some text"])


# --------------------------------------------------------------------------- #
# Maybe pattern + GOLDEN RULE (fake model, deterministic)                      #
# --------------------------------------------------------------------------- #

async def test_full_nib_extraction_with_evidence():
    payload = {
        "nib_number": {"value": "1234567890123", "source_page": 1},
        "company_name": {"value": "PT BALI ZERO SUKSES", "source_page": 1},
        "kbli_codes": {"value": ["56101", "68111"], "source_page": 2},
        "address": {"value": "Jl. Sunset Road 88, Kuta", "source_page": 1},
        "issue_date": {"value": "2024-03-12", "source_page": 1},
    }
    out = await extract.extract_fields(
        "nib", ["page one text", "page two kbli"], generate_fn=_fake_gen(payload)
    )
    assert out["doc_type"] == "nib"
    assert out["extraction_model"] == "sea-lion"
    assert out["fields"]["nib_number"]["value"] == "1234567890123"
    assert out["fields"]["nib_number"]["source_page"] == 1
    assert out["fields"]["nib_number"]["confidence"] >= 0.6
    assert out["fields"]["kbli_codes"]["value"] == ["56101", "68111"]
    assert out["any_low_confidence"] is False


async def test_golden_rule_illegible_field_becomes_null():
    """THE CRITICAL TEST: a field the model returns as null stays null + 0.0.

    The model is told to null illegible fields; here address + issue_date are
    null. The extractor must NOT invent — it preserves null with confidence 0.0.
    """
    payload = {
        "nib_number": {"value": "9876543210987", "source_page": 1},
        "company_name": {"value": "PT NUZANTARA JAYA", "source_page": 1},
        "kbli_codes": {"value": ["70209"], "source_page": 1},
        "address": {"value": None, "source_page": None},  # illegible smudge
        "issue_date": {"value": None, "source_page": None},  # absent
    }
    out = await extract.extract_fields(
        "nib", ["legible header, smudged address"], generate_fn=_fake_gen(payload)
    )
    addr = out["fields"]["address"]
    date = out["fields"]["issue_date"]
    assert addr["value"] is None and addr["confidence"] == 0.0 and addr["source_page"] is None
    assert date["value"] is None and date["confidence"] == 0.0
    assert out["any_low_confidence"] is True
    # legible fields untouched
    assert out["fields"]["nib_number"]["value"] == "9876543210987"


async def test_list_field_accepts_model_value_objects():
    """List fields may arrive as [{value, source_page}] objects from local models."""
    payload = {
        "certificate_no": {"value": "AL-2026-0001", "source_page": 1},
        "name": {"value": "TEST CHILD", "source_page": 1},
        "dob": {"value": "2020-05-06", "source_page": 1},
        "place_of_birth": {"value": "DENPASAR", "source_page": 1},
        "parents": {
            "value": [
                {"value": "TEST FATHER", "source_page": 1},
                {"value": "TEST MOTHER", "source_page": 1},
            ],
            "source_page": 1,
        },
    }

    out = await extract.extract_fields(
        "birth_certificate",
        ["birth certificate OCR fragment without deterministic labels"],
        generate_fn=_fake_gen(payload),
    )

    assert out["fields"]["parents"]["value"] == ["TEST FATHER", "TEST MOTHER"]
    assert out["fields"]["parents"]["source_page"] == 1
    assert out["fields"]["parents"]["confidence"] >= 0.6
    assert out["any_low_confidence"] is False


async def test_empty_string_sentinels_coerced_to_null():
    payload = {
        "nib_number": {"value": "", "source_page": 1},
        "company_name": {"value": "N/A", "source_page": 1},
        "kbli_codes": {"value": [], "source_page": None},
        "address": {"value": "-", "source_page": None},
        "issue_date": {"value": "null", "source_page": None},
    }
    out = await extract.extract_fields("nib", ["junk"], generate_fn=_fake_gen(payload))
    for name in ("nib_number", "company_name", "kbli_codes", "address", "issue_date"):
        assert out["fields"][name]["value"] is None, name
        assert out["fields"][name]["confidence"] == 0.0


async def test_bare_value_without_evidence_object_is_low_confidence():
    """Model returns bare scalars (no {value,source_page}). Value kept, citation
    distrusted -> halved confidence, never fabricated page."""
    payload = {
        "nib_number": "1234567890123",
        "company_name": "PT X",
        "kbli_codes": ["56101"],
        "address": "Jl. Y",
        "issue_date": "2024-01-01",
    }
    out = await extract.extract_fields("nib", ["p1"], generate_fn=_fake_gen(payload))
    f = out["fields"]["nib_number"]
    assert f["value"] == "1234567890123"
    assert f["source_page"] is None
    assert 0 < f["confidence"] < extract._PRESENT_CONFIDENCE  # halved


async def test_out_of_range_source_page_dropped():
    payload = {"nib_number": {"value": "1234567890123", "source_page": 99}}
    out = await extract.extract_fields("nib", ["only one page"], generate_fn=_fake_gen(payload))
    f = out["fields"]["nib_number"]
    assert f["value"] == "1234567890123"
    assert f["source_page"] is None  # 99 > 1 page -> dropped, not trusted


async def test_empty_ocr_yields_all_null_without_model_call():
    """No legible OCR -> every field null, model NOT called (golden rule)."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    out = await extract.extract_fields("akta_pendirian", ["", "   "], generate_fn=_gen)
    assert called["n"] == 0
    assert out["any_low_confidence"] is True
    for name in ("company_name", "directors", "commissioners", "capital", "notary", "date"):
        assert out["fields"][name]["value"] is None


async def test_passport_mrz_complete_skips_model_call():
    """A valid TD3 MRZ is enough to extract passport fields deterministically."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "PASSPORT\n"
        "P<ITAERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\n"
        "L898902C36ITA7408122F3004157ZE184226B<<<<<10"
    )
    out = await extract.extract_fields("passport", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["extraction_model"] == "passport_mrz"
    assert out["deterministic_extractors"] == ["passport_mrz"]
    assert out["any_low_confidence"] is False
    assert out["fields"]["passport_no"]["value"] == "L898902C3"
    assert out["fields"]["name"]["value"] == "Eriksson Anna Maria"
    assert out["fields"]["nationality"]["value"] == "Italian"
    assert out["fields"]["dob"]["value"] == "1974-08-12"
    assert out["fields"]["expiry"]["value"] == "2030-04-15"
    assert out["fields"]["name"]["confidence"] >= 0.9


async def test_passport_partial_mrz_merges_with_model_output():
    """Partial trusted MRZ fields supplement SEA-LION output instead of guessing."""
    payload = {
        "passport_no": {"value": "MODEL123", "source_page": 1},
        "name": {"value": None, "source_page": None},
        "nationality": {"value": None, "source_page": None},
        "dob": {"value": None, "source_page": None},
        "expiry": {"value": None, "source_page": None},
    }
    # Passport-number check digit is deliberately wrong (5 instead of 6), while
    # DOB + expiry check digits are valid. The MRZ pair is trusted enough to
    # provide name/dates/nationality, but not passport_no.
    ocr = (
        "P<ITAERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\n"
        "L898902C35ITA7408122F3004157ZE184226B<<<<<10"
    )
    out = await extract.extract_fields("passport", [ocr], generate_fn=_fake_gen(payload))

    assert out["extraction_model"] == "sea-lion"
    assert out["deterministic_extractors"] == ["passport_mrz"]
    assert out["fields"]["passport_no"]["value"] == "MODEL123"
    assert out["fields"]["name"]["value"] == "Eriksson Anna Maria"
    assert out["fields"]["nationality"]["value"] == "Italian"
    assert out["fields"]["dob"]["value"] == "1974-08-12"
    assert out["fields"]["expiry"]["value"] == "2030-04-15"


async def test_nib_label_fields_skip_model_call():
    """Clearly-labelled OSS/NIB OCR carries routing-critical company fields locally."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "LEMBAGA OSS REPUBLIK INDONESIA\n"
        "NOMOR INDUK BERUSAHA (NIB)\n"
        "NIB : 1234567890123\n"
        "Nama Pelaku Usaha : PT BALI ZERO SUKSES\n"
        "KBLI : 70209 Aktivitas Konsultasi Manajemen Lainnya\n"
        "Alamat : Jl Sunset Road 88, Kuta\n"
        "Tanggal Terbit : 20 Juni 2026"
    )
    out = await extract.extract_fields("oss", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "nib"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["nib_labels"]
    assert out["fields"]["nib_number"]["value"] == "1234567890123"
    assert out["fields"]["company_name"]["value"] == "PT BALI ZERO SUKSES"
    assert out["fields"]["kbli_codes"]["value"] == ["70209"]
    assert out["fields"]["address"]["value"] == "Jl Sunset Road 88, Kuta"
    assert out["fields"]["issue_date"]["value"] == "2026-06-20"


async def test_nib_label_fields_accept_colonless_ocr_labels():
    """NIB OCR often drops separators but still carries deterministic company fields."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "NOMOR INDUK BERUSAHA\n"
        "NIB 8123456789012\n"
        "Nama Perusahaan PT CONTOH MAJU BERSAMA\n"
        "KBLI 62019 AKTIVITAS PEMROGRAMAN KOMPUTER LAINNYA\n"
        "Alamat JL. MERDEKA NO. 5, DENPASAR\n"
        "Tanggal Terbit 12 MEI 2026"
    )
    out = await extract.extract_fields("oss", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "nib"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["nib_labels"]
    assert out["fields"]["nib_number"]["value"] == "8123456789012"
    assert out["fields"]["company_name"]["value"] == "PT CONTOH MAJU BERSAMA"
    assert out["fields"]["kbli_codes"]["value"] == ["62019"]
    assert out["fields"]["address"]["value"] == "JL. MERDEKA NO. 5, DENPASAR"
    assert out["fields"]["issue_date"]["value"] == "2026-05-12"


async def test_npwp_label_fields_skip_model_call():
    """Clearly-labelled NPWP OCR carries taxpayer fields locally."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "KARTU NOMOR POKOK WAJIB PAJAK\n"
        "NPWP : 09.876.543.2-901.000\n"
        "Nama : PT ZANTARA TEST MANDIRI\n"
        "Alamat : JALAN RAYA CANGGU NO 10 BADUNG"
    )
    out = await extract.extract_fields("npwp_company", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "npwp"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["npwp_labels"]
    assert out["fields"]["npwp_number"]["value"] == "098765432901000"
    assert out["fields"]["name"]["value"] == "PT ZANTARA TEST MANDIRI"
    assert out["fields"]["address"]["value"] == "JALAN RAYA CANGGU NO 10 BADUNG"


async def test_npwp_label_fields_accept_colonless_ocr_labels():
    """NPWP OCR often omits separators while preserving taxpayer identity fields."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "KARTU NPWP\n"
        "NPWP 09.876.543.2-901.000\n"
        "Nama PT CONTOH MAJU BERSAMA\n"
        "Alamat JL. RAYA UBUD NO. 10, GIANYAR\n"
        "KPP PRATAMA GIANYAR"
    )
    out = await extract.extract_fields("npwp_company", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "npwp"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["npwp_labels"]
    assert out["fields"]["npwp_number"]["value"] == "098765432901000"
    assert out["fields"]["name"]["value"] == "PT CONTOH MAJU BERSAMA"
    assert out["fields"]["address"]["value"] == "JL. RAYA UBUD NO. 10, GIANYAR"


async def test_skt_label_fields_skip_model_call():
    """Clearly-labelled SKT OCR carries tax-registration fields locally."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "SURAT KETERANGAN TERDAFTAR\n"
        "Nomor : PEM-00123/WPJ.12/KP.0103/2026\n"
        "NPWP : 09.876.543.2-901.000\n"
        "Nama : PT ZANTARA TEST MANDIRI\n"
        "Alamat : JALAN RAYA CANGGU NO 10 BADUNG\n"
        "Tanggal Terdaftar : 15 Mei 2026"
    )
    out = await extract.extract_fields("skt", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "skt"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["skt_labels"]
    assert out["fields"]["skt_number"]["value"] == "PEM-00123/WPJ.12/KP.0103/2026"
    assert out["fields"]["npwp_number"]["value"] == "098765432901000"
    assert out["fields"]["name"]["value"] == "PT ZANTARA TEST MANDIRI"
    assert out["fields"]["address"]["value"] == "JALAN RAYA CANGGU NO 10 BADUNG"
    assert out["fields"]["registration_date"]["value"] == "2026-05-15"


async def test_skt_label_fields_accept_colonless_ocr_labels():
    """SKT OCR often drops separators on taxpayer fields."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "SURAT KETERANGAN TERDAFTAR\n"
        "Nomor PEM-00123/WPJ.12/KP.0103/2026\n"
        "NPWP 09.876.543.2-901.000\n"
        "Nama PT ZANTARA TEST MANDIRI\n"
        "Alamat JALAN RAYA CANGGU NO 10 BADUNG\n"
        "Tanggal Terdaftar 15 Mei 2026"
    )
    out = await extract.extract_fields("skt", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "skt"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["skt_labels"]
    assert out["fields"]["skt_number"]["value"] == "PEM-00123/WPJ.12/KP.0103/2026"
    assert out["fields"]["npwp_number"]["value"] == "098765432901000"
    assert out["fields"]["name"]["value"] == "PT ZANTARA TEST MANDIRI"
    assert out["fields"]["address"]["value"] == "JALAN RAYA CANGGU NO 10 BADUNG"
    assert out["fields"]["registration_date"]["value"] == "2026-05-15"


async def test_skt_model_alias_fields_map_to_canonical_schema():
    """LLM alias names for SKT are preserved as canonical fields."""
    payload = {
        "registration_number": {
            "value": "PEM-00123/WPJ.12/KP.0103/2026",
            "source_page": 1,
        },
        "npwp": {"value": "09.876.543.2-901.000", "source_page": 1},
        "taxpayer_name": {"value": "PT ZANTARA TEST MANDIRI", "source_page": 1},
        "taxpayer_address": {
            "value": "JALAN RAYA CANGGU NO 10 BADUNG",
            "source_page": 1,
        },
        "registered_date": {"value": "2026-05-15", "source_page": 1},
    }

    out = await extract.extract_fields(
        "skt",
        ["OCR fragment from a tax registration certificate without clear labels"],
        generate_fn=_fake_gen(payload),
    )

    assert out["doc_type"] == "skt"
    assert out["extraction_model"] == "sea-lion"
    assert out["fields"]["skt_number"]["value"] == "PEM-00123/WPJ.12/KP.0103/2026"
    assert out["fields"]["npwp_number"]["value"] == "09.876.543.2-901.000"
    assert out["fields"]["name"]["value"] == "PT ZANTARA TEST MANDIRI"
    assert out["fields"]["address"]["value"] == "JALAN RAYA CANGGU NO 10 BADUNG"
    assert out["fields"]["registration_date"]["value"] == "2026-05-15"
    assert out["field_aliases"] == {
        "skt_number": "registration_number",
        "npwp_number": "npwp",
        "name": "taxpayer_name",
        "address": "taxpayer_address",
        "registration_date": "registered_date",
    }
    assert out["any_low_confidence"] is False


async def test_sk_kemenkumham_label_fields_skip_model_call():
    """Clearly-labelled SK Kemenkumham OCR carries company decision fields locally."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "KEPUTUSAN MENTERI HUKUM DAN HAK ASASI MANUSIA REPUBLIK INDONESIA\n"
        "Nomor AHU-0012345.AH.01.01.TAHUN 2026\n"
        "Tentang Pengesahan Pendirian Badan Hukum Perseroan Terbatas\n"
        "PT BALI ZERO SUKSES\n"
        "Ditetapkan di Jakarta\n"
        "Pada tanggal 05 Mei 2026"
    )
    out = await extract.extract_fields("sk_menkumham", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "sk_kemenkumham"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["sk_kemenkumham_labels"]
    assert out["fields"]["sk_number"]["value"] == "AHU-0012345.AH.01.01.TAHUN 2026"
    assert out["fields"]["company_name"]["value"] == "PT BALI ZERO SUKSES"
    assert out["fields"]["date"]["value"] == "2026-05-05"


async def test_sk_kemenkumham_label_fields_accept_colonless_company_label():
    """SK Kemenkumham OCR often keeps the company label but drops the separator."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "KEPUTUSAN MENTERI HUKUM DAN HAK ASASI MANUSIA REPUBLIK INDONESIA\n"
        "Nomor AHU-0012345.AH.01.01.TAHUN 2026\n"
        "Tentang Pengesahan Pendirian Badan Hukum Perseroan Terbatas\n"
        "Nama Perseroan PT BALI ZERO SUKSES\n"
        "Ditetapkan di Jakarta\n"
        "Pada tanggal 05 Mei 2026"
    )
    out = await extract.extract_fields("sk_menkumham", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "sk_kemenkumham"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["sk_kemenkumham_labels"]
    assert out["fields"]["sk_number"]["value"] == "AHU-0012345.AH.01.01.TAHUN 2026"
    assert out["fields"]["company_name"]["value"] == "PT BALI ZERO SUKSES"
    assert out["fields"]["date"]["value"] == "2026-05-05"


async def test_passport_label_fields_skip_model_call():
    """Clearly-labelled passport OCR carries routing-critical fields locally."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "REPUBLIC OF EXAMPLAND\n"
        "PASSPORT\n"
        "Surname: ROSSI\n"
        "Given Names: MARIO LUCA\n"
        "Passport No.: XK1234567\n"
        "Nationality: ITALIAN\n"
        "Date of Birth: 1987-05-13\n"
        "Date of Expiry: 2031-09-22"
    )
    out = await extract.extract_fields("passport", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["passport_labels"]
    assert out["fields"]["passport_no"]["value"] == "XK1234567"
    assert out["fields"]["name"]["value"] == "Mario Luca Rossi"
    assert out["fields"]["nationality"]["value"] == "Italian"
    assert out["fields"]["dob"]["value"] == "1987-05-13"
    assert out["fields"]["expiry"]["value"] == "2031-09-22"


async def test_passport_label_fields_accept_colonless_ocr_labels():
    """Vision OCR often drops label separators while keeping field order clear."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "PASSPORT\n"
        "Type P Country UTOPIA\n"
        "Passport No YA1234567\n"
        "Surname ROSSI\n"
        "Given Names MARIO LUCA\n"
        "Nationality ITALIAN\n"
        "Date of Birth 14 JAN 1987\n"
        "Sex M\n"
        "Date of Expiry 13 JAN 2032"
    )
    out = await extract.extract_fields("passport", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["passport_labels"]
    assert out["fields"]["passport_no"]["value"] == "YA1234567"
    assert out["fields"]["name"]["value"] == "Mario Luca Rossi"
    assert out["fields"]["nationality"]["value"] == "Italian"
    assert out["fields"]["dob"]["value"] == "1987-01-14"
    assert out["fields"]["expiry"]["value"] == "2032-01-13"


async def test_visa_label_fields_skip_model_call():
    """Clearly-labelled e-visa OCR carries routing-critical fields locally."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "REPUBLIC OF INDONESIA\n"
        "ELECTRONIC VISA\n"
        "Visa No. : EV-2026-000123\n"
        "Visa Index : C1\n"
        "Name : MARIO ROSSI\n"
        "Passport No. : XK1234567\n"
        "Valid Until : 2026-09-30\n"
        "Sponsor : PT BALI ZERO"
    )
    out = await extract.extract_fields("e-visa", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["visa_labels"]
    assert out["fields"]["visa_no"]["value"] == "EV-2026-000123"
    assert out["fields"]["visa_index"]["value"] == "C1"
    assert out["fields"]["name"]["value"] == "Mario Rossi"
    assert out["fields"]["passport_no"]["value"] == "XK1234567"
    assert out["fields"]["expiry"]["value"] == "2026-09-30"
    assert out["fields"]["sponsor"]["value"] == "PT BALI ZERO"


async def test_kitas_label_fields_skip_model_call():
    """Clearly-labelled KITAS OCR carries routing-critical fields without SEA-LION."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "KARTU IZIN TINGGAL TERBATAS\n"
        "No. KITAS : 2C11JE0001-X\n"
        "Nama : MARIO ROSSI\n"
        "Berlaku Hingga : 31 DEC 2027\n"
        "Penjamin : PT BALI ZERO"
    )
    out = await extract.extract_fields("kitas", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["kitas_labels"]
    assert out["fields"]["kitas_no"]["value"] == "2C11JE0001-X"
    assert out["fields"]["name"]["value"] == "Mario Rossi"
    assert out["fields"]["expiry"]["value"] == "2027-12-31"
    assert out["fields"]["sponsor"]["value"] == "PT BALI ZERO"


async def test_kitas_label_number_drops_ocr_prefix_inside_value():
    """Vision OCR may include the ITAS/KITAS label inside the captured number."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "KARTU IZIN TINGGAL TERBATAS\n"
        "No. ITAS : ITAS 2C11AB98765\n"
        "Nama : MARIO LUCA ROSSI"
    )
    out = await extract.extract_fields("kitas", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["extraction_model"] == "deterministic_labels"
    assert out["fields"]["kitas_no"]["value"] == "2C11AB98765"


async def test_kitas_label_fields_accept_colonless_ocr_labels():
    """Gemini/Ollama OCR can emit KITAS fields as label + value without punctuation."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "IZIN TINGGAL TERBATAS\n"
        "No. ITAS 2C11AB98765\n"
        "Name MARIO LUCA ROSSI\n"
        "Nationality ITALIA\n"
        "Sponsor PT BALI ZERO NUSANTARA\n"
        "Valid Until 30 JUN 2027"
    )
    out = await extract.extract_fields("itas", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "kitas"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["kitas_labels"]
    assert out["fields"]["kitas_no"]["value"] == "2C11AB98765"
    assert out["fields"]["name"]["value"] == "Mario Luca Rossi"
    assert out["fields"]["expiry"]["value"] == "2027-06-30"
    assert out["fields"]["sponsor"]["value"] == "PT BALI ZERO NUSANTARA"


async def test_itap_label_fields_skip_model_call():
    """Clearly-labelled KITAP/ITAP OCR carries routing-critical fields locally."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "REPUBLIK INDONESIA\n"
        "KARTU IZIN TINGGAL TETAP\n"
        "No. ITAP : 2C-123456\n"
        "Nama : MARIO ROSSI\n"
        "Berlaku Hingga : 2030-05-31\n"
        "Penjamin : PT BALI ZERO"
    )
    out = await extract.extract_fields("kitap", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "itap"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["itap_labels"]
    assert out["fields"]["itap_no"]["value"] == "2C-123456"
    assert out["fields"]["name"]["value"] == "Mario Rossi"
    assert out["fields"]["expiry"]["value"] == "2030-05-31"
    assert out["fields"]["sponsor"]["value"] == "PT BALI ZERO"


async def test_itk_label_fields_skip_model_call():
    """Clearly-labelled ITK OCR carries routing-critical fields locally."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "REPUBLIK INDONESIA\n"
        "IZIN TINGGAL KUNJUNGAN\n"
        "No. ITK : ITK-2026-7788\n"
        "Nama : MARIO ROSSI\n"
        "Berlaku Hingga : 2026-08-15\n"
        "Penjamin : PT BALI ZERO"
    )
    out = await extract.extract_fields("itk_card", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "itk"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["itk_labels"]
    assert out["fields"]["itk_no"]["value"] == "ITK-2026-7788"
    assert out["fields"]["name"]["value"] == "Mario Rossi"
    assert out["fields"]["expiry"]["value"] == "2026-08-15"
    assert out["fields"]["sponsor"]["value"] == "PT BALI ZERO"


async def test_ktp_label_fields_skip_model_call():
    """Clearly-labelled KTP OCR extracts NIK/name without the heavy model."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "PROVINSI BALI\n"
        "NIK : 5101010101010001\n"
        "Nama : MADE SARI\n"
        "Tempat/Tgl Lahir : DENPASAR, 01-01-1990\n"
        "Alamat : JL SUNSET ROAD"
    )
    out = await extract.extract_fields("ktp", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["ktp_labels"]
    assert out["fields"]["nik"]["value"] == "5101010101010001"
    assert out["fields"]["name"]["value"] == "Made Sari"
    assert out["fields"]["dob"]["value"] == "1990-01-01"
    assert out["fields"]["address"]["value"] == "JL SUNSET ROAD"


async def test_ktp_label_fields_accept_colonless_ocr_labels():
    """KTP OCR often drops separators but still carries client identity fields."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "PROVINSI BALI\n"
        "NIK 5101010101010001\n"
        "Nama MADE SARI\n"
        "Tempat/Tgl Lahir DENPASAR, 01-01-1990\n"
        "Alamat JL SUNSET ROAD"
    )
    out = await extract.extract_fields("e_ktp", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "ktp"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["ktp_labels"]
    assert out["fields"]["nik"]["value"] == "5101010101010001"
    assert out["fields"]["name"]["value"] == "Made Sari"
    assert out["fields"]["dob"]["value"] == "1990-01-01"
    assert out["fields"]["address"]["value"] == "JL SUNSET ROAD"


async def test_family_card_label_fields_skip_model_call():
    """Clearly-labelled KK OCR extracts family routing fields locally."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "KARTU KELUARGA\n"
        "No. KK : 5101010101010001\n"
        "Kepala Keluarga : MADE FAMILY\n"
        "Anggota Keluarga : MADE FAMILY; WAYAN CHILD\n"
        "Alamat : JL SUNSET ROAD DENPASAR"
    )
    out = await extract.extract_fields("kk", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "family_card"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["family_card_labels"]
    assert out["fields"]["family_card_no"]["value"] == "5101010101010001"
    assert out["fields"]["name"]["value"] == "Made Family"
    assert out["fields"]["members"]["value"] == ["Made Family", "Wayan Child"]
    assert out["fields"]["address"]["value"] == "JL SUNSET ROAD DENPASAR"


async def test_family_card_label_fields_accept_colonless_ocr_labels():
    """KK OCR often keeps labels but drops separators."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "KARTU KELUARGA\n"
        "No. KK 5101010101010001\n"
        "Kepala Keluarga MADE FAMILY\n"
        "Anggota Keluarga MADE FAMILY; WAYAN CHILD\n"
        "Alamat JL SUNSET ROAD DENPASAR"
    )
    out = await extract.extract_fields("kartu_keluarga", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "family_card"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["family_card_labels"]
    assert out["fields"]["family_card_no"]["value"] == "5101010101010001"
    assert out["fields"]["name"]["value"] == "Made Family"
    assert out["fields"]["members"]["value"] == ["Made Family", "Wayan Child"]
    assert out["fields"]["address"]["value"] == "JL SUNSET ROAD DENPASAR"


async def test_birth_certificate_label_fields_skip_model_call():
    """Clearly-labelled birth-certificate OCR extracts child and parent fields locally."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "AKTA KELAHIRAN\n"
        "No. Akta : AK-2026-0001\n"
        "Nama Anak : WAYAN CHILD\n"
        "Tempat Lahir : DENPASAR\n"
        "Tanggal Lahir : 01 Januari 2020\n"
        "Nama Orang Tua : MADE PARENT; WAYAN PARENT"
    )
    out = await extract.extract_fields("akta_kelahiran", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "birth_certificate"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["birth_certificate_labels"]
    assert out["fields"]["certificate_no"]["value"] == "AK-2026-0001"
    assert out["fields"]["name"]["value"] == "Wayan Child"
    assert out["fields"]["dob"]["value"] == "2020-01-01"
    assert out["fields"]["place_of_birth"]["value"] == "DENPASAR"
    assert out["fields"]["parents"]["value"] == ["Made Parent", "Wayan Parent"]


async def test_birth_certificate_label_fields_accept_colonless_ocr_labels():
    """Birth-certificate OCR often keeps labels but drops separators."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "AKTA KELAHIRAN\n"
        "No. Akta AK-2026-0001\n"
        "Nama Anak WAYAN CHILD\n"
        "Tempat Lahir DENPASAR\n"
        "Tanggal Lahir 01 Januari 2020\n"
        "Nama Orang Tua MADE PARENT; WAYAN PARENT"
    )
    out = await extract.extract_fields("akta_kelahiran", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "birth_certificate"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["birth_certificate_labels"]
    assert out["fields"]["certificate_no"]["value"] == "AK-2026-0001"
    assert out["fields"]["name"]["value"] == "Wayan Child"
    assert out["fields"]["dob"]["value"] == "2020-01-01"
    assert out["fields"]["place_of_birth"]["value"] == "DENPASAR"
    assert out["fields"]["parents"]["value"] == ["Made Parent", "Wayan Parent"]


async def test_birth_certificate_label_fields_split_comma_separated_parents():
    """OCR often emits parent lists as comma-separated label values."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "AKTA KELAHIRAN\n"
        "No. Akta : AK-2026-0001\n"
        "Nama Anak : WAYAN CHILD\n"
        "Tanggal Lahir : 01 Januari 2020\n"
        "Nama Orang Tua : MADE PARENT, WAYAN PARENT"
    )
    out = await extract.extract_fields("akta_kelahiran", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["fields"]["parents"]["value"] == ["Made Parent", "Wayan Parent"]


async def test_marriage_certificate_label_fields_skip_model_call():
    """Clearly-labelled marriage-certificate OCR extracts spouse fields locally."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "BUKU NIKAH\n"
        "No. Akta Nikah : MN-2026-0007\n"
        "Nama Suami : MADE SPOUSE\n"
        "Nama Istri : WAYAN SPOUSE\n"
        "Tanggal Nikah : 14 Februari 2024\n"
        "Tempat Nikah : DENPASAR"
    )
    out = await extract.extract_fields("buku_nikah", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "marriage_certificate"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["marriage_certificate_labels"]
    assert out["fields"]["certificate_no"]["value"] == "MN-2026-0007"
    assert out["fields"]["name"]["value"] == "Made Spouse"
    assert out["fields"]["spouse_names"]["value"] == ["Made Spouse", "Wayan Spouse"]
    assert out["fields"]["marriage_date"]["value"] == "2024-02-14"
    assert out["fields"]["place"]["value"] == "DENPASAR"


async def test_marriage_certificate_label_fields_accept_colonless_ocr_labels():
    """Marriage-certificate OCR may drop separators after spouse/date/place labels."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "BUKU NIKAH\n"
        "No. Akta Nikah MN-2026-0007\n"
        "Nama Suami MADE SPOUSE\n"
        "Nama Istri WAYAN SPOUSE\n"
        "Tanggal Nikah 14 Februari 2024\n"
        "Tempat Nikah DENPASAR"
    )
    out = await extract.extract_fields("buku_nikah", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "marriage_certificate"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["marriage_certificate_labels"]
    assert out["fields"]["certificate_no"]["value"] == "MN-2026-0007"
    assert out["fields"]["name"]["value"] == "Made Spouse"
    assert out["fields"]["spouse_names"]["value"] == ["Made Spouse", "Wayan Spouse"]
    assert out["fields"]["marriage_date"]["value"] == "2024-02-14"
    assert out["fields"]["place"]["value"] == "DENPASAR"


async def test_bank_statement_label_fields_skip_model_call():
    """Bank statements can expose account holder/number/balance in labels."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "PT BANK CENTRAL ASIA TBK\n"
        "Nama Rekening : MARIO ROSSI\n"
        "No. Rekening : 1234567890\n"
        "Periode : JUNI 2026\n"
        "Saldo Akhir : IDR 100,000,000"
    )
    out = await extract.extract_fields("bank_statement", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["bank_statement_labels"]
    assert out["fields"]["account_holder"]["value"] == "Mario Rossi"
    assert out["fields"]["bank_name"]["value"] == "BCA"
    assert out["fields"]["account_no"]["value"] == "1234567890"
    assert out["fields"]["statement_period"]["value"] == "JUNI 2026"
    assert out["fields"]["balance"]["value"] == "IDR 100,000,000"


async def test_bank_statement_label_fields_accept_colonless_ocr_labels():
    """Bank-statement OCR often drops separators after account labels."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "PT BANK CENTRAL ASIA TBK\n"
        "Nama Rekening MARIO ROSSI\n"
        "No. Rekening 1234567890\n"
        "Periode JUNI 2026\n"
        "Saldo Akhir IDR 100,000,000"
    )
    out = await extract.extract_fields("bank_statement", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["bank_statement_labels"]
    assert out["fields"]["account_holder"]["value"] == "Mario Rossi"
    assert out["fields"]["bank_name"]["value"] == "BCA"
    assert out["fields"]["account_no"]["value"] == "1234567890"
    assert out["fields"]["statement_period"]["value"] == "JUNI 2026"
    assert out["fields"]["balance"]["value"] == "IDR 100,000,000"


async def test_payment_receipt_label_fields_skip_model_call():
    """Payment receipts can expose transaction fields in labels."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "PAYMENT RECEIPT\n"
        "Receipt No : TRX-2026-00077\n"
        "Payer Name : MARIO ROSSI\n"
        "Amount : IDR 10,000,000\n"
        "Payment Date : 2026-06-01\n"
        "Reference : Invoice INV-1"
    )
    out = await extract.extract_fields("proof_of_payment", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "payment_receipt"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["payment_receipt_labels"]
    assert out["fields"]["receipt_no"]["value"] == "TRX-2026-00077"
    assert out["fields"]["payer_name"]["value"] == "Mario Rossi"
    assert out["fields"]["amount"]["value"] == "IDR 10,000,000"
    assert out["fields"]["payment_date"]["value"] == "2026-06-01"
    assert out["fields"]["reference"]["value"] == "Invoice INV-1"


async def test_payment_receipt_label_fields_accept_colonless_ocr_labels():
    """Payment receipts stay deterministic when OCR drops label separators."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "PAYMENT RECEIPT\n"
        "Receipt No TRX-2026-00077\n"
        "Payer Name MARIO ROSSI\n"
        "Amount IDR 10,000,000\n"
        "Payment Date 2026-06-01\n"
        "Reference Invoice INV-1"
    )
    out = await extract.extract_fields("proof_of_payment", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "payment_receipt"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["payment_receipt_labels"]
    assert out["fields"]["receipt_no"]["value"] == "TRX-2026-00077"
    assert out["fields"]["payer_name"]["value"] == "Mario Rossi"
    assert out["fields"]["amount"]["value"] == "IDR 10,000,000"
    assert out["fields"]["payment_date"]["value"] == "2026-06-01"
    assert out["fields"]["reference"]["value"] == "Invoice INV-1"


async def test_travel_ticket_label_fields_skip_model_call():
    """Travel tickets can expose passenger and booking fields in labels."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "BOARDING PASS\n"
        "Passenger Name : MARIO ROSSI\n"
        "Ticket No : TKT-2026-12345\n"
        "Flight Date : 2026-07-01\n"
        "Route : DPS-SIN\n"
        "Booking Reference : ABC123"
    )
    out = await extract.extract_fields("boarding_pass", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "travel_ticket"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["travel_ticket_labels"]
    assert out["fields"]["ticket_no"]["value"] == "TKT-2026-12345"
    assert out["fields"]["name"]["value"] == "Mario Rossi"
    assert out["fields"]["travel_date"]["value"] == "2026-07-01"
    assert out["fields"]["route"]["value"] == "DPS-SIN"
    assert out["fields"]["booking_reference"]["value"] == "ABC123"


async def test_travel_ticket_label_fields_accept_colonless_ocr_labels():
    """Travel tickets stay deterministic when OCR drops label separators."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "BOARDING PASS\n"
        "Passenger Name MARIO ROSSI\n"
        "Ticket No TKT-2026-12345\n"
        "Flight Date 2026-07-01\n"
        "Route DPS-SIN\n"
        "Booking Reference ABC123"
    )
    out = await extract.extract_fields("boarding_pass", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "travel_ticket"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["travel_ticket_labels"]
    assert out["fields"]["ticket_no"]["value"] == "TKT-2026-12345"
    assert out["fields"]["name"]["value"] == "Mario Rossi"
    assert out["fields"]["travel_date"]["value"] == "2026-07-01"
    assert out["fields"]["route"]["value"] == "DPS-SIN"
    assert out["fields"]["booking_reference"]["value"] == "ABC123"


async def test_travel_ticket_label_fields_accept_indonesian_labels():
    """Indonesian e-ticket OCR should expose booking fields without SEA-LION."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "TIKET ELEKTRONIK\n"
        "Nama Penumpang ANTON TEST\n"
        "Nomor Tiket 1261234567890\n"
        "Tanggal Keberangkatan 25 JUNI 2026\n"
        "Rute DPS-CGK\n"
        "Kode Booking BZ9K2L"
    )
    out = await extract.extract_fields("e_ticket", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "travel_ticket"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["travel_ticket_labels"]
    assert out["fields"]["ticket_no"]["value"] == "1261234567890"
    assert out["fields"]["name"]["value"] == "Anton Test"
    assert out["fields"]["travel_date"]["value"] == "2026-06-25"
    assert out["fields"]["route"]["value"] == "DPS-CGK"
    assert out["fields"]["booking_reference"]["value"] == "BZ9K2L"


async def test_medical_insurance_label_fields_skip_model_call():
    """Medical insurance policies can expose coverage fields in labels."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "TRAVEL INSURANCE POLICY\n"
        "Policy No : POL-2026-7788\n"
        "Insured Name : MARIO ROSSI\n"
        "Insurer : Example Insurance\n"
        "Coverage Period : 2026-07-01 to 2026-12-31\n"
        "Expiry Date : 2026-12-31"
    )
    out = await extract.extract_fields("travel_insurance", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "medical_insurance"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["medical_insurance_labels"]
    assert out["fields"]["policy_no"]["value"] == "POL-2026-7788"
    assert out["fields"]["name"]["value"] == "Mario Rossi"
    assert out["fields"]["insurer"]["value"] == "Example Insurance"
    assert out["fields"]["coverage_period"]["value"] == "2026-07-01 to 2026-12-31"
    assert out["fields"]["expiry"]["value"] == "2026-12-31"


async def test_medical_insurance_label_fields_accept_colonless_ocr_labels():
    """Medical insurance stays deterministic when OCR drops label separators."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "TRAVEL INSURANCE POLICY\n"
        "Policy No POL-2026-7788\n"
        "Insured Name MARIO ROSSI\n"
        "Insurer Example Insurance\n"
        "Coverage Period 2026-07-01 to 2026-12-31\n"
        "Expiry Date 2026-12-31"
    )
    out = await extract.extract_fields("travel_insurance", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "medical_insurance"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["medical_insurance_labels"]
    assert out["fields"]["policy_no"]["value"] == "POL-2026-7788"
    assert out["fields"]["name"]["value"] == "Mario Rossi"
    assert out["fields"]["insurer"]["value"] == "Example Insurance"
    assert out["fields"]["coverage_period"]["value"] == "2026-07-01 to 2026-12-31"
    assert out["fields"]["expiry"]["value"] == "2026-12-31"


async def test_akta_pendirian_label_fields_skip_model_call():
    """Clearly-labelled deed OCR carries company establishment fields locally."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "AKTA PENDIRIAN PERSEROAN TERBATAS\n"
        "Nama Perseroan : PT BALI ZERO SUKSES\n"
        "Notaris : Made Sutrisna, S.H., M.Kn.\n"
        "Modal Dasar : Rp 1.000.000.000\n"
        "Tanggal Akta : 05 Mei 2026"
    )
    out = await extract.extract_fields("akta", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "akta_pendirian"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["akta_pendirian_labels"]
    assert out["fields"]["company_name"]["value"] == "PT BALI ZERO SUKSES"
    assert out["fields"]["notary"]["value"] == "Made Sutrisna, S.H., M.Kn."
    assert out["fields"]["capital"]["value"] == "Rp 1.000.000.000"
    assert out["fields"]["date"]["value"] == "2026-05-05"


async def test_akta_pendirian_label_fields_accept_colonless_company_label():
    """Akta OCR often keeps the company label but drops the separator."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "AKTA PENDIRIAN PERSEROAN TERBATAS\n"
        "Nama Perseroan PT BALI ZERO SUKSES\n"
        "Notaris : Made Sutrisna, S.H., M.Kn.\n"
        "Modal Dasar : Rp 1.000.000.000\n"
        "Tanggal Akta : 05 Mei 2026"
    )
    out = await extract.extract_fields("akta", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "akta_pendirian"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["akta_pendirian_labels"]
    assert out["fields"]["company_name"]["value"] == "PT BALI ZERO SUKSES"
    assert out["fields"]["notary"]["value"] == "Made Sutrisna, S.H., M.Kn."
    assert out["fields"]["capital"]["value"] == "Rp 1.000.000.000"
    assert out["fields"]["date"]["value"] == "2026-05-05"


async def test_akta_pendirian_label_fields_accept_colonless_detail_labels():
    """Akta establishment fields stay deterministic when OCR drops separators."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "AKTA PENDIRIAN PERSEROAN TERBATAS\n"
        "Nama Perseroan PT BALI ZERO SUKSES\n"
        "Notaris Made Sutrisna, S.H., M.Kn.\n"
        "Modal Dasar Rp 1.000.000.000\n"
        "Tanggal Akta 05 Mei 2026"
    )
    out = await extract.extract_fields("akta", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "akta_pendirian"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["akta_pendirian_labels"]
    assert out["fields"]["company_name"]["value"] == "PT BALI ZERO SUKSES"
    assert out["fields"]["notary"]["value"] == "Made Sutrisna, S.H., M.Kn."
    assert out["fields"]["capital"]["value"] == "Rp 1.000.000.000"
    assert out["fields"]["date"]["value"] == "2026-05-05"


async def test_profil_perseroan_label_fields_skip_model_call():
    """Company-profile OCR carries registry fields locally."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "PROFIL PERSEROAN\n"
        "Nama Perseroan : PT BALI ZERO SUKSES\n"
        "Direktur : MARIO ROSSI\n"
        "Komisaris : LUCA BIANCHI\n"
        "KBLI : 70209, 55120\n"
        "Modal Dasar : Rp 1.000.000.000\n"
        "Alamat : Jalan Sunset Road 88, Badung"
    )
    out = await extract.extract_fields("company_profile", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "profil_perseroan"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["profil_perseroan_labels"]
    assert out["fields"]["company_name"]["value"] == "PT BALI ZERO SUKSES"
    assert out["fields"]["directors"]["value"] == ["Mario Rossi"]
    assert out["fields"]["commissioners"]["value"] == ["Luca Bianchi"]
    assert out["fields"]["kbli_codes"]["value"] == ["70209", "55120"]
    assert out["fields"]["capital"]["value"] == "Rp 1.000.000.000"
    assert out["fields"]["address"]["value"] == "Jalan Sunset Road 88, Badung"


async def test_profil_perseroan_label_fields_accept_colonless_company_label():
    """Profil Perseroan OCR often keeps the company label but drops the separator."""
    called = {"n": 0}

    async def _gen(model, prompt):  # noqa: ARG001
        called["n"] += 1
        return "{}"

    ocr = (
        "PROFIL PERSEROAN\n"
        "Nama Perseroan PT BALI ZERO SUKSES\n"
        "Direktur : MARIO ROSSI\n"
        "Komisaris : LUCA BIANCHI\n"
        "KBLI : 70209, 55120\n"
        "Modal Dasar : Rp 1.000.000.000\n"
        "Alamat : Jalan Sunset Road 88, Badung"
    )
    out = await extract.extract_fields("company_profile", [ocr], generate_fn=_gen)

    assert called["n"] == 0
    assert out["doc_type"] == "profil_perseroan"
    assert out["extraction_model"] == "deterministic_labels"
    assert out["deterministic_extractors"] == ["profil_perseroan_labels"]
    assert out["fields"]["company_name"]["value"] == "PT BALI ZERO SUKSES"
    assert out["fields"]["directors"]["value"] == ["Mario Rossi"]
    assert out["fields"]["commissioners"]["value"] == ["Luca Bianchi"]
    assert out["fields"]["kbli_codes"]["value"] == ["70209", "55120"]
    assert out["fields"]["capital"]["value"] == "Rp 1.000.000.000"
    assert out["fields"]["address"]["value"] == "Jalan Sunset Road 88, Badung"


async def test_akta_list_fields():
    payload = {
        "company_name": {"value": "PT MAJU", "source_page": 1},
        "directors": {"value": ["Budi Santoso", "Siti Aminah"], "source_page": 2},
        "commissioners": {"value": ["Andi Wijaya"], "source_page": 2},
        "capital": {"value": "Rp 1.000.000.000", "source_page": 1},
        "notary": {"value": "Notaris Made Sutrisna", "source_page": 1},
        "date": {"value": "2023-11-02", "source_page": 1},
    }
    out = await extract.extract_fields(
        "akta_pendirian", ["p1", "p2 directors"], generate_fn=_fake_gen(payload)
    )
    assert out["fields"]["directors"]["value"] == ["Budi Santoso", "Siti Aminah"]
    assert out["fields"]["commissioners"]["value"] == ["Andi Wijaya"]


@pytest.mark.parametrize(
    "doc_type, payload, expected_key, expected_value",
    [
        (
            "visa",
            {
                "visa_no": {"value": "EV-123456", "source_page": 1},
                "visa_index": {"value": "B211A", "source_page": 1},
                "name": {"value": "Mario Rossi", "source_page": 1},
                "passport_no": {"value": "YC1234567", "source_page": 1},
                "expiry": {"value": "2026-12-31", "source_page": 1},
                "sponsor": {"value": "PT Bali Zero", "source_page": 1},
            },
            "visa_index",
            "B211A",
        ),
        (
            "itap",
            {
                "itap_no": {"value": "2C-123456", "source_page": 1},
                "name": {"value": "Mario Rossi", "source_page": 1},
                "expiry": {"value": "2030-05-31", "source_page": 1},
                "sponsor": {"value": "PT Bali Zero", "source_page": 1},
            },
            "itap_no",
            "2C-123456",
        ),
        (
            "itk",
            {
                "itk_no": {"value": "99/ITK/2026", "source_page": 1},
                "name": {"value": "Mario Rossi", "source_page": 1},
                "expiry": {"value": "2026-08-01", "source_page": 1},
                "sponsor": {"value": None, "source_page": None},
            },
            "itk_no",
            "99/ITK/2026",
        ),
        (
            "ktp",
            {
                "nik": {"value": "5101010101010001", "source_page": 1},
                "name": {"value": "Made Sari", "source_page": 1},
                "dob": {"value": "1990-01-01", "source_page": 1},
                "address": {"value": "Denpasar", "source_page": 1},
            },
            "nik",
            "5101010101010001",
        ),
        (
            "family_card",
            {
                "family_card_no": {"value": "5101010101010001", "source_page": 1},
                "name": {"value": "Made Family", "source_page": 1},
                "members": {"value": ["Made Family", "Wayan Child"], "source_page": 1},
                "address": {"value": "Denpasar", "source_page": 1},
            },
            "members",
            ["Made Family", "Wayan Child"],
        ),
        (
            "birth_certificate",
            {
                "certificate_no": {"value": "AK-123", "source_page": 1},
                "name": {"value": "Wayan Child", "source_page": 1},
                "dob": {"value": "2020-01-01", "source_page": 1},
                "place_of_birth": {"value": "Denpasar", "source_page": 1},
                "parents": {"value": ["Made Parent", "Wayan Parent"], "source_page": 1},
            },
            "name",
            "Wayan Child",
        ),
        (
            "marriage_certificate",
            {
                "certificate_no": {"value": "MN-123", "source_page": 1},
                "name": {"value": "Made Spouse", "source_page": 1},
                "spouse_names": {"value": ["Made Spouse", "Wayan Spouse"], "source_page": 1},
                "marriage_date": {"value": "2024-01-01", "source_page": 1},
                "place": {"value": "Denpasar", "source_page": 1},
            },
            "spouse_names",
            ["Made Spouse", "Wayan Spouse"],
        ),
        (
            "payment_receipt",
            {
                "receipt_no": {"value": "TRX-123", "source_page": 1},
                "payer_name": {"value": "Mario Rossi", "source_page": 1},
                "amount": {"value": "IDR 10,000,000", "source_page": 1},
                "payment_date": {"value": "2026-06-01", "source_page": 1},
                "reference": {"value": "Invoice INV-1", "source_page": 1},
            },
            "amount",
            "IDR 10,000,000",
        ),
        (
            "travel_ticket",
            {
                "ticket_no": {"value": "TKT-123", "source_page": 1},
                "name": {"value": "Mario Rossi", "source_page": 1},
                "travel_date": {"value": "2026-07-01", "source_page": 1},
                "route": {"value": "DPS-SIN", "source_page": 1},
                "booking_reference": {"value": "ABC123", "source_page": 1},
            },
            "booking_reference",
            "ABC123",
        ),
        (
            "bank_statement",
            {
                "account_holder": {"value": "Mario Rossi", "source_page": 1},
                "bank_name": {"value": "BCA", "source_page": 1},
                "account_no": {"value": "****1234", "source_page": 1},
                "statement_period": {"value": "2026-06", "source_page": 1},
                "balance": {"value": "IDR 100,000,000", "source_page": 1},
            },
            "bank_name",
            "BCA",
        ),
        (
            "medical_insurance",
            {
                "policy_no": {"value": "POL-123", "source_page": 1},
                "name": {"value": "Mario Rossi", "source_page": 1},
                "insurer": {"value": "Example Insurance", "source_page": 1},
                "coverage_period": {"value": "2026", "source_page": 1},
                "expiry": {"value": "2026-12-31", "source_page": 1},
            },
            "policy_no",
            "POL-123",
        ),
        (
            "sk_kemenkumham",
            {
                "sk_number": {"value": "AHU-0000001.AH.01.01", "source_page": 1},
                "company_name": {"value": "PT Bali Zero", "source_page": 1},
                "date": {"value": "2024-01-01", "source_page": 1},
            },
            "company_name",
            "PT Bali Zero",
        ),
    ],
)
async def test_new_doc_type_schemas_extract_with_evidence(
    doc_type, payload, expected_key, expected_value
):
    out = await extract.extract_fields(
        doc_type, ["legible intake document text"], generate_fn=_fake_gen(payload)
    )
    assert out["doc_type"] == doc_type
    assert out["fields"][expected_key]["value"] == expected_value
    assert out["fields"][expected_key]["confidence"] >= 0.6


# --------------------------------------------------------------------------- #
# Worker stage-handler contract                                               #
# --------------------------------------------------------------------------- #

async def test_extract_stage_reads_upstream_stage_output(monkeypatch):
    payload = {"nib_number": {"value": "1234567890123", "source_page": 1}}

    async def _gen(model, prompt):  # noqa: ARG001
        return json.dumps(payload)

    monkeypatch.setattr(extract, "_ollama_generate", _gen)
    job = {
        "id": 42,
        "stage_output": {
            "classify": {"doc_type": "nib"},
            "ocr": {"ocr_text_per_page": ["NIB: 1234567890123"]},
        },
    }
    out = await extract.extract_stage(job, "extract")
    assert out["doc_type"] == "nib"
    assert out["fields"]["nib_number"]["value"] == "1234567890123"


async def test_extract_stage_rejects_wrong_stage():
    with pytest.raises(ValueError):
        await extract.extract_stage({"id": 1}, "validate")


# --------------------------------------------------------------------------- #
# LIVE: real SEA-LION model (deselect with -m "not slow")                     #
# --------------------------------------------------------------------------- #

@pytest.mark.slow
@pytest.mark.integration
async def test_live_sealion_golden_rule_null_on_illegible():
    """Real SEA-LION must null an illegible field, not invent it."""
    if not await is_ollama_available():
        pytest.skip("SEA-LION/Ollama not reachable (localhost:11434)")
    ocr = (
        "NOMOR INDUK BERUSAHA\n"
        "NIB: 9876543210987\n"
        "Nama Perusahaan: PT NUZANTARA JAYA\n"
        "Alamat: [tidak terbaca / illegible smudge]\n"
        "KBLI: 70209"
    )
    out = await extract.extract_fields("nib", [ocr])
    # legible fields present
    assert out["fields"]["nib_number"]["value"] == "9876543210987"
    assert out["fields"]["company_name"]["value"] == "PT NUZANTARA JAYA"
    # GOLDEN RULE: illegible address must be null, not fabricated
    assert out["fields"]["address"]["value"] is None
    assert out["fields"]["address"]["confidence"] == 0.0
    # issue_date absent -> null
    assert out["fields"]["issue_date"]["value"] is None
    await extract.close_extract_client()
