---
date: 2026-07-05
domain: seo
client_case: none (KBLI acquisition surface)
sources:
  - research/marketing/kbli-gsc-clean-window-2026-07-03.md (PAUSE decision + root cause)
  - agy SERP research 2026-07-05 (long-tail query families)
  - dataset audit this session (status distribution over 1,559 codes)
status: RESURRECTED 2026-07-26 as a DRAFT PR (the original, #1967, was closed by the
  2026-07-13 PII-purge force-push, not by a decision). Merge = Zero's call (Legge 5).
---

# KBLI Batch 3 — title/meta v3 queue (PREPARED, NOT LIVE)

## Lineage

| Batch | Date | Change |
|---|---|---|
| v1 (pre-#1136) | — | `KBLI {code} — {titleEn}: PMA Eligibility, Risk Level & 2026 Requirements` |
| v2 (#1136, Batch "GSC 2026-06-05") | 2026-06-05 | `KBLI {code}: {titleEn} — Indonesia Business Guide 2025` |
| **v3 (Batch 3, this branch)** | prepared 2026-07-05 | data-differentiated per PMA status (below) |

Batch 3 was **PAUSED** by the GSC clean-window investigation (2026-07-03): the impressions
collapse is a crawl-priority gap, not a title-quality problem — rewriting titles cannot fix
an indexing gap and re-processing 1,559 titles mid-recovery would add churn while Google is
re-evaluating the cluster.

## Proposed v3 formulas (all fields from the dataset — zero new regulatory claims)

Title (per PMA status; dataset distribution in parentheses):

| Case | Formula |
|---|---|
| TERBUKA, not Bali-blocked (~968) | `KBLI {code}: {titleEn} — 100% Foreign Ownership, {risk} Risk` |
| TERBUKA, Bali-blocked (520) | `KBLI {code}: {titleEn} — Blocked for PT PMA in Bali (2026)` |
| TERBATAS, capVerified (10) | `KBLI {code}: {titleEn} — Max {maxForeign}% Foreign Ownership` |
| TERBATAS, capSpecial | `KBLI {code}: {titleEn} — Foreign Ownership With Conditions` |
| TERTUTUP (61) | `KBLI {code}: {titleEn} — Closed to Foreign Investment` |

Description v3 (target ≤155 chars, leads with the answer):
`{titleEn} (KBLI {code}): {pmaShort}. {risk} risk, license: {licenseType}. KBLI 2025 rules + Bali notes by Bali Zero.`

Rationale: the low-competition long-tail families are `KBLI [code] foreign ownership` /
`KBLI [code] risk level` / `OSS requirements for KBLI [code]` (agy SERP research 2026-07-05).
v2's fixed suffix answers none of them; v3 puts the queried datum IN the title and
de-templates 1,559 identical suffixes. The Bali-blocked variant is honest (dataset l4_bali),
current, and is the binding answer for our audience.

## Per-page quality checklist (gate for every rendered title/meta)

- [ ] Title ≤60 chars where feasible; datum suffix never truncates the code
- [ ] PMA status in title matches `pma_status` in dataset (no upgrade/downgrade)
- [ ] `maxForeign` shown ONLY when `capVerified` — unverified caps never stated as fact
- [ ] Bali-block qualification present when `l4_bali.blocked` (never an unqualified "100% open")
- [ ] Risk level from `licensing[0].riskCategory`; omit when absent (no invented risk)
- [ ] No prices (PricingTool-only rule), no promises, no year older than current
- [ ] English only; Indonesian terms only as `titleId` verbatim
- [ ] JSON-LD description stays consistent with the new meta description

## GO criteria (recommendation to Zero)

Unpause **after** the crawl fixes (robots/sitemap #1963, full SSG, internal-link
distribution, FAQ parity) have been live ≥2-3 weeks AND GSC shows the gap closing
(sample of long-tail /kbli/* URLs with last-crawl <14 days, impressions recovering).
Then Batch 3 converts recovered impressions into CTR. Sequencing it earlier risks
title-churn during re-evaluation with no indexing benefit.

## Rollout (when GO)

1. Merge this branch (template change in `generateMetadata` — one deploy, all 1,559 pages).
2. Re-submit the 4-5 sample URLs from the investigation via GSC URL Inspection.
3. Measure: GSC /kbli/* CTR + impressions, clean windows, after 2-3 weeks.
4. Rollback = revert PR (template-level, instant).

---

## Addendum 2026-07-26 — resurrection + the verification gate

### Why this doc came back

PR #1967 was **closed on 2026-07-13 at 00:57:29Z as collateral of the PII history-purge
force-push** (its timeline carries `base_ref_force_pushed` at the same second; 20 of the 22
unmerged PRs closed that day share that one second). It was never decided, and unlike the other
18 it never got a successor. Resurrected as a draft on Zero's ruling, 2026-07-26. Full evidence:
`research/operations/2026-07-26-verdetto-seo-1967-e-ledger-stale.md` §A1.

### What changed since 2026-07-05, and why it forced a gate

Two things moved under this branch while it sat closed:

1. **The metadata surface was already rewritten once.** `NEXT_PUBLIC_KBLI_META_EN=1` went live on
   2026-07-13, switching `<title>` from the curated-legacy EN map to the full 1,559-title map.
   v3 now stacks on top of that, which is why the GO window starts **≥ 2026-07-27** (two weeks
   after the flip), not at the "~2026-07-26" crawl-recovery date.

2. **The fields v3 puts in the title went under cure.** `baliL4.blocked`, `licensing[].riskCategory`
   and `licenseType` come from payloads the GARUDA-FILIERA work has been re-grounding since — W100
   quarantined 13/13 in Lot 1 on `payload_cross_contamination` / `unresolvable_source_pointer`.

The original v3 gated only `pma.capVerified`. The other three fields were ungated and would have
been indexed as bare regulatory assertions on 1,559 pages.

### The gate (implemented, measured)

The repo already declares the discipline: `isLicensingVerificationPending()` exists so that
*"every surface that states risk/license/processing as fact must qualify the claim — FAQ, JSON-LD,
key-fact grids all key on this single helper so they can't drift apart."* The page body obeys it
(`page.tsx:345`) and qualifies the Bali verdict too (`confidence` + `needsReview` on
`BaliStatusBadge`). A `<title>` cannot carry a qualifier, so it gets the **positive** complement:

| helper (`kbli-provenance.ts`) | states the fact only when |
|---|---|
| `isLicensingVerifiedForBareClaim` | `provenance.licensing.status === "oss_native"` **and** rows are served |
| `isBaliL4BlockVerifiedForBareClaim` | `blocked` **and** `confidence === "HIGH"` **and** not `needsReview` |
| (pre-existing) `pma.capVerified` | unchanged |

Both fail **closed**: a record with a missing or unreadable provenance block yields `false`. A
negative gate (`!pending`) would have promoted exactly those records to "verified".

Measured on the 1,559-code canonical (`kbli-meta.test.ts` pins these):

| fact | pages that would state it | verified | **withheld** |
|---|---|---|---|
| `{risk} Risk` + `license: {type}` | 1,342 | 1,336 | **6** |
| `Blocked for PT PMA in Bali (2026)` | 455 | 33 | **422** |

Composition lives in `apps/mouth/src/lib/kbli-meta.ts` — pure and unit-tested, not inline in a
server component. Guilt **and** innocence corpus in `kbli-meta.test.ts`; both gates were verified
non-vacuous by neutralizing them (negative-gating → 3 red; drop the Bali confidence check → 4 red).

### Revised checklist row

- [x] `maxForeign` shown ONLY when `capVerified`
- [x] **risk + licenseType shown ONLY when the licensing provenance is OSS-native**
- [x] **Bali-block stated ONLY at HIGH confidence without a review flag** — otherwise the title
      states the (verified) national PMA fact and the body carries the Bali caveat

### GO criteria (superseding the section above)

1. From 2026-07-27, GSC: long-tail `/kbli/*` last-crawl <14d and impressions stable after the
   2026-07-13 META_EN flip.
2. This gate merged (done in this PR).
3. Post-merge spot-check on a **Lot-1 quarantined code**, not only `/kbli/56101`.
