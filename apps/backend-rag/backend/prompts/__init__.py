"""
Prompts package for Nuzantara AI.

Single source of truth: zantara_core.py
Channel configs: channel_overlays.py
Few-shot examples: few_shot_examples.py
"""

from backend.prompts.zantara_core import (
    CREATOR_PERSONA,
    TEAM_PERSONA,
    ZANTARA_MASTER_TEMPLATE,
)

__all__ = [
    "ZANTARA_MASTER_TEMPLATE",
    "CREATOR_PERSONA",
    "TEAM_PERSONA",
]
