# Visa Oracle V2 — Current State

> **SUPERSEDED (2026-08-23).** This is a 2026-08-15 snapshot, last touched by PR #4209. Four
> RulePack activations have shipped since — seq-9 (2026-08-19), seq-10 (2026-08-19, cured
> `el.c2.corporate-sponsor-type` / `el.e31c-mixed-marriage-parents`), seq-11 (2026-08-20,
> E30A/E30B pricing_key), seq-12 (2026-08-20, source re-attestation, freshness sentinel loaded
> and DB-reading on Pro — alert delivery unproven) — none of which this file records.
> **`.agents/skills/visaoracle/SKILL.md` § LIVE STATE is the current record; read that first.**
> Body below kept as archaeology, not deleted.

Snapshot: 2026-08-15, Asia/Makassar (Pro takeover, finalization in progress)

Owner: Zero / Bali Zero

Purpose: canonical restart and Claude-review handoff for `/visaoracle`

## Read this first

> **BUSINESS-VALIDATION RULING (Zero, 2026-08-08):** there is no automated
> traffic-volume gate for ENFORCE — the former 1,000/7d proposal, 100/14d
> fallback and Wilson-threshold approach are superseded. The Bali Zero team
> validates through heavy manual testing in SHADOW. This ruling does not close
> the DPIA, analytics-TTL or explicit ENFORCE-authorization blockers below.
> Canonical rationale:
> `research/visa/2026-08-08-decision-tree-v2-full-index-design.md` §4.

> **UPDATE 2026-08-15 — Mini unavailable; Pro continuation is active.** This
> does not transfer or widen any signing, activation, deployment, promotion or
> ENFORCE authority. SHADOW remains the only authorized engine posture and
> ENFORCE remains NO-GO. Frontend labeling PR #4192 is merged, and interactive
> Fable promoted its exact READY candidate
> `dpl_GCXrsjrXwPjL9mrZdwDg9seFnLK7` once at `2026-08-14T23:47:31Z` without a
> rebuild. Independent Vercel API verification resolves the production alias
> `mouth-nuzantara-2026.vercel.app` to that exact deployment, target
> `production`, state `READY`, commit
> `32c8b26d2d632fc21af1d17fff74bcdc1a55fa49`; a read-only `GET /visa`
> returned the deployment-protection redirect (`302`, no 5xx) and sent no Visa
> Oracle evaluation. Backend replay support from #4195 is live. The bounded
> live replay wrote 20/20 rows as
> `synthetic_gold`, produced 5 fixture matches and 15 unexplained divergences,
> and supplied no organic evidence. Policy-parity PR #4200 was frozen at
> `4367d2c7aa2739011a7bedadb46d374424b6041a` with green local and GitHub
> verification. Its exact-SHA Fable 5 gate returned SHIP, and Fable armed it
> once through `scripts/mq.sh arm 4200` at `2026-08-14T23:35:58Z`. The queue
> merged that unchanged head at `2026-08-15T00:06:34Z` as exact merge-group
> commit `0fae2a64c5f495ead2a0f4f497c253f6f0cee2bd`, after all merge-group
> checks completed successfully; GraphQL then reported no queue entry. The
> local arm receipt is mode `0600` and records the exact reviewed head. The
> automatic `Deploy Backend to Fly.io` workflow for that exact merge, run
> `31852588636`, completed successfully at `2026-08-15T00:16:26Z`, including
> all migration and post-deploy health jobs. Fly release 4126 runs digest
> `sha256:d195c251d9ae9f8ae4f016c9029604d296455631b3bf05c19835366c06c388b6`;
> every reported image carries `GH_SHA=0fae2a64...`, machine health is passing,
> and a separate read-only `GET /health/ready` returned `ready=true`. No Visa
> evaluation POST was sent. The dependent chain is #4198, #4199 and #4201 in
> that order. #4198 has
> now passed its immutable exact-SHA Fable 5 gate at
> `94ed6bd9204ef63080339d2a24ba5d8ea9de98a1` (binary diff SHA-256
> `bc3187b018bf265424ce9a2caae0e8cf4c2dfe515db5e3617c1a2b9a186a1fb6`),
> with audit marker `visa-fable-exact-sha-gate:94ed6bd9` recorded in PR comment
> `#issuecomment-5299331193`. Fable operator session
> `1327f48a-b8b2-47a9-ba30-84d70a08aada` then independently revalidated the
> unchanged head, gate marker, binary diff and terminal-green CI, marked the PR
> ready, and invoked `scripts/mq.sh arm 4198` exactly once. Its mode-`0600`
> receipt records that exact head at `2026-08-15T00:21:27Z`. GraphQL initially
> reported #4198 `QUEUED`/`AWAITING_CHECKS` at position 3 behind unrelated #4204
> and #4202. At `2026-08-15T00:25:40Z`, the aggregate merge group containing
> those preceding entries failed their `Immune enforcement` census because
> #4202 adds `scripts/ci/test_bot_provider_gate.py` without the required
> `codex_seat` resolver; GraphQL therefore marked both #4202 and downstream
> #4198 `UNMERGEABLE`. #4198 itself remained exact-head `MERGEABLE`/`CLEAN`
> with no bad checks. No queue mutation was attempted. GitHub then removed the
> unrelated failing predecessor, advanced `main` to `ef8db35d...`, and at
> `2026-08-15T00:29:21Z` rebuilt #4198 alone as merge-group
> `2b0cae1866bc24d4b77c0b81840dca1f9b2da393`; GraphQL now reports #4198
> `AWAITING_CHECKS` at position 1. At `2026-08-15T00:46:22Z`, all 42/42
> merge-group checks were terminal-clean with zero bad conclusions; no re-arm
> or queue mutation was attempted. The queue merged the exact reviewed head at
> `2026-08-15T00:46:36Z` as squash/merge-group commit
> `2b0cae1866bc24d4b77c0b81840dca1f9b2da393` directly atop
> `ef8db35dbd4d5943354a5d3479f63080a4811f3d`. Independent GraphQL verification
> reports `state=MERGED`, `main` at that exact commit and no merge-queue entry;
> the PR still records reviewed head `94ed6bd9...`.
> #4199 also passed
> its immutable exact-SHA Fable 5 gate at
> `903b01f8b5d2bb33141ddacaca9ac6aa6043efcc` (binary diff SHA-256
> `ae31cc045030dcb4b778f19bdf2904d80c394533d938e7586a05f5ed0606abd2`),
> with audit marker `visa-fable-exact-sha-gate:903b01f8` recorded in PR comment
> `#issuecomment-5299393419`. Fable queue operator session
> `d0837493-4bdb-403d-ad4e-0a56c4e31771` independently revalidated the
> immutable identity, clean worktree, unique gate marker, binary diff and 58
> terminal-clean check-runs plus successful combined status, then marked
> #4199 ready exactly once. Its post-ready retrigger settled at 61 clean
> check-runs with zero pending/bad and combined status `success`; after one
> final immutable-identity check, Fable invoked `scripts/mq.sh arm 4199`
> exactly once. The mode-`0600` receipt records the reviewed head at
> `2026-08-15T00:52:49Z`, and GraphQL advanced it from `QUEUED` to
> `AWAITING_CHECKS` at position 1 with the head unchanged. GitHub constructed
> merge-group commit `d56550a5d89a543d3f5e2de13d20b0fd5f6d57c7`; all 43/43
> checks reached terminal `success`, with combined status `success`, at
> `2026-08-15T01:21:09Z`. The queue merged the exact reviewed head at
> `2026-08-15T01:21:41Z` as that commit, directly after #4198 merge
> `2b0cae1866bc24d4b77c0b81840dca1f9b2da393`. GraphQL now reports
> `state=MERGED`, no queue entry and `main` at `d56550a5...`; the PR still
> records reviewed head `903b01f8...`. #4201 has now also
> passed its exact-SHA Fable 5 gate at
> `69c7493146ed23fc717b73a18fff652e05089204` (binary diff SHA-256
> `d92a1f986a6d706d7fa6cac4ee95a9f2783895fc1bc4b251eef32c8e4b3fa53a`),
> with a byte-exact replay reproduction and audit marker
> `visa-fable-exact-sha-gate:69c74931` in PR comment
> `#issuecomment-5299448049`. Independent queue-operator session
> `ea8bf063-9e6b-4dc8-b622-0b655bc25e63` revalidated the unique marker,
> clean exact-head worktree, fresh merge-base and binary diff digest, then
> invoked `gh pr ready 4201` exactly once at `2026-08-15T01:24:59Z`. Its
> post-ready suite settled 51/51 terminal-clean; Fable
> then invoked the canonical queue arm exactly once. The mode-`0600` receipt
> records the reviewed head at `2026-08-15T01:25:52Z`, and GraphQL first reported the
> unchanged head enqueued at position 1 from `2026-08-15T01:25:53Z`. The queue
> advanced it to `AWAITING_CHECKS` on speculative merge commit
> `d54999e3ab3d01d90828ffc231f0dd3c575edd7f`; all 43/43 merge-group checks
> settled terminal-clean with combined status `success`. At
> `2026-08-15T01:43:30Z`, the queue merged the exact reviewed head as that
> commit, whose sole parent is #4199 merge `d56550a5...`. Independent REST,
> GraphQL and remote-ref verification now agree on `state=MERGED`, no queue
> entry and `main` at `d54999e3...`.
> Phase B, which
> makes `traffic_source` required and
> fail-closed, is now one locally committed change
> `b5d6da2e989d2943099236b8871734cb7b378d0d` directly atop the #4200 merge
> commit, with binary diff SHA-256
> `c0724febc0d2cbfd3b1239a756cd2e54d979cde532b1d786fd45b154c5dfb8fe`
> and green post-rebase backend/frontend/static/contract verification. It is
> published as PR #4208 at that exact head. Independent Fable 5 session
> `8bef8be3-9ced-4860-9b42-f9cfb2e7949b` reviewed every changed byte,
> reproduced the focused backend 3/3, mouth 35/35, TypeScript and generated
> OpenAPI-validator passes, and mutation-proved the boundary by restoring the
> former implicit `real` default: both the no-evaluation guard and required
> OpenAPI guard then failed. It rechecked 63 exact-head check-runs as 57
> success, 6 path/config skips, zero pending/bad, with combined commit status
> `success`, and returned SHIP. Pro independently repeated the immutable-head,
> merge-base, binary-digest and live-check reads and recorded unique audit
> marker `visa-fable-exact-sha-gate:b5d6da2e` in comment
> `#issuecomment-5299580365`. Independent queue-operator session
> `f7f9ba3f-105e-430c-88c3-ee124a5b24b0` then revalidated the predecessor,
> unique marker, clean exact-head worktree, fresh merge-base and binary diff
> digest. It invoked `gh pr ready 4208` exactly once; the resulting 66
> exact-head check-runs settled terminal-clean as 59 success, 6 skips and one
> neutral advisory, with combined status `success`. Fable revalidated every
> invariant and invoked the canonical queue arm exactly once. The mode-`0600`
> receipt records the reviewed head at `2026-08-15T01:49:28Z`; GraphQL first
> reported the unchanged head `QUEUED` at position 1 from
> `2026-08-15T01:49:29Z`, then advanced it to `AWAITING_CHECKS` on speculative
> merge commit `650716442c81298647eb07542e198565709de014`. All 42/42 merge-group
> checks settled terminal-clean (39 success, 3 skips) with combined status
> `success`; the queue merged the exact reviewed head at
> `2026-08-15T02:16:05Z` as that commit, whose sole parent is #4201 merge
> `d54999e3...`. Independent REST, GraphQL and remote-ref verification agree on
> `state=MERGED`, no queue entry and `main` at `65071644...`. Automatic deploy
> run `31858744114` completed `success` at `2026-08-15T02:25:55Z`, including
> rolling deploy, fresh-image SQL v2 migrations, idempotent Python migrations
> and post-deploy health. Fly release 4127 is complete on image digest
> `sha256:6bef531ce86eef0f9bca6ea3934ed3a53bf65d7d6495d024ceba319328dee0c6`;
> all four image records carry exact OCI label `GH_SHA=65071644...`, and the
> API service check is passing. One and only one evaluate POST was then sent
> without `traffic_source`. Live application log correlation
> `93fd9096-5d8f-4625-b7f7-b70531e4fdd6` records a sanitized `422` with
> `loc=[query,field]`, type `missing` and static message `Required field is
missing`; the production global handler adds only its non-applicant
> `correlation_id` envelope field. A separate GET/SQL-only readback sent zero
> evaluate POSTs and proved live OpenAPI `traffic_source.required=true`, exact
> three-value enum, `/health/ready` `200/ready=true`, a read-only DB connection
> and zero matching idempotency rows after the live request. Final aggregate
> window `2026-08-14T18:27:38Z`–`2026-08-15T02:32:36Z` remains 20
> `synthetic_gold`, 0 `synthetic_driver`, 0 `real`, 0 legacy; therefore the
> gate is honestly RED and `enforce_ready=false`. Canonical artifacts are
> `research/visa/2026-08-15-traffic-source-fail-closed-live-proof.json` and
> `research/visa/2026-08-15-shadow-evidence-final.json`. Any reviewed-head
> change would still void the historical gate identity.
> No RulePack was signed or activated during this continuation.

Visa Oracle V2 is **ONLINE IN SHADOW with every operational gate proven
against real production** — roles provisioned, migrations 262–267 applied,
Privacy Policy V1 registered, a corrected signed RulePack activated
(`prod-003`, sequence 3 — since superseded by `prod-004`/sequence 4, see the
2026-08-08 UPDATE addendum below), the 15-minute retention scheduler installed and
armed with real deletions (`APPLY=true`), and a full kill-switch drill
(SHADOW→OFF→SHADOW) executed and proven. It is still **not authorized for
production ENFORCE** — that flip is a separate, explicit, Zero-gated action,
withheld by mandate, and `VISA_ENGINE_EVALUATE_MODE=SHADOW` is confirmed
live. See "Production operational verification" below for the exact
evidence, and "Remaining production blockers" for what is genuinely still
open (DPIA, analytics TTL, ENFORCE authorization).

Do not infer that operational-gates-green means ENFORCE is authorized. Do not
merge, push, deploy, activate a RulePack or change ENFORCE from this record —
each is a distinct, explicit action requiring its own Zero go-ahead.

> **UPDATE 2026-08-08 (later, same day) — `prod-004` (sequence 4) is now the
> active PRODUCTION RulePack, superseding `prod-003`.** Activated under an
> explicit Zero go-ahead ("fai tu e trovale") via the two-login ceremony
> (`activate_pack.py --yes`, ephemeral roles minted + dropped same session).
> `rule_pack_id 720f50fc-12e2-5633-8586-4b31b086ea64`, activation
> `41fc8d3e-12cf-4d93-b265-9ee554630d5c`, `payload_sha256 1f0f7b0d…f410e49`,
> `previous_payload_sha256 99b843b8…fb477534` (the real prod-003 hash — chain
> intact), reason `seq4-shadow-activation-260808`. Independently DB-verified:
> seq-4 is the single open activation (`legal_period @> now()`,
> `system_period` open), prod-003 closed at the same instant (no gap/overlap).
> Prove-live PASS: the SHADOW binding query (`environment=PRODUCTION`,
> `jurisdiction=ID`, `decision_domain=IMMIGRATION_VISA`, fresh per-request read,
> no cache) resolves to seq-4 on the next evaluation. Content: 38 products /
> 112 rules (Fase-A citizenship-conflict guard for dual-nationals + D1/D2/D12
> purpose scoping + B1 nationality gate). **EVALUATE_MODE stays SHADOW;
> ENFORCE remains NO-GO** — still a separate Zero-gated action, unchanged by
> this activation. This addendum records a live prod state change; the
> historical `prod-003` narrative below is retained as history.

> **UPDATE 2026-08-09 — `prod-005` (sequence 5) is now the active PRODUCTION
> RulePack, superseding `prod-004`.** Activated under an explicit Zero go-ahead
> ("Sì, attiva seq-5 (SHADOW)" via checkpoint) through the two-login ceremony
> (`activate_pack.py --yes` on Pro over `fly proxy` → `nuzantara-postgres`;
> ephemeral roles `visa_pack_writer_ceremony_260809` / `visa_activation_ceremony_260809`
> minted via stdin→psql — pw never in argv — and dropped same session).
> `rule_pack_id 4159265d-53e8-5b25-ab5a-fa4f5b25a2d1`, activation
> `560839f3-a71d-42ef-bdec-246579630884`, `payload_sha256 ebc19f5c…aaad322e`,
> `previous_payload_sha256 1f0f7b0d…f410e49` (the real prod-004 hash — chain
> intact), reason `seq5-shadow-activation-260809`. **Signing kid CORRECTION:** the
> production kid is **`prod-2026-07-1`** (letter-first), NOT `2026-07-prod-1` — the
> latter (in the older runbook) was a transposition seeded by an illustrative
> `bundle.py` docstring example + the M5 key FILENAME `2026-07-prod-1.ed25519.pem`
> (filename ≠ kid). Proven against the live prod-004 signature; there is NO kid
> Identifier regression on main.
> **Single-active model CONFIRMED (an earlier revision of this block got it wrong).** A
> first draft here claimed "multiple PRODUCTION activations are open BY DESIGN … the newest
> `created_at` wins" and called the prod-004 note's "single open activation" imprecise.
> **That was wrong and is retracted** — it came from a probe that filtered `legal_period`
> ALONE, omitting the `system_period` clause the runtime applies. Re-measured with the
> runtime's real predicate (`legal_period @> now() AND system_period @> now()`): **exactly
> ONE active row — seq-5**; seq 1/3/4 have an open `legal_period` but a **CLOSED**
> `system_period`. The schema enforces this (GiST exclusion over both periods,
> `250_visa_engine_core.sql`; the writer closes covered activations,
> `253_visa_activation_writer_hardening.sql`), and `ORDER BY created_at DESC LIMIT 1` is
> DEFENSIVE, not a selection policy. The prod-004 note above stands as written.
> Content: 113 rules (= prod-004 112 + GLOBAL `review.minor-without-guardian`
> safety gate; plus the 5 D12 investment review rules now gated on
> `investment.pt_pma_committed != true` so a committed investor concludes E28A instead
> of a business-visit review). **EVALUATE_MODE stays SHADOW; ENFORCE remains NO-GO.**
> The Bali Zero team's 38-scheda manual SHADOW test runs against this corrected tree.

> **UPDATE 2026-08-10 — `prod-006` (sequence 6) is now the active PRODUCTION
> RulePack, superseding `prod-005`.** Activated under Zero's "tutte in sequenza"
> go-ahead through the two-login ceremony (`activate_pack.py --yes` on Pro over
> `fly proxy` → `nuzantara-postgres`; ephemeral roles
> `visa_pack_writer_ceremony_260810` / `visa_activation_ceremony_260810` minted via
> stdin→psql — pw never in argv — and dropped same session).
> `rule_pack_id e04a21e7-8716-584b-90ac-de3b5c192330`, activation
> `4c25cfbb-748e-404c-b639-1213304695da`, `payload_sha256 9691534c…3ca83f6`,
> `previous_payload_sha256 ebc19f5c…aaad322e` (the real prod-005 hash — chain
> intact), reason `seq6-shadow-activation-260810`. Content: 104 rules / 15
> HUMAN_REVIEW ("a requirement is a condition, not a proof", #3940): hr/review→el
> conversions conjoined to each product's genuine gate, E23U/E23V/E30E/E30F
> fail-closed, `hf.e33f.age-below-55` closes the under-55 retirement-offer
> CRITICAL. Prove-live: the HANDOFF-2026-08-08 IT/TOURISM/10d case now returns
> `SUPPORTED_CANDIDATES` [B1, C1]; NG negative control keeps
> `CALLING_VISA_REVIEW` with no B1. **EVALUATE_MODE stays SHADOW; ENFORCE remains NO-GO.**

> **UPDATE 2026-08-11 — `prod-007` (sequence 7) is now the active PRODUCTION
> RulePack, superseding `prod-006`.** Activated through the two-login ceremony
> (`activate_pack.py --yes`; ephemeral roles `visa_pack_writer_ceremony_260811` /
> `visa_activation_ceremony_260811` minted and dropped same session).
> `rule_pack_id 453ee842-7f35-5d77-b460-31d67e2784c2`, activation
> `3b849e1f-be39-4211-bfc9-395caef875c9`, `payload_sha256 3d068aef…9719f82`,
> `previous_payload_sha256 9691534c…3ca83f6` (the real prod-006 hash — chain
> intact), reason `seq7-shadow-activation-260811`. DB-verified: the runtime's
> real predicate (`legal_period @> now() AND system_period @> now()`) resolves
> to exactly one open activation — seq-7; `prod-006` closed at 2026-08-10
> 21:54:58 UTC, no gap/overlap. Content is **data-only**: 104 rules, identical
> to `prod-006` — the sole change is `E28C` `sponsor_types`
> `INDIVIDUAL → NONE` (plus the matching locator update on
> `source_record 9248b1d7`), no new rule — "the gate that does not exist"
> (`research/visa/2026-08-11-seq7-sponsor-semantics-and-the-gate-that-does-not-exist.md`).
> Prove-live: the IT/TOURISM/10d case still returns `SUPPORTED_CANDIDATES`
> [B1, C1], now served by `sequence 7`; the NG negative control still returns
> `HUMAN_REVIEW_REQUIRED` with no B1. **Declared shadow-ledger contamination
> from this ceremony's own replay probes**: 2 rows recorded with
> `traffic_source=real` (the IT and NG replay `evaluate` calls used to prove
> the activation) plus 1 further replay attempt that was rejected with
> HTTP 422 (validation failure, not persisted as a ledger row) — noted here so
> a future volume/G-a read on the shadow evidence ledger does not mistake
> these rows for genuine end-user traffic. **EVALUATE_MODE stays SHADOW;
> ENFORCE remains NO-GO.**

## Product contract

- The guarantee is **zero unsupported recommendations**, not zero errors.
- Only the deterministic evaluator and a verified signed RulePack may select,
  eliminate or preserve visa paths.
- LLM and Qdrant may explain an already-approved decision; they may never add,
  remove, select or reorder visa paths.
- Keep these states separate:
  1. legal eligibility;
  2. operational availability;
  3. Bali Zero service availability.
- UNKNOWN, insufficient facts, stale sources, source conflicts and integrity
  failures must abstain as `NEEDS_INPUT`, `HUMAN_REVIEW_REQUIRED` or
  `TEMPORARILY_UNAVAILABLE`; they must never improve eligibility.
- Prices come only from an exact `PricingTool` identity and are shown as one
  all-inclusive amount. No hardcoded price or split fee is permitted.
- EN and ID are co-first-class; facts are language-independent.

## Canonical workspace and reviewed commits

- Integration worktree (operational-gates delivery):
  `/Users/nuzantara/nuzantara/.worktrees/backend-rag-visa-oracle-v2-operational-gates`
- Closure-docs worktree (this update):
  `/Users/nuzantara/nuzantara/.worktrees/docs-visa-oracle-closure-docs`
- Branch: `agent/mini-pro2/backend-rag/visa-oracle-v2-operational-gates`
- Frozen G6 baseline: `cd343655c7d77f65f50897f91c299ba92da35cb0`
- Independently reviewed candidate: `635bbccd00ba5ad578eaaadcd27415918b2e1bc1`
- Independently reviewed final delivery record:
  `e15fc1b84501cbdc2e023497b3e1af298f51034f`
- Independent verdict: **LGTM, 0 BLOCKER, 0 MEDIUM**.
- **Merged to `main`**: PR #3732, merge commit
  `63234a12aa3c5dd451c22e2591a2ec9dd4b34e91`, merged 2026-08-07T12:34:07Z.
  Verified: the frozen G6 baseline (`cd343655c`) is a full ancestor of
  `origin/main`.
- **Open, not yet merged, both verified at time of writing**:
  - PR #3766 (`agent/mini-pro2/backend-rag/visa-oracle-268-followups`) —
    codifies migration 268 (`SECURITY DEFINER` + ownership fix for the 3
    retention-binding trigger functions broken by the D1 least-privilege
    repair) plus preflight/smoke coverage. Production already carries the
    equivalent hand-applied fix (see "P0" below), so this migration will be
    an idempotent no-op against prod once merged. Until merge, the repo does
    not yet reflect prod's real function-ownership/security posture for
    those 3 functions — this is a deliberate, tracked repo-vs-prod drift, not
    an oversight.
  - PR #3765 (`agent/mini-pro2/mouth/visa-verdict-states`) — mouth verdict
    panel fix so `HUMAN_REVIEW_REQUIRED` responses are no longer displayed as
    "no evaluation was submitted." Unrelated to the ops work below; tracked
    separately.
- This `CURRENT_STATE.md` update is documentation-only.

Never edit the main checkout. Continue only in the integration worktree or a
new worktree created through `scripts/agent_start.py`.

## Git and machine warning

The final 2026-08-07 machine check found Mini and Pro reachable but out of sync:

- Mini `main`: `5d0f3ddeb`
- Pro `main`: `029e6ca43`
- reviewed branch merge-base: `cd343655c`

The reviewed branch was two commits behind Mini's newest `main` at handoff.
One observed concurrent commit, `029e6ca43`, changed only
`.claude/skills/modus/PENDING-ARMS.md` and was graded LOW merge hygiene. A later
Mini commit, `5d0f3ddeb`, is a KBLI content fix and was not part of the frozen
G6 baseline. This is now historical — PR #3732 merged past this drift on
2026-08-07T12:34:07Z.

Before review or merge of unrelated future work, Claude must:

1. restore Mini/Pro git synchronization;
2. inspect every post-baseline commit for overlap;
3. rebase the worktree branch, never the main checkout;
4. rerun impacted G5 tests and `git diff --check`;
5. request a new exact-SHA G6 review if the rebase changes product/runtime/test
   behavior or creates a conflict.

Do not keep chasing unrelated concurrent `main` commits during a running G6
review. Freeze and record the reviewed baseline; handle later drift explicitly.

## Gate matrix

| Gate                                    | Initial state    | Reviewed repository state  | Production state                                                                                                                                                                                                    |
| --------------------------------------- | ---------------- | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| G0 inventory / AS-IS                    | PASS             | PASS                       | N/A                                                                                                                                                                                                                 |
| G1 contracts and sources                | BLOCKED          | PASS                       | signed pack carries per-source `freshness_policy` (7d/365d), all 28 sources `CURRENT`; no automated re-verification scheduler — next 7-day recheck ~2026-08-13, owner/SLA still a Zero decision (G1 packet point 6) |
| G2 engine and gold/adversarial harness  | PARTIAL          | PASS                       | roles/migrations provisioned and proven (D1 repair + P0 hand-cure, migrations through 267 applied, 268 hand-applied live / PR #3766 open)                                                                           |
| G3 UI states and categories             | PARTIAL          | PASS                       | reviewed candidate deployed and live-smoked (`mode=CURATED`)                                                                                                                                                        |
| G4 backend authority over public result | PARTIAL / SHADOW | PASS in candidate          | production confirmed live in SHADOW (`VISA_ENGINE_EVALUATE_MODE=SHADOW`, verified read); ENFORCE not authorized                                                                                                     |
| G5 automated verification               | PARTIAL          | PASS                       | production preflight + smoke run and green (see evidence below)                                                                                                                                                     |
| G6 independent review                   | PENDING          | PASS, 0 BLOCKER / 0 MEDIUM | does not authorize ENFORCE                                                                                                                                                                                          |

Activation verdict (repository + operational gates): **ONLINE IN SHADOW —
operational prerequisites are now proven green** in real production: roles,
migrations, policy, scheduler, corrected RulePack activation, production
smoke and kill-switch drill (see "Production operational verification"
below). **ENFORCE remains NO-GO by mandate**: DPIA is an unsigned draft ("DO
NOT ENFORCE — open high residual risks remain"), analytics TTL
destination/proof is unresolved, and the ENFORCE flip itself is a separate,
explicit, Zero-authorized action never requested or taken.

## Resulting architecture

The public interview maps language-independent facts to the generated OpenAPI
contract and calls `POST /api/visa-oracle/evaluate`. Strict response parsing
rejects malformed or duplicated JSON. Network failure never fabricates a
candidate. Preview/mock logic remains available only for tests and controlled
preview; it is not the authority for a user decision.

The backend resolves one signed PRODUCTION RulePack, evaluates tri-state rules,
derives one of the five terminal states, resolves an exact `PricingTool` quote
without changing legal candidate selection, builds a deterministic trace,
seals the decision with domain-separated HMAC and persists decision/evidence
under the approved retention authority.

Migration 267 adds atomic replacement of a complete activation set. The
replacement ceremony requires separately signed carry-forward/correction packs
and enforces:

- one scope advisory lock;
- one database clock for every close/open boundary;
- exact multirange legal coverage, without gaps or implicit orphaning;
- non-overlapping replacement intervals;
- monotone sequence and continuous payload hash-chain;
- idempotent exact replay and rejection of actor/reason drift;
- transaction rollback on every failure;
- maximum 64 signed segments;
- maximum 2 MiB per strict JSON bundle;
- Ed25519/JCS verification before insertion;
- distinct pack-writer and activation LOGIN principals.

The independent grader found and closed a real separation defect: the original
single-pack ceremony compared `current_user`, so one login using two
`SET ROLE` identities could appear separated. It now compares `session_user`,
still checks capabilities as `current_user`, and rejects a superuser session or
effective role fail-closed. PostgreSQL-real regression tests cover the attack.

**Production proved a second, closely related invariant the same night**: the
simple `visa_activate_rule_pack` function refuses to activate any candidate
whose `legal_period` does not fully cover an already-open prior activation —
see "RulePack correction" below for the real incident this caught.

## Source and Calling Visa decisions

- National sources have precedence when national and regional publications
  conflict on a national Calling Visa classification.
- Canonical current country set recorded in the approved evidence packet:
  Afghanistan (`AF`), Israel (`IL`), North Korea (`KP`), Liberia (`LR`),
  Nigeria (`NG`) and Somalia (`SO`).
- Zero approved the official Immigration announcements for Cameroon and Guinea
  as sufficient primary evidence.
- Cameroon (`CM`) and Guinea (`GN`) are excluded by those official removal
  announcements. Niger (`NE`) is excluded by the approved national-authority
  precedence decision; do not confuse Niger (`NE`) with Nigeria (`NG`), which
  remains in the canonical six-country set.
- The Guinea announcement identifies Kepmenkumham
  `M.HH-03.GR.01.06 Tahun 2024`, effective 2024-06-12, and reports the resulting
  six-country list.
- The Cameroon announcement identifies Kepmenkumham
  `M.HH-05.GR.01.06 Tahun 2023`, approved 2023-11-23.
- Permenkumham 2/2024 is byte-verified against the official source.
- Kepmen `M.HH-03.GR.01.06/2023` is archived as related `Indeks Visa`
  evidence, not misrepresented as the Calling Visa removal instrument.
- The normalized announcement record, raw official HTML and source manifest
  were content-addressed, uploaded to the Visa Oracle Drive archive and read
  back.
- The ministerial removal PDFs remain desirable corroboration if later found,
  but Zero ruled that their absence is not a G1 blocker.

**Executed in production (2026-08-08)**: the CM/GN removal is live. Signed
pack `rulepack-prod-003` (sequence 3, `rule_pack_id
37be33e4-8fbb-55bc-8fe2-7dcb23eab979`, activation
`783f5fcc-d7cd-4cc5-ba22-c6724d4a3bf1`, reason token
`g1-calling-visa-retroactive-fix`, 16:34:34Z) is the active PRODUCTION
RulePack. Live smoke confirmed: Cameroon now resolves to the ordinary
D1/D2/D12 document-requirement path (no `CALLING_VISA_REVIEW` reason code);
Nigeria still resolves with `review_reasons=['CALLING_VISA_REVIEW']` only
(positive control — the mechanism was not disarmed for a country that must
stay flagged); Italy is unchanged baseline. See "Production operational
verification" below for full evidence, including why activation required a
retroactive-legal-period re-signing (sequence 2 → 3) rather than a simple
sequence-2 activation, and the independent DB re-verification (sequence 3
confirmed current, sequence 1 closed without a gap).

Canonical evidence:

- `docs/audits/2026-08-06-visa-oracle-g1-source-decision-packet.md`
- `docs/audits/evidence/visa-oracle-v2/2026-08-06-source-archive-manifest.json`
- manifest SHA-256:
  `ce5ac3d6dc9a530ea2099710967ec72673a525f292e02abe8c62c78e1e6a421a`

Freshness policy:

- official portal observations: max age 7 days, daily recheck;
- primary laws and ministerial decisions: max age 365 days, monthly recheck;
- no last-known-good fallback after expiry;
- nationality/product conflicts are scoped to the affected branch;
- integrity or global-provenance failures block the whole evaluation.
- **Live in the active pack (2026-08-08)**: all 28 `source_records` in
  `rulepack-prod-003` carry a populated `freshness_policy` — 19 official-portal
  sources at 604800s (7d), 9 primary-law sources at 31536000s (365d). Confirmed
  via live evaluate response: `freshness.status="CURRENT"` on every cited
  source, replacing the prior `FRESHNESS_POLICY_NOT_DEFINED` gap (the
  previously-active `prod-001` had `freshness_policy=null` on every source).
  The policy is populated in the signed content, but **no automated
  re-verification scheduler exists yet** — the next 7-day recheck for the 19
  portal sources is due ~2026-08-13. Per the G1 source decision packet, point
  6: "Freshness — POLICY DECIDED / OPERATIONS REMAINING... Zero must still
  assign the production owner/SLA, scheduler and alerting." Unchanged, still
  open.

## Pricing state

- Accountable owner: Finance.
- Approver: Zero.
- Technical custodian: Backend.
- Catalogue version: `2026.1`.
- Effective date: `2026-01-01`.
- Provenance `last_updated`: `2026-05-06`; this is not an invented expiry.
- Full catalogue SHA-256:
  `97e377d769df7f2dd060cba1896c13362a7419001dcc526c60d2522147c0c2a8`.
- The snapshot remains approved until superseded or explicitly withdrawn.
- The frontend snapshot contains 106 exact rows.
- Sequence 2 currently maps 13 exact products. Missing or ambiguous onshore /
  offshore variants abstain from price display.
- The nonexistent `C317 Single Entry` entry and copied fallback price were
  removed.
- Ranges, non-IDR values, contact text, malformed rows and monetary add-ons in
  notes never become displayed prices.
- **Verified live (2026-08-08)**: production container's catalogue file
  SHA-256 matches the worktree exactly — no drift.

## Privacy Policy V1

Zero approved:

- durable decisions: 30 days;
- idempotency/retry records: 24 hours;
- PII-free operational telemetry: 90 days;
- DSR acknowledgement and action: within 3 × 24 hours;
- separate unticked consent for CRM and WhatsApp;
- minimum-field handoff only;
- guardian confirmation for minors;
- documented legal hold only for identified records;
- DPIA approval before ENFORCE.

Repository controls include an unseeded/fail-closed policy authority, bounded
purge and aggregate evidence functions, DSR erasure, legal hold/release,
bilingual public notice, PII-free Visa Oracle analytics and a one-shot retention
worker. The worker directly reads only the approved non-PII policy row and uses
bounded SECURITY DEFINER functions for deletion/evidence.

**Now installed and armed (2026-08-08)**: the 15-minute LaunchAgent
(`com.nuzantara.visa-oracle-retention.15min.plist`) is running on Mini with
`VISA_ORACLE_RETENTION_APPLY=true` — real deletions, not dry-run. It uses zero
immediate retries so backlog/lag exit `2` cannot be retried until the required
alert disappears. Cell thresholds are warning at 30 minutes and critical at 60
minutes, both confirmed armed. First `apply=True` run 16:01:37Z; every run
since reports `healthy=True`, 0 backlog. See "Production operational
verification" below for install/flip evidence.

Analytics TTL is an independent ENFORCE gate. The checked-in placeholder
attestation exits `2` fail-closed. It must not delay an already-due database
purge. **Still fully open** — no analytics destination/provider has been
identified and no 90-day TTL export/probe has been reproduced since the
original assessment.

## Verification evidence

Final generator G5 after the last implementation rebase:

- backend Visa Engine/router: 1,668 collected; 1,667 passed; one expected skip
  because `visa_activation_executor` is not provisioned in the test environment;
- targeted activation/CLI/migration/privacy suite: green;
- Mouth Visa-focused Vitest: 31 files, 319 tests passed;
- Mouth full Vitest: 346 files, 3,178 tests passed;
- Mouth typecheck: passed;
- retention operations: 16 tests passed;
- Cell retention sensor: 4 tests passed;
- Playwright Visa Oracle V2: 15/15 passed;
- disposable full-stack smoke: 1/1 passed through browser → Next → FastAPI →
  signed TEST RulePack → PostgreSQL with migrations through 267;
- disposable database was dropped in `finally`;
- Ruff, Prettier, plist lint, shell syntax and `git diff --check`: passed.

Independent G6 reproduced:

- 78 critical activation/CLI/preflight/PostgreSQL tests passed;
- one expected provisioning skip;
- privacy: 9 passed;
- retention/TTL: 16 passed;
- Cell: 4 passed;
- same-login/two-`SET ROLE` attack reproduced and rejected;
- placeholder analytics attestation exit `2` reproduced;
- 0 BLOCKER and 0 MEDIUM.

Screenshots:

- `docs/audits/assets/visa-oracle-v2/as-is-desktop-light.png`
- `docs/audits/assets/visa-oracle-v2/as-is-mobile-320-dark.png`
- `docs/audits/assets/visa-oracle-v2/final-desktop-engine-supported.png`
- `docs/audits/assets/visa-oracle-v2/final-mobile-320-engine-reduced-motion.png`
- `docs/audits/screenshots/visa-oracle-v2/book-pricing-chromium.png`
- `docs/audits/screenshots/visa-oracle-v2/book-pricing-mobile-chrome.png`
- `docs/audits/screenshots/visa-oracle-v2/visa-oracle-privacy-v1-desktop.png`
- `docs/audits/screenshots/visa-oracle-v2/visa-oracle-privacy-v1-mobile-320.png`

## Production operational verification (night 2026-08-07→08, Mini)

Everything below was executed against the real `nuzantara-postgres` /
`nuzantara-rag` production stack, not staging or a disposable database.
Detailed contemporaneous memory: `ops_visa_oracle_pack003_gates_proven_2026_08_08.md`.

**D1 — roles and least-privilege repair.** Provisioned the 5 missing
capability roles (`visa_ledger_owner`, `visa_pack_writer`, `visa_policy_writer`,
`visa_privacy_operator`, plus repair of `visa_activation_executor`'s
over-broad grants) and repaired ownership/grants on every Visa Oracle
table/function per `docs/runbooks/visa-oracle-privacy-enforce-gate.md` §2, in
one atomic transaction. Verified against `operational_preflight.py`'s
allowlists.

**P0 — production outage caused by D1, diagnosed and fixed same night.**
Moving table ownership to `visa_ledger_owner` broke `SELECT ... FOR SHARE`
inside 3 migration-264 `bind_*` trigger functions (idempotency/decision/payload
retention binding) — the runtime role lost the UPDATE-adjacent privilege
`FOR SHARE` requires. Symptom: every `POST /evaluate` returned
`TEMPORARILY_UNAVAILABLE` / `IDEMPOTENCY_UNAVAILABLE`. Cure: `ALTER FUNCTION
... OWNER TO visa_ledger_owner` + `SECURITY DEFINER` on all 3 functions,
verified via probe transaction and live evaluate. **This is currently a
hand-applied production cure without a matching migration file** — PR #3766
(open) codifies it as migration 268; merging it is a no-op against prod.

**D2/D2b — preflight, retention policy registration.** Read-only production
preflight: green (the one flagged item, `pg_has_role` superuser bypass on
`flypgadmin`/`postgres`/`repmgr`, is a structural false positive — accepted
and documented, not a real finding). Privacy Policy V1 registered via the
canonical `register_privacy_policy` ceremony (worked around a real packaging
defect in `default_policy_path()` — eager `Path(__file__).resolve().parents[5]`
assumes a fuller checkout than the container ships; flagged for a repo fix,
not patched in place). Retention gate query confirmed `count=1` for
`environment=PRODUCTION`.

**D3a — retention scheduler.** `visa_retention_worker_mini` persistent LOGIN
minted, LaunchAgent installed on Mini (`com.nuzantara.visa-oracle-retention.15min.plist`,
`StartInterval=900`, `KeepAlive=false`). Tested dry-run and real one-shot
(clean no-op, 0 expired rows). `VISA_ORACLE_RETENTION_APPLY` was later flipped
`true` (real deletions armed) — confirmed live and healthy: first `apply=True`
run at 16:01:37Z, every run since reporting `healthy=True`, 0 backlog. Cell
sensor + `cron-wrapper.sh`'s unconditional Telegram P0-on-failure alert are
both confirmed armed. **Residual risk to flag for Zero, not a defect**: the
Telegram alert fired for real once during this session, triggered by a
transient DSN URL-encoding bug in the operator's own test harness (caught and
fixed same session, not a production credential/data issue) — a benign false
page that Zero should be told about since it did reach a real alert channel.

**D3b — production smoke.** Pack hash: proven indirectly (the live evaluate
call would have raised on a `verify_rule_pack` integrity mismatch; it did
not). Policy active: confirmed. Trust store: 2 non-revoked PRODUCTION/TEST
keys present, 1 facts-fingerprint key (`fp-2026-07-1`) matching what live
decisions actually use. Source age / freshness: see "Source and Calling Visa
decisions" above. PricingTool snapshot SHA
`97e377d769df7f2dd060cba1896c13362a7419001dcc526c60d2522147c0c2a8`: identical
in worktree and live container.

**D3c / rollback proven — kill-switch drill.** Executed and proven, not just
prepared: `VISA_ENGINE_EVALUATE_MODE` flipped `SHADOW → OFF` at 16:10:50Z;
verified live `POST /evaluate` returned `TEMPORARILY_UNAVAILABLE` /
`EVALUATE_SURFACE_DISABLED` (HTTP 200, fail-closed) by 16:12:28Z; flipped back
`OFF → SHADOW` at 16:12:43Z, verified restored to ordinary CURATED evaluation
by 16:13:44Z. All 4 `nuzantara-rag` machines confirmed consistent post-restore.
**This is the rollback proof**: the kill switch is a single Fly secret flip
(`flyctl secrets set VISA_ENGINE_EVALUATE_MODE=...`), each direction costs one
rolling machine restart (the app runs on a single machine per process group,
so each flip is a real, brief availability blip beyond the intentional OFF
window — plan around that for any future drill), and both directions were
independently verified against a live evaluate call rather than assumed from
the secret-set command succeeding.

**RulePack correction — Cameroon/Guinea Calling Visa fix, activated.**
`rulepack-prod-002` (the first attempt at the fix, `sequence=2`,
`valid_period.from=2026-08-06`) was signed and inserted but **could never be
activated**: `visa_activate_rule_pack`'s bitemporal guard refused it twice
(independently, by two different operators — the second attempt reproduced
the identical verbatim error, confirming the diagnosis) because its
legal_period did not fully cover `prod-001`'s still-open `[2026-07-25, ∞)` —
activating it as-is would have orphaned 12 days of legal history, which the
append-only design correctly refuses to allow silently. Resolution
(Zero-ratified, "strada A"): re-signed the identical rule/product/source
content as `rulepack-prod-003` (`sequence=3`,
`rule_pack_id=37be33e4-8fbb-55bc-8fe2-7dcb23eab979`,
`valid_period.from=2026-07-25` — retroactive, justified because the official
CM/GN removal sources predate the entire contested window by years). Signed
on M5 (`ssh air`, key never left `~/.config/nuzantara/visa-signing/`),
activated `783f5fcc-d7cd-4cc5-ba22-c6724d4a3bf1` at 16:34:34Z. `visa_rule_packs`
now holds 3 rows; **`prod-002`'s row is permanently inert** (append-only,
`sequence` unique per environment/jurisdiction/domain — it can never be
reused or deleted) and is documented here as the aborted-ceremony artifact it
is. New convention adopted for `rule_pack_id` going forward (the historical
one was not reconstructable from the 2 existing samples):
`uuid5(NAMESPACE_URL, "https://balizero.com/visa-oracle/rule-pack/<ENV>/<JURISDICTION>/<DOMAIN>/<sequence>")`.

Ceremony note, for completeness: the first real-activation attempt against
`prod-003` accidentally re-ran the previous session's script unmodified
against `prod-002`'s file (a mistake in re-labelling output text instead of
correcting the underlying command); it reproduced the same rejected-guard
error, no database write occurred, and it was caught and corrected before
being reported anywhere. The corrected, successful attempt (the one recorded
above) is the one that actually wrote to `visa_rule_packs`.

A mandatory pre-activation semantic diff (001 vs corrected-002/003 content)
surfaced one change outside the expected CM/GN/NE scope:
`LIMITED_STAY.extension_policy.allowed` flipped `true → false`. Verified
**deliberate, not a defect**: `docs/audits/2026-08-06-visa-oracle-g1-source-decision-packet.md`
point 9 decided all uncited extension policies become explicit neutral
`UNKNOWN`/`EXTENSION_POLICY_NOT_VERIFIED`, and
`test_prod_sequence2_bundle.py` enforces the invariant `status=UNKNOWN ⇒
allowed=false` — a fail-closed abstention, not a new prohibition; the
`status` field is what a consumer should actually read. Zero-approved. This
is the value of running the diff as a hard gate rather than trusting a
pre-written expectation list.

Live smoke (3/3 PASS, 16:37:16–16:37:37Z), all responses citing `rule_pack
{sequence: 3, version: "2026.8.8"}`:

| Nationality | `state`                 | `review_reasons`                                                              |
| ----------- | ----------------------- | ----------------------------------------------------------------------------- |
| Cameroon    | `HUMAN_REVIEW_REQUIRED` | D1/D2/D12 document requirements only — **no `CALLING_VISA_REVIEW`** (the fix) |
| Nigeria     | `HUMAN_REVIEW_REQUIRED` | `['CALLING_VISA_REVIEW']` only — **positive control, mechanism still armed**  |
| Italy       | `HUMAN_REVIEW_REQUIRED` | Same document-requirement baseline as Cameroon — unchanged                    |

Independent post-activation DB re-verification (separate operator):
`visa_ruleset_activations` shows exactly 2 rows — `prod-001` closed at
16:34:34Z (the same instant `prod-003` opened, no gap, no overlap) and
`prod-003` current/open. `visa_rule_packs` holds all 3 rows (1 active
history, 1 permanently inert, 1 current).

Ephemeral ceremony credentials (`visa_pack_writer_ceremony_260808`,
`visa_activation_ceremony_260808`) were actively dropped after use, not left
to expire.

## Key implementation pointers

- Engine: `apps/backend-rag/backend/services/visa_engine/`
- Evaluate endpoint: `apps/backend-rag/backend/app/routers/visa_oracle_evaluate.py`
- Atomic replacement migration:
  `apps/backend-rag/backend/db/migrations_v2/267_visa_replace_activation_set.sql`
- Activation CLI:
  `apps/backend-rag/backend/scripts/visa_engine/activate_pack.py`
- Complete-set correction CLI:
  `apps/backend-rag/backend/scripts/visa_engine/replace_activation_set.py`
- Operational preflight:
  `apps/backend-rag/backend/scripts/visa_engine/operational_preflight.py`
- Retention worker:
  `apps/backend-rag/backend/scripts/visa_engine/retention_worker.py`
- Frontend: `apps/mouth/src/app/(visa-oracle)/visa-oracle/`
- Final operational record:
  `docs/audits/2026-08-06-visa-oracle-operational-gates.md`
- Privacy/ENFORCE runbook:
  `docs/runbooks/visa-oracle-privacy-enforce-gate.md`
- Retention operations runbook:
  `docs/runbooks/visa-oracle-retention-operations.md`

## Remaining production blockers

Status as of 2026-08-08 — items 1–5 and 8–9 are **DONE**, verified against
real production (see "Production operational verification" above). Items 6, 7
and 10 are **still open** and are the actual gate to ENFORCE.

1. ✅ **DONE.** Reviewed branch merged to `main`: PR #3732, `63234a12a`,
   2026-08-07T12:34:07Z. Frozen G6 baseline confirmed a full ancestor.
2. ✅ **DONE.** Migrations through 267 applied in production; migration 264's
   downstream trigger-ownership defect (see P0 above) hand-cured in prod, PR
   #3766 (open) codifies it as migration 268 — merging it is a no-op catch-up,
   not a new prod change.
3. ✅ **DONE.** All 6 capability roles provisioned and proven: `visa_ledger_owner`,
   runtime (`backend_rag_v2`), `visa_pack_writer`, `visa_activation_executor`,
   `visa_policy_writer`, `visa_privacy_operator`, `visa_retention_executor`.
4. ✅ **DONE.** Mis-arm corrected: runtime role no longer owns activation
   writes or has pack-table access; mutation functions re-owned to
   `visa_ledger_owner`; `visa_ledger_owner` provisioned. (The D1 repair itself
   caused the P0 `FOR SHARE` outage above — fixed same session, see P0.)
5. ✅ **DONE.** 15-minute LaunchAgent installed on Mini, observed running,
   `APPLY=true` (real deletions armed) confirmed live and healthy. 30/60-minute
   Cell sensor alerting + `cron-wrapper.sh`'s unconditional Telegram
   failure-alert both confirmed armed (the latter fired for real once, a
   benign false page — see D3a residual-risk note above, worth mentioning to
   Zero).
6. ⬜ **STILL OPEN.** Identify the real analytics destination/provider and
   obtain a fresh, closed-schema 90-day TTL export plus
   prior-present/expired/control probe. Zero decision, no progress since the
   original assessment.
7. ⬜ **STILL OPEN.** DPIA (`docs/audits/2026-08-06-visa-oracle-dpia-v1.md`) is
   an unsigned draft — controller entity and Privacy/DPO owner both marked
   `OPEN`, signature block blank, explicit closing line "**DO NOT ENFORCE —
   open high residual risks remain**." Processor/region inventory and
   lawful-basis record still incomplete. Zero must name owners and approve
   residual risk before this closes.
8. ✅ **DONE.** Read-only production preflight green (one structural false
   positive, documented and accepted). Production smoke: pack hash (indirect
   proof via successful integrity-checked evaluate), policy active, trust
   store keys present and matching live decisions, source freshness
   `CURRENT`, exact PricingTool SHA match — all confirmed. See "Production
   operational verification" for the full table.
9. ✅ **DONE.** Kill-switch drill executed and proven both directions
   (`SHADOW→OFF` at 16:10:50Z, verified `EVALUATE_SURFACE_DISABLED`;
   `OFF→SHADOW` at 16:12:43Z, verified restored), not merely rehearsed. This
   doubles as the rollback proof this closure report requires.
10. ⬜ **STILL OPEN — the actual remaining gate.** ENFORCE evaluation requires
    items 6 and 7 closed first. `VISA_ENGINE_EVALUATE_MODE=SHADOW` confirmed
    live; no one has requested or executed an ENFORCE flip. Activation of a
    corrected RulePack (done, see above) is explicitly a different action from
    an ENFORCE mode change — do not conflate the two when reading this record.

## Decisions still requiring Zero

- Approve the DPIA and residual privacy risk after processor/region/lawful-basis
  facts are filled in (blocker 7, unchanged — still fully open).
- Name the analytics destination owner and accept its independently reproduced
  TTL proof (blocker 6, unchanged — still fully open).
- Own/SLA the freshness-policy re-verification cadence (G1 packet point 6):
  the signed pack declares 7d/365d recheck intervals but no automated
  scheduler exists yet; next manual recheck for the 19 portal sources due
  ~2026-08-13.
- Be informed of the benign spurious Telegram P0 alert fired during D3a
  testing (transient DSN bug in the operator's own harness, not a production
  incident) — no action required, just visibility.
- Explicitly authorize the ENFORCE flip once blockers 6 and 7 close — every
  operational/technical prerequisite is now proven, this is a pure policy
  decision at that point, not a technical one.
- Decide the disposition of PR #3766 (migration 268 catch-up, open) and PR
  #3765 (unrelated mouth verdict-panel fix, open) — both are pending merge,
  neither blocks the operational state recorded here.

Already decided by Zero and not open for re-litigation without new evidence:

- national source precedence;
- official Cameroon and Guinea Immigration announcements are sufficient G1
  primary evidence;
- Cameroon/Guinea Calling Visa removal is retroactive to the whole
  `prod-001` legal window (2026-07-25 onward) — "strada A", executed;
- `LIMITED_STAY.extension_policy` fail-closed `UNKNOWN`/`allowed=false` for
  every uncited policy is deliberate (G1 packet point 9), not a defect;
- PricingTool catalogue remains current until superseded/withdrawn;
- Privacy Policy V1 terms listed above;
- one all-inclusive client price, never a fee split;
- retention `APPLY=true` (real deletions armed) — executed;
- production RulePack activation of the corrected pack — executed. **ENFORCE
  itself remains a separate decision, not yet made.**

## Safe resume sequence

```bash
cd /Users/nuzantara/nuzantara

# Required machine/peer/main check from AGENTS.md first.

cd /Users/nuzantara/nuzantara/.worktrees/backend-rag-visa-oracle-v2-operational-gates
git status --short --branch
git log --oneline -5
git rev-list --left-right --count main...HEAD
git diff --check

cd apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. python -m pytest \
  backend/tests/services/visa_engine \
  backend/tests/routers/test_visa_oracle.py -q
```

Then run Mouth typecheck/Vitest, Playwright and the disposable full-stack smoke
if the rebase or review touches relevant files. Never use production writes to
prove a repository gate.

## Final handoff rule

Repository G0–G6 is green for the recorded frozen baseline and reviewed
candidate, **and** the operational prerequisites (roles, migrations, policy,
scheduler, corrected RulePack activation, production smoke, kill-switch
rollback) are now proven green in real production as of 2026-08-08. Production
remains **NO-GO for ENFORCE / confirmed live in SHADOW** — that is a distinct,
still-unmade, Zero-gated decision blocked on the DPIA and analytics-TTL items
above, not a technical one. Any future legal rule, signed pack, source policy,
price identity, privacy term, privilege or runtime-authority change reopens
the relevant gate and requires generator ≠ grader evidence.
