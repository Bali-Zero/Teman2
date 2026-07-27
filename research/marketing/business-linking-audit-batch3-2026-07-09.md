---
adversarial_review: human-Subhi Darajat / Claude Sonnet 4.6 — 2026-07-30
---

# /business/ Internal Linking Audit — Batch 3

# Date: 9 July 2026

# Auditor: Subhi Darajat

# Method: grep -rL "/business/" apps/mouth/src/content/articles/business/

# Scope: English base .mdx files only

# Rule: Audit today (9 Jul), PR execution tomorrow (10 Jul)

## PRIORITY 1 — High Value

| #     | Slug                                                                      | Suggested Link Targets                                                                                                                                     |
| ----- | ------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| B3-01 | bali-business-setup-in-2026-what-every-foreign-entrepreneur-must-know.mdx | /business/pt-pma-registration-guide, /business/business-licenses-overview, /business/kbli-2025-foreign-ownership-pma-guide                                 |
| B3-02 | bali-business-climate-2026-what-foreigners-actually-face.mdx              | /business/bali-business-setup-in-2026-what-every-foreign-entrepreneur-must-know, /business/pt-pma-registration-guide, /business/bkpm-regulation-5-2025-fdi |
| B3-03 | bali-tourism-business-license-what-you-need-to-start-legally.mdx          | /business/business-licenses-overview, /business/nib-oss-guide, /business/kbli-2025-hospitality-accommodation                                               |
| B3-04 | bali-property-2026-what-the-investment-numbers-actually-tell-you.mdx      | /business/buy-property-in-bali-as-a-foreigner-2026-legal-investment-guide, /business/pt-pma-capital-requirements, /business/kbli-2025-real-estate-property |
| B3-05 | bali-property-2026-whos-really-buying-and-what-could-go-wrong.mdx         | /business/buy-property-in-bali-as-a-foreigner-2026-legal-investment-guide, /business/kbli-2025-real-estate-property, /business/due-diligence-indonesia     |
| B3-06 | bali-investment-market-separating-real-opportunity-from-the-hype.mdx      | /business/buy-property-in-bali-as-a-foreigner-2026-legal-investment-guide, /business/pt-pma-registration-guide, /business/capital-requirements-guide       |

## PRIORITY 2 — Medium Value

| #     | Slug                                                                             | Suggested Link Targets                                                                                                                                    |
| ----- | -------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| B3-07 | bali-vs-koh-samui-where-your-property-money-actually-works-harder.mdx            | /business/buy-property-in-bali-as-a-foreigner-2026-legal-investment-guide, /business/can-foreigners-buy-property-in-bali-in-2025-ultimate-guide           |
| B3-08 | thailand-vs-bali-the-hidden-cost-of-picking-the-wrong-jurisdiction.mdx           | /business/pt-pma-registration-guide, /business/business-licenses-overview                                                                                 |
| B3-09 | phuket-vs-bali-the-property-investment-battle-foreigners-get-wrong.mdx           | /business/buy-property-in-bali-as-a-foreigner-2026-legal-investment-guide, /business/can-foreigners-buy-property-in-bali-in-2025-ultimate-guide           |
| B3-10 | bali-cements-status-as-world-class-leisure-hub.mdx                               | /business/bali-business-setup-in-2026-what-every-foreign-entrepreneur-must-know, /business/investing-in-bali-2026-all-you-need-to-know-before-buying-bali |
| B3-11 | bank-indonesia-bali-stays-a-top-investment-destination-despite-global-unrest.mdx | /business/investing-in-bali-2026-all-you-need-to-know-before-buying-bali, /business/bali-business-setup-in-2026-what-every-foreign-entrepreneur-must-know |
| B3-12 | bali-2026-eco-luxury-villas-and-the-new-american-expat-playbook.mdx              | /business/buy-property-in-bali-as-a-foreigner-2026-legal-investment-guide, /business/kbli-2025-hospitality-villa-hotel-bali-investment-guide              |
| B3-13 | balis-2026-short-term-rental-rules-what-owners-must-do-now.mdx                   | /business/business-licenses-overview, /business/kbli-2025-hospitality-accommodation, /business/environmental-permits                                      |
| B3-14 | bali-ota-purge-2026.mdx                                                          | /business/balis-2026-short-term-rental-rules-what-owners-must-do-now, /business/business-licenses-overview                                                |

## REVIEW NEEDED

| #     | Slug                                                                                   | Note                                                     |
| ----- | -------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| B3-15 | three-sexual-assaults-in-three-days-puts-bali-tourism-safety-under-scrutiny.mdx        | Sensitive topic — skip unless clear regulatory angle     |
| B3-16 | indonesia-moves-to-bar-under-16s-from-social-media-in-sweeping-digital-safety-push.mdx | Tangential — only link if references business compliance |

## DUPLICATE — VERIFY BEFORE INCLUDING

- bali-vs-koh-samui-where-your-property-money-actually-works-h.mdx → possible truncated duplicate of B3-07
- Run: diff apps/mouth/src/content/articles/business/bali-vs-koh-samui-where-your-property-money-actually-works-h.mdx apps/mouth/src/content/articles/business/bali-vs-koh-samui-where-your-property-money-actually-works-harder.mdx

## EXCLUDED

- the-convergence-of-early-life-stress-and-autism-spectrum-disorder-on-the-epigenetics-of-genes-key-to-the-hpa-axis.mdx → medical/academic, no /business/ link appropriate

## PR Execution Plan (10 Jul 2026)

Branch: sancho/business-indexing-batch3

- Cross-ref business-isolated-articles-2026-06-10.txt dulu — remove overlap Batch 1/2
- Start P1 (B3-01 to B3-06), lanjut P2
- Max 3 links per article, contextual only
- Commit: fix(business): add internal links batch 3 — N articles
- Self-merge VERDE kalau CI hijau

## Adversarial review

**Reviewer:** Claude Sonnet 4.6 (grader) — generator: Subhi Darajat — 2026-07-30

This audit assumes all suggested link targets (e.g. /business/pt-pma-registration-guide, /business/nib-oss-guide) exist as live pages, but no verification was performed that these slugs actually exist in apps/mouth/src/content/articles/business/. Risk: the PR execution will insert dead links if any target slug is missing or differently named. Cross-referencing with business-isolated-articles-2026-06-10.txt before execution is noted in the PR plan but not yet done — this is a hard prerequisite, not optional. B3-15 and B3-16 are flagged "REVIEW NEEDED" with no explicit decision recorded — must be resolved before the PR, not left ambiguous. The possible truncated duplicate (bali-vs-koh-samui-...-h.mdx vs -harder.mdx) requires a diff and explicit resolution before inclusion.
