# Visa Oracle V2 operational gates — execution record

Date: 2026-08-06

Candidate base: `b758920d3896cf4c68dcf072c22a09b6d03ada20`

Activation verdict: **NO-GO**

This record converts the remaining production-readiness bullets into concrete,
fail-closed operating decisions. It does not authorize a production database
write, pack activation, merge, push, deploy, or client-facing send.

## Actions and decisions

| Gate                      | Decision / action                                                                                                                                                                                                                                                                                                                                                                                                                  | Current result                                                                                                                                                                                                                                                                                                                      | Activation condition                                                                                                                                                                                                                                                                 |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Official source archive   | Content-address every relied-on artifact, record acquisition provenance and operative locators, upload it to the Visa Oracle Drive folder, then read back Drive metadata. Never infer an instrument from its filename.                                                                                                                                                                                                             | **DONE for Calling Visa treatment.** Permenkumham 2/2024 is byte-verified; the official Cameroon and Guinea Immigration announcements are captured with hashes and archived. The recovered 2023 `Indeks Visa` decision remains correctly classified as related evidence.                                                            | Re-observe dynamic official pages under the signed source policy. The two ministerial PDFs remain desirable corroboration if later located, but Zero explicitly approved the official Immigration announcements as sufficient primary evidence and they are not activation blockers. |
| Source freshness          | Keep the signed candidate policy: official portal observations have a seven-day max age and daily recheck; primary laws and ministerial decisions have a 365-day max age and monthly recheck. Country/product conflicts are scoped to the affected nationality/product; source-integrity and global-provenance failures block the complete evaluation.                                                                             | **POLICY DONE / OPERATIONS OPEN.**                                                                                                                                                                                                                                                                                                  | Assign the production scheduler identity, on-call owner and alerts before activation. No last-known-good fallback after expiry.                                                                                                                                                      |
| PricingTool catalogue     | Finance is accountable owner; Zero is approver; Backend is technical custodian. Use an exact PricingTool key only; recompute the full catalogue and row SHA-256 and fail closed on a missing, ambiguous or unparsable row. `metadata.last_updated` is provenance, not an invented expiry clock. The approved snapshot remains current until superseded or explicitly withdrawn.                                                    | **CATALOGUE APPROVED / ADAPTER DONE / PRODUCT MAP PARTIAL.** Version `2026.1`, effective `2026-01-01`, last updated `2026-05-06`, SHA-256 `97e377d769df7f2dd060cba1896c13362a7419001dcc526c60d2522147c0c2a8`. Exact scalar IDR rows now become sealed and persisted `PriceQuote`s. Public cards use the generated 106-row snapshot. | Extend the next signed RulePack's pricing identities only where the service variant is exact. Sequence 2 maps 13 products; onshore/offshore variants must not be guessed. Never use the removed card fallback, fuzzy matching or a manually copied amount.                           |
| Retention and privacy     | Minimize by purpose: no raw interview payloads in telemetry; decision/idempotency retention must be policy-bound; CRM/WhatsApp handoff uses explicit consent and minimum fields. Use contract/pre-contractual steps for the user-requested evaluation, explicit consent for handoff, and legitimate interest only for PII-free security telemetry. Legal hold suspends deletion only for identified records and must be auditable. | **POLICY FRAME DECIDED / DURATION OPEN.** Migration 264 correctly seeds no duration.                                                                                                                                                                                                                                                | Zero/privacy counsel records the exact decision TTL, idempotency TTL, historical-row disposition, child/specific-data controls, notice version, DSR SLA and legal-hold release procedure. No runtime default may fill a missing value.                                               |
| Roles, keys and scheduler | Provision in staging first: separate `visa_ledger_owner`, runtime, `visa_activation_executor`, policy writer and bounded retention worker. Revoke direct runtime writes after ownership transfer. Store HMAC keys outside Git, with distinct request/response/decision domains, active key IDs and an overlap window longer than the maximum retained artifact.                                                                    | **NOT PROVISIONED HERE.** This branch performs no production mutation.                                                                                                                                                                                                                                                              | Superuser applies the reviewed role plan; the read-only privilege probe and existing activation-writer tests pass; scheduler backlog/max-lag alerts and HMAC retirement runbook are armed.                                                                                           |
| Smoke before activation   | Run the existing disposable full-stack smoke first, then a production-environment preflight that is read-only. Only after all gates are green may Zero authorize one inactive insert and a controlled activation.                                                                                                                                                                                                                  | **DISPOSABLE SMOKE PASS / PRODUCTION SMOKE NOT RUN.**                                                                                                                                                                                                                                                                               | Run production preflight with no writes; independently compare active pack/hash, policy, roles, keys, source age, PricingTool snapshot and retention backlog. Activation remains a separate explicit command.                                                                        |

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

| Gate                       | Before                 | After                                                                                                                            |
| -------------------------- | ---------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| G0 inventory               | PASS                   | PASS                                                                                                                             |
| G1 contracts and sources   | BLOCKED                | PASS; official announcement evidence approved, hashed and archived; optional Kepmen PDFs remain a non-blocking corroboration gap |
| G2 engine harness          | PASS                   | PASS (unchanged)                                                                                                                 |
| G3 UI states/categories    | PASS                   | PASS (unchanged)                                                                                                                 |
| G4 public engine authority | PASS                   | PASS (unchanged)                                                                                                                 |
| G5 automated suites        | PASS                   | PASS; backend Visa Engine/router suite, 416 pertinent Vitest tests, Mouth typecheck and desktop/320 px Playwright are green      |
| G6 independent review      | PASS on base candidate | Re-review pending after remediation of the public-pricing fallback and 320 px overlap findings                                   |

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
- Playwright screenshots:
  [desktop](screenshots/visa-oracle-v2/book-pricing-chromium.png) and
  [320 px mobile](screenshots/visa-oracle-v2/book-pricing-mobile-chrome.png).

Verification on 2026-08-06:

- Backend Visa Engine/router suite: green, with one expected provisioning skip
  because `visa_activation_executor` does not yet exist.
- Mouth typecheck: green.
- Pertinent Vitest: 40 files, 416 tests green, including full parity across all
  106 generated PricingTool rows and the public Visa service catalogue.
- Playwright: Chromium desktop and Mobile Chrome at 320 px, 4/4 green across
  `/book/services` and `/services/visa`; no horizontal overflow, overlap,
  fabricated fallback price or separated fee.
