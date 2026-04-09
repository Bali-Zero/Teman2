"""Tests for AI-Intel-Sentinel harvester agents and tools."""
import pytest
from unittest.mock import patch, MagicMock


class TestArXivTools:
    def test_parse_arxiv_atom(self):
        from mata_garuda.tools.arxiv_tools import _parse_arxiv_atom

        sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
        <entry>
            <id>http://arxiv.org/abs/2504.12345</id>
            <title>A New Method for Retrieval Augmented Generation</title>
            <summary>We propose a novel approach to RAG that improves retrieval quality.</summary>
            <author><name>John Smith</name></author>
            <author><name>Jane Doe</name></author>
            <published>2026-04-09T00:00:00Z</published>
            <category term="cs.CL"/>
            <category term="cs.AI"/>
        </entry>
        <entry>
            <id>http://arxiv.org/abs/2504.67890</id>
            <title>Efficient Language Models via Mixture of Experts</title>
            <summary>MoE architectures enable scaling without proportional compute increase.</summary>
            <author><name>Alice Bob</name></author>
            <published>2026-04-09T00:00:00Z</published>
            <category term="cs.LG"/>
        </entry>
        </feed>"""

        papers = _parse_arxiv_atom(sample_xml)
        assert len(papers) == 2
        assert "Retrieval Augmented Generation" in papers[0]["title"]
        assert papers[0]["url"] == "http://arxiv.org/abs/2504.12345"
        assert "John Smith" in papers[0]["authors"]
        assert papers[0]["source"] == "arxiv"
        assert "cs.CL" in papers[0]["categories"]

    def test_parse_empty_xml(self):
        from mata_garuda.tools.arxiv_tools import _parse_arxiv_atom

        papers = _parse_arxiv_atom("<feed></feed>")
        assert papers == []


class TestFeedTools:
    def test_parse_rss_feed(self):
        from mata_garuda.tools.feed_tools import _parse_feed

        sample_rss = """<?xml version="1.0"?>
        <rss version="2.0">
        <channel>
        <item>
            <title>AI Weekly: New Breakthroughs</title>
            <link>https://example.com/ai-weekly</link>
            <pubDate>Thu, 09 Apr 2026 00:00:00 GMT</pubDate>
            <description>This week in AI: major breakthroughs in reasoning.</description>
        </item>
        </channel>
        </rss>"""

        items = _parse_feed(sample_rss)
        assert len(items) == 1
        assert "AI Weekly" in items[0]["title"]
        assert items[0]["url"] == "https://example.com/ai-weekly"

    def test_parse_atom_feed(self):
        from mata_garuda.tools.feed_tools import _parse_feed

        sample_atom = """<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
        <entry>
            <title>Papers With Code: Top Papers</title>
            <link href="https://paperswithcode.com/top" />
            <published>2026-04-09T10:00:00Z</published>
            <summary>Top trending papers this week.</summary>
        </entry>
        </feed>"""

        items = _parse_feed(sample_atom)
        assert len(items) == 1
        assert "Papers With Code" in items[0]["title"]

    def test_parse_empty_feed(self):
        from mata_garuda.tools.feed_tools import _parse_feed

        items = _parse_feed("<rss><channel></channel></rss>")
        assert items == []


class TestGitHubTools:
    @patch("mata_garuda.tools.github_tools.subprocess.run")
    def test_fetch_trending_success(self, mock_run):
        from mata_garuda.tools.github_tools import fetch_github_trending
        import json

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "items": [
                    {
                        "full_name": "openai/gpt-5-tools",
                        "stargazers_count": 5000,
                        "description": "GPT-5 tool use framework",
                        "html_url": "https://github.com/openai/gpt-5-tools",
                        "language": "Python",
                        "forks_count": 200,
                    }
                ]
            }),
        )
        result = fetch_github_trending(max_results=5)
        assert "gpt-5-tools" in result
        assert "★5000" in result


class TestHarvesterAgents:
    def test_arxiv_agent_registered(self):
        import mata_garuda.agents  # noqa: F401
        from mata_garuda.registry import registry

        assert "ArXiv Harvester" in registry.agents_info

    def test_youtube_agent_registered(self):
        import mata_garuda.agents  # noqa: F401
        from mata_garuda.registry import registry

        assert "YouTube Intel Harvester" in registry.agents_info

    def test_github_agent_registered(self):
        import mata_garuda.agents  # noqa: F401
        from mata_garuda.registry import registry

        assert "GitHub Trending Harvester" in registry.agents_info

    def test_twitter_agent_registered(self):
        import mata_garuda.agents  # noqa: F401
        from mata_garuda.registry import registry

        assert "AI Twitter Harvester" in registry.agents_info

    def test_newsletter_agent_registered(self):
        import mata_garuda.agents  # noqa: F401
        from mata_garuda.registry import registry

        assert "AI Newsletter Harvester" in registry.agents_info

    def test_all_harvesters_have_genome(self):
        from pathlib import Path

        agents_dir = Path(__file__).parent.parent / "mata_garuda" / "agents"
        harvesters = [
            "arxiv_harvester",
            "youtube_intel_harvester",
            "github_trending_harvester",
            "ai_twitter_harvester",
            "ai_newsletter_harvester",
        ]
        for name in harvesters:
            genome = agents_dir / f"{name}_GENOME.md"
            assert genome.exists(), f"Missing GENOME for {name}"

    def test_arxiv_agent_has_correct_layer(self):
        from mata_garuda.agents.arxiv_harvester import get_arxiv_harvester

        agent = get_arxiv_harvester()
        assert agent.layer == "harvester"
        assert agent.genome_path.endswith("arxiv_harvester_GENOME.md")
        assert len(agent.functions) >= 5  # fetch + publish + kb + case tools

    def test_total_agents_count(self):
        import mata_garuda.agents  # noqa: F401
        from mata_garuda.registry import registry

        # 3 original + 5 new harvesters = 8
        assert len(registry.agents_info) >= 8
