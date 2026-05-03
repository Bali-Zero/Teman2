# Air Retirement Phase 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Free the Air today (2026-04-24) so it can be gifted to Ari within 48-72h, by moving all 33 Air cron jobs either to Pro (Cat2/Cat3) or to GitHub Actions on `Balizero1987/Teman2` (Cat1). Air stays powered for 48h as a parallel safety net with crontab disabled.

**Architecture:** Three destinations for three categories: Cat1 (6 HTTP-curl jobs) → GH Actions scheduled workflows on public repo `Balizero1987/Teman2`. Cat2 (19 Python/bash jobs, no Claude/Ollama) → Pro crontab with path/venv rewrite. Cat3 (7 Ollama-dependent jobs) → Pro crontab, reuses Pro's existing Ollama service.

**Tech Stack:** macOS `crontab`, GitHub Actions scheduled workflows, `gh` CLI, `scp` for script transfer, `ssh air` mDNS alias. Reference spec: `docs/superpowers/specs/2026-04-24-air-retirement-cloud-offload-design.md`.

---

## Reference — Full Air cron inventory (as of measurement 2026-04-24)

**Cat1 (HTTP-only, 6 entries) — destination GitHub Actions:**

| # | Air cron expression | Endpoint | WITA → UTC |
|---|---|---|---|
| C1.1 | `0 0 * * *` | `POST /api/cron/notifiers/all` | 00:00 WITA → 16:00 UTC prev day |
| C1.2 | `5 0 * * *` | `POST /api/cron/notifiers/birthday` | 00:05 WITA → 16:05 UTC prev day |
| C1.3 | `*/15 * * * *` | `POST /api/cron/notifiers/welcome-pending` | every 15 min (UTC=WITA offset-invariant) |
| C1.4 | `30 7 * * *` | `POST /api/admin/practice/auto-create` | 07:30 WITA → 23:30 UTC prev day |
| C1.5 | `0 23 * * *` | `POST /api/cron/notifiers/lkpm-deadlines` | 23:00 WITA → 15:00 UTC same day |
| C1.6 | `*/30 * * * *` | `POST /api/cron/notifiers/email-health` | every 30 min |

**Cat2 (Python/bash, 19 entries) — destination Pro:**

| # | Schedule | Air command | Pro-rewritten command |
|---|---|---|---|
| C2.1 | `0 5 * * *` | `$AIR_P/scripts/cron-wrapper.sh kb-ingest $AIR_P/scripts/auto_kb_ingest.sh` | See Task 3 |
| C2.2 | `30 */6 * * *` | `cron-wrapper.sh rag-canary bash -c 'cd $AIR_P && $AIR_P/apps/backend-rag/venv/bin/python3 scripts/rag_canary.py'` | See Task 3 |
| C2.3 | `0 8 * * *` | `cron-wrapper.sh system-doctor bash -c '... system_doctor.py --notify-telegram'` | See Task 3 |
| C2.4 | `0 */6 * * *` | `cron-wrapper.sh drive-watchdog bash -c '... drive_token_watchdog.py'` | See Task 3 |
| C2.5 | `0 1 * * *` | `cron-wrapper.sh seo-guardian bash -c '... seo_guardian_agent.py --observe-first'` | See Task 3 |
| C2.6 | `0 */6 * * *` | `cron-wrapper.sh t4-monitor /bin/bash .../run_t4_monitor.sh` | See Task 3 |
| C2.7 | `0 23 * * *` | `cron-wrapper.sh crm-automation bash -c '... crm_automation_engine.py'` | See Task 3 |
| C2.8 | `30 3 1,15 * *` | `npm cache clean --force && pip cache purge && brew cleanup` | See Task 3 |
| C2.9 | `20 3 * * *` | `cron-wrapper.sh fly-pg-backup /Users/antonellosiano/scripts/fly-pg-backup.sh` | See Task 3 |
| C2.10 | `0 4 * * 0` | `cron-wrapper.sh qdrant-snapshot /Users/antonellosiano/scripts/qdrant-snapshot.sh` | See Task 3 |
| C2.11 | `30 20 * * *` | `cron-wrapper.sh db-nlm-sync .../run_db_nlm_sync.sh` | See Task 3 |
| C2.12 | `0 * * * *` | `$HOME/sync-damar.sh` | See Task 3 |
| C2.13 | `0 4 * * *` | `cp ~/.claude/memory.db ~/.claude/backups/memory_$(date +%Y%m%d).db` | See Task 3 |
| C2.14 | `0 5 * * 0` | `find ~/.claude/backups -name "memory_*.db" -mtime +30 -delete` | See Task 3 |
| C2.15 | `0 5 * * *` | `sqlite3 ~/.claude/memory.db 'DELETE FROM memories WHERE ttl_days IS NOT NULL...'` | See Task 3 |
| C2.16 | `40 3 * * 0` | `NB_SESSION_ID=... bash ~/.claude/scripts/sync-memory-to-nlm.sh` | See Task 3 |
| C2.17 | `0 2 * * 0` | `~/scripts/audit_trail_cleanup.sh` | See Task 3 |
| C2.18 | `0 9 * * *` | `$AIR_P/apps/backend-rag/venv/bin/python3 scripts/job_health.py --alert` | See Task 3 |
| C2.19 | `0 1 * * 1` | `cron-wrapper.sh owner-cashout-sync $AIR_P/scripts/sync_owner_cashout_fly.sh` | See Task 3 |
| C2.20 | `0 9 * * *` | `source ~/.nuzantara-secrets.env && $AIR_P/scripts/sentry-quota-check.sh` | See Task 3 |

(Note: 20 entries listed — C2.1 = kb-ingest is Ollama-adjacent because it uses bge-m3 embeddings, but it does HTTP to Fly Qdrant not local Ollama. Keeping in Cat2 unless preflight shows otherwise.)

**Cat3 (Ollama-dependent, 7 entries) — destination Pro with Ollama window:**

| # | Schedule | Purpose | Depends on |
|---|---|---|---|
| C3.1 | `0 1 * * *` | `ollama_cron_window.sh start` — open Ollama window | Pro Ollama service |
| C3.2 | `15 2 * * *` | `auto_test.sh` — backend tests with Qwen | Ollama running |
| C3.3 | `0 3 * * *` | `auto_sentinel.sh` — sentinel quality check | Ollama running |
| C3.4 | `0 16 * * 0` | `auto_judgement_day.sh` — RAG evaluation | Ollama running |
| C3.5 | `0 6 * * 6` | `ragas_eval.py` — RAGAS metrics Saturday | Ollama + `ragas` python pkg |
| C3.6 | `0 5 * * 0` | `brew services restart ollama && ollama-warm-pin.sh` | Pro has same script already — may deduplicate |
| C3.7 | `AIR_P$/scripts/ollama_cron_window.sh stop` (implicit via schedule end) | Close Ollama window | N/A |

Where `$AIR_P` = `/Users/antonellosiano/Projects/nuzantara` throughout.

**Cat1 Teman2 repo:** `Balizero1987/Teman2` (public, already has 12 workflows, Actions enabled). Repo root locally at a checked-out copy — clone path to be decided in Task 4.

---

## File Structure (what gets created / modified)

**On Pro (`/Users/nuzantara`):**
- `scripts/qdrant-snapshot.sh` — Create (copied from Air)
- `scripts/sentry-quota-check.sh` — Create (copied from Air)
- `scripts/audit_trail_cleanup.sh` — Create (copied from Air)
- `scripts/audit_trail_cleanup.py` — Create (copied from Air)
- `Desktop/nuzantara/apps/backend-rag/scripts/rag_canary.py` — Create (copied from Air)
- `Desktop/nuzantara/apps/backend-rag/scripts/system_doctor.py` — Create (copied from Air)
- `Desktop/nuzantara/apps/backend-rag/scripts/drive_token_watchdog.py` — Create (copied from Air)
- `Desktop/nuzantara/apps/backend-rag/scripts/ragas_eval.py` — Create (copied from Air)
- `Desktop/nuzantara/apps/backend-rag/scripts/job_health.py` — Create (copied from Air)
- `$HOME/sync-damar.sh` — Create if missing (Air has it in $HOME)
- Pro crontab — Modify: append 26 new lines (Cat2 + Cat3)
- `~/air-retirement-2026-04-24/` — Create (working directory for logs, backups, checklist)

**On Teman2 repo (`.github/workflows/`):**
- `cron-notifiers-all.yml` — Create
- `cron-notifiers-birthday.yml` — Create
- `cron-notifiers-welcome-pending.yml` — Create
- `cron-practice-auto-create.yml` — Create
- `cron-notifiers-lkpm-deadlines.yml` — Create
- `cron-notifiers-email-health.yml` — Create

**GitHub secret on Balizero1987/Teman2:**
- `NUZANTARA_API_KEY` — Create/verify (value: `zantara-secret-2024`)

**On Air:**
- `~/air-crontab-backup-2026-04-24.txt` — Create (backup of current crontab)
- `~/air-crontab-status.txt` — Create (status marker)
- Air crontab — Modify: deactivated via `crontab -r`

---

## Task 0: Pre-flight checks

**Files:** none (read-only investigation)

- [ ] **Step 0.1: Confirm SSH to Air works**

Run:
```
ssh -o ConnectTimeout=5 air 'echo OK; uname -n; date'
```
Expected: `OK` + `Nuzantara-9.local` + current date. If fails, abort — can't migrate without Air access.

- [ ] **Step 0.2: Confirm Pro cron-wrapper.sh signature matches Air's**

Run:
```
diff <(ssh air 'cat /Users/antonellosiano/Projects/nuzantara/scripts/cron-wrapper.sh') /Users/nuzantara/Desktop/nuzantara/scripts/cron-wrapper.sh | head -40
```
Expected: either identical (ideal) or only cosmetic path differences. If the signature `cron-wrapper.sh <job-name> <command...>` differs, Task 3 crontab lines must be adapted. Note any semantic divergence in `~/air-retirement-2026-04-24/preflight-notes.md`.

- [ ] **Step 0.3: Verify Pro has scripts referenced by Air cron but not in Air-unique list**

Run:
```
for f in \
  /Users/nuzantara/Desktop/nuzantara/apps/evaluator/seo_guardian_agent.py \
  /Users/nuzantara/Desktop/nuzantara/apps/evaluator/nlm_deep_research/scripts/run_t4_monitor.sh \
  /Users/nuzantara/Desktop/nuzantara/apps/evaluator/nlm_deep_research/scripts/run_db_nlm_sync.sh \
  /Users/nuzantara/Desktop/nuzantara/scripts/auto_kb_ingest.sh \
  /Users/nuzantara/Desktop/nuzantara/scripts/auto_test.sh \
  /Users/nuzantara/Desktop/nuzantara/scripts/auto_sentinel.sh \
  /Users/nuzantara/Desktop/nuzantara/scripts/auto_judgement_day.sh \
  /Users/nuzantara/Desktop/nuzantara/scripts/ollama_cron_window.sh \
  /Users/nuzantara/Desktop/nuzantara/scripts/sync_owner_cashout_fly.sh \
  /Users/nuzantara/.claude/scripts/sync-memory-to-nlm.sh \
  ; do
  if [ -f "$f" ]; then echo "✓ $f"; else echo "✗ MISSING $f"; fi
done
```
Expected: mostly ✓. Any ✗ gets added to the Task 1 copy list.

- [ ] **Step 0.4: Verify Pro venv has ragas package (needed by C3.5)**

Run:
```
/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python3 -c "import ragas; print(ragas.__version__)"
```
Expected: version string. If `ModuleNotFoundError`, add `pip install ragas` to Task 1.

- [ ] **Step 0.5: Verify Pro Ollama has bge-m3 and qwen3.5 models pulled**

Run:
```
curl -s http://localhost:11434/api/tags | python3 -c "import sys, json; names=[m['name'] for m in json.load(sys.stdin)['models']]; print('\n'.join(names))"
```
Expected: list includes `bge-m3:*` and `qwen3.5:*` (or whatever exact tags Air uses). If missing, add `ollama pull bge-m3` / `ollama pull qwen3.5:9b` to Task 5.

- [ ] **Step 0.6: Check Pro Ollama window 01:00-06:00 WITA has capacity**

Run:
```
crontab -l | awk '$1 ~ /^[0-9*/,-]+$/ && $2 ~ /^(0?[1-5]|[0-5]):?/' | grep -vE '^\s*#'
crontab -l | awk 'NR>1 { h=$2; if (h ~ /^[12345]$/ || h == "*" ) print }' | head -20
```
Expected: inspect what Pro does 01-06 WITA. Document in preflight-notes.md. If collisions with heavy jobs (>5 min runtime), Task 5 will stagger Air's 01:00, 02:15, 03:00 times by +15 min to avoid overlap.

- [ ] **Step 0.7: Create working directory and checklist**

Run:
```
mkdir -p ~/air-retirement-2026-04-24
cd ~/air-retirement-2026-04-24
touch preflight-notes.md
touch migration-log.md
echo "$(date -u +%FT%TZ) — Phase 1 start" > migration-log.md
```

- [ ] **Step 0.8: Commit preflight notes**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add docs/superpowers/plans/2026-04-24-air-retirement-phase1.md docs/superpowers/specs/2026-04-24-air-retirement-cloud-offload-design.md
git commit -m "docs(ops): add Air retirement Phase 1 plan + spec

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 1: Copy Air-only scripts to Pro

**Files:**
- Create: `/Users/nuzantara/scripts/qdrant-snapshot.sh`
- Create: `/Users/nuzantara/scripts/sentry-quota-check.sh`
- Create: `/Users/nuzantara/scripts/audit_trail_cleanup.sh`
- Create: `/Users/nuzantara/scripts/audit_trail_cleanup.py`
- Create: `/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/scripts/rag_canary.py`
- Create: `/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/scripts/system_doctor.py`
- Create: `/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/scripts/drive_token_watchdog.py`
- Create: `/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/scripts/ragas_eval.py`
- Create: `/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/scripts/job_health.py`
- Create: `/Users/nuzantara/sync-damar.sh` (from Air `~/sync-damar.sh` — only if Pro doesn't already have an equivalent at `/Users/nuzantara/Desktop/nuzantara/scripts/sync-damar.sh`)

- [ ] **Step 1.1: Check sync-damar.sh collision**

Run:
```
ls -la /Users/nuzantara/sync-damar.sh /Users/nuzantara/Desktop/nuzantara/scripts/sync-damar.sh 2>&1
```
Expected: only the `Desktop/nuzantara/scripts/` one exists (Pro's own), `/Users/nuzantara/sync-damar.sh` does NOT exist. If BOTH exist and are different, investigate which Air uses with `ssh air 'head -5 ~/sync-damar.sh'` vs the Pro version — pick the one Air's crontab references (`$HOME/sync-damar.sh` → Air uses `/Users/antonellosiano/sync-damar.sh`).

- [ ] **Step 1.2: Copy bash scripts Air → Pro `/Users/nuzantara/scripts/`**

Run:
```
scp air:/Users/antonellosiano/scripts/qdrant-snapshot.sh /Users/nuzantara/scripts/
scp air:/Users/antonellosiano/scripts/sentry-quota-check.sh /Users/nuzantara/scripts/
scp air:/Users/antonellosiano/scripts/audit_trail_cleanup.sh /Users/nuzantara/scripts/
scp air:/Users/antonellosiano/scripts/audit_trail_cleanup.py /Users/nuzantara/scripts/
chmod +x /Users/nuzantara/scripts/qdrant-snapshot.sh /Users/nuzantara/scripts/sentry-quota-check.sh /Users/nuzantara/scripts/audit_trail_cleanup.sh
```
Expected: 4 files transferred, chmod applied. Run `ls -la /Users/nuzantara/scripts/{qdrant-snapshot,sentry-quota-check,audit_trail_cleanup}.sh` to verify.

- [ ] **Step 1.3: Copy sync-damar.sh to $HOME if missing**

Run (only if Step 1.1 showed Pro lacks `/Users/nuzantara/sync-damar.sh`):
```
scp air:/Users/antonellosiano/sync-damar.sh /Users/nuzantara/sync-damar.sh
chmod +x /Users/nuzantara/sync-damar.sh
```
Expected: file created or already exists.

- [ ] **Step 1.4: Copy Python scripts Air → Pro backend-rag/scripts/**

Run:
```
BACKEND_SCRIPTS=/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/scripts
scp air:/Users/antonellosiano/Projects/nuzantara/apps/backend-rag/scripts/rag_canary.py $BACKEND_SCRIPTS/
scp air:/Users/antonellosiano/Projects/nuzantara/apps/backend-rag/scripts/system_doctor.py $BACKEND_SCRIPTS/
scp air:/Users/antonellosiano/Projects/nuzantara/apps/backend-rag/scripts/drive_token_watchdog.py $BACKEND_SCRIPTS/
scp air:/Users/antonellosiano/Projects/nuzantara/apps/backend-rag/scripts/ragas_eval.py $BACKEND_SCRIPTS/
scp air:/Users/antonellosiano/Projects/nuzantara/apps/backend-rag/scripts/job_health.py $BACKEND_SCRIPTS/
```
Expected: 5 files transferred.

- [ ] **Step 1.5: Rewrite hardcoded Air paths in copied scripts**

Some copied scripts may contain hardcoded `/Users/antonellosiano/...` paths. Grep and fix:
```
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/scripts
grep -l 'antonellosiano' rag_canary.py system_doctor.py drive_token_watchdog.py ragas_eval.py job_health.py 2>/dev/null
```
Expected: list of files containing the string. For each match:
```
sed -i '' 's|/Users/antonellosiano/Projects/nuzantara|/Users/nuzantara/Desktop/nuzantara|g' <file>
sed -i '' 's|/Users/antonellosiano|/Users/nuzantara|g' <file>
sed -i '' 's|/backend-rag/venv/|/backend-rag/.venv/|g' <file>
```
Also check the `/Users/nuzantara/scripts/` bash scripts the same way.

- [ ] **Step 1.6: Install missing Python deps for new scripts**

Run:
```
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
source .venv/bin/activate
# Only if Step 0.4 showed ragas missing:
pip install ragas
# If any import error surfaces when running a script in dry-run (Task 3), also install those
deactivate
```
Expected: installs complete with no errors.

- [ ] **Step 1.7: Manual smoke test each copied script (dry-run)**

For each of the 5 Python scripts + 3 bash scripts copied, run a harmless invocation:
```
/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python3 \
  /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/scripts/rag_canary.py --help 2>&1 | head -20
# Repeat for system_doctor.py (has --notify-telegram flag, try without notifying first), drive_token_watchdog.py, job_health.py
bash -n /Users/nuzantara/scripts/qdrant-snapshot.sh
bash -n /Users/nuzantara/scripts/sentry-quota-check.sh
bash -n /Users/nuzantara/scripts/audit_trail_cleanup.sh
```
Expected: `--help` returns usage text or a banner (no traceback); `bash -n` returns silent (syntax OK). If ModuleNotFoundError on any Python script, fix per Step 1.6.

- [ ] **Step 1.8: Commit copied scripts**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/backend-rag/scripts/rag_canary.py \
        apps/backend-rag/scripts/system_doctor.py \
        apps/backend-rag/scripts/drive_token_watchdog.py \
        apps/backend-rag/scripts/ragas_eval.py \
        apps/backend-rag/scripts/job_health.py
git commit -m "feat(ops): port Air-only backend scripts to Pro

Part of Air retirement Phase 1. Scripts previously lived only on Air
at /Users/antonellosiano/Projects/nuzantara/apps/backend-rag/scripts/.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

Bash scripts under `/Users/nuzantara/scripts/` are NOT in the git repo — they stay as personal scripts on Pro filesystem. No git add for those.

---

## Task 2: Backup Pro crontab before modification

**Files:**
- Create: `~/air-retirement-2026-04-24/pro-crontab-before-2026-04-24.txt`

- [ ] **Step 2.1: Snapshot current Pro crontab**

Run:
```
crontab -l > ~/air-retirement-2026-04-24/pro-crontab-before-2026-04-24.txt
wc -l ~/air-retirement-2026-04-24/pro-crontab-before-2026-04-24.txt
```
Expected: ~80-90 lines total (75 active + comments + PATH).

- [ ] **Step 2.2: Verify backup is complete**

Run:
```
grep -c '^[^#]*\*' ~/air-retirement-2026-04-24/pro-crontab-before-2026-04-24.txt
```
Expected: ~75 (active cron entries).

---

## Task 3: Append Cat2 jobs to Pro crontab

**Files:**
- Modify: Pro crontab (via `crontab -e` — append 20 lines for Cat2)

- [ ] **Step 3.1: Construct the 20 new Cat2 lines in a staging file**

Create `~/air-retirement-2026-04-24/new-cron-cat2.txt` with the following exact content. Each line is the Pro-equivalent of an Air Cat2 line, with path/venv rewrites applied.

Path substitutions applied throughout:
- `/Users/antonellosiano/Projects/nuzantara` → `/Users/nuzantara/Desktop/nuzantara`
- `/Users/antonellosiano/scripts` → `/Users/nuzantara/scripts`
- `/Users/antonellosiano/logs` → `/Users/nuzantara/logs`
- `/Users/antonellosiano` (as $HOME) → `/Users/nuzantara`
- `apps/backend-rag/venv/bin/python3` → `apps/backend-rag/.venv/bin/python3`

```
# === AIR RETIREMENT PHASE 1 — Cat2 jobs ported from Air 2026-04-24 ===
# Source crontab: ~/air-retirement-2026-04-24/air-crontab-backup-2026-04-24.txt

# C2.1 kb-ingest (daily 05:00 WITA)
0 5 * * * /Users/nuzantara/Desktop/nuzantara/scripts/cron-wrapper.sh kb-ingest /Users/nuzantara/Desktop/nuzantara/scripts/auto_kb_ingest.sh

# C2.2 rag-canary (every 6h at :30)
30 */6 * * * /Users/nuzantara/Desktop/nuzantara/scripts/cron-wrapper.sh rag-canary bash -c 'cd /Users/nuzantara/Desktop/nuzantara && /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python3 apps/backend-rag/scripts/rag_canary.py'

# C2.3 system-doctor (daily 08:00 WITA)
0 8 * * * /Users/nuzantara/Desktop/nuzantara/scripts/cron-wrapper.sh system-doctor bash -c 'cd /Users/nuzantara/Desktop/nuzantara && /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python3 apps/backend-rag/scripts/system_doctor.py --notify-telegram'

# C2.4 drive-watchdog (every 6h)
0 */6 * * * /Users/nuzantara/Desktop/nuzantara/scripts/cron-wrapper.sh drive-watchdog bash -c 'cd /Users/nuzantara/Desktop/nuzantara && /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python3 apps/backend-rag/scripts/drive_token_watchdog.py'

# C2.5 seo-guardian (daily 09:00 WITA = 01:00 UTC)
0 1 * * * CRON_TIMEOUT=600 /Users/nuzantara/Desktop/nuzantara/scripts/cron-wrapper.sh seo-guardian bash -c 'cd /Users/nuzantara/Desktop/nuzantara && /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python apps/evaluator/seo_guardian_agent.py --observe-first'

# C2.6 t4-monitor (every 6h)
0 */6 * * * /Users/nuzantara/Desktop/nuzantara/scripts/cron-wrapper.sh t4-monitor /bin/bash /Users/nuzantara/Desktop/nuzantara/apps/evaluator/nlm_deep_research/scripts/run_t4_monitor.sh

# C2.7 crm-automation (daily 23:00 UTC = 07:00 WITA)
0 23 * * * /Users/nuzantara/Desktop/nuzantara/scripts/cron-wrapper.sh crm-automation bash -c 'cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python3 scripts/crm_automation_engine.py'

# C2.8 cache cleanup (1st + 15th of month 03:30) — Pro already has equivalent; skip to avoid duplicate
# DUPLICATE_SKIPPED: Pro crontab already has this job (verify with grep 'cache clean')

# C2.9 fly-pg-backup (daily 03:20)
20 3 * * * /Users/nuzantara/Desktop/nuzantara/scripts/cron-wrapper.sh fly-pg-backup /Users/nuzantara/scripts/fly-pg-backup.sh

# C2.10 qdrant-snapshot (Sunday 04:00)
0 4 * * 0 CRON_TIMEOUT=600 /Users/nuzantara/Desktop/nuzantara/scripts/cron-wrapper.sh qdrant-snapshot /Users/nuzantara/scripts/qdrant-snapshot.sh

# C2.11 db-nlm-sync (daily 20:30 UTC = 04:30 WITA)
30 20 * * * /Users/nuzantara/Desktop/nuzantara/scripts/cron-wrapper.sh db-nlm-sync /Users/nuzantara/Desktop/nuzantara/apps/evaluator/nlm_deep_research/scripts/run_db_nlm_sync.sh

# C2.12 sync-damar hourly — Pro already has it; skip
# DUPLICATE_SKIPPED: Pro crontab line `0 * * * * /bin/bash /Users/nuzantara/Desktop/nuzantara/scripts/sync-damar.sh` already exists

# C2.13 claude memory db backup (daily 04:00)
0 4 * * * cp /Users/nuzantara/.claude/memory.db /Users/nuzantara/.claude/backups/memory_$(date +\%Y\%m\%d).db 2>/dev/null

# C2.14 claude memory backup purge >30d (Sunday 05:00)
0 5 * * 0 find /Users/nuzantara/.claude/backups -name "memory_*.db" -mtime +30 -delete 2>/dev/null

# C2.15 claude memory ttl sweep (daily 05:00)
0 5 * * * sqlite3 /Users/nuzantara/.claude/memory.db 'DELETE FROM memories WHERE ttl_days IS NOT NULL AND julianday("now") - julianday(created_at) > ttl_days;' 2>/dev/null

# C2.16 memory→NLM sync (Sunday 03:40)
40 3 * * 0 NB_SESSION_ID=1e5f9b04-9485-4620-a775-801b7e6b0395 bash /Users/nuzantara/.claude/scripts/sync-memory-to-nlm.sh >> /tmp/cron-mos-sync.log 2>&1

# C2.17 audit trail cleanup (Sunday 02:00)
0 2 * * 0 /Users/nuzantara/scripts/audit_trail_cleanup.sh >> /tmp/cron-audit-cleanup.log 2>&1

# C2.18 job-health (daily 09:00)
0 9 * * * /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python3 /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/scripts/job_health.py --alert >> /Users/nuzantara/logs/cron/job-health.log 2>&1

# C2.19 owner-cashout-sync (Monday 01:00)
0 1 * * 1 /Users/nuzantara/Desktop/nuzantara/scripts/cron-wrapper.sh owner-cashout-sync /Users/nuzantara/Desktop/nuzantara/scripts/sync_owner_cashout_fly.sh

# C2.20 sentry quota check (daily 09:00)
0 9 * * * source /Users/nuzantara/.nuzantara-secrets.env && /Users/nuzantara/scripts/sentry-quota-check.sh >> /Users/nuzantara/logs/sentry_quota_check.log 2>&1
```

Save via `nano ~/air-retirement-2026-04-24/new-cron-cat2.txt` or equivalent.

- [ ] **Step 3.2: Check for duplicates against existing Pro crontab**

Run:
```
grep -E 'sync-damar|cache clean' ~/air-retirement-2026-04-24/pro-crontab-before-2026-04-24.txt
```
Expected: confirms C2.8 (cache cleanup) and C2.12 (sync-damar) are already on Pro. If NOT present on Pro, remove the `DUPLICATE_SKIPPED:` comments and un-comment the lines in `new-cron-cat2.txt`.

- [ ] **Step 3.3: Dry-run each new line manually**

For each line in `new-cron-cat2.txt` (skip the duplicates), extract the command part (everything after the schedule expression) and run with `bash -x`:
```
# Example for C2.3:
bash -x -c 'cd /Users/nuzantara/Desktop/nuzantara && /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python3 apps/backend-rag/scripts/system_doctor.py --notify-telegram 2>&1 | head -5' || echo "FAILED: $?"
```
Expected: either success (with Telegram message if applicable) or a specific error visible. Document failures in migration-log.md. **If a line fails, fix before including in crontab** — a silent-fail cron is worse than no cron.

For time-window-sensitive jobs (ollama-dependent in Cat3, covered later), skip dry-run and rely on first scheduled execution.

- [ ] **Step 3.4: Append validated lines to Pro crontab**

Run:
```
(crontab -l; echo ""; cat ~/air-retirement-2026-04-24/new-cron-cat2.txt) | crontab -
crontab -l | tail -50
```
Expected: Pro crontab now has the Cat2 lines appended. Verify counts:
```
# Before: 75 active (from Step 2.1)
# After should be: 75 + (20 minus DUPLICATE_SKIPPED) ≈ 93 active
crontab -l | grep -vE '^\s*#|^\s*$|^PATH=' | wc -l
```

- [ ] **Step 3.5: Commit new-cron-cat2.txt for audit trail**

The file `~/air-retirement-2026-04-24/new-cron-cat2.txt` is NOT in the repo — keep in home dir. But create a committed record:
```bash
mkdir -p /Users/nuzantara/Desktop/nuzantara/reports/air-retirement
cp ~/air-retirement-2026-04-24/new-cron-cat2.txt /Users/nuzantara/Desktop/nuzantara/reports/air-retirement/
cp ~/air-retirement-2026-04-24/pro-crontab-before-2026-04-24.txt /Users/nuzantara/Desktop/nuzantara/reports/air-retirement/
cd /Users/nuzantara/Desktop/nuzantara
git add reports/air-retirement/
git commit -m "chore(ops): record Pro crontab state before + Cat2 additions

Part of Air retirement Phase 1.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Cat1 — GitHub Actions workflows on Teman2

**Files (create on `Balizero1987/Teman2` repo, branch `ops/air-retirement-cron-migration`):**
- Create: `.github/workflows/cron-notifiers-all.yml`
- Create: `.github/workflows/cron-notifiers-birthday.yml`
- Create: `.github/workflows/cron-notifiers-welcome-pending.yml`
- Create: `.github/workflows/cron-practice-auto-create.yml`
- Create: `.github/workflows/cron-notifiers-lkpm-deadlines.yml`
- Create: `.github/workflows/cron-notifiers-email-health.yml`

- [ ] **Step 4.1: Clone Teman2 locally if not already**

Run:
```
cd ~
test -d Teman2 || gh repo clone Balizero1987/Teman2
cd ~/Teman2
git fetch origin
git checkout main
git pull --ff-only
git checkout -b ops/air-retirement-cron-migration
```
Expected: fresh branch ready.

- [ ] **Step 4.2: Verify/create `NUZANTARA_API_KEY` secret**

Run:
```
gh secret list -R Balizero1987/Teman2 | grep NUZANTARA_API_KEY
```
If not listed:
```
gh secret set NUZANTARA_API_KEY -R Balizero1987/Teman2 --body 'zantara-secret-2024'
```
Expected: `✓ Set Actions secret NUZANTARA_API_KEY`.

- [ ] **Step 4.3: Create workflow file `cron-notifiers-all.yml`**

Content:
```yaml
name: cron - notifiers all (daily 00:00 WITA)
on:
  schedule:
    - cron: '0 16 * * *'   # 16:00 UTC = 00:00 WITA next day
  workflow_dispatch: {}

jobs:
  run:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - name: POST /api/cron/notifiers/all
        run: |
          curl -fsS -X POST https://nuzantara-rag.fly.dev/api/cron/notifiers/all \
            -H "X-API-Key: ${{ secrets.NUZANTARA_API_KEY }}" \
            -w '\nHTTP %{http_code} in %{time_total}s\n'
```

Save to `~/Teman2/.github/workflows/cron-notifiers-all.yml`.

- [ ] **Step 4.4: Create `cron-notifiers-birthday.yml`**

Content:
```yaml
name: cron - notifiers birthday (daily 00:05 WITA)
on:
  schedule:
    - cron: '5 16 * * *'   # 16:05 UTC = 00:05 WITA next day
  workflow_dispatch: {}

jobs:
  run:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - name: POST /api/cron/notifiers/birthday
        run: |
          curl -fsS -X POST https://nuzantara-rag.fly.dev/api/cron/notifiers/birthday \
            -H "X-API-Key: ${{ secrets.NUZANTARA_API_KEY }}" \
            -w '\nHTTP %{http_code} in %{time_total}s\n'
```

- [ ] **Step 4.5: Create `cron-notifiers-welcome-pending.yml`**

Content:
```yaml
name: cron - notifiers welcome-pending (every 15 min)
on:
  schedule:
    - cron: '*/15 * * * *'
  workflow_dispatch: {}

jobs:
  run:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - name: POST /api/cron/notifiers/welcome-pending
        run: |
          curl -fsS -X POST https://nuzantara-rag.fly.dev/api/cron/notifiers/welcome-pending \
            -H "X-API-Key: ${{ secrets.NUZANTARA_API_KEY }}" \
            -w '\nHTTP %{http_code} in %{time_total}s\n'
```

- [ ] **Step 4.6: Create `cron-practice-auto-create.yml`**

Content:
```yaml
name: cron - practice auto-create (daily 07:30 WITA)
on:
  schedule:
    - cron: '30 23 * * *'  # 23:30 UTC = 07:30 WITA next day
  workflow_dispatch: {}

jobs:
  run:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - name: POST /api/admin/practice/auto-create
        run: |
          curl -fsS -X POST https://nuzantara-rag.fly.dev/api/admin/practice/auto-create \
            -H "X-API-Key: ${{ secrets.NUZANTARA_API_KEY }}" \
            -w '\nHTTP %{http_code} in %{time_total}s\n'
```

- [ ] **Step 4.7: Create `cron-notifiers-lkpm-deadlines.yml`**

Content:
```yaml
name: cron - notifiers lkpm-deadlines (daily 23:00 WITA)
on:
  schedule:
    - cron: '0 15 * * *'   # 15:00 UTC = 23:00 WITA same day
  workflow_dispatch: {}

jobs:
  run:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - name: POST /api/cron/notifiers/lkpm-deadlines
        run: |
          curl -fsS -X POST https://nuzantara-rag.fly.dev/api/cron/notifiers/lkpm-deadlines \
            -H "X-API-Key: ${{ secrets.NUZANTARA_API_KEY }}" \
            -w '\nHTTP %{http_code} in %{time_total}s\n'
```

- [ ] **Step 4.8: Create `cron-notifiers-email-health.yml`**

Content:
```yaml
name: cron - notifiers email-health (every 30 min)
on:
  schedule:
    - cron: '*/30 * * * *'
  workflow_dispatch: {}

jobs:
  run:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - name: POST /api/cron/notifiers/email-health
        run: |
          curl -fsS -X POST https://nuzantara-rag.fly.dev/api/cron/notifiers/email-health \
            -H "X-API-Key: ${{ secrets.NUZANTARA_API_KEY }}" \
            -w '\nHTTP %{http_code} in %{time_total}s\n'
```

- [ ] **Step 4.9: Commit workflow files on feature branch**

```
cd ~/Teman2
git add .github/workflows/cron-notifiers-all.yml \
        .github/workflows/cron-notifiers-birthday.yml \
        .github/workflows/cron-notifiers-welcome-pending.yml \
        .github/workflows/cron-practice-auto-create.yml \
        .github/workflows/cron-notifiers-lkpm-deadlines.yml \
        .github/workflows/cron-notifiers-email-health.yml
git commit -m "feat(ops): migrate 6 Air HTTP cron jobs to GitHub Actions

Part of Air retirement Phase 1. These workflows replace curl-based
cron entries that previously ran on /Users/antonellosiano's machine.
Schedules expressed in UTC; original WITA (UTC+8) noted in each file's name.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push -u origin ops/air-retirement-cron-migration
```

- [ ] **Step 4.10: Open PR and merge to main**

```
cd ~/Teman2
gh pr create --fill --title "ops: migrate 6 Air HTTP cron jobs to GitHub Actions"
# After PR checks pass:
gh pr merge --squash --delete-branch
```
Expected: PR opens, checks run (should be a no-op for these yml-only changes), merge succeeds.

- [ ] **Step 4.11: Manually trigger each workflow once to verify**

```
for w in cron-notifiers-all cron-notifiers-birthday cron-notifiers-welcome-pending cron-practice-auto-create cron-notifiers-lkpm-deadlines cron-notifiers-email-health; do
  gh workflow run "$w.yml" -R Balizero1987/Teman2
done
sleep 45
gh run list -R Balizero1987/Teman2 --limit 10 --workflow cron-notifiers-welcome-pending.yml
```
Expected: each run shows `completed success`. If any shows `failure`:
```
gh run view <run-id> -R Balizero1987/Teman2 --log-failed
```
Fix the endpoint URL or API key and re-run. Record in migration-log.md.

---

## Task 5: Append Cat3 (Ollama) jobs to Pro crontab

**Files:**
- Modify: Pro crontab (append 6-7 lines)

- [ ] **Step 5.1: Verify Pro does not already run equivalent Ollama jobs**

Run:
```
crontab -l | grep -E 'ollama_cron_window|auto_test\.sh|auto_sentinel\.sh|auto_judgement|ragas_eval|ollama-warm-pin'
```
Expected: either empty (clean slate) or a few of the jobs already present. Mark duplicates in `~/air-retirement-2026-04-24/cat3-duplicates.txt` so Step 5.2 skips them.

- [ ] **Step 5.2: Construct 7 new Cat3 lines**

Create `~/air-retirement-2026-04-24/new-cron-cat3.txt`. Apply Task 3 path substitutions:

```
# === AIR RETIREMENT PHASE 1 — Cat3 Ollama jobs ported from Air 2026-04-24 ===
# Ollama nightly window 01:00-06:00 WITA (17:00-22:00 UTC prev day).
# Pro already runs Ollama H24 via homebrew, so ollama_cron_window.sh may be a no-op — keep for parity.

# C3.1 ollama cron window START (daily 01:00 WITA = 17:00 UTC prev day)
0 17 * * * /Users/nuzantara/Desktop/nuzantara/scripts/ollama_cron_window.sh start >> /Users/nuzantara/logs/ollama_cron.log 2>&1

# C3.2 auto-test (daily 02:15 WITA = 18:15 UTC)
15 18 * * * /Users/nuzantara/Desktop/nuzantara/scripts/auto_test.sh >> /Users/nuzantara/logs/auto_test.log 2>&1

# C3.3 auto-sentinel (daily 03:00 WITA = 19:00 UTC)
0 19 * * * /Users/nuzantara/Desktop/nuzantara/scripts/auto_sentinel.sh >> /Users/nuzantara/logs/sentinel_nightly.log 2>&1

# C3.4 auto-judgement day (Sunday 16:00 WITA = 08:00 UTC)
0 8 * * 0 /Users/nuzantara/Desktop/nuzantara/scripts/auto_judgement_day.sh >> /Users/nuzantara/logs/judgement_day.log 2>&1

# C3.5 ragas eval (Saturday 06:00 WITA = 22:00 UTC Friday)
0 22 * * 5 cd /Users/nuzantara/Desktop/nuzantara && /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python3 apps/backend-rag/scripts/ragas_eval.py >> /Users/nuzantara/logs/ragas_eval.log 2>&1

# C3.6 ollama warm restart (Sunday 05:00 WITA = 21:00 UTC Saturday) — SKIP if Pro already has equivalent
# DUPLICATE_CHECK: `brew services restart ollama && ~/scripts/ollama-warm-pin.sh` — Pro crontab has `0 5 * * 0 brew services restart ollama && sleep 15 && /Users/nuzantara/scripts/ollama-warm-pin.sh`
# Time differs (Pro: 05:00 Sun WITA; Air: also 05:00 Sun WITA) — same schedule, same effect. SKIP C3.6.

# C3.7 ollama cron window STOP (daily 06:05 WITA = 22:05 UTC prev day)
5 22 * * * /Users/nuzantara/Desktop/nuzantara/scripts/ollama_cron_window.sh stop >> /Users/nuzantara/logs/ollama_cron.log 2>&1
```

- [ ] **Step 5.3: Check for time collisions in Pro 17:00-22:05 UTC window**

Run:
```
crontab -l | awk '{
  if ($0 ~ /^#|^$|^PATH=/) next
  split($2, h, ",")
  for (i in h) {
    hh = h[i]
    if (hh ~ /^[0-9]+$/ && hh+0 >= 17 && hh+0 <= 22) print
    if (hh == "*") print "STAR:", $0
  }
}' | head -30
```
Expected: review list. If more than 3-4 jobs already occupy this window with heavy work (>5min), stagger C3.2 (18:15 UTC) to 18:35 UTC, C3.3 (19:00) to 19:20, etc. Document choice in migration-log.md.

- [ ] **Step 5.4: Append Cat3 lines to Pro crontab**

Run:
```
(crontab -l; echo ""; cat ~/air-retirement-2026-04-24/new-cron-cat3.txt) | crontab -
crontab -l | grep -vE '^\s*#|^\s*$|^PATH=' | wc -l
```
Expected: active line count grew by ~6 (7 Cat3 minus 1 duplicate).

- [ ] **Step 5.5: Manual dry-run of one key Cat3 job**

The safest to test immediately is C3.1 (ollama_cron_window.sh start):
```
bash /Users/nuzantara/Desktop/nuzantara/scripts/ollama_cron_window.sh start 2>&1 | head -20
tail -20 /Users/nuzantara/logs/ollama_cron.log 2>&1
```
Expected: script runs without error, log file updated. For C3.5 (ragas_eval.py) run in foreground:
```
cd /Users/nuzantara/Desktop/nuzantara
/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python3 apps/backend-rag/scripts/ragas_eval.py --help 2>&1 | head -20
```
Expected: help/usage printed, no ImportError.

- [ ] **Step 5.6: Commit new-cron-cat3.txt**

```bash
cp ~/air-retirement-2026-04-24/new-cron-cat3.txt /Users/nuzantara/Desktop/nuzantara/reports/air-retirement/
cd /Users/nuzantara/Desktop/nuzantara
git add reports/air-retirement/new-cron-cat3.txt
git commit -m "chore(ops): record Cat3 Ollama cron additions to Pro crontab

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Disable Air crontab (safety net mode)

**Files:**
- Create (on Air): `/Users/antonellosiano/air-crontab-backup-2026-04-24.txt`
- Create (on Air): `/Users/antonellosiano/air-crontab-status.txt`
- Modify (on Air): Air crontab (clear via `crontab -r`)

- [ ] **Step 6.1: Back up Air crontab on Air itself**

Run:
```
ssh air 'crontab -l > ~/air-crontab-backup-2026-04-24.txt && wc -l ~/air-crontab-backup-2026-04-24.txt'
```
Expected: `~/air-crontab-backup-2026-04-24.txt` contains ~50-60 lines (Air's full crontab with comments).

- [ ] **Step 6.2: Also pull copy to Pro for safekeeping**

Run:
```
scp air:/Users/antonellosiano/air-crontab-backup-2026-04-24.txt ~/air-retirement-2026-04-24/air-crontab-backup-2026-04-24.txt
diff ~/air-retirement-2026-04-24/air-crontab-backup-2026-04-24.txt <(ssh air 'crontab -l') | head -5
```
Expected: `diff` returns no output (identical). Store copy in Pro's retirement folder.

- [ ] **Step 6.3: Clear Air crontab**

Run:
```
ssh air 'crontab -r'
ssh air 'crontab -l 2>&1 || echo "(crontab cleared)"'
```
Expected: `(crontab cleared)` or `crontab: no crontab for antonellosiano`.

- [ ] **Step 6.4: Write status marker on Air**

Run:
```
ssh air 'cat > ~/air-crontab-status.txt <<EOF
Disabled 2026-04-24 by Pro migration (Phase 1 Air retirement).
Backup: ~/air-crontab-backup-2026-04-24.txt
To restore: crontab ~/air-crontab-backup-2026-04-24.txt
Plan: $(date -u +%FT%TZ) — Pro observation window 48h. Wipe Air ~2026-04-26/27.
EOF
cat ~/air-crontab-status.txt'
```

- [ ] **Step 6.5: Commit Air crontab backup to Pro repo for audit trail**

```bash
cp ~/air-retirement-2026-04-24/air-crontab-backup-2026-04-24.txt /Users/nuzantara/Desktop/nuzantara/reports/air-retirement/
cd /Users/nuzantara/Desktop/nuzantara
git add reports/air-retirement/air-crontab-backup-2026-04-24.txt
git commit -m "chore(ops): archive Air crontab before deactivation

Safety net: Air is disabled but backup preserved. Rollback command:
ssh air 'crontab ~/air-crontab-backup-2026-04-24.txt'

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Post-migration verification and observation window

**Files:**
- Modify: `~/air-retirement-2026-04-24/migration-log.md`

- [ ] **Step 7.1: Pro crontab sanity check**

Run:
```
crontab -l | grep -vE '^\s*#|^\s*$|^PATH=' | wc -l
crontab -l | grep -E 'PHASE 1'
```
Expected: active line count ~95-100 (was 75 before, plus ~20 Cat2 + ~6 Cat3 additions minus duplicates). Markers `# === AIR RETIREMENT PHASE 1` visible.

- [ ] **Step 7.2: Verify GitHub Actions manual-trigger smoke test succeeded**

Run:
```
gh run list -R Balizero1987/Teman2 --limit 10 --json name,status,conclusion | python3 -c "
import json, sys
runs = json.load(sys.stdin)
for r in runs:
    if r['name'].startswith('cron -'):
        print(r['status'], r['conclusion'], r['name'])
"
```
Expected: 6 rows, all `completed success`.

- [ ] **Step 7.3: Watch for first scheduled trigger in next hour**

Run every 10 min for up to 60 min:
```
date -u
gh run list -R Balizero1987/Teman2 --limit 5 --workflow cron-notifiers-welcome-pending.yml --json createdAt,conclusion | head -20
```
Expected: a new run from schedule (not from manual dispatch) within 15-20 min of enabling.

- [ ] **Step 7.4: Update migration-log.md with outcome**

Record in `~/air-retirement-2026-04-24/migration-log.md`:
```
# Air Retirement Phase 1 — Migration Log

## 2026-04-24 — execution
- Task 0 preflight: <OK / notes>
- Task 1 scripts copied: <count>/<expected>
- Task 2 Pro crontab backed up at ~/air-retirement-2026-04-24/pro-crontab-before-2026-04-24.txt
- Task 3 Cat2 lines added: <count>
- Task 4 GH Actions workflows merged in PR #<N>
- Task 5 Cat3 lines added: <count>
- Task 6 Air crontab cleared at <UTC timestamp>
- Task 7 GH Actions smoke: 6/6 success

## Observation window (ends 2026-04-26 ~evening)
- H+1h: <observation>
- H+6h: <observation>
- H+24h: <observation>
- H+48h: <observation, then wipe decision>

## Rollback triggers
- Any Pro cron logged silent failure for >2 consecutive runs
- Missing expected Telegram message from system_doctor daily digest
- Missing email-health 30-min trigger
Rollback command: ssh air 'crontab ~/air-crontab-backup-2026-04-24.txt'
```

- [ ] **Step 7.5: Set calendar reminder for 48h checkpoint**

Manual step (user action): set a reminder for 2026-04-26 evening WITA to evaluate observation window. If all green, proceed to Air wipe. If any red, roll back and investigate before wiping.

- [ ] **Step 7.6: Final commit of Phase 1 artifacts**

```bash
cd /Users/nuzantara/Desktop/nuzantara
cp ~/air-retirement-2026-04-24/migration-log.md reports/air-retirement/
git add reports/air-retirement/migration-log.md
git commit -m "ops(air-retirement): Phase 1 complete — migration log

Cat1 → GH Actions (6 jobs, Teman2).
Cat2 → Pro crontab (20 jobs, dedup).
Cat3 → Pro crontab (6 jobs, Ollama reuses Pro service).
Air crontab cleared; Air stays powered 48h as safety net.

Next: 48h observation, then Phase 2 (Cat2 → Fly Machines).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-review (done before sharing with executor)

1. **Spec coverage**: Every spec section maps to a task:
   - Step 1.1 (copy scripts) → Task 1
   - Step 1.2 (port Cat2 crontab) → Task 3
   - Step 1.3 (port Cat3 crontab) → Task 5
   - Step 1.4 (Cat1 → GH Actions) → Task 4
   - Step 1.5 (verify Pro crontab) → Task 7
   - Step 1.6 (disable Air crontab) → Task 6
   - Step 1.7 (48h observation) → Task 7 step 7.5
   ✓ All covered.

2. **Placeholder scan**: Searched for "TBD", "TODO", "implement later" → none. All code blocks complete. Path substitution tables are explicit (not "adjust paths appropriately").

3. **Type consistency**: All file paths consistent throughout:
   - Pro repo: `/Users/nuzantara/Desktop/nuzantara/`
   - Pro scripts: `/Users/nuzantara/scripts/`
   - Pro venv: `apps/backend-rag/.venv/`
   - Air paths used only in explicit "Air →" mapping tables
   ✓ No cross-task inconsistencies.

4. **Known limitations documented**:
   - Placeholder `<run-id>` in Step 4.11 (filled at runtime with actual id from `gh run list` output) — not a plan placeholder, a runtime variable, acceptable.
   - Step 5.3 defers collision stagger decision to runtime observation of Pro crontab window — documented explicitly, not hidden TBD.
