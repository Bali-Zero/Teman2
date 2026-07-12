---
date: 2026-07-11
domain: company
client_case: none (production data quality — KBLI Navigator gold editorial layer)
sources:
  - apps/mouth/data/kbli-gold-all.json (428-entry editorial gold layer, this session's on-disk read)
  - apps/mouth/data/KBLI_2025_FINAL_CLEAN.json (1559-entry authoritative dataset, cross-referenced)
  - data/source_documents/tka_kbli_README.md (Kepmenaker 228/2019 TKA positive-list provenance)
  - research/operations/2026-07-08-kbli-editorial-content-audit.md (PR #2164 precedent — 11 confirmed mis-assignments)
  - PR #2164 (5b4a983925, merged 2026-07-08/09) diff, read verbatim this session
adversarial_review: gpt-5.5
---

# KBLI gold-layer certification — 428 entries, post-#2164

**Mandate**: certify the REST of `apps/mouth/data/kbli-gold-all.json` (post PR #2164, which
purged 8 mis-assigned gold entries + 128 cross-tagged `tkaInfo` blocks) is coherent — same
defect class, different survivors.

## Method

1. Precondition check: confirmed `apps/mouth/data/kbli-gold-all.json` last touched by #2164
   (merged), zero uncommitted changes on main, zero open PRs touching it, and the concurrent
   KBLIREGEN work (branch `agent/air-m5/mouth/kbli-editorials`) targets
   `scripts/kbli_triangle/editorial_drafts/` — a disjoint surface. Safe to proceed.
2. Cross-referenced all 428 gold keys against the 1559-code authoritative dataset
   (`KBLI_2025_FINAL_CLEAN.json`) — 8 keys are dead orphans (not in the 1559 set, page doesn't
   render them; already documented in the #2164 audit's own Residuals section, not a new finding).
3. **tkaInfo.categoryName coherence** — grouped all 146 surviving `tkaInfo` blocks by
   `categoryName`, checked each cluster's KBLI-division homogeneity against its label. Found
   9 multi-division clusters that are legitimately coherent (same KBLI *section*, different
   divisions — e.g. Accommodation §55 + Food/Bev §56 both "Akomodasi & Makan/Minum" is correct),
   and 1 defect cluster spanning 3 wrongly-labeled divisions (below).
4. **Exact-duplicate content scan** (sha256 of `whatItMeans`/`baliContext` across all 428) —
   found 2 duplicate clusters, both confirmed benign (a generic "contact Bali Zero" placeholder
   reused across 7 unrelated codes with no authored Bali-context yet, and a legitimate shared
   agriculture-context paragraph across 2 genuinely adjacent farming codes).
5. **Cross-lingual anchor scan** (curated Indonesian-noun → expected-English-synonym dictionary,
   ~65 anchors) run across all 428 `whatItMeans`/`baliContext` pairs, to catch the #2164 defect
   signature (official judul about X, gold prose about unrelated Y). 14 total flags raised,
   all 14 manually verified as false positives (translation-vocabulary misses in my own
   anchor list, e.g. "wine" not in my beverage-synonym list) — zero new theme mis-assignments
   found by this method.
6. **Known-bad-theme leak scan** — checked whether the exact contaminant themes from #2164
   (disco/karaoke/shisha/P2P-lending) appear on any code OTHER than their legitimate home code.
   Zero leaks found — the #2164 fix holds.
7. **Dangling cross-reference scan** — extracted all 5-digit code references inside
   `youllAlsoNeed` and checked existence in the 1559-code authoritative set. Found a real,
   substantial gap (below). First-pass regex (bold-only) undercounted by 45%; a fresh-context
   adversarial refuter caught this and the corrected permissive-regex count is reported.
8. **Untranslated-content scan** — flagged entries whose `whatItMeans` is substantially raw
   Indonesian KBLI `uraian` text rather than authored English prose.
9. **Adversarial refute** (devils-advocate subagent, fresh context, zero trust in my reasoning)
   on both candidate defects before any fix — verdicts folded into Findings below.

### Scope of "PASS" — corrected (R1, gpt-5.5)

Each `kbli-gold-all.json` entry has **6 editorial fields**: `whatItMeans`, `whatYouNeed`,
`whatChanged`, `baliContext`, `youllAlsoNeed`, `zantaraOpener`. The content-correctness scans
above (duplicate-content #4, cross-lingual anchor #5, known-bad-theme-leak #6) check only
`whatItMeans` and `baliContext` — **2 of the 6 fields**. `whatYouNeed`, `whatChanged`, and
`zantaraOpener` are not content-checked by any method in this pass. `youllAlsoNeed` is
existence-checked (does the referenced code exist — Findings below) but not checked for
editorial correctness/relevance. There is no curated anchor dictionary beyond the ~65-term
cross-lingual list built ad hoc for this session, and no human-reviewer transcript. A code
tagged **PASS** in the table below means: *not flagged by these heuristics, on the 2 of 6 fields
they cover* — it is a heuristic screen, not a certification that the entry's editorial content is
correct or complete. The report title and mandate ("certify... is coherent") overstate this scope;
read every PASS/FIXED/SUSPECT verdict below against this narrower definition.

## Findings

### FIXED — tkaInfo.categoryName cross-leak, 3 KBLI divisions, 7 codes

`categoryId: 4` is shared correctly across food (§10, "Industri Makanan") and beverage (§11,
"Industri Minuman") manufacturing clusters — but 3 OTHER divisions sharing that same
`categoryId` bucket carry a **wrong** `categoryName`, borrowed from an unrelated division:

| Codes | Official judul (division) | Wrong categoryName | Correct division is |
|---|---|---|---|
| 23961, 23969 | Marble/stone products (§23, Non-Metallic Mineral Products) | "Industri Bahan Kimia" (Chemicals, §20) | §23 |
| 16291, 16293 | Rattan/bamboo weaving, non-furniture wood carving (§16, Wood Products) — 16293's own title says "Bukan Furnitur" (NOT furniture) | "Industri Furnitur" (Furniture, §31) | §16 |
| 32111, 32112, 32120 | Gemstone/jewelry manufacturing (§32, Other Manufacturing) | "Industri Minuman" (Beverages, §11 — name literally borrowed from the correct neighbor cluster) | §32 |

The `whatItMeans`/`baliContext` prose on all 7 codes is accurate and on-topic — only the
`tkaInfo.categoryName` label is wrong. Same defect species as #2164 (label lies about section),
narrower blast radius (label-only, not full-entry content swap).

**Adversarial review verdict**: data fact CONFIRMED, but my proposed remediation (rewrite to a
new hand-authored division-accurate label) was **REJECTED** — the refuter found
`data/source_documents/tka_kbli_README.md` explicitly states *"No per-KBLI join. Deliberate
(Zero, 2026-07-01): the decree's structure is national, not per-KBLI, so spreading it across
1559 codes would fake a specificity the law does not have"* — and the #2164 audit report's own
Residuals section already flags whether `tkaInfo` should exist per-code at all as **"a business
decision (Zero)"**, not an engineering fix. Writing a new label would invent a phantom
replacing a phantom with the same unverified provenance. **Fix applied: delete-only** (exact
precedent match to #2164's 128 removals — same operation, same justification: categoryName
provably inconsistent with the code's real section). This does NOT resolve the open business
question (keep/redesign/remove tkaInfo entirely) — it removes 7 more instances of the
already-flagged failure mode using the already-established remedy, nothing more.

### SUSPECT-unconfirmed — dangling phantom-code references in `youllAlsoNeed`, 164/428 entries

`youllAlsoNeed` recommends KBLI codes that do not exist anywhere in the 1559-code authoritative
2025 dataset — **83 unique phantom codes**, most plausibly stale KBLI-2020/2017 codes never
migrated in the 2025 transition (structurally correct 5-digit format, just absent from the
current classification). Top offenders: `47719`/`47999` (46 references each), `68200` (16),
`74909` (13), `69100` (12).

**Adversarial review verdict (R1, gpt-5.5)**: CONFIRMED as a real defect (5-sample-verified
genuinely absent from the 1559 set), but the previously-reported permissive-regex count
(77 codes / 159 entries) was **itself still incomplete** — a full unfiltered rerun (every
standalone 5-digit token in `youllAlsoNeed`, cross-checked against the 1559-code authoritative
set) yields **83 unique phantom codes across 164 entries**. There is no exclusion rule that
legitimately produces 77/159 from the underlying data; that number undercounted for the same
class of reason as the original 54/132 pass (regex + counting methodology, not a deliberate
scope decision). 83/164 is the number this certification now stands behind. No safe
automatic remediation exists (would require domain knowledge of the correct replacement code per
phantom reference, not just deletion) — **ships as SUSPECT-unconfirmed / follow-up-lane**, not
an in-PR fix, per the mandate's own guidance for unconfirmed suspects. Recommend the deploy lane
or a dedicated follow-up task re-derive the 83→correct-code mapping (likely via the
`KBLI_2017_TO_2025_MAPPING.json` crosswalk, though that file currently only covers 12 curated
mappings — insufficient on its own).

### SUSPECT-unconfirmed — untranslated raw-Indonesian content, 9 entries

Codes `01133, 01299, 35111, 38211, 43211, 52291, 52311, 52329, 85330` have `whatItMeans`
substantially in raw Indonesian KBLI `uraian` prose ("Kelompok ini mencakup...") rather than
authored English editorial content, and 7 of the 9 also share a generic "Contact Bali Zero for
location-specific advice" placeholder `baliContext` (benign — see Method #4). Content is
**accurate** (not mis-assigned, just thin/unauthored) — a completeness gap, not a
correctness defect. Not fixed in this PR (writing new English editorial prose requires domain
authoring judgment outside this certification's scope).

### SUSPECT-unconfirmed — 8 dead orphan keys, only 2 of 8 are actually benign

`64921, 85300, 85491, 85499, 85600, 86903, 96120, 96130` are gold keys not present in the
1559-code authoritative dataset. Each carries internally-coherent, on-topic content (KSP
cooperative, SMK vocational school, health spa, beauty salon, etc.) — the mismatch is
existential (dead code, page never renders it), not a content-quality defect on its own face.
Already documented in the #2164 audit's own Residuals section as dead orphans — not a new
discovery.

**Adversarial review verdict (R1, gpt-5.5)**: the "benign / no action" characterization was
**REFUTED**. A reverse-reference scan (does any OTHER entry's `youllAlsoNeed` actively recommend
this dead code?) shows 6 of the 8 are NOT inert — they are actively pointed-to:
`85491`/`85499`/`85600` form a closed loop of 3 dead education codes that all recommend each
other, and `86903`/`96120`/`96130` form a closed loop of 3 dead spa/beauty codes that all
recommend each other. Only `64921` and `85300` have zero incoming references and are genuinely
inert. This means 6 of the 8 "benign" orphans are the SAME defect as the phantom-cross-reference
finding above (a live gold entry recommending a dead code), just discovered from the opposite
direction (orphan-key audit vs. reference audit) — not a separate, lower-severity issue. Recorded
here as SUSPECT-unconfirmed, not fixed in this PR (same remediation-scope argument as the
phantom-reference finding: deleting the dead orphan key itself is a separate business call from
deleting/rewriting the 6 dangling recommendations that point at it).

## Cross-check against the parallel S4 gate (orchestrator, same hour)

The orchestrator's S4 gate (a separate lane, live-page probes of the purged family) passed 5
calibration facts mid-session, verified against this session's own on-disk read with zero
correction needed: (1) 428 is the current count (436 was pre-#2164); (2) 56303/56304/56305
correctly have no gold entry at all (never appeared in this table — my scans never treated
their absence as a defect); (3) 70209 correctly has only 6 fields and no `tkaInfo` by design
— re-verified its editorial content line-by-line against the official judul ("Aktivitas
Konsultasi Manajemen dan Bisnis Lainnya" — general business/management consulting): all 5
fields on-topic and consistent, its `SUSPECT-unconfirmed` tag in the table below is solely
for the unrelated `youllAlsoNeed` phantom-code finding (`74909`), not for missing `tkaInfo`;
(4)/(5) field-set and live-page-out-of-scope both match this report's Method section
verbatim. No table entries changed as a result of this cross-check.

## Verdict table (428 entries)

| Code | Judul | Verdict | Note |
|---|---|---|---|
| 01111 | Pertanian Jagung | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 01112 | Pertanian Serealia Selain Padi dan Jagung | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 01113 | Pertanian Kedelai | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 01114 | Pertanian Kacang Tanah | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 01115 | Pertanian Kacang Hijau | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 01131 | Pertanian Sayuran Daun | PASS |  |
| 01133 | Pertanian Sayuran Buah | SUSPECT-unconfirmed | whatItMeans substantially untranslated raw Indonesian |
| 01299 | Pertanian Tanaman Tahunan Lainnya YTDL | SUSPECT-unconfirmed | whatItMeans substantially untranslated raw Indonesian |
| 03212 | Pembudidayaan Ikan Hias Air Laut yang Tidak Dilindungi | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 03222 | Pembudidayaan Ikan Hias Air Tawar yang Tidak Dilindungi | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 03232 | Pembudidayaan Ikan Hias Air Payau yang Tidak Dilindungi | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 10501 | Industri Susu Segar dan Krim | PASS |  |
| 10503 | Industri Es Krim | PASS |  |
| 10504 | Industri Es yang Dapat Dimakan dan Es Pencuci Mulut | PASS |  |
| 10710 | Industri Produk Bakeri | PASS |  |
| 10732 | Industri Cokelat dan Kembang Gula dari Cokelat | PASS |  |
| 10750 | Industri Makanan dan Masakan Olahan | PASS |  |
| 10761 | Pengolahan Kopi | PASS |  |
| 10792 | Industri Kue Basah | PASS |  |
| 10793 | Industri Produk Makanan dari Kelapa | PASS |  |
| 10794 | Industri Kerupuk, Keripik, Peyek, dan Sejenisnya | PASS |  |
| 10795 | Industri Sari Nabati dan Krimer Nabati | PASS |  |
| 10796 | Industri Dodol | PASS |  |
| 10797 | Industri Infusi Herbal/Herb Infusion | PASS |  |
| 10798 | Industri Bahan Makanan dari Rumput Laut | PASS |  |
| 11010 | Industri Penyulingan, Pemurnian, dan Pencampuran Minuman Beralkohol | PASS |  |
| 11020 | Industri Minuman Beralkohol Hasil Fermentasi Anggur dan Hasil Pertanian Lainnya | PASS |  |
| 11030 | Industri Minuman Beralkohol Hasil Fermentasi Malt | PASS |  |
| 11051 | Industri Air Kemasan | PASS |  |
| 11053 | Industri Minuman Ringan | PASS |  |
| 11059 | Industri Minuman Lainnya | PASS |  |
| 13133 | Industri Kain Batik | PASS |  |
| 16103 | Pengawetan Rotan, Bambu, dan Sejenisnya | PASS |  |
| 16104 | Pengolahan Rotan | PASS |  |
| 16291 | Industri Barang Anyaman dari Rotan dan Bambu | FIXED | tkaInfo.categoryName cross-leak deleted (matches #2164 precedent) |
| 16292 | Industri Barang Anyaman dari Tanaman Selain Rotan dan Bambu | PASS |  |
| 16293 | Industri Kerajinan Ukiran dari Kayu Bukan Furnitur | FIXED | tkaInfo.categoryName cross-leak deleted (matches #2164 precedent) |
| 16294 | Industri Alat Dapur dan Alat Makan dari Kayu, Rotan, dan Bambu | PASS |  |
| 18111 | Pencetakan Umum | PASS |  |
| 18112 | Pencetakan Khusus | PASS |  |
| 18113 | Pencetakan Tiga Dimensi (3D) | PASS |  |
| 20232 | Industri Kosmetik untuk Manusia, Cairan Lensa Kontak | PASS |  |
| 20235 | Industri Parfum Sesuai Pesanan | PASS |  |
| 21022 | Industri Produk Obat Bahan Alam untuk Manusia | PASS |  |
| 23961 | Industri Barang dari Batu Marmer | FIXED | tkaInfo.categoryName cross-leak deleted (matches #2164 precedent) |
| 23962 | Industri Barang dari Batu Granit | PASS |  |
| 23969 | Industri Barang dari Batu Lainnya | FIXED | tkaInfo.categoryName cross-leak deleted (matches #2164 precedent) |
| 26602 | Industri Peralatan Elektromedik dan Elektroterapi | PASS |  |
| 26701 | Industri Peralatan Fotografi | PASS |  |
| 28193 | Industri Mesin Pendingin | PASS |  |
| 28250 | Industri Mesin Pengolahan Makanan, Minuman dan Tembakau | PASS |  |
| 30111 | Industri Kendaraan Air dan Bawah Air Berawak | PASS |  |
| 30120 | Industri Kapal dan Perahu Untuk Tujuan Wisata atau Rekreasi dan Olahraga | PASS |  |
| 31011 | Industri Furnitur Dari Kayu | PASS |  |
| 31012 | Industri Furnitur dari Rotan dan Bambu | PASS |  |
| 32111 | Industri Permata | FIXED | tkaInfo.categoryName cross-leak deleted (matches #2164 precedent) |
| 32112 | Industri Perhiasan dari Logam Mulia | FIXED | tkaInfo.categoryName cross-leak deleted (matches #2164 precedent) |
| 32113 | Industri Barang Berharga dari Logam Mulia Bukan Perhiasan | PASS |  |
| 32114 | Industri Perhiasan dari Mutiara | PASS |  |
| 32119 | Industri Barang Berharga Lainnya dari Logam Mulia | PASS |  |
| 32120 | Industri Perhiasan Imitasi dan Barang Sejenis | FIXED | tkaInfo.categoryName cross-leak deleted (matches #2164 precedent) |
| 32201 | Industri Alat Musik Tradisional | PASS |  |
| 32300 | Industri Peralatan dan Perlengkapan Olahraga | PASS |  |
| 32502 | Industri Peralatan Kedokteran dan Kedokteran Gigi, serta Perlengkapan Ortopedi dan Prostetik | PASS |  |
| 32509 | Industri Peralatan Kedokteran dan Kedokteran Gigi, serta Perlengkapan Lainnya | PASS |  |
| 33133 | Reparasi dan Pemeliharaan Peralatan Fotografi dan Optik | PASS |  |
| 35111 | Pembangkitan Tenaga Listrik dari Sumber Energi Tidak Terbarukan yang Menghasilkan Emisi | SUSPECT-unconfirmed | whatItMeans substantially untranslated raw Indonesian |
| 35112 | Pembangkitan Tenaga Listrik dari Sumber Energi Tidak Terbarukan yang Tidak Menghasilkan Emisi | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 35133 | Pengoperasian Fasilitas atau Stasiun Pengisian Daya untuk Kendaraan dan Peralatan Listrik | PASS |  |
| 38211 | Pengolahan Sampah Tidak Berbahaya untuk Menghasilkan Energi | SUSPECT-unconfirmed | whatItMeans substantially untranslated raw Indonesian |
| 41011 | Konstruksi Konvensional Gedung Hunian | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 41012 | Konstruksi Konvensional Gedung Perkantoran | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 41014 | Konstruksi Konvensional Gedung Perbelanjaan | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 41015 | Konstruksi Konvensional Gedung Kesehatan | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 41016 | Konstruksi Konvensional Gedung Pendidikan | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 41017 | Konstruksi Konvensional Gedung Penginapan | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 41018 | Konstruksi Konvensional Gedung Hiburan dan Olahraga | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 41019 | Konstruksi Konvensional Gedung Lainnya | PASS |  |
| 41020 | Konstruksi Prapabrikasi Bangunan Gedung | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 42994 | Konstruksi Bangunan Sipil Fasilitas Olahraga | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 43120 | Penyiapan Lahan | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 43211 | Pemasangan Jaringan Listrik | SUSPECT-unconfirmed | whatItMeans substantially untranslated raw Indonesian |
| 43221 | Pemasangan Saluran Air (Plumbing) | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 43222 | Pemasangan Sistem Pemanas dan Geotermal | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 43224 | Pemasangan Pendingin dan Ventilasi Udara | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 43301 | Pemasangan Kaca, Pintu, Kusen, Jendela, dan Sejenisnya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 43302 | Pengerjaan Lantai, Dinding, dan Plafon | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 43303 | Pengecatan | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 43903 | Pemasangan Rangka dan Atap/Roof Covering | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 43909 | Konstruksi Khusus Lainnya YTDL | PASS |  |
| 46100 | Perdagangan Besar atas dasar Balas Jasa (Fee) atau Kontrak | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46201 | Perdagangan Besar Padi dan Palawija | PASS |  |
| 46203 | Perdagangan Besar Bunga dan Tanaman Hias | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46206 | Perdagangan Besar Ikan dan Biota Air Hidup Lainnya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46207 | Perdagangan Besar Hasil Kehutanan dan Perburuan | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46209 | Perdagangan Besar Hasil Pertanian dan Hewan Hidup Lainnya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46311 | Perdagangan Besar Beras | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46312 | Perdagangan Besar Buah-buahan | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46313 | Perdagangan Besar Sayuran | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46314 | Perdagangan Besar Kopi, Teh, dan Kakao | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46315 | Perdagangan Besar Minyak dan Lemak Nabati | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46319 | Perdagangan Besar Bahan Makanan dan Minuman Hasil Pertanian Lainnya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46321 | Perdagangan Besar Daging Sapi dan Daging Sapi Olahan | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46322 | Perdagangan Besar Daging Ayam dan Daging Ayam Olahan | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46323 | Perdagangan Besar Daging dan Daging Olahan Lainnya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46324 | Perdagangan Besar Hasil Perikanan dan Olahan Terkait | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46325 | Perdagangan Besar Telur dan Hasil Olahan Telur | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46326 | Perdagangan Besar Susu dan Produk Susu | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46327 | Perdagangan Besar Minyak dan Lemak Hewani | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46329 | Perdagangan Besar Bahan Makanan dan Minuman Hasil Peternakan dan Perikanan Lainnya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46331 | Perdagangan Besar Gula, Cokelat, dan Kembang Gula | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46332 | Perdagangan Besar Produk Bakeri | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46333 | Perdagangan Besar Minuman Beralkohol | PASS |  |
| 46334 | Perdagangan Besar Minuman Nonalkohol Bukan Susu | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46335 | Perdagangan Besar Rokok dan Tembakau | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46339 | Perdagangan Besar Makanan dan Minuman Lainnya | PASS |  |
| 46412 | Perdagangan Besar Pakaian | PASS |  |
| 46420 | Perdagangan Besar Furnitur, Karpet, Perlengkapan Pencahayaan untuk Rumah Tangga, Perkantoran, dan Pertokoan | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46430 | Perdagangan Besar Alat Fotografi dan Barang Optik | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46441 | Perdagangan Besar Sediaan Farmasi untuk Manusia | PASS |  |
| 46491 | Perdagangan Besar Peralatan Masak, Peralatan Dapur, dan Elektronik Rumah Tangga | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46494 | Perdagangan Besar Perhiasan dan Jam | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46496 | Perdagangan Besar Tas, Dompet, Koper, Ransel, dan Sejenisnya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46511 | Perdagangan Besar Komputer dan Perlengkapan Komputer | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46512 | Perdagangan Besar Perangkat Lunak | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46738 | Perdagangan Besar Berbagai Macam Material Bangunan | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 46791 | Perdagangan Besar Alat Kesehatan dan Laboratorium untuk Manusia | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47111 | Perdagangan Eceran Berbagai Macam Barang yang Utamanya Makanan, Minuman, atau Tembakau dengan Sistem Swalayan | PASS |  |
| 47112 | Perdagangan Eceran Berbagai Macam Barang yang Utamanya Makanan, Minuman, atau Tembakau Selain dengan Sistem Swalayan | PASS |  |
| 47191 | Perdagangan Eceran Berbagai Macam Barang yang Utamanya Bukan Makanan, Minuman, atau Tembakau dengan Sistem Swalayan | PASS |  |
| 47192 | Perdagangan Eceran Berbagai Macam Barang yang Utamanya Bukan Makanan, Minuman, atau Tembakau Selain dengan Sistem Swalayan | PASS |  |
| 47221 | Perdagangan Eceran Minuman Beralkohol | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47222 | Perdagangan Eceran Minuman Tidak Beralkohol | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47242 | Perdagangan Eceran Roti, Kue Kering, serta Kue Basah dan Sejenisnya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47243 | Perdagangan Eceran Kopi, Gula Pasir, Gula Merah, dan Sejenisnya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47245 | Perdagangan Eceran Daging Olahan | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47246 | Perdagangan Eceran Ikan Olahan | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47249 | Perdagangan Eceran Makanan Lainnya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47401 | Perdagangan Eceran Komputer dan Perlengkapannya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47402 | Perdagangan Eceran Peralatan dan Produk Gim Video serta Sejenisnya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47403 | Perdagangan Eceran Perangkat Lunak (Software) | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47404 | Perdagangan Eceran Telepon beserta Aksesorisnya | PASS |  |
| 47406 | Perdagangan Eceran Peralatan Audio dan Video | PASS |  |
| 47521 | Perdagangan Eceran Bahan dan Material Konstruksi | PASS |  |
| 47526 | Perdagangan Eceran Bahan-bahan Energi Terbarukan | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47591 | Perdagangan Eceran Furnitur | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47592 | Perdagangan Eceran Peralatan Listrik Rumah Tangga, Peralatan Penerangan, dan Perlengkapannya | PASS |  |
| 47620 | Perdagangan Eceran Peralatan dan Perlengkapan Olahraga | PASS |  |
| 47690 | Perdagangan Eceran Khusus Barang Kesenian dan Rekreasi YTDL | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47711 | Perdagangan Eceran Pakaian | PASS |  |
| 47712 | Perdagangan Eceran Sepatu, Sandal, dan Alas Kaki Lainnya | PASS |  |
| 47714 | Perdagangan Eceran Tas, Dompet, Koper, Ransel, dan Sejenisnya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47721 | Perdagangan Eceran Sediaan Farmasi untuk Manusia di Apotek | PASS |  |
| 47722 | Perdagangan Eceran Sediaan Farmasi untuk Manusia Selain di Apotek | PASS |  |
| 47723 | Perdagangan Eceran Obat Bahan Alam untuk Manusia | PASS |  |
| 47724 | Perdagangan Eceran Kosmetik untuk Manusia | PASS |  |
| 47725 | Perdagangan Eceran Alat Kesehatan untuk Manusia | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47729 | Perdagangan Eceran Bahan Baku Farmasi dan Alat Kesehatan Lainnya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47731 | Perdagangan Eceran Alat Fotografi dan Perlengkapannya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47733 | Perdagangan Eceran Kacamata | PASS |  |
| 47735 | Perdagangan Eceran Barang Perhiasan | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47746 | Perdagangan Eceran Barang Antik | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47751 | Perdagangan Eceran Hewan Kesayangan (Pet Animals) | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47761 | Perdagangan Eceran Bunga Potong/Florist | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47774 | Perdagangan Eceran Aromatik/Penyegar (Minyak Asiri) | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47779 | Perdagangan Eceran Bahan Kimia, Aromatik/Penyegar (Minyak Asiri), dan Bahan Bakar Selain Bahan Bakar untuk Kendaraan Bermotor Lainnya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47781 | Perdagangan Eceran Cendera mata, Kerajinan, dan Barang-barang Keagamaan | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47782 | Perdagangan Eceran Lukisan | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47792 | Perdagangan Eceran Alat Transportasi Darat Tidak Bermotor dan Perlengkapannya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47795 | Perdagangan Eceran Perlengkapan Pengendara Kendaraan Bermotor | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47811 | Perdagangan Eceran Mobil Baru | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47812 | Perdagangan Eceran Mobil Bekas | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47820 | Perdagangan Eceran Suku Cadang dan Aksesori Mobil | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47831 | Perdagangan Eceran Sepeda Motor Baru | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47901 | Platform Digital Intermediasi Perdagangan Eceran | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 47909 | Jasa Intermediasi Perdagangan Eceran Lainnya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 49111 | Angkutan Kereta Wisata Antarkota | PASS |  |
| 49211 | Angkutan Kereta Wisata dalam Kota | PASS |  |
| 49213 | Angkutan Perkotaan | PASS |  |
| 49231 | Angkutan Bermotor untuk Barang Umum | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 49292 | Angkutan Pariwisata | PASS |  |
| 49293 | Angkutan Taksi | PASS |  |
| 49295 | Angkutan Sewa | PASS |  |
| 49296 | Angkutan Ojek Motor | PASS |  |
| 49297 | Angkutan Tidak Bermotor untuk Penumpang | PASS |  |
| 49299 | Transportasi Darat Lainnya untuk Penumpang YTDL | PASS |  |
| 50113 | Angkutan Laut Dalam Negeri untuk Wisata | PASS |  |
| 50115 | Angkutan Laut Luar Negeri untuk Wisata | PASS |  |
| 50131 | Angkutan Penyeberangan Umum Antarprovinsi untuk Penumpang | PASS |  |
| 50132 | Angkutan Penyeberangan Umum Antarkabupaten/kota untuk Penumpang | PASS |  |
| 50133 | Angkutan Penyeberangan Umum Dalam Kabupaten/kota untuk Penumpang | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 50213 | Angkutan Sungai dan Danau untuk Wisata | PASS |  |
| 51101 | Angkutan Udara Niaga Berjadwal untuk Penumpang | PASS |  |
| 51102 | Angkutan Udara Niaga Tidak Berjadwal untuk Penumpang | PASS |  |
| 52291 | Angkutan Multimoda | SUSPECT-unconfirmed | whatItMeans substantially untranslated raw Indonesian |
| 52311 | Jasa Pengurusan Transportasi (JPT) | SUSPECT-unconfirmed | whatItMeans substantially untranslated raw Indonesian |
| 52321 | Agen Penjualan Tiket Transportasi | PASS |  |
| 52329 | Jasa Intermediasi Transportasi Lainnya untuk Penumpang | SUSPECT-unconfirmed | whatItMeans substantially untranslated raw Indonesian |
| 53200 | Aktivitas Kurir | PASS |  |
| 55101 | Aktivitas Hotel Bintang Lima | PASS |  |
| 55102 | Aktivitas Hotel Bintang Empat | PASS |  |
| 55103 | Aktivitas Hotel Bintang Tiga | PASS |  |
| 55104 | Aktivitas Hotel Bintang Dua | PASS |  |
| 55105 | Aktivitas Hotel Bintang Satu | PASS |  |
| 55106 | Aktivitas Hotel Nonbintang | PASS |  |
| 55201 | Aktivitas Rumah Tinggal Sewa (Homestay) | PASS |  |
| 55202 | Aktivitas Hostel Remaja (Youth Hostel) | PASS |  |
| 55203 | Aktivitas Vila | PASS |  |
| 55204 | Aktivitas Apartemen Hotel | PASS |  |
| 55209 | Aktivitas Penyediaan Akomodasi Jangka Pendek Lainnya | PASS |  |
| 55300 | Aktivitas Penyediaan Bumi Perkemahan, Persinggahan Karavan, dan Taman Karavan | PASS |  |
| 55400 | Aktivitas Jasa Intermediasi Akomodasi | PASS |  |
| 55901 | Aktivitas Jasa Manajemen Akomodasi | PASS |  |
| 55909 | Penyediaan Akomodasi Lainnya YTDL | PASS |  |
| 56101 | Aktivitas Penyediaan Makanan di Bangunan Tetap | PASS |  |
| 56102 | Aktivitas Penyediaan Makanan di Bangunan Tidak Tetap | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 56210 | Aktivitas Jasa Boga untuk Acara Tertentu (Event Catering) | PASS |  |
| 56290 | Aktivitas Penyediaan Jasa Boga Lainnya | PASS |  |
| 56301 | Aktivitas Bar | PASS |  |
| 56302 | Aktivitas Kelab Malam atau Diskotek yang Utamanya Menyediakan Minuman | PASS |  |
| 56400 | Aktivitas Jasa Intermediasi Penyediaan Makanan dan Minuman | PASS |  |
| 58211 | Penerbitan Perangkat Lunak Video Gim dalam Jaringan (Game Online) | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 58219 | Penerbitan Perangkat Lunak Video Gim Lainnya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 58290 | Penerbitan Perangkat Lunak (Software) Lainnya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 59111 | Aktivitas Produksi Film, Video, dan Program Televisi oleh Pemerintah | PASS |  |
| 59112 | Aktivitas Produksi Film, Video, dan Program Televisi oleh Swasta | PASS |  |
| 59121 | Aktivitas Pascaproduksi Film, Video, dan Program Televisi oleh Pemerintah | PASS |  |
| 59122 | Aktivitas Pascaproduksi Film, Video, dan Program Televisi oleh Swasta | PASS |  |
| 59140 | Aktivitas Pemutaran Film | PASS |  |
| 59201 | Aktivitas Perekaman Suara | PASS |  |
| 59202 | Aktivitas Penerbitan Musik dan Buku Musik | PASS |  |
| 60103 | Aktivitas Distribusi dan Streaming Audio Atas Permintaan | PASS |  |
| 60203 | Aktivitas Distribusi dan Streaming Video Atas Permintaan | PASS |  |
| 60390 | Aktivitas Situs Jejaring Sosial dan Distribusi Konten Lainnya | PASS |  |
| 61104 | Aktivitas Jasa Akses Internet (Internet Service Provider) | PASS |  |
| 62110 | Pengembangan Video Gim, Perangkat Lunak Video Gim, dan Perangkat Lunak Pendukungnya | PASS |  |
| 62191 | Aktivitas Pengembangan Aplikasi Perdagangan melalui Internet (E-Commerce) | PASS |  |
| 62192 | Aktivitas Pengembangan Aplikasi dan Produksi Konten Berbasis Media Imersif | PASS |  |
| 62193 | Aktivitas Pengembangan Aplikasi Berbasis Teknologi Blockchain | PASS |  |
| 62194 | Aktivitas Pengembangan Komponen Dasar Kecerdasan Buatan | PASS |  |
| 62199 | Aktivitas Pemrograman Komputer Lainnya YTDL | PASS |  |
| 62201 | Aktivitas Konsultansi dan Manajemen Keamanan Siber | PASS |  |
| 62202 | Aktivitas Penyediaan dan Pengelolaan Identitas Digital | PASS |  |
| 62203 | Aktivitas Penyediaan Sertifikat Elektronik dan Jasa Terkait | PASS |  |
| 62204 | Aktivitas Konsultansi dan Perancangan Internet of Things (IoT) | PASS |  |
| 62209 | Aktivitas Konsultansi Komputer dan Manajemen Fasilitas Komputer Lainnya | PASS |  |
| 62900 | Aktivitas Jasa Teknologi Informasi dan Komputer Lainnya | PASS |  |
| 63101 | Aktivitas Pengolahan Data | PASS |  |
| 63102 | Aktivitas Penyediaan Infrastruktur Komputasi, Hosting, dan Aktivitas Terkait | PASS |  |
| 63900 | Aktivitas Jasa Portal Pencarian Web dan Informasi Lainnya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 64194 | Pembiayaan Mikro Syariah Nonperbankan | PASS |  |
| 64210 | Aktivitas Perusahaan Induk | PASS |  |
| 64921 | (orphan — not in auth dataset) | SUSPECT-unconfirmed | dead orphan key, not in 1559 auth dataset (pre-existing, page doesn't render it) |
| 64992 | Aktivitas Modal Ventura Syariah | PASS |  |
| 64995 | Perdagangan Unit Karbon atas Nama Sendiri | PASS |  |
| 65121 | Asuransi Umum Konvensional | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 66125 | Aktivitas Penukaran Valuta Asing (Money Changer) | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 66151 | Aktivitas Advisori Investasi | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 66199 | Aktivitas Penunjang Jasa Keuangan Lainnya YTDL, Kecuali Asuransi dan Dana Pensiun | PASS |  |
| 66301 | Manajemen Investasi Konvensional di Pasar Keuangan | PASS |  |
| 68111 | Aktivitas Pengembangan Bangunan dan Lahan Hunian | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 68112 | Aktivitas Penyewaan Bangunan dan Lahan Hunian Milik Sendiri atau Sewa | PASS |  |
| 68121 | Pengelolaan Kawasan Pariwisata | PASS |  |
| 68122 | Pengelolaan Kawasan Industri | PASS |  |
| 68123 | Pengelolaan Kawasan Ekonomi Khusus | PASS |  |
| 68124 | Penyewaan Tempat Penyelenggaraan Aktivitas Pertemuan, Perjalanan Insentif, Konvensi, dan Pameran, serta Acara Khusus | PASS |  |
| 68125 | Pengelolaan Pusat Perbelanjaan | PASS |  |
| 68126 | Penyewaan Gudang dan Fasilitas Penyimpanan Mandiri | PASS |  |
| 68127 | Pengelolaan Gedung Perkantoran | PASS |  |
| 68129 | Aktivitas Real Estat (Bangunan dan Lahan) Nonhunian Lainnya Milik Sendiri atau Sewa | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 68210 | Aktivitas Jasa Intermediasi Real Estat | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 68291 | Jasa Penaksir Real Estat | PASS |  |
| 68292 | Pengelolaan Real Estat Hunian Atas Dasar Balas Jasa (Fee) atau Kontrak | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 68299 | Aktivitas Real Estat Atas Dasar Balas Jasa (Fee) atau Kontrak Lainnya YTDL | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 69101 | Aktivitas Pengacara | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 69102 | Aktivitas Konsultan Hukum | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 69103 | Aktivitas Konsultan Kekayaan Intelektual | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 69104 | Aktivitas Notaris dan Pejabat Pembuat Akta Tanah | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 69201 | Aktivitas Akuntansi, Pembukuan, dan Pemeriksa | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 69202 | Aktivitas Konsultansi Pajak | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 70100 | Aktivitas Kantor Pusat | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 70201 | Aktivitas Konsultansi Manajemen dan Bisnis Pariwisata | PASS |  |
| 70202 | Aktivitas Konsultansi Manajemen dan Bisnis Industri | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 70203 | Aktivitas Konsultansi Manajemen dan Bisnis Perdagangan | PASS |  |
| 70209 | Aktivitas Konsultasi Manajemen dan Bisnis Lainnya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 71101 | Aktivitas Arsitektural | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 71102 | Aktivitas Perancangan dan Konsultansi Teknis Pabrik | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 71109 | Aktivitas Enjinering dan Konsultansi Teknis Terkait Lainnya | PASS |  |
| 72101 | Penelitian dan Pengembangan Ilmu Alam | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 72109 | Penelitian dan Pengembangan Eksperimental Ilmu Alam dan Enjinering Lainnya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 72201 | Penelitian dan Pengembangan Ilmu Pengetahuan Sosial | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 73100 | Aktivitas Periklanan | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 73201 | Penelitian Pasar | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 73202 | Jajak Pendapat Opini Publik | PASS |  |
| 73300 | Aktivitas Kehumasan | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 74112 | Aktivitas Desain Peralatan Rumah Tangga dan Furnitur | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 74113 | Aktivitas Desain Tekstil, Mode/Fesyen, dan Garmen | PASS |  |
| 74115 | Aktivitas Desain Alat Komunikasi dan Elektronika | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 74116 | Aktivitas Desain Peralatan Olahraga dan Permainan | PASS |  |
| 74117 | Aktivitas Desain Produk Kesehatan, Kosmetik, dan Perlengkapan Laboratorium | PASS |  |
| 74118 | Aktivitas Desain Pengemasan | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 74119 | Aktivitas Desain Industri Lainnya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 74191 | Aktivitas Desain Interior | PASS |  |
| 74192 | Aktivitas Desain Grafis/Komunikasi Visual | PASS |  |
| 74193 | Aktivitas Desain Khusus Film, Video, Program Televisi, Animasi dan Komik | PASS |  |
| 74194 | Aktivitas Desain Konten Gim | PASS |  |
| 74199 | Aktivitas Desain Khusus Lainya YTDL | PASS |  |
| 74201 | Aktivitas Fotografi Udara | PASS |  |
| 74209 | Aktivitas Fotografi Lainnya | PASS |  |
| 74300 | Aktivitas Penerjemah Atau Interpreter | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 74910 | Aktivitas Broker dan Layanan Pemasaran Paten | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 74999 | Semua Aktivitas Profesional, Ilmiah dan Teknis YTDL Lainnya | PASS |  |
| 75001 | Aktivitas Personel Kesehatan Hewan Mandiri | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 75002 | Aktivitas Pengelolaan Sarana Kesehatan Hewan | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 75009 | Aktivitas Pengelolaan Kesehatan Hewan Lainnya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 77100 | Penyewaan dan Sewa Guna Usaha Kendaraan Bermotor | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 77210 | Penyewaan dan Sewa Guna Usaha Alat rekreasi dan Olahraga | PASS |  |
| 77291 | Penyewaan Peralatan dan Perlengkapan Acara | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 77294 | Penyewaan Bunga dan Tanaman Hias | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 77299 | Penyewaan Barang Pribadi dan Barang Rumah Tangga Lainnya YTDL | PASS |  |
| 77311 | Penyewaan dan Sewa Guna Usaha Alat Transportasi Darat Bukan Kendaraan Bermotor | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 77312 | Penyewaan dan Sewa Guna Usaha Alat Transportasi Air | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 77313 | Penyewaan dan Sewa Guna Usaha Alat Transportasi Udara | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 77393 | Penyewaan dan Sewa Guna Usaha Mesin dan Peralatan Konstruksi dan Teknik Sipil | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 77400 | Sewa Guna Usaha Kekayaan Intelektual dan Produk Sejenis, Bukan Karya Berhak Cipta | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 77510 | Aktivitas Jasa Intermediasi untuk Penyewaan dan Sewa Guna Usaha Mobil | PASS |  |
| 77520 | Aktivitas Jasa Intermediasi untuk Penyewaan dan Sewa Guna Usaha Barang Berwujud dan Aset Tak Berwujud Nonfinansial Lainnya | PASS |  |
| 79110 | Aktivitas Agen Perjalanan | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 79121 | Aktivitas Biro Perjalanan Wisata | PASS |  |
| 79122 | Aktivitas Biro Perjalanan Ibadah Umrah dan Haji Khusus | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 79129 | Aktivitas Biro Perjalanan Lainnya | PASS |  |
| 79901 | Jasa Informasi Pariwisata | PASS |  |
| 79902 | Jasa Informasi Daya Tarik Wisata | PASS |  |
| 79903 | Jasa Pramuwisata | PASS |  |
| 79909 | Aktivitas Terkait Perjalanan Lainnya YTDL | PASS |  |
| 81300 | Aktivitas Jasa Lanskap | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 82100 | Aktivitas Administrasi Kantor dan Penunjang Kantor | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 82200 | Aktivitas Pusat Panggilan (Call Center) | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 82300 | Penyelenggaraan Konvensi dan Pameran Bisnis | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 82400 | Jasa Intermediasi untuk Aktivitas Penunjang Usaha YTDL Selain Intermediasi Finansial | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 82990 | Aktivitas Jasa Penunjang Usaha Lainnya YTDL | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 85102 | Pendidikan Taman Kanak-Kanak Umum Swasta | PASS |  |
| 85202 | Pendidikan Dasar Umum Swasta | PASS |  |
| 85300 | (orphan — not in auth dataset) | SUSPECT-unconfirmed | dead orphan key, not in 1559 auth dataset (pre-existing, page doesn't render it) |
| 85312 | Pendidikan Menengah Pertama Umum Swasta | PASS |  |
| 85316 | Pendidikan Menengah Atas Umum Swasta | PASS |  |
| 85330 | Pendidikan Pascamenengah Nontersier | SUSPECT-unconfirmed | whatItMeans substantially untranslated raw Indonesian |
| 85402 | Pendidikan Tinggi Umum Swasta | PASS |  |
| 85491 | (orphan — not in auth dataset) | SUSPECT-unconfirmed | dead orphan key, not in 1559 auth dataset (pre-existing, page doesn't render it) |
| 85499 | (orphan — not in auth dataset) | SUSPECT-unconfirmed | dead orphan key, not in 1559 auth dataset (pre-existing, page doesn't render it) |
| 85510 | Pendidikan Olahraga dan Rekreasi | PASS |  |
| 85520 | Pendidikan Kebudayaan | PASS |  |
| 85572 | Pelatihan Kerja Teknologi Informasi dan Komunikasi Swasta | PASS |  |
| 85573 | Pelatihan Kerja Industri Kreatif Swasta | PASS |  |
| 85574 | Pelatihan Kerja Pariwisata dan Perhotelan Swasta | PASS |  |
| 85575 | Pelatihan Kerja Bisnis dan Manajemen Swasta | PASS |  |
| 85579 | Pelatihan Kerja Swasta Lainnya | PASS |  |
| 85582 | Pelatihan Kerja Teknologi Informasi dan Komunikasi Perusahaan | PASS |  |
| 85583 | Pelatihan Kerja Industri Kreatif Perusahaan | PASS |  |
| 85584 | Pelatihan Kerja Pariwisata dan Perhotelan Perusahaan | PASS |  |
| 85585 | Pelatihan Kerja Bisnis dan Manajemen Perusahaan | PASS |  |
| 85592 | Pendidikan Komputer (Teknologi Informasi dan Komunikasi) Swasta | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 85593 | Pendidikan Bahasa Swasta | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 85595 | Pendidikan Bimbingan Belajar Dan Konseling Swasta | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 85600 | (orphan — not in auth dataset) | SUSPECT-unconfirmed | dead orphan key, not in 1559 auth dataset (pre-existing, page doesn't render it) |
| 85610 | Jasa Perantara Kursus dan Tutor | PASS |  |
| 86101 | Aktivitas Rumah Sakit Pemerintah | PASS |  |
| 86103 | Aktivitas Rumah Sakit Swasta | PASS |  |
| 86105 | Aktivitas Klinik Swasta | PASS |  |
| 86109 | Aktivitas Rumah Sakit Lainnya | PASS |  |
| 86202 | Aktivitas Praktik Dokter Spesialis | PASS |  |
| 86203 | Aktivitas Praktik Dokter Gigi | PASS |  |
| 86903 | (orphan — not in auth dataset) | SUSPECT-unconfirmed | dead orphan key, not in 1559 auth dataset (pre-existing, page doesn't render it) |
| 86910 | Aktivitas Jasa Intermediasi untuk Kesehatan Medis, Kedokteran Gigi, dan Pelayanan Kesehatan Manusia Lainnya | PASS |  |
| 86991 | Aktivitas Pelayanan Kesehatan yang Dilakukan oleh Tenaga Kesehatan Selain Dokter dan Dokter Gigi | PASS |  |
| 86992 | Aktivitas Pelayanan Kesehatan Tradisional | PASS |  |
| 86993 | Aktivitas Pelayanan Penunjang Kesehatan | PASS |  |
| 86995 | Aktivitas Rumah Pijat | PASS |  |
| 90112 | Aktivitas Penciptaan Komposisi Musik | PASS |  |
| 90120 | Aktivitas Penciptaan Karya Seni Rupa | PASS |  |
| 90130 | Aktivitas Penciptaan Karya Seni Lainnya | PASS |  |
| 90200 | Aktivitas Seni Pertunjukan | PASS |  |
| 90310 | Aktivitas Operasional Tempat dan Fasilitas Kesenian | PASS |  |
| 90391 | Penyelenggaraan Kegiatan Kesenian dan Kebudayaan | PASS |  |
| 91212 | Museum yang Dikelola Swasta | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 91221 | Aktivitas Situs Bersejarah dan Monumen yang Dikelola Pemerintah | PASS |  |
| 91222 | Aktivitas Situs Bersejarah dan Monumen yang Dikelola Swasta | PASS |  |
| 91300 | Konservasi, Restorasi, dan Aktivitas Penunjang Lainnya untuk Warisan Budaya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 91410 | Aktivitas Taman Botani dan Kebun Binatang | PASS |  |
| 91424 | Taman Wisata Alam | PASS |  |
| 91425 | Taman Hutan Raya | PASS |  |
| 91426 | Taman Laut | PASS |  |
| 93111 | Fasilitas Stadion | PASS |  |
| 93112 | Fasilitas Sirkuit | PASS |  |
| 93113 | Fasilitas Gelanggang/Arena | PASS |  |
| 93114 | Fasilitas Lapangan | PASS |  |
| 93115 | Fasilitas Olahraga Beladiri | PASS |  |
| 93116 | Fasilitas Pusat Kebugaran/Fitness Center | PASS |  |
| 93119 | Pengelolaan Fasilitas Olahraga Lainnya | PASS |  |
| 93122 | Klub Golf | PASS |  |
| 93123 | Klub Renang | PASS |  |
| 93124 | Klub Tenis Lapangan | PASS |  |
| 93127 | Klub Kebugaran/Fitness Dan Binaraga | PASS |  |
| 93129 | Klub Olahraga Lainnya | PASS |  |
| 93191 | Penyelenggaraan Kegiatan Olahraga | PASS |  |
| 93195 | Aktivitas Olahraga Tradisional | PASS |  |
| 93196 | Pengelolaan Fasilitas Pemancingan | PASS |  |
| 93199 | Aktivitas Lainnya yang Berkaitan dengan Olahraga YTDL | PASS |  |
| 93210 | Aktivitas Taman Bertema dan Taman Hiburan | PASS |  |
| 93291 | Aktivitas Lantai Dansa | PASS |  |
| 93292 | Pengelolaan Fasilitas Karaoke | PASS |  |
| 93293 | Pengelolaan Arena Permainan | PASS |  |
| 93294 | Wisata Gua, Pemandian, dan Petualangan Alam | PASS |  |
| 93295 | Wisata Pantai | PASS |  |
| 93296 | Wisata Agro | PASS |  |
| 93297 | Wisata Tirta | PASS |  |
| 93299 | Aktivitas Hiburan dan Rekreasi Lainnya YTDL | PASS |  |
| 95101 | Reparasi dan Pemeliharaan Komputer dan Peralatan Sejenisnya | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 95102 | Reparasi dan Pemeliharaan Peralatan Komunikasi | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 96100 | Aktivitas Pencucian dan Pembersihan Produk Tekstil dan Bulu | PASS |  |
| 96120 | (orphan — not in auth dataset) | SUSPECT-unconfirmed | dead orphan key, not in 1559 auth dataset (pre-existing, page doesn't render it) |
| 96130 | (orphan — not in auth dataset) | SUSPECT-unconfirmed | dead orphan key, not in 1559 auth dataset (pre-existing, page doesn't render it) |
| 96210 | Aktivitas Penataan dan Pangkas Rambut | SUSPECT-unconfirmed | youllAlsoNeed references phantom (non-2025) KBLI code(s) |
| 96220 | Aktivitas Perawatan Kecantikan dan Perawatan Kecantikan Lainnya | PASS |  |
| 96230 | Aktivitas Sante Par Aqua (SPA) Harian, Sauna, dan Pemandian Uap | PASS |  |
| 96300 | Aktivitas Pemakaman dan Kegiatan Terkait | PASS |  |
| 96400 | Aktivitas Jasa Intermediasi untuk Jasa Perorangan | PASS |  |
| 96900 | Aktivitas Jasa Perorangan Lainnya YTDL | PASS |  |
## Summary counts

| Verdict | Count | % of 428 |
|---|---|---|
| PASS | 248 | 58% |
| FIXED | 7 | 2% |
| SUSPECT-unconfirmed | 173 | 40% |

**Note (R1, gpt-5.5)**: the 173 row count above is a correct partition of 428 (248+7+173=428) under
this table's own first-matched-reason tagging — it is NOT wrong as a row count. What was wrong is
the narrative breakdown of that 173 in the paragraph below: the originally-reported component
counts (159 + 9 + 8 = 176) never summed to 173 in the first place, a plain arithmetic error
independent of any overlap, and the phantom-reference component itself was undercounted (see
correction above — true figure is 164 entries, not 159). See the corrected breakdown immediately
below for the reconciled accounting.

**SUSPECT breakdown — corrected (R1, gpt-5.5)**: the table's first-matched-reason tagging
(156 phantom-cross-reference, 9 untranslated-content, 8 dead-orphan-key = 173, the row count
above) undercounts the true phantom-reference problem, because an entry tagged
untranslated-content or dead-orphan-key first is never re-checked for phantom refs even when it
also has them. The independent full rerun in the Findings section above (every standalone
5-digit token in every entry's `youllAlsoNeed`, checked against the 1559-code authoritative set)
finds **164 entries** with at least one phantom reference — 8 more than the 156 the table
surfaces under that tag. The original prose figure of "159" in an earlier draft of this section
was itself wrong on both counts: it neither matched the table's own 156 nor the corrected 164.
6 of the 8 dead-orphan-key entries are additionally phantom-cross-reference entries in their own
right (see the dead-orphan finding above) — the categories are not disjoint, and "slight overlap
possible" undersold a confirmed, non-trivial overlap.

## What this certification does NOT cover (explicit residuals, same honesty standard as #2164)

- **`intel_2026` field content** for the ~420 non-fixed gold codes — masked by gold precedence
  on the live page but embedded into Qdrant search content. Same residual the #2164 audit
  already flagged; not re-closed here.
- **`tkaInfo.categoryId` correctness** independent of name, and whether `tkaInfo` should exist
  per-KBLI-code at all — explicitly Zero's open business decision per the #2164 report and the
  TKA README's own stated design constraint. This certification does not resolve it, only avoids
  making it worse.
- **Phantom-code replacement mapping** (which real 2025 code should each of the 83 stale
  references point to) — needs domain research, out of scope for a mechanical certification pass.

## Files touched

- `apps/mouth/data/kbli-gold-all.json` — 7 `tkaInfo` blocks deleted (23961, 23969, 16291, 16293,
  32111, 32112, 32120). 315 lines removed, 1 line context. No other field touched. Verified valid
  JSON post-edit, 428 entries preserved, `tkaInfo` type is `?: KBLITkaInfo` (optional) in
  `apps/mouth/src/lib/kbli-types.ts:283` — schema-safe removal, no consuming code assumes
  unconditional presence (`kbli-data.server.ts`/`kbli-gold-codes.ts` have zero direct `tkaInfo`
  references). `apps/mouth/src/lib/kbli-dataset-version.test.ts` only checksums
  `KBLI_2025_FINAL_CLEAN.json` (untouched by this PR) — no sidecar bump required.

## Adversarial review

- Seat: gpt-5.5 (Codex CLI, fresh context, read-only) — 2026-07-12
- (Earlier in-session devils-advocate subagent pass on the tkaInfo/phantom-reference
  candidate defects, referenced in Method step 9 and frontmatter history, predates and is
  superseded by this R1 gate seat for the frontmatter contract below.)
- Verdict as returned: REFUTED (4/5 claim blocks; core fix HOLDS)
- (a) "248 PASS / gold layer certified" — CONFIRMED overreach → reworded: PASS means
  not-flagged by heuristics covering 2 of 6 editorial fields (`whatItMeans`/`baliContext`), no
  anchor dictionary or reviewer transcript beyond the ad hoc ~65-term list exists; scope note
  added after the Method section.
- (b) "77 phantom codes across 159 entries" — CONFIRMED undercounted → corrected to 83 unique
  phantom codes across 164 entries (independent full rerun, every standalone 5-digit token in
  `youllAlsoNeed` vs. the 1559-code authoritative set; matches the refuter's own rerun exactly).
- (c) "8 dead orphans are benign" — CONFIRMED wrong → corrected: a reverse-reference scan shows
  6 of 8 (`85491, 85499, 85600, 86903, 96120, 96130`) are actively recommended by other entries'
  `youllAlsoNeed` (two closed loops of 3 dead codes recommending each other); only `64921` and
  `85300` have zero incoming references and are genuinely benign. Re-tagged SUSPECT-unconfirmed.
- (d) "173 SUSPECT = 159 + 9 + 8" — CONFIRMED arithmetic error → 159+9+8=176, not 173, independent
  of any overlap; the table's own first-matched-reason tagging (156+9+8=173) is a correct
  partition of 428, but the prose breakdown matched neither its own table nor the corrected
  phantom count. Reconciled in the Summary counts section with the confirmed 6-code overlap
  between the phantom-reference and dead-orphan sets.
- (e) "7 `tkaInfo` deletions" — HOLDS, no action: 146 tkaInfo blocks before, 139 after, diff is
  exactly 315 deletions + 1 addition. Core fix stands unchanged by this review.
