"""Tests for Layer 5 Kita Feed Generator (Wave 2 of W4)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


WITA = timezone(timedelta(hours=8))


class TestKitaFilter:
    def test_accepts_qualifying(self):
        from mata_garuda.agents.kita_feed_generator import _is_kita_eligible

        assert _is_kita_eligible(
            {
                "public_safe": "true",
                "relevance_score": "4",
                "title": "Hello",
            }
        )

    def test_rejects_private(self):
        from mata_garuda.agents.kita_feed_generator import _is_kita_eligible

        assert not _is_kita_eligible(
            {
                "public_safe": "false",
                "relevance_score": "5",
                "title": "t",
            }
        )

    def test_rejects_low_score(self):
        from mata_garuda.agents.kita_feed_generator import _is_kita_eligible

        assert not _is_kita_eligible(
            {"public_safe": "true", "relevance_score": "2", "title": "t"}
        )

    def test_rejects_missing_title(self):
        from mata_garuda.agents.kita_feed_generator import _is_kita_eligible

        assert not _is_kita_eligible(
            {"public_safe": "true", "relevance_score": "5"}
        )


class TestBuildFeed:
    def test_sorts_by_score_desc_then_time_desc(self):
        from mata_garuda.agents.kita_feed_generator import build_feed

        items = [
            {
                "_id": f"17000000{i}-0",
                "title": f"t{i}",
                "content": "c",
                "public_safe": "true",
                "relevance_score": str(score),
                "domain": "immigration_visa",
                "timestamp": f"2026-04-{20 - i:02d}T12:00:00+08:00",
            }
            for i, score in enumerate([3, 5, 4, 5, 3])
        ]

        feed = build_feed(
            fetch_fn=lambda: items,
            now=datetime(2026, 4, 20, 12, 0, tzinfo=WITA),
        )
        scores = [it["relevance_score"] for it in feed["items"]]
        assert scores == sorted(scores, reverse=True)
        # Top two should be the two 5s
        assert scores[0] == 5 and scores[1] == 5

    def test_caps_at_max(self):
        from mata_garuda.agents.kita_feed_generator import MAX_ITEMS, build_feed

        many = [
            {
                "_id": f"1700000{i:04d}-0",
                "title": f"t{i}",
                "content": "c",
                "public_safe": "true",
                "relevance_score": "5",
                "timestamp": "2026-04-20T12:00:00+08:00",
            }
            for i in range(MAX_ITEMS + 10)
        ]
        feed = build_feed(fetch_fn=lambda: many)
        assert feed["count"] == MAX_ITEMS

    def test_feed_entry_fields(self):
        from mata_garuda.agents.kita_feed_generator import build_feed

        feed = build_feed(
            fetch_fn=lambda: [
                {
                    "_id": "X-0",
                    "title": "Hello",
                    "content": "body",
                    "url": "https://ex.com",
                    "public_safe": "true",
                    "relevance_score": "4",
                    "domain": "tax_fiscal",
                    "source": "regulation_watcher",
                    "timestamp": "2026-04-20T10:00:00+08:00",
                }
            ],
            now=datetime(2026, 4, 20, 12, 0, tzinfo=WITA),
        )
        assert feed["version"] == 1
        assert feed["count"] == 1
        entry = feed["items"][0]
        assert entry["title"] == "Hello"
        assert entry["url"] == "https://ex.com"
        assert entry["domain"] == "tax_fiscal"
        assert entry["relevance_score"] == 4


class TestWriteFeed:
    def test_write_produces_valid_json(self, tmp_path: Path):
        from mata_garuda.agents.kita_feed_generator import run_kita_feed_cycle

        feed_path = tmp_path / "kita_feed.json"

        items = [
            {
                "_id": "X-0",
                "title": "Hello",
                "content": "body",
                "public_safe": "true",
                "relevance_score": "4",
                "domain": "immigration_visa",
                "timestamp": "2026-04-20T10:00:00+08:00",
            }
        ]
        result = run_kita_feed_cycle(
            fetch_fn=lambda: items,
            path=feed_path,
            now=datetime(2026, 4, 20, 12, 0, tzinfo=WITA),
        )
        assert result["status"] == "ok"
        assert feed_path.exists()
        data = json.loads(feed_path.read_text())
        assert data["count"] == 1
        assert data["items"][0]["title"] == "Hello"

    def test_write_is_atomic(self, tmp_path: Path):
        """Temp file must not linger after successful write."""
        from mata_garuda.agents.kita_feed_generator import run_kita_feed_cycle

        feed_path = tmp_path / "kita_feed.json"
        run_kita_feed_cycle(fetch_fn=lambda: [], path=feed_path)
        assert not feed_path.with_suffix(".json.tmp").exists()


class TestAgentRegistration:
    def test_agent_registered(self):
        import mata_garuda.agents  # noqa: F401
        from mata_garuda.registry import registry

        assert "Kita Feed Generator" in registry.agents_info

    def test_agent_layer(self):
        from mata_garuda.agents.kita_feed_generator import get_kita_feed_generator

        agent = get_kita_feed_generator()
        assert agent.layer == "distribuzione"
        assert agent.genome_path.endswith("kita_feed_generator_GENOME.md")
