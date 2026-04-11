# Causal Regression Harness

A git-walking, KB-reconstructing, BM25-replaying tool that answers the question
**"which commit broke this eval prompt?"** for any query in the Nuzantara RAG
evaluation suite.

## What it does

- Walks a git rev range (default `HEAD~30..HEAD`) filtered to commits that touch
  `apps/backend-rag/`.
- For every commit, reconstructs the KB state from git blobs into
  `/tmp/causal-kb-cache/{sha}/` — never a `git checkout`, never a touch of the
  working tree.
- Runs a frozen JSONL eval set through a deterministic, dependency-free BM25
  mock retriever over the reconstructed KB.
- For every adjacent commit pair, computes a causal diff and classifies any
  pass -> fail transition into one of seven root-cause categories.
- Emits two artifacts: a machine-readable JSON and a self-contained HTML
  flamegraph (no JS, no network).

The harness never calls an external LLM. The default is zero API keys. An opt-in
`--with-ollama` flag is reserved for a future local-only extension; it is not
required to produce the report.

## Usage

```bash
PYTHONPATH=. python -m apps.evaluator.causal_regression \
    --range HEAD~30..HEAD \
    --eval-set apps/evaluator/causal_regression/data/eval_visa.jsonl \
    --out outputs/ \
    --kb-root apps/backend-rag/backend/kb
```

Useful flags:

- `--range` — any git revision range.
- `--eval-set` — JSONL of `{query_id, query, expected_keywords}` rows.
- `--out` — directory where `causal_report.json` and `causal_report.html` land.
- `--kb-root` — prefix under which to search KB files at each commit.
- `--top-k` — number of retrieved chunks per query (default 5).
- `--coverage-threshold` — minimum `covered/expected` ratio for pass (default 0.5).
- `--trim-json` — smaller JSON (no per-query `results`, only non-trivial diffs).
- `--dry-run` — walk only, print `short_sha subject` per commit and exit.

Exit codes: 0 success, 2 empty range, 3 eval set unreadable, 4 invalid range.

## Eval set format

```jsonl
{"query_id": "V01_kitas_basics", "query": "What is KITAS", "expected_keywords": ["kitas", "permit"]}
```

Each row must have `query_id` (stable across runs — used as the flamegraph row
label), `query` (the retrieval query), and `expected_keywords` (a list; a
row passes when at least `coverage-threshold` of these appear in any
retrieved snippet after lowercasing and tokenization).

## Root cause categories

1. `KB_CONTENT_CHANGED` — a doc that was or is in top-k was edited.
2. `KB_REMOVED` — a supporting doc was deleted.
3. `KB_ADDED_NOISE` — a new doc crowded out a previously-top chunk.
4. `PROMPT_CHANGED` — a `backend/prompts/` file changed in this commit.
5. `RETRIEVER_CONFIG_CHANGED` — `backend/services/rag/`, reranker, chunking.
6. `LLM_CONFIG_CHANGED` — `backend/llm/`, `ollama_client`, model config.
7. `UNKNOWN` — nothing in scope changed; the regression came from elsewhere.

Classification is deterministic and applied in a fixed decision-table order.
The harness is conservative: if nothing in scope moved, it does not guess.

## Architecture

```
apps/evaluator/causal_regression/
  __init__.py            role docstring only
  __main__.py            CLI (argparse)
  _gitblob.py            git show / ls-tree helpers, binary detection
  _retriever.py          fixed-params BM25 retriever (k1=1.5, b=0.75)
  _types.py              dataclasses + RootCause enum
  commit_walker.py       walk_range() -> list[CommitSnapshot]
  replay_engine.py       reconstruct_kb + run_eval_set
  causal_diff.py         diff_snapshots() -> list[CausalDiff]
  regression_report.py   build_json / build_html / write_report
  data/eval_visa.jsonl   default visa eval set (8 queries)
  data/eval_politics.jsonl   politics eval set used by the committed example
```

## Determinism

- JSON output is written via `json.dumps(sort_keys=True, indent=2)` with a
  trailing newline. No timestamps anywhere in the JSON body.
- BM25 ties are broken by lexicographic doc path.
- All lists in the output are sorted by a stable key. `commit_walker` sorts
  file lists with `sorted(set(...))`.
- `test_e2e_determinism_two_runs` asserts the final JSON is byte-identical
  across two CLI invocations on the same range.

## Limitations

- **Mock retriever != production.** The BM25 scorer ignores chunking,
  hybrid search, RRF, and the CrossEncoder reranker. A query that passes the
  mock retriever may still fail in production and vice-versa. Causal
  attribution is still useful whenever the mock's verdict agrees with
  production on the query's pass/fail state at both endpoints of the range.
- **Heuristic classification.** The decision table matches the most common
  patterns but cannot tell a "deleted and recreated" file from a "renamed"
  one; in that case the commit is classified as `KB_REMOVED` on the parent
  pair and `KB_ADDED_NOISE` on the child pair. The report surfaces the raw
  snapshots so a human can disambiguate.
- **Large KBs.** Files >256 KiB are skipped with an `oversize_skipped`
  warning; binary files (null byte in first 8 KiB) are `binary_skipped`.
  A KB that stores most content in PDFs will produce no useful replay
  signal.

## Future work

- Plug in an alternative retriever backend (e.g. a read-only copy of the
  production Qdrant schema + sentence-transformers) behind a feature flag.
- Add `--with-ollama` to annotate cells with a locally-generated answer and
  a `claim_entailment` sub-score.
- Replace the decision table with a learned classifier trained on the
  corpus of past RAGAS failures once we have enough labeled data.
