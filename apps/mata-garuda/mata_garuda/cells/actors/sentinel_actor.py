"""SentinelActor — executes the full publish cycle.

1. Stores ALL items in KB
2. Feeds URLs to NLM notebook
3. Generates complete Markdown report
4. Queries NLM for cross-source synthesis
5. Sends TG digest
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from cell_core.types import Proposal, SensorReading

from mata_garuda.config import NLM_NOTEBOOKS, TG_ZERO_CHAT_ID
from mata_garuda.runtime.knowledge import KnowledgeBase

logger = logging.getLogger("mata_garuda.cells")

REPORTS_DIR = Path(__file__).parent.parent.parent.parent / "data" / "reports"


class SentinelActor:
    """Publishes harvested items: KB + NLM + report + TG."""

    def __init__(self, kb: KnowledgeBase, thinker: Any = None):
        self._kb = kb
        self._thinker = thinker
        self._readings: list[SensorReading] = []

    def set_readings(self, readings: list[SensorReading]) -> None:
        """Set readings from current pulse (called by PulseLoop before act)."""
        self._readings = readings

    def can_execute(self, action_name: str) -> bool:
        return action_name in ("publish_all", "none")

    async def act(self, proposal: Proposal) -> str:
        if proposal.action == "none":
            return "no_action"

        items = self._thinker.get_deduped_items(self._readings) if self._thinker else []
        if not items:
            return "no_items"

        # 1. Store ALL in KB
        for item in items:
            self._kb.store(
                agent=f"sentinel:{item['sensor']}",
                entry_type="harvested_item",
                content=f"[{item['source']}] {item['title']}\n{item['content']}",
                source=item["url"],
                confidence=0.5,
            )

        # 2. Feed URLs to NLM
        nlm_fed = self._feed_nlm(items)

        # 3. Generate complete Markdown report
        report_path = self._write_report(items)

        # 4. Query NLM for synthesis (if notebook has enough sources)
        nlm_synthesis = self._query_nlm_synthesis()

        # 5. Send TG digest
        tg_sent = self._send_tg(items, nlm_synthesis)

        result = (
            f"Published {len(items)} items: "
            f"KB={len(items)}, NLM={nlm_fed}, "
            f"report={report_path}, TG={'sent' if tg_sent else 'skipped'}"
        )
        logger.info(f"[sentinel_actor] {result}")
        return result

    def _feed_nlm(self, items: list[dict]) -> int:
        """Feed URLs to NLM notebook. Returns count fed."""
        nb_id = NLM_NOTEBOOKS.get("ai_research", "")
        if not nb_id:
            return 0

        fed = 0
        for item in items:
            url = item.get("url", "")
            if not url.startswith("http"):
                continue
            try:
                result = subprocess.run(
                    ["nlm", "source", "add", nb_id, "--url", url],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode == 0:
                    fed += 1
            except Exception:
                pass
        return fed

    def _write_report(self, items: list[dict]) -> str:
        """Write complete Markdown report with ALL items."""
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        path = REPORTS_DIR / f"sentinel_{date_str}.md"

        # Group by sensor/source
        by_source: dict[str, list[dict]] = {}
        for item in items:
            key = item["sensor"]
            by_source.setdefault(key, []).append(item)

        lines = [
            f"# AI-Intel-Sentinel Report — {date_str}",
            f"\n**Total: {len(items)} items** | Generated: {datetime.now().strftime('%H:%M %Z')}",
            "",
        ]

        for source, source_items in by_source.items():
            lines.append(f"\n## {source.upper()} ({len(source_items)} items)\n")
            for i, item in enumerate(source_items, 1):
                lines.append(f"### {i}. {item['title'][:120]}")
                lines.append(f"- **URL:** {item['url']}")
                lines.append(f"- **Source:** {item['source']}")
                if item.get("content"):
                    lines.append(f"- **Content:** {item['content'][:300]}")
                lines.append("")

        report_text = "\n".join(lines)
        path.write_text(report_text)
        logger.info(f"[sentinel_actor] Report: {path} ({len(report_text)} chars)")
        return str(path)

    def _query_nlm_synthesis(self) -> str:
        """Query NLM for cross-source synthesis."""
        nb_id = NLM_NOTEBOOKS.get("ai_research", "")
        if not nb_id:
            return ""
        try:
            result = subprocess.run(
                [
                    "nlm", "notebook", "query", nb_id,
                    "--question",
                    "Based on all sources in this notebook, what are the emerging patterns "
                    "and cross-connections between different AI research papers, repos, and articles? "
                    "Focus on: RAG improvements, agent architectures, knowledge graphs, "
                    "self-improving systems. Be specific with titles and connections.",
                ],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception as e:
            logger.warning(f"[sentinel_actor] NLM synthesis failed: {e}")
        return ""

    def _send_tg(self, items: list[dict], nlm_synthesis: str) -> bool:
        """Send TG digest to Zero."""
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not token:
            logger.warning("[sentinel_actor] TELEGRAM_BOT_TOKEN not set")
            return False

        date_str = datetime.now().strftime("%d %b %Y")
        # Count by source
        by_source: dict[str, int] = {}
        for item in items:
            by_source[item["sensor"]] = by_source.get(item["sensor"], 0) + 1

        source_summary = " | ".join(f"{k}:{v}" for k, v in by_source.items())

        lines = [
            f"AI INTEL SENTINEL — {date_str}",
            f"\n{len(items)} items raccolti ({source_summary})",
            "",
        ]

        # Top items per source (max 3 each)
        for source, count in by_source.items():
            source_items = [i for i in items if i["sensor"] == source][:3]
            lines.append(f"\n{source.upper()}:")
            for item in source_items:
                lines.append(f"  {item['title'][:70]}")
                lines.append(f"  {item['url']}")

        if nlm_synthesis:
            lines.append(f"\nNLM SYNTHESIS:\n{nlm_synthesis[:500]}")

        lines.append(f"\nReport completo: data/reports/sentinel_{datetime.now().strftime('%Y-%m-%d')}.md")

        message = "\n".join(lines)

        try:
            result = subprocess.run(
                [
                    "curl", "-s",
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    "-d", f"chat_id={TG_ZERO_CHAT_ID}",
                    "--data-urlencode", f"text={message}",
                ],
                capture_output=True, text=True, timeout=15,
            )
            if '"ok":true' in result.stdout:
                return True
        except Exception as e:
            logger.warning(f"[sentinel_actor] TG failed: {e}")
        return False
