# apps/cell/launchagent — operator-controlled plist files

> **DO NOT edit autonomously.** Per `cicatrix-scars.md` 2026-04-29 antibody
> pattern, plist files in `~/Library/LaunchAgents/` must be operator-deployed
> with read-only permissions after manual review. Use `0444` only for plists
> without inline secrets; use `0400` for any plist that can carry secrets.

This directory stores the canonical source for plist files; operators copy
them into `~/Library/LaunchAgents/` and chmod them read-only.

## cell.organism (Cell core daemon) — RESURRECTION 2026-05-21

The Cell core daemon plist source is at `apps/cell/com.cell.organism.plist`
(parent dir, not this directory — historical layout).

**Status as of 2026-05-21**: NOT installed in `~/Library/LaunchAgents/`.
Cell core stopped pulsing on 2026-05-16 08:01 WITA. Empirical evidence in
`~/.cell-observatory/observatory.db` (`cell_id='cell'` last_pulse).

**Operator install steps** (run from clean checkout of `nuzantara` main):

```bash
# 1. Preconditions
ls apps/cell/.env                    # secrets in CELL_*, GOOGLE_API_KEY, etc.
ls apps/cell/.venv/bin/python        # virtualenv exists
ls apps/cell/com.cell.organism.plist # plist source

# 2. Run installer (idempotent)
bash apps/cell/scripts/install_cell_daemon.sh

# 3. Verify pulses resume within 5min
sleep 60
sqlite3 ~/.cell-observatory/observatory.db \
  "SELECT max(pulse_timestamp) FROM pulse_events WHERE cell_id='cell';"
```

**Warning re P0 secret leak 2026-05-21**: `apps/cell/.env` currently contains
the `backend_rag_v2` Postgres password that is the subject of the P0
incident (`cicatrix-scars.md` head entry). If/when that password is rotated,
`apps/cell/.env` MUST be updated BEFORE re-launching the daemon (or the
daemon will crash-loop on `CELL_DATABASE_URL` auth failure).

The reconstructed plist at `~/p0-3-recovery/plist_reconstructed/com.cell.organism.plist`
contains the same leaked secrets inline; do NOT use that file as install
source. The repo-tracked `apps/cell/com.cell.organism.plist` sources
secrets from `.env` (out-of-tree) — this is the correct posture.

## skills-bridge-consumer (TICKET G.3)

Cron-invoked shim that pulls `cell:skills` Redis stream entries from
Fly Upstash to Pro localhost Redis. Spec:
`research/symbiosis/2026-05-13-ticket-G-narrow-spec.md`.

**Operator deploy steps**:

1. Generate `BRIDGE_SKILLS_API_KEY` (32+ char random string):
   ```bash
   openssl rand -hex 32
   ```

2. Add to Pro secrets file (operator-edited):
   ```bash
   # ~/.nuzantara-secrets.env
   BRIDGE_SKILLS_API_KEY=<generated-key>
   ```

3. Add same key to Fly secrets:
   ```bash
   fly secrets set BRIDGE_SKILLS_API_KEY=<generated-key> -a nuzantara-rag
   ```

4. Do not add `BRIDGE_SKILLS_API_KEY` to the plist. The plist calls
   `apps/cell/scripts/skills_bridge_consumer_launcher.sh`, which sources
   `~/.nuzantara-secrets.env` at runtime and then execs
   `skills_bridge_consumer.py`.

5. Expand the `StartCalendarInterval` array to cover the full
   06:00–21:55 window (every 5 min × 17h = 204 entries). The shipped
   plist only covers the 06:00 hour as a template — operator
   generates the full schedule via:
   ```python
   for h in range(6, 22):
       for m in range(0, 60, 5):
           print(f"  <dict><key>Hour</key><integer>{h}</integer>"
                 f"<key>Minute</key><integer>{m}</integer></dict>")
   ```

6. Copy + chmod + bootstrap:
   ```bash
   cp apps/cell/launchagent/com.nuzantara.skills-bridge-consumer.plist \
      ~/Library/LaunchAgents/
   chmod 0400 ~/Library/LaunchAgents/com.nuzantara.skills-bridge-consumer.plist
   launchctl bootstrap gui/$(id -u) \
      ~/Library/LaunchAgents/com.nuzantara.skills-bridge-consumer.plist
   ```

7. Verify next tick:
   ```bash
   tail -f ~/Library/Logs/skills-bridge-consumer.log
   ```

   Within 5 min you should see:
   ```
   YYYY-MM-DD HH:MM:SS INFO [skills_bridge] no new events (last_id=0-0)
   ```
   ... or, if A.2 has published events:
   ```
   YYYY-MM-DD HH:MM:SS INFO [skills_bridge] success: XADD'd N events, last_id=X-0 (was 0-0)
   ```

8. Empirical verify Pro `XLEN cell:skills`:
   ```bash
   redis-cli XLEN cell:skills
   # before: 19  →  after first tick (if A.2 has published): >19
   ```
