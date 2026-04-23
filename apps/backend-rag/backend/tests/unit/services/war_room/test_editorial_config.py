"""Tests for editorial_config — loads wr2_weights.json → WR2 runtime config."""

from __future__ import annotations

import json
import pytest
from pathlib import Path

from backend.services.war_room.editorial_config import (
    EditorialConfig,
    EditorialConfigNotReady,
)


def _valid_weights() -> dict:
    return {
        "persona_weight": {
            "expat_boomer_retiree": 0.25,
            "expat_techie_pma": 0.30,
            "expat_italian_aire": 0.15,
            "id_konsultan_kadin": 0.10,
            "id_founder_pma": 0.12,
            "id_umkm_digital": 0.08,
        },
        "tone_resonance": {
            "expat_techie_pma": {"tecnico": 0.4, "analitico": 0.3, "pedagogico": 0.3}
        },
        "cadence_by_channel": {
            "instagram": {"posts_per_day": 1.0, "optimal_hours_wita": [7, 12, 19]}
        },
        "format_mix_by_objective": {
            "lead": {"carousel_education": 0.4, "case_study": 0.3, "data_story": 0.3}
        },
        "publisher_enabled_by_channel": {"instagram": False},
    }


def test_load_from_file(tmp_path: Path):
    wpath = tmp_path / "w.json"
    wpath.write_text(json.dumps(_valid_weights()))
    cfg = EditorialConfig.load(wpath)
    assert cfg.cadence_for("instagram")["posts_per_day"] == 1.0
    assert cfg.weight_for("expat_techie_pma") == 0.30
    assert cfg.is_publisher_enabled("instagram") is False


def test_raises_when_file_missing(tmp_path: Path):
    with pytest.raises(EditorialConfigNotReady):
        EditorialConfig.load(tmp_path / "nope.json")


def test_unknown_channel_returns_none():
    cfg = EditorialConfig(**_valid_weights())
    assert cfg.cadence_for("unknown") is None
    assert cfg.is_publisher_enabled("unknown") is False  # safe default


def test_tone_resonance_normalized():
    cfg = EditorialConfig(**_valid_weights())
    tr = cfg.tone_for("expat_techie_pma")
    assert abs(sum(tr.values()) - 1.0) < 0.01
