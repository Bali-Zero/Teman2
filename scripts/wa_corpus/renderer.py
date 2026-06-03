"""Render a chat to markdown and write it as a NATIVE Google Doc via Drive API.

Drive calls are exactly the ones proven in the 2026-06-04 gate:
  - files().create(mimeType=google-apps.document, media=text/markdown)  -> native Doc
  - files().update(media=text/markdown)                                 -> refresh
  - permissions().create(writer, antonellosiano@gmail.com)              -> F1 share
"""
from __future__ import annotations

import io
from datetime import datetime, timezone

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from scripts.wa_corpus.config import (
    DELEGATED_USER,
    DRIVE_SCOPES,
    NLM_ACCOUNT_EMAIL,
    SA_KEY_PATH,
)
from scripts.wa_corpus.db import ChatLine


def render_markdown(team_phone: str, counterpart_phone: str, lines: list[ChatLine]) -> str:
    out = [
        f"# WhatsApp chat — team {team_phone} ↔ counterpart {counterpart_phone}",
        "",
        f"Rendered: {datetime.now(timezone.utc).isoformat()}",
        f"Message count: {sum(1 for ln in lines if ln.text)}",
        "",
        "---",
        "",
    ]
    for ln in lines:
        if not ln.text:
            continue
        who = "TEAM" if ln.direction == "outbound" else "COUNTERPART"
        ts = ln.message_date.isoformat() if ln.message_date else "(no-date)"
        out.append(f"**[{ts}] {who}:** {ln.text}")
        out.append("")
    return "\n".join(out)


class ChatDocRenderer:
    def __init__(self) -> None:
        creds = service_account.Credentials.from_service_account_file(
            SA_KEY_PATH, scopes=DRIVE_SCOPES
        ).with_subject(DELEGATED_USER)
        self.svc = build("drive", "v3", credentials=creds, cache_discovery=False)

    def _media(self, markdown: str) -> MediaIoBaseUpload:
        return MediaIoBaseUpload(
            io.BytesIO(markdown.encode("utf-8")),
            mimetype="text/markdown",
            resumable=False,
        )

    def create_doc(self, name: str, markdown: str) -> str:
        created = (
            self.svc.files()
            .create(
                body={"name": name, "mimeType": "application/vnd.google-apps.document"},
                media_body=self._media(markdown),
                fields="id",
                supportsAllDrives=True,
            )
            .execute()
        )
        file_id = created["id"]
        self.share_with_nlm_account(file_id)  # F1: must share or nlm can't see it
        return file_id

    def update_doc(self, file_id: str, markdown: str) -> None:
        self.svc.files().update(
            fileId=file_id,
            media_body=self._media(markdown),
            fields="id, modifiedTime",
            supportsAllDrives=True,
        ).execute()

    def share_with_nlm_account(self, file_id: str) -> None:
        self.svc.permissions().create(
            fileId=file_id,
            body={"type": "user", "role": "writer", "emailAddress": NLM_ACCOUNT_EMAIL},
            sendNotificationEmail=False,
            supportsAllDrives=True,
            fields="id",
        ).execute()

    def export_text(self, file_id: str) -> str:
        data = self.svc.files().export(fileId=file_id, mimeType="text/plain").execute()
        return data.decode("utf-8") if isinstance(data, bytes) else str(data)
