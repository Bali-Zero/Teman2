# S11 Portal Audit — Prioritized UX Backlog

Session: ONDA-3 S11 portal-audit | 2026-06-03 | read-only audit, no prod mutation
Repo: Balizero1987/Teman2 | rebased on `e8e59150e`

## Subdomain health (curl, this turn)

| Subdomain | HTTP | Redirect | Final | Role | Verdict |
|---|---|---|---|---|---|
| kita.balizero.com | 307 | /login | 200 | Team/internal | LIVE |
| my.balizero.com | 307 | /portal/login | 200 | **Client portal** (Next.js apps/mouth) | LIVE |
| prime.balizero.com | 200 | — | 200 | Prime tier | LIVE |

Screenshot-QA: **MARKED MANUAL-TODO** (browser MCP not available in this subagent). curl HTML inspection done: login pages render with email/password form + Next.js bundle.

---

## P0 — Broken in production NOW (fix first)

### B1. Three portal routers orphaned → 404 on live client features
Same scar class as Sprint 1.B PR #422→#424 (manifest entry without `include_router` ⇒ prod 404, tests green).

`portal_dashboard`, `portal_family`, `portal_notification_prefs` are defined, prefixed, and listed in `router_manifest.py` — but NEVER registered via `include_router()` in `router_registration.py` (neither `include_routers()` nor `include_light_routers()`), and not mounted via `app_factory`. The runtime ignores the manifest.

Live frontend pages that call them (→ 404):
- **Family page** `portal/(authenticated)/family/page.tsx` → `GET /api/portal/family`
- **Notification settings** `portal/(authenticated)/settings/notifications` + `useNotificationPrefs` hook + `NotificationSettings.tsx` → `GET/PUT /api/portal/notifications/prefs`
- **Dashboard summary + iCal deadline export** `lib/api/portal/portal.api.ts` + `api/portal/deadlines/ical/route.ts` → `GET /api/portal/dashboard/summary`

**Fix**: add explicit imports + `include_router(...)` for the 3 routers in BOTH `include_routers()` and `include_light_routers()`. Smoke each prefix returns 200/401 (not 404) post-deploy.

---

## P2 — Structural / regression-guard

### B2. Parity test too narrow — did not catch B1
`tests/setup/test_router_registration_parity.py` only guards `channel_health` + `guardian`. The exact drift class it was written to prevent recurred on 3 portal routers. Generalize the parity sweep or add explicit guards per portal router.

---

## P3 — Hygiene / clarity

### B3. router_manifest.py is non-authoritative
Manifest claims 13 portal routers mounted; only tests consume it. Misleading single-source-of-truth. Either wire it into runtime registration or annotate test-only.

### B4. MCP client_id vs JWT identity ambiguity
MCP portal tools pass `client_id` query param, but core endpoints derive identity from JWT (`get_current_client`); `client_id` honored only on superuser `?as_client` path. Confirm MCP service account is superuser and document the `as_client` contract.

---

## Client (immigration) UX coverage matrix

| Need | Status | Note |
|---|---|---|
| Real-time practice/process tracker | ✅ LIVE | `/process/{id}/timeline` + `/process/required-documents`, process page present |
| Visa status + history + summary | ✅ LIVE | `portal_visa` |
| Visa/deadline aggregation + iCal export | ⚠️ BROKEN | depends on orphan `/dashboard/summary` |
| Downloadable documents | ✅ LIVE | `/documents`, `/documents/{id}/download`, `portal_drive` |
| Chat/messaging with team | ✅ LIVE | `/messages` + read receipts, chat page |
| Billing/invoices (+PDF) | ✅ LIVE | `portal_billing` |
| Tax obligations + summary | ✅ LIVE | `portal_taxes` |
| Family/dependents management | ❌ BROKEN | frontend page exists, backend orphan → 404 |
| Notification preferences (email/WA/phone) | ❌ BROKEN | frontend + hook exist, backend orphan → 404 |
| Company management | ✅ LIVE | `/companies`, `/company/{id}`, select-primary |
| Profile view/edit | ✅ LIVE | `/profile` GET+PATCH |
| LKPM submission | ✅ wired | lkpm pages present (separate router) |
| Partner/referral dashboard | ✅ wired | partner pages present |

**Net**: portal coverage is broad (28 frontend pages, ~40 live endpoints). The single highest-leverage fix is B1 — it converts 3 already-built client features from 404-broken to working with a ~6-line registration change.

---

## Auth posture (audit)
- Two consistent JWT dependencies: `get_current_client` (portal.py core) and `get_current_portal_client` (deps/auth.py, used by visa/taxes). Both enforce role=client + linked_client_id, with audit-logged superuser impersonation via `?as_client`.
- No open-auth portal endpoint found.
- No `cl.name`→`cl.full_name` class bug in portal routers (crm_portal_integration correctly uses `c.full_name`).
