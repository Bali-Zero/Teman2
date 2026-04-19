"""Tests for weekly_digest_agent — W3 Wave 3."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from mata_garuda.agents import weekly_digest_agent as wda
from mata_garuda.runtime.knowledge import KnowledgeBase


NOW = datetime(2026, 4, 19, 8, 0, tzinfo=timezone.utc)  # Sunday


def _item(domain: str, title: str, *, days_ago: float = 1.0,
          score: float = 3.0, url: str = "", content: str = "") -> dict:
    ts = (NOW - timedelta(days=days_ago)).isoformat()
    return {
        "id": f"{int(ts.replace('-', '').replace(':', '').replace('T', '')[:14])}-0",
        "data": {
            "title": title,
            "domain": domain,
            "normalized_at": ts,
            "relevance_score": str(score),
            "url": url,
            "content": content,
            "source": "test.src",
        },
    }


class TestFilterLast7Days:
    def test_drops_older_than_7d(self):
        items = [
            _item("tax_fiscal", "new", days_ago=2),
            _item("tax_fiscal", "old", days_ago=10),
        ]
        rows = wda.filter_last_7_days(items, now=NOW)
        titles = [r["title"] for r in rows]
        assert "new" in titles
        assert "old" not in titles

    def test_top_n_cap_and_sort(self):
        items = [
            _item("x", f"i{i}", days_ago=1, score=float(i)) for i in range(120)
        ]
        rows = wda.filter_last_7_days(items, now=NOW, top_n=80)
        assert len(rows) == 80
        # Highest score first
        assert rows[0]["title"] == "i119"


class TestAnalysisPrompt:
    def test_prompt_contains_items_and_instructions(self):
        rows = [
            {"title": "PMK 25/2026", "domain": "tax_fiscal",
             "source": "ddtc", "url": "https://x/1", "relevance_score": "4.5",
             "content": "tax detail"},
        ]
        prompt = wda.build_analysis_prompt(rows, now=NOW)
        assert "PMK 25/2026" in prompt
        assert "Top 3" in prompt
        assert "MAX 500 parole" in prompt
        assert "mai inventare" in prompt


class TestFallback:
    def test_fallback_empty(self):
        out = wda.fallback_digest([], now=NOW)
        assert "silenziosa" in out

    def test_fallback_renders_top_10(self):
        rows = [
            {"title": f"t{i}", "domain": "tax_fiscal",
             "url": f"https://x/{i}", "relevance_score": str(i)}
            for i in range(15)
        ]
        out = wda.fallback_digest(rows, now=NOW)
        # 10 items listed (sorted upstream)
        assert out.count("- [tax_fiscal") == 10


class TestRunner:
    def test_runner_uses_claude_then_falls_back(self, tmp_path):
        kb = KnowledgeBase(db_path=tmp_path / "db.db")
        items = [_item("tax_fiscal", "PMK Y", days_ago=2, score=5)]
        with patch.object(wda, "_xrevrange", return_value=items), \
             patch.object(wda, "call_claude", return_value=""), \
             patch.object(wda, "_send_telegram", return_value=True) as m_tg, \
             patch.object(wda, "stream_publish"):
            stats = wda.run_weekly_digest(kb=kb, now=NOW, use_claude=True)

        assert stats["tg_ok"] is True
        assert stats["items"] == 1
        # Fallback digest body sent (contains "Weekly Digest" header)
        body = m_tg.call_args.args[0]
        assert "Weekly Digest" in body or "WEEKLY DIGEST" in body
        assert "PMK Y" in body
        kb.close()

    def test_runner_uses_claude_output_when_available(self, tmp_path):
        kb = KnowledgeBase(db_path=tmp_path / "db.db")
        items = [_item("tax_fiscal", "T", days_ago=1, score=4)]
        with patch.object(wda, "_xrevrange", return_value=items), \
             patch.object(wda, "call_claude", return_value="## Claude Analysis\nTrends: X"), \
             patch.object(wda, "_send_telegram", return_value=True) as m_tg, \
             patch.object(wda, "stream_publish"):
            wda.run_weekly_digest(kb=kb, now=NOW, use_claude=True)
        body = m_tg.call_args.args[0]
        assert "Claude Analysis" in body
        kb.close()

    def test_dry_run(self, tmp_path):
        kb = KnowledgeBase(db_path=tmp_path / "db.db")
        with patch.object(wda, "_xrevrange", return_value=[]):
            stats = wda.run_weekly_digest(kb=kb, now=NOW, dry_run=True)
        assert stats["dry_run"] is True
        kb.close()
