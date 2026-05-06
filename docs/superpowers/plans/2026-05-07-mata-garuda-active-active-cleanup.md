# W2-C Mata Garuda Active-Active Cleanup Plan

**Date:** 2026-05-07
**Branch:** `feat/mata-garuda-active-active-cleanup-2026-05-07`
**Cicatrix:** STRUCTURAL P1 — 13 launchd labels active-active Pro+Mini
**Reference:** `.claude/rules/cicatrix-scars.md` line 8

## Decision Map (Zero-ratified, NOT for relitigation)

| Label (filename basis)              | Canonical Side | Losing Side | Rationale                           |
| ----------------------------------- | -------------- | ----------- | ----------------------------------- |
| `com.matagaruda.intel-bridge.daily` | Mini           | Pro         | Mini = OSINT producer (Modo B)      |
| `com.matagaruda.sentinel.daily`     | Mini           | Pro         | Sentinel = OSINT layer 1            |
| `com.matagaruda.reg-alert.30min`    | Pro            | Mini        | Telegram bot token Pro              |
| `com.matagaruda.kg-linker`          | Pro            | Mini        | Postgres KG locale Pro              |
| `com.matagaruda.wr-topic`           | Pro            | Mini        | WR2 producer suite Pro              |
| `com.matagaruda.wr2-bridge.hourly`  | Pro            | Mini        | WR2 producer suite Pro              |
| `com.matagaruda.bridge.adaptive`    | Pro            | Mini        | Mediator MCP Pro                    |
| `com.matagaruda.daily-briefing`     | Pro            | Mini        | Telegram delivery Pro               |
| `com.matagaruda.kita-feed.daily`    | Pro            | Mini        | kita.balizero.com Vercel deploy Pro |
| `com.matagaruda.public-channel`     | Pro            | Mini        | Outbound socials Pro orchestrator   |
| `com.matagaruda.weekly-digest`      | Pro            | Mini        | Telegram delivery Pro               |
| `com.matagaruda.gap.consumer`       | Pro            | Mini        | KG gaps consumer Pro                |
| `com.matagaruda.watcher.daily`      | Pro            | Mini        | Generic watchdog Pro                |

**Target state:** 2 labels Mini-only (intel-bridge, sentinel), 11 labels Pro-only.

## Validation Findings

### Label/Filename Discrepancy

Two plist files have an internal `Label` key that differs from the filename:

- `com.matagaruda.kita-feed.daily.plist` → Label = `com.matagaruda.kita-feed`
- `com.matagaruda.wr2-bridge.hourly.plist` → Label = `com.matagaruda.wr2-bridge`

`launchctl bootout` requires the **actual Label** (what `launchctl list` shows), NOT the filename.
However, `genome.yaml` references the **filename-style label** (e.g., `com.matagaruda.kita-feed.daily`).
This means:

- bootout target: actual Label key (from `PlistBuddy -c "Print :Label"`)
- genome.yaml drop target: filename-style (matches existing entries verbatim)

### File Mode Hardening (Cicatrix 2026-04-29 P0-3)

All project plist files are now `chmod 0444` (readonly). Before `rm`, must `chmod u+w "$plist"` first.

### SMOKE Check Results (2026-05-07)

Pro launchctl list shows 13/13 mata_garuda doubled labels.
Mini launchctl list (via SSH `ssh mini`) shows same 13/13 doubled labels.
SSH to Mini reachable via mDNS or Tailscale alias.

## Execution Plan

### Phase 1: Test-First (TDD)

1. Create `apps/organism/tests/test_genome_no_active_active.py`:
   - Parse `apps/organism/organism/genome.yaml`
   - Group entries by `recovery_params.label`
   - Fail if any label appears with both `host: pro` AND `host: mini`
   - Whitelist parameter (empty by default — anything failing is a regression)
2. Run pytest — expect 13 failures (current state).

### Phase 2: Bootout Sequence (Atomic Per Label)

For each of the 13 labels, on the LOSING side:

```
LABEL=<actual launchd Label>          # e.g. com.matagaruda.kita-feed (not .daily)
PLIST=~/Library/LaunchAgents/<filename>.plist
UID=$(id -u)

# Step 1: Backup (REQUIRED before any mutation)
cp "$PLIST" "$PLIST.pre-W2C-2026-05-07"

# Step 2: Bootout
launchctl bootout gui/$UID/$LABEL

# Step 3: Verify bootout succeeded
launchctl print gui/$UID/$LABEL 2>&1 | grep -q "Could not find service"
[ $? -eq 0 ] || { echo "ABORT: $LABEL still loaded"; exit 1; }

# Step 4: Make plist writable (cicatrix protection chmod 0444 default)
chmod u+w "$PLIST"

# Step 5: Remove
rm "$PLIST"
```

Atomic per label. If ANY step fails, abort and do not proceed to next label.

### Phase 3: genome.yaml Edit

Drop the LOSING-side entries (13 blocks, ~13-15 lines each) from `apps/organism/organism/genome.yaml`.

Each block to remove follows the pattern:

```yaml
- id: mata_garuda.<name>.<losing_side>
  runtime: <pro|mini>_launchd
  type: cron|daemon
  expected_hb_seconds: ...
  owner_module: ...
  dependencies: [...]
  recovery_action: launchctl_kickstart
  recovery_params:
    host: <losing_side>
    label: com.matagaruda.<label>
  severity_on_silence: warning|error
  cicatrix_refs: []
  duplicates_id: mata_garuda.<name>.<canonical_side>
```

Also strip the `duplicates_id` cross-link line from the canonical-side entries (since the duplicate no longer exists).

### Phase 4: CI Test Verification

Run pytest again — test should now PASS (no active-active pairs).

### Phase 5: Resolver Hardening (Best-Effort)

Update `~/scripts/wave1-pro-mini-dup-resolver.sh` if it tracks per-label whitelists.
This is per-machine state on Pro, not in git, so the patch is local-only.

## Bootout Sequence Order

Mini-canonical (remove from Pro):

1. com.matagaruda.intel-bridge.daily
2. com.matagaruda.sentinel.daily

Pro-canonical (remove from Mini, via SSH): 3. com.matagaruda.reg-alert.30min 4. com.matagaruda.kg-linker 5. com.matagaruda.wr-topic 6. com.matagaruda.wr2-bridge (filename `wr2-bridge.hourly.plist`) 7. com.matagaruda.bridge.adaptive 8. com.matagaruda.daily-briefing 9. com.matagaruda.kita-feed (filename `kita-feed.daily.plist`) 10. com.matagaruda.public-channel 11. com.matagaruda.weekly-digest 12. com.matagaruda.gap.consumer 13. com.matagaruda.watcher.daily

## Rollback

If a bootout fails partway:

- All `.pre-W2C-2026-05-07` backups remain on disk
- Restore via: `cp "$PLIST.pre-W2C-2026-05-07" "$PLIST" && launchctl bootstrap gui/$UID "$PLIST"`

## Risk Assessment

- **Low risk for cron labels** — double-firing is just 2× metric inflation, no data corruption (per cicatrix entry).
- **Medium risk for `bridge.adaptive` daemon** — losing one side means the daemon only runs on Pro. If Mini was the canonical mediator, this would silently break MCP. Decision per spec: Pro is canonical. Verify post-cleanup via `launchctl list` on Pro confirms it stays loaded.
- **No risk to gap.consumer/kg-linker** — these are Pro-only writers per spec; Mini was firing redundantly.
