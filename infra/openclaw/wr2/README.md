# OpenClaw WR2 wrappers — repo mirror

The actual executable files live OUTSIDE this repo at:
- `~/.openclaw/bin/wr2/wr2-script-wrapper.sh`

This directory is the **versioned mirror** that documents what the
deployed version *should* contain. Changes here SHOULD be reflected
on the deployed copy, and vice versa.

## Why outside the repo?

The OpenClaw runtime installs its binaries under `~/.openclaw/bin/`
during initial setup. LaunchAgent plists reference these absolute
paths because the OpenClaw bin dir is a stable mount point not
tied to any worktree (avoid branch-hijack / nuzantara-deploy pull
race conditions).

## Sync protocol

When a change lands on this repo:

```bash
cp ~/Desktop/nuzantara/infra/openclaw/wr2/wr2-script-wrapper.sh \
   ~/.openclaw/bin/wr2/wr2-script-wrapper.sh
chmod +x ~/.openclaw/bin/wr2/wr2-script-wrapper.sh
```

A pre-push CI gate (TODO Wave 2) will verify:
```bash
diff -q infra/openclaw/wr2/wr2-script-wrapper.sh \
        ~/.openclaw/bin/wr2/wr2-script-wrapper.sh
```

For now, manual sync after merge.

## Current version

`wr2-script-wrapper.sh` includes:
- Source `~/.nuzantara-secrets.env` + `~/.nuzantara-backend-secrets.env`
- Force-override `DATABASE_URL` to `DATABASE_URL_LOCAL` (pg-proxy
  127.0.0.1:15432) — bug discovered 2026-05-06
- pg-proxy sanity check
- Script path resolution + venv-preflight auto-heal (Wave 1 fix
  2026-05-19 — 4-LLM panel synthesis, see
  `research/operations/2026-05-19-wr2-intel-lake-fixes-panel.md`)

## Recent changes

| Date | Change | Reason |
|---|---|---|
| 2026-05-06 | DATABASE_URL_LOCAL override | flycast hostname unreachable from Pro |
| 2026-05-19 | Venv-preflight auto-heal | 84h silent crashloop 2026-05-16→2026-05-19 |
