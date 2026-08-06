# Visa Oracle V2 operational gates — execution record

Date: 2026-08-06

Candidate base: `b758920d3896cf4c68dcf072c22a09b6d03ada20`

Activation verdict: **NO-GO**

This record converts the remaining production-readiness bullets into concrete,
fail-closed operating decisions. It does not authorize a production database
write, pack activation, merge, push, deploy, or client-facing send.

## Actions and decisions

| Gate                        | Decision / action                                                                                                                                                                                                                                                                                                                                                                                                                  | Current result                                                                                                                                             | Activation condition                                                                                                                                                                                                                   |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Official instrument archive | Content-address every PDF, record acquisition provenance, verify text and rendered pages, upload to the Visa Oracle Drive folder, then read back Drive metadata. Never infer an instrument from its filename.                                                                                                                                                                                                                      | **PARTIAL.** Permenkumham 2/2024 and Kepmen M.HH-03.GR.01.06/2023 are archived. The latter is an `Indeks Visa` decision, not a Calling Visa list decision. | Acquire the official PDFs for M.HH-05.GR.01.06/2023 and M.HH-03.GR.01.06/2024 from an official origin; verify operative text, annexes, dates and supersession lineage.                                                                 |
| Source freshness            | Keep the signed candidate policy: official portal observations have a seven-day max age and daily recheck; primary laws and ministerial decisions have a 365-day max age and monthly recheck. Country/product conflicts are scoped to the affected nationality/product; source-integrity and global-provenance failures block the complete evaluation.                                                                             | **POLICY DONE / OPERATIONS OPEN.**                                                                                                                         | Assign the production scheduler identity, on-call owner and alerts before activation. No last-known-good fallback after expiry.                                                                                                        |
| PricingTool catalogue       | Finance is accountable owner; Zero is approver; Backend is technical custodian. Use an exact PricingTool key only. Catalogue max age is 30 calendar days from `metadata.last_updated`; recompute the full catalogue and row SHA-256 on every evaluation; check the file daily; invalidate immediately on any catalogue mutation.                                                                                                   | **POLICY DECIDED / CATALOGUE STALE.** The checked catalogue says `last_updated=2026-05-06`, so it cannot emit `AVAILABLE` pricing on 2026-08-06.           | Finance reviews the complete catalogue and publishes a new dated snapshot. Zero records the snapshot hash and approval reference. Until then, omit the amount and return `CONTACT_REQUIRED`/`UNKNOWN`; never reuse the stale amount.   |
| Retention and privacy       | Minimize by purpose: no raw interview payloads in telemetry; decision/idempotency retention must be policy-bound; CRM/WhatsApp handoff uses explicit consent and minimum fields. Use contract/pre-contractual steps for the user-requested evaluation, explicit consent for handoff, and legitimate interest only for PII-free security telemetry. Legal hold suspends deletion only for identified records and must be auditable. | **POLICY FRAME DECIDED / DURATION OPEN.** Migration 264 correctly seeds no duration.                                                                       | Zero/privacy counsel records the exact decision TTL, idempotency TTL, historical-row disposition, child/specific-data controls, notice version, DSR SLA and legal-hold release procedure. No runtime default may fill a missing value. |
| Roles, keys and scheduler   | Provision in staging first: separate `visa_ledger_owner`, runtime, `visa_activation_executor`, policy writer and bounded retention worker. Revoke direct runtime writes after ownership transfer. Store HMAC keys outside Git, with distinct request/response/decision domains, active key IDs and an overlap window longer than the maximum retained artifact.                                                                    | **NOT PROVISIONED HERE.** This branch performs no production mutation.                                                                                     | Superuser applies the reviewed role plan; the read-only privilege probe and existing activation-writer tests pass; scheduler backlog/max-lag alerts and HMAC retirement runbook are armed.                                             |
| Smoke before activation     | Run the existing disposable full-stack smoke first, then a production-environment preflight that is read-only. Only after all gates are green may Zero authorize one inactive insert and a controlled activation.                                                                                                                                                                                                                  | **DISPOSABLE SMOKE PASS / PRODUCTION SMOKE NOT RUN.**                                                                                                      | Run production preflight with no writes; independently compare active pack/hash, policy, roles, keys, source age, PricingTool snapshot and retention backlog. Activation remains a separate explicit command.                          |

## Immutable archive result

The complete machine-readable record is in
`docs/audits/evidence/visa-oracle-v2/2026-08-06-source-archive-manifest.json`.
The manifest SHA-256 is
`5bbc6149319dbe86d1341108c3d8b1dcebd626d8f48496380886d309bcab9a8a`;
its Drive read-back is file `1Y3xHQttA68ZodE_ahIQchd9ltwCPL5g3`, 5,238 bytes,
created and last modified at `2026-08-06T08:21:53.300Z`.

- Drive folder: `visa-oracle/official-sources/calling-visa-related-legislation`
- Kepmen M.HH-03.GR.01.06/2023 (`Indeks Visa`): SHA-256
  `65e452cab706ca03aab496ee1ea7cbcf591df63f8d16c70095d0a4369cc03210`,
  367,013 bytes, 9 pages. Related evidence only.
- Permenkumham 2/2024: SHA-256
  `7c90dc281b1d625748f8719e90a0d954b7ca07eda113da99e32e5c0bb801905e`,
  137,150 bytes, 8 pages. The M5 file is byte-identical to the official
  `peraturan.go.id` download.

## Remaining source blocker

The two dispositive Calling Visa artifacts are still absent:

1. Kepmenkumham `M.HH-05.GR.01.06 Tahun 2023` — Cameroon removal.
2. Kepmenkumham `M.HH-03.GR.01.06 Tahun 2024` — fifth amendment / Guinea.

The national Ditjen list remains canonical and the signed sequence-2 country
treatment remains the approved forward candidate, but these missing immutable
artifacts keep G1 and production activation blocked. The recovered 2023 Visa
Index decision must never be substituted for either missing act.

## Gate state after this execution

| Gate                       | Before                 | After                                                                                    |
| -------------------------- | ---------------------- | ---------------------------------------------------------------------------------------- |
| G0 inventory               | PASS                   | PASS                                                                                     |
| G1 contracts and sources   | BLOCKED                | BLOCKED; two related sources archived and classified, two dispositive PDFs still missing |
| G2 engine harness          | PASS                   | PASS (unchanged)                                                                         |
| G3 UI states/categories    | PASS                   | PASS (unchanged)                                                                         |
| G4 public engine authority | PASS                   | PASS (unchanged)                                                                         |
| G5 automated suites        | PASS                   | Requires rerun after this docs-only operational record                                   |
| G6 independent review      | PASS on base candidate | New branch requires independent docs/source-manifest review                              |
