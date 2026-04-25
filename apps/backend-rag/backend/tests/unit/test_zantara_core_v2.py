"""Smoke + structural tests for zantara_core_v2.

Goal: catch obvious regressions in the v2 prompt assembly without trying to
score Gemini quality (that requires a live model). We assert:

- All v2 sections are non-empty strings.
- The composite ZANTARA_MASTER_TEMPLATE wires every v2 section.
- The multi-language business phrases are surfaced as instruction lines so
  the model can pick the right variant via LANGUAGE_PROTOCOL.
- The protocol-level meta-rule LANGUAGE_PROTOCOL is preserved verbatim from
  v1 (the v2 layer is content; the protocol stays).
"""

from backend.prompts import zantara_core, zantara_core_v2
from backend.prompts.business_rules_i18n import BUSINESS_PHRASES_I18N


class TestSectionPresence:
    def test_all_v2_sections_are_non_empty_strings(self) -> None:
        for name in (
            "SECURITY_BOUNDARY",
            "TOOL_USAGE_POLICY",
            "GREETING_RULES",
            "INTERNAL_MONOLOGUE",
            "ESCALATION_PROTOCOL",
            "CRASH_PROTOCOL",
            "ZANTARA_MASTER_TEMPLATE",
        ):
            section = getattr(zantara_core_v2, name)
            assert isinstance(section, str)
            assert section.strip(), f"{name} is empty in v2"

    def test_master_template_includes_every_section(self) -> None:
        master = zantara_core_v2.ZANTARA_MASTER_TEMPLATE
        for name in (
            "SECURITY_BOUNDARY",
            "TOOL_USAGE_POLICY",
            "SYSTEM_INSTRUCTIONS",
            "KNOWLEDGE_GOVERNANCE",
            "LANGUAGE_PROTOCOL",
            "GREETING_RULES",
            "CITATION_RULES",
            "ESCALATION_PROTOCOL",
            "CRASH_PROTOCOL",
            "CLOSING_PHRASES",
            "INTERNAL_MONOLOGUE",
        ):
            section = getattr(zantara_core_v2, name)
            assert section in master, f"v2 master template missing {name}"


class TestMultiLanguageBusinessPhrasesSurfaced:
    """For every business phrase referenced via _render_phrase_choices, all three
    language variants must end up inside ZANTARA_MASTER_TEMPLATE — that is what
    lets Gemini pick the right one at runtime."""

    def test_redirect_to_indonesia_short_form_present_in_all_langs(self) -> None:
        master = zantara_core_v2.ZANTARA_MASTER_TEMPLATE
        for variant in BUSINESS_PHRASES_I18N["redirect_to_indonesia"].values():
            assert variant in master, f"missing redirect_to_indonesia variant: {variant!r}"

    def test_verify_with_team_present_in_all_langs(self) -> None:
        master = zantara_core_v2.ZANTARA_MASTER_TEMPLATE
        for variant in BUSINESS_PHRASES_I18N["verify_with_team"].values():
            assert variant in master, f"missing verify_with_team variant: {variant!r}"

    def test_temporary_system_issue_present_in_all_langs(self) -> None:
        master = zantara_core_v2.ZANTARA_MASTER_TEMPLATE
        for variant in BUSINESS_PHRASES_I18N["temporary_system_issue"].values():
            assert variant in master, f"missing temporary_system_issue variant: {variant!r}"


class TestProtocolPreservation:
    def test_language_protocol_section_is_unchanged_from_v1(self) -> None:
        # The protocol itself is the meta-rule — content sections may be rewritten,
        # the protocol must not drift from v1.
        assert zantara_core_v2.LANGUAGE_PROTOCOL == zantara_core.LANGUAGE_PROTOCOL


class TestPlaceholdersPreservedForFstringSubstitution:
    """ZANTARA_MASTER_TEMPLATE is consumed by SystemPromptBuilder.format(...) at
    runtime; the {user_memory}, {rag_results}, {query} placeholders must survive
    the v2 assembly."""

    def test_runtime_placeholders_present(self) -> None:
        master = zantara_core_v2.ZANTARA_MASTER_TEMPLATE
        for placeholder in ("{user_memory}", "{rag_results}", "{query}"):
            assert placeholder in master, f"v2 master template lost placeholder {placeholder}"
