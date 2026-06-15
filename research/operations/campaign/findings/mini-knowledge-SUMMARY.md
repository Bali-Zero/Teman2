# mini-knowledge — L-KNOWLEDGE lane SUMMARY (Connectome Campaign)

> **Host:** mini-pro2 · **Lane:** L-KNOWLEDGE · **Account:** antonellosiano@ · **Started:** 2026-06-16 05:31 WITA
> **Mandate:** knowledge-decay + domain correctness — continue the Fable5 audit (2026-06-13, 8 P0) on the Mini.
> **Method:** ground-truth via the on-disk NB-verified claim ledger (NLM/Gemini OAuth offline on Mini = firebreak),
> grep-precise surface audit, DeepSeek adversarial refuter, Opus on-disk final gate (never delegated — W65).
> **Cycle 1 verdict: 1 P0 fixed (PR pushed) · 1 P0-structural meta-pattern found · 3 fronts verified-clean · 2 firebreaks surfaced.**

---

## §0 Executive

The Fable5 audit (13/06) correctly diagnosed knowledge-decay and built the right antibody — a
`_regulatory-claim-ledger.json` (14 NB-verified claims) + a `content-freshness-sentinel.test.ts` that fails
CI if any stale fact reappears. **But the antibody guards only the English canonical `.mdx` and explicitly
defers the 7 translation locales (`.id/.it/.ru/.fr/.de/.es/.nl`) to "a separate audit" that does not exist.**
Result: the exact surface served to local (Bahasa-reading) clients silently rots. Cycle 1 confirmed this on
disk: the LKPM "the 10th → 15th" correction (PerBKPM 5/2025) shipped to the English article but **all 4
occurrences in the Indonesian article were left stale**. Fixed and pushed (PR pending operator open).

---

## §1 — FRONT: public site / KB localized surfaces  → **P0 (1 fixed, channel-wide gap)**

**Finding KN-1 [P0, FIXED]** — `apps/mouth/src/content/articles/business/pt-pma-first-year-compliance.id.mdx`
- Stale: LKPM quarterly deadline taught as **"tanggal 10 / 10 April-Juli-Oktober-Januari"** in **4 places**
  (FAQ frontmatter L46, prose L262 "jatuh tempo 10 Januari", compliance table L282, FAQ body L343).
- Current fact: **1st–15th window** (Q1 15 Apr · Q2 15 Jul · Q3 15 Oct · Q4 15 Jan).
- **NB-citation:** ledger `LKPM-DEADLINE-10TH` → *PerBKPM 5/2025 Pasal 285(3)* (ledger `verified_on` 2026-06-14,
  ground-truth NB-2/NB-3/NB-5). Corroborated by the already-shipped English sibling + 4 independent IDN legal
  sources (SmartLegal.id, Prolegal, Permitindo, Golaw).
- **Correction shipped:** branch `agent/mini-pro2/mouth/lkpm-id-freshness`, commit `9ea89635c`, pushed to origin.
  Before→after proof: `grep '10 (April|Juli|Oktober|Januari)' = 4 hits → 0`. BPJS/PPh-21 "10th" deadlines
  (separate statutes) deliberately untouched (anti-over-match, superscar #3).

**Lead KN-2 [P1, staged next cycle]** — locale-invariant stale codes living in translation surfaces the
sentinel cannot see (raw grep counts are LEADS — most are legitimate migration-context or comparison):
- `C312` asserted as the **current** work-KITAS in `kitas-transfer-change-sponsor.{fr,ru}.mdx:229-231`
  ("le KITAS Visa de séjour limité C312"). Ledger `VISA-C312`: C312 is a retired pre-2024 code → now **E23**.
  Needs English-sibling diff before fixing (could be a translated-but-not-updated artifact). **Likely genuine.**
- `55110` presented as a current hotel KBLI in property tables `property-via-pt-pma-indonesia.{it,ru,id,fr}.mdx:132`.
  Ledger `KBLI-HOTEL-55110`: 55110 split into 55101–55105 (Peraturan BPS 7/2025). Verify per-file context next cycle.
- `55193` (170 raw hits) and `B211A` (547 raw hits) are **mostly legitimate** (migration narrative / historical
  comparison) — NOT bulk offenders. Do **not** mass-replace (superscar #3).

**Negative/clean (verified):** paid-up capital `IDR 2.5B` correct across `llms.txt` + KBLI data; English LKPM,
English RUPS/NIB (SABH not NIB suspension) correct (batch-1 #1383 held on the English surface).

**Structural smell [P2]** — nested duplicate dir `apps/mouth/apps/mouth/data/KBLI_2025_FINAL_CLEAN.json`
(frozen 3 May). Superscar #1 (HOME-fork) smell — a stale data copy. Verify referrers before any cleanup.

---

## §2 — FRONT: golden corpus  → **CLEAN ✅**

`apps/evaluator/zantara_persona_eval/validate_corpus.py`: **50 scenarios, 150 questions, 0 schema errors.**
1 freshness warning (correct, not a bug): `COMP-003` expires **2026-06-18** ("KBLI 2025 national switch deadline").
→ business-critical: this corpus fact + the public KBLI 18/06 campaign need a coordinated update *after* the deadline.

---

## §3 — FRONT: WhatsApp RAG bridge freshness  → **CLEAN ✅ (reconfirmed)**

`apps/backend-rag/backend/services/wa_copilot/kg_bridge.py`: grep for hardcoded stale norms
(`LKPM|tanggal 10|55193|B211A|C312|10 billion|paid-up`) = **0 hits**. The bridge carries no hardcoded
regulatory facts (pulls from the KG), consistent with the Fable5 "100% CURRENT" finding (13/06). Reconfirmed.

---

## §4 — FRONT: ground-truth tooling  → **DEGRADED (firebreak, see §Solo-operatore)**

NotebookLM MCP **not connected** on Mini (`claude mcp list` → absent) and `agy` (Gemini) **OAuth expired**
(interactive login required). The mandated "bipolar verifier (1 LLM + 1 NB)" runs in degraded mode this cycle:
NB side = the on-disk NB-verified ledger (preserves NB-2/3/5 citations from 13/06) + targeted public-web
cross-check. **No fresh regulatory fact was invented** (anti-hallucination). New facts requiring live NLM
ground-truth are blocked pending operator login.

---

## §Meta-pattern (the real topic) — **"Il guardiano monolingue"**

> **One faulty belief generates the whole family: "guarding the canonical surface = guarding the content."**

The 13/06 audit built a freshness guard scoped to English `.mdx` and wrote, in the test header, that the 7
translation locales are *"audited separately"* — a promise never kept. So the guard **runs green in CI while
the highest-value audience (Bahasa-reading Indonesians, the primary consumers of the localized site) is served
exactly the stale facts the English readers are protected from.** This is superscar **#2 (Esiste≠Armato)** in
its subtlest form — the guard *exists and runs*, but its **scope has a hole shaped like the most important
audience** — crossed with **#3 (guard coverage ≠ real surface)**, inverted: not over-match, but **under-scope**.

**Three cross-cutting evidences:** (a) LKPM stale in 4 IDN spots while EN is clean; (b) C312 stale in FR/RU
while ledger says E23; (c) 55110 stale in IT/RU/ID/FR property tables. All three share the one cause.

**Second, deeper corollary (design-level):** even *removing* the `TRANSLATION_SUFFIX` skip would NOT fix this —
the ledger's `stale_pattern`s are **English strings** ("by April 10", "Paid-up Capital: IDR 10 billion") that do
not match translated text ("tanggal 10", "modal disetor Rp 10 miliar"). Guarding localized surfaces needs either
per-locale stale patterns **or** a structural "translations are regenerated from corrected English source +
freshness-date stamp" design. → architectural decision for the operator (§Solo-operatore).

**Structural antidote (proposed):** extend the freshness regime to localized surfaces — but as a *designed*
unit (localized patterns or regen-from-source), not a naive scope-widening that would go red without matching.
Staged: cycle-2 completes the localized offender sweep (C312, 55110, …) and fixes them; the sentinel extension
lands green only after the offenders are cleared.

---

## §Refuter ledger (W65 live instance — valuable)

DeepSeek V4 Pro (`reasoning_effort` default), adversarial prompt on KN-1 → **VERDICT: REFUTED** ("the 10th is
still live; PerBKPM 5/2025 is hallucinated"). **Adjudicated: false-refute.** A reasoning model with a pre-2025
cutoff cannot know a 2025 Indonesian regulation and confidently calls it fictitious. Overridden by the father's
independent on-disk + web verification (ledger NB-verified + EN canonical + 4 IDN legal firms all confirm the
15th and the real regulation). DeepSeek point (3) — "leaving BPJS/PPh untouched was correct" — *was* accepted
(the part it could reason without 2025 data). **This is the campaign's bipolar-verifier thesis proven live: a
reasoning council without ground-truth FALSELY refutes current regulatory facts — which is precisely why
domain facts demand NLM, not a reasoning panel.** (opus-mythos: "anche il refuter allucina".)

---

## §Terapia eseguita (cure-while-diagnosing)

| Action | Status | Proof |
|---|---|---|
| Fix KN-1 (4 LKPM stale deadlines, IDN) | ✅ committed `9ea89635c`, pushed | branch on origin; before→after grep 4→0 |
| Open PR | ⏳ operator (gh token not collaborator on Mini) | URL: `github.com/Balizero1987/Teman2/pull/new/agent/mini-pro2/mouth/lkpm-id-freshness` |

---

## §Solo-operatore (firebreaks — only Zero / L0)

1. **Open the PR** for branch `agent/mini-pro2/mouth/lkpm-id-freshness` from M5 (gh authenticated there) or
   the URL above. L2-safe content fix, no merge required from me.
2. **Mini NLM login** (`nlm` / NotebookLM MCP) + **`agy login`** (Gemini) — interactive OAuth. The L-KNOWLEDGE
   lane runs degraded without them (no live ground-truth, no Gemini width). Pre-flight §9 already flagged both.
3. **Architectural decision** — how to extend freshness-guarding to the 7 translation locales (per-locale
   patterns vs regenerate-from-source-with-freshness-stamp). This is the structural antidote to the meta-pattern;
   it is a design call, not an autonomous edit.

---

## §6/§8 handoff for L0 (fold into 00-CAMPAIGN-STATE.md)

**§6 registry append:**
`[2026-06-16 05:31 WITA] mini-pro2/L-KNOWLEDGE — cycle 1 done — KN-1 P0 fixed (PR branch agent/mini-pro2/mouth/lkpm-id-freshness, commit 9ea89635c, pushed); meta-pattern "guardiano monolingue" found; corpus+WA-bridge clean; NLM/agy firebreak. → findings/mini-knowledge-SUMMARY.md + receipts/mini-pro2-knowledge-lkpm-id-freshness.json`

**§7 backlog candidate (scar/pattern):**
"Guardiano monolingue" — freshness/guard built for canonical surface only; localized mirror (highest-value
audience) left unguarded. Sub-family of superscar #2 (Esiste≠Armato) ∩ #3 (coverage≠surface, under-scope).
Candidate antibody: guard regime must cover every *published* surface, not just the source-of-truth one.

**§8 operator-only additions:** PR-open from M5; Mini `nlm login` + `agy login`; translation-freshness design decision.

---

## §Verdetti per fronte (verified this cycle)

| Front | Verdict | Evidence |
|---|---|---|
| Site localized (`.id` LKPM) | ❌→✅ FIXED | 4 stale → 0, PR pushed |
| Site localized (C312/55110) | ⚠️ LEADS staged | grep hits, need EN-sibling diff |
| Site EN canonical | ✅ CLEAN | sentinel armed in CI, batch-1 held |
| Golden corpus | ✅ CLEAN | 0 schema errors; 1 expected freshness signal (KBLI 18/06) |
| WA bridge | ✅ CLEAN | 0 hardcoded stale norms |
| Ground-truth tooling | ⛔ DEGRADED | NLM+Gemini OAuth offline (firebreak) |

**Not done (mandate "every front a verified verdict"):** §1 localized offender sweep (C312/55110/others) +
their fixes; live-NLM reconfirm of the ledger's P0 facts (blocked on firebreak #2). → cycle 2.

---
*Cycle 1 — 2026-06-16 ~05:31 WITA. Opus 4.8 final on-disk gate. Effect-receipt:
`receipts/mini-pro2-knowledge-lkpm-id-freshness.json`.*
