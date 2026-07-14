"""
Root conftest for all backend tests.

Sets up environment variables and shared fixtures BEFORE any module is imported.
This prevents pydantic validation errors and real API key requirements.

Shared fixtures: mock_db_pool, mock_qdrant_client, mock_redis
"""

import os
from unittest.mock import AsyncMock, MagicMock

# ============================================================================
# Environment Variables — must be set FIRST, before any import
# Covers: EmbeddingsGenerator, Settings validation, JWT, WhatsApp, Instagram
# ============================================================================

os.environ.setdefault("OPENAI_API_KEY", "sk-test-key-for-testing-only-nuzantara")
os.environ.setdefault("GOOGLE_API_KEY", "test-google-api-key")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars_long")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
# Fail closed for integration tests that historically defaulted to
# ``nuzantara_dev``.  That database carries the live local Intake/WhatsApp
# queue on Pro, so a manual pytest run must never claim or rewrite its rows.
# CI and operators can still provide an explicit isolated TEST_DATABASE_URL.
os.environ.setdefault(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_test",
)
if os.environ["TEST_DATABASE_URL"].split("?", 1)[0].rstrip("/").endswith("/nuzantara_dev"):
    raise RuntimeError(
        "Refusing to run pytest against operational nuzantara_dev; use nuzantara_test"
    )
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
# Unit tests run with localhost Qdrant while developer shells may export a
# different cloud QDRANT_URL; keep the production ingest guard explicit.
os.environ["LEGAL_INGEST_ALLOW_QDRANT_ENV_OVERRIDE"] = "1"
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_whatsapp_verify_token")
os.environ.setdefault("INSTAGRAM_VERIFY_TOKEN", "test_instagram_verify_token")
# FORCE-assign (not setdefault): the Pro dev/cron shell exports the REAL
# TELEGRAM_BOT_TOKEN (a GitHub secret used by all cron wrappers). With
# setdefault the real token survived into pytest, so every un-mocked Telegram
# sender — sentinel alerter (scripts/sentinel_lib/alerter.py), canva_renderer
# _telegram.send_telegram, email_audit.notify_email_failure_critical — fired
# REAL alerts to the owner chat (1125336968) during the test run (verbatim
# leaks: "OCR ... Context: unit.test.context", "WR2 rendered: Test / DAG123",
# "Invoice INV-2026-001 ... john@example.com"). Forcing the fake token makes
# those calls hit a non-existent bot (401, swallowed) — never the owner.
# Tests that genuinely exercise a sender still win via per-test monkeypatch.
os.environ["TELEGRAM_BOT_TOKEN"] = "123456:test_token"
os.environ.setdefault("EMBEDDING_PROVIDER", "openai")
os.environ.setdefault("EMBEDDING_MODEL", "text-embedding-3-small")

# Some SDK import chains load `mcp.types`, which asks pydantic to create
# RootModel generics before `pydantic.root_model` has been registered in
# sys.modules on the local dev venv. Import it here before test modules pull
# portal/multimodal services through router imports.
import pydantic.root_model  # noqa: E402,F401

# ============================================================================
# Shared fixtures
# ============================================================================
import pytest  # noqa: E402 — must come after env setup


@pytest.fixture
def mock_db_pool():
    """Standard mock asyncpg connection pool.

    Supports: async with pool.acquire() as conn
              async with conn.transaction()  (no-op async context manager)
    Usage: pool, conn = mock_db_pool
    """
    pool = MagicMock()
    conn = MagicMock()

    class _AsyncCtx:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *args):
            return None

    class _TransactionCtx:
        async def __aenter__(self):
            return None

        async def __aexit__(self, *args):
            return None

    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=_AsyncCtx())
    # conn.transaction() must return an async context manager, not a coroutine.
    # AsyncMock would make it a coroutine; use MagicMock returning _TransactionCtx.
    conn.transaction = MagicMock(return_value=_TransactionCtx())
    return pool, conn


@pytest.fixture
def mock_qdrant_client():
    """Standard mock Qdrant client."""
    client = AsyncMock()
    client.search = AsyncMock(return_value=[])
    client.upsert = AsyncMock(return_value=None)
    client.delete = AsyncMock(return_value=None)
    client.get_collections = AsyncMock(return_value=MagicMock(collections=[]))
    return client


@pytest.fixture(autouse=True)
def _wr2_runtime_isolation(tmp_path, monkeypatch):
    """Tests must NEVER touch the real WR2 runtime state (W96, 2026-07-13).

    Any test that reaches wr2_html_render_apply's visibility chain (or any
    other WR2 writer honoring WR2_OUTPUT_ROOT) without mocking it would land
    fixture entries in the PRODUCTION human-review-queue.json and spool real
    Telegram notifications — 24 phantom "micro carousels" reached the WR2
    Control app this way. Redirect both to tmp_path unconditionally; a test
    that needs its own root still wins by monkeypatching the env itself
    (test-body setenv runs after this autouse fixture).
    """
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(tmp_path / "wr2-output"))
    monkeypatch.setenv("TG_DRY_RUN", "1")
    monkeypatch.setenv("TG_SPOOL_DIR", str(tmp_path / "tg-spool"))


@pytest.fixture
def mock_redis():
    """Standard mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.exists = AsyncMock(return_value=0)
    redis.expire = AsyncMock(return_value=True)
    redis.keys = AsyncMock(return_value=[])
    return redis
