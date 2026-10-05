---
date: 2026-10-06
domain: operations
subject: cicatrix-sweep-batch-b-esiste-armato
status: CENSUS — 5 fresh Esiste≠Armato findings, 6 already tracked; no code changed
author: kimi (external-builder seat, Air-M5)
adversarial_review: exempt-census-every-claim-carries-its-reproducing-command-and-ledger-grep-grading-is-the-claude-verifier-session-named-in-the-builder-contract
---

# Cicatrix sweep 2026-10-06 — Batch B: Esiste≠Armato + name-promises-check census

- **Lane:** `agent/air-m5/docs/cicatrix-sweep-1006` (worktree `.worktrees/docs-cicatrix-sweep-1006`), based on fresh `origin/main` @ `83237f8f93`.
- **Scope:** mechanically-checkable instances of superscar family **#2 (Esiste≠Armato)** and the pattern the task brief calls **#3 ("the name promises a check the code never performs" — declared-but-unread flags/config fields)**.
- **Ledger discipline:** every candidate was grepped against `.claude/skills/modus/PENDING-ARMS.md` (2,576 lines) by exact artifact name before being written up. 5 fresh findings, 6 already-tracked items (Appendix A).
- **Census only:** no code was changed; every "minimal arm" is a suggestion.

## Naming note (discrepancy, recorded)

`.claude/rules/cicatrix-superscar.md` labels family **#3 as "Guard-over-match / UNDER-match"** (substring guards), while the task brief and PENDING-ARMS row 35 both use "#3" for "the name promises a check the code never performs" (dead declarations). Both hunts were run; the dead-declaration family produced 0 fresh findings beyond what row 35 already covers (see Appendix A), so the fresh findings below are all family #2.

## Method and positive controls (each probe proven able to go non-zero)

1. **Required-contexts probe.** `gh api repos/Bali-Zero/Teman2/branches/main/protection --jq '.required_status_checks.contexts'` measured live: **15 contexts today**. Compared against all 126 `pull_request`/`merge_group`-triggered jobs across 129 workflow files. Positive control: the same comparison surfaced `wr3-spend-gate-tests` as unarmed in ledger row 294 — the probe fires.
2. **continue-on-error census.** `grep -n 'continue-on-error: true' .github/workflows/*.yml` minus comment lines → **28 real YAML keys**. 27 of 28 are either self-documented advisory-by-design (with in-file measured-evidence comments) or ledgered; the one fresh instance is Finding 2.
3. **Orphan-script probe.** All `scripts/*.py|sh` named `check|audit|lint|verify|guard|probe|sentinel|watch*` (67 files) cross-referenced against `.github/workflows/`, `.husky/`, then a repo-wide executor grep (any file type, excluding docs/research/evidence). Positive control: the same probe returns `verify_mcp_integrity.sh → com.nuzantara.mcp-integrity.plist` (armed) and `audit_launchd_crons.py → infra/launchagents/wrappers/audit-launchd-daily.sh` (armed) — the probe discriminates armed from orphaned.
4. **Ledger probe.** `grep -ci <artifact> .claude/skills/modus/PENDING-ARMS.md`. Positive control: `token-contrast-tests` → row 1654, `wr3-spend-gate` → row 294, `sensitive` → row 35.
5. **Dead-field probe (the `sensitive:` pattern).** Hot registries parsed for declared keys vs consumers. Positive control + the one big hit are both already ledgered (row 35); the largest remaining registry (`scripts/verify_the_verifiers_gates.yaml`, 34 gates) is **clean** — all 13 declared key kinds are read by `scripts/verify_the_verifiers.py`.

---

## FINDINGS (ranked by blast radius)

### F1 — `scripts/verify_home_bridge_sync.sh` guards the production WhatsApp bridge's live-vs-checkout divergence, and nothing on any machine is known to run it

- **Claim:** The script's own header states the invariant — the live WA bridge runs from `~/.openclaw/bin/openclaw_whatsapp_bridge.py` (HOME copy, not git-tracked), which is supposed to be byte-identical to `scripts/openclaw_whatsapp_bridge.py` on origin/main, and "nothing enforced that — they can diverge IN SILENCE" (`scripts/verify_home_bridge_sync.sh:1-15`). It exists as the antibody for scar family W50/W51/W52 (a fix that touches only `scripts/` is invisible to prod until re-copied into HOME).
- **Evidence (measured fresh on origin/main @ 83237f8f93):**
  - Repo-wide grep for the artifact name: exactly **2 files** — the script itself and `infra/tg-gateway/grandfathered.json:144`.
  - `grandfathered.json` is a Telegram-sender exception register (`"_doc": "Direct api.telegram.org senders grandfathered at gateway birth..."`) — an entry there exempts the file from a *different* lint; it executes nothing.
  - No LaunchAgent plist in `infra/launchagents/` references it (`grep -rn 'verify_home_bridge' infra/launchagents/` → 0 hits; siblings `verify_mcp_integrity.sh` and `audit_launchd_crons.py` *are* wired to plists — the probe fires).
  - No workflow, no `.husky/` hook, no wrapper script references it.
- **Why not already ledgered:** `grep -c 'verify_home_bridge' .claude/skills/modus/PENDING-ARMS.md` → **0**. The W50/51/52 scars it answers are ledgered as history; the guard built against them was never registered as unarmed.
- **Blast radius:** highest of the batch — client-facing production surface (the WhatsApp bridge); a `scripts/` fix already lost to HOME-fork drift once per the W50/51/52 record, and the antibody built to catch the recurrence has no heartbeat.
- **Suggested minimal arm:** wire it into an existing daily LaunchAgent wrapper on the machine owning the bridge (same pattern as `infra/launchagents/wrappers/audit-launchd-daily.sh`), reporting into the sentinel outbox; then add the row to PENDING-ARMS. If it is deliberately manual-only, say so in the header and ledger that decision instead.

### F2 — `sonarqube.yml` has never once performed an analysis, is self-documented as such, and has no ledger row

- **Claim:** The workflow's own header (added 2026-08-06) measures: over the last 29 completed runs, the `SonarQube Scan` step succeeded **0 times** — `SONAR_TOKEN` has never been configured, so both terminal steps were skipped on every run, while the two test+coverage steps that fed them ran anyway (1228s + 211s thrown away). Verbatim: "A whole job of 'exists but has never once done the thing it exists for' (cicatrix #2)" (`.github/workflows/sonarqube.yml:34-45`). The 2026-08-06 `preflight` job now zeroes the cost when the token is absent — but the workflow still exists, still runs on every `**.py`/`**.ts` PR, and still enforces nothing: the `sonarqube` job is `continue-on-error: true` (`.github/workflows/sonarqube.yml:85`) and the quality-gate step is doubly `continue-on-error: true` (line 167), so even a configured token would block nothing.
- **Evidence:** `grep -n 'never once did the thing\|costing 20-30' .github/workflows/sonarqube.yml` → line 44; continue-on-error keys at lines 85, 143, 148, 167, 177.
- **Why not already ledgered:** `grep -c 'sonarqube'` and `grep -c 'sonar'` in PENDING-ARMS.md → **0 / 0**. The workflow self-diagnoses but the diagnosis was never carried to the ledger — exactly the "self-documented ≠ tracked" gap this sweep exists for.
- **Blast radius:** medium — currently ~zero runner cost (preflight), but it advertises "SonarQube Analysis Complete" PR comments as a capability the repo has never had, and the 2026-08-06 measurement will go stale unread.
- **Suggested minimal arm:** one PENDING-ARMS row with a binary decision — configure `SONAR_TOKEN` and promote, or delete the workflow. Until then it is a permanently-green vestige.

### F3 — `scripts/lint_canva_pending.py` is a HARD validator for client-facing WR2 Canva payloads, and no pipeline stage, workflow, or test invokes it

- **Claim:** The script declares HARD (exit-1) checks on `apps/war-room/output/canva/canva_pending_*.json`: schema_version, slide/operation counts, banned `_drop_page`, `hero_sha256_uniqueness_check` pairwise/anchor distinctness, slide-index bounds (`scripts/lint_canva_pending.py:1-40`). The WR2 canva pipeline writes and applies these files (`scripts/wr2_canva_desktop_apply.py:83,426`; `scripts/wr2_canva_headless_apply.py:1`) but never calls the validator.
- **Evidence (measured fresh):**
  - `grep -rl 'lint_canva_pending' <repo>` → **1 file** (itself). Zero hits in `.github/workflows/`, `.husky/`, `scripts/tests/` (no `test_lint_canva_pending.py` exists), `.kimi-code/skills/wr2/`, `.agents/skills/wr2-carousel-pipeline/`, `docs/runbooks/`.
  - Positive control on the same probe: `scripts/ci/change_map.py` references `audit_httpx_violations.sh`; `scripts/fix_skills_agents_drift.sh` references `lint_skills_agents_drift.py`.
- **Why not already ledgered:** `grep -c 'lint_canva'` / `'canva_pending'` in PENDING-ARMS.md → **0 / 0**. (The WR2 queue JSONs' canonical-writer rule is unrelated — this is a validator, not a writer.)
- **Blast radius:** medium-high — WR2 output is published to Instagram clients; a malformed `canva_pending.json` (duplicate hero SHA, out-of-range slide index) passes silently into the desktop/headless apply step.
- **Suggested minimal arm:** one line in the canva apply wrapper (`wr2_canva_desktop_apply.py` preflight, or the WR2 cron wrapper on Pro) invoking the lint and aborting on exit 1; plus a `scripts/tests/` guilt fixture. Cheapest version: run it in the existing nightly scripts-tests sweep — but note that sweep is itself report-only (Appendix A), so a real arm needs a wired caller.

### F4 — `scripts/check_autonomous_ops_staleness.py` has no executor, and the mechanism it measures is documented broken on 0 of 3 machines

- **Claim:** The script exists to measure whether the Autonomous Ops contract (30-day staleness → conservative mode) is actually enforced by the SessionStart hook. Its docstring records (measured on Pro 2026-08-31): the verified 2026-06-11 hook fix "was LOST — because it lived in a file that no repository tracks", the live hook computes from mtime again, and "the mechanism that announces the contract's own expiry works on zero of three machines" (`scripts/check_autonomous_ops_staleness.py:1-18`). Nothing runs the probe: repo-wide grep → only `AUTONOMOUS_OPS.md` (prose) and its own test `scripts/tests/test_autonomous_ops_staleness.py` — which itself only executes in the report-only nightly sweep (Appendix A).
- **Why not already ledgered:** `grep -c 'autonomous_ops_staleness'` in PENDING-ARMS.md → **0**. PENDING-ARMS row 1205 mentions `AUTONOMOUS_OPS.md` only as one of six doctrine files getting a doc correction — the broken mechanism and the orphaned probe are not a row. (The 29 'staleness' hits in the ledger are healer-tick receptor vocabulary, not this artifact.)
- **Blast radius:** medium — an autonomous-ops session whose contract has lapsed runs un-conservative; nobody is told, and the only instrument that would say so has no schedule.
- **Suggested minimal arm:** run the probe from a weekly LaunchAgent on each machine (it is read-only and PII-safe), alert via the existing sentinel outbox; separately, move the hook itself into a repo-tracked, CI-verified location (the docstring's own diagnosis — family #1).

### F5 — `scripts/audit_asyncio_tasks.py` is a named audit with zero references anywhere

- **Claim:** Lexical audit classifying every `asyncio.create_task` call site SAFE/DROPPED/UNCLEAR (`scripts/audit_asyncio_tasks.py:1-12`) — the fire-and-forget "lost task" detector. Repo-wide grep (no excludes) → **zero references** outside itself; no test, no workflow, no cron wrapper, no doc names it.
- **Why not already ledgered:** `grep -c 'asyncio_task'` in PENDING-ARMS.md → **0**.
- **Blast radius:** low — a triage instrument, not a standing guard; its value decays silently as the codebase drifts from its last (unrecorded) run.
- **Suggested minimal arm:** cheapest honest version is a header line declaring it manual-only, or a quarterly cron on Pro writing results to a dated report. Include in the same PENDING-ARMS row as F4's class ("on-demand audits with no recorded last-run").

---

## Appendix A — already tracked (not findings)

| Artifact | Ledger row | State |
|---|---|---|
| `sensitive:` flag on 56 Visa Oracle questions — zero consumers (the task's example pattern) | PENDING-ARMS **row 35** (opened 2026-08-24, still open) | Arming step defined (wire to real behaviour or delete the 56 declarations); includes the adjacent `schema.d.ts` freshness gap |
| `token-contrast-tests.yml` advisory `continue-on-error` | row **1654** (2026-08-29) | Awaiting the 6-item checker spec, then delete the one line |
| `wr3-spend-gate-tests.yml` visible-not-blocking + `paths:`/`merge_group:` fork | row **294** (2026-08-23) | Promotion decision recorded; recommendation (B) waits a quiet queue |
| `scripts-tests-sweep.yml` report-only nightly sweep (the 632-file corpus, incl. the tests of the guards) | task #16 + 5 mentions (sweep header is self-aware; row in ledger) | Staged plan: triage junit → promote per-file |
| `contract-tests.yml` Schemathesis advisory | row at line 15-comment + 1 ledger mention | Deliberate NON-BLOCKING with promotion criteria |
| `hot-zone-pr-gate.yml:262,346`, `p3-sandbox-gates.yml:138` continue-on-error steps | 3 / 4 ledger mentions + in-file "NOT a disarm" registry notes | Monitor-by-design, named to `hot_zone_redis_lease` pattern |
| `tests.yml` / `security.yml` advisory continue-on-error steps/jobs (classifier-tests, classify, impact, npm-audit, visa-oracle-fullstack-smoke, snyk SARIF upload, etc.) | 553 / 87 ledger mentions for those workflow names; each instance carries an in-file measured rationale | Advisory-by-design with red-check-run signal preserved |

## What was NOT swept (declared, not implied)

- **The 37 PR-triggered, non-required, zero-ledger workflows** (e.g. `semgrep.yml`, `sbom.yml`, `frontend-typecheck.yml`, `yield-optimizer-pii-gate-tests.yml`, `wr2-master-template-guard.yml`, the `lint-*` family): triaged as a class, not individually. Every one sampled carries an in-file "advisory by design, promotion is operator-gated per CLAUDE.md §13" header; per ledger row 294's doctrine this is the repo's deliberate pattern, and rows exist only for gates whose PR's purpose was arming. A future lane could census all 37 into one ledger row if Zero wants the class named.
- **launchd/LaunchAgent reality on Pro/Mini:** wiring was verified only against in-repo plists (`infra/launchagents/`). An out-of-repo plist on Pro could theoretically invoke F1/F4/F5 — checked via `proprioception.py`'s tool list (no mention) but not via `ssh pro launchctl list`. Flagged as open risk below.
- **Family #3-as-in-the-rule-file (Guard-over-match/UNDER-match):** not audited beyond the dead-declaration pattern; `infra/guard-conformance/` owns that surface.
- **Cron-side (Pro/Mini) guards:** superscar #2's "cron verdi mascherano worker morti" half is out of scope for an M5 repo census; only CI/launchd-in-repo wiring was checked.
- **Rulesets API:** required contexts were read via the classic protection API (the ledger warns `rules/branches/main` returns zero required-check rules — same trap avoided here).

## Open risks

1. **F1 is the urgent one** and the cheapest to confirm: if `ssh pro launchctl list | grep -i home_bridge` (or a wrapper grep) finds nothing, the production WA bridge has had no divergence sentinel since the W50/51/52 cures — one `cp` drift is all it takes to regress.
2. F4's fix crosses the family #1 boundary (hook lives in `~/.claude/settings.json`, untracked); arming the probe does not fix the hook.
3. The 27→15→13→15 required-context count history across ledger rows shows protection is actively edited; any future promotion of the 37 advisory workflows should re-run probe 1 rather than trust this census's snapshot.
4. Positive-control caveat on F3: the canva pipeline may validate structurally inside `build_canva_pending` (backend renderer) — the lint's *specific* checks (SHA pairwise distinctness, `_drop_page` ban) were not found anywhere else, but a semantic-equivalent check inside the renderer would downgrade F3 from "unarmed guard" to "duplicated guard"; worth one renderer grep before arming.

*Bites: the Claude verification session reviewing this PR is the consumer — the observation that proves this census is in force is `grep -c` of each of the 5 finding names against `.claude/skills/modus/PENDING-ARMS.md` returning 0 on the merge commit, and this file rendering at `research/operations/2026-10-06-cicatrix-sweep-esiste-armato.md` on `origin/main`.*
