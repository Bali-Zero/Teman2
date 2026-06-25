#!/usr/bin/env python3
"""wr2_rerender_local — re-render a carousel's PNGs from its on-disk slides.json.

WHY THIS EXISTS (2026-06-25)
----------------------------
The app's "Migliora" button drives the full `wr2-design-architect` agent: it
re-storyboards, re-composes, re-renders, re-critiques — ~15-20 min, because the
agent has to REASON about the feedback. But when the slides.json is ALREADY in
the desired shape (e.g. an operator/agent edited the copy directly), there is no
reasoning to do — only re-rendering. This tool does exactly that: it replays the
SAME render+designer-loop the production render path uses (`_render_carousel` in
wr2_html_render_apply.py), but fed from `output/carousel/<slug>/slides.json`
instead of the DB. ~2-3 min, no DB write, no Drive upload — just fresh PNGs +
critic verdicts on disk.

It REUSES the production renderer verbatim (compose_carousel / run_designer_loop /
claude_design_critic) — no new rendering logic, so the output is identical to what
the pipeline would produce. The only deltas vs `_render_carousel`:
  - slides come from slides.json on disk (not war_room_drafts.slides_json)
  - heroes come from the slide's local `hero_image_path` (not an image_url download)
  - output lands in the carousel dir's slides/ (not a tmp work dir + Drive upload)

USAGE
    PYTHONPATH=scripts python -m wr2_rerender_local <slug> [--no-vision]
    # <slug> = a dir name under apps/war-room/output/carousel/

EXIT 0 = all slides rendered + converged. EXIT 1 = a slide failed its gate
(the critic verdict is printed so you see WHY, same as the production path).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("wr2.rerender")

# Carousel output root (M5 app machine path; overridable for the Pro/Mini).
_CAROUSEL_ROOT = Path(
    os.environ.get(
        "WR2_CAROUSEL_ROOT",
        str(Path.home() / "Desktop/nuzantara/apps/war-room/output/carousel"),
    )
)


def _load_slides(carousel_dir: Path) -> list[dict[str, Any]]:
    sj = carousel_dir / "slides.json"
    if not sj.is_file():
        raise FileNotFoundError(f"no slides.json at {sj}")
    data = json.loads(sj.read_text(encoding="utf-8"))
    slides = data.get("slides") if isinstance(data, dict) else data
    if not slides:
        raise ValueError(f"slides.json has no slides: {sj}")
    return slides


async def rerender(slug: str, *, use_vision: bool = True) -> int:
    """Re-render <slug> from its slides.json. Returns process exit code."""
    carousel_dir = _CAROUSEL_ROOT / slug
    if not carousel_dir.is_dir():
        logger.error("carousel dir not found: %s", carousel_dir)
        return 1

    slides = _load_slides(carousel_dir)
    out_dir = carousel_dir  # render in place; slides/ is the canonical PNG slot
    slides_dir = out_dir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)

    from wr2_html_renderer.composer import _stage_assets, make_slide_render_fn

    _stage_assets(out_dir)
    _stage_assets(slides_dir)

    if not use_vision:
        # Fast path (DEFAULT): bulk straight render, anti-Canva hero gate, NO critic
        # loop. The vision critic is an LLM on screenshots — stochastic AND slow, so
        # the same slides.json can converge on one run and fail the next (verified
        # 2026-06-25). For a re-render of already-shaped copy we want determinism, so
        # we skip it. Use --vision only when a fresh editorial judgement is wanted.
        #
        # compose_carousel locates each hero via the slide's `image_url`, which its
        # httpx downloader GETs (httpx rejects file://). Our slides carry only a local
        # `hero_image_path`. So we reuse the PRODUCTION _HeroServer + _normalize_heroes
        # (wr2_html_render_apply) — they serve the local files on 127.0.0.1 and rewrite
        # image_url to that localhost URL, exactly as the live render path does.
        from wr2_html_renderer.composer import compose_carousel
        from wr2_html_render_apply import _HeroServer, _normalize_heroes

        # _normalize_heroes resolves hero_image_path via Path(local) — i.e. CWD-
        # relative. In the live pipeline that path is absolute; in an on-disk
        # slides.json it is relative to the carousel dir (e.g. "slides/1-hero.jpg").
        # Resolve each to an ABSOLUTE path up front so _normalize_heroes finds it
        # regardless of CWD, without touching the production helper.
        resolved = []
        for slide in slides:
            s = dict(slide)
            hp = (s.get("hero_image_path") or "").strip()
            if hp and not Path(hp).is_absolute():
                s["hero_image_path"] = str((carousel_dir / hp).resolve())
            resolved.append(s)

        # The server MUST serve from the same dir _normalize_heroes copies INTO
        # (its `hero_dir` arg): it writes hero-NN.jpg there and rewrites image_url
        # to server.url_for("hero-NN.jpg"), so the server root must be that dir.
        with _HeroServer(slides_dir) as server:
            staged = _normalize_heroes(resolved, slides_dir, server)
            result = await compose_carousel(staged, out_dir, topic="", timeout_ms=30000)
        if not result.ok:
            logger.error(
                "render gate failed: slides=%s heroes=%s/%s failures=%s",
                result.slides_rendered, result.heroes_placed,
                result.heroes_expected, result.failures,
            )
            return 1
        logger.info("re-render OK (fast, no-vision): %s slides → %s", len(slides), slides_dir)
        return 0

    # Vision path: per-slide designer loop (render → critic → adjust → re-render).
    from wr2_html_renderer.claude_vision import claude_design_critic
    from wr2_html_renderer.designer_loop import run_designer_loop

    total = len(slides)
    done = 0
    for i, slide in enumerate(slides, start=1):
        is_hero = bool(slide.get("is_hero_image")) or i == 1
        # Local hero: the slide carries hero_image_path relative to the carousel dir.
        hero_filename: str | None = None
        hp = (slide.get("hero_image_path") or "").strip()
        if is_hero and hp:
            src = (carousel_dir / hp) if not Path(hp).is_absolute() else Path(hp)
            if src.is_file():
                hero_filename = f"slide-{i:02d}-hero.jpg"
                dest = slides_dir / hero_filename
                if src.resolve() != dest.resolve():
                    dest.write_bytes(src.read_bytes())
            else:
                logger.warning("slide %s hero_image_path missing on disk: %s", i, src)

        render_fn = make_slide_render_fn(
            slides_dir=slides_dir, index=i, total=total,
            hero_filename=hero_filename, timeout_ms=30000,
        )
        res = await run_designer_loop(
            slide=slide,
            render_fn=render_fn,
            out_dir=slides_dir / f"loop-{i:02d}",
            is_hero=is_hero,
            hero_path=(slides_dir / hero_filename) if hero_filename else None,
            vision_critic=claude_design_critic,
            brand_verifier=claude_design_critic,
            use_vision=True,
            max_iters=3,
        )
        if not (res.converged and res.final_png and Path(res.final_png).is_file()):
            logger.error(
                "slide %s did NOT converge (reason=%r). Critic said:\n  %s",
                i, res.reason,
                "; ".join(str(h) for h in (res.history or [])[-2:]),
            )
            return 1
        dest = slides_dir / f"{i:02d}.png"
        if Path(res.final_png).resolve() != dest.resolve():
            Path(res.final_png).replace(dest)
        done += 1
        logger.info("slide %s/%s converged → %s", i, total, dest.name)

    logger.info("✅ re-render complete: %s/%s slides converged in %s", done, total, slides_dir)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug", help="carousel dir name under output/carousel/")
    ap.add_argument(
        "--vision", action="store_true",
        help="opt-in: run the per-slide vision critic loop (slow + stochastic; "
             "the same slides can converge on one run and fail the next). Default "
             "is the fast deterministic bulk render with the anti-Canva hero gate.",
    )
    args = ap.parse_args()
    try:
        return asyncio.run(rerender(args.slug, use_vision=args.vision))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001
        logger.exception("re-render crashed: %s", exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
