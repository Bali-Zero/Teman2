from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ModelCapabilities:
    max_context_tokens: int
    max_output_tokens: int
    supports_system_prompt: bool
    supports_few_shot: bool
    supports_json_mode: bool
    supports_tool_use: bool
    optimal_temperature: float
    reasoning_strength: str  # "high", "medium", "low"
    instruction_following: str  # "strict", "loose"
    verbosity_tendency: str  # "verbose", "concise", "balanced"


class ModelAdapter(ABC):
    @property
    @abstractmethod
    def capabilities(self) -> ModelCapabilities:
        """Return model capabilities for prompt optimization."""
        pass

    @abstractmethod
    def adapt_system_prompt(self, base_prompt: str) -> str:
        """Adapt base prompt to model-specific format."""
        pass

    @abstractmethod
    def adapt_few_shot(self, examples: list[dict]) -> list[dict]:
        """Format few-shot examples for this model."""
        pass

    @abstractmethod
    def get_brevity_instruction(self) -> str:
        """Return model-specific instruction for conciseness."""
        pass

    @abstractmethod
    def get_anti_patterns(self) -> list[str]:
        """Return patterns this model tends to produce that we want to avoid."""
        pass

    def get_generation_params(self) -> dict:
        """Return default generation parameters."""
        return {
            "temperature": self.capabilities.optimal_temperature,
            "max_output_tokens": self.capabilities.max_output_tokens,
        }
