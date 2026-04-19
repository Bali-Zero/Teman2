"""Tests for OracleCouncil + OracleOrchestrator (Sprint 18)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.services.cognitive.models import (
    UltraMove,
    UltraMoveDecision,
)
from backend.services.cognitive.oracle import (
    MAX_MOVES,
    OracleCouncil,
    OracleOrchestrator,
    OracleProposal,
    _coerce_move,
    _fallback_merge,
)
from backend.services.council.cli_runners import CLIRunner, RunnerResult

# ── Mock runner ────────────────────────────────────────────


@dataclass
class MockRunner(CLIRunner):
    name: str = "mock"
    default_timeout: int = 60
    scripts: list[str] = field(default_factory=list)
    call_count: int = 0
    fail: bool = False

    async def run(self, prompt, timeout=None) -> RunnerResult:
        idx = self.call_count
        self.call_count += 1
        if self.fail:
            return RunnerResult(
                runner_name=self.name, prompt_chars=len(prompt),
                ok=False, error="runner down",
            )
        if idx >= len(self.scripts):
            return RunnerResult(
                runner_name=self.name, prompt_chars=len(prompt),
                ok=False, error="out of script",
            )
        return RunnerResult(
            runner_name=self.name, prompt_chars=len(prompt),
            ok=True, output=self.scripts[idx],
        )


def _moves_json(moves: list[dict]) -> str:
    return json.dumps({"moves": moves})


def _judge_json(moves: list[dict]) -> str:
    return json.dumps({"final_moves": moves})


def _valid_move(thesis: str = "x") -> dict:
    return {
        "thesis": thesis,
        "narrative": "supporting narrative",
        "target_query": "458 PT PMA clients",
        "estimated_cost": "2 days",
        "estimated_value": "avoid auto flag",
        "recommended_tone_register": "analitico",
    }


def _returned_move() -> UltraMove:
    now = datetime.now(timezone.utc)
    return UltraMove(
        id=uuid4(),
        proposed_at=now,
        thesis="t",
        narrative="n",
        zero_decision=UltraMoveDecision.PENDING,
    )


# ── _coerce_move ──────────────────────────────────────────


def test_coerce_move_non_dict():
    assert _coerce_move("nope") is None


def test_coerce_move_missing_fields():
    assert _coerce_move({"thesis": "only"}) is None


def test_coerce_move_happy_path():
    move = _coerce_move(_valid_move())
    assert move is not None
    assert move.recommended_tone_register == "analitico"
    assert move.target_query == "458 PT PMA clients"


def test_coerce_move_preserves_source_voices():
    raw = _valid_move()
    raw["source_voices"] = ["claude", "gemini"]
    move = _coerce_move(raw)
    assert move.source_inputs == {"source_voices": ["claude", "gemini"]}


def test_coerce_move_caps_long_thesis():
    raw = _valid_move(thesis="x" * 800)
    move = _coerce_move(raw)
    assert move is not None
    assert len(move.thesis) <= 500


# ── _fallback_merge ───────────────────────────────────────


def test_fallback_merge_round_robin():
    p1 = OracleProposal(author="a", moves=[_valid_move("a1"), _valid_move("a2")])
    p2 = OracleProposal(author="b", moves=[_valid_move("b1")])
    merged = _fallback_merge([p1, p2], cap=3)
    theses = [m.thesis for m in merged]
    assert theses == ["a1", "b1", "a2"]


def test_fallback_merge_skips_invalid():
    p1 = OracleProposal(
        author="a",
        moves=[{"invalid": "shape"}, _valid_move("good")],
    )
    merged = _fallback_merge([p1], cap=3)
    assert len(merged) == 1
    assert merged[0].thesis == "good"


def test_fallback_merge_respects_cap():
    p1 = OracleProposal(
        author="a",
        moves=[_valid_move(f"m{i}") for i in range(10)],
    )
    merged = _fallback_merge([p1], cap=2)
    assert len(merged) == 2


# ── OracleCouncil round_propose ───────────────────────────


@pytest.mark.asyncio
async def test_council_empty_proponents_rejected():
    with pytest.raises(ValueError):
        OracleCouncil(proponents={}, judge=MockRunner())


@pytest.mark.asyncio
async def test_council_propose_parses_each_voice():
    proponents = {
        "claude": MockRunner(scripts=[_moves_json([_valid_move("claude-A")])]),
        "gemini": MockRunner(scripts=[_moves_json([_valid_move("gemini-A")])]),
    }
    judge = MockRunner(scripts=[_judge_json([_valid_move("final-1")])])
    council = OracleCouncil(proponents=proponents, judge=judge)

    proposals, final = await council.deliberate(context="ctx")
    assert len(proposals) == 2
    assert all(p.ok for p in proposals)
    assert final[0].thesis == "final-1"


@pytest.mark.asyncio
async def test_council_proposal_failure_isolated():
    proponents = {
        "claude": MockRunner(scripts=[_moves_json([_valid_move("c1")])]),
        "gemini": MockRunner(fail=True),
    }
    judge = MockRunner(scripts=[_judge_json([_valid_move("final-1")])])
    council = OracleCouncil(proponents=proponents, judge=judge)
    proposals, final = await council.deliberate(context="ctx")
    assert len(proposals) == 2
    ok = [p for p in proposals if p.ok]
    bad = [p for p in proposals if not p.ok]
    assert len(ok) == 1
    assert len(bad) == 1


@pytest.mark.asyncio
async def test_council_all_proposals_fail_no_judge_call():
    proponents = {
        "a": MockRunner(fail=True),
        "b": MockRunner(fail=True),
    }
    judge = MockRunner(scripts=[_judge_json([_valid_move("should-not-see")])])
    council = OracleCouncil(proponents=proponents, judge=judge)
    proposals, final = await council.deliberate(context="ctx")
    # final must be empty (judge not invoked)
    assert final == []
    assert judge.call_count == 0


@pytest.mark.asyncio
async def test_council_judge_cap_respected():
    proponents = {
        "a": MockRunner(scripts=[_moves_json([_valid_move("x")])]),
    }
    too_many = [_valid_move(f"m{i}") for i in range(10)]
    judge = MockRunner(scripts=[_judge_json(too_many)])
    council = OracleCouncil(proponents=proponents, judge=judge, max_moves=3)
    _, final = await council.deliberate(context="ctx")
    assert len(final) == 3


@pytest.mark.asyncio
async def test_council_judge_failure_falls_back_to_merge():
    proponents = {
        "a": MockRunner(scripts=[_moves_json([_valid_move("a-only")])]),
    }
    judge = MockRunner(fail=True)
    council = OracleCouncil(proponents=proponents, judge=judge, max_moves=3)
    _, final = await council.deliberate(context="ctx")
    # fallback merges proposals
    assert len(final) == 1
    assert final[0].thesis == "a-only"


@pytest.mark.asyncio
async def test_council_judge_invalid_json_falls_back():
    proponents = {
        "a": MockRunner(scripts=[_moves_json([_valid_move("m1")])]),
    }
    judge = MockRunner(scripts=["not json"])
    council = OracleCouncil(proponents=proponents, judge=judge)
    _, final = await council.deliberate(context="ctx")
    assert len(final) == 1


@pytest.mark.asyncio
async def test_council_judge_final_moves_not_list_falls_back():
    proponents = {
        "a": MockRunner(scripts=[_moves_json([_valid_move("m1")])]),
    }
    judge = MockRunner(scripts=[json.dumps({"final_moves": "bad"})])
    council = OracleCouncil(proponents=proponents, judge=judge)
    _, final = await council.deliberate(context="ctx")
    assert len(final) == 1


# ── OracleOrchestrator ───────────────────────────────────


@pytest.fixture
def cognitive_repo():
    repo = AsyncMock()
    repo.insert_ultra_move = AsyncMock(return_value=_returned_move())
    return repo


async def _fixed_context() -> str:
    return "context text"


@pytest.mark.asyncio
async def test_orchestrator_happy_path(cognitive_repo):
    proponents = {
        "a": MockRunner(scripts=[_moves_json([_valid_move("m1")])]),
    }
    judge = MockRunner(scripts=[_judge_json([_valid_move("final-1")])])
    council = OracleCouncil(proponents=proponents, judge=judge)
    orch = OracleOrchestrator(
        cognitive_repo=cognitive_repo,
        council=council,
        context_fn=_fixed_context,
    )
    result = await orch.run_once()
    assert result.context_chars == len("context text")
    assert len(result.proposals) == 1
    assert len(result.judged_moves) == 1
    assert len(result.inserted) == 1
    cognitive_repo.insert_ultra_move.assert_awaited_once()


@pytest.mark.asyncio
async def test_orchestrator_context_failure_captured(cognitive_repo):
    async def broken_ctx() -> str:
        raise RuntimeError("pg down")

    proponents = {"a": MockRunner(scripts=[_moves_json([_valid_move("m1")])])}
    judge = MockRunner(scripts=[_judge_json([_valid_move("final-1")])])
    council = OracleCouncil(proponents=proponents, judge=judge)
    orch = OracleOrchestrator(
        cognitive_repo=cognitive_repo,
        council=council,
        context_fn=broken_ctx,
    )
    result = await orch.run_once()
    assert any("context" in e for e in result.errors)
    assert len(result.inserted) == 0


@pytest.mark.asyncio
async def test_orchestrator_insert_failure_captured(cognitive_repo):
    cognitive_repo.insert_ultra_move = AsyncMock(
        side_effect=RuntimeError("pg"),
    )
    proponents = {"a": MockRunner(scripts=[_moves_json([_valid_move("m1")])])}
    judge = MockRunner(scripts=[_judge_json([_valid_move("final-1")])])
    council = OracleCouncil(proponents=proponents, judge=judge)
    orch = OracleOrchestrator(
        cognitive_repo=cognitive_repo,
        council=council,
        context_fn=_fixed_context,
    )
    result = await orch.run_once()
    assert len(result.inserted) == 0
    assert any("insert" in e for e in result.errors)


@pytest.mark.asyncio
async def test_orchestrator_degraded_when_voice_down(cognitive_repo):
    proponents = {
        "a": MockRunner(scripts=[_moves_json([_valid_move("m1")])]),
        "b": MockRunner(fail=True),
    }
    judge = MockRunner(scripts=[_judge_json([_valid_move("final-1")])])
    council = OracleCouncil(proponents=proponents, judge=judge)
    orch = OracleOrchestrator(
        cognitive_repo=cognitive_repo,
        council=council,
        context_fn=_fixed_context,
    )
    result = await orch.run_once()
    assert result.degraded is True


def test_max_moves_constant():
    assert MAX_MOVES == 3
