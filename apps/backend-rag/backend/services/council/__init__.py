"""Consiglio — multi-LLM deliberation engine (Pilastro 4 Confronto).

War Room 2.0 tone selection + cognitive layer Oracle use this module.
Reference: docs/war-room-2.0-design.md §3, §17.4.
"""

from backend.services.council.cli_runners import (
    ClaudeCLIRunner,
    CLIRunner,
    CLIRunnerError,
    GeminiCLIRunner,
    KimiCLIRunner,
    RunnerResult,
)
from backend.services.council.prompts import (
    REGISTER_PROMPTS,
    RegisterDefinition,
)
from backend.services.council.tone_council import (
    CouncilProposal,
    JudgeDecision,
    ToneCouncil,
    ToneCouncilResult,
)

__all__ = [
    "REGISTER_PROMPTS",
    "CLIRunner",
    "CLIRunnerError",
    "ClaudeCLIRunner",
    "CouncilProposal",
    "GeminiCLIRunner",
    "JudgeDecision",
    "KimiCLIRunner",
    "RegisterDefinition",
    "RunnerResult",
    "ToneCouncil",
    "ToneCouncilResult",
]
