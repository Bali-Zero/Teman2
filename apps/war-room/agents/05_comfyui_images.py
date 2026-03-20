#!/usr/bin/env python3
"""
War Room Step 3 — Generate carousel images via ComfyUI Flux + captions IG/X.
Replaces 05_gemini_images.py (Playwright browser automation).

Output:
  output/images/slide_01.png ... slide_N.png
  output/images/caption_instagram.txt
  output/images/caption_x.txt
  output/images/manifest.json
"""
import json
import sys
import argparse
from pathlib import Path

# Reuse the ComfyUI/Pollinations client from intel scraper
SCRIPT_DIR = Path(__file__).parent
INTEL_SCRIPTS = SCRIPT_DIR.parent.parent / "bali-intel-scraper" / "scripts"
if not INTEL_SCRIPTS.exists():
    print(f"ERROR: intel-scraper scripts not found at {INTEL_SCRIPTS}", file=sys.stderr)
    sys.exit(1)
sys.path.insert(0, str(INTEL_SCRIPTS))
from comfyui_image_generator import check_comfyui, generate_image, generate_image_pollinations
from bz_image_style import build_slide_prompt


def generate_caption_ig(topic: str, slides: list, tone: str) -> str:
    """Generate Instagram carousel caption."""
    headlines = [s.get("title", s.get("headline", "")) for s in slides[:8]]
    bullet_points = "\n".join(f"→ {h}" for h in headlines if h)

    return f"""{topic}

{bullet_points}

Swipe per saperne di più. ←

Il panorama normativo e fiscale di Bali e dell'Indonesia cambia ogni giorno.
Noi lo monitoriamo per te — così tu puoi concentrarti sul tuo business.

Tone: {tone}

#BaliZero #BusinessInBali #IndonesiaBusiness #Expat #DigitalNomad #BaliLife #Immigration #Visa #KITAS #PMA #Coretax #Compliance #BaliExpat #IndonesiaLaw"""


def generate_caption_x(topic: str, slides: list) -> str:
    """Generate X/Twitter caption (max 280 chars)."""
    headline = slides[0].get("title", topic) if slides else topic
    if len(headline) > 200:
        headline = headline[:197] + "..."

    return f"""{headline}

Full analysis → balizero.com/news

#BaliZero #IndonesiaBusiness"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slides", required=True, help="Path to claude_slides.json")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--output", required=True, help="Output directory for images")
    args = parser.parse_args()

    slides_data = json.loads(Path(args.slides).read_text())
    slides = slides_data.get("slides", [])
    tone = slides_data.get("tone", "professional")
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    use_comfyui = check_comfyui()
    if not use_comfyui:
        print("ComfyUI not running — will use Pollinations.ai fallback", file=sys.stderr)

    manifest = {"topic": args.topic, "images": [], "captions": {}}
    generated = 0

    for i, slide in enumerate(slides):
        title = slide.get("title", slide.get("headline", f"Slide {i+1}"))
        body = slide.get("body", slide.get("copy", ""))
        layout = slide.get("layout", "content")
        style = slide.get("image_prompt_suffix", "")

        prompt = build_slide_prompt(title, body, style)
        img_path = output_dir / f"slide_{i+1:02d}.png"
        print(f"\n[{i+1}/{len(slides)}] {title[:60]}...", file=sys.stderr)

        # Carousel = 1080x1080, cover = 1080x1350
        w, h = (1080, 1350) if i == 0 else (1080, 1080)

        ok = False
        if use_comfyui:
            ok = generate_image(prompt, img_path, width=w, height=h, timeout=180)
            if not ok:
                print(f"  ComfyUI failed — trying Pollinations fallback", file=sys.stderr)
                ok = generate_image_pollinations(prompt, img_path, width=w, height=h)
        else:
            ok = generate_image_pollinations(prompt, img_path, width=w, height=h)

        if ok:
            manifest["images"].append({
                "slide": i + 1,
                "title": title,
                "path": str(img_path),
                "layout": layout,
            })
            generated += 1
        else:
            print(f"  Failed — placeholder will be used", file=sys.stderr)

    # Generate captions
    caption_ig = generate_caption_ig(args.topic, slides, tone)
    caption_x = generate_caption_x(args.topic, slides)
    (output_dir / "caption_instagram.txt").write_text(caption_ig)
    (output_dir / "caption_x.txt").write_text(caption_x)
    manifest["captions"] = {
        "instagram": str(output_dir / "caption_instagram.txt"),
        "x": str(output_dir / "caption_x.txt"),
    }

    # Save manifest
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    print(f"\nGenerated {generated}/{len(slides)} images + 2 captions", file=sys.stderr)


if __name__ == "__main__":
    main()
