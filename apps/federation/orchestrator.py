"""
Federation Orchestrator v3 — ADK + A2A native.

Replaces scripts/federation_orchestrator.py (LangGraph PoC) with
Google ADK agents + A2A protocol for inter-agent communication.

Architecture:
  1. ClassifierTool (Qwen 3.5:9b via Ollama) → classifies task
  2. RouterAgent (LlmAgent) → reads classification, picks sub-agents
  3. RemoteA2aAgent(s) → dispatches to federation agents via A2A
  4. Assembler → merges results
  5. Reviewer → optional red team (if high risk)

Usage:
  python -m apps.federation.orchestrator "add quarterly tax calculation for PT PMA"
  python -m apps.federation.orchestrator --no-confirm "task description"
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# Load env
_master_env = Path.home() / "Desktop" / "NUZANTARA_ENV_KEYS.env"
_backend_env = Path(__file__).resolve().parents[2] / "apps" / "backend-rag" / ".env"
for _env in (_master_env, _backend_env):
    if _env.exists():
        load_dotenv(_env, override=False)

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.federation_capability_table import (
    ARSENAL_SUMMARY,
    build_classifier_context,
    match_domains,
    suggest_agents,
)

logger = logging.getLogger("federation.orchestrator")

# ═══════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "ai-dispatch-output"
AUDIT_FILE = OUTPUT_DIR / "audit.jsonl"

CLASSIFIER_MODEL = "qwen3.5:9b"  # Local via Ollama — $0
OLLAMA_URL = "http://localhost:11434"

# Agent Card locations (local file paths — no HTTP needed for discovery)
AGENT_CARDS_DIR = Path(__file__).parent / "agents"

# Compact classifier prompt (must stay <2K tokens for Qwen 9b fast inference)
CLASSIFY_PROMPT = """Route this task. Available agents:
- gemini-search: regulations/KBLI/visa/tax/market research (web search)
- gemini-explore: codebase analysis across 3+ apps (1M context)
- codex-sandbox: DB migration/schema changes (isolated sandbox)
- claude-review: pre-deploy security/logic review (red team)
- notebooklm: multi-document synthesis/research (citations)
- gws: Google Workspace operations (email/calendar/drive/sheets)

Pre-matched domains: {matched_domains}

Task: {task}

Respond ONLY with JSON, no other text:
{{"type":"feature|bugfix|refactor|deploy|research|conversation","risk":"low|medium|high","domains":[...],
"dispatch":[list of agent IDs to dispatch, e.g. "gemini-search","codex-sandbox"]}}"""


# ═══════════════════════════════════════════════════════
# Classifier — Local Qwen 3.5:9b via Ollama
# ═══════════════════════════════════════════════════════
async def classify_task(task: str) -> dict[str, Any]:
    """Classify the task using Qwen 3.5:9b (local, $0)."""
    matched = match_domains(task)
    keyword_suggestions = suggest_agents(task)

    prompt = CLASSIFY_PROMPT.format(
        task=task,
        matched_domains=", ".join(matched) if matched else "none detected",
    )

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": CLASSIFIER_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 300},
                    "think": False,  # CRITICAL: disable thinking for Qwen 3.5
                    "keep_alive": "30m",
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
    except Exception as e:
        logger.warning("Classifier failed (%s: %s), using keyword fallback", type(e).__name__, e)
        dispatch = []
        if keyword_suggestions.get("needs_search"):
            dispatch.append("gemini-search")
        if keyword_suggestions.get("needs_explore"):
            dispatch.append("gemini-explore")
        if keyword_suggestions.get("needs_sandbox"):
            dispatch.append("codex-sandbox")
        if keyword_suggestions.get("needs_redteam"):
            dispatch.append("claude-review")
        if keyword_suggestions.get("needs_notebook"):
            dispatch.append("notebooklm")
        if keyword_suggestions.get("needs_gws"):
            dispatch.append("gws")

        classification = {
            "type": "research" if keyword_suggestions.get("needs_search") else "feature",
            "risk": "medium",
            "domains": matched or ["general"],
            "dispatch": dispatch,
        }

    # Ensure dispatch list exists
    if "dispatch" not in classification:
        dispatch = []
        # Backward compat with needs_* format from Qwen
        if classification.get("needs_search"):
            dispatch.append("gemini-search")
        if classification.get("needs_explore"):
            dispatch.append("gemini-explore")
        if classification.get("needs_sandbox"):
            dispatch.append("codex-sandbox")
        if classification.get("needs_redteam"):
            dispatch.append("claude-review")
        classification["dispatch"] = dispatch

    # Merge: if keywords caught something Qwen missed, add it
    keyword_to_agent = {
        "needs_search": "gemini-search",
        "needs_explore": "gemini-explore",
        "needs_sandbox": "codex-sandbox",
        "needs_redteam": "claude-review",
        "needs_notebook": "notebooklm",
        "needs_gws": "gws",
    }
    for key, agent_id in keyword_to_agent.items():
        if keyword_suggestions.get(key) and agent_id not in classification["dispatch"]:
            classification["dispatch"].append(agent_id)

    # Force redteam for high-risk tasks
    if classification.get("risk") == "high" and "claude-review" not in classification["dispatch"]:
        classification["dispatch"].append("claude-review")

    return classification


# ═══════════════════════════════════════════════════════
# A2A Dispatch — Call remote agents
# ═══════════════════════════════════════════════════════
async def dispatch_to_agent(agent_id: str, task: str, port: int) -> dict[str, Any]:
    """Send a task to an A2A agent service and wait for completion."""
    from apps.federation.generate_agent_cards import AGENT_PORTS

    url = f"http://localhost:{port}/"
    request_id = f"fed-{agent_id}-{datetime.now().strftime('%H%M%S')}"

    # JSON-RPC request for message/send
    rpc_request = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "message/send",
        "params": {
            "message": {
                "messageId": request_id,
                "role": "user",
                "parts": [{"kind": "text", "text": task}],
            }
        },
    }

    start = datetime.now(timezone.utc)
    try:
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(url, json=rpc_request)
            resp.raise_for_status()
            result = resp.json()
    except Exception as e:
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        logger.error("Dispatch to %s failed after %.1fs: %s", agent_id, elapsed, e)
        return {
            "agent_id": agent_id,
            "status": "failed",
            "error": str(e),
            "elapsed_s": elapsed,
        }

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()

    # Extract result text from JSON-RPC response
    output = ""
    if "result" in result:
        r = result["result"]
        # Task response
        if isinstance(r, dict):
            status = r.get("status", {})
            msg = status.get("message", {})
            parts = msg.get("parts", [])
            for p in parts:
                if p.get("kind") == "text" or "text" in p:
                    output += p.get("text", "")

            # Also check artifacts
            for artifact in r.get("artifacts", []):
                for p in artifact.get("parts", []):
                    if "text" in p:
                        output += "\n" + p["text"]

    return {
        "agent_id": agent_id,
        "status": "completed",
        "output": output.strip() or "(no output)",
        "elapsed_s": elapsed,
    }


async def dispatch_fallback(agent_id: str, task: str) -> dict[str, Any]:
    """Fallback: use ai-dispatch.sh directly (no A2A service running)."""
    from scripts.federation_capability_table import AGENTS

    agent = AGENTS.get(agent_id, {})
    dispatch_cmd = agent.get("dispatch_cmd")
    if not dispatch_cmd:
        return {
            "agent_id": agent_id,
            "status": "skipped",
            "output": f"No dispatch command for {agent_id}",
            "elapsed_s": 0,
        }

    dispatch_script = PROJECT_ROOT / "scripts" / "ai-dispatch.sh"
    start = datetime.now(timezone.utc)

    try:
        proc = await asyncio.create_subprocess_exec(
            str(dispatch_script), dispatch_cmd, task,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(PROJECT_ROOT),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=180)
        output = stdout.decode().strip()
        if proc.returncode != 0 and not output:
            output = f"[ERROR exit={proc.returncode}] {stderr.decode().strip()}"
    except asyncio.TimeoutError:
        output = f"[TIMEOUT after 180s]"
    except Exception as e:
        output = f"[ERROR] {e!s}"

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    return {
        "agent_id": agent_id,
        "status": "completed",
        "output": output or "(no output)",
        "elapsed_s": elapsed,
    }


async def dispatch_agents(agent_ids: list[str], task: str) -> list[dict[str, Any]]:
    """Dispatch to multiple agents in parallel. Try A2A first, fallback to CLI."""
    from apps.federation.generate_agent_cards import AGENT_PORTS

    async def try_agent(agent_id: str) -> dict[str, Any]:
        port = AGENT_PORTS.get(agent_id)
        if port:
            # Check if A2A service is running
            try:
                async with httpx.AsyncClient(timeout=2) as client:
                    resp = await client.get(f"http://localhost:{port}/.well-known/agent-card.json")
                    if resp.status_code == 200:
                        logger.info("Dispatching to %s via A2A (port %d)", agent_id, port)
                        return await dispatch_to_agent(agent_id, task, port)
            except Exception:
                pass

        # Fallback to direct CLI dispatch
        logger.info("Dispatching to %s via CLI fallback", agent_id)
        return await dispatch_fallback(agent_id, task)

    results = await asyncio.gather(*[try_agent(aid) for aid in agent_ids])
    return list(results)


# ═══════════════════════════════════════════════════════
# Assembly + Output
# ═══════════════════════════════════════════════════════
def assemble_context(task: str, classification: dict, results: list[dict]) -> str:
    """Assemble all results into a single context document."""
    parts = [f"# Federation Context\n\n## Task\n{task}"]

    c = classification
    parts.append(
        f"\n## Classification\n"
        f"- Type: {c.get('type')} | Risk: {c.get('risk')}\n"
        f"- Domains: {', '.join(c.get('domains', []))}\n"
        f"- Dispatched: {', '.join(c.get('dispatch', []))}"
    )

    agent_labels = {
        "gemini-search": "Web Research (Gemini Search)",
        "gemini-explore": "Codebase Analysis (Gemini Explore 1M)",
        "codex-sandbox": "Sandbox Test (Codex)",
        "claude-review": "Red Team Review (Claude Opus)",
        "notebooklm": "Knowledge Synthesis (NotebookLM)",
        "gws": "Workspace Operations (GWS)",
    }

    for r in results:
        agent_id = r["agent_id"]
        label = agent_labels.get(agent_id, agent_id)
        status = r["status"]
        elapsed = r.get("elapsed_s", 0)
        output = r.get("output", "")

        parts.append(
            f"\n## {label}\n"
            f"_Status: {status} | Time: {elapsed:.1f}s_\n\n"
            f"{output}"
        )

    return "\n\n---\n\n".join(parts)


def save_output(context: str, task: str, classification: dict) -> Path:
    """Save context to file and audit log."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    outfile = OUTPUT_DIR / f"{timestamp}-federation-v3.md"
    outfile.write_text(context)

    # Audit log
    audit_entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "task": task[:200],
        "classification": classification,
        "output_file": str(outfile.name),
        "source": "federation_orchestrator_v3",
    }
    with open(AUDIT_FILE, "a") as f:
        f.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")

    return outfile


async def send_telegram(chat_id: str, text: str) -> None:
    """Send message via @Balizerobot."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return
    if len(text) > 4000:
        text = text[:3990] + "\n...(truncated)"
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
        )


# ═══════════════════════════════════════════════════════
# Main Pipeline
# ═══════════════════════════════════════════════════════
async def run_federation(
    task: str,
    *,
    interactive: bool = True,
    telegram_chat_id: str | None = None,
) -> str:
    """Run the full federation pipeline.

    CLASSIFY → CHECKPOINT → DISPATCH (parallel) → ASSEMBLE → REVIEW (if high risk) → OUTPUT
    """
    total = ARSENAL_SUMMARY["total_capabilities"]
    print(f"\n  Federation Orchestrator v3 — ADK+A2A ({total} capabilities)")
    print(f"  Task: {task[:100]}")
    print()

    # 1. CLASSIFY
    print("  [1/5] Classifying task (Qwen 3.5:9b)...")
    classification = await classify_task(task)
    dispatch_list = classification.get("dispatch", [])

    # 2. CHECKPOINT — show routing and confirm
    print(f"\n  {'='*45}")
    print(f"  Type:     {classification.get('type')} | Risk: {classification.get('risk')}")
    print(f"  Domains:  {', '.join(classification.get('domains', []))}")
    print(f"  Dispatch: {', '.join(dispatch_list) or 'none (simple task)'}")
    print(f"  {'='*45}")

    if telegram_chat_id:
        await send_telegram(telegram_chat_id, f"🤖 Federation routing:\nDispatch: {', '.join(dispatch_list)}")

    if interactive and dispatch_list:
        confirm = input("\n  Proceed? [Y/n]: ").strip().lower()
        if confirm == "n":
            print("  Aborted.")
            sys.exit(0)

    # 3. DISPATCH — parallel execution
    results = []
    if dispatch_list:
        # Separate redteam from regular dispatch (redteam runs AFTER others)
        regular = [a for a in dispatch_list if a != "claude-review"]
        needs_review = "claude-review" in dispatch_list

        if regular:
            print(f"\n  [2/5] Dispatching {len(regular)} agents in parallel...")
            results = await dispatch_agents(regular, task)
            for r in results:
                status_icon = "✅" if r["status"] == "completed" else "❌"
                print(f"    {status_icon} {r['agent_id']}: {r['status']} ({r.get('elapsed_s', 0):.1f}s)")
        else:
            print("\n  [2/5] No regular dispatch needed.")

        # 4. ASSEMBLE
        print("\n  [3/5] Assembling context...")
        context = assemble_context(task, classification, results)

        # 5. REVIEW — conditional red team
        if needs_review:
            print("\n  [4/5] Red team review (Claude Opus)...")
            review_results = await dispatch_agents(["claude-review"], context[:3000])
            results.extend(review_results)
            context = assemble_context(task, classification, results)
            for r in review_results:
                status_icon = "✅" if r["status"] == "completed" else "❌"
                print(f"    {status_icon} {r['agent_id']}: {r['status']} ({r.get('elapsed_s', 0):.1f}s)")
        else:
            print("\n  [4/5] No red team needed (risk={}).".format(classification.get("risk", "low")))
    else:
        print("\n  [2-4/5] No dispatch needed — simple task for Claude Code.")
        context = assemble_context(task, classification, [])

    # 6. OUTPUT
    outfile = save_output(context, task, classification)
    print(f"\n  [5/5] Context saved: {outfile}")
    print(f"  Dispatched: {', '.join(dispatch_list) or 'none'}")

    if not dispatch_list:
        print("  → Proceed directly with Claude Code.")
    else:
        print("  → Paste context file into Claude Code or OpenClaw coder.")

    if telegram_chat_id:
        await send_telegram(
            telegram_chat_id,
            f"✅ *Federation v3 Complete*\n\n"
            f"Task: {task[:200]}\n"
            f"Dispatched: {', '.join(dispatch_list)}\n"
            f"File: `{outfile.name}`",
        )

    return str(outfile)


def main() -> None:
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

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    asyncio.run(
        run_federation(
            task,
            interactive=not non_interactive and not telegram_chat_id,
            telegram_chat_id=telegram_chat_id,
        )
    )


if __name__ == "__main__":
    main()
