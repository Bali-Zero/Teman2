#!/usr/bin/env python3
"""Intake Review Refinery — PILOT (measurement only, ZERO writes).

Reads review-proposal evidence from local nuzantara_dev (read-only role), runs a
single-LLM adjudication pass (local Ollama qwen3.5:9b), and compares the verdict to
ground truth. Emits ONLY redacted output (client_id ints, match booleans, scores) —
never client names / passport numbers / OCR text (SYMBIOSIS Law-2 output boundary held
even though processing is Law-2-waived for this mission).

Usage:
  PYTHONPATH=. .venv/bin/python scripts/intake_refinery_pilot.py --mode groundtruth --limit 8
  PYTHONPATH=. .venv/bin/python scripts/intake_refinery_pilot.py --mode sample-review --limit 5
"""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
from typing import Any

import asyncpg
import httpx

OLLAMA = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen3.5:9b"

# Ground-truth: auto_routed proposals whose committed client_id we trust as the label.
GROUNDTRUTH: list[tuple[int, int]] = [
    (111537, 10226), (108983, 6927), (100334, 7315), (99685, 10214),
    (99678, 6299), (87241, 10487), (86817, 10587), (86534, 10522),
    (80767, 10339), (80338, 10382), (73465, 10273), (73307, 10280),
]


async def _connect() -> asyncpg.Connection:
    # Local nuzantara_dev via trust auth (user=nuzantara). Script is SELECT-only by construction.
    return await asyncpg.connect(
        host="127.0.0.1", port=5432, user="nuzantara", database="nuzantara_dev",
    )


def _ocr_text(stage_output: dict[str, Any], max_chars: int = 4000) -> str:
    """Assemble OCR text from stage_output (classify holds it per the reader map)."""
    classify = stage_output.get("classify") or {}
    pages = classify.get("ocr_text_per_page")
    if isinstance(pages, list):
        text = "\n".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in pages)
    else:
        ocr = stage_output.get("ocr") or {}
        pgs = ocr.get("pages") or []
        text = "\n".join(p.get("text", "") for p in pgs if isinstance(p, dict))
    return text[:max_chars]


def _extract_fields(stage_output: dict[str, Any], routing: dict[str, Any]) -> dict[str, Any]:
    fields = (routing or {}).get("fields") or (stage_output.get("extract") or {}).get("fields") or {}
    out = {}
    for k, v in fields.items():
        if isinstance(v, dict):
            out[k] = v.get("value")
        else:
            out[k] = v
    return {k: v for k, v in out.items() if v}


async def _candidate_clients(conn: asyncpg.Connection, candidates: list[dict]) -> list[dict]:
    """Fetch match-fields for each candidate client (name/phone/passport/kitas/nationality)."""
    ids = [c["id"] for c in candidates if c.get("table") == "clients" and c.get("id")]
    if not ids:
        return []
    rows = await conn.fetch(
        "SELECT id, full_name, phone_normalized, passport_number, kitas_number, nationality "
        "FROM clients WHERE id = ANY($1::int[]) AND deleted_at IS NULL", ids,
    )
    return [dict(r) for r in rows]


ADJUDICATE_PROMPT = """You are a strict document-to-client matcher for an Indonesian immigration agency.
Given a document's OCR text + extracted fields, and a list of candidate clients, decide which candidate
client is the SUBJECT of this document (the person the document is ABOUT — not who forwarded it).

Rules:
- Match on strong identifiers first: passport number, KITAS number. If the document's passport/KITAS
  number equals a candidate's, that candidate is the subject with high confidence.
- Then match on full name (the name printed ON the document vs the candidate's full_name).
- A phone match alone is WEAK: the sender may be a staff member forwarding a client's document.
- If NO candidate is the subject, answer NONE. If two candidates are equally plausible, answer AMBIGUOUS.
- Never guess from frequency or folder names.

Return ONLY compact JSON: {"client_id": <int|null>, "verdict": "MATCH"|"NONE"|"AMBIGUOUS",
"confidence": <0..1>, "matched_on": "passport"|"kitas"|"name"|"phone"|"none"}

DOCUMENT:
doc_type: {doc_type}
extracted_fields: {fields}
ocr_text (truncated):
{ocr}

CANDIDATE CLIENTS:
{candidates}
"""


async def _adjudicate(client: httpx.AsyncClient, bundle: dict) -> dict:
    prompt = (ADJUDICATE_PROMPT
              .replace("{doc_type}", str(bundle["doc_type"]))
              .replace("{fields}", json.dumps(bundle["fields"], ensure_ascii=False))
              .replace("{ocr}", bundle["ocr"])
              .replace("{candidates}", json.dumps(bundle["candidates"], ensure_ascii=False)))
    r = await client.post(OLLAMA, json={
        "model": MODEL, "prompt": prompt, "stream": False,
        "think": False, "format": "json", "keep_alive": "5m",
        "options": {"temperature": 0.0, "num_predict": 200},
    }, timeout=120)
    r.raise_for_status()
    resp = r.json().get("response", "{}")
    try:
        return json.loads(resp)
    except json.JSONDecodeError:
        return {"client_id": None, "verdict": "PARSE_ERROR", "confidence": 0.0, "matched_on": "none"}


async def _evidence_bundle(conn: asyncpg.Connection, proposal_id: int) -> dict | None:
    row = await conn.fetchrow(
        "SELECT p.entity_resolution, p.routing, p.commit_gate, q.stage_output "
        "FROM document_routing_proposal p JOIN intake_queue q ON q.id=p.queue_id WHERE p.id=$1",
        proposal_id,
    )
    if not row:
        return None
    er = json.loads(row["entity_resolution"]) if isinstance(row["entity_resolution"], str) else (row["entity_resolution"] or {})
    routing = json.loads(row["routing"]) if isinstance(row["routing"], str) else (row["routing"] or {})
    so = json.loads(row["stage_output"]) if isinstance(row["stage_output"], str) else (row["stage_output"] or {})
    candidates = er.get("candidates") or []
    cand_clients = await _candidate_clients(conn, candidates)
    # Redact candidate presentation for the LLM: keep name+identifiers (processing allowed, Law2 waived).
    cand_view = [{
        "client_id": c["id"], "full_name": c.get("full_name"),
        "passport_number": c.get("passport_number"), "kitas_number": c.get("kitas_number"),
        "phone": c.get("phone_normalized"), "nationality": c.get("nationality"),
    } for c in cand_clients]
    return {
        "proposal_id": proposal_id,
        "doc_type": er.get("doc_type") or routing.get("doc_type") or "unknown",
        "fields": _extract_fields(so, routing),
        "ocr": _ocr_text(so),
        "candidates": cand_view,
        "n_candidates": len(candidates),
    }


async def run(mode: str, limit: int) -> None:
    conn = await _connect()
    try:
        if mode == "groundtruth":
            targets = GROUNDTRUTH[:limit]
        else:
            rows = await conn.fetch(
                "SELECT p.id FROM document_routing_proposal p "
                "WHERE p.status='review_pending' AND p.entity_resolution->>'decision'='AMBIGUOUS' "
                "ORDER BY p.created_at DESC LIMIT $1", limit,
            )
            targets = [(r["id"], None) for r in rows]

        agree = 0
        total = 0
        async with httpx.AsyncClient() as http:
            for proposal_id, truth in targets:
                bundle = await _evidence_bundle(conn, proposal_id)
                if bundle is None:
                    print(f"proposal={proposal_id} MISSING")
                    continue
                verdict = await _adjudicate(http, bundle)
                total += 1
                picked = verdict.get("client_id")
                match_truth = (truth is not None and picked == truth)
                if match_truth:
                    agree += 1
                # REDACTED output only: ids, verdict, confidence, matched_on, ocr length.
                print(json.dumps({
                    "proposal": proposal_id, "truth_client": truth,
                    "picked_client": picked, "verdict": verdict.get("verdict"),
                    "matched_on": verdict.get("matched_on"), "conf": verdict.get("confidence"),
                    "n_cand": bundle["n_candidates"], "ocr_chars": len(bundle["ocr"]),
                    "agrees_with_truth": match_truth if truth is not None else None,
                }, ensure_ascii=False))
        if mode == "groundtruth" and total:
            print(f"\nGROUNDTRUTH AGREEMENT: {agree}/{total} = {agree/total:.0%}")
    finally:
        await conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["groundtruth", "sample-review"], default="groundtruth")
    ap.add_argument("--limit", type=int, default=8)
    args = ap.parse_args()
    asyncio.run(run(args.mode, args.limit))
