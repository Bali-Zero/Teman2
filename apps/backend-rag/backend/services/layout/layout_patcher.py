"""Claude CLI generates targeted CSS patch (no full rewrite).

Input:
- screenshot PNG (b64)
- rendered HTML source
- LayoutFlags JSON
- brand constraints (colors, fonts)

Output: :class:`CSSPatch` with a small CSS snippet appended to the existing
style block. The patch is appended via the ``$patch_css`` slot in each
template (see :mod:`backend.services.layout.templates`).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass

from backend.services.council.cli_runners import CLIRunner
from backend.services.layout.layout_qa import LayoutFlags
from backend.services.layout.templates import (
    BRAND_BG,
    BRAND_TEXT_ACCENT,
    BRAND_TEXT_PRIMARY,
)

logger = logging.getLogger(__name__)


@dataclass
class CSSPatch:
    ok: bool
    css: str = ""
    rationale: str = ""
    duration_ms: float = 0.0
    error: str | None = None
    raw: str = ""


_PATCH_PROMPT_TEMPLATE = """Sei un CSS editor. Ti mostro uno screenshot di un
layout che ha problemi, insieme al sorgente HTML completo. Devi produrre
UN PATCH CSS — non una riscrittura.

Regole inviolabili:
- Non cambiare la palette: background {bg}, testo {text}, accent {accent}.
- Non cambiare dimensioni canvas.
- Modifica SOLO: font-size, padding, line-height, max-width, position, z-index.
- Usa selettori piu' specifici del template per vincere (.container .headline etc).
- Commenta ogni regola con /* reason: ... */.

Problemi rilevati (flags QA):
{flags_json}

HTML sorgente:
{html}

Rispondi SOLO JSON:

{{
  "css": "/* patch */ .container .headline {{ font-size: 48px; /* reason: overflow */ }} ...",
  "rationale": "1-2 righe, cosa hai cambiato e perche'"
}}

Se non sai come risolvere, rispondi {{"css": "", "rationale": "no safe fix"}}."""


class LayoutPatcher:
    """Uses a Claude CLI runner to produce a targeted CSS patch."""

    def __init__(
        self,
        runner: CLIRunner,
        *,
        max_patch_chars: int = 2000,
        timeout: int = 60,
    ) -> None:
        self.runner = runner
        self.max_patch_chars = max_patch_chars
        self.timeout = timeout

    async def propose_patch(
        self,
        *,
        html_source: str,
        flags: LayoutFlags,
        screenshot_png: bytes | None = None,
    ) -> CSSPatch:
        start = time.perf_counter()

        # keep the prompt compact: Claude CLI Opus can handle large HTML but
        # we cap to prevent CLI argv overflow and latency
        trimmed_html = html_source[:5000]
        flags_payload = json.dumps(
            {
                "text_overflow": flags.text_overflow,
                "low_contrast_regions": flags.low_contrast_regions,
                "element_overlap": flags.element_overlap,
                "logo_visible": flags.logo_visible,
                "logo_position_ok": flags.logo_position_ok,
                "readability_score_0_10": flags.readability_score_0_10,
            },
            ensure_ascii=False,
        )

        prompt = _PATCH_PROMPT_TEMPLATE.format(
            bg=BRAND_BG,
            text=BRAND_TEXT_PRIMARY,
            accent=BRAND_TEXT_ACCENT,
            flags_json=flags_payload,
            html=trimmed_html,
        )
        # Screenshot byte payload is not included inline (CLI argv size); the
        # model works from HTML + flags. If needed, a future revision can use
        # a vision-capable CLI runner.

        parsed, result = await self.runner.run_json(prompt, timeout=self.timeout)
        duration_ms = (time.perf_counter() - start) * 1000

        if not result.ok or parsed is None:
            return CSSPatch(
                ok=False,
                duration_ms=duration_ms,
                error=result.error or "no parseable JSON patch",
                raw=result.output,
            )

        css = str(parsed.get("css") or "").strip()
        rationale = str(parsed.get("rationale") or "").strip()

        if len(css) > self.max_patch_chars:
            return CSSPatch(
                ok=False,
                css=css[: self.max_patch_chars],
                rationale=rationale,
                duration_ms=duration_ms,
                error=f"patch too large ({len(css)} chars > {self.max_patch_chars})",
                raw=result.output,
            )
        if not css:
            return CSSPatch(
                ok=False,
                rationale=rationale or "model returned empty css",
                duration_ms=duration_ms,
                error="empty css patch",
                raw=result.output,
            )

        return CSSPatch(
            ok=True,
            css=css,
            rationale=rationale,
            duration_ms=duration_ms,
            raw=result.output,
        )
