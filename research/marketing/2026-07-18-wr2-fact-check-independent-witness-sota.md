---
date: 2026-07-18
domain: marketing
client_case: false
adversarial_review: codex
sources:
  - FActScore arXiv:2305.14251 — atomic-fact decomposition + retrieval-verify against a fixed corpus (Wikipedia)
  - SAFE arXiv:2403.18802 (DeepMind) — per-fact multi-step search+reasoning agent; 72% human agreement, ~20× cheaper than annotators
  - RARR arXiv:2210.08726 — post-hoc research-AND-revise: retrieve evidence, agreement-check, edit unsupported spans
  - CoVe arXiv:2309.11495 (Meta) — 4-step self-verification; independence only within-model unless grafted onto retrieval
  - Self-RAG arXiv:2310.11511 — reflection-token on-demand retrieval; requires fine-tuning (not a prompt bolt-on)
  - AVeriTeC arXiv:2305.13117 — real-world claim verification; classes Supported/Refuted/NEI/Conflicting-Cherrypicking (categories, not an ordered scale)
  - AIS arXiv:2112.12870 (Google) — attributable = output supported BY the identified sources (attribution/fidelity), NOT a not-seen-by-generator requirement
  - SelfCheckGPT arXiv:2303.08896 — sampling-consistency hallucination detection; confidence ≠ truth
  - Self-preference bias arXiv:2404.13076 — LLM judges favor their own generations (grounds model-level generator≠grader)
  - LLMs cannot self-correct REASONING yet arXiv:2310.01798 — reasoning self-correction without external feedback can degrade (scoped to reasoning)
  - BERT for Evidence Retrieval and Claim Verification arXiv:1910.02655 — SUPPORTED/REFUTED/NEI entailment framing (not the original FEVER dataset paper)
  - WR2 backend on disk: wr2_fact_checker.py (DEFAULT_MODEL claude-opus-4-7:85, _verify_number_or_date_claim:357, _llm_verify_claim:434, merge no-downgrade:677-695), wr2_draft_generator.py (composer model claude-opus-4-7:840), wr2_grounding.py:_query_oracle/_query_rag, app/streaming.py (STREAM_TIMEOUT 120s:26 + IntelligentRouter), services/search/search_service.py (hybrid_search, no HTTP surface), config/job-ownership.yaml (cron_light)
---

# SOTA: a witness independent of the composer for the WR2 fact-checker

**Sprint R companion to B4** ([[discovery_wr2_factcheck_degraded_no_independent_witness_2026_07_18]]).
B4 proved the checker verifies each draft against `brief_json` — the composer's own lossy
summary — so it can only measure fidelity-to-brief. This capture asked what the field does about
it. The literature + an on-disk read of the backend force a **more honest answer than the first
draft of this file gave** (Codex CADE'd it — see `## Adversarial review`): "independent witness"
is not one thing you buy cheaply; it is THREE independences, WR2 currently has none of them, and
the cheap fix delivers only the first.

## The distinction the first draft blurred: attribution ≠ independent truth

Per AIS (2112.12870), a statement is **attributable** if a reader can verify it FROM the cited
source — the source being *supported*, not the generator being *blind to it*. That is exactly the
property B4 lacks: today the checker verifies against `brief_json` (a composer artifact), not
against the underlying authority. Verifying a claim against the raw regulatory KB **is** a real
upgrade — it catches the composer DISTORTING the authority (the live "Permenimipas 5/2025 *ended*
the requirement" vs a KB that says *requires* case). But that is **attribution/fidelity**
verification, not **independent-truth** corroboration. The KB itself can be wrong or stale (W90:
even ground-truth ages). Naming an attribution check "independently_corroborated" would be a new
overclaim. Keep the labels honest.

## Three independences — WR2 has zero

1. **Independence of the evidence.** A check-time query keyed on the claim, hitting the SAME KB
   that `wr2_grounding.py` already queried (keyed on the topic) and seeded the brief with, is a
   *second path to potentially the same chunks* — not independent. Real independence needs
   **provenance exclusion**: exclude the exact chunks/citations grounding already surfaced, or
   route through a structurally different retrieval path (oracle agentic multi-hop vs chat-stream
   vs a raw vector search), so a match means the authority corroborates *afresh*, not that the
   rail echoed.
2. **Independence of the judge.** The composer and the checker BOTH run `claude-opus-4-7`
   (`wr2_draft_generator.py:840`, `wr2_fact_checker.py:85`). Self-preference bias (2404.13076)
   says an LLM judge favors its own generations in proportion to how well it recognizes them — so
   the current LLM verify pass violates this repo's own model-level generator≠grader rule. The
   cheapest true-independence lever is **grade with a different model family** (a non-Claude
   judge, or at minimum a different tier) — orthogonal to retrieval and nearly free.
3. **Independence of the authority (truth).** The KB is one authority. Corroborating *truth*
   (not just attribution) needs a SECOND authority — the repo's own documented **NotebookLM
   bipolar verifier** (LLM + 1 NB ground-truth), or web (SAFE-style). This is the only tier that
   approaches "independent truth", and it is the most expensive.

CoVe (2309.11495) is the cautionary tale: its verification questions decorrelate wording from the
draft but are answered by the *same model from the same knowledge* — within-model independence,
which the self-correction-of-reasoning result (2310.01798, scoped to reasoning) warns can even
degrade. Independence has to come from outside the model, not from re-prompting it.

## Entailment vs regex — and the numeric precedence the first draft hand-waved

The checker ALREADY does 3-way semantic classification (`_llm_verify_claim:434`,
supports/contradicts/inconclusive) — so "add entailment" is NOT the material change; entailment
(FEVER framing, 1910.02655; AVeriTeC, 2305.13117) is already half-present. The material changes
are narrower and concrete: **(a)** swap the LLM source (today `brief`-derived, and *slide-inclusive*
when `has_external_truth`, `:676`) for provenance-excluded check-time evidence; **(b)** grade with
a non-composer model; **(c)** let the cross-check **downgrade** a deterministic `verified` — today
the merge only re-checks `unverifiable` and the code comment literally says "never downgrade a
deterministic verified" (`:677-695`), so drift a deterministic pass missed can never be caught.

The digit cross-check needs an explicit precedence rule, absent from the first draft. Today
`_NUMBER_RX` (`:357`) scans for ANY numeric token across the whole corpus — it can false-verify a
number lifted from an irrelevant sentence, call "3" contradicted when the source says "three", or
read top-k absence as contradiction when it is merely missing evidence. The defensible rule:
**explicit mismatch in the SAME semantic slot ⇒ CONTRADICTED; absence or spelled-out form ⇒
NEUTRAL / normalize-then-compare; a numeric match ⇒ necessary but not sufficient** (the entailment
layer must also hold). Entailment replaces regex for *meaning*; a slot-aware numeric check governs
*magnitude*; neither alone is the verdict.

## Cost — honestly (the first draft undercounted badly)

"1 warm HTTP + 1 LLM per claim" was wrong. `chat-stream` is not raw retrieval: it runs through
`IntelligentRouter` / agentic RAG with a **120s server stream cap** (`streaming.py:26`,
`STREAM_TIMEOUT_SECONDS=120`). `SearchService.hybrid_search` is the leanest evidence but is **not a
ready surface** — `wr2_grounding.py:20-27` documents that the local import doesn't work off-Fly
(Qdrant/embeddings/secrets), and no existing HTTP endpoint exposes those raw chunks; "no new API"
is proven only for `chat-stream`. The checker runs claims sequentially (`:677`), on a `cron_light`
job (`config/job-ownership.yaml`). Worst-case envelope for a 5-claim draft: chat-stream
`5×(retrieval+128s cap)` ≈ up to ~10 min; oracle `5×(~90s+cap)` ≈ up to ~17 min — upper bounds,
not means, but enough to falsify "latency-safe" without **a per-draft global budget, per-claim
dedup, a per-evidence cache, and a hard timeout**. Any check-time retrieval design MUST carry
those four guardrails or it starves the lane.

## Recommendation (re-tiered, honest)

**Tier 1 — attribution/fidelity, the shippable win (RARR/FActScore pattern).** For each checkable
`law`/`number`/`date` claim, retrieve fresh evidence from the KB keyed on the CLAIM TEXT ALONE
(never `brief_json`), **exclude the chunks grounding already surfaced** (provenance), and classify
claim-vs-evidence with a strict 3-way schema, applying the slot-aware numeric precedence above.
Label the result `source_attributed` — NOT `independently_corroborated`. Surface = `chat-stream`
(the only ready HTTP path), wrapped in the four guardrails. Expected: catches composer distortion
of the authority (the drift B4 can't see), fixes word-number brittleness by meaning, and makes
`contradicted` reachable — WITHOUT pretending it corroborates truth.

**Tier 2 — judge independence (nearly free, orthogonal).** Grade with a model family ≠ the
composer's `claude-opus-4-7`. Removes self-preference bias; the single cheapest honesty gain, and
it should ship WITH Tier 1, not after.

**Tier 3 — authority independence / truth (the real thing, expensive).** Add the NotebookLM
bipolar cross-check as a second authority and emit a WR2-defined provenance ladder
(`independently_corroborated` > `source_attributed` > `unverifiable` > `contradicted` — note: this
ladder is a WR2 design choice, *not* an AVeriTeC result; AVeriTeC's labels are categories, not an
ordered scale). This changes `fact_check_json.claims[i].verdict` values → every reader of
`fact_check_status`/`fact_check_json` must be consumer-mapped first (ship-lifecycle rule) →
schema-migration class → design-GO-gated.

**Scope boundary:** all tiers are fact-checker behavior changes on the editorial-integrity path.
They do not auto-publish (Legge 5). They ride the B4 ledger line, get a Codex red-team + prove-live
on real prod drafts, and — because the honest cost is real — a load/latency probe on the
`cron_light` lane before landing.

## Meta-note

B4 (from the prod failure) and this R (from the literature) converged on the same skeleton, but
the CADE on this file's first draft is the real lesson: **"independent" is a word that hides three
separate properties** (evidence, judge, authority), and it is easy — even for the analysis meant to
fix the echo — to sell a cheaper single-property fix as all three. The defective belief this kills
is subtler than B4's: not "a pre-read source can't validate writing" (it can — that's attribution),
but "attribution against the same corpus, judged by the same model, equals independent truth." It
does not.

## Adversarial review

Codex (`gpt-5.6-sol`, high, read-only) **CADE'd the first draft**; every objection was
re-verified on disk (W65) and all held. Resolutions:

- **Strongest (CADE) — independence overclaimed.** A claim-keyed query on the same KB, judged by
  the same model, is a second path to the same evidence, not an independent witness; and a
  pre-read source *can* verify attribution/fidelity (just not independent truth). **Conceded** —
  rewritten around three independences (evidence/judge/authority) and the attribution≠truth
  distinction; labels changed to `source_attributed`.
- **Judge not independent (verified `:85`/`:840`).** Composer and checker both run
  `claude-opus-4-7`. **Folded in** as Tier 2 (different-model judge).
- **Cost undercounted (verified `streaming.py:26`).** chat-stream is a 120s agentic pipeline, not
  1 HTTP; `hybrid_search` has no HTTP surface; sequential per-claim on `cron_light` multiplies
  latency. **Conceded** — honest envelope + four mandatory guardrails.
- **Entailment/numeric precedence undefined; "entailment" isn't the material change (`:434`).**
  **Conceded** — the material change is evidence-source + judge-model + allow-downgrade (`:677-695`);
  added the slot-aware numeric precedence rule.
- **Citation over-interpretation.** AIS does not require the generator be blind to the source nor
  name "same corpus blessed it" as an anti-pattern (my attribution was wrong); AVeriTeC's classes
  are categories, not an ordered provenance scale (the ladder is a WR2 invention); 1910.02655 is
  the BERT-verification paper, not the FEVER dataset paper; self-correct (2310.01798) is scoped to
  reasoning. **All fixed** in the sources block + body.
