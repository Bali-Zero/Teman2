# PR-E1 — Cleanup: /tmp logs → ~/logs/cron-tmp/, NLM CLI arg drift (2026-04-30)

Phase E (cleanup) of the Pro automations renaissance. Two unrelated
classes of fix, bundled because both fall under "things-that-rot-on-Pro":

1. **/tmp/cron-\*.log persistence** — 29 cron lines on Pro logged to
   `/tmp/`, which is volatile across reboots and macOS sweeps. Audit
   trails and Sentinel both depend on log persistence.
2. **NLM CLI arg drift** — the `nlm` CLI shipped a breaking change:
   `nlm source add` dropped `--notebook` (NOTEBOOK_ID is now positional),
   and `nlm studio create infographic|mind-map` was promoted to top-level
   `nlm infographic create` / `nlm mindmap create`. Two repo scripts still
   used the old syntax and were silently failing every cron firing.

## Targets

### Part 1 — log path rewrite (29 cron lines)

| Old destination            | New destination                       |
| -------------------------- | ------------------------------------- |
| `/tmp/cron-<NAME>.log`     | `~/logs/cron-tmp/<NAME>.log`          |
| `/tmp/legal_radar.log`     | `~/logs/cron-tmp/legal_radar.log`     |
| `/tmp/openclaw-bridge.log` | `~/logs/cron-tmp/openclaw-bridge.log` |

Applied via `scripts/ops/pr-e1-cleanup-tmp-logs.sh`: idempotent
crontab rewrite via awk (in-place pattern match, never delete/add
lines, only rewrite paths). Sanity gates: line count must be
unchanged after the rewrite, and zero `/tmp/cron-` /
`/tmp/legal_radar.log` / `/tmp/openclaw-bridge.log` references must
remain.

The script also `mkdir -p ~/logs/cron-tmp/` before installing the
new crontab, so the next cron firing doesn't fail with "no such
directory".

### Part 2 — NLM CLI arg drift fixes (2 repo files)

#### `yt_monitor.py:214` — source add

**Before:**

```python
["nlm", "source", "add", "--notebook", notebook_id, "--url", video_url]
```

`nlm source add` errored with `No such option: --notebook` for every
YT video found, blocking ingestion entirely. The cron run still
"succeeded" because the outer wrapper logs `complete: 180 polled,
9 relevant, 0 ingested` — but the `0 ingested` was a silent failure.

**After:**

```python
["nlm", "source", "add", notebook_id, "--youtube", video_url]
```

`NOTEBOOK_ID` is now positional. `--youtube` is the YT-specific URL
option (more semantically accurate than the old `--url`).

#### `multimodal_pipeline.py:_run_nlm_create` — studio create rename

**Before:**

```python
elif artifact_type == "infographic":
    cmd = [NLM_CLI, "studio", "create", "infographic", notebook_id, "--confirm"]
elif artifact_type == "mind-map":
    cmd = [NLM_CLI, "studio", "create", "mind-map", notebook_id, "--confirm"]
```

`nlm studio` no longer has a `create` subcommand — only
`status/delete/rename`. Every multimodal cron run errored with
`No such command 'create'. Did you mean 'rename'?`

**After:**

```python
elif artifact_type == "infographic":
    cmd = [NLM_CLI, "infographic", "create", notebook_id, "--confirm"]
elif artifact_type == "mind-map":
    cmd = [NLM_CLI, "mindmap", "create", notebook_id, "--confirm"]
```

`infographic` and `mindmap` are now top-level `nlm` subcommands with
their own `create NOTEBOOK_ID --confirm` shape. `audio create` and
`report create` did NOT change shape — left untouched.

## Live operation on Pro (2026-04-29 18:15 UTC = 2026-04-30 02:15 WITA)

```
[2026-04-29T18:15:51Z] line count unchanged: 243
[2026-04-29T18:15:51Z] no /tmp/ residual paths after rewrite.
[2026-04-29T18:15:51Z] crontab installed.
[2026-04-29T18:15:51Z] post-install verified.
[2026-04-29T18:15:51Z] PR-E1 applied. Backup: /Users/nuzantara/.crontab.backups/20260429T181551Z.cron
[2026-04-29T18:15:51Z] New log dir: /Users/nuzantara/logs/cron-tmp (created).
```

Re-run reported `no-op: crontab already matches PR-E1 target state`.

The Python edits (`yt_monitor.py`, `multimodal_pipeline.py`) will
land on Pro through the standard post-commit sync hook
(Air → Pro → GitHub). py_compile validated locally before commit.

## Rollback

```bash
# Crontab rewrite
ssh pro 'crontab "$HOME/.crontab.backups/20260429T181551Z.cron"'

# Python edits
git revert <commit-sha>
```

## Test plan

- [x] Pre-flight: dry-run awk on snapshot of Pro crontab — 29 entries
      rewritten, 0 residuals
- [x] Live apply on Pro
- [x] Idempotence verified
- [x] `~/logs/cron-tmp/` directory created
- [x] py_compile both Python edits
- [ ] (Post-merge, next cron firings):
  - `~/logs/cron-tmp/yt-monitor.log` should fill with new
    `Ingested <url> into <notebook>` lines instead of
    `No such option: --notebook`
  - `~/logs/cron-tmp/multimodal.log` should fill with successful
    `infographic`/`mindmap` creates instead of
    `No such command 'create'. Did you mean 'rename'?`
- [ ] (Reboot test, eventual) Logs in `~/logs/cron-tmp/` survive
      reboot whereas `/tmp/` would have been wiped

## Out of scope (deliberately deferred)

- 2 cron lines still log to `/tmp/openclaw-bridge.log` and
  `/tmp/legal_radar.log` were rewritten in this PR. Other 4 stragglers
  (`/tmp/cron-drive-poll.log` is in a `# DISABLED` line, so ignored;
  the cache-cleanup chained 4 redirects to the same /tmp file — all 4
  rewritten correctly thanks to awk `while (match)`).
- Whether `nlm source add --youtube` produces the same Drive folder
  outcome as the old `--url` for YT videos — to be verified next 6h
  cycle.

## Related

- Plan: `~/.claude/plans/RESUME-renaissance-2026-04-29.md` (PR-E1 row)
- Audit SSOT:
  `research/ops/2026-04-29-pro-automations-audit/automations-audit-2026-04-29.csv`
- Predecessors: PR #367 (PR-C5), #368 (PR-C3), #369 (PR-C4)
