"""Unit tests for FASE 3a intake preprocess + classify.

Fast + deterministic: the live Ollama vision call is monkeypatched so CI never
needs a GPU/model. Two empirically-grounded behaviours are locked:

  * anti-hallucination: undeterminable text -> unknown + 0.0 (never a guess);
  * cloud OCR remains opt-in: default intake OCR is local, and cloud OCR is
    blocked unless the sovereignty gate explicitly allows it.

The live-model behaviour (qwen3-vl thinking-leak, qwen2.5vl fallback) is
exercised separately by the on-Pro E2E run, not here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from backend.services.intake import classify as cls
from backend.services.intake import model_roles
from backend.services.intake import preprocess as pre

# ---------------------------------------------------------------------------
# classify_document -- pure text, no model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_text_is_unknown():
    r = await cls.classify_document("")
    assert r["type"] == "unknown"
    assert r["confidence"] == 0.0
    assert r["source_page"] is None


@pytest.mark.asyncio
async def test_whitespace_text_is_unknown():
    r = await cls.classify_document("   \n  \t ")
    assert r["type"] == "unknown"
    assert r["confidence"] == 0.0


@pytest.mark.asyncio
async def test_garbage_text_is_unknown_not_guessed():
    # Anti-hallucination: noise with no doc-evidence must NOT be classified.
    r = await cls.classify_document("xkcd 9981 lorem ipsum qwerty zzz 4471")
    assert r["type"] == "unknown"
    assert r["confidence"] == 0.0


@pytest.mark.asyncio
async def test_weak_single_keyword_below_floor_is_unknown():
    # "imigrasi" alone (weight 0.2) is below the 0.30 floor -> unknown.
    r = await cls.classify_document("kantor imigrasi kelas satu")
    assert r["type"] == "unknown"
    assert r["confidence"] == 0.0


@pytest.mark.asyncio
async def test_npwp_classified():
    r = await cls.classify_document(
        "KEMENTERIAN KEUANGAN REPUBLIK INDONESIA DIREKTORAT JENDERAL PAJAK "
        "NOMOR POKOK WAJIB PAJAK NPWP 09.123.456.7-901.000"
    )
    assert r["type"] == "npwp"
    assert r["confidence"] >= 0.30


@pytest.mark.asyncio
async def test_passport_classified_via_mrz():
    r = await cls.classify_document(
        "REPUBLIC OF INDONESIA PASSPORT PASPOR\nP<IDNSUKARNO<<KARNO<<<<<<<<<<<<<"
    )
    assert r["type"] == "passport"
    assert r["confidence"] >= 0.30


@pytest.mark.asyncio
async def test_akta_classified():
    r = await cls.classify_document(
        "AKTA PENDIRIAN PERSEROAN TERBATAS PT MAJU JAYA NOMOR 17 "
        "DIHADAPAN NOTARIS ANGGARAN DASAR"
    )
    assert r["type"] == "akta_pendirian"
    assert r["confidence"] >= 0.30


@pytest.mark.asyncio
async def test_sk_kemenkumham_classified():
    r = await cls.classify_document(
        "KEPUTUSAN MENTERI HUKUM DAN HAK ASASI MANUSIA TENTANG PENGESAHAN "
        "BADAN HUKUM PERSEROAN AHU-0012345.AH.01.01"
    )
    assert r["type"] == "sk_kemenkumham"


@pytest.mark.asyncio
async def test_evisa_classified():
    r = await cls.classify_document(
        "REPUBLIC OF INDONESIA E-VISA VISA INDEX B211A "
        "DIRECTORATE GENERAL OF IMMIGRATION"
    )
    assert r["type"] == "visa"
    assert r["confidence"] >= 0.30


@pytest.mark.asyncio
async def test_generic_visa_word_alone_stays_unknown():
    r = await cls.classify_document("visa consultation payment note")
    assert r["type"] == "unknown"
    assert r["confidence"] == 0.0


@pytest.mark.asyncio
async def test_family_card_classified():
    r = await cls.classify_document(
        "KARTU KELUARGA Nomor Kartu Keluarga No. KK Kepala Keluarga"
    )
    assert r["type"] == "family_card"
    assert r["confidence"] >= 0.30


@pytest.mark.asyncio
async def test_birth_certificate_classified():
    r = await cls.classify_document(
        "KUTIPAN AKTA KELAHIRAN Dinas Kependudukan dan Pencatatan Sipil"
    )
    assert r["type"] == "birth_certificate"
    assert r["confidence"] >= 0.30


@pytest.mark.asyncio
async def test_marriage_certificate_classified():
    r = await cls.classify_document(
        "BUKU NIKAH AKTA NIKAH Kantor Urusan Agama tanggal pernikahan"
    )
    assert r["type"] == "marriage_certificate"
    assert r["confidence"] >= 0.30


@pytest.mark.asyncio
async def test_generic_family_word_alone_stays_unknown():
    r = await cls.classify_document("family whatsapp note")
    assert r["type"] == "unknown"
    assert r["confidence"] == 0.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text, expected_type",
    [
        ("BUKTI PEMBAYARAN transfer berhasil Transaction ID 123", "payment_receipt"),
        ("BOARDING PASS Passenger Departure Arrival Seat 12A", "travel_ticket"),
        ("BANK STATEMENT Statement of Account saldo awal saldo akhir", "bank_statement"),
        ("TRAVEL INSURANCE policy number sum insured", "medical_insurance"),
    ],
)
async def test_support_documents_classified(text, expected_type):
    r = await cls.classify_document(text)
    assert r["type"] == expected_type
    assert r["confidence"] >= 0.30


@pytest.mark.asyncio
async def test_indonesian_electronic_ticket_classified_without_nik_false_positive():
    r = await cls.classify_document(
        "TIKET ELEKTRONIK Penumpang ANTON TEST Nomor Penerbangan GA421 "
        "Tanggal Keberangkatan 25 JUN 2026 Kode Booking BZ9K2L"
    )
    assert r["type"] == "travel_ticket"
    assert r["confidence"] >= 0.30
    assert "ktp" not in r["scores"]


@pytest.mark.asyncio
async def test_indonesian_transaction_receipt_classified():
    r = await cls.classify_document(
        "BUKTI TRANSAKSI BERHASIL Nomor Referensi 123456 Jumlah Rp 500.000"
    )
    assert r["type"] == "payment_receipt"
    assert r["confidence"] >= 0.30


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "bank meeting note",
        "ticket discussion in whatsapp",
        "insurance question from client",
        "pertanyaan asuransi dari client di whatsapp",
        "payment note without proof",
    ],
)
async def test_generic_support_words_stay_unknown(text):
    r = await cls.classify_document(text)
    assert r["type"] == "unknown"
    assert r["confidence"] == 0.0


@pytest.mark.asyncio
async def test_source_page_attribution():
    # Evidence lives on page 1 (index 1), not page 0.
    pages = [
        {"page": 0, "text": "halaman sampul tanpa isi"},
        {"page": 1, "text": "NOMOR INDUK BERUSAHA NIB lembaga oss perizinan berusaha"},
    ]
    r = await cls.classify_document(None, pages)
    assert r["type"] == "nib"
    assert r["source_page"] == 1


# ---------------------------------------------------------------------------
# Stay-permit disambiguation (ITK / ITAS / ITAP) -- live defect 2026-06-17
# (proposals 12937 / 15368 / 12694: izin-tinggal cards misfiled as passport
# because the card prints a "Passport Number" field -> passport 0.8 > kitas 0.75)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stay_permit_itas_not_passport():
    # Electronic limited stay permit. Note it DOES carry a "Passport Number"
    # field (the exact thing that fooled the scorer into passport:0.8).
    r = await cls.classify_document(
        "IZIN TINGGAL TERBATAS ELEKTRONIK / ELECTRONIC LIMITED STAY PERMIT\n"
        "DIREKTORAT JENDERAL IMIGRASI REPUBLIK INDONESIA\n"
        "Passport Number: <redacted>  Stay Permit Index: <redacted>"
    )
    assert r["type"] == "itas"
    assert r["type"] != "passport"
    assert r["via"] == "stay_permit_override"
    assert r["confidence"] >= 0.55


@pytest.mark.asyncio
async def test_stay_permit_itk_not_passport():
    r = await cls.classify_document(
        "IZIN TINGGAL KUNJUNGAN / VISIT STAY PERMIT\n"
        "DIREKTORAT JENDERAL IMIGRASI\n"
        "Passport Number: <redacted>  Permit Number: 99/ITK/2026"
    )
    assert r["type"] == "itk"
    assert r["type"] != "passport"
    assert r["via"] == "stay_permit_override"


@pytest.mark.asyncio
async def test_stay_permit_itap_not_passport():
    r = await cls.classify_document(
        "IZIN TINGGAL TETAP / PERMANENT STAY PERMIT\n"
        "DIREKTORAT JENDERAL IMIGRASI\n"
        "Passport Number: <redacted>  Stay Permit Index: II C"
    )
    assert r["type"] == "itap"
    assert r["type"] != "passport"
    assert r["via"] == "stay_permit_override"


@pytest.mark.asyncio
async def test_real_passport_still_passport_innocence():
    # INNOCENCE: a genuine passport (proposal 12927 head "PASSPORT / AUSTRALIA")
    # carries NO izin-tinggal / stay-permit marker, so the override must NOT
    # fire and the doc must STILL classify as passport.
    r = await cls.classify_document(
        "PASSPORT  AUSTRALIA  PASSEPORT\n"
        "P<AUSCITIZEN<<JANE<<<<<<<<<<<<<<<<<<<<<<<<<<\n"
        "Type P  Date of expiry 12 JAN 2030"
    )
    assert r["type"] == "passport"
    assert r.get("via") != "stay_permit_override"
    assert r["confidence"] >= 0.30


# ---------------------------------------------------------------------------
# ocr_pages -- monkeypatched vision call (deterministic)
# ---------------------------------------------------------------------------


def test_resolve_ocr_model_reads_model_topology(tmp_path, monkeypatch):
    topology = {"roles": {"ocr_vision": "registry-qwen3-vl:8b"}}
    (tmp_path / "MODEL_TOPOLOGY.json").write_text(json.dumps(topology), encoding="utf-8")
    monkeypatch.setenv("INTAKE_REPO_ROOT", str(tmp_path))
    model_roles.clear_model_role_cache()
    try:
        assert cls._resolve_ocr_model() == "registry-qwen3-vl:8b"
    finally:
        model_roles.clear_model_role_cache()


class _FakePage:
    def __init__(self, index: int, data: bytes):
        self.index = index
        self.png_bytes = data
        self.enhanced = False


@pytest.mark.asyncio
async def test_ocr_pages_uses_primary_response(monkeypatch):
    async def fake_vision(model, b64):
        return ("NOMOR POKOK WAJIB PAJAK", "")  # response present

    monkeypatch.setattr(cls, "_ollama_vision", fake_vision)
    out = await cls.ocr_pages([_FakePage(0, b"x")])
    assert out[0]["via"] == "response"
    assert "WAJIB PAJAK" in out[0]["text"]
    assert out[0]["confidence"] > 0.0


@pytest.mark.asyncio
async def test_ocr_pages_unwraps_json_line_list_response(monkeypatch):
    async def fake_vision(model, b64):
        return ('["PASSPORT / PASPOR", "Passport No: YA1234567"]', "")

    monkeypatch.setattr(cls, "_ollama_vision", fake_vision)
    out = await cls.ocr_pages([_FakePage(0, b"x")])
    assert out[0]["via"] == "response"
    assert out[0]["text"] == "PASSPORT / PASPOR\nPassport No: YA1234567"


@pytest.mark.asyncio
async def test_ocr_pages_unwraps_fenced_json_line_list_response(monkeypatch):
    async def fake_vision(model, b64):
        return ('```json\n["VISA INDEX : E33G", "Expiry Date : 2026-12-24"]\n```', "")

    monkeypatch.setattr(cls, "_ollama_vision", fake_vision)
    out = await cls.ocr_pages([_FakePage(0, b"x")])
    assert out[0]["via"] == "response"
    assert out[0]["text"] == "VISA INDEX : E33G\nExpiry Date : 2026-12-24"


@pytest.mark.asyncio
async def test_ocr_pages_unwraps_json_line_object_list_response(monkeypatch):
    async def fake_vision(model, b64):
        return (
            '[{"text": "Passport No: YA1234567"}, {"line": "Name : MARIO LUCA ROSSI"}]',
            "",
        )

    monkeypatch.setattr(cls, "_ollama_vision", fake_vision)
    out = await cls.ocr_pages([_FakePage(0, b"x")])
    assert out[0]["via"] == "response"
    assert out[0]["text"] == "Passport No: YA1234567\nName : MARIO LUCA ROSSI"


@pytest.mark.asyncio
async def test_ocr_pages_unwraps_json_text_object_response(monkeypatch):
    async def fake_vision(model, b64):
        return ('{"text": "PAYMENT RECEIPT\\nReceipt No : TRX-2026-00077"}', "")

    monkeypatch.setattr(cls, "_ollama_vision", fake_vision)
    out = await cls.ocr_pages([_FakePage(0, b"x")])
    assert out[0]["via"] == "response"
    assert out[0]["text"] == "PAYMENT RECEIPT\nReceipt No : TRX-2026-00077"


@pytest.mark.asyncio
async def test_ocr_pages_unwraps_json_pages_object_response(monkeypatch):
    async def fake_vision(model, b64):
        return (
            '{"pages": [{"text": "KITAS No : 2C11AB98765"}, '
            '{"text": "Name : MARIO LUCA ROSSI"}]}',
            "",
        )

    monkeypatch.setattr(cls, "_ollama_vision", fake_vision)
    out = await cls.ocr_pages([_FakePage(0, b"x")])
    assert out[0]["via"] == "response"
    assert out[0]["text"] == "KITAS No : 2C11AB98765\nName : MARIO LUCA ROSSI"


@pytest.mark.asyncio
async def test_ocr_pages_salvages_thinking_when_response_empty(monkeypatch):
    async def fake_vision(model, b64):
        # qwen3-vl pattern: empty response, transcription buried in thinking.
        return ("", "Got it, let's transcribe the text: KARTU TANDA PENDUDUK NIK 3201")

    monkeypatch.setattr(cls, "_ollama_vision", fake_vision)
    out = await cls.ocr_pages([_FakePage(0, b"x")])
    assert out[0]["via"] == "thinking"
    assert "TANDA PENDUDUK" in out[0]["text"]


@pytest.mark.asyncio
async def test_ocr_pages_same_model_retry_rescues_page(monkeypatch):
    """Antibody #10 (2026-06-13): with primary == fallback (today's topology)
    the cascade is a same-model RETRY — kept deliberately because live logs
    show a second attempt rescues pages that returned empty once. Distinguish
    by call COUNT, not model name."""
    calls = []

    async def fake_vision(model, b64):
        calls.append(model)
        if len(calls) == 1:
            return ("", "")  # first attempt yields nothing usable
        return ("KEMENTERIAN KEUANGAN", "")  # retry succeeds

    monkeypatch.setattr(cls, "_resolve_ocr_model", lambda: cls._OCR_FALLBACK)
    monkeypatch.setattr(cls, "_ollama_vision", fake_vision)
    out = await cls.ocr_pages([_FakePage(0, b"x")])
    assert out[0]["via"] == "fallback"
    assert out[0]["model"] == cls._OCR_FALLBACK
    assert calls == [cls._OCR_FALLBACK, cls._OCR_FALLBACK]


@pytest.mark.asyncio
async def test_ocr_pages_cascades_to_fallback_across_models(monkeypatch):
    """Cross-model cascade still works when the topology points the primary
    at a different (e.g. experimental reasoning) VLM."""
    calls = []

    async def fake_vision(model, b64):
        calls.append(model)
        if model == "experimental-vlm:test":
            return ("", "")  # primary yields nothing usable
        return ("KEMENTERIAN KEUANGAN", "")  # fallback succeeds

    monkeypatch.setattr(cls, "_resolve_ocr_model", lambda: "experimental-vlm:test")
    monkeypatch.setattr(cls, "_ollama_vision", fake_vision)
    out = await cls.ocr_pages([_FakePage(0, b"x")])
    assert out[0]["via"] == "fallback"
    assert out[0]["model"] == cls._OCR_FALLBACK
    assert calls == ["experimental-vlm:test", cls._OCR_FALLBACK]


@pytest.mark.asyncio
async def test_ocr_pages_unreadable_yields_empty_not_invented(monkeypatch):
    async def fake_vision(model, b64):
        return ("", "")  # both primary and fallback see nothing

    monkeypatch.setattr(cls, "_ollama_vision", fake_vision)
    out = await cls.ocr_pages([_FakePage(0, b"x")])
    assert out[0]["text"] == ""
    assert out[0]["confidence"] == 0.0
    assert out[0]["via"] == "empty"


# ---------------------------------------------------------------------------
# ocr_pages -- optional cloud OCR routing (Gemini primary, Ollama fallback)
# ---------------------------------------------------------------------------


def test_intake_ocr_provider_defaults_to_ollama(monkeypatch):
    monkeypatch.delenv("INTAKE_OCR_PROVIDER", raising=False)
    assert cls._ocr_provider() == "ollama"


@pytest.mark.asyncio
async def test_gemini_vision_uses_genai_client_inline_image(monkeypatch):
    calls = []

    class _FakeGenAIClient:
        is_available = True

        async def generate_content(self, **kwargs):
            calls.append(kwargs)
            return {"text": '{"text": "PASSPORT\\nPassport No YA1234567"}'}

    monkeypatch.setattr(
        "backend.llm.genai_client.get_genai_client",
        lambda: _FakeGenAIClient(),
    )

    out = await cls._gemini_vision("Zm9v", prompt="OCR PROMPT", num_predict=77)

    assert out == "PASSPORT\nPassport No YA1234567"
    assert calls[0]["model"] == cls._GEMINI_OCR_MODEL
    assert calls[0]["max_output_tokens"] == 77
    assert calls[0]["temperature"] == 0.0
    assert calls[0]["endpoint"] == "intake_ocr"
    assert calls[0]["contents"] == [
        {"text": "OCR PROMPT"},
        {"inline_data": {"mime_type": "image/png", "data": "Zm9v"}},
    ]


@pytest.mark.asyncio
async def test_ocr_pages_uses_gemini_primary_when_enabled_and_allowed(monkeypatch):
    async def fake_gemini(b64):
        return "PASSPORT\nPassport No YA1234567"

    async def fail_ollama(model, b64):
        raise AssertionError("Ollama must not run when Gemini primary succeeds")

    monkeypatch.setenv("INTAKE_OCR_PROVIDER", "gemini")
    monkeypatch.setattr(cls, "_GEMINI_OCR_AUTH_FAILED", False)
    monkeypatch.setattr(cls, "_cloud_vision_allowed", lambda: True)
    monkeypatch.setattr(cls, "_gemini_vision", fake_gemini)
    monkeypatch.setattr(cls, "_ollama_vision", fail_ollama)

    out = await cls.ocr_pages([_FakePage(0, b"x")])

    assert out[0]["via"] == "gemini"
    assert out[0]["model"] == cls._GEMINI_OCR_MODEL
    assert out[0]["text"] == "PASSPORT\nPassport No YA1234567"


@pytest.mark.asyncio
async def test_ocr_pages_blocks_gemini_when_gate_denies_then_uses_ollama(monkeypatch):
    calls = []

    async def fail_gemini(b64):
        raise AssertionError("Gemini must not run when cloud gate denies")

    async def fake_ollama(model, b64):
        calls.append(model)
        return ("NOMOR POKOK WAJIB PAJAK", "")

    monkeypatch.setenv("INTAKE_OCR_PROVIDER", "gemini")
    monkeypatch.setattr(cls, "_GEMINI_OCR_AUTH_FAILED", False)
    monkeypatch.setattr(cls, "_cloud_vision_allowed", lambda: False)
    monkeypatch.setattr(cls, "_note_cloud_ocr_blocked", lambda context: calls.append(context))
    monkeypatch.setattr(cls, "_gemini_vision", fail_gemini)
    monkeypatch.setattr(cls, "_ollama_vision", fake_ollama)

    out = await cls.ocr_pages([_FakePage(0, b"x")])

    assert out[0]["via"] == "response"
    assert out[0]["model"] == cls._OCR_FALLBACK
    assert out[0]["text"] == "NOMOR POKOK WAJIB PAJAK"
    assert calls[0] == "intake.classify.ocr_pages"
    assert calls[1:] == [cls._OCR_FALLBACK]


@pytest.mark.asyncio
async def test_ocr_pages_gemini_empty_falls_back_to_ollama(monkeypatch):
    calls = []

    async def fake_gemini(b64):
        calls.append("gemini")
        return ""

    async def fake_ollama(model, b64):
        calls.append(model)
        return ("IZIN TINGGAL TERBATAS", "")

    monkeypatch.setenv("INTAKE_OCR_PROVIDER", "gemini")
    monkeypatch.setattr(cls, "_GEMINI_OCR_AUTH_FAILED", False)
    monkeypatch.setattr(cls, "_cloud_vision_allowed", lambda: True)
    monkeypatch.setattr(cls, "_gemini_vision", fake_gemini)
    monkeypatch.setattr(cls, "_ollama_vision", fake_ollama)

    out = await cls.ocr_pages([_FakePage(0, b"x")])

    assert out[0]["via"] == "response"
    assert out[0]["model"] == cls._OCR_FALLBACK
    assert out[0]["text"] == "IZIN TINGGAL TERBATAS"
    assert calls == ["gemini", cls._OCR_FALLBACK]


@pytest.mark.asyncio
async def test_ocr_pages_disables_gemini_after_auth_failure(monkeypatch):
    calls = []

    async def fail_gemini(b64):
        calls.append("gemini")
        raise RuntimeError("403 PERMISSION_DENIED API key was reported as leaked")

    async def fake_ollama(model, b64):
        calls.append(model)
        return ("PASSPORT", "")

    monkeypatch.setenv("INTAKE_OCR_PROVIDER", "gemini")
    monkeypatch.setattr(cls, "_GEMINI_OCR_AUTH_FAILED", False)
    monkeypatch.setattr(cls, "_cloud_vision_allowed", lambda: True)
    monkeypatch.setattr(cls, "_gemini_vision", fail_gemini)
    monkeypatch.setattr(cls, "_ollama_vision", fake_ollama)

    out = await cls.ocr_pages([_FakePage(0, b"x"), _FakePage(1, b"y")])

    assert [page["via"] for page in out] == ["response", "response"]
    assert calls == ["gemini", cls._OCR_FALLBACK, cls._OCR_FALLBACK]


# ---------------------------------------------------------------------------
# preprocess -- mime detection (no model)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preprocess_detects_png_and_returns_page(tmp_path):
    from PIL import Image

    p = tmp_path / "doc.png"
    Image.new("RGB", (200, 100), "white").save(p, format="PNG")
    r = await pre.preprocess_blob(str(p))
    assert r.mime == "image/png"
    assert r.n_pages == 1
    assert r.pages[0].png_bytes


@pytest.mark.asyncio
async def test_preprocess_missing_file_graceful():
    r = await pre.preprocess_blob("/nonexistent/path/blob.pdf")
    assert r.n_pages == 0
    assert r.notes and "read_failed" in r.notes


# ---------------------------------------------------------------------------
# Cloud OCR guard (local default, explicit opt-in only)
# ---------------------------------------------------------------------------

_SOURCE_FILES = [
    Path(cls.__file__),
    Path(pre.__file__),
]
_BANNED_CLOUD_TOKENS = re.compile(r"openai|anthropic|googleapis", re.IGNORECASE)


def test_intake_source_uses_cloud_only_through_gate():
    """Intake may contain Gemini OCR, but not an ungated raw cloud endpoint.

    The old contract was strict-local source only. The new contract is narrower
    and explicit: default provider remains Ollama, and any Gemini path must go
    through the shared cloud_vision_gate helper rather than a raw HTTP endpoint.
    """
    for f in _SOURCE_FILES:
        text = f.read_text()
        for lineno, line in enumerate(text.splitlines(), 1):
            m = _BANNED_CLOUD_TOKENS.search(line)
            assert m is None, f"raw cloud token '{m.group(0)}' in {f.name}:{lineno}: {line.strip()}"
    assert cls._ocr_provider() == "ollama"
    src = Path(cls.__file__).read_text()
    assert "_cloud_vision_allowed" in src
    assert "_note_cloud_ocr_blocked" in src


# ---------------------------------------------------------------------------
# Antibody Debt #10 (2026-06-13) -- OCR primary model invariants
# ---------------------------------------------------------------------------


def test_ocr_primary_default_invariant():
    """CLAUDE.md S9: vision = qwen2.5vl:7b ONLY. Until 2026-06-13 the
    hardcoded default was qwen3-vl:8b, so a missing/unreadable
    MODEL_TOPOLOGY.json silently resurrected the documented-broken primary
    (empty response, thinking-leak; the 2026-06-12 backlog run poisoned
    782/812 review_pending proposals -- PR #1359). Do NOT flip this back
    without re-reading the HISTORY section in classify.py."""
    assert cls._OCR_PRIMARY_DEFAULT == "qwen2.5vl:7b"
    assert cls._OCR_FALLBACK == "qwen2.5vl:7b"


def test_topology_ocr_vision_role_matches_invariant():
    """MODEL_TOPOLOGY.json (the runtime source for the ocr_vision role) must
    agree with the S9 invariant -- guards a config-side regression that the
    hardcoded-default test above cannot see."""
    topo = json.loads(model_roles._topology_path().read_text())
    assert topo["roles"]["ocr_vision"] == "qwen2.5vl:7b"
