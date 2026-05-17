#!/usr/bin/env python3
"""CRM-Guardian Gemini CLI Worker (gemini --print variant).

Replacement driver for the Playwright Gemini Web App worker
(scripts/crm_guardian_gemini_worker.py), which is blocked by Google's
anti-automation policy on Chrome-for-Testing (verified 2026-05-17 with
"Impossibile eseguire l'accesso" → invalid_grant on gemini.google.com).

Architecture:
  - Use `gemini` CLI (v0.41.2, /opt/homebrew/bin/gemini) via subprocess
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
import json
import logging
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_RAG = REPO_ROOT / "apps" / "backend-rag"
sys.path.insert(0, str(BACKEND_RAG))

from backend.services.crm_guardian.schemas import (  # noqa: E402
    L1ClientSummary,
    SCHEMA_VERSION,
)

LOG = logging.getLogger("crm_guardian.cli_worker")

DEFAULT_PROMPT_FILE = BACKEND_RAG / "backend/services/crm_guardian/prompts/L1_extraction_v2.md"
PROMPT_VERSION_V2 = "L1_extraction_v2"

RAW_DUMP_DIR = Path.home() / ".crm_guardian" / "raw_dumps_cli"
RAW_DUMP_DIR.mkdir(parents=True, exist_ok=True)

GEMINI_CLI = "/opt/homebrew/bin/gemini"
GEMINI_TIMEOUT_SECONDS = 240  # match Web App worker
GEMINI_DEFAULT_MODEL: str | None = None  # let CLI pick its default (Gemini 2.5 Pro free OAuth)


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
    """Active company links for this client with their Drive folder ID."""
    rows = await conn.fetch(
        """
        SELECT
            ccl.company_id,
            ccl.role,
            ccl.is_primary,
            c.company_name,
            c.google_drive_folder_id
        FROM client_company_links ccl
        JOIN companies c ON c.id = ccl.company_id
        WHERE ccl.client_id = $1
          AND ccl.status = 'active'
          AND c.google_drive_folder_id IS NOT NULL
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
        if not cf_id:
            continue
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
            continue

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
# Prompt assembly (no Drive @mention — inline metadata table)
# ---------------------------------------------------------------------------

def build_cross_folder_context_block(
    client_id: int,
    client_root_folder: str,
    linked_companies: list[dict[str, Any]],
) -> str:
    """Render <CROSS_FOLDER_CONTEXT> block per L1_extraction_v2 spec."""
    lines = [
        "<CROSS_FOLDER_CONTEXT>",
        f"client_id: {client_id}",
        f"client_root_folder: {client_root_folder}",
    ]
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
) -> str:
    """Render <FILE_INVENTORY> block exposing file metadata to Gemini.

    Since `gemini` CLI cannot @mention Drive folders, we list every file's
    (id, name, mimeType, size, modifiedTime, source_folder_name) so the LLM
    can reason about identity/visa/company structure from filenames + types.
    OCR'd text content is NOT inlined here (would explode prompt size for
    50+ docs); that path remains the existing crm-drive OCR pipeline which
    writes to client_documents table independently.
    """
    lines = ["<FILE_INVENTORY>"]
    lines.append(
        "# Format: source_folder | file_id | name | mimeType | size_bytes | modifiedTime"
    )
    for f in flat_files:
        src = folder_id_to_name.get(f.get("source_folder_id", ""), "?")
        size = f.get("size", "")
        lines.append(
            f"{src} | {f['id']} | {f.get('name', '?')} | "
            f"{f.get('mimeType', '?')} | {size} | {f.get('modifiedTime', '?')}"
        )
    lines.append(f"# Total files: {len(flat_files)}")
    lines.append("</FILE_INVENTORY>")
    return "\n".join(lines)


def assemble_full_prompt(
    prompt_template: str,
    context_block: str,
    inventory_block: str,
) -> str:
    """Assemble the final prompt: template + context + inventory."""
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

    The prompt is passed via `-p` arg, NOT stdin, because the CLI uses
    `--prompt` as the primary non-interactive trigger. Long prompts (50+
    files) tested up to ~120KB without issue.
    """
    if not shutil.which("gemini"):
        raise RuntimeError(
            f"gemini CLI not found at expected path {GEMINI_CLI}. "
            "Install via: npm install -g @google/gemini-cli"
        )

    cmd = [GEMINI_CLI, "-p", prompt]
    if model:
        cmd.extend(["-m", model])

    LOG.info(
        "Calling gemini CLI (model=%s prompt_len=%d timeout=%ds)",
        model or "default", len(prompt), timeout_seconds,
    )
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    if proc.returncode != 0:
        LOG.error(
            "gemini CLI exited %d. stderr (last 500): %s",
            proc.returncode, proc.stderr[-500:],
        )
        raise RuntimeError(
            f"gemini CLI returncode={proc.returncode}: {proc.stderr[:300]}",
        )
    return proc.stdout


# ---------------------------------------------------------------------------
# JSON extraction (copied from Playwright worker — proven heuristic)
# ---------------------------------------------------------------------------

JSON_FENCE_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def extract_json_block(text: str) -> dict[str, Any] | None:
    """Extract ```json fenced block, fallback to largest balanced {...}."""
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
        "[client=%d] files_total=%d cliente_root=%s linked=%d → calling gemini CLI",
        client_id, len(flat_files), folder_id, len(linked_companies),
    )

    context_block = build_cross_folder_context_block(
        client_id, folder_id, linked_companies,
    )
    inventory_block = build_file_inventory_block(flat_files, folder_id_to_name)
    full_prompt = assemble_full_prompt(prompt_template, context_block, inventory_block)

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
        await queue_mark_terminal(conn, queue_id, "error",
                                    last_error="no JSON block in response",
                                    raw_response_path=str(response_dump))
        return {
            "client_id": client_id, "status": "error",
            "error": "no JSON block", "raw_dump": str(response_dump),
        }

    # Enrich with server-known metadata
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload.setdefault("prompt_version", PROMPT_VERSION_V2)
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
    from backend.services.crm_guardian.base import build_drive_service

    db_url = _resolve_db_url()
    conn = await asyncpg.connect(db_url)

    if args.client_id:
        targets = [args.client_id]
    else:
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
            await conn.close()
            return 0

    LOG.info("Targets: %s dry_run=%s model=%s",
                targets, args.dry_run, args.model or "default")

    drive_service = build_drive_service(prefer_user_oauth=True)
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

    await conn.close()
    print(json.dumps({"run_id": run_id, "results": results}, indent=2, default=str))
    return 0 if all(
        r.get("status") in ("success", "dry_run", "skipped") for r in results
    ) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
