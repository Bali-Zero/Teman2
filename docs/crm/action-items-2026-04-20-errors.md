# Live errors triage — 2026-04-20 evening

Collected from a browser console after deploying #135. Four classes of
errors surfaced on /dashboard and /process.

## 1. ✅ FIXED — team avatars 404

**Symptom:** `images/team/{sahira,ari,adit,krisna}.png → 404` loaded from
CRM pages.

**Root cause:** `team_members.avatar` column in prod DB stored the legacy
path `/images/team/*.png`, but the static assets live under
`/static/team/*.png` (and also `/avatars/team/*.png`). Public folder has
no `images/team/` tree.

**Fix applied (prod, out-of-band):**

```sql
UPDATE team_members
   SET avatar = REPLACE(avatar, '/images/team/', '/static/team/'),
       updated_at = NOW()
 WHERE avatar LIKE '/images/team/%';
-- 5 rows touched: adit, ari.firda, dea, krisna, sahira
```

`ruslana@balizero.com` still points to `/avatars/team/ruslana.jpg` — valid,
file exists there, left untouched.

---

## 2. ✅ FIXED — `api/crm/interactions → 404`

**Symptom:** console 404 on `api/crm/interactions` without trailing slash.

**Root cause:** Backend router is
`APIRouter(prefix="/api/crm/interactions")` with `@router.get("/")`, so
only the trailing-slash variant matches. FastAPI issues a 307 on the
non-slash variant; the browser fetch drops auth on the redirect and the
CRM UI reads the result as a 404.

**Fix applied (code, PR forthcoming):**
`apps/mouth/src/lib/api/crm/crm.api.ts` — added trailing slash to the
`getInteractions` URL builder.

---

## 3. ⚠️ MANUAL ACTION REQUIRED — Drive thumbnail 503

**Symptom:** `api/documents/thumbnail/{file_id} → 503` — "Google Drive
not connected".

**Root cause:** `google_drive_tokens` table shows both SYSTEM and the
linked user token are EXPIRED and the refresh_token itself was **revoked
or expired by Google** (tested: `POST /oauth2/token` with the stored
refresh_token returns `400 invalid_grant: Token has been expired or
revoked`).

```
 user_id  | expires_at                    | expired_since
----------+-------------------------------+-------------------
 SYSTEM   | 2026-04-13 09:55:04.433381+00 | 7 days 02:55:59
 7dfe56b2…| 2026-04-15 03:03:59.931116+00 | 5 days 09:47:04
```

**Fix required (human):** re-authenticate Google Drive via
https://kita.balizero.com/settings/integrations (OAuth consent screen).
The `scripts/drive_token_watchdog.py` cron should have alerted 7 days
before expiry — check whether the watchdog ran and why the Telegram
alert was missed.

---

## 4. ℹ️ EXPECTED — `api/crm/practices?limit=3 → 401`

**Symptom:** two 401 responses on `api/crm/practices?limit=3` at page
load.

**Root cause:** the JWT cookie had not finished rehydrating at the
moment the fetch fired. The subsequent authenticated call succeeded
(visible in the same console: "Dashboard loaded" log right after).
Expected behaviour of the SSO bootstrap — no action.

---

## 5. ℹ️ EXPECTED — `Invalid status transition: inquiry → sending_invoice`

**Symptom:** 400 on `api/crm/practices/244` when toggling status.

**Root cause:** the state machine (PR #132/#133 — live) correctly
rejects non-canonical transitions. `inquiry` must pass through
`waiting_documents` before reaching `sending_invoice`. The UI should
refuse to let the user click a forbidden step or preview the path.

**Fix pending (P1):** UI-side guard — disable the status stepper
buttons that would trigger an invalid transition according to
`practice_state_machine.VALID_TRANSITIONS`. Out of scope for today.
