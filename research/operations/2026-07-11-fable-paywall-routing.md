---
date: 2026-07-11
domain: operations
client_case: Fable-5 goes paid — routing contingency + "make the model matter less" research
sources: 12 community fronts (arXiv/HN/r/LocalLLaMA/DSPy/RouteLLM/FrugalGPT + provider ToS) — swept by 12 blind readers, findings adversarially refuted cross-vendor
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

**Follow-up (same day, 2026-07-11 22:47): the recommended blind A/B was run** — `fable-vs-opus-ab-blind`
Workflow, 7 real KBLI codes (from `agent/air-m5/mouth/kbli-editorials`), Fable and Opus-4.8 each wrote the
editorial from identical fact inputs, blind-judged (model identity hidden) on factual accuracy + house-style.
Result in **§0.5** — it does not simply confirm the hypothesis, it complicates it, and that's reported honestly.

---

## 0.5. EMPIRICAL FOLLOW-UP — the blind A/B result (KBLI shape)

**12/14 planned judgements completed** (2 failed on judge session-limit, not a design flaw — reported as
missing, not fabricated). Small sample (7 codes) — this is a signal, not a law, but it's a real measurement
where before there was none, and the direction is worth stating plainly:

| Metric | Fable | Opus-4.8 |
|---|---|---|
| Overall wins (blind) | 5 | **7** |
| Factual-accuracy wins | 0 | 2 |
| Ties (factual) | 10 | 10 |
| Total factual errors | **1** | 0 |

**On this KBLI fact-lookup shape, Opus-4.8 was not worse than Fable — it edged ahead, both on raw wins and
on the one axis that matters most for this task (factual accuracy).** The single factual error found across
all 12 judgements was Fable's: on code 01111 it invented a specific crop ("corn farming / Pertanian Jagung")
that the given facts never specified and that doesn't match the code's real-world referent — a fabrication
that propagated through headline, standfirst, body and pullQuote. Opus's parallel draft used the correct
plain-English gloss and committed no such error.

**Second finding, orthogonal to the model question**: both models, independent of which one, sometimes
invented ungrounded regulatory detail beyond the given facts (zoning apparatus, Hak Milik/HGU land-rights
mechanics, moratorium mechanics) when trying to *explain* a bare status code — a house-style hard-rule
violation ("no invented regulations or figures not in the facts") that hit both models at similar rates. This
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
3. **The cheap experiment that converts the meta-pattern from hypothesis to fact** (recommended before relying
   on this): run N flagged KBLI records + N WR2 lane-3 critiques *blind* through both Fable and Sonnet+scaffold,
   grade independently. No delta → table proven. Delta → we learned where Fable earns its price *before* paying
   blind. ~1 short Workflow, highest-value follow-up.
4. **Verify the ~80-90% Haiku pre-filter catch-rate** — the paid-Fable budget line rests on it.
5. Any future fine-tune spend / ToS acceptance (§5) — parked.

---

## 7. Loop note (modus self-refinement)

Clean win for **generator≠grader**: the cross-vendor refuter caught a safety-breaking edit the same-lineage
synthesizer wrote and would have shipped. Lesson: the adversarial gate on fresh, different-lineage context is
load-bearing, exactly as doctrine says — and a report proposing edits to routing-contract files must self-flag
any edit touching a hardcoded invariant as high-risk, not present it flat alongside cosmetic changes.
