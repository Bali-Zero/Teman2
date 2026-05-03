"""
Mata Garuda — Lamarckian Feedback Loop.

The core evolution mechanism:
1. Agent runs → case_resolved or case_not_resolved
2. On failure → log to feedback/{agent}.md
3. Retry up to MAX_RETRY times with progressive hints
4. After max retries → escalate to meta-agent for GENOME mutation
5. Track fitness → auto-revert if mutation degrades performance

Pattern: HKUDS/AutoAgent run_in_client + Mata Garuda Lamarckian extension.
Reference: docs/mata-garuda/40d-AUTOAGENT-PATTERNS.md Pattern 3
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from mata_garuda.runtime.cli_runtime import CLIRuntime
from mata_garuda.runtime.fitness import (
    check_and_auto_revert,
    get_mutation_version,
    record_run,
)
from mata_garuda.runtime.genome import (
    log_feedback,
    read_genome,
)
from mata_garuda.runtime.knowledge import KnowledgeBase
from mata_garuda.runtime.loop import run_agent_loop
from mata_garuda.runtime.reflection import (
    build_reflection_context,
    build_reflection_prompt,
    parse_reflection,
    store_reflection_in_kb,
)
from mata_garuda.types import Agent, Response

logger = logging.getLogger("mata_garuda.runtime")

MAX_RETRY = 3

# Hints get progressively more specific
RETRY_HINTS = [
    "Try a different approach. Re-read your constraints.",
    "Read your GENOME.md carefully. What constraint are you violating?",
    "This is your last attempt. Simplify your approach to the bare minimum.",
]


def _parse_case_status(output: str) -> tuple[Optional[str], Optional[dict]]:
    """Parse case_resolved or case_not_resolved from output.

    Returns:
        (status, details) where status is "resolved"/"not_resolved"/None
        and details contains parsed fields
    """
    if "Case resolved" in output:
        # Extract result
        match = re.search(r"Case resolved\. The result is: (.+)", output, re.DOTALL)
        result = match.group(1).strip() if match else output
        return "resolved", {"result": result}

    if "Case not resolved" in output:
        reason_match = re.search(r"Reason: ([^.]+(?:\.[^I])*)", output)
        insight_match = re.search(r"Insight: (.+)", output, re.DOTALL)
        return "not_resolved", {
            "reason": reason_match.group(1).strip() if reason_match else "unknown",
            "insight": insight_match.group(1).strip() if insight_match else "",
        }

    return None, None


def _run_post_reflection(
    agent: Agent,
    query: str,
    success: bool,
    messages: list[dict],
    kb: Optional[KnowledgeBase] = None,
) -> None:
    """Run post-run reflection and store in KB. Non-blocking — failures logged, not raised."""
    if kb is None:
        return

    try:
        genome = read_genome(agent.name) or ""
        genome_snippet = genome[:500] if genome else "No GENOME"

        messages_summary = ""
        for msg in messages[-5:]:
            content = msg.get("content", "")[:200]
            messages_summary += f"[{msg.get('role', '?')}] {content}\n"

        prompt = build_reflection_prompt(
            agent_name=agent.name,
            query=query,
            outcome_success=success,
            messages_summary=messages_summary,
            genome_snippet=genome_snippet,
        )

        runtime = CLIRuntime(model="claude")
        result = runtime.invoke(prompt=prompt, system_prompt="Output only JSON.")

        if result.success:
            parsed = parse_reflection(result.output)
            store_reflection_in_kb(kb, agent.name, parsed)
            logger.info(f"[lamarckian] Reflection stored for {agent.name}")
        else:
            logger.warning(f"[lamarckian] Reflection CLI failed: {result.stderr[:100]}")
    except Exception as e:
        logger.warning(f"[lamarckian] Reflection failed (non-blocking): {e}")


def run_with_lamarckian_feedback(
    agent: Agent,
    query: str,
    context_variables: Optional[dict] = None,
    max_retry: int = MAX_RETRY,
    kb: Optional[KnowledgeBase] = None,
) -> Response:
    """
    Run an agent with Lamarckian feedback loop + Reflexion.

    Flow:
    1. Inject recent reflections from KB into prompt
    2. Run agent via MetaChain loop
    3. Check for case_resolved/case_not_resolved in output
    4. On resolved → record success, run reflection, return
    5. On not_resolved → log feedback, run reflection, retry with hint
    6. After max retries → escalate to meta-agent

    Args:
        agent: Agent instance to run
        query: User query
        context_variables: Shared state
        max_retry: Maximum retry attempts
        kb: Optional KnowledgeBase instance for reflection storage

    Returns:
        Response with all messages
    """
    if context_variables is None:
        context_variables = {}

    # Inject KB into context_variables for knowledge tools
    if kb is not None:
        context_variables["kb"] = kb
        context_variables["agent_name"] = agent.name

    mutation_version = get_mutation_version(agent.name)
    all_messages: list[dict] = []

    # Inject recent reflections into the first query
    reflection_context = ""
    if kb is not None:
        reflection_context = build_reflection_context(kb, agent.name, n=5)

    for attempt in range(max_retry):
        logger.info(
            f"[lamarckian] Attempt {attempt + 1}/{max_retry} for {agent.name}"
        )

        # Build query with retry hint if this is a retry
        if attempt > 0 and attempt <= len(RETRY_HINTS):
            current_query = (
                f"{query}\n\n"
                f"[RETRY {attempt + 1}/{max_retry}] "
                f"{RETRY_HINTS[attempt - 1]}"
            )
            genome = read_genome(agent.name)
            if genome:
                current_query += f"\n\nYour GENOME.md:\n{genome}"
        else:
            current_query = query + reflection_context

        # Run agent
        response = run_agent_loop(
            agent=agent,
            query=current_query,
            context_variables=context_variables,
        )

        all_messages.extend(response.messages)

        # Check terminal state in all messages
        last_content = ""
        for msg in reversed(response.messages):
            content = msg.get("content", "")
            if "Case resolved" in content or "Case not resolved" in content:
                last_content = content
                break

        if not last_content and response.messages:
            last_content = response.messages[-1].get("content", "")

        status, details = _parse_case_status(last_content)

        if status == "resolved":
            record_run(agent.name, success=True, mutation_version=mutation_version)
            logger.info(f"[lamarckian] {agent.name} resolved on attempt {attempt + 1}")
            _run_post_reflection(agent, query, True, all_messages, kb)
            return Response(
                messages=all_messages,
                agent=agent,
                context_variables=context_variables,
            )

        if status == "not_resolved":
            details = details or {}
            feedback_path = log_feedback(
                agent_name=agent.name,
                attempt=attempt + 1,
                failure_reason=details.get("reason", "unknown"),
                take_away=details.get("insight", ""),
            )
            record_run(agent.name, success=False, mutation_version=mutation_version)

            logger.warning(
                f"[lamarckian] {agent.name} failed attempt {attempt + 1}: "
                f"{details.get('reason', 'unknown')}"
            )

            if attempt >= max_retry - 1:
                logger.warning(
                    f"[lamarckian] {agent.name} exhausted retries. "
                    f"Escalating to meta-agent."
                )
                _run_post_reflection(agent, query, False, all_messages, kb)
                escalation_msg = {
                    "role": "system",
                    "content": (
                        f"[ESCALATION] Agent {agent.name} failed after "
                        f"{max_retry} attempts. Feedback logged at {feedback_path}. "
                        f"Consider proposing a GENOME.md mutation via "
                        f"'python -m mata_garuda.cli mutate {agent.name}'."
                    ),
                }
                all_messages.append(escalation_msg)
                break

            continue

        # No terminal state detected — treat as implicit resolution
        record_run(agent.name, success=True, mutation_version=mutation_version)
        logger.info(
            f"[lamarckian] {agent.name} finished without explicit case status "
            f"on attempt {attempt + 1} — treating as resolved"
        )
        _run_post_reflection(agent, query, True, all_messages, kb)
        return Response(
            messages=all_messages,
            agent=agent,
            context_variables=context_variables,
        )

    # Check fitness after the run
    check_and_auto_revert(agent.name)

    return Response(
        messages=all_messages,
        agent=agent,
        context_variables=context_variables,
    )
