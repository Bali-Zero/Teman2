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
The compliant PMA routes are a star-rated hotel (KBLI 55101-55105) or a
serviced apartment/apartemen hotel (KBLI 55204) for direct operation, or a
management-only company (KBLI 55901) for third-party accommodation
management. Bali is not under a blanket construction/licensing moratorium
(the Governor explicitly rejected one on 2026-01-09), but zoning/KKPR
control remains strict per-project.

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

**Q3 — Does a Bali moratorium independently block this route? → PARTIALLY-BOTH
(Claim B overstates).** No enacted province-wide licensing ban exists.
2024-09-10 reporting: central government (Kemenko Marves) "agreed" a
moratorium concept on new hotels/villas/nightclubs — a policy discussion,
not enacted law. 2026-01-09: Governor Koster explicitly **rejected** a
formal moratorium ("Tidak perlu moratorium. Yang ada pengendalian secara
ketat" — no moratorium needed, what exists is strict control) — permits
continue under strict Perda rules. Real constraints do exist (no
productive-land conversion since 2025, water-catchment-zone restrictions,
tight KKPR/zoning review) but this is a control regime, not a categorical
freeze on hotel/apartemen-hotel PMA licensing.

**Q4 — What is the correct compliant PMA path in 2026? → CONFIRMED-CLAIM-B
(no direct villa route exists).** PMA is excluded from short-term
accommodation other than hotels (Perpres 49/2021). PMA-open codes: **Hotel
Bintang 55101-55105** (100% PMA-open, needs TDUP + star classification);
**Apartemen Hotel / Serviced Apartment 55204** (kbli.co.id/55204: "Open to
PMA"). A non-star hotel tier (55106) also exists — confirm per-project. The
reviewer's "apartment hotel" reclassification suggestion is a genuine,
correct workaround; star-hotel is the cleaner route where the project
scale supports it. Land: HGB, or a long-term Hak Sewa; zoning (pink/
tourism designation) + TDUP prerequisites still apply. NOT PMA-eligible:
Vila (55193/55203), Pondok Wisata (55130), Homestay (55201). Do not
disguise short-term rental under property-ownership codes (68111/68112) —
flagged elsewhere as a compliance violation.

**Q5 — Is KBLI 55901 (management services) PMA-open and moratorium-affected?
→ PARTIALLY-BOTH / one leg UNABLE-TO-CONFIRM.** 55901 = Aktivitas Jasa
Manajemen Akomodasi = third-party management for a fee, explicitly NOT
ownership/direct operation. It is a distinct service code, well-supported
as PMA-usable, though a crisp primary "terbuka 100% PMA" citation was not
independently located this session (treat as well-supported, not
primary-confirmed). On the moratorium question: the moratorium discourse
targets *construction* of new accommodation, not *management* of already-
licensed accommodation — no evidence found that 55901 is moratorium-
affected; the reviewer's claim that it "too is affected by the Bali
moratorium" is unsupported (a pure management service builds nothing).
Caveat: the villas a 55901 company manages must themselves be legally
licensed under a valid classification.

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

## What Bali Zero should tell a client today (plain language)

A foreigner cannot legally run a villa / short-term (Airbnb-style) rental
in Bali by putting KBLI 55203 "Aktivitas Vila" into a PT PMA — that code is
reserved for Indonesian micro/small/medium businesses (UMKM) and has no
large-scale licence tier, while a PT PMA must invest above Rp10 billion per
KBLI per location, i.e. operate at large scale. There is currently no KBLI
that lets a PT PMA operate a villa directly. The legitimate routes are to
structure the property as a star-rated hotel (KBLI 55101-55105) or a
serviced apartment/apartemen hotel (KBLI 55204) — both open to 100%
foreign ownership, requiring the >Rp10bn investment, TDUP, star
classification where applicable, correct zoning (KKPR), and HGB land — or
to set up a PT PMA management-services company (KBLI 55901) that manages
Indonesian-owned villas for a fee. Bali is not under a blanket
construction/licensing moratorium, but it is under strict "pengendalian"
(land-conversion bans, tight zoning, some area/water-catchment
moratoria), so zoning and KKPR must be checked per project.

## Checklist for action

- [x] Correct the 9 affected `property-villa-rental.jsonl` Q&A rows
      (applied 2026-07-21, see `corrections/` in this PR) — Claim A was
      legally dangerous for a live advice bot.
- [ ] Do NOT promote this batch to the verbatim FAQ sink until a licensed
      consultant pins the exact Perpres 49/2021 lampiran citation
      (primary-source caveat above).
- [ ] Re-harvest the corrected Qdrant `curated_qa` points — requires
      Zero's review per `curated_qa_harvest.py`'s own operator gate
      ("Do NOT run against prod without Zero's review of the batch being
      loaded").
