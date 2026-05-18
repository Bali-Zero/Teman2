#!/usr/bin/env python3
"""WR3 dispatch agent — Claude Agent SDK wrapper with cost ceiling + cascade.

Enforces Symbiosis precedence at dispatch time (Law 7 > Law 4):
- BudgetExceededError on GATE agents → HARD HALT + Telegram P0
- BudgetExceededError on HOT PATH    → cascade Tier 1 → Tier 2 (Gemini free) → Tier 3 (Codex) → mark FAIL
- Generic Exception on HOT PATH      → Telegram P0, raise (do NOT ack, replays on reconnect)

Reference: docs/wr3/symbiosis-precedence.md
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from wr3_contracts import AgentContract, WR3Contracts

# ---------------------------------------------------------------------------
# Exceptions — surface inter-law conflicts to supervisor
# ---------------------------------------------------------------------------


class WR3DispatchError(Exception):
    """Base for dispatch-layer errors."""


class BudgetExceededError(WR3DispatchError):
    """Claude Agent SDK returned BudgetExceeded — wrapped for precedence routing."""


class HardHaltException(WR3DispatchError):
    """Gate agent hit ceiling. Episode halts, Telegram P0 fires."""


class CascadeExhaustedError(WR3DispatchError):
    """All cascade tiers exhausted. Mark FAIL, retry next cycle."""


class OSINTLeakError(WR3DispatchError):
    """Law 2 violation. Trumps everything — episode halts regardless of Zero approval."""


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DispatchResult:
    agent: str
    cost_usd_estimated: float | None
    duration_ms: int
    cascade_tier: int  # 1 = primary, 2 = Gemini, 3 = Codex
    raw_output: str
    cascade_reason: str | None = None


# ---------------------------------------------------------------------------
# Tier 1 — Claude Agent SDK native
# ---------------------------------------------------------------------------


async def _dispatch_claude_sdk(
    contract: AgentContract,
    prompt: str,
    *,
    timeout_ms: int = 300000,
) -> DispatchResult:
    """Primary path: Claude Agent SDK with native max_budget_usd.

    SDK is itself a subprocess wrapper (compliant Symbiosis Law 1).
    Reference: ~/.claude/agents/wr3-<agent>.md frontmatter.
    """
    try:
        from claude_agent_sdk import query, ClaudeAgentOptions  # type: ignore
    except ImportError as e:
        raise WR3DispatchError(
            "claude_agent_sdk not installed. pip install claude-agent-sdk. "
            f"Underlying: {e}"
        ) from e

    ceiling = contract.cost.ceiling_usd
    if ceiling is None and contract.cost_class == "render":
        ceiling = 0.50  # 200 cr Flow Pro cash equivalent
    elif ceiling is None:
        ceiling = 0.15

    options = ClaudeAgentOptions(
        agent=contract.name,
        max_budget_usd=ceiling,
        timeout_ms=timeout_ms,
        allowed_tools=list(contract.allowed_tools),
    )

    started = asyncio.get_event_loop().time()
    output_parts: list[str] = []

    # Try to import SDK-specific budget exception type. Codex+Gemini+DeepSeek
    # 3/3 review 2026-05-18 flagged string-match heuristic as brittle Law 7
    # bypass. Order of preference:
    #   1. SDK-exported BudgetExceededError class (exact instanceof match)
    #   2. SDK error_type attribute (when SDK upgrades schema)
    #   3. String heuristic (legacy fallback)
    sdk_budget_class = None
    try:  # pragma: no cover — depends on SDK version
        from claude_agent_sdk import BudgetExceededError as _SdkBudgetExceeded  # type: ignore
        sdk_budget_class = _SdkBudgetExceeded
    except ImportError:
        pass

    try:
        async for message in query(prompt=prompt, options=options):
            if hasattr(message, "result"):
                output_parts.append(str(message.result))
    except Exception as e:  # pragma: no cover — SDK-specific exception type varies
        # Layer 1: instance check (preferred when SDK exports the class)
        if sdk_budget_class is not None and isinstance(e, sdk_budget_class):
            raise BudgetExceededError(f"{contract.name}: {e}") from e
        # Layer 2: SDK error_type attribute (if SDK ever standardizes one)
        error_type = getattr(e, "error_type", None) or getattr(e, "code", None)
        if error_type and str(error_type).lower() in {
            "budget_exceeded", "max_budget_exceeded", "spend_limit_reached",
        }:
            raise BudgetExceededError(f"{contract.name}: {e}") from e
        # Layer 3: string heuristic ONLY as a final fallback. Expanded to
        # cover known phrasings; still imperfect but documented.
        text = str(e).lower()
        budget_signals = (
            "budget", "max_budget", "ceiling", "spend_limit",
            "spending limit", "out of credit", "insufficient funds",
        )
        if any(sig in text for sig in budget_signals):
            raise BudgetExceededError(f"{contract.name}: {e}") from e
        raise

    duration_ms = int((asyncio.get_event_loop().time() - started) * 1000)
    return DispatchResult(
        agent=contract.name,
        cost_usd_estimated=None,  # SDK does not always return final cost
        duration_ms=duration_ms,
        cascade_tier=1,
        raw_output="\n".join(output_parts),
    )


# ---------------------------------------------------------------------------
# Tier 2 — Gemini CLI free OAuth (long-context safety net)
# ---------------------------------------------------------------------------


async def _dispatch_gemini_cli(
    contract: AgentContract,
    prompt: str,
    *,
    timeout_s: int = 300,
) -> DispatchResult:
    """Cascade fallback: gemini -m gemini-3.1-pro-preview -p '...'.

    OAuth free — no API key. Symbiosis Law 1 compliant (CLI subprocess).
    """
    gemini = shutil.which("gemini")
    if gemini is None:
        raise WR3DispatchError("gemini CLI not on PATH for cascade Tier 2")

    started = asyncio.get_event_loop().time()
    proc = await asyncio.create_subprocess_exec(
        gemini,
        "-m",
        "gemini-3.1-pro-preview",
        "-p",
        prompt,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError as e:
        proc.kill()
        raise CascadeExhaustedError(
            f"{contract.name}: Gemini cascade timeout {timeout_s}s"
        ) from e

    duration_ms = int((asyncio.get_event_loop().time() - started) * 1000)
    if proc.returncode != 0:
        text = stderr.decode("utf-8", "replace").lower()
        if "quota" in text or "429" in text or "rate" in text:
            raise CascadeExhaustedError(
                f"{contract.name}: Gemini quota exhausted (stderr={text[:200]})"
            )
        raise WR3DispatchError(
            f"{contract.name}: Gemini exit {proc.returncode} stderr={text[:200]}"
        )

    return DispatchResult(
        agent=contract.name,
        cost_usd_estimated=0.0,  # free OAuth
        duration_ms=duration_ms,
        cascade_tier=2,
        raw_output=stdout.decode("utf-8", "replace"),
        cascade_reason="claude_budget_exceeded",
    )


# ---------------------------------------------------------------------------
# Telegram P0 — Symbiosis Law 4 degrade-loud
# ---------------------------------------------------------------------------


async def telegram_p0(message: str) -> None:
    """Fire Telegram P0 alert to Zero. Non-blocking — best effort."""
    script = Path.home() / "scripts" / "telegram-notify.sh"
    if not script.exists():
        return
    chat_id = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    try:
        proc = await asyncio.create_subprocess_exec(
            str(script), chat_id, f"[WR3 P0] {message}",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=10)
    except Exception:
        pass  # never let telegram failure break dispatch


# ---------------------------------------------------------------------------
# Dispatch — orchestrates Tier 1 → Tier 2 cascade per precedence
# ---------------------------------------------------------------------------


async def dispatch_agent(
    contracts: WR3Contracts,
    agent_name: str,
    prompt: str,
    *,
    episode_id: str = "unknown",
    timeout_ms: int = 300000,
) -> DispatchResult:
    """Dispatch with precedence Law 2 > Law 5 > Law 7 > Law 4.

    Currently implements Tier 1 (Claude SDK) → Tier 2 (Gemini CLI) cascade.
    Tier 3 (Codex) reserved for future cascade if Gemini quota also exhausted.
    """
    contract = contracts.for_agent(agent_name)

    try:
        return await _dispatch_claude_sdk(contract, prompt, timeout_ms=timeout_ms)
    except BudgetExceededError as e:
        if contract.is_gate:
            # Law 7: gate ceiling hit → HARD HALT (do NOT cascade)
            await telegram_p0(
                f"{agent_name} hit cost ceiling. Episode {episode_id} HALTED."
            )
            raise HardHaltException(str(e)) from e

        if contract.is_core:
            # Law 4 cascade — Tier 2 Gemini
            try:
                return await _dispatch_gemini_cli(contract, prompt)
            except CascadeExhaustedError:
                await telegram_p0(
                    f"{agent_name} budget+cascade exhausted. Episode {episode_id} marked FAIL."
                )
                raise

        # Non-core, non-gate (scheduled/fallback) — mark fail, retry next cycle
        raise CascadeExhaustedError(
            f"{agent_name} (non-core) budget exceeded — no cascade for scheduled/fallback tier"
        ) from e


if __name__ == "__main__":
    # Smoke test — no real dispatch, just verify imports + contract resolution
    from wr3_contracts import load_contracts

    contracts = load_contracts()
    print(f"Loaded {len(contracts.agents)} contracts")
    for name in sorted(contracts.agents):
        c = contracts.for_agent(name)
        print(
            f"  {name:30s} model={c.model:6s} ceiling=${c.cost.ceiling_usd} "
            f"gate={c.is_gate} core={c.is_core}"
        )
