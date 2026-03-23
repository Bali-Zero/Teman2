"""
Federation Launcher — Start all A2A agent services.

Usage:
  python -m apps.federation.launcher                    # Start all agents
  python -m apps.federation.launcher --agents gemini-search notebooklm  # Start specific agents
  python -m apps.federation.launcher --list             # List available agents
"""

from __future__ import annotations

import asyncio
import logging
import signal
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("federation.launcher")

# Port allocation — must match generate_agent_cards.py
AGENT_PORTS = {
    "gemini-search": 8082,
    "gemini-explore": 8083,
    "codex-sandbox": 8084,
    "claude-review": 8085,
    "aider": 8086,
    "notebooklm": 8087,
    "gws": 8088,
    # War Room agents (Pro only)
    "war-room-topic": 8100,
    "war-room-researcher": 8101,
    "war-room-strategist": 8102,
    "war-room-director": 8103,
    "war-room-image-gen": 8104,
    "war-room-canva": 8105,
    "war-room-delivery": 8106,
    # Intel Scraper agents (Pro only)
    "intel-pipeline": 8107,
    "intel-enricher": 8108,
    # claude-code (8081) is NOT launched — it IS the orchestrator
}

# Heartbeat monitoring
HEARTBEAT_INTERVAL = 30  # seconds between health checks
MAX_FAILED_CHECKS = 3    # consecutive failures before auto-restart


async def start_agent(agent_id: str, port: int) -> asyncio.subprocess.Process:
    """Start a single agent as a subprocess."""
    cmd = [
        sys.executable, "-m", "apps.federation.a2a_service",
        "--agent", agent_id,
        "--port", str(port),
    ]
    logger.info("Starting %s on port %d", agent_id, port)
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(Path(__file__).resolve().parents[2]),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    return process


async def health_check(host: str, port: int, retries: int = 10) -> bool:
    """Check if an agent is responding at /.well-known/agent.json."""
    import httpx

    url = f"http://{host}:{port}/.well-known/agent.json"
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return True
        except Exception:
            pass
        await asyncio.sleep(1.0)
    return False


async def monitor_agents(
    processes: dict[str, asyncio.subprocess.Process],
    shutdown: asyncio.Event,
) -> None:
    """Periodically health-check agents and auto-restart on repeated failure."""
    fail_counts: dict[str, int] = {agent_id: 0 for agent_id in processes}

    while not shutdown.is_set():
        # Sleep while respecting shutdown signal
        try:
            await asyncio.wait_for(shutdown.wait(), timeout=HEARTBEAT_INTERVAL)
            break  # shutdown was set
        except asyncio.TimeoutError:
            pass  # normal timeout — proceed with checks

        for agent_id in list(processes.keys()):
            port = AGENT_PORTS[agent_id]
            alive = await health_check("localhost", port, retries=1)

            if alive:
                fail_counts[agent_id] = 0
                continue

            fail_counts[agent_id] = fail_counts.get(agent_id, 0) + 1
            logger.debug(
                "Agent %s failed health check (%d/%d)",
                agent_id, fail_counts[agent_id], MAX_FAILED_CHECKS,
            )

            if fail_counts[agent_id] >= MAX_FAILED_CHECKS:
                logger.warning(
                    "Agent %s failed %d consecutive health checks, restarting...",
                    agent_id, MAX_FAILED_CHECKS,
                )
                # Kill the old process
                old_proc = processes[agent_id]
                old_proc.terminate()
                try:
                    await asyncio.wait_for(old_proc.wait(), timeout=5)
                except asyncio.TimeoutError:
                    old_proc.kill()

                # Start a new process
                new_proc = await start_agent(agent_id, port)
                processes[agent_id] = new_proc
                fail_counts[agent_id] = 0
                logger.info("Agent %s restarted on port %d", agent_id, port)


async def run_federation(agents: list[str] | None = None) -> None:
    """Start all (or specified) federation agents."""
    targets = agents or list(AGENT_PORTS.keys())
    processes: dict[str, asyncio.subprocess.Process] = {}

    # Start all agents
    for agent_id in targets:
        if agent_id not in AGENT_PORTS:
            logger.warning("Unknown agent: %s (skipping)", agent_id)
            continue
        port = AGENT_PORTS[agent_id]
        proc = await start_agent(agent_id, port)
        processes[agent_id] = proc

    # Wait for health checks
    logger.info("Waiting for agents to start...")
    await asyncio.sleep(2)  # Give uvicorn time to bind

    healthy = []
    unhealthy = []
    for agent_id, proc in processes.items():
        port = AGENT_PORTS[agent_id]
        if await health_check("localhost", port, retries=5):
            healthy.append(agent_id)
            logger.info("  ✅ %s (port %d) — healthy", agent_id, port)
        else:
            unhealthy.append(agent_id)
            logger.warning("  ❌ %s (port %d) — failed to start", agent_id, port)

    print(f"\n{'='*50}")
    print(f"Federation: {len(healthy)}/{len(processes)} agents running")
    if unhealthy:
        print(f"Failed: {', '.join(unhealthy)}")
    print(f"{'='*50}\n")

    # Wait for shutdown signal
    shutdown = asyncio.Event()

    def signal_handler():
        logger.info("Shutdown signal received")
        shutdown.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    # Start heartbeat monitor as background task
    monitor_task = asyncio.create_task(monitor_agents(processes, shutdown))

    await shutdown.wait()

    # Cancel monitor and cleanup
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass
    logger.info("Shutting down federation...")
    for agent_id, proc in processes.items():
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            proc.kill()
        logger.info("  Stopped %s", agent_id)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Federation Launcher")
    parser.add_argument("--agents", nargs="+", default=None, help="Specific agents to start")
    parser.add_argument("--list", action="store_true", help="List available agents")
    args = parser.parse_args()

    if args.list:
        print("Available federation agents:")
        for agent_id, port in AGENT_PORTS.items():
            print(f"  {agent_id:20s} → port {port}")
        print(f"\n  claude-code (8081) — orchestrator (not a service)")
        return

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    asyncio.run(run_federation(args.agents))


if __name__ == "__main__":
    main()
