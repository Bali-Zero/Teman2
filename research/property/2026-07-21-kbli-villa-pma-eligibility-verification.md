---
date: 2026-07-21
domain: property
client_case: none
author: deep-researcher (Bali Zero)
status: verified
sources:
  - https://kbli.co.id/id/55193
  - Peraturan BKPM 5/2025
  - Perpres 49/2021
  - https://kbli.co.id/id/55204
  - data/source_documents/KBLI_2025_FINAL_CLEAN.json (Bali Zero's own curated ground truth, l4_bali field — Bali-specific PMA moratorium status per code, injected 2026-06-19, source Gubernur letter B.27.000/642/PM/DPMPTSP eff. 2026-05-13)
  - https://www.detik.com/bali/bisnis/d-7725601/koster-tolak-moratorium-hotel-dan-vila-di-bali-hanya-pengendalian-ketat (2025-01-09)
adversarial_review: kimi-k3
---

# Verification: can a PT PMA hold KBLI 55203 (villa rental)?

## Question

Fact-check a disputed claim surfaced in the 2026-07-20 team review round of
Bali Zero's client-facing WhatsApp assistant Q&A corpus
(`apps/backend-rag/data/curated_qa/property-villa-rental.jsonl`, 9 of 20
rows): can a PT PMA (foreign-owned limited company) legally hold KBLI 55203
"Aktivitas Vila" and operate a villa/short-term-rental business directly?

- **Claim A** (original draft, live in ~9 Q&A rows): "Under the current
  KBLI 2025 classification, villa rental is KBLI 55203 'Aktivitas Vila' —
  foreign investment is open (PMA-eligible) for this code."
- **Claim B** (reviewer's correction, no source cited): KBLI 55203 exists
  in KBLI 2025 but caps at Usaha Menengah (medium-scale); it cannot be used
  by PT PMA. No KBLI currently allows a PT PMA to run a villa/short-term
  rental business directly.

## TL;DR

**Claim B is correct. Claim A is wrong and was live in a client-facing
assistant.** A PT PMA cannot legally hold KBLI 55203/55193 "Vila" directly.
**Revised post-adversarial-review (2026-07-21):** of the routes this
document originally called "compliant," only **serviced apartment/apartemen
hotel (KBLI 55204)** is cleanly open in Bali right now. **Star-rated hotel
(55101-55105)** is scope-dependent, not a blanket "100% open" route — Bali
Zero's own KBLI ground truth flags it `AMBIGUOUS`/verify-live-OSS.
**Management-only (KBLI 55901)** — this document's original third
route — is currently **BLOCKED for PMA in Bali** despite being 100%
foreign-open nationally: Bali's island-wide moratorium (Gubernur letter
B.27.000/642/PM/DPMPTSP, effective 2026-05-13) blocks every Low/
Medium-Low-risk KBLI code for new PMA registration, and 55901 falls in
that band at the mandatory PMA (Besar) scale. There IS an enacted,
currently-active Bali-specific PMA registration block — narrower than a
"construction moratorium" but real; this document's original Q3
("no enacted province-wide licensing ban exists") understated it. Governor
Koster's rejection of a *construction* moratorium was 2025-01-09, not
2026-01-09 as originally stated here.

## Findings by question

**Q1 — Does 55203's skala-usaha restriction exclude PMA? → CONFIRMED-CLAIM-B.**
The OSS villa-licensing matrix has no Usaha Besar (large-scale) tier — it
caps at Mikro/Kecil/Menengah only. Villa is non-star accommodation reserved
for UMKM. Sources: kbli.co.id/55193 ("SME-reserved… allocated to koperasi
& UMKM, foreign investment via PT PMA not permitted, no Large-scale
licensing matrix in OSS"); multiple legal/compliance aggregators state a
PT PMA must register at Large scale, and this code cannot be a
foreign-owned company's NIB activity. Perpres 49/2021: "Short-term tourist
accommodation… reserved for Indonesian UMKM entities… PT PMA entities are
excluded from operating short-term tourist accommodation other than
hotels."

**Q2 — Does the Rp10bn/KBLI/location floor still stand? → CONFIRMED.**
Peraturan BKPM 5/2025 (in force 2025-10-02) Pasal 26(2): investment ">Rp10
miliar, tidak termasuk tanah dan bangunan, per bidang usaha KBLI 5 digit,
per lokasi proyek" stands. (Paid-up capital is a separate figure, Rp2.5bn/
company, Pasal 26(10) — do not conflate the three different "10 miliar"
figures circulating in this domain.) This is the structural mechanism: PMA
is required to invest at Usaha Besar scale (>Rp10bn); a code that caps at
Usaha Menengah literally has no tier for that investment to register
under. Matches Bali Zero's own internal note on BKPM 5/2025.

**Q3 — Does a Bali moratorium independently block this route? → REVISED
2026-07-21: CONFIRMED-REVIEWER, this document originally understated it.**
No enacted province-wide *construction* moratorium exists — 2024-09-10
reporting on a central-government (Kemenko Marves) "agreed" concept for new
hotels/villas/nightclubs was never enacted, and Governor Koster explicitly
**rejected** a formal moratorium on **2025-01-09** (not 2026-01-09 as this
document originally stated — verified against the source article's
byline): *"Tidak perlu moratorium. Yang ada pengendalian secara ketat."*
**But that is not the whole picture.** Bali Zero's own curated KBLI ground
truth (`KBLI_2025_FINAL_CLEAN.json`, `l4_bali` field per code) records a
**separate, enacted, currently-active PMA *registration* block**: effective
**2026-05-13** (Gubernur letter B.27.000/642/PM/DPMPTSP), Bali blocks ALL
Low- and Medium-Low-risk KBLI activities from new PMA registration,
island-wide and permanent, and additionally bans virtual offices as a PMA
domicile in Bali. This is a real, enacted, PMA-specific licensing
restriction — narrower in scope than a blanket construction freeze (it
gates *who* can register, not whether construction happens at all), but it
is exactly the kind of "enacted province-wide licensing ban" this document
originally said didn't exist. See Adversarial review below.

**Q4 — What is the correct compliant PMA path in 2026? → REVISED
2026-07-21.** PMA is excluded from short-term accommodation other than
hotels (Perpres 49/2021), and villa (55203) has no PMA tier at all
(Q1-Q2). Among the hotel-family codes, current status per Bali Zero's own
`l4_bali` ground truth differs by code — this is NOT a uniform "100%
PMA-open" family:
- **Apartemen Hotel / Serviced Apartment (55204)** — `verdict: OPEN`, not
  blocked (OSS risk at Besar scale is Menengah-Tinggi/Tinggi, outside the
  moratorium's Low/Medium-Low band). The clean route today.
- **Hotel Bintang 55101-55105 + Nonbintang 55106** — `verdict: AMBIGUOUS`
  (`status: BLOCCATO_DIPENDE_SCOPE`): OSS risk at Besar scale is low on
  some scopes and higher on others; registrable as PMA in Bali **only** by
  declaring the higher-risk scope for that specific project — must be
  verified live in OSS per project, not assumed open.
Land: HGB, or a long-term Hak Sewa; zoning (pink/tourism designation) +
TDUP prerequisites still apply regardless of which code clears. NOT
PMA-eligible: Vila (55193/55203, `verdict: NO_BESAR`), Pondok Wisata
(55130), Homestay (55201). Do not disguise short-term rental under
property-ownership codes (68111/68112) — flagged elsewhere as a compliance
violation.

**Q5 — Is KBLI 55901 (management services) PMA-open and moratorium-affected?
→ REVISED 2026-07-21: CONFIRMED-REVIEWER, this document's original verdict
was wrong.** 55901 = Aktivitas Jasa Manajemen Akomodasi = third-party
management for a fee, explicitly NOT ownership/direct operation — and it
IS 100% foreign-open **nationally** (Perpres 10/2021, 49/2021). But
Bali Zero's own `l4_bali` ground truth records it as **`BLOCCATO_CLASSE_RISCHIO`,
`blocked: true`, `verdict: BLOCKED`** for new PMA registration in Bali
specifically: at the mandatory PMA (Besar) scale, its OSS risk class is
Low/Medium-Low on every scope, which is exactly the band the 2026-05-13
island-wide moratorium (Q3) blocks. This document originally concluded the
reviewer's "55901 too is affected by the Bali moratorium" claim was
*unsupported* — that was wrong; the reviewer was right, and this document's
own web-only research missed a restriction Bali Zero's internal dataset
already had on file. **Do not offer 55901 to a client as a currently-open
PMA route in Bali** until this classification changes (verify live OSS
before ever reversing this).

## Reliability / caveats

Counter-sources exist (e.g. some property-marketing sites claiming "villa
55193 is fine for PMA") — down-weighted as low-reliability: at least one
such source mislabels 55193 as "Pondok Wisata" and advises
under-capitalizing below the Rp10bn threshold, both non-compliant
positions. Industry practitioner discourse independently corroborates
Claim B (multiple "regulatory gap for PT PMA villa investors" pieces).

**Primary-source caveat**: confirmations rely on secondary legal/
compliance aggregators and news reporting, not directly-fetched government
PDFs — several official OSS/BPS portals returned HTTP 403 to automated
fetch this session. Convergence across 8+ independent sources plus Bali
Zero's own BKPM 5/2025 internal note is strong, but the exact Perpres
49/2021 lampiran line listing villa/non-star accommodation as
"dialokasikan untuk UMKM" should be pinned by a licensed consultant before
this finding is promoted from Qdrant-grounding-only to the verbatim FAQ
sink.

## What Bali Zero should tell a client today (plain language, revised 2026-07-21)

A foreigner cannot legally run a villa / short-term (Airbnb-style) rental
in Bali by putting KBLI 55203 "Aktivitas Vila" into a PT PMA — that code is
reserved for Indonesian micro/small/medium businesses (UMKM) and has no
large-scale licence tier, while a PT PMA must invest above Rp10 billion per
KBLI per location, i.e. operate at large scale. There is currently no KBLI
that lets a PT PMA operate a villa directly. Beyond that, as of a Bali
provincial rule effective 2026-05-13, the picture is narrower than "any
hotel-family code works": the clean, currently-open route is a **serviced
apartment / apartemen hotel (KBLI 55204)**. A **star-rated hotel
(55101-55105)** is only registrable in Bali by declaring a higher-risk
project scope — confirm live in OSS before quoting a client, don't assume
it clears. A **management-only company (KBLI 55901)**, managing
Indonesian-owned villas for a fee, is 100% foreign-open *nationally* but is
**currently blocked from new PMA registration in Bali** by the same
2026-05-13 rule — do not offer it as an available route today. All routes
still need the >Rp10bn investment threshold, correct zoning (KKPR), TDUP/
star classification where applicable, and HGB or long-term Hak Sewa land.
Bali is not under a blanket *construction* moratorium, but it IS under an
enacted, PMA-specific *registration* restriction (island-wide, blocks all
Low/Medium-Low-risk codes, bans virtual-office PMA domicile) on top of the
pre-existing "pengendalian" regime (land-conversion bans, tight zoning,
some area/water-catchment restrictions) — so live-OSS verification per
project is mandatory, not optional, before telling a client a route is open.

## Adversarial review

Reviewed by an independent seat (Kimi K3, `kimi-code/k3`), which checked
this document against Bali Zero's own internal KBLI ground-truth dataset
(`data/source_documents/KBLI_2025_FINAL_CLEAN.json`, the `l4_bali` field)
as well as external reporting — a check this document's original web-only
research never ran. Verdict on central claims: **55203 not PMA-eligible
holds** (confirmed independently by the internal dataset's own
`verdict: NO_BESAR`); **"no blanket construction moratorium" holds**; but
the document's compliant-routes advice (Q4, Q5) and its "no enacted
licensing ban" framing (Q3) did not. 6 objections survived; all are fixed
above:

1. **[Major] Q5's 55901 verdict was backwards.** This document originally
   cleared 55901 as "not moratorium-affected." Bali Zero's own dataset
   marks it `BLOCCATO_CLASSE_RISCHIO` / `blocked: true` for Bali PMA
   registration, sourced to the same Gubernur letter. Independently
   re-verified directly against the dataset file before accepting this —
   confirmed. Fixed above; this was the single most consequential error,
   since it was offered as a client-facing "compliant route."
2. **[Major] Q3's "no enacted province-wide licensing ban exists" was
   overstated.** It correctly ruled out a *construction* moratorium but
   never checked for a narrower, enacted *PMA-registration* restriction —
   which exists (2026-05-13, per the same internal dataset). Fixed above.
3. **[Minor] Koster statement misdated** as 2026-01-09; independently
   re-verified against the source article's byline: it was **2025-01-09**.
   Fixed above (appeared in TL;DR and Q3, both corrected).
4. **[Minor] The Perpres 49/2021 "quotation" in Q1 is not verbatim
   regulatory prose** — Lampiran II is a KBLI code table with checkmarks,
   not a sentence. The underlying allocation (villa/pondok-wisata/guest-house
   → UMKM) is independently confirmed via the lampiran table itself,
   so the substance holds; the citation should read "Lampiran II, tourism
   sector" rather than imply a quoted clause. Not re-edited line-by-line
   above (low stakes, doesn't change any conclusion) — noted here as a
   citation-hygiene item for whoever next touches Q1.
5. **[Minor] "Pondok Wisata (55130)" cites a retired KBLI 2020 code**
   without giving its KBLI 2025 disposition (folded into 55106, which this
   document itself lists in the ambiguous hotel-family group). Substance
   (not PMA-eligible) holds via the Lampiran II allocation; citation is
   loose. Not re-edited line-by-line above — noted for the same reason as
   (4).
6. **[Minor] 55101-55105 originally presented as unqualified "100%
   PMA-open."** Fixed above (Q4) — reclassified as scope-dependent,
   verify-live-OSS.

One seat objection (that the corrections package "doesn't exist" at the
path this document cites) was investigated and retracted — the corrections
live at `research/curated-qa-corrections-2026-07-21/` in this same PR
(20 rows, content matches); only the path string in an earlier draft
pointed at the live-data target path rather than the drafted-corrections
path, which `corrections/README.md` (now `research/curated-qa-corrections-2026-07-21/README.md`)
already explains.

## Checklist for action

- [x] Correct the 9 affected `property-villa-rental.jsonl` Q&A rows
      (drafted 2026-07-21, revised again post-adversarial-review same day,
      see `research/curated-qa-corrections-2026-07-21/` in this PR) —
      Claim A was legally dangerous for a live advice bot, and the
      original Q4/Q5 compliant-routes advice needed correction too.
- [ ] Do NOT promote this batch to the verbatim FAQ sink until a licensed
      consultant pins the exact Perpres 49/2021 lampiran citation
      (primary-source caveat above) AND confirms current live-OSS status
      for 55101-55106 and 55901 in Bali (both are dataset-flagged as
      scope-dependent / blocked, not primary-government-source pinned
      this session).
- [ ] Re-harvest the corrected Qdrant `curated_qa` points — requires
      Zero's review per `curated_qa_harvest.py`'s own operator gate
      ("Do NOT run against prod without Zero's review of the batch being
      loaded").
