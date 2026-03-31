#!/usr/bin/env python3
"""
FASE 2 — Gemini 3.1 Pro Deep Think — Stratega di Business
Produce 3 narrative concepts asimmetrici dal dump processato.
Fallback: Grok-3 via xAI API (no Anthropic/Google SDK needed).
"""
import json
import argparse
import sys
import subprocess
import os
from pathlib import Path
from typing import Optional

import httpx


XAI_BASE_URL = "https://api.x.ai/v1"
GROK_MODEL = "grok-3"


def run_gemini(prompt: str) -> str:
    """Call Gemini via CLI. Raises RuntimeError on failure."""
    result = subprocess.run(
        ["gemini", "-p", prompt],
        capture_output=True, text=True, timeout=300
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"Gemini CLI error (rc={result.returncode}): {result.stderr[:200]}")
    return result.stdout.strip()


def extract_json_array(text: str) -> str:
    """
    Robustly extract a JSON array from LLM output.
    Handles: ```json...```, ```...```, and bare [...] arrays.
    Uses rfind to skip any '[' in reasoning prose and grab the last/real array.
    """
    # Try fenced blocks first (most reliable)
    if "```json" in text:
        inner = text.split("```json", 1)[1]
        if "```" in inner:
            return inner.split("```", 1)[0].strip()

    if "```" in text:
        # Find the last ``` block, which is typically the JSON output
        parts = text.rsplit("```", 2)
        if len(parts) >= 2:
            candidate = parts[-2].strip()
            if candidate.startswith("[") or candidate.startswith("{"):
                return candidate

    # Bare array: use rfind to get the LAST '[' — skips prose/reasoning
    last_open = text.rfind("[")
    last_close = text.rfind("]")
    if last_open != -1 and last_close > last_open:
        return text[last_open:last_close + 1]

    return text


def run_grok_fallback(topic: str, facts: list, sentiment: list, api_key: str) -> Optional[list]:
    """
    Call Grok-3 via xAI API to generate 3 narrative concepts.
    Returns list of concepts or None on failure.
    """
    facts_preview = json.dumps(facts[:8], ensure_ascii=False)
    sentiment_preview = json.dumps(sentiment[:5], ensure_ascii=False)

    prompt = f"""You are an expert content strategist for Bali Zero, an Indonesian business services firm.
Generate 3 asymmetric narrative concepts for a LinkedIn/Instagram carousel about: {topic}

Context facts: {facts_preview}
Social sentiment: {sentiment_preview}

Return ONLY a valid JSON array of exactly 3 objects, each with these fields:
- title: compelling headline (max 60 chars)
- hook: opening line that stops the scroll
- core_insight: the main takeaway (1-2 sentences)
- asymmetric_angle: the counterintuitive or overlooked angle
- recommended_tone: one of istituzionale_severo | cinico | ironico | empatico
- why_this_will_perform: why this angle resonates with expats/investors in Bali

Output ONLY the JSON array. No prose, no markdown fences."""

    try:
        with httpx.Client(timeout=90) as client:
            resp = client.post(
                f"{XAI_BASE_URL}/chat/completions",
                json={
                    "model": GROK_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.4,
                    "max_tokens": 3000,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            extracted = extract_json_array(content)
            concepts = json.loads(extracted)
            if isinstance(concepts, list) and len(concepts) > 0:
                print(f"  ✓ Grok-3 fallback: {len(concepts)} concepts", file=sys.stderr)
                return concepts
    except Exception as e:
        print(f"  Grok-3 fallback failed: {e}", file=sys.stderr)
    return None


def hardcoded_fallback(topic: str) -> list:
    """Last-resort fallback — only if both Gemini and Grok fail."""
    return [
        {
            "title": f"The {topic} Compliance Gap",
            "hook": f"What most foreign investors don't know about {topic}",
            "core_insight": f"The real risk of {topic} is not what it looks like on the surface.",
            "asymmetric_angle": "Second-order consequences that experts are not covering",
            "recommended_tone": "istituzionale_severo",
            "why_this_will_perform": "Actionable intelligence for a specific audience"
        },
        {
            "title": f"{topic}: The Timeline Nobody Told You About",
            "hook": "You have less time than you think",
            "core_insight": "Deadlines and enforcement windows that change everything.",
            "asymmetric_angle": "Most people will act too late — here's the exact calendar",
            "recommended_tone": "cinico",
            "why_this_will_perform": "Urgency drives engagement"
        },
        {
            "title": f"How to Navigate {topic} Without Losing Your Investment",
            "hook": "The checklist that protects you",
            "core_insight": "Simple steps that separate compliant from non-compliant investors.",
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

    # Load Grok API key (already injected by pipeline.sh, but also read .env as safety)
    grok_api_key = os.environ.get("GROK_API_KEY", "")
    if not grok_api_key:
        env_file = Path(__file__).parent.parent / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("GROK_API_KEY="):
                    grok_api_key = line.split("=", 1)[1].strip().strip('"')
                    break

    # Keys match 015_qwen_preprocessor.py output schema
    facts = dump_data.get("facts", dump_data.get("legal_summary", []))
    sentiment = dump_data.get("sentiment", dump_data.get("social_summary", []))
    sentiment_str = json.dumps(sentiment, ensure_ascii=False, indent=2)
    legal_str = json.dumps(facts, ensure_ascii=False, indent=2)
    prompt = (
        prompts["gemini_strategist"]
        .replace("{social_dump}", sentiment_str)
        .replace("{legal_dump}", legal_str)
    ) + f"\n\nTOPIC FOCUS: {args.topic}\n\nOutput ONLY valid JSON array of 3 concepts."

    print("🧠 Gemini 3.1 Pro thinking...", file=sys.stderr)

    concepts = None
    gemini_source = "gemini"

    try:
        response = run_gemini(prompt)
        extracted = extract_json_array(response)
        concepts = json.loads(extracted)
        if not isinstance(concepts, list):
            raise ValueError(f"Expected list, got {type(concepts)}")
        print(f"  ✓ Gemini: {len(concepts)} concepts parsed", file=sys.stderr)

    except subprocess.TimeoutExpired:
        print("⚠️  Gemini timeout — trying Grok-3 fallback", file=sys.stderr)
        gemini_source = "grok3"
    except RuntimeError as e:
        print(f"⚠️  Gemini unavailable: {e} — trying Grok-3 fallback", file=sys.stderr)
        gemini_source = "grok3"
    except (json.JSONDecodeError, ValueError) as e:
        print(f"⚠️  Gemini JSON parse failed: {e} — trying Grok-3 fallback", file=sys.stderr)
        gemini_source = "grok3"

    # Grok-3 fallback (topic-aware, uses actual facts)
    if not concepts and grok_api_key:
        concepts = run_grok_fallback(args.topic, facts, sentiment, grok_api_key)

    # Last resort: hardcoded templates
    if not concepts:
        if not grok_api_key:
            print("⚠️  No GROK_API_KEY — using hardcoded fallback", file=sys.stderr)
        concepts = hardcoded_fallback(args.topic)
        gemini_source = "hardcoded"
        print(f"   ↩️  Hardcoded fallback: {len(concepts)} generic concepts", file=sys.stderr)

    output = {
        "topic": args.topic,
        "model": "gemini-2.5-pro",
        "source": gemini_source,
        "concepts": concepts,
        "count": len(concepts)
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"✅ {len(concepts)} concept generati [{gemini_source}] → {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
