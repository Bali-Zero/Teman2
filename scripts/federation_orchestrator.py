#!/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python3
"""
Nuzantara Federation Orchestrator — LangGraph-based automatic task routing.

Classifies incoming tasks and dispatches to the right agents:
- Gemini CLI (search, explore) for intelligence gathering
- Codex CLI (sandbox) for risky isolated execution
- Gemini CLI (redteam) for pre-deploy review

Usage:
    python scripts/federation_orchestrator.py "add quarterly tax calculation for PT PMA"
    python scripts/federation_orchestrator.py --telegram CHAT_ID "task description"

Architecture:
    CLASSIFY → CHECKPOINT → DISPATCH (parallel) → ASSEMBLE → REVIEW → OUTPUT
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv

# Load env for TELEGRAM_BOT_TOKEN
_master_env = Path.home() / "Desktop" / "NUZANTARA_ENV_KEYS.env"
_backend_env = Path(__file__).resolve().parent.parent / "apps" / "backend-rag" / ".env"
for _env in (_master_env, _backend_env):
    if _env.exists():
        load_dotenv(_env, override=False)

import httpx
from langgraph.graph import END, StateGraph

# ═══════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DISPATCH_SCRIPT = PROJECT_ROOT / "scripts" / "ai-dispatch.sh"
OUTPUT_DIR = PROJECT_ROOT / "ai-dispatch-output"
AUDIT_FILE = OUTPUT_DIR / "audit.jsonl"

CLASSIFIER_MODEL = "qwen3.5:9b"  # Local via Ollama — $0, no API credits needed
OLLAMA_URL = "http://localhost:11434"

# LangSmith observability (disabled until API key configured)
# Set LANGCHAIN_API_KEY in .env to enable tracing
if not os.environ.get("LANGCHAIN_API_KEY"):
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
else:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "nuzantara-federation")


# ═══════════════════════════════════════════════════════
# State
# ═══════════════════════════════════════════════════════
class FederationState(TypedDict, total=False):
    task: str
    telegram_chat_id: str | None
    interactive: bool
    classification: dict
    search_result: str | None
    explore_result: str | None
    sandbox_result: str | None
    redteam_result: str | None
    assembled_context: str
    audit_entries: list[dict]


# ═══════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════
async def run_dispatch(cmd: str, prompt: str) -> str:
    """Execute ai-dispatch.sh and return output."""
    proc = await asyncio.create_subprocess_exec(
        str(DISPATCH_SCRIPT), cmd, prompt,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(PROJECT_ROOT),
    )
    stdout, stderr = await proc.communicate()
    output = stdout.decode().strip()
    if proc.returncode != 0 and not output:
        output = f"[DISPATCH ERROR exit={proc.returncode}] {stderr.decode().strip()}"
    return output


def append_audit(entry: dict) -> None:
    """Append entry to audit.jsonl."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_FILE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


async def send_telegram(chat_id: str, text: str) -> None:
    """Send message via @Balizerobot."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return
    # Truncate to Telegram's 4096 char limit
    if len(text) > 4000:
        text = text[:3990] + "\n...(truncated)"
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
        )


# ═══════════════════════════════════════════════════════
# Nodes
# ═══════════════════════════════════════════════════════
CLASSIFY_PROMPT = """Classify this software development task for routing.

Task: {task}

Respond with ONLY valid JSON (no markdown, no explanation):
{{
  "type": "feature|bugfix|refactor|deploy|research|conversation",
  "risk": "low|medium|high",
  "domains": ["list of app/service areas involved"],
  "needs_search": <true if task involves regulations, laws, taxes, visa, KBLI, or external data>,
  "needs_explore": <true if task touches 3+ apps or requires reading >5 files>,
  "needs_sandbox": <true if task involves DB migration, schema change, or risky code>,
  "needs_redteam": <true if task involves deployment or critical system changes>
}}"""


async def classify_node(state: FederationState) -> dict:
    """Classify the task using local Ollama (Qwen 3.5:9b)."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": CLASSIFIER_MODEL,
                "messages": [{"role": "user", "content": CLASSIFY_PROMPT.format(task=state["task"])}],
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 300},
                "think": False,  # CRITICAL: disable thinking for Qwen 3.5
            },
        )
        resp.raise_for_status()
        raw = resp.json()["message"]["content"].strip()

    # Extract JSON from potential markdown fencing or think tags
    if "<think>" in raw:
        raw = raw.split("</think>")[-1].strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    classification = json.loads(raw)
    return {"classification": classification}


async def human_checkpoint_node(state: FederationState) -> dict:
    """Show classification and ask for confirmation."""
    c = state["classification"]
    summary = (
        f"\n{'='*40}\n"
        f"  FEDERATION ROUTING\n"
        f"{'='*40}\n"
        f"  Task:    {state['task'][:80]}\n"
        f"  Type:    {c.get('type')} | Risk: {c.get('risk')}\n"
        f"  Search:  {c.get('needs_search')} | Explore: {c.get('needs_explore')}\n"
        f"  Sandbox: {c.get('needs_sandbox')} | Redteam: {c.get('needs_redteam')}\n"
        f"  Domains: {', '.join(c.get('domains', []))}\n"
        f"{'='*40}"
    )

    if state.get("telegram_chat_id"):
        # Telegram mode: send summary, no blocking input
        await send_telegram(state["telegram_chat_id"], f"```\n{summary}\n```\nProceeding automatically...")
        return {}

    if state.get("interactive", True):
        print(summary)
        confirm = input("  Proceed? [Y/n/edit]: ").strip().lower()
        if confirm == "n":
            print("  Aborted.")
            sys.exit(0)
        elif confirm == "edit":
            override = input('  JSON override (e.g. {"needs_search": true}): ')
            try:
                updates = json.loads(override)
                return {"classification": {**c, **updates}}
            except json.JSONDecodeError:
                print("  Invalid JSON, proceeding with original classification.")
    return {}


async def search_node(state: FederationState) -> dict:
    """Launch Gemini search via ai-dispatch.sh."""
    print("  [DISPATCH] Gemini search...")
    result = await run_dispatch("search", state["task"])
    append_audit({
        "ts": datetime.now(timezone.utc).isoformat(),
        "cmd": "search", "source": "federation_orchestrator",
        "exit_code": 0 if result and "error" not in result.lower() else 1,
    })
    return {"search_result": result}


async def explore_node(state: FederationState) -> dict:
    """Launch Gemini explore via ai-dispatch.sh."""
    print("  [DISPATCH] Gemini explore...")
    result = await run_dispatch("explore", state["task"])
    append_audit({
        "ts": datetime.now(timezone.utc).isoformat(),
        "cmd": "explore", "source": "federation_orchestrator",
        "exit_code": 0 if result and "error" not in result.lower() else 1,
    })
    return {"explore_result": result}


async def sandbox_node(state: FederationState) -> dict:
    """Launch Codex sandbox via ai-dispatch.sh."""
    print("  [DISPATCH] Codex sandbox...")
    result = await run_dispatch("sandbox", state["task"])
    append_audit({
        "ts": datetime.now(timezone.utc).isoformat(),
        "cmd": "sandbox", "source": "federation_orchestrator",
        "exit_code": 0 if result and "error" not in result.lower() else 1,
    })
    return {"sandbox_result": result}


async def assemble_node(state: FederationState) -> dict:
    """Assemble all gathered context into a single document."""
    parts = [f"# Federation Context for Task\n\n## Original Task\n{state['task']}"]

    c = state.get("classification", {})
    parts.append(
        f"\n## Classification\n"
        f"- Type: {c.get('type')} | Risk: {c.get('risk')}\n"
        f"- Domains: {', '.join(c.get('domains', []))}"
    )

    if state.get("search_result"):
        parts.append(f"\n## Normative/Web Research (Gemini Search)\n{state['search_result']}")
    if state.get("explore_result"):
        parts.append(f"\n## Codebase Analysis (Gemini Explore)\n{state['explore_result']}")
    if state.get("sandbox_result"):
        parts.append(f"\n## Sandbox Test (Codex)\n{state['sandbox_result']}")

    assembled = "\n\n---\n\n".join(parts)
    return {"assembled_context": assembled}


async def review_node(state: FederationState) -> dict:
    """Red team review via Claude CLI (Opus reasoning) — for high-risk tasks only."""
    print("  [DISPATCH] Claude redteam (Opus 4.6)...")
    # Use Claude CLI for redteam — superior reasoning vs Gemini
    context_summary = state.get("assembled_context", "")[:3000]
    result = await run_dispatch("claude-redteam", context_summary)
    append_audit({
        "ts": datetime.now(timezone.utc).isoformat(),
        "cmd": "redteam", "source": "federation_orchestrator",
        "exit_code": 0 if result and "error" not in result.lower() else 1,
    })
    updated = state.get("assembled_context", "") + f"\n\n---\n\n## Red Team Review\n{result}"
    return {"assembled_context": updated, "redteam_result": result}


async def output_node(state: FederationState) -> dict:
    """Save assembled context and deliver results."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    outfile = OUTPUT_DIR / f"{timestamp}-federation-context.md"

    context = state.get("assembled_context", "No context assembled.")
    outfile.write_text(context)

    c = state.get("classification", {})
    dispatched = []
    if c.get("needs_search"):
        dispatched.append("search")
    if c.get("needs_explore"):
        dispatched.append("explore")
    if c.get("needs_sandbox"):
        dispatched.append("sandbox")
    if c.get("needs_redteam") or c.get("risk") == "high":
        dispatched.append("redteam")

    summary_line = f"Dispatched: {', '.join(dispatched) or 'none (simple task)'}"

    print(f"\n  Context saved: {outfile}")
    print(f"  {summary_line}")
    if not dispatched:
        print("  No dispatch needed — proceed directly with Claude Code.")
    else:
        print("  Paste context file into Claude Code or OpenClaw coder.")

    # Telegram output
    if state.get("telegram_chat_id"):
        # Send a concise summary, not the full context
        tg_msg = (
            f"*Federation Complete*\n\n"
            f"Task: {state['task'][:200]}\n"
            f"Type: {c.get('type')} | Risk: {c.get('risk')}\n"
            f"{summary_line}\n\n"
            f"Context: `{outfile.name}`"
        )
        await send_telegram(state["telegram_chat_id"], tg_msg)

    return {}


# ═══════════════════════════════════════════════════════
# Routing logic
# ═══════════════════════════════════════════════════════
def route_after_checkpoint(state: FederationState) -> list[str]:
    """Decide which dispatch nodes to run in parallel."""
    c = state.get("classification", {})
    routes = []
    if c.get("needs_search"):
        routes.append("search")
    if c.get("needs_explore"):
        routes.append("explore")
    if c.get("needs_sandbox"):
        routes.append("sandbox")
    if not routes:
        routes.append("assemble")
    return routes


def route_after_assemble(state: FederationState) -> str:
    """Decide if review is needed."""
    c = state.get("classification", {})
    if c.get("needs_redteam") or c.get("risk") == "high":
        return "review"
    return "output"


# ═══════════════════════════════════════════════════════
# Build Graph
# ═══════════════════════════════════════════════════════
def build_graph() -> StateGraph:
    graph = StateGraph(FederationState)

    graph.add_node("classify", classify_node)
    graph.add_node("checkpoint", human_checkpoint_node)
    graph.add_node("search", search_node)
    graph.add_node("explore", explore_node)
    graph.add_node("sandbox", sandbox_node)
    graph.add_node("assemble", assemble_node)
    graph.add_node("review", review_node)
    graph.add_node("output", output_node)

    graph.set_entry_point("classify")
    graph.add_edge("classify", "checkpoint")
    graph.add_conditional_edges("checkpoint", route_after_checkpoint)
    graph.add_edge("search", "assemble")
    graph.add_edge("explore", "assemble")
    graph.add_edge("sandbox", "assemble")
    graph.add_conditional_edges("assemble", route_after_assemble)
    graph.add_edge("review", "output")
    graph.add_edge("output", END)

    return graph.compile()


# ═══════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════
def main():
    args = sys.argv[1:]

    telegram_chat_id = None
    if "--telegram" in args:
        idx = args.index("--telegram")
        telegram_chat_id = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    non_interactive = "--no-confirm" in args
    if non_interactive:
        args.remove("--no-confirm")

    task = " ".join(args) if args else input("Task: ")
    if not task.strip():
        print("Error: empty task")
        sys.exit(1)

    app = build_graph()
    initial_state: FederationState = {
        "task": task,
        "telegram_chat_id": telegram_chat_id,
        "interactive": not non_interactive and not telegram_chat_id,
        "classification": {},
        "search_result": None,
        "explore_result": None,
        "sandbox_result": None,
        "redteam_result": None,
        "assembled_context": "",
        "audit_entries": [],
    }

    print(f"\n  Federation Orchestrator v1")
    print(f"  Task: {task[:100]}")
    print()

    result = asyncio.run(app.ainvoke(initial_state))


if __name__ == "__main__":
    main()
