---
date: 2026-07-29
domain: property
client_case: none
author: deep-researcher (Bali Zero)
status: draft
partial: true
sources:
  - Peraturan Menteri Investasi dan Hilirisasi/Kepala BKPM No. 5 Tahun 2025 (primary PDF, 698 pp., fetched 2026-07-29 from https://jdih-storage.bkpm.go.id/jdih/jdih/2025Permeninvesthil005-.pdf) — Pasal 16, 26, 34-35, 60-61, 300
  - Peraturan Menteri Pariwisata dan Ekonomi Kreatif No. 4 Tahun 2021 (primary PDF, fetched 2026-07-29 from https://peraturan.bpk.go.id/Download/162295/PERMEN%20PAREKRAF%20NOMOR%204%20TAHUN%202021.pdf) — Standar Usaha Hotel, Vila, Apartemen Hotel
  - data/source_documents/KBLI_2025_FINAL_CLEAN.json (Bali Zero curated OSS ground truth, per_skala + l4_bali fields)
  - NotebookLM NB-5 Property (d9438180-5e63-4e2a-a473-6061101f6a8d), query 2026-07-29 — independent confirmation of Pasal 26(5)
  - A&O Shearman, "Risk-based licensing: BKPM Regulation 5/2025 consolidates and clarifies the 2021 regime" (https://www.aoshearman.com/en/insights/risk-based-licensing-bkpm-regulation-5-2025-consolidates-and-clarifies-the-2021-regime)
  - Golaw.id, "LKPM untuk Perusahaan dengan Lebih dari Satu Proyek" (https://golaw.id/blog/lkpm-untuk-perusahaan-dengan-lebih-dari-satu-proyek-apakah-harus-dibuat-terpisah/)
  - Permenpar 10/2018 on electronically-integrated tourism licensing (via jogloabang.com summary of the TDUP one-location/one-management clause)
  - research/property/2026-07-21-kbli-villa-pma-eligibility-verification.md (sibling capture; this document CORRECTS two of its statements)
adversarial_review: codex gpt-5.6-terra (Q3 lane, citations independently re-verified against primary PDF); kimi-k3 seat UNAVAILABLE (HTTP 403 quota)
---

# Consolidating 5 scattered Bali villas into one PMA-compliant structure

## Question

A client owns 5 villas in Bali, scattered across different but nearby
desa/kecamatan (exact addresses not yet disclosed). She already holds a
PT PMA with an unrelated business scope. She wants the 5 villas to
produce rental income inside a PMA-compliant structure. Open questions
nobody in the Bali Zero corpus had answered: what does "per lokasi
proyek" actually mean; can one NIB / one licence cover multiple
non-contiguous sites; does Indonesia recognise a dispersed-accommodation
("albergo diffuso") licensing concept; and if not, what structures work.

## TL;DR

- **"Lokasi proyek" is never defined in the regulation.** Two readings
  coexist inside the same instrument. The weight of evidence favours
  **per-site**, not per-kabupaten/kota, for accommodation — because
  administrative-unit aggregation is granted as an **express,
  sector-specific carve-out** (F&B, EV charging) that accommodation does
  not receive. UNRESOLVED at primary-source level; needs a live OSS test.
- **The Rp10bn threshold for accommodation INCLUDES land and buildings**
  (Pasal 26(5)(b)). This is a material correction to our own sibling
  capture and to the brief's premise, and it changes feasibility
  dramatically in the client's favour.
- **One NIB covering 5 villas is trivially true and legally
  uninformative.** A company can only ever have one NIB (Pasal 16(2)).
  The binding unit is the KBLI-times-location project record, and
  scattered parcels require a **KKPR per hamparan** (Pasal 61(3)).

## Key citations (verbatim)

**Permeninves/BKPM 5/2025 Pasal 26(2)** — the general rule:

> Ketentuan minimum nilai investasi bagi PMA sebagaimana dimaksud pada
> ayat (1), yaitu total investasi lebih besar dari Rp10.000.000.000,00
> (sepuluh miliar rupiah), di luar tanah dan bangunan per bidang usaha
> KBLI 5 (lima) digit per lokasi proyek.

**Pasal 26(3)(b) and 26(4)** — the F&B carve-out, the only place an
administrative unit is named for the general threshold:

> (3) Ketentuan sebagaimana dimaksud pada ayat (2) dikecualikan untuk
> kegiatan usaha: [...] b. jasa makanan dan minuman, lebih besar dari
> Rp10.000.000.000,00 [...] adalah per 2 (dua) digit awal KBLI per
> 1 (satu) titik lokasi;
>
> (4) Ketentuan Titik lokasi sebagaimana dimaksud pada ayat (3) huruf b
> berlaku per kabupaten/kota.

**Pasal 26(5)** — decisive for this client, and the correction:

> Dalam hal PMA melakukan kegiatan usaha: a. pengusahaan properti yang
> meliputi pembangunan, penjualan, dan/atau penyewaan; **b. penyediaan
> akomodasi jangka pendek dan jangka panjang**; c. pertanian;
> d. perkebunan; e. peternakan; dan f. perikanan budidaya, kriteria
> nilai investasi sebagaimana dimaksud pada ayat (2) **termasuk tanah dan
> bangunan**.

**Pasal 26(6)** — the adjacent property rule, which cuts the other way:

> Dalam hal kegiatan usaha pembangunan dan pengusahaan properti berlaku
> ketentuan: a. berupa properti dalam bentuk bangunan gedung secara utuh
> atau kompleks perumahan secara terpadu dengan ketentuan nilai investasi
> lebih besar dari Rp10.000.000.000,00 termasuk tanah dan bangunan; atau
> b. berupa **unit properti tidak dalam 1 (satu) bangunan gedung secara
> utuh atau 1 (satu) kompleks perumahan secara terpadu**, nilai investasi
> lebih besar dari Rp10.000.000.000,00 **di luar tanah dan bangunan**.

**Pasal 16(2)** — one entity, one NIB:

> Setiap entitas usaha hanya memiliki 1 (satu) NIB.

**Pasal 35(1)** — the real unit of account:

> Data usaha terkait dengan spasial dan kesesuaian ruang sebagaimana
> dimaksud dalam Pasal 34 diisi untuk masing-masing kode KBLI 5 (lima)
> digit dan per lokasi.

**Pasal 61(2)-(3)** — scattered parcels, scattered KKPR:

> (2) Koordinat lokasi [...] merupakan koordinat lokasi usaha yang
> terintegrasi dalam satu hamparan.
>
> (3) Dalam hal koordinat lokasi usaha sebagaimana dimaksud pada ayat (2)
> **tidak berada dalam satu hamparan, permohonan diajukan berdasarkan
> setiap koordinat lokasi hamparan**.

**Permenparekraf 4/2021, Standar Usaha Hotel (55110/55120)** — multiple
buildings are expressly contemplated:

> Usaha Hotel adalah usaha penyediaan akomodasi secara harian berupa
> kamar-kamar **di dalam 1 (satu) atau lebih bangunan**, termasuk losmen,
> penginapan, pesanggrahan, yang dapat dilengkapi dengan jasa pelayanan
> makan dan minum, kegiatan hiburan dan/atau fasilitas lainnya.

**Permenparekraf 4/2021, Standar Usaha Apartemen Hotel (55204)** — same
multi-building phrasing, but note the scope:

> Usaha Apartemen hotel adalah usaha penyediaan akomodasi secara harian
> berupa **unit hunian dalam 1 (satu) atau lebih bangunan** yang dikelola
> oleh usaha jasa manajemen apartemen hotel.

## Findings by question

### Q1 — What does "per lokasi proyek" mean?

**Verdict: NOT DEFINED. Genuinely unresolved in primary text. The
better-supported reading is per-site, not per-kabupaten/kota.**

"Lokasi proyek" appears exactly 5 times in Permeninves 5/2025 and is
**absent from the Pasal 1 definitions article** (verified by exhaustive
grep against the extracted primary text, with a positive control
confirming the definitions article was inside the extract — 81 "adalah"
definitions present, including OSS and KKPR). It is a load-bearing term
the drafter never defined.

**Evidence for the per-site reading (stronger):**

1. *Expressio unius.* Pasal 26(3)(b) plus 26(4) grant F&B aggregation to
   the kabupaten/kota level, and Pasal 26(7) grants EV-charging stations
   aggregation to the province level. Both are drafted as **express
   exceptions**. If "lokasi proyek" already meant kabupaten/kota, the F&B
   clause would be largely pointless. Accommodation receives no such
   clause.
2. A&O Shearman reads the 2025 regulation the same way: the new
   regulation "clarifies and eases the requirement by expressly tying
   location to certain government administrative units" — *certain*, i.e.
   the named sectors, which is a change **from** a regime that lacked
   that geographic clarity elsewhere.
3. Pasal 35(1) makes OSS spatial data an entry **per 5-digit KBLI and per
   location**, and Pasal 61(3) requires a separate KKPR application per
   non-contiguous hamparan. The system's own unit of account is the site.

**Evidence for the per-kabupaten/kota reading (weaker but real, and
client-favourable):**

1. Pasal 300(5)(d), listing the contents of the routine field-inspection
   register, writes **"lokasi proyek (kabupaten/kota)"** — the only place
   in the entire instrument where the term is glossed, and it glosses it
   as regency/city. This is in a supervision context, not a definitions
   article, but it is the drafter's own parenthetical.
2. LKPM reporting practice is organised per kabupaten/kota (Perka BKPM
   5/2021 lineage; multiple DPMPTSP portals state investors with
   activities in more than one district/city file one LKPM per district).

**Source conflict, stated plainly:** one practitioner source (Golaw)
describes the OSS project identity as the triple *KBLI 5-digit + lokasi
proyek + NKU*, with each distinct combination producing an independent
project requiring its own LKPM — i.e. address-level. Another line of
sources describes LKPM as filed per kabupaten/kota — i.e. regency-level.
Both can be true simultaneously if OSS groups address-level projects into
regency-level reports, but that reconciliation is our inference, not a
sourced statement. **We could not pin this to a primary-source
definition. Do not quote a definitive answer to a client.**

### Q1-bis — MATERIAL CORRECTION: land and buildings COUNT

The brief and our sibling capture both state the Rp10bn threshold
excludes land and buildings. **For this client's sector that is wrong.**
Pasal 26(5)(b) puts "penyediaan akomodasi jangka pendek dan jangka
panjang" on the list where "kriteria nilai investasi sebagaimana dimaksud
pada ayat (2) **termasuk tanah dan bangunan**." Independently confirmed
by NB-5 Property, which states: "for property and accommodation sectors,
the value of land and buildings can now be included in that IDR 10
billion calculation" under Article 26(5).

This is the single most consequential finding for feasibility. Five Bali
villas will in most realistic cases carry land-plus-building value that
clears Rp10bn either per site or close to it — so the threshold that
looks fatal under the "excluding" reading is often satisfiable under the
correct one.

**Counter-risk, do not skip:** Pasal 26(6)(b) says that where the
business is *pembangunan dan pengusahaan properti* and the assets are
**units not within one whole building or one integrated housing
complex** — a precise description of 5 scattered villas — the threshold
reverts to **excluding** land and buildings. So the favourable treatment
depends on the activity being characterised as **accommodation provision
(55xxx)** rather than **property leasing (68xxx)**. There is unresolved
tension between 26(5)(a) and 26(6)(b) on the face of the instrument.
Characterisation is the whole ballgame here.

### Q2 — Can one NIB / one licence cover multiple non-contiguous sites?

**Verdict: the question dissolves. One NIB — yes, necessarily. One
licence/one project — no.**

Pasal 16(2): "Setiap entitas usaha hanya memiliki 1 (satu) NIB." A
company cannot have more than one NIB, so "one NIB covering 5 villas" is
automatic and proves nothing. The NIB is entity identity (Pasal 16(3)),
not a site permit.

What is genuinely per-site:

- **Spatial/business data** — Pasal 34 requires address, land area,
  tenure, coordinates, planned number of buildings and floors; Pasal
  35(1) requires this per 5-digit KBLI **and per location**.
- **KKPR** — Pasal 61(2) presumes coordinates "terintegrasi dalam satu
  hamparan"; Pasal 61(3) requires a separate application per hamparan
  where they are not. Five scattered villas are five hamparan, therefore
  five KKPR. (This clause sits in the cross-regency/cross-province KKPR
  procedure of Pasal 60-61, which is exactly the client's fact pattern if
  the villas straddle regencies.)
- **Risk grading and the resulting sertifikat standar** — graded on the
  project's own room count, staff count or building area.
- **Investment value** — per Pasal 26(2), subject to Q1's unresolved
  granularity.

So the honest formulation for a client: *the company is one; the projects
are five.*

### Q3 — Does Indonesia recognise a dispersed / "albergo diffuso" model?

**Verdict: no such category exists, and no rule expressly forbids it
either. The silence is the finding.**

- An exact-text review of Permenparekraf 4/2021 (run by an independent
  Codex seat, spot-verified by us against the primary PDF) found **no**
  "tersebar", "vila tersebar", "hotel terpadu", or "resort multi-lokasi"
  category. The villa classifications are non-star and stars 1-3; there
  is no dispersed variant.
- **But the hotel and aparthotel standards both define the business as
  rooms/units "di dalam 1 (satu) atau lebih bangunan"** — one *or more*
  buildings. Multi-building is expressly contemplated. What the
  regulation never addresses is whether those buildings may be
  geographically separated. It says neither yes nor no.
- By contrast the **villa** standard defines the business as renting a
  building "secara keseluruhan" (as a whole) — a single-building concept
  by construction.
- **Permenpar 10/2018** (TDUP-era, pre-OSS but directionally instructive)
  allowed one TDUP document for multiple tourism businesses **"di dalam
  1 (satu) lokasi dan 1 (satu) manajemen"** — one location AND one
  management — and required an operator expanding "di lokasi lain" to
  satisfy the location-attached permits in each such area. One document
  for one location; expansion is re-permitted per location.
- **Market practice is not evidence of licensing.** Bali villa
  collections (e.g. BaliSuperHost, Nakula) market scattered portfolios as
  one brand, but we could not verify a single one of their NIBs, KBLI
  registrations or KKPRs from public records. Those are brand and
  management aggregations. **Do not cite them to a client as proof that a
  single multi-site accommodation licence is obtainable.**

### Q4 — Realistic alternative structures

**(a) One PT PMA, five registered lokasi usaha under 55204 — the base
case.** Legally coherent: one NIB, five projects, five KKPR, five risk
gradings, five investment lines. With Pasal 26(5) counting land and
buildings, the per-location threshold is far more achievable than the
brief assumed. *Scope caveat:* 55204's standard scope is
"apartemen hotel/kondominium hotel apartel/kondotel" — apartment or
condominium **units** functioning as a hotel. Applying it to five
detached villas in different desa is a real stretch that a Dinas
Pariwisata or OSS verifier may reject. Our sibling capture recommends
55204 as the clean route on moratorium grounds without raising this
scope-fit risk. Flagging it now.

**(b) Star hotel (55101-55105) — structurally hostile to scattered small
villas, and we can now say why.** Our own OSS ground truth shows 55101's
risk tier is keyed to project size: `Luas bangunan ≤ 6.000 M²` grades
Menengah Rendah at every scale including Besar, while `> 6.000 M²` grades
Menengah Tinggi. Permenparekraf 4/2021 gives the same criteria (Menengah
Tinggi = 101-200 rooms, or 100-200 staff, or land >6,000-10,000 m²).
Because Bali's 2026-05-13 moratorium blocks Low/Medium-Low-risk codes for
new PMA registration, a hotel project only clears **if it is big enough
to reach Menengah Tinggi** — and each scattered villa would have to reach
that threshold on its own project record. Implausible for villa-scale
assets. This mechanism explains the sibling capture's "scope-dependent,
verify live in OSS" verdict.

**(c) Management-only (55901) — still blocked.** Our ground truth shows
Menengah Rendah at **every** scale including Besar, therefore inside the
band the Bali moratorium blocks (`verdict: BLOCKED`). Unchanged from the
sibling capture.

**(d) Add the activity to the existing PT PMA vs. incorporate a second
one.** Paid-up capital is **per company** (Pasal 26(10),
Rp2.5bn), but the investment threshold is **per KBLI per location**
regardless of how many companies you use. Therefore a second PT PMA
**does not reduce the threshold burden at all** — it only adds a second
Rp2.5bn paid-up requirement plus duplicate compliance. Default
recommendation: **add the accommodation KBLI to the existing PMA**,
unless there is a shareholder, risk-ring-fencing or exit reason to
separate. **Unresolved and decision-critical:** whether adding a new KBLI
to an *existing* PMA is treated as a "new PMA registration" for the
purposes of the Bali moratorium. If it is not, the client's existing PMA
may be a materially better vehicle than a new one. We found no source
either way. This is the highest-value question to test.

**(e) Five SPVs, one per villa.** Five times Rp2.5bn paid-up (Rp12.5bn
cash locked, Pasal 27(1) imposing a 12-month lock-up), five sets of
compliance, and no relief on the per-location threshold. Only justified
if per-villa sale or per-villa risk isolation is an explicit client goal.

### Q5 — Conflicts, gaps, and things we refuse to guess

1. **"Lokasi proyek" granularity — UNRESOLVED** (Q1). Two readings inside
   one instrument. Needs a live OSS registration test or written BKPM
   confirmation.
2. **Conflict with our own sibling capture, unresolved.** That document
   states the villa code "has no Usaha Besar tier at all in OSS", citing
   secondary aggregators, and flagged it as needing primary-source
   pinning. Primary text now **contradicts the stated mechanism**:
   Permenparekraf 4/2021's Standar Usaha Vila says
   "**Skala usaha vila adalah Mikro, Kecil, Menengah dan Besar**" — Besar
   included. We checked whether this is boilerplate: it is not, the field
   varies across standards (others read "Menengah dan Besar", or "Mikro,
   Kecil, Menengah dan Besar sesuai dengan ketentuan peraturan
   perundang-undangan"). However, Bali Zero's OSS-derived KBLI 2025
   dataset shows 55203 with **only** Mikro/Kecil/Menengah rows and no
   Besar row, while 55204 and 55901 do carry Besar rows. Most likely
   reconciliation: the 2021 tourism standard was written against KBLI
   2020 code 55193 and the live OSS 2025 matrix for 55203 diverges from
   it. **The OSS matrix is what binds at registration**, so the sibling
   capture's conclusion survives even though its stated mechanism is not
   supported by the tourism standard's own text. Flagged rather than
   silently reconciled.
3. **55204 scope-fit risk for detached villas** — raised above, unverified
   either way.
4. **Whether adding a KBLI to an existing PMA triggers the Bali
   moratorium** — no source found.
5. **Panel was 3 seats, not 4.** The Kimi K3 refuter seat returned HTTP
   403 (billing-cycle quota exhausted) and contributed nothing. Codex
   covered the Q3 lane; every article number it cited was independently
   re-verified by us against the primary PDF before being used here
   (Pasal 61(2)-(3) confirmed verbatim). Its Bali-operator examples are
   marked practitioner-commentary and are **not** relied on.
6. **Apparent drafting error in the primary text:** Pasal 27(1)
   cross-references "Pasal 26 ayat (6)" for modal ditempatkan/disetor,
   but paid-up capital is set in ayat (10); ayat (6) is the property
   rule. Cosmetic, but do not quote Pasal 27(1)'s cross-reference.
7. Hukumonline and Prolegal pages returned HTTP 403 to automated fetch;
   where they appear, they are cited via search-result excerpts, not
   direct retrieval. The two regulations that carry this document's
   weight were fetched as complete primary PDFs.

## What Bali Zero should tell a client today (plain language)

Your company stays one company — an Indonesian company can only ever have
one NIB, so "one registration for all five villas" is automatic and
doesn't mean what it sounds like. What matters is that OSS will treat
**each villa as its own project**: its own address record, its own zoning
approval (KKPR), its own risk grade, and its own investment line. Five
scattered villas means five KKPR, because the rules require a separate
zoning application for each non-contiguous parcel of land.

The good news, and it is significant: for accommodation businesses the
Rp10 billion investment requirement **counts the value of your land and
buildings**. Most guides — and our own earlier note — say land and
buildings are excluded. That general rule has an express exception for
short-term and long-term accommodation. For five Bali villas that
frequently turns an impossible-looking threshold into a satisfiable one.
The catch is that this depends on the business being licensed as
*accommodation*, not as *property rental*: if it is characterised as
renting out scattered property units, land and buildings drop back out of
the calculation and the numbers get hard again.

There is **no Indonesian equivalent of the Italian "albergo diffuso"** —
no licence category for scattered buildings sold as one hotel. The hotel
and serviced-apartment standards do allow "one or more buildings", so
multiple buildings are fine; the rules simply never say whether those
buildings may be kilometres apart. Nobody has written the rule either
way. Villa collections in Bali that market scattered properties under one
brand are doing brand and management aggregation — we have not verified
how any of them is actually licensed, and neither should you assume.

Practically: **add the activity to your existing PT PMA rather than open
a second one.** A second company would cost you another Rp2.5 billion in
paid-up capital, locked for 12 months, and would not reduce the
investment threshold by a single rupiah — because that threshold attaches
per activity code per location no matter how many companies you own.
Before we commit to that, we need to confirm one thing we could not
resolve from the regulations: whether adding a new activity code to an
existing PMA counts as a "new registration" under Bali's
moratorium (effective 2026-05-13, which blocks new PMA registration for
all Low and Medium-Low risk codes). If it does not, your existing company
is a genuine advantage.

Two honest warnings. First, the serviced-apartment code we would normally
recommend is written for apartment and condominium units run as a hotel;
using it for five detached villas is a stretch that a licensing officer
may refuse — this must be tested live in OSS before anyone quotes you a
price. Second, the star-hotel route almost certainly will not work here:
in Bali a hotel project only escapes the moratorium if it is large enough
to be graded medium-high risk, which needs roughly 100+ rooms or over
6,000 m² of building — per project, not across your portfolio. Villa-scale
assets do not reach it.

## Checklist for action

- [ ] Run a live OSS dry-registration for KBLI 55204 with two separate
      lokasi usaha in different desa, and record: (i) whether OSS demands
      the Rp10bn investment value per address or per kabupaten/kota;
      (ii) whether it issues one sertifikat standar or one per location.
      This single test resolves Q1 and the 55204 scope-fit risk at once.
- [ ] Get written confirmation (DPMPTSP Bali or licensed consultant)
      whether adding a KBLI to an **existing** PT PMA is treated as new
      PMA registration under the 2026-05-13 moratorium. Highest-value
      open question for this client.
- [ ] Obtain the 5 exact addresses and confirm whether they fall in one
      kabupaten or several — this decides whether Pasal 60-61's
      cross-regency KKPR track applies, and it is the difference between
      one and several DPMPTSP counterparties.
- [ ] Per villa, verify zoning (pink/tourism designation), land title
      (HGB or long-term Hak Sewa), and PBG/SLF status before any
      investment-value modelling. Their aggregate land+building valuation
      should be obtained now, since under Pasal 26(5) it counts toward
      the threshold.
- [ ] Correct the sibling capture's Q2 statement that the Rp10bn
      threshold is "excluding land and buildings" — for accommodation and
      property it is not (Pasal 26(5)). That sentence is currently
      client-facing-adjacent and materially understates feasibility.
- [ ] Log the Permenparekraf-4/2021-vs-OSS-matrix divergence on villa
      scale (finding Q5.2) as an open item against the sibling capture's
      unresolved primary-source checklist item; do not promote either
      document to the curated FAQ sink until it is closed.
- [ ] Do NOT promote any of this to `apps/backend-rag/data/curated_qa/`.
      Research stays ad-hoc and auditable per CLAUDE.md §15.
