# Subhi memory mirror — operator notes

## What it does

Daily filter+copy of Antonello's `~/.claude/projects/-Users-nuzantara/memory/`
to the local staging directory
`~/Desktop/subhi_TUTOR_KIT/staging/.claude/memory-mirror/` on Pro.

Filter rules live in `subhi-memory-mirror.config.yaml` (declarative —
edit the YAML, not the script, to change behaviour).

Per addendum B (option B):

- This script does **not** push to git.
- Distribution to Subhi's MacBook happens via a separate rsync-over-
  Tailscale step (T3, separate task / LaunchAgent).
- No second GitHub repo. No PAT for memory mirror. The memory dump
  never leaves Antonello's machine until rsync ships the filtered
  staging dir to Subhi via the tailnet.

## Files

- `subhi-memory-mirror.config.yaml` — declarative filter rules.
- `subhi-memory-mirror.py` — Python implementation (canonical).
- `subhi-memory-mirror.sh` — bash wrapper around the Python script
  (LaunchAgent compatibility, stable entry point).
- `test_mirror.sh` — TDD harness (11 assertions).
- `README.md` — this file.

## Schedule

Pro LaunchAgent (created in T3, not this task) runs the wrapper at
04:00 WITA daily. The wrapper exits with status 0 on success; the
LaunchAgent's `StandardOutPath` / `StandardErrorPath` should point to
`~/logs/subhi-memory-mirror.{out,err}.log`.

## Manual run

```bash
# Dry-run on a throwaway directory (recommended before first real run)
DRY_RUN=1 \
  CONFIG_OVERRIDE_DEST_DIR=/tmp/subhi-mirror-real-test \
  bash scripts/subhi/subhi-memory-mirror.sh

cat /tmp/subhi-mirror-real-test/_AUDIT.txt | head -50

# Real run — writes to the configured staging dir
bash scripts/subhi/subhi-memory-mirror.sh
```

`DRY_RUN=1` is informational under option B (there is no git step
to skip); the env var is preserved for parity with older docs that
referenced it.

## Test

```bash
bash scripts/subhi/test_mirror.sh
```

11 assertions covering:

1. Safe markdown files are mirrored as-is.
2. The `Subhi/` directory is fully blocked.
3. Files inside `Subhi/` (e.g. `Subhi/private.md`) are blocked.
4. `discovery_token_*.md` files are blocked.
5. Files containing fake `sk-ant-*` tokens are still mirrored…
6. …with the token replaced by `[REDACTED-secret]`.
7. The raw token does not appear in the mirrored copy.
8. `MEMORY.md` is mirrored.
9. `MEMORY.md` no longer references the `Subhi/` path.
10. `MEMORY.md` no longer references `discovery_token_` files.
11. `_AUDIT.txt` is generated and contains an `Excluded:` section.

## Troubleshooting

| Symptom                                              | Fix                                                                                                                |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `_AUDIT.txt` shows `Included: 0`                     | Check `source_dir` in YAML; verify path exists and contains `*.md` files.                                          |
| `_AUDIT.txt` shows 0 excluded                        | YAML syntax error — `python3 -c "import yaml; yaml.safe_load(open('scripts/subhi/subhi-memory-mirror.config.yaml'))"` |
| `Subhi/` folder leaked                               | Verify `Subhi/**` and `Subhi` in `exclude_patterns`.                                                               |
| Secret regex didn't match                            | Add the regex (raw, no surrounding quotes) under `content_redact_regex`. Re-run dry-run to confirm.                |
| `python3 not found in PATH`                          | LaunchAgent has no PATH — set `EnvironmentVariables.PATH=/opt/homebrew/bin:/usr/bin:/bin` in the plist.            |
| `Permission denied` writing to `~/logs/...`          | The Python script falls back to stderr if the log file can't be opened; check `~/logs/` ownership.                 |
| Subhi-specific files still appear in dest            | The plan exclude list does not cover `subhi-task-routing.md`, `subhi-rbac-permissions.md`, etc. by default.        |

### What the script does NOT do

- It does not rsync to Subhi's Mac. That's a separate script (T3).
- It does not push to GitHub. Per addendum B, there is no separate
  repo; the staging dir is the canonical local artifact.
- It does not encrypt the staging dir. Tailscale provides transport-
  level encryption when the rsync ships it.
- It does not version-control the staging dir. Recreate from source
  on each run (the script overwrites every included file).

## First-run safety checklist

1. Run dry-run with `DRY_RUN=1 CONFIG_OVERRIDE_DEST_DIR=/tmp/subhi-mirror-real-test`.
2. Inspect `_AUDIT.txt`:
   - `Included` should be ~200.
   - `Excluded` should include all 21 files under `Subhi/`, plus
     `MEMORY_ARCHIVE.md`, `discovery_token_*.md`,
     `reference_subhi_folder.md`, `feedback_subhi_*.md`,
     `archive/**`, and `MEMORY.md.pre-*`.
   - `Redacted` count should be small (typically <20).
3. Spot-check a redacted file: open one of the files in the
   `=== Redacted files ===` list and grep for `REDACTED-secret`
   — it should appear, and no raw `sk-ant-`, `ghp_`, etc. should remain.
4. Verify `MEMORY.md` in the dest does NOT contain the strings
   `Subhi/`, `reference_subhi_folder`, or `discovery_token_`.
5. Only after manual review, allow the LaunchAgent / rsync to run.

## Reference

- Spec: `docs/superpowers/specs/2026-05-04-subhi-tutor-design.md`
- Addendum: `docs/superpowers/specs/2026-05-04-subhi-tutor-design-addendum-B.md`
- Plan: `docs/superpowers/plans/2026-05-04-subhi-tutor-implementation.md`
  (T1 + T2)
