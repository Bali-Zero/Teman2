# GARUDA VOA — next session mandate: close steps 5, 7 and 8

> **Scope of this file.** One mandate, three steps, nothing else. Written 2026-09-02 at the end of
> a long session so the next one starts from disk and not from a chat transcript. Everything here
> was measured, not remembered; every sha and path below was re-read the turn it was written.
> **Verify anyway** — a fact in this file is a lead, and this repo's scar record is mostly the
> distance between "was true when written" and "is true now".

## Before turn 1

- **Fix the model before the first turn.** `--model claude-opus-5` (or the settings key), never
  `/model` afterwards: switching mid-session rewrote a 121k-token startup cache and cost $3.65 in
  one measured case. Effort `xhigh`.
- Start in a fresh worktree: `python scripts/agent_start.py --lane ops --task-id garuda-voa-<step>`.
  Never work in the main checkout — live sibling sessions hold it.
- Read, in this order: `docs/plans/2026-08-24-garuda-voa-live/MANDATE.md`, then this file, then
  `docs/factory/ASSEMBLY-LINE.md` (product work: where it overlaps `modus`, ASSEMBLY-LINE wins).
- This is a **dark launch**. Xendit is still sandbox. Ship behind the flag; simulate payment.

## Where the funnel actually stands

| step | state | evidence |
|---|---|---|
| 1-3 route, verdict, single all-inclusive price | done | live |
| 4 passwordless account | **live in prod** | `/health` → `build_sha e83632f7b37d…` |
| 5 upload + local OCR | **blocked** — route merged, store cannot land | PR #5526 |
| 6 payment | Xendit sandbox — simulate, do not wait for it | `WHEN-THE-PAYMENT-KEYS-ARRIVE.md` |
| 7 tracker | not started | — |
| 8 portal / staff surface | not started | — |

Step 4 closed a real hole: every magic link used to be copied to `asya@`, i.e. a second person
could sign in as the customer. That is fixed and live.

## Step 5 — the blocker is a DESIGN DECISION, not code

The upload route is merged and live. What cannot land is the **store**, because migration
`304_garuda_documents.sql` cannot be applied by the role the deploy authenticates as.

**Branch state (verify with `git ls-remote --heads origin`):**

- `agent/air-m5/ops/garuda-voa-documents` @ `6ea6eb9ade` — PR **#5526**, BLOCKED, deliberately
  **UNARMED**. The consumer break is cured here (`92012ccf96`: `actor_id` threaded through three
  call sites; router suite 28 passed / 1 skipped, up from 12 red).
- `agent/air-m5/ops/garuda-voa-store-wiring` @ `7cc6878f07` — the wiring in
  `service_initializer.py:1483-1520`. **Must not merge before #5526.** May need re-cherry-picking
  if #5526's files moved.
- `agent/air-m5/spec/retention-scope-enum-cross-owner` — PR **#5548**, the spec for this blocker.

### Do not merge #5526 to "see what happens"

Merging any `apps/backend-rag/**` PR **is the deploy** (`fly-deploy.yml` on push to main; the
`release_command` applies migrations). If 304 lands un-appliable, it fails at every subsequent
release_command — **every backend deploy in the repo stops**, not just this one. That is why the
PR is unarmed. Leave it unarmed until the decision below is made.

### What was tried and what killed it

- **Round 2** widened the `policy_scope` CHECK and granted `REFERENCES` in production
  (both verified live, `2026-09-01 22:05:43+00`). Necessary, not sufficient.
- **Round 3** found the real blocker: 304's `DO $garuda_304_owner_transfer$` block (lines 266-304)
  raises when the runner role can neither `ALTER FUNCTION … OWNER TO visa_ledger_owner` nor is
  already a member of it. Measured `22:25:11Z`: `pg_has_role('backend_rag_v2','visa_ledger_owner',
  'MEMBER') = false`, `rolsuper = false`.
- **Round 4 (2026-09-02) — a cross-family seat returned BLOCK on both privileged paths.**
  codex CLI, `gpt-5.6-sol`, effort `xhigh`. Full text folded into PR #5548; the evidence journal
  entry is `evidence/2026-09/agent-air-m5-ops-garuda-voa-documents-57f48f6b/journal.jsonl`, round 4.

**The option-A decision recorded in round 3 is SUPERSEDED. Do not execute it.** The codeowner
chose "temporary `GRANT visa_ledger_owner TO backend_rag_v2` spanning the apply" on a premise the
session supplied and which is false on disk: `301_garuda_magic_link_binding_owner.sql`'s own header
documents a **manual superuser session** as the precedent, never a role grant. The codeowner has
not re-decided on corrected information, so **no privileged production operation is authorised.**

Why option A is unsafe as specified:

1. Membership alone is not the full precondition — the new owner also needs `CREATE` on the
   containing schema, and the membership needs the `SET` option (`INHERIT` separately governs
   automatic inheritance). None of these were measured.
2. The `GRANT` elevates the **live application role**, not the migration process: for the whole
   window every runtime session inherits owner privileges over *all* ledger-owned objects, and a
   session that already did `SET ROLE` is not neutralised by the `REVOKE` — it must be terminated.
3. The runner does not stop the pending batch on a failed migration, so others can commit while
   the membership is live.
4. Revoking before the **new image's** release_command reaches 304 reproduces the same failure —
   304 exists only in the new image.

Why the plain superuser path is also unsafe: raw `psql` does not write the migration-tracking rows
(the Python runner does), so the deploy retries 304; and objects created in that session are
superuser-owned, leaving the app unable to write — **deploy green, feature dead.**

Why option C (scope lookup table) is not free either: as specified it grants **permanent `INSERT`**
on the lookup to the runtime role, weakening the integrity property it exists to protect.

### The decision to put to the codeowner — ONE question, with costs measured first

Not "membership yes/no". The two live options are:

- **(D) a dedicated migration role** that owns the DDL path, distinct from the runtime role; or
- **(E) a fully specified superuser transaction** that `SET LOCAL ROLE`s to `backend_rag_v2` for
  ordinary object creation, switches back for the owner transfer, asserts every final owner and
  grant, and records the migration through runner-compatible tracking.

**Measure before asking.** For each: what it costs to build, what it leaves owned by whom, whether
it is reusable for migration 305+, and whether it can be proved read-only afterwards. Bring numbers,
not adjectives. Under rule 8 this surface has had three rounds on the same cause — the next move is
the spec and the decision, **not a fourth attempt**.

### Definition of done for step 5

A real document uploaded from a phone camera, OCR'd locally (`qwen2.5vl:7b` only — never cloud),
stored, and visible in review. Proved on the live surface, not in a test. Nothing is "done"
because it merged.

## Steps 7 and 8 — not started, and NOT blocked by step 5

Do these in parallel with the step-5 decision; they do not need the document store.

**Step 7 — tracker.** The customer's status view after paying. Only the **published D-7 checkpoint**
may be shown publicly; never internal state, never a fabricated ETA. No PII in URLs or logs.

**Step 8 — portal / staff surface.** Deliberately deferred until now because it reuses the same
magic-link mechanism as PR #5559 — land or resolve that first and build on the settled shape, do
not fork a second auth path. Staff RBAC: admin is `zero@`, `antonellosiano@`, `asya@balizero.com`;
team members see only rows where `assigned_to` matches.

## Also in flight — inherit or close, do not restart

- **PR #5559** (`agent/air-m5/ops/garuda-voa-link-preview` @ `9f00f9f417`) — magic-link preview.
  A security guard is red on it, correctly: `POST /api/visa/voa/auth/magic-links/preview` is a
  **public mutating route reachable with zero credentials** and is declared in neither
  `INTENTIONALLY_PUBLIC_MUTATIONS` nor `KNOWN_UNGATED_PUBLIC_MUTATIONS`. Answer the guard, do not
  weaken it: confirm `peek()` writes nothing (a rate-limit counter would count as state), confirm
  it must be credential-free, and decide whether `POST` was right at all — a `GET` sidesteps the
  gate and the token rides in an HttpOnly cookie, not the URL. Second red: "Harness floor
  recompute", cause not yet identified.
- **PR #5548** — the spec. Docs-only. Its R1 gate needs `adversarial_review: <cross-family seat>`
  in the frontmatter plus a `## Adversarial review` body section; a Claude byline is not accepted
  by design. It touches `PENDING-ARMS.md`, a `merge=union` file — a DIRTY there is the phantom
  conflict; resolve by keeping BOTH sides' rows, never by deleting another session's row.

## Traps this lane actually hit — read before repeating them

- **CI shards run fail-fast.** `exit code 2` means INTERRUPTED, not "tests failed" (that's 1). A red
  run names at most one defect per shard; everything after it is *unobserved*, not green. Four
  defects surfaced serially here for exactly this reason.
- **Count the checks; never read the summary colour.** `gh api …/actions/runs` without
  `--paginate` shows 30 of ~100 — a published red sat on page 2 and two sessions missed it.
- **`autoMergeRequest: null` does not mean disarmed** — it goes null when the PR enters the merge
  queue. Read `mergeQueueEntry` via GraphQL.
- **zsh eats `"$REF:path"`** (history modifiers): returns empty with no error. Always
  `"${REF}:path"`.
- **The worktree-isolation hook judges cwd**, not the post-`cd` target — use absolute paths.
- **This repo is npm-managed.** Never run `pnpm`; it builds a pnpm-shaped `node_modules` that breaks
  the typecheck hook. `npm ci` is the cure.
- **Never `-q` with pytest** (the repo guard rejects it as unreadable evidence); never `--no-verify`;
  never bare `git stash`.
- Production DB access is **read-only** via `scripts/pg.sh`. Never read Fly secret values; never
  `printenv`/`env`/`launchctl` on a production machine.
- The OCR corpus at `/Users/balizero/garuda-ocr-corpus/` must **never** enter the repo or any shared
  artifact — this repo is PUBLIC. Aggregate metrics only; refer to documents as `p01..p20`.

## What belongs to the codeowner, and what does not

The session reviews, merges, arms, deploys and proves-live. The codeowner does **not** merge, review
or deploy. What genuinely stays with them here: **the D-vs-E privilege decision** (business/risk),
any credential they alone hold, and physical/GUI actions. Everything else is the session's work.

Do not park anything on "waiting for the codeowner's merge".
