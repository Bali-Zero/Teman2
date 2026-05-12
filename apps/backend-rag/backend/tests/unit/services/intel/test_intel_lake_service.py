"""Unit tests for IntelLakeService.

Pure logic tests — canonicalize_url is no-DB so we can test directly.
DB-backed tests live in tests/integration/ (require live PG).
"""

from __future__ import annotations

from backend.services.intel.intel_lake_service import (
    MAX_RAW_PAYLOAD_BYTES,
    canonicalize_url,
)


class TestCanonicalizeUrl:
    def test_strips_fragment(self) -> None:
        assert canonicalize_url("https://x.com/a#section") == "https://x.com/a"

    def test_lowercases_host(self) -> None:
        assert canonicalize_url("https://EXAMPLE.com/a") == "https://example.com/a"

    def test_drops_utm_params(self) -> None:
        url = "https://x.com/a?utm_source=newsletter&utm_medium=email&keep=1"
        assert canonicalize_url(url) == "https://x.com/a?keep=1"

    def test_drops_fbclid_gclid(self) -> None:
        url = "https://x.com/a?fbclid=ABC&gclid=DEF&utm_campaign=x"
        assert canonicalize_url(url) == "https://x.com/a"

    def test_preserves_meaningful_query(self) -> None:
        url = "https://x.com/article?id=42&page=2"
        result = canonicalize_url(url)
        # order of params may shift but both must be present
        assert "id=42" in result and "page=2" in result

    def test_strips_trailing_whitespace(self) -> None:
        assert canonicalize_url("  https://x.com/a  ") == "https://x.com/a"

    def test_combined_normalization(self) -> None:
        url = "https://IMIGRASI.go.id/news?utm_source=x&utm_medium=y&id=42#frag"
        assert canonicalize_url(url) == "https://imigrasi.go.id/news?id=42"

    def test_handles_empty_path(self) -> None:
        assert canonicalize_url("https://x.com?utm_source=x") == "https://x.com"

    def test_handles_root_path(self) -> None:
        assert canonicalize_url("https://x.com/?fbclid=x") == "https://x.com/"


class TestPayloadSizeLimit:
    def test_max_payload_constant_is_50kb(self) -> None:
        assert MAX_RAW_PAYLOAD_BYTES == 50_000
