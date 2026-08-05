---
date: 2026-08-06
domain: compliance
client_case: none — catalogue-wide determination affecting every PT PMA enquiry on these activities
adversarial_review: cross-family blind re-derivation (Sonnet proposes, Codex re-derives without sight of the proposal) over all 85 codes, plus a final on-disk check by the conductor which overturned 7 of 41
sources:
  - Perpres 10/2021 as amended by Perpres 49/2021, Lampiran II (vaulted PDF 161564, 180 ticks, 0 unresolved)
  - scripts/kbli_filiera/perpres_umkm_reservation_relation.py --json
  - data/source_documents/KBLI_2025_FINAL_CLEAN.json (bps_2020_ancestors, published pma_status)
---

# Lampiran II K-UMKM reservations: 85 codes adjudicated one by one

## What was found

`perpres_umkm_reservation_relation.py` reads the annex that allocates activities
to cooperatives and MSMEs. It sorts 181 rows into five buckets; the one that
matters is **`whole-row` — 85 codes where the live KBLI code IS the reserved
row**. Of those, **84 are published on our surfaces as `TERBUKA` with
`pma_max_asing: 100`** — fully open to foreign ownership.

The other buckets are the reason this is not a sweep: **57 `kemitraan-no-bar`**
(a duty to partner with K-UMKM, which an open PMA discharges — not a bar),
**12 `split-heirs`** (the annex reserves *Hotel Bintang I*, not all five star
ratings), **25 `segment-qualified`**. Restricting those would be as wrong as
leaving the 85 open.

## How each code was judged

Ten batches, two independent passes, generator ≠ grader: a Claude lane proposed
a verdict from the annex row, an OpenAI lane re-derived the same codes **blind**,
and disagreements were kept as disagreements rather than reconciled. The rule
given to both put the bias **against** restricting:

> a wrongly-restricted code costs a client a business they could lawfully run;
> that is not a safer error, it is a different error

with `REFUSE_UNCLEAR` a real option rather than a fallback.

**Result: agree 72 · disagree 13 · missing 0.** Agreed verdicts: PATCH 41,
REFUSE_BROADER 28, REFUSE_UNCLEAR 3. Arithmetic re-verified independently
(72+13 = 85, 85 unique codes, all source codes present, recomputed counts match).

## What the final check overturned, and why it matters

**18 of the 85 codes are not KBLI-2025 codes at all** — they are 2020 numbers
the crosswalk never resolved. Seven of them sat among the PATCH verdicts, and
**both families had agreed on all seven**, because neither was ever asked
whether the code exists and the record handed to them did not say. Agreement
measures fidelity to the evidence supplied, not truth.

Each of the seven resolves to **exactly one** 2025 heir with the same activity
name, so the determination transfers to the heir rather than being lost:

| 2020 (judged) | 2025 (real) | activity |
|---|---|---|
| `10391` | `10307` | Pembuatan Tempe Kedelai |
| `10392` | `10308` | Pembuatan Tahu Kedelai |
| `55120` | `55106` | Aktivitas Hotel Nonbintang |
| `55130` | `55201` | Rumah Tinggal Sewa (Homestay) |
| `55193` | `55203` | Aktivitas Vila |
| `79111` | `79110` | Aktivitas Agen Perjalanan |
| `79921` | `79903` | Jasa Pramuwisata |

None of the seven heirs was already in the 85, so no code is counted twice.

One further PATCH is withdrawn: **`47722`** rests on annex text the OCR
destroyed (`'B"rt"t dan obat farmasi...`), and the corrupted token is the one
that sets the scope. A verdict on illegible evidence is an unclear verdict.

**Actionable set: 40 codes, not 41.**

## Nothing has been written to the dataset

This document is the determination, not the patch. Section A is held for a
ruling; sections B and C are stated so the next session does not re-derive them.

## A. Accommodation & tourism — determination HELD for a ruling (5 codes)

These are Bali Zero's own market. The determination is the same as section B;
what differs is the consequence of being wrong, in both directions.

| 2025 code | activity | annex row (Lampiran II) | p | reached via 2020 |
|---|---|---|---|---|
| `55106` | Aktivitas Hotel Nonbintang | Hotel Melati | 15 | 55120 |
| `55201` | Aktivitas Rumah Tinggal Sewa (Homestay) | Pondok Wisata | 15 | 55130 |
| `55203` | Aktivitas Vila | Vila | 15 | 55193 |
| `79110` | Aktivitas Agen Perjalanan | Aktivitas agen perialanan wisata | 16 | 79111 |
| `79903` | Jasa Pramuwisata | Jasa pramuwisata | 16 | 79921 |

## B. Determination stands (35 codes)

| 2025 code | activity | annex row | p | via 2020 |
|---|---|---|---|---|
| `01111` | Pertanian Jagung | Jagung | 1 | — |
| `01113` | Pertanian Kedelai | Kedelai | 1 | — |
| `01114` | Pertanian Kacang Tanah | Kacang tanah | 1 | — |
| `01115` | Pertanian Kacang Hijau | Kacang hijau | 1 | — |
| `01121` | Pertanian Padi Hibrida | Padi hibrida | 1 | — |
| `01122` | Pertanian Padi Inbrida | Padi inbrida | 1 | — |
| `10214` | Pengolahan dan Pengawetan Ikan dengan Pe | Industri pemindangan ikan | 2 | — |
| `10307` | Pembuatan Tempe Kedelai | Industri tempe kedelai | 2 | 10391 |
| `10308` | Pembuatan Tahu Kedelai | Industri tahu kedelai | 2 | 10392 |
| `10722` | Industri Gula Merah | Industri gula merah | 2 | — |
| `10794` | Industri Kerupuk, Keripik, Peyek, dan Se | Industri kerupuk, keripik, peyek dan s | 3 | — |
| `16293` | Industri Kerajinan Ukiran dari Kayu Buka | Industri kerajinan ukiran dari kayu bu | 4 | — |
| `22121` | Industri Karet Asap | Industri pengasapan karet | 4 | — |
| `41016` | Konstruksi Konvensional Gedung Pendidika | gedung pendidikan meliputi sarana pend | 7 | — |
| `41018` | Konstruksi Konvensional Gedung Hiburan d | gedung tempat hiburan dan olahraga mel | 7 | — |
| `41020` | Konstruksi Prapabrikasi Bangunan Gedung | jasa pekerjaan konstruksi prafabrikasi | 7 | — |
| `42202` | Konstruksi Bangunan Sipil Pengolahan Air | bangunan pengolahan, penyaluran dan pe | 8 | — |
| `42912` | Konstruksi Bangunan Pelabuhan Bukan Peri | pelabuhan bukan perikanan pelabuhan pe | 9 | — |
| `42913` | Konstruksi Bangunan Pelabuhan Perikanan | pelabuhan perikanan | 9 | — |
| `43215` | Pemasangan Sistem Persinyalan dan Teleko | sinyal dan telekomunikasi kereta api | 10 | — |
| `43221` | Pemasangan Saluran Air (Plumbing) | saluran air Qtlambingl pemanas dan geo | 10 | — |
| `43222` | Pemasangan Sistem Pemanas dan Geotermal | pemanas dan geotermal | 10 | — |
| `43224` | Pemasangan Pendingin dan Ventilasi Udara | pendingin dan ventilasi udara mekanika | 11 | — |
| `43303` | Pengecatan | pengecatan | 11 | — |
| `43309` | Penyelesaian Konstruksi Bangunan Lainnya | Penyelesaian konstruksi bangunan lainn | 12 | — |
| `43902` | Pemasangan Perancah (Steger) | Pemasangan perancah (steigefi Pemasang | 12 | — |
| `43904` | Pemasangan Kerangka Baja | Kerangka baja Penyewaan alat konstruks | 12 | — |
| `47241` | Perdagangan Eceran Beras | Beras | 13 | — |
| `47242` | Perdagangan Eceran Roti, Kue Kering, ser | Roti, kue kering, serta kue basah dan  | 13 | — |
| `47244` | Perdagangan Eceran Tahu, Tempe, Tauco, d | Tahu, tempe, tauco dan oncom | 13 | — |
| `47249` | Perdagangan Eceran Makanan Lainnya | Makanan lainnya | 14 | — |
| `47712` | Perdagangan Eceran Sepatu, Sandal, dan A | Alas kaki | 14 | — |
| `95220` | Reparasi dan Pemeliharaan Peralatan Ruma | Reparasi peralatan: Peralatan rumah ta | 16 | — |
| `95291` | Aktivitas Vermak Pakaian | Vermak pakaian | 16 | — |
| `95299` | Reparasi dan Pemeliharaan Barang Keperlu | Industri reparasi barang rumah tangga  | 16 | — |

## C. For Zero — 13 split verdicts + 3 unclear + 1 illegible (17)

| code | activity | Sonnet | Codex |
|---|---|---|---|
| `16291` | Industri Barang Anyaman dari Rotan | REFUSE_UNCLEAR | PATCH |
| `16294` | Industri Alat Dapur dan Alat Makan | REFUSE_UNCLEAR | PATCH |
| `41014` | Konstruksi Konvensional Gedung Per | REFUSE_UNCLEAR | PATCH |
| `41015` | Konstruksi Konvensional Gedung Kes | REFUSE_UNCLEAR | PATCH |
| `41019` | Konstruksi Konvensional Gedung Lai | PATCH | REFUSE_BROADER |
| `43216` | Pemasangan Perlengkapan Jalan Berb | PATCH | REFUSE_BROADER |
| `43291` | Pemasangan Perlengkapan Mekanikal  | REFUSE_BROADER | REFUSE_UNCLEAR |
| `43302` | Pengerjaan Lantai, Dinding, dan Pl | PATCH | REFUSE_UNCLEAR |
| `43903` | Pemasangan Rangka dan Atap/Roof Co | PATCH | REFUSE_BROADER |
| `47192` | Perdagangan Eceran Berbagai Macam  | REFUSE_BROADER | REFUSE_UNCLEAR |
| `47245` | Perdagangan Eceran Daging Olahan | PATCH | REFUSE_UNCLEAR |
| `47721` | Perdagangan Eceran Sediaan Farmasi | PATCH | REFUSE_UNCLEAR |
| `86103` | Aktivitas Rumah Sakit Swasta | REFUSE_BROADER | REFUSE_UNCLEAR |
| `43213` | Pemasangan Sistem Elektronika | UNCLEAR | UNCLEAR |
| `43223` | Pemasangan Jaringan Penyaluran Gas | UNCLEAR | UNCLEAR |
| `95120` | Reparasi dan Pemeliharaan Peralata | UNCLEAR | UNCLEAR |
| `47722` | Perdagangan Eceran Sediaan Farmasi | PATCH | PATCH — **held, annex text OCR-corrupted** |

## D. Refused as broader than the reserved activity (28 codes)

Both families agreed the 2025 code covers more than the annex reserves.
Pasal 3(3): the requirement attaches to the named *bidang usaha*, never to the code number.

Codes: `02302`, `02303`, `02304`, `02305`, `02306`, `02307`, `02308`, `02309`, `10750`, `13121`, `13122`, `13134`, `13912`, `14111`, `14131`, `16292`, `23932`, `25931`, `25932`, `25934`, `32201`, `35111`, `41017`, `43211`, `43299`, `47243`, `55199`, `71204`
