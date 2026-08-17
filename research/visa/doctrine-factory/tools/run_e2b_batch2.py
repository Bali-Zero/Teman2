#!/usr/bin/env python3
"""E2b batch-2 driver -- runs query-bank/e2b-batch2-selection.json (9 queries) through
nb2_query.py. Mirrors run_e2b_batch1.py's contract (fresh conversation per query, mandatory
answer template, sequential execution, fail-loud on timeout) but reads from its OWN selection
file and logs to its OWN response-log so it never touches E2a's or batch-1's files.

Scope: the 6 BLOCKED products batch-1 did NOT cover (E28B, E28C, E28D, E28F, E30E, E30F) --
per OD-4's original 11-BLOCKED-product list, batch-1's coverage-delta landed on a different
subset (E28A/E30A/E33/E33E/E33F/E33G among others), leaving these 6 without a dedicated
doctrine-lite pinpoint hunt.

Selection: 6 single-product doctrine-lite queries (5-point format proven in batch-1: category/
purpose, activities, entry/duration, extension/conversion, sponsor) + 3 pinpoint-hunt cross-
check queries (E28B/C threshold table, E28D/F index-code attestation, E30E/F index-code
attestation) -- the cross-checks exist because E28D/E28F/E30E/E30F do not appear anywhere in
e2a's or batch-1's claim ledgers, raising the live possibility that NB-2 simply does not
attest these index codes (an honest NO_PINPOINT_FOUND / OUT_OF_COMMERCIAL_SCOPE outcome, not a
retrieval failure).

Budget: <=20 live queries + <=5 retries TOTAL (global counter), per this task's binding
constraint. 9 base queries, comfortable retry headroom.
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

SELECTION_PATH = Path(__file__).parent.parent / "query-bank" / "e2b-batch2-selection.json"
LOG_PATH = Path(__file__).parent.parent / "nb2-answers" / "e2b-batch2-response-log.jsonl"

RETRY_BUDGET_TOTAL = 5
NO_RETRY_CATEGORIES: set[str] = set()  # nothing in this batch is full 17-part doctrine-card shape


def narrowed_retry_text(item: dict) -> str:
    """On retry, shrink further: single point instead of 5, or trim the pinpoint-hunt text."""
    if item.get("category") == "pinpoint-hunt":
        return item["text"][:400] + " (narrowed retry, single question only)"
    return item["text"][:400] + " (narrowed retry, fewer points requested)"


def main():
    queries = json.loads(SELECTION_PATH.read_text())
    results = []
    retries_used = 0

    for i, item in enumerate(queries, 1):
        qid = item["query_id"]
        category = item.get("category", "")
        question = item["text"] + TEMPLATE
        print(f"[{i}/{len(queries)}] {qid} ({category}) ...", flush=True)

        allow_retry = category not in NO_RETRY_CATEGORIES
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

    summary_path = Path(__file__).parent.parent / "query-bank" / "e2b-batch2-run-summary.json"
    summary_path.write_text(json.dumps(results, indent=2))
    print(f"\nDone. Summary: {summary_path}. Retries used: {retries_used}/{RETRY_BUDGET_TOTAL}")


if __name__ == "__main__":
    main()
