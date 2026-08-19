---
date: 2026-08-19
domain: compliance
client_case: none
sources:
  - apps/backend-rag/backend/app/routers/portal.py (get_current_client, ?as_client branch)
  - apps/backend-rag/backend/services/portal/_rbac.py
  - apps/backend-rag/backend/services/security/audit_service.py
  - apps/mouth/src/lib/api/client.ts + src/contexts/AdminImpersonationContext.tsx
  - apps/backend-rag/backend/db/migrations_v2/236_portal_documents_purpose_softdelete.sql
adversarial_review: qwen
---

# Impersonation: an operator can act as a client, and nothing in the data or the code says so

This is the literal subject of the mandate — an operator becoming a user — and it is the most
consequential cluster the simulation found. Four claims, each verified independently by a
cross-family seat (Qwen 3.8 Max, Alibaba Token Plan) that was instructed to refute them. All four
survived; two came back **stronger** than they went in.

## The compound condition, in one sentence

A superuser in `ADMIN_EMAILS` can act as any client with full write authority; the mutated rows
carry the client's identity and not the operator's; the only trace is an audit table no code ever
reads; and the frontend impersonation state survives logout and re-arms on the next login.

## C1 — Writes made while impersonating carry the client's identity, never the operator's

`portal.py` (superuser `?as_client` branch) returns a context whose `email` is the **target
client's**; the operator's email goes only to the audit log. Every portal mutation then resolves
the actor from that context or from the client's own row:

- `_mixins/messaging.py` `send_message` → `INSERT INTO portal_messages (... sent_by)` with the
  client's email, direction `client_to_team`.
- `_mixins/documents.py` `upload_document` → `uploaded_by` = client's email, `uploaded_source` = `'client'`.
- `_mixins/documents.py` `soft_delete_document` → `deleted_by` = the context email, i.e. the client's.
- `_mixins/billing.py` `update_profile` → side effects write `"Client updated their profile: …"`.

The refuting seat tried to find one write path that stamps the operator and found none: the only
operator-derived field in the context (`user_id`) is consumed by no writer at all — zero matches
repo-wide in `backend/services`.

**The sharpest evidence is one the original analysis missed.** Migration
`236_portal_documents_purpose_softdelete.sql` documents the `deleted_by` column as *"Who
soft-deleted (client email or impersonating superuser)"*. That second half is a capability the
code never delivers: on the `?as_client` path the context email has already been overwritten with
the client's, so an impersonating superuser can never land there. **The schema comment promises a
traceability that does not exist** — and it is exactly the kind of comment someone reads during an
incident to decide whether they can tell who did what.

**Correct scope.** Distinguishability exists only *outside* the rows — in `security_audit_log`,
which C2 shows nothing reads.

## C2 — The impersonation audit trail is write-only

`SecurityAuditService` exposes exactly **one** method, `log_event`, which executes an `INSERT`.
There is no query method. Repo-wide, `security_audit_log` appears 45 times: the creating migration,
a QA schema mirror, the `INSERT`, tests asserting the `INSERT`, docstrings, research manifests.
**No `SELECT ... FROM security_audit_log` anywhere** — not in backend-rag, not in mouth, not in the
admin dashboard, not in the MCP servers.

The claim is precisely scoped: a human running ad-hoc SQL could read it. No program does, so the
trail cannot feed a UI, an alert, or a gate. It is a record kept for a reader who does not exist.

## C3 — There is no write-block during impersonation

Every mutating portal endpoint takes the identical dependency as the read endpoints, with no
impersonation guard: company select, document upload, document delete, document restore, send
message, mark read, patch settings, patch profile — all `Depends(get_current_client)`.

The defensive service-layer decorator (`_rbac.py`) does not merely fail to block writes: it
**explicitly authorizes** them. Its only restriction is target-mismatch, never read-vs-write, and
`test_rbac_defensive.py` codifies "superuser impersonating a client → allowed" as intended
behaviour. So this is a deliberate design, not an oversight — which is worth stating plainly,
because the remedy is a decision, not a bug fix.

Concretely, an operator "viewing as" a client can send messages as them, upload/delete/restore
their documents, change their notification settings, phone, WhatsApp and address, and flip their
primary company.

**Correct scope.** CSRF double-submit protection applies, the superuser set is bounded by
`ADMIN_EMAILS`, and each hit is audit-logged. The defect is the absence of *prevention*, with
detection limited to the unread trail of C2.

## C4 — Impersonation survives logout, and the next operator inherits it

`logout()` calls `clearToken()`. `clearToken()` nulls the token, CSRF token and user profile, and
removes `auth_token` and `user_profile` from storage. It does **not** remove the impersonation key
`bz_portal_impersonation_v1`, and does not reset the in-memory id that is injected into every
`/api/portal` request. `AdminImpersonationContext` then restores it from localStorage on mount and
immediately re-applies it. The same gap exists on the token-expiry path.

**The danger the original analysis did not name:** after logout → login in the same browser, every
portal call silently carries `as_client=<id>` again — including when a **different** superuser logs
in, who inherits the previous operator's active target without ever choosing it. That is an
operator-to-operator handoff through stale state, which is precisely the alternation this
simulation set out to exercise.

**Correct scope.** Server-side authority is per-request (JWT + `?as_client`), so nothing executes
while logged out, and a subsequent non-superuser login renders the leftover parameter inert. The
defect is residual client-side state that silently re-arms impersonation across sessions — not a
token that keeps working.

The logout integration test asserts token/auth/profile/CSRF clearing and does not cover
impersonation state, which is why the gap is invisible to CI.

## Adversarial review

The four claims were produced by a Sonnet lane and refuted by **Qwen 3.8 Max (Alibaba Token
Plan)** on fresh context, instructed to default to "the claim is defective". It opened every cited
file, ran its own repo-wide greps, and returned STANDS on all four with additional evidence on C1
(migration 236) and C4 (the cross-operator inheritance).

**Declared weakness of the first pass, and the mechanism — measured, not assumed.** The workflow's
own refutation stage reached **no** external seat: all twelve lanes reported the seat
`unavailable`. My first explanation was that the worktree-isolation hook had *blocked* the prompt
write. Checking both directories falsifies that:

| Artifact | Written at | Landed in |
|---|---|---|
| `s1/s2-*.md` (stage 1) | 14:03–14:04 | repo **main checkout** |
| `*.refute-prompt.txt`, `*.refutation.md` (stage 2) | 14:07–14:17 | the **worktree** |

The prompts are 6 373 and 5 228 bytes — full, not empty. Nothing was blocked. A worktree was
created at 13:58, between the two stages, and from then on the same path string resolved somewhere
else: the lane's `Write` **succeeded**, the file **exists**, and the shell `cat "$OUT/…"` two lines
later read the original path and found nothing. An empty prompt reached the seat, which correctly
reported it had nothing to review.

The class is worth naming, because it is the same one this whole simulation keeps finding: **a
silent path redirect is worse than a block.** A block tells you that you are off the road. A
redirect returns success, leaves a real file on disk, and breaks the reader — with no error
anywhere pointing at the cause. The isolation hook is a safety feature working as designed; it
severed the data path of the audit that was running through it.

Consequence: every verdict from that first pass is **same-family** (Sonnet grading Sonnet), which
is the precise weakness the organism has already been bitten by. The cluster in this file is the
portion since re-refuted cross-family; the remaining scenarios have not been, and are marked as
such in the index.

## What is NOT claimed

- No third-party client data was shown to be exposed by this cluster. C1–C4 describe an authorized
  superuser acting within a bounded admin set.
- No exploit path from an unauthenticated or client-role caller was demonstrated.
- The impersonation *entry* authorization was examined and found sound; it is recorded as a clean
  result, not a finding.

## Remedy — the decision is the owner's

C3 is a design choice, so the first question is a business one, not an engineering one: **should
"view as client" be able to write at all?** The three plausible answers — read-only impersonation,
write-allowed-but-stamped, write-allowed-and-announced-to-the-client — have different consequences
under UU PDP, and that makes this `operator[business]`.

Whatever the answer, three repairs stand on their own:

1. **C4 is unambiguously a bug** and is in perimeter: `clearToken()` must clear the impersonation
   key and the in-memory id, and the logout test must cover it. Cross-operator inheritance of an
   impersonation target has no defensible reading. **Shipped and proven live** — the served bundle
   on both hosts now carries
   `clearToken(){…this.portalImpersonationClientId=null,…try{localStorage.removeItem(s)}catch{}}`
   with `s="bz_portal_impersonation_v1"`.

   Proving that took three wrong answers first, and they are worth recording because each is a way
   a deploy check lies. (i) A first pass declared the deploy healthy on the strength of both
   subdomains resolving to the same deployment id and the pages rendering — the deployment was
   built from a commit merged nearly three hours *before* the fix. (ii) Two probes of the served
   JavaScript returned "not live" while actually measuring nothing: under `zsh`, `for c in $chunks`
   does not word-split, so the loop ran once against a garbage URL. (iii) A corrected probe found a
   `clearToken()` genuinely lacking the cure — belonging to `PublicAuthClient`
   (`lib/api/public-auth.ts:99`), a separate transport for unauthenticated screens, which correctly
   has no impersonation state to clear. The decisive method is: fetch with the cache defeated
   (`x-vercel-cache` must not be `HIT`), download every referenced chunk and assert the downloaded
   count equals the referenced count, then match `removeItem` **applied to** the key — never the
   bare string, which lives on the read path and predates the fix.
2. **C1's schema comment must stop promising what the code does not do** — either stamp the actor
   on the row, or correct the comment. A comment consulted during an incident is worse than no
   comment when it is wrong.
3. **C2**: a trail nothing reads is not a control. Either something reads it (an alert on
   impersonated writes, a surface in the admin dashboard) or it should stop being cited as the
   mitigation for C1 and C3 — which is how it currently functions in the code's own reasoning.
