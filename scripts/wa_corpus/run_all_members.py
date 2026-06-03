"""Daily driver: reconcile every team member's WhatsApp chats into their NB.

Reads a members config (JSON) mapping each team member to their email, main
phone line, and dedicated NB id. Runs the Reconciler per member and prints a
combined digest (one line per member + totals). The shell wrapper turns the
totals into a Telegram message.

Config file (default ~/.config/nuzantara/wa_corpus_members.json):
[
  {"email": "surya@balizero.com",  "team_phone": "+628133946856",  "nb_id": "<NB-Surya>"},
  {"email": "adit@balizero.com",   "team_phone": "+628213454725",  "nb_id": "<NB-Adit>"},
  ...
]

Members whose nb_id is empty/missing are skipped with a warning (the NB has not
been bootstrapped yet — create it once with `nlm notebook create`).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import psycopg2

from scripts.wa_corpus.config import DB_DSN
from scripts.wa_corpus.reconciler import Reconciler

DEFAULT_CONFIG = os.path.expanduser("~/.config/nuzantara/wa_corpus_members.json")


def load_members(path: str) -> list[dict]:
    if not os.path.exists(path):
        print(f"[wa-corpus] members config not found: {path}", file=sys.stderr)
        return []
    with open(path) as f:
        return json.load(f)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--limit", type=int, default=None, help="cap counterparts per member")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    members = load_members(args.config)
    if not members:
        print("[wa-corpus] no members to process")
        return 1

    conn = psycopg2.connect(DB_DSN)
    totals = {
        "created": 0, "renamed": 0, "updated": 0, "skipped": 0,
        "archived": 0, "recap_written": 0, "unverified": 0, "errors": 0,
    }
    lines = []
    for m in members:
        nb_id = (m.get("nb_id") or "").strip()
        if not nb_id:
            lines.append(f"{m.get('email')}: SKIPPED (no nb_id — bootstrap NB first)")
            continue
        rec = Reconciler(conn, nb_id, dry_run=args.dry_run)
        dg = rec.reconcile_member(m["email"], m["team_phone"], limit=args.limit)
        lines.append(dg.line())
        totals["created"] += dg.created
        totals["renamed"] += dg.renamed
        totals["updated"] += dg.updated
        totals["skipped"] += dg.skipped
        totals["archived"] += dg.archived
        totals["recap_written"] += dg.recap_written
        totals["unverified"] += dg.unverified
        totals["errors"] += len(dg.errors)

    print("WA-CORPUS daily reconcile" + (" [DRY-RUN]" if args.dry_run else ""))
    for ln in lines:
        print("  " + ln)
    print(
        "TOTAL "
        + " ".join(f"{k}={v}" for k, v in totals.items())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
