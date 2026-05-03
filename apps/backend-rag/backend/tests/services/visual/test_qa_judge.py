"""Unit tests for QAJudge dual-voice (vision flags + Claude Haiku CLI)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from backend.services.council.cli_runners import CLIRunner, RunnerResult
from backend.services.visual.qa_judge import (
    QAJudge,
    QAVerdict,
)
from backend.services.visual.vision_qa import VisionFlags


@dataclass
class MockRunner(CLIRunner):
    name: str = "mock"
    default_timeout: int = 30
    scripted: list[str] = field(default_factory=list)
    fail: bool = False
    call_count: int = 0

    async def run(
        self, prompt: str, timeout: int | None = None,
    ) -> RunnerResult:
        idx = self.call_count
        self.call_count += 1
        if self.fail:
            return RunnerResult(
                runner_name=self.name,
                prompt_chars=len(prompt),
                ok=False,
                error="runner down",
            )
        if idx >= len(self.scripted):
            return RunnerResult(
                runner_name=self.name,
                prompt_chars=len(prompt),
                ok=False,
                error="no more scripts",
            )
        return RunnerResult(
            runner_name=self.name,
            prompt_chars=len(prompt),
            ok=True,
            output=self.scripted[idx],
        )


def _good_flags() -> VisionFlags:
    return VisionFlags(
        matches_brief=True,
        has_banned_elements=[],
        brand_fit_score_0_10=9,
        text_area_available_ratio=0.6,
        readability_issues=[],
        ok=True,
    )


def _bad_flags(reason: str = "banned") -> VisionFlags:
    if reason == "banned":
        return VisionFlags(
            matches_brief=True,
            has_banned_elements=["mani_deformi"],
            brand_fit_score_0_10=7,
            text_area_available_ratio=0.5,
            readability_issues=[],
            ok=True,
        )
    if reason == "low_fit":
        return VisionFlags(
            matches_brief=True,
            has_banned_elements=[],
            brand_fit_score_0_10=3,
            text_area_available_ratio=0.6,
            readability_issues=[],
            ok=True,
        )
    return VisionFlags(
        matches_brief=False,
        has_banned_elements=[],
        brand_fit_score_0_10=0,
        text_area_available_ratio=0.0,
        readability_issues=[],
        ok=False,
        error="vision offline",
    )


def _judge_json(
    verdict: str,
    *,
    rationale: str = "ok",
    suggested: str | None = None,
) -> str:
    return json.dumps({
        "verdict": verdict,
        "rationale": rationale,
        "suggested_prompt_fix": suggested,
    })


# ── Happy paths ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_judge_pass_when_all_green():
    runner = MockRunner(scripted=[_judge_json("pass", rationale="looks great")])
    judge = QAJudge(judge_runner=runner)
    decision = await judge.judge(prompt="p", flags=_good_flags())
    assert decision.verdict == QAVerdict.PASS
    assert decision.fallback_used is False
    assert decision.flags is not None


@pytest.mark.asyncio
async def test_judge_retry_with_suggested_fix():
    runner = MockRunner(
        scripted=[
            _judge_json(
                "retry_with_modified_prompt",
                rationale="banned hands",
                suggested="scene without hands",
            )
        ],
    )
    judge = QAJudge(judge_runner=runner)
    decision = await judge.judge(prompt="p with hands", flags=_bad_flags("banned"))
    assert decision.verdict == QAVerdict.RETRY
    assert decision.suggested_prompt_fix == "scene without hands"


@pytest.mark.asyncio
async def test_judge_hard_reject():
    runner = MockRunner(scripted=[_judge_json("hard_reject", rationale="brand violation")])
    judge = QAJudge(judge_runner=runner)
    decision = await judge.judge(prompt="p", flags=_bad_flags("banned"))
    assert decision.verdict == QAVerdict.REJECT


# ── Fallbacks ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_judge_fallback_retry_on_bad_flags_when_runner_fails():
    runner = MockRunner(fail=True)
    judge = QAJudge(judge_runner=runner)
    decision = await judge.judge(prompt="p", flags=_bad_flags("low_fit"))
    assert decision.verdict == QAVerdict.RETRY
    assert decision.fallback_used is True
    assert "deterministic" in decision.rationale


@pytest.mark.asyncio
async def test_judge_fallback_pass_when_flags_green_runner_fails():
    runner = MockRunner(fail=True)
    judge = QAJudge(judge_runner=runner)
    decision = await judge.judge(prompt="p", flags=_good_flags())
    assert decision.verdict == QAVerdict.PASS
    assert decision.fallback_used is True


@pytest.mark.asyncio
async def test_judge_retries_when_vision_itself_failed():
    runner = MockRunner(scripted=[_judge_json("pass")])
    judge = QAJudge(judge_runner=runner)
    decision = await judge.judge(prompt="p", flags=_bad_flags("vision_offline"))
    assert decision.verdict == QAVerdict.RETRY
    assert decision.fallback_used is True
    assert "vision qa unavailable" in decision.rationale


@pytest.mark.asyncio
async def test_judge_invalid_verdict_falls_back():
    runner = MockRunner(
        scripted=[json.dumps({"verdict": "maybe", "rationale": "..."})],
    )
    judge = QAJudge(judge_runner=runner)
    decision = await judge.judge(prompt="p", flags=_good_flags())
    # Invalid verdict → fallback deterministic: green flags → PASS
    assert decision.verdict == QAVerdict.PASS
    assert decision.fallback_used is True


@pytest.mark.asyncio
async def test_judge_none_suggested_fix_stays_none():
    runner = MockRunner(
        scripted=[_judge_json("pass", rationale="ok", suggested=None)],
    )
    judge = QAJudge(judge_runner=runner)
    decision = await judge.judge(prompt="p", flags=_good_flags())
    assert decision.suggested_prompt_fix is None
