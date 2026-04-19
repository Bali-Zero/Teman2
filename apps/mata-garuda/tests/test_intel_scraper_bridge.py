"""Tests for intel_scraper_bridge agent and tools."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from mata_garuda.agents.intel_scraper_bridge import bridge_intel_scraper
from mata_garuda.tools import intel_scraper_tools as ist


def _write_articles(dir_path: Path, items: list[dict]) -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    target = dir_path / ist.PUBLISHED_FILE
    target.write_text(
        json.dumps({"articles": items}, ensure_ascii=False),
        encoding="utf-8",
    )
    return target


def test_read_published_articles_missing_file(tmp_path, monkeypatch):
    monkeypatch.setenv("BALI_INTEL_SCRAPER_DATA_DIR", str(tmp_path))
    assert ist.read_published_articles() == []


def test_read_published_articles_malformed_json(tmp_path, monkeypatch):
    (tmp_path / ist.PUBLISHED_FILE).write_text("{not json", encoding="utf-8")
    monkeypatch.setenv("BALI_INTEL_SCRAPER_DATA_DIR", str(tmp_path))
    assert ist.read_published_articles() == []


def test_read_published_articles_happy(tmp_path, monkeypatch):
    _write_articles(
        tmp_path,
        [
            {
                "url": "https://example.com/a",
                "title": "A",
                "published_at": "2026-04-20T01:00:00",
            },
            {"title": "no url — dropped"},
        ],
    )
    monkeypatch.setenv("BALI_INTEL_SCRAPER_DATA_DIR", str(tmp_path))
    out = ist.read_published_articles()
    assert len(out) == 1
    assert out[0]["url"] == "https://example.com/a"


def test_filter_recent_lexicographic():
    items = [
        {"url": "u1", "published_at": "2026-04-19T00:00:00"},
        {"url": "u2", "published_at": "2026-04-20T12:00:00"},
        {"url": "u3"},
    ]
    cut = "2026-04-20T00:00:00"
    out = ist.filter_recent(items, cut)
    assert [a["url"] for a in out] == ["u2"]


def test_bridge_publishes_to_garuda_raw(tmp_path, monkeypatch):
    _write_articles(
        tmp_path,
        [
            {
                "url": "https://example.com/new",
                "title": "Fresh piece",
                "published_at": "2999-01-01T00:00:00",  # always in window
            }
        ],
    )
    monkeypatch.setenv("BALI_INTEL_SCRAPER_DATA_DIR", str(tmp_path))

    with patch(
        "mata_garuda.agents.intel_scraper_bridge.stream_publish_redis",
        return_value="1-0",
    ) as fake_publish:
        result = bridge_intel_scraper()

    assert result["case_resolved"] is True
    assert result["published"] == 1
    fake_publish.assert_called_once()
    stream, fields = fake_publish.call_args.args
    assert stream == "garuda:raw"
    assert fields["agent"] == "intel_scraper_bridge"
    assert fields["source_agent"] == "intel_scraper_bridge"
    assert fields["source_type"] == "intel_scraper"
    assert fields["url"] == "https://example.com/new"
    assert fields["source"] == "example.com"


def test_bridge_no_recent_items(tmp_path, monkeypatch):
    _write_articles(
        tmp_path,
        [
            {
                "url": "https://example.com/old",
                "title": "old",
                "published_at": "1970-01-01T00:00:00",
            }
        ],
    )
    monkeypatch.setenv("BALI_INTEL_SCRAPER_DATA_DIR", str(tmp_path))

    with patch(
        "mata_garuda.agents.intel_scraper_bridge.stream_publish_redis"
    ) as fake_publish:
        result = bridge_intel_scraper(window_hours=1)

    assert result["case_resolved"] is False
    assert result["published"] == 0
    assert "no items newer" in result["reason"]
    fake_publish.assert_not_called()


def test_bridge_file_missing(tmp_path, monkeypatch):
    # Empty dir → no file
    monkeypatch.setenv("BALI_INTEL_SCRAPER_DATA_DIR", str(tmp_path))
    with patch(
        "mata_garuda.agents.intel_scraper_bridge.stream_publish_redis"
    ) as fake_publish:
        result = bridge_intel_scraper()
    assert result["case_resolved"] is False
    assert "missing" in result["reason"].lower() or "empty" in result["reason"].lower()
    fake_publish.assert_not_called()


def test_agent_registered_and_has_genome():
    import mata_garuda.agents.intel_scraper_bridge  # noqa: F401
    from mata_garuda.registry import get_agent

    agent = get_agent("intel_scraper_bridge")
    assert agent is not None
    assert agent.layer == "harvester"
    fn_names = {fn.__name__ for fn in agent.functions}
    assert "bridge_intel_scraper" in fn_names
    assert "case_resolved" in fn_names
    assert "case_not_resolved" in fn_names

    genome = (
        Path(__file__).parent.parent
        / "mata_garuda" / "agents" / "intel_scraper_bridge_GENOME.md"
    )
    assert genome.exists()
    text = genome.read_text()
    assert "garuda:raw" in text
    assert "OSINT blindato" in text
