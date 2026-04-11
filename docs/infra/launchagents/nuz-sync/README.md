# nuz-sync — bidirectional git sync daemon for nuzantara repo

Keeps the `nuzantara` repo in sync between **Pro** and **Air** (and origin) without
manual `git pull` / `git push` on every branch switch. Designed to be safe by
default: only does fast-forward merges, never force-pushes, never auto-pushes
your commits.

## Quick install

After cloning the repo, on each machine (Pro and Air):

```bash
bash docs/infra/launchagents/nuz-sync/install.sh
```

The installer is **idempotent** — re-run it to apply updates after `git pull`,
or to recover from a broken state. It detects host (Pro/Air) automatically and
configures paths accordingly.

To verify it's working:

```bash
launchctl list com.nuzantara.nuz-sync           # daemon
launchctl list com.nuzantara.nuz-sync-watchdog  # self-healing layer
tail -f ~/logs/nuz-sync/sync.log                # live log
```

## What it solves

Two MacBooks (Pro, Air) share the same nuzantara repo. You want:

- Work seamlessly on either machine without "which branch is ahead of which?"
- Automatic `git fetch` + fast-forward of `main` between runs
- Notification when the two diverge (requires manual merge)
- **No surprises**: the daemon never pushes your local commits — you decide when to expose work

What it replaces: the old `post-commit` hooks that tried to push Pro↔Air directly via SSH,
which failed silently when the peer was offline or had a dirty working tree.

## Architecture

```
┌──────────────┐                              ┌──────────────┐
│  Pro (M4)    │                              │  Air (M4)    │
│  ~/Desktop/  │                              │  ~/Projects/ │
│  nuzantara   │                              │  nuzantara   │
└──────┬───────┘                              └──────┬───────┘
       │                                             │
       │  launchd: com.nuzantara.nuz-sync            │
       │  runs every 120s                            │
       │                                             │
       │  1. fetch origin (GitHub)                   │
       │  2. fetch peer (SSH, 15s timeout)           │
       │  3. if on main + clean working tree:        │
       │     FF to origin/main                       │
       │     FF to peer/main                         │
       │  4. auto-stash noise files (state JSONs)    │
       │  5. alert Telegram on divergence            │
       │                                             │
       └────────────►  GitHub origin  ◄──────────────┘
                      (source of truth)
```

### Nodes

| Node | Host          | User             | Repo path              | Peer remote |
| ---- | ------------- | ---------------- | ---------------------- | ----------- |
| Pro  | `Nuzantara`   | `nuzantara`      | `~/Desktop/nuzantara`  | `air`       |
| Air  | `Nuzantara-9` | `antonellosiano` | `~/Projects/nuzantara` | `pro`       |

Both nodes run identical logic. Host detection is automatic via `scutil --get LocalHostName`.

### Files (per node)

```
~/scripts/nuz-sync/
  nuz-sync.sh           # main daemon script (called by launchd every 2 min)
  nuz-sync-check.sh     # lightweight health probe (called by Claude SessionStart hook)
  nuz-sync-watchdog.sh  # self-healing watchdog (called every 10 min)
  README.md             # this file

~/logs/nuz-sync/
  sync.log              # daemon run history (rotated at 1MB)
  sync.log.1            # previous rotation
  stdout.log            # launchd stdout capture
  stderr.log            # launchd stderr capture
  last-run              # unix timestamp of last successful run (heartbeat)
  sync.lock             # PID lock file (auto-cleared on exit)
  .alert-*              # per-category alert cooldown markers

~/Library/LaunchAgents/
  com.nuzantara.nuz-sync.plist           # daemon (StartInterval=120)
  com.nuzantara.nuz-sync-watchdog.plist  # watchdog (StartInterval=600)
```

## What it does

### Every 2 minutes (`nuz-sync.sh` via launchd)

1. **Rotate log** if `sync.log` exceeds 1MB
2. **Check kill switch**: if `.git/sync-pause` exists, exit 0 (no-op)
3. **Acquire lock**: PID file in `~/logs/nuz-sync/sync.lock`, exits if another run is active
4. **Load Telegram token** from `~/.zshrc.secrets` (Pro) or `~/.nuzantara-secrets.env` (Air)
5. **Fetch remotes**:
   - `git fetch origin --quiet`
   - `timeout 15 git fetch <peer> --quiet` (peer may be offline)
6. **For each managed branch** (`main` only, by design):
   - Skip if not currently on that branch (you're working on a feature branch → leave alone)
   - Skip if HEAD is detached
   - Skip if working tree has real (non-noise) changes
   - Auto-stash noise files (see pattern list below)
   - If origin ahead and local is ancestor → `git merge --ff-only origin/main`
   - If local ahead of origin → **do not push** (manual push policy)
   - If diverged → **alert Telegram**, do nothing
   - Same logic for peer remote
7. **Write heartbeat** to `~/logs/nuz-sync/last-run`

### Every 10 minutes (`nuz-sync-watchdog.sh` via launchd)

Self-healing layer. See [Self-healing](#self-healing) below.

### At every Claude Code session start (`nuz-sync-check.sh` via SessionStart hook)

Lightweight probe. Exits 0 always (never blocks Claude). Prints one-line warning if:

- Daemon never ran (missing heartbeat file)
- Heartbeat stale (>10 min since last run)
- Current branch is behind or ahead of origin/main (info only, not error)

## Noise file patterns (auto-stashed)

These are auto-generated files that pollute the working tree constantly. The daemon
stashes them before pull so they never block a fast-forward. They are recoverable
via `git stash list`.

```bash
NOISE_PATTERNS=(
    "apps/evaluator/nlm_deep_research/"
    "apps/evaluator/nlm_nb"
    "apps/evaluator/nlm_deep_research/t4_state.json"
    "apps/evaluator/nlm_deep_research/yt_state.json"
    "apps/evaluator/nlm_deep_research/freshness_monitor_state.json"
    "apps/evaluator/nlm_deep_research/gap_scanner_state.json"
    "shared/escalations_pro.jsonl"
    "apps/bali-intel-scraper/data/published_articles.json"
    "data/analysis/SEO_ACTION_PLAN_REAL_DATA.json"
    "apps/backend-rag/backend/app/routers/admin_team_activity.py"
)
```

If you find another file that constantly appears modified without your input, add
it to this list in `nuz-sync.sh` and restart the daemon on both nodes.

## Safety guarantees

| Guarantee                             | How                                        |
| ------------------------------------- | ------------------------------------------ |
| Never loses your work                 | Never force-pushes, never `reset --hard`   |
| Never pushes your local commits       | `git push` is not in the script at all     |
| Never merges a non-fast-forward       | Uses `merge --ff-only`                     |
| Never stashes your real edits         | Only files matching `NOISE_PATTERNS`       |
| Never corrupts HEAD                   | Skips if detached or branch unreadable     |
| Never spams Telegram                  | 1-hour cooldown per alert category         |
| Never runs twice in parallel          | PID lock file                              |
| Never runs during manual intervention | `.git/sync-pause` kill switch              |
| Never runs out of disk silently       | Watchdog cleans temp packs, alerts at <2GB |

## Self-healing

`nuz-sync-watchdog.sh` runs every 10 minutes and checks for 6 failure modes.
When it detects one, it attempts auto-fix and sends a Telegram alert describing
what it did.

| Failure                         | Detection                                  | Auto-fix                                     |
| ------------------------------- | ------------------------------------------ | -------------------------------------------- |
| Daemon not loaded in launchd    | `launchctl list` missing label             | `launchctl load` the plist                   |
| Daemon LastExitStatus != 0      | `launchctl list` returns bad exit          | `launchctl kickstart` + alert                |
| Heartbeat stale (>10 min)       | `last-run` file older than 10 min          | Run daemon manually once + alert             |
| Lock file orphan (pid dead)     | `sync.lock` exists but pid not running     | Remove lock file                             |
| Disk < 2GB free                 | `df` output                                | `brew cleanup`, remove git temp packs, alert |
| Syncthing service not running   | `brew services list` shows `none` or empty | `brew services start syncthing` + alert      |
| Log file >10MB (rotation stuck) | File size check                            | Manual rotation, alert                       |
| Git `.git/index.lock` orphan    | `index.lock` > 5 min old                   | Remove it (safe: git retries)                |

Watchdog failures are non-fatal. If the watchdog itself can't run, the Claude
SessionStart hook will surface that at next session.

## Operations

### Check daemon status

```bash
# Is it loaded?
launchctl list | grep nuz-sync

# When did it last run?
cat ~/logs/nuz-sync/last-run | xargs -I{} date -r {}

# Last 20 log lines
tail -20 ~/logs/nuz-sync/sync.log
```

### Pause temporarily

```bash
# Before doing manual git surgery
touch ~/Desktop/nuzantara/.git/sync-pause   # Pro
touch ~/Projects/nuzantara/.git/sync-pause  # Air

# When done
rm .git/sync-pause
```

### Force a run now

```bash
/bin/bash ~/scripts/nuz-sync/nuz-sync.sh
```

### Read alert cooldown

```bash
ls -la ~/logs/nuz-sync/.alert-*
```

### Disable completely

```bash
launchctl unload ~/Library/LaunchAgents/com.nuzantara.nuz-sync.plist
launchctl unload ~/Library/LaunchAgents/com.nuzantara.nuz-sync-watchdog.plist
```

To re-enable:

```bash
launchctl load ~/Library/LaunchAgents/com.nuzantara.nuz-sync.plist
launchctl load ~/Library/LaunchAgents/com.nuzantara.nuz-sync-watchdog.plist
```

## Troubleshooting

### "Telegram alerts not arriving"

Check that the secrets file is readable and `TELEGRAM_BOT_TOKEN` is set:

```bash
# Pro
grep TELEGRAM_BOT_TOKEN ~/.zshrc.secrets

# Air
grep TELEGRAM_BOT_TOKEN ~/.nuzantara-secrets.env
```

Test manually:

```bash
set -a; source ~/.zshrc.secrets; set +a
curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d chat_id=8764530025 -d text="test"
```

### "Daemon says 'not on main, fetch-only' but I am on main"

Happens transiently when `git rev-parse --abbrev-ref HEAD` returns empty during
a concurrent operation (another daemon tick, a manual git command, or launchd
race). Safe: next tick will succeed. If persistent, check `.git/HEAD` and fix
manually.

### "Working tree has real changes — fetch-only"

The daemon found files in the working tree that don't match `NOISE_PATTERNS`.
Either:

- Commit/stash them manually, OR
- Add the pattern to `NOISE_PATTERNS` if it's truly auto-generated garbage

### "Diverged from origin/main"

Telegram alerted you. Neither machine nor origin can fast-forward — both sides
have unique commits. You must merge manually. Typical recipe:

```bash
# On the machine that's behind
cd ~/Desktop/nuzantara  # or ~/Projects/nuzantara on Air
git fetch origin
git merge origin/main   # resolve conflicts
git push origin main
```

Then wait 2 minutes; the other machine will FF automatically.

### "Peer fetch keeps timing out"

Peer is offline or on a different network. Not a bug. SSH config defines `air` /
`pro` via mDNS (`Nuzantara-9.local` / `Nuzantara.local`) — works on any LAN with
Bonjour. Check with:

```bash
ssh -o ConnectTimeout=3 air echo ok
```

If it fails, check: both on same WiFi? mDNS resolvable (`ping Nuzantara-9.local`)?
SSH agent loaded?

### "Air disk is full"

Watchdog should catch this and auto-clean. Manual diagnosis:

```bash
ssh air 'df -h /'

# If orphan git temp packs (happens when git gc fails mid-way):
ssh air 'ls -la ~/Projects/nuzantara/.git/objects/pack/tmp_pack_*'
ssh air 'rm -f ~/Projects/nuzantara/.git/objects/pack/tmp_pack_*'

# Other big consumers:
ssh air 'du -sh ~/Library/Application\ Support/* | sort -hr | head -5'
ssh air 'brew cleanup --prune=all'
```

### "I need to stop everything right now"

```bash
launchctl unload ~/Library/LaunchAgents/com.nuzantara.nuz-sync*.plist
touch ~/Desktop/nuzantara/.git/sync-pause
```

### "I want to roll back to the old post-commit hooks"

They're still there, just renamed:

```bash
# Pro
mv ~/Desktop/nuzantara/.git/hooks/post-commit.disabled-nuz-sync-20260411 \
   ~/Desktop/nuzantara/.git/hooks/post-commit

# Air
ssh air 'mv ~/Projects/nuzantara/.git/hooks/post-commit.disabled-nuz-sync-20260411 \
         ~/Projects/nuzantara/.git/hooks/post-commit'
```

Then unload the daemons. Note: the old hooks had the failure modes this system was
built to replace — you probably don't want to roll back.

## Design decisions (and alternatives rejected)

### Why fast-forward only, never merge commits?

Merge commits introduced by an automated daemon become noise in git log and
obscure the real history. If FF isn't possible, human judgment is needed — the
daemon alerts and stops.

### Why no auto-push?

Pushing local commits to origin is irreversible (GitHub sees them, CI runs, other
people may pull them). This is exactly the kind of action that should not be
automated. The daemon's job is to make _incoming_ changes visible, not to expose
_outgoing_ changes. You decide when to push.

### Why Telegram, not email/Slack/macOS notification?

Telegram was already wired up (`TELEGRAM_BOT_TOKEN` exists in both machines'
secrets). Zero new dependencies. Mobile notifications arrive instantly. The bot
(`@balizerobot`) is dedicated to nuzantara alerts.

### Why launchd, not cron?

- launchd survives reboot cleanly (cron does too, but with more ceremony)
- `StartInterval` is wall-clock (runs at boot + every N seconds), cron has the `@reboot` weirdness
- `ThrottleInterval` prevents rapid re-runs if the daemon crashes in a loop
- Better logging integration (`StandardOutPath`, `StandardErrorPath`)

### Why 2 minutes?

- Cache-friendly: doesn't hammer SSH or GitHub API
- Fast enough that you never wait for sync (you'd have to context-switch between
  machines in under 2 min, which is rare)
- Slow enough that intermediate noise (state file writes every minute from
  crons) doesn't trigger constant stash churn

### Why no `main` auto-checkout?

The daemon refuses to touch branches other than the current one. If you're on
`feature/xyz`, it will fetch but not pull main. Doing a silent `git checkout main`
would lose your working state and kill your concentration. You're in control of
which branch you're on.

## Incident log

### 2026-04-11 — initial setup

Issue: Air and Pro diverged by 100+ commits over several weeks. Old `post-commit`
hooks (`git push air` / `git push pro`) had been failing silently:

- `[remote rejected] main -> main (Working directory has unstaged changes)` when peer had dirty tree
- `ssh: connect to host timed out` when peer was suspended
- Log in `~/.openclaw/logs/git-sync.log` grew to 9MB without anyone reading it

Fix: merged `origin/main` into Air main via dedicated test branch, resolved 1
trivial docstring conflict in `apps/mata-garuda/scripts/run_sentinel_py.py`,
pushed 20 commits to origin (3 CELL + 11 mata-garuda/olympus + 5 test coverage +
merges). Pro pulled clean (FF). Old hooks disabled (renamed `.disabled-*`).
This daemon installed.

Collateral: Air disk was at 116MB free (out of 228GB). `git gc --prune=now`
failed mid-way leaving 7.7GB of orphan tmp_pack files. Cleanup via `rm` +
`brew cleanup` + `docker.install` removal recovered to 7.2GB free.

### Adding new incident entries

When you fix something non-trivial, add an entry here with: date, symptom, root
cause, fix. Future-you will thank you.
