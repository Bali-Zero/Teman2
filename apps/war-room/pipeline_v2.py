"""
War Room Pipeline v2 — A2A-native Python orchestrator.

Replaces the sequential bash pipeline.sh with async Python calling
war-room agents via A2A JSON-RPC protocol.

Usage:
  python -m apps.war_room.pipeline_v2 "Coretax 2025" [--dry-run] [--auto]
  python apps/war-room/pipeline_v2.py "topic" [--dry-run]

Agents read/write to apps/war-room/output/ filesystem.
This orchestrator does NOT pass data between agents — each agent
reads the previous agent's output from disk.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

# ═══════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════

WAR_ROOM = Path(__file__).resolve().parent
OUTPUT_DIR = WAR_ROOM / "output"
LOG_DIR = WAR_ROOM / "logs"

# Phases and their criticality.
# Critical phases abort the pipeline on failure; non-critical log a warning and continue.
CRITICAL_PHASES = {"war-room-director"}

# Agent ports — mirrors AGENT_REGISTRY from apps.federation.discovery
AGENT_PORTS: dict[str, int] = {
    "war-room-topic": 8100,
    "war-room-researcher": 8101,
    "war-room-strategist": 8102,
    "war-room-director": 8103,
    "war-room-image-gen": 8104,
    "war-room-canva": 8105,
    "war-room-delivery": 8106,
}

# ═══════════════════════════════════════════════════════
# Logging
# ═══════════════════════════════════════════════════════

logger = logging.getLogger("war-room.pipeline_v2")


def _setup_logging(log_file: Path) -> None:
    """Configure dual logging: stdout + file."""
    log_file.parent.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(fmt)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)

    root = logging.getLogger("war-room.pipeline_v2")
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console_handler)


def log(msg: str) -> None:
    """Log with emoji + timestamp, matching pipeline.sh format."""
    logger.info(msg)


# ═══════════════════════════════════════════════════════
# A2A Client Helper
# ═══════════════════════════════════════════════════════


async def call_agent(
    agent_id: str, prompt: str, timeout: float = 600
) -> dict[str, Any]:
    """Call a war-room A2A agent via JSON-RPC message/send.

    Args:
        agent_id: Agent identifier from AGENT_PORTS.
        prompt: Text prompt (the topic string).
        timeout: HTTP request timeout in seconds.

    Returns:
        The full JSON-RPC response dict.

    Raises:
        AgentError: On connection failure or non-zero JSON-RPC error.
    """
    port = AGENT_PORTS.get(agent_id)
    if port is None:
        # Try dynamic import from federation registry
        try:
            from apps.federation.discovery import AGENT_REGISTRY

            entry = AGENT_REGISTRY.get(agent_id)
            if entry:
                port = entry["port"]
        except ImportError:
            pass

    if port is None:
        raise AgentError(agent_id, f"Unknown agent: {agent_id}")

    url = f"http://localhost:{port}/"
    payload = {
        "jsonrpc": "2.0",
        "id": f"{agent_id}-{int(time.time())}",
        "method": "message/send",
        "params": {
            "message": {
                "messageId": str(uuid.uuid4()),
                "role": "user",
                "parts": [{"kind": "text", "text": prompt}],
            }
        },
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload)
            result = resp.json()

            # Check for JSON-RPC error
            if "error" in result:
                error = result["error"]
                raise AgentError(
                    agent_id,
                    f"JSON-RPC error {error.get('code', '?')}: {error.get('message', 'unknown')}",
                )

            return result

    except httpx.ConnectError:
        raise AgentError(
            agent_id,
            f"Agent {agent_id} not running "
            f"-- start with: python -m apps.federation.a2a_service --agent {agent_id} --port {port}",
        )
    except httpx.ReadTimeout:
        raise AgentError(
            agent_id,
            f"Agent {agent_id} timed out after {timeout}s",
        )


def extract_artifact_text(result: dict[str, Any]) -> str:
    """Extract text content from an A2A JSON-RPC response.

    Looks for artifact parts in the result, falling back to the
    status message text.
    """
    resp = result.get("result", {})

    # Check artifacts first
    artifacts = resp.get("artifacts", [])
    for artifact in artifacts:
        for part in artifact.get("parts", []):
            if part.get("kind") == "text":
                return part.get("text", "")
            # TextPart inside root
            root = part.get("root", {})
            if root.get("text"):
                return root["text"]

    # Fallback: status message
    status = resp.get("status", {})
    message = status.get("message", {})
    for part in message.get("parts", []):
        if part.get("kind") == "text":
            return part.get("text", "")
        root = part.get("root", {})
        if root.get("text"):
            return root["text"]

    return ""


def extract_topic(result: dict[str, Any]) -> str:
    """Extract the topic string from a topic selector response."""
    text = extract_artifact_text(result)
    # Try parsing as JSON (topic selector outputs JSON)
    try:
        data = json.loads(text)
        return data.get("topic", text.strip())
    except (json.JSONDecodeError, TypeError):
        return text.strip()


# ═══════════════════════════════════════════════════════
# Error handling
# ═══════════════════════════════════════════════════════


class AgentError(Exception):
    """Raised when an A2A agent call fails."""

    def __init__(self, agent_id: str, message: str) -> None:
        self.agent_id = agent_id
        super().__init__(message)


# ═══════════════════════════════════════════════════════
# Pipeline
# ═══════════════════════════════════════════════════════


async def run_pipeline(topic: str, dry_run: bool = False) -> dict[str, Any]:
    """Run the full war-room content pipeline.

    Args:
        topic: The content topic. If empty, Phase 0 selects one.
        dry_run: If True, log what would happen without calling agents.

    Returns:
        Pipeline result summary dict.
    """
    t_start = time.monotonic()
    results: dict[str, Any] = {}

    # Ensure output directories exist
    for subdir in ("raw", "strategy", "images", "canva", "master"):
        (OUTPUT_DIR / subdir).mkdir(parents=True, exist_ok=True)

    # ── Phase 0: Topic selection ──────────────────────────
    if not topic:
        log("")
        log("━━━ FASE 0: TOPIC SELECTOR (A2A) ━━━")
        if dry_run:
            log("   [DRY RUN] Would call war-room-topic agent")
            topic = "DRY-RUN-TOPIC"
        else:
            try:
                result = await call_agent("war-room-topic", "select best topic", timeout=240)
                topic = extract_topic(result)
                results["topic_selector"] = "ok"
                log(f"   Topic selezionato: {topic}")
            except AgentError as e:
                log(f"   {e}")
                log("   FATAL: Nessun topic disponibile")
                return {"topic": "", "status": "failed", "error": str(e)}

    if not topic:
        log("FATAL: Nessun topic. Passa un topic come argomento.")
        return {"topic": "", "status": "failed", "error": "no topic"}

    log(f"📌 Topic: {topic}")

    # ── Phase 1: Research ─────────────────────────────────
    log("")
    log("━━━ FASE 1: RESEARCH (ChatGPT + Exa + Qwen merge) ━━━")
    if dry_run:
        log("   [DRY RUN] Would call war-room-researcher agent")
    else:
        try:
            result = await call_agent("war-room-researcher", topic, timeout=600)
            results["researcher"] = "ok"
            log("   ✅ Research completata")
        except AgentError as e:
            log(f"   ⚠️  Research fallita: {e}")
            log("   Continuo con dati disponibili su disco...")
            results["researcher"] = f"failed: {e}"

    # ── Phase 2a: Strategy ────────────────────────────────
    log("")
    log("━━━ FASE 2a: STRATEGY (Gemini 3 concepts) ━━━")
    if dry_run:
        log("   [DRY RUN] Would call war-room-strategist agent")
    else:
        try:
            result = await call_agent("war-room-strategist", topic, timeout=600)
            results["strategist"] = "ok"
            log("   ✅ Concepts pronti")
        except AgentError as e:
            log(f"   ⚠️  Strategy fallita: {e}")
            results["strategist"] = f"failed: {e}"

    # ── Phase 2b: Director ────────────────────────────────
    log("")
    log("━━━ FASE 2b: DIRECTOR (slides JSON) ━━━")
    if dry_run:
        log("   [DRY RUN] Would call war-room-director agent")
    else:
        try:
            result = await call_agent("war-room-director", topic, timeout=600)
            results["director"] = "ok"
            log("   ✅ Slides JSON pronti")
        except AgentError as e:
            # Director is CRITICAL — abort pipeline
            log(f"   ❌ CRITICAL: Director fallito: {e}")
            results["director"] = f"failed: {e}"
            elapsed = time.monotonic() - t_start
            log(f"\n❌ PIPELINE ABORTED dopo {elapsed:.0f}s — director failure")
            return {
                "topic": topic,
                "status": "aborted",
                "error": str(e),
                "elapsed_s": round(elapsed),
                "results": results,
            }

    # ── Phase 3: Images ───────────────────────────────────
    log("")
    log("━━━ FASE 3: IMAGES ━━━")
    log("   ℹ️  Image prompts embedded as text annotations")
    results["images"] = "annotations_only"

    # ── Phase 4: Canva builder ────────────────────────────
    log("")
    log("━━━ FASE 4: CANVA BUILDER ━━━")
    if dry_run:
        log("   [DRY RUN] Would call war-room-canva agent")
    else:
        try:
            result = await call_agent("war-room-canva", topic, timeout=120)
            results["canva"] = "ok"
            log("   ✅ canva_pending.json pronto")
            log("   💡 Scrivi 'applica canva_pending' in Claude Code per applicare")
        except AgentError as e:
            log(f"   ⚠️  Canva builder fallito: {e}")
            log("   Continuo senza carousel (non bloccante)")
            results["canva"] = f"failed: {e}"

    # ── Phase 5: Delivery ─────────────────────────────────
    log("")
    log("━━━ FASE 5: DELIVERY ━━━")
    if dry_run:
        log("   [DRY RUN] Would call war-room-delivery agent")
    else:
        try:
            result = await call_agent("war-room-delivery", topic, timeout=120)
            results["delivery"] = "ok"
            log("   ✅ Delivery completata")
        except AgentError as e:
            log(f"   ⚠️  Delivery fallita: {e}")
            log("   Verifica manualmente Drive/Telegram")
            results["delivery"] = f"failed: {e}"

    # ── Summary ───────────────────────────────────────────
    elapsed = time.monotonic() - t_start
    log("")
    log(f"🏁 WAR ROOM COMPLETATA in {elapsed:.0f}s")
    log(f"📁 Output: {OUTPUT_DIR}/")

    return {
        "topic": topic,
        "status": "complete",
        "elapsed_s": round(elapsed),
        "results": results,
    }


# ═══════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════


def main() -> None:
    parser = argparse.ArgumentParser(
        description="War Room Pipeline v2 — A2A orchestrator",
        usage='python -m apps.war_room.pipeline_v2 "topic" [--dry-run] [--auto]',
    )
    parser.add_argument(
        "topic",
        nargs="?",
        default="",
        help="Content topic (if omitted, Phase 0 selects one)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would happen without calling agents",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto mode (skip confirmations)",
    )
    args = parser.parse_args()

    # Setup logging
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"pipeline_v2_{timestamp}.log"
    _setup_logging(log_file)

    log("🚨 BALI ZERO WAR ROOM v2 (A2A)")
    log(f"🕐 Start: {datetime.now(tz=timezone.utc).isoformat()}")
    if args.dry_run:
        log("⚠️  DRY RUN MODE — nessuna azione reale")

    # Run pipeline
    result = asyncio.run(run_pipeline(topic=args.topic, dry_run=args.dry_run))

    log(f"📋 Log: {log_file}")

    # Print result summary as JSON
    log(f"📊 Result: {json.dumps(result, ensure_ascii=False)}")

    # Exit code: 0 on complete, 1 on failure/abort
    if result.get("status") not in ("complete",):
        sys.exit(1)


if __name__ == "__main__":
    main()
