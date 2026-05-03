"""Tests for LayoutPatcher (Claude CLI CSS diff generator)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from backend.services.council.cli_runners import CLIRunner, RunnerResult
from backend.services.layout.layout_patcher import LayoutPatcher
from backend.services.layout.layout_qa import LayoutFlags


@dataclass
class MockRunner(CLIRunner):
    name: str = "mock-claude"
    default_timeout: int = 30
    scripted: list[str] = field(default_factory=list)
    call_count: int = 0
    fail: bool = False

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
                error="out of scripts",
            )
        return RunnerResult(
            runner_name=self.name,
            prompt_chars=len(prompt),
            ok=True,
            output=self.scripted[idx],
        )


def _flags_with_overflow() -> LayoutFlags:
    return LayoutFlags(
        text_overflow=True,
        low_contrast_regions=[],
        element_overlap=False,
        logo_visible=True,
        logo_position_ok=True,
        readability_score_0_10=5,
        ok=True,
    )


def _patch_json(css: str, rationale: str = "ok") -> str:
    return json.dumps({"css": css, "rationale": rationale})


@pytest.mark.asyncio
async def test_propose_patch_happy_path():
    runner = MockRunner(scripted=[_patch_json(
        ".headline { font-size: 42px; /* reason: overflow */ }",
        "reduced headline size",
    )])
    patcher = LayoutPatcher(runner=runner)
    patch = await patcher.propose_patch(
        html_source="<html><head><style>.headline{font-size:64px}</style></head></html>",
        flags=_flags_with_overflow(),
    )
    assert patch.ok is True
    assert "font-size: 42px" in patch.css
    assert "reduced" in patch.rationale


@pytest.mark.asyncio
async def test_propose_patch_runner_fail():
    runner = MockRunner(fail=True)
    patcher = LayoutPatcher(runner=runner)
    patch = await patcher.propose_patch(
        html_source="<html></html>",
        flags=_flags_with_overflow(),
    )
    assert patch.ok is False
    assert patch.error == "runner down"


@pytest.mark.asyncio
async def test_propose_patch_empty_css_rejected():
    runner = MockRunner(scripted=[_patch_json("", "no safe fix")])
    patcher = LayoutPatcher(runner=runner)
    patch = await patcher.propose_patch(
        html_source="<html></html>",
        flags=_flags_with_overflow(),
    )
    assert patch.ok is False
    assert "empty" in (patch.error or "").lower()
    assert patch.rationale == "no safe fix"


@pytest.mark.asyncio
async def test_propose_patch_exceeds_max_size_rejected():
    large_css = ".x { color: red; /* " + "x" * 3000 + " */ }"
    runner = MockRunner(scripted=[_patch_json(large_css, "too big")])
    patcher = LayoutPatcher(runner=runner, max_patch_chars=2000)
    patch = await patcher.propose_patch(
        html_source="<html></html>",
        flags=_flags_with_overflow(),
    )
    assert patch.ok is False
    assert "too large" in (patch.error or "")


@pytest.mark.asyncio
async def test_propose_patch_bad_json_rejected():
    runner = MockRunner(scripted=["not a json response at all"])
    patcher = LayoutPatcher(runner=runner)
    patch = await patcher.propose_patch(
        html_source="<html></html>",
        flags=_flags_with_overflow(),
    )
    assert patch.ok is False
    assert patch.raw == "not a json response at all"


@pytest.mark.asyncio
async def test_propose_patch_trims_long_html():
    """5000-char cap shouldn't crash even if html_source is massive."""
    huge_html = "<html>" + ("a" * 100_000) + "</html>"
    runner = MockRunner(scripted=[_patch_json(
        ".x { padding: 10px; }",
        "minor tweak",
    )])
    patcher = LayoutPatcher(runner=runner)
    patch = await patcher.propose_patch(
        html_source=huge_html,
        flags=_flags_with_overflow(),
    )
    assert patch.ok is True
