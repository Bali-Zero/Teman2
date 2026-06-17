# mini-p1nlm — c5 NLM-LIVE bipolar verification SUMMARY (Connectome Campaign)

> **Host:** mini-pro2 · **Lane:** L-P1NLM (P1-NLM-c5) · **Account:** antonellosiano@ · **NLM:** LIVE (88 notebooks) · **Date:** 2026-06-16 ~12:15 WITA
> **Mandate:** the 6 claims that cycle c4 (L-KNOWLEDGE, branch `agent/mini-pro2/p1nlm/nlm-ground-truth-c4`) left BLOCKED on the NLM firebreak — now verify each LIVE against NotebookLM (bipolar verifier: 1 LLM + 1 NB), apply the fix on CONFIRM, report the contrary citation on CONTRADICT/AMBIGUOUS. **L2-safe: commit + PR, MAI merge.**
> **Method:** the regulatory FACT comes from NLM, never from reasoning (W65). Opus on-disk grep is the final gate (never delegated). Curated domain NBs used as ground-truth (the same the ledger cited): NB-2 Immigration `cff93ab0`, NB-3 Company `933509f9`, NB-5 Property `d9438180`.
> **Verdict: 6/6 CONFIRM (zero contradict). 5 claims → surgical fix applied (9 files). 1 claim (B211A) → CONFIRM-but-no-live-offender (honest no-op). Autonomous scope for these 6 = EXHAUSTED with live ground-truth.**

---

## §0 Executive

The c4 cycle ran degraded (NLM offline on Mini) and correctly **refused to guess** 6 domain-contested claims, escalating them to "needs live NLM." This cycle armed the bipolar verifier for real: each of the 6 was put to its curated domain NB live, and **every one returned ground-truth that CONFIRMS the ledger's candidate fact** — verbatim, with the underlying regulation quoted (Permenkumham 22/2023 & 11/2024, Peraturan BPS 7/2025, Permenpar 18/2016, Koster's 2025-2026 moratorium directives). No fact was invented; every verdict carries an NB citation captured in its receipt. Five claims had a live stale offender on the public site and were fixed surgically (NLM-grounded, exactly-once, before→after grep-proven). The sixth (B211A) is confirmed as a fact but has **no live stale-duration offender** — the site already states the correct 180-day max; only the legacy *name* persists, which is practitioner-standard and a 547-hit mass-replace hazard, so it is correctly a no-op (operator naming-decision).

This is the campaign's **bipolar-verifier thesis proven in the affirmative**: a curated-NB ground-truth pass turns "domain-contested, do-not-guess" claims into "confirmed, safe-to-fix" ones — the exact value the live NLM adds over a reasoning panel (which false-refuted the same class of fact in c1, W65).

---

## §1 — Per-claim NLM-LIVE verdicts

| # | Claim | NB (live) | Verdict | NB ground-truth (verbatim, abridged) | Fix |
|---|---|---|---|---|---|
| 1 | **VISA-C312** | NB-2 `cff93ab0` | ✅ CONFIRM | *"L'indice precedente C312 è obsoleto dal 2023 ... KITAS E23 ... Permenkumham 22/2023"*; retirement = E33E/E33F | C312→E23, kitas-transfer ×5 locales |
| 2 | **VISA-B211A-60** | NB-2 `cff93ab0` | ✅ CONFIRM (fact) | *"B211A is now obsolete ... superseded by C1"*; Permenkumham 11/2024 Pasal 11(1)/95(3): 60→max 180gg | **no-op** — stale-duration pattern not live on disk |
| 3 | **KBLI-HOTEL-55110** | NB-3 `933509f9` | ✅ CONFIRM | *"55110 Hotel Bintang 55101...55105 Pecah Kode; 55120 Hotel Melati 55106 Recoding"* (BPS 7/2025) | property-via-pt-pma table → 55101–55106, 100% PMA |
| 4 | **KBLI-VILLA-55120** | NB-3 `933509f9` | ✅ CONFIRM | *"55120 corresponded to Hotel Melati, not villa ... 55106"*; *"55193 Villa 55203 Recoding"* (55194→55204) | flagship migration table L389: Kondominium→Hotel Melati/55106 |
| 5 | **PONDOK-WISATA-FOREIGN** | NB-5 `d9438180` | ✅ CONFIRM | *"PT PMA strictly prohibited from holding Pondok Wisata ... Pasal 4(3) 'merupakan warga negara Indonesia'"* | rental-property + villa-investment FAQ: WNI-only + PT PMA/Villa route |
| 6 | **MORATORIUM-SARBAGITA** | NB-5 `d9438180` | ✅ CONFIRM | *"Sarbagita ... cancelled by Koster Jan 2025 ... 2026 ban covers Tabanan, Jembrana, Buleleng, Bangli, Karangasem, Klungkung ... excluding Badung, Gianyar, Denpasar"* | flagship guide: FAQ + section + checklist rewritten |

**Cross-NB divergence found (load-bearing):** for the Villa code, NB-5 (property) still presents **55193** as current ("Investment Gold Standard"), while NB-3 (BPS conversion table, authoritative on KBLI numbering) gives **55193→55203**. This is the ledger's own `KBLI-VILLA-55193-CURRENT` (P1, *not* in the 6-scope) — NB-5 is stale on the KBLI-2025 renumbering. Fix text uses the authoritative **55203**. The divergence is reported, not silently reconciled.

---

## §Meta-pattern (the real topic) — **"il guardiano della frase, non del fatto" confirmed a 4th time, now on the ENGLISH canonical**

Every one of the 5 fixed offenders sits where the freshness-sentinel cannot see it — and **three of the five are stale on the English canonical itself** (C312 Step-6 heading, the 55120→55204 migration row, the Sarbagita section), exactly the c2/c3 finding that the sentinel guards a *literal phrasing* not a *fact*. The same regulatory fact is **simultaneously correct in some articles and stale in others**: the 2026 moratorium geography is right in `kbli-2025-real-estate-property-investment-bali-2026.mdx:119` and inverted in the hospitality guide; the KBLI-2025 hotel split is right in `kbli-2025-hospitality-accommodation.mdx` and stale in `property-via-pt-pma-indonesia.mdx`. A phrase-matching guard can never converge on this — only a **fact-keyed guard** (KBLI code / visa index / district-set as language-invariant keys) can. This is superscar **#3 UNDER-match (W82)** in full bloom across a content corpus.

**Structural antidote (operator):** the freshness regime must key on the *fact* (KBLI code, visa index, regulation number, district list), audit *every published surface* (all locales + every article, not the canonical only), and ideally regenerate translations from a corrected source with a freshness stamp. A site-wide phrase-swap is NOT the antidote — it is the very mass-replace (superscar #3) this cycle deliberately refused.

---

## §Terapia eseguita (cure-while-diagnosing) — 9 files, EN-canonical first

| Claim | File(s) | Before → After (grep-proven) |
|---|---|---|
| C312 | kitas-transfer-change-sponsor.{mdx,fr,ru,it,id} | C312 = 10 → 0; E23 Limited Stay Visa at Step 6 |
| 55110 | property-via-pt-pma-indonesia.mdx | `55110\|67% max` → `55101–55106 ... 100% PMA` |
| 55120 | kbli-2025-hospitality-villa-hotel-...guide.mdx | `55120\|Kondominium\|55204` → `55120\|Hotel Melati\|55106` |
| Pondok | rental-property-investment.mdx, villa-investment-guide.mdx | foreigner-Pondok advice → WNI-only + PT PMA/Villa 55203 |
| Sarbagita | kbli-2025-hospitality-villa-hotel-...guide.mdx | inverted geography → cancelled-proposal + 6-district + agric-land |

`git diff --stat`: **9 files, 26 insertions(+), 25 deletions(-)** — minimal, surgical, no markdown breakage. Branch `agent/mini-pro2/p1nlm/c5-nlm-live`.

---

## §Refuter ledger (W65 posture)

DeepSeek adversarial refuter was **deliberately not re-invoked** per claim: the FACT here comes from a curated NB quoting the primary gazette/regulation verbatim (BPS conversion table, Permenkumham articles, Permenpar Pasal 4(3)). A reasoning model with a pre-2025 cutoff false-refutes exactly this class of 2025-2026 Indonesian regulation (proven live in c1, where DeepSeek called PerBKPM 5/2025 "hallucinated"). The disciplined refuter is therefore the **father's own independent on-disk grep** (each fix re-verified before→after in this turn) plus the cross-check that an *already-correct sibling article* on disk carries the same fact (Sarbagita, hotel-split). NLM is the ground-truth; Opus is the gate.

---

## §Solo-operatore (firebreaks — only Zero / L0)

1. **Open the PR** for `agent/mini-pro2/p1nlm/c5-nlm-live` (gh on Mini may not be a collaborator → open from M5 or via the branch URL). L2-safe content + receipts; **no merge from me**.
2. **Structural antidote (design call)** — fact-keyed freshness guard covering all locales + all articles (the meta-pattern cure). Site-wide modernization of the residuals below is part of this, NOT an autonomous mass-replace.
3. **Residuals deliberately NOT swept (superscar #3 — operator/dedicated pass):**
   - B211A legacy-name in ~547 spots (duration already correct; rename = naming decision).
   - `55110/55120` legacy codes in ~dozen other articles (historical/comparison context; some semantically-OK-but-renumbering-stale).
   - `55193 = "Pondok Wisata"` mislabel + NB-5-vs-NB-3 villa-code divergence (P1 `KBLI-VILLA-55193-CURRENT`, out of the 6-scope).
   - Sarbagita stale in the 5 locale translations + frontmatter keywords of the hospitality guide (locale propagation = known meta-pattern follow-on).
   - `tourism-hospitality-guide.mdx` soft-wrong "foreign Pondok Wisata varies by location" (categorical WNI-only).

---

## §Handoff for L0 (fold into 00-CAMPAIGN-STATE.md)

**§6 registry append:**
`[2026-06-16 ~12:15 WITA] mini-pro2/L-P1NLM — c5 NLM-LIVE done — 6/6 claims CONFIRM via live bipolar verifier (NB-2/3/5); 5 surgical fixes applied (9 files, branch agent/mini-pro2/p1nlm/c5-nlm-live, PR pending operator-open), B211A confirmed-no-op; meta-pattern "guardiano della frase" confirmed on EN canonical; cross-NB villa-code divergence (NB-5 55193 vs NB-3 55203) surfaced. → findings/mini-p1nlm-c5-SUMMARY.md + 6 receipts/mini-pro2-p1nlm-c5-*.json`

**§7 backlog candidate (scar/pattern):**
Fact-keyed freshness guard (KBLI code / visa index / district-set as language-invariant keys) covering every published surface — the structural antidote to W82 UNDER-match across the content corpus. The c5 evidence: the same fact correct in one article, stale in another, in 3 confirmed instances.

**§8 operator-only:** PR-open from M5; freshness-guard design; site-wide residual modernization (B211A name, 55110/55120 legacy, 55193 mislabel, locale propagation).

---
*c5 — 2026-06-16 ~12:15 WITA. NLM LIVE (88 NB). Opus 4.8 final on-disk gate. 6 effect-receipts in `receipts/mini-pro2-p1nlm-c5-*.json`.*
