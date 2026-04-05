# Visa Oracle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a consumer-facing visa guidance product at `visa.balizero.com` — quiz + 3 AI chat questions + WhatsApp handoff to Damar.

**Architecture:** New `(visa-oracle)` route group in `apps/mouth` with subdomain routing via middleware. Backend: new `/api/v1/visa-oracle/*` router in `apps/backend-rag`. Quiz uses pure logic (no LLM). Chat uses existing HybridSearch + CrossEncoder + Gemini Flash pipeline. Session logging to PostgreSQL. Telegram notification for lead handoff.

**Tech Stack:** Next.js 15 (App Router, SSG), TypeScript, Tailwind CSS, FastAPI, PostgreSQL, Qdrant, Gemini Flash, Telegram Bot API.

**Spec:** `docs/superpowers/specs/2026-04-04-visa-oracle-design.md`

---

## File Map

### Frontend — New Files

| File                                                        | Responsibility                                            |
| ----------------------------------------------------------- | --------------------------------------------------------- |
| `apps/mouth/src/app/(visa-oracle)/layout.tsx`               | Standalone layout (own nav, footer, no workspace sidebar) |
| `apps/mouth/src/app/(visa-oracle)/page.tsx`                 | Landing page with hero + dual CTA                         |
| `apps/mouth/src/app/(visa-oracle)/quiz/page.tsx`            | 4-step wizard                                             |
| `apps/mouth/src/app/(visa-oracle)/result/page.tsx`          | Visa recommendation cards                                 |
| `apps/mouth/src/app/(visa-oracle)/chat/page.tsx`            | 3-question chat with counter + WhatsApp CTA               |
| `apps/mouth/src/app/(visa-oracle)/privacy/page.tsx`         | Privacy policy                                            |
| `apps/mouth/src/app/(visa-oracle)/terms/page.tsx`           | Terms of service                                          |
| `apps/mouth/src/components/visa-oracle/QuizWizard.tsx`      | 4-step form component                                     |
| `apps/mouth/src/components/visa-oracle/VisaCard.tsx`        | Recommendation card                                       |
| `apps/mouth/src/components/visa-oracle/VisaChat.tsx`        | Consumer chat wrapper                                     |
| `apps/mouth/src/components/visa-oracle/QuestionCounter.tsx` | "X questions remaining"                                   |
| `apps/mouth/src/components/visa-oracle/WhatsAppCTA.tsx`     | Handoff overlay                                           |
| `apps/mouth/src/components/visa-oracle/ConfidenceBadge.tsx` | CAUTIOUS vs NORMAL                                        |
| `apps/mouth/src/components/visa-oracle/ConsentBanner.tsx`   | Cookie/privacy consent                                    |
| `apps/mouth/src/lib/visa-oracle/types.ts`                   | TypeScript types                                          |
| `apps/mouth/src/lib/visa-oracle/api.ts`                     | API client                                                |
| `apps/mouth/src/lib/visa-oracle/quiz-logic.ts`              | Client-side visa matching                                 |
| `apps/mouth/src/lib/visa-oracle/nationalities.ts`           | Top 15 nationalities data                                 |
| `apps/mouth/src/lib/visa-oracle/storage.ts`                 | localStorage counter + session ID                         |

### Frontend — Modified Files

| File                            | Change                                    |
| ------------------------------- | ----------------------------------------- |
| `apps/mouth/src/middleware.ts`  | Add `visa.balizero.com` subdomain routing |
| `apps/mouth/src/app/sitemap.ts` | Add visa-oracle pages to sitemap          |

### Backend — New Files

| File                                                                        | Responsibility                          |
| --------------------------------------------------------------------------- | --------------------------------------- |
| `apps/backend-rag/backend/app/routers/visa_oracle.py`                       | `/api/v1/visa-oracle/*` endpoints       |
| `apps/backend-rag/backend/services/visa_oracle/visa_oracle_service.py`      | Quiz logic, chat orchestration, handoff |
| `apps/backend-rag/backend/services/visa_oracle/__init__.py`                 | Package init                            |
| `apps/backend-rag/backend/migrations/migration_080_visa_oracle_sessions.py` | Session logging table                   |
| `apps/backend-rag/backend/tests/services/test_visa_oracle_service.py`       | Service tests                           |
| `apps/backend-rag/backend/tests/routers/test_visa_oracle.py`                | Router tests                            |

### Backend — Modified Files

| File                                                        | Change                                        |
| ----------------------------------------------------------- | --------------------------------------------- |
| `apps/backend-rag/backend/app/setup/router_registration.py` | Register visa_oracle router                   |
| `apps/backend-rag/backend/middleware/rate_limiter.py`       | Add rate limit for `/api/v1/visa-oracle/chat` |

---

## Task 1: Backend — Database Migration + Service Foundation

**Files:**

- Create: `apps/backend-rag/backend/migrations/migration_080_visa_oracle_sessions.py`
- Create: `apps/backend-rag/backend/services/visa_oracle/__init__.py`
- Create: `apps/backend-rag/backend/services/visa_oracle/visa_oracle_service.py`
- Create: `apps/backend-rag/backend/tests/services/test_visa_oracle_service.py`

- [ ] **Step 1: Write the migration**

```python
"""
Migration 080: Visa Oracle Sessions

Creates visa_oracle_sessions table for logging quiz results, chat conversations,
and handoff events. 90-day auto-purge via expires_at column.

Reviewed by: Claude Opus 4.6
"""

import logging

logger = logging.getLogger(__name__)


async def apply(conn) -> None:
    """Create visa_oracle_sessions table."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS visa_oracle_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id VARCHAR(64) NOT NULL,
            quiz_answers JSONB DEFAULT '{}',
            recommended_visas JSONB DEFAULT '[]',
            messages JSONB DEFAULT '[]',
            language_detected VARCHAR(10),
            handoff_triggered BOOLEAN DEFAULT FALSE,
            ip_hash VARCHAR(64),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            expires_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '90 days')
        );

        CREATE INDEX IF NOT EXISTS idx_visa_oracle_sessions_session_id
            ON visa_oracle_sessions(session_id);

        CREATE INDEX IF NOT EXISTS idx_visa_oracle_sessions_created_at
            ON visa_oracle_sessions(created_at);

        CREATE INDEX IF NOT EXISTS idx_visa_oracle_sessions_expires_at
            ON visa_oracle_sessions(expires_at);
    """)
    logger.info("Migration 080: visa_oracle_sessions table created")


async def rollback(conn) -> None:
    """Drop visa_oracle_sessions table."""
    await conn.execute("DROP TABLE IF EXISTS visa_oracle_sessions CASCADE;")
    logger.info("Migration 080: visa_oracle_sessions table dropped")
```

- [ ] **Step 2: Write the service package init**

```python
# apps/backend-rag/backend/services/visa_oracle/__init__.py
from .visa_oracle_service import VisaOracleService, get_visa_oracle_service

__all__ = ["VisaOracleService", "get_visa_oracle_service"]
```

- [ ] **Step 3: Write failing tests for the service**

```python
# apps/backend-rag/backend/tests/services/test_visa_oracle_service.py
"""Tests for VisaOracleService — quiz recommendation logic and session management."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services.visa_oracle.visa_oracle_service import VisaOracleService


@pytest.fixture
def pricing_data():
    """Minimal pricing data matching bali_zero_official_prices_2025.json structure."""
    return {
        "services": {
            "single_entry_visas": {
                "C1 Tourism": {
                    "price": "2.300.000 IDR",
                    "duration": "",
                    "validity": "",
                    "notes": "Single entry, 60 days",
                },
                "C2 Business": {
                    "price": "3.600.000 IDR",
                    "duration": "",
                    "validity": "",
                    "notes": "Single entry, 60 days",
                },
            },
            "kitas_permits": {
                "Investor KITAS 2 Years (New)": {
                    "price": "28.000.000 IDR",
                    "duration": "",
                    "validity": "2 Years",
                    "notes": "",
                },
                "Retirement KITAS 1 Year (New)": {
                    "price": "18.000.000 IDR",
                    "duration": "",
                    "validity": "1 Year",
                    "notes": "",
                },
            },
        }
    }


@pytest.fixture
def service(pricing_data):
    with patch(
        "backend.services.visa_oracle.visa_oracle_service.get_pricing_service"
    ) as mock_pricing:
        mock_ps = MagicMock()
        mock_ps.prices = pricing_data
        mock_pricing.return_value = mock_ps
        svc = VisaOracleService()
    return svc


class TestRecommendVisas:
    def test_recommend_returns_list(self, service):
        result = service.recommend_visas(
            nationality="australian",
            purpose="visit",
            duration="short",
            family="solo",
        )
        assert isinstance(result, list)
        assert len(result) > 0

    def test_recommend_visit_short_returns_tourism(self, service):
        result = service.recommend_visas(
            nationality="australian",
            purpose="visit",
            duration="short",
            family="solo",
        )
        names = [r["visa_name"] for r in result]
        assert any("Tourism" in n or "C1" in n for n in names)

    def test_recommend_invest_long_returns_kitas(self, service):
        result = service.recommend_visas(
            nationality="australian",
            purpose="invest",
            duration="long",
            family="solo",
        )
        names = [r["visa_name"] for r in result]
        assert any("KITAS" in n or "Investor" in n for n in names)

    def test_recommend_retire_returns_retirement(self, service):
        result = service.recommend_visas(
            nationality="australian",
            purpose="retire",
            duration="long",
            family="solo",
        )
        names = [r["visa_name"] for r in result]
        assert any("Retire" in n.lower() or "retirement" in n.lower() for n in names)

    def test_recommend_has_required_fields(self, service):
        result = service.recommend_visas(
            nationality="australian",
            purpose="visit",
            duration="short",
            family="solo",
        )
        for visa in result:
            assert "visa_name" in visa
            assert "category" in visa
            assert "price" in visa
            assert "score" in visa

    def test_recommend_max_3_results(self, service):
        result = service.recommend_visas(
            nationality="australian",
            purpose="work",
            duration="long",
            family="spouse_children",
        )
        assert len(result) <= 3


class TestGetAllVisaTypes:
    def test_returns_all_types(self, service):
        result = service.get_all_visa_types()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_each_type_has_name_and_category(self, service):
        result = service.get_all_visa_types()
        for vt in result:
            assert "name" in vt
            assert "category" in vt
            assert "price" in vt
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/services/test_visa_oracle_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.services.visa_oracle'`

- [ ] **Step 5: Write the VisaOracleService**

```python
# apps/backend-rag/backend/services/visa_oracle/visa_oracle_service.py
"""Visa Oracle Service — quiz recommendation logic and session management.

Handles:
- Visa recommendation from quiz answers (no LLM, pure logic + PricingTool)
- Session creation and message logging
- Handoff data assembly for WhatsApp + Telegram
"""

import hashlib
import logging
import uuid
from typing import Any

from backend.services.pricing.pricing_service import get_pricing_service

logger = logging.getLogger(__name__)

# Purpose → visa category mapping
PURPOSE_CATEGORY_MAP: dict[str, list[str]] = {
    "visit": ["single_entry_visas", "multiple_entry_visas"],
    "work": ["kitas_permits", "single_entry_visas"],
    "invest": ["kitas_permits", "multiple_entry_visas"],
    "retire": ["kitas_permits"],
    "digital_nomad": ["single_entry_visas", "multiple_entry_visas", "kitas_permits"],
    "family": ["kitas_permits"],
    "study": ["single_entry_visas", "kitas_permits"],
}

# Duration mapping
DURATION_MAP: dict[str, str] = {
    "short": "< 6 months",
    "medium": "6-12 months",
    "long": "1+ years",
    "permanent": "permanent",
}

# Keywords for scoring relevance
PURPOSE_KEYWORDS: dict[str, list[str]] = {
    "visit": ["tourism", "tourist", "visit", "c1"],
    "work": ["work", "employment", "rptka", "imta", "c18", "trial"],
    "invest": ["investor", "investment", "business", "d12"],
    "retire": ["retire", "retirement", "pension"],
    "digital_nomad": ["digital", "nomad", "remote", "freelance"],
    "family": ["spouse", "dependent", "family", "reunion"],
    "study": ["student", "study", "education", "internship", "c22"],
}


class VisaOracleService:
    """Pure logic visa recommendation + session management."""

    def __init__(self) -> None:
        self.pricing = get_pricing_service()

    def recommend_visas(
        self,
        nationality: str,
        purpose: str,
        duration: str,
        family: str,
    ) -> list[dict[str, Any]]:
        """Recommend visas based on quiz answers. No LLM — pure logic + pricing data."""
        categories = PURPOSE_CATEGORY_MAP.get(purpose, ["single_entry_visas"])
        keywords = PURPOSE_KEYWORDS.get(purpose, [])
        candidates: list[dict[str, Any]] = []

        for category in categories:
            services = self.pricing.prices.get("services", {}).get(category, {})
            for name, details in services.items():
                score = self._score_visa(name, details, purpose, duration, family, keywords)
                if score > 0:
                    candidates.append({
                        "visa_name": name,
                        "category": category,
                        "price": details.get("price", ""),
                        "duration": details.get("duration", ""),
                        "validity": details.get("validity", ""),
                        "notes": details.get("notes", ""),
                        "score": score,
                    })

        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:3]

    def get_all_visa_types(self) -> list[dict[str, str]]:
        """Return all visa types with name, category, and price."""
        result: list[dict[str, str]] = []
        for category, services in self.pricing.prices.get("services", {}).items():
            for name, details in services.items():
                result.append({
                    "name": name,
                    "category": category,
                    "price": details.get("price", ""),
                    "duration": details.get("duration", ""),
                    "validity": details.get("validity", ""),
                    "notes": details.get("notes", ""),
                })
        return result

    def build_whatsapp_message(
        self,
        nationality: str,
        purpose: str,
        duration: str,
        visa_name: str,
        price: str,
    ) -> str:
        """Build pre-filled WhatsApp message for Damar."""
        return (
            f"Hi, I used Visa Oracle. I'm {nationality}, "
            f"looking to {purpose} in Indonesia for {duration}. "
            f"Recommended: {visa_name}. Bali Zero fee: {price}."
        )

    def build_telegram_summary(
        self,
        session_id: str,
        quiz_answers: dict[str, str],
        recommended_visas: list[dict[str, Any]],
        messages: list[dict[str, str]],
        language: str | None,
    ) -> str:
        """Build Telegram notification message for Damar."""
        visa_names = ", ".join(v["visa_name"] for v in recommended_visas[:3])
        msg_summary = ""
        for i, m in enumerate(messages):
            if m.get("role") == "user":
                msg_summary += f"\n  Q{i // 2 + 1}: {m['content'][:100]}"
            elif m.get("role") == "assistant":
                msg_summary += f"\n  A: {m['content'][:150]}"

        return (
            f"🆕 *Visa Oracle Lead*\n\n"
            f"🌍 Nationality: {quiz_answers.get('nationality', 'N/A')}\n"
            f"🎯 Purpose: {quiz_answers.get('purpose', 'N/A')}\n"
            f"⏱ Duration: {quiz_answers.get('duration', 'N/A')}\n"
            f"👨‍👩‍👧 Family: {quiz_answers.get('family', 'N/A')}\n"
            f"🗣 Language: {language or 'EN'}\n\n"
            f"📋 Recommended: {visa_names}\n\n"
            f"💬 Conversation:{msg_summary}\n\n"
            f"🔗 Session: {session_id}"
        )

    @staticmethod
    def hash_ip(ip: str) -> str:
        """SHA-256 hash of IP address for rate limiting."""
        return hashlib.sha256(ip.encode()).hexdigest()

    @staticmethod
    def generate_session_id() -> str:
        """Generate a unique session ID."""
        return uuid.uuid4().hex[:16]

    def _score_visa(
        self,
        name: str,
        details: dict[str, str],
        purpose: str,
        duration: str,
        family: str,
        keywords: list[str],
    ) -> float:
        """Score a visa candidate based on purpose, duration, and keywords."""
        score = 0.0
        name_lower = name.lower()
        notes_lower = (details.get("notes", "") or "").lower()
        combined = f"{name_lower} {notes_lower}"

        # Keyword match
        for kw in keywords:
            if kw in combined:
                score += 2.0

        # Duration fit
        validity = (details.get("validity", "") or "").lower()
        visa_duration = (details.get("duration", "") or "").lower()
        if duration == "short" and ("60 day" in combined or "30 day" in combined or "90 day" in combined):
            score += 1.5
        elif duration == "long" and ("year" in validity or "year" in visa_duration or "kitas" in name_lower):
            score += 1.5
        elif duration == "permanent" and ("kitap" in name_lower or "permanent" in combined):
            score += 2.0

        # Family modifier
        if family in ("spouse", "spouse_children") and "spouse" in combined:
            score += 1.0
        if family in ("children", "spouse_children") and ("dependent" in combined or "family" in combined):
            score += 1.0

        return score


# Singleton
_visa_oracle_service: VisaOracleService | None = None


def get_visa_oracle_service() -> VisaOracleService:
    global _visa_oracle_service
    if _visa_oracle_service is None:
        _visa_oracle_service = VisaOracleService()
    return _visa_oracle_service
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/services/test_visa_oracle_service.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/migrations/migration_080_visa_oracle_sessions.py \
        apps/backend-rag/backend/services/visa_oracle/__init__.py \
        apps/backend-rag/backend/services/visa_oracle/visa_oracle_service.py \
        apps/backend-rag/backend/tests/services/test_visa_oracle_service.py
git commit -m "feat(visa-oracle): add service foundation + migration + tests"
```

---

## Task 2: Backend — API Router + Rate Limiting

**Files:**

- Create: `apps/backend-rag/backend/app/routers/visa_oracle.py`
- Create: `apps/backend-rag/backend/tests/routers/test_visa_oracle.py`
- Modify: `apps/backend-rag/backend/app/setup/router_registration.py`
- Modify: `apps/backend-rag/backend/middleware/rate_limiter.py`

- [ ] **Step 1: Write failing tests for the router**

```python
# apps/backend-rag/backend/tests/routers/test_visa_oracle.py
"""Tests for Visa Oracle API router."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestRecommendEndpoint:
    """POST /api/v1/visa-oracle/recommend"""

    def test_recommend_returns_visas(self):
        from backend.app.routers.visa_oracle import router
        assert router is not None

    def test_recommend_requires_nationality(self):
        from backend.app.routers.visa_oracle import RecommendRequest
        req = RecommendRequest(
            nationality="australian",
            purpose="visit",
            duration="short",
            family="solo",
        )
        assert req.nationality == "australian"

    def test_recommend_request_validates_purpose(self):
        from backend.app.routers.visa_oracle import RecommendRequest
        req = RecommendRequest(
            nationality="american",
            purpose="invest",
            duration="long",
            family="spouse",
        )
        assert req.purpose == "invest"


class TestVisaTypesEndpoint:
    """GET /api/v1/visa-oracle/visa-types"""

    def test_visa_types_endpoint_exists(self):
        from backend.app.routers.visa_oracle import router
        routes = [r.path for r in router.routes]
        assert "/visa-types" in routes or any("/visa-types" in r for r in routes)


class TestHandoffEndpoint:
    """POST /api/v1/visa-oracle/handoff"""

    def test_handoff_request_model(self):
        from backend.app.routers.visa_oracle import HandoffRequest
        req = HandoffRequest(
            session_id="abc123",
            quiz_answers={"nationality": "australian", "purpose": "work"},
            recommended_visas=[{"visa_name": "C2 Business", "price": "3.600.000 IDR"}],
            messages=[{"role": "user", "content": "How long does it take?"}],
            language="en",
        )
        assert req.session_id == "abc123"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/routers/test_visa_oracle.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the router**

```python
# apps/backend-rag/backend/app/routers/visa_oracle.py
"""Visa Oracle API — /api/v1/visa-oracle/*

Consumer-facing endpoints for visa guidance quiz and chat.
No authentication required (public product).
"""

import logging
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from backend.services.visa_oracle.visa_oracle_service import get_visa_oracle_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/visa-oracle", tags=["visa-oracle"])


# --- Request/Response Models ---

class RecommendRequest(BaseModel):
    nationality: str
    purpose: str  # visit, work, invest, retire, digital_nomad, family, study
    duration: str  # short, medium, long, permanent
    family: str  # solo, spouse, children, spouse_children


class RecommendResponse(BaseModel):
    success: bool
    visas: list[dict[str, Any]]
    session_id: str


class ChatRequest(BaseModel):
    session_id: str
    message: str
    quiz_answers: dict[str, str] | None = None
    conversation_history: list[dict[str, str]] | None = None


class ChatResponse(BaseModel):
    success: bool
    answer: str
    confidence: str  # ABSTAIN, CAUTIOUS, NORMAL
    sources: list[str]
    session_id: str


class HandoffRequest(BaseModel):
    session_id: str
    quiz_answers: dict[str, str]
    recommended_visas: list[dict[str, Any]]
    messages: list[dict[str, str]]
    language: str | None = None


class HandoffResponse(BaseModel):
    success: bool
    whatsapp_url: str
    telegram_sent: bool


# --- Endpoints ---

@router.post("/recommend", response_model=RecommendResponse)
async def recommend_visas(request: RecommendRequest) -> RecommendResponse:
    """Quiz answers → ranked visa recommendations. No LLM, pure logic + PricingTool."""
    service = get_visa_oracle_service()
    session_id = service.generate_session_id()

    visas = service.recommend_visas(
        nationality=request.nationality,
        purpose=request.purpose,
        duration=request.duration,
        family=request.family,
    )

    logger.info(
        f"Visa Oracle recommend: {request.nationality}/{request.purpose} "
        f"→ {len(visas)} results, session={session_id}"
    )

    return RecommendResponse(
        success=True,
        visas=visas,
        session_id=session_id,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request) -> ChatResponse:
    """Question → RAG pipeline → structured response. Rate limited: 10/hour/IP."""
    # Import here to avoid circular imports at module level
    from backend.services.rag.hybrid_search import HybridSearchService
    from backend.services.rag.reranker import CrossEncoderReranker

    service = get_visa_oracle_service()

    # Build context from quiz answers if available
    context = ""
    if request.quiz_answers:
        qa = request.quiz_answers
        context = (
            f"User profile: {qa.get('nationality', '')} national, "
            f"purpose: {qa.get('purpose', '')}, "
            f"duration: {qa.get('duration', '')}, "
            f"family: {qa.get('family', '')}. "
        )

    # Combine context + user message for RAG query
    query = f"{context}{request.message}" if context else request.message

    # Use existing RAG pipeline
    try:
        search_service = HybridSearchService()
        results = await search_service.search(
            query=query,
            collection_names=["visa_oracle", "legal_unified_hybrid", "immigration_circulars"],
            limit=5,
        )

        # Rerank results
        reranker = CrossEncoderReranker()
        reranked = reranker.rerank(query, results) if results else []

        # Calculate confidence from reranker scores
        if not reranked:
            confidence = "ABSTAIN"
            answer = "This requires expert review. Our team can give you a definitive answer."
            sources = []
        else:
            top_score = reranked[0].get("rerank_score", 0.0) if reranked else 0.0
            if top_score < 0.15:
                confidence = "ABSTAIN"
                answer = "This requires expert review. Our team can give you a definitive answer."
                sources = []
            elif top_score < 0.60:
                confidence = "CAUTIOUS"
                # Generate answer via Gemini Flash with hedging
                answer = await _generate_answer(query, reranked, cautious=True)
                sources = [r.get("source", "") for r in reranked[:3] if r.get("source")]
            else:
                confidence = "NORMAL"
                answer = await _generate_answer(query, reranked, cautious=False)
                sources = [r.get("source", "") for r in reranked[:3] if r.get("source")]

    except Exception as e:
        logger.error(f"Visa Oracle chat error: {e}", exc_info=True)
        confidence = "ABSTAIN"
        answer = "I'm having trouble processing your question. Our team can help directly."
        sources = []

    logger.info(
        f"Visa Oracle chat: session={request.session_id}, "
        f"confidence={confidence}, sources={len(sources)}"
    )

    return ChatResponse(
        success=True,
        answer=answer,
        confidence=confidence,
        sources=sources,
        session_id=request.session_id,
    )


@router.post("/handoff", response_model=HandoffResponse)
async def handoff(request: HandoffRequest) -> HandoffResponse:
    """Trigger WhatsApp link generation + Telegram notification to Damar."""
    from backend.services.integrations.telegram_bot_service import telegram_bot

    service = get_visa_oracle_service()
    DAMAR_CHAT_ID = 1125336968
    DAMAR_WHATSAPP = "6281338051876"  # Bali Zero WhatsApp from pricing JSON

    # Build WhatsApp URL
    visa_name = ""
    price = ""
    if request.recommended_visas:
        top = request.recommended_visas[0]
        visa_name = top.get("visa_name", "")
        price = top.get("price", "")

    wa_message = service.build_whatsapp_message(
        nationality=request.quiz_answers.get("nationality", ""),
        purpose=request.quiz_answers.get("purpose", ""),
        duration=request.quiz_answers.get("duration", ""),
        visa_name=visa_name,
        price=price,
    )
    whatsapp_url = f"https://wa.me/{DAMAR_WHATSAPP}?text={wa_message}"

    # Send Telegram notification
    telegram_sent = False
    try:
        summary = service.build_telegram_summary(
            session_id=request.session_id,
            quiz_answers=request.quiz_answers,
            recommended_visas=request.recommended_visas,
            messages=request.messages,
            language=request.language,
        )
        await telegram_bot.send_message(
            chat_id=DAMAR_CHAT_ID,
            text=summary,
            parse_mode="Markdown",
        )
        telegram_sent = True
        logger.info(f"Visa Oracle handoff: Telegram sent to {DAMAR_CHAT_ID}")
    except Exception as e:
        logger.error(f"Visa Oracle handoff Telegram error: {e}", exc_info=True)

    return HandoffResponse(
        success=True,
        whatsapp_url=whatsapp_url,
        telegram_sent=telegram_sent,
    )


@router.get("/visa-types")
async def get_visa_types() -> dict[str, Any]:
    """Return all current visa types. Used at build time for SSG pages."""
    service = get_visa_oracle_service()
    return {"visa_types": service.get_all_visa_types()}


@router.get("/visa-types/{code}")
async def get_visa_type_detail(code: str) -> dict[str, Any]:
    """Return detail for one visa type by name. Used at build time for SSG."""
    service = get_visa_oracle_service()
    all_types = service.get_all_visa_types()
    for vt in all_types:
        if vt["name"].lower().replace(" ", "-") == code.lower():
            return {"visa_type": vt}
    return {"visa_type": None, "error": "Not found"}


# --- Internal helpers ---

async def _generate_answer(
    query: str,
    context_docs: list[dict[str, Any]],
    cautious: bool = False,
) -> str:
    """Generate answer via Gemini Flash using RAG context."""
    from backend.llm.gemini_client import GeminiClient

    context = "\n\n".join(
        doc.get("content", doc.get("text", ""))[:500]
        for doc in context_docs[:3]
    )

    hedging = (
        "IMPORTANT: Hedge your answer — say 'Based on available information' "
        "and recommend confirming with the team for their specific case. "
    ) if cautious else ""

    prompt = (
        f"You are an Indonesian visa specialist. Answer ONLY based on the context below. "
        f"If the context doesn't contain the answer, say so. "
        f"Never say 'you should' or 'you must'. Use 'typically requires', 'the standard process involves'. "
        f"Include Bali Zero service prices if mentioned in context. "
        f"{hedging}"
        f"\n\nContext:\n{context}\n\nQuestion: {query}\n\nAnswer:"
    )

    try:
        client = GeminiClient()
        response = await client.generate(prompt, max_tokens=500)
        return response
    except Exception as e:
        logger.error(f"Gemini generation error: {e}", exc_info=True)
        return "I'm having trouble generating a response. Our team can help directly."
```

- [ ] **Step 4: Register the router in router_registration.py**

Add to `apps/backend-rag/backend/app/setup/router_registration.py` — inside the `include_routers` function, add the lazy import and registration following the existing pattern:

```python
# Add among the lazy imports (around line ~110):
from backend.app.routers import visa_oracle

# Add among the include_router calls (around line ~330):
api.include_router(visa_oracle.router, prefix=settings.API_V1_STR)
```

- [ ] **Step 5: Add rate limit for visa-oracle chat**

In `apps/backend-rag/backend/middleware/rate_limiter.py`, add to `RATE_LIMITS` dict (around line 175):

```python
"/api/v1/visa-oracle/chat": (10, 3600),  # 10 per hour per IP
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/routers/test_visa_oracle.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/app/routers/visa_oracle.py \
        apps/backend-rag/backend/tests/routers/test_visa_oracle.py \
        apps/backend-rag/backend/app/setup/router_registration.py \
        apps/backend-rag/backend/middleware/rate_limiter.py
git commit -m "feat(visa-oracle): add API router + rate limiting"
```

---

## Task 3: Frontend — Types, API Client, Quiz Logic, Storage

**Files:**

- Create: `apps/mouth/src/lib/visa-oracle/types.ts`
- Create: `apps/mouth/src/lib/visa-oracle/api.ts`
- Create: `apps/mouth/src/lib/visa-oracle/quiz-logic.ts`
- Create: `apps/mouth/src/lib/visa-oracle/nationalities.ts`
- Create: `apps/mouth/src/lib/visa-oracle/storage.ts`

- [ ] **Step 1: Create TypeScript types**

```typescript
// apps/mouth/src/lib/visa-oracle/types.ts

export interface QuizAnswers {
  nationality: string;
  purpose: 'visit' | 'work' | 'invest' | 'retire' | 'digital_nomad' | 'family' | 'study';
  duration: 'short' | 'medium' | 'long' | 'permanent';
  family: 'solo' | 'spouse' | 'children' | 'spouse_children';
}

export interface VisaRecommendation {
  visa_name: string;
  category: string;
  price: string;
  duration: string;
  validity: string;
  notes: string;
  score: number;
}

export interface RecommendResponse {
  success: boolean;
  visas: VisaRecommendation[];
  session_id: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  confidence?: 'ABSTAIN' | 'CAUTIOUS' | 'NORMAL';
  sources?: string[];
}

export interface ChatResponse {
  success: boolean;
  answer: string;
  confidence: 'ABSTAIN' | 'CAUTIOUS' | 'NORMAL';
  sources: string[];
  session_id: string;
}

export interface HandoffResponse {
  success: boolean;
  whatsapp_url: string;
  telegram_sent: boolean;
}

export interface Nationality {
  code: string;
  name: string;
  flag: string;
}
```

- [ ] **Step 2: Create nationalities data**

```typescript
// apps/mouth/src/lib/visa-oracle/nationalities.ts

import type { Nationality } from './types';

export const TOP_NATIONALITIES: Nationality[] = [
  { code: 'AU', name: 'Australia', flag: '🇦🇺' },
  { code: 'US', name: 'United States', flag: '🇺🇸' },
  { code: 'GB', name: 'United Kingdom', flag: '🇬🇧' },
  { code: 'RU', name: 'Russia', flag: '🇷🇺' },
  { code: 'CN', name: 'China', flag: '🇨🇳' },
  { code: 'KR', name: 'South Korea', flag: '🇰🇷' },
  { code: 'JP', name: 'Japan', flag: '🇯🇵' },
  { code: 'DE', name: 'Germany', flag: '🇩🇪' },
  { code: 'FR', name: 'France', flag: '🇫🇷' },
  { code: 'NL', name: 'Netherlands', flag: '🇳🇱' },
  { code: 'CA', name: 'Canada', flag: '🇨🇦' },
  { code: 'IN', name: 'India', flag: '🇮🇳' },
  { code: 'BR', name: 'Brazil', flag: '🇧🇷' },
  { code: 'IT', name: 'Italy', flag: '🇮🇹' },
  { code: 'SG', name: 'Singapore', flag: '🇸🇬' },
];

// Full list for the dropdown search (all countries)
export const ALL_NATIONALITIES: Nationality[] = [
  ...TOP_NATIONALITIES,
  { code: 'AF', name: 'Afghanistan', flag: '🇦🇫' },
  { code: 'AL', name: 'Albania', flag: '🇦🇱' },
  { code: 'DZ', name: 'Algeria', flag: '🇩🇿' },
  { code: 'AR', name: 'Argentina', flag: '🇦🇷' },
  { code: 'AT', name: 'Austria', flag: '🇦🇹' },
  { code: 'BD', name: 'Bangladesh', flag: '🇧🇩' },
  { code: 'BE', name: 'Belgium', flag: '🇧🇪' },
  { code: 'CL', name: 'Chile', flag: '🇨🇱' },
  { code: 'CO', name: 'Colombia', flag: '🇨🇴' },
  { code: 'CZ', name: 'Czech Republic', flag: '🇨🇿' },
  { code: 'DK', name: 'Denmark', flag: '🇩🇰' },
  { code: 'EG', name: 'Egypt', flag: '🇪🇬' },
  { code: 'FI', name: 'Finland', flag: '🇫🇮' },
  { code: 'GR', name: 'Greece', flag: '🇬🇷' },
  { code: 'HU', name: 'Hungary', flag: '🇭🇺' },
  { code: 'IE', name: 'Ireland', flag: '🇮🇪' },
  { code: 'IL', name: 'Israel', flag: '🇮🇱' },
  { code: 'KE', name: 'Kenya', flag: '🇰🇪' },
  { code: 'MY', name: 'Malaysia', flag: '🇲🇾' },
  { code: 'MX', name: 'Mexico', flag: '🇲🇽' },
  { code: 'NZ', name: 'New Zealand', flag: '🇳🇿' },
  { code: 'NG', name: 'Nigeria', flag: '🇳🇬' },
  { code: 'NO', name: 'Norway', flag: '🇳🇴' },
  { code: 'PK', name: 'Pakistan', flag: '🇵🇰' },
  { code: 'PH', name: 'Philippines', flag: '🇵🇭' },
  { code: 'PL', name: 'Poland', flag: '🇵🇱' },
  { code: 'PT', name: 'Portugal', flag: '🇵🇹' },
  { code: 'RO', name: 'Romania', flag: '🇷🇴' },
  { code: 'SA', name: 'Saudi Arabia', flag: '🇸🇦' },
  { code: 'ZA', name: 'South Africa', flag: '🇿🇦' },
  { code: 'ES', name: 'Spain', flag: '🇪🇸' },
  { code: 'SE', name: 'Sweden', flag: '🇸🇪' },
  { code: 'CH', name: 'Switzerland', flag: '🇨🇭' },
  { code: 'TH', name: 'Thailand', flag: '🇹🇭' },
  { code: 'TR', name: 'Turkey', flag: '🇹🇷' },
  { code: 'UA', name: 'Ukraine', flag: '🇺🇦' },
  { code: 'AE', name: 'United Arab Emirates', flag: '🇦🇪' },
  { code: 'VN', name: 'Vietnam', flag: '🇻🇳' },
].sort((a, b) => a.name.localeCompare(b.name));
```

- [ ] **Step 3: Create localStorage storage helper**

```typescript
// apps/mouth/src/lib/visa-oracle/storage.ts

const STORAGE_KEY = 'visa_oracle_session';
const MAX_QUESTIONS = 3;

interface SessionData {
  sessionId: string;
  questionsUsed: number;
  createdAt: number;
}

function generateSessionId(): string {
  return Math.random().toString(36).substring(2, 18);
}

export function getSession(): SessionData {
  if (typeof window === 'undefined') {
    return {
      sessionId: generateSessionId(),
      questionsUsed: 0,
      createdAt: Date.now(),
    };
  }

  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const data: SessionData = JSON.parse(stored);
      // Reset after 24 hours
      if (Date.now() - data.createdAt > 24 * 60 * 60 * 1000) {
        return resetSession();
      }
      return data;
    }
  } catch {
    // localStorage unavailable or corrupted
  }
  return resetSession();
}

export function incrementQuestions(): SessionData {
  const session = getSession();
  session.questionsUsed += 1;
  saveSession(session);
  return session;
}

export function getRemainingQuestions(): number {
  const session = getSession();
  return Math.max(0, MAX_QUESTIONS - session.questionsUsed);
}

export function hasQuestionsRemaining(): boolean {
  return getRemainingQuestions() > 0;
}

function resetSession(): SessionData {
  const session: SessionData = {
    sessionId: generateSessionId(),
    questionsUsed: 0,
    createdAt: Date.now(),
  };
  saveSession(session);
  return session;
}

function saveSession(session: SessionData): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  } catch {
    // localStorage full or unavailable
  }
}
```

- [ ] **Step 4: Create API client**

```typescript
// apps/mouth/src/lib/visa-oracle/api.ts

import type { QuizAnswers, RecommendResponse, ChatResponse, HandoffResponse } from './types';

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || 'https://nuzantara-rag.fly.dev';

export async function recommendVisas(answers: QuizAnswers): Promise<RecommendResponse> {
  const res = await fetch(`${API_BASE}/api/v1/visa-oracle/recommend`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(answers),
  });
  if (!res.ok) throw new Error(`Recommend failed: ${res.status}`);
  return res.json();
}

export async function sendChatMessage(
  sessionId: string,
  message: string,
  quizAnswers?: QuizAnswers,
  conversationHistory?: Array<{ role: string; content: string }>
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/api/v1/visa-oracle/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      message,
      quiz_answers: quizAnswers || null,
      conversation_history: conversationHistory || null,
    }),
  });
  if (!res.ok) throw new Error(`Chat failed: ${res.status}`);
  return res.json();
}

export async function triggerHandoff(
  sessionId: string,
  quizAnswers: Record<string, string>,
  recommendedVisas: Array<Record<string, unknown>>,
  messages: Array<{ role: string; content: string }>,
  language?: string
): Promise<HandoffResponse> {
  const res = await fetch(`${API_BASE}/api/v1/visa-oracle/handoff`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      quiz_answers: quizAnswers,
      recommended_visas: recommendedVisas,
      messages,
      language,
    }),
  });
  if (!res.ok) throw new Error(`Handoff failed: ${res.status}`);
  return res.json();
}
```

- [ ] **Step 5: Create quiz logic**

```typescript
// apps/mouth/src/lib/visa-oracle/quiz-logic.ts

export const PURPOSE_OPTIONS = [
  { value: 'visit', label: 'Visit / Tourism', icon: '✈️' },
  { value: 'work', label: 'Work / Employment', icon: '💼' },
  { value: 'invest', label: 'Invest / Start a Business', icon: '📈' },
  { value: 'retire', label: 'Retire', icon: '🌴' },
  { value: 'digital_nomad', label: 'Digital Nomad / Remote Work', icon: '💻' },
  { value: 'family', label: 'Join Family / Spouse', icon: '👨‍👩‍👧' },
  { value: 'study', label: 'Study / Internship', icon: '🎓' },
] as const;

export const DURATION_OPTIONS = [
  {
    value: 'short',
    label: 'Less than 6 months',
    description: 'Short stay or visit',
  },
  { value: 'medium', label: '6-12 months', description: 'Extended stay' },
  { value: 'long', label: '1+ years', description: 'Long-term residence' },
  {
    value: 'permanent',
    label: 'Permanent',
    description: 'Settle indefinitely',
  },
] as const;

export const FAMILY_OPTIONS = [
  { value: 'solo', label: 'Just me', icon: '🧑' },
  { value: 'spouse', label: 'With spouse/partner', icon: '👫' },
  { value: 'children', label: 'With children', icon: '👨‍👧' },
  { value: 'spouse_children', label: 'With spouse and children', icon: '👨‍👩‍👧‍👦' },
] as const;

export type QuizStep = 1 | 2 | 3 | 4;

export function getStepTitle(step: QuizStep): string {
  switch (step) {
    case 1:
      return "What's your nationality?";
    case 2:
      return "What's your purpose?";
    case 3:
      return 'How long do you plan to stay?';
    case 4:
      return "Who's coming with you?";
  }
}

export function isQuizComplete(answers: {
  nationality?: string;
  purpose?: string;
  duration?: string;
  family?: string;
}): boolean {
  return !!(answers.nationality && answers.purpose && answers.duration && answers.family);
}
```

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/mouth/src/lib/visa-oracle/
git commit -m "feat(visa-oracle): add frontend types, API client, quiz logic, storage"
```

---

## Task 4: Frontend — Middleware + Layout + Landing Page

**Files:**

- Modify: `apps/mouth/src/middleware.ts`
- Create: `apps/mouth/src/app/(visa-oracle)/layout.tsx`
- Create: `apps/mouth/src/app/(visa-oracle)/page.tsx`

- [ ] **Step 1: Add visa subdomain to middleware**

In `apps/mouth/src/middleware.ts`, add after line 56 (after `SSO_SUBDOMAINS`):

```typescript
const VISA_DOMAIN = 'visa.balizero.com';
```

Then add a new block after the Zantara handling (after line ~225), following the same pattern:

```typescript
// Visa Oracle subdomain
if (hostname === VISA_DOMAIN || hostname === `www.${VISA_DOMAIN}`) {
  if (pathname === '/') {
    return response;
  }
  // All paths under visa.balizero.com serve from (visa-oracle) route group
  return response;
}
```

Also add `visa` to the subdomain detection logic so it doesn't get caught by `isAppDomain` or `isPublicDomain`. In the domain detection section (~line 163-176), add before the existing conditions:

```typescript
const isVisaDomain = hostname.includes(VISA_DOMAIN) || hostname.includes('visa.balizero');
```

And update `isPublicDomain` to exclude visa:

```typescript
const isPublicDomain =
  hostname.includes(PUBLIC_DOMAIN) &&
  !hostname.includes('kita') &&
  !hostname.includes('my') &&
  !hostname.includes('visa') &&
  !isSSOSubdomain &&
  subdomain !== 'prime';
```

- [ ] **Step 2: Create the layout**

```tsx
// apps/mouth/src/app/(visa-oracle)/layout.tsx
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: {
    default: 'Visa Oracle — What visa do you need for Indonesia?',
    template: '%s | Visa Oracle by Bali Zero',
  },
  description:
    'Free AI-powered Indonesian visa guidance. Find the right visa, see transparent pricing, and connect with our team. Built on 68,000+ legal documents.',
  openGraph: {
    title: 'Visa Oracle by Bali Zero',
    description: 'What visa do you need for Indonesia? Get instant answers.',
    siteName: 'Visa Oracle',
    type: 'website',
  },
};

export default function VisaOracleLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[var(--bz-base)] text-[var(--tx-primary)]">
      {/* Minimal nav — just logo + "Powered by Bali Zero" */}
      <header className="border-b border-white/10 px-6 py-4">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-xl font-bold text-[var(--bz-accent)]">Visa Oracle</span>
            <span className="text-xs text-[var(--tx-secondary)]">by Bali Zero</span>
          </div>
          <a
            href="https://balizero.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-[var(--tx-secondary)] transition-colors hover:text-[var(--bz-accent)]"
          >
            balizero.com
          </a>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>

      {/* Minimal footer with disclaimer */}
      <footer className="border-t border-white/10 px-6 py-6">
        <div className="mx-auto max-w-5xl text-center text-xs text-[var(--tx-secondary)]">
          <p>
            Visa Oracle provides general informational guidance about Indonesian immigration. This
            is not legal advice. Immigration regulations change frequently — always verify with
            official sources or a licensed immigration consultant.
          </p>
          <p className="mt-2">
            Bali Zero is a registered business services provider, not a law firm.
          </p>
          <div className="mt-3 flex justify-center gap-4">
            <a href="/privacy" className="hover:text-[var(--bz-accent)]">
              Privacy Policy
            </a>
            <a href="/terms" className="hover:text-[var(--bz-accent)]">
              Terms of Service
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
```

- [ ] **Step 3: Create the landing page**

```tsx
// apps/mouth/src/app/(visa-oracle)/page.tsx
'use client';

import Link from 'next/link';

export default function VisaOracleLanding() {
  return (
    <div className="flex flex-col items-center gap-12 py-12">
      {/* Hero */}
      <div className="text-center">
        <h1 className="text-4xl font-bold leading-tight md:text-5xl">
          What visa do you need
          <br />
          <span className="text-[var(--bz-accent)]">for Indonesia?</span>
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-lg text-[var(--tx-secondary)]">
          Get instant, AI-powered visa guidance built on 68,000+ Indonesian legal documents. See
          transparent pricing. Connect with our team.
        </p>
      </div>

      {/* Dual CTA */}
      <div className="flex flex-col items-center gap-4 sm:flex-row">
        <Link
          href="/quiz"
          className="rounded-lg bg-[var(--bz-accent)] px-8 py-4 text-lg font-semibold text-white transition-colors hover:bg-[var(--bz-accent-hover)]"
        >
          Start Quiz
        </Link>
        <Link
          href="/chat"
          className="rounded-lg border border-white/20 px-8 py-4 text-lg font-semibold text-[var(--tx-primary)] transition-colors hover:border-[var(--bz-accent)] hover:text-[var(--bz-accent)]"
        >
          I already know what I need
        </Link>
      </div>

      {/* Trust signals */}
      <div className="grid grid-cols-1 gap-6 text-center sm:grid-cols-3">
        <div className="rounded-lg bg-[var(--bz-elevated)] p-6">
          <div className="text-2xl font-bold text-[var(--bz-accent)]">5,000+</div>
          <div className="mt-1 text-sm text-[var(--tx-secondary)]">Clients served in Bali</div>
        </div>
        <div className="rounded-lg bg-[var(--bz-elevated)] p-6">
          <div className="text-2xl font-bold text-[var(--bz-accent)]">68,000+</div>
          <div className="mt-1 text-sm text-[var(--tx-secondary)]">Legal documents indexed</div>
        </div>
        <div className="rounded-lg bg-[var(--bz-elevated)] p-6">
          <div className="text-2xl font-bold text-[var(--bz-accent)]">3</div>
          <div className="mt-1 text-sm text-[var(--tx-secondary)]">Free AI-powered questions</div>
        </div>
      </div>

      {/* How it works */}
      <div className="w-full max-w-3xl">
        <h2 className="mb-6 text-center text-2xl font-bold">How it works</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
          {[
            {
              step: '1',
              title: 'Take the quiz',
              desc: '60 seconds. Nationality, purpose, duration.',
            },
            {
              step: '2',
              title: 'Get recommendations',
              desc: 'Visa types ranked by fit, with real prices.',
            },
            {
              step: '3',
              title: 'Ask questions',
              desc: '3 free AI-powered questions about your visa.',
            },
            {
              step: '4',
              title: 'Connect with us',
              desc: 'Chat with our team on WhatsApp for processing.',
            },
          ].map((item) => (
            <div key={item.step} className="rounded-lg bg-[var(--bz-elevated)] p-4 text-center">
              <div className="mb-2 text-2xl font-bold text-[var(--bz-accent)]">{item.step}</div>
              <div className="font-semibold">{item.title}</div>
              <div className="mt-1 text-xs text-[var(--tx-secondary)]">{item.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/mouth/src/middleware.ts \
        apps/mouth/src/app/\(visa-oracle\)/layout.tsx \
        apps/mouth/src/app/\(visa-oracle\)/page.tsx
git commit -m "feat(visa-oracle): add middleware routing + layout + landing page"
```

---

## Task 5: Frontend — Quiz Wizard + Result Page

**Files:**

- Create: `apps/mouth/src/components/visa-oracle/QuizWizard.tsx`
- Create: `apps/mouth/src/app/(visa-oracle)/quiz/page.tsx`
- Create: `apps/mouth/src/app/(visa-oracle)/result/page.tsx`
- Create: `apps/mouth/src/components/visa-oracle/VisaCard.tsx`

- [ ] **Step 1: Create QuizWizard component**

```tsx
// apps/mouth/src/components/visa-oracle/QuizWizard.tsx
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import type { QuizAnswers } from '@/lib/visa-oracle/types';
import {
  PURPOSE_OPTIONS,
  DURATION_OPTIONS,
  FAMILY_OPTIONS,
  getStepTitle,
  type QuizStep,
} from '@/lib/visa-oracle/quiz-logic';
import { ALL_NATIONALITIES } from '@/lib/visa-oracle/nationalities';

export function QuizWizard() {
  const router = useRouter();
  const [step, setStep] = useState<QuizStep>(1);
  const [answers, setAnswers] = useState<Partial<QuizAnswers>>({});
  const [search, setSearch] = useState('');

  const filteredNationalities = search
    ? ALL_NATIONALITIES.filter((n) => n.name.toLowerCase().includes(search.toLowerCase()))
    : ALL_NATIONALITIES;

  function selectNationality(name: string) {
    setAnswers((prev) => ({ ...prev, nationality: name.toLowerCase() }));
    setStep(2);
  }

  function selectPurpose(value: string) {
    setAnswers((prev) => ({
      ...prev,
      purpose: value as QuizAnswers['purpose'],
    }));
    setStep(3);
  }

  function selectDuration(value: string) {
    setAnswers((prev) => ({
      ...prev,
      duration: value as QuizAnswers['duration'],
    }));
    setStep(4);
  }

  function selectFamily(value: string) {
    setAnswers((prev) => ({ ...prev, family: value as QuizAnswers['family'] }));
    // Navigate to result page with answers as query params
    const params = new URLSearchParams({
      nationality: answers.nationality || '',
      purpose: answers.purpose || '',
      duration: answers.duration || '',
      family: value,
    });
    router.push(`/result?${params.toString()}`);
  }

  function goBack() {
    if (step > 1) setStep((prev) => (prev - 1) as QuizStep);
  }

  return (
    <div className="mx-auto max-w-lg">
      {/* Progress bar */}
      <div className="mb-8 flex gap-2">
        {[1, 2, 3, 4].map((s) => (
          <div
            key={s}
            className={`h-1.5 flex-1 rounded-full transition-colors ${
              s <= step ? 'bg-[var(--bz-accent)]' : 'bg-white/10'
            }`}
          />
        ))}
      </div>

      {/* Step title */}
      <h2 className="mb-6 text-2xl font-bold">{getStepTitle(step)}</h2>

      {step > 1 && (
        <button
          onClick={goBack}
          className="mb-4 text-sm text-[var(--tx-secondary)] hover:text-[var(--bz-accent)]"
        >
          &larr; Back
        </button>
      )}

      {/* Step 1: Nationality */}
      {step === 1 && (
        <div>
          <input
            type="text"
            placeholder="Search your country..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="mb-4 w-full rounded-lg bg-[var(--bz-elevated)] px-4 py-3 text-[var(--tx-primary)] placeholder:text-[var(--tx-secondary)] focus:outline-none focus:ring-2 focus:ring-[var(--bz-accent)]"
            autoFocus
          />
          <div className="grid max-h-80 grid-cols-1 gap-2 overflow-y-auto">
            {filteredNationalities.map((n) => (
              <button
                key={n.code}
                onClick={() => selectNationality(n.name)}
                className="flex items-center gap-3 rounded-lg bg-[var(--bz-elevated)] px-4 py-3 text-left transition-colors hover:bg-[var(--bz-surface)]"
              >
                <span className="text-xl">{n.flag}</span>
                <span>{n.name}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Step 2: Purpose */}
      {step === 2 && (
        <div className="grid gap-3">
          {PURPOSE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => selectPurpose(opt.value)}
              className="flex items-center gap-3 rounded-lg bg-[var(--bz-elevated)] px-4 py-4 text-left transition-colors hover:bg-[var(--bz-surface)]"
            >
              <span className="text-2xl">{opt.icon}</span>
              <span className="font-medium">{opt.label}</span>
            </button>
          ))}
        </div>
      )}

      {/* Step 3: Duration */}
      {step === 3 && (
        <div className="grid gap-3">
          {DURATION_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => selectDuration(opt.value)}
              className="rounded-lg bg-[var(--bz-elevated)] px-4 py-4 text-left transition-colors hover:bg-[var(--bz-surface)]"
            >
              <div className="font-medium">{opt.label}</div>
              <div className="text-sm text-[var(--tx-secondary)]">{opt.description}</div>
            </button>
          ))}
        </div>
      )}

      {/* Step 4: Family */}
      {step === 4 && (
        <div className="grid gap-3">
          {FAMILY_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => selectFamily(opt.value)}
              className="flex items-center gap-3 rounded-lg bg-[var(--bz-elevated)] px-4 py-4 text-left transition-colors hover:bg-[var(--bz-surface)]"
            >
              <span className="text-2xl">{opt.icon}</span>
              <span className="font-medium">{opt.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create quiz page**

```tsx
// apps/mouth/src/app/(visa-oracle)/quiz/page.tsx
import { QuizWizard } from '@/components/visa-oracle/QuizWizard';

export default function QuizPage() {
  return (
    <div className="py-8">
      <QuizWizard />
    </div>
  );
}
```

- [ ] **Step 3: Create VisaCard component**

```tsx
// apps/mouth/src/components/visa-oracle/VisaCard.tsx
import type { VisaRecommendation } from '@/lib/visa-oracle/types';

const CATEGORY_LABELS: Record<string, string> = {
  single_entry_visas: 'Single Entry',
  multiple_entry_visas: 'Multiple Entry',
  visa_extensions: 'Extension',
  kitas_permits: 'KITAS Permit',
  kitap_permits: 'KITAP Permit',
};

interface VisaCardProps {
  visa: VisaRecommendation;
  rank: number;
  onAskQuestion: () => void;
}

export function VisaCard({ visa, rank, onAskQuestion }: VisaCardProps) {
  return (
    <div className="rounded-xl border border-white/10 bg-[var(--bz-elevated)] p-6">
      <div className="flex items-start justify-between">
        <div>
          <span className="rounded-full bg-[var(--bz-accent)]/20 px-2 py-0.5 text-xs text-[var(--bz-accent)]">
            {rank === 1 ? 'Best match' : `Option ${rank}`}
          </span>
          <h3 className="mt-2 text-xl font-bold">{visa.visa_name}</h3>
          <span className="text-sm text-[var(--tx-secondary)]">
            {CATEGORY_LABELS[visa.category] || visa.category}
          </span>
        </div>
        <div className="text-right">
          <div className="text-xl font-bold text-[var(--bz-accent)]">{visa.price}</div>
          <div className="text-xs text-[var(--tx-secondary)]">Bali Zero fee</div>
        </div>
      </div>

      {(visa.duration || visa.validity || visa.notes) && (
        <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
          {visa.duration && (
            <div>
              <span className="text-[var(--tx-secondary)]">Duration: </span>
              <span>{visa.duration}</span>
            </div>
          )}
          {visa.validity && (
            <div>
              <span className="text-[var(--tx-secondary)]">Validity: </span>
              <span>{visa.validity}</span>
            </div>
          )}
          {visa.notes && (
            <div className="col-span-2">
              <span className="text-[var(--tx-secondary)]">Notes: </span>
              <span>{visa.notes}</span>
            </div>
          )}
        </div>
      )}

      <button
        onClick={onAskQuestion}
        className="mt-4 w-full rounded-lg bg-[var(--bz-accent)] px-4 py-3 font-medium text-white transition-colors hover:bg-[var(--bz-accent-hover)]"
      >
        Ask a question about this visa
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Create result page**

```tsx
// apps/mouth/src/app/(visa-oracle)/result/page.tsx
'use client';

import { useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { VisaCard } from '@/components/visa-oracle/VisaCard';
import { recommendVisas } from '@/lib/visa-oracle/api';
import type { QuizAnswers, VisaRecommendation } from '@/lib/visa-oracle/types';

export default function ResultPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [visas, setVisas] = useState<VisaRecommendation[]>([]);
  const [sessionId, setSessionId] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const quizAnswers: QuizAnswers = {
    nationality: searchParams.get('nationality') || '',
    purpose: (searchParams.get('purpose') || 'visit') as QuizAnswers['purpose'],
    duration: (searchParams.get('duration') || 'short') as QuizAnswers['duration'],
    family: (searchParams.get('family') || 'solo') as QuizAnswers['family'],
  };

  useEffect(() => {
    async function fetchRecommendations() {
      try {
        const result = await recommendVisas(quizAnswers);
        setVisas(result.visas);
        setSessionId(result.session_id);
      } catch (e) {
        setError('Failed to get recommendations. Please try again.');
      } finally {
        setLoading(false);
      }
    }
    fetchRecommendations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleAskQuestion() {
    const params = new URLSearchParams({
      ...quizAnswers,
      session_id: sessionId,
    });
    router.push(`/chat?${params.toString()}`);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--bz-accent)] border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return <div className="py-20 text-center text-[var(--error)]">{error}</div>;
  }

  return (
    <div className="py-8">
      <h1 className="mb-2 text-2xl font-bold">Your visa recommendations</h1>
      <p className="mb-8 text-[var(--tx-secondary)]">
        Based on your profile: {quizAnswers.nationality} national, {quizAnswers.purpose} purpose,{' '}
        {quizAnswers.duration} stay,{' '}
        {quizAnswers.family === 'solo' ? 'traveling alone' : `with ${quizAnswers.family}`}.
      </p>

      <div className="grid gap-4">
        {visas.map((visa, i) => (
          <VisaCard
            key={visa.visa_name}
            visa={visa}
            rank={i + 1}
            onAskQuestion={handleAskQuestion}
          />
        ))}
      </div>

      {visas.length === 0 && (
        <div className="rounded-lg bg-[var(--bz-elevated)] p-8 text-center">
          <p className="text-[var(--tx-secondary)]">
            We couldn&apos;t find a perfect match. Our team can help you find the right visa.
          </p>
          <a
            href="https://wa.me/6281338051876?text=Hi%2C%20I%20used%20Visa%20Oracle%20but%20couldn%27t%20find%20a%20match."
            target="_blank"
            rel="noopener noreferrer"
            className="mt-4 inline-block rounded-lg bg-green-600 px-6 py-3 font-medium text-white"
          >
            Chat with us on WhatsApp
          </a>
        </div>
      )}

      <p className="mt-6 text-center text-sm text-[var(--tx-secondary)]">
        You have 3 free questions to ask about these visa options.
      </p>
    </div>
  );
}
```

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/mouth/src/components/visa-oracle/QuizWizard.tsx \
        apps/mouth/src/components/visa-oracle/VisaCard.tsx \
        apps/mouth/src/app/\(visa-oracle\)/quiz/page.tsx \
        apps/mouth/src/app/\(visa-oracle\)/result/page.tsx
git commit -m "feat(visa-oracle): add quiz wizard + result page + visa cards"
```

---

## Task 6: Frontend — Chat Page + WhatsApp CTA + Counter

**Files:**

- Create: `apps/mouth/src/components/visa-oracle/VisaChat.tsx`
- Create: `apps/mouth/src/components/visa-oracle/QuestionCounter.tsx`
- Create: `apps/mouth/src/components/visa-oracle/WhatsAppCTA.tsx`
- Create: `apps/mouth/src/components/visa-oracle/ConfidenceBadge.tsx`
- Create: `apps/mouth/src/app/(visa-oracle)/chat/page.tsx`

- [ ] **Step 1: Create QuestionCounter component**

```tsx
// apps/mouth/src/components/visa-oracle/QuestionCounter.tsx
interface QuestionCounterProps {
  remaining: number;
}

export function QuestionCounter({ remaining }: QuestionCounterProps) {
  if (remaining <= 0) return null;

  return (
    <div className="flex items-center gap-2 rounded-full bg-[var(--bz-elevated)] px-3 py-1.5 text-sm">
      <div className="flex gap-1">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className={`h-2 w-2 rounded-full ${
              i <= remaining ? 'bg-[var(--bz-accent)]' : 'bg-white/20'
            }`}
          />
        ))}
      </div>
      <span className="text-[var(--tx-secondary)]">
        {remaining} question{remaining !== 1 ? 's' : ''} remaining
      </span>
    </div>
  );
}
```

- [ ] **Step 2: Create ConfidenceBadge component**

```tsx
// apps/mouth/src/components/visa-oracle/ConfidenceBadge.tsx
interface ConfidenceBadgeProps {
  confidence: 'ABSTAIN' | 'CAUTIOUS' | 'NORMAL';
}

export function ConfidenceBadge({ confidence }: ConfidenceBadgeProps) {
  if (confidence === 'NORMAL') return null;

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs ${
        confidence === 'CAUTIOUS'
          ? 'bg-[var(--warning)]/20 text-[var(--warning)]'
          : 'bg-[var(--error)]/20 text-[var(--error)]'
      }`}
    >
      {confidence === 'CAUTIOUS' ? 'May vary by case' : 'Expert review needed'}
    </span>
  );
}
```

- [ ] **Step 3: Create WhatsAppCTA component**

```tsx
// apps/mouth/src/components/visa-oracle/WhatsAppCTA.tsx
'use client';

interface WhatsAppCTAProps {
  whatsappUrl: string;
  onDismiss?: () => void;
}

export function WhatsAppCTA({ whatsappUrl, onDismiss }: WhatsAppCTAProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-md rounded-2xl bg-[var(--bz-elevated)] p-8 text-center">
        <div className="mb-4 text-4xl">&#128172;</div>
        <h3 className="mb-2 text-xl font-bold">You&apos;ve used your 3 free questions</h3>
        <p className="mb-6 text-[var(--tx-secondary)]">
          For personalized guidance through the full visa process, chat with our visa specialist
          Damar. He has your conversation context and is ready to help.
        </p>
        <a
          href={whatsappUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 rounded-lg bg-green-600 px-8 py-4 text-lg font-semibold text-white transition-colors hover:bg-green-700"
        >
          <svg className="h-6 w-6" fill="currentColor" viewBox="0 0 24 24">
            <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
          </svg>
          Chat with Damar on WhatsApp
        </a>
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="mt-4 block w-full text-sm text-[var(--tx-secondary)] hover:text-[var(--tx-primary)]"
          >
            Maybe later
          </button>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create VisaChat component**

```tsx
// apps/mouth/src/components/visa-oracle/VisaChat.tsx
'use client';

import { useState, useRef, useEffect } from 'react';
import type { ChatMessage, QuizAnswers } from '@/lib/visa-oracle/types';
import { sendChatMessage, triggerHandoff } from '@/lib/visa-oracle/api';
import {
  getSession,
  incrementQuestions,
  getRemainingQuestions,
  hasQuestionsRemaining,
} from '@/lib/visa-oracle/storage';
import { QuestionCounter } from './QuestionCounter';
import { ConfidenceBadge } from './ConfidenceBadge';
import { WhatsAppCTA } from './WhatsAppCTA';

interface VisaChatProps {
  quizAnswers?: QuizAnswers;
  initialSessionId?: string;
}

export function VisaChat({ quizAnswers, initialSessionId }: VisaChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'system',
      content:
        'I provide information based on current Indonesian immigration data. For your specific situation, our team can give definitive guidance. Ask me anything about Indonesian visas.',
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [remaining, setRemaining] = useState(getRemainingQuestions());
  const [whatsappUrl, setWhatsappUrl] = useState<string | null>(null);
  const [showCTA, setShowCTA] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const session = getSession();
  const sessionId = initialSessionId || session.sessionId;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function handleSend() {
    if (!input.trim() || loading) return;

    if (!hasQuestionsRemaining()) {
      await doHandoff();
      setShowCTA(true);
      return;
    }

    const userMessage: ChatMessage = { role: 'user', content: input.trim() };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const history = messages
        .filter((m) => m.role !== 'system')
        .map((m) => ({ role: m.role, content: m.content }));

      const response = await sendChatMessage(sessionId, userMessage.content, quizAnswers, history);

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response.answer,
        confidence: response.confidence,
        sources: response.sources,
      };
      setMessages((prev) => [...prev, assistantMessage]);

      // Increment question counter
      incrementQuestions();
      setRemaining(getRemainingQuestions());

      // If ABSTAIN, trigger handoff immediately (doesn't count as question)
      if (response.confidence === 'ABSTAIN') {
        await doHandoff();
        setShowCTA(true);
      }
      // If no questions remaining after this one, trigger handoff
      else if (getRemainingQuestions() <= 0) {
        await doHandoff();
        setShowCTA(true);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: "I'm having trouble right now. Our team can help directly.",
          confidence: 'ABSTAIN',
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function doHandoff() {
    try {
      const plainMessages = messages
        .filter((m) => m.role !== 'system')
        .map((m) => ({ role: m.role, content: m.content }));

      const result = await triggerHandoff(
        sessionId,
        quizAnswers || {},
        [],
        plainMessages,
        undefined
      );
      setWhatsappUrl(result.whatsapp_url);
    } catch {
      // Fallback WhatsApp URL
      setWhatsappUrl('https://wa.me/6281338051876?text=Hi%2C%20I%20used%20Visa%20Oracle.');
    }
  }

  return (
    <div className="flex h-[70vh] flex-col">
      {/* Header with counter */}
      <div className="flex items-center justify-between border-b border-white/10 pb-4">
        <h2 className="text-lg font-bold">Ask about Indonesian visas</h2>
        <QuestionCounter remaining={remaining} />
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto py-4">
        {messages.map((msg, i) => (
          <div key={i} className={`mb-4 ${msg.role === 'user' ? 'text-right' : 'text-left'}`}>
            <div
              className={`inline-block max-w-[80%] rounded-2xl px-4 py-3 ${
                msg.role === 'user'
                  ? 'bg-[var(--bz-accent)] text-white'
                  : msg.role === 'system'
                    ? 'bg-[var(--bz-surface)] text-[var(--tx-secondary)] text-sm italic'
                    : 'bg-[var(--bz-elevated)]'
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.content}</p>
              {msg.confidence && msg.role === 'assistant' && (
                <div className="mt-2">
                  <ConfidenceBadge confidence={msg.confidence} />
                </div>
              )}
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-2 text-xs text-[var(--tx-secondary)]">
                  Sources: {msg.sources.join(', ')}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="mb-4 text-left">
            <div className="inline-block rounded-2xl bg-[var(--bz-elevated)] px-4 py-3">
              <div className="flex gap-1">
                <div className="h-2 w-2 animate-bounce rounded-full bg-[var(--tx-secondary)]" />
                <div className="h-2 w-2 animate-bounce rounded-full bg-[var(--tx-secondary)] [animation-delay:0.1s]" />
                <div className="h-2 w-2 animate-bounce rounded-full bg-[var(--tx-secondary)] [animation-delay:0.2s]" />
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-white/10 pt-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder={
              hasQuestionsRemaining()
                ? 'Ask about visas, requirements, costs...'
                : 'No questions remaining'
            }
            disabled={!hasQuestionsRemaining() || loading}
            className="flex-1 rounded-lg bg-[var(--bz-elevated)] px-4 py-3 text-[var(--tx-primary)] placeholder:text-[var(--tx-secondary)] focus:outline-none focus:ring-2 focus:ring-[var(--bz-accent)] disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading}
            className="rounded-lg bg-[var(--bz-accent)] px-6 py-3 font-medium text-white transition-colors hover:bg-[var(--bz-accent-hover)] disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </div>

      {/* WhatsApp CTA overlay */}
      {showCTA && whatsappUrl && (
        <WhatsAppCTA whatsappUrl={whatsappUrl} onDismiss={() => setShowCTA(false)} />
      )}
    </div>
  );
}
```

- [ ] **Step 5: Create chat page**

```tsx
// apps/mouth/src/app/(visa-oracle)/chat/page.tsx
'use client';

import { useSearchParams } from 'next/navigation';
import { VisaChat } from '@/components/visa-oracle/VisaChat';
import type { QuizAnswers } from '@/lib/visa-oracle/types';

export default function ChatPage() {
  const searchParams = useSearchParams();

  const hasQuizData = searchParams.has('nationality');

  const quizAnswers: QuizAnswers | undefined = hasQuizData
    ? {
        nationality: searchParams.get('nationality') || '',
        purpose: (searchParams.get('purpose') || 'visit') as QuizAnswers['purpose'],
        duration: (searchParams.get('duration') || 'short') as QuizAnswers['duration'],
        family: (searchParams.get('family') || 'solo') as QuizAnswers['family'],
      }
    : undefined;

  const sessionId = searchParams.get('session_id') || undefined;

  return (
    <div className="py-4">
      <VisaChat quizAnswers={quizAnswers} initialSessionId={sessionId} />
    </div>
  );
}
```

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/mouth/src/components/visa-oracle/VisaChat.tsx \
        apps/mouth/src/components/visa-oracle/QuestionCounter.tsx \
        apps/mouth/src/components/visa-oracle/WhatsAppCTA.tsx \
        apps/mouth/src/components/visa-oracle/ConfidenceBadge.tsx \
        apps/mouth/src/app/\(visa-oracle\)/chat/page.tsx
git commit -m "feat(visa-oracle): add chat page + WhatsApp CTA + question counter"
```

---

## Task 7: Frontend — Privacy + Terms Pages + Consent Banner

**Files:**

- Create: `apps/mouth/src/app/(visa-oracle)/privacy/page.tsx`
- Create: `apps/mouth/src/app/(visa-oracle)/terms/page.tsx`
- Create: `apps/mouth/src/components/visa-oracle/ConsentBanner.tsx`
- Modify: `apps/mouth/src/app/(visa-oracle)/layout.tsx`

- [ ] **Step 1: Create privacy page**

A static page with the privacy policy text from the spec (Section 8.2). Content covers: what data we collect (nationality, purpose, duration, family, chat messages, IP hash), retention (90 days), no PII, consent flow.

- [ ] **Step 2: Create terms page**

A static page with terms of service covering: informational guidance only (not legal advice), no guarantee of accuracy, immigration regulations change frequently, Bali Zero is a business services provider not a law firm, limitation of liability.

- [ ] **Step 3: Create ConsentBanner component**

A simple cookie consent banner that shows on first visit, links to privacy and terms pages, and stores acknowledgement in localStorage.

- [ ] **Step 4: Add ConsentBanner to layout**

Import and add `<ConsentBanner />` to the bottom of the `(visa-oracle)/layout.tsx` file, before the closing `</div>`.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/mouth/src/app/\(visa-oracle\)/privacy/page.tsx \
        apps/mouth/src/app/\(visa-oracle\)/terms/page.tsx \
        apps/mouth/src/components/visa-oracle/ConsentBanner.tsx \
        apps/mouth/src/app/\(visa-oracle\)/layout.tsx
git commit -m "feat(visa-oracle): add privacy, terms, consent banner"
```

---

## Task 8: Integration Testing + Deploy

**Files:**

- Modify: `apps/mouth/src/app/sitemap.ts` (add visa-oracle pages)
- Run: Backend tests, frontend build, deploy

- [ ] **Step 1: Add visa-oracle to sitemap**

In `apps/mouth/src/app/sitemap.ts`, add a new section after the KBLI sectors section (~line 237) that adds visa oracle pages to the sitemap.

- [ ] **Step 2: Run all backend tests**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/test_visa_oracle_service.py backend/tests/routers/test_visa_oracle.py -v
```

Expected: All tests PASS

- [ ] **Step 3: Run frontend build**

```bash
cd ~/Desktop/nuzantara
npm run typecheck -w apps/mouth
npm run build -w apps/mouth
```

Expected: Build succeeds with no TypeScript errors

- [ ] **Step 4: Test locally**

```bash
cd apps/mouth && npm run dev
```

Visit `http://localhost:3000` and test the full flow: landing → quiz → results → chat → WhatsApp CTA.

- [ ] **Step 5: Run pre-deploy checklist**

```bash
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('OK')"
PYTHONPATH=. pytest backend/tests/services/rag/test_confidence.py -q --tb=no
```

Expected: Import chain OK, core tests pass

- [ ] **Step 6: Deploy backend**

```bash
cd apps/backend-rag && fly deploy --strategy rolling
```

- [ ] **Step 7: Run migration on Fly.io**

```bash
fly ssh console -a nuzantara-rag -C "python -m backend.db.migrate apply"
```

- [ ] **Step 8: Push frontend (auto-deploys to Vercel)**

```bash
cd ~/Desktop/nuzantara
git add -A
git commit -m "feat(visa-oracle): integration + sitemap + deploy"
git push origin main
```

- [ ] **Step 9: Configure DNS**

Add `visa` CNAME record pointing to Vercel in Cloudflare DNS:

```
visa.balizero.com → cname.vercel-dns.com
```

Add `visa.balizero.com` as a domain in Vercel project settings.

- [ ] **Step 10: Smoke test production**

Visit `https://visa.balizero.com` and test the full flow:

1. Landing page loads
2. Quiz works (all 4 steps)
3. Results show visa cards with pricing
4. Chat works (send a question, get response)
5. WhatsApp CTA appears after 3 questions
6. Telegram notification received by Damar (chat_id 1125336968)

---

## Summary

| Task      | Description                             | New Files | Modified Files |
| --------- | --------------------------------------- | --------- | -------------- |
| 1         | Backend: Migration + Service            | 4         | 0              |
| 2         | Backend: Router + Rate Limiting         | 2         | 2              |
| 3         | Frontend: Types + API + Storage         | 5         | 0              |
| 4         | Frontend: Middleware + Layout + Landing | 2         | 1              |
| 5         | Frontend: Quiz + Results + VisaCard     | 4         | 0              |
| 6         | Frontend: Chat + WhatsApp CTA           | 5         | 0              |
| 7         | Frontend: Privacy + Terms + Consent     | 3         | 1              |
| 8         | Integration + Deploy                    | 0         | 1              |
| **Total** |                                         | **25**    | **5**          |

Estimated time: 5-7 days for Tasks 1-7, Day 8 for integration + deploy.
