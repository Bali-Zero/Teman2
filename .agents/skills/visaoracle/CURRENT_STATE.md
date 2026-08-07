# Visa Oracle V2 — Current State

Snapshot: 2026-08-07, Asia/Makassar  
Owner: Zero / Bali Zero  
Purpose: canonical restart and Claude-review handoff for `/visaoracle`

## Read this first

Visa Oracle V2 is repository-complete on the frozen reviewed baseline, but it
is **not authorized for production ENFORCE**. The public/runtime posture remains
SHADOW until the operational gates in this document are proven against the real
production environment.

Do not infer that a green repository candidate means the production database,
scheduler, analytics TTL, DPIA or kill-switch drill has been provisioned. Do not
merge, push, deploy, activate a RulePack or change ENFORCE from this record.

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

- Integration worktree:
  `/Users/nuzantara/nuzantara/.worktrees/backend-rag-visa-oracle-v2-operational-gates`
- Branch:
  `agent/mini-pro2/backend-rag/visa-oracle-v2-operational-gates`
- Frozen G6 baseline: `cd343655c7d77f65f50897f91c299ba92da35cb0`
- Independently reviewed candidate: `635bbccd00ba5ad578eaaadcd27415918b2e1bc1`
- Independently reviewed final delivery record:
  `e15fc1b84501cbdc2e023497b3e1af298f51034f`
- Independent verdict: **LGTM, 0 BLOCKER, 0 MEDIUM**.
- This `CURRENT_STATE.md` update is a documentation-only continuation after
  that exact-SHA review; the reviewed implementation remains its ancestor.

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
G6 baseline.

Before review or merge, Claude must:

1. restore Mini/Pro git synchronization;
2. inspect every post-baseline commit for overlap;
3. rebase the worktree branch, never the main checkout;
4. rerun impacted G5 tests and `git diff --check`;
5. request a new exact-SHA G6 review if the rebase changes product/runtime/test
   behavior or creates a conflict.

Do not keep chasing unrelated concurrent `main` commits during a running G6
review. Freeze and record the reviewed baseline; handle later drift explicitly.

## Gate matrix

| Gate                                    | Initial state    | Reviewed repository state  | Production state                  |
| --------------------------------------- | ---------------- | -------------------------- | --------------------------------- |
| G0 inventory / AS-IS                    | PASS             | PASS                       | N/A                               |
| G1 contracts and sources                | BLOCKED          | PASS                       | freshness scheduler still unarmed |
| G2 engine and gold/adversarial harness  | PARTIAL          | PASS                       | migrations/roles not provisioned  |
| G3 UI states and categories             | PARTIAL          | PASS                       | reviewed candidate not deployed   |
| G4 backend authority over public result | PARTIAL / SHADOW | PASS in candidate          | production remains SHADOW         |
| G5 automated verification               | PARTIAL          | PASS                       | production smoke not run          |
| G6 independent review                   | PENDING          | PASS, 0 BLOCKER / 0 MEDIUM | does not authorize ENFORCE        |

Activation verdict: **NO-GO** until every operational prerequisite below is
measured green.

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

The 15-minute LaunchAgent example is not installed and defaults to dry-run. It
uses zero immediate retries so backlog/lag exit `2` cannot be retried until the
required alert disappears. Cell thresholds are warning at 30 minutes and
critical at 60 minutes.

Analytics TTL is an independent ENFORCE gate. The checked-in placeholder
attestation exits `2` fail-closed. It must not delay an already-due database
purge.

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

1. Synchronize Mini and Pro and integrate the reviewed branch onto the current
   reviewed `main` without losing exact-SHA evidence.
2. Apply migrations 264–267 in staging and then in an approved production
   change window.
3. Provision and prove the separated roles: ledger owner, runtime, pack writer,
   activation executor, policy writer, privacy operator and retention executor.
4. Correct the previously observed production mis-arm: runtime activation
   writes, executor pack-table access, runtime-owned mutation functions and
   absent `visa_ledger_owner`.
5. Install and observe the 15-minute retention scheduler; prove 30/60-minute
   alerts and retention backlog/lag behavior.
6. Identify the real analytics destination/provider and obtain a fresh,
   closed-schema 90-day TTL export plus prior-present/expired/control probe.
7. Complete processor and region inventory, controller details, lawful-basis
   record and DPIA; Zero must approve residual risk.
8. Run the read-only production preflight and production smoke. Compare active
   pack/hash, policy, roles, keys, source age, exact PricingTool snapshot and
   retention evidence.
9. Run and record the kill-switch drill.
10. Only after all evidence is green may the pre-authorized ENFORCE procedure be
    evaluated. Activation remains a separate explicit operation.

## Decisions still requiring Zero

- Approve the DPIA and residual privacy risk after processor/region/lawful-basis
  facts are filled in.
- Approve the production change window for migrations, ownership transfer,
  grants, HMAC/key overlap and scheduler installation.
- Name the analytics destination owner and accept its independently reproduced
  TTL proof.
- Accept the post-provision production smoke and explicitly authorize the
  controlled RulePack activation/ENFORCE sequence if every objective gate is
  green.

Already decided by Zero and not open for re-litigation without new evidence:

- national source precedence;
- official Cameroon and Guinea Immigration announcements are sufficient G1
  primary evidence;
- PricingTool catalogue remains current until superseded/withdrawn;
- Privacy Policy V1 terms listed above;
- one all-inclusive client price, never a fee split.

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

Repository G0–G6 is green only for the recorded frozen baseline and reviewed
candidate. Production remains NO-GO/SHADOW. Any future legal rule, signed pack,
source policy, price identity, privacy term, privilege or runtime-authority
change reopens the relevant gate and requires generator ≠ grader evidence.
