# Visa Oracle V2 operational gates — execution record

Date: 2026-08-07

Candidate implementation: `8fb5c1290` (rebased on synchronized `main`
`cd343655c`)

Activation verdict: **NO-GO**

This record converts the remaining production-readiness bullets into concrete,
fail-closed operating decisions. It does not authorize a production database
write, pack activation, merge, push, deploy, or client-facing send.

## Actions and decisions

| Gate                      | Decision / action                                                                                                                                                                                                                                                                                                                                                                        | Current result                                                                                                                                                                                                                                                                                                                                                                                                              | Activation condition                                                                                                                                                                                                                                                                 |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Official source archive   | Content-address every relied-on artifact, record acquisition provenance and operative locators, upload it to the Visa Oracle Drive folder, then read back Drive metadata. Never infer an instrument from its filename.                                                                                                                                                                   | **DONE for Calling Visa treatment.** Permenkumham 2/2024 is byte-verified; the official Cameroon and Guinea Immigration announcements are captured with hashes and archived. The recovered 2023 `Indeks Visa` decision remains correctly classified as related evidence.                                                                                                                                                    | Re-observe dynamic official pages under the signed source policy. The two ministerial PDFs remain desirable corroboration if later located, but Zero explicitly approved the official Immigration announcements as sufficient primary evidence and they are not activation blockers. |
| Source freshness          | Keep the signed candidate policy: official portal observations have a seven-day max age and daily recheck; primary laws and ministerial decisions have a 365-day max age and monthly recheck. Country/product conflicts are scoped to the affected nationality/product; source-integrity and global-provenance failures block the complete evaluation.                                   | **POLICY DONE / OPERATIONS OPEN.**                                                                                                                                                                                                                                                                                                                                                                                          | Assign the production scheduler identity, on-call owner and alerts before activation. No last-known-good fallback after expiry.                                                                                                                                                      |
| PricingTool catalogue     | Finance is accountable owner; Zero is approver; Backend is technical custodian. Use an exact PricingTool key only; recompute the full catalogue and row SHA-256 and fail closed on a missing, ambiguous or unparsable row. `metadata.last_updated` is provenance, not an invented expiry clock. The approved snapshot remains current until superseded or explicitly withdrawn.          | **CATALOGUE APPROVED / ADAPTER DONE / PRODUCT MAP PARTIAL.** Version `2026.1`, effective `2026-01-01`, last updated `2026-05-06`, SHA-256 `97e377d769df7f2dd060cba1896c13362a7419001dcc526c60d2522147c0c2a8`. Exact scalar IDR rows now become sealed and persisted `PriceQuote`s. Public cards use the generated 106-row snapshot.                                                                                         | Extend the next signed RulePack's pricing identities only where the service variant is exact. Sequence 2 maps 13 products; onshore/offshore variants must not be guessed. Never use the removed card fallback, fuzzy matching or a manually copied amount.                           |
| Retention and privacy     | Minimize by purpose: no raw interview payloads in telemetry; decision/idempotency retention must be policy-bound; CRM/WhatsApp handoff uses explicit consent and minimum fields. Use pre-contractual steps at the user's request for evaluation and separate explicit consent for each optional handoff. Legal hold suspends deletion only for identified records and must be auditable. | **POLICY V1 APPROVED / REPOSITORY CONTROLS DONE.** Zero approved 30-day decisions, 24-hour idempotency, PII-free 90-day telemetry, DSR within 72 hours, separate CRM/WhatsApp consent, minor protection and DPIA before ENFORCE. Machine-readable authority, bilingual notice, bounded purge/DSR/hold primitives, dry-run scheduler manifest and 30/60-minute missed-run sensor are present.                                | Apply migrations 264–267, register the exact policy at the real change window, install/observe the retention job, configure the 90-day analytics deletion, complete processor/region inventory and obtain DPIA approval. No runtime default may fill a missing policy value.         |
| Roles, keys and scheduler | Provision in staging first: separate `visa_ledger_owner`, runtime, `visa_activation_executor`, policy writer, privacy operator and bounded retention worker. Revoke direct runtime writes after ownership transfer. Store HMAC keys outside Git, with distinct request/response/decision domains, active key IDs and an overlap window longer than the maximum retained artifact.        | **CODED / PRODUCTION MIS-ARM CONFIRMED.** Atomic complete-set replacement now closes the legal-period correction gap; the preflight checks both activation functions and every PG15/PG17 table privilege. Read-only production inspection still shows the old mis-arm: executor table access, runtime activation writes, runtime-owned mutation functions and no `visa_ledger_owner`. No production mutation was performed. | Infra applies migration 267 and the separated capability model, then the read-only `operational_preflight` must exit 0. Arm the 15-minute worker and prove its alerts. Product ENFORCE also requires a reproduced 90-day analytics TTL export/probe.                                 |
| Smoke before activation   | Run the existing disposable full-stack smoke first, then a production-environment preflight that is read-only. Only after all gates are green may Zero authorize one inactive insert and a controlled activation.                                                                                                                                                                        | **DISPOSABLE SMOKE PASS / PRODUCTION SMOKE NOT RUN.**                                                                                                                                                                                                                                                                                                                                                                       | Run production preflight with no writes; independently compare active pack/hash, policy, roles, keys, source age, PricingTool snapshot and retention backlog. Activation remains a separate explicit command.                                                                        |

## Immutable archive result

The complete machine-readable record is in
`docs/audits/evidence/visa-oracle-v2/2026-08-06-source-archive-manifest.json`.
The current manifest SHA-256 is
`ce5ac3d6dc9a530ea2099710967ec72673a525f292e02abe8c62c78e1e6a421a`;
its immutable Drive read-back is file `1Wf6EGsuKUl5svwMqmB6Rq4FB2bdAqvOj`,
7,752 bytes, created and last modified at `2026-08-06T09:35:51.899Z`.

- Drive folder: `visa-oracle/official-sources/calling-visa-related-legislation`
- Kepmen M.HH-03.GR.01.06/2023 (`Indeks Visa`): SHA-256
  `65e452cab706ca03aab496ee1ea7cbcf591df63f8d16c70095d0a4369cc03210`,
  367,013 bytes, 9 pages. Related evidence only.
- Permenkumham 2/2024: SHA-256
  `7c90dc281b1d625748f8719e90a0d954b7ca07eda113da99e32e5c0bb801905e`,
  137,150 bytes, 8 pages. The M5 file is byte-identical to the official
  `peraturan.go.id` download.
- Official Cameroon/Guinea announcement record: SHA-256
  `02ee0ef8291d8500c1c17d488219a5c8ce797b1aa0696b68b50e60578c2d1239`,
  3,533 bytes; Drive file `1wAuF5L14gg-yKzaEzqaqD5-v0IlkPHZz`. The raw
  Guinea and Cameroon HTML captures are also archived as Drive files
  `1jli20E-kEw47vUsRPK9y_JB-pkdLn_5m` and
  `1yUos6FMJMX1wj3T4YnvniJ1eEYCy5mbB` with byte-size read-back.

## Calling Visa source closure

Zero approved the two official Immigration announcements as sufficient primary
evidence. The Cameroon publication identifies Kepmenkumham
`M.HH-05.GR.01.06 Tahun 2023` and its 2023-11-23 approval; the Guinea
publication identifies Kepmenkumham `M.HH-03.GR.01.06 Tahun 2024`, its
2024-06-12 effective date, the fifth-amendment lineage and the resulting six
countries. Their normalized evidence record is content-addressed and archived
in Drive. The ministerial PDFs are optional corroboration, not G1 blockers.

## Gate state after this execution

| Gate                       | Before                  | After                                                                                                                                                                                                                                                                                                           |
| -------------------------- | ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| G0 inventory               | PASS                    | PASS                                                                                                                                                                                                                                                                                                            |
| G1 contracts and sources   | BLOCKED                 | PASS; official announcement evidence approved, hashed and archived; optional Kepmen PDFs remain a non-blocking corroboration gap                                                                                                                                                                                |
| G2 engine harness          | PASS                    | PASS (unchanged)                                                                                                                                                                                                                                                                                                |
| G3 UI states/categories    | PASS                    | PASS (unchanged)                                                                                                                                                                                                                                                                                                |
| G4 public engine authority | PASS                    | PASS (unchanged)                                                                                                                                                                                                                                                                                                |
| G5 automated suites        | PASS                    | PASS on the rebased operational candidate: 1,667 backend Visa Engine/router tests passed with one expected provisioning skip; 3,178 Mouth Vitest tests, typecheck, 15/15 desktop/320 px Playwright, 16 retention-operation tests, four Cell sensor tests and the unmocked disposable full-stack smoke are green |
| G6 independent review      | PASS on prior candidate | **RE-GRADE REQUIRED.** `6558afaa1` closed with 0 BLOCKER and 0 MEDIUM; the rebased migration-267/retention delta must receive an independent exact-SHA review before this record may claim final G6 closure                                                                                                     |

## Privacy Policy V1 implementation evidence

- The approved authority is versioned in
  `docs/policies/visa-oracle-privacy-policy-v1.json`; its human-readable record
  explicitly does not authorize ENFORCE.
- Migration 264 remains unseeded and fail-closed. The registration command
  imports the checked-in durations and refuses serving-runtime or superuser
  sessions.
- The one-shot external retention worker validates the complete active policy,
  deletes only through bounded database functions and reports aggregate
  backlog/lag evidence. Migration 266 exposes no applicant or decision ID.
- DSR erasure atomically removes the decision, encrypted payload and matching
  replay record, refuses an active hold and records only aggregate evidence.
- A legal hold requires an opaque case reference and reason code, a separate
  approver, and a review deadline within the approved 30-day interval. Release
  is a separate audited transition.
- The public EN/ID notice states the exact retention and consent boundary.
  Minor handoff requires guardian confirmation before the separate WhatsApp
  opt-in. A deterministic backend privacy adapter also turns every known-minor
  result into `HUMAN_REVIEW_REQUIRED` before persistence because the public
  evaluation contract carries no guardian-proof fact; unknown age cannot
  preserve supported candidates. This is a product/privacy abstention, not a
  claim of visa ineligibility. Visa Oracle events use a PII-free analytics path
  with no generic browser session/user identifier.
- Playwright screenshots:
  [privacy desktop](screenshots/visa-oracle-v2/visa-oracle-privacy-v1-desktop.png)
  and
  [privacy 320 px](screenshots/visa-oracle-v2/visa-oracle-privacy-v1-mobile-320.png).
- Independent G6 review on `6558afaa1` proved that unexpected function grants,
  direct DML grants, runtime capability membership and combined pack-write /
  activation authority all fail the production preflight. Its final verdict
  was 0 BLOCKER and 0 MEDIUM.

## Pricing and UI correction evidence

- The arbitrary 30-day catalogue expiry was removed. Zero confirmed the
  PricingTool catalogue as current until superseded or withdrawn.
- `PricingResolution` now parses only one exact IDR amount. Ranges, contact
  text, non-IDR values, missing version/provenance and malformed rows abstain.
- An available resolution becomes a deterministic `PriceQuote` before HMAC
  sealing and persistence; legal candidate selection remains unchanged when
  pricing fails.
- The frontend generated snapshot now contains 106 exact catalogue rows. The
  nonexistent `C317 Single Entry` card and copied price fallback were removed.
- The public `/services/visa` catalogue is generated from all exact rows in the
  six approved PricingTool categories. Its cards and JSON-LD omit prices when
  an exact category/key lookup fails; static package text is never a fallback.
  Monetary add-ons embedded in notes are excluded, so the UI exposes one
  all-inclusive amount per row.
- Book cards now display `C1 Tourism`, `C2 Business`, `D1 Tourism (1 Year)`,
  `E33G Remote Worker (Offshore)` and `Retirement (Offshore)` using exact
  category/key identities. E33 Second Home uses the same generated source.
- On 320 px screens, locale and chapter navigation remain in document flow and
  do not overlap service cards. Keyboard tab activation, reduced-motion mode
  and horizontal-overflow assertions are part of the browser gate.
- The public `More Details` surface is a named modal dialog. It transfers and
  traps focus, exposes an accessible close control, closes on `Escape` and
  restores focus to the trigger; unit and real-browser tests cover the full
  keyboard path.
- Playwright screenshots:
  [desktop](screenshots/visa-oracle-v2/book-pricing-chromium.png) and
  [320 px mobile](screenshots/visa-oracle-v2/book-pricing-mobile-chrome.png).

## Activation correction and retention operations evidence

- Migration 267 adds `visa_replace_activation_set(uuid[], text, text)`: one
  advisory lock, one database clock, exact multirange coverage, non-overlapping
  signed segments, monotone sequence/hash continuity and transaction rollback
  on any failure. Exact replay is read-only; actor/reason drift fails closed.
- A correction cannot truncate or synthesize an existing pack. The ceremony
  requires newly signed carry-forward/correction bundles, at most 64 segments,
  each no larger than 2 MiB, parsed with duplicate-key and non-finite-number
  rejection and verified through Ed25519/JCS before insertion.
- `visa_activation_executor` receives only both activation functions; the pack
  writer cannot execute either. The read-only preflight now asserts an exact
  function and table-privilege matrix, including PostgreSQL 17 `MAINTAIN` while
  retaining PostgreSQL 15 CI compatibility.
- The independent re-grade found that the single-pack ceremony originally
  compared `current_user`, allowing one login with two `SET ROLE` identities to
  appear separated. It now compares `session_user`, rejects a superuser login
  even after role switching, and has a dedicated adversarial regression test.
- The retention worker's actual direct read of the approved, non-PII policy row
  is now represented in both its boundary check and the preflight allowlist.
  Every other table privilege for that executor remains forbidden.
- The scheduler example is one-shot, dry-run and uninstalled. It reuses the
  existing lock/timeout/heartbeat/P0 alert infrastructure, performs no immediate
  retries that could hide backlog exit `2`, and Cell observes warning/critical
  missed runs at 30/60 minutes.
- Analytics remains deliberately disabled/fail-closed until the real destination
  owner supplies a fresh, closed-schema 90-day TTL attestation and the grader
  independently reproduces its read-only export plus prior-presence/expiry/control
  synthetic probe. The purge is independent and may not be delayed by this gap.

Verification on 2026-08-07 after rebase onto synchronized `main`:

- Backend Visa Engine/router suite: 1,668 collected, 1,667 passed and one
  expected provisioning skip because the operator role is not fully
  provisioned.
- Mouth typecheck: green.
- Visa-focused Mouth Vitest: 31 files, 319 tests green.
- Full Mouth Vitest: 346 files, 3,178 tests green, including the Visa Oracle
  privacy, telemetry, guardian-consent and prior pricing coverage.
- Retention operations: 16 tests green; Cell missed-run sensor: four tests
  green; LaunchAgent plist and shell wrapper syntax checks green.
- Playwright Visa Oracle V2: 15/15 Chromium tests green across typed engine
  states, network failures, keyboard EN/ID, reduced motion, consent, WCAG and
  320 px policy layout.
- Unmocked full-stack smoke: 1/1 green through browser → Next → FastAPI → signed
  TEST RulePack → PostgreSQL; the complete Visa Engine chain through migration
  267 was applied and the disposable `visa_oracle_smoke_*` database was dropped
  in `finally`.
