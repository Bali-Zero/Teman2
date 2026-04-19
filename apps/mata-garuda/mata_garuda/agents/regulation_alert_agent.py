"""
Mata Garuda — Regulation Alert Agent.

Quasi-real-time (cron every 30 min) consumer of `garuda:alerts`. Forwards
actionable alerts from upstream workers (scorer, contradiction, semantic_diff)
to Zero on Telegram, ACKing each message so the stream doesn't back up.

Layer 4 Analista. Autonomy L1 (forward only).
"""
from __future__ import annotations

import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mata_garuda.config import STREAM_ALERTS, TG_ZERO_CHAT_ID
from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.runtime.knowledge import KnowledgeBase
from mata_garuda.tools.knowledge_tools import kb_search, kb_store
from mata_garuda.tools.tg_tools import send_tg_alert
from mata_garuda.types import Agent
from mata_garuda.workers.base_worker import stream_ack, stream_read_new

logger = logging.getLogger("mata_garuda.agents.regulation_alert")

GENOME_FILE = str(Path(__file__).parent / "regulation_alert_agent_GENOME.md")

CONSUMER_GROUP = "reg_alert"
CONSUMER_NAME = "reg_alert-1"


# ── formatting ────────────────────────────────────────────────────────────


def format_alert(data: dict[str, Any]) -> str:
    """Render one alert as a short TG message."""
    title = (data.get("title") or "(senza titolo)").strip()[:200]
    domain = (data.get("topic") or data.get("domain") or "unknown").strip()
    source = (data.get("source") or "").strip()
    url = (data.get("url") or "").strip()
    score = data.get("score") or data.get("weighted_score") or "?"
    reason = (data.get("reason") or data.get("motivo") or "").strip()
    kind = (data.get("alert_kind") or data.get("kind") or "alert").strip()

    lines = [
        f"🚨 REG ALERT — {kind}",
        f"*{title}*",
        f"Domain: {domain}  ·  Score: {score}",
    ]
    if reason:
        lines.append(f"Why: {reason[:300]}")
    if source:
        lines.append(f"Source: {source}")
    if url:
        lines.append(url)
    return "\n".join(lines)


# ── TG send ───────────────────────────────────────────────────────────────


def _send_telegram(text: str, dry_run: bool = False) -> bool:
    if dry_run:
        logger.info(f"[DRY-RUN] would send TG ({len(text)} chars)")
        return True
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("[reg_alert] TELEGRAM_BOT_TOKEN not set")
        return False
    try:
        result = subprocess.run(
            [
                "curl", "-s",
                f"https://api.telegram.org/bot{token}/sendMessage",
                "-d", f"chat_id={TG_ZERO_CHAT_ID}",
                "--data-urlencode", f"text={text}",
            ],
            capture_output=True, text=True, timeout=15,
        )
        return '"ok":true' in (result.stdout or "")
    except Exception as e:
        logger.error(f"[reg_alert] TG send exception: {e}")
        return False


# ── operational entrypoint ────────────────────────────────────────────────


def run_regulation_alert(
    kb: KnowledgeBase | None = None,
    *,
    max_items: int = 20,
    dry_run: bool = False,
) -> dict:
    """Drain new alerts from `garuda:alerts` and forward each to Zero.

    Returns stats: {processed, sent, failed}.
    """
    stats = {"processed": 0, "sent": 0, "failed": 0}
    own_kb = False
    if kb is None:
        kb = KnowledgeBase()
        own_kb = True

    try:
        items = stream_read_new(
            STREAM_ALERTS, CONSUMER_GROUP, CONSUMER_NAME, count=max_items,
        )
        if not items:
            logger.info("[reg_alert] No new items in garuda:alerts")
            return stats

        for item in items:
            stats["processed"] += 1
            msg_id = item["id"]
            data = item.get("data") or {}

            msg = format_alert(data)
            ok = _send_telegram(msg, dry_run=dry_run)

            if ok:
                stats["sent"] += 1
                try:
                    kb.store(
                        "regulation_alert_agent", "alert_forwarded",
                        f"{data.get('title','')[:80]} | {data.get('topic','')}",
                        data.get("url", ""), 0.8,
                    )
                except Exception as e:
                    logger.warning(f"[reg_alert] kb.store failed: {e}")
            else:
                stats["failed"] += 1
                try:
                    kb.store(
                        "regulation_alert_agent", "case_not_resolved",
                        f"tg_send_failed | {data.get('title','')[:80]}",
                        data.get("url", ""), 0.3,
                    )
                except Exception:
                    pass

            # ACK regardless: we don't want to re-send on retry (duplicate
            # TG spam is worse than a dropped alert — alerts are already
            # also in the stream + KB audit trail).
            stream_ack(STREAM_ALERTS, CONSUMER_GROUP, msg_id)

        logger.info(
            f"[reg_alert] Done at {datetime.now(timezone.utc).isoformat(timespec='seconds')}: "
            f"{stats['processed']} processed, {stats['sent']} sent, {stats['failed']} failed"
        )
        return stats
    finally:
        if own_kb:
            try:
                kb.close()
            except Exception:
                pass


# ── Agent registration ────────────────────────────────────────────────────


@register_agent(name="Regulation Alert Agent", func_name="get_regulation_alert_agent")
def get_regulation_alert_agent(model: str = "claude") -> Agent:
    """Returns the registered Agent stub. Operational work is
    ``run_regulation_alert()`` invoked from the cron script.
    """

    def instructions(context_variables: dict) -> str:  # pragma: no cover
        return (
            "You are the Regulation Alert Agent for Mata Garuda. Every 30 "
            "minutes you drain new items from garuda:alerts (populated by "
            "scorer + contradiction + semantic_diff workers) and forward "
            "each to Zero via Telegram. ACK on every message — duplicate "
            "spam is worse than a dropped alert (KB audit trail remains)."
        )

    return Agent(
        name="Regulation Alert Agent",
        model=model,
        instructions=instructions,
        functions=[
            kb_search, kb_store,
            send_tg_alert, case_resolved, case_not_resolved,
        ],
        genome_path=GENOME_FILE,
        layer="analista",
    )
