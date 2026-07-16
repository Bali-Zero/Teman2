"""Tests for scripts/backfill_avatar_data_uris.py (legacy avatar data: URI backfill).

Covers, per the one-shot backfill spec:
  - the data-URI parser (valid jpeg/png/webp, malformed -> skip, unsupported
    mime -> skip) — pure, no DB/network.
  - key derivation matches the live upload_client_avatar() convention
    (client-avatar/{id}/{sha8}.{ext}) for known bytes.
  - the public URL shape.
  - the per-row flow against mocked S3 + asyncpg: happy path, upload
    failure -> row skipped not crashed, verify-readback mismatch -> failure.
  - dry-run performs ZERO writes (no put_object, no UPDATE) — the single
    most important guarantee this script makes.
  - the retry/backoff wrapper reused from _tigris (transient retries then
    succeeds, non-transient fails fast, exhausted retries raises).

House style: load the target script via importlib.util (scripts/ has no
__init__.py) — same pattern as test_lint_home_fork.py /
test_wr2_ig_publish_records.py. Loading the module triggers its own
sys.path bootstrap onto apps/backend-rag, so real backend imports
(_AVATAR_CONTENT_TYPES, _tigris) work afterwards without extra PYTHONPATH
plumbing.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "backfill_avatar_data_uris.py"
_spec = importlib.util.spec_from_file_location("backfill_avatar_data_uris", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["backfill_avatar_data_uris"] = mod
_spec.loader.exec_module(mod)  # runs the module's own sys.path bootstrap

# `backend.app.routers.crm_clients` transitively imports `backend.app.core.config`,
# whose pydantic Settings() requires JWT_SECRET_KEY/API_KEYS to be set. In a real
# invocation the operator runs from `apps/backend-rag` with `.env` in cwd (same as
# backfill_portal_profiles.py's documented usage), which pydantic-settings loads
# automatically. Under pytest (cwd = repo root, no relative .env) that doesn't
# happen — set harmless test-only defaults, same pattern as
# apps/backend-rag/backend/tests/conftest.py, so collection doesn't require real
# secrets. setdefault() only: never clobbers a real value if one is present.
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars_long")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")

# Now safe to import the real backend modules the script reuses.
from backend.app.routers.crm_clients import _AVATAR_CONTENT_TYPES  # noqa: E402
from backend.services.canva_renderer_v2 import _tigris  # noqa: E402
from botocore.exceptions import ClientError  # noqa: E402


def _data_uri(mime: str, payload: bytes) -> str:
    return f"data:{mime};base64,{base64.b64encode(payload).decode()}"


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "x"}}, "PutObject")


# --------------------------------------------------------------------------
# parse_data_uri — pure, no DB/network
# --------------------------------------------------------------------------


class TestParseDataUri:
    def test_valid_jpeg(self):
        payload = b"FAKE-JPEG-BYTES"
        parsed = mod.parse_data_uri(_data_uri("image/jpeg", payload))
        assert parsed == ("image/jpeg", payload)

    def test_valid_png(self):
        payload = b"FAKE-PNG-BYTES"
        parsed = mod.parse_data_uri(_data_uri("image/png", payload))
        assert parsed == ("image/png", payload)

    def test_valid_webp(self):
        payload = b"FAKE-WEBP-BYTES"
        parsed = mod.parse_data_uri(_data_uri("image/webp", payload))
        assert parsed == ("image/webp", payload)

    def test_mime_lowercased(self):
        payload = b"x"
        parsed = mod.parse_data_uri(_data_uri("IMAGE/JPEG", payload))
        assert parsed is not None
        assert parsed[0] == "image/jpeg"

    def test_no_comma_returns_none(self):
        assert mod.parse_data_uri("data:image/jpeg;base64") is None

    def test_bad_base64_returns_none(self):
        assert mod.parse_data_uri("data:image/jpeg;base64,%%%not-base64%%%") is None

    def test_not_a_data_uri_returns_none(self):
        assert mod.parse_data_uri("https://already-migrated.example/x.jpg") is None

    def test_empty_payload_returns_none(self):
        assert mod.parse_data_uri("data:image/jpeg;base64,") is None

    def test_unsupported_mime_still_parses_flagged_downstream(self):
        # The parser only decodes; rejecting a mime it doesn't recognise is
        # process_row's job (via the SAME content-type table the live
        # upload endpoint uses) — it must never guess a fallback extension.
        parsed = mod.parse_data_uri(_data_uri("image/gif", b"GIF89a"))
        assert parsed == ("image/gif", b"GIF89a")
        assert "image/gif" not in _AVATAR_CONTENT_TYPES


# --------------------------------------------------------------------------
# derive_key — matches upload_client_avatar()'s convention exactly
# --------------------------------------------------------------------------


class TestDeriveKey:
    def test_matches_endpoint_convention(self):
        raw = b"known-bytes-for-hash-test"
        sha8 = hashlib.sha256(raw).hexdigest()[:8]
        key = mod.derive_key(12125, raw, "jpg")
        assert key == f"client-avatar/12125/{sha8}.jpg"

    def test_different_bytes_different_key(self):
        k1 = mod.derive_key(1, b"aaa", "png")
        k2 = mod.derive_key(1, b"bbb", "png")
        assert k1 != k2

    def test_public_url_shape(self, monkeypatch):
        monkeypatch.setattr(_tigris, "PUBLIC_HOST", "test-bucket.fly.storage.tigris.dev")
        raw = b"shape-test"
        key = mod.derive_key(7, raw, "png")
        url = f"https://{_tigris.PUBLIC_HOST}/{key}"
        assert url.startswith("https://test-bucket.fly.storage.tigris.dev/client-avatar/7/")
        assert url.endswith(".png")


# --------------------------------------------------------------------------
# process_row — mocked S3 client + asyncpg connection
# --------------------------------------------------------------------------


def _fake_conn(*, fetchval_return: object = None) -> MagicMock:
    conn = MagicMock()
    conn.execute = AsyncMock(return_value="UPDATE 1")
    conn.fetchval = AsyncMock(return_value=fetchval_return)
    return conn


def _fake_s3(*, put_object_side_effect=None) -> MagicMock:
    s3 = MagicMock()
    if put_object_side_effect is not None:
        s3.put_object = MagicMock(side_effect=put_object_side_effect)
    else:
        s3.put_object = MagicMock(return_value={})
    return s3


class TestProcessRowDryRunZeroWrites:
    """The single most important guarantee: dry-run touches NEITHER Tigris
    NOR Postgres, no matter what the row looks like."""

    @pytest.mark.asyncio
    async def test_dry_run_no_put_object_no_db_write(self, monkeypatch):
        monkeypatch.setattr(_tigris, "PUBLIC_HOST", "test-bucket.fly.storage.tigris.dev")
        s3 = _fake_s3()
        conn = _fake_conn()

        result = await mod.process_row(
            client_id=12125,
            avatar_url=_data_uri("image/jpeg", b"real-looking-photo-bytes"),
            apply=False,
            content_types=_AVATAR_CONTENT_TYPES,
            tigris_mod=_tigris,
            s3=s3,
            conn=conn,
        )

        assert result.status == "would_migrate"
        assert result.url is not None and result.url.startswith("https://")
        s3.put_object.assert_not_called()
        conn.execute.assert_not_called()
        conn.fetchval.assert_not_called()

    @pytest.mark.asyncio
    async def test_dry_run_works_even_with_s3_none(self):
        # run() passes s3=None in dry-run mode (no AWS creds required at all
        # for a report-only pass) — process_row must never touch it.
        conn = _fake_conn()
        result = await mod.process_row(
            client_id=1,
            avatar_url=_data_uri("image/png", b"bytes"),
            apply=False,
            content_types=_AVATAR_CONTENT_TYPES,
            tigris_mod=_tigris,
            s3=None,
            conn=conn,
        )
        assert result.status == "would_migrate"
        conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_dry_run_malformed_row_is_reported_not_crashed(self):
        conn = _fake_conn()
        result = await mod.process_row(
            client_id=2,
            avatar_url="data:image/jpeg;base64,%%%bad%%%",
            apply=False,
            content_types=_AVATAR_CONTENT_TYPES,
            tigris_mod=_tigris,
            s3=None,
            conn=conn,
        )
        assert result.status == "skipped_malformed"
        conn.execute.assert_not_called()


class TestProcessRowApplyHappyPath:
    @pytest.mark.asyncio
    async def test_migrated(self, monkeypatch):
        monkeypatch.setattr(_tigris, "BUCKET", "test-bucket")
        monkeypatch.setattr(_tigris, "PUBLIC_HOST", "test-bucket.fly.storage.tigris.dev")
        raw = b"jpeg-bytes-for-happy-path"
        s3 = _fake_s3()
        expected_key = mod.derive_key(12125, raw, "jpg")
        expected_url = f"https://test-bucket.fly.storage.tigris.dev/{expected_key}"
        conn = _fake_conn(fetchval_return=expected_url)

        result = await mod.process_row(
            client_id=12125,
            avatar_url=_data_uri("image/jpeg", raw),
            apply=True,
            content_types=_AVATAR_CONTENT_TYPES,
            tigris_mod=_tigris,
            s3=s3,
            conn=conn,
        )

        assert result.status == "migrated"
        assert result.key == expected_key
        assert result.url == expected_url

        s3.put_object.assert_called_once()
        kwargs = s3.put_object.call_args.kwargs
        assert kwargs["Bucket"] == "test-bucket"
        assert kwargs["Key"] == expected_key
        assert kwargs["Body"] == raw
        assert kwargs["ContentType"] == "image/jpeg"
        assert kwargs["ACL"] == "public-read"

        assert conn.execute.await_args is not None
        args = conn.execute.await_args.args
        assert args[1] == expected_url
        assert args[2] == 12125


class TestProcessRowApplyUploadFailure:
    @pytest.mark.asyncio
    async def test_upload_failure_skips_row_not_crash(self, monkeypatch):
        monkeypatch.setattr(_tigris, "MAX_RETRIES", 1)  # fail fast in the test
        monkeypatch.setattr(_tigris, "PUBLIC_HOST", "test-bucket.fly.storage.tigris.dev")
        s3 = _fake_s3(put_object_side_effect=_client_error("403"))  # non-transient
        conn = _fake_conn()

        result = await mod.process_row(
            client_id=99,
            avatar_url=_data_uri("image/png", b"some-bytes"),
            apply=True,
            content_types=_AVATAR_CONTENT_TYPES,
            tigris_mod=_tigris,
            s3=s3,
            conn=conn,
        )

        assert result.status == "failed_upload"
        assert result.reason is not None
        # never crashes the batch, and never writes the DB for a failed upload
        conn.execute.assert_not_called()


class TestProcessRowApplyVerifyMismatch:
    @pytest.mark.asyncio
    async def test_verify_readback_mismatch_reported_as_failure(self, monkeypatch):
        monkeypatch.setattr(_tigris, "PUBLIC_HOST", "test-bucket.fly.storage.tigris.dev")
        s3 = _fake_s3()
        # UPDATE "succeeds" (rowcount-wise) but the readback still shows the
        # legacy data: value — must NOT be trusted as success.
        conn = _fake_conn(fetchval_return="data:image/png;base64,stillstale")

        result = await mod.process_row(
            client_id=5,
            avatar_url=_data_uri("image/png", b"bytes-here"),
            apply=True,
            content_types=_AVATAR_CONTENT_TYPES,
            tigris_mod=_tigris,
            s3=s3,
            conn=conn,
        )

        assert result.status == "failed_verify"
        s3.put_object.assert_called_once()
        conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_verify_readback_none_reported_as_failure(self, monkeypatch):
        monkeypatch.setattr(_tigris, "PUBLIC_HOST", "test-bucket.fly.storage.tigris.dev")
        s3 = _fake_s3()
        conn = _fake_conn(fetchval_return=None)

        result = await mod.process_row(
            client_id=6,
            avatar_url=_data_uri("image/jpeg", b"bytes"),
            apply=True,
            content_types=_AVATAR_CONTENT_TYPES,
            tigris_mod=_tigris,
            s3=s3,
            conn=conn,
        )
        assert result.status == "failed_verify"


class TestProcessRowUnsupportedMimeAndMalformed:
    @pytest.mark.asyncio
    async def test_unsupported_mime_never_uploads(self):
        s3 = _fake_s3()
        conn = _fake_conn()
        result = await mod.process_row(
            client_id=8,
            avatar_url=_data_uri("image/gif", b"GIF89a"),
            apply=True,
            content_types=_AVATAR_CONTENT_TYPES,
            tigris_mod=_tigris,
            s3=s3,
            conn=conn,
        )
        assert result.status == "skipped_unsupported_mime"
        s3.put_object.assert_not_called()
        conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_malformed_never_uploads_even_in_apply_mode(self):
        s3 = _fake_s3()
        conn = _fake_conn()
        result = await mod.process_row(
            client_id=9,
            avatar_url="data:image/jpeg;base64,%%%garbage%%%",
            apply=True,
            content_types=_AVATAR_CONTENT_TYPES,
            tigris_mod=_tigris,
            s3=s3,
            conn=conn,
        )
        assert result.status == "skipped_malformed"
        s3.put_object.assert_not_called()
        conn.execute.assert_not_called()


# --------------------------------------------------------------------------
# put_object_with_retry — reused _tigris retry/backoff primitives
# --------------------------------------------------------------------------


class TestPutObjectWithRetry:
    @pytest.mark.asyncio
    async def test_transient_then_success(self, monkeypatch):
        monkeypatch.setattr(_tigris, "BACKOFF_BASE_S", 0.001)
        s3 = MagicMock()
        s3.put_object = MagicMock(side_effect=[_client_error("503"), {}])

        await mod.put_object_with_retry(_tigris, s3, "k", b"body", "image/jpeg")

        assert s3.put_object.call_count == 2

    @pytest.mark.asyncio
    async def test_non_transient_fails_fast_no_retry(self):
        s3 = MagicMock()
        s3.put_object = MagicMock(side_effect=_client_error("403"))

        with pytest.raises(_tigris.TigrisError):
            await mod.put_object_with_retry(_tigris, s3, "k", b"body", "image/jpeg")

        assert s3.put_object.call_count == 1

    @pytest.mark.asyncio
    async def test_exhausted_retries_raises_tigris_error(self, monkeypatch):
        monkeypatch.setattr(_tigris, "MAX_RETRIES", 2)
        monkeypatch.setattr(_tigris, "BACKOFF_BASE_S", 0.001)
        s3 = MagicMock()
        s3.put_object = MagicMock(side_effect=_client_error("503"))

        with pytest.raises(_tigris.TigrisError):
            await mod.put_object_with_retry(_tigris, s3, "k", b"body", "image/jpeg")

        assert s3.put_object.call_count == 2


# --------------------------------------------------------------------------
# run() — DSN guard (fails loudly, never hardcodes/guesses a DSN)
# --------------------------------------------------------------------------


class TestRunDsnGuard:
    @pytest.mark.asyncio
    async def test_missing_database_url_returns_1(self, monkeypatch, tmp_path):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        rc = await mod.run(apply=False, out_path=tmp_path / "report.jsonl")
        assert rc == 1
