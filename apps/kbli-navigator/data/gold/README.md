# Gold-Tier Editorial Content — Voice Guidelines

## The Voice

**"We know the difficult stuff and explain it simply."**

Write like you're explaining to a friend at a café in Bali. They're smart, they're motivated, but they don't speak Indonesian bureaucracy. Your job is to translate regulation into action.

## Rules

### Be concrete, not abstract

- "You need an SBU construction certificate from LPJK" not "the relevant construction credentials must be obtained"
- "Seminyak landlords charge 2-3x what you'd pay in Sanur" not "rental costs vary by location"
- "Budget 2-4 weeks for the health inspection" not "processing times may vary"

### Zero bureaucratese

- "You can open a restaurant" not "the licensee may engage in food service activities"
- "The government merged four old codes into one" not "the regulatory framework underwent consolidation"
- "This code is brand new — it didn't exist before 2025" not "this classification was introduced in the current revision"

### Name real places

- Mention specific Bali areas: Canggu, Seminyak, Ubud, Sanur, Uluwatu, Nusa Dua, Denpasar, Amed, Sidemen, Munduk
- Compare areas: "Canggu is saturated, Tabanan still has room"
- Reference real landmarks and businesses as context (not as endorsements)

### Cross-reference related codes

- Every business needs multiple KBLI codes. Always tell the reader what else they'll need.
- Format: `CODE — Plain reason why`
- Example: "56301 — If you serve alcohol (separate bar license required)"

### Be honest about complexity

- If something is hard, say so: "The SBU requirement is the key barrier"
- If licensing data doesn't exist yet: "Brand new code — no PP28 requirements published yet"
- If there's a catch for foreigners: "PMA companies face extra certification that locals don't need"

### Use precise data

- Every fact must come from `KBLI_2025_FINAL_CLEAN.json`
- Cite actual risk categories: Rendah, Menengah Rendah, Menengah Tinggi, Tinggi
- Cite actual processing times: "Otomatis" = automatic, "14 Hari" = 14 working days
- Cite actual PMA status: TERBUKA (open), TERBATAS (restricted), TERTUTUP (closed)
- Cite actual pp28_sources and status_mapping values

### Never guess or invent

- If PP28 data is empty (BPS_ONLY codes), say so explicitly
- If a code was renumbered, name the old code number
- If codes were merged, list all the old codes that fed into it
- Do not fabricate requirements, timelines, or fees not in the source data

## Content Structure (KBLIGoldContent interface)

| Field           | Purpose                                                     | Style                                                                                                                  |
| --------------- | ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `whatItMeans`   | 2-3 sentences. What this code lets you DO in plain English. | Start with the business activity, not the code number. Use examples.                                                   |
| `whatYouNeed`   | Requirements from `per_skala` data, by business scale.      | Markdown formatting. Bold the scale names. List actual documents.                                                      |
| `whatChanged`   | 2020 to 2025 transition.                                    | Name old code numbers. Use status_mapping terms (MATCH_LANGSUNG, CODICE_RINUMERATO, MATCH_CON_AGGREGAZIONE, BPS_ONLY). |
| `baliContext`   | Bali-specific advice. Areas, competition, tips, gotchas.    | This is where the real value lives. Be specific and practical.                                                         |
| `youllAlsoNeed` | Related codes as bullet list.                               | Format: `- CODE — Reason` per line. 3-5 related codes.                                                                 |
| `zantaraOpener` | Chat opener for the AI assistant.                           | One sentence, conversational, mentions the code number.                                                                |

## Tone Spectrum

| Situation                    | Tone                                      |
| ---------------------------- | ----------------------------------------- |
| Explaining what a code means | Friendly, clear, uses analogies           |
| Listing requirements         | Precise, structured, no ambiguity         |
| Describing 2020-2025 changes | Factual, references exact old codes       |
| Bali-specific context        | Opinionated, practical, insider knowledge |
| Zantara chat opener          | Warm, direct, action-oriented             |

## Source of Truth

All factual claims must be verifiable against:

- **`KBLI_2025_FINAL_CLEAN.json`** — codes, titles, descriptions, per_skala, status_mapping, pp28_sources, pma_status
- **BPS Regulation 7/2025** — the classification system itself
- **PP28/2024** — the risk-based licensing framework

Do NOT reference:

- Blog posts, forum discussions, or unofficial sources
- Outdated KBLI 2020 requirements (unless comparing to show what changed)
- Prices or fees (these change and must come from PricingTool)

## Adding New Gold Content

1. Look up the code in `KBLI_2025_FINAL_CLEAN.json`
2. Read EVERY field: `per_skala`, `status_mapping`, `pp28_sources`, `pma_status`, `pma_max_asing`, `pma_kondisi`
3. Write content following this guide
4. Have someone verify the factual claims against the source JSON
5. Add the entry to `lib/kbli-gold-content.ts`
