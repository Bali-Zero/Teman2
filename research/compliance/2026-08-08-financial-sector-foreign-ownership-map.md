---
date: 2026-08-08
domain: compliance
client_case: "KBLI navigator financial-sector cluster (102 codes, 64-66) — foreign-ownership caps from primary instruments"
adversarial_review: codex
sources:
  - "UU 40/2014 (Perasuransian) — peraturan.bpk.go.id Download endpoint"
  - "PP 14/2018 (Kepemilikan Asing pada Perusahaan Perasuransian) — peraturan.bpk.go.id Download endpoint"
  - "PP 3/2020 — investigated, NOT relied on: a first-pass claim that it 'allows new cases >80%' was REJECTED because it contradicts the held PP 14/2018 Pasal 6 verbatim; kept in the source list only as the record of a rejected hypothesis"
  - "UU 1/2016 (Penjaminan) — peraturan.bpk.go.id Download endpoint"
  - "UU 4/2023 (P2SK) — peraturan.go.id, full 819pp text (Bab-by-Bab grep, incl. Lampiran)"
  - "PP 31/2022 (Perusahaan Efek) — peraturan.bpk.go.id Download endpoint, full PDF read (LN 2022/179, TLN 6816)"
  - "PP 29/1999 (Pembelian Saham Bank Umum) — peraturan.bpk.go.id Download endpoint, Download ID 43683 (ID 54286 serves a wrong cached PDF — see Method receipts)"
  - "POJK 12/2021 (Bank Umum) — ojk.go.id"
  - "POJK 56/2016 (Kepemilikan Saham Bank Umum) — ojk.go.id, still in force"
  - "POJK 7/2024 (BPR/BPRS) — ojk.go.id, Bab III Pasal 28-47 read in full"
  - "UU 1/2013 (LKM) — peraturan.bpk.go.id Download endpoint"
  - "POJK 41/2024 (LKM) — ojk.go.id, 185pp fetched"
  - "POJK 46/2024 (Perusahaan Pembiayaan) — ojk.go.id"
  - "POJK 35/2025 (amends POJK 46/2024, POJK 46/2020 Infrastruktur, PMV) — ojk.go.id, effective 22-12-2025"
  - "POJK 40/2024 (LPBBTI/P2P, revokes POJK 10/2022) — ojk.go.id"
  - "POJK 39/2024 (Pergadaian) — ojk.go.id"
  - "POJK 29/2025 (amends POJK 39/2024) — peraturan.bpk.go.id Download/410985, full 52pp grepped"
  - "PBI 18/20/PBI/2016 (KUPVA Bukan Bank / money changer) — bi.go.id direct fetch"
  - "PBI 23/6/PBI/2021 (Penyelenggara Jasa Pembayaran) — bi.go.id"
  - "PBI 23/7/PBI/2021 (Penyelenggara Infrastruktur Pasar) — bi.go.id"
  - "POJK 27/2024 (Perdagangan Aset Keuangan Digital termasuk Aset Kripto) — ojk.go.id"
  - "UU 8/1995 (Pasar Modal) — peraturan.bpk.go.id Download endpoint"
  - "PP 49/2014 (Penyelenggaraan Perdagangan Berjangka Komoditi) — peraturan.bpk.go.id Download endpoint, Bab IV Pasal 45-52 read"
  - "Perpres 10/2021 (Bidang Usaha Penanaman Modal) Pasal 11(2) — peraturan.bpk.go.id Download/154474, OCR'd text dump (scratchpad/perpres10-2021-pt.txt); see Method receipts for OCR caveat"
---

# Financial-sector foreign-ownership map — KBLI 64-66 (102 codes)

Consolidated capture of a same-day, four-lane primary-source research pass on
foreign-ownership caps across the financial-services KBLI cluster (banking,
financing/pembiayaan, capital markets/payments, penjaminan/insurance/pensions).
This file is faithful to the four gate scratchpad files it consolidates — their
orchestrator-level verdicts, corrections, and one retraction are preserved
exactly. Where a gate file states a claim with a hedge (MEDIUM confidence,
"believed", "not re-verified"), this file keeps the same hedge. **No claim below
is stated more strongly than its source gate file states it.** One additional,
**fifth** source sits outside that four-gate chain: Perpres 10/2021 Pasal 11(2)
(the finance/banking sectoral carve-out), fetched and read directly from a raw
OCR text dump, not gated by any of the four research lanes. It is flagged as
such wherever it appears — see Method receipts for its own, separate
verification caveat — and its own hedge (single-pass OCR, not independently
re-verified) is likewise never stated more strongly than warranted.

Two research generations are folded together per lane: a first pass (mixed
primary/secondary/triangulated) and a same-day second pass that upgraded nearly
everything to PRIMARY-VERBATIM by re-fetching and grepping full instrument
text. Where the two passes conflict, the second pass supersedes — this is
marked explicitly in the source gate files and preserved here.

## Per-family map

### Banking

- **64121/64122 — Bank Umum: 99% of modal disetor.** PRIMARY-VERBATIM: POJK
  12/2021 Pasal 13(2) — "paling banyak 99% ... dari modal disetor Bank BHI"
  (kemitraan form). **Plus** PP 29/1999 Pasal 3/4 (99% purchase ceiling
  via-bursa mechanics, ≥1% stays domestic) — first pass held this only as
  triangulated/strong (an OJK-reviewed IPO prospectus quoting the pasal,
  after 5 failed raw-fetch attempts); the second pass upgraded it to
  **PRIMARY-VERBATIM** once the correct Download ID (43683) was found — see
  Method receipts — with Pasal 3 verbatim on the 99% ceiling, Pasal 4(1)-(3)
  listing mechanics, and the Penjelasan self-declaring the PP as the UU
  10/1998 kemitraan elaboration.
  **Plus category caps**, POJK 56/2016 PRIMARY (still in force, not in POJK
  12/2021's revocation list): 40% financial-institution / 30% non-financial
  corporate / 20% individual (25% for syariah banks) shareholders, the 40%
  ceiling exceedable with OJK approval plus health/CAR/go-public-in-5yr
  conditions; none of the caps bind Pemerintah or LPS.
- **64123/64124 — BPR/BPRS ("Perbankan Konvensional/Syariah Lainnya"): regime
  changed by P2SK, opened by silence.** Old UU 7/1992 Pasal 23 restricted BPR
  founders to WNI / wholly-domestic legal entity / pemda; P2SK's amendment to
  Pasal 23 drops that qualifier — founders now "WNI dan/atau badan hukum
  Indonesia" (PT PMA qualifies). POJK 7/2024 (PRIMARY, Bab III Pasal 28-47 read
  in full) contains **zero nationality tests** in its ownership chapter — no
  banking-specific %-cap is in force; entry runs through ordinary FDI/BKPM
  machinery. This is a recent change (2023-2024) and should be presented as
  such, not as a settled long-standing rule.
- **64193/64194 — LKM (non-bank microfinance): domestic-only, absolute.** ★
  UU 1/2013 Pasal 8 (owners restricted to WNI / BUMDes / pemda kabupaten-kota
  / koperasi) plus Pasal 6 verbatim: *"LKM dilarang dimiliki, baik langsung
  maupun tidak langsung, oleh warga negara asing dan/atau badan usaha yang
  sebagian atau seluruhnya dimiliki oleh warga negara asing."* Independently
  re-enacted by POJK 41/2024 Pasal 3/Pasal 4 (PRIMARY-VERBATIM, 185pp fetched):
  PT form needs ≥60% pemda/BUMDes ownership, WNI individual cap 20%. **P2SK did
  NOT open LKM** — POJK 41/2024 is P2SK's own implementing regulation, not a
  liberalisation. This makes any canonical entry showing LKM as TERBUKA/100%
  **flat false** and, per the source gate file, "the worst lie in the family" —
  the correct disclosure is TERTUTUP-to-foreign (0%), direct **and** indirect,
  statutory.
- **64199 — Perantara Moneter Lainnya YTDL: unresolved.** No governing
  license/ownership provision was identified (a residual deposit-taking
  bucket, possibly near-dormant). Render as honest disclosure with **no
  verdict** — this is a declared gap, not a finding (see Declared gaps below).

### Financing / pembiayaan

- **Perusahaan Pembiayaan (64910/64920/64930/64959): 85% of modal disetor,
  direct + indirect.** HIGH/VERBATIM via the chain POJK 47/2020 → POJK
  46/2024 Pasal 4 angka 9 (new Pasal 9) → POJK 35/2025 (effective 22-12-2025,
  current). Verbatim held: *"kepemilikan asing Perusahaan baik secara
  langsung maupun tidak langsung dilarang melebihi 85% ... dari modal
  disetor"* — with exceptions: grandfather for pre-existing >85% holdings (no
  ownership change), listed-company exemption, capital-rescue breach (3-year
  cure window), and a power/shipping-dedicated financing carve-out. Foreign
  entities enter only via kemitraan; foreign individuals only via capital
  market. POJK 35/2025 reframed the 85% from a PP-deferred fallback into a
  standing OJK rule.
- **Pembiayaan Infrastruktur (64951/64952): 85%, but still interim.** Now
  HIGH/VERBATIM (own Pasal 10, POJK 35/2025): 85% cap, but framed as *"Dalam
  hal peraturan pemerintah ... belum berlaku"* — i.e. it stands only until an
  unissued implementing PP arrives. Minimum capital Rp2 trillion within 5
  years (own Pasal 8(4)).
- **Modal Ventura (64991/64992): 85%, direct standing rule.** Now
  HIGH/VERBATIM — POJK 35/2025 item 38 rewrites the PMV Pasal 10: 85% direct +
  indirect, as a **direct** standing rule (the PP-gate is removed here, unlike
  Infrastruktur), exceptions a-e (grandfather/listed/rescue/3yr) but
  **without** the power/shipping carve-out. Minimum capital Rp50bn,
  primary-verified. The **PT/Koperasi-only legal-form requirement keeps its
  original, separate hedge** — MEDIUM confidence, secondary pattern-inference
  from the first pass — the second-pass upgrade to HIGH/VERBATIM covers only
  the 85% cap, its exceptions, and the minimum-capital figure, not the form
  requirement.
- **Gadai / pawnbroking (64953/64954): mechanism-only, NO percentage — a
  retraction.** See the RETRACTION in Method receipts below: the true regime
  is POJK 39/2024 Pasal 4, unamended — mechanism-only (badan hukum asing via
  kemitraan bersama; WNA via pasar modal only), with **no numeric cap in
  force** pending an unissued PP. Render the mechanism, never a percentage,
  for this family.
- **LPBBTI / P2P lending (66161/66162): 85%, interim.** HIGH/VERBATIM — POJK
  40/2024 Pasal 3(6) (revokes POJK 10/2022), same interim framing as
  Infrastruktur ("Dalam hal peraturan pemerintah ... belum berlaku"), only
  the cap + grandfather limbs (no listed/rescue carve-outs). Minimum capital
  Rp25bn (secondary confidence). Reconfirmed unchanged in the second pass
  (only SEOJK 19/2025 exists, no ownership content).
- **64940 — Pembiayaan Sekunder Perumahan** (SMF-style secondary mortgage,
  NOT generic securitization): no private licensing path found (LOW/absence
  finding — a gap, not a cap).
- **64210 (holding) / 64220 (conduit)**: no OJK sectoral cap identified;
  governed by general company law (MEDIUM/absence finding).
- **Three distinct postures across this sector** — do not flatten to one
  "85% financing" line: **direct-rule** (Pembiayaan + Modal Ventura, current
  since Dec-2025) · **interim-pending-PP** (Infrastruktur + LPBBTI, same 85%
  figure but conditional on an unissued PP) · **mechanism-only-no-%**
  (Pergadaian). The final implementing PP with a permanent number is unissued
  for all five families; all five share an identical who-can-own template
  (6-category list; foreign entity via kemitraan bersama; foreign individual
  via pasar modal only).

### Capital markets, payments, digital assets

- **Securities (66121/66196) + Investment Management (66301/66302/66309):
  tiered 85%/99%.** PRIMARY-VERIFIED, full PP 31/2022 PDF (LN 2022/179, TLN
  6816). Pasal 1 angka 2 confirms Manajer Investasi is within scope. Pasal 2:
  a Perusahaan Efek is either **nasional** (100% WNI/domestic-entity-owned) or
  **patungan** (JV, where the foreign shareholder must itself be a
  financial-sector entity). Pasal 3 tiers the JV foreign cap: **85%** of modal
  disetor for a non-securities financial foreign shareholder, **99%** for a
  foreign shareholder licensed/supervised by a securities regulator in its
  home jurisdiction. Pasal 4: on a **public offering (Penawaran Umum)** the
  Pasal 2/3 caps "tidak berlaku" — shares "dapat dimiliki seluruhnya oleh
  Pemodal Dalam Negeri atau Pemodal Asing", including non-financial foreign
  investors. Pasal 5: PP 45/1995 jo. PP 12/2004 formally revoked.
- **Investment Advisory (66151/66153/66159)**: a separate license track, NOT
  a Perusahaan Efek — no sector foreign-ownership cap found; the Perpres
  lampiran entry is unverified (scanned PDF). Render as a disclosure frame,
  no number.
- **Money changer (66125): 100% domestic.** PBI 18/20/PBI/2016 Pasal 4,
  verbatim, direct bi.go.id fetch: *"berbadan hukum Perseroan Terbatas yang
  seluruh sahamnya dimiliki oleh warga negara Indonesia dan/atau badan usaha
  yang seluruh sahamnya dimiliki oleh warga negara Indonesia."* Still in
  force (a hypothesised "PBI 24/2022 successor" does not exist). P2SK has no
  effect — BI retains KUPVA-bukan-bank.
- **PJP — payment service providers (66141): max 85% foreign equity, min 51%
  domestic voting.** PBI 23/6/PBI/2021, moderate confidence, triangulated
  three times ("min 15% domestic" is a noise/mis-paraphrase variant — do not
  use it) — domestic side must also hold control rights, not just equity.
- **PIP — payment infrastructure providers (66142): min 80% domestic (max
  20% foreign).** PBI 23/7/PBI/2021, near-verbatim: *"Komposisi kepemilikan
  saham paling sedikit 80% ... dimiliki oleh warga negara Indonesia dan/atau
  badan hukum Indonesia"* — applies to **both** equity and voting.
- **66143**: no distinct instrument identified — NOT VERIFIED, not a
  finding.
- **Exchanges / SROs (66111-66119, 66131-66133): no nationality cap;
  eligibility gated by institutional category, not ownership %.** UU 8/1995
  Pasal 8: Bursa Efek shareholders must be licensed broker-dealer Perusahaan
  Efek. Pasal 15 (corrected from an earlier mis-cite of Pasal 14): the
  eligible-shareholder pool for LKP and LPP is identical — Bursa Efek /
  Perusahaan Efek / BAE / Bank Kustodian / other OJK-approved entities; the
  majority-must-be-BEI-held rule is Pasal 15(2) and is **LKP-only**
  (deliberate per the elucidation — KSEI/LPP carries no such majority rule).
  **Live-unresolved**: UU 4/2026 (amending P2SK) opens BEI demutualization —
  shareholders may be individuals or entities, member or not (Pasal 8(3));
  Kemenkeu/BI/Danantara may hold (Pasal 8B(1)) — but the implementing POJK
  Demutualisasi is **not yet issued** (target Q3-2026). Render as "pending
  POJK Demutualisasi"; assert nothing further.
- **Commodity futures (66122/66152/66303): a hedged, currency-unconfirmed
  95%.** PP 49/2014's own text does NOT carry a 95% figure — this is a
  confirmed negative (Bab IV Pasal 45-52 read; Pasal 46(2) fully delegates
  permodalan/ownership detail to a Perba). The commonly-cited 95% figure
  traces to Perba Bappebti 74/2009, a 2009 implementing regulation whose
  **current-in-force status is unverified**. Use only with a "per Bappebti
  implementing regulation, status unconfirmed" hedge, or omit the number and
  disclose the mechanism only. New verbatim held: PP 49/2014 Pasal 8 (Bursa
  Berjangka) + Pasal 34 (Lembaga Kliring Berjangka) share a **dispersed-
  ownership template** — an Indonesian legal-entity shareholder that itself
  carries foreign capital may hold ≤10% of SRO shares each, and all such
  entities aggregate to ≤40%.
- **Digital assets / crypto (66113/66123/66127, 64995): POJK 27/2024,
  role-specific, no flat cap.** Regulatory authority moved Bappebti→OJK
  10-Jan-2025 (confirmed); POJK 27/2024 + POJK 23/2025 capital floors
  confirmed. **Bursa Kripto** (Pasal 23, verbatim): shares the SRO
  dispersed-ownership template — per-shareholder ≤20% of modal disetor,
  foreign-capital-carrying PT shareholders ≤10% each, aggregate ≤40%.
  **Pedagang Aset Kripto** (Pasal 48/49, verbatim): **no foreign equity cap**
  at all — foreigners are eligible owners on equal footing — but control is
  structural: majority of Direksi must be WNI and domiciled in Indonesia,
  the Direktur Utama must be WNI, and a foreign investor already in one
  Pedagang may hold in only ONE Pedagang (anti-concentration). **Do not
  import the financing-sector 85% figure by analogy anywhere in this
  family** — it does not appear in POJK 27/2024 or POJK 23/2025 for
  ownership.

### Penjaminan, insurance, pensions

- **Penjaminan / credit guarantee (65131/65132/65203/65204): 30%, and the
  Pasal number is 9(2), not 15.** ⚠️ Correction preserved verbatim from the
  gate file: the cap is UU 1/2016 **Pasal 9(2)** (Bab III, "Badan Hukum dan
  Permodalan" — a self-corrected Bab label; Bab IV starts at Pasal 13 and
  covers cross-shareholding caps / one-PSP rule / kepengurusan Pasal 15-17).
  **Never cite Pasal 15 for this cap** — Pasal 15 is kepengurusan
  (management), not ownership. Verbatim Pasal 9(2): *"Kepemilikan asing pada
  Lembaga Penjamin berbentuk badan hukum perseroan terbatas, baik secara
  langsung maupun tidak langsung paling banyak sebesar 30% (tiga puluh per
  seratus) dari modal disetor."* Pasal 9(3): the foreign capital portion must
  sit in a domestic-bank account in the Lembaga Penjamin's own name. Pasal 1
  angka 6 verbatim defines Lembaga Penjamin as covering Perusahaan
  Penjaminan, Penjaminan Syariah, Penjaminan Ulang, and Penjaminan Ulang
  Syariah — so **all four** codes 65131/65132/65203/65204 sit at 30%,
  primary. **66224-66226 (agen/broker penjaminan)** are NOT among the law's
  defined terms (all 25 angka of Pasal 1 read, pp.1-15/47) — "very likely
  outside scope" but not formally confirmed; frame under ordinary PMA rules,
  make no 30% assertion for these three codes.
- **Insurance (65111/65112/65121/65122/65201/65202/66222/66223/66212): 80%,
  scope definitively closed.** UU 40/2014 Pasal 1 angka 14 (official BPK
  copy) verbatim: *"Perusahaan Perasuransian adalah perusahaan asuransi,
  perusahaan asuransi syariah, perusahaan reasuransi, perusahaan reasuransi
  syariah, perusahaan pialang asuransi, perusahaan pialang reasuransi, dan
  perusahaan penilai kerugian asuransi."* PP 14/2018 Pasal 1 angka 2
  re-defines the term with the **identical, word-for-word 7-item list** — so
  the 80% cap covers exactly: asuransi (65111/65112), asuransi syariah
  (65121/65122), reasuransi (65201), reasuransi syariah (65202), pialang
  asuransi (66222), pialang reasuransi (66223), penilai kerugian asuransi
  (66212). **Explicitly excluded**, verbatim: 66221 agen asuransi (Pasal 1
  angka 28 defines this as a **person** acting for/on behalf of an insurer —
  categorically not the capped corporate entity) and 66291 aktuaria
  (a profession, usaha penunjang) — both governed by ordinary PMA rules for
  their corporate wrapper, not the 80% cap. **66211 penilai risiko**: the
  statute names only "penilai kerugian" — do **not** assert 66211 falls under
  the cap without a dedicated mapping follow-up (open item). Mechanism:
  UU 40/2014 Pasal 7(1)(b) — the foreign shareholder must itself be a
  same-line Perusahaan Perasuransian, or a parent with a same-line
  subsidiary; Pasal 7(2) — WNA individuals may hold only via bursa efek. PP
  14/2018 operative set, all verbatim: Pasal 3 (WNA via bursa; badan hukum
  asing via direct/bursa/Indonesian holdco), Pasal 4 (strategic-partner gate
  + equity requirement ≥5× the target stake, exempt if entering via bursa or
  holdco), **Pasal 5(1) — 80% of modal disetor**, Pasal 5(2) — listed-company
  carve-out (perseroan terbuka is uncapped), Pasal 6 — grandfather clause
  (pre-existing >80% holdings are frozen; an increase is allowed only via IPO
  or an injection of ≥20% new domestic capital), Pasal 10 revokes PP 73/1992
  jo. PP 81/2008. The Penjelasan to Pasal 5(1) states the 80% is **cumulative
  across all ownership channels**. A first-pass claim that "PP 3/2020 allows
  new cases >80%" was investigated and **rejected** — it directly contradicts
  the held Pasal 6 verbatim; do not import it anywhere downstream.
- **P2SK vs the 80% and the 30% — both definitively unmoved.** Full 819pp
  P2SK text grepped chapter-by-chapter for both figures. For insurance: Bab
  VI Perasuransian (Pasal 51-103, source lines 13207-14681) amends 28 UU
  40/2014 articles — **Pasal 7 is not among them**; zero grep hits for
  "kepemilikan asing" / "80%" / "delapan puluh persen" across the entire
  chapter; the only Pasal-7 mention in the whole chapter is the **new**
  sanctions article (Pasal 71), which cites Pasal 7(1) as a still-live
  obligation — affirmative evidence it stands unamended. For penjaminan: Bab
  IX Penjaminan is Pasal 104-105 only, and the sole substantive edit anywhere
  in P2SK touching UU 1/2016 is Pasal 62 (sharia-unit spin-off, implemented
  by POJK 10/2023) — Pasal 9 is untouched; the only other UU 1/2016 reference
  in P2SK is the Pasal 326 continuity boilerplate.
- **Pensions (65301-65304): the barrier is legal form, not a percentage.**
  P2SK (UU 4/2023) Pasal 330 revokes UU 11/1992 outright. Pasal 135: Dana
  Pensiun is a sui generis legal entity — it has no shares, so there is
  nothing to cap a foreign % of. Pasal 137(2): a DPPK (employer pension fund)
  may be founded only by the employer itself — of any nationality, including
  a PT PMA, for its own staff — subject to OJK approval. Pasal 137(3): a
  DPLK (financial-institution pension fund) may be founded only by a closed
  list — bank umum/syariah, perusahaan asuransi jiwa/syariah, manajer
  investasi/syariah, plus other OJK-designated founders. **There is no
  PT-PMA path for a pension-fund business itself**; any foreign exposure
  flows only through the founder's own sector cap (e.g. an insurer-founded
  DPLK inherits the insurer's 80% ceiling upstream, not a pension-specific
  number). Render as a form barrier, never as a %.
- **Bonus, first-pass, not re-verified**: 66192 Kustodian/trust appears
  bank-gated (POJK 27/2015; Wali Amanat restricted to Bank Umum per POJK
  19/2020) — carried here as a lead, not a closed finding. 64330 scope is
  still unverified (declared gap).

## Method receipts

- **RETRACTION[gadai-85-secondary] — pergadaian is NOT capped at 85%.** The
  first-pass finding "Gadai 85% as of POJK 29/2025" is **false**. The full
  52-page POJK 29/2025 was fetched primary (BPK Download/410985) and grepped
  end-to-end: it amends Pasal 42A / 47 / 52 / 53A / 54 / 55A / 56 / 56A / 62 /
  63 / 65 / 65A **only** — it never touches Pasal 3 or Pasal 4 (the ownership
  articles), and the string "85%" / "delapan puluh lima persen" appears
  **nowhere** in the document. The four secondary outlets that reported 85%
  for this family were wrong. The true regime is POJK 39/2024 Pasal 4,
  unamended — mechanism-only, no numeric cap in force. Third-pass
  confirmation: the negative was checked doubly, against both the regulation
  text and OJK's own FAQ document (both primary, 0 hits for "asing"/"85%",
  `pdfinfo` confirms the 52pp is complete). This retraction is preserved here
  exactly because it is part of the record — do not silently correct it away.
- **Penjaminan Pasal 9(2), not Pasal 15.** The 30% cap for Lembaga Penjamin
  is in UU 1/2016 Pasal 9(2) (Bab III, ownership), not Pasal 15 (Bab IV,
  kepengurusan/management). An early draft of this research line risked
  citing Pasal 15 — the gate file flags this explicitly ("Never cite Pasal
  15") and it is preserved as a standing correction above.
- **UU 8/1995 Pasal 15, not Pasal 14.** The LKP/LPP eligible-shareholder
  article is Pasal 15, correcting an earlier mis-cite of Pasal 14 in the
  same research line. Pasal 8 (Bursa Efek shareholder eligibility) is a
  separate, correctly-cited article and was never in question.
- **P2SK non-movement, proven both directions.** Both the 30% (penjaminan)
  and 80% (insurance) caps were checked not by absence-of-mention but by a
  full chapter grep of the 819pp P2SK statute against the exact percentage
  strings and the governing pasal numbers, in both Indonesian numeral forms
  ("30%"/"tiga puluh per seratus", "80%"/"delapan puluh persen"). Zero hits
  in the relevant chapters is treated as affirmative evidence, strengthened
  in the insurance case by a *new* P2SK sanctions article (Pasal 71) that
  cites the un-amended Pasal 7(1) as a still-live obligation.
- **BPK Download fetch technique.** peraturan.bpk.go.id serves regulation
  PDFs behind a Download endpoint that returns 403 to a bare `curl`; a
  browser-identified User-Agent header beats it reliably. **Known bug**:
  Download ID 54286 serves a **wrong cached PDF** unrelated to the requested
  instrument — a real BPK-side defect, not a fetch-tool error. For PP
  29/1999, use Download ID **43683** instead (confirmed correct content:
  Pasal 3 99% verbatim, Pasal 4(1)-(3) listing mechanics, Penjelasan
  self-declaring the PP as the UU 10/1998 kemitraan elaboration). Treat any
  single Download ID that resolves to unexpected content as a candidate
  instance of this bug before treating it as evidence for or against a
  claim.
- **Perpres 10/2021 Pasal 11(2) — OCR caveat.** The source for the sectoral
  carve-out is a single OCR'd text dump of the BPK Download/154474 PDF
  (`scratchpad/perpres10-2021-pt.txt`), not a re-fetched clean copy. The raw
  OCR text (line 568-575) reads: *"Pcrizinan bcrusaha dan pelaksanaan
  kegiatan dalam rangka Pcnanaman Modal untuk Bidang Usaha kctrangan dan
  Bidang Usaha pcrbankan diiaksanakan se suai dengan ketentuan pcraLuran
  perundang_ undangan di bidangnya masing-rnasing."* The intended reading
  (character-substitution artifacts are typical OCR noise — c/e, l/i, rn/m
  confusions) is: *"Perizinan berusaha dan pelaksanaan kegiatan dalam rangka
  Penanaman Modal untuk Bidang Usaha keuangan dan Bidang Usaha perbankan
  dilaksanakan sesuai dengan ketentuan peraturan perundang-undangan di
  bidangnya masing-masing"* — i.e. business licensing for the **finance** and
  **banking** business fields follows their own sectoral regulations, not
  Perpres 10/2021's general positive-list mechanics. This cleaned reading is
  a reconstruction from a single noisy OCR pass, **not independently
  re-verified against a second clean fetch** — treat the pasal number and
  general thrust as reliable, but do not quote the cleaned sentence as a
  verbatim primary citation without a fresh fetch.

## Declared gaps

Carried over verbatim (in substance) from the four gate files' own open
items — none of these were chased to closure in this pass:

- **64199 (Perantara Moneter Lainnya YTDL)**: no governing license/ownership
  provision identified at all; render honest disclosure with no verdict.
- **66143**: no distinct payments/markets instrument identified — not
  verified, not resolved.
- **Perba Bappebti 74/2009 currency status**: the 95% commodity-futures
  figure traces only to this 2009 implementing regulation, whose current
  in-force status was not confirmed (do not conflate with Perba 76/2009's
  separate revocation, a different regulation).
- **POJK 5/2026 effect on Manajer Investasi**: not chased; believed unlikely
  to touch ownership % since PP 31/2022 governs ownership directly, but this
  is an assumption, not a verified negative.
- **64330 scope**: unverified (penjaminan/insurance gate file, bonus note).
- **Perpres-annex overlay on bank codes**: not checked — whether Perpres
  10/2021's own Lampiran (as amended) carries a separate overlay on the
  banking codes was flagged as an open item in the banking gate file and was
  not investigated in this pass. The Pasal 11(2) carve-out documented above
  (finance/banking fields deferred to sectoral law) is the closest available
  signal but does not by itself resolve whether an annex-level overlay
  exists.
- Secondary/unclosed items noted in-line above and not repeated here:
  66211 penilai risiko mapping, investment-advisory Perpres lampiran
  (scanned PDF, unread), 66192 Kustodian/Wali Amanat (first-pass only), UU
  4/2026 POJK Demutualisasi (target Q3-2026, not yet issued).

## Adversarial review

Codex GPT-5.6 (`gpt-5.6-terra`), 2026-08-08 — read-only refute pass against
this capture, checking every percentage and pasal citation against the four
source gate files' own verbatims, and flagging any claim stated more
strongly than its source file states it (the W113 failure mode: a
correction/retraction that is itself imprecise). The reviewer read all five
files directly off disk (this capture + the four gate scratchpads) rather
than trusting a summary, and confirmed generator≠grader (Codex GPT-5.6
family, independent of the Claude session that wrote the capture).

Three objections raised, all fixed in this revision:

1. **PP 29/1999 (Bank Umum 99% cap) was under-credited.** The capture
   originally called it "Triangulated — strong" — the first-pass confidence
   level — while the banking gate file's second pass explicitly upgraded it
   to PRIMARY-VERBATIM (correct Download ID 43683, Pasal 3/4 verbatim). Not
   an overclaim, but a violation of "keep the same evidentiary level as the
   source" — fixed by stating the PRIMARY-VERBATIM upgrade explicitly.
2. **Modal Ventura's "PT/Koperasi form only" clause lost its hedge — the
   W113 shape.** The capture folded the whole Modal Ventura entry under
   "Now HIGH/VERBATIM", including the PT/Koperasi legal-form requirement.
   The gate file's second pass only upgrades the 85% cap, its exceptions,
   and the minimum-capital figure to HIGH/VERBATIM — the legal-form
   requirement itself remains MEDIUM/secondary-pattern-inference from the
   first pass, untouched by the second. Fixed by re-separating the hedge.
3. **The Perpres 10/2021 Pasal 11(2) block reads as part of the "faithful
   four-gate consolidation" but is not supported by any of the four gates.**
   The OCR-reconstruction caveat itself was correctly stated (no overclaim
   on verification level), but the document did not flag this as a fifth,
   independent source outside the four-gate chain. Fixed by adding an
   explicit fifth-source note in the introduction.

Everything else the reviewer checked passed without objection: all other
percentages and their hedges (banking category caps 40/30/20/25%, financing
85% family, PP 31/2022's 85/99 tier, PJP 85%+51% at moderate confidence, PIP
80/20, the SRO 20/10/40 dispersed-ownership template, penjaminan 30%,
insurance 80%, money changer 100%, commodity futures 95% with its
currency-status hedge intact); both Pasal corrections (penjaminan UU 1/2016
Pasal 9(2) never Pasal 15; UU 8/1995 Pasal 15 for LKP/LPP kept distinct from
Pasal 8 for Bursa Efek); the gadai retraction, integral everywhere including
the "three postures" summary line; the LKM 64193/64194 finding; both P2SK
non-movement proofs; the BPK Download-ID bug note; the insurance-cap KBLI
code mapping; and the Declared gaps section.
