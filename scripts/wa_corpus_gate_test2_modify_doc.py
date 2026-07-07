#!/usr/bin/env python3
"""GATE TEST 2 helper — modify the test Doc via Drive API (append new content).

Re-uploads the Doc content (old + a new sentinel block) via files().update with a
text/markdown media body, re-converting to native Google Doc. This mirrors how the
production renderer will refresh a chat Doc when new WhatsApp messages arrive:
regenerate the full Doc from the (now longer) chat.

PASS path: after this runs, `nlm source sync` + a query must surface the sentinel.
"""
import io, sys, json
from datetime import datetime, timezone
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SA_KEY="/Users/nuzantara/.config/nuzantara/service-accounts/nuzantara-google-drive-sa-20260530.json"
DELEGATED_USER="zero@balizero.com"
SCOPES=["https://www.googleapis.com/auth/drive"]

FILE_ID=sys.argv[1]
SENTINEL=sys.argv[2]

creds=service_account.Credentials.from_service_account_file(SA_KEY,scopes=SCOPES).with_subject(DELEGATED_USER)
svc=build("drive","v3",credentials=creds,cache_discovery=False)

# Read current text (export) to preserve old content
old=svc.files().export(fileId=FILE_ID, mimeType="text/plain").execute()
old_text=old.decode("utf-8") if isinstance(old,bytes) else str(old)

new_block = (
    "\n\n---\n\n"
    "## NEW MESSAGES APPENDED " + datetime.now(timezone.utc).isoformat() + "\n\n"
    f"**[2029-12-31T10:00:00+08:00] TEAM:** Confirmation code {SENTINEL}. "
    "Your KITAS appointment is scheduled for 2029-12-31 at the Denpasar immigration office. "
    "Please bring your passport and sponsor letter.\n\n"
    f"**[2029-12-31T10:05:00+08:00] COUNTERPART:** Received, code {SENTINEL}, thank you.\n"
)
combined = old_text.rstrip() + new_block

media=MediaIoBaseUpload(io.BytesIO(combined.encode("utf-8")), mimetype="text/markdown", resumable=False)
updated=svc.files().update(
    fileId=FILE_ID,
    media_body=media,
    fields="id,name,mimeType,modifiedTime",
    supportsAllDrives=True,
).execute()
print("[test2-modify] updated:", json.dumps(updated))

# Verify the new content is in the Doc itself (Drive-side round trip)
check=svc.files().export(fileId=FILE_ID, mimeType="text/plain").execute()
check_text=check.decode("utf-8") if isinstance(check,bytes) else str(check)
print(f"[test2-modify] Doc now {len(check_text)} chars (was {len(old_text)})")
assert SENTINEL in check_text, "sentinel not found in Doc after update!"
print(f"[test2-modify] sentinel '{SENTINEL}' present in the Doc ✅")
