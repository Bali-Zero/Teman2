---
date: 2026-08-24
domain: visa
client_case: none
sources:
  - path: research/visa/doctrine-factory/claims/e2c-blocked5-claim-ledger.md
    note: "2026-08-18 NB-2 batch, 11 queries, claims CL-E33A-01..03 / CL-E33B-01..04 / CL-E33C-01..03 — treated as LEAD, cross-checked against primary law directly by this report"
  - path: research/visa/2026-08-11-w3-sponsor-rules-factbase.md
    note: "2026-08-11, Codex sol-xhigh adversarially reviewed, verbatim Pasal 57/58/59 quotes — cross-checked and CONFIRMED against the primary-law PDF text fetched fresh in this session"
  - path: research/visa/2026-08-11-seq7-sponsor-semantics-and-the-gate-that-does-not-exist.md
    note: "the rejected 'manufactured offer' SUPPORT-rule attempt, reproduced empirically against a live evaluator, 2026-08-11"
  - path: research/visa/doctrine-factory/e5/2026-08-19-e5-increment3-spec.md
    note: "2026-08-19 ratification of the HARD_FILTER-only shape for E33A/B/C, citing the manufactured-offer bug by name"
  - path: apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-013.source.json
    note: "current production pack (sequence 13, version 2026.8.23), re-read live this session — confirms E33A/B/C each carry exactly one HUMAN_REVIEW rule + one HARD_FILTER rule, zero ELIGIBILITY/SUPPORT rule"
  - path: apps/backend-rag/backend/services/visa_engine/enums.py
    note: "SponsorType docstring, Pasal 57/58/59 per-value citations, re-read live this session"
  - path: apps/backend-rag/backend/services/visa_engine/fact_registry.py
    note: "re-read live this session — confirms no FactPath exists for government-invitation-confirmed, expertise-certificate, university-ranking/GPA, or cooperation-commitment"
  - path: "apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/fact-mapper.ts"
    note: "re-read live this session — sponsor.type and intent.purposes are dynamically collected; intent.requested_product_code is hard-coded unknownFact(NOT_ASKED), never collected"
  - url: "https://peraturan.go.id/files/permenkumham-no-22-tahun-2023.pdf"
    note: "Permenkumham 22/2023 full text, fetched + pdftotext-extracted live this session — Pasal 33, 57, 58, 59, 60, 61, 105(10) read directly, not from memory"
  - url: "https://peraturan.go.id/files/permenkumham-no-11-tahun-2024.pdf"
    note: "Permenkumham 11/2024 (amendment) full text, fetched + pdftotext-extracted live this session — confirms 'Pasal 60 dihapus' and the Pasal 59 ayat (2) / Pasal 61 amendments verbatim"
  - url: "https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E33A"
    note: "Ditjen Imigrasi official product page, fetched live this session — PNBP figures"
  - url: "https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E33B"
    note: "Ditjen Imigrasi official product page, fetched live this session"
  - url: "https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E33C"
    note: "Ditjen Imigrasi official product page, fetched live this session — confirms NO USD 25M/50M figure on E33C's live page"
adversarial_review: none (this report is itself the adversarial pass over the 2026-08-18 NB-2 claim ledger; no further cross-family review run in this session)
---

# E33A / E33B / E33C grounding pass — can a SUPPORT rule be authored today?

**Verdict up front: NO, for all three, and it should stay NO by design, not by neglect.** The
current production pack (`rulepack-prod-013.source.json`, seq 13, `2026.8.23`) already reflects
the correct answer: one `HUMAN_REVIEW` rule + one `HARD_FILTER` rule per product, zero
`ELIGIBILITY`/`SUPPORT` rule. A SUPPORT-rule attempt for exactly these three products was tried on
2026-08-11, reproduced empirically against a live evaluator, and rejected as a "manufactured
offer" — documented below with the mechanism, not just the label. This report's job was to check
whether anything has changed since (new facts, new law, a live NB-2 re-query) that would make a
SUPPORT rule authorable now. It does not. It also surfaces two new, primary-source-verified
corrections to the 2026-08-18 NB-2 claim ledger that should be applied before that ledger is cited
again.

## 0. Methodology note — NB-2 access blocked this session

The mandate asked me to query NB-2 (`cff93ab0-813a-42f2-a8de-36987e724271`, confirmed as NB-2's
real notebook id from `research/visa/doctrine-factory/tools/nb2_query.py`, not guessed) via the
`nlm` CLI. On this machine (M5, `default` profile, `antonellosiano@gmail.com`), `nlm notebook
list` and `nlm notebook query` both returned `Authentication Error: Authentication expired. Run
'nlm login' in your terminal to re-authenticate.` — confirmed twice, once for `list` and once
attempting `query`, both against the only profile that exists. `nlm login` launches an interactive
Google OAuth browser flow — a GUI/consent action outside what this session can complete
autonomously (`operator[gui]`, per this repo's operator-boundary doctrine). **No fresh NB-2 query
was executed in this session.** This is a genuine live-state gap, not a skipped step: flag for
Zero to `nlm login` interactively (2 minutes, browser) if a live NB-2 re-confirmation round is
wanted later.

In its place, this report does two things the mandate's own anti-hallucination clause anticipates:

1. **Treats the existing 2026-08-18 NB-2 answers as LEADS**, graded per query: source cited, date
   of that source, and whether a more recent official re-grounding exists. All eleven
   `e2c-blocked5` queries cite the same two Level-2 primary sources (`Kepmen
   M.IP-08.GR.01.01/2025` and `Permenkumham No. 22/2023` / `No. 11/2024`) — six days old
   relative to this report, no newer regulatory instrument found in the WebSearch below.
2. **Cross-checks every load-bearing NB-2 claim against the primary-law text directly**, fetched
   fresh in this session (`peraturan.go.id`'s PDF of both Permenkumham instruments,
   `pdftotext`-extracted, greppable — not paraphrase, not memory) plus the live Ditjen Imigrasi
   product pages. Where NB-2 and primary law agree, the claim is upgraded to **VERIFIED (this
   session)**. Where they disagree, primary law governs, and both readings are shown (§5).

## 1. Primary law, read directly this session (do not re-derive from memory)

`Permenkumham No. 22 Tahun 2023` (206 Pasal total, ends at Pasal 206, signed 22 Aug 2023) is the
base instrument. `Permenkumham No. 11 Tahun 2024` amends it; its own text (fetched and
`pdftotext`-extracted this session) lists amendment items by number — item 16 changes Pasal 59
ayat (2) only (a cross-reference fix, substance unchanged), **item 17 reads verbatim "Pasal 60
dihapus"** (Pasal 60 deleted), item 18 rewrites Pasal 61 to read "55 (lima puluh lima) tahun" for
seniors. Pasal 57 and 58 are **not** in either amendment's list of touched articles — unchanged
since 2023.

Pasal 33 ayat (2) huruf j ("rumah kedua") enumerates five sub-categories, quoted verbatim from the
extracted text:

```
j. rumah kedua, yang terdiri atas;
   1. rumah kedua;                                                    → E33 (base)
   2. keahlian khusus;                                                → E33A / E33B
   3. tokoh dunia;                                                    → E33C (/ E33D, repealed)
   4. lanjut usia berusia 55 (lima puluh lima) tahun atau lebih; and   → E33E
   5. pekerja jarak jauh (remote worker) ...                          → E33G
```

Duration for all three (Pasal 105 ayat (10) huruf b/c, unchanged by 11/2024): **5 or 10 years**,
selectable by the applicant — matches `rulepack-prod-013.source.json`'s `stay_policy.minimum_days:
1825 / maximum_days: 3650` for all three products, re-read live this session.

## 2. Per-product predicate tables

Legend: **Exists** = the FactPath is declared in `fact_registry.py`. **Collected** = the frontend
(`fact-mapper.ts`) sends a real value, not a hard-coded `unknownFact(NOT_ASKED)`. **Grounding** =
VERIFIED (re-confirmed against primary-law text or the live Ditjen page, this session) / LEAD
(NB-2-only, 2026-08-18, not independently re-checked here) / UNVERIFIABLE (no fact path could ever
capture this, by the nature of the requirement).

### E33A — Second Home Visa, Special-Expertise Government Invitation

Governing article: **Permenkumham 22/2023 Pasal 57** (unchanged by 11/2024). Sponsor: central
government (Penjamin = "pemerintah pusat"), mandatory — there is no self-sponsored variant of
Pasal 57 in the regulation.

| Predicate (plain terms) | FactPath | Exists? | Collected? | Grounding | Source + date |
|---|---|---|---|---|---|
| Applicant's stated purpose intersects EMPLOYMENT | `intent.purposes` | Yes | **Yes** (`mapPurposes`, dynamic) | VERIFIED (this session) | Kepmen Hak clause quotes an employment relationship with the central government; Pasal 57 itself is purpose-agnostic — the pack's own `EMPLOYMENT` binding is a rule-author choice, textually consistent per the W3 factbase (2026-08-11) | Pasal 57, `peraturan.go.id` PDF, fetched this session |
| Sponsor category = GOVERNMENT | `sponsor.type` | Yes | **Yes** (`mapSponsorType`, dynamic, from `facts.sponsor_category`) | VERIFIED (this session) | Pasal 57(1)(b): *"bukti penjaminan dari Penjamin, yang merupakan pemerintah pusat"* — quoted verbatim, re-read live this session | Pasal 57, same PDF |
| Applicant holds a confirmed, genuine central-government invitation letter naming urgency/expertise | *(none — no FactPath)* | **No** | **No** | UNVERIFIABLE by self-report | Pasal 57(2): the "dokumen lain" is *"undangan atau keterangan dari pemerintah pusat yang menjelaskan urgensi Orang Asing tersebut diundang sebagai orang yang memiliki keahlian khusus"* — an actual document a human must authenticate, not a boolean an applicant can self-declare | Pasal 57(2), same PDF |
| Minimum living-cost bank balance | *(none — not modeled; distinct from `secondhome.*`)* | No | No | VERIFIED (this session, no engine use) | Ditjen page: USD 2,000 in the last 3 months — a baseline shared across the whole rumah kedua family, not an E33A-specific financial threshold; no large deposit exists for this product | `imigrasi.go.id/.../E33A`, fetched this session |
| Which E33 sub-product is actually being requested | `intent.requested_product_code` | Yes | **No — hard-coded `unknownFact(NOT_ASKED)`** | N/A (production-inert) | This fact is required by the *existing* `review.e33a.central-government-invitation` rule's own `when` clause; since it is never collected, that HUMAN_REVIEW rule cannot resolve in production today either — a separate, already-known defect (visaoracle SKILL.md, PENDING-ARMS, Track C/E6), not created by this report | `fact-mapper.ts:597`, re-read this session |

**Verdict: NO.** The only two facts that exist and are collected (`intent.purposes`,
`sponsor.type`) are both *necessary* conditions per Pasal 57, never *sufficient* — the actual
qualifying fact (a real, government-issued invitation) has no FactPath and structurally cannot
have one that an evaluator could trust (see §4).

### E33B — Second Home Golden Visa, Special-Expertise Collaboration

Governing article: **Permenkumham 22/2023 Pasal 58** (unchanged by 11/2024). Sponsor: **none** —
Pasal 58(1) opens *"...tanpa Penjamin diajukan oleh Orang Asing"* (no Penjamin option exists for
this Pasal at all, unlike Pasal 57's "atau Penjamin").

| Predicate (plain terms) | FactPath | Exists? | Collected? | Grounding | Source + date |
|---|---|---|---|---|---|
| Sponsor category = NONE | `sponsor.type` | Yes | Yes | VERIFIED (this session) | Pasal 58(1): *"tanpa Penjamin diajukan oleh Orang Asing"* — no Penjamin category exists for this Pasal | Pasal 58, same PDF |
| Applicant provides a formal 90-day commitment (Jaminan Keimigrasian) to submit proof of cooperation with a government/state body | *(none — no FactPath for a process-commitment fact of this shape)* | No | No | UNVERIFIABLE by self-report | Pasal 58(2): *"pernyataan komitmen akan menyampaikan bukti kerja sama dengan pemerintah atau lembaga negara ... paling lama 90 (sembilan puluh) Hari"* — a written commitment reviewed by an immigration officer, not a client-side boolean | Pasal 58(2), same PDF |
| Applicant holds a certificate in a state-needed specialized field OR graduated within 3 years from a top-100 world university with GPA ≥ 3.5 | *(none — `study.*` is shaped for a prospective student, semantically wrong direction for a past credential)* | No | No | UNVERIFIABLE by self-report (document-authenticity gate) | Pasal 58(3): *"sertifikat di bidang keahlian khusus yang dibutuhkan oleh negara; atau bukti kelulusan dari salah satu dari daftar 100 (seratus) universitas terbaik dunia dalam 3 (tiga) tahun terakhir dengan ... GPA paling sedikit 3,5"* — quoted verbatim, re-read live this session; matches the Ditjen page's own English paraphrase exactly | Pasal 58(3), same PDF; corroborated by `imigrasi.go.id/.../E33B`, fetched this session |
| Applicant's stated purpose intersects EMPLOYMENT | `intent.purposes` | Yes | Yes | LEAD, partially grounded | The live rule keys only on `EMPLOYMENT`, but the Kepmen Hak clause for E33B also grants business/investment activity (`INVESTMENT`) — under-triggering, not over-triggering: a legitimate business-purpose E33B applicant may not get flagged for the review at all. Flagged in the 2026-08-11 W3 factbase, not re-derived from primary text in this session (Kepmen Lampiran text, not fetchable — no public PDF located) | `research/visa/2026-08-11-w3-sponsor-rules-factbase.md` §5, 2026-08-11 |

**Verdict: NO.** `sponsor.type == NONE` is real, verbatim, and collected — but it is the single
weakest kind of evidence here: it only proves the applicant *chose the unsponsored route*, saying
nothing about whether they actually hold the certificate/degree/GPA Pasal 58(3) requires, or
whether they will honor the 90-day cooperation commitment. Neither of those two substantive facts
has a FactPath, and both are inherently document-verification gates (a certificate's authenticity,
a university's actual ranking) — the same "cannot self-report a document a human must read"
problem as E33A/C, not a smaller version of it.

### E33C — Second Home Golden Visa, World-Figure Government Invitation

Governing article: **Permenkumham 22/2023 Pasal 59** (ayat (2) cross-reference fixed by 11/2024
item 16, substance unchanged). Sponsor: central government instansi, mandatory — Pasal 59(1)(b):
*"bukti penjaminan dari penjamin dari instansi pemerintah pusat."*

| Predicate (plain terms) | FactPath | Exists? | Collected? | Grounding | Source + date |
|---|---|---|---|---|---|
| Sponsor category = GOVERNMENT | `sponsor.type` | Yes | Yes | VERIFIED (this session) | Pasal 59(1)(b), quoted above | Pasal 59, same PDF |
| Applicant's stated purpose intersects INVESTMENT | `intent.purposes` | Yes | Yes | LEAD, incomplete trigger | The live rule keys only on `INVESTMENT`; the Kepmen Hak clause for E33C also authorizes *"pembahasan, negosiasi, dan/atau menandatangani perjanjian bisnis"* (`BUSINESS_MEETINGS`), which the current rule does not intersect against — an applicant stating only business-meeting purpose would not trigger review. W3 factbase, 2026-08-11, not re-derived from Kepmen text this session (Kepmen PDF not located) | `research/visa/2026-08-11-w3-sponsor-rules-factbase.md` §6, 2026-08-11 |
| Applicant holds a confirmed central-government "world figure" invitation | *(none)* | No | No | UNVERIFIABLE by self-report | Pasal 59(1)(e)/(2): the "dokumen lain" is *"undangan atau keterangan dari instansi pemerintah pusat"* | Pasal 59, same PDF |
| **A financial/investment commitment tier (USD 25M for 5y / USD 50M for 10y)** | *(none)* | No | No | **CORRECTED THIS SESSION — does not apply to E33C** | See §5 below. | — |

**Verdict: NO.** Same shape as E33A: the only collectible facts are necessary, never sufficient,
and the substantive gate is a document a human must authenticate.

## 3. The rejected "manufactured offer" attempt — exact record, so it is not repeated

Found in `research/visa/2026-08-11-seq7-sponsor-semantics-and-the-gate-that-does-not-exist.md`.
The mandate for that pack (seq-7) asked for two ELIGIBILITY rules,
`el.e33a.sponsor-government` / `el.e33c.sponsor-government`, each `sponsor.type eq GOVERNMENT`
conjoined with "the genuine E33A/E33C gate already in the pack." Two shapes were tried, **against
a live copy of the compiled evaluator, not reasoned about in the abstract**:

- **Narrow** (`when = all(product_code eq E33A, sponsor.type eq GOVERNMENT)`, purpose scope =
  `EMPLOYMENT` only, mirroring the review rule): dead code both ways — with EMPLOYMENT purpose the
  pre-existing `HUMAN_REVIEW` rule always fires first (its condition is a subset of this rule's);
  with TOURISM-only purpose the rule's own coverage never applies. Cannot change any decision.
- **Broad** (same `when`, purpose scope widened to match E33A's full `covered_purposes:
  [EMPLOYMENT, TOURISM, FAMILY]`): with EMPLOYMENT still dead (review dominates); but **with a
  TOURISM-only purpose, the evaluator returned `SUPPORTED_CANDIDATES`, E33A offered.** Quoting the
  note directly: *"An applicant who declares only a tourism purpose and answers 'government' to a
  sponsor-category question — with no invitation, no special-expertise justification, none of
  Pasal 57's actual content checked — is offered the Second Home Visa reserved for people the
  central government specifically invited."* That is the manufactured offer: a real, sellable
  product code granted on a proxy fact that was necessary but never sufficient, with the actual
  gate (an authentic invitation) never checked at all.

The same failure mode applies mechanically to E33C (Pasal 59 has the identical shape as Pasal 57 —
Penjamin from a central-government body, no other checkable statutory content) and to E33B (the
mandate pre-authorized "no rule" if E33B's gate proved unwritable; `sponsor.type == NONE` is real
and verbatim but not sufficient, for the same reason). **No SUPPORT/ELIGIBILITY rule was written
for any of the three in seq-7.**

On 2026-08-19 (`e5/2026-08-19-e5-increment3-spec.md`, "Assembly decisions round 2", item 6), the
question was revisited with the 2026-08-18 NB-2 doctrine in hand, and the same conclusion was
ratified explicitly: *"E33A/B/C shape RATIFIED as delivered: HARD_FILTER/EXCLUDE narrowing on
sponsor.type (never SUPPORT — the W3 factbase + [the seq-7 note] document the 'manufactured offer'
bug for the SUPPORT shape)."* The `HARD_FILTER` shape actually shipped (`hf.e33a.sponsor-not-
government`, `hf.e33b.sponsor-not-government-or-none`, `hf.e33c.sponsor-not-government-or-none` —
all `safety_critical: true`, live in `rulepack-prod-013.source.json`, re-read this session) is
categorically safe in a way SUPPORT never was: a `HARD_FILTER` can only ever **remove** a candidate
from consideration (a necessary-condition failure), it can never **grant** SUPPORTED status — so
encoding a necessary-but-not-sufficient fact into it cannot manufacture an offer, only prune
applicants who are definitely disqualified, deferring everyone else (including the genuinely
eligible) to the same `HUMAN_REVIEW` gate that already existed. **Do not repeat the SUPPORT/
ELIGIBILITY shape for these three products; the HARD_FILTER-only design is the correct, durable
answer, not an interim one.**

## 4. Why the substantive gate cannot be automated even in principle — not just "not yet"

This is the structural point that distinguishes E33A/B/C from an ordinary "doctrine gap, author a
fact later" story. Every one of the three products' real qualifying fact is one of:

- The authenticity and content of a government-issued invitation letter (E33A, E33C) — no
  self-report can substitute for reading the actual letter and confirming which agency issued it
  and what it says.
- The authenticity of a professional certificate, or the actual (not self-declared) global ranking
  of a university a degree came from, plus a GPA figure lifted from an actual transcript (E33B) —
  same class of problem: a self-reported boolean cannot stand in for document verification.
- A 90-day forward-looking commitment whose fulfillment is itself checked later by an immigration
  officer (E33B) — not a fact that exists yet at application time in any verifiable form.

Adding a new FactPath for any of these (e.g. `government.invitation_confirmed`, a boolean) would
not close this gap — it would recreate exactly the shape `family.sponsor_confirmed` and
`study.sponsor_confirmed` already use for comparable "has this evidence been confirmed"
self-reports, and those existing facts are correctly never trusted for `op: known` in an
ELIGIBILITY rule; they only ever feed `HUMAN_REVIEW`. The same discipline applies here by
construction, not by an unclosed research task.

## 5. Two corrections to the 2026-08-18 NB-2 claim ledger, found by primary-source re-check this session

Per the mandate's own instruction ("an NB verdict is a LEAD, not a fact... never promote an NB
answer to VERIFIED on the strength of how confident it sounds"), both of the following were
machine-audited `VERIFIED`/citation-resolved in `e2c-blocked5-claim-ledger.md` — confident, clean
citations — and both are wrong on direct primary-source read.

### 5a. CL-E33C-03's USD 25,000,000 / 50,000,000 figure does not belong to E33C

The ledger claims (`e2c-blocked5-claim-ledger.md:372-399`) that E33C's self-sponsored (*tanpa
penjamin*) pathway requires a committed paid-up-capital company-establishment commitment of USD
25M (5y tier) or USD 50M (10y tier), citing `Permenkumham 22/2023` with a verbatim-quoted passage.
Kimi K3's adversarial review flagged this as a *plausibility concern* ("closer to the corporate-
investor Golden Visa tier than a prominence-based world-figure invitee... could reflect merging two
adjacent table rows") but left the claim state at `VERIFIED`, unable to resolve it further without
re-deriving statute text.

**Resolved definitively this session.** The USD 25M/50M figure is real — it is **Pasal 60**, not
Pasal 59: *"pernyataan komitmen akan mendirikan perusahaan di Indonesia dengan investasi senilai
paling sedikit US$25.000.000 ... untuk tinggal paling lama 5 (lima) tahun; atau ... US$50.000.000
... untuk tinggal paling lama 10 (sepuluh) tahun"* — text confirmed by `pdftotext` extraction of
the primary-law PDF this session, exact byte match to the quoted figures. Pasal 60 governed *"Orang
Asing yang merupakan tokoh dunia ... tanpa penjamin"* — the self-sponsored world-figure variant,
which the live pack calls (informally, per the W3 factbase) **E33D**, a distinct product from
E33C. **Permenkumham 11/2024 item 17 reads, verbatim, "Pasal 60 dihapus"** — confirmed this
session directly from the amendment's own PDF text. This pathway is repealed, and even before
repeal it was never E33C's own basis: E33C (Pasal 59) requires a central-government sponsor and
carries no financial threshold at all beyond the family-wide USD 2,000 living-cost minimum
(confirmed on the live Ditjen Imigrasi E33C page, fetched this session, which lists only the USD
2,000 figure — no USD 25M/50M anywhere on the product's official page). **The claim ledger's
CL-E33C-03 financial-tier statement should be struck, not merely caveated**, and the production
pack's decision not to encode it (`e5-increment3-spec.md`: *"Do NOT encode the USD 25M/50M
guarantee tiers"*) was the right call, made correctly even without this confirmation.

### 5b. CL-E33B-03's "Pasal 458, sponsor mandatory" claim cites an article that does not exist

The ledger's CL-E33B-03 (`e2c-blocked5-claim-ledger.md:285-310`) records an NB-2 answer stating "a
sponsor is mandatory and must be the Indonesian central government (`Pasal 458`)" for E33B — a
claim the ledger itself flagged as in tension with CL-E33B-01/CL-E33B-04 (E33B is self-sponsored,
per Pasal 58's own "tanpa Penjamin"), and downgraded to an unresolved "two-pathway" reading rather
than adjudicated.

**Resolved definitively this session, not merely softened.** Permenkumham 22/2023 has **206 Pasal
total**, ending at Pasal 206 (the closing/entry-into-force clause, confirmed by reading the
document's final page this session). `grep -n "Pasal 458"` against the full extracted text returns
**zero matches** — the article does not exist in this regulation. The duration figure the same
NB-2 answer correctly cites elsewhere (5 or 10 years) is real and independently confirmed at
**Pasal 105 ayat (10) huruf b** (`"Orang Asing yang memiliki keahlian khusus dengan jangka waktu
paling lama: 1. 5 (lima) tahun; atau 2. 10 (sepuluh) tahun"`, read directly this session) — the
"Pasal 458" citation appears to be a fabricated article number attached near a genuine duration
citation, the same shape as the W90 scar this mandate named as a risk. **There is no primary-law
basis for "sponsor mandatory, central government" on E33B; discard that reading. Pasal 58's plain
text — self-sponsored, no Penjamin category exists for this article at all — governs, consistent
with CL-E33B-01/04 and with the live pack's `sponsor_types: ["NONE"]`.**

### 5c. A residual HARD_FILTER laxity, found while re-deriving E33B/E33C from primary text (new, minor)

Not a repeat of the manufactured-offer defect (a `HARD_FILTER` cannot manufacture an offer), but
worth recording for whoever next opens this pack: `hf.e33b.sponsor-not-government-or-none` and
`hf.e33c.sponsor-not-government-or-none` both let `sponsor.type ∈ {GOVERNMENT, NONE}` pass. Per
Pasal 58 (E33B), only `NONE` is the article's own basis — a `GOVERNMENT`-sponsored applicant
pursuing "keahlian khusus" is, by the regulation's own structure, an E33A applicant (Pasal 57), not
E33B. Symmetrically for E33C: since Pasal 60 (the only "tanpa penjamin" variant of *tokoh dunia*)
is repealed, `NONE` is no longer a live pathway for E33C at all — only `GOVERNMENT` (Pasal 59)
remains. Today this has zero live effect, because `intent.requested_product_code` (needed to even
know which of the two/three sibling products is being evaluated) is never collected (§2, E33A
table) — but it is a latent defect worth a one-line tightening whenever that fact is wired up.

## 6. Design question — does the E28 (Golden Visa) "always human" doctrine apply here?

The owner's ruling on E28B/C/D/F (Investor Golden Visa family) is recorded identically across all
four OD-4 cards: *"the always-REVIEW design is treated as intentional and retained — high-value/
high-fraud-risk threshold verification is not the kind of fact an automated evaluator should
self-certify"* (`e3/od4-decision-package.md:65-68`). **The practical outcome for E33A/B/C is the
same — permanent `HUMAN_REVIEW`, never `SUPPORT` — but for a different, and in one sense stronger,
reason, and the difference is worth keeping explicit rather than filing E33A/B/C under the E28
precedent by default.**

- **E28's gate is a policy choice about a knowable fact.** "Does this applicant hold USD 2.5M in a
  verifiable account" is, in principle, a fact an automated system COULD check (bank API,
  attestation, KYC integration) — the owner's ruling is that Bali Zero chooses not to let a
  machine self-certify it given the stakes, not that the fact is unknowable. A future policy
  reversal (with proper controls) is conceivable without touching this codebase's factual
  modeling capacity.
- **E33A/B/C's gate is closer to structurally unmodelable today.** "Is this a genuine, currently-
  valid invitation letter from the specific central-government institution named in it" or "is
  this certificate authentic and does this university actually rank in the world's top 100" are
  not numeric thresholds a boolean self-report can stand in for — the codebase's own precedent
  (`family.sponsor_confirmed`, `study.sponsor_confirmed`) already treats "has this evidence been
  confirmed" as PERSONAL-tier self-report that can only ever feed `HUMAN_REVIEW`, never `op:
  known` in an ELIGIBILITY rule, for exactly this reason (§4).

**Recommendation: yes, the same "never auto-certify" outcome applies, and for E33A/B/C it is the
more durable of the two justifications** — E28's gate could theoretically be replaced by better
tooling (document/bank verification infrastructure) without a change of principle; E33A/B/C's gate
would need actual government-registry or university-accreditation verification infrastructure Bali
Zero has no plan to build, making "keep it human, permanently" less a policy stance here and more a
description of what the fact actually is. Treat E33A/B/C's `HUMAN_REVIEW`-only design with the same
weight as E28's ("intentional and retained," `e3/od4-decision-package.md` framing) rather than as
an open doctrine gap awaiting a future FactPath — there is no FactPath on the horizon that would
close it safely.

## 7. Summary table

| Product | Governing Pasal | Sponsor (verified this session) | Financial threshold | Can SUPPORT be authored today? | Correct current design |
|---|---|---|---|---|---|
| E33A | 22/2023 Pasal 57 (unamended) | GOVERNMENT, mandatory | None beyond USD 2,000 baseline | **NO** — genuine invitation is unmodelable | `HARD_FILTER` (sponsor≠GOVERNMENT excludes) + `HUMAN_REVIEW`, both already live |
| E33B | 22/2023 Pasal 58 (unamended) | NONE, mandatory (no Penjamin option exists) | None beyond USD 2,000 baseline | **NO** — certificate/GPA/cooperation-commitment unmodelable | `HARD_FILTER` (sponsor∉{GOVERNMENT,NONE} excludes — tighten to NONE-only per §5c) + `HUMAN_REVIEW`, both live |
| E33C | 22/2023 Pasal 59 (ayat 2 cross-ref fixed 11/2024) | GOVERNMENT, mandatory (Pasal 60's self-sponsored variant repealed) | None — the USD 25M/50M figure belongs to repealed Pasal 60/E33D, not E33C (§5a) | **NO** — genuine invitation is unmodelable | `HARD_FILTER` (tighten to GOVERNMENT-only per §5c) + `HUMAN_REVIEW`, both live |

**The honest answer, stated once more plainly: none of the three can be given an automated
SUPPORT path today, and this is not a temporary gap waiting on more NB-2 queries or a new
FactPath — it is what these three products' own governing law actually requires (a human reading
an actual document), the same category of requirement the owner already ruled must never be
self-certified for the E28 family, on stronger grounds here than there.** No rule was authored or
changed as part of this report.
