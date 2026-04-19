"""
Shared Lamarckian harvester implementation for .go.id OSINT portals.

Each concrete agent module (imigrasi/bkpm/kemlu/kemkumham) declares its
identity + URL/prefix config, then delegates the actual harvest logic
here. Keeps 4 agents consistent and testable through one contract.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from mata_garuda.config import STREAM_OSINT
from mata_garuda.tools.goid_tools import MAX_ITEMS, extract_links, fetch_goid
from mata_garuda.workers.base_worker import stream_publish as stream_publish_redis

logger = logging.getLogger("mata_garuda.agents.goid")


def harvest_goid(
    agent_name: str,
    source_domain: str,
    landing_url: str,
    allow_prefixes: list[str],
    max_items: int = MAX_ITEMS,
) -> dict[str, Any]:
    """Fetch landing_url, extract whitelisted links, publish to garuda:osint.

    Returns {"case_resolved": bool, "agent": str, "published": int,
             "reason": str}.
    """
    code, html = fetch_goid(landing_url)
    if code == 0:
        return {
            "case_resolved": False,
            "agent": agent_name,
            "published": 0,
            "reason": f"transport failure fetching {landing_url}",
        }
    if code >= 400:
        return {
            "case_resolved": False,
            "agent": agent_name,
            "published": 0,
            "reason": f"HTTP {code} from {landing_url}",
        }

    links = extract_links(html, allow_prefixes, max_items=max_items)
    if not links:
        return {
            "case_resolved": False,
            "agent": agent_name,
            "published": 0,
            "reason": f"no matching links on {landing_url} (structure drift?)",
        }

    ts = datetime.now().isoformat(timespec="seconds")
    published = 0
    failures = 0
    for item in links:
        fields = {
            "title": item["title"],
            "url": item["url"],
            "source": source_domain,
            "source_type": "osint_goid",
            "source_agent": agent_name,
            "content": "",
            "agent": agent_name,
            "timestamp": ts,
        }
        msg_id = stream_publish_redis(STREAM_OSINT, fields)
        if isinstance(msg_id, str) and not msg_id.startswith("[ERROR]"):
            published += 1
        else:
            failures += 1
            logger.warning("publish failed for %s: %s", item["url"], msg_id)

    if published == 0:
        return {
            "case_resolved": False,
            "agent": agent_name,
            "published": 0,
            "reason": f"all {failures} stream publishes failed",
        }

    return {
        "case_resolved": True,
        "agent": agent_name,
        "published": published,
        "failures": failures,
        "reason": "",
    }
