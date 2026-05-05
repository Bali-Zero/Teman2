#!/usr/bin/env python3
"""Codex visual orchestrator — generates visual assets for BZ Dispatch via Codex CLI.

Designed to eventually replace `wr2_image_generator.py` (FlowKit/Playwright)
once parity is validated. For now runs ALONGSIDE the existing pipeline,
output goes to a separate folder so output can be A/B compared.

Asset bundle per topic (1 dispatch):
- 1× hero (1080×1350 IG carousel slide 1) — 5 prompt variants
- 6× body (1080×1350 IG carousel slides 2-7) — coherent style
- 2× story (1080×1920 vertical) — extracted hero highlights
- 1× twitter card (1200×630)
- 1× linkedin header (1200×627)

Total: ~15 images / dispatch.

Uses Codex CLI built-in image generation (`$imagegen` tag) which calls
`gpt-image-2` via OAuth Pro $200 quota — NO API key, NO per-call billing.

Output: ~/Desktop/nuzantara/research/dispatch/YYYY-MM-DD/codex-visuals/
        ├── hero-{1..5}.png
        ├── body-{1..6}.png
        ├── story-{1,2}.png
        ├── twitter-card.png
        └── linkedin-header.png
        └── manifest.json (prompts used + metadata)

Usage:
    python codex_visual_orchestrator.py --topic-file path/to/topic.md
    python codex_visual_orchestrator.py --topic-text "Topic title and brief"
    python codex_visual_orchestrator.py --dispatch-date YYYY-MM-DD --topic-text "..."

Hard rules:
- No OPENAI_API_KEY — Codex CLI uses OAuth Pro quota
- Idempotent: if manifest.json exists for the dispatch date, skip
- Telegram notify on completion + failure
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# Defense-in-depth: strip ANTHROPIC keys from env
for forbidden in ("ANTHROPIC_API_KEY", "AWS_BEDROCK_ANTHROPIC_KEY", "VERTEX_AI_ANTHROPIC_KEY"):
    os.environ.pop(forbidden, None)

# Derive repo root from this script's location. Override via
# NUZANTARA_REPO_ROOT env var when running from a worktree.
REPO_ROOT = Path(os.environ.get("NUZANTARA_REPO_ROOT") or
                 Path(__file__).resolve().parent.parent)
DISPATCH_ROOT = REPO_ROOT / "research" / "dispatch"
LOG_DIR = Path.home() / "logs" / "codex-visual-orchestrator"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("visual-orchestrator")


# ─────────────────────────────────────────────────────────────────
# Asset spec
# ─────────────────────────────────────────────────────────────────


@dataclass
class AssetRequest:
    name: str
    size: str  # "WxH" Codex accepts ratio hints
    aspect: str  # "1080x1350", "1080x1920", "1200x630"
    purpose: str
    prompt_template: str  # uses {topic}, {style_anchor}


# Bali Zero brand style anchor — applied to every prompt for coherence
BZ_STYLE_ANCHOR = (
    "Editorial style, neo-noir tropical aesthetic, deep teal ocean tones, "
    "warm amber sun, crushed blacks, Bali volcanic landscape elements, "
    "Indonesian heritage motifs (subtle batik patterns, temple silhouettes), "
    "ARRI Alexa Mini LF cinematic grade, shallow depth of field, "
    "ultra-sharp typography overlay-ready (negative space top 20% and bottom 30%). "
    "Absolutely no cartoon, no clipart, no infographic icons, no stock photo aesthetic, "
    "no people unless explicitly required."
)

ASSET_BUNDLE: list[AssetRequest] = [
    # 5 hero variants (carousel slide 1)
    *[
        AssetRequest(
            name=f"hero-{i+1}",
            size="1080x1350",
            aspect="1080x1350 (Instagram carousel 4:5)",
            purpose="Carousel slide 1 hero — main editorial image",
            prompt_template=(
                "Hero image for Bali Zero editorial dispatch on: {topic}. "
                "Variant {variant_num}: {variant_angle}. "
                "{style_anchor}"
            ),
        )
        for i in range(5)
    ],
    # 6 body images (slides 2-7)
    *[
        AssetRequest(
            name=f"body-{i+1}",
            size="1080x1350",
            aspect="1080x1350 (Instagram carousel 4:5)",
            purpose=f"Carousel slide {i+2} — supporting visual",
            prompt_template=(
                "Supporting visual #{slide_num} for editorial on: {topic}. "
                "Focus angle: {body_angle}. {style_anchor}"
            ),
        )
        for i in range(6)
    ],
    # 2 story variants
    AssetRequest(
        name="story-1",
        size="1080x1920",
        aspect="1080x1920 (Instagram story 9:16)",
        purpose="Instagram story vertical hero",
        prompt_template=(
            "Vertical story hero for: {topic}. "
            "Compose for 9:16 mobile fullscreen, top safe-area for username overlay, "
            "bottom safe-area for swipe-up. {style_anchor}"
        ),
    ),
    AssetRequest(
        name="story-2",
        size="1080x1920",
        aspect="1080x1920 (Instagram story 9:16)",
        purpose="Instagram story alternative",
        prompt_template=(
            "Alternative vertical story for: {topic}. "
            "Different mood than story-1 — wider environmental shot, more breathing room. {style_anchor}"
        ),
    ),
    # Social previews
    AssetRequest(
        name="twitter-card",
        size="1200x630",
        aspect="1200x630 (Twitter/X large card 1.91:1)",
        purpose="Twitter share card",
        prompt_template=(
            "Twitter/X card for: {topic}. Wide horizontal composition, "
            "title placement on left third, image weight on right. {style_anchor}"
        ),
    ),
    AssetRequest(
        name="linkedin-header",
        size="1200x627",
        aspect="1200x627 (LinkedIn post 1.91:1)",
        purpose="LinkedIn post header",
        prompt_template=(
            "Professional LinkedIn header for: {topic}. "
            "B2B framing, more corporate, less editorial flair, but keep style coherent. {style_anchor}"
        ),
    ),
]


# Variant angles for hero variations
HERO_VARIANT_ANGLES = [
    "wide environmental establishing shot, drone aerial perspective",
    "intimate close-up macro detail of central object/element",
    "human element silhouette against landscape (no faces visible)",
    "abstract geometric composition with key brand element",
    "documentary-style mid-shot, ground-level, golden hour light",
]

# Body angles for slide 2-7 progression
BODY_ANGLES = [
    "introduction context — wide setup shot",
    "detail #1 of the topic — first key concept visualized",
    "detail #2 — second concept or contrast element",
    "human/process angle — practical implication",
    "data or insight angle — abstract representation of numbers/trend",
    "closing/horizon angle — forward-looking visual",
]


# ─────────────────────────────────────────────────────────────────
# Codex image generation
# ─────────────────────────────────────────────────────────────────


@dataclass
class GenerationResult:
    asset_name: str
    success: bool
    output_path: str | None
    duration_s: float
    error: str | None = None
    prompt_used: str = ""


async def generate_one(asset: AssetRequest, topic: str, output_dir: Path, slot_idx: int = 0) -> GenerationResult:
    """Invoke Codex CLI with $imagegen for a single asset."""
    start = time.time()

    # Build prompt with style anchor + variant
    template_vars: dict[str, Any] = {
        "topic": topic,
        "style_anchor": BZ_STYLE_ANCHOR,
        "variant_num": slot_idx + 1,
        "variant_angle": HERO_VARIANT_ANGLES[slot_idx % len(HERO_VARIANT_ANGLES)] if asset.name.startswith("hero") else "",
        "slide_num": slot_idx + 1,
        "body_angle": BODY_ANGLES[slot_idx % len(BODY_ANGLES)] if asset.name.startswith("body") else "",
    }
    prompt_text = asset.prompt_template.format(**template_vars)

    full_prompt = (
        f"$imagegen {prompt_text}\n\n"
        f"Output requirements: {asset.aspect}. "
        f"Save the generated image to: {output_dir / asset.name}.png"
    )

    output_path = output_dir / f"{asset.name}.png"

    logger.info("Generating %s (size=%s)...", asset.name, asset.size)

    try:
        proc = await asyncio.create_subprocess_exec(
            "codex",
            "--profile",
            "image",
            "exec",
            full_prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(output_dir),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        duration = time.time() - start

        # Check if image actually got generated
        if output_path.exists() and output_path.stat().st_size > 1024:
            return GenerationResult(
                asset_name=asset.name,
                success=True,
                output_path=str(output_path),
                duration_s=duration,
                prompt_used=prompt_text,
            )

        # Fallback: scan output_dir for any new PNG that Codex may have named differently
        candidates = sorted(
            [p for p in output_dir.glob("*.png") if p.stat().st_mtime > start],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            # Rename to expected name
            new_path = output_path
            candidates[0].rename(new_path)
            return GenerationResult(
                asset_name=asset.name,
                success=True,
                output_path=str(new_path),
                duration_s=duration,
                prompt_used=prompt_text,
            )

        # No image found
        err_summary = stderr.decode(errors="replace")[:500] or stdout.decode(errors="replace")[:500]
        return GenerationResult(
            asset_name=asset.name,
            success=False,
            output_path=None,
            duration_s=duration,
            error=f"no image produced: {err_summary}",
            prompt_used=prompt_text,
        )

    except asyncio.TimeoutError:
        return GenerationResult(
            asset_name=asset.name,
            success=False,
            output_path=None,
            duration_s=time.time() - start,
            error="timeout 300s",
            prompt_used=prompt_text,
        )
    except Exception as e:
        return GenerationResult(
            asset_name=asset.name,
            success=False,
            output_path=None,
            duration_s=time.time() - start,
            error=str(e),
            prompt_used=prompt_text,
        )


async def generate_bundle(topic: str, output_dir: Path, parallelism: int = 3) -> list[GenerationResult]:
    """Generate all 15 assets, with limited parallelism to respect quota pace."""
    output_dir.mkdir(parents=True, exist_ok=True)

    sem = asyncio.Semaphore(parallelism)

    async def with_sem(asset: AssetRequest, idx: int) -> GenerationResult:
        async with sem:
            return await generate_one(asset, topic, output_dir, idx)

    # For hero/body assets, slot_idx = position in their group; for singletons, idx = 0
    tasks = []
    hero_idx = body_idx = 0
    for a in ASSET_BUNDLE:
        if a.name.startswith("hero"):
            tasks.append(with_sem(a, hero_idx))
            hero_idx += 1
        elif a.name.startswith("body"):
            tasks.append(with_sem(a, body_idx))
            body_idx += 1
        else:
            tasks.append(with_sem(a, 0))

    return list(await asyncio.gather(*tasks))


# ─────────────────────────────────────────────────────────────────
# Telegram notify
# ─────────────────────────────────────────────────────────────────


def telegram_notify(text: str) -> None:
    notify_script = Path.home() / ".claude" / "scripts" / "hotfix-notify.sh"
    if notify_script.exists():
        try:
            subprocess.run([str(notify_script), text], check=False, timeout=10)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────


async def main_async(args: argparse.Namespace) -> int:
    # Resolve topic text
    if args.topic_file:
        topic = Path(args.topic_file).read_text(encoding="utf-8").strip()
    else:
        topic = args.topic_text or ""

    if not topic.strip():
        logger.error("Empty topic")
        return 1

    # Truncate topic if too long (Codex prompt limits)
    if len(topic) > 4000:
        topic = topic[:4000] + "..."

    dispatch_date = args.dispatch_date or time.strftime("%Y-%m-%d")
    output_dir = DISPATCH_ROOT / dispatch_date / "codex-visuals"

    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists() and not args.force:
        logger.info("Manifest already exists at %s. Use --force to regenerate.", manifest_path)
        return 0

    logger.info("Topic: %s", topic[:200])
    logger.info("Output dir: %s", output_dir)
    logger.info("Bundle: %d assets", len(ASSET_BUNDLE))

    start = time.time()
    results = await generate_bundle(topic, output_dir, parallelism=args.parallelism)
    duration = time.time() - start

    success_count = sum(1 for r in results if r.success)

    # Write manifest
    manifest = {
        "dispatch_date": dispatch_date,
        "topic": topic[:500],
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "duration_s": round(duration, 1),
        "assets_total": len(ASSET_BUNDLE),
        "assets_success": success_count,
        "results": [asdict(r) for r in results],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str))

    logger.info("Generated %d/%d assets in %.1fs", success_count, len(ASSET_BUNDLE), duration)

    if args.notify:
        if success_count == len(ASSET_BUNDLE):
            telegram_notify(
                f"✅ Codex visual: {success_count}/{len(ASSET_BUNDLE)} assets for {dispatch_date}\n"
                f"📁 {output_dir}"
            )
        elif success_count > 0:
            failed = [r.asset_name for r in results if not r.success]
            telegram_notify(
                f"⚠️ Codex visual: {success_count}/{len(ASSET_BUNDLE)} assets for {dispatch_date}\n"
                f"Failed: {', '.join(failed[:5])}"
            )
        else:
            telegram_notify(f"🔴 Codex visual: 0/{len(ASSET_BUNDLE)} assets generated for {dispatch_date}")

    return 0 if success_count > 0 else 1


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--topic-file", type=Path, help="Path to markdown file describing the topic")
    src.add_argument("--topic-text", help="Inline topic description")
    ap.add_argument("--dispatch-date", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--parallelism", type=int, default=3, help="Concurrent Codex calls (default: 3)")
    ap.add_argument("--force", action="store_true", help="Regenerate even if manifest exists")
    ap.add_argument("--notify", action="store_true", help="Telegram notify on completion")
    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()
    exit_code = asyncio.run(main_async(args))
    raise SystemExit(exit_code)
