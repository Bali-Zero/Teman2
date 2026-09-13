# B1.4 build spec — the support-signal design note, measured offline

Mandate B1 (BLUE), PR B1.4 (docs/measurement). Contract: `research/operations/2026-09-11-bot-staff-room/B1-design.md`
§4 B1.4 + §2 exception (1). Deliverable: `research/operations/2026-09-11-bot-staff-room/B1-4-support-signal.md`
plus the probe harness and its receipts under this PR's evidence directory. No production code changes.

## Measurement set

The counterfactual pairs of B1.3's mandatory manifest (`apps/backend-rag/backend/tests/benchmarks/evidence_sufficiency/
manifest_mandatory.json`, cases carrying `pair_id`): same entity, language, provenance and rank; fact present
(`sufficient`) vs absent (`relevant_insufficient`). Use ALL pairs (16 expected; ≥8 required). The harness reads the
manifest's `query`, `context`, `provenance_fixture.sources` ONLY at decision time; `stratum`, `expected_*`,
`supporting_span`, `missing_fact_explanation`, `requested_fact` and `case_id` are used ONLY afterwards, for scoring.

## Candidates (measure all; failures recorded, never excluded)

- **(i) deterministic span check.** Requested-fact extraction is part of the method: slot rules on the QUERY
  (price → currency amount `IDR|Rp` + number; minimum capital → amount + capital/modal; duration → number + time unit
  weeks/days/months/minggu/hari/bulan; requirements → at least two items of a fixed document lexicon: deed/akta,
  NPWP, KBLI, address/alamat, approval/SK/pengesahan). SUPPORTED iff the slot's pattern is found in the context;
  NOT_SUPPORTED iff a slot rule matched the query but not the context; UNKNOWN iff no slot rule matches the query.
- **(ii) local model judge (Ollama on Pro, no egress, $0).** Model pinned `qwen3.8:27b-mlx` (present on Pro — verify
  with `ollama list`), HTTP `http://127.0.0.1:11434/api/generate`, `options: {temperature: 0, seed: 42}`,
  `think: false` if the model accepts it (record what was sent), `stream: false`, timeout 120 s. Fixed rubric (same
  text for (ii) and (iii)): "You judge evidence sufficiency. Question: <q>. Context: <c>. Does the context explicitly
  state the specific fact the question asks for? Reply with exactly one word: SUPPORTED, NOT_SUPPORTED or UNKNOWN."
  Strict parse (first token, case-insensitive, punctuation stripped); anything else or a timeout → UNKNOWN.
- **(iii) Codex seat through the UNCHANGED adapter ONLY.** `backend.llm.codex_exec_client.CodexExecClient` —
  `await CodexExecClient(model=<pinned>).generate(prompt, timeout_s=90)`; model pinned to the WA leg's production
  model (read `wa_codex_leg.py` READ-ONLY to find which constant it passes; if unclear, `MODEL_TERRA`, and say so).
  The adapter supplies its fixed argv prefix, fresh empty cwd, minimal env and stdin transport; if the adapter or any
  control is unavailable (binary missing, login, exception at construction) the candidate is UNAVAILABLE — no hand-typed
  `codex exec`. `PATH` must include `/opt/homebrew/bin` (codex is a Node shebang script). Inputs are the REDACTED
  query and the capped REDACTED context: pass `history=[{"role": "user", "content": query}]` and the case's chunks
  through `wa_dlp.redact_package_fields` exactly as `wa_package_builder.py:~584` does, apply the package's chunk cap
  (find the constant the builder uses), never send the raw query or the reversal map. Temperature/seed are not
  exposed by `codex exec` — record "not controllable", pin model + adapter version instead.
- **(iv) control — no support signal, scorer as today.** `calculate_evidence_score(sources, context, query)` +
  `build_abstain_policy(query).label_abstains(score)` → SUPPORTED iff the label gate passes. Expected to FAIL.

LLM candidates run THREE repetitions per item; any disagreement across repetitions on a pair member marks the pair
UNSTABLE for that candidate, and an UNSTABLE pair counts as not distinguished. Parallelism: (ii) sequential; (iii) at
most 4 concurrent calls. Record per call: latency (s), outcome, parse result; cost = "flat subscription" (iii) /
"$0 local" (ii) / "none" (i, iv).

## Scoring (after all decisions exist)

A pair is **distinguished** by a candidate iff the sufficient member is SUPPORTED and the insufficient member is
NOT_SUPPORTED on every repetition. UNKNOWN is never a success and stays distinct from SUPPORTED in the output.
**Selection contract:** a candidate QUALIFIES only if it distinguishes EVERY pair with no UNSTABLE and no UNKNOWN.

## Outputs

- `evidence/…/support_probe.py` — the harness (one file; async for (iii); `--candidates i,ii,iii,iv`, `--reps 3`,
  `--out receipts.json`); no network other than 127.0.0.1:11434 and the Codex adapter subprocess.
- `evidence/…/support_probe_receipts.json` — every call's decision/latency, plus the per-candidate summary, manifest
  sha256, base sha, model ids, adapter file sha256, host, UTC start/end.
- The note `B1-4-support-signal.md` — frontmatter `title`, `date: 2026-09-11`, `adversarial_review: codex`; sections:
  1 question and why the scorer cannot answer it (the 0.8/0.8 pair, F-B1.1a: no candidate may lean on
  `top_source_cosine`); 2 candidates, each with inputs, failure behaviour (what happens when it cannot decide), consumer
  (where in the package/finalize chain it would be read — upstream of the leg call, per README K3/B2.1(g)),
  cost/latency, PII posture, invocation, model/rubric identity, timeout, failure handling; 3 the measurement table
  (candidate × pair → decisions per repetition, distinguished?, latency) and the summary; 4 recommendation — the
  staff room CHOOSES, the note recommends; if nothing qualifies, say so plainly (B1 §6 stop: B2 cannot open);
  5 residuals; `## Adversarial review` section (filled after the Codex round).
