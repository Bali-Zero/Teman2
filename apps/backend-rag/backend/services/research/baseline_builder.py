"""Baseline builder — assembles 00_baseline.json from sensor outputs.

Gate 1 (Fase 0 EOD day 1): ≥20 numeric metrics in baseline.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass
class BaselineSnapshot:
    """One full cross-source snapshot of Bali Zero's reach + funnel state."""

    captured_at: str  # ISO-8601 UTC
    gsc: dict[str, Any]
    ga4: dict[str, Any]
    instagram: dict[str, Any]
    brevo: dict[str, Any]
    ahrefs: dict[str, Any]
    crm: dict[str, Any]

    def metric_count(self) -> int:
        """Count numeric scalars across every nested dict (Gate 1 invariant)."""
        count = 0
        for section in (self.gsc, self.ga4, self.instagram, self.brevo, self.ahrefs, self.crm):
            for value in section.values():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    count += 1
        return count


class BaselineBuilder:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir

    def build_and_persist(self, snap: BaselineSnapshot) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.output_dir / "00_baseline.json"
        out_path.write_text(json.dumps(asdict(snap), indent=2), encoding="utf-8")
        return out_path
