---
date: 2026-06-16
domain: compliance
scar: W82
status: SPEC — not armed (operator decision pending)
author: Connectome Campaign / Super-Observer
---

# W82 — Fact-based freshness sentinel (per-ENTITY approach)

> This document is a **specification**, not an implementation. It arms nothing.
> It describes how to replace the string-literal + EN-only freshness sentinel
> (`apps/mouth/src/content/content-freshness-sentinel.test.ts`) with a guard that
> watches the **normative entity** (KBLI code / visa sigla / regulation number),
> not the **literal sentence**. Deterministic, no-AI, runs in CI for free.
> Operator (Antonello) chose the per-ENTITY approach over AI/embedding.

---

## 1. Problema

The freshness sentinel is the dead-man's switch between published content and
regulatory ground-truth, but it watches the **string**, not the **fact** — so a
stale fact that is reworded, put in a table cell, or written in another language
slips through and the guard stays GREEN. Three structural holes, all verified on
disk in this worktree:

- **Substring, not fact** — `staleHits()` matches a literal phrase via
  `lines[i].toLowerCase().includes(needle)` (`content-freshness-sentinel.test.ts:125`,
  function body lines 119-132). The ledger's `KBLI-HOTEL-55110` claim carries
  `"stale_pattern": "hotels (55110)"` (`_regulatory-claim-ledger.json:42`). The
  same KBLI code `55110` in a markdown table cell (`| 55110 | hotel |`), or
  reworded (`"perhotelan 55110"`, `"55110 (akomodasi)"`), or cited without the
  English word `"hotels"`, does **not** match → test green while the fact rots.
- **Translation-skip by design** — `TRANSLATION_SUFFIX`
  (`content-freshness-sentinel.test.ts:36`) excludes `.it/.id/.ru/.fr/.de/.es/.nl`
  from `collectMdx()` (lines 106-107); the file header declares scope
  "*English canonical .mdx only ... translations audited separately*" (lines 21-22).
  "Audited separately" = audited **never** until a human passes.
- **The escape-clause is itself literal** — `MIGRATION_CONTEXT`
  (`content-freshness-sentinel.test.ts:58-97`) is a hand-maintained list of
  English phrases (`"superseded"`, `"old kbli 2020"`, `"moved to the 15th"`...)
  that "excuse" a stale pattern; a correction phrased differently or non-EN is
  not recognised as legitimate.

**Three live proofs (verified, not assumed):**

1. **LKPM deadline stale in it/ru/fr (KN-3).** The ledger claim `LKPM-DEADLINE-10TH`
   (`_regulatory-claim-ledger.json:104-110`, `"by April 10"` → moved to the 15th
   by PerBKPM 5/2025 Pasal 285(3)) was found stale in the Italian, Russian and
   French translations while the sentinel was GREEN — because `TRANSLATION_SUFFIX`
   structurally never looks at those files. This bug had to be fixed by hand in
   PR #1500. The translation-skip **is** the root cause.
2. **C312 stale in the EN canonical.** `VISA-C312`
   (`_regulatory-claim-ledger.json:16-22`) is stale even in canonical English, yet
   the substring guard does not catch every reformulation of the C312 reference.
3. **55110 stale in the EN canonical.** `KBLI-HOTEL-55110`
   (`_regulatory-claim-ledger.json:40-46`) — `55110` in a conversion table or
   without the literal token `"hotels ("` evades the `"hotels (55110)"` needle.

Net: the test "already accuses itself" — its own header (lines 8-12) names the
malattia-delle-malattie *"the SAME stale code reappears across many files and
silently rots"*, then fights it with the very vector (substring) that lets it rot.

> **Ledger reality check (doc-drift noted):** the ledger holds **14 claims**, not
> 15. The W82 scar body says "15 stale_pattern" — that is a one-off doc-drift; the
> on-disk `_regulatory-claim-ledger.json` array has 14 entries (3 of severity P1,
> 11 of severity P0). This spec is grounded on the 14 real entries.

---

## 2. Approccio scelto: per-ENTITÀ normativa

**Principle: a normative entity is language-invariant; a sentence is not.**

A KBLI code, a visa index sigla, a regulation number, or a statutory threshold is
the same token in every language, in prose, and in a table cell. `55110` is
`55110` in `| 55110 |`, in `"perhotelan 55110"`, and in the French translation.
The guard must therefore search for the **entity wherever it appears**, not for a
specific English phrasing of it.

This is the structural antidote to superscar **#3 (Guard-over-match)** — W82 is
its UNDER-match twin. #3's over-match clobbers correct answers (false-positive);
W82's under-match lets rotten facts through (false-negative). Same root: the match
is on textual form, not on the entity/intent. The cure is identical at both signs:
**match on entity, plus a mandatory innocence test.**

**Why per-entity, not AI/embedding (operator decision):**

- **Deterministic** — same input, same verdict; no model drift, no flaky CI.
- **$0** — pure regex over MDX, runs inside the existing Vitest suite; no API
  call, no Anthropic key (banned), no Ollama latency in CI.
- **Auditable** — every anchor is a regex a human can read and a test can prove
  innocent. No black box deciding "this fact is stale".
- **Language-coverage for free** — because the entity is language-invariant, one
  anchor covers all locales for code/number facts.

**Honest boundary (carried to §7):** this only covers facts that *have* a code or
number. A prose-only fact ("Pondok Wisata reserved for WNI") has no
language-invariant token to anchor on and stays out of scope — a known-gap, not a
hidden one.

---

## 3. Schema ledger v2

Each claim keeps its v1 fields for backward-compat during migration and adds an
entity layer. New per-claim fields:

- **`fact_key`** *(string)* — the canonical entity id, namespaced by type:
  `KBLI:55110`, `VISA:C312`, `REG:PerBKPM-5-2025`, `CAPITAL:paid-up`. Human-readable,
  stable, used in test names and offender reports.
- **`fact_kind`** *(enum)* — `code` | `sigla` | `regnum` | `threshold` | `prose`.
  Drives scope: `code`/`sigla`/`regnum`/`threshold` are language-invariant → scanned
  across ALL locales; `prose` is EN-only (and flagged as known-gap, §7).
- **`stale_value`** / **`current_value`** *(string)* — the entity's stale vs verified
  value (the structured form of the old `stale_pattern`/`current_fact` prose).
- **`fact_anchor`** *(array of regex source strings)* — tolerant patterns that match
  the entity wherever it appears: prose, table cell, any language. Word-boundary by
  construction so a longer number does not false-match (see innocence test, §5).
- **`stale_pattern`** *(string, LEGACY — retained for retro-compat)* — kept so the v1
  guard keeps passing during the migration window (§6). Removed in phase 3.

### Example: KBLI-HOTEL-55110 rewritten in v2

```json
{
  "id": "KBLI-HOTEL-55110",
  "domain": "company",
  "fact_key": "KBLI:55110",
  "fact_kind": "code",
  "stale_value": "55110 = star hotels (single combined code)",
  "current_value": "KBLI 2025 split 55110 into 55101-55105 by star rating; Hotel Melati 55120 -> 55106 (nonbintang)",
  "fact_anchor": [
    "(?<![0-9])55110(?![0-9])"
  ],
  "source": "Tabel Konversi BPS (Peraturan BPS 7/2025): '55110 Hotel Bintang 55101 ... Pecah Kode'",
  "severity": "P0",
  "_legacy": {
    "stale_pattern": "hotels (55110)"
  }
}
```

Notes on the anchor `(?<![0-9])55110(?![0-9])`:

- Matches `55110` in a table cell `| 55110 |`, in prose `"perhotelan 55110"`, and
  in any language — because the digits are the same everywhere.
- The negative look-behind/look-ahead on `[0-9]` is the word-boundary for numbers:
  it will NOT match `55110` inside `551105` or `155110` (innocence requirement, §5).
- For `fact_kind: sigla` (e.g. `VISA:C312`) the anchor is `\bC312\b`; for
  `fact_kind: regnum` (e.g. `REG:Perpres-37-2022`) it is a tolerant pattern over the
  number with separators normalised (`Perpres\s*(No\.?\s*)?37[\/-]2022`).

---

## 4. Logica del guardiano v2 (pseudo-TS — NON codice di produzione)

```text
# pseudocode — illustrative only, not the implementation

load ledger v2 (14 claims, each with fact_key / fact_kind / fact_anchor / stale_value)

for each claim:
    anchors = claim.fact_anchor.map(compileRegex)   # word-boundary by construction

    # scope: language-invariant kinds scan ALL locales (drop TRANSLATION_SUFFIX skip)
    if claim.fact_kind in {code, sigla, regnum, threshold}:
        files = collectMdx(articles + visa, includeTranslations = true)
    else:                                            # prose → EN-only (known-gap, §7)
        files = collectMdx(articles + visa, includeTranslations = false)

    offenders = []
    for each file in files:
        for each line, window(line-1, line, line+1):
            if any(anchor matches line):
                # keep the EXISTING migration-context excuse (do not regress it)
                if MIGRATION_CONTEXT.some(cue => window.toLowerCase().includes(cue)):
                    continue                         # legitimate historical/correction note
                offenders.push(file:line)

    assert offenders.isEmpty(),
        "STALE ENTITY reasserted (${claim.severity}): ${claim.fact_key} = ${claim.stale_value}"
        + " — current: ${claim.current_value}"
```

Key changes vs v1:

- **Match the entity, not the phrase** — `fact_anchor` regex instead of
  `staleHits(content, stale_pattern)`.
- **Translations included for code/number facts** — the `TRANSLATION_SUFFIX` skip
  (`content-freshness-sentinel.test.ts:36`, used at lines 106-107) is removed *only*
  for `fact_kind in {code, sigla, regnum, threshold}`; prose stays EN-only.
- **`MIGRATION_CONTEXT` is preserved verbatim** — the existing excuse list
  (`content-freshness-sentinel.test.ts:58-97`) keeps working so legitimate "old KBLI
  2020 code 55110" notes do not trip the guard. (Its EN-only fragility for non-EN
  correction notes is a known-gap, §7.)
- **Fail on entity-as-current** — the assertion message names the `fact_key` and the
  `stale_value` vs `current_value`, not a prose pattern.

---

## 5. Test di INNOCENZA obbligatorio (regola madre superscar #3)

**No `fact_anchor` is merged without proving it does NOT fire on a legitimate
neighbour, in addition to proving it fires on the real stale fact.** This is the
mother-rule of family #3: a guard ships only with both a guilt test and an
innocence test.

For each anchor, two tests:

**Innocence (must stay GREEN — legitimate neighbours):**

- `55110` inside a migration note — `"old KBLI 2020 code 55110, now split into
  55101-55105"` — MUST NOT fire (the `MIGRATION_CONTEXT` excuse covers it).
- `55110` as a substring of a longer number — `"reference 551105"` or `"155110"` —
  MUST NOT fire (the `(?<![0-9])...(?![0-9])` word-boundary).
- The *current* code in place of the stale one — `"55101"`, `"55106"` — MUST NOT fire
  (the anchor targets only the stale `55110`).
- `\bC312\b` MUST NOT fire on `"C3120"` or `"AC312B"`.

**Guilt (must turn RED — real stale fact):**

- `55110` asserted as current in prose — `"register your hotel under KBLI 55110"` —
  MUST fire.
- `55110` asserted as current in a table cell — `"| 55110 | Hotel | ... |"` — MUST fire
  (this is the v1 blind spot the whole spec exists to close).
- The same in a translation file (`.it.mdx`, `.ru.mdx`) for a `code`/`sigla` claim —
  MUST fire (the v1 translation-skip blind spot).

A claim whose anchor cannot pass both tests does not get a `fact_key` and stays on
the legacy v1 path until its anchor is corrected.

---

## 6. Migrazione (v1 → v2 senza rompere)

- **Phase 1 — ledger carries both.** Add `fact_key` / `fact_kind` / `stale_value` /
  `current_value` / `fact_anchor` to each claim while keeping `stale_pattern` (moved
  under `_legacy` or retained top-level). v1 guard keeps passing unchanged. No guard
  code touched. Reviewable as a data-only PR.
- **Phase 2 — v2 guard runs ALONGSIDE v1.** The new entity-based test file runs in
  the same Vitest suite as the existing one. Both must be green to merge. This is the
  side-by-side window where the v2 anchors prove themselves (innocence + guilt) on the
  real corpus without removing the safety net.
- **Phase 3 — remove v1.** Delete the legacy substring path and the `stale_pattern`
  field ONLY when: (a) every claim has a `fact_key` + a passing innocence test, AND
  (b) the firebreak claims (§8) are NLM-verified. Until both hold, v1 stays as the
  backstop.

---

## 7. Scope / limiti onesti

**Covered (~80%)** — every fact that has a language-invariant token:

- KBLI codes (`55110`, `55120`, `55193`, `55203`...), visa siglas (`C312`, `B211A`,
  `E33G`, `E28A`...), regulation numbers (`PerBKPM 5/2025`, `Permenkum 49/2025`,
  `Perpres 37/2022`...), numeric thresholds where the number itself is the
  discriminator (paid-up `2.5 billion` vs stale `10 billion`).
- These are caught in prose, in table cells, and across ALL locales.

**NOT covered (honest known-gap)** — prose-only facts with no code/number anchor:

- `PONDOK-WISATA-FOREIGN` (`_regulatory-claim-ledger.json:80-86`): "Pondok Wisata
  reserved for Indonesian citizens (WNI)" — the staleness is a *semantic* assertion
  (a foreigner may/may-not hold it), not an entity value. No regex anchor can
  distinguish "foreigners cannot hold Pondok Wisata" from "foreigners can hold Pondok
  Wisata" reliably.
- Similar prose-semantic claims (`MORATORIUM-PERGUB` codification nuance,
  `RETIRE-NO-SPONSOR-SINGLE` two-track conflation where the discriminator is the
  *meaning* not a number).
- These remain for a **future AI-sweep** (NLM bipolar-verifier / embedding pass) and
  are flagged `fact_kind: prose` in the ledger so they are visibly out of the
  deterministic guard's reach — not silently dropped.

This is a deliberate trade: 80% caught for $0 and zero flakiness, with the remaining
20% honestly labelled rather than pretended-covered.

---

## 8. Firebreak

**This spec arms nothing.** It is a document. Writing the v2 ledger, writing the v2
guard, and turning it on in CI are all separate operator decisions.

Hard precondition before the v2 guard can be ARMED:

- **The firebreak claims must be NLM-verified first.** The Connectome Campaign
  (lane L-KNOWLEDGE, `mini-knowledge-SUMMARY.md`) classified a set of claims as
  `⛔ P1 NLM` — stale even in the EN canonical and/or in ledger-vs-article conflict,
  needing the live NotebookLM bipolar-verifier (firebreak-blocked on Mini for
  NLM/agy login): `VISA-C312` + `KBLI-HOTEL-55110` (stale in EN, domain-uncertain
  replacement), `KBLI-VILLA-55120` (ledger-vs-article conflict), `VISA-B211A-60`,
  `PONDOK-WISATA-FOREIGN`, `MORATORIUM-SARBAGITA-FREEZE`.
  Arming the guard before these `current_value`s are confirmed against ground-truth
  would enforce **unconfirmed facts** — the guard would turn red on content that may
  actually be correct, or green on a "current" value that is itself wrong. The
  no-guess rule (anti-hallucination) forbids this: verify against NLM, then arm.
- Phase 3 (v1 removal) additionally requires every claim to carry a passing
  innocence test (§5, §6).

Until the operator says go AND the firebreak claims are NLM-verified, this stays a
spec on disk.
