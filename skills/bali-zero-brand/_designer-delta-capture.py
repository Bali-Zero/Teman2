#!/usr/bin/env python3
"""Designer-delta diff capture — the gold-standard learning signal.

Damar's workflow when publishing a carousel:
1. Open Canva design from queue.
2. (Optional) Edit any slide.
3. Run this script: `python3 _designer-delta-capture.py <queue_id>`.
4. Script reads pre-edit Canva snapshot from drafted carousel + current Canva state,
   diffs them, writes structured JSON to queue.json `designer_override_diff`.
5. Damar publishes to IG, runs `--mark-published <queue_id> <ig_url>`.

Why this matters (Codex review FLAW MEDIUM):
- Reflexion-style post-mortem requires `published_vs_draft` diffs.
- Without structured capture, weekly Reflexion produces "self-justification noise" not lessons.
- This script gives the orchestrator concrete signal: what Damar trusted, what he changed.

The diff is per-slide:
- text changes (heading, body, subheading) → voice lesson
- image swap → image lesson (cliché flagged?)
- layout swap → layout lesson (closed-pool family inadequate?)
- slide deletion → narrative arc lesson
- slide insertion → narrative arc lesson
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

QUEUE_PATH = Path.home() / "Desktop/nuzantara/apps/war-room/output/queue/human-review-queue.json"


def load_queue():
    if not QUEUE_PATH.exists():
        print(f"Queue not found at {QUEUE_PATH}", file=sys.stderr)
        sys.exit(1)
    return json.loads(QUEUE_PATH.read_text())


def save_queue(queue):
    QUEUE_PATH.write_text(json.dumps(queue, indent=2))


def find_item(queue, item_id):
    for it in queue:
        if it["id"] == item_id:
            return it
    return None


def fetch_canva_state(design_id):
    """Read current Canva design state via MCP. Returns slide-by-slide JSON.

    NOTE: This requires running inside a Claude Code session with mcp__claude_ai_Canva__*
    tools available. Standalone CLI execution will fail. Suggested usage: invoke this script
    from the wr2-design-architect orchestrator OR via `claude -p` subprocess.
    """
    # Stub: in real impl, call mcp__claude_ai_Canva__get-design-content(design_id)
    # and extract per-page text + image elements.
    return {
        "design_id": design_id,
        "slides": [],
        "_stub": "Run via orchestrator with Canva MCP available",
    }


def diff_slides(draft_slides, published_slides):
    """Compute structured diff between draft and published states."""
    diff = {
        "slides_modified": [],
        "modifications": [],
        "slides_deleted": [],
        "slides_inserted": [],
    }

    draft_by_index = {s.get("index"): s for s in draft_slides}
    pub_by_index = {s.get("index"): s for s in published_slides}

    all_indices = sorted(set(draft_by_index) | set(pub_by_index))

    for idx in all_indices:
        d = draft_by_index.get(idx)
        p = pub_by_index.get(idx)

        if d and not p:
            diff["slides_deleted"].append(idx)
            continue
        if p and not d:
            diff["slides_inserted"].append(idx)
            continue

        slide_changes = []
        for field in ("heading", "subheading", "body", "image_url", "layout_family"):
            if d.get(field) != p.get(field):
                slide_changes.append({
                    "field": field,
                    "before": d.get(field),
                    "after": p.get(field),
                })
        if slide_changes:
            diff["slides_modified"].append(idx)
            for ch in slide_changes:
                diff["modifications"].append({"slide": idx, **ch})

    return diff


def categorize_changes(diff):
    """Annotate the diff with high-level categories for Reflexion synthesis."""
    categories = set()
    for mod in diff["modifications"]:
        f = mod["field"]
        if f in ("heading", "subheading", "body"):
            categories.add("voice")
        elif f == "image_url":
            categories.add("image")
        elif f == "layout_family":
            categories.add("layout")
    if diff["slides_deleted"] or diff["slides_inserted"]:
        categories.add("narrative-arc")
    return sorted(categories)


def capture(item_id, reason_tag=None, free_text=None):
    queue = load_queue()
    item = find_item(queue, item_id)
    if not item:
        print(f"Queue item {item_id} not found.", file=sys.stderr)
        sys.exit(1)

    if item["state"] not in ("drafted", "reviewed"):
        print(f"Item state is {item['state']}; cannot capture delta.", file=sys.stderr)
        sys.exit(1)

    draft_slides_path = Path(item["carousel_path"]).expanduser() / "slides.json"
    if not draft_slides_path.exists():
        print(f"Draft slides.json missing at {draft_slides_path}", file=sys.stderr)
        sys.exit(1)
    draft_doc = json.loads(draft_slides_path.read_text())
    draft_slides = draft_doc.get("slides", [])

    canva_state = fetch_canva_state(item["canva_design_id"])
    if canva_state.get("_stub"):
        print("Canva MCP not available in CLI mode; cannot fetch live state.", file=sys.stderr)
        print("Run this script from wr2-design-architect orchestrator instead.", file=sys.stderr)
        sys.exit(2)

    published_slides = canva_state.get("slides", [])

    diff = diff_slides(draft_slides, published_slides)
    categories = categorize_changes(diff)
    has_changes = bool(diff["modifications"] or diff["slides_deleted"] or diff["slides_inserted"])

    item["state"] = "reviewed"
    item["damar_action_at"] = datetime.now(timezone.utc).isoformat()
    item["damar_notes"] = free_text
    item["state_history"].append({
        "state": "reviewed",
        "at": item["damar_action_at"],
        "by": "damar",
        "notes": reason_tag,
    })
    item["designer_override_diff"] = {
        **diff,
        "categories": categories,
        "has_changes": has_changes,
        "captured_at": item["damar_action_at"],
    }

    save_queue(queue)
    print(f"Delta captured. Categories: {categories}. has_changes={has_changes}")
    print(f"Modifications: {len(diff['modifications'])}, deletions: {len(diff['slides_deleted'])}, insertions: {len(diff['slides_inserted'])}")


def mark_published(item_id, ig_url):
    queue = load_queue()
    item = find_item(queue, item_id)
    if not item:
        print(f"Queue item {item_id} not found.", file=sys.stderr)
        sys.exit(1)

    if item["state"] != "reviewed":
        print(f"Item state is {item['state']}; expected 'reviewed' before mark-published.", file=sys.stderr)
        sys.exit(1)

    has_edits = bool(item.get("designer_override_diff", {}).get("has_changes"))
    new_state = "published_with_edits" if has_edits else "published"

    now = datetime.now(timezone.utc).isoformat()
    item["state"] = new_state
    item["instagram_post_url"] = ig_url
    item["instagram_published_at"] = now
    item["state_history"].append({
        "state": new_state,
        "at": now,
        "by": "damar",
    })
    save_queue(queue)
    print(f"Marked {item_id} as {new_state}.")


def mark_rejected(item_id, reason_tag, free_text):
    queue = load_queue()
    item = find_item(queue, item_id)
    if not item:
        print(f"Queue item {item_id} not found.", file=sys.stderr)
        sys.exit(1)

    valid_tags = {"factually-wrong", "tone-off", "image-bad", "topic-stale",
                  "legal-risk", "client-conflict", "other"}
    if reason_tag not in valid_tags:
        print(f"Invalid reason tag. Must be one of: {sorted(valid_tags)}", file=sys.stderr)
        sys.exit(1)

    now = datetime.now(timezone.utc).isoformat()
    item["state"] = "rejected"
    item["damar_action_at"] = now
    item["damar_notes"] = f"[{reason_tag}] {free_text or ''}".strip()
    item["state_history"].append({
        "state": "rejected",
        "at": now,
        "by": "damar",
        "reason_tag": reason_tag,
    })
    save_queue(queue)
    print(f"Marked {item_id} as rejected ({reason_tag}).")


def main():
    parser = argparse.ArgumentParser(description="Capture designer-delta for WR2 carousels")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_capture = sub.add_parser("capture", help="Capture diff before publishing")
    p_capture.add_argument("item_id")
    p_capture.add_argument("--reason-tag", help="Optional categorical tag for review")
    p_capture.add_argument("--notes", help="Optional free-text notes")

    p_pub = sub.add_parser("mark-published", help="Mark as published after IG post")
    p_pub.add_argument("item_id")
    p_pub.add_argument("ig_url")

    p_rej = sub.add_parser("mark-rejected", help="Mark as rejected (no publish)")
    p_rej.add_argument("item_id")
    p_rej.add_argument("reason_tag", choices=["factually-wrong", "tone-off", "image-bad",
                                              "topic-stale", "legal-risk", "client-conflict", "other"])
    p_rej.add_argument("--notes")

    args = parser.parse_args()

    if args.cmd == "capture":
        capture(args.item_id, args.reason_tag, args.notes)
    elif args.cmd == "mark-published":
        mark_published(args.item_id, args.ig_url)
    elif args.cmd == "mark-rejected":
        mark_rejected(args.item_id, args.reason_tag, args.notes)


if __name__ == "__main__":
    main()
