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
needs >100 examples before a single-item swing stays under threshold — the
`independent_corroboration` and `syndication` strata, the two most safety-relevant, are set to
100 for exactly this reason).

## 4. What NOT to promote by default

`dossier_compiler.py`'s existing `DEFAULT_CLUSTER_SIMILARITY = 3` keyword-count clustering
(CONTRACT-MAP.md §5.2) must not be treated as a pre-approved incumbent just because it already
runs in production on a neighboring table. It has never been measured against a golden set, and
the packet's own rule ("the chosen cascade is the simplest candidate that passes the
preregistered profile") requires it be evaluated on equal footing with the deterministic
exact/normalized layer, not given seniority for having shipped first.
