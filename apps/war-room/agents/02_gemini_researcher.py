#!/usr/bin/env python3
"""
FASE 1 — Gemini Legal Researcher
Uses Gemini CLI with native Google Search to find fresh Indonesian
government/legal sources that ChatGPT and Exa miss.

Runs in parallel with 01_chatgpt_researcher.py and 09_exa_researcher.py.

Usage:
    python 02_gemini_researcher.py --topic "Coretax March 31" --output output/raw/gemini_dump.json
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_gemini(prompt: str, timeout: int = 180) -> str:
    """Call Gemini CLI — has native Google Search grounding."""
    result = subprocess.run(
        ["gemini", "-p", prompt],
        capture_output=True, text=True, timeout=timeout
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    raise RuntimeError(f"Gemini CLI error (rc={result.returncode}): {result.stderr[:200]}")


def extract_json_array(text: str) -> list:
    """Extract JSON array from Gemini response."""
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    if text.startswith("["):
        return json.loads(text)

    # Try to find array in text
    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        return json.loads(text[start:end])

    return []


PROMPT_TEMPLATE = """Search Google NOW for the latest Indonesian government and legal news.

TOPIC: {topic}

SEARCH THESE SPECIFIC SOURCES (last 72 hours):
- site:ddtcnews.com "{topic}"
- site:hukumonline.com "{topic}"
- site:pajak.go.id OR site:djp.go.id
- site:oss.go.id OR site:bkpm.go.id
- site:cnbcindonesia.com OR site:bisnis.com "{topic}"
- site:imigrasi.go.id

For each relevant result, extract:
- Exact regulation name/number (e.g., PP 28/2025, PMK 81/2024)
- Effective dates and deadlines
- Penalties or sanctions mentioned
- Official quotes if available
- The source URL

Output ONLY a JSON array of facts. Each fact:
{{"title": "short title", "brief": "2-3 sentence summary with specific numbers/dates", "category": "gov|tax|immigration|business|regulation", "source": "URL", "regulation": "regulation number if applicable"}}

Return ONLY the JSON array, no other text."""


def main():
    parser = argparse.ArgumentParser(description="Gemini Legal Researcher")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    prompt = PROMPT_TEMPLATE.format(topic=args.topic)

    print(f"🔍 Gemini legal research: {args.topic[:60]}", file=sys.stderr)
    print(f"  Searching Google (ddtcnews, hukumonline, pajak.go.id, oss.go.id)...", file=sys.stderr)

    try:
        response = run_gemini(prompt, timeout=180)
        facts = extract_json_array(response)
        print(f"  ✅ Gemini: {len(facts)} legal facts found", file=sys.stderr)
    except (RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired) as e:
        print(f"  ⚠️  Gemini research failed: {e}", file=sys.stderr)
        facts = []
    except FileNotFoundError:
        print("  ⚠️  Gemini CLI not found — skipping", file=sys.stderr)
        facts = []

    output = {
        "facts": facts,
        "count": len(facts),
        "source": "gemini_google_search",
        "topic": args.topic,
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"  → {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
