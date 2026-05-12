# apps/cell/cell/memory/dreamer.py
"""Dreamer — CELL's nocturnal consolidation.

Active during circadian "asleep" phase. Replays today's episodes,
extracts generalizable rules, identifies knowledge gaps, and writes
a dream summary to cell_dreams.

Inspired by MemGPT (paged memory consolidation) + sleep consolidation research.

LEVA 1 (2026-05-13): after the dream is persisted, every rule in
``rules_extracted`` is upserted into ``cell_skills`` as a candidate skill
(``kind='skill'``, ``status='candidate'``, ``source='dreamer'``). This closes
the loop ``dream → persisted skill`` so subsequent pulses can recall the rule
across cell restarts. Dedup is hash-based on the normalised rule text.
"""
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

import httpx

from cell.cortex.skill_library import compute_embedding

logger = logging.getLogger("cell.memory.dreamer")

# LEVA 1 (2026-05-13): cap rules-as-skills per dream cycle to bound bloat if
# the Qwen 9B consolidator emits an outlier high count.
_MAX_RULES_PER_DREAM = 20

# Normalisation helpers for rule dedup. We match on case-insensitive, trailing-
# punctuation-stripped, whitespace-collapsed form so "Rule!  " collides with
# "rule" (this happens daily — empirical: last 3 dreams emit identical rules).
_WHITESPACE_RE = re.compile(r"\s+")
_TRAILING_PUNCT_RE = re.compile(r"[.!?\s]+$")


def _normalize_rule(rule: str) -> str:
    """Lowercase + strip trailing punctuation + collapse whitespace. Cap 4000."""
    if not rule:
        return ""
    s = rule.lower().strip()
    s = _TRAILING_PUNCT_RE.sub("", s)
    s = _WHITESPACE_RE.sub(" ", s)
    return s[:4000]

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
        http_client: Any = None,
    ) -> None:
        self._pool = pool
        self._ollama_url = ollama_url
        self._model = ollama_model
        self._http_client = http_client  # persistent client (Golden Rule #10)
        self._owns_client = http_client is None  # True if we created it
        self._client: Any = None

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

    def _get_client(self) -> Any:
        """Return persistent httpx client, creating one if not provided."""
        if self._http_client is not None:
            return self._http_client
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        """Close the httpx client if we own it."""
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

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
            client = self._get_client()
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

    async def _upsert_rules_as_skills(
        self, rules: list[str], dream_date: date
    ) -> int:
        """Upsert dream-extracted rules as candidate skills in cell_skills.

        Returns the number of NEW skills inserted (0 if all dedup hits).
        Best-effort: any exception is logged at WARNING and swallowed; the
        outer ``dream()`` call must never break because of a skill upsert.

        LEVA 1 contract:
        - ``kind='skill'`` (LEVA 2 column, default already set by migration 172
          but written explicitly to stay self-describing).
        - ``status='candidate'`` (only ``status='active'`` is returned by
          ``SkillLibrary.recall()``; promotion is a LEVA 4 concern).
        - ``fitness=0.0`` (initial; the existing ``record_use()`` formula will
          recompute it on the first use). The source confidence (0.6) is stored
          in ``precondition.source_confidence`` instead, so the formula is not
          shadowed.
        - ``scope='Project'`` (germline-inheritable via HGT, LEVA 5).
        - ``source='dreamer'``.
        - Dedup: ``name = f"rule:{sha1(normalised)[:24]}"``; SELECT-then-INSERT
          inside a single connection. Single-process dreamer cron makes the
          race window trivial.
        """
        if not rules:
            return 0

        rules = rules[:_MAX_RULES_PER_DREAM]
        inserted = 0

        for rule_text in rules:
            try:
                norm = _normalize_rule(rule_text)
                if not norm:
                    continue
                skill_name = f"rule:{hashlib.sha1(norm.encode()).hexdigest()[:24]}"
                trigger_nl = rule_text[:4000]
                embedding = compute_embedding(norm)
                precondition = {
                    "source": "dreamer",
                    "source_confidence": 0.6,
                    "source_dream_date": dream_date.isoformat(),
                    "rule_text_sha1": skill_name.removeprefix("rule:"),
                }

                async with self._pool.acquire() as conn:
                    existing = await conn.fetchval(
                        "SELECT id FROM cell_skills WHERE name = $1",
                        skill_name,
                    )
                    if existing is not None:
                        continue
                    await conn.execute(
                        """
                        INSERT INTO cell_skills
                            (name, trigger_nl, action_sequence, rationale_nl,
                             fitness, success_count, failure_count, use_count,
                             generation, parent_id, embedding, status, source,
                             kind, scope, precondition)
                        VALUES
                            ($1, $2, '[]'::jsonb, $3,
                             0.0, 0, 0, 0,
                             0, NULL, $4, 'candidate', 'dreamer',
                             'skill', 'Project', $5::jsonb)
                        """,
                        skill_name,
                        trigger_nl,
                        f"Rule extracted by Dreamer on {dream_date.isoformat()}.",
                        embedding,
                        json.dumps(precondition),
                    )
                    inserted += 1
            except Exception as exc:
                logger.warning(
                    "Failed to upsert rule as skill: %s -- %s",
                    rule_text[:80],
                    exc,
                )

        if inserted:
            logger.info(
                "Dreamer: upserted %d new candidate skills from %d rules",
                inserted,
                len(rules),
            )
        return inserted

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

        # LEVA 1: close the loop dream -> persisted candidate skill.
        # Best-effort: never blocks the caller.
        if result.rules_extracted:
            try:
                await self._upsert_rules_as_skills(
                    result.rules_extracted, result.dream_date
                )
            except Exception as exc:
                logger.warning("Dreamer skill upsert failed: %s", exc)

        logger.info(
            f"Dreamer: consolidated {len(episodes)} episodes -> "
            f"{len(rules)} rules, {len(gaps)} gaps"
        )
        return result
