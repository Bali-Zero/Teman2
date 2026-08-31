---
date: 2026-08-24
domain: visa
client_case: none
adversarial_review: kimi-k3
sources:
  - https://peraturan.go.id/id/permenkumham-no-22-tahun-2023
  - https://peraturan.go.id/files/permenkumham-no-22-tahun-2023.pdf
  - https://peraturan.go.id/id/permenkumham-no-11-tahun-2024
  - https://peraturan.go.id/files/permenkumham-no-11-tahun-2024.pdf
  - https://peraturan.go.id/id/permenimipas-no-3-tahun-2025
  - https://peraturan.go.id/files/Permenpkp2-no-3-tahun-2025.pdf
  - https://peraturan.go.id/id/uu-no-6-tahun-2011
  - https://peraturan.go.id/id/uu-no-63-tahun-2024
  - https://peraturan.go.id/id/uu-no-61-tahun-2024
  - https://peraturan.go.id/id/pp-no-31-tahun-2013
  - https://peraturan.go.id/id/pp-no-26-tahun-2016
  - https://peraturan.go.id/id/pp-no-51-tahun-2020
  - https://peraturan.go.id/id/pp-no-48-tahun-2021
  - https://peraturan.go.id/id/pp-no-40-tahun-2023
  - https://peraturan.go.id/id/pp-no-45-tahun-2024
  - https://peraturan.go.id/id/perpres-no-157-tahun-2024
  - https://peraturan.go.id/id/perpres-no-95-tahun-2024
  - https://peraturan.go.id/id/perpres-no-21-tahun-2016
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E33C
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E33D
  - https://www.imigrasi.go.id/siaran_pers/ditjen-imigrasi-terapkan-kebijakan-terbaru-tentang-klasifikasi-visa
  - https://kemenimipas.go.id/attachments/2025/peraturan/20250813_09_Kepmen_No_M.IP-08.GR.01.01_Th_2025_Tentang_Klasifikasi_Visa.pdf
  - https://www.imigrasi.go.id/siaran_pers/tekan-angka-pelanggaran-keimigrasian-wna-wajib-ke-kantor-imigrasi-untuk-perpanjangan-izin-tinggal
  - https://www.imigrasi.go.id/siaran_pers/ditjen-imigrasi-perbarui-aturan-visa-kunjungan-untuk-calon-tka-dalam-uji-coba
  - https://www.imigrasi.go.id/siaran_pers/imigrasi-berikan-izin-tinggal-keadaan-terpaksa-dan-hapus-overstay-bagi-wna-terimbas-erupsi-gunung-lewotobi
  - https://kemenimipas.go.id/berita-utama/kemenimipas-menambah-enam-negara-penerima-bebas-visa-kunjungan-ke-indonesia
  - https://depok.imigrasi.go.id/direktorat-jenderal-imigrasi-berlakukan-bridging-visa/
---

# Indonesian Immigration Regulatory Timeline, 1 Jan 2023 – 24 Aug 2026

**Purpose**: authoritative yardstick to judge whether NotebookLM notebook NB-2 (72 sources) is stale. Built by direct primary-source fetch (peraturan.go.id status pages + raw PDF text extraction of the actual regulation text, not summaries) plus three parallel research passes for breadth. Every claim below is labeled **VERIFIED (primary)**, **VERIFIED (secondary-corroborated)**, **UNVERIFIED**, or **COULD NOT FIND**, per the task's anti-hallucination requirement — no fact is asserted without a URL fetched in this session (either by me directly, via `curl`+`pdftotext` raw extraction, or by a coordinated sub-agent's own tool calls within this same task).

**Method note on tooling**: `peraturan.bpk.go.id` returned HTTP 403 to every fetch attempt across all research threads — never independently reachable, always via WebSearch snippets only. `peraturan.go.id` (the national JDIH/Setneg portal) was reachable and is the primary source of record used throughout; its "Detail Status" panel exposes machine-readable `Berlaku`/`Tidak Berlaku`/`Diubah Oleh`/`Dicabut Oleh`/`Mencabut` relationship fields, and it hosts a direct PDF download for most instruments (`peraturan.go.id/files/<slug>.pdf`), which was downloaded and run through `pdftotext -layout` for word-for-word Pasal text — this is the technique used to resolve both settle-questions below. **A caution baked into the technique itself**: `WebFetch`'s AI-summarization layer produced one materially wrong-sounding read on this run (see §3) that only raw HTML/PDF extraction caught — treat any AI-summarized fetch as a lead to verify, not a citation in itself.

---

## 1. Chronological instrument table

Legend: **B**=Berlaku (in force) · **TB**=Tidak Berlaku (repealed/superseded) · V=VERIFIED primary (URL fetched, raw text/HTML read) · Vs=VERIFIED secondary-corroborated (official source located/cross-referenced but not independently raw-fetched by me) · U=UNVERIFIED (secondary only, conflicting or unconfirmed) · CNF=COULD NOT FIND.

| Date | Instrument | Title (short) | Status @ 2026-08-24 | Grade |
|---|---|---|---|---|
| 1992/2009 | UU 9/1992, UU 37/2009 | Prior Keimigrasian laws | **TB** — repealed by UU 6/2011 | V |
| 2011-05-05 | **UU 6/2011** | Keimigrasian (base law) | **B**, amended (see below) | V |
| 2013-04-16 | **PP 31/2013** | Peraturan Pelaksanaan UU 6/2011 | **B**, amended 4x | V |
| 2016-06-28 | PP 26/2016 | Perubahan (1st) atas PP 31/2013 | superseded-in-text by later amendments; instrument itself not shown repealed | V (existence/date/status page) |
| 2016-03-02 | Perpres 21/2016 | Bebas Visa Kunjungan | **TB** — revoked by Perpres 95/2024 | Vs |
| 2020-09-09 | PP 51/2020 | Perubahan Kedua atas PP 31/2013 | ditto | V |
| 2021-02-02 | PP 48/2021 | Perubahan Ketiga atas PP 31/2013 | ditto (superseded-in-text by PP 40/2023) | V |
| 2022 / 2023 | Perppu 2/2022 -> **UU 6/2023** | Cipta Kerja (omnibus) — amends UU 6/2011 | folded into UU 6/2011's current text | V (peraturan.go.id "Diubah Oleh" field) |
| 2023-08-04 | PP 40/2023 | Perubahan Keempat atas PP 31/2013 | **B** — current PP-31/2013 text | V |
| **2023-08-22** | **Permenkumham 22/2023** | **Visa dan Izin Tinggal — THE SPINE** | **B** (as amended — see Sec 2) | V |
| 2023 (~Sep-Oct) | Kepmenkumham M.HH-01.GR.01.04/2023 -> M.HH-02.GR.01.04/2023 | Klasifikasi Visa (index v1 -> v2) | superseded by M.IP-08.GR.01.01/2025 (Sec 1 below) | Vs |
| 2023-01-04 (several) | SE Dirjen Imigrasi IMI-0058/0018/0076/0133.GR.01.01/2023 | e-VOA rollout + VOA country-list additions (Kazakhstan; Panama/Guatemala/Macau) | superseded by later SE/Kepmen VOA-list revisions | mixed V/U — see Sec 4 |
| 2024-01-09 | Kepmenkumham M.HH-02.GR.01.06/2024 | VOA/BVK country-list revision (->97 countries incl. Mongolia) | superseded (see Sec 4 gaps — Panama status disputed) | Vs |
| **2024-04-01** | **Permenkumham 11/2024** | **Perubahan atas Permenkumham 22/2023** — deletes Pasal 60, launches Bridging Visa, restructures Pasal 33/39/40/59 etc. | Freestanding instrument tagged **"Tidak Berlaku"** by peraturan.go.id (see Sec 3 — this is a database-label nuance, not a wholesale revival of pre-2024 text) | V (raw PDF text read) |
| 2024-08-29 | Perpres 95/2024 | Bebas Visa Kunjungan (replaces Perpres 21/2016) | **B** | Vs |
| 2024-10-15 | UU 61/2024 | Amends UU 39/2008 Kementerian Negara — lifts 34-ministry cap, enables the split | **B** | V |
| 2024-10-17 | **UU 63/2024** | Perubahan Ketiga atas UU 6/2011 Keimigrasian — extends penangkalan (entry-ban) to 10y+10y | **B** | V |
| 2024-10-18 | **PP 45/2024** | Jenis & Tarif PNBP pada Kementerian Hukum dan HAM (incl. immigration/visa services) | **B** | V |
| 2024-10-21 | Perpres 139/2024 | Penataan Tugas Kementerian Kabinet Merah Putih | **B** | Vs |
| 2024-11-05 | Perpres 142/2024 | Kemenko Hukum, HAM, Imigrasi, Pemasyarakatan | **B** | Vs |
| 2024-11-05 | Perpres 155/2024 | Kementerian Hukum | **B** | Vs |
| 2024-11-05 | Perpres 156/2024 | Kementerian Hak Asasi Manusia | **B** | Vs |
| **2024-11-05** | **Perpres 157/2024** | **Kementerian Imigrasi dan Pemasyarakatan (Kemenimipas)** — ministry split | **B** | V |
| 2025-02-06/07 | **Permen Imipas 3/2025** | Visa, Izin Tinggal, Fasilitas, Pengawasan bagi Diaspora — repeals **only** Pasal 43,45,52,53,54,55 of 22/2023-as-amended; eff. 6 May 2025 | **B** | V (raw PDF text read — see Sec 3) |
| 2025-05-28 (eff. 29 May) | SE Dirjen Imigrasi IMI-417.GR.01.01/2025 | Reinstates mandatory in-person biometrics for ITAS/ITK extension | **B** | V |
| 2025-05-27 (eff. 14 Jun) | SE Dirjen Imigrasi IMI-453.GR.01.01/2025 | C18 visa: flat 90-day non-extendable, no repeat same-sponsor use | **B** | V |
| 2025-06-13 (PDF stamped 13 Aug) | **Kepmen Imipas M.IP-08.GR.01.01/2025** | Klasifikasi Visa v3 — 133->110 indices; E23 consolidation; new A1/C7C/E28F/E28G | **B** — current visa-index authority | V (press release); PDF itself not machine-readable |
| ~2025-06-21 | SE Dirjen Imigrasi IMI-568.GR.01.01/2025 | Force-majeure stay permit + Rp0 overstay waiver, Lewotobi eruption | event-scoped, spent | V |
| 2025-07-03 | Permenimipas 9/2025 | Adds Brazil, Turkey to Bebas Visa Kunjungan (BVK) list | superseded-in-part by 10/2025->10/2026 chain | Vs |
| 2025 (undated) | Permenimipas 10/2025 | Adds Peru/Brazil/Turkey to BVK | **TB** — revoked by Permenimipas 10/2026 | Vs |
| 2025-12-10 (eff. 16 Dec) | Permenimipas 13/2025 | Pelaksanaan Pencegahan dan Penangkalan (exit-ban/entry-ban procedure implementing UU 63/2024) | **B**, reportedly amended by Permenimipas 1/2026 (unverified) | Vs |
| 2026 (undated) | Permenimipas 1/2026 | Amendment to 13/2025 | status/content CNF | CNF |
| **2026-07-07** (eff. 9 Jul) | **Permenimipas 10/2026** | Revokes & replaces 10/2025; adds Turkey, Brazil, Peru, Kazakhstan, Macau SAR, Belarus to BVK | **B** — current BVK country-list authority | V |
| 2026-04-10 | SE Menteri Imipas 2/2026 | Internal WFH policy (NOT visa/stay-permit — noted for completeness only) | n/a | Vs |

---

## 2. Amendments to Permenkumham 22/2023 — Pasal by Pasal

Source: `peraturan.go.id/files/permenkumham-no-11-tahun-2024.pdf` (670KB, 49 pages), downloaded and extracted with `pdftotext -layout` in this session — full text read, not a summary. **Permenkumham 11/2024 (1 Apr 2024) is the ONLY instrument peraturan.go.id lists under 22/2023's own "Diubah Oleh" field** (22/2023's status page shows `Status: Berlaku`, `Diubah Oleh: Permenkumham 11/2024` — no other amending instrument named). Its own Menimbang recites: *"...serta untuk melaksanakan penyesuaian kebijakan Golden Visa, perlu mengubah Peraturan Menteri Hukum dan Hak Asasi Manusia Nomor 22 Tahun 2023..."* — the amendment's stated purpose explicitly includes a Golden Visa policy adjustment.

Pasal I of 11/2024 contains **40 numbered amendment points**, verified by direct grep of the extracted text:

| # | Pasal touched | Type | Substance (as read from the actual replacement text) |
|---|---|---|---|
| 1 | Pasal 1 | diubah | Definitions clause rewritten |
| 2 | Pasal 5A-5D (new) | disisipkan | New articles on Visa form (sticker vs electronic) and Vaucer Visa specs |
| 3 | Pasal 7 ayat (5) | diubah | — |
| 4 | Pasal 15 ayat (1) | diubah | — |
| 5 | Pasal 16 ayat (1) | diubah | — |
| 6 | Pasal 19 | diubah | — |
| 7 | Pasal 24 | diubah | — |
| 8 | Pasal 26 | diubah | — |
| 9 | Pasal 27 | diubah | — |
| 10 | **Pasal 33** | diubah | Visa-category enumeration rewritten. Structurally unchanged for huruf j ("rumah kedua" umbrella, 5 sub-items: 1. rumah kedua, 2. keahlian khusus, 3. **tokoh dunia**, 4. lansia, 5. remote worker) — **one substantive change**: senior/elderly age threshold in huruf j angka 4 lowered from **60 tahun** (original 22/2023 text) to **55 tahun** (11/2024 text). Also expands huruf e "penanaman modal asing" (foreign investment) sub-structure into detailed 2-year/5-year/10-year tiers with lettered sub-categories a)-d) — this is where the US$25M/US$50M figures relocate to (see Q2 below). |
| 11 | Pasal 38 | ditambah ayat (6) | — |
| 12 | **Pasal 39** | diubah | 5-year foreign-investment visa (Pasal 33(2)(e) angka 2). Ayat (2): solo investor establishing a company, min. **US$2,500,000**. Ayat (3): investor NOT establishing a company — govt bonds/listed shares/mutual funds min **US$350,000**. **Ayat (4): branch director/commissioner or parent-company representative — company must commit to invest at least US$25,000,000 within 90 days.** |
| 13 | **Pasal 40** | diubah | 10-year foreign-investment visa (Pasal 33(2)(e) angka 3). Ayat (2): solo investor establishing a company, min. **US$5,000,000**. Ayat (3): investor not establishing a company — bonds/shares/mutual funds min **US$700,000**, or apartment purchase min **US$1,000,000**. **Ayat (4): branch director/commissioner or representative — company must commit to invest at least US$50,000,000 within 90 days.** |
| 14 | Pasal 50 | diubah | — |
| 15 | (new, between 50-51) | disisipkan | 1 new pasal |
| 16 | **Pasal 59** | diubah (ayat 2 only) | "Tokoh dunia" (World Figure) visa **WITH sponsor** (Pasal 33(2)(j) angka 3). Amendment is a **cross-reference correction**: ayat (2)'s reference to "ayat (1) huruf d" corrected to "ayat (1) huruf e" (the original 2023 text mis-cited pasfoto's letter instead of "dokumen lain"'s letter) — substance of the application procedure (government-agency sponsorship) is otherwise **unchanged**. |
| **17** | **Pasal 60** | **DIHAPUS (deleted)** | Verbatim: **"17. Pasal 60 dihapus."** — no replacement text. This deleted "Tokoh Dunia" visa **WITHOUT sponsor**, whose ayat (2) had specified the "Jaminan Keimigrasian" guarantee as a company-establishment commitment of **>=US$25,000,000 for max. 5-year stay, or >=US$50,000,000 for max. 10-year stay** — see Q2 below for what happened to these figures. |
| 18 | Pasal 61 | diubah | Senior/elderly visa procedure — age threshold updated to match Pasal 33's new 55-year floor (see #10) |
| 19 | Pasal 62 | diubah | — |
| 20 | Pasal 65 | diubah | — |
| 21 | Pasal 80 | diubah | — |
| 22 | Pasal 85 | diubah | — |
| 23 | (new, between 86-87) | disisipkan | 1 new pasal |
| 24 | (new, between 94-95) | disisipkan | 2 new pasal |
| 25 | Pasal 95 | diubah | — |
| 26 | Pasal 97 | diubah | — |
| 27 | Pasal 101 | diubah | — |
| 28 | Pasal 105 | diubah | — |
| 29 | Pasal 120 | diubah | — |
| 30 | Pasal 129 | diubah | — |
| 31 | Pasal 138 | diubah | — |
| 32 | Pasal 141 | diubah | — |
| 33 | Pasal 142 | diubah | — |
| 34 | Pasal 143 | diubah | — |
| 35 | Pasal 167 | ditambah ayat | — |
| 36 | Pasal 173 | diubah | — |
| 37 | Pasal 176 | diubah | — |
| 38 | Pasal 186 | diubah | Golden Visa chapter (BAB V) — investment-activity sub-provision |
| 39 | Pasal 189 | diubah | Golden Visa chapter |
| 40 | Pasal 191 | diubah | Golden Visa chapter |

Points marked "—" were located and confirmed to exist (grep-verified line numbers in the extracted text) but their substantive replacement text was not read line-by-line in this pass — flagged as a lower-confidence item below rather than asserted.

### Golden Visa is defined in the ORIGINAL 22/2023 text, not introduced by 11/2024

Verbatim, from the original PDF (BAB V, Pasal 184, `pmk22_2023.txt` line 5943): *"Golden Visa merupakan pengelompokan terhadap Visa Tinggal terbatas, Izin Tinggal Terbatas, Izin Tinggal Tetap, dan Izin Masuk Kembali untuk jangka waktu tertentu."* Pasal 185(1) lists 4 activities grouped under "Golden Visa": (a) penanaman modal, (b) penyatuan keluarga, (c) repatriasi, (d) **rumah kedua** — for 5 or 10 years (Pasal 185(2)). Since "tokoh dunia" is a sub-item of "rumah kedua" (Pasal 33(2)(j) angka 3), the World Figure route is a Golden Visa product by construction, from August 2023 onward — the term did not first appear with 11/2024's Golden Visa "policy adjustment"; that amendment restructured details underneath a pre-existing chapter.

### Permenimipas 3/2025 (Diaspora) — the ONLY other amendment touching 22/2023's text

`peraturan.go.id/files/Permenpkp2-no-3-tahun-2025.pdf` (515KB, 33 pages), downloaded and extracted. Ketentuan Penutup, **Pasal 45**, verbatim: *"Pada saat Peraturan Menteri ini mulai berlaku, ketentuan **Pasal 43, Pasal 45, Pasal 52, Pasal 53, Pasal 54, dan Pasal 55** Peraturan Menteri Hukum dan Hak Asasi Manusia Nomor 22 Tahun 2023 tentang Visa dan Izin Tinggal ... sebagaimana telah diubah dengan Peraturan Menteri Hukum dan Hak Asasi Manusia Nomor 11 Tahun 2024 ... **dicabut dan dinyatakan tidak berlaku**."* I cross-checked what those six Pasal covered in the original 22/2023 text: **Pasal 43 and 45 = family-reunification visa procedures (spouse/child of an Indonesian citizen); Pasal 52 = ex-Indonesian-citizen ("repatriasi") visa without sponsor** (all confirmed by direct text read, `pmk22_2023.txt` lines 1670-2050). These are exactly the population Permenimipas 3/2025's own Diaspora regime absorbs and replaces (former WNI + descendants + related family) — **confirms the repeal is scoped and targeted, not a blanket revocation.**

**Load-bearing correction of a database-label artifact** (flagged per the task's anti-hallucination instructions, because it is exactly the "confident-but-wrong from a status flag" trap the mandate warns about): `peraturan.go.id`'s own status page for the **freestanding** Permenkumham 11/2024 document reads `Status: Tidak Berlaku`, `Dicabut Oleh: Permen Imipas 3/2025` — read naively, this looks like "11/2024 is entirely gone." But 3/2025's own Pasal 45 (read above, primary text) repeals only 6 named Pasal of the **consolidated** 22/2023-as-amended text — not Pasal 60 (already separately deleted by 11/2024 itself), not Pasal 33/39/40/59/61 etc. The most coherent reading, consistent with both primary texts: the JDIH database tags the entire freestanding "Perubahan" instrument as spent/superseded once ANY of what it touched is later re-legislated elsewhere, even though the *rest* of its amendments remain merged into 22/2023's operative text (which peraturan.go.id's OWN 22/2023 page independently confirms is still `Berlaku`, listing 11/2024 as its sole amending instrument, with no reversion noted). **I could not find a case-law or JDIH-methodology document explaining this labeling convention explicitly** — this is my best-supported reading from the two primary texts, not a certainty; flagged in Sec 6.

---

## 3. Settled Question 1 — Which Pasal governs each E33 sub-product, and is E33C or E33D "World Figure"?

**Governing primary-law Pasal (Permenkumham 22/2023, as it now reads):**
- **Pasal 33 ayat (2) huruf j angka 3** defines "tokoh dunia" (World Figure) as one of 5 sub-categories under the "rumah kedua" (Second Home) umbrella.
- **Pasal 59** (amended by 11/2024, cross-reference fix only — substance unchanged): World Figure application **WITH a Penjamin/sponsor** — sponsorship documentation from a central-government agency (`instansi pemerintah pusat`).
- **Pasal 60** (ORIGINAL text, before deletion): World Figure application **WITHOUT a sponsor**, guaranteed instead by "Jaminan Keimigrasian" = a commitment to establish a company in Indonesia with investment >=US$25,000,000 (5-yr stay) or >=US$50,000,000 (10-yr stay). **Deleted outright by Permenkumham 11/2024, point 17: "Pasal 60 dihapus."**

**Official Ditjen Imigrasi product index (fetched by a coordinated sub-agent this session, triangulated 3 ways — individual E33C page, individual E33D page, and the master `daftar-visa-indonesia` index, all agreeing):**
- `https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E33C` — verbatim title: **"Visa Rumah Kedua Tokoh Dunia Undangan Pemerintah Golden Visa"** (Second Home Visa, World Figure, **Government Invitation**, Golden Visa).
- `https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E33D` — verbatim title: **"Visa Rumah Kedua Tokoh Dunia Pendirian Perusahaan"** (Second Home Visa, World Figure, **Company Establishment**).

**Resolution**: **Both E33C and E33D are "Tokoh Dunia" (World Figure) — they are not a world-figure/business-establishment binary, they are the two guarantee-route sub-pathways of the SAME World Figure category**, mapping cleanly onto the two primary-law articles:
- **E33C = Pasal 59** (government-invitation / sponsor route)
- **E33D = Pasal 60** (company-establishment route — **now a deleted article**, see below)

Against the two internal Bali Zero framings named in the task:
- *"E33D = World Figure"* — **directionally correct** but incomplete: E33C is equally "Tokoh Dunia" by its own official title.
- *"E33C = Second Home via business establishment"* — **incorrect against the primary index**. E33C's title says "Undangan Pemerintah" (government invitation), not company establishment. The **business-establishment route is E33D**, not E33C.
- The competing claim that *"E33C = the world-figure route"* is **also correct** (both are), but equally incomplete on its own if it implies E33D is not.

**The PRIMARY LAW supports**: neither internal framing is precise: **World Figure = the Pasal 33(2)(j) angka 3 category as a whole, split into E33C (Pasal 59, government invitation) and E33D (Pasal 60, company establishment)** — with E33D's own enabling article now void (see Q2). This is the correct way to state the product line, not a pick between the two competing internal claims.

**Corroborating gap that fits this resolution**: the sub-agent that fetched the live Ditjen index reports **E33D's detail page currently returns "Data Belum Tersedia" (data not yet available)** — no requirements/fee text is published for it, unlike every other E33 sub-code. This is consistent with E33D's enabling Pasal (60) having been deleted with no replacement: the code still exists in the Kepmen classification index (`M.IP-08.GR.01.01/2025`, confirmed live with E33D as a listed code), but Permenkumham 22/2023 — the substantive law the index implements — no longer contains an operative procedure article for it. **This is itself a "what a corpus should flag" finding**: E33D is a live catalog code with no live governing Pasal, a genuine index/law mismatch, not a research gap on my part.

---

## 4. Settled Question 2 — Does the US$25M / US$50M threshold survive anywhere in the current text?

**Short answer: the exact figures survive verbatim in the current consolidated text of Permenkumham 22/2023 — but NOT for any Second Home / World Figure (E33) route, and NOT under Pasal 60. Pasal 60 itself is gone with no replacement.**

Confirmed by direct text search of the amended articles (`pmk11_2024.txt`, `grep -n "25.000.000\|50.000.000"`):

- **Pasal 39 ayat (4)** (5-year **Penanaman Modal Asing** / Foreign Investment visa, Pasal 33(2)(e) angka 2 — a *completely different* visa category from Second Home/World Figure): for a foreign national who will serve as branch director/commissioner, or as a parent-company representative, the **company** must commit to invest **at least US$25,000,000** within 90 days of the Izin Tinggal Terbatas being granted. Verbatim: *"...berupa pernyataan komitmen dari perusahaan akan mendirikan cabang atau anak perusahaan di Indonesia dengan nilai investasi paling sedikit US\$25.000.000 (dua puluh lima juta dolar Amerika) yang harus dipenuhi dalam jangka waktu paling lama 90 (sembilan puluh) Hari..."*
- **Pasal 40 ayat (4)** (10-year Foreign Investment visa, Pasal 33(2)(e) angka 3): same structure, **at least US$50,000,000**. Verbatim: *"...berupa pernyataan komitmen dari perusahaan akan mendirikan cabang atau anak perusahaan di Indonesia dalam bentuk modal ditempatkan (saham) atau nilai investasi paling sedikit US\$50.000.000 (lima puluh juta dolar Amerika)..."*

**These are the SAME dollar figures the deleted Pasal 60 used** (US$25M/5-yr, US$50M/10-yr) — the 11/2024 amendment did not simply delete a threshold, it **relocated the number from the World-Figure-without-sponsor route (old Pasal 60) to the branch-director/representative sub-category of the ordinary Foreign Investment visa (new Pasal 39(4)/40(4))**. This is a materially different legal basis: Pasal 39/40's guarantee is a *company's* investment commitment tied to installing a branch officer, not an individual applying for World Figure status.

**Confirmed no revival**: Permenimipas 3/2025's Pasal 45 closing clause (read in full, Sec 2 above) repeals only Pasal 43/45/52-55 — Pasal 60 is not on that list, so its earlier deletion by 11/2024 stands undisturbed; no later instrument found in this research reinstates it. I searched specifically for any inserted "Pasal 60A" or equivalent in 11/2024's own amendment list (the only nearby insertion point found is between Pasal 50 and 51, unrelated) and found none.

**Answer to the question as posed**: **No** — a US$25M/US$50M threshold is **not** currently in force for any Second Home / World Figure route. It is in force, verbatim, for the **ordinary Foreign Investment visa's branch-director/commissioner/representative sub-category** (Pasal 39 ayat (4) for the 5-year track, Pasal 40 ayat (4) for the 10-year track) — a different visa product from E33. The figure's "true home" in the original 2023 text WAS the now-repealed Pasal 60 (World Figure without sponsor), exactly as suspected in the task brief; it did not simply vanish, it moved to a different Pasal governing a different visa category.

---

## 5. What a 2025-era corpus would be missing

Instruments issued from **mid-2025 onward** — anything built before roughly June-July 2025, or indexed only under "Permenkumham"/"Kemenkumham"/old Kepmen prefixes, will miss all of these:

1. **Permen Imipas 3/2025** (eff. 6 May 2025) — Diaspora visa/stay-permit regime; partially repeals Permenkumham 22/2023 (Pasal 43/45/52-55).
2. **SE Dirjen Imigrasi IMI-417.GR.01.01/2025** (eff. 29 May 2025) — mandatory in-person biometrics reinstated for ITAS/ITK extension; agent-only processing no longer sufficient.
3. **SE Dirjen Imigrasi IMI-453.GR.01.01/2025** (eff. 14 Jun 2025) — C18 visa flattened to 90 days non-extendable, no repeat use with same sponsor.
4. **Kepmen Imipas M.IP-08.GR.01.01/2025** (~13 Jun 2025) — **the current visa classification/index**, 133->110 codes, 31 work-visa types collapsed into 6 (with 20 skilled-worker indices E23B-E23W merged into a single E23), new A1/C7C/E28F/E28G codes. **Any content still describing the old 133-index table, or old E23 sub-letter codes individually, is obsolete.**
5. **SE Dirjen Imigrasi IMI-568.GR.01.01/2025** (~Jun 2025) — event-scoped force-majeure/overstay-waiver precedent (Lewotobi eruption) — useful as a template for how such waivers are structured, though itself spent.
6. **Permenimipas 9/2025** (eff. 3 Jul 2025) and **10/2025** — Bebas Visa Kunjungan (fully visa-free, distinct from VOA) list additions: Brazil, Turkey, Peru.
7. **Permenimipas 13/2025** (eff. 16 Dec 2025) — implements UU 63/2024's extended entry-ban/exit-ban (Pencegahan/Penangkalan) regime with a new emergency at-checkpoint exit-ban procedure. Reportedly amended by **Permenimipas 1/2026** (content not independently verified — see gaps).
8. **Permenimipas 10/2026** (eff. 9 Jul 2026) — **current** Bebas Visa Kunjungan country list: revokes 10/2025, adds Turkey/Brazil/Peru/Kazakhstan/Macau SAR/Belarus. Any BVK country list dated before July 2026 is stale.
9. **The letterhead/numbering shift itself**: post-5 Nov 2024, Peraturan Menteri-level instruments are issued as **"Peraturan Menteri Imigrasi dan Pemasyarakatan" (Permen Imipas / Permenimipas)**, and Keputusan Menteri-level instruments switched prefix from **"M.HH-"** to **"M.IP-"**. Surat Edaran Dirjen Imigrasi kept the same "IMI-XXX.GR.01.01" numbering series, only the letterhead changed. **A corpus that only searches "Permenkumham" or "M.HH-" will silently miss everything from #1-8 above.**
10. A parallel finding worth flagging even though it isn't a single instrument: **VOA-specific (pay-on-arrival) country-list activity appears to have gone quiet after the January 2024 Kepmenkumham M.HH-02.GR.01.06/2024 revision**, while **Bebas Visa Kunjungan (fully visa-free) list activity accelerated sharply from mid-2025 onward** (items #6, #8) — a policy-tool shift a stale corpus indexed only under "VOA" would not surface.

---

## 6. Could not verify / explicit gaps

- **Exact effective/enactment date for Kepmenkumham M.HH-02.GR.01.04/2023** (the visa-classification decree cited as introducing the Second Home/E33 index) — secondary sources gave "22 Oktober 2023" and a conflicting "effective 9 Jan 2024" claim; the PDF itself served only a metadata/title page via WebFetch, not extractable body text. Treat the exact date as unconfirmed.
- **Exact date of Kepmen M.IP-08.GR.01.01/2025** — the Ditjen press release does not state the underlying Kepmen's own "ditetapkan" date; the PDF filename on kemenimipas.go.id is stamped "20250813" (13 Aug 2025), while the press release's own framing implies a June 2025 rollout. I could not resolve this discrepancy — the PDF itself is a scanned/image file, not machine-readable via the tools used in this session.
- **Whether Kepmen M.IP-08.GR.01.01/2025 itself touches the E33 series** — its press release makes no explicit mention of E33/Second Home/Golden Visa by name; my E33 findings rest entirely on the LIVE Ditjen product index (imigrasi.go.id), not on this Kepmen's own text, which I could not read.
- **Panama's status in Kepmenkumham M.HH-02.GR.01.06/2024** (Jan 2024 VOA-list revision) — two secondary sources directly conflict (added vs. removed); no primary text of that decree was reached.
- **Permenimipas 1/2026** (reported amendment to Permenimipas 13/2025, the entry-ban/exit-ban procedure regulation) — existence reported by one secondary source only (paralegal.id); content, date, and scope not independently verified.
- **E33D's substantive requirements** (deposit/investment figures, processing steps) — the live Ditjen page returns "Data Belum Tersedia." I can state its title and its enabling-Pasal history (Pasal 60, deleted) with confidence, but cannot quote a current verbatim requirement text for it because none is published.
- **First/second amendment identity for UU 6/2011** — peraturan.go.id's own "Diubah Oleh" field for UU 6/2011 lists only two entries (Perppu 2/2022->UU 6/2023 Cipta Kerja, and UU 63/2024 "Perubahan Ketiga"/Third Amendment) — meaning the Cipta Kerja omnibus route apparently counts as covering the "first" and/or "second" amendment through its own multi-stage history (original UU 11/2020 -> constitutional-court conditional-unconstitutional ruling -> Perppu 2/2022 -> ratified as UU 6/2023). I did not trace that separate constitutional history in this session; flagging rather than asserting a specific 1st/2nd split.
- **Points #3-9, #11, #14, #18-40 of Permenkumham 11/2024's amendment list** (Sec 2 table) — I confirmed each of these amendment points EXISTS and located their line numbers via grep on the extracted PDF text, but did not read each one's full substantive replacement text line-by-line (only Pasal 33, 39, 40, 59, 60, 61, 184-186 were read in full, being the ones load-bearing for the two settle-questions and the Golden Visa framing). Treat the "—" cells in Sec 2's table as "existence-confirmed, substance-unread," not as "no change."
- **The JDIH "Tidak Berlaku" labeling convention** for a partially-repealed freestanding amending instrument (Sec 2, the 11/2024 status-flag discrepancy) — I could not find an explicit BPHN/JDIH methodology document explaining why the whole document is flagged "Tidak Berlaku" when only 6 of its ~40 amendment points were later touched; my reading is the best-supported inference from the two primary texts (11/2024's own content + 3/2025's own Pasal 45), not a confirmed convention.
- **peraturan.bpk.go.id** — never independently reachable (HTTP 403 on every attempt across all research threads in this session); every fact that might have used it as sole source was either re-sourced to peraturan.go.id or flagged as secondary.

---

## 7. Sources actually fetched in this session

Primary (raw HTML `Detail Status` panel and/or raw PDF text extracted via `pdftotext -layout`):
- `peraturan.go.id/id/{permenkumham-no-22-tahun-2023, permenkumham-no-11-tahun-2024, permenimipas-no-3-tahun-2025, uu-no-6-tahun-2011, uu-no-63-tahun-2024, uu-no-61-tahun-2024, pp-no-31-tahun-2013, pp-no-26-tahun-2016, pp-no-51-tahun-2020, pp-no-48-tahun-2021, pp-no-40-tahun-2023, pp-no-45-tahun-2024, perpres-no-157-tahun-2024}`
- `peraturan.go.id/files/{permenkumham-no-22-tahun-2023.pdf, permenkumham-no-11-tahun-2024.pdf, Permenpkp2-no-3-tahun-2025.pdf}` — full text extracted and grep/read line-by-line.

Primary (fetched by coordinated sub-agents within this same research task, each reporting VERIFIED/UNVERIFIED grading with URLs, per the task's method instructions):
- `imigrasi.go.id/wna/daftar-visa-indonesia` + individual `/E33`, `/E33A`-`/E33G` pages; `imigrasi.go.id/siaran_pers/*` (multiple 2025 press releases); `kemenimipas.go.id/berita-utama/*`; `depok.imigrasi.go.id`; `jogja.imigrasi.go.id`; `peraturan.go.id/id/{perpres-no-95-tahun-2024, perpres-no-21-tahun-2016, perpres-no-139/142/155/156-tahun-2024}`.

Secondary (used only to locate instrument numbers/dates, then labeled UNVERIFIED where a primary re-check was not achieved): hukumonline.com (mostly paywalled/403), paralegal.id, meridianhukum.com, regulasip.id (404 on the specific page attempted), setkab.go.id, kompas.com, infopublik.id, LMI Consultancy (visa-agent blog).

---

## Adversarial review

**Reviewer**: Kimi K3 (`kimi -m kimi-code/k3`), acting as hostile fact-checker, followed by independent human-session re-verification of Kimi's own claims (per the repo's generator≠grader R1 gate — this document's author never gates its own diff).

**Method**: Kimi re-downloaded the primary PDFs from peraturan.go.id itself, ran its own `pdftotext` extraction, grepped for every dollar figure and Pasal cross-reference, and cross-checked ~25 dated claims against independent secondary sources (Setkab, CNN Indonesia, Hukumonline, paralegal.id, pajakku, Antara). The reviewing session then independently re-verified Kimi's three flagged "errors" via direct web search/fetch against peraturan.go.id and BPK, because Kimi's own memory-based reasoning (visible in its transcript) is not itself a primary source and produced at least one false positive.

**Substantive scholarship — confirmed accurate.** Every Pasal-level claim that carries legal weight for a Bali Zero visa product was independently re-derived by Kimi from the raw PDF text and matched the document verbatim: the "Pasal 60 dihapus" deletion, the 60→55 lansia age change, the Pasal 59 huruf-d→e cross-reference fix, the original Pasal 60 US$25M/US$50M figures and their relocation to Pasal 39(4)/40(4), all US$ figures in Pasal 39/40, the Pasal 184/185 Golden Visa definition, the Permenimipas 3/2025 Pasal 45 repeal list (Pasal 43/45/52-55) and what those repealed articles covered, and the E33C/E33D title/Pasal mapping (independently corroborated against this repo's own `data/kb_sources/visa_imigrasi_list.txt`). Kimi also initially suspected "UU 37/2009" was a hallucinated citation, searched for it, and confirmed it is real (ratification of Perppu 3/2009 amending UU 9/1992) — a genuine near-miss the reviewing session re-checked and agrees is not an error.

**One flagged "error" is a false positive — corrected here.** Kimi's report claimed the document's "eff. 6 May 2025" for Permenimipas 3/2025 (§1 table, §5 item 1) was wrong and should be "7 May 2025," based on Hukumonline's summary sentence. Independent re-verification against `peraturan.go.id/id/permenimipas-no-3-tahun-2025` directly (fetched in this review) shows: ditetapkan 7 Feb 2025, **diundangkan 7 March 2025**. Pasal 46 sets the effective date at 60 days after promulgation. 7 March + 60 days = **6 May 2025** — exactly what the document says. Kimi's own arithmetic used an assumed diundangkan date (~8 March) rather than the actual one and arrived at the wrong day. The document's date stands as correct; Kimi's finding is discarded.

**One flagged date discrepancy is confirmed real but immaterial.** PP 51/2020 (Perubahan Kedua atas PP 31/2013): the document gives "2020-09-09"; independent web verification (corroborating Kimi) shows it was ditetapkan **10 September 2020**, diundangkan 11 September 2020 — a one-to-two-day metadata slip with no effect on any legal conclusion in the document (PP 51/2020's substance is not itself load-bearing for any of the document's two settled questions).

**One flagged discrepancy is not an error, just an undisclosed date-convention choice.** PP 26/2016: the document's "2016-06-28" is not the ditetapkan date (27 June 2016, per Setkab) but matches the diundangkan/effective date (28 June 2016) exactly. The document is internally inconsistent about which convention (ditetapkan vs. diundangkan) it uses per row, but 28 June 2016 is a genuine, correct date for the instrument — not a fabrication.

**Confirmed internal-consistency defect (verified directly against the document's own table, no external source needed): the "Chronological instrument table" is not fully chronological.** Four ordering violations: PP 26/2016 (28 Jun 2016 row) appears before Perpres 21/2016 (2 Mar 2016 row); the 2023-01-04 SE e-VOA row appears after the 2023-08-22 and "~Sep-Oct 2023" rows; the 2025-05-28 row (IMI-417) appears before the 2025-05-27 row (IMI-453); and the 2026-07-07 row (Permenimipas 10/2026) appears before the 2026-04-10 row (SE Menteri 2/2026). None of these affect the document's substantive conclusions (Sec 3/4 settled questions), but a document whose stated purpose is to be a staleness "yardstick" should sort its own table.

**Kimi also surfaced, without asserting as errors:** (a) a possible drafting defect inside Permenkumham 11/2024 itself — Pasal 40(4) huruf b cross-references "Pasal 33(2)(e) angka 2 butir d)" where angka 3 appears to be intended (a regulatory drafting error, not a defect in this document, which quotes the Pasal's substance correctly); (b) coverage gaps for a self-declared "authoritative yardstick" — Permenimipas 2/2025 (Pengawasan/TAK) and Permenimipas 5/2025 (repeal of Permenkumham 36/2021 Penjamin Keimigrasian) are not mentioned, though neither contradicts anything the document does assert.

**Verdict: PASS.** No material factual or legal error was found in the document's substantive claims (Pasal citations, dollar figures, repeal chains, E33 product mapping — the parts a Bali Zero visa consultant would actually rely on). Two peripheral date-metadata issues were found: one is a genuine minor slip (PP 51/2020, immaterial), one is a Kimi false positive that the document actually got right (Permenimipas 3/2025 effective date), and a third is a convention-labeling gap rather than a factual error (PP 26/2016). The chronological table's internal ordering has four cosmetic sort bugs. None of these change the document's stated purpose or its two settled questions about E33C/E33D and the US$25M/50M threshold's fate.
