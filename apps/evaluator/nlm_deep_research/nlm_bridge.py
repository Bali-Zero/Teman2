"""Bridge between NLM pipeline and NotebookLM MCP server.

Wraps the `nlm` CLI tool to execute notebook_query calls from Python.
This is the production query function injected into NLMPipeline.

Usage:
    from apps.evaluator.nlm_deep_research.nlm_bridge import nlm_query
    pipeline = NLMPipeline(nlm_query_fn=nlm_query)
"""

import json
import logging
import subprocess
import time
from typing import Optional

logger = logging.getLogger(__name__)

# NLM CLI path — installed via: npm install -g notebooklm-mcp
NLM_CLI = "nlm"

# Default timeout for NLM queries (seconds).
# Measured: warm queries 28-60s, complex cluster queries can reach 90-150s.
# Bumped 120→180 on 2026-04-25 after NB-2 cluster A query hit 122s (exit 1 at 120s cap).
QUERY_TIMEOUT = 180

# Retry policy for transient cloud failures (NotebookLM backend flakiness).
# 2026-04-28: NB-2 L2 query failed at 02:16 with exit 1 after 182s, but the same
# query succeeded when replayed manually. Pattern is cloud-side, not local — one
# retry with backoff catches the common case without inflating cron wallclock.
RETRY_ATTEMPTS = 2  # initial + 1 retry
RETRY_BACKOFF_S = 30


def _run_nlm_once(cmd: list, timeout: int, conversation_id: Optional[str]) -> dict:
    """Single nlm CLI invocation. Returns normalized dict (success or error)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 30,  # extra margin for CLI overhead
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or f"nlm exited with code {result.returncode}"
            return {"status": "error", "error": error_msg, "_retryable": True}

        output = result.stdout.strip()
        if not output:
            return {"status": "error", "error": "Empty response from nlm CLI", "_retryable": True}

        data = json.loads(output)

        # nlm CLI v0.5.x wraps response in {"value": {...}}
        if "value" in data and isinstance(data["value"], dict):
            data = data["value"]

        return {
            "status": data.get("status", "success"),
            "answer": data.get("answer", ""),
            "sources_used": data.get("sources_used", []),
            "conversation_id": data.get("conversation_id", conversation_id),
            "citations": data.get("citations", {}),
        }

    except subprocess.TimeoutExpired:
        return {"status": "error", "error": f"Query timed out after {timeout}s", "_retryable": True}
    except json.JSONDecodeError as e:
        return {"status": "error", "error": f"JSON parse error: {e}", "_retryable": False}
    except FileNotFoundError:
        return {"status": "error", "error": "nlm CLI not found", "_retryable": False}
    except Exception as e:
        return {"status": "error", "error": str(e), "_retryable": False}


def nlm_query(
    notebook_id: str,
    query: str,
    conversation_id: Optional[str] = None,
    timeout: int = QUERY_TIMEOUT,
) -> dict:
    """Execute a NotebookLM query via the nlm CLI.

    Args:
        notebook_id: NLM notebook UUID
        query: Query text to send
        conversation_id: Optional conversation ID for context injection
        timeout: Query timeout in seconds

    Returns:
        Dict with status, answer, sources_used, conversation_id
    """
    cmd = [
        NLM_CLI, "query", "notebook",
        notebook_id,
        query,
        "--timeout", str(timeout),
    ]

    if conversation_id:
        cmd.extend(["--conversation-id", conversation_id])

    logger.info("NLM query: %s... (timeout=%ds)", query[:80], timeout)

    last_error = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        result = _run_nlm_once(cmd, timeout, conversation_id)

        if result.get("status") != "error":
            if attempt > 1:
                logger.info("NLM query succeeded on attempt %d", attempt)
            return result

        last_error = result.get("error", "unknown")
        retryable = result.pop("_retryable", False)

        if attempt < RETRY_ATTEMPTS and retryable:
            logger.warning(
                "NLM CLI error (attempt %d/%d): %s — retrying in %ds",
                attempt, RETRY_ATTEMPTS, last_error, RETRY_BACKOFF_S,
            )
            time.sleep(RETRY_BACKOFF_S)
            continue

        logger.error("NLM CLI error (attempt %d/%d, final): %s", attempt, RETRY_ATTEMPTS, last_error)
        return {"status": "error", "error": last_error}

    return {"status": "error", "error": last_error or "exhausted retries"}


def check_nlm_available() -> bool:
    """Check if the nlm CLI is installed and accessible."""
    try:
        result = subprocess.run(
            [NLM_CLI, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            logger.info("nlm CLI available: %s", result.stdout.strip())
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return False
