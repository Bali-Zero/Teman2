#!/usr/bin/env python3
"""
FASE 1 — NotebookLM Deep Research (NB-7: Editorial & Content Strategy)
Queries NB-7 for content strategy intelligence: audience insights, SEO angles,
narrative hooks, pain points, competitor gaps — specific to the war room topic.

NB-7 is the right notebook for War Room because it knows:
- Audience personas (expats, investors, digital nomads) and their search intent
- SEO/GEO angles that perform for Indonesian business content
- Narrative hooks and content formats that drive engagement
- Competitor content gaps on the topic

Usage:
    python 11_nlm_researcher.py --topic "Property for foreigners Bali" --output output/raw/nlm_dump.json
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

NB7_NOTEBOOK_ID = "f51ab8a0-50d0-49f1-a64f-ebc131fed7b8"
NLM_CLI = os.environ.get("NLM_CLI_PATH", "nlm")
QUERY_TIMEOUT = 90  # seconds per query


def log(msg: str, level: str = "INFO"):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [NLM] [{level}] {msg}", file=sys.stderr, flush=True)


def nlm_query(notebook_id: str, query: str, conversation_id: Optional[str] = None) -> dict:
    cmd = [NLM_CLI, "query", "notebook", notebook_id, query, "--timeout", str(QUERY_TIMEOUT)]
    if conversation_id:
        cmd.extend(["--conversation-id", conversation_id])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=QUERY_TIMEOUT + 30)
        if result.returncode != 0:
            return {"status": "error", "error": result.stderr.strip() or f"exit {result.returncode}"}

        output = result.stdout.strip()
        if not output:
            return {"status": "error", "error": "empty response"}

        data = json.loads(output)
        if "value" in data and isinstance(data["value"], dict):
            data = data["value"]

        return {
            "status": data.get("status", "success"),
            "answer": data.get("answer", ""),
            "sources_used": data.get("sources_used", []),
            "conversation_id": data.get("conversation_id", conversation_id),
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": f"timeout after {QUERY_TIMEOUT}s"}
    except json.JSONDecodeError as e:
        return {"status": "error", "error": f"json parse: {e}"}
    except FileNotFoundError:
        return {"status": "error", "error": "nlm CLI not found"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_nlm_available() -> bool:
    try:
        r = subprocess.run([NLM_CLI, "--version"], capture_output=True, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def extract_facts_from_answer(answer: str, query_type: str, topic: str) -> list:
    """Parse NLM's narrative answer into structured facts for war room pipeline."""
    if not answer or len(answer) < 50:
        return []

    facts = []
    # Split on bullet/numbered list patterns or double newlines
    import re
    segments = re.split(r'\n\s*[\*\-•]\s+|\n\s*\d+\.\s+|\n\n+', answer)
    segments = [s.strip() for s in segments if len(s.strip()) > 40]

    for seg in segments[:8]:  # max 8 facts per query
        # First sentence as title
        first_sent = re.split(r'\.|\!|\?', seg)[0].strip()
        title = first_sent[:80] if first_sent else seg[:60]
        facts.append({
            "title": title,
            "brief": seg[:300],
            "category": query_type,
            "source": f"NLM NB-7 ({query_type})",
            "published": "",
            "relevance": "high",
            "from_nlm": True,
        })

    return facts


def main():
    parser = argparse.ArgumentParser(description="NLM NB-7 Deep Research for War Room")
    parser.add_argument("--topic", required=True, help="Research topic")
    parser.add_argument("--output", required=True, help="Output JSON path")
    args = parser.parse_args()

    if not check_nlm_available():
        log("nlm CLI not available — skipping NLM research", "WARN")
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps({"facts": [], "error": "nlm_unavailable"}, indent=2))
        sys.exit(0)  # non-fatal: pipeline continues

    log(f"NB-7 research: '{args.topic}'")
    t0 = time.time()

    all_facts = []
    raw_responses = []
    conv_id = None

    # Q1 — Audience & pain points
    q1 = (
        f"For the topic '{args.topic}': what are the main pain points, fears, and questions "
        f"that foreign investors and expats in Bali have? What search intent drives them to research this? "
        f"Include any specific audience segments (nationalities, investor types, digital nomads)."
    )
    log("Q1: audience & pain points")
    r1 = nlm_query(NB7_NOTEBOOK_ID, q1, conv_id)
    if r1.get("status") != "error":
        conv_id = r1.get("conversation_id")
        facts1 = extract_facts_from_answer(r1.get("answer", ""), "audience_insights", args.topic)
        all_facts.extend(facts1)
        raw_responses.append({"query": "audience", "answer": r1.get("answer", ""), "facts": len(facts1)})
        log(f"Q1 done — {len(facts1)} facts, conv_id={conv_id}")
    else:
        log(f"Q1 failed: {r1.get('error')}", "WARN")

    # Q2 — Content angles & hooks (continues in same conversation)
    q2 = (
        f"For '{args.topic}': what narrative angles and hooks would make a LinkedIn/Instagram carousel "
        f"perform well with this audience? What is the asymmetric angle — the thing most people miss? "
        f"What competing content exists and what gap can we exploit?"
    )
    log("Q2: content angles & hooks")
    r2 = nlm_query(NB7_NOTEBOOK_ID, q2, conv_id)
    if r2.get("status") != "error":
        conv_id = r2.get("conversation_id")
        facts2 = extract_facts_from_answer(r2.get("answer", ""), "content_strategy", args.topic)
        all_facts.extend(facts2)
        raw_responses.append({"query": "angles", "answer": r2.get("answer", ""), "facts": len(facts2)})
        log(f"Q2 done — {len(facts2)} facts")
    else:
        log(f"Q2 failed: {r2.get('error')}", "WARN")

    elapsed = round(time.time() - t0, 1)

    output = {
        "topic": args.topic,
        "scraped_at": datetime.now().isoformat(),
        "source": "NotebookLM NB-7 (Editorial & Content Strategy)",
        "notebook_id": NB7_NOTEBOOK_ID,
        "facts": all_facts,
        "raw_responses": raw_responses,
        "count": len(all_facts),
        "stats": {
            "facts_count": len(all_facts),
            "queries_run": len(raw_responses),
            "elapsed_seconds": elapsed,
        },
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2))

    log(f"Done in {elapsed}s — {len(all_facts)} facts from {len(raw_responses)} NLM queries")
    log(f"Output: {args.output}")


if __name__ == "__main__":
    main()
