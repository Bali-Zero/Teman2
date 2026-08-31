---
date: 2026-08-31
domain: visa
topic: e-VOA / VOA government fee (PNBP) — contested figure reconciliation
sources: primary (imigrasi.go.id, evisa.imigrasi.go.id, peraturan PP 45/2024 PDF) + secondary (Indonesian news outlets, DNS lookup)
---

## VERDICT (read this first)

1. **Official PNBP fee for the 30-day Visa Kunjungan Saat Kedatangan (VOA / e-VOA, index B1), currently in force as of 31 August 2026, is IDR 500,000 (Rp 500.000).** Legal basis: **Peraturan Pemerintah (PP) Nomor 45 Tahun 2024**, "Jenis dan Tarif atas Jenis Penerimaan Negara Bukan Pajak yang Berlaku pada Kementerian Hukum dan Hak Asasi Manusia" — Section III.B.1.c ("Visa Kunjungan Paling Lama 30 Hari … Rp 500.000,00"), signed/promulgated 18 Oct 2024, effective 60 days later (~17 Dec 2024). The extension (Izin Tinggal Kunjungan, 30 days) is the same figure, Rp 500.000, under Section III.C.1.c of the same PP.
2. **Both contested lanes were partially right for the wrong reason.** The lane that said evisa.imigrasi.go.id "carries no fee figure at all" was correct only for the **bare root URL** (`https://evisa.imigrasi.go.id` returns HTTP 200 with a literal **empty body**, confirmed by raw curl). The fee figure lives on an inner page, `https://evisa.imigrasi.go.id/front/info/evoa`, which states in raw HTML: *"The Visitor Visa fee is IDR 500.000,00."* The lane that asserted Rp 500.000 was correct on the number and on attributing it to Indonesian Immigration.
3. **Caveat, live and important for 31 Aug 2026**: on 12 August 2026 the Director General of Immigration (Hendarsam Marantoko) publicly announced a **plan** to raise the fee to a two-tier Rp 750.000 (e-VOA applied online pre-arrival) / Rp 1.000.000 (arranged manually on arrival). As of the date of this research (31 Aug 2026, confirmed by re-fetching the live official pages the same day), this is **not yet enacted** — no amending PP has been found, and both official portals (evisa.imigrasi.go.id and imigrasi.go.id) still show Rp 500.000. Treat Rp 500.000 as the figure in force, but flag the pending revision to Zero/the page copy as a known near-term risk.
4. **`molina.imigrasi.go.id` is confirmed NXDOMAIN** (direct `dig`/`nslookup`, no A record, SOA-only NXDOMAIN response from `imigrasi.go.id`'s own nameservers). "MOLINA" is not a live subdomain — it is the **internal application name** of the eVisa system itself: the raw HTML of `evisa.imigrasi.go.id`'s own pages carries `<meta property="og:site_name" content="MOLINA">`. So a Yogyakarta office page calling `molina.imigrasi.go.id` "the only official e-VOA site" is citing a dead/wrong hostname for a real system whose actual live home is `evisa.imigrasi.go.id`.

---

## Evidence

### A. The official fee figure — primary sources, fetched live 31 Aug 2026

**1. `https://evisa.imigrasi.go.id/front/info/evoa`** (the official eVOA info page, part of the DGI's own eVisa portal)
- Fetched via `curl` (raw HTML, 85,993 bytes, HTTP 200).
- Exact quote found in the raw HTML: *"The Visitor Visa fee is IDR 500.000,00. Please note that every payment via Debit/Credit Card will in[cur additional fees]…"*
- Also repeated in the page's FAQ block.
- Note: `https://evisa.imigrasi.go.id` (bare root, no path) returns HTTP 200 with a **0-byte body** — this is the URL that produces "no fee figure at all" if that's the only page fetched. This explains, without contradiction, why one research lane reported no number.

**2. `https://www.imigrasi.go.id/wna/daftar-visa-indonesia/B1`** (Directorate General of Immigration's own visa-index catalog page for B1 — Visa Kunjungan Wisata)
- Fetched via `curl` (raw HTML, 60,006 bytes, HTTP 200).
- Exact quote: *"Biaya visa B1 Rp 500.000 (untuk 30 hari)"*
- Same page cites its legal basis verbatim: *"Peraturan Pemerintah Nomor 45 tahun 2024 tentang Tarif PNBP di Lingkungan Kementerian Hukum dan HAM RI"*
- Also lists: *"Biaya Verifikasi I/II Rp 0"* (verification fee for this visa class is zero) and cites two further instruments (PMK 9/PMK.02/2022 and PMK 82/2023 for "kebutuhan mendesak"/urgent-service surcharges — a distinct, separate fast-track charge, not the base fee).

**3. Peraturan Pemerintah Nomor 45 Tahun 2024** ("JENIS DAN TARIF ATAS JENIS PENERIMAAN NEGARA BUKAN PAJAK YANG BERLAKU PADA KEMENTERIAN HUKUM DAN HAK ASASI MANUSIA") — the actual regulation, downloaded as PDF from `https://jogja.imigrasi.go.id/wp-content/uploads/2025/02/PP-Nomor-45-Tahun-2024-tarif-baru-keimigrasian_compressed.pdf` and text-extracted locally with `pdftotext -layout` (OCR-quality text, digits occasionally rendered as O/0 confusion but unambiguous in context).
- Section **III. PELAYANAN KEIMIGRASIAN → B. VISA → 1. Visa Kunjungan**:
  - a. 7 hari — Rp 250.000
  - b. 14 hari — Rp 350.000
  - **c. 30 hari — Rp 500.000,00** ← this is the line item that both VOA-at-airport and e-VOA draw on; the PP does not carve out a textually separate "Saat Kedatangan" sub-category — the on-arrival/e-VOA distinction is an operational channel (per DGI's own B1 catalog page), not a separate PNBP tariff line.
  - d–f. 60/90/180 hari — Rp 1.000.000 / 1.500.000 / 2.000.000
- Section **III. PELAYANAN KEIMIGRASIAN → C. IZIN KEIMIGRASIAN → 1. Izin Tinggal Kunjungan** (the stay-permit/extension mechanism a VOA-holder converts into):
  - **c. 30 hari — Rp 500.000,00** — i.e. the 30-day extension carries the identical figure, Rp 500.000, not a different number.
- Signature block: *"Ditetapkan di Jakarta pada tanggal 18 Oktober 2024 … PRESIDEN REPUBLIK INDONESIA, JOKO WIDODO"*; *"Diundangkan di Jakarta pada tanggal 18 Oktober 2024 … LEMBARAN NEGARA REPUBLIK INDONESIA TAHUN 2024 NOMOR 240."*
- Transitional clause: *"Peraturan Pemerintah ini mulai berlaku setelah 60 (enam puluh) hari terhitung sejak tanggal diundangkan"* → effective date ≈ 17 December 2024 (matches multiple secondary sources' "berlaku 17 Desember 2024").
- This PP explicitly superseded the prior PP 28/2019 tariff schedule (per secondary sources; not independently verified against PP 28/2019's own text in this pass).

### B. Three things kept apart, as instructed

| Item | Amount | Basis |
|---|---|---|
| VOA paid at the airport counter (manual) | Rp 500.000 | PP 45/2024 §III.B.1.c, same line as below — the PP does not price the manual/airport channel differently from the online channel today |
| e-VOA applied for online before travel | Rp 500.000 | Same PP line; imigrasi.go.id's B1 page and evisa.imigrasi.go.id's own page both state Rp 500.000 with no channel-based split as of this fetch |
| 30-day extension (perpanjangan) | Rp 500.000 | PP 45/2024 §III.C.1.c, "Izin Tinggal Kunjungan Masa Berlaku Paling Lama 30 Hari" |

**All three are currently the same number, Rp 500.000, under the regulation in force.** The channel-based split (Rp 750.000 online / Rp 1.000.000 manual) that several August 2026 news reports describe is a **proposal**, not yet reflected in a PP or on the official portals — see §C below. Conflating "proposed new split" with "current fee" is exactly the trap the task warned about.

### C. Live tariff-revision signal (2026) — why this matters for "as of 31 Aug 2026"

- 12 August 2026: Director General of Immigration Hendarsam Marantoko announced at a press briefing a plan to raise the VOA fee, splitting it by channel: e-VOA (applied online, pre-arrival) → **Rp 750.000**; VOA arranged manually on arrival → **Rp 1.000.000**. Multiple independent Indonesian outlets carried this the same week: `kompas.com` (nasional and travel desks), `bisnis.com`, `cnnindonesia.com`, `rri.co.id`, `tirto.id`, `antaranews.com`, `liputan6.com`, `tribunnews.com`. Stated rationale: the current Rp 500.000 figure is considered too low given rupiah exchange-rate movement, and the differential is meant to push travelers toward e-VOA to reduce airport queues.
- SECONDARY analysis source `royalvisa.id` (a visa agency, title: *"Indonesia May Raise Its VOA Fee To Rp1 Million—But Not Yet"*) makes the "not yet in force" reading explicit: *"The VOA fee increase is a reported government plan, not an effective tariff… That is a policy plan reported from a media briefing. It is not the same thing as a new tariff already in force."*
- I could not find, in this pass, any amending PP, Permenkumham, or DGI circular that has actually put the Rp 750.000/1.000.000 figures into force. Both `evisa.imigrasi.go.id/front/info/evoa` and `imigrasi.go.id/wna/daftar-visa-indonesia/B1` were re-fetched live on 31 Aug 2026 (same day as this research) and both still show **Rp 500.000**, consistent with the "plan, not yet enacted" reading.
- **Practical implication for our own page copy**: print Rp 500.000 as current, but this is a live, dated risk — a follow-up check in the following weeks is warranted before this figure is treated as durable.

### D. `molina.imigrasi.go.id` DNS check

```
$ dig molina.imigrasi.go.id
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN
;; AUTHORITY SECTION:
imigrasi.go.id.  495  IN  SOA  ns-55.awsdns-06.com. awsdns-hostmaster.amazon.com. ...

$ nslookup molina.imigrasi.go.id
** server can't find molina.imigrasi.go.id: NXDOMAIN
```
Confirmed independently via two tools (`dig`, `nslookup`) against the Tailscale-provided resolver (100.100.100.100): **NXDOMAIN, no A/AAAA record.** The other lane's finding is correct.

Additional context found in this pass (not asked for, but explains the confusion): the live eVisa portal's own HTML carries `<meta property="og:site_name" content="MOLINA">` on the `/front/info/evoa` page. "MOLINA" is the **name of the software system**, not a hostname — it appears the DGI's own regional office page (Yogyakarta) that calls `molina.imigrasi.go.id` "the only official e-VOA site" is misremembering/mistyping the system's internal name as if it were the domain. The actual, live, working home of that system is `evisa.imigrasi.go.id`.

---

## What I could not verify

- **No amending regulation for the Rp 750.000/1.000.000 proposal was located** — I searched Bahasa Indonesia terms for a 2025/2026 revision PP and found only press-briefing coverage, no promulgated instrument. This may mean it genuinely hasn't been enacted yet (most likely, given the "Bakal Naik"/"will rise" framing in every headline checked), or it may mean the amending PP exists but hasn't been indexed by the search surfaces I used. Recommend a direct check of `peraturan.bpk.go.id` and `jdih.imigrasi.go.id` closer to publish time if this page ships after early-to-mid September 2026.
- **`kanimbatam.kemenkumham.go.id`** (a regional immigration-office tariff page cited in search results as carrying a full PNBP table) returned `getaddrinfo ENOTFOUND` — could not be fetched to cross-check. Not load-bearing since the DGI headquarters page (`imigrasi.go.id/wna/daftar-visa-indonesia/B1`) and the PP text itself both independently corroborate Rp 500.000.
- **Whether PP 45/2024's Section III.B.1 table has a distinct, separately-numbered "Visa Kunjungan Saat Kedatangan" line elsewhere in the ~20-page document** — I grepped for the literal phrase "Saat Kedatangan" in the extracted PP text and got zero hits. The operational "on-arrival vs pre-arrival online" distinction appears only on DGI's website copy (B1 catalog page), not as a separately priced PP line item. I could not fully rule out a "Saat Kedatangan" line existing elsewhere in the regulation under OCR-garbled text that my grep missed, though a full manual read of the 2,960-line extracted text's VISA section (lines ~1690–1800) found no such heading.
- **Whether the Rp 0 "Biaya Verifikasi I/II"** on the B1 page and the PMK 9/2022 and PMK 82/2023 "kebutuhan mendesak" (urgent-service) surcharges ever apply to a standard e-VOA/VOA transaction** — not investigated; flagged only because the B1 page cites them alongside the base fee and a naive reader could double-count them into "the government fee."
