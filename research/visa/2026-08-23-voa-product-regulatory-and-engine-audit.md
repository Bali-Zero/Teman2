---
date: 2026-08-23
domain: visa
client_case: none
sources: 32
adversarial_review: codex
---

# GARUDA VOA — regulatory truth-sheet refresh + engine audit (2026-08-23)

> **Post-merge correction notice (2026-08-23, fix-forward).** This document merged to `main`
> (commit `f26bd5a5f`, PR #4681, 13:31Z) before a completed adversarial review's findings had been
> applied: the PR was converted to draft to hold it at 13:21Z, but it had already entered the merge
> queue at 13:16Z, and drafting a queued entry does not eject it. This capture is now fixed
> forward, in place — nothing is silently rewritten. Every correction below is marked inline with
> what changed and why; the original text is recoverable from git history on this file
> (`git show f26bd5a5f:research/visa/2026-08-23-voa-product-regulatory-and-engine-audit.md`). The
> single most consequential fix is in §1.2: the original text called the PricingTool client price a
> service fee separate from PNBP — backwards, and a real double-charge risk. Full accounting in the
> **Adversarial review** section (Pass 2, Codex).

## 0. What this is, and what fed it

This is the research capture for one ring of the S14 GARUDA-VOA ULTRA-RESEARCH mandate (Mini,
2026-08-23): a regulatory refresh against primary sources, an independent code audit of the
`garuda_flow` engine, an adversarial red-team pass, and a legal-premise refuter pass — reconciled
by an empirical grader that re-ran the actual code. Five artifacts fed this document, all produced
earlier in the same session, all read in full or to their actual end before writing this:

- **G1** — file:line audit of the engine/backend/UI as it stands on `origin/main` (baseline
  commit `665bfd40d`, PR #4344, which retired the public VOA funnel and left GARUDA as an
  owner-only internal preview tool).
- **G2** — Claude WebSearch/WebFetch + grounded-RAG regulatory pass against `imigrasi.go.id`.
- **R1** — Codex `gpt-5.6-sol` (xhigh) adversarial red-team of the engine, run via `ssh pro` (its
  own transcript is prefixed `[Pro]` on the final verdict line — Codex is auth-dead on Mini).
- **R2** — Kimi K3 refuter, run locally on Mini, judging the LEGAL PREMISES behind R1's findings
  (not the code). **This run was cut off by a timeout mid-sentence** (55 lines, ends "The D-7
  figure" with no closing punctuation). *(Corrected 2026-08-23, post-merge — the original line here
  read "What did complete (claims A–F) is used below," which contradicted §6's own admission that
  claim E is partial and claim F is absent; see the Adversarial review section, Pass 2.)* R2
  completed claims A–D; claim E is **PARTIAL** (cut off mid-reasoning — used below as
  real-but-incomplete, never as silence-implies-agreement); claim F was **never written up by R2 in
  its own words** at all. F's CONFIRMED verdict used below and in §3/§1.6 is V1's conductor-layer
  annotation, recorded before the transcript ended — not a completed Kimi sign-off.
- **V1** — an empirical grader that re-executed the engine against every R1 finding inside the
  actual `.venv`, and folded in R2's legal verdicts where R2 reached them, producing a reconciled
  table with a "conductor" layer resolving two of R1's seven findings.

**Arsenal degradation, declared up front** (G2's own note, corroborated independently within R1
itself via its `[Pro]` prefix): on Mini, `agy` and `codex` are auth-dead and NotebookLM MCP is not
installed at all. This ring therefore has **no NotebookLM ground-truth leg** — every regulatory
claim below rests on live `imigrasi.go.id`-family primary fetches and the grounded RAG tools
(`nuzantara-knowledge`), never on NB. `codex` was rescued by routing through `ssh pro` (visible in
R1's own transcript). `agy`/Gemini answered directly (R3). Kimi (R2) ran locally but timed out
before finishing its own claim E and before addressing claim F's write-up. None of this is fatal
to the findings that did complete — but a reader must be able to see exactly which leg is thin.

---

## 1. Regulatory truth-sheet, refreshed

### 1.1 B1 VOA core rules
`[PRIMARY]` `imigrasi.go.id/wna/daftar-visa-indonesia/B1` (WebFetch, 2026-08-23, via G2): initial
stay **"maksimal 30 hari, dihitung sejak tanggal kedatangan"**, single entry (**"satu kali masuk ke
Indonesia"**), extendable once (**"dapat diperpanjang satu kali"**) to a **"maksimal 60 hari"**
total. eVOA validity **"90 hari sejak diterbitkan"** for use before travel. Legal basis for these
visa/stay-permit rules: **Permenkumham RI No. 11 Tahun 2024, amending Permenkumham 22/2023**.
*(Corrected 2026-08-23, post-merge: the original line here read "any material still citing the
older Permenkumham 44/2015 is stale," fusing two separate regulatory chains — see Adversarial
review, Pass 2.)* **44/2015 is a different chain entirely** — it governed border/entry-exit
inspection, not visas or stay permits, and was repealed separately by **Permenkumham 9/2024**.
Material citing 44/2015 for entry/exit inspection is stale (superseded by 9/2024); material citing
44/2015 for visa/stay-permit rules was never on the right chain to begin with (that has always been
22/2023 → 11/2024). Do not fuse the two.
Cross-checked clean against `mcp__nuzantara-knowledge__get_visa_details("b1")` (RAG, 2026-08-23,
via G2): 30 days extendable to 60, eVOA validity 90 days from issuance, extension_count 1,
extension_duration 30 days.

### 1.2 PNBP — *Biaya*, exact index strings, never recomposed from PP 45/2024 components
Two instruments retrieved two different pages this turn, and neither should be silently merged
into an invented "combined" figure — that is precisely the mistake a prior research run made by
recomposing the fee from PP 45/2024 components instead of quoting the printed index. Both strings
below are verbatim, as printed, with their own source:

> **Issuance** — *"Biaya visa B1 Rp 500.000 (untuk 30 hari)"* — plus a listed *"Biaya Verifikasi
> I/II Rp 0"*. Source: `imigrasi.go.id/wna/daftar-visa-indonesia/B1`, WebFetch, 2026-08-23 (G2).
> G2's own caveat, carried forward: this page's fetch did **not** surface a discrete "Biaya
> perpanjangan" line, so the extension leg is **not independently re-confirmed on this specific
> index field** by G2's pass.
>
> **Extension** — *"Rp 500.000,- per permohonan"*. Source: `ngurahrai.imigrasi.go.id/layanan-wna/`,
> WebFetch, 2026-08-23 (R3/agy) — also cross-listed at `evisa.imigrasi.go.id/web/visa-selection`
> (the catalogue data endpoint).

Read together: the extension PNBP figure (Rp 500.000) is primary-sourced by R3 from the Ngurah Rai
page even though G2's own B1-index fetch didn't carry it — the two passes are complementary, not
contradictory, and both matter for the record.

**PricingTool client price — corrected 2026-08-23, post-merge adversarial review (Codex, Pass 2;
full accounting in the Adversarial review section).** The paragraph originally here asserted that
IDR 790,000/850,000 were "a Bali Zero service fee, not a government fee" and told the reader to
keep it "visibly separate" from the PNBP block above, as if the client price excluded the
government fee. **That was false, and inverted the actual contract — a reader who acted on it would
add the PNBP on top and double-charge the client.** `mcp__nuzantara-knowledge__search_service_pricing`
(RAG, 2026-08-23, via G2) confirms PricingTool lists **B1 VOA issuance = IDR 790,000** and **B1 VOA
Extension = IDR 850,000**, unchanged since 2026-07-24 — and both are exact, **ALL-INCLUSIVE**
customer quotes, PNBP already inside. This is established two ways: `apps/mouth/e2e/book-pricing.spec.ts:126`
is a live test named *"public visa service cards expose only exact all-inclusive PricingTool
rows"*, and in `apps/mouth/data/bali-zero-prices.json` the sibling A1 row uses its `notes` field to
say "No Bali Zero service fee — visa-free arrival" — i.e. that field is where fee-composition is
declared, and the B1 issuance/extension rows leave it empty, inheriting the file's all-inclusive
contract. The owner confirmed this directly (Zero, 2026-08-23): 790k is the client price with the
PNBP already inside it.

**Do not add the PNBP figures above on top of 790k/850k, and do not infer a government/service
split from the two being quoted in separate blocks here.** The corner's standing rule — "PNBP ≠
biaya jasa Bali Zero, never mix the two in one price line" — is a rule against *conflating the two
figures when explaining what each one is* (don't call the PNBP index string a client price, or vice
versa); it is **not** a claim that the 790k/850k client price excludes the government fee. Quoting
the PNBP index above and the PricingTool price here, in two separate blocks, satisfies that rule.
Adding them together, or telling a client to pay both, does not — and produces exactly the
double-charge this correction exists to prevent.

### 1.3 Biometrics — mandatory, not fully online
`[PRIMARY]`, published 28 May 2025, citing **Surat Edaran Direktur Jenderal Imigrasi Nomor
IMI-417.GR.01.01 Tahun 2025**, effective **29 May 2025** (G2, imigrasi.go.id press release;
mirrored in English by R3 at `ngurahrai.imigrasi.go.id/alleviating-immigration-violations-...`):

> ID (G2): *"wajib melakukan pengambilan foto dan wawancara di kantor imigrasi saat mengajukan
> perpanjangan izin tinggal"* — applies explicitly to VoA holders too.
> EN mirror (R3): *"foreign nationals in Indonesia are required to undergo photo capture and an
> interview at the immigration office when applying for a stay permit extension ... This procedure
> also applies to foreign nationals holding a visa on arrival (VoA)."*

Online registration/upload via `evisa.imigrasi.go.id` still precedes the mandatory in-person step;
only vulnerable groups (elderly, disabled, pregnant/nursing) may bundle everything into one visit.
**CONFIRMED, not refuted** — no instrument in this ring contradicted it. Live counter-example
worth flagging for market hygiene, not as anything to emulate: `bali.com` (WebSearch, 2026-08-23,
G2) currently advertises the e-VoA extension as doable "fully online without a visit to the
immigration office" — precisely the forbidden claim class ("perpanjangan sepenuhnya online") this
corner already bans, now confirmed circulating on a competitor/affiliate page.

### 1.4 2026 H2 holiday calendar — cross-verified by three independent passes
**SKB 3 Menteri Nomor 1497/2025, Nomor 2/2025, Nomor 5/2025** (signed 19 September 2025). For the
window 2026-07-28 → 2026-12-31, all three of G1 (the engine's own `operating_calendar.py:87`
hardcoded tuple), R3 (agy, direct regulatory fetch), and R1 (Codex's own pass-check against
`setneg.go.id/baca/index/inilah_skb_3_menteri_libur_nasional_dan_cuti_bersama_2026`) agree on
exactly four entries and no more:

| Date | Occasion | Kind |
|---|---|---|
| 2026-08-17 (Monday) | Proklamasi Kemerdekaan RI | Libur Nasional |
| 2026-08-25 (Tuesday) | Maulid Nabi Muhammad S.A.W. | Libur Nasional |
| 2026-12-24 (Thursday) | Kelahiran Yesus Kristus | Cuti Bersama |
| 2026-12-25 (Friday) | Kelahiran Yesus Kristus | Libur Nasional |

R1 explicitly marked this check **PASS** against the code. This is the strongest-corroborated fact
in the whole capture — three independent instruments, zero divergence.

### 1.5 SKB 2027 — not decreed, status unchanged from the 2026-07-27 truth-sheet
`[SECONDARY]` (G2 + R3 agree, no primary decree found either way): the SKB for calendar year 2027
has **not been issued** as of 2026-08-23. Expected window: "akhir 2026" (G2) / "September–October
2026, per the ministerial coordination meeting that precedes signing" (R3). All 2027 tables
online (tanggalans.com, kalenderlibur.id, hari.co.id, Tribun) are explicitly labeled
proyeksi/estimates, not law. Absence-of-decree is inferred from consistent secondary silence, not
from a primary "not yet" statement — neither instrument reached one. This directly matters for
§3's Finding 6 below: the engine's `COVERAGE_END = 2026-12-31` horizon is 130 days from this
session's date and its replacement data does not exist yet.

### 1.6 The 97-nationality decree
The eligible-nationality list at `imigrasi.go.id/wna/daftar-negara-voa-bvk-calling-visa/...`
(WebFetch, 2026-08-23, G2) currently enumerates **97 countries/entities** — independently
enumerated end-to-end (all 97, "1. Afrika Selatan" → "97. Yunani", with ISO-3 codes) by R4/agy.
Governing instrument: **Keputusan Menteri Hukum dan HAM RI No. M.HH-02.GR.01.06 Tahun 2024**. Note
the confidence asymmetry between the two passes that name this decree number: G2's own fetch of
the imigrasi.go.id list page did **not** display a regulation number in the extract and explicitly
flagged the number as `[SECONDARY]`-sourced (via a detik.com news report, "revoking a September
2023 decree") — "treat the decree number as secondary-sourced, not primary-confirmed." R3/agy
cites the same number attached directly to its own imigrasi.go.id/Ngurah Rai fetches, with no
comparable caveat trail. Both passes converge on the same number; the count of 97 itself is
doubly-confirmed (G2 primary fetch + R4's full enumeration), but the exact decree number should
still be treated as **LEAD, re-verify against a Berita Negara/JDIH copy before it goes in front of
a client**, per G2's own stated caution.

---

## 2. The D-7 problem — this is the most valuable finding in this capture

`PUBLISHED_FILING_DEADLINE_DAYS = 7` is hardcoded in `constants.py:43` as a national constant, and
the engine's `eligibility.screen()` gates every extension case on it. Two independent instruments
— G2/R3's regulatory fetch and R2's Kimi refuter — each separately found that Ngurah Rai's own
page contradicts itself, and R2 additionally found a **third, different** formulation at a second
kanim. None of the three pages supports "D-7" as a clean, universal rule.

**Ngurah Rai publishes two incompatible formulations on the same page**
(`ngurahrai.imigrasi.go.id/layanan-wna/`, WebFetch, 2026-08-23 — fetched independently by both G2
and R3, same result each time):

> **(a) Main body**, under *Perpanjangan Visa Kunjungan Saat Kedatangan*:
> *"Permohonan perpanjangan VOA paling cepat diajukan 14 hari sebelum masa berlaku izin tinggal
> habis"* — opens filing D-14 before expiry; publishes **no closing deadline at all**.
>
> **(b) Callout box, immediately beneath (a)**:
> *"Permohonan perpanjangan VOA paling cepat 14 hari setelah kedatangan dan paling lambat 7 hari
> sebelum masa izin tinggal berakhir."* — opens filing 14 days **after arrival** (≈D-16 before
> expiry on a 30-day stay, not D-14) and closes D-7.

The D-7 figure only exists inside formulation (b). The two openings disagree by roughly two days
and use different reference points entirely (before-expiry vs. after-arrival); (a) has no closing
date at all.

**Yogyakarta publishes a third formulation, and it isn't D-7 at all.**
`jogja.imigrasi.go.id/warga-negara-asing/perpanjangan-izin-tinggal/` (WebFetch, 2026-08-23, via
R2/Kimi, in the course of judging the D-7 legal premise, not as its primary task):

> *"Pengajuan perpanjangan dapat dilakukan paling cepat 14 hari dan paling lambat pada hari kerja
> sebelum jangka waktu izin tinggal berakhir."*

That is **D-1 working day**, not D-7 — a different closing rule on a different reference axis
(working days, not calendar days) than either Ngurah Rai formulation. The same page's opening
window (D-14) matches Ngurah Rai's formulation (a).

**The conclusion, stated explicitly because the charter already anticipated it and this is the
first evidence it isn't theoretical**: a D-7 written into `constants.py` as a single national
constant is a generalisation that **none of the three retrieved pages actually supports** taken on
its own terms — Ngurah Rai's own page disagrees with itself, and a second kanim (Yogyakarta)
publishes a materially different rule (D-1 working day vs. D-7 calendar days). The corner's charter
already said "verify per office" as a standing instruction; this capture is the first concrete data
point showing that instruction was not precautionary boilerplate. Until a per-kanim sweep exists,
any client-facing "file by D-7" line should be understood as Ngurah-Rai-specific practice at best,
not a national rule — and even Ngurah Rai's own two formulations disagree on where it opens.

---

## 3. The engine audit — seven red-team findings, each with the grader's real verdict

R1 (Codex, adversarial) filed 2 CRITICAL / 3 HIGH / 2 MEDIUM against `origin/main` at commit
`665bfd40d`. V1 (the empirical grader) then re-ran every one of them against the live `.venv` and
folded in R2's legal-premise verdicts where R2 reached them. **Two of the seven were downgraded
from "defect" to "documented and accepted"** by that reconciliation — presenting those two as live
defects would be false, and the fact that the gate caught its own over-claim is the actually
interesting result here, not a footnote to bury.

| # | R1 severity | Finding (file:line) | V1 grader verdict |
|---|---|---|---|
| 1 | CRITICAL | ISSUANCE +1-day optimistic stay estimate (`safe_clock.py:104,120`) | **PARTIAL — not a live defect.** Arithmetic reproduces exactly, but the code's own docstring already flags it ("the estimate is NOMINAL and may be up to one day OPTIMISTIC"), the response carries `expiry_is_estimated=True`, `printed_expiry` overrides it when supplied, and `test_safe_clock.py:43-55` pins this deliberately with a comment reading **"Grader finding 2026-07-25 (Kimi K3)"** — this exact issue was already caught by a prior grader round and closed with a design decision, not silently left. |
| 2 | CRITICAL | EXTENSION 60-day boundary off-by-one (`internal_preview_cli.py:132`) | **CONFIRMED — real, live, undocumented, untested at the exact boundary.** The guard rejects only `expiry - entry > 60`; a diff of exactly 60 represents **61 inclusive days**. `EXTENSION`, entry 2026-07-01, printed expiry 2026-08-30 → engine returns `ACCEPT`, D-7 = 2026-08-23; the legal 60-day max ends 2026-08-29, so the true D-7 was 2026-08-22 — the client is accepted one day past the real deadline. No docstring names this gap; the only existing test uses a 61-day diff (clearly over), never the diff==60 edge. Fix candidate: `>=` instead of `>`. |
| 3 | HIGH | Nationality hardcoded `True` (`intake.py:228,242-243`) | **CONFIRMED — real gap, but disclosed, not silent.** `nationality_entry_eligible=True` is hardcoded regardless of `request.nationality`; grep across the engine finds zero eligibility dataset. An independent refuter (R2, Kimi's claim F) confirmed Afghanistan is **not** among the 97 VOA-eligible nationalities under Kepmenkumham M.HH-02.GR.01.06/2024 — so `ISSUANCE, nationality=AFG` returns a clean `ACCEPT` for a nationality a real decree excludes. It is not silent: `_BASE_WARNINGS[1]` (`internal_preview_cli.py:48`) always states "Nationality and entry-point eligibility are not yet checked against an authoritative dataset and require manual verification," and the docstring names a downstream human pilot-intake gate before travel. |
| 4 | HIGH | No 90-day eVOA validity check (`intake.py:98,190,257`) | **CONFIRMED — real gap, reframed 2026-08-23 (post-merge, Codex Pass 2).** The original framing used `ISSUANCE`, entry 130 days out (2026-12-31), today 2026-08-23 → `ACCEPT` as if that alone proved a 90-day-validity violation — **it does not**: the 90-day eVOA use window runs from **issuance**, not from today's audit date, so an entry 130 days out is not itself invalid (the eVOA could still be issued later, well inside its own 90 days). The real, confirmed gap is narrower but still real: no `issuance_date` field exists anywhere in the engine (`grep issuance_date` = zero hits), so once an eVOA IS issued, the engine has no mechanism to check a travel date against that eVOA's own 90-day validity window. No 90-day bound exists either way (only unrelated 365-day windows). Unlike Finding 3, **no docstring anywhere names this scope gap.** |
| 5 | HIGH | 6-month passport validity measured from entry, not filing date (`intake.py:217,238`) | **DROPPED per conductor ruling — premise-contested, not confirmed as a defect.** Mechanics reproduce exactly (passport valid 184 days from entry passes; only 132 days from today/filing): but R2 (Kimi's claim C) could not find any 6-month passport-validity condition in the official Yogyakarta kanim extension-requirement list at all — that list states only *"paspor yang sah dan masih berlaku"* (a valid passport), full stop. `constants.py:33` cites "from entry" as the documented spec, but that citation may itself rest on the same unconfirmed premise. V1's original framing ("REFUTED as defect, matches SOP") is itself downgraded: **do not treat either the code's behavior or the original defense of it as authoritative** on the EXTENSION question specifically. *(Corrected 2026-08-23, post-merge, Codex Pass 2 — narrowing, not overriding, the line above: this is only unresolved for the EXTENSION-phase measurement point. For B1 issuance/entry, passport validity ≥6 months from arrival IS a sourced official rule (`jakartapusat.imigrasi.go.id` FAQ; VFS FAQ Q10) — not unresolved. What stays genuinely open is only whether the 6-month clock re-applies "from filing" at extension time, since the extension checklist requires only that the passport remain "valid," not a fresh 6-month window. See §6.)* |
| 6 | MEDIUM | `operating_calendar.py` `COVERAGE_END` off-by-one (`operating_calendar.py:137,152`) | **CONFIRMED — a real, clean code defect.** `last_open_day_before(2027-01-01)` returns `None` → `DECLINE/ARRIVAL_DATE_UNCONFIRMED`, even though the only date the calculation actually needs (`COVERAGE_END` = 2026-12-31 itself) is fully in coverage and open (Thursday, no holiday). `day <= COVERAGE_START` is correctly inclusive (test-pinned); `day > COVERAGE_END` is the off-by-one, and the docstring's own justification ("would cross materialized-data coverage") doesn't hold for this exact case. **Notable**: the bug is enshrined as *expected* at `test_operating_calendar.py:120-121` — a fix requires rewriting that test too, or `pytest` staying green over the wrong behavior. |
| 7 | MEDIUM | Pricing failure independent of verdict (`pricing.py:46`, `internal_preview_cli.py:159`) | **CONFIRMED — real, quiet asymmetry.** `pricing.py` fails closed to `(None, None)` on any exception (correct per its own contract), but `internal_preview_cli.py` computes the verdict and the price as two fully independent calls with no cross-check. Unlike the calendar path (which appends an explicit `calendar_warning` string on `calendar_status=="uncovered"`), there is **no analogous price-unavailable warning**. Client sees a clean `ACCEPT` with a silently missing price. Direct client exposure today is **UNVERIFIED-but-narrow**: the only live surface is owner-only and authenticated (`route.ts:23`), and every preview request spawns a fresh Python process (no stale-cache risk between requests) — but disk-catalogue freshness itself is UNVERIFIED. |

Boundary checks V1 also confirmed by direct execution: `days_until_expiry=7` → `ACCEPT`;
`days_until_expiry=6` → `DECLINE (EXPIRES_TOO_SOON)` — the D-7 constant's own edge is exactly
where the code says it is (a separate question from §2's "is D-7 the right constant at all").
Full suite: **162/162 passing, exit 0** (verified via `--collect-only -q` count + dot-count +
zero failure markers; this repo's custom pytest `addopts` suppresses the usual "N passed" summary
line, noted as a config quirk, not a gap).

---

## 4. Where the instruments disagreed, named — the calendar-independence of D-7

Both R1 (Codex) and R2 (Kimi) reasoned about the same underlying question — does the D-7 extension
filing deadline need to shift when it lands on a non-working day? — and reached opposite
conclusions. Neither side is resolved below; the disagreement is reported as a disagreement.

**Codex's position (argument "RIGHT" — the engine's calendar-independence is fine as designed).**
R1 constructed two adversarial cases against the live code and then judged them: expiry
2026-08-30 computes D-7 = **2026-08-23**, which this session independently verified is a **Sunday**;
expiry 2026-08-24 computes D-7 = **2026-08-17**, independently verified as a **Monday that is also
Proklamasi Kemerdekaan**, a national holiday per §1.4's table. `eligibility.py:185` treats both as
filable with no adjustment. Codex's argument for why that's still correct: Ngurah Rai describes the
*permohonan* (application) itself as an online claim/upload/payment step; the in-person photo and
interview follow later. So D-7 is the legal deadline for the **online filing**, not for a physical
office appointment — and an online portal does not observe office hours. Codex flags the load-bearing
premise as **UNVERIFIED**: whether `evisa.imigrasi.go.id`/molina is actually reachable and accepts
submissions 24/7 including Sundays and public holidays was never confirmed by either research pass.

**Kimi's refutation (claim E — REFUTED).** R2 reasoned to the opposite conclusion on two grounds:
(1) the general filing-deadline rule Kimi actually found in official kanim guidance (Yogyakarta,
§2 above) is not D-7 at all — it's "paling lambat pada hari kerja sebelum" (D-1 working day), which
already implies deadlines are meant to respect the working-day calendar, undercutting the premise
that a calendar-day D-7 is even the right rule to reason about; (2) independent of where the D-7
figure itself comes from, Kimi's engineering judgment is that a filing engine should not rely on
"no adjustment needed" when the computed deadline falls on a Sunday or public holiday — the safer
and more defensible posture is to shift the effective deadline earlier to the last working day
before the non-working D-7, mirroring how the general rule is already expressed in working days
elsewhere in official guidance. Kimi's own transcript records real uncertainty in reaching this
verdict (it explicitly weighed "CANNOT DETERMINE" against "REFUTED" before settling on REFUTED per
its own instruction to default to refuted when uncertain) — this is not a confident rebuttal, it is
a reasoned one under real ambiguity, and R2's run was cut off before it could finish stating all of
its reasoning for claim E in full.

**What would settle it**, named rather than guessed: (a) confirming whether Ngurah Rai's D-7 is
genuinely a local/practical figure layered on a national D-1-working-day floor (Permenkumham-level),
or is the number the online portal itself enforces at submission time — nobody in this ring
resolved which; (b) verifying the online portal's actual availability window (24/7 including
Sundays/holidays, or not) — the one fact Codex's own defense depends on and neither instrument
checked; (c) the per-kanim sweep §2 already calls for, since a third office (Yogyakarta) has
already shown a materially different formulation on the same underlying question.

### 4.1 Post-merge addendum (2026-08-23) — a sourced challenge to D-7 itself, UNVERIFIED here

A second, independent post-merge adversarial pass (Codex, reviewing this document as committed to
`main` — Pass 2 in the Adversarial review section) raised a challenge more fundamental than §4's
disagreement over whether D-7 should *shift* for non-working days: it challenges whether **D-7 is
the right national-level number to reason about at all.**

**The claim, with its citation, exactly as Pass 2 reported it**: Permenkumham 22/2023, as amended
by Permenkumham 11/2024, Pasal 97, is reported to set the national statutory window for a
stay-permit-extension application as **D-14 through before expiry — with no D-7 closing date in the
statute itself**. The "D-1 working day" formulation Yogyakarta publishes (§2 above) is reported to
trace back to **Permenkumham 29/2021, which is REVOKED**. Sources cited by Pass 2:
`peraturan.bpk.go.id/Download/344251/Permenkumham%20Nomor%2011%20Tahun%202024.pdf` (Pasal 97) and
`peraturan.go.id/id/permenkumham-no-29-tahun-2021` (revocation status).

**This document does NOT independently verify the Pasal 97 text or the 29/2021 revocation status
here** — a separate lane was attempting that verification at the time of this correction, and its
result is not folded into this capture. Treat this as a **SOURCED CHALLENGE, not a resolved fact**:
it carries a citable source, but neither the citation nor its bearing on §2's kanim-level findings
is certified by this document. §2's original findings are left exactly as captured, unedited.

**Why this is recorded and not resolved**: it bears directly on **Ruling Zero 2026-07-27 (b)**
(`~/.claude/projects/-Users-nuzantara/memory/garuda_voa-activity-log.md`, entry "RULING ZERO (b)
implementato: l'estensione si accetta fino al termine PUBBLICATO"), where Zero explicitly chose to
gate the engine on the *published* Ngurah Rai deadline rather than deriving it from statute —
`PUBLISHED_FILING_DEADLINE_DAYS` in `constants.py` is that ruling's direct implementation. If Pasal
97 does set a D-14 statutory floor with no D-7 closing date, that is information the ruling did not
have in front of it on 2026-07-27. Whether it changes the ruling is **Zero's call, not this
document's** — this addendum exists so that call can be made with the citation in hand, not so the
document pre-empts it.

---

## 5. Competitors and funnel UX (G2)

Five competitors surveyed, all productising VOA/eVOA as a self-serve or chat-first flow:

1. **VFS Global** (`idnonline.vfsevisa.id`, `indonesiavoa.vfsevisa.id`) — *corrected 2026-08-23,
   post-merge adversarial review (Codex, Pass 2).* The original text here called VFS "the actual
   official exclusive private partner appointed by Ditjen Imigrasi" — **that asserted an
   exclusivity no source documents, and is precisely one of this corner's own forbidden claims**
   ("mitra resmi/reseller pertama"). VFS's own January 2025 press release calls the platform
   "official"; Ditjen Imigrasi's own communications describe *cooperation/kerja sama*, not an
   exclusive appointment (`jogja.imigrasi.go.id/ditjen-imigrasi-bahas-kerja-sama-layanan-keimigrasian-dengan-vfs-global/`).
   Corrected statement: **Ditjen Imigrasi cooperates with VFS Global, whose platform is an accepted
   application channel — no exclusive appointment was verified.** VFS remains an entity Bali Zero
   must never claim to be or imply proximity to. Flow: online form → upload → pay → eVOA emailed.
   **Price, also corrected**: VFS's own FAQ publishes **IDR 500,000 government e-VoA fee plus IDR
   230,000 VFS service fee, including taxes — IDR 730,000 total** (`indonesiavoa.vfsevisa.id/faqs.html`),
   not "500,000 flat (unclear whether a surcharge is layered)" as originally written. On this
   corrected basis, Bali Zero at 790,000 sits just above the official channel (730,000) and just
   below Flado's 800,000 — not below an unclear 500,000 figure.
2. **Flado Indonesia** — eVOA 30 days at **IDR 800,000 all-inclusive**, 1–2 business-day
   processing, "no hidden fees, 0% card-payment commission."
3. **MyVisa.World** — chat-first (Telegram/WhatsApp), assigned "visa manager." All-inclusive:
   **$60** (30-day), **$120** (60-day), +$20 super-express (2h).
4. **iVisa** — 4-step flow, single all-inclusive figure **"from $84.99"**, no government/service
   breakdown shown to the buyer.
5. **e-visa-indonesia.com / evisaindonesia.info** — generic agency sites bundling "assistance"
   around the official flow; reference-only, not deeply probed.

**Pattern across all four non-official competitors**: price is shown **all-inclusive, never
split** government-fee-vs-service-fee. The charter's "PNBP ≠ Bali Zero fee, never mix in one line"
rule is therefore **stricter and more transparent than the market norm**, not laxer — worth stating
plainly so it isn't second-guessed as over-engineering later.

**Seven transferable SOTA UX patterns**, named sources, mapped to the two frictions the mandate
named (document rework; deadline anxiety):
1. Name the exact document required, never "more info needed" (SimpleVisa, *eVisa Checkout UX Tips*).
2. Dynamic requirement re-render on purpose-of-travel change (same source).
3. Trust signal placed exactly where the anxiety happens — *why* at upload, *what* at payment,
   *who reviews* at submit (SimpleVisa, *How to Guide Customers Through Visa Applications*).
4. Post-booking recovery channel (email/SMS/push before the filing deadline) rather than relying
   on the applicant to remember (SimpleVisa, *eVisa Status Page UX*).
5. Small, stable customer-facing status taxonomy (8–12 named states) reused across product
   variants (same source).
6. "Gather your documents before you start" priming step (Consulate General of India, San
   Francisco, e-Visa guidance page).
7. Visible progress tracker / step counter (UserGuiding, *Progress Trackers and Indicators* —
   general SaaS onboarding research, transferable by direct analogy, flagged as such, not
   visa-specific).

Patterns 1, 2, 6 address document rework; patterns 3, 4, 5 address deadline anxiety.

---

## 6. What this capture does NOT establish

- Whether a D-7-style deadline should be adjusted for non-working days is an open disagreement
  (§4), not a resolved fact — do not build a "fix" on either side's argument without first
  confirming the two named unknowns.
- The exact decree number behind the 97-nationality list (§1.6) is a lead, not a primary-confirmed
  citation.
- The extension PNBP figure (§1.2) rests on one primary source (R3/Ngurah Rai), not
  cross-confirmed by G2's own separate B1-index fetch.
- Findings 1 and 5 of the engine audit (§3) are **not** live defects — do not re-open them as bugs
  without new evidence. *(Corrected 2026-08-23, post-merge, Codex Pass 2 — the line originally here
  read "Finding 5 specifically has no resolved legal grounding on either side," which is too weak
  and misleading.)* For B1 issuance/entry, passport validity is at least six months from arrival —
  that IS a sourced rule, not unresolved; at extension it must remain valid. The tested case
  (measuring "from entry" vs. "from filing" in the extension code path) does not establish a defect
  against either framing — see the corrected §3 row 5.
- No NotebookLM ground-truth leg ran in this ring (§0) — nothing here should be read as
  NB-corroborated.
- R2 (Kimi) was cut off by a timeout before finishing claim E and before writing up claim F in its
  own words; F's CONFIRMED verdict on Afghanistan-ineligibility is preserved because V1's
  conductor-layer explicitly recorded it before the transcript ended, not because R2's own file
  shows a completed sign-off.
- §4.1 (added 2026-08-23, post-merge) records a **sourced but here-UNVERIFIED** challenge to D-7
  itself (a reported D-14 statutory floor, no D-7 closing date, per Permenkumham 22/2023 as amended
  by 11/2024 Pasal 97) — this document does not resolve it, and it bears on Ruling Zero 2026-07-27
  (b), which only Zero may revisit.

---

## Adversarial review

This document has now been through **two** adversarial passes by two different model families,
neither of which authored it (Claude). Both are recorded here in full, per this repo's discipline
against a research capture quietly rewriting its own history.

### Pass 1 — Kimi K3 (`kimi-k3`)

Run locally on Mini as R2, during the original research ring, tasked specifically with judging the
LEGAL PREMISES behind R1's red-team findings — not the code, and not this write-up. R2's own
transcript is the source for every line below; nothing here is paraphrased optimism.

**Objections that survive — not resolved by this capture, reported as open:**
1. **D-7 calendar-independence (§4).** Kimi's claim E refuted Codex's "no adjustment needed"
   position: the general kanim filing-deadline rule Kimi found is expressed in working days
   (D-1 working day, not D-7 calendar days), and an engine relying on a Sunday/holiday deadline
   with no shift is, in Kimi's judgment, the wrong default. This capture does **not** side with
   Codex over Kimi (or vice versa) — §4 states both arguments and names what would settle it.
   Objection stands. (See also §4.1, added in Pass 2 below — a more fundamental, still-unverified
   challenge to whether D-7 is the right number at all.)
2. **6-month passport validity measured "from filing" (§3, Finding 5).** Kimi's claim C could not
   find any 6-month passport-validity condition in the official Yogyakarta kanim extension
   requirement list at all (it lists only "paspor yang sah dan masih berlaku"). This is why
   Finding 5 is reported as **DROPPED / premise-contested** rather than defended as either a
   confirmed defect or a confirmed non-defect. **Narrowed in Pass 2** (below): the objection stands
   only for the EXTENSION-phase measurement point — the ISSUANCE/entry-phase six-month-from-arrival
   rule is sourced and not in dispute (§3 row 5, §6).

**Objections that did not survive (Kimi confirmed these; this capture adopts them without
contest — Kimi's own reasoning for each is reproduced inline where each claim is used):** claim A
(arrival-day-as-day-1 counting, feeding §1.1 and Finding 1), claim B (60-day inclusive max, feeding
Finding 2), and claim D (90-day eVOA validity from issuance, feeding §1.1 and Finding 4).

**Claim F is a special case, corrected in Pass 2**: claim F (Afghanistan excluded from the
97-nationality list, feeding §1.6 and Finding 3) is CONFIRMED, but — unlike A, B, and D — **it was
never actually written up by Kimi in its own words**; R2 was cut off before reaching it. The
CONFIRMED verdict used in this document is V1's conductor-layer annotation, recorded before the
transcript ended, not a completed Kimi sign-off. The original text here listed claim F alongside
A/B/D without this distinction, which Pass 2 flagged as an internal contradiction against §6 (which
already stated it correctly) — corrected 2026-08-23.

**Declared limitation on Pass 1 itself**, not laundered into a stronger claim than it is: R2's run
was cut off by a timeout mid-sentence during its own write-up of claim E, before it finished
stating its full reasoning and before it produced a standalone write-up of claim F. Treat Pass 1 as
real but partial, not exhaustive.

### Pass 2 — Codex (`gpt-5.6-sol`, xhigh)

Run via `ssh pro` on 2026-08-23, adversarially reviewing **this document as merged to `main`**
(commit `f26bd5a5f`, PR #4681) — the write-up itself, not the underlying engine or legal premises
(that was Pass 1's job). Triggered because the PR's adversarial-review findings had not been
applied before an unintended merge (see the notice at the top of this document). Full verdict text
preserved in the correction PR that applied these findings (this file's own git history, commits
following `f26bd5a5f`).

**Findings applied (accepted, corrected in place — each marked "corrected 2026-08-23" at its
location):**
- **CRITICAL** — §1.2's "This is a Bali Zero service fee, not a government fee" was false and
  invited double-charging a client (the PricingTool price is all-inclusive, PNBP already included).
  Highest-severity finding in this pass; corrected.
- **HIGH** — §5's VFS Global price ("500,000 flat, unclear whether a surcharge is layered") was
  factually wrong. Corrected to VFS's own published 730,000 total (500k government fee + 230k VFS
  service fee).
- **HIGH** — §5's VFS "actual official exclusive private partner appointed by Ditjen Imigrasi" was
  one of this corner's own named forbidden claims. Corrected to "cooperates with" — no exclusivity
  verified by any source.
- **HIGH** — §3 Finding 4's "entry 130 days out" framing implied a 90-day-validity violation the
  case doesn't actually demonstrate (the 90 days run from issuance, not from today). Reframed to
  the real, narrower, still-confirmed gap: no `issuance_date` field exists in the engine.
- **HIGH** — §6's "Finding 5 specifically has no resolved legal grounding on either side" was too
  weak: the B1 issuance/entry six-month-from-arrival passport rule is sourced. Corrected, and Pass
  1's item 2 above narrowed accordingly.
- **HIGH** — §0's "What did complete (claims A–F) is used below" contradicted §6's own admission
  that claim E is partial and claim F was never written up by R2. Corrected; see the claim-F note
  in Pass 1 above.
- **MEDIUM** — §1.1 fused two separate regulatory chains (11/2024 amending 22/2023 on visas/stay
  permits, vs. 9/2024 repealing 44/2015 on border/entry-exit inspection) into one sentence.
  Corrected to state both chains separately.

**Finding recorded but deliberately NOT resolved in this document's own voice — reported as open,
unverified here:**
- **CRITICAL** — a citation (Permenkumham 22/2023 as amended by 11/2024, Pasal 97) reported to set
  a D-14-through-expiry statutory window with no D-7 closing date, and to trace the "D-1 working
  day" formulation to a revoked Permenkumham 29/2021. This document does not independently verify
  either the Pasal 97 text or the 29/2021 revocation status, and the claim bears on Ruling Zero
  2026-07-27 (b) (`constants.py`'s `PUBLISHED_FILING_DEADLINE_DAYS`), which only Zero can revisit.
  Recorded as a sourced challenge in the new §4.1, not resolved here. **Objection stands, open.**

**Sections Pass 2 attacked and could not fault — left unchanged**: §1.3 (biometrics, mandatory,
not fully online) and §1.4 (the H2 2026 holiday calendar, three-instrument cross-verified, zero
divergence). "Fully online extension" is correctly reported throughout as a contested EXTERNAL
claim (a competitor's own marketing, quoted specifically to flag the forbidden-claim class), never
as an assertion made by this document.

---

## Sources

1. `imigrasi.go.id/wna/daftar-visa-indonesia/B1` · 2026-08-23 · WebFetch [PRIMARY] (G2) — B1 core rules, issuance PNBP index string.
2. `ngurahrai.imigrasi.go.id/layanan-wna/` · 2026-08-23 · WebFetch [PRIMARY] (G2, R3, and independently referenced by R1) — the two D-7/D-14 formulations, extension PNBP string, 97-country list mirror.
3. `imigrasi.go.id/siaran_pers/tekan-angka-pelanggaran-keimigrasian-wna-wajib-ke-kantor-imigrasi-untuk-perpanjangan-izin-tinggal` · 2026-08-23 · WebFetch [PRIMARY] (G2) — biometrics circular, Bahasa Indonesia text.
4. `imigrasi.go.id/wna/daftar-negara-voa-bvk-calling-visa/daftar-negara-subjek-visa-on-arrival` · 2026-08-23 · WebFetch [PRIMARY] (G2) — 97-nationality list, primary count.
5. `evisa.imigrasi.go.id/front/info/evoa` · 2026-08-23 · WebFetch [PRIMARY, older/looser text] (G2).
6. `evisa.imigrasi.go.id/front/faq/dd5c2220-28a7-4024-9a10-82f30a09e0d2` · 2026-08-23 · WebFetch [PRIMARY] (G2).
7. `imigrasi.go.id/en/visa-on-arrival` · 2026-08-23 · WebFetch [404 — dead, not used] (G2).
8. `balizero.com/visa/voa` · 2026-08-23 · WebFetch + curl [VERIFIED-LIVE, 404, noindex/nofollow] (G2) — confirms the public funnel is retired per PR #4344.
9. `flado.id` / `id.flado.id` · 2026-08-23 · WebSearch [SECONDARY] (G2) — competitor.
10. `idnonline.vfsevisa.id` / `indonesiavoa.vfsevisa.id` + VFS Global press release · 2026-08-23 · WebSearch [SECONDARY] (G2) — official appointed partner.
11. `myvisa.world/en/indonesia/eVOA` · 2026-08-23 · WebFetch [SECONDARY] (G2) — competitor.
12. `ivisa.com/visas/indonesia/evoa` · 2026-08-23 · WebFetch [SECONDARY] (G2) — competitor.
13. `simplevisa.com` (3 articles: checkout UX, guiding customers, status-page UX) · 2026-08-23 · WebSearch [SECONDARY] (G2) — UX patterns 1-5.
14. `cgisf.gov.in/page/e-visa/` · 2026-08-23 · WebSearch [SECONDARY] (G2) — UX pattern 6.
15. `userguiding.com/blog/progress-trackers-and-indicators` · 2026-08-23 · WebSearch [SECONDARY] (G2) — UX pattern 7.
16. `news.detik.com/berita/d-7671829/97-negara-subjek-visa-on-arrival-voa-indonesia-ini-daftarnya` · 2026-08-23 · WebSearch [SECONDARY] (G2) — decree-number attribution for the 97-list, flagged not-primary-confirmed.
17. SKB 2027 status: `tanggalans.com`, `kalenderlibur.id`, `hari.co.id`, `pontianak.tribunnews.com` · 2026-08-23 · WebSearch [SECONDARY] (G2) — no primary decree found either way.
18. `imigrasi.go.id/berita/2024/04/19/jangan-salah-pilih-ini-beda-visa-kunjungan-wisata-dan-visa-on-arrival` · 2026-08-23 · WebSearch [PRIMARY, snippet only] (G2).
19. `mcp__nuzantara-knowledge__get_visa_details("b1")` · 2026-08-23 · RAG tool call [RAG] (G2).
20. `mcp__nuzantara-knowledge__search_service_pricing("B1 visa on arrival extension")` · 2026-08-23 · RAG tool call [RAG] (G2) — Bali Zero PricingTool cross-check.
21. `bali.com` · 2026-08-23 · WebSearch [SECONDARY] (G2) — competitor page found asserting the forbidden "fully online extension" claim; market-hygiene flag only.
22. `evisa.imigrasi.go.id/web/visa-selection` (+ `/data` catalogue endpoint) · 2026-08-23 · WebFetch [PRIMARY] (R3/agy) — PNBP issuance index and nationality-list mirror.
23. `ngurahrai.imigrasi.go.id/alleviating-immigration-violations-foreign-nationals-must-go-to-immigration-office-to-extend-stay-permit/` + `kemenimipas.go.id` · 2026-08-23 · WebFetch [PRIMARY] (R3/agy) — English mirror of the biometrics circular.
24. `setneg.go.id/baca/index/inilah_skb_3_menteri_libur_nasional_dan_cuti_bersama_2026` (also monitored: `kemenkopmk.go.id`, `menpan.go.id`) · 2026-08-23 · WebFetch [PRIMARY] (R1/Codex, R3/agy) — SKB 2026 official document, holiday-table cross-check.
25. `jogja.imigrasi.go.id/warga-negara-asing/perpanjangan-izin-tinggal/` · 2026-08-23 · WebFetch [PRIMARY] (R2/Kimi) — the third D-7-vs-D-1-working-day formulation; §2's central finding.
26. `jogja.imigrasi.go.id/e-voa-bisa-digunakan-masuk-ri-sampai-90-hari-setelah-terbit-berlaku-paling-lama-60-hari/` · 2026-08-23 · WebFetch [PRIMARY] (R1/Codex) — 90-day eVOA validity / 60-day max-stay rule, underlying §3 Findings 1 and 2.

**Added 2026-08-23, post-merge correction (Pass 2, Codex):**

27. `indonesiavoa.vfsevisa.id/faqs.html` · 2026-08-23 · WebFetch [PRIMARY-COMPETITOR] (post-merge, Codex) — VFS's own government-fee + service-fee breakdown (IDR 730,000 total), used to correct §5 item 1; also FAQ Q10, passport-validity rule used in §3 row 5 / §6.
28. `jogja.imigrasi.go.id/ditjen-imigrasi-bahas-kerja-sama-layanan-keimigrasian-dengan-vfs-global/` · 2026-08-23 · WebFetch [PRIMARY] (post-merge, Codex) — Ditjen Imigrasi describes cooperation/*kerja sama* with VFS Global, not an exclusive appointment; used to correct §5 item 1.
29. `peraturan.bpk.go.id/Download/344251/Permenkumham%20Nomor%2011%20Tahun%202024.pdf` · 2026-08-23 · WebFetch [PRIMARY, UNVERIFIED IN THIS DOCUMENT] (post-merge, Codex) — cited for Pasal 97's reported D-14-through-expiry window; see §4.1, not independently confirmed here.
30. `peraturan.go.id/id/permenkumham-no-29-tahun-2021` · 2026-08-23 · WebFetch [PRIMARY, UNVERIFIED IN THIS DOCUMENT] (post-merge, Codex) — cited as the revoked source of the "D-1 working day" formulation; see §4.1.
31. `jakartapusat.imigrasi.go.id/index.php/layanan/warga-negara-asing-wna/visa-republik-indonesia/b1-visa-saat-kedatangan-wisata` + `jakartapusat.imigrasi.go.id/faqs` · 2026-08-23 · WebFetch [PRIMARY] (post-merge, Codex) — official ≥6-month passport validity from arrival, B1 issuance/entry; used to correct §3 row 5 / §6.
32. `peraturan.bpk.go.id/Details/133323/permenkumham-no-44-tahun-2015` + `peraturan.go.id/id/permenkumham-no-11-tahun-2024` · 2026-08-23 · WebFetch [PRIMARY] (post-merge, Codex) — confirms 44/2015 (border/entry-exit inspection) was repealed separately by 9/2024, a different chain from 11/2024's amendment of 22/2023 on visas/stay permits; used to correct §1.1.

Internal artifacts consumed as inputs (not external regulatory sources, listed for traceability):
G1 (engine file:line audit), R1 (Codex `gpt-5.6-sol` red-team transcript, `apps/backend-rag/backend/services/garuda_flow/*` + `apps/admin-dashboard-local/*` file:line citations throughout), R2 (Kimi K3 refuter transcript, truncated), R4 (agy 97-country enumeration), V1 (empirical grader re-execution against the live `.venv`, 162/162 pytest), R5 (Codex `gpt-5.6-sol` xhigh, post-merge document adversarial review, run via `ssh pro`, 2026-08-23 — Pass 2 above).
