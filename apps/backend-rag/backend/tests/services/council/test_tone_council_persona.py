"""ToneCouncil v2 — schema widening to carry persona_slug through.

Backward-compat test: existing callers that do not pass persona_slug must
keep working. New WR2 callers can pass persona_slug to tag the decision.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from backend.services.council.cli_runners import CLIRunner, RunnerResult
from backend.services.council.tone_council import ToneCouncil, ToneCouncilResult


@dataclass
class _MockRunner(CLIRunner):
    name: str
    scripted_outputs: list[str] = field(default_factory=list)
    default_timeout: int = 10
    call_count: int = 0

    async def run(self, prompt: str, timeout: int | None = None) -> RunnerResult:
        idx = self.call_count
        self.call_count += 1
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


def _propose(register: str) -> str:
    return json.dumps({
        "register": register,
        "rationale": f"because {register} fits",
        "risk": "low",
        "example_headline": "x",
    })


def _challenge(best: str, worst: str) -> str:
    return json.dumps({
        "best_not_mine": {"author": best, "motivation": "good fit"},
        "worst": {"author": worst, "critique": "off tone"},
    })


def _judge(register: str) -> str:
    return json.dumps({
        "chosen_register": register,
        "rationale": "judge says so",
        "rejected_registers": [],
        "hard_rules_triggered": [],
        "groupthink_detected": False,
    })


def _make_council() -> ToneCouncil:
    """Minimal 2-proponent council wired with scripted outputs for r0/r1/r2."""
    p_claude = _MockRunner(
        name="claude",
        scripted_outputs=[_propose("analitico"), _challenge("gemini", "gemini")],
    )
    p_gemini = _MockRunner(
        name="gemini",
        scripted_outputs=[_propose("pedagogico"), _challenge("claude", "claude")],
    )
    judge = _MockRunner(name="judge", scripted_outputs=[_judge("analitico")])
    return ToneCouncil(
        proponents={"claude": p_claude, "gemini": p_gemini},
        judge=judge,
    )


@pytest.mark.asyncio
async def test_run_accepts_persona_slug_and_tags_result():
    """WR2 passes persona_slug — result carries it through for audit."""
    council = _make_council()
    result = await council.run(
        topic="KITAS family route",
        research_json="{}",
        persona_slug="id_konsultan_kadin",
    )
    assert isinstance(result, ToneCouncilResult)
    assert result.persona_slug == "id_konsultan_kadin"
    assert result.decision.chosen_register == "analitico"


@pytest.mark.asyncio
async def test_run_without_persona_slug_defaults_to_none():
    """Existing callers that don't know about persona_slug keep working."""
    council = _make_council()
    result = await council.run(
        topic="KITAS family route",
        research_json="{}",
    )
    assert result.persona_slug is None
    assert result.decision.chosen_register == "analitico"


@pytest.mark.asyncio
async def test_to_dict_includes_persona_slug_when_set():
    """Serialization must expose persona_slug so downstream audit/DB sees it."""
    council = _make_council()
    result = await council.run(
        topic="KITAS family route",
        research_json="{}",
        persona_slug="expat_techie_pma",
    )
    d = result.to_dict()
    assert d["persona_slug"] == "expat_techie_pma"
