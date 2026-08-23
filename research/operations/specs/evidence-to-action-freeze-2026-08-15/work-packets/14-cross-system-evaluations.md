---
adversarial_review: exempt-frozen-spec-landed-verbatim-from-10d500e1c
---

# Work Packet 14 — Cross-System Evaluations and Release Gates

**Wave:** 3
**Depends on:** Packets 05–13, 17, and 18; evaluator scaffolding may start earlier, but no release gate can pass before Packet 13 measurements are runnable
**Unlocks:** Packet 15 and every broad cutover
**Risk:** high governance leverage; graders never self-authorize production

## Session prompt

You own the evaluation system that determines whether a new research-OS component is measurably better and safe enough to canary. Separate task, trial, trace, grader, reviewer, and real outcome. The generator can never be the sole grader.

You are not alone in the codebase. Work in a dedicated worktree, own the evaluator/datasets/reports you declare, and preserve concurrent changes. Do not modify the systems being graded merely to make their tests pass. Do not deploy or authorize publication.

## Mission

Create a reproducible evaluation suite spanning ingestion, story clustering, claims, temporal truth, entity resolution, retrieval, decisions, publishing, WR2, WR3, privacy, and outcome telemetry.

## Baseline to establish

Inventory existing tests, probes, critic rubrics, evaluator applications, fixtures, telemetry, and operational scorecards. Mark fixture-only versus live-grounded evidence. Identify tautological graders, self-grading, unstable prompts, unlabeled datasets, and metrics that reward throughput over correctness.

Primary ownership:

- `apps/evaluator/` and narrowly scoped evaluation services;
- new versioned datasets/fixtures containing public or synthetic data only;
- evaluation runner, result schemas, regression reports, and CI gates;
- adapters that read traces/manifests/receipts without changing producers.

Do not own the implementation under test or protected raw data.

## Inputs and frozen contracts

- Every tested run references contract version, code/model/prompt/tool versions, input hashes, and outputs.
- Deterministic graders precede model judges.
- Model judges are calibrated against expert labels and cannot replace mandatory human/legal/privacy approval.
- Dataset changes are versioned and cannot silently rewrite historical scores.

## Deliverables

1. Evaluation taxonomy: `task`, `trial`, `trace`, `grader`, `review`, `outcome`, and `release_gate`.
2. Versioned public/synthetic golden sets:
   - 500–1,000 news pairs/story clusters;
   - 200–300 atomic claims with source spans and temporal truth;
   - at least 300 entity pairs including Indonesian aliases and homonyms;
   - at least 200 retrieval queries;
   - 30 WR2 carousels;
   - 10 WR3 episodes;
   - at least 100 Action Inbox/outcome chains.
3. Deterministic graders for schema, lineage, claims, temporal correctness, idempotency, permissions, hashes, manifests, accessibility, media mechanics, and state transitions.
4. Calibrated model/human rubrics for nuanced relevance, narrative, visual-topic fit, brand voice, and semantic fidelity.
5. Generator≠grader enforcement and grader identity in every result.
6. Baseline-versus-candidate reports with uncertainty, regressions, cost, latency, and subgroup breakdowns.
7. Adversarial privacy/security suite covering PII, restricted OSINT, stale approval, prompt injection, sensitivity downgrade, and replay.
8. Two explicit operating phases: **Phase A**, an advisory evaluation harness that may expose missing or weak measurements without authorizing a release; and **Phase B**, a blocking release-gate layer enabled only after the relevant measurements, graders, and `MetricProfile` are independently validated.
9. Release-gate `MetricProfile` objects and immutable `MetricResult` objects for each work packet; CI may block code merges, but production canary still requires the owner-defined operational gate.
10. Evaluation drift and contamination checks.

## Non-goals

- Do not create one opaque “quality score.”
- Do not use an LLM judge as ground truth.
- Do not let a producer choose only favorable examples.
- Do not include client PII or protected NEXUS rows in cloud-evaluated datasets.
- Do not turn production user behavior into automatic approval.
- Do not optimize to a frozen set without a held-out/adversarial split.

## Implementation sequence

1. Inventory and classify existing tests/evals.
2. Freeze labeling guides and reviewer qualifications.
3. Build deterministic graders and canonical result schema.
4. Assemble and version datasets with train/development/held-out/adversarial partitions.
5. Calibrate model judges against independent human labels; reject poorly calibrated rubrics.
6. Capture baselines before testing candidate branches.
7. Add cost, latency, subgroup, and privacy reporting.
8. Run one candidate from each system family and publish an internal regression report.
9. Independently validate each required measurement and its `MetricProfile` before moving that profile from Phase A advisory status to Phase B blocking status; the immutable `MetricResult.gate_disposition`, never a dashboard-local flag, records each evaluated gate.

Every metric that can influence a gate must reference a canonical, preregistered `MetricProfile` created before candidate results are inspected. It freezes exact dataset/version/hash and split assignment, window, sample floor or power target, thresholds, subgroup and guardrail treatment, exclusions, uncertainty/confidence method, missing-data rule, owner, and expiry. Candidate values, exact source-observation hashes, decision-rule evaluation, reason codes, and gate disposition live only in a later immutable `MetricResult` bound to that exact profile hash. Corrections and late arrivals use the canonical result family/successor mechanism. A threshold without its runnable measurement and profile is advisory only.

## Required metrics

- ingestion: loss, duplicate side effect, lineage coverage;
- clustering: precision, recall, critical false collapse;
- claims: critical support precision, source-span coverage, temporal correctness, abstention;
- entity resolution: merge precision/recall and false-merge severity;
- retrieval: Recall@20, nDCG@10, MRR, support, temporal/no-answer precision, p95, cost;
- Action Inbox: duplicate reduction, time to owner/action, authorization failures;
- publishing: correction, failure, lifecycle truth, indexing verification;
- WR2: claim errors, critic coverage, asset uniqueness, edit distance, preference;
- WR3: claim/identity/audio/license/manifest pass, credits, retries, accepted-asset cost;
- privacy/security: leak and unauthorized-action counts, both required to be zero for critical paths.

## Exit criteria

- datasets and graders are versioned and reproducible;
- independent labels exist for every nuanced gate;
- grader calibration meets a predeclared agreement threshold and subgroup failures are visible;
- every Packet 05–13 exit metric used by a release gate has a runnable, independently validated measurement and preregistered `MetricProfile`; an unresolved measurement gap, unmet sample floor, or expired profile makes that gate `BLOCKED`, never passed, waived, or conditionally passed;
- known bad implementations fail the relevant gates;
- a second reviewer reproduces a representative evaluation run;
- no protected data enters prohibited tooling.

## Shadow and rollback

Run Phase A advisory-first. Phase B blocking is enabled profile-by-profile only after independent validation; it never inherits authority merely because Phase A produced a score. A broken or drifting evaluator cannot approve a candidate and fails closed on critical safety invariants. Rollback removes only the affected CI blocking flag, restores that profile to advisory status, preserves results, and opens an evaluator incident. Historical result versions are immutable.

## Reviewer handoff

Provide dataset cards, labeling guide, grader code, calibration results, contamination checks, baseline/candidate reports, known-bad tests, cost/latency data, and privacy audit.
