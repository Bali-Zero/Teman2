from backend.app.routers.kbli_notebook import _payload_value
from backend.scripts.index_kbli_gold_content import build_payload as build_gold_payload
from backend.scripts.reindex_kbli_2025_final import build_payload as build_bps_payload


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


def test_gold_kbli_payload_is_flat() -> None:
    payload = build_gold_payload(
        "56210",
        {"whatItMeans": "Katering untuk acara", "tka_positions": []},
        {
            "judul": "Aktivitas Jasa Boga untuk Acara Tertentu",
            "sektor_id": "I",
            "pma_status": "TERBUKA",
        },
        embedding_text="KBLI 56210 Katering",
    )

    assert "metadata" not in payload
    assert payload["kode_kbli"] == "56210"
    assert payload["doc_type"] == "kbli_gold"
    assert payload["has_gold_content"] is True
