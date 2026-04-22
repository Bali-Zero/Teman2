"""Cadence engine — optimal posting windows per (channel × timezone × hour).

Output shape (consumed by `06_cadence_engine.json`):
    matrix[channel][timezone][hour] = quality_score

Quality score semantic:
    1.5 — inside the literature-derived optimal window
    1.0 — ±1 hour from the optimal window (acceptable)
    0.8 — outside the window (sub-optimal but not forbidden)

Timezones:
    WITA   = UTC+8 (Bali local)
    GMT+1  = European expat
    GMT+8  = China + Singapore + other East Asia expat

Base windows (hours in the audience's LOCAL timezone) derived from the
literature synthesis (Task 12, section `03_cadence_algorithm_2026`).
Conservative defaults — Consiglio v1 can refine per (channel × persona)
in Task 20, writing a v1 override file alongside v0.
"""

from __future__ import annotations

from typing import Any

CHANNELS: list[str] = [
    "instagram", "linkedin", "tiktok", "threads", "x_twitter",
    "youtube_long", "youtube_shorts", "telegram", "whatsapp",
    "newsletter", "blog_seo", "podcast", "xiaohongshu_weibo", "quora_reddit",
]
TIMEZONES: list[str] = ["WITA", "GMT+1", "GMT+8"]

# Base windows per channel — hours (0-23) in the audience's LOCAL tz.
_BASE_WINDOWS: dict[str, list[int]] = {
    "instagram":         [7, 12, 19, 21],
    "linkedin":          [7, 8, 12, 17],
    "tiktok":            [18, 19, 20, 21, 22],
    "threads":           [7, 19, 22],
    "x_twitter":         [8, 12, 17, 22],
    "youtube_long":      [19, 20, 21],
    "youtube_shorts":    [17, 18, 19, 20, 21],
    "telegram":          [8, 12, 18],
    "whatsapp":          [9, 12, 16],
    "newsletter":        [8, 17],
    "blog_seo":          [10, 11],
    "podcast":           [7, 18],
    "xiaohongshu_weibo": [12, 19, 21],
    "quora_reddit":      [10, 14, 21],
}


def _score_hour(hour: int, window: list[int]) -> float:
    if hour in window:
        return 1.5
    if any(abs(hour - w) == 1 for w in window):
        return 1.0
    return 0.8


def build_cadence_matrix() -> dict[str, Any]:
    """Build the full 14 × 3 × 24 matrix with deterministic output."""
    matrix: dict[str, Any] = {}
    for channel in CHANNELS:
        base = _BASE_WINDOWS.get(channel, [])
        matrix[channel] = {
            tz: {str(hour): _score_hour(hour, base) for hour in range(24)}
            for tz in TIMEZONES
        }
    return {
        "version": "v0-literature-derived",
        "matrix": matrix,
        "channels": CHANNELS,
        "timezones": TIMEZONES,
        "notes": (
            "Hours are in each timezone's LOCAL time. Score 1.5 = optimal "
            "window, 1.0 = ±1h, 0.8 = outside. Consiglio v1 (Task 20) can "
            "publish a v1 override with per-persona refinements."
        ),
    }
