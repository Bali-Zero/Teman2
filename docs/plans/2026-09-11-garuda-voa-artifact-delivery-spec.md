# GARUDA VOA — the artifact: what it is, who owns it, who may read it, how it is served, how long it lives

> Window **W3A** of `docs/plans/2026-09-11-garuda-voa-final-spec.md` §3. This file is phase 1 of
> that window: the spec the phase-2 build is written against. It changes no code and no contract —
> `products/garuda-voa/contracts/openapi.yaml` belongs to **W3C** until its PRs merge, and phase 2
> starts from a fresh `origin/main` only after they do.
>
> It closes the _specification_ half of the `PENDING-ARMS.md` row opened 2026-09-02
> (`ops/garuda-voa-step8-portal`, codex-gpt-5.6-sol council finding #3): _"the staff transition
> engine records OPAQUE evidence/artifact ids and never verifies their content nor serves the
> artifact."_ That row's arming step is a contract change **plus** an engine check; this file
> specifies both so the phase-2 PR is an implementation, not a design.
>
> Every fact in §1 was measured on the worktree at base `c0a4a3bffe` on 2026-09-11. Nothing here is
> recalled from a previous session. §2–§7 were then read adversarially by two seats outside the
> drafting chain; §8 records what they found, what was accepted, and what was rebutted with a
> measurement rather than an argument.

---

## 1. What is actually there today (measured, not recalled)

| #   | Fact                                                                                                                                                                                                                                                                                                                                                                                                              | Where                                                                                                                                                                                                                             |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `garuda_practices` carries `artifact_id TEXT`, `artifact_digest TEXT`, `artifact_available BOOLEAN NOT NULL DEFAULT FALSE`.                                                                                                                                                                                                                                                                                       | `apps/backend-rag/backend/db/migrations_v2/287_garuda_practices.sql:84-86`                                                                                                                                                        |
| 2   | A table CHECK makes the three columns and the state agree: `(state = 'Delivered') = (artifact_id IS NOT NULL AND artifact_digest IS NOT NULL)`.                                                                                                                                                                                                                                                                   | `287_garuda_practices.sql:105`                                                                                                                                                                                                    |
| 3   | The only validation the engine performs on PR-11 is **shape**: `artifact_id` must match `_ID_PATTERN`, `artifact_digest` must be a 64-character string. Not a hex check, not an existence check, not a content check.                                                                                                                                                                                             | `services/garuda_portal/staff_transitions.py:148-157`                                                                                                                                                                             |
| 4   | On acceptance the engine writes both columns and sets `artifact_available = TRUE` unconditionally.                                                                                                                                                                                                                                                                                                                | `staff_transitions.py:264-266`                                                                                                                                                                                                    |
| 5   | The customer wire shape deliberately **omits** `artifact_id`/`artifact_digest` (PR-F04) and exposes only the boolean `artifact_available`.                                                                                                                                                                                                                                                                        | `services/garuda_portal/practice.py:111-124`                                                                                                                                                                                      |
| 6   | The `practice_delivered_email` body is the shared `_practice_transition_body`: one sentence plus the **tracker** link `{TRACKER_BASE}/{order_id}`. There is no artifact link in any of the seven transition emails.                                                                                                                                                                                               | `services/garuda_orders/outbox_handlers.py:1336-1352`, `:1390-1394`                                                                                                                                                               |
| 7   | The customer principal is the magic-link session; `_require_magic_session_actor` returns the session's `result_id`, and every customer read filters on `garuda_orders.result_id_ref = actor`.                                                                                                                                                                                                                     | `app/routers/garuda_orders_router.py:221-256`, `:476-492`                                                                                                                                                                         |
| 8   | In the **customer** lane an ownership miss is **404 `ORDER_NOT_FOUND`**, never 403 — the catalog has no `ACCESS_DENIED` member at all, by construction: the lane never discloses that a foreign order exists.                                                                                                                                                                                                     | `garuda_orders_router.py:177-193`, `:482-483`                                                                                                                                                                                     |
| 9   | In the **staff** lane both shapes exist: 404 `PRACTICE_NOT_FOUND` for absent, 403 `ACCESS_DENIED` via `visible_or_403` for visible-but-not-mine.                                                                                                                                                                                                                                                                  | `app/routers/garuda_staff_router.py:119-126`, `:362-364`, `:388`                                                                                                                                                                  |
| 10  | The frozen contract declares **16** operations. None of them retrieves an artifact (`grep -c 'operationId: getPracticeArtifact'` → `0`).                                                                                                                                                                                                                                                                          | `products/garuda-voa/contracts/openapi.yaml`                                                                                                                                                                                      |
| 11  | `garuda_practice_evidence` (305) binds an `evidence_id` to a practice and a transition for `kind IN ('filing','approval','rejection')`. It has no artifact kind and no digest column — 305's own header says so deliberately, because the artifact columns already live on `garuda_practices`.                                                                                                                    | `305_garuda_practices_assignment.sql:40-48`, `:145-174`                                                                                                                                                                           |
| 12  | **`garuda_documents` (304, unmerged) is not the artifact store.** Its own table comment: _"GARUDA VOA document-upload intake (product step 5) … Never stores raw document bytes or extracted passport field VALUES"_. It is an idempotency/outcome cache, explicitly placed in the same retention tier as `garuda_order_idempotency`.                                                                             | `304_garuda_documents.sql:129-136`, `:140-171` — **not on `main`**: read it with `git show origin/agent/air-m5/ops/garuda-voa-documents:apps/backend-rag/backend/db/migrations_v2/304_garuda_documents.sql` (PR #5526, suspended) |
| 13  | **No storage anywhere in this repository holds a delivered artifact's bytes.** The only object store wired into the backend is Tigris (`https://fly.storage.tigris.dev`) bucket `nuzantara-warroom-images`, whose module docstring states its prefix is **public-read** and whose purpose is minting public HTTPS URLs.                                                                                           | `services/canva_renderer_v2/_tigris.py:1-22`, `app/routers/asset_upload.py:1-18`                                                                                                                                                  |
| 14  | The signed retention row is `garuda-document-privacy-v1`: PRODUCTION / `GARUDA_DOCUMENT` / **30 days** / **`CREATED_AT`** / approved by Zero.                                                                                                                                                                                                                                                                     | `docs/plans/2026-09-03-relaunch-lanes/ZERO-DECISIONS.md:19`                                                                                                                                                                       |
| 15  | **Exactly one practice per order, structurally**: `garuda_practices.order_id` is `NOT NULL UNIQUE`, and the migration says so in its own comment. One order carries one applicant email.                                                                                                                                                                                                                          | `287_garuda_practices.sql:46`, `:90`, `:114`                                                                                                                                                                                      |
| 16  | **The frozen paths are lane-split by key**: every customer path is order- or result-scoped (`/orders/{order_id}`, `/eligibility-checks/{result_id}/documents`) and **no customer path carries a `practice_id`**; every practice-keyed path lives under `/staff/` (`/staff/practices/{practice_id}/assignment`, `/transitions`). `documents` as a sub-resource name is already taken by intake.                    | `products/garuda-voa/contracts/openapi.yaml`, the 14 `paths:` entries                                                                                                                                                             |
| 17  | **The frozen `DeliverPracticeTransition` schema REQUIRES both artifact fields** — `required: [transition_id, artifact_id, artifact_digest]` with `additionalProperties: false` — and constrains the digest to `^[a-f0-9]{64}$`. The contract is therefore **stricter than the engine**, which only checks length (fact 3): a mixed-case or non-hex 64-character string passes the code and violates the contract. | `products/garuda-voa/contracts/openapi.yaml:1837-1846`                                                                                                                                                                            |
| 18  | Every operation declares `x-feature-flag: GARUDA_PUBLIC_ENABLED`, folds `GARUDA_PUBLIC_DISABLED` into its 404 bucket alongside the resource's own not-found code, and declares a 500 `INTERNAL_ERROR` and a 503 `SERVICE_UNAVAILABLE`, each with an `x-error-codes` array.                                                                                                                                        | `openapi.yaml:834-884` (`getStaffPractice`, representative)                                                                                                                                                                       |

### 1bis. What those facts add up to

`artifact_id` is not merely unverified — **it has no referent**. There is no table, no bucket and no
route in which an id could be resolved to bytes. Fact 2's CHECK therefore enforces a correspondence
between a state and two strings, not between a state and a document; and fact 5 means the customer
is shown `artifact_available: true` on the strength of fact 4's unconditional assignment. A staff
user who types sixteen arbitrary characters and sixty-four more moves a practice to `Delivered`,
fires fact 6's _"your document is ready"_ email, and the customer is told a document exists that
nothing in the system has ever held.

That is the whole defect. It is not a missing endpoint; it is a missing object.

---

## 2. What an artifact IS

**One immutable file, at most one live per practice: the deliverable Bali Zero hands the customer at
the end of a VOA practice** (the e-VOA grant or its equivalent official output).

It is defined by exclusion as much as by inclusion:

- It is **not** the customer's intake uploads. Those are step 5, they live under `garuda_documents`
  (fact 12), they are produced by the customer, and they are already covered.
- It is **not** evidence. `garuda_practice_evidence` (fact 11) records the staff's own audit trail
  for filing/approval/rejection; evidence is never served to a customer and keeps its own lifecycle.
- It is **not** a rendering, a preview, a thumbnail or a derived copy. One practice, one live file,
  one digest, no variants — variants multiply the surface on which a digest can drift from its bytes.

**Immutability is structural, not conventional.** An artifact is written once; a correction is a new
artifact with a new id and a new digest, and the practice points at the new one. Nothing overwrites
bytes under a live id, because a customer who has already downloaded a file must be able to
establish which bytes they were given.

**Superseded artifacts are a named state, not an orphan.** When a correction supersedes an artifact,
the superseded row is marked `superseded_at` and its object is deleted **immediately**, not left to
the retention sweep: a withdrawn travel document must stop being retrievable the moment it is
withdrawn. The row survives as a record that bytes once existed under that id; a read against a
superseded id answers as if it had expired (§4, row 4). Only one row per practice may have
`superseded_at IS NULL` — a partial unique index, so "one live artifact per practice" is a database
fact and not a convention.

**Identity.** `artifact_id` keeps the existing `^[A-Za-z0-9_-]{16,128}$` shape (fact 3) so no
already-written row becomes invalid, but phase 2 **generates** it server-side rather than accepting
it from a staff form. `artifact_digest` is the lowercase-hex SHA-256 of the exact bytes stored —
sixty-four characters, which is why fact 3's length test happens to be right for the wrong reason.

---

## 3. Who OWNS it

Three distinct ownerships, and conflating them is how the current state came about.

**The bytes.** A **private** Tigris bucket, `garuda-voa-artifacts`, on the endpoint the backend
already speaks (`https://fly.storage.tigris.dev`) but **separate from `nuzantara-warroom-images`**
and never public-read. Fact 13 is the trap in plain sight: the only bucket already wired exists
precisely to mint public URLs, and reaching for it would publish a passport-bearing document to the
open internet. Key layout `artifacts/{environment}/{practice_id}/{artifact_id}`, so a purge is a
prefix delete and a stray key cannot be guessed from an order id.

_Provisioning is not a session's to do_: the bucket and a **scoped** credential pair — scoped to
this bucket alone, not the fleet-wide `AWS_ACCESS_KEY_ID` that today reaches the public bucket — are
`operator[secret]`. Phase 2 reads them under their own env names and fails closed, service-unavailable,
when they are absent; it never falls back to the public bucket's credentials.

**The row.** A new table `garuda_practice_artifacts`, owned by `backend_rag_v2` like every other
`garuda_*` table, one row per artifact, retention-bound through the shared authority
`visa_decision_retention_policies` exactly the way 281/285/304 bind theirs — never a bare TTL
column. It carries the storage key, the digest, the byte length, the content type, the producing
staff actor, the `practice_id`, `superseded_at`, and `created_at` from the transaction clock.

_"Append-only" is a grant, not an adjective._ The runtime role holds `INSERT` and `SELECT` on this
table and on nothing else; `UPDATE` is granted for the single column `superseded_at` and `DELETE` is
not granted at all. Expiry deletion runs under the retention sweep's own role (§6). A spec that says
"append-only" and leaves the runtime role able to `DELETE` has described a wish.

**The document, as a business object.** Bali Zero produces it; the customer is its subject and its
recipient. The customer is never given a write path to it and the staff are never given a delete
path — withdrawal is supersession (§2) and expiry is the sweep's (§6).

**Producer, and the path that makes PR-11 possible at all.** An artifact is created by a **separate,
earlier staff operation**, not by the transition:

> `PUT /api/visa/voa/staff/practices/{practice_id}/artifact` → `operationId: putPracticeArtifact`,
> staff lane, `Idempotency-Key` required — a practice-keyed sub-resource beside the `/assignment`
> and `/transitions` the staff lane already exposes (fact 16). It accepts the bytes, computes the digest **server-side**,
> writes the object, then the row, and returns the generated `artifact_id` and `artifact_digest`.

PR-11 then consumes what this produced (§5). Without this operation the transition has nothing to
resolve and the whole design is circular — the first reader found exactly that hole in an earlier
draft (§8, G-1). Only a staff session that already passes `visible_or_403` for the practice may call
it.

---

## 4. Who may READ it

Two principals, **two routes** — never one route that multiplexes two authentication schemes.

**(a) The customer — the magic-link session bound to that practice**, through the customer lane's
own route. The predicate is the one that already exists (fact 7): the session's `result_id` must
equal the `result_id_ref` of the `garuda_orders` row the practice hangs off. No second predicate, no
email comparison, no token in a URL. It is enforced in the same `WHERE` clause that loads the
artifact row, never as a check performed after a successful load. This is the binding the window's
success bar names.

_One order is one practice is one applicant_ (fact 15), so there is no co-traveller on a shared order
who could read a neighbour's document: a group booking is N orders, N sessions, N artifacts. This was
raised as a leak by the first reader and is answered by the schema, not by policy (§8, G-5).

**(b) Staff**, through the **staff** lane's own route —
`GET /api/visa/voa/staff/practices/{practice_id}/artifact`, `operationId: getStaffPracticeArtifact`
— under staff session auth and `visible_or_403` (fact 9), for support purposes. Staff reads are audited with the
acting actor; customer reads are counted without identity.

**(c) Nobody else, and the failure mode is specified, not left to the implementation.**

| caller                                                                | outcome                                                 | why                                                                                                                                                                                                                                                                                                                                            |
| --------------------------------------------------------------------- | ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| no session                                                            | **401 `SESSION_REQUIRED`**                              | fact 8's catalog member, unchanged                                                                                                                                                                                                                                                                                                             |
| a _different_ magic-link session                                      | **404 `ORDER_NOT_FOUND`**                               | **not 403.** Fact 8: the customer lane has never had an `ACCESS_DENIED`, deliberately — answering 403 would confirm to a stranger that this order exists. The staff lane's 403 (fact 9) is correct _there_ because staff already know the population. Reusing the existing code rather than minting one is what the order-keyed path buys (§5) |
| the right session, artifact not yet produced                          | **404 `ORDER_NOT_FOUND`**                               | same shape, and it costs the customer nothing: the tracker already carries `artifact_available` (fact 5), so a legitimate client distinguishes "not ready" from "not mine" **before** it ever calls this route. The error does not have to carry a signal the model already publishes                                                          |
| the right session, artifact superseded or expired                     | **404 `ORDER_NOT_FOUND`**                               | a document that no longer exists must not look like a document the caller is not allowed to see                                                                                                                                                                                                                                                |
| the right session, row present but bytes missing or digest mismatched | **503 `SERVICE_UNAVAILABLE`, retryable**, plus an alert | never a partial or unverified stream (§5)                                                                                                                                                                                                                                                                                                      |

A presigned URL, a signed token in an email, or any other bearer credential that travels outside the
session is **forbidden** — it recreates exactly the property this window exists to remove, namely an
artifact reachable by whoever holds a string.

---

## 5. How it is SERVED

**Fetch, verify, then emit. One route per lane.**

`GET /api/visa/voa/orders/{order_id}/artifact` → `operationId: getPracticeArtifact`, customer tag,
added to the frozen contract by phase 2 **after W3C's contract PRs have merged**.

**The path is ORDER-keyed, and that is not cosmetic.** Fact 16: no customer path in the frozen
contract carries a `practice_id` — practice-keyed paths live under `/staff/`. Keying the customer
read by `order_id` keeps the path parameter and the ownership predicate the _same_ value
(`garuda_orders.result_id_ref = actor`, fact 7), so authorisation cannot drift from routing; it
keeps the customer's URL space consistent with `getOrderAndPractice`, which is where the customer
learns `artifact_available` in the first place; and it means an ownership miss reuses the catalog's
existing **`ORDER_NOT_FOUND`** (fact 8) instead of importing a new error code into a lane that has
deliberately never had one. An earlier draft put this at `/practices/{practice_id}/artifact` and
would have contradicted the frozen hierarchy on both counts (§8, K-1).

- Response `200`: `application/pdf`, `Content-Disposition: attachment; filename="..."`,
  `Cache-Control: no-store`, plus the router's existing `_privacy_headers()` — one helper, not a
  second copy (`garuda_orders_router.py:163`).
- **The digest is verified before the first byte reaches the client.** The object is fetched into
  memory, hashed, and compared against `artifact_digest`; only on a match does the response begin.
  A chunked stream that hashes as it goes cannot do this — by the time the mismatch is known the
  client already holds most of an unverified file, and the status line has already said `200`. The
  first reader named this and it is accepted (§8, G-4). An explicit byte ceiling (rejecting an
  oversized object at write time in §3) is what keeps buffering safe; a VOA grant is a document,
  not a video.
- No redirect to storage, ever. The bucket is private (§3) and the backend is its only reader.
- Errors carry the three contract fields (`code`, `retryable`, `message_key`) through the same
  `_error()` path every other code in the lane uses.
- **The operation declares what its 16 siblings declare** (fact 18), and §4's table is the
  lane-specific part of it, not the whole of it: `x-feature-flag: GARUDA_PUBLIC_ENABLED`;
  `GARUDA_PUBLIC_DISABLED` folded into the 404 bucket beside `ORDER_NOT_FOUND`; a 500
  `INTERNAL_ERROR`; a 503 `SERVICE_UNAVAILABLE`; `x-error-codes` arrays on each. A binary body is
  also the first in this contract, so it declares `content: application/pdf: schema: {type: string,
format: binary}` and names `Content-Disposition` as a response header — JSON-only siblings never
  had to (§8, K-3).

**The `delivered` email.** Fact 6's body gains a second link beside the tracker: _"Download my
document"_, pointing at the same customer-facing artifact URL. The link carries **no** token. An
expired session lands on the magic-link re-issue path W4C owns — the recovery is the existing one,
never a second authentication route.

**And `Delivered` becomes impossible without a retrievable artifact — without breaking the frozen
request schema.** The first draft said PR-11 would stop accepting the two fields from the request
body. That would have been a breaking change to `DeliverPracticeTransition`, which is
`required: [transition_id, artifact_id, artifact_digest]` under `additionalProperties: false`
(fact 17), and the second reader was right to call it a hidden contract change declared as one added
GET (§8, K-2).

The fields stay. **What changes is what they mean: an assertion the server CHECKS, not a claim it
RECORDS.** The staff client already holds the pair — `putPracticeArtifact` returned it (§3). Inside
the same transaction as the CAS state update, PR-11:

1. resolves the live (non-superseded) artifact row for this practice,
2. requires the submitted `artifact_id` **and** `artifact_digest` to equal that row's,
3. confirms the stored object exists and its digest matches the row,
4. only then writes the columns and `artifact_available = TRUE`.

A fabricated, stale, superseded or mismatched pair is rejected with **422 `INVALID_REQUEST`** before
any state moves and before any email is enqueued. That is the ledger row's own `proof-of-armed`, and
it is the assertion `test_staff_router_transitions.py` must carry. No schema changes; a field that
was the source of truth becomes a field the server refuses to take on faith.

_While the engine is being touched_, fact 17's second half is cured in the same place: the runtime
check becomes the contract's `^[a-f0-9]{64}$`, not a bare length test, so the code stops being
looser than the document it implements.

---

## 6. How long it LIVES

**30 days, anchored on `CREATED_AT`**, under the signed row `garuda-document-privacy-v1`
(fact 14) — bound the way 304 binds its table: a fail-closed `BEFORE INSERT` trigger that derives
`retention_until` server-side from the single active policy for the row's environment, so an insert
fails when no policy is live rather than defaulting to forever.

**The sweep is named, not implied.** Expiry is executed by the same retention-purge path the other
`GARUDA_*` scopes use, running under its own role (§3), in this order: delete the object first, then
the row. Object-then-row is deliberate — the reverse leaves a byte in a bucket with no record that
it is owed deletion, which is the worse of the two failure modes; object-deleted-but-row-surviving is
self-healing, because the next sweep retries and a read in the meantime hits §4's 503 rather than
serving a ghost. A download in flight is unaffected: §5 fetches and verifies **before** emitting, so
a purge either precedes the fetch (404) or finds the bytes already copied.

`artifact_available` goes `FALSE` at expiry; the practice keeps `artifact_id`/`artifact_digest` as a
historical record of what was delivered.

**Three residuals, declared rather than discovered later:**

1. **The anchor is the real question, and it is Zero's.** The signed 30 days were authored for the
   _intake cache_ tier (fact 12: 304 places `garuda_documents` explicitly in the
   `garuda_order_idempotency` tier, an operational-lifetime cache). Binding a delivered travel
   document to that same scope means **the customer's download window closes 30 days after staff
   produce the file, not 30 days after the customer is told about it, and not relative to the trip**
   — and `CREATED_AT` is the only anchor a `GARUDA_DOCUMENT` policy admits today. The first reader
   was right that scope-vs-scope is the smaller question underneath (§8, G-6). Phase 2 builds
   against **30 d / `CREATED_AT` as ruled**; what goes to Zero as a named checkpoint is:
   _does the delivered artifact keep the `GARUDA_DOCUMENT` scope at 30 days from creation, or does it
   get its own scope — and does that scope need an anchor this policy table does not yet have?_ If
   the answer is a new scope, the change is one policy row and one binder, and nothing in §5 moves.
2. **Backups and replicas outlive the sweep.** Postgres WAL/snapshot backups and any bucket
   versioning retain bytes past `retention_until` by design. This spec does not solve it and must not
   pretend to: phase 2 disables object versioning on `garuda-voa-artifacts` at creation, and the
   database-backup horizon stays a known, declared property of the platform rather than a claim this
   document makes.
3. **`Cache-Control: no-store` binds our edge, not the customer's disk.** A downloaded file is the
   customer's. Retention governs what Bali Zero holds.

---

## 7. What phase 2 builds (the consumer of this spec)

Strictly after W3C's contract PRs are **MERGED** (`gh pr list --search "W3C OR contract closure"`),
from a fresh `origin/main`. This is more than one PR's worth of work and is **split at the seam**,
each ≤ ~400 net lines, merged in order:

**PR A — the object exists.** Migration `garuda_practice_artifacts` (§3: grants, partial unique
index on live rows, fail-closed retention binder), the private-bucket client with its own scoped
credentials and byte ceiling, and `putPracticeArtifact` in the staff lane (§3).

**PR B — the object is reachable, and `Delivered` depends on it.** `getPracticeArtifact`
(customer, order-keyed) and `getStaffPracticeArtifact` (staff, practice-keyed) with §4's error table and §5's fetch-verify-emit; PR-11
rewritten to resolve-and-verify (§5); the tokenless download link in `practice_delivered_email` (§6
of the emails, `_practice_transition_body`); the retention sweep entry (§6).

**Tests that must exist before either PR is armed:** the positive case; the **mandatory negative
case** (a second magic-link session gets 404); the digest-mismatch case (503, never a partial body);
supersession (a superseded id reads as 404); and the **422 on a fabricated `artifact_id`** in
`test_staff_router_transitions.py`, which is the ledger row's own `proof-of-armed`.

**Acceptance** is this window's success bar, unchanged: an authenticated magic-link session opens the
artifact; a different session fails; `delivered` is impossible without a retrievable artifact. Proof
is a `curl` against the promoted commit — authenticated and unauthenticated — never a merged PR.

---

## 8. Review record — seats, findings, dispositions

| seat                       | model id         | role                                                                                                                        | outcome                                                                                                                                                                                                     |
| -------------------------- | ---------------- | --------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claude (this session, W3A) | `claude-opus-5`  | Dux / author                                                                                                                | drafted §1–§7 against measurements taken at `c0a4a3bffe`                                                                                                                                                    |
| Gemini via `agy`           | `gemini-3.1-pro` | long-read reader: "who owns it" / "who reads it" / "what is missing for retention"                                          | **answered** — 12 findings, dispositions below. (The `arsenal` probe at session start reported this seat `TIMEOUT`; it answered on first invocation, so the probe was stale, not the seat.)                 |
| Kimi                       | `kimi-k3`        | second reader on the **contract surface** only — operation shape, lane, status codes, headers, irreversibility, duplication | **answered**, after grounding itself in the frozen `openapi.yaml` rather than in the spec's summary of it. 3 defects, all accepted. (Probe also reported this seat `TIMEOUT` at session start; also stale.) |

Generator is never grader: the on-disk gate for this PR is signed by a session that did not write
it, and phase 2's adversarial round on the session↔artifact binding goes to Codex Sol
(`gpt-5.6-sol`) outside the contribution chain.

**Accepted, and the spec changed:**

- **G-1 — ghost ingestion flow.** PR-11 was specified to resolve an artifact row that no operation
  created. The circularity was real. → `putPracticeArtifact` added (§3).
- **G-2 — superseded artifacts had no lifecycle.** → §2 gives them `superseded_at`, immediate object
  deletion, a partial unique index, and a read behaviour (§4).
- **G-3 — "append-only" was unenforceable and the bucket was unnamed.** → §3 names the provider, the
  separate private bucket, the scoped credential as `operator[secret]`, and states append-only as a
  grant with `DELETE` withheld from the runtime role.
- **G-4 — verify-while-streaming leaks unverified bytes.** The strongest finding: a mismatch
  discovered at EOF arrives after `200` and after most of the file. → §5 is now fetch-verify-emit,
  with a byte ceiling to make buffering safe.
- **G-6 — the flagged retention question was the smaller one.** → §6 residual 1 now names the anchor
  class, not just the scope, and states the consequence in the customer's terms.
- **G-7 — no purge executor, no ordering, no backup story.** → §6 names the sweep, the
  object-then-row order and why, the in-flight case, and three declared residuals.
- **G-8 — staff could not read through a customer-authenticated route.** → §4 is two routes, never
  one route multiplexing two auth schemes.

- **K-1 — the customer path broke the frozen lane convention.** Raised independently of the author's
  own re-measurement, and both landed on the same cure: no customer path carries a `practice_id`
  (fact 16), so `/practices/{practice_id}/artifact` was wrong twice over. → §5 is order-keyed, which
  also removes the need for any new customer error code (§4).
- **K-2 — the redesign hid two further contract changes behind "one added GET".** Dropping the two
  request fields would break `DeliverPracticeTransition` (fact 17). → §5 keeps the fields and
  changes their MEANING to a checked assertion; no schema change, and the cure is stronger than the
  removal was.
- **K-3 — the operation declared less than its 16 siblings do.** Missing `x-feature-flag`,
  `GARUDA_PUBLIC_DISABLED` in the 404 bucket, 500, and the binary-body/`Content-Disposition`
  declarations a JSON-only contract has never needed (fact 18). → §5 lists them.
- **K-4 (= G-4, reached independently)** — the two readers converged on verify-before-emit from
  opposite directions: one from the leak, one from the impossibility of answering 503 after a `200`
  has already gone out. Two seats, one defect, and the agreement is why it is the change this review
  most clearly earned.

**Rebutted, with a measurement rather than an argument:**

- **G-5 — "multi-traveller orders leak across co-travellers."** Does not apply here:
  `garuda_practices.order_id` is `NOT NULL UNIQUE` (fact 15), so one order is one practice is one
  applicant email. A group booking is N orders and N sessions. Recorded because the finding would be
  correct against a schema this product does not have.
- **G-9 — "404 overloading makes pending, unauthorised and purged indistinguishable to the client."**
  Accepted as a description, rejected as a defect: the tracker already publishes `artifact_available`
  (fact 5), so a legitimate client distinguishes the states **before** calling this route. Making the
  error carry that signal would hand the same distinction to a caller who has no practice at all,
  which is the leak §4 exists to prevent. The timing-side-channel half of the finding is real but
  generic, and is not traded against a disclosure that is certain.
