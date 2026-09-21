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
adversarial_review: codex
---

# Visa Oracle: B4 full live-enumeration sweep (2026-09-21)

PLAN.md's **B4** row (`research/operations/2026-09-<dd>-visa-oracle-live-enumeration/**`, "the
full enumeration run + the report + one fix PR per red"). This report and the four JSON files
beside it ARE that artefact. Every number below is re-derived from the JSONs by
`scripts/derive_numbers.py` (pasted in the PR body, not committed here — it is a one-shot
reproduction aid, not product code); none is copied from the conductor's mandate log.

## Purpose

Advance **PLAN G2-b** — the engine-side live sweep — by walking the manifest's 253-walk edge
covering set against the deployed evaluate endpoint and recording every verdict, with zero
unexplained transport failures. **Not** every path combination: the manifest's own
`walksTotalExact` is 72,165,845,568,960 (edge coverage, proven, is a different and much smaller
claim than combinatorial coverage — see Declared limits).

## Instrument

Two committed pieces, chained:

- **B1 enumerator** — `apps/mouth/scripts/visa-oracle/enumerate-interview-space.ts`. DFS over
  the real `computeNextNode` graph, emits a manifest with the walk count and bound proof.
- **B2 live runner** — `apps/backend-rag/backend/scripts/visa_engine/enumerate_live.py`. Reads
  the manifest, posts each walk to `POST /api/visa-oracle/evaluate` as
  `traffic_source=synthetic_driver`, fail-closed (`--max-requests` has no default). Three
  independent circuit breakers (`enumerate_live.py:940-960`): HTTP 401/403 stops immediately;
  HTTP 429 stops immediately after its own bounded retries and never counts toward the other
  tally; every other harness red (5xx, timeout, connection error, invalid 200 body) stops after
  3 CONSECUTIVE reds (an engine verdict resets that counter to zero). Resumable.

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
live run (the 193-walk resumed leg) 2026-09-20T20:51:10Z → 2026-09-21T00:41:36Z UTC,
`stopped_reason=completed`, `requests_used_this_run=193`, `requests_used_total=253`.
`health.start.build_sha == health.end.build_sha == 000eaf0732…`, both HTTP 200. **Scope of that
claim, precisely**: `report["health"]["start"]` is overwritten on every resume
(`enumerate_live.py:914`), so the two probes bound only the 193-walk resumed leg's own window
(20:51–00:41Z), not the full 253-walk history back to the original 60-walk partial, and two
discrete probes cannot rule out a redeploy-and-revert between them — what is actually proven is
that the **rule pack was constant across all 253 responses** (sequence 22,
`rule_pack_id 916915d8-1c58-508d-aff7-742a3c012df7`, no drift), which is the load-bearing fact
for verdict comparability. `summary.harness_reds == {}`.

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

HTTP status: 253/253 = 200. Retries: 0. Latency over the 253 walks, standard nearest-rank
(`sorted_lat[ceil(n·p) − 1]`, 0-indexed, n=253): **p50 273 ms · p95 1494 ms · max 5128 ms · min
195 ms**. **Correction (adversarial review):** a first draft reported p95 as 1341 ms, from a
different index (`round((n−1)·0.95) = 239`, val 1340.72) that happens to match the conductor's
own informal reading in `MANDATE-vo.md` — that is not the standard nearest-rank definition
(rank `⌈p·n⌉`, 1-indexed = 241, 0-indexed 240, val 1493.69). Both indices are adjacent
(239 vs 240) and both are "a nearest-rank convention", but they are not the same number and the
draft did not disclose the choice; corrected here to the standard one.

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
317/317 edge coverage, only those 3 gain a flag. Re-swept live, the API now returns each walk's
named notice (engine-side only — no DOM was rendered, see Declared limits) and all 3 stay
`HUMAN_REVIEW_REQUIRED`, held by the pack rule
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

**Proven** (G2-b, the runner's own transport contract): a committed, rate-limited, resumable
live runner posted all 253 edge-covering walks of the real interview graph to the deployed
evaluate endpoint labelled `traffic_source=synthetic_driver`, a constant rule-pack sequence
(22) across all 253 responses, zero *harness* reds (the runner's own transport-failure
classification: 401/403, 429, 5xx, timeout, connection error, invalid 200 body — none
occurred), zero retries, 253/253 HTTP 200. **Not present in this report**: the Fly release id
and the Vercel deployment id that PLAN's G2-b row asks the report to name — `enumerate_live.py`
records `build_sha` (a git commit) in `health`, not a Fly release id, and no Vercel id at all;
named here as owed rather than silently omitted.

**Retracted** (adversarial review, first draft): a first draft claimed "G2-d holds vacuously —
there were no reds to close." That conflated two different definitions of "red". PLAN's own
**G2-c** defines red to include "(iii) `HUMAN_REVIEW_REQUIRED` for a non-criminal cause" — and
this sweep's own data shows **40** such walks (the table above). `summary.harness_reds == {}`
certifies only the runner's transport-level classification; it says nothing about G2-c's
verdict-content classification, and G2-d ("every red closed inside the mission") is not met by
this PR — those 40 holds are open, owed to A3'/A8-A9 as stated in the review_reasons table.
G2-e holds by construction: every persona is synthetic (`probe_evaluate.py`'s driver-token
idiom), confirmed here by grep (see `## Declared limits`).

**Not proven** (G2-c, B3): this sweep only exercises the engine endpoint over its **edge
covering set**, not the full `72,165,845,568,960`-combination space the manifest itself
reports, and it excludes `review_gate` multi-item combinations by the manifest's own declared
gap. It says nothing about whether the **promoted mouth** renders the same verdict, candidate
set, or review-reason text in its DOM — that is B3's UI-parity runner (Playwright, stratified
sample, against the promoted Vercel deployment), which needs a Zero decision on walk
authorization before it can run (per the conductor's mandate, OD pending). Until B3 runs, "the
live engine returns X" and "the live UI shows X" are two separate claims; only the first is
measured here.

## Declared limits

- This is the **engine half** of G2-b only, over the manifest's edge-covering set (317/317
  edges, 253 walks) — not full combinatorial coverage (`72,165,845,568,960` per the manifest's
  own `walksTotalExact`), and not the UI half (B3, see above). `review_gate` multi-item
  combinations are excluded by the manifest's own declared gap (a duplicate item, or "none"
  combined with another item — `GATE-B1-REPORT-6842.md` Check 4, LOW-7).
- Two health probes with equal `build_sha` bound only the resumed leg's own window
  (2026-09-20T20:51–00:41Z), not the full run history, and cannot rule out a redeploy-and-revert
  between them — see Method for what is actually proven (rule-pack constancy).
- `AGE_BELOW_55`/employer/compensation dead ends are the pack's stated policy, not this
  report's judgment — this report counts them, it does not evaluate them.
- The 41 `HUMAN_REVIEW_REQUIRED` walks are held, not resolved; 40 of 41 wait on A3'/A8-A9 work
  already on PLAN, 1 is criminal-by-design and stays held permanently. Per PLAN's own G2-c red
  definition these 40 are unresolved reds — G2-d is NOT met by this PR (see G2 section above).
- No client data anywhere: the four JSON files below carry synthetic personas only
  (`traffic_source=synthetic_driver`). Confirmed by grep — precisely, not just "zero matches":
  an email-address pattern and a search for a key named
  `email`/`phone`/`passport`/`npwp`/`ktp`/`nik` both return zero hits across all four files; a
  bare `[0-9]{10,}` digit run returns **160 lines**: 148 are the round threshold constant
  `1000000000` (144 as a `value` under `investment.investment_capital_idr` /
  `investment.paid_up_capital_idr` / `investment.investment_amount_usd` /
  `secondhome.bank_deposit_usd` / `secondhome.passive_monthly_income_usd` /
  `secondhome.qualifying_property_value_usd`, 4 as the enumeration edge label
  `edge/investment_amount_usd=1000000000` under both `walk_id` and `label`), 10 are a `uuid5`
  `assessment_id` (5 distinct values, each appearing twice), and 2 are the manifest's own
  `walksTotalExact`. None is applicant-shaped: the amount is one constant repeated identically
  across walks, not a real capital figure. Classified by:

  ```
  $ grep -Ehn '[0-9]{10,}' *.json | sed -E 's/^[0-9]+://; s/^ +//; s/,$//' | sort | uniq -c | sort -rn
   144 "value": 1000000000
     2 "walksTotalExact": 72165845568960
     2 "walk_id": "edge/investment_amount_usd=1000000000"
     2 "label": "edge/investment_amount_usd=1000000000"
     2 "assessment_id": "de42fff9-baff-5c6f-9bd1-590419228296"
     2 "assessment_id": "ca0c4e0e-c3ab-591b-b70e-e8526342957b"
     2 "assessment_id": "ae1d2ad7-ff5f-5d1e-b13e-c22474276960"
     2 "assessment_id": "83475e84-3ca0-5135-af47-033993391374"
     2 "assessment_id": "3c9c8b3c-e8ff-5be8-8c69-0c7118222670"
  ```

  The only `passport`-adjacent strings are the notice enum
  `DISCLOSED_DIPLOMATIC_PASSPORT_CONDITION` and the walk label
  `review-gate/diplomatic_passport` (a scenario name, not a passport number).

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
# PR history for the two enumerator files (path history, origin/main only) — from repo root
git log --oneline origin/main -- \
  apps/backend-rag/backend/scripts/visa_engine/enumerate_live.py \
  apps/mouth/scripts/visa-oracle/enumerate-interview-space.ts

# re-derive verdicts/review_reasons/no_path_reasons/notices/latency from the four JSONs beside
# this README (run from THIS directory, research/operations/2026-09-21-visa-oracle-live-enumeration/)
python3 - <<'PY'
import json
from collections import Counter
d = json.load(open("prove-live-b4-full-sweep-report-20260921.json"))
walks = d["walks"]
print("verdicts:", dict(Counter(w["engine_state"] for w in walks)))
review_reasons, no_path_reasons, notices = Counter(), Counter(), Counter()
for w in walks:
    rc = w["reason_codes"]
    review_reasons.update(rc.get("review_reasons", []))
    no_path_reasons.update(rc.get("no_path_reasons", []))
    notices.update(rc.get("notices", []))
print("review_reasons:", dict(review_reasons))
print("no_path_reasons:", dict(no_path_reasons))
print("notices:", dict(notices))
lat = sorted(w["latency_ms"] for w in walks)
p = lambda pct: lat[__import__("math").ceil(len(lat) * pct) - 1]  # standard nearest-rank
print("p50/p95/max:", round(p(0.5)), round(p(0.95)), round(max(lat)))
PY

# re-run the sweep against the live engine — needs the driver token file, and MUST run as a
# module from apps/backend-rag with PYTHONPATH set to that directory (running the .py file
# directly from repo root with PYTHONPATH=. fails: ModuleNotFoundError: backend).
# --manifest/--report are both required; --max-requests is required with no default (fail-closed).
cd apps/backend-rag
PYTHONPATH=. .venv/bin/python -m backend.scripts.visa_engine.enumerate_live \
  --manifest ../../research/operations/2026-09-21-visa-oracle-live-enumeration/prove-live-b2c-c3-manifest-raw-20260920.json \
  --report /tmp/reproduce-b4-report.json \
  --max-requests 253 --rate-per-minute 25
```

## Adversarial review

Seat: **codex** (`gpt-6-astra`, read-only sandbox, xhigh effort), reviewing this diff against
the four JSONs and the repo directly (`git log`, `gh pr view`/GitHub connector, direct file
reads). Generator ≠ grader: the session that wrote this report cannot be the one to certify it.

Raised 8 findings against the first-committed draft, **all 8 CONFIRMED and fixed in this PR**:

1. **p95 wrong** — the draft's nearest-rank index (`round((n−1)·0.95)`) is not the standard
   nearest-rank definition (`⌈p·n⌉`, 1-indexed); corrected 1341 ms → **1494 ms**, with both
   indices and the divergence from `MANDATE-vo.md`'s own informal reading disclosed rather than
   silently overwritten. p50 273, max 5128, min 195 were already correct.
2. **G2-d does not hold vacuously** — PLAN's own G2-c defines red to include
   `HUMAN_REVIEW_REQUIRED` for a non-criminal cause; this sweep has 40 of those.
   `summary.harness_reds == {}` is the runner's transport classification only. Retracted the
   vacuous-G2-d claim; G2-b rescoped to what the runner's own contract actually shows, plus the
   missing Fly-release-id/Vercel-deployment-id named as owed.
3. **Coverage overstated** — "every path combination" corrected against the manifest's own
   `walksTotalExact` (72,165,845,568,960) and its declared `review_gate` multi-item gap; edge
   coverage (317/317) is proven, combinatorial coverage is not.
4. **Build stability overclaimed** — `health.start` is overwritten on every resume
   (`enumerate_live.py:914`), so the two probes bound only the final 193-walk leg's window, not
   the full 253-walk history, and cannot rule out a redeploy-and-revert between them. Rescoped
   to what is actually proven: rule-pack constancy across all 253 responses.
5. **PII grep report imprecise** — the draft said "zero matches" for the phone-like pattern
   when the actual grep run (allowing separators) had matches, correctly assessed as UUID5
   values but not disclosed as such. Corrected to report the real grep output (a bare
   `[0-9]{10,}` returns 160 lines; each inspected and named by shape) instead of a blanket
   "zero".
6. **Reproduction command not runnable as written** — `PYTHONPATH=.` from the repo root raises
   `ModuleNotFoundError: backend`; the working invocation runs as a module from
   `apps/backend-rag` with `PYTHONPATH=.` set there. Corrected, and verified with `--help`
   (not a live run — a live run would spend production request budget).
7. **429 behavior misdescribed** — the draft lumped HTTP 429 into "stops after 3 consecutive
   harness reds"; the code (`enumerate_live.py:959`) gives 429 its own rule: bounded retries,
   then an immediate stop that never counts toward the 3-consecutive tally. Corrected.
8. **R1 registration** — this section and the `adversarial_review: codex` frontmatter key are
   that registration.

Not raised by the reviewer and independently confirmed: the verdict distribution (173/41/27/12),
every `review_reasons`/`no_path_reasons`/notices count (47/39/64 tags), the #6856+#6970 /
#6952+#6972 PR provenance, the #6861-closed-unmerged and #6920-touches-report_lock-only
correction (checked via the GitHub connector after `gh` was blocked by the sandbox network), the
delta finding's 3-walk diff and its `+0` effect on the G1 ledger, and the manifest/report
`manifest_sha256` digests.
