"""LangSmith Observability Tools - 3 tools to query LangGraph traces."""

import os
from typing import Any, Optional

import httpx

LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "nuzantara-rag")
LANGSMITH_BASE = "https://api.smith.langchain.com"

# Persistent HTTP client for LangSmith API (Golden Rule #10)
_ls_client: Optional[httpx.AsyncClient] = None


def _get_ls_client() -> httpx.AsyncClient:
    """Get or create persistent LangSmith HTTP client."""
    global _ls_client
    if _ls_client is None or _ls_client.is_closed:
        _ls_client = httpx.AsyncClient(
            base_url=LANGSMITH_BASE,
            timeout=15,
            headers={"x-api-key": LANGSMITH_API_KEY},
            limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
        )
    return _ls_client


async def _ls_get(path: str, params: Optional[dict] = None) -> Any:
    """Authenticated GET to LangSmith API."""
    client = _get_ls_client()
    resp = await client.get(path, params=params)
    resp.raise_for_status()
    return resp.json()


def register(mcp, _call, _call_safe):
    @mcp.tool()
    async def langsmith_recent_runs(limit: int = 10, error_only: bool = False) -> dict:
        """
        Fetch recent LangGraph traces from LangSmith for nuzantara-rag project.

        Use this to debug RAG pipeline issues, check error rates, or verify
        that recent queries are being traced correctly.

        Args:
            limit: Number of runs to return (default 10, max 50)
            error_only: If True, return only failed/error runs

        Returns:
            List of recent runs with id, name, status, latency, token usage.
        """
        try:
            params: dict = {
                "project_name": LANGSMITH_PROJECT,
                "limit": min(limit, 50),
                "is_root": True,
            }
            if error_only:
                params["error"] = True

            data = await _ls_get("/runs", params=params)
            runs = data if isinstance(data, list) else data.get("runs", [])

            return {
                "project": LANGSMITH_PROJECT,
                "count": len(runs),
                "runs": [
                    {
                        "id": r.get("id"),
                        "name": r.get("name"),
                        "status": r.get("status"),
                        "error": r.get("error"),
                        "latency_ms": round((r.get("total_time") or 0) * 1000),
                        "prompt_tokens": r.get("prompt_tokens"),
                        "completion_tokens": r.get("completion_tokens"),
                        "start_time": r.get("start_time"),
                    }
                    for r in runs
                ],
            }
        except Exception as e:
            return {"error": str(e), "project": LANGSMITH_PROJECT}

    @mcp.tool()
    async def langsmith_run_detail(run_id: str) -> dict:
        """
        Get full detail of a specific LangSmith run including child nodes.

        Use this to inspect exactly what happened in a LangGraph execution:
        which nodes ran, what inputs/outputs each node received, where errors occurred.

        Args:
            run_id: The run UUID from langsmith_recent_runs

        Returns:
            Full run detail with inputs, outputs, child runs per node.
        """
        try:
            run = await _ls_get(f"/runs/{run_id}")

            # Fetch child runs (individual LangGraph nodes)
            children_data = await _ls_get("/runs", params={"parent_run": run_id, "limit": 20})
            children = children_data if isinstance(children_data, list) else children_data.get("runs", [])

            return {
                "id": run.get("id"),
                "name": run.get("name"),
                "status": run.get("status"),
                "error": run.get("error"),
                "inputs": run.get("inputs"),
                "outputs": run.get("outputs"),
                "latency_ms": round((run.get("total_time") or 0) * 1000),
                "prompt_tokens": run.get("prompt_tokens"),
                "completion_tokens": run.get("completion_tokens"),
                "start_time": run.get("start_time"),
                "nodes": [
                    {
                        "name": c.get("name"),
                        "status": c.get("status"),
                        "error": c.get("error"),
                        "latency_ms": round((c.get("total_time") or 0) * 1000),
                    }
                    for c in children
                ],
            }
        except Exception as e:
            return {"error": str(e), "run_id": run_id}

    @mcp.tool()
    async def langsmith_project_stats() -> dict:
        """
        Get aggregate stats for the nuzantara-rag LangSmith project.

        Returns error rate, average latency, total runs, and token usage
        for the last 100 runs. Use this for a quick health check of the
        RAG pipeline observability.

        Returns:
            Aggregate stats: total_runs, error_rate, avg_latency_ms, total_tokens.
        """
        try:
            data = await _ls_get(
                "/runs",
                params={"project_name": LANGSMITH_PROJECT, "limit": 100, "is_root": True},
            )
            runs = data if isinstance(data, list) else data.get("runs", [])

            if not runs:
                return {"project": LANGSMITH_PROJECT, "total_runs": 0, "message": "No runs yet"}

            errors = sum(1 for r in runs if r.get("status") == "error")
            latencies = [
                (r.get("total_time") or 0) * 1000 for r in runs if r.get("total_time")
            ]
            tokens = sum(
                (r.get("prompt_tokens") or 0) + (r.get("completion_tokens") or 0)
                for r in runs
            )

            return {
                "project": LANGSMITH_PROJECT,
                "total_runs": len(runs),
                "error_count": errors,
                "error_rate_pct": round(errors / len(runs) * 100, 1),
                "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else 0,
                "total_tokens": tokens,
                "url": f"https://smith.langchain.com/projects/{LANGSMITH_PROJECT}",
            }
        except Exception as e:
            return {"error": str(e), "project": LANGSMITH_PROJECT}
