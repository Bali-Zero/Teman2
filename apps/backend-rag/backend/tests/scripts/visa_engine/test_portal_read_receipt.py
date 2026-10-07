"""portal_read_receipt.py — the mechanical half of "write the ledger during the reading".

No network: ``fetch`` is monkeypatched. What is tested is the receipt's shape and
the three judgements the tool makes on its own (visible text, key phrase,
fingerprint), each with a guilt twin.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.scripts.visa_engine import portal_read_receipt as prr

E31B = {
    "source_record_id": "570f2bc4-5120-561f-90ba-58fcd9507514",
    "source_key": "imigrasi.go.id.e31b.daftar-visa-indonesia",
    "canonical_url": "https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31B",
    "authority_type": "OFFICIAL_PORTAL",
    "title": "Visa Keluarga Suami/Istri Pemegang ITAS/ITAP (E31B) — Direktorat Jenderal Imigrasi",
}
VOA_LIST = {
    "source_record_id": "38a6cb08-041f-51e4-86e4-9e73243acd3a",
    "source_key": "imigrasi-voa-country-list",
    "canonical_url": "https://www.imigrasi.go.id/wna/x",
    "authority_type": "OFFICIAL_PORTAL",
    "title": "Daftar Negara Subjek Visa on Arrival (VoA) — Direktorat Jenderal Imigrasi",
}
CSRF = "a" * 20 + "B" * 20
PAGE = (
    "<html><head><title>WNA</title><meta name='csrf-token' content='" + CSRF + "'>"
    "<script>var t='" + CSRF + "';</script><style>.x{}</style></head><body>"
    "<h1>E31B Visa Keluarga Suami/Istri Pemegang ITAS/ITAP</h1>"
    "<p>Anda dapat memilih untuk tinggal di Indonesia selama 1 tahun atau 2 tahun.</p>"
    "<!-- comment --><div>" + CSRF + "</div></body></html>"
)


class TestVisibleText:
    def test_strips_markup_scripts_styles_and_comments(self) -> None:
        text = prr.visible_text(PAGE)
        assert "E31B Visa Keluarga Suami/Istri Pemegang ITAS/ITAP" in text
        assert "selama 1 tahun atau 2 tahun" in text
        assert "var t=" not in text
        assert ".x{}" not in text
        assert "comment" not in text
        assert "<" not in text

    def test_guilt_raw_html_is_not_visible_text(self) -> None:
        assert prr.visible_text(PAGE) != PAGE


class TestKeyPhrase:
    def test_visa_pages_key_on_their_code(self) -> None:
        assert prr.key_phrase(E31B) == "E31B"

    def test_pinned_pages_key_on_the_served_heading_not_the_catalogue_title(self) -> None:
        assert prr.key_phrase(VOA_LIST) == "Daftar Subjek Visa on Arrival"

    def test_guilt_an_unpinned_label_page_falls_back_to_its_title_name(self) -> None:
        record = {**VOA_LIST, "source_key": "something-else"}
        assert prr.key_phrase(record) == "Daftar Negara Subjek Visa on Arrival (VoA)"

    def test_every_pinned_key_names_a_real_source_key_shape(self) -> None:
        for source_key, phrase in prr.KEY_PHRASE_BY_SOURCE_KEY.items():
            assert source_key.startswith("imigrasi")
            assert len(phrase) >= 12


class TestFingerprint:
    def test_the_csrf_token_does_not_move_the_fingerprint(self) -> None:
        with_token = prr.visible_text(PAGE)
        without_token = with_token.replace(CSRF, "")
        assert prr.fingerprint(with_token) == prr.fingerprint(without_token)

    def test_guilt_content_moves_the_fingerprint(self) -> None:
        text = prr.visible_text(PAGE)
        assert prr.fingerprint(text) != prr.fingerprint(text.replace("2 tahun", "3 tahun"))


class TestReadOne:
    def test_a_200_with_the_phrase_writes_text_and_a_complete_receipt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(prr, "fetch", lambda url: (200, PAGE.encode(), url))
        receipt = prr.read_one(E31B, reader="reader-x", text_dir=tmp_path)
        assert receipt["http_status"] == 200
        assert receipt["key_phrase"] == "E31B"
        assert receipt["key_phrase_found"] is True
        assert receipt["reader"] == "reader-x"
        assert receipt["fetched_at"].endswith("Z")
        saved = Path(receipt["text_file"])
        assert saved == tmp_path / "570f2bc4.txt"
        assert "selama 1 tahun atau 2 tahun" in saved.read_text(encoding="utf-8")
        assert receipt["visible_text_sha256"] == prr.fingerprint(saved.read_text(encoding="utf-8").rstrip("\n"))
        assert "E31B" in receipt["key_phrase_context"]
        json.dumps(receipt)

    def test_guilt_a_page_without_the_phrase_is_a_check_not_a_pass(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(prr, "fetch", lambda url: (200, b"<html><body>Halaman tidak ditemukan</body></html>", url))
        receipt = prr.read_one(E31B, reader="reader-x", text_dir=tmp_path)
        assert receipt["http_status"] == 200
        assert receipt["key_phrase_found"] is False
        assert receipt["key_phrase_context"] is None

    def test_guilt_a_404_is_recorded_as_a_404(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(prr, "fetch", lambda url: (404, b"", url))
        receipt = prr.read_one(E31B, reader="reader-x", text_dir=tmp_path)
        assert receipt["http_status"] == 404
        assert receipt["key_phrase_found"] is False

    def test_guilt_a_transport_error_is_recorded_not_raised(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(_url: str) -> tuple[int, bytes, str]:
            raise OSError("connection reset")

        monkeypatch.setattr(prr, "fetch", boom)
        receipt = prr.read_one(E31B, reader="reader-x", text_dir=tmp_path)
        assert receipt["http_status"] is None
        assert "connection reset" in receipt["error"]


class TestMain:
    def test_main_appends_one_receipt_per_record_and_exits_nonzero_on_a_check(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        pack = {"payload": {"source_records": [E31B, VOA_LIST, {**E31B, "source_record_id": "0" * 36, "authority_type": "REGULATION"}]}}
        pack_path = tmp_path / "pack.json"
        pack_path.write_text(json.dumps(pack), encoding="utf-8")
        monkeypatch.setattr(prr, "fetch", lambda url: (200, PAGE.encode(), url))
        out = tmp_path / "ledger"
        rc = prr.main(["--pack", str(pack_path), "--out-dir", str(out), "--reader", "reader-x", "--all"])
        lines = (out / "reader-x-receipts.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2, "REGULATION records are not portal reads"
        assert rc == 1, "the VoA list page served the E31B page: a CHECK, exit 1"
        assert "CHECK" in capsys.readouterr().out

    def test_guilt_a_prefix_matching_two_records_is_refused(self, tmp_path: Path) -> None:
        pack = {"payload": {"source_records": [E31B, {**E31B, "source_record_id": "570f2bc4-ffff-5120-561f-90ba58fcd750"}]}}
        pack_path = tmp_path / "pack.json"
        pack_path.write_text(json.dumps(pack), encoding="utf-8")
        with pytest.raises(SystemExit, match="matches 2"):
            prr.main(["--pack", str(pack_path), "--out-dir", str(tmp_path / "l"), "--reader", "r", "--ids", "570f2bc4"])
