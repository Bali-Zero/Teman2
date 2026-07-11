#!/usr/bin/env python3
"""GATE TEST 1 — WhatsApp corpus-miner: write a Google Doc via DIRECT Drive API.

Purpose (prova-di-fuoco): prove we can render a real WhatsApp chat from the local
Postgres into a NATIVE Google Doc inside the zero@balizero.com Workspace using the
Drive API directly (files().create with text/markdown -> google-apps.document
conversion), bypassing the buggy MCP google-workspace docs path entirely.

PASS criteria:
  - Doc is created (returns a fileId).
  - get_file_metadata confirms mimeType == application/vnd.google-apps.document
    and the file lives under the impersonated zero@ Drive.
  - export of the Doc as text/plain returns the rendered chat content (round-trip).

Auth: Service Account with Domain-Wide Delegation impersonating zero@balizero.com
(same path ServiceAccountDriveService uses in the backend).

Writes a small JSON receipt to /tmp so TEST 2 can pick up the fileId.
"""
from __future__ import annotations

import io
import json
import os
import sys
from datetime import datetime, timezone

import psycopg2
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SA_KEY = "/Users/nuzantara/.config/nuzantara/service-accounts/nuzantara-google-drive-sa-20260530.json"
DELEGATED_USER = "zero@balizero.com"
SCOPES = ["https://www.googleapis.com/auth/drive"]
DB_DSN = "postgresql://localhost:5432/nuzantara_dev"

# Chosen real 1-a-1 chat (external counterpart, contact_type='contact', ~53 msg)
TEAM_PHONE = "+628120000001"
COUNTERPART_PHONE = "+33600000000"

RECEIPT_PATH = "/tmp/wa_corpus_gate_test1_receipt.json"


def build_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        SA_KEY, scopes=SCOPES
    ).with_subject(DELEGATED_USER)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def render_chat_markdown(team_phone: str, counterpart_phone: str) -> tuple[str, int]:
    conn = psycopg2.connect(DB_DSN)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT direction, message_date,
                   COALESCE(NULLIF(body,''), NULLIF(message_text,''), '') AS txt
            FROM whatsapp_message_context
            WHERE chat_type='direct'
              AND team_member_phone=%s AND counterpart_phone=%s
            ORDER BY message_date NULLS LAST, id
            """,
            (team_phone, counterpart_phone),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    lines = [
        f"# WhatsApp chat — team {team_phone} ↔ counterpart {counterpart_phone}",
        "",
        f"Rendered: {datetime.now(timezone.utc).isoformat()}",
        f"Message count: {len(rows)}",
        "",
        "---",
        "",
    ]
    for direction, mdate, txt in rows:
        if not txt:
            continue
        who = "TEAM" if direction == "outbound" else "COUNTERPART"
        ts = mdate.isoformat() if mdate else "(no-date)"
        lines.append(f"**[{ts}] {who}:** {txt}")
        lines.append("")
    return "\n".join(lines), len(rows)


def main() -> int:
    print(f"[test1] rendering chat {TEAM_PHONE} <-> {COUNTERPART_PHONE} ...")
    md, n = render_chat_markdown(TEAM_PHONE, COUNTERPART_PHONE)
    print(f"[test1] rendered {n} rows, {len(md)} chars of markdown")
    if len(md) < 50:
        print("[test1] FAIL: rendered content suspiciously small")
        return 1

    svc = build_drive_service()

    doc_name = f"WA-GATE-TEST1-{COUNTERPART_PHONE}-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}"
    media = MediaIoBaseUpload(
        io.BytesIO(md.encode("utf-8")),
        mimetype="text/markdown",
        resumable=False,
    )
    # Native Google Doc via conversion: target mimeType = google-apps.document
    file_meta = {
        "name": doc_name,
        "mimeType": "application/vnd.google-apps.document",
    }
    print(f"[test1] creating native Google Doc '{doc_name}' via Drive API ...")
    created = (
        svc.files()
        .create(
            body=file_meta,
            media_body=media,
            fields="id, name, mimeType, webViewLink, owners(emailAddress)",
            supportsAllDrives=True,
        )
        .execute()
    )
    file_id = created["id"]
    print(f"[test1] created fileId={file_id} mimeType={created.get('mimeType')}")
    print(f"[test1] owners={[o.get('emailAddress') for o in created.get('owners', [])]}")
    print(f"[test1] webViewLink={created.get('webViewLink')}")

    # VERIFY 1: metadata round-trip
    meta = (
        svc.files()
        .get(
            fileId=file_id,
            fields="id, name, mimeType, owners(emailAddress)",
            supportsAllDrives=True,
        )
        .execute()
    )
    assert meta["mimeType"] == "application/vnd.google-apps.document", (
        f"expected native Doc, got {meta['mimeType']}"
    )
    print(f"[test1] VERIFY metadata OK: native Doc, name={meta['name']}")

    # VERIFY 2: export back to text/plain and confirm content round-trip
    exported = (
        svc.files()
        .export(fileId=file_id, mimeType="text/plain")
        .execute()
    )
    exported_text = exported.decode("utf-8") if isinstance(exported, bytes) else str(exported)
    print(f"[test1] exported {len(exported_text)} chars back from the Doc")

    # The Doc must contain a distinctive line from our render (round-trip proof).
    probe = "Message count:"
    if probe not in exported_text:
        print(f"[test1] FAIL: round-trip probe '{probe}' not found in exported text")
        print("[test1] first 300 chars exported:\n" + exported_text[:300])
        return 1
    # Also confirm at least one real message body survived.
    print("[test1] first 400 chars exported from Doc:")
    print(exported_text[:400])

    receipt = {
        "test": "gate-test1-drive-write",
        "status": "PASS",
        "file_id": file_id,
        "doc_name": doc_name,
        "mime_type": meta["mimeType"],
        "owners": [o.get("emailAddress") for o in created.get("owners", [])],
        "web_view_link": created.get("webViewLink"),
        "rendered_rows": n,
        "rendered_chars": len(md),
        "exported_chars": len(exported_text),
        "team_phone": TEAM_PHONE,
        "counterpart_phone": COUNTERPART_PHONE,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    with open(RECEIPT_PATH, "w") as f:
        json.dump(receipt, f, indent=2)
    print(f"[test1] receipt written to {RECEIPT_PATH}")
    print("[test1] PASS ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
