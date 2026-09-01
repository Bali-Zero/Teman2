---
date: 2026-08-25
domain: operations
client_case: none
adversarial_review: kimi-k3
sources:
  - live scroll of the production Qdrant collection `legal_unified` (physical `legal_unified_hybrid_hybrid`), all 83,969 points, page size 512
  - `apps/backend-rag/backend/core/qdrant_db.py` — `_convert_filter_to_qdrant_format`, `_FLAT_PAYLOAD_COLLECTIONS`, `scroll_strict`
  - `apps/backend-rag/backend/services/ingestion/legal_ingestion_service.py` — `_assert_identity_unclaimed`, `_quarantine_current_points`
  - `research/operations/2026-08-25-legal-document-identity-collision-spec.md` — the identity contract this census sizes
  - PR #4865 (guard), #4869 (index fix), #4873 (refuter answers)
---

# Legal-document identity collision — full-corpus census

> **Why this file exists.** An earlier scan reported "83,969 points / 28 document ids /
> exactly one collision, two documents". That sentence was false, and the error was the
> PROBE, not the world: it filtered on the FLAT `document_id` key, which exists on 5,222
> of 83,969 points. The other 78,747 carry a NESTED `metadata.document_id` and were
> invisible to it. This census resolves BOTH payload shapes.

## Adversarial review

Refuted by **Kimi K3** in the same lane (against PR #4869, whose subject is the guard that
consumes these identities). What its attack changed here:

- **The "destroyed chunks" arithmetic was refused, and rightly.** The refuter's earlier pass
  on the two-document story named two alternative explanations the arithmetic alone does not
  exclude — intra-document id collapse, and partial upsert failure. For PMK 1/2026 both were
  then eliminated by `chunk_index` contiguity (survivors 50–543, no gaps; the colliding
  document occupying 0–49). **That proof does not generalise**, so this census deliberately
  quotes NO corpus-wide destroyed-chunk figure — see the chunk-estimate section, where the
  naive computation goes negative on 17 of 22 rows.
- **Independent corroboration of the claimant counts.** After the census, the production
  guard was executed against live data: it refused `Permen_1_2026` naming 7 foreign
  claimants (7 + the one being ingested = the 8 counted here) and `Permen_2_2026` naming 6.
  Two methods, agreeing, on data neither method wrote.
- **What is NOT established.** The 6,933 claimant-less points are counted but not
  characterised — nobody has established whether they are legacy imports, a different
  writer, or a payload the current pipeline no longer produces. And no integration test
  exercises this path against a real Qdrant, so every server-behaviour claim here rests on
  a measurement taken by hand once, not on a repeatable gate. Both are open ledger rows.

---


STRICTLY READ-ONLY census. Scrolled the entire `legal_unified` collection
(physical: `legal_unified_hybrid_hybrid`) via `next_page_offset` pagination,
page size 512, `with_payload=true`, `with_vectors=false`. No mutation of any
kind was performed against Qdrant, git, or disk (aside from writing this
report and its scratch JSON state).

Resolution rule applied to every point:

- `payload_shape`: `flat` if a top-level `document_id` key is present,
  else `nested` if top-level `metadata` is a dict, else `flat` (anomaly
  fallback bucket — count reported below, was 0 in this scan).
- `effective_document_id` = `payload["document_id"]` if present, else
  `payload["metadata"]["document_id"]`.
- `effective_source` = `source_basename`, else `basename(file_path)`, taken
  from the SAME level that produced `effective_document_id` (i.e. same level
  used for `payload_shape`) — else the literal string `"<none>"`.
- `total_chunks` (chunk-estimate input only): best-effort, same level first,
  falling back to the other level if absent there.

---

## 1. Total points scanned

**83,969** points scanned. Expected **83,969**. Result: **MATCHES**.
Pages consumed: 165 (page size 512).

Payload shape breakdown: `flat`=5,222, `nested`=78,747.
Anomaly fallback (neither top-level `document_id` nor a `metadata` dict present): 0 points.

## 2. Distinct document_id values / unresolvable

- Distinct `effective_document_id` values: **386**
- Points with NO resolvable `document_id` (neither top-level nor nested `metadata.document_id`): **0**

## 3. THE CENSUS — document_ids claimed by more than one distinct effective_source

**22** distinct `document_id` values are claimed by more than one distinct `effective_source`.
Full list below (not top-N), sorted by number of distinct claimants descending, then total points descending.

Note on `<none>`: this is a valid, literal value of `effective_source` per the
resolution rule (a point with neither `source_basename` nor `file_path`).
Where `<none>` appears as one claimant among others for a `document_id`, it is
flagged — it does NOT necessarily indicate a second real colliding document,
only that some points under that id carry no resolvable source of their own.
5 of the 22 collided ids have `<none>` as one of their claimants.

### `Permen_1_2026` — 8 distinct claimants, 1506 total points

| Claimant source | Points | Shape(s) |
|---|---:|---|
| permenperin-no-1-tahun-2026.pdf | 698 | nested |
| PMK_1_2026_Coretax_System.pdf | 494 | flat |
| permenkes-no-1-tahun-2026.pdf | 142 | nested |
| 2026PemenkoEkon001.pdf | 73 | nested |
| PermenImipas_1_2026_Perubahan_Pencegahan_dan_Penangkalan.pdf | 50 | flat |
| Peraturan Menko Pangan Nomor 1 Tahun 2026.pdf | 31 | nested |
| permenpora-no-1-tahun-2026.pdf | 14 | nested |
| permensos-no-1-tahun-2026.pdf | 4 | nested |

### `Permen_2_2026` — 6 distinct claimants, 1285 total points

| Claimant source | Points | Shape(s) |
|---|---:|---|
| Permendikdasmen-no-2-tahun-2026.pdf | 1103 | nested |
| 2026pmkeuangan002.pdf | 111 | nested |
| 2026PemenkoEkon002.pdf | 43 | nested |
| Permenkomdigi-no-2-tahun-2026.pdf | 23 | nested |
| 2 Tahun 2026.pdf | 3 | nested |
| 2026pmnaker002.pdf | 2 | nested |

### `PP_28_2025` — 5 distinct claimants, 887 total points

| Claimant source | Points | Shape(s) |
|---|---:|---|
| PP Nomor 28 Tahun 2025.pdf | 709 | nested |
| PP_28_2025.pdf | 157 | nested |
| PP_28_2025_FULL.pdf | 10 | nested |
| **`<none>`** (no resolvable source) | 9 | nested |
| PP Nomor 28 Tahun 2025 (3).pdf | 2 | nested |

### `UU_UNKNOWN_1945` — 5 distinct claimants, 67 total points

| Claimant source | Points | Shape(s) |
|---|---:|---|
| UUD 1945 dan Amandemen.pdf | 18 | nested |
| UUD_1945_Amd2_20251122_163034_7476b5.pdf | 17 | nested |
| UUD_1945_Amd3_20251122_163034_2ea2aa.pdf | 12 | nested |
| UUD_1945_Amd4_20251122_163034_eb7c5a.pdf | 11 | nested |
| UUD_1945_Amd1_20251122_163034_a0d9f2.pdf | 9 | nested |

### `Permen_4_2026` — 3 distinct claimants, 529 total points

| Claimant source | Points | Shape(s) |
|---|---:|---|
| 2026permen004.pdf | 429 | nested |
| 2026pmkeuangan04.pdf | 56 | nested |
| Permendikdasmen-no-4-tahun-2026.pdf | 44 | nested |

### `Permen_3_2026` — 3 distinct claimants, 313 total points

| Claimant source | Points | Shape(s) |
|---|---:|---|
| 2026pmkeuangan003.pdf | 294 | nested |
| Permendikdasmen-no-3-tahun-2026.pdf | 17 | nested |
| Permenkomdigi-no-3-tahun-2026.pdf | 2 | nested |

### `DOC_UNKNOWN_UNKNOWN` — 2 distinct claimants, 2954 total points

| Claimant source | Points | Shape(s) |
|---|---:|---|
| 2.6b_Lampiran_I.F_Perindustrian_701-1400.pdf | 2484 | nested |
| 2.3_Lampiran_I.C_Kehutanan.pdf | 470 | nested |

### `UU_UNKNOWN_UNKNOWN` — 2 distinct claimants, 2953 total points

| Claimant source | Points | Shape(s) |
|---|---:|---|
| 2.6c Lampiran I.F PP Nomor  28 Tahun 2025 (I.F.1401-2125).pdf | 2072 | nested |
| 2.6b Lampiran I.F PP Nomor  28 Tahun 2025 (I.F.701-1400).pdf | 881 | nested |

### `UU_6_2011` — 2 distinct claimants, 491 total points

| Claimant source | Points | Shape(s) |
|---|---:|---|
| **`<none>`** (no resolvable source) | 261 | nested |
| UU_6_2011_Keimigrasian.pdf | 230 | flat |

### `UU_28_2007` — 2 distinct claimants, 311 total points

| Claimant source | Points | Shape(s) |
|---|---:|---|
| UU Nomor 28 Tahun 2007 _penjelasan_20251122_163034_d39945.pdf | 201 | nested |
| Perubahan Ketiga atas Undang-Undang Nomor 6 Tahun 1983 tentang Ketentuan Umum dan Tata Cara Perpajakan.pdf | 110 | nested |

### `Perda_3_2013` — 2 distinct claimants, 278 total points

| Claimant source | Points | Shape(s) |
|---|---:|---|
| UU_6_2011_Immigration_EN.pdf | 276 | nested |
| UU_6_2011_Immigration_20251122_163034_1244ae.pdf | 2 | nested |

### `UU_1_2026` — 2 distinct claimants, 257 total points

| Claimant source | Points | Shape(s) |
|---|---:|---|
| 2026perkppu01.pdf | 143 | nested |
| UU Nomor 1 Tahun 2026.pdf | 114 | nested |

### `UU_31_2004` — 2 distinct claimants, 204 total points

| Claimant source | Points | Shape(s) |
|---|---:|---|
| UU_31_2004_Perikanan_clean.pdf | 169 | nested |
| **`<none>`** (no resolvable source) | 35 | nested |

### `PP_40_2023` — 2 distinct claimants, 186 total points

| Claimant source | Points | Shape(s) |
|---|---:|---|
| **`<none>`** (no resolvable source) | 167 | nested |
| SE-DIRJEN-IMIGRASI-IMI-941-GR-01-01-2024.pdf | 19 | nested |

### `UU_3_2022` — 2 distinct claimants, 183 total points

| Claimant source | Points | Shape(s) |
|---|---:|---|
| Keolahragaan.pdf | 136 | nested |
| Ibu Kota Negara.pdf | 47 | nested |

### `UU_28_2014` — 2 distinct claimants, 142 total points

| Claimant source | Points | Shape(s) |
|---|---:|---|
| Hak Cipta.pdf | 121 | nested |
| 02-hak-cipta-uu28-2014-employment.pdf | 21 | nested |

### `UU_11_2020` — 2 distinct claimants, 124 total points

| Claimant source | Points | Shape(s) |
|---|---:|---|
| UU-11-2020_20251122_163034_38bf40.pdf | 122 | nested |
| **`<none>`** (no resolvable source) | 2 | nested |

### `UU_8_1983` — 2 distinct claimants, 124 total points

| Claimant source | Points | Shape(s) |
|---|---:|---|
| 68_PMK.03_2022.pdf | 81 | nested |
| Pajak Pertambahan Nilai Barang dan Jasa dan Pajak Penjualan atas Barang Mewah.pdf | 43 | nested |

### `UU_3_1983` — 2 distinct claimants, 61 total points

| Claimant source | Points | Shape(s) |
|---|---:|---|
| UU_4_2023_Financial_Sector_Dev_20251122_163034_e8880d.pdf | 59 | nested |
| UU_4_2023_PPSK_Financial_Sector.pdf | 2 | nested |

### `UU_63_2024` — 2 distinct claimants, 38 total points

| Claimant source | Points | Shape(s) |
|---|---:|---|
| Perubahan Ketiga atas Undang-Undang Nomor 6 Tahun 2011 tentan Keimigrasian.pdf | 28 | nested |
| UU_63_2024_Perubahan_Ketiga_UU_Keimigrasian.pdf | 10 | flat |

### `UU_4_2011` — 2 distinct claimants, 19 total points

| Claimant source | Points | Shape(s) |
|---|---:|---|
| karangasem_sidemen_02_51D4_BA_Lampiran.pdf | 16 | nested |
| jembrana_negara_02_51A7_BA_Lampiran.pdf | 3 | nested |

### `UU_1_2024` — 2 distinct claimants, 14 total points

| Claimant source | Points | Shape(s) |
|---|---:|---|
| Perubahan Kedua atas Undang-Undang Nomor 11 Tahun 2008 tentang Informasi dan Transaksi Elektronik.pdf | 13 | nested |
| 04-electronic-evidence-ite-monitoring.pdf | 1 | nested |

## 4. Summary integers

- Document_ids collided (>1 distinct claimant): **22**
- Total points sitting under a collided identity: **12,926**
- Distinct real source documents involved in collisions (excluding the `<none>` bucket): **57**
- Distinct claimant values involved in collisions (including `<none>` as its own bucket where present): **58**
- Collided ids where `<none>` is one of the claimants: **5**

## 5. Destroyed-chunk estimate per collided identity (ESTIMATE — read the caveats)

For each collided `document_id`, for each claimant source, we take the MAXIMUM
`total_chunks` value observed across that claimant's surviving points (many, not
all, points carry this field). We sum these per-claimant maxima and compare against
the number of points ACTUALLY SURVIVING under that document_id today.

**This is explicitly an ESTIMATE, not an exact figure**, because:
(a) chunks at different hierarchy levels (e.g. section vs paragraph vs sentence)
may not all carry a `total_chunks` field, so the true intended chunk count for a
claimant can be undercounted; (b) a claimant whose points carry `total_chunks` on
NONE of its surviving points cannot be estimated at all — its contribution to the
sum is treated as 0, which understates the true destroyed-chunk count for that
document_id. Rows below flag this explicitly wherever it applies.

### `Permen_1_2026`

| Claimant | max(total_chunks) seen | total_chunks ever observed? |
|---|---:|---|
| permenperin-no-1-tahun-2026.pdf | 521 | yes |
| PMK_1_2026_Coretax_System.pdf | 544 | yes |
| permenkes-no-1-tahun-2026.pdf | 76 | yes |
| 2026PemenkoEkon001.pdf | 73 | yes |
| PermenImipas_1_2026_Perubahan_Pencegahan_dan_Penangkalan.pdf | 50 | yes |
| Peraturan Menko Pangan Nomor 1 Tahun 2026.pdf | 12 | yes |
| permenpora-no-1-tahun-2026.pdf | 13 | yes |
| permensos-no-1-tahun-2026.pdf | — | **NO — cannot be estimated, treated as 0** |

Sum of per-claimant max(total_chunks): **1289**. Points actually surviving under this identity today: **1506**. Difference (estimated destroyed/missing chunks): **-217**. ⚠️ at least one claimant has NO total_chunks data — sum is a floor, not a true total.

### `Permen_2_2026`

| Claimant | max(total_chunks) seen | total_chunks ever observed? |
|---|---:|---|
| Permendikdasmen-no-2-tahun-2026.pdf | 1041 | yes |
| 2026pmkeuangan002.pdf | 111 | yes |
| 2026PemenkoEkon002.pdf | 43 | yes |
| Permenkomdigi-no-2-tahun-2026.pdf | — | **NO — cannot be estimated, treated as 0** |
| 2 Tahun 2026.pdf | — | **NO — cannot be estimated, treated as 0** |
| 2026pmnaker002.pdf | — | **NO — cannot be estimated, treated as 0** |

Sum of per-claimant max(total_chunks): **1195**. Points actually surviving under this identity today: **1285**. Difference (estimated destroyed/missing chunks): **-90**. ⚠️ at least one claimant has NO total_chunks data — sum is a floor, not a true total.

### `PP_28_2025`

| Claimant | max(total_chunks) seen | total_chunks ever observed? |
|---|---:|---|
| PP Nomor 28 Tahun 2025.pdf | 49 | yes |
| PP_28_2025.pdf | — | **NO — cannot be estimated, treated as 0** |
| PP_28_2025_FULL.pdf | — | **NO — cannot be estimated, treated as 0** |
| `<none>` | — | **NO — cannot be estimated, treated as 0** |
| PP Nomor 28 Tahun 2025 (3).pdf | 32 | yes |

Sum of per-claimant max(total_chunks): **81**. Points actually surviving under this identity today: **887**. Difference (estimated destroyed/missing chunks): **-806**. ⚠️ at least one claimant has NO total_chunks data — sum is a floor, not a true total.

### `UU_UNKNOWN_1945`

| Claimant | max(total_chunks) seen | total_chunks ever observed? |
|---|---:|---|
| UUD 1945 dan Amandemen.pdf | — | **NO — cannot be estimated, treated as 0** |
| UUD_1945_Amd2_20251122_163034_7476b5.pdf | — | **NO — cannot be estimated, treated as 0** |
| UUD_1945_Amd3_20251122_163034_2ea2aa.pdf | — | **NO — cannot be estimated, treated as 0** |
| UUD_1945_Amd4_20251122_163034_eb7c5a.pdf | — | **NO — cannot be estimated, treated as 0** |
| UUD_1945_Amd1_20251122_163034_a0d9f2.pdf | — | **NO — cannot be estimated, treated as 0** |

Sum of per-claimant max(total_chunks): **0**. Points actually surviving under this identity today: **67**. Difference (estimated destroyed/missing chunks): **-67**. ⚠️ at least one claimant has NO total_chunks data — sum is a floor, not a true total.

### `Permen_4_2026`

| Claimant | max(total_chunks) seen | total_chunks ever observed? |
|---|---:|---|
| 2026permen004.pdf | 160 | yes |
| 2026pmkeuangan04.pdf | 56 | yes |
| Permendikdasmen-no-4-tahun-2026.pdf | — | **NO — cannot be estimated, treated as 0** |

Sum of per-claimant max(total_chunks): **216**. Points actually surviving under this identity today: **529**. Difference (estimated destroyed/missing chunks): **-313**. ⚠️ at least one claimant has NO total_chunks data — sum is a floor, not a true total.

### `Permen_3_2026`

| Claimant | max(total_chunks) seen | total_chunks ever observed? |
|---|---:|---|
| 2026pmkeuangan003.pdf | 255 | yes |
| Permendikdasmen-no-3-tahun-2026.pdf | — | **NO — cannot be estimated, treated as 0** |
| Permenkomdigi-no-3-tahun-2026.pdf | — | **NO — cannot be estimated, treated as 0** |

Sum of per-claimant max(total_chunks): **255**. Points actually surviving under this identity today: **313**. Difference (estimated destroyed/missing chunks): **-58**. ⚠️ at least one claimant has NO total_chunks data — sum is a floor, not a true total.

### `DOC_UNKNOWN_UNKNOWN`

| Claimant | max(total_chunks) seen | total_chunks ever observed? |
|---|---:|---|
| 2.6b_Lampiran_I.F_Perindustrian_701-1400.pdf | 2954 | yes |
| 2.3_Lampiran_I.C_Kehutanan.pdf | 470 | yes |

Sum of per-claimant max(total_chunks): **3424**. Points actually surviving under this identity today: **2954**. Difference (estimated destroyed/missing chunks): **470**.

### `UU_UNKNOWN_UNKNOWN`

| Claimant | max(total_chunks) seen | total_chunks ever observed? |
|---|---:|---|
| 2.6c Lampiran I.F PP Nomor  28 Tahun 2025 (I.F.1401-2125).pdf | 2072 | yes |
| 2.6b Lampiran I.F PP Nomor  28 Tahun 2025 (I.F.701-1400).pdf | 2953 | yes |

Sum of per-claimant max(total_chunks): **5025**. Points actually surviving under this identity today: **2953**. Difference (estimated destroyed/missing chunks): **2072**.

### `UU_6_2011`

| Claimant | max(total_chunks) seen | total_chunks ever observed? |
|---|---:|---|
| `<none>` | — | **NO — cannot be estimated, treated as 0** |
| UU_6_2011_Keimigrasian.pdf | 86 | yes |

Sum of per-claimant max(total_chunks): **86**. Points actually surviving under this identity today: **491**. Difference (estimated destroyed/missing chunks): **-405**. ⚠️ at least one claimant has NO total_chunks data — sum is a floor, not a true total.

### `UU_28_2007`

| Claimant | max(total_chunks) seen | total_chunks ever observed? |
|---|---:|---|
| UU Nomor 28 Tahun 2007 _penjelasan_20251122_163034_d39945.pdf | 206 | yes |
| Perubahan Ketiga atas Undang-Undang Nomor 6 Tahun 1983 tentang Ketentuan Umum dan Tata Cara Perpajakan.pdf | 47 | yes |

Sum of per-claimant max(total_chunks): **253**. Points actually surviving under this identity today: **311**. Difference (estimated destroyed/missing chunks): **-58**.

### `Perda_3_2013`

| Claimant | max(total_chunks) seen | total_chunks ever observed? |
|---|---:|---|
| UU_6_2011_Immigration_EN.pdf | 175 | yes |
| UU_6_2011_Immigration_20251122_163034_1244ae.pdf | — | **NO — cannot be estimated, treated as 0** |

Sum of per-claimant max(total_chunks): **175**. Points actually surviving under this identity today: **278**. Difference (estimated destroyed/missing chunks): **-103**. ⚠️ at least one claimant has NO total_chunks data — sum is a floor, not a true total.

### `UU_1_2026`

| Claimant | max(total_chunks) seen | total_chunks ever observed? |
|---|---:|---|
| 2026perkppu01.pdf | 143 | yes |
| UU Nomor 1 Tahun 2026.pdf | 33 | yes |

Sum of per-claimant max(total_chunks): **176**. Points actually surviving under this identity today: **257**. Difference (estimated destroyed/missing chunks): **-81**.

### `UU_31_2004`

| Claimant | max(total_chunks) seen | total_chunks ever observed? |
|---|---:|---|
| UU_31_2004_Perikanan_clean.pdf | 59 | yes |
| `<none>` | — | **NO — cannot be estimated, treated as 0** |

Sum of per-claimant max(total_chunks): **59**. Points actually surviving under this identity today: **204**. Difference (estimated destroyed/missing chunks): **-145**. ⚠️ at least one claimant has NO total_chunks data — sum is a floor, not a true total.

### `PP_40_2023`

| Claimant | max(total_chunks) seen | total_chunks ever observed? |
|---|---:|---|
| `<none>` | — | **NO — cannot be estimated, treated as 0** |
| SE-DIRJEN-IMIGRASI-IMI-941-GR-01-01-2024.pdf | 20 | yes |

Sum of per-claimant max(total_chunks): **20**. Points actually surviving under this identity today: **186**. Difference (estimated destroyed/missing chunks): **-166**. ⚠️ at least one claimant has NO total_chunks data — sum is a floor, not a true total.

### `UU_3_2022`

| Claimant | max(total_chunks) seen | total_chunks ever observed? |
|---|---:|---|
| Keolahragaan.pdf | 40 | yes |
| Ibu Kota Negara.pdf | 24 | yes |

Sum of per-claimant max(total_chunks): **64**. Points actually surviving under this identity today: **183**. Difference (estimated destroyed/missing chunks): **-119**.

### `UU_28_2014`

| Claimant | max(total_chunks) seen | total_chunks ever observed? |
|---|---:|---|
| Hak Cipta.pdf | 20 | yes |
| 02-hak-cipta-uu28-2014-employment.pdf | 18 | yes |

Sum of per-claimant max(total_chunks): **38**. Points actually surviving under this identity today: **142**. Difference (estimated destroyed/missing chunks): **-104**.

### `UU_11_2020`

| Claimant | max(total_chunks) seen | total_chunks ever observed? |
|---|---:|---|
| UU-11-2020_20251122_163034_38bf40.pdf | 37 | yes |
| `<none>` | — | **NO — cannot be estimated, treated as 0** |

Sum of per-claimant max(total_chunks): **37**. Points actually surviving under this identity today: **124**. Difference (estimated destroyed/missing chunks): **-87**. ⚠️ at least one claimant has NO total_chunks data — sum is a floor, not a true total.

### `UU_8_1983`

| Claimant | max(total_chunks) seen | total_chunks ever observed? |
|---|---:|---|
| 68_PMK.03_2022.pdf | 54 | yes |
| Pajak Pertambahan Nilai Barang dan Jasa dan Pajak Penjualan atas Barang Mewah.pdf | 23 | yes |

Sum of per-claimant max(total_chunks): **77**. Points actually surviving under this identity today: **124**. Difference (estimated destroyed/missing chunks): **-47**.

### `UU_3_1983`

| Claimant | max(total_chunks) seen | total_chunks ever observed? |
|---|---:|---|
| UU_4_2023_Financial_Sector_Dev_20251122_163034_e8880d.pdf | 61 | yes |
| UU_4_2023_PPSK_Financial_Sector.pdf | — | **NO — cannot be estimated, treated as 0** |

Sum of per-claimant max(total_chunks): **61**. Points actually surviving under this identity today: **61**. Difference (estimated destroyed/missing chunks): **0**. ⚠️ at least one claimant has NO total_chunks data — sum is a floor, not a true total.

### `UU_63_2024`

| Claimant | max(total_chunks) seen | total_chunks ever observed? |
|---|---:|---|
| Perubahan Ketiga atas Undang-Undang Nomor 6 Tahun 2011 tentan Keimigrasian.pdf | 28 | yes |
| UU_63_2024_Perubahan_Ketiga_UU_Keimigrasian.pdf | — | **NO — cannot be estimated, treated as 0** |

Sum of per-claimant max(total_chunks): **28**. Points actually surviving under this identity today: **38**. Difference (estimated destroyed/missing chunks): **-10**. ⚠️ at least one claimant has NO total_chunks data — sum is a floor, not a true total.

### `UU_4_2011`

| Claimant | max(total_chunks) seen | total_chunks ever observed? |
|---|---:|---|
| karangasem_sidemen_02_51D4_BA_Lampiran.pdf | 16 | yes |
| jembrana_negara_02_51A7_BA_Lampiran.pdf | 19 | yes |

Sum of per-claimant max(total_chunks): **35**. Points actually surviving under this identity today: **19**. Difference (estimated destroyed/missing chunks): **16**.

### `UU_1_2024`

| Claimant | max(total_chunks) seen | total_chunks ever observed? |
|---|---:|---|
| Perubahan Kedua atas Undang-Undang Nomor 11 Tahun 2008 tentang Informasi dan Transaksi Elektronik.pdf | — | **NO — cannot be estimated, treated as 0** |
| 04-electronic-evidence-ite-monitoring.pdf | — | **NO — cannot be estimated, treated as 0** |

Sum of per-claimant max(total_chunks): **0**. Points actually surviving under this identity today: **14**. Difference (estimated destroyed/missing chunks): **-14**. ⚠️ at least one claimant has NO total_chunks data — sum is a floor, not a true total.

### Aggregate across all collided identities

- Sum of per-claimant max(total_chunks), summed across ALL collided ids: **12594**
- Points actually surviving under a collided identity (all collided ids): **12926**
- Aggregate difference (ESTIMATE of destroyed/missing chunks, floor value — see caveats above): **-332**

## 6. Points with NO resolvable claimant at all

**6,933** points have neither `source_basename` nor a usable
`file_path` at their resolution level (`effective_source == "<none>"`). These are
the identities the guard cannot protect by its own documented residual hole: with
no source to compare against, no guard logic keyed on `source_basename`/`file_path`
can ever detect that these points collide with anything.

(Note: `no_source_count` and `no_claimant_at_all_count` are identical in this scan —
6,933 — because `effective_source=="<none>"` is defined exactly as
"neither field present", so the two measures coincide by construction.)

