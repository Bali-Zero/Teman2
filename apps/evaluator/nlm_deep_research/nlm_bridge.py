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
from typing import Optional

logger = logging.getLogger(__name__)

# NLM CLI path — installed via: npm install -g notebooklm-mcp
NLM_CLI = "nlm"

# Default timeout for NLM queries (seconds)
QUERY_TIMEOUT = 120


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
    # Build nlm CLI command (v0.5.x syntax: nlm query notebook <ID> <QUESTION>)
    cmd = [
        NLM_CLI, "query", "notebook",
        notebook_id,
        query,
        "--timeout", str(timeout),
    ]

    if conversation_id:
        cmd.extend(["--conversation-id", conversation_id])

    logger.info("NLM query: %s... (timeout=%ds)", query[:80], timeout)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 30,  # extra margin for CLI overhead
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or f"nlm exited with code {result.returncode}"
            logger.error("NLM CLI error: %s", error_msg)
            return {"status": "error", "error": error_msg}

        # Parse JSON output
        output = result.stdout.strip()
        if not output:
            return {"status": "error", "error": "Empty response from nlm CLI"}

        data = json.loads(output)

        # nlm CLI v0.5.x wraps response in {"value": {...}}
        if "value" in data and isinstance(data["value"], dict):
            data = data["value"]

        # Normalize response format
        return {
            "status": data.get("status", "success"),
            "answer": data.get("answer", ""),
            "sources_used": data.get("sources_used", []),
            "conversation_id": data.get("conversation_id", conversation_id),
            "citations": data.get("citations", {}),
        }

    except subprocess.TimeoutExpired:
        logger.error("NLM query timed out after %ds", timeout)
        return {"status": "error", "error": f"Query timed out after {timeout}s"}
    except json.JSONDecodeError as e:
        logger.error("Failed to parse NLM response: %s", e)
        return {"status": "error", "error": f"JSON parse error: {e}"}
    except FileNotFoundError:
        logger.error("nlm CLI not found — install with: npm install -g notebooklm-mcp")
        return {"status": "error", "error": "nlm CLI not found"}
    except Exception as e:
        logger.error("NLM query failed: %s", e, exc_info=True)
        return {"status": "error", "error": str(e)}


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
