"""Tests for hexagram 6-bit dashboard."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from apps.evaluator.nlm_deep_research.hexagram import (
    KING_WEN,
    _dim_balance,
    _dim_consciousness,
    _dim_health,
    _dim_ingest,
    _dim_memory,
    _dim_service,
    append_state,
    binary_to_hexagram,
    compute_for_nb,
    derive_lines,
    lines_to_binary,
    render_ascii,
)


# ── King Wen table integrity ─────────────────────────────────────────────────


def test_king_wen_has_64_entries() -> None:
    assert len(KING_WEN) == 64


def test_king_wen_binary_keys_are_all_6_bits() -> None:
    for key in KING_WEN:
        assert len(key) == 6
        assert all(c in "01" for c in key)


def test_king_wen_numbers_are_unique_1_to_64() -> None:
    numbers = sorted(entry[0] for entry in KING_WEN.values())
    assert numbers == list(range(1, 65))


def test_king_wen_pure_yang_is_qian() -> None:
    assert KING_WEN["111111"][0] == 1
    assert KING_WEN["111111"][2] == "Qián"


def test_king_wen_pure_yin_is_kun() -> None:
    assert KING_WEN["000000"][0] == 2
    assert KING_WEN["000000"][2] == "Kūn"


# ── Binary <-> hexagram ──────────────────────────────────────────────────────


def test_binary_to_hexagram_valid() -> None:
    out = binary_to_hexagram("111111")
    assert out["valid"] is True
    assert out["king_wen"] == 1
    assert out["pinyin"] == "Qián"


def test_binary_to_hexagram_invalid_length() -> None:
    out = binary_to_hexagram("10101")
    assert out["valid"] is False


def test_binary_to_hexagram_non_binary_chars() -> None:
    out = binary_to_hexagram("10101x")
    assert out["valid"] is False


# ── Dimensions ───────────────────────────────────────────────────────────────


def test_dim_ingest_yang_when_fresh() -> None:
    ts = (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat()
    assert _dim_ingest({"available": True, "last_updated": ts}) == 1


def test_dim_ingest_yin_when_stale() -> None:
    ts = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()
    assert _dim_ingest({"available": True, "last_updated": ts}) == 0


def test_dim_ingest_yin_when_unavailable() -> None:
    assert _dim_ingest({"available": False}) == 0


def test_dim_ingest_yin_on_malformed_timestamp() -> None:
    assert _dim_ingest({"available": True, "last_updated": "nope"}) == 0


def test_dim_health_yang_above_threshold() -> None:
    assert _dim_health({"available": True, "offered": 7}) == 1


def test_dim_health_yin_below_threshold() -> None:
    assert _dim_health({"available": True, "offered": 3}) == 0


def test_dim_health_yin_when_unavailable() -> None:
    assert _dim_health({"available": False}) == 0


def test_dim_balance_yang_only_when_healthy() -> None:
    assert _dim_balance({"available": True, "status": "HEALTHY"}) == 1
    assert _dim_balance({"available": True, "status": "YANG_FLOOD"}) == 0
    assert _dim_balance({"available": True, "status": "YIN_FAMINE"}) == 0


def test_dim_memory_yang_requires_weekly_source() -> None:
    assert _dim_memory({"available": True, "weekly_sources_count": 1}) == 1
    assert _dim_memory({"available": True, "weekly_sources_count": 0}) == 0


def test_dim_service_yang_above_cite_threshold() -> None:
    assert _dim_service({"available": True, "global_cite_rate": 0.20}) == 1
    assert _dim_service({"available": True, "global_cite_rate": 0.10}) == 0
    assert _dim_service({"available": True, "global_cite_rate": None}) == 0


def test_dim_consciousness_yang_when_heartbeat_fresh() -> None:
    assert _dim_consciousness({"available": True, "age_hours": 5.0}) == 1
    assert _dim_consciousness({"available": True, "age_hours": 48.0}) == 0
    assert _dim_consciousness({"available": True, "age_hours": None}) == 0


# ── Lines + binary ───────────────────────────────────────────────────────────


def test_derive_lines_all_yang_snapshot() -> None:
    fresh_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    snap = {
        "jagrat": {"available": True, "last_updated": fresh_ts},
        "yajna": {"available": True, "offered": 20, "global_cite_rate": 0.3},
        "yin_yang": {"available": True, "status": "HEALTHY"},
        "sushupti": {"available": True, "weekly_sources_count": 2},
        "heartbeat": {"available": True, "age_hours": 2.0},
    }
    lines = derive_lines(snap)
    assert all(v == 1 for v in lines.values())
    assert lines_to_binary(lines) == "111111"


def test_derive_lines_all_yin_snapshot() -> None:
    snap = {
        "jagrat": {"available": False},
        "yajna": {"available": False},
        "yin_yang": {"available": False},
        "sushupti": {"available": False},
        "heartbeat": {"available": False},
    }
    lines = derive_lines(snap)
    assert all(v == 0 for v in lines.values())
    assert lines_to_binary(lines) == "000000"


# ── render_ascii ─────────────────────────────────────────────────────────────


def test_render_ascii_six_rows() -> None:
    out = render_ascii("111111")
    assert len(out.splitlines()) == 6


def test_render_ascii_distinguishes_yin_yang() -> None:
    yang_only = render_ascii("111111")
    yin_only = render_ascii("000000")
    assert yang_only != yin_only


def test_render_ascii_invalid_returns_placeholder() -> None:
    assert render_ascii("bogus") == "(invalid)"


# ── compute + append ─────────────────────────────────────────────────────────


def test_compute_for_nb_all_unavailable(tmp_path: Path) -> None:
    # When state files missing, should still produce a well-formed entry
    entry = compute_for_nb("nb4", evaluator_root=tmp_path, heartbeat_dir=tmp_path)
    assert entry["nb"] == "nb4"
    assert entry["binary"] == "000000"
    assert entry["hexagram"]["king_wen"] == 2  # Kun
    assert entry["hexagram"]["pinyin"] == "Kūn"


def test_append_state_writes_jsonl(tmp_path: Path) -> None:
    state_file = tmp_path / "hexagram_state.jsonl"
    entries = [{"nb": "nb4", "binary": "111111", "ts": "2026-04-22T00:00Z"}]
    count = append_state(entries, state_file=state_file)
    assert count == 1
    assert state_file.exists()
    lines = state_file.read_text().strip().split("\n")
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["nb"] == "nb4"
