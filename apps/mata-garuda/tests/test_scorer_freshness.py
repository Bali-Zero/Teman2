"""Tests for the scorer alert-freshness gate (2026-07-14, backlog-drain hardening).

Ground truth (verified live 2026-07-14): the scorer worker drained only
~50 items/day while inflow kept pace, so a permanent ~1000-item backlog
built up and high-relevance alerts fired ~8 days late. run_sentinel_py.py's
max_items was raised 50->300 to actually drain the backlog — but
regulation_alert_agent.run_regulation_alert sends ONE Telegram message per
alert, so draining the backlog without a gate would flood Zero with alerts
about week-old news.

The freshness gate: every item is still scored + stored to the KB exactly
as before (KB stays complete); only the `garuda:alerts` publish is skipped
when the item's stream id (the ms-prefixed PUBLISH timestamp) is older than
`GARUDA_ALERT_MAX_AGE_H` (env, default 48h).

Guilt + innocence corpus:
  (a) GUILT    — an item older than the max age: scored+stored, NOT
                 published to alerts, counted in stale_skipped.
  (b) INNOCENCE — a fresh item with a SCORE_SIGNAL-worthy score: published
                 exactly as before (unchanged behavior).
  (c) ENV       — GARUDA_ALERT_MAX_AGE_H override is honored both ways
                 (a 2h-old item is stale under a 1h cap, fresh under the
                 48h default).
"""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from mata_garuda.workers import scorer
from mata_garuda.runtime.knowledge import KnowledgeBase

H = 3_600_000  # one hour in ms, matching Redis Stream id units


def _item(msg_id: str, title: str, **overrides) -> dict:
    data = {
        "title": title,
        "content": "",
        "source": "imigrasi.go.id",
        "url": f"https://ex.com/{msg_id}",
    }
    data.update(overrides)
    return {"id": msg_id, "data": data}


# "KITAS extension" hits the immigration_visa keyword fast-path
# (score=4, weight=5 -> weighted=min(5, 4+(5-3)*0.5)=5.0 >= SCORE_SIGNAL=4),
# so these tests exercise the real scoring path with zero Ollama subprocess
# calls (see test_scorer_fastpath.py for the fast-path contract itself).
SIGNAL_TITLE = "KITAS extension procedure update"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Ensure GARUDA_ALERT_MAX_AGE_H is unset by default (uses the 48h default)."""
    monkeypatch.delenv("GARUDA_ALERT_MAX_AGE_H", raising=False)


class TestFreshnessGate:
    def test_stale_item_scored_stored_but_not_alerted(self, tmp_path):
        """(a) GUILT: an item older than the default 48h max age must be
        scored+stored (KB stays complete) but NOT published to garuda:alerts,
        and counted in stats['stale_skipped']."""
        kb = KnowledgeBase(db_path=tmp_path / "db.db")
        now_ms = int(time.time() * 1000)
        old_id = f"{now_ms - 50 * H}-0"  # 50h old, > 48h default
        items = [_item(old_id, SIGNAL_TITLE)]

        with patch.object(scorer, "stream_read_new", return_value=items), \
             patch.object(scorer, "stream_publish") as m_pub, \
             patch.object(scorer, "stream_ack") as m_ack:
            stats = scorer.run_scorer(kb, max_items=10)

        assert stats["processed"] == 1
        assert stats["stored"] == 1
        assert stats["alerts"] == 0
        assert stats["stale_skipped"] == 1
        m_pub.assert_not_called()
        m_ack.assert_called_once()

        # KB actually has the scored item (freshness gate does not touch storage).
        rows = kb.get_by_type("scored_item", limit=5)
        assert any("KITAS extension" in r["content"] for r in rows)
        kb.close()

    def test_fresh_item_alerts_exactly_as_before(self, tmp_path):
        """(b) INNOCENCE: a fresh item with a SCORE_SIGNAL-worthy score must
        still publish to garuda:alerts exactly as before the gate existed."""
        kb = KnowledgeBase(db_path=tmp_path / "db.db")
        now_ms = int(time.time() * 1000)
        fresh_id = f"{now_ms}-0"
        items = [_item(fresh_id, SIGNAL_TITLE)]

        with patch.object(scorer, "stream_read_new", return_value=items), \
             patch.object(scorer, "stream_publish") as m_pub, \
             patch.object(scorer, "stream_ack") as m_ack:
            stats = scorer.run_scorer(kb, max_items=10)

        assert stats["processed"] == 1
        assert stats["stored"] == 1
        assert stats["alerts"] == 1
        assert stats["stale_skipped"] == 0
        m_pub.assert_called_once()
        assert m_pub.call_args.args[0] == scorer.STREAM_ALERTS
        alert_payload = m_pub.call_args.args[1]
        assert alert_payload["title"] == SIGNAL_TITLE
        m_ack.assert_called_once()
        kb.close()

    def test_env_override_tightens_the_window(self, tmp_path, monkeypatch):
        """(c) ENV: GARUDA_ALERT_MAX_AGE_H=1 makes a 2h-old item stale, even
        though it would pass under the 48h default."""
        monkeypatch.setenv("GARUDA_ALERT_MAX_AGE_H", "1")
        kb = KnowledgeBase(db_path=tmp_path / "db.db")
        now_ms = int(time.time() * 1000)
        two_hour_old_id = f"{now_ms - 2 * H}-0"
        items = [_item(two_hour_old_id, SIGNAL_TITLE)]

        with patch.object(scorer, "stream_read_new", return_value=items), \
             patch.object(scorer, "stream_publish") as m_pub, \
             patch.object(scorer, "stream_ack"):
            stats = scorer.run_scorer(kb, max_items=10)

        assert stats["alerts"] == 0
        assert stats["stale_skipped"] == 1
        m_pub.assert_not_called()
        kb.close()

    def test_env_override_widens_the_window(self, tmp_path, monkeypatch):
        """(c) ENV: the SAME 2h-old item passes under a widened
        GARUDA_ALERT_MAX_AGE_H=72 — proves the env var is actually read,
        not a hardcoded constant."""
        monkeypatch.setenv("GARUDA_ALERT_MAX_AGE_H", "72")
        kb = KnowledgeBase(db_path=tmp_path / "db.db")
        now_ms = int(time.time() * 1000)
        two_hour_old_id = f"{now_ms - 2 * H}-0"
        items = [_item(two_hour_old_id, SIGNAL_TITLE)]

        with patch.object(scorer, "stream_read_new", return_value=items), \
             patch.object(scorer, "stream_publish") as m_pub, \
             patch.object(scorer, "stream_ack"):
            stats = scorer.run_scorer(kb, max_items=10)

        assert stats["alerts"] == 1
        assert stats["stale_skipped"] == 0
        m_pub.assert_called_once()
        kb.close()

    def test_default_window_is_48h(self, tmp_path):
        """(c) ENV: with no override, the 2h-old item from the tightened-window
        test above is well within the 48h default and must NOT be skipped."""
        kb = KnowledgeBase(db_path=tmp_path / "db.db")
        now_ms = int(time.time() * 1000)
        two_hour_old_id = f"{now_ms - 2 * H}-0"
        items = [_item(two_hour_old_id, SIGNAL_TITLE)]

        with patch.object(scorer, "stream_read_new", return_value=items), \
             patch.object(scorer, "stream_publish") as m_pub, \
             patch.object(scorer, "stream_ack"):
            stats = scorer.run_scorer(kb, max_items=10)

        assert stats["alerts"] == 1
        assert stats["stale_skipped"] == 0
        m_pub.assert_called_once()
        kb.close()

    def test_below_signal_score_never_alerts_regardless_of_age(self, tmp_path):
        """Sanity check: the freshness gate only applies to items that WOULD
        alert. A low-score item still doesn't alert, fresh or not — and the
        gate must not accidentally count it as stale_skipped."""
        kb = KnowledgeBase(db_path=tmp_path / "db.db")
        now_ms = int(time.time() * 1000)
        fresh_id = f"{now_ms}-0"
        # "Cooking pasta" matches no keyword fast-path AND is not mocked to
        # reach Ollama, so score_with_ollama's own timeout/exception fallback
        # (score=2, topic=other) applies — well below SCORE_SIGNAL=4.
        items = [_item(fresh_id, "Cooking pasta in Sicily", source="lifestyle blog")]

        with patch.object(scorer, "stream_read_new", return_value=items), \
             patch.object(scorer.subprocess, "run",
                          side_effect=scorer.subprocess.TimeoutExpired(cmd="curl", timeout=60)), \
             patch.object(scorer, "stream_publish") as m_pub, \
             patch.object(scorer, "stream_ack"):
            stats = scorer.run_scorer(kb, max_items=10)

        assert stats["alerts"] == 0
        assert stats["stale_skipped"] == 0
        m_pub.assert_not_called()
        kb.close()


class TestItemAgeHours:
    """Unit tests for the _item_age_hours helper in isolation."""

    def test_parses_valid_id(self):
        now_ms = 10_000_000
        msg_id = f"{now_ms - 2 * H}-3"
        assert scorer._item_age_hours(msg_id, now_ms) == pytest.approx(2.0)

    def test_unparseable_id_returns_none(self):
        now_ms = 10_000_000
        assert scorer._item_age_hours("not-an-id", now_ms) is None
        assert scorer._item_age_hours("", now_ms) is None

    def test_zero_age_for_just_published_item(self):
        now_ms = 10_000_000
        assert scorer._item_age_hours(f"{now_ms}-0", now_ms) == 0.0
