"""Unit tests for T4State persistence and PID lock."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from apps.evaluator.nlm_deep_research.t4_state import T4State, T4StatePersistence


class TestT4StateDefaults:
    def test_fresh_state_has_empty_seen_ids(self):
        state = T4State()
        assert state.seen_ids == set()

    def test_fresh_state_cb_closed(self):
        state = T4State()
        assert state.cb_status == "CLOSED"
        assert state.cb_failure_count == 0

    def test_fresh_state_no_active_sources(self):
        state = T4State()
        assert state.active_t4_sources == []

    def test_fresh_state_x_enabled(self):
        state = T4State()
        assert state.x_enabled is True

    def test_fresh_state_no_pid(self):
        state = T4State()
        assert state.run_lock_pid is None


class TestT4StatePersistence:
    def test_save_and_load_roundtrip(self, tmp_path):
        state_path = tmp_path / "t4_state.json"
        persistence = T4StatePersistence(state_path)

        state = T4State(
            seen_ids={"abc123", "def456"},
            active_t4_sources=["src-1", "src-2"],
            cb_status="CLOSED",
            cb_failure_count=1,
        )
        persistence.save(state)

        loaded = persistence.load()
        assert loaded.seen_ids == {"abc123", "def456"}
        assert loaded.active_t4_sources == ["src-1", "src-2"]
        assert loaded.cb_failure_count == 1

    def test_load_missing_file_returns_fresh_state(self, tmp_path):
        state_path = tmp_path / "nonexistent.json"
        persistence = T4StatePersistence(state_path)
        state = persistence.load()
        assert state.seen_ids == set()

    def test_save_creates_parent_directory(self, tmp_path):
        state_path = tmp_path / "subdir" / "t4_state.json"
        persistence = T4StatePersistence(state_path)
        persistence.save(T4State())
        assert state_path.exists()


class TestT4StateBudget:
    def test_is_over_budget_when_full(self):
        state = T4State(active_t4_sources=["s"] * 11)
        assert state.is_over_budget(max_slots=11) is True

    def test_is_not_over_budget_when_below(self):
        state = T4State(active_t4_sources=["s"] * 10)
        assert state.is_over_budget(max_slots=11) is False

    def test_evict_oldest_removes_first_entry(self):
        state = T4State(active_t4_sources=["old", "mid", "new"])
        evicted = state.evict_oldest()
        assert evicted == "old"
        assert state.active_t4_sources == ["mid", "new"]

    def test_evict_oldest_on_empty_raises(self):
        state = T4State(active_t4_sources=[])
        with pytest.raises(IndexError):
            state.evict_oldest()
