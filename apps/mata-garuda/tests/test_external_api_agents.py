"""Tests for Exa / Tavily / Reddit external-API agents.

Mocks the per-tool HTTP layer; verifies each agent publishes to
garuda:raw with the right source_type and degrades gracefully when
API keys are missing or calls fail.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from mata_garuda.agents.exa_search_agent import run_exa_batch
from mata_garuda.agents.reddit_listener_agent import run_reddit_listen
from mata_garuda.agents.tavily_research_agent import run_tavily_batch
from mata_garuda.tools import reddit_tools as rt


# ── Exa ────────────────────────────────────────────────────────────────


def test_exa_agent_missing_key(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    with patch(
        "mata_garuda.agents.exa_search_agent.stream_publish_redis"
    ) as fake_publish:
        result = run_exa_batch(queries=["q1"])
    assert result["case_resolved"] is False
    assert "EXA_API_KEY missing" in result["reason"]
    fake_publish.assert_not_called()


def test_exa_agent_publishes(monkeypatch):
    fake_ok = {
        "ok": True,
        "results": [
            {"url": "https://example.com/a", "title": "A", "text": "snippet"},
            {"url": "https://example.com/b", "title": "B", "text": ""},
        ],
        "reason": "",
    }
    with patch(
        "mata_garuda.agents.exa_search_agent.run_exa_search",
        return_value=fake_ok,
    ), patch(
        "mata_garuda.agents.exa_search_agent.stream_publish_redis",
        return_value="1-0",
    ) as fake_publish:
        result = run_exa_batch(queries=["q1"])
    assert result["case_resolved"] is True
    assert result["published"] == 2
    # Verify stream + source markers on first call
    stream, fields = fake_publish.call_args_list[0].args
    assert stream == "garuda:raw"
    assert fields["source"] == "exa.ai"
    assert fields["source_type"] == "exa"
    assert fields["source_agent"] == "exa_search_agent"
    assert fields["query"] == "q1"


def test_exa_agent_registered_with_genome():
    import mata_garuda.agents.exa_search_agent  # noqa: F401
    from mata_garuda.registry import get_agent

    agent = get_agent("exa_search_agent")
    assert agent is not None
    assert agent.layer == "harvester"
    genome = Path(mata_garuda.agents.exa_search_agent.__file__).parent / "exa_search_agent_GENOME.md"
    assert genome.exists()


# ── Tavily ─────────────────────────────────────────────────────────────


def test_tavily_agent_missing_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with patch(
        "mata_garuda.agents.tavily_research_agent.stream_publish_redis"
    ) as fake_publish:
        result = run_tavily_batch(queries=["q1"])
    assert result["case_resolved"] is False
    assert "TAVILY_API_KEY missing" in result["reason"]
    fake_publish.assert_not_called()


def test_tavily_agent_publishes():
    fake_ok = {
        "ok": True,
        "results": [
            {"url": "https://example.com/t", "title": "T", "content": "x"},
        ],
        "reason": "",
    }
    with patch(
        "mata_garuda.agents.tavily_research_agent.run_tavily_search",
        return_value=fake_ok,
    ), patch(
        "mata_garuda.agents.tavily_research_agent.stream_publish_redis",
        return_value="1-0",
    ) as fake_publish:
        result = run_tavily_batch(queries=["q1"])
    assert result["case_resolved"] is True
    assert result["published"] == 1
    stream, fields = fake_publish.call_args.args
    assert stream == "garuda:raw"
    assert fields["source"] == "tavily.com"
    assert fields["source_type"] == "tavily"
    assert fields["source_agent"] == "tavily_research_agent"


def test_tavily_agent_registered_with_genome():
    import mata_garuda.agents.tavily_research_agent  # noqa: F401
    from mata_garuda.registry import get_agent

    agent = get_agent("tavily_research_agent")
    assert agent is not None
    assert agent.layer == "harvester"
    genome = Path(mata_garuda.agents.tavily_research_agent.__file__).parent / "tavily_research_agent_GENOME.md"
    assert genome.exists()


# ── Reddit ─────────────────────────────────────────────────────────────


def test_reddit_keyword_filter():
    posts = [
        {"title": "Visa issue in Bali", "selftext": ""},
        {"title": "Beach photos", "selftext": "sunset"},
        {"title": "Tax rules", "selftext": ""},
    ]
    out = rt.filter_keywords(posts, ["visa", "tax"])
    titles = [p["title"] for p in out]
    assert "Visa issue in Bali" in titles
    assert "Tax rules" in titles
    assert "Beach photos" not in titles


def test_reddit_agent_publishes():
    fake_ok = {
        "ok": True,
        "posts": [
            {
                "title": "Help with KITAS extension",
                "url": "https://www.reddit.com/r/bali/comments/abc/foo",
                "subreddit": "bali",
                "selftext": "I need KITAS info",
            },
            {
                "title": "Best beach",
                "url": "https://www.reddit.com/r/bali/comments/xyz/foo",
                "subreddit": "bali",
                "selftext": "pretty",
            },
        ],
        "reason": "",
    }
    with patch(
        "mata_garuda.agents.reddit_listener_agent.fetch_subreddit_new",
        return_value=fake_ok,
    ), patch(
        "mata_garuda.agents.reddit_listener_agent.stream_publish_redis",
        return_value="1-0",
    ) as fake_publish:
        result = run_reddit_listen(subs=["bali"])
    assert result["case_resolved"] is True
    assert result["published"] == 1  # only KITAS post matches keywords
    stream, fields = fake_publish.call_args.args
    assert stream == "garuda:raw"
    assert fields["source_type"] == "social_reddit"
    assert fields["source_agent"] == "reddit_listener_agent"
    assert fields["source"] == "reddit.com/r/bali"


def test_reddit_agent_all_subs_fail():
    fake_fail = {"ok": False, "posts": [], "reason": "reddit HTTP 429"}
    with patch(
        "mata_garuda.agents.reddit_listener_agent.fetch_subreddit_new",
        return_value=fake_fail,
    ), patch(
        "mata_garuda.agents.reddit_listener_agent.stream_publish_redis"
    ) as fake_publish:
        result = run_reddit_listen(subs=["bali"])
    assert result["case_resolved"] is False
    assert "HTTP 429" in result["reason"]
    fake_publish.assert_not_called()


def test_reddit_agent_registered_with_genome():
    import mata_garuda.agents.reddit_listener_agent  # noqa: F401
    from mata_garuda.registry import get_agent

    agent = get_agent("reddit_listener_agent")
    assert agent is not None
    assert agent.layer == "harvester"
    genome = Path(mata_garuda.agents.reddit_listener_agent.__file__).parent / "reddit_listener_agent_GENOME.md"
    assert genome.exists()
