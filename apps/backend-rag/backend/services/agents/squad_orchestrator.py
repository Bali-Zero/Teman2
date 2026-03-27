"""
Squad Orchestrator - Agent Management Arsenal

This module implements the Manager Agent capabilities.
The Orchestrator does not do the domain work; it delegates, monitors, and synthesizes.
"""

import logging
from typing import Any, TypeVar

from pydantic import BaseModel

# Lazy imports for LLMs
try:
    from langchain_anthropic import ChatAnthropic
except ImportError:
    ChatAnthropic = None  # type: ignore

from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class SquadOrchestrator:
    """
    The Orchestrator acts as the Engineering Manager for the Agent Squad.
    It holds the 'Arsenal' of multi-agent commands.
    """

    def __init__(self, llm: ChatAnthropic | None = None) -> None:
        """
        Initialize the Orchestrator.
        Preferably uses Codex-sonnet-4-6 (Sonnet 3.5 update) for orchestration reasoning.
        """
        import os

        self.llm = llm
        if not self.llm and ChatAnthropic is not None and os.getenv("ANTHROPIC_API_KEY"):
            # Recommended model for Nuzantara per AGENTS.md
            self.llm = ChatAnthropic(
                model="claude-3-5-sonnet-latest",  # Placeholder for the 4.6 adaptive equivalent
                temperature=0.1,
                max_tokens=8192,
            )

    async def delegate_task(
        self, agent_role: str, task_payload: dict[str, Any], strict_schema: type[T]
    ) -> T:
        """
        COMMAND 1: Task Delegation

        Spawns a specialized agent thread, executes the task, and guarantees
        the output matches the strict_schema (Pydantic).

        Args:
            agent_role: e.g., "KBLI Compliance Expert", "Corporate Tax Auditor"
            task_payload: The context/data the agent needs to do its job.
            strict_schema: Pydantic model defining the exact JSON shape required.

        Returns:
            Validated Pydantic object from the LLM output.
        """
        logger.info(f"👔 [Orchestrator] Delegating task to specialized [{agent_role}]")

        if not self.llm:
            raise RuntimeError("Orchestrator LLM not initialized.")

        # Construct the context payload string
        payload_str = "\n".join([f"- **{k}**: {v}" for k, v in task_payload.items()])

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are an expert {agent_role} for Nuzantara, a premium Indonesian business consulting firm. "
                    "Execute the following task strictly. Do not hallucinate. "
                    "If information is missing, use default abstention patterns.",
                ),
                (
                    "human",
                    "Task Context & Data:\n{payload_str}\n\n"
                    "Provide the requested analysis according to the required schema.",
                ),
            ]
        )

        # Core mechanic: Pydantic enforced output (no raw text parsing)
        structured_llm = self.llm.with_structured_output(strict_schema)
        chain = prompt | structured_llm

        try:
            result = await chain.ainvoke({"agent_role": agent_role, "payload_str": payload_str})
            logger.info(f"✅ [Orchestrator] [{agent_role}] completed delegation successfully.")
            return result
        except Exception as e:
            logger.error(f"❌ [Orchestrator] [{agent_role}] failed: {e}", exc_info=True)
            raise RuntimeError(f"Delegation to {agent_role} failed: {e}") from e
