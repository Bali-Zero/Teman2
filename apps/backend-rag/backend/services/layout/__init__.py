"""Layout — HTML/CSS rendering + Playwright screenshot + QA + CSS patch loop.

Reference: docs/war-room-2.0-design.md §5.

Modules:
- templates: HTML string templates per platform (IG carousel, X thread image,
  LinkedIn post, newsletter)
- template_renderer: variable substitution + validation
- playwright_client: async Chromium headless screenshot
- layout_qa: qwen2.5vl flags specifically for layout (overflow, contrast, logo)
- layout_patcher: Claude CLI generates CSS-only diff patch
- layout_renderer: orchestrator with retry loop max 3
"""

from backend.services.layout.layout_patcher import (
    CSSPatch,
    LayoutPatcher,
)
from backend.services.layout.layout_qa import (
    LayoutFlags,
    LayoutQAClient,
)
from backend.services.layout.layout_renderer import (
    LayoutRenderer,
    LayoutResult,
    SlideLayoutSpec,
)
from backend.services.layout.playwright_client import (
    PlaywrightClient,
    ScreenshotError,
    ScreenshotResult,
)
from backend.services.layout.template_renderer import (
    TemplateRenderer,
    TemplateValidationError,
)
from backend.services.layout.templates import (
    PlatformTemplate,
    get_template,
    list_templates,
)

__all__ = [
    "CSSPatch",
    "LayoutFlags",
    "LayoutPatcher",
    "LayoutQAClient",
    "LayoutRenderer",
    "LayoutResult",
    "PlatformTemplate",
    "PlaywrightClient",
    "ScreenshotError",
    "ScreenshotResult",
    "SlideLayoutSpec",
    "TemplateRenderer",
    "TemplateValidationError",
    "get_template",
    "list_templates",
]
