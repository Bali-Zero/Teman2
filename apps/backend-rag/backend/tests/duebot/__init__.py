"""I DUE BOT — lane B6a test harness (transport level).

Instruments other lanes build on top of, NOT client/team-bot business
logic. See ``docs/plans/2026-08-25-due-bot-live/MANDATE.md`` (F3, F9) and
``research/operations/2026-08-25-due-bot-7-lens-research.md`` §5.1-5.3 for
the design this package implements.

Public surface other lanes should import (stable — treat as a contract):

- ``backend.tests.duebot.webhook_signer`` — ``sign_payload`` /
  ``tamper`` — raw-body HMAC signer for Meta webhooks.
- ``backend.tests.duebot.fake_meta_sender`` — Meta-shaped WhatsApp/
  Instagram payload builders + ``to_raw_body`` / ``load_static_payload``.
- ``backend.tests.duebot.replay`` — ``WebhookReplayer`` /
  ``whatsapp_replayer`` / ``instagram_replayer`` — drives a local FastAPI
  ``TestClient`` with exact raw bytes.
- ``backend.tests.duebot.fake_codex_broker`` — ``FakeCodexBroker`` — the
  closed F3 wire-error vocabulary (``AUTH_DEAD`` / ``QUOTA`` / ``TIMEOUT`` /
  ``HOST_OFFLINE`` / ``OUTPUT_INVALID`` / ``POLICY_BLOCKED`` / ``INTERNAL``),
  zero network, in-process.
- ``backend.tests.duebot.defect_catalogue`` — ``load_defect_catalogue`` /
  ``DefectClass`` — the shared defect-class-id fixture both bots' golden
  suites are meant to index into (B6b is data entry against this, not a
  second list).

Every test under this package tree runs under the autouse network guard in
``conftest.py`` — see ``test_no_network_guard.py`` for the proof it fires.
"""

from __future__ import annotations
