#!/usr/bin/env python3
"""
FASE 1.5 — Smart Preprocessor
Deterministic preprocessing: dedup by hash + recency scoring + source trust weighting.
Falls back to Ollama Qwen3.5 ONLY if running inside the Ollama cron window (01:00-06:05 WITA)
and Ollama is actually up (TCP probe, 1s).
Zero cost, H24 available.
"""
import json
import argparse
import socket
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional


# Source trust weights — higher = more reliable/editorial
SOURCE_TRUST = {
    "nlm": 1.0,          # NLM NB-7: editorial + verified claims
    "xai": 0.9,          # xAI Grok: real-time X + web
    "gemini": 0.85,      # Gemini: legal/gov focus
    "exa": 0.8,          # Exa: broad news, high volume
    "intel": 0.75,       # Intel scraper: local enriched
    "chatgpt": 0.65,     # ChatGPT: broad but can be stale
}


def ollama_is_up(host: str = "localhost", port: int = 11434, timeout: float = 1.0) -> bool:
    """TCP probe — returns True only if Ollama port is open."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def in_ollama_window() -> bool:
    """Check if current WITA time is inside the Ollama active window (01:00-06:05)."""
    wita = timezone(timedelta(hours=8))
    now = datetime.now(wita)
    return (now.hour == 1 or (now.hour >= 1 and now.hour < 6) or
            (now.hour == 6 and now.minute <= 5))


def run_qwen_api(prompt: str) -> Optional[str]:
    """Chiama Qwen3.5 via Ollama REST API — solo se Ollama è up."""
    for model, timeout in [("qwen3.5:27b", 90), ("qwen3.5:9b", 60)]:
        try:
            print(f"  Trying {model} via REST API (timeout={timeout}s)...", file=sys.stderr)
            payload = json.dumps({
                "model": model, "prompt": prompt, "stream": False, "think": False,
                "options": {"num_predict": 2048, "temperature": 0.1},
            }).encode("utf-8")
            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=payload, headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data.get("response", "").strip()
                if text:
                    print(f"  {model} OK ({len(text)} chars)", file=sys.stderr)
                    return text
        except (urllib.error.URLError, TimeoutError, Exception) as e:
            print(f"  {model} failed: {e}", file=sys.stderr)
    return None


def deterministic_preprocess(facts: list, sentiment: list, max_facts: int = 15) -> dict:
    """
    Pure-Python preprocessing: dedup + score + rank.
    No LLM required. O(n) time.
    """
    seen_hashes: set = set()
    scored: list = []

    for fact in facts:
        title = fact.get("title", "").strip().lower()
        url = fact.get("source", fact.get("url", "")).strip()

        # Dedup key: title prefix (first 60 chars) or URL
        dedup_key = title[:60] if title else url
        if not dedup_key or dedup_key in seen_hashes:
            continue
        seen_hashes.add(dedup_key)

        # Source trust score
        src = fact.get("_source", fact.get("source_name", "")).lower()
        trust = 0.5  # default
        for key, weight in SOURCE_TRUST.items():
            if key in src:
                trust = weight
                break

        # Recency score (0.0-1.0) — published within last 7 days
        recency = 0.5
        pub = fact.get("published", fact.get("scraped_at", ""))
        if pub:
            try:
                from dateutil import parser as dateparser
                pub_dt = dateparser.parse(pub[:19])
                if pub_dt:
                    if pub_dt.tzinfo is None:
                        pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                    age_hours = (datetime.now(timezone.utc) - pub_dt).total_seconds() / 3600
                    recency = max(0.0, 1.0 - age_hours / 168)  # 168h = 7 days
            except Exception:
                pass

        # Relevance from upstream scoring
        relevance_raw = fact.get("qwen_score", fact.get("quality_score", fact.get("score", 50)))
        relevance = float(relevance_raw) / 100.0 if relevance_raw else 0.5

        # Composite score
        composite = trust * 0.4 + recency * 0.3 + relevance * 0.3
        scored.append({**fact, "_score": round(composite, 3)})

    # Sort by composite score descending
    scored.sort(key=lambda x: x["_score"], reverse=True)
    top_facts = scored[:max_facts]

    # Extract topics
    topics = list(dict.fromkeys(
        f.get("category", f.get("qwen_category", ""))
        for f in top_facts if f.get("category") or f.get("qwen_category")
    ))

    return {
        "facts": top_facts,
        "sentiment": sentiment[:8],
        "topics": [t for t in topics if t],
        "preprocessed_by": "deterministic",
        "stats": {
            "input_count": len(facts),
            "output_count": len(top_facts),
            "dedup_removed": len(facts) - len(scored),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sentiment", required=False, default="")
    parser.add_argument("--research", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    sentiment_path = Path(args.sentiment) if args.sentiment else None
    sentiment_data = json.loads(sentiment_path.read_text()) if sentiment_path and sentiment_path.exists() else []
    research_data = json.loads(Path(args.research).read_text())

    facts = research_data.get("facts", research_data) if isinstance(research_data, dict) else research_data
    if not isinstance(facts, list):
        facts = []
    sentiment_list = sentiment_data if isinstance(sentiment_data, list) else []

    print("🔄 Smart pre-processor — deterministic mode...", file=sys.stderr)

    # Try Qwen ONLY if: inside Ollama window AND Ollama TCP probe passes
    result = None
    if in_ollama_window():
        if ollama_is_up():
            print("  ✓ Ollama is up (in window) — attempting Qwen enhancement", file=sys.stderr)
            prompt_path = Path(__file__).parent.parent / "config" / "prompts.json"
            try:
                prompts = json.loads(prompt_path.read_text())
                facts_trimmed = facts[:15]
                sentiment_trimmed = sentiment_list[:8]
                prompt = prompts["qwen_preprocessor"] + f"""

RAW SOCIAL SENTIMENT DATA:
{json.dumps(sentiment_trimmed, ensure_ascii=False, indent=2)}

FACTS:
{json.dumps(facts_trimmed, ensure_ascii=False, indent=2)}

Output ONLY valid JSON. No markdown, no prose, no explanation."""

                response = run_qwen_api(prompt)
                if response:
                    # Parse JSON from Qwen
                    if "<think>" in response:
                        end_think = response.rfind("</think>")
                        if end_think != -1:
                            response = response[end_think + len("</think>"):].strip()
                    for fence in ["```json", "```"]:
                        if fence in response:
                            response = response.split(fence)[1].split("```")[0].strip()
                            break
                    if "{" in response:
                        start = response.find("{")
                        end = response.rfind("}") + 1
                        response = response[start:end]
                    parsed = json.loads(response)
                    if isinstance(parsed, dict) and "facts" in parsed:
                        result = parsed
                        result["preprocessed_by"] = "qwen"
                        print(f"  ✓ Qwen enhanced: {len(result.get('facts', []))} facts", file=sys.stderr)
            except Exception as e:
                print(f"  Qwen enhancement failed: {e} — using deterministic", file=sys.stderr)
        else:
            print("  Ollama not responding (TCP probe failed) — skipping", file=sys.stderr)
    else:
        print("  Outside Ollama window — skipping Qwen, using deterministic", file=sys.stderr)

    # Always use deterministic as base or fallback
    if not result:
        result = deterministic_preprocess(facts, sentiment_list)
        stats = result["stats"]
        print(f"  ✓ Deterministic: {stats['output_count']}/{stats['input_count']} facts "
              f"(removed {stats['dedup_removed']} dupes)", file=sys.stderr)

    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"✅ Pre-processed dump → {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
