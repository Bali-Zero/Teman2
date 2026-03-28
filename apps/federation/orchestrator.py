"""
Federation Orchestrator v3.1 — 3-tier taxonomy (agents/services/pipelines).

Architecture (v3.1, 2026-03-25):
  1. Classifier (Qwen 3.5:9b via Ollama) → classifies task type, risk, domains
  2. Deterministic routing → maps classification to agent dispatch OR orchestrator action
  3. Parallel dispatch → agents execute, orchestrator calls services directly
  4. Assembler → merges results
  5. Reviewer → optional red team (if high risk)

Key principle: Qwen classifies, deterministic rules dispatch.
  - AGENTS (7): autonomous runtimes that accept tasks → dispatchable
  - SERVICES (5): stateless tools → orchestrator calls directly via ai-dispatch.sh
  - PIPELINES (5): scheduled workflows → NOT dispatched, triggered by cron/manual

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
# v3.1: Only AGENTS are dispatchable. Services/pipelines handled by orchestrator.
CLASSIFY_PROMPT = """Classify this task. You decide TYPE, RISK, and which AGENTS to dispatch.

DISPATCHABLE AGENTS (autonomous, accept tasks):
- gemini-explore: codebase analysis across 3+ apps (1M context, read-only)
- gemini-search: Google grounded web search for regulations/market/news
- codex-sandbox: DB migration/schema changes in isolated kernel sandbox
- claude-review: pre-deploy security review, red team, architectural critique
- aider: quick single-file bug fixes and refactoring
- deepseek-reasoning: complex architecture decisions, trade-off analysis (slow, deep)

ORCHESTRATOR handles these directly (do NOT dispatch, just classify):
- CRM, compliance, pricing, portal, analytics → orchestrator uses MCP tools
- Email, WhatsApp, Telegram, Drive, Sheets → orchestrator uses gws/MCP
- Knowledge queries, NLM citations → orchestrator calls oracolo service
- Instagram carousels, content creation → orchestrator triggers pipeline
- OCR, translation, image generation → orchestrator calls service

ROUTING RULES:
1. Architecture decisions or complex debugging → deepseek-reasoning
2. Codebase exploration across 3+ apps → gemini-explore
3. Current regulations, Indonesian law, web info → gemini-search
4. DB migration or risky code changes → codex-sandbox
5. Quick single-file fix → aider
6. Pre-deploy review, security audit → claude-review
7. Everything else → orchestrator (empty dispatch list)

Pre-matched domains: {matched_domains}

Task: {task}

Respond ONLY with JSON:
{{"type":"feature|bugfix|refactor|deploy|research|reasoning|content-creation","risk":"low|medium|high","domains":[...],"dispatch":["agent-id-1"],"services":["service-needed-1"]}}}"""


# ═══════════════════════════════════════════════════════
# Classifier — Local Qwen 3.5:9b via Ollama
# ═══════════════════════════════════════════════════════
# Valid agent IDs that can be dispatched (from AGENTS tier only)
DISPATCHABLE_AGENTS = {
    "gemini-search", "gemini-explore", "codex-sandbox",
    "claude-review", "aider", "deepseek-reasoning",
}
# Note: claude-code is not dispatchable — it IS the orchestrator

# Service commands the orchestrator calls directly via ai-dispatch.sh
SERVICE_COMMANDS = {
    "oracolo", "oracolo-nb", "research", "websearch",
}


# ═══════════════════════════════════════════════════════
# Preflight SDD — Trigger detection + audit logging
# ═══════════════════════════════════════════════════════

# Objective triggers — no judgment required.
# Lower-level triggers also match if higher-level is not present.
PREFLIGHT_TRIGGERS: dict[str, list[str]] = {
    "l3": [
        "architettura", "architecture", "auth ", "billing", "rag pipeline",
        "sistema critico", "critical system", "payment", "security", "sicurezza",
        "completamente nuovo", "rethink", "riprogetta",
    ],
    "l2": [
        "refactor", "migration", "alembic", "kbli", "visa", "normativa",
        "deploy", "dependencies.py", "service_initializer", "app_factory",
        "pre-deploy", "fly.io", "monorepo", "3+ app", "tre app", "più app",
        "schema change", "schema cambia", "database schema",
    ],
    "l1": [
        "new feature", "nuova feature", "aggiungi", "add endpoint",
        "new component", "nuovo componente", "nuovo router", "new router",
        "implementa", "implement", "crea ", "create ",
    ],
}


def detect_preflight_level(task: str) -> str | None:
    """Detect if a task requires preflight and at which level (l1/l2/l3).

    Returns None if no preflight needed (trivial task).
    Checks L3 first (highest priority), then L2, then L1.
    """
    task_lower = task.lower()
    for level in ("l3", "l2", "l1"):
        for trigger in PREFLIGHT_TRIGGERS[level]:
            if trigger in task_lower:
                return level
    return None


def log_preflight_bypass(task: str, reason: str, user: str = "unknown") -> None:
    """Log any preflight bypass to the append-only audit trail."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": "preflight_bypass",
        "task": task[:200],
        "reason": reason,
        "user": user,
        "machine": os.uname().nodename,
    }
    with open(AUDIT_FILE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    logger.warning("Preflight bypass logged: task=%s reason=%s", task[:60], reason)


async def classify_task(task: str) -> dict[str, Any]:
    """Classify the task using Qwen 3.5:9b (local, $0).

    Returns classification with:
      - dispatch: list of AGENT IDs to dispatch (only real agents)
      - services: list of SERVICE commands the orchestrator should call
      - type, risk, domains: task metadata
    """
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
        classification = {
            "type": "research" if keyword_suggestions.get("needs_search") else "feature",
            "risk": "medium",
            "domains": matched or ["general"],
            "dispatch": [],
            "services": [],
        }

    # Ensure dispatch and services lists exist
    if "dispatch" not in classification:
        classification["dispatch"] = []
    if "services" not in classification:
        classification["services"] = []

    # --- Merge keyword suggestions (agents only) ---
    keyword_to_agent = {
        "needs_search": "gemini-search",
        "needs_explore": "gemini-explore",
        "needs_sandbox": "codex-sandbox",
        "needs_reasoning": "deepseek-reasoning",
        "needs_redteam": "claude-review",
        "needs_aider": "aider",
    }
    for key, agent_id in keyword_to_agent.items():
        if keyword_suggestions.get(key) and agent_id not in classification["dispatch"]:
            classification["dispatch"].append(agent_id)

    # --- Merge keyword suggestions (services) ---
    keyword_to_service = {
        "needs_oracolo": "oracolo",
        "needs_oracolo_nb": "oracolo-nb",
        "needs_websearch": "websearch",
        "needs_notebook": "oracolo",  # NLM queries go through oracolo command
    }
    for key, svc_cmd in keyword_to_service.items():
        if keyword_suggestions.get(key) and svc_cmd not in classification["services"]:
            classification["services"].append(svc_cmd)

    # --- Sanitize: remove non-agents from dispatch list ---
    # Qwen might still output service IDs in dispatch — filter them out
    classification["dispatch"] = [
        aid for aid in classification["dispatch"]
        if aid in DISPATCHABLE_AGENTS
    ]

    # Move any service IDs that Qwen put in dispatch to services
    raw_dispatch = classification.get("_raw_dispatch", classification["dispatch"])
    for aid in raw_dispatch:
        if aid in SERVICE_COMMANDS and aid not in classification["services"]:
            classification["services"].append(aid)

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
    from scripts.federation_capability_table import AGENTS, SERVICES

    # Look up in agents first, then services
    entity = AGENTS.get(agent_id) or SERVICES.get(agent_id, {})
    # Services have dispatch_cmds (list), agents have dispatch_cmd (str)
    dispatch_cmd = entity.get("dispatch_cmd")
    if not dispatch_cmd and "dispatch_cmds" in entity:
        cmds = entity["dispatch_cmds"]
        dispatch_cmd = cmds[0] if cmds else None
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
        # Agents (dispatchable)
        "gemini-search": "Web Research (Gemini Search)",
        "gemini-explore": "Codebase Analysis (Gemini Explore 1M)",
        "codex-sandbox": "Sandbox Test (Codex GPT-5.4)",
        "deepseek-reasoning": "Deep Reasoning (DeepSeek R1 671b)",
        "claude-review": "Red Team Review (Claude Opus)",
        "aider": "Quick Fix (DeepSeek V3 / Claude Sonnet)",
        # Services (called by orchestrator, shown in results if executed)
        "oracolo": "Architecture Truth (NB-1 Codebase)",
        "oracolo-nb": "Domain Knowledge (NLM notebook)",
        "websearch": "Deep Web Search (Exa/Brave)",
        "research": "Deep Research (NLM autonomous)",
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
    print(f"\n  Federation Orchestrator v3.1 — 3-tier ({total} capabilities)")
    print(f"  Task: {task[:100]}")
    print()

    # 0. PREFLIGHT CHECK — auto-detect if spec is needed first
    skip_preflight = os.environ.get("SKIP_PREFLIGHT", "").lower() in ("1", "true", "yes")
    if not skip_preflight:
        preflight_level = detect_preflight_level(task)
        if preflight_level:
            print(f"  ⚡ Preflight SDD triggered: level={preflight_level.upper()}")
            print(f"  Running preflight-{preflight_level} before implementation...")
            print(f"  (Set SKIP_PREFLIGHT=1 to bypass — will be logged in audit.jsonl)\n")
            if interactive:
                confirm = input(f"  Run preflight-{preflight_level}? [Y/n]: ").strip().lower()
                if confirm == "n":
                    reason = input("  Bypass reason (required for audit): ").strip() or "no reason given"
                    log_preflight_bypass(task, reason)
                    print("  Preflight bypassed — logged in audit.jsonl. Proceeding to standard dispatch.")
                else:
                    from apps.federation.workflows import execute_workflow
                    return str((await execute_workflow(f"preflight-{preflight_level}", task, interactive=interactive)).get("output_file", ""))
            else:
                # Non-interactive: auto-run preflight
                from apps.federation.workflows import execute_workflow
                return str((await execute_workflow(f"preflight-{preflight_level}", task, interactive=False)).get("output_file", ""))
    elif skip_preflight:
        reason = os.environ.get("SKIP_PREFLIGHT_REASON", "SKIP_PREFLIGHT env var set")
        log_preflight_bypass(task, reason)

    # 1. CLASSIFY
    print("  [1/5] Classifying task (Qwen 3.5:9b)...")
    classification = await classify_task(task)
    dispatch_list = classification.get("dispatch", [])
    service_list = classification.get("services", [])

    # 2. CHECKPOINT — show routing and confirm
    print(f"\n  {'='*50}")
    print(f"  Type:     {classification.get('type')} | Risk: {classification.get('risk')}")
    print(f"  Domains:  {', '.join(classification.get('domains', []))}")
    print(f"  Agents:   {', '.join(dispatch_list) or 'none (orchestrator handles)'}")
    if service_list:
        print(f"  Services: {', '.join(service_list)}")
    print(f"  {'='*50}")

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
