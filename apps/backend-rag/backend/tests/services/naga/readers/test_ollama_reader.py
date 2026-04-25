"""Tests for ``backend.services.naga.readers.ollama_reader``.

Mocks :func:`backend.llm.ollama_client.ollama_chat` — we never hit a real
model. Verifies:

- concurrency bound (no more than ``max_concurrency`` in-flight at once),
- majority-failure raises :class:`OllamaFallbackDegraded`,
- successful chunks have their claims merged into the envelope.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from backend.services.naga.readers import ollama_reader
from backend.services.naga.readers.ollama_reader import (
    OllamaFallbackDegraded,
    ollama_bulk_read_hierarchical,
)


def _source(domain: str, idx: int, chars: int = 500) -> dict:
    return {
        "url": f"https://{domain}/{idx}",
        "title": f"Title {idx}",
        "content": "x" * chars,
    }


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_read_respects_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    """No more than ``max_concurrency`` ollama_chat invocations can overlap."""

    in_flight = 0
    peak = 0
    lock = asyncio.Lock()

    async def fake_chat(*, messages, model, temperature, max_tokens, timeout):
        nonlocal in_flight, peak
        async with lock:
            in_flight += 1
            peak = max(peak, in_flight)
        try:
            await asyncio.sleep(0.05)
            return json.dumps({"claims": [], "missing": []})
        finally:
            async with lock:
                in_flight -= 1

    monkeypatch.setattr(ollama_reader, "ollama_chat", fake_chat)

    # 6 distinct domains → 6 chunks, concurrency capped at 2.
    sources = [_source(f"d{i}.com", i) for i in range(6)]
    result = await ollama_bulk_read_hierarchical(
        sources=sources,
        sub_questions=["What is X?"],
        max_concurrency=2,
        per_chunk_timeout_s=5.0,
    )

    assert result["chunks_processed"] == 6
    assert result["chunks_failed"] == 0
    assert peak <= 2, f"concurrency breach: peak={peak}, expected ≤ 2"


# ---------------------------------------------------------------------------
# Degraded mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_raises_degraded_when_majority_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """>50 % chunk failures must raise OllamaFallbackDegraded."""

    call_count = {"n": 0}

    async def fake_chat(*, messages, model, temperature, max_tokens, timeout):
        call_count["n"] += 1
        # 3 failures then 1 success → 3/4 failed ≥ majority.
        if call_count["n"] <= 3:
            raise asyncio.TimeoutError()
        return json.dumps({"claims": [{"claim": "ok"}], "missing": []})

    monkeypatch.setattr(ollama_reader, "ollama_chat", fake_chat)

    sources = [_source(f"d{i}.com", i) for i in range(4)]
    with pytest.raises(OllamaFallbackDegraded) as exc_info:
        await ollama_bulk_read_hierarchical(
            sources=sources,
            sub_questions=["q"],
            max_concurrency=1,
            per_chunk_timeout_s=5.0,
        )
    assert "3/4" in str(exc_info.value) or "chunks failed" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Claim merging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_merges_claims_from_successful_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Successful chunks' claims are concatenated; unanimous missing is kept."""

    responses = [
        json.dumps(
            {
                "claims": [{"claim": "A", "source_url": "u1", "confidence": 0.8}],
                "missing": ["What about Z?", "What about Y?"],
            }
        ),
        json.dumps(
            {
                "claims": [{"claim": "B", "source_url": "u2", "confidence": 0.7}],
                "missing": ["What about Y?"],
            }
        ),
    ]
    idx = {"n": 0}

    async def fake_chat(*, messages, model, temperature, max_tokens, timeout):
        out = responses[idx["n"]]
        idx["n"] += 1
        return out

    monkeypatch.setattr(ollama_reader, "ollama_chat", fake_chat)

    sources = [_source("a.com", 0), _source("b.com", 0)]
    result = await ollama_bulk_read_hierarchical(
        sources=sources,
        sub_questions=["What about Y?", "What about Z?"],
        max_concurrency=2,
        per_chunk_timeout_s=5.0,
    )

    assert result["reader"] == "ollama_deepseek_r1_32b"
    assert result["chunks_processed"] == 2
    assert result["chunks_failed"] == 0
    claim_texts = {c["claim"] for c in result["claims"]}
    assert claim_texts == {"A", "B"}
    # "What about Y?" is reported missing by *both* successful chunks → kept.
    # "What about Z?" only by the first → dropped from unanimous intersection.
    assert result["missing"] == ["What about Y?"]


@pytest.mark.asyncio
async def test_returns_empty_envelope_when_no_sources() -> None:
    result = await ollama_bulk_read_hierarchical(
        sources=[],
        sub_questions=["anything"],
    )
    assert result["chunks_processed"] == 0
    assert result["chunks_failed"] == 0
    assert result["claims"] == []
    assert result["missing"] == ["anything"]
    assert result["reader"] == "ollama_deepseek_r1_32b"


@pytest.mark.asyncio
async def test_ollama_unavailable_counted_as_chunk_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``ollama_chat`` returning None (Ollama down) counts as a chunk failure."""

    async def fake_chat(*, messages, model, temperature, max_tokens, timeout):
        return None  # ollama_client contract for unavailable

    monkeypatch.setattr(ollama_reader, "ollama_chat", fake_chat)

    # One chunk → one failure → 1/1 > 0 → degraded.
    with pytest.raises(OllamaFallbackDegraded):
        await ollama_bulk_read_hierarchical(
            sources=[_source("x.com", 0)],
            sub_questions=["q"],
        )
