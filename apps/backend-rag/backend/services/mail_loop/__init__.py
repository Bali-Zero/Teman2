"""Daily Zoho mail loop: route inbox mail, draft replies, learn from Sent.

This package is a thin orchestration layer on top of the EXISTING
`services.integrations.zoho_email_service.ZohoEmailService` (OAuth already
carries ZohoMail.messages.CREATE / .UPDATE / folders.READ). It deliberately
does NOT open a second IMAP stack: a duplicate organ for the same job is the
`apps/cell` vs `packages/cell-core` pattern that cicatrix warns about.

Design contract:
    * Nothing is archived on our side. Mail stays in Zoho; we only MOVE it
      into a folder and APPEND a draft. The ONLY thing that persists here is
      the learned style file (`style.ReplyStyleStore`).
    * The learning signal is diff(our draft, what Zero actually sent), read
      back from the Sent folder on the next run.
    * We never send. `save_draft` only. A human presses send (org rule).
"""

from __future__ import annotations

__all__ = ["classify", "draft", "learn", "loop", "style"]
