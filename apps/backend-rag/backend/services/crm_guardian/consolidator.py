"""I3 satellite_consolidation + I1 canonical_folder provisioning.

Handles R3 (has canonical, satellites → consolidate) and
R4 (no canonical, satellites → provision + consolidate).

All file moves preserve the revision history (Drive API `files.update`
with addParents/removeParents, not copy+delete).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import asyncpg

from backend.services.crm_guardian.base import (
    GuardianAction,
    GuardianEvent,
    GuardianRunContext,
    record_event,
)

logger = logging.getLogger(__name__)

STANDARD_SUBFOLDERS = [
    "00_Profile",
    "01_Immigration",
    "02_Company",
    "02_Company/AKTA",
    "02_Company/NIB",
    "02_Company/NPWP",
    "02_Company/Profile Perseroan",
    "03_Tax",
    "03_Tax/SPT company",
    "03_Tax/SPT personal",
    "03_Tax/LKPM reports",
    "03_Tax/NPWP personal",
    "04_Family",
    "99_Misc",
]


# ============================================================
# Drive helpers (synchronous — called from async code via no-op wrapper)
# ============================================================
def _drive_create_folder(drive, name: str, parent_id: str) -> dict:
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    return drive.files().create(
        body=metadata,
        fields="id, name, parents, createdTime",
        supportsAllDrives=True,
    ).execute()


def _drive_list_children(drive, folder_id: str) -> list[dict]:
    out: list[dict] = []
    page_token = None
    while True:
        params = {
            "q": f"'{folder_id}' in parents and trashed = false",
            "fields": "nextPageToken, files(id, name, mimeType, parents)",
            "pageSize": 1000,
            "supportsAllDrives": True,
            "includeItemsFromAllDrives": True,
        }
        if page_token:
            params["pageToken"] = page_token
        resp = drive.files().list(**params).execute()
        out.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return out


def _drive_move(drive, file_id: str, new_parent_id: str, old_parent_id: str, new_name: str | None = None) -> dict:
    """Move a file/folder: add to new parent, remove from old. Optionally rename."""
    body: dict[str, Any] = {}
    if new_name:
        body["name"] = new_name
    return drive.files().update(
        fileId=file_id,
        body=body or None,
        addParents=new_parent_id,
        removeParents=old_parent_id,
        fields="id, name, parents",
        supportsAllDrives=True,
    ).execute()


def _drive_trash(drive, file_id: str) -> dict:
    return drive.files().update(
        fileId=file_id,
        body={"trashed": True},
        fields="id, trashed",
        supportsAllDrives=True,
    ).execute()


# Shared soft-delete folder inside BALI ZERO root. Items are moved here
# instead of being trashed when the SA lacks ownership (cross-domain
# trash needs OAuth admin consent the SA doesn't have). Zero empties
# this folder manually in bulk.
DA_TRASHARE_FOLDER_ID = "1kP0NbPiqFGXsiyCzq0OxgrC_wwfzhx9M"


def _drive_move_to_dumpster(drive, file_id: str, label: str | None = None) -> dict:
    """Move an item to `_DA_TRASHARE_` instead of trashing it.

    SA can move (write permission on BALI ZERO shared drive) but cannot
    cross-domain trash. Moving to the shared dumpster is the equivalent
    from the team-member perspective: the item disappears from their
    My Drive and reappears in one central location for manual bulk-trash.
    """
    import time
    meta = drive.files().get(
        fileId=file_id,
        fields="id, name, parents",
        supportsAllDrives=True,
    ).execute()
    original_name = meta.get("name", file_id)
    original_parents = meta.get("parents", [])

    new_name = original_name
    if label:
        ts = int(time.time())
        new_name = f"{label}_{original_name}_{ts}"[:200]

    body: dict = {}
    if new_name != original_name:
        body["name"] = new_name

    return drive.files().update(
        fileId=file_id,
        body=body or None,
        addParents=DA_TRASHARE_FOLDER_ID,
        removeParents=",".join(original_parents) if original_parents else None,
        fields="id, name, parents",
        supportsAllDrives=True,
    ).execute()


def _safe_filename_component(name: str, max_len: int = 60) -> str:
    s = re.sub(r"[^\w\-.() ]+", "_", name)[:max_len].strip(" _")
    return s or "file"


# ============================================================
# I1 provisioning — create canonical folder + template
# ============================================================
def provision_canonical_folder(drive: Any, client_id: int, full_name: str, parent_id: str) -> dict:
    """Create a new canonical folder under parent_id with the full subfolder template.

    Returns:
        dict {root_id, subfolders: {name→id}} where 'subfolders' includes nested paths.
    """
    root_name = f"{client_id}_{full_name}"
    root = _drive_create_folder(drive, root_name, parent_id)
    root_id = root["id"]

    subfolders: dict[str, str] = {"": root_id}
    for path in STANDARD_SUBFOLDERS:
        parent_path, _, leaf = path.rpartition("/")
        parent_leaf_id = subfolders.get(parent_path, root_id)
        created = _drive_create_folder(drive, leaf, parent_leaf_id)
        subfolders[path] = created["id"]

    return {"root_id": root_id, "root_name": root_name, "subfolders": subfolders}


# ============================================================
# I3 — consolidate satellites into canonical/99_Misc
# ============================================================
@dataclass
class MoveOp:
    file_id: str
    file_name: str
    mime_type: str
    source_parent_id: str
    source_parent_name: str
    dest_parent_id: str
    new_name: str


def plan_consolidation(
    drive: Any,
    plan_row: dict,
    canonical_root_id: str,  # noqa: ARG001 — kept for API parity with future per-tree dispatch
    misc_id: str,
) -> list[MoveOp]:
    """Walk each satellite folder and build the flat list of move operations.

    Every file found anywhere in a satellite (recursive) is scheduled to be moved
    directly under canonical/99_Misc with a prefix that records the satellite name
    and the intra-satellite path, so no content is lost or mixed silently.

    New name pattern:  `{sat_short}__{relative_path}__{original_filename}`

    Subfolders of satellites are NOT moved; they are walked to collect their files,
    then the now-empty satellite tree is trashed by the caller.
    """
    ops: list[MoveOp] = []

    for sat in plan_row["satellites"]:
        sat_id = sat["id"]
        sat_short = _safe_filename_component(sat["name"], max_len=30)

        stack: list[tuple[str, str, str]] = [(sat_id, "", sat["name"])]
        # (folder_id, relative_path_from_satellite_root, folder_display_name)

        while stack:
            fid, rel_path, disp = stack.pop()
            try:
                children = _drive_list_children(drive, fid)
            except Exception as exc:  # noqa: BLE001
                logger.warning("list_children failed for %s: %s", fid, exc)
                continue
            for c in children:
                if c["mimeType"] == "application/vnd.google-apps.folder":
                    new_rel = f"{rel_path}/{c['name']}" if rel_path else c["name"]
                    stack.append((c["id"], new_rel, c["name"]))
                    continue
                # File — schedule move
                rel_component = _safe_filename_component(rel_path.replace("/", "_"), max_len=40)
                orig = _safe_filename_component(c["name"], max_len=80)
                new_name = f"{sat_short}__{rel_component}__{orig}" if rel_component else f"{sat_short}__{orig}"
                ops.append(
                    MoveOp(
                        file_id=c["id"],
                        file_name=c["name"],
                        mime_type=c["mimeType"],
                        source_parent_id=fid,
                        source_parent_name=disp,
                        dest_parent_id=misc_id,
                        new_name=new_name,
                    )
                )
    return ops


async def apply_consolidation_for_client(
    conn: asyncpg.Connection,
    drive,
    plan_row: dict,
    context: GuardianRunContext,
) -> dict[str, Any]:
    """Execute R3 (merge into existing canonical) for one client.

    Steps (in order):
        1. Confirm canonical_folder_id exists and has a 99_Misc subfolder.
        2. Enumerate satellites → build flat move plan.
        3. For each move: call Drive files.update (addParents/removeParents).
        4. After all moves succeed, trash each satellite root folder.
        5. Ensure clients.google_drive_folder_id points to canonical.
        6. Record one event per action.

    On dry_run: no Drive or DB calls, only synthetic events with status='dry_run'.

    Returns: summary dict with counts.
    """
    client_id = plan_row["client_id"]
    canonical_id = plan_row["canonical_folder_id"]
    misc_id = plan_row.get("canonical_misc_folder_id")
    assert canonical_id, "R3 requires canonical_folder_id"

    dry = context.config.dry_run
    ev = lambda **kw: GuardianEvent(  # noqa: E731
        invariant_id="I3_satellite_consolidation",
        run_id=context.run_id,
        dry_run=dry,
        client_id=client_id,
        **kw,
    )

    # If misc_id is missing from the plan (older audit), look it up now.
    if not misc_id:
        for ch in _drive_list_children(drive, canonical_id):
            if ch["mimeType"] == "application/vnd.google-apps.folder" and ch["name"] == "99_Misc":
                misc_id = ch["id"]
                break
        if not misc_id and not dry:
            # Create 99_Misc on the fly so consolidation has a destination.
            created = _drive_create_folder(drive, "99_Misc", canonical_id)
            misc_id = created["id"]
            await record_event(
                conn,
                ev(
                    action=GuardianAction.CREATE_SUBFOLDER,
                    target_type="folder",
                    target_id=misc_id,
                    status="success",
                    after_state={"name": "99_Misc", "parent": canonical_id},
                    notes="99_Misc was missing under canonical; created on-demand",
                ),
            )

    # Build move ops
    ops = plan_consolidation(drive, plan_row, canonical_id, misc_id or "")

    moved = 0
    errors = 0
    for op in ops:
        if context.op_count >= context.config.max_ops_per_client:
            await record_event(
                conn,
                ev(
                    action=GuardianAction.SKIP,
                    target_type="file",
                    target_id=op.file_id,
                    status="skipped",
                    notes=f"max_ops_per_client={context.config.max_ops_per_client} reached",
                ),
            )
            break
        if dry:
            await record_event(
                conn,
                ev(
                    action=GuardianAction.MOVE_FILE,
                    target_type="file",
                    target_id=op.file_id,
                    status="dry_run",
                    before_state={
                        "parent": op.source_parent_id,
                        "parent_name": op.source_parent_name,
                        "name": op.file_name,
                    },
                    after_state={"parent": op.dest_parent_id, "name": op.new_name},
                ),
            )
            context.bump_ops()
            continue
        try:
            _drive_move(drive, op.file_id, op.dest_parent_id, op.source_parent_id, op.new_name)
            await record_event(
                conn,
                ev(
                    action=GuardianAction.MOVE_FILE,
                    target_type="file",
                    target_id=op.file_id,
                    status="success",
                    before_state={
                        "parent": op.source_parent_id,
                        "parent_name": op.source_parent_name,
                        "name": op.file_name,
                    },
                    after_state={"parent": op.dest_parent_id, "name": op.new_name},
                ),
            )
            moved += 1
            context.bump_ops()
        except Exception as exc:  # noqa: BLE001
            errors += 1
            context.bump_errors()
            await record_event(
                conn,
                ev(
                    action=GuardianAction.MOVE_FILE,
                    target_type="file",
                    target_id=op.file_id,
                    status="error",
                    before_state={"parent": op.source_parent_id},
                    error_message=str(exc)[:500],
                ),
            )
            if context.error_count >= context.config.max_total_errors:
                logger.error("circuit-breaker tripped at %d errors", context.error_count)
                break

    # Move satellite roots to `_DA_TRASHARE_` (soft-delete, bypasses cross-domain trash 403).
    # The satellite must be already cleared of direct files (subfolders are OK — they go
    # along with the move and can be cleaned on a second pass).
    trashed = 0
    if not dry and errors == 0:
        client_label = f"client{plan_row.get('client_id','?')}"
        for sat in plan_row["satellites"]:
            try:
                remaining = _drive_list_children(drive, sat["id"])
                any_files = any(c["mimeType"] != "application/vnd.google-apps.folder" for c in remaining)
                if any_files:
                    await record_event(
                        conn,
                        ev(
                            action=GuardianAction.SKIP,
                            target_type="folder",
                            target_id=sat["id"],
                            status="skipped",
                            notes="satellite still has direct files — not moved to dumpster",
                        ),
                    )
                    continue
                _drive_move_to_dumpster(drive, sat["id"], label=client_label)
                await record_event(
                    conn,
                    ev(
                        action=GuardianAction.TRASH_FOLDER,
                        target_type="folder",
                        target_id=sat["id"],
                        status="success",
                        before_state={"name": sat["name"], "parent": sat.get("parent_id")},
                        notes=f"moved_to_dumpster parent={DA_TRASHARE_FOLDER_ID}",
                    ),
                )
                trashed += 1
            except Exception as exc:  # noqa: BLE001
                await record_event(
                    conn,
                    ev(
                        action=GuardianAction.TRASH_FOLDER,
                        target_type="folder",
                        target_id=sat["id"],
                        status="error",
                        error_message=str(exc)[:500],
                    ),
                )
    elif dry:
        for sat in plan_row["satellites"]:
            await record_event(
                conn,
                ev(
                    action=GuardianAction.TRASH_FOLDER,
                    target_type="folder",
                    target_id=sat["id"],
                    status="dry_run",
                    before_state={"name": sat["name"], "parent": sat.get("parent_id")},
                ),
            )

    # Ensure DB points to canonical
    if not dry:
        current = await conn.fetchval(
            "SELECT google_drive_folder_id FROM clients WHERE id = $1", client_id
        )
        if current != canonical_id:
            await conn.execute(
                "UPDATE clients SET google_drive_folder_id = $2 WHERE id = $1",
                client_id, canonical_id,
            )
            await record_event(
                conn,
                ev(
                    action=GuardianAction.UPDATE_DB_FOLDER_ID,
                    target_type="client",
                    target_id=str(client_id),
                    status="success",
                    before_state={"google_drive_folder_id": current},
                    after_state={"google_drive_folder_id": canonical_id},
                ),
            )
    else:
        current = await conn.fetchval(
            "SELECT google_drive_folder_id FROM clients WHERE id = $1", client_id
        )
        if current != canonical_id:
            await record_event(
                conn,
                ev(
                    action=GuardianAction.UPDATE_DB_FOLDER_ID,
                    target_type="client",
                    target_id=str(client_id),
                    status="dry_run",
                    before_state={"google_drive_folder_id": current},
                    after_state={"google_drive_folder_id": canonical_id},
                ),
            )

    return {
        "client_id": client_id,
        "dry_run": dry,
        "files_moved": moved,
        "folders_trashed": trashed,
        "move_ops_planned": len(ops),
        "errors": errors,
    }


async def apply_provision_and_consolidate(
    conn: asyncpg.Connection,
    drive,
    plan_row: dict,
    context: GuardianRunContext,
) -> dict[str, Any]:
    """Execute R4: create canonical folder + template, then consolidate.

    We pick the richest satellite (by total_files_recursive) as the "preferred"
    source; all others still contribute via the I3 walker. After provisioning,
    the function delegates to apply_consolidation_for_client with the freshly
    created canonical_folder_id and misc_id.
    """
    client_id = plan_row["client_id"]
    full_name = plan_row["full_name"]
    parent_id = context.config.individual_crm_id

    dry = context.config.dry_run
    ev = lambda **kw: GuardianEvent(  # noqa: E731
        invariant_id="I1_canonical_folder",
        run_id=context.run_id,
        dry_run=dry,
        client_id=client_id,
        **kw,
    )

    if dry:
        # Synthesize dry-run events for folder creation only — the consolidation
        # part can't be meaningfully dry-simulated until the canonical exists.
        await record_event(
            conn,
            ev(
                action=GuardianAction.CREATE_FOLDER,
                target_type="folder",
                target_id=f"dry_canonical_{client_id}",
                status="dry_run",
                after_state={"name": f"{client_id}_{full_name}", "parent": parent_id, "template_subfolders": len(STANDARD_SUBFOLDERS)},
            ),
        )
        # Also log what I3 would do
        synthetic_misc = f"dry_misc_{client_id}"
        plan_for_dry = dict(plan_row)
        plan_for_dry["canonical_folder_id"] = f"dry_canonical_{client_id}"
        plan_for_dry["canonical_misc_folder_id"] = synthetic_misc
        return await apply_consolidation_for_client(conn, drive, plan_for_dry, context)

    # Real run — create canonical
    provisioned = provision_canonical_folder(drive, client_id, full_name, parent_id)
    canonical_id = provisioned["root_id"]
    misc_id = provisioned["subfolders"]["99_Misc"]

    await record_event(
        conn,
        ev(
            action=GuardianAction.CREATE_FOLDER,
            target_type="folder",
            target_id=canonical_id,
            status="success",
            after_state={
                "name": provisioned["root_name"],
                "parent": parent_id,
                "template_subfolders": len(STANDARD_SUBFOLDERS),
                "misc_id": misc_id,
            },
        ),
    )

    # Update DB immediately so re-runs are safe
    await conn.execute(
        "UPDATE clients SET google_drive_folder_id = $2 WHERE id = $1",
        client_id, canonical_id,
    )

    # Now run consolidation with the freshly created canonical
    augmented = dict(plan_row)
    augmented["canonical_folder_id"] = canonical_id
    augmented["canonical_misc_folder_id"] = misc_id
    augmented["has_canonical"] = True

    result = await apply_consolidation_for_client(conn, drive, augmented, context)
    result["provisioned_canonical"] = canonical_id
    result["provisioned_misc"] = misc_id
    return result
