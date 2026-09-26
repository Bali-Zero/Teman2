# Portal Champion finale

Status: implemented and independently reviewed PASS in an isolated BLUE builder worktree; not deployed. Final review, condition verification and frozen hashes are recorded in [the preparation receipt](../../evidence/2026-09/agent-nuzantara-frontend-portal-champion-finale-4d7385d5/review.md).

## Product behavior

The Kita dashboard leads with the race: contender photographs, live positions, a selectable contender and the number of points needed to pass the next higher-scoring rival. The existing prize thresholds and scoring rules remain authoritative. Prize, personal prize progression, tax bonus and rules now sit inside a closed details section after the ranking and activity feed.

A scored registration produces a short full-screen goal celebration on authenticated staff pages throughout Kita, including the intake gate. It shows the scorer's staff display name, photograph and activation total. It closes automatically or by Escape, backdrop or button; keyboard focus is contained and restored, and reduced-motion preferences suppress spatial animation. Names and score fixtures in the visual evidence are synthetic.

## Event path

1. The existing registration service commits before the router schedules a background goal publication.
2. A three-second deadline bounds publication. The canonical challenge CTEs decide eligibility and score; the goal payload contains only staff presentation fields and activation count.
3. An atomic Redis operation appends to a bounded stream and deduplicates by a hash of the scoring unit. One shared reader per backend process distributes events to individual staff browser queues.
4. The staff-only SSE endpoint runs through the existing same-origin Next proxy without buffering. Native reconnects retain the event cursor; permanent failures recreate the connection with capped backoff. Replay is restricted to recent events. The server clock calibrates stale-event checks.
5. A goal invalidates the identity-scoped leaderboard query. The UI requests a fresh snapshot so an overlapping pre-goal cached request cannot freeze the standings behind the celebration. The challenge subscription stops after the fixed contest window closes.

## Verification

Current checks: 81 frontend tests and 103 backend tests pass, including eight scratch-PostgreSQL cases. TypeScript passes. Ruff passes. ESLint reports no errors and one existing workspace-layout ref-cleanup warning outside this change. The context verification helper records four successful check commands.

Evidence and synthetic previews: [desktop](../../evidence/2026-09/agent-nuzantara-frontend-portal-champion-finale-4d7385d5/portal-champion-desktop.png), [mobile](../../evidence/2026-09/agent-nuzantara-frontend-portal-champion-finale-4d7385d5/portal-champion-mobile.png), [goal](../../evidence/2026-09/agent-nuzantara-frontend-portal-champion-finale-4d7385d5/portal-champion-goal.png). The same directory contains logs, the verification receipt and frozen source hashes.

- Targeted frontend tests cover presentation order, contender selection, identity cleanup, duplicate/stale suppression, reconnect cursor, clock skew and streaming proxy behavior.
- Targeted backend tests cover the scoring rules, staff-only endpoint, fresh cache bypass, publication projection, excluded registrations, timeout and after-commit background scheduling, fanout and replay.
- A dedicated temporary Redis instance verifies the actual Lua operation, two simultaneous subscribers, reconnect replay and reader teardown.
- A real headless Chrome run renders the actual Next application at desktop and 390px mobile widths. Two native EventSource connections cross the actual Next proxy to an isolated fixture publisher; dashboard and notifications pages both celebrate, suppress a repeated ID and recover after HTTP 503. All arena images decode, the mobile page does not overflow and no page JavaScript errors occur.
- A dedicated PostgreSQL 18 scratch cluster executes the real goal SQL against temporary synthetic tables. It checks parity with canonical aggregate scoring, duplicate invites, aliases, internal addresses, deleted clients, test/pilot tags and prior activation. No production client rows or credentials were accessed.

## Release boundary and limitations

This external seat prepares only. The BLUE release owner must independently approve the candidate, commit/push/open the PR as appropriate, deploy both backend and frontend, and prove a real eligible activation reaches two authenticated production browsers. Local fixture evidence is not production proof.

Publication is best-effort after the registration commit, not a transactional outbox guarantee: registration-worker death or unavailable Redis during publication can lose that celebration, while the official score remains in PostgreSQL. Short subscriber reconnects replay events already accepted by Redis; fresh logins do not replay old celebrations. Stream retention is bounded to approximately 2,000 events and seven days. The existing shared Redis pool uses one reader connection per active backend process. Each staff browser maintains an SSE request, so production connection and hosting limits need observation during release.

The current competition ends at 2026-09-30 00:00 Asia/Makassar. No new scoring rules, prize amounts, client communications, publication or production mutation were introduced.
