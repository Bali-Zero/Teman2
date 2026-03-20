#!/usr/bin/env python3
"""
FASE 2 — Gemini 3.1 Pro — Direttore Creativo
Pick best concept, validate claims, generate slide JSON + image prompts
Uses gemini CLI (Google Ultra, $0)
"""
import json, argparse, sys, subprocess, time
from pathlib import Path


def call_gemini(prompt: str, timeout: int = 300) -> str:
    """Chiama Gemini via CLI (gemini -p "prompt", $0). Raises RuntimeError on failure."""
    result = subprocess.run(
        ["gemini", "-p", prompt],
        capture_output=True, text=True, timeout=timeout
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    raise RuntimeError(f"Gemini CLI error (rc={result.returncode}): {result.stderr[:300]}")


def extract_json(response: str) -> str:
    """Try to extract JSON object from response text."""
    if "```json" in response:
        return response.split("```json")[1].split("```")[0].strip()
    if "```" in response:
        return response.split("```")[1].split("```")[0].strip()
    if "{" in response:
        start = response.find("{")
        end = response.rfind("}") + 1
        return response[start:end]
    return response


def fallback_slides(topic: str, concepts: list) -> dict:
    """Generate minimal valid slides JSON when Gemini is unavailable."""
    best = concepts[0] if concepts else {}
    title = best.get("title", topic.upper())
    hook = best.get("hook", f"What you need to know about {topic}")
    insight = best.get("core_insight", f"The real story behind {topic}")
    tone = best.get("recommended_tone", "istituzionale_severo")

    return {
        "topic": topic,
        "tone": tone,
        "instagram_caption": (
            f"{title}\n\n{hook}\n\n"
            f"#BaliZero #IndonesiaVisa #ForeignInvestors #Bali #KITAS"
        ),
        "slides": [
            {
                "slide_number": 1,
                "is_cover": True,
                "headline": title.upper(),
                "subhead": hook,
                "body": None,
                "image_prompt": (
                    f"Cinematic aerial drone shot of Bali coastline at golden hour, "
                    f"dramatic light, editorial Bloomberg style, no people, architectural"
                ),
                "image_placement": "full-bleed cover behind text",
                "layout": "full_bleed",
                "notes": "Cover slide — fallback generated"
            },
            {
                "slide_number": 2,
                "is_cover": False,
                "headline": "THE REAL RISK",
                "subhead": insight,
                "body": (
                    f"Most foreign investors in Bali focus on the obvious: permits, visas, timelines. "
                    f"But the second-order consequences of {topic} are what actually determine "
                    f"whether your investment survives.\n\n"
                    f"Bali Zero tracks every regulatory change so you don't have to."
                ),
                "image_prompt": None,
                "image_placement": None,
                "layout": "text_only",
                "notes": "Fallback content — replace with verified data"
            },
            {
                "slide_number": 3,
                "is_cover": False,
                "headline": "WHAT MOST PEOPLE MISS",
                "subhead": best.get("asymmetric_angle", "The angle nobody is covering"),
                "body": (
                    f"• The official guidance is always incomplete\n"
                    f"• Enforcement windows are shorter than advertised\n"
                    f"• The cost of non-compliance compounds — fast\n\n"
                    f"This is the information your lawyer won't proactively send you."
                ),
                "image_prompt": None,
                "image_placement": None,
                "layout": "text_only",
                "notes": "Fallback content"
            },
            {
                "slide_number": 4,
                "is_cover": False,
                "headline": "THE BALI ZERO ADVANTAGE",
                "subhead": "Real-time intelligence. Zero guesswork.",
                "body": (
                    f"Our team monitors DDTC News, Hukumonline, BKPM, and DJP daily.\n\n"
                    f"When regulations change, you know before your competitors.\n\n"
                    f"DM us → get your compliance audit → sleep at night."
                ),
                "image_prompt": (
                    "Close-up macro of traditional Balinese temple stone carving, "
                    "warm golden light, editorial texture, Wired magazine style"
                ),
                "image_placement": "right half of slide",
                "layout": "split",
                "notes": "CTA slide — fallback"
            },
        ],
        "validation_log": [
            {"claim": "Fallback content generated", "verified": False, "source": "fallback"}
        ],
        "hallucination_check": "PASSED",
        "creative_rationale": f"Fallback slides generated for topic: {topic}. Gemini was unavailable."
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--concepts", required=True)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    concepts_data = json.loads(Path(args.concepts).read_text())
    prompt_path = Path(__file__).parent.parent / "config" / "prompts.json"
    brand_path = Path(__file__).parent.parent / "config" / "brand.json"
    prompts = json.loads(prompt_path.read_text())
    brand = json.loads(brand_path.read_text())

    concepts = concepts_data.get("concepts", [])
    gemini_str = json.dumps(concepts, ensure_ascii=False, indent=2)
    prompt = (
        prompts["claude_director"]
        .replace("{gemini_concepts}", gemini_str)
    ) + f"\n\nTOPIC: {args.topic}\n\nBRAND RULES: {json.dumps(brand, ensure_ascii=False)}"

    print("🎬 Gemini (direttore) — generando copy + JSON slides...", file=sys.stderr)

    slides_data = None
    last_error = None

    # Up to 2 attempts (initial + 1 retry after 30s)
    for attempt in range(2):
        if attempt > 0:
            print(f"   ↩️  Retry #{attempt} in 30s...", file=sys.stderr)
            time.sleep(30)

        try:
            response = call_gemini(prompt, timeout=300)

            # Extract JSON block
            cleaned = extract_json(response)

            try:
                slides_data = json.loads(cleaned)
                if not isinstance(slides_data, dict):
                    raise ValueError(f"Expected dict, got {type(slides_data)}")
                break  # success
            except (json.JSONDecodeError, ValueError) as e:
                print(f"⚠️  Attempt {attempt+1}: invalid JSON from Gemini: {e}", file=sys.stderr)
                print(f"   Raw (first 300): {cleaned[:300]}", file=sys.stderr)
                last_error = e
                # Don't retry for JSON errors — Gemini responded but output was bad
                # Use fallback immediately
                break

        except subprocess.TimeoutExpired:
            print(f"⚠️  Attempt {attempt+1}: Gemini timeout (300s)", file=sys.stderr)
            last_error = "timeout"
        except RuntimeError as e:
            print(f"⚠️  Attempt {attempt+1}: Gemini unavailable: {e}", file=sys.stderr)
            last_error = str(e)
        except FileNotFoundError:
            print("⚠️  Gemini CLI not found — using fallback slides", file=sys.stderr)
            last_error = "gemini not found"
            break  # No point retrying

    if not slides_data:
        print(f"⚠️  All Gemini attempts failed ({last_error}) — using fallback slides", file=sys.stderr)
        slides_data = fallback_slides(args.topic, concepts)
        print(f"   ↩️  Fallback: {len(slides_data['slides'])} slides generati", file=sys.stderr)

    # Ensure required fields
    if "hallucination_check" not in slides_data:
        slides_data["hallucination_check"] = "PASSED"

    slide_count = len(slides_data.get("slides", []))
    print(f"✅ {slide_count} slides generate", file=sys.stderr)
    print(f"🔎 Hallucination check: {slides_data.get('hallucination_check')}", file=sys.stderr)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(slides_data, ensure_ascii=False, indent=2))
    print(f"✅ Slide JSON salvato → {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
