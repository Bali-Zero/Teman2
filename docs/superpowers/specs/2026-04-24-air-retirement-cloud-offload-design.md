# Air Retirement + Cloud Offload — Design Spec

**Date:** 2026-04-24
**Author:** Antonello Siano + Claude Opus 4.7
**Status:** Approved, pre-implementation
**Horizon:** Phase 1 today (2026-04-24), Phase 2 over 1-2 weeks after Air handover

## Goal

Free the Air (M4, 16GB) so it can be wiped and gifted to Ari, while simultaneously taking the opportunity to move cloud-eligible automations off the Pro too. End state: Pro runs only what truly needs a macOS session (Claude OAuth CLI jobs, Ollama-dependent jobs); everything else lives in the cloud.

## Constraints and rules

- **Golden Rule #13 (Anthropic ban).** No `ANTHROPIC_API_KEY`, no paid Anthropic SDK, no Bedrock/Vertex-for-Claude credentials anywhere — local, cloud, CI, cron. Only sanctioned path for Claude: `claude` CLI via `CLAUDE_CODE_OAUTH_TOKEN`, which must run on a Max-plan device (the Pro). This rule alone forces Cat3 to stay on-device.
- **Other paid per-token APIs (DeepSeek, etc.) stay allowed** — the ban is Anthropic-specific.
- **Email rule:** outbound email continues via Brevo endpoint on `nuzantara-rag.fly.dev`, `from=zantara@balizero.com`. Migration does not touch email sending path.
- **Time box Phase 1:** must complete today 2026-04-24 so Air can be wiped within 48-72h.
- **Air as safety net:** Air stays powered with crontab disabled but recoverable for 48h after Phase 1 cutover.

## Current state (measured 2026-04-24)

### Air
- 33 active cron entries, ~15 LaunchAgents, services: postgresql@17, redis, ollama, syncthing
- Repo at `/Users/antonellosiano/Projects/nuzantara` (8.8 GB)
- Venv at `apps/backend-rag/venv` (note: `venv`, not `.venv`)
- Scripts unique to Air (NOT yet on Pro):
  - Python: `rag_canary.py`, `system_doctor.py`, `drive_token_watchdog.py`, `ragas_eval.py`, `job_health.py`
  - Bash: `qdrant-snapshot.sh`, `sync-damar.sh`, `sentry-quota-check.sh`, `audit_trail_cleanup.sh`

### Pro
- 75 active cron entries, ~40 LaunchAgents
- Repo at `/Users/nuzantara/Desktop/nuzantara`
- Venv at `apps/backend-rag/.venv`
- ~15 cron entries use `claude` CLI (`cron-agent.sh agent <name>`) — **these must stay**

## Categorization of automations

Three buckets, based on what each job fundamentally requires:

| Cat | Definition | Count (Air) | Count (Pro) | Destination |
|---|---|---|---|---|
| **1** | HTTP scheduler only (curl to Fly backend) | 6 | ~6 | GitHub Actions on `Balizero1987/Teman2` |
| **2** | Python/bash job, no Claude CLI, no Ollama | 19 | ~30 | Phase 1: Pro. Phase 2: Fly Machines (new app `nuzantara-cron`) |
| **3** | Needs Ollama locally, or Claude OAuth CLI | 7 | ~15 | Pro, permanent |

Boundary definitions:
- **Cat1** = the entire script body is `curl -X POST https://*.fly.dev/...`. Zero local dependency.
- **Cat2** = runs Python with repo imports or bash with filesystem access, but does NOT import Ollama API endpoints and does NOT invoke `claude` CLI.
- **Cat3** = either (a) hits `http://localhost:11434` (Ollama), or (b) invokes `claude` CLI or `cron-agent.sh agent ...`.

## Architecture decisions

### D1. Air → Ari, big-bang cutover with 48h safety net
Phase 1 completes today. Air crontab disabled but backup kept (`~/air-crontab-backup.txt`). Air stays powered 48h as parallel verification. If Pro misses any job, we reactivate Air crontab with one command. After 48h of clean Pro operation, wipe Air.

### D2. Cat1 → GitHub Actions on existing `Balizero1987/Teman2`
Repo is already public (diskUsage 1.9 GB, 12 active workflows). Public repo = unlimited GitHub Actions minutes for scheduled workflows. New workflows use filename prefix `cron-*.yml` and `name: "cron - <purpose>"` for easy filtering in the Actions tab. No new repo needed.

### D3. Cat2 → Phase 1 on Pro, Phase 2 on Fly Machines
A serious migration of 40+ Python jobs with secrets, venv bootstrap, and cross-repo deps cannot be done responsibly in one day. Phase 1 consolidates Air's Cat2 onto Pro (pathing/venv fix only). Phase 2 moves Cat2 from Pro to a new Fly app `nuzantara-cron` with machines auto-stopped between runs. Expected Phase 2 cost: ~$1-5/month.

### D4. Cat3 permanent on Pro
Claude OAuth CLI cannot legitimately run in a cloud container (Golden Rule #13 intent: Max subscription is device-bound). Ollama cron jobs (`auto_test`, `auto_sentinel`, `auto_judgement_day`, `ragas_eval`) need bge-m3 / qwen3.5 at `localhost:11434`; hosting Ollama in cloud would cost more than the Max plan they avoid. Pro keeps postgresql@17, redis, ollama, qdrant docker running H24 as it does now.

### D5. Secrets isolation for Fly `nuzantara-cron` (Phase 2)
New Fly app has its own `fly secrets` bag, not shared with `nuzantara-rag`. Reason: least-privilege blast radius. If a cron script is compromised (e.g., via a malicious scraped page), it cannot read `nuzantara-rag` backend secrets.

### D6. Rejected alternatives
- **Hetzner CX22 VPS** rejected: reproduces the "always-on macOS cron host" problem on a different machine; higher baseline cost (€4.90/mo vs ~$2/mo Fly scale-to-zero); additional OS maintenance; latency penalty to Fly Postgres; no Singapore region (bad for Indonesia scrapers).
- **Big-bang to cloud today** rejected: 40 Python jobs with secrets + venvs + cross-repo imports cannot be verified in a day. Honesty requires two phases.
- **Dedicated `Teman2-crons` repo** rejected: `Teman2` is already public; second repo is pure overhead.

## Phase 1 execution plan (today 2026-04-24)

### Step 1.1 — Copy Air-only scripts to Pro
Files to copy from Air to Pro with appropriate path adjustments:

From Air `/Users/antonellosiano/Projects/nuzantara/apps/backend-rag/scripts/` → Pro `/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/scripts/`:
- `rag_canary.py`
- `system_doctor.py`
- `drive_token_watchdog.py`
- `ragas_eval.py`
- `job_health.py`

From Air `/Users/antonellosiano/scripts/` → Pro `/Users/nuzantara/scripts/`:
- `qdrant-snapshot.sh`
- `sync-damar.sh` (if not already a different version on Pro — check for name collision first)
- `sentry-quota-check.sh`
- `audit_trail_cleanup.sh`
- `audit_trail_cleanup.py`

Verification per file: `scp` from Air to Pro, diff against Air to confirm transfer, open each script and rewrite hardcoded `/Users/antonellosiano/` paths to `/Users/nuzantara/Desktop/nuzantara/` and `venv` to `.venv`.

### Step 1.2 — Port Air Cat2 crontab to Pro
For each of the 19 Cat2 Air entries, produce a Pro-equivalent line and append to Pro's crontab. Transformations:
- `/Users/antonellosiano/Projects/nuzantara` → `/Users/nuzantara/Desktop/nuzantara`
- `/Users/antonellosiano/scripts` → `/Users/nuzantara/scripts`
- `.../backend-rag/venv/bin/python3` → `.../backend-rag/.venv/bin/python3`
- `/Users/antonellosiano/logs/...` → `/Users/nuzantara/logs/...`
- `/Users/antonellosiano/Projects/nuzantara/scripts/cron-wrapper.sh` → `/Users/nuzantara/Desktop/nuzantara/scripts/cron-wrapper.sh` (confirm Pro has this script; if not, copy)

### Step 1.3 — Port Air Cat3 crontab to Pro
The 7 Cat3 jobs (ollama_cron_window, auto_test, auto_sentinel, auto_kb_ingest, auto_judgement_day, ollama warm restart, ragas_eval) need Ollama on Pro. Pro already has `homebrew.mxcl.ollama` and the warm-pin script. Verify bge-m3 and qwen3.5 models are pulled on Pro Ollama. Times may need to shift from Air's Ollama window (01:00-06:00 WITA) if Pro already has conflicting nightly work; inspect Pro crontab nightly slot usage.

### Step 1.4 — Cat1 → GitHub Actions workflows on Teman2
For each of the 6 Air Cat1 entries, produce a file `.github/workflows/cron-<purpose>.yml`:

1. `cron-notifiers-all.yml` — daily 00:00 UTC (actually 16:00 UTC-8 = 00:00 WITA)
2. `cron-notifiers-birthday.yml` — daily 00:05 WITA
3. `cron-notifiers-welcome-pending.yml` — every 15 min
4. `cron-practice-auto-create.yml` — daily 07:30 WITA
5. `cron-notifiers-lkpm-deadlines.yml` — daily 23:00 WITA
6. `cron-notifiers-email-health.yml` — every 30 min

Each workflow is a single job, single step:
```yaml
on:
  schedule:
    - cron: '<utc_expression>'  # Convert from WITA (UTC+8)
  workflow_dispatch: {}
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - name: POST to fly backend
        run: |
          curl -fsS -X POST https://nuzantara-rag.fly.dev/<endpoint> \
            -H "X-API-Key: ${{ secrets.NUZANTARA_API_KEY }}"
```

The `X-API-Key` currently hardcoded as `REDACTED-ROTATED-KEY` in Air crontab must move to GitHub repo secret `NUZANTARA_API_KEY`. Verify the secret exists on Teman2, add if missing.

WITA→UTC conversion table for scheduling (WITA is UTC+8):
- 00:00 WITA → 16:00 UTC prev day
- 00:05 WITA → 16:05 UTC prev day
- 07:30 WITA → 23:30 UTC prev day
- 23:00 WITA → 15:00 UTC same day

### Step 1.5 — Verify Pro crontab additions
After appending ~26 new entries (19 Cat2 + 7 Cat3) to Pro:
- `crontab -l | wc -l` should be ~101 (was 75)
- `crontab -l | grep -v '^#' | grep -v '^$' | wc -l` active line count
- Run each newly-added script manually once with `bash -x` to verify path/venv/secrets resolve

### Step 1.6 — Disable Air crontab (safety-net mode)
```
ssh air 'crontab -l > ~/air-crontab-backup-2026-04-24.txt && crontab -r'
ssh air 'echo "Disabled 2026-04-24 by Pro migration" > ~/air-crontab-status.txt'
```
Air keeps PostgreSQL/Redis/Ollama/Syncthing running (services) but no cron jobs fire.

Rollback (if Pro cron fails within 48h):
```
ssh air 'crontab ~/air-crontab-backup-2026-04-24.txt'
```

### Step 1.7 — Observe Phase 1 for 48h
Cross-check Telegram notifications arrive (Brevo email health, system-doctor daily digest, welcome-pending every 15 min). Check `~/logs/` on Pro for new log files from ported jobs. If anything silent for >1 expected interval, investigate before wiping Air.

## Phase 2 execution plan (next 1-2 weeks)

### Step 2.1 — Create `nuzantara-cron` Fly app
```
cd /Users/nuzantara/Desktop/nuzantara/apps/cron  # new directory
fly apps create nuzantara-cron --org <your-org>
```

`fly.toml` with `auto_stop_machines=true`, `auto_start_machines=true`, `min_machines_running=0`, single machine shared-cpu-1x 256MB.

Dockerfile installs Python 3.11, node, git, copies `apps/backend-rag/requirements.txt` for shared deps, plus a minimal runtime for scrapers.

### Step 2.2 — Migrate Pro Cat2 progressively to Fly
Batch 1 (week 1): move the ~15 HTTP-scheduler-like jobs that have simple bodies. Verify 1 week.
Batch 2 (week 2): move the heavier Python scrapers (intel-radar, fact-checker, oss-monitor, imigrasi-monitor, pajak-monitor). Verify 1 week.
Batch 3 (week 3+): NLM data-pipelines if they don't need Ollama; otherwise leave on Pro.

After each batch is verified, disable corresponding Pro crontab lines (don't delete — comment out with `# migrated to nuzantara-cron 2026-XX-XX`).

### Step 2.3 — Secrets
`fly secrets set -a nuzantara-cron SENDGRID_API_KEY=xkeysib-... TELEGRAM_BOT_TOKEN=... DEEPSEEK_API_KEY=... ZANTARA_API_KEY=REDACTED-ROTATED-KEY ...`

Do NOT copy from `nuzantara-rag`; build a minimal set per the actual needs of migrated jobs.

### Step 2.4 — Scheduling model
Fly built-in `schedule` only supports `hourly|daily|weekly|monthly`. For cron with custom minute/hour expressions (`*/15`, `30 */6`, `*/40`), use one of:
- A scheduler machine inside `nuzantara-cron` that runs a tiny Python `schedule` library / APScheduler daemon and spawns child machines via `fly machine run` — BUT this contradicts scale-to-zero.
- Preferred: GitHub Actions scheduled workflow that calls `fly machine run -a nuzantara-cron <cmd>`. Consolidates scheduling on GH.

Decision deferred to Phase 2 start: pick whichever pattern is cleaner per actual job set.

## Testing and verification strategy

- **Phase 1 acceptance:** 48h observation window. Criteria: all Telegram notifications that fired from Air in the preceding 48h also fire from Pro in the next 48h, at approximately the same times. Log files appear in `~/logs/` on Pro for each ported job. No new Sentry alerts traced to migration.
- **Phase 2 acceptance per batch:** one week of parallel dry-run (Pro and Fly both run the job, Fly's output logged only, not acted upon), then cutover Pro→Fly, then one week observation, then Pro line deleted (not just commented).

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Pro crontab exceeds memory/CPU with +26 new jobs | Phase 2 moves the heaviest Cat2 off Pro within 2 weeks; baseline check after Phase 1 step 1.5 |
| Path/venv typo in ported crontab causes silent failures | Step 1.5 requires `bash -x` manual run of each newly-added line before trusting the cron |
| Ollama on Pro already saturated during Air's 01:00-06:00 window | Step 1.3 requires inspecting Pro crontab slot overlap; may need to stagger |
| GH Actions cron drift (±5-15 min not guaranteed) | Accepted — none of the Cat1 jobs are time-critical to the minute |
| Fly Machines cold-start 2-4s | Accepted — no sub-second Cat2 jobs |
| `X-API-Key: REDACTED-ROTATED-KEY` hardcoded in multiple places | Phase 1 only moves it to GH secret for Cat1. Broader rotation separate ticket |
| Air disk `postgresql@17` data matters? | Need to check — if Air's local Postgres holds unique state not replicated to Fly PG, snapshot before wipe |

## Open questions resolved during brainstorming

- Fly vs Hetzner for Cat2 → **Fly**, for network locality + no OS maintenance + scale-to-zero economics
- GH repo for Cat1 → **Teman2**, because public (unlimited minutes)
- Migration strategy → **Two-phase**: Air free today, cloud offload next 1-2 weeks
- Cat3 on Pro vs try DeepSeek-ified migration → **Pro permanent**, conversions deferred to a later effort

## Post-implementation clean-up (after Phase 2 complete)

- Update `~/.claude/CLAUDE.md` Machines table: remove Air, note Pro serves H24 for Claude/Ollama only
- Update `MEMORY.md` project entries referencing Air-specific paths
- Remove `ssh air` aliases / `tunnel-air.sh` / `tunnel-air-stop.sh` from Pro
- Archive `/Users/antonellosiano/Projects/nuzantara` full tarball to Tigris before wiping Air (forensic safety)
