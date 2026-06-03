---
date: 2026-05-25
domain: operations
client_case: pro-orchestrator-audit
sources:
  - git branch -a (local + remote)
  - git worktree list
  - git stash list
  - ps aux claude/codex
  - launchctl list
---

# Pro Cleanup State Snapshot — 2026-05-25 22:00 WITA

Pre-cleanup snapshot before full-sweep operation requested by Antonello.
This file is the rollback authority — every delete below references this snapshot.

## Active processes (claude/codex)

nuzantara        36667  28,5  1,3 509236048 647040 s010  R+   10:30PM  55:34.75 claude
nuzantara         4515   0,3  1,0 508788096 509488 s018  S+    5:56PM   3:28.27 claude
nuzantara        66115   0,2  1,3 509249856 641248 s013  S+    9:45AM  24:35.01 claude
nuzantara        34716   0,0  0,1 435793536  34528 s008  S     8:17AM   0:01.21 /Applications/Codex.app/Contents/Resources/codex app-server --listen stdio://
nuzantara        34618   0,0  0,3 435805808 133792 s008  S+    8:17AM   4:43.80 /opt/homebrew/lib/node_modules/@openai/codex/node_modules/@openai/codex-darwin-arm64/vendor/aarch64-apple-darwin/bin/codex
nuzantara        34617   0,0  0,1 436122704  34688 s008  S+    8:17AM   0:00.43 node /opt/homebrew/bin/codex
nuzantara        30285   0,0  0,0 435307584   5024   ??  S    10:47PM   0:00.10 /Users/nuzantara/.codex/plugins/cache/openai-bundled/chrome/latest/extension-host/macos/arm64/extension-host chrome-extension://hehggadaopoacecdllhhajmbjkdcmajg/
nuzantara        54316   0,0  0,0 435269616  10672   ??  S    sab03AM   0:31.24 /opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/Resources/Python.app/Contents/MacOS/Python /Users/nuzantara/.claude/daemons/guardrails.py
nuzantara         4268   0,0  0,0 435303488   2832   ??  SN   ven05PM   0:19.53 /bin/bash /Users/nuzantara/scripts/codex/spark-loop.sh
nuzantara        13633   0,0  0,0 435300128    560   ??  S    ven05PM   0:15.02 tail -F -n 0 /Users/nuzantara/.claude/skills/bali-zero-brand/logs/canva-apply.log

## Worktrees BEFORE cleanup
```
/Users/nuzantara/Desktop/nuzantara                                             4562e29df [chore/cicatrix-cleanup-2026-05-25]
/private/tmp/wt-lid-fix                                                        2a4626d3f [fix/wa-mirror-lid-direct-2026-05-25]
/private/tmp/wt-pr-853-rebase                                                  61fb14d02 [feat/redis-lease-registry-2026-05-24]
/Users/nuzantara/Desktop/nuzantara-claude-workflow-2026-05-25                  b8df2f996 [feat/ai-agent-workflow-spec-2026-05-25]
/Users/nuzantara/Desktop/nuzantara-crm-guardian-drive                          0a7ef76c5 [main]
/Users/nuzantara/Desktop/nuzantara-deploy                                      4a4db81f9 [chore-cicatrix-rebase]
/Users/nuzantara/Desktop/nuzantara-wa-dashboard-m1                             dca53bf9b [feat/wa-dashboard-m1-readonly-2026-05-25]
/Users/nuzantara/Desktop/nuzantara/.worktrees/codex-autofix-ci-runtime         61fb14d02 (detached HEAD)
/Users/nuzantara/Desktop/nuzantara/.worktrees/codex-coverage-improver-runtime  fce272c83 (detached HEAD)
/Users/nuzantara/Desktop/nuzantara/.worktrees/codex-research-actor-runtime     fce272c83 (detached HEAD)
```

## Stash list BEFORE cleanup (49 entries)
```
stash@{0}: On chore/cicatrix-cleanup-2026-05-25: codex-preserve-before-main-realign-2026-05-25
stash@{1}: On main: docsync-counts-2026-05-25-stop-10
stash@{2}: On main: session-stop-message-capture-sibling-2026-05-25
stash@{3}: On main: session-stop-readme-onboarding-from-sibling-rebase-2026-05-25
stash@{4}: On main: session-stop-docsync-cron-readme+ai_onboarding-2026-05-25
stash@{5}: On main: sibling-orphan-wa-copilot-2026-05-25-stop-resolution
stash@{6}: On main: sibling+cron-orphan-2026-05-25-stop-8-massive-11files-migrations+monitoring
stash@{7}: On main: sibling-orphan-2026-05-25-stop-7-wa-copilot-action-queue-rules
stash@{8}: On feat/ai-agent-workflow-spec-2026-05-25: docsync-cron-2026-05-25
stash@{9}: On main: sibling+cron-orphan-2026-05-25-stop-6-multi-source
stash@{10}: On feat/ai-agent-workflow-spec-2026-05-25: docsync-cron-counts-update-2026-05-25
stash@{11}: On main: sibling-orphan-2026-05-25-stop-5-wa-copilot-kg-bridge-S16
stash@{12}: On main: cicatrix-scars-half-archive-2026-05-25-preserve-before-clean
stash@{13}: On main: cicatrix-archive-auto-2026-05-25-stop
stash@{14}: On feat/ai-agent-workflow-spec-2026-05-25: cicatrix-archive-auto-2026-05-25-stop
stash@{15}: On feat/ai-agent-workflow-spec-2026-05-25: sibling-orphan-2026-05-25-stop-5-mcpserver
stash@{16}: On feat/ai-agent-workflow-spec-2026-05-25: sibling-orphan-2026-05-25-stop-5-router
stash@{17}: On feat/ai-agent-workflow-spec-2026-05-25: sibling-orphan-2026-05-25-stop-5-mcp
stash@{18}: On feat/ai-agent-workflow-spec-2026-05-25: sibling-orphan-2026-05-25-stop-5
stash@{19}: On feat/ai-agent-workflow-spec-2026-05-25: sibling-orphan-2026-05-25-stop-4
stash@{20}: On feat/ai-agent-workflow-spec-2026-05-25: sibling-orphan-2026-05-25-stop-3
stash@{21}: On main: sibling-orphan-2026-05-25-stop-2
stash@{22}: On main: sibling-orphan-2026-05-25-during-s13-fix
stash@{23}: On main: sibling+cron-orphan-2026-05-25-pre-stop
stash@{24}: On main: sibling-orphan-test-changes-2026-05-25-pre-S134-relaunch
stash@{25}: On main: session-stop-orphan-sibling-2026-05-25-backend-rag-tests-unit-batch3
stash@{26}: On main: session-stop-orphan-sibling-2026-05-25-backend-rag-test-updates-batch2
stash@{27}: On main: session-stop-orphan-sibling-2026-05-25-backend-rag-test-updates
stash@{28}: On main: sibling-orphan-test-changes-2026-05-25-04-37
stash@{29}: On feat/wa-dashboard-m1-readonly-2026-05-25: session-stop-orphan-sibling-2026-05-25-wa-dashboard-m1-readme-pkglock
stash@{30}: On chore/cicatrix-2026-05-25-gap-fixes-and-tests: session-stop-orphan-sibling-2026-05-25-cicatrix-readme-aiOnboarding-updates
stash@{31}: On main: session-stop-orphan-sibling-2026-05-25-wa-dashboard-nextjs-multipage
stash@{32}: On main: session-stop-orphan-sibling-2026-05-25-wa-copilot-identity-audit-nb-health
stash@{33}: On program/base: wr2-rescue-pre-checkout-2026-05-25
stash@{34}: On main: session-stop-orphan-sibling-2026-05-25-wa-copilot-mig-200
stash@{35}: On main: session-stop-orphan-sibling-2026-05-25-wa-corpus-monetization-panel
stash@{36}: On main: session-stop-orphan-sibling-2026-05-25-god-test-v2-results
stash@{37}: On fix/bound-background-loops-pool-2026-05-25: wip-sibling-published-articles-json-2026-05-25
stash@{38}: On main: session-stop-2026-05-25-wa-dashboard-features: 5 files staged by other session
stash@{39}: On main: session-stop-2026-05-25-sibling-claude-cli-god-test
stash@{40}: On feature/wr2-event-driven: session-stop-2026-05-24-sibling-ai-dispatch-tri-llm
stash@{41}: On feature/wr2-event-driven: session-stop-2026-05-24-sibling-cicatrix-automations
stash@{42}: On chore/sota-synthesis-restore: session-stop-2026-05-24-sibling-husky-agents-pro-air
stash@{43}: On chore/sota-synthesis-restore: session-stop-arsenale-audit-2026-05-24-qdrant-marker
stash@{44}: On chore/sota-synthesis-restore: session-stop-2026-05-24-m1-residuals-from-parallel-sessions
stash@{45}: On chore/sota-synthesis-restore: session-stop-2026-05-24-mos-plus-spec
stash@{46}: On chore/sota-synthesis-restore: session-stop-2026-05-24-secrets-dir-noise
stash@{47}: On chore/sota-synthesis-restore: session-stop-2026-05-24-wa-mirror-query
stash@{48}: On feat/agent-worktree-broker-2026-05-24: wip-pre-lease-registry-2026-05-24
```

## Local branches BEFORE cleanup
```
74 minutes ago | main | <nuzantara@nuzantara.tail461666.ts.net> | 0a7ef76c5
8 hours ago | chore/cicatrix-cleanup-2026-05-25 | <nuzantara@nuzantara.tail461666.ts.net> | 4562e29df
9 hours ago | feat/wa-dashboard-m1-readonly-2026-05-25 | <nuzantara@nuzantara.tail461666.ts.net> | dca53bf9b
9 hours ago | fix/fly-toml-api-oom-emergency-2026-05-25 | <nuzantara@nuzantara.tail461666.ts.net> | c65967f30
10 hours ago | fix/wa-mirror-lid-direct-2026-05-25 | <antonellosiano@gmail.com> | 2a4626d3f
11 hours ago | chore-cicatrix-rebase | <nuzantara@nuzantara.tail461666.ts.net> | 4a4db81f9
12 hours ago | feat/redis-lease-registry-2026-05-24 | <nuzantara@nuzantara.tail461666.ts.net> | 61fb14d02
12 hours ago | deploy/main | <zero@balizero.com> | 2c773a294
13 hours ago | feat/ai-agent-workflow-spec-2026-05-25 | <nuzantara@nuzantara.tail461666.ts.net> | b8df2f996
17 hours ago | chore/cicatrix-2026-05-25-gap-fixes-and-tests | <nuzantara@nuzantara.tail461666.ts.net> | aea921126
23 hours ago | chore/sota-synthesis-restore | <nuzantara@nuzantara.tail461666.ts.net> | ba033df49
27 hours ago | feat/merge-queue-rulesets-2026-05-24 | <claude@zantara.com> | b53c465c0
28 hours ago | cherry/846-chat-tests-only | <claude@zantara.com> | e544b4689
28 hours ago | cherry/805-portal-notifications-ui | <claude@zantara.com> | 635fc1a8e
28 hours ago | cherry/835-palette-ui-only | <claude@zantara.com> | 15db080d8
34 hours ago | codex/auto-fix-ci-26349779566 | <claude@zantara.com> | 5cb272f61
35 hours ago | codex-overnight/spark-alarm-20260524_103238-spark-dispatch-20260524_101225-scout-4668b729fde6-20260524_103238 | <claude@zantara.com> | c5a40f41d
2 days ago | codex-overnight/spark-alarm-20260524_100806-spark-dispatch-20260524_094252-scout-aa7701382deb-20260524_100806 | <claude@zantara.com> | 002d8c08f
2 days ago | codex-overnight/spark-alarm-20260524_093742-spark-dispatch-20260524_092503-scout-9b6e9025f6ef-20260524_093742 | <claude@zantara.com> | c023b89e1
2 days ago | codex-overnight/spark-alarm-20260524_091022-spark-dispatch-20260524_084913-scout-c0358ab8a94a-20260524_091022 | <claude@zantara.com> | b9766ccc5
2 days ago | codex-overnight/spark-alarm-20260524_084529-spark-dispatch-20260524_084309-scout-1421f4f7fa53-20260524_084529 | <claude@zantara.com> | 7c76b0d7c
2 days ago | saved/mouth-auth-test-coverage-codex | <claude@zantara.com> | bea491bc0
2 days ago | worktree-audit-nb-automations-2026-05-21 | <claude@zantara.com> | 8dc056059
2 days ago | program/base | <noreply@balizero.com> | 7902ac05d
2 days ago | codex/coverage-device-id | <claude@zantara.com> | 51f950e63
2 days ago | cleanup/whatsapp-export-backfill-20260521 | <zero@balizero.com> | a2c6cc91b
2 days ago | codex/crm-guardian-ocr-2026-05-19 | <claude@zantara.com> | 437111ef6
2 days ago | ops/hardening-2026-05-19 | <claude@zantara.com> | ad7e3d52e
2 days ago | codex/coverage-owner-access | <claude@zantara.com> | 5afc1d7a4
2 days ago | saved/mouth-untracked-coverage-tests | <claude@zantara.com> | dacbc817f
2 days ago | codex/coverage-dashboard-metrics | <claude@zantara.com> | 9c9b3baaf
2 days ago | saved/t2.7-chat-data-amendments | <claude@zantara.com> | 005b405a0
2 days ago | codex/coverage-use-previous | <claude@zantara.com> | e45951fe0
2 days ago | saved/codex-orphan-697c | <claude@zantara.com> | 1727973f2
2 days ago | saved/codex-orphan-69bb | <claude@zantara.com> | ea25b04a0
2 days ago | saved/codex-orphan-3af4 | <claude@zantara.com> | 9e27cda65
2 days ago | fix/wr2-canva-reconcile-checked-20260523 | <claude@zantara.com> | 0c9466f0a
2 days ago | saved/codex-orphan-c4d3 | <claude@zantara.com> | 332d347f6
2 days ago | saved/codex-orphan-557c | <claude@zantara.com> | d9d57d9f6
2 days ago | saved/audit-cell-genoma-organism | <claude@zantara.com> | 09f2e6faf
2 days ago | saved/codex-orphan-3d49 | <claude@zantara.com> | 16976da2b
3 days ago | chat-data-extract-2026-05-23 | <claude@zantara.com> | 66f139c9e
3 days ago | codex/coverage-loop-20260523 | <claude@zantara.com> | b238bdaf7
3 days ago | saved/wa-mirror-f1-historical-ingestion | <claude@zantara.com> | c11d2ac75
4 days ago | fix/crm-guardian-agy-cli-2026-05-22 | <claude@zantara.com> | 56eb322e4
5 days ago | sancho/inbox-auto-refresh-2026-05-20 | <claude@zantara.com> | 55be05d88
6 days ago | chore/outbox-drain-log-routing-2026-05-20 | <claude@zantara.com> | 1d5fa87cf
6 days ago | chore/intel-lake-rules-ssot-2026-05-20 | <claude@zantara.com> | 967528bfa
6 days ago | fix/wr2-supervisor-zombie-2026-05-20-clean | <claude@zantara.com> | 3e3ef05eb
6 days ago | hardening/disk-watchdog-2026-05-19 | <claude@zantara.com> | 1540ec04c
7 days ago | feat/wr3-room-genesis | <claude@zantara.com> | 18d5130a8
8 days ago | feat/tax-genius-ingest-whitelist-2026-05-18 | <claude@zantara.com> | 24d95a0c1
8 days ago | saved/cockpit-v1-widgets | <claude@zantara.com> | ec457ae26
10 days ago | docs/r5-phase2-indexing-parity-audit-2026-05-16 | <claude@zantara.com> | bb6ab1d23
3 weeks ago | saved/sprint-1b-scar-antibody-tests | <noreply@anthropic.com> | f0a548bd1
```

## Local-only branches (no remote tracking) — DELETE candidates
```
chat-data-extract-2026-05-23
chore/intel-lake-rules-ssot-2026-05-20
chore/outbox-drain-log-routing-2026-05-20
codex/coverage-dashboard-metrics
codex/coverage-device-id
codex/coverage-loop-20260523
codex/coverage-owner-access
codex/coverage-use-previous
fix/wa-mirror-lid-direct-2026-05-25
fix/wr2-supervisor-zombie-2026-05-20-clean
program/base
saved/audit-cell-genoma-organism
saved/cockpit-v1-widgets
saved/codex-orphan-3af4
saved/codex-orphan-3d49
saved/codex-orphan-557c
saved/codex-orphan-697c
saved/codex-orphan-69bb
saved/codex-orphan-c4d3
saved/wa-mirror-f1-historical-ingestion
```
