"""Format matrix builder — 294 cells (14 channels × 3 objectives × 7 registers).

Each cell specifies the recommended format + hook pattern + expected
engagement range + confidence score. Populated in two stages:

  1. `build_empty_matrix()` — scaffold with all 294 keys, confidence=None
  2. `populate_from_playbook_stub()` — initial heuristic fill, confidence ≤ 0.5

Consiglio v1 (Task 19-20) then overwrites cells where the 4-LLM consensus
has higher confidence. Any cell with stub confidence remains visible as
"uncalibrated" in the final playbook — Zero can see where the system is
still guessing.
"""

from __future__ import annotations

from typing import Any


CHANNELS: list[str] = [
    "instagram",
    "linkedin",
    "tiktok",
    "threads",
    "x_twitter",
    "youtube_long",
    "youtube_shorts",
    "telegram",
    "whatsapp",
    "newsletter",
    "blog_seo",
    "podcast",
    "xiaohongshu_weibo",
    "quora_reddit",
]
assert len(CHANNELS) == 14

OBJECTIVES: list[str] = ["lead", "authority", "audience"]

# 7 WR2 canonical registers (identical set used by empirical_ig_analyzer).
REGISTERS: list[str] = [
    "pedagogico",
    "analitico",
    "tecnico",
    "rituale",
    "poetico",
    "ironico",
    "militante",
]


class FormatMatrixBuilder:
    def build_empty_matrix(self) -> list[dict[str, Any]]:
        """Produce 294 cells with all fields null. Deterministic ordering."""
        cells: list[dict[str, Any]] = []
        for channel in CHANNELS:
            for obj in OBJECTIVES:
                for reg in REGISTERS:
                    cells.append({
                        "cell_key": f"{channel}:{obj}:{reg}",
                        "channel": channel,
                        "objective": obj,
                        "register": reg,
                        "recommended_format": None,
                        "hook_pattern": None,
                        "cadence_note": None,
                        "expected_engagement_rate_range": None,
                        "confidence": None,
                    })
        return cells

    def populate_from_playbook_stub(
        self,
        cells: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Apply channel-specific heuristics with low confidence (≤0.5).

        This is NOT the final recommendation — Consiglio v1 (Task 19-20)
        overwrites cells where it has higher confidence. Keeping
        confidence low here ensures the 4-LLM consensus dominates the
        decision process.
        """
        for cell in cells:
            if cell["recommended_format"] is not None:
                continue

            ch = cell["channel"]
            obj = cell["objective"]

            cell["recommended_format"] = self._default_format(ch, obj)
            cell["hook_pattern"] = "question" if obj == "lead" else "stat"
            cell["cadence_note"] = "see 06_cadence_engine.json"
            cell["expected_engagement_rate_range"] = [0.01, 0.05]
            cell["confidence"] = 0.3

        return cells

    @staticmethod
    def _default_format(channel: str, objective: str) -> str:
        """Channel-first, objective-second heuristic default format."""
        if channel == "instagram":
            return "carousel" if objective == "lead" else "reel"
        if channel == "linkedin":
            return "long_post" if objective == "authority" else "carousel_native"
        if channel == "tiktok":
            return "reel_short"
        if channel == "threads":
            return "thread"
        if channel == "x_twitter":
            return "thread"
        if channel == "youtube_long":
            return "long_video"
        if channel == "youtube_shorts":
            return "short_video"
        if channel == "newsletter":
            return "long_form"
        if channel == "blog_seo":
            return "long_article"
        if channel == "podcast":
            return "audio_episode"
        if channel == "telegram":
            return "broadcast_post"
        if channel == "whatsapp":
            return "broadcast_card"
        if channel == "xiaohongshu_weibo":
            return "note_post"
        if channel == "quora_reddit":
            return "qa_answer"
        return "generic_post"
