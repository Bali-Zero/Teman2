"""
Federation Discovery — Cross-machine agent discovery.

Manages agent locations across Pro and Air machines.
Pro agents: localhost:808x
Air agents: air.local:808x (mDNS over local network)

Usage:
  from apps.federation.discovery import discover_agents, get_agent_url

  agents = await discover_agents()  # Returns all reachable agents
  url = get_agent_url("notebooklm")  # Returns base URL for an agent
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("federation.discovery")

# ═══════════════════════════════════════════════════════
# Agent Location Registry
# ═══════════════════════════════════════════════════════
# Static registry — which agent runs where.
# All agents currently on Pro. When Air agents are added,
# change the host to "air.local" for those agents.

AGENT_REGISTRY: dict[str, dict[str, Any]] = {
    # Pro agents (localhost — development machine)
    "claude-code": {"host": "localhost", "port": 8081, "machine": "pro"},
    "gemini-search": {"host": "localhost", "port": 8082, "machine": "pro"},
    "gemini-explore": {"host": "localhost", "port": 8083, "machine": "pro"},
    "codex-sandbox": {"host": "localhost", "port": 8084, "machine": "pro"},
    "claude-review": {"host": "localhost", "port": 8085, "machine": "pro"},
    "aider": {"host": "localhost", "port": 8086, "machine": "pro"},
    "gws": {"host": "localhost", "port": 8088, "machine": "pro"},
    # Air agents (air.local — H24 server machine)
    "notebooklm": {"host": "air.local", "port": 8087, "machine": "air"},
    "air-batch": {"host": "air.local", "port": 8091, "machine": "air"},
}


def get_agent_url(agent_id: str) -> str:
    """Get the base URL for an agent."""
    if agent_id not in AGENT_REGISTRY:
        raise ValueError(f"Unknown agent: {agent_id}")
    r = AGENT_REGISTRY[agent_id]
    return f"http://{r['host']}:{r['port']}"


def get_agent_card_url(agent_id: str) -> str:
    """Get the Agent Card URL for an agent."""
    return f"{get_agent_url(agent_id)}/.well-known/agent-card.json"


async def check_agent_health(agent_id: str) -> dict[str, Any]:
    """Check if an agent service is reachable and healthy."""
    r = AGENT_REGISTRY.get(agent_id)
    if not r:
        return {"agent_id": agent_id, "status": "unknown", "error": "Not in registry"}

    url = get_agent_card_url(agent_id)
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                card = resp.json()
                return {
                    "agent_id": agent_id,
                    "status": "healthy",
                    "name": card.get("name", agent_id),
                    "skills": len(card.get("skills", [])),
                    "url": get_agent_url(agent_id),
                    "machine": r["machine"],
                }
            return {
                "agent_id": agent_id,
                "status": "unhealthy",
                "error": f"HTTP {resp.status_code}",
                "machine": r["machine"],
            }
    except httpx.ConnectError:
        return {
            "agent_id": agent_id,
            "status": "offline",
            "error": "Connection refused (service not running)",
            "machine": r["machine"],
        }
    except Exception as e:
        return {
            "agent_id": agent_id,
            "status": "error",
            "error": str(e),
            "machine": r["machine"],
        }


async def discover_agents() -> list[dict[str, Any]]:
    """Discover all registered agents and check their health."""
    import asyncio
    tasks = [check_agent_health(aid) for aid in AGENT_REGISTRY]
    return await asyncio.gather(*tasks)


async def discover_and_print() -> None:
    """Discovery with pretty output."""
    agents = await discover_agents()

    print(f"\n  Federation Discovery — {len(agents)} registered agents")
    print(f"  {'='*55}")

    healthy = 0
    for a in agents:
        status = a["status"]
        icon = {"healthy": "✅", "offline": "⚫", "unhealthy": "🟡", "error": "❌"}.get(status, "❓")
        if status == "healthy":
            healthy += 1
            print(f"  {icon} {a['agent_id']:20s} {a['name']:30s} [{a['machine']}] {a.get('skills', 0)} skills")
        else:
            print(f"  {icon} {a['agent_id']:20s} {a.get('error', status):30s} [{a.get('machine', '?')}]")

    print(f"  {'='*55}")
    print(f"  {healthy}/{len(agents)} agents online")


def main() -> None:
    import asyncio
    asyncio.run(discover_and_print())


if __name__ == "__main__":
    main()
