# S18 — Zantara RAG truth-eval harness

A real RAG evaluation harness for Zantara prod. Measures **retrieval** (recall@k)
and **generation** (faithfulness / correctness) against a *verified* golden set.

## Why this exists (scar S2)

The previous audit (`research/operations/2026-05-31-rag-truth-vs-nlm-oracle.md`)
could **not** measure Zantara accuracy: `/api/oracle/query` is RBAC-walled
(requires a JWT bound to a `team_members` row; an MCP/unknown caller gets 401).
This harness is built so it is **provably runnable even while that arm is
blocked** (`--offline`), and runs a full paired eval the moment a JWT is
provisioned (`--jwt`).

## Golden set

`golden_set.json` — 13 Q&A pairs across `kbli / company / tax / property`. Every
`ground_truth` and `must_contain` fact is sourced from artifacts **committed on
`origin/main`** and is grep-verifiable:

- KBLI codes: `apps/backend-rag/scripts/generated_guides/company/kbli_2025_catalogo_completo.txt` (BPS Reg 7/2025)
- Company/capital/nominee: `research/legal/2026-06-02-pt-pma-nominee-ban-bkpm-oss.md`
- Positive list: `research/legal/2026-06-02-positive-investment-list-kbli-foreign-ownership.md`
- Tax: `research/tax/2026-06-02-corporate-withholding-but-coretax.md` + `fact_pmk_131_2024_ppn_effective_rate`
- Property: `research/property/2026-06-02-foreign-property-rights-hak-pakai-hgb-leasehold.md`

No NotebookLM live calls — the golden set is fully self-contained and auditable.

## Metrics

- **recall@k** — fraction of `expected_sources` basenames that appear in the
  top-k `sources` the RAG returns. Pure retrieval signal.
- **must_contain coverage** — fraction of the ground-truth key facts the answer
  asserts (cheap, always runs, no LLM).
- **LLM faithfulness** (`--judge`) — a 0–1 score from a strict judge prompt run
  over the **Claude Max-plan OAuth CLI** (`CLAUDE_CODE_OAUTH_TOKEN`). The judge
  subprocess strips `ANTHROPIC_API_KEY` (Golden Rule: never the paid endpoint).
  If the CLI is missing, the judge degrades to the lexical scorer — it never
  reaches for a paid SDK.
- **asserts_stale_as_current** — guard that flags answers presenting a legacy
  code (e.g. `55193`) as the current 2025 villa code.

The embedding model is **FROZEN** to `text-embedding-3-small` / 1536 dim. The
harness never embeds anything itself; it consumes the prod RAG's own retrieval,
so the frozen embedding is honoured by construction. `load_golden()` asserts the
golden set declares the frozen model/dim.

## Usage

```bash
cd apps/evaluator/rag_eval

# 1. Offline self-check (no prod, no creds) — proves the harness runs.
python rag_eval.py --offline

# 2. Full eval vs prod once a JWT is granted (NEEDS-ANTONELLO).
python rag_eval.py --jwt "$RAG_EVAL_JWT" --k 5 --report report.json

# 3. Add the LLM faithfulness judge.
python rag_eval.py --jwt "$RAG_EVAL_JWT" --judge --report report.json

# 4. Against a local backend.
python rag_eval.py --jwt "$RAG_EVAL_JWT" --local
```

## NEEDS-ANTONELLO

To unblock the prod arm: provision a JWT for a `team_members` row with a service
role (`visa_specialist` / `tax_consultant` / `company_setup`), or authorize the
eval to run from inside the backend venv against `services/rag/query_service`.
Pass it via `--jwt` or env `RAG_EVAL_JWT`. Until then the harness runs
`--offline` and exits 0.

## Tests

```bash
python -m pytest test_rag_eval.py -v
```

No network / no LLM — pins golden-set integrity, the villa verdict (55203), and
the metric functions.

## Villa KBLI verdict

**55203** is correct (`AKTIVITAS VILA`, KBLI 2025 / BPS Reg 7/2025). `55193` is a
legacy KBLI-2020/PP28 source code that maps to 55203; it is absent from the
canonical KBLI 2025 catalog. See `research/operations/S18-rag-eval-FROZEN.json`.
