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

TIGRIS_ENDPOINT = "https://fly.storage.tigris.dev"
TIGRIS_BUCKET = "nuzantara-warroom-images"
# Public URLs must use subdomain format (path-style returns 403 on public buckets)
TIGRIS_PUBLIC_BASE = f"https://{TIGRIS_BUCKET}.fly.storage.tigris.dev"


def upload_to_tigris(file_path: Path, key: str) -> str:
    """Upload image to Tigris S3 → return public URL. Returns "" on failure."""
    import os
    access_key = os.environ.get("AWS_ACCESS_KEY_ID", "tid_sZQYyrgouAXAdQDuvsfPlLIIUMMvEDNhfMWmzCdeouELsPMn_U")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "tsec_5knItu7FoHkkv2P5qaEMSRdHxXDNb6ZD0+mgDfLsLF-lLntRwDUgrH4qmzhJX+3OI4XYTc")
    if not access_key or not secret_key:
        return ""
    try:
        img_bytes = file_path.read_bytes()
        # Build S3 PUT request manually (no boto3 dependency)
        import hmac, hashlib, datetime
        now = datetime.datetime.utcnow()
        date_str = now.strftime("%Y%m%d")
        ts_str = now.strftime("%Y%m%dT%H%M%SZ")
        region = "auto"
        host = "fly.storage.tigris.dev"
        content_type = "image/jpeg"
        content_hash = hashlib.sha256(img_bytes).hexdigest()

        canonical = "\n".join([
            "PUT",
            f"/{TIGRIS_BUCKET}/{key}",
            "",
            f"content-type:{content_type}",
            f"host:{host}",
            f"x-amz-content-sha256:{content_hash}",
            f"x-amz-date:{ts_str}",
            "",
            "content-type;host;x-amz-content-sha256;x-amz-date",
            content_hash,
        ])
        string_to_sign = "\n".join([
            "AWS4-HMAC-SHA256", ts_str,
            f"{date_str}/{region}/s3/aws4_request",
            hashlib.sha256(canonical.encode()).hexdigest(),
        ])
        def hmac_sha256(key, msg):
            return hmac.new(key if isinstance(key, bytes) else key.encode(), msg.encode(), hashlib.sha256).digest()
        signing_key = hmac_sha256(hmac_sha256(hmac_sha256(hmac_sha256(
            f"AWS4{secret_key}", date_str), region), "s3"), "aws4_request")
        signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
        auth = (
            f"AWS4-HMAC-SHA256 Credential={access_key}/{date_str}/{region}/s3/aws4_request,"
            f"SignedHeaders=content-type;host;x-amz-content-sha256;x-amz-date,"
            f"Signature={signature}"
        )
        req = urllib.request.Request(
            f"{TIGRIS_ENDPOINT}/{TIGRIS_BUCKET}/{key}",
            data=img_bytes,
            method="PUT",
            headers={
                "Content-Type": content_type,
                "Authorization": auth,
                "x-amz-date": ts_str,
                "x-amz-content-sha256": content_hash,
                "x-amz-acl": "public-read",
            }
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status in (200, 204):
                url = f"{TIGRIS_PUBLIC_BASE}/{key}"
                print(f"   ✅ Tigris upload OK: {url}", file=sys.stderr)
                return url
    except Exception as e:
        print(f"   ⚠️  Tigris upload failed: {e}", file=sys.stderr)
    return ""



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


def generate_image(prompt: str, api_key: str, output_path: Path, width: int = 1440, height: int = 1800):
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
        # Upload to Tigris for public URL (needed by Canva upload-asset-from-url)
        tigris_key = f"warroom/{output_path.name}"
        public_url = upload_to_tigris(output_path, tigris_key)
        return public_url if public_url else True
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

    # Target: 1 cover + 5 slide images = 6 total
    TARGET_IMAGES = 6
    cover_slides = [s for s in slides if s.get("is_cover") or s.get("slide_number") == 1]
    body_with_prompt = [s for s in slides if not (s.get("is_cover") or s.get("slide_number") == 1) and s.get("image_prompt")]
    body_without_prompt = [s for s in slides if not (s.get("is_cover") or s.get("slide_number") == 1) and not s.get("image_prompt")]

    # Ensure cover has an image_prompt
    for s in cover_slides:
        if not s.get("image_prompt"):
            s["image_prompt"] = (
                f"Ultra-cinematic aerial cover image for: {s.get('headline', topic)}. "
                "Bali, Indonesia. Maximum visual impact, golden hour, editorial photography."
            )
            print(f"   🔧 Auto-generated cover image_prompt", file=sys.stderr)

    # Auto-generate image_prompt for body slides until we reach TARGET_IMAGES
    needed = TARGET_IMAGES - len(cover_slides) - len(body_with_prompt)
    for s in body_without_prompt[:max(0, needed)]:
        headline = s.get("headline", "")
        subhead = s.get("subhead", "") or ""
        s["image_prompt"] = (
            f"Editorial photograph for slide: {headline}. {subhead[:80]}. "
            "Bali Indonesia context, cinematic teal and amber color grading."
        )
        body_with_prompt.append(s)
        print(f"   🔧 Auto-generated image_prompt for slide {s.get('slide_number')}: {headline[:50]}", file=sys.stderr)

    image_slides = cover_slides + body_with_prompt[:TARGET_IMAGES - len(cover_slides)]
    print(f"🎨 Image brainstorm — {len(image_slides)} immagini (1 cover + {len(image_slides)-len(cover_slides)} slide, target {TARGET_IMAGES})", file=sys.stderr)

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
            manifest_entry["generated"] = bool(success)
            if success:
                # Inject image path + public URL back into slides_data
                public_url = success if isinstance(success, str) else ""
                manifest_entry["public_url"] = public_url
                for s in slides_data["slides"]:
                    if s.get("slide_number") == slide_num:
                        s["generated_image_path"] = str(output_path)
                        if public_url:
                            s["generated_image_url"] = public_url
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
