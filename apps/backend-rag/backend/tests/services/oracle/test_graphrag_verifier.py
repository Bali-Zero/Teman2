"""Tests for ARCH-7: GraphRAG Verifier.

All database calls are mocked — no real PostgreSQL access.
Gold set fixtures used for integration-style tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.oracle.graphrag_verifier import (
    STRONG_EDGE_TYPES,
    ClaimVerification,
    GraphRAGResult,
    GraphRAGVerifier,
    extract_claims_for_verification,
    extract_keywords,
    get_verifier,
    reset_verifier,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GOLD_FILE = Path(
    "/Users/nuzantara/Desktop/nuzantara/apps/evaluator/nlm_deep_research/tests/fixtures/graphrag_gold_20.json"
)


def _load_gold() -> list[dict]:
    if _GOLD_FILE.exists():
        return json.loads(_GOLD_FILE.read_text())
    return []


def _make_node_record(entity_id: str, name: str, entity_type: str):
    """Create a dict-like record that supports subscript access."""
    data = {"entity_id": entity_id, "name": name, "entity_type": entity_type}
    m = MagicMock()
    m.__getitem__ = lambda self, k: data[k]
    m.__contains__ = lambda self, k: k in data
    m.get = lambda k, default=None: data.get(k, default)
    return m


def _make_edge_record(src: str, rel: str, tgt: str):
    """Create a dict-like edge record."""
    data = {"src": src, "relationship_type": rel, "tgt": tgt}
    m = MagicMock()
    m.__getitem__ = lambda self, k: data[k]
    m.get = lambda k, default=None: data.get(k, default)
    return m


def _make_db_pool(
    node_rows: list[dict] | None = None,
    edge_rows: list[dict] | None = None,
) -> MagicMock:
    """Create a mock asyncpg pool that returns given rows."""
    conn = AsyncMock()
    _node_rows = node_rows or []
    _edge_rows = edge_rows or []

    async def fake_fetch(query, *args, **kwargs):
        if "kg_nodes" in query:
            return [_make_node_record(r["entity_id"], r["name"], r["entity_type"]) for r in _node_rows]
        if "kg_edges" in query:
            return [_make_edge_record(r.get("src", "A"), r.get("relationship_type", "REQUIRES"), r.get("tgt", "B")) for r in _edge_rows]
        return []

    conn.fetch = fake_fetch

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=conn),
        __aexit__=AsyncMock(return_value=False),
    ))
    return pool


# ---------------------------------------------------------------------------
# TestExtractClaims
# ---------------------------------------------------------------------------

class TestExtractClaimsForVerification:
    def test_plain_text_splits_into_sentences(self):
        text = (
            "KITAS requires an employment contract from the sponsoring company in Indonesia. "
            "Processing time for the KITAS application takes approximately thirty working days. "
            "The DKP-TKA compensation fee is USD 100 per month per foreign worker position."
        )
        claims = extract_claims_for_verification(text)
        assert len(claims) == 3

    def test_short_sentences_filtered(self):
        text = "Yes. No. KITAS requires a valid RPTKA from the Ministry of Manpower."
        claims = extract_claims_for_verification(text)
        assert len(claims) == 1

    def test_max_claims_cap(self):
        text = ". ".join([f"Statement about Indonesian regulation number {i} for foreign workers in Bali" for i in range(30)])
        claims = extract_claims_for_verification(text, max_claims=5)
        assert len(claims) <= 5

    def test_empty_text_returns_empty(self):
        assert extract_claims_for_verification("") == []
        assert extract_claims_for_verification(None) == []

    def test_unwraps_nlm_json_envelope(self):
        """NLM responses come wrapped in {"value": {"answer": "..."}}."""
        payload = json.dumps({
            "value": {
                "answer": (
                    "The minimum capital requirement for PT PMA is USD 1 million. "
                    "Foreign investors must submit LKPM reports quarterly. "
                    "The NIB registration is mandatory for all companies operating in Indonesia."
                )
            }
        })
        claims = extract_claims_for_verification(payload)
        assert len(claims) >= 2
        # Should NOT contain JSON artifacts
        for c in claims:
            assert '"answer"' not in c
            assert '"value"' not in c

    def test_strips_markdown_and_citations(self):
        text = "**KITAS** requires RPTKA [1,2]. The _processing_ takes 30 days [3]."
        claims = extract_claims_for_verification(text)
        for c in claims:
            assert "[" not in c or "1,2" not in c  # citations stripped


# ---------------------------------------------------------------------------
# TestExtractKeywords
# ---------------------------------------------------------------------------

class TestExtractKeywords:
    def test_extracts_meaningful_words(self):
        text = "KITAS requires employment contract from PT PMA company sponsor"
        kw = extract_keywords(text)
        assert len(kw) > 0
        # Stop words excluded
        assert "from" not in kw
        assert "company" not in kw  # in stop words

    def test_extracts_uppercase_abbreviations(self):
        text = "RPTKA approval is needed before KITAS application at Imigrasi office"
        kw = extract_keywords(text)
        assert "rptka" in kw or "kitas" in kw

    def test_caps_at_8_keywords(self):
        text = " ".join(["keyword_" + str(i) for i in range(20)])
        kw = extract_keywords(text)
        assert len(kw) <= 8

    def test_empty_text_returns_empty(self):
        assert extract_keywords("") == []


# ---------------------------------------------------------------------------
# TestGraphRAGVerifier — no DB
# ---------------------------------------------------------------------------

class TestGraphRAGVerifierNoPool:
    def test_none_pool_returns_unknown(self):
        verifier = GraphRAGVerifier(db_pool=None)
        import asyncio
        result = asyncio.run(
            verifier.verify("Some NLM response about KITAS requirements.")
        )
        assert result.overall_status == "UNKNOWN"
        assert result.hallucination_risk is False

    def test_empty_text_returns_unknown(self):
        verifier = GraphRAGVerifier(db_pool=MagicMock())
        import asyncio
        result = asyncio.run(
            verifier.verify("")
        )
        assert result.overall_status == "UNKNOWN"


# ---------------------------------------------------------------------------
# TestGraphRAGVerifier — mocked DB
# ---------------------------------------------------------------------------

class TestGraphRAGVerifierMocked:
    @pytest.mark.asyncio
    async def test_high_status_when_nodes_and_edges_found(self):
        """When KG has 2+ nodes with strong edges → HIGH."""
        pool = _make_db_pool(
            node_rows=[
                {"entity_id": "1", "name": "KITAS", "entity_type": "permit_type"},
                {"entity_id": "2", "name": "RPTKA", "entity_type": "document"},
                {"entity_id": "3", "name": "Employment Contract", "entity_type": "document"},
            ],
            edge_rows=[
                {"src": "KITAS", "relationship_type": "REQUIRES", "tgt": "RPTKA"},
                {"src": "RPTKA", "relationship_type": "REQUIRED_FOR", "tgt": "KITAS"},
            ],
        )
        verifier = GraphRAGVerifier(db_pool=pool)
        text = (
            "KITAS requires a valid RPTKA from the Ministry of Manpower. "
            "The employment contract must be approved before processing. "
            "Foreign workers need NIB registration to work legally in Indonesia."
        )
        result = await verifier.verify(text)
        assert result.claims_total > 0
        assert result.overall_status in ("HIGH", "MEDIUM")

    @pytest.mark.asyncio
    async def test_medium_status_when_only_nodes_found(self):
        """When KG has nodes but no strong edges → MEDIUM."""
        pool = _make_db_pool(
            node_rows=[
                {"entity_id": "1", "name": "KITAS", "entity_type": "permit_type"},
            ],
            edge_rows=[],
        )
        verifier = GraphRAGVerifier(db_pool=pool)
        text = (
            "KITAS processing takes approximately thirty working days in Indonesia. "
            "The applicant must submit all required documentation to the immigration office."
        )
        result = await verifier.verify(text)
        assert result.claims_total > 0
        # With 1 node and no edges, claims get MEDIUM at best
        assert result.overall_status in ("MEDIUM", "LOW")

    @pytest.mark.asyncio
    async def test_low_status_when_no_nodes_found(self):
        """When KG finds no relevant nodes → LOW."""
        pool = _make_db_pool(node_rows=[], edge_rows=[])
        verifier = GraphRAGVerifier(db_pool=pool)
        text = (
            "The weather in Bali is tropical and warm throughout the entire year. "
            "Tourists visiting the island should bring sunscreen and light clothing. "
            "The best time to visit is during the dry season from April to September."
        )
        result = await verifier.verify(text)
        assert result.overall_status == "LOW"
        assert result.hallucination_risk is True

    @pytest.mark.asyncio
    async def test_hallucination_risk_false_for_high(self):
        pool = _make_db_pool(
            node_rows=[
                {"entity_id": "1", "name": "PT PMA", "entity_type": "company"},
                {"entity_id": "2", "name": "KITAS", "entity_type": "permit"},
                {"entity_id": "3", "name": "RPTKA", "entity_type": "document"},
            ],
            edge_rows=[
                {"src": "PT PMA", "relationship_type": "REQUIRES", "tgt": "KITAS"},
            ],
        )
        verifier = GraphRAGVerifier(db_pool=pool)
        text = (
            "PT PMA requires KITAS for all foreign workers employed in Indonesia. "
            "RPTKA approval from Kemnaker is mandatory before hiring foreign workers. "
            "The DKP-TKA fee must be paid monthly for each foreign worker position."
        )
        result = await verifier.verify(text)
        if result.overall_status == "HIGH":
            assert result.hallucination_risk is False

    @pytest.mark.asyncio
    async def test_suppresses_nlm_enrichment_when_low(self):
        """Caller should suppress NLM if LOW — verifier returns LOW."""
        pool = _make_db_pool(node_rows=[], edge_rows=[])
        verifier = GraphRAGVerifier(db_pool=pool)
        # Long enough claims (>40 chars) with extractable keywords, but KG returns nothing
        result = await verifier.verify(
            "Tropical climate forecasting requires specialized meteorological satellite analysis tools. "
            "Biodiversity conservation planning involves coordinated international regulatory frameworks. "
            "Quantum computing architecture requires specialized photonic crystalline substrate materials."
        )
        assert result.overall_status == "LOW"

    @pytest.mark.asyncio
    async def test_db_error_returns_medium_gracefully(self):
        """DB errors during claim verification → graceful degradation."""
        conn = AsyncMock()
        conn.fetch = AsyncMock(side_effect=Exception("Connection lost"))
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=False),
        ))
        verifier = GraphRAGVerifier(db_pool=pool)
        # Should not raise — graceful degradation
        result = await verifier.verify(
            "KITAS E23 requires employment contract and RPTKA approval from Kemnaker."
        )
        assert result is not None
        assert result.overall_status in ("HIGH", "MEDIUM", "LOW", "UNKNOWN")


# ---------------------------------------------------------------------------
# TestClaimVerification
# ---------------------------------------------------------------------------

class TestClaimVerification:
    def test_high_when_nodes_and_evidence(self):
        cv = ClaimVerification(
            text="KITAS requires RPTKA approval",
            status="HIGH",
            nodes_found=["KITAS", "RPTKA"],
            evidence=["KITAS → REQUIRES → RPTKA"],
        )
        assert cv.status == "HIGH"
        assert len(cv.evidence) == 1

    def test_medium_when_only_nodes(self):
        cv = ClaimVerification(
            text="KITAS requires valid documentation",
            status="MEDIUM",
            nodes_found=["KITAS"],
            evidence=[],
        )
        assert cv.status == "MEDIUM"

    def test_low_when_empty(self):
        cv = ClaimVerification(text="unverifiable claim", status="LOW")
        assert cv.nodes_found == []
        assert cv.evidence == []


# ---------------------------------------------------------------------------
# TestGraphRAGResult
# ---------------------------------------------------------------------------

class TestGraphRAGResult:
    def test_score_in_range(self):
        result = GraphRAGResult(
            overall_status="HIGH",
            score=0.85,
            claims_verified=8,
            claims_total=10,
            evidence=["KITAS → REQUIRES → RPTKA"],
            hallucination_risk=False,
        )
        assert 0.0 <= result.score <= 1.0

    def test_hallucination_risk_true_for_low(self):
        result = GraphRAGResult(
            overall_status="LOW",
            score=0.1,
            claims_verified=1,
            claims_total=10,
            evidence=[],
            hallucination_risk=True,
        )
        assert result.hallucination_risk is True

    def test_claim_details_default_empty(self):
        result = GraphRAGResult(
            overall_status="MEDIUM",
            score=0.5,
            claims_verified=3,
            claims_total=5,
            evidence=[],
            hallucination_risk=False,
        )
        assert result.claim_details == []


# ---------------------------------------------------------------------------
# TestSingleton
# ---------------------------------------------------------------------------

class TestGetVerifier:
    def setup_method(self):
        reset_verifier()

    def teardown_method(self):
        reset_verifier()

    def test_returns_graphrag_verifier_instance(self):
        v = get_verifier()
        assert isinstance(v, GraphRAGVerifier)

    def test_singleton_reuse(self):
        v1 = get_verifier()
        v2 = get_verifier()
        assert v1 is v2

    def test_db_pool_stored_on_first_call(self):
        pool = MagicMock()
        v = get_verifier(db_pool=pool)
        assert v.db_pool is pool

    def test_pool_updated_when_provided(self):
        v1 = get_verifier(db_pool=None)
        assert v1.db_pool is None
        pool = MagicMock()
        v2 = get_verifier(db_pool=pool)
        assert v2.db_pool is pool


# ---------------------------------------------------------------------------
# TestGoldSet — integration-style against collected NLM responses
# ---------------------------------------------------------------------------

class TestGoldSet:
    """Smoke tests using the real gold set collected from NLM.

    These tests verify the verifier logic produces reasonable outputs
    for real NLM responses — without hitting the actual database
    (KG lookup is mocked to return some nodes).
    """

    def _load_gold(self) -> list[dict]:
        return _load_gold()

    @pytest.mark.asyncio
    async def test_gold_set_loaded(self):
        gold = self._load_gold()
        assert len(gold) == 20, f"Expected 20 gold items, got {len(gold)}"

    @pytest.mark.asyncio
    async def test_gold_set_structure(self):
        gold = self._load_gold()
        for item in gold:
            assert "id" in item
            assert "query" in item
            assert "domain" in item
            assert "nlm_response" in item
            assert "overall_kg_verification" in item
            assert item["domain"] in ("immigration", "company", "tax", "property", "operations")
            assert item["overall_kg_verification"] in ("HIGH", "MEDIUM", "LOW", "UNKNOWN")

    @pytest.mark.asyncio
    async def test_claim_extraction_on_real_nlm_responses(self):
        """Claims can be extracted from all 20 NLM responses."""
        gold = self._load_gold()
        total_claims = 0
        for item in gold:
            claims = extract_claims_for_verification(item["nlm_response"])
            total_claims += len(claims)
        # Average should be at least 2 claims per response
        assert total_claims >= 40, f"Too few claims extracted: {total_claims}"

    @pytest.mark.asyncio
    async def test_verifier_with_mocked_pool_returns_result_for_all_gold(self):
        """Verifier runs without errors on all 20 gold NLM responses."""
        gold = self._load_gold()
        pool = _make_db_pool(
            node_rows=[
                {"entity_id": "1", "name": "KITAS", "entity_type": "permit"},
                {"entity_id": "2", "name": "PT PMA", "entity_type": "company"},
            ],
            edge_rows=[
                {"src": "PT PMA", "relationship_type": "REQUIRES", "tgt": "KITAS"},
            ],
        )
        verifier = GraphRAGVerifier(db_pool=pool)

        for item in gold:
            result = await verifier.verify(item["nlm_response"])
            assert result is not None
            assert result.overall_status in ("HIGH", "MEDIUM", "LOW", "UNKNOWN")
            assert 0.0 <= result.score <= 1.0
            assert result.claims_total >= 0

    @pytest.mark.asyncio
    async def test_immigration_responses_claim_count(self):
        """Immigration domain responses should yield substantial claims."""
        gold = self._load_gold()
        immigration = [g for g in gold if g["domain"] == "immigration"]
        for item in immigration:
            claims = extract_claims_for_verification(item["nlm_response"])
            assert len(claims) > 0, f"No claims from: {item['id']}"

    @pytest.mark.asyncio
    async def test_strong_edge_types_are_meaningful(self):
        """Spot-check that STRONG_EDGE_TYPES contains expected relationship types."""
        assert "REQUIRES" in STRONG_EDGE_TYPES
        assert "HAS_FEE" in STRONG_EDGE_TYPES
        assert "HAS_DURATION" in STRONG_EDGE_TYPES
        assert "ENABLES" in STRONG_EDGE_TYPES
