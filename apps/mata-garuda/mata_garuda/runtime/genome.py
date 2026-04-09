"""
Mata Garuda — GENOME Manager.

Read, propose mutations, and apply changes to agent GENOME.md files.
Mutations always require human review (Zero) unless --auto-mutate is set.

GENOME.md is the agent's identity + constraints document.
Mutations are proposed based on feedback.md failure patterns.
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("mata_garuda.runtime")

AGENTS_DIR = Path(__file__).parent.parent / "agents"


def get_genome_path(agent_name: str) -> Path:
    """Get the GENOME.md path for an agent."""
    safe_name = agent_name.lower().replace(" ", "_").replace("-", "_")
    return AGENTS_DIR / f"{safe_name}_GENOME.md"


def read_genome(agent_name: str) -> str:
    """Read an agent's GENOME.md content.

    Returns:
        Content string, or empty string if not found
    """
    path = get_genome_path(agent_name)
    if path.exists():
        return path.read_text()
    return ""


def get_feedback_path(agent_name: str) -> Path:
    """Get the feedback.md path for an agent."""
    feedback_dir = Path(__file__).parent.parent.parent / "feedback"
    feedback_dir.mkdir(exist_ok=True)
    safe_name = agent_name.lower().replace(" ", "_").replace("-", "_")
    return feedback_dir / f"{safe_name}.md"


def read_feedback(agent_name: str) -> str:
    """Read an agent's feedback log.

    Returns:
        Content string, or empty string if not found
    """
    path = get_feedback_path(agent_name)
    if path.exists():
        return path.read_text()
    return ""


def log_feedback(
    agent_name: str,
    attempt: int,
    failure_reason: str,
    take_away: str,
) -> Path:
    """Append a failure entry to feedback/{agent_name}.md.

    Returns:
        Path to the feedback file
    """
    path = get_feedback_path(agent_name)
    ts = datetime.now().isoformat(timespec="seconds")

    entry = (
        f"\n## {ts} (attempt {attempt})\n"
        f"**Reason:** {failure_reason}\n"
        f"**Insight:** {take_away}\n"
    )

    with open(path, "a") as f:
        f.write(entry)

    logger.info(f"[genome] Logged feedback for {agent_name} (attempt {attempt})")
    return path


def propose_mutation(agent_name: str, feedback_text: str) -> str:
    """Generate a proposed GENOME.md mutation based on feedback.

    This creates a human-readable diff showing what would be added.
    Does NOT apply the mutation — that requires review.

    Returns:
        Proposed mutation text with context
    """
    genome = read_genome(agent_name)
    ts = datetime.now().strftime("%Y-%m-%d")

    proposal = (
        f"# Proposed GENOME Mutation for {agent_name}\n"
        f"Date: {ts}\n\n"
        f"## Current GENOME\n```\n{genome}\n```\n\n"
        f"## Feedback triggering mutation\n{feedback_text}\n\n"
        f"## Proposed addition to Constraints section\n"
        f"(Review required — add these lines to GENOME.md if approved)\n"
    )

    return proposal


def apply_mutation(
    agent_name: str, new_constraint: str, reason: str
) -> bool:
    """Apply a mutation to an agent's GENOME.md.

    Appends a new constraint to the Constraints section.

    Args:
        agent_name: Agent to mutate
        new_constraint: The constraint text to add
        reason: Why this mutation was proposed

    Returns:
        True if applied, False if GENOME not found
    """
    path = get_genome_path(agent_name)
    if not path.exists():
        logger.error(f"[genome] GENOME not found for {agent_name}")
        return False

    content = path.read_text()
    ts = datetime.now().strftime("%Y-%m-%d")

    mutation_block = (
        f"\n- {new_constraint}\n"
        f"  (added {ts}, reason: {reason})\n"
    )

    # Insert after "## Constraints" section
    if "## Constraints" in content:
        # Find end of constraints section (next ## or end of file)
        parts = content.split("## Constraints", 1)
        after_header = parts[1]

        # Find next section header
        next_section_idx = after_header.find("\n## ", 1)
        if next_section_idx > 0:
            # Insert before next section
            new_content = (
                parts[0]
                + "## Constraints"
                + after_header[:next_section_idx]
                + mutation_block
                + after_header[next_section_idx:]
            )
        else:
            # No next section — append to end
            new_content = content + mutation_block
    else:
        # No Constraints section — append at end
        new_content = content + f"\n## Constraints\n{mutation_block}"

    path.write_text(new_content)

    # Update mutation count in Fitness section
    _increment_mutation_count(path)

    logger.info(f"[genome] Applied mutation to {agent_name}: {new_constraint}")
    return True


def revert_last_mutation(agent_name: str) -> bool:
    """Revert the last mutation by removing the last constraint added.

    Simple approach: remove the last line matching "(added YYYY-MM-DD, reason:".

    Returns:
        True if reverted, False if nothing to revert
    """
    path = get_genome_path(agent_name)
    if not path.exists():
        return False

    content = path.read_text()
    lines = content.split("\n")

    # Find last mutation marker
    last_mutation_idx = -1
    for i in range(len(lines) - 1, -1, -1):
        if "(added " in lines[i] and "reason:" in lines[i]:
            last_mutation_idx = i
            break

    if last_mutation_idx < 0:
        return False

    # Remove the constraint line and the reason line
    # The constraint is the line before the reason
    start = max(0, last_mutation_idx - 1)
    if start > 0 and lines[start].startswith("- "):
        del lines[start : last_mutation_idx + 1]
    else:
        del lines[last_mutation_idx]

    path.write_text("\n".join(lines))
    logger.info(f"[genome] Reverted last mutation for {agent_name}")
    return True


def _increment_mutation_count(genome_path: Path) -> None:
    """Increment the mutation counter in Fitness section."""
    content = genome_path.read_text()
    if "Mutations:" in content:
        import re

        def _inc(m: re.Match) -> str:
            try:
                count = int(m.group(1))
            except ValueError:
                count = 0
            return f"Mutations: {count + 1}"

        content = re.sub(r"Mutations:\s*(\d+)", _inc, content, count=1)
        genome_path.write_text(content)
