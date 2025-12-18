from llm.adapters.base import ModelAdapter, ModelCapabilities


class GeminiAdapter(ModelAdapter):
    @property
    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            max_context_tokens=1_000_000,  # Gemini 1.5/2.0
            max_output_tokens=8192,
            supports_system_prompt=True,
            supports_few_shot=True,
            supports_json_mode=True,
            supports_tool_use=True,
            optimal_temperature=0.7,
            reasoning_strength="high",
            instruction_following="strict",
            verbosity_tendency="balanced",
        )

    def adapt_system_prompt(self, base_prompt: str) -> str:
        # Gemini respects instructions well, minimal adaptation needed
        return base_prompt

    def adapt_few_shot(self, examples: list[dict]) -> list[dict]:
        # Gemini expects standard message format for few-shot
        return examples

    def get_brevity_instruction(self) -> str:
        return "Be concise. Answer the question directly first."

    def get_anti_patterns(self) -> list[str]:
        return [
            "I'd be happy to help",
            "Great question!",
            "Let me explain",
            "Here is the information",
            "As an AI",
        ]
