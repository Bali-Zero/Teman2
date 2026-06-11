# HOME-bridge sync antibody

**Script:** `scripts/verify_home_bridge_sync.sh`
**Scar family:** W50 / W51 / W52
**LaunchAgent watched:** `com.nuzantara.openclaw-whatsapp-bridge`

## The invariant

The **live** WhatsApp bridge does **not** run from the git checkout. It runs from
a HOME copy that is **not** git-tracked:

```
~/.openclaw/bin/openclaw_whatsapp_bridge.py     <- PROD (live, hand-patched historically)
scripts/openclaw_whatsapp_bridge.py             <- tracked source of truth (origin/main)
```

These two must be byte-identical. Nothing enforced that, so they drifted in
silence (the W50/W51/W52 scar): a fix that touches only `scripts/` is invisible
to prod until HOME is re-copied; a hand-patch on HOME never lands in git.

This is dangerous because the WhatsApp **safety guards** (property-zoning /
nominee / villa — commits F05 / F06 / F13) live in this file. Drift means prod
either runs **without** the guards the repo thinks are deployed, or runs guards
**different** from what the repo says is shipped — and until this antibody, both
were undetectable.

## What the antibody does

1. `git hash-object ~/.openclaw/bin/openclaw_whatsapp_bridge.py` (live HOME blob).
2. `git fetch origin main` then `git rev-parse origin/main:scripts/openclaw_whatsapp_bridge.py` (ground-truth blob).
   **origin/main is ground truth — deliberately NOT the local checkout**, which
   can be stale by dozens of commits.
3. Hashes match → exit 0, logs `HOME bridge in sync with origin/main`.
4. Hashes diverge → exit 1, prints both hashes + a diff line-count summary, and
   fires a Telegram `⚠️ HOME bridge DRIFT vs origin/main` alert (if creds are
   configured, same secret-sourcing pattern as the other sentinel scripts).
5. HOME copy absent (e.g. on Mini, no bridge installed) → exit 0 with a WARN.
   That is a non-event, not a drift.

Kill switch: `HOME_BRIDGE_SYNC_OFF=1`.
Self-test of the alert path: `FORCE_ALERT=1 bash scripts/verify_home_bridge_sync.sh`.

## How to run it

```bash
cd ~/Desktop/nuzantara
bash scripts/verify_home_bridge_sync.sh ; echo "exit=$?"
```

Exit `0` = in sync (or no HOME copy on this machine). Exit `1` = DRIFT.

## What to do on DRIFT

Resolution is **one-directional: origin/main → HOME, NEVER the reverse.**
The HOME copy is a deployment artifact; the repo is the source of truth. If
someone hand-patched HOME and that patch is genuinely wanted, it must first be
committed to `scripts/openclaw_whatsapp_bridge.py` via a normal PR, land on
origin/main, and only then be re-deployed to HOME.

To re-deploy origin/main → HOME:

```bash
cd ~/Desktop/nuzantara
git fetch origin main
# materialise the ground-truth blob straight into the live HOME path:
git show origin/main:scripts/openclaw_whatsapp_bridge.py > ~/.openclaw/bin/openclaw_whatsapp_bridge.py
chmod +x ~/.openclaw/bin/openclaw_whatsapp_bridge.py

# restart the bridge so prod picks up the new file:
launchctl kickstart -k "gui/$(id -u)/com.nuzantara.openclaw-whatsapp-bridge"
# (or: launchctl unload + load the plist if kickstart is unavailable)

# re-verify:
bash scripts/verify_home_bridge_sync.sh ; echo "exit=$?"   # expect exit=0
```

**Never** copy HOME → repo to "fix" a drift. That launders an unreviewed
hand-patch (possibly one that weakens a safety guard) into the source of truth.

## Scheduling (operator step — NOT installed by this change)

This change deliberately does **not** install a LaunchAgent (local infra is an
operator decision). Recommended: run every ~30 min via launchd. Sketch:

```xml
<!-- ~/Library/LaunchAgents/com.nuzantara.home-bridge-sync.plist -->
<key>Label</key><string>com.nuzantara.home-bridge-sync</string>
<key>ProgramArguments</key>
<array>
  <string>/bin/bash</string>
  <string>/Users/nuzantara/Desktop/nuzantara/scripts/verify_home_bridge_sync.sh</string>
</array>
<key>StartInterval</key><integer>1800</integer>   <!-- 30 min -->
<key>RunAtLoad</key><true/>
```

The script already self-hardens for launchd: minimal `PATH`, absolute `git`
path, secrets sourced from `~/.nuzantara-secrets.env`.

## Note: stale local checkout (separate issue)

As of writing, the **local checkout** of the bridge can differ from both HOME and
origin/main — the checkout has been observed ~85 commits behind origin/main with
dirty files. That is a _separate_ hygiene problem (the antibody intentionally
compares against `origin/main`, not the checkout, precisely so a stale checkout
cannot produce a false DRIFT). Pulling the local checkout up to origin/main is
tracked separately and is not required for this antibody to be correct.
