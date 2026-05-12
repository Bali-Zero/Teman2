# spec-tax.md — Tax content cluster mapping & 12 money pages

**Owner**: Antonello + Subhi
**Created**: 2026-05-11
**Source of truth**: this file. Notion / Google Docs intermediate workspaces allowed for brainstorming, final deliverables land here.
**Status**: §1-§5 ready for Day 2 (Minggu 3 — 14-20 Mei).

---

## §1 — Purpose

Define the tax content strategy for `balizero.com`:

1. **Topic cluster map** (pillar + spoke) tied to existing 42 base slug in `apps/mouth/src/content/articles/tax/` + 16 cross-category tax articles (in `business/`, `property/`, `digital-nomad/`, `immigration/`, `tax-legal/`).
2. **12 money pages** to prioritize during Subhi D2 (Minggu 3): on-page SEO + WhatsApp CTA + ArticleClusterCTA + ArticleToolEmbed where applicable.
3. **URL canonicalization decisions** to resolve cannibalization between `/tax/`, `/tax-legal/`, `/taxes/`, `/services/tax`, `/insights/lifestyle/`, `/visas/`.

---

## §2 — Inventory baseline (2026-05-11)

### 2.1 Articles by category

| Category folder           | Base slug count | Notes                                                                              |
| ------------------------- | --------------- | ---------------------------------------------------------------------------------- |
| `articles/tax/`           | 42              | Canonical home of tax content per category-folder convention                       |
| `articles/tax-legal/`     | ~50             | Press-release + analytical articles (overlap with `tax/`) — see §6 deduplication   |
| `articles/property/`      | 5 tax-related   | rental-income-tax, property-tax-guide, bphtb-\*, capital-gains, selling-property   |
| `articles/business/`      | 4 tax-related   | kbli-tax-implications, kbli-legal-accounting, pt-pma-compliance, 183-day-residency |
| `articles/digital-nomad/` | 2               | remote-work-tax, freelancing-legally                                               |
| `articles/immigration/`   | 8 tax-touched   | indonesia-tax-for-expats-2026, zero-tax-countries, npwp-wives-coretax, etc.        |

### 2.2 Search Console snapshot (90gg, 2026-02-10 → 2026-05-09)

- **Total tax-related queries indexed**: 95 (after regex filter `tax|pajak|pph|ppn|spt|npwp|coretax|fiskal|withholding|deemed|ortax|djp`)
- **Total clicks on tax queries**: 0 (zero!)
- **Total impressions on tax queries**: ~660
- **Top page by tax impressions**: `/tax-legal/tax-incentives-indonesia` (106 imp, position 39.75)
- **Best-positioned page (high intent, low impression)**: `/tax-legal/tax-deadlines-2026` (position 4.9, 10 imp)

**Read**: SEO equity already exists (pages ranking position 4-12 on high-intent queries) but **title/description debole** → 0 click. Money page work in §4 must fix title + meta + add WhatsApp CTA + internal linking.

---

## §3 — Cluster mapping (pillar + spoke)

Six topic clusters identified from GSC query intent + existing slug inventory. Each cluster has 1 **pillar** (broad, evergreen, deserves position-1) and 4-8 **spokes** (long-tail, specific, deserve position-1-3 each).

### Cluster 1 — Tax Residency & 183-day rule

- **Pillar**: `tax-residency-indonesia` (slug: `articles/tax/tax-residency-indonesia.mdx`)
- **Target queries**: `tax residency indonesia` (41 imp), `indonesia tax residency 183 days official 2026` (6 imp), `tax in indonesia for foreigners` (29 imp), `indonesia tax residency rules 2026` (4 imp), `does indonesia tax foreign income` (1 imp)
- **Spokes**:
  - `articles/business/indonesias-183-day-tax-residency-rule-what-expats-get-wrong-in-2026.mdx` (existing, position 13.25)
  - `articles/tax/indonesia-zero-tax-foreign-income-2026.mdx` (existing)
  - `articles/tax/indonesia-tax-guide-for-foreigners.mdx` (existing)
  - `articles/tax/tax-planning-expats.mdx` (existing)
  - `articles/tax/tax-deductions-expats-indonesia.mdx` (existing)

### Cluster 2 — NPWP & Coretax onboarding

- **Pillar**: `npwp-foreigners-guide` (slug: `articles/tax/npwp-foreigners-guide.mdx`)
- **Target queries**: `npwp` (5 imp, position 3.8), `individual npwp registration` (16 imp), `company npwp registration` (3 imp), `npwp aali` (1 imp, position 4 — likely brand misspell)
- **Spokes**:
  - `articles/tax/coretax-npwp16-vs-npwp15-foreigners.mdx` (existing)
  - `articles/tax/coretax-npwp-problems-2026.mdx` (existing)
  - `articles/tax/coretax-login-errors-fixes-2026.mdx` (existing)
  - `articles/tax/coretax-efiling-spt-guide.mdx` (existing)
  - `articles/tax/coretax-vs-djp-online-what-changed.mdx` (existing)
  - `articles/immigration/npwp-of-wives-automatically-deactivated-in-coretax.mdx` (existing — currently in `immigration/`, candidate to **redirect** to `tax/`)

### Cluster 3 — Tax incentives & holiday

- **Pillar**: `tax-incentives-indonesia` (canonical: `articles/tax/tax-incentives-indonesia.mdx`)
- **Target queries**: `indonesia tax incentive` (29 imp), `tax incentives indonesia` (24 imp), `indonesia tax exemption` (48 imp), `tax exemptions indonesia` (18 imp), `indonesia tax holiday pioneer industries list` (4-6 imp variants — **9 distinct query variants total**, this is gold), `indonesia tax allowance 30% investment deduction 6 years` (1 imp, position 5)
- **Spokes** (existing or to-create):
  - `articles/tax/indonesia-zero-tax-foreign-income-2026.mdx` (already cluster-1 spoke, double-link OK)
  - `articles/business/kbli-2025-tax-implications-klu.mdx` (existing)
  - `articles/immigration/bali-kek-financial-zone-targets-dubai-style-tax-breaks-for-investors.mdx` (existing)
  - **TO CREATE**: `tax-holiday-pioneer-industries-list-2026` (9 query variants begging for a dedicated page, currently `/tax-legal/` press articles only)
  - **TO CREATE**: `tax-allowance-30-investment-deduction-guide` (1 imp position 5, demand exists)
  - **TO CREATE**: `tax-incentives-vs-tax-holiday-difference` (disambiguation page — high intent confusion)

### Cluster 4 — Rental & property income tax

- **Pillar**: `rental-income-tax-indonesia` (canonical: `articles/tax/rental-income-tax-indonesia.mdx`; **currently duplicated** in `articles/property/rental-income-tax.mdx` — see §6)
- **Target queries**: `indonesia final tax on rental income 10%` (10 imp position 4.2), `indonesia final income tax on rental of land and buildings 10%` (8 imp position 5.38), `airbnb tax` (2 imp position 4.5), `rent and tax` (2 imp position 2.5), `rental income tax` (2 imp position 5.5)
- **Spokes**:
  - `articles/tax/bphtb-property-transfer-tax.mdx` (existing)
  - `articles/tax/capital-gains-tax-indonesia.mdx` (existing)
  - `articles/tax/pbb-property-tax-indonesia.mdx` (existing)
  - `articles/property/property-tax-guide.mdx` (existing)
  - `articles/property/selling-property-indonesia.mdx` (existing)
- **Cannibalization risk**: 2 versions of `rental-income-tax` (under `/tax/` and `/property/`) ranking simultaneously — see §6.

### Cluster 5 — Tax deadlines, filing & compliance

- **Pillar**: `tax-calendar-indonesia` (slug: `articles/tax/tax-calendar-indonesia.mdx`)
- **Target queries**: `indonesia tax filing deadline 2026` (6 imp), `tax report deadline 2026` (2 imp), `personal tax due date 2026` (1 imp position 1!), `tax submission deadline 2026` (1 imp position 5), `deadline of tax filing 2026` (1 imp), `indonesia annual tax filing` (1 imp), `indonesia annual tax reconciliation` (1 imp)
- **Spokes**:
  - `articles/tax/annual-tax-return-guide.mdx` (existing)
  - `articles/tax/coretax-efiling-spt-guide.mdx` (existing)
  - `articles/tax/quarterly-tax-reporting-indonesia.mdx` (existing)
  - `articles/tax/pph-29-annual-settlement-guide.mdx` (existing)
  - `articles/tax/tax-compliance-checklist-pt-pma.mdx` (existing)
  - `articles/tax/tax-penalties-interest-indonesia.mdx` (existing)
  - `articles/immigration/indonesia-extends-2024-annual-tax-return-deadline-to-april-30.mdx` (news, lower priority)

### Cluster 6 — VAT/PPN

- **Pillar**: `vat-ppn-guide` (slug: `articles/tax/vat-ppn-guide.mdx`)
- **Target queries**: `ppn vat` (6 imp position 50), `indonesia ppn rate 2026` (5 imp position 6), `ppn rate indonesia 2026` (4 imp position 5.25), `ppn indonesia 2026 rate` (4 imp), `indonesia vat ppn rate 2026` (1 imp), `vat ppn` (1 imp position 56), `vat adalah ppn` (1 imp, Indonesian intent), `tax vat` (1 imp position 38), `ppn indonesia` (2 imp position 8)
- **Spokes**:
  - `articles/tax/e-faktur-vat-invoice-guide.mdx` (existing)
  - `articles/tax/tax-payment-methods-indonesia.mdx` (existing)
  - **TO CREATE**: `ppn-12-percent-increase-2026` (specific to 2026 rate change, current position 50 on generic page is wasted opportunity)

### Cross-cluster / standalone slugs (not in main 6)

- Bali tourist tax → 3-4 query variants, standalone page `bali-tourist-tax-2026-amount` (could be created or extracted from `articles/tax-legal/`)
- Digital nomad visa tax → high-value query `indonesia digital nomad visa tax implications 2026` (4 imp position 1!), spoke of immigration cluster `e33g-remote-worker-visa-guide`
- Double tax treaties → existing `articles/tax/double-taxation-treaties.mdx` + `tax-treaties-explained.mdx` (consolidate, see §6)
- Capital gains → existing `articles/tax/capital-gains-tax-indonesia.mdx` (position 28 generic, 31 in EN, room for ranking improvement)

---

## §4 — 12 money pages prioritization (D2 Minggu 3)

Selected for: (a) existing SEO equity (position <15), (b) high commercial intent, (c) deliverability of WhatsApp CTA + ArticleClusterCTA without rewrite.

| #   | Slug                                          | Existing position           | Target   | Cluster     | Notes                                                            |
| --- | --------------------------------------------- | --------------------------- | -------- | ----------- | ---------------------------------------------------------------- |
| 1   | `tax-residency-indonesia`                     | 5.8                         | 1-3      | C1 pillar   | Title+meta rewrite, schema FAQ, WA CTA                           |
| 2   | `npwp-foreigners-guide`                       | 3-3.8                       | 1        | C2 pillar   | Position-3 already, polish only                                  |
| 3   | `tax-incentives-indonesia`                    | 39-72                       | 5-10     | C3 pillar   | Heavy rewrite + structure                                        |
| 4   | `rental-income-tax-indonesia`                 | 4.2-5.5                     | 1-3      | C4 pillar   | Title rewrite + redirect canon (§6)                              |
| 5   | `tax-calendar-indonesia`                      | 4.9                         | 1-3      | C5 pillar   | Position-5 already, year-update + table                          |
| 6   | `vat-ppn-guide`                               | 21.85                       | 5-10     | C6 pillar   | Rewrite with 2026 rate change as lede                            |
| 7   | `indonesia-zero-tax-foreign-income-2026`      | 43-44.7                     | 5-10     | C1 spoke    | Existing, fix title/intro for clarity                            |
| 8   | `capital-gains-tax-indonesia`                 | 27-33                       | 10-15    | C4 spoke    | Mid-funnel, schema markup                                        |
| 9   | `pph-21-expat-guide`                          | TBD (no GSC visibility yet) | 5-15     | C5 spoke    | New traffic capture (low-comp ID)                                |
| 10  | `e33g-remote-worker-visa-guide` (immigration) | 1 (specific query)          | maintain | C5/C1 spoke | Tax implications section + WA CTA                                |
| 11  | `coretax-efiling-spt-guide`                   | TBD                         | 5-15     | C2 spoke    | Coretax is hot in 2026                                           |
| 12  | `tax-holiday-pioneer-industries-list-2026`    | (new)                       | 1-5      | C3 spoke    | **NEW article**, 9 distinct query variants. Highest ROI new page |

### 4.1 Per-page deliverables (Subhi scope)

For each of the 12, in this order:

1. **Title rewrite** (60-70 chars, target query verbatim once, "2026" if year-sensitive)
2. **Meta description** (155-165 chars, value prop + verb + WA hook)
3. **H1 alignment** (matches title intent)
4. **Lede paragraph rewrite** (first 50 words contain target query + secondary)
5. **TL;DR callout** (≤ 80 words, MDX `<Callout>` component)
6. **WhatsApp CTA** (`<HeaderWhatsAppCTA />` — already shipped in PR #584)
7. **ArticleClusterCTA** (D2 builds this — internal-link block to 3-5 cluster siblings + pillar)
8. **ArticleToolEmbed** (D3 builds this — embed `/tools/tax-calendar` or `/tools/kbli` where contextually relevant; this means D2 must scaffold the slot)
9. **FAQ schema markup** (JSON-LD, 3-5 Q&A from the target query variants in §3)
10. **Internal linking audit** (each money page must have ≥ 5 inbound internal links from cluster siblings)

### 4.2 Out of scope D2

- Backlink outreach (D7+)
- Translation to ID/IT (Minggu 6+, separate workstream, depends on `transform-outdated-visa-codes.ts` Week 4-5)
- New article body writing (only #12 is new; the other 11 are existing-article SEO refactor)

---

## §5 — Cluster mapping summary (Subhi-facing table)

Subhi consumes this table directly when building `ArticleClusterCTA` component (D2 Minggu 3). Each money page imports its cluster JSON from `apps/mouth/src/data/clusters/<cluster-id>.json`.

| Cluster ID               | Pillar slug                   | Money pages count | Spokes count                 | JSON file                                  |
| ------------------------ | ----------------------------- | ----------------- | ---------------------------- | ------------------------------------------ |
| C1 — residency           | `tax-residency-indonesia`     | 2 (#1, #7)        | 5                            | `data/clusters/c1-tax-residency.json`      |
| C2 — npwp-coretax        | `npwp-foreigners-guide`       | 2 (#2, #11)       | 6                            | `data/clusters/c2-npwp-coretax.json`       |
| C3 — incentives-holiday  | `tax-incentives-indonesia`    | 2 (#3, #12)       | 6 (3 existing + 3 to-create) | `data/clusters/c3-incentives-holiday.json` |
| C4 — rental-property-tax | `rental-income-tax-indonesia` | 2 (#4, #8)        | 5                            | `data/clusters/c4-rental-property.json`    |
| C5 — deadlines-filing    | `tax-calendar-indonesia`      | 3 (#5, #9, #10)   | 7                            | `data/clusters/c5-deadlines-filing.json`   |
| C6 — vat-ppn             | `vat-ppn-guide`               | 1 (#6)            | 2 (+1 to-create)             | `data/clusters/c6-vat-ppn.json`            |

### 5.1 Cluster JSON schema

```ts
// apps/mouth/src/data/clusters/c1-tax-residency.json
{
  "id": "c1-tax-residency",
  "title": "Tax Residency & 183-day rule",
  "pillar": {
    "slug": "tax-residency-indonesia",
    "category": "tax",
    "title": "Indonesia Tax Residency: The 183-day Rule for Foreigners (2026)"
  },
  "spokes": [
    {
      "slug": "indonesia-zero-tax-foreign-income-2026",
      "category": "tax",
      "title": "Zero Tax on Foreign Income in Indonesia (2026): Reality Check"
    },
    {
      "slug": "indonesias-183-day-tax-residency-rule-what-expats-get-wrong-in-2026",
      "category": "business",
      "title": "What Expats Get Wrong About Indonesia's 183-day Rule (2026)"
    }
    // ... 3 more spokes
  ],
  "related_clusters": ["c5-deadlines-filing"]
}
```

`ArticleClusterCTA` reads this and renders: pillar link (1) + 3 random spokes (rotate per page-view for freshness) + 1 related-cluster link.

---

## §6 — URL canonicalization & cannibalization fixes (separate ticket, NOT D2 scope)

GSC reveals 4 cannibalization clusters that must be resolved via 301 redirects + `<link rel="canonical">` headers. These are tracked here for Antonello/Subhi visibility but **NOT part of D2 Subhi scope** — they need Next.js routing changes + redirect map + revalidation.

### 6.1 `tax-incentives-indonesia` triple-fork

| URL                                                           | Imp 90gg | Position | Status                                                             |
| ------------------------------------------------------------- | -------- | -------- | ------------------------------------------------------------------ |
| `https://www.balizero.com/tax-legal/tax-incentives-indonesia` | 106      | 39.75    | **CANONICAL** (most equity)                                        |
| `https://www.balizero.com/taxes/tax-incentives-indonesia`     | 37       | 72.54    | 301 → canonical                                                    |
| `https://balizero.com/services/tax` (mentions incentives)     | 73       | 73.84    | Keep (services page), no internal link to tax-incentives-indonesia |

### 6.2 `tax-residency-indonesia` triple-fork

| URL                                                          | Imp 90gg | Position | Status                       |
| ------------------------------------------------------------ | -------- | -------- | ---------------------------- |
| `https://www.balizero.com/tax-legal/tax-residency-indonesia` | 15       | 5.8      | **CANONICAL**                |
| `https://www.balizero.com/taxes/tax-residency-indonesia`     | 11       | 38.91    | 301 → canonical              |
| `https://balizero.com/tax-legal/tax-residency-indonesia`     | 2        | 5        | Already canonical (no `www`) |

### 6.3 `rental-income-tax` dual-fork

| URL                                                   | Imp 90gg | Position | Status                       |
| ----------------------------------------------------- | -------- | -------- | ---------------------------- |
| `https://www.balizero.com/property/rental-income-tax` | 32       | 5.72     | Keep (`/property/` context)  |
| `https://balizero.com/property/rental-income-tax`     | 1        | 3        | Already canonical (no `www`) |

| Content of `/tax/rental-income-tax-indonesia.mdx` should hard-link to `/property/rental-income-tax` and vice-versa, both kept (different intent split: tax-side vs property-side)

### 6.4 `npwp-foreigners-guide` dual-fork

| URL                                                        | Imp 90gg | Position | Status                      |
| ---------------------------------------------------------- | -------- | -------- | --------------------------- |
| `https://balizero.com/tax-legal/npwp-foreigners-guide`     | 2        | 3        | **CANONICAL**               |
| `https://balizero.com/taxes/npwp-foreigners-guide?lang=it` | 5        | 3.8      | This is IT lang version, OK |

### 6.5 `tax-deadlines-2026` triple-fork

| URL                                                     | Imp 90gg | Position | Status                                           |
| ------------------------------------------------------- | -------- | -------- | ------------------------------------------------ |
| `https://www.balizero.com/tax-legal/tax-deadlines-2026` | 10       | 4.9      | **CANONICAL**                                    |
| `https://balizero.com/tax-legal/tax-deadlines-2026`     | 1        | 1        | Position 1 but only 1 imp, low confidence sample |
| `https://www.balizero.com/taxes/tax-deadlines-2026`     | 1        | 18       | 301 → canonical                                  |

### 6.6 `www.` vs root domain split

The `balizero.com` (Domain property) GSC sees both `www.balizero.com` and `balizero.com` (apex) as separate hostnames. Same content indexed twice = ~50% search budget wasted.

**Decision**: redirect 301 all `www.balizero.com/*` → `balizero.com/*` (apex preferred) in Next.js `middleware.ts` or Vercel project settings. This is **infrastructure ticket**, not Subhi scope.

---

## §7 — Deliverable handoff to Subhi

**Owner D2 (Minggu 3 — 14-20 Mei)**: Subhi
**Owner cluster JSON authoring**: Antonello (this PR + follow-up `data/clusters/c1..c6.json`)
**Owner §6 redirect map**: Antonello (separate infrastructure PR, no Subhi blocking)

### 7.1 What Subhi needs to start D2

1. ✅ This file (`docs/marketing/spec-tax.md`)
2. ⏳ The 6 cluster JSON files (Antonello deliverable, **paling lambat Kamis 15 Mei**)
3. ✅ `HeaderWhatsAppCTA` component (already shipped PR #584)
4. ⏳ `<ArticleClusterCTA cluster="c1-tax-residency" />` component (D2 build itself)
5. ⏳ `<ArticleToolEmbed tool="tax-calendar" />` component slot (D3)

### 7.2 What Subhi delivers at end of D2

12 PR (or 1 PR with 12 commit, Subhi's choice) covering:

- Per money page: title, meta, H1, lede, TL;DR callout, WA CTA, ArticleClusterCTA, FAQ schema, internal linking
- 1 new MDX article: `tax-holiday-pioneer-industries-list-2026.mdx` (slug C3 #12)
- 1 new component: `apps/mouth/src/components/ArticleClusterCTA.tsx`

### 7.3 Quality gates

- Lighthouse SEO ≥ 95 per money page
- All money pages must have ≥ 5 inbound internal links from cluster siblings (verify via `scripts/audit-internal-links.ts` — to build if doesn't exist, otherwise grep)
- Vercel preview reviewed by Antonello before merge

---

## §8 — Open questions for Antonello

1. **Is `www.balizero.com` → `balizero.com` 301 redirect on Antonello's roadmap?** Without it, every D2 money page will continue to be indexed twice (waste).
2. **Should `/services/tax` page (currently position 73-79 with 73-83 impressions combined) be kept or redirected to `/tax/` pillar?** Mixed signals: it serves a different intent (commercial/service-oriented) but cannibalizes residency/incentive intent.
3. **Tourist tax (`bali-tourist-tax-2026-amount`)**: 4-5 query variants, no existing slug. Greenfield article worth creating in C5? Or separate `bali-fees/` cluster?
4. **`crypto-tax-indonesia-2026.mdx` exists but no GSC visibility yet** — should we promote it (D2 spoke) or wait for organic discovery?
5. **Subhi access to GSC**: should Antonello add Subhi as Restricted User to `balizero.com` Domain property so he can self-verify after-merge ranking shifts? Recommend: yes, restricted (read-only) role.

---

## §9 — Changelog

- **2026-05-11** — v1 spec created from GSC 90gg export + repo inventory baseline. Author: Antonello (with Claude Opus 4.7 assist). PR: `docs(marketing): spec-tax §1-§5 cluster mapping`.
