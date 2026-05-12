"""NLM Effector — feeds harvested items to NotebookLM and generates reports.

This is how the organism grows its analytical brain. Every harvest,
URLs go into NB-INTEL-AIResearch. After 30 days = 300+ sources.
NLM becomes the cross-source synthesizer that no single LLM can match.

Also generates:
- Complete Markdown report (ALL items, not a filtered summary)
- TG digest via TelegramAlerter
"""
from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("cell.effectors.nlm")

REPORTS_DIR = Path(__file__).parent.parent.parent / "data" / "reports"
NLM_NOTEBOOK_ID = os.environ.get(
    "NLM_AI_RESEARCH_NOTEBOOK",
    "dc5d01cd-e99f-4c8f-aae4-75060b43d0de",
)

# Domain → NB-INTEL UUID routing, mirrors apps/mata-garuda/workers/nlm_feeder.py
# NLM_DOMAIN_ROUTING. Set via env or use defaults below. The keys match the
# `domain` field in enriched items (Mata Garuda scorer convention).
NB_INTEL_ROUTING: dict[str, str] = {
    "immigration_visa": os.environ.get(
        "NLM_IMMIGRATION_NOTEBOOK", "1ed02e54-542f-426a-94f8-53c5ffde4b7d"
    ),
    "tax_fiscal": os.environ.get(
        "NLM_TAX_NOTEBOOK", "7fb12c9c-4e12-4a8d-9bd1-c5b857bf310f"
    ),
    "investment_licensing": os.environ.get(
        "NLM_REGULATION_NOTEBOOK", "a17f134e-b9ab-42d9-bfc2-5bbc45165c76"
    ),
    "labor_manpower": os.environ.get(
        "NLM_REGULATION_NOTEBOOK", "a17f134e-b9ab-42d9-bfc2-5bbc45165c76"
    ),
    "political_risk": os.environ.get(
        "NLM_PRESS_NOTEBOOK", "9d262101-abeb-4e15-af9c-c38e028c62fe"
    ),
    "provincial_bali": os.environ.get(
        "NLM_PRESS_NOTEBOOK", "9d262101-abeb-4e15-af9c-c38e028c62fe"
    ),
    "ai_research": NLM_NOTEBOOK_ID,
}


@dataclass
class NLMEffectorResult:
    success: bool
    detail: str
    items_fed: int = 0
    report_path: str = ""


class NLMEffector:
    """Feeds URLs to NLM + writes complete reports."""

    def __init__(self, notebook_id: str = NLM_NOTEBOOK_ID) -> None:
        self._nb_id = notebook_id

    async def execute(self, action: str, items: list[dict[str, Any]] | None = None) -> NLMEffectorResult:
        """Execute an NLM-related action."""
        if action == "feed_nlm" and items:
            return self._feed_items(items)
        if action == "write_report" and items:
            return self._write_report(items)
        return NLMEffectorResult(success=False, detail=f"Unknown action: {action}")

    def _feed_items(self, items: list[dict[str, Any]]) -> NLMEffectorResult:
        """Feed URLs to NLM notebook, routing per-item by `domain` field.

        Falls back to the legacy single-NB behavior (AIResearch) when the
        item has no `domain` set OR the domain is `other`/unrecognized.
        Matches the routing of apps/mata-garuda/workers/nlm_feeder.py so
        the cell-side effector and the stream-feeder converge on the
        same NB-INTEL targets.
        """
        if not self._nb_id:
            return NLMEffectorResult(success=False, detail="No NLM notebook ID configured")

        fed = 0
        per_nb_counts: dict[str, int] = {}
        for item in items:
            url = item.get("url", "")
            if not url.startswith("http"):
                continue
            domain = (item.get("domain") or "").strip()
            target_nb = NB_INTEL_ROUTING.get(domain, self._nb_id)
            try:
                result = subprocess.run(
                    ["nlm", "source", "add", target_nb, "--url", url],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode == 0:
                    fed += 1
                    per_nb_counts[target_nb[:8]] = per_nb_counts.get(target_nb[:8], 0) + 1
            except Exception as e:
                logger.debug(f"NLM feed failed for {url} (domain={domain}): {e}")

        breakdown = ", ".join(f"{k}={v}" for k, v in sorted(per_nb_counts.items())) or "none"
        return NLMEffectorResult(
            success=fed > 0,
            detail=f"Fed {fed}/{len(items)} URLs across NB-INTEL ({breakdown})",
            items_fed=fed,
        )

    def _write_report(self, items: list[dict[str, Any]]) -> NLMEffectorResult:
        """Write complete Markdown report with ALL items."""
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        path = REPORTS_DIR / f"sentinel_{date_str}.md"

        # Group by source
        by_source: dict[str, list[dict]] = {}
        for item in items:
            key = item.get("source", "unknown")
            by_source.setdefault(key, []).append(item)

        lines = [
            f"# AI-Intel-Sentinel Report — {date_str}",
            f"\n**Total: {len(items)} items** | Generated: {datetime.now().strftime('%H:%M %Z')}",
            f"\n**NLM Notebook:** {self._nb_id}",
            "",
        ]

        for source, source_items in sorted(by_source.items()):
            lines.append(f"\n## {source.upper()} ({len(source_items)} items)\n")
            for i, item in enumerate(source_items, 1):
                lines.append(f"### {i}. {item.get('title', 'Untitled')[:120]}")
                lines.append(f"- **URL:** {item.get('url', 'N/A')}")
                if item.get("authors"):
                    lines.append(f"- **Authors:** {item['authors']}")
                if item.get("stars"):
                    lines.append(f"- **Stars:** {item['stars']}")
                if item.get("channel"):
                    lines.append(f"- **Channel:** {item['channel']}")
                if item.get("content"):
                    lines.append(f"- **Content:** {item['content'][:300]}")
                lines.append("")

        report_text = "\n".join(lines)
        path.write_text(report_text)

        logger.info(f"Report written: {path} ({len(items)} items, {len(report_text)} chars)")

        return NLMEffectorResult(
            success=True,
            detail=f"Report: {path} ({len(items)} items)",
            report_path=str(path),
        )

    def query_synthesis(self, question: str) -> str:
        """Query NLM for cross-source synthesis. Returns empty on failure."""
        if not self._nb_id:
            return ""
        try:
            result = subprocess.run(
                ["nlm", "notebook", "query", self._nb_id, "--question", question],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception as e:
            logger.warning(f"NLM synthesis query failed: {e}")
        return ""
