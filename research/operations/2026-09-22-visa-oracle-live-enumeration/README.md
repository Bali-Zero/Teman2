---
date: 2026-09-22
domain: operations
client_case: none
sources:
  - prove-live-b4-2-full-sweep-report-20260922.json (252/252 walks, live)
  - prove-live-b52-manifest-raw-main-1c6d2240-20260922.json (post-A6-2, post-B5-2 manifest, 252 walks)
discovered_by: session (M5), vo-builder-b4-2-report
---

# Visa Oracle: B4-2 full live-enumeration re-sweep (2026-09-22)

PLAN.md's **Slice B4-2** row (`MANDATE-vo.md`, "B4-2 (delta)" — ruled as a full 252-walk
re-sweep, not a delta). This report and the two JSON files beside it ARE that artefact. Every
number below is re-derived from the JSONs by `scripts/derive_numbers.py` (pasted in the PR
body, not committed here — a one-shot reproduction aid, not product code); none is copied from
the conductor's mandate log.

**B4's records are the live ENGINE's verdicts on fact sets the engine accepts, and every
engine-side finding there stands; what does NOT stand is that a browser could produce 246 of
those requests, so B4 does not satisfy G2 for them. This report replaces B4 for G2 and
supersedes nothing for G1.**

## Why this re-sweep, and against which manifest

Between B4 (2026-09-21) and this sweep, two PRs changed the engine's inputs without changing
the manifest's 252 edge-covering labels: **A6-2** rewrote 7 walk payloads to carry seven
conservative `=unsure` defaults instead of omitted facts (`secondhome_{deposit_usd,own_name,
passive_income_usd,property_value_usd,state_bank}`, `study_{admission_confirmed,
sponsor_confirmed}`), and **B5-2** (#7091, merge commit `1c6d2240044dbd8fb691006019d9762ae6ffb041`)
made the two enumerator scripts importable libraries with no payload effect of its own. The
manifest run against here — `prove-live-b52-manifest-raw-main-1c6d2240-20260922.json` — is the
POST-A6-2, POST-B5-2 emission from that merged head, not the earlier B5-1 anchor: a browser
today produces exactly these 252 requests, which is what G2 asks.

## Run facts

| fact | value |
|---|---|
| `stopped_reason` | `completed` |
| `requests_used_this_run` / `requests_used_total` | 252 / 252 |
| `max_requests` / `rate_per_minute` | 252 / 25.0 |
| window | `2026-09-22T07:27:31.969445+00:00` → `2026-09-22T07:37:38.783180+00:00` (10m06.8s) |
| `health.start.build_sha` | `514151cb7f4a5f26c20b0fbb767ce4bcc96a4bab`, HTTP 200 |
| `health.end.build_sha` | `514151cb7f4a5f26c20b0fbb767ce4bcc96a4bab`, HTTP 200 (equal — same Fly release across the sweep) |
| `manifest_sha256` | `cac14db834bee20184126b5cb9267c1255db8482e3510672ab25e36296125de7` |
| `manifest_walk_count` | 252 |
| rule pack sequence over all 252 responses | `22` on the 251 walks that carry a rule pack (`rule_pack_id 916915d8-1c58-508d-aff7-742a3c012df7`, version `2026.9.16`); 1 walk (`review-gate/blacklist`) carries `rule_pack: null` — see Unexplained observation below |
| `summary.harness_reds` | `{}` |
| retries | 0 across all 252 walks (`attempts == 1` for every walk) |
| HTTP status | 200/252 = 200 |
| latency (standard nearest-rank, `sorted_lat[ceil(n·p) − 1]`, n=252) | p50 273 ms · p95 1350 ms · max 4601 ms · min 203 ms |

Manifest coverage (unchanged from B4/B5-1): `edgesRequired == edgesCovered == 317`,
`edgesMissing == edgesExtra == []`, `bound == PROVEN`, `walksTotalExact == 55234481243760`
(edge coverage, proven, is a much smaller claim than combinatorial coverage — B4's own Declared
limits apply here unchanged).

## Verdict distribution (252/252 walks)

| verdict | count |
|---|---|
| SUPPORTED_CANDIDATES | 172 |
| HUMAN_REVIEW_REQUIRED | 42 |
| NO_SUPPORTED_PATH | 31 |
| NEEDS_INPUT | 6 |
| TEMPORARILY_UNAVAILABLE | 1 |
| **total** | **252** |

## `review_reasons` / `no_path_reasons` / notices (252 walks)

`review_reasons` (48 tags / 42 walks, a walk may carry >1):

| tag | count |
|---|---|
| `DISCLOSED_ACTIVITY_BOUNDARY_REVIEW` | 25 |
| `BRIDGING_ADVERSE_HISTORY` | 11 |
| `BRIDGING_FROM_VISIT_ITK_PROHIBITED` | 3 |
| `BRIDGING_TO_BRIDGING_PROHIBITED` | 3 |
| `SECOND_HOME_BELOW_THRESHOLD_STUDIO` | 2 |
| `BRIDGING_ONSHORE_ONLY` | 1 |
| `CALLING_VISA_REVIEW` | 1 |
| `CITIZENSHIP_LIST_DIVERGENCE` | 1 |
| `DISCLOSED_CRIMINAL_RECORD_REVIEW` | 1 |

`no_path_reasons` (43 tags / 31 walks):

| tag | count |
|---|---|
| `AGE_BELOW_55` | 16 |
| `INDONESIAN_EMPLOYER_NOT_ALLOWED` | 9 |
| `INDONESIAN_SOURCE_COMPENSATION_BANNED` | 7 |
| `LEVEL_BAND_DIKTI` | 4 |
| `BUSINESS_LOCAL_COMPENSATION_NOT_ALLOWED` | 3 |
| `BVK_NATIONALITY_ONLY` | 2 |
| `PAID_ACTIVITY_WITHOUT_INDONESIAN_SPONSOR` | 1 |
| `E33A_SPONSOR_NOT_GOVERNMENT` | 1 |

`notices` (59 tags / 252 walks):

| tag | count |
|---|---|
| `DISCLOSED_UNCERTAINTY_CONDITION` | 48 |
| `DISCLOSED_AMBIGUOUS_SPONSOR_CONDITION` | 3 |
| `DISCLOSED_MULTI_PURPOSE_TRIP_CONDITION` | 1 |
| `DISCLOSED_HEALTH_CONCERN_CONDITION` | 1 |
| `DISCLOSED_PRIOR_VISA_REFUSAL_CONDITION` | 1 |
| `DISCLOSED_PAST_OVERSTAY_CONDITION` | 1 |
| `DISCLOSED_IMMIGRATION_INVESTIGATION_CONDITION` | 1 |
| `DISCLOSED_PEP_OR_SANCTIONS_CONDITION` | 1 |
| `DISCLOSED_SOURCE_OF_FUNDS_CONDITION` | 1 |
| `DISCLOSED_DIPLOMATIC_PASSPORT_CONDITION` | 1 |

## MEASURED comparison table over the 251 labels shared with B4

`B4 count = 253`, `B4-2 count = 252`, `shared = 251`, derived by set intersection over
`walk_id`, never transcribed.

**One new label** (in B4-2, absent from B4): `edge/application_channel=OFFSHORE`.
**Two gone labels** (in B4, absent from B4-2): `edge/application_channel=ONSHORE_CONVERSION`,
`edge/wants_onshore_conversion=no`.

**7 of the 251 shared labels moved state.** 6 are the A6-2 conservative-default effect; 1 is
unrelated and unexplained (named separately below).

| label | B4 state | B4-2 state | cause |
|---|---|---|---|
| `edge/secondhome_deposit_usd=unsure` | NEEDS_INPUT | HUMAN_REVIEW_REQUIRED (`SECOND_HOME_BELOW_THRESHOLD_STUDIO`) | **A6-2** default |
| `edge/secondhome_own_name=unsure` | NEEDS_INPUT | NO_SUPPORTED_PATH (`AGE_BELOW_55`) | **A6-2** default |
| `edge/secondhome_property_value_usd=unsure` | NEEDS_INPUT | HUMAN_REVIEW_REQUIRED (`SECOND_HOME_BELOW_THRESHOLD_STUDIO`) | **A6-2** default |
| `edge/secondhome_state_bank=unsure` | NEEDS_INPUT | NO_SUPPORTED_PATH (`AGE_BELOW_55`) | **A6-2** default |
| `edge/study_admission_confirmed=unsure` | NEEDS_INPUT | NO_SUPPORTED_PATH (`LEVEL_BAND_DIKTI`) | **A6-2** default |
| `edge/study_sponsor_confirmed=unsure` | NEEDS_INPUT | NO_SUPPORTED_PATH (`LEVEL_BAND_DIKTI`) | **A6-2** default |
| `review-gate/blacklist` | HUMAN_REVIEW_REQUIRED (`BRIDGING_ADVERSE_HISTORY`) | TEMPORARILY_UNAVAILABLE | **unexplained** — see below |

`edge/secondhome_passive_income_usd=unsure` is the 7th A6-2 payload delta named in the
conductor's record; it did **not** move state (`NO_SUPPORTED_PATH` in both B4 and B4-2) —
listed here for completeness, not in the moved-rows table above because nothing moved.

All 6 A6-2 rows are the expected effect of the payload change ruled on 2026-09-22T07:24:41Z: a
conservative `=unsure` default that used to leave the fact unasked (`NEEDS_INPUT`,
`DISCLOSED_UNCERTAINTY_CONDITION`) now feeds the engine an explicit value the rule pack can act
on — `SECOND_HOME_BELOW_THRESHOLD_STUDIO` for the two secondhome-value facts,
`AGE_BELOW_55`/`LEVEL_BAND_DIKTI` for the other four. None of these six is a rule-pack change:
same sequence 22 both before and after.

### Unexplained observation: `review-gate/blacklist`

The one non-A6-2 moved row is not caused by A6-2 (which touches only the six secondhome/study
labels above) or by B5-2 (a library-import refactor with no payload effect, confirmed by the
conductor's manifest diff: identical label set, identical `seed`/`edgesRequired`/`edgesCovered`
against the B5-1 anchor). In B4 (2026-09-21) and in B4-2's own manifest, `review-gate/blacklist`
carries the same `disclosed_review_flags` payload that made it `HUMAN_REVIEW_REQUIRED` via
`BRIDGING_ADVERSE_HISTORY` in B4 (see the B4 README's delta finding). In this sweep it returned
`engine_state=TEMPORARILY_UNAVAILABLE`, HTTP 200, `classification=engine_verdict` (the runner
parsed a valid decision envelope — this is not a harness-level transport failure:
`summary.harness_reds == {}`, `retries == 0`, `attempts == 1` for this walk), `rule_pack: null`.
`TEMPORARILY_UNAVAILABLE` is a real, documented engine state
(`backend/services/visa_engine/enums.py:53`, `evaluate_path.py`) used when the engine fails
closed — an unavailable rule pack or a persistence failure on the ENFORCE path
(`evaluate_path.py:1855-2089`) — but `enumerate_live.py`'s walk record has no field for the
envelope's outage detail (checked: the walk object carries only `attempts`,
`attempts_history`, `classification`, `engine_state`, `harness_detail` (`null` here),
`http_status`, `latency_ms`, `reason_codes`, `retries`, `rule_pack`, `timestamp`, `walk_id` —
none of them names *why*). This report cannot say whether it was a transient pack-load hiccup
during the sweep's own window or something that would reproduce on a second live request; it is
named here as an open, unresolved observation, not smoothed into "expected" and not folded into
the A6-2 explanation above.

## Context: no rule pack in production (020/021/022) reads `process.application_channel`

```
$ grep -c "process.application_channel" apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-020.*.json apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-021.*.json apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-022.*.json
apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-020.signed.json:0
apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-020.source.json:0
apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-021.source.json:0
apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-022.signed.json:0
apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-022.source.json:0
```

(No `rulepack-prod-021.signed.json` exists — seq-21 is not signed or activated, per
`test_seq21_pack.py`'s own docstring; the active production pack across all 252 responses is
seq 22, signed.) This is **context only**, for why the distribution above was expected to hold
despite the `application_channel` label churn (one new, two gone) — it explains *why no rule
pack change* could be responsible for a distribution shift, it is **not a substitute for the
252 live observations** above, which are the actual measurement.

## What this proves for PLAN G2, and what it does not

**Proven**: the same committed, rate-limited, resumable live runner posted all 252 edge-covering
walks of the manifest emitted from `origin/main` post-A6-2/post-B5-2 (`1c6d2240`) to the deployed
evaluate endpoint, `traffic_source=synthetic_driver`, a constant Fly release (`build_sha`
identical start/end) and a constant rule pack (sequence 22) across every response that carried
one, zero harness reds, zero retries, 252/252 HTTP 200. This is G2-b for the 252 requests a
browser produces today — B4's engine-side findings (G1, the 40 non-criminal
`HUMAN_REVIEW_REQUIRED` holds owed to A3'/A8-A9) are unchanged and this report does not touch
them.

**Not proven**: same declared scope as B4 — the manifest's edge-covering set (317/317 edges),
not the full `55,234,481,243,760`-combination space; the UI half (B3, a separate runner against
the promoted Vercel deployment) is still not exercised here. The `review-gate/blacklist`
observation above is a new, unresolved item this sweep introduces that B4 did not have.

## Declared limits

- Engine half of G2-b only, over the manifest's edge-covering set — not full combinatorial
  coverage, not the UI half (B3).
- Two health probes with equal `build_sha` bound only that they matched at start and end of
  this window (07:27–07:37Z); they cannot rule out a change-and-revert inside the window.
- The 42 `HUMAN_REVIEW_REQUIRED` walks are held, not resolved — same G1 status as B4's 41 (net
  +1 from the six A6-2 conservative-default rows moving in, minus the one `review-gate/blacklist`
  row moving out to `TEMPORARILY_UNAVAILABLE`, net effect described in the comparison table).
- `review-gate/blacklist`'s `TEMPORARILY_UNAVAILABLE` result is reported, not explained — see
  Unexplained observation above.
- No client data: both JSON files carry synthetic personas only (`traffic_source
  synthetic_driver`). Confirmed by grep: zero matches for an email pattern and for the key
  names `email`/`phone`/`passport`/`npwp`/`ktp`/`nik`; a bare `[0-9]{10,}` digit run returns 81
  lines, all one of the round constant `1000000000` (72, the same investment-amount value
  repeated across walks, not a real capital figure), the manifest's own `walksTotalExact`
  (1), the enumeration edge label `edge/investment_amount_usd=1000000000` under both `walk_id`
  and `label` (2 + 1 = 3), and five `uuid5`-derived `assessment_id` values (5, each appearing
  once, in the manifest).

## Files

- `prove-live-b4-2-full-sweep-report-20260922.json` — the 252-walk report (this README's
  primary source), sha256 `20d429cc8eaf0221382d0c0db6eedc76c2862c80b52b6bfc16b5e437c31dd34e`
  (the B3 v3 U9 source-report anchor).
- `prove-live-b52-manifest-raw-main-1c6d2240-20260922.json` — the manifest the sweep ran
  against (post-A6-2, post-B5-2, emitted from merge commit `1c6d2240`, 252 walks,
  `sha256 9de8c1bf…708d` per the conductor's record).

## Reproduction

```bash
# re-derive verdicts/review_reasons/no_path_reasons/notices/latency/comparison from the JSONs
# beside this README — run from THIS directory
# (research/operations/2026-09-22-visa-oracle-live-enumeration/)
python3 - <<'PY'
import json, math
from collections import Counter

b4 = json.load(open("../2026-09-21-visa-oracle-live-enumeration/prove-live-b4-full-sweep-report-20260921.json"))
b42 = json.load(open("prove-live-b4-2-full-sweep-report-20260922.json"))

b4_walks = {w["walk_id"]: w for w in b4["walks"]}
b42_walks = {w["walk_id"]: w for w in b42["walks"]}
shared = set(b4_walks) & set(b42_walks)

print("B4:", len(b4_walks), "B4-2:", len(b42_walks), "shared:", len(shared))
print("new in B4-2:", sorted(set(b42_walks) - set(b4_walks)))
print("gone from B4:", sorted(set(b4_walks) - set(b42_walks)))

dist = Counter(w["engine_state"] for w in b42["walks"])
print("verdicts:", dict(dist))

lat = sorted(w["latency_ms"] for w in b42["walks"])
n = len(lat)
p = lambda pct: lat[math.ceil(n * pct) - 1]
print("p50/p95/max/min:", round(p(0.5)), round(p(0.95)), round(max(lat)), round(min(lat)))

moved = [(l, b4_walks[l]["engine_state"], b42_walks[l]["engine_state"])
         for l in sorted(shared) if b4_walks[l]["engine_state"] != b42_walks[l]["engine_state"]]
print("moved rows:", moved)
PY

# B3 v3 U9 anchor, printed by command
sha256sum prove-live-b4-2-full-sweep-report-20260922.json
python3 -c "import json; print(len({w['walk_id'] for w in json.load(open('prove-live-b4-2-full-sweep-report-20260922.json'))['walks']}))"

# re-run a live sweep — needs the driver token file, fail-closed (--max-requests required)
cd ../../../apps/backend-rag
PYTHONPATH=. .venv/bin/python -m backend.scripts.visa_engine.enumerate_live \
  --manifest ../../research/operations/2026-09-22-visa-oracle-live-enumeration/prove-live-b52-manifest-raw-main-1c6d2240-20260922.json \
  --report /tmp/reproduce-b4-2-report.json \
  --max-requests 252 --rate-per-minute 25
```
