"""
Mata Garuda — NLM Expander Agent (L2 autonomy).

Weekly scan. If a domain has been producing >50 enriched items over the
last 30 days but isn't mapped to an NLM notebook in
`config.NLM_DOMAIN_ROUTING`, propose to Zero (via Telegram) that a new
NB-INTEL-{X} be created. Also flags mapped notebooks that appear stale
(no fed entries in KB for 30+ days).

CRITICAL: L2 autonomy — this agent PROPOSES, does NOT create. A human
(Zero) decides via Telegram reply.

Layer 4 Analista.
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from mata_garuda.agents.daily_briefing_agent import _send_telegram, _xrevrange
from mata_garuda.config import NLM_DOMAIN_ROUTING, NLM_NOTEBOOKS, STREAM_ENRICHED
from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.runtime.knowledge import KnowledgeBase
from mata_garuda.tools.knowledge_tools import kb_search, kb_store
from mata_garuda.tools.tg_tools import send_tg_alert
from mata_garuda.types import Agent

logger = logging.getLogger("mata_garuda.agents.nlm_expander")

GENOME_FILE = str(Path(__file__).parent / "nlm_expander_agent_GENOME.md")

DEFAULT_PROPOSAL_THRESHOLD = 50  # items in 30d → proposal-worthy
DEFAULT_STALE_DAYS = 30           # NB unused for this many days → stale flag


def _parse_ts(data: dict[str, str]) -> datetime | None:
    for key in ("normalized_at", "timestamp", "alert_time", "created_at"):
        v = data.get(key)
        if not v:
            continue
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            continue
    return None


def count_domains_last_30d(
    items: list[dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, int]:
    """Count enriched items per domain over the last 30 days."""
    now = now or datetime.now(timezone.utc)
    horizon = now - timedelta(days=30)
    counts: Counter[str] = Counter()
    for it in items:
        data = it.get("data") or {}
        ts = _parse_ts(data)
        if ts is not None and ts < horizon:
            continue
        domain = (data.get("domain") or data.get("topic") or "").strip()
        if domain:
            counts[domain] += 1
    return dict(counts)


def find_proposal_candidates(
    counts: dict[str, int],
    threshold: int = DEFAULT_PROPOSAL_THRESHOLD,
) -> list[tuple[str, int]]:
    """Return (domain, count) pairs where count>=threshold AND domain is
    NOT already mapped in NLM_DOMAIN_ROUTING.
    """
    candidates = []
    for domain, n in counts.items():
        if n < threshold:
            continue
        if domain in NLM_DOMAIN_ROUTING:
            continue
        candidates.append((domain, n))
    # Highest volume first
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates


def find_stale_notebooks(
    kb: KnowledgeBase,
    now: datetime | None = None,
    stale_days: int = DEFAULT_STALE_DAYS,
) -> list[str]:
    """Return nb_key names whose `nlm_fed` KB entries have no activity in
    the last ``stale_days``. Ignores notebooks with empty IDs."""
    now = now or datetime.now(timezone.utc)
    horizon = now - timedelta(days=stale_days)
    stale: list[str] = []

    try:
        cursor = kb._conn.execute(
            "SELECT MAX(created_at) FROM knowledge "
            "WHERE agent = 'nlm_feeder' AND type = 'nlm_fed'"
        )
        row = cursor.fetchone()
    except Exception:
        return []

    # If there's NEVER been a fed entry, every configured NB is stale
    last_fed = None
    if row and row[0]:
        try:
            last_fed = datetime.fromisoformat(str(row[0]).replace(" ", "T"))
            if last_fed.tzinfo is None:
                last_fed = last_fed.replace(tzinfo=timezone.utc)
        except Exception:
            last_fed = None

    for nb_key, nb_id in NLM_NOTEBOOKS.items():
        if not nb_id:
            continue
        if last_fed is None or last_fed < horizon:
            stale.append(nb_key)
    return stale


def build_proposal_message(
    candidates: list[tuple[str, int]],
    stale: list[str],
    now: datetime | None = None,
) -> str:
    now = now or datetime.now(timezone.utc)
    lines = [
        f"🧭 NLM EXPANDER — {now.strftime('%Y-%m-%d')}",
        "",
    ]
    if candidates:
        lines.append("**Propongo nuovi notebook:**")
        for domain, n in candidates:
            lines.append(f"• `{domain}` — {n} item/30gg (non mappato)")
        lines.append("")
        lines.append("Rispondi `y <domain>` per approvare la creazione, `n <domain>` per ignorare.")
    if stale:
        lines.append("")
        lines.append(f"**NB stali (>{DEFAULT_STALE_DAYS}gg senza feed):** {', '.join(stale)}")
    if not candidates and not stale:
        lines.append("Niente da proporre — coverage stabile, feed attivo.")
    lines.append("")
    lines.append("_L2 autonomy: solo proposte. Non creo NB senza tua approvazione._")
    return "\n".join(lines)


def run_nlm_expander(
    kb: KnowledgeBase | None = None,
    *,
    now: datetime | None = None,
    dry_run: bool = False,
    max_stream_items: int = 2000,
    proposal_threshold: int = DEFAULT_PROPOSAL_THRESHOLD,
) -> dict:
    """Scan enriched stream for unmapped high-volume domains and stale NBs.

    Returns stats: {counts, candidates, stale, tg_ok, dry_run}.
    Never creates notebooks (L2 autonomy — Zero decides).
    """
    now = now or datetime.now(timezone.utc)
    own_kb = False
    if kb is None:
        kb = KnowledgeBase()
        own_kb = True

    try:
        items = _xrevrange(STREAM_ENRICHED, count=max_stream_items)
        counts = count_domains_last_30d(items, now=now)
        candidates = find_proposal_candidates(counts, threshold=proposal_threshold)
        stale = find_stale_notebooks(kb, now=now)

        should_send = bool(candidates or stale)
        tg_ok = True
        if should_send:
            msg = build_proposal_message(candidates, stale, now=now)
            tg_ok = _send_telegram(msg, dry_run=dry_run)
            if not dry_run:
                try:
                    kb.store(
                        "nlm_expander_agent", "proposal",
                        msg[:4000], "weekly_scan", 0.7,
                    )
                except Exception as e:
                    logger.warning(f"[nlm_expander] kb.store failed: {e}")

        return {
            "domains_seen": len(counts),
            "candidates": [{"domain": d, "count": n} for d, n in candidates],
            "stale": stale,
            "tg_ok": tg_ok,
            "dry_run": dry_run,
            "sent": should_send,
        }
    finally:
        if own_kb:
            try:
                kb.close()
            except Exception:
                pass


@register_agent(name="NLM Expander Agent (L2)", func_name="get_nlm_expander_agent")
def get_nlm_expander_agent(model: str = "claude") -> Agent:
    def instructions(context_variables: dict) -> str:  # pragma: no cover
        return (
            "You are the NLM Expander Agent (L2 autonomy) for Mata Garuda. "
            "Weekly, scan the enriched stream for domains with >50 items/30d "
            "that aren't already mapped in NLM_DOMAIN_ROUTING, and flag "
            "notebooks that haven't been fed in 30+ days. PROPOSE to Zero "
            "via Telegram — DO NOT create notebooks autonomously. Zero "
            "approves by TG reply."
        )

    return Agent(
        name="NLM Expander Agent (L2)",
        model=model,
        instructions=instructions,
        functions=[
            kb_search, kb_store,
            send_tg_alert, case_resolved, case_not_resolved,
        ],
        genome_path=GENOME_FILE,
        layer="analista",
    )
