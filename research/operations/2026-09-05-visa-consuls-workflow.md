# Visa product consuls: execution contract

Owner mandate: 2026-09-05. Complete GARUDA VOA, Second Home and Visa Oracle,
covering both engines and customer/staff UI, through coordinated multi-LLM work.

## Coordination and authority

- Codex consul: thread `01a0703b-22d9-7270-8b93-d13e560968cc`, Air-M5.
- Fable 5.1 consul: interactive session `7561e9d7-d544-48e5-a211-b3534020394d`,
  Air-M5. Located by the matching owner mandate and live session registry.
- Handshake acknowledged by Fable and read in this session. The first discovery
  dispatches preceded that agreement; implementation ownership is now accepted.
  Future execution requires acknowledged ownership and a nonempty file list.
- Shared coordination worktree: `.worktrees/ops-visa-consuls`.
- Codex owns this workflow and `2026-09-05-visa-consuls-state.json`.
  The acknowledged split is preserved in `2026-09-05-visa-consuls-agreement.md`.
  Addressed fleet-mail messages carry future updates; the initial temporary reply
  file is transport history only, not the resume source.
- Fable owns the shared index at
  `.worktrees/ops-visa-consuls-claude/.agent/consoli/BOARD.md`. Codex sends updates
  by addressed mailbox instead of racing a full rewrite of that index.
- Implementation ownership is per exact file and task, not just per product.
  The consuls serialize overlapping files and lockfiles before dispatch.
- Codex prepares and tests; independent Anthropic review and the existing
  controlled shipping path remain required. A consul never grades its own work.

## Execution loop

1. **Observe:** read the current corner, actual source, current PR state and
   relevant runtime evidence. Treat old plans as leads, not current status.
2. **Select:** choose the smallest reproducible customer/engine defect or
   incomplete path. Refute the finding before assigning an implementation.
3. **Claim:** record owner, exact files, base SHA, dedicated worktree, acceptance
   checks, dependency and reviewer. A task with an empty scope or an unacknowledged
   ownership split cannot enter execution. Inform the other consul before edits.
4. **Build:** use a bounded worker with the actual contract and synthetic inputs.
   Add a regression that fails before the fix when behavior is nontrivial.
5. **Challenge:** a different model family attacks the diff and its assumptions.
   Code authors may explain evidence but cannot approve their own artifact.
6. **Verify:** rerun relevant tests on the exact revision, exercise the customer
   path, and inspect mobile/desktop rendering where layout changed. An HTTP 200
   alone does not establish working UI, truthful copy or engine correctness.
7. **Prepare:** commit one concern, open a reviewable PR with a `Bites:` consumer
   and observed proof. Record head SHA and cross-family reviewer dispatch.
8. **Ship and prove:** the authorized Claude session owns the controlled ship
   path. Production observations must identify the deployed revision and actual
   behavior. Preserve business gates separately from engineering readiness.
9. **Continue:** reconcile receipts, PRs and evidence, select the next ready task.
   Queue unavailable seats with explicit reason; never label an unrun check PASS.

A peer's process being alive does not prove it is executing. On 2026-09-05 its
session registry reported `waiting / permission prompt`, and its requested
`Workflow` had no result. The owner was notified to resolve that prompt in the
other window. Mailbox files remained queued; no ground or review completion was
inferred from delivery. Independent, nonoverlapping Codex work continued.

Use existing primitives: `scripts/agent_start.py` for isolation,
`scripts/fleet_mail.sh` for addressed messages, the session's agent tools for
bounded work, and the existing evidence/gate pipeline. No new daemon is needed.
`scripts/modus_autoloop.py` is not an execution guarantee: its inspected
implementation documents a no-spawn path. This campaign is driven by the active
consul sessions and the explicit Codex goal.

## Model roles

| Role | Seat | Output | Independent check |
| --- | --- | --- | --- |
| Systems/integration consul | Codex Astra, owner-selected | Claims, contracts, reproduced failures, implementation integration | Fable/Anthropic review |
| Product/design consul | Fable 5.1, owner-selected window | Product decisions, design integration, assigned implementation | Codex behavioral/refutation evidence |
| Bounded implementer | Existing subscription worker selected per task | Small isolated diff and regression evidence | Other family; never self-approval |
| Constructive reviewer | Gemini subscription when an independent third lens is useful | Simplifications and missed user paths | Consuls test proposed changes |
| Regulatory verifier | Relevant NotebookLM and current primary source | Exact claim/source applicability | Separate source-to-engine check |
| Final gate | Existing mandated Anthropic gate | Revision-bound verdict | Existing CI/gate mechanism |

The existing final-gate roster remains binding. The owner's manual Fable 5.1
selection authorizes this interactive consul, not an automatic rewrite of all
fleet gate settings. Model identity, actual route, completion and any fallback
are recorded separately; a requested model is never proof of a completed call.

Air-M5 handles editing and bounded lightweight tests. Pro handles heavy builds,
backend suites, rendering batches and local inference. Client/OSINT data stays on
Pro; all campaign fixtures and shared artifacts are synthetic or non-PII.

## Current work packages

| ID | Product | Task | Initial state | Acceptance |
| --- | --- | --- | --- | --- |
| G-01 | GARUDA | Truthful payment labels and live fulfillment polling | Draft PR #5761; review requested | No paid claim without paid order state; no charge-absence promise on failed/expired; Approved/Blocked transitions keep updating; terminal/unmount cleanup tested |
| V-01 | Visa Oracle | Route missing-input edits to the current branch | Draft PR #5762; review requested | Shared fact paths choose an editable question in the active history; edit opens it and prevents repeated unchanged evaluation |
| S-01 | Second Home | Reliable save/copy feedback | Draft PR #5763; review requested | Blocked storage is not reported as saved; clipboard denial offers an actionable fallback |
| S-02 | Second Home | Reject a practice belonging to another client | Draft PR #5764; review requested | Synthetic mismatched client/practice pair is rejected before case insertion; matching pair passes |
| V-02 | Visa Oracle | Negative witnesses against actual signed-pack content | Accepted by Fable engine owner | Regression measures highest signed candidate; source-only merge cannot masquerade as signed/live correction |
| G-02 | GARUDA | Document persistence and DDL integration | Existing PR #5526; do not duplicate | Existing owner decision and migration path, then upload/OCR/persistence/review verification |
| V-03 | Visa Oracle | Consultant request persistence | Existing PR #5037; do not duplicate | Inherit the existing lane and its gate rather than recreate tables |
| V-04 | Visa Oracle | Consultant available throughout the interview | Full UI tested and pushed at ff60b29a09 on exact #5762 dependency; PR waits for parent merge/rebase | Generic contact contains no invented verdict or interview answers; context-specific consent; visible control on every interview phase |
| B-04 | Second Home editorial surface | Reject unknown article categories before metadata lookup | Draft PR #5765 fixes index contradiction; single-tag criterion remains unmet | Unknown category cannot inherit an indexable canonical article's metadata; canonical, alias and noIndex controls preserved; literal tag-count proof is still open |

## Completion evidence by product

- **GARUDA:** eligibility/intake → authoritative price → payment truth → document
  processing → staff transitions → customer tracker. Tests cover failure,
  retry and idempotency as well as successful progression.
- **Second Home:** grounded route choices → editable plan → truthful save/share
  feedback → authorized case creation with valid associations → lifecycle status.
  Browser persistence limits must be visible to the user.
- **Visa Oracle:** branch selection → appropriate questions → engine contract →
  source-grounded result → missing-input correction → consultant fallback.
  Positive support tests alone do not prove exclusion rules; add negative witnesses.

## Distinct business gates

Keep Visa Oracle in its existing SHADOW posture. ENFORCE, RulePack activation,
sales opening, real payments, credentials/consents and unresolved business terms
are separate actions with their existing explicit gates. Second Home letters,
property validation and first-real-case Day-90 requirements cannot be replaced by
synthetic test success. Do not insert synthetic cases into production to make a
proof appear complete.

The overall campaign remains active while any required product path or gate is
unresolved. A tested diff is `tested`, an independently reviewed diff is
`reviewed`, a merged diff is `merged`, and only observed production behavior is
`verified_live`. These states are never interchangeable.

## Refuted leads

- Second Home clear-plan URL resurrection: refuted by `clearPlan()` in
  `apps/mouth/src/lib/secondhome-studio/plan-codec.ts`, which removes the fragment.
- Direct client A → B switch retaining a practice in the normal picker flow:
  refuted because the picker requires clearing first. The API ownership question
  is a separate finding and must be tested independently.
- Visa Oracle noindex restoration: already present on disk and independently
  observed in production on 2026-09-05; served metadata is `noindex, nofollow`.
- Visa Oracle fullstack smoke described as never green since #4709: refuted by
  run `33944949234`, job `101249240297` on main `af949e6e`, completed
  `2026-09-05T04:38:51Z`, and run `33948149675`, job `101257973087` on unrelated
  branch `7d9763ff`, completed `2026-09-05T05:52:45Z`. In both jobs the actual
  `Run the disposable-DB fullstack smoke` step succeeded; retry steps were skipped.
  This is CI evidence, not a production customer-journey observation.
- Portal FR/RU missing keys: already fixed by #5612. Five locales have matching
  271 leaf keys and 12 portal keys; the existing parity suite passed 16 cases.
- Blanket F7 archive deindexing: invalid `/blog/...` routes can produce a 404
  noindex while their canonical `/living/...` or `/visas/...` articles remain
  indexable and in the sitemap. Editorial assessment must use canonical URLs.
- Public GARUDA `/visa/voa` currently displays the not-found page in the clean
  mobile browser. Source explicitly enforces the existing public-release flag
  in its server layout. This observation is not permission to open sales.

## First-wave review handoff

The five draft PRs have passed their scoped regression tests and commit/push hooks.
Exact head SHAs, test receipts and addressed-review timestamps live in the state
JSON. Those revisions are queued in Fable's single-writer inbox and fleet mailbox;
the unresolved permission prompt means receipt is not inferred from enqueueing.
All five PRs have completed their reported GitHub checks without failed or pending
checks at the recorded observation. Skipped and neutral checks are not execution
proof. Independent verdicts and production proof remain pending; browser evidence
is scoped below. No consul may infer these observations from PR creation.

S-02 received an evidence-only follow-up after CI detected public hashes and a
synthetic DSN as unaudited findings. The corrective commit uses narrow annotations
on verified public hashes and a credential-free loopback command. That command
was rerun on Pro (41 tests passed). Unannotated synthetic guilty controls still
fail the scanner; the new GitHub secret check passed. Python source is unchanged.

S-01 has real Chrome evidence on its exact commit: three denied-storage/clipboard
conditions recover through a selectable link without horizontal overflow at
390 px. V-04 has real Chrome evidence at 320/390/1280 px in English and Indonesian,
including keyboard, focus, consent, QR, unique IDs and print exclusion. These are
isolated Pro localhost proofs, not production delivery. The second Gemini review
covered only the four consent files; it did not grade the complete UI or replace
the required independent Anthropic gate.

V-04 is committed and pushed as `ff60b29a09cbbf4dbb21eb22b263b8bee6065d40`,
with a dedicated evidence pack, normal hooks and full mouth TypeScript passing.
The remote SHA matches the clean local branch. Its V-01 dependency remains
explicit; the next PR is created after that parent merges and the base is refreshed.
The Pro browser sessions and temporary servers used for S-01, V-04 and B-04 are
closed, with ports 3417, 3420 and 3214 free. Source snapshots and receipts remain
available for the independent reviewer.

B-04's rendered HTML exposed a remaining criterion failure despite passing unit
tests. A single private `robots: null` candidate removed the duplicate from HTTP
HTML and the Googlebot response, but loaded Chrome still contained two noindex
tags. No candidate correction was committed. The failure spec and receipts are
under `output/reviews/b04-robots/`; the current PR body states the limitation.
The next investigation must distinguish development-mode hydration from a
production build before defining a further implementation. The one-tag criterion
has not been weakened or marked passed.

## Constructive review disposition

Gemini 3.1 Pro subscription review completed through the `agy` plan/sandbox door.
It identified early execution before handshake, an empty claimed file list and
the temporary reply path as coordination weaknesses. All three are accepted:
the acknowledged split, explicit task-level scope/base/checks and durable agreement
now replace the initial provisional entries. No runtime/production behavior was
verified by that review. Its original artifact is
`~/.gemini/antigravity-cli/brain/3c365124-4006-418c-89bb-efa0682a0d2b/workflow_review_plan.md`.
