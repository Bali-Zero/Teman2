"""
Mata Garuda — WR Topic Agent (Layer 4 Analista).

Wed/Sat morning agent: scans garuda:enriched last-3-days, selects top-5
business-relevant items (score >= 4, business domains), proposes 5
carousel topic ideas for War Room 2.0.

Output: Markdown list sent to Zero via Telegram + stored in SQLite KB
as `wr_topic_agent:suggestion` entries for WR2 consumption.

Layer: 4 (Analista). Autonomy: L2 (propose only, never auto-create
content in WR2).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from mata_garuda.agents.daily_briefing_agent import _send_telegram, _xrevrange
from mata_garuda.config import RELEVANCE_WEIGHTS, STREAM_ENRICHED
from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.runtime.knowledge import KnowledgeBase
from mata_garuda.types import Agent

logger = logging.getLogger("mata_garuda.agents.wr_topic")

GENOME_FILE = str(Path(__file__).parent / "wr_topic_agent_GENOME.md")

BUSINESS_DOMAINS = {
    "immigration_visa",
    "tax_fiscal",
    "investment_licensing",
    "labor_manpower",
    "property",
}

MIN_SCORE = 4.0
LOOKBACK_DAYS = 3
TOP_N = 5


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.split("+", 1)[0].rstrip("Z")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _score(row: dict) -> float:
    raw = row.get("score")
    try:
        return float(raw)
    except (TypeError, ValueError):
        pass
    return float(RELEVANCE_WEIGHTS.get(row.get("domain", ""), 0))


def _filter_candidates(
    rows: list[dict], *, now: datetime, lookback_days: int = LOOKBACK_DAYS,
) -> list[dict]:
    cutoff = now - timedelta(days=lookback_days)
    out = []
    for r in rows:
        ts = _parse_dt(r.get("timestamp") or r.get("normalized_at"))
        if ts is None or ts < cutoff:
            continue
        domain = (r.get("domain") or r.get("topic") or "").strip()
        if domain not in BUSINESS_DOMAINS:
            continue
        if _score(r) < MIN_SCORE:
            continue
        out.append(r)
    out.sort(key=_score, reverse=True)
    return out[:TOP_N]


def format_suggestions(rows: list[dict], now: datetime) -> str:
    """Markdown block: 5 WR carousel ideas with title/domain/score/URL."""
    if not rows:
        return (
            f"📋 **WR Topic Suggestions — {now.strftime('%a %d %b')}**\n\n"
            "📭 Nessun item business-critical negli ultimi 3 giorni. "
            "Prossimo run Mer/Sab."
        )

    lines = [f"📋 **WR Topic Suggestions — {now.strftime('%a %d %b %Y')}**", ""]
    for i, r in enumerate(rows, 1):
        title = (r.get("title") or "").strip()[:180]
        domain = (r.get("domain") or r.get("topic") or "n/a").strip()
        score = _score(r)
        url = (r.get("url") or "").strip()
        lines.append(f"{i}. **[{domain} | {score:.1f}]** {title}")
        if url:
            lines.append(f"   → {url}")
        reason = (r.get("reason") or "").strip()
        if reason:
            lines.append(f"   _Perché_: {reason[:180]}")
        lines.append("")
    lines.append(
        "🎨 WR2 può trasformare ognuno in carousel IG / thread X / post LI / "
        "blog / newsletter."
    )
    return "\n".join(lines)


def run_wr_topic_agent(
    kb: KnowledgeBase | None = None,
    *,
    now: datetime | None = None,
    dry_run: bool = False,
    max_stream_items: int = 500,
) -> dict:
    """Generate WR topic suggestions. Returns stats."""
    now = now or datetime.now(timezone.utc)
    own_kb = False
    if kb is None:
        kb = KnowledgeBase()
        own_kb = True

    try:
        raw = _xrevrange(STREAM_ENRICHED, count=max_stream_items)
        candidates = _filter_candidates(raw, now=now)
        body = format_suggestions(candidates, now)
        tg_ok = _send_telegram(body, dry_run=dry_run)

        if not dry_run and candidates:
            for c in candidates:
                try:
                    kb.store(
                        "wr_topic_agent", "wr_topic_suggestion",
                        json.dumps({
                            "title": c.get("title", "")[:300],
                            "url": c.get("url", ""),
                            "domain": c.get("domain") or c.get("topic"),
                            "score": _score(c),
                            "reason": c.get("reason", "")[:300],
                            "suggested_at": now.isoformat(timespec="seconds"),
                        }, ensure_ascii=False),
                        c.get("url", ""),
                        0.8,
                    )
                except Exception as e:
                    logger.warning(f"[wr_topic] kb.store failed: {e}")

        return {
            "candidates": len(candidates),
            "chars": len(body),
            "tg_ok": tg_ok,
            "dry_run": dry_run,
        }
    finally:
        if own_kb:
            kb.close()


# Register in Lamarckian agent registry
@register_agent(name="wr_topic_agent", func_name="get_wr_topic_agent")
def get_wr_topic_agent(model: str = "claude") -> Agent:
    """Layer 4 Analista agent — propose WR carousel topics Wed/Sat."""

    def instructions(context_variables: dict) -> str:
        return """You are the WR Topic Agent for Mata Garuda.

Every Wed/Sat you scan the last 3 days of garuda:enriched for
business-critical items (score>=4, domains: immigration/tax/investment/
labor/property), pick top 5, and send Markdown suggestions to Zero.

Do NOT create WR2 content directly. You are L2 autonomy: propose only.

Call run_wr_topic_agent(), then case_resolved with the candidate count
in take_away_message.
"""

    return Agent(
        name="wr_topic_agent",
        model=model,
        instructions=instructions,
        functions=[run_wr_topic_agent, case_resolved, case_not_resolved],
        tool_choice=None,
        parallel_tool_calls=False,
        genome_path=GENOME_FILE,
        layer="analista",
    )
