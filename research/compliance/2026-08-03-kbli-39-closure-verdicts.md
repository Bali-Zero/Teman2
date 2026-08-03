---
date: 2026-08-03
domain: compliance
client_case: none
adversarial_review: codex
sources:
  # Investment list (the only instrument that can create a foreign-ownership reservation)
  - https://peraturan.bpk.go.id/Details/168534/perpres-no-49-tahun-2021
  - https://peraturan.bpk.go.id/Download/161562 # Perpres 49/2021 body (Pasal I angka 3/4/5 replace Lampiran I/II/III)
  - https://peraturan.bpk.go.id/Download/161563 # Perpres 49/2021 Lampiran I (priority fields, 69 pp)
  - https://peraturan.bpk.go.id/Download/161564 # Perpres 49/2021 Lampiran II (dialokasikan / kemitraan, 22 pp, 106 entries)
  - https://peraturan.bpk.go.id/Download/161565 # Perpres 49/2021 Lampiran III (conditions/caps, 4 pp, 37 entries)
  - https://peraturan.bpk.go.id/Details/161806/perpres-no-10-tahun-2021 # status: Berlaku, sole amendment 49/2021
  - https://peraturan.bpk.go.id/Download/154474 # Perpres 10/2021 body (Pasal 2, 3, 5, 6, 7)
  - https://peraturan.bpk.go.id/Download/154475 # original Feb-2021 Lampiran zip (timing control)
  - https://peraturan.go.id/files/ps49-2021.pdf # consolidated copy used for the independent 300dpi OCR pass
  # Risk-based licensing
  - https://peraturan.bpk.go.id/Download/394946 # PP 28/2025 Lampiran I.J–I.P (incl. I.L Pariwisata, I.P Ekraf)
  - https://peraturan.bpk.go.id/Download/394944 # PP 28/2025 Lampiran I.H (construction)
  - https://peraturan.bpk.go.id/Download/394948 # PP 28/2025 Lampiran II (PB-UMKU)
  - https://peraturan.bpk.go.id/Download/394633 # Permeninves/BKPM 5/2025 (Pasal 10, 26)
  - https://jdih-storage.bkpm.go.id/jdih/jdih/2025Permeninvesthil005-.pdf
  # Sectoral standards
  - https://peraturan.bpk.go.id/Details/331639 # Permenpar 6/2025 (LIVE tourism standards; revokes Permenparekraf 4/2021)
  - https://peraturan.bpk.go.id/Download/393675 # Permenpar 6/2025 full text, 562 pp
  - https://peraturan.bpk.go.id/Details/169198 # Permenparekraf 4/2021 — status "Tidak Berlaku"
  - https://jdih.kemenpora.go.id/cms/uploads/produkhukum/8/2/4/permen-9-2026.pdf # Permenpora 9/2026 (Industri Olahraga)
  - https://jdih.kemenpora.go.id/produk_hukum/download/701/pp-46-2024.pdf # PP 46/2024 Keolahragaan
  - https://peraturan.bpk.go.id/Download/197117 # UU 11/2022 Keolahragaan
  - https://www.peraturan.go.id/files/permenekraf-no-7-tahun-2025.pdf # Permen Ekraf 7/2025
  - https://peraturan.bpk.go.id/Download/354517 # UU 32/2024 (replaces UU 5/1990 Pasal 34)
  - https://peraturan.bpk.go.id/Download/35455 # UU 5/1990 KSDAE
  - https://peraturan.bpk.go.id/Download/35929 # PP 36/2010 Pengusahaan Pariwisata Alam
  - https://peraturan.bpk.go.id/Download/27961 # UU 22/2009 LLAJ (Pasal 35, 41(2))
  - https://peraturan.bpk.go.id/Download/154551 # PP 30/2021 (terminal, Pasal 36/39/40)
  - https://peraturan.bpk.go.id/Download/67598 # Perpres 191/2014 (subsidised fuel)
  - https://peraturan.bpk.go.id/Download/28462 # UU 18/2008 Pengelolaan Sampah
  # Classification
  - https://www.bps.go.id/id/publication/2026/04/22/909d503355d2b7664e43dea8/tabel-konversi-kbli-2020-kbli-2025.html
  - https://ppid.bps.go.id/upload/doc/Peraturan_Badan_Pusat_Statistik_No__2_Tahun_2020_Klasifikasi_Baku_Lapangan_Usaha_Indonesia_1658133734.pdf
---

## Adversarial review — what it changed, and what it left standing

Graded by **Codex GPT-5.6 (`terra`, high effort), 2026-08-03**, on fresh context, instructed to
default to DEFECTIVE. Not the same family as the lanes that produced this document — which matters,
because the eight refute lanes above were **Claude agents**, i.e. the same family as the research
lanes they graded. An earlier draft of this frontmatter called that pass "cross-family"; it was not,
and the label has been corrected to name the seat that actually did this review.

**Overturned in the companion code artifact** (`perpres_umkm_reservation_relation.py`, same day):
the fix originally let the BPS crosswalk override number-identity unconditionally. The review found
a spurious edge in the shipped file — `14111 Industri Pakaian Jadi → 17091 Industri Kertas Tisu`,
alongside the correct `14111 → 14111` — under which one bad edge demoted a correctly-judged row into
a bucket nothing evaluates. **34 rows** had left the evaluated buckets that way. Corrected: identity
wins where it exists, the crosswalk resolves only what identity cannot. It also caught a false
summary claim — 66 live pages were described as "all published `TERBUKA/100%`" when **63** are:
`47222` is `TERTUTUP/0%`, `47221` `TERBATAS/special`, `79110` `TERBATAS/100%`.

**Three claims in THIS document it did not accept, recorded rather than argued away:**

- **`86995` (massage) is counted among the 19 "no restriction anywhere".** The document itself
  states that the decisive Permenkes 14/2021 annex is image-only and was not read. The defensible
  claim is *"no PMA reservation found in the Perpres"*, not *"no restriction anywhere"* — and the
  total of 19 inherits that weakness.
- **`38110` (waste collection) is listed as "clean — publish as open".** No local instrument was
  read for any code in this pass; the Perpres badge may be removable, but "publish as open" is past
  the evidence.
- **`95291` (tailoring) is `RESERVED` at high confidence.** The crosswalk the companion tool uses
  maps `95291 → [95291, 95400]`, i.e. a split whose heirs are not automatically co-reserved.
  Materially it may well be reserved; *high confidence* without adjudicating the heir is not earned.

**What it confirmed by re-running:** 181 rows conserved, buckets sum correctly, `retired-2020-code`
is genuinely 0, every `split-heirs` row genuinely has more than one heir, and the historical "30 of
30 had a live heir" is reproducible by emulating the old number-identity lookup.

The corrections above are applied to the code; the three verdict caveats are recorded here and are
**not** silently rewritten in the tables below — a reader comparing this section with row `86995`,
`38110` or `95291` should see the tension, because that tension is the honest state of the evidence.


# The 39 codes we publish as "closed to PT PMA" — closure verdicts

**Audience:** agency owner. **Purpose:** decide which red badges come down, which stay, and which
stay up with a different sentence on them.

**Premise, verified this pass, not assumed.** I fetched four of the 39 live pages
(`balizero.com/kbli/{86995,38110,93121,55201}`) on 2026-08-03: all four carry the strings
"closed to PT PMA" / "Reserved for MSME", three also "Blocked for PT PMA". A negative control
(`62010`) returns zero such markers, so the probe discriminates between a page that carries the
badge and one that does not. **The badge population is larger than these 39** — `70209`, which is
not in this set, carries it too. Clearing these 39 does not clear the class.

---

## Bottom line

Of the 39 codes the site publishes as closed to PT PMA, **only 9 are actually closed to a foreign
company by an operative instrument** — and two of those nine are closed only as to a *named
sub-activity*, not the whole code (Perpres 10/2021 Pasal 5(5) scopes a Lampiran II reservation to
the wording in the "Bidang Usaha" column, so KBLI 55209 is reserved only for *Guest House* and
KBLI 43110 only for *demolition using simple and intermediate technology*). A further **11 carry a
real, located requirement that is not an ownership rule at all** — a hygiene or business standard,
a personal permit on a foreign individual, a State-concession regime, a partnership duty that
attaches only to international championships, a subsidised-fuel assignment regime — every one of
which a PT PMA can satisfy, and none of which supports the word "closed". The remaining **19 have
no restriction anywhere**: not in Perpres 49/2021 Lampiran I, II or III, not in the closed list,
not in any sectoral instrument read in this pass — their red badge is unsupported and should come
down. Separately, and cutting across all three buckets, **for 17 of the 39 a named, specific,
still-unread document could move the client-facing answer** — but note *what kind* of movement is
still possible: the investment annexes themselves were read end-to-end by several independent lanes
with positive controls, so **no new Perpres-level reservation can appear** among these codes; what
remains open is downstream (a sectoral licensing condition, a scale question, a Bali local
instrument, or whether OSS will let a PT hold a code drafted for a natural person). The single
structural weakness under all nine reservations is that **no investment instrument has ever been
re-issued in KBLI-2025 numbering**: every 2025-code verdict here rests on the BPS conversion table,
which is a statistical artefact with no legal force.

**Root cause of the false closures, in one sentence:** the dataset inferred "OSS/PP 28/2025
publishes no *Usaha Besar* scale row → the activity is reserved for MSME → closed to PT PMA."
That inference is invalid twice over. A missing scale row is licensing-portal data, not a legal
reservation; and Permeninves/BKPM 5/2025 Pasal 26(1) — *"Badan usaha … yang dikategorikan PMA
merupakan usaha besar"* — inverts the causation: being *Usaha Besar* is a **consequence** of PMA
status, not a gate a PMA must first pass. That single bad inference accounts for the majority of
the 19 unsupported badges.

---

## 1. Verdict table

Verdict key: **RESERVED** = closed to PT PMA by the Lampiran II *dialokasikan* column ·
**PARTIAL** = reserved only as to a named sub-activity · **REQUIREMENT** = a real condition
located, but not an ownership rule · **PARTNERSHIP** = duty to partner, no equity effect ·
**NONE** = no restriction located.

| Code | Activity (KBLI 2025) | Verdict | Instrument + locator | Source URL | Confidence |
|---|---|---|---|---|---|
| 55201 | Aktivitas Rumah Tinggal Sewa (Homestay) | **RESERVED** | Perpres 49/2021 Lampiran II p.15, entry 48 sub-row *Pondok Wisata*, KBLI 55130, tick in *dialokasikan* | [Lampiran II](https://peraturan.bpk.go.id/Download/161564) | high |
| 55202 | Aktivitas Hostel Remaja (Youth Hostel) | **NONE** | none — absent from Lampiran I/II/III; Permenpar 6/2025 KBLI 55191 standard has zero ownership conditions | [Lampiran II](https://peraturan.bpk.go.id/Download/161564) · [Permenpar 6/2025](https://peraturan.bpk.go.id/Download/393675) | high |
| 55203 | Aktivitas Vila | **RESERVED** | Perpres 49/2021 Lampiran II p.15, entry 48 sub-row *Vila*, KBLI 55193, *dialokasikan* | [Lampiran II](https://peraturan.bpk.go.id/Download/161564) | high on the annex fact / medium on "no PMA can hold it today" |
| 55209 | Aktivitas Penyediaan Akomodasi Jangka Pendek Lainnya | **PARTIAL** | Lampiran II p.15, entry 48 sub-row *Guest House*, KBLI 55199 — scoped by Perpres 10/2021 **Pasal 5(5)** to "Guest House" only, not the residual code | [Lampiran II](https://peraturan.bpk.go.id/Download/161564) · [Perpres 10/2021](https://peraturan.bpk.go.id/Download/154474) | high |
| 55300 | Aktivitas Penyediaan Bumi Perkemahan, Persinggahan Karavan dan Taman Karavan | **NONE** | none — 2020 code 55192 absent from all three annexes; Permenpar 6/2025 KBLI 55192 standard has zero ownership conditions | [Lampiran II](https://peraturan.bpk.go.id/Download/161564) · [Permenpar 6/2025](https://peraturan.bpk.go.id/Download/393675) | high |
| 56102 | Food stalls / itinerant food service (2020 ancestors 56103, 56104, 56109) | **REQUIREMENT** | Permenpar 6/2025 Lampiran, standards for 56103/56104/56109 — Sertifikat Standar + hygiene (HSP/SLHS). No 56xxx entry anywhere in Perpres 49/2021 | [Permenpar 6/2025](https://peraturan.bpk.go.id/Download/393675) | high |
| 56304 | Aktivitas Kedai Minuman | **REQUIREMENT** | Permenpar 6/2025 Lampiran, "KBLI (56304) KEDAI MINUMAN", risk Menengah Rendah — Sertifikat Standar + HSP; *Penggolongan Usaha* is "-" (no scale gating) | [Permenpar 6/2025](https://peraturan.bpk.go.id/Download/393675) | high |
| 56306 | Aktivitas Penyediaan Minuman Keliling/Tempat Tidak Tetap | **REQUIREMENT** | Permenpar 6/2025 Lampiran p.170, "KBLI (56306)" — Sertifikat Standar + HSP; no scale gating | [Permenpar 6/2025](https://peraturan.bpk.go.id/Download/393675) | high |
| 70100 | Aktivitas Kantor Pusat | **NONE** | none — zero rows across **all 22** PP 28/2025 annex files and all three Perpres annexes; falls to Perpres 10/2021 Pasal 3(1)(d) + 3(2) | [Perpres 49/2021](https://peraturan.bpk.go.id/Details/168534/perpres-no-49-tahun-2021) | high |
| 70201 | Aktivitas Konsultansi Manajemen dan Bisnis Pariwisata | **NONE** | none — Lampiran II entry 49 is 70202 (transport consultancy), *not* 70201; PP 28/2025 I.L entry 27 has an empty *Persyaratan* column | [Lampiran II](https://peraturan.bpk.go.id/Download/161564) · [PP 28/2025](https://peraturan.bpk.go.id/Download/394946) | medium |
| 73300 | Aktivitas Kehumasan | **REQUIREMENT** | Two instruments **conflict**: PP 28/2025 Lampiran I.P entry 9 (70203) gives Mikro/Kecil/Menengah, no Besar; Permen Ekraf 7/2025 Lampiran I entry 9 gives **UMKMB** (incl. Besar). No investment-annex entry either way | [PP 28/2025](https://peraturan.bpk.go.id/Download/394946) · [Permen Ekraf 7/2025](https://www.peraturan.go.id/files/permenekraf-no-7-tahun-2025.pdf) | medium |
| 74199 | Aktivitas Desain Khusus Lainya YTDL | **REQUIREMENT** | PP 28/2025 Lampiran I.P entry 4 (74149) *Skala Usaha* = Mikro, Kecil only; Permen Ekraf 7/2025 Lampiran I entry 4 = **UMK** (the only 1 of its 16 codes so marked). Not a Pasal 5(1)(a) reservation | [PP 28/2025](https://peraturan.bpk.go.id/Download/394946) · [Permen Ekraf 7/2025](https://www.peraturan.go.id/files/permenekraf-no-7-tahun-2025.pdf) | medium |
| 79901 | Jasa Informasi Pariwisata | **NONE** | none — 2020 code 79911 in no annex; PP 28/2025 I.L entry 32 *Persyaratan* = "-" | [Lampiran II](https://peraturan.bpk.go.id/Download/161564) · [PP 28/2025](https://peraturan.bpk.go.id/Download/394946) | medium |
| 79902 | Jasa Informasi Daya Tarik Wisata | **NONE** | none — 2020 code 79912 in no annex; PP 28/2025 I.L entry 33 *Persyaratan* = "-" | [Lampiran II](https://peraturan.bpk.go.id/Download/161564) · [PP 28/2025](https://peraturan.bpk.go.id/Download/394946) | medium |
| 79903 | Jasa Pramuwisata | **RESERVED** | Perpres 49/2021 Lampiran II p.16, entry 56 *Jasa pramuwisata*, KBLI 79921, tick in *dialokasikan* | [Lampiran II](https://peraturan.bpk.go.id/Download/161564) | high |
| 86995 | Aktivitas Rumah Pijat | **NONE** | none located — 2020 code 96121 absent from all three annexes; OSS requires only *Sertifikat Laik Sehat* | [Lampiran II](https://peraturan.bpk.go.id/Download/161564) · [Perpres 10/2021](https://peraturan.bpk.go.id/Download/154474) | medium |
| 91424 | Taman Wisata Alam (2020: 91034) | **REQUIREMENT** | UU 5/1990 Pasal 34 as replaced by UU 32/2024 Pasal I angka 15 — TWA management is a **State** function; private parties enter by permit/concession over the utilisation zone (PP 36/2010 Pasal 8(3): *perorangan, badan usaha, koperasi*; Penjelasan includes *badan usaha swasta*) | [UU 32/2024](https://peraturan.bpk.go.id/Download/354517) · [PP 36/2010](https://peraturan.bpk.go.id/Download/35929) | high |
| 93115 | Fasilitas Olahraga Beladiri | **NONE** | none — no 93xxx in any Perpres annex; Permenpora 9/2026 §F standard has zero ownership terms, and its Pasal 80(2)(a) expressly supervises *"usaha sektor Keolahragaan PMA"* | [Permenpora 9/2026](https://jdih.kemenpora.go.id/cms/uploads/produkhukum/8/2/4/permen-9-2026.pdf) | high |
| 93119 | Pengelolaan Fasilitas Olahraga Lainnya | **NONE** | none — as 93115. PP 28/2025 I.L entry 50 omits Menengah *and* Besar, which is a licensing-scale row, not a restriction | [PP 28/2025](https://peraturan.bpk.go.id/Download/394946) · [Permenpora 9/2026](https://jdih.kemenpora.go.id/cms/uploads/produkhukum/8/2/4/permen-9-2026.pdf) | high |
| 93121 | Klub Sepak Bola | **NONE** | none — no 9312x code in any Perpres annex or in PP 28/2025 at all; Permenpora 9/2026 issues no club standards | [Lampiran II](https://peraturan.bpk.go.id/Download/161564) · [Permenpora 9/2026](https://jdih.kemenpora.go.id/cms/uploads/produkhukum/8/2/4/permen-9-2026.pdf) | high |
| 93122 | Klub Golf | **NONE** | none — every golf reference attaches to a *facility* code (93114 "Lapangan Golf", which PP 28/2025 licenses at **Menengah/Besar**), never to the club code | [PP 28/2025](https://peraturan.bpk.go.id/Download/394946) · [Permenpora 9/2026](https://jdih.kemenpora.go.id/cms/uploads/produkhukum/8/2/4/permen-9-2026.pdf) | high |
| 93123 | Klub Renang | **NONE** | none — as 93121; swimming *facilities* are 93113, a separate code | [Lampiran II](https://peraturan.bpk.go.id/Download/161564) · [Permenpora 9/2026](https://jdih.kemenpora.go.id/cms/uploads/produkhukum/8/2/4/permen-9-2026.pdf) | high |
| 93125 | Klub Tinju | **NONE** | none — as 93121; boxing *sasana* is 93115, a separate code | [Lampiran II](https://peraturan.bpk.go.id/Download/161564) · [Permenpora 9/2026](https://jdih.kemenpora.go.id/cms/uploads/produkhukum/8/2/4/permen-9-2026.pdf) | high |
| 93126 | Klub Bela Diri | **NONE** | none — as 93121; martial-arts *facility* is 93115 | [Lampiran II](https://peraturan.bpk.go.id/Download/161564) · [Permenpora 9/2026](https://jdih.kemenpora.go.id/cms/uploads/produkhukum/8/2/4/permen-9-2026.pdf) | high |
| 93128 | Klub Boling | **NONE** | none — as 93121; the bowling *venue* is 93113 (Permenpora 9/2026 §C carries a dedicated "Usaha Bowling" sub-standard) | [Lampiran III](https://peraturan.bpk.go.id/Download/161565) · [Permenpora 9/2026](https://jdih.kemenpora.go.id/cms/uploads/produkhukum/8/2/4/permen-9-2026.pdf) | high |
| 93129 | Klub Olahraga Lainnya | **NONE** | none — as 93121. Note KBLI 2025 **added e-sport clubs** to this code (BPS change note) | [BPS conversion table](https://www.bps.go.id/id/publication/2026/04/22/909d503355d2b7664e43dea8/tabel-konversi-kbli-2020-kbli-2025.html) | high |
| 93192 | Aktivitas Juri dan Wasit Profesional | **REQUIREMENT** | UU 11/2022 Pasal 69(1) + **Pasal 71**; PP 46/2024 Pasal 103 — a foreign referee/judge needs competency certificate, federation recommendation and a government permit. A **personal** licence, not an equity rule | [UU 11/2022](https://peraturan.bpk.go.id/Download/197117) · [PP 46/2024](https://jdih.kemenpora.go.id/produk_hukum/download/701/pp-46-2024.pdf) | high |
| 93194 | Badan Regulasi dan Liga Olahraga | **PARTNERSHIP** | UU 11/2022 Pasal 54(3) (*dapat*) hardened by **Permenpora 9/2026 Pasal 73(1)**: a foreign entity organising an **international-level** championship **wajib** partner with the national federation and/or a professional sport organisation | [Permenpora 9/2026](https://jdih.kemenpora.go.id/cms/uploads/produkhukum/8/2/4/permen-9-2026.pdf) | high |
| 93195 | Aktivitas Olahraga Tradisional | **REQUIREMENT** | Permenpora 9/2026 Lampiran I §I, mandatory Standar Kegiatan Usaha (risk Rendah): 8 cumulative *persyaratan*, Sertifikat Standar (Pasal 78), sanctions to revocation (Pasal 84). No ownership term anywhere | [Permenpora 9/2026](https://jdih.kemenpora.go.id/cms/uploads/produkhukum/8/2/4/permen-9-2026.pdf) | high |
| 93197 | Aktivitas Olahragawan/Atlet Independen | **NONE** | none — athletes are *not* within the Pasal 69(1) *Tenaga Keolahragaan* list, which is precisely why 93192 attracts a permit and 93197 does not | [UU 11/2022](https://peraturan.bpk.go.id/Download/197117) | high |
| 93199 | Aktivitas Lainnya yang Berkaitan dengan Olahraga YTDL | **NONE** | none — neither 2020 predecessor (93199, **51106**) appears in any annex; critically the 49% aviation cap in Lampiran III covers only 51101/51102/51109, **not** 51106 | [Lampiran III](https://peraturan.bpk.go.id/Download/161565) | medium |
| 95291 | Aktivitas Vermak Pakaian | **RESERVED** | Perpres 49/2021 Lampiran II p.16, entry 57 sub-row *Vermak pakaian*, KBLI 95291, *dialokasikan*. Code number **unchanged** 2020→2025 | [Lampiran II](https://peraturan.bpk.go.id/Download/161564) | high |
| 96100 | Aktivitas Pencucian dan Pembersihan Produk Tekstil dan Bulu | **RESERVED** | Lampiran II p.16, entry 57 sub-row *Penatu*, KBLI 96200, *dialokasikan* | [Lampiran II](https://peraturan.bpk.go.id/Download/161564) | high |
| 96210 | Aktivitas Penataan dan Pangkas Rambut | **RESERVED** | Lampiran II p.16, entry 57 sub-row *Pangkas rambut/barber shop*, KBLI 96111, *dialokasikan* | [Lampiran II](https://peraturan.bpk.go.id/Download/161564) | high |
| 96220 | Aktivitas Perawatan Kecantikan dan Perawatan Kecantikan Lainnya | **RESERVED** | Lampiran II p.16, entry 57 sub-row *Salon kecantikan*, KBLI 96112, *dialokasikan*. **Does not reach SPA (96230) or fitness** | [Lampiran II](https://peraturan.bpk.go.id/Download/161564) | high |
| 43110 | Pembongkaran (demolition) | **PARTIAL** | Lampiran II p.10, entry 37 *"Pembongkaran yang menggunakan teknologi sederhana dan madya"*, KBLI 43110, *dialokasikan* — Pasal 5(5) scopes it to that segment. **PP 28/2025 Lampiran I.H entry 39 publishes a Besar row written expressly for "BUJK PMA"** | [Lampiran II](https://peraturan.bpk.go.id/Download/161564) · [PP 28/2025 I.H](https://peraturan.bpk.go.id/Download/394944) | high |
| 52211 | Aktivitas Terminal Darat | **REQUIREMENT** | UU 22/2009 Pasal 35 (private parties may build *goods* terminals for own use); PP 30/2021 Pasal 39(2)/40(3) — public passenger terminals stay a government responsibility but may be **kerja-sama'd with swasta**. PP 28/2025 Lampiran II PB-UMKU *Sertifikat Penyelenggaraan Terminal Barang Untuk Kepentingan Sendiri* | [UU 22/2009](https://peraturan.bpk.go.id/Download/27961) · [PP 30/2021](https://peraturan.bpk.go.id/Download/154551) | medium |
| 47771 | Perdagangan Eceran Minyak Tanah (kerosene retail) | **REQUIREMENT** | Perpres 191/2014 Pasal 3(1), 8(1), 9 — subsidised-fuel distribution is an **assignment** to a Badan Usaha already holding an *Izin Usaha Niaga Umum* plus storage and distribution facilities. Commercial gate, nationality-neutral | [Perpres 191/2014](https://peraturan.bpk.go.id/Download/67598) | medium |
| 38110 | Pengumpulan Limbah atau Sampah Tidak Berbahaya | **NONE** | none — absent from all three annexes. The only 38xxx row in Lampiran II is 38302, and its tick is in **kemitraan**, not *dialokasikan*. UU 18/2008 Pasal 17(1) imposes a universal local permit on *any* operator | [Lampiran II](https://peraturan.bpk.go.id/Download/161564) · [UU 18/2008](https://peraturan.bpk.go.id/Download/28462) | high |

---

## 2. SAFE TO REOPEN — 19 codes whose red badge is unsupported

No restriction was located in any operative instrument, and the adversarial pass agreed. **Take the
"closed to PT PMA" / "Reserved for MSME" badge down on all 19.** They are not equally clean, so
they split into two publishing treatments.

### 2a. Clean — publish as open (14)

`55202` · `55300` · `70100` · `93115` · `93119` · `93121` · `93122` · `93123` · `93125` ·
`93126` · `93128` · `93129` · `93197` · `38110`

For these the negative is *affirmative*, not merely an absence: Perpres 10/2021 Pasal 3(1)(d) puts
an activity in none of the three annexes into a residual class, and Pasal 3(2) states verbatim that
such fields *"dapat diusahakan oleh semua Penanam Modal"*. The residual class was verified by
enumerating all three exclusions, not by one failed lookup.

Three of these carry positive corroboration worth putting on the page:

- **93115 / 93119 / 93121–93129** — Permenpora 9/2026 Pasal 80(2)(a) expressly assigns the Minister
  supervision of *"usaha sektor Keolahragaan PMA yang berlokasi di luar KEK, KPBPB, dan Otorita Ibu
  Kota Nusantara"*. The sport regulator legislates **for** foreign-invested sport businesses.
- **93122 (Klub Golf)** — the adjacent facility code 93114 "Lapangan Golf" is licensed by PP 28/2025
  at **Menengah/Besar**, i.e. expressly at the scale a PMA occupies. The opposite of a closure.
- **38110** — the one 38xxx row in Lampiran II (38302) sits in the **kemitraan** column, proved by
  bbox coordinate against that page's own headers. So the waste family *is* reachable by the annex,
  and 38110 is in neither column. That makes the absence diagnostic rather than accidental.

Two carry a caveat that belongs in the copy but does not justify a closed badge:

- **93197 (independent athlete)** — the KBLI 2025 uraian defines it as an athlete *"yang bertindak
  atas nama perorangan"*. Whether OSS will let a PT (let alone a PT PMA) hold a code drafted for a
  natural person is a **registrability** question, not an ownership prohibition. Do not publish it
  as either "closed" or "confirmed available".
- **38110** — UU 18/2008 Pasal 18(2) delegates *which types* of waste business may be licensed to a
  **Perda**. Universal permit duty, nationality-neutral, but a Bali local instrument could bite.

### 2b. Reopen with the gap stated (5)

`70201` · `79901` · `79902` · `86995` · `93199`

Same verdict — no restriction located — but each carries a declared gap the pass did not fully
close. **Correct wording is "no reservation found in the investment list; [named] still to be
confirmed", never "confirmed open".**

- **70201 / 79901 / 79902** — these three lanes declared the live tourism standards regulation
  (Permenpar 6/2025) unread, and rated themselves medium. That gap was in fact **closed by sibling
  lanes in the same pass**, which downloaded the 562-page instrument and measured it: *"penanaman
  modal asing"* appears exactly **twice**, both inside the definitions article, where it defers
  outward to the investment law; all 70 hits of *"kepemilikan"* are premises tenure or certificate
  holding; *"dialokasikan"* appears **zero** times. I record this as a cross-lane closure rather
  than raising their stated confidence, because the lanes that owned those codes did not read it
  themselves. Note also the finding that matters most for 79902: **79912 is "Jasa Informasi Daya
  Tarik Wisata", not pramuwisata** — a crosswalk that confuses the two would drag the genuine 79921
  reservation onto the wrong 2025 code.
- **86995 (Rumah Pijat)** — annex absence independently reproduced by a stricter column-position
  method, and keyword sweeps for *pijat / SPA / kebugaran / refleksi / panti* across all three
  annexes return zero. But the Permenkes 14/2021 annex could not be read. Note the structural bound:
  UU 25/2007 Pasal 12 reserves the designation of closed/conditional fields to a **Presidential
  Regulation**, so a Permenkes could impose facility, competency or legal-form conditions but
  **cannot** impose a foreign-capital cap.
- **93199** — residual bucket. The valuable finding: 2020 code **51106 (air transport for sport)**
  folded into it, and 51106 is **not** among the Lampiran III aviation entries (51101/51102/51109)
  that carry the 49% + single-majority cap. So the cap does **not** reach this code.

---

## 3. GENUINELY RESTRICTED — 20 codes, three very different things

### 3a. Column: *dialokasikan* — reservation. Closed to a PT PMA. (7 full + 2 partial)

The Lampiran II tick sits in the **DIALOKASIKAN UNTUK KOPERASI DAN UMKM** column, which Perpres
10/2021 Pasal 5(1)(a) defines as *"Bidang Usaha yang dialokasikan bagi Koperasi dan UMKM"*, with
Pasal 5(2)(c) capping business capital at Rp10bn excluding land and buildings. **Commercially: a
PT PMA cannot enter.** Not because of Pasal 7(1) — that article conditions the *investor*, and is
used here only as the definitional bridge — but because the activity is allocated away.

The one textual proof that this excludes new large entrants: **Pasal 5(6)** gives an incumbent
Koperasi/UMKM that *grows into* Usaha Besar an express right to continue (with a Pasal 5(7)
partnership duty). That carve-out would be superfluous if an Usaha Besar could simply enter.

**Fully reserved (7):** `55201` Homestay · `55203` Vila · `79903` Pramuwisata · `95291` Vermak
pakaian · `96100` Penatu · `96210` Pangkas rambut · `96220` Salon kecantikan.

**Partially reserved (2) — this is the commercially valuable finding:**

- **`55209`** — the annex names *"Guest House"* (KBLI 55199). Perpres 10/2021 **Pasal 5(5)**:
  where a KBLI covers more than one Bidang Usaha, the allocation *"hanya berlaku bagi Bidang Usaha
  yang tercantum dalam kolom Bidang Usaha tersebut"*. KBLI 2020 defines 55199 as expressly
  **residual** — accommodation "belum termasuk dalam kelompok 55191 sd. 55194", enumerating
  bungalows, cottages, motels, *guesthouse* and *"dan lain-lain"*. Publishing the whole of 55209 as
  closed is wrong: bungalows and cottages are not the reserved item. **Corollary:** a youth hostel
  is *not* inside 55199 (it is 55191), so the reservation does not migrate into hostel operations.
- **`43110`** — the annex names *"Pembongkaran yang menggunakan teknologi sederhana dan madya"*.
  KBLI 2025's own uraian for 43110 covers *"pembongkaran bangunan dengan material berbahaya;
  pembongkaran terkontrol"* — hazardous-material and controlled demolition are plainly not
  simple/intermediate technology, so Pasal 5(5) bites. And **PP 28/2025 Lampiran I.H entry 39
  publishes a Besar block whose persyaratan is written for BUJK PMA**: *"Untuk BUJK PMA: Penanam
  modal asing/pemegang saham asing merupakan badan usaha jasa konstruksi berbadan hukum di negara
  asal."* The operative licensing regulation contemplates a foreign demolition contractor. The
  badge on 43110 is wrong for the code as a whole.

**Scope warnings to carry into client copy:**

- `96220` reaches salon/beauty care only. **SPA (2020 96122 → 2025 96230) and fitness (96129 →
  96230) are NOT reserved** — verified in the BPS table and by keyword sweep of all three annexes
  (the six "SPA" hits in Lampiran I are "SPAM", *Sistem Penyediaan Air Minum*).
- `96100` — the slice of old 96200 that went to the **new** intermediation code **96400** is in no
  annex. A laundry *platform/intermediation* business is not caught.
- `55203` — do **not** lean on "villas are intrinsically owner-operated". The live sectoral
  definition dropped that element: Permenpar 6/2025 defines *Usaha Villa* with no owner-management
  requirement.

### 3b. Column: none — a real requirement, but not an ownership rule (10)

**Commercially: a PT PMA can hold every one of these.** The badge must change from "closed" to the
actual condition.

| Code | What the condition actually is | What a foreign client must do |
|---|---|---|
| `56102`, `56304`, `56306` | Permenpar 6/2025 business standard: Sertifikat Standar + hygiene label (HSP) / SLHS. *Penggolongan Usaha* is "-" — **no scale gating at all** | Obtain the hygiene label and standard certificate. Certificate route for a PMA is via an **LSPr** |
| `74199` | PP 28/2025 I.P + Permen Ekraf 7/2025 publish only a **UMK** standard for the 2020 ancestor 74149 | Confirm with BKPM whether a Besar-scale filing is accepted; not a reservation |
| `73300` | PP 28/2025 says Mikro/Kecil/Menengah; Permen Ekraf 7/2025 says **UMKMB** (incl. Besar). Two primary instruments **disagree** | Do not state either as settled — see §4 |
| `91424` | UU 5/1990 Pasal 34 as replaced by UU 32/2024: **TWA management is a State function**. Private entry is by permit/concession over the *zona pemanfaatan* | Structure as a nature-tourism concession, not as ownership of the park. PP 36/2010 expressly admits *badan usaha swasta* and its Pasal 26 Penjelasan routes capital cooperation back to the investment law — where this code is absent |
| `93192` | UU 11/2022 Pasal 71 + PP 46/2024 Pasal 103: a **foreign individual** referee/judge needs a competency certificate, federation recommendation and a government permit | A personal licence for the person, not a cap on the company |
| `93195` | Permenpora 9/2026 §I: mandatory standard, 8 cumulative requirements, Sertifikat Standar, sanctions to revocation | Meet the standard. Also settle the classification risk in §4 |
| `52211` | UU 22/2009 Pasal 35 permits private **goods** terminals for own use; PP 30/2021 Pasal 39(2)/40(3) opens public passenger terminal construction and operation to *kerja sama* with **swasta** (but never *pengawasan operasional*) | Enter via the government kerja-sama / KPBU route, or operate a goods terminal for own use under the PB-UMKU |
| `47771` | Perpres 191/2014: subsidised kerosene is distributed under **assignment** to a Badan Usaha holding an *Izin Usaha Niaga Umum* plus storage and distribution facilities | A commercial and licensing threshold, nationality-neutral. Note the immediately adjacent code 47772 (LPG 3kg) *does* carry a **Besar** row |

Two of these overturn a claim previously published:

- **56102 carries a live vintage trap.** Permenpar 6/2025 still numbers in **KBLI 2020**. Its entry
  "(56102) WARUNG/RUMAH MAKAN" is scoped to a *permanent building* — that is **KBLI 2025 56101**,
  not 2025 56102. Matching on the digits "56102" across the vintage boundary attaches the wrong
  standard.
- **52211's earlier basis was overstated.** It is not true that the statute "nowhere grants private
  operation of public passenger terminals" — PP 30/2021 does, via kerja sama. What a private party
  cannot be is the free-standing *penyelenggara*.

### 3c. Column: none — partnership duty only (1)

- **`93194` (Badan Regulasi dan Liga Olahraga).** UU 11/2022 Pasal 54(3) is permissive (*dapat*),
  but **Permenpora 9/2026 Pasal 73(1)** hardens it: a foreign person or legal entity organising an
  **international-level** championship in Indonesia **wajib** partner with the national federation
  and/or a professional sport organisation. **Commercially:** full foreign ownership is fine; the
  duty is a mandatory partnership on international events, and it is **not** the Perpres
  *kemitraan-with-UMKM* column. Three practical points the earlier record could not state: the duty
  is now mandatory not optional; it is **narrowed to international-level** championships, so a
  purely domestic league does not trigger Pasal 73(1); and the eligible partner set is **wider**
  than the federation alone.

---

## 4. STILL UNDETERMINED — and the one document that would settle each

None of these can be resolved by re-reading the investment annexes; they were read end-to-end,
twice, by independent methods with positive controls. **No new Perpres-level reservation can
emerge among these 39 codes.** What is open is downstream.

**Fleet-wide, and the single biggest one:**

> **The KBLI 2020 → 2025 bridge has no legal instrument.** Every reservation above is written
> against a **KBLI 2020** code. No investment instrument has ever been re-issued in 2025 numbering
> — Permeninves/BKPM 5/2025 Pasal 10(1)(d)/(2) recognises the *"dialokasikan bagi koperasi dan
> UMK-M"* category and then refers its content out to *"ketentuan peraturan perundang-undangan
> mengenai bidang usaha penanaman modal"*, with no conversion table. Application to a 2025 code
> rests on the BPS crosswalk, a statistical artefact.
> **Settling document:** a BKPM instrument re-issuing Perpres 10/2021 Lampiran II in KBLI-2025
> numbering. Currently only **programmed** — Keppres 38/2025 is the *Program Penyusunan Peraturan
> Presiden Tahun 2026* and carries an RPerpres on Bidang Usaha Penanaman Modal. Programmed, **not
> enacted**. Re-check before any client filing.

**Also fleet-wide, and decisive for a Bali client:**

> **The Bali provincial moratorium.** The repo dataset asserts a Governor's letter
> **B.27.000/642/PM/DPMPTSP, effective 2026-05-13**, blocking all Low and Medium-Low risk KBLI for
> PMA. Most codes in this set are Rendah or Menengah Rendah, so it would catch them regardless of
> everything above. **Nobody in this pass read that letter at source** — our own capture
> `research/compliance/2026-06-09-bali-pma-kbli-moratorium-low-risk-block.md` rests on secondary
> reporting (Emerhub, TraceWorthy, InvestinAsia, sasbali).
> **Settling document:** the Governor's letter itself, obtained from DPMPTSP Bali.

**Per code:**

| Code | What is undetermined | The single document that settles it |
|---|---|---|
| `55203` | Whether a PT PMA can obtain it *today*. Permenparekraf 4/2021 legislated for supervision of *"usaha vila PMA"*, drafted **after** the reservation existed (verified against the original Feb-2021 annex). Best explanation is a grandfathered stock preserved by Perpres 10/2021 Pasal 6(4)(a), and the instrument is now revoked — but the tension is real | An OSS/BKPM ruling, or an actual accepted PT PMA filing on 55203 outside grandfathering |
| `55209` | Whether OSS applies Pasal 5(5) in practice or treats the whole residual code as reserved | A BKPM written confirmation of the "Guest House"-only scope (or a test filing on a bungalow/cottage operation) |
| `43110` | Same Pasal 5(5) scope question, plus whether a Permen PUPR/LPJK confines 43110 to BUJKN at every scale | The Permen PUPR on construction-services business entities (BUJK/BUJKA) |
| `70201`, `79901`, `79902` | Own-lane gap on Permenpar 6/2025, closed by sibling measurement (see §2b) but not by the owning lane | Nothing further; treat as clean once the sibling measurement is accepted |
| `73300` | Which governs: PP 28/2025 I.P (no Besar) or the later, lower Permen Ekraf 7/2025 (UMKMB) | A BKPM/OSS ruling, or an amendment to PP 28/2025 Lampiran I.P |
| `74199` | Whether the UMK scope attached to 2020 code 74149 carries to 2025 code 74199, and whether an unpublished Besar standard *bars* a Besar actor or merely leaves a standard unwritten | A BKPM/OSS written confirmation on the 74149→74199 carry-over |
| `86995` | Whether the health-sector standard imposes a legal-form condition | The **Permenkes 14/2021 annex** (as amended by 8/2022 and 17/2024), standard for 96121/86995 — the copy available is image-only |
| `91424` | Whether the current concession licensing (PB-PSWA / PB-PJWA) conditions holders on domestic capital | **PermenLHK 3/2021** PB-PSWA/PB-PJWA annex (and PermenLHK 8/2019) |
| `52211` | How far a PT PMA can go inside the PP 30/2021 Pasal 39(2)/40(3) kerja-sama route | The PermenHub on terminal kerja sama / KPBU |
| `47771` | Whether the *Izin Usaha Niaga Umum* holder or a subsidised-kerosene *penyalur* faces a domestic-capital condition | **Permen ESDM 29/2017 jo. 52/2018** on niaga migas, plus the BPH Migas penyalur/agen rules |
| `38110` | Which waste-business types may be licensed locally | The **Bali/Badung Perda** issued under UU 18/2008 Pasal 18(2) |
| `93195` | Classification collapse risk: if the business presents as a cultural performance studio it lands on **KBLI 90011 "Sanggar seni"**, which Lampiran III entry 37 subjects to **"Modal dalam negeri 100%"** | A BKPM classification confirmation, 93195 vs 90011, before publishing "open to PMA" |
| `93192`, `93197` | Whether a PT — let alone a PT PMA — may register a code defined as acting *"atas nama perorangan"* | A BKPM classification ruling on personal-capacity KBLI codes |
| `93199` | Residual bucket: the sub-activity determines the regime (sport aviation → civil aviation; mountain guiding → tourism; racing stables → animal health / gambling-adjacent) | No single document. The settling artefact is the client's own concrete activity description, re-derived against the KBLI 2025 uraira |

---

## 5. WHAT I COULD NOT CHECK

Stated plainly, because an honest gap is more useful than a full-looking table.

1. **Local law was not surveyed at all.** No Bali provincial Perda, no Badung/Gianyar/Denpasar
   kabupaten instrument, no RTRW or zoning rule was read for any of the 39. For land-intensive or
   itinerant activities — camping grounds (`55300`), mobile food and drink vending (`56102`,
   `56306`), waste collection (`38110`), massage houses (`86995`) — this is the **most plausible
   place a real, live condition sits**, and it is entirely unexamined. Separately, an unverified
   secondary report says **Perda Provinsi Bali 5/2016 defines a *pramuwisata* as a Warga Negara
   Indonesia** — a profession-nationality rule, not a shareholding rule, but material to `79903`
   for a Bali agency. Not verified at source; treat as a lead only.
2. **Land tenure is a separate legal axis and was not analysed.** Nothing here speaks to whether a
   foreign-owned entity can hold the land under a villa, a golf course or a camping ground.
3. **PP 28/2025 was read in part.** Annexes I.J–I.P and Lampiran II were read; **I.A–I.I and
   I.Q–I.V were not**. I.J–I.P contains every sibling code in the tourism, sport and creative-economy
   families, so the material rows are covered — but the claim "swept every annex" is not one I can
   make.
4. **Permenpar 6/2025 (562 pp) was keyword-swept, not read line by line.** The accommodation and
   food-service sections were read; the whole document was swept for ownership, nationality and PMA
   vocabulary. A condition expressed in wording none of those sweeps anticipated would be missed.
5. **These are scanned PDFs with a lying text layer, and that changes what a null result means.**
   Perpres 49/2021's annexes are Canon scans whose OCR corrupts digits: `79111` renders `79t11`,
   `96112` renders `96r12`, `95291` renders `9529t`, `01461` renders `ot46l`, and — worst —
   **`10794` renders `70794`**, a phantom 70xxx code that does not exist in the annex. A plain grep
   over these files is worthless in both directions. Every absence claim above was re-derived with
   substitution-tolerant *and* space-tolerant matchers validated against positive controls
   (`25200`, `51101`, `55193`, `55120`, `01111`, `71102`), plus full end-to-end human reads of all
   106 Lampiran II entries and all 37 Lampiran III entries. Where a single row decided a verdict,
   the page was rendered at 200–300 dpi and read as an image.
6. **The earlier "column proof" was wrong and was replaced.** The original method used a *global*
   absolute-x histogram to decide whether a tick sat in *dialokasikan* or *kemitraan*. The table's
   horizontal position shifts up to 16 characters page to page, so that method mis-files the two
   genuine kemitraan ticks on page 22 and yields 124/57 instead of the true 122/59. Replaced by a
   per-page normalisation against each page's own "KOPERASI" header: over all 181 ticks the
   distribution is cleanly bimodal (dialokasikan at offsets +5..+7, kemitraan at +19..+22, nothing
   between +8 and +18), and corroborated structurally — entries **1–60 are all dialokasikan, 61–106
   all kemitraan, zero entries carry both**. Anyone re-checking this work should use the normalised
   method, not the global one.
7. **BPK's website returns HTTP 403 to automated fetch for some pages.** Several lanes could not
   read the *Status* field for Perpres 10/2021 directly and relied on an independent witness
   reporting "Berlaku, amended only by Perpres 49/2021". Other lanes did land on it and confirmed
   exactly that. Recorded as a mixed-evidence point rather than a clean primary verification.
8. **One cross-family witness seat was unavailable.** In the sport-code lanes, `codex exec --search`
   is unsupported in the installed CLI build and the fallback invocation returned zero bytes. Those
   lanes report the absence of a witness rather than citing one they do not have.
9. **No OSS filing was attempted.** Every "practice" question above — Pasal 5(5) scoping,
   personal-capacity registrability, missing-Besar-row behaviour — is answerable only empirically,
   and this pass is documentary.
10. **This pass covers 39 codes, not the badge population.** `70209` carries the same badge and is
    not in this set. Note it is likely a *correct but over-scoped* badge: Lampiran II entry 49
    reserves *"Aktivitas konsultansi transportasi yang menggunakan teknologi sederhana dan madya"*
    (KBLI 2020 70202), whose 2025 heir is 70209 — so Pasal 5(5) should confine that reservation to
    the simple/intermediate-technology segment, exactly as with `55209` and `43110`. **The same
    Pasal 5(5) audit should be run across every remaining badged code before the class is declared
    clean.**

---

## Appendix — two inferences that must not be used again

Both produced false closures in the current dataset, and both were used as the *primary* ground.

1. **"OSS / PP 28/2025 publishes no *Usaha Besar* scale row → reserved for MSME → closed to PMA."**
   Invalid. A scale row is licensing configuration, not a reservation. And Permeninves/BKPM 5/2025
   **Pasal 26(1)** — *"Badan usaha … yang dikategorikan PMA merupakan usaha besar dan wajib
   mengikuti ketentuan minimum nilai investasi"* — makes Usaha Besar a **consequence** of PMA
   status. The dataset had the causation backwards. Two internal tells that this inference was
   being misused: for `52211` and `38110` the record's stated reason cites scale rows it does not
   have (`per_skala` is empty for 52211; 38110's six rows do not come from PP 28/2025, which
   publishes none) — a reason describing data that was never read.
2. **"Perpres 10/2021 Pasal 7(1) says a foreign investor may only conduct Usaha Besar → therefore
   this activity is closed."** Invalid as a source of closure. Pasal 7(1) conditions the
   **investor**, not the activity. It is legitimate only as a *definitional bridge* once a
   reservation has independently been located in the annex column — which is exactly how it is used
   for the nine RESERVED codes above, and exactly how it was misused for `93115`, `93119`, `86995`,
   `52211` and `38110`.

A useful marker for the next reviewer: a finding that reports `restriction_found: true` **and**
concedes in its own caveat that "no instrument I read states this activity may not be conducted at
large scale" is internally inconsistent. That pattern appeared twice in the prior round and both
instances were overturned here.
