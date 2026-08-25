#!/usr/bin/env python3
"""probe_legal_status_marking — makes Decision 5 (MARK over REMOVE) testable.

Zero's reasoning for MARK over REMOVE (docs/plans/2026-08-25-kb-current-live/
MANDATE.md §7 decision 5, and the orchestrator's brief for this task): a filter
that excludes anything `legal_status: dicabut` would have dropped Permen_22_2023
(the CURRENT, in-force visa regulation — journey 3/4's live defect) while keeping
Permen_29_2021 (the genuinely superseded predecessor) — REMOVE makes the corpus
worse, not better. MARK survives only if a mark is actually retrievable and
correct at query time. This script measures exactly that, read-only, against the
SAME production retrieval path `kb/ops/probe_retrieval.py` uses (imports its
`repo_root`/`load_env`/`retrieve` rather than reimplementing them — a probe that
reimplements retrieval logic can go green while production goes red, per that
file's own docstring).

It does NOT replace probe_retrieval.py's phrase-based journeys, and it
deliberately does not touch that 622-line shared tool (used by property/tax lanes
too) or its guilt/innocence test contract — this is a narrow, additive companion
scoped to the ONE pair MANDATE.md names directly (journeys 3 & 4 of
kb/journeys/immigration.yaml): the current instrument (Permen_22_2023) vs. the
superseded one it replaced (Permen_29_2021), asked with journey 4's real
ITAS-duration question.

WHAT IT ASSERTS
For the SAME question journey 4 already probes, among the retrieved chunks:
  - is Permen_29_2021 (superseded) present, and is it MARKED as such
    (legal_status == 'dicabut')?
  - is Permen_22_2023 (current) present, and is it MARKED as CURRENT
    (legal_status == 'berlaku', i.e. NOT 'dicabut')?
Today (2026-08-25, before any repair), the audit (audit_legal_status.py) measured
BOTH documents carrying legal_status='dicabut' — so this script is expected to
report the superseded side AT TARGET and the current side OUTSTANDING, which is
the live defect this campaign exists to fix. After the narrow repair proposed in
propose_legal_status_repair.py is (if ever) applied, re-running this script is
how a lane proves the mark, not just the presence, is now correct — a green here
is decision 5 becoming true in production, not just declared.

Run: apps/backend-rag/.venv/bin/python scripts/kb/probe_legal_status_marking.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kb" / "ops"))
from probe_retrieval import load_env, repo_root, retrieve  # noqa: E402

QUESTION = (
    "Berapa lama masa berlaku Izin Tinggal Terbatas (ITAS) bagi WNA yang masuk "
    "dengan visa tinggal terbatas?"
)
COLLECTION = "legal_unified"
CURRENT_DOC = "Permen_22_2023"
SUPERSEDED_DOC = "Permen_29_2021"
EXPECT_CURRENT_STATUS = "berlaku"
EXPECT_SUPERSEDED_STATUS = "dicabut"


def doc_id_of(chunk: dict) -> str:
    meta = chunk.get("metadata")
    meta = meta if isinstance(meta, dict) else {}
    return chunk.get("document_id") or meta.get("document_id") or "<none>"


def legal_status_of(chunk: dict) -> str:
    meta = chunk.get("metadata")
    meta = meta if isinstance(meta, dict) else {}
    val = chunk.get("legal_status")
    if val is None:
        val = meta.get("legal_status")
    return str(val) if val is not None else "<missing>"


async def main() -> int:
    root = repo_root()
    load_env(root)
    sys.path.insert(0, str(root / "apps" / "backend-rag"))
    from backend.services.search.search_service import SearchService

    service = SearchService()
    chunks = await retrieve(service, QUESTION, COLLECTION, limit=10)

    print("=== probe_legal_status_marking — Decision 5, journey 3/4 pair ===")
    print("question: %r" % QUESTION)
    print("collection: %s\n" % COLLECTION)

    findings = []
    for label, doc_id, expect in (
        ("CURRENT (should read as in-force)", CURRENT_DOC, EXPECT_CURRENT_STATUS),
        ("SUPERSEDED (should read as revoked)", SUPERSEDED_DOC, EXPECT_SUPERSEDED_STATUS),
    ):
        rank = None
        status = None
        for i, chunk in enumerate(chunks, start=1):
            if doc_id_of(chunk) == doc_id:
                rank = i
                status = legal_status_of(chunk)
                break
        print(f"--- {doc_id} — {label} ---")
        if rank is None:
            print(f"  NOT in top {len(chunks)} results for this question.")
            findings.append((doc_id, "absent_from_results"))
            print()
            continue
        marked_correctly = status == expect
        print(f"  rank: {rank}")
        print(f"  legal_status on the retrieved chunk: {status!r}")
        print(f"  expected for a correct mark: {expect!r}")
        print(f"  verdict: {'AT TARGET' if marked_correctly else 'OUTSTANDING — wrong mark'}")
        findings.append((doc_id, "at_target" if marked_correctly else "outstanding"))
        print()

    outstanding = [d for d, v in findings if v != "at_target"]
    if outstanding:
        print(f"OUTSTANDING — {len(outstanding)} of {len(findings)} instrument(s) not "
              f"correctly marked: {', '.join(outstanding)}")
        print("Decision 5 (MARK) is not yet true in production for this pair.")
        return 2
    print("AT TARGET — both instruments carry the correct mark in production.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
