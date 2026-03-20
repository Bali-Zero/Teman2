#!/usr/bin/env python3
"""
FASE 0 — Topic Selector
=======================
Analizza gli articoli recenti dall'intel scraper + Google Trends (via Gemini CLI)
e sceglie il topic ottimale per il carousel Bali Zero.

Input:  intel_output_latest.json (bali-intel-scraper)
Output: output/strategy/selected_topic.json
  {
    "topic": "string — topic strategico formulato per carousel",
    "angle": "string — angolo asimmetrico per foreign investors",
    "why":   "string — perché questo topic ora",
    "trend_signal": "string — segnale Google Trends se disponibile",
    "source_articles": ["title1", "title2", ...]
  }
"""
import json
import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime


GEMINI_BIN = "gemini"

TOPIC_SELECTOR_PROMPT = """STEP 1 — Search Google Trends now:
Search Google Trends for these terms this week in Indonesia: "Coretax", "KITAS", "OSS perizinan", "pajak Indonesia", "visa Bali", "PT PMA", "KBLI 2025". Note which terms are rising.

STEP 2 — Search Google for breaking news:
Search: "Indonesia business regulation site:hukumonline.com OR site:ddtcnews.com OR site:bisnis.com last 7 days". Extract the top 3 most urgent stories.

STEP 3 — Cross-reference with this intel from today:
{intel_articles}

STEP 4 — Pick ONE topic. Rules:
- Must directly affect foreign investors or expats in Bali (visa, tax, permits, property ownership)
- Must have a rising trend signal OR a hard deadline in the next 30 days
- Must have a non-obvious "second consequence" (not just the headline)
- Formulate as a strategic angle, NOT a news headline

GOOD: "Coretax Deadline: The Gap Nobody Warned You About"
GOOD: "New KBLI Rules Are Quietly Voiding Existing PT PMAs"
BAD: "Indonesia Coretax update" (too generic)
BAD: "Bali visa news" (too vague)

Output ONLY this JSON — no other text, no explanation:
{{
  "topic": "strategic angle max 65 chars",
  "angle": "the second-order consequence nobody is covering (1 sentence)",
  "why": "timing/urgency — why this week specifically (1 sentence)",
  "trend_signal": "exact trend data you found (rising/stable/breakout + search volume if available)",
  "source_articles": ["article title 1", "article title 2", "article title 3"]
}}"""


def run_gemini(prompt: str, timeout: int = 180) -> str:
    """Call Gemini CLI — has native Google Search + Trends access."""
    result = subprocess.run(
        [GEMINI_BIN, "-p", prompt],
        capture_output=True, text=True, timeout=timeout
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    raise RuntimeError(f"Gemini error (rc={result.returncode}): {result.stderr[:200]}")


def run_qwen_fallback(articles: list, topic_hint: str = "") -> dict:
    """Fallback: Qwen local — analisi senza Google Trends."""
    import urllib.request, urllib.error

    titles = [a.get("title", "") for a in articles[:10]]
    categories = list(set(a.get("category", "") for a in articles if a.get("category")))

    # Trova topic dominante per frequenza categoria
    from collections import Counter
    cat_counts = Counter(a.get("category", "OTHER") for a in articles)
    dominant_cat = cat_counts.most_common(1)[0][0] if cat_counts else "GENERAL"

    # Trova articolo con score più alto nella categoria dominante
    top_articles = [a for a in articles if a.get("category") == dominant_cat]
    top_articles.sort(key=lambda x: x.get("qwen_score", 0), reverse=True)
    best = top_articles[0] if top_articles else (articles[0] if articles else {})

    topic = topic_hint or best.get("title", "Indonesia Business Intelligence")[:60]

    prompt = f"""You are an editor for Bali Zero, targeting foreign investors in Bali.

Top articles this week (category: {dominant_cat}):
{json.dumps([a.get('title','') for a in top_articles[:5]], ensure_ascii=False)}

Reformulate the dominant topic as a strategic carousel angle for foreign investors.
Output ONLY JSON: {{"topic": "...", "angle": "...", "why": "...", "trend_signal": "no trends data", "source_articles": [...]}}"""

    for model in ["qwen3.5:9b", "gemma3:12b"]:
        try:
            payload = json.dumps({
                "model": model, "prompt": prompt, "stream": False,
                "options": {"temperature": 0.3, "num_predict": 400}
            }).encode()
            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=payload, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                resp = json.loads(r.read())
                text = resp.get("response", "").strip()
                # Extract JSON
                if "{" in text:
                    start, end = text.find("{"), text.rfind("}") + 1
                    return json.loads(text[start:end])
        except Exception:
            continue

    # Hard fallback
    return {
        "topic": topic,
        "angle": f"Key regulatory implications of {dominant_cat} for foreign investors",
        "why": "Most covered topic in today's Indonesian business news",
        "trend_signal": "no trends data",
        "source_articles": titles[:3]
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--intel",   required=True,  help="Path a intel_output_latest.json")
    parser.add_argument("--output",  required=True,  help="Path output selected_topic.json")
    parser.add_argument("--hint",    default="",     help="Topic hint opzionale (override parziale)")
    args = parser.parse_args()

    intel_path = Path(args.intel)
    if not intel_path.exists():
        print(f"❌ Intel file not found: {intel_path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(intel_path.read_text())
    articles = [a for a in data.get("articles", []) if a.get("enrichment")]
    if not articles:
        articles = data.get("articles", [])

    if not articles:
        print("❌ No articles in intel file", file=sys.stderr)
        sys.exit(1)

    # Top 15 per score
    articles.sort(key=lambda a: a.get("qwen_score", 0), reverse=True)
    top15 = articles[:15]

    print(f"🎯 Topic Selector — {len(top15)} articles analized", file=sys.stderr)

    # Build intel summary for Gemini
    intel_summary = []
    for a in top15:
        enrich = a.get("enrichment", {})
        brief = enrich.get("executive_brief") or enrich.get("the_facts") or ""
        intel_summary.append({
            "title":    a.get("title", ""),
            "category": a.get("category") or a.get("qwen_category", ""),
            "score":    a.get("qwen_score", 0),
            "brief":    str(brief)[:200],
            "source":   a.get("url", "")[:80],
        })

    intel_str = json.dumps(intel_summary, ensure_ascii=False, indent=2)
    prompt = TOPIC_SELECTOR_PROMPT.replace("{intel_articles}", intel_str)
    if args.hint:
        prompt += f"\n\nUSER HINT: The user suggests focusing on: {args.hint}"

    result = None

    # Try Gemini (has Google Trends access)
    print("🔍 Querying Gemini + Google Trends...", file=sys.stderr)
    try:
        response = run_gemini(prompt, timeout=180)

        # Extract JSON
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "{" in response:
            start, end = response.find("{"), response.rfind("}") + 1
            response = response[start:end]

        result = json.loads(response)
        print(f"✅ Gemini selected topic: {result.get('topic')}", file=sys.stderr)
        print(f"   Trend signal: {result.get('trend_signal', 'N/A')}", file=sys.stderr)

    except subprocess.TimeoutExpired:
        print("⚠️  Gemini timeout — usando Qwen fallback", file=sys.stderr)
    except RuntimeError as e:
        print(f"⚠️  Gemini unavailable: {e} — usando Qwen fallback", file=sys.stderr)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"⚠️  Gemini JSON invalido: {e} — usando Qwen fallback", file=sys.stderr)

    if not result:
        print("🔄 Qwen local fallback (no trends)...", file=sys.stderr)
        result = run_qwen_fallback(top15, args.hint)
        print(f"✅ Qwen selected topic: {result.get('topic')}", file=sys.stderr)

    # Add metadata
    result["selected_at"] = datetime.now().isoformat()
    result["articles_analyzed"] = len(top15)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"✅ Topic → {args.output}", file=sys.stderr)

    # Print topic to stdout per pipeline.sh
    print(result["topic"])


if __name__ == "__main__":
    main()
