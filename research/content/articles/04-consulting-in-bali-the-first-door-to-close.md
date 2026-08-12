---
date: 2026-06-21
domain: compliance
client_case: none
kbli_codes:
  - "70209 — Aktivitas Konsultasi Manajemen dan Bisnis Lainnya — National: TERBUKA 100% — Bali: CHIUSO_BALI (blocked, closed from 28/1/2026)"
  - "70201 — Aktivitas Konsultansi Manajemen dan Bisnis Pariwisata — National: TERBUKA 100% — Bali: CHIUSO_MORATORIA_BALI (blocked by the risk-tier moratorium)"
  - "70202 — Aktivitas Konsultansi Manajemen dan Bisnis Industri — National: TERBUKA 100% — Bali: BLOCCATO_CLASSE_RISCHIO (blocked)"
  - "62201 — Aktivitas Konsultansi dan Manajemen Keamanan Siber — National: TERBUKA 100% — Bali: OK_or_HIGHER_RISK (registrable)"
  - "62209 — Aktivitas Konsultansi Komputer dan Manajemen Fasilitas Komputer Lainnya — National: TERBUKA 100% — Bali: OK_or_HIGHER_RISK (registrable)"
status: published-draft
adversarial_review: codex
---
# Consulting in Bali: The First Door to Close (KBLI 70209)

"I'll just set up a consultancy." It is the most reflexive sentence in the Bali expat playbook — the fallback for the marketer, the strategist, the ex-corporate fixer who wants a clean, asset-light PMA without a kitchen, a pool, or a warehouse. Pure advice. What could be lower-friction than that?

As it turns out, the answer is: almost everything. Management consulting was, in a quiet way, **the first door Bali closed** to foreign-owned companies — and it closed before most people noticed the moratorium had even arrived.

## 70209 was shut on 28 January 2026

**KBLI 70209 — Aktivitas Konsultasi Manajemen dan Bisnis Lainnya** ("other management and business consulting") is the catch-all consulting code: strategic and organisational planning, business advice, the work that doesn't fit a narrower bucket. Nationally it is `TERBUKA`, fully open to foreign ownership.

In Bali its status is **CHIUSO_BALI** — closed to PMA, and the ground-truth record is specific about the date: _closed to PMA in Bali from 28 January 2026 — the first of the seven._ In other words, the province began fencing off foreign consulting **months before** the broad 13 May 2026 risk-class moratorium. Consulting was singled out early, deliberately, as a category where the island wanted to protect local professional services.

So the asset-light dream — the cleanest, simplest PMA you could imagine — is one of the _hardest_ to register in Bali right now.

## And the neighbours are no better

If your instinct is to slide to a different consulting code, check the whole row before you celebrate. The management-consulting family is closed across the board for a Bali PMA:

- **70201 — Konsultansi Manajemen dan Bisnis Pariwisata** (tourism consulting): open nationally, but **blocked** in Bali — and by the moratorium, not by any reservation. We located no foreign-ownership restriction on this activity in the Perpres annexes or the closed list; it is caught because its risk tier is _Rendah_, inside the band the Governor asked BKPM to close (letter B.27.000/642/PM/DPMPTSP, 28 January 2026).
- **70202 — Konsultansi Manajemen dan Bisnis Industri** (industrial consulting): open nationally, but **blocked** in Bali under the low-risk moratorium.

The pattern is unmistakable. "Generic business consulting, foreign-owned, in Bali" is the exact profile the province has decided to wall off. Reading a national "100% open" on any 7020x code and assuming Bali agrees is precisely the National-vs-Provincial blind spot that kills business plans.

## The route that survives: take the advice into IT

Here is the genuine escape, and it is not a loophole — it is a real, higher-substance business. The **IT-consulting** codes are classified at **medium-high risk**, which lifts them clear of the moratorium. They are open both nationally and in Bali:

- **62201 — Konsultansi dan Manajemen Keamanan Siber** (cybersecurity consulting and management). National: open. Bali: **REGISTRABLE.** Carved out as its own 2025 code (it was buried inside general IT consulting in 2020), reflecting national cyber-resilience priorities. Medium-high risk → survives.
- **62209 — Konsultansi Komputer dan Manajemen Fasilitas Komputer Lainnya** (computer consulting and IT facilities management). National: open. Bali: **REGISTRABLE.** This covers advising on hardware/software type, configuration, and requirements, plus managing computer facilities. Medium-high risk → survives.

If your actual expertise has a genuine technology spine — security advisory, systems and infrastructure consulting, IT strategy — these codes let you run a foreign-owned advisory business in Bali _legally_, where the bare 70209 management-consulting shingle cannot. The honest caveat: you must really be doing the IT activity the code describes. Substance-based inspection is now the norm, and a "cybersecurity consultancy" that only does generic management advice is a 70209 wearing a 62201 costume — exactly the kind of mismatch an inspection is designed to catch.

The lesson of the consulting door is the lesson of the whole island: the simplest-looking business is rarely the easiest to register, and the route that survives is usually the one with more substance, not less.

_Before you register any 7020x consulting code, check its live Bali status on the Bali Zero KBLI Navigator at balizero.com — and see the IT-consulting alternatives (62201, 62209) that survive the moratorium, mapped national-vs-Bali in the same two-branch view._

## Adversarial review

- Seat: Codex `gpt-5.6-sol` (reasoning xhigh), refute stance, cross-family — reviewed the
  2026-08-12 retraction-cure diff touching this file, verified against
  `KBLI_2025_FINAL_CLEAN.json` (the cured dataset).
- Outcome: FIX-FIRST → fixed in this same PR. 10 findings (9 confirmed/accommodated, 1 HOLDS): 96220 national status corrected to TERBATAS 0% (measured); 55201/55203 restated as the same Annex II entry 48 (sub-rows *Pondok Wisata* / *Vila*); the annex stated as a national instrument (articles 01/02); honest-map wording corrected (33.2% = almost exactly one in three; all but FOUR of the 372 nationally open; 1,041 = "not blocked", not "open"); surf-coliving guest-house-scope reading stated as OSS's call, not the founder's certainty; stale ID fact-sheet row (55203 "tanpa Besar") cured. Every fix re-measured against KBLI_2025_FINAL_CLEAN.json before applying.
- Note: this section and the `adversarial_review` frontmatter key are R1-gate metadata;
  the book/PDF composer strips the frontmatter block and this section from rendered output.
