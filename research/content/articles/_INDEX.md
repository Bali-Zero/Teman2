---
date: 2026-06-21
domain: compliance
client_case: none
status: index — TIER 1 + TIER 2 (plan items 1-10) written
source_facts: apps/mouth/data/KBLI_2025_FINAL_CLEAN.json (1559 records, key kode_kbli_2025; l4_bali status verified per code)
moratorium: Gubernur letter B.27.000/642/PM/DPMPTSP, eff. 13 May 2026 — Bali blocks ALL low + medium-low risk KBLI for PMA, island-wide
---

# KBLI Articles — Index (Articles 1-10)

Voice: "Pragmatic Sherpa" (matches `research/content/book-chapters/ch-the-boutique-villa-55203.md`).
Every KBLI code + Bali status below was looked up in `KBLI_2025_FINAL_CLEAN.json` before being cited.
Ranges (not exact prices/days) used throughout. Each article closes with a soft CTA to the KBLI Navigator on balizero.com.

**Status legend (from `l4_bali.status` in FINAL_CLEAN):**
- `TERBUKA` (national `pma_status`) = open to foreign ownership nationally.
- `OK_or_HIGHER_RISK` = **registrable** in Bali (medium-high/high risk class survives the moratorium).
- `BLOCCATO_CLASSE_RISCHIO` = **blocked** in Bali (low/medium-low risk, caught by moratorium).
- `CHIUSO_PMA_NO_BESAR` = **blocked** in Bali (no large-scale OSS row → reserved for UMKM; a PT PMA cannot register).
- `CHIUSO_BALI` = **closed** to PMA in Bali (specific early closure, e.g. consulting 70209 from 28/1/2026).
- `CHIUSO_BALI_PROPOSTO` = **proposed** for closure (not yet blocked in OSS as of data date).
- `TERTUTUP` = **closed** outright (reserved for WNI / local operators, 0% foreign).
- `BLOCCATO_DIPENDE_SCOPE` = registrable **only by declaring the higher-risk scope**; verify live OSS per exact activity.

---

## TIER 1 — Hot / 2026 (the moratorium is the news)

### 01 — Your KBLI Is Open Nationally — and Blocked in Bali
File: `01-open-nationally-blocked-in-bali.md` · ~739 words · the flagship moratorium explainer.
| Code | Judul | National | Bali status | Verdict |
|---|---|---|---|---|
| 55203 | Aktivitas Vila | TERBUKA 100% | `CHIUSO_PMA_NO_BESAR` | BLOCKED (illustration) |

### 02 — The Villa Dream Has a New Wall (KBLI 55203)
File: `02-the-villa-dream-has-a-new-wall.md` · ~748 words.
| Code | Judul | National | Bali status | Verdict |
|---|---|---|---|---|
| 55203 | Aktivitas Vila | TERBUKA 100% | `CHIUSO_PMA_NO_BESAR` | BLOCKED |
| 55204 | Aktivitas Apartemen Hotel | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE (pivot) |
| 55400 | Aktivitas Jasa Intermediasi Akomodasi | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE (pivot) |

### 03 — The Virtual Office Is Dead for PMA in Bali
File: `03-the-virtual-office-is-dead-for-pma-in-bali.md` · ~695 words · domicile / substance-based inspection.
| Code | Judul | National | Bali status | Verdict |
|---|---|---|---|---|
| 55203 | Aktivitas Vila | TERBUKA 100% | `CHIUSO_PMA_NO_BESAR` | BLOCKED (illustration of domicile rule) |
| — | (virtual office BANNED as PMA domicile in Bali — per moratorium record, no specific KBLI) | — | — | — |

### 04 — Consulting in Bali: The First Door to Close (KBLI 70209)
File: `04-consulting-in-bali-the-first-door-to-close.md` · ~670 words.
| Code | Judul | National | Bali status | Verdict |
|---|---|---|---|---|
| 70209 | Konsultasi Manajemen dan Bisnis Lainnya | TERBUKA 100% | `CHIUSO_BALI` (closed 28/1/2026) | CLOSED |
| 70201 | Konsultansi Manajemen dan Bisnis Pariwisata | TERBUKA 100% | `CHIUSO_PMA_NO_BESAR` | BLOCKED |
| 70202 | Konsultansi Manajemen dan Bisnis Industri | TERBUKA 100% | `BLOCCATO_CLASSE_RISCHIO` | BLOCKED |
| 62201 | Konsultansi dan Manajemen Keamanan Siber | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE (IT alt) |
| 62209 | Konsultansi Komputer dan Manajemen Fasilitas Komputer Lainnya | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE (IT alt) |

### 05 — Pondok Wisata vs Villa: Why Foreigners Can't Own the Cheap One
File: `05-pondok-wisata-vs-villa.md` · ~669 words.
| Code | Judul | National | Bali status | Verdict |
|---|---|---|---|---|
| 55201 | Aktivitas Rumah Tinggal Sewa (Homestay / Pondok Wisata) | TERBUKA 100% | `TERTUTUP` | CLOSED (0% foreign, owner-resident) |
| 55203 | Aktivitas Vila | TERBUKA 100% | `CHIUSO_PMA_NO_BESAR` | BLOCKED |
| 55204 | Aktivitas Apartemen Hotel | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE (pivot) |

---

## TIER 2 — Evergreen by sector (real codes)

### 06 — The Beach Club Stack
File: `06-the-beach-club-stack.md` · ~666 words.
| Code | Judul | National | Bali status | Verdict |
|---|---|---|---|---|
| 56301 | Aktivitas Bar (uraian explicitly names "beach club") | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE |
| 56302 | Kelab Malam atau Diskotek (Nightclub/Discotheque) | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE |
| 56303 | Rumah Minum / Kafe (Cafe/Coffee Shop) | TERBUKA 100% | `BLOCCATO_CLASSE_RISCHIO` | BLOCKED |

### 07 — Real Estate in Bali: 68111 Is on the Chopping Block
File: `07-real-estate-68111-on-the-chopping-block.md` · ~666 words.
| Code | Judul | National | Bali status | Verdict |
|---|---|---|---|---|
| 68111 | Pengembangan Bangunan dan Lahan Hunian (residential development) | TERBUKA 100% | `CHIUSO_BALI_PROPOSTO` | PROPOSED for closure (not yet blocked) |
| 68210 | Jasa Intermediasi Real Estat (real estate intermediation) | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE |

### 08 — The Content Creator's Real KBLI in 2025
File: `08-the-content-creators-real-kbli-in-2025.md` · ~734 words · **explicitly flags 74149 as phantom/dead code.**
| Code | Judul | National | Bali status | Verdict |
|---|---|---|---|---|
| 74149 | — | — | **DOES NOT EXIST** | PHANTOM / DEAD CODE (absent from OSS ground-truth) |
| 59112 | Produksi Film, Video, dan Program Televisi oleh Swasta | TERBUKA 100% | `BLOCCATO_DIPENDE_SCOPE` | registrable only via higher-risk scope; verify live OSS |
| 60390 | Situs Jejaring Sosial dan Distribusi Konten Lainnya | TERBUKA 100% | `BLOCCATO_CLASSE_RISCHIO` | BLOCKED |
| 90200 | Aktivitas Seni Pertunjukan (performing arts) | TERBUKA 100% | `BLOCCATO_CLASSE_RISCHIO` | BLOCKED |

### 09 — Wellness & Aesthetics: One of the Open Doors — and a Hidden Wall (86105 vs 96220)
File: `09-wellness-and-aesthetics-an-open-door.md` · ~688 words.
| Code | Judul | National | Bali status | Verdict |
|---|---|---|---|---|
| 86105 | Aktivitas Klinik Swasta (private clinic) | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE |
| 96220 | Perawatan Kecantikan dan Perawatan Kecantikan Lainnya (beauty care) | TERBUKA 100% | `CHIUSO_PMA_NO_BESAR` | BLOCKED (no large-scale row) |

### 10 — Jewelry & Wholesale: Low-Risk = Blocked (46494)
File: `10-jewelry-wholesale-low-risk-equals-blocked.md` · ~684 words.
| Code | Judul | National | Bali status | Verdict |
|---|---|---|---|---|
| 46494 | Perdagangan Besar Perhiasan dan Jam (wholesale jewelry & watches) | TERBUKA 100% | `BLOCCATO_CLASSE_RISCHIO` (low-risk) | BLOCKED |

---

## Corrections made vs the editorial plan (fact-gated against FINAL_CLEAN)

1. **74149 (Art. 8) — CONFIRMED PHANTOM.** Absent from FINAL_CLEAN entirely. Article 8 explicitly buries it and gives the real 2025 codes (59112 / 60390 / 90200). Note: 59112's old 2020 codes were 62011/62012/62013/62015/62019 (per its `intel_2026.whatChanged`) — which is precisely why the plan's IT-code guesses below don't exist as 2025 codes.

2. **IT escape codes (Art. 12 prep) — ALL ABSENT, plan flagged correctly as UNVERIFIED.** None of 63122 / 62011 / 62019 (nor 62010 / 62021 / 62029 / 63111 / 63112 / 63121 / 58200) exist in KBLI 2025 — they were aggregated into newer 2025 codes. The REAL high-risk IT codes that PASS the Bali moratorium (`OK_or_HIGHER_RISK`, verified present) are: **62110** (game/software dev), **62191** (e-commerce app dev), **62199** (other computer programming), **62201** (cybersecurity consulting), **62202** (digital identity), **62203** (electronic certificates), **62209** (computer/IT-facilities consulting), **63101** (data processing), **63102** (hosting/cloud infrastructure). IT traps that are BLOCKED (low-risk): 62193 (blockchain), 62194 (AI components), 62204 (IoT), 62900 (other IT services), 95101 (computer repair). These are documented here for whoever writes Article 12 next.

3. **96220 beauty care (Art. 9) — CORRECTED from plan.** The plan listed both 86105 and 96220 as "OK_or_HIGHER_RISK." FINAL_CLEAN shows **96220 is BLOCKED** (`CHIUSO_PMA_NO_BESAR` — no large-scale row). Only 86105 (clinic) is registrable. Article 9 was written around this clinical-vs-cosmetic split (the correction is the article's whole point).

4. **55203 villa (Arts. 1/2/3/5) — mechanism refined.** The book chapter frames 55203 as a generic low/medium-low-risk moratorium victim. FINAL_CLEAN shows the precise mechanism is `CHIUSO_PMA_NO_BESAR` (no Usaha Besar scale row → reserved for UMKM). Practical outcome is identical ("a PT PMA cannot register a villa in Bali"); articles state the accurate mechanism.

5. **55201 pondok wisata (Art. 5) — status confirmed `TERTUTUP`.** The plan flagged it "TERTUTUP_CANDIDATE (verify)." Verified: it is `TERTUTUP` (closed, reserved for local operators, owner-resident requirement). Article 5 written accordingly, and notes the nominee workaround is now criminalised.

6. **56303 café (Art. 6) — confirmed BLOCKED; 56301 Bar & 56302 Nightclub confirmed REGISTRABLE.** Bonus verified fact: 56301's `uraian` literally lists "beach club" — used as the anchor of Article 6.

7. **70209 consulting (Art. 4) — confirmed `CHIUSO_BALI` from 28/1/2026** (the early, pre-moratorium closure). Neighbours 70201/70202 also blocked. IT-consulting alternatives 62201/62209 verified registrable.

## Codes still FLAGGED for the parent to double-check
- **59112** (`BLOCCATO_DIPENDE_SCOPE`): registrable in Bali ONLY by declaring the higher-risk scope. Article 8 states this as conditional and tells the reader to verify the live OSS status of their exact activity. Parent: confirm the higher-risk scope is genuinely available for a foreign producer before this is treated as an "open" route.
- **68111** (`CHIUSO_BALI_PROPOSTO`): status is *proposed*, time-sensitive. If the proposal lands as a hard block, Article 7's "not yet blocked" framing needs a one-line update.
- **Article 12 (IT escape route)** is NOT in this batch (items 1-10 only) but its real codes are documented in Correction #2 above for the next writer — the plan's flagged codes were all confirmed absent.

---

## Batch 2 (11-20)

Plan items 11-20 — TIER 2 closer (11-12) + TIER 3 structural/mindset (13-20). Same "Pragmatic Sherpa" voice, hook opening, soft Navigator CTA close, frontmatter (date 2026-06-21, domain compliance, kbli_codes cited+verified). Every code + status looked up in `KBLI_2025_FINAL_CLEAN.json` (1,559 records) before citing — never from memory. Ranges (not exact prices) throughout. ~600-800 words each.

### 11 — Minimarket Is Closed to Foreigners
File: `11-minimarket-closed-to-foreigners.md` · ~667 words · retail reserved for WNI.
| Code | Judul | National | Bali status | Verdict |
|---|---|---|---|---|
| 47111 | Perdagangan Eceran ... Swalayan (minimarket, food-dominant) | TERBATAS (0%) | `TERTUTUP` | CLOSED (triple-locked: national 0% + provincial + moratorium) |
| 47112 | Perdagangan Eceran ... (non-food-dominant, dept-store) | TERBUKA 100% | `TERTUTUP` | CLOSED (national-open but Bali-closed — clean illustration) |
| 47191 | Perdagangan Eceran Berbagai Macam Barang Lainnya | TERBUKA 100% | `BLOCCATO_CLASSE_RISCHIO` | BLOCKED |
| 47711 | Perdagangan Eceran Pakaian | TERBUKA 100% | `BLOCCATO_CLASSE_RISCHIO` | BLOCKED |

### 12 — The IT Escape Route
File: `12-the-it-escape-route.md` · ~694 words · the IT codes that PASS the moratorium, and the traps that don't. **Uses the REAL 2025 codes (the plan's 63122/62011/62019 are absent — corrected per batch-1 _INDEX Correction #2).**
| Code | Judul | National | Bali status | Verdict |
|---|---|---|---|---|
| 62110 | Pengembangan Video Gim / software | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE |
| 62191 | Pengembangan Aplikasi Perdagangan via Internet | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE |
| 62199 | Pemrograman Komputer Lainnya YTDL | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE |
| 62201 | Konsultansi & Manajemen Keamanan Siber | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE |
| 62202 | Penyediaan & Pengelolaan Identitas Digital | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE |
| 62203 | Penyediaan Sertifikat Elektronik & Jasa Terkait | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE |
| 62209 | Konsultansi Komputer & Manajemen Fasilitas Komputer | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE |
| 63101 | Pengolahan Data | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE |
| 63102 | Infrastruktur Komputasi, Hosting/Cloud | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE |
| 62193 | Pengembangan Aplikasi Blockchain | TERBUKA 100% | `BLOCCATO_CLASSE_RISCHIO` | BLOCKED (trap) |
| 62194 | Pengembangan Komponen Dasar AI | TERBUKA 100% | `BLOCCATO_CLASSE_RISCHIO` | BLOCKED (trap) |
| 62204 | Konsultansi & Perancangan IoT | TERBUKA 100% | `BLOCCATO_CLASSE_RISCHIO` | BLOCKED (trap) |
| 62900 | Jasa Teknologi Informasi & Komputer Lainnya | TERBUKA 100% | `BLOCCATO_CLASSE_RISCHIO` | BLOCKED (trap) |
| 95101 | Reparasi & Pemeliharaan Komputer | TERBUKA 100% | `BLOCCATO_CLASSE_RISCHIO` | BLOCKED (trap) |

### 13 — PT PMA vs Nominee: The Math of the Bet
File: `13-pt-pma-vs-nominee-the-math-of-the-bet.md` · ~747 words · the honest, unbounded-downside math of nominee structures (void agreements + criminal/immigration exposure). No fabricated statute — frames the Investment/Agrarian-Law voidness + enforcement spotlight.
| Code | Judul | National | Bali status | Verdict |
|---|---|---|---|---|
| 55203 | Aktivitas Vila | TERBUKA 100% | `CHIUSO_PMA_NO_BESAR` | BLOCKED (the activity people try to nominee) |
| 55201 | Aktivitas Rumah Tinggal Sewa (Pondok Wisata) | TERBUKA 100% | `TERTUTUP` | CLOSED |

### 14 — Risk Class Is Destiny in Bali Now
File: `14-risk-class-is-destiny-in-bali-now.md` · ~674 words · how the OSS risk class (Rendah → Tinggi) at *Besar* scale decides Bali registrability. The moratorium line = blocks Rendah + Menengah Rendah.
| Code | Judul | National | Bali status | Verdict |
|---|---|---|---|---|
| 62110 | Pengembangan Video Gim | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE (Besar-scale risk rises to Menengah Tinggi — verified in per_skala) |
| 56301 | Aktivitas Bar | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE |
| 56303 | Rumah Minum/Kafe | TERBUKA 100% | `BLOCCATO_CLASSE_RISCHIO` | BLOCKED (low-risk) |
| 46494 | Perdagangan Besar Perhiasan dan Jam | TERBUKA 100% | `BLOCCATO_CLASSE_RISCHIO` | BLOCKED (low-risk) |
| 86105 | Aktivitas Klinik Swasta | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE |

### 15 — Paid-Up vs Investment: The Rp 10bn Myth
File: `15-paid-up-vs-investment-the-rp-10bn-myth.md` · ~789 words · separates *nilai investasi* (total investment plan, land/building historically excluded) from *modal disetor* (paid-up capital). Permeninves 5/2025 framed as evolving, per-KBLI/per-location — RANGES not exact figures, no invented numbers.
| Code | Judul | National | Bali status | Verdict |
|---|---|---|---|---|
| 55204 | Aktivitas Apartemen Hotel | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE (capital-heavy illustration) |
| 62199 | Pemrograman Komputer Lainnya YTDL | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE (capital-light illustration) |

### 16 — The Banjar Is the Real Authority
File: `16-the-banjar-is-the-real-authority.md` · ~706 words · three authority layers (national / provincial+RTRW-ITR / adat-banjar), green-zone (jalur hijau) zoning trap, social licence. Structural — no new codes asserted; 55203/56301 used illustratively.
| Code | Judul | National | Bali status | Verdict |
|---|---|---|---|---|
| 55203 | Aktivitas Vila | TERBUKA 100% | `CHIUSO_PMA_NO_BESAR` | BLOCKED (illustration: even a build must clear zoning + banjar) |
| 56301 | Aktivitas Bar | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE on paper, still subject to zoning + local consent |

### 17 — TKA: Can You Hire (or Be) the Foreign Worker?
File: `17-tka-can-you-hire-or-be-the-foreign-worker.md` · ~739 words · RPTKA gateway, permitted vs reserved positions (HR closed to foreigners), KITAS work permit flows from RPTKA, owner ≠ working-worker distinction. No KBLI-specific TKA data in FINAL_CLEAN (only 2 records mention TKA) — leans on the regulatory frame; 62199/55204 used as illustrative employer codes.
| Code | Judul | National | Bali status | Verdict |
|---|---|---|---|---|
| 62199 | Pemrograman Komputer Lainnya YTDL | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE (tech employer — foreign engineers easier to justify) |
| 55204 | Aktivitas Apartemen Hotel | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE (hospitality employer — foreign chef/GM) |

### 18 — How to Read a KBLI Like a Pro
File: `18-how-to-read-a-kbli-like-a-pro.md` · ~715 words · educational — judul vs uraian vs ruang lingkup, using the REAL OSS 56301 record (its uraian literally lists "beach club" + the "primarily serves drinks" line that splits Bar from Café).
| Code | Judul | National | Bali status | Verdict |
|---|---|---|---|---|
| 56301 | Aktivitas Bar (worked example: judul/uraian/ruang lingkup="Seluruh") | TERBUKA 100% | `OK_or_HIGHER_RISK` | REGISTRABLE |
| 56303 | Rumah Minum/Kafe (the neighbour the uraian distinguishes) | TERBUKA 100% | `BLOCCATO_CLASSE_RISCHIO` | BLOCKED |

### 19 — What Changed from KBLI 2020 to 2025
File: `19-what-changed-from-kbli-2020-to-2025.md` · ~798 words · four status_mapping classes (MATCH_LANGSUNG 926 / CODICE_RINUMERATO 264 / MATCH_CON_AGGREGAZIONE 194 / BPS_ONLY 174). Concrete retired-code example: **74149 (phantom, absent) → its successors are the 74111–74199 design family, with 74199 the "other design" catch-all (itself CHIUSO_PMA_NO_BESAR in Bali)**; concrete renumbering: **55193 → 55203** (villa, 100% PP28 match, from `whatChanged`).
| Code | Judul | National | Bali status | Verdict |
|---|---|---|---|---|
| 74149 | — | — | **DOES NOT EXIST** | PHANTOM / RETIRED |
| 74199 | Aktivitas Desain Khusus Lainnya YTDL (real "other design" bucket) | TERBUKA 100% | `CHIUSO_PMA_NO_BESAR` | BLOCKED |
| 55193 | — (2020 villa code) | — | **DOES NOT EXIST as 2025 code** | RENUMBERED → 55203 |
| 55203 | Aktivitas Vila | TERBUKA 100% | `CHIUSO_PMA_NO_BESAR` | BLOCKED (the renumbering target) |

### 20 — The Honest Map: ~30% of Bali Business Codes Are Blocked for PMA
File: `20-the-honest-map-blocked-bali-codes.md` · ~796 words · data-journalism. **Measured count, not the plan's 945/39%.**
- **MEASURED: 465 of 1,559 classified codes have `l4_bali.blocked == true` → 29.83% (just under one in three).** Computed by counting `blocked==true` across all 1,559 records in FINAL_CLEAN.
- Breakdown of the 465: `BLOCCATO_CLASSE_RISCHIO` 373 · `NEEDS_REVIEW_NO_OSS_SCOPE` 63 · `CHIUSO_PMA_NO_BESAR` 20 · `TERTUTUP` 8 · `CHIUSO_BALI` 1.
- The 1,094 NOT-blocked: `OK_or_HIGHER_RISK` 1014 · `BLOCCATO_DIPENDE_SCOPE` 70 (registrable only via higher-risk scope) · `TERBATAS` 5 · `CHIUSO_BALI_PROPOSTO` 5.
- Article explains the discrepancy publicly: the plan's "945/39%" came from the larger 2,422-row OSS export (multiple scope/sub-scale rows per code, inflating both numerator and denominator); counting at one-verdict-per-business-code (1,559) gives the defensible 465/29.8%.

## Corrections / measurements made in Batch 2 (fact-gated against FINAL_CLEAN)

1. **Article 20 blocked-count — CORRECTED from plan's 945/39% to MEASURED 465/29.83%.** The plan's figure counted the 2,422-row OSS scope-level export; FINAL_CLEAN holds 1,559 one-verdict-per-code records, of which exactly 465 are `l4_bali.blocked==true`. Article 20 reports the measured 29.8% and explains the discrepancy in-text (per the "verify, don't presume" mandate). The two figures describe the same structural reality; 29.8% is the one defensible code-by-code.

2. **Article 12 IT codes — used the REAL 2025 codes per batch-1 Correction #2.** All 9 pass-codes (62110/62191/62199/62201/62202/62203/62209/63101/63102) re-verified `OK_or_HIGHER_RISK` and all 5 trap-codes (62193/62194/62204/62900/95101) re-verified BLOCKED in this batch. The plan's 63122/62011/62019 confirmed ABSENT.

3. **Article 19 — 74149→74199 framing refined.** 74149 confirmed ABSENT (phantom). The literal "74149 → 74199" mapping the prompt suggested is approximate: 74149's design-services family was reorganised into the 74111–74199 block, with **74199 ("Aktivitas Desain Khusus Lainnya") as the real surviving "other design" catch-all**. 74199's own `whatChanged` is MATCH_LANGSUNG (not itself renumbered), so the article presents it as "where the dead 74149's activity now lives" rather than a strict 1:1 renumber. The clean CODICE_RINUMERATO example used instead is **55193 → 55203** (villa, verbatim from `whatChanged`, 100% PP28 match). Note: 74199 is itself `CHIUSO_PMA_NO_BESAR` (blocked for PMA in Bali) — stated in the article.

4. **Articles 15 & 17 — no fabricated numbers.** FINAL_CLEAN carries almost no TKA/RPTKA or investment-threshold data (2 TKA mentions, 10 Rp-10bn-ish mentions across 1,559 records). Both articles therefore frame the regime (Permeninves 5/2025 investment plan vs paid-up capital; RPTKA + permitted positions) qualitatively with RANGES and "evolving / per-code / per-location" caveats — no invented exact figures or invented statutes.

5. **47112 — verified TERBUKA national but TERTUTUP in Bali.** Used in Article 11 as the cleanest "national-open ≠ Bali-registrable" retail illustration (its sibling 47111 is national TERBATAS 0% + Bali TERTUTUP — "triple-locked" per its `baliContext`).
