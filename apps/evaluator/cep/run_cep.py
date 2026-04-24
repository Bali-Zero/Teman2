#!/usr/bin/env python3
"""Sprint 2 CEP — Continuous Evaluation Pipeline.

Runs the versioned golden query set against a target answer source
(``--answers-file`` JSON map, or stub for dry-run), grades each result
with DeepSeek Reasoner against the rubric (required_facts), and emits a
CSV report + summary suitable for cron + Telegram alerting.

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

    # Real run with pre-collected answers JSON
    python -m apps.evaluator.cep.run_cep \\
        --golden golden_v20260425.json \\
        --answers-file /tmp/cep-answers.json \\
        --report /tmp/cep-report-$(date +%F).csv
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

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


def load_golden(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def iter_queries(golden: dict[str, Any]):
    """Yield (domain, query_dict) tuples in stable order."""
    for domain, queries in golden.get("domains", {}).items():
        for q in queries:
            yield domain, q


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
        "model": "deepseek-reasoner",
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
) -> dict[str, Any]:
    """Run the CEP and return aggregate metrics.

    Args:
        golden_path: JSON file with the golden set.
        answers: Pre-supplied {query_id: answer_text} (preferred for tests).
        answers_file: Alternative — JSON file with same shape.
        dry_run: Skip DeepSeek; use a stub answer ("dry-run stub") and
            mark each row as evaluator_error="dry_run". Hit rate = 0.
        report_path: Where to write the CSV report.
        deepseek_key: Override env DEEPSEEK_API_KEY.
    """
    golden = load_golden(golden_path)
    if answers is None and answers_file is not None:
        answers = json.loads(answers_file.read_text())
    answers = answers or {}

    if not dry_run:
        deepseek_key = deepseek_key or os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if not deepseek_key:
            logger.warning("DEEPSEEK_API_KEY missing — running in dry_run mode")
            dry_run = True

    rows: list[dict[str, Any]] = []
    per_domain: dict[str, dict[str, int]] = {}

    for domain, q in iter_queries(golden):
        qid = q["id"]
        answer = answers.get(qid, "")
        if dry_run:
            grade = {
                "hit": False,
                "facts_covered": 0,
                "facts_total": len(q["required_facts"]),
                "contradiction": False,
                "notes": "dry_run",
                "evaluator_error": "dry_run",
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
        else:
            grade = grade_with_deepseek(
                q["query"], answer, q["required_facts"],
                api_key=deepseek_key,  # type: ignore[arg-type]
            )

        rows.append({
            "domain": domain,
            "id": qid,
            "tier": q.get("tier", 2),
            "query": q["query"],
            "answer_excerpt": (answer[:200] + "...") if len(answer) > 200 else answer,
            "hit": grade["hit"],
            "facts_covered": grade["facts_covered"],
            "facts_total": grade["facts_total"],
            "contradiction": grade["contradiction"],
            "notes": grade["notes"],
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
                "domain", "id", "tier", "query", "answer_excerpt",
                "hit", "facts_covered", "facts_total", "contradiction", "notes",
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
    )

    # Compact summary to stdout — cron-friendly
    print(json.dumps({
        "ts": summary["ts"],
        "golden_version": summary["golden_version"],
        "total": summary["total"],
        "hits": summary["hits"],
        "hit_rate": round(summary["hit_rate"], 3),
        "per_domain": {
            d: round(b["hit_rate"], 3)
            for d, b in summary["per_domain"].items()
        },
        "report": str(report),
    }, indent=2))

    # Exit nonzero if hit rate < 0.8 (so cron + sentinel can alert)
    sys.exit(0 if summary["hit_rate"] >= 0.8 or args.dry_run else 1)


if __name__ == "__main__":
    main()
