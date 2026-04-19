"""Tests for regulation_alert_agent — W3 Wave 2."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from mata_garuda.agents import regulation_alert_agent as raa
from mata_garuda.runtime.knowledge import KnowledgeBase


def _alert(i: int, **overrides) -> dict:
    base = {
        "id": f"{i}-0",
        "data": {
            "title": f"Alert {i}",
            "topic": "tax_fiscal",
            "source": "ddtc.co.id",
            "url": f"https://ex.com/{i}",
            "score": "4.5",
            "reason": "New PMK",
            "alert_time": "2026-04-20T07:00:00",
        },
    }
    base["data"].update(overrides)
    return base


class TestFormatAlert:
    def test_contains_core_fields(self):
        msg = raa.format_alert({
            "title": "PMK 25/2026",
            "topic": "tax_fiscal",
            "source": "ddtc.co.id",
            "url": "https://ex/pmk",
            "score": "4.2",
            "reason": "New tax rule",
        })
        assert "PMK 25/2026" in msg
        assert "tax_fiscal" in msg
        assert "4.2" in msg
        assert "https://ex/pmk" in msg
        assert "New tax rule" in msg

    def test_handles_missing_title(self):
        msg = raa.format_alert({})
        assert "(senza titolo)" in msg

    def test_kind_aliases(self):
        msg1 = raa.format_alert({"alert_kind": "contradiction"})
        msg2 = raa.format_alert({"kind": "semantic_diff"})
        assert "contradiction" in msg1
        assert "semantic_diff" in msg2


class TestRunner:
    def test_drains_alerts_and_sends_each(self, tmp_path):
        kb = KnowledgeBase(db_path=tmp_path / "db.db")
        alerts = [_alert(i) for i in range(3)]

        with patch.object(raa, "stream_read_new", return_value=alerts), \
             patch.object(raa, "_send_telegram", return_value=True) as m_tg, \
             patch.object(raa, "stream_ack") as m_ack:
            stats = raa.run_regulation_alert(kb=kb, dry_run=False)

        assert stats["processed"] == 3
        assert stats["sent"] == 3
        assert stats["failed"] == 0
        assert m_tg.call_count == 3
        assert m_ack.call_count == 3
        kb.close()

    def test_tg_failure_still_acks_and_logs_case_not_resolved(self, tmp_path):
        kb = KnowledgeBase(db_path=tmp_path / "db.db")
        alerts = [_alert(1)]
        with patch.object(raa, "stream_read_new", return_value=alerts), \
             patch.object(raa, "_send_telegram", return_value=False), \
             patch.object(raa, "stream_ack") as m_ack:
            stats = raa.run_regulation_alert(kb=kb)

        assert stats["failed"] == 1
        assert stats["sent"] == 0
        # ACK still happens (no retry storm)
        m_ack.assert_called_once()
        # case_not_resolved stored
        crn = kb.get_by_type("case_not_resolved", limit=5)
        assert any("tg_send_failed" in r["content"] for r in crn)
        kb.close()

    def test_empty_stream(self, tmp_path):
        kb = KnowledgeBase(db_path=tmp_path / "db.db")
        with patch.object(raa, "stream_read_new", return_value=[]):
            stats = raa.run_regulation_alert(kb=kb)
        assert stats == {"processed": 0, "sent": 0, "failed": 0}
        kb.close()

    def test_dry_run_skips_real_tg(self, tmp_path):
        kb = KnowledgeBase(db_path=tmp_path / "db.db")
        alerts = [_alert(1)]
        with patch.object(raa, "stream_read_new", return_value=alerts), \
             patch("subprocess.run") as m_run, \
             patch.object(raa, "stream_ack"):
            stats = raa.run_regulation_alert(kb=kb, dry_run=True)
        assert stats["sent"] == 1
        # Real curl subprocess never invoked under dry_run
        m_run.assert_not_called()
        kb.close()
