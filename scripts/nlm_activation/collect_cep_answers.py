#!/usr/bin/env python3
"""Collect RAG answers for the CEP golden set — Stage 5 of activation runbook.

Iterates the golden_v20260425.json query list, fires each against the prod
RAG endpoint, and emits a JSON file mapping query_id -> answer_text suitable
for run_cep.py --answers-file.

Usage:
    python scripts/nlm_activation/collect_cep_answers.py \\
        --golden apps/evaluator/cep/golden_v20260425.json \\
        --endpoint https://nuzantara-rag.fly.dev \\
        --out /tmp/cep-answers-$(date +%F).json

Auth: set NUZANTARA_RAG_TOKEN env var if the endpoint requires Bearer auth.

Throttles 2s between requests to be polite to the prod endpoint. Tolerates
per-query failures (logs + records empty answer; CEP grader treats empty as
miss with notes='no answer').

Vincoli rispettati:
  - Anthropic OAuth-only (Golden Rule #13): no Anthropic API key.
  - Pure HTTP client to YOUR own RAG endpoint — no third-party API.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger("collect_cep_answers")


def fetch_answer(
    endpoint: str,
    query: str,
    *,
    token: str | None = None,
    timeout: int = 30,
) -> str:
    """POST a query to the RAG endpoint, return the answer text.

    Endpoint is assumed to expose POST /api/rag/query with payload:
      {"query": "..."}
    and response shape (worst case, defensive parsing):
      {"answer": "..."} OR {"value": {"answer": "..."}} OR {"text": "..."}
    """
    body = json.dumps({"query": query}).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(
        endpoint.rstrip("/") + "/api/rag/query",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        logger.warning("HTTP %d on query %r: %s", exc.code, query[:50], exc.reason)
        return ""
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning("Fetch failed for %r: %s", query[:50], exc)
        return ""

    # Defensive: try common shapes
    if isinstance(payload, dict):
        for key in ("answer", "text", "response"):
            v = payload.get(key)
            if isinstance(v, str) and v:
                return v
        # Wrapped under "value"
        inner = payload.get("value")
        if isinstance(inner, dict):
            for key in ("answer", "text", "response"):
                v = inner.get(key)
                if isinstance(v, str) and v:
                    return v
    return ""


def collect(
    golden_path: Path,
    endpoint: str,
    *,
    token: str | None = None,
    delay_seconds: float = 2.0,
) -> dict[str, str]:
    """Iterate the golden set and return {query_id: answer}."""
    golden = json.loads(golden_path.read_text())
    answers: dict[str, str] = {}
    total = sum(len(qs) for qs in golden.get("domains", {}).values())
    idx = 0
    for domain, queries in golden.get("domains", {}).items():
        for q in queries:
            idx += 1
            qid = q["id"]
            text = q["query"]
            logger.info("[%d/%d] %s/%s", idx, total, domain, qid)
            answers[qid] = fetch_answer(endpoint, text, token=token)
            time.sleep(delay_seconds)
    return answers


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        description="Collect RAG answers for CEP grading (Stage 5)"
    )
    parser.add_argument(
        "--golden",
        default="apps/evaluator/cep/golden_v20260425.json",
        help="Path to versioned golden set",
    )
    parser.add_argument(
        "--endpoint",
        default=os.environ.get("NUZANTARA_RAG_ENDPOINT", "https://nuzantara-rag.fly.dev"),
        help="RAG endpoint base URL (env NUZANTARA_RAG_ENDPOINT, default Fly prod)",
    )
    parser.add_argument(
        "--out", required=True,
        help="Output JSON file (query_id -> answer_text) for run_cep --answers-file",
    )
    parser.add_argument(
        "--delay", type=float, default=2.0,
        help="Seconds between queries (rate limiting, default 2.0)",
    )
    args = parser.parse_args()

    token = os.environ.get("NUZANTARA_RAG_TOKEN") or None
    answers = collect(
        Path(args.golden),
        args.endpoint,
        token=token,
        delay_seconds=args.delay,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(answers, ensure_ascii=False, indent=2))

    non_empty = sum(1 for v in answers.values() if v)
    logger.info("Wrote %d answers (%d non-empty) to %s", len(answers), non_empty, out_path)
    sys.exit(0 if non_empty > 0 else 1)


if __name__ == "__main__":
    main()
