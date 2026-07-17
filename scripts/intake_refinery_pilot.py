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
import os
import re
from pathlib import Path
from typing import Any

import asyncpg
import httpx

OLLAMA = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen3.5:9b"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-v4-pro"


def _deepseek_key() -> str | None:
    env = Path.home() / ".openclaw/workspace/.env.master"
    if not env.exists():
        return None
    for line in env.read_text().splitlines():
        if line.startswith("DEEPSEEK_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    return None


def _norm_id(v: str | None) -> str | None:
    if not v:
        return None
    s = re.sub(r"[^A-Za-z0-9]", "", str(v)).upper()
    return s if len(s) >= 6 else None


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


def _build_prompt(bundle: dict) -> str:
    return (ADJUDICATE_PROMPT
            .replace("{doc_type}", str(bundle["doc_type"]))
            .replace("{fields}", json.dumps(bundle["fields"], ensure_ascii=False))
            .replace("{ocr}", bundle["ocr"])
            .replace("{candidates}", json.dumps(bundle["candidates"], ensure_ascii=False)))


def _safe_json(s: str) -> dict:
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        m = re.search(r"\{.*\}", s or "", re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {"client_id": None, "verdict": "PARSE_ERROR", "confidence": 0.0, "matched_on": "none"}


async def _ollama_adjudicate(client: httpx.AsyncClient, bundle: dict) -> dict:
    r = await client.post(OLLAMA, json={
        "model": MODEL, "prompt": _build_prompt(bundle), "stream": False,
        "think": False, "format": "json", "keep_alive": "5m",
        "options": {"temperature": 0.0, "num_predict": 200},
    }, timeout=120)
    r.raise_for_status()
    return _safe_json(r.json().get("response", "{}"))


async def _deepseek_adjudicate(client: httpx.AsyncClient, bundle: dict, key: str) -> dict:
    r = await client.post(DEEPSEEK_URL, headers={"Authorization": f"Bearer {key}"}, json={
        "model": DEEPSEEK_MODEL, "temperature": 0.0,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": _build_prompt(bundle)}],
    }, timeout=120)
    r.raise_for_status()
    return _safe_json(r.json()["choices"][0]["message"]["content"])


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
    fields = _extract_fields(so, routing)
    # STATION 4-pre: deterministic strong-id tiebreak (zero-risk) — doc's passport/kitas vs candidates'.
    doc_pp, doc_kt = _norm_id(fields.get("passport_no")), _norm_id(fields.get("kitas_no"))
    det_hits = []
    for c in cand_clients:
        if doc_pp and _norm_id(c.get("passport_number")) == doc_pp:
            det_hits.append((c["id"], "passport"))
        elif doc_kt and _norm_id(c.get("kitas_number")) == doc_kt:
            det_hits.append((c["id"], "kitas"))
    det_client = det_hits[0][0] if len(det_hits) == 1 else None
    det_on = det_hits[0][1] if len(det_hits) == 1 else None
    return {
        "proposal_id": proposal_id,
        "doc_type": er.get("doc_type") or routing.get("doc_type") or "unknown",
        "fields": fields,
        "ocr": _ocr_text(so),
        "candidates": cand_view,
        "n_candidates": len(candidates),
        "det_client": det_client, "det_on": det_on,
    }


def _to_int(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _gate(bundle: dict, oll: dict, ds: dict) -> tuple[str, int | None, str]:
    """Return (tier, client_id, reason). tier in AUTO_COMMIT / HUMAN_CONFIRM / NONE."""
    if bundle["det_client"] is not None:
        return "AUTO_COMMIT", bundle["det_client"], f"deterministic strong-id ({bundle['det_on']})"
    o_id, d_id = _to_int(oll.get("client_id")), _to_int(ds.get("client_id"))
    o_ok = oll.get("verdict") == "MATCH" and o_id is not None
    d_ok = ds.get("verdict") == "MATCH" and d_id is not None
    if o_ok and d_ok and o_id == d_id:
        strong = oll.get("matched_on") in ("passport", "kitas") or ds.get("matched_on") in ("passport", "kitas")
        return ("AUTO_COMMIT" if strong else "HUMAN_CONFIRM", o_id,
                "panel agree + strong-id" if strong else "panel agree, name-only")
    if o_ok and d_ok and o_id != d_id:
        return "HUMAN_CONFIRM", None, "panel split on client"
    if o_ok or d_ok:
        return "HUMAN_CONFIRM", (o_id if o_ok else d_id), "single-model match"
    return "NONE", None, "no model match"


async def run(mode: str, limit: int) -> None:
    conn = await _connect()
    ds_key = _deepseek_key()
    try:
        if mode == "groundtruth":
            rows = await conn.fetch(
                "SELECT p.id, a.client_id FROM document_routing_proposal p "
                "JOIN intake_commit_audit a ON a.proposal_id=p.id "
                "WHERE p.status IN ('routed','auto_routed') AND a.outcome='committed' "
                "AND a.client_id IS NOT NULL ORDER BY a.committed_at DESC LIMIT $1", limit)
            targets = [(r["id"], r["client_id"]) for r in rows]
        else:
            rows = await conn.fetch(
                "SELECT p.id FROM document_routing_proposal p "
                "WHERE p.status='review_pending' ORDER BY p.created_at DESC LIMIT $1", limit)
            targets = [(r["id"], None) for r in rows]

        tiers = {"AUTO_COMMIT": 0, "HUMAN_CONFIRM": 0, "NONE": 0}
        auto_correct = auto_total = gt_total = 0
        nonlocal_ds_err: list[str] = []
        async with httpx.AsyncClient() as http:
            for proposal_id, truth in targets:
                bundle = await _evidence_bundle(conn, proposal_id)
                if bundle is None:
                    continue
                oll = await _ollama_adjudicate(http, bundle)
                ds = {"verdict": "SKIP"}
                if ds_key:
                    try:
                        ds = await _deepseek_adjudicate(http, bundle, ds_key)
                    except (httpx.HTTPError, KeyError) as exc:
                        nonlocal_ds_err.append(str(exc)[:80])
                        ds = {"verdict": "ERR"}
                tier, cid, reason = _gate(bundle, oll, ds)
                tiers[tier] += 1
                if truth is not None:
                    gt_total += 1
                    if tier == "AUTO_COMMIT":
                        auto_total += 1
                        if cid == truth:
                            auto_correct += 1
                print(json.dumps({
                    "proposal": proposal_id, "truth": truth, "tier": tier, "picked": cid,
                    "reason": reason, "n_cand": bundle["n_candidates"], "det": bundle["det_on"],
                    "oll": oll.get("verdict"), "ds": ds.get("verdict"),
                    "auto_ok": (cid == truth) if (truth is not None and tier == "AUTO_COMMIT") else None,
                }, ensure_ascii=False))
        n = sum(tiers.values())
        print(f"\nTIERS: {tiers}  (n={n})")
        if n:
            print(f"COVERAGE auto-commit: {tiers['AUTO_COMMIT']}/{n} = {tiers['AUTO_COMMIT']/n:.0%}")
        if auto_total:
            print(f"AUTO-COMMIT PRECISION vs ground truth: {auto_correct}/{auto_total} = {auto_correct/auto_total:.0%}")
        if gt_total:
            print(f"(ground-truth rows evaluated: {gt_total})")
        if nonlocal_ds_err:
            print(f"DEEPSEEK DEGRADED: {len(nonlocal_ds_err)} errors, e.g. {nonlocal_ds_err[0]}")
    finally:
        await conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["groundtruth", "sample-review"], default="groundtruth")
    ap.add_argument("--limit", type=int, default=8)
    args = ap.parse_args()
    asyncio.run(run(args.mode, args.limit))
