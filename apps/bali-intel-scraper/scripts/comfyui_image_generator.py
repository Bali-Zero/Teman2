#!/usr/bin/env python3
"""
Bali Zero Cover Image Generator
Primary: Fireworks.ai Flux.1 Dev (~$0.014/img, 2-3s, editorial quality)
Fallback: Pollinations.ai (free, no auth, ~10-30s)
Used by intel scraper step 8 (runs BEFORE publishing).
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from typing import Optional

FIREWORKS_API_KEY = os.environ.get("FIREWORKS_API_KEY", "")
FIREWORKS_URL = "https://api.fireworks.ai/inference/v1/workflows/accounts/fireworks/models/flux-1-dev-fp8/text_to_image"
POLLINATIONS_URL = "https://image.pollinations.ai/prompt"


# ── Fireworks.ai Flux.1 Dev ──

def generate_image_fireworks(prompt: str, output_path: Path,
                              width: int = 1200, height: int = 640) -> bool:
    """Primary: Fireworks.ai Flux.1 Dev — ~$0.014/image, 2-3s, editorial quality."""
    if not FIREWORKS_API_KEY:
        print("  Fireworks: FIREWORKS_API_KEY not set — skipping", file=sys.stderr)
        return False

    # Fireworks rounds to multiples of 64
    width = (width // 64) * 64
    height = (height // 64) * 64

    payload = json.dumps({
        "prompt": prompt,
        "negative_prompt": (
            "text, watermark, logo, signature, caption, subtitle, headline, "
            "illustration, cartoon, anime, flat design, 3D render, CGI, "
            "neon colors, cyberpunk, oversaturated, HDR, plastic skin, "
            "smiling businesspeople, handshake, stock photo, generic, "
            "blurry, low quality, distorted, deformed, artifact"
        ),
        "width": width,
        "height": height,
        "steps": 28,
        "cfg_scale": 3.5,
    }).encode()

    req = urllib.request.Request(
        FIREWORKS_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {FIREWORKS_API_KEY}",
        },
    )
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        if resp.status != 200:
            print(f"  Fireworks: HTTP {resp.status}", file=sys.stderr)
            return False
        data = resp.read()
        if len(data) < 5000:
            print(f"  Fireworks: response too small ({len(data)} bytes)", file=sys.stderr)
            return False
        output_path.write_bytes(data)
        print(f"  Saved via Fireworks [flux-dev]: {output_path} ({len(data) // 1024}KB)", file=sys.stderr)
        return True
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        print(f"  Fireworks HTTP error {e.code}: {body}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  Fireworks error: {e}", file=sys.stderr)
        return False


# ── Pollinations.ai fallback ──

def generate_image_pollinations(prompt: str, output_path: Path,
                                width: int = 1200, height: int = 630) -> bool:
    """Fallback: Pollinations.ai (free, no auth). Tries models in order."""
    models = ["flux", "schnell", "sana", "turbo"]
    encoded = urllib.parse.quote(prompt)
    seed = int(time.time()) % 99999

    for model in models:
        url = f"{POLLINATIONS_URL}/{encoded}?width={width}&height={height}&seed={seed}&nologo=true&model={model}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "BaliZero-IntelScraper/1.0"})
            resp = urllib.request.urlopen(req, timeout=150)
            if resp.status != 200:
                print(f"  Pollinations [{model}]: HTTP {resp.status}", file=sys.stderr)
                continue
            data = resp.read()
            if len(data) < 5000:
                print(f"  Pollinations [{model}]: response too small ({len(data)} bytes)", file=sys.stderr)
                continue
            output_path.write_bytes(data)
            print(f"  Saved via Pollinations [{model}]: {output_path} ({len(data) // 1024}KB)", file=sys.stderr)
            return True
        except TimeoutError:
            print(f"  Pollinations [{model}]: timeout — trying next", file=sys.stderr)
        except Exception as e:
            print(f"  Pollinations [{model}] error: {e}", file=sys.stderr)

    return False


# ── CLI entrypoint for intel scraper step 8 ──

def main():
    """
    Usage: python comfyui_image_generator.py <state_file>
    Reads pipeline state, generates cover images for T1/featured articles.
    Runs BEFORE publishing (step 8 → step 7).
    """
    if len(sys.argv) < 2:
        print("Usage: comfyui_image_generator.py <state_file>", file=sys.stderr)
        sys.exit(1)

    state_file = Path(sys.argv[1])
    state = json.loads(state_file.read_text())
    articles = state.get("articles", [])

    # Targets: T1/featured articles with enrichment (already filtered by pipeline)
    targets = [a for a in articles if a.get("enrichment") and
               (a.get("tier") == "T1" or a.get("featured"))]

    if not targets:
        # Fallback: top-scored enriched articles (up to 5)
        enriched = [a for a in articles if a.get("enrichment")]
        targets = sorted(enriched, key=lambda a: a.get("quality_score", 0), reverse=True)[:5]

    if not targets:
        print("No articles for image generation — nothing to do", file=sys.stderr)
        sys.exit(0)

    use_fireworks = bool(FIREWORKS_API_KEY)
    if use_fireworks:
        print(f"Fireworks.ai available — using Flux.1 Dev (~$0.014/img)", file=sys.stderr)
    else:
        print("FIREWORKS_API_KEY not set — using Pollinations.ai fallback", file=sys.stderr)

    output_dir = state_file.parent / "images"
    output_dir.mkdir(exist_ok=True)
    generated = 0

    from bz_image_style import build_cover_prompt

    for i, art in enumerate(targets):
        enr = art.get("enrichment", {})
        title = enr.get("headline", art.get("title", ""))
        category = art.get("category", "general")
        summary = enr.get("the_facts", enr.get("bali_zero_take", ""))
        prompt = build_cover_prompt(title, category, summary=summary or None)

        # Use staging ID if published ID not yet available (runs before publishing)
        item_id = art.get("_published_item_id") or art.get("_staging_item_id") or f"article_{i}"
        img_path = output_dir / f"cover_{item_id}.png"

        tier = art.get("tier", "?")
        featured = "★ " if art.get("featured") else ""
        print(f"\n[{i+1}/{len(targets)}] {featured}[{tier}] {title[:60]}", file=sys.stderr)

        if use_fireworks:
            ok = generate_image_fireworks(prompt, img_path, width=1200, height=640)
            if not ok:
                print("  Fireworks failed — trying Pollinations fallback", file=sys.stderr)
                ok = generate_image_pollinations(prompt, img_path)
        else:
            ok = generate_image_pollinations(prompt, img_path)

        if ok:
            art["image_path"] = str(img_path)
            art["image_source"] = "fireworks" if use_fireworks else "pollinations"
            generated += 1
        else:
            print("  Failed — skipping", file=sys.stderr)

        time.sleep(1)

    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    print(f"\nGenerated {generated}/{len(targets)} cover images", file=sys.stderr)


if __name__ == "__main__":
    main()
