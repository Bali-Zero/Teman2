# apps/cell/tests/test_journal.py
"""Tests for Journal daily narrative."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date

from cell.identity.journal import Journal, JournalEntry


class TestJournalEntry:
    def test_dataclass_fields(self):
        entry = JournalEntry(
            journal_date=date(2026, 4, 3),
            narrative="Today CELL was alert. Backend was green all day.",
            emotion_summary="calm",
            actions_taken=0,
            lessons_count=2,
        )
        assert entry.journal_date == date(2026, 4, 3)
        assert "green" in entry.narrative


class TestJournalWrite:
    @pytest.fixture
    def pool(self):
        acquire_ctx = AsyncMock()
        acquire_ctx.__aenter__ = AsyncMock(return_value=acquire_ctx)
        acquire_ctx.__aexit__ = AsyncMock(return_value=None)
        acquire_ctx.fetch = AsyncMock(return_value=[])
        acquire_ctx.execute = AsyncMock()
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=acquire_ctx)
        return pool, acquire_ctx

    @pytest.mark.asyncio
    async def test_write_journal_stores_entry(self, pool):
        db_pool, conn = pool
        journal = Journal(pool=db_pool, ollama_url="http://localhost:11434")

        with patch.object(journal, "_summarize_with_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "CELL observed green status all day. Backend stable at 120ms."
            entry = await journal.write(
                episodes=[],
                emotion_summary="calm",
                actions_taken=0,
                lessons_count=0,
            )

        assert entry is not None
        assert "CELL" in entry.narrative or "stable" in entry.narrative

    @pytest.mark.asyncio
    async def test_write_journal_without_ollama_uses_fallback(self, pool):
        db_pool, conn = pool
        journal = Journal(pool=db_pool, ollama_url="http://localhost:99999")

        # Fallback should produce a narrative even without Ollama
        entry = await journal.write(
            episodes=[],
            emotion_summary="calm",
            actions_taken=0,
            lessons_count=0,
        )
        assert entry is not None
        assert isinstance(entry.narrative, str)
        assert len(entry.narrative) > 0


class TestJournalRecentDays:
    @pytest.fixture
    def pool_with_rows(self):
        rows = [
            {"journal_date": date(2026, 4, 3), "narrative": "Day was green.", "emotion_summary": "calm"},
            {"journal_date": date(2026, 4, 2), "narrative": "Backend was slow.", "emotion_summary": "alert"},
        ]
        acquire_ctx = AsyncMock()
        acquire_ctx.__aenter__ = AsyncMock(return_value=acquire_ctx)
        acquire_ctx.__aexit__ = AsyncMock(return_value=None)
        acquire_ctx.fetch = AsyncMock(return_value=rows)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=acquire_ctx)
        return pool

    @pytest.mark.asyncio
    async def test_recent_days_returns_formatted_text(self, pool_with_rows):
        journal = Journal(pool=pool_with_rows, ollama_url="http://localhost:11434")
        text = await journal.recent_days(limit=3)
        assert "2026-04-03" in text
        assert "Day was green" in text
        assert "Backend was slow" in text

    @pytest.mark.asyncio
    async def test_recent_days_empty_returns_empty(self):
        acquire_ctx = AsyncMock()
        acquire_ctx.__aenter__ = AsyncMock(return_value=acquire_ctx)
        acquire_ctx.__aexit__ = AsyncMock(return_value=None)
        acquire_ctx.fetch = AsyncMock(return_value=[])
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=acquire_ctx)

        journal = Journal(pool=pool, ollama_url="http://localhost:11434")
        text = await journal.recent_days()
        assert text == ""
