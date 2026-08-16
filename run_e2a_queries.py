#!/usr/bin/env python3
"""Ephemeral E2a driver — runs the slice query bank through nb2_query.py.

Not part of the doctrine-factory tooling (that lives in tools/); this is a one-shot
runner for the E2a task, deleted after use. Appends the mandatory template
(blueprint C §3.0 / master prompt §5C) to every question, sequential execution,
fresh conversation per query (nb2_query.py's own contract).
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "research/visa/doctrine-factory/tools"))
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

QUERIES_PATH = Path(__file__).parent / "research/visa/doctrine-factory/e2a_queries.json"
LOG_PATH = Path(__file__).parent / "research/visa/doctrine-factory/nb2-answers/response-log.jsonl"


def main():
    queries = json.loads(QUERIES_PATH.read_text())
    for i, item in enumerate(queries, 1):
        qid = item["id"]
        question = item["q"] + TEMPLATE
        print(f"[{i}/{len(queries)}] {qid} ...", flush=True)
        try:
            record = nb2_query.run_one_query(
                query_id=qid,
                question=question,
                log_path=LOG_PATH,
                timeout=150.0,
            )
            print(f"  -> status={record.get('status')}", flush=True)
        except Exception as exc:  # noqa: BLE001 - report and continue, log already durable
            print(f"  -> EXCEPTION {type(exc).__name__}: {exc}", flush=True)
        time.sleep(2)


if __name__ == "__main__":
    main()
