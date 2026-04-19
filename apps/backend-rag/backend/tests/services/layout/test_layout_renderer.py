"""Tests for LayoutRenderer orchestrator (render → QA → patch loop)."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from backend.services.layout.layout_patcher import CSSPatch
from backend.services.layout.layout_qa import LayoutFlags
from backend.services.layout.layout_renderer import (
    LayoutRenderer,
    SlideLayoutSpec,
    _merge_patches,
)
from backend.services.layout.playwright_client import ScreenshotResult
from backend.services.layout.template_renderer import TemplateRenderer
from backend.services.layout.templates import PlatformTemplate

# ── Mock collaborators ───────────────────────────────────────────


@dataclass
class _MockPlaywright:
    shots: list[ScreenshotResult] = field(default_factory=list)
    calls: int = 0

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def screenshot(
        self,
        html: str,
        *,
        width: int,
        height: int,
    ) -> ScreenshotResult:
        idx = self.calls
        self.calls += 1
        if idx >= len(self.shots):
            return ScreenshotResult(
                ok=False,
                error="exhausted",
                width=width,
                height=height,
            )
        shot = self.shots[idx]
        shot.width = width
        shot.height = height
        return shot


@dataclass
class _MockQA:
    flags_seq: list[LayoutFlags] = field(default_factory=list)
    calls: int = 0

    async def analyze(self, png: bytes) -> LayoutFlags:
        idx = self.calls
        self.calls += 1
        if idx >= len(self.flags_seq):
            raise AssertionError("ran out of mock QA flags")
        return self.flags_seq[idx]


@dataclass
class _MockPatcher:
    patches: list[CSSPatch] = field(default_factory=list)
    calls: int = 0

    async def propose_patch(
        self,
        *,
        html_source: str,
        flags: LayoutFlags,
        screenshot_png: bytes | None = None,
    ) -> CSSPatch:
        idx = self.calls
        self.calls += 1
        if idx >= len(self.patches):
            return CSSPatch(ok=False, error="no more patches")
        return self.patches[idx]


def _good_flags() -> LayoutFlags:
    return LayoutFlags(
        text_overflow=False,
        low_contrast_regions=[],
        element_overlap=False,
        logo_visible=True,
        logo_position_ok=True,
        readability_score_0_10=9,
        ok=True,
    )


def _bad_flags() -> LayoutFlags:
    return LayoutFlags(
        text_overflow=True,
        low_contrast_regions=[],
        element_overlap=False,
        logo_visible=True,
        logo_position_ok=True,
        readability_score_0_10=4,
        ok=True,
    )


def _shot_ok(payload: bytes = b"PNG_OK") -> ScreenshotResult:
    return ScreenshotResult(ok=True, png_bytes=payload, duration_ms=50.0)


def _ig_slide_vars() -> dict[str, str]:
    return {
        "slide_num": "2 / 6",
        "headline": "Permenkumham 22/2023",
        "body": "Articolo 51 comma 3.",
        "image_url": "https://example.com/a.jpg",
    }


# ── _merge_patches helper ────────────────────────────────────────

def test_merge_patches_empty_left():
    merged = _merge_patches("", ".x {}")
    assert merged == ".x {}"


def test_merge_patches_concatenates():
    merged = _merge_patches(".a {}", ".b {}")
    assert ".a {}" in merged
    assert ".b {}" in merged
    assert "next patch" in merged


# ── First-pass success ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_render_slide_passes_first_try():
    playwright = _MockPlaywright(shots=[_shot_ok()])
    qa = _MockQA(flags_seq=[_good_flags()])
    patcher = _MockPatcher()
    renderer = LayoutRenderer(
        template_renderer=TemplateRenderer(),
        playwright=playwright,
        qa_client=qa,
        patcher=patcher,
        max_patch_iterations=3,
    )
    result = await renderer.render_slide(SlideLayoutSpec(
        slide_number=2,
        template=PlatformTemplate.IG_CAROUSEL_SLIDE,
        variables=_ig_slide_vars(),
    ))
    assert result.ok is True
    assert result.attempts == 1
    assert result.png_bytes == b"PNG_OK"
    assert result.patches_applied == []
    assert patcher.calls == 0  # never asked for a patch


# ── Retry with patch that fixes things ───────────────────────────

@pytest.mark.asyncio
async def test_render_slide_patch_fixes_overflow():
    playwright = _MockPlaywright(shots=[_shot_ok(), _shot_ok(b"PNG_AFTER_PATCH")])
    qa = _MockQA(flags_seq=[_bad_flags(), _good_flags()])
    patcher = _MockPatcher(patches=[
        CSSPatch(ok=True, css=".headline { font-size: 42px; }", rationale="shrink"),
    ])
    renderer = LayoutRenderer(
        template_renderer=TemplateRenderer(),
        playwright=playwright,
        qa_client=qa,
        patcher=patcher,
        max_patch_iterations=3,
    )
    result = await renderer.render_slide(SlideLayoutSpec(
        slide_number=2,
        template=PlatformTemplate.IG_CAROUSEL_SLIDE,
        variables=_ig_slide_vars(),
    ))
    assert result.ok is True
    assert result.attempts == 2
    assert result.png_bytes == b"PNG_AFTER_PATCH"
    assert len(result.patches_applied) == 1
    assert "font-size: 42px" in result.final_html


# ── Max retries exhausted ────────────────────────────────────────

@pytest.mark.asyncio
async def test_max_iterations_exhausted_escalates():
    playwright = _MockPlaywright(shots=[_shot_ok(), _shot_ok(), _shot_ok()])
    qa = _MockQA(flags_seq=[_bad_flags(), _bad_flags(), _bad_flags()])
    patcher = _MockPatcher(patches=[
        CSSPatch(ok=True, css=".x { padding: 10px; }", rationale="a"),
        CSSPatch(ok=True, css=".x { padding: 20px; }", rationale="b"),
    ])
    renderer = LayoutRenderer(
        template_renderer=TemplateRenderer(),
        playwright=playwright,
        qa_client=qa,
        patcher=patcher,
        max_patch_iterations=3,
    )
    result = await renderer.render_slide(SlideLayoutSpec(
        slide_number=2,
        template=PlatformTemplate.IG_CAROUSEL_SLIDE,
        variables=_ig_slide_vars(),
    ))
    assert result.ok is False
    assert result.needs_escalation is True
    assert result.attempts == 3


# ── Patcher fails early ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_patcher_failure_aborts_loop_early():
    playwright = _MockPlaywright(shots=[_shot_ok()])
    qa = _MockQA(flags_seq=[_bad_flags()])
    patcher = _MockPatcher(patches=[CSSPatch(ok=False, error="no safe fix")])
    renderer = LayoutRenderer(
        template_renderer=TemplateRenderer(),
        playwright=playwright,
        qa_client=qa,
        patcher=patcher,
        max_patch_iterations=3,
    )
    result = await renderer.render_slide(SlideLayoutSpec(
        slide_number=2,
        template=PlatformTemplate.IG_CAROUSEL_SLIDE,
        variables=_ig_slide_vars(),
    ))
    assert result.ok is False
    assert result.needs_escalation is True
    # only one attempt before aborting
    assert result.attempts == 1
    assert patcher.calls == 1


# ── Screenshot failure ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_screenshot_failure_escalates():
    playwright = _MockPlaywright(shots=[
        ScreenshotResult(ok=False, error="browser crashed"),
    ])
    qa = _MockQA(flags_seq=[])
    patcher = _MockPatcher()
    renderer = LayoutRenderer(
        template_renderer=TemplateRenderer(),
        playwright=playwright,
        qa_client=qa,
        patcher=patcher,
    )
    result = await renderer.render_slide(SlideLayoutSpec(
        slide_number=2,
        template=PlatformTemplate.IG_CAROUSEL_SLIDE,
        variables=_ig_slide_vars(),
    ))
    assert result.ok is False
    assert "screenshot failed" in (result.error or "")
    assert result.needs_escalation is True


# ── Template validation failure ──────────────────────────────────

@pytest.mark.asyncio
async def test_template_validation_error_surfaces():
    playwright = _MockPlaywright(shots=[])
    qa = _MockQA(flags_seq=[])
    patcher = _MockPatcher()
    renderer = LayoutRenderer(
        template_renderer=TemplateRenderer(),
        playwright=playwright,
        qa_client=qa,
        patcher=patcher,
    )
    # missing image_url + body
    bad_spec = SlideLayoutSpec(
        slide_number=2,
        template=PlatformTemplate.IG_CAROUSEL_SLIDE,
        variables={"slide_num": "1", "headline": "h"},
    )
    result = await renderer.render_slide(bad_spec)
    assert result.ok is False
    assert "template validation" in (result.error or "")
    assert result.needs_escalation is True


# ── QA offline → treat as pass (Law 4 graceful) ──────────────────

@pytest.mark.asyncio
async def test_qa_offline_passes_through():
    playwright = _MockPlaywright(shots=[_shot_ok()])
    qa_offline = LayoutFlags(
        text_overflow=False,
        low_contrast_regions=[],
        element_overlap=False,
        logo_visible=True,
        logo_position_ok=True,
        readability_score_0_10=0,
        ok=False,
        error="ollama unreachable",
    )
    qa = _MockQA(flags_seq=[qa_offline])
    patcher = _MockPatcher()
    renderer = LayoutRenderer(
        template_renderer=TemplateRenderer(),
        playwright=playwright,
        qa_client=qa,
        patcher=patcher,
    )
    result = await renderer.render_slide(SlideLayoutSpec(
        slide_number=2,
        template=PlatformTemplate.IG_CAROUSEL_SLIDE,
        variables=_ig_slide_vars(),
    ))
    assert result.ok is True
    assert result.png_bytes == b"PNG_OK"
    # Pipeline proceeded despite QA being offline


# ── Carousel batch ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_carousel_renders_all_slides():
    playwright = _MockPlaywright(shots=[_shot_ok(), _shot_ok(), _shot_ok()])
    qa = _MockQA(flags_seq=[_good_flags(), _good_flags(), _good_flags()])
    patcher = _MockPatcher()
    renderer = LayoutRenderer(
        template_renderer=TemplateRenderer(),
        playwright=playwright,
        qa_client=qa,
        patcher=patcher,
    )
    slides = [
        SlideLayoutSpec(
            slide_number=i,
            template=PlatformTemplate.IG_CAROUSEL_SLIDE,
            variables={
                "slide_num": str(i),
                "headline": f"h{i}",
                "body": f"b{i}",
                "image_url": f"https://x/{i}.jpg",
            },
        )
        for i in (2, 3, 4)
    ]
    results = await renderer.render_carousel(slides)
    assert len(results) == 3
    assert all(r.ok for r in results)
