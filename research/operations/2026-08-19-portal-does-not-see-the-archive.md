---
date: 2026-08-19
domain: operations
client_case: none
adversarial_review: codex
sources:
  - apps/backend-rag/backend/app/routers/crm_clients.py
  - apps/backend-rag/backend/app/routers/portal.py
  - apps/backend-rag/backend/services/portal/_rbac.py
  - apps/backend-rag/backend/services/portal/_mixins/
---

# Archiving a client on kita revokes some of the portal and not the rest, and nothing decides which

Simulating the operator↔client alternation: an operator archives a client on `kita.balizero.com`,
then asks what that client still sees on `my.balizero.com`. There is no single answer, and that is
the finding. Whether an archived client can still reach a given portal surface depends on whether
the individual method that serves it happens to look the client row up — because the one place all
of them pass through does not.

## What archiving writes

`DELETE /api/crm/clients/{client_id}` (`crm_clients.py:1801`) is a soft delete:

```sql
UPDATE clients
SET status = 'inactive', updated_at = NOW(), deleted_at = NOW()
WHERE id = $1 AND deleted_at IS NULL
```

It writes `clients` and `activity_log`. It does **not** touch `team_members` — that string appears
in the whole of `crm_clients.py` exactly **once**, at line 730, in a comment about auto-creating the
portal profile when a client is *created*.

## The client can still log in

The portal auth gate (`portal.py:233-246`) reads:

```sql
SELECT id, email, full_name, linked_client_id, portal_access
FROM team_members
WHERE id = $1 AND role = 'client' AND active = true
```

then rejects on `not portal_access` and on a missing `linked_client_id`. It never consults
`clients.deleted_at`. Archiving does not touch `team_members`, so **login is unaffected**.

## The chokepoint exists and it is the wrong kind of check

Every client-scoped service method — **22** of them — wears `@require_client_access`
(`services/portal/_rbac.py:117`). Read what it does: it binds the call signature, pulls
`current_user["client_id"]`, compares it to the method's `client_id` argument, and handles the
impersonation case. It performs **zero database queries**.

That is an *authorization* check — "is this client_id yours?" — and archival is not an authorization
question, so it cannot answer it. Every method that wants to know whether the client is still live
has to ask on its own. Some do; some never thought to.

## Who asks and who doesn't

Measured per function across the four `_mixins` files that mention `clients` or `deleted_at`
(12 functions classified; the remaining methods of the 22 do not reference either and were not
classified):

| verdict | functions |
|---|---|
| **verifies the client row is live** | `get_dashboard` · `get_visa_status` · `upload_document` · `send_message` · `_get_profile_data` · `_val` |
| **never reads `clients` at all** — cannot notice archival | `get_documents` · `download_document` · `soft_delete_document` · `restore_document` |
| **reads `clients`, no liveness filter** | `get_company_detail` · `_notify_lead_about_document` |

Plus the router itself. `portal.py` reads the `clients` table in exactly **three** places, and none
of the three filters `deleted_at`:

| line | function | what it exposes |
|---|---|---|
| 165 | `get_current_client()` | superuser's own linked profile |
| 191 | `get_current_client()` | the `?as_client=<id>` **impersonation target** |
| ~1128 | `get_profile()` | `passport_expiry`, `date_of_birth`, `gender`, `address` |

## What an archived client can still do

- **log in**
- **read their full profile, PII included** — `GET /portal/profile` (`portal.py:1092`)
- **list and download their documents** — `get_documents`, `download_document`
- soft-delete and restore documents
- see company detail

## What correctly refuses

`get_dashboard`, `get_visa_status`, `send_message`, `upload_document`, and
`PATCH /portal/profile` all resolve the client row with `deleted_at IS NULL`, raise `ValueError`, and
the router converts it to a **404 Client not found**. `portal.py:305-309` carries the reasoning:

> `# BUG C: get_dashboard raises ValueError("Client X not found") when the linked client row is`
> `# gone / soft-deleted … surface 404 so a soft-deleted client's portal doesn't 500 the whole dashboard.`

## The asymmetry, on one resource

| route | path | liveness check | archived client gets |
|---|---|---|---|
| `GET /portal/profile` (`portal.py:1092`) | raw SQL in the router | **none** | the full profile, PII included |
| `PATCH /portal/profile` (`portal.py:1185`) | `PortalService` | yes | `404 Client not found` |

Same resource, two verbs, opposite answers about whether this client exists. The write refuses; the
read serves.

## Meta-pattern

The operator's action and the client's surface **disagree about what "archived" means** — and the
disagreement is not even consistent within one surface.

The structural cause is precise: there is exactly one chokepoint every client-scoped method passes
through, and it answers *"is this client_id yours?"* — not *"is this client still a client?"*.
Because the chokepoint cannot express liveness, liveness became a per-method convention, and a
convention is only as good as the last person who remembered it. Twelve methods, six remembered.

The quieter shape sits in the router: `portal.py` contains the string `deleted_at IS NULL` **twelve
times, all twelve inside comments, zero in SQL**. The comments are accurate — they describe what the
service does for the routes they annotate — but reading that file alone, the archive looks handled
everywhere. The evidence that it is handled lives in another directory; the evidence that it is not
lives in three lines that never mention it.

## Second-order consequence (not re-derived here)

A sibling note from the same day —
`research/operations/2026-08-19-crm-upsert-by-phone-duplicate-advisory.md` — measured that the live
`com.balizero.wa-mirror-auto-promote` job calls `upsert-by-phone` on the endpoint defaults, and that
on an all-archived phone-core collision the endpoint runs `deleted_at = NULL` (`crm_clients.py:1427`),
un-archiving a card chosen by recency; 390 collision groups are in that state. Read together with
the above, an inbound WhatsApp message can restore the surfaces archival did revoke, with no operator
involved. That claim rests on the sibling note's measurements and is cited, not repeated.

## Open questions (`operator[business]` — deliberately not answered)

1. **Is archiving meant to revoke portal access at all?** If `deleted_at` is CRM list-hygiene and
   revocation is meant to run through `team_members.active` / `portal_access`, then login is correct
   by design and the defect is only the scattered data paths. If archiving means "this client is
   gone", the auth gate is wrong too. Different readings, different fixes.
2. **Document download by an archived client** — is that intended? It is the sharpest item on the
   list: `get_documents` and `download_document` never read `clients`, so no amount of archiving
   reaches them.
3. **Should a superuser impersonate an archived client?** `get_current_client()` resolves
   `?as_client=<id>` with no liveness filter and writes an impersonation audit record. Plausibly
   deliberate — reviewing a closed file — but currently implicit rather than decided.

## Adversarial review

Seat: **Codex `gpt-5.6-terra`** (`model_reasoning_effort=medium`, `--sandbox read-only`), run against
the first draft with instructions to verify every file:line on disk and report only defects. It
returned `VERDICT: FIX` with one objection, and the objection **destroyed the draft's central claim**.

The draft asserted that the portal "guards the archive on every path that goes through its service
layer", framing the defect as *mediated path guards / direct path doesn't*. The seat answered that
`require_client_access` only compares client ids and never checks `clients.deleted_at`, and that
`get_documents`, `download_document`, `soft_delete_document` and the messaging/preferences routes
never read `clients` at all — so an archived client can still list and download documents.

Verified on disk before accepting, and the seat was right on both counts:

- `_rbac.py:117-175` performs zero database queries — pure signature binding and id comparison.
- A per-function scan of the four `_mixins` files gives 6 guarded / 4 that never read `clients` /
  2 that read it unguarded, exactly as the seat described.

The draft's error had a specific cause worth recording: I counted the string `deleted_at IS NULL` in
`services/portal/` (nine occurrences), and concluded the layer guarded the client row — **without
checking which table each filter was on**. Six of the nine guard `clients`; the other three
(`_mixins/documents.py:209, 256, 397`) guard the `documents` table's own soft-delete column, which
says nothing about the client. Counting a string and inferring a property is the same failure the
sibling note records under a different disguise: the token was there, the entity was not.

One measurement error of mine surfaced during the rewrite and is noted for the next reader: an
earlier `find … | head` listed ten files and I read the layout as flat, when `billing.py`,
`documents.py`, `dashboard.py` and `messaging.py` all live in `_mixins/`. Third truncation-induced
mistake of the session.
