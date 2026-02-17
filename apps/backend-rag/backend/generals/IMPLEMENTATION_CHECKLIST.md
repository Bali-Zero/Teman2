# IMPLEMENTATION CHECKLIST: The Generals

This checklist guides the transformation of Workers into Autonomous Agents.

## Phase 1: Foundation (The Constitution)

- [ ] **Enforce AI_ONBOARDING**
  - [ ] Add `pre-commit` hook to reject commits violating Golden Rules.
  - [ ] Create `tests/compliance/test_onboarding.py` to auto-check new code.

- [ ] **Shared Memory & Locking**
  - [ ] Create `generals_locks` table in Postgres (see Architecture doc).
  - [ ] Implement `GeneralsMemory.acquire_lock(resource, ttl=60)` in `task_coordinator.py`.
  - [ ] Update `TaskCoordinator` to respect locks.

## Phase 2: The Core Generals (Upgrade)

### Coding General

- [ ] Implement `GithubClient` (read issues, comment on PRs).
- [ ] Implement `SentryClient` (fetch new errors).
- [ ] Add `git` capability: `checkout -b`, `add`, `commit`, `push`.
- [ ] **Autonomy Test:** Make it fix a dummy bug and merge its own PR.

### Intelligence General

- [ ] Integrate `BaliIntelScraper` results directly into memory.
- [ ] Add `UserRequest` listener (WebSocket or API polling).
- [ ] Implement `ReportGenerator` (Markdown -> PDF/HTML).

### Antigravity General

- [ ] **Refactor:** Move from AppleScript-only to System Orchestrator.
- [ ] Add `FlyClient` (monitor deployments, restart machines).
- [ ] Add `HealthMonitor` (check DB connections, disk space).
- [ ] Implement `ConflictResolver` (unlock stuck tasks).

## Phase 3: The New Generals (Expansion)

### Perplexity General (New)

- [ ] Create `apps/backend-rag/backend/generals/perplexity_general.py`.
- [ ] Integrate `Perplexity API` (sonar-deep-research).
- [ ] Implement `FactChecker` loop (Claim -> Verify -> Verdict).

### Marketing & Media General (New)

- [ ] Create `apps/backend-rag/backend/generals/marketing_general.py`.
- [ ] Connect to `zantara-media` content pipeline.
- [ ] Add `SocialPublisher` (Twitter/LinkedIn API mock interface first).

## Phase 4: Triggers & Events

- [ ] **Cron System**
  - [ ] Deploy a dedicated `cron` service or use `APScheduler` in `run_generals.py`.
  - [ ] Load schedules from `CRON_SCHEDULES.yaml`.

- [ ] **Event Bus**
  - [ ] Simple Postgres `NOTIFY/LISTEN` channel `generals_events`.
  - [ ] Agents subscribe to events (e.g., `DEPLOY_FAILED`, `NEW_BLOG_POST`).

## Phase 5: Drill & Verify

- [ ] **Chaos Monkey Test:** Simulating a DB failure and seeing if Antigravity handles it.
- [ ] **Conflict Test:** Assign same task to Coding and Intelligence -> Check locking.
- [ ] **Compliance Test:** Try to commit hardcoded secret -> Check rejection.
