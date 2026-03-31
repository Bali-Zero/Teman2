#!/usr/bin/env python3
"""
FASE 0 — Topic Selector (Multi-Source)
=======================================
Collects signals from 4 parallel sources, then DeepSeek synthesizes the best topic.

Sources:
  1. Exa AI search — Indonesian news + legal domains, last 72h
  2. NLM NB-7 query — audience pain points + content gaps
  3. xAI Grok — X/Twitter trending signals on Indonesia business
  4. Intel pre-seed — local scraper enriched articles (if fresh)

Synthesis:
  DeepSeek (via API) — reads all signals, picks ONE topic with angle + rationale
  Fallback: deterministic scoring on intel articles

Input:  intel_output_latest.json (bali-intel-scraper)
Output: output/strategy/selected_topic.json
  {
    "topic": "string — topic strategico formulato per carousel (max 65 chars)",
    "angle": "string — angolo asimmetrico per foreign investors",
    "why":   "string — perché questo topic ora",
    "trend_signal": "string — segnale trend se disponibile",
    "source_articles": ["title1", "title2", "title3"],
    "sources_used": ["exa", "nlm", "xai", "intel"]
  }
"""
import json
import sys
import os
import argparse
import subprocess
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path


# ── Config ────────────────────────────────────────────────────────────────────
NLM_NB7_ID   = "f51ab8a0-50d0-49f1-a64f-ebc131fed7b8"   # NB-7 content strategy
XAI_BASE_URL = "https://api.x.ai/v1"
GROK_MODEL   = "grok-3"
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
EXA_BASE_URL = "https://api.exa.ai"

INDONESIAN_LEGAL_DOMAINS = [
    "hukumonline.com", "ddtc.co.id", "ddtcnews.com",
    "bisnis.com", "cnbcindonesia.com", "thejakartapost.com",
    "imigrasi.go.id", "bkpm.go.id", "pajak.go.id", "oss.go.id",
]

SYNTHESIS_PROMPT = """You are the editorial director of Bali Zero, an Indonesian business services firm targeting foreign investors and expats in Bali.

You have received intelligence from multiple sources this morning. Your job: pick ONE topic for a carousel post.

RULES for the best topic:
- Must directly affect foreign investors or expats in Bali (visa, tax, permits, property, company setup)
- Must have urgency: rising trend, hard deadline in 30 days, or enforcement risk
- Must have an asymmetric angle — the "second-order consequence" most people are missing
- Max 65 characters for the topic string
- Formulate as a strategic angle, NOT a news headline

GOOD: "Coretax Deadline: The Gap Nobody Warned You About"
GOOD: "New KBLI Rules Are Quietly Voiding Existing PT PMAs"
BAD: "Indonesia Coretax update" (too generic)

INTELLIGENCE:
{signals}

Output ONLY this JSON — no markdown, no explanation:
{{
  "topic": "strategic angle max 65 chars",
  "angle": "the second-order consequence nobody is covering (1 sentence)",
  "why": "timing/urgency — why this week specifically (1 sentence)",
  "trend_signal": "strongest trend signal found (or 'no trend data')",
  "source_articles": ["title 1", "title 2", "title 3"]
}}"""


def fetch_exa_signals(topic_hint: str, api_key: str) -> list:
    """Exa AI search — Indonesian news last 72h."""
    if not api_key:
        print("  ⚠️  EXA_API_KEY not set — skipping Exa", file=sys.stderr)
        return []

    queries = [
        f"{topic_hint} Indonesia business regulation" if topic_hint else "Indonesia business regulation expat investor 2026",
        "Indonesia visa KITAS permit regulation 2026",
        "Indonesia tax pajak regulation update 2026",
    ]

    import httpx
    results = []
    from datetime import timedelta
    cutoff = (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")

    for q in queries[:2]:  # 2 queries max
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    f"{EXA_BASE_URL}/search",
                    json={
                        "query": q,
                        "num_results": 8,
                        "type": "neural",
                        "start_published_date": cutoff,
                        "include_domains": INDONESIAN_LEGAL_DOMAINS[:6],
                        "contents": {"text": {"max_characters": 500}},
                    },
                    headers={"x-api-key": api_key, "Content-Type": "application/json"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for r in data.get("results", []):
                        results.append({
                            "title": r.get("title", ""),
                            "brief": (r.get("text") or r.get("snippet") or "")[:300],
                            "source": r.get("url", ""),
                            "_src": "exa",
                        })
        except Exception as e:
            print(f"  ⚠️  Exa query failed: {e}", file=sys.stderr)

    print(f"  ✅ Exa: {len(results)} articles", file=sys.stderr)
    return results


def fetch_nlm_signals(topic_hint: str) -> list:
    """NLM NB-7 query — content strategy + audience pain points."""
    query = (
        f"What are the most pressing concerns for foreign investors and expats in Bali right now"
        + (f" regarding {topic_hint}" if topic_hint else "")
        + "? List top 3-5 pain points or questions they have this week. Be specific."
    )
    try:
        result = subprocess.run(
            ["nlm", "query", "notebook", NLM_NB7_ID, query, "--timeout", "60"],
            capture_output=True, text=True, timeout=90
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise RuntimeError(result.stderr.strip() or "empty response")

        output = result.stdout.strip()
        try:
            data = json.loads(output)
            if "value" in data and isinstance(data["value"], dict):
                data = data["value"]
            answer = data.get("answer", output)
        except json.JSONDecodeError:
            answer = output

        signals = []
        for line in answer.splitlines():
            line = line.strip(" •-*0123456789.")
            if len(line) > 20:
                signals.append({"title": line[:120], "brief": "", "_src": "nlm"})

        print(f"  ✅ NLM NB-7: {len(signals)} pain points", file=sys.stderr)
        return signals[:5]

    except Exception as e:
        print(f"  ⚠️  NLM NB-7 failed: {e}", file=sys.stderr)
        return []


def fetch_xai_signals(topic_hint: str, api_key: str) -> list:
    """xAI Grok — X/Twitter trending signals on Indonesia business."""
    if not api_key:
        print("  ⚠️  GROK_API_KEY not set — skipping xAI", file=sys.stderr)
        return []

    prompt = (
        f"Search X/Twitter for the most discussed topics among expats and foreign investors in Indonesia/Bali this week"
        + (f", especially about {topic_hint}" if topic_hint else "")
        + ". Focus on: visa changes, tax enforcement, business permits, property rules. "
        "List top 5 trending topics/concerns with their urgency level. Be concise."
    )

    try:
        import httpx
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                f"{XAI_BASE_URL}/chat/completions",
                json={
                    "model": GROK_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 600,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()

        signals = []
        for line in content.splitlines():
            line = line.strip(" •-*0123456789.")
            if len(line) > 20:
                signals.append({"title": line[:150], "brief": "", "_src": "xai"})

        print(f"  ✅ xAI Grok: {len(signals)} X signals", file=sys.stderr)
        return signals[:5]

    except Exception as e:
        print(f"  ⚠️  xAI Grok failed: {e}", file=sys.stderr)
        return []


def synthesize_with_deepseek(all_signals: list, api_key: str) -> dict | None:
    """DeepSeek — synthesizes all signals into best topic."""
    if not api_key:
        print("  ⚠️  DEEPSEEK_API_KEY not set — skipping DeepSeek synthesis", file=sys.stderr)
        return None

    # Group signals by source for clarity
    by_source = {}
    for s in all_signals:
        src = s.get("_src", "unknown")
        by_source.setdefault(src, []).append(s)

    signals_text = ""
    for src, items in by_source.items():
        signals_text += f"\n[{src.upper()} — {len(items)} signals]\n"
        for s in items[:5]:
            title = s.get("title", "")
            brief = s.get("brief", "")[:150]
            signals_text += f"  • {title}"
            if brief:
                signals_text += f": {brief}"
            signals_text += "\n"

    prompt = SYNTHESIS_PROMPT.replace("{signals}", signals_text.strip())

    try:
        payload = json.dumps({
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 600,
            "temperature": 0.3,
        }).encode()

        req = urllib.request.Request(
            DEEPSEEK_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            content = data["choices"][0]["message"]["content"].strip()

        # Extract JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        elif "{" in content:
            start, end = content.find("{"), content.rfind("}") + 1
            content = content[start:end]

        result = json.loads(content)
        print(f"  ✅ DeepSeek synthesis: {result.get('topic', '')[:50]}", file=sys.stderr)
        return result

    except Exception as e:
        print(f"  ⚠️  DeepSeek synthesis failed: {e}", file=sys.stderr)
        return None


def deterministic_fallback(articles: list, topic_hint: str = "") -> dict:
    """Last-resort: pick best article from intel scraper by score."""
    from collections import Counter
    cat_counts = Counter(a.get("category") or a.get("qwen_category", "OTHER") for a in articles)
    dominant_cat = cat_counts.most_common(1)[0][0] if cat_counts else "GENERAL"

    top = sorted(articles, key=lambda a: a.get("qwen_score", 0), reverse=True)
    best = top[0] if top else {}
    topic = topic_hint or best.get("title", "Indonesia Business Intelligence")[:60]

    return {
        "topic": topic,
        "angle": f"Key regulatory implications for foreign investors",
        "why": "Top story in today's Indonesian business intelligence",
        "trend_signal": "no trend data (deterministic fallback)",
        "source_articles": [a.get("title", "") for a in top[:3]],
        "sources_used": ["intel_fallback"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--intel",  required=True, help="Path a intel_output_latest.json")
    parser.add_argument("--output", required=True, help="Path output selected_topic.json")
    parser.add_argument("--hint",   default="",    help="Topic hint opzionale")
    args = parser.parse_args()

    intel_path = Path(args.intel)
    if not intel_path.exists():
        print(f"❌ Intel file not found: {intel_path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(intel_path.read_text())
    articles = [a for a in data.get("articles", []) if a.get("enrichment")]
    if not articles:
        articles = data.get("articles", [])

    articles.sort(key=lambda a: a.get("qwen_score", 0), reverse=True)
    top_articles = articles[:15]
    intel_signals = [
        {
            "title": a.get("title", ""),
            "brief": str((a.get("enrichment") or {}).get("executive_brief") or
                         (a.get("enrichment") or {}).get("the_facts") or "")[:200],
            "category": a.get("category") or a.get("qwen_category", ""),
            "_src": "intel",
        }
        for a in top_articles
    ]

    # API keys
    exa_key       = os.environ.get("EXA_API_KEY", "")
    grok_key      = os.environ.get("GROK_API_KEY", "")
    deepseek_key  = os.environ.get("DEEPSEEK_API_KEY", "")

    print(f"🎯 Topic Selector (multi-source) — {len(top_articles)} intel articles", file=sys.stderr)
    print(f"   Sources: intel ✅ | exa {'✅' if exa_key else '❌'} | nlm ✅ | xai {'✅' if grok_key else '❌'} | deepseek {'✅' if deepseek_key else '❌'}", file=sys.stderr)

    # ── Fetch all signals in parallel ──────────────────────────────────────────
    all_signals = list(intel_signals)
    sources_used = ["intel"]

    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = {
            ex.submit(fetch_exa_signals, args.hint, exa_key): "exa",
            ex.submit(fetch_nlm_signals, args.hint): "nlm",
            ex.submit(fetch_xai_signals, args.hint, grok_key): "xai",
        }
        for f in as_completed(futures):
            src = futures[f]
            try:
                signals = f.result()
                if signals:
                    all_signals.extend(signals)
                    sources_used.append(src)
            except Exception as e:
                print(f"  ⚠️  {src} fetch failed: {e}", file=sys.stderr)

    print(f"   Total signals: {len(all_signals)} from {sources_used}", file=sys.stderr)

    # ── Synthesize with DeepSeek ───────────────────────────────────────────────
    result = None
    if deepseek_key and all_signals:
        print("🧠 DeepSeek synthesis...", file=sys.stderr)
        result = synthesize_with_deepseek(all_signals, deepseek_key)

    if not result:
        print("↩️  Deterministic fallback (no DeepSeek or synthesis failed)", file=sys.stderr)
        result = deterministic_fallback(top_articles, args.hint)

    # Add metadata
    result["selected_at"] = datetime.now().isoformat()
    result["articles_analyzed"] = len(top_articles)
    result["signals_total"] = len(all_signals)
    result.setdefault("sources_used", sources_used)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2))

    print(f"✅ Topic: {result['topic']}", file=sys.stderr)
    print(f"   Angle: {result.get('angle','')[:80]}", file=sys.stderr)
    print(f"   Trend: {result.get('trend_signal','')[:60]}", file=sys.stderr)

    # Stdout per pipeline.sh
    print(result["topic"])


if __name__ == "__main__":
    main()
