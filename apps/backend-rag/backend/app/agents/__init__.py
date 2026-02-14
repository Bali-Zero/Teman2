"""
Agentic Layer for Nuzantara Prime

This package contains the LangGraph-based agentic orchestration layer
that sits on top of the existing FastAPI deterministic logic.

Architecture:
- state.py: Agent state definitions (TypedDict)
- graph.py: LangGraph workflow definitions
- nodes.py: Individual node implementations
- tools.py: Tool definitions for agents to use

Design Principles:
1. Separation of Concerns: Agents orchestrate, services execute
2. Idempotency: Nodes should be retryable without side effects
3. Observability: All state transitions are logged
4. Backward Compatibility: Existing routers remain unchanged
"""

__version__ = "1.0.0"
