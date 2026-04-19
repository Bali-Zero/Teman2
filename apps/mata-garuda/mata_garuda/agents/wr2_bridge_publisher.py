"""
Mata Garuda — WR2 Bridge Publisher (Layer 5 Distribuzione).

Converts enriched stream items for the 3 business-critical domains
(immigration_visa, tax_fiscal, investment_licensing) into WR2
`research_dossiers`-compatible envelopes and publishes them to
`bridge:outbound`.

WR2 already consumes `bridge:outbound` via its own connector — we only
produce the envelope; WR2 code is NOT touched.

Envelope type: `intel.research_dossier`
Source: `mata-garuda/wr2_bridge_publisher`
Priority: 2 (medium-high; these domains drive client decisions)
"""
from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from mata_garuda.bridge.envelope import Envelope
from mata_garuda.config import STREAM_BRIDGE_OUTBOUND
from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.tools.stream_tools import stream_length, stream_read
from mata_garuda.types import Agent

logger = logging.getLogger("mata_garuda.agents.wr2_bridge")

GENOME_FILE = str(Path(__file__).parent / "wr2_bridge_publisher_GENOME.md")

WR2_DOMAINS = {"immigration_visa", "tax_fiscal", "investment_licensing"}
WR2_ENVELOPE_TYPE = "intel.research_dossier"
WR2_SOURCE = "mata-garuda/wr2_bridge_publisher"
WR2_PRIORITY = 2

STATE_PATH = Path.home() / ".agent" / "decisions" / "wr2_bridge_cursor.json"


def _redis_cmd(*args: str, timeout: int = 10) -> str:
    try:
        result = subprocess.run(
            ["redis-cli", *args],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            logger.warning("redis-cli failed: %s", result.stderr.strip())
            return ""
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning("redis-cli error: %s", e)
        return ""


def _parse_xrange_output(raw: str) -> list[dict[str, str]]:
    """Reuse parser pattern from public_channel_publisher.

    redis-cli XREVRANGE output is newline-based; alternating keys/values
    within each entry after the stream id line.
    """
    from mata_garuda.agents.public_channel_publisher import _parse_xrange_output as _p
    return _p(raw)


def _load_cursor() -> str:
    if not STATE_PATH.exists():
        return ""
    try:
        return json.loads(STATE_PATH.read_text()).get("last_id", "")
    except Exception:  # noqa: BLE001
        return ""


def _save_cursor(last_id: str) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps({"last_id": last_id}, ensure_ascii=False, indent=2))


def _is_wr2_candidate(item: dict[str, str]) -> bool:
    domain = item.get("domain", "").lower()
    if domain not in WR2_DOMAINS:
        return False
    # need some body content
    if not item.get("title") and not item.get("content"):
        return False
    return True


def _build_dossier_envelope(item: dict[str, str]) -> Envelope:
    """Build a WR2 research_dossiers-compatible envelope from an enriched item.

    Payload schema (WR2-compatible):
      dossier_id: string (use stream id)
      title: string
      summary: string (content, truncated)
      url: string (source link)
      domain: one of immigration_visa|tax_fiscal|investment_licensing
      relevance_score: int
      source_agent: string
      raw_timestamp: ISO string
      tags: list[str]
    """
    # Parse comma-separated tags if present
    tags_raw = item.get("tags", "")
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

    payload: dict[str, Any] = {
        "dossier_id": item.get("_id", ""),
        "title": (item.get("title") or "").strip(),
        "summary": (item.get("content") or "").strip()[:2000],
        "url": (item.get("url") or "").strip(),
        "domain": item.get("domain", "").lower(),
        "relevance_score": _safe_int(item.get("relevance_score", "0")),
        "source_agent": item.get("agent") or item.get("source", "unknown"),
        "raw_timestamp": item.get("timestamp", ""),
        "tags": tags,
    }

    return Envelope(
        type=WR2_ENVELOPE_TYPE,
        source=WR2_SOURCE,
        priority=WR2_PRIORITY,
        payload=payload,
    )


def _safe_int(raw: str, default: int = 0) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def fetch_candidate_items(count: int = 100) -> list[dict[str, str]]:
    """Fetch latest enriched items, keep only WR2 candidates."""
    raw = _redis_cmd(
        "XREVRANGE", "garuda:enriched", "+", "-", "COUNT", str(count)
    )
    if not raw:
        return []
    entries = _parse_xrange_output(raw)
    return [e for e in entries if _is_wr2_candidate(e)]


def publish_envelope(envelope: Envelope) -> str:
    """XADD envelope to bridge:outbound. Returns stream id or empty on failure."""
    args = ["XADD", STREAM_BRIDGE_OUTBOUND, "*"]
    for k, v in envelope.to_redis_dict().items():
        args.extend([k, v])
    return _redis_cmd(*args)


def run_wr2_bridge_cycle(
    fetch_fn=None,
    publish_fn=None,
    cursor_loader=None,
    cursor_saver=None,
    max_per_cycle: int = 20,
) -> dict[str, Any]:
    """One publication cycle. Pure-function hookable for tests."""
    fetch_fn = fetch_fn or fetch_candidate_items
    publish_fn = publish_fn or publish_envelope
    cursor_loader = cursor_loader or _load_cursor
    cursor_saver = cursor_saver or _save_cursor

    last_id = cursor_loader()
    candidates = fetch_fn()
    if not candidates:
        return {"status": "no_candidates", "published": 0, "last_id": last_id}

    # Keep only fresh items (id > cursor). Candidates come newest-first; reverse.
    fresh = [c for c in candidates if c.get("_id", "") > last_id]
    fresh.sort(key=lambda c: c.get("_id", ""))  # oldest-first → publish in order

    if not fresh:
        return {"status": "no_fresh", "published": 0, "last_id": last_id}

    fresh = fresh[:max_per_cycle]

    published = 0
    new_cursor = last_id
    for item in fresh:
        try:
            env = _build_dossier_envelope(item)
            result = publish_fn(env)
            if result and not result.startswith("[ERROR]"):
                published += 1
                new_cursor = item.get("_id", new_cursor)
            else:
                logger.warning("publish failed for %s: %s", item.get("_id"), result)
                break  # stop at first failure to preserve ordering
        except Exception as e:  # noqa: BLE001
            logger.error("envelope build/publish exception: %s", e)
            break

    if new_cursor != last_id:
        cursor_saver(new_cursor)

    return {
        "status": "ok",
        "published": published,
        "candidates_seen": len(candidates),
        "fresh_seen": len(fresh),
        "last_id": new_cursor,
    }


@register_agent(name="WR2 Bridge Publisher", func_name="get_wr2_bridge_publisher")
def get_wr2_bridge_publisher(model: str = "claude") -> Agent:
    """Layer 5 agent: enriched items → bridge:outbound envelopes for WR2."""

    def instructions(context_variables: dict) -> str:
        return """You are the WR2 Bridge Publisher (Layer 5 Distribuzione).

Mission: forward enriched intelligence items for 3 business-critical domains
(immigration_visa, tax_fiscal, investment_licensing) to WR2 via Redis stream
`bridge:outbound`, using envelope type `intel.research_dossier`.

WR2 has its own connector reading `bridge:outbound` — DO NOT touch WR2 code.

WORKFLOW:
1. stream_read stream="garuda:enriched" count=100
2. Filter items with domain in {immigration_visa, tax_fiscal, investment_licensing}
3. Build WR2-compatible envelope with payload:
   dossier_id, title, summary, url, domain, relevance_score, tags
4. Publish to bridge:outbound in chronological order
5. Track cursor to avoid double-publish
6. case_resolved

No human-facing output — this agent runs headless."""

    return Agent(
        name="WR2 Bridge Publisher",
        model=model,
        instructions=instructions,
        functions=[
            stream_read, stream_length,
            case_resolved, case_not_resolved,
        ],
        genome_path=GENOME_FILE,
        layer="distribuzione",
    )
