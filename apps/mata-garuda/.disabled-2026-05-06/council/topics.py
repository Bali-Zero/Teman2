"""
Consiglio v1 — Topic selector.

Sources topics from:
1. Manual CLI input
2. Escalations (shared/escalations.json)
3. MOS unresolved entries (via mem subprocess)
"""
from __future__ import annotations

import json
import logging
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from mata_garuda.council.models import Topic

logger = logging.getLogger("mata_garuda.council.topics")

# Default escalations path (monorepo root)
ESCALATIONS_PATH = Path(__file__).parent.parent.parent.parent.parent / "shared" / "escalations.json"


class TopicSelector:
    """Select topics for council deliberation."""

    def __init__(self, escalations_path: Optional[Path] = None):
        self._escalations_path = escalations_path or ESCALATIONS_PATH

    def from_cli(
        self,
        title: str,
        description: str,
        category: str = "operational",
    ) -> Topic:
        """Create a topic from CLI input."""
        return Topic(
            id=str(uuid.uuid4())[:12],
            title=title,
            description=description,
            category=category,
            source="cli",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def from_escalation(self, escalation: dict) -> Topic:
        """Convert an escalation entry to a Topic."""
        return Topic(
            id=str(uuid.uuid4())[:12],
            title=escalation.get("title", escalation.get("description", "")[:80]),
            description=escalation.get("description", ""),
            category=_infer_category(escalation),
            source="escalation",
            constraints=escalation.get("constraints", []),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def from_mos_unresolved(self, limit: int = 5) -> list[Topic]:
        """Query MOS for unresolved entries with importance >= 6."""
        try:
            result = subprocess.run(
                [str(Path.home() / ".claude" / "scripts" / "mem"), "query", "unresolved"],
                capture_output=True, text=True,
                timeout=10,
            )
            if result.returncode != 0:
                logger.warning(f"[topics] mem query failed: {result.stderr[:100]}")
                return []

            topics = []
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                topics.append(Topic(
                    id=str(uuid.uuid4())[:12],
                    title=line[:80],
                    description=line,
                    category="operational",
                    source="mos",
                    created_at=datetime.now(timezone.utc).isoformat(),
                ))
                if len(topics) >= limit:
                    break
            return topics

        except Exception as e:
            logger.warning(f"[topics] MOS query failed: {e}")
            return []

    def from_escalations_file(self) -> list[Topic]:
        """Read pending escalations from shared/escalations.json."""
        if not self._escalations_path.exists():
            return []

        try:
            data = json.loads(self._escalations_path.read_text())
            if isinstance(data, list):
                entries = data
            elif isinstance(data, dict):
                entries = data.get("pending", data.get("escalations", []))
            else:
                return []

            return [
                self.from_escalation(e) for e in entries
                if isinstance(e, dict) and e.get("status", "pending") == "pending"
            ]
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"[topics] escalations read failed: {e}")
            return []

    def auto_select(self) -> Optional[Topic]:
        """Pick the highest-priority pending topic.

        Priority order:
        1. Escalations > 3 days old (weight 3)
        2. MOS unresolved importance >= 7 (weight 2)
        3. Recent escalations (weight 1)
        """
        candidates: list[tuple[int, Topic]] = []

        # Escalations
        for topic in self.from_escalations_file():
            candidates.append((3, topic))

        # MOS unresolved
        for topic in self.from_mos_unresolved(limit=3):
            candidates.append((2, topic))

        if not candidates:
            return None

        # Sort by priority descending
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]


def _infer_category(escalation: dict) -> str:
    """Infer topic category from escalation metadata."""
    text = json.dumps(escalation).lower()
    if any(w in text for w in ("architect", "refactor", "migration", "infrastructure")):
        return "architecture"
    if any(w in text for w in ("strategy", "revenue", "policy", "compliance")):
        return "strategic"
    if any(w in text for w in ("escalat", "critical", "urgent", "blocker")):
        return "escalation"
    return "operational"
