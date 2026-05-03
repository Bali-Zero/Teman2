#!/usr/bin/env python3
"""
Mata Garuda — AI-Intel-Sentinel cell pulse.

Single Python script for LaunchAgent cron.
Runs one pulse of the SentinelCell (sense→think→act→reflect→dream→mature).

Pipeline steps:
  1. Harvest all sources → garuda:raw
  2. Normalize + Score → garuda:enriched + KB
  3. Digest (Claude synthesis) → garuda:digest + TG alert

Designed for TCC-safe execution via venv python.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mata_garuda.tools.arxiv_tools import _parse_arxiv_atom
from mata_garuda.tools.stream_tools import stream_publish
from mata_garuda.tools.feed_tools import fetch_rss_feed
from mata_garuda.tools.github_tools import fetch_github_trending
from mata_garuda.tools.youtube_tools import fetch_youtube_transcript
from mata_garuda.runtime.knowledge import KnowledgeBase
from mata_garuda.workers.normalizer import run_normalizer
from mata_garuda.workers.scorer import run_scorer
from mata_garuda.workers.nlm_feeder import run_nlm_feeder
from mata_garuda.config import AI_RSS_FEEDS, AI_YOUTUBE_CHANNELS


def harvest() -> dict:
    """Harvest all sources → garuda:raw. Returns counts."""
    counts = {"arxiv": 0, "rss": 0, "github": 0, "youtube": 0, "errors": 0}

    # ArXiv
    try:
        url = (
            "http://export.arxiv.org/api/query?"
            "search_query=cat:cs.AI+OR+cat:cs.CL+OR+cat:cs.LG+OR+cat:cs.IR"
            "&sortBy=submittedDate&sortOrder=descending&max_results=15"
        )
        r = subprocess.run(
            ["curl", "-sL", url, "--connect-timeout", "15"],
            capture_output=True, text=True, timeout=25,
        )
        for p in _parse_arxiv_atom(r.stdout):
            stream_publish(
                title=p["title"][:200], url=p["url"],
                source="arxiv", content=p["abstract"][:500],
            )
            counts["arxiv"] += 1
    except Exception as e:
        print(f"  [arxiv] Error: {e}")
        counts["errors"] += 1

    # RSS
    for feed_url in AI_RSS_FEEDS:
        try:
            r = fetch_rss_feed(feed_url, max_items=5)
            for line in r.split("\n"):
                if "URL: http" in line:
                    u = line.strip().replace("URL: ", "")
                    t = r.split(u)[0].split("\n")[-2].strip()
                    stream_publish(title=t[:200], url=u, source="rss", content="newsletter")
                    counts["rss"] += 1
        except Exception:
            counts["errors"] += 1

    # GitHub
    try:
        r = fetch_github_trending(topics="machine-learning", max_results=10, days=1)
        for line in r.split("\n"):
            if line.strip().startswith("URL: https://github.com"):
                u = line.strip().replace("URL: ", "")
                t = r.split(u)[0].split("\n")[-2].strip()
                stream_publish(title=t[:200], url=u, source="github", content="trending repo")
                counts["github"] += 1
    except Exception:
        counts["errors"] += 1

    # YouTube (top 3 channels)
    for channel in AI_YOUTUBE_CHANNELS[:3]:
        try:
            r = fetch_youtube_transcript(f"@{channel}", max_videos=2)
            for line in r.split("\n"):
                if "URL: https://www.youtube.com" in line:
                    u = line.strip().replace("URL: ", "")
                    t = r.split(u)[0].split("\n")[-2].strip()
                    stream_publish(title=t[:200], url=u, source="youtube", content="video")
                    counts["youtube"] += 1
        except Exception:
            counts["errors"] += 1

    return counts


def main():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
    print(f"\n=== AI-Intel-Sentinel — {ts} ===")

    # 1. Harvest
    print("\n[HARVEST]")
    counts = harvest()
    total = sum(v for k, v in counts.items() if k != "errors")
    print(f"  Total: {total} items ({counts})")

    if total == 0:
        print("  No items harvested. Exiting.")
        return

    # 2. Normalize + Score + NLM Feed
    print("\n[PROCESS]")
    kb = KnowledgeBase()
    n_stats = run_normalizer(kb, max_items=50)
    print(f"  Normalizer: {n_stats}")
    s_stats = run_scorer(kb, max_items=50)
    print(f"  Scorer: {s_stats}")

    # 3. Feed to NLM (grows the brain over time)
    print("\n[NLM FEED]")
    nlm_stats = run_nlm_feeder(kb, max_items=30)
    print(f"  NLM Feeder: {nlm_stats}")
    kb.close()

    # 3. Digest
    print("\n[DIGEST]")
    # Import here to avoid circular issues
    from scripts.run_ai_digest import main as run_digest
    run_digest()

    print(f"\n=== Sentinel complete ({total} harvested, "
          f"{n_stats['published']} normalized, {s_stats['stored']} scored) ===")


if __name__ == "__main__":
    main()
