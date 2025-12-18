"""
Prompt Manager - Handles system prompt loading and building

Separated from ZantaraAIClient to follow Single Responsibility Principle.
"""

import logging
from pathlib import Path

from services.emotional_attunement import ToneStyle

logger = logging.getLogger(__name__)

# Path to the SINGLE consolidated system prompt file
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
SYSTEM_PROMPT_FILE = PROMPTS_DIR / "zantara_system_prompt.md"  # Single source of truth
FALLBACK_PROMPT_FILE = PROMPTS_DIR / "zantara_system_prompt.md"  # Same file (no fallback needed)

# Tone style prompts
TONE_PROMPTS = {
    ToneStyle.PROFESSIONAL: "Maintain a professional, balanced tone. Be clear and concise.",
    ToneStyle.WARM: "Use a warm, friendly tone. Show empathy and encouragement.",
    ToneStyle.TECHNICAL: "Provide detailed technical explanations. Use precise terminology.",
    ToneStyle.SIMPLE: "Explain in simple terms. Break down complex concepts step by step.",
    ToneStyle.ENCOURAGING: "Be reassuring and supportive. Acknowledge the challenge and offer clear next steps.",
    ToneStyle.DIRECT: "Be direct and action-oriented. Focus on solutions, not explanations.",
}


class PromptManager:
    """
    Manages system prompt loading and building with context injection.

    Responsibilities:
    - Load prompt from file or use embedded fallback
    - Build prompt with memory and identity context
    - Handle prompt file errors gracefully
    """

    def __init__(self):
        """Initialize PromptManager and load base system prompt."""
        self._base_system_prompt = self._load_system_prompt_from_file()

    def _load_system_prompt_from_file(self) -> str:
        """
        Load the rich system prompt from markdown file.

        Falls back to embedded prompt if file not found.

        Returns:
            System prompt string loaded from file or embedded fallback.
        """
        try:
            if SYSTEM_PROMPT_FILE.exists():
                prompt = SYSTEM_PROMPT_FILE.read_text(encoding="utf-8")
                logger.info(f"✅ Loaded system prompt from {SYSTEM_PROMPT_FILE.name}")
                return prompt
            elif FALLBACK_PROMPT_FILE.exists():
                prompt = FALLBACK_PROMPT_FILE.read_text(encoding="utf-8")
                logger.info(f"⚠️ Using fallback prompt from {FALLBACK_PROMPT_FILE.name}")
                return prompt
        except Exception as e:
            logger.warning(f"⚠️ Failed to load prompt file: {e}")

        # Ultimate fallback - embedded prompt
        logger.warning("⚠️ Using embedded fallback system prompt")
        return self._get_embedded_fallback_prompt()

    def _get_embedded_fallback_prompt(self) -> str:
        """
        Get embedded fallback prompt if files are not available.

        Returns:
            Embedded system prompt string.
        """
        return """# ZANTARA - Intelligent AI Assistant for Bali Zero

## Core Identity

You are ZANTARA, the intelligent assistant for Bali Zero.
Think of yourself as a knowledgeable colleague who genuinely
cares about helping people navigate Indonesian business,
visas, and life in Bali.

Your expertise spans visa procedures, company formation, tax
compliance, legal requirements, and practical aspects of doing
 business in Indonesia. You have deep knowledge of business
classification codes, immigration regulations, and the
cultural nuances that make Indonesia unique.

## Communication Philosophy

**Be naturally professional.** Your tone should be warm and
approachable without being overly casual or robotic. Imagine
explaining complex topics to a smart friend who values your
expertise.

**Match the user's language and energy:**
- English: Professional but friendly, clear and confident
- Italian: Warm and personable, maintain substance
- Indonesian: Respectful and culturally aware

## Knowledge Domains

You draw from comprehensive knowledge bases covering:
- Immigration & visas (all visa types and permits)
- Business structures (company types)
- Business classification system (KBLI codes)
- Tax compliance and financial planning
- Legal requirements and regulatory frameworks
- Real estate and property investment
- Indonesian cultural intelligence and business practices

## Response Principles

**Clarity over cleverness.** Say what needs to be said without
 unnecessary embellishment.

**Context-aware assistance.**
- When users need help with services: "Need help with this?
Reach out on WhatsApp +62 859 0436 9574"
- For team members or casual conversations, skip the sales
pitch

**Honest about limitations.**
- If you need to verify: "Let me confirm the latest
requirements with our team"
- For specific cases: "This would benefit from consultation
with our specialist"
- Never fabricate details, especially regarding timelines or
costs
- If you don't have specific information: "I don't have
detailed information on this specific topic in my current
knowledge base. I can provide general guidance, or you can
contact our team for accurate details."

## Indonesian Cultural Intelligence

You understand Indonesian business culture deeply:
- The importance of building relationships
- Patience with bureaucratic processes
- Respect for hierarchy and proper titles
- The concept of Tri Hita Karana in Bali
- Face-saving in communication
- Flexibility and adaptability in timelines

## What Makes You Different

You're not just a chatbot regurgitating information. You
understand:
- The real challenges foreigners face in Indonesian
bureaucracy
- Why timing matters in visa applications
- The strategic implications of choosing different company
structures
- How cultural context affects business success

Bring this depth to every interaction while keeping your
language clear and accessible.
"""

    def build_system_prompt(
        self,
        memory_context: str | None = None,
        identity_context: str | None = None,
        use_rich_prompt: bool = True,
        style: str | ToneStyle | None = None,
    ) -> str:
        """
        Build ZANTARA system prompt with context injection.

        Args:
            memory_context: Optional memory/RAG context to inject. Will be wrapped
                in <context> tags if provided.
            identity_context: Optional user identity context. Will be wrapped in
                <user_identity> tags if provided.
            use_rich_prompt: If True, loads prompt from file. If False, uses
                embedded fallback prompt.
            style: Optional tone style to apply (ToneStyle enum or string).

        Returns:
            Complete system prompt string with all context sections properly
            structured with XML tags.
        """
        # Start with base prompt (from file or embedded)
        if use_rich_prompt:
            base_prompt = self._base_system_prompt
        else:
            base_prompt = self._get_embedded_fallback_prompt()

        # Build structured context sections
        context_sections = []

        # Tone/Style Context
        if style:
            tone_instruction = None
            if isinstance(style, ToneStyle):
                tone_instruction = TONE_PROMPTS.get(style)
            elif isinstance(style, str):
                # Try to map string to ToneStyle
                try:
                    style_enum = ToneStyle(style.lower())
                    tone_instruction = TONE_PROMPTS.get(style_enum)
                except ValueError:
                    # If string doesn't match enum, use it as is if it's not empty
                    if style.strip():
                        tone_instruction = f"Style/Tone: {style}"

            if tone_instruction:
                context_sections.append(
                    f"""
<style_instruction>
{tone_instruction}
</style_instruction>
"""
                )

        # Memory/RAG context
        if memory_context:
            context_sections.append(
                """

CONTEXT USAGE INSTRUCTIONS:
1. Use the information in <context> tags to answer questions accurately
2. When citing facts, mention the source document if available
3. If the context doesn't contain specific information, acknowledge this honestly
4. Do NOT make up information - only use what's in the context or your general knowledge
5. For pricing, legal requirements, and specific procedures: ONLY use context data
"""
            )

        # Combine everything
        if context_sections:
            full_prompt = base_prompt + "\n\n---\n" + "\n".join(context_sections)
        else:
            full_prompt = base_prompt

        return full_prompt

    def get_system_prompt(self, prompt_type: str | None = None) -> str:
        """
        Get system prompt for a specific prompt type.

        Args:
            prompt_type: Optional prompt type (e.g., "tax_specialist", "legal_specialist", "visa_specialist").
                        If None or not recognized, returns the base system prompt.

        Returns:
            System prompt string for the requested type, or base prompt if type not recognized.
        """
        # For now, return the base prompt for all types
        # The base prompt already covers all domains (tax, legal, visa, etc.)
        # Future enhancement: Add specialized prompts per type if needed
        base_prompt = self._base_system_prompt

        # Add domain-specific context if requested
        if prompt_type:
            prompt_type_lower = prompt_type.lower()

            # Add domain-specific instructions to the base prompt
            if "tax" in prompt_type_lower or "pajak" in prompt_type_lower:
                domain_context = "\n\n## Tax Specialist Focus\n\nYou are particularly knowledgeable about Indonesian tax regulations, including PPh (Income Tax), PPn (VAT), tax treaties, and compliance requirements. Provide accurate tax calculations and cite relevant tax regulations."
            elif "legal" in prompt_type_lower or "law" in prompt_type_lower:
                domain_context = "\n\n## Legal Specialist Focus\n\nYou are particularly knowledgeable about Indonesian legal frameworks, corporate law, business regulations, and compliance requirements. Provide accurate legal guidance and cite relevant laws and regulations."
            elif "visa" in prompt_type_lower or "immigration" in prompt_type_lower:
                domain_context = "\n\n## Visa Specialist Focus\n\nYou are particularly knowledgeable about Indonesian immigration regulations, visa types (KITAS, KITAP, etc.), and visa application procedures. Provide accurate visa information and cite relevant immigration regulations."
            else:
                domain_context = ""

            if domain_context:
                return base_prompt + domain_context

        return base_prompt
