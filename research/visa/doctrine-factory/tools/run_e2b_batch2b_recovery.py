#!/usr/bin/env python3
"""E2b batch-2 RECOVERY driver -- re-runs the 10 query_ids whose raw answers were lost when a
sibling process's git reset overwrote e2b-batch2-response-log.jsonl mid-run (see PR #4258's own
commit message: it found this worktree "already running an unowned, orphaned (PPID 1) process
executing a different, broader, apparently-abandoned 25-query attempt" and treated it as dead --
it was this session's live process). The queries themselves succeeded the first time (status=OK,
confirmed by this session's own monitor notification); only the durable record was lost. This
script re-issues the SAME 10 questions (verbatim, reconstructed from this session's own prior
tool-call record) and APPENDS (never overwrites) to the shared response-log, so it does not
disturb the sibling's 9 already-committed records or this session's own 20 already-recovered
records currently sitting after them in the same file.

Counts toward the task's <=40 live queries + <=5 retries budget: this session's original 25-query
selection + these 10 recovery re-issues = 35 total live query attempts, still within budget
(15 unused of 40 before this run).
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

LOG_PATH = Path(__file__).parent.parent / "nb2-answers" / "e2b-batch2b-response-log.jsonl"

LOST_QUERIES = [
    ("E2B2-T5-001", "Which products are legally single-entry vs multiple-entry, and in which does a single exit permanently void the stay permit?"),
    ("E2B2-T5-002", "For C-series (C1, C2, C6): exact extension mechanics -- how many extensions, of what length, filed where, total resulting stay. Cite source and passage per product."),
    ("E2B2-T5-003", "For D-series (D1, D2, D12): does exiting and re-entering reset the per-entry clock on multiple-entry visas? Any minimum time abroad required? Cite source and passage per product."),
    ("E2B2-T8-001", "Are there blackout windows (e.g. pending application) during which the applicant must not exit Indonesia, and for which products? Cite source and passage."),
    ("E2B2-T8-002", "What happens to a KITAS if the holder exits Indonesia without a re-entry permit (MERP), and how is it restored? Is any product exempt? Cite source and passage."),
    ("E2B2-T11-001", "RPTKA: who files, for what validity, which roles are exempt? Current instrument, cite article."),
    ("E2B2-T1-BRIDGING", "For the Indonesian onshore bridging permit (BRIDGING) ONLY, answer just these 5 points, concisely, one short paragraph each: (1) category and legal purpose (why it exists, what gap it bridges); (2) permitted vs prohibited activities while holding it; (3) single or multiple entry, and duration; (4) how many times it can be extended and for how long, and what it converts to; (5) is a sponsor/guarantor required. Cite source title and passage for each of the 5 points."),
    ("E2B2-T1-E31J", "For E31J (family/dependent index code) ONLY, answer just these 5 points, concisely: (1) category and legal purpose (which family relationship it covers); (2) permitted vs prohibited activities; (3) single or multiple entry, duration per entry and total validity; (4) extension mechanics and onshore conversion path if any; (5) mandatory sponsor/guarantor. Cite source title and passage for each point."),
    ("E2B2-T1-E31BC", "For E31B and E31C separately, answer just these 5 points per product, concisely: (1) category and legal purpose; (2) permitted vs prohibited activities; (3) single or multiple entry, duration per entry and total validity; (4) extension mechanics and onshore conversion path; (5) mandatory sponsor/guarantor. Cite source and passage for each point, per product."),
    ("E2B2-T1-E31DE", "For E31D and E31E separately, answer just these 5 points per product, concisely: (1) category and legal purpose; (2) permitted vs prohibited activities; (3) single or multiple entry, duration per entry and total validity; (4) extension mechanics and onshore conversion path; (5) mandatory sponsor/guarantor. Cite source and passage for each point, per product."),
]


def main():
    results = []
    for i, (qid, text) in enumerate(LOST_QUERIES, 1):
        print(f"[{i}/{len(LOST_QUERIES)}] {qid} (recovery) ...", flush=True)
        question = text + TEMPLATE
        attempt = 0
        max_attempts = 2
        while attempt < max_attempts:
            attempt += 1
            try:
                q_text = question if attempt == 1 else (text[:400] + " (narrowed retry)" + TEMPLATE)
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
    print("\nRecovery done:", results)


if __name__ == "__main__":
    main()
