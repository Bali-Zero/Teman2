# Sprint 0 Wrap — 2026-05-02

**Owner:** Claude Opus 4.7 (Air session, branch
`feat/sprint0-inventory-hardening`) on behalf of Antonello Siano.
**Reference:** brainstorm 2026-05-02 round 2 § "Sprint 0 — Inventory +
Hardening (1 settimana, urgente)".

## Deliverables

15 commits across 4 tracks (A: 5, B: 4, C: 3, D: 3 + 1 setup commit
for the brainstorm docs themselves). Branch pushed to origin.

### Track A — OpenClaw hardening (5 commits)

1. `feat(sprint0): logrotate for OpenClaw gateway logs (mitigates disk risk)`
   → `infra/launchagents/com.nuzantara.openclaw-logrotate.plist` +
   `scripts/openclaw-logrotate.sh` (cron 03:00 WITA, 100 MB threshold,
   gzip+truncate-in-place, 7-day retention).
2. `feat(sprint0): OpenClaw skill audit + Telegram <80 commands plan`
   → `scripts/openclaw-skill-audit.py` (read-only, runs from Air via
   SSH or local on Pro) + `docs/audits/sprint0/openclaw-skills-audit.jsonl`
   + `docs/audits/sprint0/openclaw-telegram-skills.md`. Empirical:
   92 commands → ~57-62 expected after disable plan.
3. `feat(sprint0): mcporter usage audit + disable idle plan`
   → `scripts/openclaw-mcporter-toggle.sh` + `docs/audits/sprint0/
   mcporter-usage.md`. 13 servers, 208 tools — only 13 tools have
   ever been called in 30 days. Disable list: 8 servers (docker,
   playwright, perplexity, brave-search, exa, context7,
   sequential-thinking, vercel/fetch). KEEP_FORCE: nuzantara-mcp,
   nuzantara-mcp-advanced, filesystem, memory.
4. `docs(sprint0): OpenClaw upgrade v2026.4.29 plan (rollback-safe)`
   → 5-phase plan: pre-flight → side-by-side install → sandbox test
   (isolated HOME, separate port, Lobster compile verification) →
   atomic flip → rollback procedure → 24h soak. Application order
   pre-requirements documented.
5. `docs(sprint0): claude-code 3rd agent audit + 24 frozen jobs cleanup`
   → `docs/audits/sprint0/openclaw-claude-code-agent.md` (read-only
   audit procedure for the undocumented 3rd agent, decision matrix
   document/remove) + `docs/audits/sprint0/openclaw-frozen-jobs.md`
   + `scripts/openclaw-frozen-jobs-disable.sh` (idempotent, --revert
   from latest backup).

### Track B — Audit completeness (4 commits)

6. `docs(sprint0): Bali Zero Dispatch 7-vs-9 LaunchAgents normalized`
   → empirical: repo has 13 WR2 plist, Pro launchd has 16. 4 Pro-only
   plist (`canva-apply, draft-generator, image-generator, topic-selector`)
   need rsync into repo. `canva-renderer` orphan in repo. **Verdict: 9
   is the canonical cognitive backbone count.**
7. `docs(sprint0): WR2 IPC mechanism audit (Event-driven Law compliance)`
   → all 13+4 organelle effectively respect Law 4 via DB triggers
   (mig 112/113/114/138). 1 narrow violation: `measurer` writes
   `post_metrics_history` without trigger. 1 grey area: `wr2-hardening
   chain.sh` outputs filesystem only — fits Track C2 ObservedShellBus.
8. `docs(sprint0): WR2 OpenClaw insertions duplicate detection`
   → 3 round-1 insertions (#1 L1 Connector, #2 Learner M14, #3 Trend
   pre-filter). Verdict: #1 + #2 are DUPLICATES of existing LaunchAgents
   running Claude CLI subprocess — DISMISS. #3 is genuine new capability
   but NOT YET NEEDED — DEFER until Consiglio overload is empirically
   observed; redesign as confidence-tag (not cull) per recall safety.
9. `docs(sprint0): Intel Scraper main path verification`
   → drive-poll incident (cicatrix 2026-04-29) is unrelated. Intel
   Scraper main path alive: `apps/bali-intel-scraper/` 03:00 WITA daily
   + cron-agent-python intel-radar hourly + intel-feed-processor 2h.

### Track C — Cell admission framework (3 commits)

10. `feat(cell-core): 7 Leggi admission test framework + 9 tests`
    → `packages/cell-core/cell_core/admission_test.py` (registry-based,
    1 Check per Legge, AdmissionResult.passed only if zero blockers) +
    `packages/cell-core/tests/test_admission.py` (9 tests covering all
    7 laws + summary formatting) + `docs/cell-core/admission-test-rubric.md`
    (YAML template + PASS/FAIL examples per law + 2 complete cases:
    hgt-coordinator pass, oracle-L4-standalone fail with 6 blockers).
11. `feat(cell-core): observed-shell tier (migration 151 + ObservedShellBus + tests)`
    → `apps/backend-rag/backend/db/migrations_v2/151_observed_shell_events.sql`
    (NOT 147 — collision with `federation_alert_proposals.sql`. ROLLBACK
    marker present; squawk-ignore directives on indexes for legitimate
    empty-table case) + `apps/backend-rag/backend/services/events/
    observed_shell.py` + `apps/backend-rag/backend/tests/services/events/
    test_observed_shell.py` (4 tests) + `docs/cell-core/observed-shell-tier.md`
    (lists 11 Sprint-1 migration targets).
12. `docs(cell-core): cognitive levels matrix 14 cells L0-L4.5 + 7 Leggi pre-check`
    → per-cell offline judgment on which Sprint addresses each ⚠️ in
    pre-check, with concrete remediation paths.

### Track D — Runtime register + handoff (3 commits)

13. `docs(sprint0): runtime register 200+ automations 5-tier classified`
14. `docs(sprint0): runtime ownership + Codex 3/5 criterion 14 cells`
    → 11/14 cells primary cron-agent-python; 1/14 (hgt-coordinator)
    OpenClaw; 1/14 (tech-orchestrator) hybrid; 1/14 sub-cell candidate
    OC migration Sprint 8.
15. (this doc) `docs(sprint0): wrap-up + handoff to Sprint 1`

## Audit findings consolidated

| Track | Question | Verdict |
|---|---|---|
| **B1** | "7" or "9" Bali Zero Dispatch organelle? | **9** cognitive backbone (oracle, strategos, supervisor, pg-proxy, connector, learner-nightly, trend-hunter, measurer, dossier-compiler). Operational organelle (newsletter, canva, draft, image, topic, sla-worker, hardening) bring file-count to 13/repo or 16/Pro. |
| **B2** | Do all WR2 LA respect Event-driven Law? | **Effectively yes**, with 1 narrow violation (`measurer` write without trigger) + 1 grey area (`hardening` filesystem-only) + 1 orphan (`canva-renderer`). NO PG NOTIFY migration needed for cognitive set. |
| **B3** | Are the 3 OpenClaw insertions duplicates? | **#1 + #2 yes (dismiss); #3 not duplicate but defer.** Sprint 5 freed up. |
| **B4** | Is Intel Scraper main path alive? | **Yes** — drive-poll incident orthogonal. 03:00 WITA cron alive + intel-radar hourly + intel-feed-processor 2h. |
| **D2** | OpenClaw vs cron-agent-python verdict per cell? | 11/14 cron-agent-python primary; 1/14 OpenClaw primary (hgt-coordinator); 1/14 hybrid (tech-orchestrator). |

## OpenClaw hardening artifacts

- `infra/launchagents/com.nuzantara.openclaw-logrotate.plist` (A1)
- `scripts/openclaw-logrotate.sh` (A1)
- `scripts/openclaw-skill-audit.py` (A2)
- `docs/audits/sprint0/openclaw-skills-audit.jsonl` (A2)
- `docs/audits/sprint0/openclaw-telegram-skills.md` (A2)
- `scripts/openclaw-mcporter-toggle.sh` (A3)
- `docs/audits/sprint0/mcporter-usage.md` (A3)
- `docs/audits/sprint0/openclaw-upgrade-plan.md` (A4)
- `docs/audits/sprint0/openclaw-claude-code-agent.md` (A5)
- `docs/audits/sprint0/openclaw-frozen-jobs.md` (A5)
- `scripts/openclaw-frozen-jobs-disable.sh` (A5)

## Cell admission framework

- `packages/cell-core/cell_core/admission_test.py` (C1)
- `packages/cell-core/tests/test_admission.py` (C1, 9 tests)
- `docs/cell-core/admission-test-rubric.md` (C1)
- `apps/backend-rag/backend/db/migrations_v2/151_observed_shell_events.sql` (C2)
- `apps/backend-rag/backend/services/events/observed_shell.py` (C2)
- `apps/backend-rag/backend/tests/services/events/test_observed_shell.py` (C2, 4 tests)
- `docs/cell-core/observed-shell-tier.md` (C2)
- `docs/cell-core/cognitive-levels-matrix.md` (C3)

## Runtime register

- `docs/automations/runtime-register.md` (D1)
- `docs/automations/runtime-ownership.md` (D2)
- `docs/automations/runtime-3of5-criterion.md` (D2)

## Audit findings — open questions (Pro SSH-unreachable at audit time)

This Sprint 0 was completed during a window when Pro was unreachable
via SSH (`Host is down` for the entire Track A4 onwards). Several
verifications must be re-run by Antonello once Pro is back:

- `[gap]` Verify state file timestamps for cells #1-12 (B4 procedure)
- `[gap]` Reverse-engineer schedules of the 4 Pro-only WR2 plist
  (B1 — rsync into repo)
- `[gap]` List the actual 24 frozen OpenClaw jobs (A5 Step 1)
- `[gap]` Count actual `~/.cron-agent-python/strategies/` directory
- `[gap]` Audit `~/.openclaw/openclaw.json` `agents.list[]` for
  `claude-code` (A5 part 1)
- `[gap]` Confirm `wr2.canva-renderer` LaunchAgent fate

These don't block PR review or merge — they just defer the manual
"verify on Pro" steps that follow merge.

## Action items MANUAL (pre-Sprint 1)

Owner: Antonello. Order matters; do NOT change.

1. **`Day 0` — Apply Track A2 (Telegram skill disable)** on Pro:
   - Backup `~/.openclaw/openclaw.json` to `.pre-skill-disable-2026-05-02`
   - Apply jq edits per `docs/audits/sprint0/openclaw-telegram-skills.md`
   - Verify Telegram menu count drops via gateway.log next `setMyCommands`

2. **`Day 0` — Apply Track A5 (24 frozen jobs disable + claude-code review)** on Pro:
   - Run `bash scripts/openclaw-frozen-jobs-disable.sh --apply` on Pro
   - Hot-reload OpenClaw via `launchctl kickstart -k gui/501/ai.openclaw.gateway`
   - Run the read-only `claude-code` agent audit per
     `docs/audits/sprint0/openclaw-claude-code-agent.md` Step 1
   - Decide document-or-remove based on Step 2 matrix

3. **`Day 1` — Apply Track A3 (mcporter idle disable)** on Pro:
   - Run `bash scripts/openclaw-mcporter-toggle.sh --disable-idle --dry-run` on Pro
   - Review the plan output
   - Run `--apply` to commit
   - Restart OpenClaw to re-snapshot

4. **`Day 1` — Install logrotate plist (Track A1)** on Pro:
   - `cp infra/launchagents/com.nuzantara.openclaw-logrotate.plist ~/Library/LaunchAgents/`
   - `chmod 0444` for cicatrix 2026-04-29 hardening compliance
   - `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.nuzantara.openclaw-logrotate.plist`
   - Verify by waiting for next 03:00 WITA fire OR run `bash scripts/openclaw-logrotate.sh --apply` once manually

5. **`Day 2` — Run Track A4 OpenClaw upgrade v2026.4.29** following the
   phased rollout in `docs/audits/sprint0/openclaw-upgrade-plan.md`. Off-peak
   (~22:00 WITA). 24h soak after Phase 3.

6. **`Day 2-3` — Migration 151 deploy.** Auto-applied by `fly-deploy.yml`
   `run-sql-v2-migrations-post-deploy` job once the PR merges and the next
   CI run completes (cicatrix lesson — happens automatically; verify via
   `psql -c "\d observed_shell_events"` post-deploy).

7. **`Day 3` — Runtime dismissal**: rm `~/Jules`, `~/kradle`, `~/.kimi`
   directories. Freeze `~/.cagent` (no autostart, no new strategies).
   Limit `~/claude-squad` scope to git/PR only.

8. **`Day 3-7` — WR2 deltas** (per Tracks B1-B2 follow-ups):
   - Decide fate of `wr2.canva-renderer` LaunchAgent (rename or delete)
   - rsync 4 Pro-only WR2 plist into `infra/launchagents/`
   - Sprint 1 W1 work: add `measurer_event` channel + trigger on
     `post_metrics_history`

## Sprint 1 ready

Pre-conditions for Sprint 1 start:

- [ ] Action items 1-7 above completed
- [ ] Migration 151 confirmed applied on prod (via `\d observed_shell_events`)
- [ ] OpenClaw v2026.4.29 verified stable on Pro (24h soak)
- [ ] Cell admission framework tests passing in CI (verified via PR check)

Sprint 1 deliverables (per `99b_synthesis_v2.md` § Sprint 1):

- **`intel-scraper-cell` light** (Genome scar registry + HGT publisher +
  event bridge). NO PulseLoop, NO Homeostasis. Mostly observability
  instrumentation per cogitive-levels-matrix.md row #8.
- **`hgt-coordinator-cell` standalone propose-only quarantine** (Kimi K2.6
  via OpenClaw — the only cell where OC is primary). ≥10 uses + conf>0.7
  gate enforced inside the cell.

Sprint 1 estimated 1 week, 2-3 PRs. Owner: Antonello + (future) Asya.

## References

- All Sprint 0 docs: `docs/audits/sprint0/*.md` + `docs/cell-core/*.md`
  + `docs/automations/*.md`
- Brainstorm round 1+2: `docs/audits/2026-05-02-cell-openclaw-brainstorm/`
- Cicatrix log: `.claude/rules/cicatrix-scars.md`
- Symbiosis principles: `SYMBIOSIS.md`
- Vademecum: `VADEMECUM.md`
- Atlas: `INDEX.md`
