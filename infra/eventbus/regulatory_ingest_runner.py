#!/usr/bin/env python3
"""regulatory_ingest_runner.py — execute the regulatory-ingest skill.

Implements the 6-stage pipeline described in
`~/.claude/skills/regulatory-ingest.md`:

  1. Verify EXISTS via JDIH web search
  2. Download PDF to local archive
  3. Upload to Drive /peraturan/<domain>/
  4. Update spreadsheet GAP_ANALYSIS
  5. Push to NotebookLM (domain-routed NB)
  6. Embed + upsert to Qdrant via LegalIngestionService
  7. KG entity extraction via kg_incremental_extraction.py
  8. Final report

Designed to be invoked:
  - Manually: python3 regulatory_ingest_runner.py --reg "PMK 81/2024" --domain tax
  - From devils-advocate runner when NOT_FOUND_IN_QUERIED is verified-real
  - From a future auto-watcher on bz:regulatory.delta.detected events

Idempotent: safe to re-run, won't duplicate.
"""
from __future__ import annotations
import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path.home() / "logs" / "regulatory-ingest.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger("reg-ingest")

# ──────────────────────────────────────────────────────────────────────────
# Constants — canonical paths and IDs
# ──────────────────────────────────────────────────────────────────────────
PERATURAN_BASE = Path.home() / "Desktop/nuzantara/data/source_documents/peraturan"
SHEET_ID = "1Je7eAK3ya_P5yY9L_JtnwRzkTDrucnzgZ4PvvWlb2us"
DRIVE_SA_PATH = Path.home() / ".nuzantara-drive-sa.json"
BACKEND_ENV = Path.home() / "Desktop/nuzantara/apps/backend-rag/.env"
PYTHON_BIN = "/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3"

# NB UUID map (mirror of devils_advocate_runner.NB_REGISTRY)
NB_REGISTRY = {
    "tax": "d4b2eedb-9863-4a1a-81ff-a11b0b45d853",        # NB-4
    "visa": "cff93ab0-813a-42f2-a8de-36987e724271",       # NB-2
    "property": "d9438180-5e63-4e2a-a473-6061101f6a8d",   # NB-5
    "company": "933509f9-1561-403d-bd44-4a7a67a36df2",    # NB-3
    "regulatory": "a17f134e-b9ab-42d9-bfc2-5bbc45165c76", # NB-INTEL-Regulation
    "labor": "933509f9-1561-403d-bd44-4a7a67a36df2",      # NB-3 (same as company)
}


# ──────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────
def _safe_filename(reg_code: str) -> str:
    """Canonicalize reg_code into a filesystem-safe form."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", reg_code.replace("/", "-"))


def _load_qdrant_creds() -> tuple[str, str]:
    """Read QDRANT_URL + QDRANT_API_KEY from backend-rag/.env."""
    qdrant_url = qdrant_key = None
    if not BACKEND_ENV.exists():
        raise RuntimeError(f"backend env not found: {BACKEND_ENV}")
    with open(BACKEND_ENV) as fp:
        for line in fp:
            line = line.strip()
            if line.startswith("QDRANT_URL"):
                qdrant_url = line.split("=", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("QDRANT_API_KEY"):
                qdrant_key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not qdrant_url or not qdrant_key:
        raise RuntimeError("QDRANT_URL / QDRANT_API_KEY missing in backend env")
    return qdrant_url, qdrant_key


# ──────────────────────────────────────────────────────────────────────────
# Step 1 — Verify EXISTS (web search + JDIH check)
# ──────────────────────────────────────────────────────────────────────────
def step1_verify(reg_code: str, jdih_url: str | None = None) -> dict:
    """If jdih_url is provided, try fetching it. Otherwise return needs_url=True
    so caller (or LLM) can resolve."""
    if not jdih_url:
        return {"verified": False, "needs_url": True,
                "hint": f"web-search '{reg_code} site:peraturan.go.id OR site:peraturan.bpk.go.id OR site:jdih.kemenkeu.go.id'"}
    try:
        result = subprocess.run(
            ["curl", "-sfL", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "20", jdih_url],
            capture_output=True, text=True, timeout=25,
        )
        code = result.stdout.strip()
        if code == "200":
            return {"verified": True, "jdih_url": jdih_url, "http": code}
        return {"verified": False, "http": code, "url_failed": jdih_url}
    except Exception as e:
        return {"verified": False, "error": str(e)}


# ──────────────────────────────────────────────────────────────────────────
# Step 2 — Download PDF
# ──────────────────────────────────────────────────────────────────────────
def step2_download(reg_code: str, domain: str, jdih_url: str) -> dict:
    """Download PDF with HTML→text fallback for sources that publish only as
    press release / siaran-pers / news article (e.g. KEP DJP series).

    Returns: {"ok": True, "pdf_path": str, "is_text_fallback": bool}
    """
    safe = _safe_filename(reg_code)
    domain_dir = PERATURAN_BASE / domain
    domain_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = domain_dir / f"{safe}.pdf"
    txt_path = domain_dir / f"{safe}.txt"

    # Skip if PDF cached
    if pdf_path.exists() and pdf_path.stat().st_size > 50_000:
        log.info("PDF exists already at %s, skipping download", pdf_path)
        return {"ok": True, "pdf_path": str(pdf_path), "size": pdf_path.stat().st_size,
                "skipped": True, "is_text_fallback": False}
    # Skip if TXT cached (from previous fallback)
    if txt_path.exists() and txt_path.stat().st_size > 500:
        log.info("TXT exists already at %s, skipping download (text fallback)", txt_path)
        return {"ok": True, "pdf_path": str(txt_path), "size": txt_path.stat().st_size,
                "skipped": True, "is_text_fallback": True}

    log.info("downloading: %s → %s", jdih_url, pdf_path)
    try:
        result = subprocess.run(
            ["curl", "-sfL", "-o", str(pdf_path), "--max-time", "60", jdih_url],
            capture_output=True, text=True, timeout=70,
        )
        if result.returncode != 0:
            return {"ok": False, "error": f"curl exit {result.returncode}: {result.stderr[:200]}"}
        size = pdf_path.stat().st_size
        # Validate magic bytes for PDF
        with open(pdf_path, "rb") as fp:
            magic = fp.read(4)
        if magic.startswith(b"%PDF") and size >= 50_000:
            return {"ok": True, "pdf_path": str(pdf_path), "size": size,
                    "is_text_fallback": False}

        # Not a PDF — fallback to HTML→text extraction
        log.warning(
            "downloaded file is not a valid PDF (magic=%r, size=%d). "
            "Falling back to HTML→text extraction for sources like "
            "press releases / siaran-pers.",
            magic, size,
        )
        # Re-fetch as HTML if the previous file was small (likely error page);
        # otherwise re-use what we have to feed the HTML parser.
        try:
            html_text = subprocess.run(
                ["curl", "-sfL", "--max-time", "60", jdih_url],
                capture_output=True, text=True, timeout=70,
            ).stdout
        except Exception as e:
            return {"ok": False, "error": f"HTML re-fetch failed: {e}"}

        # Extract visible text via regex (no BeautifulSoup dep)
        import html as html_mod
        clean = re.sub(r"<script[^>]*>.*?</script>", "", html_text,
                       flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r"<style[^>]*>.*?</style>", "", clean,
                       flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r"<[^>]+>", " ", clean)
        clean = html_mod.unescape(clean)
        clean = re.sub(r"\s+", " ", clean).strip()

        if len(clean) < 500:
            # Even the HTML body is too small — likely 404 or paywalled
            return {"ok": False, "error": "html_body_too_small",
                    "size": len(clean), "magic": str(magic)}

        # Persist as .txt (LegalIngestionService → parsers.auto_detect_and_parse → .txt path)
        # Remove invalid PDF first
        try:
            pdf_path.unlink()
        except Exception:
            pass
        # Prefix with regulation header so chunker has context
        header = f"REGULATION: {reg_code}\nSOURCE_URL: {jdih_url}\nFETCH_DATE: {datetime.now(timezone.utc).isoformat()}\nINGEST_MODE: text-fallback (HTML→text extraction)\n\n"
        txt_path.write_text(header + clean[:500_000])  # cap at 500k chars to be safe
        log.info("text fallback OK: extracted %d chars → %s", len(clean), txt_path)
        return {"ok": True, "pdf_path": str(txt_path), "size": txt_path.stat().st_size,
                "is_text_fallback": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ──────────────────────────────────────────────────────────────────────────
# Step 3 — Upload to Drive
# ──────────────────────────────────────────────────────────────────────────
def step3_drive_upload(pdf_path: str, reg_code: str, domain: str,
                       official_title: str, jdih_url: str) -> dict:
    if not DRIVE_SA_PATH.exists():
        return {"ok": False, "error": f"SA file missing: {DRIVE_SA_PATH}"}
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        return {"ok": False, "error": "google-api-python-client not installed"}

    creds = service_account.Credentials.from_service_account_file(
        str(DRIVE_SA_PATH),
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)

    # Find or create peraturan/<domain>/ folder
    # First, search for existing 'peraturan' folder owned by SA or accessible
    q = "name='peraturan' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    folders = drive.files().list(q=q, fields="files(id,name,parents)").execute().get("files", [])
    if not folders:
        log.warning("'peraturan' folder not accessible to SA — uploading to SA root")
        peraturan_id = "root"
    else:
        peraturan_id = folders[0]["id"]
        log.info("found peraturan folder: %s", peraturan_id)

    # Find or create domain subfolder
    q_sub = f"name='{domain}' and mimeType='application/vnd.google-apps.folder' and '{peraturan_id}' in parents and trashed=false"
    subs = drive.files().list(q=q_sub, fields="files(id,name)").execute().get("files", [])
    if subs:
        domain_id = subs[0]["id"]
    else:
        # Create
        meta = {"name": domain, "mimeType": "application/vnd.google-apps.folder",
                "parents": [peraturan_id]}
        try:
            domain_folder = drive.files().create(body=meta, fields="id").execute()
            domain_id = domain_folder["id"]
            log.info("created %s subfolder: %s", domain, domain_id)
        except Exception as e:
            log.warning("create subfolder failed: %s — uploading to peraturan root", e)
            domain_id = peraturan_id

    # Idempotency: check if file with this title already exists
    safe = _safe_filename(reg_code)
    q_file = f"name='{safe}.pdf' and '{domain_id}' in parents and trashed=false"
    existing = drive.files().list(q=q_file, fields="files(id,webViewLink)").execute().get("files", [])
    if existing:
        log.info("file already on Drive: %s", existing[0]["id"])
        return {"ok": True, "drive_file_id": existing[0]["id"],
                "drive_url": existing[0]["webViewLink"], "skipped": True}

    media = MediaFileUpload(pdf_path, mimetype="application/pdf", resumable=True)
    file_meta = {
        "name": f"{safe}.pdf",
        "parents": [domain_id],
        "description": (
            f"{reg_code} | {official_title} | JDIH: {jdih_url} | "
            f"uploaded by regulatory-ingest skill {datetime.now(timezone.utc).isoformat()}"
        ),
    }
    try:
        result = drive.files().create(body=file_meta, media_body=media,
                                      fields="id,webViewLink").execute()
        log.info("uploaded to Drive: %s", result["id"])
        return {"ok": True, "drive_file_id": result["id"], "drive_url": result["webViewLink"]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ──────────────────────────────────────────────────────────────────────────
# Step 4 — Spreadsheet GAP_ANALYSIS update
# ──────────────────────────────────────────────────────────────────────────
def step4_spreadsheet(reg_code: str, domain: str, official_title: str,
                      jdih_url: str, priority: str, drive_url: str,
                      notes: str) -> dict:
    if not DRIVE_SA_PATH.exists():
        return {"ok": False, "error": "SA missing"}
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        return {"ok": False, "error": "google-api-python-client not installed"}

    creds = service_account.Credentials.from_service_account_file(
        str(DRIVE_SA_PATH),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)

    # Check if reg already exists
    result = sheets.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range="GAP_ANALYSIS!C2:C200"
    ).execute()
    existing = [r[0] if r else "" for r in result.get("values", [])]

    why = f"Auto-ingested via regulatory-ingest skill"
    new_row = [priority, domain.capitalize(), reg_code, official_title,
               why, jdih_url, "DOWNLOADED+SHEET", "YES", "PENDING", notes]

    if reg_code in existing:
        row_idx = existing.index(reg_code) + 2
        update_range = f"GAP_ANALYSIS!A{row_idx}:J{row_idx}"
        sheets.spreadsheets().values().update(
            spreadsheetId=SHEET_ID, range=update_range, valueInputOption="RAW",
            body={"values": [new_row]},
        ).execute()
        log.info("updated existing row %d for %s", row_idx, reg_code)
        return {"ok": True, "action": "updated", "row": row_idx}
    else:
        result = sheets.spreadsheets().values().append(
            spreadsheetId=SHEET_ID, range="GAP_ANALYSIS!A:J",
            valueInputOption="RAW", body={"values": [new_row]},
        ).execute()
        log.info("appended new row for %s", reg_code)
        return {"ok": True, "action": "appended",
                "range": result.get("updates", {}).get("updatedRange")}


# ──────────────────────────────────────────────────────────────────────────
# Step 5 — NotebookLM push
# ──────────────────────────────────────────────────────────────────────────
def step5_nlm_push(reg_code: str, domain: str, jdih_url: str,
                   official_title: str, pdf_path: str | None = None) -> dict:
    nb_uuid = NB_REGISTRY.get(domain)
    if not nb_uuid:
        return {"ok": False, "error": f"no NB registered for domain={domain}"}

    # Try URL first
    log.info("nlm source add (url) → NB-%s for %s", nb_uuid[:8], reg_code)
    result = subprocess.run(
        ["nlm", "source", "add", nb_uuid, "--url", jdih_url],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode == 0:
        # Extract source id from output
        source_id_match = re.search(r"Source ID: ([a-f0-9-]+)", result.stdout)
        source_id = source_id_match.group(1) if source_id_match else "unknown"
        log.info("✓ added via URL: source_id=%s", source_id)
        return {"ok": True, "source_id": source_id, "nb_uuid": nb_uuid, "method": "url"}

    # Fallback: text paste
    log.warning("URL push failed, trying text fallback. stderr: %s", result.stderr[:200])
    if pdf_path and Path(pdf_path).exists():
        try:
            # Extract text via pdftotext if available
            txt_result = subprocess.run(
                ["pdftotext", "-layout", pdf_path, "-"],
                capture_output=True, text=True, timeout=60,
            )
            content = txt_result.stdout[:8000] if txt_result.returncode == 0 else ""
        except Exception:
            content = ""
    else:
        content = ""

    text = (f"REGULATION: {official_title} ({reg_code}). "
            f"SOURCE: {jdih_url}. CONTENT: {content}")
    result2 = subprocess.run(
        ["nlm", "source", "add", nb_uuid, "--text", text],
        capture_output=True, text=True, timeout=120,
    )
    if result2.returncode == 0:
        source_id_match = re.search(r"Source ID: ([a-f0-9-]+)", result2.stdout)
        source_id = source_id_match.group(1) if source_id_match else "unknown"
        log.info("✓ added via text: source_id=%s", source_id)
        return {"ok": True, "source_id": source_id, "nb_uuid": nb_uuid, "method": "text"}
    return {"ok": False, "error": f"both URL and text push failed: {result2.stderr[:200]}"}


# ──────────────────────────────────────────────────────────────────────────
# Step 6 — Qdrant embed + upsert via LegalIngestionService
# ──────────────────────────────────────────────────────────────────────────
def step6_qdrant_ingest(pdf_path: str, reg_code: str, official_title: str,
                        domain: str) -> dict:
    if not Path(pdf_path).exists():
        return {"ok": False, "error": f"PDF not found at {pdf_path}"}

    backend_dir = Path.home() / "Desktop/nuzantara/apps/backend-rag"
    venv_python = backend_dir / ".venv/bin/python"
    if not venv_python.exists():
        return {"ok": False, "error": f"backend venv not found: {venv_python}"}

    # Inline ingest script (uses LegalIngestionService canonical path)
    ingest_code = f"""
import asyncio, json, sys, os
sys.path.insert(0, '{backend_dir}')
from dotenv import load_dotenv
load_dotenv('{backend_dir}/.env', override=True)
from backend.services.ingestion.legal_ingestion_service import LegalIngestionService

async def main():
    service = LegalIngestionService(collection_name="legal_unified_2026")
    try:
        result = await service.ingest_legal_document(
            file_path={pdf_path!r},
            title={official_title + ' (' + reg_code + ')'!r},
            category={domain!r},
        )
        print(json.dumps({{"ok": True, "result": str(result)[:500]}}))
    except Exception as e:
        print(json.dumps({{"ok": False, "error": f"{{type(e).__name__}}: {{str(e)[:300]}}"}}))

asyncio.run(main())
"""
    log.info("running LegalIngestionService for %s", reg_code)
    try:
        result = subprocess.run(
            [str(venv_python), "-c", ingest_code],
            capture_output=True, text=True, timeout=600,
            cwd=str(backend_dir),
        )
        if result.returncode != 0:
            return {"ok": False, "error": f"venv exec failed: {result.stderr[-500:]}"}
        # Parse last JSON line
        last_line = result.stdout.strip().split("\n")[-1]
        try:
            return json.loads(last_line)
        except json.JSONDecodeError:
            return {"ok": False, "error": f"output not JSON: {result.stdout[-300:]}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "ingest timed out (>10 min)"}


# ──────────────────────────────────────────────────────────────────────────
# Step 7 — KG entity extraction (incremental)
# ──────────────────────────────────────────────────────────────────────────
def step7_kg_extract(domain: str, limit: int = 200) -> dict:
    backend_dir = Path.home() / "Desktop/nuzantara/apps/backend-rag"
    venv_python = backend_dir / ".venv/bin/python"
    script = backend_dir / "scripts/kg_incremental_extraction.py"
    if not script.exists():
        return {"ok": False, "error": f"script not found: {script}"}

    log.info("running kg_incremental_extraction limit=%d", limit)
    try:
        result = subprocess.run(
            [str(venv_python), str(script),
             "--collection", "legal_unified_2026",
             "--limit", str(limit)],
            capture_output=True, text=True, timeout=900,
            cwd=str(backend_dir),
        )
        # Parse output for entity/edge counts (script logs them)
        nodes_match = re.search(r"(\d+) entities? extracted", result.stdout)
        edges_match = re.search(r"(\d+) edges? created", result.stdout)
        return {
            "ok": result.returncode == 0,
            "exit": result.returncode,
            "entities": int(nodes_match.group(1)) if nodes_match else None,
            "edges": int(edges_match.group(1)) if edges_match else None,
            "stderr_tail": result.stderr[-300:] if result.returncode != 0 else None,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "KG extraction timed out (>15 min)"}


# ──────────────────────────────────────────────────────────────────────────
# Step 8 — Update spreadsheet final + report
# ──────────────────────────────────────────────────────────────────────────
def step8_finalize(reg_code: str, summary: dict) -> dict:
    """Update spreadsheet with final FULL status."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        return {"ok": False, "error": "google-api-python-client not installed"}

    creds = service_account.Credentials.from_service_account_file(
        str(DRIVE_SA_PATH),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)

    result = sheets.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range="GAP_ANALYSIS!C2:C200"
    ).execute()
    existing = [r[0] if r else "" for r in result.get("values", [])]
    if reg_code not in existing:
        return {"ok": False, "error": "row not found in spreadsheet"}

    row_idx = existing.index(reg_code) + 2
    completed_stages = []
    for k in ["pdf", "drive", "sheet", "nb", "qdrant", "kg"]:
        v = summary.get(k, {})
        if isinstance(v, dict) and v.get("ok"):
            completed_stages.append(k.upper())

    status = "DOWNLOADED+" + "+".join(completed_stages[1:]) if len(completed_stages) > 1 else "PARTIAL"
    in_qdrant = "YES" if summary.get("qdrant", {}).get("ok") else "NO"
    in_drive = "YES" if summary.get("drive", {}).get("ok") else "NO"

    notes = (f"PDF: {summary.get('drive',{}).get('drive_url','—')} | "
             f"NB-{summary.get('nb',{}).get('nb_uuid','?')[:8]} src {summary.get('nb',{}).get('source_id','?')} | "
             f"KG entities: {summary.get('kg',{}).get('entities','?')} | "
             f"Ingested: {datetime.now(timezone.utc).isoformat()}")

    update_range = f"GAP_ANALYSIS!G{row_idx}:J{row_idx}"
    sheets.spreadsheets().values().update(
        spreadsheetId=SHEET_ID, range=update_range, valueInputOption="RAW",
        body={"values": [[status, in_drive, in_qdrant, notes]]},
    ).execute()
    return {"ok": True, "row": row_idx, "status": status}


# ──────────────────────────────────────────────────────────────────────────
# Main orchestrator
# ──────────────────────────────────────────────────────────────────────────
def run(reg_code: str, domain: str, jdih_url: str, official_title: str,
        priority: str = "MEDIUM", skip_kg: bool = False) -> dict:
    summary = {"reg_code": reg_code, "domain": domain, "started_at": datetime.now(timezone.utc).isoformat()}
    log.info("=== INGEST START: %s (domain=%s) ===", reg_code, domain)

    # Step 1 — verify
    summary["verify"] = step1_verify(reg_code, jdih_url)
    if not summary["verify"].get("verified"):
        log.error("Step 1 FAILED — abort: %s", summary["verify"])
        return summary

    # Step 2 — download
    summary["pdf"] = step2_download(reg_code, domain, jdih_url)
    pdf_path = summary["pdf"].get("pdf_path") if summary["pdf"].get("ok") else None

    # Step 3 — Drive upload (only if PDF ok)
    if pdf_path:
        summary["drive"] = step3_drive_upload(pdf_path, reg_code, domain, official_title, jdih_url)
    else:
        summary["drive"] = {"ok": False, "skipped": "no_pdf"}

    drive_url = summary["drive"].get("drive_url", "—")

    # Step 4 — spreadsheet (initial entry)
    summary["sheet"] = step4_spreadsheet(
        reg_code, domain, official_title, jdih_url, priority, drive_url,
        notes=f"In progress, started {datetime.now(timezone.utc).isoformat()}",
    )

    # Step 5 — NLM push
    summary["nb"] = step5_nlm_push(reg_code, domain, jdih_url, official_title, pdf_path)

    # Step 6 — Qdrant embed (only if PDF ok)
    if pdf_path:
        summary["qdrant"] = step6_qdrant_ingest(pdf_path, reg_code, official_title, domain)
    else:
        summary["qdrant"] = {"ok": False, "skipped": "no_pdf"}

    # Step 7 — KG extraction (only if Qdrant succeeded)
    if not skip_kg and summary["qdrant"].get("ok"):
        summary["kg"] = step7_kg_extract(domain)
    else:
        summary["kg"] = {"ok": False, "skipped": "no_qdrant_or_disabled"}

    # Step 8 — finalize
    summary["finalize"] = step8_finalize(reg_code, summary)

    summary["completed_at"] = datetime.now(timezone.utc).isoformat()
    log.info("=== INGEST DONE: %s ===", reg_code)
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reg", required=True, help="Regulation code (e.g. 'PMK 81/2024')")
    ap.add_argument("--domain", required=True,
                    choices=["tax", "visa", "property", "company", "regulatory", "labor"])
    ap.add_argument("--jdih-url", required=True, help="Authoritative JDIH URL")
    ap.add_argument("--title", required=True, help="Official title (Bahasa Indonesia)")
    ap.add_argument("--priority", default="MEDIUM", choices=["CRITICAL", "HIGH", "MEDIUM", "LOW"])
    ap.add_argument("--skip-kg", action="store_true", help="Skip Step 7 KG extraction")
    args = ap.parse_args()

    result = run(args.reg, args.domain, args.jdih_url, args.title,
                 args.priority, args.skip_kg)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("finalize", {}).get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
