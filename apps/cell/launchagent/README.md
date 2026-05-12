# apps/cell/launchagent — operator-controlled plist files

> **DO NOT edit autonomously.** Per `cicatrix-scars.md` 2026-04-29 antibody
> pattern, plist files in `~/Library/LaunchAgents/` must be operator-deployed
> with `chmod 0444` after manual review.

This directory stores the canonical source for plist files; operators copy
them into `~/Library/LaunchAgents/` and chmod them read-only.

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

4. Edit `com.nuzantara.skills-bridge-consumer.plist` to add
   `BRIDGE_SKILLS_API_KEY` to `EnvironmentVariables` OR ensure the
   plist sources `~/.nuzantara-secrets.env` at runtime (recommended:
   wrap `skills_bridge_consumer.py` invocation in a shell that
   sources the secrets file).

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
   chmod 0444 ~/Library/LaunchAgents/com.nuzantara.skills-bridge-consumer.plist
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
