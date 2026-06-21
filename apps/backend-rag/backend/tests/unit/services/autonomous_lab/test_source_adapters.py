from __future__ import annotations

import json
from datetime import datetime, timezone

from backend.services.autonomous_lab.source_adapters import (
    SOURCE_ADAPTER_CONTRACT_VERSION,
    build_shadow_watchtower_tick,
    default_source_adapters,
)


def test_shadow_watchtower_tick_is_metadata_only_and_deterministic() -> None:
    tick = build_shadow_watchtower_tick(
        objective="study AI coding agents for Nuzantara",
        captured_at=datetime(2026, 6, 16, tzinfo=timezone.utc),
    )
    receipt = tick.to_receipt()
    receipt_text = json.dumps(receipt, sort_keys=True)

    assert receipt["version"] == SOURCE_ADAPTER_CONTRACT_VERSION
    assert receipt["signal_count"] == 3
    assert receipt["external_calls"] == 0
    assert len(receipt["adapters"]) == len(default_source_adapters())
    assert "study AI coding agents for Nuzantara" not in receipt_text
    assert "objective_fingerprint:sha256:" in receipt_text


def test_shadow_watchtower_materials_feed_planner_without_network() -> None:
    tick = build_shadow_watchtower_tick(objective="source adapter test")
    materials = tick.materials()

    assert len(materials) == 3
    assert all(material.material_id.startswith("signal-") for material in materials)
    assert all("Shadow material is generated from metadata only." in material.text for material in materials)
