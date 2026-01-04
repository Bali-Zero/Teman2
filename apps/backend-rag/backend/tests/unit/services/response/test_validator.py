"""
Unit tests for ZantaraResponseValidator
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.response.validator import ValidationResult, ZantaraResponseValidator


class TestZantaraResponseValidator:
    """Tests for ZantaraResponseValidator"""

    def test_init(self):
        """Test validator initialization"""
        config = {"modes": {"santai": {"max_sentences": 3}}}
        validator = ZantaraResponseValidator(config, dry_run=True)
        assert validator.config == config
        assert validator.dry_run is True
        assert validator.violations == []

    def test_validate_no_modifications(self):
        """Test validation with no modifications needed"""
        config = {"modes": {"santai": {}}}
        validator = ZantaraResponseValidator(config, dry_run=False)
        context = MagicMock()
        context.mode = "santai"

        response = "This is a clean response without any issues."
        result = validator.validate(response, context)

        assert isinstance(result, ValidationResult)
        assert result.original == response
        assert result.validated == response
        assert result.was_modified is False
        assert len(result.violations) == 0

    def test_remove_fillers_certainly(self):
        """Test removing 'Certainly' filler"""
        config = {"modes": {"santai": {}}}
        validator = ZantaraResponseValidator(config, dry_run=False)
        context = MagicMock()
        context.mode = "santai"

        response = "Certainly, here is the answer."
        result = validator.validate(response, context)

        assert "Certainly" not in result.validated
        assert len(result.violations) > 0

    def test_remove_fillers_absolutely(self):
        """Test removing 'Absolutely' filler"""
        config = {"modes": {"santai": {}}}
        validator = ZantaraResponseValidator(config, dry_run=False)
        context = MagicMock()
        context.mode = "santai"

        response = "Absolutely! Here is the information."
        result = validator.validate(response, context)

        assert "Absolutely" not in result.validated
        assert len(result.violations) > 0

    def test_remove_fillers_let_me(self):
        """Test removing 'Let me help' filler"""
        config = {"modes": {"santai": {}}}
        validator = ZantaraResponseValidator(config, dry_run=False)
        context = MagicMock()
        context.mode = "santai"

        response = "Let me help you with that."
        result = validator.validate(response, context)

        assert "Let me help" not in result.validated
        assert len(result.violations) > 0

    def test_remove_fillers_italian(self):
        """Test removing Italian filler phrases"""
        config = {"modes": {"santai": {}}}
        validator = ZantaraResponseValidator(config, dry_run=False)
        context = MagicMock()
        context.mode = "santai"

        response = "Grazie per la domanda. Ecco la risposta."
        result = validator.validate(response, context)

        assert "Grazie per la domanda" not in result.validated
        assert len(result.violations) > 0

    def test_enforce_length_max_sentences(self):
        """Test enforcing maximum sentence limit"""
        config = {"modes": {"santai": {"max_sentences": 2}}}
        validator = ZantaraResponseValidator(config, dry_run=False)
        context = MagicMock()
        context.mode = "santai"

        response = "First sentence. Second sentence. Third sentence. Fourth sentence."
        result = validator.validate(response, context)

        assert result.was_modified is True
        assert len(result.violations) > 0
        # Should be truncated to 2 sentences
        assert result.validated.count(".") <= 2

    def test_enforce_length_no_limit(self):
        """Test validation without length limit"""
        config = {"modes": {"santai": {}}}
        validator = ZantaraResponseValidator(config, dry_run=False)
        context = MagicMock()
        context.mode = "santai"

        response = "First. Second. Third. Fourth."
        result = validator.validate(response, context)

        # Should not be truncated
        assert "Fourth" in result.validated

    def test_ensure_hook_with_question(self):
        """Test hook detection with question mark"""
        config = {"modes": {"santai": {"include_hook": True}}}
        validator = ZantaraResponseValidator(config, dry_run=False)
        context = MagicMock()
        context.mode = "santai"

        response = "Here is the information. Do you need more details?"
        result = validator.validate(response, context)

        # Should not have violation for missing hook
        hook_violations = [v for v in result.violations if "hook" in v.lower()]
        assert len(hook_violations) == 0

    def test_ensure_hook_with_cta(self):
        """Test hook detection with call to action"""
        config = {"modes": {"santai": {"include_hook": True}}}
        validator = ZantaraResponseValidator(config, dry_run=False)
        context = MagicMock()
        context.mode = "santai"

        response = "Here is the information. Dimmi se hai bisogno di altro."
        result = validator.validate(response, context)

        # Should not have violation for missing hook
        hook_violations = [v for v in result.violations if "hook" in v.lower()]
        assert len(hook_violations) == 0

    def test_ensure_hook_missing(self):
        """Test hook detection when hook is missing"""
        config = {"modes": {"santai": {"include_hook": True}}}
        validator = ZantaraResponseValidator(config, dry_run=False)
        context = MagicMock()
        context.mode = "santai"

        response = "Here is the information. That's all."
        result = validator.validate(response, context)

        # Should have violation for missing hook
        hook_violations = [v for v in result.violations if "hook" in v.lower()]
        assert len(hook_violations) > 0

    def test_ensure_hook_disabled(self):
        """Test hook check when disabled"""
        config = {"modes": {"santai": {"include_hook": False}}}
        validator = ZantaraResponseValidator(config, dry_run=False)
        context = MagicMock()
        context.mode = "santai"

        response = "Here is the information."
        result = validator.validate(response, context)

        # Should not check for hook
        hook_violations = [v for v in result.violations if "hook" in v.lower()]
        assert len(hook_violations) == 0

    def test_clean_artifacts_source_brackets(self):
        """Test cleaning source brackets"""
        config = {"modes": {"santai": {}}}
        validator = ZantaraResponseValidator(config, dry_run=False)
        context = MagicMock()
        context.mode = "santai"

        response = "Here is the information. [Source: document.pdf]"
        result = validator.validate(response, context)

        assert "[Source:" not in result.validated
        assert len(result.violations) > 0

    def test_clean_artifacts_excessive_asterisks(self):
        """Test cleaning excessive asterisks"""
        config = {"modes": {"santai": {}}}
        validator = ZantaraResponseValidator(config, dry_run=False)
        context = MagicMock()
        context.mode = "santai"

        response = "Here is the information. ***"
        result = validator.validate(response, context)

        assert "***" not in result.validated
        assert len(result.violations) > 0

    def test_clean_artifacts_multiple_newlines(self):
        """Test cleaning multiple newlines"""
        config = {"modes": {"santai": {}}}
        validator = ZantaraResponseValidator(config, dry_run=False)
        context = MagicMock()
        context.mode = "santai"

        response = "First line.\n\n\nSecond line."
        result = validator.validate(response, context)

        assert "\n\n\n" not in result.validated
        assert len(result.violations) > 0

    def test_dry_run_mode(self):
        """Test dry run mode returns original"""
        config = {"modes": {"santai": {}}}
        validator = ZantaraResponseValidator(config, dry_run=True)
        context = MagicMock()
        context.mode = "santai"

        response = "Certainly, here is the answer."
        result = validator.validate(response, context)

        # In dry run, should return original even if violations detected
        assert result.validated == response
        assert result.was_modified is False
        assert len(result.violations) > 0

    def test_mode_config_not_found(self):
        """Test validation when mode config not found"""
        config = {"modes": {"other_mode": {}}}
        validator = ZantaraResponseValidator(config, dry_run=False)
        context = MagicMock()
        context.mode = "santai"  # Mode not in config

        response = "Here is the response."
        result = validator.validate(response, context)

        # Should still work, just use empty mode config
        assert isinstance(result, ValidationResult)
        assert result.validated == response

    def test_multiple_violations(self):
        """Test validation with multiple violations"""
        config = {"modes": {"santai": {"max_sentences": 2}}}
        validator = ZantaraResponseValidator(config, dry_run=False)
        context = MagicMock()
        context.mode = "santai"

        response = "Certainly! First sentence. Second sentence. Third sentence. [Source: doc.pdf]"
        result = validator.validate(response, context)

        assert result.was_modified is True
        assert len(result.violations) > 1
