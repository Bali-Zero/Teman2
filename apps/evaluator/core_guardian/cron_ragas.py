"""
Core Guardian V4 — RAGAS Evaluation Cron Wrapper

Weekly RAG quality evaluation using the judgement_day.py pattern.
Queries 100 Q&A pairs, evaluates faithfulness and relevancy,
compares with previous week's baseline, alerts on quality drop.

Schedule: Sunday 06:00 WITA
Cost: ~$0.50-1.00 (Gemini API for evaluation judge)

Usage:
    python cron_ragas.py                  # full evaluation
    python cron_ragas.py --dry-run        # load dataset, don't evaluate
    python cron_ragas.py --sample 20      # evaluate only 20 random pairs
    python cron_ragas.py --local          # query localhost instead of production
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="[RAGAS %(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("cron_ragas")

# Paths
_THIS_DIR = Path(__file__).resolve().parent
_EVALUATOR_DIR = _THIS_DIR.parent
_PROJECT_ROOT = _THIS_DIR.parent.parent.parent
_DATASET_FILE = _THIS_DIR / "ragas_dataset.json"
_REPORTS_DIR = _PROJECT_ROOT / ".agent" / "decisions" / "ragas_reports"

# Add evaluator to path
if str(_EVALUATOR_DIR) not in sys.path:
    sys.path.insert(0, str(_EVALUATOR_DIR))

# API URLs
PRODUCTION_API = "https://nuzantara-rag.fly.dev"
LOCAL_API = "http://localhost:8000"

# Quality thresholds
MIN_FAITHFULNESS = 0.70
MIN_RELEVANCY = 0.65
DEGRADATION_ALERT_PCT = 10  # Alert if quality drops >10% from previous


async def query_rag(question: str, api_url: str, client: Any = None) -> dict:
    """Query the RAG API and collect answer + contexts.

    Accepts a shared httpx.AsyncClient to avoid creating one per query.
    """
    import os

    import httpx

    api_key = os.environ.get("JUDGEMENT_DAY_API_KEY", "")
    headers = {"x-api-key": api_key} if api_key else {}

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=60.0)

    try:
        response = await client.post(
            f"{api_url}/api/oracle/query",
            json={"query": question, "limit": 5, "use_ai": True},
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

        answer = data.get("answer", "") or data.get("response", {}).get("answer", "")
        sources = data.get("sources", [])
        contexts = [s.get("content", "") for s in sources if s.get("content")]
        if not contexts:
            contexts = data.get("documents", [])[:5]

        return {"question": question, "answer": answer, "contexts": contexts}

    except Exception as e:
        return {"question": question, "answer": f"Error: {e}", "contexts": []}
    finally:
        if owns_client:
            await client.aclose()


def evaluate_faithfulness(answer: str, contexts: list[str]) -> float:
    """Simple faithfulness check: is the answer grounded in contexts?

    Returns 0.0-1.0 score based on keyword overlap between answer and contexts.
    For a more sophisticated evaluation, use RAGAS with Gemini judge.
    """
    if not contexts or not answer:
        return 0.0

    # Combine all contexts
    context_text = " ".join(contexts).lower()
    answer_words = set(answer.lower().split())

    # Remove common stopwords
    stopwords = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for",
                 "of", "and", "or", "yang", "dan", "di", "ke", "dari", "untuk", "dengan", "ini",
                 "itu", "adalah", "the", "be", "have", "do", "will", "can"}
    meaningful_words = answer_words - stopwords

    if not meaningful_words:
        return 0.5  # Can't evaluate

    grounded = sum(1 for w in meaningful_words if w in context_text)
    return min(1.0, grounded / len(meaningful_words))


def evaluate_relevancy(question: str, answer: str) -> float:
    """Simple relevancy check: does the answer address the question?

    Returns 0.0-1.0 score based on question keyword presence in answer.
    """
    if not answer or "Error:" in answer:
        return 0.0

    question_words = set(question.lower().split()) - {"what", "how", "when", "where", "who",
                                                       "which", "apa", "bagaimana", "kapan",
                                                       "dimana", "siapa", "berapa", "?"}
    if not question_words:
        return 0.5

    answer_lower = answer.lower()
    relevant = sum(1 for w in question_words if w in answer_lower)
    return min(1.0, relevant / max(1, len(question_words) * 0.5))


async def run_ragas_evaluation(
    sample_size: int | None = None,
    dry_run: bool = False,
    use_local: bool = False,
) -> dict:
    """Run the RAGAS evaluation cycle."""
    start = datetime.now(timezone.utc)
    run_id = f"ragas-{start.strftime('%Y%m%d%H%M')}"

    logger.info(f"=== RAGAS Evaluation — {run_id} ===")

    # 1. Load dataset
    if not _DATASET_FILE.exists():
        logger.error(f"Dataset file not found: {_DATASET_FILE}")
        return {"status": "error", "reason": "missing dataset file"}

    with open(_DATASET_FILE) as f:
        dataset = json.load(f)

    pairs = dataset.get("pairs", [])
    logger.info(f"Loaded {len(pairs)} Q&A pairs")

    if sample_size and sample_size < len(pairs):
        pairs = random.sample(pairs, sample_size)
        logger.info(f"Sampled {sample_size} pairs")

    if dry_run:
        logger.info("DRY RUN — dataset loaded, skipping evaluation")
        return {"status": "dry_run", "pairs": len(pairs)}

    # 2. Query RAG API for each pair (persistent client per Golden Rule #10)
    api_url = LOCAL_API if use_local else PRODUCTION_API
    logger.info(f"Querying {api_url} for {len(pairs)} questions...")

    import httpx
    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=60.0) as shared_client:
        for i, pair in enumerate(pairs, 1):
            question = pair["question"]
            ground_truth = pair.get("ground_truth", "")

            logger.info(f"[{i}/{len(pairs)}] {question[:60]}...")
            rag_result = await query_rag(question, api_url, client=shared_client)

            # Evaluate
            faithfulness = evaluate_faithfulness(rag_result["answer"], rag_result["contexts"])
            relevancy = evaluate_relevancy(question, rag_result["answer"])

            results.append({
                "question": question,
                "ground_truth": ground_truth,
                "answer": rag_result["answer"][:500],
                "contexts_count": len(rag_result["contexts"]),
                "faithfulness": round(faithfulness, 3),
                "relevancy": round(relevancy, 3),
                "domain": pair.get("domain", "general"),
            })

            # Rate limit: 2 queries/sec
            await asyncio.sleep(0.5)

    # 3. Compute aggregate metrics
    avg_faithfulness = sum(r["faithfulness"] for r in results) / len(results) if results else 0
    avg_relevancy = sum(r["relevancy"] for r in results) / len(results) if results else 0
    error_count = sum(1 for r in results if "Error:" in r["answer"])

    # By domain
    domains: dict[str, list] = {}
    for r in results:
        domains.setdefault(r["domain"], []).append(r)

    domain_scores = {}
    for domain, domain_results in domains.items():
        domain_scores[domain] = {
            "count": len(domain_results),
            "avg_faithfulness": round(sum(r["faithfulness"] for r in domain_results) / len(domain_results), 3),
            "avg_relevancy": round(sum(r["relevancy"] for r in domain_results) / len(domain_results), 3),
        }

    logger.info(
        f"Results: faithfulness={avg_faithfulness:.3f}, relevancy={avg_relevancy:.3f}, "
        f"errors={error_count}/{len(results)}"
    )

    # 4. Compare with previous week
    degradation = _check_degradation(avg_faithfulness, avg_relevancy)

    # 5. Log to DB
    try:
        from decision_logger import log_decision_sync, log_risk_score_sync

        severity = "info"
        if avg_faithfulness < MIN_FAITHFULNESS or avg_relevancy < MIN_RELEVANCY:
            severity = "warning"
        if degradation:
            severity = "error"

        log_decision_sync(
            run_id, "ragas", "evaluation_complete",
            f"Faithfulness={avg_faithfulness:.3f}, Relevancy={avg_relevancy:.3f}, Errors={error_count}",
            severity,
            "alert" if severity == "error" else "none",
            rationale=f"Evaluated {len(results)} pairs against {api_url}",
            metadata={
                "domain_scores": domain_scores,
                "degradation": degradation,
                "sample_size": len(results),
            },
        )

        # Low-scoring pairs
        low_scorers = [r for r in results if r["faithfulness"] < 0.3 or r["relevancy"] < 0.3]
        for ls in low_scorers[:5]:
            log_decision_sync(
                run_id, "ragas", "low_score_pair",
                f"F={ls['faithfulness']:.2f} R={ls['relevancy']:.2f}: {ls['question'][:100]}",
                "warning", "none",
                metadata={"domain": ls["domain"], "answer_preview": ls["answer"][:200]},
            )

        # Update risk score
        log_risk_score_sync(
            overall=0, rbac=0, api_contract=0, cache=0, dead_code=0,
            ragas_quality=avg_faithfulness,
        )

    except Exception as e:
        logger.warning(f"Decision logging failed: {e}")

    # 6. Save report
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_file = _REPORTS_DIR / f"ragas_{start.strftime('%Y%m%d_%H%M')}.json"
    report_data = {
        "run_id": run_id,
        "timestamp": start.isoformat(),
        "api_url": api_url,
        "pairs_evaluated": len(results),
        "avg_faithfulness": round(avg_faithfulness, 3),
        "avg_relevancy": round(avg_relevancy, 3),
        "error_count": error_count,
        "domain_scores": domain_scores,
        "degradation": degradation,
        "results": results,
    }
    try:
        report_file.write_text(json.dumps(report_data, indent=2))
        logger.info(f"Report saved: {report_file}")
    except Exception as e:
        logger.warning(f"Report save failed: {e}")

    # 7. Telegram
    try:
        from watchdog import send_telegram_alert
        icon = "✅" if not degradation and avg_faithfulness >= MIN_FAITHFULNESS else "⚠️"
        if avg_faithfulness < 0.5:
            icon = "🔴"
        lines = [
            f"{icon} RAGAS Eval: F={avg_faithfulness:.2f} R={avg_relevancy:.2f}",
            f"Pairs: {len(results)}, Errors: {error_count}",
        ]
        if degradation:
            lines.append(f"DEGRADATION: {degradation}")
        for domain, ds in domain_scores.items():
            if ds["avg_faithfulness"] < MIN_FAITHFULNESS:
                lines.append(f"  Low: {domain} F={ds['avg_faithfulness']:.2f}")
        send_telegram_alert("\n".join(lines))
    except Exception as e:
        logger.warning(f"Telegram alert failed: {e}")

    duration = (datetime.now(timezone.utc) - start).total_seconds()
    logger.info(f"=== RAGAS Complete: F={avg_faithfulness:.3f} R={avg_relevancy:.3f}, {duration:.0f}s ===")

    return {
        "status": "ok",
        "avg_faithfulness": avg_faithfulness,
        "avg_relevancy": avg_relevancy,
        "pairs_evaluated": len(results),
        "error_count": error_count,
        "degradation": degradation,
    }


def _check_degradation(faithfulness: float, relevancy: float) -> str | None:
    """Compare with previous week's scores from DB or local reports."""
    # Check last report
    if _REPORTS_DIR.exists():
        reports = sorted(_REPORTS_DIR.glob("ragas_*.json"), reverse=True)
        if len(reports) >= 2:  # Need at least a previous report
            try:
                prev = json.loads(reports[1].read_text())
                prev_f = prev.get("avg_faithfulness", 0)
                prev_r = prev.get("avg_relevancy", 0)

                if prev_f > 0:
                    f_drop = (prev_f - faithfulness) / prev_f * 100
                    if f_drop > DEGRADATION_ALERT_PCT:
                        return f"Faithfulness dropped {f_drop:.1f}% (was {prev_f:.3f})"

                if prev_r > 0:
                    r_drop = (prev_r - relevancy) / prev_r * 100
                    if r_drop > DEGRADATION_ALERT_PCT:
                        return f"Relevancy dropped {r_drop:.1f}% (was {prev_r:.3f})"
            except Exception:
                pass

    return None


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    use_local = "--local" in sys.argv
    sample_size = None
    if "--sample" in sys.argv:
        idx = sys.argv.index("--sample")
        if idx + 1 < len(sys.argv):
            sample_size = int(sys.argv[idx + 1])

    result = asyncio.run(run_ragas_evaluation(
        sample_size=sample_size, dry_run=dry_run, use_local=use_local,
    ))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
