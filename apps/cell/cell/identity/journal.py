# apps/cell/cell/identity/journal.py
"""Journal — CELL's daily narrative.

Once per day (during sleep phase), CELL writes a free-text summary of the day.
Stored in `cell_journal`, injected as context into SlowReasoner system prompt.
Creates narrative continuity between restarts.

Inspired by Stanford Smallville (persistent agent identity with daily summaries).
"""
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger("cell.identity.journal")

_JOURNAL_SYSTEM = """You are CELL, an autonomous digital organism.
Write a 2-3 sentence first-person journal entry summarizing your day.
Focus on: what you observed, what you learned, how you felt, what you did.
Be concise, honest, and specific. Use past tense. No markdown."""


@dataclass
class JournalEntry:
    journal_date: date
    narrative: str
    emotion_summary: str
    actions_taken: int
    lessons_count: int


class Journal:
    """Writes and retrieves daily narrative entries."""

    def __init__(
        self,
        pool: Any,
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen3.5:9b",
    ) -> None:
        self._pool = pool
        self._ollama_url = ollama_url
        self._model = ollama_model

    async def _summarize_with_llm(self, prompt: str) -> str:
        """Call Qwen 9B to write the journal narrative. Falls back gracefully."""
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"{self._ollama_url}/api/chat",
                    json={
                        "model": self._model,
                        "messages": [
                            {"role": "system", "content": _JOURNAL_SYSTEM},
                            {"role": "user", "content": prompt},
                        ],
                        "stream": False,
                        "think": False,
                        "options": {"temperature": 0.4, "num_predict": 200},
                    },
                )
                response.raise_for_status()
                return response.json()["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"Journal LLM call failed: {e}")
            return ""

    def _build_prompt(
        self,
        episodes: list[dict],
        emotion_summary: str,
        actions_taken: int,
        lessons_count: int,
        today: date,
    ) -> str:
        episode_summary = ""
        if episodes:
            lines = []
            for ep in episodes[:10]:  # top 10 by activation
                lines.append(
                    f"- [{ep.get('emotion', '?')}] {ep.get('action_taken', '?')} "
                    f"-> {ep.get('outcome', '?')}: {ep.get('lesson', '')[:80]}"
                )
            episode_summary = "\nKey episodes:\n" + "\n".join(lines)

        return (
            f"Date: {today.isoformat()}\n"
            f"Overall emotion: {emotion_summary}\n"
            f"Actions taken: {actions_taken}\n"
            f"Lessons learned: {lessons_count}\n"
            f"{episode_summary}\n\n"
            "Write your journal entry:"
        )

    async def write(
        self,
        episodes: list[dict],
        emotion_summary: str = "calm",
        actions_taken: int = 0,
        lessons_count: int = 0,
        today: date | None = None,
    ) -> JournalEntry:
        """Write today's journal entry and persist to cell_journal."""
        if today is None:
            today = datetime.now(timezone.utc).date()

        prompt = self._build_prompt(episodes, emotion_summary, actions_taken, lessons_count, today)
        narrative = await self._summarize_with_llm(prompt)

        if not narrative:
            # Fallback: template narrative when LLM is unavailable
            narrative = (
                f"On {today.isoformat()}, CELL operated in {emotion_summary} state. "
                f"{actions_taken} action(s) taken, {lessons_count} lesson(s) recorded."
            )

        entry = JournalEntry(
            journal_date=today,
            narrative=narrative,
            emotion_summary=emotion_summary,
            actions_taken=actions_taken,
            lessons_count=lessons_count,
        )

        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO cell_journal
                   (journal_date, narrative, emotion_summary, actions_taken, lessons_count)
                   VALUES ($1, $2, $3, $4, $5)
                   ON CONFLICT (journal_date) DO UPDATE
                   SET narrative = EXCLUDED.narrative,
                       emotion_summary = EXCLUDED.emotion_summary,
                       actions_taken = EXCLUDED.actions_taken,
                       lessons_count = EXCLUDED.lessons_count""",
                entry.journal_date,
                entry.narrative,
                entry.emotion_summary,
                entry.actions_taken,
                entry.lessons_count,
            )

        logger.info(
            f"Journal written: {today.isoformat()} emotion={emotion_summary} "
            f"actions={actions_taken}"
        )
        return entry

    async def recent_days(self, limit: int = 3) -> str:
        """Return last N journal entries as formatted text for LLM injection."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT journal_date, narrative, emotion_summary
                   FROM cell_journal
                   ORDER BY journal_date DESC
                   LIMIT $1""",
                limit,
            )

        if not rows:
            return ""

        lines = ["JOURNAL (recent days):"]
        for row in rows:
            lines.append(
                f"  [{row['journal_date'].isoformat()}] ({row['emotion_summary']}) "
                f"{row['narrative']}"
            )
        return "\n".join(lines)
