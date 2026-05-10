# scripts/mini-migration/ — Mini-Pro2 H24 server migration toolkit

Tools for the Pro→Mini cron migration described in
`docs/superpowers/specs/2026-05-10-mini-h24-server-migration-design.md`.

**Status**: Fase 0 (osservabilità + guardrail). Nessuna migrazione di job
ancora eseguita. Tutto è dry-run by default.

## Files

| Script | Purpose | Side-effect |
|---|---|---|
| `gen-yaml.py` | Regenerate `config/job-ownership.yaml` from current Pro+Mini launchd state. | Writes `config/job-ownership.yaml`. |
| `preflight-job.sh <label>` | Read-only check: greps Pro plist + script body for hidden Pro-bound deps (Postgres@17, Qdrant, ssh-pro paths). Exit 0 = safe, 1 = blocked. | None (read-only). |
| `migrate-job.sh <label> [--apply]` | Execute the deterministic migration procedure (spec §6, 17 steps). DRY-RUN by default; `--apply` actually does it. | When `--apply`: launchctl bootout Pro, bootstrap Mini, edit `job-ownership.yaml`, git commit. |
| `rollback-job.sh <label> [--apply]` | Reverse a migration: re-enable Pro plist, disable Mini. | When `--apply`: launchctl ops + yaml edit. |
| `overlap-detector.sh` | Run on Mini daily to detect labels active on BOTH Pro+Mini. Telegram alert on overlap. | Telegram (cooldown 12h). |
| `idempotent-runner.sh <label> <cmd> [args...]` | Wrapper for non-idempotent jobs (Brevo/social/Canva): claims a per-window key in Redis, skips if already claimed. | Redis SET NX EX. |

## Workflow

### Regenerate inventory (idempotent, safe anytime)
```
ssh pro 'for f in ~/Library/LaunchAgents/*.plist; do
  case "$f" in *.bak*|*.disabled*|*.archived*) continue;; esac
  [ -f "$f" ] || continue
  label=$(basename "$f" .plist)
  active="inactive"
  launchctl list 2>/dev/null | awk -v l="$label" "\$3 == l && \$1 ~ /^[0-9-]+\$/ {print \"hit\"}" | grep -q hit && active="active"
  ral=$(plutil -p "$f" 2>/dev/null | grep RunAtLoad | head -1 | awk -F"=>" "{print \$2}" | tr -d " ,")
  si=$(plutil -p "$f" 2>/dev/null | grep StartInterval | head -1 | awk -F"=>" "{print \$2}" | tr -d " ,")
  echo "$label|$active|$ral|$si"
done' > /tmp/pro-plists.tsv

for f in /Users/nuzantara/Library/LaunchAgents/*.plist; do
  case "$f" in *.bak*|*.disabled*|*.archived*) continue;; esac
  [ -f "$f" ] || continue
  /usr/bin/plutil -p "$f" 2>/dev/null | awk -F'"' '/Label/{print $4; exit}'
done > /tmp/mini-plists.txt

python3 scripts/mini-migration/gen-yaml.py
cp /tmp/job-ownership.yaml config/job-ownership.yaml
```

### Migrate a job (Fase 1+, NOT YET ACTIVATED)
```
# 1. Pre-flight (read-only)
scripts/mini-migration/preflight-job.sh com.balizero.cost-advisor-daily-cap

# 2. Dry-run migrate (no side effect)
scripts/mini-migration/migrate-job.sh com.balizero.cost-advisor-daily-cap

# 3. Real migrate
scripts/mini-migration/migrate-job.sh com.balizero.cost-advisor-daily-cap --apply
```

### Rollback
```
scripts/mini-migration/rollback-job.sh com.balizero.cost-advisor-daily-cap --apply
```

### Overlap detection (cron daily, see com.nuzantara.overlap-detector.daily.plist)
```
scripts/mini-migration/overlap-detector.sh
```

## Hard rules (from spec §1)

1. **Zero duplication**: a job runs on Pro OR Mini, never both.
2. **Mini RAM 24 GB**: max 3 Ollama jobs parallel via `flock`.
3. **No Postgres / Qdrant on Mini**: Pro-bound jobs stay on Pro.
4. **Sync daemons untouched**: memory-sync, claude-config-sync, secrets-sync,
   drive-sync, git-pull-main must stay green.

## Open questions (spec §9, pending Antonello)

1. Redis cross-machine for distributed lock? (`Nuzantara.local:6379` exposed
   on LAN vs each machine isolated)
2. wr2.reflexion/voyager/learner/ig-scraper migrate or stay on Pro?
3. Codex device slots ChatGPT Plus: 2 slots OK or need to logout Pro?
4. translate.hourly: rewrite with qwen3.5:9b or stay on Pro?
5. Timing 6 weeks acceptable?
