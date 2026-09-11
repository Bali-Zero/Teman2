# Claude review-fix evidence — 2026-09-09

Candidate-only native runs; global Claude adapter routing remains rolled back. Codex configuration and installed hook files were retained. This record is evidence for review, not shipping or merge approval.

## Source identity

All 19 native runs below passed with these exact candidate hook bytes. All eight source files in the probe package also match this worktree byte-for-byte after the runs.

- child_workflow.py: `955b8e7a75d94acdde558216d71a0741bd68bd13586b0659a4b4505f457f6176`
- child_context.py: `7c2a6db79669b92d8fe7a6d2ba9f63e9dadc1b0645b14b87947690757dc745c8`
- mandate_budget.py: `9dc46ea662d06534ed006c5c0d6f36e744cbb8965a80a87e80185afb01207b26`

## Rollback verification

The exact pre-adapter settings backups were restored; symlinks and unrelated settings were preserved. Hook source files were unchanged. Both profiles on all three hosts were re-read with no adapter routing. M5 was already rolled back by Zero. Mini secondary had no SubagentStop hook in its backup; its exact previous configuration was restored.

| Host/profile                        | Pre-adapter backup under profile state/child-workflow-backups | Restored settings SHA-256                                        |
| ----------------------------------- | ------------------------------------------------------------- | ---------------------------------------------------------------- |
| Pro primary and symlinked secondary | 1788943865556796000/settings.json                             | 799d5ad9aea2a56d9ba8bc116ab11e69e415a13c6d7eef9c721076ee831faba3 |
| Mini primary                        | 1788943885617487000/settings.json                             | 799d5ad9aea2a56d9ba8bc116ab11e69e415a13c6d7eef9c721076ee831faba3 |
| Mini secondary                      | 1788943885620347000/settings.json                             | 117d9b726cf95a5d21e71b34895c5431585473a41354f5d9ea73156a9a88b5bc |

- Pro: audit `/Users/nuzantara/.claude/state/child-workflow-rollbacks/1788955401139056000/evidence.json`; all 58 recorded Codex files still match their pre-rollback hashes after the probes.
- Mini: audit `/Users/nuzantara/.claude/state/child-workflow-rollbacks/1788955459554396000/evidence.json`; all 10 recorded Codex files still match their pre-rollback hashes after the probes.

## Native calibration and consumers

Primary profiles only, ordinary main-repository cwd and normal recovery flags. M5 retained STOP_VERIFY_ALLOW_DIRTY=1. Candidate settings/hooks were selected per invocation; global routing was unchanged. Warmups establish native capacity. Consumers must observe usage and calibrated capacity. Returned children remain unverified until independent acceptance.

| Host | Native model / child count    | CLI     | Window / 40% limit  | Warmup session                       | Consumer session                     | Evidence directory suffix              |
| ---- | ----------------------------- | ------- | ------------------- | ------------------------------------ | ------------------------------------ | -------------------------------------- |
| M5   | claude-opus-5 / 1             | 2.1.266 | 1,000,000 / 400,000 | de7b1396-a1f8-4726-8657-30a5e56f051c | 23cb5072-78a2-4e42-8550-6a6f58b9b0e1 | claude-child-probe-1788956759949544000 |
| M5   | claude-opus-5 / 4             | 2.1.266 | 1,000,000 / 400,000 | de7b1396-a1f8-4726-8657-30a5e56f051c | 8bd3245b-11ef-4449-b9fb-53bab028c830 | claude-child-probe-1788956783158787000 |
| M5   | claude-sonnet-5 / 1           | 2.1.266 | 1,000,000 / 400,000 | bc55bfd2-ecfa-4ebc-8e7c-69e460d5319e | 190b42f3-8356-467c-8dbd-7b81eabb7a5b | claude-child-probe-1788956843196628000 |
| M5   | claude-haiku-4-5-20251001 / 1 | 2.1.266 | 200,000 / 80,000    | 50074a4a-8023-4150-b7d9-78a73283babf | c3185e52-195e-44de-b485-2559eacabd9e | claude-child-probe-1788956911715057000 |
| Pro  | claude-opus-5 / 1             | 2.1.266 | 1,000,000 / 400,000 | 725f21d9-36fa-48e6-ab52-f6db3c1d809a | 29577013-d5ab-42fc-97fe-d5d50a1254a7 | claude-child-probe-1788956820524361000 |
| Pro  | claude-sonnet-5 / 1           | 2.1.266 | 1,000,000 / 400,000 | 1394ba85-3243-4d77-bf15-c9a0f66c69fd | 643ee6a9-ac6e-4e77-a75d-6998af45120c | claude-child-probe-1788956917761789000 |
| Pro  | claude-haiku-4-5-20251001 / 1 | 2.1.266 | 200,000 / 80,000    | 3a5d1f9a-8fb9-4efd-9c4d-cea667bc5238 | f95e0a29-f66b-41ff-8db4-bd0e9aac581a | claude-child-probe-1788957040551278000 |
| Mini | claude-opus-5 / 1             | 2.1.263 | 1,000,000 / 400,000 | 8ba9f029-8094-440b-943b-7c589e863a26 | d37997d9-b2a2-43ed-9608-0122912083ee | claude-child-probe-1788956821006252000 |
| Mini | claude-sonnet-5 / 1           | 2.1.263 | 1,000,000 / 400,000 | b1ab743d-24a8-4a44-9cd2-8ee04ddac1ee | 32e4a77c-6fc8-4fc1-8ccc-cd99ee95d5e3 | claude-child-probe-1788956888991538000 |
| Mini | claude-haiku-4-5-20251001 / 1 | 2.1.263 | 200,000 / 80,000    | ba899d8c-3f8e-4260-8d15-695d600d05fa | 72f0c4a0-c391-4d6c-977c-49eda8d8cb0a | claude-child-probe-1788956976587481000 |

Evidence directories are under each host primary profile ~/.claude/state/worktrees/. Their result.json, hook payloads and corresponding native transcripts remain on that host. All consumers made two sequential Reads, had no denials, released all reservations to returned_unverified, and stopped their active clocks. The M5 four-child Opus run issued exactly four Agent calls in one parent message; every child observed a calibrated 1M window.

## Validation and open acceptance

- Targeted suite: **71 passed** across test_child_context.py, test_child_review_regressions.py, test_child_lifecycle.py and test_context_bridge.py. Ruff and whitespace checks passed.
- Regressions cover both Stop recovery flags, broken legacy Stop imports, clock pause/resume, interactive observation of all resource limits, strict eight-slot enforcement, transcript/heartbeat stale-slot accounting, strict reacquisition, UNKNOWN warnings/400k ceiling and canonical Opus calibration.
- **Native 20-minute active builder proof remains OPEN.** The deterministic 1,200-second clock test passes. Owned wall-time attempts encountered a denied standalone sleep or an asynchronous Monitor that returned the child early; neither is a 20-minute proof. This acceptance item must be closed before merge.
- Calibration is scoped to host/profile/model/version/routing and expires after seven days. This matrix proves primary profiles only; changed routing requires fresh consumer evidence.
- A suspect_zombie frees scheduling capacity and retains its record. Resumed strict tool use must reacquire capacity. This does not fence an already-running process; unavailable transcript metadata remains UNKNOWN and retains the slot.
- Fable D3 is deferred to the separate calibration-receptor pilot. No receptor, PR, pilot, merge, auto-merge or deployment was started here.
- The historical five-child/two-reservation ledger cause remains unestablished. Existing interpreter and timeout inconsistencies were preserved, not claimed fixed.
