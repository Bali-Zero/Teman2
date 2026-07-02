# modus — PENDING-ARMS (the W81 ledger: built ≠ armed)

> Anything created-but-not-{merged, installed, propagated, armed} lands here at SHIP+ARM and is
> re-read at TRIAGE of every subsequent modus run. Remove a line ONLY when the arming is PROVEN
> live (a probe of the work, never an exit code). Distinguish legitimate firebreaks (operator
> gate, Legge 5, business decision) from tech debt — say which it is.
>
> Format: `opened YYYY-MM-DD | artifact | missing arming step | owner (me|operator) | proof-of-armed`

- opened 2026-07-02 | DeepSeek V4 Pro refuter tier | balance top-up — probed live this day: HTTP 402 Insufficient Balance (2nd consecutive council with the seat dead) | operator | a 1-token chat/completions call returns 200
- opened 2026-07-02 | escalations receptor (`scripts/hooks/escalations_alert_sessionstart.sh`, PR #1852) | hooks entry ships with the modus PR in repo `.claude/settings.json`; liveness provable only at next session boot per machine | me | a nuzantara session boot shows the "🚨 ESCALATIONS BOARD" block (or a manual run emits valid hook JSON with current board state)
- opened 2026-07-02 | main-checkout pull on Pro (`~/Desktop/nuzantara`) — pull aborts on sibling's untracked `apps/wa-mirror/bridge/group_subject.ts` | PENDING-ALIGN:Pro — sibling wa-mirror/mata-garuda work in flight; self-resolves once the sibling lands or moves the file | operator (or next clean session) | `git -C ~/Desktop/nuzantara rev-parse HEAD` on Pro contains 3509f3e2ab content (blob check)

## closed (proof recorded)

- closed 2026-07-02 | opus-mythos deprecation banner M5+Pro+Mini | operator ran the idempotent one-liner on all 3 | PROVEN: `grep -c SUPERSEDED` = 2 on M5, Pro, Mini (description prefix + body banner); live skill registry on M5 reloaded with the superseded description
- closed 2026-07-02 | main-checkout pull on M5 (PENDING-ALIGN:M5) | operator pulled same-day | PROVEN: HEAD `3509f3e2ab`, `.claude/skills/modus/SKILL.md` present, receptor hook wired in `.claude/settings.json`
- opened 2026-07-02 | 9 dead/unhealthy heartbeat organs (doctrine §8, 2026-06-30) | heartbeat writer/bridge investigation on Pro — restart is NOT the cure | operator | organism_alert boot receptor shows 0 stale-critical organs
