"""
Mata Garuda — Reflection Engine.

After every run (success OR failure), generates a structured JSON reflection
via claude --print. Reflections are stored in the unified SQLite KB.

Design: JSON output (not regex) per Gemini review — robust to formatting changes.
Pattern: Reflexion (Shinn 2023)
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from mata_garuda.runtime.knowledge import KnowledgeBase

logger = logging.getLogger("mata_garuda.runtime")

MAX_REFLECTION_CHARS = 2000


def build_reflection_prompt(
    agent_name: str,
    query: str,
    outcome_success: bool,
    messages_summary: str,
    genome_snippet: str,
) -> str:
    """Build the prompt for claude --print to generate a JSON reflection."""
    status = "SUCCESS" if outcome_success else "FAILURE"
    focus = (
        "What worked well? What pattern should be repeated? What reusable skill emerged?"
        if outcome_success
        else "What was the root cause? What should the agent do differently? What constraint was violated?"
    )
    return f"""You are the reflection engine for agent "{agent_name}".

The agent just completed a run with outcome: {status}

Query: {query}
Run summary: {messages_summary}
GENOME constraints: {genome_snippet}

Produce a structured reflection as a JSON object inside a ```json fence.
Focus: {focus}

```json
{{
    "what_worked": "one sentence — what went well",
    "what_didnt": "one sentence — what failed or was inefficient",
    "skill": "one reusable procedure extracted from this run, or null",
    "insight": "one non-obvious insight useful for future runs, or null"
}}
```

Output ONLY the JSON block. No other text."""


def parse_reflection(raw: str) -> dict:
    """Parse a JSON reflection from claude output. Fallback to raw text."""
    fence_match = re.search(r"```json\s*\n?(.*?)\n?\s*```", raw, re.DOTALL)
    json_str = fence_match.group(1) if fence_match else raw.strip()

    try:
        parsed = json.loads(json_str)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    return {"raw": raw}


def store_reflection_in_kb(
    kb: KnowledgeBase,
    agent_name: str,
    parsed: dict,
) -> list[int]:
    """Store parsed reflection fields in the KB. Returns list of row IDs."""
    ids = []
    source = f"reflection_{agent_name}"

    if "insight" in parsed and parsed["insight"]:
        row_id = kb.store(agent_name, "insight", parsed["insight"], source, 0.7)
        ids.append(row_id)

    if "skill" in parsed and parsed["skill"]:
        row_id = kb.store(agent_name, "skill", parsed["skill"], source, 0.8)
        ids.append(row_id)

    full_text = json.dumps(parsed, ensure_ascii=False) if "raw" not in parsed else parsed["raw"]
    row_id = kb.store(agent_name, "reflection", full_text, source, 0.5)
    ids.append(row_id)

    return ids


def get_recent_reflections(
    kb: KnowledgeBase,
    agent_name: str,
    n: int = 5,
) -> list[str]:
    """Get the N most recent reflections for an agent from the KB."""
    cursor = kb._conn.execute(
        "SELECT content FROM knowledge WHERE agent = ? AND type = 'reflection' "
        "ORDER BY created_at DESC LIMIT ?",
        (agent_name, n),
    )
    return [row["content"] for row in cursor.fetchall()]


def build_reflection_context(
    kb: KnowledgeBase,
    agent_name: str,
    n: int = 5,
) -> str:
    """Build a string of recent reflections to inject into agent prompt.
    Respects MAX_REFLECTION_CHARS token budget."""
    reflections = get_recent_reflections(kb, agent_name, n)
    if not reflections:
        return ""

    lines = []
    total_chars = 0
    for i, r in enumerate(reflections):
        entry = f"[Reflection {i + 1}] {r}"
        if total_chars + len(entry) > MAX_REFLECTION_CHARS:
            break
        lines.append(entry)
        total_chars += len(entry)

    return "\n\nPREVIOUS REFLECTIONS (learn from these):\n" + "\n".join(lines)
