#!/usr/bin/env python3
"""Execute APOPTOSIS for Round 1 NB univoci.

Two modes:
  --dry-run  → write preview to /tmp + ZERO mcp calls
  --apply    → rename in NLM, regenerate _registry_data.py after EACH transition

Idempotency: skip NB whose live title already starts with `[ARCHIVED-...]`.
Crash-safety: persist after each transition, so SIGKILL mid-loop loses at most 1 entry.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "data" / "nb_round1_candidates_2026-05-07.json"
REGISTRY_TARGET = REPO / "mata_garuda" / "_registry_data.py"
PREVIEW_PATH = Path("/tmp/apoptosis-preview-2026-05-07.md")
EXPORT_DIR = REPO.parent.parent / "research" / "nb-archive"
DECISION_MATRIX_PATH = (
    REPO.parent.parent / "docs" / "nb-lifecycle" / "round1-19-ambiguous-decisions-2026-05-07.md"
)
AUDIT_LOG = EXPORT_DIR / "audit_log.md"
TODAY = "2026-05-07"
ARCHIVED_PREFIX = f"[ARCHIVED-{TODAY}]"
EXPORTED_PREFIX = f"[EXPORTED-{TODAY}]"


# --- helpers ---------------------------------------------------------------

def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if not s:
        return "untitled"
    return s[:80]


def export_filename(uuid: str, title: str) -> str:
    return f"{uuid[:8]}-{slugify(title)}-{TODAY}.md"


def render_export(uuid: str, title: str, sources: list[dict[str, Any]], summary: str) -> str:
    """Build the playbook export markdown."""
    front = ["---"]
    front.append(f"uuid: {uuid}")
    front.append(f"title: {json.dumps(title, ensure_ascii=False)}")
    front.append(f"exported_at: {dt.datetime.now(dt.timezone.utc).isoformat()}")
    url_sources = [s for s in sources if s.get("type") == "url" and s.get("url")]
    if url_sources:
        urls = " ".join(s["url"] for s in url_sources)
        front.append(f"reimport_command: nlm source add {uuid} {urls}")
    front.append("---")
    body = ["", "## Summary", "", summary, ""]
    if sources:
        body.append("## Sources")
        for s in sources:
            if s.get("type") == "url":
                body.append(f"- [URL] {s.get('url', '')}")
            else:
                body.append(f"- [TEXT] {s.get('snippet', '')[:200]}")
    return "\n".join(front + body)


def telegram_alert(msg: str) -> None:
    # Reuse audit_nb_live's telegram path (avoid duplication).
    sys.path.insert(0, str(Path(__file__).parent))
    import audit_nb_live as audit
    audit.telegram_alert(msg)


# --- nlm CLI wrappers (used only in --apply) -------------------------------

def _run(cmd: list[str], timeout: int = 30) -> tuple[str, int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return proc.stdout, proc.returncode, proc.stderr


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


def nlm_get_sources(uuid: str) -> list[dict[str, Any]]:
    out, rc, _ = _run(["nlm", "source", "list", uuid, "--json"])
    if rc != 0:
        return []
    try:
        payload = json.loads(out)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and "value" in payload:
        v = payload["value"]
        if isinstance(v, list):
            return v
    return []


def nlm_rename(uuid: str, new_name: str) -> bool:
    _, rc, _ = _run(["nlm", "notebook", "rename", uuid, new_name])
    return rc == 0


# --- registry persistence --------------------------------------------------

def persist_transition(uuid: str, status: str) -> None:
    """Patch the manifest in place + re-run the regenerator."""
    manifest = json.loads(MANIFEST.read_text())
    for c in manifest["candidates"]:
        if c["uuid"] == uuid:
            c["proposed_action"] = status  # KILL | EXPORT | ORPHAN_REVIEW
            break
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    overrides = {uuid: status}
    rebuilder = REPO / "scripts" / "build_registry_from_manifest.py"
    subprocess.run(
        [sys.executable, str(rebuilder), json.dumps(overrides)], check=True
    )


def append_audit_log_local(uuid: str, action: str, note: str) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now(dt.timezone.utc).isoformat()
    with AUDIT_LOG.open("a") as f:
        f.write(f"- {ts} | {uuid} | {action} | {note}\n")


# --- dry-run preview -------------------------------------------------------

def render_preview(pending: list[str]) -> str:
    lines = [
        f"# APOPTOSIS dry-run preview — {TODAY}",
        "",
        f"Pending: {len(pending)} NB",
        "",
        "## NBs that will be renamed",
        "",
    ]
    for u in pending:
        lines.append(f"- `{u}` → `[ARCHIVED-{TODAY}] <name>` or `[EXPORTED-{TODAY}] <name>`")
    lines += ["", "## To apply", "", "```bash", "python apps/mata-garuda/scripts/execute_apoptosis.py --apply", "```", ""]
    return "\n".join(lines)


# --- decision matrix doc ---------------------------------------------------

def generate_decision_matrix(review_entries: list[dict], out_path: Path) -> Path:
    """Generate docs/nb-lifecycle/round1-19-ambiguous-decisions-<date>.md."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    by_cluster: dict[str, list[dict]] = {}
    for e in review_entries:
        by_cluster.setdefault(e["cluster"], []).append(e)

    lines = [
        f"# Round 1 — 19 ambiguous NB decisions ({TODAY})",
        "",
        f"Total entries pending Zero approval: **{len(review_entries)}**",
        "",
        "| Cluster | Count |",
        "|---|---|",
    ]
    for cluster, items in by_cluster.items():
        lines.append(f"| {cluster} | {len(items)} |")
    lines.append("")

    for cluster, items in by_cluster.items():
        lines += [f"## Cluster: {cluster}", ""]
        for e in items:
            lines += [
                f"### `{e['uuid']}` — {e.get('name','(unknown)')}",
                "",
                f"- source_count_live: {e.get('source_count_live')}",
                f"- peer_uuids: {e.get('peer_uuids', [])}",
                "",
                f"**Zero decision ({TODAY}):** _____________________________",
                "",
            ]

    lines += [
        "## Follow-up — `NLM_NOTEBOOKS` callsites pending migration",
        "",
        "This PR keeps these consumers on the compat shim. Future PR should migrate them",
        "to `notebook_registry.NOTEBOOK_REGISTRY` directly:",
        "",
        "- `apps/mata-garuda/mata_garuda/agents/sentinel_actor.py`",
        "- `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py`",
        "- `apps/mata-garuda/mata_garuda/agents/nlm_expander_agent.py`",
        "- `apps/backend-rag/backend/tools/health_tools.py`",
        "",
        "Total references: ~9. Migration is a pure refactor (no behavior change required).",
        "",
    ]
    out_path.write_text("\n".join(lines))
    return out_path


# --- main loop -------------------------------------------------------------

def run_apoptosis(pending: list[str], dry_run: bool) -> int:
    """Iterate `pending` UUIDs and rename / preview each."""
    if dry_run:
        PREVIEW_PATH.write_text(render_preview(pending))
        print(f"dry-run preview at {PREVIEW_PATH}")
        return 0
    failed = 0
    for uuid in pending:
        title = nlm_get_title(uuid) or ""
        if title.startswith(("[ARCHIVED-", "[EXPORTED-")):
            append_audit_log_local(uuid, "SKIP_ALREADY_ARCHIVED", title)
            continue
        new_name = f"{ARCHIVED_PREFIX} {title}"  # Cluster decides prefix in real version
        ok = nlm_rename(uuid, new_name)
        if ok:
            persist_transition(uuid, "APOPTOSIS_DONE")
            append_audit_log_local(uuid, "APOPTOSIS_DONE", new_name)
        else:
            persist_transition(uuid, "RENAME_FAIL")
            failed += 1
            append_audit_log_local(uuid, "RENAME_FAIL", title)
    if failed:
        telegram_alert(f"NB-LIFECYCLE: {failed}/{len(pending)} APOPTOSIS renames failed (re-run will retry)")
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.dry_run and not args.apply:
        print("ERROR: pick --dry-run or --apply", file=sys.stderr)
        return 1
    if args.dry_run and args.apply:
        print("ERROR: pick exactly one of --dry-run / --apply", file=sys.stderr)
        return 1

    # Load pending UUIDs from registry.
    sys.path.insert(0, str(REPO))
    from mata_garuda.notebook_registry import get_by_status
    pending = [e.uuid for e in get_by_status("KILL_PENDING")] + [
        e.uuid for e in get_by_status("EXPORT_PENDING")
    ]

    rc = run_apoptosis(pending, dry_run=args.dry_run)

    # In --apply mode, also (re-)generate the decision matrix.
    if args.apply:
        review = [
            {
                "uuid": e.uuid, "name": e.name, "cluster": e.cluster,
                "source_count_live": None, "peer_uuids": list(e.peer_uuids),
            }
            for e in get_by_status("ORPHAN_REVIEW")
        ]
        generate_decision_matrix(review, DECISION_MATRIX_PATH)

    return rc


if __name__ == "__main__":
    sys.exit(main())
