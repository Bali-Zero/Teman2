"""Tests for portal AI recap — facts-locked, prose-polished (FASE 3)."""

from __future__ import annotations

import pytest

from backend.services.portal.recap_service import (
    DISCLAIMER,
    _facts_preserved,
    build_deterministic_recap,
    build_recap,
    polish_recap,
)


class TestDeterministicRecap:
    def test_no_actions_no_deadlines(self):
        text = build_deterministic_recap(
            open_actions=[], upcoming_deadlines=[], unread_messages=0
        )
        assert "Nothing needs your attention" in text

    def test_single_action(self):
        text = build_deterministic_recap(
            open_actions=[{"title": "Upload passport scan"}],
            upcoming_deadlines=[],
            unread_messages=0,
        )
        assert "1 thing" in text
        assert "Upload passport scan" in text

    def test_multiple_actions_count_exact(self):
        text = build_deterministic_recap(
            open_actions=[{"title": "A"}, {"title": "B"}, {"title": "C"}],
            upcoming_deadlines=[],
            unread_messages=0,
        )
        assert "3 things" in text
        assert "starting with A" in text

    def test_deadline_with_days_until(self):
        text = build_deterministic_recap(
            open_actions=[],
            upcoming_deadlines=[{"label": "KITAS expiry", "days_until": 12}],
            unread_messages=0,
        )
        assert "KITAS expiry" in text
        assert "12 day" in text

    def test_deadline_today_is_singular_phrase(self):
        text = build_deterministic_recap(
            open_actions=[],
            upcoming_deadlines=[{"label": "Visa expiry", "days_until": 0}],
            unread_messages=0,
        )
        assert "today" in text

    def test_deadline_due_date_fallback(self):
        text = build_deterministic_recap(
            open_actions=[],
            upcoming_deadlines=[{"label": "Visa expiry", "due_date": "2026-07-01"}],
            unread_messages=0,
        )
        assert "Visa expiry" in text
        assert "2026-07-01" in text

    def test_unread_messages(self):
        text = build_deterministic_recap(
            open_actions=[], upcoming_deadlines=[], unread_messages=3
        )
        assert "3 unread messages" in text

    def test_client_first_name_greeting(self):
        text = build_deterministic_recap(
            open_actions=[],
            upcoming_deadlines=[],
            unread_messages=0,
            client_name="Sarah Connor",
        )
        assert "Sarah" in text
        assert "Connor" not in text  # only first name


class TestFactsPreservedGuard:
    def test_identical_numbers_pass(self):
        assert _facts_preserved("3 actions, 12 days", "You have 3 things, 12 days left")

    def test_changed_number_rejected(self):
        # polished invented a different deadline — must be rejected
        assert not _facts_preserved("12 days", "15 days")

    def test_dropped_number_rejected(self):
        assert not _facts_preserved("3 actions, 12 days", "a few actions, 12 days")

    def test_added_number_rejected(self):
        assert not _facts_preserved("3 actions", "3 actions and 5 more")


class TestBuildRecap:
    @pytest.mark.asyncio
    async def test_no_polish_returns_deterministic(self):
        result = await build_recap(
            open_actions=[{"title": "Upload X"}],
            upcoming_deadlines=[],
            unread_messages=0,
            polish=False,
        )
        assert result["polished"] is False
        assert "Upload X" in result["text"]
        assert result["disclaimer"] == DISCLAIMER

    @pytest.mark.asyncio
    async def test_disclaimer_always_present(self):
        result = await build_recap(
            open_actions=[], upcoming_deadlines=[], unread_messages=0, polish=False
        )
        assert "not legal advice" in result["disclaimer"]

    @pytest.mark.asyncio
    async def test_polish_falls_back_when_ollama_unavailable(self, monkeypatch):
        # Simulate Ollama down → polish_recap must return the deterministic text
        async def boom(*args, **kwargs):
            raise RuntimeError("ollama down")

        import backend.llm.ollama_client as oc

        monkeypatch.setattr(oc, "ollama_generate", boom)
        det = "Welcome back. There are 2 things that need you."
        out = await polish_recap(det)
        assert out == det

    @pytest.mark.asyncio
    async def test_polish_rejected_when_it_alters_facts(self, monkeypatch):
        async def liar(*args, **kwargs):
            return "Welcome back. There are 9 things that need you."  # 2 → 9

        import backend.llm.ollama_client as oc

        monkeypatch.setattr(oc, "ollama_generate", liar)
        det = "Welcome back. There are 2 things that need you."
        out = await polish_recap(det)
        assert out == det  # liar rejected, deterministic kept

    @pytest.mark.asyncio
    async def test_polish_accepted_when_facts_preserved(self, monkeypatch):
        async def faithful(*args, **kwargs):
            return "Hi! Just 2 items need your attention — quick ones."

        import backend.llm.ollama_client as oc

        monkeypatch.setattr(oc, "ollama_generate", faithful)
        det = "Welcome back. There are 2 things that need you."
        out = await polish_recap(det)
        assert out == "Hi! Just 2 items need your attention — quick ones."
