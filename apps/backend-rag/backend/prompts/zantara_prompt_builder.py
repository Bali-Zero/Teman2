import logging
import os
from dataclasses import dataclass

import yaml
from llm.adapters import ModelAdapter

logger = logging.getLogger(__name__)


@dataclass
class PromptContext:
    query: str
    language: str
    mode: str
    emotional_state: str
    user_name: str | None = None
    user_role: str | None = None
    conversation_history: list | None = None
    rag_context: str | None = None


class ZantaraPromptBuilder:
    """
    Builds Zantara prompts that are:
    1. True to Zantara's identity (from ZIS)
    2. Appropriate for the communication mode
    3. Optimized for the specific LLM
    """

    def __init__(self, model_adapter: ModelAdapter):
        self.adapter = model_adapter
        self.identity_spec = self._load_identity()
        self.modes = self._load_modes()

    def _load_identity(self) -> str:
        """Load the consolidated system prompt from zantara_system_prompt.md"""
        try:
            # Single source of truth: consolidated system prompt
            path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "zantara_system_prompt.md")
            )
            if os.path.exists(path):
                with open(path) as f:
                    return f.read()

            logger.warning("zantara_system_prompt.md not found, using embedded fallback")
            return "You are Zantara, a helpful consultant."
        except Exception as e:
            logger.warning("Could not load Zantara prompt: %s", e)
            return "You are Zantara, a helpful consultant."

    def _load_modes(self) -> dict:
        try:
            path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "../config/communication_modes.yaml")
            )
            with open(path) as f:
                return yaml.safe_load(f)["modes"]
        except Exception as e:
            logger.warning("Could not load communication_modes.yaml: %s", e)
            return {}

    def build(self, context: PromptContext) -> str:
        mode_config = self.modes.get(context.mode, self.modes.get("small_talk", {}))

        # 1. Core identity (always present)
        prompt = self._build_identity_section()

        # 2. Language rules
        prompt += self._build_language_section(context.language)

        # 3. Mode-specific instructions
        prompt += self._build_mode_section(mode_config)

        # 4. Emotional adaptation
        prompt += self._build_emotional_section(context.emotional_state)

        # 5. Anti-patterns (model-specific)
        prompt += self._build_anti_patterns()

        # 6. RAG context if available
        if context.rag_context:
            prompt += self._build_context_section(context.rag_context)

        # 7. Apply model-specific adaptations
        prompt = self.adapter.adapt_system_prompt(prompt)

        return prompt

    def _build_identity_section(self) -> str:
        # Extract key sections from ZIS markdown or use a summarized version
        # For efficiency, we'll use a summarized version derived from ZIS
        return """
## IDENTITY
You are Zantara, a senior consultant at Bali Zero based in SCBD, Jakarta.
You are a colleague, part of the team - not an external AI assistant.
You know Indonesian bureaucracy from direct experience.

## VOICE
- Direct: Answer the question first, elaborate after
- Concrete: Use real examples, numbers, scenarios
- Warm: Human, collegial tone
- Competent: Confident in your knowledge
- Concise: Say what's needed, no more
"""

    def _build_language_section(self, language: str) -> str:
        rules = {
            "it": """
## LANGUAGE: ITALIAN
- Respond entirely in Italian
- Professional but warm tone
- No unnecessary anglicisms
- Technical Indonesian terms (KITAS, NIB) stay in original""",
            "en": """
## LANGUAGE: ENGLISH
- Clear, confident English
- British-neutral spelling
- Professional but friendly""",
            "id": """
## LANGUAGE: INDONESIAN (JAKSEL STYLE)
- Natural English-Indonesian code-switching
- Casual but professional
- "Gue/lo" acceptable, "saya/anda" for formal context""",
        }
        return rules.get(language, rules["en"])

    def _build_mode_section(self, config: dict) -> str:
        structure_templates = {
            "answer_first": "Answer directly in first sentence, then elaborate if needed.",
            "hook_context_explain_example_summary": """
Structure your response:
1. Hook: Opening that engages
2. Context: Why this matters (1 sentence)
3. Explanation: Core answer
4. Example: Concrete scenario
5. Summary: TL;DR + next step""",
            "numbered_steps": """
Format as numbered steps:
1. [Action] - [Timeline] - [Tip]
2. [Action] - [Timeline] - [Tip]
...""",
            "risk_consequence_alternative": """
Structure:
1. State the risk clearly but calmly
2. Explain concrete consequences
3. Provide the compliant alternative
4. Reassurance + action step""",
        }

        structure_name = config.get("structure") or "default"
        section = f"\n## RESPONSE MODE: {structure_name.upper()}\n"
        section += f"Max length: {config.get('max_sentences', 5)} sentences\n"

        if config.get("structure") and config["structure"] in structure_templates:
            section += structure_templates[config["structure"]]

        if config.get("include_examples"):
            section += "\nInclude a concrete example.\n"

        if config.get("include_hook"):
            section += "\nEnd with a natural question or next step.\n"

        return section

    def _build_emotional_section(self, state: str) -> str:
        adaptations = {
            "stressed": "User seems stressed. Be calm, solution-focused. No extra questions.",
            "confused": "User seems confused. Simplify. One concept at a time.",
            "frustrated": "User is frustrated. Brief empathy, then straight to solution.",
            "excited": "User is excited. Match energy, be supportive.",
            "neutral": "Normal conversation. Warm and helpful.",
        }
        return f"\n## EMOTIONAL CONTEXT\n{adaptations.get(state, adaptations['neutral'])}\n"

    def _build_anti_patterns(self) -> str:
        patterns = self.adapter.get_anti_patterns()
        patterns_str = ", ".join(f'"{p}"' for p in patterns)
        return f"""
## FORBIDDEN PATTERNS
NEVER start responses with: {patterns_str}
Start directly with useful content.
"""

    def _build_context_section(self, rag_context: str) -> str:
        return f"""
## KNOWLEDGE CONTEXT
Use this information to answer:
{rag_context}

Cite sources naturally when relevant.
"""
