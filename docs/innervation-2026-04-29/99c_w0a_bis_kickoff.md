# 99c — Kickoff for W0-A.bis (next session, post-2026-04-29 22:30 hijack)

This document briefs the next Claude session (Sonnet 4.6 medium effort
sufficient — Opus 4.7 max effort NOT needed for the remaining mechanical work)
on how to resume W0-A from the current WIP state without repeating the
file-loss recurrence cicatrice.

**Branch**: `feature/innervation-2026-04-29`
**HEAD at session-end**: `9e32d454c` (cicatrice docs)
**WIP code commit**: `3980a1403` (9 files, 1029 insertions, 18 tests passing)
**Status doc**: `7decc8187` (`99b_status_2026_04_29_w0a_branch_hijack.md`)

---

## 1. Pre-flight (DO NOT skip — different from 99_handoff §3)

The 6 checks in `99_handoff.md` §3 still apply, BUT add these 3 first:

### 1.1 Concurrent claude session count

```bash
ps aux | grep -E "(\s|/)claude(\s|$)" | grep -v grep | wc -l
```

- **If output ≥ 3**: STOP. Ask Zero which sessions to kill before starting.
  Multiple concurrent sessions are the documented vector of the 22:30
  branch hijack (cicatrice STRUCTURAL `9e32d454c`).
- **If output = 1 or 2** (this session + the watcher cron tick): proceed.

### 1.2 Branch HEAD sanity

```bash
git fetch origin feature/innervation-2026-04-29
git rev-parse HEAD
git rev-parse origin/feature/innervation-2026-04-29
# both must equal 9e32d454c (or whatever 99_handoff is updated to point to)
```

If local HEAD diverged from origin or is not on this branch, STOP — another
hijack happened in the gap between sessions. Recover from origin first.

### 1.3 Verify the 18 tests still pass

```bash
cd apps/organism && PYTHONPATH=. python3 -m pytest tests/tools/test_validate_genome.py -q
cd ../cell && python3 -m pytest tests/test_bridge_state_reader.py -q
# expected: 10 passed + 8 passed
cd ../..
PYTHONPATH=apps/organism python3 -m organism.tools.validate_genome apps/organism/organism/genome.yaml
# expected: ✓ genome.yaml valid
```

If any fails, STOP — investigate before adding new code on top of broken state.

---

## 2. State recap (what's already done — do NOT redo)

WIP commit `3980a1403` contains:

| File | Lines | Status |
|---|---:|---|
| `apps/organism/organism/genome.yaml` | 153 | 7 organi (3 infra + 4 wave1), checksum sha256 valid |
| `apps/organism/organism/tools/__init__.py` | 0 | empty subpackage marker |
| `apps/organism/organism/tools/validate_genome.py` | 307 | 8 invariant classes + bootstrap mode + checksum stability |
| `apps/organism/tests/tools/__init__.py` | 0 | |
| `apps/organism/tests/tools/test_validate_genome.py` | 187 | 10 tests, all passing |
| `apps/organism/README.md` | +25 | Genoma usage docs (validation + checksum update procedure) |
| `apps/cell/cell/sensors/bridge_state_reader.py` | 146 | `BridgeSource` + `BridgeReading` + `BridgeStateReader.read_all()`, supports state_file in W0 |
| `apps/cell/tests/test_bridge_state_reader.py` | 199 | 8 tests, all passing (happy + 6 failure modes + custom field overrides) |
| `.pre-commit-config.yaml` | +12 | new `validate-genome` hook entry |

**Test count**: 18/18 passing.

**Genoma checksum** (canonical SHA256 of the 7 organ entries):
`2b5b1da6bc848220a0bdedd8fe2b2a1e8a1c5f0c881a6c85435aac82182121ff`. After
ANY edit to `organism/genome.yaml`, run:

```bash
PYTHONPATH=apps/organism python3 -m organism.tools.validate_genome \
    apps/organism/organism/genome.yaml --update-checksum
```

then re-apply the comment header (yaml.safe_dump strips comments — see
README.md note). Then re-run validate_genome (no flags) to confirm.

---

## 3. Remaining W0-A.bis scope

Per `99_handoff.md` §6 + `09_migration_plan.md` §2, W0-A.bis must complete:

### 3.1 W0.2 — `genome_aggregator_sensor.py` + 6 unit tests

**Path**: `apps/cell/cell/sensors/genome_aggregator_sensor.py` + `apps/cell/tests/test_genome_aggregator_sensor.py`.

**Imports**:
- `from cell.sensors.bridge_state_reader import BridgeSource, BridgeStateReader, BridgeReading` (W0.3 already shipped in WIP commit)
- `import yaml` for genome loading
- Optional `import sqlite3` if hooking into `~/.organism/last_seen.db` directly (Wave 2 reads-only)

**Behavior** (07_innervation_protocol.md §3.1):
- `__init__(genome_path, last_seen_db_path)` — both optional with defaults.
- `async def read() -> SensorReading`:
  1. Load genome YAML.
  2. Read `~/.organism/last_seen.db` if present (else assume all stale).
  3. For each organ with a `bridge_source`, run `BridgeStateReader` to get virtual heartbeat.
  4. Merge: organ is `alive` if `last_seen < 90s` (or `1.5x expected_hb_seconds` for custom intervals), `stale` if `< 3x`, `dead` otherwise. Organi with `expected_hb_seconds=0` (infra) are classified by bridge presence only.
  5. Emit `SensorReading(status=green|yellow|red, metadata={total_organs, alive, stale, dead, dead_organs})`.

**Tests** (6 cases):
1. All organi alive → `status=green`.
2. Some stale → `status=yellow`, `metadata.stale=N`.
3. Some dead → `status=red`, `metadata.dead_organs=[...]`.
4. Missing `genome.yaml` → returns reading with error metadata.
5. Missing `last_seen.db` → all organi treated as stale, reading reports it.
6. Bridge source override (use `BridgeStateReader` instead of last_seen.db lookup for that organ).

**DEFERRED to W0-A.bis.bis (not part of this PR)**: wiring the sensor into
`apps/cell/cell/main.py` PulseEngine. Reason: PulseEngine already has 26
constructor args; adding a 27th + plumbing through fixtures is a
cross-cutting change not contained in W0-A scope. Document the wire-up
intent in the new sensor's module docstring.

### 3.2 W0.6 — `scheduled-tick.plist` (repo file only, NO install)

**Path**: `apps/organism/organism/launchd/com.nuzantara.organism.scheduled-tick.plist`.

**Schema** (mirror `com.nuzantara.organism.supervisor.plist` + add hourly cron):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.nuzantara.organism.scheduled-tick</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3</string>
    <string>-m</string><string>organism.scheduled_tick</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>/usr/local/bin:/usr/bin:/bin</string>
    <key>HOME</key><string>/Users/nuzantara</string>
    <key>ORGANISM_REDIS_URL</key><string>redis://127.0.0.1:6379/0</string>
    <key>PYTHONPATH</key><string>/Users/nuzantara/Desktop/nuzantara/apps/organism</string>
  </dict>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Minute</key><integer>0</integer>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>/Users/nuzantara/logs/organism/scheduled-tick.log</string>
  <key>StandardErrorPath</key><string>/Users/nuzantara/logs/organism/scheduled-tick.err</string>
</dict>
</plist>
```

**Verify** with `plutil -lint apps/organism/organism/launchd/com.nuzantara.organism.scheduled-tick.plist` before commit.

**Confirm** the module already exists: `ls apps/organism/organism/scheduled_tick.py` (it does — verified 2026-04-29 22:25).

### 3.3 W0-B — `deploy_w0.sh` script (repo only, runs post-merge)

**Path**: `apps/organism/scripts/deploy_w0.sh`.

**Pattern** (per Zero §Q1 22:08 WITA — bootout/bootstrap, not load/unload):

```bash
#!/usr/bin/env bash
set -euo pipefail

# Per-plist deploy with full 5-trigger abort.
# Triggers (any one fires the abort + Telegram path):
#   1. plutil -lint exit != 0 after cp
#   2. file size <500 bytes after cp
#   3. launchctl bootstrap exit != 0
#   4. presence of new .bak-* / .disabled files in ~/Library/LaunchAgents/com.balizero.organism.* not seen pre-cp
#   5. launchctl print gui/$(id -u)/<label> doesn't show state=running within 30s

REPO=/Users/nuzantara/Desktop/nuzantara/apps/organism/organism/launchd
TARGET=$HOME/Library/LaunchAgents
PLISTS=(
  com.nuzantara.organism.supervisor.plist
  com.nuzantara.organism.control-panel.plist
  com.nuzantara.organism.scheduled-tick.plist
)
CHAT_ID=${TELEGRAM_OWNER_CHAT_ID:-1125336968}

abort() {
  local trigger=$1 plist=$2 msg=$3
  echo "🔴 W0-B ABORT — trigger=$trigger plist=$plist msg=$msg" >&2
  # rollback the deployed plist (if any)
  launchctl bootout "gui/$(id -u)/$(plist_label "$plist")" 2>/dev/null || true
  rm -f "$TARGET/$plist"
  ~/.claude/scripts/mem save unresolved "W0-B abort trigger=$trigger plist=$plist msg=$msg ts=$(date -u +%FT%TZ)" 7 || true
  curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d "chat_id=${CHAT_ID}" \
    --data-urlencode "text=🔴 W0-B ABORT — P0-3 plist corruption signal detected during deploy
Trigger: $trigger
Plist: $plist
Msg: $msg
Time: $(date -u +%FT%TZ)
State: rolled back, organism still on pre-W0 baseline
Next: Zero needs to triage producer before W0-B retry" >/dev/null
  exit 1
}

# ... (full logic per Zero's pattern, single bootout+chmod+cp+lint+chmod+bootstrap+verify cycle per plist)
```

**Tests**: at least one happy-path dry-run test that mocks launchctl / plutil
and verifies the 5 triggers each cause abort. Path:
`apps/organism/tests/scripts/test_deploy_w0.py` (new dir + file).

### 3.4 W0.7 — final commit + draft PR

After 3.1-3.3 complete:

1. Run all tests — expect 18 (existing) + 6 (W0.2) + N (W0-B unit) ≥ 24/24 passing.
2. `plutil -lint` on the new `scheduled-tick.plist`.
3. **WIP-commit-every-10min discipline applies**: commit after each major
   addition (W0.2 alone, W0.6 alone, W0-B alone) and push within 30s.
4. Final commit message footer: include the W0-A.bis scope-cut + reorder
   notes per Zero's 22:08 WITA guidance (already stated in `99b_status` and
   the WIP commit).
5. Open PR draft (NOT auto-merge — Zero reviews W0-A as a unit before W0-B
   actual deploy).
6. PR title: `feat(innervation/W0-A): Genoma + sensors + deploy script (no live LaunchAgent install)`.

---

## 4. Critical reminders

1. **Anti-pattern checklist** from `99_handoff.md` §7 still applies. Do NOT
   redesign the protocol; do NOT touch LaunchAgents in this PR; do NOT
   parallelize Air SSH or Fly deploy.
2. **WIP commit every ~10 min IF untracked files exist**:
   ```bash
   if git ls-files --others --exclude-standard | grep -q .; then
     git add apps/organism/ apps/cell/  # scope-limited
     git commit -m "WIP(innervation/W0-A.bis): checkpoint $(date +%H:%M)"
     git push origin "$(git rev-parse --abbrev-ref HEAD)"
   fi
   ```
3. **Path of last resort recovery**: if a hijack happens, run `git fsck
   --dangling --no-reflogs | grep "dangling blob"` and `git cat-file -p
   <hash>` for any blob suspected of holding lost work. Path B procedure
   in commit `3980a1403` is the canonical idempotent recipe.
4. **Send Telegram alert** to `1125336968` if any abort threshold from
   `99_handoff.md §4` fires. Token in `~/.nuzantara-secrets.env`.
5. **Stash audit**: at session start AND end, run `git stash list | head
   -10`. Any new stash labeled `innervation-wip-*` or `nuz-sync auto-stash`
   between session start and end is a signal another hijack happened —
   investigate before continuing.

---

## 5. Open questions for Zero (NOT blocking — can default if unclear)

1. **Cell PulseEngine wire-up timing**: should it be W0-A.bis.bis (a third
   PR after W0-A.bis lands), or merged into W0-A.bis if the test fixture
   touch-up turns out smaller than feared? Default if Zero silent: separate
   PR (preserve atomicity).
2. **Test path convention for cell sensors**: existing pattern is flat
   (`apps/cell/tests/test_*.py`), Zero §Q4 22:08 suggested `apps/cell/tests/sensors/test_*.py`. WIP commit
   used flat per existing convention. W0.2 should follow the same flat
   pattern unless Zero rules otherwise.
3. **DOCSYNC drift**: still in `stash@{1}: innervation-fase3-preflight-2026-04-29`.
   Per Zero §Q3 22:08 WITA original guidance: leave stashed, regen as separate
   `chore(docsync): regen counters` PR after W0-A merges. Default applies.
