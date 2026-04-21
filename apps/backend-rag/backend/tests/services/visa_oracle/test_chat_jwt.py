"""Tests for visa_oracle.chat JWT branch (Task 3)."""

from __future__ import annotations

import os

# Must be set before any backend imports load config/settings.
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars_long")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key-for-testing-only-nuzantara")
os.environ.setdefault("GOOGLE_API_KEY", "test-google-api-key")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from jose import jwt
from starlette.requests import Request

from backend.app.core.config import settings


def _make_jwt(sub: str, *, ttl_seconds: int = 3600, wrong_key: bool = False) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": sub,
        "type": "visa_funnel",
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
    }
    key = "WRONG_KEY_FOR_TEST_ONLY_PAD_TO_32_CHARS" if wrong_key else settings.jwt_secret_key
    return jwt.encode(claims, key, algorithm=settings.jwt_algorithm)


def _build_request(auth_header: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if auth_header:
        headers.append((b"authorization", auth_header.encode()))
    return Request({"type": "http", "headers": headers})


@pytest.mark.asyncio
async def test_chat_rejects_missing_jwt_when_check_hash_present(monkeypatch):
    """When check_hash is posted but no Authorization header, return 401."""
    from backend.app.routers import visa_oracle as mod

    req = _build_request(auth_header=None)
    body = mod.ChatRequest(
        session_id="s1", message="hello",
        check_hash="abc1234567890000",
    )
    with pytest.raises(HTTPException) as ei:
        await mod.chat(req, body, db_pool=None)
    assert ei.value.status_code == 401


@pytest.mark.asyncio
async def test_chat_rejects_wrong_signature(monkeypatch):
    """Token signed with a different key: 401."""
    from backend.app.routers import visa_oracle as mod

    token = _make_jwt("abc1234567890000", wrong_key=True)
    req = _build_request(f"Bearer {token}")
    body = mod.ChatRequest(
        session_id="s1", message="hello",
        check_hash="abc1234567890000",
    )
    with pytest.raises(HTTPException) as ei:
        await mod.chat(req, body, db_pool=None)
    assert ei.value.status_code == 401


@pytest.mark.asyncio
async def test_chat_rejects_sub_mismatch(monkeypatch):
    """Valid token but sub != posted check_hash: 403."""
    from backend.app.routers import visa_oracle as mod

    token = _make_jwt("DIFFERENT_HASH")
    req = _build_request(f"Bearer {token}")
    body = mod.ChatRequest(
        session_id="s1", message="hello",
        check_hash="abc1234567890000",
    )
    with pytest.raises(HTTPException) as ei:
        await mod.chat(req, body, db_pool=None)
    assert ei.value.status_code == 403


@pytest.mark.asyncio
async def test_chat_returns_410_when_funnel_context_vanished(monkeypatch):
    """Valid JWT but the visa_checks row is gone (TTL / purge): 410 Gone."""
    from backend.app.routers import visa_oracle as mod

    # Patch bridge.get_funnel_context to return None (lazy-imported inside chat)
    async def _none(*_a, **_kw):
        return None

    monkeypatch.setattr(
        "backend.services.visa_unified.bridge.get_funnel_context",
        _none,
    )

    token = _make_jwt("abc1234567890000")
    req = _build_request(f"Bearer {token}")
    body = mod.ChatRequest(
        session_id="s1", message="hello",
        check_hash="abc1234567890000",
    )
    with pytest.raises(HTTPException) as ei:
        await mod.chat(req, body, db_pool=None)
    assert ei.value.status_code == 410


@pytest.mark.asyncio
async def test_chat_augments_system_prompt_when_jwt_valid(monkeypatch):
    """Valid JWT + existing context: the system prompt passed to Gemini
    contains the visa code and cost from the wizard."""
    from backend.app.routers import visa_oracle as mod
    from backend.services.visa_unified.bridge import FunnelContext

    ctx = FunnelContext(
        check_hash="abc1234567890000",
        nationality="USA", purpose="work_remote",
        duration_months=12, budget_band="50m_500m",
        recommended_visa="E33G", estimated_cost_idr=13_000_000,
        alternatives=["E23-FREELANCE", "C1"], referral_mode=False,
    )

    async def _ctx(*_a, **_kw):
        return ctx

    monkeypatch.setattr(
        "backend.services.visa_unified.bridge.get_funnel_context",
        _ctx,
    )

    # Stub HybridSearchService — patched on its actual module (lazy-imported inside chat)
    class _FakeSearch:
        async def search_hybrid(self, **_kw):
            return {
                "results": [
                    {
                        "content": "E33G is the Remote Worker KITAS",
                        "score": 0.8,
                        "source": "immigrasi.go.id",
                    }
                ],
            }

    monkeypatch.setattr(
        "backend.services.rag.hybrid_search.HybridSearchService",
        _FakeSearch,
    )

    # Capture the prompt passed to Gemini
    captured: dict = {}

    class _FakeGemini:
        async def generate_content(self, *, contents, **kw):
            captured["contents"] = contents
            return {"text": "E33G answer"}

    # get_genai_client is lazy-imported inside chat; patch the module-level function
    monkeypatch.setattr(
        "backend.llm.genai_client.get_genai_client",
        lambda: _FakeGemini(),
    )

    token = _make_jwt("abc1234567890000")
    req = _build_request(f"Bearer {token}")
    body = mod.ChatRequest(
        session_id="sess-1", message="posso estendere?",
        check_hash="abc1234567890000", language="it",
    )
    resp = await mod.chat(req, body, db_pool=None)

    assert "E33G" in captured["contents"]
    assert ("13,000,000" in captured["contents"]
            or "13000000" in captured["contents"])
    assert resp.session_id == "sess-1"
