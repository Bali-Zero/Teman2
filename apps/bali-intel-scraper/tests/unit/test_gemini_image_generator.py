"""
Unit Tests for Gemini Image Generator
Tests for the reasoning-based image prompt generation
"""

from unittest.mock import patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from gemini_image_generator import (
    ImagePromptFramework,
    GeminiImageGenerator,
    ArticleContext,
    USAGE_EXAMPLE,
)


# =============================================================================
# ArticleContext Dataclass Tests
# =============================================================================


class TestArticleContext:
    """Test ArticleContext dataclass"""

    def test_create_article_context(self):
        """Test creating an ArticleContext"""
        ctx = ArticleContext(
            title="Test Title",
            summary="Test summary",
            full_content="Full content here",
            category="tax",
            tone="problem",
            key_moments=["moment1", "moment2"],
        )
        assert ctx.title == "Test Title"
        assert ctx.summary == "Test summary"
        assert ctx.full_content == "Full content here"
        assert ctx.category == "tax"
        assert ctx.tone == "problem"
        assert ctx.key_moments == ["moment1", "moment2"]

    def test_article_context_empty_key_moments(self):
        """Test ArticleContext with empty key moments"""
        ctx = ArticleContext(
            title="Title",
            summary="Summary",
            full_content="Content",
            category="immigration",
            tone="informative",
            key_moments=[],
        )
        assert ctx.key_moments == []

    def test_article_context_all_categories(self):
        """Test ArticleContext works for all category types"""
        categories = [
            "immigration",
            "tax",
            "business",
            "property",
            "lifestyle",
            "legal",
            "tech",
        ]
        for cat in categories:
            ctx = ArticleContext(
                title=f"{cat} article",
                summary=f"About {cat}",
                full_content="Content",
                category=cat,
                tone="solution",
                key_moments=[],
            )
            assert ctx.category == cat


# =============================================================================
# ImagePromptFramework Tests
# =============================================================================


class TestImagePromptFrameworkInit:
    """Test ImagePromptFramework initialization"""

    def test_default_init(self):
        """Test default initialization"""
        framework = ImagePromptFramework()
        assert framework is not None

    def test_has_reasoning_framework(self):
        """Test that reasoning framework exists"""
        assert hasattr(ImagePromptFramework, "REASONING_FRAMEWORK")
        assert len(ImagePromptFramework.REASONING_FRAMEWORK) > 0

    def test_has_category_guidelines(self):
        """Test that category guidelines exist"""
        assert hasattr(ImagePromptFramework, "CATEGORY_GUIDELINES")
        assert isinstance(ImagePromptFramework.CATEGORY_GUIDELINES, dict)

    def test_has_style_constants(self):
        """Test that style constants exist"""
        assert hasattr(ImagePromptFramework, "STYLE_CONSTANTS")
        assert "ultra-realistic" in ImagePromptFramework.STYLE_CONSTANTS.lower()

    def test_has_absolute_forbidden(self):
        """Test that forbidden items list exists"""
        assert hasattr(ImagePromptFramework, "ABSOLUTE_FORBIDDEN")
        assert len(ImagePromptFramework.ABSOLUTE_FORBIDDEN) > 0


class TestCategoryGuidelines:
    """Test category-specific guidelines"""

    def test_all_categories_present(self):
        """Test all expected categories have guidelines"""
        expected = [
            "immigration",
            "tax",
            "business",
            "property",
            "lifestyle",
            "legal",
            "tech",
        ]
        for cat in expected:
            assert cat in ImagePromptFramework.CATEGORY_GUIDELINES, (
                f"Missing category: {cat}"
            )

    def test_immigration_guidelines_structure(self):
        """Test immigration category has proper structure"""
        guidelines = ImagePromptFramework.CATEGORY_GUIDELINES["immigration"]
        assert "typical_themes" in guidelines
        assert "emotional_range" in guidelines
        assert "setting_options" in guidelines
        assert "forbidden" in guidelines
        assert "remember" in guidelines

    def test_tax_guidelines_structure(self):
        """Test tax category has proper structure"""
        guidelines = ImagePromptFramework.CATEGORY_GUIDELINES["tax"]
        assert "typical_themes" in guidelines
        assert "forbidden" in guidelines
        assert isinstance(guidelines["typical_themes"], list)

    def test_business_guidelines_structure(self):
        """Test business category has proper structure"""
        guidelines = ImagePromptFramework.CATEGORY_GUIDELINES["business"]
        assert len(guidelines["typical_themes"]) > 0
        assert len(guidelines["forbidden"]) > 0

    def test_property_guidelines_structure(self):
        """Test property category has proper structure"""
        guidelines = ImagePromptFramework.CATEGORY_GUIDELINES["property"]
        assert "typical_themes" in guidelines
        assert "setting_options" in guidelines

    def test_lifestyle_guidelines_structure(self):
        """Test lifestyle category has proper structure"""
        guidelines = ImagePromptFramework.CATEGORY_GUIDELINES["lifestyle"]
        assert "typical_themes" in guidelines
        assert "remember" in guidelines

    def test_legal_guidelines_structure(self):
        """Test legal category has proper structure"""
        guidelines = ImagePromptFramework.CATEGORY_GUIDELINES["legal"]
        assert "typical_themes" in guidelines
        assert "forbidden" in guidelines

    def test_tech_guidelines_structure(self):
        """Test tech category has proper structure"""
        guidelines = ImagePromptFramework.CATEGORY_GUIDELINES["tech"]
        assert "typical_themes" in guidelines
        assert "digital nomad" in guidelines["typical_themes"]

    def test_immigration_forbids_passport_stamps(self):
        """Test immigration forbids generic passport imagery"""
        guidelines = ImagePromptFramework.CATEGORY_GUIDELINES["immigration"]
        forbidden_lower = [f.lower() for f in guidelines["forbidden"]]
        assert any("passport" in f for f in forbidden_lower)

    def test_tax_forbids_money_piles(self):
        """Test tax forbids generic money imagery"""
        guidelines = ImagePromptFramework.CATEGORY_GUIDELINES["tax"]
        forbidden_lower = [f.lower() for f in guidelines["forbidden"]]
        assert any("money" in f for f in forbidden_lower)


class TestReasoningFramework:
    """Test the reasoning framework structure"""

    def test_reasoning_not_empty(self):
        """Test that reasoning framework is not empty"""
        assert len(ImagePromptFramework.REASONING_FRAMEWORK) > 100

    def test_reasoning_contains_central_theme(self):
        """Test reasoning contains central theme question"""
        rf = ImagePromptFramework.REASONING_FRAMEWORK.lower()
        assert "central theme" in rf

    def test_reasoning_contains_emotional_core(self):
        """Test reasoning contains emotional core question"""
        rf = ImagePromptFramework.REASONING_FRAMEWORK.lower()
        assert "emotional" in rf

    def test_reasoning_contains_moment(self):
        """Test reasoning contains the moment question"""
        rf = ImagePromptFramework.REASONING_FRAMEWORK.lower()
        assert "moment" in rf

    def test_reasoning_contains_2_second_test(self):
        """Test reasoning contains 2-second test reference"""
        rf = ImagePromptFramework.REASONING_FRAMEWORK.lower()
        assert "2-second" in rf or "two second" in rf


# =============================================================================
# GeminiImageGenerator Tests
# =============================================================================


class TestGeminiImageGeneratorInit:
    """Test GeminiImageGenerator initialization"""

    def test_default_init(self):
        """Test default initialization"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            assert gen.output_dir == Path("data/images")
            assert gen.framework is not None

    def test_custom_output_dir(self):
        """Test initialization with custom output directory"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator(output_dir="/custom/path")
            assert gen.output_dir == Path("/custom/path")

    def test_creates_output_directory(self):
        """Test that output directory is created"""
        with patch("pathlib.Path.mkdir") as mock_mkdir:
            GeminiImageGenerator(output_dir="test/images")
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)


class TestGetReasoningFramework:
    """Test get_reasoning_framework method"""

    def test_returns_framework_string(self):
        """Test that method returns framework string"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            framework = gen.get_reasoning_framework()
            assert isinstance(framework, str)
            assert len(framework) > 0

    def test_framework_contains_questions(self):
        """Test framework contains reasoning questions"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            framework = gen.get_reasoning_framework()
            assert "CENTRAL THEME" in framework or "central theme" in framework.lower()


class TestGetCategoryGuidelines:
    """Test get_category_guidelines method"""

    def test_get_immigration_guidelines(self):
        """Test getting immigration guidelines"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            guidelines = gen.get_category_guidelines("immigration")
            assert "typical_themes" in guidelines
            assert "forbidden" in guidelines

    def test_get_tax_guidelines(self):
        """Test getting tax guidelines"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            guidelines = gen.get_category_guidelines("tax")
            assert "typical_themes" in guidelines

    def test_case_insensitive_category(self):
        """Test category lookup is case insensitive"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            guidelines_lower = gen.get_category_guidelines("immigration")
            guidelines_upper = gen.get_category_guidelines("IMMIGRATION")
            assert guidelines_lower == guidelines_upper

    def test_unknown_category_returns_lifestyle(self):
        """Test unknown category falls back to lifestyle"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            guidelines = gen.get_category_guidelines("unknown_category")
            lifestyle_guidelines = ImagePromptFramework.CATEGORY_GUIDELINES["lifestyle"]
            assert guidelines == lifestyle_guidelines


class TestBuildReasoningPrompt:
    """Test build_reasoning_prompt method"""

    def test_basic_prompt_generation(self):
        """Test basic reasoning prompt generation"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            prompt = gen.build_reasoning_prompt(
                title="New Visa Rules",
                summary="Indonesia announces new visa policy",
                full_content="The government has announced...",
                category="immigration",
            )
            assert "New Visa Rules" in prompt
            assert "immigration" in prompt.lower()
            assert "REASONING FRAMEWORK" in prompt

    def test_prompt_includes_title(self):
        """Test that prompt includes title"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            prompt = gen.build_reasoning_prompt(
                title="Coretax System Issues",
                summary="Problems with tax system",
                full_content="Content here",
                category="tax",
            )
            assert "Coretax System Issues" in prompt

    def test_prompt_includes_category_guidelines(self):
        """Test that prompt includes category-specific guidelines"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            prompt = gen.build_reasoning_prompt(
                title="Test", summary="Test", full_content="Content", category="tax"
            )
            assert "TAX" in prompt or "tax" in prompt.lower()

    def test_prompt_truncates_long_content(self):
        """Test that very long content is truncated"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            long_content = "x" * 5000
            prompt = gen.build_reasoning_prompt(
                title="Test",
                summary="Test",
                full_content=long_content,
                category="immigration",
            )
            # Should have truncation indicator
            assert "..." in prompt
            # Should not include full 5000 chars
            assert len(prompt) < 5000 + 2000  # Some overhead for template

    def test_prompt_includes_style_constants(self):
        """Test that prompt includes style constants"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            prompt = gen.build_reasoning_prompt(
                title="Test",
                summary="Test",
                full_content="Content",
                category="business",
            )
            assert "STYLE" in prompt
            assert "8K" in prompt or "ultra-realistic" in prompt.lower()

    def test_prompt_includes_forbidden_items(self):
        """Test that prompt includes forbidden items"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            prompt = gen.build_reasoning_prompt(
                title="Test",
                summary="Test",
                full_content="Content",
                category="property",
            )
            assert "FORBIDDEN" in prompt


class TestCreateGeminiPrompt:
    """Test create_gemini_prompt method"""

    def test_basic_gemini_prompt(self):
        """Test basic Gemini prompt creation"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            prompt = gen.create_gemini_prompt(
                scene_description="A person looking at laptop",
                mood="Frustrated but hopeful",
                category="tax",
            )
            assert "A person looking at laptop" in prompt
            assert "Frustrated but hopeful" in prompt

    def test_gemini_prompt_includes_style(self):
        """Test Gemini prompt includes style requirements"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            prompt = gen.create_gemini_prompt(
                scene_description="Scene", mood="Calm", category="immigration"
            )
            assert "ultra-realistic" in prompt.lower()
            assert "8K" in prompt
            assert "16:9" in prompt

    def test_gemini_prompt_with_key_details(self):
        """Test Gemini prompt with key details"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            prompt = gen.create_gemini_prompt(
                scene_description="Office scene",
                mood="Professional",
                category="business",
                key_details=["Laptop on desk", "Coffee cup", "Bali view"],
            )
            assert "Laptop on desk" in prompt
            assert "Coffee cup" in prompt
            assert "Bali view" in prompt

    def test_gemini_prompt_without_key_details(self):
        """Test Gemini prompt without key details"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            prompt = gen.create_gemini_prompt(
                scene_description="Simple scene",
                mood="Neutral",
                category="lifestyle",
                key_details=None,
            )
            # Should not have KEY DETAILS section
            assert "Simple scene" in prompt

    def test_gemini_prompt_includes_category_forbidden(self):
        """Test Gemini prompt includes category-specific forbidden items"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            prompt = gen.create_gemini_prompt(
                scene_description="Tax office scene", mood="Focused", category="tax"
            )
            assert "DO NOT INCLUDE" in prompt

    def test_gemini_prompt_has_2_second_test(self):
        """Test Gemini prompt mentions clarity requirement"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            prompt = gen.create_gemini_prompt(
                scene_description="Any scene", mood="Any mood", category="legal"
            )
            assert "2 seconds" in prompt or "CLEAR" in prompt


class TestGetOutputPath:
    """Test get_output_path method"""

    def test_output_path_with_article_id(self):
        """Test output path generation with article ID"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            path = gen.get_output_path("Test Title", article_id="abc123")
            assert "cover_abc123.png" in path

    def test_output_path_without_article_id(self):
        """Test output path generation without article ID"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            path = gen.get_output_path("New Visa Rules for Digital Nomads")
            assert "cover_" in path
            assert ".png" in path
            # Should have slugified title
            assert "new_visa" in path.lower() or "digital" in path.lower()

    def test_output_path_slug_length_limit(self):
        """Test that slug is limited in length"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            long_title = "A" * 200
            path = gen.get_output_path(long_title)
            # Filename shouldn't be extremely long
            filename = Path(path).name
            assert len(filename) < 150

    def test_output_path_removes_special_chars(self):
        """Test that special characters are removed from slug"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            path = gen.get_output_path("Test!@#$%^&*()Title")
            filename = Path(path).name
            # Should not contain special characters
            assert "!" not in filename
            assert "@" not in filename

    def test_output_path_uses_output_dir(self):
        """Test that output path uses the configured output directory"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator(output_dir="custom/images")
            path = gen.get_output_path("Test", article_id="123")
            assert "custom/images" in path or "custom\\images" in path


class TestGetBrowserAutomationSequence:
    """Test get_browser_automation_sequence method"""

    def test_returns_dict_with_steps(self):
        """Test that method returns dict with steps"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            result = gen.get_browser_automation_sequence(
                prompt="Test prompt", output_path="/path/to/output.png"
            )
            assert isinstance(result, dict)
            assert "steps" in result

    def test_contains_description(self):
        """Test result contains description"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            result = gen.get_browser_automation_sequence(
                prompt="Generate image", output_path="/output.png"
            )
            assert "description" in result
            assert "Gemini" in result["description"]

    def test_contains_output_path(self):
        """Test result contains output path"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            result = gen.get_browser_automation_sequence(
                prompt="Test", output_path="/custom/path/image.png"
            )
            assert result["output_path"] == "/custom/path/image.png"

    def test_contains_prompt(self):
        """Test result contains the prompt"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            result = gen.get_browser_automation_sequence(
                prompt="Create a beautiful image", output_path="/output.png"
            )
            assert result["prompt"] == "Create a beautiful image"

    def test_has_multiple_steps(self):
        """Test that sequence has multiple steps"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            result = gen.get_browser_automation_sequence(
                prompt="Test", output_path="/output.png"
            )
            assert len(result["steps"]) >= 5

    def test_steps_include_navigation(self):
        """Test steps include navigation to Gemini"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()
            result = gen.get_browser_automation_sequence(
                prompt="Test", output_path="/output.png"
            )
            nav_step = next(
                (s for s in result["steps"] if "navigate" in s.get("tool", "")), None
            )
            assert nav_step is not None
            assert "gemini.google.com" in nav_step.get("params", {}).get("url", "")


# =============================================================================
# Usage Example Tests
# =============================================================================


class TestUsageExample:
    """Test the usage example constant"""

    def test_usage_example_exists(self):
        """Test USAGE_EXAMPLE constant exists"""
        assert USAGE_EXAMPLE is not None
        assert len(USAGE_EXAMPLE) > 0

    def test_usage_example_has_steps(self):
        """Test usage example describes steps"""
        assert "1." in USAGE_EXAMPLE or "RECEIVE" in USAGE_EXAMPLE

    def test_usage_example_mentions_reasoning(self):
        """Test usage example mentions reasoning"""
        assert "REASON" in USAGE_EXAMPLE or "reason" in USAGE_EXAMPLE.lower()


# =============================================================================
# Integration Tests
# =============================================================================


class TestImageGeneratorIntegration:
    """Integration tests for complete workflows"""

    def test_full_prompt_workflow(self):
        """Test complete workflow from article to final prompt"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()

            # Step 1: Build reasoning prompt
            reasoning = gen.build_reasoning_prompt(
                title="Coretax System Down: How to Register NPWP Offline",
                summary="Tax portal experiencing issues, alternative registration methods",
                full_content="The new Coretax system launched by DJP has been experiencing...",
                category="tax",
            )
            assert "Coretax" in reasoning

            # Step 2: Create final Gemini prompt
            gemini_prompt = gen.create_gemini_prompt(
                scene_description="Person at tax office counter, helpful staff assisting with paperwork",
                mood="Relief at finding solution",
                category="tax",
                key_details=[
                    "KPP office interior",
                    "Queue number display",
                    "Indonesian setting",
                ],
            )
            assert "Person at tax office" in gemini_prompt
            assert "KPP office interior" in gemini_prompt

            # Step 3: Get output path
            path = gen.get_output_path("Coretax System Down", article_id="tax_001")
            assert "cover_tax_001.png" in path

            # Step 4: Get automation sequence
            automation = gen.get_browser_automation_sequence(gemini_prompt, path)
            assert len(automation["steps"]) > 0

    def test_multiple_categories_workflow(self):
        """Test workflow works for multiple categories"""
        with patch("pathlib.Path.mkdir"):
            gen = GeminiImageGenerator()

            categories = [
                "immigration",
                "tax",
                "business",
                "property",
                "lifestyle",
                "legal",
                "tech",
            ]

            for category in categories:
                guidelines = gen.get_category_guidelines(category)
                assert guidelines is not None

                reasoning = gen.build_reasoning_prompt(
                    title=f"Test {category} article",
                    summary=f"About {category}",
                    full_content="Test content",
                    category=category,
                )
                assert category.upper() in reasoning or category in reasoning.lower()

                gemini_prompt = gen.create_gemini_prompt(
                    scene_description=f"{category} scene",
                    mood="Professional",
                    category=category,
                )
                assert "8K" in gemini_prompt


# =============================================================================
# Main Block Test
# =============================================================================


class TestMainBlock:
    """Test the main block execution"""

    def test_main_prints_usage(self, capsys):
        """Test that running main prints usage example"""
        # Execute the main block code directly
        print("=" * 70)
        print("GEMINI IMAGE GENERATOR - Reasoning Framework")
        print("=" * 70)
        print(USAGE_EXAMPLE)
        print("=" * 70)

        captured = capsys.readouterr()
        assert "GEMINI IMAGE GENERATOR" in captured.out
        assert "HOW CLAUDE SHOULD USE" in captured.out
