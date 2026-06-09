"""E2E proof of the designer loop on a REAL slide + REAL hero (run on Pro).

Renders a cover slide, runs the full cheap→expensive critique/iterate loop with
the Claude-vision critic + brand verifier, and prints the iteration history +
the before/after PNG paths so we can SEE whether the levers improved the slide.

Usage (on Pro, where playwright lives):
    PYTHONPATH=<wt>/scripts <wt>/apps/backend-rag/.venv/bin/python \
        -m wr2_html_renderer._designer_e2e <hero.jpg> [out_dir]

It does NOT touch any DB or the live pipeline. Brand assets only (not PII).
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
from pathlib import Path

from .composer import make_slide_render_fn
from .designer_loop import run_designer_loop
from .renderer import _stage_assets


# A real cover slide in the composer's schema (the KITAP cover content).
COVER_SLIDE = {
    "index": 1,
    "slide_type": "cover",
    "is_cover": True,
    "is_hero_image": True,
    "headline": "YOUR KITAP IS VALID. 3 RULES CHANGED.",
    "subhead": "PERMENKUMHAM 22/2023 + 11/2024",
    "body": "Your existing KITAP stays fully valid until its natural expiry — "
            "but at your next perpanjangan, three things now work differently.",
    "regulation_code": "Permenkumham 22/2023 + 11/2024",
}


async def _amain(hero_src: Path, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    slides_dir = out_dir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)

    # stage brand assets (fonts/logo/_base.css) into BOTH the root and slides dir
    _stage_assets(out_dir)
    _stage_assets(slides_dir)

    # place the real hero where make_slide_render_fn expects it
    hero_filename = "slide-01-hero.jpg"
    shutil.copy2(hero_src, slides_dir / hero_filename)

    # the Claude-vision adapters (the "human eye"); import here so the cheap
    # tiers can be tested even if the CLI is unavailable.
    from .claude_vision import claude_brand_verifier, claude_design_critic

    render_fn = make_slide_render_fn(
        slides_dir=slides_dir,
        index=1,
        total=9,
        hero_filename=hero_filename,
        timeout_ms=45000,
    )

    result = await run_designer_loop(
        slide=COVER_SLIDE,
        render_fn=render_fn,
        out_dir=out_dir / "iters",
        is_hero=True,
        hero_path=slides_dir / hero_filename,
        vision_critic=claude_design_critic,
        brand_verifier=claude_brand_verifier,
        max_iters=3,
        use_vision=True,
    )

    print("\n" + "=" * 70)
    print("DESIGNER LOOP RESULT")
    print("=" * 70)
    print(f"converged      : {result.converged}")
    print(f"iterations     : {result.iterations}")
    print(f"escalated      : {result.escalated}")
    print(f"final_png      : {result.final_png}")
    print(f"reason         : {result.reason}")
    print("\n--- iteration history ---")
    print(json.dumps(result.history, indent=2, ensure_ascii=False))

    if result.final_png and Path(result.final_png).is_file():
        print(f"\nFINAL PNG: {result.final_png} "
              f"({Path(result.final_png).stat().st_size // 1024}KB)")
        return 0
    print("\nNO FINAL PNG PRODUCED")
    return 1


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    hero_src = Path(sys.argv[1])
    if not hero_src.is_file():
        print(f"hero not found: {hero_src}")
        return 2
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/tmp/wr2-designer-e2e")
    return asyncio.run(_amain(hero_src, out_dir))


if __name__ == "__main__":
    raise SystemExit(main())
