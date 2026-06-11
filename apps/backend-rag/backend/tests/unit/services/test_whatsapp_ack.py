"""Unit tests for the concierge ack heuristics (whatsapp_ack)."""

from __future__ import annotations

import pytest

from backend.services import whatsapp_ack as ack


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    ack._reset_for_testing()
    monkeypatch.delenv("WHATSAPP_ACK_ENABLED", raising=False)
    yield
    ack._reset_for_testing()


class TestShouldSendAck:
    def test_consultation_question_gets_ack(self):
        q = "How much does the 2-year investor KITAS cost and what documents do I need?"
        assert ack.should_send_ack(q, "62811111") is True

    def test_greeting_skipped(self):
        assert ack.should_send_ack("Hello", "62811111") is False
        assert ack.should_send_ack("selamat pagi", "62811111") is False

    def test_thanks_skipped_even_with_padding(self):
        assert ack.should_send_ack("ok thanks!! 🙏", "62811111") is False
        assert ack.should_send_ack("terima kasih 🙏", "62811111") is False

    def test_short_message_skipped(self):
        assert ack.should_send_ack("price?", "62811111") is False

    def test_throttle_blocks_second_ack_within_window(self):
        q = "I want to open a beach club in Canggu, which KBLI codes apply?"
        assert ack.should_send_ack(q, "62822222", now=1000.0) is True
        ack.mark_acked("62822222", now=1000.0)
        assert ack.should_send_ack(q, "62822222", now=1060.0) is False
        # Window elapsed → ack again.
        assert ack.should_send_ack(q, "62822222", now=1000.0 + 121.0) is True

    def test_throttle_is_per_phone(self):
        q = "Berapa biaya perpanjangan KITAS investor dan dokumen apa saja?"
        ack.mark_acked("62833333", now=1000.0)
        assert ack.should_send_ack(q, "62844444", now=1010.0) is True

    def test_kill_switch(self, monkeypatch):
        monkeypatch.setenv("WHATSAPP_ACK_ENABLED", "false")
        q = "How much does the 2-year investor KITAS cost and what documents?"
        assert ack.should_send_ack(q, "62855555") is False


class TestAckText:
    def test_known_languages(self):
        assert "cek" in ack.ack_text("id")
        assert "verifico" in ack.ack_text("it")
        assert "check" in ack.ack_text("en")

    def test_unknown_language_falls_back_to_english(self):
        assert ack.ack_text("de") == ack.ack_text("en")
        assert ack.ack_text(None) == ack.ack_text("en")
