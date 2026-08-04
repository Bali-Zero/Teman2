"""
Unit tests for backend/services/rag/kg_subgraph_company.py

Covers all 4 node functions:
  - identify_company_type_node
  - check_pma_eligibility_node
  - get_capital_requirements_node
  - synthesize_company_workflow_node
Plus: build_company_subgraph construction.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.rag.kg_subgraph_company import (
    build_company_subgraph,
    check_pma_eligibility_node,
    get_capital_requirements_node,
    identify_company_type_node,
    synthesize_company_workflow_node,
)

# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def mock_llm():
    return MagicMock()


@pytest.fixture
def mock_db_pool():
    pool = MagicMock()
    conn = AsyncMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acquire_cm)
    pool._mock_conn = conn
    return pool


def _base_state(**overrides):
    state = {
        "query": "How to set up a company?",
        "user_context": {},
        "current_entities": [],
        "visited_entities": set(),
        "relationship_chains": [],
        "workflow": None,
        "company_type": None,
        "is_foreign_investor": False,
        "capital_amount": None,
        "kbli_codes": [],
        "licensing_requirements": [],
        "shareholders": [],
        "legal_structure_recommendations": [],
    }
    state.update(overrides)
    return state


# ============================================================
# identify_company_type_node
# ============================================================


class TestIdentifyCompanyType:
    @pytest.mark.asyncio
    async def test_pt_pma_in_query(self, mock_llm):
        state = _base_state(query="I want to set up a PT PMA in Bali")
        result = await identify_company_type_node(state, mock_llm, db_pool=None)
        assert result["company_type"] == "pt_pma"

    @pytest.mark.asyncio
    async def test_foreign_citizen_company(self, mock_llm):
        state = _base_state(
            query="I want to start a company",
            user_context={"citizenship": "foreign"},
        )
        result = await identify_company_type_node(state, mock_llm, db_pool=None)
        assert result["company_type"] == "pt_pma"
        assert result["is_foreign_investor"] is True

    @pytest.mark.asyncio
    async def test_cv_in_query(self, mock_llm):
        state = _base_state(query="How to register a CV?")
        result = await identify_company_type_node(state, mock_llm, db_pool=None)
        assert result["company_type"] == "cv"

    @pytest.mark.asyncio
    async def test_commanditaire_in_query(self, mock_llm):
        state = _base_state(query="commanditaire vennootschap setup")
        result = await identify_company_type_node(state, mock_llm, db_pool=None)
        assert result["company_type"] == "cv"

    @pytest.mark.asyncio
    async def test_perorangan_in_query(self, mock_llm):
        state = _base_state(query="I want perorangan business")
        result = await identify_company_type_node(state, mock_llm, db_pool=None)
        assert result["company_type"] == "perorangan"

    @pytest.mark.asyncio
    async def test_sole_proprietor_in_query(self, mock_llm):
        state = _base_state(query="sole proprietor registration")
        result = await identify_company_type_node(state, mock_llm, db_pool=None)
        assert result["company_type"] == "perorangan"

    @pytest.mark.asyncio
    async def test_pt_lokal_in_query(self, mock_llm):
        state = _base_state(query="setup PT in Jakarta")
        result = await identify_company_type_node(state, mock_llm, db_pool=None)
        assert result["company_type"] == "pt_lokal"

    @pytest.mark.asyncio
    async def test_default_foreign(self, mock_llm):
        state = _base_state(
            query="I want to start a business",
            user_context={"citizenship": "foreign"},
        )
        result = await identify_company_type_node(state, mock_llm, db_pool=None)
        assert result["company_type"] == "pt_pma"

    @pytest.mark.asyncio
    async def test_default_local(self, mock_llm):
        state = _base_state(
            query="I want to start a business",
            user_context={"citizenship": "indonesian"},
        )
        result = await identify_company_type_node(state, mock_llm, db_pool=None)
        assert result["company_type"] == "perorangan"

    @pytest.mark.asyncio
    async def test_kbli_from_query_with_db(self, mock_llm, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchval = AsyncMock(return_value=True)

        state = _base_state(query="KBLI 47111 company setup")
        result = await identify_company_type_node(state, mock_llm, db_pool=mock_db_pool)
        assert result["company_type"] == "pt_pma"
        assert result["is_foreign_investor"] is True

    @pytest.mark.asyncio
    async def test_kbli_from_entities_with_db(self, mock_llm, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchval = AsyncMock(return_value=False)

        state = _base_state(
            query="company setup help",
            current_entities=["kbli:47111", "visa:b211"],
        )
        result = await identify_company_type_node(state, mock_llm, db_pool=mock_db_pool)
        # KBLI does NOT require pt_pma, so keep heuristic default
        assert result["company_type"] is not None

    @pytest.mark.asyncio
    async def test_kbli_db_failure_uses_heuristic(self, mock_llm, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchval = AsyncMock(side_effect=Exception("DB error"))

        state = _base_state(query="KBLI 47111 setup")
        result = await identify_company_type_node(state, mock_llm, db_pool=mock_db_pool)
        # Falls back to heuristic
        assert result["company_type"] is not None

    @pytest.mark.asyncio
    async def test_kbli_codes_from_state(self, mock_llm, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchval = AsyncMock(return_value=True)

        state = _base_state(
            query="company setup",
            kbli_codes=["kbli:62011"],
        )
        result = await identify_company_type_node(state, mock_llm, db_pool=mock_db_pool)
        assert result["company_type"] == "pt_pma"


# ============================================================
# check_pma_eligibility_node
# ============================================================


class TestCheckPMAEligibility:
    @pytest.mark.asyncio
    async def test_skips_non_foreign(self, mock_db_pool):
        state = _base_state(is_foreign_investor=False)
        await check_pma_eligibility_node(state, mock_db_pool)
        # Should return state unchanged (no DB call)
        mock_db_pool.acquire.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_kbli_codes_warns(self, mock_db_pool):
        state = _base_state(
            is_foreign_investor=True,
            kbli_codes=[],
            current_entities=[],
        )
        result = await check_pma_eligibility_node(state, mock_db_pool)
        # Should return without error
        assert result is not None

    @pytest.mark.asyncio
    async def test_kbli_allowed(self, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "entity_id": "kbli:47111",
                    "entity_type": "kbli",
                    "name": "Perdagangan Eceran",
                    "properties": {"pma_status": "allowed"},
                }
            ]
        )

        state = _base_state(
            is_foreign_investor=True,
            kbli_codes=["kbli:47111"],
        )
        result = await check_pma_eligibility_node(state, mock_db_pool)
        assert len(result["licensing_requirements"]) >= 1
        req = result["licensing_requirements"][-1]
        assert req["requirement_type"] == "pma_eligibility"
        assert req["details"][0]["eligible"] is True

    @pytest.mark.asyncio
    async def test_kbli_restricted_is_undetermined_not_closed(self, mock_db_pool):
        """
        "restricted" (the English of TERBATAS) means capped, NOT closed.

        This assertion used to read ``is False`` — it PINNED the L2.11 defect:
        a capped code answered as ineligible denies a lawful foreign stake
        (the sea-cabotage codes allow 49%). The KG carries no cap field, so
        the honest answer from this store is "undetermined, go read the cap".
        """
        conn = mock_db_pool._mock_conn
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "entity_id": "kbli:01111",
                    "entity_type": "kbli",
                    "name": "Pertanian Padi",
                    "properties": {"pma_status": "restricted"},
                }
            ]
        )

        state = _base_state(
            is_foreign_investor=True,
            kbli_codes=["kbli:01111"],
        )
        result = await check_pma_eligibility_node(state, mock_db_pool)
        pma_detail = result["licensing_requirements"][-1]["details"][0]
        assert pma_detail["eligible"] is None
        assert "cap" in pma_detail["eligibility_basis"]


class TestPmaEligibilityVocabulary:
    """
    The store speaks Indonesian; the old code tested itself in English.

    Censused on the live KG 2026-08-03: TERBUKA 1464 · TERTUTUP 61 ·
    TERBATAS 29 · "Verify at OSS" 4, and ZERO rows carrying "allowed" /
    "open" / "restricted". The old ``pma_status in ["allowed", "open"]``
    therefore answered False for every code in production, including all
    1,464 fully open ones — and both existing tests passed, because they
    invented a vocabulary to be right about.
    """

    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            ("TERBUKA", True),
            ("TERTUTUP", False),
            ("TERBATAS", None),
            ("Verify at OSS", None),
            ("terbuka", True),  # case/whitespace must not decide a verdict
            ("  TERBUKA  ", True),
        ],
    )
    @pytest.mark.asyncio
    async def test_live_vocabulary(self, mock_db_pool, status, expected):
        conn = mock_db_pool._mock_conn
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "entity_id": "kbli:56101",
                    "entity_type": "kbli_code",
                    "name": "Restaurant",
                    "properties": {"pma_status": status},
                }
            ]
        )
        state = _base_state(is_foreign_investor=True, kbli_codes=["kbli:56101"])
        result = await check_pma_eligibility_node(state, mock_db_pool)
        assert result["licensing_requirements"][-1]["details"][0]["eligible"] is expected

    @pytest.mark.parametrize("status", ["", None, "OPEN-ISH", "TERBUK", 42])
    @pytest.mark.asyncio
    async def test_unknown_status_is_never_a_silent_false(self, mock_db_pool, status):
        """An unrecognised or missing status is undetermined, never "closed"."""
        conn = mock_db_pool._mock_conn
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "entity_id": "kbli:56101",
                    "entity_type": "kbli",
                    "name": "Restaurant",
                    "properties": {"pma_status": status},
                }
            ]
        )
        state = _base_state(is_foreign_investor=True, kbli_codes=["kbli:56101"])
        result = await check_pma_eligibility_node(state, mock_db_pool)
        assert result["licensing_requirements"][-1]["details"][0]["eligible"] is None

    @pytest.mark.parametrize(
        "code", ["kbli:55111", "kbli:62011", "kbli:62021", "kbli:68110", "kbli:73110", "kbli:74100"]
    )
    @pytest.mark.asyncio
    async def test_reachable_node_without_pma_layer_is_undetermined(self, mock_db_pool, code):
        """
        These six are REAL rows this query now reaches and cannot answer.

        Measured 2026-08-03: of the 1,568 ids matching `kbli:NNNNN`, 1,562
        carry a `pma_status` and SIX do not — 55111 / 62011 / 62021 / 68110 /
        73110 / 74100, all filed as `kbli_code`. They are exactly the rows the
        old `entity_type = 'kbli'` filter dropped, so widening the query makes
        them reachable for the first time; each must answer "undetermined".

        (An earlier version of this test justified itself with the 12,075
        kbli nodes that carry no PMA layer — true, but IRRELEVANT: their ids
        are `kbli_kbli_NNNNN`-shaped and this query can never reach them. Real
        test, wrong reason.)
        """
        conn = mock_db_pool._mock_conn
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "entity_id": code,
                    "entity_type": "kbli_code",
                    "name": f"KBLI {code.split(':')[1]}",
                    "properties": {},
                }
            ]
        )
        state = _base_state(is_foreign_investor=True, kbli_codes=[code])
        result = await check_pma_eligibility_node(state, mock_db_pool)
        detail = result["licensing_requirements"][-1]["details"][0]
        assert detail["eligible"] is None
        assert detail["eligibility_state"] == "undetermined"
        assert detail["pma_status"] == "unknown"

    @pytest.mark.parametrize(
        ("status", "expected_state"),
        [
            ("TERBUKA", "open"),
            ("TERTUTUP", "closed"),
            ("TERBATAS", "undetermined"),
            ("Verify at OSS", "undetermined"),
            ("wat", "undetermined"),
        ],
    )
    @pytest.mark.asyncio
    async def test_state_string_and_bool_can_never_disagree(
        self, mock_db_pool, status, expected_state
    ):
        """
        One writer, two renderings.

        `eligible` is derived from `eligibility_state` in a single place; this
        pins that they cannot drift apart, and that a consumer branching on
        the string gets the same verdict as one comparing the bool with `is`.
        """
        conn = mock_db_pool._mock_conn
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "entity_id": "kbli:56101",
                    "entity_type": "kbli_code",
                    "name": "Restaurant",
                    "properties": {"pma_status": status},
                }
            ]
        )
        state = _base_state(is_foreign_investor=True, kbli_codes=["kbli:56101"])
        result = await check_pma_eligibility_node(state, mock_db_pool)
        detail = result["licensing_requirements"][-1]["details"][0]
        assert detail["eligibility_state"] == expected_state
        assert detail["eligible"] is {"open": True, "closed": False, "undetermined": None}[
            expected_state
        ]

    @pytest.mark.asyncio
    async def test_truthiness_hazard_is_documented_by_a_failing_consumer(self, mock_db_pool):
        """
        A consumer writing `if not detail["eligible"]` denies a CAPPED code.

        This is the L2.11 defect arriving through a downstream truthiness test
        rather than through this module's table, and it is why the string
        state exists. The test pins BOTH halves: the naive read is wrong, and
        the state string gives the consumer a way to be right.
        """
        conn = mock_db_pool._mock_conn
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "entity_id": "kbli:79110",  # TERBATAS on the live KG
                    "entity_type": "kbli_code",
                    "name": "Travel Agency",
                    "properties": {"pma_status": "TERBATAS"},
                }
            ]
        )
        state = _base_state(is_foreign_investor=True, kbli_codes=["kbli:79110"])
        result = await check_pma_eligibility_node(state, mock_db_pool)
        detail = result["licensing_requirements"][-1]["details"][0]

        # The naive consumer would deny a lawful capped stake...
        assert not detail["eligible"]
        # ...while the honest verdict is "we do not know the cap from here".
        assert detail["eligible"] is not False
        assert detail["eligibility_state"] == "undetermined"

    @pytest.mark.asyncio
    async def test_jsonb_returned_as_string_still_reads(self, mock_db_pool):
        """A pool without a jsonb codec hands back str — must not crash."""
        conn = mock_db_pool._mock_conn
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "entity_id": "kbli:56101",
                    "entity_type": "kbli",
                    "name": "Restaurant",
                    "properties": '{"pma_status": "TERTUTUP"}',
                }
            ]
        )
        state = _base_state(is_foreign_investor=True, kbli_codes=["kbli:56101"])
        result = await check_pma_eligibility_node(state, mock_db_pool)
        assert result["licensing_requirements"][-1]["details"][0]["eligible"] is False

    @pytest.mark.asyncio
    async def test_code_absent_from_kg_is_reported_not_dropped(self, mock_db_pool):
        """
        Silence reads downstream as "no restriction found".

        A requested code the KG has no row for must come back as an explicit
        undetermined entry, not as an absent one.
        """
        conn = mock_db_pool._mock_conn
        conn.fetch = AsyncMock(return_value=[])
        state = _base_state(is_foreign_investor=True, kbli_codes=["kbli:99999"])
        result = await check_pma_eligibility_node(state, mock_db_pool)
        details = result["licensing_requirements"][-1]["details"]
        assert len(details) == 1
        assert details[0]["kbli_code"] == "kbli:99999"
        assert details[0]["eligible"] is None
        assert "no node in the KG" in details[0]["eligibility_basis"]

    @pytest.mark.asyncio
    async def test_query_is_not_filtered_by_entity_type(self, mock_db_pool):
        """
        The 10 highest-traffic codes are filed as `kbli_code`, not `kbli`.

        Measured 2026-08-03: 47721 / 55111 / 56101 / 62011 / 62021 / 68110 /
        70201 / 73110 / 74100 / 79110 live ONLY under `entity_type='kbli_code'`
        (zero overlap with the 1,558 filed as `kbli`), so the old
        `AND entity_type = 'kbli'` made the restaurant code invisible.
        """
        conn = mock_db_pool._mock_conn
        conn.fetch = AsyncMock(return_value=[])
        state = _base_state(is_foreign_investor=True, kbli_codes=["kbli:56101"])
        await check_pma_eligibility_node(state, mock_db_pool)
        sql = conn.fetch.await_args.args[0]
        assert "entity_type = 'kbli'" not in sql
        assert "entity_id = ANY" in sql

    @pytest.mark.asyncio
    async def test_extract_kbli_from_entities(self, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetch = AsyncMock(return_value=[])

        state = _base_state(
            is_foreign_investor=True,
            kbli_codes=[],
            current_entities=["kbli:62011"],
        )
        result = await check_pma_eligibility_node(state, mock_db_pool)
        assert result["kbli_codes"] == ["kbli:62011"]


# ============================================================
# get_capital_requirements_node
# ============================================================


class TestGetCapitalRequirements:
    @pytest.mark.asyncio
    async def test_pt_pma_capital(self, mock_db_pool):
        state = _base_state(company_type="pt_pma")
        result = await get_capital_requirements_node(state, mock_db_pool)
        assert result["capital_amount"] == 10_000_000_000
        req = result["licensing_requirements"][-1]
        assert req["requirement_type"] == "capital"
        assert req["details"]["min_capital"] == 10_000_000_000

    @pytest.mark.asyncio
    async def test_pt_lokal_capital(self, mock_db_pool):
        state = _base_state(company_type="pt_lokal")
        result = await get_capital_requirements_node(state, mock_db_pool)
        assert result["capital_amount"] == 50_000_000

    @pytest.mark.asyncio
    async def test_cv_no_capital(self, mock_db_pool):
        state = _base_state(company_type="cv")
        result = await get_capital_requirements_node(state, mock_db_pool)
        assert result["capital_amount"] is None

    @pytest.mark.asyncio
    async def test_perorangan_no_capital(self, mock_db_pool):
        state = _base_state(company_type="perorangan")
        result = await get_capital_requirements_node(state, mock_db_pool)
        assert result["capital_amount"] is None

    @pytest.mark.asyncio
    async def test_unknown_type_empty(self, mock_db_pool):
        state = _base_state(company_type="unknown_type")
        result = await get_capital_requirements_node(state, mock_db_pool)
        assert result["capital_amount"] is None


# ============================================================
# synthesize_company_workflow_node
# ============================================================


class TestSynthesizeCompanyWorkflow:
    @pytest.mark.asyncio
    async def test_pt_pma_workflow(self):
        state = _base_state(
            company_type="pt_pma",
            is_foreign_investor=True,
            capital_amount=10_000_000_000,
            kbli_codes=["kbli:62011"],
        )
        result = await synthesize_company_workflow_node(state)
        wf = result["workflow"]
        assert wf is not None
        assert wf["type"] == "company_setup"
        assert wf["id"] == "company_setup:pt_pma"
        assert "PT_PMA" in wf["name"]
        # Should have: structure, capital, registration, licensing, bank
        assert len(wf["steps"]) == 5
        assert wf["confidence"] > 0
        assert "confidence_breakdown" in wf

    @pytest.mark.asyncio
    async def test_cv_workflow_no_capital_step(self):
        state = _base_state(
            company_type="cv",
            is_foreign_investor=False,
            capital_amount=None,
        )
        result = await synthesize_company_workflow_node(state)
        wf = result["workflow"]
        # No capital step, no KBLI step => structure + registration + bank = 3
        assert len(wf["steps"]) == 3
        step_actions = [s["action"] for s in wf["steps"]]
        assert any("CV" in a for a in step_actions)

    @pytest.mark.asyncio
    async def test_workflow_with_kbli(self):
        state = _base_state(
            company_type="pt_lokal",
            capital_amount=50_000_000,
            kbli_codes=["kbli:47111"],
        )
        result = await synthesize_company_workflow_node(state)
        step_actions = [s["action"] for s in result["workflow"]["steps"]]
        assert any("KBLI" in a for a in step_actions)

    @pytest.mark.asyncio
    async def test_workflow_without_kbli(self):
        state = _base_state(
            company_type="perorangan",
            capital_amount=None,
            kbli_codes=[],
        )
        result = await synthesize_company_workflow_node(state)
        step_actions = [s["action"] for s in result["workflow"]["steps"]]
        assert not any("KBLI" in a for a in step_actions)

    @pytest.mark.asyncio
    async def test_confidence_with_db_validation(self):
        state = _base_state(
            company_type="pt_pma",
            is_foreign_investor=True,
            capital_amount=10_000_000_000,
        )
        result = await synthesize_company_workflow_node(state)
        # is_foreign_investor = True means has_db_validation = True
        assert result["workflow"]["confidence"] > 0.5

    @pytest.mark.asyncio
    async def test_confidence_without_db_validation(self):
        state = _base_state(
            company_type="cv",
            is_foreign_investor=False,
            capital_amount=None,
        )
        result = await synthesize_company_workflow_node(state)
        assert result["workflow"]["confidence"] > 0


# ============================================================
# build_company_subgraph
# ============================================================


class TestBuildCompanySubgraph:
    def test_build_returns_state_graph(self, mock_db_pool, mock_llm):
        sg = build_company_subgraph(mock_db_pool, mock_llm)
        # Should be a StateGraph instance (not compiled)
        assert sg is not None
        # Verify it has the expected nodes
        assert "identify_company_type" in sg.nodes
        assert "check_pma_eligibility" in sg.nodes
        assert "get_capital_requirements" in sg.nodes
        assert "synthesize_company_workflow" in sg.nodes
