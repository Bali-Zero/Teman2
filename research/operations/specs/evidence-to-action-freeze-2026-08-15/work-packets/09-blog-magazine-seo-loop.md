---
adversarial_review: exempt-frozen-spec-landed-verbatim-from-10d500e1c
---

# Work Packet 09 — Blog, Magazine, and SEO Outcome Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this packet task by task. Track execution with the checkboxes in this document. Use an independent reviewer before merge.

**Wave:** 2; read-only measurement scaffolding may start after Packets 02 and 04, while outward-adapter integration also waits for Packets 12 and 18.

**Goal:** Connect approved content to truthful deployment, indexing, audience, and commercial outcomes across the Bali Zero blog and Bali Zero Magazine without activating external publication.

**Architecture:** Use the Packet 04 canonical `OutcomeEvent` repository and build read-mostly publication/SEO projections keyed by the canonical IDs from Work Packet 02. Adapt the blog post-publish and indexing jobs, SEO Cell sensors, and Magazine preparation/publishing code to emit through that one repository. Separate notification, deployment, sitemap inclusion, verification, availability, and indexing so each metric means exactly what it says.

**Tech Stack:** Python 3.11+, FastAPI services, asyncpg/PostgreSQL, Google Search Console and GA4 read-only APIs, Next.js sitemap, pytest, deterministic CLI probes, macOS LaunchAgent definitions.

**Spec:** This file is the frozen execution contract. It consumes the Packet 04 canonical contracts and the Packet 02 publication specialization without changing their meanings or creating a second outcome ledger.

**Depends on:** Packets 04 and 02 for canonical content/publication truth, Packet 18 for an operator-confirmed `ConductorHandoff`, and Packet 12 for deterministic publication `ActionItem`/`ActionIntent` materialization and execution receipts.

## Execution-session prompt

You are implementing the evidence-to-outcome loop after Work Packets 04 and 02 have passed independent review. Read-only outcome work may begin at that point; any outward-adapter integration also waits for independently reviewed Packets 12 and 18. Work in a fresh isolated worktree created from the latest authoritative Pro branch. Read `AGENTS.md`, identify the machine, verify repository and peer state, and confirm migration 274 is reserved for this packet. If a dependency required by the selected task is absent, its tests fail, or migration 274 is occupied, stop and request a versioned central-ledger revision.

This packet prepares and tests integrations only. Do not deploy, publish, install or load LaunchAgents, mutate production publication state, submit a live Indexing API notification, create a public Magazine edition, change workspace access, or send alerts. Read-only GSC/GA4 probes may be exercised manually only after credentials are verified and outputs are aggregated and PII-free; unit and integration tests use fixtures.

## Global constraints

- Consume the exact canonical sequence `generated` → `staged` → `human_approved` → `publishing` → `deployed` → `indexed_verified`.
- Consume verification and availability as independent axes; never rewrite publication history to express staleness, correction, or withdrawal.
- Do not infer `deployed` from a Git commit, pull request, CI result, database row, or queue completion.
- Do not infer `indexed_verified` from Indexing API acceptance, sitemap membership, an HTTP 200, or a successful crawl request.
- Amber content always keeps the authorized human gate.
- Red content cannot publish; it must be remediated and reclassified under Work Packet 02.
- Green content also retains the human gate during this freeze. No automatic outward action is armed.
- `human_approved` proves editorial approval only. Every outward blog or Magazine attempt also requires its own exact, unexpired publication `ActionIntent` approval, immutable started `ExecutionAttempt`, and separate typed result `OperationalReceipt`; no content receipt, generic vote, environment flag, or queue status can substitute for them.
- Blog and Magazine use the same identity, policy, state, provenance, and outcome contracts.
- Magazine consumes sanitized projections only. Raw OSINT, CRM records, NotebookLM source text, and client PII never enter the public surface or outcome ledger.
- Indexing, engagement, and lead metrics are observations. They must not trigger autonomous editorial mutation in this packet.
- Preserve the frozen embedding model and existing pricing/visa source rules.
- Use typed async I/O, structured logging, the project virtual environment, and additive schema.
- Do not modify files owned by Work Packet 02. Integrate through its exported service interfaces.

---

## Mission

Produce one truthful feedback loop:

```text
research candidate
  → canonical publication truth
  → approved artifact
  → publishing attempt
  → live deployment proof
  → sitemap/canonical proof
  → indexing notification
  → verified Google index state
  → 7/28/60/90-day GSC, GA4, and organic-lead outcomes
  → read-only editorial evidence report
```

The loop must distinguish blog and Magazine surfaces while allowing comparison by canonical content-object reference, topic, source set, risk class, and artifact revision. It must expose missing and stale evidence instead of converting absence into success.

## Why now: verified live baseline

The following baseline was verified read-only on the authoritative Pro on 2026-08-15:

### Research and blog publication

- The live nightly Intel job runs at 01:00 WITA and completed its latest run.
- Seven articles were enriched and SEO-optimized, then seven of seven were submitted to staging and explicitly left `awaiting News Room approval`.
- The post-publish poller is installed and runs every 300 seconds: `/Users/nuzantara/Library/LaunchAgents/com.balizero.post-publish-poller.plist:22-40`.
- Its code can perform SEO/GEO work, translations, two cover formats, Git batching, and queue completion: `apps/bali-intel-scraper/scripts/post_publish_poller.py:3-24` and `:1198-1304`.
- The live post-publish queue was empty during the audit. That means no item was waiting after publication; it does not prove that staged items were published.
- The blog loader is live and hybrid: backend articles have priority, MDX is legacy/fallback, and the path documents `scraper → staging → approval → publish`: `apps/mouth/src/lib/blog/articles.ts:1-8` and `:756-858`.
- `https://balizero.com/sitemap.xml` returned HTTP 200 with 2,412 URLs and approximately 805 article-like entries. The newest article `lastmod` was 2026-07-25, demonstrating that daily research was not producing daily public articles at audit time.
- The backend news endpoint returned 25 approved records, with the newest `published_at` at 2026-01-13.

### Indexing

- The installed live job `com.nuzantara.daily-indexing-sweep` runs at 01:00 WITA: `/Users/nuzantara/Library/LaunchAgents/com.nuzantara.daily-indexing-sweep.plist:5-22`.
- On 2026-08-15 it recorded 200 accepted article notifications, zero failures in that batch, 1,815/3,305 submitted URLs, and 1,490 remaining.
- The article state file also retained 214 historical failed entries.
- KBLI reported 1,563 submitted for 1,559 URLs, or 100.3%, proving that submission counts are not a clean uniqueness or index-health metric.
- `articles_indexing_submit.py` records success immediately after `urlNotifications().publish(URL_UPDATED)` and appends the slug to `submitted`: `apps/evaluator/articles_indexing_submit.py:170-186` and `:232-266`.
- Its GSC priority table was last hardcoded on 2026-03-11: `apps/evaluator/articles_indexing_submit.py:55-77`.

### SEO feedback

- `com.balizero.seo-cell.daily` is installed at 19:30 WITA: `/Users/nuzantara/Library/LaunchAgents/com.balizero.seo-cell.daily.plist:18-39`.
- The latest pulse was yellow: three sensors green, four yellow, `action=None`, and its Cell Observatory emit failed authentication.
- GSC already exposes 28-day queries, clicks, impressions, CTR, and position: `apps/evaluator/seo_cell/sensors/gsc_sensor.py:66-104`.
- GA4 already exposes sessions and conversions by page: `apps/evaluator/seo_cell/sensors/ga4_sensor.py:84-139`.
- CRM attribution already exposes organic leads by landing page: `apps/evaluator/seo_cell/sensors/lead_attribution_sensor.py:92-144`.
- The cell intentionally takes no action while pre-natal, and its post-graduation action branch is also not implemented: `apps/evaluator/seo_cell/run_seo_cell.py:19-23` and `apps/evaluator/seo_cell/thinker.py:153-174`.
- Its SQLite memory had 110 episodes and zero long-term rules during the audit.

### Bali Zero Magazine

- The Magazine codebase exists and its publisher supports morning and breaking modes.
- Repo-canon schedules define morning at 08:15 WITA and breaking every 600 seconds: `infra/launchagents/com.balizero.magazine.morning.plist:21-40` and `infra/launchagents/com.balizero.magazine.breaking.plist:21-35`.
- Neither Magazine LaunchAgent was installed or loaded on Pro, and no current Magazine logs existed.
- `~/.local/state/bali-zero-magazine/` contained only 2026-07-20 artifacts: morning and breaking packets remained `publication_state=building` and one outcome remained pending.
- `https://bali-zero-magazine.antonellosiano.chatgpt.site/` responded, but unauthenticated users saw `Protected workspace / Workspace access required`.
- The deployed `/robots.txt` returned 404.

The system therefore has many valuable components but no end-to-end, truthful, learning loop.

## Explicit scope and file ownership

This execution session owns only the following implementation files and their named tests.

### Create

- `apps/evaluator/content_loop/__init__.py`
- `apps/evaluator/content_loop/contracts.py`
- `apps/evaluator/content_loop/repository.py`
- `apps/evaluator/content_loop/deployment_verifier.py`
- `apps/evaluator/content_loop/index_verifier.py`
- `apps/evaluator/content_loop/outcome_collector.py`
- `apps/evaluator/content_loop/report.py`
- `apps/evaluator/content_loop/run_daily.py`
- `apps/backend-rag/backend/db/migrations_v2/274_content_outcome_projections.sql`
- `apps/evaluator/content_loop/tests/test_contracts.py`
- `apps/evaluator/content_loop/tests/test_deployment_verifier.py`
- `apps/evaluator/content_loop/tests/test_index_verifier.py`
- `apps/evaluator/content_loop/tests/test_outcome_collector.py`
- `apps/evaluator/content_loop/tests/test_report.py`
- `apps/evaluator/content_loop/tests/test_baseline_replay.py`
- `infra/launchagents/wrappers/content-outcome-loop-daily.sh`
- `infra/launchagents/com.balizero.content-outcome-loop.daily.plist`
- `infra/launchagents/wrappers/seo-cell-daily.sh`

### Modify

- `apps/bali-intel-scraper/scripts/post_publish_poller.py`
- `apps/bali-intel-scraper/scripts/post_publish_webhook.py`
- `apps/evaluator/articles_indexing_submit.py`
- `scripts/daily_indexing_sweep.py`
- `apps/evaluator/seo_cell/run_seo_cell.py`
- `apps/evaluator/seo_cell/thinker.py`
- `apps/zantara-media/zantara_media/cli/magazine_prepare.py`
- `apps/zantara-media/zantara_media/cli/magazine_publish.py`
- `apps/zantara-media/zantara_media/magazine/contracts.py`
- `infra/launchagents/wrappers/bali-zero-magazine-publish.sh`
- `infra/launchagents/com.balizero.magazine.morning.plist`
- `infra/launchagents/com.balizero.magazine.breaking.plist`
- `infra/launchagents/com.balizero.indexing-sweep.daily.plist`
- `infra/launchagents/com.balizero.seo-cell.daily.plist`

### Forbidden in this packet

- Files owned by Work Packet 02.
- Live files under `~/Library/LaunchAgents`, `~/scripts`, or `~/.local/state`.
- Hosting access controls, DNS, the deployed Magazine site, robots configuration in production, or external site settings.
- Article generation prompts, research ranking, NotebookLM notebooks, WR2, WR3, NEXUS, CRM data, and raw OSINT.
- Production migration application, job installation, deployment, public publishing, and real Indexing API mutation.

## Inputs and frozen contracts

### 1. Packet 02 input contract

Consume these canonical values without aliases:

- `content_object_ref = {content_object_id, revision, object_hash}`
- `artifact_revision = {artifact_revision_id, artifact_sha256}`
- `surface`
- `source_kind`
- `publication_state`
- `classification = {risk_class, sensitivity}`
- `policy_version`
- `reason_codes`
- `canonical_url`
- `content_approval_receipt_ref`
- `publication_action_intent_ref`
- `publication_approval_receipt_ref`
- `current_execution_attempt_ref`
- `current_operational_receipt_ref`

If an event lacks the exact canonical content-object or artifact-revision reference, quarantine it as `unattributed` in the report. Do not manufacture identity from title alone. Legacy `content_id`, `revision_id`, or `evidence_band` fields are adapter inputs only; the adapter must resolve them to canonical refs and full classification or quarantine them, and must never emit them as canonical fields.

### 2. Surface names

Use exactly:

- `blog` for `https://balizero.com/{category}/{slug}`;
- `magazine` for `https://bali-zero-magazine.antonellosiano.chatgpt.site/` story or edition routes.

Each language derivative has its own exact canonical `ContentObject` revision and artifact revision. Variants may share an explicit origin/campaign relation, but never share or infer identity merely because titles or slugs resemble each other; canonical URL and `locale` remain derivative-specific.

### 3. Outcome event types

Register and implement these exact namespaced `OutcomeEvent.outcome_type` values:

- `publication.publish_attempt_started`
- `publication.publish_attempt_failed`
- `publication.deployment_verified`
- `publication.deployment_verification_failed`
- `publication.sitemap_verified`
- `publication.sitemap_verification_failed`
- `publication.indexing_notification_accepted`
- `publication.indexing_notification_rejected`
- `publication.index_inspection_verified`
- `publication.index_inspection_not_verified`
- `publication.correction_required`
- `publication.withdrawal_requested`
- `publication.withdrawal_completed`
- `seo.gsc_window_observed`
- `seo.ga4_window_observed`
- `seo.organic_lead_window_observed`
- `publication.surface_readiness_observed`

Only `publication.deployment_verified` may request Packet 02's `publishing → deployed` transition. Only `publication.index_inspection_verified` may request `deployed → indexed_verified`.

### 4. Deployment proof

Mark deployment verified only when all are true:

- canonical URL is present;
- HTTP response is 200 after redirects;
- final host is the expected surface host;
- canonical tag resolves to the expected normalized URL;
- no `noindex` directive is present;
- the rendered artifact contains the expected content or deployment hash;
- the probe is not an authentication wall, error shell, placeholder, or stale prior revision.

For Magazine, `Protected workspace` is not public deployment proof. Record `SURFACE_AUTH_WALL` and leave canonical state unchanged.

### 5. Sitemap proof

Sitemap membership is a separate observation:

- URL must appear in the correct sitemap;
- `lastmod` must not predate the deployed revision;
- canonical URL normalization must match;
- duplicate locale URLs must not collapse into one outcome record.

Sitemap proof never advances `deployed` to `indexed_verified`.

### 6. Verified indexing

`indexed_verified` requires a read-only Google Search Console URL Inspection result satisfying all of:

- inspection verdict is `PASS`;
- indexing state is `INDEXING_ALLOWED`;
- page fetch state is `SUCCESSFUL`;
- Google canonical matches the expected canonical URL after normalization;
- the inspection result is for the deployed revision's canonical URL;
- evidence timestamp is stored.

The verifier materializes an independent canonical `VerificationReceipt` whose target objects bind the exact `ContentObject`, artifact revision, and canonical-URL observation hashes. Only an unexpired PASS receipt may be referenced by the `publication.index_inspection_verified` `OutcomeEvent` that requests `deployed → indexed_verified`; the read-only verification does not fabricate a publication `ExecutionAttempt` or `OperationalReceipt`.

If the API is unavailable, quota-limited, unauthorized, delayed, or ambiguous, emit `index_inspection_not_verified` and keep state at `deployed`. Indexing API `URL_UPDATED` acceptance is only `indexing_notification_accepted`.

### 7. Observation windows

Collect immutable aggregate snapshots at:

- pre-deploy baseline: most recent complete 28-day window before `deployed_at`;
- operational: 7 days;
- outcome: 28, 60, and 90 days.

Metrics:

- GSC: impressions, clicks, CTR, average position, distinct queries;
- GA4: sessions and configured conversions;
- CRM: count of organic first-touch leads attributed to canonical landing page, suppressed outside the protected CRM when the cohort is below 10;
- operations: staged age, approval latency, publish latency, queue retries, deployment verification latency, index verification latency.

Do not calculate uplift when the pre-deploy denominator is missing. Emit `baseline_missing=true` instead of zero.

### 8. Editorial learning is report-only

Compute comparable outcome rows by:

- surface;
- canonical risk class;
- topic/domain;
- source kind;
- language;
- article revision;
- 28/60/90-day window.

The SEO Cell may read the report in shadow mode, but `thinker.py` must continue returning `action="none"`. Do not wire the Bayesian calibrator to mutate weights or content in this packet.

### 9. Magazine activation lock

Repo-canon Magazine wrappers must default to dry-run and additionally require `MAGAZINE_PUBLISH_ENABLED=1`. Every outward blog or Magazine wrapper requires all of:

- canonical state `human_approved` for every outward story;
- canonical `classification.risk_class` green or amber and a sensitivity permitted for the public destination;
- exact content-object and artifact-revision hash match;
- an operator-confirmed Packet 18 `ConductorHandoff` containing the exact publication `RequestedActionSpec`;
- the Packet 12 `ActionItem` and publication `ActionIntent` materialized from that exact spec;
- a separate, unexpired canonical `approve` `ApprovalReceipt` whose subject is the exact `ActionIntent` hash, whose context carries the exact `action_item_ref` ID/hash pair, and whose bindings match `arguments_hash` and `input_revision_hash`;
- an authorized effect, surface, canonical target, and time window that match the wrapper call;
- a canonical immutable `ExecutionAttempt.state=started` carrying the same approval and idempotency key;
- explicit side-effect mode;
- successful preflight.

The wrapper appends a separate immutable `execution.result` `OperationalReceipt` that references the exact started attempt ID/hash, terminal outcome, effects, artifacts/evidence, idempotency, and reconciliation state. It never updates the attempt. Only an independently verified successful operational receipt may support a later state transition; retries create a new numbered attempt. The content-revision approval and publication-action approval remain separate receipts even when shown in one interface; `Approve all` is forbidden.

No environment in this packet sets `MAGAZINE_PUBLISH_ENABLED=1`. Red never publishes. Breaking mode does not waive either approval. The flag is necessary but never sufficient.

### 10. Secret contract

- Move the repository-canon SEO wrapper to environment/Keychain-backed database configuration.
- Never copy the hardcoded connection string observed in the current live wrapper.
- The live credential must be rotated through a separately authorized incident operation; this packet only prevents the repository-canon replacement from embedding it.
- Logs and test fixtures contain no secrets.

## Deliverables

1. Packet 04 `MetricProfile`, `MetricResult`, `OutcomeEvent`, immutable attempt, and typed `OperationalReceipt` adapters plus publication/SEO snapshot contracts.
2. Additive PostgreSQL projections only:
   - `content_outcome_snapshots`, immutable per canonical content-object/artifact-revision/surface/window;
   - `surface_readiness_snapshots`, immutable operational probes.
   - collector cursors and reconciliation state; no second canonical event table.
3. A deployment verifier that distinguishes live content from CI, queue, auth wall, stale artifact, or HTTP-only success.
4. A GSC URL Inspection verifier that alone can emit `index_inspection_verified`.
5. An outcome collector correlating GSC, GA4, and aggregate organic leads by canonical page and time window.
6. A deterministic daily report with freshness, publication funnel, index health, engagement, conversions, and data-quality gaps.
7. Post-publish adapters that emit truth events without changing current outward behavior.
8. Indexing scripts that distinguish unique discovered URLs, accepted notifications, rejected notifications, pending URLs, duplicate state entries, and verified index status.
9. Removal of the stale hardcoded GSC-priority dictionary as the live scheduler input. Dynamic read-only GSC priority is used when available; deterministic zero-priority fallback is explicit and observable.
10. SEO Cell report-only ingestion with no actor activation.
11. Blog and Magazine publisher integration with Packet 02 identity plus the separate Packet 18 → Packet 12 publication authorization chain.
12. Repo-canon LaunchAgent definitions and wrappers prepared but not installed.
13. A baseline replay report reproducing the verified 2026-08-15 system state without production writes.

## Non-goals

- Publishing any blog or Magazine content.
- Removing the human gate.
- Making the Magazine site public or changing its access controls.
- Installing or loading any LaunchAgent.
- Calling the live Indexing API mutating endpoint.
- Enabling SEO Cell actions or Bayesian weight mutation.
- Improving research quality, prose, image generation, translations, WR2, or WR3.
- Backfilling all historical content.
- Declaring index success from a search-engine query or sitemap alone.

## Dependencies

- Work Packet 04 and Work Packet 02 contracts, repository read API, and transition request API must be merged or available on the execution branch.
- Packet 18 operator-confirmed handoffs and Packet 12 deterministic requested-action materialization must be available before any outward adapter can leave dry-run.
- The blog loader, post-publish queue, and current dry-run Magazine publisher must remain operational.
- Read-only GSC and GA4 credentials may be used for a manual diagnostic, but tests cannot require them.
- A production database migration, LaunchAgent installation, hosting change, and secret rotation each require their own operator-approved runbook.
- Packet 04 owns the canonical `OutcomeEvent` repository. Packet 09 owns migration 274 for projections/cursors only; no other packet may use it.

## Implementation sequence

### Task 1: Freeze outcome contracts and schema

- [ ] Write failing tests for exact event names, surface names, observation windows, immutable snapshots, exact canonical refs, and PII rejection.
- [ ] Create migration 274 tests for unique content-object/artifact-revision/surface/window projections, collector cursors, reconciliation, and rollback marker.
- [ ] Implement Packet 04 adapters, projection `contracts.py`, and migration 274.
- [ ] Implement the async projection repository and canonical OutcomeEvent writer adapter with idempotency and typed reads.
- [ ] Run tests twice to prove deterministic serialization.
- [ ] Commit with `feat(content-loop): add outcome evidence ledger`.

### Task 2: Prove deployment truth

- [ ] Write failing fixtures for valid blog, stale revision, wrong canonical, noindex, redirect to wrong host, 404, auth wall, and Magazine protected workspace.
- [ ] Implement `deployment_verifier.py` using injectable async transport.
- [ ] Require artifact/canonical proof, not HTTP 200 alone.
- [ ] Add sitemap fixtures for present/fresh, present/stale, absent, and duplicate locale cases.
- [ ] Prove only valid deployment evidence requests `publishing → deployed`.
- [ ] Commit with `feat(content-loop): verify deployed content truthfully`.

### Task 3: Separate indexing notification from indexing proof

- [ ] Write failing tests in which `URL_UPDATED` acceptance leaves state at `deployed`.
- [ ] Write GSC inspection fixtures for PASS, neutral, fail, wrong canonical, blocked indexing, failed fetch, quota, and auth errors.
- [ ] Implement `index_verifier.py` with read-only dependency injection.
- [ ] Materialize the exact independent `VerificationReceipt`, bind it to the inspection observation, content object, and artifact revision, and require its ID/hash in the canonical `OutcomeEvent` before requesting `deployed → indexed_verified`.
- [ ] Adapt `articles_indexing_submit.py` and `daily_indexing_sweep.py` to record unique notification outcomes without claiming indexing.
- [ ] Add duplicate-state detection covering the 1,563/1,559 KBLI baseline anomaly.
- [ ] Prove only a valid inspection result requests `deployed → indexed_verified`.
- [ ] Commit with `fix(indexing): distinguish submit acceptance from verified index`.

### Task 4: Collect audience and commercial outcomes

- [ ] Write GSC, GA4, and organic-lead aggregate fixtures for 7/28/60/90-day windows.
- [ ] Add missing-baseline, delayed-data, canonical mismatch, locale, zero-denominator, and unavailable-source cases.
- [ ] Implement `outcome_collector.py` without storing queries containing personal data or individual lead rows.
- [ ] Persist only aggregates and source-health metadata.
- [ ] Suppress general-ledger CRM cohorts below 10 and emit `insufficient_evidence`; retain row-level truth only in protected CRM.
- [ ] Prove a source outage produces missing evidence, not zero performance.
- [ ] Commit with `feat(content-loop): collect bounded content outcomes`.

### Task 5: Integrate post-publish events

- [ ] Add focused poller/webhook tests for approved revision, stale revision, queue retry, Git failure, deployment failure, and idempotent replay.
- [ ] Require the exact operator-confirmed handoff → requested-action spec → materialized publication intent → separate unexpired approval chain before constructing a canonical `ExecutionAttempt`; content approval or queue state alone fails closed.
- [ ] Emit `publish_attempt_started` only from the canonical immutable started execution attempt and append `publish_attempt_failed` plus a separate exact `execution.result` `OperationalReceipt` on failure.
- [ ] Run deployment verification after the existing pipeline reports completion.
- [ ] Preserve the current queue retry and manual gate behavior.
- [ ] Prove an empty queue is reported as idle, not as publication success.
- [ ] Commit with `feat(post-publish): emit publication outcome evidence`.

### Task 6: Replace stale ranking input with live/read-only evidence

- [ ] Add tests proving dynamic GSC priority wins when healthy.
- [ ] Add tests proving unavailable GSC yields explicit `priority_source="unavailable"` and deterministic ordering.
- [ ] Remove the 2026-03-11 dictionary from live prioritization while retaining any fixture history needed for regression tests.
- [ ] Report discovered unique URLs, duplicate state entries, accepted notifications, rejected notifications, pending URLs, and verified-indexed URLs separately.
- [ ] Commit with `fix(indexing): use current evidence for article priority`.

### Task 7: Keep SEO Cell observational

- [ ] Add tests that load outcome snapshots while the thinker still returns `action="none"`.
- [ ] Add a report-only calibration preview requiring at least 30 valid 28/60/90-day outcomes.
- [ ] Never persist learned weights or invoke the actor.
- [ ] Create a repo-canon wrapper that loads database configuration from approved environment/Keychain inputs and contains no credential literal.
- [ ] Update the repo-canon SEO plist to use that wrapper without installing it.
- [ ] Add an observatory emit health field so an emit failure cannot be summarized as fully green.
- [ ] Commit with `fix(seo-cell): close observation gaps without autonomous action`.

### Task 8: Integrate Magazine without activating it

- [ ] Add contract tests mapping a prepared story to the exact Packet 02 canonical content-object/artifact refs and `{risk_class, sensitivity}` classification.
- [ ] Require `human_approved`, matching canonical and artifact hashes, exact publication `ActionIntent`, separate unexpired approval, and canonical started `ExecutionAttempt` in both morning and breaking publish preflight.
- [ ] Make repo-canon wrappers dry-run by default and require `MAGAZINE_PUBLISH_ENABLED=1` for outward mode.
- [ ] Add fixtures proving auth-wall and missing robots/readiness conditions are surfaced.
- [ ] Keep the two Magazine plists repo-canon only; do not install them.
- [ ] Prove red, stale-revision, unapproved, and raw-OSINT payloads fail closed.
- [ ] Commit with `fix(magazine): gate publication on canonical evidence`.

### Task 9: Produce the daily evidence report

- [ ] Write report fixtures for the verified baseline and healthy target state.
- [ ] Implement `report.py` and `run_daily.py` with JSON plus concise Markdown output.
- [ ] Include source-health and missing-evidence sections.
- [ ] Create the daily repo-canon wrapper/plist in disabled, uninstalled form.
- [ ] Ensure the report has no names, raw leads, source text, credentials, or chat identifiers.
- [ ] Commit with `feat(content-loop): report publication and SEO outcomes`.

### Task 10: Integrated shadow verification

- [ ] Replay the full golden set.
- [ ] Validate every decision metric through a preregistered `MetricProfile`, append its exact `MetricResult`, and bind both hashes from each metric-bearing `OutcomeEvent`.
- [ ] Run all focused suites listed below.
- [ ] Run a secret/PII scan over changed files and generated fixtures.
- [ ] Run a forbidden-side-effect spy for HTTP POST, Git push/PR, deployment, Telegram, scheduler, and Magazine publish.
- [ ] Produce an independent-review bundle.
- [ ] Do not deploy, publish, migrate production, or install jobs.

## Golden set and baseline

Use synthetic content and public example URLs. Include these cases:

| Case | Evidence | Expected result |
|---|---|---|
| B1 | seven generated Intel fixtures matching the 2026-08-15 count | seven staged, zero deployed |
| B2 | live poller queue empty | operationally idle; no publication claim |
| B3 | sitemap newest article date 2026-07-25 | freshness warning |
| B4 | backend news newest date 2026-01-13 | API freshness warning |
| D1 | approved blog revision, URL 200, correct canonical/hash, no noindex | deployment verified |
| D2 | Git/CI success but URL still old revision | remains publishing |
| D3 | URL 200 with auth wall | not deployed publicly |
| D4 | correct URL absent from sitemap | deployed, sitemap warning |
| I1 | Indexing API accepts URL_UPDATED | notification accepted; remains deployed |
| I2 | GSC inspection PASS, allowed, successful fetch, correct canonical | indexed verified |
| I3 | GSC quota or auth error | remains deployed; evidence missing |
| I4 | Google canonical differs | remains deployed; canonical mismatch |
| O1 | GSC/GA4 data present, pre-deploy baseline present | valid 28-day outcome/lift |
| O2 | source unavailable | missing evidence, not zero |
| O3 | organic lead aggregate present | count stored; no individual row stored |
| M1 | Magazine packet still building | not deployed |
| M2 | Magazine site returns protected workspace | surface auth-wall warning |
| M3 | breaking item amber and unapproved | no publish attempt |
| M4 | Magazine flag enabled but publication action missing, expired, or mismatched | no publish attempt; flag is insufficient |
| P1 | red item on either surface | no publish attempt |
| P2 | green item with content approval only | remains human-approved; no publish attempt |
| P3 | approved content with exact publication intent but no separate intent approval | no execution attempt |
| P4 | exact handoff/spec/intent/approval chain with mocked executor | one immutable started attempt and one separate typed result receipt; no real outward effect |
| X1 | KBLI state contains 1,563 submissions for 1,559 URLs | duplicate anomaly reported; rate capped at 100% unique |
| C1 | a deployed claim becomes contradicted or source rights are revoked | verification stale; correction or withdrawal ActionItem opens; publication history unchanged |
| C2 | CRM cohort contains fewer than 10 leads | protected CRM remains authoritative; general outcome is suppressed and insufficient evidence |

The baseline report must contain:

- Intel nightly: seven staged, zero automatically public;
- blog newest sitemap article: 2026-07-25;
- backend news newest approved date: 2026-01-13;
- post-publish queue: zero pending at observation time;
- article notification state: 1,815/3,305, 1,490 remaining, 214 historical failure entries;
- KBLI: 1,559 unique target URLs and duplicate-state anomaly;
- SEO Cell: yellow, three green/four yellow sensors, no action, observatory emit failure;
- Magazine: jobs not installed, state building/pending from 2026-07-20, public auth wall, robots 404.

These values are a frozen replay fixture, not a continuously valid production claim.

## Tests and evaluations

Run content-loop tests from the repository root using its virtual environment:

```bash
source .venv/bin/activate
PYTHONPATH=. pytest \
  apps/evaluator/content_loop/tests/test_contracts.py \
  apps/evaluator/content_loop/tests/test_deployment_verifier.py \
  apps/evaluator/content_loop/tests/test_index_verifier.py \
  apps/evaluator/content_loop/tests/test_outcome_collector.py \
  apps/evaluator/content_loop/tests/test_report.py \
  apps/evaluator/content_loop/tests/test_baseline_replay.py -q
```

Run affected existing suites:

```bash
PYTHONPATH=. pytest \
  apps/evaluator/seo_cell/tests/test_gsc_sensor.py \
  apps/evaluator/seo_cell/tests/test_ga4_sensor.py \
  apps/evaluator/seo_cell/tests/test_lead_attribution_sensor.py \
  apps/evaluator/seo_cell/tests/test_thinker_and_actor.py \
  apps/zantara-media/tests/magazine -q
```

Discover and run focused poller/indexing tests:

```bash
rg -l "post_publish_poller|post_publish_webhook|articles_indexing_submit|daily_indexing_sweep" \
  apps/bali-intel-scraper apps/evaluator scripts \
  -g '*test*.py'
```

Run each discovered test file. Add static checks that:

- no changed file contains a credential literal;
- `indexed_verified` appears only behind the GSC inspection verifier;
- Magazine wrappers default to dry-run;
- no test performs an outward POST or Git/deployment mutation;
- SEO thinker still returns no action.

## Shadow and canary plan

### Phase 0: fixture replay

- Run entirely offline.
- Match all frozen baseline facts and golden-set expectations.
- Generate no external side effect.

### Phase 1: read-only shadow

- Duration: at least 14 consecutive days.
- Collect read-only deployment, sitemap, GSC, GA4, and aggregate lead observations.
- Do not transition production records, publish, submit indexing notifications, or install schedulers.
- Compare reported state with manual operator observations daily.
- Report source outages as gaps.

### Phase 2: internal canary preparation

- Requires Packet 02 and Packet 09 independent PASS.
- Run the report-only job manually once on Pro.
- Verify logs are PII-free and every canonical transition proposal is correct.
- Keep all outward feature flags disabled.

### External canary

No external canary is authorized by this packet. A later owner decision must specify:

- one exact green blog item;
- an exact canonical content-object and artifact-revision reference;
- separate explicit receipts for content-revision approval and the exact publication `ActionIntent`;
- exact URL and window;
- rollback owner;
- monitoring duration.

Amber and red never enter an automatic canary. Magazine activation is a separate decision after the site is truly public, robots/readiness pass, and the owner approves the exact edition.

## Metrics and exit criteria

Packet 09 is complete only when:

- 100% of tested publish attempts carry exact Packet 02 content-object and artifact-revision refs.
- 100% of tested outward attempts bind an operator-confirmed handoff, its exact requested-action spec, the materialized publication `ActionIntent`, a separate unexpired exact approval, one immutable started `ExecutionAttempt`, and one exact typed result `OperationalReceipt`.
- 100% of amber/red cases retain the human/remediation gate.
- Zero Git/CI/queue-only outcomes are mislabeled `deployed`.
- Zero Indexing API-only outcomes are mislabeled `indexed_verified`.
- 100% of verified deployment fixtures satisfy host, canonical, noindex, artifact, and auth-wall checks.
- 100% of verified indexing fixtures satisfy GSC verdict, allowed state, successful fetch, and canonical match.
- Submission reporting uses unique URLs and caps rates at 100%.
- GSC priority is current/read-only or explicitly unavailable; no stale hardcoded ranking silently drives the job.
- Missing GSC, GA4, CRM, deployment, or index evidence remains missing rather than zero.
- Outcome snapshots contain aggregates only and no individual lead or PII fields.
- Every metric-bearing `OutcomeEvent` binds the exact preregistered `MetricProfile` and resulting `MetricResult`; unmet sample floors remain `insufficient_evidence`.
- SEO Cell remains report-only with `action=None`.
- Magazine remains dry-run by default and no Magazine LaunchAgent is installed.
- The frozen baseline replay is exact.
- All focused tests and static security checks pass.
- A 14-day read-only shadow completes with zero false-positive deployed/indexed states before any external canary is proposed.
- Independent reviewer returns PASS on publication truth, index truth, privacy, no-side-effect enforcement, and rollback readiness.

Recommended post-activation service-level indicators, to be observed rather than enforced in this packet:

- staged age p50/p95;
- content-approval and publication-action-approval conversion and latency by canonical risk class;
- approved-to-deployed latency and failure rate;
- deployed-to-indexed-verified latency;
- verified-index rate at 7 and 14 days;
- sitemap freshness lag;
- GSC impressions/clicks/CTR/position at 28/60/90 days;
- GA4 sessions/conversions at 28/60/90 days;
- aggregate organic first-touch leads by canonical landing page;
- source-health uptime and missing-baseline rate.

## Rollback

- Before production adoption, delete the feature branch/worktree; no live system changed.
- Migration 274 must be additive and include the mandatory rollback marker.
- After future production adoption, disable `CONTENT_OUTCOME_LOOP_ENABLED` and all outward Magazine flags; preserve append-only outcome history.
- Revert repo-canon plist/wrapper references without touching installed jobs until an operator executes a reviewed runbook.
- If the verifier is wrong, stop transition requests while continuing to store raw aggregate observations; recompute snapshots after the fix.
- Never downgrade `indexed_verified` by editing history. Append a new `VerificationReceipt`, set current verification state to stale, and use the availability axis for correction or withdrawal.
- Magazine rollback leaves the site protected and jobs unloaded.

## Security and privacy

- Query CRM only for aggregate organic-lead counts by canonical landing page and bounded window.
- Never persist names, phone numbers, emails, client IDs, referrer full paths containing identifiers, message content, raw OSINT, or NotebookLM source text.
- Normalize and redact URLs before logging; drop query strings except approved locale/canonical parameters.
- Keep all Google, database, GitHub, hosting, and Telegram credentials in environment/Keychain-backed mechanisms.
- The audit found a credential literal in the current live SEO wrapper. Do not quote or copy it. Prepare a safe repo-canon replacement and hand a separate rotation action to the operator.
- Magazine adapters accept sanitized projections only and fail closed on unclassified payloads.
- Generated reports must be safe for the repository and independent review.

## Independent reviewer handoff

Provide a fresh reviewer with:

1. Packet 02 interface version and test result;
2. exact commit hashes and changed-file list;
3. migration 274 forward/rollback review and proof that no second OutcomeEvent store exists;
4. golden-set and frozen-baseline replay outputs;
5. deployment-proof fixture matrix;
6. index-proof fixture matrix;
7. unique-URL and duplicate-anomaly report;
8. outcome aggregation/privacy schema;
9. evidence that SEO Cell remains no-op;
10. evidence that Magazine remains dry-run and uninstalled;
11. secret/PII scan output;
12. forbidden-side-effect spy output;
13. explicit confirmation that no content, deployment, indexing notification, alert, or scheduler activation occurred.

The reviewer must inspect implementation and rerun focused tests. It must reject the packet if any accepted notification is called indexed, any auth wall is called deployed, any amber/red item bypasses human handling, any individual lead data is persisted, or any outward side effect occurred.
