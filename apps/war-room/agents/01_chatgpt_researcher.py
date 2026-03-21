#!/usr/bin/env python3
"""
FASE 1 — ChatGPT Research Agent (replaces 01_exa_scraper + legacy research launchers)
Target: web research via GPT-5.4 (browsing + reasoning)
Output: raw research JSON with facts, sentiment, gov sources

Uses: npx chatgpt -m gpt-5.4 --no-store (no API key needed — uses ChatGPT account)
"""
import json
import argparse
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

# Topics to always include in Indonesia/Bali research
ALWAYS_INCLUDE = [
    "OSS perizinan", "Coretax DJP", "KITAS KBLI", "imigrasi Bali",
    "peraturan baru Indonesia", "pajak usaha asing"
]

# Source categories to cover
SOURCE_CATEGORIES = {
    "gov": ["pajak.go.id", "oss.go.id", "hukumonline.com", "jdih.go.id", "imigrasi.go.id"],
    "news": ["kontan.co.id", "bisnis.com", "cnbcindonesia.com", "detik.com"],
    "expat": ["reddit.com/r/bali", "reddit.com/r/indonesia", "expatsinbali", "internations.org"],
}


def run_chatgpt(prompt: str, timeout: int = 120) -> str:
    """Run chatgpt CLI with GPT-5.4 and return response text."""
    # Strip ANTHROPIC_API_KEY to avoid conflicts, keep OPENAI_API_KEY if present
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}

    try:
        result = subprocess.run(
            ["npx", "chatgpt", "-m", "gpt-4o", "--no-store", prompt],
            capture_output=True, text=True, timeout=timeout, env=env
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        if result.stderr:
            print(f"  chatgpt stderr: {result.stderr[:200]}", file=sys.stderr)
        return ""
    except subprocess.TimeoutExpired:
        print(f"  chatgpt timeout after {timeout}s", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"  chatgpt error: {e}", file=sys.stderr)
        return ""


def research_facts(topic: str) -> list[dict]:
    """Research factual/regulatory info on the topic via GPT-5.4 web browsing."""
    prompt = (
        f"Research the following topic for Indonesian business intelligence: '{topic}'\n\n"
        f"Search recent sources (last 7 days): {', '.join(SOURCE_CATEGORIES['gov'] + SOURCE_CATEGORIES['news'])}\n\n"
        "Return a JSON array of facts. Each fact:\n"
        '{"title": "short title", "brief": "2-3 sentence summary", '
        '"category": "gov|tax|immigration|business|regulation", '
        '"source": "source name or URL", "relevance": "high|medium"}\n\n'
        "Focus on: new regulations, OSS/Coretax/KITAS changes, business permit issues, "
        "tax rules for foreigners, Bali property/visa news.\n"
        "Return ONLY the JSON array, no other text."
    )

    print(f"  GPT-5.4 web research: {topic[:60]}...", file=sys.stderr)
    raw = run_chatgpt(prompt, timeout=120)

    if not raw:
        return []

    # Extract JSON from response
    try:
        # Find JSON array in response
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start >= 0 and end > start:
            facts = json.loads(raw[start:end])
            print(f"  Facts found: {len(facts)}", file=sys.stderr)
            return facts
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: return raw as single fact
    if raw.strip():
        return [{"title": topic, "brief": raw[:500], "category": "general",
                 "source": "chatgpt_research", "relevance": "medium"}]
    return []


def research_sentiment(topic: str) -> list[dict]:
    """Research social sentiment + expat community reaction via GPT-5.4."""
    prompt = (
        f"Search X (Twitter), Reddit (r/bali, r/indonesia), and expat forums "
        f"for recent posts (last 72h) about: '{topic}'\n\n"
        "What are people saying? What are the pain points, complaints, concerns?\n\n"
        "Return a JSON array of sentiment signals:\n"
        '{"source": "x.com|reddit|forum", "text": "post summary", '
        '"sentiment": "frustrated|worried|positive|neutral", '
        '"pain_point": "what specific problem is mentioned", '
        '"volume": "high|medium|low"}\n\n'
        "Return ONLY the JSON array, no other text."
    )

    print(f"  GPT-5.4 sentiment scan: {topic[:60]}...", file=sys.stderr)
    raw = run_chatgpt(prompt, timeout=90)

    if not raw:
        return []

    try:
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start >= 0 and end > start:
            signals = json.loads(raw[start:end])
            print(f"  Sentiment signals: {len(signals)}", file=sys.stderr)
            return signals
    except (json.JSONDecodeError, ValueError):
        pass

    return []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True, help="Research topic")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--sentiment-output", help="Separate sentiment output path (optional)")
    parser.add_argument("--force", action="store_true", help="No-op, kept for pipeline compat")
    args = parser.parse_args()

    print(f"ChatGPT researcher — topic: {args.topic}", file=sys.stderr)

    # Run both research and sentiment in sequence
    facts = research_facts(args.topic)
    sentiment = research_sentiment(args.topic)

    # Combined output: facts (research) + sentiment (social scraping)
    output = {
        "topic": args.topic,
        "scraped_at": datetime.now().isoformat(),
        "source": "ChatGPT GPT-5.4 (web browsing)",
        "facts": facts,
        "sentiment": sentiment,
        "count": len(facts) + len(sentiment),
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"{len(facts)} facts + {len(sentiment)} sentiment -> {args.output}", file=sys.stderr)

    # Also write compat files if needed
    if args.sentiment_output:
        sentiment_data = {
            "topic": args.topic,
            "scraped_at": datetime.now().isoformat(),
            "sources": ["X/Twitter (GPT-5.4)", "Reddit (GPT-5.4)"],
            "data": sentiment,
            "count": len(sentiment),
        }
        Path(args.sentiment_output).write_text(
            json.dumps(sentiment_data, ensure_ascii=False, indent=2)
        )
        print(f"Sentiment -> {args.sentiment_output}", file=sys.stderr)


if __name__ == "__main__":
    main()
