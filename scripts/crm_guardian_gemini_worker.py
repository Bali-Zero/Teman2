#!/usr/bin/env python3
"""CRM-Guardian Gemini Worker (gemini.google.com variant).

Drives a real Chrome profile (~/.chrome-cdp-profile/Profile 1 =
antonellosiano@gmail.com with Gemini Ultra) against gemini.google.com
to extract L1 client summaries. Uses the dedicated Gemini web app
(more stable than Drive Panel Side).

Flow per client:
 1. Compute file fingerprint (skip if unchanged)
 2. Navigate to gemini.google.com (new chat)
 3. Type prompt with "@<folder_name>" to attach the client's Drive folder
 4. Wait for response completion (textContent stability)
 5. Extract JSON fenced block
 6. Validate via Pydantic L1ClientSummary
 7. Write to clients.ai_summary + crm_guardian_events

Usage:
    python scripts/crm_guardian_gemini_worker.py --client-id 484 --dry-run
    python scripts/crm_guardian_gemini_worker.py --from-queue --max 3
    python scripts/crm_guardian_gemini_worker.py --client-id 484 --no-headful
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_RAG = REPO_ROOT / "apps" / "backend-rag"
sys.path.insert(0, str(BACKEND_RAG))

from backend.services.crm_guardian.schemas import L1ClientSummary, SCHEMA_VERSION  # noqa: E402

LOG = logging.getLogger("crm_guardian.worker")

CHROME_PROFILE_DIR = Path.home() / ".chrome-cdp-profile"
CHROME_PROFILE_NAME = "Profile 1"  # antonellosiano@gmail.com / Gemini Ultra
DEFAULT_PROMPT_FILE = BACKEND_RAG / "backend/services/crm_guardian/prompts/L1_extraction_v1.md"

RAW_DUMP_DIR = Path.home() / ".crm_guardian" / "raw_dumps"
RAW_DUMP_DIR.mkdir(parents=True, exist_ok=True)

GEMINI_APP_URL = "https://gemini.google.com/app"

RESPONSE_STABLE_SECONDS = 4
RESPONSE_POLL_INTERVAL = 0.8
RESPONSE_MAX_WAIT_SECONDS = 240


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _resolve_db_url() -> str:
    """Resolve local flyctl-proxy DATABASE_URL (port 15432)."""
    secrets = Path.home() / ".nuzantara-secrets.env"
    if not secrets.exists():
        raise RuntimeError(f"Secrets file not found: {secrets}")
    for line in secrets.read_text().splitlines():
        if line.startswith("DATABASE_URL="):
            url = line.split("=", 1)[1].strip().strip('"')
            return re.sub(r"@[^:/]+(\.internal)?:\d+", "@localhost:15432", url)
    raise RuntimeError("DATABASE_URL not found in secrets")


async def fetch_client(conn, client_id: int) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        """
        SELECT id, name, surname, email, folder_id, folder_link,
               ai_summary_file_hash, ai_summary_generated_at
        FROM clients WHERE id = $1
        """,
        client_id,
    )
    return dict(row) if row else None


async def list_drive_files(drive_service, folder_id: str) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    page_token: str | None = None
    while True:
        resp = drive_service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id, name, mimeType, modifiedTime, size)",
            pageSize=200,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        files.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return files


def compute_fingerprint(files: list[dict[str, Any]]) -> str:
    pairs = sorted((f["id"], f.get("modifiedTime", "")) for f in files)
    blob = json.dumps(pairs, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


async def resolve_folder_name(drive_service, folder_id: str) -> str | None:
    try:
        meta = drive_service.files().get(
            fileId=folder_id, fields="name", supportsAllDrives=True,
        ).execute()
        return meta.get("name")
    except Exception as e:
        LOG.warning("resolve_folder_name failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Playwright Gemini app driver
# ---------------------------------------------------------------------------

async def start_new_chat(page) -> None:
    """Start a fresh conversation in gemini.google.com."""
    await page.goto(GEMINI_APP_URL, wait_until="domcontentloaded", timeout=30_000)
    await asyncio.sleep(2)

    # Click "New chat" if already inside a conversation (otherwise already fresh)
    for sel in [
        'button[aria-label="New chat" i]',
        'button[data-test-id="new-chat-button"]',
        'a[href="/app"]',
    ]:
        try:
            btn = await page.query_selector(sel)
            if btn:
                await btn.click()
                await asyncio.sleep(1)
                break
        except Exception:
            continue


async def find_prompt_input(page):
    """Locate Gemini chat textarea/contenteditable."""
    selectors = [
        'rich-textarea [contenteditable="true"]',
        'div[contenteditable="true"][role="textbox"]',
        'textarea[aria-label*="prompt" i]',
        'textarea[aria-label*="Gemini" i]',
        'div.ql-editor[contenteditable="true"]',
    ]
    for sel in selectors:
        try:
            inp = await page.wait_for_selector(sel, timeout=8000, state="visible")
            if inp:
                LOG.info("Gemini input located: %s", sel)
                return inp, sel
        except Exception:
            continue
    return None, None


async def attach_folder_via_at_mention(page, folder_name: str) -> bool:
    """Type @folder_name and pick the matching Drive folder from suggestions."""
    inp, sel = await find_prompt_input(page)
    if not inp:
        LOG.error("Cannot find Gemini input for @ mention")
        return False

    await inp.click()
    await page.keyboard.press("Meta+A")
    await page.keyboard.press("Delete")
    await page.keyboard.type("@", delay=50)
    await asyncio.sleep(0.6)
    await page.keyboard.type(folder_name, delay=30)
    await asyncio.sleep(1.5)  # wait for suggestion popup

    # Pick first suggestion matching "Drive" / folder type
    # Gemini's @ picker dropdown is a listbox of options
    suggestion_selectors = [
        f'[role="option"]:has-text("{folder_name[:30]}")',
        '[role="listbox"] [role="option"]:first-child',
        '[data-source="drive"]',
        'mat-option',
    ]
    picked = False
    for s_sel in suggestion_selectors:
        try:
            opt = await page.wait_for_selector(s_sel, timeout=3000, state="visible")
            if opt:
                await opt.click()
                picked = True
                LOG.info("Folder suggestion picked via %s", s_sel)
                break
        except Exception:
            continue

    if not picked:
        # Fallback: press Enter to pick first suggestion
        await page.keyboard.press("Enter")
        await asyncio.sleep(0.5)
        LOG.warning("No suggestion matched; pressed Enter as fallback")

    return True


async def submit_prompt_body(page, prompt_body: str) -> bool:
    """After @folder is attached, append the actual prompt and send."""
    inp, sel = await find_prompt_input(page)
    if not inp:
        return False
    await inp.click()
    # Move cursor to end and add a newline + prompt body
    await page.keyboard.press("End")
    await page.keyboard.type("\n\n", delay=30)

    # Type prompt body (long) — faster via clipboard-paste pattern via eval
    if sel and "textarea" in sel:
        cur = await inp.input_value()
        await inp.fill((cur + "\n\n" + prompt_body).strip())
    else:
        await page.evaluate(
            """([el, txt]) => {
                el.focus();
                document.execCommand('insertText', false, txt);
            }""",
            [inp, prompt_body],
        )

    # Send button
    send_selectors = [
        'button[aria-label*="Send" i]:not([disabled])',
        'button[aria-label*="Invia" i]:not([disabled])',
        'button[data-test-id="send-button"]:not([disabled])',
    ]
    sent = False
    for ss in send_selectors:
        try:
            btn = await page.query_selector(ss)
            if btn and await btn.is_enabled():
                await btn.click()
                sent = True
                LOG.info("Send clicked: %s", ss)
                break
        except Exception:
            continue
    if not sent:
        # Fallback: ctrl/cmd+enter
        await page.keyboard.press("Meta+Enter")
        LOG.info("Fallback Meta+Enter to send")
    return True


async def wait_for_response(page) -> str:
    """Stability-poll response pane textContent."""
    start = asyncio.get_event_loop().time()
    last_len = -1
    stable_since = None

    while True:
        elapsed = asyncio.get_event_loop().time() - start
        if elapsed > RESPONSE_MAX_WAIT_SECONDS:
            LOG.warning("Response timeout after %.1fs", elapsed)
            break

        cur_text = await page.evaluate(
            """() => {
                // Response area in gemini.google.com is marked model-response-text
                // or similar custom elements. Fall back to message-content.
                const containers = document.querySelectorAll(
                    'model-response-text, message-content, [data-response-index], .model-response, .response-container'
                );
                let last = containers[containers.length - 1];
                if (!last) {
                    // broader scope
                    const mains = document.querySelectorAll('main, [role="main"]');
                    last = mains[mains.length - 1] || document.body;
                }
                // Force virtualization: scroll last to bottom
                try {
                    if (last.scrollHeight > last.clientHeight) {
                        last.scrollTop = last.scrollHeight;
                    }
                } catch (_) {}
                return last.innerText || '';
            }"""
        )
        cur_len = len(cur_text or "")
        now = asyncio.get_event_loop().time()

        if cur_len == last_len and cur_len > 0:
            if stable_since is None:
                stable_since = now
            elif now - stable_since >= RESPONSE_STABLE_SECONDS:
                LOG.info("Response stable at %d chars after %.1fs", cur_len, elapsed)
                return cur_text
        else:
            stable_since = None
        last_len = cur_len
        await asyncio.sleep(RESPONSE_POLL_INTERVAL)

    final = await page.evaluate("() => document.body.innerText")
    return final or ""


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

JSON_FENCE_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def extract_json_block(text: str) -> dict[str, Any] | None:
    m = JSON_FENCE_RE.search(text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError as e:
            LOG.warning("Fenced JSON parse failed: %s", e)

    # Fallback: largest balanced {…} that parses
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
    page,
    prompt_template: str,
    client_id: int,
    dry_run: bool,
    run_id: str,
) -> dict[str, Any]:
    client = await fetch_client(conn, client_id)
    if not client:
        return {"client_id": client_id, "status": "error", "error": "client not found"}
    if not client.get("folder_id"):
        return {"client_id": client_id, "status": "skipped", "error": "no folder_id"}

    folder_id = client["folder_id"]

    try:
        files = await list_drive_files(drive_service, folder_id)
    except Exception as e:
        return {"client_id": client_id, "status": "error", "error": f"list files: {e}"}
    fingerprint = compute_fingerprint(files)
    if client.get("ai_summary_file_hash") == fingerprint:
        return {"client_id": client_id, "status": "skipped", "error": "fingerprint unchanged"}

    folder_name = await resolve_folder_name(drive_service, folder_id)
    if not folder_name:
        return {"client_id": client_id, "status": "error", "error": "folder_name not resolved"}
    LOG.info("[client=%d] folder_name=%r  files=%d", client_id, folder_name, len(files))

    # 1. Start fresh chat
    await start_new_chat(page)

    # 2. @mention the folder
    if not await attach_folder_via_at_mention(page, folder_name):
        return {"client_id": client_id, "status": "error", "error": "at-mention failed"}

    # 3. Paste prompt body + send
    if not await submit_prompt_body(page, prompt_template):
        return {"client_id": client_id, "status": "error", "error": "submit failed"}

    # 4. Wait + capture
    response_text = await wait_for_response(page)

    # 5. Save raw dump
    dump_path = RAW_DUMP_DIR / f"client_{client_id}_{int(datetime.now().timestamp())}.txt"
    dump_path.write_text(response_text, encoding="utf-8")
    LOG.info("[client=%d] dump saved: %s (%d chars)", client_id, dump_path, len(response_text))

    # 6. Extract JSON
    payload = extract_json_block(response_text)
    if payload is None:
        return {
            "client_id": client_id, "status": "error",
            "error": "no JSON block", "raw_dump": str(dump_path),
        }

    # 7. Enrich with server-known metadata
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload["client_id"] = client_id
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    payload["source_folder_id"] = folder_id
    payload["source_file_count"] = len(files)
    payload["source_file_fingerprint"] = fingerprint

    # 8. Pydantic validate
    try:
        summary = L1ClientSummary.model_validate(payload)
    except Exception as e:
        return {
            "client_id": client_id, "status": "error",
            "error": f"pydantic validation: {e}", "raw_dump": str(dump_path),
        }

    # 9. Write DB
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
            str(client_id), client_id, summary.model_dump_json(),
            run_id, f"gemini_webapp fp={fingerprint[:12]}",
        )

    return {
        "client_id": client_id,
        "status": "success" if not dry_run else "dry_run",
        "archetype": summary.profile.archetype,
        "tier": summary.profile.tier,
        "confidence": summary.extraction_confidence,
        "fingerprint": fingerprint[:12],
        "raw_dump": str(dump_path),
    }


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-id", type=int)
    ap.add_argument("--from-queue", action="store_true")
    ap.add_argument("--max", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true", default=False)
    ap.add_argument("--headful", action="store_true", default=True)
    ap.add_argument("--no-headful", dest="headful", action="store_false")
    ap.add_argument("--prompt-file", type=Path, default=DEFAULT_PROMPT_FILE)
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    if not args.client_id and not args.from_queue:
        ap.error("specify --client-id N or --from-queue")

    prompt_template = args.prompt_file.read_text()

    import asyncpg
    from playwright.async_api import async_playwright
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

    LOG.info("Targets: %s  dry_run=%s", targets, args.dry_run)

    drive_service = build_drive_service(prefer_user_oauth=True)
    run_id = str(uuid.uuid4())
    results: list[dict[str, Any]] = []

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(CHROME_PROFILE_DIR),
            headless=not args.headful,
            args=[
                f"--profile-directory={CHROME_PROFILE_NAME}",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            viewport={"width": 1400, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        for cid in targets:
            try:
                r = await run_one_client(
                    conn, drive_service, page, prompt_template,
                    cid, args.dry_run, run_id,
                )
            except Exception as e:
                LOG.exception("client %d crashed", cid)
                r = {"client_id": cid, "status": "error", "error": str(e)}
            results.append(r)
            LOG.info("Result: %s", r)

        await ctx.close()

    await conn.close()
    print(json.dumps({"run_id": run_id, "results": results}, indent=2, default=str))
    return 0 if all(
        r.get("status") in ("success", "dry_run", "skipped") for r in results
    ) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
