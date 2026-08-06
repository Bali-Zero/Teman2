---
date: 2026-08-06
domain: compliance
client_case: none — catalogue-wide determination affecting every PT PMA enquiry on these activities
adversarial_review: codex
sources:
  - Perpres 10/2021 as amended by Perpres 49/2021, Lampiran II (vaulted PDF 161564, 180 ticks, 0 unresolved)
  - scripts/kbli_filiera/perpres_umkm_reservation_relation.py --json
  - data/source_documents/KBLI_2025_FINAL_CLEAN.json (bps_2020_ancestors, published pma_status)
---

# Lampiran II K-UMKM reservations: 85 codes adjudicated one by one

> ## ⛔ WITHDRAWN THE SAME DAY — the 39-code patch was never applied
>
> An independent cross-family review of this finished document (Codex GPT-5.6,
> instructed to refute) returned **DEFECTIVE**, and its first point held up at
> the source PDF: the annex reserves food crops only **"dengan luas kurang dari
> 25 Ha"**. Nothing in the evidence given to the 21 adjudicating agents said so
> — because **Lampiran II is not a flat table**. A numbered PARENT bidang usaha
> carries the scope, and the rows indented under it carry a bare name:
>
> ```
> 1   Pertanian tanaman pangan dengan luas kurang dari 25 Ha:
>        Padi hibrida        01121   V
>        Jagung              01111   V
> ```
>
> Our parser emitted the child cell only. A lane judging `01111` saw `"Jagung"`
> and had no way to learn about the 25 hectares, so both families agreed to
> reserve the whole code — agreement measuring fidelity to the evidence supplied,
> exactly as W100 says. **Eleven of the 39 codes this document proposed to patch
> sit under a restricting parent** (`01111 01113 01114 01115 01121 01122 43215
> 43221 43222 43224 43303` — the 25-Ha crops, and the "teknologi sederhana dan
> madya" installation/works grades). Publishing 0% on them would tell a client
> they cannot run an activity they lawfully can.
>
> **Nothing reached a client**: the patch was withdrawn before merge and the
> canonical dataset is untouched. What ships instead is the cure for the cause —
> `parse_perpres_lampiran2` now emits `parent_heading` on every row, and the
> classifier has a named **`parent-qualified`** bucket (17 rows), which moves
> `whole-row` from **85 to 68**. Every count below that derives from 85 is
> therefore superseded; the verdicts are kept as the record of what was decided
> on what evidence, not as a queue to apply.
>
> The sharpest part is not that the parser was thin — it is that
> `perpres_umkm_reservation_relation.py` **already said so**, in its own
> docstring, and deliberately left such rows in `whole-row` so a human would ask
> about them. That caveat was true, load-bearing, and invisible to every reader
> who consumed the DATA instead of the module. A limitation that lives only in a
> comment does not travel with the rows.

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

**Actionable set: 39 codes, not 41.**

A further removal came from CI, not from this reading: `79110` (travel agent) is
asserted at **100%, never 0** by `test_kbli_eye.py`, a determination that lives
in a TEST rather than in `pma_official_basis` — so the applier's own
refuse-on-prior-adjudication rule could not see it. Two in-repo determinations
disagree; that is Zero's to settle, not a silent overwrite.

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
**Pasal 5 ayat (5)**: where one KBLI covers more than one *bidang usaha*, the Lampiran II
allocation applies only to the *bidang usaha* named in that column — never to the code number.

Codes: `02302`, `02303`, `02304`, `02305`, `02306`, `02307`, `02308`, `02309`, `10750`, `13121`, `13122`, `13134`, `13912`, `14111`, `14131`, `16292`, `23932`, `25931`, `25932`, `25934`, `32201`, `35111`, `41017`, `43211`, `43299`, `47243`, `55199`, `71204`

## Adversarial review

**Seat**: Codex GPT-5.6 (`gpt-5.6-terra`, read-only sandbox), given this
document, the cure spec and the applier, and told to refute the determination
and default to DEFECTIVE. It did not write any of the work it reviewed
(generator ≠ grader). **Verdict: DEFECTIVE.** Seven points; what happened to
each, including the ones that did not survive:

1. **The 25-Ha qualifier — UPHELD, and it withdrew the cure.** Re-verified here
   at the vaulted PDF rather than taken on the reviewer's word (W65: a refuter's
   verdict is a lead). `pdftotext -layout` page 1 shows the parent row verbatim.
   Codex named 6 codes; the parent-aware re-parse measures **11**, because the
   two "teknologi sederhana dan madya" headings restrict a second family the
   reviewer did not reach. The refuter was right about the disease and short
   about its extent — which is the normal shape, and the reason the count in a
   finding gets re-derived rather than quoted.
2. **The granularity article — UPHELD, and SETTLED at the source the same day:
   the `Pasal 3(3)` this document cited does not exist; the rule is Pasal 5(5).** Read in the vaulted body of Perpres 10/2021 (`154474`) rather than
   swapped for the reviewer's number, because replacing one unchecked citation
   with another is not a fix (W113). What the text says:

   - **Pasal 3 has two ayat.** `Pasal 3(3)` does not exist. It was a phantom.
   - **Pasal 5(5)** — *"Dalam hal Klasifikasi Baku Lapangan Usaha Indonesia …
     meliputi lebih dari satu Bidang Usaha, ketentuan mengenai alokasi dan
     kemitraan … dalam **Lampiran II** hanya berlaku bagi Bidang Usaha yang
     tercantum dalam kolom Bidang Usaha tersebut."* This is our article.
   - **Pasal 6(3)** is its twin for **Lampiran III** (the foreign-cap annex),
     word-for-word the same rule with `persyaratan` in place of `alokasi dan
     kemitraan`.

   So the granularity rule is written **once per annex**, and one remembered
   number cannot serve both — which is exactly how the phantom propagated to
   **five** places: this document, `apply_umkm_reservations.py`, the
   already-merged `perpres_foreign_cap_relation.py` (2026-08-01), the
   `kbli-navigator` corner skill that every KBLI session loads, and the modus
   ledger. All five corrected to the article of their own annex, with a
   tripwire (`test_the_granularity_article_is_per_annex`) so the phantom cannot
   come back. Inherited, not invented here — and it had been in the corner
   skill for five days.

   Pasal 5(2) also explains WHY the annex headings carry the qualifiers this
   review turned on: allocation to K-UMKM is defined by criteria — *no or
   simple technology*, special/labour-intensive/heritage processes, or capital
   not exceeding Rp10bn excluding land and buildings. "teknologi sederhana dan
   madya" in a heading is that criterion, written into the list.
3. **`55106`/`55201`/`55203`/`79903` were in the spec while the text called them
   HELD — UPHELD as a defect of the RECORD.** The hold was lifted deliberately
   by the owner ("fai il tuo lavoro senza importartene dei clienti e di noi") and
   that decision stands; the document simply never said so, so it contradicted
   its own artifact. A reader would have found four 0% verdicts on codes the
   text called unresolved. Moot under the withdrawal, fixed in the re-write.
4. **Semantic check on the seven 2020→2025 mappings — UPHELD as insufficient.**
   The applier verified cardinality (exactly one heir) and not identity of
   perimeter. `55120` "Hotel Melati" → `55106` "Aktivitas Hotel Nonbintang" is a
   single heir and not obviously the same activity.
5. **`42912` — UPHELD on the evidence, and it is a second parser defect.** Its
   activity cell reads `"pelabuhan bukan perikanan pelabuhan perikanan"`: two
   distinct annex cells run together. Ledgered, not fixed here.
6. **OCR-contaminated locators — PARTLY UPHELD.** The consistency argument is
   sound (holding `47722` for illegible OCR while accepting other damaged
   strings is incoherent), but the specific list was asserted, not measured; a
   loose "over-long cell" probe flags 74 rows, which is too blunt to act on.
   Recorded as a limit, not a finding.
7. **Harden the applier — PARTLY ADOPTED.** It now refuses a withdrawn spec by
   name (`test_guilt_a_withdrawn_spec_is_refused_before_anything_is_read`); the
   perimeter and atomicity points belong with the re-adjudication.

**What this review did not do**: it did not read the rendered annex images, so
none of the above is image-grounded (W100 asks for that on content claims). The
25-Ha finding was confirmed against the PDF text layer plus the parent-aware
re-parse — two readings of the same artifact, not two independent witnesses.
