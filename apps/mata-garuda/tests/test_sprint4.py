"""
Mata Garuda — Sprint 4 tests for Regulation Watcher POC.

Tests:
- Scraper tools: check source, scrape regulations, extract entries
- Stream tools: publish, read, info, length (requires Redis)
- Regulation Watcher agent: registration, tools, GENOME
- End-to-end mock: scrape → publish → verify stream
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

import mata_garuda.agents  # noqa: F401
from mata_garuda.registry import registry
from mata_garuda.tools.scraper_tools import (
    _curl_fetch,
    _extract_regulations,
    check_regulation_source,
    scrape_regulations,
)
from mata_garuda.tools.stream_tools import (
    _redis_cmd,
    stream_info,
    stream_length,
    stream_publish,
    stream_read,
)
from mata_garuda.types import Agent


# ─── Helpers ───────────────────────────────────────────────────────────

def _redis_available() -> bool:
    """Check if Redis is running."""
    try:
        result = subprocess.run(
            ["redis-cli", "ping"], capture_output=True, text=True, timeout=3
        )
        return result.stdout.strip() == "PONG"
    except Exception:
        return False


REDIS_OK = _redis_available()
TEST_STREAM = "garuda:test_sprint4"


# ─── Scraper Tools Tests ──────────────────────────────────────────────


class TestCurlFetch:
    def test_fetch_valid_url(self):
        result = _curl_fetch("https://peraturan.go.id/", timeout=10)
        assert not result.startswith("[ERROR]")
        assert "peraturan" in result.lower()

    def test_fetch_invalid_url(self):
        result = _curl_fetch("https://thisdomaindoesnotexist12345.com/", timeout=3)
        assert "[ERROR]" in result


class TestExtractRegulations:
    def test_extract_from_sample_html(self):
        """Test regex extraction with sample HTML matching peraturan.go.id 2026 structure."""
        sample = """
        <div>
            <p>Peraturan Presiden</p>
            <p>Tentang Perubahan Atas PP Nomor 10 Tahun 2024</p>
            <br>
            <p><a href="/harmon/abc123" title="lihat detail" data-pjax="0">Lihat Detail</a></p>
        </div>
        <div>
            <p>Peraturan Menteri</p>
            <p>Tentang Keimigrasian Tahun 2025</p>
            <br>
            <p><a href="/harmon/def456" title="lihat detail" data-pjax="0">Lihat Detail</a></p>
        </div>
        """
        entries = _extract_regulations(sample)
        assert len(entries) == 2
        assert entries[0]["url"] == "https://peraturan.go.id/harmon/abc123"
        assert "Presiden" in entries[0]["title"]
        assert entries[1]["source"] == "peraturan.go.id"

    def test_extract_from_empty_html(self):
        entries = _extract_regulations("<html><body>No tables</body></html>")
        assert entries == []


class TestCheckSource:
    def test_check_peraturan(self):
        result = check_regulation_source("https://peraturan.go.id/")
        assert "[OK]" in result or "[WARNING]" in result

    def test_check_unreachable(self):
        result = check_regulation_source("https://thisdomaindoesnotexist12345.com/")
        assert "[ERROR]" in result or "[WARNING]" in result


class TestScrapeRegulations:
    def test_scrape_returns_string(self):
        result = scrape_regulations(limit=3)
        assert isinstance(result, str)
        # Either finds regulations or warns about structure
        assert "Found" in result or "[WARNING]" in result or "[ERROR]" in result


# ─── Stream Tools Tests ───────────────────────────────────────────────


@pytest.mark.skipif(not REDIS_OK, reason="Redis not available")
class TestStreamTools:
    @pytest.fixture(autouse=True)
    def cleanup_test_stream(self):
        """Clean up test stream after each test."""
        yield
        _redis_cmd("DEL", TEST_STREAM)

    def test_publish_and_read(self):
        result = stream_publish(
            title="Test Regulation",
            url="https://peraturan.go.id/harmon/test123",
            source="peraturan.go.id",
            content="Test content",
            stream=TEST_STREAM,
        )
        assert "[SUCCESS]" in result

        read_result = stream_read(count=1, stream=TEST_STREAM)
        assert "Test Regulation" in read_result or "1" in read_result

    def test_stream_length(self):
        stream_publish(
            title="Test 1", url="http://test/1",
            source="test", stream=TEST_STREAM,
        )
        stream_publish(
            title="Test 2", url="http://test/2",
            source="test", stream=TEST_STREAM,
        )

        result = stream_length(stream=TEST_STREAM)
        assert "2" in result

    def test_stream_info_nonexistent(self):
        result = stream_info(stream="garuda:nonexistent_test_stream")
        assert "does not exist" in result or "[ERROR]" in result

    def test_redis_cmd_ping(self):
        result = _redis_cmd("PING")
        assert result == "PONG"


# ─── Regulation Watcher Agent Tests ───────────────────────────────────


class TestRegulationWatcher:
    def test_agent_registered(self):
        assert "get_regulation_watcher" in registry.agents
        assert "Regulation Watcher" in registry.agents_info

    def test_agent_instantiates(self):
        from mata_garuda.agents.regulation_watcher import get_regulation_watcher

        agent = get_regulation_watcher(model="claude")
        assert isinstance(agent, Agent)
        assert agent.name == "Regulation Watcher"
        assert agent.layer == "harvester"
        assert agent.genome_path is not None

    def test_agent_has_correct_tools(self):
        from mata_garuda.agents.regulation_watcher import get_regulation_watcher

        agent = get_regulation_watcher()
        tool_names = [f.__name__ for f in agent.functions]
        assert "scrape_regulations" in tool_names
        assert "stream_publish" in tool_names
        assert "check_regulation_source" in tool_names
        assert "case_resolved" in tool_names
        assert "case_not_resolved" in tool_names

    def test_agent_instructions(self):
        from mata_garuda.agents.regulation_watcher import get_regulation_watcher

        agent = get_regulation_watcher()
        assert callable(agent.instructions)
        instr = agent.instructions({})
        assert "peraturan.go.id" in instr
        assert "garuda:raw" in instr
        assert "OSINT blindato" in instr

    def test_genome_exists(self):
        from mata_garuda.agents.regulation_watcher import GENOME_FILE

        assert os.path.exists(GENOME_FILE)

    def test_genome_content(self):
        from mata_garuda.agents.regulation_watcher import GENOME_FILE

        content = Path(GENOME_FILE).read_text()
        assert "peraturan.go.id" in content
        assert "harvester" in content
        assert "garuda:raw" in content
        assert "Mutations: 0" in content


# ─── End-to-End Mock Test ─────────────────────────────────────────────


@pytest.mark.skipif(not REDIS_OK, reason="Redis not available")
class TestEndToEnd:
    """Simulates the regulation watcher flow without calling the LLM."""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        yield
        _redis_cmd("DEL", TEST_STREAM)

    def test_scrape_and_publish_flow(self):
        """Simulate: check source → scrape → publish → verify."""
        # 1. Check source
        source_ok = check_regulation_source()
        assert "[OK]" in source_ok or "[WARNING]" in source_ok

        # 2. Scrape (may or may not find entries depending on page structure)
        scrape_result = scrape_regulations(limit=3)

        # 3. Publish mock entries to test stream
        pub1 = stream_publish(
            title="PP Nomor 10 Tahun 2025 tentang Investasi",
            url="https://peraturan.go.id/harmon/abc123",
            source="peraturan.go.id",
            content="Peraturan tentang perubahan investasi...",
            stream=TEST_STREAM,
        )
        assert "[SUCCESS]" in pub1

        pub2 = stream_publish(
            title="Permen Nomor 5 Tahun 2025 tentang Keimigrasian",
            url="https://peraturan.go.id/harmon/def456",
            source="peraturan.go.id",
            content="Peraturan tentang izin tinggal...",
            stream=TEST_STREAM,
        )
        assert "[SUCCESS]" in pub2

        # 4. Verify
        length = stream_length(stream=TEST_STREAM)
        assert "2" in length

        read = stream_read(count=5, stream=TEST_STREAM)
        assert "Investasi" in read or "Keimigrasian" in read


# ─── List All Agents Test ─────────────────────────────────────────────


class TestAgentRegistry:
    def test_three_agents_registered(self):
        """After Sprint 4, we should have 3 agents."""
        agent_names = list(registry.agents_info.keys())
        assert "Dummy Agent" in agent_names
        assert "Meta Agent" in agent_names
        assert "Regulation Watcher" in agent_names
