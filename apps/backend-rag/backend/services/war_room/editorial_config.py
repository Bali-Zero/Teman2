"""EditorialConfig — WR2 runtime configuration loaded from 09_wr2_weights.json.

Injected at WR2 startup. Council reads persona_weight + tone_resonance
to select draft target. Publisher checks is_publisher_enabled per channel.

Location of weights file: research/sota-social-2026-v1/09_wr2_weights.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


class EditorialConfigNotReady(FileNotFoundError):
    """Raised when WR2 tries to use editorial config before Consiglio ran."""


@dataclass
class EditorialConfig:
    persona_weight: dict[str, float] = field(default_factory=dict)
    tone_resonance: dict[str, dict[str, float]] = field(default_factory=dict)
    cadence_by_channel: dict[str, dict] = field(default_factory=dict)
    format_mix_by_objective: dict[str, dict[str, float]] = field(default_factory=dict)
    publisher_enabled_by_channel: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "EditorialConfig":
        if not path.is_file():
            raise EditorialConfigNotReady(
                f"Editorial config not found at {path}. "
                "Run Consiglio v1 (sota_consiglio_playbook.py --wave=final) first."
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            **{
                k: data.get(k, {})
                for k in (
                    "persona_weight",
                    "tone_resonance",
                    "cadence_by_channel",
                    "format_mix_by_objective",
                    "publisher_enabled_by_channel",
                )
            }
        )

    def cadence_for(self, channel: str) -> dict | None:
        return self.cadence_by_channel.get(channel)

    def weight_for(self, slug: str) -> float:
        """Return persona weight (renamed from `persona_weight(slug)` to
        avoid shadowing the dataclass field of the same name)."""
        return float(self.persona_weight.get(slug, 0.0))

    def is_publisher_enabled(self, channel: str) -> bool:
        return bool(self.publisher_enabled_by_channel.get(channel, False))

    def tone_for(self, persona_slug: str) -> dict[str, float]:
        """Return normalized tone resonance distribution for a persona."""
        raw = dict(self.tone_resonance.get(persona_slug, {}))
        total = sum(raw.values())
        if total == 0:
            return {}
        return {k: v / total for k, v in raw.items()}
