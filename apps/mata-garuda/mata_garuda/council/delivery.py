"""
Consiglio v1 — Telegram delivery.

Formats council decisions and sends to Zero via Telegram Bot API.
Uses subprocess curl (not httpx/requests) per mata-garuda constraints.
Pattern: bridge/nerve.py _default_http_post().
"""
from __future__ import annotations

import json
import logging
import os
import subprocess

from mata_garuda.config import TG_BOT_TOKEN_ENV, TG_ZERO_CHAT_ID
from mata_garuda.council.models import CouncilDecision

logger = logging.getLogger("mata_garuda.council.delivery")


def format_telegram_report(decision: CouncilDecision) -> str:
    """Format a council decision for Telegram display."""
    short_id = decision.id[:8]
    consensus = decision.consensus

    # Header
    lines = [f"CONSIGLIO #{short_id}: {decision.topic.title}"]
    lines.append("")

    # Consensus
    if consensus:
        lines.append(f"Consensus: {consensus.score:.2f} ({consensus.method})")
        gt = "YES" if consensus.groupthink_detected else "No"
        lines.append(f"Groupthink: {gt}")
    else:
        lines.append("Consensus: N/A (abstain)")

    # Agents
    responded = [v for v in decision.votes if v.success]
    failed = [v for v in decision.votes if not v.success]
    agent_names = ", ".join(v.agent_name for v in responded)
    lines.append(f"Agents: {agent_names} ({len(responded)}/{len(decision.votes)} responded)")
    if failed:
        failed_names = ", ".join(v.agent_name for v in failed)
        lines.append(f"Failed: {failed_names}")
    lines.append("")

    # Agent positions (brief)
    for v in responded:
        conf = f"{v.confidence:.1f}" if v.confidence else "?"
        pos = v.position[:120] + "..." if len(v.position) > 120 else v.position
        lines.append(f"  {v.agent_name} (conf {conf}): {pos}")
    lines.append("")

    # Synthesis
    lines.append("SYNTHESIS:")
    lines.append(decision.synthesis or "(none)")
    lines.append("")

    # Dissents
    if decision.dissents:
        lines.append(f"DISSENT ({len(decision.dissents)}):")
        for d in decision.dissents:
            pos = d.position[:100] + "..." if len(d.position) > 100 else d.position
            lines.append(f"  - {d.agent_name} (divergence {d.divergence_score:.2f}): {pos}")
        lines.append("")

    # Action items
    if decision.action_items:
        lines.append("ACTION ITEMS:")
        for i, item in enumerate(decision.action_items, 1):
            lines.append(f"  {i}. {item}")
        lines.append("")

    # Status
    if decision.requires_zero_approval:
        lines.append(f"Status: PENDING APPROVAL")
        lines.append(f"Reason: {decision.escalation_reason}")
    else:
        lines.append(f"Status: {decision.status.upper()}")

    return "\n".join(lines)


def send_to_zero(
    decision: CouncilDecision,
    chat_id: str = TG_ZERO_CHAT_ID,
) -> bool:
    """Send council decision to Zero via Telegram Bot API.

    Returns True on success, False on failure.
    """
    token = os.environ.get(TG_BOT_TOKEN_ENV, "")
    if not token:
        logger.warning(f"[delivery] {TG_BOT_TOKEN_ENV} not set, skipping Telegram")
        return False

    text = format_telegram_report(decision)

    # Truncate if too long for Telegram (4096 char limit)
    if len(text) > 4000:
        text = text[:3997] + "..."

    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML" if "<" in text else None,
    })

    try:
        result = subprocess.run(
            [
                "curl", "-sS",
                "--max-time", "15",
                "-X", "POST",
                f"https://api.telegram.org/bot{token}/sendMessage",
                "-H", "Content-Type: application/json",
                "-d", payload,
            ],
            capture_output=True, text=True,
            timeout=20,
        )
        if result.returncode != 0:
            logger.error(f"[delivery] curl failed: {result.stderr[:200]}")
            return False

        response = json.loads(result.stdout)
        if response.get("ok"):
            logger.info(f"[delivery] sent to Zero (chat={chat_id})")
            return True
        else:
            logger.error(f"[delivery] Telegram API error: {response.get('description', '?')}")
            return False

    except Exception as e:
        logger.error(f"[delivery] send failed: {e}")
        return False
