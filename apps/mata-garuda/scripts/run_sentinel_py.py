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
from mata_garuda.workers.heartbeat import emit_heartbeat
from mata_garuda.config import AI_RSS_FEEDS, AI_YOUTUBE_CHANNELS

# Organ id matches organs_registry.yaml `mata_garuda.sentinel_daily.mini`
# (com.matagaruda.sentinel.daily on Mini — live ProgramArguments invoke THIS
# file). A prior instrumentation pass (PR #2090) wired emit_heartbeat into
# run_sentinel_cell.py under this same organ_id, but that script is what
# Pro's separate hourly cron (com.matagaruda.sentinel.hourly) invokes — an
# unverified assumption ("this script is the Mini daily cron target") that
# never held. The Mini daily cron kept writing no sidecar at all, so the
# healer receptor flagged this organ never_armed indefinitely. Wired here
# 2026-07-08 (healer tick, PENDING-ARMS ledger-overdue).
ORGAN_ID = "mata_garuda.sentinel_daily.mini"


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


def main() -> int:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
    print(f"\n=== AI-Intel-Sentinel — {ts} ===")

    # 1. Harvest
    print("\n[HARVEST]")
    counts = harvest()
    total = sum(v for k, v in counts.items() if k != "errors")
    print(f"  Total: {total} items ({counts})")

    if total == 0:
        print("  No items harvested. Exiting.")
        emit_heartbeat(ORGAN_ID, "ok", metadata={"harvested": counts, "normalized": 0, "scored": 0})
        return 0

    # 2. Normalize + Score + NLM Feed
    print("\n[PROCESS]")
    kb = KnowledgeBase()
    n_stats = run_normalizer(kb, max_items=50)
    print(f"  Normalizer: {n_stats}")
    s_stats = run_scorer(kb, max_items=50)
    print(f"  Scorer: {s_stats}")

    # NLM feeding is a SEPARATE Sink stage, handled by the dedicated cron
    # com.matagaruda.nlm-feeder-stream.hourly (reads the stream every hour).
    # It was inline here, but run_nlm_feeder (KB-scan → `nlm` CLI / headless
    # Chrome) HANGS under launchd (no TTY) and got SIGKILL'd (-9), which
    # silently stalled the WHOLE harvester for days. Decoupled 2026-06-30.
    kb.close()

    # Digest/briefing is a SEPARATE Sink, handled by the dedicated crons
    # com.matagaruda.daily-briefing + com.matagaruda.weekly-digest. It was
    # inline here, but run_ai_digest calls `nlm notebook query` (headless
    # Chrome) which ALSO hangs under launchd. Decoupled 2026-06-30.

    print(f"\n=== Sentinel complete ({total} harvested, "
          f"{n_stats['published']} normalized, {s_stats['stored']} scored) ===")

    # Heartbeat at real completion, carrying the actual run counts — not
    # just a process-start ping (same convention as run_intel_bridge.py).
    emit_heartbeat(
        ORGAN_ID,
        "ok",
        metadata={
            "harvested": total,
            "normalized": n_stats.get("published", 0),
            "scored": s_stats.get("stored", 0),
        },
    )
    return 0


def _cli_entrypoint(main_fn) -> int:
    """Run `main_fn()`, emitting a fail heartbeat only on a genuine exception.

    Catching `Exception` (not `BaseException`) means a `sys.exit()` inside
    `main_fn` would propagate untouched instead of being caught and
    relabeled as a failure — the exact class of bug fixed in run_normalizer.py
    / run_intel_bridge.py (2026-07-07, PR #2107). `main` here never calls
    `sys.exit()` itself, but the guard is applied from the start to avoid
    reintroducing that bug later.
    """
    try:
        return main_fn()
    except Exception as exc:  # noqa: BLE001 — heartbeat then re-raise
        emit_heartbeat(ORGAN_ID, "fail", metadata={"error": f"{type(exc).__name__}: {exc}"})
        raise


if __name__ == "__main__":
    sys.exit(_cli_entrypoint(main))
