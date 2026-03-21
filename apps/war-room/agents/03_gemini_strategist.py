#!/usr/bin/env python3
"""
FASE 2 — Gemini 3.1 Pro Deep Think — Stratega di Business
Produce 3 narrative concepts asimmetrici dal dump processato
"""
import json, argparse, sys, subprocess
from pathlib import Path

def run_gemini(prompt: str) -> str:
    """Call Gemini via CLI (gemini -p "prompt"). Raises RuntimeError on failure."""
    result = subprocess.run(
        ["gemini", "-p", prompt],
        capture_output=True, text=True, timeout=300
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"Gemini CLI error (rc={result.returncode}): {result.stderr[:200]}")
    return result.stdout.strip()


def fallback_concepts(topic: str) -> list:
    """Genera 3 concept minimali come fallback se Gemini è unavailable."""
    return [
        {
            "title": f"The {topic} Compliance Gap",
            "hook": f"What most foreign investors don't know about {topic}",
            "core_insight": f"The real risk of {topic} is not what it looks like on the surface",
            "asymmetric_angle": "Second-order consequences that experts are not covering",
            "recommended_tone": "istituzionale_severo",
            "why_this_will_perform": "Actionable intelligence for a specific audience"
        },
        {
            "title": f"{topic}: The Timeline Nobody Told You About",
            "hook": "You have less time than you think",
            "core_insight": "Deadlines and enforcement windows that change everything",
            "asymmetric_angle": "Most people will act too late — here's the exact calendar",
            "recommended_tone": "cinico",
            "why_this_will_perform": "Urgency drives engagement"
        },
        {
            "title": f"How to Navigate {topic} Without Losing Your Investment",
            "hook": "The checklist that protects you",
            "core_insight": "Simple steps that separate compliant from non-compliant investors",
            "asymmetric_angle": "The solution is simpler than the fear — actionable in 24h",
            "recommended_tone": "ironico",
            "why_this_will_perform": "Practical value signals expertise"
        }
    ]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", required=True)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    dump_data = json.loads(Path(args.dump).read_text())
    prompt_path = Path(__file__).parent.parent / "config" / "prompts.json"
    prompts = json.loads(prompt_path.read_text())

    # Keys match 015_qwen_preprocessor.py output schema
    sentiment_str = json.dumps(dump_data.get("sentiment", dump_data.get("social_summary", [])), ensure_ascii=False, indent=2)
    legal_str     = json.dumps(dump_data.get("facts", dump_data.get("legal_summary", [])), ensure_ascii=False, indent=2)
    prompt = (
        prompts["gemini_strategist"]
        .replace("{social_dump}", sentiment_str)
        .replace("{legal_dump}",  legal_str)
    ) + f"\n\nTOPIC FOCUS: {args.topic}\n\nOutput ONLY valid JSON array of 3 concepts."

    print(f"🧠 Gemini 3.1 Pro thinking...", file=sys.stderr)

    concepts = None
    try:
        response = run_gemini(prompt)

        # Extract JSON array from response
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "[" in response:
            start = response.find("[")
            end = response.rfind("]") + 1
            response = response[start:end]

        concepts = json.loads(response)
        if not isinstance(concepts, list):
            raise ValueError(f"Expected list, got {type(concepts)}")

    except subprocess.TimeoutExpired:
        print("⚠️  Gemini timeout — using fallback concepts", file=sys.stderr)
    except RuntimeError as e:
        print(f"⚠️  Gemini unavailable: {e} — using fallback concepts", file=sys.stderr)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"⚠️  Gemini returned invalid JSON: {e} — using fallback concepts", file=sys.stderr)

    if not concepts:
        concepts = fallback_concepts(args.topic)
        print(f"   ↩️  Fallback: {len(concepts)} generic concepts generated", file=sys.stderr)

    output = {
        "topic": args.topic,
        "model": "gemini-2.5-pro",
        "concepts": concepts,
        "count": len(concepts)
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"✅ {len(concepts)} concept generati → {args.output}", file=sys.stderr)

if __name__ == "__main__":
    main()
