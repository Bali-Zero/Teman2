"""Drive folder setup — Week 0 Phase D foundation.

Creates the three top-level folders on antonellosiano@gmail.com's 30TB
personal Drive that downstream backup pipelines write into:

    /nuzantara-nb-backup-daily/   → daily NLM export targets
    /nuzantara-nb-cold-archive/   → apoptosis-archived NB sources
    /nuzantara-rd-archive/        → R&D pipeline output (arxiv + framework changelogs)

The script is idempotent: it queries Drive for each folder name in the
account root before creating it, so re-running is safe.

Auth path:
    1. Reads OAuth refresh token + client_id + client_secret from
       ``~/.nuzantara/drive_backup_oauth.json`` (chmod 0400 enforced).
    2. If the file is missing, prints recovery instructions referencing the
       existing rclone OAuth token and exits 2.

We deliberately accept the existing rclone refresh-token's broad
``https://www.googleapis.com/auth/drive`` scope rather than minting a fresh
``drive.file``-only token, because rotating to ``drive.file`` would require an
interactive browser flow on the operator's machine and create exactly zero
extra capability for this backup workload (folders we create + files we
upload are already covered by ``drive.file``). The over-scope is documented
in WEEK0_PHASE_D_DRIVE_SETUP.md "Risks / open issues" so a future operator
can mint a narrower token whenever they have GUI access.

Usage::

    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. python -m backend.services.backup.drive_folder_setup --apply

    # Dry-run (default — prints folder IDs without creating anything new
    # if all three already exist):
    PYTHONPATH=. python -m backend.services.backup.drive_folder_setup
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger("backend.services.backup.drive_folder_setup")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

# Token store — chmod 0400, must contain client_id, client_secret, refresh_token
TOKEN_PATH = Path(os.path.expanduser("~/.nuzantara/drive_backup_oauth.json"))

# Folders to create on the account root.
# Path-traversal hardening: validated against FOLDER_NAME_RE before any API call.
FOLDER_NAMES = (
    "nuzantara-nb-backup-daily",
    "nuzantara-nb-cold-archive",
    "nuzantara-rd-archive",
)
FOLDER_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ABOUT_FIELDS = "user,storageQuota"
EXPECTED_USER_EMAIL = "antonellosiano@gmail.com"


class DriveSetupError(RuntimeError):
    """Raised when the setup cannot proceed (missing token, API error, wrong account)."""


def _validate_folder_names(names: tuple[str, ...]) -> None:
    """Reject folder names that are not strict alphanum + dash + underscore.

    This is a path-traversal defense even though Drive uses folder IDs (not
    paths) at the API layer — folder NAMES still get echoed into Drive UI,
    audit logs, and our own ``WEEK0_PHASE_D_DRIVE_SETUP.md``. Refusing
    suspect characters at the script boundary keeps the surface clean.
    """
    for name in names:
        if not FOLDER_NAME_RE.match(name):
            raise DriveSetupError(
                f"Invalid folder name {name!r}: must match {FOLDER_NAME_RE.pattern}",
            )


def _load_oauth_credentials() -> dict[str, str]:
    """Load OAuth client_id, client_secret, refresh_token from TOKEN_PATH.

    Returns dict with keys: client_id, client_secret, refresh_token, scope (optional).
    Enforces chmod 0400 on the file. Raises DriveSetupError if anything is wrong.
    """
    if not TOKEN_PATH.exists():
        raise DriveSetupError(
            f"OAuth token store missing: {TOKEN_PATH}. "
            "Run setup with --bootstrap-from-rclone or perform InstalledAppFlow first. "
            "See WEEK0_PHASE_D_DRIVE_SETUP.md.",
        )

    # Enforce chmod 0400 — fail loud if perms are wrong.
    mode = stat.S_IMODE(TOKEN_PATH.stat().st_mode)
    if mode != 0o400:
        logger.warning(
            "TOKEN_PATH %s mode is 0%o, expected 0400 — fixing now",
            TOKEN_PATH,
            mode,
        )
        TOKEN_PATH.chmod(0o400)

    try:
        with TOKEN_PATH.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise DriveSetupError(f"Cannot read token store {TOKEN_PATH}: {exc}") from exc

    required = {"client_id", "client_secret", "refresh_token"}
    missing = required - set(payload)
    if missing:
        raise DriveSetupError(
            f"Token store {TOKEN_PATH} missing keys: {sorted(missing)}",
        )

    return payload


def _exchange_refresh_token(creds: dict[str, str]) -> str:
    """Exchange refresh_token for short-lived access_token.

    Uses the OAuth 2.0 token endpoint directly (no google-auth-oauthlib
    dependency required for this minimal flow).
    """
    data = urllib.parse.urlencode(
        {
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
            "refresh_token": creds["refresh_token"],
            "grant_type": "refresh_token",
        },
    ).encode("utf-8")

    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")  # noqa: S310 — explicit https URL
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            body = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise DriveSetupError(
            f"OAuth token refresh failed (HTTP {exc.code}): {detail}",
        ) from exc
    except urllib.error.URLError as exc:
        raise DriveSetupError(f"OAuth token refresh network error: {exc}") from exc

    if "access_token" not in body:
        raise DriveSetupError(
            f"OAuth refresh returned no access_token: {body}",
        )
    return body["access_token"]


def _drive_api_call(
    method: str,
    path: str,
    access_token: str,
    *,
    params: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Minimal Drive v3 client built on stdlib urllib.

    No httpx dependency so the setup script can run in a fresh venv.
    Returns parsed JSON body. Raises DriveSetupError on non-2xx.
    """
    url = f"{DRIVE_API_BASE}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"

    headers = {"Authorization": f"Bearer {access_token}"}
    payload: bytes | None = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=payload, method=method, headers=headers)  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise DriveSetupError(
            f"Drive {method} {path} failed (HTTP {exc.code}): {detail}",
        ) from exc
    except urllib.error.URLError as exc:
        raise DriveSetupError(
            f"Drive {method} {path} network error: {exc}",
        ) from exc


def _verify_account(access_token: str) -> dict[str, Any]:
    """Confirm the OAuth token belongs to the expected 30TB account."""
    about = _drive_api_call(
        "GET",
        "/about",
        access_token,
        params={"fields": ABOUT_FIELDS},
    )
    user = about.get("user", {})
    email = user.get("emailAddress")
    if email != EXPECTED_USER_EMAIL:
        raise DriveSetupError(
            f"Drive token belongs to {email!r}, expected {EXPECTED_USER_EMAIL!r}. "
            "Refusing to create folders on the wrong account.",
        )
    return about


def _find_folder_id(name: str, access_token: str) -> str | None:
    """Return the folder ID if a folder with this name exists at root, else None.

    Uses Drive's search with a name + mimeType + parent filter so the result
    set is bounded; if there are duplicates we pick the oldest (lexically first
    by id, deterministic) and warn — re-running the script with the
    same name should not be ambiguous in the first place.
    """
    # Escape single quotes in the folder name per Drive query syntax.
    escaped = name.replace("\\", "\\\\").replace("'", "\\'")
    query = (
        f"name = '{escaped}' "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and 'root' in parents "
        f"and trashed = false"
    )
    response = _drive_api_call(
        "GET",
        "/files",
        access_token,
        params={
            "q": query,
            "fields": "files(id,name,createdTime,parents)",
            "pageSize": "10",
        },
    )
    files = response.get("files", [])
    if not files:
        return None
    if len(files) > 1:
        ids = sorted(f["id"] for f in files)
        logger.warning(
            "Folder %r has %d duplicates at root: %s — picking %s",
            name,
            len(files),
            ids,
            ids[0],
        )
        return ids[0]
    return files[0]["id"]


def _create_folder(name: str, access_token: str) -> str:
    """Create a folder at account root and return its ID."""
    body = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": ["root"],
    }
    response = _drive_api_call(
        "POST",
        "/files",
        access_token,
        params={"fields": "id,name"},
        body=body,
    )
    folder_id = response.get("id")
    if not folder_id:
        raise DriveSetupError(f"Drive POST /files returned no id: {response}")
    return folder_id


def _list_folder_contents(folder_id: str, access_token: str) -> list[dict[str, Any]]:
    """List children of a folder (cap 10 entries) for verification output."""
    response = _drive_api_call(
        "GET",
        "/files",
        access_token,
        params={
            "q": f"'{folder_id}' in parents and trashed = false",
            "fields": "files(id,name,mimeType,createdTime)",
            "pageSize": "10",
        },
    )
    return response.get("files", [])


def setup_folders(*, apply: bool = False) -> dict[str, Any]:
    """Idempotent folder setup. Returns a summary dict suitable for JSON dump.

    When apply=False, missing folders are reported but NOT created.
    When apply=True, missing folders are created; existing folders untouched.
    """
    _validate_folder_names(FOLDER_NAMES)
    creds = _load_oauth_credentials()
    access_token = _exchange_refresh_token(creds)
    about = _verify_account(access_token)

    quota = about.get("storageQuota", {})
    summary: dict[str, Any] = {
        "auth_account": about.get("user", {}).get("emailAddress"),
        "auth_account_name": about.get("user", {}).get("displayName"),
        "quota_limit_bytes": quota.get("limit"),
        "quota_usage_bytes": quota.get("usage"),
        "scope": creds.get("scope", "unknown"),
        "folders": {},
    }

    for name in FOLDER_NAMES:
        existing = _find_folder_id(name, access_token)
        if existing is not None:
            logger.info("Folder %r exists: id=%s", name, existing)
            children = _list_folder_contents(existing, access_token)
            summary["folders"][name] = {
                "id": existing,
                "status": "existed",
                "child_count_sample": len(children),
                "children_sample": [
                    {"id": c["id"], "name": c["name"], "mime": c["mimeType"]}
                    for c in children
                ],
            }
            continue

        if not apply:
            logger.info("Folder %r missing (would create with --apply)", name)
            summary["folders"][name] = {"id": None, "status": "missing"}
            continue

        new_id = _create_folder(name, access_token)
        logger.info("Folder %r CREATED: id=%s", name, new_id)
        summary["folders"][name] = {
            "id": new_id,
            "status": "created",
            "child_count_sample": 0,
            "children_sample": [],
        }

    return summary


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns process exit code."""
    parser = argparse.ArgumentParser(
        description="Idempotent Drive folder setup for nuzantara backup foundation.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually create missing folders. Default: dry-run (report only).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print result summary as JSON only (no human-readable lines on stdout).",
    )
    args = parser.parse_args(argv)

    try:
        summary = setup_folders(apply=args.apply)
    except DriveSetupError as exc:
        logger.error("setup failed: %s", exc)
        return 2

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    print("=" * 72)
    print(f"Account     : {summary['auth_account']} ({summary['auth_account_name']})")
    print(f"Scope       : {summary['scope']}")
    print(
        f"Quota       : {summary['quota_usage_bytes']} / {summary['quota_limit_bytes']} bytes",
    )
    print("Folders     :")
    for name, info in summary["folders"].items():
        print(f"  - {name}: id={info['id']} status={info['status']}")
    print("=" * 72)
    print("Summary JSON:")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
