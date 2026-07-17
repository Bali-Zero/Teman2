---
date: 2026-07-17
domain: visa
client_case: none — Visa Oracle v2 TRACK B Content, Phase 1 (Bridging branch + bonifica Table-2 close-out)
sources:
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/{D7,D7A,D7B,D8A,D8B,D7ZZ,E23B,B211A} — 8 direct per-code fetches, live 2026-07-17, EACH double-verified with an independent second tool (WebFetch + raw curl/grep on saved HTML; §2.1) — incl. 1 invented-code negative control (D7ZZ) and 2 KNOWN-DEAD-code controls (E23B consolidated into E23; B211A retired)
  - https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia/d7a-visa-pertunjukan-musik + …/d7b-kru-… — live-fetched 2026-07-17; resolves to the official "Informasi Visa Republik Indonesia" product directory, which TODAY lists "D7A Visa Pertunjukan Musik" and "D7B Visa Kru Pertunjukan Musik" among ~80 clickable product links (§2.1 evidence line 3)
  - apps/kb/data/immigration/visa_d7a-visa-pertunjukan-musik.txt (+d7b/d8a/d8b) — on-disk post-reform crawl (committed f2d9fb0bc, 2026-03-31); crawl captured page chrome+nav only (NOT product bodies — see §2.1 honesty note), so it evidences the official product URL slugs/names existing at crawl time, nothing more
  - https://peraturan.bpk.go.id/Download/344251/ Permenkumham Nomor 11 Tahun 2024.pdf — PRIMARY legal text, downloaded + pdftotext-extracted this session (49 pp.)
  - https://peraturan.bpk.go.id/Download/378164/ Permen Imipas Nomor 3 Tahun 2025.pdf — PRIMARY legal text, downloaded + pdftotext-extracted this session (33 pp.; its Pasal 45 resolves the revocation tension, §3.2a)
  - https://peraturan.bpk.go.id/Download/365416/ PP Nomor 45 Tahun 2024.pdf — downloaded; tariff lampiran is a scan, NOT machine-extractable (§6)
  - https://kupang.imigrasi.go.id/izin-tinggal-peralihan-… + https://depok.imigrasi.go.id/direktorat-jenderal-imigrasi-berlakukan-bridging-visa/ (official kanwil articles, live-fetched 2026-07-17)
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/global-citizen (official diaspora landing, live-fetched 2026-07-17)
  - https://jakartapusat.imigrasi.go.id/layanan/biaya-keimigrasian (official PNBP fee list, live-fetched 2026-07-17)
  - research/visa/2026-07-17-visa-catalog-bonifica-110-remap.md — NOT in this branch's tree; lives on PR #2602's branch `origin/agent/air-m5/mouth/visa-catalog-bonifica` (fetched and read this session); its Table 2 is the gap list this file closes
  - research/visa/2026-07-17-catalog-gaps-closeout-d7ab-diaspora.md + 2026-07-17-bridging-visa-branch-profile.md — PARALLEL-SESSION deliverables found untracked in this same worktree mid-session; reconciled in §8 (their raw probe data is byte-identical to this session's; the D7A/D7B verdict divergence is a signal-choice artifact, resolved §2.1; their GCI enumeration and revocation-tension finding are adopted §4.2a/§3.2a)
  - docs/plans/2026-07-17-visa-oracle-v2/00-product-design.md §4 + research/visa/2026-07-17-visa-oracle-v2-round2-glm-interview-design.md + round2-gemini-regulatory-delta.md (this repo, on main)
  - apps/backend-rag/backend/data/bali_zero_official_prices_2026.json (PricingTool SSOT) + apps/backend-rag/backend/db/migrations_v2/148_practice_types_bridging_visa.sql (CRM practice type — §3.6 category liability) — both read on-disk this session
status: phase-1 deliverable — D7A/D7B + D8A/D8B RESOLVED-EXIST; Bridging fact-base primary-grounded incl. partial-revocation resolution; diaspora COVERED (product-level, Kepmen-gated); parallel-session conflict reconciled
adversarial_review: codex
---

# Bridging Visa branch + D7A/D7B (+D8A/D8B) + diaspora — bonifica Table-2 close-out (TRACK B, Phase 1)

> One-line: closes the three open items of the catalog bonifica's Table 2 (PR #2602) on primary-source
> evidence, finds one more gap of the same class (D8A/D8B), resolves a live conflict with a
> parallel-session deliverable on D7A/D7B (byte-identical raw data, divergent signal choice — settled by
> dead-code controls + the official product directory listing both codes today), and resolves the
> Permenkumham-11/2024 "revoked?" tension from the primary text of Permen Imipas 3/2025 (partial
> revocation, bridging articles untouched). Content research only — no engine code, no catalog DB writes.

## 1. Mandate and scope

TRACK B — Content of the Visa Oracle v2 corner (claim declared in this PR). Phase 1 of 2: research and
construction of the Bridging Visa branch + close the D7A/D7B and diaspora gaps left open by the catalog
bonifica (Table 2). Phase 2 (the 7 interview categories on the cleaned catalog) is gated on #2602's
merge and is NOT part of this file. Scope fence: `research/visa/**` only. Mid-session, two
parallel-session files on the same topics appeared untracked in this shared worktree — treated as
sibling work (not modified), reconciled in §8.

## 2. D7A / D7B — RESOLVED: both codes EXIST (and so do D8A / D8B)

### 2.1 Method — the discriminator, controlled and reconciled

The bonifica probed `imigrasi.go.id/wna/daftar-visa-indonesia/{CODE}` on page-TITLE alone and left D7A
OPEN. This session re-probed with two independent tools per code (WebFetch + raw curl/grep on saved
HTML) and added what no prior pass had: **known-dead-code controls**. The full signature space, from
this session's own saved HTML (every count reproducible from the files in the session log):

| Probe | Class | "Daftar Visa Indonesia" count | "Data Belum Tersedia" count | Body | Verdict |
|---|---|---|---|---|---|
| D7 | positive control (in catalog) | 2 | 0 | populated + specific heading | live ✓ |
| **D7A** | disputed | 3 | **0** | **populated, code-specific** | **EXISTS** |
| **D7B** | disputed | 3 | **0** | **populated, code-specific** | **EXISTS** |
| **D8A** | discovered (§2.3) | 3 | **0** | **populated, code-specific** | **EXISTS** |
| **D8B** | discovered (§2.3) | 3 | **0** | **populated, code-specific** | **EXISTS** |
| D7ZZ | invented negative control | 3 | 1 | empty | not a code ✓ |
| **E23B** | **known-DEAD control** (consolidated into E23, 3-source press quote in the bonifica) | — | 1 | **empty** | dead ✓ |
| **B211A** | **known-DEAD control** (retired; C1/C2 successors; `OBSOLETE_VISA_CODES` in the engine) | — | 1 | **empty** | dead ✓ |

Three-state signature, and this is the load-bearing methodological finding: the generic-heading count
(2 vs 3) separates only *curated* from *uncurated* pages — it groups live-but-unheadlined pages together
with fakes. The **"Data Belum Tersedia" empty-body marker separates live from dead**: every control
known or invented to be dead shows it exactly once; every populated page shows it zero times. D7A, D7B,
D8A, D8B all sit in the live-uncurated state: generic heading slot, full code-specific body (distinct
D7A performer prose vs D7B crew prose, correct in-body cross-references, complete section structure,
PNBP figures).

Because a body-populated page could still in principle be CMS residue, three further evidence lines:

1. **Dead-code purge behavior**: E23B and B211A — codes the reform demonstrably killed — are EMPTY.
   This CMS does not keep populated bodies for dead codes on the two known-dead routes tested. (Two
   controls characterize a purge *behavior*, not every conceivable CMS state — accepted residual risk,
   stated rather than hidden.)
2. **The official product directory TODAY**: `…/wna/permohonan-visa-republik-indonesia/…` was
   live-fetched this session and **lists "D7A Visa Pertunjukan Musik" and "D7B Visa Kru Pertunjukan
   Musik" among its ~80 clickable product links** — current navigation, not an archive. This directly
   contradicts the "the current official list omits D7A/D7B" claim (which came from the SUMMARY flat
   list, a tier the bonifica already proved lossy — it omits ~15 real codes).
3. **Post-reform crawl slugs**: the repo's 2026-03-31 crawl contains files for the official product
   URLs `d7a-visa-pertunjukan-musik` / `d7b-visa-kru-pertunjukan-musik`. HONESTY NOTE (pass-2
   correction): the crawl captured page chrome+nav only, NOT product bodies — it evidences that the
   official site exposed those named product routes at crawl time, nothing more. The body evidence is
   this session's own live fetches, not the crawl.

**Reconciliation with the parallel session (§8):** its probe run measured the same pages and got
byte-identical sizes and the same heading-slot counts, then concluded ABSENT from the count-3 signature
plus missing specific headings — without a body-content check and with only invented-code negative
controls (which are empty-bodied, so its two legs could not distinguish live-uncurated from dead). The
raw data of the two sessions agree completely; the verdicts diverged on signal choice. With the
body-marker leg, the dead-code controls, and the live product-directory listing, **EXISTS stands**.
Residual caveats carried into the RulePack gate: the heading slot is unpopulated and D7B's "Jenis visa"
sentence says "Visa D7" where D7B is meant (copy-edit slip on a live page — dead pages on this CMS look
empty, not mislabeled); these pages are less curated than their C-series siblings.

### 2.2 What the codes are (official body text, verbatim-sourced)

The **multiple-entry (D-series) analogues of C7A/C7B**:

- **D7A** — *"Dengan visa D7A, anda dapat melakukan kegiatan seni dan budaya di Indonesia seperti
  memperlihatkan, menampilkan atau mempertunjukkan (perform) suatu karya yang berhubungan dengan
  musik…"* — music/arts performance, multiple entry.
- **D7B** — *"…kegiatan dalam rangka mendukung orang asing yang melakukan seni dan budaya…"* — the
  supporting-crew counterpart.
- Shared mechanics (both pages, identical wording): *"Visa Kunjungan untuk beberapa kali masuk ke
  Indonesia dengan izin tinggal maksimal 30 hari setiap kedatangan"*; *"Izin tinggal dari visa ini
  tidak bisa diperpanjang atau dialihkan menjadi izin tinggal terbatas"*; sponsor (penjamin) files via
  evisa.imigrasi.go.id; honorarium allowed, employment relationship prohibited. Official PNBP shown:
  Rp 2.500.000 per 30-day stay — recorded as source evidence ONLY (client surfaces carry a single
  all-inclusive Bali Zero price per the owner's ruling, §3.5; no Bali Zero price exists yet for these
  codes, §7).

### 2.3 D8A / D8B — same-class discovery beyond the mandate's named gaps

A systematic diff of the crawl corpus' 85 per-code product pages against the catalog's 114 codes yields
**exactly four** codes with an official product page and no catalog row: D7A, D7B, **D8A, D8B**. Both
D8 sub-codes live-verified this session with the same dual-tool check (populated bodies, zero empty
markers): **D8A** *"…melakukan kegiatan olahraga yang tidak bersifat komersial seperti mengikuti
kegiatan olahraga atas undangan pemerintah Indonesia…"* (athlete; corpus name "Visa Olahraga (Atlet)"),
**D8B** the same non-commercial-sport frame for officials ("Visa Olahraga (Ofisial)"); both max **60
days per entry** (unlike D7A/D7B's 30), PNBP Rp 2.500.000, sponsor via evisa — the D-series analogues
of C8A/C8B.

### 2.4 Proposed catalog rows (content-ready, no DB write here)

| Code | Name (catalog EN, consistent with C-series siblings) | Category | Stay | Notes |
|---|---|---|---|---|
| D7A | Visit Visa Music Performance (Multiple Entry) | Multiple-Entry Visit | max 30 days/entry, non-extendable, non-convertible | sponsor-filed via evisa; honorarium allowed, employment prohibited |
| D7B | Visit Visa Music Performance Crew (Multiple Entry) | Multiple-Entry Visit | max 30 days/entry, non-extendable, non-convertible | crew supporting the D7A activity |
| D8A | Visit Visa Athlete (Multiple Entry) | Multiple-Entry Visit | max 60 days/entry | non-commercial sports; sponsor-filed via evisa |
| D8B | Visit Visa Sports Official (Multiple Entry) | Multiple-Entry Visit | max 60 days/entry | non-commercial sports officials |

Catalog frame stated on the bonifica's own arithmetic: today 114 rows = 110 confirmed index rows + 4
out-of-scope service labels. These additions apply to the INDEX side: **110 → 114 confirmed index rows**
(catalog total 114 → 118 if the out-of-scope labels stay). All four rows enter the RulePack only through
the four-eyes quarantine gate (bonifica §7), carrying the §2.1 curation caveats.

## 3. Bridging Visa — the fact base on primary text

### 3.1 Legal identity

**Not a visa-index code.** An **Izin Tinggal Kunjungan granted "dalam rangka peralihan Izin Tinggal
Keimigrasian"** — created by **Permenkumham 11/2024** (promulgated 1 April 2024) inserting Pasal 86A,
94A, 94B into Permenkumham 22/2023. Primary PDF downloaded and read this session (the bonifica's WAF
blocker does not bite peraturan.bpk.go.id under a browser UA). The bonifica's classification
(catalog/interview product, not a Kepmen index row) is confirmed.

### 3.2 The rules, article by article (primary text, extracted verbatim this session)

| Fact | Primary text | Source |
|---|---|---|
| Duration **max 60 days, non-extendable** | *"diberikan untuk jangka waktu paling lama 60 (enam puluh) hari dan tidak dapat diperpanjang"* | Ps. 86A(1) |
| Permitted activities = "kegiatan tertentu" set by the Director General | Ps. 86A(2)-(3) | Ps. 86A |
| Applied **from within Indonesia** by the foreigner, Penjamin, or Penanggung Jawab, via the application (evisa.imigrasi.go.id) | Ps. 94A(1) | Ps. 94A |
| **Eligibility (exhaustive list): (a) ITK holders whose ITK derives from a Visa on Arrival; (b) ITAS holders; (c) ITAP holders** | Ps. 94A(2); attachment list 94A(3)(b) repeats the same trio | Ps. 94A |
| **Filing deadline**: *"diajukan dalam jangka waktu paling lama 3 (tiga) hari sebelum Izin Tinggal yang dimiliki berakhir"* | Ps. 94A(4) | Ps. 94A |
| **Overstay shield**: application filed AND fee paid before old-permit expiry → no overstay counted if processing runs past it | Ps. 94A(5) | Ps. 94A |
| **Issuance within max 3 WORKING days after payment received**, delivered electronically | Ps. 94B(2)-(3) | Ps. 94B |
| Onshore-only; **voided if the holder leaves Indonesia** | *"Izin tinggal ini tidak berlaku lagi apabila WNA keluar wilayah Indonesia"* — official kanwil articles (Kupang, Depok), NOT located in the primary articles this session | popularization tier, 2 official sources |

### 3.2a The "revoked?" tension — RESOLVED from the primary text

The parallel session's bridging profile surfaced (first-hand, peraturan.go.id metadata) that
Permenkumham 11/2024 is marked **"Tidak Berlaku — Dicabut Oleh: Permen Imipas 3/2025"**, and flagged the
instrument's currency as CRITICAL/UNRESOLVED. The primary text of Permen Imipas 3/2025, on disk this
session, resolves it — **Pasal 45 (Ketentuan Penutup), verbatim**:

> *"Pada saat Peraturan Menteri ini mulai berlaku, ketentuan **Pasal 43, Pasal 45, Pasal 52, Pasal 53,
> Pasal 54, dan Pasal 55** Peraturan Menteri Hukum dan Hak Asasi Manusia Nomor 22 Tahun 2023 tentang
> Visa dan Izin Tinggal … sebagaimana telah diubah dengan … Nomor 11 Tahun 2024 …, **dicabut dan
> dinyatakan tidak berlaku**."*

A **partial revocation**: exactly six named articles of the 22/2023-as-amended framework (the old
repatriation/ex-WNI subject matter that 3/2025 supersedes) are revoked. **Pasal 86A, 94A and 94B — the
bridging articles — are not among them and remain in force.** The peraturan.go.id "Dicabut Oleh" banner
is database-level metadata rendering a partial revocation as if wholesale. Consistent with the kanwil
offices still actively promoting the bridging permit in 2026 and with the R2 delta's "highly active"
status. The parallel session's honest flag is hereby closed with a primary citation.

### 3.3 Two findings the popularizations get loose — load-bearing for the branch

**(a) Eligibility is narrower than the official popularizations reviewed this session state.**
Ps. 94A(2) lists exactly three source-statuses: **VOA-derived ITK, ITAS, ITAP**. An ITK deriving from a
C-series e-visa or from visa-free entry is NOT in the list (the operative fact is the list's silence;
no claim is made here about what those holders' alternative paths are). The kanwil articles say "ITK
holders" generically; the primary text does not. Product consequence: the branch MUST ask *how the
person entered* before offering bridging, and route non-VOA ITK holders to human review with honest
copy — never auto-offer, never auto-reject (a Dirjen-level implementing practice wider than the text
cannot be excluded from here; a person checks).

**(b) There are TWO distinct "3-day" rules; conflating them mis-routes people.**
1. **Filing deadline** (Ps. 94A(4), about the APPLICATION): *"paling lama 3 hari sebelum … berakhir"* —
   in isolation grammatically ambiguous (a misreading takes it as a last-3-days-only window). The
   official popularizations state the operational rule with the payment leg included: *"pembayaran
   biaya keimigrasian **paling lambat** 3 (tiga) hari sebelum masa berlaku izin tinggal sebelumnya
   habis"* — **a deadline at T-3, not an opening at T-3**. Precision kept: the primary clause governs
   filing; the payment phrasing is the kanwil gloss; Ps. 94A(5)'s overstay shield requires BOTH filed
   AND paid before expiry. The branch's operational rule — *file and pay no later than 3 days before
   expiry* — follows the official gloss, which is the authoritative operational resolution; the
   alternative literal parse (a window opening at T-3) is recorded as a linguistic note and rejected on
   the strength of the government's own popularizations, not silently ignored. Two stale artifacts of the
   opposite misreading remain upstream, flagged for their owners (outside this scope fence): bonifica
   Table 2's "filed ≤3 days before expiry" (PR #2602 branch) and one leftover "≤3 days" at
   product-design line ~462 contradicting that doc's own corrected §4.
2. **Service-time promise** (Ps. 94B(2)): issuance within 3 WORKING days after payment — a different
   clock. Outcome-card copy may cite it as expected turnaround; it is not the deadline.

### 3.4 The interview branch (content spec — construction deliverable of Phase 1)

Slot: onshore lane of Q0 (product-design §4 corrected lane table, restated with the boundary made
coherent):

| Days remaining | Lane | Bridging card? |
|---|---|---|
| already expired | overstay-help (human, reassuring) | never |
| 1-2 | urgent human review | never (window missed) |
| **exactly 3** | bridging-urgent, **human-review-first** (boundary case) | named as the likely path, not auto-offered |
| 4-7 | bridging-urgent | yes, card shown |
| 8-60 | extend-or-convert | shown when transition (not plain extension) is the goal |
| 60+ | planning | contextual mention |

**Entry conditions for the card (ALL must hold):** onshore = yes · days-to-expiry ≥ 4 (with the =3
boundary case above) · current status ∈ {VOA-derived ITK, ITAS, ITAP}, established by a **new required
question** — *"How did you enter Indonesia?"* (VOA / e-visa visit visa / visa-free / I already hold an
ITAS or ITAP) — Ps. 94A(2) makes it load-bearing · the goal is a NEW/different stay status, not a plain
extension (ITAS/ITAP holders whose permit "can no longer be extended" are the canonical users per both
kanwil articles).

**Boundary rule (honest limit of the sources):** the calendar-vs-working-days question IS resolved by
the primary text — the framework's definitions state *"Hari adalah hari kalender"* (def. 36), so
94A(4)'s "3 hari" are CALENDAR days (and the contrast with 94B(2)'s explicit "3 hari kerja" confirms
the drafters distinguish the two). Still genuinely open: filing-day inclusivity and the expiry
timestamp/timezone. Hence the conservative table above; those two boundary semantics stay an open
fact-registry item (§6). The tree must not pretend a precision the source doesn't have.

**Guards (route to human review with honest copy, never auto-reject, never auto-offer):** ITK from
C-series e-visa or visa-free entry → *"Bridging is defined by regulation for VOA, ITAS and ITAP
holders. Your situation has a path, but it needs a person."* · days < 3 or expired → existing
urgent/overstay lanes, bridging never named available · calling-visa nationality overlay (7 states, per
the corrected corner record) → human review.

**Outcome card (facts the card may state, each traceable to §3.2):** 60 days, one shot
(non-extendable); onshore-only and voided by ANY exit; overstay shield if filed+paid before expiry;
issuance typically ≤3 working days after payment; file+pay no later than 3 days before your current
permit expires; channel evisa.imigrasi.go.id.

**Microcopy register** (GLM lane grammar): countdown-aware, no alarm copy; the card leads with what the
permit protects (the gap), not with fear of overstay.

### 3.5 Price (owner's ruling applied)

**ONE all-inclusive client-facing price from PricingTool: IDR 3.500.000** — verified on-disk in BOTH
sources of truth: `bali_zero_official_prices_2026.json` → `services.single_entry_visas."Bridging
Visa".price = "3.500.000 IDR"`, and CRM `practice_types` seed (migration 148, `visa_bridging`,
base_price 3500000, 60 days, active). Never a PNBP/service-fee split on any client surface (Zero
ruling, corner LIVE STATE 2026-07-17). Official PNBP for the bridging ITK not pinned this session (§6)
— irrelevant to client surfaces under the ruling, open for the internal fact registry.

### 3.6 Existing-content liabilities found (flags, outside this file's scope fence)

1. `apps/mouth/src/content/articles/immigration/bridging-visa-indonesia.mdx` (+ .it/.id, published
   2026-03-17, `aiGenerated: true`, author "Exa: gilivisa.com") **conflates the Bridging Visa with
   VITAS/ITAS in general** — wrong per §3.1, live on balizero.com, contradicting the branch specified
   here. Recommended: rewrite from this fact base or unpublish. Owner: apps/mouth (Track A / site).
2. **The CRM product model carries the same conflation in miniature**: migration 148's comment calls it
   "a temporary single-entry visa" under category `single_entry_visa`. Legally it is a stay permit with
   no entry function that dies on exit. Price/duration right; category/comment = data-hygiene follow-up
   ticket (same class as the bonifica's EPO/ERP note).
3. Product-design line ~462 stale "≤3 days" phrase — §3.3(b).

## 4. Diaspora — COVERED at product level (definitive index closure gated on the Kepmen annex)

### 4.1 Primary source read — and the honest limit of what it proves

Full Permen Imipas 3/2025 PDF read (the close-out condition the bonifica listed). Mechanical result:
**the Permen contains ZERO visa index codes** (no E31*/E32* token in the extracted text; the only
"indeks" is "indeks prestasi", a GPA requirement) — products are defined by description; codes are
assigned by the Kepmen klasifikasi.

Logical limit, stated: Permen silence does not by itself prove the Kepmen assigned no new diaspora
indexes. What IS claimable on evidence: (1) every diaspora product the Permen defines has a semantic
counterpart in the confirmed catalog (§4.2); (2) the official GCI enumeration (§4.2a) names exactly 7
e-visa indexes, all in catalog; (3) no source touched by either session — flat list, 85-page crawl,
per-code probes, GCI press — surfaces any diaspora index outside E32/E31. Verdict: **covered at product
level, no counter-evidence of a missing code; definitive index-level closure requires the Kepmen annex**
(still WAF-blocked, §6).

### 4.2 Who is Diaspora (Ps. 1.6) and what products exist (Ps. 3)

Six categories: ex-WNI · descendants ≤2nd degree · spouse of ex-WNI · spouse of such a descendant ·
spouse of a WNI · child of a legal mixed marriage.

Products (all **Visa tinggal terbatas**, Ps. 3(2)) mapped onto the EXISTING catalog. Strength: **exact**
= duration+sponsor+wording align uniquely with the confirmed catalog label; **label** = the official
label collapses two Permen products into one code; **class** = maps to an existing catalog FAMILY, exact
sub-code not derivable without the Kepmen annex.

| Permen product (Ps. 3(2)) | Catalog code | Strength |
|---|---|---|
| a.1.a ex-WNI, with Penjamin, ≤2 yrs | E32C "VISA EKS WNI (MAKS 2 TAHUN)" | exact |
| a.1.b ex-WNI, no Penjamin, ≤1 yr | E32D "VISA EKS WNI (MAKS 1 TAHUN)" | exact |
| a.1.c ex-WNI, no Penjamin, ≤5 yrs | E32A "VISA EKS WNI" (5-yr row) | exact |
| a.1.d ex-WNI settling permanently | E32E "VISA REPATRIASI TINGGAL TETAP" | exact |
| a.1.e ex-WNI special skills, central-gov Penjamin | E32F "VISA REPATRIASI KEAHLIAN KHUSUS" | exact |
| a.2.a/b descendant ≤2°, 5 yrs / 10 yrs | E32B "VISA EKS WNI (DERAJAT 1 DAN 2)" | label |
| a.2.c descendant settling permanently | E32G "VISA KETURUNAN EX-WNI TINGGAL TETAP" | exact |
| a.2.d descendant special skills | E32H "VISA KETURUNAN EX-WNI KEAHLIAN KHUSUS" | exact |
| b.1 spouse of WNI | E31A row | class |
| b.2 spouse of repatriation-ITAS/ITAP holder | E31B-family | class |
| b.3 child of legal mixed marriage | E31C row | class |
| b.4 minor child joining repatriation-permit parent | E31E/F-family | class |

No Permen product lacks a counterpart. The "label"/"class" rows are exactly where the Kepmen annex
could refine assignment (sponsor type, dependency chain). All rows four-eyes-gated before RulePack
facts.

### 4.2a Corroboration adopted from the parallel session (verbatim-sourced there)

The parallel session's close-out independently pins the official GCI enumeration — *"E-visa GCI (indeks
E31A, E31B, E31C, E32E, E32F, E32G, E32H) terintegrasi dengan sistem perlintasan"* (kemenimipas.go.id
press release) — 7 codes, ALL already in catalog, and adds two facts adopted here with attribution:
(1) the **Dasar Hukum split** — per-code pages of E32C/E32D cite only the 22/2023 chain while
E32B/E/F/H cite Imipas 3/2025 — which independently corroborates treating fine-grained code assignment
as Kepmen/implementation-layer, not Permen-layer (§4.1); (2) the **GCI-vs-Golden-Visa branding trap**
(government UI groups E32A-D + E33 under "Golden Visa" while E32E-H + E31A/B/C are "GCI") — an
interview-design requirement: the flow must disambiguate the two programs explicitly. Both sessions'
diaspora verdicts agree in substance (their "CLOSED-COMPLETE at the GCI level" / this file's
"COVERED at product level, Kepmen-gated" — the residual difference is only how hard to state
index-level closure without the Kepmen annex).

### 4.3 Content-grade extras from the primary text (for the diaspora interview category later)

- Eligibility boundaries (Ps. 4): ex-WNI counted "sejak 17 Agustus 1945"; blood-line ≤2nd degree;
  exclusions — citizens of states formerly part of Indonesian territory, foreign civil-service /
  law-enforcement / intelligence / military service, separatism involvement, national-interest
  conflicts. Interview guard: exclusion triggers → human review, never auto-reject copy.
- One-application bundle (Ps. 42): the VITAS application simultaneously counts as application for ITAS,
  ITAS→ITAP status change, indefinite-ITAP extension, and re-entry permit; bundle issued at the TPI on
  arrival at the same time; **autogate**; onshore same-day indefinite-ITAP extension after status
  change — the "instant landing" story the official global-citizen landing markets (*"izin tinggal
  tetap tanpa batas waktu tanpa harus menanggalkan kewarganegaraan"*).
- ITAS durations (Ps. 23): sponsor-track 1-2 yrs; no-sponsor 1 yr / 5 yrs; settle-tracks 6-month
  VITAS-to-ITAP runway.

## 5. Impact on the bonifica (PR #2602 Table 2 — status after this file)

| Item | Was | Now | Basis |
|---|---|---|---|
| D7A, D7B | OPEN — conflicting evidence | **RESOLVED — both EXIST; 2 catalog rows proposed** (§2) | dual-tool body check + dead-code controls + live product directory + crawl slugs |
| D8A, D8B | not in Table 2 (undetected) | **NEW same-class gap — both EXIST; 2 rows proposed** (§2.3) | systematic corpus↔catalog diff + dual-tool live check |
| Bridging Visa | CONFIRMED GAP, facts from R2/press | **GAP CONFIRMED; fact base primary-grounded incl. partial-revocation resolution; branch spec delivered** (§3) | Permenkumham 11/2024 PDF + Permen Imipas 3/2025 Ps. 45 |
| Diaspora indices beyond E32 | OPEN | **COVERED at product level; index-level closure Kepmen-gated** (§4) | Permen Imipas 3/2025 PDF + GCI enumeration + corpus |

#2602 is OPEN and currently CONFLICTING (its `docs/AI_ONBOARDING.md` side, not the report); nothing here
depends on its merge, but Phase 2 of this track stays gated on it per the mandate.

## 6. Blockers / still open

- **Kepmen M.IP-08.GR.01.01/2025 PDF still unread** (kemenimipas.go.id WAF; not found on the BPK mirror
  this session). Gates: diaspora index-level closure (§4.1), the label/class mapping rows (§4.2), the
  bonifica's 4 ⚑ name-flags.
- **Bridging PNBP tariff not pinned.** PP 45/2024's lampiran is a scan; the official jakartapusat fee
  page has **no "peralihan" line** (checked live — nearest: Izin Tinggal Kunjungan 60 Hari =
  Rp 1.000.000/permohonan, plausibly the billed rate but an INFERENCE, not asserted). Client surfaces
  unaffected (§3.5); fact-registry item open.
- **Bridging T-3 residual boundary semantics** — days are CALENDAR days by primary definition (§3.4);
  still open: filing-day inclusivity and expiry timestamp/timezone. Handled conservatively; item open.
- **PricingTool MCP probe returned HTTP 401** this session — price verified from on-disk SSOT + 
  migration instead. Arsenal note, not a content blocker.
- Codex CLI on this host (v0.142.0) refuses the gpt-5.6 family ("requires a newer version") — review
  ran on gpt-5.5 xhigh; CLI upgrade is a fleet-maintenance item, not a content blocker.

## 7. §Solo-operatore

- Whether to productize D7A/D7B/D8A/D8B (Bali Zero prices for musician/crew/athlete/official visas) —
  business decision (Legge 5); no price invented here.
- The live mis-article and migration-148 category fix (§3.6) sit outside this PR's scope fence — Track
  A / follow-up ticket decisions.
- Everything else is content research; no operator action required to merge this file.

## 8. Parallel-session reconciliation (sibling work in this same worktree — untouched)

Mid-session, two untracked files by a parallel session appeared in this shared worktree (the broker
handed both sessions the same `research-visa-content` path — a live instance of the sibling-race
family): `2026-07-17-catalog-gaps-closeout-d7ab-diaspora.md` and
`2026-07-17-bridging-visa-branch-profile.md`. Per sibling discipline they are NOT modified, committed,
or discarded by this session. Substance reconciliation:

- **D7A/D7B — the one real conflict.** Their verdict ABSENT vs this file's EXISTS. Raw data identical
  (byte-for-byte page sizes, same heading-slot counts); divergence is signal choice — their two legs
  (specific-heading presence + generic-heading count) cannot distinguish live-uncurated from dead, and
  their negative controls were invented codes only. This session's body-marker leg + known-dead-code
  controls + today's product-directory listing resolve it: **EXISTS** (§2.1). Their honesty note that
  byte size does not discriminate is correct and is retained here.
- **Diaspora — agreement.** Their GCI 7-code enumeration and Dasar-Hukum split are adopted with
  attribution (§4.2a); verdicts substantively agree.
- **Bridging — their CRITICAL/UNRESOLVED revocation tension is resolved by this session's primary PDF**
  (partial revocation, Ps. 45 verbatim, bridging articles untouched — §3.2a). Their multi-kanwil
  source sweep (Jogja, Tasikmalaya, Jakarta Barat) is complementary to this file's primary-text table.
- **Process flag for the corner:** the task-id-collision that produced two parallel Track-B takes in
  one worktree is itself a finding (broker idempotency hands out shared worktrees); surfaced in the PR
  body for the corner's LIVE STATE (outside this file's scope fence).

## Adversarial review

R1 gate (generator≠grader): reviewer seat `codex`. GPT-5.6-sol and -terra were refused by the local CLI
(v0.142.0 "requires a newer version of Codex", both attempts recorded), so the passes ran on
**`gpt-5.5`, reasoning effort xhigh, `--sandbox read-only`**, a different model family from the
authoring session, attacking (a) the D7A/D7B EXISTS derivation, (b) the Ps. 94A eligibility narrowing
and the two-3-day-rules disentanglement, (c) the diaspora closure logic, plus internal consistency.
Honest history — two REFUTED passes, each answered with new evidence or upheld with fixes, then a final
pass on this text. Recorded condensed; full verbatim in the session log.

### Pass 1 — VERDICT: REFUTED (13 objections)

Strongest: (1) diaspora close-out a category error (Kepmen unread); (2) single invented negative
control can't characterize the CMS — SPECULATIVE stale/orphan alternatives unexcluded; (4) a cited
source still carried "filed ≤3 days"; (5) boundary math undefined; (7) an unsourced BVK claim; (11)
unstable catalog arithmetic; (12) migration-148 category conflation ignored; (13) review section
self-certified before any pass was recorded.

**Dispositions:** (2)+(3) answered with NEW evidence — known-dead-code controls (E23B, B211A → empty)
run after the pass; (1)(8)(9) upheld → verdict renamed and mapping strength column added; (4) upheld,
sharpened — the stale "≤3" found at product-design line ~462 and flagged; (5) upheld → conservative
boundary rule; (6)(7)(10)(11)(12) upheld → rephrased/cut/sourced/restated/recorded; (13) process
artifact, moot once recorded.

### Pass 2 (post-fix, same command) — VERDICT: REFUTED (12 objections)

Strongest, with dispositions each verified against evidence rather than conceded:

1. *Dead-code controls don't settle it (2 routes ≠ CMS-wide purge proof).* **PARTIALLY UPHELD** — the
   overclaiming word "settle" is gone; §2.1 now states what 2 controls prove (a purge behavior on the
   tested dead routes) and carries the residual risk explicitly, alongside two additional independent
   evidence lines (live product directory today; body-content semantics).
2. *The cited crawl files contain only chrome/nav, not product bodies.* **UPHELD, verified on disk** —
   the crawl evidence line is downgraded to exactly what it proves (official product URL slugs/names at
   crawl time); body evidence rests on this session's own live fetches (§2.1 honesty note, frontmatter).
3. *A sibling file in this worktree concludes the OPPOSITE (D7A/D7B ABSENT).* **UPHELD as a real
   conflict, then resolved** — the sibling file is real (found and read after the pass); raw data
   byte-identical, divergence is signal-choice; full reconciliation §2.1/§8, EXISTS stands on the
   body-marker + dead-code controls + today's product-directory listing.
4. *D7B "Visa D7" slip = template contamination evidence.* **RECORDED as residual caveat** in §2.1 —
   under the dead-code controls, mislabeled-but-populated is the signature of an uncurated live page,
   not of purged residue; carried into the RulePack gate rather than dismissed.
5. *Catalog arithmetic rests on the disputed premise.* **CONDITIONAL, stands with §2.1** — stated as
   the bonifica-frame arithmetic applying only with the EXISTS verdict.
6. *T-3 conversion of a filing rule via a payment gloss.* **UPHELD, precision added** — §3.3(b) now
   separates the filing clause (94A(4)), the payment gloss (kanwil), and the overstay shield's
   filed-AND-paid condition (94A(5)), and names the branch's rule the conservative composite.
7. *Boundary lane self-contradiction (≥3 vs ≥4).* **UPHELD, fixed** — single coherent lane table in
   §3.4 (=3 → bridging-urgent human-review-first; ≥4 → card).
8. *"Primary-text-grounded" overclaim (exit-void is popularization-sourced).* **UPHELD** — §3.2 row
   marks it explicitly; headline wording adjusted.
9. *Diaspora verdict still overreads lossy-list absence.* **UPHELD in wording** — verdict is now
   "covered at product level; index-level closure Kepmen-gated" with the three claimable evidence
   lines enumerated (§4.1), reinforced by the GCI official enumeration (§4.2a).
10. *"exact (label-level)" is an oxymoron; class rows aren't coverage proof.* **UPHELD** — strength
    values renamed (exact / label / class) and their meaning defined (§4.2).
11. *Global-citizen landing covers only E32E-H, not the whole table.* **UPHELED as scoping note** — it
    is cited only for the settle-track subset; the full-table evidence is the Permen enumeration + GCI
    press quote (§4.2a).
12. *Pass-2 verdict placeholder unfilled.* **Moot** — this section now records both passes and the
    final one below.

### Pass 3 (post-reconciliation) — VERDICT: REFUTED on 2 wording objections; ALL load-bearing claims explicitly NOT refuted

Verbatim core: *"1. The Bridging boundary semantics are falsely left open… Permenkumham 11/2024 defines
the term: 'Hari adalah hari kalender.' So 'calendar vs working days' is not unresolved… 2. The
filing-vs-payment fix still overclaims… ['file and pay no later than 3 days before expiry'] does not
satisfy the last-3-days-only reading; it relies on the official popularization/kanwil gloss."* And,
decisive for the substance: *"I did not refute the partial-revocation resolution: BPK now clearly
frames Permen Imipas 3/2025 as 'Mencabut sebagian' and names only Pasal 43, 45, 52, 53, 54, 55. I also
did not refute the D7A/D7B directory evidence; the official Imigrasi product directory currently lists
D7A/D7B/D8A/D8B."* — the reviewer's own checks independently confirm the partial revocation AND the
live directory listing of all four disputed codes.

**Dispositions (both objections UPHELD and fixed in place):** (1) verified on the primary text this
session (def. 36, *"Hari adalah hari kalender"*) — §3.4 boundary rule rewritten: calendar-days
resolved, only filing-day inclusivity + expiry timestamp remain open (§6 updated); the finding also
sharpens the two-clock contrast (94A(4) "hari" calendar vs 94B(2) "hari kerja" working). (2) "satisfies
every reading" struck — §3.3(b) now states the branch follows the official gloss as the authoritative
operational resolution and records the alternative literal parse as a rejected linguistic note.

### Pass 4 (fix-verification, scoped to the two pass-3 objections) — VERDICT: SURVIVES

Verbatim: *"1. §3.4 now correctly closes the calendar-vs-working-days issue… leaves open only
inclusivity plus expiry timestamp/timezone. 2. §6 honestly mirrors that narrowed residual blocker…
3. §3.3(b) no longer claims the file+pay rule 'satisfies every reading'… records the last-3-days-only
parse as a rejected linguistic note. 4. I don't see a new internal inconsistency from these fixes. The
`=3` lane remains human-review-first, while automatic card display starts at `≥4`, which is coherent
with the residual inclusivity uncertainty."*

Gate closed: two REFUTED passes answered with new evidence and fixes, a third pass whose only surviving
objections were wording-level (fixed and re-verified), and an explicit reviewer confirmation of the
load-bearing claims (partial revocation "Mencabut sebagian"; official directory currently listing
D7A/D7B/D8A/D8B). One procedural scar for the record: the first pass-4 attempt ran in the wrong
checkout (main instead of this worktree) and reported the file missing — re-run with the correct
workdir; recorded so the "file not found = REFUTED" artifact is not mistaken for a content verdict.
