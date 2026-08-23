---
adversarial_review: exempt-frozen-spec-landed-verbatim-from-10d500e1c
---

# Work Packet 15 — Active Learning from Human Decisions

**Wave:** 3
**Depends on:** Packets 12, 13, 14, and 18
**Unlocks:** better prioritization; never autonomous self-modification
**Risk:** high feedback-loop and privacy risk

## Session prompt

You own the safe learning loop from operator/team decisions and downstream outcomes. Convert edits and choices into versioned training/evaluation signals, then produce offline proposals. Never let the system rewrite production prompts, code, policies, or approval rules autonomously.

You are not alone in the codebase. Use a dedicated worktree, declare the feedback store/feature pipeline/evaluator you own, and preserve concurrent changes. Do not ingest raw client PII or restricted OSINT into a general learning dataset. Do not deploy a learner without explicit review and canary authorization.

## Mission

Reduce repeated operator effort while preserving editorial sensitivity and risk judgment by learning from structured human decisions, not by imitating final outputs without context.

## Baseline to establish

Inventory where choices and edits currently exist: topic selection, queue actions, claim corrections, source rejection, entity merge/split, title/body/slide/script changes, asset rejection, critic override, alert ignore/snooze, publish/no-publish, correction, lead, conversion, and retention. Measure how much of this is currently lost, free-form, or disconnected from the original candidate and outcome.

## File ownership

Preferred boundary:

- a new feedback/learning service and additive persistence under the research-OS backend namespace;
- Action Inbox and WR2/WR3 adapters that emit structured deltas without changing their core behavior;
- offline feature/ranking experiments and evaluation reports;
- focused privacy, bias, replay, and regression tests.

Do not own production prompts, routing policy, risk policy, canonical claims, or raw CRM/NEXUS records.

## Inputs and frozen contracts

- Exact `RequestedActionSpec`, `ActionItem`, `ActionIntent`, `ApprovalReceipt`, immutable started `ExecutionAttempt`, terminal `OperationalReceipt`, before/after object hashes, `OutcomeEvent`, and Packet 14 evaluation results.
- Human action must retain context: candidate set, evidence state, risk, task, surface, actor role, and timestamp.
- Reject, snooze, and no-action have different meanings.
- Protected content is represented by approved features/IDs, not copied text.

## Deliverables

1. Feedback taxonomy: select, edit, reject, snooze, assign, merge/split, request evidence, override, publish, withdraw, correct, and downstream outcome.
2. Structured delta format for text, claims, layout/slide/shot, assets, owner/SLA, and risk decisions.
3. Context-preserving feedback store with consent/purpose, retention, sensitivity, and deletion/revocation rules.
4. Active-learning sampler prioritizing uncertainty, model/source disagreement, novelty, regulatory risk, economic impact, and underrepresented clusters.
5. Offline candidate-ranking and retrieval/rubric proposals with feature explanations.
6. Counterfactual/off-policy evaluation where feasible; otherwise explicit limits.
7. Bias and representation report across domains, languages, risk classes, sources, and outcome families.
8. Human-readable proposed amendments with expected impact, evidence, evaluation result, and rollback—not direct mutation.
9. Experiment registry linking proposal, dataset/version, evaluator, approval, canary, and outcome.

## Non-goals

- Do not self-edit production code, prompts, brand rules, risk policy, or contracts.
- Do not learn that “ignored” means “bad” without controlling for workload and timing.
- Do not optimize solely for clicks, speed, or operator agreement.
- Do not train on client PII or raw restricted OSINT.
- Do not conceal the features or history that caused a ranking change.
- Do not allow the same model to propose and approve its own amendment.

## Implementation sequence

1. Freeze taxonomy, privacy model, and actor/authority semantics.
2. Capture structured decisions in shadow without changing user workflow.
3. Reconcile deltas with original object and downstream outcomes.
4. Build a representative historical/offline dataset with leakage controls.
5. Establish heuristic baseline before any learned ranker.
6. Train/evaluate proposals offline using Packet 14 held-out/adversarial sets.
7. Present proposals to an independent reviewer and operator.
8. Materialize one reversible, low-risk prioritization canary through the Conductor/Packet 12 path only: exact `RequestedActionSpec` → `ActionItem`/`ActionIntent` → unexpired effect-specific `ApprovalReceipt` → immutable started `ExecutionAttempt` → terminal `OperationalReceipt` → `OutcomeEvent`.

## Golden set and adversarial cases

Target at least 500 decision examples, with domain/language/risk balance, but do not treat “when available” as evidence. Before model selection, preregister a `MetricProfile` with a power analysis or justified minimum sample, held-out split, subgroup floors, operating window, exclusions, uncertainty/confidence method, and safety/diversity guardrails. Test sparse outcomes, delayed outcomes, operator overload, conflicting reviewers, changed policy, repeated template preference, novelty suppression, malicious feedback, duplicated decisions, and revoked sensitive data.

## Metrics and exit criteria

- feedback-object linkage at least 99% in canary;
- structured coverage of at least 90% of supported decision types;
- no prohibited text/PII in the learning store;
- sampler yields measurably higher correction/information value than random selection;
- proposed ranking improves a predeclared Packet 14 metric without degrading critical safety, diversity, novelty, or minority-domain performance;
- median human edit distance or triage time improves at least 20% in a bounded canary;
- every production change has an exact action intent, independent effect-specific approval, immutable started attempt, terminal operational receipt, observed outcome, and rollback;
- no automatic prompt/code/policy mutation exists.

No ranking, sampler-value, edit-distance, or triage-time improvement may be claimed unless the preregistered sample/power floor is met and its confidence interval clears the improvement threshold while all critical guardrails hold. Otherwise the result is `insufficient_evidence`, the heuristic/chronological baseline remains canonical, and no canary is authorized.

## Shadow, canary, and rollback

Capture and score in shadow first. Shadow cannot reorder or otherwise affect a live queue. The first canary may reorder only low-risk internal candidates, only through the canonical authorized execution chain, and must allow instant return to chronological/baseline ordering. Rollback is a separately authorized effect: it disables the learned scorer, records its terminal receipt and outcome, and retains versioned feedback/outcome records subject to privacy retention.

## Reviewer handoff

Provide taxonomy, privacy map, dataset card, feature list, bias report, baseline/candidate evaluation, counterfactual limitations, proposal text, approval receipt, canary results, and rollback proof.
