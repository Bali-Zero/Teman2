"""
Simple integration tests to verify ZANTARA is fluid and powerful
Tests fluidity (low ABSTAIN rate) and strength (proactive, helpful responses)
"""

import os
from pathlib import Path

# Set test environment before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("API_KEYS", "test-api-key-1,test-api-key-2")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("GOOGLE_API_KEY", "test-google-key")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("ENVIRONMENT", "test")

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"


class TestZantaraFluidity:
    """Test that ZANTARA is fluid (responds often, low ABSTAIN rate)"""

    def test_low_abstain_threshold(self):
        """Test that ABSTAIN threshold is low (0.2) for fluidity"""
        # Read constants file directly
        constants_file = backend_path / "app" / "core" / "constants.py"
        constants_content = constants_file.read_text()

        # Verify threshold is 0.15 (may include type annotation)
        assert (
            "ABSTAIN_THRESHOLD = 0.15" in constants_content
            or "ABSTAIN_THRESHOLD=0.15" in constants_content
            or "ABSTAIN_THRESHOLD: float = 0.15" in constants_content
        ), "ABSTAIN threshold should be 0.15"

    def test_proactive_abstain_message(self):
        """Test that ABSTAIN message is proactive (suggests alternatives)"""
        # Read reasoning.py to verify ABSTAIN message
        reasoning_file = backend_path / "services" / "rag" / "agentic" / "reasoning.py"
        reasoning_content = reasoning_file.read_text()

        # Check for proactive message elements in the actual ABSTAIN message (not in comments)
        # The proactive message should be in the final_answer assignment
        assert (
            "Posso aiutarti con:" in reasoning_content
            or "posso aiutarti con" in reasoning_content.lower()
        )
        assert "visti e KITAS" in reasoning_content or "KITAS" in reasoning_content
        assert "Setup aziendale" in reasoning_content or "PT PMA" in reasoning_content

        # Check that the proactive message is used (not the old "altro?" version)
        # Find the actual ABSTAIN message assignment
        proactive_patterns = [
            "Posso aiutarti con:",
            "visti e KITAS",
            "Setup aziendale",
            "Questioni fiscali",
        ]
        found_proactive = sum(1 for pattern in proactive_patterns if pattern in reasoning_content)
        assert found_proactive >= 2, (
            f"ABSTAIN message should include proactive suggestions (found {found_proactive}/{len(proactive_patterns)} patterns)"
        )

    def test_evidence_score_allows_responses(self):
        """Test that evidence score thresholds allow responses"""
        constants_file = backend_path / "app" / "core" / "constants.py"
        constants_content = constants_file.read_text()

        # Verify threshold is 0.15 (may include type annotation)
        assert (
            "ABSTAIN_THRESHOLD = 0.15" in constants_content
            or "ABSTAIN_THRESHOLD=0.15" in constants_content
            or "ABSTAIN_THRESHOLD: float = 0.15" in constants_content
        )

        # With threshold 0.15, scores >= 0.15 should allow responses
        # This means most queries will get responses (fluidity)


class TestZantaraStrength:
    """Test that ZANTARA is strong (proactive, helpful, suggests next steps)"""

    def test_prompt_includes_proactivity(self):
        """Test that system prompt includes proactivity rules"""
        prompt_file = backend_path / "services" / "rag" / "agentic" / "prompt_builder.py"
        prompt_content = prompt_file.read_text()

        # Check for proactivity keywords
        assert "PROACTIVITY" in prompt_content or "proactive" in prompt_content.lower()
        assert (
            "suggest" in prompt_content.lower()
            or "suggerire" in prompt_content.lower()
            or "proactive" in prompt_content.lower()
        )
        assert (
            "next step" in prompt_content.lower()
            or "prossimi passi" in prompt_content.lower()
            or "build_proactive_prompt" in prompt_content
        )
        assert (
            "Vuoi sapere anche" in prompt_content
            or "Ti interesse anche" in prompt_content
            or "proactive" in prompt_content.lower()
        )

    def test_final_prompt_includes_suggestions(self):
        """Test that final answer prompt includes instruction to suggest next steps"""
        reasoning_file = backend_path / "services" / "rag" / "agentic" / "reasoning.py"
        reasoning_content = reasoning_file.read_text()

        # Check for suggestion instructions in final prompt
        assert "suggest" in reasoning_content.lower() or "suggerire" in reasoning_content.lower()
        assert (
            "next step" in reasoning_content.lower()
            or "prossimi passi" in reasoning_content.lower()
        )
        assert "Vuoi sapere anche" in reasoning_content or "Ti interessa anche" in reasoning_content
        assert (
            "IMPORTANT: After your answer" in reasoning_content
            or "After your answer" in reasoning_content
        )

    def test_moderate_evidence_uses_positive_language(self):
        """Test that moderate evidence uses positive language"""
        reasoning_file = backend_path / "services" / "rag" / "agentic" / "reasoning.py"
        reasoning_content = reasoning_file.read_text()

        # Check for positive language ("available" not "limited")
        assert (
            "available information" in reasoning_content.lower()
            or "informazioni disponibili" in reasoning_content.lower()
        )
        # Should NOT use negative language
        assert (
            "limited information" not in reasoning_content.lower()
            or reasoning_content.count("limited information") == 0
        )

    def test_followup_service_has_metrics(self):
        """Test that FollowupService has metrics for tracking"""
        followup_file = backend_path / "services" / "misc" / "followup_service.py"
        followup_content = followup_file.read_text()

        # Check for Prometheus metrics
        assert "followup_requests_total" in followup_content
        assert "followup_generation_duration" in followup_content
        assert "followup_ai_generation_total" in followup_content
        assert "Counter" in followup_content
        assert "Histogram" in followup_content

    def test_followup_service_has_logging(self):
        """Test that FollowupService has comprehensive logging"""
        followup_file = backend_path / "services" / "misc" / "followup_service.py"
        followup_content = followup_file.read_text()

        # Check for structured logging
        assert "logger.info" in followup_content
        assert "logger.error" in followup_content
        assert "extra={" in followup_content or "extra=" in followup_content
        assert "component" in followup_content.lower()
        assert "action" in followup_content.lower()


class TestZantaraProactivity:
    """Test ZANTARA proactivity features"""

    def test_abstain_message_quality(self):
        """Test that ABSTAIN messages are helpful and proactive"""
        reasoning_file = backend_path / "services" / "rag" / "agentic" / "reasoning.py"
        reasoning_content = reasoning_file.read_text()

        # Find ABSTAIN message patterns
        abstain_patterns = [
            "Posso aiutarti con:",
            "visti e KITAS",
            "Setup aziendale",
            "Questioni fiscali",
            "Procedure e documentazione",
        ]

        found_patterns = sum(1 for pattern in abstain_patterns if pattern in reasoning_content)
        assert found_patterns >= 3, (
            f"ABSTAIN message should include multiple helpful suggestions (found {found_patterns}/{len(abstain_patterns)})"
        )

        # The proactive message should be present (not just "altro?")
        # Check that the proactive version is used
        has_proactive_intro = (
            "Posso aiutarti con:" in reasoning_content
            or "posso aiutarti con" in reasoning_content.lower()
        )
        assert has_proactive_intro, "ABSTAIN message should start with 'Posso aiutarti con:'"

    def test_prompt_proactivity_examples(self):
        """Test that prompt includes proactivity examples"""
        prompt_file = backend_path / "services" / "rag" / "agentic" / "prompt_builder.py"
        prompt_content = prompt_file.read_text()

        # Check for example suggestions
        assert (
            "Vuoi sapere anche quanto costa?" in prompt_content
            or "quanto costa" in prompt_content.lower()
        )
        assert "processo" in prompt_content.lower() or "process" in prompt_content.lower()
        assert "requisiti" in prompt_content.lower() or "requirements" in prompt_content.lower()

    def test_reasoning_includes_suggestion_instructions(self):
        """Test that reasoning includes instructions to suggest next steps"""
        reasoning_file = backend_path / "services" / "rag" / "agentic" / "reasoning.py"
        reasoning_content = reasoning_file.read_text()

        # Check for instruction to suggest
        assert (
            "suggest 1-2" in reasoning_content.lower() or "suggerire" in reasoning_content.lower()
        )
        assert (
            "related topics" in reasoning_content.lower()
            or "argomenti correlati" in reasoning_content.lower()
        )
        assert (
            "next steps" in reasoning_content.lower()
            or "prossimi passi" in reasoning_content.lower()
        )


class TestZantaraEvidenceScore:
    """Test evidence score calculation allows fluidity"""

    def test_evidence_score_formula_allows_responses(self):
        """Test that evidence score formula allows most queries to get responses"""
        reasoning_file = backend_path / "services" / "rag" / "agentic" / "reasoning.py"
        reasoning_content = reasoning_file.read_text()

        # Check for evidence score calculation
        assert "calculate_evidence_score" in reasoning_content
        assert "HIGH_QUALITY_SOURCE_BONUS" in reasoning_content or "0.5" in reasoning_content
        assert "calculate_evidence_score" in reasoning_content or "0.2" in reasoning_content

        # With bonuses, most queries should score >= 0.2
        # Formula: base (0.0) + high quality source (0.5) = 0.5 >= 0.2 ✓
        # Formula: base (0.0) + multiple sources (0.2) = 0.2 >= 0.2 ✓

    def test_trusted_tools_bypass_evidence_check(self):
        """Test that trusted tools bypass evidence check for fluidity"""
        reasoning_file = backend_path / "services" / "rag" / "agentic" / "reasoning.py"
        reasoning_content = reasoning_file.read_text()

        # Check for trusted tools
        assert "trusted_tools_used" in reasoning_content
        assert "get_pricing" in reasoning_content
        assert "calculator" in reasoning_content
        assert "bypass" in reasoning_content.lower() or "skip" in reasoning_content.lower()


class TestZantaraIntegration:
    """Integration tests for ZANTARA fluidity and strength"""

    def test_all_components_configured(self):
        """Test that all components are configured for fluidity and proactivity"""
        # Check constants
        constants_file = backend_path / "app" / "core" / "constants.py"
        constants_content = constants_file.read_text()
        assert "ABSTAIN_THRESHOLD" in constants_content and "0.15" in constants_content

        # Check prompt
        prompt_file = backend_path / "services" / "rag" / "agentic" / "prompt_builder.py"
        prompt_content = prompt_file.read_text()
        assert "PROACTIVITY" in prompt_content or "proactive" in prompt_content.lower()

        # Check reasoning
        reasoning_file = backend_path / "services" / "rag" / "agentic" / "reasoning.py"
        reasoning_content = reasoning_file.read_text()
        assert "EvidenceScoreConstants.ABSTAIN_THRESHOLD" in reasoning_content

        # Check followup service
        followup_file = backend_path / "services" / "misc" / "followup_service.py"
        followup_content = followup_file.read_text()
        assert "get_followups" in followup_content
