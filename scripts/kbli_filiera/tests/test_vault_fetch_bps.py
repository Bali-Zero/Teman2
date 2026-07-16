"""Unit tests for scripts/kbli_filiera/vault_fetch_bps.py — pure logic +
local-file I/O only, no network (this compiler never fetches over HTTP)."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from kbli_filiera import vault_common as common  # noqa: E402
from kbli_filiera import vault_fetch_bps as bps  # noqa: E402


class TestValidateSourceUrl:
    def test_official_id_url_accepted(self):
        assert bps.validate_source_url(bps.OFFICIAL_URLS[0]) is True

    def test_official_en_url_accepted(self):
        assert bps.validate_source_url(bps.OFFICIAL_URLS[1]) is True

    def test_en_url_has_the_live_probed_triple_dash_slug(self):
        # Pin the exact live-probed (2026-07-16, vault-scout) EN slug:
        # "2020---kbli" is a TRIPLE dash, not a typo — a gate review caught
        # an earlier single-dash version of this constant that would have
        # refused the real page (guard-over-match, cicatrix superscar #3).
        assert "tabel-konversi-kbli-2020---kbli-2025.html" in bps.OFFICIAL_URLS[1]

    def test_single_dash_en_lookalike_is_correctly_refused(self):
        # Plausible fetch typo AND a plausible phishing-style lookalike of
        # the real (triple-dash) EN URL — refusing it is correct behavior,
        # pinned so it can never silently start being accepted.
        single_dash_lookalike = (
            "https://www.bps.go.id/en/publication/2026/04/22/909d503355d2b7664e43dea8/"
            "tabel-konversi-kbli-2020-kbli-2025.html"
        )
        assert single_dash_lookalike != bps.OFFICIAL_URLS[1]
        assert bps.validate_source_url(single_dash_lookalike) is False

    def test_third_party_mirror_rejected(self):
        assert bps.validate_source_url("https://some-mirror.example.com/tabel-konversi.pdf") is False

    def test_lookalike_url_rejected(self):
        # A near-identical URL (trailing slash, different scheme) is still
        # NOT one of the two exact official strings — no fuzzy matching.
        assert bps.validate_source_url(bps.OFFICIAL_URLS[0] + "/") is False
        assert bps.validate_source_url(bps.OFFICIAL_URLS[0].replace("https", "http")) is False

    def test_empty_string_rejected(self):
        assert bps.validate_source_url("") is False


class TestRegister:
    def test_register_copies_file_and_appends_log(self, tmp_path):
        src = tmp_path / "downloads" / "tabel-konversi.pdf"
        src.parent.mkdir(parents=True)
        src.write_bytes(b"%PDF fake bps table")
        vault_root = tmp_path / "vault"

        rec = bps.register(vault_root, src, bps.OFFICIAL_URLS[0], fetched_at="2026-07-16T00:00:00Z")

        dest = vault_root / "bps" / "tabel-konversi.pdf"
        assert dest.exists()
        assert dest.read_bytes() == src.read_bytes()
        assert rec["sha256"] == common.sha256_bytes(src.read_bytes())
        assert rec["fetched_via"] == "browser-manual"
        assert rec["source_url"] == bps.OFFICIAL_URLS[0]
        assert rec["rel_path"] == "bps/tabel-konversi.pdf"

        logged = common.read_jsonl(vault_root / "bps" / "fetch-log.jsonl")
        assert logged == [rec]

    def test_register_refuses_third_party_mirror(self, tmp_path):
        src = tmp_path / "x.pdf"
        src.write_bytes(b"data")
        with pytest.raises(ValueError, match="no silent mirrors"):
            bps.register(tmp_path / "vault", src, "https://mirror.example.com/x.pdf")

    def test_register_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            bps.register(tmp_path / "vault", tmp_path / "does-not-exist.pdf", bps.OFFICIAL_URLS[0])


class TestInstructions:
    def test_mentions_both_official_urls(self):
        text = bps.instructions()
        assert bps.OFFICIAL_URLS[0] in text
        assert bps.OFFICIAL_URLS[1] in text

    def test_mentions_register_flag(self):
        assert "--register" in bps.instructions()


class TestBuildBpsRecord:
    def test_shape(self, tmp_path):
        vault_root = tmp_path / "vault"
        dest = vault_root / "bps" / "x.pdf"
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"data")
        rec = bps.build_bps_record(dest, vault_root, bps.OFFICIAL_URLS[0], b"data", "2026-07-16T00:00:00Z")
        assert rec["http_status"] == 200
        assert rec["fetched_via"] == "browser-manual"
        assert rec["bytes"] == 4
        assert rec["rel_path"] == "bps/x.pdf"
