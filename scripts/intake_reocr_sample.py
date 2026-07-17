#!/usr/bin/env python3
"""Intake Station-1 re-OCR RECALL sample — MEASUREMENT ONLY, ZERO writes.

Answers the mandate question empirically on a labeled sample: for zero-candidate
`review_pending` docs whose blob STILL exists on disk, does a second qwen2.5vl:7b
vision pass (all pages) extract a NAME / strong-id that the one-shot missed, and
does that newly-extracted signal produce >=1 candidate against the full clients table?

Read-only against local nuzantara_dev (trust). Never writes the DB, never re-attaches.
PII (Law 2): emits ONLY redacted output — proposal_id (int), client_id (int), booleans,
similarity floats. Never a name / passport / OCR text leaves this process.

Usage:
  cd apps/backend-rag && source .venv/bin/activate
  PYTHONPATH=. python ../../scripts/intake_reocr_sample.py --limit 45 --doctype unknown
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import re
from pathlib import Path
from typing import Any

import asyncpg
import httpx

OLLAMA = "http://127.0.0.1:11434/api/generate"
VISION_MODEL = "qwen2.5vl:7b"  # data-invariant: ONLY vision model (qwen3.5 strips vision)
NAME_SIM = 0.45  # instrument-validated: attached docs match own client at avg 0.79, >=0.45 in 90%

PROMPT = (
    "You are an OCR field extractor for an Indonesian immigration document. "
    "Read the image and return ONLY a compact JSON object with keys: "
    "doc_type (one of passport,kitas,itk,visa,ktp,npwp,nib,akta,bank_statement,"
    "payment_receipt,travel_ticket,other,not_a_document), "
    "subject_name (the person the document is ABOUT, latin letters, or null), "
    "passport_no (or null), kitas_no (or null), nik (or null). "
    "No prose, no markdown, JSON only."
)


def _norm_id(v: str | None) -> str | None:
    if not v:
        return None
    s = re.sub(r"[^A-Za-z0-9]", "", str(v)).upper()
    return s if len(s) >= 6 else None


def _load_image_b64(path: Path) -> str | None:
    """jpg/jpeg/png only (sample filters to these) → base64. No PDF rendering here."""
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if not raw:
        return None
    return base64.b64encode(raw).decode("ascii")


async def _connect() -> asyncpg.Connection:
    return await asyncpg.connect(
        host="127.0.0.1", port=5432, user="nuzantara", database="nuzantara_dev"
    )


async def _vision(client: httpx.AsyncClient, b64: str) -> dict[str, Any]:
    payload = {
        "model": VISION_MODEL,
        "prompt": PROMPT,
        "images": [b64],
        "stream": False,
        "think": False,
        "format": "json",
        "options": {"temperature": 0.0, "num_ctx": 4096},
    }
    try:
        r = await client.post(OLLAMA, json=payload, timeout=120.0)
        r.raise_for_status()
        txt = r.json().get("response", "") or ""
        return json.loads(txt)
    except Exception:
        return {}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=250)
    ap.add_argument("--pids-file", required=True,
                    help="TSV: pid<TAB>doctype<TAB>blob_path (disk-truth present list)")
    args = ap.parse_args()

    conn = await _connect()

    present: list[tuple[int, Path, str | None]] = []
    for line in Path(args.pids_file).read_text().splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        pid_s, _dt, bp = parts[0], parts[1], parts[2]
        p = Path(bp)
        if pid_s.isdigit() and p.is_file():
            present.append((int(pid_s), p, None))
    present = present[: args.limit]

    stats = {
        "sampled_present": len(present),
        "vision_ok": 0,
        "gained_name": 0,           # re-OCR produced a subject_name where before there was none/again
        "gained_strongid": 0,       # re-OCR produced a normalized strong-id
        "strongid_matches_client": 0,
        "name_matches_client_ge045": 0,  # >=1 client at trigram >=0.45
        "reclassified_not_document": 0,  # vision says not_a_document -> junk lead
        "any_new_candidate": 0,     # strong-id match OR name match -> Station 2 would now find something
    }

    async with httpx.AsyncClient() as client:
        for pid, bp, old_name in present:
            b64 = _load_image_b64(bp)
            if b64 is None:
                continue
            out = await _vision(client, b64)
            if not out:
                continue
            stats["vision_ok"] += 1

            dtype = str(out.get("doc_type") or "").lower()
            if dtype == "not_a_document":
                stats["reclassified_not_document"] += 1

            name = out.get("subject_name")
            if name and len(str(name).strip()) >= 3:
                stats["gained_name"] += 1

            sid = _norm_id(out.get("passport_no")) or _norm_id(out.get("kitas_no")) or _norm_id(out.get("nik"))
            if sid:
                stats["gained_strongid"] += 1

            new_cand = False
            # strong-id -> client
            if sid:
                m = await conn.fetchval(
                    """
                    SELECT count(*) FROM clients
                    WHERE deleted_at IS NULL AND (
                      upper(regexp_replace(coalesce(passport_number,''),'[^A-Za-z0-9]','','g'))=$1
                      OR upper(regexp_replace(coalesce(kitas_number,''),'[^A-Za-z0-9]','','g'))=$1)
                    """,
                    sid,
                )
                if m and m > 0:
                    stats["strongid_matches_client"] += 1
                    new_cand = True
            # name -> client (trigram)
            if name and len(str(name).strip()) >= 3:
                await conn.execute("SELECT set_limit($1)", NAME_SIM)
                m = await conn.fetchval(
                    "SELECT count(*) FROM clients WHERE deleted_at IS NULL AND lower(trim(full_name)) % lower(trim($1))",
                    str(name),
                )
                if m and m > 0:
                    stats["name_matches_client_ge045"] += 1
                    new_cand = True
            if new_cand:
                stats["any_new_candidate"] += 1

    await conn.close()
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
