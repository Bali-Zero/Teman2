# Tax Cluster Linking Plan — Research Memo

**Date:** 2026-05-18
**Author:** Subhi (Growth Systems)
**Status:** Read-only research. No production changes. Hold linking PR until Antonello sign-off on the new tax-residency article.
**Location:** `research/seo/2026-05-18-tax-cluster-linking-plan.md`

---

## TL;DR

Tax cluster contains **~90 article files** across 7 categories (with per-language variants: en, id, it, sometimes fr+ru). Hub candidate **confirmed**: `tax/indonesia-tax-guide-for-foreigners` (featured=true, comprehensive, established Jan 2026).

**Critical finding — keyword cannibalization risk:**
The new article Antonello is reviewing (`business/indonesias-183-day-tax-residency-rule-what-expats-get-wrong-in-2026`) overlaps 80%+ in title, topic, and angle with the existing evergreen article `tax/tax-residency-indonesia.mdx` (published 2026-05-15, 3 days ago). Without clear differentiation or a canonical decision, both will cannibalize each other in SERP.

This memo is not a blocker. Linking PR stays on hold until Antonello decides on canonical strategy. Hub-level linking improvements can proceed independently.

---

## 1. Cluster Inventory

| Surface                                 | Path                                                | Count                 | Type                 |
| --------------------------------------- | --------------------------------------------------- | --------------------- | -------------------- |
| `/tax-calendar` (route)                 | `apps/mouth/src/app/(tax-calendar)/tax-calendar/`   | 1                     | Public tool page     |
| `/portal/taxes` (route)                 | `apps/mouth/src/app/portal/(authenticated)/taxes/`  | 1                     | Authenticated portal |
| `/clients/tax-pilot` (route)            | `apps/mouth/src/app/(workspace)/clients/tax-pilot/` | 1                     | Internal CRM         |
| `/articles/tax/`                        | `apps/mouth/src/content/articles/tax/`              | ~45                   | Evergreen guides     |
| `/articles/tax-legal/`                  | `apps/mouth/src/content/articles/tax-legal/`        | ~40                   | News archive         |
| `/articles/business/` (tax-tagged)      | —                                                   | 4 (incl. new 183-day) | Cross-category       |
| `/articles/immigration/` (tax-tagged)   | —                                                   | 8                     | Cross-category       |
| `/articles/property/` (tax-tagged)      | —                                                   | 2                     | Cross-category       |
| `/articles/digital-nomad/` (tax-tagged) | —                                                   | 1                     | Cross-category       |

---

## 2. Hub Recommendation — CONFIRMED

**Hub:** `tax/indonesia-tax-guide-for-foreigners.mdx`

| Signal           | Status                                             |
| ---------------- | -------------------------------------------------- |
| `featured` field | `true` ✅                                          |
| Title framing    | "Complete guide..." ✅                             |
| Content breadth  | Residency + income tax + reporting + compliance ✅ |
| Published        | 2026-01-15 (established authority) ✅              |
| Slug             | `indonesia-tax-guide-for-foreigners` (clean) ✅    |
| Languages        | en + id + it                                       |

**Action (independent of residency decision):**

- Ensure all `/articles/tax/*` pages link to hub in body or related section
- Ensure `/tax-calendar` route links hub in contextual CTA
- Hub should link top-10 sub-topics: PPH 21, NPWP, VAT/PPN, Coretax, Tax Treaties, Tax Residency, Annual Return, Transfer Pricing, Withholding, BPHTB

---

## 3. ⚠️ Tax Residency Cannibalization Risk

### Head-to-head comparison

| Field         | New (Under Antonello review)                                                       | Evergreen (Live)                                                              |
| ------------- | ---------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| **File path** | `business/indonesias-183-day-tax-residency-rule-what-expats-get-wrong-in-2026.mdx` | `tax/tax-residency-indonesia.mdx`                                             |
| **Title**     | "Indonesia's 183-Day Tax Residency Rule: What Expats Get Wrong in 2026"            | "Tax Residency in Indonesia: The 183-Day Rule and What Most Expats Get Wrong" |
| **Slug**      | `indonesias-183-day-tax-residency-rule-what-expats-get-wrong-in-2026`              | `tax-residency-indonesia`                                                     |
| **Category**  | `business`                                                                         | `tax`                                                                         |
| **Published** | 2026-04-27 (metadata)                                                              | 2026-05-15 (live)                                                             |
| **Author**    | "Exa: rumavi.com" (third-party)                                                    | "Zantara AI"                                                                  |
| **Length**    | 3 min read                                                                         | (unspecified)                                                                 |
| **AI flag**   | Generated (0.85 confidence)                                                        | Zantara-generated                                                             |

**Both target identical primary search intent:** "183-day tax residency rule Indonesia expats"

Title semantic overlap: ~80%+. Category paths differ (business vs tax) but topical SERP collision is guaranteed.

### Three canonical options for Antonello

**Option A — Differentiate by purpose (RECOMMENDED)**

- Evergreen `tax-residency-indonesia` = authoritative comprehensive guide (dual-test, edge cases, KITAS/PMA/E33G holders, treaty mechanics)
- New 183-day article = news/opinion angle with AEO snippet for SGE (what most expats get wrong, 2026 updates)
- Both live, but with explicit canonical cross-linking and clear differentiation
- **Pros:** Keep both, target different user journeys (quick answer vs deep reference)
- **Cons:** Requires disciplined linking to avoid remaining overlap

**Option B — Merge**

- Choose evergreen as canonical, absorb best paragraphs from new article (AEO snippet, news framing)
- Discard new article file
- **Pros:** Zero cannibalization
- **Cons:** Lose news angle and SGE optimization

**Option C — Demote**

- Publish new article with `noindex` meta robots OR move to `tax-legal/` (news archive) with canonical pointing to evergreen
- **Pros:** Keep content, no SERP competition
- **Cons:** New article gets no organic traffic

**Recommendation:** Option A with strict editorial discipline. New article must link to evergreen in opening paragraph as "comprehensive guide," and evergreen must link back as "2026 updates and common misconceptions." Differentiate by _purpose_ (snapshot vs reference), not topic.

---

## 4. Linking Strategy — For when new article is approved

### 4.1 Inbound links to new article (6 candidates)

| From                                                             | Anchor text                                 | Context               |
| ---------------------------------------------------------------- | ------------------------------------------- | --------------------- |
| `tax/tax-residency-indonesia.mdx`                                | "what expats commonly get wrong in 2026"    | Opening paragraph     |
| `tax/indonesia-tax-guide-for-foreigners.mdx` (hub)               | "2026 updates: 183-day rule misconceptions" | Tax residency section |
| `tax/pph-21-expat-guide.mdx`                                     | "confirm your tax residency status"         | Before tax-rate table |
| `immigration/indonesia-tax-for-expats-who-owes-what-in-2026.mdx` | "183-day rule clarifications 2026"          | Body context          |
| `tax/tax-planning-expats.mdx`                                    | "residency status planning traps"           | Planning checklist    |
| `tax/tax-deductions-expats-indonesia.mdx`                        | "verify residency status first"             | Eligibility section   |

### 4.2 Outbound links from new article (7 candidates)

| To                                               | Anchor text                                    | Purpose                              |
| ------------------------------------------------ | ---------------------------------------------- | ------------------------------------ |
| `tax/tax-residency-indonesia.mdx`                | "Complete guide to tax residency in Indonesia" | Canonical reference (MUST prominent) |
| `tax/indonesia-tax-guide-for-foreigners.mdx`     | "Indonesia tax guide for foreigners"           | Hub reference                        |
| `tax/pph-21-expat-guide.mdx`                     | "Expat PPH 21 tax obligations"                 | Next action                          |
| `tax/npwp-foreigners-guide.mdx`                  | "NPWP registration for foreigners"             | Tactical step                        |
| `tax/double-tax-agreement-claiming-benefits.mdx` | "Claiming treaty relief"                       | Compliance context                   |
| `/tax-calendar` (route)                          | "Indonesia tax calendar 2026"                  | Deadline reference                   |
| WhatsApp CTA                                     | "Consult with a Bali Zero tax specialist"      | Conversion                           |

### 4.3 Hreflang / multilingual notes

Both articles have 3 language variants (en, id, it). On publish:

- Ensure `<link rel="alternate" hreflang="...">` tags are consistent between new and evergreen
- Maintain slug pattern parity across languages

---

## 5. Other duplicate-looking articles (backlog — low priority)

For Antonello's eventual review, **not in scope today**:

| Group           | Files                                                                                                      | Recommendation                                                |
| --------------- | ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| Tax treaties    | `double-tax-agreement-claiming-benefits.mdx`, `double-taxation-treaties.mdx`, `tax-treaties-explained.mdx` | 3 files with semantic overlap — confirm canonical             |
| Freelancer tax  | `freelancer-tax-guide.mdx`, `tax-for-freelancers-indonesia-2026.mdx`                                       | Possible duplicate — consolidate or differentiate             |
| Rental income   | `tax/rental-income-tax-indonesia.mdx`, `property/rental-income-tax.mdx`                                    | Cross-category pair — add canonical pointer                   |
| Withholding tax | `withholding-tax-guide.mdx`, `pph-23-withholding-tax-guide.mdx`, `pph-26-foreign-withholding-tax.mdx`      | Hierarchy: parent overview + 2 sub-pillars? Confirm structure |
| VAT/PPN         | `vat-ppn-guide.mdx`, `e-faktur-vat-invoice-guide.mdx`, `ppn-12-percent-increase-2026.mdx`                  | 4 files forming VAT sub-cluster — clarify relationships       |

---

## 6. Recommendations

1. **No immediate production changes today.** This memo is read-only analysis.
2. **Flag cannibalization risk to Antonello** alongside the article review request — ensure canonical decision is made concurrently with publish decision.
3. **Linking PR on hold** until decision is made. Premature linking will require rework.
4. **Hub-level linking improvements** can proceed independently in a separate PR.
5. **Duplicate cleanup (section 5)** enters SEO backlog for Antonello's eventual review.

---

## 7. Next Actions

| Timeline                 | Action                                                                                          | Owner     |
| ------------------------ | ----------------------------------------------------------------------------------------------- | --------- |
| Today (2026-05-18)       | Share memo summary with Antonello alongside article review context                              | Subhi     |
| After Antonello decision | Draft linking PR (`sancho/seo-tax-residency-linking-plan`), include Studio Layer in description | Subhi     |
| Post-merge               | QA: GSC submission, rich result validation, SERP overlap monitoring                             | Subhi     |
| Backlog                  | Antonello review section 5 duplicates for cleanup strategy                                      | Antonello |

---

## Appendix A — Referenced files

- `apps/mouth/src/content/articles/business/indonesias-183-day-tax-residency-rule-what-expats-get-wrong-in-2026.mdx`
- `apps/mouth/src/content/articles/tax/tax-residency-indonesia.mdx`
- `apps/mouth/src/content/articles/tax/indonesia-tax-guide-for-foreigners.mdx`
- `apps/mouth/src/app/(tax-calendar)/tax-calendar/page.tsx`
- `apps/mouth/src/content/articles/tax/` (core directory, ~45 evergreen articles)

## Appendix B — Methodology

Discovery via `find` + `grep` on path patterns. Frontmatter analysis via `head -25` per file. No production files modified. No runtime/build checks executed. Memo grounded in static frontmatter + slug analysis only — full body content not read.
