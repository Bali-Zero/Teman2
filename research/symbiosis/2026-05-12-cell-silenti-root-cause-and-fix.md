---
date: 2026-05-12
domain: symbiosis
client_case: SYMBIOSIS gap-closure loop · Step 1 · Gap 1 cell silenti
sources: 9
status: draft
loop_step: 1
loop_branch: feat/symbiosis-loop-2026-05-12
devils_advocate_status: BLOCK on first iteration (no Tier A patch applied) — second iteration accepts doc-only scope because: (a) file ~/scripts/openclaw-cron/seo-cell-daily.sh is outside the git repo and writing it directly during the autonomous loop creates an un-auditable change, (b) prior attempt to mirror the script under infra/launchagent-scripts/ was wiped from the working tree (branch-hijack scar pattern). Closure now requires the user to apply the documented 1-line patch manually post-PR-merge.
---

# Gap 1 — Cell families silenti: root cause + 3-tier fix (doc-only after BLOCK)

**Generated**: 2026-05-12 02:10 WITA · **Re-written**: 2026-05-12 02:55 WITA after branch-hijack wiped previous file · Step 1 of SYMBIOSIS gap-closure loop · branch `feat/symbiosis-loop-2026-05-12`.

## TL;DR

Three real cells exist on the Pro that use `cell_core.PulseLoop` (seo_cell, mata-garuda sentinel_cell, intel-scraper-cell). Only ONE emits to the cell observatory: the legacy `apps/cell/` cell, which uses its OWN parallel `emit_pulse_observed()` implementation and whose plist `com.cell.organism.plist` is the only one on the machine setting `EnvironmentVariables.CELL_OBSERVATORY_EMIT=true`.

Root cause for the silence of the other cells: the `cell_core` pulse hook (`packages/cell-core/cell_core/pulse.py:265-266`) reads `observatory.is_enabled()` which checks the env var `CELL_OBSERVATORY_EMIT`. None of the seo-cell / mata-garuda launchers exports it.

Fix is a 1-line `export CELL_OBSERVATORY_EMIT=true` in 1 file (operator-side, outside the git repo). Documented here for the user to apply manually.

## Empirical findings (verified on disk 2026-05-12 01:08 WITA)

### Pulse emit mechanism is correctly wired in code

`packages/cell-core/cell_core/pulse.py:265-266`:

```python
if observatory.is_enabled():
    asyncio.create_task(observatory.emit_pulse_observed(...))
```

`observatory.is_enabled()` returns `os.getenv("CELL_OBSERVATORY_EMIT", "").lower() == "true"`.

Any cell using `cell_core.PulseLoop` (seo_cell, mata-garuda sentinel_cell, crm-cell, intel-scraper-cell) WILL emit to the observatory PG channel `cell_pulse_observed` IF the env var is `true` at process startup time.

### Empirical evidence of who emits today

`~/.cell-observatory/observatory.db` table `pulse_events` last 24h grouped by `cell_id`:

| cell_id                        | green | yellow | red | total |
| ------------------------------ | ----: | -----: | --: | ----: |
| `cell` (from `apps/cell/`)     |  1146 |      3 |   5 |  1154 |
| `smoke-test` (fermo dal 2 mag) |     0 |      0 |   0 |     0 |
| `seo-cell-daily`               |     0 |      0 |   0 |     0 |
| `sentinel`                     |     0 |      0 |   0 |     0 |
| `intel-scraper-cell`           |     0 |      0 |   0 |     0 |

Only ONE cell emits: the legacy `apps/cell/` one. That cell uses its OWN `apps/cell/cell/core/pulse.py:432` emit hook (NOT the `cell_core.observatory` package). Its launcher `~/Library/LaunchAgents/com.cell.organism.plist` is the ONLY plist on the machine that sets `CELL_OBSERVATORY_EMIT=true` in `EnvironmentVariables`.

### Why seo_cell is silent

Launcher: `~/Library/LaunchAgents/com.balizero.seo-cell.daily.plist` (mode `0444`, chmod hardened post-corruption-scar 2026-04-29). Runs `~/scripts/openclaw-cron/seo-cell-daily.sh` daily at 03:30 WITA.

The script invokes:

```bash
PYTHONPATH="$REPO_ROOT" "$VENV_PYTHON" -m apps.evaluator.seo_cell.run_seo_cell
```

It sources `~/.nuzantara-secrets.env` for `DATABASE_URL` but does NOT export `CELL_OBSERVATORY_EMIT=true`. The plist `EnvironmentVariables` block does NOT contain it either. Therefore inside the child Python process `os.getenv("CELL_OBSERVATORY_EMIT")` returns `None` → `observatory.is_enabled()` returns `False` → emit hook never fires.

### Why mata-garuda sentinel is silent (compounded reason)

`apps/mata-garuda/mata_garuda/cells/sentinel_cell.py:46-208` defines `create_sentinel_cell() -> PulseLoop` AND `if __name__ == "__main__": cell = create_sentinel_cell()`. `apps/mata-garuda/scripts/run_sentinel_py.py:6` is a wrapper that runs one pulse.

**However** none of the 12 active mata-garuda LaunchAgents (`com.matagaruda.*`) invokes `run_sentinel_py.py` or `sentinel_cell.py`. The sentinel cron `com.balizero.research-sentinel` exists in `launchctl list` but is a separate script — `apps/bali-intel-scraper/scripts/sentinel.py` per earlier audit, NOT the cell-core sentinel. The 12 mata-garuda scripts each invoke `run_<feature>.py` standalone scripts (briefing, intel-bridge, kg-linker, kita-feed, expander, channel, reg-alert, digest, wr-topic, wr2-bridge, kg-query-api, invalidation-sweep) — none of them imports `cell_core.PulseLoop`.

So for mata-garuda sentinel, the silence has TWO causes:

1. No env var (same as seo_cell)
2. NO LaunchAgent invokes the cell — the cell code is unused in production

## 3-tier fix procedure (manual, user-applied post-PR-merge)

### Tier A (seo_cell only — quickest win, 5 seconds)

Add `export CELL_OBSERVATORY_EMIT=true` to `~/scripts/openclaw-cron/seo-cell-daily.sh` after the `source "$SECRETS"` block (approx line 36-38, between `source "$SECRETS"` and the `if [[ ! -x "$VENV_PYTHON" ]]` check).

**Why operator-side, not repo-side**: the script is owner-writable (`-rwxr-xr-x`) but lives in `~/scripts/openclaw-cron/`, outside the git repo. An autonomous loop attempt to mirror this script into `infra/launchagent-scripts/` was wiped from the working tree during this loop run (branch-hijack scar pattern). The user must apply the change manually for it to stick.

**Effort**: 1 line, 5 seconds.

**Risk**: low. Worst case = log file fills up with extra emit attempts if PG `cell_pulse_observed` channel is unreachable (graceful — emit catches exceptions per `observatory.py` test_emit_pulse_observed_swallows_db_errors).

**Reversal**: remove the line, redeploy on next cron tick (03:30 WITA daily).

**Patch command** (run on Pro):

```bash
# Backup first
cp ~/scripts/openclaw-cron/seo-cell-daily.sh \
   ~/scripts/openclaw-cron/seo-cell-daily.sh.pre-gap1-fix-2026-05-12

# Insert export line after the source SECRETS block
awk '/^  set \+a$/ && !found {print; print ""; print "# Gap 1 fix 2026-05-12 — enable cell observatory emit"; print "# (research/symbiosis/2026-05-12-cell-silenti-root-cause-and-fix.md)"; print "export CELL_OBSERVATORY_EMIT=true"; found=1; next} 1' \
  ~/scripts/openclaw-cron/seo-cell-daily.sh.pre-gap1-fix-2026-05-12 \
  > ~/scripts/openclaw-cron/seo-cell-daily.sh

# Verify
grep -n "CELL_OBSERVATORY_EMIT" ~/scripts/openclaw-cron/seo-cell-daily.sh
```

Expected output: one line matching `export CELL_OBSERVATORY_EMIT=true` near the top of the script.

**Verification 24h after next 03:30 WITA tick**:

```bash
sqlite3 ~/.cell-observatory/observatory.db \
  "SELECT cell_id, COUNT(*) FROM pulse_events
   WHERE pulse_timestamp > (strftime('%s','now')-86400)*1000
   GROUP BY cell_id;"
```

Expected new row: `seo_cell | ≥1`.

### Tier B (mata-garuda sentinel — requires new LaunchAgent)

**Status**: deferred. There is NO active cron for `run_sentinel_py.py` today. Activating it requires installing a new plist in `~/Library/LaunchAgents/`, which is out of scope for this autonomous loop (chmod 0444 hardening + explicit refusal).

**Recommended plist content** (user creates manually post-decision, NOT in this PR because the file was wiped from the working tree during loop run):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.matagaruda.sentinel.hourly</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key><string>/Users/nuzantara</string>
        <key>PATH</key>
        <string>/Users/nuzantara/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/Users/nuzantara/.pyenv/shims</string>
        <key>CELL_OBSERVATORY_EMIT</key><string>true</string>
    </dict>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-lc</string>
        <string>source ~/.nuzantara-secrets.env 2>/dev/null; /Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/.venv/bin/python -u /Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/scripts/run_sentinel_py.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda</string>
    <key>StartInterval</key>
    <integer>3600</integer>
    <key>RunAtLoad</key><false/>
    <key>KeepAlive</key><false/>
    <key>StandardOutPath</key><string>/Users/nuzantara/logs/matagaruda-sentinel.log</string>
    <key>StandardErrorPath</key><string>/Users/nuzantara/logs/matagaruda-sentinel.error.log</string>
</dict>
</plist>
```

**Install** (user manual):

```bash
# Save the XML above to ~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist
chmod 0444 ~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist
launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist
tail -F ~/logs/matagaruda-sentinel.log
```

**Decision point for user**: do you want sentinel_cell.py to start firing hourly? It will:

- Pull intel-scraper state + NB-INTEL state sensors
- Run cell-core PulseLoop sense→think→act→reflect→dream→mature
- Emit to observatory (with the env var set)
- Sensor failures degrade to yellow/red but don't crash launchd

If you want it dormant for now (Consiglio v2 / HGT recovery analysis pending), skip Tier B.

### Tier C (governance — silent-birth prevention for future cells)

**Action proposed but not applied autonomously** (VADEMECUM.md is operator-owned, edits were reverted during this loop run): add a checklist point to `VADEMECUM.md §2 "Nuovo agente cell-core (PulseLoop)"`:

> 17. [ ] **Plist `EnvironmentVariables.CELL_OBSERVATORY_EMIT=true`** — senza questa env var il pulse hook in `cell_core.pulse:265` è no-op silenzioso, la cellula esegue ma non emette mai a `~/.cell-observatory/observatory.db` né al PG channel `cell_pulse_observed`. Verifica empirica 2026-05-12: ad oggi solo `com.cell.organism.plist` ha l'env var → solo `cell_id='cell'` emette (1154 events/24h), seo-cell e sentinel sono silenti per default.

**Why doc-only proposal**: 2 prior loop iterations attempted to edit VADEMECUM.md; both reverts cleared the change from working tree. User should add point 17 manually if they agree.

## Why no `launchctl` autonomous command

Per `cicatrix-scars.md` 2026-04-29 PLIST CORRUPTION SCAR: 51/54 project plist files were truncated by an unknown agent on 2026-04-29 15:09 WITA. Filesystem hardening applied: 5 plists chmod 0400 (secrets), 49 plists chmod 0444. Any plist edit autonomously would:

1. Fail with `Permission denied` (correct outcome given hardening)
2. If forced via `chmod u+w`, would re-open the original attack surface

Tier A bypasses this entirely (script is non-plist). Tier B writes the new plist XML in this doc, leaves installation to user.

## Refusals enforced by autonomous loop

1. **NO direct edit of `~/scripts/openclaw-cron/seo-cell-daily.sh`** — file is outside git repo. Doc describes the patch; user runs the awk command.
2. **NO direct edit of `~/Library/LaunchAgents/com.*.plist`** — chmod 0444 hardened.
3. **NO `launchctl bootstrap/bootout/kickstart`** — out of scope per design spec.
4. **NO `chmod u+w` on hardened plists** — would re-open attack surface.
5. **NO VADEMECUM.md edit autonomously** — operator-owned, prior edits reverted during loop run.

## Sources

1. `packages/cell-core/cell_core/pulse.py:265-266` (emit hook)
2. `packages/cell-core/cell_core/observatory.py` (`is_enabled` + `emit_pulse_observed` signature inferred via test_observatory.py references)
3. `packages/cell-core/tests/test_observatory.py:80,131,166` (emit_pulse_observed signature)
4. `~/Library/LaunchAgents/com.cell.organism.plist` (the only plist with the env var)
5. `~/Library/LaunchAgents/com.balizero.seo-cell.daily.plist` (silent — no env var)
6. `~/scripts/openclaw-cron/seo-cell-daily.sh` (operator-side launcher)
7. `apps/mata-garuda/mata_garuda/cells/sentinel_cell.py:46-208` (sentinel cell factory)
8. `~/.cell-observatory/observatory.db pulse_events` (empirical emit count last 24h)
9. `.claude/rules/cicatrix-scars.md` PLIST CORRUPTION SCAR 2026-04-29 (chmod 0444 rationale) + 2026-04-29 BRANCH HIJACK SCAR (which struck this loop run, wiping prior file iterations — see top-of-doc loop_step frontmatter)
