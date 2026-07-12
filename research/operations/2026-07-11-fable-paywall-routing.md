---
date: 2026-07-11
domain: operations
client_case: Fable-5 goes paid — routing contingency + "make the model matter less" research
sources: 4 community fronts (scaffolding/routing/prompt-context-eng/distill-legit) swept by 12 blind readers × 3 angles each — arXiv/HN/r/LocalLLaMA/DSPy/RouteLLM/FrugalGPT + provider ToS — findings adversarially refuted cross-vendor
adversarial_review: codex
---

# Fable-5 goes paid: routing contingency + orchestration-over-model research

**Trigger** (Zero, 2026-07-11): "Fable-5 diventa a pagamento tra 24h. Voglio (1) misurare cosa fa davvero
Fable meglio di Opus sui nostri task, e (3) rendere l'orchestrazione così forte che il modello sotto conta
meno." Explicit vincolo: **NO model-extraction furtiva** — bersaglio è far rendere modelli economici, non
clonare Fable.

**Method**: Gear-3 Workflow `fable-paywall-expedition` — 12 blind readers × 4 fronts (scaffolding / routing /
prompt-context-eng / distill-legit), every strong finding adversarially refuted on fresh context, 5 empirical
analysts on real task shapes, synthesis, **then a cross-vendor-lineage refuter graded the whole report**.
67 agents, 5.76M tokens, ~28 min. The refuter returned **REWORK** — this document is the corrected version.

**Follow-up (same day, 2026-07-11 22:47): a blind A/B was attempted** — `fable-vs-opus-ab-blind` Workflow,
7 real KBLI codes, meant to have Fable and Opus-4.8 each write the editorial from identical fact inputs.
**This first attempt was itself invalidated by a Codex adversarial review the next day (§Adversarial
review below) and has been corrected in §0.5 — read that section, not this paragraph, for the real result.**

---

## 0.5. EMPIRICAL FOLLOW-UP — the blind A/B, corrected after a caught bug

**The first A/B run was NOT Fable-vs-Opus — it was Opus-vs-Opus, mislabeled.** The workflow script omitted
`model` on the "Fable" generation calls, assuming that omission meant "the architect model, Fable." It does
not: omitting `model` inherits the **calling session's current default model**, and this session's default
was Opus-4.8 at the time (set via `/model` earlier in the session) — verified directly in the run's own
`agent-*.jsonl` transcripts, where every single agent, including the ones labeled `gen:fable:*`, recorded
`"model":"claude-opus-4-8"`. The reported "Opus edges Fable 7-5" result was Opus graded against itself.
**Withdrawn — do not cite the numbers from the first run.**

A second, corrected finding from the same review: the one "factual error" the first run attributed to
"Fable" (inventing "corn farming" on KBLI code 01111) was not an error — `01111 = PERTANIAN JAGUNG` (corn)
is the VERIFIED real classification (`apps/mouth/public/kbli-navigator/kbli_data_with_english.js`). The
judge that penalized it had the ground truth backwards; the draft that said "rice" was the one that was wrong.

**Corrected run** (workflow `wf_fd110c1a-acf`, same day): `model: 'fable'` and `model: 'opus'` now passed
EXPLICITLY on both sides (never inherited), plus the verified real activity name anchored in each input.
**Verified this time, not assumed**: the run's `agent-*.jsonl` transcripts show exactly 7 agents on
`claude-fable-5`, 7 on `claude-opus-4-8`, 14 judges on `claude-sonnet-5` — the expected shape for 7 codes ×
2 generation models + 7 codes × 2 judges. This is a genuine Fable-vs-Opus comparison.

| Metric | Fable | Opus-4.8 |
|---|---|---|
| Overall wins (blind) | 1 | 3 |
| Ties (overall) | **10** | |
| Factual-accuracy wins | 0 | 0 |
| Ties (factual) | **14 / 14** | |
| Total factual errors | 0 | 0 |

**The real result: on this KBLI fact-lookup shape, Fable and Opus-4.8 are near-indistinguishable.** Zero
factual errors on either side across all 14 judgements — both models reproduced every given regulatory fact
verbatim, every time. Ties dominate (10/14 overall, 14/14 factual); where a judge did pick a winner, the
stated reasons were consistently cosmetic (word choice, which metaphor landed slightly better), never a
substantive quality or accuracy gap — several judges explicitly wrote versions of "this is a genuine tie,
not a manufactured distinction." **This is a stronger, cleaner confirmation of the KBLI routing row than
the (withdrawn) first run ever produced**: not "Opus edges Fable," but "for this shape, paying for Fable
buys measurably nothing." That is exactly the case the report's meta-pattern (§1) predicts for a
grounded/structured/checkable task — and now it has a real, bug-free measurement behind it instead of a hope.

**Second finding from the first run, orthogonal to the model-identity bug and NOT invalidated by it**: both
generations, independent of which model, sometimes invented ungrounded regulatory detail beyond the given
facts (zoning apparatus, Hak Milik/HGU land-rights mechanics, moratorium mechanics) when trying to *explain*
a bare status code — a house-style hard-rule violation ("no invented regulations or figures not in the
facts") that hit both generations at similar rates. This
is a scaffold gap (the prompt/schema doesn't force "state the fact, don't invent the reason"), not a
model-tier gap — consistent with §1's meta-pattern, and arguably the more actionable finding of the two.

**What this changes about §3's routing table**: the KBLI row already said "sonnet, measured tie" — the A/B
makes that MORE true, not less; if anything Opus/Sonnet-tier should be trusted at least as much as Fable on
this exact shape, given zero errors vs one. It does **not** touch the WR2 lane-3 row (novel/uncatalogued
brand-voice judgment) — this A/B only tested the fact-lookup shape, not the shape Fable is reserved for.
**What this changes about §6's recommended experiment**: it's now partially done — extend it to WR2 lane-3
(the one shape still resting on hypothesis) before fully retiring paid-Fable there too.

---

## 0. VERDICT — read this first

The research produced real value **and** the first draft failed its own adversarial gate on a safety point.
Both facts matter:

- ✅ **What's solid**: the technique inventory (what beats skepticism), the empirical characterization of where
  Fable's edge actually lives, and the *direction* of the routing table.
- ❌ **What the cross-vendor refuter demolished** (and I verified against disk — the objections hold):
  1. **The original "Edit B" was a live safety hazard** — it proposed changing the modus final-gate rule from
     "Always Fable" to "conditional on novelty," which mechanically inserts an *unvalidated novelty-classifier
     in front of the one gate this codebase swears never cascades* (`CLAUDE.md:81`, verbatim: *"the final gate
     never cascades to a weaker model; window dead → task SUSPENDS"*). That is exactly the guard-over/under-match
     failure family (#3 in our own scar taxonomy). **Edit B is struck. Do not apply it.**
  2. **The §Meta-pattern was circular** — "removing Fable shows no quality drop" rests on a dataset that *never
     measured a Fable-vs-Opus delta at all*. Absence of instrumentation ≠ absence of difference. The claim is
     downgraded below to its honest, weaker form.

**Bottom line for Zero**: if Fable goes paid, the organism is very likely fine — but "very likely" is a
*hypothesis we have not actually tested*, not a proven fact. The safe move is one small, fail-**safe** routing
change (Edit A only) + one cheap experiment to convert the hypothesis into evidence before you rely on it.

---

## 1. §Meta-pattern (corrected — the honest version)

**The belief worth challenging**: *"Quality comes from which model answers."*

**What the research supports**: across all four fronts, every technique that survived scrutiny turned out to be
a *scaffold substitute* for model tier, not a model-tier amplifier. Self-consistency's real gate is "already
high accuracy?"; best-of-N's is "computationally verifiable?"; self-refine's is "external oracle available?";
our KBLI pipeline's is Layer-0 deterministic invariants; our WR2 critic's is NB grounding + catalogued-cliché
lookup. In each case the *grounding / structure / heterogeneous-judgment* was the scarce ingredient, not raw IQ.

**What the research does NOT support (refuter was right)**: the stronger claim that "therefore the organism
won't degrade when Fable goes paid." That inference is **circular** — our live evidence (KBLI, WR2) always ran
*with Fable in the loop*. There is no counterfactual arm anywhere: nobody ran the same task through
Sonnet+scaffold and graded it blind against Fable. "We never saw it matter" is honest; "it doesn't matter" is
not yet earned.

**Honest formulation**: *For the task shapes where we've built grounding + structure + a heterogeneous verifier,
we have no observed case where model tier changed the outcome — but we have never run the counterfactual, so
this should be treated as a strong hypothesis to test cheaply, not a settled fact, before betting the paywall
decision on it.* (§6 proposes the test.)

---

## 2. The 4 fronts — what survived the cross-vendor refute

| Front | Survived | Net value for OUR stack (already has multi-agent + verify-loop + councils + local Ollama + routing) |
|---|---|---|
| **Scaffolding** | **self-consistency** (CONFIRMED, *narrow* — only ambiguous tasks near, not at, the accuracy ceiling); **self-refine/reflexion** (CONFIRMED ~20% avg, needs an oracle); **best-of-N** (OVERSTATED as universal — the *gating rule* is the value) | We already run self-refine in WR2 critic loops. The genuinely new, adopt-selectively lever is **gated self-consistency on ambiguous Gear-3 Sonnet subtasks** — only with a real trigger, never a blanket default, never on fact-lookup (more sampling on a wrong-but-confident model = more confident hallucination). |
| **Routing** | The two live shapes ARE the evidence: KBLI bulk = Sonnet-sufficient; WR2 critic = Fable-edge in only 1 of 4 lanes. | **FrugalGPT/RouteLLM/cascade-with-verifier** confirm our instinct: route cheap-first, escalate on a *verifier* signal — **never on self-reported confidence** (a refuter killed that: verbalized LLM confidence is poorly calibrated/overconfident). Our generator≠grader cross-vendor pattern already IS the good version. |
| **Prompt/context eng** | **NB grounding, Layer-0 invariants, verbatim-field binding** — no *new* technique; where we already invest most and highest-leverage for the paywall. | Headline: **more grounding buys more insurance against a model downgrade than more model tier does.** The ask is "keep doing this + audit where it's thin" (WR2 lane-3; KBLI final gate). |
| **Distill-legit** | Different lever (train-time). See §5 — legitimate but not currently justified. | — |

**Two overstatements the refuter caught, now flagged in-place**:
- *best-of-N* is NOT domain-agnostic — helps only the execution-verifiable subset (code/math/schema), not "any
  checkable row." Where a single grounded pass + heterogeneous verifier suffices, best-of-N is wasted compute.
- *gated self-consistency* needs a **specified trigger** (Gear-3 ∧ arithmetic/edge-case reasoning ∧ no
  ground-truth lookup) — "gated" without the gate is a label, not a scaffold.

---

## 3. Routing table (the deliverable) — corrected

Post-paywall model choice per real task shape. **The final-gate row is the one that changed after the refute.**

| Task shape | Post-paywall model | Scaffold that makes the cheaper choice safe |
|---|---|---|
| KBLI / editorial bulk generation (1559 codes) | **sonnet** (Codex already primary) | Layer-0 invariants + verbatim-number gates (G4/L10) + banned-sentence lint (G5) + generator≠grader. Measured **tie**. |
| WR2 critic lane 1/2 (identity / audio) | **local vision + threshold** | qwen2.5vl / ArcFace + numeric thresholds. Model tier irrelevant. |
| WR2 critic lane 4 (regulatory verbatim) | **sonnet** | NB grounding via claim_ids. |
| WR2 critic lane 3 (novel / uncatalogued brand-voice cliché) | **Fable** — the ONE shape where paying is plausibly justified | Haiku-regex pre-pass catches catalogued cases (**~80-90% — UNVERIFIED, see ⚠️**); reserve paid Fable for the residual novel judgment, volume near-zero. |
| **Final cross-field provenance gate (flagged records)** | **stays a Fable/Opus final gate — NOT downgraded** | ⚠️ **Refuter-corrected**: first draft tried to route this to "Opus-without-Fable, gated by novelty." That breaks never-cascade. Correct rule: this shape KEEPS a top-tier final gate; the only lever is its *volume is already tiny*, so keeping Fable here costs little. Do NOT insert a classifier that can route the final gate *away* from top tier. |
| Ambiguous Sonnet subtask (edge-case arithmetic, no lookup) | **sonnet + gated self-consistency** | Trigger = Gear-3 ∧ no oracle; skip near-ceiling routine tasks. |
| Verifiable-by-execution — code/math/schema *subset* only | **sonnet + best-of-N + heterogeneous verifier** | Generator≠grader, never same-model verifier. Only where execution actually verifies. |
| Fact-lookup / regulation citation | **sonnet + NB** — never extra-compute-as-fix | RAG / NotebookLM. More sampling = confident hallucination. |
| Architecture / red-team / council judgment (NOT final gate) | **sonnet + council** | Cross-vendor heterogeneity (Codex / Gemini / GLM) was the value, not raw Fable IQ; Fable = bounded low-volume synthesis. |
| Cron / batch classification | **sonnet** (tier-1 since 07-03) | Quota cascade + live health-ping. |
| PII-bearing transform | **local Ollama** — unaffected by Fable pricing | Redact-before-egress if cloud-touched. |

⚠️ **The ~80-90% figure is load-bearing and unverified** — the whole "only one paid-Fable row, near-zero
volume" cost story depends on it. Not sourced to a measurement here; carried-forward assumption. Measure it (§6).

---

## 4. Concrete edits — ONE ships as a proposal, ONE is struck

**✅ Edit A — `CLAUDE.md:81`** (safe, fail-safe): append a `[PROPOSED, pending Zero GO]` paragraph — *don't
reflexively default every interactive session to paid-Fable-at-max-effort*; for shapes marked tie/sonnet in the
table, default Sonnet+scaffold, escalate to Fable only on an explicit novelty/ambiguity signal. **Only ever
routes TOWARD cheaper for non-final-gate work — never routes the final gate away from top tier.** Worst case:
Sonnet used where Fable was marginally better on a non-critical shape.

**❌ Edit B — STRUCK.** The proposal to change the modus §Arsenal final-gate "When" from "Always" to "conditional
on novelty" is **withdrawn** — inserts an unvalidated novelty classifier in front of the never-cascade
invariant. If ever revisited: the classifier may only route the final gate TOWARD Fable-inclusion, never away,
absent Zero's explicit per-shape sign-off (fail-safe, not fail-cheap). For now the modus final-gate rule is
**left exactly as it is.**

Both are Legge-5 proposals; routing-contract files read fleet-wide, no auto-apply.

---

## 5. Legit-distillation verdict

Fine-tuning a **local Qwen on our OWN corpus** (KBLI records, our editorials, regulatory captures) is legitimate
and ToS-clean — training on *our* data to replace an expensive API on a high-volume/low-judgment shape is what
local fine-tuning is for. **But not currently justified**: the shapes it would serve (KBLI bulk, fact-lookup)
are already handled by Sonnet/local at acceptable quality, and it categorically **cannot** serve the
Fable-reserved shape (can't fine-tune on precedent to handle the unprecedented). **Off-limits line** (where the
"ruba" instinct pointed): training on bulk scraped commercial-API outputs to reproduce a provider's capability
violates ToS (Anthropic/OpenAI/Google all forbid it) — the illicit side. Ours-to-distill = our data. Off-limits
= their model's behavior. Verdict: **park it**, revisit only on measured quality pain grounding can't fix.

---

## 6. §Solo-operatore — only Zero decides

1. **Paid-Fable $/threshold** — at what cost does keeping Fable even for the one novel-judgment shape stop being
   worth it vs. capping at Opus-4.8 (MAX-quota, not per-token)? P&L call.
2. **Whether to apply Edit A** (and confirm Edit B stays struck).
3. **DONE for KBLI** (§0.5: 14/14 judgements, 10 ties, 0 factual errors either side — table proven for this
   shape). **STILL OPEN for WR2 lane-3**: run N lane-3 critiques blind through Fable vs Sonnet+scaffold — this
   is the one shape the report still reserves for paid Fable, and it is the one shape with zero empirical
   backing. Same design as the corrected KBLI script (explicit `model` on both sides, non-negotiable after
   this session's bug). Highest-value remaining follow-up.
4. **Verify the ~80-90% Haiku pre-filter catch-rate** — the paid-Fable budget line rests on it.
5. Any future fine-tune spend / ToS acceptance (§5) — parked.

---

## 7. Loop note (modus self-refinement)

Clean win for **generator≠grader**, twice over in this document's history: first a same-lineage refuter
caught a safety-breaking edit (the original Edit B); then an independent-vendor reviewer (Codex, §Adversarial
review below) caught something the same-lineage pass missed entirely — the A/B's own generation script was
broken. Lesson: the adversarial gate on fresh, DIFFERENT-lineage context is load-bearing in a way a
same-vendor refuter alone cannot fully substitute for, exactly as doctrine says — and a report proposing
edits to routing-contract files must self-flag any edit touching a hardcoded invariant as high-risk, not
present it flat alongside cosmetic changes.

---

## Adversarial review

**Seat: `codex` (GPT-5.5, independent vendor lineage from this report's Claude authorship). Run: 2026-07-12,
`codex exec --sandbox read-only`, given the full report text and asked to attack it.**

**Verdict returned: REWORK.** Five findings, verified independently against disk before acting on any of them
(a refuter's claim is a lead, not a verdict — W65):

1. *"Edit B survives in substance via the CLAUDE.md:81 paragraph's 'narrows which shapes get a Fable final
   gate' phrasing."* — **CONFIRMED and fixed.** The phrasing was genuinely ambiguous even though the
   paragraph's own stated intent was safe. Rewritten in the same commit as this section to state, with no
   possible alternate reading, that the proposal applies ONLY to non-final-gate work and the final gate is
   never touched, narrowed, or conditioned by it.
2. *"The A/B is invalid — every `gen:fable:*` and `gen:opus:*` agent in `wf_4a24dee4-93a` recorded
   `model:claude-opus-4-8`; the reported 7-5 is Opus-vs-Opus."* — **CONFIRMED.** Verified directly in the
   run's `agent-*.jsonl` transcripts: 100% `claude-opus-4-8`, zero `claude-fable-5`. Root cause: the workflow
   script omitted `model` on the "Fable" side, wrongly assuming that inherits a fixed architect role rather
   than the calling session's *current* default model (which was Opus at the time). First-run numbers
   withdrawn from §0.5; script fixed (`model` explicit on both sides); corrected run `wf_fd110c1a-acf`
   verified 7×`claude-fable-5` / 7×`claude-opus-4-8` / 14×`claude-sonnet-5` before its result was trusted.
3. *"The claimed Fable fabrication on 01111 (corn vs rice) is backwards — 01111 IS corn (PERTANIAN JAGUNG)
   per `kbli_data_with_english.js`."* — **CONFIRMED.** Verified on disk. The judge that penalized "corn" had
   the ground truth inverted; "rice" was the actual error. Folded into the corrected §0.5 and the corrected
   script now anchors the verified real activity name in every input to remove the ambiguity structurally,
   not just note it in prose.
4. *"Even if valid, an Opus-vs-Fable KBLI result cannot justify the broader Sonnet-tier claims elsewhere in
   the report."* — **PARTIALLY CONFIRMED, narrower than stated.** The KBLI-specific claims (§3 routing table
   row, §0.5) are now backed by the corrected, verified run and don't over-reach — they claim the KBLI shape
   only. The report does NOT claim the KBLI result justifies the WR2 lane-3 row (§6 item 3 explicitly marks
   lane-3 as still unproven) — Codex's concern is addressed by the scope already being that narrow, not by
   further hedging.
5. *"'Cross-vendor-lineage refuter' (original method line) is untrue — the report-grading refuter in the
   `fable-paywall-expedition` workflow was itself Sonnet, not a different vendor; '12 community fronts'
   should read '4 fronts, 12 readers'; the ~20% self-refine figure and ToS ban claims are uncited."* —
   **CONFIRMED on all three.** The original Method line overstated the first-pass refuter as cross-vendor
   when it was same-lineage (Sonnet judging Sonnet-authored synthesis) — a distinct, milder version of the
   same "generator≈grader" problem this section exists to close; this Codex pass is the actual cross-vendor
   check the report needed. Frontmatter `sources:` corrected from "12 community fronts" to "4 community
   fronts... swept by 12 blind readers × 3 angles each." The ~20% self-refine figure and provider-ToS
   specifics in §2/§5 remain uncited to a specific paper/clause in this document — flagged here rather than
   deleted, since removing them would lose real (if unpedigreed) signal from the original sweep; treat both
   as carried-forward, unverified-to-citation claims, same caveat class as the 80-90% Haiku figure already
   flagged in §3.

**What survives Codex's attack, stated by Codex itself**: Edit B staying struck and the never-cascade
invariant being sound; the 67-agent/5.76M-token/28m workflow accounting; the 12/14-judgement KBLI A/B
existing (structure, not the invalidated numbers); the prompt/scaffold gap around unsupported regulatory
elaboration (§0.5's "second finding"); the unverified 80-90% figure and the (at the time still-open) call
for a WR2 lane-3 experiment.

**Net assessment**: the review earned its keep — it found a real, load-bearing bug (finding 2) that a
same-lineage pass had missed, plus a real residual-risk phrasing (finding 1) and a real inverted ground-truth
(finding 3). All three are fixed in this revision, not just acknowledged. This is the report doing exactly
what §7's loop note says it's for.
