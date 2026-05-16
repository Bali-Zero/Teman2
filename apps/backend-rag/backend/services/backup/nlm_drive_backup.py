"""Daily NLM → Drive backup — Week 0 Phase D foundation.

Iterates every NotebookLM notebook accessible to the active session,
exports per-NB metadata + per-source content as a single JSON artifact,
uploads it under ``/nuzantara-nb-backup-daily/YYYY-MM-DD/<nb_id>.json``
on antonellosiano@gmail.com's 30 TB Drive.

Trigger
-------
LaunchAgent ``com.nuzantara.nlm-drive-backup.daily`` fires at 03:00 WITA
(macOS-local time). The plist sits at
``~/Library/LaunchAgents/com.nuzantara.nlm-drive-backup.daily.plist``
and is owned by the operator (Pro machine — Mini-Pro2 keeps the backup
binary in sync via the standard rsync daemons but does NOT run the cron
to avoid double-writes).

NLM access path (Week 0 only)
-----------------------------
Phase 0 of the script uses the **existing** ``nlm`` Node.js CLI via
``subprocess`` (``nlm`` is already installed and authenticated under
``~/.notebooklm-mcp-cli/``). This is the canonical path *until* Phase 1.5
spike concludes and migrates 25 callsites to ``notebooklm-py``. By using
the same CLI the rest of the codebase uses today, this backup script is
unaffected by the eventual swap — the CLI keeps working in parallel.

Drive access path
-----------------
OAuth user credentials live in ``~/.nuzantara/drive_backup_oauth.json``
(written by ``drive_folder_setup.py``, chmod 0400). Same minted access
token is reused for all uploads in a run.

Idempotency
-----------
- Day folder ``YYYY-MM-DD/`` is created idempotently (existing folder
  re-used on re-runs).
- Per-NB JSON is overwritten on re-run (last-write-wins) — daily backup
  cadence makes this safe; if the operator wants point-in-time history
  they re-run with ``--target-folder /nuzantara-nb-backup-daily-rerun-…``.

Logs
----
``~/logs/nlm-drive-backup/YYYY-MM-DD.log`` — one log per run. Stdout +
stderr also captured by LaunchAgent stdout/stderr keys.

Constraints (hard rules)
------------------------
- NO paid Anthropic API. NO new paid subscriptions.
- Token file must be chmod 0400 — script aborts if owner write or world
  read is set.
- Folder name validation: ``^[A-Za-z0-9_-]{1,128}$`` (path traversal
  defense).
- All HTTP through ``urllib`` stdlib — no httpx/google-auth runtime
  dependency. Keeps the script standalone for cron.

Usage
-----
.. code-block:: bash

    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. python -m backend.services.backup.nlm_drive_backup --apply

    # Dry-run (no Drive writes, just inventory):
    PYTHONPATH=. python -m backend.services.backup.nlm_drive_backup
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger("backend.services.backup.nlm_drive_backup")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

# --- constants -------------------------------------------------------------

TOKEN_PATH = Path(os.path.expanduser("~/.nuzantara/drive_backup_oauth.json"))
LOG_DIR = Path(os.path.expanduser("~/logs/nlm-drive-backup"))

DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
DRIVE_UPLOAD_BASE = "https://www.googleapis.com/upload/drive/v3"
TOKEN_URL = "https://oauth2.googleapis.com/token"

# Top-level Drive folder for daily backups.
# ID hard-coded after one-shot setup via ``drive_folder_setup.py --apply``;
# trace in ``WEEK0_PHASE_D_DRIVE_SETUP.md``.
BACKUP_ROOT_FOLDER_ID = "1wlVhMGVxd_H28vHeX3FsMaM7PBvEDlAX"

NLM_CLI = "nlm"  # resolved via PATH; assumes existing Node CLI installed
NLM_CLI_TIMEOUT_S = 60  # per subprocess call

# Folder name regex (matches drive_folder_setup.py for symmetry).
FOLDER_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

# UUID regex for NB ID validation (path-traversal defense).
NB_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
# Source IDs from NLM are also UUIDs but tolerate slightly looser format.
SOURCE_ID_RE = re.compile(r"^[0-9a-fA-F][0-9a-fA-F-]{7,63}$")
# Drive folder/file IDs follow Google's URL-safe base64 alphabet.
DRIVE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{10,128}$")

# Account verification — backups MUST land on antonellosiano@gmail.com.
EXPECTED_USER_EMAIL = "antonellosiano@gmail.com"

# Hard cap on notebook count to prevent unbounded loops if NLM CLI returns
# a corrupted / cyclic list. Today's NB count is ~63; 200 gives 3× headroom.
MAX_NOTEBOOKS_HARD_CAP = 200

# Rate limiting
PER_NB_SLEEP_S = 2.0  # gentle pacing between notebooks
PER_SOURCE_SLEEP_S = 0.3  # pacing between sources within an NB


class BackupError(RuntimeError):
    """Raised when backup cannot proceed (missing token, NLM CLI failure, Drive failure)."""


# --- token management ------------------------------------------------------


def _load_oauth_credentials() -> dict[str, str]:
    """Load OAuth credentials from TOKEN_PATH. Enforce chmod 0400."""
    if not TOKEN_PATH.exists():
        raise BackupError(
            f"OAuth token store missing: {TOKEN_PATH}. "
            "Run drive_folder_setup.py to bootstrap.",
        )
    mode = stat.S_IMODE(TOKEN_PATH.stat().st_mode)
    if mode != 0o400:
        logger.warning("Fixing TOKEN_PATH %s mode 0%o → 0400", TOKEN_PATH, mode)
        TOKEN_PATH.chmod(0o400)
    try:
        return json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BackupError(f"Cannot read token store {TOKEN_PATH}: {exc}") from exc


def _mint_access_token(creds: dict[str, str]) -> str:
    """Exchange refresh token for short-lived access token."""
    data = urllib.parse.urlencode({
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "refresh_token": creds["refresh_token"],
        "grant_type": "refresh_token",
    }).encode("utf-8")
    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise BackupError(f"Token mint failed: HTTP {exc.code} — {body[:200]}") from exc
    if "access_token" not in payload:
        raise BackupError(f"Token mint missing access_token in response: {payload}")
    return payload["access_token"]


# --- Drive helpers ---------------------------------------------------------


def _retry(fn: Any, *, attempts: int = 4, base: float = 1.0, label: str = "drive") -> Any:
    """Retry helper for transient HTTP errors on Drive calls.

    Retries on 429 / 5xx / URLError up to ``attempts`` times. Honors
    ``Retry-After`` header on 429 if present; otherwise exponential
    backoff (base × 2**attempt). Last attempt re-raises the original
    exception.
    """
    last_exc: BaseException | None = None
    for i in range(attempts):
        try:
            return fn()
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code in (429, 500, 502, 503, 504) and i < attempts - 1:
                retry_after = int(exc.headers.get("Retry-After", "0") or 0) if exc.headers else 0
                delay = max(retry_after, base * (2 ** i))
                logger.warning("%s HTTP %d on attempt %d/%d — sleeping %.1fs",
                               label, exc.code, i + 1, attempts, delay)
                time.sleep(delay)
                continue
            raise
        except urllib.error.URLError as exc:
            last_exc = exc
            if i < attempts - 1:
                delay = base * (2 ** i)
                logger.warning("%s URLError on attempt %d/%d (%s) — sleeping %.1fs",
                               label, i + 1, attempts, exc, delay)
                time.sleep(delay)
                continue
            raise
    if last_exc is not None:
        raise last_exc
    raise BackupError(f"{label}: retry exhausted with no captured exception")


def _verify_account(token: str) -> dict[str, Any]:
    """Confirm the access token belongs to ``EXPECTED_USER_EMAIL``.

    Raises BackupError if the account does not match. Run this immediately
    after minting the access token, before any uploads, so we never write
    backup data to the wrong Drive (e.g. if a token rotation accidentally
    swaps to a Service Account or another user).
    """
    about = _drive_get(token, "/about", {"fields": "user,storageQuota"})
    user = about.get("user", {})
    email = user.get("emailAddress")
    if email != EXPECTED_USER_EMAIL:
        raise BackupError(
            f"Drive token belongs to {email!r}, expected "
            f"{EXPECTED_USER_EMAIL!r}. Refusing to write backups to wrong account.",
        )
    return about


def _verify_root_folder(token: str, folder_id: str) -> None:
    """Confirm BACKUP_ROOT_FOLDER_ID still exists and is not trashed.

    Drive's ``q`` searches return 0 matches when the parent doesn't exist
    rather than 404, which would silently let us create a day folder at
    Drive root if BACKUP_ROOT_FOLDER_ID was deleted. Catch that here.
    """
    if not DRIVE_ID_RE.match(folder_id):
        raise BackupError(f"BACKUP_ROOT_FOLDER_ID {folder_id!r} fails format validation")
    try:
        meta = _drive_get(token, f"/files/{folder_id}", {"fields": "id,name,trashed,mimeType"})
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise BackupError(
                f"BACKUP_ROOT_FOLDER_ID {folder_id} returns 404 — folder "
                "missing or unreachable. Re-run drive_folder_setup.py to recreate.",
            ) from exc
        raise
    if meta.get("trashed"):
        raise BackupError(
            f"BACKUP_ROOT_FOLDER_ID {folder_id} is trashed. Restore it or "
            "re-run drive_folder_setup.py.",
        )
    if meta.get("mimeType") != "application/vnd.google-apps.folder":
        raise BackupError(
            f"BACKUP_ROOT_FOLDER_ID {folder_id} is not a folder "
            f"(mime={meta.get('mimeType')!r}).",
        )


def _drive_get(token: str, path: str, query: dict[str, str] | None = None) -> dict[str, Any]:
    qs = "?" + urllib.parse.urlencode(query) if query else ""

    def _do() -> dict[str, Any]:
        req = urllib.request.Request(
            f"{DRIVE_API_BASE}{path}{qs}",
            headers={"Authorization": f"Bearer {token}"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    return _retry(_do, label=f"drive_get {path}")


def _drive_post_json(token: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")

    def _do() -> dict[str, Any]:
        req = urllib.request.Request(
            f"{DRIVE_API_BASE}{path}",
            data=data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    return _retry(_do, label=f"drive_post {path}")


def _drive_find_or_create_folder(
    token: str, parent_id: str, name: str
) -> str:
    """Return folder ID for ``name`` under ``parent_id``; create if missing."""
    if not FOLDER_NAME_RE.match(name):
        raise BackupError(f"Invalid folder name {name!r}")
    if not DRIVE_ID_RE.match(parent_id):
        raise BackupError(f"Invalid parent_id {parent_id!r} — fails Drive ID format")
    # Search existing
    q = (
        f"name = '{name}' and "
        f"'{parent_id}' in parents and "
        "mimeType = 'application/vnd.google-apps.folder' and "
        "trashed = false"
    )
    res = _drive_get(token, "/files", {"q": q, "fields": "files(id,name)"})
    files = res.get("files", [])
    if files:
        return files[0]["id"]
    # Create
    body = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    created = _drive_post_json(token, "/files", body)
    return created["id"]


def _drive_upload_json(
    token: str, parent_id: str, filename: str, payload: dict[str, Any]
) -> str:
    """Multipart upload a JSON document; replace if same name already exists.

    Returns the file ID.
    """
    # Validate filename and parent_id (defense-in-depth — used in `q=` query).
    if not DRIVE_ID_RE.match(parent_id):
        raise BackupError(f"Invalid parent_id {parent_id!r}")
    # filename is built from validated nb_id + ".json", so safe by construction
    # but escape single quotes in the q filter for symmetry with drive_folder_setup.py.
    escaped_name = filename.replace("\\", "\\\\").replace("'", "\\'")
    q = f"name = '{escaped_name}' and '{parent_id}' in parents and trashed = false"
    res = _drive_get(token, "/files", {"q": q, "fields": "files(id,name)"})
    existing = res.get("files", [])
    body_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

    if existing:
        # Update content of the existing file (PATCH /upload)
        file_id = existing[0]["id"]

        def _patch() -> dict[str, Any]:
            req = urllib.request.Request(
                f"{DRIVE_UPLOAD_BASE}/files/{file_id}?uploadType=media",
                data=body_bytes,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                method="PATCH",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))

        out = _retry(_patch, label=f"drive_upload_patch {file_id}")
        return out.get("id", file_id)

    # Multipart insert with random boundary to prevent collision with payload bytes.
    import secrets
    boundary = f"==NUZANTARA_{secrets.token_hex(16)}=="
    metadata = {
        "name": filename,
        "parents": [parent_id],
        "mimeType": "application/json",
    }
    multipart_body = (
        f"--{boundary}\r\n"
        f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(metadata)}\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: application/json\r\n\r\n"
    ).encode() + body_bytes + f"\r\n--{boundary}--\r\n".encode()

    # Sanity check boundary not present in payload (defense-in-depth)
    if boundary.encode("utf-8") in body_bytes:
        raise BackupError("multipart boundary collision with payload — regenerate")

    def _post() -> dict[str, Any]:
        req = urllib.request.Request(
            f"{DRIVE_UPLOAD_BASE}/files?uploadType=multipart",
            data=multipart_body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": f"multipart/related; boundary={boundary}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8"))

    out = _retry(_post, label="drive_upload_post")
    return out["id"]


# --- NLM helpers -----------------------------------------------------------


def _nlm_call(args: list[str]) -> str:
    """Invoke nlm CLI, return stdout. Raise BackupError on non-zero exit."""
    if shutil.which(NLM_CLI) is None:
        raise BackupError(
            f"NLM CLI {NLM_CLI!r} not found in PATH — install via "
            "`uv tool install notebooklm-mcp-cli` or check ~/.local/bin",
        )
    try:
        out = subprocess.run(
            [NLM_CLI, *args],
            capture_output=True,
            text=True,
            timeout=NLM_CLI_TIMEOUT_S,
            check=True,
        )
        return out.stdout
    except subprocess.CalledProcessError as exc:
        # Defensive: stderr can be None if the child was killed by signal
        # before producing output. Guard against TypeError on slice.
        stderr = (exc.stderr or "")[:300]
        raise BackupError(
            f"nlm {' '.join(args)} failed (rc={exc.returncode}): {stderr}",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise BackupError(f"nlm {' '.join(args)} timed out after {NLM_CLI_TIMEOUT_S}s") from exc


def _nlm_list_notebooks() -> list[dict[str, Any]]:
    """Return list of notebooks visible to the authenticated CLI session.

    Output schema: list of dicts with at minimum ``id``, ``title``,
    ``source_count``, ``updated_at``. Verified empirically against
    `nlm notebook list --json` (singular `notebook`, `--json` flag,
    NOT `nlm notebooks list --format json`).
    """
    raw = _nlm_call(["notebook", "list", "--json"])
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BackupError(f"nlm notebook list returned invalid JSON: {raw[:200]}") from exc
    return data if isinstance(data, list) else data.get("notebooks", [])


def _nlm_describe_notebook(notebook_id: str) -> dict[str, Any]:
    """`nlm notebook describe NOTEBOOK_ID --json` — AI summary + topics."""
    raw = _nlm_call(["notebook", "describe", notebook_id, "--json"])
    return json.loads(raw)


def _nlm_list_sources(notebook_id: str) -> list[dict[str, Any]]:
    """`nlm source list NOTEBOOK_ID --json` — list sources in a notebook."""
    raw = _nlm_call(["source", "list", notebook_id, "--json"])
    data = json.loads(raw)
    return data if isinstance(data, list) else data.get("sources", [])


def _nlm_get_source_content(notebook_id: str, source_id: str) -> dict[str, Any]:
    """`nlm source content SOURCE_ID --json` — raw content (no AI processing).

    Note the CLI takes only SOURCE_ID, not NOTEBOOK_ID. notebook_id is kept
    in the signature for callsite symmetry but not passed to subprocess.
    Both IDs validated against regex BEFORE invocation as defense-in-depth.
    """
    if not NB_ID_RE.match(notebook_id):
        raise BackupError(f"notebook_id {notebook_id!r} fails NB_ID_RE before subprocess")
    if not SOURCE_ID_RE.match(source_id):
        raise BackupError(f"source_id {source_id!r} fails SOURCE_ID_RE — refusing subprocess call")
    raw = _nlm_call(["source", "content", source_id, "--json"])
    return json.loads(raw)


# --- main backup logic -----------------------------------------------------


def _today_folder_name(now: dt.datetime | None = None) -> str:
    if now is None:
        now = dt.datetime.now(dt.timezone.utc).astimezone()
    return now.strftime("%Y-%m-%d")


def backup_one_notebook(
    nb: dict[str, Any], token: str, day_folder_id: str, *, apply: bool
) -> dict[str, Any]:
    """Build and (optionally) upload backup JSON for one notebook.

    Returns a result dict with keys ``nb_id``, ``title``, ``source_count``,
    ``upload_status`` (``"applied"`` | ``"skipped-dry-run"`` | ``"error"``),
    ``error`` (str | None).
    """
    nb_id = nb.get("id") or nb.get("notebook_id") or ""
    if not NB_ID_RE.match(nb_id):
        return {"nb_id": nb_id, "title": nb.get("title", ""),
                "source_count": 0, "upload_status": "error",
                "error": "invalid nb_id format"}
    title = nb.get("title", "")
    try:
        descr = _nlm_describe_notebook(nb_id)
    except BackupError as exc:
        return {"nb_id": nb_id, "title": title, "source_count": 0,
                "upload_status": "error", "error": f"describe failed: {exc}"}

    try:
        sources = _nlm_list_sources(nb_id)
    except BackupError as exc:
        return {"nb_id": nb_id, "title": title, "source_count": 0,
                "upload_status": "error", "error": f"sources list failed: {exc}"}

    source_payloads = []
    for s in sources:
        sid = s.get("id") or s.get("source_id") or ""
        if not sid or not SOURCE_ID_RE.match(sid):
            source_payloads.append({"meta": s, "content": {"_error": f"invalid source id {sid!r}"}})
            continue
        try:
            content = _nlm_get_source_content(nb_id, sid)
        except BackupError as exc:
            content = {"_error": str(exc)}
        source_payloads.append({"meta": s, "content": content})
        time.sleep(PER_SOURCE_SLEEP_S)

    payload = {
        "schema_version": 1,
        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "notebook": {"id": nb_id, "title": title, "describe": descr},
        "sources": source_payloads,
    }

    if not apply:
        return {"nb_id": nb_id, "title": title, "source_count": len(sources),
                "upload_status": "skipped-dry-run", "error": None}

    try:
        file_id = _drive_upload_json(token, day_folder_id, f"{nb_id}.json", payload)
    except (urllib.error.HTTPError, urllib.error.URLError, BackupError) as exc:
        return {"nb_id": nb_id, "title": title, "source_count": len(sources),
                "upload_status": "error", "error": f"upload failed: {exc}"}

    return {"nb_id": nb_id, "title": title, "source_count": len(sources),
            "upload_status": "applied", "drive_file_id": file_id, "error": None}


def run_backup(*, apply: bool, max_notebooks: int | None = None) -> dict[str, Any]:
    """Run a full backup pass over all notebooks.

    Returns summary dict with per-notebook outcomes.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    creds = _load_oauth_credentials()
    token = _mint_access_token(creds)
    token_minted_at = time.monotonic()

    # Verify account + root folder ALWAYS, even on dry-run, so the operator's
    # sanity check actually exercises the auth path that production will use.
    # (PR #456 review MEDIUM #5: dry-run was skipping these checks.)
    about = _verify_account(token)
    logger.info(
        "Account verified: %s (used=%s/%s bytes)",
        about.get("user", {}).get("emailAddress"),
        about.get("storageQuota", {}).get("usage"),
        about.get("storageQuota", {}).get("limit"),
    )
    _verify_root_folder(token, BACKUP_ROOT_FOLDER_ID)
    logger.info("Backup root folder verified: %s", BACKUP_ROOT_FOLDER_ID)

    notebooks = _nlm_list_notebooks()
    logger.info("Discovered %d notebooks", len(notebooks))
    if len(notebooks) > MAX_NOTEBOOKS_HARD_CAP:
        raise BackupError(
            f"NLM returned {len(notebooks)} notebooks, hard cap is "
            f"{MAX_NOTEBOOKS_HARD_CAP}. Refusing to proceed — investigate "
            "NLM CLI output before continuing.",
        )
    if max_notebooks is not None:
        notebooks = notebooks[:max_notebooks]
        logger.info("Limiting to first %d notebooks (--max-notebooks)", max_notebooks)

    day_folder_name = _today_folder_name()
    if apply:
        day_folder_id = _drive_find_or_create_folder(
            token, BACKUP_ROOT_FOLDER_ID, day_folder_name,
        )
        logger.info("Drive day folder %s/ id=%s", day_folder_name, day_folder_id)
    else:
        day_folder_id = "DRY-RUN"

    # Token refresh budget: refresh after 50min to give headroom on the 60min TTL
    # so a long-running batch (60+ NB × ~30 sources) doesn't hit 401 mid-loop.
    TOKEN_REFRESH_AFTER_S = 50 * 60

    results: list[dict[str, Any]] = []
    for i, nb in enumerate(notebooks):
        if time.monotonic() - token_minted_at > TOKEN_REFRESH_AFTER_S:
            logger.info("Refreshing access token after %ds", int(time.monotonic() - token_minted_at))
            token = _mint_access_token(creds)
            token_minted_at = time.monotonic()
        logger.info("[%d/%d] backing up %s", i + 1, len(notebooks), nb.get("id"))
        res = backup_one_notebook(nb, token, day_folder_id, apply=apply)
        results.append(res)
        time.sleep(PER_NB_SLEEP_S)

    summary = {
        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "applied": apply,
        "day_folder": day_folder_name,
        "day_folder_id": day_folder_id,
        "total_notebooks": len(notebooks),
        "applied_count": sum(1 for r in results if r["upload_status"] == "applied"),
        "error_count": sum(1 for r in results if r["upload_status"] == "error"),
        "results": results,
    }
    logger.info(
        "Done: applied=%d errors=%d total=%d",
        summary["applied_count"], summary["error_count"], summary["total_notebooks"],
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--apply", action="store_true",
        help="Perform Drive uploads. Without --apply, runs dry (inventory only).",
    )
    parser.add_argument(
        "--max-notebooks", type=int, default=None,
        help="Limit to first N notebooks (testing).",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Emit summary JSON to stdout (for cron consumption).",
    )
    args = parser.parse_args(argv)

    try:
        summary = run_backup(apply=args.apply, max_notebooks=args.max_notebooks)
    except BackupError as exc:
        logger.error("Backup aborted: %s", exc)
        return 2

    if args.json:
        sys.stdout.write(json.dumps(summary, indent=2) + "\n")
    else:
        sys.stdout.write(
            f"NLM Drive backup — applied={summary['applied_count']} "
            f"errors={summary['error_count']} total={summary['total_notebooks']} "
            f"day_folder={summary['day_folder']}\n",
        )
    return 0 if summary["error_count"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
