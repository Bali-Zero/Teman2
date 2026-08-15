from backend.app.routers.kbli_notebook import _payload_value
from backend.scripts.build_kbli_oss_twin_v3 import build_chunks
from backend.scripts.index_kbli_gold_content import (
    GOLD_CONTENT_FILE,
    KBLI_DATA_FILE,
    load_kbli_base_data,
    parse_gold_content_ts,
)
from backend.scripts.index_kbli_gold_content import (
    build_payload as build_gold_payload,
)
from backend.scripts.reindex_kbli_2025_final import (
    build_embedding_text as build_bps_embedding,
)
from backend.scripts.reindex_kbli_2025_final import (
    build_payload as build_bps_payload,
)


def test_payload_value_supports_flat_and_legacy_shapes() -> None:
    flat_payload = {"kode_kbli": "56101", "judul": "Restoran"}
    legacy_payload = {"metadata": {"kode": "56210", "judul": "Katering"}}

    assert _payload_value(flat_payload, "kode_kbli", "kode") == "56101"
    assert _payload_value(legacy_payload, "kode_kbli", "kode") == "56210"
    assert _payload_value(flat_payload, "missing", default="fallback") == "fallback"


def test_reindex_kbli_payload_is_flat() -> None:
    payload = build_bps_payload(
        {
            "kode_kbli_2025": "56101",
            "judul": "Restoran",
            "uraian": "Aktivitas penyediaan makanan.",
            "sektor_id": "I",
            "pma_status": "TERBUKA",
            "per_skala": [{"skala_usaha": ["Menengah"], "kategori_risiko": "Menengah Rendah"}],
        },
        embedding_text="KBLI 56101 Restoran",
    )

    assert "metadata" not in payload
    assert payload["kode_kbli"] == "56101"
    assert payload["judul"] == "Restoran"
    assert payload["doc_type"] == "kbli_bps"
    assert payload["kategori_risiko"] == "Menengah Rendah"
    assert payload["pma_status"] == "NOT_VERIFIED"
    assert payload["pma_max_asing"] is None
    assert payload["bali_status"] is None
    assert payload["bali_blocked"] is None
    assert payload["bali_needs_review"] is None


def test_gold_kbli_payload_is_flat() -> None:
    code = "47111"
    gold = parse_gold_content_ts(GOLD_CONTENT_FILE)[code]
    base = load_kbli_base_data(KBLI_DATA_FILE)[code]
    payload = build_gold_payload(
        code,
        gold,
        base,
        embedding_text="KBLI 47111 Perdagangan Eceran",
    )

    assert "metadata" not in payload
    assert payload["kode_kbli"] == code
    assert payload["doc_type"] == "kbli_gold"
    assert payload["has_gold_content"] is True
    assert payload["editorial_disclosed"] is True


def test_gold_kbli_payload_withholds_editorial_without_the_full_pma_tuple() -> None:
    payload = build_gold_payload(
        "56210",
        {"whatItMeans": "Katering untuk acara", "tka_positions": []},
        {
            "judul": "Aktivitas Jasa Boga untuk Acara Tertentu",
            "sektor_id": "I",
            "pma_status": "TERBUKA",
            "pma_verification_status": "declared_gap",
        },
        embedding_text="KBLI 56210 Katering",
    )

    assert payload["has_gold_content"] is False
    assert payload["editorial_disclosed"] is False
    assert payload["pma_status"] == "NOT_VERIFIED"
    assert payload["pma_max_asing"] is None
    assert payload["pma_official_basis"] is None
    assert payload["pma_source_vintage"] is None


def test_gold_kbli_payload_withholds_editorial_for_unknown_pma_status() -> None:
    payload = build_gold_payload(
        "56210",
        {"whatItMeans": "Katering untuk acara", "tka_positions": []},
        {
            "judul": "Aktivitas Jasa Boga untuk Acara Tertentu",
            "sektor_id": "I",
            "pma_status": "FUTURE_STATUS",
            "pma_verification_status": "located",
            "pma_official_basis": "Perpres 49/2021 official locator",
            "pma_source_vintage": "2021-05-25",
        },
        embedding_text="KBLI 56210 Katering",
    )

    assert payload["has_gold_content"] is False
    assert payload["editorial_disclosed"] is False


def test_oss_twin_withholds_pma_and_bali_claims_for_a_declared_gap() -> None:
    chunks = build_chunks(
        {
            "kode_kbli_2025": "01111",
            "judul": "Pertanian Jagung",
            "uraian": "Official BPS description",
            "pma_status": "TERBUKA",
            "pma_max_asing": 100,
            "pma_verification_status": "declared_gap",
            "l4_bali": {
                "status": "OK_or_HIGHER_RISK",
                "blocked": False,
                "needs_review": False,
                "reason": "UNSAFE_BALI_REASON",
            },
            "per_skala": [{"skala_usaha": ["Besar"]}],
        }
    )

    assert chunks
    for chunk in chunks:
        assert chunk["metadata"]["pma_status"] == "NOT_VERIFIED"
        assert chunk["metadata"]["pma_max_asing"] is None
        assert chunk["metadata"]["bali_status"] is None
        assert chunk["metadata"]["bali_blocked"] is None
        assert "TERBUKA" not in chunk["text"]
        assert "100%" not in chunk["text"]
        assert "OK_or_HIGHER_RISK" not in chunk["text"]
        assert "UNSAFE_BALI_REASON" not in chunk["text"]


def _located_with_bali(*, blocked: object, needs_review: object = False) -> dict:
    return {
        "kode_kbli_2025": "86995",
        "judul": "Aktivitas Pelayanan Kesehatan",
        "uraian": "Official BPS description",
        "pma_status": "TERBUKA",
        "pma_max_asing": 100,
        "pma_verification_status": "located",
        "pma_official_basis": "Perpres 49/2021 official locator",
        "pma_source_vintage": "2021-05-25",
        "pma_cap_verified": True,
        "l4_bali": {
            "status": "CHIUSO_MORATORIA_BALI",
            "blocked": blocked,
            "needs_review": needs_review,
            "reason": "UNSAFE_BALI_REASON",
        },
        "per_skala": [{"skala_usaha": ["Besar"]}],
    }


def test_reindex_never_coerces_a_string_bali_blocked_value() -> None:
    entry = _located_with_bali(blocked="false")

    payload = build_bps_payload(entry, embedding_text="KBLI 86995")

    assert payload["bali_status"] is None
    assert payload["bali_blocked"] is None
    assert payload["bali_needs_review"] is None
    assert payload["bali_reason"] == ""
    assert payload["has_bali_l4"] is False


def test_oss_twin_never_coerces_a_string_bali_blocked_value() -> None:
    chunks = build_chunks(_located_with_bali(blocked="false"))

    assert chunks
    for chunk in chunks:
        assert chunk["metadata"]["bali_status"] is None
        assert chunk["metadata"]["bali_blocked"] is None
        assert chunk["metadata"]["bali_needs_review"] is None
        assert chunk["metadata"]["has_bali_l4"] is False
        assert "CHIUSO_MORATORIA_BALI" not in chunk["text"]
        assert "UNSAFE_BALI_REASON" not in chunk["text"]


def test_verified_code_without_bali_evidence_stays_neutral_not_open() -> None:
    entry = _located_with_bali(blocked=False)
    entry.pop("l4_bali")

    payload = build_bps_payload(entry, embedding_text="KBLI 86995")
    chunks = build_chunks(entry)

    assert payload["bali_status"] is None
    assert payload["bali_blocked"] is None
    assert payload["has_bali_l4"] is False
    assert all(chunk["metadata"]["bali_blocked"] is None for chunk in chunks)


def test_all_builders_reject_a_string_bali_review_flag() -> None:
    entry = _located_with_bali(blocked=True, needs_review="false")

    payload = build_bps_payload(entry, embedding_text="KBLI 86995")
    chunks = build_chunks(entry)

    assert payload["bali_status"] is None
    assert payload["bali_needs_review"] is None
    assert payload["has_bali_l4"] is False
    assert all(chunk["metadata"]["bali_needs_review"] is None for chunk in chunks)
    assert all(chunk["metadata"]["has_bali_l4"] is False for chunk in chunks)


def test_oss_twin_does_not_hardcode_an_open_national_status_in_bali_guidance() -> None:
    entry = _located_with_bali(blocked=False)
    entry["pma_status"] = "TERBATAS"
    entry["pma_max_asing"] = 49

    chunks = build_chunks(entry)

    assert chunks
    for chunk in chunks:
        assert "Nasional bisa TERBUKA 100%" not in chunk["text"]
        assert "Status nasional dan verdict Bali adalah lapisan terpisah" in chunk["text"]


def test_special_cap_never_receives_a_percentage_suffix_in_index_text() -> None:
    entry = _located_with_bali(blocked=False)
    entry["pma_status"] = "TERBATAS"
    entry["pma_max_asing"] = "special"
    entry["pma_cap_special"] = True

    embedding = build_bps_embedding(entry)
    chunks = build_chunks(entry)

    assert "Kepemilikan asing: kondisi khusus non-persentase" in embedding
    assert all("special non-percentage conditions" in chunk["text"] for chunk in chunks[1:])
    assert "special%" not in embedding
    assert all("special%" not in chunk["text"] for chunk in chunks)


def test_reindex_text_does_not_republish_malformed_cap_or_auxiliary_fields() -> None:
    entry = _located_with_bali(blocked=False)
    entry.update(
        {
            "pma_max_asing": "67",
            "pma_kondisi": {"unsafe": "RAW_CONDITION"},
            "pma_prioritas": "true",
            "pma_nota": ["RAW_NOTE"],
        }
    )

    embedding = build_bps_embedding(entry)

    assert "67" not in embedding
    assert "RAW_CONDITION" not in embedding
    assert "Prioritas" not in embedding
    assert "RAW_NOTE" not in embedding
