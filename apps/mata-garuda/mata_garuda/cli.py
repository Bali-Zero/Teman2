"""
Mata Garuda — CLI entry point.

Usage:
    python -m mata_garuda.cli list-agents
    python -m mata_garuda.cli info <agent_name>
    python -m mata_garuda.cli run <agent_name> "query"
    python -m mata_garuda.cli run <agent_name> "query" --lamarckian
    python -m mata_garuda.cli mutate <agent_name>
    python -m mata_garuda.cli fitness <agent_name>
    python -m mata_garuda.cli health
    python -m mata_garuda.cli health --json
    python -m mata_garuda.cli version
"""
from __future__ import annotations

import argparse
import json
import sys

from mata_garuda import __version__
from mata_garuda.registry import registry

# Importa il sotto-package agents — triggera il recursive auto-import
# e popola il registry con tutti gli @register_agent decorators
import mata_garuda.agents  # noqa: F401


def cmd_list_agents(args: argparse.Namespace) -> int:
    """List all registered agents."""
    if not registry.agents:
        print("No agents registered.")
        return 0

    print(f"Registered agents ({len(registry.agents)}):")
    for display_name, info in registry.agents_info.items():
        print(f"  • {display_name} (func: {info.func_name})")
        if info.docstring:
            first_line = info.docstring.strip().split("\n")[0]
            print(f"    {first_line}")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Show detailed info for a specific agent."""
    name = args.name
    if name not in registry.agents_info:
        print(f"Error: agent '{name}' not found.", file=sys.stderr)
        print(f"Available: {', '.join(registry.agents_info.keys())}", file=sys.stderr)
        return 1

    info = registry.agents_info[name]
    print(json.dumps(info.to_dict(), indent=2, default=str))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Run an agent with a query."""
    from mata_garuda.runtime.loop import run_agent_loop

    agent_name = args.agent
    query = args.query

    # Find agent by display name or func_name
    agent_fn = None
    for display_name, info in registry.agents_info.items():
        if display_name == agent_name or info.func_name == agent_name:
            agent_fn = info.func
            agent_name = display_name
            break

    if agent_fn is None:
        print(f"Error: agent '{agent_name}' not found.", file=sys.stderr)
        print(f"Available: {', '.join(registry.agents_info.keys())}", file=sys.stderr)
        return 1

    # Instantiate agent
    model = args.model or "claude"
    agent = agent_fn(model=model)

    print(f"[Mata Garuda] Running {agent_name} (model={model})")
    print(f"[Mata Garuda] Query: {query}")
    print()

    # Always provide KB in context for knowledge tools
    from mata_garuda.runtime.knowledge import KnowledgeBase

    kb = KnowledgeBase()
    context_variables = {"kb": kb, "agent_name": agent_name}

    # Run with Lamarckian feedback if requested
    if getattr(args, "lamarckian", False):
        from mata_garuda.runtime.lamarckian import run_with_lamarckian_feedback

        print("[Mata Garuda] Lamarckian feedback loop ACTIVE")
        response = run_with_lamarckian_feedback(
            agent=agent, query=query, kb=kb, context_variables=context_variables,
        )
    else:
        response = run_agent_loop(
            agent=agent, query=query, context_variables=context_variables,
        )

    kb.close()

    # Print final messages
    for msg in response.messages:
        role = msg.get("role", "?")
        content = msg.get("content", "")
        if role == "assistant":
            print(content)
        elif role == "tool":
            tool_name = msg.get("tool_name", "tool")
            print(f"  [{tool_name}] {content}")

    return 0


def cmd_mutate(args: argparse.Namespace) -> int:
    """Propose and optionally apply a GENOME.md mutation from feedback."""
    from mata_garuda.runtime.genome import (
        apply_mutation,
        propose_mutation,
        read_feedback,
        read_genome,
    )

    agent_name = args.agent
    feedback = read_feedback(agent_name)
    if not feedback:
        print(f"No feedback found for '{agent_name}'.")
        return 0

    genome = read_genome(agent_name)
    if not genome:
        print(f"No GENOME.md found for '{agent_name}'.", file=sys.stderr)
        return 1

    # Show proposal
    proposal = propose_mutation(agent_name, feedback)
    print(proposal)
    print()

    if args.auto:
        print("[WARNING] Auto-mutate is ON — applying without review")
        # Extract a simple constraint from the last feedback entry
        lines = feedback.strip().split("\n")
        last_insight = ""
        last_reason = ""
        for line in reversed(lines):
            if line.startswith("**Insight:**"):
                last_insight = line.replace("**Insight:**", "").strip()
            elif line.startswith("**Reason:**"):
                last_reason = line.replace("**Reason:**", "").strip()
            if last_insight and last_reason:
                break

        if last_insight:
            apply_mutation(agent_name, last_insight, last_reason)
            print(f"[APPLIED] Mutation: {last_insight}")
            print(f"[REASON] {last_reason}")
        else:
            print("[SKIP] Could not extract constraint from feedback")
    else:
        print("To apply a mutation, run with --auto flag or edit GENOME.md manually.")
        print(f"  GENOME: mata_garuda/agents/{agent_name.lower().replace(' ', '_')}_GENOME.md")
        print(f"  Feedback: feedback/{agent_name.lower().replace(' ', '_')}.md")

    return 0


def cmd_fitness(args: argparse.Namespace) -> int:
    """Show fitness statistics for an agent."""
    from mata_garuda.runtime.fitness import get_fitness_summary, get_recent_runs

    agent_name = args.agent
    summary = get_fitness_summary(agent_name)
    print(summary)

    runs = get_recent_runs(agent_name)
    if runs:
        print(f"\nRecent runs ({len(runs)}):")
        for r in runs[-5:]:
            ts = r.get("timestamp", "?")
            if "event" in r:
                print(f"  {ts} — {r['event']} (from v{r.get('from_version', '?')})")
            else:
                status = "✓" if r.get("success") else "✗"
                print(f"  {ts} — {status} (v{r.get('mutation_version', 0)})")

    return 0


def cmd_version(args: argparse.Namespace) -> int:
    """Print Mata Garuda version."""
    print(f"mata-garuda {__version__}")
    return 0


def cmd_health(args: argparse.Namespace) -> int:
    """Print Mata Garuda health dashboard (streams, agents, KB, bridge)."""
    from mata_garuda.tools.health_tools import build_health_report, format_report

    report = build_health_report()
    if getattr(args, "json", False):
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    else:
        print(format_report(report))

    return 0 if report["status"] != "RED" else 2



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mata-garuda",
        description="Mata Garuda — Intelligence Super Hub CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list-agents", help="List all registered agents")
    p_list.set_defaults(func=cmd_list_agents)

    p_info = sub.add_parser("info", help="Show info for a specific agent")
    p_info.add_argument("name", help="Agent display name (e.g., 'Dummy Agent')")
    p_info.set_defaults(func=cmd_info)

    p_run = sub.add_parser("run", help="Run an agent with a query")
    p_run.add_argument("agent", help="Agent display name or func_name")
    p_run.add_argument("query", help="Query/task to send to the agent")
    p_run.add_argument("--model", "-m", help="LLM model (default: claude)")
    p_run.add_argument(
        "--lamarckian", "-L", action="store_true",
        help="Enable Lamarckian feedback loop (retry + feedback + escalation)"
    )
    p_run.set_defaults(func=cmd_run)

    p_mutate = sub.add_parser("mutate", help="Propose GENOME.md mutation from feedback")
    p_mutate.add_argument("agent", help="Agent display name")
    p_mutate.add_argument(
        "--auto", action="store_true",
        help="Apply mutation without human review (DANGEROUS)"
    )
    p_mutate.set_defaults(func=cmd_mutate)

    p_fitness = sub.add_parser("fitness", help="Show fitness stats for an agent")
    p_fitness.add_argument("agent", help="Agent display name")
    p_fitness.set_defaults(func=cmd_fitness)

    p_version = sub.add_parser("version", help="Print version")
    p_version.set_defaults(func=cmd_version)

    p_health = sub.add_parser("health", help="System health dashboard")
    p_health.add_argument(
        "--json", action="store_true",
        help="Emit machine-readable JSON instead of the human report"
    )
    p_health.set_defaults(func=cmd_health)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
