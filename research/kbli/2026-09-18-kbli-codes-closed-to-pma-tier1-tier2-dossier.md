---
title: "Which KBLI-2025 codes are NOT available to a PT PMA — Tier-1 (government) and Tier-2 (law-firm) dossier, per-code relation, and the 'no Usaha Besar row ⇒ not PMA' verdict"
date: 2026-09-18
domain: legal
client_case: false
adversarial_review: codex
sources:
  - "UU 6/2023 (Penetapan Perppu 2/2022 Cipta Kerja) — full gazette PDF, https://peraturan.bpk.go.id/Download/302681/UU%20Nomor%206%20Tahun%202023.pdf, fetched 2026-09-18, text layer; read: Pasal 77 item 2 (new UU 25/2007 Pasal 12), Pasal 33 item 18 (new UU 13/2010 Pasal 100)"
  - "Perpres 10/2021 tentang Bidang Usaha Penanaman Modal — body text (OCR layer, scratchpad perpres10.txt from the 2026-09-13 fetch of https://peraturan.go.id/files/ps10-2021.pdf), re-read 2026-09-18: Pasal 1 angka 7, 2, 3, 5, 6, 7, 8, 9"
  - "Perpres 49/2021 tentang Perubahan atas Perpres 10/2021 — body text, https://peraturan.bpk.go.id/Download/161562/Perpres%20Nomor%2049%20Tahun%202021.pdf, fetched 2026-09-18: Pasal 2 (1a),(2), Pasal 6 (3),(3a),(4), Pasal II"
  - "Perpres 49/2021 Lampiran III — https://peraturan.bpk.go.id/Download/161565/Perpres%20Nomor%2049%20Tahun%202021%20-%20Lampiran%20III.pdf, fetched 2026-09-18 (vault id 161565); transcription = scripts/kbli_filiera/perpres_foreign_cap_relation.py RELATION (37 entries / 41 pairs)"
  - "Perpres 49/2021 Lampiran II — vault id 161564 (PDF pages 1-16 and 22 read directly this session via pdftotext -layout: items 8, 9, 11, 14, 19, 21, 25, 28, 35, 42, 43, 53 and 106), compiled rows data/kbli-filiera/perpres-umkm-reservation.json via scripts/kbli_filiera/parse_perpres_lampiran2.py; joined 2026-09-18 with perpres_umkm_reservation_relation.py --check --json"
  - "PP 7/2021 (UMKM) — https://peraturan.bpk.go.id/Download/154506/PP%20Nomor%207%20Tahun%202021.pdf, fetched 2026-09-18: Pasal 35 (scale criteria)"
  - "PP 28/2025 (PBBR) — body, https://peraturan.bpk.go.id/Download/381375/PP%20Nomor%2028%20Tahun%202025.pdf, fetched 2026-09-18: Pasal 5(3)-(4), 124(1), 126(1), 127(2), 138(4), 211, 212; exhaustive grep of the extracted text: the words 'Usaha Besar' do not occur in the body"
  - "Permen Investasi dan Hilirisasi/Kepala BKPM 5/2025 — https://jdih-storage.bkpm.go.id/jdih/jdih/2025Permeninvesthil005-.pdf, fetched 2026-09-18: Pasal 8(4),(6), 23, 25, 26(1)-(8), 27"
  - "BKPM, Naskah Urgensi Rapermen PBBR (OSS) — https://jdih-storage.bkpm.go.id/jdih/jdih/Naskah-Urgensi-Rapermen-PBBR-%28OSS%29-.pdf, fetched 2026-09-18, sha256 d6545dc2401d08ed…, 18 pages: p.8 row 1 explains Pasal 8(6)-(7) (drafting rationale — explanatory, not enacted law)"
  - "UU 18/2003 Advokat Pasal 23; UU 2/2014 Jabatan Notaris Pasal 3; UU 40/1999 Pers Pasal 11; UU 32/2002 Penyiaran Pasal 17; UU 31/2004 Perikanan Pasal 29; UU 13/2010 Hortikultura Pasal 100 (pre-amendment); UU 17/2008 Pelayaran Pasal 8; UU 1/2009 Penerbangan Pasal 108 — secondary mirror https://pasal.id/peraturan/uu/…, fetched 2026-09-18 (statute text, non-government mirror; JDIH primaries not fetched)"
  - "Bali 18-KBLI administrative closure for new PMA — Antara Bali 2026-07-23, https://bali.antaranews.com/berita/410161/…, and BP Lawyers 2026-08-05, https://bplawyers.co.id/2026/08/05/kbli-70209-ditutup-bagi-pma-baru-di-bali-…, fetched 2026-09-18 (secondary; no instrument number located)"
  - "Tier-2, 11 documents fetched across 7 providers, all 2026-09-18: SSEK Doing Business in Indonesia 2025 (https://ssek.com/wp-content/uploads/2025/01/Doing-Business-in-Indonesia.pdf); ABNR ×3 (abnrlaw.com 2021 news + Chambers Doing Business 2026 Indonesia); AHP ×2 (client update 2021-03-17 + guidebook 2024); PwC Legal Alert 2025-48; KPMG Investing in Indonesia 2025; Makarim 2016 (superseded, historical); Lexology GTDT FLR Indonesia 2022 (Nagashima Ohno & Tsunematsu). NOT fetched: HSF Kramer 2025-11 and Dentons HPRP 2024-09 — HTTP 403, used for no claim"
  - "Canonical dataset data/source_documents/KBLI_2025_FINAL_CLEAN.json v11.0-L2-oss-risk-20260911, md5 dc735b4b18bd4438089a39dc44d6264f, 1,559 records (pma_verification_status: located 65 / declared_gap 1,494), measured 2026-09-18 in the worktree"
  - "UU 12/2011 tentang Pembentukan Peraturan Perundang-undangan — https://peraturan.bpk.go.id/Download/28610/UU%2012%20Tahun%202011.pdf, fetched 2026-09-18 (201 pages, text layer): Pasal 7(1) hierarchy, Pasal 8(1)-(2) ministerial regulations, Penjelasan Pasal 8"
  - "Companion relation: research/kbli/2026-09-18-kbli-closed-to-pma-relation.json (this PR; 269 rows, 267 in catalogue)"
---

# Which KBLI-2025 codes are not available to a PT PMA

> Nothing below is a client-facing verdict. Every fact carries an instrument + article/annex row;
> everything else is labelled INFERENCE. No client data is involved. The per-code relation that
> this dossier explains is `2026-09-18-kbli-closed-to-pma-relation.json`; the pages stay as they
> are until the owner rules on §8.

## 0. Answer in one screen

**(a) The sourced list.** Under national law a KBLI-2025 code is unavailable to a PT PMA for one
of six reasons, and the reason is the instrument (counts = codes present in the 1,559-code
catalogue; "canonical agrees" = the dataset already says the same):

| # | Class | Instrument | Codes | Canonical agrees |
|---|---|---|---|---|
| 1 | Closed to ALL investment | UU 25/2007 Pasal 12(2) (as amended); Perpres 10/2021 Pasal 2(2)(b) (as amended) | 4 (+ 11031 absent from KBLI-2025) | 4/4 |
| 2 | Activity of the state, by title | Perpres 10/2021 Pasal 2(1)(b) + (3), (1a) | 54 | 54/54 |
| 2b | Not a commercial field, not a state activity either (international bodies) | Perpres 10/2021 Pasal 2(1a) | 1 (99000) | 1/1 |
| 3 | Allocated to Koperasi/UMKM — row coextensive with the code on its own text (decided blind to the canonical, §3.3) | Perpres 49/2021 Lampiran II + Pasal 5(1)(a), 5(5) + Pasal 7(1) | 20 | 13/20 (7 published open; 13133 closes by the UNION of Lampiran II + III, `closure_basis`) |
| 4 | 100% domestic capital, whole code (3 of them: at ESTABLISHMENT only, §3.4; 21022 promoted over a narrower Lampiran II row) | Perpres 49/2021 Lampiran III | 7 | 4/7 |
| 5 | Closure in a sector statute (3 establishment-only; 69104 entity-form) | UU 30/2004 as amended by UU 2/2014, UU 40/1999, UU 32/2002 | 4 | 0/4 |
| | **Closed to a NEW PT PMA, sourced** | | **90** | **76/90** |
| 5b | Professional-PERSON restriction, ownership rule not sourced — **not counted**, not a finding of openness either | UU 18/2003 Pasal 23 | 1 (69101) | n/a |
| 6 | Foreign share capped at 49% as the ORDINARY limit — PMA as minority (entry #7: >49% with Menhan approval) | Lampiran III | 30 | 25/30 |
| 7 | Lampiran II row names the code with no qualifier, coverage UNRESOLVED — **candidate**: 3 readable cells that enumerate products under a generic title or sit under a 2025-widened title, 7 with mixed 2020 ancestry | Lampiran II, Pasal 5(5) | 10 | 0/10 (9 open, 79110 `TERBATAS/100`) |
| 7b | Canonical closes the WHOLE 2025 code but the instrument does not prove it — **scope review**, not counted: 4 rows PROVEN narrower on their text, 9 of unresolved coverage | Lampiran II, Pasal 5(5) | 13 | canonical broader than instrument |
| 8 | Lampiran II/III on a SEGMENT of the code — code stays open, segment does not | Pasal 5(5), Pasal 6(3) | 93 + 4 | n/a |
| 8b | Lampiran II row reaching a 2025 code only through a KBLI split, heir title DISJOINT from the named activity — nothing reserved | crosswalk only | 7 | n/a |
| 9 | Alcohol trade — conditional, neither closed nor capped | Pasal 6(1)(d) + (3a) | 1 as primary class (46333) + 47221 as a secondary relation on a Lampiran II segment row (+ 47826 absent) | n/a |
| 10 | Bali administrative closure for NEW PMA via OSS | no instrument number located (secondary) | 18 (13 in catalogue) | 13/13 `CHIUSO_BALI` |

The full per-code rows, with the Bidang Usaha text and parent heading of every annex line, are in
the relation JSON.

**(b) The «no Usaha Besar row ⇒ not PMA» verdict — without theatrics.** The premise is right and
the inference is wrong. *Premise:* a PMA is by law a large enterprise — Perpres 10/2021 Pasal 7(1)
and Permen BKPM 5/2025 Pasal 26(1) say it in those words (§2.4). *Inference:* «therefore a KBLI
whose PP 28/2025 licensing annex has no `Besar` row is closed to PMA» does not follow: the rule
that governs exactly this case — Permen BKPM 5/2025 Pasal 8(6), the implementing regulation of PP
28/2025 — says that when the scale is not listed in the risk-based licensing rules the business
actor **may still carry on the activity**, «sepanjang tidak dibatasi dalam ketentuan peraturan
perundang-undangan mengenai bidang usaha penanaman modal». The gate is the investment-field rules
(Perpres 10/2021 + annexes + sector statutes); a missing row in the licensing matrix is a
licensing gap, not an investment-field closure (§4.2 states the strongest counter-argument and why
it fails). No Tier-1 text states the inference; no fetched Tier-2 document states it (§4). In the
catalogue the inference fires on 21 codes: 7 are Lampiran II allocated codes (closed, by Lampiran
II — which is what the canonical cites), 2 sit on Lampiran II rows (55209 a proven segment, 79110 a candidate), 12 are
residual codes published open (§4.3) where the honest page reads *declared gap*, not closure.

## 1. Method

Four research seats ran in parallel on 2026-09-18 (Tier-1 body texts; Tier-1 per-code lists;
Tier-1 sector statutes; Tier-2 law firms), each writing a scratchpad report with a §A table of
every URL fetched, status and date. This session then (i) re-read every quoted article in the
primary PDFs before quoting it here, (ii) regenerated the three repo relations from the vaulted
annexes (`perpres_umkm_reservation_relation.py --check --json`, `perpres_foreign_cap_relation.py
--check` via its `classify_join()`, `perpres_body_default_relation.py --check --json`), (iii)
joined them to the canonical through the BPS crosswalk, (iv) wrote the relation JSON, (v) ran a
Codex refuter round (fresh context) over dossier + relation + primary texts and folded its findings
(§ Adversarial review). No paid per-token API was used; no client data was touched. Tier-1 =
`*.go.id` / `peraturan.bpk.go.id` / JDIH; sector statutes were read on `pasal.id` (a non-government
mirror of the statute text) and are marked as such. Tier-2 = published law-firm / Big-4 guides,
used only for consensus on the reading, never as a source of a code.

## 2. The legal chain (verbatim, primary text read this session)

### 2.1 The closed list is six items, and it is exhaustive at statute level
UU 25/2007 Pasal 12 as replaced by UU 6/2023 Pasal 77 item 2 (gazette text, «Ketentuan Pasal 12 diubah sehingga berbunyi sebagai berikut»):

> (1) Semua bidang usaha terbuka bagi kegiatan Penanaman Modal, kecuali bidang usaha yang
> dinyatakan tertutup untuk Penanaman Modal atau kegiatan yang hanya dapat dilakukan oleh
> Pemerintah Pusat. (2) Bidang usaha yang tertutup untuk Penanaman Modal … meliputi: a. budi daya
> dan industri narkotika golongan I; b. segala bentuk kegiatan perjudian dan/atau kasino;
> c. penangkapan spesies ikan yang tercantum dalam Appendix I … (CITES); d. pemanfaatan atau
> pengambilan koral … ; e. industri pembuatan senjata kimia; dan f. industri bahan kimia industri
> dan industri bahan perusak lapisan ozon.

### 2.2 Perpres 10/2021 as amended by Perpres 49/2021 — the four-way partition
Pasal 1 angka 7 defines «Usaha Besar» by reference to the UMKM statute (UU 20/2008 as amended);
the capital criteria are in PP 7/2021 Pasal 35 (§2.3).

Pasal 2 (as amended): (1) all fields open except (a) declared closed, (b) government-only;
**(1a)** «Bidang Usaha terbuka … adalah Bidang Usaha yang bersifat komersial»; (2)(a) the UU
25/2007 Pasal 12 list, **(2)(b)** «Industri Minuman Keras Mengandung Alkohol (KBLI 11010),
Industri Minuman Mengandung Alkohol: Anggur (KBLI 11020), dan Industri Minuman Mengandung Malt
(KBLI 11031)»; (3) government-only = «kegiatan yang bersifat pelayanan atau dalam rangka
pertahanan dan keamanan yang bersifat strategis dan tidak dapat dilakukan atau dikerjasamakan
dengan pihak lainnya».

Pasal 3: (1) open fields are (a) prioritas, (b) dialokasikan/kemitraan Koperasi-UMKM,
(c) persyaratan tertentu, (d) everything else; **(2)** «Bidang Usaha sebagaimana dimaksud pada
ayat (1) huruf d dapat diusahakan oleh semua Penanam Modal». (1)(d) is residual to (1)(b): a code
that sits on a Lampiran II row is not a (1)(d) field.

Pasal 5: **(1)(a)** fields ALLOCATED to Koperasi/UMKM vs (1)(b) fields open to Usaha Besar that
PARTNER with them; (2) allocation criteria joined by **«dan/atau»** — (a) activities not using
advanced technology or capital-intensive processes, (b) activities with special cultural-heritage
or labour characteristics, **(c)** «modal usaha kegiatan tidak melebihi Rp10.000.000.000,00 … di
luar nilai tanah dan bangunan» — so the capital ceiling is ONE of three alternative criteria, not a
universal one; (4) the list is Lampiran II; **(5)** «Dalam hal [KBLI] … meliputi lebih dari satu
Bidang Usaha, ketentuan mengenai alokasi dan kemitraan … hanya berlaku bagi Bidang Usaha yang
tercantum dalam kolom Bidang Usaha tersebut»; (6)–(7) an allocated business that grows into Usaha
Besar keeps its field and partners with Koperasi/UMKM — the annex contemplates growth, not a
capital cap on the activity.

Pasal 6 (as amended): (1)(b) foreign-ownership caps, (1)(d) other requirements; **(3)** the same
column rule as 5(5) for Lampiran III; **(3a)** «a. Perdagangan Besar Minuman Keras/Beralkohol
(importir, distributor, dan sub distributor) (KBLI 46333); b. Perdagangan Eceran Minuman Keras atau
Beralkohol (KBLI 47221); dan c. Perdagangan Eceran Kaki Lima Minuman Keras atau Beralkohol (KBLI
47826)» — conditional, not closed; **(4)** the foreign-ownership caps of (1)(b) do not apply to
(a) investments approved in the field before promulgation as recorded in the licence, unless the
Perpres is more favourable, or (b) investors holding privileges under a treaty between Indonesia
and their home state, unless the Perpres is more favourable.

**Pasal 7 (1)** «Penanam Modal asing hanya dapat melakukan kegiatan usaha pada Usaha Besar dengan
nilai investasi lebih dari Rp 10.000.000.000,00 … di luar nilai tanah dan bangunan.» (2) PMA must
be a PT under Indonesian law.

Pasal 8: (1) Pasal 3(1)(c) requirements do not apply inside a KEK; (2) tech start-ups in a KEK may
invest ≤ Rp10bn. Pasal 9: Lampiran II/III do not bind portfolio investment through the domestic
capital market. Perpres 49/2021 Pasal II(1) grandfathers investments approved before promulgation
ONLY for Pasal 2 and Pasal 6(1)(a),(c),(d),(2),(3),(3a) — the foreign-ownership caps have their own
grandfathering in Pasal 6(4) above; the allocation rules of Pasal 5 are not named.

### 2.3 Scale criteria — PP 7/2021 Pasal 35
Capital criteria for establishment/registration: Mikro ≤ Rp1bn, Kecil Rp1–5bn, Menengah Rp5–10bn,
all excluding land and buildings; a separate annual-sales criterion applies to running businesses.
«Usaha Besar» is the enterprise above the Menengah ceiling (UU 20/2008 definition by reference,
Perpres 10/2021 Pasal 1 angka 7); the Rp10bn residual is the capital criterion relevant here.

### 2.4 «PMA = usaha besar» in the ministerial rule — and its own exception clauses
Permen BKPM 5/2025 **Pasal 26**: (1) «Badan usaha … yang dikategorikan PMA merupakan usaha besar
dan wajib mengikuti ketentuan minimum nilai investasi, kecuali ditentukan lain berdasarkan
peraturan perundang-undangan.» (2) «total investasi lebih besar dari Rp10.000.000.000,00 … di luar
tanah dan bangunan per bidang usaha KBLI 5 (lima) digit per lokasi proyek.» (3) aggregation
exceptions — wholesale per 4 digits, F&B per 2 digits per location, construction per 4 digits,
multi-product single production line — change how the Rp10bn is counted, not the PMA = usaha
besar classification. (5) accommodation, agriculture, plantation, livestock, aquaculture count
land/buildings INSIDE the threshold. **(6) property is two cases:** (a) a whole building or an
integrated housing complex — >Rp10bn INCLUDING land and buildings; (b) property units not in one
whole building/complex — >Rp10bn EXCLUDING land and buildings. (7)–(8): EV charging stations and
KEK defer to their own rules.

### 2.5 The clause that decides the no-Besar question — Permen BKPM 5/2025 Pasal 8(6)
> (6) Dalam hal skala kegiatan usaha tidak tercantum dalam ketentuan peraturan perundang-undangan
> mengenai penyelenggaraan perizinan berusaha berbasis risiko, Pelaku Usaha dapat tetap
> melaksanakan kegiatan usaha sesuai dengan ketentuan peraturan perundang-undangan sepanjang tidak
> dibatasi dalam ketentuan peraturan perundang-undangan mengenai bidang usaha penanaman modal.

Pasal 8(4) is the sentence right above it: the KBLI, scope, **skala usaha**, risk, PB and
requirements per sector «sesuai dengan ketentuan peraturan perundang-undangan mengenai
penyelenggaraan perizinan berusaha berbasis risiko» — i.e. PP 28/2025 Lampiran I is where the
`Besar` row lives, and (6) is the rule for when it does not.

### 2.6 PP 28/2025 — the scale matrix is law, and the Rp10bn test is a value check
Pasal 5(3)(a)+(4): the per-sector PBBR rules — «kode KBLI …, ruang lingkup kegiatan, **skala
usaha**, tingkat Risiko, PB, persyaratan …» — are in Lampiran I, «yang merupakan bagian tidak
terpisahkan dari Peraturan Pemerintah ini». Pasal 124(1): PB is issued on the risk level AND the
scale of the activity; 126(1)(b) scale identification is a step of the risk analysis; **127(2)**
the scale is identified «berdasarkan peraturan perundang-undangan di bidang kemudahan, pelindungan,
dan pemberdayaan koperasi dan UMK-M» — by the UMKM capital criteria, not by reading a row.
Pasal 212(1)-(2): «Untuk Penanaman Modal Asing, Sistem OSS melaksanakan pemeriksaan ketentuan atas
data usaha berupa rencana nilai investasi … per bidang usaha KBLI 5 (lima) digit per lokasi usaha
harus lebih besar dari Rp10.000.000.000,00 … di luar tanah dan bangunan»; 212(3) the same four
aggregation exceptions as Permen 5/2025 Pasal 26(3) — and (3)(b)-(c) say «sepanjang terbuka untuk
Penanaman Modal Asing», i.e. the value test presupposes the openness question is answered
elsewhere. Pasal 138(4) routes PB issuance to Lembaga OSS where the activity involves PMA. The
string «Usaha Besar» does not occur in the body (exhaustive grep of the extracted text).

## 3. Findings per class

### 3.1 Closed to all investment (class `closed_all`)
11010, 11020 — named 5-digit in Pasal 2(2)(b); 11031 is named too but does not exist in KBLI-2025
(malt beverages were merged into the 11030 family — a page for the 2025 heir must carry the
closure as a segment). 01287 «Pertanian Tanaman Narkotika dan Tanaman Obat Terlarang» and 92000
«Aktivitas Perjudian dan Pertaruhan» match UU 25/2007 Pasal 12(2)(a)/(b) by TITLE; no instrument
maps the statute's six items to 5-digit codes. Items (c)–(f) (CITES fish, coral, chemical weapons,
ozone-depleting chemicals) are segments of 031xx / 03xxx / 201xx and are listed as
`unmapped_statutory_closures` — they close a product, not a code.

### 3.2 Activities of the state (class `government_activity`, 54) and 99000
84111–84300 (33 codes of public administration/defence) and every «… oleh Pemerintah» title:
59111/59121/59131 (film production/distribution/exhibition by government), 60311 (radio network by
government), 85101/85201/85311/85315/85321/85401/85403/85550/85560 (government schools),
86101/86104 (government hospitals/clinics), 87201/87301, 91111/91121/91211/91221 (government
museums/libraries/…). The class is TITLE-DERIVED: no instrument names these 5-digit codes; the
builder asserts «Pemerintah» in the title or an 84xxx prefix for every member. Pasal 2(1a) settles
the consequence — the open list is commercial fields, so these are not "closed to PMA" in the
Perpres sense, they are not investable fields. **99000** «Aktivitas Badan Internasional dan Badan
Ekstra Internasional Lainnya» is kept apart (`non_commercial_institutional`): it is not a
commercial field either, but it is not an activity «yang tidak dapat dilakukan atau dikerjasamakan
dengan pihak lainnya» by the central government — Pasal 2(3) does not reach it, Pasal 2(1a) does.
The canonical has all 55 as `TERTUTUP` under `declared_gap`; the reading agrees, the label
"correct by construction" would not — it is a reading of titles.

### 3.3 Koperasi/UMKM allocation — Lampiran II
The mechanism is the eligible-investor rule, not a capital cap on the activity: Pasal 5(1)(a)
ALLOCATES the field to Koperasi and UMKM; a PMA is Usaha Besar by definition (Pasal 7(1), Permen
5/2025 Pasal 26(1)) and is neither; Pasal 5(6)–(7) confirms the annex is about who may enter, not
about how big the business may become. The ≤Rp10bn criterion of Pasal 5(2)(c) is one of three
alternative allocation criteria («dan/atau») and is not the operative bar. **DIALOKASIKAN ≠
KEMITRAAN**: 59 KBLI-2020 rows in the kemitraan column carry a duty to partner, not a bar (listed
under `kemitraan_codes_kbli_2020_no_bar`, now including 95120 and 95210 — §5).

**Scope test, applied to every row alike and blind to the canonical** (Pasal 5(5): the reservation
binds the Bidang Usaha in the column, not the KBLI number). A 2025 code is covered WHOLE only if
(i) the row has no qualifying parent heading («yang menggunakan teknologi sederhana dan madya»,
«dengan luas kurang dari 25 Ha» — a bare category label such as «Jasa Penginapan» groups and does
not narrow), (ii) the row text carries no qualifier and is not product- or scale-narrower than the
title (a regex on the text plus a manual reading recorded per row in `narrower_text`), (iii) the
2025 code descends only from reserved 2020 codes, and (iv) where KBLI-2025 split the 2020 code,
this heir's title carries the named activity (`split_heir_overlap: demonstrated`). Whether the
canonical already closes the code is compared AFTERWARDS (`canonical_agrees`) and never used as
evidence. The mechanical flags (`parent_ancestry_clean`) are named for what they check; the
text reading is a separate field. Restrictions aggregate across instruments: a whole-code closure
in Lampiran III is not cancelled by a narrower Lampiran II row on the same code (21022, §3.4).

| Bucket | Codes | Reading |
|---|---|---|
| coextensive (`umkm_reserved_coextensive`) — **counted as closed** | 20 — canonical already located 13: 10214 «Industri pemindangan ikan», 10722, 22121, 55105 «Hotel Bintang I» (= Bintang Satu), 55201 «Pondok Wisata» (= Homestay), 55203 «Vila», 79903, 95220, 95291, 95299, 96100 «Penatu», 96210 «Pangkas rambut/barber shop», 96220 «Salon kecantikan»; canonical still publishes 7 OPEN: 10307 «Industri tempe kedelai», 10308 «Industri tahu kedelai», 13133 (the ONE explicit exception to the class: Lampiran II item 11 reserves batik tulis + kombinasi and is NARROWER than the code; batik cap is Lampiran III #2 at 0% — the UNION covers every method in the code's uraian, neither annex alone does; `text_vs_title_reading: union_with_lampiran_iii`, `closure_basis: union`), 16291 «Industri barang anyaman — Rotan dan bambu» (item 14 p.4, read on the `-layout` text: parent + row = the title), 16293 «kerajinan ukiran dari kayu bukan mebeller», 32201 (parent «Industri alat musik tradisional antara lain» lists instruments by example — the code's own title, not a restriction), 55106 «Hotel Melati» (= Nonbintang) | one test, blind to the canonical: no qualifying parent, no qualifier in the row text (`QUALIFIER` regex runs on the text too), no manual narrower reading, single reserved ancestry, title ≈ row text. Coverage is the instrument's; agreement with the canonical is recorded AFTERWARDS in `canonical_agrees` (13 true / 7 false). The 7 are legal conclusions on the instrument's text, not options — what stays with the owner is the RELABEL of the pages (§8), not the reading |
| located, scope review (`umkm_reserved_located_scope_review`) — **not counted** | 13 — PROVEN narrower on the row's own text, 4: 41016, 41018, 41020 (parent «Konstruksi gedung yang menggunakan teknologi sederhana dan madya», item 25 p.6-7, lost by the text layer at the page break), 47111 (row reserves «Minimarket», the code covers minimarket/supermarket/hypermarket). UNRESOLVED coverage, 9: 47222 «Minuman tidak beralkohol», 47241, 47242, 47244, 47245, 47246, 47249, 47712, 47722 — KBLI-2025 merged the 2020 shop code with kaki-lima 4782x/47833/47842 and online 4791x/4799x codes that are NOT on Lampiran II (47246 is a split heir with a commodity-family match only) | for the 4 the canonical closes more than the instrument proves; for the 9 the mixed ancestry is a REVIEW TRIGGER — it neither proves a narrower scope nor an open remainder (47222's text is plainly «Minuman tidak beralkohol»); whether OSS treats the whole 2025 code as reserved is unverified — divergence `canonical_closure_broader_than_instrument` (§6) |
| whole-row candidate (`umkm_reserved_whole_row`) — **not counted** | 10 — readable on the `-layout` text but unproven, 3: 16292 (seven named plants vs the generic «Tanaman Selain Rotan dan Bambu»), 23932 («berupa: Gerabah, Keramik hias» vs «Perlengkapan Rumah Tangga dari Tanah Liat atau Keramik»), 16294 (row = the 2020 title «alat-alat dapur»; KBLI-2025 added «Alat Makan»); mixed 2020 ancestry, 7: 02300, 10794, 13122, 47192, 47243, 47721, 79110 | published TERBUKA/100% (79110: `TERBATAS/100`). No qualifier, no narrowing read, but coverage of the 2025 code unresolved: 10794's own text names «pabrikan dan non-pabrikan» although its 2020 sibling 10793 sits on the annex in the KEMITRAAN column (a duty to partner, no bar — `kemitraan_codes_kbli_2020_no_bar`), so Pasal 5(5) asks which activity of the merged code each row binds — a review, not a deduction either way |
| segment (`umkm_reserved_segment`) | 93 — qualifying parent (incl. the 14 children of items 25/35/42/43 whose heading the compiled rows lost: 41011, 41014, 41015, 41017, 41019, 42911, 42912, 42913, 43309, 43901–43905), in-row qualifier caught by the regex (35111 «< 1 MW», 43211 and 71204 «tegangan rendah/menengah», 95320 «terintegrasi dengan … penjualan sepeda motor»), or a product narrower than the title on this session's reading (10750 «Rendang», 13912, 14111, 14131, 25931, 25934 «Keris, Rencong, Mandau», 55209 «Guest House», 86103; 71204 also carries a second, technology-qualified row on p.16; and, read on the `-layout` text in round 3: 13121 six named traditional weaves, 25932 «diproses secara manual atau semi mekanik», 42202 «Pemasangan bangunan prafabrikasi …» — the compiled cells of 13121 and 42202 drop the opening phrase), or a split heir with a commodity-family match only (4791x/4792x online-retail rows → the commodity codes) | the code stays open; the segment is not. Every row carries `bidang_usaha_text`, `parent_heading` (explicit null when the annex has none), `text_qualifier`, `narrower_text`, `split_heir_overlap`; secondary relations (`also`) carry the same evidence object |
| crosswalk projection, disjoint (`umkm_reserved_crosswalk_projection`) | 7 — 55101–55104 (a «Hotel Bintang I» row descended by the split of 2020 55110 onto the two-to-five-star codes), 96400, 95400, 43400 (barber/salon/laundry, motorcycle repair, decoration rows descended onto INTERMEDIATION codes) | no demonstrated overlap between the named activity and the heir's title — nothing is reserved here; not a segment, nothing to apply |
| kemitraan, mis-compiled (`umkm_kemitraan_no_bar`) | 95102 (2020 95120) | the annex page ticks KEMITRAAN — duty to partner, no bar (§5) |

Corner rule preserved: the 2026-08-06 adjudication that reserved 39 whole-row codes was withdrawn
because 11 sat under a restricting parent; this dossier repeats the scope test instead of the
mistake — nothing on Lampiran II is counted closed unless the row text covers the code.

### 3.4 Lampiran III — foreign-ownership caps
37 entries / 41 (Bidang Usaha, KBLI-2020) pairs; the unit is the PAIR (Pasal 6(3)). Joined to
KBLI-2025 by the crosswalk: agree 30 · disagree 15 · ambiguous 2 · no descendant 0.

- **0% whole code** (`foreign_cap_0`, 7): 16221, 21021, 21022, 79122 (canonical agrees); 58130,
  60102, 60202 (canonical says TERBUKA/100% — divergence). 21022 «Industri produk obat tradisional
  untuk manusia» is entry #6 (`lampiran3_perpres49_2021.txt:22`), coextensive with the 2020 title;
  the Lampiran II row on the same code is scale-qualified (UKOT/UMOT) and cannot cancel a
  whole-code 100%-domestic requirement — the relation promotes the Lampiran III relation to
  primary (`promoted_from_secondary`) and keeps the Lampiran II row under `also`. **The press and broadcasting rows close the
  ESTABLISHMENT of a PMA, not every foreign share**: #33 press admits foreign capital only through
  the domestic capital market on expansion (UU 40/1999 Pasal 11); #34/#35 LPS/LPB are 0% at
  establishment and ≤20% on expansion (UU 32/2002 Pasal 17(2)). The relation carries
  `closure_scope: establishment` + `condition` on the three.
- **0% on a segment** (`foreign_cap_0_segment`, 4): 10761 (kopi indikasi geografis ⊂ Industri
  Pengolahan Kopi), 20232/20235 (kosmetik tradisional ⊂ Industri Kosmetik), 90200 (sanggar seni ⊂
  Aktivitas Seni Pertunjukan). The repo's join reports these as DISAGREE at code level; this
  dossier says a code-level 0% would be an over-claim — the segment is closed, the code is not.
- **0% by crosswalk projection** (`foreign_cap_0_crosswalk_projection`, 2): 60103/60203
  (internet audio/video streaming) inherit the LPS/LPB 0% only because the mechanical crosswalk
  descends them from the 2020 private-broadcasting codes; UU 32/2002 regulates penyiaran, not
  internet streaming. Verify, never apply.
- **Ambiguous by law** (2): 30111/30113 — the same 2020 code 30111 carries 49% (kapal perang) and
  0% (pinisi/cadik) on different rows; one integer cannot say this.
- **49% as the ordinary limit** (`foreign_cap_pct`, 30): 25200, 30400, 50111–50223
  (sea/river/ferry), 51101, 51102, 53200 agree; 26513 (radar pertahanan ⊂ alat ukur),
  30301/30302/30303 (pesawat militer ⊂ pesawat terbang) and 51103 (space transport, from 2020
  51109 «angkutan udara lainnya») are published TERBUKA/100% — the first four are segment caps,
  51103 is a crosswalk reading. Entry #7 (defence industry: 25200, 30400, 26513, 30301–30303)
  admits MORE than 49% with Menteri Pertahanan approval for strategic interests — the JSON
  `condition` keeps it; "minority only" is the ordinary case, not an absolute.

### 3.5 Sector statutes (class `sector_law`, 4 + 1 person-restriction) — closures the Perpres annexes do not carry
| Code | Statute | Rule | Note |
|---|---|---|---|
| 69101 Aktivitas Pengacara — `sector_law_person_restriction`, **not counted** | UU 18/2003 Pasal 23(1)-(2) | ADVOKAT ASING may not practise or open a law office or its representative; an Indonesian firm may employ them with government approval | a restriction on the professional PERSON. The rule that would close the CODE to a PT PMA — the permitted entity form of a law office, or a bar on a foreign non-advocate shareholder — is not in Pasal 23 and was not sourced; withdrawn from the closed count. This is not a finding that PMA ownership is permitted |
| 69104 Notaris dan PPAT | UU 30/2004 as amended by UU 2/2014 Pasal 1 angka 1 + Pasal 3 huruf a (+ PP 24/2016 Pasal 6 for PPAT) | a Notaris is a «pejabat umum» — a public office held by a natural person who must be WNI | entity-form closure: the activity cannot be held by a company of any capital origin, PMA included (`closure_scope: entity-form`) |
| 58120 Penerbitan Surat Kabar | UU 40/1999 Pasal 11 + Lampiran III #33 | foreign capital only via the capital market (expansion) — establishment closed | KBLI-2025 split 2020 58130 into 58120 + 58130; the crosswalk records 58120's ancestor as 2020 58120 «Penerbitan Direktori dan Mailing List» — a number match, not an activity match (superscar #3). Title-matched here, `crosswalk_suspect` |
| 60101 Radio Analog / 60201 TV Analog | UU 32/2002 Pasal 17(2) + Lampiran III #34/#35 | LPS/LPB: 0% at establishment, ≤20% for expansion — establishment closed | KBLI-2020 split radio/TV by OWNER (60101 pemerintah / 60102 swasta); KBLI-2025 splits by TECHNOLOGY (analog / digital / streaming). The mechanical crosswalk therefore sends only the digital codes to the LPS row. Canonical has zero `per_skala` rows for 60101 and 60201. `crosswalk_suspect` |

### 3.6 Alcohol trade (class `conditional_other_requirement`)
46333 as primary class, 47221 as a secondary relation (its primary row is a Lampiran II
online-retail segment), 47826 absent from KBLI-2025 — so `counts.conditional_other_requirement`
reads 2 = 46333 + 47826 and the in-catalogue codes carrying the condition are 46333 and 47221.
Pasal 6(3a) — «persyaratan Penanaman Modal lainnya». Not closed, not capped; the canonical's
`TERBATAS/special` on 47221 is the honest label.

### 3.7 Bali overlay (`bali_administrative_overlay`)
18 codes closed for NEW PMA through OSS in Bali, reported in force since mid-May 2026 and announced
2026-07-23 (Antara; BP Lawyers 2026-08-05): 55110 68111 55120 70209 77100 47711 47511 77311 47249 47991 55900 56303 56305 14120
93111 93116 93191 70204. Five are KBLI-2020 numbers absent from KBLI-2025 (55110, 55120, 47991,
55900, 70204); the 13 present are all `CHIUSO_BALI` in the canonical's `l4_bali`. No instrument
number was located — a provincial/OSS administrative measure, a separate axis from the national
PMA verdict, and the one place where a code that is nationally open is still refused.

## 4. The «no Usaha Besar row ⇒ not PMA» verdict

### 4.1 What is right
«PMA è intrinsecamente una skala besar» — yes, verbatim in two instruments: Perpres 10/2021 Pasal
7(1) («hanya dapat melakukan kegiatan usaha pada Usaha Besar») and Permen BKPM 5/2025 Pasal 26(1)
(«yang dikategorikan PMA merupakan usaha besar»). Five of the seven fetched Tier-2 providers restate
it explicitly (SSEK, ABNR, AHP, KPMG, GTDT); PwC is only forward-looking and Makarim 2016 pre-dates
the rule, all citing BKPM Reg 4/2021 → 5/2025 for the Rp10bn per 5-digit KBLI per location test.

### 4.2 Why the inference does not follow
The strongest case FOR the inference, stated fairly: PP 28/2025 Pasal 5(3)-(4) makes Lampiran I
— scale column included — an integral part of a Government Regulation; Pasal 124(1) issues PB on
risk AND scale; so a matrix with no `Besar` row could be read as the Government having defined the
activity as one without a large-scale form, and Perpres Pasal 7(1) would then leave a PMA nowhere
to stand. It fails on four texts:
1. **Scale is identified by capital, not by row — a supporting point, not the decisive one.** PP
   28/2025 Pasal 127(2) says the scale of an activity is identified «berdasarkan peraturan
   perundang-undangan di bidang … koperasi dan UMK-M» — the PP 7/2021 Pasal 35 criteria — but it
   sits inside the Government's risk-analysis process (Pasal 126-127): it tells the Government how
   to label a row, it does not tell an investor to disregard the resulting annex. Pasal 212 tests a
   VALUE (>Rp10bn) and is a necessary condition, not a licensing pathway. PP 28/2025's body never
   uses the words «Usaha Besar». On these two texts alone the counter-argument would survive as a
   licensing objection; the substantive answer is point 2.
2. **The implementing rule regulates the exact case and says "carry on" — and its drafters say
   why.** Permen 5/2025 Pasal 8(6) (§2.5) is the BKPM rule that implements PP 28/2025's KBLI/scale
   provisions. A Peraturan Menteri is not in the UU 12/2011 Pasal 7(1) hierarchy at all (UUD, Tap
   MPR, UU/Perppu, PP, Perpres, Perda); it is recognised by Pasal 8(1)-(2) «sepanjang diperintahkan
   oleh Peraturan Perundang-undangan yang lebih tinggi atau dibentuk berdasarkan kewenangan» — so
   it cannot override a PP or a Perpres, and it does not need to: neither the PP nor the Perpres
   says that a missing row closes a field. BKPM's own drafting rationale (Naskah Urgensi Rapermen
   PBBR, p.8 row 1 — explanatory material, not enacted law) states the purpose of Pasal 8(6)-(7)
   in these words: «Kepastian hukum bagi pelaku usaha, karena dalam Lampiran I PP 28/2025 terkesan
   melarang skala kegiatan usaha tertentu padahal skala kegiatan usaha tersebut tidak diatur dalam
   UU atau PP», and «Pembatasan untuk skala kegiatan usaha tertentu mengikuti ketentuan dalam
   Perpres BUPM». The regulator that runs OSS read the missing-row annex as an APPARENT
   prohibition and wrote the clause to say it is not one. The Permen fills the gap the way the
   Perpres itself points: openness is decided by «peraturan perundang-undangan mengenai bidang
   usaha penanaman modal», i.e. Perpres 10/2021 Pasal 3(2) («dapat diusahakan oleh semua Penanam
   Modal») unless an annex or a statute says otherwise.
3. **Investment eligibility and licensing compliance are two questions.** A PMA in a no-Besar
   code is eligible (Perpres) and may still find no licensing pathway in OSS until the matrix
   carries a row (PP 28 / Permen 5/2025 Pasal 8(6) «sesuai dengan ketentuan peraturan
   perundang-undangan»). That is friction to disclose, not a closure to publish.
4. **No source states it.** Zero Tier-1 texts; none of the 11 fetched Tier-2 documents (the seat's
   own consensus row reads "not stated verbatim" for all seven providers; the seat then called the
   bridge "a sound inference from the two documented rules" — this dossier disagrees with that
   sentence for the reasons above, and the corner already recorded the same withdrawal on
   2026-08-03, PR #3579, for five articles and two book chapters).

### 4.3 What the inference actually touches in the catalogue
`perpres_body_default_relation.py` measures the `Besar` axis on the PP 28/2025 rows: observed
1,321 · absent 21 · unobserved 217 (no rows at all). Of the 21 absent: **7** are Lampiran II
allocated codes (55201 55203 79903 95291 96100 96210 96220) — closed, by Lampiran II, which is
what the canonical cites (`umkm_rows_corroborated_by_missing_besar_row`); **2** sit on Lampiran II
rows — 55209 «Guest House» a PROVEN segment restriction (`umkm_reserved_segment`), 79110 agen
perjalanan a whole-row candidate (merged ancestry) — and are neither closed nor residual there —
Pasal 3(1)(d) is residual to 3(1)(b); **12** are residual codes published open (38110 55202 55300
56102 56304 56306 70201 73300 74199 79901 79902 86995). For those 12 the honest page reads: *open
under Pasal 3(1)(d)+(2); no `Besar` row in the licensing annex — OSS pathway to be verified per
scope (Permen 5/2025 Pasal 8(6))*. That is a declared gap, not a closure. The sectoral seat's own
pass over the earlier 22-code «no Besar» list found a sector instrument for **0 of 22**.

INFERENCE, stated as such: a missing `Besar` row is decent circumstantial evidence that BKPM never
built that activity's licensing matrix for a >Rp10bn investor, and a client should expect friction
in OSS. It is not a legal closure, and a page that says «CHIUSO PMA» on that basis says more than
the law does.

## 5. Corrections to the seats' findings and to the compiled data (folded, with the primary text)
- **Horticulture 30% cap is gone.** UU 13/2010 Pasal 100 was REPLACED by UU 6/2023 Pasal 33 item
  18: «(1) Pemerintah Pusat mendorong penanaman modal dalam Usaha Hortikultura. (2) … dilakukan
  sesuai dengan ketentuan peraturan perundang-undangan di bidang penanaman modal.» The sectoral
  seat cited the pre-amendment text; no 01xxx horticulture code is capped by statute today.
- **Fisheries is not a PMA closure.** UU 31/2004 Pasal 29(1) admits «badan hukum Indonesia»; a PT
  PMA is one. Cipta Kerja did not amend Pasal 29. 03110/03120 stay open (03110 is canonical
  `located` TERBUKA).
- **The six "suspicious" TERTUTUP codes are legitimate.** 59111/59121/59131/60311/87201/87301
  are «… oleh Pemerintah» titles → class 2. The only over-claim among the 60 TERTUTUP is
  **20119** «Industri Kimia Dasar Anorganik Lainnya»: UU 25/2007 Pasal 12(2)(e)/(f) closes chemical
  weapons and ozone-depleting chemicals, a segment of the code, not the code.
- **Broadcasting 20% (UU 32/2002 Pasal 17), aviation single-majority (UU 1/2009 Pasal 108),
  cabotage (UU 17/2008 Pasal 8)** — unamended by Cipta Kerja; consistent with Lampiran III.
- **Lampiran II compiled rows, four defect classes found on the vault PDF (161564) this
  session** — to be fixed in `data/kbli-filiera/perpres-umkm-reservation.json` by its own PR, not
  here: (a) qualifying parent headings LOST across a line or page break, on four items: item 25
  «Konstruksi gedung yang menggunakan teknologi sederhana dan madya:» (p.6→7; 41011, 41014–41020 —
  41011's cell starts with the orphan «madya:»), item 35 «Konstruksi bangunan yang menggunakan
  teknologi sederhana dan madya:» (p.9; 42911, 42912, 42913 — the text layer reads 42913 as
  «42973»), item 42 «Dekorasi yang menggunakan teknologi sederhana dan madya» (p.12; 43304, 43305,
  43309) and item 43 «Pemasangan kontruksi yang menggunakan teknologi sederhana dan madya:» (p.12;
  43901–43905) — the round-1 fix restored item 25 only, round 2 caught the other three
  (`umkm_segment_rows_from_lost_parent_headings`, 14 codes); (b) p.22 item 106 «Reparasi
  peralatan» ticks **95120 and 95210 under KEMITRAAN** — the compiled row carries 95120 as
  `dialokasikan` (the only dialokasikan row after p.16) and omits 95210; (c) 71204 has TWO rows
  (p.15 item 53 «Pemeriksaan dan pengujian instalasi tenaga listrik: Tenaga listrik tegangan
  rendah/menengah», p.16 «Jasa inspeksi teknik instalasi yang menggunakan teknologi sederhana dan
  madya»), both qualified — the relation had classed the first as whole-row; (d) cells TRUNCATED
  at the top (13121 keeps four of six named weaves and loses «bukan pertenunan karung goni», 42202
  loses «Pemasangan bangunan prafabrikasi untuk konstruksi») or garbled (16291, 16292, 16294,
  23932 — all four readable on the `-layout` text of pp.3-4, round 3). The relation applies all
  corrections as overrides and flags them.

## 6. What the canonical says instead (measured 2026-09-18, md5 dc735b4b…)
| Divergence | Codes | Reading |
|---|---|---|
| Lampiran II row coextensive with the code (13133 by union with Lampiran III), published open | 10307, 10308, 13133, 16291, 16293, 32201, 55106 | closures on the instrument's text (class `umkm_reserved_coextensive`, `canonical_agrees: false`); the relabel needs Zero's go (§8), the reading does not |
| Lampiran II whole-row candidate published open | 10 (3 readable-unproven cells, 7 mixed ancestry) | unresolved — owner's reading (§3.3) |
| Canonical closure broader than the instrument proves | proven narrower: 41016, 41018, 41020, 47111; unresolved coverage: 47222, 47241, 47242, 47244, 47245, 47246, 47249, 47712, 47722 (all located TERBATAS/0%); 20119 (TERTUTUP) | scope review, adjudicate; for the 9 the mixed ancestry is a trigger, not a proof either way |
| Lampiran III 0% whole code published open | 58130, 60102, 60202 | law is clear on ESTABLISHMENT; apply after Zero's go with the expansion route in the note |
| Lampiran III 49% published open | 26513, 30301, 30302, 30303, 51103 | four are segment caps; 51103 crosswalk |
| Sector-law closures published open | 58120, 60101, 60201, 69104 | the instrument is a statute the annex-only `pma_source` cannot see |
| Person-restriction only, published open | 69101 | UU 18/2003 Pasal 23 binds the foreign advocate, not the shareholder — no sourced closure, no sourced openness; page unchanged |
| 99000 TERTUTUP as a government activity | 99000 | unavailable for a different reason (Pasal 2(1a)); `canonical_agrees: true` on the verdict, the label is what differs |
| `TERBATAS` with `pma_max_asing` 100 | 79110 | internal contradiction, cure |
| Located on 65 codes only; 1,494 `declared_gap` | — | by design of the fail-closed disclosure (2026-09-01); the relation is the evidence for widening it |

## 7. Honest gaps
- No government per-code machine-readable PMA table exists in public: `oss.go.id` BUPM pages
  render client-side and the listed URLs 404; `nswi.bkpm.go.id` timed out.
- **Crosswalk provenance (corrected 2026-09-18 after the owner asked; the first wording said
  «BPS conversion table 403 … the repo's own crosswalk», which read as if the official table had
  not been used).** The 2020↔2025 join IS the official BPS table: *Tabel Konversi KBLI 2020 –
  KBLI 2025*, Vol. 2, Katalog 1302033, published 2026-04-22
  (https://www.bps.go.id/id/publication/2026/04/22/909d503355d2b7664e43dea8/tabel-konversi-kbli-2020-kbli-2025.html),
  fetched by browser 2026-07-16 because `bps.go.id` answers 403 to non-browser clients (it did so
  again on 2026-09-18 — that is what the earlier «403» recorded), vault-pinned sha256
  `29f17b3b…724949`, parsed fail-closed by `scripts/kbli_filiera/parse_bps_crosswalk.py` into
  `data/kbli-filiera/bps-crosswalk/edges-lampiran5.json` (Lampiran 5 forward 2020→2025, 2,560
  edges over 1,789 KBLI-2020 codes → 1,559 KBLI-2025 codes; Lampiran 10 reverse identical, 0
  unresolved rows, 0 `sebagian` markers; `parser-run-manifest.json`). No later BPS edition was
  found on 2026-09-18. What is *mechanical* is the join, not the source: BPS records that a 2020
  code split or merged but not which activity went to which heir (Vol. 2 carries no `sebagian`
  markers), so a Lampiran row that names one activity of a split 2020 code reaches every heir —
  this pass found three such wrong-entity matches (58120, 60101, 60201) and cured them on the
  Bidang Usaha text and the KBLI-2025 `uraian` (`split_heir_overlap`), which is the rule §3.3
  now applies to every split.
- Sector statutes were read on `pasal.id`, not on JDIH. UU 12/2011 was fetched from BPK in round 2
  after the refuter caught the misattribution: a Permen is NOT in the Pasal 7(1) list, it is a
  Pasal 8(1)-(2) regulation; §4.2(2) now says so.
- 69101: the ownership / entity-form rule for a law office (whether a PT with a foreign non-advocate
  shareholder may hold the code) was not sourced; UU 18/2003 Pasal 23 binds the person. The code is
  counted neither closed nor open by this dossier.
- BKPM's Naskah Urgensi is drafting rationale — Tier-1 institution, non-binding text; it is cited
  for what the drafters meant, never as law.
- Lampiran II was read from the compiled rows of the vaulted scan (OCR noise survives in some
  `bidang_usaha_text`; four defect classes in §5) plus the `-layout` text of pp.1-16 and 22;
  Lampiran III from the repo's transcription of rendered pages.
- The text-vs-title reading of the 20 coextensive rows and of the narrower rows (§3.3) is this
  session's, on the compiled text and (round 3) on the `-layout` text of pp.1-16; it is recorded per row in `text_vs_title_reading` /
  `narrower_text` and has not been read by a second pair of eyes on the vault PDF cells.
- Whether OSS enforces a Lampiran II reservation on the whole 2025 code or on the named segment
  (the 13 scope-review codes) was not observed — it needs a live OSS probe, not a text.
- The 269-row relation reproduces its own partitions (refuter round 2, #10); it does not by itself
  substantiate the whole-catalogue `located 65 / declared_gap 1,494` figure, which is measured on
  the canonical directly (frontmatter).
- The Bali 18-code measure has no instrument number.
- 11031 and 47826 are named in the body and have no KBLI-2025 code: their 2025 heirs need a
  segment note, not done here.
- The Codex refuter's rounds 1 and 2 are folded (dispositions below); round 3 is recorded when run.

## 8. Decisions that belong to the owner (Legge 5)
1. **Apply the clear-law divergences** (3 Lampiran III 0% codes with the establishment/expansion
   note, 4 sector-law codes, the 7 coextensive Lampiran II codes 10307 10308 13133 16291 16293 32201
   55106, 79110 contradiction, 20119 over-claim) — a `--pma-only` cure on ~16 codes, then Qdrant
   sync + cache bust. The 7 Lampiran II codes are closures on the instrument's text (§3.3); what is
   Zero's here is the publication, not the reading.
2. **Adjudicate the 10 Lampiran II whole-row candidates** row by row — the 3 readable-unproven
   cells against the KBLI-2025 uraian, the 7 mixed-ancestry rows on activity coverage (this relation carries the text,
   `parent_ancestry_clean`, `merged_heir_non_reserved_ancestors`); never as a batch.
3. **Scope-review the 13 located codes** the page closes whole while the instrument proves less
   (§6): for the 4 proven-narrower rows narrow the label to the segment or keep the closure as an
   explicit house policy; for the 9 unresolved retail codes probe OSS or read the 2020→2025
   merger notes before choosing.
4. **Retire the «no Besar ⇒ CHIUSO PMA» label** on the 12 residual codes in favour of the declared
   gap wording of §4.3, or keep it as an explicit house policy stated as such on the page.
5. **Whole-catalogue PMA apply** (the ~1,500 `declared_gap` → residual-open relabel) stays a
   separate go.

## Adversarial review
Seat: Codex (`codex exec --sandbox read-only`, `model_reasoning_effort=high`, default model of the
ChatGPT-account CLI, fresh context), 2026-09-18. Inputs: this dossier, the relation JSON, the
Lampiran III transcription module, and the scratchpad primary texts (read-only). Every finding was
re-verified by this session against the primary text before being folded; the Lampiran II items
behind #9 and #14 were read on the vault PDF itself.

**Round 1 — VERDICT: BLOCKED(1) · 15 MAJOR · 1 MINOR · 3 NOTE.** Disposition:

| # | Sev | Finding (short) | Verified | Disposition |
|---|---|---|---|---|
| 1 | NOTE | quotations verbatim and correctly attributed | yes | retained |
| 2 | MAJOR | Pasal II(1) grandfathers only Pasal 2 + Pasal 6(1)(a),(c),(d),(2),(3),(3a); caps have Pasal 6(4) | yes (`perpres49.txt:241-248`, `178-195`) | §2.2 rewritten |
| 3 | MINOR | «Usaha Besar» is defined — Pasal 1 angka 7 by reference to UU 20/2008; PP 7/2021 Pasal 35 has capital AND sales criteria | yes | §2.2/§2.3 rewritten |
| 4 | MAJOR | property has two cases, Pasal 26(6)(a)/(b) | yes (`permen5-full.txt:1409-1420`) | §2.4 rewritten |
| 5 | MAJOR | "same rank", "never", "no counter-argument" over-stated; PP 28 Pasal 5(3)-(4)+124+126 is the strongest opposing text | yes | §0(b)/§4.2 rewritten: counter-argument stated and answered with Pasal 127(2), 212, 8(6), Perpres 3(2); eligibility vs licensing distinguished |
| 6 | MAJOR | Pasal 5(2) criteria are «dan/atau»; 5(6)-(7) contemplate growth; 26(3) does not reclassify | yes (`perpres10.txt:296-312, 346-354`) | §2.2/§3.3 rewritten: allocation basis = Pasal 5(1)(a) eligible investors |
| 7 | NOTE | headline arithmetic reproduces from the JSON | yes | preserved; every figure recomputed from the regenerated JSON |
| 8 | MAJOR | "22 of 42" is 14; 79110 is TERBATAS not open; md5 5549… ≠ dc73…; located 65 / declared_gap 1,494 | yes | frontmatter, §0, §3.3, §4.3, §6 regenerated from the pinned snapshot |
| 9 | BLOCKER | 41016/41018/41020 sit under item 25's «teknologi sederhana dan madya» (parent lost by the text layer); 47111 row is «Minimarket» | yes — vault PDF p.6-7, p.13 | builder: `PARENT_LOST` override for 41011, 41014-41020, `NARROWER_TEXT` for 47111 and 21022; the four moved to `umkm_reserved_located_scope_review`, not counted; 97 → 83 |
| 10 | MAJOR | promotion of 8 merged retail heirs to closed was circular (canonical status as evidence) | yes (`build_relation.py` v1 lines 95-99) | promotion loop removed; one scope test for all rows; the 8 moved to scope review |
| 11 | MAJOR | press/broadcasting 0% is establishment-only; expansion routes exist | yes (`lampiran3_perpres49_2021.txt:91-97`) | `closure_scope: establishment` + `condition` on 58130/60102/60202/58120/60101/60201; §0, §3.4, §3.5 reworded |
| 12 | MAJOR | 49% is the ordinary limit; entry #7 admits >49% with Menhan approval; radar/military aircraft are segments | yes (`lampiran3_perpres49_2021.txt:23-28`) | class description + §0 row 6 + §3.4 reworded |
| 13 | MAJOR | 99000 is not a central-government activity under Pasal 2(3) | yes | new class `non_commercial_institutional`; §3.2 rewritten, "correct by construction" withdrawn; the government class now asserts its title rule in the builder |
| 14 | MAJOR | 95120 is ticked KEMITRAAN on p.22 item 106; 95210 missing from the compiled rows | yes — vault PDF p.22 | `COLUMN_DEFECT` override → 95102 `umkm_kemitraan_no_bar`; 95120 + 95210 added to the kemitraan list; compiled-data defect recorded in §5 for its own PR |
| 15 | MAJOR | 10307/10308 (tempe/tahu) and 13133 (batik, union of L-II + L-III) are closures on the adopted mappings, not undecided | yes | scope test applied: the two are `whole_row_clean` + `text_vs_title_reading: coextensive`, 13133 carries `union_note`; presented as closures on the instrument's text whose RELABEL is the owner's (Legge 5), not silently deferred — 10 such rows in §3.3 |
| 16 | MAJOR | mixed ancestry proves review, not an open remainder (10794 «pabrikan dan non-pabrikan») | yes | note wording changed on every merged row; §3.3 says so |
| 17 | MAJOR | segment rows lacked `bidang_usaha_text`/parent; candidates carried `foreign_cap_pct: 0` | yes | every Lampiran II row now carries `bidang_usaha_text`, `parent_heading`, `scope_bucket`, `kbli_2020`; candidates carry `foreign_cap_pct: null` + `proposed_cap_pct: 0` |
| 18 | MAJOR | 55209/79110 are on Lampiran II rows, so not residual-open under Pasal 3(1)(d) | yes | residual `also` entries removed; §4.3 split 7 + 2 + 12 |
| 19 | MAJOR | HSF/Dentons were HTTP 403 not fetched; "nine" = documents not firms; PwC/Makarim do not restate; the seat called the bridge "sound inference" | yes (`tier2-lawfirms.md:22-23, 90, 122-124`) | frontmatter, §4.1, §4.2(4) corrected; the disagreement with the seat is stated |
| 20 | NOTE | sampled annex rows match their locators | yes | preserved |

**Round 2** — Codex (`codex exec --sandbox read-only`, `model_reasoning_effort=high`, default model of the ChatGPT-account CLI, fresh context,
inputs: the round-1 dossier and relation, the compiled Lampiran II rows, the vault-PDF text of
pp.6-7 and 22, the builder, the primary texts). Verdict returned: **BLOCKED(5)** — 5 BLOCKER,
6 MAJOR, 2 MINOR, 5 NOTE. Disposition of each, in the builder (v3) and in this text:

| # | Severity | Finding | Verified | Disposition |
|---|---|---|---|---|
| 1 | BLOCKER | split heirs were eligible for whole-code classification only when the canonical had located them — coverage decided on canonical status | yes (`build_relation.py` v2 line 118) | one test for every row, blind to the canonical: `SPLIT_HEIR_OVERLAP` (demonstrated / plausible / disjoint) read on title vs text; `canonical_agrees` recorded afterwards; classes `umkm_reserved_located` + `umkm_reserved_whole_row` (coextensive) merged into `umkm_reserved_coextensive` (19: 13 agree, 6 open) |
| 2 | BLOCKER | 10307/10308/13133 kept as "candidate" in the JSON while the text called them closures | yes | the 6 coextensive rows are class `umkm_reserved_coextensive`, `foreign_cap_pct: 0`, inside `closed_to_pma_codes_in_catalogue`, `canonical_agrees: false`; §0 row 3 = 19, sourced-closed 83 → 89; §8(1) separates the reading (done) from the relabel (Zero's) |
| 3 | BLOCKER | 9 scope-review notes still said the instrument "proves a narrower scope" on mixed ancestry alone | yes (47222 «Minuman tidak beralkohol») | notes split into PROVEN narrower (`scope_review_proven_narrower`, 4) and UNRESOLVED coverage (`scope_review_unresolved_coverage`, 9); §3.3 and §6 say which is which |
| 4 | BLOCKER | 29 `also` entries lacked text/parent/bucket; 105 rows omitted `parent_heading`; 95102 lacked `scope_bucket` | yes (`add()` v2 line 46) | `also` now carries the whole evidence object; every Lampiran II row carries every flag with explicit nulls; 95102 carries `scope_bucket` |
| 5 | NOTE | the other round-1 corrections landed | yes | retained |
| 6 | NOTE | quotations verbatim at the cited articles; Pasal 8(6) matches | yes | retained |
| 7 | NOTE | the strongest opposing construction is a licensing objection, not an investment closure; BKPM's Naskah Urgensi p.8 explains Pasal 8(6) | yes — PDF fetched, sha256 d6545dc2…, p.8 row 1 read | §4.2(2) quotes the drafting rationale as explanatory material; the eligibility-vs-pathway distinction kept |
| 8 | MINOR | Pasal 127(2) governs the Government's scale identification, Pasal 212 is a value check — neither alone defeats the counter-argument | yes (`pp28-body.txt:3489-3506`) | §4.2(1) narrowed to a supporting point; Pasal 8(6) named as the substantive answer |
| 9 | MINOR | a Permen is not in UU 12/2011 Pasal 7(1); it is a Pasal 8(1)-(2) regulation | yes — UU 12/2011 fetched from BPK, Pasal 7-8 read | §4.2(2) and §7 corrected |
| 10 | NOTE | totals reproduce (269 rows, 267 in catalogue, 83 = 4+54+1+13+6+5) | yes | regenerated after the corrections: 89 = 4+54+1+19+7+4 |
| 11 | MAJOR | "75/83" summed to 74 because 99000 was `canonical_agrees: false` against a TERTUTUP canonical; `conditional_other_requirement` = 46333 + absent 47826, not 47221 | yes | agreement rule covers `non_commercial_institutional`; §0 now 76/89; §0 row 9 and §3.6 distinguish primary class from in-catalogue codes carrying the condition |
| 12 | BLOCKER | lost qualifying parents recur on items 35 (42912/42913), 42 (43309) and 43 (43902–43904) — four "coextensive" rows sit under «teknologi sederhana dan madya» | yes — vault PDF pp.9, 12 (`l2-p1-16.txt:300-309, 407-432`) | `PARENT_LOST` covers items 25/35/42/43 (14 children, all segment); coextensive 10 → 6; §5 defect (a) generalised |
| 13 | MAJOR | 21022 is closed whole by Lampiran III entry #6 (100% domestic) regardless of the narrower Lampiran II row; first-class-wins hid it | yes (`lampiran3_perpres49_2021.txt:22`) | closures aggregate across instruments: a closing secondary relation is promoted to primary (`promoted_from_secondary`); 21022 → `foreign_cap_0` (7), scope review 14 → 13 |
| 14 | MAJOR | `scope_flags` never read the row text; 10 rows were `whole_row_clean` AND `narrower` (35111 «< 1 MW», 55209 «Guest House») | yes | the qualifier regex runs on the text (`text_qualifier`); manual readings live in `narrower_text` and decide the class; flag renamed `parent_ancestry_clean` for what it checks; the 10 narrower rows are segments |
| 15 | MAJOR | «Hotel Bintang I» projected onto 55101–55104; barber/salon/laundry onto 96400 | yes | `split_heir_overlap: disjoint` → class `umkm_reserved_crosswalk_projection` (7: 55101–55104, 96400, 95400, 43400), outside the segment count; 80 → 90 segments after the lost parents and narrower rows moved in |
| 16 | MAJOR | UU 18/2003 Pasal 23 restricts the foreign ADVOCATE; it does not state an ownership/entity-form bar | yes (`uu18-pasal23.html`) | 69101 → `sector_law_person_restriction`, not counted, not a finding of openness; §0 row 5b, §3.5, §6, §7 |
| 17 | NOTE | 16 Lampiran II and 13 Lampiran III samples match their locators | yes | retained |
| 18 | NOTE | Tier-2 attribution now supported by `tier2-lawfirms.md` | yes | retained |

**Round 3** — Codex (`codex exec --sandbox read-only`, `model_reasoning_effort=high`, default
model of the ChatGPT-account CLI, fresh context; inputs: the round-2 dossier, relation and builder
(v3), the round-2 findings verbatim, the compiled Lampiran II rows, the `-layout` text of pp.1-16
and 22, BKPM's Naskah Urgensi, UU 12/2011, the primary texts). Verdict returned: **BLOCKED(1)** —
1 BLOCKER, 3 MAJOR, 1 MINOR, 7 NOTE. Disposition of each, in the builder (v4) and in this text:

| # | Severity | Finding | Verified | Disposition |
|---|---|---|---|---|
| 1 | BLOCKER | §0(b) and §4.3 still called 55209 AND 79110 "whole-row candidates" while the relation classes 55209 `umkm_reserved_segment` («Guest House», round-2 #14) — a disposition that landed in the JSON but not in two sentences | yes (`grep 55209` on the round-2 text) | both sentences now read: 55209 a proven SEGMENT restriction, 79110 a whole-row candidate (merged ancestry); the 7+2+12 partition of §4.3 is unchanged |
| 2 | NOTE | every other round-2 disposition landed (canonical-blind test, six closures at cap 0, unresolved notes, full `also` evidence, restored parents, 21022, 99000, alcohol memberships, seven disjoint projections, 69101) | — | retained |
| 3 | NOTE | no material misquotation in §2 (UU 6/2023, Perpres 10 and 49, Permen 5/2025 incl. Pasal 8(6), PP 28/2025 checked at line level) | — | retained |
| 4 | NOTE | the strongest opposing argument (binding annex + Government risk determination) supports a licensing objection, not an investment closure; Pasal 8(6) expressly addresses an unlisted scale; the Naskah Urgensi (p.8, draft paragraphs (6)–(7), enacted as (6)) supports the explanatory attribution only; UU 12/2011 Pasal 7 AND 8 correctly cited | — | retained; §4.2 unchanged |
| 5 | NOTE | totals reproduced (269 rows, 267 in catalogue, 89 = 4+54+1+19+7+4, 76 = 4+54+1+13+4+0, Besar axis 1,321/21/217) — mechanical only, to be regenerated after #6–#8 | yes | regenerated: **90 = 4+54+1+20+7+4**, agreement **76/90**, whole-row candidates 10, segment 93 |
| 6 | MAJOR | 13121, 25932, 42202 carry AFFIRMATIVE textual restrictions on the `-layout` text (six named traditional weaves excl. sack weaving; «diproses secara manual atau semi mekanik»; «Pemasangan bangunan prafabrikasi …») yet sat in the merged-ancestry candidate bucket with `narrower_text: null`; the compiled cells of 13121 and 42202 are truncated at the top. 13122 was named too but its row «Industri kain tenun ikat» is the 2020 title, no restriction | yes (`l2-p1-16.txt:74-82,152-154,255-257`) | three `NARROWER_TEXT` entries → class `umkm_reserved_segment` (93); 13122 stays a merged-ancestry candidate; truncation recorded as defect class (d) in §5 |
| 7 | MAJOR | 16291 is readable on the `-layout` text: grouping «Industri barang anyaman» + «Rotan dan bambu» = the 2025 title, ancestry clean — kept outside the closures only by a hard-coded "unreadable" | yes (`l2-p1-16.txt:109-110`) | 16291 `coextensive`, counted (20 / 90); the other three ex-"unreadable" cells re-read individually and NOT promoted: 16292 and 23932 `enumerated` (named products under a generic title), 16294 `title_widened_2025` («Alat Makan» added in 2025) — `umkm_whole_row_candidates_readable_unproven` |
| 8 | MAJOR | 13133 does not meet the class definition "wholly reserved by its Lampiran II row alone": Lampiran II = tulis + kombinasi, Lampiran III #2 = cap; the JSON carried the union note but labelled the primary row `coextensive` | yes (`l2-p1-16.txt:83-85`, `lampiran3_perpres49_2021.txt:17-18`) | reading `union_with_lampiran_iii` + `closure_basis: union`, stated as the ONE explicit exception in the class description and in §3.3; the aggregate closure stands |
| 9 | MINOR | §3.3 said 10794's 2020 sibling 10793 "is not on the annex" — it is, under KEMITRAAN (`kemitraan_codes_kbli_2020_no_bar`), i.e. not allocated rather than not listed | yes | wording corrected; Pasal 5(5) framed as activity-specific analysis of the merged code |
| 10 | NOTE | the seven crosswalk projections, the 21022 promotion (Lampiran III #6) and the 69101 downgrade are textually supported; "no reservation demonstrated by this projected row" ≠ "no other restriction applies" | — | retained |
| 11 | NOTE | all 174 Lampiran II evidence texts match their compiled row at the stored locator (so upstream truncation survives unchanged); 19 coextensive and 13 Lampiran III entries sampled against the primary text | — | retained; truncation is defect (d) |
| 12 | NOTE | Tier-2 attribution supported (11 documents, 7 providers, 2 failed fetches); Tier-2 consensus cannot resolve per-code scope | — | retained |

Three rounds run; the third returned one BLOCKER that was a narrative lag, not a legal error, and
three MAJOR scope readings that moved 4 codes (3 out of the candidate bucket into segments, 1 into
the closures). The relation is regenerated after every round; the figures in §0 are the round-3
figures.

Post-merge correction 2026-09-18 (owner's question, author's own — no refuter round): §7's first
gap bullet mis-described the crosswalk as «the repo's own» with the BPS table «403»; it is the
official BPS Tabel Konversi (vault-pinned, parsed fail-closed) and only the code-level join is
mechanical. No figure and no verdict changes.
