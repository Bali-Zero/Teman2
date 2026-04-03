# apps/cell/cell/memory/dreamer.py
"""Dreamer — CELL's nocturnal consolidation.

Active during circadian "asleep" phase. Replays today's episodes,
extracts generalizable rules, identifies knowledge gaps, and writes
a dream summary to cell_dreams.

Inspired by MemGPT (paged memory consolidation) + sleep consolidation research.
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger("cell.memory.dreamer")

_DREAMER_SYSTEM = """You are CELL's consolidation process, running during sleep.
Analyze today's episodes and extract generalizable rules.
Rules should be in the form: "When [condition], [action] leads to [outcome]."
Also identify gaps: situations where you were uncertain or had no clear rule.

RESPOND with exactly this JSON:
{
  "rules": ["rule1", "rule2"],
  "gaps": ["gap1", "gap2"],
  "summary": "One sentence summary of the day."
}"""


@dataclass
class DreamResult:
    dream_date: date
    episodes_count: int
    rules_extracted: list[str] = field(default_factory=list)
    merged_count: int = 0
    gaps_identified: list[str] = field(default_factory=list)
    summary: str = ""


class Dreamer:
    """Nocturnal memory consolidation. Runs once per sleep cycle."""

    def __init__(
        self,
        pool: Any,
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen3.5:9b",
    ) -> None:
        self._pool = pool
        self._ollama_url = ollama_url
        self._model = ollama_model

    async def _fetch_todays_episodes(self) -> list[dict]:
        """Fetch all episodes from the last 24 hours."""
        cutoff = datetime.now(timezone.utc).timestamp() - 86400.0
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, timestamp, situation, emotion, action_taken,
                          outcome, lesson, recall_count
                   FROM cell_episodes
                   WHERE timestamp >= $1
                   ORDER BY timestamp ASC""",
                cutoff,
            )

        episodes = []
        for row in rows:
            sit = row["situation"]
            if isinstance(sit, str):
                sit = json.loads(sit)
            episodes.append({
                "id": row["id"],
                "timestamp": float(row["timestamp"]),
                "situation": sit,
                "emotion": row["emotion"],
                "action_taken": row["action_taken"],
                "outcome": row["outcome"],
                "lesson": row["lesson"],
                "recall_count": row["recall_count"],
            })
        return episodes

    async def _extract_rules_with_llm(
        self, episodes: list[dict]
    ) -> tuple[list[str], list[str]]:
        """Use Qwen 9B to extract rules and gaps from episodes. Returns (rules, gaps)."""
        episode_text = "\n".join(
            f"- [{ep['emotion']}] {ep['action_taken']} -> {ep['outcome']}: {ep['lesson'][:100]}"
            for ep in episodes[:20]  # cap at 20 episodes for prompt size
        )
        user_msg = f"Today's episodes:\n{episode_text}\n\nConsolidate into rules and gaps."

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self._ollama_url}/api/chat",
                    json={
                        "model": self._model,
                        "messages": [
                            {"role": "system", "content": _DREAMER_SYSTEM},
                            {"role": "user", "content": user_msg},
                        ],
                        "stream": False,
                        "think": False,
                        "options": {"temperature": 0.2, "num_predict": 512},
                    },
                )
                response.raise_for_status()
                text = response.json()["message"]["content"]

                # Parse JSON from response
                start = text.find("{")
                end = text.rfind("}") + 1
                if start == -1 or end == 0:
                    logger.warning("Dreamer LLM produced no JSON")
                    return [], []

                data = json.loads(text[start:end])
                rules = data.get("rules", [])
                gaps = data.get("gaps", [])
                return rules, gaps

        except Exception as e:
            logger.warning(f"Dreamer LLM extraction failed: {e}")
            return [], []

    async def _persist_dream(self, result: DreamResult) -> None:
        """Write dream result to cell_dreams."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO cell_dreams
                   (dream_date, episodes_count, rules_extracted, merged_count,
                    gaps_identified, summary)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                result.dream_date,
                result.episodes_count,
                json.dumps(result.rules_extracted),
                result.merged_count,
                json.dumps(result.gaps_identified),
                result.summary,
            )

    async def dream(self, today: date | None = None) -> DreamResult:
        """Run nocturnal consolidation. Call once per sleep cycle.

        Returns DreamResult with extracted rules and gaps.
        Persists to cell_dreams table.
        """
        if today is None:
            today = datetime.now(timezone.utc).date()

        episodes = await self._fetch_todays_episodes()

        if not episodes:
            result = DreamResult(
                dream_date=today,
                episodes_count=0,
                rules_extracted=[],
                gaps_identified=[],
                summary="No episodes today — quiet rest.",
            )
            await self._persist_dream(result)
            logger.info("Dreamer: no episodes to consolidate")
            return result

        rules, gaps = await self._extract_rules_with_llm(episodes)

        # Summary from gaps + rules count
        if rules:
            summary = f"Consolidated {len(episodes)} episodes into {len(rules)} rules."
        else:
            summary = f"Reviewed {len(episodes)} episodes. No clear rules emerged yet."

        result = DreamResult(
            dream_date=today,
            episodes_count=len(episodes),
            rules_extracted=rules,
            merged_count=0,  # future: merge similar episodes into prototypes
            gaps_identified=gaps,
            summary=summary,
        )
        await self._persist_dream(result)

        logger.info(
            f"Dreamer: consolidated {len(episodes)} episodes -> "
            f"{len(rules)} rules, {len(gaps)} gaps"
        )
        return result
