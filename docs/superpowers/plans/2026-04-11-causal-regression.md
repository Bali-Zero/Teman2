# Plan: Causal Regression Harness for backend-rag Evals

Date: 2026-04-11
Branch: `feat/evaluator-causal-regression`
Scope: `apps/evaluator/causal_regression/` + tests + docs. Zero touches to `apps/backend-rag/`.

## Problem

`apps/evaluator/judgement_day.py` runs Ragas over a live RAG deploy and prints a csv. When a
query that used to pass now fails, we have no way to ask **why**. The answer is a commit + a
concrete artifact (a chunk, a prompt line, a config flag). This harness walks backward
through commits touching `apps/backend-rag/`, replays each against a frozen eval set, and
attributes failures to one of seven root-cause categories.

## Constraints (hard)

- No network. No API keys. No Anthropic/OpenAI/Gemini calls.
- Local Ollama allowed but optional. If absent, emit feature vectors only.
- Never touch the working tree. Never `git checkout`. Use `git show SHA:path` for blob
  reconstruction, cache under `/tmp/causal-kb-cache/{sha}/`.
- Handle binary KB files: detect null byte in blob, skip with a `warning` entry in metadata.
- Run on a repo with uncommitted changes. Do not consider uncommitted changes.
- Determinism: re-running on the same `--range` produces byte-identical JSON. Sort
  everything. No timestamps inside the JSON body. Only metadata fields under author control.
- Wall clock budget: 30 commits x 50 queries, no LLM, < 30 min on M4 Pro.

## Causal categories (seven)

1. `KB_CONTENT_CHANGED` — expected-supporting chunk text mutated.
2. `KB_REMOVED` — expected-supporting doc deleted.
3. `KB_ADDED_NOISE` — new doc displaced a previously top-k chunk.
4. `PROMPT_CHANGED` — referenced system prompt file diff.
5. `RETRIEVER_CONFIG_CHANGED` — top-k / chunking / thresholds / collection names.
6. `LLM_CONFIG_CHANGED` — model / temperature / max tokens.
7. `UNKNOWN` — no in-scope file changed between parent and child commit.

## Architecture

```
apps/evaluator/causal_regression/
  __init__.py
  __main__.py           CLI entry (argparse)
  commit_walker.py      walk_range() -> list[CommitSnapshot]
  replay_engine.py      run_eval_set(snapshot, eval_rows) -> list[QueryResult]
  causal_diff.py        diff_snapshots(prev, curr) -> CausalDiff
  regression_report.py  build_report(results, diffs) -> {json, html}
  _retriever.py         small deterministic BM25-ish retriever
  _gitblob.py           git show / cat-file helpers
  _types.py             dataclasses and enums
```

### `commit_walker.py`

- Inputs: `range_expr` (default `HEAD~30..HEAD`), `path_filter` (default `apps/backend-rag/`).
- For each SHA (oldest first), calls `git log -n1 --format=...` and `git show --name-only`
  to compute: `{sha, short_sha, subject, parent_sha, changed_kb_files, changed_prompts,
  changed_llm_cfg, changed_retriever_cfg}`.
- Categorization regexes (compiled once):
  - KB: matches `backend/kb/` or `packages/kb/` or `.jsonl` under kb.
  - Prompts: matches `backend/prompts/`.
  - LLM cfg: `llm/`, `ollama_client.py`, `config.py` with `model` in diff, `llm_config.yaml`.
  - Retriever cfg: `services/rag/`, `hybrid_search`, `retriever_config.yaml`, `chunking`,
    and `top_k` / `chunk_size` appearing in the unified diff text.
- Returns plain dicts — no live `git` subprocess state leaks.
- Determinism: commits sorted by `(commit_order_index, sha)` where order is the git log
  topological index we walked. Never uses calendar dates.

### `replay_engine.py`

- For each `CommitSnapshot`:
  1. Reconstruct KB state: for each `changed_kb_file` in the snapshot AND any baseline KB
     files we care about (tracked by scanning `git ls-tree -r SHA -- {kb_root}`), we write
     the blob to `/tmp/causal-kb-cache/{sha}/{path}`. Binary blobs (`\x00` in first 8k)
     are skipped with `warning`.
  2. Build an in-memory `MockRetriever` instance (see `_retriever.py`).
  3. For every row in the frozen eval set (`{query_id, query, expected_keywords}`):
     - Call `retriever.retrieve(query, top_k=5)` -> list of `(doc_path, score, snippet)`.
     - Compute `claim_coverage` = fraction of `expected_keywords` present in any top-k
       snippet after normalization (lowercase, strip punctuation, tokenize).
     - `passed` = `claim_coverage >= 0.5` (half the expected hooks present).
     - Collect feature vector: top-k chunk ids + scores.
- No LLM call. The CLI exposes `--with-ollama` which, if set AND `ollama` CLI is on PATH,
  runs a local `gemma4:e2b` (or configurable) generation to add a `generated_answer` field.
  Not wired to causal categorization; pure cosmetic for the HTML report.

### `causal_diff.py`

- Inputs: `prev_snapshot`, `curr_snapshot`, results from the replay on both.
- Outputs: `CausalDiff` per query_id:
  - `retrieval_delta`: ordered list of `{doc, prev_rank, curr_rank, prev_score, curr_score,
    delta}` for chunks that moved in/out of top-k.
  - `prompt_delta`: boolean + list of prompt files that changed between the two commits.
  - `config_delta`: dict of retriever / llm config files that changed.
  - `claim_delta`: `{prev_covered, curr_covered, missing_now, regained}`.
  - `root_cause`: applies the decision table:
    ```
    if passed_prev and not passed_curr:
      if claim_delta.missing_now and KB_REMOVED in diff_kind -> KB_REMOVED
      elif claim_delta.missing_now and any retrieval_delta prev-only file was mutated
           in this commit -> KB_CONTENT_CHANGED
      elif any retrieval_delta curr-only doc is new in this commit -> KB_ADDED_NOISE
      elif prompt_delta -> PROMPT_CHANGED
      elif config_delta.retriever -> RETRIEVER_CONFIG_CHANGED
      elif config_delta.llm -> LLM_CONFIG_CHANGED
      else -> UNKNOWN
    ```

### `regression_report.py`

- Aggregates per query, per commit.
- Emits:
  - `outputs/causal_report.json`: sorted keys, no timestamps in body, single
    `metadata.range` field.
  - `outputs/causal_report.html`: self-contained (inline CSS, no JS), with a CSS-grid
    flamegraph: rows = queries, columns = commits (left = old, right = new), cells colored
    by pass/fail, legend keyed to the seven categories. Tooltip via `title=` attribute.
- `top_regressions`: sorted list of `(query_id, commit_sha, category)` for the biggest
  coverage drops (prev - curr), stable tie-break by `(query_id, sha)`.

### `__main__.py`

CLI:
```
python -m apps.evaluator.causal_regression \
  --range HEAD~30..HEAD \
  --eval-set apps/evaluator/causal_regression/data/eval_visa.jsonl \
  --out outputs/
```

Flags:
- `--range` (default `HEAD~30..HEAD`)
- `--eval-set` (required unless omitted for dry-run)
- `--out` (default `outputs/`)
- `--kb-root` (default `apps/backend-rag/backend/kb`)
- `--with-ollama` (opt-in, off by default)
- `--quiet` / `--verbose`
- `--dry-run` (walk commits, print count, exit 0)

Exit codes:
- 0 success
- 2 no commits matched range (empty)
- 3 eval set unreadable
- 4 git range invalid

## Tests

`apps/evaluator/tests/test_causal_regression.py`:

1. `test_commit_walker_5commit_synthetic(tmp_path)` — build a throwaway git repo with 5
   commits touching a fake `kb/`, assert walker returns 5 snapshots with categorization.
2. `test_causal_diff_known_retrieval_delta()` — hand-craft two snapshots with one doc
   added in commit 2, assert `KB_ADDED_NOISE` classification.
3. `test_report_generator_html_sections(tmp_path)` — feed fixture, assert HTML contains
   `<table class="flamegraph">`, `<div class="legend">`, and the category names.
4. `test_e2e_on_real_repo(tmp_path)` — run CLI with `--range HEAD~5..HEAD` against real
   worktree, assert exit 0 and both files exist, JSON parses.
5. `test_determinism(tmp_path)` — run CLI twice on same range, `cmp` the two JSON files,
   assert equal.
6. `test_binary_kb_file_skipped(tmp_path)` — add a `.png`-style blob to synth repo, assert
   it appears in `warnings` list, no crash.

## Fixtures

`apps/evaluator/tests/fixtures/causal/`:
- `snapshot_a/doc_kitas.md` (~400 bytes)
- `snapshot_a/doc_bpjs.md` (~400 bytes)
- `snapshot_b/doc_kitas.md` (mutated)
- `snapshot_b/doc_bpjs.md`
- `snapshot_b/doc_newnoise.md` (new, competes with kitas)
- `snapshot_c/doc_bpjs.md` (kitas DELETED)
- `eval_tiny.jsonl` — 5 queries, each with `expected_keywords` list.

Target total size: < 20 KB.

## Determinism details

- `json.dumps(..., sort_keys=True, ensure_ascii=False, indent=2)` with trailing newline.
- Lists of results: sort by `(query_id, commit_sha)` before dumping.
- HTML: the generator uses fixed-width formatting and no timestamps except an optional
  footer that reads `metadata.range` (user input, deterministic).
- All path separators normalized to forward slashes in output.

## Deliverables checklist

- [x] `commit_walker.py` with docstring
- [x] `replay_engine.py` with docstring
- [x] `causal_diff.py` with docstring
- [x] `regression_report.py` with docstring
- [x] `_retriever.py` + `_gitblob.py` + `_types.py`
- [x] `__main__.py` CLI
- [x] Tests above passing
- [x] `apps/evaluator/docs/causal_report_example.json` (example from real run)
- [x] `apps/evaluator/docs/causal-regression.md`
- [x] 3+ meaningful commits

## Non-goals

- No live LLM judge. No API calls.
- No re-ranker, no embeddings, no Qdrant. The mock retriever is BM25-ish so we can diff
  retrieval decisions without touching the vector store.
- No intent to replace Ragas. This complements it: Ragas tells you what fails, causal
  tells you who to blame.

## Risks

- `git ls-tree` on 30 commits may be slow if the KB is large. Mitigation: scope the
  KB root via `--kb-root` and filter by blob size < 256 KB.
- Retriever disagreement with production (BM25 vs hybrid+rerank) means we may miss some
  real regressions. Accepted: categorization is still useful whenever the mock agrees.
- The decision table is heuristic. Accepted and documented in the report.
