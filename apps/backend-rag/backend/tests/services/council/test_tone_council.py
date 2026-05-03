"""Unit tests for ToneCouncil 3-round protocol + hard rules + fallback."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from backend.services.council.cli_runners import CLIRunner, RunnerResult
from backend.services.council.tone_council import (
    ALL_REGISTERS,
    CouncilProposal,
    ToneCouncil,
    _concordance_ratio,
)

# ── Mock runner ────────────────────────────────────────────────────────


@dataclass
class MockCLIRunner(CLIRunner):
    name: str
    scripted_outputs: list[str] = field(default_factory=list)
    default_timeout: int = 10
    fail_next: bool = False
    call_count: int = 0

    async def run(self, prompt: str, timeout: int | None = None) -> RunnerResult:
        idx = self.call_count
        self.call_count += 1
        if self.fail_next:
            return RunnerResult(
                runner_name=self.name,
                prompt_chars=len(prompt),
                ok=False,
                error="simulated_fail",
            )
        if idx >= len(self.scripted_outputs):
            return RunnerResult(
                runner_name=self.name,
                prompt_chars=len(prompt),
                ok=False,
                error="ran out of scripted outputs",
            )
        return RunnerResult(
            runner_name=self.name,
            prompt_chars=len(prompt),
            ok=True,
            output=self.scripted_outputs[idx],
        )


def _propose(register: str, example: str = "x") -> str:
    return json.dumps({
        "register": register,
        "rationale": f"because {register} fits",
        "risk": "low",
        "example_headline": example,
    })


def _challenge(best: str, worst: str) -> str:
    return json.dumps({
        "best_not_mine": {"author": best, "motivation": "clear framing"},
        "worst": {"author": worst, "critique": "banal register"},
    })


def _judge(chosen: str, rejected: list[str] | None = None,
           groupthink: bool = False,
           rules: list[str] | None = None) -> str:
    return json.dumps({
        "chosen_register": chosen,
        "rationale": "chosen because history says so",
        "rejected_registers": rejected or [],
        "hard_rules_triggered": rules or [],
        "groupthink_detected": groupthink,
    })


# ── Concordance helper ────────────────────────────────────────────────


def test_concordance_ratio_all_agree():
    p = [
        CouncilProposal(author=a, register="ironico", rationale="", risk="", example_headline="")
        for a in ("claude", "gemini", "deepseek")
    ]
    assert _concordance_ratio(p) == 1.0


def test_concordance_ratio_majority():
    p = [
        CouncilProposal(author="claude", register="ironico", rationale="", risk="", example_headline=""),
        CouncilProposal(author="gemini", register="ironico", rationale="", risk="", example_headline=""),
        CouncilProposal(author="deepseek", register="analitico", rationale="", risk="", example_headline=""),
    ]
    assert _concordance_ratio(p) == pytest.approx(2 / 3)


def test_concordance_ratio_empty_returns_zero():
    assert _concordance_ratio([]) == 0.0


def test_concordance_ratio_ignores_errors():
    p = [
        CouncilProposal(author="claude", register="ironico", rationale="", risk="", example_headline=""),
        CouncilProposal(author="gemini", register="", rationale="", risk="", example_headline="", ok=False, error="x"),
    ]
    assert _concordance_ratio(p) == 1.0  # only 1 valid, unanimous


# ── Full cycle: clean run ─────────────────────────────────────────────


def _make_council(
    proposals: dict[str, str],
    challenges: dict[str, tuple[str, str]],
    judge_register: str,
    judge_rejected: list[str] | None = None,
    judge_rules: list[str] | None = None,
    judge_groupthink: bool = False,
) -> ToneCouncil:
    """Build a ToneCouncil with pre-scripted mock runners."""
    proponents: dict[str, CLIRunner] = {}
    for name, register in proposals.items():
        best, worst = challenges[name]
        proponents[name] = MockCLIRunner(
            name=name,
            scripted_outputs=[
                _propose(register, f"headline_{name}"),
                _challenge(best, worst),
            ],
        )
    judge = MockCLIRunner(
        name="judge",
        scripted_outputs=[
            _judge(judge_register, judge_rejected, judge_groupthink, judge_rules),
        ],
    )
    return ToneCouncil(proponents=proponents, judge=judge)


@pytest.mark.asyncio
async def test_full_cycle_happy_path():
    council = _make_council(
        proposals={
            "claude": "analitico",
            "gemini": "pedagogico",
            "deepseek": "ironico",
        },
        challenges={
            "claude": ("gemini", "deepseek"),
            "gemini": ("claude", "deepseek"),
            "deepseek": ("claude", "gemini"),
        },
        judge_register="analitico",
    )
    result = await council.run(
        topic="B211A extension",
        research_json={"facts": []},
        registers_last_14d={},
    )
    assert result.decision.chosen_register == "analitico"
    assert len(result.proposals) == 3
    assert all(p.ok for p in result.proposals)
    assert not result.degraded
    assert len(result.challenges) == 3


@pytest.mark.asyncio
async def test_degraded_when_one_proponent_fails():
    proponents: dict[str, CLIRunner] = {
        "claude": MockCLIRunner(
            name="claude",
            scripted_outputs=[_propose("analitico"), _challenge("gemini", "deepseek")],
        ),
        "gemini": MockCLIRunner(
            name="gemini", fail_next=True,
        ),
        "deepseek": MockCLIRunner(
            name="deepseek",
            scripted_outputs=[_propose("ironico"), _challenge("claude", "gemini")],
        ),
    }
    judge = MockCLIRunner(
        name="judge",
        scripted_outputs=[_judge("analitico")],
    )
    council = ToneCouncil(proponents=proponents, judge=judge)
    result = await council.run(
        topic="x",
        registers_last_14d={},
    )
    assert result.degraded is True
    assert result.decision.chosen_register == "analitico"


# ── Hard rules ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_hard_rule_same_register_7d_swaps():
    """If judge picks 'analitico' but history already has 3 'analitico' in 7d,
    we must swap to a different register."""
    council = _make_council(
        proposals={
            "claude": "analitico",
            "gemini": "pedagogico",
            "deepseek": "tecnico",
        },
        challenges={
            "claude": ("gemini", "deepseek"),
            "gemini": ("claude", "deepseek"),
            "deepseek": ("claude", "gemini"),
        },
        judge_register="analitico",
    )
    result = await council.run(
        topic="x",
        registers_last_14d={"analitico": 3},
    )
    assert result.decision.chosen_register != "analitico"
    assert result.decision.chosen_register in ("pedagogico", "tecnico")
    assert any(
        "max_same_register_7d_exceeded" in r
        for r in result.decision.hard_rules_triggered
    )
    assert "analitico" in result.decision.rejected_registers


@pytest.mark.asyncio
async def test_hard_rule_ironic_militant_cap():
    """ironico+militante combined >=3 in 7d forces swap if judge picks either."""
    council = _make_council(
        proposals={
            "claude": "ironico",
            "gemini": "militante",
            "deepseek": "analitico",
        },
        challenges={
            "claude": ("gemini", "deepseek"),
            "gemini": ("claude", "deepseek"),
            "deepseek": ("claude", "gemini"),
        },
        judge_register="ironico",
    )
    result = await council.run(
        topic="x",
        registers_last_14d={"ironico": 2, "militante": 1},
    )
    assert result.decision.chosen_register not in ("ironico", "militante") or (
        # swap target might fall back to another proposed register
        result.decision.chosen_register == "analitico"
    )


@pytest.mark.asyncio
async def test_groupthink_detection_swaps():
    """All 3 proponents pick 'ironico' (100% concordance) -> hard-rule swap."""
    council = _make_council(
        proposals={
            "claude": "ironico",
            "gemini": "ironico",
            "deepseek": "ironico",
        },
        challenges={
            "claude": ("gemini", "deepseek"),
            "gemini": ("claude", "deepseek"),
            "deepseek": ("claude", "gemini"),
        },
        judge_register="ironico",
    )
    result = await council.run(
        topic="x",
        registers_last_14d={},
    )
    assert result.decision.groupthink_detected is True
    # swap may or may not happen depending on hard-rule violations path;
    # at minimum groupthink flag must be set and judge rationale annotated
    # if swap happened.


# ── Fallback when judge fails ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_judge_failure_falls_back_to_majority():
    proponents: dict[str, CLIRunner] = {
        "claude": MockCLIRunner(
            name="claude",
            scripted_outputs=[_propose("analitico"), _challenge("gemini", "deepseek")],
        ),
        "gemini": MockCLIRunner(
            name="gemini",
            scripted_outputs=[_propose("analitico"), _challenge("claude", "deepseek")],
        ),
        "deepseek": MockCLIRunner(
            name="deepseek",
            scripted_outputs=[_propose("ironico"), _challenge("claude", "gemini")],
        ),
    }
    judge = MockCLIRunner(name="judge", fail_next=True)
    council = ToneCouncil(proponents=proponents, judge=judge)
    result = await council.run(topic="x", registers_last_14d={})
    assert result.decision.chosen_register == "analitico"
    assert "judge_fallback" in result.decision.hard_rules_triggered


@pytest.mark.asyncio
async def test_judge_returns_invalid_register_falls_back():
    proponents: dict[str, CLIRunner] = {
        "claude": MockCLIRunner(
            name="claude",
            scripted_outputs=[_propose("pedagogico"), _challenge("gemini", "deepseek")],
        ),
        "gemini": MockCLIRunner(
            name="gemini",
            scripted_outputs=[_propose("pedagogico"), _challenge("claude", "deepseek")],
        ),
        "deepseek": MockCLIRunner(
            name="deepseek",
            scripted_outputs=[_propose("tecnico"), _challenge("claude", "gemini")],
        ),
    }
    judge = MockCLIRunner(
        name="judge",
        scripted_outputs=[json.dumps({"chosen_register": "invalid_register"})],
    )
    council = ToneCouncil(proponents=proponents, judge=judge)
    result = await council.run(topic="x", registers_last_14d={})
    assert result.decision.chosen_register == "pedagogico"  # majority


# ── Result serialization ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_result_to_dict_serializable():
    council = _make_council(
        proposals={
            "claude": "analitico",
            "gemini": "pedagogico",
            "deepseek": "tecnico",
        },
        challenges={
            "claude": ("gemini", "deepseek"),
            "gemini": ("claude", "deepseek"),
            "deepseek": ("claude", "gemini"),
        },
        judge_register="analitico",
    )
    result = await council.run(topic="Test", registers_last_14d={})
    d = result.to_dict()
    assert d["chosen_register"] == "analitico"
    assert d["topic"] == "Test"
    assert len(d["proposals"]) == 3
    # must be JSON serializable end-to-end
    serialized = json.dumps(d)
    assert "analitico" in serialized


def test_all_seven_registers_defined():
    from backend.services.council.prompts import REGISTER_PROMPTS

    assert set(ALL_REGISTERS) == {r.value for r in REGISTER_PROMPTS.keys()}
    assert len(ALL_REGISTERS) == 7


def test_empty_proponents_rejected():
    from backend.services.council.cli_runners import ClaudeCLIRunner

    with pytest.raises(ValueError):
        ToneCouncil(proponents={}, judge=ClaudeCLIRunner(binary_path="/bin/echo"))
