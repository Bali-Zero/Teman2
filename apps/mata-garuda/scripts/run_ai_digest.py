#!/usr/bin/env python3
"""
Mata Garuda — AI Intel Digest Runner.

Reads REAL data from KB + Redis, synthesizes via Claude CLI (one call),
publishes to garuda:digest, sends TG alert.

This is the operational script — it bypasses the MetaChain loop
(which can't do function calling with claude --print) and calls
tools directly in Python.

Usage:
    cd ~/Desktop/nuzantara/apps/mata-garuda
    source .venv/bin/activate
    python scripts/run_ai_digest.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mata_garuda.runtime.knowledge import KnowledgeBase
from mata_garuda.tools.stream_tools import stream_publish, stream_read
from mata_garuda.config import TG_ZERO_CHAT_ID, NLM_NOTEBOOKS


def query_nlm(question: str) -> str:
    """Query NLM AI Research notebook for synthesis. Returns empty on failure."""
    nb_id = NLM_NOTEBOOKS.get("ai_research", "")
    if not nb_id:
        return ""
    try:
        result = subprocess.run(
            ["nlm", "notebook", "query", nb_id, "--question", question],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception as e:
        print(f"  [NLM] Query failed: {e}")
    return ""


def get_kb_data(kb: KnowledgeBase) -> dict:
    """Gather all real data from KB + NLM."""
    data = {
        "scored_items": kb.get_by_type("scored_item", limit=20),
        "harvested_arxiv": kb.search("arxiv", limit=10),
        "harvested_github": kb.search("github", limit=10),
        "harvested_rss": kb.search("rss", limit=10),
        "harvested_youtube": kb.search("youtube", limit=5),
        "nlm_synthesis": "",
    }
    # Filter out hash entries
    for key in data:
        if isinstance(data[key], list):
            data[key] = [
                item for item in data[key]
                if item.get("type") != "hash" and len(item.get("content", "")) > 30
            ]

    # Ask NLM for cross-source synthesis (if notebook has sources)
    nlm_result = query_nlm(
        "What are the most important AI research trends from the latest sources? "
        "Focus on: RAG improvements, agent architectures, knowledge graphs, "
        "and anything relevant to production AI systems. Be specific with paper names."
    )
    if nlm_result:
        data["nlm_synthesis"] = nlm_result

    return data


def build_synthesis_prompt(data: dict) -> str:
    """Build a prompt with ALL real data for Claude to synthesize."""
    sections = []

    if data["scored_items"]:
        sections.append("## SCORED ITEMS (highest priority)")
        for item in data["scored_items"]:
            sections.append(f"- {item['content'][:300]}")
            sections.append(f"  URL: {item.get('source', 'N/A')}")

    if data["harvested_arxiv"]:
        sections.append("\n## ARXIV PAPERS")
        for item in data["harvested_arxiv"]:
            sections.append(f"- {item['content'][:300]}")
            sections.append(f"  URL: {item.get('source', 'N/A')}")

    if data["harvested_github"]:
        sections.append("\n## GITHUB REPOS")
        for item in data["harvested_github"]:
            sections.append(f"- {item['content'][:200]}")
            sections.append(f"  URL: {item.get('source', 'N/A')}")

    if data["harvested_rss"]:
        sections.append("\n## RSS NEWSLETTERS")
        for item in data["harvested_rss"]:
            sections.append(f"- {item['content'][:200]}")
            sections.append(f"  URL: {item.get('source', 'N/A')}")

    if data["harvested_youtube"]:
        sections.append("\n## YOUTUBE VIDEOS")
        for item in data["harvested_youtube"]:
            sections.append(f"- {item['content'][:200]}")
            sections.append(f"  URL: {item.get('source', 'N/A')}")

    if data.get("nlm_synthesis"):
        sections.append("\n## NLM CROSS-SOURCE SYNTHESIS (from 600-source brain)")
        sections.append(data["nlm_synthesis"][:1000])

    raw_data = "\n".join(sections)
    total = sum(len(v) for v in data.values() if isinstance(v, list))

    if total == 0:
        return ""

    return f"""Sei l'analista AI di Mata Garuda. Questi sono i DATI REALI raccolti oggi da arXiv, GitHub, YouTube e newsletter RSS.

DATI ({total} item totali):

{raw_data}

COMPITO:
Produci un digest di ESATTAMENTE 5 bullet point in italiano.
Per ogni bullet:
- Un tag: [SIGNAL] (importante), [CODE] (applicabile al nostro stack RAG/KG/Agent), [WATCH] (da monitorare), [TREND] (pattern emergente)
- Il TITOLO ESATTO del paper/repo/video (copialo dai dati sopra)
- UNA frase di insight: cosa significa per noi?
- L'URL ESATTO (copialo dai dati sopra)

REGOLE ASSOLUTE:
- USA SOLO titoli e URL presenti nei dati sopra
- NON inventare NESSUN paper, repo o link
- Seleziona i 5 più rilevanti per uno stack AI (RAG ibrido, Knowledge Graph 108k nodi, agenti self-evolving, business services Indonesia)
- Se meno di 5 item rilevanti, metti meno bullet

Formato:
🔬 AI INTEL DIGEST — {datetime.now().strftime('%d %b %Y')}

1. [TAG] Titolo — insight
   → URL

Output SOLO il digest, niente altro."""


def call_claude_synthesis(prompt: str) -> str:
    """Call Claude CLI for synthesis. Uses multi-account fallback."""
    token_vars = [
        "CLAUDE_CODE_OAUTH_TOKEN_1",
        "CLAUDE_CODE_OAUTH_TOKEN_2",
        "CLAUDE_CODE_OAUTH_TOKEN_3",
    ]

    for var in token_vars:
        token = os.environ.get(var)
        if not token:
            continue

        env = os.environ.copy()
        env["CLAUDE_CODE_OAUTH_TOKEN"] = token

        try:
            result = subprocess.run(
                ["claude", "--print", "-p", prompt],
                capture_output=True, text=True, timeout=120, env=env,
            )
            if result.returncode == 0 and result.stdout.strip():
                output = result.stdout.strip()
                # Strip [Pro]/[Air] prefix if present
                if output.startswith("[Pro]") or output.startswith("[Air]"):
                    output = output.split("\n", 1)[-1].strip()
                return output
            if "hit your limit" in (result.stderr + result.stdout).lower():
                print(f"  [{var}] rate limited, trying next...")
                continue
        except subprocess.TimeoutExpired:
            print(f"  [{var}] timeout, trying next...")
            continue

    return ""


def send_telegram(message: str) -> bool:
    """Send TG alert to Zero."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("  [TG] TELEGRAM_BOT_TOKEN not set")
        return False

    try:
        result = subprocess.run(
            [
                "curl", "-s",
                f"https://api.telegram.org/bot{token}/sendMessage",
                "-d", f"chat_id={TG_ZERO_CHAT_ID}",
                "--data-urlencode", f"text={message}",
            ],
            capture_output=True, text=True, timeout=15,
        )
        if '"ok":true' in result.stdout:
            msg_id = json.loads(result.stdout).get("result", {}).get("message_id", "?")
            print(f"  [TG] Sent (msg_id: {msg_id})")
            return True
        print(f"  [TG] Failed: {result.stdout[:200]}")
    except Exception as e:
        print(f"  [TG] Error: {e}")
    return False


def main():
    print(f"=== AI Intel Digest — {datetime.now().strftime('%Y-%m-%d %H:%M')} ===\n")

    # 1. Gather data from KB
    print("[1] Reading KB...")
    kb = KnowledgeBase()
    data = get_kb_data(kb)
    total = sum(len(v) for v in data.values())
    print(f"    Found: {len(data['scored_items'])} scored, "
          f"{len(data['harvested_arxiv'])} arxiv, "
          f"{len(data['harvested_github'])} github, "
          f"{len(data['harvested_rss'])} rss, "
          f"{len(data['harvested_youtube'])} youtube "
          f"= {total} total")

    if total == 0:
        print("    No data. Sending quiet day digest.")
        digest = (
            f"🔬 AI INTEL DIGEST — {datetime.now().strftime('%d %b %Y')}\n\n"
            "📭 Giornata silenziosa — nessun item raccolto oggi.\n"
            "Pipeline harvesting non ha prodotto dati.\n\n"
            "Mata Garuda AI-Intel-Sentinel"
        )
        stream_publish(
            title=f"AI Intel Digest — {datetime.now().strftime('%Y-%m-%d')} (quiet)",
            url="garuda:digest", source="ai_digest", content=digest,
            stream="garuda:digest",
        )
        send_telegram(digest)
        kb.close()
        return

    # 2. Build synthesis prompt
    print("[2] Building synthesis prompt...")
    prompt = build_synthesis_prompt(data)
    print(f"    Prompt: {len(prompt)} chars, {total} real items")

    # 3. Call Claude for synthesis
    print("[3] Claude synthesis...")
    digest = call_claude_synthesis(prompt)

    if not digest:
        print("    Claude failed. Building fallback digest from raw data.")
        # Fallback: just list the top 5 items
        items = data["scored_items"] + data["harvested_arxiv"][:3] + data["harvested_github"][:2]
        lines = [f"🔬 AI INTEL DIGEST — {datetime.now().strftime('%d %b %Y')}\n"]
        for i, item in enumerate(items[:5], 1):
            title = item["content"].split("\n")[0][:80]
            url = item.get("source", "N/A")
            lines.append(f"{i}. {title}\n   → {url}")
        lines.append("\nMata Garuda AI-Intel-Sentinel (fallback — Claude non disponibile)")
        digest = "\n".join(lines)

    print(f"    Digest: {len(digest)} chars")
    print()
    print(digest)
    print()

    # 4. Publish to garuda:digest
    print("[4] Publishing to garuda:digest...")
    result = stream_publish(
        title=f"AI Intel Digest — {datetime.now().strftime('%Y-%m-%d')}",
        url="garuda:digest", source="ai_digest", content=digest,
        stream="garuda:digest",
    )
    print(f"    {result}")

    # 5. Send Telegram
    print("[5] Sending Telegram...")
    send_telegram(digest)

    # 6. Store in KB
    print("[6] Saving to KB...")
    kb.store("ai_digest_agent", "digest", digest, "daily_run", 0.9)
    print(f"    KB stats: {kb.stats()}")
    kb.close()

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
