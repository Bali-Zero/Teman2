# GENERALE — ONDA 1 Convergence Report

> **Role**: serial merge-queue coordinator (no combat, no parallel git assault). Analysis only — **NO merges, NO rebases on armata branches, NO force push**. All merges are left to Antonello (he approves each one).
> **Generated**: 2026-06-02 (WITA), machine Pro (`nuzantara@Nuzantara`), branch `general/onda-1-convergence` (forked from `origin/main` @ `1fd005f32`).
> **Method**: `git fetch` + `git diff`/`git merge-tree` on **remote** refs only. Operator checkout (`feat/wa-army-launcher-2026-06-02`, dirty, no stash) was never moved.

---

## 0. Headline

- **6/6 armata branches each = exactly 1 commit** on top of a **shared merge-base `e66ccd018`** (which is itself **19 commits BEHIND** `origin/main` `1fd005f32`).
- **Collision matrix: ALL 15 pairs DISJOINT.** The 6 commits touch **zero overlapping files**. This is a perfectly clean fan-out. Merge order is therefore **NOT constrained by inter-branch file collision** — any order is safe for collision purposes.
- **`git merge-tree origin/main origin/<branch>` = CLEAN (exit 0) for all 6.** No branch conflicts with current `origin/main`. **No manual rebase required for content** (GitHub will auto-merge; the `mergeStateStatus: BEHIND` is just "branch behind base", auto-resolved at merge time or via "Update branch").
- **CI red on all 6 is INHERITED, not armata-caused.** Every PR fails `Backend Tests (Python)` with the identical `ModuleNotFoundError: No module named 'backend.services.crm.whatsapp_enrichment'` (in `test_crm_clients.py`). This import **does not exist on `origin/main`** (already fixed there) but **does** exist at the stale merge-base `e66ccd018`. → Disappears the moment each branch is brought up to date with main. Same for the `Frontend Tests (mouth/admin-dashboard)` failures and the `Detect Secrets` failures on S4/S5/S15 and the S16 `root-guard` failure (a `actions/checkout@v6` cancel/timeout — pure CI flake).

**Net recommendation**: these 6 are docs/research/infra-isolated and mutually disjoint. Antonello can merge **all 6 in any order**. The single PR carrying real executable code + tests is **S4 (broker)**; the rest are docs/audit/research (S1, S6, S15, S16) or audit-JSON only (S5). The red CI is a stale-base artifact — "Update branch" (or merge, which rebases onto main) clears it.

---

## 1. Six-session matrix

| Session | PR | Branch | Verdict (from FROZEN) | CI status | Files (true delta) | Collides with |
|---|---|---|---|---|---|---|
| **S1** events-outbox | [#1025](https://github.com/Balizero1987/Teman2/pull/1025) | `agent/air-m5/backend-rag/s1-events-outbox` | 5 dead channels triaged: 4× `SAFE_WITH_CONDITIONS`, 1× `UNSAFE` (cell_pulse_sustained_red). **Docs-only, zero code.** | red (inherited backend/frontend fail); Detect-Secrets **pass** | **2** (`research/operations/2026-06-02-S1-events-outbox-resurrection.md`, `S1-outbox-resurrection-FROZEN.json`) | none |
| **S4** broker-enforcement | [#1020](https://github.com/Balizero1987/Teman2/pull/1020) | `agent/nuzantara/infra/s4-broker` | W62 fix: TTL self-enforcing (daily cleanup cron + orphan WARN + CI gate). **35/35 tests pass. 1 latent bug fixed** (`.env.worktree` not in WIP-ignore → clean worktrees never reaped). | red (inherited backend/frontend fail + Detect-Secrets fail); **broker-hygiene, root-guard, inventory-check all PASS** | **9** (broker code/tests/CI/runbook/launchagent) | none |
| **S5** plist-secrets | [#1021](https://github.com/Balizero1987/Teman2/pull/1021) | `agent/nuzantara/infra/s5-plist-secrets` | 169 plist scanned. **Key finding: all 5 inline-secret plists ALREADY 0400** (S4 scar remediated). 2 autonomous chmod 0444 applied (filesystem, not committed). Remaining 0644 = empty/numeric/`*_FILE` refs. **Audit-JSON only.** | red (inherited backend/frontend fail + Detect-Secrets fail) | **1** (`S5-plist-secrets-FROZEN.json`) | none |
| **S6** regulatory-deep-fill | [#1022](https://github.com/Balizero1987/Teman2/pull/1022) | `agent/nuzantara/docs/s6-regulatory` | 4 new research files (legal/property/tax). 13 DeepSeek-verified claims (12 OK, 1 caveat). **No verdict key — research deliverable.** Structural 2025 shift documented (PP 28/2025, BKPM 5/2025, CoreTax, Perda Bali 4/2026). | red (inherited backend/frontend fail); Detect-Secrets **pass** | **5** (4 research .md + `S6-regulatory-FROZEN.json`) | none |
| **S15** symbiosis-audit | [#1023](https://github.com/Balizero1987/Teman2/pull/1023) | `agent/nuzantara/organism/s15-symbiosis` | 7 Symbiosis laws (2 PARTIAL, 5 RESPECTED). **2 scars REOPENED: W64 (W34 asyncpg regression), W65 (skills-bridge API key world-readable backup).** 4 RED launchagents found. | red (inherited backend/frontend fail + Detect-Secrets fail) | **2** (`.claude/rules/cicatrix-scars.md`, `S15-symbiosis-FROZEN.json`) | none |
| **S16** sota-multiagent | [#1024](https://github.com/Balizero1987/Teman2/pull/1024) | `agent/air-m5/docs/s16-sota` | 34 claims (27 SUPPORTED, 7 PARTIAL, 0 killed). 11 adoption verdicts (7 ADOPT, 1 DEFER, 2 REJECT, 1 KEEP). **Research deliverable.** | red (inherited backend/frontend fail) + **root-guard fail = checkout timeout flake** (not a policy violation) | **3** (`2026-05-24-sota-...-synthesis.md` [modified], `2026-06-02-sota-multiagent-orchestration.md`, `2026-06-02-sota-multiagent-FROZEN.json`) | none |

---

## 2. Collision matrix (the core)

**Method**: for each branch, the TRUE delta is `git diff --name-only <merge-base e66ccd018>..origin/<branch>` (the single commit), NOT `origin/main..branch` (which is polluted by ~70 files = the gap between the stale fork-point and current main, identical across all 6 and **not** part of any armata's work). Pairwise shared files via `comm -12`.

```
         S1    S4    S5    S6    S15   S16
   S1     —    ·     ·     ·     ·     ·
   S4           —    ·     ·     ·     ·
   S5                 —    ·     ·     ·
   S6                       —    ·     ·
  S15                             —    ·
  S16                                   —

  ·  = DISJOINT (0 shared files)
```

**All 15 pairs disjoint.** No two armatas touch the same file. Verified file-by-file:

- S1 → `research/operations/2026-06-02-S1-events-outbox-resurrection.md` + `S1-outbox-resurrection-FROZEN.json`
- S4 → `.github/workflows/broker-hygiene.yml`, `docs/runbooks/agent-worktree-broker.md`, `infra/launchagents/com.nuzantara.agent-worktree-cleanup.daily.plist.example`, `infra/launchagents/install_agent_worktree_cleanup.sh`, `scripts/agent_start.py`, `scripts/agent_worktree_cleanup_cron.sh`, `scripts/tests/test_agent_start.py`, `tests/integration/test_no_stale_worktrees.py`, `S4-broker-FROZEN.json`
- S5 → `S5-plist-secrets-FROZEN.json` (audit only; the chmod 0444 it applied are filesystem ops, not tracked)
- S6 → `research/legal/2026-06-02-positive-investment-list-kbli-foreign-ownership.md`, `research/legal/2026-06-02-pt-pma-nominee-ban-bkpm-oss.md`, `research/property/2026-06-02-foreign-property-rights-hak-pakai-hgb-leasehold.md`, `research/tax/2026-06-02-corporate-withholding-but-coretax.md`, `S6-regulatory-FROZEN.json`
- S15 → `.claude/rules/cicatrix-scars.md` (APPENDS W64/W65), `S15-symbiosis-FROZEN.json`
- S16 → `research/operations/2026-05-24-sota-multi-agent-repo-architecture-synthesis.md` (MODIFIES existing), `research/operations/2026-06-02-sota-multiagent-orchestration.md` (new), `2026-06-02-sota-multiagent-FROZEN.json`

> **Methodology caveat (anti-hallucination)**: an earlier collision pass used an associative-array bash script that silently failed under macOS bash 3.2 (`declare -A` unsupported) and produced a FALSE "every pair collides on the S16 files" matrix — a measurement artifact. It was discarded after the per-branch delta files were verified distinct (line counts 2/9/1/5/2/3, distinct md5). The matrix above is from the corrected run.

### The two "modify-existing-file" branches — extra scrutiny

S15 (`cicatrix-scars.md`) and S16 (`2026-05-24-sota-...-synthesis.md`) are the only branches that EDIT a pre-existing file (everyone else only ADDS). These are the highest conflict risk. Verified:

- Both files are **byte-identical between `origin/main` and the merge-base `e66ccd018`** (`git diff` empty). Main has not touched them since the fork → each branch applies its edit onto an unchanged base → **zero conflict**. `merge-tree` confirms exit 0 with no conflict messages.
- **Operator caveat**: the live operator checkout currently has `.claude/rules/cicatrix-scars.md` **dirty** (uncommitted). This is independent of the merge (the merge happens on GitHub against `origin/main`, not the local dirty tree), but **after S15 merges, the operator's local dirty `cicatrix-scars.md` will diverge from the new `origin/main`** — a `git pull` on that file may conflict locally. Flag for Antonello: stash/commit the local cicatrix edit before pulling post-S15-merge.

---

## 3. Merge readiness per branch (no merge performed)

| Branch | merge-tree vs main | CI armata-specific | Action needed before merge |
|---|---|---|---|
| S1 #1025 | CLEAN | none (only inherited red) | "Update branch" to clear inherited red, then merge. Or merge directly (squash rebases onto main → red clears). |
| S4 #1020 | CLEAN | none (broker-hygiene/root-guard/inventory PASS) | Same. The Detect-Secrets red is inherited (see §4). |
| S5 #1021 | CLEAN | none | Same. |
| S6 #1022 | CLEAN | none | Same. |
| S15 #1023 | CLEAN | none | Same. Warn operator re: local dirty cicatrix (§2). |
| S16 #1024 | CLEAN | root-guard = **flake** (checkout timeout) | **Re-run root-guard** (`gh run rerun <run> --failed`) OR merge (the merge commit re-triggers checks on the merged tree). Not a real violation. |

**No branch is in CONFLICT-with-main.** Zero require a manual rebase to resolve conflicts. The only thing standing between each PR and green is the **stale base** — resolved by GitHub's "Update branch" button or by the merge itself (squash/rebase replays the single commit onto current main where `whatsapp_enrichment` is already gone).

---

## 4. Why the CI is red (and why it's safe)

All 6 PRs share the failing-check signature because they share the stale merge-base `e66ccd018`:

1. **`Backend Tests (Python)` — fail on ALL 6.** Root cause: `test_crm_clients.py` at base imports `backend.services.crm.whatsapp_enrichment`, a module **absent on `origin/main`** (the import was removed there). Verified: `git show origin/main:.../test_crm_clients.py | grep whatsapp_enrichment` → empty; same grep at `e66ccd018` → present. **None of the 6 armata commits touch any `backend/` code.** → 100% inherited; clears on rebase-to-main.
2. **`Frontend Tests (Next.js)` (mouth + admin-dashboard) — fail on ALL 6.** Same inherited-base cause (no armata touches `apps/mouth` source either).
3. **`Detect Secrets` — fail on S4, S5, S15 only.** S5 and S15 FROZEN files legitimately discuss secret env-key NAMES (e.g. `BRIDGE_SKILLS_API_KEY`, `GH_TOKEN`) as audit findings; the detector flags the literal key-name strings in the JSON. S4 likely trips on the same shared base or a plist example. → **Audit-content false-positive**, not a real leak (values are REDACTED in the FROZEN per the orchestrators). Antonello: confirm via the Detect-Secrets diff, baseline-allow if it's the audit JSON.
4. **`root-guard` — fail on S16 only.** Log shows `##[error]The operation was canceled.` during `actions/checkout@v6` (~2min, fetch of PR merge ref) → **CI runner cancellation/timeout flake**. S16 adds only `research/*.md` — nothing root-guard would reject. Re-run passes.

> **Important**: I did **not** re-run any CI and did **not** touch the branches to "fix" CI. Clearing the red is Antonello's call (Update-branch / re-run / merge).

---

## 5. Recommended merge order

Since all 6 are **disjoint** and all merge **clean against main**, there is **no hard dependency ordering**. The order below is a *soft* recommendation by risk/foundation, not a requirement:

1. **S4 #1020** (broker-enforcement) — **FIRST**. It's the only PR with executable code + tests + CI gate; merging it first means the worktree-hygiene antibody (and its W62 fix) is live before any subsequent agent waves. Self-contained, 35/35 tests, broker-hygiene CI green. Foundation for repo hygiene.
2. **S5 #1021** (plist-secrets) — infra-isolated audit, audit-JSON only. Pairs naturally with S4 (both `infra/`-lane). No code risk.
3. **S15 #1023** (symbiosis-audit) — appends 2 scars to `cicatrix-scars.md`. Merge before S1/S6/S16 so the W64/W65 scar record is in main when their NEEDS-ANTONELLO items reference it. **Warn operator re: local dirty cicatrix.**
4. **S1 #1025** (events-outbox triage) — docs-only triage of 5 dead channels; its NEEDS-ANTONELLO are all "execute-on-Pro-later", no merge-time dependency.
5. **S6 #1022** (regulatory research) — pure research files, independent.
6. **S16 #1024** (sota research) — pure research files; **re-run root-guard before merge** (flake).

**Rationale for "S4 first"**: it's the only branch that changes how the agent infrastructure behaves (broker TTL enforcement). Everything else is inert documentation/audit. Putting the live-behavior change first minimizes the window where new agent waves run under the old advisory-TTL broker. After S4, the remaining 5 are order-independent.

---

## 6. Branches in CONFLICT-with-main

**None.** All 6 pass `git merge-tree origin/main origin/<branch>` with exit 0 and no conflict markers. No manual rebase required to resolve conflicts.

The only branch needing a CI re-trigger (not a rebase) is **S16 #1024** (root-guard checkout flake).

---

## 7. NEEDS-ANTONELLO (accumulated from all 6 FROZEN)

### 7a. Security / secret rotation (HIGH)
- **`BRIDGE_SKILLS_API_KEY` rotation** — **flagged by BOTH S5 and S15** (independent confirmation). A 64-hex value was world-readable in `com.nuzantara.skills-bridge-consumer.plist.bak-pre-chmod0400-20260531` (S15) / inline-secret window (S5). **chmod 0400 (or `rm`) the `.bak-pre-chmod0400-20260531` backup** AND **rotate the key**. (S15 W65 reopen.)
- **S5 rotation checklist** (scar 2026-04-29 plaintext-plist window — assume compromised): `GH_TOKEN`, `FIREWORKS_API_KEY`, `SCRAPER_API_KEY` (all in `com.balizero.post-publish-poller.plist`, priority HIGH); `TELEGRAM_BOT_TOKEN` (`sentinel.plist`); `POST_PUBLISH_SECRET` (`post-publish-webhook.plist`); local Postgres password (`wa-dashboard-m1.plist`, if any non-Pro process read it during the 0644 window).
- **S5 structural rec**: migrate the 5 inline-secret plists to the `*_FILE`/`*_PATH` reference pattern (secret in a 0600 file outside the plist) — survives the 2026-04-29 plist-overwrite scar. Design decision, not autonomous.

### 7b. Cicatrix reopened by S15 (code fixes)
- **W64 reopen** (was W34): `scripts/wr2_canva_lease_watchdog.py:40` — `except (asyncio.TimeoutError, OSError, asyncpg.PostgresError)` is **missing `asyncpg.InterfaceError`**. Lint exits 1 (orchestrator-verified this turn). Add `asyncpg.InterfaceError` + wire the W34 lint into CI (the W35 deferral that let the regression in). Regression introduced by W49 fix (commit `120078999`) after W34's `cb32f8214`.
- **canva-renderer flycast wrapper** = `CANNOT_VERIFY` (plist present, no wrapper script found; also appears as RED binary_missing below — needs Pro re-check).

### 7c. LaunchAgent RED (S15 — 4 confirmed-red, launchctl-authoritative)
- **`com.balizero.wr2.canva-renderer`** — **P1, fails EVERY 5 MIN** (wrapper `wr2-canva-renderer-wrapper.sh` ABSENT, `StartInterval=300 + RunAtLoad=true`, last exit 78 EX_CONFIG). Bootout the plist OR restore the wrapper.
- 3 more RED binary_missing (wr3/ dir, docs-lab-clean-recreate worktree, workspace-event-bridge-sheets-import) — bootout or restore wrappers.

### 7d. Symbiosis Law violations (S15)
- **Law 1 PARTIAL**: `apps/evaluator/seo_auto_fixer.py:95-98` POSTs to `https://api.anthropic.com/v1/messages` with `x-api-key=ANTHROPIC_API_KEY` — **BANNED paid endpoint** (CLAUDE.md §5). Live automation (`dlq_autopilot.py` lists `seo_auto_fixer`). Degrades gracefully only when key UNSET. **Patch to CLI path OR confirm key intentionally unset in prod env.** Extend `wr3_lint_cli_only` lint scope to cover it.
- **Law 2 PARTIAL**: confirm `bali-intel fly.toml` + `qdrant.fly.dev` URLs are vestigial vs an active cloud-OSINT crossing (runtime/network check).
- **Doc cleanup**: `SYMBIOSIS.md:195` still says "Air 16GB" (decommissioned 2026-05-05).

### 7e. events_outbox resurrection (S1 — all execute-on-Pro, postgres MCP was DOWN this session)
- **LIVE RE-VERIFY required first** (S1 ran with postgres-nuzantara MCP down → counts are the 2026-05-31 baseline, not live). Per-channel `SELECT channel, COUNT(*) FILTER (WHERE consumed_at IS NULL), MAX(created_at)` on Pro before ANY action.
- Recommended dispositions (all NEEDS-ANTONELLO, do NOT auto-run): `client_changed`, `practice_changed`, `intel_lake_event`, `war_room_event` → **mark-consumed-without-replay (drop stale)** via the existing idempotent `nz bus replay <chan> --all` (noop dispatch_fn, marks consumed with zero side-effects). `cell_pulse_sustained_red` → **UNSAFE**: do NOT hand-`pg_notify`; verify W2 supervisor `active.flag` (SHADOW mode is the load-bearing safety); restart `pg-organism-bridge` only after confirming the emitter (`CELL_OBSERVATORY_EMIT=true`).

### 7f. Research caveats (S6)
- **NB-5 push FAILED** for the property file (NB-5 `d9438180` is shared-not-owned → `source_add` text may need ownership, or transient rate-limit). Property research file lives on disk only (auditable). Manual NB-5 push or ownership fix if NotebookLM propagation is wanted.
- **Stale-knowledge correction shipped**: modal disetor reduced to **2.5 mld** (BKPM 5/2025) — pre-2025 memory/docs saying "10 mld versato" are STALE. Advertising KBLI 73100 is TERBATAS 49% (common error cites TERBUKA).

### 7g. CI hygiene (cross-cutting, from this convergence)
- The shared stale base `e66ccd018` is the root of the red CI on all 6. Bringing each branch up to date with main (Update-branch button, or merge) clears `Backend/Frontend Tests`. Confirm `Detect Secrets` on S4/S5/S15 is the audit-JSON false-positive before baseline-allowing. Re-run S16 root-guard (checkout flake).

---

## 8. COMMANDS MERGE PRONTI (for Antonello — copy/paste, run in sequence, NOT executed by me)

> Run from `~/Desktop/nuzantara`. Each `--squash` replays the single armata commit onto current `main` (which clears the inherited `whatsapp_enrichment` CI failure). Review each PR's green state after "Update branch" if you prefer green-before-merge. **The GENERALE never merges — this block is yours.**

```bash
# OPTIONAL pre-step: clear inherited red by updating each branch onto main (makes CI green before merge)
for pr in 1020 1021 1023 1025 1022 1024; do gh pr update-branch "$pr"; done
# Re-run the S16 root-guard checkout flake (only if you want it green pre-merge):
gh run rerun --failed $(gh pr checks 1024 --json link -q '.[]|select(.name=="root-guard")|.link' | grep -oE '[0-9]+' | head -1) 2>/dev/null || true

# MERGE ORDER (squash; foundation first, then disjoint docs/audit in any order):
gh pr merge 1020 --squash --delete-branch   # S4  broker-enforcement (code+tests, broker-hygiene green)
gh pr merge 1021 --squash --delete-branch   # S5  plist-secrets audit (infra-isolated)
gh pr merge 1023 --squash --delete-branch   # S15 symbiosis-audit (appends W64/W65 to cicatrix)  ⚠ stash local dirty cicatrix-scars.md before next local pull
gh pr merge 1025 --squash --delete-branch   # S1  events-outbox triage (docs-only)
gh pr merge 1022 --squash --delete-branch   # S6  regulatory research
gh pr merge 1024 --squash --delete-branch   # S16 sota research (re-run root-guard first if not green)
```

> **Caveat on `--delete-branch` for S4**: the S4 FROZEN notes a rescue branch `rescue/s4-root-guard-army-prompts-wip` (a sibling codex-autofix committed WIP `scripts/root_guard.py +2` whitelist, preserved at origin `eecbd1c1f`). That is a SEPARATE branch from `agent/nuzantara/infra/s4-broker` and must NOT be deleted by the S4 merge — verify it survives and decide its fate independently.

---

## 9. Provenance / verification trail

- Operator checkout `feat/wa-army-launcher-2026-06-02` (dirty, no stash) — **never moved**; all analysis on remote refs.
- Shared merge-base across all 6: `e66ccd018` (`git merge-base --octopus`). `origin/main` = `1fd005f32` (#1017).
- Each branch = 1 commit: S1 `237641fa0`, S4 `dc682e8e1`, S5 `5fce10958`, S6 `d0eef9696`, S15 `95e0918c6`, S16 `99eb11acc`.
- Collision matrix: `comm -12` on `git diff --name-only e66ccd018..origin/<branch>` (per-branch delta files verified distinct by line-count + md5 after correcting a bash-3.2 `declare -A` artifact).
- Conflict check: `git merge-tree --write-tree --messages origin/main origin/<branch>` = exit 0, no messages, all 6.
- CI: `gh pr checks <N>`; failure root cause via `gh run view --job <id> --log[-failed]`.
- FROZEN files read via `git show origin/<branch>:<path>` (S1 116KB, S4 9.1KB, S5 9.5KB, S6 4.0KB, S15 10.9KB, S16 150KB) — all valid JSON, parsed for verdict/needs-antonello fields.

---

*Report by the GENERALE (Claude Opus 4.8, 1M ctx) — ONDA 1 serial merge-queue coordinator. No merge, no rebase, no force push performed. Disposition of all 6 PRs is Antonello's.*
