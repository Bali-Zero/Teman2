"""
Mata Garuda — Tavily retrieval adapter.

Tavily research API (https://api.tavily.com/search) — retrieval-only
per Legge 1. Env: TAVILY_API_KEY. When unset, returns "missing key".
CLI-only: curl subprocess.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from typing import Any

logger = logging.getLogger("mata_garuda.tools.tavily")

TAVILY_URL = "https://api.tavily.com/search"
TIMEOUT_S = 20


def run_tavily_search(query: str, max_results: int = 10) -> dict[str, Any]:
    """Run a single Tavily search. Returns {"ok":bool, "results":[...], "reason"}."""
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        return {"ok": False, "results": [], "reason": "TAVILY_API_KEY missing"}

    payload = json.dumps(
        {"api_key": key, "query": query, "max_results": int(max_results)}
    )
    try:
        proc = subprocess.run(
            [
                "curl", "-sS",
                "-X", "POST", TAVILY_URL,
                "-H", "Content-Type: application/json",
                "--data", payload,
                "--max-time", str(TIMEOUT_S),
                "-w", "\n__HTTP_CODE__%{http_code}",
            ],
            capture_output=True, text=True, timeout=TIMEOUT_S + 5,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "results": [], "reason": "tavily timeout"}
    except FileNotFoundError:
        return {"ok": False, "results": [], "reason": "curl missing"}

    body = proc.stdout
    marker = "\n__HTTP_CODE__"
    code = 0
    if marker in body:
        idx = body.rfind(marker)
        try:
            code = int(body[idx + len(marker):].strip())
        except ValueError:
            code = 0
        body = body[:idx]

    if code >= 400 or code == 0:
        return {"ok": False, "results": [], "reason": f"tavily HTTP {code}"}

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {"ok": False, "results": [], "reason": "tavily non-json body"}

    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        return {"ok": False, "results": [], "reason": "tavily unexpected shape"}

    return {"ok": True, "results": results, "reason": ""}
