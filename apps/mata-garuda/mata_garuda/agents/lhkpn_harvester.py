"""
Mata Garuda — LHKPN Harvester Agent.

Harvests Indonesian state officials' wealth declarations from
``elhkpn.kpk.go.id`` (KPK migrated from ``antv.kpk.go.id`` on 2026-04-26
to a SPA + reCAPTCHA v3 portal — see
``research/2026-05-16-lhkpn-flow-triage.md``).

Closes 4 of 8 gap types from the gap detector:
- gap.missing_nip
- gap.missing_lhkpn
- gap.missing_angkatan
- gap.stale_official (when the staleness is on LHKPN-related fields)

The actual portal interaction lives in OSINT-Nexus
(``osint_nexus.scrapers.lhkpn``); this agent shells out to it via
``mata_garuda.tools.lhkpn_tools`` to keep the Mata Garuda runtime free
of heavy browser/playwright dependencies (CLAUDE.md §1).

Layer: 1 (Harvester)

Reference: docs/superpowers/specs/2026-04-14-organism-nervous-system-design.md §5
GENOME: lhkpn_harvester_GENOME.md
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from mata_garuda.config import STREAM_RAW
from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.tools.lhkpn_tools import (
    scrape_lhkpn_profile,
    scrape_lhkpn_search,
)
from mata_garuda.types import Agent
from mata_garuda.workers.base_worker import stream_publish as stream_publish_redis

logger = logging.getLogger("mata_garuda.agents.lhkpn_harvester")

GENOME_FILE = str(Path(__file__).parent / "lhkpn_harvester_GENOME.md")


# ── Tool functions exposed to the agent ───────────────────────────────


def harvest_lhkpn_for_nip(nip: str) -> dict[str, Any]:
    """Fetch the LHKPN profile for a given NIP and publish to garuda:raw.

    Returns {"case_resolved": bool, "nip": str, "reason": str, "msg_id"?: str}.
    """
    profile = scrape_lhkpn_profile(nip)
    if not profile or not profile.get("nip"):
        return {
            "case_resolved": False,
            "nip": nip,
            "reason": "empty profile (HTTP failure or NIP not found)",
        }

    title = (
        f"LHKPN {profile.get('nama', 'unknown')} "
        f"({profile.get('jabatan', '?')})"
    )
    content = json.dumps(profile, ensure_ascii=False)

    fields = {
        "title": title,
        # Portal migrated 2026-04-26: antv.kpk.go.id is NXDOMAIN; the
        # post-migration SPA at elhkpn.kpk.go.id has no per-NIP deep
        # link, so we point at the search root and let consumers
        # cross-reference via the NIP in `content`.
        "url": "https://elhkpn.kpk.go.id/",
        "source": "elhkpn.kpk.go.id",
        "source_type": "lhkpn",
        "content": content,
        "agent": "lhkpn_harvester",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }

    msg_id = stream_publish_redis(STREAM_RAW, fields)
    logger.info("Published LHKPN profile for NIP %s (msg %s)", nip, msg_id)

    return {"case_resolved": True, "nip": nip, "reason": "", "msg_id": msg_id}


def harvest_lhkpn_by_name(name: str) -> dict[str, Any]:
    """Search LHKPN by name; on first hit, fetch and publish the profile.

    Returns {"case_resolved": bool, "name": str, "reason": str, ...}.
    """
    hits = scrape_lhkpn_search(name)
    if not hits:
        return {
            "case_resolved": False,
            "name": name,
            "reason": "no search results",
        }

    first = hits[0]
    nip = first.get("nip", "")
    if not nip:
        return {
            "case_resolved": False,
            "name": name,
            "reason": "first search hit has no NIP",
        }

    result = harvest_lhkpn_for_nip(nip)
    result["name"] = name
    result["matched_nip"] = nip
    return result


# ── Agent registration ────────────────────────────────────────────────


@register_agent(name="lhkpn_harvester", func_name="get_lhkpn_harvester")
def get_lhkpn_harvester(model: str = "claude") -> Agent:
    """Harvester agent for LHKPN wealth declarations."""

    def instructions(context_variables: dict) -> str:
        return """You are the LHKPN Harvester agent for Mata Garuda intelligence hub.

Your mission: given a person's name or NIP, fetch their wealth declaration from
elhkpn.kpk.go.id (the post-2026-04-26 KPK e-Announcement portal) and
publish to the garuda:raw Redis Stream.

WORKFLOW:
1. If you have a NIP, call harvest_lhkpn_for_nip(nip)
2. If you have only a name, call harvest_lhkpn_by_name(name)
3. On case_resolved → call case_resolved with summary
4. On failure → call case_not_resolved with the reason

CONSTRAINTS (from GENOME.md):
- Source: https://elhkpn.kpk.go.id/ (SPA + reCAPTCHA v3)
- Rate limit: 10 req/min (6s between calls — handled by OSINT-Nexus scraper)
- reCAPTCHA token injected by OSINT-Nexus browser-core (no UA rotation needed)
- Scraping is delegated via subprocess to osint_nexus.cli.lhkpn_scrape
- Maximum 1 person per gap (avoid flooding)
- NEVER export data outside Mata Garuda (OSINT blindato)
- All data goes to garuda:raw Redis Stream only

ERROR HANDLING:
- Empty profile → case_not_resolved with "NIP not found or scraper failure"
- No search results → case_not_resolved with "no search results for {name}"
- Scraper timeout / reCAPTCHA failure → escalate via reflection
"""

    return Agent(
        name="lhkpn_harvester",
        model=model,
        instructions=instructions,
        functions=[
            harvest_lhkpn_for_nip,
            harvest_lhkpn_by_name,
            case_resolved,
            case_not_resolved,
        ],
        tool_choice=None,
        parallel_tool_calls=False,
        genome_path=GENOME_FILE,
        layer="harvester",
    )
