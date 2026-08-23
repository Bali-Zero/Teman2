---
adversarial_review: exempt-frozen-spec-landed-verbatim-from-10d500e1c
---

# Research OS Dispatch Manifest

**Template version:** `research-os/dispatch-v1.0.0`
**Rule:** instantiate and freeze this manifest before a child session edits any file

This manifest is the immutable execution envelope for one work packet. It prevents a good architecture from becoming ambiguous parallel work. The Conductor fills every required field, the implementer confirms it before editing, and the independent reviewer receives the same hash-addressed revision. Progress and completion are appended as separate `DispatchStateReceipt` records; the manifest is never edited in place.

## 1. Dispatch identity

```yaml
dispatch_manifest_id: uuid
dispatch_family_id: stable namespaced identifier
revision: positive integer
supersedes_dispatch_manifest_ref?: {dispatch_manifest_id, object_hash}
research_os_version: research-os/v1.0.0
packet_id: "NN"
packet_path: absolute path
objective: one bounded, testable outcome
created_at: UTC timestamp
created_by: purpose-bound Conductor reference
recorded_at: UTC timestamp
object_hash: sha256
```

The first revision has no predecessor. Every replacement binds the exact current manifest ID and hash, increments `revision`, records a later timestamp, and appends an `ObjectSuccessorEdge` in the dispatch family. Forks, stale predecessors, missing hashes, or in-place edits invalidate the dispatch. A new revision changes prospective scope only; it never retroactively authorizes or rewrites an observed effect.

## 2. Repository and machine truth

```yaml
base_commit: full git SHA
source_branch: exact branch
worktree_path: absolute dedicated worktree path
work_branch: codex/ or agent/ feature branch
execution_machine: Pro | Mini-Pro2 | Air-M5
authoritative_machine: Pro
peer_sync_result: exact verified result and timestamp
```

Rules:

- Editing never begins in the main checkout.
- Air-M5 may edit its isolated worktree and operate lightweight control clients. Heavy processing, databases, protected data, NEXUS, rendering, and daemon work remain on Pro or Mini-Pro2 as routed by `AGENTS.md`.
- An unreachable Pro is a stop condition for work that requires live or protected truth; it is not permission to install a substitute on Air-M5.

## 3. Exact ownership and shared leases

```yaml
owned_files:
  - exact file or narrow glob
read_only_dependencies:
  - exact file, service, or schema
forbidden_files:
  - exact protected paths from AGENTS.md and packet boundary
shared_leases:
  - resource: migration registry | router registry | contract export | queue schema | other
    owner_dispatch_id: uuid
    acquired_at: timestamp
    expires_at: timestamp
migration_reservation:
  number: integer | none
  frozen_purpose: string | none
  ledger_version: research-os/v1.0.0
```

Any ownership collision, expired lease, or occupied migration number stops mutation until the Conductor issues a versioned replacement manifest.

## 4. Authority and side-effect ceiling

```yaml
allowed_side_effects:
  filesystem: read | isolated_worktree_write | exact_production_write
  database: none | disposable_test_only | read_only_authoritative | exact_production_write
  network: none | public_read_only | approved_service_health_only | exact_production_write
  external_messages: none | exact_recipient_send
  publication: none | exact_revision_publish
  deployment: none | exact_release_deploy
  production_flags: none | exact_flag_transition
  scheduler: none | exact_job_activation
  service_control: none | exact_service_restart
  secret_rotation: none | exact_named_secret_rotation
  paid_usage: none | named subscription or pre-authorized service with numeric ceiling
effect_authority:
  - effect_type: registered exact effect from allowed_side_effects
    target_and_arguments_hash: sha256
    action_intent_ref: {action_intent_id, object_hash}
    approval_receipt_ref: {approval_receipt_id, object_hash}
    approved_scope_hash: sha256
    expires_at: timestamp
explicitly_forbidden:
  - merge
  - push to main
  - deploy
  - publish
  - send client or team communication
  - mutate CRM or protected OSINT
  - arm LaunchAgent or scheduler
```

The default manifest uses the narrowest value and an empty `effect_authority` list. A work packet may lower the ceiling but cannot raise it. A successor manifest may represent a production side effect only when every effect has an exact, unexpired owner `ApprovalReceipt` bound to the exact `ActionIntent`, target, arguments, scope, and effect type. The started action then creates an immutable `ExecutionAttempt` and a terminal typed `OperationalReceipt`; the manifest itself is neither approval nor proof of execution. `explicitly_forbidden` remains authoritative for every effect not removed by that exact successor revision, and review approval can establish eligibility but can never substitute for owner action authority.

## 5. Privacy, sources, and model routing

```yaml
maximum_input_sensitivity: public | internal | confidential | restricted_osint | client_pii
permitted_processing_location: Air-M5 | Pro-only | Mini-Pro2-only
cloud_prompt_policy: public_minimized_only | no_cloud
source_registry_snapshot: durable path and hash
notebooklm_route: notebook ID/alias or none
llm_route: exact sanctioned model cascade or none
redaction_policy_version: string
retention_policy_version: string
```

No prompt, fixture, log, report, commit, or artifact may contain raw client PII, protected OSINT, secrets, or private locations. IDs, hashes, aggregates, and approved sanitization receipts are used instead.

## 6. Baseline, fixtures, and preregistered measurement

```yaml
baseline:
  observed_at: timestamp
  commands_or_probes: [exact read-only command or test]
  counts_latency_failures_side_effects: structured reference with hash
golden_set_paths: [absolute or repository-relative path]
adversarial_fixture_paths: [path]
metric_profile_refs: [{metric_profile_id, object_hash}]
operating_window:
  domain_cycle: exact definition
  starts_at: timestamp or relative rule
  ends_at: timestamp or relative rule
  late_arrival_policy: string
  required_complete_windows: 2 or stricter packet value
```

An operating window covers one complete expected producer-to-outcome cycle and is frozen before results are observed. Thresholds, sample floors, denominators, exclusions, confidence method, and guardrails come from exact canonical `MetricProfile` revisions. Bare IDs, mutable paths, or profile aliases cannot govern a release decision.

## 7. Flags, cost, rollback, and failure boundaries

```yaml
feature_flags:
  - name: exact flag
    default: off
    permitted_phase: tests | shadow | canary | owner_authorized_live
cost_ceiling:
  unit: credits | tokens | currency | runtime
  hard_limit: numeric value
  preflight_source: exact live or fixture source
rollback:
  code_point: commit or tag
  data_strategy: additive rollback or disposable test reset
  command_or_runbook: exact reference
  owner: role
hard_stop_conditions:
  - stale or missing authoritative baseline
  - contract validation failure
  - privacy or secret exposure
  - unknown external effect
  - cost truth unavailable
  - migration or shared-file collision
  - golden-set regression beyond preregistered tolerance
```

## 8. Required commands and evidence

```yaml
discovery_commands: [exact commands]
implementation_tests: [exact commands]
security_privacy_tests: [exact commands]
evaluation_commands: [exact commands]
reconciliation_commands: [exact commands]
diff_checks: [exact commands]
expected_artifacts:
  - path
  - schema/version
  - required hash
```

Commands run from the declared worktree and approved virtual environment. A fixture-only PASS is never labeled live readiness.

## 9. Independent review

```yaml
implementer: session or agent reference
reviewer: different session or model reference
independence_requirement: generator_not_equal_grader
review_inputs:
  - immutable dispatch manifest
  - diff
  - baseline and post-change evidence
  - golden/adversarial results
  - exact MetricProfile, MetricResult, and metric-bearing OutcomeEvent references where applicable
  - rollback proof
allowed_verdicts: pass | pass_with_limits | fail | insufficient_evidence
```

The reviewer reruns the critical tests and checks the actual implementation boundary. Self-review cannot open a canary, release gate, migration integration, or retirement.

## 10. Append-only state, completion, and handoff

```yaml
dispatch_state_receipt_id: uuid
dispatch_manifest_ref: {dispatch_manifest_id, object_hash}
previous_state_receipt_ref?: {dispatch_state_receipt_id, object_hash}
status: prepared | accepted | implementing | review_ready | passed | failed | superseded
recorded_at: UTC timestamp
producer: {name, version}
completion?:
  final_commit: full SHA
  files_changed: [exact paths]
  tests_and_results: [structured references with hashes]
  metric_result_refs: [{metric_result_id, object_hash}]
  metric_bearing_outcome_event_refs: [{outcome_event_id, object_hash}]
  unresolved_gaps: []
  side_effects_observed: [{execution_attempt_id, object_hash, operational_receipt_id, operational_receipt_hash}]
  migration_state: not_created | created_not_applied | applied_test_only
  flags_state: exact values
  reviewer_verification_receipt_ref: {verification_receipt_id, object_hash}
  next_authorized_step: none unless separately dispatched
object_hash: sha256
```

State receipts are immutable and form one exact predecessor chain for each manifest revision. A metric-bearing dispatch cannot reach `passed` without the exact preregistered profile reference, its exact `MetricResult`, and the subsequent metric-bearing `OutcomeEvent` bound to both hashes. A completed packet prepares evidence for the next gate. It never implies merge, deploy, scheduler activation, public publication, client communication, production migration, or retirement authority.
