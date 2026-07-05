---
date: 2026-07-05
domain: seo
client_case: none (KBLI acquisition surface)
sources:
  - research/marketing/kbli-gsc-clean-window-2026-07-03.md (PAUSE decision + root cause)
  - agy SERP research 2026-07-05 (long-tail query families)
  - dataset audit this session (status distribution over 1,559 codes)
status: READY-TO-GO — PAUSED. Unpause = Zero's decision (Legge 5).
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
