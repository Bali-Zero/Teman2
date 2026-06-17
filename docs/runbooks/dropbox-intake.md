# Dropbox → Google Drive Intake

Every file that lands in the Bali Zero Dropbox (`data.bayusantero@gmail.com`) is
copied to Google Drive (`antonellosiano@gmail.com`) under `Dropbox-Intake/`,
mirroring the original folder structure.

**Invariant (operator decision 2026-06-12): COPY ONLY.** Dropbox is never
emptied — no `move`, no `sync` (which deletes), no `purge`. Drive accumulates.

## Architecture

```
Dropbox (data.bayusantero@gmail.com)
   │  rclone copy — incremental, idempotent, bwlimit 4M
   │  LaunchAgent com.balizero.dropbox-intake on Pro, every 10 min
   ▼
Drive antonellosiano@gmail.com → Dropbox-Intake/  (mirrored structure)
   ├── Telegram digest when ≥1 new file copied
   └── Telegram alert (1h cooldown) when a run fails or remotes are missing
```

- No state to maintain: `rclone copy` compares src/dst (size+modtime) each run
  and copies only the delta. A missed run self-heals on the next tick.
- A single-instance lock lets long runs (e.g. the first ~527 GiB backfill)
  continue while later cron ticks exit 0.
- State JSON for the sentinel: `~/.agent/decisions/state/dropbox_intake.last.json`.
- Run logs: `~/.cache/dropbox-intake/` (last 100 kept), summary in `latest.log`.

## Components

| Piece       | Repo source                                            | Deployed at (Pro)                  |
| ----------- | ------------------------------------------------------ | ---------------------------------- |
| Sync script | `scripts/dropbox_intake_sync.sh`                       | `~/scripts/dropbox-intake-sync.sh` |
| LaunchAgent | `infra/launchagents/com.balizero.dropbox-intake.plist` | `~/Library/LaunchAgents/`          |
| Installer   | `infra/launchagents/install_dropbox_intake.sh`         | run on Pro                         |

The repo is the source of truth; after editing, re-run the installer on the Pro
(HOME-fork discipline, scar family W50/W51/W52).

## rclone remotes (prereq)

`~/.config/rclone/rclone.conf` on the Pro (must be **0600**) holds two remotes:

- `gdrive` — Google Drive OAuth as antonellosiano@gmail.com (`type = drive`,
  `scope = drive`). Shared with `nuzantara-drive-sync.sh` and the
  `gdrive-*-backup.sh` family.
- `dropbox-bayu` — Dropbox OAuth as data.bayusantero@gmail.com (`type = dropbox`).

### Re-auth (token expired/revoked)

On any machine with a browser (rclone installed):

```bash
rclone authorize "drive"     # login antonellosiano@gmail.com
rclone authorize "dropbox"   # login data.bayusantero@gmail.com
```

Paste the resulting `token = {...}` JSON into the matching section of
`~/.config/rclone/rclone.conf` on the Pro. Never paste tokens into chat
transcripts or commit them.

## Operations

```bash
# Kill switch (set in plist env, then bootout/bootstrap — or just bootout):
launchctl bootout gui/$(id -u)/com.balizero.dropbox-intake

# Manual run (respects the lock):
bash ~/scripts/dropbox-intake-sync.sh

# Status:
cat ~/.agent/decisions/state/dropbox_intake.last.json
tail -20 ~/.cache/dropbox-intake/latest.log
```

Tunables (env): `DROPBOX_INTAKE_ENABLED`, `DROPBOX_INTAKE_SRC`,
`DROPBOX_INTAKE_DST`, `DROPBOX_INTAKE_BWLIMIT` (default `4M` ≈ 32 Mbit/s).

## Troubleshooting

- **"remote not configured" alert** → the rclone config was wiped (it happened
  2026-05-25, silently breaking the Drive mirror + backups for 18 days) or the
  token was revoked → re-auth as above.
- **Run fails with Drive upload-limit** → `--drive-stop-on-upload-limit` halted
  at Google's 750 GB/day cap; the next tick resumes where it left off.
- **No digest but files were added** → check `latest.log`; the digest fires only
  at the END of a run — during the initial backfill that can be a day+.
