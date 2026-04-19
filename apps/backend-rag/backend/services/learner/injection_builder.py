"""MemoriaEpisodicaBuilder — compact War Room memory for Consiglio M4 prompts.

Design §10.4: inject a 2000-char max ``<memoria_episodica>…</memoria_episodica>``
block with:

    - top-5 war_room skills by confidence
    - rejections ultimi 14gg GROUP BY reason
    - register performance (from war_room_council_performance materialized view)

Budget is a hard ceiling (``SYMBIOSIS.md:43``): we truncate and add an
``…`` sentinel if the body overflows.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from backend.services.war_room.repository import WarRoomRepository

logger = logging.getLogger(__name__)


MAX_BLOCK_CHARS = 2000
BLOCK_OPEN = "<memoria_episodica>"
BLOCK_CLOSE = "</memoria_episodica>"
MAX_SKILLS = 5
MAX_REJECTION_BUCKETS = 6


class SkillSearchFn(Protocol):
    """Abstract skill-search over the genome. Returns list of {name, confidence, procedure}."""

    async def __call__(self, query: str, limit: int) -> list[dict[str, Any]]: ...


class CouncilPerformanceFn(Protocol):
    """Abstract lookup to war_room_council_performance materialized view."""

    async def __call__(self) -> list[dict[str, Any]]: ...


@dataclass
class _MemoriaParts:
    skills: list[dict[str, Any]] = field(default_factory=list)
    rejections: dict[str, int] = field(default_factory=dict)
    performance: list[dict[str, Any]] = field(default_factory=list)


class MemoriaEpisodicaBuilder:
    """Build a compact memory block injected into Consiglio prompts."""

    def __init__(
        self,
        repo: WarRoomRepository,
        *,
        skill_search_fn: SkillSearchFn | None = None,
        council_performance_fn: CouncilPerformanceFn | None = None,
        max_chars: int = MAX_BLOCK_CHARS,
    ) -> None:
        self.repo = repo
        self.skill_search_fn = skill_search_fn
        self.council_performance_fn = council_performance_fn
        self.max_chars = max_chars

    async def build(self) -> str:
        parts = await self._gather_parts()
        body = self._render(parts)
        block = f"{BLOCK_OPEN}\n{body}\n{BLOCK_CLOSE}"
        if len(block) <= self.max_chars:
            return block
        # over budget — truncate body, keeping open/close tags intact
        overhead = len(BLOCK_OPEN) + len(BLOCK_CLOSE) + 3  # newlines
        budget = self.max_chars - overhead - 1            # room for ellipsis
        if budget <= 0:
            return BLOCK_OPEN + "\n" + BLOCK_CLOSE
        truncated = body[:budget].rstrip() + "…"
        return f"{BLOCK_OPEN}\n{truncated}\n{BLOCK_CLOSE}"

    # ── Data gathering ────────────────────────────────────────

    async def _gather_parts(self) -> _MemoriaParts:
        parts = _MemoriaParts()

        # 1. genome skills
        if self.skill_search_fn is not None:
            try:
                parts.skills = await self.skill_search_fn("war_room", MAX_SKILLS)
            except Exception as exc:  # noqa: BLE001
                logger.debug("skill_search_fn failed: %s", exc)

        # 2. rejections last 14d
        try:
            rejections = await self.repo.recent_rejections(days=14)
            for rej in rejections:
                key = rej.reason.value
                parts.rejections[key] = parts.rejections.get(key, 0) + 1
        except Exception as exc:  # noqa: BLE001
            logger.debug("recent_rejections failed: %s", exc)

        # 3. council performance view
        if self.council_performance_fn is not None:
            try:
                parts.performance = await self.council_performance_fn()
            except Exception as exc:  # noqa: BLE001
                logger.debug("council_performance failed: %s", exc)

        return parts

    # ── Rendering ─────────────────────────────────────────────

    @staticmethod
    def _render(parts: _MemoriaParts) -> str:
        lines: list[str] = []

        if parts.skills:
            lines.append("[Skills recenti (top-5)]")
            for skill in parts.skills[:MAX_SKILLS]:
                name = skill.get("name") or skill.get("skill_id") or "?"
                conf = skill.get("confidence")
                proc = skill.get("procedure") or ""
                conf_s = f"{float(conf):.2f}" if conf is not None else "?"
                proc_s = (proc[:160] + "…") if len(proc) > 160 else proc
                lines.append(f"- {name} (conf={conf_s}): {proc_s}")
            lines.append("")

        if parts.rejections:
            lines.append("[Rifiuti ultimi 14gg per motivo]")
            sorted_buckets = sorted(
                parts.rejections.items(),
                key=lambda kv: kv[1],
                reverse=True,
            )[:MAX_REJECTION_BUCKETS]
            for reason, count in sorted_buckets:
                lines.append(f"- {reason}: {count}")
            lines.append("")

        if parts.performance:
            lines.append("[Performance per registro (ultimi 14gg)]")
            for row in parts.performance:
                register = row.get("register", "?")
                avg = row.get("avg_composite_score")
                n = row.get("last_14d_posts", 0)
                top = row.get("top_topic", "")
                avg_s = f"{float(avg):.2f}" if avg is not None else "?"
                lines.append(f"- {register}: n={n} avg={avg_s} top='{top}'")

        if not lines:
            return "(nessuna memoria episodica disponibile)"

        return "\n".join(lines).rstrip()
