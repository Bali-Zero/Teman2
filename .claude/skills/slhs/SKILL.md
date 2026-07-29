---
name: slhs
description: SLHS corner — the live shared context for the Sertifikat Laik Higiene Sanitasi vertical (food-hygiene certification as a Bali Zero product, owner Krisna). Load BEFORE touching any SLHS content, pricing, page, or client-facing claim — or when Zero says /slhs, "hygiene certificate", "laik higiene", "laik sehat". Holds: what is VERIFIED vs merely believed, the live-defect list, the phase plan F0-F6, and the blood-bought rules from the 2026-07-29 research.
---

# /slhs — Sertifikat Laik Higiene Sanitasi as a Bali Zero product

> **Owner: Krisna** (Executive Consultant, setup, LKPM cycle owner). Third project corner after
> `/garuda_voa` (Surya) and `/secondhome` (Ari). Opened 2026-07-29.
>
> **North star:** be the only operator in Bali that sells a food-hygiene certificate **honestly** —
> transparent price, a pre-inspection that tells the client the truth about their kitchen, and a
> renewal that arrives before the expiry, not after the fine.

---

## 0. What this vertical is

SLHS is the health certificate a food business must hold to operate legally. It is **not a
standalone permit**: it is a **PB-UMKU** (_Perizinan Berusaha untuk Menunjang Kegiatan Usaha_) hung
off an existing NIB inside OSS-RBA. The client must already have a NIB; SLHS is filed against it.

Three consequences that shape everything:

1. **We sell to businesses that already exist** — not to new incorporations. The buyer is a running
   restaurant, not a founder.
2. **The government fee is Rp 0.** What we sell is not access; it is _passing the inspection on the
   first attempt_, and _not forgetting the renewal_. Price honesty is therefore a product feature,
   not a marketing choice — see §6.
3. **It expires in 3 years.** It is a cycle, not a transaction — structurally the same shape as the
   LKPM cycle Krisna already owns.

---

## 1. Where the truth lives (in order)

1. **This file** — state, decisions, phase plan.
2. **`research/compliance/2026-07-29-slhs-lane-f-primary-text.md`** — the ONLY source for regulation
   numbers. Verbatim `pdftotext` extractions with page numbers and reproducible commands. **If a
   number is not in Lane F, it is not verified.**
3. `research/compliance/2026-07-29-slhs-lane-a-regulatory.md` (PR #3447) — regulatory chain, the
   3-tier certificate finding. Good on structure; **its KBLI lists were wrong twice** — do not cite
   its code numbers.
4. `research/compliance/2026-07-29-slhs-lane-b-procedura.md` (PR #3443) — the operational flow,
   costs, bottlenecks, and 11 declared field gaps.
5. `research/compliance/2026-07-29-slhs-lane-c-market.md` (PR #3442) — competitors, prices, white
   space. Codex-reviewed; read its own caveats, they are load-bearing.
6. `research/compliance/2026-07-29-slhs-lane-d-internal-audit.md` (PR #3444) — what we own.
7. `research/compliance/2026-07-29-slhs-lane-e-demand.md` (PR #3445) — the demand signal.
8. `research/compliance/2026-07-29-slhs-lane-g-why-now.md` (PR #3448) — why the signal appeared.
9. `data/source_documents/KBLI_2025_FINAL_CLEAN.json` — **the arbiter for every KBLI code.**
   Field is `kode_kbli_2025` (not `kode_kbli`). 1,559 codes.

---

## 2. Verified facts (method stated; do not regress)

| #   | Fact                                                                                                                                                                                                    | How it was verified                                                                                                                               |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Validity = 3 (tiga) tahun** from issue date                                                                                                                                                           | Verbatim from the certificate-template Lampiran: _"Sertifikat Laik Higiene Sanitasi ... berlaku selama 3 (tiga) tahun sejak tanggal diterbitkan"_ |
| 2   | **Sanctions = PP 28/2024 Pasal 251-252** — teguran lisan → tertulis → penghentian sementara → pencabutan izin                                                                                           | Verbatim `pdftotext`. Note: the pasal does **not** name "SLHS"/"TPP"; it is the umbrella kesehatan-lingkungan clause                              |
| 3   | **PP 66/2014 abrogated by PP 28/2024 Pasal 1169 huruf q**                                                                                                                                               | Verbatim, BAB XIII Ketentuan Penutup                                                                                                              |
| 4   | **The SLHS Lampiran names exactly SIX KBLI codes**: 56101 Restoran · 56210 Event Catering · 56290 Jasa Boga Periode Tertentu · 10391 Tempe · 10392 Tahu · 11052 Depot Air Minum                         | Verbatim, Permenkes 14/2021 PDF page 1682, `pdftotext -layout -f 1682 -l 1682`                                                                    |
| 5   | Of those six, **10391 and 10392 do not exist in KBLI 2025**; the other four do                                                                                                                          | Direct lookup in `KBLI_2025_FINAL_CLEAN.json`                                                                                                     |
| 6   | **Government filing fee = Rp 0** (Denpasar, Perwali 16/2014); official Denpasar SLA = **7 working days**                                                                                                | Dinkes Denpasar official page + independent national confirmation                                                                                 |
| 7   | **Realistic all-in cost**: DIY floor ≈ Rp 500k–3jt (lab + one staff certificate). Agencies charge Rp 8.5jt–22jt. Documented broker markup on an adjacent program: Rp 9–30jt against a ~Rp 2jt real cost | Triangulated across city-government page, bahasa explainer, and a national investigative piece                                                    |
| 8   | **Our client book holds 36 companies on KBLI 56101** — the only code in our book that the Lampiran actually names                                                                                       | `SELECT ... FROM companies WHERE kbli_code LIKE '56%'` on live Postgres                                                                           |
| 9   | **Zero SLHS practices ever** (0 of 749) and **no `practice_types` entry** — structurally undefined as a service line                                                                                    | Live Postgres                                                                                                                                     |
| 10  | **Demand is real, organic, and new**: 0 messages/month 2022→May 2026, then June = 10, July = 19, across 10 distinct clients                                                                             | Live WA mirror on Pro (94k+ rows), aggregate counts only                                                                                          |
| 11  | **No competitor sells proactive renewal**; **no Bali-specific, price-transparent standalone SLHS page exists** in either language across ~25 sources                                                    | Lane C, Codex-reviewed                                                                                                                            |
| 12  | **`56101-2025` merges the old Restoran AND the old Warung Makan** — so the certificate tier is **not derivable from the KBLI code**                                                                     | `bps_2020_ancestors.codes` reverse index                                                                                                          |

### The 3 certification tiers (Lane A; structure CERTAIN, boundaries not fully verified)

- **Full SLHS** — restaurants, catering, depot air minum, tempe/tahu.
- **Label Pengawasan/Pembinaan HSP** — lighter, for warung/kantin/street vendors.
- **SLS (Sertifikat Laik Sehat)** — a _separate_ certificate for hotels, recreation, entertainment.
  ⚠️ **Hotels and villas do NOT need SLHS.** Any pitch that sells SLHS to a villa is wrong.

---

## 3. What is NOT verified (do not assert these)

1. **Which KBLI codes beyond the six actually trigger the obligation in OSS.** The Lampiran names six.
   Our website currently claims eight, including cafés, bars, nightclubs and warungs — **unverified
   and probably wrong** (see §4).
2. **Per-kabupaten fees and SLA for Badung, Gianyar, Tabanan, Buleleng** — only Denpasar is confirmed.
   88 of our 161 hospitality clients sit in Badung + Gianyar. This is the most valuable field gap.
3. **The cost of the PKP course for a private company.** The government course (UPTD Bapelkesmas
   Provinsi Bali) publishes no fee; a private BNSP/HACCP alternative runs Rp 6–11.8jt/participant.
   The two are not the same product. Unresolved.
4. **The IKL scoring weights** — the official form is an image-only scan; needs OCR.
5. **Whether a PHRI recommendation letter is still required.**
6. **The KBLI 2020↔2025 bridge**: 1,338 of 1,559 codes carry ancestors, but **100% are
   `mechanical-only` / `not-adjudicated`** — a wide bridge nobody has audited.
7. **Why demand appeared in June 2026.** Best hypothesis: the national MBG/SPPG food-poisoning
   scandal (37k+ victims; Komnas HAM naming SLHS completeness on 15 June; 833 kitchens closed 27
   July) put the acronym into public vocabulary. **Timing-consistent, not causally proven** — no
   client message was read.

---

## 4. LIVE DEFECTS — client-facing, unfixed as of 2026-07-29

**P1 — `balizero.com/business/kbli-2025-food-beverage-fnb` publishes wrong facts and an unbacked price.**
Verified live: HTTP 200, "SLHS" ×11, "9,000,000" ×3.

- Publishes **"IDR 9,000,000"** as our SLHS fee. **Not in PricingTool** — violates the hardcoded-price
  ban (CLAUDE.md §8.11). Whether the number is right is a **Zero decision**, but publishing a price
  the pricing engine doesn't know is a defect regardless.
- Expands the acronym **wrongly**: "Sertifikat Laik **Sehat**". The correct expansion is _Sertifikat
  Laik **Higiene Sanitasi**_. "Laik Sehat" is a _different certificate_ (§2, tier 3) — so this is not
  a typo, it names the wrong product.
- Its "KBLI 2025" table contains **56103, 56109, 56702 — none exist in KBLI 2025**, and attributes
  SLHS to cafés, bars, nightclubs and warungs, which the Lampiran does not name.

**P2 — the shopfront card has no engine.** `services_data.ts:773` renders a live "SLHS (Hygiene
Certificate)" card saying "Check live pricing" on `/services/company`, while
`bali_zero_official_prices_2026.json` has **zero** SLHS entries. A client asking the bot for the
price gets nothing from the tool the bot is required to call first.

**P3 — 26 KBLI pages assert SLHS with invented glosses.** The acronym is expanded three incompatible
ways across codes, and code 41017 says TDUP **"or"** SLHS while others say **"and"** — a direct
internal contradiction, i.e. the content is LLM-generated and unverified.

---

## 5. The phase plan (Krisna)

Sequenced so that **nothing client-facing ships before the facts are right**, and each phase produces
something checkable. F0 is not optional: we are currently publishing wrong claims.

| Phase                               | What                                                                                                                                                                                                    | Done when                                                                                                                          | Owner                       |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | --------------------------- |
| **F0 — Stop the bleeding**          | Fix the three live defects in §4. Correct the acronym, remove the invented codes, and either back the Rp 9jt price with a PricingTool entry or remove the number                                        | The live page passes a content probe: correct expansion present, `56103\|56109\|56702` absent, price either in PricingTool or gone | Krisna + session            |
| **F1 — Ground truth on the ground** | Close the §3 field gaps that only a phone call closes: fee + SLA for **Badung** and **Gianyar** (88 clients), the real PKP cost and 2026 calendar from UPTD Bapelkesmas, whether PHRI is still required | A dated one-pager per kabupaten, each fact attributed to a named office and a date                                                 | **Krisna**                  |
| **F2 — The IKL checklist**          | OCR the official IKL form; turn the scoring grid into a **pre-audit checklist** a consultant can walk a kitchen with. This is the product's core                                                        | A printable checklist whose items map 1:1 to the official form's items                                                             | Krisna + session            |
| **F3 — Pilot on 3 real clients**    | Run the full flow end-to-end on three of the 36 companies on 56101. Measure: real timeline, real cost, where it stalled, what the inspector actually flagged                                            | 3 certificates issued or 3 documented failures, with a written post-mortem each                                                    | **Krisna**                  |
| **F4 — Price and package**          | With F1+F3 numbers in hand, set the price in **PricingTool** and define the package boundary (what's included, what's a pass-through cost)                                                              | Price lives in PricingTool; the site reads it; no number hardcoded anywhere                                                        | **Zero decides the number** |
| **F5 — The renewal engine**         | Fork the LKPM cycle (`lkpm_client_config.kbli_codes` already keys eligibility off a KBLI array) into an SLHS expiry tracker: 3-year clock, alert at T-90                                                | An alert fires on a seeded test record and lands where a human sees it                                                             | session                     |
| **F6 — The honest page**            | One Bali-specific, price-transparent SLHS page — the white space Lane C verified nobody occupies                                                                                                        | Page live, price from PricingTool, every regulatory claim traceable to Lane F                                                      | Krisna + session            |

**Sequencing rule**: F4 cannot start before F1 and F3. We do not price a service we have never
performed and whose local costs we have not measured.

### Untuk Krisna (bahasa Indonesia)

> **Proyek: SLHS (Sertifikat Laik Higiene Sanitasi) — kamu pemiliknya.**
>
> Kenapa kamu: SLHS berlaku **3 tahun** lalu harus diperpanjang. Bentuknya sama persis dengan siklus
> LKPM yang sudah kamu pegang — bukan pekerjaan sekali jadi, tapi siklus yang harus dijaga.
>
> Yang sudah pasti: biaya resmi ke pemerintah **Rp 0**. Yang kita jual bukan aksesnya — yang kita jual
> adalah **lulus inspeksi pada percobaan pertama** dan **tidak lupa perpanjangannya**.
>
> Tugas pertamamu (F1), dan hanya ini dulu:
>
> 1. Telepon **Dinkes Badung** dan **Dinkes Gianyar**: berapa biayanya, berapa lama, apa syaratnya. Di
>    dua kabupaten itu ada 88 klien kita. Denpasar sudah kita tahu: 7 hari kerja, gratis.
> 2. Hubungi **UPTD Bapelkesmas Dinas Kesehatan Provinsi Bali** (Jl. Gumitir 135, Denpasar Timur):
>    berapa biaya pelatihan **PKP** untuk perusahaan swasta, dan kapan jadwal batch 2026.
> 3. Tanyakan apakah **surat rekomendasi PHRI** masih diperlukan atau sudah tidak.
>
> Tulis jawabannya dengan **tanggal dan nama kantor** yang memberi jawaban. Kalau tidak dapat jawaban,
> tulis "belum dapat" — jangan dikira-kira. Satu angka yang salah lebih mahal daripada satu kolom
> kosong.

---

## 6. Blood-bought rules (from the 2026-07-29 research)

1. **Never cite an Indonesian code or article number from an LLM.** In one session, three models from
   three families produced three lists of KBLI codes, all confidently labelled "verified", all wrong.
   Even the lane that ran `pdftotext` and claimed verbatim got the pasal number off by one (1170 vs
   1169). **The arbiter for codes is `KBLI_2025_FINAL_CLEAN.json`; the arbiter for articles is a
   verbatim extraction with a page number.**
2. **A confidence label produced by the same process that produced the claim is worthless.**
   "TERVERIFIKASI DARI SUMBER PRIMER" appeared on the list that turned out ~70% wrong.
3. **Measure the entity, not the container.** Three separate errors in one session came from this:
   `kode_kbli` vs `kode_kbli_2025`; 32 grep lines read as 32 occurrences (they were 26 codes);
   iterating a dict and counting its 8 keys as "8 codes" (there were 1,338).
4. **The regulation speaks KBLI 2020; our dataset speaks 2025; our CRM speaks 2020.** Always state
   which vintage a code belongs to. "Doesn't exist in 2025" ≠ "was never real".
5. **A price on a page is a commercial commitment.** It comes from PricingTool or it does not exist.
6. **Sell the right certificate.** Hotels and villas need **SLS**, not SLHS. 46 of our hospitality
   clients are in that bucket — pitching them SLHS would be selling the wrong product.

---

## 7. Operator boundary (Zero only — Legge 5)

- **The price.** Whether Rp 9jt stands, moves, or becomes a range — and whether we price against a
  Rp 0 government fee at all, given the broker-markup reputation of this market.
- **Whether to enter.** The demand sample is **10 clients**. Lane G's own verdict is "medium-low
  confidence the window is opening" and recommends a small cheap move, not a go-to-market push.
- **Whether Krisna takes it on**, given he already carries the largest client book (323) and the
  LKPM quarterly cycle.
- Anything client-facing published under the Bali Zero name.
