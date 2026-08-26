---
date: 2026-08-26
domain: operations
adversarial_review: kimi-k3
---

# Candidate metrics, `MetricProfile` design, and golden-set design

Design only. No golden set was built, no label was assigned, and no benchmark ran this session
— the packet requires the `MetricProfile` frozen *before* any challenger is inspected (packet
"Before inspecting challenger results, freeze a `MetricProfile`..."), so producing labels ahead
of a reviewed profile would itself violate the packet's own sequencing. This document proposes
the profile shape and the golden-set design for review, per the "golden-set design, dedup
labels... schema mapping" item in this lane's ALLOWED list.

## 1. Packet exit criteria, restated as measurable candidates

| Packet exit criterion (verbatim) | Candidate metric | Data source (schema mapping) |
|---|---|---|
| "zero lost events in bounded replay" | `count(events_submitted) == count(events_persisted) + count(events_dead_lettered)` over a replay window, reconciled by `identity.idempotency_key` | new: requires the idempotency key that does not exist today (CONTRACT-MAP.md §5.1) |
| "zero duplicate external side effects" | `count(distinct external_effect_id) == count(external_effect_id)` for every downstream call (NB push, WR2 dispatch) keyed by an idempotency/dedup receipt | `intel_item_nb_pushes` (migration 171) already has a per-target status column — reusable pattern, not reusable table (wrong grain: keyed to `intel_items`, not to a new `IntelEvent`) |
| "exact-duplicate precision at least 99.5%" | precision of the deterministic (exact/normalized) dedup layer against the golden set's exact-duplicate stratum | golden set §3 below |
| "story-cluster precision at least 95% and recall at least 90%" | precision/recall of the *chosen* incumbent against the golden set's cluster-labeled stratum | golden set §3 below |
| "critical false collapse below 1%" | rate of golden-set pairs labeled *genuinely independent* that the incumbent nonetheless merges into one cluster | golden set §3, "genuinely independent corroboration" stratum |
| "100% producer/run/artifact lineage for the canary window" | `count(events with lineage.pipeline_run_id populated) / count(events)` over the canary window | new: `lineage.pipeline_run_id` does not exist in any live table today — this metric is 0% by construction until the field is added, not a bug found by measuring it |
| "unknown-message success ACKs equal zero" | `count(unknown-type messages ACKed as success)` — target is a literal zero-count, not a rate | directly falsifiable today: CONTRACT-MAP.md §2.2/§2.3 already found this is currently **not** zero (the `intel.research_dossier` ACK-drop) — this metric is the packet's own smoking gun and is already known-failing before any new code ships |
| "old and canonical feeds reconcile within a declared tolerance for two complete windows" | `abs(count(old_feed_pushes) - count(canonical_feed_pushes)) / count(old_feed_pushes) <= tolerance`, per window, for 2 consecutive windows | needs both feeds instrumented with comparable counters — today `intel-lake-nb-pusher-standalone.py`'s `metrics.json` (mentioned in its own docstring) and MATA GARUDA's `run_nlm_feeder_stream.py` heartbeat metadata are two **different** metric shapes; reconciling them needs a shared schema, itself a small design task |
| "independent reviewer passes code, data sample, and live receipts" | binary gate, not a metric — process requirement on the eventual builder, not measurable in advance |

## 2. `MetricProfile` design (frozen model exists: `research_os/models/metric_profile.py`,
listed in CONTRACT-MAP.md §5, not read line-by-line this session — flagged as an open item in
UNKNOWNS.md since the exact frozen field names were not re-verified against this proposal)

Proposed profile, to be checked against the actual `MetricProfile` model fields before any
future PR freezes it (do not treat the field names below as already validated against the frozen
schema — that check is explicitly deferred, see UNKNOWNS.md):

```yaml
metric_profile:
  incumbent: "exact_canonical_url_match"          # today's only real behavior, promoted to an
                                                     # explicit, named baseline instead of an
                                                     # implicit default
  labeled_set_version: "p05-golden-v0"             # does not exist yet — §3
  sample_floors:
    exact_duplicates: 150
    tracking_url_variants: 100
    translations: 80
    syndication: 100
    updates: 80
    same_event_different_angle: 100
    similar_headline_different_event: 100
    independent_corroboration: 100
    # sum = 810, within the packet's stated 500-1,000 range
  precision_recall_thresholds:
    exact_duplicate_precision_min: 0.995            # packet exit criterion
    story_cluster_precision_min: 0.95                # packet exit criterion
    story_cluster_recall_min: 0.90                   # packet exit criterion
    critical_false_collapse_max: 0.01                # packet exit criterion
  latency_cost_privacy_guardrails:
    max_added_latency_per_event_ms: "not yet set — needs a measured baseline latency for
      record_observation(), which was not measured this session (Postgres tool unreachable)"
    cost_per_1k_events: "candidate layers should be free-tier/local-first per repo-wide cost
      constraint (CLAUDE.md Cost constraint) unless Zero explicitly authorizes a paid per-token
      call; a semantic/embedding layer must name its exact model+endpoint in its own PR, not here"
    privacy: "no layer may send restricted_osint/client_pii payload content to any non-local
      service — PROTECTED-DATA-BOUNDARY.md §3"
  subgroup_slices:
    - by_source_domain_class          # regulatory .go.id vs. general news vs. blog
    - by_language                     # Indonesian vs. English vs. mixed
    - by_producer                     # Intel Lake API producers vs. MATA GARUDA-originated
  confidence_treatment: "layers below story_cluster_precision_min on any subgroup slice route to
    decision.verdict = 'review', never auto-merge — mirrors the frozen StoryClusterDecision.verdict
    enum's own 'review' option (story_cluster.py:140, read this session)"
  operating_window: "to be set by the builder against the actual canary window it runs, not
    predetermined here"
```

## 3. Golden-set design (labels, strata, provenance — no data yet)

### 3.1 Strata (from the packet's own enumerated list, verbatim)

exact duplicates · tracking-URL variants · translations · syndication · updates · same
event/different angle · similar headline/different event · genuinely independent corroboration.

### 3.2 Provenance rule (protected-data-boundary-compliant by construction)

Every golden-set pair/cluster must be built from `source.canonical_url` (a public URL) plus a
short, human-written *paraphrase* of why the pair belongs in its stratum — **never** a copy of
the article body. This satisfies PROTECTED-DATA-BOUNDARY.md §2's ceiling (public URL, never body
content) even for MATA-GARUDA-sourced items, and happens to also make the golden set durable
against link rot in a reviewable way (the paraphrase, not the fetched content, is what a
reviewer checks).

### 3.3 Labeling process (proposed, not run)

1. Draw candidate pairs from **synthetic, not live**, `canonical_url` sets for this design
   review — this bundle's write perimeter forbids any real row (dispatch: "Synthetic fixtures
   only").
2. Two independent labelers (cross-family per the repo's generator≠grader norm — e.g. one
   Sonnet-5 pass + one Kimi K3 pass) label each pair against the 8 strata above; disagreement
   goes to a third, human-adjudicated pass — this mirrors `StoryClusterDecision.decided_by`'s
   `"deterministic" | "model" | "human"` enum (story_cluster.py:142, read this session) rather
   than inventing a new adjudication vocabulary.
3. `labeled_set_version` gets a content hash of the finished set (not a date string) so a
   `MetricProfile` can pin an exact version — consistent with this repo's general "SHA-anchor,
   never timestamp" antidote (superscar family #9).

### 3.4 Sample-floor rationale

The packet's own range is 500-1,000 pairs/clusters across 8 named categories. §2's proposed
floors sum to 810 and give every stratum at least 80 examples — large enough that a single
mislabel does not swing a stratum's precision/recall by more than ~1.2 percentage points, which
is inside the packet's own tightest threshold (critical false collapse < 1%, i.e. a stratum
needs >100 examples before a single-item swing stays under threshold. **CORRECTED 2026-08-26
(adversarial review): the two most safety-relevant strata, `independent_corroboration` and
`syndication`, were set to exactly 100 "for exactly this reason" — but 1/100 = 1.00%, which
does NOT satisfy "< 1%". The rationale's own arithmetic requires >=101.** Treat 100 as the
floor that FAILS this test; a build lane setting these strata must use >=101, and the 810 total
moves accordingly.

## 4. What NOT to promote by default

`dossier_compiler.py`'s existing `DEFAULT_CLUSTER_SIMILARITY = 3` keyword-count clustering
(CONTRACT-MAP.md §5.2) must not be treated as a pre-approved incumbent just because it already
runs in production on a neighboring table. It has never been measured against a golden set, and
the packet's own rule ("the chosen cascade is the simplest candidate that passes the
preregistered profile") requires it be evaluated on equal footing with the deterministic
exact/normalized layer, not given seniority for having shipped first.


## Adversarial review

**Seat:** Kimi K3 (`kimi -m kimi-code/k3`), cross-family — neither the model that wrote this
bundle nor the session that gated it. Run 2026-08-26 against a FROZEN diff (head `2807f50e9`):
the generator was dead before the refuter was dispatched, so nothing moved under it.

**Verdict: DEFECTIVE on method, sound on its two headline findings.** The bridge ACK-drop and the
`intel_lake_service.py` docstring-vs-SQL drift both check out on independent re-read. The
systematic defect is a *class*: single-search results stated with more precision than the search
supports. Every finding below was re-verified against disk by the gating session before it was
accepted — the refuter is not trusted either (superscar #6).

| # | Finding | Verified | Disposition |
|---|---|---|---|
| 1 | D7 dependency unflagged: `object_hash` + MATA-side hash reconciliation need the same digest in two implementations, but `apps/mata-garuda` caps deps at `pydantic>=2` | TRUE (`grep D7` → 0 hits in bundle) | **FIXED** — §5.1 now flags it as a §7-forbidden primitive; do not design that reconciliation until D7 lands |
| 2 | "Enumerated every function" used `^def ` — blind to indented sync methods; missed `__init__` (267) and `_classify` (387), the actual rules engine | TRUE | **FIXED** — §1.4 restated; conclusion survives on a re-read, not on the enumeration |
| 3 | "7 files" while listing 8 names in the same sentence | TRUE (`ls` → 8) | **FIXED** |
| 4 | Migration list from a literal-string grep, misses `205_cockpit_intents.sql` (`intel_items`); and `171` is listed as found by a pattern that does not return it | TRUE | **FIXED** — list relabelled a lower bound, both gaps named |
| 5 | Line counts off: 306→305, 230→229, `WR2_ENVELOPE_TYPE` line 34→36 | TRUE | **FIXED** — re-measured |
| 6 | "No file in `apps/backend-rag` imports `intel_event`/`story_cluster`" — false, a test file imports both | TRUE (hedged in-sentence and in UNKNOWNS §2) | **FIXED** — restated; substantive point (importer is a test, no adapter) stands |
| 7 | "89 local databases" is a count carried from a prior session, contradicting this bundle's own "no live counts anywhere" | TRUE | **FIXED** — marked carried-over, not a confirmation |
| 8 | §3.4 arithmetic defeats itself: needs >100, sets the two safety-critical strata to exactly 100; 1/100 = 1.00%, not < 1% | TRUE | **FIXED** — >=101 required, 810 total moves |
| 9 | README cites §3 (NotebookLM feed) for the ACK-drop finding, which lives in §2.2/§2.3 | TRUE | **FIXED** |
| 10 | UNKNOWNS §2 "two producer entrypoints" vs §1.3, which says `intel_radar` writes by a SEPARATE path | PARTIAL | **FIXED** — wording corrected, overstatement removed |
| 11 | "Every dossier envelope has been ACKed-and-dropped since the producer was written" is a live-traffic history claim provable only from code paths | TRUE (overreach) | **ACCEPTED AS LIMIT** — the drop PATH is proven by direct read; whether the producer ever ran with traffic is unknowable without the live stream this bundle could not reach (UNKNOWNS §1) |

**Not a finding** (refuter checked, found sound): migration numbering — head 287, 282 absent,
`272_wa_broker_package_text.sql` WhatsApp-broker-owned; the bundle correctly refuses to bind an
integer. Readiness claims — disclaimed consistently across README and UNKNOWNS §5.
