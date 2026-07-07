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
import re
import unicodedata
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


def _normalise_name(value: str) -> str:
    """Return an ASCII-ish lowercase token string for conservative matching."""
    ascii_value = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    return re.sub(r"[^a-z0-9]+", " ", ascii_value).strip()


def _names_match(expected: str, found: str) -> bool:
    """Conservative name match for portal rows."""
    expected_norm = _normalise_name(expected)
    found_norm = _normalise_name(found)
    if not expected_norm or not found_norm:
        return False
    return (
        expected_norm == found_norm
        or expected_norm in found_norm
        or found_norm in expected_norm
    )


def _publish_lhkpn_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Publish a normalised LHKPN profile to garuda:raw."""
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
    logger.info("Published LHKPN profile for NIP %s (msg %s)", profile.get("nip"), msg_id)

    return {
        "case_resolved": True,
        "nip": profile.get("nip", ""),
        "reason": "",
        "msg_id": msg_id,
    }


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

    return _publish_lhkpn_profile(profile)


def harvest_lhkpn_by_name(name: str) -> dict[str, Any]:
    """Search LHKPN by name; on first hit, fetch and publish the profile.

    Returns {"case_resolved": bool, "name": str, "reason": str, ...}.
    """
    return harvest_lhkpn_for_person(name=name, nip="")


def harvest_lhkpn_for_person(name: str, nip: str = "") -> dict[str, Any]:
    """Search LHKPN by name and publish the best exact-name hit.

    The current KPK portal does not search by NIP, but legacy OSINT gaps often
    carry both ``entity_name`` and ``entity_nip``. Use the name to query the
    portal, then attach the already-known NIP to the normalised profile.
    """
    clean_name = name.strip()
    clean_nip = nip.strip()
    if not clean_name:
        if clean_nip:
            return harvest_lhkpn_for_nip(clean_nip)
        return {"case_resolved": False, "name": name, "reason": "missing name and NIP"}

    hits = scrape_lhkpn_search(clean_name)
    if not hits:
        return {
            "case_resolved": False,
            "name": clean_name,
            "reason": "no search results",
        }

    matching_hits = [hit for hit in hits if _names_match(clean_name, hit.get("nama", ""))]
    if not matching_hits:
        return {
            "case_resolved": False,
            "name": clean_name,
            "reason": "no exact name match",
        }

    first = matching_hits[0]
    matched_nip = first.get("nip", "").strip()
    if not clean_nip and matched_nip:
        result = harvest_lhkpn_for_nip(matched_nip)
        result["name"] = clean_name
        result["matched_nip"] = matched_nip
        return result
    if not clean_nip:
        return {
            "case_resolved": False,
            "name": clean_name,
            "reason": "matched declaration has no NIP; provide entity_nip",
        }

    raw = first.get("_raw") or {}
    profile = {
        "nama": first.get("nama", ""),
        "nip": clean_nip,
        "jabatan": first.get("jabatan", ""),
        "angkatan": "",
        "total_harta_idr": int(raw.get("total_harta", 0) or 0),
        "properties_count": 0,
        "vehicles_count": 0,
        "accounts_count": 0,
        "_raw": {
            "tahun_data": raw.get("tahun_data", first.get("report_year", "")),
            "lembaga": raw.get("lembaga", ""),
            "unit_kerja": raw.get("unit_kerja", ""),
            "tanggal_lapor": raw.get("tanggal_lapor", ""),
            "jenis_laporan": raw.get("jenis_laporan", ""),
            "data_id": raw.get("data_id", ""),
            "pdf_path": raw.get("pdf_path", ""),
        },
    }

    result = _publish_lhkpn_profile(profile)
    result["name"] = clean_name
    result["matched_nip"] = clean_nip
    return result


# ── Agent registration ────────────────────────────────────────────────


@register_agent(name="lhkpn_harvester", func_name="get_lhkpn_harvester")
def get_lhkpn_harvester(model: str = "ollama:qwen3.5:9b") -> Agent:
    """Harvester agent for LHKPN wealth declarations."""

    def instructions(context_variables: dict) -> str:
        return """You are the LHKPN Harvester agent for Mata Garuda intelligence hub.

Your mission: given a person's name or NIP, fetch their wealth declaration from
elhkpn.kpk.go.id (the post-2026-04-26 KPK e-Announcement portal) and
publish to the garuda:raw Redis Stream.

WORKFLOW:
1. If you have both a name and NIP, call harvest_lhkpn_for_person(name, nip)
2. If you have only a NIP, call harvest_lhkpn_for_nip(nip)
3. If you have only a name, call harvest_lhkpn_by_name(name)
4. On case_resolved → call case_resolved with summary
5. On failure → call case_not_resolved with the reason

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
            harvest_lhkpn_for_person,
            case_resolved,
            case_not_resolved,
        ],
        tool_choice=None,
        parallel_tool_calls=False,
        genome_path=GENOME_FILE,
        layer="harvester",
    )
