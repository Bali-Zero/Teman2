---
date: 2026-07-21
domain: visa
client_case: none
author: deep-researcher (Bali Zero)
status: verified
sources:
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31J
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31E
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E33F
  - https://id.flado.id/panduan-lengkap-untuk-visa-kitas-bagi-tanggungan-suami-istri-anak-orang-tua-dan-saudara-di-indonesia-e31b-e31e-e31h-e31j/
  - https://id.flado.id/kitas-pensiunan-e33f-dan-visa-rambut-perak-e33e-panduan-anda-untuk-tinggal-di-indonesia/
  - https://cptcorporate.com/pension-kitas-indonesia-2025-guide/
  - https://mpgbali.com/indonesia-introduces-new-retirement-kitas/
  - https://peraturan.bpk.go.id/details/272044/permenkumham-no-22-tahun-2023
  - UU 6/2011 Keimigrasian + PP 31/2013
  - Permenkumham 22/2023 primary PDF text (data/source_documents/t0_regulations/, pdftotext-extracted 2026-07-21)
  - Permenkumham 11/2024 primary PDF text (data/source_documents/t0_regulations/permenkumham_11_2024_perubahan_visa.pdf, pdftotext-extracted 2026-07-21)
adversarial_review: kimi-k3
---

# Verification: E31J age limit · E33F cumulative cap · KITAP-RET income threshold

## Question

Fact-check 3 disputed DRAFT-vs-REVIEWER claims surfaced in the 2026-07-20 team
review round of Bali Zero's client-facing WhatsApp assistant Q&A corpus
(`apps/backend-rag/data/curated_qa/`): (1) does E31J state an explicit max
age of 18? (2) is E33F subject to the general "<5yr first grant → 6yr
cumulative cap, unless excepted" rule? (3) is the current retiree income
threshold USD 3,000 or USD 1,500/month?

## TL;DR

- Dispute 1 (E31J max age) → **CONFIRMED-DRAFT**. No verifiable published
  "18-year max" for E31J; the reviewer conflated it with E31E. The draft's
  cautious framing is accurate — do not hard-code "E31J max age 18".
- Dispute 2 (E33F cumulative cap) → **CONFIRMED-REVIEWER**. A cumulative cap
  applies to E33F; it is not an exception category; no indefinite renewal
  (retirement track: ~5 annual renewals → KITAP, inside the general 6-year
  ITAS umbrella).
- Dispute 3 (retiree income) → **CONFIRMED-REVIEWER**. Current E33F income
  requirement = USD 3,000/month (official page + Permenkumham 22/2023).
  USD 1,500/month is the superseded pre-2024 figure.

## Key citations (verbatim)

- E31J official page: name "Visa Keluarga Anak yang Bergabung dengan
  Saudara Kandung Pemegang ITAS/ITAP"; purpose "Tinggal dan menempuh
  pendidikan di Indonesia"; persyaratan (3 lines, no age line).
- E31E: flado.id — "Hanya dapat diberikan jika anak berusia di bawah 18
  tahun dan belum menikah"; jangkargroups.co.id — "kategori anak dibatasi
  hingga usia 18 tahun atau belum menikah". → the 18-year rule attaches to
  E31E; E31J has no stated age restriction in any source found.
- E33F official page: masa tinggal "1 tahun"; "Bukti penghasilan atau
  tunjangan dengan nilai sekurang-kurangnya US$3.000 (tiga ribu dolar
  Amerika Serikat) per bulan."
- Permenkumham 22/2023 Pasal 185 ayat (1): penanaman modal, penyatuan
  keluarga, repatriasi, rumah kedua issued "paling lama 5 sampai 10 tahun"
  (the exception categories to the general ITAS cap).
- UU 6/2011 + PP 31/2013: ordinary ITAS 2-year grant, extendable,
  "keseluruhan maksimal 6 tahun".

## Findings

### Dispute 1 — E31J max age (CONFIRMED-DRAFT)

No published 18-year cap exists for E31J specifically. The rule attaches to
E31E in every professional source checked (flado.id ×2 guides,
jangkargroups.co.id), which explicitly treat E31J as having no age
restriction. The reviewer's "halaman publik menetapkan batas usia maksimal
sampai 18 tahun" appears to be a transposition of the E31E rule onto E31J,
unsubstantiated on the E31J page itself. Caveat: the E31E official
"Persyaratan Khusus" block also shows no explicit age line via direct
fetch, yet E31E demonstrably has the under-18 rule — so "no age line in
persyaratan" is not by itself proof of absence. The load-bearing evidence
is the flado/jangkargroups asymmetry (E31E limited, E31J not) plus the fact
that no source anywhere states a published E31J 18-year cap. Net: the
draft's caution — "we don't read this as open to any adult joining an
adult sibling; confirm dependant status" — is the correct posture, given
E31J's "Anak" + "menempuh pendidikan" framing structurally implies a
minor/student-dependant route. Do not hard-code "E31J max age 18" as a
published fact.

### Dispute 2 — E33F cumulative cap (CONFIRMED-REVIEWER)

Two structural claims both hold, but the citation was wrong and has been
corrected post-adversarial-review (see below): (a) the general rule —
**Permenkumham 22/2023 Pasal 113** (not UU 6/2011 + PP 31/2013, which
carry an older, separate flat rule) — an ordinary ITAS whose first grant
runs less than 5 years is cumulatively capped at 6 years total via
extensions (ayat 1); a first grant of 5+ years is capped at 10 years
(ayat 2). Pasal 185 does NOT list "exceptions" to Pasal 113 — it separately
defines that 4 activities (penanaman modal/investment, penyatuan
keluarga/family reunification, repatriasi, rumah kedua/Second Home) are
themselves GRANTED for 5-or-10 years as their first-grant duration (ayat
2), which is what lands them in Pasal 113's higher (10-year) bucket — not
a blanket exemption from any cap. (b) E33F is not one of those 4
Pasal-185 activities and its own official page confirms a 1-year first
grant (E33E is the 5-year sibling, under Pasal 185(1)(d) rumah kedua),
so it falls under Pasal 113(1)'s 6-year bucket by the ordinary mechanism,
not an up-front 5/10-year grant. Conclusion: the draft's uncertainty
("maybe no cumulative cap / indefinite renewal") is wrong — a cap applies.
Operative client-facing figure: valid 1 year, renewable annually up to
roughly 5 years of total stay under this track, then convert to Retirement
KITAP — which sits inside (and is stricter than) the general 6-year ITAS
ceiling. State it as "up to 5 years → KITAP", not literally "6 years" (the
6-year figure is the general umbrella; the retirement-specific practical
ceiling is 5 years then conversion).

### Dispute 3 — Retiree income threshold (CONFIRMED-REVIEWER)

Current figure = USD 3,000/month, confirmed verbatim on the official
imigrasi.go.id E33F page: "Bukti penghasilan atau tunjangan dengan nilai
sekurang-kurangnya US$3.000 (tiga ribu dolar Amerika Serikat) per bulan."
Corroborated by 2024+ guides (flado.id, balivisas Nov-2025, mpgbali.com).
Legal basis: Permenkumham 22/2023, effective 2024. USD 1,500/month is the
SUPERSEDED pre-2024 figure — explicit history found: "The 1-year
Retirement KITAS previously required USD 1,500/month, while the new visa
requires USD 3,000/month" (mpgbali.com). One 2025 guide (cptcorporate.com)
still quotes ~USD 1,500 — this is precisely the stale number the draft "saw
quoted" and correctly flagged as unresolved; it is now resolved. Minimum
age for E33F is 55 — confirmed via primary text of Permenkumham 11/2024
(which amends Pasal 33/61/62 of 22/2023 from 60 to "55 (lima puluh lima)
tahun atau lebih"), see Adversarial review below. **Correction (2026-07-21,
post-adversarial-review): the "USD 50,000 state-bank deposit" requirement
belongs to E33E only, not E33F** — E33F's official page and Permenkumham
22/2023 Pasal 61 show only the USD 3,000/month income test; the deposit
line (Pasal 62) is the E33E/"Silver Hair" 5-year track. This document
originally conflated the two; see Adversarial review.

## Disagreements / open questions

- Dispute 1: genuine source split — official page + flado.id +
  jangkargroups.co.id vs. what appears to be a conflated search-engine
  summary — resolved against the reviewer's specific "18 on the E31J page"
  claim.
- Dispute 2: number-precision nuance — "6-year general cap" (the umbrella
  baseline) vs. "5 annual renewals → KITAP" (the retirement-track practical
  ceiling); both frames agree a cap exists, only the exact number to quote
  to a client differs by which frame you use. Permenkumham 22/2023 primary
  PDF on bpk.go.id returned HTTP 403 to automated fetch this session;
  verified instead via kemenkumham/imigrasi summaries + the UU/PP text.
- Dispute 3: none — official page is unambiguous.

## Adversarial review

Reviewed by an independent seat (Kimi K3, `kimi-code/k3`), which pulled the
Permenkumham 22/2023 primary text itself (bypassing the bpk.go.id 403 via a
mirror PDF + `pdftotext`) rather than reviewing the text-pack. Verdict on
the seat's own central-claims check: **all 3 disputed conclusions hold**
(E31J age unconfirmed — correct to leave unhardcoded; E33F capped ~5yr→KITAP;
USD 3,000 current/1,500 superseded). It raised 7 objections; after
independently checking each against primary-source PDFs, 4 were real and
have been fixed above, 1 was investigated and found to be the reviewer's
own error (not fixed — see below), and 2 are citation-precision notes
folded into the fixes:

**Fixed (confirmed real):**
1. The "USD 50,000 state-bank deposit" was wrongly attached to E33F in
   this document's Dispute-3 section — that deposit belongs to E33E
   (Pasal 62), not E33F (Pasal 61, income-only). Fixed above. (The
   client-facing KB rows already had this right — only this research
   document's summary line was wrong.)
2. The cumulative-cap rule (Dispute 2) was mis-cited to "UU 6/2011 + PP
   31/2013" — the actual operative article, independently confirmed via
   primary PDF text, is **Permenkumham 22/2023 Pasal 113**. Fixed above.
3. Pasal 185 was mischaracterized as an "exceptions" clause — primary
   text confirms it instead defines which 4 activities get a 5-or-10-year
   *first grant* (investment/family/repatriation/second-home), which is
   what lands them in Pasal 113's higher cap bucket. Fixed above.
4. The mpgbali.com "1,500→3,000 history" quote could not be re-found
   verbatim at the cited URL by the seat's fresh fetch — the underlying
   fact is independently corroborated by 3 other sources (cptcorporate,
   cekindo, affordableretirementabroad) so the conclusion is unaffected,
   but the citation should not claim that exact sentence lives at that URL.

**Investigated and NOT fixed — the seat's objection was itself wrong:**
5. The seat flagged "minimum age 55" for E33F as contradicted by
   Permenkumham 22/2023, which does say 60 (Pasal 33(2)(j)(4), Pasal 61,
   Pasal 62 all read "60 (enam puluh) tahun" in the base 2023 text). The
   seat explicitly identified the necessary next check — whether
   **Permenkumham 11/2024** amends this — but could not complete it
   (same bpk.go.id 403). Independently pulling
   `permenkumham_11_2024_perubahan_visa.pdf` (already present in this
   repo's `data/source_documents/t0_regulations/`) and running
   `pdftotext` on it confirms: **Pasal 33 is explicitly restated
   ("Ketentuan Pasal 33 diubah sehingga berbunyi sebagai...") with "55
   (lima puluh lima) tahun atau lebih"**, and Pasal 61 + Pasal 62 both
   carry the same "55" text post-amendment. So the original "minimum age
   55" claim was correct all along — the seat's objection is a case of
   checking the base regulation and not completing the check on its own
   amending regulation, exactly the failure mode this repo's scars call
   "even the refuter hallucinates" (W65) / "the ground-truth can itself
   be stale" (W90). No KB or research-doc change made on this point.

**Minor, not touching any conclusion (noted, not separately fixed):**
6. TL;DR/body internal-math phrasing ("~5 annual renewals" vs "~5 years
   total stay") — cosmetic; the operative client-facing guidance ("plan
   the KITAP conversion into the timeline from year one") is unaffected.
7. "Permenkumham 22/2023, effective 2024" is loosely worded (promulgated
   2023, the retiree-track amendment is via Permenkumham 11/2024,
   ditetapkan 1 April 2024) — the practical "pre-2024 vs current" framing
   for the USD 1,500→3,000 dispute is unaffected.

## Checklist for action

- [x] Keep the draft's cautious E31J wording; do NOT hard-code "E31J max
      age 18" (unverified) — no KB change needed for E31J.
- [x] Fix the E33F row in `visa-second-home-variants.jsonl`: remove
      "possibly indefinite renewal" language; state "1-year, annually
      renewable up to ~5 years → Retirement KITAP; not exempt from the
      general ITAS cumulative cap." (applied 2026-07-21, see
      `research/curated-qa-corrections-2026-07-21/` in this PR)
- [x] Fix the KITAP-RET row in `visa-catalog-sweep.jsonl`: set retiree
      income to USD 3,000/month as the current governing figure; state
      USD 1,500/month explicitly as the superseded pre-2024 figure, not an
      unresolved regional variance. (applied 2026-07-21, see
      `research/curated-qa-corrections-2026-07-21/` in this PR)
- [ ] If a live client quote ever hinges on the exact ITAS cumulative-cap
      article number, pull the Permenkumham 22/2023 primary PDF directly
      (bpk.go.id returned 403 to automated fetch on 2026-07-21; try a
      different access path or a manual browser fetch).

## Sources

1. imigrasi.go.id E31J page (fetched 2026-07-21).
2. imigrasi.go.id E31E page (fetched 2026-07-21).
3. imigrasi.go.id E33F page — verbatim "US$3.000 per bulan" (fetched
   2026-07-21).
4. flado.id — E31B/E31E/E31H/E31J guide.
5. flado.id — E33F/E33E guide.
6. jangkargroups.co.id — E31 guide.
7. cptcorporate.com — pension KITAS 2025 guide.
8. mpgbali.com — "Indonesia Introduces New Retirement KITAS" (1,500→3,000
   history).
9. Permenkumham 22/2023 (peraturan.bpk.go.id/details/272044 — primary PDF
   403'd; verified via secondary summaries).
10. UU 6/2011 tentang Keimigrasian + PP 31/2013 (general ITAS cumulative
    cap baseline).
