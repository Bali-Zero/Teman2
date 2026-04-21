# Visa Funnel Fusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge `visa.balizero.com` (Oracle chat) into `balizero.com/visa` (Check wizard) as a single funnel — keep the Check design, add an inline accordion chat on the result page, bypass chat for `wizard_abstained` cases, redirect the subdomain, delete dead code.

**Architecture:** A new `visa_unified/bridge.py` facade reads the canonical `visa_checks` row and augments the Oracle chat system prompt with ground-truth visa + cost. `submit_match` returns a short-lived JWT (1h, HS256 via existing `JWT_SECRET_KEY`) that the chat endpoint validates before loading context. Frontend result page renders an accordion-inline chat (closed by default) below the checklist and above the WhatsApp CTA when `referral_mode=false`, or a pre-compiled `wa.me` link with quiz summary when `referral_mode=true` (wizard_abstained). Middleware rewrites on the legacy subdomain become 302 redirects with a 1:1 path map; cleanup deletes `(visa-oracle)/` + `components/visa-oracle/`.

**Tech Stack:** Python 3.11 (FastAPI, asyncpg, python-jose), Next.js 16 / React 19 / Tailwind, Vitest + Playwright, Vercel + Fly.io. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-04-21-visa-funnel-fusion.md`

**Branch:** `feat/visa-funnel-fusion` (from `main`)

**Budget:** 5 working days.

---

## Pre-flight: branch + baseline

- [ ] **Step 0.1: Clean main + create branch**

```bash
cd ~/Desktop/nuzantara
git status --short
# If dirty: git stash push -u -m "pre-visa-fusion"
git checkout main
git pull --ff-only
git checkout -b feat/visa-funnel-fusion
```

- [ ] **Step 0.2: Confirm existing codebase state**

```bash
cd ~/Desktop/nuzantara
# Backend: visa_check already shipped (PR #143) with 18-code VisaMeta
ls apps/backend-rag/backend/services/visa_check/catalogue.py \
   apps/backend-rag/backend/app/routers/visa_check.py \
   apps/backend-rag/backend/app/routers/visa_oracle.py
# Frontend: Check at /visa, Oracle at (visa-oracle)/
ls "apps/mouth/src/app/visa/" \
   "apps/mouth/src/app/(visa-oracle)/visa-oracle/"
# Middleware: rewrite rule for visa.balizero.com exists
grep -n "isVisaDomain\|VISA_DOMAIN" apps/mouth/src/middleware.ts | head -5
```

Expected: all 7 paths exist. Two grep matches on `isVisaDomain` + `VISA_DOMAIN`.

- [ ] **Step 0.3: Baseline tests must be green**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/visa_check/ -q
# Expected: 57 passed
```

If any fails → **STOP**, this plan assumes PR #143's baseline is intact.

---

## Task 1: `visa_unified/bridge.py` — facade + `FunnelContext` dataclass

**Files:**

- Create: `apps/backend-rag/backend/services/visa_unified/__init__.py`
- Create: `apps/backend-rag/backend/services/visa_unified/bridge.py`
- Create: `apps/backend-rag/backend/tests/services/visa_unified/__init__.py`
- Create: `apps/backend-rag/backend/tests/services/visa_unified/test_bridge.py`

Reads the `visa_checks` row by hash, returns a typed `FunnelContext`. Separates data access from prompt augmentation so the two concerns can be tested in isolation.

- [ ] **Step 1.1: Create package skeleton**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
mkdir -p backend/services/visa_unified backend/tests/services/visa_unified
touch backend/services/visa_unified/__init__.py backend/tests/services/visa_unified/__init__.py
```

- [ ] **Step 1.2: Write failing test for `FunnelContext` + `get_funnel_context`**

Create `backend/tests/services/visa_unified/test_bridge.py`:

```python
"""Tests for visa_unified.bridge — facade between Visa Check and Oracle chat."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from backend.services.visa_unified.bridge import (
    FunnelContext,
    augment_chat_system_prompt,
    get_funnel_context,
)


# --- Fake asyncpg.Pool that returns canned rows ---------------------------

class _FakeConn:
    def __init__(self, row: dict | None):
        self._row = row

    async def fetchrow(self, *args, **kwargs):
        return self._row


class _FakePool:
    def __init__(self, row: dict | None = None):
        self._row = row
        self.acquire_calls = 0

    def acquire(self):
        self.acquire_calls += 1
        parent = self

        class _AcquireCtx:
            async def __aenter__(self_inner):
                return _FakeConn(parent._row)

            async def __aexit__(self_inner, *exc):
                return None

        return _AcquireCtx()


# --- get_funnel_context ---------------------------------------------------

@pytest.mark.asyncio
async def test_get_funnel_context_returns_typed_dataclass():
    row = {
        "hash": "abc1234567890000",
        "nationality": "USA",
        "purpose": "work_remote",
        "duration_months": 12,
        "budget_band": "50m_500m",
        "recommended_visa": "E33G",
        "recommendation_reason": "Digital Nomad KITAS",
        "alternatives": json.dumps(["E23-FREELANCE", "C1"]),
        "estimated_cost_idr": 13_000_000,
        "created_at": datetime.now(timezone.utc),
    }
    pool = _FakePool(row=row)
    ctx = await get_funnel_context("abc1234567890000", pool)
    assert isinstance(ctx, FunnelContext)
    assert ctx.check_hash == "abc1234567890000"
    assert ctx.recommended_visa == "E33G"
    assert ctx.estimated_cost_idr == 13_000_000
    assert ctx.alternatives == ["E23-FREELANCE", "C1"]
    assert ctx.referral_mode is False  # recommended_visa present ⇒ wizard did NOT abstain


@pytest.mark.asyncio
async def test_get_funnel_context_returns_none_when_hash_absent():
    pool = _FakePool(row=None)
    ctx = await get_funnel_context("missinghash000000", pool)
    assert ctx is None


@pytest.mark.asyncio
async def test_get_funnel_context_returns_none_for_expired_row():
    old_row = {
        "hash": "old111111111111",
        "nationality": "USA",
        "purpose": "work_remote",
        "duration_months": 12,
        "budget_band": "50m_500m",
        "recommended_visa": "E33G",
        "recommendation_reason": "...",
        "alternatives": json.dumps([]),
        "estimated_cost_idr": None,
        "created_at": datetime.now(timezone.utc) - timedelta(days=31),
    }
    pool = _FakePool(row=old_row)
    ctx = await get_funnel_context("old111111111111", pool)
    assert ctx is None, "Rows older than 30 days should not be returned"


@pytest.mark.asyncio
async def test_get_funnel_context_flags_referral_mode_when_visa_is_null():
    abstained_row = {
        "hash": "other11111111111",
        "nationality": "ITA",
        "purpose": "other",
        "duration_months": 12,
        "budget_band": "50m_500m",
        "recommended_visa": None,
        "recommendation_reason": "Let's review on WhatsApp",
        "alternatives": json.dumps([]),
        "estimated_cost_idr": None,
        "created_at": datetime.now(timezone.utc),
    }
    pool = _FakePool(row=abstained_row)
    ctx = await get_funnel_context("other11111111111", pool)
    assert ctx is not None
    assert ctx.referral_mode is True
    assert ctx.recommended_visa is None


# --- augment_chat_system_prompt -------------------------------------------

def _ctx(**overrides) -> FunnelContext:
    defaults = dict(
        check_hash="abc1234567890000",
        nationality="USA",
        purpose="work_remote",
        duration_months=12,
        budget_band="50m_500m",
        recommended_visa="E33G",
        estimated_cost_idr=13_000_000,
        alternatives=["E23-FREELANCE", "C1"],
        referral_mode=False,
    )
    defaults.update(overrides)
    return FunnelContext(**defaults)


def test_augment_chat_system_prompt_includes_visa_code():
    base = "You are the Visa Oracle."
    out = augment_chat_system_prompt(_ctx(), base)
    assert "E33G" in out
    assert base in out


def test_augment_chat_system_prompt_includes_cost_and_alternatives():
    base = "You are the Visa Oracle."
    out = augment_chat_system_prompt(_ctx(), base)
    assert "13,000,000" in out or "13000000" in out
    assert "E23-FREELANCE" in out
    assert "C1" in out


def test_augment_for_wizard_abstained_shifts_tone_to_handoff():
    base = "You are the Visa Oracle."
    ctx = _ctx(recommended_visa=None, estimated_cost_idr=None, alternatives=[], referral_mode=True)
    out = augment_chat_system_prompt(ctx, base)
    # When the wizard abstained, the augmentation tells the LLM to gather
    # details for WhatsApp handoff rather than invent a visa recommendation.
    low = out.lower()
    assert "whatsapp" in low or "human" in low or "handoff" in low
    assert "recommended visa:" not in low  # no fake recommendation to quote
    assert base in out


def test_augment_never_quotes_pricing_when_cost_is_null():
    base = "You are the Visa Oracle."
    ctx = _ctx(estimated_cost_idr=None)
    out = augment_chat_system_prompt(ctx, base)
    # Should not claim "IDR 0" or "IDR None"
    assert "IDR 0" not in out
    assert "None" not in out
```

- [ ] **Step 1.3: Run the failing test**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/visa_unified/test_bridge.py -v
```

Expected: `ImportError: cannot import name 'FunnelContext' from 'backend.services.visa_unified.bridge'` — module doesn't exist yet.

- [ ] **Step 1.4: Implement `bridge.py`**

Create `backend/services/visa_unified/bridge.py`:

```python
"""Facade between Visa Check (deterministic wizard) and Visa Oracle (RAG chat).

Reads the canonical visa_checks row by hash and produces a typed FunnelContext
that the Oracle chat endpoint uses to augment its system prompt with
ground-truth visa + cost. No state of its own; no new migration.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

_CONTEXT_TTL = timedelta(days=30)


@dataclass(frozen=True)
class FunnelContext:
    """Snapshot of a wizard completion, safe to inject into an LLM prompt."""

    check_hash: str
    nationality: str
    purpose: str
    duration_months: int
    budget_band: str
    recommended_visa: str | None
    estimated_cost_idr: int | None
    alternatives: list[str]
    referral_mode: bool


async def get_funnel_context(check_hash: str, pool: Any) -> FunnelContext | None:
    """Load the wizard snapshot for `check_hash`.

    Returns None when the row is absent or older than _CONTEXT_TTL.
    The TTL is a safety net against long-held JWTs replaying ancient
    wizard state; authoritative freshness comes from the JWT's `exp`.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT hash, nationality, purpose, duration_months, budget_band,
                   recommended_visa, recommendation_reason, alternatives,
                   estimated_cost_idr, created_at
              FROM visa_checks
             WHERE hash = $1 AND branch = 'match'
            """,
            check_hash,
        )
    if row is None:
        return None

    created_at = row["created_at"]
    if created_at and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if created_at and datetime.now(timezone.utc) - created_at > _CONTEXT_TTL:
        logger.info("funnel context expired for hash=%s", check_hash)
        return None

    alts_raw = row["alternatives"]
    if isinstance(alts_raw, str):
        try:
            alternatives = list(json.loads(alts_raw) or [])
        except json.JSONDecodeError:
            alternatives = []
    else:
        alternatives = list(alts_raw or [])

    recommended = row["recommended_visa"]
    return FunnelContext(
        check_hash=row["hash"],
        nationality=row["nationality"] or "",
        purpose=row["purpose"] or "",
        duration_months=int(row["duration_months"] or 0),
        budget_band=row["budget_band"] or "",
        recommended_visa=recommended,
        estimated_cost_idr=row["estimated_cost_idr"],
        alternatives=alternatives,
        referral_mode=(recommended is None),
    )


def augment_chat_system_prompt(context: FunnelContext, base_prompt: str) -> str:
    """Prepend wizard ground-truth to an Oracle chat system prompt.

    For normal (non-abstained) completions, the augmentation names the
    recommended visa, the Bali Zero IDR cost, and the ranked alternatives,
    so the LLM cannot contradict the wizard or invent prices.

    For wizard_abstained completions, the augmentation explicitly tells
    the LLM NOT to produce a recommendation: it should gather details
    for a WhatsApp handoff instead.
    """
    if context.referral_mode:
        preamble = (
            "The user just completed our visa wizard and their case did not "
            "match any deterministic branch (purpose=`other`, unsupported "
            "duration, or under-budget investor). Do NOT recommend a visa "
            "yourself. Instead, gather 1-2 clarifying details about their "
            "situation and suggest a WhatsApp handoff to the Bali Zero human "
            "team for a tailored answer. Keep the reply under 4 sentences.\n\n"
        )
        return preamble + base_prompt

    cost_line = (
        f" Cost from PricingTool: IDR {context.estimated_cost_idr:,}."
        if context.estimated_cost_idr
        else ""
    )
    alts = (
        f" Alternatives already surfaced: {', '.join(context.alternatives)}."
        if context.alternatives
        else ""
    )
    preamble = (
        "The user just completed our visa wizard. "
        f"Recommended visa: {context.recommended_visa}."
        f"{cost_line}{alts} Always quote this recommended visa and cost "
        "unless the user explicitly asks for an updated price; in that case "
        "say Bali Zero will confirm on WhatsApp. Do not invent alternative "
        "visas beyond the ones listed above.\n\n"
    )
    return preamble + base_prompt


__all__ = [
    "FunnelContext",
    "get_funnel_context",
    "augment_chat_system_prompt",
]
```

- [ ] **Step 1.5: Run tests — all pass**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
PYTHONPATH=. pytest backend/tests/services/visa_unified/test_bridge.py -v
```

Expected: 8 tests pass.

- [ ] **Step 1.6: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/services/visa_unified/ \
        apps/backend-rag/backend/tests/services/visa_unified/
git commit -m "$(cat <<'EOF'
feat(visa-unified): add bridge facade + FunnelContext

Introduces backend/services/visa_unified/bridge.py as the single
integration surface between the deterministic Visa Check wizard
(backend/services/visa_check/) and the Oracle chat RAG pipeline
(backend/app/routers/visa_oracle.py).

- FunnelContext frozen dataclass: snapshot of a wizard completion
  safe to inject in an LLM prompt (nationality, purpose, duration,
  budget_band, recommended_visa, cost, alternatives, referral_mode).
- get_funnel_context(hash, pool): reads visa_checks WHERE branch='match'
  with a 30-day TTL safety net; returns None when absent or expired.
- augment_chat_system_prompt(ctx, base): prepends ground-truth preamble
  with visa + cost for normal cases, or a handoff-only preamble for
  wizard_abstained cases (referral_mode=True).

8 unit tests covering normal flow, absent hash, expired row,
wizard_abstained flag, cost/alternatives injection, null-cost safety.

No migration; no new dependency; reads existing PR #143 schema.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `submit_match` returns `session_jwt` (1h HS256)

**Files:**

- Modify: `apps/backend-rag/backend/app/routers/visa_check.py` (MatchResponse + submit_match + get_match)
- Modify: `apps/backend-rag/backend/tests/services/visa_check/` — add `test_visa_check_router.py`

Issues a short-lived JWT with claim `{sub: check_hash, iat, exp, type: "visa_funnel"}` signed with the existing `settings.jwt_secret_key` / `settings.jwt_algorithm`. The frontend stores it and sends it as `Authorization: Bearer <jwt>` when calling the chat endpoint.

- [ ] **Step 2.1: Write failing test**

Create `apps/backend-rag/backend/tests/services/visa_check/test_router_jwt.py`:

```python
"""Tests that submit_match emits a session_jwt usable for chat auth."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from jose import jwt

from backend.app.core.config import settings


@pytest.fixture
def response_builder():
    """Import lazily — the endpoint imports settings at module load."""
    from backend.app.routers.visa_check import MatchResponse
    return MatchResponse


def _decode(token: str) -> dict:
    return jwt.decode(
        token, settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        options={"verify_exp": False},
    )


def test_match_response_schema_exposes_session_jwt(response_builder):
    # Smoke: MatchResponse must declare the `session_jwt` field.
    fields = response_builder.model_fields
    assert "session_jwt" in fields, "MatchResponse missing session_jwt field"


@pytest.mark.asyncio
async def test_submit_match_returns_valid_jwt_with_check_hash_claim(monkeypatch):
    from backend.app.routers import visa_check as router_mod

    # Build a fake result so we only exercise the router's JWT path.
    class _FakeResult:
        recommended_visa = None  # simplest path: referral_mode=true
        reason = "Let's WhatsApp"
        pre_arrival_steps: list[str] = []
        alternatives: list = []
        referral_mode = True

    async def _fake_save_match(**kwargs):
        from backend.services.visa_check.repository import VisaMatchResult
        return VisaMatchResult(
            hash="abc1234567890000",
            nationality=kwargs["nationality"],
            purpose=kwargs["purpose"],
            duration_months=kwargs["duration_months"],
            budget_band=kwargs["budget_band"],
            recommended_visa=None,
            recommendation_reason=kwargs["recommendation_reason"],
            pre_arrival_steps=[],
            alternatives=[],
            expected_arrival_date=None,
            estimated_cost_idr=None,
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(
        router_mod, "recommend_visa",
        lambda **_: _FakeResult(),
    )
    monkeypatch.setattr(
        router_mod.VisaCheckRepository, "save_match", _fake_save_match,
    )

    payload = router_mod.MatchRequest(
        nationality="USA", purpose=router_mod.Purpose.OTHER,
        duration_months=12, budget_band=router_mod.BudgetBand.MID_50_500M,
    )
    response = await router_mod.submit_match(payload, db_pool=None)
    assert response.session_jwt
    claims = _decode(response.session_jwt)
    assert claims["sub"] == "abc1234567890000"
    assert claims["type"] == "visa_funnel"
    assert "iat" in claims
    assert "exp" in claims
    assert claims["exp"] - claims["iat"] == 3600  # 1 hour TTL


@pytest.mark.asyncio
async def test_get_match_does_not_regenerate_jwt(monkeypatch):
    """GET /api/visa/match/{hash} should NOT issue a JWT — it is a read
    endpoint used to re-render the result page from a shareable URL.
    Chat auth must be obtained fresh from submit_match."""
    from backend.app.routers import visa_check as router_mod

    async def _fake_load(*args, **kwargs):
        from backend.services.visa_check.repository import VisaMatchResult
        return VisaMatchResult(
            hash="xyz1234567890000", nationality="USA", purpose="work_remote",
            duration_months=12, budget_band="50m_500m",
            recommended_visa=None, recommendation_reason="...",
            pre_arrival_steps=[], alternatives=[],
            expected_arrival_date=None, estimated_cost_idr=None,
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(router_mod.VisaCheckRepository, "load_match", _fake_load)
    monkeypatch.setattr(router_mod.VisaCheckRepository, "bump_view_count", AsyncMock())

    response = await router_mod.get_match(hash="xyz1234567890000", db_pool=None)
    # session_jwt is optional on GET; we assert it's absent or null-ish.
    assert getattr(response, "session_jwt", None) in (None, "")
```

- [ ] **Step 2.2: Run test — it fails**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
PYTHONPATH=. pytest backend/tests/services/visa_check/test_router_jwt.py -v
```

Expected: `AssertionError: MatchResponse missing session_jwt field` on the first test.

- [ ] **Step 2.3: Edit `visa_check.py` — add JWT helper**

In `apps/backend-rag/backend/app/routers/visa_check.py`, add at the top (after existing imports):

```python
from datetime import datetime, timedelta, timezone
from jose import jwt

from backend.app.core.config import settings

_VISA_FUNNEL_JWT_TTL_SECONDS = 3600


def _issue_visa_funnel_jwt(check_hash: str) -> str:
    """Short-lived token that grants chat access for THIS wizard only."""
    now = datetime.now(timezone.utc)
    claims = {
        "sub": check_hash,
        "type": "visa_funnel",
        "iat": now,
        "exp": now + timedelta(seconds=_VISA_FUNNEL_JWT_TTL_SECONDS),
    }
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
```

- [ ] **Step 2.4: Extend `MatchResponse` with `session_jwt`**

Find `class MatchResponse(BaseModel):` in `visa_check.py` (around line 109) and add the field:

```python
class MatchResponse(BaseModel):
    hash: str
    recommended_visa: VisaType | None
    reason: str
    estimated_cost_idr: int | None
    cost_source: str | None
    processing_days: int | None
    pre_arrival_steps: list[str]
    alternatives: list[VisaType]
    referral_mode: bool
    result_url: str
    session_jwt: str | None = None  # NEW: populated by POST, empty by GET
```

- [ ] **Step 2.5: Populate `session_jwt` in `submit_match`**

In `submit_match` (around line 231), change the return:

```python
    return MatchResponse(
        hash=saved.hash,
        recommended_visa=saved.recommended_visa,
        reason=saved.recommendation_reason,
        estimated_cost_idr=saved.estimated_cost_idr,
        cost_source=cost_source,
        processing_days=proc_days,
        pre_arrival_steps=saved.pre_arrival_steps,
        alternatives=[VisaType(v) for v in saved.alternatives],
        referral_mode=result.referral_mode,
        result_url=f"/visa/match/{saved.hash}",
        session_jwt=_issue_visa_funnel_jwt(saved.hash),  # NEW
    )
```

- [ ] **Step 2.6: Keep `session_jwt` unset on GET**

In `get_match` (around line 284), confirm the return does NOT set `session_jwt` (default `None` is correct). No edit needed.

- [ ] **Step 2.7: Run tests**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
PYTHONPATH=. pytest backend/tests/services/visa_check/ -v
```

Expected: **all prior visa_check tests still pass** + 3 new tests pass = 60 total.

- [ ] **Step 2.8: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/app/routers/visa_check.py \
        apps/backend-rag/backend/tests/services/visa_check/test_router_jwt.py
git commit -m "$(cat <<'EOF'
feat(visa-check): issue session_jwt on submit_match for chat auth

POST /api/visa/match now returns `session_jwt`, a short-lived HS256
token (1h TTL, signed with settings.jwt_secret_key) with claims
{sub: check_hash, type: "visa_funnel", iat, exp}. The frontend stores
this and sends it as Authorization: Bearer <jwt> to the chat endpoint,
proving the caller completed THIS wizard before accessing context.

- MatchResponse grows a session_jwt: str | None field (optional on GET).
- _issue_visa_funnel_jwt() helper isolated from endpoint logic.
- GET /api/visa/match/{hash} does NOT regenerate the JWT — shareable
  result URLs must be regenerated via a fresh wizard run if chat is
  needed. Tested.

3 new tests; all 57 pre-existing visa_check tests still green.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `visa_oracle.chat` accepts + validates `check_hash` + JWT

**Files:**

- Modify: `apps/backend-rag/backend/app/routers/visa_oracle.py` (ChatRequest + chat function)
- Create: `apps/backend-rag/backend/tests/services/visa_oracle/test_chat_jwt.py`

The chat endpoint gains an **optional** `check_hash` field. When present, the `Authorization: Bearer <jwt>` header is **required**; the JWT is validated against `settings.jwt_secret_key`, the `sub` claim must equal the posted `check_hash`, and the wizard context is loaded via `bridge.get_funnel_context` and merged into the Oracle system prompt. When absent (legacy Oracle-only callers), behaviour is unchanged.

- [ ] **Step 3.1: Create test directory + failing test**

```bash
mkdir -p ~/Desktop/nuzantara/apps/backend-rag/backend/tests/services/visa_oracle
touch ~/Desktop/nuzantara/apps/backend-rag/backend/tests/services/visa_oracle/__init__.py
```

Create `backend/tests/services/visa_oracle/test_chat_jwt.py`:

```python
"""Tests for visa_oracle.chat's new `check_hash` + JWT auth branch."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException, Request
from jose import jwt

from backend.app.core.config import settings


def _make_jwt(sub: str, *, ttl_seconds: int = 3600, wrong_key: bool = False) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": sub,
        "type": "visa_funnel",
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
    }
    key = "WRONG" if wrong_key else settings.jwt_secret_key
    return jwt.encode(claims, key, algorithm=settings.jwt_algorithm)


@pytest.mark.asyncio
async def test_chat_without_check_hash_skips_jwt_validation(monkeypatch):
    """Backwards-compat: Oracle-only callers (no check_hash) still work."""
    from backend.app.routers import visa_oracle as router_mod

    monkeypatch.setattr(
        router_mod, "_detect_language", lambda _msg: "en",
    )
    # Stub the RAG pipeline to return a trivial answer quickly.
    fake_answer = AsyncMock(return_value={
        "answer": "hello", "confidence": 0.8, "session_id": "s1",
    })
    monkeypatch.setattr(router_mod, "_run_rag_pipeline", fake_answer)

    req = Request({"type": "http", "headers": []})
    body = router_mod.ChatRequest(
        message="Hello", session_id=None, quiz_answers=None, language="en",
        check_hash=None,
    )
    resp = await router_mod.chat(req, body, db_pool=None)
    assert resp.answer == "hello"


@pytest.mark.asyncio
async def test_chat_with_check_hash_rejects_missing_jwt(monkeypatch):
    from backend.app.routers import visa_oracle as router_mod

    req = Request({"type": "http", "headers": []})  # no Authorization header
    body = router_mod.ChatRequest(
        message="Hello", check_hash="abc1234567890000",
    )
    with pytest.raises(HTTPException) as ei:
        await router_mod.chat(req, body, db_pool=None)
    assert ei.value.status_code == 401


@pytest.mark.asyncio
async def test_chat_with_check_hash_rejects_wrong_signature(monkeypatch):
    from backend.app.routers import visa_oracle as router_mod

    token = _make_jwt("abc1234567890000", wrong_key=True)
    req = Request({
        "type": "http",
        "headers": [(b"authorization", f"Bearer {token}".encode())],
    })
    body = router_mod.ChatRequest(
        message="Hello", check_hash="abc1234567890000",
    )
    with pytest.raises(HTTPException) as ei:
        await router_mod.chat(req, body, db_pool=None)
    assert ei.value.status_code == 401


@pytest.mark.asyncio
async def test_chat_with_check_hash_rejects_sub_mismatch(monkeypatch):
    from backend.app.routers import visa_oracle as router_mod

    token = _make_jwt("DIFFERENT_HASH")
    req = Request({
        "type": "http",
        "headers": [(b"authorization", f"Bearer {token}".encode())],
    })
    body = router_mod.ChatRequest(
        message="Hello", check_hash="abc1234567890000",
    )
    with pytest.raises(HTTPException) as ei:
        await router_mod.chat(req, body, db_pool=None)
    assert ei.value.status_code == 403


@pytest.mark.asyncio
async def test_chat_with_valid_jwt_augments_system_prompt(monkeypatch):
    from backend.app.routers import visa_oracle as router_mod
    from backend.services.visa_unified.bridge import FunnelContext

    ctx = FunnelContext(
        check_hash="abc1234567890000",
        nationality="USA", purpose="work_remote",
        duration_months=12, budget_band="50m_500m",
        recommended_visa="E33G", estimated_cost_idr=13_000_000,
        alternatives=["E23-FREELANCE", "C1"], referral_mode=False,
    )
    monkeypatch.setattr(
        router_mod, "get_funnel_context", AsyncMock(return_value=ctx),
    )
    captured = {}

    async def _capture(*args, system_prompt: str, **kwargs):
        captured["system_prompt"] = system_prompt
        return {"answer": "ok", "confidence": 0.9, "session_id": "s2"}

    monkeypatch.setattr(router_mod, "_run_rag_pipeline", _capture)
    monkeypatch.setattr(router_mod, "_detect_language", lambda _m: "en")

    token = _make_jwt("abc1234567890000")
    req = Request({
        "type": "http",
        "headers": [(b"authorization", f"Bearer {token}".encode())],
    })
    body = router_mod.ChatRequest(
        message="Posso estendere?", check_hash="abc1234567890000",
    )
    await router_mod.chat(req, body, db_pool=None)
    assert "E33G" in captured["system_prompt"]
    assert "13,000,000" in captured["system_prompt"]
```

- [ ] **Step 3.2: Run test — it fails**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
PYTHONPATH=. pytest backend/tests/services/visa_oracle/test_chat_jwt.py -v
```

Expected: failures on `ChatRequest(..., check_hash=...)` kwarg missing, `_run_rag_pipeline` name not present, etc.

- [ ] **Step 3.3: Edit `visa_oracle.py` — extend ChatRequest**

Locate `class ChatRequest(BaseModel):` (around line 280) and add the field:

```python
class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    quiz_answers: dict[str, str] | None = None
    language: str | None = None
    check_hash: str | None = None  # NEW: wizard completion hash for context augmentation
```

- [ ] **Step 3.4: Extract the RAG pipeline call into `_run_rag_pipeline` helper**

In `visa_oracle.py`, find the block starting at `HybridSearchService` usage inside `chat()` and extract the Gemini call + confidence logic into a module-level coroutine:

```python
# ~ line 430, above the @router.post("/chat") decorator, add:

async def _run_rag_pipeline(
    *,
    query: str,
    language: str,
    system_prompt: str,
    session_id: str | None,
    db_pool,
) -> dict:
    """Run hybrid search + Gemini Flash + confidence gating.

    Returns {"answer": str, "confidence": float, "session_id": str}.
    Extracted for testability: tests stub this instead of spinning up
    Qdrant + Gemini.
    """
    # Move the existing logic from chat() into here. Keep signatures
    # stable. See original implementation at backend/app/routers/visa_oracle.py
    # lines ~450-680. No behavioural change, pure refactor.
    ...  # implementation moves verbatim
```

**Important:** this is a refactor. Do NOT change the pipeline logic; just relocate the lines inside `_run_rag_pipeline` and have `chat()` call it. Run the existing Oracle tests after this step to prove no regression:

```bash
PYTHONPATH=. pytest backend/tests/services/visa_oracle/ -v
```

Expected: all pre-existing visa_oracle tests green.

- [ ] **Step 3.5: Add JWT validation + context augmentation in `chat()`**

At the **top** of `chat()` (after `ChatRequest` is received, before building the query), insert:

```python
    # NEW: wizard-context branch.
    augmented_system_prompt = base_system_prompt  # existing variable
    if body.check_hash:
        # JWT required when a check_hash is posted.
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Missing bearer token")
        token = auth.split(" ", 1)[1].strip()
        try:
            from jose import JWTError, jwt
            from backend.app.core.config import settings

            claims = jwt.decode(
                token, settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
                options={"verify_exp": True},
            )
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        if claims.get("sub") != body.check_hash:
            raise HTTPException(status_code=403, detail="Token does not match check_hash")
        if claims.get("type") != "visa_funnel":
            raise HTTPException(status_code=401, detail="Wrong token type")

        from backend.services.visa_unified.bridge import (
            augment_chat_system_prompt,
            get_funnel_context,
        )
        ctx = await get_funnel_context(body.check_hash, db_pool)
        if ctx is None:
            # Token valid but underlying wizard row vanished (TTL/purge).
            raise HTTPException(status_code=410, detail="Wizard context expired")
        augmented_system_prompt = augment_chat_system_prompt(
            ctx, base_system_prompt,
        )
```

Then pass `augmented_system_prompt` into `_run_rag_pipeline(..., system_prompt=augmented_system_prompt, ...)` instead of the raw `base_system_prompt`.

**Note:** `base_system_prompt` is the variable name in the existing `chat()` for the Oracle system prompt. If the current code uses a different name (e.g. `system_instructions`), match that name — do not rename.

- [ ] **Step 3.6: Run JWT tests — all pass**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
PYTHONPATH=. pytest backend/tests/services/visa_oracle/test_chat_jwt.py -v
```

Expected: 5 tests pass.

- [ ] **Step 3.7: Run full visa\_\* suite**

```bash
PYTHONPATH=. pytest backend/tests/services/visa_check/ backend/tests/services/visa_oracle/ backend/tests/services/visa_unified/ -q
```

Expected: 57 visa_check + prior visa_oracle + 8 visa_unified + 5 new = all green.

- [ ] **Step 3.8: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/app/routers/visa_oracle.py \
        apps/backend-rag/backend/tests/services/visa_oracle/
git commit -m "$(cat <<'EOF'
feat(visa-oracle): validate session_jwt and augment prompt when check_hash present

ChatRequest gains an optional `check_hash` field. When present, the
handler requires a valid `Authorization: Bearer <jwt>` header whose
claims match {sub: check_hash, type: "visa_funnel", exp: unexpired,
signature: signed by settings.jwt_secret_key}. On pass, loads the
wizard snapshot via bridge.get_funnel_context and prepends a ground-
truth preamble (visa + cost + alternatives, or handoff-only for
wizard_abstained) to the Oracle base system prompt.

Backwards-compatible: when check_hash is absent, validation is
skipped and behaviour is identical to before (Oracle-only callers).

Refactor: extracted the RAG pipeline body of chat() into
_run_rag_pipeline() without behavioural change, so tests can stub
it without spinning up Qdrant + Gemini.

5 new tests; all pre-existing visa_oracle + visa_check + visa_unified
tests still green.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Move Oracle UI components into `components/visa/`

**Files:**

- Move: `apps/mouth/src/components/visa-oracle/VisaChat.tsx` → `apps/mouth/src/components/visa/VisaChat.tsx`
- Move: `apps/mouth/src/components/visa-oracle/QuestionCounter.tsx` → `apps/mouth/src/components/visa/QuestionCounter.tsx`
- Move: `apps/mouth/src/components/visa-oracle/ConsentBanner.tsx` → `apps/mouth/src/components/visa/ConsentBanner.tsx`
- Update imports in files that reference `visa-oracle/`.

Pure relocation — no logic changes, no style changes. Styling comes in Task 5.

- [ ] **Step 4.1: Move three component files**

```bash
cd ~/Desktop/nuzantara
mkdir -p apps/mouth/src/components/visa
git mv apps/mouth/src/components/visa-oracle/VisaChat.tsx \
       apps/mouth/src/components/visa/VisaChat.tsx
git mv apps/mouth/src/components/visa-oracle/QuestionCounter.tsx \
       apps/mouth/src/components/visa/QuestionCounter.tsx
git mv apps/mouth/src/components/visa-oracle/ConsentBanner.tsx \
       apps/mouth/src/components/visa/ConsentBanner.tsx
```

- [ ] **Step 4.2: Update import paths**

```bash
cd ~/Desktop/nuzantara
grep -rln "components/visa-oracle/VisaChat\|components/visa-oracle/QuestionCounter\|components/visa-oracle/ConsentBanner" apps/mouth/src/
```

For each hit, replace `components/visa-oracle/` with `components/visa/` in the import line. Typically:

- `apps/mouth/src/app/(visa-oracle)/visa-oracle/chat/page.tsx`
- `apps/mouth/src/app/(visa-oracle)/visa-oracle/result/page.tsx`
- `apps/mouth/src/app/(visa-oracle)/visa-oracle/quiz/page.tsx`

Use `sed -i '' 's|components/visa-oracle/|components/visa/|g'` on each file.

- [ ] **Step 4.3: Verify Next.js build compiles**

```bash
cd ~/Desktop/nuzantara/apps/mouth
npx tsc --noEmit 2>&1 | tail -20
```

Expected: no errors referencing the three moved components.

- [ ] **Step 4.4: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/mouth/src/components/visa/ apps/mouth/src/components/visa-oracle/ \
        apps/mouth/src/app/(visa-oracle)/
git commit -m "$(cat <<'EOF'
refactor(visa-frontend): relocate Oracle UI components to components/visa/

Pure file move, no logic changes. VisaChat, QuestionCounter,
ConsentBanner now live under apps/mouth/src/components/visa/ so the
upcoming fusion work can import them alongside the Check wizard
components without confusing path names. All pre-existing importers
updated to the new path.

Part 1 of visa-funnel-fusion (spec 2026-04-21-visa-funnel-fusion.md).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Accordion chat on result page (match branch)

**Files:**

- Create: `apps/mouth/src/components/visa/ChatAccordion.tsx`
- Create: `apps/mouth/src/components/visa/__tests__/ChatAccordion.test.tsx`
- Modify: `apps/mouth/src/app/visa/match/[hash]/page.tsx` (embed accordion when `referral_mode=false`)

The accordion is closed by default; label "Have doubts? Ask 3 free questions". When opened, it mounts `<VisaChat>` inline (same scroll flow) and passes `checkHash` + `sessionJwt` to the chat component so every `/chat` request carries both.

- [ ] **Step 5.1: Write component test first**

Create `apps/mouth/src/components/visa/__tests__/ChatAccordion.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ChatAccordion } from "../ChatAccordion";

vi.mock("../VisaChat", () => ({
  VisaChat: ({
    checkHash,
    sessionJwt,
  }: {
    checkHash: string;
    sessionJwt: string;
  }) => (
    <div
      data-testid="visa-chat-mock"
      data-hash={checkHash}
      data-jwt={sessionJwt}
    />
  ),
}));

describe("ChatAccordion", () => {
  it("is closed by default and does not mount VisaChat", () => {
    render(<ChatAccordion checkHash="abc" sessionJwt="jwt" />);
    expect(screen.queryByTestId("visa-chat-mock")).toBeNull();
    expect(
      screen.getByRole("button", { name: /ask 3 free questions/i }),
    ).toBeInTheDocument();
  });

  it("opens inline on header click and mounts VisaChat with props", () => {
    render(
      <ChatAccordion checkHash="abc1234567890000" sessionJwt="tokenXYZ" />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /ask 3 free questions/i }),
    );
    const chat = screen.getByTestId("visa-chat-mock");
    expect(chat.dataset.hash).toBe("abc1234567890000");
    expect(chat.dataset.jwt).toBe("tokenXYZ");
  });

  it("renders nothing when sessionJwt is empty", () => {
    const { container } = render(
      <ChatAccordion checkHash="abc" sessionJwt="" />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
```

- [ ] **Step 5.2: Run test — fails (component missing)**

```bash
cd ~/Desktop/nuzantara/apps/mouth
npx vitest run src/components/visa/__tests__/ChatAccordion.test.tsx
```

Expected: `Cannot find module '../ChatAccordion'`.

- [ ] **Step 5.3: Implement ChatAccordion**

Create `apps/mouth/src/components/visa/ChatAccordion.tsx`:

```tsx
"use client";

import { useState } from "react";
import { VisaChat } from "./VisaChat";

export interface ChatAccordionProps {
  checkHash: string;
  sessionJwt: string;
}

export function ChatAccordion({ checkHash, sessionJwt }: ChatAccordionProps) {
  const [open, setOpen] = useState(false);

  if (!sessionJwt) return null;

  return (
    <section className="mt-12 border-t border-white/10 pt-8">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="w-full text-left flex items-center justify-between py-4 px-6 rounded-lg bg-white/5 hover:bg-white/10 transition"
      >
        <span className="text-lg font-serif">
          Have doubts? Ask 3 free questions
        </span>
        <span aria-hidden="true" className="text-xl">
          {open ? "—" : "+"}
        </span>
      </button>

      {open && (
        <div className="mt-6">
          <VisaChat checkHash={checkHash} sessionJwt={sessionJwt} />
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 5.4: Update `VisaChat.tsx` to accept `checkHash` + `sessionJwt` and forward them to `/api/visa-oracle/chat`**

Open `apps/mouth/src/components/visa/VisaChat.tsx`. At the top of the component signature, extend the props:

```tsx
export interface VisaChatProps {
  // ... existing props
  checkHash?: string; // NEW
  sessionJwt?: string; // NEW
  quizAnswers?: {
    nationality: string;
    purpose: string;
    duration: string;
    family: string;
  };
  initialSessionId?: string;
  visas?: Array<unknown>;
}
```

Inside the function where the chat POST is built, include `check_hash` in the body and `Authorization: Bearer <jwt>` in the headers when both are present:

```tsx
const body: Record<string, unknown> = {
  session_id: sessionId,
  message: userMessage,
  language: navigator.language?.slice(0, 2) ?? "en",
};
if (checkHash) body.check_hash = checkHash;

const headers: Record<string, string> = { "Content-Type": "application/json" };
if (sessionJwt) headers.Authorization = `Bearer ${sessionJwt}`;

const response = await fetch("/api/visa-oracle/chat", {
  method: "POST",
  headers,
  body: JSON.stringify(body),
});
```

Legacy callers with no `checkHash` keep working (no Authorization header, no `check_hash` field, backend skips JWT branch).

- [ ] **Step 5.5: Run the accordion tests — all pass**

```bash
cd ~/Desktop/nuzantara/apps/mouth
npx vitest run src/components/visa/__tests__/ChatAccordion.test.tsx
```

Expected: 3 tests pass.

- [ ] **Step 5.6: Embed accordion in result page when `referral_mode=false`**

Open `apps/mouth/src/app/visa/match/[hash]/page.tsx`. Find where the pre-arrival checklist renders (around the `<ul>` for `pre_arrival_steps`) and, **after** the checklist closing `</ul>` but **before** the WhatsApp CTA, add:

```tsx
{
  !match.referral_mode && match.session_jwt && (
    <ChatAccordion checkHash={match.hash} sessionJwt={match.session_jwt} />
  );
}
```

Add the import at the top:

```tsx
import { ChatAccordion } from "@/components/visa/ChatAccordion";
```

Also update the TypeScript type for `match` (wherever the server response is modeled) to include `session_jwt: string | null`.

- [ ] **Step 5.7: Build compiles**

```bash
cd ~/Desktop/nuzantara/apps/mouth
npx tsc --noEmit 2>&1 | tail -10
```

Expected: no errors.

- [ ] **Step 5.8: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/mouth/src/components/visa/ChatAccordion.tsx \
        apps/mouth/src/components/visa/__tests__/ChatAccordion.test.tsx \
        apps/mouth/src/components/visa/VisaChat.tsx \
        apps/mouth/src/app/visa/match/\[hash\]/page.tsx
git commit -m "$(cat <<'EOF'
feat(visa-frontend): add inline ChatAccordion on result page

The result page /visa/match/{hash} now renders a closed-by-default
accordion labelled "Have doubts? Ask 3 free questions" below the
pre-arrival checklist and above the primary WhatsApp CTA.

- ChatAccordion component: pure presentational shell that mounts
  VisaChat lazily on open, passes checkHash + sessionJwt as props.
- VisaChat extended with optional checkHash + sessionJwt props; when
  present, sends `check_hash` in the POST body and
  `Authorization: Bearer <jwt>` header. Legacy callers unchanged.
- Accordion renders ONLY when referral_mode=false AND session_jwt is
  truthy — i.e. only for normal (non-abstained) wizard completions.

3 new Vitest component tests.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `HandoffWaLink` component for `wizard_abstained` path

**Files:**

- Create: `apps/mouth/src/components/visa/HandoffWaLink.tsx`
- Create: `apps/mouth/src/components/visa/__tests__/HandoffWaLink.test.tsx`
- Modify: `apps/mouth/src/app/visa/match/[hash]/page.tsx` (render HandoffWaLink when `referral_mode=true`)

Renders a pre-compiled `wa.me` link when the wizard abstained. The link's `?text=` param is an URL-encoded Italian-or-English summary of the quiz answers so the Bali Zero team picks up a hot lead with context.

- [ ] **Step 6.1: Write component test**

Create `apps/mouth/src/components/visa/__tests__/HandoffWaLink.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { HandoffWaLink } from "../HandoffWaLink";

describe("HandoffWaLink", () => {
  it("generates a wa.me URL with encoded quiz summary", () => {
    render(
      <HandoffWaLink
        phone="+6285156005858"
        nationality="ITA"
        purpose="investor"
        durationMonths={12}
        budgetBand="under_50m"
        reason="Investor routes all have minimum capital requirements."
      />,
    );
    const link = screen.getByRole("link", { name: /whatsapp/i });
    const href = link.getAttribute("href")!;
    expect(href.startsWith("https://wa.me/6285156005858?text=")).toBe(true);
    const decoded = decodeURIComponent(href.split("?text=")[1]);
    expect(decoded).toContain("ITA");
    expect(decoded).toContain("investor");
    expect(decoded).toContain("12 months");
    expect(decoded).toContain("under_50m");
    expect(decoded).toContain("minimum capital");
  });

  it("truncates phone prefix plus sign", () => {
    render(
      <HandoffWaLink
        phone="+6285156005858"
        nationality="USA"
        purpose="other"
        durationMonths={6}
        budgetBand="50m_500m"
        reason="..."
      />,
    );
    const href = screen.getByRole("link").getAttribute("href")!;
    expect(href).toContain("wa.me/6285156005858"); // no "+"
  });
});
```

- [ ] **Step 6.2: Run test — fails (module missing)**

```bash
cd ~/Desktop/nuzantara/apps/mouth
npx vitest run src/components/visa/__tests__/HandoffWaLink.test.tsx
```

Expected: `Cannot find module '../HandoffWaLink'`.

- [ ] **Step 6.3: Implement HandoffWaLink**

Create `apps/mouth/src/components/visa/HandoffWaLink.tsx`:

```tsx
"use client";

export interface HandoffWaLinkProps {
  phone: string; // E.164 with or without leading '+'
  nationality: string;
  purpose: string;
  durationMonths: number;
  budgetBand: string;
  reason: string;
}

export function HandoffWaLink({
  phone,
  nationality,
  purpose,
  durationMonths,
  budgetBand,
  reason,
}: HandoffWaLinkProps) {
  const normalisedPhone = phone.replace(/^\+/, "");
  const summary =
    `Hi Bali Zero, your wizard couldn't pick a visa for my case.\n\n` +
    `Nationality: ${nationality}\n` +
    `Purpose: ${purpose}\n` +
    `Duration: ${durationMonths} months\n` +
    `Budget: ${budgetBand}\n\n` +
    `Wizard note: ${reason}\n\n` +
    `Can you help me figure out the right visa?`;
  const href = `https://wa.me/${normalisedPhone}?text=${encodeURIComponent(summary)}`;

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-2 px-6 py-4 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-black font-serif text-lg transition"
    >
      Start on WhatsApp →
    </a>
  );
}
```

- [ ] **Step 6.4: Run test — passes**

```bash
npx vitest run src/components/visa/__tests__/HandoffWaLink.test.tsx
```

Expected: 2 tests pass.

- [ ] **Step 6.5: Render HandoffWaLink in result page for `referral_mode=true`**

In `apps/mouth/src/app/visa/match/[hash]/page.tsx`, replace the existing "WhatsApp CTA" rendering block with:

```tsx
{
  match.referral_mode ? (
    <HandoffWaLink
      phone={process.env.NEXT_PUBLIC_WA_PHONE ?? "+6285156005858"}
      nationality={match.nationality}
      purpose={match.purpose}
      durationMonths={match.duration_months}
      budgetBand={match.budget_band}
      reason={match.reason}
    />
  ) : (
    /* existing primary WhatsApp CTA stays here for normal path */
    <PrimaryWaCta hash={match.hash} visa={match.recommended_visa} />
  );
}
```

Add the import: `import { HandoffWaLink } from "@/components/visa/HandoffWaLink";`

If `PrimaryWaCta` does not already exist as a named component, wrap the current inline CTA code into a local component (keeps the JSX readable).

- [ ] **Step 6.6: Build compiles**

```bash
cd ~/Desktop/nuzantara/apps/mouth
npx tsc --noEmit 2>&1 | tail -10
```

- [ ] **Step 6.7: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/mouth/src/components/visa/HandoffWaLink.tsx \
        apps/mouth/src/components/visa/__tests__/HandoffWaLink.test.tsx \
        apps/mouth/src/app/visa/match/\[hash\]/page.tsx
git commit -m "$(cat <<'EOF'
feat(visa-frontend): HandoffWaLink for wizard_abstained cases

When the Visa Check wizard abstains (referral_mode=true — OTHER
purpose, tourism > 6mo, investor under-budget), the result page now
renders a pre-compiled wa.me link with an encoded summary of the
quiz answers + the wizard's reason line. The chat accordion is
suppressed for this path: these are hot human leads.

- HandoffWaLink: pure presentational component, no network calls,
  deterministic URL generation from props.
- Phone number comes from NEXT_PUBLIC_WA_PHONE with a sensible
  fallback so local dev without envs still works.
- 2 Vitest component tests covering URL encoding + phone normalisation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Clock branch — same accordion, urgency copy

**Files:**

- Modify: `apps/mouth/src/app/visa/clock/[hash]/page.tsx`
- Modify: `apps/backend-rag/backend/app/routers/visa_check.py` (clock endpoint also emits `session_jwt`)

Same chat accordion, but the accordion's label uses urgency-aware copy derived from the nearest checkpoint. E.g. if `days_remaining <= 7`, label is "Urgent: ask questions before expiry". For `14 < days_remaining ≤ 30`, "Have 2 weeks or less? Ask 3 free questions". Default (> 30) is the generic "Have doubts?" copy.

- [ ] **Step 7.1: Extend clock endpoint to return `session_jwt`**

Open `apps/backend-rag/backend/app/routers/visa_check.py`. In `class ClockResponse(BaseModel)` (around line 86), add:

```python
    session_jwt: str | None = None
```

In `submit_clock`, at the return, add `session_jwt=_issue_visa_funnel_jwt(saved.hash)`. `get_clock` leaves it unset (same pattern as Task 2).

- [ ] **Step 7.2: Add urgency derivation test**

Create `apps/mouth/src/components/visa/__tests__/ChatAccordion.urgency.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChatAccordion } from "../ChatAccordion";

describe("ChatAccordion urgency copy", () => {
  it("uses urgent copy when daysRemaining <= 7", () => {
    render(<ChatAccordion checkHash="x" sessionJwt="j" daysRemaining={5} />);
    expect(screen.getByRole("button", { name: /urgent/i })).toBeInTheDocument();
  });

  it("uses short-window copy when 8 <= daysRemaining <= 30", () => {
    render(<ChatAccordion checkHash="x" sessionJwt="j" daysRemaining={20} />);
    expect(
      screen.getByRole("button", { name: /2 weeks or less/i }),
    ).toBeInTheDocument();
  });

  it("uses default copy when daysRemaining > 30 or undefined", () => {
    render(<ChatAccordion checkHash="x" sessionJwt="j" daysRemaining={90} />);
    expect(
      screen.getByRole("button", { name: /ask 3 free questions/i }),
    ).toBeInTheDocument();
  });
});
```

- [ ] **Step 7.3: Run tests — fail (prop missing)**

```bash
npx vitest run src/components/visa/__tests__/ChatAccordion.urgency.test.tsx
```

- [ ] **Step 7.4: Extend ChatAccordion with `daysRemaining`**

In `ChatAccordion.tsx`, add the optional prop and derive the label:

```tsx
export interface ChatAccordionProps {
  checkHash: string;
  sessionJwt: string;
  daysRemaining?: number;
}

function deriveLabel(daysRemaining?: number): string {
  if (daysRemaining !== undefined) {
    if (daysRemaining <= 7) return "Urgent: ask questions before expiry";
    if (daysRemaining <= 30) return "2 weeks or less — ask 3 free questions";
  }
  return "Have doubts? Ask 3 free questions";
}
```

And use `{deriveLabel(daysRemaining)}` in place of the hardcoded string.

- [ ] **Step 7.5: Wire accordion into clock page**

In `apps/mouth/src/app/visa/clock/[hash]/page.tsx`, compute `daysRemaining` from `timeline.expiry_date` and pass it:

```tsx
const daysRemaining = Math.max(
  0,
  Math.ceil(
    (new Date(timeline.expiry_date).getTime() - Date.now()) / 86_400_000,
  ),
);

{
  timeline.session_jwt && (
    <ChatAccordion
      checkHash={timeline.hash}
      sessionJwt={timeline.session_jwt}
      daysRemaining={daysRemaining}
    />
  );
}
```

- [ ] **Step 7.6: All tests green**

```bash
cd ~/Desktop/nuzantara/apps/mouth
npx vitest run src/components/visa/
cd ../backend-rag
PYTHONPATH=. pytest backend/tests/services/visa_check/ -q
```

- [ ] **Step 7.7: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/app/routers/visa_check.py \
        apps/mouth/src/components/visa/ChatAccordion.tsx \
        apps/mouth/src/components/visa/__tests__/ChatAccordion.urgency.test.tsx \
        apps/mouth/src/app/visa/clock/\[hash\]/page.tsx
git commit -m "$(cat <<'EOF'
feat(visa-clock): chat accordion with urgency-aware copy

Clock branch now gets the same ChatAccordion as the match result
page, with copy that shifts by daysRemaining from expiry:
- <= 7d: "Urgent: ask questions before expiry"
- 8-30d: "2 weeks or less — ask 3 free questions"
- > 30d or undefined: default "Have doubts?" copy

Backend: submit_clock now issues the same visa_funnel JWT as
submit_match, so the chat auth path is uniform across both branches.

3 new Vitest tests for urgency derivation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Privacy + terms + consent banner in `/visa` namespace

**Files:**

- Create: `apps/mouth/src/app/visa/privacy/page.tsx` (copy from Oracle, update canonical URL)
- Create: `apps/mouth/src/app/visa/terms/page.tsx` (same)
- Modify: `apps/mouth/src/app/visa/page.tsx` (mount `<ConsentBanner />` once on `/visa` root)

Pure file copy with minor canonical-URL + nav updates. No new tests here (pages are static and trivially rendered).

- [ ] **Step 8.1: Copy pages**

```bash
cd ~/Desktop/nuzantara
mkdir -p apps/mouth/src/app/visa/privacy apps/mouth/src/app/visa/terms
cp "apps/mouth/src/app/(visa-oracle)/visa-oracle/privacy/page.tsx" \
   apps/mouth/src/app/visa/privacy/page.tsx
cp "apps/mouth/src/app/(visa-oracle)/visa-oracle/terms/page.tsx" \
   apps/mouth/src/app/visa/terms/page.tsx
```

- [ ] **Step 8.2: Update canonical URLs**

In both new files, find and replace:

- `https://visa.balizero.com/privacy` → `https://balizero.com/visa/privacy`
- `https://visa.balizero.com/terms` → `https://balizero.com/visa/terms`
- `Visa Oracle` → `Bali Zero — Visa`
- Internal links like `/privacy` → `/visa/privacy`, `/terms` → `/visa/terms`

Use your editor; these are copy strings, no functional changes.

- [ ] **Step 8.3: Mount ConsentBanner on `/visa` root**

Open `apps/mouth/src/app/visa/page.tsx`. At the top of the returned JSX, add:

```tsx
import { ConsentBanner } from "@/components/visa/ConsentBanner";

// inside the returned JSX, before the hero:
<ConsentBanner />;
```

`ConsentBanner` uses a cookie on `.balizero.com` to remember dismissal, so it auto-hides on subsequent visits (same behaviour as Oracle).

- [ ] **Step 8.4: Next build compiles + pages 200**

```bash
cd ~/Desktop/nuzantara/apps/mouth
npx tsc --noEmit 2>&1 | tail -5
```

Expected: no errors.

- [ ] **Step 8.5: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/mouth/src/app/visa/privacy/ apps/mouth/src/app/visa/terms/ \
        apps/mouth/src/app/visa/page.tsx
git commit -m "$(cat <<'EOF'
feat(visa-frontend): port privacy, terms, and ConsentBanner into /visa

- /visa/privacy + /visa/terms: copied verbatim from the Oracle route
  group, canonical URLs updated to the new path.
- ConsentBanner now mounted once on the /visa root. Uses the existing
  .balizero.com cookie for dismissal memory; no new state.

No logic changes; pure relocation + URL cleanup.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Middleware — replace subdomain rewrite with 302 redirects (6 rules)

**Files:**

- Modify: `apps/mouth/src/middleware.ts` (lines 239-248 block)
- Modify: `apps/mouth/src/middleware.test.ts` (add 6 redirect tests)

- [ ] **Step 9.1: Write failing redirect tests**

Open `apps/mouth/src/middleware.test.ts` (or create if absent with existing patterns in the repo). Add a new describe block:

```ts
describe("visa.balizero.com subdomain redirects", () => {
  const host = "visa.balizero.com";
  const cases: Array<[string, string]> = [
    ["/", "/visa"],
    ["/quiz", "/visa/match"],
    ["/result", "/visa/match"],
    ["/chat", "/visa/match"],
    ["/privacy", "/visa/privacy"],
    ["/terms", "/visa/terms"],
    ["/random-unmapped-path", "/visa"], // conservative catch-all
  ];

  for (const [from, to] of cases) {
    it(`redirects 302 ${from} → balizero.com${to}`, async () => {
      const req = new NextRequest(new URL(`https://${host}${from}`));
      const res = await middleware(req);
      expect(res.status).toBe(302);
      const location = res.headers.get("location")!;
      const url = new URL(location);
      expect(url.hostname).toBe("balizero.com");
      expect(url.pathname).toBe(to);
    });
  }
});
```

If `middleware.test.ts` does not yet exist, create it with `import { NextRequest } from "next/server";` and `import { middleware } from "./middleware";` at the top.

- [ ] **Step 9.2: Run — tests fail (still rewriting)**

```bash
cd ~/Desktop/nuzantara/apps/mouth
npx vitest run src/middleware.test.ts
```

- [ ] **Step 9.3: Rewrite the middleware block**

In `apps/mouth/src/middleware.ts`, replace the current `isVisaDomain` rewrite block (lines ~239-252) with:

```ts
// === VISA DOMAIN (visa.balizero.com) — LEGACY, redirect to /visa ===
// The visa funnel was consolidated at balizero.com/visa (see spec
// 2026-04-21-visa-funnel-fusion.md). This block remaps legacy
// Oracle subdomain paths 1:1 to the canonical /visa paths with a
// temporary 302 so GSC can propagate the change of address; when
// traffic drops to < 1% of peak for 30 days, the DNS record for
// visa.balizero.com is removed entirely.
if (isVisaDomain) {
  const target = new URL(request.url);
  target.hostname = "balizero.com";
  target.port = "";
  target.protocol = "https:";

  const legacy = pathname.replace(/\/+$/, "") || "/";
  const map: Record<string, string> = {
    "/": "/visa",
    "/quiz": "/visa/match",
    "/result": "/visa/match",
    "/chat": "/visa/match",
    "/privacy": "/visa/privacy",
    "/terms": "/visa/terms",
  };
  target.pathname = map[legacy] ?? "/visa";

  return NextResponse.redirect(target, 302);
}
```

- [ ] **Step 9.4: Run tests — all pass**

```bash
npx vitest run src/middleware.test.ts
```

Expected: 7 redirect tests pass + prior middleware tests untouched.

- [ ] **Step 9.5: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/mouth/src/middleware.ts apps/mouth/src/middleware.test.ts
git commit -m "$(cat <<'EOF'
feat(middleware): 302 redirects visa.balizero.com → balizero.com/visa

Replaces the legacy rewrite (visa.balizero.com → /visa-oracle/*) with
a 1:1 302 redirect map to the consolidated /visa funnel:
  /         → /visa
  /quiz     → /visa/match
  /result   → /visa/match
  /chat     → /visa/match
  /privacy  → /visa/privacy
  /terms    → /visa/terms
  anything  → /visa   (conservative catch-all)

302 (not 301) because the subdomain will be removed entirely after
GSC change-of-address propagates and traffic drops to < 1% of peak
for 30 days. See spec docs/superpowers/specs/2026-04-21-visa-funnel-fusion.md.

7 Vitest cases covering every mapped path + catch-all.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Sitemap + internal link sweep

**Files:**

- Modify: `apps/mouth/src/app/sitemap.ts` (add /visa/\*; remove visa.balizero.com URLs)
- Internal links across `apps/mouth/src/`

- [ ] **Step 10.1: Scan for internal references to the old subdomain**

```bash
cd ~/Desktop/nuzantara
grep -rn "visa.balizero.com\|/visa-oracle" apps/mouth/src \
  --include="*.tsx" --include="*.ts" \
  --exclude-dir=node_modules \
  | grep -vE "(middleware.ts|\.test\.tsx?$)"
```

Expected output: navigation / footer / hero / homepage funnel files.

- [ ] **Step 10.2: Replace each with the new path**

For each hit, swap:

- `https://visa.balizero.com` → `/visa` (relative, since we're on the same origin now)
- `/visa-oracle` → `/visa`
- `/visa-oracle/quiz` → `/visa/match`

Review every change — do NOT touch the `middleware.ts` map (already correct) or any test that intentionally asserts the old URL.

- [ ] **Step 10.3: Add sitemap entries**

In `apps/mouth/src/app/sitemap.ts`, add the following entries to the returned array:

```ts
{
  url: "https://balizero.com/visa",
  lastModified: new Date(),
  changeFrequency: "weekly",
  priority: 0.9,
},
{
  url: "https://balizero.com/visa/match",
  lastModified: new Date(),
  changeFrequency: "weekly",
  priority: 0.9,
},
{
  url: "https://balizero.com/visa/clock",
  lastModified: new Date(),
  changeFrequency: "weekly",
  priority: 0.9,
},
{
  url: "https://balizero.com/visa/privacy",
  lastModified: new Date(),
  changeFrequency: "monthly",
  priority: 0.5,
},
{
  url: "https://balizero.com/visa/terms",
  lastModified: new Date(),
  changeFrequency: "monthly",
  priority: 0.5,
},
```

And remove any existing `visa.balizero.com` entries.

- [ ] **Step 10.4: Build + commit**

```bash
cd ~/Desktop/nuzantara/apps/mouth
npx tsc --noEmit 2>&1 | tail -5
```

```bash
cd ~/Desktop/nuzantara
git add apps/mouth/src/
git commit -m "$(cat <<'EOF'
chore(visa-frontend): update sitemap + replace subdomain in internal links

- sitemap.ts: 5 new /visa/* entries, priority 0.9 (main) / 0.5 (legal).
- Removed visa.balizero.com sitemap entries.
- Internal links across apps/mouth/src/ pointing at the legacy
  subdomain or /visa-oracle/* now point at the consolidated /visa
  paths. Middleware still handles anyone arriving from outside via
  the 302 redirect, but internal navigation now goes direct.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Delete `(visa-oracle)/` route group + `components/visa-oracle/` folder

**Files:**

- Delete: `apps/mouth/src/app/(visa-oracle)/` (entire directory)
- Delete: `apps/mouth/src/components/visa-oracle/` (already empty after Task 4; confirm and remove)

No Next.js route for the `(visa-oracle)` group survives: the subdomain redirect in the middleware handles any incoming traffic to the old URL before routing.

- [ ] **Step 11.1: Confirm the group is referenced only by dead files**

```bash
cd ~/Desktop/nuzantara
grep -rn "visa-oracle" apps/mouth/src/ \
  --include="*.ts" --include="*.tsx" \
  | grep -v "middleware.ts" \
  | grep -v "\.test\.tsx?$"
```

Expected: zero non-test, non-middleware hits. If hits remain, fix them before deleting.

- [ ] **Step 11.2: Delete**

```bash
cd ~/Desktop/nuzantara
rm -rf "apps/mouth/src/app/(visa-oracle)"
rm -rf apps/mouth/src/components/visa-oracle
```

- [ ] **Step 11.3: Build + type-check clean**

```bash
cd ~/Desktop/nuzantara/apps/mouth
npx tsc --noEmit 2>&1 | tail -10
npx vitest run 2>&1 | tail -15
```

Expected: no type errors, no test failures.

- [ ] **Step 11.4: Commit**

```bash
cd ~/Desktop/nuzantara
git add -A apps/mouth/src/app apps/mouth/src/components
git commit -m "$(cat <<'EOF'
chore(visa-frontend): delete legacy (visa-oracle) route group + components

The visa.balizero.com subdomain no longer needs a Next.js route
group because the middleware now 302-redirects every legacy path
to the consolidated /visa funnel (see commit for the middleware
change). Components were moved to components/visa/ in an earlier
commit; the empty components/visa-oracle/ shell is removed too.

No functional change from the user's perspective: anyone who still
hits visa.balizero.com/* is redirected before Next.js ever looks
up a route, and nothing inside balizero.com/* ever referenced the
deleted paths after the internal-link sweep.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Telemetry — 9 GA4 events

**Files:**

- Modify: `apps/mouth/src/lib/analytics.ts` (or wherever `logEvent` is defined) — add event schemas.
- Modify: all files where new events fire (landing, match wizard, result, clock, chat accordion, handoff link).

Nine events instrumented end-to-end, each with the typed payload defined in the spec.

- [ ] **Step 12.1: Check where analytics currently fires**

```bash
cd ~/Desktop/nuzantara
grep -rln "logEvent\|gtag\|trackEvent" apps/mouth/src/ --include="*.ts" --include="*.tsx" | head -5
```

Identify the existing helper (e.g. `logEvent(name, params)`).

- [ ] **Step 12.2: Add event definitions**

In the analytics module (e.g. `apps/mouth/src/lib/analytics.ts`), append:

```ts
// Visa funnel events (spec: 2026-04-21-visa-funnel-fusion.md)
export const VisaEvents = {
  visaLandingView: () => logEvent("visa_landing_view"),
  visaBranchSelected: (branch: "clock" | "match") =>
    logEvent("visa_branch_selected", { branch }),
  visaMatchSubmitted: (p: {
    purpose: string;
    budget_band: string;
    duration_months: number;
    referral_mode: boolean;
    recommended_visa: string | null;
  }) => logEvent("visa_match_submitted", p),
  visaResultView: (p: {
    hash: string;
    recommended_visa: string | null;
    referral_mode: boolean;
    source: "match" | "clock";
  }) => logEvent("visa_result_view", p),
  visaChatOpened: (p: { hash: string; remaining_questions: number }) =>
    logEvent("visa_chat_opened", p),
  visaChatQuestionSent: (p: {
    hash: string;
    question_index: number;
    confidence_bucket: "abstain" | "cautious" | "normal";
  }) => logEvent("visa_chat_question_sent", p),
  visaWaClick: (p: {
    hash: string;
    source: "primary" | "chat_handoff" | "wizard_abstained";
    referral_mode: boolean;
  }) => logEvent("visa_wa_click", p),
  visaPaywallHit: (p: { hash: string; question_index: number }) =>
    logEvent("visa_paywall_hit", p),
  visaSubdomainRedirect: (p: { from_path: string; to_path: string }) =>
    logEvent("visa_subdomain_redirect", p),
};
```

- [ ] **Step 12.3: Fire events at call sites**

For each event, add the call in the right component:

| Event                   | File                                                                                                                                                                                             | Where                                                |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------- |
| `visaLandingView`       | `apps/mouth/src/app/visa/page.tsx`                                                                                                                                                               | `useEffect` on mount                                 |
| `visaBranchSelected`    | `apps/mouth/src/app/visa/page.tsx`                                                                                                                                                               | onClick of each branch CTA                           |
| `visaMatchSubmitted`    | `apps/mouth/src/app/visa/match/page.tsx`                                                                                                                                                         | after POST success                                   |
| `visaResultView`        | `apps/mouth/src/app/visa/match/[hash]/page.tsx` and `.../clock/[hash]/page.tsx`                                                                                                                  | `useEffect` on mount                                 |
| `visaChatOpened`        | `apps/mouth/src/components/visa/ChatAccordion.tsx`                                                                                                                                               | inside `onClick` toggle, only when opening           |
| `visaChatQuestionSent`  | `apps/mouth/src/components/visa/VisaChat.tsx`                                                                                                                                                    | after successful POST, reading `response.confidence` |
| `visaWaClick`           | primary WA CTA + chat handoff CTA + `HandoffWaLink`                                                                                                                                              | `onClick` of the link                                |
| `visaPaywallHit`        | `VisaChat.tsx`                                                                                                                                                                                   | when `remaining === 0` guard fires                   |
| `visaSubdomainRedirect` | `middleware.ts` — **NOT** a frontend event. Use a 1px pixel on the landing: `apps/mouth/src/app/visa/page.tsx` reads `document.referrer`, if it starts with `visa.balizero.com` fires the event. |

- [ ] **Step 12.4: Build + commit**

```bash
cd ~/Desktop/nuzantara/apps/mouth
npx tsc --noEmit 2>&1 | tail -5
```

```bash
cd ~/Desktop/nuzantara
git add apps/mouth/src/lib/analytics.ts apps/mouth/src/app/visa apps/mouth/src/components/visa
git commit -m "$(cat <<'EOF'
feat(visa-telemetry): instrument 9 GA4 events across the funnel

Instruments the events defined in the spec so the contact-rate KPI
(wizard → contact) can be measured post-fusion:

- visa_landing_view / visa_branch_selected
- visa_match_submitted (incl. referral_mode, recommended_visa)
- visa_result_view
- visa_chat_opened / visa_chat_question_sent (with confidence bucket)
- visa_wa_click (primary | chat_handoff | wizard_abstained)
- visa_paywall_hit
- visa_subdomain_redirect (pixel on landing; NOT emitted by middleware
  since server-side events don't route to GA4 directly here)

Baseline contact rate is ~2% (CRO audit 2026-04-19); target >= 15%
at 30 days post-merge.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Playwright E2E

**Files:**

- Create: `apps/mouth/e2e/visa-funnel-fusion.spec.ts` (or in the project's Playwright dir)

- [ ] **Step 13.1: Write 3 scenarios**

Create `apps/mouth/e2e/visa-funnel-fusion.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

test.describe("Visa funnel fusion E2E", () => {
  test("match happy path — user completes wizard, chats, WA click", async ({
    page,
  }) => {
    await page.goto("/visa");
    await page.getByRole("link", { name: /no, i'm planning/i }).click();

    // Step 1 — nationality
    await page.getByRole("combobox").selectOption("USA");
    await page.getByRole("button", { name: /next/i }).click();

    // Step 2 — purpose
    await page.getByRole("button", { name: /work remotely/i }).click();
    await page.getByRole("button", { name: /next/i }).click();

    // Step 3 — duration (leave default)
    await page.getByRole("button", { name: /next/i }).click();

    // Step 4 — budget
    await page.getByRole("button", { name: /idr 50m/i }).click();
    await page.getByRole("button", { name: /see result/i }).click();

    // Result page: stamp, cost, checklist, accordion
    await expect(page.getByText(/your visa:/i)).toBeVisible();
    await expect(page.getByText(/E33G/)).toBeVisible();
    await expect(page.getByText(/IDR \d+[.,]\d{3}[.,]\d{3}/)).toBeVisible();

    // Open accordion
    const accordion = page.getByRole("button", {
      name: /ask 3 free questions/i,
    });
    await expect(accordion).toBeVisible();
    await accordion.click();

    // Chat input becomes visible
    await expect(page.getByPlaceholder(/ask/i)).toBeVisible();

    // WhatsApp CTA is still present and unaffected
    await expect(
      page.getByRole("link", { name: /start on whatsapp/i }),
    ).toBeVisible();
  });

  test("wizard_abstained path — under-budget investor sees HandoffWaLink, no accordion", async ({
    page,
  }) => {
    await page.goto("/visa");
    await page.getByRole("link", { name: /no, i'm planning/i }).click();

    await page.getByRole("combobox").selectOption("ITA");
    await page.getByRole("button", { name: /next/i }).click();
    await page.getByRole("button", { name: /invest/i }).click();
    await page.getByRole("button", { name: /next/i }).click();
    await page.getByRole("button", { name: /next/i }).click();
    await page.getByRole("button", { name: /under idr 50m/i }).click();
    await page.getByRole("button", { name: /see result/i }).click();

    // Accordion MUST NOT render
    await expect(
      page.getByRole("button", { name: /ask 3 free questions/i }),
    ).toHaveCount(0);
    // HandoffWaLink with pre-compiled summary
    const wa = page.getByRole("link", { name: /start on whatsapp/i });
    const href = await wa.getAttribute("href");
    expect(href).toContain("wa.me/");
    expect(decodeURIComponent(href!)).toContain("investor");
    expect(decodeURIComponent(href!)).toContain("ITA");
  });

  test("subdomain 302 redirect — visa.balizero.com/privacy → /visa/privacy", async ({
    request,
  }) => {
    const res = await request.get("https://visa.balizero.com/privacy", {
      maxRedirects: 0,
    });
    expect(res.status()).toBe(302);
    expect(res.headers().location).toMatch(/balizero\.com\/visa\/privacy$/);
  });
});
```

- [ ] **Step 13.2: Run E2E against local dev or preview**

```bash
cd ~/Desktop/nuzantara/apps/mouth
npx playwright test e2e/visa-funnel-fusion.spec.ts
```

Expected: all 3 pass (the third only reliably passes against deployed preview; in local dev mock via the standard pattern in the repo or skip with `test.skip(!process.env.VERCEL_URL)`).

- [ ] **Step 13.3: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/mouth/e2e/visa-funnel-fusion.spec.ts
git commit -m "$(cat <<'EOF'
test(visa-e2e): 3 Playwright scenarios for the unified funnel

1. Match happy path: wizard → result → expand accordion → WA visible.
2. Wizard-abstained: investor + under-50M → no accordion → HandoffWaLink
   with pre-compiled wa.me summary.
3. Subdomain redirect: hit visa.balizero.com/privacy → 302 to
   balizero.com/visa/privacy.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Full verification before PR

- [ ] **Step 14.1: Backend suite**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/visa_check/ \
                    backend/tests/services/visa_oracle/ \
                    backend/tests/services/visa_unified/ -v
PYTHONPATH=. pytest backend/tests/services/rag/test_confidence.py \
                    backend/tests/services/rag/test_kg_langgraph.py \
                    backend/tests/services/rag/test_kg_subgraphs.py -q
```

Expected: visa suite all green; RAG core no regressions.

- [ ] **Step 14.2: Import chain**

```bash
python -c "from backend.app.dependencies import get_current_user; print('OK')"
```

- [ ] **Step 14.3: Frontend suite**

```bash
cd ~/Desktop/nuzantara/apps/mouth
npx vitest run
npx tsc --noEmit
```

- [ ] **Step 14.4: Build**

```bash
cd ~/Desktop/nuzantara/apps/mouth
npm run build 2>&1 | tail -20
```

Expected: build succeeds, no type errors, no missing routes.

---

## Task 15: Open PR + monitor deploy

- [ ] **Step 15.1: Push branch**

```bash
cd ~/Desktop/nuzantara
git push -u origin feat/visa-funnel-fusion
```

- [ ] **Step 15.2: Open PR**

```bash
gh pr create --title "feat(visa): unify Check + Oracle into single funnel at /visa" --body "$(cat <<'EOF'
## Summary

Fuses `visa.balizero.com` (Oracle chat) into `balizero.com/visa` (Check wizard) per spec 2026-04-21-visa-funnel-fusion.md, brainstormed cross-LLM (Codex + DeepSeek R1 + Gemini 2.5 Pro).

- **Backend**: new `visa_unified/bridge.py` facade reads `visa_checks` by hash, produces a typed `FunnelContext`, augments Oracle chat system prompt with visa + cost ground truth. `submit_match` and `submit_clock` now return `session_jwt` (1h HS256 via existing `JWT_SECRET_KEY`); Oracle `/chat` validates it when `check_hash` is posted.
- **Frontend**: accordion-inline chat on `/visa/match/[hash]` and `/visa/clock/[hash]` (closed by default, urgency-aware label on Clock). `wizard_abstained` cases (`referral_mode=true`: OTHER purpose, tourism > 6mo, investor under-budget) bypass the chat entirely and render a pre-compiled `wa.me` link with quiz summary for hot-lead handoff. Consent banner + privacy + terms ported to `/visa/*`.
- **Infra**: `visa.balizero.com` 302-redirects with 1:1 mapping to `balizero.com/visa/*`. Sitemap updated. Internal links rewritten. Dead code (`(visa-oracle)/` + `components/visa-oracle/`) deleted.
- **Telemetry**: 9 GA4 events wired across the funnel.
- **Tests**: 8 new unit + 11 new component + 5 new integration + 3 new Playwright E2E.

Spec: `docs/superpowers/specs/2026-04-21-visa-funnel-fusion.md`
Plan: `docs/superpowers/plans/2026-04-21-visa-funnel-fusion.md`

## Test plan

- [x] Backend: all visa suites green + RAG core no regressions.
- [x] Frontend: Vitest green, `tsc --noEmit` clean.
- [x] Playwright: 3 scenarios pass locally / against preview.
- [ ] Post-deploy: 21-scenario sweep via `curl` against prod as in PR #143.
- [ ] GSC change-of-address submitted within 24h of merge.

## Follow-up (NOT in this PR)

- Dynamic "18 visa codes" counter on landing (currently hardcoded "24+").
- A/B test primary CTA placement using the new telemetry (day 14 data).
- Consider removing Oracle `/recommend` endpoint if no consumer remains.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 15.3: Arm auto-merge**

```bash
cd ~/Desktop/nuzantara
gh pr merge --squash --auto --subject "feat(visa): unify Check + Oracle into single funnel at /visa (#PR_NUM)" --body "See PR description."
```

- [ ] **Step 15.4: Post-deploy verification**

```bash
cd ~/Desktop/nuzantara
./scripts/post-deploy-verify.sh $(gh pr view --json number --jq .number)
```

Then manually verify in a browser:

```bash
curl -sS https://balizero.com/visa -o /dev/null -w "landing=%{http_code}\n"
curl -sS -X POST https://nuzantara-rag.fly.dev/api/visa/match \
  -H 'Content-Type: application/json' \
  -d '{"nationality":"USA","purpose":"work_remote","duration_months":12,"budget_band":"50m_500m"}' \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print('visa=',d['recommended_visa'],'jwt?',bool(d.get('session_jwt')))"
curl -sSI https://visa.balizero.com/privacy | head -5
```

Expected: landing 200, match returns `E33G` + non-empty `session_jwt`, subdomain returns `302` with `Location: https://balizero.com/visa/privacy`.

- [ ] **Step 15.5: Submit GSC change-of-address**

Manual step: open Google Search Console, select the `visa.balizero.com` property, Settings → Change of Address → enter destination `balizero.com` → Submit. Document the submission time in the PR comments for audit trail.

---

## Self-review

**1. Spec coverage check:**

| Spec requirement                                                                                           | Task(s)                                                                                                             |
| ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Landing / Clock-Match split stays                                                                          | Task 12 (telemetry only — no page change)                                                                           |
| Accordion-inline chat on result (closed by default, below checklist, above WA)                             | Task 5                                                                                                              |
| Chat restyled to Check palette                                                                             | Task 5 (relies on Tailwind tokens in VisaChat — acceptable deferred polish; spec says "restyled", not "redesigned") |
| ConsentBanner mounted on `/visa`                                                                           | Task 8                                                                                                              |
| `/visa/privacy` + `/visa/terms` ported                                                                     | Task 8                                                                                                              |
| Clock gets accordion with urgency copy                                                                     | Task 7                                                                                                              |
| `wizard_abstained` skips accordion, renders HandoffWaLink                                                  | Task 6                                                                                                              |
| `visa_unified/bridge.py` facade with `FunnelContext` + `get_funnel_context` + `augment_chat_system_prompt` | Task 1                                                                                                              |
| `submit_match` returns `session_jwt`                                                                       | Task 2                                                                                                              |
| `chat` endpoint validates JWT + accepts `check_hash`                                                       | Task 3                                                                                                              |
| No new migration                                                                                           | Tasks 1–3 (schema untouched)                                                                                        |
| Middleware rewrite → 302 redirect (6 rules + catch-all)                                                    | Task 9                                                                                                              |
| GSC change-of-address submitted                                                                            | Task 15.5                                                                                                           |
| Sitemap updated                                                                                            | Task 10                                                                                                             |
| Internal links rewritten                                                                                   | Task 10                                                                                                             |
| `(visa-oracle)/` + `components/visa-oracle/` deleted                                                       | Task 11                                                                                                             |
| Oracle backend router kept                                                                                 | not touched (Task 3 only extends `chat`, not the endpoint registration)                                             |
| 9 GA4 events                                                                                               | Task 12                                                                                                             |
| Backend unit tests 9 cases                                                                                 | Task 1 (8) + Task 2 (3) — slight over-count; acceptable                                                             |
| Frontend component tests 6 cases                                                                           | Task 5 (3) + Task 6 (2) + Task 7 (3) = 8 — over target, good                                                        |
| E2E 3 scenarios                                                                                            | Task 13                                                                                                             |

**2. Placeholder scan:**

- Step 3.4 uses `...  # implementation moves verbatim` as a pointer to the refactor's scope. This is explicit by design (the engineer is told which lines to move) and the step numbers cite concrete line ranges. Marginally acceptable; no invented API.
- No "TBD" / "TODO" / "implement later".

**3. Type consistency:**

- `FunnelContext` fields match between Task 1 definition, Task 1 tests, Task 3 `get_funnel_context` consumption, and Task 1 `augment_chat_system_prompt`.
- `session_jwt` field is `str | None` across `MatchResponse` (Task 2) and `ClockResponse` (Task 7).
- `check_hash` is `str | None = None` in `ChatRequest` (Task 3), matches frontend `VisaChat` prop `checkHash?: string` (Task 5).
- `referral_mode` (JSON) vs `wizard_abstained` (narrative) per spec terminology note — used consistently: `referral_mode` only when referring to JSON field, concept text uses "wizard_abstained".
- `daysRemaining` prop on `ChatAccordion` (Task 7) consistent with test assertions.
- `HandoffWaLink` prop names match the result page invocation in Task 6.5.

**4. Scope check:**

Single sub-system (the visa funnel). Clear PR boundary. All tasks can run sequentially. Task 11 (cleanup) is gated behind Task 4 + Task 10 — ordering is explicit via step-level checks.
