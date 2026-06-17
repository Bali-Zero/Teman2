#!/usr/bin/env python3
"""S7 CRM Yield — PII-safe local pitch drafter.

Connects the 1,450 active-universe CRM clients to revenue signals and drafts
WhatsApp outreach pitches *entirely on-machine*. Reads client PII (names,
expiry dates, nationality, contact) directly from the read-only Postgres role
and feeds it to a LOCAL Ollama model. NOTHING with PII ever leaves the machine.

HARD PRIVACY CONTRACT (UU PDP / SYMBIOSIS Law 2):
  - DB access: read-only role `nuzantara_readonly` via pg-proxy localhost:15432.
  - Drafting LLM: Ollama qwen3.5:9b LOCAL only. NEVER OpenAI/Anthropic/Gemini.
  - PII (names, passport, phone) is written ONLY to a local staging dir under
    $HOME (gitignored, outside the repo tree). It is NEVER printed to stdout
    and NEVER committed.
  - stdout/logs carry ONLY client_id + aggregate counts (the privacy log rule).
  - This script SENDS NOTHING. It produces drafts for the ops team to review
    and send manually (SYMBIOSIS Law 5).

Usage:
  python scripts/s7_yield_draft_local.py --segment S1 --limit 10
  python scripts/s7_yield_draft_local.py --all --limit 5        # all segments
  python scripts/s7_yield_draft_local.py --segment S1 --dry-run  # no Ollama, list only

Exit codes: 0 ok · 2 Ollama down · 3 DB unreachable · 4 bad args
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# --- config ---------------------------------------------------------------
PSQL = os.environ.get("PSQL_BIN", "/opt/homebrew/bin/psql")
DSN = "postgresql://nuzantara_readonly@127.0.0.1:15432/nuzantara_rag?sslmode=disable"
KEYCHAIN_SERVICE = "nuzantara-postgres-readonly"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = os.environ.get("S7_OLLAMA_MODEL", "qwen3.5:9b")
STAGING = Path(os.environ.get("S7_STAGING", str(Path.home() / ".nuzantara-staging" / "s7-yield")))

# Segment SQL. Each returns the per-client fields the drafter needs.
# assigned_to is an internal Bali Zero team email (NOT client PII).
SEGMENTS: dict[str, dict] = {
    "S1": {
        "label": "Visa/KITAS renewal pipeline (expiring 0-90d)",
        "pitch": "renewal of their expiring permit (and KITAP eligibility check if applicable)",
        "sql": """
            SELECT DISTINCT c.id, c.full_name, c.nationality, c.assigned_to,
                   v.document_type, v.days_until_expiry, v.expiry_date
            FROM clients c
            JOIN client_expiry_alerts_view v ON v.client_id = c.id
            WHERE c.deleted_at IS NULL
              AND v.document_type IN ('visa','kitas','e-visa','e_visa','telex_visa')
              AND v.days_until_expiry BETWEEN 0 AND 90
            ORDER BY v.days_until_expiry ASC
        """,
    },
    "S2": {
        "label": "Expired-permit win-back (visa/kitas already expired)",
        "pitch": "re-activating their lapsed permit before penalties accrue",
        "sql": """
            SELECT DISTINCT c.id, c.full_name, c.nationality, c.assigned_to,
                   v.document_type, v.days_until_expiry, v.expiry_date
            FROM clients c
            JOIN client_expiry_alerts_view v ON v.client_id = c.id
            WHERE c.deleted_at IS NULL
              AND v.document_type IN ('visa','kitas','e-visa','e_visa','telex_visa')
              AND v.days_until_expiry < 0
            ORDER BY v.days_until_expiry DESC
        """,
    },
    "S3": {
        "label": "Passport expiring 0-180d (blocks future visa work)",
        "pitch": "renewing their passport early so upcoming visa work is not blocked",
        "sql": """
            SELECT DISTINCT c.id, c.full_name, c.nationality, c.assigned_to,
                   v.document_type, v.days_until_expiry, v.expiry_date
            FROM clients c
            JOIN client_expiry_alerts_view v ON v.client_id = c.id
            WHERE c.deleted_at IS NULL AND v.document_type='passport'
              AND v.days_until_expiry BETWEEN 0 AND 180
            ORDER BY v.days_until_expiry ASC
        """,
    },
    "S4": {
        "label": "Active client, no contact 120d+ (relationship health)",
        "pitch": "a quick check-in on their current status and any pending needs",
        "sql": """
            SELECT c.id, c.full_name, c.nationality, c.assigned_to,
                   'last_contact' AS document_type, NULL::int AS days_until_expiry,
                   c.last_interaction_date::date AS expiry_date
            FROM clients c
            WHERE c.deleted_at IS NULL AND c.status='active'
              AND (c.last_interaction_date IS NULL OR c.last_interaction_date < now()-interval '120 days')
            ORDER BY c.last_interaction_date ASC NULLS FIRST
        """,
    },
    "S5": {
        "label": "Corporate (NPWP/NIB) with zero practice (tax/compliance expansion)",
        "pitch": "a monthly tax & compliance retainer for their Indonesian company (LKPM, SPT, bookkeeping)",
        "sql": """
            SELECT c.id, c.full_name, c.nationality, c.assigned_to,
                   'corporate' AS document_type, NULL::int AS days_until_expiry, NULL::date AS expiry_date
            FROM clients c
            LEFT JOIN practices p ON p.client_id=c.id
            WHERE c.deleted_at IS NULL AND (c.npwp IS NOT NULL OR c.nib IS NOT NULL) AND p.id IS NULL
            ORDER BY c.created_at DESC
        """,
    },
    "S6": {
        "label": "WhatsApp-warm (msg <60d) with no practice (warm conversion)",
        "pitch": "turning their recent enquiry into a concrete service plan",
        "sql": """
            SELECT c.id, c.full_name, c.nationality, c.assigned_to,
                   'wa_warm' AS document_type, NULL::int AS days_until_expiry, max(w.last_message_at)::date AS expiry_date
            FROM clients c
            JOIN whatsapp_contacts w ON w.phone_normalized=c.phone_normalized
            LEFT JOIN practices p ON p.client_id=c.id
            WHERE c.deleted_at IS NULL AND p.id IS NULL AND w.last_message_at >= now()-interval '60 days'
            GROUP BY c.id, c.full_name, c.nationality, c.assigned_to
            ORDER BY max(w.last_message_at) DESC
        """,
    },
    "S8": {
        "label": "Repeat buyers (2+ paid practices) — loyalty/premium",
        "pitch": "a priority/retainer arrangement reflecting their repeat business with us",
        "sql": """
            SELECT c.id, c.full_name, c.nationality, c.assigned_to,
                   'repeat' AS document_type,
                   count(*) FILTER (WHERE lower(coalesce(p.payment_status,''))='paid') AS days_until_expiry,
                   NULL::date AS expiry_date
            FROM clients c JOIN practices p ON p.client_id=c.id
            WHERE c.deleted_at IS NULL
            GROUP BY c.id, c.full_name, c.nationality, c.assigned_to
            HAVING count(*) FILTER (WHERE lower(coalesce(p.payment_status,''))='paid') >= 2
            ORDER BY 6 DESC
        """,
    },
}


def lang_for(nationality: str | None) -> str:
    """Infer draft language from nationality (language pref column is unpopulated)."""
    n = (nationality or "").strip().lower()
    if any(k in n for k in ("indonesia", "indonesian", "wni")):
        return "Indonesian (Bahasa Indonesia)"
    if any(k in n for k in ("ital", "italiana")):
        return "Italian"
    if any(k in n for k in ("españ", "espan", "spanish", "esp")):
        return "Spanish"
    if any(k in n for k in ("franç", "franc", "french", "fra")):
        return "French"
    if any(k in n for k in ("deutsch", "german", "deu")):
        return "German"
    if any(k in n for k in ("russ", "ukrain", "ukr")):
        return "English"  # safe lingua franca for RU/UA expat clients
    return "English"


def get_pgpassword() -> str:
    out = subprocess.run(
        ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
        capture_output=True, text=True,
    )
    if out.returncode != 0 or not out.stdout.strip():
        sys.exit("[S7] FATAL: readonly Keychain creds missing (nuzantara-postgres-readonly)")
    return out.stdout.strip()


def fetch_rows(sql: str, pgpass: str, limit: int) -> list[dict]:
    env = dict(os.environ, PGPASSWORD=pgpass)
    full = f"COPY (SELECT row_to_json(t) FROM ({sql.strip().rstrip(';')} LIMIT {int(limit)}) t) TO STDOUT"
    proc = subprocess.run([PSQL, DSN, "-tA", "-c", full], capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        sys.exit(3)
    rows = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def ollama_up() -> bool:
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3).read()
        return True
    except Exception:
        return False


def draft_pitch(name: str, nationality: str, language: str, seg_pitch: str,
                doc_type: str, days: int | None, expiry) -> str:
    fact = ""
    if doc_type in ("visa", "kitas", "e-visa", "e_visa", "telex_visa") and days is not None:
        fact = f"Their {doc_type.upper()} expires in {days} days ({expiry})."
    elif doc_type == "passport" and days is not None:
        fact = f"Their passport expires in {days} days ({expiry})."
    elif doc_type == "repeat":
        fact = f"They have completed {days} paid services with Bali Zero."
    elif doc_type == "corporate":
        fact = "They have an Indonesian company (NPWP/NIB on file) but no active service with us."
    prompt = (
        f"You are a Bali Zero account executive writing a WhatsApp message to a client.\n"
        f"Client first name: {name}. Write in {language}.\n"
        f"Context: {fact}\n"
        f"Goal: invite them to discuss {seg_pitch}.\n"
        f"Rules: 40-80 words. Warm but professional. NO marketing buzzwords, NO emoji, "
        f"NO 'exciting opportunity'. Reference the specific fact above. End with a concrete "
        f"next step (a suggested 20-30 min call this week). Output ONLY the message text.\n/no_think"
    )
    body = json.dumps({"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                       "think": False, "options": {"temperature": 0.4}}).encode()
    req = urllib.request.Request(OLLAMA_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        resp = json.loads(r.read())
    txt = (resp.get("response") or "").strip()
    # qwen may wrap in <think>...</think>; strip if present
    if "</think>" in txt:
        txt = txt.split("</think>", 1)[1].strip()
    return txt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--segment", choices=list(SEGMENTS))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--dry-run", action="store_true", help="list opportunities, skip Ollama")
    args = ap.parse_args()
    if not args.segment and not args.all:
        ap.error("pass --segment <S#> or --all")

    if not args.dry_run and not ollama_up():
        sys.exit("[S7] FATAL: Ollama down — NO cloud fallback (UU PDP). Aborting.")

    pgpass = get_pgpassword()
    STAGING.mkdir(parents=True, exist_ok=True)
    targets = list(SEGMENTS) if args.all else [args.segment]
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary = {}

    for seg in targets:
        meta = SEGMENTS[seg]
        rows = fetch_rows(meta["sql"], pgpass, args.limit)
        drafted = 0
        out_path = STAGING / f"{seg}-{ts}-drafts.md"
        with out_path.open("w") as f:
            f.write(f"# S7 Yield drafts — {seg}: {meta['label']}\n")
            f.write(f"_Generated {ts} · LOCAL Ollama {OLLAMA_MODEL} · DRAFT ONLY (do not auto-send)_\n\n")
            for row in rows:
                cid = row["id"]
                name = (row.get("full_name") or "there").split()[0]
                nat = row.get("nationality")
                lang = lang_for(nat)
                f.write(f"## client_id={cid} · owner={row.get('assigned_to') or '(unassigned)'} · lang={lang}\n")
                if args.dry_run:
                    f.write(f"- {row.get('document_type')} days={row.get('days_until_expiry')} expiry={row.get('expiry_date')}\n\n")
                else:
                    try:
                        pitch = draft_pitch(name, nat or "", lang, meta["pitch"],
                                            row.get("document_type"), row.get("days_until_expiry"),
                                            row.get("expiry_date"))
                        f.write(f"**Pitch ({lang})**:\n> {pitch}\n\n")
                        drafted += 1
                    except Exception as e:  # noqa: BLE001
                        f.write(f"_draft failed: {type(e).__name__}_\n\n")
                # privacy log: client_id ONLY, never name
                print(f"[S7] {seg} client_id={cid} drafted={not args.dry_run}")
        summary[seg] = {"pulled": len(rows), "drafted": drafted, "file": str(out_path)}
        print(f"[S7] {seg}: pulled={len(rows)} drafted={drafted} -> {out_path}")

    print("[S7] SUMMARY " + json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
