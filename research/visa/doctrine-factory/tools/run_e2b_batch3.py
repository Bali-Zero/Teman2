#!/usr/bin/env python3
"""E2b batch-3 (closure batch) driver.

Measured residual (against `coverage-matrix-after-batch2b.json`, cross-referenced with the
claim ledgers e2a/e2b-batch1/e2b-batch2 incl. the batch-2b additive EXTENSION section): of the
27 REACHABLE products, 26 already carry a VERIFIED or VERIFIED-WITH-CAVEAT claim closing every
required_claim_topic (many T1 "doctrine-card" topics close via composition/corroboration from
narrower already-VERIFIED claims, or via cross-reference to the E3a authoritative doctrine
cards for D1/D2/D12/E31B/E31D already merged on main -- see the batch-3 claim ledger's Method
section for the full per-product accounting). The SOLE genuine gap is **C2 (Visit Visa
Business, single-entry)** T1 -- both prior attempts (`E2B2-T1-C2`, a 5-point "doctrine-lite"
ask, and its narrowed retry `E2B2-T1-C2-RETRY`) TIMED OUT. Per the binding rule ("No 17-part
doctrine-card queries -- narrow per-topic only"), this driver splits C2's doctrine into TWO
even-narrower asks (2-3 points each) instead of retrying the same 5-point shape a third time.
"""
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

LOG_PATH = Path(__file__).parent.parent / "nb2-answers" / "e2b-batch3-response-log.jsonl"

QUERIES = [
    (
        "E2B3-C2-IDENTITY",
        "For C2 (Visit Visa Business, single-entry, Visa Kunjungan Bisnis) ONLY -- answer just "
        "these 2 points, concisely, one short paragraph each: (1) category/legal purpose and "
        "permitted vs prohibited activities; (2) single or multiple entry, duration per entry "
        "and total validity (compare briefly to D2 -- Business Multiple Entry -- only if it "
        "clarifies the single-entry distinction). Cite source title and passage for each point.",
    ),
    (
        "E2B3-C2-PROCEDURE",
        "For C2 (Visit Visa Business, single-entry, Visa Kunjungan Bisnis) ONLY -- answer just "
        "these 2 points, concisely, one short paragraph each: (1) extension mechanics (how many, "
        "how long) and any onshore conversion path; (2) mandatory sponsor/guarantor requirement. "
        "Cite source title and passage for each point.",
    ),
]


def main():
    results = []
    for i, (qid, text) in enumerate(QUERIES, 1):
        print(f"[{i}/{len(QUERIES)}] {qid} ...", flush=True)
        question = text + TEMPLATE
        attempt = 0
        max_attempts = 2
        while attempt < max_attempts:
            attempt += 1
            try:
                q_text = question if attempt == 1 else (text[:250] + " (narrowed retry)" + TEMPLATE)
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
            except Exception as exc:  # noqa: BLE001
                print(f"  -> EXCEPTION {type(exc).__name__}: {exc}", flush=True)
                results.append({"query_id": qid, "attempt": attempt, "status": f"EXCEPTION:{type(exc).__name__}"})
                break
        time.sleep(2)
    print("\nBatch-3 done:", results)


if __name__ == "__main__":
    main()
