# scripts/mini/

Scripts that run **only on Mini-Pro2** (the M4 24GB server-mode workstation
acting as Pro's "natural extension" since 2026-05-05 when Air was
decommissioned).

Repo-tracked so any change ships to Mini via the next git-pull tick.

## mini-git-pull.sh

Periodic (5 min) `git pull --ff-only origin main` for `~/Desktop/nuzantara`
on Mini.

### Hardening (2026-05-06 incident)

The naive `git stash --include-untracked` + `git pull --ff-only` pattern
broke when origin/main carried a tracked symlink at a path that Mini had
materialized as a real directory (`apps/backend-rag/.venv`, 762 MB).

`stash --include-untracked` would attempt to stash the entire dir, hang
or fail silently, and the pull would never apply. The 5-min cron
re-tried 8+ times in 2.5 hours with zero progress.

The hardened version detects this class of incident before stashing and
refuses with a Telegram alert, requiring human triage (typically
`mv path path.aside-YYYY-MM-DD` on Mini before retry).

### Behavior

| Condition | Action |
|---|---|
| Branch not `main` | Skip silently |
| Up-to-date | Skip silently (no log spam) |
| HEAD diverged from `origin/main` | Telegram alert + exit 1 |
| Tracked symlink ↔ local dir/file mismatch | Telegram alert + exit 1 |
| Stash list > 5 entries (sign of repeated pop conflict) | Telegram alert (warning, continue) |
| Tracked dirty files only | Stash → pull → pop |
| Untracked files | Left alone (ff-only doesn't touch them) |
| Stash pop conflict after pull | Telegram alert, stash retained, exit 0 (pull succeeded) |

### Telegram alerts (per-key cooldown)

Each alert key has a 1-hour cooldown to avoid notification storms when
the same condition persists across many cron ticks.

Alert keys: `type-mismatch`, `diverged`, `stash-bloat`, `stash-failed`,
`pull-failed`, `stash-pop-conflict`. State stored at
`~/.agent/decisions/state/mini-git-pull-alert-<key>.ts`.

Requires `$TELEGRAM_BOT_TOKEN` in `~/.nuzantara-secrets.env`. Falls back
to `chat_id=1125336968` (Zero) if `$TELEGRAM_OWNER_CHAT_ID` is unset.

### Deployment

LaunchAgent `~/Library/LaunchAgents/com.nuzantara.git-pull-main.5min.plist`
should invoke this script via:

```xml
<key>ProgramArguments</key>
<array>
  <string>/bin/bash</string>
  <string>-lc</string>
  <string>/Users/nuzantara/Desktop/nuzantara/scripts/mini/mini-git-pull.sh</string>
</array>
```

After updating the plist, run on Mini:

```bash
launchctl bootout gui/$(id -u)/com.nuzantara.git-pull-main.5min
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.nuzantara.git-pull-main.5min.plist
```

## Mini-local exclusions

Add Mini-local untracked detritus to `.git/info/exclude` (per-checkout,
not committed):

```
apps/backend-rag/.venv.mini-aside-*
*.mini-aside-*
```

These are aside-directories created by the operator after a type-mismatch
incident — they should not appear in git status output.
