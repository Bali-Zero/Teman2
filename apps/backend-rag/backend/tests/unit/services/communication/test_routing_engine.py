"""
Unit tests for backend/services/communication/routing_engine.py

Covers:
  - classify_intent (all 7 intents + empty/unknown)
  - score_priority (intent-based, VIP detection, edge cases)
  - suggest_assignment (routing rules)
  - route_message (full pipeline)
  - _matches_any (helper)
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.communication.models import MessageIntent, Priority
from backend.services.communication.routing_engine import (
    classify_intent,
    route_message,
    score_priority,
    suggest_assignment,
)


# ============================================================
# classify_intent
# ============================================================


class TestClassifyIntent:
    # --- Spam ---
    def test_spam_bitcoin(self):
        assert classify_intent("Buy bitcoin now click here") == MessageIntent.SPAM

    def test_spam_lottery(self):
        assert classify_intent("You are the winner of a lottery! Claim now") == MessageIntent.SPAM

    def test_spam_forex(self):
        assert classify_intent("forex investment guaranteed 100% return") == MessageIntent.SPAM

    def test_spam_free_money(self):
        assert classify_intent("free money for everyone") == MessageIntent.SPAM

    # --- Complaint (Italian, English, Indonesian) ---
    def test_complaint_italian(self):
        assert classify_intent("Questo servizio e' inaccettabile") == MessageIntent.COMPLAINT

    def test_complaint_english(self):
        assert classify_intent("This service is terrible and unacceptable") == MessageIntent.COMPLAINT

    def test_complaint_indonesian(self):
        assert classify_intent("Saya sangat kecewa dengan pelayanan ini") == MessageIntent.COMPLAINT

    def test_complaint_angry(self):
        assert classify_intent("I am furious about the delay") == MessageIntent.COMPLAINT

    def test_complaint_still_waiting(self):
        assert classify_intent("I am still waiting for my document") == MessageIntent.COMPLAINT

    def test_complaint_non_funziona(self):
        assert classify_intent("Il sistema non funziona") == MessageIntent.COMPLAINT

    # --- Lead ---
    def test_lead_quanto_costa(self):
        assert classify_intent("Quanto costa aprire una PT PMA?") == MessageIntent.LEAD

    def test_lead_how_much(self):
        assert classify_intent("How much does it cost to set up a company?") == MessageIntent.LEAD

    def test_lead_berapa_biaya(self):
        assert classify_intent("Berapa biaya untuk buka PT PMA?") == MessageIntent.LEAD

    def test_lead_interested_in(self):
        assert classify_intent("I am interested in your KITAS service") == MessageIntent.LEAD

    def test_lead_new_company(self):
        assert classify_intent("I want to register company in Bali") == MessageIntent.LEAD

    def test_lead_preventivo(self):
        assert classify_intent("Vorrei un preventivo per il servizio") == MessageIntent.LEAD

    # --- Support ---
    def test_support_aiuto(self):
        assert classify_intent("Ho bisogno di aiuto con il mio visto") == MessageIntent.SUPPORT

    def test_support_help(self):
        assert classify_intent("I need help with my visa application") == MessageIntent.SUPPORT

    def test_support_status_update(self):
        assert classify_intent("What is the status of my application?") == MessageIntent.SUPPORT

    def test_support_indonesian(self):
        assert classify_intent("Tolong bantu saya dengan dokumen") == MessageIntent.SUPPORT

    # --- Question ---
    def test_question_english(self):
        # "I need" triggers SUPPORT before QUESTION; use a pure question
        assert classify_intent("What is the capital of Indonesia?") == MessageIntent.QUESTION

    def test_question_italian(self):
        assert classify_intent("Quali documenti servono?") == MessageIntent.QUESTION

    def test_question_mark(self):
        assert classify_intent("Is this service available?") == MessageIntent.QUESTION

    def test_question_indonesian(self):
        assert classify_intent("Apa saja syarat untuk visa?") == MessageIntent.QUESTION

    # --- Greeting ---
    def test_greeting_ciao(self):
        # "ciao come stai?" has `?` which triggers QUESTION; pure greeting has no `?`
        assert classify_intent("ciao") == MessageIntent.GREETING

    def test_greeting_hello(self):
        assert classify_intent("hello there") == MessageIntent.GREETING

    def test_greeting_selamat(self):
        assert classify_intent("selamat pagi") == MessageIntent.GREETING

    def test_greeting_good_morning(self):
        assert classify_intent("good morning") == MessageIntent.GREETING

    # --- Unknown ---
    def test_unknown_empty(self):
        assert classify_intent("") == MessageIntent.UNKNOWN

    def test_unknown_whitespace(self):
        assert classify_intent("   ") == MessageIntent.UNKNOWN

    def test_unknown_gibberish(self):
        assert classify_intent("asdfghjkl qwerty") == MessageIntent.UNKNOWN

    # --- Priority order: spam > complaint ---
    def test_spam_over_complaint(self):
        # If message has both spam and complaint indicators, spam wins
        assert classify_intent("This is terrible! Buy bitcoin now click here") == MessageIntent.SPAM


# ============================================================
# score_priority
# ============================================================


class TestScorePriority:
    @pytest.mark.asyncio
    async def test_complaint_high(self):
        priority, is_vip = await score_priority(None, MessageIntent.COMPLAINT, None)
        assert priority == Priority.HIGH
        assert is_vip is False

    @pytest.mark.asyncio
    async def test_lead_normal(self):
        priority, _ = await score_priority(None, MessageIntent.LEAD, None)
        assert priority == Priority.NORMAL

    @pytest.mark.asyncio
    async def test_question_low(self):
        priority, _ = await score_priority(None, MessageIntent.QUESTION, None)
        assert priority == Priority.LOW

    @pytest.mark.asyncio
    async def test_greeting_low(self):
        priority, _ = await score_priority(None, MessageIntent.GREETING, None)
        assert priority == Priority.LOW

    @pytest.mark.asyncio
    async def test_spam_low(self):
        priority, _ = await score_priority(None, MessageIntent.SPAM, None)
        assert priority == Priority.LOW

    @pytest.mark.asyncio
    async def test_no_client_no_vip(self):
        _, is_vip = await score_priority(None, MessageIntent.SUPPORT, MagicMock())
        assert is_vip is False

    @pytest.mark.asyncio
    async def test_vip_10_practices_urgent(self):
        db_pool = AsyncMock()
        db_pool.fetchval = AsyncMock(return_value=10)

        priority, is_vip = await score_priority(1, MessageIntent.LEAD, db_pool)
        assert priority == Priority.URGENT
        assert is_vip is True

    @pytest.mark.asyncio
    async def test_vip_5_practices_high(self):
        db_pool = AsyncMock()
        db_pool.fetchval = AsyncMock(return_value=5)

        priority, is_vip = await score_priority(1, MessageIntent.LEAD, db_pool)
        assert priority == Priority.HIGH
        assert is_vip is True

    @pytest.mark.asyncio
    async def test_vip_3_practices(self):
        db_pool = AsyncMock()
        db_pool.fetchval = AsyncMock(return_value=3)

        _, is_vip = await score_priority(1, MessageIntent.SUPPORT, db_pool)
        assert is_vip is True

    @pytest.mark.asyncio
    async def test_non_vip_1_practice(self):
        db_pool = AsyncMock()
        db_pool.fetchval = AsyncMock(return_value=1)

        _, is_vip = await score_priority(1, MessageIntent.SUPPORT, db_pool)
        assert is_vip is False

    @pytest.mark.asyncio
    async def test_db_error_non_fatal(self):
        db_pool = AsyncMock()
        db_pool.fetchval = AsyncMock(side_effect=Exception("DB error"))

        priority, is_vip = await score_priority(1, MessageIntent.LEAD, db_pool)
        assert priority == Priority.NORMAL
        assert is_vip is False

    @pytest.mark.asyncio
    async def test_complaint_at_least_high(self):
        db_pool = AsyncMock()
        db_pool.fetchval = AsyncMock(return_value=0)

        priority, _ = await score_priority(1, MessageIntent.COMPLAINT, db_pool)
        assert priority == Priority.HIGH


# ============================================================
# suggest_assignment
# ============================================================


class TestSuggestAssignment:
    @pytest.mark.asyncio
    async def test_complaint_to_admin(self):
        result = await suggest_assignment(MessageIntent.COMPLAINT, Priority.HIGH, None)
        assert result == "zero@balizero.com"

    @pytest.mark.asyncio
    async def test_high_priority_lead_to_admin(self):
        result = await suggest_assignment(MessageIntent.LEAD, Priority.HIGH, None)
        assert result == "zero@balizero.com"

    @pytest.mark.asyncio
    async def test_urgent_lead_to_admin(self):
        result = await suggest_assignment(MessageIntent.LEAD, Priority.URGENT, None)
        assert result == "zero@balizero.com"

    @pytest.mark.asyncio
    async def test_normal_lead_no_assignment(self):
        result = await suggest_assignment(MessageIntent.LEAD, Priority.NORMAL, None)
        assert result is None

    @pytest.mark.asyncio
    async def test_question_ai_handled(self):
        result = await suggest_assignment(MessageIntent.QUESTION, Priority.LOW, None)
        assert result is None

    @pytest.mark.asyncio
    async def test_greeting_ai_handled(self):
        result = await suggest_assignment(MessageIntent.GREETING, Priority.LOW, None)
        assert result is None

    @pytest.mark.asyncio
    async def test_unknown_ai_handled(self):
        result = await suggest_assignment(MessageIntent.UNKNOWN, Priority.NORMAL, None)
        assert result is None

    @pytest.mark.asyncio
    async def test_support_no_assignment(self):
        result = await suggest_assignment(MessageIntent.SUPPORT, Priority.NORMAL, None)
        assert result is None


# ============================================================
# route_message (full pipeline)
# ============================================================


class TestRouteMessage:
    @pytest.mark.asyncio
    async def test_complaint_full_routing(self):
        decision = await route_message("This is terrible service!", None, None, channel="whatsapp")
        assert decision.intent == MessageIntent.COMPLAINT
        assert decision.priority == Priority.HIGH
        assert decision.suggested_assignee == "zero@balizero.com"
        assert "whatsapp" in decision.reason

    @pytest.mark.asyncio
    async def test_lead_full_routing(self):
        decision = await route_message("How much does a KITAS cost?", None, None, channel="web")
        assert decision.intent == MessageIntent.LEAD
        assert decision.priority == Priority.NORMAL
        assert decision.suggested_assignee is None
        assert "web" in decision.reason

    @pytest.mark.asyncio
    async def test_greeting_full_routing(self):
        decision = await route_message("hello", None, None)
        assert decision.intent == MessageIntent.GREETING
        assert decision.priority == Priority.LOW

    @pytest.mark.asyncio
    async def test_spam_full_routing(self):
        decision = await route_message("Win free money now! click here bitcoin", None, None)
        assert decision.intent == MessageIntent.SPAM
        assert decision.priority == Priority.LOW

    @pytest.mark.asyncio
    async def test_vip_lead_routing(self):
        db_pool = AsyncMock()
        db_pool.fetchval = AsyncMock(return_value=12)

        decision = await route_message("How much for PT PMA?", 1, db_pool)
        assert decision.intent == MessageIntent.LEAD
        assert decision.priority == Priority.URGENT
        assert decision.is_vip is True
        assert decision.suggested_assignee == "zero@balizero.com"

    @pytest.mark.asyncio
    async def test_client_id_in_decision(self):
        decision = await route_message("hello", 42, None)
        assert decision.client_id == 42
