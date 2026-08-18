---
date: 2026-08-17
domain: visa
client_case: none
sources:
  - path: research/visa/doctrine-factory/claims/e2b-batch2-claim-ledger.md
    note: "companion claim ledger this report supports — each CF below is cross-referenced from a CONFLICTING claim there"
  - path: research/visa/doctrine-factory/claims/e2b-batch1-conflict-report.md
    note: "frozen batch-1 template + CF-7..CF-12 numbering; this report continues at CF-13 to avoid collision"
adversarial_review: kimi-k3
---

# E2b batch-2 conflict report — CF-13 through CF-15

Numbering continues from `e2b-batch1-conflict-report.md`'s CF-7..CF-12 (which itself continued from
`e2a-conflict-report.md`'s CF-1..CF-6). This batch does not renumber or re-litigate any earlier CF —
CL-CROSS-E28-01 in the companion ledger cross-references batch-1's CF-12 (E28G nomenclature) without
opening a new number for it, since it is new evidence for that same finding, not a distinct dispute.

## Findings

### CF-13 — E28D: primary law ("branch/subsidiary director") vs internal production DB ("bond
investor") — CROSS-TIER primary-law-vs-internal-material disagreement, CONFLICTING
(heading corrected — an earlier draft mislabeled this "same-tier," directly contradicting this
finding's own body text below, which correctly identifies it as primary-law-vs-internal-material)

Two independent NB-2 answers (`E2B2-E28D`, `E2B2-E28DF-XCHECK`) both surface, unprompted, the same
disagreement: the primary regulatory classification (`Permenkumham 22/2023` as amended by
`Permenkumham 11/2024`, Pasal 33 Ayat (2) Huruf e Angka 2/3 Butir c); confirmed in
`Kepmen M.IP-08.GR.01.01/2025`'s official index table) defines **E28D** as the permit for a foreign
national serving as director/commissioner (`direksi`/`komisaris`) of a newly-established Indonesian
branch or subsidiary of a foreign parent company — an investment threshold of USD 25M (5yr) / USD 50M
(10yr), funded and attested by the foreign parent.

Bali Zero's own production database (`nb2_visa_types_final.txt`, the table the client-facing systems
and portals actually read from) instead labels E28D as **"Investor KITAS (Bonds)"** — an
individual-portfolio bond/government-securities product. That description does not match E28D under
either primary source; it is, if anything, closer to what the primary law calls **E28C**.

- **Authority level**: primary national regulation (Permenkumham + Kepmen, both T0/T1) vs. an internal
  operational database (T2/T3, per `source-hierarchy-draft.md` §3.1.3's tiering) — this is NOT a
  same-tier disagreement the way CF-1/CF-7 were; it is a primary-law-vs-internal-material conflict, so
  per §3.1.3 the primary-law reading is the one that SHOULD govern client-facing advice. It is still
  logged as `CONFLICTING` rather than silently resolved in the ledger, because the disagreement is a
  live operational risk (whichever system actually drives quoting/onboarding for E28D applicants is
  currently telling them the wrong product story) — the fix is not "pick the legally correct answer
  and move on," it is "find and correct wherever `nb2_visa_types_final.txt`'s E28D row is actually
  consumed downstream," which is outside this batch's scope (query-only, no pack/DB mutation).
- **State: CONFLICTING**, not resolved here. Recommend: (1) treat the primary-law definition as
  authoritative for any client-facing E28D content going forward: (2) a separate, scoped follow-up
  task to locate and correct/flag every consumer of `nb2_visa_types_final.txt`'s E28D row (the
  Postgres `visa_types` table this file appears to be an export of, per the E30EF-XCHECK answer's own
  description of its provenance — "Estrazione diretta dal database PostgreSQL di produzione
  `nuzantara_dev` (tabella `visa_types`)").

### CF-14 — E28F: primary law ("IKN branch/subsidiary") vs internal production DB ("Bali real
estate investor") — same class of defect as CF-13, higher client-risk

Same structural conflict as CF-13, different product: `Kepmen M.IP-08.GR.01.01/2025` defines **E28F**
as the permit for establishing a branch/subsidiary specifically inside **Ibu Kota Nusantara (IKN)**,
Indonesia's new capital city — a targeted investment-attraction incentive, unconnected to Bali. The
same `nb2_visa_types_final.txt` production table instead labels E28F as **"Investor properti Rp 5
miliar+; Real estate"** — i.e., framed as a Bali/general-Indonesia luxury real-estate investor product.

This is a HIGHER client-risk instance of CF-13's pattern: Bali Zero's own core business is Bali-based
immigration services, and "real estate investor visa" is exactly the kind of product a Bali-facing
client would ask about and be quoted on. If any live quoting or advisory surface reads E28F's row from
the internal DB rather than the primary law, a client could be told they qualify for a Bali property
KITAS via E28F when the actual legal product for that purpose is a different index entirely (this
batch's own `E2B2-E28F` answer independently recommends **E33A — Second Home via Property** as the
operationally-tested Bali real-estate route, precisely because it flags this E28F mismatch itself).

- **State: CONFLICTING**, not resolved here. Same recommendation as CF-13: primary law governs
  client-facing content; locate and correct/flag the `nb2_visa_types_final.txt`/`visa_types` E28F row
  consumers in a separate scoped follow-up.
- Companion, lower-priority gap on the SAME product: E28F's specific stay-duration figure was not
  found anywhere in this batch's sources (recorded as `NO_PINPOINT_FOUND` in CL-E28F-03 of the
  companion ledger) — independent of the category-conflict above, and not resolved here either.

### CF-15 — E30E (and structurally, likely the whole E30 student family): operational "Path to
KITAP" claim vs primary law's no-direct-conversion rule

The `E2B2-E30E` answer itself flags, unprompted, that operational/client-facing material
(`nb2_visa_types_final.txt`) advertises a direct "Path to KITAP" for E30E holders, while the primary
national instruments (`UU No. 6/2011 tentang Keimigrasian`, `Peraturan Pemerintah No. 31 Tahun 2013`)
do not recognize academic/student status as a basis for direct conversion to KITAP — a student must
first change status (`Alih Status`) to another eligible category (the answer names E28A investor or
E31A spouse-sponsored as examples) before any KITAP path becomes available.

The `E2B2-E30F` answer, asked the same question about the sibling product E30F, does **not**
independently surface this same conflict as explicitly — it states the ≥3-year KITAP eligibility
without flagging the direct-conversion issue. This asymmetry is recorded honestly rather than assumed
away: it is plausible the same primary-law restriction applies equally to E30F (since neither UU
6/2011 nor PP 31/2013 carves out an E30-index-specific exception), but this batch did NOT ask a
dedicated cross-check question to confirm that, so CF-15 is scoped to what was actually asked:
**confirmed CONFLICTING for E30E**, **suspected but unconfirmed for E30F and the rest of the E30
family** (E30, E30A, E30B) — flagged as a likely wider pattern worth a dedicated cross-cutting query in
a future batch, not asserted as fact here.

- **State: CONFLICTING** for E30E specifically. Products: E30E (confirmed), E30/E30A/E30B/E30F
  (suspected, unconfirmed — do not treat as resolved either way).
- Recommend: a future targeted query — "does UU 6/2011/PP 31/2013's restriction on direct
  student-to-KITAP conversion apply uniformly across E30/E30A/E30B/E30E/E30F, or does any sub-index
  carry an exception?" — before this is generalized into a blanket rule for the whole E30 family.

## Dedup check against earlier CF numbers

No finding in this batch's CF-13/14/15 duplicates e2a's CF-1..CF-6 or batch-1's CF-7..CF-12 — the only
overlap is CL-CROSS-E28-01 in the companion ledger, which is explicitly new EVIDENCE for batch-1's
already-open CF-12 (not a new number) and is cross-referenced there, not re-litigated in this file.

## Adversarial review

**Round 1** — `kimi -m kimi-code/k3`, run jointly with the companion claim ledger (concatenated single
input), timeboxed 8 minutes, internal-coherence-only scope (no NB-2 access). Completed inside budget
with 13 numbered findings — full disposition table lives in the companion ledger's own `## Adversarial
review` section (findings against this file specifically: #1, CF-13's heading/body self-contradiction,
**FIXED**; the rest of the 13 targeted the ledger). One finding directly against THIS file: CF-13's
heading called the disagreement "same-tier internal-material" while its own body correctly says the
opposite ("NOT a same-tier disagreement... it is a primary-law-vs-internal-material conflict") — cured
by rewriting the heading to "CROSS-TIER," with a self-note. No finding against this file was rejected.

---

## EXTENSION — CF-7/8/10/12 pinpoint-hunt outcomes (new evidence, batch-2b session)

This EXTENSION does not renumber CF-7/CF-8/CF-10/CF-12 — they remain numbered and their base findings
recorded in `e2b-batch1-conflict-report.md`. This section records NEW EVIDENCE (5 dedicated
pinpoint-hunt queries this session: `E2B2-CF7-A`, `E2B2-CF7-B`, `E2B2-CF8-A` [retry], `E2B2-CF10-A`,
`E2B2-CF12-A`, all `VERIFIED`-audited per `e2b-batch2b-citation-audit.json`) against each, and updates
each disposition from batch-1's `OPEN` to `RESOLVED` where an article-level primary-law pinpoint was
actually found — per this task's binding rule, resolution requires a real pinpoint, not a preference.
`e2b-batch1-conflict-report.md` itself is NOT edited (frozen precedent, matching how batch-1 itself
never edited e2a's file) — read this section as the authoritative UPDATE to those four dispositions
going forward.

### CF-7 UPDATE — RESOLVED: E33E minimum age is 55, per multiple article-level primary-law pinpoints

Batch-1's disposition left this OPEN because the only article-level citation found there (`T1-032`'s
"Art. 33 comma 2 lettera j") self-contradicted its own source's comparison table. This session's two
dedicated probes (`E2B2-CF7-A`, legal-text pinpoint; `E2B2-CF7-B`, operational-practice pinpoint) found
clean, mutually-consistent, non-self-contradicting verbatim citations:

- `Permenkumham No. 11 Tahun 2024` (in force 3 May 2024) Pasal 33(2)(j)(4), Pasal 61(1), Pasal 62(1),
  and Pasal 101(2)(f)(4) — FOUR independent articles, all quoted verbatim in `E2B2-CF7-A`'s answer, all
  giving **55 (lima puluh lima) tahun**. `Kepmen M.IP-08.GR.01.01/2025`'s own classification annex
  (in force 1 June 2025, i.e. AFTER Permenkumham 11/2024) independently confirms 55, quoted verbatim in
  the same answer.
- The **60-year** figure traces to `Permenkumham No. 22 Tahun 2023` (adopted 22 Aug 2023, i.e. BEFORE
  the 2024 reform) Pasal 33(2)(j)(4)/Pasal 61(1) — the PRE-REFORM text, superseded by the 2024 amendment
  on this specific figure. `E2B2-CF7-B` independently confirms Bali Zero's own operational guide
  (`kitas_e33e_silver_hair_guida_2025.txt`, dated 27 March 2025 — AFTER the 2024 legal change but before
  this session's query) still states 60 years, i.e. the guide was never updated to reflect the 2024
  reform.
- **Disposition: RESOLVED.** 55 years is the current, correctly-dated, article-level-pinpointed legal
  minimum. The 60-year figure in Bali Zero's operational guide is not "erroneous" in a
  fabrication sense — it correctly transcribes the PRE-2024-reform text (`Permenkumham 22/2023`) but was
  never updated after the 2024 amendment changed the figure. Per `source-hierarchy-draft.md` §3.2 and
  matching CF-11's precedent (a clean primary-law-vs-primary-law/dated-supersession case), the current
  55-year figure governs; the internal guide should be corrected to reflect the 2024 reform. This does
  NOT resolve whether the Ngurah Rai counter's actual REAL-WORLD practice still applies 60 (a
  legal-text-vs-live-enforcement-practice question this batch's sources cannot settle — `E2B2-CF7-B`'s
  own operational-practice source is dated 27 March 2025, itself possibly stale by now); that narrower
  question is flagged for an operator field-check, not treated as resolved by this pinpoint.

### CF-8 UPDATE — RESOLVED: E33/E33E KITAP conversion window is 3 years, Pasal 179(1) (not Pasal 76)

Batch-1's disposition left this OPEN, ambiguous between "Pasal 179(1)/Pasal 76". `E2B2-CF8-A`'s retry
resolves the ambiguity directly: **Pasal 76** governs only visa CANCELLATION by the Director General,
unrelated to KITAP conversion timing — the answer explicitly states "Non è stabilito l'articolo Pasal
76". The governing article is **Pasal 179(1)** of `Permenkumham 22/2023` ("...telah berada di Wilayah
Indonesia paling singkat 3 (tiga) tahun berturut-turut...", quoted verbatim), scoped to the E33/E33E
family via Pasal 173 huruf f. The answer also confirms neither `Permenkumham 11/2024` nor `UU 63/2024`
amends this 3-year figure — their reforms target guarantor rules and MERP integration, not the KITAP
conversion window.

- **Disposition: RESOLVED.** 3 years, Pasal 179(1), is the legal minimum. The 5-year figure in
  `nb2_golden_visa.txt`/`nb2_visa_types_final.txt` is explicitly identified by the same answer as a
  general-purpose commercial-guide figure NOT specific to E33/E33E (those guides describe
  `KITAP-INV`/`KITAP-RET` generically) — the E33E-SPECIFIC internal guide
  (`kitas_e33e_silver_hair_guida_2025.txt`) actually already states the correct 3-year figure, per the
  same answer. Not called "erroneous" — the 5-year figure is a real, differently-scoped operational
  guide value that happens to get quoted against the wrong product family, not a fabrication.

### CF-10 UPDATE — RESOLVED: E28A KITAP conversion window is 3 years, not "5+ years"

`E2B2-CF10-A` finds the same 3-year figure for E28A specifically: `Permenkumham 22/2023` Pasal 179(1),
scoped to investors via Pasal 173 huruf c ("*penanaman modal asing*" named explicitly among eligible
categories). Neither `Permenkumham 11/2024` nor `Permenimipas 5/2025` amends this figure — both touch
guarantor (`penjamin`)/guarantee (`jaminan keimigrasian`) mechanics, not the conversion timing.

- **Disposition: RESOLVED.** 3 years is the legal minimum; the answer itself identifies the "5+ years"
  commercial-guide figure (`nb2_golden_visa.txt`, `nb2_visa_procedures_guide.txt`) as most likely a
  deliberate PRUDENTIAL margin — aligning E28A's public-facing guidance with the stricter general
  standard applied to non-privileged worker categories, or as a buffer against continuity-of-stay
  rejections — not a legal citation error. Neither figure is called erroneous; the 3-year figure is the
  binding legal minimum, the 5+-year figure is an operational choice.

### CF-12 UPDATE — RESOLVED (independently corroborating the already-merged section's CL-CROSS-E28-01
above)

`E2B2-CF12-A`, run before this session was aware of the already-merged section's own `E2B2-E28BC-XCHECK`
answer above, independently reaches the SAME conclusion: `Kepmen M.IP-08.GR.01.01/2025` defines index
**E28G** as "*Melakukan pekerjaan sebagai representatif dari Perusahaan Induk yang ditempatkan di
Perusahaan cabang*" (working as a representative of a foreign parent company posted to its Indonesian
branch) — a LABOR/EMPLOYMENT index, not an investment tier. The two figures Bali Zero's internal
materials attach to "E28G" (Rp 5 miliar+ / USD 700,000) trace to two DIFFERENT real products' figures,
with different confirmation status for each: USD 700,000 is E28C's confirmed 10-year portfolio-investor
threshold (`Permenkumham 11/2024` Pasal 40(3)) — a clean, uncontested primary-law figure. Rp 5 miliar+
belongs to E28F's INTERNAL-DB label specifically — but per this batch's own **CF-14** (already-merged
section above), that label is ITSELF a contested primary-law-vs-internal-DB mismatch (E28F's real
primary-law meaning is an IKN branch/subsidiary permit, not a real-estate-investor product at all) — so
"Rp 5 miliar+ traces to E28F" is only true of the DISPUTED internal-DB reading of E28F, not a confirmed
real E28F threshold the way USD 700,000 is a confirmed real E28C threshold. This is worth stating
precisely rather than glossing: CF-12's E28G mislabeling and CF-14's E28F mislabeling are TWO SEPARATE,
independently-real internal-DB defects that happen to share the same root cause
(`nb2_visa_types_final.txt`'s general unreliability) — CF-12 does not "reinforce" CF-14 by being a
second, independent sighting of the SAME fact; it reinforces CF-14 only in the weaker sense of adding
more evidence that this internal file is broadly unreliable across multiple, distinct index letters.

- **Disposition: RESOLVED.** "E28G" as a Golden-Visa label is a confirmed internal-material labeling
  artifact, independently corroborated by two separate answers in two separate sessions. Recommend:
  E5/operator confirm whether the "2026-03-28 errata corrige" both this batch's answers reference
  already addresses this in Bali Zero's CURRENT internal materials, since `E2B2-CF12-A`'s own answer
  notes the errata document exists but does not confirm it specifically covers the E28G mislabeling
  (as opposed to the E28B/E28C threshold corrections CL-E28B-05/CL-E28C-05 above already track).

## Adversarial review (EXTENSION)

Full account, covering this EXTENSION section AND the already-merged batch-2 section above (CF-13/14/15)
— per this task's binding constraint that no section is adversarial-review-exempt — lives in the
companion claim ledger's own `## Adversarial review (this EXTENSION + re-covering the already-merged
CF-13/14/15 section)`, run as a single joint pass over both files concatenated. That pass's finding #3
(the original CF-12 UPDATE draft's imprecise "Rp 5 miliar+ is E28F's real-estate-investor threshold"
framing) is what produced this section's own reworded CF-12 UPDATE paragraph above.
