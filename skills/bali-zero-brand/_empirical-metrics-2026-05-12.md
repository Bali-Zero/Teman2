# Empirical IG Metrics — Bali Zero @balizero0
**Date captured**: 2026-05-12
**Source**: Antonello manual paste from IG Insights tab (Meta Business Suite)
**Account**: @balizero0 (~10K followers at capture date)
**Sample**: 7 top-performing carouseli selected by Antonello as reference set
**Purpose**: ground-truth dataset for `wr2-image-prompt-author`, `wr2-storyboarder`, `wr2-critic`, `wr2-ig-metrics-analyst`. Replaces guesswork with evidence.

---

## Raw dataset

| Post slug | Likes | Comments | Shares | Saves | Views | Reach | Engaged | Follows | %Non-fol reach | From Home | From Explore | From Other | From Profile |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **traffic** (Kerobokan Kelod) | 289 | 67 | 259 | 70 | 43,068 | 23,672 | 592 | 68 | 86% | 36,964 | 2,972 | 1,216 | — |
| **villa_ota** (Airbnb/OTA rules) | 174 | 14 | 468 | 382 | 26,144 | 13,276 | 847 | 109 | 80% | 23,408 | — | 7 | 1,541 |
| **37k_villa** (oversupply) | 402 | 32 | 816 | 450 | 72,472 | 47,077 | 1,362 | 272 | 91% | 54,391 | — | 10 | 1,213 |
| **bali_flood** (farmland ban) | 568 | 88 | 134 | 47 | 29,536 | 14,407 | 717 | 18 | 70% | 15,787 | 3,072 | 2,072 | — |
| **cepaka** (2vs7 floors) | 60 | 4 | 83 | 37 | 6,218 | 3,136 | 151 | 21 | 52% | 5,685 | — | 460 | 73 |
| **mangrove** ($7B zone) | 893 | 61 | 552 | 192 | 39,586 | 25,218 | 1,351 | 144 | 85% | 30,907 | — | 8,348 | 331 |
| **respect** (Gub Bali rules) | 146 | 2 | 17 | 22 | 9,916 | 3,696 | 181 | 2 | 15% | 7,673 | — | 43 | 1,239 |
| **trash** (license-env risk) [ADDED 2026-05-12] | 30 | 0 | 30 | 10 | 3,254 | 1,422 | 61 | 0 | 21% | 3,146 | — | 85 | 23 |

**Update 2026-05-12 (post-pipeline-rules-merge)**: TRASH post published 2026-05-11, captured 2026-05-12 18:25 WITA. First post captured AFTER Article 14 subset merge but the post itself was produced PRE-merge (no Art 14 enforcement). Added as 8th data point + diagnostic case study below.

---

## Derived ratios (the metrics that matter)

| Post | Save/Like | Share/Like | Engaged/Reach | Follows/1K reach | Verdict |
|---|---:|---:|---:|---:|---|
| **villa_ota** | **2.20** 🚀 | **2.69** 🚀 | **6.38%** 🚀 | 8.21 | **S-pattern gold** — utility content magnet |
| **37k_villa** | 1.12 | 2.03 🚀 | 2.89% | **5.78** 🚀 | **V-pattern gold** — viral analysis |
| **mangrove** | 0.21 | 0.62 | 5.36% | 5.71 | 🟢 emotional + scale shock |
| **traffic** | 0.24 | 0.90 | 2.50% | 2.87 | 🟡 social commentary, shareable |
| **cepaka** | 0.62 | 1.38 | 4.81% | 6.69 | 🟡 low volume but decent ratios |
| **trash** | 0.33 | **1.00** | 4.29% | **0** 🔴 | 🟡 **soft-performer engaging-not-actionable** (see §below) |
| **bali_flood** | 0.08 | 0.24 | 4.97% | 1.25 | 🔴 likes-only, low utility |
| **respect** | 0.15 | 0.12 | 4.90% | 0.54 | 🔴 follower-only, no spread |

**Thresholds for "good carousel" (derived empirically):**
- `Save/Like ≥ 0.5` = utility content (target this for regulatory/visa/tax/property)
- `Share/Like ≥ 0.5` = social currency (target this for news/comparison archetypes)
- `Engaged/Reach ≥ 5%` = quality threshold
- `Follows/1K reach ≥ 3` = growth ROI threshold
- **NEW 2026-05-12 (TRASH case)**: `Share/Like ≥ 1 AND Save/Like < 0.5` = **engaging-not-actionable pattern** — body lacks consequence + actionable next step (Art 6.9 S-pattern soft fail)

---

## Soft-performer pattern: engaging-not-actionable (added 2026-05-12 after TRASH post)

The TRASH post (`NOT TAX. NOT VISA. TRASH — WASTE CAN SHUT DOWN YOUR BALI BUSINESS`) is the first carousel that scores **mid on shares but low on saves and zero on follows**. Distinct pattern from the 7 prior data points.

**Symptom**: `Share/Like = 1.0` (people forward it) BUT `Save/Like = 0.33` (people don't bookmark) AND `follows = 0` AND `non-fol reach = 20.7%` (IG didn't push to Explore).

**Root cause hypothesis** (to validate by retro-applying Article 14 + S-pattern audit):

1. **Cover is excellent** (Art 14.4 informal — license-risk-stamp acts as regulation-badge; Art 5.8.1 Tier 1 provocation-photo; Art 6.9 anchors 4 + 5 present). The cover earns the share.

2. **Body fails S-pattern**:
   - Likely missing **specific consequence** (no Rupiah penalty amount, no concrete enforcement story)
   - Likely missing **actionable next step** (no "verify your TPS3R coverage" / "check Perda Bali waste compliance Q2 2026" / specific helpline)
   - Likely missing **regulatory citation verbatim** (the topic begs for PP 22/2021 Limbah B3 or Perda Bali Sampah — neither visible in available data)

3. **Caption likely under-engineered**:
   - 0 comments = no provocation/question to spark thread
   - 1 external link tap = no compelling CTA + link in bio
   - 20.7% non-fol = caption hashtags too generic (#bali #business) or absent

**Diagnostic value**:

This is the **first carousel processed by our new measurement framework where the cover-vs-body asymmetry is measurable end-to-end**. Earlier 7 posts were curated as "top performers" (Antonello hand-picked best); TRASH is captured as **just-published, performance-as-found** — closer to typical production output baseline.

**Implications for storyboarder + critic**:

- Storyboarder MUST enforce S-pattern (rule + consequence + action) for environmental/regulatory carouseli, not just tax/visa. **Environmental compliance** is a new domain category empirically lacking guidance.
- Critic Rubric 5 check 5.2 (S-pattern body) should flag soft-fail when share/like > 1 AND save/like < 0.5 in retrospective analysis (currently checks structure-level; this is performance-level signal).
- Caption template needs review: hashtag-strategy + 1-line provocation-question were probably absent. Out of scope for WR2 storyboarder (it produces slides only), but adjacent system (caption-author?) deserves attention.

**Counter-hypothesis to test**: maybe the topic itself has a small audience ceiling. Bali waste/license-environmental is a niche-of-niche even for investors. Need to compare against another environmental post if Bali Zero has one in archive. **Action**: scrape past 30-day @balizero0 history for environmental-domain carouseli.

**Action items**:

1. ✅ Added to empirical dataset row
2. ☐ Open post on IG, screenshot caption + hashtags + slide 2 → audit retroactively
3. ☐ Add `environmental` as 5th category in `_empirical-metrics` next revision
4. ☐ wr2-storyboarder.md: add explicit environmental-compliance S-pattern guidance
5. ☐ wr2-critic.md Rubric 5.2: extend retro-analysis hook (consume `_empirical-metrics` performance data when available, not just structural check)


---

## Pattern S — Utility content (Saves > Likes)

Carouseli che insegnano una regola pratica con conseguenza monetaria diretta.

**Top performers**: `villa_ota` (Airbnb/OTA license rules), `37k_villa` (oversupply analysis)

**Common structure**:
- **Cover headline**: concrete number + categorical verdict
  - `37,881 villas for rent / SAME POOL. SAME DESIGN. SAME PROBLEM.`
- **Audience targeted**: investor / business operator (NOT local Indonesian, NOT culture tourist)
- **Body slides**: rule → consequence → actionable next step
- **Image style**: aerial drone documentary (high above, full scene)
- **Tone register**: analitico + militante hybrid

**Required ingredients** (storyboarder MUST produce all):
1. A specific number or named regulation in the cover headline
2. A consequence stated in plain words (monetary, legal, operational)
3. An implicit "what should YOU do about this" thread through body slides
4. Optional: an explicit elegant-close CTA

## Pattern V — Viral spread (Shares > Likes)

Carouseli che la gente manda ad altri perché "devi sapere questo".

**Top performers**: `37k_villa` (816 shares), `mangrove` (552 shares), `villa_ota` (468 shares), `traffic` (259 shares)

**Common structure**:
- **Cover claim**: number-shock + moral/causal verdict
  - `Bali Shuts Down a $7B Investment Zone / MANGROVES VS. MEGA-PROJECT — MANGROVES WON`
- **Distribution**: NOT via Explore push — via FOLLOWER-TO-DM-SHARE
  - `mangrove` got 8,348 views from "From Other" = DMs/saves shared peer-to-peer
  - `37k_villa` got 99.97% from Home — IG showed it only to followers, but they SHARED it
- **Image style**: aerial drone (37k_villa, mangrove) or dramatic ground-level documentary (traffic)

**Lesson**: design for SHARE-BY-FOLLOWER, not for Explore algorithm push.

## Anti-pattern A1 — Surreal/abstract metaphor (EMPIRICALLY PENALIZED)

`cepaka` (man with floating melted blueprint, Dalí-style) = **lowest volume of the 7** (60 likes, 6,218 views).

Confirms that **surreal/abstract/conceptual visuals are penalized** vs documentary photoreal aerial.

**Banned for cover slides (effective 2026-05-12)**:
- Surreal Dalí-style figures
- Melted/floating/distorted objects
- Wax seal + parchment + scroll (template trap S11)
- Abstract geometric shattering
- Lucchetto, chiave, lock-and-key metaphors
- Painterly/illustrated style

## Anti-pattern A2 — Cultural/local without investor implication

`respect` ("Things you can't do in Bali") = 0% Explore push, 85% reach within followers, 2 new follows. Beautiful image (line of Balinese raising hands) but **no actionable investor implication**.

**Lesson**: Bali Zero IG audience is **expat/investor/digital-nomad**, NOT cultural tourist. Pure-cultural content gets liked but doesn't convert. If a topic must be cultural, MUST be tied to:
- A rule change affecting expats
- A market-impact angle
- A "what this means for your business" thread

---

## Empirical ranking of 9 image-style modes (Article 5.8)

Re-rank by performance evidence:

| Tier | Style mode | Evidence |
|---|---|---|
| **Tier 1 (use freely)** | aerial-drone documentary | 37k_villa, mangrove, traffic — top 3 reach |
| **Tier 1 (use freely)** | ground-documentary realism | bali_flood, respect, villa_ota — high engagement |
| **Tier 2 (use selectively)** | weather-atmospheric | bali_flood (rain composition) — top likes |
| **Tier 2 (use selectively)** | market-scene | not in sample, retained for visa/business contexts |
| **Tier 3 (rare, justified only)** | ritual object Balinese | respect uses it — low spread |
| **Tier 3 (rare, justified only)** | editorial portrait | cepaka uses it — lowest performer |
| **Tier 3 (rare)** | chiaroscuro photography | not in sample |
| **Tier 4 (BANNED for cover)** | abstract geometric | cepaka adjacent — empirically penalized |
| **Tier 4 (BANNED for cover)** | surreal / Dalí-style | cepaka — clearest penalty |

---

## Headline rules (empirically validated, refined 2026-05-12)

Effective immediately for `wr2-storyboarder`:

1. **Cover heading + subhead together MUST carry ≥1 of 6 empirical anchors**:
   1. Concrete number (`37,881`, `$7B`, `25%`)
   2. Regulation / code (`KEP-71/PJ/2026`, `Permenkumham 22/2023`)
   3. Specific Indonesian location (`KEROBOKAN`, `UBUD`, `BADUNG`)
   4. Categorical verdict (`MANGROVES WON`, `BANS`, `RESCINDED`, `SHUTS DOWN`)
   5. Editorial contrast / parallelism (`TWO BOYS. TWO FAITHS. ONE ISLAND.`, `SAME POOL. SAME DESIGN. SAME PROBLEM.`)
   6. Time-specific event (`AFTER THE SEPTEMBER 10TH FLOODS`, `DECEMBER 30, 2025`, `Q1 2026`)
   - Zero anchors = `respect` outcome (low spread). The fix is NOT "force a number" if topic has none — pick a different anchor type.
2. **Body slides MUST teach 1 rule + 1 consequence + 1 next step** (S-pattern). Critic to enforce.
3. **Bilingual lexicon only on first occurrence** (Article 6.2 already in constitution). Top performers respect this.

---

## How to use this file

- **`wr2-image-prompt-author`**: read tier ranking before authoring prompts. For cover slides ALWAYS choose Tier 1. NEVER use Tier 4 vocabulary.
- **`wr2-storyboarder`**: read headline rules. Refuse to emit a cover without concrete number + verdict.
- **`wr2-critic`**: score against thresholds (Save/Like, Share/Like, Engaged/Reach). Soft-fail any carousel that predicts <2% engaged-rate based on its design (no number → no spread → predict <2%).
- **`wr2-ig-metrics-analyst`**: read this file as baseline. New carouseli get compared against these 7 empirical anchors when computing weekly amendments.

---

## Maintenance

This file is appended-only. When new carouseli get ≥1 week of IG metrics and clear the bar (Save/Like ≥ 0.5 OR Share/Like ≥ 0.5), `wr2-ig-metrics-analyst` adds a row to the dataset and updates the derived ratios + tier ranking.

Last manual update: 2026-05-12 by Antonello (paste from IG Insights).
