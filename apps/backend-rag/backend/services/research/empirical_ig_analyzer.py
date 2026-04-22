"""Empirical analyzer for @balizero0 IG posts.

Pipeline (Fase 0 day 2):
  1. load_posts_for_analysis — pull posts 5-29 (skip last 4 too recent)
  2. classify_hook — Claude batch classifier → hook_type (Task 8)
  3. classify_tone — Gemini 1M ctx batch → tone_register (Task 9)
  4. persist → 01_balizero_corpus.json (Task 10 driver)

Gate 2 invariant (EOD day 2): no single tone >60% of corpus.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ClassifiedPost:
    post_id: str
    caption: str
    format: str
    hook_type: str  # question | stat | story | contrarian | list
    tone_register: str  # pedagogico | analitico | tecnico | rituale | poetico | ironico | militante
    topic: str
    posted_hour_wita: int
    likes: int
    comments: int
    saves: int
    reach: int

    @property
    def engagement_rate(self) -> float:
        if self.reach == 0:
            return 0.0
        return (self.likes + self.comments + self.saves) / self.reach


class EmpiricalIGAnalyzer:
    def __init__(self, ig_sensor: Any) -> None:
        self.sensor = ig_sensor

    async def load_posts_for_analysis(self) -> list[dict[str, Any]]:
        """Fetch 29 most recent posts, return posts 5-29 (skip 4 newest).

        If fewer than 29 posts exist, skip the 4 newest and return the rest.
        If 4 or fewer exist, return an empty list.
        """
        all_posts = await self.sensor.read_posts(limit=29)
        if len(all_posts) <= 4:
            return []
        return all_posts[4:]
