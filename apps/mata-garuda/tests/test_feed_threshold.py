"""Test the relevance threshold gate in the NLM feeder (council fix #3)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from mata_garuda.workers import nlm_feeder


def _item(msg_id, **data):
    return {"id": msg_id, "data": data}


class TestFeedRelevanceGate:
    """Feed only score >= FEED_MIN_SCORE; skip+ACK lower; fail-OPEN on no score."""

    def _run(self, items):
        kb = MagicMock()
        with patch.object(nlm_feeder, "stream_read_new", return_value=items), \
             patch.object(nlm_feeder, "stream_ack", return_value=True) as m_ack, \
             patch.object(nlm_feeder, "route_domain_to_notebook",
                          return_value=("ai_research", "nb-uuid")), \
             patch.object(nlm_feeder, "_already_fed", return_value=False), \
             patch.object(nlm_feeder, "_nlm_add_text", return_value=True) as m_add:
            stats = nlm_feeder._run_nlm_feeder_from(
                kb, "garuda:enriched", "g", "c", max_items=10, sleep_s=0)
        return stats, m_add, m_ack

    def test_low_score_skipped_and_acked(self):
        stats, m_add, m_ack = self._run([
            _item("1-0", title="noise", url="http://x/1", score="2", domain="ai_research"),
        ])
        assert stats["skipped"] == 1 and stats["fed"] == 0
        m_add.assert_not_called()           # never burned the NLM cap
        m_ack.assert_called()               # but DID ack (lag reflects attempted work)

    def test_high_score_fed(self):
        stats, m_add, _ = self._run([
            _item("2-0", title="signal", url="http://x/2", score="5", domain="ai_research"),
        ])
        assert stats["fed"] == 1 and stats["skipped"] == 0
        m_add.assert_called_once()

    def test_unscored_item_fails_open_and_is_fed(self):
        # no score field at all → must still feed (never drop un-scored intel)
        stats, m_add, _ = self._run([
            _item("3-0", title="unscored", url="http://x/3", domain="ai_research"),
        ])
        assert stats["fed"] == 1
        m_add.assert_called_once()

    def test_relevance_field_alias_respected(self):
        # some items use 'relevance' instead of 'score'
        stats, m_add, _ = self._run([
            _item("4-0", title="x", url="http://x/4", relevance="1", domain="ai_research"),
        ])
        assert stats["skipped"] == 1
        m_add.assert_not_called()

    def test_unparseable_score_fails_open(self):
        stats, m_add, _ = self._run([
            _item("5-0", title="x", url="http://x/5", score="N/A", domain="ai_research"),
        ])
        assert stats["fed"] == 1   # garbage score → fail-open
        m_add.assert_called_once()

    def test_boundary_exact_threshold_is_fed(self):
        stats, m_add, _ = self._run([
            _item("6-0", title="x", url="http://x/6", score="4", domain="ai_research"),
        ])
        assert stats["fed"] == 1   # >= threshold, inclusive
        m_add.assert_called_once()
