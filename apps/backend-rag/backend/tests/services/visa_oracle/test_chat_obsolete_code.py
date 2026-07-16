"""PR0 safety freeze (W2) — tests for the removal of the ABSTAIN->CAUTIOUS
obsolete-code promotion in `visa_oracle.chat()`.

Prior behavior (round2 spec §6.6 step 2 / product-design.md §2 claim #2):
when a user mentioned a retired visa code (e.g. B211A) AND the KB evidence
was too weak to answer (top_score < 0.30, normally ABSTAIN), the endpoint
promoted the outcome to CAUTIOUS "on the strength of pretraining context +
SYSTEM_PROMPT rules" and let Gemini generate a free-form answer with no
grounded evidence. That promotion is removed: weak evidence now ALWAYS
abstains, obsolete code or not. The obsolete-code signal is preserved only
as a `review_reasons` annotation on the (still-safe) ABSTAIN response.
"""

from __future__ import annotations

import os
import re

# Must be set before any backend imports load config/settings.
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars_long")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key-for-testing-only-nuzantara")
os.environ.setdefault("GOOGLE_API_KEY", "test-google-api-key")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

import pytest
from starlette.requests import Request


def _build_request() -> Request:
    return Request({"type": "http", "headers": []})


class _StubSearch:
    """Hybrid search stub returning a fixed result set."""

    def __init__(self, results: list) -> None:
        self._results = results

    async def search_hybrid(self, **_kw):
        return {"results": self._results}


class _NeverCalledGemini:
    """Fails the test loudly if the LLM is invoked — weak evidence must
    never reach generation, obsolete code or not."""

    async def generate_content(self, *_a, **_kw):
        raise AssertionError(
            "Gemini must not be called on weak evidence — ABSTAIN must not "
            "be promoted to a generated answer (PR0 safety freeze, W2)."
        )


def _weak_search(score: float = 0.10) -> _StubSearch:
    return _StubSearch([{"content": "barely relevant snippet", "score": score, "source": "x"}])


@pytest.mark.asyncio
async def test_obsolete_code_weak_evidence_stays_abstain(monkeypatch):
    """B211A mentioned + top_score below 0.30 -> confidence stays ABSTAIN,
    the LLM is never called, and (FIX-7, Codex red-team P2 #6) the answer is
    the DETERMINISTIC zero-LLM obsolete-code template — not the generic
    fallback, and not a generated explanation."""
    from backend.app.routers import visa_oracle as mod

    monkeypatch.setattr(
        "backend.services.rag.hybrid_search.HybridSearchService",
        lambda: _weak_search(0.10),
    )
    monkeypatch.setattr(
        "backend.llm.genai_client.get_genai_client",
        lambda: _NeverCalledGemini(),
    )

    req = _build_request()
    body = mod.ChatRequest(session_id="s1", message="What about my B211A visa?")
    resp = await mod.chat(req, body, db_pool=None)

    assert resp.confidence == mod.CONFIDENCE_ABSTAIN
    assert resp.sources == []
    assert resp.answer == mod._obsolete_code_static_answer([("B211A", "irrelevant")])
    assert resp.answer != mod.ABSTAIN_FALLBACK_BY_LANG["en"]
    assert "B211A" in resp.answer
    assert "C1" in resp.answer


@pytest.mark.asyncio
async def test_obsolete_code_weak_evidence_sets_review_reasons(monkeypatch):
    """The obsolete-code signal survives as a review_reasons annotation."""
    from backend.app.routers import visa_oracle as mod

    monkeypatch.setattr(
        "backend.services.rag.hybrid_search.HybridSearchService",
        lambda: _weak_search(0.10),
    )
    monkeypatch.setattr(
        "backend.llm.genai_client.get_genai_client",
        lambda: _NeverCalledGemini(),
    )

    req = _build_request()
    body = mod.ChatRequest(session_id="s1", message="What about my B211A visa?")
    resp = await mod.chat(req, body, db_pool=None)

    assert resp.review_reasons == ["obsolete_code_mentioned:B211A"]


@pytest.mark.asyncio
async def test_obsolete_code_no_search_results_stays_abstain_with_reason(monkeypatch):
    """Same safety property when hybrid search returns zero rows at all
    (the other ABSTAIN early-return point in chat())."""
    from backend.app.routers import visa_oracle as mod

    monkeypatch.setattr(
        "backend.services.rag.hybrid_search.HybridSearchService",
        lambda: _StubSearch([]),
    )
    monkeypatch.setattr(
        "backend.llm.genai_client.get_genai_client",
        lambda: _NeverCalledGemini(),
    )

    req = _build_request()
    body = mod.ChatRequest(session_id="s1", message="Is B211 still valid?")
    resp = await mod.chat(req, body, db_pool=None)

    assert resp.confidence == mod.CONFIDENCE_ABSTAIN
    assert resp.review_reasons == ["obsolete_code_mentioned:B211"]


@pytest.mark.asyncio
async def test_multiple_obsolete_codes_both_named_in_answer_and_reasons(monkeypatch):
    """R2-C guilt (Codex re-review NEW-BUG, F6): a message mentioning TWO
    distinct retired codes (B211 and B211A) must not silently answer for
    only the first match — both must appear in the deterministic answer
    AND both must get their own review_reasons entry.

    Round-3 nit (Codex): a bare `"B211" in answer` substring check is
    itself a scar-family-#3 guard-over-match — INSIDE a test this time —
    since it would also (trivially, uselessly) pass on "B211A" alone,
    never actually proving B211 was named as its OWN entry. Assert
    exact-boundary presence two independent ways instead: (1) each code
    appears as its own enumerated "The visa code <CODE> ..." line, not
    merely as a substring inside the other code's line; (2) a
    word-boundary regex confirms `\bB211\b` can never match by landing
    inside "B211A" (no boundary between the shared "211" and trailing
    "A")."""
    from backend.app.routers import visa_oracle as mod

    monkeypatch.setattr(
        "backend.services.rag.hybrid_search.HybridSearchService",
        lambda: _StubSearch([]),
    )
    monkeypatch.setattr(
        "backend.llm.genai_client.get_genai_client",
        lambda: _NeverCalledGemini(),
    )

    req = _build_request()
    body = mod.ChatRequest(session_id="s1", message="Is B211 or B211A still valid?")
    resp = await mod.chat(req, body, db_pool=None)

    assert resp.confidence == mod.CONFIDENCE_ABSTAIN

    # Exact-boundary check #1: each code owns its own enumerated line.
    code_lines = [line for line in resp.answer.splitlines() if line.startswith("The visa code ")]
    mentioned_codes = {line.split("The visa code ", 1)[1].split(" ", 1)[0] for line in code_lines}
    assert mentioned_codes == {"B211", "B211A"}
    assert len(code_lines) == 2

    # Exact-boundary check #2: word-boundary regex, independent method.
    assert re.search(r"\bB211\b", resp.answer) is not None
    assert re.search(r"\bB211A\b", resp.answer) is not None

    assert set(resp.review_reasons) == {
        "obsolete_code_mentioned:B211",
        "obsolete_code_mentioned:B211A",
    }
    assert len(resp.review_reasons) == 2


@pytest.mark.asyncio
async def test_weak_evidence_without_obsolete_code_stays_abstain_no_reason(monkeypatch):
    """Innocence test: the plain ABSTAIN path (no obsolete code mentioned)
    is unaffected — review_reasons stays empty."""
    from backend.app.routers import visa_oracle as mod

    monkeypatch.setattr(
        "backend.services.rag.hybrid_search.HybridSearchService",
        lambda: _weak_search(0.10),
    )
    monkeypatch.setattr(
        "backend.llm.genai_client.get_genai_client",
        lambda: _NeverCalledGemini(),
    )

    req = _build_request()
    body = mod.ChatRequest(session_id="s1", message="What visa do I need for surfing?")
    resp = await mod.chat(req, body, db_pool=None)

    assert resp.confidence == mod.CONFIDENCE_ABSTAIN
    assert resp.review_reasons == []


@pytest.mark.asyncio
async def test_obsolete_code_strong_evidence_still_answers_normally(monkeypatch):
    """Innocence test: a GENUINE strong match (top_score > 0.55) that
    happens to mention an obsolete code is untouched — only the
    weak-evidence promotion was unsafe, not obsolete-code mentions
    in general."""
    from backend.app.routers import visa_oracle as mod

    monkeypatch.setattr(
        "backend.services.rag.hybrid_search.HybridSearchService",
        lambda: _StubSearch(
            [
                {
                    "content": "B211A was retired; the tourism replacement is C1.",
                    "score": 0.9,
                    "source": "imigrasi.go.id",
                }
            ]
        ),
    )

    class _Gemini:
        async def generate_content(self, *, contents, **_kw):
            return {"text": "B211A was retired — use C1 Visa Wisata instead."}

    monkeypatch.setattr("backend.llm.genai_client.get_genai_client", lambda: _Gemini())

    req = _build_request()
    body = mod.ChatRequest(session_id="s1", message="Is B211A still valid?")
    resp = await mod.chat(req, body, db_pool=None)

    assert resp.confidence == mod.CONFIDENCE_NORMAL
    assert "C1" in resp.answer


@pytest.mark.asyncio
async def test_high_score_but_empty_content_stays_abstain(monkeypatch):
    """FIX-4 (Codex red-team P1 #3, empty-content generation): a hit can
    carry a real similarity score (0.9, well past the 0.55 NORMAL floor)
    but empty `content` — nothing for the LLM to ground on. Guilt: this
    must ABSTAIN, not reach generation on an empty context string."""
    from backend.app.routers import visa_oracle as mod

    monkeypatch.setattr(
        "backend.services.rag.hybrid_search.HybridSearchService",
        lambda: _StubSearch([{"content": "", "score": 0.9, "source": "x"}]),
    )
    monkeypatch.setattr(
        "backend.llm.genai_client.get_genai_client",
        lambda: _NeverCalledGemini(),
    )

    req = _build_request()
    body = mod.ChatRequest(session_id="s1", message="What visa do I need for surfing?")
    resp = await mod.chat(req, body, db_pool=None)

    assert resp.confidence == mod.CONFIDENCE_ABSTAIN
    assert resp.sources == []


@pytest.mark.asyncio
async def test_whitespace_only_content_stays_abstain(monkeypatch):
    """Guilt (variant): whitespace-only content is not "usable" content
    either — same ABSTAIN outcome as a fully empty string."""
    from backend.app.routers import visa_oracle as mod

    monkeypatch.setattr(
        "backend.services.rag.hybrid_search.HybridSearchService",
        lambda: _StubSearch([{"content": "   \n\t  ", "score": 0.9, "source": "x"}]),
    )
    monkeypatch.setattr(
        "backend.llm.genai_client.get_genai_client",
        lambda: _NeverCalledGemini(),
    )

    req = _build_request()
    body = mod.ChatRequest(session_id="s1", message="What visa do I need for surfing?")
    resp = await mod.chat(req, body, db_pool=None)

    assert resp.confidence == mod.CONFIDENCE_ABSTAIN


@pytest.mark.asyncio
async def test_mixed_results_empty_content_row_dropped_real_content_kept(monkeypatch):
    """Innocence: a high-score EMPTY-content row alongside a genuine
    lower-score row with real content must not push the empty row's score
    into `top_score` — the filter runs before top_score is computed, so
    the surviving real row's score (0.9 here) legitimately drives NORMAL."""
    from backend.app.routers import visa_oracle as mod

    class _Gemini:
        async def generate_content(self, *, contents, **_kw):
            return {"text": "Real grounded answer."}

    monkeypatch.setattr(
        "backend.services.rag.hybrid_search.HybridSearchService",
        lambda: _StubSearch(
            [
                {"content": "", "score": 0.95, "source": "empty-but-scored"},
                {"content": "Real visa content here.", "score": 0.9, "source": "real"},
            ]
        ),
    )
    monkeypatch.setattr("backend.llm.genai_client.get_genai_client", lambda: _Gemini())

    req = _build_request()
    body = mod.ChatRequest(session_id="s1", message="What visa do I need for surfing?")
    resp = await mod.chat(req, body, db_pool=None)

    assert resp.confidence == mod.CONFIDENCE_NORMAL
    assert resp.sources == ["real"]
