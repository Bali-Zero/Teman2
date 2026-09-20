---
date: 2026-09-20
domain: operations
client_case: none
adversarial_review: none
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
probe used a synthetic request or public KBLI corpus text.

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

### Batching is a pure win, not a tradeoff

Questions in one request are scored independently against the same state — an answer does not
shift because of what else was asked. The documented GDPR test (13 questions, ~54k-char article)
measured **12.2× cheaper and 10.0× faster** than 13 separate calls, with standard deviation 0.0
on the answers. The saving is structural: the document is transmitted once instead of thirteen
times. Every lane below should batch, and should include speculative questions whose answers
code may discard.

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
0.77, **56301** (Bar) at 0.15, confidence 0.73. 662 input tokens. The answer is right AND the
0.73 is right: a beach club genuinely straddles restaurant and bar, and the confidence says so
instead of hiding it.

Probe C is the shape of the whole dossier: the useful output is not just the label, it is the
**distribution that tells code when to stop trusting the label**.

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
every other vendor: **no client PII in cleartext, ever, in any direction**. This is what
separates the lanes below into two classes, and it is not negotiable by convenience:

- **PII-free by construction** — L2, L3, L5, L7, L8. The state is corpus text, a KBLI
  description, a generated answer, public intel, or our own skill catalog. Ship these first.
- **PII-bearing at source** — L1, L4, L6, L9. WhatsApp messages and intake documents carry
  names, passport numbers, addresses. These require a **redaction pass in code before the
  request** (client_id substitution, regex scrub of passport/NIK/phone/email) and, even then,
  Zero's explicit authorization before the first production call. The paid-per-token
  authorization Zero gave today covers the spend; it does not by itself move the PII boundary.

Note also: the Anthropic paid-endpoint ban does not apply here — TypeSafe is not an Anthropic
route. Jev is an *addition* to the arsenal, never a path back to a per-token Claude key.

---

## 5. Application plan — nine lanes, ordered by (value ÷ risk)

Each lane names its **consumer** and the **observation that proves it live**, per §2 of the
Builder Contract.

### L1 · WhatsApp intent classifier — replace 735 lines of trilingual keyword matching
`apps/backend-rag/backend/services/classification/intent_classifier.py` is pattern matching over
IT/EN/ID keyword lists. It is cicatrix **#3 (guard-over-match)** written as a product feature:
it judges substrings, not meaning, and it fails silently on the colloquial register Probe B used.
**Design:** one batched request — `Choice` on intent, `Noul` on needs_human, `Score` on
frustration, `Noul` on onboarding-vs-existing-client. Keep the keyword table as the **fallback
on API failure and as the shadow comparator**, do not delete it on day one.
**Gate:** PII — redact before send. **Consumer:** `whatsapp_chat.py` router.
**Prove-live:** shadow mode for 500 real messages, log both verdicts, diff them; promote only on
measured disagreement-where-Jev-is-right.

### L2 · RAG re-ranking — second opinion on, or replacement of, Ze-Rank 2
`apps/backend-rag/backend/core/reranker.py` calls an **external paid API** (`ZERANK_API_KEY`,
`zerank-2`). The documented Jev reranking result on 3,565 court opinions with 40 queries:
**top-1 5% → 18%, top-10 38% → 62%, 1,200 calls for $0.0645**. Our corpus is legal-adjacent
(Perpres, PP, Permenaker) — the closest published evaluation there is.
**Design:** per-candidate `Noul` — *"Could this passage answer the query?"* — 30 candidates
batched. Config flag `reranker_backend: 'cross-encoder' | 'zerank2' | 'jev'` (the config already
has two backends, so adding a third is an enum entry, not an architecture change).
**Gate:** query text may carry PII → redact. Corpus side is clean.
**Prove-live:** A/B on a frozen 40-query gold set against both incumbents; report top-1/top-10.

### L3 · KBLI classification — 1,559 codes by beam search
The KBLI corpus has **1,559 five-digit codes**; a `Choice` takes at most 255 options, so this is
the hierarchical cookbook verbatim: section → division → group → five-digit, keeping the best
K=3 paths by geometric-mean edge probability (`product(edges) ** (1/decisions)`). Beam search
scored 4/4 against greedy's 2/4 in the published test. The **separation ratio** (top path vs
nearest rival) is the natural handoff signal to a human consultant.
**Design:** code walks the tree, Jev decides each edge; the `per_skala` / `pma_status` /
`pma_max_asing` fields stay in code — they are rules, and RULED 2026-09-14 (no-Besar ⇒ 0% PMA)
is a deterministic check Jev must never be asked to re-derive.
**Gate:** PII-free (business description only). **Consumer:** `kbli-navigator` + `search_kbli` MCP.
**Prove-live:** run the 1,559-code tree against the existing gold remap table
(`scripts/kbli_gold_remap_table.json`) and publish the confusion set.

### L4 · RAG passage gate — injection, contradiction, relevance
Between retrieval and generation, score each of the top-12 passages on four questions and route
on thresholds: injection first (security), then contradiction, then relevance. Accepted evidence
and contradicting evidence go into **separate prompt blocks**, so the generator can tell "this
answers you" from "this contradicts your premise". The published run excluded ~2/3 of retrieved
passages and caught an injected forum post at 0.99.
This is the **cicatrix #6 antibody at the data layer**: the generator stops being able to build
on a passage that does not support the claim.
**Gate:** passages are KB (clean), the query may not be. **Prove-live:** inject a known
poisoned passage into a staging index and observe it scored >0.9 and excluded.

### L5 · Citation / claim verification on legal + Visa Oracle output
Two steps: exact string match catches **fabricated** quotes for free; a `Choice` —
`supports` / `contradicts` / `says_nothing` — catches the harder case, *a real quote whose
context does not support the claim built on it*. The published run: 4 accurate at 0.93+, 1
fabrication caught by string match, 1 contradiction, 2 unsupported. Accept ≥0.8, flag the rest.
**This is the highest-value lane for Bali Zero specifically**: a wrong regulatory citation to a
client is a liability event, and it is exactly the failure a generative model produces most
fluently. **Gate:** PII-free (our answer + our KB).
**Prove-live:** run it over the last 200 Visa Oracle / `ask_legal` answers and count.

### L6 · Guardrail on the public WhatsApp surface
Hazard `Noul`s (jailbreak, harmful request, out-of-scope advice, self-harm signal) plus a
severity `Score`, routed to pass / review / block / escalate. Thresholds are a **product
decision in our config**, not something buried in model weights. One request per message,
batched with L1's questions — same state, so it is nearly free to add.
**Gate:** PII — same redaction as L1.

### L7 · Intel triage for WR2 / bali-intel-scraper
Score each scraped item once on several dimensions (regulatory relevance, novelty, source
authority, client impact, carousel-worthiness), store the raw scores, and let **code** change
weights and thresholds afterwards without re-running inference. Composite scoring: the judgments
are reusable data, the policy is ours and editable.
**Gate:** PII-free (public sources). **Consumer:** WR2 queue ranking.
**Prove-live:** rank one real day's scrape, compare to the human editorial pick.

### L8 · Skill suggestion for the harness itself
The published result on a 182-skill catalog: **wrong skill loads 16.8% → 7.3%, needless loads
9.8% → 4.0%** (2.3× / 2.4× better). This repo carries a comparable skill roster. A single
appended suggestion line after the roster preserves prefix caching; the agent keeps full
judgment and the complete index.
**Gate:** PII-free (our own catalog). Lowest risk lane in the list — good place to start if a
shakedown run is wanted before touching a client-facing surface.

### L9 · Intake document classification — **design now, ship last**
Document type, completeness, which client file it attaches to. The extraction cascade pattern
applies (cheap extract → Jev per-field verification → escalate only the flagged fields), and the
published cascade sat up-and-left of every single model on the cost/quality frontier.
**Gate:** intake documents are passports, KTP, deeds — **maximum PII density in the whole
system**. Nothing here ships without redaction, an authorized lane and Zero's explicit sign-off.
Listed for completeness, not for the first wave.

---

## 6. Suggested sequence

| Wave | Lanes | Why this order |
|---|---|---|
| 1 | L8, L5 | PII-free, self-contained, and L5 protects the highest-liability surface |
| 2 | L3, L7 | PII-free, measurable against existing gold data |
| 3 | L2 | measurable against two incumbent rerankers; query redaction required |
| 4 | L1 + L6 (one request) | needs redaction + shadow-mode evidence before promotion |
| 5 | L4 | needs an adversarial test bench first |
| 6 | L9 | needs an authorized-lane decision from Zero |

One PR per lane, ≤ ~400 net lines, each with its `Bites:` line naming the consumer and the
observation. Shared across all of them: a thin `backend/core/typesafe_client.py` (persistent
httpx client per Golden Rule #10, retry with backoff on 429/529, `TYPESAFE_API_KEY` from env,
pass-through disable when the key is absent — exactly the shape `reranker.py` already uses for
Ze-Rank), which ships in the first lane's PR rather than as a speculative scaffold PR.

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
