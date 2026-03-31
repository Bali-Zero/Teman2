#!/usr/bin/env python3
"""
FASE 1 — xAI Grok Researcher
Uses Grok-3 (xAI API, OpenAI-compatible) for real-time web search + analysis.
Grok has live X/Twitter data access and real-time web search built-in.

Usage:
    python 10_xai_researcher.py --topic "Coretax 2025" --output output/raw/xai_dump.json
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

XAI_API_KEY = os.environ.get("GROK_API_KEY", "")
XAI_BASE_URL = "https://api.x.ai/v1"
MODEL = "grok-3"

SYSTEM_PROMPT = """You are an expert researcher on Indonesian business law, immigration, tax, and investment in Bali.
You have access to real-time web search and live X/Twitter data.

Your task: given a topic, research it thoroughly from an Indonesia/Bali business perspective.
Focus on: recent regulatory changes, government announcements, expert opinions, expat community reactions on X.

Return ONLY valid JSON — no prose, no markdown fences."""

RESEARCH_PROMPT = """Research this topic for an Indonesian business intelligence briefing aimed at foreign investors in Bali:

TOPIC: {topic}

Search the web and X/Twitter for the latest developments (last 7 days preferred).
Focus on: regulatory changes, government announcements, market impact, expat community sentiment.

Return JSON:
{{
  "topic": "{topic}",
  "facts": [
    {{
      "title": "concise headline",
      "brief": "2-3 sentence summary of key fact",
      "category": "immigration|tax|business_regulations|property|legal|compliance",
      "source": "source URL or name",
      "published": "YYYY-MM-DD if known",
      "relevance": "high|medium",
      "from_x": false
    }}
  ],
  "x_sentiment": [
    {{
      "text": "paraphrase of X post or thread",
      "sentiment": "positive|negative|neutral|concerned",
      "pain_point": "what issue is being raised",
      "volume": "high|medium|low"
    }}
  ],
  "key_insight": "1-sentence most important takeaway for Bali-based foreign investor",
  "count": <total facts + x_sentiment count>
}}

Include at least 8 facts and 3 X sentiment signals if available. Prioritize recency and regulatory impact."""


def log(msg: str, level: str = "INFO"):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [xAI] [{level}] {msg}", file=sys.stderr, flush=True)


def research(topic: str) -> dict:
    if not XAI_API_KEY:
        log("GROK_API_KEY not set", "ERROR")
        return {"facts": [], "x_sentiment": [], "error": "no_api_key"}

    prompt = RESEARCH_PROMPT.format(topic=topic)
    log(f"Grok-3 research: '{topic}'")

    try:
        with httpx.Client(timeout=90) as client:
            resp = client.post(
                f"{XAI_BASE_URL}/chat/completions",
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 4000,
                },
                headers={
                    "Authorization": f"Bearer {XAI_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]

            # Strip markdown fences if present
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```", 2)[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.rsplit("```", 1)[0].strip()

            data = json.loads(content)
            facts = data.get("facts", [])
            x_sentiment = data.get("x_sentiment", [])
            log(f"Got {len(facts)} facts + {len(x_sentiment)} X signals")
            return data

    except json.JSONDecodeError as e:
        log(f"JSON parse error: {e}", "WARN")
        # Return raw as single fact
        return {
            "facts": [{"title": f"xAI research: {topic}", "brief": content[:500], "category": "general", "source": "grok-3", "relevance": "medium"}],
            "x_sentiment": [],
            "error": "json_parse_failed",
        }
    except Exception as e:
        log(f"Request failed: {e}", "ERROR")
        return {"facts": [], "x_sentiment": [], "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="xAI Grok Researcher")
    parser.add_argument("--topic", required=True, help="Research topic")
    parser.add_argument("--output", required=True, help="Output JSON path")
    args = parser.parse_args()

    # Load API key from .env if not in environment
    if not XAI_API_KEY:
        env_file = Path(__file__).parent.parent / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("GROK_API_KEY="):
                    os.environ["GROK_API_KEY"] = line.split("=", 1)[1].strip().strip('"')
                    globals()["XAI_API_KEY"] = os.environ["GROK_API_KEY"]
                    break

    if not XAI_API_KEY:
        log("GROK_API_KEY not found in env or .env file", "ERROR")
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps({"facts": [], "x_sentiment": [], "error": "no_api_key"}, indent=2))
        sys.exit(1)

    t0 = time.time()
    data = research(args.topic)

    output = {
        "topic": args.topic,
        "scraped_at": datetime.now().isoformat(),
        "source": f"xAI Grok-3 (live search)",
        "facts": data.get("facts", []),
        "x_sentiment": data.get("x_sentiment", []),
        "key_insight": data.get("key_insight", ""),
        "count": len(data.get("facts", [])) + len(data.get("x_sentiment", [])),
        "stats": {
            "facts_count": len(data.get("facts", [])),
            "x_signals": len(data.get("x_sentiment", [])),
            "elapsed_seconds": round(time.time() - t0, 1),
        },
    }
    if data.get("error"):
        output["error"] = data["error"]

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2))

    log(f"Done in {output['stats']['elapsed_seconds']}s — {output['count']} total signals")
    log(f"Output: {args.output}")


if __name__ == "__main__":
    main()
