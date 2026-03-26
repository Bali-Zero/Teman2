# KBLI 2025 Gold Content Research — Prompt for Gemini 3

## Your Role

You are a business intelligence researcher specializing in Indonesian business regulations, specifically KBLI (Klasifikasi Baku Lapangan Usaha Indonesia) codes, OSS (Online Single Submission) licensing, and foreign investment (PMA) rules. You have deep knowledge of Bali's business landscape.

## Your Task

For each KBLI 2025 code below, produce **Gold-tier editorial content** in English. This content will be displayed on a public-facing reference tool (KBLI Navigator by Bali Zero) used by foreign investors, entrepreneurs, and consultants planning to start businesses in Bali, Indonesia.

## Output Format (STRICT)

For each code, return a JSON object with exactly these 6 fields:

```json
{
  "code": "XXXXX",
  "whatItMeans": "...",
  "whatYouNeed": "...",
  "whatChanged": "...",
  "baliContext": "...",
  "youllAlsoNeed": "...",
  "zantaraOpener": "..."
}
```

### Field Descriptions

**whatItMeans** (2-4 sentences)

- Plain English explanation of what this business activity covers
- Include what it includes AND what it does NOT include (reference related codes)
- Use concrete examples relevant to Bali

**whatYouNeed** (structured, detailed)

- Licensing requirements per business scale (Mikro/Kecil/Menengah/Besar)
- Risk category with Indonesian name: e.g. "Medium-Low (Menengah Rendah)"
- License type: NIB, Sertifikat Standar, Izin, etc. — always include Indonesian names
- Processing time with Indonesian: e.g. "Automatic (Otomatis)" or "14 days (14 Hari)"
- Post-issuance obligations — always Indonesian names in parentheses:
  - Sertifikat Laik Sehat (Health Feasibility Certificate)
  - Laporan Kegiatan Berkala (Periodic Activity Reports)
  - Dokumen Penerapan Standar (Standards Compliance Documentation)
  - Sertifikat Standar Usaha Pariwisata (Tourism Business Standard Certificate)
  - etc.
- Authority level: Bupati/Walikota or Gubernur
- PMA status: Terbuka (Open) with %, or Terbatas (Restricted) with conditions
- Source regulation: cite PP28/2024, Perpres 10/2021, etc.

**whatChanged** (1-3 sentences)

- KBLI 2020 → 2025 transition. Use exact mapping terminology:
  - MATCH_LANGSUNG = Direct match, unchanged
  - CODICE_RINUMERATO = Renumbered (new code, same business)
  - MATCH_CON_AGGREGAZIONE = Merged/aggregated from multiple old codes
  - BPS_ONLY = New in 2025, no PP28 licensing data yet
- If renumbered: state old code explicitly

**baliContext** (4-8 sentences, THIS IS THE MOST IMPORTANT FIELD)

- Real-world Bali business intelligence — this is what makes our tool unique
- Specific areas/locations where this business thrives (Seminyak, Canggu, Ubud, etc.)
- Realistic cost ranges in IDR where possible
- Common pitfalls and regulatory traps
- Market saturation vs opportunity assessment
- Practical advice a consultant would give a client
- Cultural or local nuances (e.g. banjar relations, adat considerations)

**youllAlsoNeed** (bullet list)

- Related KBLI codes the business owner will likely need
- Format: `- XXXXX — Brief reason why`
- 3-6 related codes, practical not theoretical

**zantaraOpener** (1 sentence)

- Conversational hook for our AI assistant "Zantara"
- Friendly, knowledgeable tone — like a smart consultant friend
- Must mention the code number

## CRITICAL RULES

1. **Every certificate/document name MUST include the Indonesian name in parentheses** — our users need to know exactly what to ask for at the OSS office
2. **Verify against the PP28/2024 data provided** — do not invent licensing requirements. If a code has no PP28 data (BPS_ONLY), say so explicitly
3. **PMA percentages must match the data** — if it says TERBATAS 49%, do not write "100% open"
4. **Bali context must be specific and current** — mention actual areas, price ranges, competition levels. Generic tourism platitudes are worthless
5. **Write for sophisticated readers** — our users are investors, lawyers, and consultants. No fluff
6. **Risk categories** — always state both English and Indonesian: "Low (Rendah)", "Medium-Low (Menengah Rendah)", "Medium-High (Menengah Tinggi)", "High (Tinggi)"

## Reference: Existing Gold Content Style

Here's an example of our existing Gold content for 55203 (Villa) to match the tone and depth:

```
whatItMeans: "Villas — private houses specifically rented out to tourists, complete with facilities, managed by the owner. Unlike a homestay (55201), the owner doesn't live in the same building. These are dedicated rental properties — the classic Bali villa experience with a private pool, garden, and often staff."

whatYouNeed: "**Micro + Small + Medium**: Medium-Low risk (Menengah Rendah). NIB + Sertifikat Standar issued **automatically** (Otomatis).\n\nPost-issuance obligations:\n- Obtain a Health Feasibility Certificate (Sertifikat Laik Sehat)\n- Submit periodic activity reports (Laporan Kegiatan Berkala)\n- Submit standards compliance documentation (Dokumen Penerapan Standar)\n\n**Authority:** Bupati/Walikota (district/city level).\n\n**PMA:** Fully open (Terbuka) — 100% foreign ownership.\n\nNote: Renumbered from old code 55193 (Vila), same licensing substance."

baliContext: "Villas ARE Bali's tourism identity. Seminyak, Canggu, Ubud, Uluwatu, Sanur — every area has its villa scene. For foreign investors, this is the most popular accommodation code. The business model is typically: lease land (25-30 year Hak Sewa), build a villa, rent it on Airbnb/Booking.com, and manage it through a local PT PMA. Reality check: Bali's villa market is massively oversupplied in some areas..."
```

## Codes to Research

See the attached `gemini-research-input.json` for the full PP28 data for each code.

The 23 codes are:

1. **55104** — Hotel Bintang Dua (Two-Star Hotel)
2. **55105** — Hotel Bintang Satu (One-Star Hotel)
3. **55400** — Intermediasi Akomodasi (Accommodation Intermediary / OTA)
4. **56304** — Kedai Minuman (Beverage Shop / Juice Bar / Bubble Tea)
5. **77100** — Penyewaan Kendaraan Bermotor (Vehicle Rental)
6. **77311** — Penyewaan Alat Transportasi Darat (Land Transport Equipment Rental)
7. **79901** — Jasa Informasi Pariwisata (Tourism Information Services)
8. **93111** — Fasilitas Stadion (Stadium Facilities) — or more relevant: gym/fitness
9. **93210** — Taman Bertema dan Taman Hiburan (Theme Park & Amusement Park)
10. **96100** — Pencucian dan Pembersihan Tekstil (Laundry & Textile Cleaning)
11. **47111** — Perdagangan Eceran Berbagai Macam Barang (Minimarket/Convenience Store) — **NOTA: PMA TERBATAS**
12. **47192** — Perdagangan Eceran Berbagai Macam Barang (Non-food Retail / Boutique)
13. **47901** — Platform Digital Intermediasi Perdagangan Eceran (E-commerce Platform)
14. **63101** — Pengolahan Data (Data Processing)
15. **63102** — Infrastruktur Komputasi, Hosting (Cloud/Hosting Infrastructure)
16. **73100** — Periklanan (Advertising) — **NOTA: PMA TERBATAS 49%**
17. **74192** — Desain Grafis / Komunikasi Visual (Graphic Design)
18. **85510** — Pendidikan Olahraga dan Rekreasi (Sports & Recreation Education — yoga, surf school)
19. **85579** — Pelatihan Kerja Swasta Lainnya (Private Job Training — general courses)
20. **69201** — Akuntansi dan Pembukuan (Accounting & Bookkeeping)
21. **16291** — Barang Anyaman dari Rotan dan Bambu (Rattan & Bamboo Crafts)
22. **23961** — Barang dari Batu Marmer (Marble/Stone Products)
23. **32112** — Perhiasan dari Logam Mulia (Precious Metal Jewelry)

## Important Notes

- For codes marked **BPS_ONLY** (like 55400): there is NO PP28 licensing data yet. State this clearly — "This code exists in KBLI 2025 but has no PP28/2024 licensing data. Requirements will be published when OSS integrates KBLI 2025."
- For codes marked **TERBATAS** (like 47111, 73100): PMA is RESTRICTED, not open. Detail the restrictions.
- **93111 is technically "Stadium Facilities"** but in the Bali context, the relevant use case is fitness centers/gyms. Explain this distinction.
- KBLI 2025 deadline: 18 June 2026 (BPS Regulation 7/2025). OSS has NOT yet integrated KBLI 2025 (as of Feb 2026).

## Delivery

Return ALL 23 codes as a single JSON array. No markdown wrapping — pure JSON that I can parse directly.
