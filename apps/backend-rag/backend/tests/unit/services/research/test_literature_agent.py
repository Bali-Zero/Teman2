"""Tests for LiteratureAgent — URL counting + synthesize + subprocess shape."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
from backend.services.research.literature_agent import (
    LiteratureAgent,
    ResearchTopic,
    TOPICS,
)


def test_topics_covers_4_sota_dimensions():
    """Q8 A4: Hook + Tone + Cadence + Format."""
    slugs = {t.slug for t in TOPICS}
    assert "01_hook_taxonomy" in slugs
    assert "02_tone_voice_b2b_legal" in slugs
    assert "03_cadence_algorithm_2026" in slugs
    assert "04_format_objective_matrix" in slugs


def test_count_sources_counts_distinct_urls():
    md = """
Some prose.

- https://example.com/paper1
- https://example.com/paper1  (duplicate, still 1 distinct URL)
- https://arxiv.org/abs/2501.12345 (published 2025)
- https://buffer.com/blog/hook-patterns (published 2026)
"""
    total, recent = LiteratureAgent.count_sources(md)
    assert total == 3  # 3 distinct URLs (duplicates merged)
    assert recent == 2  # "2025" + "2026" each mentioned once


def test_count_sources_strips_trailing_punctuation():
    md = "See https://a.com/x, and https://b.com/y."
    total, _ = LiteratureAgent.count_sources(md)
    assert total == 2


def test_count_sources_empty_markdown():
    total, recent = LiteratureAgent.count_sources("# empty\n\nnothing here.")
    assert total == 0
    assert recent == 0


def test_synthesize_concatenates_topic_bodies():
    agent = LiteratureAgent(output_dir=Path("/tmp/whatever"))
    bodies = {
        "01_hook_taxonomy": "Body A",
        "02_tone_voice_b2b_legal": "Body B",
    }
    md = agent.synthesize(bodies)
    assert "# SOTA Literature Synthesis" in md
    assert "## 01_hook_taxonomy" in md
    assert "Body A" in md
    assert "## 02_tone_voice_b2b_legal" in md
    assert "Body B" in md


def test_research_topic_returns_placeholder_on_rc_nonzero():
    agent = LiteratureAgent(output_dir=Path("/tmp/whatever"))
    topic = ResearchTopic(slug="99_test", prompt="anything")
    fake_proc = type("P", (), {"returncode": 3, "stdout": "", "stderr": "fail"})()
    with patch("subprocess.run", return_value=fake_proc):
        body = agent.research_topic(topic, timeout_sec=10)
    assert "99_test" in body
    assert "Research failed" in body
    assert "exited 3" in body


def test_research_topic_returns_placeholder_on_missing_binary():
    agent = LiteratureAgent(output_dir=Path("/tmp/whatever"))
    topic = ResearchTopic(slug="99_test", prompt="anything")
    with patch("subprocess.run", side_effect=FileNotFoundError("no gemini")):
        body = agent.research_topic(topic, timeout_sec=10)
    assert "99_test" in body
    assert "gemini CLI not found" in body


def test_research_topic_uses_gemini_model_flag():
    agent = LiteratureAgent(output_dir=Path("/tmp/whatever"))
    topic = ResearchTopic(slug="test", prompt="X")
    fake_proc = type("P", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()
    with patch("subprocess.run", return_value=fake_proc) as run_mock:
        agent.research_topic(topic, timeout_sec=10)
    cmd = run_mock.call_args.args[0]
    assert cmd[0] == "gemini"
    assert cmd[1] == "-m"
    assert "3.1" in cmd[2]
    assert cmd[3] == "-p"
    prompt = cmd[4]
    # Prompt must include the mandatory OUTPUT contract (Sources with URLs)
    assert "## Sources" in prompt
    assert "https://" in prompt
