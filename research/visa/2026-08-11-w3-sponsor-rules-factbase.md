---
date: 2026-08-11
domain: visa
client_case: none
adversarial_review: codex
sources:
  - https://peraturan.go.id/files/permenkumham-no-22-tahun-2023.pdf
  - https://peraturan.go.id/files/permenkumham-no-11-tahun-2024.pdf
  - https://kemenimipas.go.id/attachments/2025/peraturan/20250813_09_Kepmen_No_M.IP-08.GR.01.01_Th_2025_Tentang_Klasifikasi_Visa.pdf
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E23U
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E23V
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E28C
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E33A
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E33B
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E33C
  - apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-006.source.json (internal, seq-6 unsigned/unactivated)
  - apps/backend-rag/backend/services/visa_engine/contracts/contract.schema.json (internal)
  - apps/backend-rag/backend/services/visa_engine/enums.py (internal)
  - apps/backend-rag/backend/services/visa_engine/fact_registry.py (internal)
  - research/visa/2026-08-10-seq6-requirements-are-not-walls.md (internal)
---

# W3 — sponsor.type factbase for E23U, E23V, E28C, E33A, E33B, E33C

## Method and evidence tiers

Every claim below is tagged:

- **[PRIMARY]** — read directly from the regulation's own PDF text, extracted with
  `pypdf` (both `peraturan.go.id` PDFs and the `kemenimipas.go.id` Kepmen PDF are
  genuine text-layer PDFs — `WebFetch`'s HTML-conversion path mis-reads them as
  image streams and reports "cannot extract text"; extracting with `pypdf` outside
  that path recovers full text). Pasal/ayat/huruf/butir citations below are
  verbatim locations in that extracted text, not agy paraphrase.
- **[OFFICIAL PORTAL]** — read from `imigrasi.go.id/wna/daftar-visa-indonesia/<code>`,
  the DG Immigration's own per-product catalog page, via `WebFetch`.
- **[SECONDARY — agy, verified]** — a Gemini 3.1 Pro (`agy`) research claim that I
  independently re-derived from the primary PDF text above and confirmed correct.
- **[SECONDARY — agy, unverified]** — an agy claim I could not independently confirm
  (source unreachable, or contradicted). Not treated as fact.
- **[NON VERIFICATO]** — no source found either way; stated as a gap, not a claim.

Two research agents ran in parallel for the initial sweep (`agy --model "Gemini 3.1
Pro (High)"`, one prompt per product cluster); every load-bearing number/citation
they returned was then re-derived from the primary-source PDFs directly, because
agy is known to fabricate plausible regulation numbers (it did, twice — see
`## Adversarial review` and the per-product notes).

The internal rulepack facts referenced below (`sponsor_types`, `covered_purposes`,
existing rule ids) are read live from `rulepack-prod-006.source.json` in this
worktree, not from the caller's briefing — two of the briefing's priors turned out
wrong (E28C's `sponsor_types` is `["INDIVIDUAL"]`, not `["INVESTMENT"]`; E33B's is
`["NONE"]`, not `["GOVERNMENT"]`).

---

## Cross-cutting finding: two Kepmen citations, one gap

**Corrected after adversarial review** — the pack cites the Kepmen
M.IP-08.GR.01.01/2025 content two different ways, and this file originally
conflated them. `source_record 6f5135f2-1f77-571f-88ed-26d1d2b9efba`
(`canonical_url: imigrasi.go.id/wna/daftar-visa-indonesia`) is the pack's citation
for the **web catalog** — used as the `source_ref` for E28A-F and the E33 family
— while `e3572ad2-08a9-55bd-b818-353b3e9db715`
(`canonical_url: kemenimipas.go.id/attachments/.../Kepmen_...Klasifikasi_Visa.pdf`)
is its citation for the **downloadable Lampiran PDF**, used only as the
`source_ref` for E23U/E23V. The Lampiran text quoted throughout this file (the
80-page PDF, extracted with `pypdf`) is the document behind `e3572ad2`, not
`6f5135f2` — both are plausibly the same underlying Kepmen content in different
publication forms, but this file cites the one I actually read.

That Lampiran is a **catalog of rights and prohibitions per index**, not a
procedural regulation — it does not itself define who may be a `Penjamin` or what
a sponsor must produce. That lives in Permenkumham 22/2023 *jo.* 11/2024 (pack's
`9248b1d7-9172-54d9-ad61-251e83a2285b`), structured as one dedicated Pasal per
`Pasal 33 ayat (2)` sub-item.

Cross-referencing the two **[PRIMARY]**: E28C, E33A, E33B, E33C all have a
dedicated procedural Pasal in Permenkumham 22/2023 (39/40, 57, 58, 59
respectively). For E33A/E33B/E33C that Pasal states **explicitly** whether a
`Penjamin` is required and who it must be (`atau Penjamin` / `tanpa Penjamin` /
`yang merupakan pemerintah pusat` are all verbatim). For **E28C** the Pasal states
the application is filed by the foreigner alone and requires `Jaminan
Keimigrasian` — the *absence* of a Penjamin is a structural inference from that
silence, not an explicit "tanpa Penjamin" clause (see §3, corrected). **E23U and
E23V have no dedicated Pasal at all** — a full-text search of both the 2023 base
text and the 2024 amendment (115 + 49 pages, extracted in full) for "diplomat",
"kamar dagang", and "asisten rumah tangga" returns **zero hits** outside the
Kepmen row itself. This matches the `imigrasi.go.id` catalog pages for these two
codes, which both read "**Data Belum Tersedia**" (data not yet available, checked
this session — see the retrieval-date caveat under §Summary table) — consistent
with, but not proof of causation for, why the rulepack currently carries **zero
rules of any stage** for E23U/E23V. Absence of a public procedure does not by
itself demonstrate absence of an operational requirement; the Kepmen row alone
already supplies enough identity/activity/limit information that a fail-closed or
`HUMAN_REVIEW` rule could in principle be written today — the pack's silence on
E23U/E23V is evidence of caution, not proof there is "nothing to encode."

---

## 1. E23U — Working Visa, Foreign Diplomat House Assistant

**Official name [PRIMARY]**: Kepmen M.IP-08.GR.01.01/2025, Lampiran, Bagian B
("Klasifikasi Visa Tinggal Terbatas"), row 1, sub-index E23U (PDF page 37 of the
80-page Lampiran): *"E23U — Melakukan pekerjaan sebagai asisten rumah tangga
diplomat asing"* ("performing work as a household assistant of a foreign
diplomat"). Sits in the same `No. 1` block as base **E23** ("`...dalam hubungan
kerja dengan penjamin`" — "...in an employment relationship **with a sponsor**")
and **E23A/E23X/E23Y**.

**Penjamin ammesso — mapped to `sponsor.type`**: **UNRESOLVED, not merely
"plausible"** — corrected after adversarial review. Textual signal **[PRIMARY]**:
unlike E23, E23A and E23Y, whose Uraian Kegiatan explicitly says "`...dengan
penjamin`", **E23U's row omits that phrase entirely** — the only sponsor-shaped
word anywhere in the row is "diplomat asing" itself. No dedicated procedural
Pasal exists in Permenkumham 22/2023/11/2024 for E23U (confirmed by full-text
search, see above), so there is no statutory definition of who signs as
`Penjamin` here. The omission only shows that E23U is **not** the ordinary
"employment with a Penjamin" shape (E23/E23A/E23Y) — it does **not** by itself
establish that the diplomat personally is the Penjamin; an institutional actor
(the sending state's mission, or a Kemlu-mediated arrangement) not visible in the
row is equally consistent with the same silence. `sponsor.type = INDIVIDUAL` is
Bali Zero's working hypothesis, stated here as a hypothesis to resolve
deliberately, not a reading the source text forces.

**Diplomatic-privilege basis [SECONDARY — agy, unverified]**: agy cited UU 1/1982
(ratification of the 1961 Vienna Convention on Diplomatic Relations) and its
distinction between mission staff and "pelayan pribadi" (private servants) as the
underlying rationale for a distinct visa index. I could not independently fetch
`bphn.go.id/data/documents/82uu001.pdf` (403 Forbidden) to confirm the specific
"private servant" clause agy quoted, though UU 1/1982 itself is a well-known,
uncontested ratification statute. **Treat the private-servant distinction as
plausible context, not a cited fact**, until fetched from a working mirror.

**Requisiti congiunti (gate completo) [PRIMARY, single pypdf extraction pass, not
independently cross-checked by a second reader]**: Hak includes bringing family
to reside in Indonesia (subject to standard immigration rules), re-entry during
Izin Masuk Kembali validity, receiving remuneration from the work. Kewajiban:
comply with labour law and other regulations, comply with the employment
contract, respect local customs. Larangan: overstay, work inconsistent with the
permit, sale of goods/services. `stay_policy` in the pack:
`FIXED_DAYS 365/365` (matches E23U's Kepmen row placement alongside E23's general
work-visa duration convention — **[NON VERIFICATO]** for the exact duration
article, since as above there is no dedicated E23U Pasal).

**What is NOT verifiable with the current 41-fact vocabulary**:
- No fact path distinguishes "employer is a natural person" from "employer is a
  company" — `work.employer_is_indonesian_entity` is a plain boolean and doesn't
  capture "employer is a foreign individual" as a category at all.
- No fact path records diplomatic accreditation of the employer (e.g. a Kemlu
  Protokol confirmation). The engine has no channel to verify this even in
  principle — it would have to remain a `HUMAN_REVIEW`/document-check gate, not
  an applicant self-report fact, similar in shape to `review.e33a.*`.
- `intent.purposes = EMPLOYMENT` is the only purpose-level fact that would fire
  for this route today, and it is shared with ordinary E23/E23A/E23X/E23Y — there
  is no discriminator fact between "household assistant of a diplomat" and any
  other EMPLOYMENT purpose. This is exactly the class of gap the seq-6 note (§2)
  already names for E23U/E23V generically.

**Proposed `when` shape (pseudoform, NOT a rule — illustrative only)**:
```
HARD_FILTER (fail-closed until the facts below exist):
  all:
    - eq(intent.requested_product_code, "E23U")
    - NOT intersects(intent.purposes, [EMPLOYMENT])   # placeholder — real gate
      needs "employer_is_accredited_diplomat" or equivalent, which does not exist
```
No SUPPORT rule can be written for E23U today without either (a) a new fact for
diplomatic-employer confirmation, entered via `HUMAN_REVIEW`/document check rather
than self-report, or (b) accepting `sponsor.type == INDIVIDUAL` alone as sufficient
— which the seq-6 doctrine (§1: "a converted requirement may add a candidate
reason only when conjoined with the product's genuine eligibility gate") would
reject, since `INDIVIDUAL` is also true for ordinary family-sponsor and other
individual-sponsor cases that are not E23U.

---

## 2. E23V — Working Visa, Trade and Economic Office

**Official name [PRIMARY]**: Kepmen Lampiran, same block (PDF page 37-38):
*"E23V — Melakukan pekerjaan atau sebagai tenaga ahli sebagai pejabat atau staf
pada kamar dagang asing"* ("performing work or acting as an expert, an official or
staff member at a **foreign chamber of commerce**"). Correction to the mandate's
prior — the literal text says "kamar dagang asing" (foreign chamber of commerce),
not "Kantor Dagang dan Ekonomi Indonesia"/KDEI specifically; KDEI-style
representative offices (e.g. Taipei Economic and Trade Office) are a plausible
real-world instance of this class but the Kepmen text does not name any
institution.

**Penjamin ammesso — mapped to `sponsor.type`**: **UNRESOLVED** — corrected after
adversarial review from an earlier "plausible/weaker-than-it-looks" framing that
still overstated confidence. Same negative-evidence pattern as E23U: the Kepmen
row does not say "dengan penjamin" or "instansi pemerintah" — compare **E23X**,
three rows below in the same document, whose Uraian Kegiatan explicitly reads
*"Sebagai Tenaga Ahli pemerintahan"* with Hak *"...hubungan kerja **dengan
instansi pemerintah**"* [PRIMARY]. E23X names the government relationship
explicitly; E23V does not, and that absence refutes the mapping more than it
supports it: a foreign chamber of commerce can equally be a private trade
association or an ordinary `EMPLOYER` under Indonesian law — nothing in the Kepmen
row establishes governmental character normatively, and the pack's `GOVERNMENT`
choice should be read as an unresolved judgment call, not a defensible inference,
until a dedicated source is found. No dedicated Permenkumham Pasal exists for
E23V either (confirmed by the same full-text search).

**Requisiti congiunti [PRIMARY, same single-pass extraction caveat as E23U]**:
same Hak/Kewajiban/Larangan structure as E23U (family residence, re-entry,
remuneration; comply with labour law/contract/customs; no overstay, no
mismatched work, no sale of goods/services except as needed for the job).
`prohibited_activities` in the pack —
`work_for_standard_corporate_employers` — is a Bali Zero paraphrase, not
Kepmen-sourced wording; the closest textual anchor is simply that the row's Jenis
Kegiatan names "kamar dagang asing" as the only qualifying employer.

**What is NOT verifiable with the current 41-fact vocabulary**: identical gap to
E23U — no fact distinguishes "foreign chamber of commerce / trade office" from
"ordinary foreign employer" or "Indonesian government instansi". `sponsor.type`
alone cannot carry this distinction because a real foreign chamber of commerce in
Indonesia is neither a `Korporasi` under Indonesian law in the PT-PMA sense, nor
literally `instansi pemerintah` of Indonesia (it represents a *foreign* state's
trade interests) — the six-value enum has no clean slot for "foreign
quasi-governmental representative body", and whoever writes the rule will have to
choose `GOVERNMENT` or `EMPLOYER` by judgment call, undocumented in
`enums.py`/`fact_registry.py` (neither file records intended per-value semantics
beyond the bare name).

**Proposed `when` shape (illustrative only)**: same structural note as E23U — no
SUPPORT rule is safely writable without a new discriminator fact (e.g.
`work.employer_is_foreign_trade_office` or similar), and the existing
`EMPLOYMENT`-only purpose signal is shared with every other E23 sub-variant.

---

## 3. E28C — Investor Golden Visa, Capital Market (no company)

**Official name [PRIMARY]**: Permenkumham 22/2023, Pasal 33(2)(e) angka 2 butir b)
/ angka 3 butir b): *"Orang Asing sebagai investor perorangan yang **tidak
bermaksud mendirikan perusahaan** di Indonesia"* ("a foreign national as an
individual investor who does **not** intend to establish a company in
Indonesia"). Kepmen 2025 Lampiran (PDF page 51-52) [PRIMARY] confirms the same
framing for the E28C row: *"Penanaman modal asing ... yang melibatkan orang asing
sebagai investor perorangan ... E28C ... yang tidak bermaksud mendirikan
perusahaan di Indonesia."*

**Penjamin — self-filed, but not "tanpa Penjamin" in as many words — corrected
after adversarial review**: **[PRIMARY]**. Permenkumham 22/2023 Pasal 39(1)
(5-year track) and Pasal 40(1) (10-year track), **as amended and re-enacted
unchanged by Permenkumham 11/2024** (Pasal 39 shows in 11/2024's amendment list
but its text, cross-checked page-for-page against the 2023 original, is identical
for this sub-item): *"diajukan oleh Orang Asing"* ("submitted by the foreign
national") — E33A/E33C's Pasal (57, 59) instead read *"diajukan oleh Orang Asing
**atau Penjamin**"*, and E33B's Pasal 58 states the absence explicitly ("`tanpa
Penjamin`"). Ayat (1) huruf b of Pasal 39/40 requires *"bukti Jaminan
Keimigrasian"* (immigration-guarantee evidence), never *"bukti penjaminan dari
Penjamin"* (the phrase E33A/E33C's Pasal use). **This is a structural absence, not
an explicit "tanpa Penjamin" clause** — weaker evidence than what E33B has for the
same conclusion, even though it points the same direction. `imigrasi.go.id/wna/
daftar-visa-indonesia/E28C` **[OFFICIAL PORTAL, retrieved 2026-08-11 this
session]** states in plain language: *"Anda tidak membutuhkan penjamin/sponsor
untuk mengajukan visa ini"* — this portal claim was not independently reproducible
by the adversarial reviewer (its sandbox could not resolve `imigrasi.go.id`), so
it stands on my own `WebFetch` call in this session only; treat it as
current-as-of-retrieval, not permanently verified.

**Not a "mismatch" — a semantic ambiguity, corrected after adversarial review**:
an earlier version of this section called the pack's `sponsor_types:
["INDIVIDUAL"]` for E28C a "mismatch" against the source. That overstated the
case. What the source actually establishes is: self-filed, no Penjamin
attestation required, `Jaminan Keimigrasian` substituted. Whether that maps to
`sponsor.type = NONE` (the value the pack uses for the textually-explicit
"tanpa Penjamin" case on **E33B**) or `INDIVIDUAL` (read as "the natural-person
applicant stands as their own guarantor" — also a legitimate reading, since E28C
literally has only one natural person as a party to the transaction) **cannot be
settled from the statute alone**, because neither `enums.py` nor
`fact_registry.py` documents what `INDIVIDUAL` is supposed to mean as opposed to
`NONE` (see the vocabulary-gap note at the end of this file). The real finding is
narrower than "the pack is wrong": **the enum's undocumented semantics make E28C's
current encoding unfalsifiable either way** — flagged here so whoever writes the
E28C rule resolves the INDIVIDUAL-vs-NONE question deliberately, with a written
rationale, rather than leaving it to stand by default.

**Requisiti congiunti — thresholds, verified against BOTH the 2023 base text and
the 2024 amendment (identical in both) [PRIMARY]**:
- 5-year track (Pasal 33(2)(e) angka 2 butir b), procedure Pasal 39(3)): commit to
  purchase, within 90 days of ITAS issuance, **at least USD 350,000** in (a)
  Indonesian government bonds, (b) shares in an Indonesian publicly listed
  company, or (c) mutual funds of an Indonesian publicly listed company.
- 10-year track (Pasal 33(2)(e) angka 3 butir b), procedure Pasal 40(3)): **at
  least USD 700,000** in the same three instrument classes, **or USD 1,000,000**
  in a rumah susun/apartemen (residential unit) — a fourth option not present on
  the 5-year track.
- **Catalog/norm discrepancy, found on adversarial review**: the Kepmen Lampiran
  row for E28C (as extracted here) lists only three instruments — government
  bonds, listed shares, mutual funds — and does not mention the apartment/rumah
  susun option that Pasal 40(3) explicitly grants on the 10-year track. The
  Kepmen classification table and the Permenkumham procedural Pasal are not
  perfectly mirror-consistent on this product; the Pasal is the binding
  procedural text and should govern if a rule is ever written, but the gap
  itself is worth recording.
- Of `prohibited_activities` in the pack (`operational_work`,
  `corporate_establishment`), only `corporate_establishment` has a direct textual
  anchor — the Pasal's "tidak bermaksud mendirikan perusahaan" framing.
  `operational_work` has **no supporting text in either Permenkumham document**;
  it is a Bali Zero paraphrase of the same eligibility condition (not intending to
  run a company), not a separately-cited prohibition, and should not be presented
  as independently normatively grounded.
- This confirms (independently, via the primary PDF, not by trusting agy) the
  $350k/$700k figures agy also reported — agy's number was right, its cited
  regulation ("Peraturan Pemerintah Nomor 45 tahun 2024") does not appear in
  either Permenkumham text I extracted and is **not used as a source here**.

**What is NOT verifiable / vocabulary gap**: `investment.investment_capital_idr`
and `investment.paid_up_capital_idr` are IDR-denominated and, by name, shaped for
PT PMA paid-up capital (the E28A pathway) — neither is a natural fit for a
USD-denominated securities-purchase commitment with no company involved. The
vocabulary already has a precedent for USD-denominated individual thresholds
(`secondhome.bank_deposit_usd`, `secondhome.qualifying_property_value_usd`); no
equivalent exists under `investment.*` for E28C's instrument purchase.
`investment.proposed_role = NO_OPERATIONAL_ROLE` (existing enum value) is a
reasonable fit for the investor's role and needs no new vocabulary.
`investment.pt_pma_committed = false` is already usable to distinguish this
pathway from E28A.

---

## 4. E33A — Second Home Visa, Special-Expertise Government Invitation

**Official name [PRIMARY]**: Permenkumham 22/2023 Pasal 57 (unchanged by
11/2024 — not in that amendment's list of touched Pasal), governing Pasal 33(2)(j)
angka 2 **with** Penjamin: *"Orang Asing yang memiliki keahlian khusus... diajukan
oleh Orang Asing **atau Penjamin**... b. bukti penjaminan dari Penjamin, **yang
merupakan pemerintah pusat**"* ("proof of sponsorship from a Penjamin, which is
the central government"). Kepmen Lampiran (PDF page 72-73) [PRIMARY] row: *"E33A
— Orang asing yang diundang oleh pemerintah karena keahliannya"*, with Hak
including *"...hubungan kerja **dengan pemerintah pusat**"* — an explicit right to
work FOR the central government, textually the strongest sponsor signal of all
six products.

**Penjamin ammesso — mapped to `sponsor.type`**: **GOVERNMENT, verified
[PRIMARY]** — statute says "Penjamin ... yang merupakan pemerintah pusat" in so
many words. This is **one of two** products of the six (with E33C) where
`sponsor.type = GOVERNMENT` is a direct, cited match rather than an inference —
corrected from an earlier "the one product" overstatement.

**Requisiti congiunti [PRIMARY]**: Pasal 57(2): the "dokumen lain" is *"undangan
atau keterangan dari pemerintah pusat yang menjelaskan urgensi Orang Asing
tersebut diundang sebagai orang yang memiliki keahlian khusus"* (an invitation or
statement from the central government explaining the urgency/justification for
inviting this specific person for their special expertise). Standard passport
(6mo+), living-cost proof, photo requirements apply. **No separate financial
deposit threshold is stated in Pasal 57** — the Pasal is simply silent on a
deposit, which is consistent with, but not textual proof of, a causal
"the invitation substitutes for the deposit" reading (an earlier draft of this
paragraph asserted that causal reading as fact; retracted here). Separately, the
`imigrasi.go.id` **[OFFICIAL PORTAL, retrieved 2026-08-11 this session, not
independently reproduced by the adversarial reviewer — see the E28C note above
for why]** page lists only the USD 2,000 bank-statement minimum common to all
Second Home sub-products, not a Second-Home-specific deposit tier.

**Existing rule verdict**: `review.e33a.central-government-invitation`
(`GOVT_INVITATION_REQUIRED`, fires on `intent.purposes ∩ EMPLOYMENT`) is
**grounded** — E33A's own Hak clause is specifically an employment relationship
with the central government, so keying the review on `EMPLOYMENT` is textually
consistent, not an arbitrary purpose binding.

**What is NOT verifiable / vocabulary gap**: there is no fact path for "holds a
confirmed central-government invitation" (a boolean, or a reference/urgency
statement) — nothing analogous to `family.sponsor_confirmed` or
`study.sponsor_confirmed` exists under a `government.*` prefix. This is likely
fine as a permanent `HUMAN_REVIEW`-only gate (a government invitation letter is
inherently a document a human must read, not something meaningfully
self-reported), but if a future SUPPORT rule is ever wanted, this fact does not
exist today.

---

## 5. E33B — Second Home Golden Visa, Special-Expertise Collaboration

**Official name [PRIMARY]**: Permenkumham 22/2023 Pasal 58 (unchanged by
11/2024), governing Pasal 33(2)(j) angka 2 **without** Penjamin: *"Orang Asing
yang memiliki keahlian khusus... **tanpa Penjamin**... diajukan oleh Orang
Asing"* (submitted by the foreigner alone — no "atau Penjamin" option here, unlike
E33A). Kepmen Lampiran (PDF page 74) [PRIMARY]: *"E33B — Orang asing yang memiliki
keahlian khusus dan akan berkolaborasi dengan pemerintah"*.

**Penjamin ammesso — mapped to `sponsor.type`**: **NONE, verified [PRIMARY]** —
the pack's existing `sponsor_types: ["NONE"]` is correct and directly grounded,
not merely plausible. Pasal 58(1) huruf b requires *"bukti Jaminan
Keimigrasian"*, never a Penjamin attestation.

**Requisiti congiunti — the most concrete of the six [PRIMARY, Pasal 58(2)-(3)]**:
1. Jaminan Keimigrasian = a written commitment to submit, **within 90 days** of
   ITAS issuance, proof of cooperation with a government body or state
   institution ("bukti kerja sama dengan pemerintah atau lembaga negara").
2. Expertise proof (either one): (a) a certificate in a specialised field the
   state needs ("sertifikat di bidang keahlian khusus yang dibutuhkan oleh
   negara" — the specific field list is delegated to the Dirjen, not stated in
   the Pasal itself), OR (b) graduation within the last 3 years from one of the
   world's top-100 universities with a **GPA ≥ 3.5**.
   This confirms — independently, via the primary text — the agy claim that was
   most likely to be a fabrication (a suspiciously specific "top-100
   university + GPA 3.5" detail); it is not fabricated, it is Pasal 58(3) huruf
   b verbatim.

**Existing rule verdict**: `review.e33b.expertise-qualification`
(`E33B_EXPERTISE_QUALIFICATION_CHECK`, fires on `intent.purposes ∩ EMPLOYMENT`) —
**partially grounded**. E33B's Hak clause (Kepmen row) grants *both* "hubungan
kerja" (employment) *and* "bisnis atau investasi" (business/investment)
activities; keying only on `EMPLOYMENT` misses the `INVESTMENT`/business half of
what the product actually covers. Not flagged as wrong in the sense E28C's
`sponsor_types` was — the review rule is a `HUMAN_REVIEW` gate, so under-triggering
here means some legitimate E33B business-purpose applicants might not get flagged
for the expertise check, not that an ineligible applicant gets waved through. Worth
the rule-author's attention when this pack is next opened.

**What is NOT verifiable / vocabulary gap** — the largest gap of the six:
- No fact path records professional certification or its field (nothing under
  `study.*`, `work.*`, or elsewhere captures "holds a certification the state
  needs").
- No fact path records university ranking, graduation date/recency, or GPA.
  `study.level` / `study.admission_confirmed` are shaped for a *prospective*
  student (someone about to study), not a *past* credential being presented as
  proof of qualification — semantically the wrong direction for E33B.
- No fact path for "committed to submit cooperation proof within 90 days" (a
  process/commitment fact, analogous to `process.wants_onshore_conversion` in
  shape but for a different commitment).
**Correction after adversarial review**: this is the strongest case among the six
for needing new facts, but the earlier claim that "no rule — support or review —
can be written safely" without them overstated it. The existing
`review.e33b.expertise-qualification` rule already proves a `HUMAN_REVIEW` gate
can be written today without any of these facts — it defers the certification/
GPA/cooperation check to a human reading the actual documents, the same pattern
`review.e33a.*` and `review.e33c.*` use. What these facts are actually needed for
is **automation** (a future SUPPORT rule) or a more precise `required_facts` list
on the existing review rule — not for a review rule to exist at all.

---

## 6. E33C — Second Home Golden Visa, World-Figure Government Invitation

**Official name [PRIMARY]**: Permenkumham 22/2023 Pasal 59, **amended by
11/2024** (only ayat (2) changed — the definition of "dokumen lain"; ayat (1),
the sponsor clause, is untouched across both versions), governing Pasal 33(2)(j)
angka 3 **with** Penjamin: *"Orang Asing yang merupakan tokoh dunia... diajukan
oleh Orang Asing atau Penjamin... b. bukti penjaminan dari penjamin dari
**instansi pemerintah pusat**"*. Kepmen Lampiran (PDF page 74-75) [PRIMARY]:
*"Tokoh dunia — E33C — Orang asing yang diundang oleh pemerintah karena
ketokohannya"*.

**Important disambiguation not in the mandate's briefing**: **E33C and E33D are
different products with the same "tokoh dunia" label**, easy to conflate. E33C
(Pasal 59, WITH Penjamin from a government instansi, no minimum-investment
figure in the Pasal) is one; **E33D** ("tokoh dunia yang akan mendirikan
perusahaan di Indonesia" — a world figure who WILL establish a company, requiring
USD 25M/50M investment, WITHOUT Penjamin) was originally Pasal 60 — **which
Permenkumham 11/2024 item 17 explicitly repeals** ("Pasal 60 dihapus"). E33D is
outside this mandate's 6 products, but flagged here because (a) it sits in the
same Kepmen table row group as E33C and is the likeliest source of a future
rule-authoring mix-up, and (b) its procedural basis appears to have been
deleted by the 2024 amendment while the 2025 Kepmen classification table still
lists the index — a live discrepancy between the two governing documents that a
future E33D rule (if ever written) would need to resolve, not something this
factbase resolves.

**Penjamin ammesso — mapped to `sponsor.type`**: **GOVERNMENT, verified
[PRIMARY]** — same directness as E33A: "penjamin dari instansi pemerintah pusat"
is explicit statutory text, present in both the 2023 original and the 2024
re-enactment.

**Requisiti congiunti [PRIMARY, Pasal 59(2)]**: "dokumen lain" = an invitation or
statement from a central-government instansi. No stated financial threshold — the
government invitation itself is the qualifying fact, same pattern as E33A.

**Existing rule verdict — corrects a suspicion raised in the mandate, but only
partially, per adversarial review**: the mandate flagged
`review.e33c.central-government-invitation` firing on `intent.purposes ∩
INVESTMENT` (rather than `EMPLOYMENT`, as E33A's twin rule does) as a possible
binding error. The `EMPLOYMENT`-is-wrong part of that suspicion **is** refuted —
Kepmen's Hak clause for E33C (PDF page 74-75) grants *"kegiatan yang berhubungan
dengan investasi, bisnis, atau pembelian barang"* and *"pembahasan, negosiasi,
dan/atau menandatangani perjanjian bisnis"*, with **no "hubungan kerja"
(employment) right anywhere in the row** — unlike E33A. `INVESTMENT` is a
textually-authorized purpose and a valid trigger, not a copy-paste artefact.

But **"matches exactly" overstates it** — corrected here. The rule triggers only
on `intent.purposes ∩ INVESTMENT`; the same Hak clause also authorizes
"pembahasan, negosiasi, dan/atau menandatangani perjanjian bisnis" — i.e.
`BUSINESS_MEETINGS` activity — which the current rule does not intersect against,
so an applicant whose stated purpose is business meetings/negotiation without an
investment purpose would not trigger the review even though the product's own Hak
clause covers that activity. And the extracts available to this file's
adversarial reviewer do not independently confirm `TOURISM`/`FAMILY` in
`covered_purposes` — those two values were read from the pack's own JSON, not
cross-verified against a Hak clause quote. The honest statement is: **valid
trigger, incomplete trigger** — `INVESTMENT` is correctly one of the purposes
that should fire this review, not the only one that should.

**What is NOT verifiable / vocabulary gap**: same shape as E33A — no fact path
for "holds a confirmed government invitation," and no fact path could
meaningfully capture "tokoh dunia" (public-figure prominence) as a self-reported
applicant fact; this is inherently a human-judgment gate on the inviting
government body's side, not something the interview schema should try to encode
as a boolean.

---

## Summary table

| Code | Primary source (Pasal) | Penjamin per source | Pack's current `sponsor_types` | Match? |
|---|---|---|---|---|
| E23U | none dedicated — Kepmen row only | no statutory statement either way | `INDIVIDUAL` | **UNRESOLVED — pack assumption** |
| E23V | none dedicated — Kepmen row only | no statutory statement either way | `GOVERNMENT` | **UNRESOLVED — pack assumption** |
| E28C | Permenkumham 22/2023 Pasal 39/40 | self-filed, no Penjamin attestation required (structural absence, not an explicit "tanpa Penjamin") | `INDIVIDUAL` | **semantic ambiguity — enum semantics for INDIVIDUAL vs. NONE are undocumented; flag for rule author, not a proven mismatch** |
| E33A | Permenkumham 22/2023 Pasal 57 | **GOVERNMENT**, cited verbatim | `GOVERNMENT` | confirmed |
| E33B | Permenkumham 22/2023 Pasal 58 | **NONE**, cited verbatim ("tanpa Penjamin") | `NONE` | confirmed |
| E33C | Permenkumham 22/2023 Pasal 59 | **GOVERNMENT**, cited verbatim | `GOVERNMENT` | confirmed |

Only 3 of 6 (E33A/B/C) have a Penjamin category directly stated in force-of-law
text — E33A and E33C's is the strongest (verbatim "Penjamin ... pemerintah
pusat"), E33B's is equally verbatim but on the negative side ("tanpa Penjamin").
E23U/E23V have no dedicated procedural Pasal at all (consistent with, not proven
by, their "Data Belum Tersedia" status on the DG Immigration's site, retrieved
2026-08-11 this session). E28C's "no Penjamin" reading is well-supported but
structural rather than an explicit statutory denial, and whether the pack's
`INDIVIDUAL` encoding is consistent with that reading depends on an
undocumented enum-semantics question this factbase cannot resolve on its own.

## Vocabulary gaps (all 6 products)

1. No fact distinguishes "employer/sponsor is a natural person" from "employer is
   a company" from "employer is a foreign quasi-governmental body" — needed for
   E23U and E23V, absent from `work.*` and `sponsor.*`.
2. No USD-denominated fact under `investment.*` for a securities-purchase
   commitment (E28C) — the two existing `investment.*_idr` facts are shaped for
   PT PMA paid-up capital, not this pathway. The `secondhome.*_usd` group is the
   nearest structural precedent.
3. No fact for "holds a confirmed central-government invitation" (E33A, E33C) —
   likely correctly left as a `HUMAN_REVIEW`-only gate rather than a new fact,
   but currently undocumented as a deliberate choice.
4. No fact for professional certification, its field, university
   ranking/recency/GPA, or a 90-day cooperation-proof commitment (E33B) — the
   largest gap of the six. Correction after adversarial review: this blocks
   *automation* (a future SUPPORT rule) and a precise `required_facts` list on
   the existing review rule, not the existence of a `HUMAN_REVIEW` rule itself —
   `review.e33b.expertise-qualification` already exists without any of these
   facts, deferring the check to a human reading the documents.
5. `SponsorType` enum values have no documented per-value semantics in
   `enums.py`/`fact_registry.py` beyond the bare name — every ambiguous mapping
   above (E23V government-vs-employer, E28C individual-vs-none) is a judgment
   call with no written definition to appeal to.

---

## Adversarial review

**Seat**: `codex exec -m gpt-5.6-sol -c model_reasoning_effort="xhigh" --sandbox
read-only`, run against a first draft of this file plus verbatim Pasal excerpts
supplied in the prompt (not a re-fetch — the reviewer's sandbox could not resolve
`imigrasi.go.id` when it independently attempted one, so OFFICIAL PORTAL claims
were graded "not independently reproducible in this pass" rather than confirmed
or refuted). The reviewer additionally verified the local Permenkumham 22/2023
and 11/2024 copies' SHA-256 against the rulepack's `source_records` and
cross-read `enums.py`, `fact_registry.py`, and both `rulepack-prod-005` (the prior
sequence) and `rulepack-prod-006` directly from the repo — it was not confined to
the excerpts I handed it.

**First-pass verdict: DO-NOT-SHIP.** 27 findings, roughly half holding the claim
as written ("REGGE") and half requiring a correction — none were "the underlying
legal research is wrong," all were about **overclaiming certainty**: presenting a
structural inference as an explicit statutory statement (E28C's "no Penjamin"),
presenting an unresolved judgment call as merely "plausible" (E23U/E23V's sponsor
category), asserting a causal relationship the text doesn't state (E33A's
"invitation substitutes for the deposit"), overgeneralizing a correct narrow
claim into an incorrect broad one (E33C's purpose-binding "matches exactly" when
it only correctly matches on the employment/investment axis), and one outright
mislabeling (calling Pasal 57/59/61 — which govern the `rumah kedua` family,
`Pasal 33(2)(j)` — "E23-family Pasal"). It also caught a real content gap I had
missed: the Kepmen table's E28C row lists three investment instruments, silently
dropping the fourth (apartment/rumah susun) option Pasal 40(3) grants on the
10-year track.

**Every finding graded MEDIUM or higher has been applied above** — see the
per-product sections and the summary table, both revised in place rather than
appended as errata, so a reader does not have to cross-reference this section
against the claims to know what to trust. The reviewer explicitly logged which
claims it could **not** confirm for lack of network access (the three OFFICIAL
PORTAL claims) as a distinct category from claims it actively refuted — those are
marked with retrieval dates above rather than downgraded, because I *did* execute
those `WebFetch` calls myself in this session (their content is quoted verbatim
earlier in this document from that live call, not from memory or agy).

**What the reviewer found held, unchanged, after full adversarial pressure**: the
USD figures (350k/700k/1M/25M/50M), the 90-day windows, the top-100-university/
GPA≥3.5 detail, the E33A/E33B/E33C Penjamin citations (all three verbatim), the
E33D disambiguation and the Pasal 60 repeal, the E23U/E23V "no dedicated Pasal"
finding, and the rejection of "Peraturan Pemerintah 45/2024" as an unsupported
citation. It found **zero fabricated regulation numbers or URLs** in the
Pasal-level claims — the earlier E33D $25M/$50M figures, the UU 1/1982 citation
(explicitly flagged here as unverified, not asserted as fact), and every other
number it checked against the supplied excerpts were correct.

**Revised verdict after applying the fixes**: the reviewer's own stated
conditional — "after correcting these points, the document would be a SHIP-WITH-
FIXES candidate" — is met; the corrections above are exactly the set it asked
for, applied in place rather than layered as caveats. No new independent
re-review round was run after the fixes (the reviewer's objections were about
overclaiming, not about a wrong underlying fact, so each fix is a direct,
mechanical downgrade of a specific sentence's certainty level, verifiable by
reading the corrected sentence against the same excerpt cited in the finding).
