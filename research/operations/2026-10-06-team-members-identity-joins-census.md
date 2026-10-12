---
date: 2026-10-06
domain: backend-rag
subject: team-members-identity-joins-census
status: CENSUS — report only, no code changes
adversarial_review: exempt-external-builder-census-generator-neq-grader-by-contract
adversarial_review_note: "Author seat: Kimi (external builder). Per AGENTS.md §0.0 the generator!=grader rule is enforced at the workflow level: an interactive Claude session independently verifies this branch before merge. Every claim below is code-cited (file:line) and independently re-runnable from the grep patterns in §2; no production data was accessed."
---

# Census — `team_members` identity/access joins by email (role-unfiltered)

**Date:** 2026-10-06
**Lane:** backend-rag · census-only (report deliverable; **no code changes shipped** — see Decision)
**Base:** fresh `origin/main` (`83237f8f93`)
**Context:** follow-up to PR #7899 (`agent/air-m5/backend-rag/teammembers-role-guard`, still **OPEN / unmerged** at census time), which hardened the 3 surviving owner-validity predicates with `tm.role IS DISTINCT FROM 'client'`. This census covers the **out-of-scope family #7899 flagged**: identity/access joins on `team_members` email (auth, drive access, HR, notifications routing) that remain role-unfiltered.

**PII note:** all analysis from code only. Every example below is synthetic (`staff@example.com`, `client@example.com`); no production data was queried and no real name/email appears in this report.

---

## 1. Why this family is different from #7899's

`team_members` is overloaded: ~515 `role='client'` portal-login rows share the table with ~25 staff rows. `email` is UNIQUE, so two rows can never hold the same address — the collision risk is **not** "two rows, one email". It is:

> **An email/identity that belongs to (or is claimed by) a non-staff principal is matched against a `team_members` row *as if that row proved staff identity*, because the query filters `email (+ active)` only and never checks `role`.**

A `role='client'` row is `active = true`, `portal_access = true`, `department = NULL`, `whatsapp` populated from CRM data. Any query that treats "row exists + active" as "is staff" is mis-authorizing by construction.

---

## 2. Method (grep completeness evidence)

All patterns were run against `apps/backend-rag/backend/**.py`, excluding tests/migrations/scripts unless noted:

```
rg -n "team_members" backend --type py                     # 149 files → narrowed to non-test runtime code
rg -n "team_members.{0,80}email|email.{0,80}team_members"  # every email-co-occurrence site
rg -n "FROM team_members|JOIN team_members" backend        # every SQL shape (raw SQL + docstring SQL)
rg -n "team_member_email" backend                          # producer/consumer graph for the WA-copilot signal
```

ORM usage: the only `table=True` model on this table is `backend/app/modules/identity/models.py:20` (`User`); its consumers were traced individually. Every non-test `FROM/JOIN team_members` site was read in full — 40+ sites. Sites were classified by **what decision the result feeds**, not by query text alone.

---

## 3. Sites covered by PR #7899 (OPEN, unmerged — listed for the record)

| Site | Decision it feeds |
|---|---|
| `backend/app/modules/notifications/service.py:432-442` | client-owner lookup for notification routing — the real predicate of the three |
| `backend/app/routers/portal.py:1199` | `assigned_to` name/avatar display join (display-only; guard is defense-in-depth) |
| `backend/services/portal/_mixins/billing.py:462` | same display join in billing profile (display-only) |

If #7899 merges before any fix PR from this census, those three drop off the list below.

---

## 4. HIGH RISK — identity/access decision, role-unfiltered, one-line-guardable

### H1. `backend/app/routers/team_drive.py:160-169` — Drive folder access decision
```sql
SELECT tm.department, tm.full_name, d.name AS role_name, d.can_see_all
FROM team_members tm
LEFT JOIN departments d ON tm.department = d.code
WHERE tm.email = $1 AND tm.active = true
```
**Feeds:** `get_user_allowed_folders()` → the allow-list for `list-folders` (line 403) and `list-files` (line 554) on the team shared drive. Endpoints depend only on `get_current_user` (`deps/auth.py:35`), which accepts **any** valid JWT — including `role='client'` portal JWTs.

**Mis-authorization path:** a portal client's row (active, `department NULL`) matches → not the not-found branch → `department=None`, `can_see_all=False` → code sets `role = "team"` → `folder_access_rules` are resolved by `user_email` → `department` (NULL, no match) → **`role='team'`** → default `*`. The client gets whatever role-`team`/default rules grant (line 229 always adds `SHARED_FOLDERS` — BOARD, CRM, TAX DEPARTMENT folders — on top of rule matches), instead of the safe not-found fallback (`SHARED_FOLDERS` only, line 169). Impact magnitude is data-dependent on live `folder_access_rules` rows, which this census did not read (no prod data access); the identity confusion itself is not data-dependent.

**Contrast (same file, benign):** `check_is_board` (line 871) uses an INNER JOIN on `departments`, so a NULL-department client row matches nothing and fails closed. The fix for line 160 is the same shape as #7899: `AND tm.role IS DISTINCT FROM 'client'` in the WHERE — client rows then fall to the existing not-found default.

### H2. `backend/services/wa_copilot/identity_resolver.py:186-207` — `resolve_team_email`
```sql
SELECT id::TEXT AS tm_id FROM team_members
WHERE LOWER(email) = LOWER($1) AND active = true LIMIT 1
```
**Feeds:** the WA-copilot sender-identity cascade (`CASCADE` at line 550) — a hit returns `sender_role='team'` with confidence 1.00. That classification drives team-mode handling of the message (autonomy, cache behaviour per the 2026-07-20 ruling — team answers never touch the shared cache). A `team_member_email` field carrying a **client's** address (e.g. stale context rows, `_core.py:545` falling back to payload values) classifies the client as staff.

### H3. `backend/services/wa_copilot/identity_resolver.py:393-470` — `resolve_team_name`
```sql
SELECT id::TEXT AS tm_id, full_name, similarity(full_name, $1) AS sim
FROM team_members
WHERE active = true AND full_name IS NOT NULL AND full_name % $1
ORDER BY sim DESC LIMIT 2
```
**Feeds:** same cascade, `sender_role='team'` on a ≥0.5 trigram match of the sender push name against `team_members.full_name`. Client rows carry real `full_name`s, so an inbound client message whose push name resembles any roster name is classified as team. No role filter, no `<> 'client'`, no `NULLIF` fail-closed hardening — unlike its sibling `backend/services/whatsapp_identity.py:54-64`, which is the repo's gold standard (`role <> 'client'` + NULL/blank-role rejection + active check).

---

## 5. MEDIUM — notification/routing joins, unfiltered, bounded blast radius

| # | Site | Query shape | Decision | Assessment |
|---|---|---|---|---|
| M1 | `backend/services/crm/team_whatsapp_sender.py:55` | `email+active` only | sends free-form WhatsApp text to the row's `whatsapp` number (API-key cron endpoint) | contract says "team member"; an active client row with a whatsapp number would receive if a caller passed a client email. Callers today pass staff addresses only |
| M2 | `backend/services/wa_copilot/telegram_notifier.py:373` | `JOIN tm ON LOWER(tm.email)=LOWER(a.owner)`, `active+notify_telegram` | per-owner Telegram DM for open action_queue items | misroute needs a client email in `action_queue.owner`; owners are staff by writing convention, not by constraint |
| M3 | `backend/services/crm/assignment.py:655-668` | `tm.email=$1 → user_profiles → messaging_users.telegram_chat_id`, no active/role on `tm` | Telegram DM on lead assignment | same family; deactivated staff would also still receive |
| M4 | `backend/services/mail_loop/cli.py:118` | `lower(email)` → `id`, no filter | resolves the Zoho-token owner id at CLI startup | any row with the configured email yields its id; config is an operator address, so practical exposure is low |
| M5 | `backend/app/utils/crm_utils.py:275` | `lower(email)` → `department, active`; passes iff `department='tax'` | widens client-invite authority to the tax department | a client row would need `department='tax'`; portal rows are written with NULL department, and the email looked up is the authenticated caller's own — benign in practice, noted for completeness |

---

## 6. LOW / benign by construction (read and cleared)

**Already role-scoped (the correct pattern):**
- `backend/services/whatsapp_identity.py:54-64` — fail-closed `role <> 'client'` + blank-role rejection (model implementation)
- `backend/services/garuda_portal/staff_auth.py:210` — role fetched, then `_is_staff_role()` → `is_human_team_member()` allow-list
- `backend/services/garuda_portal/assignment_targets.py:118` — candidates validated through the same predicate
- `backend/services/crm/partners/repository.py:122` — `role IN ('team','admin') AND active`
- `backend/services/crm/assignment.py:557,596` — `tm.role IN (ASSIGNABLE_ROLES)`
- `backend/app/routers/visa_oracle_testing.py:80` — role checked downstream via `is_human_team_member`
- `backend/app/routers/team.py:58-107` — roster queries carry `role <> ALL(non_human_roles_sql_array())`; caller identity itself comes from an upstream staff gate
- `backend/services/integrations/drive/drive_auth.py:254` — INNER JOIN `departments`: NULL-department client rows match nothing, fail closed (contrast with H1's LEFT JOIN)
- `backend/app/routers/admin_team_activity.py:106` — `role NOT IN (NON_HUMAN_ROLES)`

**Role-scoped by design (`role='client'` is the intended match):**
- `backend/app/routers/auth.py:360-388` (login) and `backend/app/modules/identity/service.py:104-121` — the dual-purpose login; it *must* match client rows, and the 2026-09-11 `linked_client_id/deleted_at` gate already covers the soft-deleted-client hole
- `backend/services/portal/magic_link_service.py:77,182` — `role='client' AND portal_access AND linked_client_id IS NOT NULL`
- `backend/services/portal/portal_profile_service.py:67-84` — creates client rows; `ON CONFLICT … WHERE role='client'`
- `backend/services/compliance/lkpm_service.py:169`, `backend/app/routers/crm_portal_integration.py:211` — client-scope resolution
- `backend/services/portal/invite_service.py:283,332` — collision *detection*: matching any row (including client rows) is the point

**Display / enrichment only (no access decision):**
- `backend/services/portal/_mixins/billing.py:462`, `backend/app/routers/portal.py:1199`, `backend/app/modules/notifications/service.py:435` — the three #7899 sites (display/owner-routing)
- `backend/services/notifications/email_branding.py:202` — signature avatar/name
- `backend/services/portal/challenge_leaderboard.py:235` — activation display name
- `backend/services/rag/agentic/context_manager.py:83,113` — AI profile enrichment via `user_profiles` email join; unique-email constraint makes cross-principal joins impossible
- `backend/services/crm/welcome/welcome_email_service.py:197` — advisor whatsapp shown in welcome email
- `backend/app/routers/admin_team_activity.py:547-580` — admin-only practice stats with fuzzy email-alias normalisation

**Stats / analytics (accuracy, not authorization):**
- `backend/app/routers/dashboard_summary.py:244` — `COUNT(*) WHERE active` inflates the "agenti" metric with client rows
- `backend/services/analytics/weekly_email_reporter.py:93-103` — report *recipients* are computed from `email_activity_log`; the unfiltered member list only pollutes per-member stats. (Also: queries `is_active = TRUE`, a legacy column name this census could not confirm on the current table — worth a separate look.)
- `backend/services/analytics/attendance_monitor.py:706-718,723-731` — HR analytics rosters, same `is_active` caveat
- `backend/app/services/hr/hr_service.py` (9 sites), `backend/services/analytics/attendance_monitor.py:687`, `backend/services/crm/client_core.py:1144`, `backend/app/routers/crm_practices.py:180` — all join on `tm.id = e.team_member_id` (FK through `hr_employees`), not email

**Static staff-only data sources:**
- `backend/data/team_members.json` / `backend/data/team_members.py` (19 entries, all staff job titles) consumed by `backend/services/rag/agentic/tools.py`, `backend/services/misc/zantara_tools.py`, `backend/plugins/team/list_members_plugin.py`, `backend/services/oracle/oracle_database.py:54-64`
- `backend/services/rag/agentic/team_crm_tools.py:120-160` — consumes the *already-filtered* whatsapp_identity profile, not the table

**Recipient validation where clients are intended recipients:**
- `backend/app/routers/whatsapp_conversations.py:279` — outbound send gate accepts `clients.phone` OR `team_members.whatsapp`; either branch is a legitimate recipient class

**Id-based (not the email family):**
- `backend/services/crm/partners/emails.py:288,470`, `backend/services/crm/partners/service.py:274,282,323`, `backend/app/routers/partners.py:406,429,478`, `backend/app/routers/zoho_email.py`, `backend/services/integrations/zoho_email_service.py:250`, `backend/app/routers/visa_oracle_testing.py:279`, `backend/app/routers/auth.py:232,904`

**Ops scripts (CLI, manual run):** `backend/scripts/seed_users.py:115`, `backend/scripts/check_schema.py:35`, `backend/services/hardening/llm_credit_sentinel_cli.py:71`, `backend/services/mail_loop/cli.py` (M4 above).

---

## 7. Decision: no code changes in this PR

The mandate allows a fix **only if exactly one site** is both high-risk and one-line-guardable. This census found **three** (H1, H2, H3). All three are one-line guards (`AND tm.role IS DISTINCT FROM 'client'` / `AND LOWER(BTRIM(COALESCE(role,''))) <> 'client'` following the `whatsapp_identity.py` hardened pattern), but shipping one and not the others would leave the PR inconsistent with its own motivation, and shipping all three exceeds the "exactly one" carve-out. **Recommend a follow-up guard PR covering H1+H2+H3 together** (plus optional M1), with tests mirroring `backend/tests/unit/services/crm/test_owner_role_guard.py` from #7899.

## 8. What was NOT verified / open risks

- **Live `folder_access_rules` content** (H1 impact magnitude) — not read; DB access is out of bounds for this lane. If no role='team'/default rules exist beyond `SHARED_FOLDERS`, H1's practical delta shrinks to the personal-folder exposure (`full_name` folder added for any matched row, including client rows).
- **Whether `is_active` (weekly_email_reporter, attendance_monitor) is a live column** — legacy-column migration 137 was checked and does not mention it; if the column is dead these two paths may already be failing or hitting a compat view.
- **Callers of `team_whatsapp_sender`** outside the S7 dispatch script were not exhaustively enumerated.
- **#7899 merge state** — still OPEN at census time; if it merges, Section 3 sites are already guarded.
- The fuzzy-name signal (H3) has a legitimate ambiguity guard, but it guards *two staff candidates against each other*, never *staff vs client* — the role filter is the only client/staff separator and it is absent.
