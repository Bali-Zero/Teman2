#!/usr/bin/env python3
"""
FASE 3 — Image Brainstorm + Fireworks Generation
Multi-agent brainstorming (Gemini + DeepSeek + Claude) → best prompt per slide → Fireworks Flux.1 Dev

For each slide with image_prompt:
  1. Brainstorm 3 prompt variants (Gemini visual, DeepSeek conceptual, Claude editorial)
  2. Claude synthesizes the best single prompt with BZ style
  3. Generate image via Fireworks API → save to output/images/

Output: output/images/slide_N.jpg + output/images/image_manifest.json
"""
import json
import sys
import argparse
import subprocess
import urllib.request
import time
import os
from pathlib import Path

BZ_STYLE = """
BALI ZERO VISUAL IDENTITY — MANDATORY RULES:
1. CINEMATIC REALISM (never AI art, never illustration, never rendering)
2. COLOR GRADING: teal/cyan in shadows + amber/gold in highlights — ALWAYS
3. CAMERA + LENS: always specify (ARRI Alexa Mini LF / Hasselblad X2D / RED V-Raptor) + (85mm f/1.4 / 35mm anamorphic / 50mm prime)
4. LIGHT: golden hour 80% / moody overcast for risk slides
5. STYLE KEYWORDS: hyper-realistic, editorial photography, film grain, shallow depth of field, volumetric golden light
6. NEVER: text in image, logos, stock imagery, handshakes, cartoon, illustration, AI-pretty aesthetic
7. ASPECT: 4:5 portrait (Instagram), 1024x1280px
8. MOOD: opportunity slides = warm golden serene authority / risk slides = cold shadows surveillance tense / cover = maximum cinematic impact
"""

FIREWORKS_URL = "https://api.fireworks.ai/inference/v1/workflows/accounts/fireworks/models/flux-1-dev-fp8/text_to_image"


def call_gemini(prompt: str, timeout: int = 120) -> str:
    """Gemini CLI — visual brainstorming."""
    result = subprocess.run(
        ["gemini", "-p", prompt],
        capture_output=True, text=True, timeout=timeout
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    raise RuntimeError(f"Gemini error: {result.stderr[:200]}")


def call_claude(prompt: str, timeout: int = 120) -> str:
    """Claude CLI — synthesis."""
    import shutil
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    claude_bin = shutil.which("claude") or "/Users/nuzantara/.local/bin/claude"
    result = subprocess.run(
        [claude_bin, "-p", prompt],
        capture_output=True, text=True, timeout=timeout, env=env
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    raise RuntimeError(f"Claude error: {result.stderr[:200]}")


def call_deepseek(prompt: str, timeout: int = 120) -> str:
    """DeepSeek via OpenRouter API — conceptual reasoning."""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY not set")
    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 500
    }).encode()
    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
        msg = data["choices"][0]["message"]
        content = msg.get("content", "").strip()
        if not content:
            content = msg.get("reasoning_content", "").strip()
        return content


def brainstorm_prompt(slide: dict, topic: str, slide_type: str) -> str:
    """
    Multi-agent brainstorm → Claude synthesizes best Fireworks prompt.
    Returns final optimized prompt string.
    """
    raw_prompt = slide.get("image_prompt", "")
    headline = slide.get("headline", "")
    is_cover = slide.get("is_cover", False)
    placement = slide.get("image_placement", "full_bleed")

    brainstorm_brief = f"""
You are a world-class editorial art director for Bali Zero, an Indonesian business services firm.

SLIDE CONTEXT:
- Topic: {topic}
- Headline: {headline}
- Is cover: {is_cover}
- Image placement: {placement}
- Slide type: {slide_type}
- Raw image concept: {raw_prompt}

BZ VISUAL IDENTITY:
{BZ_STYLE}

YOUR TASK:
Generate ONE ultra-precise Fireworks/Flux image generation prompt for this slide.
The prompt must:
- Follow BZ visual identity strictly (teal+amber, cinematic, hyper-realistic)
- Specify camera + lens
- Specify lighting (golden hour or moody overcast)
- Be 2-4 sentences max, dense with visual specifics
- End with: "Hyper-realistic, editorial photography, cinematic teal and amber color grading, film grain, no text, no logos."
- NO Midjourney flags (--ar, --v, --style) — this is for Flux/Fireworks

Return ONLY the prompt text, nothing else.
"""

    variants = []

    # Agent 1: Gemini — visual/compositional angle
    try:
        g_prompt = f"You are a cinematographer. {brainstorm_brief}\nFocus on: composition, lighting, camera movement, visual metaphor."
        variants.append(("Gemini", call_gemini(g_prompt, timeout=90)))
        print("   ✅ Gemini variant OK", file=sys.stderr)
    except Exception as e:
        print(f"   ⚠️  Gemini: {e}", file=sys.stderr)

    # Agent 2: DeepSeek — conceptual/symbolic angle
    try:
        ds_prompt = f"You are a conceptual photographer. {brainstorm_brief}\nFocus on: symbolic meaning, emotional tension, narrative subtext."
        variants.append(("DeepSeek", call_deepseek(ds_prompt, timeout=90)))
        print("   ✅ DeepSeek variant OK", file=sys.stderr)
    except Exception as e:
        print(f"   ⚠️  DeepSeek: {e}", file=sys.stderr)

    # If no variants, use raw prompt + BZ style suffix
    if not variants:
        print("   ⚠️  No brainstorm agents available — using raw prompt", file=sys.stderr)
        return (
            f"{raw_prompt} "
            "Shot on ARRI Alexa Mini LF with 85mm f/1.4 lens. "
            "Golden hour, volumetric light, teal and amber color grading. "
            "Hyper-realistic, editorial photography, cinematic teal and amber color grading, film grain, no text, no logos."
        )

    # Claude synthesizes
    variants_text = "\n\n".join([f"VARIANT {i+1} ({name}):\n{v}" for i, (name, v) in enumerate(variants)])
    synthesis_prompt = f"""
You are Claude, creative director at Bali Zero. You have {len(variants)} image prompt variants for a slide.

SLIDE: "{headline}" | Topic: {topic} | Cover: {is_cover}

VARIANTS:
{variants_text}

BZ STYLE RULES:
{BZ_STYLE}

Synthesize the SINGLE best Fireworks/Flux prompt by:
1. Taking the strongest visual idea from each variant
2. Ensuring strict BZ style compliance (teal+amber, cinematic, hyper-realistic)
3. Specifying camera (ARRI Alexa Mini LF or Hasselblad X2D) + lens (85mm f/1.4 or 35mm anamorphic)
4. Keeping it 3-5 sentences, ultra-specific
5. Ending with: "Hyper-realistic, editorial photography, cinematic teal and amber color grading, film grain, no text, no logos."

Return ONLY the final prompt. No explanation, no preamble.
"""

    try:
        final = call_claude(synthesis_prompt, timeout=120)
        print("   ✅ Claude synthesis OK", file=sys.stderr)
        return final.strip()
    except Exception as e:
        print(f"   ⚠️  Claude synthesis failed: {e} — using best variant", file=sys.stderr)
        return variants[0][1] if variants else raw_prompt


def generate_image(prompt: str, api_key: str, output_path: Path, width: int = 1024, height: int = 1280) -> bool:
    """Generate image via Fireworks Flux.1 Dev. Returns True on success."""
    payload = json.dumps({
        "prompt": prompt,
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
            "Authorization": f"Bearer {api_key}",
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            img_bytes = resp.read()
        if len(img_bytes) < 5000:
            print(f"   ⚠️  Response too small ({len(img_bytes)} bytes)", file=sys.stderr)
            return False
        output_path.write_bytes(img_bytes)
        print(f"   ✅ Image saved: {output_path} ({len(img_bytes)//1024}KB)", file=sys.stderr)
        return True
    except Exception as e:
        print(f"   ⚠️  Fireworks generation failed: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slides", required=True, help="Path to claude_slides.json")
    parser.add_argument("--output", required=True, help="Output directory for images")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    slides_data = json.loads(Path(args.slides).read_text())
    topic = slides_data.get("topic", "")
    tone = slides_data.get("tone", "cinico")
    slides = slides_data.get("slides", [])
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    fireworks_key = os.environ.get("FIREWORKS_API_KEY", "")
    if not fireworks_key:
        # Try loading from war-room .env
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("FIREWORKS_API_KEY="):
                    fireworks_key = line.split("=", 1)[1].strip()
                    break

    if not fireworks_key:
        print("❌ FIREWORKS_API_KEY not found — skipping image generation", file=sys.stderr)
        sys.exit(1)

    # Filter slides with image_prompt
    image_slides = [s for s in slides if s.get("image_prompt")]
    print(f"🎨 Image brainstorm — {len(image_slides)} slides con image_prompt", file=sys.stderr)

    manifest = []

    for slide in image_slides:
        slide_num = slide.get("slide_number", 0)
        is_cover = slide.get("is_cover", False)
        slide_type = "cover" if is_cover else ("risk" if tone in ["cinico", "allerta"] else "opportunity")

        print(f"\n   🖼️  Slide {slide_num} ({slide_type}) — brainstorming...", file=sys.stderr)

        # Brainstorm → best prompt
        final_prompt = brainstorm_prompt(slide, topic, slide_type)
        print(f"   📝 Final prompt ({len(final_prompt)} chars):", file=sys.stderr)
        print(f"      {final_prompt[:120]}...", file=sys.stderr)

        output_path = output_dir / f"slide_{slide_num:02d}.jpg"
        manifest_entry = {
            "slide_number": slide_num,
            "is_cover": is_cover,
            "final_prompt": final_prompt,
            "output_file": str(output_path),
            "generated": False
        }

        if not args.dry_run:
            print(f"   🚀 Generating via Fireworks...", file=sys.stderr)
            success = generate_image(final_prompt, fireworks_key, output_path)
            manifest_entry["generated"] = success
            if success:
                # Inject image path back into slides_data for canva_builder
                for s in slides_data["slides"]:
                    if s.get("slide_number") == slide_num:
                        s["generated_image_path"] = str(output_path)
                        break
            time.sleep(1)  # Rate limit courtesy
        else:
            print(f"   DRY RUN — skipping generation", file=sys.stderr)

        manifest.append(manifest_entry)

    # Save manifest
    manifest_path = output_dir / "image_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))

    # Update slides JSON with generated image paths
    if not args.dry_run:
        Path(args.slides).write_text(json.dumps(slides_data, ensure_ascii=False, indent=2))

    generated = sum(1 for m in manifest if m.get("generated"))
    print(f"\n✅ Image brainstorm completato: {generated}/{len(image_slides)} generate", file=sys.stderr)
    print(f"📋 Manifest: {manifest_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
