"""
Unit tests for SystemPromptBuilder
Target: 100% coverage
Composer: 1
"""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.rag.agentic.prompt_builder import SystemPromptBuilder


@pytest.fixture
def prompt_builder():
    """Create prompt builder instance"""
    return SystemPromptBuilder()


class TestSystemPromptBuilder:
    """Tests for SystemPromptBuilder"""

    def test_init(self):
        """Test initialization"""
        builder = SystemPromptBuilder()
        assert builder is not None

    def test_build_prompt_basic(self, prompt_builder):
        """Test basic prompt building"""
        user_profile = {"email": "test@example.com", "name": "Test User"}
        query = "What is KITAS?"

        prompt = prompt_builder.build_system_prompt(
            user_id=user_profile.get("email", "test@example.com"),
            context={"user_profile": user_profile},
            query=query,
        )

        assert prompt is not None
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_build_prompt_with_memory_facts(self, prompt_builder):
        """Test prompt building with memory facts"""
        user_profile = {"email": "test@example.com"}
        memory_facts = [{"fact": "User is interested in KITAS", "category": "interest"}]

        prompt = prompt_builder.build_system_prompt(
            user_id=user_profile.get("email", "test@example.com"),
            context={"user_profile": user_profile, "memory_facts": memory_facts},
            query="Tell me about KITAS",
        )

        assert "KITAS" in prompt

    def test_build_prompt_with_collective_facts(self, prompt_builder):
        """Test prompt building with collective facts"""
        user_profile = {"email": "test@example.com"}
        collective_facts = [{"fact": "KITAS costs 15M IDR", "confidence": 0.9}]

        prompt = prompt_builder.build_system_prompt(
            user_id=user_profile.get("email", "test@example.com"),
            context={"user_profile": user_profile, "collective_facts": collective_facts},
            query="What is KITAS?",
        )

        assert prompt is not None

    def test_build_prompt_with_rag_results(self, prompt_builder):
        """Test prompt building with RAG results"""
        user_profile = {"email": "test@example.com"}
        rag_results = "[1] KITAS is a work permit..."

        prompt = prompt_builder.build_system_prompt(
            user_id=user_profile.get("email", "test@example.com"),
            context={"user_profile": user_profile, "rag_results": rag_results},
            query="What is KITAS?",
        )

        assert "KITAS" in prompt

    def test_build_prompt_italian_language(self, prompt_builder):
        """Test prompt building for Italian query"""
        user_profile = {"email": "test@example.com"}
        query = "Cos'è il KITAS?"

        prompt = prompt_builder.build_system_prompt(
            user_id=user_profile.get("email", "test@example.com"),
            context={"user_profile": user_profile},
            query=query,
        )

        assert prompt is not None

    def test_build_prompt_english_language(self, prompt_builder):
        """Test prompt building for English query"""
        user_profile = {"email": "test@example.com"}
        query = "What is KITAS?"

        prompt = prompt_builder.build_system_prompt(
            user_id=user_profile.get("email", "test@example.com"),
            context={"user_profile": user_profile},
            query=query,
        )

        assert prompt is not None

    def test_build_prompt_with_deep_think(self, prompt_builder):
        """Test prompt building with deep think mode"""
        user_profile = {"email": "test@example.com"}

        prompt = prompt_builder.build_system_prompt(
            user_id=user_profile.get("email", "test@example.com"),
            context={"user_profile": user_profile},
            query="Complex question",
            deep_think_mode=True,
        )

        assert prompt is not None

    def test_build_prompt_caching(self, prompt_builder):
        """Test prompt caching"""
        user_profile = {"email": "test@example.com"}

        prompt1 = prompt_builder.build_system_prompt(
            user_id=user_profile.get("email", "test@example.com"),
            context={"user_profile": user_profile},
            query="test",
        )

        prompt2 = prompt_builder.build_system_prompt(
            user_id=user_profile.get("email", "test@example.com"),
            context={"user_profile": user_profile},
            query="test",
        )

        # Should use cache (same inputs)
        assert prompt1 == prompt2

    def test_build_prompt_cache_invalidation(self, prompt_builder):
        """Test cache invalidation on facts change"""
        user_profile = {"email": "test@example.com"}

        prompt1 = prompt_builder.build_system_prompt(
            user_id=user_profile.get("email", "test@example.com"),
            context={"user_profile": user_profile, "facts": []},
            query="test",
        )

        prompt2 = prompt_builder.build_system_prompt(
            user_id=user_profile.get("email", "test@example.com"),
            context={"user_profile": user_profile, "facts": ["new fact"]},
            query="test",
        )

        # Should be different (facts changed) - the cache key includes len(facts)
        # So prompts should differ when facts change
        assert prompt1 != prompt2


class TestDateContextInjection:
    """<date_context>{today_wita}</date_context> (2026-07-17 design doc §3):
    injected by build_system_prompt() at every call, but only visible in the
    OUTPUT when the active template actually has the {today_wita}
    placeholder — that's v4 only, as of this PR. v1/v2/v3 ignore the extra
    kwarg silently (str.format() ignores unused kwargs), which is the
    deliberately invisible default-path behavior §5 commits to.

    ZANTARA_MASTER_TEMPLATE is bound at prompt_builder.py IMPORT time (a
    name-value copy from prompt_manager, not a live reference), so testing
    the v4 case requires reloading prompt_manager under the env var, then
    reloading prompt_builder so it re-binds to the v4 template.
    """

    def test_default_v1_prompt_has_no_date_context_block(self, prompt_builder):
        """Backward-compat anchor: default env (no ZANTARA_PROMPT_VERSION)
        must NOT gain a <date_context> block — v1's template has no such
        placeholder, so today_wita is passed but has nowhere to land."""
        prompt = prompt_builder.build_system_prompt(
            user_id="test@example.com",
            context={"profile": {"email": "test@example.com"}},
            query="Cos'è il KITAS?",
        )
        assert "<date_context>" not in prompt

    def test_v4_prompt_contains_today_wita_date_context(self, monkeypatch):
        """The actual point of F3 (2026-07-17 design doc): once v4 is the
        active template, the built prompt must carry today's WITA date so
        the model can reason about past-vs-future deadlines (F2)."""
        import importlib
        from datetime import datetime
        from zoneinfo import ZoneInfo

        import backend.llm.prompt_manager as pm
        import backend.services.rag.agentic.prompt_builder as pb

        monkeypatch.setenv("ZANTARA_PROMPT_VERSION", "v4")
        try:
            importlib.reload(pm)
            importlib.reload(pb)

            builder = pb.SystemPromptBuilder()
            prompt = builder.build_system_prompt(
                user_id="test@example.com",
                context={"profile": {"email": "test@example.com"}},
                query="Cos'è il KITAS?",
            )

            assert "<date_context>" in prompt
            today_iso = datetime.now(ZoneInfo("Asia/Makassar")).strftime("%Y-%m-%d")
            assert today_iso in prompt
            assert "WITA" in prompt
        finally:
            # Restore module state so later tests in this process see the
            # default (v1) import, matching what a fresh import would give
            # them (cicatrix #10-adjacent: don't leave global state behind).
            monkeypatch.delenv("ZANTARA_PROMPT_VERSION", raising=False)
            importlib.reload(pm)
            importlib.reload(pb)


class TestTemplateFillDoesNotChokeOnEmbeddedBraces:
    """Regression guard for a P0 found live during 2026-07-17/18 verification
    of this lane: v3's (and v4's, which inherits v3's WORKED_EXAMPLES text)
    worked examples embed illustrative JSON as prose, e.g.
    ``Tool returns: {"price_idr": 1700000, ...}``. That text survives the
    template module's OWN f-string escaping as literal single braces, but
    ``str.format()`` (what prompt_builder.py used to call) requires EVERY
    brace pair in the ENTIRE template to be valid format syntax and raises
    ``KeyError('"price_idr"')`` on the first such example.

    This was DORMANT before the F1 split-brain fix in this same PR, because
    prompt_builder.py always imported v1 directly (which has no such JSON
    examples) regardless of ZANTARA_PROMPT_VERSION. Once F1 routes any
    selected version through prompt_manager, and prod's ZANTARA_PROMPT_VERSION
    Fly secret is confirmed set to v3 today, this would have crashed
    system-prompt generation on every one of the 4 live channels on deploy.

    Fixed via ``_safe_template_fill()`` (plain substring replacement of the
    known placeholders only) instead of ``.format()``. This test locks that
    fix in for every currently-selectable version.
    """

    @pytest.mark.parametrize("version", ["v1", "v2", "v3", "v4"])
    def test_build_system_prompt_does_not_raise_for_any_version(self, monkeypatch, version):
        import importlib

        import backend.llm.prompt_manager as pm
        import backend.services.rag.agentic.prompt_builder as pb

        monkeypatch.setenv("ZANTARA_PROMPT_VERSION", version)
        try:
            importlib.reload(pm)
            importlib.reload(pb)

            builder = pb.SystemPromptBuilder()
            # No try/except here on purpose: build_system_prompt() must not
            # raise for any of the 4 selectable versions, full stop.
            prompt = builder.build_system_prompt(
                user_id="test@example.com",
                context={"profile": {"email": "test@example.com"}},
                query="Quanto costa il rinnovo del visto C1 di 60 giorni?",
            )
            assert isinstance(prompt, str)
            assert len(prompt) > 0
        finally:
            monkeypatch.delenv("ZANTARA_PROMPT_VERSION", raising=False)
            importlib.reload(pm)
            importlib.reload(pb)
