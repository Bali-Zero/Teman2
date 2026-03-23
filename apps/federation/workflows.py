"""
Federation Workflows — Pre-defined multi-agent pipelines.

Each workflow defines:
  - agents: which agents to dispatch (in order or parallel)
  - steps: named steps with prompts and dependencies
  - output: what to produce

Usage:
  python -m apps.federation.workflows run task-dispatch "add pagination to clients API"
  python -m apps.federation.workflows run intel-pipeline
  python -m apps.federation.workflows list
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowStep:
    """A single step in a workflow."""
    name: str
    agent: str  # Agent ID to dispatch
    prompt_template: str  # {task} will be replaced
    depends_on: list[str] = field(default_factory=list)  # Step names this depends on


@dataclass
class Workflow:
    """A complete workflow definition."""
    id: str
    name: str
    description: str
    steps: list[WorkflowStep]
    auto_redteam: bool = False  # Force red team at the end


# ═══════════════════════════════════════════════════════
# Workflow Definitions
# ═══════════════════════════════════════════════════════

WORKFLOWS: dict[str, Workflow] = {}


def register(w: Workflow) -> None:
    WORKFLOWS[w.id] = w


# --- 1. Task Dispatch (replaces federation_orchestrator.py simple flow) ---
register(Workflow(
    id="task-dispatch",
    name="Task Dispatch",
    description="Classify and route a task to the right agents. Default workflow.",
    steps=[
        # This workflow uses the orchestrator's built-in classification.
        # No custom steps needed — it's the default path.
    ],
))

# --- 2. Intel Pipeline ---
register(Workflow(
    id="intel-pipeline",
    name="Intel Pipeline",
    description="Scraper → Deep Research → Write article → Review → Publish",
    steps=[
        WorkflowStep(
            name="research",
            agent="gemini-search",
            prompt_template="Research the latest Indonesian business regulations, visa policy changes, and KBLI updates from the past 7 days. Focus on changes that affect foreign investors and PT PMA companies in Bali. Provide sources.",
        ),
        WorkflowStep(
            name="deep-research",
            agent="notebooklm",
            prompt_template="Using the KBLI 2025 and Visa Knowledge notebooks, cross-reference: {prev_research}. Identify which of our 5000+ clients are impacted by these changes. Provide citations.",
            depends_on=["research"],
        ),
        WorkflowStep(
            name="write",
            agent="claude-code",
            prompt_template="Based on this research, compose an intelligence article for balizero.com/blog. Use the compose_article MCP tool. Research: {prev_deep-research}",
            depends_on=["deep-research"],
        ),
        WorkflowStep(
            name="review",
            agent="claude-review",
            prompt_template="Review this intelligence article for factual accuracy, legal claims, and tone. Flag any unverified claims: {prev_write}",
            depends_on=["write"],
        ),
    ],
    auto_redteam=False,  # review step already handles this
))

# --- 3. Client Onboarding ---
register(Workflow(
    id="client-onboarding",
    name="Client Onboarding",
    description="CRM create → Drive folder → Welcome email → Calendar → Journey start",
    steps=[
        WorkflowStep(
            name="crm-create",
            agent="claude-code",
            prompt_template="Create a new client in the CRM using create_client MCP tool with these details: {task}. Extract name, email, nationality, service type from the task description.",
        ),
        WorkflowStep(
            name="drive-setup",
            agent="claude-code",
            prompt_template="Create the client Drive folder using create_client_drive_folder MCP tool for the client just created: {prev_crm-create}",
            depends_on=["crm-create"],
        ),
        WorkflowStep(
            name="welcome-email",
            agent="gws",
            prompt_template="Send a welcome email to the new client. Use the welcome template. Client details: {prev_crm-create}",
            depends_on=["crm-create"],
        ),
        WorkflowStep(
            name="calendar-booking",
            agent="gws",
            prompt_template="Create a kick-off meeting in the next 3 business days for client: {prev_crm-create}. Check free-busy first.",
            depends_on=["crm-create"],
        ),
        WorkflowStep(
            name="journey-start",
            agent="claude-code",
            prompt_template="Start the client journey using create_journey MCP tool. Type based on service requested: {prev_crm-create}",
            depends_on=["drive-setup", "welcome-email"],
        ),
    ],
))

# --- 4. Compliance Watchdog ---
register(Workflow(
    id="compliance-watchdog",
    name="Compliance Watchdog",
    description="Check expiring documents → progressive escalation (90→60→30→7 days)",
    steps=[
        WorkflowStep(
            name="scan",
            agent="claude-code",
            prompt_template="Run get_expiry_alerts MCP tool. Check all clients for expiring visas, KITAS, KITAP, and company documents within 90 days.",
        ),
        WorkflowStep(
            name="classify",
            agent="claude-code",
            prompt_template="Classify these expiry alerts by urgency: 90-day (info), 60-day (warning), 30-day (urgent), 7-day (critical). Alerts: {prev_scan}",
            depends_on=["scan"],
        ),
        WorkflowStep(
            name="notify",
            agent="gws",
            prompt_template="Send compliance notification emails based on urgency level. Critical (7-day): send to client + team + admin. Urgent (30-day): send to client + team. Warning: send to team only. Classified alerts: {prev_classify}",
            depends_on=["classify"],
        ),
        WorkflowStep(
            name="track",
            agent="claude-code",
            prompt_template="Update compliance tracking in CRM using track_compliance MCP tool. Log all sent notifications. Alerts: {prev_classify}",
            depends_on=["notify"],
        ),
    ],
))

# --- 5. Pre-Deploy Review ---
register(Workflow(
    id="pre-deploy",
    name="Pre-Deploy Review",
    description="Codebase audit → Red team → Deploy or fix",
    steps=[
        WorkflowStep(
            name="codebase-audit",
            agent="gemini-explore",
            prompt_template="Analyze the codebase changes in apps/backend-rag/ for the upcoming deploy. Check: import chain integrity (dependencies.py), new routes, service changes, migration files. Use codebase_investigator tool.",
        ),
        WorkflowStep(
            name="test-run",
            agent="codex-sandbox",
            prompt_template="In sandbox mode, run: PYTHONPATH=. pytest backend/tests/services/rag/test_confidence.py -q. Report pass/fail.",
        ),
        WorkflowStep(
            name="redteam",
            agent="claude-review",
            prompt_template="Red team review of these changes before Fly.io deploy. Check for: security vulnerabilities, breaking changes, performance regressions, data integrity risks. Codebase audit: {prev_codebase-audit}. Test results: {prev_test-run}",
            depends_on=["codebase-audit", "test-run"],
        ),
    ],
    auto_redteam=False,  # Built-in
))


# ═══════════════════════════════════════════════════════
# Workflow Executor
# ═══════════════════════════════════════════════════════
async def execute_workflow(
    workflow_id: str,
    task: str = "",
    *,
    interactive: bool = True,
) -> dict[str, Any]:
    """Execute a workflow by running its steps in dependency order."""
    from apps.federation.orchestrator import dispatch_agents, save_output, assemble_context

    if workflow_id == "task-dispatch":
        # Use the default orchestrator pipeline
        from apps.federation.orchestrator import run_federation
        outfile = await run_federation(task, interactive=interactive)
        return {"workflow": workflow_id, "output_file": outfile}

    workflow = WORKFLOWS.get(workflow_id)
    if not workflow:
        print(f"Unknown workflow: {workflow_id}")
        print(f"Available: {', '.join(WORKFLOWS.keys())}")
        return {"error": f"Unknown workflow: {workflow_id}"}

    print(f"\n  Workflow: {workflow.name}")
    print(f"  Description: {workflow.description}")
    print(f"  Steps: {len(workflow.steps)}")
    if task:
        print(f"  Task: {task[:100]}")
    print()

    # Execute steps respecting dependencies
    step_results: dict[str, str] = {}  # step_name → output
    completed: set[str] = set()

    # Build dependency graph
    remaining = list(workflow.steps)

    while remaining:
        # Find steps whose dependencies are all completed
        ready = [s for s in remaining if all(d in completed for d in s.depends_on)]
        if not ready:
            print("  ERROR: Circular dependency or unresolvable steps")
            break

        # Run ready steps in parallel
        print(f"  Running {len(ready)} step(s) in parallel: {', '.join(s.name for s in ready)}")

        async def run_step(step: WorkflowStep) -> tuple[str, str]:
            # Build prompt with previous results
            prompt = step.prompt_template
            if task:
                prompt = prompt.replace("{task}", task)
            for dep_name, dep_result in step_results.items():
                prompt = prompt.replace(f"{{prev_{dep_name}}}", dep_result[:2000])

            results = await dispatch_agents([step.agent], prompt)
            output = results[0].get("output", "") if results else "(no output)"
            status = results[0].get("status", "unknown") if results else "failed"
            elapsed = results[0].get("elapsed_s", 0) if results else 0

            icon = "✅" if status == "completed" else "❌"
            print(f"    {icon} {step.name} ({step.agent}): {status} ({elapsed:.1f}s)")
            return step.name, output

        parallel_results = await asyncio.gather(*[run_step(s) for s in ready])
        for name, output in parallel_results:
            step_results[name] = output
            completed.add(name)
            remaining = [s for s in remaining if s.name != name]

    # Assemble final output
    classification = {"type": "workflow", "risk": "low", "domains": [workflow_id], "dispatch": []}
    results_list = [
        {"agent_id": f"{s.name}→{s.agent}", "status": "completed", "output": step_results.get(s.name, ""), "elapsed_s": 0}
        for s in workflow.steps
    ]
    context = assemble_context(task or workflow.name, classification, results_list)
    outfile = save_output(context, task or workflow.name, classification)

    print(f"\n  Workflow complete: {outfile}")
    return {"workflow": workflow_id, "output_file": str(outfile), "steps": len(completed)}


def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] == "list":
        print("\nAvailable workflows:")
        for wid, w in WORKFLOWS.items():
            print(f"  {wid:25s} — {w.description}")
        return

    if args[0] == "run":
        if len(args) < 2:
            print("Usage: python -m apps.federation.workflows run <workflow-id> [task]")
            return

        workflow_id = args[1]
        task = " ".join(args[2:]) if len(args) > 2 else ""

        asyncio.run(execute_workflow(workflow_id, task, interactive=False))
    else:
        print(f"Unknown command: {args[0]}. Use 'list' or 'run'.")


if __name__ == "__main__":
    main()
