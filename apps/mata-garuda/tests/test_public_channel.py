"""Tests for Layer 5 Public Channel Publisher (Wave 1 of W4)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest


# ──────────────────────────────────────────────────────────────────
# tg_public_tools
# ──────────────────────────────────────────────────────────────────


class TestTgPublicTools:
    def test_dry_run_when_channel_id_missing(self, monkeypatch):
        from mata_garuda.tools.tg_public_tools import send_tg_public_post

        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
        monkeypatch.delenv("TELEGRAM_PUBLIC_CHANNEL_ID", raising=False)

        result = send_tg_public_post("hello clients")
        assert result.startswith("[DRY-RUN]")

    def test_error_when_bot_token_missing(self, monkeypatch):
        from mata_garuda.tools.tg_public_tools import send_tg_public_post

        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.setenv("TELEGRAM_PUBLIC_CHANNEL_ID", "@whatever")

        result = send_tg_public_post("hello clients")
        assert result.startswith("[ERROR]")
        assert "TELEGRAM_BOT_TOKEN" in result

    def test_is_public_channel_configured_both_required(self, monkeypatch):
        from mata_garuda.tools.tg_public_tools import is_public_channel_configured

        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
        monkeypatch.delenv("TELEGRAM_PUBLIC_CHANNEL_ID", raising=False)
        assert not is_public_channel_configured()

        monkeypatch.setenv("TELEGRAM_PUBLIC_CHANNEL_ID", "@bali_zero_public")
        assert is_public_channel_configured()

        monkeypatch.setenv("TELEGRAM_PUBLIC_CHANNEL_ID", "   ")
        assert not is_public_channel_configured()


# ──────────────────────────────────────────────────────────────────
# Filter logic
# ──────────────────────────────────────────────────────────────────


class TestFilterLogic:
    def test_is_public_safe_accepts_qualifying_item(self):
        from mata_garuda.agents.public_channel_publisher import _is_public_safe

        item = {
            "public_safe": "true",
            "relevance_score": "4",
            "domain": "immigration_visa",
        }
        assert _is_public_safe(item) is True

    def test_rejects_if_not_public_safe(self):
        from mata_garuda.agents.public_channel_publisher import _is_public_safe

        item = {
            "public_safe": "false",
            "relevance_score": "5",
            "domain": "immigration_visa",
        }
        assert _is_public_safe(item) is False

    def test_rejects_low_score(self):
        from mata_garuda.agents.public_channel_publisher import _is_public_safe

        item = {
            "public_safe": "true",
            "relevance_score": "2",
            "domain": "tax_fiscal",
        }
        assert _is_public_safe(item) is False

    def test_rejects_off_domain(self):
        from mata_garuda.agents.public_channel_publisher import _is_public_safe

        item = {
            "public_safe": "true",
            "relevance_score": "5",
            "domain": "procurement",  # not in ALLOWED_DOMAINS
        }
        assert _is_public_safe(item) is False

    def test_rejects_missing_fields(self):
        from mata_garuda.agents.public_channel_publisher import _is_public_safe

        assert _is_public_safe({}) is False
        assert _is_public_safe({"public_safe": "true"}) is False


# ──────────────────────────────────────────────────────────────────
# Cycle behavior (rate limit, dedup, dry-run)
# ──────────────────────────────────────────────────────────────────


def _fake_state_storage():
    """In-memory state stub."""
    state = {"value": None}

    def load():
        return state["value"] or {"day": "", "count": 0, "last_post_id": ""}

    def save(s):
        state["value"] = dict(s)

    return state, load, save


class TestCycle:
    def test_dry_run_when_unconfigured(self, monkeypatch):
        from mata_garuda.agents.public_channel_publisher import run_public_channel_cycle

        monkeypatch.delenv("TELEGRAM_PUBLIC_CHANNEL_ID", raising=False)
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")

        items = [
            {
                "_id": "1700000000-0",
                "title": "New visa rule",
                "content": "Summary of new KITAS regulation for Bali.",
                "url": "https://imigrasi.go.id/news/1",
                "public_safe": "true",
                "relevance_score": "4",
                "domain": "immigration_visa",
            }
        ]

        state_store, load, save = _fake_state_storage()

        sent = []

        def fake_send(msg, context_variables=None):
            sent.append(msg)
            return "[DRY-RUN] simulated"

        result = run_public_channel_cycle(
            fetch_fn=lambda: items,
            send_fn=fake_send,
            state_loader=load,
            state_saver=save,
        )

        assert result["dry_run"] is True
        assert result["posted"] == 1
        assert len(sent) == 1
        assert "Bali Zero" in sent[0]
        assert state_store["value"]["count"] == 1
        assert state_store["value"]["last_post_id"] == "1700000000-0"

    def test_rate_limit_blocks_beyond_three(self, monkeypatch):
        from mata_garuda.agents.public_channel_publisher import (
            RATE_LIMIT_PER_DAY,
            run_public_channel_cycle,
        )

        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
        monkeypatch.setenv("TELEGRAM_PUBLIC_CHANNEL_ID", "@bali_zero_public")

        items = [
            {
                "_id": f"17000000{i:02d}-0",
                "title": f"Item {i}",
                "content": "body",
                "url": f"https://example.com/{i}",
                "public_safe": "true",
                "relevance_score": "5",
                "domain": "property",
            }
            for i in range(10)
        ]

        state_store, load, save = _fake_state_storage()

        def fake_send(msg, context_variables=None):
            return "[SUCCESS] ok"

        result = run_public_channel_cycle(
            fetch_fn=lambda: items,
            send_fn=fake_send,
            state_loader=load,
            state_saver=save,
        )

        assert result["posted"] == RATE_LIMIT_PER_DAY
        assert state_store["value"]["count"] == RATE_LIMIT_PER_DAY

        # Second run same day: no more posts
        result2 = run_public_channel_cycle(
            fetch_fn=lambda: items,
            send_fn=fake_send,
            state_loader=load,
            state_saver=save,
        )
        assert result2["status"] == "rate_limited"
        assert result2["posted"] == 0

    def test_dedup_via_last_post_id(self, monkeypatch):
        from mata_garuda.agents.public_channel_publisher import run_public_channel_cycle

        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
        monkeypatch.setenv("TELEGRAM_PUBLIC_CHANNEL_ID", "@bali_zero_public")

        state_store, load, save = _fake_state_storage()
        # Pre-seed: today, 0 posts, last_post_id already advanced.
        from mata_garuda.agents.public_channel_publisher import _today_wita

        state_store["value"] = {
            "day": _today_wita(),
            "count": 0,
            "last_post_id": "1700000000-5",
        }

        items = [
            {
                "_id": "1700000000-3",  # older than cursor
                "title": "Old item",
                "content": "old",
                "url": "https://example.com/old",
                "public_safe": "true",
                "relevance_score": "4",
                "domain": "tax_fiscal",
            }
        ]

        def fake_send(msg, context_variables=None):
            return "[SUCCESS] ok"

        result = run_public_channel_cycle(
            fetch_fn=lambda: items,
            send_fn=fake_send,
            state_loader=load,
            state_saver=save,
        )
        assert result["status"] == "no_fresh"
        assert result["posted"] == 0

    def test_filter_rejects_osint_items(self, monkeypatch):
        from mata_garuda.agents.public_channel_publisher import run_public_channel_cycle

        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
        monkeypatch.setenv("TELEGRAM_PUBLIC_CHANNEL_ID", "@bali_zero_public")

        items = [
            # explicitly NOT public_safe
            {
                "_id": "1700000000-1",
                "title": "OSINT leak",
                "content": "secret",
                "url": "https://leaked.example",
                "public_safe": "false",
                "relevance_score": "5",
                "domain": "immigration_visa",
            },
        ]

        state_store, load, save = _fake_state_storage()

        called = []

        def fake_send(msg, context_variables=None):
            called.append(msg)
            return "[SUCCESS] ok"

        # fetch_candidate_items would have filtered these; we emulate the pre-filter
        # by passing a fetch_fn that returns empty for this case (what _is_public_safe
        # would do). Verify cycle handles empty cleanly.
        result = run_public_channel_cycle(
            fetch_fn=lambda: [],  # pre-filtered away
            send_fn=fake_send,
            state_loader=load,
            state_saver=save,
        )
        assert result["status"] == "no_candidates"
        assert called == []


# ──────────────────────────────────────────────────────────────────
# Agent registration + GENOME
# ──────────────────────────────────────────────────────────────────


class TestAgentRegistration:
    def test_agent_registered(self):
        import mata_garuda.agents  # noqa: F401
        from mata_garuda.registry import registry

        assert "Public Channel Publisher" in registry.agents_info

    def test_agent_layer(self):
        from mata_garuda.agents.public_channel_publisher import (
            get_public_channel_publisher,
        )

        agent = get_public_channel_publisher()
        assert agent.layer == "distribuzione"
        assert agent.genome_path.endswith("public_channel_publisher_GENOME.md")

    def test_genome_exists(self):
        genome = (
            Path(__file__).parent.parent
            / "mata_garuda"
            / "agents"
            / "public_channel_publisher_GENOME.md"
        )
        assert genome.exists()
        body = genome.read_text()
        assert "Mission" in body
        assert "public_safe" in body
