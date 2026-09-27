---
adversarial_review: exempt-mission-process-record # ORACLE-PROD-20260927 process record (spec, progress, freeze or round log) for a code release, not a research deliverable; the reviewed object is the code, whose council and final-gate verdicts are in evidence/2026-09/agent-air-m5-mouth-oracle-prod-0927-d995492b/
---

# ENDING-ROUND — friendly ending surface, same canonical meaning (Dux, 2026-09-27T11:15Z)

Why: the approved prototype ending (`…/branching-atlas/prototype/src/Outcome.jsx`, read-only) reads as a
person talking; production still shows an engineering wall (qa3 `ending-desktop-SUPPORTED_CANDIDATES.jpg`:
"The deterministic engine supports…", "Rank 1", "Verified reason: TOURISM_SUPPORTED", per-reason external
links, "Sources used for this decision" with effective/observed stamps, "Assumptions & caveats, dated" with
three timestamps). Owner request relayed by the coordinator: remove jargon, raw codes and provenance walls;
keep every substantive condition, price/quote statement, Studio-only wording, mixed-review split, consent and
retention language, disclaimers, and useful law citations. Presentation only.

`R` = `apps/mouth/src/app/(visa-oracle)/visa-oracle`. Map of the current surface (file:line, pins):
Explore report pasted in the dispatch prompt — trust but re-verify each line before editing.

## Boundaries
- Do NOT modify `_lib/engine-adapter.ts`, `engine-response.ts`, `outcome-*.ts`, `evaluation-*.ts`, reducer/tree,
  API routes, `engine-adapter.test.ts`. No data is dropped from the view model; this round only changes what
  the screen shows and how.
- `_lib/i18n.ts`: ONLY the value edits and additive keys listed below, EN and ID together. Keys stay.
- Tests: an existing assertion that pins REMOVED jargon may be updated to pin the new copy/absence (list each
  one in the report with before/after). Assertions pinning substantive meaning, class hooks, the colour fence
  (`.oracle-verdict-chip`, `data-state`, `--oracle-state-*`), disclaimers, Studio wording, NOTICE_CONDITION_COPY,
  REVIEW_REASON_ELEMENTS, review-group headings and consent flow stay UNCHANGED. The two e2e gate specs are not
  edited unless an assertion pins removed jargon — then report it before editing.

## Changes
| # | Where | Change |
|---|---|---|
| E1 | i18n `verdict.headline.SUPPORTED_CANDIDATES` / `verdict.state_description.SUPPORTED_CANDIDATES` | EN "A path forward." / "These options match the answers you gave." · ID "Ada jalan ke depan." / "Opsi-opsi ini sesuai dengan jawaban yang Anda berikan." |
| E2 | i18n `verdict.headline.TEMPORARILY_UNAVAILABLE` / `.state_description.TEMPORARILY_UNAVAILABLE` | EN "A pause in the journey." / "We can’t check your options right now. Your answers are still on this page." · ID "Jeda sejenak dalam perjalanan." / "Kami belum bisa memeriksa opsi Anda saat ini. Jawaban Anda masih ada di halaman ini." (truthful: in-page, not "saved"). |
| E3 | i18n `outcome.needs_input_body` | EN "A few details are still missing:" · ID "Beberapa detail masih kurang:" |
| E4 | CandidateCard (`OutcomeSheet.tsx` ~555-676) | Remove the "Rank N" chip from the screen. Top row = product code (left) + `01/02…` index (right, `aria-hidden`), then product name, tagline. Move the axis badges AND the reason list into ONE closed `<details className="oracle-candidate__why">` with summary = new key `outcome.why_fits` (EN "Why this fits", ID "Mengapa ini cocok"). Timeline, price, document checklist stay visible and unchanged. |
| E5 | Support reasons (ReasonList for candidates) | Never show a raw code: a reason whose localized text matches `/^(Verified reason|Alasan terverifikasi): [A-Z0-9_]+$/` is replaced by new key `outcome.reason_generic` (EN "The assessment supports this option for the answers you provided." ID "Penilaian mendukung opsi ini untuk jawaban yang Anda berikan."); duplicates collapse to one line. Mapped reasons unchanged. |
| E6 | Inline per-reason source links (`~421-439`) | Remove from the screen (they duplicate the legal references and read as application links). |
| E7 | Sources list (`~1090-1128`) | Becomes a CLOSED `<details className="oracle-outcome__legal">` with summary new key `outcome.legal_references` (EN "Legal references", ID "Dasar hukum"): one row per source = title (as link to its trusted URL, `target="_blank" rel="noopener noreferrer"`) + publisher. Effective/observed dates and freshness badges move to `.oracle-print-only` (they stay in print/PDF, off screen). |
| E8 | Assumptions receipt (`~1130-1168`) | Title value `outcome.assumptions_receipt_title` → EN "What we assumed" · ID "Yang kami asumsikan". Keep the assumptions content; the `outcome.assessment_dates` line becomes `.oracle-print-only`. Drop the dashed "receipt" frame on screen (plain section). |
| E9 | Conditions (`~803-826`) | Title value `outcome.conditions.title` → EN "Before you apply" · ID "Sebelum Anda mengajukan" — ONLY if no existing test pins the old title; otherwise keep and report. Content unchanged. |
| E10 | i18n `why.category` (watershed WhyWeAsk sentence) | EN "Your direction only chooses the next questions. It doesn’t decide whether a visa path is available — your answers do." · ID "Arah yang Anda pilih hanya menentukan pertanyaan berikutnya. Arah ini tidak menentukan apakah jalur visa tersedia — jawaban Anda yang menentukan." |
| E11 | CSS (atlas section of `oracle.css`, after existing atlas rules, before the final print block) | Verdict/ending column full width of the confluence column, left-aligned; candidate card = prototype look (`border:1px solid #aca392`-equivalent via `--atlas-rule`, paper bg, radius ≤2px, `padding:25px 27px`, code row copper 11px letter-spaced, name serif 30px/1.15); `<details>` summaries 14px underline-free with a copper marker; inline consultant card full column width, left-aligned (FIX-ROUND-1 D3). Dark theme via existing tokens only; no new `--oracle-state-*` declarations. |

## Tests to add (focused, synthetic)
- SUPPORTED ending (EN, ID): headline/description new copy; no text matching `/\b[A-Z]{2,}(?:_[A-Z0-9]+)+\b/` outside `.oracle-print-only`; no "deterministic engine", "Rank ", "observed", "evaluated" on screen; Legal references `<details>` closed by default and lists the source title; candidate "Why this fits" closed by default.
- Unmapped support code → generic sentence, once.
- Print: dates present inside `.oracle-print-only`.
- Existing Studio-only / mixed-review / consent / disclaimer tests pass unchanged.

## Acceptance (Pro)
vitest all green (report counts; list every updated assertion); tsc 0; next build 0; harness
`atlas-qa.local.spec.ts` 0 failed (endings × desktop/mobile/narrow included); PR gate e2e 46/46; Read the
ending jpgs for all 7 endings at desktop + mobile and describe them against the prototype
(`…/branching-atlas/qa/evidence/genuine-supported-tourism-desktop.png`, `qa-synthetic-studio-only-mobile.png`).
