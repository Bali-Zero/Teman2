"""
Federation ADK Agents — Native Google ADK BaseAgent subclasses.

Replaces the async function-based orchestrator with composable ADK agents:
  - ClassifierAgent: Qwen 3.5:9b local classification via Ollama
  - DispatcherAgent: Parallel dispatch to A2A services via RemoteA2aAgent
  - AssemblerAgent: Merge results from multiple agents into context document
  - ReviewerAgent: Conditional red team review (only if high risk)
  - FederationPipeline: Root SequentialAgent composing the full pipeline

Usage:
  from apps.federation.adk_agents import create_federation_pipeline
  pipeline = create_federation_pipeline()
  # Run via ADK runner or directly
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

import httpx
from google.adk.agents import BaseAgent, SequentialAgent, ParallelAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types as genai_types

from apps.federation.discovery import AGENT_REGISTRY, get_agent_url

logger = logging.getLogger("federation.adk_agents")

# ═══════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLASSIFIER_MODEL = "qwen3.5:9b"
OLLAMA_URL = "http://localhost:11434"

CLASSIFY_PROMPT = """Route this task. Available agents:
- gemini-search: regulations/KBLI/visa/tax/market research (web search)
- gemini-explore: codebase analysis across 3+ apps (1M context)
- codex-sandbox: DB migration/schema changes (isolated sandbox)
- claude-review: pre-deploy security/logic review (red team)
- notebooklm: multi-document synthesis/research (citations)
- gws: Google Workspace operations (email/calendar/drive/sheets)
- war-room-pipeline: Instagram carousel content creation for Bali Zero (topic, research, slides, images, Canva)

Pre-matched domains: {matched_domains}

Task: {task}

Respond ONLY with JSON, no other text:
{{"type":"feature|bugfix|refactor|deploy|research|conversation|content-creation","risk":"low|medium|high","domains":[...],
"dispatch":[list of agent IDs to dispatch, e.g. "gemini-search","codex-sandbox"]}}"""


# ═══════════════════════════════════════════════════════
# ClassifierAgent — Local Qwen 3.5:9b via Ollama
# ═══════════════════════════════════════════════════════
class ClassifierAgent(BaseAgent):
    """Classifies tasks using Qwen 3.5:9b (local, $0).

    Writes classification result to session state under key 'classification'.
    Falls back to keyword matching if Qwen is unavailable.
    """

    model_config = {"arbitrary_types_allowed": True}

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        # Import capability table functions
        from scripts.federation_capability_table import (
            match_domains,
            suggest_agents,
        )

        # Get task from session state or last user message
        task = ctx.session.state.get("task", "")
        if not task and ctx.session.events:
            for event in reversed(ctx.session.events):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            task = part.text
                            break
                    if task:
                        break

        if not task:
            yield Event(
                author=self.name,
                content=genai_types.Content(
                    parts=[genai_types.Part(text="No task provided for classification")]
                ),
                invocation_id=ctx.invocation_id,
                branch=ctx.branch,
            )
            return

        matched = match_domains(task)
        keyword_suggestions = suggest_agents(task)

        prompt = CLASSIFY_PROMPT.format(
            task=task,
            matched_domains=", ".join(matched) if matched else "none detected",
        )

        classification = await self._call_qwen(prompt, keyword_suggestions, matched)

        # Merge keyword suggestions
        keyword_to_agent = {
            "needs_search": "gemini-search",
            "needs_explore": "gemini-explore",
            "needs_sandbox": "codex-sandbox",
            "needs_redteam": "claude-review",
            "needs_notebook": "notebooklm",
            "needs_gws": "gws",
            "needs_war_room": "war-room-pipeline",
        }
        for key, agent_id in keyword_to_agent.items():
            if keyword_suggestions.get(key) and agent_id not in classification.get("dispatch", []):
                classification.setdefault("dispatch", []).append(agent_id)

        # Force redteam for high-risk
        if classification.get("risk") == "high" and "claude-review" not in classification.get("dispatch", []):
            classification["dispatch"].append("claude-review")

        # Store in session state for downstream agents
        ctx.session.state["classification"] = classification
        ctx.session.state["task"] = task

        yield Event(
            author=self.name,
            content=genai_types.Content(
                parts=[genai_types.Part(text=json.dumps(classification, indent=2))]
            ),
            invocation_id=ctx.invocation_id,
            branch=ctx.branch,
        )

    async def _call_qwen(
        self, prompt: str, keyword_suggestions: dict, matched: list
    ) -> dict[str, Any]:
        """Call Qwen 3.5:9b via Ollama for classification."""
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{OLLAMA_URL}/api/chat",
                    json={
                        "model": CLASSIFIER_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                        "options": {"temperature": 0.1, "num_predict": 300},
                        "think": False,
                        "keep_alive": "30m",
                    },
                )
                resp.raise_for_status()
                raw = resp.json()["message"]["content"].strip()

            if "<think>" in raw:
                raw = raw.split("</think>")[-1].strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            return json.loads(raw)
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
            if keyword_suggestions.get("needs_war_room"):
                dispatch.append("war-room-pipeline")

            return {
                "type": "content-creation" if keyword_suggestions.get("needs_war_room") else "research" if keyword_suggestions.get("needs_search") else "feature",
                "risk": "medium",
                "domains": matched or ["general"],
                "dispatch": dispatch,
            }


# ═══════════════════════════════════════════════════════
# DispatcherAgent — Parallel dispatch to A2A or CLI
# ═══════════════════════════════════════════════════════
class DispatcherAgent(BaseAgent):
    """Dispatches tasks to federation agents (A2A HTTP or CLI fallback).

    Reads classification from session state, dispatches to listed agents
    in parallel, stores results in session state under 'dispatch_results'.
    """

    model_config = {"arbitrary_types_allowed": True}

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        classification = ctx.session.state.get("classification", {})
        task = ctx.session.state.get("task", "")
        dispatch_list = classification.get("dispatch", [])

        if not dispatch_list:
            ctx.session.state["dispatch_results"] = []
            yield Event(
                author=self.name,
                content=genai_types.Content(
                    parts=[genai_types.Part(text="No agents to dispatch — simple task for Claude Code.")]
                ),
                invocation_id=ctx.invocation_id,
                branch=ctx.branch,
            )
            return

        # Separate redteam (runs after other agents via ReviewerAgent)
        regular = [a for a in dispatch_list if a != "claude-review"]

        if not regular:
            ctx.session.state["dispatch_results"] = []
            yield Event(
                author=self.name,
                content=genai_types.Content(
                    parts=[genai_types.Part(text="Only red team review needed — handled by ReviewerAgent.")]
                ),
                invocation_id=ctx.invocation_id,
                branch=ctx.branch,
            )
            return

        # Dispatch in parallel
        from apps.federation.orchestrator import dispatch_agents
        results = await dispatch_agents(regular, task)

        ctx.session.state["dispatch_results"] = results

        summary_parts = []
        for r in results:
            icon = "✅" if r["status"] == "completed" else "❌"
            summary_parts.append(f"{icon} {r['agent_id']}: {r['status']} ({r.get('elapsed_s', 0):.1f}s)")

        yield Event(
            author=self.name,
            content=genai_types.Content(
                parts=[genai_types.Part(text=f"Dispatched {len(regular)} agents:\n" + "\n".join(summary_parts))]
            ),
            invocation_id=ctx.invocation_id,
            branch=ctx.branch,
        )


# ═══════════════════════════════════════════════════════
# AssemblerAgent — Merge results into context document
# ═══════════════════════════════════════════════════════
class AssemblerAgent(BaseAgent):
    """Assembles dispatch results into a unified context document.

    Reads dispatch_results from session state, produces assembled context,
    stores it in session state under 'assembled_context'.
    """

    model_config = {"arbitrary_types_allowed": True}

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        from apps.federation.orchestrator import assemble_context

        task = ctx.session.state.get("task", "")
        classification = ctx.session.state.get("classification", {})
        results = ctx.session.state.get("dispatch_results", [])

        context = assemble_context(task, classification, results)
        ctx.session.state["assembled_context"] = context

        yield Event(
            author=self.name,
            content=genai_types.Content(
                parts=[genai_types.Part(
                    text=f"Assembled context from {len(results)} agent(s) ({len(context)} chars)"
                )]
            ),
            invocation_id=ctx.invocation_id,
            branch=ctx.branch,
        )


# ═══════════════════════════════════════════════════════
# ReviewerAgent — Conditional red team review
# ═══════════════════════════════════════════════════════
class ReviewerAgent(BaseAgent):
    """Conditional red team review — only runs if classification.risk == 'high'
    or 'claude-review' is in the dispatch list.

    Reads assembled_context from session state, dispatches to claude-review,
    updates assembled_context with review results.
    """

    model_config = {"arbitrary_types_allowed": True}

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        classification = ctx.session.state.get("classification", {})
        dispatch_list = classification.get("dispatch", [])
        needs_review = "claude-review" in dispatch_list

        if not needs_review:
            yield Event(
                author=self.name,
                content=genai_types.Content(
                    parts=[genai_types.Part(
                        text=f"No red team needed (risk={classification.get('risk', 'low')})"
                    )]
                ),
                invocation_id=ctx.invocation_id,
                branch=ctx.branch,
            )
            return

        context = ctx.session.state.get("assembled_context", "")
        from apps.federation.orchestrator import dispatch_agents, assemble_context

        review_results = await dispatch_agents(["claude-review"], context[:3000])

        # Merge review into dispatch results and reassemble
        all_results = ctx.session.state.get("dispatch_results", []) + review_results
        ctx.session.state["dispatch_results"] = all_results

        task = ctx.session.state.get("task", "")
        updated_context = assemble_context(task, classification, all_results)
        ctx.session.state["assembled_context"] = updated_context

        review_status = review_results[0].get("status", "unknown") if review_results else "skipped"
        yield Event(
            author=self.name,
            content=genai_types.Content(
                parts=[genai_types.Part(text=f"Red team review: {review_status}")]
            ),
            invocation_id=ctx.invocation_id,
            branch=ctx.branch,
        )


# ═══════════════════════════════════════════════════════
# OutputAgent — Save results and notify
# ═══════════════════════════════════════════════════════
class OutputAgent(BaseAgent):
    """Saves assembled context to file and optional Telegram notification."""

    model_config = {"arbitrary_types_allowed": True}

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        from apps.federation.orchestrator import save_output

        task = ctx.session.state.get("task", "")
        classification = ctx.session.state.get("classification", {})
        context = ctx.session.state.get("assembled_context", "")

        if not context:
            context = f"# No dispatch results\n\nTask: {task}\nClassification: {json.dumps(classification)}"

        outfile = save_output(context, task, classification)
        ctx.session.state["output_file"] = str(outfile)

        yield Event(
            author=self.name,
            content=genai_types.Content(
                parts=[genai_types.Part(text=f"Context saved: {outfile}")]
            ),
            invocation_id=ctx.invocation_id,
            branch=ctx.branch,
        )


# ═══════════════════════════════════════════════════════
# Pipeline Factory
# ═══════════════════════════════════════════════════════
def create_federation_pipeline() -> SequentialAgent:
    """Create the full Federation v3 pipeline as a SequentialAgent.

    Pipeline: Classify → Dispatch → Assemble → Review → Output
    """
    classifier = ClassifierAgent(
        name="classifier",
        description="Classify task using Qwen 3.5:9b and keyword matching",
    )

    dispatcher = DispatcherAgent(
        name="dispatcher",
        description="Dispatch to federation agents via A2A or CLI fallback",
    )

    assembler = AssemblerAgent(
        name="assembler",
        description="Assemble dispatch results into unified context",
    )

    reviewer = ReviewerAgent(
        name="reviewer",
        description="Conditional red team review for high-risk tasks",
    )

    output = OutputAgent(
        name="output",
        description="Save context to file and audit log",
    )

    pipeline = SequentialAgent(
        name="federation_pipeline",
        description="Federation v3 orchestration pipeline: classify → dispatch → assemble → review → output",
        sub_agents=[classifier, dispatcher, assembler, reviewer, output],
    )

    return pipeline


# ═══════════════════════════════════════════════════════
# Standalone runner (for CLI usage)
# ═══════════════════════════════════════════════════════
async def run_pipeline(task: str) -> str:
    """Run the federation pipeline directly (without ADK Runner).

    Returns the output file path.
    """
    from google.adk.sessions import InMemorySessionService
    from google.adk.runners import Runner

    pipeline = create_federation_pipeline()

    session_service = InMemorySessionService()
    runner = Runner(
        agent=pipeline,
        app_name="federation_v3",
        session_service=session_service,
    )

    session = await session_service.create_session(
        app_name="federation_v3",
        user_id="orchestrator",
        state={"task": task},
    )

    user_content = genai_types.Content(
        parts=[genai_types.Part(text=task)]
    )

    events = []
    async for event in runner.run_async(
        user_id="orchestrator",
        session_id=session.id,
        new_message=user_content,
    ):
        events.append(event)
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    logger.info("[%s] %s", event.author, part.text[:200])

    # Get output file from session state
    updated_session = await session_service.get_session(
        app_name="federation_v3",
        user_id="orchestrator",
        session_id=session.id,
    )
    return updated_session.state.get("output_file", "")


def main() -> None:
    import sys

    args = sys.argv[1:]
    if "--no-confirm" in args:
        args.remove("--no-confirm")

    task = " ".join(args) if args else input("Task: ")
    if not task.strip():
        print("Error: empty task")
        sys.exit(1)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    from scripts.federation_capability_table import ARSENAL_SUMMARY
    total = ARSENAL_SUMMARY["total_capabilities"]
    print(f"\n  Federation Pipeline v3 — ADK Native ({total} capabilities)")
    print(f"  Task: {task[:100]}")
    print()

    result = asyncio.run(run_pipeline(task))
    if result:
        print(f"\n  ✅ Output: {result}")
    else:
        print("\n  ⚠️ Pipeline completed but no output file generated")


if __name__ == "__main__":
    main()
