"""Literature synthesis agent — Gemini Deep Research across 4 SOTA topics.

Produces `research/sota-social-2026-v1/03_sota_literature.md`.

Spec §Q8 A4 dimensions (Hook + Tone + Cadence + Format). 4 research
topics cover the 4 dimensions + 1 crosscut (algorithm windows).

Gate 5 invariant (EOD day 3): ≥30 distinct source URLs cited, ≥10 from
2025-26.

Gemini CLI call pattern matches the tone classifier (Task 9): single
subprocess invocation per topic with `-m gemini-3.1-pro-preview`. Each
topic call takes ~3-6 min (Gemini Deep Research grounded). Total run
time: 15-25 min for 4 topics. Script exits 1 if Gate 5 fails.
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-3.1-pro-preview"
DEFAULT_TIMEOUT_SEC = 900  # 15 min max per topic


@dataclass
class ResearchTopic:
    slug: str
    prompt: str


# Keyed by stable slug. Each prompt ends with a mandatory "OUTPUT" contract
# that forces markdown with a Sources section — so Gate 5 URL-counting
# can parse reliably.
TOPICS: list[ResearchTopic] = [
    ResearchTopic(
        slug="01_hook_taxonomy",
        prompt=(
            "Research hook taxonomy for social media 2024-2026 (Instagram, "
            "LinkedIn, TikTok). Cite academic papers where available "
            "(arxiv.org, Google Scholar) and top creator-economy blogs "
            "(Later, HubSpot, Buffer, Adam Connell). Structure as: "
            "(1) taxonomy definitions, (2) top 20 patterns observed in "
            "2025-26, (3) differences by platform. Minimum 15 distinct "
            "sources with URLs + publication year visible."
        ),
    ),
    ResearchTopic(
        slug="02_tone_voice_b2b_legal",
        prompt=(
            "Research tone/voice strategies for B2B legal + immigration "
            "services social presence 2024-2026. Benchmark signals from: "
            "Big4 legal firms (Deloitte, SSEK Indonesia, EY, KPMG), top "
            "creator lawyers on TikTok/LinkedIn, legal marketing blogs. "
            "Cover: appropriate formality, authority signaling, empathy, "
            "persona adaptation. Minimum 8 sources with URLs + dates."
        ),
    ),
    ResearchTopic(
        slug="03_cadence_algorithm_2026",
        prompt=(
            "Research 2026 algorithm windows and posting cadence for "
            "Instagram, LinkedIn, TikTok, Threads, YouTube Shorts. Include "
            "Adam Mosseri 2025-26 public statements, LinkedIn algorithmic "
            "research 2025, TikTok CPM 2026 analyses, YouTube Shorts reach "
            "data. Identify optimal posting times in WITA (UTC+8) for two "
            "audiences: Indonesian residents + European expats in Bali. "
            "Minimum 10 sources with URLs + dates."
        ),
    ),
    ResearchTopic(
        slug="04_format_objective_matrix",
        prompt=(
            "Research which content FORMATS (carousel, reel, static image, "
            "long-form article, thread, newsletter, podcast, YouTube long, "
            "YouTube Shorts) best serve which OBJECTIVES (lead generation, "
            "authority building, audience growth) for B2B service businesses. "
            "Focus on 2025-26 data only. Include benchmark engagement rate "
            "per format/objective pair where available. Minimum 8 sources."
        ),
    ),
]


class LiteratureAgent:
    """Orchestrates Gemini Deep Research for each SOTA topic."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir

    def research_topic(
        self,
        topic: ResearchTopic,
        *,
        timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    ) -> str:
        """Run Gemini Deep Research for one topic, return the markdown body.

        On failure (rc != 0 or missing gemini binary), returns a short
        placeholder markdown with the slug + error so the final synthesis
        is still writable and Gate 5 can be evaluated honestly.
        """
        prompt = (
            f"{topic.prompt}\n\n"
            "OUTPUT FORMAT (mandatory): Markdown document with exactly these "
            "three sections, in this order:\n"
            "## Summary\n"
            "A 3-5 sentence executive summary.\n"
            "## Key findings\n"
            "A bulleted list of 10-15 specific findings. Ground every "
            "finding in at least one cited source (inline numbered refs "
            "like [1], [2], ...).\n"
            "## Sources\n"
            "A numbered list of the references you cited above. Each "
            "entry MUST include: author or outlet, title, full URL "
            "(https://...), publication year (2024, 2025, or 2026)."
        )
        try:
            result = subprocess.run(
                ["gemini", "-m", GEMINI_MODEL, "-p", prompt],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                check=False,
            )
        except FileNotFoundError:
            logger.warning("gemini CLI not found in PATH")
            return f"## {topic.slug}\n\n_Research failed: gemini CLI not found._\n"
        except subprocess.TimeoutExpired:
            logger.warning("gemini timed out for %s after %ds", topic.slug, timeout_sec)
            return f"## {topic.slug}\n\n_Research timed out after {timeout_sec}s._\n"

        if result.returncode != 0:
            logger.warning(
                "gemini rc=%s stderr=%s for %s",
                result.returncode, result.stderr[-200:], topic.slug,
            )
            return (
                f"## {topic.slug}\n\n_Research failed: "
                f"gemini exited {result.returncode}._\n"
            )

        return result.stdout or f"## {topic.slug}\n\n_No output from gemini._\n"

    @staticmethod
    def count_sources(markdown: str) -> tuple[int, int]:
        """Return ``(total_distinct_urls, mentions_of_2025_or_2026)``.

        Gate 5 invariant: total ≥ 30, recent ≥ 10.
        """
        urls = re.findall(r"https?://[^\s\)\]]+", markdown)
        distinct = len({u.rstrip(".,") for u in urls})
        recent = len(re.findall(r"\b(2025|2026)\b", markdown))
        return (distinct, recent)

    def synthesize(self, bodies: dict[str, str]) -> str:
        """Concatenate topic outputs into `03_sota_literature.md`."""
        header = (
            "# SOTA Literature Synthesis — Social Media 2026\n\n"
            "> Auto-generated by `scripts/sota_literature_research.py` "
            "(Fase 0 day 3). Each section produced by Gemini 3.1 Pro Deep "
            "Research, grounded.\n\n"
            "---\n\n"
        )
        parts = [header]
        for topic_slug, body in bodies.items():
            parts.append(f"## {topic_slug}\n\n{body}\n\n---\n\n")
        return "".join(parts)
