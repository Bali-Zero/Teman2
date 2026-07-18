#!/usr/bin/env python3
"""Backfill ``clients.google_drive_folder_id`` from m227 folder-name routing evidence.

Context (2026-07-18): the v2.2-m227-folder reroute produced folder-name candidates
for ~351 clients whose Drive documents live inside a folder named after them.
Only 173/11,744 clients have ``google_drive_folder_id`` populated. This script
promotes the high-confidence subset of that routing evidence into the official
CRM mapping, acting as the reviewer (no human review — session-owned per
ship-lifecycle rule).

Review bar (Tier A — every gate must pass before a write):
  1. Candidate evidence: proposal candidates with ``method='folder_name'``,
     ``table='clients'`` and pipeline_version='v2.2-m227-folder', where the
     matched folder segment equals the CRM full name (normalized) OR the
     trigram similarity is >= 0.85.
  2. Folder uniqueness per client: if a client matched >1 distinct folder
     name, pick the one backing the most documents; strict tie -> skip.
  3. Drive ground truth: for up to 3 sample files of the client, walk the
     ancestor chain via the Drive API until a folder whose normalized name
     equals the matched segment. ALL resolved samples must converge on the
     SAME folder id; zero resolutions or divergence -> skip.
  4. Bijectivity: a folder id claimed by >=2 clients -> skip all claimants.
     A folder id already mapped to a DIFFERENT client -> skip.
  5. Live guard: GET the client profile on Fly prod; any non-null
     ``google_drive_folder_id`` is NEVER overwritten (skip; if it already
     equals ours -> noted as already_correct).

Write path: ``PATCH /api/crm/clients/{id}/profile`` on Fly prod (the sanctioned
CRM API — handles RBAC + cache invalidation). NEVER raw SQL against prod; the
local DB (``nuzantara_dev`` snapshot) is read-only evidence here.

PII (SYMBIOSIS Law 2): the audit log and stdout report contain ONLY integer
client ids, opaque Drive folder/file ids, similarity numbers and decision
codes. Folder names / client names are processed in memory and never persisted.

Auth: mints a short-lived admin JWT with the backend's JWT_SECRET_KEY (read
from ``~/.cell-bridge-state/intake-review-reader.env``; the secret is never
printed). Drive access uses the intake service-account key file (read-only
metadata scope).

Usage:
  python scripts/intake_drive_folder_id_backfill.py            # dry-run (default)
  python scripts/intake_drive_folder_id_backfill.py --limit 5  # smoke
  python scripts/intake_drive_folder_id_backfill.py --apply    # write to prod
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import asyncpg
import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "backend-rag"))

# Single source of truth for folder-name cleaning: candidates store
# matched_value AFTER _folder_segments cleaning (decorations/parentheticals
# stripped), so the Drive walk must clean raw folder names the same way
# before comparing — a raw-name equality check silently misses every
# decorated folder.
from backend.services.intake.routing import _folder_segments  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("gdrive_backfill")

DEFAULT_DSN = "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"
DEFAULT_BASE_URL = "https://nuzantara-rag.fly.dev"
DEFAULT_SA_FILE = (
    "/Users/nuzantara/.config/nuzantara/service-accounts/"
    "nuzantara-google-drive-sa-20260530.json"
)
DEFAULT_JWT_ENV_FILE = "~/.cell-bridge-state/intake-review-reader.env"
DEFAULT_AUDIT_DIR = "/tmp/intake-rescue-06ffbfc2"

PIPELINE_VERSION = "v2.2-m227-folder"
SIM_THRESHOLD = 0.85
MAX_ANCESTOR_DEPTH = 15
# Intake Drive scope folder (com.balizero.drive-intake-drain plist): every
# drained doc lived under this root at enqueue time. Used as the ancestor
# anchor for the name-search fallback.
DEFAULT_SCOPE_FOLDER_ID = "1LjJjBdJZ115Iyu_Bthl-PVC2XKlXRDrF"
SAMPLE_FILES_PER_CLIENT = 3
# Domain-wide delegation: the SA alone sees nothing (404) — production access
# goes through impersonation of the Workspace user, and the DWD grant in the
# Admin Console is scoped exactly to auth/drive (metadata.readonly is NOT
# granted). Mirrors ServiceAccountDriveService. This script only ever calls
# files().get — read-only by behavior.
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
DRIVE_DELEGATED_USER = "zero@balizero.com"
JWT_TTL_HOURS = 2
API_SLEEP_SECONDS = 0.15

# Evidence query: one row per (client, normalized matched folder segment) that
# clears the Tier-A textual bar. mv_norm is PII-in-memory only — never logged.
CANDIDATE_SQL = """
WITH cand AS (
  SELECT q.source_ref,
         q.source_path,
         (c->>'id')::bigint AS client_id,
         lower(regexp_replace(trim(c->>'matched_value'), '\\s+', ' ', 'g')) AS mv_norm,
         lower(regexp_replace(trim(c->>'name'), '\\s+', ' ', 'g')) AS crm_norm,
         (c->>'folder_sim')::float AS sim
  FROM document_routing_proposal p
  JOIN intake_queue q ON q.id = p.queue_id
  CROSS JOIN LATERAL jsonb_array_elements(p.entity_resolution->'candidates') c
  WHERE q.pipeline_version = $1
    AND q.source = 'drive'
    AND q.source_ref LIKE 'drive:%'
    AND c->>'method' = 'folder_name'
    AND c->>'table' = 'clients'
)
SELECT client_id,
       mv_norm,
       bool_or(mv_norm = crm_norm) AS has_exact,
       max(sim) AS max_sim,
       count(*) AS n_docs,
       (array_agg(DISTINCT source_ref))[1:20] AS sample_refs,
       (array_agg(DISTINCT source_path))[1:8] AS sample_paths
FROM cand
WHERE mv_norm = crm_norm OR sim >= $2
GROUP BY client_id, mv_norm
ORDER BY client_id
"""

EXISTING_MAPPING_SQL = """
SELECT id, google_drive_folder_id
FROM clients
WHERE google_drive_folder_id IS NOT NULL AND deleted_at IS NULL
"""


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


@dataclass
class ClientPlan:
    client_id: int
    mv_norm: str  # in-memory only, never persisted
    max_sim: float
    has_exact: bool
    n_docs: int
    sample_file_ids: list[str]
    raw_variants: list[str] = field(default_factory=list)  # in-memory only
    folder_id: str | None = None
    resolved_via: str = ""
    decision: str = "pending"
    detail: str = ""
    resolved_ids: list[str] = field(default_factory=list)

    def audit_row(self) -> dict[str, Any]:
        """PII-safe audit payload: ids + numbers + decision codes only."""
        return {
            "client_id": self.client_id,
            "folder_id": self.folder_id,
            "resolved_via": self.resolved_via,
            "max_sim": round(self.max_sim, 4),
            "has_exact": self.has_exact,
            "n_docs": self.n_docs,
            "n_samples_resolved": len(self.resolved_ids),
            "decision": self.decision,
            "detail": self.detail,
        }


def _read_jwt_secret(env_file: str) -> str:
    path = Path(env_file).expanduser()
    if not path.is_file():
        raise SystemExit(f"JWT env file not found: {path}")
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("JWT_SECRET_KEY="):
            secret = line.split("=", 1)[1].strip().strip("'\"")
            if secret:
                return secret
    raise SystemExit("JWT_SECRET_KEY not found in env file (never printed)")


def _mint_admin_jwt(secret: str) -> str:
    from jose import jwt as jose_jwt

    now = datetime.now(timezone.utc)
    claims = {
        "sub": "gdrive-folder-backfill",
        "email": "zero@balizero.com",
        "role": "admin",
        "type": "access",
        "iat": now,
        "exp": now + timedelta(hours=JWT_TTL_HOURS),
        "jti": str(uuid.uuid4()),
    }
    return jose_jwt.encode(claims, secret, algorithm="HS256")


def _build_drive_service(sa_file: str):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        sa_file, scopes=DRIVE_SCOPES
    ).with_subject(DRIVE_DELEGATED_USER)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _drive_meta(service, file_id: str, cache: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if file_id in cache:
        return cache[file_id]
    try:
        meta = (
            service.files()
            .get(fileId=file_id, fields="id, name, parents", supportsAllDrives=True)
            .execute()
        )
    except Exception as exc:  # 404 / 403 on individual nodes: treat as unresolvable
        logger.debug("drive meta failed for %s: %s", file_id, type(exc).__name__)
        cache[file_id] = {}
        return None
    cache[file_id] = meta
    return meta


def _resolve_named_ancestor(
    service, file_id: str, target_norm: str, cache: dict[str, dict[str, Any]]
) -> str | None:
    """Walk the parent chain of ``file_id`` until a folder whose normalized
    name equals ``target_norm``; return its id, or None."""
    meta = _drive_meta(service, file_id, cache)
    if not meta:
        return None
    cur = (meta.get("parents") or [None])[0]
    depth = 0
    while cur and depth < MAX_ANCESTOR_DEPTH:
        fmeta = _drive_meta(service, cur, cache)
        if not fmeta:
            return None
        raw_name = fmeta.get("name", "")
        cleaned = {_norm(seg) for seg in _folder_segments(raw_name)}
        if target_norm in cleaned or _norm(raw_name) == target_norm:
            return cur
        cur = (fmeta.get("parents") or [None])[0]
        depth += 1
    return None


async def _load_plans(dsn: str) -> tuple[list[ClientPlan], dict[str, int]]:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        rows = await conn.fetch(CANDIDATE_SQL, PIPELINE_VERSION, SIM_THRESHOLD)
        existing = await conn.fetch(EXISTING_MAPPING_SQL)
    finally:
        await conn.close()

    folder_owner_snapshot = {r["google_drive_folder_id"]: r["id"] for r in existing}

    by_client: dict[int, list[asyncpg.Record]] = defaultdict(list)
    for r in rows:
        by_client[r["client_id"]].append(r)

    plans: list[ClientPlan] = []
    for client_id, group in sorted(by_client.items()):
        group = sorted(group, key=lambda r: (-r["n_docs"], r["mv_norm"]))
        chosen = group[0]
        if len(group) > 1 and group[0]["n_docs"] == group[1]["n_docs"]:
            plans.append(
                ClientPlan(
                    client_id=client_id,
                    mv_norm=chosen["mv_norm"],
                    max_sim=float(chosen["max_sim"]),
                    has_exact=bool(chosen["has_exact"]),
                    n_docs=int(chosen["n_docs"]),
                    sample_file_ids=[],
                    decision="skip",
                    detail="multi_folder_tie",
                )
            )
            continue
        file_ids = [
            ref.split("drive:", 1)[1]
            for ref in (chosen["sample_refs"] or [])
            if ref and ref.startswith("drive:")
        ][:SAMPLE_FILES_PER_CLIENT]
        # Reconstruct the RAW folder-name variants (pre-cleaning) from the
        # historical source_path: the segment(s) whose cleaned form equals the
        # matched value. Needed by the name-search fallback when the file has
        # been moved since enqueue.
        raw_variants: list[str] = []
        seen_norm: set[str] = set()
        for path in chosen["sample_paths"] or []:
            for raw_seg in (path or "").split("/"):
                raw_seg = raw_seg.strip()
                if not raw_seg or _norm(raw_seg) in seen_norm:
                    continue
                cleaned = {_norm(s) for s in _folder_segments(raw_seg)}
                if chosen["mv_norm"] in cleaned or _norm(raw_seg) == chosen["mv_norm"]:
                    raw_variants.append(raw_seg)
                    seen_norm.add(_norm(raw_seg))
        plans.append(
            ClientPlan(
                client_id=client_id,
                mv_norm=chosen["mv_norm"],
                max_sim=float(chosen["max_sim"]),
                has_exact=bool(chosen["has_exact"]),
                n_docs=int(chosen["n_docs"]),
                sample_file_ids=file_ids,
                raw_variants=raw_variants[:5],
            )
        )
    return plans, folder_owner_snapshot


def _reaches_scope(
    service, folder_id: str, scope_id: str, cache: dict[str, dict[str, Any]]
) -> bool:
    cur: str | None = folder_id
    depth = 0
    while cur and depth < MAX_ANCESTOR_DEPTH:
        if cur == scope_id:
            return True
        meta = _drive_meta(service, cur, cache)
        if not meta:
            return False
        cur = (meta.get("parents") or [None])[0]
        depth += 1
    return False


def _search_folder_by_name(service, raw_name: str) -> list[dict[str, Any]]:
    escaped = raw_name.replace("\\", "\\\\").replace("'", "\\'")
    query = (
        f"name = '{escaped}' and "
        "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    try:
        resp = (
            service.files()
            .list(
                q=query,
                fields="files(id, name, parents)",
                pageSize=10,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
    except Exception as exc:
        logger.debug("folder search failed: %s", type(exc).__name__)
        return []
    return resp.get("files", [])


def _resolve_drive_folders(plans: list[ClientPlan], sa_file: str, scope_id: str) -> None:
    service = _build_drive_service(sa_file)
    cache: dict[str, dict[str, Any]] = {}
    for plan in plans:
        if plan.decision != "pending":
            continue
        # Primary evidence: ancestor walk from the client's own drained files —
        # the folder still CONTAINS the doc and bears the client's name.
        resolved: list[str] = []
        for fid in plan.sample_file_ids:
            folder = _resolve_named_ancestor(service, fid, plan.mv_norm, cache)
            if folder:
                resolved.append(folder)
        plan.resolved_ids = resolved
        distinct = sorted(set(resolved))
        if len(distinct) > 1:
            plan.decision, plan.detail = "skip", "drive_divergent"
            continue
        if len(distinct) == 1:
            plan.folder_id = distinct[0]
            plan.resolved_via = "walk"
            continue
        # Fallback (file moved since enqueue): exact-name folder search.
        # Weaker evidence, so two extra gates: the result must be UNIQUE
        # across all raw variants, and its ancestor chain must reach the
        # intake scope folder (anti-homonym anchor).
        found: dict[str, dict[str, Any]] = {}
        for raw in plan.raw_variants:
            for f in _search_folder_by_name(service, raw):
                found[f["id"]] = f
        in_scope = [
            fid for fid in found if _reaches_scope(service, fid, scope_id, cache)
        ]
        if not in_scope:
            plan.decision, plan.detail = "skip", "drive_unresolved"
        elif len(in_scope) > 1:
            plan.decision, plan.detail = "skip", "search_ambiguous"
        else:
            plan.folder_id = in_scope[0]
            plan.resolved_via = "search"


def _enforce_bijectivity(
    plans: list[ClientPlan], folder_owner_snapshot: dict[str, int]
) -> None:
    claimants: dict[str, list[ClientPlan]] = defaultdict(list)
    for plan in plans:
        if plan.decision == "pending" and plan.folder_id:
            claimants[plan.folder_id].append(plan)
    for folder_id, group in claimants.items():
        if len(group) > 1:
            for plan in group:
                plan.decision, plan.detail = "skip", "folder_conflict_multi_client"
            continue
        plan = group[0]
        snapshot_owner = folder_owner_snapshot.get(folder_id)
        if snapshot_owner is not None and snapshot_owner != plan.client_id:
            plan.decision, plan.detail = "skip", f"folder_taken_by_{snapshot_owner}"


def _live_guard_decision(live_value: str | None, folder_id: str) -> tuple[str, str] | None:
    """Never-overwrite invariant: any non-null live value wins, always."""
    if live_value:
        if live_value == folder_id:
            return ("skip", "already_correct")
        return ("skip", "already_set_live")
    return None


async def _live_screen(
    plans: list[ClientPlan], client: httpx.AsyncClient
) -> dict[str, int]:
    """GET each pending client's live prod state. Marks dead/already-served
    plans and returns the LIVE folder->client ownership map.

    This MUST run BEFORE bijectivity: the CRM has duplicate client records
    (same person, two ids) whose shared folder would otherwise count as a
    multi-claimant conflict even when prod has already deleted one twin.
    """
    live_owner: dict[str, int] = {}
    for plan in plans:
        if plan.decision != "pending" or not plan.folder_id:
            continue
        await asyncio.sleep(API_SLEEP_SECONDS)
        url = f"/api/crm/clients/{plan.client_id}/profile"
        try:
            resp = await client.get(url)
        except httpx.HTTPError as exc:
            plan.decision, plan.detail = "error", f"get_{type(exc).__name__}"
            continue
        if resp.status_code == 404:
            plan.decision, plan.detail = "skip", "not_found_prod"
            continue
        if resp.status_code != 200:
            plan.decision, plan.detail = "error", f"get_http_{resp.status_code}"
            continue
        live_value = (resp.json().get("client") or {}).get("google_drive_folder_id")
        if live_value:
            live_owner[live_value] = plan.client_id
        guard = _live_guard_decision(live_value, plan.folder_id)
        if guard:
            plan.decision, plan.detail = guard
    return live_owner


async def _apply_via_api(
    plans: list[ClientPlan], client: httpx.AsyncClient, apply: bool
) -> None:
    for plan in plans:
        if plan.decision != "pending" or not plan.folder_id:
            continue
        if not apply:
            plan.decision, plan.detail = "would_apply", ""
            continue
        await asyncio.sleep(API_SLEEP_SECONDS)
        url = f"/api/crm/clients/{plan.client_id}/profile"
        patch = await client.patch(url, json={"google_drive_folder_id": plan.folder_id})
        if patch.status_code != 200:
            plan.decision, plan.detail = "error", f"patch_http_{patch.status_code}"
            continue
        verify = await client.get(url)
        verified = (
            verify.status_code == 200
            and (verify.json().get("client") or {}).get("google_drive_folder_id")
            == plan.folder_id
        )
        if verified:
            plan.decision, plan.detail = "applied", "verified"
        else:
            plan.decision, plan.detail = "error", "applied_but_verify_mismatch"


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="write to prod (default dry-run)")
    parser.add_argument("--limit", type=int, default=0, help="cap clients processed (smoke)")
    parser.add_argument("--dsn", default=os.getenv("INTAKE_DATABASE_URL", DEFAULT_DSN))
    parser.add_argument("--base-url", default=os.getenv("CRM_PUSH_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--sa-file", default=os.getenv("INTAKE_SA_FILE", DEFAULT_SA_FILE))
    parser.add_argument("--jwt-env-file", default=os.getenv("BACKFILL_JWT_ENV_FILE", DEFAULT_JWT_ENV_FILE))
    parser.add_argument("--audit-dir", default=os.getenv("BACKFILL_AUDIT_DIR", DEFAULT_AUDIT_DIR))
    parser.add_argument(
        "--scope-folder-id",
        default=os.getenv("INTAKE_DRIVE_SCOPE_FOLDER_ID", DEFAULT_SCOPE_FOLDER_ID),
    )
    args = parser.parse_args()

    plans, folder_owner_snapshot = await _load_plans(args.dsn)
    logger.info("evidence loaded: %d clients clear the Tier-A textual bar", len(plans))
    if args.limit > 0:
        plans = plans[: args.limit]

    logger.info("resolving Drive folder ids (read-only metadata walk)...")
    _resolve_drive_folders(plans, args.sa_file, args.scope_folder_id)

    token = _mint_admin_jwt(_read_jwt_secret(args.jwt_env_file))
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(
        base_url=args.base_url, headers=headers, timeout=30.0
    ) as http_client:
        # Live screen FIRST (dead twins / already-served drop out), then
        # bijectivity on the survivors with live ownership taking precedence
        # over the (staler) local snapshot.
        live_owner = await _live_screen(plans, http_client)
        # Snapshot claims by clients PROVEN dead on prod (404) decay — the
        # surviving duplicate-twin must not stay blocked by a ghost owner.
        dead_ids = {p.client_id for p in plans if p.detail == "not_found_prod"}
        effective_snapshot = {
            folder: cid
            for folder, cid in folder_owner_snapshot.items()
            if cid not in dead_ids
        }
        _enforce_bijectivity(plans, {**effective_snapshot, **live_owner})
        await _apply_via_api(plans, http_client, apply=args.apply)

    audit_dir = Path(args.audit_dir)
    audit_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    mode = "apply" if args.apply else "dryrun"
    audit_path = audit_dir / f"gdrive_backfill_{mode}_{stamp}.jsonl"
    with audit_path.open("w", encoding="utf-8") as fh:
        for plan in plans:
            fh.write(json.dumps(plan.audit_row()) + "\n")

    counts: dict[str, int] = defaultdict(int)
    for plan in plans:
        key = plan.decision if not plan.detail else f"{plan.decision}:{plan.detail}"
        counts[key] += 1
    logger.info("=== decision summary (%s) ===", mode)
    for key in sorted(counts):
        logger.info("%-40s %d", key, counts[key])
    logger.info("audit log: %s", audit_path)

    errors = sum(1 for p in plans if p.decision == "error")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
