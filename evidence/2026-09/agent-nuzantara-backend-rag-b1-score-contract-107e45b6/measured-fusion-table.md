# B1.1 first artifact — the MEASURED rank ↔ returned-score table

Bound to git base sha `1d726045c9ca75ab64a75e92b062e52b0b763a98`. Every citation below is a
citation into THAT tree, never into a Fly release: prod moved from v4389 (the release live at
measurement time) to v4396 at 20:47Z on unrelated compliance-stack deploys while this artifact
was being written, which is exactly why the binding is to the git base.

## Why this had to be measured

`README.md` §0 states the fusion table as "an expectation, not a measurement": production fusion
is server-side (`apps/backend-rag/backend/core/qdrant_db.py:1308`, `{"fusion": "rrf"}`) and the
server's ranking constant is not verified from any file in this repo. The two in-repo RRF helpers
(`backend/services/rag/hybrid_search.py:32`, `RRF_K = 60`, 1-based ranks; and
`backend/services/search/search_service.py:897-916`) are NOT the hot path. The installed client's
local-mode constant (`apps/backend-rag/.venv/lib/python3.11/site-packages/qdrant_client/hybrid/fusion.py:4-11`,
`ranking_constant = 2`) is the package's file, not the server's behaviour.

## Method

Read-only, inside the prod container, machine `1781e5eda03438`.

- The query vectors are **one existing point's own stored `dense` and `bm25` vectors**, fetched by
  `points/scroll` with `with_vector=true`. **No embedding call was made.**
- **No write** of any kind: only `GET /`, `GET /collections`, `GET /collections/{c}`,
  `POST .../points/scroll` and `POST .../points/query`.
- **Nothing was exported** except server version, collection name, point count, vector dimensions,
  per-list ranks, list membership and returned scores. No payload, no point id, no vector, no
  credential. The probe reads `QDRANT_URL`/`QDRANT_API_KEY` from the container environment and
  never prints them.
- The fused call is byte-shaped on the production payload at `core/qdrant_db.py:1288-1312`
  (a `dense` + `bm25` prefetch under `{"fusion": "rrf"}`), with `prefetch_limit = limit * 3` as
  `backend/services/search/search_service.py:1140` computes it.
- The probe was uploaded to the container's `/tmp` with `fly ssh sftp put`, executed once with
  `fly ssh console -C`, and deleted in a second `fly ssh console -C` call.

This is the ONE prod-Qdrant read `B1-design.md` §2 grants B1 (the RC2 fence is write/export).
Any further prod read is gated on a staff-room ack before it runs.

## Measured

- **Prod Qdrant server version `1.16.3`.** Pro's local Qdrant is `1.12.5`, so the local instance
  was NOT usable as a stand-in — the version that decides the constant is the prod one.
- Collection `kbli_2025_final_hybrid`, 1873 points, dense dim 1536, query sparse nnz 393.
- `prefetch_limit = 30`, fused `limit = 10`.

| fused_rank | dense_rank0 | bm25_rank0 | lists      | returned_score | distance | formatted |
| ---------- | ----------- | ---------- | ---------- | -------------- | -------- | --------- |
| 0          | 0           | 0          | dense+bm25 | 1.000000       | 0.000000 | 1.000000  |
| 1          | 1           | 1          | dense+bm25 | 0.666667       | 0.333333 | 0.750000  |
| 2          | 2           | 14         | dense+bm25 | 0.312500       | 0.687500 | 0.592593  |
| 3          | 16          | 2          | dense+bm25 | 0.305556       | 0.694444 | 0.590164  |
| 4          | 7           | 4          | dense+bm25 | 0.277778       | 0.722222 | 0.580645  |
| 5          | 20          | 3          | dense+bm25 | 0.245455       | 0.754545 | 0.569948  |
| 6          | 3           | —          | dense      | 0.200000       | 0.800000 | 0.555556  |
| 7          | 4           | —          | dense      | 0.166667       | 0.833333 | 0.545455  |
| 8          | 5           | —          | dense      | 0.142857       | 0.857143 | 0.538462  |
| 9          | —           | 5          | bm25       | 0.142857       | 0.857143 | 0.538462  |

`distance` is `1.0 - returned_score` (`core/qdrant_db.py:1335`); `formatted` is `1/(1+distance)`
(`backend/services/misc/result_formatter.py:89`), shown WITHOUT any collection boost.

## Verdict

**`returned_score = Σ over contributing lists of 1 / (2 + rank0)`** — zero-based rank, ranking
constant 2. Exact on all ten rows (`MATCHES_k2_zero_based=True`). The k=60 / 1-based hypothesis is
refuted on all ten (`MATCHES_k60_one_based=False`).

So the SERVER's constant equals the installed client's local-mode constant. The README's
expectation table is CONFIRMED by measurement rather than assumed; there is no reconciliation gap
to declare, and B1.1(c)'s values derive from a table that is now both measured and local. Kimi K1's
substantive point holds: the in-repo RRF helpers are not the hot path.

## The consequence — finding F-B1.1a

Fusion output is bounded BELOW at `1/(2 + prefetch_limit - 1) = 1/31 = 0.0323`, so
`distance ≤ 0.9677` and `result_formatter.py:89` maps **every** hybrid result into
**[0.508, 1.000]** before any collection boost. The dense fallback is bounded the same way for any
non-negative cosine: `1/(2 - cos) ≥ 0.5` at `cos = 0`. The curated block is minted at a synthetic
`1.0` (`services/rag/agentic/wa_package_builder.py:529`).

Therefore `services/rag/agentic/reasoning_utils.py:665` —

```
if 0 < top_source_cosine < 0.5 and final_score > 0.15:
```

— **cannot fire on any live path**: not hybrid, not dense-fallback-with-non-negative-cosine, not
curated. The only input that reaches it is a NEGATIVE cosine (which makes `distance > 1`), and
1536-dim `text-embedding-3-small` vectors essentially never produce one. The comment above it at
`:650` calls the field "Qdrant's per-source cosine similarity"; it is a ranking transform that
structurally cannot enter the branch written to consume it.

**The semantic-alignment penalty is effectively dead code in production.** That is now a measured
claim, not a reading, and it sharpens D1 in a way the packet should carry: repairing provenance
does not repair the scorer, and B2 will be inverting a metric one of whose two guards has never run.

It also constrains B1.4: **no support-signal candidate may lean on `top_source_cosine` as currently
minted**, because that number is not observable as a relevance signal on the live path.

## Digest-compatibility receipt (B1.1(d) input)

Measured read-only on prod Postgres via `scripts/pg.sh` at the same sitting:

```
 status | count |            newest
--------+-------+-------------------------------
 failed |   241 | 2026-09-01 08:31:11.591666+00
 done   |   179 | 2026-09-01 09:27:53.327524+00
```

Only terminal statuses exist; there is no `pending` or `generating` row, and the newest row of any
kind is 2026-09-01 09:27:53Z — the same instant Fable measured independently. **No package is in
flight**, so the "a digest change with rows in flight is a STOP" condition of `B1-design.md` §4(d)
is not triggered. This is a receipt about in-flight rows only; it is not a licence to change the
digest casually, and the PR states the digest's actual disposition separately.
