"""
Federation Discovery — Resilient cross-machine agent discovery.

Manages agent locations across Pro and Air machines with multi-layer
host resolution to survive mDNS failures, VPN changes, and network issues.

Resolution order for Air agents:
  1. mDNS (Nuzantara-9.local) — works on same WiFi
  2. LAN IP (192.168.18.x) — works when mDNS broken
  3. Tailscale (100.89.49.94) — works over VPN/remote
  4. localhost fallback — if Air unreachable, try local

Usage:
  from apps.federation.discovery import discover_agents, get_agent_url

  agents = await discover_agents()  # Returns all reachable agents
  url = get_agent_url("notebooklm")  # Returns base URL (resolved)
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from typing import Any

import httpx

logger = logging.getLogger("federation.discovery")

# ═══════════════════════════════════════════════════════
# Machine Host Resolution — multi-layer fallback
# ═══════════════════════════════════════════════════════

# Air machine resolution candidates, tried in order.
# Override with env var FEDERATION_AIR_HOST if needed.
AIR_HOST_CANDIDATES = [
    "Nuzantara-9.local",    # mDNS (macOS Bonjour)
    "192.168.0.16",         # LAN IP (current DHCP lease — updated 2026-03-23)
    "192.168.18.211",       # LAN IP (alternate network)
    "100.89.49.94",         # Tailscale IP (works remote)
]

# Cache resolved host to avoid re-resolving on every call
_resolved_air_host: str | None = None


def _try_resolve(host: str, port: int = 8087, timeout: float = 2.0) -> bool:
    """Test if a host:port is reachable via TCP connect."""
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def _dns_resolve(hostname: str) -> str | None:
    """Try DNS/mDNS resolution. Returns IP or None."""
    try:
        return socket.gethostbyname(hostname)
    except socket.gaierror:
        return None


def resolve_air_host(port: int = 8087, force: bool = False) -> str:
    """Resolve the Air machine host with multi-layer fallback.

    Resolution order:
      1. FEDERATION_AIR_HOST env var (manual override)
      2. Cached result (if not force)
      3. Try each candidate: DNS resolve → TCP connect test
      4. Last resort: localhost (agent may run locally as fallback)

    Returns the resolved hostname or IP.
    """
    global _resolved_air_host  # noqa: PLW0603

    # 1. Environment override — always wins
    env_host = os.environ.get("FEDERATION_AIR_HOST")
    if env_host:
        logger.debug("Using FEDERATION_AIR_HOST override: %s", env_host)
        _resolved_air_host = env_host
        return env_host

    # 2. Cached result
    if _resolved_air_host and not force:
        return _resolved_air_host

    # 3. Try candidates in order
    for candidate in AIR_HOST_CANDIDATES:
        # DNS resolution first (for hostnames)
        if not candidate[0].isdigit():
            ip = _dns_resolve(candidate)
            if ip is None:
                logger.debug("DNS failed for %s, skipping", candidate)
                continue
            # Use the hostname if DNS worked (let connect use it)

        # TCP connect test
        if _try_resolve(candidate, port):
            logger.info("Air resolved via %s", candidate)
            _resolved_air_host = candidate
            return candidate
        else:
            logger.debug("TCP connect failed for %s:%d", candidate, port)

    # 4. Last resort — localhost (maybe agent runs locally)
    logger.warning(
        "All Air host candidates failed — falling back to localhost. "
        "Air agents may be unreachable. Set FEDERATION_AIR_HOST to override."
    )
    _resolved_air_host = "localhost"
    return "localhost"


def invalidate_air_cache() -> None:
    """Force re-resolution on next get_agent_url() call for Air agents."""
    global _resolved_air_host  # noqa: PLW0603
    _resolved_air_host = None
    logger.info("Air host cache invalidated")


# ═══════════════════════════════════════════════════════
# Agent Location Registry
# ═══════════════════════════════════════════════════════

AGENT_REGISTRY: dict[str, dict[str, Any]] = {
    # Pro agents (localhost — development machine)
    "claude-code": {"host": "localhost", "port": 8081, "machine": "pro"},
    "gemini-search": {"host": "localhost", "port": 8082, "machine": "pro"},
    "gemini-explore": {"host": "localhost", "port": 8083, "machine": "pro"},
    "codex-sandbox": {"host": "localhost", "port": 8084, "machine": "pro"},
    "claude-review": {"host": "localhost", "port": 8085, "machine": "pro"},
    "aider": {"host": "localhost", "port": 8086, "machine": "pro"},
    "gws": {"host": "localhost", "port": 8088, "machine": "pro"},
    # Air agents — host resolved dynamically via resolve_air_host()
    "notebooklm": {"host": "air", "port": 8087, "machine": "air"},
    "air-batch": {"host": "air", "port": 8091, "machine": "air"},
    # War Room agents (Pro only)
    "war-room-topic": {"host": "localhost", "port": 8100, "machine": "pro"},
    "war-room-researcher": {"host": "localhost", "port": 8101, "machine": "pro"},
    "war-room-strategist": {"host": "localhost", "port": 8102, "machine": "pro"},
    "war-room-director": {"host": "localhost", "port": 8103, "machine": "pro"},
    "war-room-image-gen": {"host": "localhost", "port": 8104, "machine": "pro"},
    "war-room-canva": {"host": "localhost", "port": 8105, "machine": "pro"},
    "war-room-delivery": {"host": "localhost", "port": 8106, "machine": "pro"},
}


def get_agent_url(agent_id: str) -> str:
    """Get the base URL for an agent. Air hosts are resolved dynamically."""
    if agent_id not in AGENT_REGISTRY:
        raise ValueError(f"Unknown agent: {agent_id}")
    r = AGENT_REGISTRY[agent_id]

    if r["machine"] == "air":
        host = resolve_air_host(port=r["port"])
    else:
        host = r["host"]

    return f"http://{host}:{r['port']}"


def get_agent_card_url(agent_id: str) -> str:
    """Get the Agent Card URL for an agent."""
    return f"{get_agent_url(agent_id)}/.well-known/agent-card.json"


async def check_agent_health(agent_id: str) -> dict[str, Any]:
    """Check if an agent service is reachable and healthy."""
    r = AGENT_REGISTRY.get(agent_id)
    if not r:
        return {"agent_id": agent_id, "status": "unknown", "error": "Not in registry"}

    # For Air agents, resolve host and note which resolution method worked
    resolved_host = None
    if r["machine"] == "air":
        resolved_host = resolve_air_host(port=r["port"])

    url = get_agent_card_url(agent_id)
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                card = resp.json()
                result = {
                    "agent_id": agent_id,
                    "status": "healthy",
                    "name": card.get("name", agent_id),
                    "skills": len(card.get("skills", [])),
                    "url": get_agent_url(agent_id),
                    "machine": r["machine"],
                }
                if resolved_host:
                    result["resolved_via"] = resolved_host
                return result
            return {
                "agent_id": agent_id,
                "status": "unhealthy",
                "error": f"HTTP {resp.status_code}",
                "machine": r["machine"],
            }
    except httpx.ConnectError:
        # For Air agents, try invalidating cache and re-resolving
        if r["machine"] == "air" and resolved_host != "localhost":
            invalidate_air_cache()
            new_host = resolve_air_host(port=r["port"], force=True)
            if new_host != resolved_host:
                logger.info("Retrying Air agent %s via %s", agent_id, new_host)
                try:
                    new_url = f"http://{new_host}:{r['port']}/.well-known/agent-card.json"
                    async with httpx.AsyncClient(timeout=3.0) as client:
                        resp = await client.get(new_url)
                        if resp.status_code == 200:
                            card = resp.json()
                            return {
                                "agent_id": agent_id,
                                "status": "healthy",
                                "name": card.get("name", agent_id),
                                "skills": len(card.get("skills", [])),
                                "url": f"http://{new_host}:{r['port']}",
                                "machine": r["machine"],
                                "resolved_via": new_host,
                                "failover": True,
                            }
                except Exception:
                    pass

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
    tasks = [check_agent_health(aid) for aid in AGENT_REGISTRY]
    return await asyncio.gather(*tasks)


async def discover_and_print() -> None:
    """Discovery with pretty output."""
    agents = await discover_agents()

    print(f"\n  Federation Discovery — {len(agents)} registered agents")
    print(f"  Air host resolution: {_resolved_air_host or 'not yet resolved'}")
    print(f"  {'='*65}")

    healthy = 0
    for a in agents:
        status = a["status"]
        icon = {"healthy": "✅", "offline": "⚫", "unhealthy": "🟡", "error": "❌"}.get(status, "❓")
        extra = ""
        if a.get("resolved_via"):
            extra = f" (via {a['resolved_via']})"
        if a.get("failover"):
            extra += " [failover]"

        if status == "healthy":
            healthy += 1
            print(f"  {icon} {a['agent_id']:20s} {a['name']:25s} [{a['machine']}] {a.get('skills', 0)} skills{extra}")
        else:
            print(f"  {icon} {a['agent_id']:20s} {a.get('error', status):25s} [{a.get('machine', '?')}]{extra}")

    print(f"  {'='*65}")
    print(f"  {healthy}/{len(agents)} agents online")
    print(f"\n  Resolution candidates: {', '.join(AIR_HOST_CANDIDATES)}")
    print(f"  Override: export FEDERATION_AIR_HOST=<ip-or-hostname>")


def main() -> None:
    asyncio.run(discover_and_print())


if __name__ == "__main__":
    main()
