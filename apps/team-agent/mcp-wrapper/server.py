#!/usr/bin/env python3
"""
MCP Permission Wrapper — stdio proxy that filters tools by role.

Sits between OpenClaw/Gemini CLI and the real nuzantara-mcp server.
Intercepts tools/list (filters by role) and tools/call (blocks unauthorized).

Usage in OpenClaw .mcp.json or Gemini CLI config:
{
  "nuzantara-filtered": {
    "command": "python3",
    "args": ["/path/to/apps/team-agent/mcp-wrapper/server.py"],
    "env": { "AGENT_ROLE": "visa_specialist" }
  }
}
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from permissions import PermissionChecker
from audit import log_tool_call

# Configure logging to stderr (stdout is for MCP protocol)
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="[mcp-wrapper] %(levelname)s: %(message)s",
)
logger = logging.getLogger("mcp-wrapper")

ROLE = os.getenv("AGENT_ROLE", "visa_specialist")
REAL_MCP_CMD = os.getenv(
    "REAL_MCP_CMD",
    str(Path.home() / ".local" / "bin" / "nuzantara-mcp-server"),
)

checker = PermissionChecker(str(Path(__file__).parent / "config" / "roles.yaml"))


def make_error_response(request_id, code: int, message: str) -> dict:
    """Create a JSON-RPC error response."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def filter_tools_list(response: dict) -> dict:
    """Filter tools/list response to only show allowed tools for the role."""
    if "result" not in response:
        return response

    result = response["result"]
    tools = result.get("tools", [])
    original_count = len(tools)

    filtered = [t for t in tools if checker.is_allowed(ROLE, t.get("name", ""))]
    result["tools"] = filtered

    logger.info("tools/list: %d → %d tools (role=%s)", original_count, len(filtered), ROLE)
    return response


def main():
    logger.info("Starting MCP Permission Wrapper (role=%s)", ROLE)
    logger.info("Real MCP: %s", REAL_MCP_CMD)
    logger.info("Allowed tools: %s", checker.get_allowed_tools(ROLE))

    # Start the real MCP server as subprocess
    try:
        proc = subprocess.Popen(
            [REAL_MCP_CMD],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            bufsize=0,  # Unbuffered for real-time proxy
        )
    except FileNotFoundError:
        logger.error("Real MCP server not found: %s", REAL_MCP_CMD)
        sys.exit(1)

    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            # Try to parse as JSON-RPC
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                # Not JSON — pass through to real MCP
                proc.stdin.write(line + "\n")
                proc.stdin.flush()
                # Read and forward response
                resp_line = proc.stdout.readline()
                if resp_line:
                    sys.stdout.write(resp_line)
                    sys.stdout.flush()
                continue

            method = request.get("method", "")
            request_id = request.get("id")

            # === INTERCEPT: tools/call ===
            if method == "tools/call":
                tool_name = request.get("params", {}).get("name", "")
                if tool_name and not checker.is_allowed(ROLE, tool_name):
                    log_tool_call(ROLE, tool_name, allowed=False)
                    error = make_error_response(
                        request_id,
                        -32600,
                        f"Tool '{tool_name}' not allowed for role '{ROLE}'",
                    )
                    sys.stdout.write(json.dumps(error) + "\n")
                    sys.stdout.flush()
                    logger.warning("BLOCKED: %s tried %s", ROLE, tool_name)
                    continue
                else:
                    log_tool_call(ROLE, tool_name, allowed=True)

            # === INTERCEPT: tools/list ===
            if method == "tools/list":
                # Forward request, then filter response
                proc.stdin.write(json.dumps(request) + "\n")
                proc.stdin.flush()
                resp_line = proc.stdout.readline()
                if resp_line:
                    try:
                        response = json.loads(resp_line)
                        filtered = filter_tools_list(response)
                        sys.stdout.write(json.dumps(filtered) + "\n")
                    except json.JSONDecodeError:
                        sys.stdout.write(resp_line)
                    sys.stdout.flush()
                continue

            # === PASS THROUGH: everything else ===
            proc.stdin.write(json.dumps(request) + "\n")
            proc.stdin.flush()
            resp_line = proc.stdout.readline()
            if resp_line:
                sys.stdout.write(resp_line)
                sys.stdout.flush()

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except BrokenPipeError:
        logger.info("Pipe closed, shutting down...")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        logger.info("MCP wrapper stopped")


if __name__ == "__main__":
    main()
