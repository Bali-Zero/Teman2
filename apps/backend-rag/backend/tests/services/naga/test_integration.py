"""End-to-end integration tests for the Naga research pipeline — Task 19.

Exercises the full flow: gateway -> orchestrator -> search -> quality ->
synthesis -> report.  All external dependencies (search APIs, Gemini, NLM)
are mocked so the tests are deterministic and fast.

The key difference from ``test_orchestrator.py`` is that here we let the
*real* internal modules run (claim extractor, source scorer, CRAG,
convergence detector, report writer) instead of mocking them.  Only the
external I/O boundaries are mocked.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.claims.models import ClaimRecord
from backend.services.naga.actions.action_engine import detect_actions
from backend.services.naga.gateway import classify_query
from backend.services.naga.orchestrator import NagaOrchestrator

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _build_deps(**overrides: object) -> MagicMock:
    """Build a mock dependency container with realistic return values.

    Every callable represents an external I/O boundary (MCP tool, API, etc.).
    Only the deps object is mocked — internal modules (claim extractor,
    convergence, source scorer, report writer) run for real.
    """
    deps = MagicMock()

    # Exa neural search
    deps.exa_search = overrides.get(
        "exa_search",
        AsyncMock(return_value={
            "results": [
                {
                    "url": "https://imigrasi.go.id/golden-visa",
                    "title": "Golden Visa Indonesia",
                    "text": (
                        "Indonesia launched the Golden Visa program in 2024. "
                        "Minimum investment $350,000 for 5 years. The Golden Visa "
                        "is regulated by PP 40/2024 and managed by Direktorat "
                        "Jenderal Imigrasi. Requirements include a valid passport, "
                        "proof of investment, and a clean criminal record."
                    ),
                    "score": 0.92,
                },
                {
                    "url": "https://expat.id/golden-visa-guide",
                    "title": "Golden Visa Guide",
                    "text": (
                        "The Golden Visa requires a minimum investment of $350,000. "
                        "Processing takes 15 business days. Applicants must submit "
                        "the application through the official imigrasi portal. "
                        "The visa is valid for 5 or 10 years depending on the "
                        "investment amount."
                    ),
                    "score": 0.78,
                },
            ],
        }),
    )

    # Brave web search
    deps.brave_search = overrides.get(
        "brave_search",
        AsyncMock(return_value={"web": {"results": []}}),
    )

    # Content fetcher
    deps.fetch = overrides.get(
        "fetch",
        AsyncMock(return_value={"content": ""}),
    )

    # Internal RAG (ask_legal)
    deps.ask_legal = overrides.get(
        "ask_legal",
        AsyncMock(return_value={
            "answer": (
                "Golden Visa Indonesia diatur PP 40/2024. Investasi minimum "
                "$350,000. Persyaratan meliputi paspor valid, bukti investasi, "
                "dan surat keterangan catatan kepolisian (SKCK). Berlaku untuk "
                "WNA yang ingin berinvestasi di Indonesia."
            ),
            "sources": [{"title": "PP 40/2024"}],
            "confidence": 0.88,
        }),
    )

    # Intel search
    deps.search_intel = overrides.get(
        "search_intel",
        AsyncMock(return_value=[]),
    )

    # NLM notebook query
    deps.notebook_query = overrides.get(
        "notebook_query",
        AsyncMock(return_value={
            "status": "success",
            "text": "Confirmed. Golden Visa Indonesia requires minimum investment.",
            "sources_used": [],
        }),
    )

    # Episodic memory
    deps.recall_similar = overrides.get(
        "recall_similar",
        AsyncMock(return_value=[]),
    )

    # Gemini generate (returns valid evidence JSON)
    evidence_json = json.dumps({
        "sub_q_1": {
            "facts": [
                {
                    "text": "Golden Visa requires $350,000 minimum investment",
                    "source_ids": ["s0"],
                    "confidence": 0.92,
                },
                {
                    "text": "Processing takes 15 business days",
                    "source_ids": ["s1"],
                    "confidence": 0.78,
                },
            ],
            "contradictions": [],
            "gaps": ["No data on renewal process"],
            "data_points": [
                {
                    "label": "Minimum Investment",
                    "value": "$350,000",
                    "source_id": "s0",
                },
            ],
        },
        "sub_q_2": {
            "facts": [
                {
                    "text": "Golden Visa regulated by PP 40/2024",
                    "source_ids": ["s0"],
                    "confidence": 0.90,
                },
            ],
            "contradictions": [],
            "gaps": [],
            "data_points": [],
        },
    })

    deps.gemini_generate = overrides.get(
        "gemini_generate",
        AsyncMock(return_value={"text": evidence_json}),
    )

    return deps


# ---------------------------------------------------------------------------
# test_full_research_flow — deep tier E2E
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_research_flow() -> None:
    """Full E2E: gateway classify -> orchestrator research -> report.

    Runs the REAL claim extractor, source scorer, CRAG evaluator,
    convergence detector, and report writer.  Only external I/O is mocked.
    """
    query = (
        "Analisi completa golden visa Indonesia: "
        "requisiti, costi, confronto con KITAS Investasi"
    )

    # ---- 1. Gateway classification ------------------------------------
    gw = classify_query(query)

    assert gw.domain == "indonesia", f"Expected indonesia, got {gw.domain}"
    assert gw.tier in ("deep", "exhaustive"), f"Expected deep/exhaustive, got {gw.tier}"

    # ---- 2. Orchestrator research (mocked deps, real internals) -------
    deps = _build_deps()
    orch = NagaOrchestrator(deps)

    result = await orch.research(
        query=query,
        tier=gw.tier,
        domain=gw.domain,
        mode=gw.mode,
        channel=None,
    )

    # ---- 3. Verify results --------------------------------------------
    assert result["status"] == "completed", f"Expected completed, got {result['status']}"
    assert result["report_markdown"], "Report markdown must not be empty"

    report_lower = result["report_markdown"].lower()
    assert "golden visa" in report_lower, "Report must mention Golden Visa"

    # Claims or sources should be found
    has_claims = result["claims_extracted"] > 0
    has_sources = len(result["search_results"]) > 0
    assert has_claims or has_sources, (
        f"Expected claims > 0 or sources > 0, got "
        f"claims={result['claims_extracted']}, sources={len(result['search_results'])}"
    )

    assert result.get("session_id"), "session_id must be set"
    assert result["iteration"] >= 1, "Must complete at least 1 iteration"

    # Duration is wall-clock — must be positive
    # (We compute it in the test summary below; the state dict does not store it
    # directly, but duration_ms is passed to generate_report.)

    # avg_confidence can be 0 if no claims extracted
    avg_conf = result["avg_confidence"]
    if result["claims_extracted"] > 0:
        assert avg_conf > 0, f"avg_confidence should be > 0 when claims exist, got {avg_conf}"

    # ---- 4. Print summary for visual verification (-s flag) -----------
    print("\n  Naga E2E Test Passed")
    print(f"     Tier: {result['tier']}")
    print(f"     Domain: {result['domain']}")
    print(f"     Sources: {len(result['search_results'])}")
    print(f"     Claims: {result['claims_extracted']}")
    print(f"     Confidence: {avg_conf:.2f}")
    print(f"     Iterations: {result['iteration']}")
    print(f"     Convergence: {result['convergence_decision']}")
    print(f"     Sub-questions: {len(result['sub_questions'])}")
    print(f"     Report length: {len(result['report_markdown'])} chars")


# ---------------------------------------------------------------------------
# test_flash_flow — fast path, no Gemini
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flash_flow() -> None:
    """Flash tier: single iteration, no Gemini bulk read, fast path.

    Uses a simple query that the gateway classifies as flash.
    Verifies the fast path completes without Gemini.
    """
    query = "Cos'e il KITAS?"

    # ---- 1. Gateway classification ------------------------------------
    gw = classify_query(query)
    assert gw.tier == "flash", f"Expected flash, got {gw.tier}"

    # ---- 2. Orchestrator (flash) --------------------------------------
    deps = _build_deps()
    orch = NagaOrchestrator(deps)

    result = await orch.research(
        query=query,
        tier="flash",
        domain="indonesia",
    )

    # ---- 3. Verify flash behavior -------------------------------------
    assert result["status"] == "completed"
    assert result["tier"] == "flash"
    assert result["report_markdown"], "Flash report must not be empty"
    assert result["iteration"] == 1, "Flash tier should complete in exactly 1 iteration"

    # Flash must NOT call Gemini
    deps.gemini_generate.assert_not_awaited()

    # Flash should still produce some output
    has_claims = result["claims_extracted"] > 0
    has_sources = len(result["search_results"]) > 0
    assert has_claims or has_sources, "Flash should produce claims or find sources"

    # ---- 4. Print summary for visual verification ---------------------
    print("\n  Naga Flash Test Passed")
    print(f"     Tier: {result['tier']}")
    print(f"     Sources: {len(result['search_results'])}")
    print(f"     Claims: {result['claims_extracted']}")
    print(f"     Report length: {len(result['report_markdown'])} chars")


# ---------------------------------------------------------------------------
# test_action_engine_integration — detect_actions on real claims
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_action_engine_integration() -> None:
    """After research, run detect_actions on extracted claims.

    Uses a deep-tier research flow, then feeds the claims into the
    action engine to verify it proposes relevant actions.
    """
    query = (
        "Analisi completa golden visa Indonesia: "
        "requisiti, costi, confronto con KITAS Investasi"
    )

    deps = _build_deps()
    orch = NagaOrchestrator(deps)

    result = await orch.research(
        query=query,
        tier="deep",
        domain="indonesia",
    )

    assert result["status"] == "completed"

    # Build ClaimRecord objects that simulate what the pipeline produces.
    # The real extractor runs inside the orchestrator, but claims are
    # returned as a count, not as objects.  For the action engine test,
    # we construct claims from the mocked content to verify integration.
    claims = [
        ClaimRecord(
            claim_id="NB2-integ001",
            claim_text=(
                "Indonesia launched the Golden Visa program. "
                "New regulation PP 40/2024 has changed fee structure."
            ),
            category="FEE_CHANGE",
            confidence_class="VERIFIED",
            confidence_score=0.88,
            source_ids=["s0", "s1"],
            extracted="2026-04-03T00:00:00Z",
            geographic_scope="NATIONAL",
        ),
        ClaimRecord(
            claim_id="NB2-integ002",
            claim_text=(
                "Golden Visa launched as new policy for Indonesia investment."
            ),
            category="LEGAL_CHANGE",
            confidence_class="VERIFIED",
            confidence_score=0.85,
            source_ids=["s0"],
            extracted="2026-04-03T00:00:00Z",
            geographic_scope="NATIONAL",
        ),
        ClaimRecord(
            claim_id="NB2-integ003",
            claim_text=(
                "Some sources say KITAS Investasi requires Rp 1B, "
                "but this is unconfirmed and needs review."
            ),
            category="ELIGIBILITY_RULE",
            confidence_class="LOW",
            confidence_score=0.35,
            source_ids=["s2"],
            extracted="2026-04-03T00:00:00Z",
            geographic_scope="NATIONAL",
        ),
    ]

    gaps = ["Missing regulation details about renewal process"]

    # Run the action engine
    actions = detect_actions(claims=claims, trusted_mode=False, gaps=gaps)

    # Verify actions were proposed
    assert len(actions) > 0, "Action engine should detect at least one action"

    action_types = {a.action_type for a in actions}

    # The first claim has VERIFIED + indonesia + impact keywords (fee/changed)
    # -> should trigger crm_alert + notify
    assert "crm_alert" in action_types or "notify" in action_types, (
        f"Expected crm_alert or notify action, got {action_types}"
    )

    # The second claim has VERIFIED + news keyword (launched, new policy)
    # -> should trigger draft_article
    assert "draft_article" in action_types, (
        f"Expected draft_article action, got {action_types}"
    )

    # The third claim is LOW + indonesia -> escalation
    assert "escalation" in action_types, (
        f"Expected escalation action for low-confidence claim, got {action_types}"
    )

    # Gap with "regulation" keyword -> followup
    assert "followup" in action_types, (
        f"Expected followup action for regulation gap, got {action_types}"
    )

    # Verify priority ordering (high before medium)
    priorities = [a.priority for a in actions]
    high_indices = [i for i, p in enumerate(priorities) if p == "high"]
    medium_indices = [i for i, p in enumerate(priorities) if p == "medium"]
    if high_indices and medium_indices:
        assert max(high_indices) < min(medium_indices), (
            "High-priority actions should come before medium-priority"
        )

    # ---- Print summary ------------------------------------------------
    print("\n  Naga Action Engine Integration Test Passed")
    print(f"     Claims input: {len(claims)}")
    print(f"     Gaps input: {len(gaps)}")
    print(f"     Actions detected: {len(actions)}")
    for action in actions:
        print(
            f"       - [{action.priority}] {action.action_type}: "
            f"{action.description[:80]}"
        )


# ---------------------------------------------------------------------------
# test_gateway_classification_comprehensive — verify gateway for key queries
# ---------------------------------------------------------------------------


class TestGatewayClassification:
    """Verify gateway classifies representative queries correctly."""

    def test_indonesia_deep_query(self) -> None:
        """Complex Indonesian query -> indonesia + deep/exhaustive."""
        gw = classify_query(
            "Analisi completa golden visa Indonesia: "
            "requisiti, costi, confronto con KITAS Investasi"
        )
        assert gw.domain == "indonesia"
        assert gw.tier in ("deep", "exhaustive")

    def test_simple_flash_query(self) -> None:
        """Short simple query -> flash tier."""
        gw = classify_query("What is KITAS?")
        assert gw.tier == "flash"

    def test_telegram_forces_flash(self) -> None:
        """Telegram channel forces flash regardless of complexity."""
        gw = classify_query(
            "Analisi completa golden visa Indonesia requisiti costi",
            channel="telegram",
        )
        assert gw.tier == "flash"

    def test_force_tier_override(self) -> None:
        """force_tier overrides classification."""
        gw = classify_query("simple query", force_tier="exhaustive")
        assert gw.tier == "exhaustive"

    def test_hybrid_domain(self) -> None:
        """Query with Indonesia + foreign country -> hybrid."""
        gw = classify_query(
            "confronto golden visa Indonesia e golden visa Portugal"
        )
        assert gw.domain == "hybrid"
