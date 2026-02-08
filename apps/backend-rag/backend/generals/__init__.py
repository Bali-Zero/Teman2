"""
The Generals Multi-Agent System

A distributed task execution system where specialized "Generals" handle
different types of tasks:
- Coding General: Executes code-related tasks
- Intelligence General: Performs research using Gemini 3 Pro CLI + RAG

Tasks are coordinated through PostgreSQL tables:
- generals_tasks: Task queue
- generals_memory: Shared memory between generals
- generals_activity: Activity log

Every General loads AI_ONBOARDING.md as its constitution.
All executions respect the Golden Rules defined there.
"""

from backend.generals.coding_general import CodingGeneral
from backend.generals.intelligence_general import IntelligenceGeneral
from backend.generals.onboarding_context import CRITICAL_KNOWLEDGE, GOLDEN_RULES
from backend.generals.task_coordinator import TaskCoordinator

__all__ = [
    "CodingGeneral",
    "IntelligenceGeneral",
    "TaskCoordinator",
    "GOLDEN_RULES",
    "CRITICAL_KNOWLEDGE",
]
