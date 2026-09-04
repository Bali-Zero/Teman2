# LANE A — GARUDA VOA: close steps 8, 7, 4-price; hold step 5 for Zero

**Machine:** M5. **Corner:** `docs/plans/2026-08-24-garuda-voa-live/MANDATE.md`, then
`NEXT-SESSION.md` in the same directory (2026-09-02), then `docs/factory/ASSEMBLY-LINE.md`.
**Contract:** `README.md` in this directory (session contract + team recipe) — read it first.

You are the GARUDA VOA session on M5. This is a **dark launch**: Xendit is sandbox, ship behind the
flag, simulate payment. Nothing is "done" because it merged — done is proved on the live surface.

## Where the funnel stands (measured 2026-09-03 from `origin/main`)

| step                             | state                                 | evidence                                   |
| -------------------------------- | ------------------------------------- | ------------------------------------------ |
| 1-3 route, verdict, single price | live                                  | —                                          |
| 4 passwordless account           | live; magic-link preview merged       | #5559                                      |
| 5 upload + local OCR             | route live (#5549); **store BLOCKED** | PR #5526 unarmed, migration 304            |
| 6 payment                        | Xendit sandbox — simulate             | `WHEN-THE-PAYMENT-KEYS-ARRIVE.md`          |
| 7 tracker                        | **not started**                       | no branch, no PR                           |
| 8 staff surface                  | **merged, not proven**                | #5577 (UI), #5584 (engine + migration 305) |

## A1 — Step 8 PROVE-LIVE, then the five findings (do first)

1. Prove the staff surface with a REAL admin session (`zero@` / `antonellosiano@` /
   `asya@balizero.com`): practice list renders, detail renders, one PR-02..PR-11 transition
   executes and is persisted (`scripts/pg.sh` read of the practice row, never a screenshot alone).
   Backend `build_sha` must be the merge commit of #5584; migration 305 applied on prod
   (ledger row 2026-09-02 says 6/6 columns present — re-measure).
2. Five findings from the codex/tp1 seats on #5584, one PR each, ≤ 400 lines, builder Sonnet:
   - unauthenticated staff route answers the middleware's generic 401 body, not the contract's
     `{"code":"SESSION_R…"}` shape — align the contract or the middleware, never both silently;
   - `facts.case_type` is interpolated unescaped into 8 HTML email bodies in
     `services/garuda_orders/outbox_handlers.py` (6 pre-existing, 2 from step 8) — escape at the
     one seam, add a guilt test with `<script>` in `case_type`;
   - `Idempotency-Key` is enforced at runtime (400) on `assignPractice`/`transitionPractice` but the
     live OpenAPI marks it optional — regenerate the contract and add the OpenAPI-vs-running diff
     check the ledger has wanted since 2026-08-25;
   - `customer_reason_key` / `required_action_key` are an open regex-shaped vocabulary — close them
     into an allowlist with a CHECK or enum, migration in the evening batch;
   - the transition engine records opaque evidence/artifact ids and never verifies content nor
     serves the artifact — spec first (what is an artifact, who serves it), then build.
3. Each backend PR is a deploy: batch them, watch the `release_command` on the NEW image (the
   2026-09-02 trap: «No pending migrations» printed by the OLD machine).

## A2 — Step 7 tracker (parallel with A1, no dependency on step 5)

- Customer's status view after paying. Only the **published D-7 checkpoint** may be shown; never
  internal state, never a fabricated ETA; no PII in URLs or logs.
- Reuse the magic-link mechanism settled by #5559 — do not fork a second auth path.
- ASSEMBLY-LINE order: frozen contract → tests named in advance → Sonnet builder → Sol refuter →
  Opus gate → prove on the live surface with a simulated paid order.

## A3 — Step 5 store: WAIT for Zero, then execute the chosen option

- Blocker is a DESIGN DECISION, not code: migration `304_garuda_documents.sql`'s
  `DO $garuda_304_owner_transfer$` block needs `visa_ledger_owner` membership that the runner role
  `backend_rag_v2` lacks (`pg_has_role = false`, `rolsuper = false`, measured 2026-09-01 22:25Z).
  Options D (dedicated migration role) vs E (fully specified superuser transaction) are measured in
  #5573. Option A (temporary GRANT) is SUPERSEDED and unsafe. **No privileged production operation
  without Zero's decision** (`ZERO-DECISIONS.md` item 1).
- When decided: implement per #5573; keep #5526 unarmed until 304 is applicable; then re-cherry-pick
  `agent/air-m5/ops/garuda-voa-store-wiring` (@ `7cc6878f07`, worktree
  `.worktrees/ops-voa-store-wiring`, 5 commits, no PR) onto a fresh `origin/main`.
- Definition of done: a document uploaded from a phone camera, OCR'd locally (`qwen2.5vl:7b` only),
  stored, visible in review — on the live surface.

## A4 — The price is ruled, not live

- Ruling 790.000 merged (#5407, migration 302) but the ledger (2026-08-31) says the CRM still quotes
  750.000 and `scripts/pricelist_2026/generate.py` cannot finish (one PNG missing since it shipped).
  Consumer-map first (CRM, price sheet, GARUDA funnel, WA bot corpus, `balizero.com/visa`), probe
  each live, cure the ones that still say 750k, restore the PNG, regenerate, prove.
- The two price stores have no reconciliation mechanism (same ledger row) — spec it, do not patch a
  third copy.

## Traps this lane already paid for

- CI shards are fail-fast: exit 2 = INTERRUPTED, one defect per shard, the rest unobserved.
- `autoMergeRequest: null` means "in the queue", read `mergeQueueEntry` via GraphQL.
- The failure page is not the failed state (#5523): expire credentials on the state, not the view.
- `feature/garuda-voa` has no branch protection — never `--auto` there; everything goes to `main`.

## LIVE STATE (update before ending the session)

- 2026-09-03 (written from `origin/main` @ `c4d48071a7`): nothing in this lane proved yet; A1 is
  the first move; A3 waits for Zero.
