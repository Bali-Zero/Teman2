"""
Mata Garuda — Reddit listener agent.

Layer 1 (Harvester). Polls r/bali + r/indonesia new.json feeds,
filters on Indonesia-business keywords, publishes hits to garuda:raw.

GENOME: reddit_listener_agent_GENOME.md
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from mata_garuda.config import STREAM_RAW
from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.tools.reddit_tools import fetch_subreddit_new, filter_keywords
from mata_garuda.types import Agent
from mata_garuda.workers.base_worker import stream_publish as stream_publish_redis

logger = logging.getLogger("mata_garuda.agents.reddit_listener_agent")

GENOME_FILE = str(Path(__file__).parent / "reddit_listener_agent_GENOME.md")
AGENT_NAME = "reddit_listener_agent"

DEFAULT_SUBS = ["bali", "indonesia"]
DEFAULT_KEYWORDS = [
    "visa", "kitas", "pma", "immigration", "business", "company",
    "tax", "bkpm", "imigrasi", "property", "investment",
]


def run_reddit_listen(
    subs: list[str] | None = None,
    keywords: list[str] | None = None,
) -> dict[str, Any]:
    """Poll subs, keyword-filter, publish to garuda:raw."""
    subs = subs or DEFAULT_SUBS
    keywords = keywords or DEFAULT_KEYWORDS

    ts = datetime.now().isoformat(timespec="seconds")
    published = 0
    failures = 0
    last_reason = ""
    for sub in subs:
        res = fetch_subreddit_new(sub)
        if not res.get("ok"):
            failures += 1
            last_reason = res.get("reason", "unknown")
            continue
        posts = filter_keywords(res["posts"], keywords)
        for p in posts:
            url = p.get("url") or ""
            title = p.get("title") or "(untitled)"
            if not url:
                continue
            fields = {
                "title": title[:300],
                "url": url,
                "source": f"reddit.com/r/{sub}",
                "source_type": "social_reddit",
                "source_agent": AGENT_NAME,
                "content": (p.get("selftext") or "")[:500],
                "agent": AGENT_NAME,
                "timestamp": ts,
                "subreddit": p.get("subreddit", sub),
            }
            msg_id = stream_publish_redis(STREAM_RAW, fields)
            if isinstance(msg_id, str) and not msg_id.startswith("[ERROR]"):
                published += 1

    if published == 0:
        return {
            "case_resolved": False,
            "published": 0,
            "reason": last_reason or "no matching posts across subs",
        }
    return {
        "case_resolved": True,
        "published": published,
        "failures": failures,
        "reason": "",
    }


@register_agent(name=AGENT_NAME, func_name="get_reddit_listener_agent")
def get_reddit_listener_agent(model: str = "claude") -> Agent:
    def instructions(context_variables: dict) -> str:
        return """You are the Reddit Listener Agent for Mata Garuda.

Call run_reddit_listen() to poll r/bali + r/indonesia new.json and
publish keyword-matching posts to garuda:raw. No login; public JSON
only.

ERROR HANDLING:
- Reddit 429 / 403 → case_not_resolved with HTTP code
- All subs failing → case_not_resolved with last reason
"""

    return Agent(
        name=AGENT_NAME,
        model=model,
        instructions=instructions,
        functions=[run_reddit_listen, case_resolved, case_not_resolved],
        tool_choice=None,
        parallel_tool_calls=False,
        genome_path=GENOME_FILE,
        layer="harvester",
    )
