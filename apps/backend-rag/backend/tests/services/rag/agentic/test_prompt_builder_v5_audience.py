"""
SystemPromptBuilder wiring for ZANTARA_PROMPT_VERSION=v5 (audience-composed
prompt, backend/prompts/zantara_core_v5.py) through the versioned door
(backend/llm/prompt_manager.py).

Companion to backend/tests/unit/llm/test_prompt_manager.py (door-level) and
backend/tests/unit/prompts/test_zantara_core_v5.py (module-level). This file
covers the CONSUMER side: SystemPromptBuilder.build_system_prompt derives an
`audience` from the server-resolved profile.role (creator/team/*→client) and
threads it through `prompt_manager.get_master_template(audience)`.

Reload discipline: SystemPromptBuilder reads `prompt_manager.PROMPT_VERSION_ACTIVE`
and calls `prompt_manager.get_master_template(...)` via a MODULE reference
(`from backend.llm import prompt_manager`), not a `from ... import NAME`
snapshot — so reloading only `backend.llm.prompt_manager` (not
prompt_builder.py itself) is sufficient for these tests to see the new
version. See prompt_builder.py's import-block comment for why.
"""

import importlib

import pytest

from backend.prompts.zantara_core_v4 import CREATOR_PERSONA, TEAM_PERSONA
from backend.services.rag.agentic.prompt_builder import SystemPromptBuilder


@pytest.fixture(autouse=True)
def _v5_active(monkeypatch):
    """Every test in this file runs with ZANTARA_PROMPT_VERSION=v5 active,
    restored to unset (today's default) afterwards regardless of outcome."""
    import backend.llm.prompt_manager as pm

    monkeypatch.setenv("ZANTARA_PROMPT_VERSION", "v5")
    importlib.reload(pm)
    assert pm.PROMPT_VERSION_ACTIVE == "v5"  # sanity: the fixture itself is armed
    yield
    monkeypatch.delenv("ZANTARA_PROMPT_VERSION", raising=False)
    importlib.reload(pm)


def _build(profile_role, query="What is a PT PMA?"):
    builder = SystemPromptBuilder()
    context = {"profile": {"role": profile_role}} if profile_role else {}
    return builder.build_system_prompt(
        user_id="probe@example.com",
        context=context,
        query=query,
    )


class TestAudienceMapping:
    def test_creator_role_gets_creator_voice_and_capability(self) -> None:
        prompt = _build("creator")
        assert "ARCHITECT MODE" in prompt
        assert "crm_query" in prompt

    def test_team_role_gets_team_voice_and_capability(self) -> None:
        prompt = _build("team")
        assert "INTERNAL TEAM MODE" in prompt
        assert "crm_query" in prompt

    def test_client_default_gets_no_persona_marker_and_no_crm_capability(self) -> None:
        prompt = _build(None)
        assert "ARCHITECT MODE" not in prompt
        assert "INTERNAL TEAM MODE" not in prompt
        assert "crm_query" not in prompt

    def test_unknown_role_falls_back_to_client_never_team_or_creator(self) -> None:
        """The load-bearing security property of this whole change: an
        unresolved/unrecognised role must fail SAFE toward the fewest
        capabilities and the most locked-down voice — never toward
        team/creator by omission or typo."""
        prompt = _build("some-typo-role-nobody-defined")
        assert "ARCHITECT MODE" not in prompt
        assert "INTERNAL TEAM MODE" not in prompt
        assert "crm_query" not in prompt


class TestNoDoublePersonaInjection:
    """v5 bakes the audience voice into master_template itself — the legacy
    CREATOR_PERSONA/TEAM_PERSONA prepend (still active for v1-v4) must be
    SKIPPED under v5, or the persona text would appear twice."""

    def test_creator_persona_appears_exactly_once(self) -> None:
        prompt = _build("creator")
        assert prompt.count(CREATOR_PERSONA) == 1

    def test_team_persona_appears_exactly_once(self) -> None:
        prompt = _build("team")
        assert prompt.count(TEAM_PERSONA) == 1


class TestJakselFlairSurvivesLanguageStrip:
    """Regression pin: the legacy Jaksel-phrase strip (triggered whenever
    build_system_prompt detects a non-Indonesian query) runs over the WHOLE
    composed v5 template. CREATOR_PERSONA's own tone line ("a bit of Jaksel
    flair... dev-to-dev") must survive that strip for creator/team, exactly
    as it already does in v1-v4 (there, persona is prepended AFTER the
    strip, so it was never touched)."""

    def test_creator_persona_survives_english_query(self) -> None:
        prompt = _build("creator", query="What is a PT PMA?")
        assert "Jaksel flair" in prompt

    def test_creator_persona_survives_indonesian_query(self) -> None:
        # Indonesian queries skip the strip branch entirely (detected_lang
        # is falsy) — included so both code paths are pinned, not just one.
        prompt = _build("creator", query="apa itu PT PMA?")
        assert "Jaksel flair" in prompt

    def test_client_build_language_protocol_still_gets_stripped(self) -> None:
        """Parity check: CORE_FACTUAL (shared body) must still lose the
        'Indonesian -> Indonesian (Jaksel style OK)' language-mapping note
        for a non-Indonesian query — same as v1-v4's body always did. Only
        the PERSONA segment is protected, not the whole template."""
        prompt = _build(None, query="What is a PT PMA?")
        assert "Jaksel style OK" not in prompt
