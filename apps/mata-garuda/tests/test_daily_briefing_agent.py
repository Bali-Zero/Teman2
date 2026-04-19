"""Tests for daily_briefing_agent — W3 Wave 2."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from mata_garuda.agents import daily_briefing_agent as dba
from mata_garuda.runtime.knowledge import KnowledgeBase


NOW = datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc)


def _mk_item(domain: str, title: str, *, hours_ago: float = 1.0,
             score: float = 3.0, url: str = "", content: str = "") -> dict:
    ts = (NOW - timedelta(hours=hours_ago)).isoformat()
    return {
        "id": f"{int(ts.replace('-', '').replace(':', '').replace('T', '')[:14])}-0",
        "data": {
            "title": title,
            "domain": domain,
            "normalized_at": ts,
            "relevance_score": str(score),
            "url": url,
            "content": content,
            "source": "src.test",
        },
    }


class TestWindowing:
    def test_drops_items_older_than_24h(self):
        items = [
            _mk_item("tax_fiscal", "recent", hours_ago=2),
            _mk_item("tax_fiscal", "old", hours_ago=30),
        ]
        grouped = dba._last_24h_by_domain(items, now=NOW)
        titles = [r["title"] for rows in grouped.values() for r in rows]
        assert "recent" in titles
        assert "old" not in titles

    def test_keeps_items_without_timestamp(self):
        """Defensive: items without parseable ts are kept, not silently dropped."""
        items = [{"id": "1-0", "data": {"title": "no-ts", "domain": "tax_fiscal"}}]
        grouped = dba._last_24h_by_domain(items, now=NOW)
        assert any(r["title"] == "no-ts" for rows in grouped.values() for r in rows)

    def test_top_n_per_domain(self):
        items = [
            _mk_item("tax_fiscal", f"t{i}", hours_ago=1, score=float(i))
            for i in range(8)
        ]
        grouped = dba._last_24h_by_domain(items, now=NOW, top_n=5)
        assert len(grouped["tax_fiscal"]) == 5
        # Highest scores first
        assert grouped["tax_fiscal"][0]["title"] == "t7"
        assert grouped["tax_fiscal"][4]["title"] == "t3"

    def test_groups_by_domain(self):
        items = [
            _mk_item("tax_fiscal", "t", hours_ago=1),
            _mk_item("immigration_visa", "i", hours_ago=2),
            _mk_item("immigration_visa", "i2", hours_ago=3),
        ]
        grouped = dba._last_24h_by_domain(items, now=NOW)
        assert set(grouped.keys()) == {"tax_fiscal", "immigration_visa"}
        assert len(grouped["immigration_visa"]) == 2
        assert len(grouped["tax_fiscal"]) == 1


class TestBriefingMarkdown:
    def test_empty_groups_produce_quiet_day(self):
        md = dba.build_briefing_md({}, now=NOW, use_claude_tldr=False)
        assert "Giornata silenziosa" in md
        assert NOW.strftime("%Y-%m-%d") in md

    def test_normal_briefing_contains_all_domains(self):
        grouped = {
            "tax_fiscal": [{"title": "T1", "url": "https://x/t", "content": "body",
                            "relevance_score": "4"}],
            "immigration_visa": [{"title": "I1", "url": "https://x/i", "content": "body2",
                                  "relevance_score": "5"}],
        }
        md = dba.build_briefing_md(grouped, now=NOW, use_claude_tldr=False)
        assert "Tax & Fiscal" in md
        assert "Immigration & Visa" in md
        assert "T1" in md and "I1" in md
        assert "https://x/t" in md and "https://x/i" in md
        assert "TL;DR" in md  # fallback tldr present

    def test_fallback_tldr_when_no_claude(self):
        grouped = {"tax_fiscal": [{"title": "t", "content": "primary insight line\nmore", "relevance_score": "3"}]}
        md = dba.build_briefing_md(grouped, now=NOW, use_claude_tldr=False)
        assert "primary insight line" in md


class TestRunner:
    def test_run_integrates_everything(self, tmp_path):
        kb = KnowledgeBase(db_path=tmp_path / "db.db")
        items = [
            _mk_item("tax_fiscal", "PMK update", hours_ago=1,
                     score=5, url="https://ex/pmk",
                     content="Pajak baru, ada detail rilevanti."),
            _mk_item("immigration_visa", "B211A new", hours_ago=3,
                     score=4, url="https://ex/b211",
                     content="Visa B211A update."),
            _mk_item("procurement", "old", hours_ago=48,  # out of window
                     score=5),
        ]
        with patch.object(dba, "_xrevrange", return_value=items), \
             patch.object(dba, "_send_telegram", return_value=True) as m_tg, \
             patch.object(dba, "stream_publish", return_value="ok"):
            stats = dba.run_daily_briefing(
                kb=kb, now=NOW, use_claude_tldr=False, dry_run=False,
            )

        assert stats["domains"] == 2  # procurement excluded (stale)
        assert stats["items"] == 2
        assert stats["tg_ok"] is True
        # TG was called with a briefing that mentions both items
        call_text = m_tg.call_args.args[0]
        assert "PMK update" in call_text
        assert "B211A new" in call_text
        kb.close()

    def test_dry_run_no_tg_send(self, tmp_path):
        kb = KnowledgeBase(db_path=tmp_path / "db.db")
        with patch.object(dba, "_xrevrange", return_value=[]):
            stats = dba.run_daily_briefing(
                kb=kb, now=NOW, use_claude_tldr=False, dry_run=True,
            )
        assert stats["dry_run"] is True
        assert stats["domains"] == 0
        kb.close()


class TestXrevrangeParser:
    def test_empty_input_returns_empty_list(self):
        with patch.object(dba, "redis_cmd", return_value=""):
            assert dba._xrevrange("garuda:enriched") == []

    def test_error_prefix_returns_empty_list(self):
        with patch.object(dba, "redis_cmd", return_value="[ERROR] redis-cli not found"):
            assert dba._xrevrange("garuda:enriched") == []
