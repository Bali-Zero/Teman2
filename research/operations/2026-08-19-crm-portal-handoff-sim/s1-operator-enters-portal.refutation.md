---
date: 2026-08-19
domain: compliance
client_case: null
sources:
  - apps/backend-rag/backend/app/routers/portal.py (lines 89-231, 1092-1213 — Read this turn)
  - apps/backend-rag/backend/app/core/config.py (lines 955-1023 — Read this turn)
  - apps/backend-rag/backend/app/utils/cookie_auth.py (lines 1-115 — Read this turn)
  - apps/mouth/src/proxy.ts (lines 1-300 — Read this turn)
  - "apps/mouth/src/app/portal/(authenticated)/layout.tsx (lines 120-220 — Read this turn)"
  - apps/mouth/src/lib/api/client.ts (lines 360-414 — Read this turn)
  - apps/mouth/src/lib/api/portal/portal.api.ts (lines 130-150 — Read this turn)
  - "mcp__postgres-nuzantara-local__query (SELECT id, email, full_name FROM clients WHERE LOWER(email) IN (3 admin emails) — run this turn)"
  - "mcp__postgres-nuzantara-local__query (practices/documents/portal_messages counts for client_id=68 — run this turn)"
  - "curl -sS -D - https://my.balizero.com/portal (no cookie, and with junk nz_access_token — run this turn)"
  - qwen CLI cross-family second opinion — timed out at 240s twice, no substantive output, treated as unavailable
adversarial_review: codex
---

# S1 refutation — operator crosses into client portal

## Method
(A) Re-opened every file:line cited by the prior analyst and re-ran every command cited (curl
against live my.balizero.com, and the Postgres queries against the read-only replica), independent
of the analyst's transcript. (B) Attempted a cross-family second opinion via `qwen -p` per the
convened-review protocol; it did not return a substantive answer (see below) — verdict below rests
on (A) alone.

## Seat B — qwen-alibaba-tp1
Ran the exact required command twice (`timeout 240 qwen -p "$(cat …refute-prompt.txt)"`), once
piped through `tail -120`, once redirected to a file. Both runs exited 124 (timeout) with the CLI's
own terminal output being the single line `Operation cancelled.` — no findings, no partial review,
no refusal text, nothing substantive to judge. Per protocol this is recorded as **unavailable**,
not as agreement or disagreement with any finding. Prompt used is on disk at
`research/operations/2026-08-19-crm-portal-handoff-sim/s1-operator-enters-portal.refute-prompt.txt`
in this worktree, so the review can be replayed against a healthier seat later.

## Verdicts

### Finding 1 — Superuser self-lookup fallback (portal.py get_current_client)
**STANDS.** Every citation checks out verbatim:
- `portal.py:157-179` is exactly the branch described: `is_superuser` (email in
  `settings.admin_emails_set`) + no `?as_client` → `SELECT id, email, full_name FROM clients WHERE
  LOWER(email)=LOWER($1)` keyed on the caller's OWN JWT email, returns 200 with
  `"impersonating": False` on a hit, 422 on a miss.
- `portal.py:1092-1173` (`GET /profile`) returns exactly the field set claimed:
  full_name/email/phone/whatsapp/nationality/passport_number/passport_expiry/date_of_birth/
  gender/address/member_since/assigned_to, keyed on `client["client_id"]`.
- `config.py:998-1022` confirms the 3-address fallback set
  `{zero@,asya@,antonellosiano@}balizero.com` verbatim.
- `_log_impersonation` (`portal.py:97-119`) is called only inside the `?as_client` branch
  (`portal.py:199-205`); the self-lookup branch at 157-179 has no call to it — confirmed by
  reading both ranges, nothing elides it.
- Independently re-ran the Postgres check (not copied from the analyst's transcript):
  `SELECT id, LOWER(email), full_name FROM clients WHERE LOWER(email) IN (3 admin emails)` →
  exactly one row, `id=68, email=zero@balizero.com, full_name=Antonello Siano` — the other two
  admin addresses have no matching row. `practices`/`documents`/`portal_messages` counts for
  `client_id=68` are independently confirmed `0/0/0` (using the real table names — the analyst's
  evidence line names them generically as "practices_n/documents_n/messages_n"; the underlying
  tables are `practices`, `documents`, `portal_messages`, and the counts match exactly).

**Additional supporting evidence found in this review, not in the original finding**: the write
path shares the same exposure. `PATCH /profile` (`portal.py:1185-1213`) also depends on
`get_current_client` and calls `portal_service.update_profile(client["client_id"], fields, ...)`
with `client["client_id"]` sourced from the same silent self-lookup fallback — so an admin who
edits phone/whatsapp/address while in this state writes to `clients.id=68` (their own row) through
the client-facing code path rather than the CRM's staff-facing one, with no impersonation flag and
no audit entry. This strengthens finding 1 rather than weakening it.

**One correction to the framing, not the facts**: the finding is scrupulously accurate that the
exposed/writable row belongs to the ADMIN'S OWN email, not another client's PII — this is
self-access, not a horizontal-privilege breach against a third party. The real defect is narrower
than "an operator can see a client's data": it's that (a) a presence check silently substitutes for
an authorization decision, (b) it produces an inconsistent identity state (an admin session
rendering as a client persona with `impersonating: False`) with no audit trail, unlike every other
impersonation path in this same function, and (c) it's live for exactly the org's own founder
account (`client_id=68`), which is precisely the coincidence the title calls out. "High" severity
is defensible on authorization-hygiene / audit-trail grounds even though no third party's PII is at
risk from this specific fallback branch.

### Finding 2 — Edge proxy portal gate checks cookie presence only
**STANDS**, and the live reproduction was independently re-run and matches exactly:
- `curl -sS -D - "https://my.balizero.com/portal"` (no cookie) → `HTTP/2 307`,
  `location: /portal/login-upgraded?redirect=%2Fportal`.
- `curl -sS -D - --cookie "nz_access_token=junk-not-a-real-jwt-12345"
  "https://my.balizero.com/portal"` → `HTTP/2 200`, `x-matched-path: /portal`.
- `proxy.ts:157-159` is exactly `Boolean(request.cookies.get(PORTAL_SESSION_COOKIE)?.value)`,
  `PORTAL_SESSION_COOKIE = "nz_access_token"` at line 78, used at the portal-domain gate at
  `259-280` precisely as described.
- `cookie_auth.py:80,100` confirms `domain=domain` on `set_cookie`, with `get_cookie_domain()`
  wired to `settings.cookie_domain` (`.balizero.com` in prod) — the cross-subdomain sharing claim
  holds.

**Context worth flagging (does not refute the finding)**: `proxy.ts:266-268`'s own comment states
this gate exists to "stop anonymous deep links before the client layout calls the profile API" and
"prevent the expected 401 from being reported as a browser console error" — i.e. it is documented
as a UX shim, not the security boundary; the actual authorization is `get_current_client()`
(finding 1), which does correctly reject non-clients/non-matching-superusers with 403/422. So on
its own, this finding does not describe an exploitable bypass of authorization — it describes a
consistency/defense-in-depth gap (an edge layer that could validate JWT shape/expiry cheaply and
doesn't). The finding does not overclaim exploitability, so it survives as stated; "medium" severity
is generous for a UX-declared shim but not indefensible as a hardening gap.

### Finding 3 — Portal layout catch-all treats 403 and 422 identically
**STANDS.** Verified verbatim:
- `layout.tsx:160-195`: the cookie-based auth branch's try wraps `api.portal.getProfile()`
  (lines 176-189); the `catch { … }` at **190-192** is empty except for a comment
  (`// Cookie auth also failed — redirect to login`); `router.replace(portalLoginHref(...))` sits
  unconditionally at **194**, outside any status-code check.
- `layout.tsx:149` (`if (error instanceof ApiError && error.statusCode === 401)`) is confirmed to
  be the ONLY status-code branch in the file, and it lives in the separate localStorage-token
  branch (138-156), not the cookie branch the finding is about.
- `client.ts:373-403`: both 403 (falls to the generic branch at 398-402) and 422 (special-cased at
  379-391 only for MESSAGE formatting, still constructs the same `ApiError` class with
  `statusCode` set) are thrown as the same `ApiError` type — confirmed, the 422 branch does not
  change control flow, only the error text.

**Context worth flagging (does not refute the finding)**: the blanket catch is also what makes the
ordinary-operator (403) case fail *closed* — no client data is ever rendered on an error, only a
silent redirect. So while the finding is right that diagnostic information is discarded (you can't
tell "wrong role" from "right role, no client selected" from the UI), the safety property (never
render unauthorized data) already holds regardless of this defect. "Low" severity is well-calibrated
for exactly that reason — it is an observability nitpick riding alongside two real, more consequential
issues (findings 1 and 2), not a standalone security hole.

## Summary
All three findings survive an independent correctness pass: every file:line citation matches the
code on disk verbatim, every quoted command output was independently reproduced (live curl against
production, and a fresh Postgres query rather than trusting the analyst's transcript numbers), and
no symptom was found to be already handled elsewhere or mistaken for its cause. The one adjustment
worth carrying forward is interpretive, not factual: finding 1's real teeth is authorization-hygiene
/ audit-trail-bypass on the admin's OWN record (plus a newly-confirmed write-path echo via `PATCH
/profile`), not a cross-client PII leak; findings 2 and 3 are each real but explicitly
lower-consequence layers sitting on top of finding 1's backend gate, which — when it fires for
non-matching identities — behaves correctly (403/422, fail-closed). The qwen second-opinion seat did
not return usable output (240s timeout, "Operation cancelled." only, both attempts) and is recorded
as unavailable rather than folded into the verdict.

## Adversarial review

Seat: **Codex `gpt-5.6-terra`** (OpenAI family, effort medium, read-only sandbox) — the
cross-family second opinion this file records as *unavailable* at the time it was written (`qwen`
exited 124 twice with only `Operation cancelled.`). It has now been obtained, and it did not
confirm this file's method.

Its central objection, which is accepted and applies to the file as a whole: **"STANDS. Every
citation checks out verbatim" proves transcription fidelity, not that the finding occurs in
production.** Re-reading a cited line establishes that the line says what was claimed. It does not
establish that the deployed configuration reaches that branch, nor that an authenticated superuser
request traverses it. Every verdict in this file rests on source review plus curl without a valid
identity, and should be read at that strength.

Specific objections, all standing:

1. "*no impersonation flag and no audit entry*" — the absence of a `_log_impersonation` call in that
   branch does not establish the absence of auditing; middleware, centralised logging or a DB
   trigger could record it.
2. "*It's live for exactly the org's own founder account*" — the DB query shows a matching row and
   the code shows a configuration fallback; neither shows the production allowlist's contents nor
   that the account can obtain the required token.
3. "*the cross-subdomain sharing claim holds*" — `set_cookie` code plus a declared configuration is
   not the same as the attributes actually emitted in production.
4. "*a presence check silently substitutes for an authorization decision*" — the branch already sits
   behind authentication and a superuser allowlist, so this is a policy judgement, not a
   demonstrated fact. It may be an intended fallback for an operator who also holds a client record.
5. "*no symptom was found to be already handled elsewhere*" — broader than the method can support.

The replay prompt is shipped alongside this file (`*.refute-prompt.txt`) so the original review can
still be run against a healthier seat.
