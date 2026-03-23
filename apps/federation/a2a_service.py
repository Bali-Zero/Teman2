"""
A2A Service — Wraps CLI agents as A2A-compatible services.

Each agent runs as a FastAPI server exposing:
  - GET  /.well-known/agent.json  → Agent Card
  - POST /                        → JSON-RPC endpoint (task/send, task/get, etc.)

Usage:
  python -m apps.federation.a2a_service --agent gemini-search --port 8082
  python -m apps.federation.a2a_service --agent notebooklm --port 8087
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

import uvicorn
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps.jsonrpc import A2AFastAPIApplication
from a2a.server.events import EventQueue, InMemoryQueueManager
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCard,
    Artifact,
    Message,
    Part,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
)

logger = logging.getLogger("federation.a2a_service")

# ═══════════════════════════════════════════════════════
# CLI dispatch commands per agent
# ═══════════════════════════════════════════════════════
AGENT_CLI_COMMANDS: dict[str, dict[str, Any]] = {
    "gemini-search": {
        "cmd_template": ["gemini", "-p", "{prompt}", "--sandbox", "--approval-mode", "plan"],
        "timeout": 120,
        "stream": True,
    },
    "gemini-explore": {
        "cmd_template": ["gemini", "-p", "{prompt}", "--sandbox", "--approval-mode", "plan"],
        "timeout": 180,
        "stream": True,
    },
    "codex-sandbox": {
        "cmd_template": [
            "bash", "-c",
            "cd /Users/nuzantara/Desktop/nuzantara && ./scripts/ai-dispatch.sh sandbox \"{prompt}\"",
        ],
        "timeout": 180,
        "stream": False,
    },
    "claude-review": {
        "cmd_template": [
            "bash", "-c",
            "cd /Users/nuzantara/Desktop/nuzantara && ./scripts/ai-dispatch.sh claude-redteam \"{prompt}\"",
        ],
        "timeout": 120,
        "stream": True,
    },
    "aider": {
        "cmd_template": [
            "bash", "-c",
            "cd /Users/nuzantara/Desktop/nuzantara && ./scripts/ai-dispatch.sh aider-fix \"{prompt}\"",
        ],
        "timeout": 120,
        "stream": False,
    },
    "notebooklm": {
        "cmd_template": [
            "bash", "-c",
            "cd /Users/nuzantara/Desktop/nuzantara && ./scripts/ai-dispatch.sh nlm-query \"{prompt}\"",
        ],
        "timeout": 60,
        "stream": False,
    },
    "gws": {
        "cmd_template": ["gws", "{prompt}"],
        "timeout": 60,
        "stream": False,
    },
    # claude-code is special — it IS the orchestrator, not a service
    "claude-code": {
        "cmd_template": ["claude", "-p", "{prompt}", "--allowedTools", "Read,Grep,Glob,Bash"],
        "timeout": 300,
        "stream": True,
    },
    # Air batch agent — runs slow tasks (intel pipeline, bulk processing)
    "air-batch": {
        "cmd_template": [
            "bash", "-c",
            "cd /Users/nuzantara/Desktop/nuzantara && ./scripts/ai-dispatch.sh explore \"{prompt}\"",
        ],
        "timeout": 300,
        "stream": False,
    },
    # ═══════════════════════════════════════════════════════
    # War Room agents (ports 8100-8106, Pro only)
    # Ports start at 8100 to avoid conflict with air-batch (8091)
    # ═══════════════════════════════════════════════════════
    "war-room-topic": {
        "cmd_template": [
            "bash", "-c",
            "cd /Users/nuzantara/Desktop/nuzantara/apps/war-room && "
            "source .venv/bin/activate 2>/dev/null; "
            "python agents/00_topic_selector.py "
            "--intel $HOME/Desktop/nuzantara/apps/bali-intel-scraper/data/intel_output_latest.json "
            "--hint \"{prompt}\" "
            "--output output/strategy/selected_topic.json 2>&1 && "
            "cat output/strategy/selected_topic.json",
        ],
        "timeout": 240,
        "stream": False,
    },
    "war-room-researcher": {
        "cmd_template": [
            "bash", "-c",
            "cd /Users/nuzantara/Desktop/nuzantara/apps/war-room && "
            "source .venv/bin/activate 2>/dev/null; "
            "python agents/01_chatgpt_researcher.py --topic \"{prompt}\" "
            "--output output/raw/chatgpt_dump.json 2>&1 & "
            "python agents/09_exa_researcher.py --topic \"{prompt}\" "
            "--output output/raw/exa_dump.json 2>&1 & "
            "wait && "
            "python -c '"
            "import json; from pathlib import Path; "
            "sources = [Path(\"output/raw/chatgpt_dump.json\"), Path(\"output/raw/exa_dump.json\")]; "
            "merged = {\"facts\": [], \"merged\": True}; "
            "[merged[\"facts\"].extend(json.loads(s.read_text()).get(\"facts\",[])) for s in sources if s.exists()]; "
            "Path(\"output/raw/merged_dump.json\").write_text(json.dumps(merged))' && "
            "python agents/015_qwen_preprocessor.py "
            "--research output/raw/merged_dump.json "
            "--output output/raw/processed_dump.json 2>&1 && "
            "cat output/raw/processed_dump.json",
        ],
        "timeout": 600,
        "stream": False,
    },
    "war-room-strategist": {
        "cmd_template": [
            "bash", "-c",
            "cd /Users/nuzantara/Desktop/nuzantara/apps/war-room && "
            "source .venv/bin/activate 2>/dev/null; "
            "python agents/03_gemini_strategist.py "
            "--dump output/raw/processed_dump.json "
            "--topic \"{prompt}\" "
            "--output output/strategy/gemini_concepts.json 2>&1 && "
            "cat output/strategy/gemini_concepts.json",
        ],
        "timeout": 600,
        "stream": False,
    },
    "war-room-director": {
        "cmd_template": [
            "bash", "-c",
            "cd /Users/nuzantara/Desktop/nuzantara/apps/war-room && "
            "source .venv/bin/activate 2>/dev/null; "
            "python agents/04_claude_director.py "
            "--concepts output/strategy/gemini_concepts.json "
            "--topic \"{prompt}\" "
            "--output output/strategy/claude_slides.json 2>&1 && "
            "cat output/strategy/claude_slides.json",
        ],
        "timeout": 600,
        "stream": False,
    },
    "war-room-image-gen": {
        "cmd_template": [
            "bash", "-c",
            "cd /Users/nuzantara/Desktop/nuzantara/apps/war-room && "
            "source .venv/bin/activate 2>/dev/null; "
            "python agents/05_gemini_images.py "
            "--slides output/strategy/claude_slides.json "
            "--output output/images/ "
            "--cdp http://localhost:9222 2>&1 && "
            "cat output/images/manifest.json",
        ],
        "timeout": 300,
        "stream": False,
    },
    "war-room-canva": {
        "cmd_template": [
            "bash", "-c",
            "cd /Users/nuzantara/Desktop/nuzantara/apps/war-room && "
            "source .venv/bin/activate 2>/dev/null; "
            "python agents/06_canva_builder.py "
            "--slides output/strategy/claude_slides.json "
            "--output output/canva/ "
            "--master output/master/ "
            "--design-id DAHEME4mocU "
            "--row all --page 1 2>&1 && "
            "cat output/canva/canva_pending.json",
        ],
        "timeout": 120,
        "stream": False,
    },
    "war-room-delivery": {
        "cmd_template": [
            "bash", "-c",
            "cd /Users/nuzantara/Desktop/nuzantara/apps/war-room && "
            "bash agents/07_delivery.sh --topic \"{prompt}\" 2>&1",
        ],
        "timeout": 120,
        "stream": False,
    },
}


class CLIAgentExecutor(AgentExecutor):
    """Wraps a CLI tool as an A2A AgentExecutor.

    Executes the CLI command as a subprocess, captures output,
    and publishes results to the A2A event queue.

    Special handling for notebooklm: health check before dispatch,
    graceful retry (2x), fallback to Qdrant RAG via recall_similar MCP tool.
    """

    NLM_HEALTH_RETRIES = 2
    NLM_FALLBACK_CMD = [
        "bash", "-c",
        'cd /Users/nuzantara/Desktop/nuzantara && '
        'source apps/backend-rag/.venv/bin/activate && '
        'python -c "'
        "import asyncio, json, httpx; "
        "r = asyncio.run(httpx.AsyncClient(timeout=30).post("
        "'http://localhost:8000/api/rag/recall', "
        "json={{'query': '{prompt}', 'collection': 'knowledge_base', 'limit': 5}}"
        ")); print(r.text)"
        '"'
    ]

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.config = AGENT_CLI_COMMANDS[agent_id]
        self._running_processes: dict[str, asyncio.subprocess.Process] = {}

    def _build_command(self, prompt: str) -> list[str]:
        """Build the CLI command from template + prompt."""
        cmd = []
        for part in self.config["cmd_template"]:
            cmd.append(part.replace("{prompt}", prompt))
        return cmd

    def _extract_prompt(self, context: RequestContext) -> str:
        """Extract text prompt from the A2A request context."""
        if context.message and context.message.parts:
            text_parts = []
            for part in context.message.parts:
                if hasattr(part, "root") and hasattr(part.root, "text"):
                    text_parts.append(part.root.text)
                elif hasattr(part, "text"):
                    text_parts.append(part.text)
            return " ".join(text_parts) if text_parts else ""
        return ""

    async def _nlm_health_check(self) -> bool:
        """Check if NotebookLM is authenticated and responsive.

        Uses nlm_auth_bridge for proper auth validation + auto re-login,
        falls back to simple CLI ping if bridge unavailable.
        """
        try:
            from apps.federation.nlm_auth_bridge import ensure_nlm_auth
            return await ensure_nlm_auth()
        except ImportError:
            # Fallback to simple ping if bridge not available
            try:
                proc = await asyncio.create_subprocess_exec(
                    "nlm", "login", "--check",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
                output = (stdout.decode() + stderr.decode())
                return "Authentication valid" in output or "✓" in output
            except Exception:
                return False

    async def _nlm_fallback(self, prompt: str) -> str:
        """Fallback: query Qdrant RAG via recall_similar when NLM is down."""
        logger.info("NLM fallback: querying Qdrant RAG for: %s", prompt[:80])
        fallback_cmd = [p.replace("{prompt}", prompt.replace('"', '\\"')) for p in self.NLM_FALLBACK_CMD]
        try:
            proc = await asyncio.create_subprocess_exec(
                *fallback_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            output = stdout.decode("utf-8", errors="replace").strip()
            if output:
                return f"[Qdrant RAG fallback — NotebookLM unavailable]\n\n{output}"
            return "[Qdrant RAG fallback returned no results]"
        except Exception as e:
            return f"[Both NotebookLM and Qdrant RAG fallback failed: {e}]"

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        """Execute the CLI agent and publish results.

        For notebooklm: health check → retry 2x → fallback to Qdrant RAG.
        """
        prompt = self._extract_prompt(context)
        if not prompt:
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=context.task_id,
                    context_id=context.context_id,
                    final=True,
                    status=TaskStatus(
                        state=TaskState.failed,
                        message=Message(
                            role="agent",
                            parts=[Part(TextPart(text="No prompt provided"))],
                        ),
                    ),
                )
            )
            return

        cmd = self._build_command(prompt)
        timeout = self.config["timeout"]

        # ── NLM special handling: health check + retry + fallback ──
        if self.agent_id == "notebooklm":
            nlm_healthy = await self._nlm_health_check()
            if not nlm_healthy:
                logger.warning("NotebookLM health check failed, attempting retry...")
                for attempt in range(self.NLM_HEALTH_RETRIES):
                    await asyncio.sleep(2)
                    nlm_healthy = await self._nlm_health_check()
                    if nlm_healthy:
                        logger.info("NotebookLM recovered on retry %d", attempt + 1)
                        break

            if not nlm_healthy:
                logger.warning("NotebookLM unavailable after %d retries, falling back to Qdrant RAG", self.NLM_HEALTH_RETRIES)
                fallback_result = await self._nlm_fallback(prompt)

                await event_queue.enqueue_event(
                    Artifact(
                        artifact_id=f"{context.task_id}-result",
                        parts=[Part(TextPart(text=fallback_result))],
                        name=f"{self.agent_id}_fallback_output",
                    )
                )
                await event_queue.enqueue_event(
                    TaskStatusUpdateEvent(
                        task_id=context.task_id,
                        context_id=context.context_id,
                        final=True,
                        status=TaskStatus(
                            state=TaskState.completed,
                            message=Message(
                                role="agent",
                                parts=[Part(TextPart(text=fallback_result[:500]))],
                            ),
                        ),
                    )
                )
                return

        # Signal: working
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                final=False,
                status=TaskStatus(
                    state=TaskState.working,
                    message=Message(
                        role="agent",
                        parts=[Part(TextPart(text=f"Executing {self.agent_id}..."))],
                    ),
                ),
            )
        )

        try:
            logger.info("Executing: %s (timeout=%ds)", " ".join(cmd[:3]) + "...", timeout)
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._running_processes[context.task_id] = process

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                await event_queue.enqueue_event(
                    TaskStatusUpdateEvent(
                        task_id=context.task_id,
                        context_id=context.context_id,
                        final=True,
                        status=TaskStatus(
                            state=TaskState.failed,
                            message=Message(
                                role="agent",
                                parts=[Part(TextPart(text=f"Timeout after {timeout}s"))],
                            ),
                        ),
                    )
                )
                return
            finally:
                self._running_processes.pop(context.task_id, None)

            output = stdout.decode("utf-8", errors="replace").strip()
            error = stderr.decode("utf-8", errors="replace").strip()

            if process.returncode != 0:
                error_msg = error or output or f"Exit code {process.returncode}"
                await event_queue.enqueue_event(
                    TaskStatusUpdateEvent(
                        task_id=context.task_id,
                        context_id=context.context_id,
                        final=True,
                        status=TaskStatus(
                            state=TaskState.failed,
                            message=Message(
                                role="agent",
                                parts=[Part(TextPart(text=f"Error: {error_msg[:2000]}"))],
                            ),
                        ),
                    )
                )
                return

            # Success — publish result as artifact + completed status
            result_text = output if output else "(no output)"

            # Publish artifact
            await event_queue.enqueue_event(
                Artifact(
                    artifact_id=f"{context.task_id}-result",
                    parts=[Part(TextPart(text=result_text))],
                    name=f"{self.agent_id}_output",
                )
            )

            # Signal: completed
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=context.task_id,
                    context_id=context.context_id,
                    final=True,
                    status=TaskStatus(
                        state=TaskState.completed,
                        message=Message(
                            role="agent",
                            parts=[Part(TextPart(text=result_text[:500]))],
                        ),
                    ),
                )
            )

        except Exception as e:
            logger.exception("Agent execution failed: %s", e)
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=context.task_id,
                    context_id=context.context_id,
                    final=True,
                    status=TaskStatus(
                        state=TaskState.failed,
                        message=Message(
                            role="agent",
                            parts=[Part(TextPart(text=f"Execution error: {e!s}"))],
                        ),
                    ),
                )
            )

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        """Cancel a running CLI process."""
        process = self._running_processes.get(context.task_id)
        if process:
            process.kill()
            await process.wait()
            self._running_processes.pop(context.task_id, None)

        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                final=True,
                status=TaskStatus(
                    state=TaskState.canceled,
                    message=Message(
                        role="agent",
                        parts=[Part(TextPart(text="Task canceled"))],
                    ),
                ),
            )
        )


def load_agent_card(agent_id: str) -> AgentCard:
    """Load an agent card from the generated JSON file."""
    card_path = Path(__file__).parent / "agents" / agent_id / "agent_card.json"
    if not card_path.exists():
        raise FileNotFoundError(f"Agent card not found: {card_path}")
    with open(card_path) as f:
        data = json.load(f)
    return AgentCard(**data)


def create_a2a_app(agent_id: str) -> A2AFastAPIApplication:
    """Create a complete A2A FastAPI application for an agent."""
    agent_card = load_agent_card(agent_id)
    executor = CLIAgentExecutor(agent_id)
    task_store = InMemoryTaskStore()

    handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=task_store,
    )

    a2a_app = A2AFastAPIApplication(
        agent_card=agent_card,
        http_handler=handler,
    )

    return a2a_app


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run a federation agent as an A2A service")
    parser.add_argument("--agent", required=True, choices=list(AGENT_CLI_COMMANDS.keys()))
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    # Import port allocation
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from apps.federation.generate_agent_cards import AGENT_PORTS

    port = args.port or AGENT_PORTS.get(args.agent, 8080)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    logger.info("Starting A2A service: %s on port %d", args.agent, port)

    a2a_application = create_a2a_app(args.agent)
    app = a2a_application.build(title=f"Federation Agent: {args.agent}")

    uvicorn.run(app, host=args.host, port=port)


if __name__ == "__main__":
    main()
