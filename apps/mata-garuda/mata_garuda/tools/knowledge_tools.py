"""
Mata Garuda — Knowledge Base tools for agents.

Agents can search, store, and retrieve skills from the unified SQLite KB.
"""
from __future__ import annotations

from mata_garuda.registry import register_tool
from mata_garuda.runtime.knowledge import KnowledgeBase


@register_tool(name="kb_search")
def kb_search(
    query: str,
    limit: int = 5,
    context_variables: dict | None = None,
) -> str:
    """Search the knowledge base for relevant facts, insights, or skills.

    Args:
        query: Search text (uses FTS5 full-text search)
        limit: Max results to return
    """
    kb = context_variables.get("kb") if context_variables else None
    if kb is None:
        return "[ERROR] Knowledge base not available in context"

    results = kb.search(query, limit=limit)
    if not results:
        return f"No results for '{query}'"

    lines = [f"Found {len(results)} results:"]
    for r in results:
        lines.append(
            f"  [{r['type']}] (confidence: {r['confidence']:.1f}) {r['content'][:120]}"
        )
        kb.touch(r["id"])
    return "\n".join(lines)


@register_tool(name="kb_store")
def kb_store(
    entry_type: str,
    content: str,
    source: str = "agent_runtime",
    confidence: float = 0.7,
    context_variables: dict | None = None,
) -> str:
    """Store a new fact, insight, or skill in the knowledge base.

    Args:
        entry_type: One of 'fact', 'insight', 'skill', 'pattern'
        content: The knowledge content to store
        source: Where this knowledge came from
        confidence: Confidence level 0.0-1.0
    """
    kb = context_variables.get("kb") if context_variables else None
    if kb is None:
        return "[ERROR] Knowledge base not available in context"

    agent_name = context_variables.get("agent_name", "unknown")
    row_id = kb.store(agent_name, entry_type, content, source, confidence)
    return f"[SUCCESS] Stored {entry_type} (id: {row_id})"


@register_tool(name="kb_get_skills")
def kb_get_skills(
    limit: int = 10,
    context_variables: dict | None = None,
) -> str:
    """Get all learned skills from the knowledge base.

    Args:
        limit: Max skills to return
    """
    kb = context_variables.get("kb") if context_variables else None
    if kb is None:
        return "[ERROR] Knowledge base not available in context"

    skills = kb.get_by_type("skill", limit=limit)
    if not skills:
        return "No skills learned yet."

    lines = [f"{len(skills)} skills available:"]
    for s in skills:
        lines.append(f"  • (conf: {s['confidence']:.1f}) {s['content'][:120]}")
    return "\n".join(lines)
