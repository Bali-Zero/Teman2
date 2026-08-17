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
