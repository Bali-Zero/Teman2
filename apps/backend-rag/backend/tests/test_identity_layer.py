import pytest
from prompts.zantara_prompt_builder import ZantaraPromptBuilder, PromptContext
from llm.adapters.gemini import GeminiAdapter
from services.response.validator import ZantaraResponseValidator, ValidationResult

# Mock context
@pytest.fixture
def mock_context():
    return PromptContext(
        query="How much is a PT PMA?",
        language="en",
        mode="legal_brief",
        emotional_state="neutral",
        user_name="Test User"
    )

class TestZantaraIdentityLayer:
    
    def test_prompt_builder_structure(self, mock_context):
        """Test that prompt builder assembles all sections correctly"""
        adapter = GeminiAdapter()
        builder = ZantaraPromptBuilder(adapter)
        
        prompt = builder.build(mock_context)
        
        # Check core sections
        assert "IDENTITY" in prompt
        assert "VOICE" in prompt
        assert "LANGUAGE: ENGLISH" in prompt
        assert "RESPONSE MODE: ANSWER_FIRST" in prompt
        assert "EMOTIONAL CONTEXT" in prompt
        assert "FORBIDDEN PATTERNS" in prompt
        
    def test_prompt_builder_language_switch(self):
        """Test language adaptation"""
        adapter = GeminiAdapter()
        builder = ZantaraPromptBuilder(adapter)
        
        ctx_it = PromptContext("Ciao", "it", "greeting", "neutral")
        prompt_it = builder.build(ctx_it)
        assert "LANGUAGE: ITALIAN" in prompt_it
        
        ctx_id = PromptContext("Halo", "id", "greeting", "neutral")
        prompt_id = builder.build(ctx_id)
        assert "LANGUAGE: INDONESIAN (JAKSEL STYLE)" in prompt_id

    def test_validator_filler_removal(self, mock_context):
        """Test that validator removes filler phrases"""
        config = {"modes": {"legal_brief": {"max_sentences": 5}}}
        validator = ZantaraResponseValidator(mode_config=config, dry_run=False)
        
        input_text = "Certainly! Here is the answer. It costs 10 million."
        result = validator.validate(input_text, mock_context)
        
        assert result.was_modified
        assert "Certainly!" not in result.validated
        assert result.validated.startswith("Here is the answer")
        
    def test_validator_length_enforcement(self):
        """Test sentence limit enforcement"""
        config = {"modes": {"short_mode": {"max_sentences": 2}}}
        validator = ZantaraResponseValidator(mode_config=config, dry_run=False)
        
        ctx = PromptContext("q", "en", "short_mode", "neutral")
        input_text = "Sentence one. Sentence two. Sentence three. Sentence four."
        result = validator.validate(input_text, ctx)
        
        assert result.was_modified
        assert result.validated == "Sentence one. Sentence two."
        
    def test_validator_dry_run(self):
        """Test dry run mode doesn't modify text"""
        config = {"modes": {"short_mode": {"max_sentences": 1}}}
        validator = ZantaraResponseValidator(mode_config=config, dry_run=True)
        
        ctx = PromptContext("q", "en", "short_mode", "neutral")
        input_text = "Sentence one. Sentence two."
        result = validator.validate(input_text, ctx)
        
        assert not result.was_modified
        assert result.validated == input_text
        assert len(result.violations) > 0

if __name__ == "__main__":
    # Manual run if pytest not available
    t = TestZantaraIdentityLayer()
    ctx = PromptContext(
        query="How much is a PT PMA?",
        language="en",
        mode="legal_brief",
        emotional_state="neutral",
        user_name="Test User"
    )
    t.test_prompt_builder_structure(ctx)
    t.test_prompt_builder_language_switch()
    t.test_validator_filler_removal()
    t.test_validator_length_enforcement()
    t.test_validator_dry_run()
    print("All manual tests passed!")
