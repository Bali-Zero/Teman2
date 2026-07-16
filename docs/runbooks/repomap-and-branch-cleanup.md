# Repomap auto-injection + Branch graveyard cleanup

SOTA L4 — 2026-05-24

Two coupled systems that reduce the per-session "where does X live?" tax in
the 82,970-file / 33-app monorepo and keep the remote branch count from
silently growing past 162:

1. **Repomap** — `~/.nuzantara-repomap.txt` is regenerated every 15 min by
   aider's tree-sitter-backed `--show-repo-map`. Each Claude Code session
   auto-injects the file at SessionStart if it is <30 min stale, giving the
   model a 5–10k-token bird's-eye view (function signatures, class defs,
   exports — no bodies) of `apps/`, `scripts/`, `packages/` before any
   `Read`/`Glob`/`Grep`. Saves ~50 exploratory tool calls per cold session.

2. **Branch graveyard** — `scripts/branch_graveyard_cleanup.sh` enumerates
   `origin/*`, classifies into `merged` / `claude/* zombie` / `stale other`,
   and emits a Markdown report. Weekly cron runs report-only + Telegram
   alert; deletion (only of category 1, merged-safe) is a manual
   `--apply` invocation by Antonello.

---

## File map

| File                                                           | Purpose                                                                                         |
| -------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `scripts/build_repomap.sh`                                     | Generate repomap via aider (fallback: ctags). Output `~/.nuzantara-repomap.txt`.                |
| `scripts/branch_graveyard_cleanup.sh`                          | Classify + report remote branches; optional `--apply` for category 1.                           |
| `infra/launchagents/com.nuzantara.repomap.15min.plist`         | 15-min repomap cron (Pro).                                                                      |
| `infra/launchagents/com.nuzantara.branch-cleanup.weekly.plist` | Weekly Monday 08:00 WITA report (Pro).                                                          |
| `infra/launchagents/install_repomap_cron.sh`                   | One-shot bootstrap: copy plists → `~/Library/LaunchAgents/` + `launchctl bootstrap`.            |
| `infra/launchagents/add_repomap_sessionstart_hook.py`          | Idempotent installer for the `~/.claude/settings.json` SessionStart hook that cats the repomap. |

---

## Usage

### Repomap

Manual generation:

```bash
scripts/build_repomap.sh
# Output -> ~/.nuzantara-repomap.txt (typically 5–10 kB, 270 lines)
# Wall: ~10s on Pro (cold scan first time, then aider tags cache hits)
```

The SessionStart hook (catch-all bucket in `~/.claude/settings.json`) is
the auto-inject path. To install:

```bash
python3 infra/launchagents/add_repomap_sessionstart_hook.py
# Idempotent (marker-string guard). Re-runs are no-ops.
```

Install the cron (15-min refresh):

```bash
bash infra/launchagents/install_repomap_cron.sh
# Copies both plists, bootstraps via launchctl, prints status.
# To remove: bash infra/launchagents/install_repomap_cron.sh --uninstall
```

Verify cron is alive:

```bash
launchctl print "gui/$(id -u)/com.nuzantara.repomap.15min" | grep -E "state|last exit"
tail -f ~/logs/repomap.log
```

### Branch graveyard

Dry-run report:

```bash
scripts/branch_graveyard_cleanup.sh --output /tmp/branch-report.md
# Prints categories to stdout AND writes /tmp/branch-report.md
```

Apply (delete category 1 = merged-safe only — NEVER category 2/3):

```bash
scripts/branch_graveyard_cleanup.sh --apply
# Confirms each `git push origin --delete <branch>`.
# Operator (Antonello) MUST run this manually — the weekly cron is
# report-only.
```

Weekly cron is registered alongside the repomap cron by `install_repomap_cron.sh`.

Verify weekly cron:

```bash
launchctl print "gui/$(id -u)/com.nuzantara.branch-cleanup.weekly" | grep -E "state|cron"
ls -la ~/logs/branch-cleanup-*.md  # daily report files written by cron
```

---

## Environment variables (kill-switches + tuning)

| Variable                                       | Default                         | Effect                                                           |
| ---------------------------------------------- | ------------------------------- | ---------------------------------------------------------------- |
| `REPOMAP_ENABLED`                              | `true`                          | `false` -> `build_repomap.sh` exits 0 (no-op).                   |
| `REPOMAP_MAX_TOKENS`                           | `1024`                          | Token budget passed to aider `--map-tokens`.                     |
| `REPOMAP_OUTPUT`                               | `~/.nuzantara-repomap.txt`      | Output path override (useful for tests).                         |
| `REPOMAP_REPO_ROOT`                            | `/Users/nuzantara/nuzantara`    | Working repo.                                                    |
| `BRANCH_CLEANUP_ENABLED`                       | `true`                          | `false` -> `branch_graveyard_cleanup.sh` exits 0.                |
| `BRANCH_CLEANUP_REMOTE`                        | `origin`                        | Remote to enumerate / push --delete against.                     |
| `BRANCH_CLEANUP_MAIN`                          | `main`                          | Branch used for merge-base ancestor check.                       |
| `BRANCH_CLEANUP_CLAUDE_AGE_DAYS`               | `30`                            | Threshold to flag `claude/*` as zombie.                          |
| `BRANCH_CLEANUP_STALE_AGE_DAYS`                | `90`                            | Threshold for "stale other" category.                            |
| `BRANCH_CLEANUP_TELEGRAM_THRESHOLD`            | `10`                            | Min zombie count to trigger alert.                               |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_CHAT_ID` | from `~/.nuzantara-secrets.env` | Sourced by `--telegram-alert`. Owner chat defaults `1125336968`. |

---

## Troubleshooting

### Repomap is empty or fails

```bash
# Run manually with verbose output
/Users/nuzantara/.pyenv/versions/3.11.11/bin/aider \
    --show-repo-map --map-tokens 1024 --yes --no-pretty --no-stream \
    --no-gui --no-browser --subtree-only 2>&1 | head -50
```

Common causes:

- **Aider tags cache stale**: `rm -rf .aider.tags.cache.v4/` (regenerates in ~25s on first re-run).
- **`--no-gui` missing**: aider v0.86 shim path occasionally tries to launch streamlit GUI. The wrapper forces `--no-gui --no-browser`. If you see streamlit traceback, confirm the script uses `/Users/nuzantara/.pyenv/versions/3.11.11/bin/aider` (preferred over the pyenv shim).
- **Repo too large**: aider can take 10–30s for the initial `--subtree-only` scan on 82k files. Subsequent runs use the on-disk tags cache.

Fallback path: `build_repomap.sh` will switch to `ctags` (universal-ctags via `brew install universal-ctags`) if aider is unavailable. Confirm via the strategy line in stdout:

```
[2026-05-24 19:18:37] [build_repomap] strategy=aider (...)
[2026-05-24 19:18:37] [build_repomap] strategy=ctags (...) — fallback
```

### Branch cleanup report shows fewer branches than expected

`git fetch --prune` (run at the start of `branch_graveyard_cleanup.sh`)
removes any local remote-tracking refs that have been deleted upstream.
If you previously had 162 branches and now see 130, prune removed the
30+ that GitHub had already deleted server-side — that is correct
behavior, not a bug.

### SessionStart hook not firing

```bash
# 1. Confirm hook is in settings.json
python3 -c "import json; d=json.load(open('/Users/nuzantara/.claude/settings.json')); print([h.get('command','')[:60] for e in d['hooks']['SessionStart'] for h in e.get('hooks',[]) if 'repomap-inject' in h.get('command','')])"

# Expected: list of one entry beginning with "# repomap-inject SOTA L4 2026-05-24"

# 2. Manually run the hook body
bash -c 'if [[ -f ~/.nuzantara-repomap.txt ]]; then REPOMAP_AGE_S=$(( $(date +%s) - $(stat -f %m ~/.nuzantara-repomap.txt) )); if (( REPOMAP_AGE_S < 1800 )); then echo "AGE=$REPOMAP_AGE_S"; head -10 ~/.nuzantara-repomap.txt; else echo "STALE: ${REPOMAP_AGE_S}s"; fi; else echo "MISSING"; fi'
```

If `MISSING`: run `scripts/build_repomap.sh` manually or verify the
15-min cron is loaded (`launchctl print` above).

If `STALE: <N>s` where N > 1800: the 15-min cron is not running. Reload:

```bash
launchctl bootout "gui/$(id -u)/com.nuzantara.repomap.15min" 2>/dev/null
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.nuzantara.repomap.15min.plist
launchctl kickstart -k "gui/$(id -u)/com.nuzantara.repomap.15min"
```

---

## Kill-switches (when something goes wrong)

```bash
# Disable repomap generation entirely (cron + manual)
export REPOMAP_ENABLED=false
# Or persistently via plist: edit EnvironmentVariables in
# ~/Library/LaunchAgents/com.nuzantara.repomap.15min.plist (mode 0644).

# Disable branch cleanup
export BRANCH_CLEANUP_ENABLED=false

# Disable SessionStart hook (without removing it from settings.json)
mv ~/.nuzantara-repomap.txt ~/.nuzantara-repomap.txt.disabled
# The hook guards on -f existence; renaming makes it a no-op until restored.

# Full uninstall
bash infra/launchagents/install_repomap_cron.sh --uninstall
```

To revert the SessionStart hook itself: restore the most recent
`~/.claude/settings.json.pre-repomap-hook-*` backup created by the
installer's first run.

---

## Rationale links

- SOTA synthesis brief: `research/operations/2026-05-24-sota-multi-agent-repo-architecture-synthesis.md`
- Cicatrix family (sibling-agent branch swap during long sessions): see
  `.claude/rules/cicatrix-scars.md` 2026-04-29 entry "Untracked files lost
  when sibling automation switches branches mid-session".
- Aider repomap docs: <https://aider.chat/docs/repomap.html>
