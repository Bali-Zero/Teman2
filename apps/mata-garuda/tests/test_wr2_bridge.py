"""Tests for Layer 5 WR2 Bridge Publisher (Wave 2 of W4)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def _fake_cursor_storage(initial: str = ""):
    holder = {"value": initial}

    def load():
        return holder["value"]

    def save(v):
        holder["value"] = v

    return holder, load, save


class TestWr2Filter:
    def test_accepts_wr2_domain(self):
        from mata_garuda.agents.wr2_bridge_publisher import _is_wr2_candidate

        for d in ("immigration_visa", "tax_fiscal", "investment_licensing"):
            item = {"domain": d, "title": "x"}
            assert _is_wr2_candidate(item) is True

    def test_rejects_off_domain(self):
        from mata_garuda.agents.wr2_bridge_publisher import _is_wr2_candidate

        assert _is_wr2_candidate({"domain": "property", "title": "x"}) is False
        assert _is_wr2_candidate({"domain": "ai_research", "title": "x"}) is False

    def test_rejects_empty_body(self):
        from mata_garuda.agents.wr2_bridge_publisher import _is_wr2_candidate

        assert _is_wr2_candidate({"domain": "tax_fiscal"}) is False


class TestEnvelopeBuilder:
    def test_envelope_shape(self):
        from mata_garuda.agents.wr2_bridge_publisher import (
            WR2_ENVELOPE_TYPE,
            WR2_SOURCE,
            _build_dossier_envelope,
        )

        item = {
            "_id": "1700000000-1",
            "title": "KITAS holder requirement changes",
            "content": "Imigrasi announced new...",
            "url": "https://imigrasi.go.id/news/123",
            "domain": "immigration_visa",
            "relevance_score": "5",
            "source": "regulation_watcher",
            "timestamp": "2026-04-20T12:00:00+08:00",
            "tags": "kitas,regulation",
        }
        env = _build_dossier_envelope(item)
        assert env.type == WR2_ENVELOPE_TYPE
        assert env.source == WR2_SOURCE
        assert env.priority == 2
        payload = env.payload
        assert payload["dossier_id"] == "1700000000-1"
        assert payload["domain"] == "immigration_visa"
        assert payload["relevance_score"] == 5
        assert payload["tags"] == ["kitas", "regulation"]

    def test_envelope_summary_truncates(self):
        from mata_garuda.agents.wr2_bridge_publisher import _build_dossier_envelope

        body = "x" * 3000
        env = _build_dossier_envelope(
            {
                "_id": "1",
                "title": "t",
                "content": body,
                "domain": "tax_fiscal",
                "relevance_score": "3",
            }
        )
        assert len(env.payload["summary"]) == 2000

    def test_envelope_handles_missing_tags(self):
        from mata_garuda.agents.wr2_bridge_publisher import _build_dossier_envelope

        env = _build_dossier_envelope(
            {
                "_id": "1",
                "title": "t",
                "content": "c",
                "domain": "investment_licensing",
                "relevance_score": "4",
            }
        )
        assert env.payload["tags"] == []

    def test_envelope_to_redis_dict_roundtrip(self):
        from mata_garuda.agents.wr2_bridge_publisher import _build_dossier_envelope
        from mata_garuda.bridge.envelope import Envelope

        env = _build_dossier_envelope(
            {
                "_id": "1700000000-3",
                "title": "Ok",
                "content": "body",
                "domain": "tax_fiscal",
                "relevance_score": "3",
                "url": "https://x",
            }
        )
        redis_d = env.to_redis_dict()
        restored = Envelope.from_redis_dict(redis_d)
        assert restored.type == env.type
        assert restored.payload["dossier_id"] == "1700000000-3"


class TestCycle:
    def test_no_candidates(self):
        from mata_garuda.agents.wr2_bridge_publisher import run_wr2_bridge_cycle

        _, load, save = _fake_cursor_storage()
        result = run_wr2_bridge_cycle(
            fetch_fn=lambda: [],
            publish_fn=lambda env: "ignored",
            cursor_loader=load,
            cursor_saver=save,
        )
        assert result["status"] == "no_candidates"
        assert result["published"] == 0

    def test_publishes_fresh_in_order(self):
        from mata_garuda.agents.wr2_bridge_publisher import run_wr2_bridge_cycle

        items = [
            {
                "_id": f"17000000{i:02d}-0",
                "title": f"item {i}",
                "content": "body",
                "domain": "tax_fiscal",
                "relevance_score": "4",
                "url": f"https://ex.com/{i}",
            }
            for i in range(5)
        ]
        # simulate redis XREVRANGE: newest first
        items_rev = list(reversed(items))

        published_envs = []

        def fake_publish(env):
            published_envs.append(env)
            return f"17000000{len(published_envs):02d}-99"

        _, load, save = _fake_cursor_storage()
        result = run_wr2_bridge_cycle(
            fetch_fn=lambda: items_rev,
            publish_fn=fake_publish,
            cursor_loader=load,
            cursor_saver=save,
        )
        assert result["published"] == 5
        # Verify ordering: oldest id first
        pubs = [e.payload["dossier_id"] for e in published_envs]
        assert pubs == sorted(pubs)

    def test_skips_already_published(self):
        from mata_garuda.agents.wr2_bridge_publisher import run_wr2_bridge_cycle

        items = [
            {
                "_id": "1700000000-1",
                "title": "old",
                "content": "b",
                "domain": "tax_fiscal",
                "relevance_score": "3",
            },
            {
                "_id": "1700000000-5",
                "title": "new",
                "content": "b",
                "domain": "immigration_visa",
                "relevance_score": "4",
            },
        ]
        _, load, save = _fake_cursor_storage(initial="1700000000-3")
        published = []

        def fake_publish(env):
            published.append(env)
            return "ok"

        result = run_wr2_bridge_cycle(
            fetch_fn=lambda: items,
            publish_fn=fake_publish,
            cursor_loader=load,
            cursor_saver=save,
        )
        assert result["published"] == 1
        assert published[0].payload["dossier_id"] == "1700000000-5"

    def test_stops_on_failure_preserves_cursor(self):
        from mata_garuda.agents.wr2_bridge_publisher import run_wr2_bridge_cycle

        items = [
            {
                "_id": f"17000000{i:02d}-0",
                "title": f"i{i}",
                "content": "b",
                "domain": "tax_fiscal",
                "relevance_score": "3",
            }
            for i in range(3)
        ]

        calls = {"n": 0}

        def fake_publish(env):
            calls["n"] += 1
            if calls["n"] == 2:
                return "[ERROR] simulated"
            return "ok"

        _, load, save = _fake_cursor_storage()
        result = run_wr2_bridge_cycle(
            fetch_fn=lambda: list(reversed(items)),
            publish_fn=fake_publish,
            cursor_loader=load,
            cursor_saver=save,
        )
        # One success, then failure, should have halted and advanced cursor only
        # to the first item
        assert result["published"] == 1


class TestAgentRegistration:
    def test_agent_registered(self):
        import mata_garuda.agents  # noqa: F401
        from mata_garuda.registry import registry

        assert "WR2 Bridge Publisher" in registry.agents_info

    def test_agent_layer(self):
        from mata_garuda.agents.wr2_bridge_publisher import get_wr2_bridge_publisher

        agent = get_wr2_bridge_publisher()
        assert agent.layer == "distribuzione"
        assert agent.genome_path.endswith("wr2_bridge_publisher_GENOME.md")

    def test_genome_exists(self):
        genome = (
            Path(__file__).parent.parent
            / "mata_garuda"
            / "agents"
            / "wr2_bridge_publisher_GENOME.md"
        )
        assert genome.exists()
        body = genome.read_text()
        assert "intel.research_dossier" in body

    def test_schema_doc_exists(self):
        repo_root = Path(__file__).parent.parent.parent.parent
        schema = repo_root / "docs" / "mata-garuda" / "bridge-wr2-schema.md"
        assert schema.exists(), f"Missing schema doc at {schema}"
