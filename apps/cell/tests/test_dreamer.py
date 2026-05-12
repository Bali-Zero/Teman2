# apps/cell/tests/test_dreamer.py
"""Tests for Dreamer nocturnal consolidation."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date

from cell.memory.dreamer import (
    Dreamer,
    DreamResult,
    _MAX_RULES_PER_DREAM,
    _normalize_rule,
)


class TestDreamResult:
    def test_dataclass_fields(self):
        dr = DreamResult(
            dream_date=date(2026, 4, 3),
            episodes_count=5,
            rules_extracted=["When RT > 2000ms after yellow, restart_service"],
            merged_count=1,
            gaps_identified=["Never seen Qdrant red — unclear what to do"],
            summary="Quiet day with one restart.",
        )
        assert dr.episodes_count == 5
        assert len(dr.rules_extracted) == 1
        assert len(dr.gaps_identified) == 1


class TestDreamerFetchEpisodes:
    @pytest.fixture
    def pool_with_episodes(self):
        rows = [
            {
                "id": 1, "timestamp": 1743700000.0,
                "situation": json.dumps({"health_status": "red", "response_time_ms": 3000}),
                "emotion": "stressed", "action_taken": "restart_service",
                "outcome": "success", "lesson": "Restart worked when RT > 3000ms",
                "recall_count": 2,
            },
            {
                "id": 2, "timestamp": 1743710000.0,
                "situation": json.dumps({"health_status": "yellow", "response_time_ms": 1200}),
                "emotion": "alert", "action_taken": "observe",
                "outcome": "partial", "lesson": "Yellow resolved on its own",
                "recall_count": 0,
            },
        ]
        acquire_ctx = AsyncMock()
        acquire_ctx.__aenter__ = AsyncMock(return_value=acquire_ctx)
        acquire_ctx.__aexit__ = AsyncMock(return_value=None)
        acquire_ctx.fetch = AsyncMock(return_value=rows)
        acquire_ctx.execute = AsyncMock()
        acquire_ctx.fetchval = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=acquire_ctx)
        return pool, acquire_ctx

    @pytest.mark.asyncio
    async def test_fetch_todays_episodes(self, pool_with_episodes):
        db_pool, conn = pool_with_episodes
        dreamer = Dreamer(pool=db_pool, ollama_url="http://localhost:11434")
        episodes = await dreamer._fetch_todays_episodes()
        assert len(episodes) == 2
        assert episodes[0]["action_taken"] == "restart_service"


class TestDreamerRun:
    @pytest.fixture
    def pool_empty(self):
        acquire_ctx = AsyncMock()
        acquire_ctx.__aenter__ = AsyncMock(return_value=acquire_ctx)
        acquire_ctx.__aexit__ = AsyncMock(return_value=None)
        acquire_ctx.fetch = AsyncMock(return_value=[])
        acquire_ctx.execute = AsyncMock()
        acquire_ctx.fetchval = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=acquire_ctx)
        return pool

    @pytest.mark.asyncio
    async def test_dream_no_episodes_returns_empty_result(self, pool_empty):
        dreamer = Dreamer(pool=pool_empty, ollama_url="http://localhost:11434")
        result = await dreamer.dream()
        assert result is not None
        assert result.episodes_count == 0
        assert result.rules_extracted == []
        assert result.gaps_identified == []

    @pytest.mark.asyncio
    async def test_dream_with_episodes_calls_llm(self):
        rows = [
            {
                "id": 1, "timestamp": 1743700000.0,
                "situation": json.dumps({"health_status": "red"}),
                "emotion": "stressed", "action_taken": "restart_service",
                "outcome": "success", "lesson": "Restart fixed it",
                "recall_count": 1,
            }
        ]
        acquire_ctx = AsyncMock()
        acquire_ctx.__aenter__ = AsyncMock(return_value=acquire_ctx)
        acquire_ctx.__aexit__ = AsyncMock(return_value=None)
        acquire_ctx.fetch = AsyncMock(return_value=rows)
        acquire_ctx.execute = AsyncMock()
        acquire_ctx.fetchval = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=acquire_ctx)

        dreamer = Dreamer(pool=pool, ollama_url="http://localhost:11434")

        with patch.object(dreamer, "_extract_rules_with_llm", new_callable=AsyncMock) as mock_rules:
            mock_rules.return_value = (
                ["When RED + restart -> success, trust restart for future RED"],
                ["Have not seen Qdrant failure yet"]
            )
            result = await dreamer.dream()

        assert result.episodes_count == 1
        assert len(result.rules_extracted) == 1
        assert len(result.gaps_identified) == 1

    @pytest.mark.asyncio
    async def test_dream_llm_failure_still_returns_result(self):
        """When LLM fails, dream() returns result with empty rules/gaps (graceful degradation)."""
        rows = [
            {
                "id": 1, "timestamp": 1743700000.0,
                "situation": json.dumps({"health_status": "yellow"}),
                "emotion": "alert", "action_taken": "observe",
                "outcome": "partial", "lesson": "Watched and waited",
                "recall_count": 0,
            }
        ]
        acquire_ctx = AsyncMock()
        acquire_ctx.__aenter__ = AsyncMock(return_value=acquire_ctx)
        acquire_ctx.__aexit__ = AsyncMock(return_value=None)
        acquire_ctx.fetch = AsyncMock(return_value=rows)
        acquire_ctx.execute = AsyncMock()
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=acquire_ctx)

        dreamer = Dreamer(pool=pool, ollama_url="http://localhost:11434")

        with patch.object(dreamer, "_extract_rules_with_llm", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = ([], [])  # LLM returned nothing
            result = await dreamer.dream()

        assert result.episodes_count == 1
        assert result.rules_extracted == []
        assert result.gaps_identified == []
        assert "episode" in result.summary.lower() or "rule" in result.summary.lower()


# ---------------------------------------------------------------------------
# TestNormalizeRule (LEVA 1, 2026-05-13)
# ---------------------------------------------------------------------------


class TestNormalizeRule:
    def test_strips_trailing_punctuation(self):
        assert _normalize_rule("Rule!  ") == "rule"
        assert _normalize_rule("Rule.") == "rule"
        assert _normalize_rule("Rule?") == "rule"

    def test_lowercases(self):
        assert _normalize_rule("RULE TEXT") == "rule text"

    def test_collapses_whitespace(self):
        assert _normalize_rule("rule    with     gaps") == "rule with gaps"

    def test_empty_returns_empty(self):
        assert _normalize_rule("") == ""
        assert _normalize_rule(None) == ""  # type: ignore[arg-type]

    def test_dedup_invariance(self):
        # Same canonical form for trivial variants.
        a = _normalize_rule("When health is RED, restart_service is required.")
        b = _normalize_rule("when  health is red, restart_service is required!  ")
        assert a == b


# ---------------------------------------------------------------------------
# TestUpsertRulesAsSkills (LEVA 1, 2026-05-13)
# ---------------------------------------------------------------------------


class TestUpsertRulesAsSkills:
    @pytest.fixture
    def pool_no_existing(self):
        """Pool whose SELECT id returns None (no dedup hit) — every INSERT runs."""
        acquire_ctx = AsyncMock()
        acquire_ctx.__aenter__ = AsyncMock(return_value=acquire_ctx)
        acquire_ctx.__aexit__ = AsyncMock(return_value=None)
        acquire_ctx.fetchval = AsyncMock(return_value=None)
        acquire_ctx.execute = AsyncMock()
        acquire_ctx.fetch = AsyncMock(return_value=[])
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=acquire_ctx)
        return pool, acquire_ctx

    @pytest.fixture
    def pool_all_existing(self):
        """Pool whose SELECT id always returns an int — every rule is dedup'd."""
        acquire_ctx = AsyncMock()
        acquire_ctx.__aenter__ = AsyncMock(return_value=acquire_ctx)
        acquire_ctx.__aexit__ = AsyncMock(return_value=None)
        acquire_ctx.fetchval = AsyncMock(return_value=42)
        acquire_ctx.execute = AsyncMock()
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=acquire_ctx)
        return pool, acquire_ctx

    @pytest.mark.asyncio
    async def test_empty_list_returns_zero(self, pool_no_existing):
        pool, _ = pool_no_existing
        d = Dreamer(pool=pool)
        inserted = await d._upsert_rules_as_skills([], date(2026, 5, 13))
        assert inserted == 0

    @pytest.mark.asyncio
    async def test_inserts_new_rules(self, pool_no_existing):
        pool, conn = pool_no_existing
        d = Dreamer(pool=pool)
        rules = [
            "When health is red, restart_service is required.",
            "When yellow with high RT, scale_up is proposed.",
        ]
        inserted = await d._upsert_rules_as_skills(rules, date(2026, 5, 13))
        assert inserted == 2
        # Two INSERTs ran (one per rule).
        insert_calls = [
            c for c in conn.execute.await_args_list
            if "INSERT INTO cell_skills" in c.args[0]
        ]
        assert len(insert_calls) == 2

    @pytest.mark.asyncio
    async def test_dedup_skips_existing(self, pool_all_existing):
        pool, conn = pool_all_existing
        d = Dreamer(pool=pool)
        rules = ["Rule one.", "Rule two."]
        inserted = await d._upsert_rules_as_skills(rules, date(2026, 5, 13))
        assert inserted == 0
        # No INSERT calls — only the SELECTs ran.
        assert all(
            "INSERT INTO cell_skills" not in c.args[0]
            for c in conn.execute.await_args_list
        )

    @pytest.mark.asyncio
    async def test_caps_at_max_rules(self, pool_no_existing):
        pool, conn = pool_no_existing
        d = Dreamer(pool=pool)
        # Distinct strings so dedup doesn't trim them.
        rules = [f"Rule number {i}." for i in range(50)]
        inserted = await d._upsert_rules_as_skills(rules, date(2026, 5, 13))
        assert inserted == _MAX_RULES_PER_DREAM == 20

    @pytest.mark.asyncio
    async def test_insert_failure_isolated(self):
        """An exception inside INSERT must not blow up the whole upsert call."""
        acquire_ctx = AsyncMock()
        acquire_ctx.__aenter__ = AsyncMock(return_value=acquire_ctx)
        acquire_ctx.__aexit__ = AsyncMock(return_value=None)
        acquire_ctx.fetchval = AsyncMock(return_value=None)
        # First execute call (INSERT) raises; subsequent ones succeed.
        call_count = [0]

        async def flaky_execute(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("simulated DB outage")
            return None

        acquire_ctx.execute = AsyncMock(side_effect=flaky_execute)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=acquire_ctx)

        d = Dreamer(pool=pool)
        rules = ["Rule A.", "Rule B."]
        inserted = await d._upsert_rules_as_skills(rules, date(2026, 5, 13))
        # One INSERT failed, one succeeded.
        assert inserted == 1

    @pytest.mark.asyncio
    async def test_skill_name_is_deterministic(self, pool_no_existing):
        """Same rule -> same skill_name across calls (dedup hash stable)."""
        pool, conn = pool_no_existing
        d = Dreamer(pool=pool)
        await d._upsert_rules_as_skills(
            ["Same rule text."], date(2026, 5, 13)
        )
        await d._upsert_rules_as_skills(
            ["same rule text!  "], date(2026, 5, 13)
        )
        # 2 SELECT calls fired (one per call). Compare the name parameter.
        select_calls = [
            c for c in conn.fetchval.await_args_list
            if "SELECT id FROM cell_skills" in c.args[0]
        ]
        assert len(select_calls) == 2
        # Both selects use the same skill_name parameter -> dedup hash stable.
        assert select_calls[0].args[1] == select_calls[1].args[1]

    @pytest.mark.asyncio
    async def test_precondition_has_dreamer_provenance(self, pool_no_existing):
        pool, conn = pool_no_existing
        d = Dreamer(pool=pool)
        await d._upsert_rules_as_skills(
            ["A rule."], date(2026, 5, 13)
        )
        insert_call = next(
            c for c in conn.execute.await_args_list
            if "INSERT INTO cell_skills" in c.args[0]
        )
        # precondition is positional arg 5 in the INSERT.
        precondition_json = insert_call.args[5]
        precondition = json.loads(precondition_json)
        assert precondition["source"] == "dreamer"
        assert precondition["source_confidence"] == 0.6
        assert precondition["source_dream_date"] == "2026-05-13"
        assert "rule_text_sha1" in precondition

    @pytest.mark.asyncio
    async def test_dream_end_to_end_upserts_rules(self):
        """dream() with non-empty rules calls _upsert_rules_as_skills."""
        rows = [
            {
                "id": 1, "timestamp": 1743700000.0,
                "situation": json.dumps({"health_status": "red"}),
                "emotion": "stressed", "action_taken": "restart_service",
                "outcome": "success", "lesson": "Restart fixed it",
                "recall_count": 1,
            }
        ]
        acquire_ctx = AsyncMock()
        acquire_ctx.__aenter__ = AsyncMock(return_value=acquire_ctx)
        acquire_ctx.__aexit__ = AsyncMock(return_value=None)
        acquire_ctx.fetch = AsyncMock(return_value=rows)
        acquire_ctx.fetchval = AsyncMock(return_value=None)
        acquire_ctx.execute = AsyncMock()
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=acquire_ctx)

        dreamer = Dreamer(pool=pool, ollama_url="http://localhost:11434")

        with patch.object(
            dreamer, "_extract_rules_with_llm", new_callable=AsyncMock
        ) as mock_rules, patch.object(
            dreamer, "_upsert_rules_as_skills", new_callable=AsyncMock
        ) as mock_upsert:
            mock_rules.return_value = (
                ["Rule one from dream."],
                [],
            )
            mock_upsert.return_value = 1
            result = await dreamer.dream()

        assert result.rules_extracted == ["Rule one from dream."]
        mock_upsert.assert_awaited_once()
        # Verify positional args: (rules_list, dream_date)
        upsert_args = mock_upsert.await_args
        assert upsert_args.args[0] == ["Rule one from dream."]

    @pytest.mark.asyncio
    async def test_dream_upsert_failure_does_not_break_dream(self):
        """If _upsert_rules_as_skills raises, dream() still returns result."""
        rows = [
            {
                "id": 1, "timestamp": 1743700000.0,
                "situation": json.dumps({"health_status": "red"}),
                "emotion": "stressed", "action_taken": "restart_service",
                "outcome": "success", "lesson": "Restart fixed it",
                "recall_count": 1,
            }
        ]
        acquire_ctx = AsyncMock()
        acquire_ctx.__aenter__ = AsyncMock(return_value=acquire_ctx)
        acquire_ctx.__aexit__ = AsyncMock(return_value=None)
        acquire_ctx.fetch = AsyncMock(return_value=rows)
        acquire_ctx.fetchval = AsyncMock(return_value=None)
        acquire_ctx.execute = AsyncMock()
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=acquire_ctx)

        dreamer = Dreamer(pool=pool, ollama_url="http://localhost:11434")
        with patch.object(
            dreamer, "_extract_rules_with_llm", new_callable=AsyncMock
        ) as mock_rules, patch.object(
            dreamer, "_upsert_rules_as_skills",
            new=AsyncMock(side_effect=RuntimeError("simulated upsert crash")),
        ):
            mock_rules.return_value = (["A rule."], [])
            result = await dreamer.dream()
        assert result.episodes_count == 1
        assert result.rules_extracted == ["A rule."]
