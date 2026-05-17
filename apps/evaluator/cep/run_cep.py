#!/usr/bin/env python3
"""Sprint 2 CEP — Continuous Evaluation Pipeline.

Runs the versioned golden query set against a target answer source
(``--answers-file`` JSON map, thin HTTP backend source, or stub for
dry-run), optionally grades each result with DeepSeek V4 Pro (Think Max
mode) against the rubric (required_facts), and emits a CSV report +
summary suitable for cron + Telegram alerting.

Why DeepSeek as evaluator:
  - Cheap (~$0.01/query) — 50 queries × 4 runs/day = ~$60/month, in
    budget.
  - Reasoning-capable, follows JSON-strict rubric prompts well.
  - Independent from Claude (avoids self-grading bias if Claude is the
    answer source).

Activation later via cron once the answer source is wired
(``apps/backend-rag`` query endpoint or shadow retrieval).

Usage:
    # Dry-run on synthetic answers (CI smoke)
    python -m apps.evaluator.cep.run_cep --golden golden_v20260425.json --dry-run

    # Collect answers from a live/shadow backend without paid evaluation
    python -m apps.evaluator.cep.run_cep \\
        --golden golden_v20260425.json \\
        --backend-url http://localhost:8000 \\
        --report /tmp/cep-answers-$(date +%F).csv

    # Real run with pre-collected answers JSON and explicit paid evaluator
    python -m apps.evaluator.cep.run_cep \\
        --golden golden_v20260425.json \\
        --answers-file /tmp/cep-answers.json \\
        --enable-evaluator \\
        --report /tmp/cep-report-$(date +%F).csv
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import json
import logging
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin

import httpx

logger = logging.getLogger("cep")

DEEPSEEK_RUBRIC_PROMPT = (
    "You are an evaluator scoring a RAG answer against a rubric of "
    "required facts. Reply with strict JSON only — no prose.\n\n"
    "Question: {query}\n\n"
    "Required facts (the answer should cover ALL of these): {facts}\n\n"
    "Answer to grade:\n{answer}\n\n"
    "Reply with: {{\"hit\": true|false, \"facts_covered\": int, "
    "\"facts_total\": int, \"contradiction\": true|false, "
    "\"notes\": \"short\"}}.\n"
    "hit=true ONLY if facts_covered == facts_total AND contradiction==false."
)


@dataclass(frozen=True)
class BackendAnswerSourceConfig:
    """Thin HTTP answer-source configuration for live/shadow RAG backends."""

    base_url: str
    endpoint: str = "/api/agentic-rag/query"
    api_key_env: str | None = None
    timeout: float = 30.0
    transport: httpx.BaseTransport | None = None


@dataclass(frozen=True)
class AnswerSourceResult:
    """Resolved answer text plus source metadata for one golden query."""

    answer: str
    answer_source: str
    source_error: str | None = None


def load_golden(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def iter_queries(golden: dict[str, Any]):
    """Yield (domain, query_dict) tuples in stable order."""
    for domain, queries in golden.get("domains", {}).items():
        for q in queries:
            yield domain, q


def _short_error(value: Any) -> str:
    return " ".join(str(value).split())[:200]


def _join_backend_url(base_url: str, endpoint: str) -> str:
    """Join a backend base URL and endpoint without importing backend code."""
    return urljoin(f"{base_url.rstrip('/')}/", endpoint.lstrip("/"))


def _extract_answer_text(payload: dict[str, Any]) -> str:
    """Extract answer text from common RAG/shadow response shapes."""
    if payload.get("success") is False:
        error = payload.get("error") or payload.get("warning") or "backend returned success=false"
        raise ValueError(f"backend success=false: {_short_error(error)}")

    containers: list[dict[str, Any]] = [payload]
    for nested_key in ("data", "result"):
        nested = payload.get(nested_key)
        if isinstance(nested, dict):
            containers.append(nested)

    for container in containers:
        for key in ("answer", "response", "final_answer", "text"):
            value = container.get(key)
            if isinstance(value, str) and value.strip():
                return value

    raise ValueError("backend response did not contain an answer field")


def fetch_backend_answer(
    *,
    query_id: str,
    query: str,
    config: BackendAnswerSourceConfig,
) -> AnswerSourceResult:
    """Fetch a single answer through HTTP, returning row-local errors."""
    headers = {"Content-Type": "application/json"}
    if config.api_key_env:
        api_key = os.environ.get(config.api_key_env, "").strip()
        if not api_key:
            return AnswerSourceResult(
                answer="",
                answer_source="backend",
                source_error=f"missing api key env {config.api_key_env}",
            )
        headers["Authorization"] = f"Bearer {api_key}"
        headers["x-api-key"] = api_key

    payload = {
        "query": query,
        "user_id": "cep_eval",
        "session_id": f"cep-{query_id}",
        "conversation_history": [],
    }
    url = _join_backend_url(config.base_url, config.endpoint)

    try:
        with httpx.Client(timeout=config.timeout, transport=config.transport) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            answer = _extract_answer_text(response.json())
        return AnswerSourceResult(answer=answer, answer_source="backend")
    except httpx.HTTPStatusError as exc:
        return AnswerSourceResult(
            answer="",
            answer_source="backend",
            source_error=f"HTTP {exc.response.status_code}: {_short_error(exc.response.text)}",
        )
    except httpx.TimeoutException as exc:
        return AnswerSourceResult(
            answer="",
            answer_source="backend",
            source_error=f"timeout: {_short_error(exc)}",
        )
    except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
        return AnswerSourceResult(
            answer="",
            answer_source="backend",
            source_error=_short_error(exc),
        )


def grade_with_deepseek(
    query: str,
    answer: str,
    required_facts: list[str],
    *,
    api_key: str,
    timeout: int = 60,
) -> dict[str, Any]:
    """Score a single answer against its rubric."""
    body = {
        "model": "deepseek-v4-pro",
        "reasoning_effort": "max",
        "messages": [
            {"role": "system", "content": "You are an evaluator. Reply only strict JSON."},
            {"role": "user", "content": DEEPSEEK_RUBRIC_PROMPT.format(
                query=query, facts=json.dumps(required_facts), answer=answer
            )},
        ],
        "max_tokens": 256,
        "temperature": 0.0,
    }
    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read())
        msg = payload["choices"][0]["message"].get("content", "").strip()
        msg = msg.strip("`").lstrip("json").strip()
        parsed = json.loads(msg)
        return {
            "hit": bool(parsed.get("hit", False)),
            "facts_covered": int(parsed.get("facts_covered", 0)),
            "facts_total": int(parsed.get("facts_total", len(required_facts))),
            "contradiction": bool(parsed.get("contradiction", False)),
            "notes": str(parsed.get("notes", ""))[:200],
            "evaluator_error": None,
        }
    except Exception as exc:
        return {
            "hit": False,
            "facts_covered": 0,
            "facts_total": len(required_facts),
            "contradiction": False,
            "notes": f"evaluator error: {exc}",
            "evaluator_error": str(exc)[:200],
        }


def run_cep(
    golden_path: Path,
    *,
    answers: Optional[dict[str, str]] = None,
    answers_file: Optional[Path] = None,
    dry_run: bool = False,
    report_path: Optional[Path] = None,
    deepseek_key: Optional[str] = None,
    enable_evaluator: bool = False,
    backend_url: Optional[str] = None,
    backend_endpoint: str = "/api/agentic-rag/query",
    backend_api_key_env: Optional[str] = None,
    backend_timeout: float = 30.0,
    backend_transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    """Run the CEP and return aggregate metrics.

    Args:
        golden_path: JSON file with the golden set.
        answers: Pre-supplied {query_id: answer_text} (preferred for tests).
        answers_file: Alternative — JSON file with same shape.
        dry_run: Skip DeepSeek; use a stub answer ("dry-run stub") and
            mark each row as evaluator_error="dry_run". Hit rate = 0.
        report_path: Where to write the CSV report.
        deepseek_key: Explicit API key override. Passing a non-empty key
            enables evaluator calls for programmatic usage.
        enable_evaluator: Explicitly allow paid DeepSeek evaluation via env.
        backend_url: Base URL for a live/shadow answer source.
        backend_endpoint: POST endpoint relative to backend_url.
        backend_api_key_env: Optional env var whose value is sent as bearer
            and x-api-key. Missing env is recorded as source_error.
        backend_timeout: Per-query HTTP timeout in seconds.
        backend_transport: Test hook for httpx.MockTransport.
    """
    golden = load_golden(golden_path)
    answers_loaded_from_file = answers is None and answers_file is not None
    if answers is None and answers_file is not None:
        answers = json.loads(answers_file.read_text())
    answers = answers or {}

    backend_config = None
    if backend_url:
        backend_config = BackendAnswerSourceConfig(
            base_url=backend_url,
            endpoint=backend_endpoint,
            api_key_env=backend_api_key_env,
            timeout=backend_timeout,
            transport=backend_transport,
        )

    explicit_deepseek_key = (deepseek_key or "").strip()
    evaluator_requested = enable_evaluator or bool(explicit_deepseek_key)
    evaluator_key = ""
    if evaluator_requested and not dry_run:
        evaluator_key = explicit_deepseek_key or os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if not evaluator_key:
            logger.warning("DeepSeek evaluator enabled but DEEPSEEK_API_KEY is missing")

    rows: list[dict[str, Any]] = []
    per_domain: dict[str, dict[str, int]] = {}

    for domain, q in iter_queries(golden):
        qid = q["id"]
        source_error = None
        answer_source = "none"
        answer = ""

        if not dry_run and qid in answers:
            answer = str(answers.get(qid) or "")
            answer_source = "answers_file" if answers_loaded_from_file else "supplied_answers"
        elif not dry_run and backend_config is not None:
            source_result = fetch_backend_answer(
                query_id=qid,
                query=q["query"],
                config=backend_config,
            )
            answer = source_result.answer
            answer_source = source_result.answer_source
            source_error = source_result.source_error

        if dry_run:
            grade = {
                "hit": False,
                "facts_covered": 0,
                "facts_total": len(q["required_facts"]),
                "contradiction": False,
                "notes": "dry_run",
                "evaluator_error": "dry_run",
            }
        elif source_error:
            grade = {
                "hit": False,
                "facts_covered": 0,
                "facts_total": len(q["required_facts"]),
                "contradiction": False,
                "notes": f"source error: {source_error}",
                "evaluator_error": None,
            }
        elif not answer:
            grade = {
                "hit": False,
                "facts_covered": 0,
                "facts_total": len(q["required_facts"]),
                "contradiction": False,
                "notes": "no answer provided",
                "evaluator_error": None,
            }
        elif not evaluator_requested:
            grade = {
                "hit": False,
                "facts_covered": 0,
                "facts_total": len(q["required_facts"]),
                "contradiction": False,
                "notes": "evaluator_disabled",
                "evaluator_error": "evaluator_disabled",
            }
        elif not evaluator_key:
            grade = {
                "hit": False,
                "facts_covered": 0,
                "facts_total": len(q["required_facts"]),
                "contradiction": False,
                "notes": "missing DeepSeek API key",
                "evaluator_error": "missing_deepseek_key",
            }
        else:
            grade = grade_with_deepseek(
                q["query"], answer, q["required_facts"],
                api_key=evaluator_key,
            )

        rows.append({
            "domain": domain,
            "id": qid,
            "tier": q.get("tier", 2),
            "query": q["query"],
            "answer_source": answer_source,
            "answer_excerpt": (answer[:200] + "...") if len(answer) > 200 else answer,
            "source_error": source_error,
            "hit": grade["hit"],
            "facts_covered": grade["facts_covered"],
            "facts_total": grade["facts_total"],
            "contradiction": grade["contradiction"],
            "notes": grade["notes"],
            "evaluator_error": grade.get("evaluator_error"),
        })

        bucket = per_domain.setdefault(domain, {"total": 0, "hit": 0})
        bucket["total"] += 1
        if grade["hit"]:
            bucket["hit"] += 1

    total = sum(b["total"] for b in per_domain.values())
    hits = sum(b["hit"] for b in per_domain.values())
    summary = {
        "ts": datetime.now(tz=timezone.utc).isoformat(),
        "golden_version": golden.get("version"),
        "total": total,
        "hits": hits,
        "hit_rate": (hits / total) if total else 0.0,
        "source_errors": sum(1 for row in rows if row["source_error"]),
        "evaluator_errors": sum(1 for row in rows if row["evaluator_error"]),
        "evaluator_enabled": evaluator_requested and not dry_run,
        "per_domain": {
            d: {
                "total": b["total"],
                "hit": b["hit"],
                "hit_rate": (b["hit"] / b["total"]) if b["total"] else 0.0,
            }
            for d, b in per_domain.items()
        },
        "rows": rows,
    }

    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [
                "domain", "id", "tier", "query", "answer_source", "answer_excerpt",
                "source_error", "hit", "facts_covered", "facts_total",
                "contradiction", "notes", "evaluator_error",
            ])
            writer.writeheader()
            writer.writerows(rows)
        logger.info("Wrote CEP report to %s (%d rows)", report_path, len(rows))

    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Sprint 2 CEP — Continuous Evaluation Pipeline")
    parser.add_argument(
        "--golden",
        default=str(Path(__file__).parent / "golden_v20260425.json"),
        help="Path to versioned golden set",
    )
    parser.add_argument(
        "--answers-file", help="JSON file mapping query_id → answer text"
    )
    parser.add_argument(
        "--backend-url",
        help="Base URL for live/shadow backend answer collection",
    )
    parser.add_argument(
        "--endpoint",
        "--backend-endpoint",
        dest="backend_endpoint",
        default="/api/agentic-rag/query",
        help="Backend POST endpoint for answer collection",
    )
    parser.add_argument(
        "--api-key-env",
        "--backend-api-key-env",
        dest="backend_api_key_env",
        help="Env var containing backend API key; sent as bearer and x-api-key",
    )
    parser.add_argument(
        "--backend-timeout",
        type=float,
        default=30.0,
        help="Per-query backend HTTP timeout in seconds",
    )
    parser.add_argument(
        "--enable-evaluator",
        action="store_true",
        help="Enable paid DeepSeek evaluator calls. Disabled by default.",
    )
    parser.add_argument(
        "--report",
        help="CSV report path (default /tmp/cep-report-YYYY-MM-DD.csv)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Skip evaluator calls; emit zero hits with notes='dry_run'",
    )
    args = parser.parse_args()

    report = Path(args.report) if args.report else Path(
        f"/tmp/cep-report-{datetime.now().strftime('%Y-%m-%d')}.csv"
    )

    summary = run_cep(
        Path(args.golden),
        answers_file=Path(args.answers_file) if args.answers_file else None,
        dry_run=args.dry_run,
        report_path=report,
        enable_evaluator=args.enable_evaluator,
        backend_url=args.backend_url,
        backend_endpoint=args.backend_endpoint,
        backend_api_key_env=args.backend_api_key_env,
        backend_timeout=args.backend_timeout,
    )

    # Compact summary to stdout — cron-friendly
    print(json.dumps({
        "ts": summary["ts"],
        "golden_version": summary["golden_version"],
        "total": summary["total"],
        "hits": summary["hits"],
        "hit_rate": round(summary["hit_rate"], 3),
        "source_errors": summary["source_errors"],
        "evaluator_errors": summary["evaluator_errors"],
        "evaluator_enabled": summary["evaluator_enabled"],
        "per_domain": {
            d: round(b["hit_rate"], 3)
            for d, b in summary["per_domain"].items()
        },
        "report": str(report),
    }, indent=2))

    # Exit nonzero on low graded hit rate only when paid evaluation was explicit.
    sys.exit(0 if summary["hit_rate"] >= 0.8 or args.dry_run or not args.enable_evaluator else 1)


if __name__ == "__main__":
    main()
