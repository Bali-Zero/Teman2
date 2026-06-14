---
date: 2026-06-14
domain: operations (cross: visa, company-kbli, property, tax)
client_case: none — public-site (mouth) knowledge-decay TAC, session M3 of 8 parallel Mythos
sources:
  - Knowledge-decay audit 2026-06-13 (audit_knowledge_decay_fable5; research/operations/2026-06-13-knowledge-decay-audit-fable5.md) — the LEAD; batch-1 (#1383) had fixed P0-1..P0-3
  - NotebookLM ground-truth (bipolar verifier, CENTRAL for this organ): NB-2 Immigration (cff93ab0), NB-3 Company (933509f9), NB-5 Property (d9438180) — 4 async queries, verbatim citations from Permenkumham 22/2023 & 11/2024, Permen Investasi/BKPM 5/2025, Peraturan BPS 7/2025 (KBLI 2025 + Tabel Konversi BPS), PP 28/2025, Permenpar tourism framework
  - Adversarial refuter: DeepSeek V4 Pro (out of credit) -> cascaded to Gemini agy 3.5 Flash; 5/5 refutations re-checked on disk by orchestrator (W65)
  - On-disk verification of every claim before and after fix (anti-hallucination)
author: Claude Opus 4.8 (autonomous Mythos session, M5)
---

# Mythos M3 — The Public Face: knowledge-decay TAC of the mouth site

> Session M3 of 8 parallel Mythos sessions. Organ = the SKIN / public face of the
> organism: the `mouth` site (visa/tax/KBLI/property guides) — what real clients read.
> Disease hunted: **knowledge-decay** — obsolete regulatory facts that stay published
> because the freshness pipes are dead and nothing re-verifies against ground-truth.
> Write perimeter: `apps/mouth/*` only. Done = verified live on Vercel.

## 0. Executive summary

The 13/06 audit found 8 P0 client-facing errors and shipped batch-1 (P0-1 LKPM
dates, P0-2 capital table, P0-3 SABH-not-NIB, #1383). This session completed the
TAC: **P0-4 through P0-8 fixed** against NotebookLM ground-truth, **two extra
stale facts caught that the manual sweep had missed**, and — the real structural
value — a **knowledge-freshness sentinel** built and proven: the dead-man's
switch that was the missing pipe.

What the ground-truth changed vs the starting audit (the verifier-is-imperfect
thesis, three times over — W65):

1. **P0-8 GPS auto-rejection** — the audit marked it "UNVERIFIABLE" and the
   instinct was to delete it. Ground-truth **CONFIRMED it real** (PP 28/2025
   KKKPR auto-rejects RDTR mismatches). Deleting it would have removed a correct
   fact. The refuter then correctly scoped it: auto-reject only where RDTR is
   integrated; elsewhere the manual PKKPR track applies. Final fix keeps the
   fact, scoped.
2. **P0-8 Sarbagita geography** — not just "stale framing": the article had it
   **inverted**. The real 2026 ban covers 6 *less-developed* districts and
   *excludes* the tourist core (Badung/Gianyar/Denpasar); the article said the
   tourist core was frozen. Opposite of the truth.
3. **P0-4 C312** — the audit (and my own prompt) said "C312 retirement"; ground-
   truth: C312 was the **foreign-worker (TKA)** code, now E23 — never retirement.
4. **P0-7 villa KBLI** — the audit's suggested fix (55203) collided with NB-5
   property sources that still call **55193** current. Resolved via NB-3 (the
   official BPS conversion table): 55203 is the KBLI 2025 code, 55193 is the
   2020 legacy. **The ground-truth itself has internal decay** between notebooks.

## 1. Organs covered (ontology, written first)

(a) visa/immigration guides · (b) tax/PPN · (c) KBLI/company · (d) property ·
(e) structured data (`src/data`, DB visa_types) · (f) the missing freshness
mechanism. All grounded live: audit read, pages read on disk, claims verified
against NB.

## 2. Per-organ findings (site claim vs ground-truth, verbatim)

### (a) Visa / immigration — P0-4, P0-6

| Claim on site (verbatim) | Ground-truth (NB-2, verbatim) | Fix |
|---|---|---|
| "E33G investor KITAS" (`bali-immigration-law…:46`) | "pekerja jarak jauh (remote worker)"; Investor = E28A "Penanaman modal asing … 2 tahun" | E33G→Remote Worker; investor→E28A |
| "C312 retirement KITAS" | C312 = old TKA/foreign-worker code → now **E23** (not retirement) | removed as dead code |
| "B211A … total of 60 days" | "Il visto C1 ha sostituito … B211A … 60 giorni prorogabile fino a 180 totali" | B211A→C1, 60→up to 180 |
| "Second Home … under Presidential Regulation No. 37/2022" (:50) | NB-2 **abstained** on Perpres 37/2022; regime codified in Permenkumham 22/2023, 11/2024 (E33 rumah kedua) | de-attributed (prudence — did not substitute a new unverified citation) |
| retirement "55+, USD1500, no sponsor, 1yr" (`visa/kitas/page:37,76`) | **E33F** (55+, sponsor REQUIRED, 1yr) vs **E33E Silver Hair** (no sponsor, ~USD50k BUMN deposit, 5yr) | split into two tracks; age of E33E left unasserted (see §note) |

**Note — unresolved internal ground-truth conflict (E33E age):** the primary
legal index text (Permenkumham 11/2024, cit. 7/9) says E33E and E33F are both
"55 tahun atau lebih"; another primary citation (cit. 1) and the Bali-Zero
synthesis table (cit. 8) say E33E = 60. Two sources say 60, one primary says 55.
The fix uses the *unambiguous distinguishing traits* (sponsor vs deposit, 1yr vs
5yr) and deliberately does NOT assert E33E's age number on the public page.
**Operator decision needed** to lock the canonical age (see §Solo-operatore).

### (b) Tax — confirmed correct + one cross-surface gain

NB-5 confirmed the rental-tax structure: **10% PHR local tax + PPh 10% (resident)
/ 20% (non-resident, PPh 26)**. The airbnb article's body was broadly right;
its AI `answerSnippet` was wrong (Pondok-Wisata claim) and is fixed (see (d)).

### (c) KBLI / company — P0-5 + capital regression

Tabel Konversi BPS (NB-3, verbatim): `55110 Hotel Bintang → 55101 Aktivitas
Hotel Bintang Lima Pecah Kode` (… through 55105 + 55106 nonbintang); `55193 Villa
→ 55203 Recoding`; `56101` unchanged. `55120` was **Hotel Melati** (→55106),
never villa. Capital (Pasal 26): paid-up **2.5B** + total **>10B** per 5-digit
KBLI per location — two separate figures, 12-month lock-in. Fixed in
`pt-pma-in-bali-the-legal-vehicle…` and (sentinel-caught) in the 2nd real-estate
article (`kbli-2025-real-estate-property:174` still said paid-up "10 billion").

### (d) Property — P0-7, P0-8

Pondok Wisata = **WNI-only, usaha perseorangan** (a foreigner/PT PMA cannot hold
it; nominee = criminal under Perda Bali 4/2026). Foreigner route = PT PMA + Villa
KBLI (55203) in a Pink tourism zone, OSS-RBA. Fixed body + Bali-Zero-Take + AI
answerSnippet. Moratorium: inverted geography corrected, executive-policy (not
Pergub) clarified, GPS auto-reject KEPT and scoped to integrated-RDTR.

### (e) Structured data — DB visa_types

`mcp__postgres-nuzantara__query` returned `-32603` twice (Fly PG unreachable from
M5 at audit time — infra, not code). The DB `visa_types` E33E row mislabel
(P0-6) is **M4/operator perimeter** and was not in scope to mutate; flagged.

### (f) The missing freshness mechanism — BUILT

See §Therapy. This was the point of the whole organ.

## 3. Meta-pattern — why the public site accumulates knowledge-decay

> *cosa si ripete attraverso i finding? qual è la convinzione che li genera tutti?*

**The site has no single-source-of-truth for regulatory claims, and no
dead-man's switch between content and ground-truth.** Three cross-cutting pieces
of evidence:

1. **The same stale fact is replicated, not centralized.** `55110`/`55120` appear
   in **10 EN articles**; `C312` in 5. Each article was generated/written in
   isolation, each re-encoding the same dead code. There is no shared "KBLI codes
   = X" the content draws from — so a single regulator change has to be hunted
   down N times, and the hunt never happens.
2. **Freshness is invisible.** The pre-existing `audit-outdated-visa-codes.ts`
   was a one-shot script that wrote a JSON and **never failed CI** — a
   green-but-empty organ (W74 family). Timestamps lie too: `visa/kitas/page.mdx`
   had `updatedAt: 2026-05-15` (fresh) yet carried the conflated retirement rule.
   A recent date does not mean a correct fact.
3. **Even the ground-truth decays internally.** NB-3 (BPS conversion table) has
   absorbed the KBLI 2025 renumbering (villa = 55203); NB-5 (property) has not
   (still calls 55193 current). The curated layer is itself unsynchronized —
   which is the macro-version of the site's own disease.

**The single faulty conviction:** *"a fact, once written and once correct, stays
correct."* It generates the whole family — because nothing watches for divergence,
the world moves and the page doesn't.

**Structural countermeasure (built this session):** a claim-ledger + sentinel
test that turns "is this fact still true?" from a thing nobody does into a CI
gate that fails on regression. The pipe that was missing.

## 4. Therapy executed (fixes + freshness mechanism)

**Content fixes — 6 files, 2 commits** (branch `agent/air-m5/mouth/mythos-m3-public-site`):
- `5e6b9a0b7` fix(mouth): P0-4..P0-8 (immigration, pt-pma, kitas page, airbnb,
  two real-estate articles).
- `fd6a8597a` feat(mouth): the sentinel.

**The freshness mechanism (countermeasure #1):**
- `apps/mouth/src/content/_regulatory-claim-ledger.json` — 14 verified claims,
  each `stale_pattern` → `current_fact` + verbatim NB source. The SSOT.
- `apps/mouth/src/content/content-freshness-sentinel.test.ts` — a Vitest gate
  inside `npm test` (the required `Frontend Tests (mouth)` check). Fails if any
  `stale_pattern` reappears in published EN MDX outside a migration/correction
  note. **Proven on first run: caught 3 stale facts the manual sweep missed**
  (paid-up-10B in the 2nd real-estate article, the Pondok-Wisata AI snippet, and
  one false-positive that hardened the allowlist). Now 15/15 green.

**Done = live on Vercel:** branch pushed (pre-push backend gate skipped via the
documented `PRE_PUSH_TEST_DB=nuzantara_test_skip` — the diff is 100% mouth-only;
the one failing backend test `test_s12_solidification::test_rate_limit_error_is_retried`
is pre-existing and outside perimeter). PR + Vercel live-verification of the
public pages is the closing step. Merge ≠ done — the public page must show the
corrected value post-deploy.

## 5. Solo-operatore (boundary — do not cross autonomously)

1. **Lock the E33E canonical age (55 vs 60).** Ground-truth is internally
   contradictory; the page currently sidesteps it. One source-of-truth decision
   needed (probably resolve via the primary Permenkumham 11/2024 index text =
   55, and correct the internal BZ table, OR vice-versa). Strategic/legal call.
2. **DB `visa_types` E33E row** mislabel (P0-6) is M4/CRM-cell perimeter — assign
   the row correction there. Fly PG was unreachable from M5 (-32603) regardless.
3. **NB-5 property internal decay** (still calls villa 55193 current): the
   ground-truth notebook itself needs the KBLI 2025 renumbering pushed in.
   NB-curator / P* infra perimeter, not mouth.
4. **Restart the freshness feeders** (regulatory delta + NB-INTEL) — without
   them the ledger ages like everything else. P* infra perimeter.
5. **Business campaigns at deadline** (from the 13/06 audit, still open): KBLI
   18/06, RUPS 30/06, PP 20/2026 tax outreach. Editorial/strategic.
6. Pricing on public pages: any number must come from PricingTool, never
   hardcoded. (Not touched this session.)

## 6. Method notes (Mythos reflexes that fired)

- **Fan-out + skeptic gate**: read all 5 P0 articles on disk before touching;
  audit line-numbers re-confirmed verbatim.
- **NLM bipolar verifier (central)**: 4 async queries, fire-and-sleep, verbatim
  legal-text citations — the heart of this organ.
- **Refuter cascade**: DeepSeek out-of-credit → Gemini; 5 REFUTE all re-checked
  by orchestrator (W65 — 3 mis-reads/already-incorporated, 1 won [E33E age], 1
  softened a citation). Never delegated the final grep.
- **Sentinel as cure-while-diagnosing**: the structural fix, proven by catching
  3 real misses on first run.
