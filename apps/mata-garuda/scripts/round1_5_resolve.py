#!/usr/bin/env python3
"""Round 1.5: resolve 19 ambiguous NBs from PR #497 decision matrix.

Actions per Zero (2026-05-07):
- 4 MERGE: copy sources to target NB, then rename source NB [MERGED-INTO-X]
  * Digital Sovereignty (150 src) → NB-9 Research Lab
  * Claude Code optimization (128) + World Models (49) + Nexus Palantir (44)
    → NB-INTEL-AIResearch (already ACTIVE in registry)
- 6 DELETE live: rename to [ARCHIVED-DELETE-2026-05-07] (rename only, never API delete)
- 1 STUB-CHECK: probe Foreign Investment stub (probably not live)
- 8 STUB cleanup: remove orphan_unclear stub UUIDs from manifest (no live action)

Operates via nlm CLI (CLI-only invariant). Async source-add (no --wait) to keep
runtime ≤30 min for 371 source re-adds.

Output:
- research/nb-archive/audit_log.md (append)
- apps/mata-garuda/data/nb_round1_candidates_2026-05-07.json (manifest update)
- regenerate _registry_data.py via build_registry_from_manifest.py
- update docs/nb-lifecycle/round1-19-ambiguous-decisions-2026-05-07.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
WORKTREE = REPO_ROOT  # this script lives inside the worktree
MANIFEST = WORKTREE / "apps" / "mata-garuda" / "data" / "nb_round1_candidates_2026-05-07.json"
AUDIT_LOG = WORKTREE / "research" / "nb-archive" / "audit_log.md"
DECISION_DOC = WORKTREE / "docs" / "nb-lifecycle" / "round1-19-ambiguous-decisions-2026-05-07.md"
REBUILDER = WORKTREE / "apps" / "mata-garuda" / "scripts" / "build_registry_from_manifest.py"
TODAY = "2026-05-07"
DELETE_PREFIX = f"[ARCHIVED-DELETE-{TODAY}]"


# -----------------------------------------------------------------------------
# Decisions table (Zero 2026-05-07)
# -----------------------------------------------------------------------------

NB9 = "d2a05271-2f65-4c02-a44d-eefeb7c7f7cd"  # NB-9 Research Lab
AIR = "dc5d01cd-e99f-4c8f-aae4-75060b43d0de"  # NB-INTEL-AIResearch (already ACTIVE)


# (uuid, action, target_or_label)
ACTIONS: list[tuple[str, str, str]] = [
    # MERGE → NB-9
    ("201b4b94-deda-40a9-9fcb-0e67a3f81e52", "MERGE", NB9),  # Digital Sovereignty
    # MERGE → NB-INTEL-AIResearch
    ("50396b3e-b2f9-4903-8df5-65c2b9709eba", "MERGE", AIR),  # Claude Code optimization
    ("917a1300-61ac-4fdb-8d94-8a42503c0442", "MERGE", AIR),  # World Models
    ("d97ff70b-9c14-42a3-8813-5416039b24f7", "MERGE", AIR),  # Nexus Palantir
    # DELETE
    ("4a8f3162-6f63-4876-9fe9-642dd9ae0606", "DELETE", "Analisi Video AI Agency"),
    ("46b4dfe0-2be9-4fe4-97cd-3d44ef28a8ab", "DELETE", "NB-NLM-ELEVATION"),
    ("552072ab-7f09-4cda-a13c-0988f414d36d", "DELETE", "NB-SUBHI Onboarding"),
    ("9a866adc-988c-407f-9920-60dabf5ab164", "DELETE", "NB-SUBHI Misi"),
    ("da94d615-0140-4b46-8484-f24a423a91ce", "DELETE", "NB-CRM-VIP"),
    ("9530b58d-cb7b-4bda-b5c2-c68e723b8118", "DELETE", "Indonesia Restaurant"),
    # STUB-CHECK
    ("aaaaaaaa-aaaa-aaaa-aaaa-aaaa00000036", "STUB_CHECK", "Foreign Investment stub"),
]

# 8 orphan_unclear stubs — manifest cleanup only (no live action)
ORPHAN_STUB_UUIDS = [f"aaaaaaaa-aaaa-aaaa-aaaa-aaaa{i:08d}" for i in range(18, 26)]


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _run(cmd: list[str], timeout: int = 60) -> tuple[str, int, str]:
    """Subprocess wrapper. Returns (stdout, returncode, stderr)."""
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return proc.stdout, proc.returncode, proc.stderr


def append_audit_log(uuid: str, action: str, note: str = "") -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now(dt.timezone.utc).isoformat()
    with AUDIT_LOG.open("a") as f:
        f.write(f"- {ts} | {uuid} | {action} | {note}\n")


def nlm_get_title(uuid: str) -> str | None:
    out, rc, _ = _run(["nlm", "notebook", "get", uuid, "--json"])
    if rc != 0:
        return None
    try:
        payload = json.loads(out)
    except json.JSONDecodeError:
        return None
    if "value" in payload and isinstance(payload["value"], dict):
        return payload["value"].get("title")
    return None


def nlm_rename(uuid: str, new_name: str) -> bool:
    _, rc, _ = _run(["nlm", "notebook", "rename", uuid, new_name])
    return rc == 0


def nlm_source_list(uuid: str) -> list[dict]:
    out, rc, _ = _run(["nlm", "source", "list", uuid, "--json"])
    if rc != 0:
        return []
    try:
        payload = json.loads(out)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return payload
    return []


def nlm_source_content(source_uuid: str) -> str | None:
    """Get raw text content of a source (used for generated_text type).

    Signature: `nlm source content SOURCE_ID` (notebook_id NOT required —
    source IDs are globally unique in NotebookLM).
    """
    out, rc, err = _run(["nlm", "source", "content", source_uuid], timeout=30)
    if rc != 0:
        return None
    return out.strip() if out else None


def nlm_source_add_url(target_nb: str, url: str, title: str | None = None) -> bool:
    cmd = ["nlm", "source", "add", target_nb, "--url", url]
    if title:
        cmd += ["--title", title]
    out, rc, err = _run(cmd, timeout=120)
    if rc != 0:
        # Hint: rate-limit / duplicate / blocked URL — append to log but continue.
        return False
    return True


def nlm_source_add_text(target_nb: str, text: str, title: str) -> bool:
    cmd = ["nlm", "source", "add", target_nb, "--text", text, "--title", title]
    out, rc, err = _run(cmd, timeout=120)
    return rc == 0


# -----------------------------------------------------------------------------
# MERGE
# -----------------------------------------------------------------------------

def do_merge(source_nb: str, target_nb: str) -> dict:
    """Copy all sources from source_nb to target_nb, then rename source_nb."""
    sources = nlm_source_list(source_nb)
    if not sources:
        append_audit_log(source_nb, "MERGE_SKIP", f"target={target_nb} reason=no_sources")
        return {"copied": 0, "failed": 0, "renamed": False}

    src_title = nlm_get_title(source_nb) or "?"
    print(f"  merge {source_nb[:8]}… ({len(sources)} src) → {target_nb[:8]}…")

    copied = 0
    failed = 0
    for i, s in enumerate(sources, start=1):
        stype = s.get("type", "")
        url = s.get("url")
        title = s.get("title", "")[:200]
        if url:
            ok = nlm_source_add_url(target_nb, url, title=title)
        elif stype == "generated_text":
            text = nlm_source_content(s["id"])
            if text:
                ok = nlm_source_add_text(target_nb, text, title=title or "untitled")
            else:
                ok = False
        else:
            ok = False
        if ok:
            copied += 1
        else:
            failed += 1
            append_audit_log(
                source_nb,
                "MERGE_SOURCE_FAIL",
                f"target={target_nb} source_id={s['id']} type={stype} title={title[:80]}",
            )
        if i % 25 == 0:
            print(f"    progress {i}/{len(sources)} (copied={copied} failed={failed})")
        time.sleep(0.5)  # gentle throttle

    # Rename source NB to mark merge done
    new_name = f"[MERGED-INTO-{target_nb[:8]}-{TODAY}] {src_title}"
    renamed = nlm_rename(source_nb, new_name)
    append_audit_log(
        source_nb,
        "MERGE_DONE",
        f"target={target_nb} copied={copied}/{len(sources)} renamed={renamed}",
    )
    return {"copied": copied, "failed": failed, "renamed": renamed, "total": len(sources)}


# -----------------------------------------------------------------------------
# DELETE
# -----------------------------------------------------------------------------

def do_delete(source_nb: str, label: str) -> dict:
    """Rename a NB to [ARCHIVED-DELETE-...] (never API delete)."""
    title = nlm_get_title(source_nb)
    if title is None:
        append_audit_log(source_nb, "DELETE_SKIP", f"label={label} reason=not_found_live")
        return {"renamed": False, "label": label, "live": False}
    new_name = f"{DELETE_PREFIX} {title}"
    if title.startswith("[ARCHIVED-DELETE-") or title.startswith("[ARCHIVED-") or title.startswith("[EXPORTED-"):
        append_audit_log(source_nb, "DELETE_SKIP_ALREADY_PREFIXED", title)
        return {"renamed": False, "label": label, "live": True, "skip_reason": "already_prefixed"}
    ok = nlm_rename(source_nb, new_name)
    append_audit_log(source_nb, "DELETE_RENAMED" if ok else "DELETE_FAIL", new_name)
    return {"renamed": ok, "label": label, "live": True, "new_name": new_name}


def do_stub_check(source_nb: str, label: str) -> dict:
    """Verify if a stub UUID corresponds to anything live; classify accordingly."""
    title = nlm_get_title(source_nb)
    if title is None:
        append_audit_log(source_nb, "STUB_NOT_LIVE", f"label={label}")
        return {"live": False, "label": label}
    # Unexpectedly live: treat as DELETE
    return do_delete(source_nb, label)


# -----------------------------------------------------------------------------
# Manifest update
# -----------------------------------------------------------------------------

def update_manifest(merge_done: list[str], delete_done: list[str], cleanup_uuids: list[str]) -> None:
    """Mark merged/deleted in manifest + remove cleanup entries."""
    manifest = json.loads(MANIFEST.read_text())
    new_candidates = []
    for c in manifest["candidates"]:
        uuid = c["uuid"]
        if uuid in cleanup_uuids:
            continue  # drop entry entirely
        if uuid in merge_done:
            c["proposed_action"] = "MERGED"
        elif uuid in delete_done:
            c["proposed_action"] = "DELETED"
        new_candidates.append(c)
    manifest["candidates"] = new_candidates
    manifest["candidates_count"] = len(new_candidates)
    # Update clusters_summary
    from collections import Counter
    counts = Counter(c["cluster"] for c in new_candidates)
    manifest["clusters_summary"] = {
        k: counts.get(k, 0) for k in (
            "placeholder_empty", "playbook_artifact", "orphan_unclear",
            "research_heavy", "subhi_merge", "zero_value_orphan",
        )
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"  manifest: {len(new_candidates)} entries (was 36, removed {36 - len(new_candidates)})")


def regen_registry() -> None:
    proc = subprocess.run([sys.executable, str(REBUILDER)], capture_output=True, text=True)
    print(f"  registry regen: rc={proc.returncode}")
    if proc.stdout:
        print(f"    {proc.stdout.strip()}")


# -----------------------------------------------------------------------------
# Decision doc update
# -----------------------------------------------------------------------------

def update_decision_doc(results: dict) -> None:
    """Fill in Zero decision lines in the decision matrix doc."""
    if not DECISION_DOC.exists():
        return
    text = DECISION_DOC.read_text()
    for uuid, outcome in results.items():
        # Match the Zero decision line that follows this UUID
        marker = f"`{uuid}`"
        idx = text.find(marker)
        if idx < 0:
            continue
        # Find the unfilled decision line after this marker
        deco_marker = f"**Zero decision ({TODAY}):** _____________________________"
        deco_idx = text.find(deco_marker, idx)
        if deco_idx < 0:
            continue
        replacement = f"**Zero decision ({TODAY}):** {outcome}"
        text = text[:deco_idx] + replacement + text[deco_idx + len(deco_marker):]
    DECISION_DOC.write_text(text)
    print(f"  decision doc updated")


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="preview only, no NLM action")
    parser.add_argument("--apply", action="store_true", help="execute against live NLM")
    args = parser.parse_args()
    if not args.dry_run and not args.apply:
        print("ERROR: pick --dry-run or --apply", file=sys.stderr)
        return 1

    print(f"=== R1.5 resolve {'(dry-run)' if args.dry_run else '(apply)'} ===")
    print(f"  {sum(1 for _, a, _ in ACTIONS if a == 'MERGE')} MERGE")
    print(f"  {sum(1 for _, a, _ in ACTIONS if a == 'DELETE')} DELETE")
    print(f"  {sum(1 for _, a, _ in ACTIONS if a == 'STUB_CHECK')} STUB_CHECK")
    print(f"  {len(ORPHAN_STUB_UUIDS)} orphan stub manifest cleanup")
    print()
    if args.dry_run:
        print("DRY RUN — no NLM calls. Re-run with --apply to execute.")
        return 0

    merge_done: list[str] = []
    delete_done: list[str] = []
    decision_lines: dict[str, str] = {}

    for uuid, action, target in ACTIONS:
        if action == "MERGE":
            r = do_merge(uuid, target)
            if r["renamed"]:
                merge_done.append(uuid)
                decision_lines[uuid] = f"MERGE → {target[:8]}… (copied {r['copied']}/{r['total']})"
            else:
                decision_lines[uuid] = f"MERGE → {target[:8]}… FAILED ({r['failed']} src failed)"
        elif action == "DELETE":
            r = do_delete(uuid, target)
            if r["renamed"]:
                delete_done.append(uuid)
                decision_lines[uuid] = f"DELETE — renamed {DELETE_PREFIX}"
            else:
                decision_lines[uuid] = f"DELETE — already prefixed or not live"
        elif action == "STUB_CHECK":
            r = do_stub_check(uuid, target)
            if r.get("live"):
                if r.get("renamed"):
                    delete_done.append(uuid)
                    decision_lines[uuid] = f"STUB-LIVE → DELETE renamed {DELETE_PREFIX}"
                else:
                    decision_lines[uuid] = "STUB-LIVE — could not rename"
            else:
                decision_lines[uuid] = "STUB-NOT-LIVE — manifest cleanup"

    # 8 orphan_unclear stubs → decision doc fill
    for uuid in ORPHAN_STUB_UUIDS:
        decision_lines[uuid] = "STUB — manifest cleanup (no live entry)"

    cleanup_uuids = list(ORPHAN_STUB_UUIDS)
    # If Foreign Investment stub also not live, cleanup it too
    fi_stub = "aaaaaaaa-aaaa-aaaa-aaaa-aaaa00000036"
    if fi_stub in decision_lines and "NOT-LIVE" in decision_lines[fi_stub]:
        cleanup_uuids.append(fi_stub)

    update_manifest(merge_done, delete_done, cleanup_uuids)
    regen_registry()
    update_decision_doc(decision_lines)

    print()
    print(f"=== R1.5 done ===")
    print(f"  merge_done: {len(merge_done)}")
    print(f"  delete_done: {len(delete_done)}")
    print(f"  manifest cleaned up: {len(cleanup_uuids)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
