# B2.1 — build spec (Dux B2, BLUE, base 50a3d4f762)

Authoritative for the implementer lanes. Every line number below MUST be re-grepped on this
base before it is built on; where this spec and the disk disagree, the disk wins and the
implementer says so.

## 0. The measurement that shapes the design (run by the Dux on this base, 09:25Z)

`harness.py` on the frozen manifest: 26 of 38 negatives ACCEPTED (EN>EN 5/9, EN>ID 8/10,
ID>EN 7/11, ID>ID 6/8), 1 false abstention (EN>ID), **0/16 spec pairs distinguished**.

The manifest's own provenance, measured the same turn:

| kind                   | n sources | scores present | strata                                                                                               |
| ---------------------- | --------- | -------------- | ---------------------------------------------------------------------------------------------------- |
| `hybrid_rrf_formatted` | 44        | 0.6667, 1.0    | 16 sufficient · 16 relevant_insufficient · 4 irrelevant · 4 generic_overlap · 4 company_prefix_chunk |
| `unknown`              | 14        | 0.18, 0.72     | 4 sufficient · 5 relevant_insufficient · 4 irrelevant · 1 generic_overlap                            |

**All 32 pair cases carry `hybrid_rrf_formatted` at score 1.0 on BOTH members.** Provenance
therefore CANNOT separate a counterfactual pair, by construction — that is the point. The
inversion makes relevance language-blind; the SUPPORT SIGNAL is what decides sufficiency.

## 1. New module — `backend/services/rag/agentic/_support_signal.py`

Pure, importable, no import-time I/O, no import-time seat probe.

```
class SupportVerdict(StrEnum): SUPPORTED / NOT_SUPPORTED / UNKNOWN / UNAVAILABLE
@dataclass(frozen=True) class SupportDecision:
    verdict: SupportVerdict
    votes: tuple[SupportVerdict, ...]   # per repetition — ruling I26 condition 1 requires them recorded
    judge: str                          # "codex:gpt-5.6-terra" | "ollama:qwen3.8:27b-mlx" | "absent"
    fallback_used: bool                 # the switch to (ii) is RECORDED, never silent
    latency_s: float
    detail: str                         # exception TYPE NAME only on UNAVAILABLE; never raw stdout/stderr
```

**RUBRIC** — byte-identical to B1.4's shared rubric, one module-level constant, used by BOTH
judges so the fallback is not a different question:

> `You judge evidence sufficiency. Question: {q}. Context: {c}. Does the context explicitly state the specific fact the question asks for? Reply with exactly one word: SUPPORTED, NOT_SUPPORTED or UNKNOWN.`

**Strict parse** (shared): first whitespace-delimited token of the reply, punctuation stripped,
upper-cased, compared against the three names; anything else → `UNKNOWN`.

**`majority(votes)`** — ruling I26 condition 1. `_REPETITIONS = 3`. A verdict wins only with a
STRICT majority (>= 2 of 3) of identical values. No strict majority → `NOT_SUPPORTED`
(fail-closed). `UNKNOWN` and `UNAVAILABLE` can never combine into a majority for `SUPPORTED`.
Write the truth table as a test, not as a comment.

**`CodexSupportJudge`** — async. `CodexExecClient` imported from its real module (re-grep it);
model pinned to the WA leg's production model (`MODEL_TERRA`, `gpt-5.6-terra`, as
`wa_codex_daemon` constructs it), `timeout_s=90`, three repetitions at `asyncio.Semaphore(4)`.
The adapter is UNCHANGED — never a hand-typed `codex exec` line, never a paid per-token
endpoint. Every typed adapter exception (`CodexExecUnavailableError`, `…AuthError`,
`…QuotaError`, `…ProcessError`, `…OutputShapeError`, `…TimeoutError`,
`…CommunicationError`) → that repetition votes `UNAVAILABLE` with the exception's type name.

**`OllamaSupportJudge`** — the RECORDED runner-up and the designated fallback (I26 condition 2).
`POST http://127.0.0.1:11434/api/generate`, model `qwen3.8:27b-mlx` (verified present on Pro
this turn), `{"options": {"temperature": 0, "seed": 42}, "stream": false, "think": false}`,
retry ONCE without `think` on HTTP 400 and record which attempt succeeded, timeout 120 s,
`urllib.request` only (no new dependency). Any transport/parse failure → `UNKNOWN`.

**`evaluate_support(query, context, *, judge=None) -> SupportDecision`** — async. Resolves the
judge once: Codex when its adapter reports `available`, else Ollama with `fallback_used=True`.
If the Codex judge returns `UNAVAILABLE` on a majority of its repetitions, retry ONCE on the
Ollama judge and set `fallback_used=True`. If both are unavailable the verdict is
`UNAVAILABLE` — which the scorer treats as fail-closed.

**Residual to write into `pack.yml`, not to engineer around:** fail-closed on `UNAVAILABLE`
means a dead Codex seat AND a dead local Ollama mutes the bot into blanket abstention. Name it
as a residual risk and add a PENDING-ARMS row for a seat-liveness receptor; do NOT soften the
gate to avoid it.

## 2. The inversion — `reasoning_utils.py::calculate_evidence_score`

Signature becomes `(sources, context_gathered, query, *, support: SupportVerdict | None = None)`.
It stays **synchronous and pure**; the verdict is an INPUT. The production consumer always
supplies one; legacy call sites that do not are unchanged by construction.

Order of operations:

1. `declared = [s for s in sources if score_provenance.kind_of(s) in RETRIEVED_KINDS]`
   (`hybrid_rrf_formatted`, `dense_formatted`, `reranked`).
2. **If `declared` is non-empty — provenance is PRIMARY.** Compute a band per kind from
   `score_provenance`'s MEASURED ranges, never from the magnitude alone:
   - `hybrid_rrf_formatted` ∈ [0.508, 1.000]; 0.5 means "last of a long list", NOT "half
     similar". Normalise `(score - 0.5) / 0.5` and band the result.
   - `dense_formatted`: prefer `score_raw` (the cosine); when absent recover it exactly —
     the formatter is `1/(1 + (1 - raw))`, so `raw = 2 - 1/score`. Band the cosine.
   - `reranked`: its own band. The reranker's scale is NOT measured anywhere in this repo —
     use a conservative band and record that as a declared residual in `pack.yml`.
     Band values are a small ordered table; `semantic_relevance = BAND_VALUES[band]`.
3. **Lexical overlap CORROBORATES.** Keep the existing vocabulary-aware, whole-token,
   `_SHORT_IDENTIFIERS`-preserving ratio. It may raise the band by **at most one step** and
   may never lower it, never create relevance where `sources` is empty, and never gate alone.
4. **If `declared` is empty — the legacy lexical path is UNCHANGED.** An `unknown` kind is a
   fact about our knowledge, not a low grade: there is no provenance to be primary about, so
   the scorer keeps exactly today's behaviour. This is what keeps every standing tripwire
   byte-identical — their fixtures declare no kind.
5. **Support gate, fail-closed.** `support is None` → not consulted, no change. `support is
SUPPORTED` → keep the relevance computed above. `support in {NOT_SUPPORTED, UNKNOWN,
UNAVAILABLE}` → `semantic_relevance = 0.0`, so the package lands in the no-relevance branch
   and abstains at both gates.
6. **Source quality** keeps its bands. `curated_synthetic` raises source quality and is
   EXCLUDED from the relevance band — it is a label, not a measurement. Same for
   `trusted_tool_bypass` and `kg_entity` (see the perimeter decision, §5).
7. **The `top_source_cosine` penalty is retired ONLY where it was proved unreachable.**
   `score_provenance` measured hybrid ∈ [0.508, 1] and dense ∈ [0.5, 1], so `0 < top < 0.5`
   cannot be entered from any live declared path. Keep the penalty for sources that declare NO
   kind, where a sub-0.5 value may genuinely be a raw cosine — the legacy `POOR_RETRIEVAL`
   fixtures sit at 0.18 and their tripwires depend on it. Write the asymmetry and its reason
   at the site; a blanket retirement turns those tripwires red and would be a green by
   subtraction.

## 3. Consumer wiring — `wa_package_builder.build_context_package`

After the DLP gate, before the scorer call:

- the support signal's input is the **REDACTED query and the capped REDACTED context** the DLP
  gate already produced — never the raw `query` argument passed to the scorer, and never the
  reversal map. No client PII crosses any seat boundary.
- the consumer becomes `async` if it is not already (the judge is async); `calculate_evidence_score`
  stays synchronous.
- `evidence_inputs` gains, ADDITIVELY (nothing removed, no existing key's meaning changed):
  `support_verdict`, `support_votes`, `support_judge`, `support_fallback_used`.
- `context_length` KEEPS its meaning exactly: len of sealed chunks including curated, excluding
  the pricing block. Do not touch it.

## 4. The support-negative branch — `wa_codex_leg.py`, BEFORE the broker offer

Stopping package construction is NOT the right disposition: an unbuildable package returns a
fall-off reason that the worker raises as `codex_leg_fell_off` into its retry ladder. Add an
explicit branch BEFORE the broker offer / generator invocation: when the sealed package's
support verdict is not `SUPPORTED`, reach the UNCHANGED finalizer's safe-abstention handling
with the sealed decision and the unchanged score/context, and return the terminal stub /
hand-off through the existing worker fence.

Tests must prove: **no broker offer · no generation · no generation-failure retry
classification · D6 preserved** (the branch generates nothing, so `abstained_at` stays NULL
while `evidence_score` carries the sealed package's frozen score — B3 tells the two apart by
disposition). `wa_finalize` is not edited, `context_length` is not redefined, no threshold and
no telemetry moves.

## 5. Perimeter decision — MANDATORY, recorded in the PR body, silence is not an option

For EACH of: the trusted-tool 0.85 bypass (`_reasoning_evidence.py`), the FAQ fast path and the
KG fast path (`orchestrator_core.py`, both return BEFORE any scorer call) — either (i) bring it
under the support signal and add counterfactual cells to the SUPPLEMENT, or (ii) exclude it
with a written reason AND a tripwire test per path. Any uncovered path that can release
unsupported substantive advice is named as a residual risk in `pack.yml`.

## 6. The benchmark, and how CI stays offline

`harness.decide()` gains the support verdict. Two modes, and the production path reads NEITHER
record:

- **Dux mode (the real measurement):** the judges actually run. This is the number that goes in
  `pack.yml`, with per-repetition votes.
- **CI mode (the regression):** verdicts are replayed from a frozen record
  `support_verdicts_b2.json`, keyed by `sha256(query || "\x00" || "\n".join(context))` —
  **never by `case_id`**, so no label can be smuggled through the key and acceptance (d)'s "no
  case-ID rules" holds at the key as well as in the method.

Add to the existing structural test module: `decide()`'s output is invariant under a deep-copy
mutation of every label field, WITH the support verdict supplied.

## 7. The three debts B1 hands to B2.1 — they ship HERE, not later

- **D-C4 (#6274 C4):** a test that the manifest's pinned `generic_word_definition` (plus
  `generic_word_stopwords` and `generic_word_identifiers`) agrees with EVERY recorded
  `generic_overlap` label, at the moment the rule activates. Implement the definition literally
  from the manifest's own string — case-insensitive `[A-Za-zÀ-ÿ]+` tokens of at least 3
  letters, present in both query and context, not a stopword and not an identifier — and assert
  agreement case by case. A disagreement is a FAILURE to report, never a relabelling.
- **D-B15 (B1.5 follow-up):** a test binding the artifact FILE's sha256
  (`query_vectors_b1_5.json`) to the value recorded in `b1-5-precall.json`. Locate that precall
  file on this base; if it is not in the repo, bind to the value recorded in B1.5's pack.yml and
  say so in the test's docstring. Today this is checked only by hand.
- **D-SETC (Set C):** the THIRD pair set. Set A's negatives delete the trigger token; Set B's
  negatives announce their own insufficiency; **neither measures the hard case — entity
  present, referent wrong, no meta-commentary.** Six pairs authored by the second reader
  (Gemini; Codex is recused because (iii) is its own family), each with one reviewed synthetic
  Indonesian counterpart = 24 cases, into `manifest_supplement_b2.json` together with the four
  distractor pairs ruling I26 makes mandatory. (iii) and the fallback (ii) are measured on Set C
  BEFORE any threshold is fixed in B2.2.

## 8. Frozen, and what a green must never be

- `manifest_mandatory.json` stays byte-identical: no label, no context, no band of it is edited.
  Everything B2 adds goes to the supplement, reported separately.
- Every standing tripwire green and byte-identical, with README D5's ONE exception: the
  label-selected golden loop in `test_evidence_cross_language.py` is replaced by the fixed-input
  cases and corrected expectations B1.3 recorded (the five cases carrying
  `activates_in: "B2.1"`), activated together with the scorer change. The two strict xfails
  become passes and ONLY their `xfail` markers are removed.
- A metric that needs a weakened tripwire is REWORK-DESIGN, never a green by subtraction. If a
  cell of the acceptance cannot reach 0 without relabelling, the PR SUSPENDS for staff-room
  adjudication — the Dux never relabels.
