---
date: 2026-07-21
domain: visa
client_case: none
sources:
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C12
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/D12
  - https://www.letsmoveindonesia.com/single-entry-pre-investment-visa-c12/
  - https://balivisaadvisor.com/services/multiple-entry-pre-investment-visa/
  - Permenkumham 22/2023 jo. Permenkumham 11/2024 tentang Visa dan Izin Tinggal (dasar hukum cited on both official pages)
status: verified
author: deep-researcher (Bali Zero)
adversarial_review: kimi-k3
---

# C12 vs D12 Visa — Verification of 5 Disputed Claims (Draft vs Reviewer)

## Question
Fact-check 5 disputed points between an AI-generated draft answer and a human
reviewer's un-sourced correction, for Indonesia's C12 (single-entry pre-investment
visit visa) and D12 (multiple-entry pre-investment visit visa). Feeds a live
client-facing WhatsApp assistant — precision over speed.

## TL;DR
- The DRAFT was substantially correct; the REVIEWER is wrong on 4 of 5 disputes and half-right on 1.
- Ground truth = the official DGI pages (imigrasi.go.id), verbatim, governed by Permenkumham 22/2023 jo. 11/2024.
- Key reversal vs reviewer: **C12 converts onshore to KITAS, D12 does not; C12 needs a sponsor, D12 does not; C12 funds = USD 2,000 (not 5,000).**

## Method / trust basis
Primary source is the national Directorate General of Immigration visa index pages
`imigrasi.go.id/wna/daftar-visa-indonesia/{C12,D12}`. To rule out a fetch-summary
hallucination, the raw HTML of both pages was pulled and the Indonesian sentences
below were extracted verbatim from that raw HTML (not from a model paraphrase). The
C12 page cites as legal basis **UU 6/2011 Keimigrasian, PP 31/2013, PP 45/2024 (PNBP
tariffs), Permenkumham 11/2024, and Permenkumham 22/2023 tentang Visa dan Izin Tinggal**;
the D12 page's *dasar hukum* list omits UU 6/2011 and PP 31/2013 (it cites PP 45/2024,
Permenkumham 11/2024 + 22/2023, Kepmen M.IP-08.GR.01.01/2025, and PMK 9/2022 + 82/2023)
— corrected 2026-07-21 after adversarial re-fetch, see Adversarial review below. Both
still reflect the current (2024→) index-visa regime, exactly the regulation the brief
asked to check against.

## Key citations (verbatim, official pages)

**C12 — `imigrasi.go.id/wna/daftar-visa-indonesia/C12`:**
- Entry + stay: *"Visa C12 merupakan Visa Kunjungan untuk **satu kali masuk** ke Indonesia dengan izin tinggal **maksimal 60 hari atau 180 hari**, dihitung sejak tanggal kedatangan."*
- Conversion: *"Izin Tinggal ini dapat diperpanjang dan **dapat dikonversikan menjadi Izin Tinggal Terbatas dengan penjamin yang sama**."*
- Extension: *"Anda dapat memperpanjang izin tinggal ini beberapa kali hingga maksimal 12 bulan."*
- Sponsor: *"Penjamin (Sponsor) — **Anda membutuhkan penjamin/sponsor untuk mengajukan visa ini.**"* / *"Penjamin (sponsor) harus memiliki akun di evisa.imigrasi.go.id sebelum mengajukan visa … penjamin dapat mengajukan visa C12 bagi Orang Asing."*
- Funds: *"bukti memiliki biaya hidup … sebesar **minimal USD2000** … rekening koran 3 bulan terakhir atas nama Orang Asing atau penjamin; atau slip gaji terbaru; atau deposito berjangka."*
- Fees (PNBP): *"Masa tinggal **60 Hari : Rp. 3.000.000,-**"* / *"Masa tinggal **180 Hari : Rp. 4.000.000,-**"*
- Supporting docs: surat permohonan + surat pernyataan penjamin, passport, proof of funds, pasfoto, **"Tiket kembali"** (return ticket), + institutional letter/invitation. **No CV, no travel itinerary listed.**

**D12 — `imigrasi.go.id/wna/daftar-visa-indonesia/D12`:**
- Entry + stay: *"Visa D12 merupakan Visa Kunjungan untuk **beberapa kali masuk** ke Indonesia dengan izin tinggal **maksimal 180 hari setiap kedatangan**."*
- Conversion: *"Izin tinggal dari visa ini bisa diperpanjang untuk 180 hari berikutnya **namun tidak bisa dialihkan menjadi izin tinggal terbatas**."*
- Extension: *"Anda dapat memperpanjang izin tinggal ini satu kali hingga keseluruhan masa tinggal paling lama 12 bulan (1 tahun) atau 2 tahun, bergantung pada durasi visa yang Anda pilih."*
- Sponsor: *"Penjamin (Sponsor) — **Anda tidak membutuhkan penjamin/sponsor untuk mengajukan visa ini.** Orang asing harus memiliki akun di evisa.imigrasi.go.id sebelum mengajukan visa."* (NB: the same page's extension clause says renewal *"dapat dilakukan secara online oleh sponsor"* and billing occurs *"setelah pengajuan visa oleh sponsor"* — DGI boilerplate that is internally inconsistent with the "no sponsor" line above; the "not required" claim is scoped to the **initial application** only, see Adversarial review.)
- Funds: *"rekening koran 3 bulan terakhir atas nama Orang Asing atau penjamin **sebesar minimal USD5000**."*
- Supporting docs: passport, proof of funds, pasfoto, **"curriculum vitae, rencana perjalanan (travel itinerary)"**, + institutional letter/invitation. **CV and itinerary ARE required. No return ticket is listed** (corrected 2026-07-21 — see Adversarial review).

## Findings — verdict per dispute

### Dispute 1 — Onshore KITAS conversion → **CONFIRMED-DRAFT**
Draft: C12 can convert onshore to KITAS (same sponsor); D12 cannot ("tidak bisa dialihkan").
Official pages match the draft verbatim: C12 *"dapat dikonversikan menjadi Izin Tinggal Terbatas dengan penjamin yang sama"*; D12 *"tidak bisa dialihkan menjadi izin tinggal terbatas"*. The reviewer's *"D12 JUGA BISA KONVERSI KE KITAS"* is **not supported by the regulation**. (Practice caveat in Disagreements below.)

### Dispute 2 — C12 stay-length options → **CONFIRMED-DRAFT**
Draft: C12 lets you choose 60 days or 180 days, each with its own government fee.
Official: *"izin tinggal maksimal 60 hari atau 180 hari"* + two PNBP tiers (Rp 3,000,000 for 60 days / Rp 4,000,000 for 180 days). The reviewer's *"C12 TIDAK ADA OPSI 60 HARI"* is **wrong** — the 60-day tier exists and is distinctly priced.

### Dispute 3 — Proof of funds + CV/itinerary → **PARTIALLY-BOTH**
- Funds: **Draft correct.** C12 = **USD 2,000**; D12 = **USD 5,000** (both verbatim). The reviewer's *"C12 sama minimal saldo akhir 5000 usd"* is **wrong** — C12 is USD 2,000, not 5,000.
- CV/itinerary: **Reviewer's directional point correct.** C12 does **not** list a CV or travel itinerary (it requires a return ticket); D12 **does** require *"curriculum vitae, rencana perjalanan (travel itinerary)"*. So "the documentary difference is CV + itinerary" is a real difference — but it is D12 that carries the heavier documents, and it does **not** make the funds equal.

### Dispute 4 — Sponsor requirement → **CONFIRMED-DRAFT**
Draft: only C12 requires a sponsor from the start (filed BY the sponsor); D12 has no mandatory personal guarantor for the initial application.
Official: C12 *"Anda membutuhkan penjamin/sponsor"* (and the sponsor is the party who submits the C12); D12 *"Anda tidak membutuhkan penjamin/sponsor untuk mengajukan visa ini"* (the foreigner applies via their own account). The reviewer's *"DUA DUANYA … PERLU PENJAMIN/SPONSOR"* is **wrong for D12**. (Note the confusion source: D12 still requires institutional correspondence — see Disagreements.)

### Dispute 5 — C12 60-day fee/extension tier → **CONFIRMED-DRAFT** (same root as Dispute 2)
Official PNBP explicitly lists a 60-day tier (Rp 3,000,000) distinct from the 180-day tier (Rp 4,000,000). The reviewer's *"TIDAK ADA PERPANJANGAN 60 HARI"* is **wrong**. Precision: 60 and 180 days are two **initial-stay** options; both are then extendable up to 12 months total — so "no 60-day option" fails on both the initial-stay and the fee facts.

## Disagreements / open questions
- **The reviewer, an experienced practitioner, contradicts the official pages on 4/5 points.** Two likely causes, worth flagging before this overwrites their knowledge base:
  1. **D12 → KITAS (highest stakes).** The regulation is precise: the D12 *stay permit* cannot be **alih-status** (onshore-converted) into an ITAS/KITAS — only C12's can. This does **not** mean a D12 holder can never obtain a KITAS: after setting up a PT PMA they can still get an **Investor KITAS**, but by applying for a **new** KITAS (fresh telex/e-visa), not by converting the D12 permit in place. The reviewer likely conflated "you can end up on a KITAS after a D12" (true in practice) with "the D12 permit converts onshore" (false per regulation). **Recommend Bali Zero confirm the exact live mechanism on a recent D12→Investor-KITAS case before hard-coding either extreme into client answers.**
  2. **D12 "sponsor".** The official page says no penjamin/sponsor is required, yet D12 still requires *"surat keterangan, undangan, atau korespondensi dari instansi pemerintah atau lembaga swasta"* (an institutional letter/invitation). Agents routinely collapse this into "you need a sponsoring company," which is the probable origin of the reviewer's belief.
- **Agent-site divergence.** Several agent websites (and the reviewer) still quote **USD 5,000 for C12** and "sponsor required for D12." These appear to lag the current official page (USD 2,000 / no D12 sponsor). Treat imigrasi.go.id as controlling; treat agent-site figures as stale until re-confirmed.
- The regional immigration mirror (ponorogo.imigrasi.go.id) and one 2026 agent guide were unreachable (503/500) at check time; the national page + raw-HTML extraction + partial agent corroboration (60/180 structure) were sufficient.

## Corrected reference table — C12 vs D12 (current, per Permenkumham 22/2023 jo. 11/2024)

| Attribute | C12 (Single-entry pre-investment) | D12 (Multiple-entry pre-investment) |
|---|---|---|
| Entry type | Single entry | Multiple entry (valid 1 or 2 years) |
| Initial stay | **60 or 180 days** (choose at application) | 180 days **per entry** |
| Extension | Extendable multiple times, up to **12 months** total | Extend **once**, +180 days; total up to 12 months (1-yr visa) or 2 years (2-yr visa) |
| Onshore → KITAS (alih status) | **YES** — "dapat dikonversikan menjadi Izin Tinggal Terbatas dengan penjamin yang sama" | **NO** — "tidak bisa dialihkan menjadi izin tinggal terbatas" (must leave + apply new KITAS) |
| Proof of funds (min.) | **USD 2,000** (3-mo statement / payslip / time deposit) | **USD 5,000** (3-mo bank statement) |
| Sponsor / penjamin | **Required** — sponsor holds the evisa account and files the application | **Not required** — foreigner applies via own account (but institutional letter/invitation still needed) |
| CV + travel itinerary | **Not required** (return ticket required) | **Required** (curriculum vitae + rencana perjalanan) |
| Government fee (PNBP) | Rp 3,000,000 (60-day) / Rp 4,000,000 (180-day) | Per official D12 PNBP schedule (1-yr / 2-yr tiers) |
| Visa validity (entry window) | 90 days from issuance | From issuance date |
| Legal basis | Permenkumham 22/2023 jo. 11/2024; UU 6/2011; PP 31/2013; PP 45/2024 | Permenkumham 22/2023 jo. 11/2024; PP 45/2024 (page omits UU 6/2011 + PP 31/2013) |

## Checklist for action (Bali Zero)
- [ ] **Fix the KB / bot answers** to: C12 converts onshore to KITAS, D12 does **not**; C12 needs a sponsor, D12 does **not**; C12 funds = **USD 2,000** (not 5,000); C12 has 60-day AND 180-day tiers.
- [ ] **Reconcile with the reviewer** in person — show them the two verbatim official quotes (D12 "tidak bisa dialihkan"; D12 "tidak membutuhkan penjamin/sponsor") since their correction was repeated across 4 answers and will otherwise re-enter the KB.
- [ ] **Confirm the real-world D12 → Investor-KITAS path** on a recent live case (new-KITAS-application vs in-place conversion) and document the exact mechanic before any client relies on "D12 cannot become a KITAS."
- [ ] **Purge stale USD 5,000 / "D12 needs sponsor" figures** from any agent-sourced snippets in the KB; pin the imigrasi.go.id pages as the citation.

## Adversarial review

Reviewed by an independent seat (Kimi K3, `kimi-code/k3`) after this document was
drafted — the seat re-fetched both official pages (including raw HTML) itself rather
than reviewing the text-pack, and attempted to refute the 5 central claims plus the
verbatim-quote fidelity.

**Verdict: all 5 central claims independently re-confirmed verbatim against a fresh
fetch of imigrasi.go.id/C12 and /D12 — none refuted.** 4 minor objections survived,
none touching a central claim; all 4 have been fixed in this document (fixes applied
2026-07-21, reflected above):

1. The D12 "supporting docs" bullet asserted a return ticket was required — the
   official D12 document list has no such item (the only "tiket kembali" on the page
   is unrelated stateless-persons boilerplate). Fixed: removed.
2. The Method section claimed "both pages" cite UU 6/2011 + PP 31/2013 as legal
   basis — the D12 page's own *dasar hukum* list omits both. Fixed: legal-basis
   claim now scoped per-page.
3. The D12 extension quote was presented as verbatim with a bracketed `[2 tahun]`
   insertion that silently truncated the source's trailing clause
   ("...bergantung pada durasi visa yang Anda pilih"). Fixed: quote now exact.
4. The D12 page's own boilerplate mentions a "sponsor" for extensions/billing even
   though no sponsor is needed for the initial application — this document's "no
   sponsor" claim is correct but didn't flag the source page's internal
   inconsistency, which is plausibly part of the reviewer's original confusion.
   Fixed: noted inline at the D12 sponsor citation.

Everything else the seat probed — sponsor-quote verbatim fidelity (re-verified
against raw HTML), USD figures, conversion rules, visa code identities, 60/180-day
fee tiers — was independently re-confirmed, not merely re-asserted.

## Sources
1. Official DGI — C12: https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C12 (raw HTML fetched + verbatim-extracted 2026-07-21)
2. Official DGI — D12: https://www.imigrasi.go.id/wna/daftar-visa-indonesia/D12 (raw HTML fetched + verbatim-extracted 2026-07-21)
3. Legal basis cited on both pages: Permenkumham 22/2023 jo. Permenkumham 11/2024 tentang Visa dan Izin Tinggal; UU 6/2011; PP 31/2013; PP 45/2024 (PNBP)
4. LetsMoveIndonesia C12 (corroborates 60→180 stay structure): https://www.letsmoveindonesia.com/single-entry-pre-investment-visa-c12/
5. Bali Visa Advisor D12 (multiple-entry, 180/entry): https://balivisaadvisor.com/services/multiple-entry-pre-investment-visa/
6. Divergence check — agent sites quoting USD 5,000 for C12 (now stale vs official USD 2,000): visas-indonesia.com, gayabalivisa.com, lmiconsultancy.com
