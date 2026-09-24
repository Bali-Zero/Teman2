---
date: 2026-09-22
domain: operations
client_case: none
sources:
  - prove-live-b4-2-full-sweep-report-20260922.json (252/252 walks, live)
  - prove-live-b52-manifest-raw-main-1c6d2240-20260922.json (post-A6-2, post-B5-2 manifest, 252 walks)
  - prove-live-a9-seq23-full-sweep-report-20260924.json (252/252 walks, live, post-seq-23-activation re-sweep against the same manifest)
  - prove-live-b4-3-a3pb-full-sweep-report-20260924.json (252/252 walks, live, post-#7234/Slice-A3'-B re-sweep against the same manifest)
discovered_by: session (M5), vo-builder-b4-2-report
adversarial_review: codex
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
the manifest's 252 edge-covering labels: **A6-2** rewrote 7 walk payloads' fact values for
`secondhome_{deposit_usd,own_name,passive_income_usd,property_value_usd,state_bank}`,
`study_{admission_confirmed,sponsor_confirmed}` — the underlying fact was already present in
each walk's `asked` list and carried `status: UNKNOWN, reason: UNVERIFIED` before A6-2 (verified
against the pre-A6-2 manifest: `secondhome.bank_deposit_usd` on
`edge/secondhome_deposit_usd=unsure`), not an omitted/unasked question; A6-2 replaced that
`UNKNOWN/UNVERIFIED` status with an explicit conservative `KNOWN` value (`0`/`false`) the engine
can act on. **B5-2** (#7091, merge commit `1c6d2240044dbd8fb691006019d9762ae6ffb041`)
made the two enumerator scripts importable libraries with no payload effect of its own. The
manifest run against here — `prove-live-b52-manifest-raw-main-1c6d2240-20260922.json` — is the
POST-A6-2, POST-B5-2 emission from that merged head, not the earlier B5-1 anchor: a browser
today produces exactly these 252 requests, which is what G2 asks.

## Run facts

**Corrected by B4-2b commit 3 (gate findings H1-H3/M1-M2):** the runner's report keeps ONE
top-level run-facts block, not a history — B4-2b's single-request resume OVERWROTE the full
sweep's own `requests_used_this_run`, `max_requests`, `max_consecutive_harness_reds`,
`finished_at` and `health.{start,end}.build_sha` with the resume's own values. The table below
therefore states BOTH runs explicitly: "Full sweep (B4-2)" is re-derived from the pre-B4-2b blob
(`f47d773361`, the commit before this PR's first commit), "Resume (B4-2b)" from the JSON as
committed here. A run HISTORY (so a resumed report can state both without reaching into git) is
a runner follow-up, not built in this PR — named here as a future slice, tentatively B4-3b.

| fact | Full sweep (B4-2, `f47d773361`) | Resume (B4-2b, this file) |
|---|---|---|
| `stopped_reason` | `completed` | `completed` |
| `requests_used_this_run` | 252 | **1** |
| `requests_used_total` (end of that run) | 252 | **253** |
| `max_requests` | 252 | **1** |
| `max_consecutive_harness_reds` | 3 | **1** |
| `rate_per_minute` | 25.0 | 25.0 |
| `started_at` | `2026-09-22T07:27:31.969445+00:00` | `2026-09-22T07:27:31.969445+00:00` (unchanged — the report's one `started_at` field was never touched by the resume) |
| `finished_at` | `2026-09-22T07:37:38.783180+00:00` (10m06.8s after `started_at`) | **`2026-09-22T12:01:10.480307+00:00`** (the resume's own finish, ~4h23m after the full sweep) |
| `health.start.build_sha` | `514151cb7f4a5f26c20b0fbb767ce4bcc96a4bab`, HTTP 200 | **`0b636b5867f7325f6158e8c75ee0076c15f15060`**, HTTP 200 (the resume's own probe, not the full sweep's) |
| `health.end.build_sha` | `514151cb7f4a5f26c20b0fbb767ce4bcc96a4bab`, HTTP 200 (equal to start — same Fly release across the full sweep) | **`0b636b5867f7325f6158e8c75ee0076c15f15060`**, HTTP 200 (equal to start — same Fly release across the resume; this build carries B4-3, the outage-recording slice) |

cwd: `research/operations/2026-09-22-visa-oracle-live-enumeration`

```
$ git show f47d773361efcd35560db641f5b17b9d2a373118:research/operations/2026-09-22-visa-oracle-live-enumeration/prove-live-b4-2-full-sweep-report-20260922.json | python3 -c "import json,sys; d=json.load(sys.stdin); print('requests_used_this_run', d['requests_used_this_run']); print('requests_used_total', d['requests_used_total']); print('max_requests', d['max_requests']); print('max_consecutive_harness_reds', d['max_consecutive_harness_reds']); print('started_at', d['started_at']); print('finished_at', d['finished_at']); print('health', d['health'])"
requests_used_this_run 252
requests_used_total 252
max_requests 252
max_consecutive_harness_reds 3
started_at 2026-09-22T07:27:31.969445+00:00
finished_at 2026-09-22T07:37:38.783180+00:00
health {'end': {'build_sha': '514151cb7f4a5f26c20b0fbb767ce4bcc96a4bab', 'http_status': 200}, 'probes_outside_budget': 2, 'start': {'build_sha': '514151cb7f4a5f26c20b0fbb767ce4bcc96a4bab', 'http_status': 200}}
```

| fact | value |
|---|---|
| `manifest_sha256` | `cac14db834bee20184126b5cb9267c1255db8482e3510672ab25e36296125de7` |
| `manifest_walk_count` | 252 |
| rule pack sequence over all 252 responses | `22` on **252/252** walks (`rule_pack_id 916915d8-1c58-508d-aff7-742a3c012df7`, version `2026.9.16`); **zero** `rule_pack: null` after B4-2b — `review-gate/blacklist` carried the report's only `null` pack before the re-sweep, and now carries pack 22 like every other row (see Unexplained observation below for the row's own history) |
| `summary.harness_reds` | `{}` |
| retries | 0 across all 252 walks (`attempts == 1` for every walk) |
| HTTP status | 200/252 = 200 |
| latency (standard nearest-rank, `sorted_lat[ceil(n·p) − 1]`, n=252) | p50 273 ms · p95 1350 ms · max 4601 ms · min 203 ms |

Manifest edge coverage (unchanged from B4/B5-1): `edgesRequired == edgesCovered == 317`,
`edgesMissing == edgesExtra == []`, `bound == PROVEN`. **Not unchanged:** `walksTotalExact ==
55234481243760`, DOWN from B4's `72165845568960` — the combinatorial space shrank because the
`application_channel` label churn (one new value, two gone, see the comparison table below)
changes the tree's branching, not because anything was newly excluded. Edge coverage (proven, a
much smaller claim than combinatorial coverage) is unchanged; the combinatorial total is not —
B4's own Declared limits on what edge coverage does/does not prove still apply.

## Verdict distribution (252/252 walks)

| verdict | count |
|---|---|
| SUPPORTED_CANDIDATES | 172 |
| HUMAN_REVIEW_REQUIRED | 43 |
| NO_SUPPORTED_PATH | 31 |
| NEEDS_INPUT | 6 |
| TEMPORARILY_UNAVAILABLE | 0 |
| **total** | **252** |

**B4-2b re-sweep 2026-09-22T12:01Z, one request:** `review-gate/blacklist` re-POSTed alone
(TEMPORARILY_UNAVAILABLE 1 → 0, HUMAN_REVIEW_REQUIRED 42 → 43) — see Unexplained observation
below.

## `review_reasons` / `no_path_reasons` / notices (252 walks)

`review_reasons` (49 tags / 43 walks, a walk may carry >1 — updated by B4-2b: `review-gate/blacklist`
re-swept back into `HUMAN_REVIEW_REQUIRED` adds one `BRIDGING_ADVERSE_HISTORY`, 11 → 12):

| tag | count |
|---|---|
| `DISCLOSED_ACTIVITY_BOUNDARY_REVIEW` | 25 |
| `BRIDGING_ADVERSE_HISTORY` | 12 |
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

`notices` (60 tags / 252 walks — the 252 denominator is the report's own walk count, accepted as
L3 in `GATE-B4-2-REPORT-7120.md`'s re-check against the smaller notice-carrying-walk count;
updated by B4-2b: `review-gate/blacklist`'s re-swept row adds one
`DISCLOSED_BLACKLIST_ENTRY_CONDITION`, previously absent):

| tag | count |
|---|---|
| `DISCLOSED_UNCERTAINTY_CONDITION` | 48 |
| `DISCLOSED_AMBIGUOUS_SPONSOR_CONDITION` | 3 |
| `DISCLOSED_MULTI_PURPOSE_TRIP_CONDITION` | 1 |
| `DISCLOSED_HEALTH_CONCERN_CONDITION` | 1 |
| `DISCLOSED_PRIOR_VISA_REFUSAL_CONDITION` | 1 |
| `DISCLOSED_PAST_OVERSTAY_CONDITION` | 1 |
| `DISCLOSED_BLACKLIST_ENTRY_CONDITION` | 1 |
| `DISCLOSED_IMMIGRATION_INVESTIGATION_CONDITION` | 1 |
| `DISCLOSED_PEP_OR_SANCTIONS_CONDITION` | 1 |
| `DISCLOSED_SOURCE_OF_FUNDS_CONDITION` | 1 |
| `DISCLOSED_DIPLOMATIC_PASSPORT_CONDITION` | 1 |

## The 6 NEEDS_INPUT walks, named

The mechanical part — walk_id, HTTP status, latency, notices, and the `guardian_consent`
occurrence count — by script, not prose:

```
$ python3 -c "
import json
d = json.load(open('prove-live-b4-2-full-sweep-report-20260922.json'))
ni = [w for w in d['walks'] if w['engine_state']=='NEEDS_INPUT']
print('NEEDS_INPUT walk count:', len(ni))
for w in ni:
    print(w['walk_id'], '| http', w['http_status'], '| latency_ms', w['latency_ms'], '| notices', w['reason_codes']['notices'])
print()
print('guardian_consent occurrences in report JSON:', open('prove-live-b4-2-full-sweep-report-20260922.json').read().count('guardian_consent'))
print('guardian_consent occurrences in manifest JSON:', open('prove-live-b52-manifest-raw-main-1c6d2240-20260922.json').read().count('guardian_consent'))
"
NEEDS_INPUT walk count: 6
edge/birth_date=unsure | http 200 | latency_ms 303.99 | notices ['DISCLOSED_UNCERTAINTY_CONDITION']
edge/category=unsure | http 200 | latency_ms 219.79 | notices ['DISCLOSED_UNCERTAINTY_CONDITION']
edge/overstay_days=unsure | http 200 | latency_ms 261.76 | notices ['DISCLOSED_UNCERTAINTY_CONDITION']
edge/secondhome_basis=unsure | http 200 | latency_ms 240.3 | notices ['DISCLOSED_UNCERTAINTY_CONDITION']
edge/stay_days=unsure | http 200 | latency_ms 258.42 | notices ['DISCLOSED_UNCERTAINTY_CONDITION']
edge/work_indonesia_compensation=unsure | http 200 | latency_ms 268.87 | notices ['DISCLOSED_UNCERTAINTY_CONDITION']

guardian_consent occurrences in report JSON: 0
guardian_consent occurrences in manifest JSON: 0
```

The non-mechanical part — WHICH fact each walk targets — cannot come from a script alone: the
API's own `missing_facts` field is not captured by this runner (next paragraph), so naming the
target requires reading the mouth's fact-construction source, cited by file:line below, not
guessed from the label's naming convention.

`enumerate_live.py`'s `_reason_codes()` (`enumerate_live.py:505-513`) extracts only
`review_reasons`/`no_path_reasons`/`notices` from the engine's response — it does **not**
capture the API's own `missing_facts` field (a real field, required non-empty for
`NEEDS_INPUT` by `backend/services/visa_engine/models.py:1466,1527-1529`). No committed JSON in this
PR carries it, and re-running the live sweep to fetch it is out of scope here. What follows is
NOT that field — it is independently derived from the **manifest's own construction**.
**Correction (second adversarial-review pass):** `asked` holds question IDs, some of which are
pure routing questions with no standalone engine fact/status at all (e.g. `trip_scope`,
`review_gate`) — the earlier framing that every `asked` entry has "a status" overstated this.
The narrower, verified claim: for 5 of the 6 walks, exactly one **engine fact** (a path that
actually appears in the walk's `facts` payload) is `UNKNOWN` while the walk's scenario-relevant
facts are all `KNOWN`, and that one fact is the walk's deliberate target — verified against
`apps/mouth/.../_lib/fact-mapper.ts`'s literal mapping from the raw `OracleFacts` field the
label names to the `ApplicantFactsWire` path the engine receives, not guessed from naming
convention. Latencies below are rounded to the nearest ms; exact values are in the JSON
(303.99 / 219.79 / 261.76 / 258.42 / 268.87 / 240.30):

| walk_id | HTTP / latency | notices | target fact (verified in fact-mapper.ts) | status |
|---|---|---|---|---|
| `edge/birth_date=unsure` | 200 / ~304 ms | `DISCLOSED_UNCERTAINTY_CONDITION` | `person.birth_date` (`dateFact(facts.birth_date)`, line 922) | UNKNOWN/UNVERIFIED |
| `edge/category=unsure` | 200 / ~220 ms | `DISCLOSED_UNCERTAINTY_CONDITION` | `intent.purposes` (`mapPurposes`, lines 314-317: `facts.category === "unsure"` → `unknownFact(UNVERIFIED)`; assigned to the wire at line 950) | UNKNOWN/UNVERIFIED |
| `edge/overstay_days=unsure` | 200 / ~262 ms | `DISCLOSED_UNCERTAINTY_CONDITION` | `immigration.overstay_days` (lines 937-940: `integerFact(facts.overstay_days, 0, 36500)` when `in_indonesia != "no"`) | UNKNOWN/UNVERIFIED |
| `edge/stay_days=unsure` | 200 / ~258 ms | `DISCLOSED_UNCERTAINTY_CONDITION` | `intent.stay_days` (`mapStayDays`, lines 367-368, `integerFact(facts.stay_days, 1, 36500)`; assigned at line 951) | UNKNOWN/UNVERIFIED |
| `edge/work_indonesia_compensation=unsure` | 200 / ~269 ms | `DISCLOSED_UNCERTAINTY_CONDITION` | `work.indonesia_source_compensation` (`pairedBooleanFact`, lines 150-157; assigned at lines 960-963) | UNKNOWN/UNVERIFIED |
| `edge/secondhome_basis=unsure` | 200 / ~240 ms | `DISCLOSED_UNCERTAINTY_CONDITION` | **no single fact** — see below | UNKNOWN/NOT_ASKED (×4) |

`secondhome_basis` is not itself an engine fact path — it is a mouth-side routing input.
**Correction (second adversarial-review pass):** the earlier text cited `fact-mapper.ts`'s
`depositBasisDecisivelyNotChosen`/`propertyBasisDecisivelyNotChosen` guards as the gating
mechanism; those guards only supply a **conservative fallback VALUE** for a fact that was
already not asked — the actual question-SELECTION logic lives in `flow.ts` (~lines 978-989):
when `category === "second_home"`, the four sub-questions
(`secondhome_deposit_usd`/`secondhome_state_bank`/`secondhome_own_name` if `secondhome_basis ===
"bank_deposit"`, or `secondhome_property_value_usd` if `=== "property"`) are only added to the
question list for the CHOSEN branch — when `secondhome_basis` is `"unsure"` (neither branch),
`branchQuestions` is empty and NONE of the four are ever asked. The two monetary facts
(`secondhome.bank_deposit_usd`, `secondhome.qualifying_property_value_usd`) then fall through
`integerFact(undefined, ...)` → `unknownFact(NOT_ASKED)` (fact-mapper.ts:89); the two boolean
facts (`secondhome.bank_deposit_at_state_bank`, `secondhome.bank_deposit_in_own_name`) fall
through `booleanFact(undefined, ...)` → `unknownFact(NOT_ASKED)` (fact-mapper.ts:71-72) — the
guard functions never even run their `depositBasisDecisivelyNotChosen`/
`propertyBasisDecisivelyNotChosen` check in this specific case, since neither branch condition
they gate on (`"bank_deposit"`/`"property"`) is met either. Confirmed directly in this walk's
own manifest payload: `secondhome.bank_deposit_usd`, `secondhome.bank_deposit_at_state_bank`,
`secondhome.bank_deposit_in_own_name`, and `secondhome.qualifying_property_value_usd` are all
`{status: UNKNOWN, reason: NOT_ASKED}`. This is the one walk of the six where "the missing
fact" is not a single leaf value.

**`person.guardian_consent`**: zero occurrences of the string `guardian_consent` anywhere in
either committed JSON (`grep -c` both files → 0/0), and it is not one of the 56 distinct fact
paths that appear anywhere across all 252 walks' `facts` payloads in the manifest. Consistent
with A7-B not being merged into this head — none of the 6 NEEDS_INPUT walks (or any of the 252)
could name it, because the manifest's own schema does not carry that fact path at all yet.

## MEASURED comparison table over the 251 labels shared with B4

`B4 count = 253`, `B4-2 count = 252`, `shared = 251`, derived by set intersection over
`walk_id`, never transcribed.

**One new label** (in B4-2, absent from B4): `edge/application_channel=OFFSHORE`.
**Two gone labels** (in B4, absent from B4-2): `edge/application_channel=ONSHORE_CONVERSION`,
`edge/wants_onshore_conversion=no`.

**6 of the 251 shared labels moved state, all the A6-2 conservative-default effect.**
`review-gate/blacklist` is no longer a moved row after the B4-2b re-sweep (see Unexplained
observation below): it is `HUMAN_REVIEW_REQUIRED` via `BRIDGING_ADVERSE_HISTORY` in both B4 and
B4-2.

| label | B4 state | B4-2 state | cause |
|---|---|---|---|
| `edge/secondhome_deposit_usd=unsure` | NEEDS_INPUT | HUMAN_REVIEW_REQUIRED (`SECOND_HOME_BELOW_THRESHOLD_STUDIO`) | **A6-2** default |
| `edge/secondhome_own_name=unsure` | NEEDS_INPUT | NO_SUPPORTED_PATH (`AGE_BELOW_55`) | **A6-2** default |
| `edge/secondhome_property_value_usd=unsure` | NEEDS_INPUT | HUMAN_REVIEW_REQUIRED (`SECOND_HOME_BELOW_THRESHOLD_STUDIO`) | **A6-2** default |
| `edge/secondhome_state_bank=unsure` | NEEDS_INPUT | NO_SUPPORTED_PATH (`AGE_BELOW_55`) | **A6-2** default |
| `edge/study_admission_confirmed=unsure` | NEEDS_INPUT | NO_SUPPORTED_PATH (`LEVEL_BAND_DIKTI`) | **A6-2** default |
| `edge/study_sponsor_confirmed=unsure` | NEEDS_INPUT | NO_SUPPORTED_PATH (`LEVEL_BAND_DIKTI`) | **A6-2** default |

`edge/secondhome_passive_income_usd=unsure` is the 7th A6-2 payload delta named in the
conductor's record; it did **not** move state (`NO_SUPPORTED_PATH` in both B4 and B4-2) —
listed here for completeness, not in the moved-rows table above because nothing moved.

All 6 moved A6-2 rows are the expected effect of the payload change (per the conductor's record
at 2026-09-22T07:24:41Z in `MANDATE-vo.md`; this timestamp and label are cited from that record,
not re-derived from the JSONs, since they are provenance metadata rather than counts): a
conservative default that used to leave the fact `UNKNOWN/UNVERIFIED` (`NEEDS_INPUT`,
`DISCLOSED_UNCERTAINTY_CONDITION`) now feeds the engine an explicit `KNOWN` value the rule pack
can act on — **2 of the 6** move to `HUMAN_REVIEW_REQUIRED` via `SECOND_HOME_BELOW_THRESHOLD_STUDIO`
(`secondhome_deposit_usd`, `secondhome_property_value_usd`), **4 of the 6** move to
`NO_SUPPORTED_PATH` via `AGE_BELOW_55` (`secondhome_own_name`, `secondhome_state_bank`) or
`LEVEL_BAND_DIKTI` (`study_admission_confirmed`, `study_sponsor_confirmed`). None of these six is
a rule-pack change: same sequence 22 both before and after. A6-2 changed 7 payloads in total —
these 6 plus `secondhome_passive_income_usd`, which did not move (see below) — so "six" above
refers to the moved subset of A6-2's seven changes, not a different count of what A6-2 touched.

### Unexplained observation: `review-gate/blacklist`

B4 had zero `TEMPORARILY_UNAVAILABLE` walks; this sweep has exactly one. Its full record, every
field the runner's schema carries (verified: the union of keys across all 252 walk records in
this report is exactly `attempts`, `attempts_history`, `classification`, `engine_state`,
`harness_detail`, `http_status`, `latency_ms`, `reason_codes` (itself exactly
`no_path_reasons`/`notices`/`review_reasons`), `retries`, `rule_pack`, `timestamp`, `walk_id` —
**no `retry_after` or `message` field exists anywhere in the report's schema**, not just on this
walk):

| field | value |
|---|---|
| `walk_id` / label | `review-gate/blacklist` |
| `engine_state` | `TEMPORARILY_UNAVAILABLE` |
| `classification` | `engine_verdict` — the runner counted this as a genuine engine verdict, not a harness-level transport failure |
| `http_status` | 200 |
| `latency_ms` | 2079.53 |
| `attempts` / `retries` | 1 / 0 |
| `reason_codes.review_reasons` | `[]` |
| `reason_codes.no_path_reasons` | `[]` |
| `reason_codes.notices` | `[]` |
| `rule_pack` | `null` |
| `harness_detail` | `null` |
| `attempts_history` | one element, byte-identical to this record's own top-level fields (single attempt, nothing retried) |
| `timestamp` | `2026-09-22T07:37:23.268086+00:00` |
| B4 state for this same label | `HUMAN_REVIEW_REQUIRED` via `BRIDGING_ADVERSE_HISTORY` (see below) |

**Two corrections (second adversarial-review pass) to what "engine_verdict" and "no explanatory
code" actually mean here:**

1. `enumerate_live.py`'s classification logic (`enumerate_live.py:654-672`) checks exactly three
   things before labelling a response `engine_verdict`: HTTP status is 200, the body parses as
   JSON, and its `decision` key is a mapping. It does **not** validate the decision against the
   server's own Pydantic schema. `classification=engine_verdict` therefore means "the runner's
   own transport-level checks passed" (which is what makes `summary.harness_reds == {}`
   accurate — no 5xx/timeout/connection-error/invalid-body harness red occurred), not an
   independent confirmation that the envelope conforms to every schema rule
   `backend/services/visa_engine/models.py` enforces server-side.
2. The server's `TEMPORARILY_UNAVAILABLE` envelope **does** carry an explanatory code — the
   builder sets `"outage": {"code": code, "retryable": True}` (`evaluate_path.py:637`,
   inside the `608-...` envelope function). The report does not lack this field because the
   server omitted it; `enumerate_live.py`'s `_reason_codes()` (`enumerate_live.py:505-513`)
   only extracts `review_reasons`/`no_path_reasons`/`notices` from the decision body and never
   reads `outage` at all, so the code the server sent is discarded before it reaches this
   report. The record alone therefore cannot say what `code` was — that would need the
   production server logs for this exact request (not reproducible from this report) or a
   fresh, separate live request, which this PR does not make. Routed here as a finding, not
   resolved: it cannot distinguish an engine-side transient (a momentary rule-pack load hiccup,
   a persistence-layer fail-closed on the ENFORCE path, `evaluate_path.py:1855-1858,2027-2032`)
   from a pack/adapter code path that answers "unavailable" for a fact set a real UI visitor
   could equally submit.

Routed by the conductor as finding B4-3 (single diagnostic re-POST reading
`decision.outage.code`; runner to record `outage`).

The one non-A6-2 moved row is not caused by A6-2 (whose 7 payload changes are all under the
`secondhome_*`/`study_*` labels above — `review-gate/blacklist` is not one of them) or by B5-2
(a library-import refactor with no payload effect, confirmed by the conductor's manifest diff:
identical label set, identical `seed`/`edgesRequired`/`edgesCovered` against the B5-1 anchor).
**Correction against a first draft of this section (caught by adversarial review):** the first
draft claimed `review-gate/blacklist` "carries the same `disclosed_review_flags` payload" in B4
and B4-2 — false. The B4 report entry this README's comparison table uses
(`prove-live-b4-full-sweep-report-20260921.json`, timestamp `2026-09-21T00:41:18Z`, inside the
resumed leg's own window) predates A3-M's `disclosed_review_flags` mapping: its source manifest
(the C3 manifest, pre-A3-M) carries no `disclosed_review_flags` for this walk at all. B4 held it
`HUMAN_REVIEW_REQUIRED` via `BRIDGING_ADVERSE_HISTORY` anyway, because that rule reads
`immigration.violation_history` (`["BLACKLIST"]` on this walk), independent of the flag — exactly
as the B4 README's own delta finding states for its separate 3-walk delta re-sweep. B4-2's
manifest (post-A3-M, since A3-M long predates A6-2/B5-2) DOES carry
`disclosed_review_flags: ["BLACKLIST_ENTRY"]` on this walk — verified directly in
`prove-live-b52-manifest-raw-main-1c6d2240-20260922.json` — but that flag plays no role in
`BRIDGING_ADVERSE_HISTORY` either. So the two reports' payloads are not "the same" (B4's source
manifest lacked the flag; B4-2's carries it), and neither payload's flag is what explains this
row's move — `violation_history` is present and identical in kind in both, and is not what
changed. In this sweep the walk returned `engine_state=TEMPORARILY_UNAVAILABLE`, HTTP 200,
`classification=engine_verdict` (the runner parsed a valid decision envelope — this is not a
harness-level transport failure: `summary.harness_reds == {}`, `retries == 0`, `attempts == 1`
for this walk), `rule_pack: null`.
`TEMPORARILY_UNAVAILABLE` is a real, documented engine state
(`backend/services/visa_engine/enums.py:53`, `evaluate_path.py`) used when the engine fails
closed — an unavailable rule pack or a persistence failure on the ENFORCE path
(`evaluate_path.py:1855-2089`) — but at the time of this 07:37Z observation `enumerate_live.py`'s
walk record had no field for the envelope's outage detail (checked: the walk object carried only
`attempts`, `attempts_history`, `classification`, `engine_state`, `harness_detail` (`null` here),
`http_status`, `latency_ms`, `reason_codes`, `retries`, `rule_pack`, `timestamp`, `walk_id` —
none of them names *why*). **This list is no longer exhaustive for the report as a whole after
B4-2b**: the 251 untouched sweep rows still carry only those twelve keys, but the re-swept
`review-gate/blacklist` row also carries `outage` (see the B4-2b re-sweep paragraph below). This
report cannot say whether the 07:37Z occurrence was a transient pack-load hiccup
during the sweep's own window or something that would reproduce on a second live request; it is
named here as an open, unresolved observation, not smoothed into "expected" and not folded into
the A6-2 explanation above.

**B4-2b re-sweep (2026-09-22T12:01:10Z, single walk, runner at `0b636b5867` — B4-3, the
outage-recording slice):** `review-gate/blacklist` re-POSTed alone, one request
(`requests_used_this_run=1`, `requests_used_total 252 → 253`). The row now reads
`engine_state=HUMAN_REVIEW_REQUIRED`, HTTP 200, latency 2715.29 ms, `rule_pack` sequence 22
(`916915d8-1c58-508d-aff7-742a3c012df7`, version `2026.9.16`), `reason_codes.review_reasons
["BRIDGING_ADVERSE_HISTORY"]`, `reason_codes.notices ["DISCLOSED_BLACKLIST_ENTRY_CONDITION"]`,
and — the first row in this report to carry the key at all (1/252 rows) — **`outage: null`**.
The resumed report keeps `report_version 2` with mixed rows (251 written before B4-3 landed,
without the key; 1 written after, with it) exactly as the B4-3 CHANGELOG comment declares for a
version bump read against an older-shaped report. The 07:37Z `TEMPORARILY_UNAVAILABLE`
occurrence recorded above **stays transient and unexplained** — this re-sweep did not reproduce
it and cannot say what caused it — but the runner that would observe a second occurrence now
records `outage` verbatim, so a repeat would name a cause where this one could not.

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
evaluate endpoint, `traffic_source=synthetic_driver`, matching start/end `build_sha` (bounded to
this run's own window — see Declared limits for what two probes do and do not prove) and a
constant rule pack (sequence 22) across every response that carried one, zero harness reds, zero
retries, 252/252 HTTP 200. This is G2-b for the 252 requests the manifest represents — B5-2
proved the manifest is produced by a top-level library import of the same enumerator a browser
runs, which is why these are the requests a browser would produce today, not a claim that this
sweep itself drove a browser. B4's engine-side findings (G1) are not superseded by this report;
this sweep's own `HUMAN_REVIEW_REQUIRED` count is 43 (42 non-criminal + 1 criminal-by-design,
updated by B4-2b), not B4's 41 (40 non-criminal + 1) — see Declared limits for the arithmetic.

**Not proven**: same declared scope as B4 — the manifest's edge-covering set (317/317 edges),
not the full `55,234,481,243,760`-combination space; the UI half (B3, a separate runner against
the promoted Vercel deployment) is still not exercised here. The `review-gate/blacklist`
observation above is a new, unresolved item this sweep introduces that B4 did not have.

## Declared limits

- Engine half of G2-b only, over the manifest's edge-covering set — not full combinatorial
  coverage, not the UI half (B3).
- Two health probes with equal `build_sha` bound only that they matched at start and end of the
  probed window — for the 251 untouched rows that is the full sweep's own window (07:27–07:37Z,
  `build_sha 514151cb…`); they cannot rule out a change-and-revert inside it. The re-swept
  `review-gate/blacklist` row was probed separately, in its own window (12:01Z, `build_sha
  0b636b58…` — see Run facts above for both runs' health blocks).
- The 43 `HUMAN_REVIEW_REQUIRED` walks are held, not resolved — same G1 status as B4's 41.
  **Arithmetic updated by B4-2b** (the pre-B4-2b sweep's `41 + 2 − 1 = 42` no longer holds, since
  `review-gate/blacklist` was that "− 1" and it no longer moves out): only **2** of the 6 A6-2
  rows move INTO `HUMAN_REVIEW_REQUIRED` (`secondhome_deposit_usd`,
  `secondhome_property_value_usd`, via `SECOND_HOME_BELOW_THRESHOLD_STUDIO`); the other 4 move
  into `NO_SUPPORTED_PATH`. `review-gate/blacklist` is `HUMAN_REVIEW_REQUIRED` in both B4 and
  B4-2b (see the MEASURED comparison table above), so it contributes to B4's 41 already and adds
  no separate delta term. `41 + 2 = 43`. Of the 43, 1 is `DISCLOSED_CRIMINAL_RECORD_REVIEW`
  (criminal-by-design, same as B4) and **42** are non-criminal holds owed to A3'/A8-A9 — not
  B4's 40; B4's 40 describes B4's own sweep only.
- `review-gate/blacklist`'s `TEMPORARILY_UNAVAILABLE` result from the original sweep is reported,
  not explained, and stays unexplained after the B4-2b re-sweep — see Unexplained observation
  above for the closing paragraph (the re-swept row itself is now `HUMAN_REVIEW_REQUIRED`, no
  longer a `HUMAN_REVIEW_REQUIRED` vs. G1-held ambiguity).
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
  primary source), sha256 `49f0144323e1a1229992d57f8d8dbf2753f6d7a351b28e4254eefea6e57f8ac9`
  (post-B4-2b: the `review-gate/blacklist` row re-swept, `outage` key added, `requests_used_total
  252 → 253`; the prior sha `20d429cc8eaf0221382d0c0db6eedc76c2862c80b52b6bfc16b5e437c31dd34e`
  was the pre-B4-2b file), printed by the `sha256sum` command below. The "B3 v3 U9 source-report
  anchor" designation is the ratified `### Slice B3 v3` text in `MANDATE-vo.md` naming THIS
  report as that anchor — a provenance label from the mandate record, not a value derivable from
  the JSON itself; the hash next to it is independently computed here, not copied from that
  record. B3 v3's U9 re-pins to this B4-2b sha (conductor record 2026-09-22T12:02:13Z).
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

review_reasons, no_path_reasons, notices = Counter(), Counter(), Counter()
for w in b42["walks"]:
    rc = w["reason_codes"]
    review_reasons.update(rc.get("review_reasons", []))
    no_path_reasons.update(rc.get("no_path_reasons", []))
    notices.update(rc.get("notices", []))
print("review_reasons:", dict(review_reasons), "sum:", sum(review_reasons.values()))
print("no_path_reasons:", dict(no_path_reasons), "sum:", sum(no_path_reasons.values()))
print("notices:", dict(notices), "sum:", sum(notices.values()))

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

## Adversarial review

Seat: **codex** (`gpt-6-astra`, read-only sandbox, xhigh effort), reviewing the committed README
against the two JSON files directly (not a git diff against `main`, which in this worktree pulls
in ~483 unrelated files from other merged slices and would have wasted the reviewer's budget on
noise instead of this artefact). Generator ≠ grader: the session that wrote this report cannot
certify it.

Verdict: **MEDIUM**. Raised 8 findings against the first-committed draft; all 8 disposed of in
this text (1 MEDIUM confirmed and fixed, 5 LOW confirmed and fixed, 2 notes on provenance
sourcing addressed by clarification rather than correction, since the underlying facts were
already accurately labelled as coming from the mandate record):

1. **MEDIUM — wrong blacklist-payload claim, confirmed and fixed.** A first draft said
   `review-gate/blacklist` "carries the same `disclosed_review_flags` payload" in B4 and B4-2.
   False: B4's report entry (used in the comparison table) comes from a run against the pre-A3-M
   C3 manifest, which carries no `disclosed_review_flags` for this walk at all; only the
   post-A3-M re-emitted manifest (used for B4's separate 3-walk delta sweep) and B4-2's manifest
   carry the flag. `BRIDGING_ADVERSE_HISTORY` reads `immigration.violation_history`, not the
   flag, in both. Corrected in "Unexplained observation" above with the verified facts.
2. **LOW — "omitted facts" misdescribed A6-2's inputs, confirmed and fixed.** The seven old
   facts were present in each walk's `asked` list with `status: UNKNOWN, reason: UNVERIFIED`,
   not unasked/omitted. A6-2 replaced that status with an explicit `KNOWN` value. Corrected in
   "Why this re-sweep" above, verified against the pre-A6-2 manifest directly.
3. **LOW — apparent six-vs-seven contradiction, confirmed and fixed.** "A6-2 touches only the
   six secondhome/study labels" read as contradicting "A6-2 rewrote 7 walk payloads" elsewhere.
   Both were true (6 moved, 1 — `secondhome_passive_income_usd` — did not) but the wording did
   not say so at the point of first mention. Reworded above to state the 6-of-7 relationship
   explicitly at both mentions.
4. **LOW — combinatorial coverage wrongly called "unchanged", confirmed and fixed.**
   `walksTotalExact` moved from B4's `72,165,845,568,960` to B4-2's `55,234,481,243,760` (the
   `application_channel` label churn changes the tree's branching); only edge coverage
   (317/317, `PROVEN`) is unchanged. Corrected in "Run facts" above.
5. **LOW — review-count arithmetic wrong, confirmed and fixed.** A first draft attributed the
   41→42 `HUMAN_REVIEW_REQUIRED` delta to "the six A6-2 rows moving in" — wrong: only 2 of the 6
   move into `HUMAN_REVIEW_REQUIRED` (the other 4 move into `NO_SUPPORTED_PATH`), and one row
   (`review-gate/blacklist`) moves OUT. Correct arithmetic `41 + 2 − 1 = 42`; of the 42, 41 are
   non-criminal holds (not B4's 40 — that number describes B4's own sweep). Corrected in "Proven"
   and "Declared limits" above.
6. **LOW — live-proof language overstated what two health probes and a manifest prove,
   confirmed and fixed.** "A constant Fly release" and "a browser produces today" read as this
   sweep itself having exercised a browser and having proven release stability beyond its own
   window. Reworded: release-constancy is bounded to this run's window (unchanged from the
   Declared limits already stated); "a browser would produce these requests today" is B5-2's
   proof (top-level library import of the same enumerator), not a claim this sweep drove one.
7. **LOW — reproduction script incomplete, confirmed and fixed.** The embedded Python computed
   verdicts, latency, and the label/moved-row comparison, but never computed
   `review_reasons`/`no_path_reasons`/`notices` despite the README presenting tables for all
   three. Added the missing Counter block; re-run against the committed JSONs, output matches
   the README's tables exactly (48/43/59 tag sums).
8. **Provenance sourcing, addressed by clarification.** The exact ruling timestamp
   (`2026-09-22T07:24:41Z`) and the "B3 v3 U9" anchor designation are not derivable from the two
   JSON files — they are identifiers from the conductor's `MANDATE-vo.md` record. This was
   already true and not misleading (the assigning mandate requires NUMBERS to be re-derived from
   the JSONs, never transcribed; a ruling timestamp and a slice-anchor label are provenance
   metadata, not counts) — added one sentence at each mention naming the source explicitly
   rather than leaving it implicit.

Not raised by the reviewer and independently confirmed: the verdict distribution
(172/42/31/6/1), every `review_reasons`/`no_path_reasons`/notices tag count (48/43/59), the
251-shared-label set (1 new, 2 gone), all 7 moved rows' states and reason codes, the
`review-gate/blacklist` "unexplained" framing itself (codex: "no simpler cause is established by
these records, and attributing it to A6-2/B5-2 would be unsupported"), latency p50/p95/max/min
via standard nearest-rank, the `grep -c process.application_channel` == 0 result over every
existing 020/021/022 pack file, and the PII digit-run accounting (81 lines, all 4 categories).

### Second pass (conductor addendum, same seat)

The conductor asked for the `TEMPORARILY_UNAVAILABLE` walk's own subsection (full payload,
HTTP/latency, B4 state) and for the 6 `NEEDS_INPUT` walks to be named with their missing facts.
A second codex `exec` pass (same seat, `gpt-6-astra`, xhigh, read-only) reviewed just those two
new sections. Verdict **MEDIUM**, 6 findings, all 6 CONFIRMED and fixed:

1. **MEDIUM — the server's envelope does carry an explanatory code.** A draft said the
   `TEMPORARILY_UNAVAILABLE` envelope "carries no explanatory code of any kind." False:
   `evaluate_path.py:637` sets `"outage": {"code": code, "retryable": True}` inside the
   envelope; `enumerate_live.py`'s `_reason_codes()` never reads `outage` at all, so the code is
   discarded before it reaches this report — the gap is in what the RUNNER persists, not in
   what the SERVER sends.
2. **MEDIUM — `classification=engine_verdict` overstated as "a valid decision envelope."** The
   runner's own check (`enumerate_live.py:654-672`) is exactly three things: HTTP 200, valid
   JSON, `decision` is a mapping. It does not validate the decision against the server's
   Pydantic schema. Reworded to say precisely what the classification does and does not confirm.
3. **LOW — the "full record, every field" table omitted `attempts_history`.** Added, noting it
   is a single element identical to the top-level fields (one attempt, nothing retried).
4. **LOW — the six NEEDS_INPUT latencies were unlabelled rounded integers.** Labelled as
   rounded, with exact values (303.99/219.79/261.76/258.42/268.87/240.30 ms) given alongside.
5. **LOW — the `secondhome_basis` mechanism and line citations were wrong.** A draft attributed
   question GATING to `fact-mapper.ts`'s conservative-default guard functions; those guards only
   supply a fallback VALUE for an already-unasked fact. The actual question-selection logic is
   in `flow.ts` (~978-989): when `secondhome_basis` is `"unsure"`, none of the four sub-questions
   are added to the question list at all. Also corrected: the two boolean secondhome facts use
   `booleanFact` (undefined branch at fact-mapper.ts:71-72), not `integerFact` (line 89, which
   applies only to the two monetary facts).
6. **LOW — `asked` conflated with "every entry has a status."** Routing-only question IDs
   (`trip_scope`, `review_gate`) have no standalone engine fact. Narrowed to the claim that is
   actually true: 5 of 6 walks have exactly one UNKNOWN/UNVERIFIED **engine fact** matching the
   target, with the rest of the walk's scenario-relevant facts KNOWN.

Not raised and independently confirmed: the `NEEDS_INPUT` walk_ids, HTTP statuses and notices;
the `TEMPORARILY_UNAVAILABLE` walk's full field values; the zero-occurrence `guardian_consent`
grep and the 56-distinct-fact-path count; the B4-vs-B4-2 blacklist comparison (B4 held via
`BRIDGING_ADVERSE_HISTORY`, independent of the `disclosed_review_flags` state in either
manifest); and the fail-closed `TEMPORARILY_UNAVAILABLE` state's own definition in
`enums.py`/`evaluate_path.py`.

### B4-2b addendum (2026-09-22, no fresh codex pass)

The conductor's ruling (`MANDATE-vo.md`, "B4-2b single-walk re-sweep DONE", 2026-09-22T12:02:13Z)
re-swept the single `review-gate/blacklist` row with the B4-3-capable runner and directed a
Sonnet builder to re-derive the README delta from the patched JSON. **This addendum is not a
second codex `exec` pass** — none ran against this delta — the check here is the conductor's own
re-derivation plus this builder's independent re-derivation of the same five numbers (verdict
distribution, moved-rows count, `outage` row, report sha256, `requests_used_total`), both against
the committed JSON, both printed in the PR body's proof fences: distribution
172/43/31/6/0, moved rows 6 (not 7), `outage: null` on 1/252 rows, sha256
`49f0144323e1a1229992d57f8d8dbf2753f6d7a351b28e4254eefea6e57f8ac9`, `requests_used_total 253`.
No new claim in this addendum's scope is uncorroborated by a command in the PR body.

### A9 addendum (2026-09-24, TP1 council — not a codex pass)

The frontmatter `adversarial_review: codex` names the seat that reviewed this file's ORIGINAL
B4-2/B4-2b sections (above); it predates the A9 addendum below and does not describe it. The A9
addendum's own review is a 2-seat TP1 council, per R9's Gear-3 quorum (`COUNCIL_REVIEW_SEATS`):
**`tp1-qwen3.8-max`** (titolare, probed live first) and **`tp1-deepseek-v4-pro`** (reserve,
substituting for `codex-gpt-5.6-sol`/`kimi-code/k3`, both TIMEOUT on a direct liveness probe —
named in this PR's `evidence/.../pack.yml` `seat_fallback_reason`). Each ran independently
against the same task (`scripts/tp1_call.py`, task file =
`evidence/2026-09/agent-air-m5-docs-vo-a9-sweep-research-1648e458/refuter-runs/refuter-task.txt`):
the addendum's claims (census, `sequence`/`http_status`, the 15-walk moved-state diff, the
28-HUMAN_REVIEW breakdown, the 4 new reason codes) checked against JSON excerpts of the two
committed report files.

Verdict: both **BLOCK**, 3 findings combined (2 from `tp1-qwen3.8-max`, 1 from
`tp1-deepseek-v4-pro`), all 3 traced to the SAME root cause and all 3 RETRACTED:

1. **The `payload_sha256` claim was not verifiable from the review excerpt** (the excerpt
   omitted that field to keep the task file a manageable size for a TP1 call) — not a defect in
   the README. Re-verified directly against the full committed JSON:
   `{w["rule_pack"]["payload_sha256"] for w in walks}` has exactly one member,
   `e5f791b5232fd1369ef3b94ca7bb5f349f9bb6eb4073895aa9f7deb682e72204`, on all 252/252 walks —
   matches the README verbatim.
2. **The "4 new reason codes, absent from B4-2b" claim was not verifiable from the B4-2b
   excerpt** (that excerpt carried only `walk_id`/`engine_state`, no `reason_codes`, so the
   review task's own instructions asked the seats to assume an empty universe if load-bearing —
   both seats correctly flagged the assumption rather than silently accepting it) — not a defect
   in the README. Independently recomputed from BOTH full committed JSONs' `reason_codes`
   (a proper `Counter` difference, not an assumed-empty universe): the A9-only set is exactly
   `E33G_LOCAL_COMPANY_NOT_ALLOWED` ×7, `STUDY_ADMISSION_OR_SPONSOR_NOT_CONFIRMED` ×4,
   `E33G_LOCAL_MARKET_NOT_ALLOWED` ×2, `RETIREMENT_INCOME_BELOW_THRESHOLD` ×1 — matches the
   README exactly, no extra or missing code.

All other claims the review task COULD check from the excerpts (census 185/8/31/28/252,
`sequence`=23 and `http_status`=200 on all 252, the 15 moved walk_ids with exact transitions,
the 28-HUMAN_REVIEW breakdown 25/2/1) came back clean from both seats on the first pass — no
discrepancy, no fix needed. Full transcripts, the task file, and the journal:
`evidence/2026-09/agent-air-m5-docs-vo-a9-sweep-research-1648e458/{council.jsonl,refuter-runs/}`.

Not in scope for either TP1 seat (the task was numeric/set claims over the JSON data only): the
`git log --grep "A3'-B"` provenance claim below, and the activation id/timestamp provenance —
both are text/history claims, not derivable from the report JSONs. That gap is why the fresh
on-disk gate (not this council) is what caught the qualifier this claim was missing.

### B4-3 addendum (2026-09-24, TP1 council — not a codex pass)

Same seat shape as the A9 addendum above, per R9's Gear-3 quorum (`COUNCIL_REVIEW_SEATS`):
**`tp1-qwen3.8-max`** (titolare, probed live first) and **`tp1-deepseek-v4-pro`** (reserve,
substituting for `codex-gpt-5.6-sol`/`kimi-code/k3`). Direct liveness probe this round
(`scripts/arsenal_probe.py --table`, 2026-09-24): `tp1-qwen3.8-max` LIVE 2549ms,
`tp1-deepseek-v4-pro` LIVE 2144ms, `codex` TIMEOUT 15044ms, `kimi` TIMEOUT 15087ms — the same
substitution #7230 made, named in this PR's `evidence/.../pack.yml` `seat_fallback_reason`. Each
ran independently against the same task (`scripts/tp1_call.py`, task file =
`evidence/2026-09/agent-air-m5-docs-vo-b4-3-research-a91be01f/refuter-runs/refuter-task.txt`):
the addendum's claims below (census, `sequence`/`http_status`, the 25-walk moved-state diff vs
the A9 sweep, the 3 held walk_ids) checked against JSON excerpts of the two committed report
files — **every** field either claim under review rests on is in the excerpt
(`walk_id`/`engine_state`/`sequence`/`http_status` on all 252 rows each). The one field left out
of the excerpt, `rule_pack.payload_sha256` (a 64-hex content hash, uniform across all 252 rows in
both files), was deliberately excluded and marked explicitly out-of-scope in the task's own
instructions — not omitted silently the way #7230's narrower excerpt omitted it (which drew 3
findings, all later RETRACTED against the full data, because the review task never told the
seats the field was intentionally absent). That uniformity claim was verified separately by the
builder against the full committed JSONs (`{w["rule_pack"]["payload_sha256"] for w in walks}` has
exactly one member on both files, matching the README's `e5f791b5…72204`), outside the council's
scope.

Verdict: both **PASS**, 0 findings on the 5 claims the task file actually put to the council:
the census, `sequence`/`http_status` uniformity, the 25-walk moved set, the 3 held walk_ids, and
(declared out of scope, not checked) `payload_sha256` uniformity. `tp1-deepseek-v4-pro`'s
completed PASS was its THIRD attempt, not a first pass (`council.jsonl` row 2: two earlier runs
exhausted their budget mid-reasoning before this one completed). The rest of this addendum's
claims were never put to either seat, and are re-derived directly by the builder from the two
full committed JSONs instead: the run facts (window, dry-run plan, `stopped_reason`, request
counts, the #7234 merge/build-flip times), and the reason-code characterisations below (the 25
moved walks as `ACTIVITY_BOUNDARY`-only; the 3 held walks as Studio ×2 + criminal ×1, none
`ACTIVITY_BOUNDARY`-only) — none of these rest on the council's excerpt, which carries no
`reason_codes` field. Full transcripts and the task file:
`evidence/2026-09/agent-air-m5-docs-vo-b4-3-research-a91be01f/{council.jsonl,refuter-runs/}`.


## A9 addendum (2026-09-24): seq-23 activated in production, 252-walk re-sweep

Seq-23 (`rule_pack_id a72aa24f-344a-58c1-809d-076a9227a1f0`, payload sha256
`e5f791b5232fd1369ef3b94ca7bb5f349f9bb6eb4073895aa9f7deb682e72204`) was activated in production
2026-09-24T11:27:25Z by `vo-ceremony-a9-activate` (activation_id
`5ba3b03c-693a-4ae4-b76a-130977450d3e`). Full ceremony record, including the runbook-drift and
ceremony-transport findings, is `PROVELIVE-A9-ACTIVATION-REPORT.md` (not committed here). Step 8
ran 8 targeted prove-live probes (8/8 as expected, no rollback); step 9 re-ran the same B4-class
252-walk sweep against this directory's manifest
(`prove-live-b52-manifest-raw-main-1c6d2240-20260922.json`) with the same driver command used for
B4-2/B4-2b:

```
$ … backend.scripts.visa_engine.enumerate_live \
    --manifest prove-live-b52-manifest-raw-main-1c6d2240-20260922.json \
    --report prove-live-a9-seq23-full-sweep-report-20260924.json \
    --max-requests 260 --rate-per-minute 25 --dry-run
plan: pending=252 total=252 already_recorded=0 never_attempted=252 retryable_harness_reds=0 max_requests=260 rate_per_minute=25.0 max_consecutive_harness_reds=3 health_probes_outside_budget=2 estimated_minutes=10.08
$ … backend.scripts.visa_engine.enumerate_live \
    --manifest prove-live-b52-manifest-raw-main-1c6d2240-20260922.json \
    --report prove-live-a9-seq23-full-sweep-report-20260924.json \
    --max-requests 260 --rate-per-minute 25
wrote 252/252 walks to prove-live-a9-seq23-full-sweep-report-20260924.json (stopped_reason=completed, requests_used_this_run=252, requests_used_total=252)
SWEEP_RC=0
```

Report JSON: `prove-live-a9-seq23-full-sweep-report-20260924.json`, sha256
`899ce88d9314d17cb8cc0d13770374ada19c119d46e4a706a8a929dcc084c808`.

### Census (derived by command from the JSON's `engine_state`, `rule_pack.sequence`, `http_status` — never typed)

| | B4-2b (seq-22) | **A9 sweep (seq-23)** |
|---|---|---|
| SUPPORTED_CANDIDATES | 172 | **185** |
| NEEDS_INPUT | 6 | **8** |
| NO_SUPPORTED_PATH | 31 | **31** |
| HUMAN_REVIEW_REQUIRED | 43 | **28** |
| total | 252 | 252 |
| `rule_pack.sequence` | 22 ×252 | **23 ×252** (payload `e5f791b5…72204` ×252) |
| `http_status` | — | **200 ×252** |

`HUMAN_REVIEW_REQUIRED = 28` breaks down (by command, over `review_reasons`) as
`DISCLOSED_ACTIVITY_BOUNDARY_REVIEW` ×25 (adapter hold on the mouth-side flag; closes with
A3'-B, not built as of this sweep — on this PR's merge-base `587f468fe7`, `git log 587f468fe7
--grep "A3'-B" --format=%h` returns 2 commits, `d5843d0e93` (A3'-M, #7172) and `01d1f99b60`
(#7160), neither of which BUILDS A3'-B — both merely mention it as future work; no commit's own
subject is A3'-B itself (`git log 587f468fe7 --format=%s | grep -c "A3'-B"` → `0`). The same
grep on a later `origin/main` also matches this PR's own squash commit, whose messages quote the
string),
`SECOND_HOME_BELOW_THRESHOLD_STUDIO` ×2 (D23, owner decision), `DISCLOSED_CRIMINAL_RECORD_REVIEW`
×1 (G1's allowed exception).

### The 15 walks that moved state vs B4-2b (derived by set-intersection over `walk_id`, diffing `engine_state`)

`shared = 252` (same 252 `walk_id`s in both files — no label added or dropped since B4-2b). 13
walks moved `HUMAN_REVIEW_REQUIRED → SUPPORTED_CANDIDATES`, 2 moved
`HUMAN_REVIEW_REQUIRED → NEEDS_INPUT`; the other 237 kept state.

| walk_id | B4-2b state | A9 state |
|---|---|---|
| `edge/current_status_code=other` | HUMAN_REVIEW_REQUIRED | SUPPORTED_CANDIDATES |
| `edge/current_status_code=unsure` | HUMAN_REVIEW_REQUIRED | SUPPORTED_CANDIDATES |
| `edge/in_indonesia=unsure` | HUMAN_REVIEW_REQUIRED | NEEDS_INPUT |
| `edge/nationalities=unsure` | HUMAN_REVIEW_REQUIRED | NEEDS_INPUT |
| `edge/stay_permit_code=unsure` | HUMAN_REVIEW_REQUIRED | SUPPORTED_CANDIDATES |
| `review-gate/ambiguous_sponsor` | HUMAN_REVIEW_REQUIRED | SUPPORTED_CANDIDATES |
| `review-gate/blacklist` | HUMAN_REVIEW_REQUIRED | SUPPORTED_CANDIDATES |
| `review-gate/diplomatic_passport` | HUMAN_REVIEW_REQUIRED | SUPPORTED_CANDIDATES |
| `review-gate/health_flag` | HUMAN_REVIEW_REQUIRED | SUPPORTED_CANDIDATES |
| `review-gate/immigration_investigation` | HUMAN_REVIEW_REQUIRED | SUPPORTED_CANDIDATES |
| `review-gate/not_certain` | HUMAN_REVIEW_REQUIRED | SUPPORTED_CANDIDATES |
| `review-gate/overstay` | HUMAN_REVIEW_REQUIRED | SUPPORTED_CANDIDATES |
| `review-gate/pep_or_sanctions` | HUMAN_REVIEW_REQUIRED | SUPPORTED_CANDIDATES |
| `review-gate/prior_refusal` | HUMAN_REVIEW_REQUIRED | SUPPORTED_CANDIDATES |
| `review-gate/source_of_funds_unclear` | HUMAN_REVIEW_REQUIRED | SUPPORTED_CANDIDATES |

New reason codes observed live and absent from B4-2b entirely (by command, over
`review_reasons`/`no_path_reasons`): `E33G_LOCAL_COMPANY_NOT_ALLOWED` ×7,
`STUDY_ADMISSION_OR_SPONSOR_NOT_CONFIRMED` ×4, `E33G_LOCAL_MARKET_NOT_ALLOWED` ×2,
`RETIREMENT_INCOME_BELOW_THRESHOLD` ×1.

**No finding in this sweep**: HUMAN_REVIEW = 28 = the runbook's expectation (A3'-B not live, so
the 25 `ACTIVITY_BOUNDARY` walks are still held by the adapter flag), 0 transport errors, 0
harness reds, sequence 23 on all 252, HTTP 200 on all 252.


## B4-3 addendum (2026-09-24, post-A3'-B): the 252-walk re-sweep after #7234, HUMAN_REVIEW 28 → 3

PR #7234 (`d6a2152d05cd96d596cabb3dcadf72cdd8c7cd72`, merged 2026-09-24T16:14:53Z, Slice A3'-B)
moved `ACTIVITY_BOUNDARY` from `HOLDING_DISCLOSED_FLAGS` to `DEAD_END_DISCLOSED_FLAGS` in the
engine's disclosed-flag layer; production `build_sha` flipped to match the merge commit at
2026-09-24T16:25:55Z, confirmed by polling `curl -fsS https://nuzantara-rag.fly.dev/health`
every 30s from the merge (`vo-provelive-a3p-b`, `PROVELIVE-A3P-B-REPORT-7234.md`, not committed
here — narrative provenance only; every number below is recomputed from the JSON EXCEPT the
dry-run plan `pending=252 already_recorded=0`, which the JSON does not record and is quoted from
that narrative report). Its Step 4 re-ran the same B4-class 252-walk sweep against this
directory's manifest (`prove-live-b52-manifest-raw-main-1c6d2240-20260922.json`, same driver
`backend.scripts.visa_engine.enumerate_live`, `--max-requests 260 --rate-per-minute 25`, dry-run
first with that clean plan) between the report JSON's own `started_at` and `finished_at` fields,
read by command (never the narrative report's times — its window was 22s off at the start and
10s off at the end):

```
$ python3 -c "import json; d=json.load(open('prove-live-b4-3-a3pb-full-sweep-report-20260924.json')); print(d['started_at'], d['finished_at'])"
2026-09-24T16:32:33.625989+00:00 2026-09-24T16:42:45.798555+00:00
```

`stopped_reason=completed`, `requests_used_this_run=252`, `requests_used_total=252`.

Report JSON: `prove-live-b4-3-a3pb-full-sweep-report-20260924.json`, sha256
`017bce8e460a21f52ff49442e79639d624348a1835d0587e04256f0a91ea0d8b`.

### Census (derived by command from the JSON's `engine_state`, `rule_pack.sequence`, `rule_pack.payload_sha256`, `http_status` — never typed)

| | B4-2b (seq-22) | A9 sweep (seq-23, pre-#7234) | **B4-3 sweep (seq-23, post-#7234)** |
|---|---|---|---|
| SUPPORTED_CANDIDATES | 172 | 185 | **185** |
| NEEDS_INPUT | 6 | 8 | **8** |
| NO_SUPPORTED_PATH | 31 | 31 | **56** |
| HUMAN_REVIEW_REQUIRED | 43 | 28 | **3** |
| total | 252 | 252 | 252 |
| `rule_pack.sequence` | 22 ×252 | 23 ×252 | **23 ×252** (payload `e5f791b5…72204` ×252) |
| `http_status` | 200 ×252 | 200 ×252 | **200 ×252** |

252/252 `walk_id`s identical between the A9 report and this one, by set-intersection (0 missing,
0 extra — no label added or dropped since A9).

### The 25 walks that moved state vs A9 (derived by set-intersection over `walk_id`, diffing `engine_state`)

All 25 moves are one direction, `HUMAN_REVIEW_REQUIRED → NO_SUPPORTED_PATH` — every one of them
an `ACTIVITY_BOUNDARY`-disclosed edge/review-gate walk. **0 walks moved to
SUPPORTED_CANDIDATES**; the other 227 walks kept state:

| walk_id | A9 state | B4-3 state |
|---|---|---|
| `edge/business_activity=other` | HUMAN_REVIEW_REQUIRED | NO_SUPPORTED_PATH |
| `edge/business_activity=training` | HUMAN_REVIEW_REQUIRED | NO_SUPPORTED_PATH |
| `edge/business_activity=unsure` | HUMAN_REVIEW_REQUIRED | NO_SUPPORTED_PATH |
| `edge/diaspora_connection=dual` | HUMAN_REVIEW_REQUIRED | NO_SUPPORTED_PATH |
| `edge/diaspora_connection=other` | HUMAN_REVIEW_REQUIRED | NO_SUPPORTED_PATH |
| `edge/diaspora_connection=unsure` | HUMAN_REVIEW_REQUIRED | NO_SUPPORTED_PATH |
| `edge/diaspora_documents=unsure` | HUMAN_REVIEW_REQUIRED | NO_SUPPORTED_PATH |
| `edge/investment_amount_usd=1000000000` | HUMAN_REVIEW_REQUIRED | NO_SUPPORTED_PATH |
| `edge/investment_amount_usd=unsure` | HUMAN_REVIEW_REQUIRED | NO_SUPPORTED_PATH |
| `edge/investment_currency=idr` | HUMAN_REVIEW_REQUIRED | NO_SUPPORTED_PATH |
| `edge/investment_currency=still_unsure` | HUMAN_REVIEW_REQUIRED | NO_SUPPORTED_PATH |
| `edge/investment_vehicle=family` | HUMAN_REVIEW_REQUIRED | NO_SUPPORTED_PATH |
| `edge/investment_vehicle=undecided` | HUMAN_REVIEW_REQUIRED | NO_SUPPORTED_PATH |
| `edge/investment_vehicle=unsure` | HUMAN_REVIEW_REQUIRED | NO_SUPPORTED_PATH |
| `edge/other_paid_activity=unsure` | HUMAN_REVIEW_REQUIRED | NO_SUPPORTED_PATH |
| `edge/other_purpose=arts_sport` | HUMAN_REVIEW_REQUIRED | NO_SUPPORTED_PATH |
| `edge/other_purpose=crew` | HUMAN_REVIEW_REQUIRED | NO_SUPPORTED_PATH |
| `edge/other_purpose=journalism` | HUMAN_REVIEW_REQUIRED | NO_SUPPORTED_PATH |
| `edge/other_purpose=medical` | HUMAN_REVIEW_REQUIRED | NO_SUPPORTED_PATH |
| `edge/other_purpose=other` | HUMAN_REVIEW_REQUIRED | NO_SUPPORTED_PATH |
| `edge/other_purpose=religious` | HUMAN_REVIEW_REQUIRED | NO_SUPPORTED_PATH |
| `edge/other_purpose=unsure` | HUMAN_REVIEW_REQUIRED | NO_SUPPORTED_PATH |
| `edge/other_purpose=volunteer` | HUMAN_REVIEW_REQUIRED | NO_SUPPORTED_PATH |
| `edge/retirement_basis=unsure` | HUMAN_REVIEW_REQUIRED | NO_SUPPORTED_PATH |
| `review-gate/activity_boundary` | HUMAN_REVIEW_REQUIRED | NO_SUPPORTED_PATH |

The 3 walks that stayed `HUMAN_REVIEW_REQUIRED`, exactly the three named ahead of the sweep
(Studio ×2, criminal ×1), none `ACTIVITY_BOUNDARY`-only:

| held walk_id | state |
|---|---|
| `edge/secondhome_deposit_usd=unsure` | HUMAN_REVIEW_REQUIRED |
| `edge/secondhome_property_value_usd=unsure` | HUMAN_REVIEW_REQUIRED |
| `review-gate/criminal_record` | HUMAN_REVIEW_REQUIRED |

**No finding in this sweep**: `HUMAN_REVIEW_REQUIRED` = 3 = exactly the runbook's expectation
(the 25 `ACTIVITY_BOUNDARY`-only walks left the hold, matching #7234 in force end-to-end), 0
walks moved to `SUPPORTED_CANDIDATES`, 0 transport errors, sequence 23 on all 252, HTTP 200 on
all 252.
