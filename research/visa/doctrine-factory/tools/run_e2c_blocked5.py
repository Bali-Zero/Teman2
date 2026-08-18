#!/usr/bin/env python3
"""E2c mini-batch driver -- runs query-bank/e2c-blocked5-selection.json (11 queries) through
nb2_query.py. Mirrors run_e2b_batch2.py's contract (fresh conversation per query, mandatory
answer template, sequential execution, fail-loud on timeout, ONE narrowed retry) but reads from
its OWN selection file and logs to its OWN response-log so it never touches E2a's/batch-1's/
batch-2's/batch-3's files.

Scope: the 5 query-disposition BLOCKED products from OD-4's ratified disposition
(E23U, E23V, E33A, E33B, E33C) -- E23U/E23V reuse the already-authored but never-dispatched
VO-FUSED-T1-011/012 query IDs as their basis (narrowed here per batch-3's 2-point discipline,
since the 17-point doctrine-card shape times out); E33A/E33B/E33C get freshly authored narrow
queries (E33B gets a 3rd EXTRA query -- least-documented of the trio, priority per task).

Budget: <=12 live queries, 2-3 points per query (the 17-part and 5-point shapes timeout per
this task's binding instruction). 11 base queries planned, 1 query of headroom.
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
    "verification. If the sources do not allow a conclusion, state exactly which "
    "information or source is missing."
)

SELECTION_PATH = Path(__file__).parent.parent / "query-bank" / "e2c-blocked5-selection.json"
LOG_PATH = Path(__file__).parent.parent / "nb2-answers" / "e2c-blocked5-response-log.jsonl"

RETRY_BUDGET_TOTAL = 5


def narrowed_retry_text(item: dict) -> str:
    """On retry, shrink further: single point, per the task's binding retry-once-narrower rule."""
    return item["text"][:300] + " (narrowed retry, single point only, be brief)"


def main():
    queries = json.loads(SELECTION_PATH.read_text())
    results = []
    retries_used = 0

    for i, item in enumerate(queries, 1):
        qid = item["query_id"]
        category = item.get("category", "")
        question = item["text"] + TEMPLATE
        print(f"[{i}/{len(queries)}] {qid} ({category}) ...", flush=True)

        attempt = 0
        max_attempts = 2
        while attempt < max_attempts:
            attempt += 1
            if attempt == 2:
                if retries_used >= RETRY_BUDGET_TOTAL:
                    print(f"  -> retry budget exhausted ({retries_used}/{RETRY_BUDGET_TOTAL}), skipping retry", flush=True)
                    results.append({"query_id": qid, "attempt": attempt, "status": "TIMEOUT_FINAL_NO_RETRY_BUDGET"})
                    break
                retries_used += 1
            try:
                q_text = question if attempt == 1 else (narrowed_retry_text(item) + TEMPLATE)
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

    summary_path = Path(__file__).parent.parent / "query-bank" / "e2c-blocked5-run-summary.json"
    summary_path.write_text(json.dumps(results, indent=2))
    print(f"\nDone. Summary: {summary_path}. Retries used: {retries_used}/{RETRY_BUDGET_TOTAL}")


if __name__ == "__main__":
    main()
