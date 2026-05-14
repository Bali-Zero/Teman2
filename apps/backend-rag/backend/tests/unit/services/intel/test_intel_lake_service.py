"""Unit tests for IntelLakeService.

Pure logic tests — canonicalize_url is no-DB so we can test directly.
DB-backed tests live in tests/integration/ (require live PG).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import pytest

from backend.services.intel.intel_lake_service import (
    MAX_RAW_PAYLOAD_BYTES,
    IntelLakeService,
    ObservationInput,
    PayloadTooLargeError,
    _parse_iso_datetime,
    canonicalize_url,
)


class _CapturingConn:
    """Fake asyncpg connection recording fetchrow/fetchval call args."""

    def __init__(self) -> None:
        self.fetchrow_calls: list[tuple[Any, ...]] = []
        self.fetchval_calls: list[tuple[Any, ...]] = []

    @asynccontextmanager
    async def transaction(self) -> Any:
        yield

    async def fetchrow(self, query: str, *args: Any) -> Any:
        self.fetchrow_calls.append((query, *args))
        # stored_hash == _make_obs content_hash so is_content_drift is
        # consistently False for a fresh item (is_new_item True).
        return {
            "id": "00000000-0000-0000-0000-000000000001",
            "is_new_item": True,
            "stored_hash": "hash123",
        }

    async def fetchval(self, query: str, *args: Any) -> Any:
        self.fetchval_calls.append((query, *args))
        return 42

    async def execute(self, query: str, *args: Any) -> None:
        pass


class _CapturingPool:
    """Fake asyncpg pool yielding a single shared _CapturingConn."""

    def __init__(self) -> None:
        self.conn = _CapturingConn()

    @asynccontextmanager
    async def acquire(self) -> Any:
        yield self.conn


def _make_obs(raw_payload: dict[str, Any] | None = None) -> ObservationInput:
    return ObservationInput(
        producer_name="test_producer",
        canonical_url="https://imigrasi.go.id/news",
        content_hash="hash123",
        title="Test item",
        summary="summary",
        source_domain="imigrasi.go.id",
        raw_payload=raw_payload,
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


class TestParseIsoDatetime:
    """Regression for 2026-05-13 — silent drop of items with published_at.

    asyncpg's timestamptz codec requires a datetime, not a string. Wave 4
    producers send ISO 8601 strings. Helper must parse them, return None
    for empty/invalid, and never raise.
    """

    def test_none_returns_none(self) -> None:
        assert _parse_iso_datetime(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert _parse_iso_datetime("") is None

    def test_iso_with_offset_parses(self) -> None:
        result = _parse_iso_datetime("2026-05-13T07:00:00+08:00")
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    def test_iso_with_z_parses(self) -> None:
        result = _parse_iso_datetime("2026-05-13T07:00:00Z")
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    def test_iso_date_only_parses(self) -> None:
        result = _parse_iso_datetime("2026-05-13")
        assert isinstance(result, datetime)
        assert result.year == 2026

    def test_invalid_returns_none(self) -> None:
        assert _parse_iso_datetime("not-a-date") is None

    def test_garbage_does_not_raise(self) -> None:
        # Defense in depth — any unparseable input must not propagate
        assert _parse_iso_datetime("\x00\xff") is None

    def test_returns_none_for_non_string_type(self) -> None:
        # Type-narrowing fallback
        assert _parse_iso_datetime(12345) is None  # type: ignore[arg-type]


class TestRawPayloadBindType:
    """Regression for 2026-05-14 — jsonb double-encoding of raw_payload.

    The asyncpg pool registers a jsonb codec with ``encoder=json.dumps``
    (``backend/app/core/database.py``). ``record_observation`` must bind
    ``raw_payload`` as a raw dict so the codec serializes it ONCE. The
    pre-fix code bound ``json.dumps(...)`` output, double-encoding it into
    a jsonb *string* scalar instead of a jsonb *object*.

    The ``raw_json`` string is still computed — but only for the 50KB
    size check, not for binding.
    """

    @staticmethod
    def _find_call(calls: list[tuple[Any, ...]], sql_marker: str) -> tuple[Any, ...]:
        """Locate the captured call whose query contains ``sql_marker``.

        Anchors assertions to a specific INSERT/UPDATE by SQL content rather
        than a fragile positional index into the calls list.
        """
        for call in calls:
            if sql_marker in call[0]:
                return call
        raise AssertionError(f"no captured call matched SQL marker {sql_marker!r}")

    @pytest.mark.asyncio
    async def test_raw_payload_bound_as_dict_in_intel_items(self) -> None:
        pool = _CapturingPool()
        svc = IntelLakeService(pool)  # type: ignore[arg-type]
        payload = {"url": "https://imigrasi.go.id/x", "extra": [1, 2, 3]}
        await svc.record_observation(_make_obs(raw_payload=payload))
        call = self._find_call(pool.conn.fetchrow_calls, "INSERT INTO intel_items")
        # args after query: canonical, hash, title, summary, domain,
        #   language, jurisdiction, topic_tags, published_at, raw_payload
        bound_raw = call[10]
        assert isinstance(bound_raw, dict), (
            f"intel_items.raw_payload bound as {type(bound_raw).__name__}, "
            f"expected dict — json.dumps + pool codec = double-encoding"
        )
        assert bound_raw == payload

    @pytest.mark.asyncio
    async def test_raw_payload_bound_as_dict_in_intel_observations(self) -> None:
        pool = _CapturingPool()
        svc = IntelLakeService(pool)  # type: ignore[arg-type]
        payload = {"k": "v"}
        await svc.record_observation(_make_obs(raw_payload=payload))
        call = self._find_call(
            pool.conn.fetchval_calls, "INSERT INTO intel_observations"
        )
        # args after query: item_id, producer_name, raw_payload, score
        bound_raw = call[3]
        assert isinstance(bound_raw, dict), (
            f"intel_observations.raw_payload bound as {type(bound_raw).__name__}, "
            f"expected dict"
        )
        assert bound_raw == payload

    @pytest.mark.asyncio
    async def test_none_raw_payload_bound_as_empty_dict(self) -> None:
        pool = _CapturingPool()
        svc = IntelLakeService(pool)  # type: ignore[arg-type]
        await svc.record_observation(_make_obs(raw_payload=None))
        call = self._find_call(pool.conn.fetchrow_calls, "INSERT INTO intel_items")
        bound_raw = call[10]
        assert bound_raw == {}
        assert isinstance(bound_raw, dict)

    @pytest.mark.asyncio
    async def test_oversize_payload_still_rejected(self) -> None:
        # Guard: the 50KB size check must survive the refactor.
        pool = _CapturingPool()
        svc = IntelLakeService(pool)  # type: ignore[arg-type]
        huge = {"blob": "x" * (MAX_RAW_PAYLOAD_BYTES + 100)}
        with pytest.raises(PayloadTooLargeError):
            await svc.record_observation(_make_obs(raw_payload=huge))
