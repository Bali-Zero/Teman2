#!/usr/bin/env python3
"""E2b batch-1 driver — runs the selected 40-query slice of fused-bank.jsonl through
nb2_query.py. Mirrors run_e2a_queries.py's contract (fresh conversation per query,
mandatory answer template, sequential execution, fail-loud on timeout) but reads from
query-bank/e2b-batch1-selection.json and logs to its own file so it never touches
E2a's response-log.jsonl.

v2 (post-restart, 2026-08-17): task budget is `<=40 live queries + <=5 retries` TOTAL for
the whole batch, not per-query. A global retry counter enforces this. Empirically (this run's
own first 2 queries, matching E2a's documented 3/3 finding) full "doctrine-card" (17-part)
queries have a near-0% completion rate within the 150s timeout — so doctrine-card category
queries are NOT retried (single attempt, log TIMEOUT and move on); the narrower categories
(threshold/sponsor/nationality/activity-boundary/etc.) get the retry budget instead, since
E2a found narrow queries reliably succeed. Resumable: RESUME_FROM_INDEX (1-based) and
ALREADY_SPENT_RETRIES let a restart account for live attempts already made in a prior process
that this script's own counter never saw.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import nb2_query  # noqa: E402

TEMPLATE = (
    "\n\nUse only the sources already in NB-2. Answer with concrete conclusions, do "
    "not default to requesting human review. Separate primary regulatory sources, "
    "official operational sources, and internal interpretations. For every claim "
    "give source title, date, passage and source ID. Distinguish what is legally "
    "permitted, what is operationally available, and what requires document "
    "verification. List the decisive facts, missing questions, alternatives and "
    "conflicts. If the sources do not allow a conclusion, state exactly which "
    "information or source is missing."
)

SELECTION_PATH = Path(__file__).parent.parent / "query-bank" / "e2b-batch1-selection.json"
LOG_PATH = Path(__file__).parent.parent / "nb2-answers" / "e2b-batch1-response-log.jsonl"

RETRY_BUDGET_TOTAL = 5
ALREADY_SPENT_RETRIES = 1  # VO-FUSED-T1-003-RETRY, confirmed logged in the prior (killed) process
RESUME_FROM_INDEX = 2  # 1-based; index 1 (T1-003) is done, index 2 (T1-038) had attempt-1 TIMEOUT
# already logged by the killed process — do not repeat attempt-1 for it, just mark final.
PRESEEDED_RESULTS = [
    {"query_id": "VO-FUSED-T1-003", "attempt": 2, "status": "TIMEOUT_FINAL", "note": "doctrine-card, both attempts timed out (prior process)"},
    {"query_id": "VO-FUSED-T1-038", "attempt": 1, "status": "TIMEOUT_FINAL", "note": "doctrine-card, no-retry policy (v2), attempt-1 timeout logged by prior process"},
]


def main():
    queries = json.loads(SELECTION_PATH.read_text())
    results = list(PRESEEDED_RESULTS)
    retries_used = ALREADY_SPENT_RETRIES

    for i, item in enumerate(queries, 1):
        if i < RESUME_FROM_INDEX:
            continue
        qid = item["query_id"]
        category = item.get("category", "")
        question = item["text"] + TEMPLATE
        print(f"[{i}/{len(queries)}] {qid} ({category}) ...", flush=True)

        allow_retry = category != "doctrine-card"
        attempt = 0
        max_attempts = 2 if allow_retry else 1
        while attempt < max_attempts:
            attempt += 1
            if attempt == 2:
                if retries_used >= RETRY_BUDGET_TOTAL:
                    print(f"  -> retry budget exhausted ({retries_used}/{RETRY_BUDGET_TOTAL}), skipping retry", flush=True)
                    results.append({"query_id": qid, "attempt": attempt, "status": "TIMEOUT_FINAL_NO_RETRY_BUDGET"})
                    break
                retries_used += 1
            try:
                q_text = question if attempt == 1 else (item["text"][:400] + " (narrowed retry)" + TEMPLATE)
                record = nb2_query.run_one_query(
                    query_id=qid if attempt == 1 else f"{qid}-RETRY",
                    question=q_text,
                    log_path=LOG_PATH,
                    timeout=150.0,
                )
                print(f"  -> status={record.get('status')} attempt={attempt}", flush=True)
                results.append({"query_id": qid, "attempt": attempt, "status": record.get("status")})
                break
            except nb2_query.QueryTimeoutError as exc:
                print(f"  -> TIMEOUT attempt={attempt}: {exc}", flush=True)
                if attempt >= max_attempts:
                    results.append({"query_id": qid, "attempt": attempt, "status": "TIMEOUT_FINAL"})
            except Exception as exc:  # noqa: BLE001 - report and continue, log already durable
                print(f"  -> EXCEPTION {type(exc).__name__}: {exc}", flush=True)
                results.append({"query_id": qid, "attempt": attempt, "status": f"EXCEPTION:{type(exc).__name__}"})
                break
        time.sleep(2)

    summary_path = Path(__file__).parent.parent / "query-bank" / "e2b-batch1-run-summary.json"
    summary_path.write_text(json.dumps(results, indent=2))
    print(f"\nDone. Summary: {summary_path}. Retries used: {retries_used}/{RETRY_BUDGET_TOTAL}")


if __name__ == "__main__":
    main()
