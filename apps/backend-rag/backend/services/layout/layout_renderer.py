"""LayoutRenderer — orchestrates template → screenshot → QA → patch loop.

Design §5 retry policy:
    - render → screenshot → QA
    - if flags.requires_patch: ask LayoutPatcher for CSS
    - re-render with accumulated patch, re-screenshot, re-QA
    - max 3 iterations per slide
    - if still failing: escalation flag + partial delivery (Law 4)

Cost tracking: layout passes itself don't hit paid APIs — only the patcher
uses Claude CLI (OAuth, flat-rate). No cost_repo integration needed here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from backend.services.layout.layout_patcher import CSSPatch, LayoutPatcher
from backend.services.layout.layout_qa import LayoutFlags, LayoutQAClient
from backend.services.layout.playwright_client import (
    PlaywrightClient,
    ScreenshotResult,
)
from backend.services.layout.template_renderer import (
    RenderOutput,
    TemplateRenderer,
    TemplateValidationError,
)
from backend.services.layout.templates import PlatformTemplate

logger = logging.getLogger(__name__)


@dataclass
class SlideLayoutSpec:
    slide_number: int
    template: PlatformTemplate
    variables: dict[str, str]


@dataclass
class LayoutResult:
    slide_number: int
    ok: bool
    template: PlatformTemplate
    png_bytes: bytes | None = None
    final_html: str = ""
    patches_applied: list[str] = field(default_factory=list)
    attempts: int = 0
    final_flags: LayoutFlags | None = None
    needs_escalation: bool = False
    error: str | None = None
    width: int = 0
    height: int = 0


class LayoutRenderer:
    """Render → QA → Patch loop per slide (max 3 iterations)."""

    def __init__(
        self,
        template_renderer: TemplateRenderer,
        playwright: PlaywrightClient,
        qa_client: LayoutQAClient,
        patcher: LayoutPatcher,
        *,
        max_patch_iterations: int = 3,
    ) -> None:
        self.templates = template_renderer
        self.playwright = playwright
        self.qa = qa_client
        self.patcher = patcher
        self.max_patch_iterations = max_patch_iterations

    async def render_carousel(
        self,
        slides: list[SlideLayoutSpec],
    ) -> list[LayoutResult]:
        """Render a list of slides; returns per-slide results.

        Browser lifecycle: caller is responsible for ``playwright.start()`` /
        ``stop()`` when batching. This method assumes the browser is already
        running.
        """
        results: list[LayoutResult] = []
        for spec in slides:
            results.append(await self.render_slide(spec))
        return results

    async def render_slide(
        self,
        spec: SlideLayoutSpec,
    ) -> LayoutResult:
        accumulated_patch = ""
        last_flags: LayoutFlags | None = None
        last_shot: ScreenshotResult | None = None
        last_render: RenderOutput | None = None
        patches_applied: list[str] = []
        attempts_done = 0

        for attempt in range(1, self.max_patch_iterations + 1):
            try:
                render_out = self.templates.render(
                    spec.template,
                    spec.variables,
                    patch_css=accumulated_patch,
                )
            except TemplateValidationError as exc:
                return LayoutResult(
                    slide_number=spec.slide_number,
                    ok=False,
                    template=spec.template,
                    error=f"template validation failed: {exc}",
                    attempts=attempt - 1,
                    needs_escalation=True,
                )

            last_render = render_out
            attempts_done = attempt

            shot = await self.playwright.screenshot(
                render_out.html,
                width=render_out.width,
                height=render_out.height,
            )
            last_shot = shot
            if not shot.ok or shot.png_bytes is None:
                return LayoutResult(
                    slide_number=spec.slide_number,
                    ok=False,
                    template=spec.template,
                    final_html=render_out.html,
                    attempts=attempt,
                    patches_applied=patches_applied,
                    error=f"screenshot failed: {shot.error}",
                    needs_escalation=True,
                    width=render_out.width,
                    height=render_out.height,
                )

            flags = await self.qa.analyze(shot.png_bytes)
            last_flags = flags

            if not flags.ok:
                logger.info(
                    "layout qa unavailable on slide %s attempt %s: %s",
                    spec.slide_number,
                    attempt,
                    flags.error,
                )
                # treat as pass — we must not hold up pipeline on QA outage
                return LayoutResult(
                    slide_number=spec.slide_number,
                    ok=True,
                    template=spec.template,
                    png_bytes=shot.png_bytes,
                    final_html=render_out.html,
                    patches_applied=patches_applied,
                    attempts=attempt,
                    final_flags=flags,
                    width=render_out.width,
                    height=render_out.height,
                )

            if not flags.requires_patch:
                return LayoutResult(
                    slide_number=spec.slide_number,
                    ok=True,
                    template=spec.template,
                    png_bytes=shot.png_bytes,
                    final_html=render_out.html,
                    patches_applied=patches_applied,
                    attempts=attempt,
                    final_flags=flags,
                    width=render_out.width,
                    height=render_out.height,
                )

            # QA rejected — try to get a patch from Claude
            if attempt == self.max_patch_iterations:
                # last iteration already used for render; don't patch further
                break

            patch: CSSPatch = await self.patcher.propose_patch(
                html_source=render_out.html,
                flags=flags,
                screenshot_png=shot.png_bytes,
            )
            if not patch.ok:
                logger.info(
                    "layout patch unavailable on slide %s attempt %s: %s",
                    spec.slide_number,
                    attempt,
                    patch.error,
                )
                break

            accumulated_patch = _merge_patches(accumulated_patch, patch.css)
            patches_applied.append(patch.css)

        # Exhausted retries (or patcher bailed early); best-effort + escalation.
        final_ok = last_flags is not None and not last_flags.requires_patch
        return LayoutResult(
            slide_number=spec.slide_number,
            ok=final_ok,
            template=spec.template,
            png_bytes=last_shot.png_bytes if last_shot else None,
            final_html=last_render.html if last_render else "",
            patches_applied=patches_applied,
            attempts=attempts_done,
            final_flags=last_flags,
            needs_escalation=not final_ok,
            width=last_render.width if last_render else 0,
            height=last_render.height if last_render else 0,
        )


def _merge_patches(existing: str, new_patch: str) -> str:
    """Concatenate CSS patches. Preserves order (later overrides earlier).

    No dedup — CSS cascade handles overrides naturally and we want to keep
    an auditable history inside the rendered HTML.
    """
    if not existing:
        return new_patch
    return f"{existing}\n/* --- next patch --- */\n{new_patch}"
