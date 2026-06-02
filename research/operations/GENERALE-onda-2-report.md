# GENERALE — ONDA 2 Convergence Report

> **Role**: Serial merge-queue coordinator (NON-merging). Antonello approves every merge.
> **Generated**: 2026-06-02 WITA · Pro (`nuzantara@Nuzantara`)
> **Scope**: 5 delivered PRs (S2, S3, S10, S13, S14). S7 (crm-yield) FAILED — excluded from queue, see NEEDS-ANTONELLO.
> **Method**: read-only. `git fetch origin` + `origin/main` reference. Operator checkout (`feat/wa-army-launcher-2026-06-02`) never touched.

---

## 0. Headline

- **All 5 PRs are draft, CI mostly green-modulo-inherited-noise, and pairwise DISJOINT (zero file collisions).**
- **All 5 merge CLEAN against `origin/main`** (verified `git merge-tree --write-tree`, rc=0 ×5).
- **Recommended merge order is essentially free** (no inter-branch dependency, no conflict). Suggested: **#1027 (import fix) FIRST → then S3, S10, S14, S13, S2 in any order.**
- **One real code branch** (S3 — escalation storm fix, 14/14 tests pass). The other four are research/docs-only audits (no executable prod code on their merge-base diff).

---

## 1. Five-Session Matrix

| S | PR | Branch (actual `headRefName`) | Verdict (from FROZEN) | CI status | TRUE files | Collisions |
|---|----|-------------------------------|------------------------|-----------|-----------|------------|
| **S2** spec-graveyard | [#1031](https://github.com/Balizero1987/Teman2/pull/1031) | `agent/air-m5/docs/s2-spec-graveyard` | 0 EXECUTE-NOW · 6 DEAD (archive) · 3 NEEDS-ANTONELLO (W38/L5.2/R2) · 2 RE-SPEC | Backend-Tests **PASS**; red = Detect-Secrets + Frontend(mouth/admin) **[all inherited]** | 3 (all `research/`) | none |
| **S3** escalation-debt | [#1032](https://github.com/Balizero1987/Teman2/pull/1032) | `agent/air-m5/infra/s3-escalation-debt` | W61 storm fixed at generator + JSONL rotation + W55 digest; 14/14 tests PASS | Backend-Tests **PASS**; red = Detect-Secrets + Frontend + a stale **CodeQL umbrella check (HTTP 404 job, flaky/aggregator)** — the real CodeQL Analysis (py+js) **PASS** | 8 (5 scripts + 1 plist + 1 test + FROZEN) | none |
| **S10** crm-quality | [#1029](https://github.com/Balizero1987/Teman2/pull/1029) | `agent/nuzantara/backend-rag/s10-crm-quality` | Audit-only. 1.447 ATTIVI (not 11.699); 10.252 già soft-deleted. PII audit PASS | Backend-Tests **FAIL = inherited** `whatsapp_enrichment` import; rest = inherited Detect-Secrets/Frontend | 2 (all `research/crm-guardian/`) | none |
| **S13** agent-evolve | [#1030](https://github.com/Balizero1987/Teman2/pull/1030) | `agent/air-m5/organism/s13-agent-evolve` | Evolution loop NEVER closed. Manual cycle substitute. Adversaries: enforcement>abstraction. Several proposals KILLED/REVISED | Backend-Tests **FAIL = inherited**; rest inherited | 13 (all `research/agent-library/`) | none |
| **S14** nb-curation | [#1028](https://github.com/Balizero1987/Teman2/pull/1028) | `agent/nuzantara/intel/s14-nb-curation` | 74 NB / 3530 src; 56 healthy, 18 empty, 0 broken. P1: 6 NB deletable (445 src). Audit-only | Backend-Tests **FAIL = inherited**; rest inherited | 1 (`research/nb-health/S14-curation-FROZEN.json`) | none |

**CI legend** — Every red check on every PR is one of:
1. `Detect Secrets` — fires on the FROZEN.json files (SHA / secret-name strings inside audit JSON). **Inherited / by-design**, not a leak.
2. `Frontend Tests (mouth, true)` + `Frontend Tests (admin-dashboard, false)` — failing on ALL 5 PRs identically → **cross-cutting/inherited**, not branch-fault.
3. `Backend Tests (Python)` — fails with `ModuleNotFoundError: No module named 'backend.services.crm.whatsapp_enrichment'` (test `test_crm_clients.py`). **This is the exact inherited bug the brief flagged; fix = PR #1027.** See §5 for the forensic proof it is NOT branch-fault.
4. S3 only: a `CodeQL` umbrella status shows `fail` but its job returns **HTTP 404** (stale re-run pointer / aggregator); the substantive `CodeQL Analysis (python)` + `(javascript)` both **PASS**.

---

## 2. Collision Matrix (5×5)

Computed on the **TRUE per-branch contribution** = `git diff <merge-base> <branch>` (NOT the misleading two-dot `origin/main..branch`, which falsely showed ~40 shared files — see §5 GOTCHA).

```
        S2    S3    S10   S13   S14
  S2     —    ·     ·     ·     ·
  S3     ·    —     ·     ·     ·
  S10    ·    ·     —     ·     ·
  S13    ·    ·     ·     —     ·
  S14    ·    ·     ·     ·     —
```
`·` = disjoint (zero shared files). **All 10 pairs disjoint.**

**Cross-verified two independent ways:**
- `comm -12` on each pair → empty for all 10 pairs.
- Independent count: Σ(per-branch file counts) = 3+8+2+13+1 = **27**; `sort -u` across all five = **27**. Equal ⇒ zero overlap.

**There is NO merge-order constraint from collisions.** The branches touch entirely separate paths (`research/operations`, `research/crm-guardian`, `research/agent-library`, `research/nb-health`, `scripts/escalations*`).

---

## 3. Conflict-with-main check (no checkout, no rebase)

`git merge-tree --write-tree origin/main origin/<branch>` for all 5:

| Branch | Result |
|--------|--------|
| S2 `agent/air-m5/docs/s2-spec-graveyard` | **CLEAN (rc=0)** |
| S3 `agent/air-m5/infra/s3-escalation-debt` | **CLEAN (rc=0)** |
| S10 `agent/nuzantara/backend-rag/s10-crm-quality` | **CLEAN (rc=0)** |
| S13 `agent/air-m5/organism/s13-agent-evolve` | **CLEAN (rc=0)** |
| S14 `agent/nuzantara/intel/s14-nb-curation` | **CLEAN (rc=0)** |

**Branches in CONFLICT with main: NONE.** No manual rebase required for any of the 5.

*Note:* S2 re-adds `research/operations/specs/W38-backend-rag-v2-nosuperuser.md` which already exists on main; S2's version adds 8 lines. The 3-way merge resolves this cleanly (additive). No conflict.

---

## 4. Recommended Merge Order

No collisions and no main-conflicts means order is **logically free**. The only ordering that *matters* is putting the CI-unblock first so reviewers see green:

1. **#1027** (`agent/nuzantara/backend-rag/fix-whatsapp-enrich-import`) — **MERGE FIRST.** Restores the missing `whatsapp_enrichment` module so `Backend Tests (Python)` goes green for S10/S13/S14 on re-run. (Not part of ONDA 2's 5, but it is the keystone for clean CI.)
2. **S3** #1032 (escalation-debt) — only branch with executable code; ship the storm-fix early. 14/14 tests pass, additive, graceful-degradation.
3. **S10** #1029 (crm-quality) — audit doc.
4. **S14** #1028 (nb-curation) — audit doc.
5. **S13** #1030 (agent-evolve) — audit + `_proposed/` drafts (no graduation to live agent-library yet; proposals are docs).
6. **S2** #1031 (spec-graveyard) — audit doc; last because it re-touches the W38 spec file (additive, harmless, but cleanest applied after the code branches).

**Dependencies:** none hard. S2's verdict *references* W38 (whose execution is a separate NEEDS-ANTONELLO security action — see §6), but merging the S2 doc does not execute anything. S3 is the only one that ships runnable scripts/plists; those plists are **shipped-but-not-installed** (install is a separate deploy step, see §6).

---

## 5. Forensic note: why "Backend-Tests" and the "40-file collision" were both red herrings

The brief explicitly warned: *"se vedi tutto-collide o tutto-disgiunto, RI-VERIFICA con un secondo metodo."* That warning fired. Findings:

- **Merge-base for ALL 5 branches = `e66ccd018`** (2026-05-31, PR #993). `origin/main` HEAD = `8f76274e6` (2026-06-02) = **32 commits ahead** of that base.
- `git diff --name-only origin/main..origin/<branch>` (two-dot) reported ~40 shared code files (crm_clients.py, MCP servers, hooks, browser-core, plists…) for every branch. **This was an artifact of the branches being 32 commits behind main** — two-dot diff shows main's *newer* changes as branch "deletions".
- **Proof**: for S2, `crm_clients.py` blob on the branch == blob at merge-base (`9a50e2b`), while `origin/main`'s blob is different (`1a5323a`). The branch never touched the file; main did. The correct contribution diff (`git diff <merge-base> <branch>`) shows S2 = **3 files only**.
- **Backend-Tests split** (PASS on S2/S3, FAIL on S10/S13/S14) is purely **CI-run timing against an evolving main**, plus the inherited `whatsapp_enrichment` import. None of the 5 branches modify any backend Python; the failure is 100% inherited (fix = #1027). `origin/main` HEAD no longer even contains the `test_crm_clients.py` with the bad import path, so a re-run post-#1027 will clear it.

**Lesson for the report consumer:** trust the merge-base diff (`git diff $(git merge-base main br) br`) and `merge-tree`, not two-dot `main..br`, when branches are behind.

---

## 6. NEEDS-ANTONELLO (aggregated)

### From S2 FROZEN (3 prod actions, none auto-executable)
- **W38 — `ALTER ROLE backend_rag_v2 NOSUPERUSER`.** Prod security write, irreversible-class. Stage B `ADMIN_DATABASE_URL` code split NOT implemented. "Bomb #1 by blast radius." (Matches the long-standing W38 cicatrix.) Requires explicit sign-off + low-traffic window.
- **L5.2 — flip `hot-zone-pr-gate.yml`** from monitor-mode (6× `continue-on-error:true`) to enforce + add to required_status_checks + Phase 1 bot privilege downgrade + Phase 3 branch-protection writes. All prod GitHub-API writes.
- **R2 — Exa MCP OAuth.** (1) Interactive browser OAuth grant an agent cannot perform. (2) **PAID-API HARD-RULE conflict**: Exa is not in the sanctioned subscription arsenal; on-disk `EXA_API_KEY=9e54…` is a per-token paid key. Owner must clear policy + grant OAuth. Side-cleanup: scrub stale `mcp__exa__*` allowlist + leaked key from `settings.local.json`.

### From S3 FROZEN (deploy-step + 2 design judgment calls)
- **Install step (deploy-time):** S3's new plists + rotation step are **shipped in repo but NOT installed/loaded.** Install `com.nuzantara.escalations-digest.weekly.plist` + verify `escalations-prune.plist` is loaded on Pro. **Secondary debt found:** `escalations-prune.plist` (SQLite mirror rotation) is currently **NOT loaded on Pro** — the SQLite mirror grows unbounded (~525 rows).
- **Q1 (rotation commit default = OFF):** a cron must not `git commit` a shared worktree mid-session (cicatrix W50/W51/W59). File stays git-tracked; operator/canonical flow propagates empty state. OVERRIDE only via `--commit` or untrack+gitignore if the git federation-bus contract is dead in the 2-node setup.
- **Q2 (per-job cooldown accepted):** 4h cooldown is per-JOB not per-error-hash → a genuinely-new distinct error for an already-DLQ'd job can be suppressed in JSONL up to 4h. Accepted (full history in DLQ + SQLite + TERMINAL alert bypasses cooldown). OVERRIDE → per-error-hash cooldown.

### From S10 FROZEN (data-quality remediation — operator decision, no code shipped)
- Operative dataset is **1.447 active** clients (not 11.699; 10.252 already soft-deleted). Active-only findings to action: **990 (68.4%) missing email**, **343 (23.7%) missing phone**, **48 phone-dup clusters / 100 rows**, **19 passport-dup clusters / 39 rows**, **1.093 (75.5%) full-orphans** (no practice+interaction+timeline+whatsapp), **46 unassigned**. Remediation spec in `research/crm-guardian/S10-remediation-spec.md`. PII audit PASS (counts-only).

### From S13 FROZEN (proposal triage — operator picks what graduates)
- **PRIMARY:** S13-P6 (fix evolution-loop closure) + S13-P7 (contract-test harness) — both adversaries: *enforcement, not abstraction.*
- **S13-P6 unblock:** restore `DEEPSEEK_API_KEY` export in `secrets.env`; decouple evolver from `nuzantara-deploy` worktree (cf. cicatrix 2026-05-25 worktree-sharing); regenerate stale `01-inventory.md` (16→34 drift).
- **REVISE (don't graduate as prose):** P1 provider-cascade → executable shared runner+breaker; P2 nb-ground-truth → split routing/freshness CONFIG from call-authority (preserve Contract 2); P4 metrics → keep no-data gate, DEFER correlation.
- **KILLED by adversaries:** P3 review-gate-protocol (homogenizes intentionally-distinct reviewers).
- **DOWNGRADE:** P5 orchestrator-contract → contract-test (P7 lane), not a shared skill.

### From S14 FROZEN (NB cleanup — Antonello approves NB-level deletes)
- **P1 (highest signal):** delete **6 self-marked `[MERGED-INTO-*]`/`[ARCHIVED-DELETE-*]` NBs (445 src)** after target-absorption spot-check. **Empirical caveat caught:** `201b4b94` (150 src, "Digital Sovereignty") — merge target `d2a05271` is **PARTIAL** (no Palantir/Anduril/Anchorage). **DO NOT blind-delete; content-diff or re-merge first.** Other 5 confirmed safe.
- **P2:** 24 source-level dedup (Cloudflare/Vercel anti-bot walls, dup YouTube no-URL re-ingests in NB-4).
- **P3:** 17 empty orphan-scaffold NBs deletable — **exclude** `75b73262` (Air-M5, fresh) + `7e6ae978` (PROBE-SANDBOX fixture).

### S7 — FAILED (NOT in queue) ⚠️ NEEDS ROOT-CAUSE DIAGNOSIS
- **S7 (crm-yield) died 5× with exit 143 (SIGTERM external, ~8 min after start), zero output.**
- **Goes to NEEDS-DIAGNOSI, not the merge-queue.** No PR, no branch to merge.
- **Hypotheses (UNCONFIRMED):** (a) a GC/reaper culling a slow Ollama-bound worktree; (b) a concurrent-session cap; (c) a `claude -p` timeout. None verified. Recommend: re-run S7 standalone with `run_in_background` + log capture before relaunching as part of any wave, and check for a LaunchAgent/broker TTL or OOM killer around the 8-min mark.

---

## 7. COMANDI MERGE PRONTI (TEXT ONLY — do not execute; Antonello runs)

> Order chosen so the import-fix lands first (CI goes green for the audit PRs on re-run), then the one code branch, then docs. All are draft PRs — mark ready first or merge with `--admin` per Autonomous Ops. None conflict with main.

```bash
# 0. KEYSTONE — unblock Backend-Tests for everyone (NOT one of ONDA 2's 5)
gh pr ready 1027
gh pr merge 1027 --squash            # agent/nuzantara/backend-rag/fix-whatsapp-enrich-import

# 1. S3 — escalation storm fix (only executable-code branch; 14/14 tests pass)
gh pr ready 1032
gh pr merge 1032 --squash            # agent/air-m5/infra/s3-escalation-debt
#    THEN deploy-step (manual): install the shipped-but-unloaded plists on Pro:
#      launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.nuzantara.escalations-digest.weekly.plist
#      launchctl print gui/$(id -u)/com.nuzantara.escalations-prune   # verify it is LOADED

# 2. S10 — crm-quality audit (docs)
gh pr ready 1029
gh pr merge 1029 --squash            # agent/nuzantara/backend-rag/s10-crm-quality

# 3. S14 — nb-curation audit (docs)
gh pr ready 1028
gh pr merge 1028 --squash            # agent/nuzantara/intel/s14-nb-curation

# 4. S13 — agent-evolve audit + _proposed drafts (docs)
gh pr ready 1030
gh pr merge 1030 --squash            # agent/air-m5/organism/s13-agent-evolve

# 5. S2 — spec-graveyard audit (docs; re-touches W38 spec additively)
gh pr ready 1031
gh pr merge 1031 --squash            # agent/air-m5/docs/s2-spec-graveyard
```

**Notes for the operator:**
- `Detect Secrets` will stay red on the audit PRs (it trips on SHA/secret-name *strings* inside the FROZEN.json files — by design, not a leak). Override at merge if it's a required check, or whitelist the FROZEN paths.
- `Frontend Tests (mouth/admin-dashboard)` are red on all 5 identically = cross-cutting, not introduced by these PRs.
- After #1027, re-run CI on #1029/#1030/#1028 (`gh pr checks --watch` or push an empty commit) to see Backend-Tests flip green before merging if you want fully-green merges.
- These FROZEN audits **do not auto-execute** any of the NEEDS-ANTONELLO actions (W38 demotion, L5.2 gate flip, R2 Exa OAuth, NB deletes, CRM remediation). Merging the docs ≠ doing the work.

---

## 8. Provenance

- Operator checkout `feat/wa-army-launcher-2026-06-02` verified untouched before, during, after (dirty file set identical at start and end).
- All git ops read-only: `git fetch origin <branch>`, `git diff <merge-base> <branch>`, `git merge-tree`, `git show origin/<branch>:<path>`. No `checkout`, no `rebase`, no `merge`, no push to armata branches.
- Report authored in dedicated broker worktree `.worktrees/docs-generale-onda-2` (branch `agent/nuzantara/docs/generale-onda-2`), released after PR.
- Collision matrix double-method verified (comm + unique-count). Merge-tree double-form verified (legacy + `--write-tree` rc).
