"""
Consiglio v1 — Agent adapters.

Protocol-based adapters wrapping CLI subprocess calls for each LLM runtime.
Uses asyncio.to_thread() to parallelize blocking subprocess calls,
following the pattern from cell/actor.py:49.

Runtimes:
- Claude CLI (--print) via CLIRuntime multi-account fallback
- Gemini CLI (--prompt) via CLIRuntime
- DeepSeek API via curl subprocess (ONLY HTTP API exception per SYMBIOSIS Law 1)
- Ollama local via subprocess
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import time
from typing import Optional, Protocol, runtime_checkable

from mata_garuda.council.models import AgentVote, Topic
from mata_garuda.council.prompts import COUNCIL_AGENT_PROMPT
from mata_garuda.runtime.cli_runtime import CLIRuntime

logger = logging.getLogger("mata_garuda.council.agents")

# Council-specific timeout (faster than default 300s)
COUNCIL_AGENT_TIMEOUT = 120


def _format_agent_prompt(topic: Topic) -> str:
    """Build the deliberation prompt from a Topic."""
    constraints = ", ".join(topic.constraints) if topic.constraints else "None"
    return COUNCIL_AGENT_PROMPT.format(
        topic_title=topic.title,
        topic_description=topic.description,
        topic_category=topic.category,
        constraints=constraints,
    )


def _parse_vote_json(raw: str) -> dict:
    """Extract JSON from LLM output, tolerating markdown fences."""
    # Try direct parse first
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try extracting from ```json ... ``` blocks
    match = re.search(r"```(?:json)?\s*\n?(\{.*?\})\s*\n?```", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding the first { ... } block
    match = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return {}


def _build_vote(agent_name: str, runtime: str, parsed: dict,
                elapsed: float, success: bool, error: str = "") -> AgentVote:
    """Build an AgentVote from parsed JSON output."""
    return AgentVote(
        agent_name=agent_name,
        runtime=runtime,
        position=parsed.get("position", ""),
        confidence=float(parsed.get("confidence", 0.5)),
        key_arguments=parsed.get("key_arguments", []),
        risks_identified=parsed.get("risks_identified", []),
        elapsed_seconds=round(elapsed, 2),
        success=success,
        error=error,
    )


@runtime_checkable
class CouncilAgent(Protocol):
    """Protocol for council agent adapters."""

    name: str
    runtime: str

    async def deliberate(self, topic: Topic) -> AgentVote: ...


class ClaudeAdapter:
    """Claude CLI adapter using CLIRuntime multi-account fallback."""

    name: str = "claude"
    runtime: str = "claude_cli"

    def __init__(self, timeout: int = COUNCIL_AGENT_TIMEOUT):
        self._cli = CLIRuntime(model="claude", timeout=timeout)

    async def deliberate(self, topic: Topic) -> AgentVote:
        prompt = _format_agent_prompt(topic)
        try:
            result = await asyncio.to_thread(self._cli.invoke, prompt)
            parsed = _parse_vote_json(result.output)
            return _build_vote(
                self.name, self.runtime, parsed,
                result.elapsed_seconds, result.success,
                error=result.stderr[:200] if not result.success else "",
            )
        except Exception as e:
            logger.error(f"[ClaudeAdapter] failed: {e}")
            return AgentVote(
                agent_name=self.name, runtime=self.runtime,
                success=False, error=str(e)[:200],
            )


class GeminiAdapter:
    """Gemini CLI adapter."""

    name: str = "gemini"
    runtime: str = "gemini_cli"

    def __init__(self, timeout: int = COUNCIL_AGENT_TIMEOUT):
        self._cli = CLIRuntime(model="gemini", timeout=timeout)

    async def deliberate(self, topic: Topic) -> AgentVote:
        prompt = _format_agent_prompt(topic)
        try:
            result = await asyncio.to_thread(self._cli.invoke, prompt)
            parsed = _parse_vote_json(result.output)
            return _build_vote(
                self.name, self.runtime, parsed,
                result.elapsed_seconds, result.success,
                error=result.stderr[:200] if not result.success else "",
            )
        except Exception as e:
            logger.error(f"[GeminiAdapter] failed: {e}")
            return AgentVote(
                agent_name=self.name, runtime=self.runtime,
                success=False, error=str(e)[:200],
            )


class DeepSeekAdapter:
    """DeepSeek API adapter via curl subprocess.

    DeepSeek API is the ONLY HTTP API exception per SYMBIOSIS Law 1.
    Uses subprocess curl (not httpx/requests) to match mata-garuda zero-dep constraint.
    Pattern: bridge/nerve.py _default_http_post().
    """

    name: str = "deepseek"
    runtime: str = "deepseek_api"

    def __init__(
        self,
        timeout: int = COUNCIL_AGENT_TIMEOUT,
        model: str = "deepseek-reasoner",
        api_key_env: str = "DEEPSEEK_API_KEY",
    ):
        self._timeout = timeout
        self._model = model
        self._api_key_env = api_key_env

    async def deliberate(self, topic: Topic) -> AgentVote:
        prompt = _format_agent_prompt(topic)
        try:
            result = await asyncio.to_thread(self._call_api, prompt)
            parsed = _parse_vote_json(result)
            return _build_vote(
                self.name, self.runtime, parsed,
                0.0, bool(result), error="" if result else "empty response",
            )
        except Exception as e:
            logger.error(f"[DeepSeekAdapter] failed: {e}")
            return AgentVote(
                agent_name=self.name, runtime=self.runtime,
                success=False, error=str(e)[:200],
            )

    def _call_api(self, prompt: str) -> str:
        """Call DeepSeek API via curl subprocess."""
        api_key = os.environ.get(self._api_key_env, "")
        if not api_key:
            raise ValueError(f"{self._api_key_env} not set")

        payload = json.dumps({
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 1024,
        })

        start = time.monotonic()
        result = subprocess.run(
            [
                "curl", "-sS",
                "--max-time", str(self._timeout),
                "-X", "POST",
                "https://api.deepseek.com/chat/completions",
                "-H", "Content-Type: application/json",
                "-H", f"Authorization: Bearer {api_key}",
                "-d", payload,
            ],
            capture_output=True, text=True,
            timeout=self._timeout + 10,
        )
        elapsed = time.monotonic() - start

        if result.returncode != 0:
            raise ConnectionError(f"curl failed: {result.stderr[:200]}")

        try:
            data = json.loads(result.stdout)
            content = data["choices"][0]["message"]["content"]
            # Patch elapsed into the vote later via _build_vote
            return content
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            raise ValueError(f"DeepSeek response parse error: {e}") from e


class OllamaAdapter:
    """Ollama local adapter.

    Uses gemma4:26b by default for architectural diversity.
    Not a CLIRuntime call — direct 'ollama run' subprocess.
    """

    name: str = "ollama"
    runtime: str = "ollama_local"

    def __init__(
        self,
        model: str = "gemma4:26b",
        timeout: int = COUNCIL_AGENT_TIMEOUT,
    ):
        self._model = model
        self._timeout = timeout

    async def deliberate(self, topic: Topic) -> AgentVote:
        prompt = _format_agent_prompt(topic)
        try:
            result = await asyncio.to_thread(self._invoke, prompt)
            parsed = _parse_vote_json(result["output"])
            return _build_vote(
                self.name, self.runtime, parsed,
                result["elapsed"], result["success"],
                error=result.get("error", ""),
            )
        except Exception as e:
            logger.error(f"[OllamaAdapter] failed: {e}")
            return AgentVote(
                agent_name=self.name, runtime=self.runtime,
                success=False, error=str(e)[:200],
            )

    def _invoke(self, prompt: str) -> dict:
        """Run ollama subprocess."""
        start = time.monotonic()
        try:
            result = subprocess.run(
                ["ollama", "run", self._model, prompt],
                capture_output=True, text=True,
                timeout=self._timeout,
            )
            elapsed = time.monotonic() - start
            return {
                "output": result.stdout.strip(),
                "error": result.stderr[:200] if result.returncode != 0 else "",
                "elapsed": round(elapsed, 2),
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start
            return {
                "output": "",
                "error": f"Timeout after {self._timeout}s",
                "elapsed": round(elapsed, 2),
                "success": False,
            }
        except FileNotFoundError:
            return {
                "output": "",
                "error": "ollama command not found",
                "elapsed": 0.0,
                "success": False,
            }


def get_default_agents(
    timeout: int = COUNCIL_AGENT_TIMEOUT,
    agents: Optional[list[str]] = None,
) -> list[CouncilAgent]:
    """Build the default set of council agents.

    Args:
        timeout: per-agent timeout in seconds
        agents: optional list of agent names to include
                (default: all available)
    """
    all_agents: dict[str, CouncilAgent] = {
        "claude": ClaudeAdapter(timeout=timeout),
        "gemini": GeminiAdapter(timeout=timeout),
        "deepseek": DeepSeekAdapter(timeout=timeout),
        "ollama": OllamaAdapter(timeout=timeout),
    }

    if agents:
        selected = []
        for name in agents:
            if name in all_agents:
                selected.append(all_agents[name])
            else:
                logger.warning(f"Unknown agent: {name}")
        return selected

    return list(all_agents.values())
