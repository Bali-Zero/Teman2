"""
Mata Garuda — Exa retrieval adapter.

Exa provides semantic web search via https://api.exa.ai/search. This
adapter is retrieval-only (permitted per Legge 1: API ok for retrieval,
vietate solo per LLM). CLI-only still applies — we use curl subprocess.

Env: EXA_API_KEY. When unset, `run_exa_search` returns "missing key"
so the agent reports case_not_resolved without crashing.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from typing import Any

logger = logging.getLogger("mata_garuda.tools.exa")

EXA_URL = "https://api.exa.ai/search"
TIMEOUT_S = 20


def run_exa_search(query: str, num_results: int = 10) -> dict[str, Any]:
    """Run a single Exa search. Returns {"ok": bool, "results":[...], "reason"}."""
    key = os.environ.get("EXA_API_KEY")
    if not key:
        return {"ok": False, "results": [], "reason": "EXA_API_KEY missing"}

    payload = json.dumps({"query": query, "numResults": int(num_results)})
    try:
        proc = subprocess.run(
            [
                "curl", "-sS",
                "-X", "POST", EXA_URL,
                "-H", "Content-Type: application/json",
                "-H", f"x-api-key: {key}",
                "--data", payload,
                "--max-time", str(TIMEOUT_S),
                "-w", "\n__HTTP_CODE__%{http_code}",
            ],
            capture_output=True, text=True, timeout=TIMEOUT_S + 5,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "results": [], "reason": "exa timeout"}
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
        return {"ok": False, "results": [], "reason": f"exa HTTP {code}"}

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {"ok": False, "results": [], "reason": "exa non-json body"}

    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        return {"ok": False, "results": [], "reason": "exa unexpected shape"}

    return {"ok": True, "results": results, "reason": ""}
