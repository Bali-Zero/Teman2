"""Backfill missing AI extraction on `company_profile` PDFs (Profil Perseroan)
and infer new `client_company_links` from extracted directors/commissioners.

Pipeline per PDF:
  1. Download from Drive via SA+DWD (zero@balizero.com)
  2. pdftotext -raw to extract text (strips watermark via prompt instruction)
  3. DeepSeek V4 Pro structured extraction (reasoning_effort=high) — $0.01/q
     Schema: company_name + persons[{name, role, shares, nationality}]
  4. UPDATE company_documents.ocr_extracted_data = jsonb (rich profile)
  5. For each person:
     - Try match clients.full_name (exact UPPERCASE, then tokenized)
     - If match: INSERT client_company_links (idempotent ON CONFLICT)
     - If no client: log to deferred_persons_for_review.json
  6. ON FAILURE: log to log file, NO retry inline (cron sweeps later)

Cost: ~$0.01/PDF × 431 PDFs = ~$4.31 total one-time backfill.
After backfill: cron weekly catches new uploads (~5-10/week = $0.10/week).

Run:
  cd ~/nuzantara
  ./apps/backend-rag/.venv/bin/python scripts/workspace_automation/profil_perseroan_ai_backfill.py --limit 5    # test 5 PDFs
  ./apps/backend-rag/.venv/bin/python scripts/workspace_automation/profil_perseroan_ai_backfill.py --apply --limit 5
  ./apps/backend-rag/.venv/bin/python scripts/workspace_automation/profil_perseroan_ai_backfill.py --apply       # full backfill (~431 PDFs)
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import re
import subprocess
import tempfile
import time
import urllib.request
from typing import Optional

import psycopg2
import psycopg2.extras
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

SA_KEY = "/Users/nuzantara/Desktop/codexyz/nuzantara-google-drive-sa-key-20260312.json"
IMPERSONATE = "zero@balizero.com"
DB = dict(host="localhost", port=15432, dbname="nuzantara_rag",
          user="backend_rag_v2", password="<<ROTATED_2026_05_22_see_DATABASE_URL_env>>")  # pragma: allowlist secret
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-v4-pro"
LINK_SOURCE_TAG = "ai_profil_perseroan_backfill_2026_05_20"

logger = logging.getLogger("profil_backfill")


# ---------- Drive ----------

def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        SA_KEY, scopes=["https://www.googleapis.com/auth/drive"],
    ).with_subject(IMPERSONATE)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def download_pdf(svc, file_id: str) -> bytes:
    req = svc.files().get_media(fileId=file_id, supportsAllDrives=True)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, req)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    buf.seek(0)
    return buf.read()


def pdf_to_text(pdf_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf_bytes)
        pdf_path = f.name
    try:
        out = subprocess.check_output(["pdftotext", "-raw", pdf_path, "-"], stderr=subprocess.DEVNULL)
        return out.decode("utf-8", errors="replace")
    finally:
        os.unlink(pdf_path)


# ---------- DeepSeek ----------

EXTRACT_PROMPT_TPL = """Estrai dati strutturati da questo testo PDF "PROFIL PERSEROAN" indonesiano (atto societario).

IGNORA il watermark verticale ripetuto "R E S M I D A R I D I T J E N A H U" (anti-tamper).

Estrai (return JSON, NIENTE markdown, solo JSON puro):
{{
  "company_name": "PT FULL NAME UPPER",
  "deed_number": "...",
  "deed_date": "YYYY-MM-DD",
  "notary_name": "...",
  "sk_number": "...",
  "sk_date": "YYYY-MM-DD",
  "authorized_capital": 1000000000,
  "paid_capital": 1000000000,
  "company_status": "TERTUTUP|TERBUKA",
  "city": "...",
  "registered_address": "...",
  "company_phone": "...",
  "company_email": "...",
  "kbli_codes": [{{"code":"68111","description":"..."}}],
  "persons": [
    {{
      "name": "FULL NAME IN UPPERCASE (no TTL, no birthplace)",
      "role": "DIREKTUR|KOMISARIS|DIREKTUR UTAMA|KOMISARIS UTAMA",
      "shares": 1000,
      "share_value": 1000000000,
      "ownership_pct": 50.0,
      "nationality": "ITALY|INDONESIA|AUSTRALIA|...",
      "passport": "ABC123|null"
    }}
  ]
}}

Note importanti:
- Sezione "PENGURUS DAN PEMEGANG SAHAM" contiene la tabella persone
- Per stranieri spesso c'è "WNI/WNA <country>" o passport. Per indonesiani "TTL: <luogo>, <data>" che NON va nel nome
- ownership_pct calcola: shares / total_shares * 100. Se non chiaro lascia null
- Capital in IDR senza punti/virgole

TEXT:
{text}
"""


def deepseek_extract(text: str, max_text_chars: int = 12000) -> Optional[dict]:
    """Call DeepSeek V4 Pro. Retry with effort=low if effort=high fails."""
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY env var not set")

    for effort in ("high", "low"):
        body = json.dumps({
            "model": DEEPSEEK_MODEL,
            "messages": [{"role": "user", "content": EXTRACT_PROMPT_TPL.format(text=text[:max_text_chars])}],
            "response_format": {"type": "json_object"},
            "max_tokens": 4000,
            "reasoning_effort": effort,
        }).encode()
        req = urllib.request.Request(DEEPSEEK_URL, data=body, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        })
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                payload = json.loads(resp.read())
            content = payload["choices"][0]["message"]["content"]
            return json.loads(content)
        except (urllib.error.HTTPError, urllib.error.URLError, KeyError, json.JSONDecodeError, TimeoutError) as e:
            logger.warning("DeepSeek %s failed: %s — retry with lower effort", effort, e)
            time.sleep(2)
    logger.error("DeepSeek both effort attempts failed")
    return None


# ---------- Person → Client matching ----------

def normalize(s: Optional[str]) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s.upper().strip())


def load_client_index(cur) -> dict[str, list[dict]]:
    """Return {normalized_full_name: [{id, full_name, nationality, passport_number}]}."""
    cur.execute("""
        SELECT id, full_name, nationality, passport_number
        FROM clients
        WHERE deleted_at IS NULL
    """)
    idx: dict[str, list[dict]] = {}
    for r in cur.fetchall():
        key = normalize(r["full_name"])
        if not key:
            continue
        idx.setdefault(key, []).append(dict(r))
    return idx


def match_person_to_client(person: dict, client_index: dict[str, list[dict]]) -> Optional[dict]:
    """Try exact name match. Returns the matched client dict or None."""
    name = normalize(person.get("name"))
    if not name:
        return None
    matches = client_index.get(name)
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    # Multiple — try disambig by nationality
    pers_nat = (person.get("nationality") or "").upper()
    for m in matches:
        if m.get("nationality") and m["nationality"].upper() == pers_nat:
            return m
    # Disambig by passport
    pers_pass = (person.get("passport") or "").upper()
    if pers_pass:
        for m in matches:
            if m.get("passport_number") and m["passport_number"].upper() == pers_pass:
                return m
    # Ambiguous — return first
    return matches[0]


def role_to_link_role(role: str) -> str:
    r = (role or "").upper()
    if "KOMISARIS" in r:
        return "commissioner"
    if "DIREKTUR" in r:
        return "director"
    return "shareholder"


# ---------- DB ops ----------

def update_doc_extraction(conn, doc_id: int, data: dict) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE company_documents
            SET ocr_extracted_data = %s::jsonb,
                ocr_status = 'completed',
                ocr_completed_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
        """, (json.dumps(data), doc_id))


def upsert_link(conn, client_id: int, company_id: int, role: str, shares: Optional[int], pct: Optional[float], notes: str) -> bool:
    """Returns True if a new link was inserted (False if already existed)."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO client_company_links
                (client_id, company_id, role, shares_count, ownership_percentage, notes, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'active')
            ON CONFLICT (client_id, company_id) DO UPDATE
            SET notes = CASE
                          WHEN client_company_links.notes IS NULL OR client_company_links.notes = ''
                          THEN EXCLUDED.notes
                          ELSE client_company_links.notes
                        END,
                role = COALESCE(NULLIF(client_company_links.role,''), EXCLUDED.role),
                shares_count = COALESCE(client_company_links.shares_count, EXCLUDED.shares_count),
                ownership_percentage = COALESCE(client_company_links.ownership_percentage, EXCLUDED.ownership_percentage),
                updated_at = NOW()
            RETURNING (xmax = 0) AS inserted
        """, (client_id, company_id, role, shares, pct, notes))
        return cur.fetchone()[0]


# ---------- Main ----------

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="Actually update DB + insert links (default: dry-run)")
    p.add_argument("--limit", type=int, default=0, help="Max PDFs to process (0 = all)")
    p.add_argument("--company-only", type=int, help="Filter to one company_id for debug")
    p.add_argument("--sleep", type=float, default=1.0, help="Seconds to sleep between PDFs (rate limit)")
    p.add_argument("--shard", type=int, default=0, help="Process only docs where doc_id %% shard_total == shard (for parallel runs)")
    p.add_argument("--shard-total", type=int, default=1, help="Total shards (for parallel runs)")
    args = p.parse_args()
    apply = args.apply

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    # DB connect (autocommit OFF for transactional updates)
    conn = psycopg2.connect(**DB)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Build client index
    logger.info("Loading client index...")
    client_idx = load_client_index(cur)
    logger.info("Loaded %d distinct client names", len(client_idx))

    # Get pending PDFs — only real Profil Perseroan PDFs (not jpg, not unrelated docs)
    q = """
        SELECT cd.id AS doc_id, cd.company_id, c.company_name,
               cd.google_drive_file_id, cd.file_name
        FROM company_documents cd
        JOIN companies c ON c.id = cd.company_id
        WHERE cd.document_type = 'company_profile'
          AND (cd.ocr_extracted_data IS NULL OR cd.ocr_extracted_data = '{}'::jsonb)
          AND cd.google_drive_file_id IS NOT NULL AND cd.google_drive_file_id != ''
          AND cd.file_name ILIKE %s
          AND (
            cd.file_name ILIKE %s
            OR cd.file_name ILIKE %s
            OR cd.file_name ILIKE %s
            OR cd.file_name ILIKE %s
          )
    """
    params = ["%.pdf", "%profil%", "%profile%", "%perseroan%", "%rincian%"]
    if args.company_only:
        q += " AND cd.company_id = %s"
        params.append(args.company_only)
    if args.shard_total > 1:
        q += " AND (cd.id %% %s) = %s"
        params.extend([args.shard_total, args.shard])
    q += " ORDER BY cd.id"  # deterministic order across shards
    if args.limit:
        q += f" LIMIT {args.limit}"
    cur.execute(q, params)
    pending = cur.fetchall()
    logger.info("Found %d pending PDFs", len(pending))

    svc = get_drive_service()

    stats = dict(
        processed=0, extracted=0, extraction_failed=0,
        persons_total=0, persons_matched=0,
        links_inserted=0, links_existing=0,
        deferred_persons=[],
    )

    for i, row in enumerate(pending, 1):
        logger.info("[%d/%d] doc_id=%s company=%s file=%s",
                    i, len(pending), row["doc_id"], row["company_name"][:30], row["file_name"][:35])
        try:
            pdf_bytes = download_pdf(svc, row["google_drive_file_id"])
        except HttpError as e:
            logger.error("  Drive download 404: %s", e.resp.status)
            stats["extraction_failed"] += 1
            continue
        if len(pdf_bytes) < 1000:
            logger.warning("  PDF too small (%d bytes) — likely error doc", len(pdf_bytes))
            stats["extraction_failed"] += 1
            continue

        try:
            text = pdf_to_text(pdf_bytes)
        except Exception as e:
            logger.error("  pdftotext failed: %s", e)
            stats["extraction_failed"] += 1
            continue
        if len(text) < 200:
            logger.warning("  Text too short (%d chars) — image-only PDF?", len(text))
            stats["extraction_failed"] += 1
            continue

        data = deepseek_extract(text)
        if not data or "persons" not in data:
            stats["extraction_failed"] += 1
            continue
        stats["extracted"] += 1
        stats["processed"] += 1

        persons = data.get("persons", [])
        stats["persons_total"] += len(persons)

        # Normalize data: defensively handle persons with role=None/missing
        def role_str(p): return (p.get("role") or "").upper() if isinstance(p, dict) else ""
        directors = [p for p in persons if "DIREKTUR" in role_str(p)]
        commissioners = [p for p in persons if "KOMISARIS" in role_str(p)]
        data["directors"] = directors
        data["commissioners"] = commissioners

        if apply:
            update_doc_extraction(conn, row["doc_id"], data)

        # Match each person → client → upsert link
        per_doc_links = []
        for person in persons:
            client = match_person_to_client(person, client_idx)
            if not client:
                stats["deferred_persons"].append({
                    "company_id": row["company_id"],
                    "company_name": row["company_name"],
                    "doc_id": row["doc_id"],
                    "person_name": person.get("name"),
                    "person_role": person.get("role"),
                    "nationality": person.get("nationality"),
                })
                continue
            stats["persons_matched"] += 1

            role = role_to_link_role(person.get("role", ""))
            shares = person.get("shares") if isinstance(person.get("shares"), int) else None
            pct = person.get("ownership_pct") if isinstance(person.get("ownership_pct"), (int, float)) else None
            notes = f"src={LINK_SOURCE_TAG} role={person.get('role')} doc_id={row['doc_id']}"

            if apply:
                inserted = upsert_link(conn, client["id"], row["company_id"], role, shares, pct, notes)
                if inserted:
                    stats["links_inserted"] += 1
                else:
                    stats["links_existing"] += 1
                per_doc_links.append((client["id"], client["full_name"], role, "INSERTED" if inserted else "EXISTING"))
            else:
                per_doc_links.append((client["id"], client["full_name"], role, "WOULD_INSERT"))

        for link in per_doc_links:
            logger.info("    LINK client_id=%s name=%s role=%s [%s]", *link)

        if apply:
            conn.commit()

        time.sleep(args.sleep)

    # Save deferred persons
    if stats["deferred_persons"]:
        out_path = f"/tmp/profil_backfill_deferred_persons_{time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(out_path, "w") as fp:
            json.dump(stats["deferred_persons"], fp, indent=2, ensure_ascii=False)
        logger.info("Saved %d deferred persons to %s", len(stats["deferred_persons"]), out_path)

    print("\n=== SUMMARY ===")
    for k in ["processed", "extracted", "extraction_failed", "persons_total",
              "persons_matched", "links_inserted", "links_existing"]:
        print(f"  {k}: {stats[k]}")
    print(f"  deferred_persons: {len(stats['deferred_persons'])}")
    if not apply:
        print("\n  DRY RUN — re-run with --apply to actually update DB.")

    conn.close()


if __name__ == "__main__":
    main()
