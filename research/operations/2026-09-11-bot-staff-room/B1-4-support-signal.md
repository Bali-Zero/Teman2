---
title: "B1.4 — the support-signal design note, measured offline"
date: 2026-09-11
adversarial_review: codex
---

# B1.4 — the support-signal design note

Mandate B1 (BLUE), PR B1.4. Contract: `B1-design.md` §4 B1.4 + §2 exception (1);
build spec: `evidence/2026-09/agent-nuzantara-backend-rag-b1-4-support-signal-0956ceb5/B1-4-build-spec.md`.
Harness: `evidence/2026-09/agent-nuzantara-backend-rag-b1-4-support-signal-0956ceb5/support_probe.py`.
Receipts: `evidence/2026-09/agent-nuzantara-backend-rag-b1-4-support-signal-0956ceb5/support_probe_receipts.json`
(written by the Dux's measurement run on the frozen B1.3 manifest — not present from this PR).

## 1. The question, and why the scorer cannot answer it

`calculate_evidence_score` (`reasoning_utils.py:214-699`) answers "how good does this
retrieval LOOK" — source-quality bands (0.7/0.5/0.3/0.15), a semantic-relevance term, and a
`top_source_cosine` penalty (`0 < top_source_cosine < 0.5 and final_score > 0.15 → ×0.7`,
`reasoning_utils.py:661-673`) that multiplies the score down when the top source's raw score
looks weak. None of those inputs read the text the model would actually answer from for the
one fact the question asks. The counterfactual pair that exposes this (B1-design.md §1,
Astra round 1): same query, same source score 0.9, one context WITH the requested capital
amount, one context saying the amount is unspecified — `calculate_evidence_score` returns
**0.8 for both**. The scorer is blind to the one bit that matters: does the retrieved text
state the fact, or not.

**F-B1.1a: no candidate measured below may lean on `top_source_cosine`, or on any other field
of `calculate_evidence_score`'s own inputs, to make its decision** — that would just be the
scorer grading itself. Every candidate in §2 decides from `query` + `context` alone (plus, for
candidate (iv), the existing scorer's own inputs — DELIBERATELY, since (iv) is the control that
demonstrates the blindness, not a fix for it).

The four spec pairs (`all_in_price`, `nib_oss_requirements`, `minimum_paid_up_capital`,
`registration_duration`, each EN/ID query × EN/ID context, B1-design.md §4 B1.3) are this
measurement's population; every pair in the frozen manifest carrying a `pair_id` is measured
(≥8 required, 16 expected).

## 2. Candidates

### (i) Deterministic span check

- **Inputs:** `query` (string), `context` (the case's chunk texts, joined). No manifest label
  field, no network, no repo import beyond the standard library.
- **Method:** requested-fact extraction is part of the method, not a hand-supplied field — a
  fixed set of slot rules run on the QUERY (price → currency amount `IDR|Rp` + digits; minimum
  capital → amount + the word capital/modal; duration → number + time unit
  weeks/days/months/minggu/hari/bulan; requirements → at least two items of a fixed document
  lexicon: deed/akta, NPWP, KBLI, address/alamat, approval/SK/pengesahan). SUPPORTED iff the
  matched slot's pattern is found in the context; NOT_SUPPORTED iff a slot matched the query but
  its pattern is absent from the context; UNKNOWN iff no slot rule matches the query at all.
- **Failure behaviour:** UNKNOWN whenever the query doesn't fit one of the four slots (e.g. a
  paraphrase, or a topic outside price/capital/duration/requirements) — expected to fail on
  paraphrase per the build spec, measured anyway.
- **Consumer:** none in production today — this candidate is the cheapest possible baseline,
  not a proposed wiring; if selected, it would sit at the same point as (ii)/(iii) below
  (upstream of the leg call, §2's shared consumer note applies).
  **it distinguishes at most the exact spec surface it was built to match — no generalisation
  is claimed for the requirements slot's "at least two of five lexicon items" cut, which was a
  design choice, not a measured threshold.**
- **Cost / latency:** none (a handful of regex searches, microseconds).
- **PII posture:** the query and context stay in-process; nothing crosses a process boundary.
  No redaction is applied or needed — nothing is transmitted.
- **Invocation:** pure Python function call, `support_probe.py::decide_i`.
- **Model / rubric identity:** none — deterministic regex, no model.
- **Timeout:** none (bounded regex search).
- **Failure handling:** UNKNOWN is a terminal decision for this candidate, distinct from
  SUPPORTED/NOT_SUPPORTED in every downstream comparison.

### (ii) Local model judge (Ollama, no egress, $0)

- **Inputs:** `query`, `context` (chunk texts joined with `\n`), formatted into the SHARED
  rubric (identical text to (iii)): *"You judge evidence sufficiency. Question: `<q>`. Context:
  `<c>`. Does the context explicitly state the specific fact the question asks for? Reply with
  exactly one word: SUPPORTED, NOT_SUPPORTED or UNKNOWN."*
- **Method:** `POST http://127.0.0.1:11434/api/generate`, model pinned `qwen3.8:27b-mlx`
  (present on this host, verified live: `ollama list` / `GET /api/tags`), body
  `{"model", "prompt", "options": {"temperature": 0, "seed": 42}, "stream": false, "think":
  false}`. `think: false` is attempted first; if the server rejects the field (HTTP 400) the
  harness retries once without it and records which attempt succeeded
  (`sent_think`/`accepted_think` in the receipt).
- **Failure behaviour:** any non-2xx response, connection error, timeout, or a response body
  that fails strict parsing → UNKNOWN. Strict parse: first whitespace-delimited token,
  punctuation stripped, upper-cased, compared against `{SUPPORTED, NOT_SUPPORTED, UNKNOWN}`;
  anything else (empty, a sentence, a different word) → UNKNOWN.
- **Consumer:** would sit inside `wa_package_builder.build_context_package`, called with the
  ALREADY-capped, ALREADY-redacted chunks and the raw `query` (`query` never leaves the
  process for this candidate — it stays on localhost) — upstream of the leg call, so a
  NOT_SUPPORTED/UNKNOWN verdict can gate `evidence_inputs` before `wa_codex_leg`/
  `wa_codex_daemon` ever offers the job to the broker (README K3/B2.1(g)'s mechanism: the
  consumer must sit upstream of the leg call for B2.1(g) to pass under unchanged D8).
- **Cost / latency:** $0 (local inference, no metered API); latency measured per call
  (receipts `latency_s`), sequential — no concurrency, per the build spec.
- **PII posture:** stays on `127.0.0.1` — no egress. The build spec does not require redaction
  for (ii) (unlike (iii), which is bound by the existing WA-adapter DLP contract); this probe
  sends benchmark text only, never client text, in either candidate.
- **Invocation:** `support_probe.py::call_candidate_ii` — single blocking HTTP call via
  `urllib.request`, no third-party HTTP client dependency.
- **Model / rubric identity:** `qwen3.8:27b-mlx`, `temperature=0, seed=42`, shared rubric text
  above (identical to (iii)).
- **Timeout:** 120 s.
- **Failure handling:** UNKNOWN on any transport/parse failure; never retried beyond the single
  `think`-field fallback described above.

### (iii) Codex seat via the unchanged `CodexExecClient` adapter

- **Inputs:** the REDACTED query and the capped REDACTED context — built by running the SAME
  chunk cap the package builder applies (`wa_package_builder.py`'s `_cap_chunks`, constants
  `_MAX_CHUNKS = 8`, `_MAX_CHUNK_CHARS = 4000`, `wa_package_builder.py:61-62`) and then the SAME
  `wa_dlp.redact_package_fields(history, chunks, search_query)` call site the builder uses at
  its own DLP gate (`wa_package_builder.py:585`), with `history=[{"role": "user", "content":
  query}]` and `search_query=None` (this probe has no separate pricing-block echo to thread
  through). The raw query and the DLP reversal map are never sent to the seat — only
  `dlp_result.history[0]["content"]` and the joined `dlp_result.chunks[i]["text"]`.
- **Method:** `await CodexExecClient(model=<pinned>).generate(prompt, model=<pinned>,
  timeout_s=90)`, imported from the repo (`PYTHONPATH=apps/backend-rag`), never a hand-typed
  `codex exec` line — the adapter supplies its own fixed argv prefix (`exec --sandbox read-only
  --skip-git-repo-check --ephemeral --ignore-user-config --ignore-rules -m <model> -`), a fresh
  empty `tempfile.mkdtemp()` cwd, a minimal child env (`_build_env`), and stdin-only prompt
  transport. Model pinned to the WA leg's production model: **`MODEL_TERRA` =
  `"gpt-5.6-terra"`** — the WA leg module itself (`wa_codex_leg.py`) does not call
  `CodexExecClient` directly (it only offers/awaits/consumes a job through `wa_broker.py`'s
  DB-mediated queue); the actual construction site is `wa_codex_daemon.py:159`
  (`model = (os.environ.get("WA_CODEX_MODEL") or MODEL_TERRA).strip()`) and `:230-232`
  (`CodexExecClient(..., model=config.model)`) — this is the module the spec's "if unclear,
  `MODEL_TERRA`" fallback names, confirmed exactly rather than assumed.
- **Failure behaviour:** UNAVAILABLE — never a looser invocation — on any of: the adapter
  module fails to import; `_cap_chunks`/`redact_package_fields` raises (e.g. `DlpOverflow`);
  `CodexExecClient(...)` construction raises (bad model/timeout); `client.available` is
  `False` (binary or `auth.json` missing); or `generate()` raises any of its typed exceptions
  (`CodexExecUnavailableError`, `CodexExecAuthError`, `CodexExecQuotaError`,
  `CodexExecProcessError`, `CodexExecOutputShapeError`, `CodexExecTimeoutError`,
  `CodexExecCommunicationError`). UNAVAILABLE is a fourth, distinct decision value, never
  folded into SUPPORTED/NOT_SUPPORTED/UNKNOWN.
- **Consumer:** same shared position as (ii) — inside `wa_package_builder.build_context_package`,
  upstream of the leg call, so its verdict is available before `wa_codex_leg`/
  `wa_codex_daemon` offers the job to the broker (README K3/B2.1(g)).
- **Cost / latency:** flat subscription (ChatGPT Pro, the same seat the WA leg's daemon already
  uses) — never a per-token key. Latency measured per call via both the harness's own wall
  clock and the adapter's own `CodexExecResult.latency_ms`.
- **PII posture:** redacted query + redacted, capped context only (see Inputs); the reversal
  map never leaves the process that built it. This probe's own text is synthetic/benchmark
  only — no client text crosses this boundary in this PR.
- **Invocation:** `support_probe.py::call_candidate_iii`, at most 4 concurrent calls
  (`asyncio.Semaphore(4)`), per the build spec.
- **Model / rubric identity:** `gpt-5.6-terra`, shared rubric text (identical to (ii));
  temperature/seed are not exposed by `codex exec` — "not controllable" is recorded instead,
  and the adapter file's sha256 is pinned in the receipts as the version identity.
- **Timeout:** 90 s (per-call `timeout_s`), independent of the adapter's own default (60 s)
  and independent of the local Ollama timeout (120 s).
- **Failure handling:** any adapter exception is caught and turned into UNAVAILABLE with the
  exception's type name recorded in `outcome` — the raw stdout/stderr the adapter itself
  never exposes (by the adapter's own contract, point 6) is never re-derived here either.

### (iv) Control — no support signal, the scorer as it exists today

- **Inputs:** `provenance_fixture.sources` (list of `{score, score_kind, score_raw}`),
  `context` (chunk texts), `query` — the SAME three decision-time inputs every other candidate
  gets, deliberately, so the control is measured on equal footing.
- **Method:** `score = calculate_evidence_score(sources, context_gathered=context,
  query=query)`; `policy = build_abstain_policy(query)`; decision = NOT_SUPPORTED if
  `policy.label_abstains(score)` else SUPPORTED. This is exactly the label gate the package
  builder already computes (`wa_package_builder.py:602-614`) — no new code path.
- **Failure behaviour:** none observed in this method's own control flow (both functions are
  pure and total over the manifest's inputs); an exception here is recorded as UNKNOWN with
  the exception type, defensively, though none is expected.
- **Consumer:** this candidate has no separate consumer — it names the EXISTING one:
  `wa_package_builder.build_context_package` → `evidence_inputs["evidence_score"]` /
  `abstain` flag → `wa_finalize.py`'s delivery decision. It is already upstream of the leg
  call today; the point of measuring it is to show that "upstream" alone doesn't help when the
  signal itself can't see the fact.
- **Cost / latency:** none (already-computed formula, no I/O).
- **PII posture:** unchanged from production today — out of scope for this candidate (it is
  not a new call site).
- **Invocation:** `support_probe.py::decide_iv`.
- **Model / rubric identity:** none — a scoring formula, not a model.
- **Timeout:** none.
- **Failure handling:** N/A (defensive UNKNOWN only, not expected to trigger).
- **Expected result:** FAIL — the 0.8/0.8 pair in §1 is this candidate's own worked example;
  it is measured and recorded regardless, never excluded (build spec, Candidates section).

## 3. Measurement table and summary

Two sets were measured, and they disagree with each other. That disagreement is
the finding of this window, so both ship.

**Set A — the frozen mandatory manifest** (`manifest_mandatory.json`, sha256
`9d7ea833b52bdcb9cf4fcc09c7e608f7edcc8bf2d50c5df86c4fd9849142e48f` at
measurement time, merged in #6274; re-pinned to
`240842d97a34c9f1b4230b1b8bb441844eb3f441bb762d6c1ce2052d65211bb7` by the
provenance-fixture PR — RULED I30/I31 — which is the one sanctioned exception
to the freeze and touches only case `bs-17806bb4`'s `provenance_fixture`):
16 counterfactual pairs carrying a `pair_id` with exactly one
`sufficient` and one `relevant_insufficient` member. 16 x 2 x 3 reps x 4
candidates = 384 calls, every outcome `ok`, no `UNAVAILABLE`.

**Set B — the distractor probe** (`fair_pairs_probe.json`, sha256
`9d41ef142374408fe644001382882e40b05e73df08a3ee92c8a3fd0fb02401d0`, in this
evidence directory and deliberately NOT in the frozen manifest): 4 pairs whose
*insufficient* member KEEPS the entity the query asks about and still fails to
answer it — an amount that is the government fee and not the all-in price, a
duration that is the notary's and not the total, a capital figure that is what
investors typically inject and not the legal minimum, a requirements list under
a negation. Constructed from the second reader's own text after it ruled Set A
trivial (§Adversarial review), so the author of the hard cases is not the
author of any method. Provenance is held identical between the two members of
every pair (`score` 0.72), so the only thing that varies is the wording. 4 x 2
x 3 x 4 = 96 calls, every outcome `ok`.

| Candidate | Set A (16 pairs) | A unstable | Set B (4 pairs) | B unstable | median latency A / B | cost |
|---|---|---|---|---|---|---|
| (i) deterministic span check | **16/16** | 0 | **0/4** | 0 | 0.00 s / 0.00 s | none |
| (ii) local Ollama judge `qwen3.8:27b-mlx` | 13/16 | 0 | **4/4** | 0 | 0.8 s / 0.4 s | $0, local |
| (iii) Codex via the unchanged adapter | 15/16 | **1** | **4/4** | 0 | 9.7 s / 9.3 s | flat subscription |
| (iv) control — the scorer as it exists today | **0/16** | 0 | **0/4** | 0 | 0.00 s / 0.00 s | none |

Run on Mini (`mini-pro2`), receipts in this directory
(`support_probe_receipts.json`, `fair_pairs_receipts.json`) pinning host, UTC
window, manifest sha256, the adapter file's sha256, `codex-cli 0.154.0`, the
resolved `CODEX_HOME` basename `.codex-acct2` and the Ollama model digest
`5642e97495e1...`. The judge of each candidate is never the family that
generated it.

**How each candidate fails, in its own words rather than as a score.**

- **(i)** scores `SUPPORTED` on BOTH members of all four Set-B pairs. Its slot
  regexes find `IDR 2,000,000`, `3 sampai 4 hari`, `IDR 10,000,000,000` + the
  word `capital`, and two lexicon tokens — every one of them present and every
  one of them answering a different question than the one asked. Its 16/16 on
  Set A therefore measures *entity presence*, not sufficiency.
- **(ii)** loses its three Set-A pairs to FALSE NEGATIVES — it answers
  `NOT_SUPPORTED` on the *sufficient* member too (`bp-553489d2`,
  `bp-d1f1a58b`, `bp-df57e569`). A conservative error, and the same caution
  wins it every Set-B pair.
- **(iii)** loses its one Set-A pair (`bp-3eed944f`) to INSTABILITY, not to a
  wrong answer: the same sufficient member came back `SUPPORTED` in some
  repetitions and `NOT_SUPPORTED` in others. `codex exec` exposes no
  temperature or seed, so three repetitions is the entire defence.
- **(iv)** answers `SUPPORTED` on all 40 members of both sets. It distinguishes
  nothing, anywhere — Astra's 0.8 / 0.8 finding reproduced 20 times over.

**Set A and Set B rank the candidates in opposite order.** A benchmark whose
negative member is built by DELETING the trigger token rewards pattern matching
and punishes caution; a benchmark whose negative member keeps the entity does
the reverse. That is a finding about the frozen benchmark's fitness for
*selecting* a support signal, not only about these four candidates.

Stated at the strength the measurement actually carries, after the fourth
council seat (`tp1-qwen3.8-max`) called the earlier wording overclaimed: Set A
is unfit as the **sole selector** of a support signal — it is not unfit for
every purpose, and it remains the frozen regression set B2.1 inherits. The
symmetric statement holds for Set B, which §5 already concedes is a probe and
not a benchmark: Set A rewards entity-presence matching, Set B rewards
disclaimer reading, and **neither measures silent insufficiency**. Both seats
that read this note independently — `kimi-code/k3` and `tp1-qwen3.8-max` —
reached that conclusion, which is why Set C is a precondition of B2.1 rather
than a suggestion.

## 4. Recommendation

The staff room fixed the decision rule BEFORE these numbers existed (ruling
I25): a candidate qualifies only if it distinguishes at least 3 of the 4 Set-B
pairs with zero unstable AND keeps at least 15/16 on Set A.

- (i) fails the Set-B leg outright (0/4).
- (ii) passes Set B 4/4 but scores 13/16 on Set A — fails the Set-A leg.
- (iv) fails both.
- **(iii) passes both legs** — 4/4 on Set B with zero unstable, 15/16 on Set A.

**The counting rule, as the harness actually applies it** — written out because
the fourth council seat found I25's wording ambiguous about whether "zero
unstable" binds Set A as well as Set B. Read from `support_probe.py:845-891`,
not from the ruling's prose: a pair counts as *distinguished* only when BOTH
members are unanimous across the three repetitions AND the sufficient member
came back `SUPPORTED` while the insufficient one came back `NOT_SUPPORTED`.
There is no majority vote anywhere in the scorer. Three consequences, none of
them a matter of interpretation: instability costs the pair in **both** sets,
so I25's "zero unstable" clause on Set B is redundant rather than a second
standard; (iii)'s 15/16 on Set A is 15 distinguished out of 16 with the
sixteenth lost to instability, already counted as a loss; and any decision that
is neither `SUPPORTED` nor `NOT_SUPPORTED` — `UNKNOWN`, or an `UNAVAILABLE`
outcome — fails the pair by construction, which is fail-closed. Ruling I26's
shipped mitigation (majority-of-3) is a *different* rule from the one that
produced this table, and §5 records that the shipped configuration would turn
(iii)'s unstable pair into a pass. The table is not restated under it: the
numbers here are the numbers the pre-registered rule produced.

**(iii) is the only qualifying candidate, and it is recommended with its
instability written beside it, not under it.** Its single Set-A loss is a split
vote across repetitions on a decoding path that offers no seed control. A
method that answers differently to the same input twice is a real hazard for a
gate, and the mitigation has to be part of the design rather than a hope.

**CHOSEN by the staff room, ruling I26 (2026-09-12): candidate (iii)**, the
Codex seat reached ONLY through the unchanged `CodexExecClient.generate`
adapter, with three binding conditions for B2.1:

1. **Determinism defence (K6).** The B2.1 consumer takes the MAJORITY of three
   repetitions and treats a split vote as `NOT_SUPPORTED` — fail-closed — and
   records the per-repetition votes.
2. **Fallback.** (ii), the local Ollama judge, is the recorded runner-up and
   the designated fallback when the Codex seat is unavailable: pinned seed, a
   conservative error profile, 4/4 on Set B.
3. **The benchmark.** Distractor pairs become MANDATORY in B2.1's supplement
   (`manifest_supplement_b2.json`). The B1.3 mandatory manifest stays frozen as
   merged; this probe is evidence, never a relabelling of it.

## 5. Residuals

- (i)'s slot lexicon is hand-built for four topics and now measured to collapse
  on distractors; it is not a general sufficiency method and is not a cheap
  first filter either, because its errors are false POSITIVES — the direction
  an abstain gate can least afford.
- (iii)'s decoding is not controllable (`codex exec` exposes no
  temperature/seed). Majority-of-three with fail-closed splits is the mitigation
  and it is a mitigation, not a guarantee: a systematically biased seat would be
  stably wrong, and stability is all this mechanism can see.
- Neither LLM judge has been checked for acquiescence bias independent of the
  fact. The pair design controls for it partially (same query, same provenance,
  only the fact-bearing sentence differs, and now also a distractor variant);
  a dedicated calibration pass remains out of scope.
- **Set B tests "the entity is present AND the text says so" — not sufficiency
  reasoning in general** (Kimi K3, council). Every insufficient member of the
  four pairs ANNOUNCES its own insufficiency: "is not stated here", "tidak
  disebutkan di sini", "is not detailed in this summary", "diberikan kemudian".
  A judge can therefore pass Set B by spotting an explicit non-answer cue
  without ever checking whether the requested fact is present. That is the
  MIRROR of Set A's flaw, not its cure: Set A's negatives lack the token, Set
  B's negatives carry a disclaimer, and the genuinely hard case — the entity
  present, the referent wrong, and NO meta-commentary — is measured by neither.
  A Set C is owed in B2.1's supplement: (a) insufficient members stating a
  neighbouring fact confidently, with no disclaimer; (b) sufficient members
  where the fact is stated indirectly or hedged; (c) contradiction cases. The
  4/4 of (ii) and (iii) is therefore evidence that they are not fooled by a
  distractor, and NOT evidence that they reason about sufficiency.
- **The headline table is not the shipped configuration** (Kimi K3). Ruling
  I26's mitigation — majority of three, split vote = NOT_SUPPORTED — would turn
  (iii)'s one unstable Set-A pair into a PASS, while (ii)'s three Set-A errors
  are deterministic false negatives that no vote can repair. Measured under the
  shipped rule the gap between them is WIDER than the table shows, not
  narrower. The table reports the raw unanimity rule the harness applied, which
  is the stricter one; both are stated so nobody has to guess which produced
  which number.
- **Who wrote the hard cases also reads the verdicts** (Kimi K3, lower
  severity): Gemini supplied Set B's constructions and is also the seat that
  judges candidate (iii), since Codex may not judge its own family. The
  mitigation is that Set B is executed mechanically by the harness and scored
  by code, not by Gemini — no subjective grading step exists — but the overlap
  is recorded rather than left for a reader to notice.
- Four distractor pairs is a probe, not a benchmark. It is enough to falsify
  (i) and to separate the judges; it is not enough to estimate a rate. B2.1's
  supplement is where a real negative set gets built.
- (iv)'s expected FAIL is recorded, not excluded, per the build spec. It means
  the scorer cannot see requested-fact support — not that the scorer is wrong
  about everything.
- The consumer position for (iii) (upstream of the leg call, README K3 /
  B2.1(g)) is a DESIGN target for B2. This PR ships no production call, adds no
  caller, and makes no paid call: (ii) is local and (iii) runs on the flat
  subscription through the adapter.

## Adversarial review

**Second reader — Gemini 3.1 Pro** (`agy --model gemini-3.1-pro --effort high`,
2026-09-12): read §2's definition of (i) together with all 16 Set-A pairs and
returned **TRIVIAL** — the insufficient member of every pair is built by
removing exactly the token class (i)'s regex hunts for, so a perfect score
proves only that the regex can spot an amount or a duration. It supplied the
distractor constructions that became Set B. Its verdict was ACCEPTED by the Dux
and by the staff room: ruling I24b, which had provisionally chosen (i), was
SUSPENDED by its own condition before any choice was recorded, and Set B was
measured before a method was named. The seat that broke the result is the seat
whose text built the test that replaced it.

**Adversarial reviewer — Codex `gpt-5.6-sol`** (read-only sandbox, Mini,
`CODEX_HOME=~/.codex-acct2`): candidate (iii) is Codex's own family, so Codex
does not judge (iii); Gemini does. The generator of a candidate is never its
grader, in either direction.

**Harness provenance.** `support_probe.py` was drafted by a child of the
previous window that was stopped after six hours without a report; the mandate
required treating all of it as UNVERIFIED. The Dux verified it line by line
before running it, and the property that matters was confirmed by reading:
at decision time every candidate receives only `query`, `context` and
`provenance_fixture.sources` — `stratum`, `expected_*`, `supporting_span`,
`requested_fact` and `case_id` are read only in the post-hoc scoring pass, so
the selection contract's no-label-leakage rule holds by construction rather
than by promise.

**Third seat — Kimi K3** (`kimi -m kimi-code/k3`, read-only, 2026-09-12): built
none of this and judges none of its own work. It verified the no-label-leakage
property independently from the harness source, confirmed the latencies, the
"no UNAVAILABLE" claim, the hosts and the UTC windows against the receipts, and
accepted "Set A is unfit on its own" as following from the construction reading
plus (i)'s 16/16 rather than from four pairs alone. Its two substantive
findings are ACCEPTED and are in §5: Set B measures "entity present plus an
explicit disclaimer" rather than sufficiency, so a Set C is owed; and the
shipped majority-of-3 rule would widen (iii)'s margin over (ii) rather than
narrow it, so the table's raw numbers and the shipped rule are now distinguished
in the text. It also raised a family-conflict concern premised on the Dux being
a Codex-family session: that premise is wrong — this Dux is Claude Opus 5, and
the recommendation of a Codex-family seat therefore favours no family of its
own. The half of the finding that does survive (the Set B author also reads
(iii)'s verdicts) is recorded in §5. One receipt gap it found and the Dux
confirms: `decide_iv` computes an evidence score but the call record does not
store it, so the receipts carry (iv)'s DECISIONS and not its scores — every
claim in §3 about (iv) rests on the decisions, and no numeric 0.8/0.8 claim is
made from these receipts.

**Fourth seat — TP1 `qwen3.8-max`** (`scripts/tp1_call.py --effort high`,
2026-09-12T08:30Z, dispatched by the successor window on the same docket the
other seats received): **REWORK**, seven items. Two of them changed this note:
§3's conclusion now says Set A is unfit as the SOLE selector rather than unfit
outright, and §4 now writes out the counting rule as the harness applies it —
instability costs the pair in both sets, there is no majority vote in the
scorer, and any decision that is neither `SUPPORTED` nor `NOT_SUPPORTED` fails
the pair fail-closed. Its Set C demand is the same one Kimi raised
independently, which is why that dissent entry is CONFIRMED rather than open.
Its remaining item — that the measurement table is "asserted rather than
independently verified in this review" — is a true statement about what that
seat was given (the note, not the receipt files) and NOT a defect of the PR:
the receipts ship here, and the successor window re-read them at 08:34:35Z (384
and 96 call records, every outcome `ok`, the Set B summary marking (ii) and
(iii) as qualifying), recording those reads as receipts in `pack.yml`. A seat
that says what it could not check is doing its job, not failing it.

