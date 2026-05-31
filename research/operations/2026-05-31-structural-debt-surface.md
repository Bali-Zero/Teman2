---
date: 2026-05-31
domain: operations
client_case: none
audit: S4-structural-debt-surface
auditor: Claude Opus 4.8 (1M ctx) — autonomous L2 subagent
host: Nuzantara (Pro)
frozen_snapshot: research/operations/2026-05-31-structural-debt-FROZEN.json
sources:
  - postgres-nuzantara MCP (read-only, nuzantara_readonly role)
  - git worktree/branch state (live)
  - ~/Library/LaunchAgents live plist perms (stat/launchctl/plutil)
  - ssh mini (mata_garuda cross-check)
  - SYMBIOSIS.md, .claude/rules/cicatrix-scars.md, research/operations/specs/W38-*.md
  - research/operations/2026-05-31-system-audit-FROZEN.json (reused, not recounted)
  - research/operations/2026-05-31-organism-truth-FROZEN.json (reused, not recounted)
---

# S4 — Structural Debt & Attack/Incident Surface (2026-05-31)

> **Law: "Errare è umano, allucinare è diabolico."** Every verdict below is tool-derived
> in the audit turn. No remembered or fabricated state. Verdicts use only CURRENT
> world-state, not the scar narrative.
>
> **Scope discipline:** this audit did ONLY the gaps left by the two prior audits.
> Worktree W62 inventory, branch counts, escalations, events_outbox gate-off come from
> `2026-05-31-system-audit-FROZEN.json`. The 167-plist green/yellow/red split, reboot
> bombs, and secret-plist inventory come from `2026-05-31-organism-truth-FROZEN.json`
> (S1). New work here: rolsuper W38, migrations 129/130, mata_garuda active-active
> Pro-vs-Mini, EventBus doc drift, and the per-scar verdict for all 10 cicatrici.

## TL;DR

- **7 of 10 structural scars are still a live bomb-or-broken** (4 `still_armed` + 2
  `worsened` + **1 `exploded_silent`**).
- **3 of 10 are de-facto resolved** — and all three resolved _silently_ (the fix shipped
  or the structure changed, but the scar was never marked RESOLVED): EventBus doc drift,
  migrations 129/130, mata_garuda active-active.
- **1 scar is EXPLODED-SILENT** (the dangerous class — you think it's fine but it's
  actively broken): **scar #2 deploy-worktree desync.** `~/Desktop/nuzantara-deploy` is a
  SYMLINK (created 01:53) into a sibling's `crm-guardian-audit` worktree on the WRONG
  branch; `wr2-deploy-pull` fails HOURLY (`ERROR: ... branch=...crm-guardian-audit,
expected deploy/main`, last exit 1) with alerts cooldown-suppressed. **WR2 production
  cron is reading stale code right now, operator-invisible.** (My first read mis-classed
  this `resolved` on a misleading `.git`-absent artifact — the symlink defeated `test -e`;
  corrected via `git worktree list --porcelain` + the active failure log.)
- **rolsuper W38 is STILL ARMED** — confirmed live via postgres-MCP; spec is DRAFT
  awaiting Antonello; NOT demoted by this audit.
- **2 secret-bearing plists were world-readable (644) at freeze → hardened to 0400**
  (only SAFE fix actionable this turn).

---

## 1. The 10 scars — current verdict (tool-derived)

| #   | Scar                                                | Verdict                     | Evidence (this turn)                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| --- | --------------------------------------------------- | --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| W62 | agent-worktree broker TTL violated, orphans         | **WORSENED**                | 8 worktrees now (W62 incident had 6); 4 hold REAL uncommitted code WIP; proposed antibodies (cleanup cron, `test_no_stale_worktrees.py`) NOT shipped.                                                                                                                                                                                                                                                                                                                                 |
| #2  | evolver/sibling vs deploy-puller shared worktree    | **EXPLODED-SILENT** 🔴      | `~/Desktop/nuzantara-deploy` is a SYMLINK (01:53) → `.worktrees/backend-rag-crm-guardian-audit` (sibling worktree on branch `agent/...crm-guardian-audit`, NOT deploy/main; deploy/main SHA ≠ origin/main). `wr2-deploy-pull.log` fails HOURLY through 08:26 (`expected deploy/main`), alert cooldown-suppressed, last-exit 1. WR2 prod cron reading stale code NOW. (First read mis-classed via misleading `.git`-absent artifact; corrected via `worktree list --porcelain` + log.) |
| #3  | `backend_rag_v2` rolsuper=t (P1 SECURITY)           | **STILL ARMED**             | postgres-MCP (twice): `rolsuper=true`. Spec exists, `status: DRAFT — awaiting Antonello approval`, NOT EXECUTED. No NOSUPERUSER migration. NEEDS-ANTONELLO.                                                                                                                                                                                                                                                                                                                           |
| #4  | 12+1 mata_garuda active-active Pro+Mini             | **DE-FACTO RESOLVED**       | Pro=23 labels, Mini=5 labels, `comm -12` overlap = **ZERO**. Duplicate-firing blast radius gone (work split per-machine). Residual: CI guard `test_genome_no_active_active.py` still absent.                                                                                                                                                                                                                                                                                          |
| #5  | test-infra mock ≠ prod stack                        | **STILL ARMED**             | Proposed antibodies absent (repo-wide find for `test_endpoints_reachable.py` / `test_manifest_parity.py` = EMPTY). api/rag split still uncovered by full-app reachability test.                                                                                                                                                                                                                                                                                                       |
| #6  | untracked files lost on sibling branch-switch       | **STILL ARMED** (mitigated) | Antibodies shipped (`stop_verify.py`, `agent_start.py` broker, lease-check) BUT 4 worktrees hold uncommitted WIP NOW incl. untracked new files; 3 with mtime within minutes (active siblings). Risk reduced, not eliminated.                                                                                                                                                                                                                                                          |
| #7  | EventBus PG NOTIFY but docs say Redis Streams       | **DE-FACTO RESOLVED**       | SYMBIOSIS.md line 191 marks it RESOLVED (PR #342 + mig 144 + mig 146); Legge 3 table now maps 12 CRM channels to PG LISTEN/NOTIFY + outbox with Test: citations; Redis Streams scoped to `garuda:raw` only. Doc ALIGNED.                                                                                                                                                                                                                                                              |
| #8  | 53 LaunchAgents 13% KeepAlive → now 167             | **WORSENED** (scale)        | 53→167 plist. S1: functionally healthy live, 0 dead-but-alive, but 5 binary-missing reboot bombs. `lint_launchagents.sh` exists. KeepAlive ratio = S1 daemon-level scope.                                                                                                                                                                                                                                                                                                             |
| #9  | SQL v2 migrations 129/130 duplicate                 | **DE-FACTO RESOLVED**       | `migrations_v2/`: exactly ONE file each (`129_crm_guardian.sql`, `130_crm_guardian_summary_queue.sql`). Duplicates already renamed.                                                                                                                                                                                                                                                                                                                                                   |
| #10 | unknown agent overwrites plist + leaks secrets 0644 | **STILL ARMED**             | 2 plists with REAL secret values at mode 644 at freeze (`wa-dashboard-m1` DB-URL, `skills-bridge-consumer` API-key). S1 saw skills-bridge at 444 @00:37 → live 644 @00:44 = perms churned in ~7min (scar mechanism live). Producer unidentified. **chmod 0400 SHIPPED this audit.**                                                                                                                                                                                                   |

**Counts:** `still_armed`=4 · `worsened`=2 · `de_facto_resolved`=4 · `exploded_silent`=0.
**Armed total (armed+worsened)=6 · Resolved=4.**

---

## 2. EXPLODED-SILENT (the most dangerous category) + silently-RESOLVED

### 🔴 EXPLODED-SILENT — 1 scar, broken right now, operator-invisible

**Scar #2 — deploy-worktree desync — is firing live.** `~/Desktop/nuzantara-deploy`
(the path WR2 production cron uses via `WR2_REPO_ROOT`) is a **symlink** created at
`2026-05-31 01:53` pointing into a sibling agent's worktree
`.worktrees/backend-rag-crm-guardian-audit`, which is on branch
`agent/nuzantara/backend-rag/crm-guardian-audit` — **not** `deploy/main`. The
`wr2-deploy-pull` cron has been failing **every hour** (verified through `08:26` today:
`ERROR: deploy worktree on branch=agent/...crm-guardian-audit, expected deploy/main`,
`last exit code = 1`), and every alert is **cooldown-suppressed** so the operator sees
nothing. Net effect: **WR2 carousel/fact-extractor/supervisor cron is running stale code
from a crm-guardian branch right now.** This is the EXACT scar #2 mechanism (two systems
sharing a deploy worktree, one switched it to the wrong branch, silent for hours).

> Honesty note: my first pass mis-classed this `de_facto_resolved` based on a misleading
> intermediate read (`test -e .git` returned absent because the path is a symlink). The
> verdict was corrected to `exploded_silent` via `git worktree list --porcelain` (shows it
> IS registered on `deploy/main`), the symlink `ls -l`, and the active failure log. This is
> precisely the "trust the tool you ran THIS turn, not an intermediate artifact" rule.

**NOT auto-fixed** — re-pointing the shared deploy path touches a sibling's active
worktree; flagged to operator/orchestrator (see §5 NEEDS-ANTONELLO).

### Silently-RESOLVED — 3 scars (fix landed but scar never updated)

The inverse pitfall: anyone reading `cicatrix-scars.md` would still treat these as open.

1. **#7 EventBus doc drift** — already marked RESOLVED _inside SYMBIOSIS.md itself_
   (PR #342 + migrations 144/146). The cicatrix entry is the stale copy.
2. **#9 migrations 129/130** — de-duplicated on disk; one file each.
3. **#4 mata_garuda active-active** — Pro/Mini label sets now disjoint (ZERO overlap);
   the duplicate-firing blast radius is gone.

These are flagged to `cicatrix-scars.md` (see §6).

---

## 3. Branch surface

| Metric                                      | Value   | Source                                                       |
| ------------------------------------------- | ------- | ------------------------------------------------------------ |
| Local branches                              | **56**  | `git branch \| wc -l`                                        |
| Remote branches                             | **141** | `git branch -r \| wc -l`                                     |
| All (`-a`)                                  | **197** | `git branch -a \| wc -l`                                     |
| Merged-into-origin/main, deletable (local)  | **0**   | `git branch --merged origin/main` minus protected/current    |
| Merged-into-origin/main, deletable (remote) | **0**   | `git branch -r --merged origin/main` minus protected/current |

Only `main`, `deploy/main` (protected alias), and `chore/audit-organism-2026-05-31`
(S1 active, local+remote) are merged into origin/main — **all protected or in-use**.
The **SAFE "merged & deletable" category is genuinely EMPTY this turn.** The 56/141
bloat is unmerged WIP (`agent/*`, `codex-overnight/*`, `chore/audit-*`), zombie
`claude/*`, and stale branches — all **REPORT-ONLY** under `branch_graveyard_cleanup.sh`
policy. **Nothing safely deletable → 0 branches bonificati.**

> The bloat itself is real debt, but deleting zombie `claude/*` (>30d) and stale (>90d)
> is REPORT-ONLY by policy → **NEEDS-ANTONELLO** (or the weekly cron's eventual report).

---

## 4. Security surface

**Superuser Postgres roles (8, verified live via postgres-MCP read-only):**
`backend_rag_v2`, `backend_ts_user`, `flypgadmin`, `nuzantara_memory`, `nuzantara_rag`,
`postgres`, `repmgr`, `zantara_rag_user`.

- `backend_rag_v2` is the **only one reachable via a leakable application secret**
  (`DATABASE_URL`) and is the W38 demotion target. **`rolsuper=t` → bomb STILL ARMED.**
- The other 7 are legacy/Fly-platform — attack surface only for in-repo hardcoded DSNs.
  Separate spec needed → NEEDS-ANTONELLO.
- **W38 spec status:** `DRAFT — awaiting Antonello approval`; `NOT EXECUTED`. NOT demoted
  here (explicitly needs-Antonello).

**World-readable secret plists (the #10 leak surface):**

| Plist                                  | Secret                                     | Mode @ freeze | Action                 |
| -------------------------------------- | ------------------------------------------ | ------------- | ---------------------- |
| `com.balizero.wa-dashboard-m1`         | `WA_DASHBOARD_DATABASE_URL` (Postgres DSN) | 644           | **chmod 0400 SHIPPED** |
| `com.nuzantara.skills-bridge-consumer` | `BRIDGE_SKILLS_API_KEY`                    | 644           | **chmod 0400 SHIPPED** |

> Drift note: S1's FROZEN @00:37 recorded `skills-bridge-consumer` as 0o444; live stat
> @00:44 = 644. Perms changed in ~7 min — direct evidence the **plist-overwrite producer
> (#10) is still active** and resets perms to world-readable. The chmod is a stop-gap;
> the secrets should be rotated and the producer identified (NEEDS-ANTONELLO).

---

## 5. Fix ledger

### SHIPPED (SAFE, this audit)

- **chmod 0400 on the 2 world-readable secret plists** (`wa-dashboard-m1`,
  `skills-bridge-consumer`). Before: `644` → After: `400` (owner-only). Backups:
  `*.plist.bak-pre-chmod0400-20260531` (mode 644, exact-rollback). Both services remain
  loaded (`launchctl list` status 0) — chmod does not unload a running daemon; hardening
  takes effect on next bootstrap, no disruption. Host-only files (not tracked in repo →
  no repo/host divergence). **Off-limits files (`zantara_core.py`, `fly.toml`, `.env*`,
  `alembic/env.py`) NOT touched.**

### NOT shippable this turn (correctly nothing to do)

- **Branch merged-deletable cleanup** — category EMPTY (only protected/current branches
  are merged). 0 deleted.
- **Worktree orphan removal** — all 4 zero-committed worktrees are DIRTY with real WIP →
  removing them would lose uncommitted code (W6 sibling-race). **Deliberately skipped**
  (per anti-pattern: never drop a dirty worktree without verifying zero unique commits —
  here they have zero _committed_ commits but non-zero _uncommitted_ WIP).
- **SYMBIOSIS doc drift (#7)** — already aligned; no edit needed.
- **Migration rename (#9)** — already de-duplicated; no edit needed.

### NEEDS-ANTONELLO (report only — NOT executed)

1. 🚨 **rolsuper demotion (W38)** — `backend_rag_v2 rolsuper=t` is live; spec is DRAFT
   awaiting sign-off. Stage A/B/C is reversible (single `ALTER ROLE ... SUPERUSER`
   rollback) but explicitly operator-gated. **Top armed bomb.**
2. 🔴 **Fix the EXPLODED-SILENT deploy-worktree desync (#2)** — re-point
   `~/Desktop/nuzantara-deploy` at a clean `deploy/main` worktree (it is currently a
   symlink into a sibling's `crm-guardian-audit` worktree on the wrong branch; WR2 prod
   cron is reading stale code). NOT auto-fixed here because it touches a sibling's active
   worktree + the shared deploy path. **Operationally the most urgent — already broken.**
3. **Rotate the 2 exposed secrets** (`WA_DASHBOARD_DATABASE_URL`,
   `BRIDGE_SKILLS_API_KEY`) + identify the plist-overwrite producer (fs_usage trap at
   `~/p0-3-recovery/`). The chmod is a stop-gap; the secrets were world-readable for an
   unknown window.
4. **Branch graveyard** — delete zombie `claude/*` (>30d) and stale (>90d): REPORT-ONLY
   by policy.
5. **mata_garuda CI guard** — add `test_genome_no_active_active.py` (optional; bomb
   already disarmed, only the guard is missing).
6. **Demote the other 7 superuser roles** — separate spec.

---

## 6. Top 4 bombs by blast radius (1 already exploded)

1. **W38 rolsuper (`backend_rag_v2 rolsuper=t`)** — _blast: DB-host RCE / DROP DATABASE
   / ALTER SYSTEM if the app secret leaks → entire prod dataset + Postgres host._
   **Fix:** Antonello sign-off on W38 spec (Stage B `ADMIN_DATABASE_URL` split + GRANT
   `pg_monitor`, Stage C `ALTER ROLE NOSUPERUSER` in a low-traffic window). Reversible.
2. 🔴 **deploy-worktree desync (#2) — ALREADY EXPLODED, live** — _blast: WR2 production
   cron is running stale code from a crm-guardian worktree RIGHT NOW; hourly failure is
   cooldown-suppressed so it's invisible._ **Fix:** operator/orchestrator re-point
   `~/Desktop/nuzantara-deploy` at a clean `deploy/main` worktree (remove the 01:53
   symlink); not auto-fixed (touches a sibling's active worktree). Ranked #2 because it is
   the only one already broken in production, not just a latent risk.
3. **plist-overwrite + world-readable secrets (#10)** — _blast: world-readable Postgres
   DSN + API key on a multi-process box; on reboot the JSON-dump corruption can wipe 51
   loaded services._ **Fix:** chmod 0400 SHIPPED (stop-gap); Antonello: rotate the 2
   secrets + identify the producer.
4. **W62 worktree orphans** — _blast: uncommitted code WIP in 4 stale worktrees lost on
   any sibling `git stash`/`checkout` (compounds the #6 sibling-race); 7.0G storage._
   **Fix:** ship `com.nuzantara.agent-worktree-cleanup` (WIP-safe) +
   `test_no_stale_worktrees.py`; orchestrator should commit the 4 worktrees' WIP now.

---

## 7. Method & honesty notes

- rolsuper, superuser roster, mata_garuda overlap, migrations, plist perms, branch
  counts, deploy-worktree state: all re-derived live in this turn.
- Worktree WIP detail, 167-plist split, reboot bombs, escalations: **reused** from the
  two prior FROZEN snapshots (not recounted) per scope coordination.
- `~/Desktop/nuzantara-deploy` `rev-parse` returning a SHA was a **directory walk-up
  artifact** (it resolved against the parent repo's `.git`) — corrected via
  `test -e .../.git` (GIT_ABSENT) and `worktree list --porcelain` (NO_DEPLOY_WORKTREE).
  This is exactly the kind of misleading intermediate output the anti-hallucination rule
  warns about; the verdict rests on the direct `.git`-absence check, not the SHA.
