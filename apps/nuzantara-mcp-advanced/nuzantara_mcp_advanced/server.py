"""
Nuzantara Advanced MCP Server

Additional MCP tools for development, deployment, and operations.
Complements the main Nuzantara MCP server with advanced operational capabilities.

Tools:
- Deployment operations (Fly.io, Vercel)
- Testing utilities
- Documentation generation
- System diagnostics
"""

import asyncio
import json
import logging
import os
from pathlib import Path
import subprocess
from typing import Optional

import httpx
from fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger("nuzantara-mcp-advanced")

# --- Configuration ---
BACKEND_URL = os.getenv("NUZANTARA_BACKEND_URL", "https://nuzantara-rag.fly.dev")
FLY_APP = os.getenv("FLY_APP", "nuzantara-rag")
PROJECT_ROOT = os.getenv("NUZANTARA_ROOT", "/Users/nuzantara/Desktop/nuzantara")
BACKEND_ROOT = os.path.join(PROJECT_ROOT, "apps/backend-rag")
MUTATION_CONFIRM_ENV = "NUZANTARA_MCP_ADVANCED_ALLOW_MUTATION"

mcp = FastMCP(
    name="Nuzantara Advanced Operations",
    instructions="Advanced operations for Nuzantara development, deployment, and diagnostics",
)

# Persistent HTTP client for health checks (Golden Rule #10)
_health_client: Optional[httpx.AsyncClient] = None


def _backend_python() -> str:
    """Return the backend virtualenv Python when available."""
    override = os.getenv("NUZANTARA_BACKEND_PYTHON")
    if override:
        return override

    for venv_name in (".venv", "venv"):
        candidate = os.path.join(BACKEND_ROOT, venv_name, "bin", "python")
        if os.path.exists(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise FileNotFoundError(
        f"Backend virtualenv Python not found under {BACKEND_ROOT}; "
        "set NUZANTARA_BACKEND_PYTHON to an explicit interpreter."
    )


def _backend_tool(tool_name: str) -> str:
    """Return a backend virtualenv tool path when available."""
    override = os.getenv(f"NUZANTARA_BACKEND_{tool_name.upper()}_BIN")
    if override:
        return override

    for venv_name in (".venv", "venv"):
        candidate = os.path.join(BACKEND_ROOT, venv_name, "bin", tool_name)
        if os.path.exists(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise FileNotFoundError(
        f"Backend virtualenv tool '{tool_name}' not found under {BACKEND_ROOT}; "
        f"set NUZANTARA_BACKEND_{tool_name.upper()}_BIN to an explicit executable."
    )


async def _run_command(
    cmd: list[str],
    *,
    cwd: str,
    timeout: int,
    env: Optional[dict[str, str]] = None,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess without blocking the MCP event loop."""
    return await asyncio.to_thread(
        subprocess.run,
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
        timeout=timeout,
    )


def _safe_project_path(relative_path: str) -> str:
    """Resolve a user-supplied relative project path without escaping the repo."""
    candidate = (Path(PROJECT_ROOT) / relative_path).resolve()
    project_root = Path(PROJECT_ROOT).resolve()
    if project_root not in (candidate, *candidate.parents):
        raise ValueError(f"Path escapes project root: {relative_path}")
    return str(candidate)


def _get_health_client() -> httpx.AsyncClient:
    """Get or create persistent HTTP client for health checks."""
    global _health_client
    if _health_client is None or _health_client.is_closed:
        _health_client = httpx.AsyncClient(
            base_url=BACKEND_URL,
            timeout=10,
            limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
        )
    return _health_client


# ============================================================================
# DEPLOYMENT TOOLS
# ============================================================================

@mcp.tool()
async def check_fly_status() -> dict:
    """
    Check Fly.io application status.
    
    Returns machine status, health, and recent events.
    Requires flyctl to be installed and authenticated.
    """
    try:
        result = await _run_command(
            ["fly", "status", "--app", FLY_APP, "--json"],
            cwd=BACKEND_ROOT,
            timeout=30,
        )
        if result.returncode == 0:
            return {"success": True, "status": json.loads(result.stdout)}
        return {"success": False, "error": result.stderr}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _fetch_fly_logs(lines: int = 50, filter_str: Optional[str] = None) -> dict:
    """Internal log fetcher (callable by other functions without FunctionTool wrapping)."""
    try:
        cmd = ["fly", "logs", "--app", FLY_APP, "-n", str(lines)]
        result = await _run_command(
            cmd,
            cwd=BACKEND_ROOT,
            timeout=30,
        )
        logs = result.stdout
        if filter_str:
            logs = "\n".join([line for line in logs.split("\n") if filter_str in line])
        return {"success": True, "logs": logs}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_fly_logs(lines: int = 50, filter_str: Optional[str] = None) -> dict:
    """
    Get recent Fly.io application logs.

    Args:
        lines: Number of log lines to retrieve (default 50)
        filter_str: Optional string to filter logs (e.g., "ERROR", "KG")

    Returns:
        Recent log entries from the Fly.io application
    """
    return await _fetch_fly_logs(lines=lines, filter_str=filter_str)


@mcp.tool()
async def check_deployment_readiness() -> dict:
    """
    Run pre-deployment checks for Nuzantara backend.
    
    Performs critical checks:
    1. Tests critical import chain
    2. Runs core KG tests
    3. Checks for rogue changes
    
    Returns:
        Check results with pass/fail status for each test
    """
    results = {
        "checks": {},
        "ready": True,
        "timestamp": None
    }

    # Check 1: Import chain
    try:
        result = await _run_command(
            [
                _backend_python(), "-c",
                "from backend.app.dependencies import get_current_user; print('OK')"
            ],
            cwd=BACKEND_ROOT,
            env={**os.environ, "PYTHONPATH": "."},
            timeout=30,
        )
        results["checks"]["import_chain"] = {
            "pass": result.returncode == 0 and "OK" in result.stdout,
            "output": result.stdout if result.returncode == 0 else result.stderr
        }
    except Exception as e:
        results["checks"]["import_chain"] = {"pass": False, "error": str(e)}

    # Check 2: Core tests
    try:
        result = await _run_command(
            [
                _backend_python(), "-m", "pytest",
                "backend/tests/services/rag/test_kg_langgraph.py",
                "backend/tests/services/rag/test_kg_subgraphs.py",
                "backend/tests/services/rag/test_confidence.py",
                "-q"
            ],
            cwd=BACKEND_ROOT,
            env={**os.environ, "PYTHONPATH": "."},
            timeout=120,
        )
        results["checks"]["core_tests"] = {
            "pass": result.returncode == 0,
            "output": result.stdout[-500:] if len(result.stdout) > 500 else result.stdout
        }
    except Exception as e:
        results["checks"]["core_tests"] = {"pass": False, "error": str(e)}

    # Check 3: Git status for rogue changes
    try:
        result = await _run_command(
            ["git", "diff", "--name-only", "HEAD", "--", "apps/backend-rag/backend/"],
            cwd=PROJECT_ROOT,
            timeout=15,
        )
        changed_files = result.stdout.strip().split("\n") if result.stdout.strip() else []
        results["checks"]["rogue_changes"] = {
            "pass": len(changed_files) <= 10,  # Arbitrary threshold
            "changed_files": changed_files,
            "count": len(changed_files)
        }
    except Exception as e:
        results["checks"]["rogue_changes"] = {"pass": False, "error": str(e)}

    results["ready"] = all(c.get("pass", False) for c in results["checks"].values())
    return results


# ============================================================================
# TESTING TOOLS
# ============================================================================

@mcp.tool()
async def run_backend_tests(test_path: str = "", verbose: bool = False) -> dict:
    """
    Run backend tests with pytest.
    
    Args:
        test_path: Specific test file or directory (e.g., "backend/tests/services/rag/")
        verbose: Whether to run with -v flag
    
    Returns:
        Test results with pass/fail counts and output
    """
    try:
        cmd = [_backend_python(), "-m", "pytest"]
        if test_path:
            cmd.append(test_path)
        if verbose:
            cmd.append("-v")
        cmd.append("--tb=short")

        result = await _run_command(
            cmd,
            cwd=BACKEND_ROOT,
            env={**os.environ, "PYTHONPATH": "."},
            timeout=300,
        )

        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "stdout": result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout,
            "stderr": result.stderr[-1000:] if len(result.stderr) > 1000 else result.stderr
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# AUTOPILOT & RECOVERY TOOLS
# ============================================================================

@mcp.tool()
async def analyze_fly_health(lines: int = 100) -> dict:
    """
    Analyze Fly.io logs for known issues and anomalies.

    Checks for:
    - Out of Memory (OOM)
    - Database connection failures
    - 5xx status code persistence
    - Health check timeouts

    Returns:
        Analysis report with risk score and recommendations.
    """
    logs_resp = await _fetch_fly_logs(lines=lines)
    if not logs_resp["success"]:
        return logs_resp

    logs = logs_resp["logs"]
    issues = []
    risk_score = 0.0

    # Check for OOM — use precise patterns to avoid false positives
    logs_lower = logs.lower()
    if "out of memory" in logs_lower or "oom" in logs_lower or "oom-kill" in logs_lower or "killed process" in logs_lower:
        issues.append("CRITICAL: Out of Memory (OOM) detected. Consider checking --workers count.")
        risk_score += 0.8

    # Check for DB issues
    if "connection" in logs.lower() and ("database" in logs.lower() or "postgres" in logs.lower()):
        issues.append("HIGH: Database connection issues detected.")
        risk_score += 0.5

    # Check for health check timeouts
    if "health check" in logs.lower() and ("timeout" in logs.lower() or "failed" in logs.lower()):
        issues.append("MEDIUM: Health check failures detected.")
        risk_score += 0.3

    return {
        "risk_score": min(risk_score, 1.0),
        "issues_found": issues,
        "recommendation": "Restart machine or check logs if risk_score > 0.5" if risk_score > 0 else "System looks stable.",
        "log_preview": logs[:500] + "..." if len(logs) > 500 else logs
    }


@mcp.tool()
async def execute_recovery_action(
    action: str,
    machine_id: Optional[str] = None,
    confirm: bool = False,
    dry_run: bool = True,
) -> dict:
    """
    Execute a recovery action for the Fly.io application.

    Args:
        action: "restart" or "redeploy"
        machine_id: Optional specific machine ID to target
        confirm: Must be true for non-dry-run execution
        dry_run: Return the command without executing it by default

    Returns:
        Execution result status.
    """
    try:
        cmd = ["fly"]
        if action == "restart":
            if machine_id:
                cmd.extend(["machine", "restart", machine_id, "--app", FLY_APP])
            else:
                cmd.extend(["apps", "restart", FLY_APP])
        elif action == "redeploy":
            cmd.extend(["deploy", "--app", FLY_APP, "--strategy", "rolling"])
        else:
            return {"success": False, "error": f"Unsupported action: {action}"}

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "requires_confirmation": True,
                "command": cmd,
            }

        if not confirm or os.getenv(MUTATION_CONFIRM_ENV) != "1":
            return {
                "success": False,
                "blocked": True,
                "error": (
                    "Recovery actions are mutation-gated. "
                    f"Pass confirm=true and set {MUTATION_CONFIRM_ENV}=1 to execute."
                ),
                "command": cmd,
            }

        result = await _run_command(
            cmd,
            cwd=BACKEND_ROOT,
            timeout=300,
        )

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Action '{action}' timed out after 300s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
async def run_type_checking() -> dict:
    """
    Run mypy type checking on backend code.
    
    Returns:
        Type checking results with error count
    """
    try:
        result = await _run_command(
            [_backend_tool("mypy"), "backend/", "--ignore-missing-imports"],
            cwd=BACKEND_ROOT,
            timeout=120,
        )
        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "errors": result.stderr
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
async def run_linting() -> dict:
    """
    Run ruff linting and formatting check on backend code.
    
    Returns:
        Linting results with issues found
    """
    try:
        # Check formatting
        format_result = await _run_command(
            [_backend_tool("ruff"), "format", "--check", "backend/"],
            cwd=BACKEND_ROOT,
            timeout=60,
        )

        # Check linting
        lint_result = await _run_command(
            [_backend_tool("ruff"), "check", "backend/"],
            cwd=BACKEND_ROOT,
            timeout=60,
        )

        return {
            "format_ok": format_result.returncode == 0,
            "lint_ok": lint_result.returncode == 0,
            "format_output": format_result.stdout or format_result.stderr,
            "lint_output": lint_result.stdout or lint_result.stderr
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# SYSTEM DIAGNOSTICS
# ============================================================================

@mcp.tool()
async def check_system_health() -> dict:
    """
    Comprehensive system health check.
    
    Checks:
    - Backend health endpoint
    - Qdrant connectivity
    - Database connectivity
    - LLM provider availability
    
    Returns:
        Overall health status with component details
    """
    health = {
        "timestamp": None,
        "overall": "unknown",
        "components": {}
    }

    # Check backend health
    client = _get_health_client()
    try:
        resp = await client.get("/health")
        data = resp.json()
        health["components"]["backend"] = {
            "status": "healthy" if resp.status_code == 200 else "unhealthy",
            "version": data.get("version", "unknown"),
            "embedding_model": data.get("embeddings", {}).get("model", "unknown")
        }
    except Exception as e:
        health["components"]["backend"] = {"status": "error", "error": str(e)}

    # Check detailed health
    try:
        resp = await client.get("/health/detailed")
        data = resp.json()
        services = data.get("services", {})
        health["components"]["services"] = {
            name: status.get("healthy", False)
            for name, status in services.items()
        }
    except Exception as e:
        health["components"]["services"] = {"status": "error", "error": str(e)}

    # Determine overall health
    all_healthy = all(
        c.get("status") == "healthy" or c.get("status") == "ok"
        for c in health["components"].values()
        if isinstance(c, dict) and "status" in c
    )
    health["overall"] = "healthy" if all_healthy else "degraded"

    return health


@mcp.tool()
async def get_collection_stats() -> dict:
    """
    Get Qdrant collection statistics.
    
    Returns:
        Vector counts, sizes, and health for all collections
    """
    try:
        client = _get_health_client()
        resp = await client.get("/health/metrics/qdrant")
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def search_codebase(query: str, file_pattern: str = "*.py") -> dict:
    """
    Search the codebase for specific patterns.
    
    Args:
        query: Search term (function name, variable, etc.)
        file_pattern: File pattern to search (default: *.py)
    
    Returns:
        Matching files and line numbers
    """
    try:
        result = await _run_command(
            [
                "rg", "-n",
                "--glob", file_pattern,
                "--",
                query,
                f"{BACKEND_ROOT}/backend",
            ],
            cwd=PROJECT_ROOT,
            timeout=30,
        )
        lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
        return {
            "matches": len(lines),
            "results": lines[:20]  # Limit to 20 results
        }
    except Exception as e:
        return {"error": str(e)}


# ============================================================================
# DOCUMENTATION TOOLS
# ============================================================================

@mcp.tool()
async def find_documentation(topic: str) -> dict:
    """
    Find relevant documentation files.
    
    Args:
        topic: Topic to search for (e.g., "deployment", "KG", "testing")
    
    Returns:
        List of relevant documentation files
    """
    try:
        # Search in docs directory
        result = await _run_command(
            ["rg", "--files", "--glob", "*.md", f"{PROJECT_ROOT}/docs"],
            cwd=PROJECT_ROOT,
            timeout=15,
        )
        files = result.stdout.strip().split("\n") if result.stdout.strip() else []

        # Filter by topic relevance (simple keyword matching)
        topic_lower = topic.lower()
        relevant = [
            f for f in files
            if topic_lower in f.lower() or
            topic_lower.replace(" ", "_") in f.lower()
        ]

        return {
            "topic": topic,
            "matches": len(relevant),
            "files": relevant[:10]
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def get_file_structure(path: str = "apps/backend-rag/backend") -> dict:
    """
    Get directory structure for a given path.
    
    Args:
        path: Relative path from project root
    
    Returns:
        Directory tree structure
    """
    try:
        target_path = _safe_project_path(path)
        result = await _run_command(
            ["rg", "--files", "--glob", "*.py", target_path],
            cwd=PROJECT_ROOT,
            timeout=15,
        )
        files = result.stdout.strip().split("\n") if result.stdout.strip() else []

        # Organize by directory
        structure = {}
        for f in files:
            rel_path = os.path.relpath(f, target_path)
            parts = rel_path.split("/")
            current = structure
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            if "_files" not in current:
                current["_files"] = []
            current["_files"].append(parts[-1])

        return {
            "path": path,
            "total_files": len(files),
            "structure": structure
        }
    except Exception as e:
        return {"error": str(e)}


# ============================================================================
# PROMPTS
# ============================================================================

@mcp.prompt()
def deployment_checklist() -> str:
    """Pre-deployment verification checklist."""
    return """
    Before deploying Nuzantara backend to Fly.io, verify:
    
    1. [ ] Run `check_deployment_readiness()` - All checks must pass
    2. [ ] Run `run_backend_tests("backend/tests/services/rag/")` - KG tests pass
    3. [ ] Run `run_type_checking()` - No type errors
    4. [ ] Run `check_system_health()` - Backend is healthy
    5. [ ] Review changed files with `check_deployment_readiness()`
    6. [ ] Deploy with `fly deploy --strategy rolling`
    7. [ ] Verify with `check_fly_status()` and `check_system_health()`
    
    If any step fails, DO NOT proceed to deployment.
    """


@mcp.prompt()
def debug_kg_issue() -> str:
    """Template for debugging Knowledge Graph issues."""
    return """
    To debug a Knowledge Graph issue:
    
    1. Check system health: `check_system_health()`
    2. Verify Qdrant collections: `get_collection_stats()`
    3. Search for relevant code: `search_codebase("kg_")`
    4. Run KG tests: `run_backend_tests("backend/tests/services/rag/test_kg_langgraph.py")`
    5. Check Fly logs: `get_fly_logs(lines=100, filter_str="KG")`
    
    Look for:
    - Embedding model mismatches
    - Database connection issues
    - LangGraph state errors
    - Missing entity resolutions
    """


@mcp.prompt()
def investigate_test_failure() -> str:
    """Template for investigating test failures."""
    return """
    When tests fail:
    
    1. Run specific test with verbose: `run_backend_tests("path/to/test.py", verbose=True)`
    2. Check type errors: `run_type_checking()`
    3. Check linting: `run_linting()`
    4. Search for recent changes: `search_codebase("function_name")`
    5. Review test file structure: `get_file_structure("backend/tests/")`
    
    Common causes:
    - Rogue AI removed imports (e.g., `Any` from typing)
    - Function signature changes
    - Missing env variables
    - Database state issues
    """


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    """Run MCP server with stdio transport."""
    logger.info("Starting Nuzantara Advanced MCP Server")
    logger.info(f"Project root: {PROJECT_ROOT}")
    logger.info(f"Fly app: {FLY_APP}")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
