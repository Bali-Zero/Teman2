• **Verdict: REWORK**

Static review only; I did not execute tests or read files beyond the supplied diff. Tests-passing claim is unverified.

---

**P1-1 — Legacy automatic `team_to_client` rows falsely close reply obligations**
`backend/services/portal/portal_reply_service.py::_PENDING_QUERY` + `db/migrations_v2/321_portal_reply_and_email.sql`

The NOT EXISTS clause treats any later `team_to_client` message with `is_system_generated = FALSE` as a manual reply. The migration sets the column `DEFAULT FALSE` and explicitly declines to backfill ("source cannot be reconstructed safely"). But `portal_notification_service.py` is changed _in this same diff_ to start writing `TRUE` — proof that an automatic `team_to_client` writer existed and historically wrote rows with the default FALSE. Counterexample: client asks a question 2026-09-20; the notification service wrote an automatic `team_to_client` notice 2026-09-21 (pre-deploy, `is_system_generated=FALSE`); after deploy, NOT EXISTS matches that automatic row → `total_pending = 0`, banner cleared, no human ever replied. This violates "system events cannot close reply obligations" for all pre-existing data. Fix: backfill known automatic writers (by `sent_by` sentinel / subject patterns, as already done for `sent_by='portal'` on the inbound side), or only treat post-migration manual rows as replies.

**P1-2 — `teamPortalUnreadKey` used in `PortalMessages.tsx` with no import in the diff**
`apps/mouth/src/app/(workspace)/clients/[id]/components/PortalMessages.tsx` (hunk at line ~99)

The added line references `teamPortalUnreadKey` (and `queryClient`), but the diff shows no import change for this file. If neither symbol is already in scope there, the TypeScript build fails. The hunk gives no static evidence either way; this must be verified before merge.

---

**P2-1 — Non-Brevo/missing key silently kills all portal email**
`notifications/router.py::_send_via_brevo`: with `idempotency_key` set and a non-`xkeysib-` (or empty) `SENDGRID_API_KEY`, every keyed send returns False → `EmailProviderRejected` → terminal `failed` after 3 attempts, with only a worker warning log. Delivery is now coupled to one env var's provider prefix; a deploy without it loses all client notifications silently.

**P2-2 — Explicit rejections and ambiguous duplicates are retried**
`portal_message_email.py::deliver_one`: on attempts 1–2 any exception — including `EmailProviderRejected` (terminal by definition) and `EmailDeliveryUncertain` from `duplicate_parameter` (router.py) — resets to `pending`. Rejection should be terminal immediately; duplicate-ambiguous should go straight to `uncertain` rather than burning attempts re-sending a key the provider already acknowledged.

**P2-3 — Fence failure is silent**
`portal_message_email.py::_finish`: the lease/attempts fencing `WHERE` is correct, but rowcount is unchecked — a stale finisher's no-op update leaves no log, hiding lease races.

**P2-4 — Misleading zero-state aria-label**
`TeamPortalMessageAlerts.tsx`: when data loads with 0 pending/0 unread, the trigger announces "Client messages unavailable" — indistinguishable from the error state.

**P2-5 — Worker init failure swallowed**
`app_factory.py`: if `portal_message_email` import/startup raises, only a single error log results; outbox rows accumulate `pending` forever with no surface.

**Unverified acceptance item:** "document events cannot open obligations" — no document-event writer appears in the diff; if one exists elsewhere unmarked, P1-1's class of bug applies on the open side too.
