# Production CRM Smoke Runbook

This runbook is intentionally non-secret. It documents where the shared smoke
credential lives and how to run the repeatable CRM/admin smoke without printing
passwords, tokens, or cookies.

## Credential Locator

Use MOS/project memory to find the current locator:

```bash
mem query "nuzantara-prod-smoke-login"
```

Current shared per-user env file path on Air-M5, Pro, and Mini:

```bash
~/.local/share/nuzantara/secrets/prod-smoke-login.env
```

Load it only into the shell that runs the smoke:

```bash
set -a
source ~/.local/share/nuzantara/secrets/prod-smoke-login.env
set +a
```

The env file must stay outside the repo, mode `600`, and must never be
committed, pasted into chat, or echoed in logs. Do not run `cat` on it in a
shared transcript. On Air-M5 only, Keychain also has service
`nuzantara-prod-smoke-login` for account `zero@balizero.com`; prefer the env
file for cross-session automation.

The Pro browser storage state cache is:

```bash
~/.local/state/nuzantara/prod-smoke-storage-state.json
```

It is also secret-adjacent because it contains session cookies. Keep it outside
the repo and mode `600`.

## Repeatable Live Smoke

Run browser work on Pro, not Air-M5:

```bash
ssh pro 'bash -lc "
cd ~/Desktop/nuzantara &&
set -a &&
source ~/.local/share/nuzantara/secrets/prod-smoke-login.env &&
set +a &&
node scripts/prod_crm_smoke.cjs \
  --base-url https://kita.balizero.com \
  --client-id 11671 \
  --service-code visa_bridging \
  --report-json /tmp/prod-crm-smoke.json
"'
```

The script performs:

- login or reuse of the saved browser storage state;
- `admin/team-activity` overview and team-stats checks;
- `team/my-status` check;
- process creation on the test client;
- status flow through `waiting_documents`, `sending_invoice`, `on_process`,
  and `completed`;
- cleanup via delete/cancel;
- JSON report with console/request failures and stale-read observations.

The script does not print the password, token, or cookies.

## Fly Log Monitoring

Snapshot:

```bash
ssh pro 'bash -lc "
cd ~/Desktop/nuzantara &&
bash scripts/fly_permission_log_monitor.sh --snapshot
"'
```

Long stream, for example 24 hours:

```bash
ssh pro 'bash -lc "
cd ~/Desktop/nuzantara &&
bash scripts/fly_permission_log_monitor.sh \
  --duration-seconds 86400 \
  --output /tmp/nuzantara-rag-permission-monitor.log
"'
```

Default match pattern:

```text
permission denied|insufficient privilege|team-activity|admin/team|practices
```

## Stale Read Interpretation

The smoke records `stale_read_observed` when the immediate GET after PATCH does
not yet show the target status. If the retry loop converges, treat it as
read-after-write lag or browser/API caching to investigate, not as a failed user
workflow. If it does not converge within the retry window, treat it as a real CRM
state bug.

## Failed Smoke Cleanup

If the script fails after creating a process, inspect `/tmp/prod-crm-smoke.json`
on Pro for `practice.id`. Delete/cancel that process via the CRM API or UI before
rerunning. Do not leave smoke processes active.
