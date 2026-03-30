# NotebookLM Infographic Generation Prompts

## How to Use

1. Each prompt below is designed for a specific NotebookLM notebook loaded with the relevant source documents.
2. For KBLI prompts: use the `KBLI_2025_VIDEO_SOURCE.md` or the KBLI notebook.
3. For Visa/Tax/PMA prompts: use the Immigration, Company, or Tax notebooks respectively.
4. Paste the prompt into NotebookLM's generation interface.
5. Download the output and apply Bali Zero branding in post-production (see brand specs below).

## Brand Specs for Infographics

| Element | Value |
|---------|-------|
| Background | `#0c0c0e` or `#111114` (dark variants) |
| Accent | `#d4845a` (copper) |
| Text Primary | `#FFFFFF` |
| Text Secondary | `#A0A0A0` |
| Positive/Open | `#4ADE80` (green) |
| Warning/Restricted | `#FBBF24` (amber) |
| Negative/Closed | `#F87171` (red) |
| Font | Montserrat (headings), Inter (body) |
| Logo | Bottom-right corner, 40% opacity, small |

---

## Prompt 1: KBLI 2025 vs KBLI 2020 — Key Changes

**Aspect ratio:** 16:9 (1920x1080) — for X posts, LinkedIn, website embed
**Source notebook:** KBLI

```
Create a clear, data-driven comparison infographic titled "KBLI 2025 vs KBLI 2020: What Changed."

Layout: Split the frame into two columns — KBLI 2020 on the left, KBLI 2025 on the right — connected by arrows showing the transformation.

Include these exact data points:

LEFT COLUMN (KBLI 2020):
- ~1,790 total codes
- Published 2020
- Limited digital economy coverage
- Granular retail subcategories (redundant)

RIGHT COLUMN (KBLI 2025):
- 1,563 total codes (net reduction)
- Published February 2025 (BPS Regulation 7/2025)
- 234 new codes for digital, green, creative sectors
- 194 codes merged/consolidated
- 266 codes renumbered
- 928 codes unchanged (1:1 match)

BOTTOM SECTION:
- Deadline callout: "Migrate by June 18, 2026"
- Key stat: "96.7% of codes open to 100% foreign ownership"

Style: Clean, minimal, professional. Use a dark background with white text and accent colors for emphasis. No decorative illustrations — data-forward design.
```

---

## Prompt 2: Which Visa Do You Need? Decision Flowchart

**Aspect ratio:** 9:16 (1080x1920) — for Instagram Stories, TikTok, WhatsApp Status
**Source notebook:** Immigration

```
Create a decision flowchart infographic titled "Which Indonesia Visa Do You Need?"

The flowchart should start with one question at the top and branch downward based on yes/no answers:

START: "Are you coming to Indonesia?"

Branch 1: "For how long?"
  → Under 60 days → "Tourism (C1) or Business Visit (C2)"
  → Over 60 days → Continue to Branch 2

Branch 2: "Will you work for an Indonesian company?"
  → Yes → "Working KITAS (E23) — need RPTKA"
  → No → Continue to Branch 3

Branch 3: "Are you investing / opening a company?"
  → Yes → "Investor KITAS (E28A) — need PT PMA"
  → No → Continue to Branch 4

Branch 4: "Are you married to an Indonesian citizen?"
  → Yes → "Spouse KITAS (E31A)"
  → No → Continue to Branch 5

Branch 5: "Are you working remotely for a foreign employer?"
  → Yes → "Remote Worker KITAS (E33G)"
  → No → Continue to Branch 6

Branch 6: "Are you retired (55+)?"
  → Yes → "Retirement KITAS (E33E/F)"
  → No → "Contact a consultant for your specific situation"

BOTTOM: "After 4-5 consecutive years on KITAS → KITAP (Permanent Stay)"

Style: Vertical flow, dark background, each decision box should be distinct. Use copper accent for the final visa type answers. Keep text concise — max 10 words per box.
```

---

## Prompt 3: PT PMA Setup Cost Breakdown 2026

**Aspect ratio:** 1:1 (1080x1080) — universal (X, Instagram feed, LinkedIn)
**Source notebook:** Company

```
Create a cost breakdown infographic titled "PT PMA Setup Costs in Indonesia (2026)."

Layout: Stacked horizontal bars or a structured breakdown showing each cost component.

Include these cost items with amounts:

SETUP COSTS:
- PT PMA Registration: from IDR 7,000,000 (~USD 440)
- Notary Fee (Akta Pendirian): IDR 3,000,000 - 8,000,000
- SK Kemenkumham: included in registration
- NIB + OSS Registration: included
- KBLI 2025 Alignment: included
- Company Domicile Letter: IDR 1,000,000 - 3,000,000
- Bank Account Opening: IDR 500,000 - 1,000,000

CAPITAL REQUIREMENTS (mandatory by law):
- Minimum Total Investment: IDR 10 billion (~USD 625,000) per PP 5/2021
- Minimum Paid-Up Capital: IDR 2.5 billion per shareholder
- Note: "Investment = total value including assets, not just cash"

ONGOING ANNUAL COSTS:
- Corporate Tax Filing: varies
- Annual Report (Permenkumham 49/2025): mandatory
- KITAS Renewal (if applicable): IDR 11,000,000 - 36,000,000

BOTTOM CALLOUT:
"Total setup from IDR 7,000,000 | Capital commitment IDR 10B"

Style: Clean data visualization. Use a dark background. Highlight the setup fee prominently (it's the most actionable number). Show capital requirements separately and clearly — these are often confused with setup costs.
```

---

## Prompt 4: Indonesia Tax Calendar — Key Deadlines

**Aspect ratio:** 16:9 (1920x1080) — for X, LinkedIn, website embed
**Source notebook:** Tax

```
Create a 12-month tax calendar infographic titled "Indonesia Tax Calendar 2026: Key Deadlines for Foreign-Owned Companies."

Layout: Horizontal timeline showing all 12 months, with key deadlines marked as pins or callouts above the timeline.

Include these deadlines:

MONTHLY (every month):
- 10th: PPh 21 (employee income tax) deposit deadline
- 15th: PPh 23/26 (withholding tax) deposit deadline
- 15th: PPN (VAT) deposit deadline
- 20th: PPh 21/23/26 monthly reporting
- End of month: PPN monthly reporting via Coretax

ANNUAL:
- January 31: PPh 21 annual employee tax form (1721-A1)
- March 31: Personal income tax return (SPT Tahunan OP)
- April 30: Corporate income tax return (SPT Tahunan Badan)
- April 30: Annual corporate report to Kemenkumham (NEW — Permenkumham 49/2025)

QUARTERLY:
- PPh 25 (corporate income tax installments): 15th of month following quarter end

SPECIAL 2026:
- June 18: KBLI 2025 migration deadline (not tax, but affects KLU mapping)

BOTTOM NOTE:
"All deadlines are calendar days. Late filing = 2% penalty per month. Coretax system mandatory for all filings since 2025."

Style: Horizontal calendar strip. Dark background. Use copper accent for the most critical deadlines (annual returns, KBLI migration). Monthly recurring items can be shown as a repeating pattern or legend below the timeline.
```

---

## Prompt 5: Foreign Ownership by KBLI Sector

**Aspect ratio:** 1:1 (1080x1080) — universal
**Source notebook:** KBLI

```
Create a sector overview infographic titled "Foreign Ownership in Indonesia by Sector (KBLI 2025)."

Layout: Grid or vertical list showing the most relevant sectors for foreign investors, with ownership status color-coded.

Include these sectors with their status:

100% FOREIGN OWNERSHIP ALLOWED (TERBUKA):
- Management Consulting (70209)
- Software Development (62019)
- Web Portals / Digital Platforms (63122)
- IT Consulting (62201-62209)
- Real Estate Agency (68201)
- Online Retail / E-Commerce (47911)
- Restaurant / Food Service (56101)
- General Retail (47192)

RESTRICTED (TERBATAS — foreign ownership capped):
- Alcoholic Beverage Retail
- Certain media and broadcasting
- Small-scale mining

CLOSED TO FOREIGNERS (TERTUTUP):
- Narcotics-classified substances
- Gambling
- Certain cultural heritage activities
- Weapons manufacturing

SUMMARY STATS:
- 1,512 codes (96.7%): TERBUKA (Open)
- 12 codes (0.8%): TERBATAS (Restricted)
- 39 codes (2.5%): TERTUTUP (Closed)

CALLOUT:
"Source: PP 5/2021, PP 49/2023, BPS Regulation 7/2025"
"Minimum investment for PT PMA: IDR 10 billion"

Style: Use green for TERBUKA, amber for TERBATAS, red for TERTUTUP. Dark background. Emphasize the 96.7% open statistic as the headline number. Professional, investor-grade design.
```

---

## Post-Production Notes for All Infographics

After NLM generates the infographic:

1. **Add logo:** Bottom-right corner, `balizero-logo-clean.png`, 40% opacity, ~50px.
2. **Verify brand colors:** NLM may not use the exact hex values above. Adjust in Figma, Canva, or Photoshop.
3. **Add source attribution:** Small text at bottom: `Source: BPS Regulation 7/2025, PP 5/2021 | balizero.com`
4. **Export variants:**
   - Full resolution PNG for website/blog embed.
   - Compressed JPEG (quality 85%) for social media upload.
   - PDF for email attachments and WhatsApp sharing.
5. **Naming convention:** `BZ_INFOGRAPHIC_{TOPIC}_{RATIO}_{VERSION}.png`
   - Example: `BZ_INFOGRAPHIC_KBLI_COMPARISON_16x9_v1.png`
   - Example: `BZ_INFOGRAPHIC_VISA_FLOWCHART_9x16_v1.png`
