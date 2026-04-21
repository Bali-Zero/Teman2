# Multi-LLM Council Review Synthesis — Partners Module v1

**Date:** 2026-04-21 (post-implementation)
**PR:** https://github.com/Balizero1987/nuzantara/pull/139
**Reviewers:** Gemini 2.5 Pro · Codex gpt-5.4 xhigh · DeepSeek-Reasoner · NotebookLM NB-2
**Context pack:** 144KB (spec + 11 key backend files)

## COUNCIL VERDICT: BLOCK

**Four reviewers, four BLOCK verdicts. Codex found 3 catastrophic bugs that survived the 10 per-task reviews because they cross file boundaries in ways a per-file reviewer cannot see.**

| LLM | Verdict | Crit | Imp |
|---|---|---|---|
| Gemini 2.5 Pro | BLOCK | 3 legit + 1 hallucination | 2 |
| Codex gpt-5.4 xhigh | **BLOCK** | **8 (3 catastrophic)** | 8 |
| DeepSeek-Reasoner | BLOCK | 6 | 4 |
| NB-2 (immigration) | Ship with 2 fixes | 2 (immigration) | 0 |

---

## CATASTROPHIC issues (feature does not work / silent data breach)

### CATA-1 — Accrual wired to wrong domain: reads `process_id`, DB emits `practice_id`

**Discovered by:** Codex.
**Files:** `services/crm/partners/events.py:42` vs `migrations/migration_075_practice_status_notify.py:27`.

Migration 075 (existing, in production) installs a Postgres trigger on the `practices` table that emits:
```json
{"practice_id": ..., "new_status": "completed", "new_payment": "paid", ...}
```

Our `handle_practice_status_changed()` handler reads `payload.get("process_id")` (our Task 6 plan assumed a `processes` table that doesn't exist). **On every real practice completion, the handler sees `process_id = None` and returns early.** No commission is ever accrued in production.

Migration 119's `partner_referrals.process_id` and `partner_commissions.process_id` FK-reference `processes(id)` — if `processes` doesn't exist in the live DB, the migration itself fails. If a stub exists, the FKs are wrong.

**Fix:**
1. Rename `process_id` → `practice_id` across migration 119 + models + repository + service + engine + events.
2. Update events.py to read `payload["practice_id"]` and handle the existing `practice_changed` channel (already aliased — event_bus.py:47 maps `practice_changed` → `practice.status_changed`).
3. Update FK targets to `practices(id)` (or whatever the actual table is — verify against live schema).
4. All 45+ backend tests that use `process_id` / `process_factory` need rename. The E2E test is now a false success.

**Effort:** 4-6 hours. This is v1.1 minimum — not a quick patch.

**NB:** This invalidates the Task 10 E2E test's "passing" status — the test passes against a test-stub `processes` table that doesn't exist in production. The feature has NEVER been tested against real production schema.

### CATA-2 — `GET /api/partners` leaks all partner PII to any authenticated user

**Discovered by:** Codex.
**File:** `app/routers/partners.py:214-234`, `services/crm/partners/service.py:66-76`.

The router has NO role gate on `GET /api/partners`. `service.list_partners()` only special-cases `actor_role == "team"` (forcing `assigned_to=self`). For any other role (`admin`, `partner`, or anything unexpected), the code falls through and calls `repo.list_partners()` which does `SELECT * FROM partners`.

`_partner_to_dict(p)` serializes EVERY column including: NPWP, NIK, bank_name, bank_account_holder, bank_account_number, ewallet_type, ewallet_number, iban, fiscal_address, pdp_consent_at, assigned_to.

**A partner user hitting `/api/partners` (not `/api/partners/me`) enumerates every other partner's banking details and national IDs.** UU PDP violation at its purest.

**Fix:**
1. Add `_require_team_or_admin(user)` at router top — partner role gets 403.
2. Add response DTO that strips internal fields for team-role users (they shouldn't see assigned_to for partners they don't own).
3. Introduce separate `PartnerAdminView` vs `PartnerTeamView` vs `PartnerSelfView` DTOs.

**Effort:** 1-2 hours.

### CATA-3 — Partner can create referrals for arbitrary process IDs (commission fraud)

**Discovered by:** Codex.
**File:** `app/routers/partners.py:547-561`, `services/crm/partners/service.py:211`.

The `POST /api/partners/{partner_id}/referrals` route docstring says "Team (owner) or admin". The actual code calls `verify_partner_access_with_role(svc, actor, role, partner_id)`. That helper allows `actor_role == "partner"` if the user's `partner_id == partner_id` (self-access).

**Therefore: a partner-role user can POST to their own `/referrals` endpoint with ANY `process_id` value.** If the accrual path (CATA-1) is fixed, this would trigger automatic accrual + approval + payout to the partner for a process they never referred.

No verification that:
- the process exists,
- the process is actually completed+paid yet (timing attack possible),
- the partner has any connection to the client on that process.

**Fix:**
1. Change `verify_partner_access_with_role` call to a team-or-admin check (use `_require_team_or_admin`).
2. Remove the partner-role branch entirely from the referral creation path (partners don't self-refer — the team does).
3. Add a process-access check: verify the `referred_by_user_id` (i.e., the acting team member) has `verify_client_access` on the process's client.

**Effort:** 1 hour.

---

## CRITICAL issues (production-blocking, not catastrophic)

### CRIT-1 — Commission offset lacks transaction wrapper

Multiple reviewers: Gemini, DeepSeek, Codex (C4 — they also flagged lost update on concurrent approve without `WHERE status = 'accrued'` guard).
**File:** `commission_engine.py::approve()` (~lines 240-270).
Fix: `async with self.conn.transaction():` + add `WHERE status = $2` to update query. **~30 min.**

### CRIT-2 — Mark-paid vs email: non-atomic + double-send risk

**Discovered by:** Codex.
**File:** `routers/partners.py:697-711`, `emails.py:262-268`.

Order today: (a) engine.mark_paid (DB commit) → (b) send_commission_earned (HTTP to Brevo) → (c) repo.mark_commission_email_sent (DB commit).

Failure mode: Brevo 500 between (a) and (c). Commission is `paid` in DB, no email sent, retry is impossible because `update_commission_status(paid → paid)` is disallowed by the FSM. **Partner permanently loses their commission notification.**

Second failure mode: concurrent retry between (b) and (c) → double-send because idempotency flag not set yet.

**Fix:**
1. Introduce outbox table: `partner_email_outbox` with columns `{commission_id, type, to, cc, subject, body, status, attempts, next_retry_at}`.
2. `mark_paid` writes the outbox row INSIDE the transaction that transitions status.
3. Background worker (or cron) polls and sends; updates outbox row `status=sent` + `commission_email_sent_at`.
4. Alternative v1 fix: wrap all 3 in `async with conn.transaction():` — still racy for double-send but closes the "stuck in paid without email" window.

**Effort:** 2-4h for outbox, 30 min for transaction wrap.

### CRIT-3 — Finance perm is effectively "any admin"

**Discovered by:** Codex, Gemini.
**File:** `routers/partners.py:_require_finance()`.

Current: `if "finance.mark_paid" not in perms AND user.role != "admin": 403`. Fallback means any admin has full finance power — spec said separate perm. Removes 3-person control.

**Fix:** drop the `or admin` fallback; require explicit `finance.mark_paid` permission bit. Seed that permission for Zero, Antonello, Asya as part of migration 119. **~15 min.**

### CRIT-4 — Hardcoded production secret in email module

**Discovered by:** Codex (newly noticed; we missed this in Task 8).
**File:** `emails.py:31,33,41,45`.

`NOTIFICATIONS_ENDPOINT = os.environ.get(..., "https://nuzantara-rag.fly.dev/...")` AND `X_API_KEY = os.environ.get(..., "REDACTED-ROTATED-KEY")`.

Golden Rule #6 ("No hardcoded secrets") violation. Worse: a staging/dev/CI misconfiguration (env var not set) silently falls through to PRODUCTION endpoint + PRODUCTION API key. Test environments WILL send real emails to real customer addresses.

**Fix:**
1. Remove the hardcoded fallbacks. Raise at import time if env vars unset.
2. Document required env vars in the module docstring.
3. Add `.env.example` entries.

**Effort:** 15 min.

### CRIT-5 — `entity_type="foreign"` violates Indonesian immigration law

**Discovered by:** NB-2.
**File:** `migration_119_partners.py` CHECK constraint.

Paying commission to a foreign partner on any standard KITAS (E23/E33E/F/G) violates explicit KITAS prohibitions. Every KITAS category bans "income from Indonesian sources."

**Fix (v1 minimum):** remove `foreign` from the dropdown UI until the proper split (`foreign_kitap` / `foreign_offshore`) is designed. **30 min.**

### CRIT-6 — `/me/referrals` leaks visa category via `service_type`

**Discovered by:** DeepSeek.
**File:** `routers/partners.py::me_referrals()`.

Sterilization helper minimizes client name but passes `service_type` = "KITAS E33G" which reveals investment thresholds/residency plans. UU PDP data-minimization requirement.

**Fix:** `_sterilize_service_type(raw)` → generic category. **20 min.**

### CRIT-7 — Hardcoded PPh rates with no progressive PPh21 + no-NPWP surcharge

**Discovered by:** DeepSeek.
**File:** `commission_engine.py:_WITHHOLDING_RATES`.

Rates 2.5%/2.0% are placeholders. PPh21 is progressive. No-NPWP partner needs +20% surcharge.

**Fix:** Move rates to `system_settings`; add no-NPWP surcharge logic. Asya confirms. **~30 min for code; Asya's confirmation separate.**

### CRIT-8 — Frontend/backend contract mismatch (UI unusable on first real run)

**Discovered by:** Codex.
**Files:** Multiple mismatches:
- Backend `GET /api/partners` returns `list[Partner]`. Frontend expects `{partners, total, page, page_size}`.
- Frontend types IDs as `number`. Backend uses UUID. Detail page calls `Number(params.id)` on a UUID.
- Frontend calls `/api/partner-commissions/*` (doesn't exist) and `/api/partners/commissions/export` (backend exposes `/api/partners/commissions/{id}/*` and `/api/partners/finance/export`).
- Create form sends `tax_id`, `bank_account_name`, `commission_tier`, `withheld_tarif_umum` — backend Pydantic doesn't accept any of these; it expects `npwp`, `bank_account_holder`, `tax_withholding_category` with different enum values.

**Fix:** Full audit of `apps/mouth/src/lib/api/partners/partners.ts` + every caller; align types/fields to backend Pydantic. **4-6 hours.** No UI flow actually works end-to-end today.

**NB:** the 4 unit/manual fixes on frontend during Task 9/10 (e.g., `client_display` rename) were cosmetic — the deeper contract drift was never reviewed.

---

## IMPORTANT (v1.1)

- **IMP-1:** Inactive/pending partners can still receive referrals and accrue (Codex #6). `create_referral` + `accrue_from_process` don't check `onboarding_status == 'active'`.
- **IMP-2:** Bulk reassign non-atomic (Codex #7). Partial failure leaves half-reassigned state.
- **IMP-3:** Partner commission notifications not EventBus-backed (Codex #5). `partner.commission_changed` only fires on accrual; approve/pay/clawback publish nothing.
- **IMP-4:** Audit log exposure (Codex Imp #1). Partner self-access currently permitted on audit endpoint — raw before/after JSON leaks internal field names.
- **IMP-5:** `update_partner` audit can fail AFTER the partner update commits (Codex Imp #2). `json.dumps()` on Decimal/UUID/datetime can raise — update succeeds, audit lost.
- **IMP-6:** Email TOCTOU + case-sensitivity (Codex Imp #3, Gemini, DeepSeek).
- **IMP-7:** PDP consent not captured at backend (Codex Imp #4). Frontend requires checkbox but sends `pdp_consent` — backend Pydantic only accepts `pdp_consent_version` + `terms_version`. No actual consent timestamp saved.
- **IMP-8:** NB-2 recommends hard-block on sponsor/garante/penjamin work_role.
- **IMP-9:** Finance CSV no date-range cap (DeepSeek, Codex Imp #4).
- **IMP-10:** Brevo no retry/circuit-breaker (DeepSeek).
- **IMP-11:** Process creation silently logs referral failure (Codex Imp #8). User thinks referrer saved when it wasn't.

---

## Recommended course of action

The council finds the module is **NOT production-ready**. The 3 catastrophic issues (CATA-1, CATA-2, CATA-3) mean:
- No commission will ever accrue against real practices (**feature broken**).
- Any partner can read every other partner's banking/tax IDs (**PII breach**).
- Any partner can self-assign to arbitrary practices and collect commissions (**fraud vector**).

These were invisible to per-file reviews because they require cross-reference between migrations, triggers, router, and service layer. They were only caught by Codex's whole-system reasoning pass.

**Path forward:**

**Option A (recommended): close PR #139, start v1.1 branch.**
- Revert nothing — the code is a good starting point with important surface-level polish already done.
- Create `feat/crm-partners-v1.1` branch from current head.
- Fix CATA-1 (practices rename, ~6h) + CATA-2 (role gate + DTOs, ~2h) + CATA-3 (tight access check, ~1h) + CRIT-4 (hardcoded secret, ~15min) as P0 = **~10 hours**.
- Fix CATA-4 contract audit (~6h), CRIT-2 email outbox (~3h), CRIT-1 transaction (~30min) = **~10 hours more**.
- Full v1 re-ship: **~20-25 hours focused work**.

**Option B: patch in place + new integration test against live schema.**
- Riskier: the test infrastructure built in Task 3 uses a `processes` stub table. Switching to `practices` invalidates most fixtures.
- Not recommended.

**Option C: ship with feature-flag OFF for accrual path, merge UI work only.**
- The partner anagrafica + team portal work is genuinely useful and safe if no accrual/payout flows run.
- Add a `PARTNERS_ACCRUAL_ENABLED = False` env flag.
- Merge, then do v1.1 work on the finance side behind the flag.
- Requires: CATA-2 (PII leak) fixed first — anagrafica list cannot ship without the role gate.
- Time: ~3 hours (CATA-2 + flag plumbing + disable EventBus subscriber).

## Hallucinations detected (discarded)

**Gemini CRIT-1:** claimed `models.py` has malformed `@<file-path>` decorators. Verified false: decorators are `@dataclass`.

## One-sentence summary

Per-task reviews passed because they were narrow; the whole-system review (Codex) surfaced that accrual is wired to a non-production table, partner listing leaks PII to any role, and partners can self-assign to arbitrary practices for fraud — **PR should not merge without either a full v1.1 rework or a feature-flag guard.**

## Council artifacts

- `01-gemini.md` — 66 lines, 3 criticals (1 hallucination)
- `02-codex.md` — full response. 8 criticals with file:line refs.
- `03-deepseek.md` — 180 lines, 6 criticals (incl. reasoning trace)
- `04-nb2.md` — immigration-specific, 2 criticals
- `99-synthesis.md` — this file
