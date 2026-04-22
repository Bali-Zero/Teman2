"""Empirical analyzer for @balizero0 IG posts.

Pipeline (Fase 0 day 2):
  1. load_posts_for_analysis — pull posts 5-29 (skip last 4 too recent)
  2. classify_hook — Claude batch classifier → hook_type (Task 8)
  3. classify_tone — Gemini 1M ctx batch → tone_register (Task 9)
  4. persist → 01_balizero_corpus.json (Task 10 driver)

Gate 2 invariant (EOD day 2): no single tone >60% of corpus.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

HOOK_CATEGORIES = ("question", "stat", "story", "contrarian", "list")
TONE_REGISTERS = (
    "pedagogico", "analitico", "tecnico", "rituale",
    "poetico", "ironico", "militante",
)
GEMINI_MODEL = "gemini-3.1-pro-preview"


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

    def classify_hooks_batch(self, posts: list[dict[str, Any]]) -> dict[str, str]:
        """Classify hook type for each post via a single `claude -p` call.

        Returns ``{post_id: hook_type}``. Hook categories: question, stat,
        story, contrarian, list. On subprocess failure or unparseable JSON,
        returns ``{post_id: "unknown"}`` for every post. On partial responses,
        missing post_ids are simply absent from the dict (caller must handle).
        """
        categories = "|".join(HOOK_CATEGORIES)
        prompt_lines = [
            "Classify the HOOK TYPE of each Instagram post below. Emit ONLY a "
            "single JSON object on the last line, no prose, no markdown fences. "
            f"Schema: {{\"classifications\":[{{\"post_id\":\"<id>\","
            f"\"hook_type\":\"{categories}\"}}]}}",
            "",
        ]
        for p in posts:
            snippet = (p.get("caption") or "")[:500].replace("\n", " ")
            prompt_lines.append(f"post_id={p['post_id']}: {snippet}")
        prompt = "\n".join(prompt_lines)

        try:
            result = subprocess.run(
                ["claude", "-p", prompt],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=240,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            logger.warning("claude CLI invocation failed: %s", exc)
            return {p["post_id"]: "unknown" for p in posts}

        if result.returncode != 0:
            logger.warning(
                "claude -p exited %s; falling back to 'unknown' for %d posts",
                result.returncode,
                len(posts),
            )
            return {p["post_id"]: "unknown" for p in posts}

        for line in reversed(result.stdout.splitlines()):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            cls = parsed.get("classifications") or []
            return {c["post_id"]: c["hook_type"] for c in cls if "post_id" in c and "hook_type" in c}

        logger.warning("no JSON line in claude -p output; falling back")
        return {p["post_id"]: "unknown" for p in posts}

    def classify_tones_batch(self, posts: list[dict[str, Any]]) -> dict[str, str]:
        """Classify tone register via Gemini 3.1 Pro 1M-ctx single call.

        Returns ``{post_id: tone_register}``. Registers are the 7 WR2 canonical
        ones (see TONE_REGISTERS). Same failure-fallback shape as
        classify_hooks_batch — "unknown" on any error.
        """
        registers = "|".join(TONE_REGISTERS)
        prompt_lines = [
            "Classify the TONE REGISTER of each Instagram post. Emit ONLY a "
            "single JSON object on the last line, no prose. "
            f"Schema: {{\"classifications\":[{{\"post_id\":\"<id>\","
            f"\"tone_register\":\"{registers}\"}}]}}",
            "",
        ]
        for p in posts:
            snippet = (p.get("caption") or "")[:800].replace("\n", " ")
            prompt_lines.append(f"post_id={p['post_id']}: {snippet}")
        prompt = "\n".join(prompt_lines)

        try:
            result = subprocess.run(
                ["gemini", "-m", GEMINI_MODEL, "-p", prompt],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            logger.warning("gemini CLI invocation failed: %s", exc)
            return {p["post_id"]: "unknown" for p in posts}

        if result.returncode != 0:
            logger.warning(
                "gemini -p exited %s; falling back to 'unknown' for %d posts",
                result.returncode,
                len(posts),
            )
            return {p["post_id"]: "unknown" for p in posts}

        for line in reversed(result.stdout.splitlines()):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            cls = parsed.get("classifications") or []
            return {
                c["post_id"]: c["tone_register"]
                for c in cls
                if "post_id" in c and "tone_register" in c
            }

        logger.warning("no JSON line in gemini output; falling back")
        return {p["post_id"]: "unknown" for p in posts}

    @staticmethod
    def check_skew(
        distribution: dict[str, int],
        *,
        threshold: float = 0.6,
    ) -> tuple[bool, str, float]:
        """Gate 2 check on tone distribution.

        Returns ``(ok, dominant_tone, dominant_pct)``. ``ok`` is True iff no
        single tone accounts for more than ``threshold`` (default 60%) of
        the sample. Empty distribution → ``(True, "", 0.0)``.
        """
        total = sum(distribution.values())
        if total == 0:
            return True, "", 0.0
        dominant = max(distribution, key=distribution.get)
        pct = distribution[dominant] / total
        return (pct <= threshold, dominant, pct)
