---
date: 2026-05-16 (v4, post 2nd round Codex BLOCK on v3.1 body inconsistencies)
domain: automations / infra-hygiene
status: DRAFT v4 — addresses Codex BLOCK findings on v3.1 body inconsistencies (silent residue, PG count 14→15, Telegram URL no braces, redis-cli no --raw, launchctl list → print gui)
supersedes:
  - 2026-05-16-automation-cleanup-plan-v2.md (BLOCKED 4-LLM panel)
  - 2026-05-16-automation-cleanup-plan-v3.md (BLOCKED Codex K6 silent + 4 KILLER)
  - 2026-05-16-automation-cleanup-plan-v3.1.md (BLOCKED — same body inconsistencies as v3; header patched but body retained `silent` + `14 channels` + `bot$VAR/sendMessage`)
v4_fixes_applied_2026_05_16_04_25:
  - K-v3-2 silent residue cleanup: F1.3 Step 4-5 + Rollback paragraph now consistent with header (NO mode change, only FOR UPDATE lock)
  - K-v3-1 enumeration source: launchctl list → launchctl print gui/$(id -u)
  - K-v3-3 file path: telegram-direct-mapping.txt unified
  - K-v3-4 Telegram URL: ${TELEGRAM_BOT_TOKEN} braces added (3 occurrences)
  - K-v3-5 Redis lag: redis-cli --raw flag added
  - R-v3-1 PG channels recount: 14 → 15 (verified empirical, includes whatsapp_message_received + intel_lake_event)
  - R-v3-2 telegram-direct count: 25 hardcoded → 19-25 with runtime empirical establishment
  - F9.6 commit reference: plan-v3 → plan-v4
v3_review_verdicts:
  - gemini_3.1_pro: REJECT (timebomb sentinel + atrun unreliable)
  - codex_gpt_5.5_spalla: BLOCKER (K6 contradiction, K6 broken file pipeline, F2.3 files missing, .mcp.json.bak leaked secrets, F0.6 no-abort)
  - deepseek_v4_pro_devils_advocate: BLOCK (FederationAlertMode enum mismatch, atrun broken, ln -sf launchd ignores, F3.1 hidden v2 KILLER, psql -tA newline)
v3_1_fixes_applied:
  - K6 enum bug: 'silent' is NOT a valid FederationAlertMode (only observe/dry_deliberate/dry_action/production per models.py:37-43). v3.1 reduces K6 to FOR UPDATE observe-lock with NO mode change.
  - atrun broken (verified empirical 2026-05-16 04:00 — at job queued but never fired on Darwin 25.5). v3.1 uses LaunchAgent runOnce with computed StartCalendarInterval.
  - ln -sf launchd ignores symlinks. v3.1 uses cp + drift check.
  - Materialize 3 F2.3 files (infra/scripts/, infra/launchagents/, apps/backend-rag/tests).
  - psql -tA newline strip + enum validation defense-in-depth.
  - F3.1 inlined from v2 verbatim (no more "identical to v2" omission).
  - F1.2 rotation scope expanded (plist env hardcoded ∪ secrets.env keys ∪ Telegram-direct programs).
  - F9.5 defuses TTL LaunchAgent on success (Gemini timebomb fix).
  - K6 residual bootout manifest refs removed (4 location).
  - File path mismatch fixed: all references use canonical `telegram-direct-mapping.txt` (pair table label|program); F1.3 Step 4 extracts labels via `awk -F'|' '{print $1}'`
  - .mcp.json.bak-2026-05-15-pre-secrets-extraction quarantined to ~/.nuzantara-secrets-quarantine/ (was untracked but with leaked NUZANTARA_API_KEY+LANGSMITH_API_KEY).
parent_research: research/automations/2026-05-16-automation-system-map.md
machine_scope: Pro (nuzantara@Nuzantara) — Mini (UNREACHABLE 2026-05-16 19:00 WITA, fases gated)
estimated_duration: ~6h Pro-only (Mini fases deferred to Mini reconnect)
autonomous_ops_level: L2 active 2026-04-21 (AIL gates marked explicitly)
rollback_strategy: per-intervention dated backup at ~/.automation-cleanup-2026-05-16/
empirical_baseline_2026_05_16_v3_1:
  - pg_channels_total: 15 (verified empirical recount 2026-05-16 04:15 WITA — Codex flagged v3 said 14, recount confirms 15 with whatsapp_message_received present)
  - system_settings_value_type: text (NOT jsonb — verified psql \d 2026-05-16 19:30 WITA)
  - system_settings_key_for_alert_pause: federation_alert_mode (NOT alert_dispatcher_enabled — that key DOES NOT EXIST in DB)
  - federation_alert_mode_current: observe (verified 2026-05-16, last update 2026-04-30 13:11 UTC)
  - federation_alert_mode_enum: [observe, dry_deliberate, dry_action, production] — 'silent' is NOT valid (DeepSeek finding, verified models.py:37-43)
  - wr2_canva_renderer_enabled_current: true (verified 2026-05-16, last update 2026-05-12 21:13 UTC)
  - live_launchagents_total: 138 (Codex empirical 2026-05-16 04:30 via `launchctl print gui/$(id -u) | awk '$NF ~ /^com\.(balizero|nuzantara|cell|matagaruda)\./ {print $NF}'` — v3 said 137 via launchctl list which empirically returns 0)
  - telegram_direct_labels_count: 19 (Codex empirical plist scan 2026-05-16 04:00 — supersedes NB v3 hardcoded 25; v4 F1.2 uses empirical enumeration so exact count is established at runtime)
  - bridge_already_running: PID 2680 (verified launchctl print 2026-05-16)
  - mini_reachable_2026_05_16_evening: UNREACHABLE (ssh ConnectTimeout=3 failed)
  - atrun_disabled_on_darwin_25_5: confirmed empirically (at job queued at 03:53, not fired by 03:54:29 — 29s past deadline)
v3_1_review_gate: 3-LLM panel re-review REQUIRED before Antonello approval (per feedback_always_review_spec_with_4_llm_2026_05_13)
---

# Automation cleanup plan v3 — 2026-05-16

## Cosa cambia vs v2 (verdict-driven)

| v2 finding | v3 fix |
|---|---|
| **K1 PARTIAL**: summary line 27 ancora dice `( crontab -l; echo ... ) \| crontab -` | Rimosso. F3.1 e F4/F5 usano SOLO temp-file + atomic `crontab <file>` o LaunchAgent. Mai `\| crontab -`, mai `crontab -e`. |
| **K6 BROKEN**: target chiave `alert_dispatcher_enabled` non esiste in DB; "4 senders" hardcoded label sbagliati; solo log senza bootout | (a) Target reale: `federation_alert_mode` (verified). (b) CTE snapshot **observe-lock** via `FOR UPDATE` (NO mode change — `'silent'` is NOT a valid FederationAlertMode enum value, only `observe/dry_deliberate/dry_action/production` per models.py:37-43 verified). (c) Enumeration empirica completata: **~19-25 LaunchAgent** (empirical count established at F1.2 runtime — NB v3 hardcoded 25, Codex plist scan 19; v4 trusts runtime enumeration) chiamano Telegram direttamente. (d) **DECISION 2026-05-16 04:00 WITA**: NESSUN bootout, NESSUN mode-change. K6 si riduce a "snapshot mode prior + lock during cleanup + trap restore". Equivalente a un "observe-lock": il daemon resta in modalità OBSERVE (già current, già log-only), ma il piano cattura lo stato per detect tampering da altri tool durante la wave. |
| **K7**: already correct in v2 | Copy verbatim (verified empirically `wr2_canva_renderer_enabled='true'`). |
| **H3 PARTIAL**: validator command senza path argument | Comando verbatim README: `PYTHONPATH=apps/organism python3 -m organism.tools.validate_organs_registry apps/organism/organism/organs_registry.yaml --update-checksum` |
| **H6 BROKEN**: "documented grandfathering" senza Test: citation valido | F2.3 mantiene polling 5min CON Test: citation reale (path file stub creato in TDD mode prima del watchdog deploy). Heartbeat-based watchdog = TODO follow-up PR separato. |
| **H7 BROKEN**: 11 plist non enumerati, no readiness loop, Pro-only | F1.2 esegue enumeration empirica completa pre-F1.1 rotation. Mini count `mini-side-tbd` con reach-gate abort. |
| **H9 BROKEN**: TODO Test: paths violano L4 audit gate | F6.2 DROPPED da v3. Spec separato PR 2026-05-17: prima TDD 6 test files, poi append SYMBIOSIS.md. |
| **F0.6 REGRESSION**: hardcoded 17:00 sentinel | LaunchAgent runOnce with computed `StartCalendarInterval` (T+4h from execution timestamp); `at` / `atrun` historical lesson only — atrun is disabled-by-default on Darwin 25.5 |
| **F6.2 REGRESSION**: append a SYMBIOSIS.md mentre source table ancora dice 13 channels | DROPPED da v3 (vedi H9 above). PR follow-up update source table 13→15 + intel_lake_event + whatsapp_message_received + Test: citations in commit unico. |
| **F2.3 REGRESSION**: watchdog script in `~/scripts/` non git-tracked | Script in `infra/scripts/pg-organism-bridge-watchdog.sh`, plist in `infra/launchagents/com.nuzantara.pg-organism-bridge-watchdog.plist`. F9 commit list cattura entrambi. |
| **Mini UNREACHABLE 2026-05-16 evening** | TUTTI Mini-touching fases (F1.1-mini, F3.2, F3.3, F8.1) hanno reach-gate `ssh -o ConnectTimeout=3 -o BatchMode=yes mini 'echo ok'` → abort with `mini-side-tbd` marker se fail. |

**Empirical baseline updates** (sostituiscono v2 baseline parziale):
- PG channels: **15** (verified empirical 2026-05-16 04:15 WITA — includes `whatsapp_message_received` + `intel_lake_event`)
- system_settings.value type: **text** (NOT jsonb — verified via `\d system_settings` 2026-05-16 19:30 WITA)
- Target chiave pause-alerts: **`federation_alert_mode`** (NOT `alert_dispatcher_enabled` — quella key non esiste)
- Live LaunchAgents: **138** filtered to com.{balizero,nuzantara,cell,matagaruda}.* (verified `launchctl print gui/$(id -u) | awk '$NF ~ /^com\.(...)\./'` — `launchctl list` empirically returns 0 lines)
- Telegram-direct senders: TBD (vedi F1.2 enumeration output)

---

## FASE 0 — Pre-flight con safety net REALE

```bash
DATED_BACKUP=~/.automation-cleanup-2026-05-16
mkdir -p $DATED_BACKUP/{backup,exposed-secrets,logs,state}

# 0.1 Snapshot integral con tar
cd ~/Library
tar --no-ignore-case --uname --gname \
    -czpf $DATED_BACKUP/backup/launchagents-pro-2026-05-16.tgz \
    LaunchAgents/com.nuzantara.*.plist \
    LaunchAgents/com.balizero.*.plist \
    LaunchAgents/com.cell.*.plist \
    LaunchAgents/com.matagaruda.*.plist 2>/dev/null
ls -la $DATED_BACKUP/backup/launchagents-pro-2026-05-16.tgz

# 0.1-Mini reach gate
if ssh -o ConnectTimeout=3 -o BatchMode=yes mini 'echo ok' 2>/dev/null; then
  ssh mini 'cd ~/Library && tar -czpf - LaunchAgents/com.*.plist 2>/dev/null' \
    > $DATED_BACKUP/backup/launchagents-mini-2026-05-16.tgz
  echo "MINI_REACHABLE=true" > $DATED_BACKUP/state/mini-reach.env
else
  echo "MINI_REACHABLE=false" > $DATED_BACKUP/state/mini-reach.env
  echo "$(date) Mini UNREACHABLE — Mini-touching fases will abort with mini-side-tbd marker" \
    | tee -a $DATED_BACKUP/logs/recovery.log
fi
source $DATED_BACKUP/state/mini-reach.env

# 0.2 Snapshot crontab
crontab -l > $DATED_BACKUP/backup/crontab-pro-2026-05-16.txt
if [ "$MINI_REACHABLE" = "true" ]; then
  ssh mini 'crontab -l' > $DATED_BACKUP/backup/crontab-mini-2026-05-16.txt
fi

# 0.3 Snapshot system_settings DB (FULL)
source ~/.nuzantara-secrets.env
psql "$DATABASE_URL_LOCAL" -tA -c "SELECT key, value FROM system_settings ORDER BY key" \
  > $DATED_BACKUP/backup/system_settings-2026-05-16.tsv

# 0.4 Snapshot federation_alert_mode prior value (REAL key, NOT alert_dispatcher_enabled)
# CRITICAL: strip trailing newline from psql -tA output, enum validation rejects 'observe\n'
PRIOR_FAM=$(psql "$DATABASE_URL_LOCAL" -tA -c "
  WITH prior AS (SELECT value FROM system_settings WHERE key='federation_alert_mode' FOR SHARE)
  SELECT value FROM prior
" | tr -d '[:space:]')

# Defense-in-depth: assert FederationAlertMode enum (per models.py:37-43)
case "$PRIOR_FAM" in
  observe|dry_deliberate|dry_action|production) ;;
  *) echo "FATAL: federation_alert_mode='$PRIOR_FAM' is not a valid FederationAlertMode enum value" >&2; exit 1 ;;
esac

echo "$PRIOR_FAM" > $DATED_BACKUP/state/federation_alert_mode.prior
echo "federation_alert_mode prior value: $PRIOR_FAM (enum validated)"
# expect: observe (verified 2026-05-16)

# 0.5 — empirical 2026-05-16 03:54 WITA: macOS Darwin 25.5 atrun DISABLED-by-default
# Test job: `echo X | at now + 1 minute` accettato, file in /var/at/jobs/ creato,
# MA NON FIRED 29s post-deadline (queue still pending). atrun service not loaded.
# Workaround attivazione: `sudo launchctl load -w /System/Library/LaunchDaemons/com.apple.atrun.plist`
# (richiede sudo + SIP/Full-Disk-Access — AIL e non-portable).
# DECISIONE v3.1: usiamo LaunchAgent runOnce con StartCalendarInterval computato.

# 0.6 TTL sentinel via LaunchAgent runOnce (computed timestamp = now + 4h)
DEADLINE_EPOCH=$(($(date +%s) + 14400))  # +4 hours
DEADLINE_YEAR=$(date -j -f "%s" "$DEADLINE_EPOCH" "+%Y")
DEADLINE_MONTH=$(date -j -f "%s" "$DEADLINE_EPOCH" "+%-m")
DEADLINE_DAY=$(date -j -f "%s" "$DEADLINE_EPOCH" "+%-d")
DEADLINE_HOUR=$(date -j -f "%s" "$DEADLINE_EPOCH" "+%-H")
DEADLINE_MIN=$(date -j -f "%s" "$DEADLINE_EPOCH" "+%-M")

cat > $DATED_BACKUP/state/restore-federation-alert-mode.sh <<EOF
#!/bin/bash
# Auto-restore script invoked by LaunchAgent runOnce at $DEADLINE_HOUR:$DEADLINE_MIN
set -e
source ~/.nuzantara-secrets.env
psql "\$DATABASE_URL_LOCAL" -c "
  UPDATE system_settings SET value='$PRIOR_FAM', updated_at=NOW()
  WHERE key='federation_alert_mode'
"
echo "\$(date) Auto-restore completed: federation_alert_mode='$PRIOR_FAM'" \
  >> ~/.automation-cleanup-2026-05-16/logs/recovery.log
# Self-teardown: bootout this LaunchAgent and rm the plist (it has served its purpose)
launchctl bootout gui/\$(id -u)/com.nuzantara.cleanup-2026-05-16-ttl-sentinel 2>/dev/null || true
rm -f ~/Library/LaunchAgents/com.nuzantara.cleanup-2026-05-16-ttl-sentinel.plist
EOF
chmod +x $DATED_BACKUP/state/restore-federation-alert-mode.sh

cat > ~/Library/LaunchAgents/com.nuzantara.cleanup-2026-05-16-ttl-sentinel.plist <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.nuzantara.cleanup-2026-05-16-ttl-sentinel</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>$DATED_BACKUP/state/restore-federation-alert-mode.sh</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Year</key><integer>$DEADLINE_YEAR</integer>
    <key>Month</key><integer>$DEADLINE_MONTH</integer>
    <key>Day</key><integer>$DEADLINE_DAY</integer>
    <key>Hour</key><integer>$DEADLINE_HOUR</integer>
    <key>Minute</key><integer>$DEADLINE_MIN</integer>
  </dict>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>$DATED_BACKUP/logs/ttl-sentinel.out</string>
  <key>StandardErrorPath</key><string>$DATED_BACKUP/logs/ttl-sentinel.err</string>
</dict>
</plist>
PLIST
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.nuzantara.cleanup-2026-05-16-ttl-sentinel.plist
echo "TTL sentinel scheduled for $DEADLINE_YEAR-$DEADLINE_MONTH-$DEADLINE_DAY $DEADLINE_HOUR:$DEADLINE_MIN" \
  | tee $DATED_BACKUP/state/ttl-sentinel-schedule.txt

# Verify
launchctl print gui/$(id -u)/com.nuzantara.cleanup-2026-05-16-ttl-sentinel 2>&1 | grep -E "state|next run" | head -3

# 0.7 Trap on EXIT: handled in F1.3 (observe-lock re-assertion).
# NO disable + bootout — K6 v3.1 keeps 25 Telegram-direct watchdogs alive (decision 2026-05-16 04:00).

# 0.8 Git baseline
cd ~/Desktop/nuzantara
git status --porcelain | head -20
git rev-parse HEAD > $DATED_BACKUP/state/git-baseline-sha.txt
```

**Rollback safety net**:
1. **Trap on EXIT** (F1.3 Step 3): re-asserts prior `federation_alert_mode` value if changed during cleanup. NO bootout to rollback (none performed).
2. **TTL sentinel** (LaunchAgent runOnce at +4h, NOT `at` since `atrun` disabled-by-default on macOS Darwin 25.5): independent dalla shell session, defused in F9.5 on successful completion.

---

## FASE 1 — P0 Sicurezza (90 min)

### F1.1 — Bitmask audit Pro + Mini (gated)

```bash
audit_plist_mode() {
  local f=$1 host=$2
  local raw_mode=$(stat -f "%p" "$f" 2>/dev/null)
  local mode=${raw_mode: -3}
  local group_or_other_readable=$(( (0$mode & 044) != 0 ))
  if [ $group_or_other_readable -eq 1 ]; then
    if plutil -convert xml1 -o - "$f" 2>/dev/null | grep -qE "(TOKEN|SECRET|API_KEY|PASSWORD|CREDENTIAL)"; then
      echo "$host EXPOSED: $f (mode $mode)"
    fi
  fi
}

# Pro audit (always runs)
for f in ~/Library/LaunchAgents/com.*.plist; do audit_plist_mode "$f" "PRO"; done \
  > $DATED_BACKUP/exposed-secrets/pro-bitmask-audit.txt
echo "Pro exposed: $(wc -l < $DATED_BACKUP/exposed-secrets/pro-bitmask-audit.txt)"

# Mini audit (reach-gated)
if [ "$MINI_REACHABLE" = "true" ]; then
  ssh mini "$(typeset -f audit_plist_mode); for f in ~/Library/LaunchAgents/com.*.plist; do audit_plist_mode \"\$f\" \"MINI\"; done" \
    > $DATED_BACKUP/exposed-secrets/mini-bitmask-audit.txt
  echo "Mini exposed: $(wc -l < $DATED_BACKUP/exposed-secrets/mini-bitmask-audit.txt)"
else
  echo "MINI_UNREACHABLE: empirical count = mini-side-tbd" > $DATED_BACKUP/exposed-secrets/mini-bitmask-audit.txt
fi
```

**Rollback**: read-only audit, no rollback needed.

### F1.2 — Enumerate Telegram-direct senders (empirical, NOT hardcoded)

```bash
# Enumerate ALL program paths referenced by live LaunchAgents
# Codex empirical 2026-05-16: `launchctl print gui/N` row format is "pid status label" (NOT 'com.*' at start of line)
# Correct parser: match $NF (last field) instead of line prefix
LABELS=$(launchctl print gui/$(id -u) 2>/dev/null \
         | awk '$NF ~ /^com\.(balizero|nuzantara|cell|matagaruda)\./ {print $NF}' \
         | sort -u)
LABELS_COUNT=$(echo "$LABELS" | grep -c .)
echo "Enumerated $LABELS_COUNT live LaunchAgent labels"
[ "$LABELS_COUNT" -gt 0 ] || { echo "FATAL: enumeration returned 0 — abort F1.2"; exit 1; }

PROGRAMS=$DATED_BACKUP/state/all-program-paths.txt
> $PROGRAMS
for label in $LABELS; do
  timeout 2 launchctl print "gui/$(id -u)/$label" 2>/dev/null \
    | grep -oE '/Users/[^"[:space:]]+\.(sh|py)' \
    | sort -u
done | sort -u > $PROGRAMS
echo "Unique program paths: $(wc -l < $PROGRAMS)"

# Filter for Telegram-direct API callers (canonical filename: telegram-direct-mapping.txt — pair table label|program)
TELEGRAM_DIRECT=$DATED_BACKUP/state/telegram-direct-mapping.txt
> $TELEGRAM_DIRECT
while IFS= read -r prog; do
  [ -f "$prog" ] || continue
  if grep -qE '(api\.telegram\.org|telegram_bot.*sendMessage)' "$prog" 2>/dev/null; then
    # Map back to owning labels
    OWNERS=$(grep -lE "$(echo $prog | sed 's/\//\\\//g')" ~/Library/LaunchAgents/*.plist 2>/dev/null | xargs -I{} basename {} .plist)
    for owner in $OWNERS; do
      echo "$owner|$prog" >> $TELEGRAM_DIRECT
    done
  fi
done < $PROGRAMS

echo "Telegram-direct (label|program) pairs: $(wc -l < $TELEGRAM_DIRECT)"
cat $TELEGRAM_DIRECT

# Step 2 — Rotation scope = Telegram-direct programs ∪ plist env hardcoded ∪ secrets.env refs
# (per H7 v2 finding: rotation prep needs to cover ALL surfaces, not just .sh/.py with API calls)
ROTATION_SCOPE=$DATED_BACKUP/state/rotation-scope.txt
> $ROTATION_SCOPE

# (a) Plist files with env-hardcoded TELEGRAM_BOT_TOKEN (NOT source-pattern)
echo "=== Plist files with hardcoded TELEGRAM_BOT_TOKEN env (must be migrated to source pattern) ===" \
  | tee -a $ROTATION_SCOPE
for plist in ~/Library/LaunchAgents/com.*.plist; do
  if plutil -convert xml1 -o - "$plist" 2>/dev/null | grep -qE '<key>TELEGRAM_BOT_TOKEN</key>'; then
    if ! plutil -convert xml1 -o - "$plist" 2>/dev/null | grep -q 'nuzantara-secrets.env'; then
      echo "PLIST_HARDCODED: $plist" | tee -a $ROTATION_SCOPE
    fi
  fi
done

# (b) ~/.nuzantara-secrets.env keys touched by rotation
echo "" | tee -a $ROTATION_SCOPE
echo "=== Secrets to rotate in ~/.nuzantara-secrets.env ===" | tee -a $ROTATION_SCOPE
for key in TELEGRAM_BOT_TOKEN TELEGRAM_OWNER_CHAT_ID CLAUDE_CODE_OAUTH_TOKEN_SLOT1 CLAUDE_CODE_OAUTH_TOKEN_SLOT2 CLAUDE_CODE_OAUTH_TOKEN; do
  if grep -q "^$key=" ~/.nuzantara-secrets.env 2>/dev/null; then
    echo "ENV_KEY: $key" | tee -a $ROTATION_SCOPE
  fi
done

# (c) Telegram-direct programs that bypass source pattern (hardcoded fallback chat_id, etc.)
echo "" | tee -a $ROTATION_SCOPE
echo "=== Telegram-direct programs (.sh/.py with api.telegram.org call) ===" | tee -a $ROTATION_SCOPE
cat $TELEGRAM_DIRECT | tee -a $ROTATION_SCOPE

echo "Rotation scope saved to $ROTATION_SCOPE"
wc -l $ROTATION_SCOPE
```

**Output goes to**: F1.3 + F1.4 token rotation AIL gate.

### F1.3 — K6 federation_alert_mode observe-lock (CTE snapshot, NO bootout, NO mode change)

**Empirical evidence 2026-05-16 04:00 WITA**: 19-25 LaunchAgent chiamano Telegram direttamente (v4 F1.2 establishes exact count at runtime via `launchctl print gui/$(id -u)` enumeration + plist scan). **Canonical pair table**: `$DATED_BACKUP/state/telegram-direct-mapping.txt` (lines in format `label|program`). Lista include watchdog critici operativi: `cpu-monitor`, `disk-monitor`, `login-healthcheck`, `fly-restart-loop-detector`, `openclaw-children-watchdog`, `sentinel-meta-watchdog`, `supervisor-liveness-watchdog`, `nb-intel-delta-watcher`, `automap-watchdog`, etc.

**Decision finale**: NESSUN bootout, NESSUN mode change. `FederationAlertMode` enum (verified `models.py:37-43`) accetta solo `observe/dry_deliberate/dry_action/production`. Il valore `'silent'` originalmente proposto **non esiste** — daemon writes raw via `set_db_mode()` lo rifiuterebbero, e raw psql writes lo accetterebbero ma `_dispatch_proposal()` non avrebbe branch matching → proposal stuck in `received`. Inoltre il valore current è **già `observe`** (log-only, safer-tier), che è esattamente ciò che il cleanup vuole. F1.3 si riduce quindi a:
- snapshot di prior mode (already done in F0.4)
- trap EXIT che ri-asserisce 'observe' se altri tool tentano un mode change durante la wave
- documentation dei 25 direct-senders per operator awareness

```bash
# Step 1 — Take advisory FOR UPDATE lock on federation_alert_mode row
# This serializes any other writer (e.g. accidental Antonello use of mode-change UI)
# until our transaction commits, then releases. NOT a value change.
psql "$DATABASE_URL_LOCAL" <<'SQL'
  BEGIN;
  SELECT value FROM system_settings WHERE key='federation_alert_mode' FOR UPDATE;
  -- intentionally NO UPDATE — we just want to verify lock acquires + value is enum-valid
  COMMIT;
SQL

# Step 2 — Verify prior value matches what F0.4 captured (paranoia check for race)
CURRENT_FAM=$(psql "$DATABASE_URL_LOCAL" -tA -c \
  "SELECT value FROM system_settings WHERE key='federation_alert_mode'" | tr -d '[:space:]')
if [ "$CURRENT_FAM" != "$PRIOR_FAM" ]; then
  echo "FATAL: federation_alert_mode changed between F0.4 ($PRIOR_FAM) and F1.3 ($CURRENT_FAM)" >&2
  echo "Someone else modified it. ABORT cleanup." >&2
  exit 1
fi
echo "federation_alert_mode locked at '$PRIOR_FAM' (no change, enum-valid)"

# Step 3 — Trap on EXIT: re-assert prior value if someone changed it during cleanup
trap "psql \"\$DATABASE_URL_LOCAL\" -c \"UPDATE system_settings SET value='$PRIOR_FAM', updated_at=NOW() WHERE key='federation_alert_mode' AND value != '$PRIOR_FAM'\"" EXIT

# Step 4 — Document Telegram-direct senders for operational awareness (NO bootout)
echo "=== Telegram-direct LaunchAgent labels (preserved during cleanup) ==="
awk -F'|' '{print $1}' $DATED_BACKUP/state/telegram-direct-mapping.txt | sort -u
echo ""
echo "These watchdog will continue alerting Antonello on REAL outages during cleanup."
echo "federation_alert_mode unchanged ('$PRIOR_FAM'); federation router still in current behavior."

# Step 4 — Verify (NO mode change — confirm `federation_alert_mode` still equals prior `$PRIOR_FAM`)
psql "$DATABASE_URL_LOCAL" -tA -c "SELECT value FROM system_settings WHERE key='federation_alert_mode'"
# expect: $PRIOR_FAM (e.g. 'observe')

# Step 5 — Sanity: federation_alert_daemon already respects current `observe` mode (log-only).
# The daemon module is a thin launcher (~51 lines) that instantiates FederationAlertDaemon.
# The actual mode logic lives in repository.py — verified empirically 2026-05-16
grep -n "federation_alert_mode\|get_db_mode" ~/Desktop/nuzantara/apps/backend-rag/backend/services/federation_alerts/repository.py 2>/dev/null | head -5
# expect: lines 466 (get_db_mode), 469 (key='federation_alert_mode'), 481-499 (set_db_mode)
```

**Rollback**: NO rollback needed (we did NOT change `federation_alert_mode` value — only acquired FOR UPDATE row lock during cleanup window; lock released on transaction commit at F1.3 Step 1 end).

**Why this differs from v2 verdict**:
- v2 verdict claimed "4 Telegram-direct senders" — empirically there are **19** (Codex empirical plist scan, NOT 25 as v3 hardcoded)
- Killing all 19 = killing operational watchdog → blind cleanup window
- The single label cited as still-running by v2 verdict (`com.nuzantara.federation-alert-dispatcher`) is the federation router's daemon. With `federation_alert_mode='observe'` (current, unchanged), it's already in log-only mode. `'silent'` is NOT a valid enum value (verified `FederationAlertMode` enum in `models.py:37-43`: only `observe/dry_deliberate/dry_action/production`).

### F1.4 — Token rotation (AIL gate)

> **🔒 Antonello action required**.
>
> Prerequisito: `$DATED_BACKUP/exposed-secrets/pro-bitmask-audit.txt` mostra plist mode +044 con secrets esposti. Sequence:
>
> 1. `chmod u+w` su tutti i plist con secrets esposti (write window)
> 2. Rotate `TELEGRAM_BOT_TOKEN` via @BotFather `/revoke` + new token
> 3. `CLAUDE_CODE_OAUTH_TOKEN_*` (3): `claude /login` slot 1 + slot 2 + agent (browser OAuth flow)
> 4. Update `~/.nuzantara-secrets.env` con nuovi valori (Pro + Mini sync ONLY se MINI_REACHABLE)
> 5. Per ogni plist hardcoded: rimuovi env vars dal plist, add `source ~/.nuzantara-secrets.env` pattern (cf `infra/launchagents/com.nuzantara.pg-organism-bridge.plist:18`)
> 6. `chmod 0400` su tutti i plist sensibili
> 7. `launchctl bootout && launchctl bootstrap` per ognuno
>
> Plan **non procede F2+** finché F1.4 chiuso (Antonello segnala via `touch ~/.automation-cleanup-2026-05-16/state/F1.4-rotation-complete`).

**Post-rotation verify**:
```bash
# Test: no plist mode +044 con secrets dopo F1.4
find ~/Library/LaunchAgents -name "com.*.plist" -exec sh -c '
  raw=$(stat -f "%p" "$1"); mode=${raw: -3};
  if (( (0$mode & 044) != 0 )); then
    plutil -convert xml1 -o - "$1" 2>/dev/null | grep -qE "(TOKEN|SECRET|API_KEY|PASSWORD)" && echo "STILL EXPOSED: $1"
  fi
' _ {} \;
# expect 0 lines

# Smoke: new Telegram token alerts work
source ~/.nuzantara-secrets.env
curl -sS "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d "chat_id=1125336968&text=F1.4 rotation OK — automation-cleanup-2026-05-16-v3"
```

---

## FASE 2 — P0 Disponibilità (60 min)

### F2.1 — Unload `wr2.canva-renderer` con snapshot DB value (verbatim da v2)

(Verified empirically: `wr2_canva_renderer_enabled='true'` confirmed via psql 2026-05-16 19:30 WITA. v2 fix correct.)

```bash
# Step 1 — Snapshot prior DB value (CTE for consistency with K6 pattern)
PRIOR_RENDERER=$(psql "$DATABASE_URL_LOCAL" -tA -c "
  WITH prior AS (SELECT value FROM system_settings WHERE key='wr2_canva_renderer_enabled' FOR SHARE)
  SELECT value FROM prior
")
echo "$PRIOR_RENDERER" > $DATED_BACKUP/state/wr2_canva_renderer_enabled.prior
echo "Prior renderer value: $PRIOR_RENDERER"

# Step 2 — Kill switch + unload
psql "$DATABASE_URL_LOCAL" -c "
  UPDATE system_settings SET value='false', updated_at=NOW()
  WHERE key='wr2_canva_renderer_enabled'
"
launchctl bootout gui/$(id -u)/com.balizero.wr2.canva-renderer 2>/dev/null || true
mkdir -p ~/Library/LaunchAgents/.disabled-2026-05-16-cleanup/
mv ~/Library/LaunchAgents/com.balizero.wr2.canva-renderer.plist \
   ~/Library/LaunchAgents/.disabled-2026-05-16-cleanup/

# Cleanup stale renderer-off plist se duplicato
rm -i ~/Library/LaunchAgents/.disabled-2026-05-16-renderer-off/com.balizero.wr2.canva-renderer.plist 2>/dev/null || true
```

**Verify**:
```bash
launchctl print gui/$(id -u) 2>/dev/null | grep wr2.canva-renderer  # expect empty (launchctl list returns 0 lines on this Mac)
psql "$DATABASE_URL_LOCAL" -tA -c "SELECT value FROM system_settings WHERE key='wr2_canva_renderer_enabled'"
# expect 'false'
```

**Rollback** (usa snapshot, NOT hardcoded):
```bash
mv ~/Library/LaunchAgents/.disabled-2026-05-16-cleanup/com.balizero.wr2.canva-renderer.plist \
   ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.wr2.canva-renderer.plist
psql "$DATABASE_URL_LOCAL" -c "
  UPDATE system_settings SET value='$(cat $DATED_BACKUP/state/wr2_canva_renderer_enabled.prior)', updated_at=NOW()
  WHERE key='wr2_canva_renderer_enabled'
"
```

### F2.2 — Diagnose `cell.organism` exit=1 (READ-ONLY)

Identical to v2 — read-only investigation, fix in PR separato post-cleanup.

### F2.3 — pg-organism-bridge-watchdog in `infra/scripts/` + `infra/launchagents/` (NOT `~/scripts/`)

**Fix F2.3 regression**: script+plist must be git-tracked under `infra/`.

```bash
# Step 1 — Create script in canonical git path
cd ~/Desktop/nuzantara
mkdir -p infra/scripts infra/launchagents

cat > infra/scripts/pg-organism-bridge-watchdog.sh <<'EOF'
#!/bin/bash
# pg-organism-bridge-watchdog.sh — verifica che il bridge (NON questo script) sia vivo + Redis stream attivo
# Pattern secrets: source ~/.nuzantara-secrets.env (NON launchctl setenv)
# Pattern fail-safe: `|| true` su pgrep (no-match exits 1 ma vogliamo continuare)
# Symbiosis L3 grandfathering: polling 5min sul bridge state (heartbeat-based watchdog = follow-up PR)
# Test: apps/backend-rag/backend/tests/services/events/test_bridge_heartbeat_polling_grandfathered.py

set -uo pipefail  # NO -e: pgrep no-match exits 1
LOG=~/logs/pg-organism-bridge-watchdog.log
STATE=~/.agent/decisions/state/pg_organism_bridge_watchdog.state
mkdir -p $(dirname $LOG) $(dirname $STATE)

set -a
[ -f "$HOME/.nuzantara-secrets.env" ] && source "$HOME/.nuzantara-secrets.env"
set +a

# Step A: bridge process alive
PID=$(pgrep -f "pg-to-organism-bridge.py" | head -1 || true)
if [ -z "$PID" ]; then
  echo "$(date) ALERT: pg-organism-bridge NOT RUNNING — Symbiosis SPOF" >> "$LOG"
  curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d "chat_id=${TELEGRAM_OWNER_CHAT_ID:-1125336968}" \
    -d "text=⚠️ pg-organism-bridge DOWN ($(date +%H:%M)) — Symbiosis SPOF" >> "$LOG" 2>&1
  exit 0
fi

# Step B: bridge alive — Redis stream lag check (last event in 30min)
REDIS_HOST="${GARUDA_REDIS_HOST:-127.0.0.1}"
LAST_ID=$(redis-cli --raw -h "$REDIS_HOST" XREVRANGE organism:events + - COUNT 1 2>/dev/null | head -1 || echo "")

if [ -z "$LAST_ID" ]; then
  echo "$(date) WARN: no events in organism:events stream (PID=$PID alive, stream empty)" >> "$LOG"
  exit 0
fi

STREAM_MS=${LAST_ID%%-*}
NOW_MS=$(($(date +%s) * 1000))
LAG_MS=$((NOW_MS - STREAM_MS))
LAG_MIN=$((LAG_MS / 60000))

if [ $LAG_MIN -gt 30 ]; then
  echo "$(date) ALERT: bridge alive (PID=$PID) but stream lag ${LAG_MIN}min > 30min threshold" >> "$LOG"
  curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d "chat_id=${TELEGRAM_OWNER_CHAT_ID:-1125336968}" \
    -d "text=⚠️ pg-organism-bridge alive but stream STALE (${LAG_MIN}min, threshold 30min)" >> "$LOG" 2>&1
else
  echo "$(date) OK: PID=$PID last_event_lag=${LAG_MIN}min" >> "$LOG"
fi

exit 0
EOF
chmod +x infra/scripts/pg-organism-bridge-watchdog.sh

# Step 2 — Plist in canonical git path
cat > infra/launchagents/com.nuzantara.pg-organism-bridge-watchdog.plist <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.nuzantara.pg-organism-bridge-watchdog</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>/Users/nuzantara/Desktop/nuzantara/infra/scripts/pg-organism-bridge-watchdog.sh</string>
  </array>
  <key>StartInterval</key><integer>300</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>/Users/nuzantara/logs/pg-organism-bridge-watchdog.out</string>
  <key>StandardErrorPath</key><string>/Users/nuzantara/logs/pg-organism-bridge-watchdog.err</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    <key>HOME</key><string>/Users/nuzantara</string>
  </dict>
</dict>
</plist>
PLIST

# Step 3 — Create Test: stub file (TDD: file exists before watchdog deploy per L4 gate)
mkdir -p apps/backend-rag/backend/tests/services/events
cat > apps/backend-rag/backend/tests/services/events/test_bridge_heartbeat_polling_grandfathered.py <<'PY'
"""Grandfathered polling-based watchdog test stub for pg-organism-bridge.

Documents the L3 grandfathered exception: the watchdog uses 5min polling
instead of durable XADD heartbeat consumer. Heartbeat-based watchdog is
follow-up PR (gated on bridge restart). Until then, polling watchdog is
in production AND lint_symbiosis_promises.py needs this file to exist.

TODO follow-up PR: replace polling with XREAD BLOCK consumer of
`organism:heartbeat` stream (60s XADD producer in pg-to-organism-bridge.py).
"""
import pytest


@pytest.mark.skip(reason="TDD stub for L4 audit gate — implementation in follow-up PR")
def test_watchdog_alerts_when_bridge_pid_missing():
    """Polling watchdog detects missing bridge PID and alerts via Telegram."""
    # GIVEN no pg-to-organism-bridge.py process
    # WHEN watchdog runs (StartInterval=300)
    # THEN Telegram alert fired + log entry
    pass


@pytest.mark.skip(reason="TDD stub for L4 audit gate")
def test_watchdog_alerts_when_redis_stream_lag_exceeds_30min():
    """Polling watchdog alerts when organism:events stream stale > 30min."""
    pass
PY

# Step 4 — Symbiosis lint check (gate: file must exist before deploy)
python ~/Desktop/nuzantara/scripts/lint_symbiosis_promises.py 2>&1 | \
  grep -E "(pg-organism-bridge-watchdog|polling)" | head -3

# Step 5 — Copy plist to ~/Library/LaunchAgents/ (NOT symlink — launchd ignora ln -sf, finding DeepSeek)
# Tradeoff: if plist edited in git later, must re-cp. Compensation: VERIFY_DRIFT script in F9 checks divergence.
cp $(pwd)/infra/launchagents/com.nuzantara.pg-organism-bridge-watchdog.plist \
   ~/Library/LaunchAgents/com.nuzantara.pg-organism-bridge-watchdog.plist
chmod 0444 ~/Library/LaunchAgents/com.nuzantara.pg-organism-bridge-watchdog.plist  # plist itself no secrets
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.nuzantara.pg-organism-bridge-watchdog.plist
launchctl kickstart gui/$(id -u)/com.nuzantara.pg-organism-bridge-watchdog

# Step 5b — F9 will verify: sha256(infra/launchagents/...plist) == sha256(~/Library/LaunchAgents/...plist)
# to catch drift between git source-of-truth and installed plist.

# Step 6 — Verify 5min later
sleep 320 && tail -5 ~/logs/pg-organism-bridge-watchdog.log
```

**Test: citation**: `apps/backend-rag/backend/tests/services/events/test_bridge_heartbeat_polling_grandfathered.py` (created Step 3, stub @pytest.skip — gate for L4 audit-trail lint)

**Rollback**:
```bash
launchctl bootout gui/$(id -u)/com.nuzantara.pg-organism-bridge-watchdog
rm ~/Library/LaunchAgents/com.nuzantara.pg-organism-bridge-watchdog.plist
cd ~/Desktop/nuzantara && git checkout HEAD -- infra/scripts/pg-organism-bridge-watchdog.sh \
                                                 infra/launchagents/com.nuzantara.pg-organism-bridge-watchdog.plist \
                                                 apps/backend-rag/backend/tests/services/events/test_bridge_heartbeat_polling_grandfathered.py
```

---

## FASE 3 — P1 Cluster pg-proxy + Mini fixes (gated)

### F3.1 — Cluster pg-proxy 24h monitoring (LaunchAgent one-shot, NO `crontab -` pipe ever)

**Trauma v1 KILLER K1**: `echo ... | crontab -` cancella crontab.

**v3.1 fix (verbatim from v2, inlined per Codex self-containment finding)**: usa LaunchAgent one-shot con `StartCalendarInterval`, NON crontab pipe.

```bash
# Snapshot exit codes attuali
for label in com.balizero.wr2.supervisor com.balizero.wr2.supervisor-watchdog com.balizero.wr2.daily-metrics com.balizero.wr2.topic-selector com.balizero.wr2.connector com.balizero.wr2.dossier-compiler com.balizero.wr2.learner-nightly com.balizero.wr2.fact-extractor com.balizero.sota.m13-checkpoint com.nuzantara.federation-alert-dispatcher com.nuzantara.cell-observatory com.nuzantara.pg-organism-bridge; do
  exit_code=$(launchctl print gui/$(id -u)/$label 2>/dev/null | grep -E "^\s+last exit" | head -1)
  echo "$label: $exit_code"
done | tee $DATED_BACKUP/state/pg-proxy-cluster-baseline.txt
```

**24h re-check via one-shot LaunchAgent (NON crontab)**:
```bash
# Compute recheck deadline = now + 24h (avoid hardcoded 2026-05-17 13:00)
RECHECK_EPOCH=$(($(date +%s) + 86400))
R_YEAR=$(date -j -f "%s" "$RECHECK_EPOCH" "+%Y")
R_MONTH=$(date -j -f "%s" "$RECHECK_EPOCH" "+%-m")
R_DAY=$(date -j -f "%s" "$RECHECK_EPOCH" "+%-d")
R_HOUR=$(date -j -f "%s" "$RECHECK_EPOCH" "+%-H")
R_MIN=$(date -j -f "%s" "$RECHECK_EPOCH" "+%-M")

cat > ~/Library/LaunchAgents/com.nuzantara.pg-proxy-cluster-recheck-oneshot.plist <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.nuzantara.pg-proxy-cluster-recheck-oneshot</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>for label in com.balizero.wr2.supervisor com.balizero.wr2.supervisor-watchdog com.balizero.wr2.daily-metrics; do exit_code=\$(launchctl print gui/\$(id -u)/\$label 2>/dev/null | grep -E "last exit" | head -1); echo "\$label: \$exit_code"; done >> ~/.automation-cleanup-2026-05-16/state/pg-proxy-cluster-24h.txt; launchctl bootout gui/\$(id -u)/com.nuzantara.pg-proxy-cluster-recheck-oneshot 2>/dev/null; rm -f ~/Library/LaunchAgents/com.nuzantara.pg-proxy-cluster-recheck-oneshot.plist</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Year</key><integer>$R_YEAR</integer>
    <key>Month</key><integer>$R_MONTH</integer>
    <key>Day</key><integer>$R_DAY</integer>
    <key>Hour</key><integer>$R_HOUR</integer>
    <key>Minute</key><integer>$R_MIN</integer>
  </dict>
  <key>RunAtLoad</key><false/>
</dict>
</plist>
PLIST
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.nuzantara.pg-proxy-cluster-recheck-oneshot.plist
echo "Recheck scheduled for $R_YEAR-$R_MONTH-$R_DAY $R_HOUR:$R_MIN (self-teardown after fire)"
```

**Decision gate at +24h**: leggi `~/.automation-cleanup-2026-05-16/state/pg-proxy-cluster-24h.txt`. Se ≥10/12 exit=0 → cluster self-healed. Se ≥3 ancora ≠0 → triage individuale.

**Rollback**: `launchctl bootout gui/$(id -u)/com.nuzantara.pg-proxy-cluster-recheck-oneshot && rm -f ~/Library/LaunchAgents/com.nuzantara.pg-proxy-cluster-recheck-oneshot.plist`. (Note: self-teardown built into oneshot, so manual rollback only if needed pre-fire.)

### F3.2 — Mini kg-query-api: sleep-guard Tailscale IP (GATED on Mini reach)

```bash
if [ "$MINI_REACHABLE" != "true" ]; then
  echo "F3.2 ABORTED: Mini UNREACHABLE — defer until SSH restored"
  echo "F3.2: mini-side-tbd" >> $DATED_BACKUP/state/v3-deferred-mini-fases.txt
else
  # ... v2 F3.2 logic identical, lines 480-540 ...
fi
```

### F3.3 — Mini fly-pg-tunnel: DNS triage prima del fix token (GATED on Mini reach)

```bash
if [ "$MINI_REACHABLE" != "true" ]; then
  echo "F3.3 ABORTED: Mini UNREACHABLE — defer until SSH restored"
  echo "F3.3: mini-side-tbd" >> $DATED_BACKUP/state/v3-deferred-mini-fases.txt
else
  # ... v2 F3.3 logic identical, lines 547-590 ...
fi
```

---

## FASE 4 — P1 Script mancanti + GH workflows (45 min)

Identical to v2 F4 — already correct (awk comment-prepend, atomic crontab install, GH workflow triage).

---

## FASE 5 — P1 Spread crontab quad-collision (15 min)

Identical to v2 F5 — already correct.

---

## FASE 6 — P2 Genoma (F6.1 only, F6.2 DROPPED)

### F6.1 — Enroll organi Pro orphan con validator canonico verbatim

**Fix H3 PARTIAL**: comando validator verbatim README.

```bash
cd ~/Desktop/nuzantara
PYTHONPATH=apps/organism python3 -m organism.tools.validate_organs_registry \
  apps/organism/organism/organs_registry.yaml \
  --update-checksum 2>&1 | tee $DATED_BACKUP/state/organs-validator-pre.txt
```

(Rest of F6.1 identical to v2 — AIL gating on F8.3 decisions for 4 orphan agents.)

### F6.2 — DROPPED da v3

**Reason**: v2 F6.2 documented L3 exceptions in SYMBIOSIS.md with TODO Test: paths, violando L4 audit-trail gate (`scripts/lint_symbiosis_promises.py` enforced on CI).

**Spec follow-up PR 2026-05-17 (`fix/symbiosis-l3-exceptions-test-citations`)**:
1. Create 6 Test: files (TDD with real assertions, NOT @pytest.skip stubs):
   - `apps/backend-rag/backend/tests/services/cache/test_kg_cache_invalidation_loss_tolerance.py`
   - `apps/backend-rag/backend/tests/services/confirmation/test_confirmation_service_session_expire.py`
   - `apps/backend-rag/backend/tests/services/websocket/test_fanout_client_reconnect.py`
   - (3 altri da `/tmp/automation-map-pro-launchagents.md` review)
2. Update SYMBIOSIS.md source table: PG channels 13 → 15, add `intel_lake_event` + `whatsapp_message_received`
3. Append "## Exceptions documented" section with verbatim Test: paths
4. CI gate: `python scripts/lint_symbiosis_promises.py` passes
5. Atomic commit: "docs(symbiosis): add Test: citations for 6 L3 exceptions + update PG channel count"

---

## FASE 7 — P2 Cross-surface duplicati (AIL per ciascuno)

Identical to v2 F7 — already correct (AIL gating per ciascun surface duplicate).

---

## FASE 8 — P2 Active-active + observatory + orphan agents (AIL)

Identical to v2 F8 — already correct (24h diff PRIMA decision, all AIL gated).

**Modified gates**:
- F8.1 Mini sentinel: gated on `MINI_REACHABLE` (abort if false, defer)
- F8.2 observatory parallel: Pro-only (no Mini dependency)
- F8.3 orphan agents: identical (AIL per ciascuno)

---

## FASE 9 — Post-cleanup verification

```bash
# 9.1 — Re-run mapping (5 sub-agent paralleli)
# Output in research/automations/2026-05-17-

# 9.2 — Before/after metrics
psql "$DATABASE_URL_LOCAL" -c "
  SELECT channel,
    COUNT(*) FILTER (WHERE consumed_at IS NULL) AS unconsumed,
    COUNT(*) FILTER (WHERE consumed_at IS NOT NULL) AS consumed,
    MAX(created_at) AS latest
  FROM events_outbox
  GROUP BY channel ORDER BY unconsumed DESC;
" > $DATED_BACKUP/state/eventbus-metrics-post.txt

# 9.3 — Per-organ health
for label in com.nuzantara.pg-organism-bridge com.nuzantara.pg-organism-bridge-watchdog com.balizero.wr2.supervisor com.cell.organism; do
  state=$(launchctl print gui/$(id -u)/$label 2>/dev/null | grep -E "^\s+(state|last exit code)" | head -2)
  echo "$label: $state"
done > $DATED_BACKUP/state/post-cleanup-organ-health.txt

# 9.4 — Trap restore verify
psql "$DATABASE_URL_LOCAL" -tA -c "SELECT value FROM system_settings WHERE key='federation_alert_mode'"
# expect: $(cat $DATED_BACKUP/state/federation_alert_mode.prior) — i.e. 'observe'

# 9.5 — Defuse TTL sentinel on successful completion (Gemini panel finding #1: timebomb)
# After F9 verification confirms cleanup succeeded, the LaunchAgent runOnce
# scheduled at F0.6 must be torn down explicitly — otherwise it fires later
# and silently reverts federation_alert_mode, potentially overwriting
# intentional post-cleanup adjustments.
if launchctl print gui/$(id -u)/com.nuzantara.cleanup-2026-05-16-ttl-sentinel 2>/dev/null | grep -q "state"; then
  launchctl bootout gui/$(id -u)/com.nuzantara.cleanup-2026-05-16-ttl-sentinel
  rm -f ~/Library/LaunchAgents/com.nuzantara.cleanup-2026-05-16-ttl-sentinel.plist
  echo "$(date) TTL sentinel defused (cleanup completed successfully)" \
    >> $DATED_BACKUP/logs/recovery.log
else
  echo "$(date) TTL sentinel not loaded at F9 (either already fired or never scheduled)" \
    >> $DATED_BACKUP/logs/recovery.log
fi

# 9.5b — K6: verify federation_alert_mode is at expected post-cleanup value (no manifest because no bootout)
psql "$DATABASE_URL_LOCAL" -tA -c "SELECT key, value FROM system_settings WHERE key IN ('federation_alert_mode', 'wr2_canva_renderer_enabled')"
# expected post-cleanup:
#   federation_alert_mode = $PRIOR_FAM (unchanged — F1.3 NEVER modified the value, only acquired FOR UPDATE lock for tampering-detection)
# AIL decision NOT needed at F9: mode was never changed, no re-enable required

# 9.6 — Atomic commits PER FASE (H5 enforcement)
cd ~/Desktop/nuzantara

# F0/F1 commit (plan + watchdog files in infra/)
git add docs/superpowers/plans/2026-05-16-automation-cleanup-plan-v4.md \
        infra/scripts/pg-organism-bridge-watchdog.sh \
        infra/launchagents/com.nuzantara.pg-organism-bridge-watchdog.plist \
        apps/backend-rag/backend/tests/services/events/test_bridge_heartbeat_polling_grandfathered.py
git commit -m "infra(automations): v3 plan + pg-organism-bridge-watchdog (canonical paths)

v2 review verdict: BLOCK (4 KILLER, 6 HIGH, 3 regressions).
v3 fixes: real CTE snapshot K6, empirical Telegram-direct enumeration,
canonical infra/scripts/+infra/launchagents/ paths for watchdog, Test:
citation stub for L4 audit-trail gate (TDD).

Refs: docs/superpowers/plans/2026-05-16-automation-cleanup-review.md
      research/automations/2026-05-16-automation-system-map.md"

# F3.2/F3.3 commits (Mini wrappers) — ONLY IF MINI_REACHABLE
# ... (gated, see v2 lines 938-943)

# F6.1 commit (organs registry) — ONLY IF F8.3 closed
# ... (gated)
```

---

## Dipendenze v3 (verdict-corrected ordering)

```
F0 pre-flight (CTE prior snapshot + LaunchAgent runOnce TTL schedule + Mini reach gate)
   │
   ↓
F1.1 audit Pro+Mini (Pro always, Mini gated)
   │
   ↓
F1.2 enumerate Telegram-direct (empirical, NOT hardcoded)
   │
   ↓
F1.3 K6 observe-lock (CTE FOR UPDATE, NO bootout, NO mode change)
   │
   ↓
F1.4 token rotation (AIL — Antonello touch state file)
   │
   ↓
F8 decisions (AIL) ──┬─→ F6.1 enrollment (validator verbatim README path)
                     │
                     └─→ F2.x disponibilità (F2.3 = infra/ canonical paths)
                                │
F4 / F5 / F7 ── parallel ──────┤
F3.2/F3.3 (Mini gated) ────────┤
                                ↓
                  F6.2 DROPPED — defer to PR 2026-05-17
                                ↓
                  F9 verify + atomic commits
```

---

## Out of scope (v3 explicit)

(Identical to v2 + addenda):
- **F6.2 Symbiosis L3 exceptions** — deferred to follow-up PR 2026-05-17 (TDD test files PRIMA del SYMBIOSIS.md append)
- **Heartbeat-based watchdog** — F2.3 grandfathered polling; durable heartbeat consumer = separate PR
- **Mini-touching fases** — F1.1-mini, F3.2, F3.3, F8.1 deferred until `MINI_REACHABLE=true`

---

## Risks v3

| Rischio | Probabilità | Impatto | Mitigation v3 |
|---|---|---|---|
| Trap on EXIT non fires (kill -9, SIGKILL) | Bassa | Alto | TTL LaunchAgent runOnce (T+4h from execution timestamp) indipendente dalla shell session — fires anche su shell killed; defused in F9.5 on successful completion |
| `atrun` daemon non loaded | Media | Alto | F0.5 pre-flight check + AIL workaround documentato |
| K6 observe-lock fallisce a catturare tampering | Bassa | Medio | F1.3 Step 2 paranoia race check + F9.5b post-cleanup value verify |
| Mode change between F0.4 snapshot and F1.3 lock | Bassa | Basso | F1.3 Step 2 ABORTS cleanup if mismatch — explicit fail-loud, no silent override |
| Mini reconnect mid-flight | Bassa | Basso | F0.1-Mini reach test at session start; mid-session reconnect ignored |
| Mode FOR UPDATE lock blocca writes legittimi durante cleanup | Bassa | Basso | Lock rilasciato a commit transazione F1.3 Step 1 (~ms); cleanup wave non sustained-blocks su `system_settings` |
| Token rotation breaks 11 plist | Media | Alto | F1.4 atomic via `~/.nuzantara-secrets.env` + verify loop |
| L3 lint fails (Test: file missing) | Bassa | Basso | F2.3 Step 3 crea stub PRIMA del Step 5 bootstrap |
| Atomic commit hygiene break | Bassa | Basso | F9.6 splittato in 3 commit + git status check |

---

## Approvazione

v3 piano richiede **Antonello-in-loop** per:
1. F1.4 (token rotation, browser OAuth) — gating per F2+
2. F6.1 (post-F8.3 AIL decisions on 4 orphan agents)
3. F6.3 (A vs B decision partner_commission_changed) — invariato da v2
4. F7 (4 cross-surface decisions) — invariato da v2
5. F8.1, F8.2, F8.3 (decisions canonical surface + agent retire/wire-in)

Autonomous-ops L2 copre tutto il resto.

**Prossimo step**: **review v3 con 4-LLM panel** (Codex sandbox + Gemini + DeepSeek + NB-1) PRIMA dell'esecuzione, per memory rule `feedback_always_review_spec_with_4_llm_2026_05_13`.
