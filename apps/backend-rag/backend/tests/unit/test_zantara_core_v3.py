"""Smoke + structural tests for zantara_core_v3 (worked-examples layer)."""

from backend.prompts import zantara_core, zantara_core_v2, zantara_core_v3
from backend.prompts.business_rules_i18n import BUSINESS_PHRASES_I18N


class TestSectionPresence:
    def test_worked_examples_section_is_non_empty(self) -> None:
        section = zantara_core_v3.WORKED_EXAMPLES
        assert isinstance(section, str)
        assert section.strip()
        assert len(section) > 1000, "WORKED_EXAMPLES should be substantial (>1KB)"

    def test_master_template_includes_worked_examples(self) -> None:
        assert (
            zantara_core_v3.WORKED_EXAMPLES
            in zantara_core_v3.ZANTARA_MASTER_TEMPLATE
        )

    def test_v3_inherits_all_v2_sections(self) -> None:
        master = zantara_core_v3.ZANTARA_MASTER_TEMPLATE
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
            assert section in master, f"v3 master missing v2 section {name}"


class TestDomainCoverage:
    """Each domain must have at least one worked example in the IT/EN/ID
    set, and the surrounding tags must be present."""

    def test_pricing_domain_present(self) -> None:
        section = zantara_core_v3.WORKED_EXAMPLES
        # Three pricing examples (it/en/id) — verify each surfaces a
        # tool call and a real visa code.
        assert "PRICING — happy path" in section
        assert "get_pricing(service_type=" in section
        assert "Italian:" in section and "English:" in section and "Indonesian:" in section
        # Real visa code from the canary set
        assert "C1" in section

    def test_pricing_fallback_uses_business_phrase(self) -> None:
        section = zantara_core_v3.WORKED_EXAMPLES
        assert "PRICING — fallback" in section
        # The IT/EN variants of verify_with_team must surface in this section
        # (rendered inline by _render_phrase_choices).
        for variant in BUSINESS_PHRASES_I18N["verify_with_team"].values():
            assert variant in section, (
                f"verify_with_team variant missing in WORKED_EXAMPLES: {variant!r}"
            )

    def test_visa_domain_present(self) -> None:
        section = zantara_core_v3.WORKED_EXAMPLES
        assert "VISA — multi-language" in section
        assert "knowledge_graph_search(" in section
        assert "KITAS" in section

    def test_tax_domain_present_including_pkp_query(self) -> None:
        """The exact ID query that v2 used to abstain on must appear as
        an exemplar so the model copies the pattern."""
        section = zantara_core_v3.WORKED_EXAMPLES
        assert "TAX — multi-language" in section
        assert "vector_search(" in section
        assert "tax_genius" in section
        # The canary regression query
        assert "Kapan PT PMA harus mendaftar PKP" in section
        # The expected answer pattern (4.8 billion threshold)
        assert "4,8" in section or "4.8" in section

    def test_kbli_domain_present_with_navigator_pointer(self) -> None:
        section = zantara_core_v3.WORKED_EXAMPLES
        assert "KBLI 2025 — multi-language" in section
        assert "kbli_2025_final" in section
        # Navigator URL must be in the answer template
        assert "balizero.com/kbli" in section

    def test_escalation_uses_business_phrase(self) -> None:
        section = zantara_core_v3.WORKED_EXAMPLES
        assert "ESCALATION" in section
        for variant in BUSINESS_PHRASES_I18N["connect_with_team"].values():
            assert variant in section, (
                f"connect_with_team variant missing: {variant!r}"
            )

    def test_identity_lock_uses_redirect_phrase(self) -> None:
        section = zantara_core_v3.WORKED_EXAMPLES
        assert "IDENTITY-LOCK" in section
        for variant in BUSINESS_PHRASES_I18N["redirect_to_indonesia_long"].values():
            assert variant in section


class TestProtocolPreservation:
    def test_language_protocol_byte_identical_with_v1(self) -> None:
        # The meta-rule must not drift across v1 → v2 → v3.
        assert (
            zantara_core_v3.LANGUAGE_PROTOCOL
            == zantara_core_v2.LANGUAGE_PROTOCOL
            == zantara_core.LANGUAGE_PROTOCOL
        )


class TestPlaceholdersPreservedForFstringSubstitution:
    """SystemPromptBuilder.format(...) at runtime injects user_memory,
    rag_results, query — the placeholders MUST survive the v3 assembly."""

    def test_runtime_placeholders_present(self) -> None:
        master = zantara_core_v3.ZANTARA_MASTER_TEMPLATE
        for placeholder in ("{user_memory}", "{rag_results}", "{query}"):
            assert placeholder in master, (
                f"v3 master template lost placeholder {placeholder}"
            )


class TestPromptSizeIsReasonable:
    """v3 adds a substantial WORKED_EXAMPLES section but the total prompt
    must stay within Gemini's effective attention window. Ballpark target:
    under 50KB (well under the model's 1M-token context, but more about
    keeping attention focused than about hard limits)."""

    def test_total_prompt_under_50kb(self) -> None:
        size_kb = len(zantara_core_v3.ZANTARA_MASTER_TEMPLATE) / 1024
        assert size_kb < 50, (
            f"v3 master template is {size_kb:.1f}KB — review WORKED_EXAMPLES "
            "for verbosity"
        )

    def test_v3_is_larger_than_v2(self) -> None:
        # Sanity: v3 should be larger than v2 (we ADDED a section). If they
        # are the same size, the WORKED_EXAMPLES wasn't actually inserted.
        v2_size = len(zantara_core_v2.ZANTARA_MASTER_TEMPLATE)
        v3_size = len(zantara_core_v3.ZANTARA_MASTER_TEMPLATE)
        assert v3_size > v2_size + 1000, (
            f"v3 ({v3_size}) should be at least 1KB larger than v2 ({v2_size}) "
            "after adding WORKED_EXAMPLES"
        )
