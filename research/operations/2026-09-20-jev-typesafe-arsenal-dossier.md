---
date: 2026-09-20
domain: operations
client_case: none
adversarial_review: codex
sources:
  - https://docs.typesafe.ai/llms.txt
  - https://docs.typesafe.ai/api.md
  - https://docs.typesafe.ai/models.md
  - https://docs.typesafe.ai/confidence.md
  - https://docs.typesafe.ai/model-jaggedness/jev-1.13.md
  - https://docs.typesafe.ai/cookbooks/rerank_typesafe.md
  - https://docs.typesafe.ai/cookbooks/hierarchical_classification.md
  - https://docs.typesafe.ai/cookbooks/classifying_rag_passages.md
  - https://docs.typesafe.ai/cookbooks/citation_check.md
  - https://docs.typesafe.ai/cookbooks/llm_guardrails.md
  - https://docs.typesafe.ai/cookbooks/sde_cascade.md
  - https://docs.typesafe.ai/cookbooks/parallel_questions.md
  - https://docs.typesafe.ai/cookbooks/skill_suggestion.md
---

# Jev 1.13 / TypeSafe System One — arsenal dossier + application plan

Date: 2026-09-20 · Machine: M5 · Key provisioned by Zero (`~/Desktop/JEV.rtf`) · Three live
probes run against `api.typesafe.ai` in this session. No client data entered any prompt: every
probe used a synthetic request or public KBLI corpus text. **Adversarially reviewed by Codex
(generator ≠ grader); §4, every prove-live in §5, and the whole sequencing table in §6 were
rewritten as a result — see §8 for what the review broke and why it was right.**

---

## 1. What Jev is, stated as a capability and not as a model

Jev is not a chat model and does not generate text. It takes **state** (text, JSON object or
array) plus a map of **typed questions**, and returns **one calibrated answer per question with
its full probability distribution**. It cannot invent a value outside the options you supply —
that is the whole point, and it is why its output is composable in ordinary code.

Three primitives, and choosing between them is a semantic decision, not a stylistic one:

| Primitive | Returns | Use when |
|---|---|---|
| `Noul` | probability of yes, 0-1 | a condition either holds or does not; no confidence field, the probability IS the answer |
| `Choice` | one option + confidence + full distribution | one of a closed set (≤255 options) |
| `Score` | probability-weighted position on ordered levels + confidence | degree along a described dimension |

**Economics** (this is the reason the plan below is worth running):

| | value |
|---|---|
| Model ID | `jev-1.13.0` (aliases `jev-latest`, `jev-preview`) |
| Price | $0.042 / Mtok input — **output tokens are free** |
| Context | 64k total, 32k for state + longest question |
| Rate limit | 1,200 req/min, 250k tok/s |
| Endpoint | `POST https://api.typesafe.ai/v1/systemone`, `Authorization: Bearer` |
| Training on our data | no; zero-retention only on enterprise plans |

At $0.042/Mtok a 600-token judgment costs **$0.000025**. A lane doing 1,000 judgments a day
costs **under $1/month**. Cost is not the constraint here; the PII boundary is (§4).

### Batching — a large win in the vendor's test, to be re-measured in ours

TypeSafe states that questions in one request are scored independently against the same state.
Their GDPR test (13 questions, ~54k-char article) reports **12.2× cheaper and 10.0× faster**
than 13 separate calls, with standard deviation 0.0 on the answers. **These are the vendor's
numbers on the vendor's document, not ours**, and the saving is only that large when the state
dominates the payload — with a 400-token WhatsApp message and four questions the ratio shrinks
towards 1. The structural argument (transmit the document once, not thirteen times) is sound and
worth designing around; the multiplier is a hypothesis each lane re-measures on its own traffic.

---

## 2. Three probes run in this session (live, not quoted)

**Probe A — domain routing, Italian input.** State: *"Posso aprire un ristorante a Canggu con
una PT PMA se sono straniero?"* → `domain=company` at confidence **1.0**, `is_urgent=0.06`.
427 input tokens.

**Probe B — WhatsApp intent, colloquial Indonesian.** State: *"eh mbak, kemarin saya sudah kirim
dokumen tapi belum ada kabar, gimana ya"* → `intent=status_chase` at **1.0**,
`frustration=0.99/3` ("mildly impatient", 0.98), `needs_human=0.6`. 544 input tokens.
**Not one of those words appears in the 735-line keyword table of
`apps/backend-rag/backend/services/classification/intent_classifier.py`.**

**Probe C — KBLI 2025 selection, real corpus.** 11 five-digit candidates from division 56 built
from `data/source_documents/KBLI_2025_FINAL_CLEAN.json`, state = *"beach club a Canggu:
ristorante con cucina, bar con alcolici, piscina e musica dal vivo"* → **56101** (Restoran) at
0.77, **56301** (Bar) at 0.15, confidence 0.73. 662 input tokens. The label is right, and the
spread is plausible for the right reason — a beach club genuinely straddles restaurant and bar.

Three probes show the shape works on our languages and our corpus. **They do not measure
calibration**: one plausible 0.73 is an anecdote, not evidence that 0.73 means 73%. Calibration
is a property of a distribution over many labelled cases, and every lane below that gates on a
threshold owes that measurement before it gates on it in production.

---

## 3. What Jev is bad at — read before designing any lane

Documented jagged edges of 1.13, each of which maps to a design rule:

| Failure mode | Rule it imposes here |
|---|---|
| **Math and counting** | never ask it to compute a price, a duration, a deposit. Code does arithmetic. |
| **Dates as ordered quantities** | it reads dates as text. Visa expiry, 60-day windows, overstay days → code. Extract components via `Choice`, compare in Python. |
| **Numeric representations** (hex, RGB, proximity) | bucket into named categories before sending |
| **Literal reading** | it answers the question you wrote, not the one you meant. Boundary cases go in `criteria`, explicitly. |
| **Indirection / double negatives** | write instructions directly, name the state field |
| **Large state with irrelevant detail** | accuracy falls as noise grows. Retrieve and filter in code first. |
| **Adversarial content** | it can be steered by injected instructions — so the injection-detection lane (L4) must itself be tested adversarially, not assumed |
| **Generation** | it is not trained to generate. Never ask it for prose. |
| **Structural invariants** | complementary questions are not guaranteed to sum to 1. Do not port a threshold from one primitive to another. |

Confidence thresholds per the docs: **>0.9 act automatically · 0.5–0.9 proceed cautiously or
flag · <0.5 route to a human** — and different actions in the same system get different gates
depending on what being wrong costs. Calibrate on our data; treat cookbook numbers as examples
to beat, not as promises.

---

## 4. The boundary that actually governs this — SYMBIOSIS Law 2 / UU PDP

TypeSafe is a **third-party US cloud endpoint**. The Builder Contract §4 binds it identically to
every other vendor: **no client PII *or OSINT* in cleartext, ever, in any direction**.

An earlier draft of this dossier split the lanes into "PII-free by construction" and
"PII-bearing", and an adversarial pass took that split apart. It was wrong, and the way it was
wrong is worth recording, because it is the mistake anyone designing the next lane will repeat:
**a lane is not clean because its corpus is clean.** Every request carries two halves, and the
second half is almost always user-supplied.

| Lane | corpus / catalog half | user-supplied half | verdict |
|---|---|---|---|
| L2 rerank | KB passages — clean | the **query** | dirty |
| L3 KBLI | code descriptions — clean | the client's free-text business description (may name people, addresses, the company) | dirty |
| L5 citation | KB + our own generated answer — but the answer can restate PII from the question | the claim under check | dirty |
| L7 intel | scraped public sources — **public ≠ PII-free, and §4 names OSINT explicitly** | — | dirty |
| L8 skill suggestion | our skill roster — clean | the **task text** the agent is working on | dirty |
| L1 / L6 WhatsApp | — | the message | dirty |
| L4 passage gate | retrieved passages — clean | the query | dirty |
| L9 intake | — | passports, KTP, deeds | **maximum density** |

So the honest statement is: **every lane needs a redaction pass in code before the request.**
What differs between lanes is not whether redaction is needed but how hard it is — scrubbing a
KBLI business description is a regex over names/addresses/NPWP, scrubbing an intake passport
scan is a different problem with a different answer. The sequencing in §6 is therefore ordered
by *redaction difficulty and blast radius*, not by an imaginary clean/dirty line.

One shared component follows from this: a single `redact_for_external()` in code, used by every
lane, tested once, with the lane-specific rules as parameters. It ships in the first lane's PR.

The paid-per-token authorization Zero gave on 2026-09-20 covers **the spend**; it does not by
itself move the PII boundary, and no lane reaches production traffic without that boundary being
demonstrated — not asserted — for its own input shape.

Note also: the Anthropic paid-endpoint ban does not apply here — TypeSafe is not an Anthropic
route. Jev is an *addition* to the arsenal, never a path back to a per-token Claude key.

---

## 5. Application plan — nine lanes

Each lane names its **consumer** and the **observation that proves it live**, per §2 of the
Builder Contract. Two rules apply to every prove-live below, learned from the adversarial pass:

1. **Agreement is not correctness.** Comparing Jev against the incumbent tells you they differ;
   it does not tell you who is right. Every comparative prove-live needs a third, independent
   label — a human adjudicating a sample blind to which system produced which verdict.
2. **A benchmark is not a deploy.** Winning offline proves the judgment; it does not prove the
   organ is wired in. Cicatrix #2: every lane's prove-live ends at the **live consumer**, with
   an observation taken after deploy, not at the evaluation script.

### L1 · WhatsApp intent classifier — replace 735 lines of trilingual keyword matching
`apps/backend-rag/backend/services/classification/intent_classifier.py` is pattern matching over
IT/EN/ID keyword lists. It is cicatrix **#3 (guard-over-match)** written as a product feature:
it judges substrings, not meaning, and it fails silently on the colloquial register Probe B used.
**Design:** one batched request — `Choice` on intent, `Noul` on needs_human, `Score` on
frustration, `Noul` on onboarding-vs-existing-client. Keep the keyword table as the **fallback
on API failure and as the shadow comparator**, do not delete it on day one.
**Gate:** redact before send. **Consumer:** `whatsapp_chat.py` router.
**Prove-live:** shadow mode over 500 real messages logging both verdicts; then **a human labels
the ~N disagreements blind** (verdicts shown unattributed) — that adjudication, not the diff
count, is the promotion evidence. After promotion, the observation is a routed conversation in
production whose handler was chosen by the Jev verdict, traced end to end.

### L2 · RAG re-ranking — second opinion on, or replacement of, Ze-Rank 2
`apps/backend-rag/backend/core/reranker.py` calls an **external paid API** (`ZERANK_API_KEY`,
`zerank-2`). The documented Jev reranking result on 3,565 court opinions with 40 queries:
**top-1 5% → 18%, top-10 38% → 62%, 1,200 calls for $0.0645**. Our corpus is legal-adjacent
(Perpres, PP, Permenaker) — the closest published evaluation there is.
**Design:** per-candidate `Noul` — *"Could this passage answer the query?"* — 30 candidates
batched. Config flag `reranker_backend: 'cross-encoder' | 'zerank2' | 'jev'` (the config already
has two backends, so adding a third is an enum entry, not an architecture change).
**Gate:** the query carries PII → redact. Corpus side is clean.
**Prove-live:** two observations, and the first alone is not enough. (a) A/B on a frozen
gold set against both incumbents, top-1/top-10 reported — note we do **not** have such a gold
set today, so building it (queries + adjudicated relevant passages) is part of this lane, not a
precondition someone else supplies. (b) After deploy, a production `/search` response whose
trace shows `reranker_backend=jev` and a reordering that the cross-encoder did not produce.

### L3 · KBLI classification — 1,559 codes by beam search
The KBLI corpus has **1,559 five-digit codes**; a `Choice` takes at most 255 options, so this is
the hierarchical cookbook verbatim: section → division → group → five-digit, keeping the best
K=3 paths by geometric-mean edge probability (`product(edges) ** (1/decisions)`). Beam search
scored 4/4 against greedy's 2/4 in the published test. The **separation ratio** (top path vs
nearest rival) is the natural handoff signal to a human consultant.
**Design:** code walks the tree, Jev decides each edge; the `per_skala` / `pma_status` /
`pma_max_asing` fields stay in code — they are rules, and RULED 2026-09-14 (no-Besar ⇒ 0% PMA)
is a deterministic check Jev must never be asked to re-derive.
**Gate:** the client's free-text business description can name people and addresses → redact.
**Consumer:** `kbli-navigator` + `search_kbli` MCP.
**Prove-live:** **there is no usable gold set today and this dossier initially claimed there
was.** `scripts/kbli_gold_remap_table.json` holds 83 entries mapping *2020 codes to 2025 codes*
(with 94 `UNMAPPED` markers) — it is a version-migration table, not a description→code ground
truth, and it cannot score this lane. The lane therefore starts by building one: ~100 real
client business descriptions with the code a Bali Zero consultant actually filed, drawn from
closed cases and de-identified. Accuracy at top-1 and within-beam, plus the separation-ratio
distribution on the misses, is the evidence. Then the deploy observation: a live
`search_kbli` call whose returned code came from the beam walk.

### L4 · RAG passage gate — injection, contradiction, relevance
Between retrieval and generation, score each of the top-12 passages on four questions and route
on thresholds: injection first (security), then contradiction, then relevance. Accepted evidence
and contradicting evidence go into **separate prompt blocks**, so the generator can tell "this
answers you" from "this contradicts your premise". The published run excluded ~2/3 of retrieved
passages and caught an injected forum post at 0.99.
This is the **cicatrix #6 antibody at the data layer**: the generator stops being able to build
on a passage that does not support the claim.
**Gate:** passages are KB (clean), the query is not → redact.
**Prove-live:** a single known-poisoned passage proves nothing — it is the one case the design
was written against. The bench is a **held-out adversarial set built by someone other than the
lane's author** (the natural fit for an external seat under the R1 gate): ≥30 injections in
IT/EN/ID plus ≥30 benign passages that superficially resemble them, scored for both detection
AND false-exclusion rate. A gate that drops good evidence is worse than no gate. Then the deploy
observation: a production answer whose trace shows a passage routed to the
contradicting-evidence block rather than dropped.

### L5 · Citation / claim verification on legal + Visa Oracle output
Two steps: exact string match catches **fabricated** quotes for free; a `Choice` —
`supports` / `contradicts` / `says_nothing` — catches the harder case, *a real quote whose
context does not support the claim built on it*. The published run: 4 accurate at 0.93+, 1
fabrication caught by string match, 1 contradiction, 2 unsupported. Accept ≥0.8, flag the rest.
**This is the highest-value lane for Bali Zero specifically**: a wrong regulatory citation to a
client is a liability event, and it is exactly the failure a generative model produces most
fluently. **Gate:** our generated answer can restate PII from the question → redact.
**Prove-live:** counting flags over 200 past answers measures nothing without knowing which
citations were actually wrong. So: **a human adjudicates a 60-answer sample first**, blind to
Jev's verdict, and that becomes the label set; report precision and recall of the flag against
it, separately for the string-match step and the `Choice` step. Then the deploy observation: a
live answer held back or annotated because the gate fired, visible in the response trace.

### L6 · Guardrail on the public WhatsApp surface
Hazard `Noul`s (jailbreak, harmful request, out-of-scope advice, self-harm signal) plus a
severity `Score`, routed to pass / review / block / escalate. Thresholds are a **product
decision in our config**, not something buried in model weights. One request per message,
batched with L1's questions — same state, so it is nearly free to add.
**Gate:** same redaction as L1. **Consumer:** the same `whatsapp_chat.py` entry point.
**Prove-live:** a red-team set of ≥40 hostile messages (jailbreak, out-of-scope legal/medical
advice, abuse) and ≥100 ordinary client messages, reporting **both** catch rate and the
false-block rate — blocking a real client asking about their KITAS is the expensive failure
here, not missing a jailbreak. Then a production message visibly routed to `review` or `block`
with the hazard score in the log.

### L7 · Intel triage for WR2 / bali-intel-scraper
Score each scraped item once on several dimensions (regulatory relevance, novelty, source
authority, client impact, carousel-worthiness), store the raw scores, and let **code** change
weights and thresholds afterwards without re-running inference. Composite scoring: the judgments
are reusable data, the policy is ours and editable.
**Gate:** *public is not PII-free* — §4 names OSINT explicitly, and scraped items carry named
individuals. Redact before send, and never store raw OSINT with the scores.
**Consumer:** WR2 queue ranking.
**Prove-live:** one day's scrape is a sample of one editor on one day. Take **four weeks of
already-published WR2 picks** as the label (what the editor chose is the ground truth, and it
already exists at no cost), and measure whether the ranking puts those items in the top-K.
Then the deploy observation: a WR2 queue whose order in the control app comes from the stored
scores, and a weight change visibly reordering it **without** a new inference run — that second
half is what proves the judgments were stored as reusable data rather than baked into a ranking.

### L8 · Skill suggestion for the harness itself
The published result on a 182-skill catalog: **wrong skill loads 16.8% → 7.3%, needless loads
9.8% → 4.0%** (2.3× / 2.4× better). This repo carries a comparable skill roster. A single
appended suggestion line after the roster preserves prefix caching; the agent keeps full
judgment and the complete index.
**Gate:** the catalog is ours and clean, but **the other half of the input is the task text** —
which on this repo routinely names clients. Redact, or restrict the lane to sessions whose task
text is already PII-free. Lowest *blast radius* in the list, not lowest gate.
**Consumer:** the SessionStart skill-suggestion hook.
**Prove-live:** replay a set of past sessions where the correct skill is known from what the
session actually loaded and used, and report wrong-load and needless-load rates against the
current no-suggestion baseline. Then: a live session whose transcript shows the suggestion line
and the matching skill invocation.

### L9 · Intake document classification — **design now, ship last**
Document type, completeness, which client file it attaches to. The extraction cascade pattern
applies (cheap extract → Jev per-field verification → escalate only the flagged fields), and the
published cascade sat up-and-left of every single model on the cost/quality frontier.
**Gate:** intake documents are passports, KTP, deeds — **maximum PII density in the whole
system**, and unlike the other lanes the PII is not incidental to the judgment: document *type*
is inferable from layout and headings, but *completeness* and *which client* are not, without
the very fields that must not leave. That tension is the lane's real design problem and it is
unsolved in this dossier. Nothing here ships without redaction, an authorized lane and Zero's
explicit sign-off. **Prove-live is deliberately not specified**: specifying it would imply the
boundary question is settled. Listed for completeness, not for the first wave.

---

## 6. Suggested sequence

Ordered by **blast radius and redaction difficulty**, since every lane needs redaction:

| Wave | Lanes | Why this order |
|---|---|---|
| 1 | L8 | internal surface, no client sees a mistake; shakes out the shared client + redactor |
| 2 | L5 | highest liability protected, and its label set is a 60-answer human pass |
| 3 | L7 | label set already exists (four weeks of published picks) — cheapest real measurement |
| 4 | L3 | must build its label set first (~100 de-identified closed cases) |
| 5 | L2 | must build its gold query set first; touches the live retrieval path |
| 6 | L1 + L6 (one request) | client-facing; needs shadow mode plus blind human adjudication |
| 7 | L4 | needs an adversarial bench authored by someone other than the lane |
| 8 | L9 | blocked on an unsolved boundary question, not on effort |

Waves 1–3 are the ones that can start immediately; 4 and 5 are gated on data collection that is
itself worth doing regardless of Jev, and 6–8 on evidence or a decision that does not exist yet.

One PR per lane, ≤ ~400 net lines, each with its `Bites:` line naming the consumer and the
observation. Two components are shared and both ship inside **wave 1's PR** — not as a
speculative scaffold PR, and not deferred to whichever lane needs them second:

- `backend/core/typesafe_client.py` — persistent httpx client (Golden Rule #10), retry with
  backoff on 429/529, `TYPESAFE_API_KEY` from env, pass-through disable when the key is absent.
  Exactly the shape `reranker.py` already uses for Ze-Rank.
- `redact_for_external()` — one implementation, tested once, lane-specific rules as parameters
  (§4). No lane calls the client without passing through it.

---

## 7. Key provisioning — done 2026-09-20

- `TYPESAFE_API_KEY` written to `~/.nuzantara-secrets.env` (mode 0600; backup
  `~/.nuzantara-secrets.env.bak-pre-typesafe-20260920`, also 0600 per cicatrix #4).
- `~/.zshenv` already sources that file, so the variable is live in every new shell; verified
  with a presence probe (`${VAR:+SET}` → `SET`), never printed.
- Validated against the live endpoint: HTTP 200 from `jev-1.13.0` (Probe A).
- **Not yet set on Fly.** `fly secrets set TYPESAFE_API_KEY=...` belongs to the first lane's
  deploy, not to this dossier — a secret set on a service that does not read it is
  cicatrix #2 (Esiste≠Armato) in its purest form.

---

## Adversarial review — 8. what the pass broke (codex, 3 raised, 3 survived)

Codex reviewed this dossier as a non-author and landed three hits. All three are recorded here
rather than silently patched, because the *class* of each error is more portable than the fix.

**1 — The clean/dirty split in §4 was fiction.** The original draft called five lanes "PII-free
by construction" on the strength of their corpus being clean, and simply did not look at the
other half of the request. A rerank request contains the query. A skill-suggestion request
contains the task. A KBLI request contains whatever the client wrote about their business. The
review also caught that §4 of the Builder Contract names **OSINT** alongside PII, which alone
disqualifies the "public sources, therefore clean" claim made for L7. §4 is now a two-column
table because two columns is what a request actually has.

**2 — L3's prove-live pointed at a file that cannot prove it.** The draft proposed scoring the
KBLI lane against `scripts/kbli_gold_remap_table.json`. That file holds 83 entries mapping 2020
codes to 2025 codes with 94 `UNMAPPED` markers — a version-migration table. The lane needs
description→code ground truth, which does not exist in this repo. This is cicatrix #6 in its
quietest form: the file is real, the path is real, and the *claim about what it contains* was
invented. Verified by reading the file (83 keys, `mapping_type: SPLIT`, `judul_2020`).

**3 — Vendor numbers were drifting into guarantees.** "Batching is a pure win" and "the 0.73 is
right" both promoted a vendor benchmark or a single anecdote into a property. One plausible
confidence value is not calibration evidence, and the 12.2× batching multiplier holds only when
the state dominates the payload — which is true of a 54k-character GDPR article and false of a
WhatsApp message.

The review also observed that comparative prove-lives ("diff the two classifiers") measure
disagreement, not correctness. That is now rule 1 at the head of §5 and it changed six lanes.

**Generator was not grader here, and it paid off.** Had this dossier shipped as first drafted,
the first lane built from it would have sent client business descriptions to a US endpoint under
a heading that said no redaction was needed.
