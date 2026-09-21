---
date: 2026-09-21
domain: operations
client_case: none
sources:
  - prove-live-b4-full-sweep-report-20260921.json (253/253 walks, live)
  - prove-live-b2c-c3-manifest-raw-20260920.json (the C3 manifest the full sweep ran against)
  - prove-live-b4b-manifest-raw-main-8a7e5219-20260921.json (re-emitted manifest, main `8a7e521974`)
  - prove-live-b4b-delta-report-20260921.json (3-walk delta sweep after the re-emission)
discovered_by: session (M5), vo-builder-b4-report
---

# Visa Oracle: B4 full live-enumeration sweep (2026-09-21)

PLAN.md's **B4** row (`research/operations/2026-09-<dd>-visa-oracle-live-enumeration/**`, "the
full enumeration run + the report + one fix PR per red"). This report and the four JSON files
beside it ARE that artefact. Every number below is re-derived from the JSONs by
`scripts/derive_numbers.py` (pasted in the PR body, not committed here — it is a one-shot
reproduction aid, not product code); none is copied from the conductor's mandate log.

## Purpose

Prove **PLAN G2** — "every path combination proven against the live engine" — by walking the
full interview-space manifest against the deployed evaluate endpoint and recording every
verdict, with zero unexplained transport failures.

## Instrument

Two committed pieces, chained:

- **B1 enumerator** — `apps/mouth/scripts/visa-oracle/enumerate-interview-space.ts`. DFS over
  the real `computeNextNode` graph, emits a manifest with the walk count and bound proof.
- **B2 live runner** — `apps/backend-rag/backend/scripts/visa_engine/enumerate_live.py`. Reads
  the manifest, posts each walk to `POST /api/visa-oracle/evaluate` as
  `traffic_source=synthetic_driver`, fail-closed (`--max-requests` has no default, HTTP
  401/403 stops immediately, 429/5xx/timeout stop after 3 consecutive harness reds), resumable.

PRs against these two files, read from `git log --oneline origin/main -- <path>` (path
history only — squash-merged feature-branch commits are excluded by construction):

| file | merged PRs (chronological) |
|---|---|
| `enumerate-interview-space.ts` | #6856 (injectable memo-key projection), #6970 (deterministic UUID per walk — B2''-c C2) |
| `enumerate_live.py` | #6952 (imports `report_lock`, V1-V4 cure, Gear-3 council), #6972 (refuses a walk the engine would reject, before token/network — B2''-c C1) |

**Correction against the assigning prompt's own PR list** (`#6861/#6920/#6952/#6972/#6970`):
`git log` on `origin/main` for these two file paths shows neither #6861 nor #6920:

- `gh pr view 6861` → `state CLOSED`, `mergedAt null`. The original B2 live-runner submission;
  a gate returned `REWORK-BUILD` on it and its circuit-breaker design survived into #6952's
  head (`enumerate_live.py`'s docstring: `after gate REWORK-BUILD on #6861 -- OBS-2`), but the
  PR never merged, so it is correctly absent from `origin/main` history.
- `gh pr view 6920` → merged 2026-09-20T14:04:11Z, files
  `apps/backend-rag/.../report_lock.py` + its test + a brief — the kernel-held-flock dependency
  `enumerate_live.py` imports, not either enumerator file, so it correctly does not appear in a
  path-scoped log on those two paths.

## Method

Full sweep: bench worktree at build `000eaf0732`, resumed from a 60-walk C3 partial
(`manifest_sha256` in the report JSON), `--dry-run` plan `pending=193 already_recorded=60`,
live run 2026-09-20T20:51:10Z → 2026-09-21T00:41:36Z UTC, `stopped_reason=completed`,
`requests_used_this_run=193`, `requests_used_total=253`. `health.start.build_sha ==
health.end.build_sha == 000eaf0732…`, both HTTP 200 — no mid-run redeploy. Rule pack: sequence
22, `rule_pack_id 916915d8-1c58-508d-aff7-742a3c012df7`, on all 253 walks (no drift).
`summary.harness_reds == {}`.

Delta sweep: after PR #6998 merged `main` → `8a7e521974` (A3-M, mapping
`overstay`/`blacklist`/`immigration_investigation` through `REVIEW_FLAG_MAP`), the manifest was
re-emitted (`npm run visa-oracle:enumerate -w apps/mouth`, 2026-09-21T00:55:35Z). Diffing the
253 walk labels against the C3 manifest: **identical label set**, exactly 3 changed payloads
(`review-gate/overstay`, `review-gate/blacklist`, `review-gate/immigration_investigation`),
each now carrying a `disclosed_review_flags` entry. Those 3 were re-swept live
(`--max-requests 3`, 2026-09-21T00:56:52Z → 00:56:58Z, same build `000eaf0732`, `harness_reds
== {}`).

## Verdict distribution (253/253 walks)

| verdict | count |
|---|---|
| SUPPORTED_CANDIDATES | 173 |
| HUMAN_REVIEW_REQUIRED | 41 |
| NO_SUPPORTED_PATH | 27 |
| NEEDS_INPUT | 12 |
| **total** | **253** |

HTTP status: 253/253 = 200. Retries: 0. Latency over the 253 walks (nearest-rank, no
interpolation): **p50 273 ms · p95 1341 ms · max 5128 ms · min 195 ms**.

## The 41 HUMAN_REVIEW_REQUIRED, by `review_reasons` (a walk may carry >1 tag, 47 tags / 41 walks)

| review_reasons tag | count | owning slice |
|---|---|---|
| `DISCLOSED_ACTIVITY_BOUNDARY_REVIEW` | 25 | **A3'** (U5, OD-2/OD-3) |
| `BRIDGING_ADVERSE_HISTORY` | 12 | pack rule → **A8/A9** (seq-23 fold, OD-6) |
| `BRIDGING_FROM_VISIT_ITK_PROHIBITED` | 3 | pack rule → **A8/A9** |
| `BRIDGING_TO_BRIDGING_PROHIBITED` | 3 | pack rule → **A8/A9** |
| `BRIDGING_ONSHORE_ONLY` | 1 | pack rule → **A8/A9** |
| `CALLING_VISA_REVIEW` | 1 | pack rule → **A8/A9** |
| `CITIZENSHIP_LIST_DIVERGENCE` | 1 | pack rule → **A8/A9** |
| `DISCLOSED_CRIMINAL_RECORD_REVIEW` | 1 | by design (G1-a) — not owed to any slice |

40 of the 41 walks are non-criminal holds; the two slices that close them (A3' and A8/A9) are
the ones PLAN already names. This IS the G1 gap, now measured on production rather than
estimated.

## The 27 NO_SUPPORTED_PATH, by `no_path_reasons` (39 tags / 27 walks)

| no_path_reasons tag | count |
|---|---|
| `AGE_BELOW_55` | 14 |
| `INDONESIAN_EMPLOYER_NOT_ALLOWED` | 9 |
| `INDONESIAN_SOURCE_COMPENSATION_BANNED` | 7 |
| `BUSINESS_LOCAL_COMPENSATION_NOT_ALLOWED` | 3 |
| `BVK_NATIONALITY_ONLY` | 2 |
| `LEVEL_BAND_DIKTI` | 2 |
| `PAID_ACTIVITY_WITHOUT_INDONESIAN_SPONSOR` | 1 |
| `E33A_SPONSOR_NOT_GOVERNMENT` | 1 |

Dead ends the rule pack names by design, not harness reds.

## Notices over the 253 walks (64 tags total, a walk may carry 0..N)

| notice | count |
|---|---|
| `DISCLOSED_UNCERTAINTY_CONDITION` | 55 |
| `DISCLOSED_AMBIGUOUS_SPONSOR_CONDITION` | 3 |
| `DISCLOSED_MULTI_PURPOSE_TRIP_CONDITION` | 1 |
| `DISCLOSED_HEALTH_CONCERN_CONDITION` | 1 |
| `DISCLOSED_PRIOR_VISA_REFUSAL_CONDITION` | 1 |
| `DISCLOSED_SOURCE_OF_FUNDS_CONDITION` | 1 |
| `DISCLOSED_PEP_OR_SANCTIONS_CONDITION` | 1 |
| `DISCLOSED_DIPLOMATIC_PASSPORT_CONDITION` | 1 |

On the full-sweep manifest (pre A3-M, emitted by mouth `4a149d0ff4`) the three A3-B notices —
`DISCLOSED_PAST_OVERSTAY_CONDITION`, `DISCLOSED_BLACKLIST_ENTRY_CONDITION`,
`DISCLOSED_IMMIGRATION_INVESTIGATION_CONDITION` — **never appear**: `review-gate/overstay`,
`review-gate/blacklist` and `review-gate/immigration_investigation` carried no
`disclosed_review_flags` yet.

## The delta finding

A3-M (PR #6998, merged to `main` as `8a7e521974`) maps `overstay`/`blacklist`/
`immigration_investigation` through `REVIEW_FLAG_MAP` into `disclosed_review_flags`. Re-emitting
the manifest from that head changes exactly 3 of 253 walk payloads — same 253 walk labels, same
317/317 edge coverage, only those 3 gain a flag. Re-swept live, all 3 now render their named
notice end-to-end and stay `HUMAN_REVIEW_REQUIRED`, held by the pack rule
`BRIDGING_ADVERSE_HISTORY` (which reads `immigration.violation_history`, independent of the new
flag) — the A3-B change is visible in the notice, not in the verdict:

| walk | notice | review_reasons |
|---|---|---|
| `review-gate/overstay` | `DISCLOSED_PAST_OVERSTAY_CONDITION` | `BRIDGING_ADVERSE_HISTORY` |
| `review-gate/blacklist` | `DISCLOSED_BLACKLIST_ENTRY_CONDITION` | `BRIDGING_ADVERSE_HISTORY` |
| `review-gate/immigration_investigation` | `DISCLOSED_IMMIGRATION_INVESTIGATION_CONDITION` | `BRIDGING_ADVERSE_HISTORY` |

Net effect on the G1 ledger: **+0** — these three were already `HUMAN_REVIEW_REQUIRED` via
`violation_history` before A3-M landed. Closing their hold is the pack's job (A8 fold → A9
sign/activate, OD-6, owner signs once), not the mouth's or the runner's.

## What this proves for PLAN G2, and what it does not

**Proven** (G2-b, in full): a committed, rate-limited, resumable live runner posted all 253
covering walks of the real interview graph to the deployed evaluate endpoint labelled
`traffic_source=synthetic_driver`, at a single stable build (`000eaf0732`) and rule-pack
sequence (22), zero harness reds, zero retries, 253/253 HTTP 200. G2-d (every red closed inside
the mission) holds vacuously — there were no reds to close. G2-e holds by construction: every
persona is synthetic (`probe_evaluate.py`'s driver-token idiom), confirmed here by grep (see
`## Declared limits`).

**Not proven** (G2-c, B3): this sweep only exercises the engine endpoint. It says nothing about
whether the **promoted mouth** renders the same verdict, candidate set, or review-reason text in
its DOM — that is B3's UI-parity runner (Playwright, stratified sample, against the promoted
Vercel deployment), which needs a Zero decision on walk authorization before it can run (per
the conductor's mandate, OD pending). Until B3 runs, "the live engine returns X" and "the live
UI shows X" are two separate claims; only the first is measured here.

## Declared limits

- This is the **engine half** of G2, not the UI half (B3, see above).
- `AGE_BELOW_55`/employer/compensation dead ends are the pack's stated policy, not this
  report's judgment — this report counts them, it does not evaluate them.
- The 41 `HUMAN_REVIEW_REQUIRED` walks are held, not resolved; 40 of 41 wait on A3'/A8-A9 work
  already on PLAN, 1 is criminal-by-design and stays held permanently.
- No client data anywhere: the four JSON files below carry synthetic personas only
  (`traffic_source=synthetic_driver`). Confirmed by grep for an email pattern, a 10+-digit
  phone-like run, and any key named `email`/`phone`/`passport`/`npwp`/`ktp`/`nik` across all
  four files — zero matches. The only `passport`-adjacent string found is the enum value
  `DISCLOSED_DIPLOMATIC_PASSPORT_CONDITION` (a notice name, not a passport number), and the
  apparent "phone-like" digit runs are `assessment_id` UUID5 values.

## Files

- `prove-live-b4-full-sweep-report-20260921.json` — the 253-walk report (this README's primary
  source).
- `prove-live-b2c-c3-manifest-raw-20260920.json` — the manifest the full sweep ran against
  (pre A3-M, 253 walks, `coveringSubset.walks`).
- `prove-live-b4b-manifest-raw-main-8a7e5219-20260921.json` — the re-emitted manifest from main
  `8a7e521974` (post A3-M, same 253 labels, 3 changed payloads).
- `prove-live-b4b-delta-report-20260921.json` — the 3-walk delta sweep.

## Reproduction

```bash
# PR history for the two enumerator files (path history, origin/main only)
git log --oneline origin/main -- \
  apps/backend-rag/backend/scripts/visa_engine/enumerate_live.py \
  apps/mouth/scripts/visa-oracle/enumerate-interview-space.ts

# re-derive every number in this README from the four JSONs beside it (run from this directory)
python3 - <<'PY'
import json
from collections import Counter
d = json.load(open("prove-live-b4-full-sweep-report-20260921.json"))
walks = d["walks"]
print("verdicts:", dict(Counter(w["engine_state"] for w in walks)))
lat = sorted(w["latency_ms"] for w in walks)
p = lambda pct: lat[round((len(lat) - 1) * pct)]
print("p50/p95/max:", round(p(0.5)), round(p(0.95)), round(max(lat)))
PY

# re-run the full sweep against the live engine (needs the driver token file; fresh report path,
# same manifest — --manifest and --report are both required, --max-requests is required and has
# no default by design, fail-closed)
PYTHONPATH=. .venv/bin/python apps/backend-rag/backend/scripts/visa_engine/enumerate_live.py \
  --manifest research/operations/2026-09-21-visa-oracle-live-enumeration/prove-live-b2c-c3-manifest-raw-20260920.json \
  --report /tmp/reproduce-b4-report.json \
  --max-requests 253 --rate-per-minute 25
```
