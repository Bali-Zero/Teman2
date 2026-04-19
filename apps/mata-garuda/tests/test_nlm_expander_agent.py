"""Tests for nlm_expander_agent — W3 Wave 3."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from mata_garuda.agents import nlm_expander_agent as nea
from mata_garuda.config import NLM_DOMAIN_ROUTING, NLM_NOTEBOOKS
from mata_garuda.runtime.knowledge import KnowledgeBase


NOW = datetime(2026, 4, 19, 9, 0, tzinfo=timezone.utc)  # Sunday


def _item(domain: str, days_ago: float = 5.0) -> dict:
    ts = (NOW - timedelta(days=days_ago)).isoformat()
    return {
        "id": f"{int(ts.replace('-', '').replace(':', '').replace('T', '')[:14])}-0",
        "data": {
            "domain": domain,
            "title": "t",
            "normalized_at": ts,
        },
    }


class TestCountDomains:
    def test_basic_counts(self):
        items = [_item("tax_fiscal") for _ in range(3)] + \
                [_item("ai_research") for _ in range(5)]
        counts = nea.count_domains_last_30d(items, now=NOW)
        assert counts == {"tax_fiscal": 3, "ai_research": 5}

    def test_drops_older_than_30d(self):
        items = [_item("tax_fiscal", days_ago=60)]
        counts = nea.count_domains_last_30d(items, now=NOW)
        assert counts == {}

    def test_skips_items_with_empty_domain(self):
        items = [{"id": "1-0", "data": {"title": "t"}}]  # no domain
        assert nea.count_domains_last_30d(items, now=NOW) == {}


class TestFindProposalCandidates:
    def test_threshold_respected(self):
        counts = {"domain_new": 80, "domain_small": 10}
        out = nea.find_proposal_candidates(counts, threshold=50)
        # domain_new not in NLM_DOMAIN_ROUTING → candidate
        # domain_small under threshold
        assert ("domain_new", 80) in out
        assert ("domain_small", 10) not in out

    def test_already_mapped_domains_are_not_proposed(self):
        # immigration_visa IS in NLM_DOMAIN_ROUTING (from Wave 1)
        assert "immigration_visa" in NLM_DOMAIN_ROUTING
        counts = {"immigration_visa": 500}
        out = nea.find_proposal_candidates(counts, threshold=50)
        assert out == []

    def test_sorted_by_volume_desc(self):
        counts = {"a_new": 60, "b_new": 200, "c_new": 100}
        out = nea.find_proposal_candidates(counts, threshold=50)
        assert [d for d, _ in out] == ["b_new", "c_new", "a_new"]


class TestStaleDetection:
    def test_no_fed_entries_means_all_configured_are_stale(self, tmp_path):
        kb = KnowledgeBase(db_path=tmp_path / "db.db")
        stale = nea.find_stale_notebooks(kb, now=NOW)
        # Wave 1 wired regulation/tax/immigration/press + ai_research + self_evolving
        configured = [k for k, v in NLM_NOTEBOOKS.items() if v]
        assert set(stale) == set(configured)
        kb.close()

    def test_recent_feed_clears_stale(self, tmp_path):
        kb = KnowledgeBase(db_path=tmp_path / "db.db")
        # Insert a fresh nlm_fed entry
        kb.store("nlm_feeder", "nlm_fed", "nlm_fed https://x", "https://x", 1.0)
        stale = nea.find_stale_notebooks(kb, now=NOW)
        assert stale == []
        kb.close()


class TestProposalMessage:
    def test_mentions_candidates_and_stale(self):
        msg = nea.build_proposal_message(
            candidates=[("new_domain", 120)],
            stale=["regulation"],
            now=NOW,
        )
        assert "new_domain" in msg
        assert "120" in msg
        assert "regulation" in msg
        assert "L2 autonomy" in msg

    def test_nothing_to_report(self):
        msg = nea.build_proposal_message([], [], now=NOW)
        assert "coverage stabile" in msg


class TestRunner:
    def test_no_proposals_no_stale_no_send(self, tmp_path):
        kb = KnowledgeBase(db_path=tmp_path / "db.db")
        # Fresh feed → no stale
        kb.store("nlm_feeder", "nlm_fed", "nlm_fed https://x", "https://x", 1.0)
        with patch.object(nea, "_xrevrange", return_value=[]), \
             patch.object(nea, "_send_telegram", return_value=True) as m_tg:
            stats = nea.run_nlm_expander(kb=kb, now=NOW)
        assert stats["sent"] is False
        m_tg.assert_not_called()
        kb.close()

    def test_sends_when_candidates_exist(self, tmp_path):
        kb = KnowledgeBase(db_path=tmp_path / "db.db")
        kb.store("nlm_feeder", "nlm_fed", "nlm_fed https://x", "https://x", 1.0)
        items = [_item("brand_new_topic") for _ in range(60)]
        with patch.object(nea, "_xrevrange", return_value=items), \
             patch.object(nea, "_send_telegram", return_value=True) as m_tg:
            stats = nea.run_nlm_expander(kb=kb, now=NOW, proposal_threshold=50)
        assert stats["sent"] is True
        assert any(c["domain"] == "brand_new_topic" for c in stats["candidates"])
        m_tg.assert_called_once()
        kb.close()

    def test_dry_run_does_not_send_for_real(self, tmp_path):
        kb = KnowledgeBase(db_path=tmp_path / "db.db")
        kb.store("nlm_feeder", "nlm_fed", "nlm_fed https://x", "https://x", 1.0)
        items = [_item("xyz") for _ in range(60)]
        with patch.object(nea, "_xrevrange", return_value=items), \
             patch("subprocess.run") as m_run:
            stats = nea.run_nlm_expander(
                kb=kb, now=NOW, dry_run=True, proposal_threshold=50,
            )
        assert stats["dry_run"] is True
        # Real curl subprocess NEVER invoked in dry-run
        m_run.assert_not_called()
        kb.close()

    def test_never_creates_notebooks(self, tmp_path):
        """L2 hard boundary: no nlm CLI subprocess calls happen."""
        kb = KnowledgeBase(db_path=tmp_path / "db.db")
        kb.store("nlm_feeder", "nlm_fed", "nlm_fed https://x", "https://x", 1.0)
        items = [_item("bignew") for _ in range(120)]
        with patch.object(nea, "_xrevrange", return_value=items), \
             patch.object(nea, "_send_telegram", return_value=True), \
             patch("subprocess.run") as m_run:
            nea.run_nlm_expander(kb=kb, now=NOW, proposal_threshold=50)
        # No subprocess run at all from within the agent (TG mocked)
        for call in m_run.call_args_list:
            args = call.args[0] if call.args else []
            assert "nlm" not in args[:1], \
                f"L2 violation: NLM CLI invoked with {args}"
        kb.close()
