# Deep Research: Autonomous Agent Architecture — Production Patterns 2026

You are researching for Nuzantara/Bali Zero. We're designing a multi-agent system with a military hierarchy (Commander → 6 Generals → Specialists).

## Current Architecture

- LangGraph-based agent orchestration
- 8 workflow chains (daily_ops, client_onboarding, compliance, intel_pipeline, etc.)
- MCP server with 109 tools
- Episodic memory in Qdrant (collective_memories collection)
- OODA loop pattern (Observe → Orient → Decide → Act)

## Research Questions

1. **LangGraph vs CrewAI vs AutoGen vs Agency Swarm 2026**: Production-grade comparison for hierarchical multi-agent systems. Focus on: state management, error recovery, human-in-the-loop, observability. Which framework handles 50+ tools best?

2. **Agent Memory Architecture**: Best patterns for shared memory across agent hierarchies. Specifically: episodic (what happened), semantic (what I know), procedural (how to do things). How to implement memory consolidation (short-term → long-term) without Pinecone/Weaviate (we use Qdrant)?

3. **Self-healing patterns**: How do production systems implement automatic error recovery in agent workflows? Circuit breakers, retry with backoff, graceful degradation, fallback chains. Real-world examples from 2025-2026.

4. **Agent observability**: LangSmith vs Langfuse vs Phoenix vs custom. What's the minimum viable observability for a 6-agent system? Trace correlation, cost tracking, quality scoring.

5. **Deterministic vs Autonomous**: Where to draw the line between scripted workflows (cron) and truly autonomous agents? Decision framework for "this should be a cron job" vs "this should be an agent".

## Output Format

For each question: state of the art, framework comparison table, and concrete recommendation for a 2-person team with $40/mo budget.

Save your research to `docs/research/2026-03-15-autonomous-agents-patterns.md`
