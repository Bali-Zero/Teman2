#!/usr/bin/env python3
"""CRM-Guardian Gemini CLI Worker (gemini --print variant).

Replacement driver for the Playwright Gemini Web App worker
(scripts/crm_guardian_gemini_worker.py), which is blocked by Google's
anti-automation policy on Chrome-for-Testing (verified 2026-05-17 with
"Impossibile eseguire l'accesso" → invalid_grant on gemini.google.com).

Architecture:
  - Use `agy` CLI (v1.0.0 Antigravity, /Users/nuzantara/.local/bin/agy) via subprocess
  - OAuth-only (zero paid API), Workspace AI add-on Workflow free tier
  - List Drive files via service account / OAuth user (no Drive @mention
    available outside the Web App — we inline file metadata + small text
    content into the prompt)
  - Cross-folder Phase 1: client root + linked companies via
    client_company_links → aggregate file inventory across folders

Tradeoffs vs Playwright Web App driver:
  + No browser, no anti-bot, no DOM scraping
  + Stable for cron H24 (no Chrome session decay)
  + Free OAuth, no API key
  - No native Drive @mention — we expose file names/types/sizes/IDs only,
    not full file content (would explode prompt size for 50+ docs per
    cliente). Gemini uses metadata to reason about identity/visa/company
    structure. For PDF/image OCR we rely on the existing crm-drive OCR
    pipeline (drive_poll_service → OCR worker writes to client_documents).

Flow per client:
  1. Resolve client + linked companies (active links, Drive folder set)
  2. Aggregate file inventory cross-folder (cliente root + companies)
  3. Compute fingerprint, skip if unchanged
  4. Mark queue 'running'
  5. Build prompt: L1_extraction_v2.md + <CROSS_FOLDER_CONTEXT> +
     <FILE_INVENTORY> table (file id, name, type, size, modifiedTime,
     source_folder_name) — Gemini reasons from metadata, not OCR
  6. Call `gemini -p "<full_prompt>"` subprocess
  7. Parse JSON fenced block from stdout
  8. Validate Pydantic L1ClientSummary
  9. Write clients.ai_summary (or audit-only if dry_run)
  10. Mark queue terminal

Usage:
    python scripts/crm_guardian_gemini_cli_worker.py --client-id 70 --dry-run
    python scripts/crm_guardian_gemini_cli_worker.py --from-queue --max 3
    python scripts/crm_guardian_gemini_cli_worker.py --client-id 70 \
        --dry-run --model gemini-2.5-pro
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import logging
import os
import re
import signal
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_RAG = REPO_ROOT / "apps" / "backend-rag"
sys.path.insert(0, str(BACKEND_RAG))

from backend.services.crm_guardian.ocr import (  # noqa: E402
    PRIORITY_DOC_TYPES,
    ExtractionResult,
    OcrHealth,
    check_health,
    extract_file_content,
    get_cached_content,
    upsert_cache_row,
)
from backend.services.crm_guardian.schemas import (  # noqa: E402
    SCHEMA_VERSION,
    L1ClientSummary,
)

LOG = logging.getLogger("crm_guardian.cli_worker")

# Phase 1.5 prompt is the new default (Phase 1 v2 is metadata-only; v3 adds
# the OCR-content blocks + identity-guardrail). The legacy v2 file is kept
# on disk for rollback drills.
DEFAULT_PROMPT_FILE = BACKEND_RAG / "backend/services/crm_guardian/prompts/L1_extraction_v4.md"
LEGACY_V3_PROMPT_FILE = BACKEND_RAG / "backend/services/crm_guardian/prompts/L1_extraction_v3.md"
LEGACY_PROMPT_FILE = BACKEND_RAG / "backend/services/crm_guardian/prompts/L1_extraction_v2.md"
PROMPT_VERSION_V2 = "L1_extraction_v2"  # legacy, kept for old queue rows
PROMPT_VERSION_V3 = "L1_extraction_v3"
PROMPT_VERSION_V4 = "L1_extraction_v4"  # 2026-05-23: anti-chat-mode header

RAW_DUMP_DIR = Path.home() / ".crm_guardian" / "raw_dumps_cli"
RAW_DUMP_DIR.mkdir(parents=True, exist_ok=True)

GEMINI_CLI = "/Users/nuzantara/.local/bin/agy"  # agy CLI v1.0.0 (Antigravity), Gemini 3.1 Pro default via Google AI Ultra OAuth — replaces /opt/homebrew/bin/gemini (deprecated 2026-05-21, 256-color exit-1 regression under launchd)
GEMINI_TIMEOUT_SECONDS = int(os.getenv("CRM_GUARDIAN_GEMINI_TIMEOUT_SECONDS", "900"))
GEMINI_DEFAULT_MODEL: str | None = None  # agy uses CLI default model — does NOT support `-m` flag (prints help instead)
STALE_RUNNING_SECONDS = int(os.getenv("CRM_GUARDIAN_STALE_RUNNING_SECONDS", "900"))

# Phase 1.5 OCR budget per client. Tesseract is fast but akta scans can spike
# latency; we cap how many priority files we OCR in a single client run.
# Excess files fall through as metadata-only (extractor='skipped').
OCR_MAX_FILES_PER_CLIENT = 30


def _terminate_gemini_process(proc: subprocess.Popen[str]) -> None:
    """Terminate the agy process group created for a single CLI call."""
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except Exception as exc:
        LOG.warning("failed to SIGTERM agy process group pid=%s: %s", proc.pid, exc)
    try:
        proc.wait(timeout=5)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except Exception as exc:
        LOG.warning("failed to SIGKILL agy process group pid=%s: %s", proc.pid, exc)
        return
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        LOG.warning("agy process group pid=%s survived SIGKILL timeout", proc.pid)


def _tail_text(path: Path, *, limit: int = 500) -> str:
    """Read a small diagnostic tail without loading large CLI output into logs."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[-limit:]
    except FileNotFoundError:
        return ""


# ---------------------------------------------------------------------------
# DB helpers (shared shape with Playwright worker)
# ---------------------------------------------------------------------------

def _resolve_db_url() -> str:
    """Resolve local flyctl-proxy DATABASE_URL (port 15432).

    Preferred env key order in ~/.nuzantara-secrets.env:
      1. DATABASE_URL_LOCAL  (already 127.0.0.1:15432)
      2. DATABASE_URL        (production .internal:5432 → rewritten to localhost)
    """
    secrets = Path.home() / ".nuzantara-secrets.env"
    if not secrets.exists():
        raise RuntimeError(f"Secrets file not found: {secrets}")

    raw_local: str | None = None
    raw_remote: str | None = None
    for line in secrets.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key == "DATABASE_URL_LOCAL":
            raw_local = value
        elif key == "DATABASE_URL":
            raw_remote = value

    if raw_local:
        return raw_local
    if raw_remote:
        return re.sub(r"@[^:/]+(\.internal)?:\d+", "@localhost:15432", raw_remote)
    raise RuntimeError(
        "DATABASE_URL_LOCAL or DATABASE_URL not found in ~/.nuzantara-secrets.env",
    )


async def fetch_client(conn, client_id: int) -> dict[str, Any] | None:
    """Fetch a CRM client row. Schema canonical 2026-05-17."""
    row = await conn.fetchrow(
        """
        SELECT id, full_name, email,
               google_drive_folder_id AS folder_id,
               drive_folder_url AS folder_link,
               ai_summary_file_hash, ai_summary_generated_at
        FROM clients WHERE id = $1
        """,
        client_id,
    )
    return dict(row) if row else None


async def fetch_linked_companies(conn, client_id: int) -> list[dict[str, Any]]:
    """Active company links for this client with their Drive folder ID(s).

    Phase 1.5 (2026-05-18): also returns `tax_dept_folder_id` (migration 182,
    populated by scripts/crm_guardian_tax_dept_apply.py). The tax-dept folder
    is the Bali Zero shared 'Members/<TeamMember>/<COMPANY>/' Drive area
    that holds SPT/PPN/PPh/LKPM filings outside the cliente canonical folder.
    Worker treats it as a 3rd source in aggregate_cross_folder_files when
    populated (NULL on most companies = same behavior as before).
    """
    rows = await conn.fetch(
        """
        SELECT
            ccl.company_id,
            ccl.role,
            ccl.is_primary,
            c.company_name,
            c.google_drive_folder_id,
            c.tax_dept_folder_id
        FROM client_company_links ccl
        JOIN companies c ON c.id = ccl.company_id
        WHERE ccl.client_id = $1
          AND ccl.status = 'active'
          AND (c.google_drive_folder_id IS NOT NULL OR c.tax_dept_folder_id IS NOT NULL)
        ORDER BY ccl.is_primary DESC, ccl.id ASC
        """,
        client_id,
    )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Drive helpers
# ---------------------------------------------------------------------------

async def list_drive_files(
    drive_service,
    folder_id: str,
    *,
    recursive: bool = True,
    max_depth: int = 3,
    exclude_folders: bool = True,
) -> list[dict[str, Any]]:
    """Page through non-trashed files in a Drive folder.

    Phase 1: recursive=True scends into subfolders (max_depth=3) because
    Bali Zero cliente folders are organized with canonical subfolders
    (00_Profile, 01_Immigration, etc.) — files live INSIDE the subfolders,
    not at root level. Without recursion the inventory contains only
    folder stubs and Gemini extracts nothing (verified empirically with
    client_id 70, 11 "files" = 11 empty subfolder shells).

    exclude_folders=True drops `application/vnd.google-apps.folder` entries
    from the returned list — they are navigated for recursion but not
    surfaced to the LLM (Gemini doesn't need to reason about folder
    structure, only file content metadata).

    max_depth=3 is sufficient for Bali Zero conventions:
      depth 0: client root (Oleksandr Ozolin)
      depth 1: 00_Profile / 01_Immigration / ...
      depth 2: nested categories (02_Company/AKTA, 03_Tax/SPT_2024, etc.)
      depth 3: occasional deeper archive subdirs

    Cycle protection: same folder_id visited twice returns immediately
    (cycles shouldn't exist in Drive but defensive against symlink edge
    cases via shortcuts).
    """
    files: list[dict[str, Any]] = []
    visited: set[str] = set()
    FOLDER_MIME = "application/vnd.google-apps.folder"

    async def _walk(fid: str, depth: int) -> None:
        if fid in visited:
            return
        visited.add(fid)
        if depth > max_depth:
            LOG.debug("Drive walk: max_depth %d reached at %s", max_depth, fid)
            return

        page_token: str | None = None
        while True:
            resp = drive_service.files().list(
                q=f"'{fid}' in parents and trashed=false",
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, size)",
                pageSize=200,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            for f in resp.get("files", []):
                is_folder = f.get("mimeType") == FOLDER_MIME
                if is_folder:
                    if recursive:
                        await _walk(f["id"], depth + 1)
                    if not exclude_folders:
                        files.append(f)
                else:
                    files.append(f)
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

    await _walk(folder_id, 0)
    return files


async def resolve_folder_name(drive_service, folder_id: str) -> str | None:
    try:
        meta = drive_service.files().get(
            fileId=folder_id, fields="name", supportsAllDrives=True,
        ).execute()
        return meta.get("name")
    except Exception as e:
        LOG.warning("resolve_folder_name failed for %s: %s", folder_id, e)
        return None


async def aggregate_cross_folder_files(
    drive_service,
    client_folder_id: str,
    linked_companies: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Merge file lists across cliente root + linked company folders.

    Each file enriched with source_folder_id; folder_id_to_name map for
    inventory rendering.
    """
    flat_files: list[dict[str, Any]] = []
    folder_id_to_name: dict[str, str] = {}

    try:
        cliente_files = await list_drive_files(drive_service, client_folder_id)
        for f in cliente_files:
            f["source_folder_id"] = client_folder_id
        flat_files.extend(cliente_files)
        cliente_name = await resolve_folder_name(drive_service, client_folder_id)
        if cliente_name:
            folder_id_to_name[client_folder_id] = cliente_name
    except Exception as e:
        LOG.warning("client folder %s aggregation failed: %s", client_folder_id, e)

    for company in linked_companies:
        cf_id = company.get("google_drive_folder_id")
        if cf_id:
            try:
                cf_files = await list_drive_files(drive_service, cf_id)
                for f in cf_files:
                    f["source_folder_id"] = cf_id
                flat_files.extend(cf_files)
                folder_id_to_name[cf_id] = company.get("company_name") or cf_id
            except Exception as e:
                LOG.warning(
                    "company folder %s (%s) aggregation failed: %s",
                    cf_id, company.get("company_name"), e,
                )

        # Phase 1.6 (2026-05-18): third source — tax department shared folder
        # (Members/<TeamMember>/<COMPANY>/) populated via migration 182 +
        # scripts/crm_guardian_tax_dept_apply.py. Holds SPT/PPN/PPh/LKPM that
        # don't live in the cliente canonical folder nor the company corporate
        # folder.
        tax_id = company.get("tax_dept_folder_id")
        if tax_id:
            try:
                tax_files = await list_drive_files(drive_service, tax_id)
                for f in tax_files:
                    f["source_folder_id"] = tax_id
                flat_files.extend(tax_files)
                folder_id_to_name[tax_id] = (
                    f"{company.get('company_name') or 'unknown'} (Tax Dept)"
                )
                LOG.info(
                    "tax-dept folder for company %s: +%d files",
                    company.get("company_name"), len(tax_files),
                )
            except Exception as e:
                LOG.warning(
                    "tax-dept folder %s (%s) aggregation failed: %s",
                    tax_id, company.get("company_name"), e,
                )

    return flat_files, folder_id_to_name


def compute_cross_folder_fingerprint(files: list[dict[str, Any]]) -> str:
    """SHA256 over sorted (source_folder_id, file_id, modifiedTime)."""
    pairs = sorted(
        (f.get("source_folder_id", ""), f["id"], f.get("modifiedTime", ""))
        for f in files
    )
    blob = json.dumps(pairs, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Phase 1.5 — OCR enrichment helpers
# ---------------------------------------------------------------------------

# Filename token → doc_type. Aligned with L1 schema enum + ocr.PRIORITY_DOC_TYPES.
# Order matters: more specific tokens FIRST so "Bukti Potong PPh21" doesn't
# match "pph" before "bukti_potong".
_DOC_TYPE_PATTERNS: list[tuple[str, str]] = [
    ("bukti potong", "bukti_potong"),
    ("bukti_potong", "bukti_potong"),
    ("evisa", "evisa"),
    ("e-visa", "evisa"),
    ("e visa", "evisa"),
    ("kitap", "kitap"),
    ("kitas", "kitas"),
    ("passport", "passport"),
    ("paspor", "passport"),
    ("akta pendirian", "akta"),
    ("akta perubahan", "akta"),
    ("akta", "akta"),
    ("sk kemenkumham", "sk"),
    ("sk pendirian", "sk"),
    ("sk perubahan", "sk"),
    ("sk ", "sk"),
    ("npwp", "npwp"),
    ("nib", "nib"),
    ("lkpm", "lkpm"),
    ("spt tahunan", "spt"),
    ("spt masa", "spt"),
    ("spt ppn", "spt"),
    ("spt pph", "spt"),
    ("spt ", "spt"),
    ("visa", "visa"),
]


def infer_doc_type_from_filename(filename: str | None) -> str | None:
    """Best-effort doc_type from filename tokens.

    Returns None when no pattern matches; ocr.extract_file_content() will
    treat None as non-priority and skip the file. Case-insensitive,
    space-normalised.
    """
    if not filename:
        return None
    lowered = filename.lower().replace("_", " ").replace("-", " ")
    for token, doc_type in _DOC_TYPE_PATTERNS:
        if token in lowered:
            return doc_type
    return None


def _drive_modified_time_ms(modified_time_iso: str | None) -> int:
    """Parse Drive RFC3339 modifiedTime → epoch milliseconds. Returns 0 on parse failure."""
    if not modified_time_iso:
        return 0
    try:
        # Drive returns e.g. "2023-03-24T08:15:00.000Z"
        dt = datetime.fromisoformat(modified_time_iso.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except (ValueError, AttributeError):
        return 0


async def download_drive_file_bytes(
    drive_service, file_id: str, *, max_bytes: int = 20 * 1024 * 1024,
) -> bytes | None:
    """Download a Drive file as bytes (max 20MB default).

    Runs in a thread because google-api-python-client is sync. Returns None
    on any failure (the worker skips OCR for that file, falls back to
    metadata-only in the inventory). The 20MB cap prevents memory blowups
    on accidental video/zip uploads inside a CRM folder.
    """
    def _sync_download() -> bytes | None:
        try:
            from googleapiclient.http import MediaIoBaseDownload
            request = drive_service.files().get_media(
                fileId=file_id, supportsAllDrives=True,
            )
            buf = io.BytesIO()
            downloader = MediaIoBaseDownload(buf, request, chunksize=4 * 1024 * 1024)
            done = False
            while not done:
                _, done = downloader.next_chunk()
                if buf.tell() > max_bytes:
                    LOG.warning("download_drive_file_bytes %s exceeded %d bytes, aborting",
                                file_id, max_bytes)
                    return None
            return buf.getvalue()
        except Exception as e:
            LOG.warning("download_drive_file_bytes %s failed: %s", file_id, e)
            return None

    return await asyncio.to_thread(_sync_download)


async def enrich_files_with_ocr(
    conn,
    drive_service,
    flat_files: list[dict[str, Any]],
    health: OcrHealth,
    *,
    budget: int = OCR_MAX_FILES_PER_CLIENT,
) -> dict[str, ExtractionResult]:
    """Extract text content for priority files, using the OCR cache when possible.

    Mutates each file dict with `inferred_doc_type` so build_file_inventory_block
    can render the type even when the file is non-priority (just for context).

    Returns: file_id → ExtractionResult dict, ONLY for files that went through
    extraction (cache hit or fresh extraction). Skipped/non-priority files
    are absent from the result. Worker uses this dict to render
    <FILE_CONTENT_SNIPPETS> in the prompt.

    Cache-first: every file is first looked up in crm_guardian_file_content_cache
    by (file_id, modified_time_ms). Cache hit → reconstruct ExtractionResult
    from the row. Cache miss → download bytes, extract, upsert row.

    Budget cap: at most `budget` fresh extractions per client. Excess priority
    files fall through to metadata-only. Cache hits do NOT count toward budget.
    """
    enriched: dict[str, ExtractionResult] = {}
    fresh_extractions = 0

    for f in flat_files:
        doc_type = infer_doc_type_from_filename(f.get("name"))
        f["inferred_doc_type"] = doc_type

        if doc_type not in PRIORITY_DOC_TYPES:
            continue

        file_id = f["id"]
        modtime_ms = _drive_modified_time_ms(f.get("modifiedTime"))

        # Cache lookup
        cached = await get_cached_content(conn, file_id, modtime_ms)
        if cached:
            if cached["text_content"]:
                enriched[file_id] = ExtractionResult(
                    text=cached["text_content"],
                    extractor=cached["extractor"],
                    confidence=cached["confidence"],
                    page_count=cached["page_count"],
                    duration_ms=0,
                    truncated=False,
                    notes="cache_hit",
                )
            continue

        # Budget guard for FRESH extractions
        if fresh_extractions >= budget:
            LOG.info(
                "ocr budget %d reached for this client, skipping further priority files",
                budget,
            )
            continue

        # Cache miss → fetch bytes + extract
        file_bytes = await download_drive_file_bytes(drive_service, file_id)
        if file_bytes is None:
            continue

        result = await extract_file_content(
            file_bytes=file_bytes,
            mime_type=f.get("mimeType", ""),
            doc_type=doc_type,
            health=health,
        )
        fresh_extractions += 1

        if result.extractor != "skipped" and result.text:
            enriched[file_id] = result

        # Always upsert: even 'skipped' rows are recorded so we don't retry
        # them on next bulk pass. Empty text + 'skipped' notes capture why.
        try:
            await upsert_cache_row(
                conn, file_id=file_id, modified_time_ms=modtime_ms, result=result,
            )
        except Exception as e:
            LOG.warning("ocr cache upsert failed for %s: %s", file_id, e)

    if fresh_extractions or enriched:
        LOG.info(
            "ocr enrichment: priority_files=%d fresh_ocr=%d cache_hits=%d snippets=%d",
            sum(1 for f in flat_files if f.get("inferred_doc_type") in PRIORITY_DOC_TYPES),
            fresh_extractions,
            len(enriched) - fresh_extractions if len(enriched) >= fresh_extractions else 0,
            len(enriched),
        )
    return enriched


# ---------------------------------------------------------------------------
# Prompt assembly (no Drive @mention — inline metadata table)
# ---------------------------------------------------------------------------

def build_cross_folder_context_block(
    client_id: int,
    client_root_folder: str,
    linked_companies: list[dict[str, Any]],
    client_full_name: str | None = None,
) -> str:
    """Render <CROSS_FOLDER_CONTEXT> block per L1_extraction_v3 spec.

    Phase 1.5: client_full_name is now load-bearing (prompt Article 1 —
    identity guardrail) — when supplied, the model MUST mirror it in
    identity.full_name. Defensive None to keep backward compat with the
    v2 prompt during the cutover.
    """
    lines = [
        "<CROSS_FOLDER_CONTEXT>",
        f"client_id: {client_id}",
    ]
    if client_full_name:
        lines.append(f"client_full_name: {client_full_name}")
    lines.append(f"client_root_folder: {client_root_folder}")
    if linked_companies:
        lines.append("linked_company_folders:")
        for c in linked_companies:
            lines.append(f"  - id: {c['google_drive_folder_id']}")
            lines.append(f"    company_name: {c['company_name']}")
            lines.append(f"    company_id: {c['company_id']}")
            lines.append(f"    role: {c['role']}")
            lines.append(f"    is_primary: {'true' if c['is_primary'] else 'false'}")
    else:
        lines.append("linked_company_folders: []")
    lines.append("</CROSS_FOLDER_CONTEXT>")
    return "\n".join(lines)


def build_file_inventory_block(
    flat_files: list[dict[str, Any]],
    folder_id_to_name: dict[str, str],
    _ocr_results: dict[str, ExtractionResult] | None = None,
) -> str:
    """Render <FILE_INVENTORY> block exposing file metadata to Gemini.

    Each row also tags the inferred doc_type (passport/akta/nib/...) so the
    model can prioritise the right files when extracting compliance fields.
    """
    lines = ["<FILE_INVENTORY>"]
    lines.append(
        "# Format: source_folder | file_id | name | mimeType | size_bytes | modifiedTime | inferred_doc_type"
    )
    for f in flat_files:
        src = folder_id_to_name.get(f.get("source_folder_id", ""), "?")
        size = f.get("size", "")
        doc_type = f.get("inferred_doc_type") or "-"
        lines.append(
            f"{src} | {f['id']} | {f.get('name', '?')} | "
            f"{f.get('mimeType', '?')} | {size} | {f.get('modifiedTime', '?')} | {doc_type}"
        )
    lines.append(f"# Total files: {len(flat_files)}")
    lines.append("</FILE_INVENTORY>")
    return "\n".join(lines)


def build_file_content_snippets_block(
    flat_files: list[dict[str, Any]],
    ocr_results: dict[str, ExtractionResult],
) -> str:
    """Render <FILE_CONTENT_SNIPPETS> with OCR-extracted text per priority file.

    Phase 1.5: the model gets to see actual document content (passport MRZ,
    akta capital section, NPWP number, etc.) instead of inferring from
    filenames. Snippets are truncated at MAX_TEXT_CHARS_PER_FILE in ocr.py
    so prompt size stays bounded (≈12k chars × up to 30 priority files ≈
    360k chars at worst-case — well under Gemini 2.5 Pro 1M context).
    """
    if not ocr_results:
        return "<FILE_CONTENT_SNIPPETS>\n# No OCR content extracted (no priority files, or OCR disabled).\n</FILE_CONTENT_SNIPPETS>"

    # Render in the same order as flat_files so the model can cross-reference
    # the inventory rows above.
    lines = ["<FILE_CONTENT_SNIPPETS>"]
    lines.append(
        "# OCR'd content from priority docs (passport/akta/nib/npwp/visa/lkpm/spt/...)."
    )
    lines.append(
        "# Use THIS for identity / compliance fields. Use filename inventory only as fallback."
    )
    rendered = 0
    for f in flat_files:
        fid = f["id"]
        result = ocr_results.get(fid)
        if result is None or not result.text:
            continue
        rendered += 1
        conf_str = f"{result.confidence:.2f}" if result.confidence is not None else "n/a"
        lines.append("")
        lines.append(f"--- file_id: {fid} ---")
        lines.append(
            f"# extractor={result.extractor} confidence={conf_str} "
            f"pages={result.page_count or '?'} truncated={result.truncated}"
        )
        lines.append(f"# filename: {f.get('name', '?')}")
        lines.append(result.text)

    lines.append("")
    lines.append(f"# Snippets rendered: {rendered}")
    lines.append("</FILE_CONTENT_SNIPPETS>")
    return "\n".join(lines)


def assemble_full_prompt(
    prompt_template: str,
    context_block: str,
    inventory_block: str,
    content_block: str | None = None,
) -> str:
    """Assemble the final prompt: template + context + inventory + content snippets."""
    if content_block:
        return (
            f"{context_block}\n\n{inventory_block}\n\n{content_block}\n\n{prompt_template}"
        )
    return f"{context_block}\n\n{inventory_block}\n\n{prompt_template}"


# ---------------------------------------------------------------------------
# Queue lifecycle (shared shape with Playwright worker)
# ---------------------------------------------------------------------------

async def queue_mark_running(conn, client_id: int, run_id: str) -> int | None:
    """Mark pending queue row 'running'. Returns row id or None."""
    row = await conn.fetchrow(
        """
        UPDATE crm_guardian_summary_queue
        SET status = 'running',
            attempts = attempts + 1,
            last_attempt_at = NOW(),
            started_at = COALESCE(started_at, NOW()),
            run_id = $2::uuid
        WHERE client_id = $1 AND status = 'pending'
        RETURNING id
        """,
        client_id, run_id,
    )
    return row["id"] if row else None


async def reset_stale_running_jobs(
    conn,
    *,
    stale_after_seconds: int = STALE_RUNNING_SECONDS,
) -> int:
    """Return abandoned running queue rows to pending before claiming work."""
    result = await conn.execute(
        """
        UPDATE crm_guardian_summary_queue
        SET status = 'pending',
            started_at = NULL,
            last_error = $2,
            completed_at = NULL
        WHERE status = 'running'
          AND started_at IS NOT NULL
          AND started_at < NOW() - ($1 * INTERVAL '1 second')
        """,
        stale_after_seconds,
        f"reset stale running job after {stale_after_seconds}s",
    )
    try:
        return int(result.rsplit(" ", 1)[1])
    except (IndexError, ValueError):
        LOG.warning("unexpected reset_stale_running_jobs result: %s", result)
        return 0


async def queue_mark_terminal(
    conn,
    queue_id: int | None,
    status: str,
    *,
    last_error: str | None = None,
    duration_ms: int | None = None,
    raw_response_path: str | None = None,
) -> None:
    """Mark queue row terminal with exponential backoff on retry-eligible errors."""
    if queue_id is None:
        return
    if status == "error":
        attempts_row = await conn.fetchrow(
            "SELECT attempts FROM crm_guardian_summary_queue WHERE id = $1",
            queue_id,
        )
        attempts = attempts_row["attempts"] if attempts_row else 1
        if attempts < 3:
            backoff_minutes = 15 * (2 ** (attempts - 1))
            await conn.execute(
                f"""
                UPDATE crm_guardian_summary_queue
                SET status = 'error',
                    completed_at = NOW(),
                    last_error = $2,
                    next_retry_at = NOW() + INTERVAL '{backoff_minutes} minutes',
                    duration_ms = COALESCE($3, duration_ms),
                    raw_response_path = COALESCE($4, raw_response_path)
                WHERE id = $1
                """,
                queue_id, last_error, duration_ms, raw_response_path,
            )
            return
    await conn.execute(
        """
        UPDATE crm_guardian_summary_queue
        SET status = $2,
            completed_at = NOW(),
            last_error = $3,
            duration_ms = COALESCE($4, duration_ms),
            raw_response_path = COALESCE($5, raw_response_path)
        WHERE id = $1
        """,
        queue_id, status, last_error, duration_ms, raw_response_path,
    )


# ---------------------------------------------------------------------------
# Gemini CLI driver
# ---------------------------------------------------------------------------

def call_gemini_cli(
    prompt: str,
    *,
    model: str | None = None,
    timeout_seconds: int = GEMINI_TIMEOUT_SECONDS,
) -> str:
    """Invoke `gemini -p <prompt>` and return stdout.

    Raises subprocess.TimeoutExpired on timeout, CalledProcessError on
    non-zero exit. Caller is responsible for retry/backoff logic.

    The prompt is passed via stdin while `-p/--print` selects non-interactive
    mode. This mirrors the stable local agent pattern and avoids argv limits
    on large CRM inventories.
    """
    if not Path(GEMINI_CLI).exists():
        raise RuntimeError(
            f"agy CLI not found at {GEMINI_CLI}. "
            "Install via Antigravity onboarding (Google AI Ultra subscription)."
        )

    # agy does NOT support `-m model` (prints help instead). Model is fixed to
    # CLI default (Gemini 3.1 Pro under Google AI Ultra OAuth). The legacy
    # `model` argument is accepted for back-compat but ignored when CLI=agy.
    cmd = [GEMINI_CLI, "-p", "--print-timeout", f"{timeout_seconds}s"]

    LOG.info(
        "Calling agy CLI (model=%s[ignored-on-agy] prompt_len=%d timeout=%ds)",
        model or "agy-default", len(prompt), timeout_seconds,
    )

    # Do not use subprocess.run(..., capture_output=True) here. The agy CLI can
    # delegate to a long-lived process that keeps inherited stdout/stderr pipes
    # open after the direct child is gone; communicate() then waits forever and
    # the CRM queue remains stuck in "running". Redirecting to files lets us
    # wait on the direct process only and still retain diagnostics on failure.
    capture_id = uuid.uuid4().hex
    prompt_path = RAW_DUMP_DIR / f"agy_prompt_{capture_id}.txt"
    stdout_path = RAW_DUMP_DIR / f"agy_stdout_{capture_id}.txt"
    stderr_path = RAW_DUMP_DIR / f"agy_stderr_{capture_id}.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    proc: subprocess.Popen[str] | None = None
    try:
        with (
            prompt_path.open("r", encoding="utf-8") as stdin_fh,
            stdout_path.open("w+", encoding="utf-8") as stdout_fh,
            stderr_path.open("w+", encoding="utf-8") as stderr_fh,
        ):
            proc = subprocess.Popen(
                cmd,
                stdin=stdin_fh,
                stdout=stdout_fh,
                stderr=stderr_fh,
                text=True,
                start_new_session=True,
            )
            try:
                returncode = proc.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired as exc:
                _terminate_gemini_process(proc)
                stdout_fh.flush()
                stderr_fh.flush()
                LOG.error(
                    "gemini CLI timeout > %ds. stdout_path=%s stderr_path=%s stderr_tail=%s",
                    timeout_seconds,
                    stdout_path,
                    stderr_path,
                    _tail_text(stderr_path),
                )
                raise subprocess.TimeoutExpired(
                    cmd=cmd,
                    timeout=timeout_seconds,
                    output=_tail_text(stdout_path, limit=1000),
                    stderr=_tail_text(stderr_path, limit=1000),
                ) from exc
            stdout_fh.flush()
            stderr_fh.flush()

        stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace")
        stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        if proc is not None:
            _terminate_gemini_process(proc)
        raise

    if returncode != 0:
        LOG.error(
            "gemini CLI exited %d. stdout_path=%s stderr_path=%s stderr_tail=%s",
            returncode,
            stdout_path,
            stderr_path,
            stderr_text[-500:],
        )
        raise RuntimeError(
            f"gemini CLI returncode={returncode}: {stderr_text[:300]}",
        )

    prompt_path.unlink(missing_ok=True)
    stdout_path.unlink(missing_ok=True)
    stderr_path.unlink(missing_ok=True)
    return stdout_text


# ---------------------------------------------------------------------------
# JSON extraction (copied from Playwright worker — proven heuristic)
# ---------------------------------------------------------------------------

JSON_FENCE_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


_CHAT_MODE_PREFIXES = (
    "ciao", "salve", "buongiorno", "buonasera",
    "hello", "hi ", "hi,", "hey", "greetings",
    "i have received", "ho ricevuto", "got it",
)


def _looks_like_chat_response(text: str) -> bool:
    """2026-05-23: Gemini in OAuth personal sometimes ignores prompt and chats.
    Detects short conversational replies that lack JSON. Returns True if the
    response is < 600 bytes AND starts with a chat greeting AND has no fence."""
    if len(text) > 600:
        return False
    head = text.lstrip()[:80].lower()
    if not any(head.startswith(p) for p in _CHAT_MODE_PREFIXES):
        return False
    return "```json" not in text and "{" not in text


def extract_json_block(text: str) -> dict[str, Any] | None:
    """Extract ```json fenced block, fallback to largest balanced {...}."""
    if _looks_like_chat_response(text):
        LOG.warning(
            "chat_mode_response detected (len=%d, head=%r) — Gemini ignored prompt",
            len(text), text.lstrip()[:80],
        )
        return None

    m = JSON_FENCE_RE.search(text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError as e:
            LOG.warning("Fenced JSON parse failed: %s", e)

    candidates: list[tuple[int, int]] = []
    depth = 0
    start = -1
    for i, c in enumerate(text):
        if c == "{":
            if depth == 0:
                start = i
            depth += 1
        elif c == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    candidates.append((start, i + 1))
                    start = -1
    candidates.sort(key=lambda p: p[1] - p[0], reverse=True)
    for s, e in candidates[:5]:
        try:
            return json.loads(text[s:e])
        except json.JSONDecodeError:
            continue
    return None


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

async def run_one_client(
    conn,
    drive_service,
    prompt_template: str,
    client_id: int,
    dry_run: bool,
    run_id: str,
    *,
    model: str | None = None,
) -> dict[str, Any]:
    """Process one cliente Phase 1 cross-folder via gemini CLI."""
    started = datetime.now(timezone.utc)
    queue_id: int | None = None

    client = await fetch_client(conn, client_id)
    if not client:
        await queue_mark_terminal(conn, queue_id, "error", last_error="client not found")
        return {"client_id": client_id, "status": "error", "error": "client not found"}
    if not client.get("folder_id"):
        await queue_mark_terminal(conn, queue_id, "skipped", last_error="no folder_id")
        return {"client_id": client_id, "status": "skipped", "error": "no folder_id"}

    folder_id = client["folder_id"]

    try:
        linked_companies = await fetch_linked_companies(conn, client_id)
    except Exception as e:
        LOG.warning("[client=%d] linked companies query failed: %s", client_id, e)
        linked_companies = []

    LOG.info(
        "[client=%d] linked companies: %d (%s)",
        client_id, len(linked_companies),
        ", ".join(c.get("company_name", "?") for c in linked_companies) or "none",
    )

    try:
        flat_files, folder_id_to_name = await aggregate_cross_folder_files(
            drive_service, folder_id, linked_companies,
        )
    except Exception as e:
        await queue_mark_terminal(conn, queue_id, "error",
                                    last_error=f"aggregate cross-folder: {e}")
        return {"client_id": client_id, "status": "error", "error": f"aggregate: {e}"}

    fingerprint = compute_cross_folder_fingerprint(flat_files)
    if client.get("ai_summary_file_hash") == fingerprint:
        await queue_mark_terminal(conn, queue_id, "skipped",
                                    last_error="fingerprint unchanged")
        return {
            "client_id": client_id, "status": "skipped",
            "error": "fingerprint unchanged",
            "linked_companies": len(linked_companies),
            "files_total": len(flat_files),
        }

    queue_id = await queue_mark_running(conn, client_id, run_id)

    LOG.info(
        "[client=%d] files_total=%d cliente_root=%s linked=%d → ocr enrichment",
        client_id, len(flat_files), folder_id, len(linked_companies),
    )

    # Phase 1.5: extract content from priority files (passport/akta/nib/npwp/
    # visa/lkpm/spt) so Gemini reads document substance, not just filenames.
    # Cache hits don't count toward budget; fresh OCR capped at
    # OCR_MAX_FILES_PER_CLIENT to bound latency.
    ocr_results: dict[str, ExtractionResult] = {}
    try:
        ocr_health = await check_health()
        ocr_results = await enrich_files_with_ocr(
            conn, drive_service, flat_files, ocr_health,
        )
    except Exception as e:
        LOG.warning("[client=%d] ocr enrichment failed, falling back metadata-only: %s",
                    client_id, e)

    context_block = build_cross_folder_context_block(
        client_id, folder_id, linked_companies,
        client_full_name=client.get("full_name"),
    )
    inventory_block = build_file_inventory_block(
        flat_files, folder_id_to_name, ocr_results,
    )
    content_block = build_file_content_snippets_block(flat_files, ocr_results)
    full_prompt = assemble_full_prompt(
        prompt_template, context_block, inventory_block, content_block,
    )

    # Save the prompt for audit + debugging on parse failures
    prompt_dump = RAW_DUMP_DIR / f"client_{client_id}_{int(datetime.now().timestamp())}_prompt.txt"
    prompt_dump.write_text(full_prompt, encoding="utf-8")
    LOG.info("[client=%d] prompt saved: %s (%d chars)",
                client_id, prompt_dump, len(full_prompt))

    try:
        response_text = call_gemini_cli(full_prompt, model=model)
    except subprocess.TimeoutExpired:
        await queue_mark_terminal(conn, queue_id, "error",
                                    last_error=f"gemini CLI timeout > {GEMINI_TIMEOUT_SECONDS}s",
                                    raw_response_path=str(prompt_dump))
        return {"client_id": client_id, "status": "error", "error": "gemini timeout"}
    except Exception as e:
        await queue_mark_terminal(conn, queue_id, "error",
                                    last_error=f"gemini CLI: {e}",
                                    raw_response_path=str(prompt_dump))
        return {"client_id": client_id, "status": "error", "error": f"gemini: {e}"}

    response_dump = RAW_DUMP_DIR / f"client_{client_id}_{int(datetime.now().timestamp())}_response.txt"
    response_dump.write_text(response_text, encoding="utf-8")
    LOG.info("[client=%d] response saved: %s (%d chars)",
                client_id, response_dump, len(response_text))

    payload = extract_json_block(response_text)
    if payload is None:
        # 2026-05-23: distinguish chat-mode (short greeting) from genuine parse fail
        is_chat = _looks_like_chat_response(response_text)
        err_msg = "chat_mode_response (Gemini ignored JSON-only instruction)" if is_chat else "no JSON block in response"
        await queue_mark_terminal(conn, queue_id, "error",
                                    last_error=err_msg,
                                    raw_response_path=str(response_dump))
        return {
            "client_id": client_id, "status": "error",
            "error": err_msg, "raw_dump": str(response_dump),
        }

    # Enrich with server-known metadata
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload.setdefault("prompt_version", PROMPT_VERSION_V3)
    payload["client_id"] = client_id
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    payload["source_folder_id"] = folder_id
    payload["source_file_count"] = len(flat_files)
    payload["source_file_fingerprint"] = fingerprint

    if "company" not in payload or not isinstance(payload.get("company"), dict):
        payload["company"] = {}
    payload["company"]["source_company_folders"] = [
        c["google_drive_folder_id"] for c in linked_companies
    ]

    try:
        summary = L1ClientSummary.model_validate(payload)
    except Exception as e:
        await queue_mark_terminal(conn, queue_id, "error",
                                    last_error=f"pydantic validation: {e}",
                                    raw_response_path=str(response_dump))
        return {
            "client_id": client_id, "status": "error",
            "error": f"pydantic validation: {e}", "raw_dump": str(response_dump),
        }

    duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)

    if not dry_run:
        await conn.execute(
            """
            UPDATE clients
            SET ai_summary = $1::jsonb,
                ai_summary_generated_at = NOW(),
                ai_summary_file_hash = $2,
                ai_summary_schema_version = $3
            WHERE id = $4
            """,
            summary.model_dump_json(), fingerprint, SCHEMA_VERSION, client_id,
        )
        await conn.execute(
            """
            INSERT INTO crm_guardian_events
            (invariant_id, action, target_type, target_id, client_id,
             after_state, status, dry_run, run_id, notes)
            VALUES ('I10_summary_l1', 'generate_summary', 'client', $1, $2,
                    $3::jsonb, 'success', false, $4::uuid, $5)
            """,
            str(client_id), client_id, summary.model_dump_json(), run_id,
            f"gemini_cli fp={fingerprint[:12]} linked={len(linked_companies)} files={len(flat_files)}",
        )
        await queue_mark_terminal(conn, queue_id, "success",
                                    duration_ms=duration_ms,
                                    raw_response_path=str(response_dump))
    else:
        await conn.execute(
            """
            INSERT INTO crm_guardian_events
            (invariant_id, action, target_type, target_id, client_id,
             after_state, status, dry_run, run_id, notes)
            VALUES ('I10_summary_l1', 'generate_summary', 'client', $1, $2,
                    $3::jsonb, 'dry_run', true, $4::uuid, $5)
            """,
            str(client_id), client_id, summary.model_dump_json(), run_id,
            f"DRY_RUN_CLI fp={fingerprint[:12]} linked={len(linked_companies)} files={len(flat_files)}",
        )
        await queue_mark_terminal(conn, queue_id, "skipped",
                                    last_error="dry_run mode (audit-only)",
                                    duration_ms=duration_ms,
                                    raw_response_path=str(response_dump))

    return {
        "client_id": client_id,
        "status": "success" if not dry_run else "dry_run",
        "archetype": summary.profile.archetype,
        "tier": summary.profile.tier,
        "confidence": summary.extraction_confidence,
        "fingerprint": fingerprint[:12],
        "linked_companies": len(linked_companies),
        "files_total": len(flat_files),
        "duration_ms": duration_ms,
        "raw_dump": str(response_dump),
    }


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-id", type=int)
    ap.add_argument("--from-queue", action="store_true")
    ap.add_argument("--max", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true", default=False)
    ap.add_argument("--prompt-file", type=Path, default=DEFAULT_PROMPT_FILE)
    ap.add_argument(
        "--model", type=str, default=GEMINI_DEFAULT_MODEL,
        help="Override gemini CLI -m flag (default: CLI default, free OAuth = Gemini 2.5 Pro)",
    )
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    if not args.client_id and not args.from_queue:
        ap.error("specify --client-id N or --from-queue")

    prompt_template = args.prompt_file.read_text()

    import asyncpg

    from backend.services.crm_guardian.base import (
        build_drive_service,
        bump_circuit_breaker,
    )

    db_url = _resolve_db_url()
    conn = await asyncpg.connect(db_url)

    if args.client_id:
        targets = [args.client_id]
    else:
        stale_reset_count = await reset_stale_running_jobs(conn)
        if stale_reset_count:
            LOG.warning("Reset %d stale running CRM Guardian queue row(s)", stale_reset_count)
        rows = await conn.fetch(
            """
            SELECT client_id FROM crm_guardian_summary_queue
            WHERE status = 'pending'
            ORDER BY priority ASC, enqueued_at ASC
            LIMIT $1
            """, args.max,
        )
        targets = [r["client_id"] for r in rows]
        if not targets:
            LOG.info("No pending clients in queue.")
            await bump_circuit_breaker(conn, "I10b_summary_queue", True)
            await conn.close()
            return 0

    LOG.info("Targets: %s dry_run=%s model=%s",
                targets, args.dry_run, args.model or "default")

    try:
        drive_service = build_drive_service(prefer_user_oauth=True)
    except Exception as e:
        await bump_circuit_breaker(
            conn,
            "I10b_summary_queue",
            False,
            f"build_drive_service: {e}",
        )
        await conn.close()
        raise

    run_id = str(uuid.uuid4())
    results: list[dict[str, Any]] = []

    for cid in targets:
        try:
            r = await run_one_client(
                conn, drive_service, prompt_template,
                cid, args.dry_run, run_id, model=args.model,
            )
        except Exception as e:
            LOG.exception("client %d crashed", cid)
            r = {"client_id": cid, "status": "error", "error": str(e)}
        results.append(r)
        LOG.info("Result: %s", r)

    succeeded = all(
        r.get("status") in ("success", "dry_run", "skipped") for r in results
    )
    first_error = next(
        (str(r.get("error")) for r in results if r.get("status") == "error"),
        None,
    )
    await bump_circuit_breaker(
        conn,
        "I10b_summary_queue",
        succeeded,
        first_error,
    )
    await bump_circuit_breaker(
        conn,
        "I10_summary_l1",
        succeeded,
        first_error,
    )
    await conn.close()
    sys.stdout.write(json.dumps({"run_id": run_id, "results": results}, indent=2, default=str))
    sys.stdout.write("\n")
    return 0 if succeeded else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
