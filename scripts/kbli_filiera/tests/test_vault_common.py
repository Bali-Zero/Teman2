"""Unit tests for scripts/kbli_filiera/vault_common.py — pure logic only,
no network (mirrors the repo convention in scripts/wr2_html_renderer/tests/:
sys.path insert of scripts/ + package import)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from kbli_filiera import vault_common as common  # noqa: E402


# ---------------------------------------------------------------------------
# Content-Disposition filename parsing
# ---------------------------------------------------------------------------

class TestParseContentDispositionFilename:
    def test_quoted_filename(self):
        header = 'attachment; filename="2.6g Lampiran I.F Sektor (I.F.4501-5248).pdf"'
        assert common.parse_content_disposition_filename(header) == (
            "2.6g Lampiran I.F Sektor (I.F.4501-5248).pdf"
        )

    def test_rfc5987_star_filename(self):
        header = "attachment; filename*=UTF-8''2.6g%20Lampiran%20I.F.pdf"
        assert common.parse_content_disposition_filename(header) == "2.6g Lampiran I.F.pdf"

    def test_star_takes_priority_over_plain(self):
        header = 'attachment; filename="fallback.pdf"; filename*=UTF-8\'\'real%20name.pdf'
        assert common.parse_content_disposition_filename(header) == "real name.pdf"

    def test_bare_unquoted_filename(self):
        header = "attachment; filename=plain.pdf"
        assert common.parse_content_disposition_filename(header) == "plain.pdf"

    def test_missing_header_returns_none(self):
        assert common.parse_content_disposition_filename(None) is None
        assert common.parse_content_disposition_filename("") is None

    def test_header_without_filename_returns_none(self):
        assert common.parse_content_disposition_filename("attachment") is None


# ---------------------------------------------------------------------------
# PP28 lampiran filename structural parse
# ---------------------------------------------------------------------------

class TestParsePp28LampiranFilename:
    def test_fragment_letter_range(self):
        # The grounded fact from the live probe (2026-07-16): a single
        # lampiran LETTER spans multiple sequential BPK ids.
        filename = "2.6g Lampiran I.F Sektor Pariwisata (I.F.4501-5248).pdf"
        result = common.parse_pp28_lampiran_filename(filename)
        assert result == {"fragment": "2.6g", "letter": "I.F", "range": "4501-5248"}

    def test_letter_without_sub_letter(self):
        filename = "2.1 Lampiran I Sektor ESDM (I.1-4500).pdf"
        result = common.parse_pp28_lampiran_filename(filename)
        assert result["fragment"] == "2.1"
        assert result["letter"] == "I"
        assert result["range"] == "1-4500"

    def test_no_range_present(self):
        filename = "2.19 Lampiran IV Ketentuan Umum.pdf"
        result = common.parse_pp28_lampiran_filename(filename)
        assert result["fragment"] == "2.19"
        assert result["letter"] == "IV"
        assert result["range"] is None

    def test_unparseable_filename_returns_all_none(self):
        result = common.parse_pp28_lampiran_filename("random-file-name.pdf")
        assert result == {"fragment": None, "letter": None, "range": None}

    def test_never_raises_on_empty_string(self):
        result = common.parse_pp28_lampiran_filename("")
        assert result == {"fragment": None, "letter": None, "range": None}


# ---------------------------------------------------------------------------
# Idempotent resume decision
# ---------------------------------------------------------------------------

class TestDecideResume:
    def test_no_prior_record_refetches(self, tmp_path):
        target = tmp_path / "some.pdf"
        assert common.decide_resume(None, target) == "refetch"

    def test_prior_not_200_refetches(self, tmp_path):
        target = tmp_path / "some.pdf"
        target.write_bytes(b"data")
        prior = {"http_status": 404, "bytes": 4, "sha256": common.sha256_bytes(b"data")}
        assert common.decide_resume(prior, target) == "refetch"

    def test_missing_file_refetches(self, tmp_path):
        target = tmp_path / "missing.pdf"
        prior = {"http_status": 200, "bytes": 4, "sha256": "deadbeef"}
        assert common.decide_resume(prior, target) == "refetch"

    def test_matching_size_and_sha256_skips(self, tmp_path):
        data = b"hello vault"
        target = tmp_path / "match.pdf"
        target.write_bytes(data)
        prior = {"http_status": 200, "bytes": len(data), "sha256": common.sha256_bytes(data)}
        assert common.decide_resume(prior, target) == "skip"

    def test_size_mismatch_refetches(self, tmp_path):
        data = b"hello vault"
        target = tmp_path / "sizemismatch.pdf"
        target.write_bytes(data)
        prior = {"http_status": 200, "bytes": len(data) + 1, "sha256": common.sha256_bytes(data)}
        assert common.decide_resume(prior, target) == "refetch"

    def test_sha256_mismatch_refetches_even_with_matching_size(self, tmp_path):
        # Corrupted-on-disk case: byte count happens to match, content doesn't.
        data = b"hello vault"
        corrupted = b"HELLO VAULT"  # same length, different bytes
        assert len(data) == len(corrupted)
        target = tmp_path / "corrupted.pdf"
        target.write_bytes(corrupted)
        prior = {"http_status": 200, "bytes": len(data), "sha256": common.sha256_bytes(data)}
        assert common.decide_resume(prior, target) == "refetch"

    def test_sha256_is_reverified_from_disk_not_trusted_blindly(self, tmp_path):
        # The prior record CLAIMS a sha256 that matches the (wrong) on-disk
        # bytes would only pass if we trusted the log; decide_resume must
        # actually re-hash the file.
        target = tmp_path / "trust.pdf"
        target.write_bytes(b"real content")
        wrong_hash_prior = {
            "http_status": 200,
            "bytes": len(b"real content"),
            "sha256": common.sha256_bytes(b"different content entirely!!"),
        }
        assert common.decide_resume(wrong_hash_prior, target) == "refetch"


# ---------------------------------------------------------------------------
# http_get default User-Agent (live-proven 2026-07-16, Mini Batch-0 run:
# peraturan.bpk.go.id's Cloudflare 403s the default Python-urllib UA; a
# browser UA gets 200 on the identical URL/host/minute). No real network —
# urllib.request.build_opener is monkeypatched to a fake opener that just
# inspects the constructed Request's headers.
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, status=200, headers=None, body=b"{}"):
        self.status = status
        self.headers = headers or {}
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class TestHttpGetDefaultHeaders:
    def test_default_user_agent_applied_when_caller_omits_headers(self, monkeypatch):
        captured = {}

        class _FakeOpener:
            def open(self, req, timeout=None):
                captured["user_agent"] = req.get_header("User-agent")
                return _FakeResponse()

        monkeypatch.setattr(common.urllib.request, "build_opener", lambda *a, **k: _FakeOpener())
        result = common.http_get("https://peraturan.bpk.go.id/Download/394930")
        assert captured["user_agent"] == common.DEFAULT_HEADERS["User-Agent"]
        assert result.status == 200

    def test_caller_supplied_user_agent_overrides_default(self, monkeypatch):
        captured = {}

        class _FakeOpener:
            def open(self, req, timeout=None):
                captured["user_agent"] = req.get_header("User-agent")
                return _FakeResponse()

        monkeypatch.setattr(common.urllib.request, "build_opener", lambda *a, **k: _FakeOpener())
        common.http_get("https://example.com/x", headers={"User-Agent": "custom-agent/1.0"})
        assert captured["user_agent"] == "custom-agent/1.0"
        assert captured["user_agent"] != common.DEFAULT_HEADERS["User-Agent"]

    def test_existing_caller_headers_survive_the_merge(self, monkeypatch):
        # The OSS fetcher's user_key/accept headers must be unaffected by
        # the new default — this is the regression the fix must not cause.
        captured = {}

        class _FakeOpener:
            def open(self, req, timeout=None):
                # Request.get_header does an EXACT dict lookup (it does not
                # normalize its argument) — the stored key is whatever
                # str.capitalize() produced at insertion time in add_header.
                captured["user_agent"] = req.get_header("User-agent")
                captured["user_key"] = req.get_header("User_key")
                captured["accept"] = req.get_header("Accept")
                return _FakeResponse()

        monkeypatch.setattr(common.urllib.request, "build_opener", lambda *a, **k: _FakeOpener())
        common.http_get(
            "https://gw.oss.go.id/v2/portal/kbli/some-uuid",
            headers={"user_key": "abc123", "accept": "application/json"},
        )
        assert captured["user_agent"] == common.DEFAULT_HEADERS["User-Agent"]
        assert captured["user_key"] == "abc123"
        assert captured["accept"] == "application/json"


# ---------------------------------------------------------------------------
# Hashing + jsonl + filename sanitizing
# ---------------------------------------------------------------------------

class TestHashingAndJsonl:
    def test_sha256_file_matches_sha256_bytes(self, tmp_path):
        data = b"the quick brown fox"
        f = tmp_path / "x.bin"
        f.write_bytes(data)
        assert common.sha256_file(f) == common.sha256_bytes(data)

    def test_append_and_read_jsonl_roundtrip(self, tmp_path):
        log = tmp_path / "sub" / "log.jsonl"
        common.append_jsonl(log, {"a": 1})
        common.append_jsonl(log, {"a": 2})
        records = common.read_jsonl(log)
        assert records == [{"a": 1}, {"a": 2}]

    def test_read_jsonl_missing_file_returns_empty(self, tmp_path):
        assert common.read_jsonl(tmp_path / "nope.jsonl") == []

    def test_read_jsonl_skips_corrupt_lines(self, tmp_path):
        log = tmp_path / "log.jsonl"
        log.write_text('{"a": 1}\nNOT JSON\n{"a": 2}\n', encoding="utf-8")
        assert common.read_jsonl(log) == [{"a": 1}, {"a": 2}]


class TestSanitizeFilename:
    def test_keeps_readable_characters(self):
        name = "2.6g Lampiran I.F (I.F.4501-5248).pdf"
        assert common.sanitize_filename(name) == name

    def test_strips_path_separators(self):
        assert "/" not in common.sanitize_filename("a/b\\c.pdf")

    def test_collapses_whitespace(self):
        assert common.sanitize_filename("a    b.pdf") == "a b.pdf"

    def test_caps_length_preserving_extension(self):
        long_stem = "x" * 300
        result = common.sanitize_filename(f"{long_stem}.pdf", max_len=50)
        assert len(result) <= 50
        assert result.endswith(".pdf")
