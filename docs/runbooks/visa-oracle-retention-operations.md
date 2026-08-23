# Visa Oracle retention operations

Status: repository-ready, **not installed or armed**. Last verified 2026-08-07.

This runbook closes the scheduler/observability side of retention without
creating a second retention service. The database policy and bounded one-shot
worker remain authoritative. The existing `scripts/cron-wrapper.sh` supplies
non-overlap, timeout, heartbeat and P0 failure notification. This job sets its
retry count to zero: backlog/lag exit `2` must page immediately instead of
being retried until it disappears; the next bounded attempt is the next
15-minute tick.

## Current gate

| Control                                  | Repository state                                                                                                                    | Production state     |
| ---------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | -------------------- |
| Policy-bound decision/idempotency worker | DONE in Linea A; dry-run default                                                                                                    | Not yet armed        |
| 15-minute one-shot manifest              | DONE as `.plist.example`                                                                                                            | Not installed/loaded |
| Non-overlap                              | DONE via existing PID lock in `cron-wrapper.sh`                                                                                     | Not yet observed     |
| Nonzero/backlog/lag alert                | DONE: worker exit `2` flows to existing `tg_notify.py` P0 path                                                                      | Not yet observed     |
| Missed-run evidence                      | DONE: Cell watches the wrapper heartbeat at 30m warning / 60m critical                                                              | Not yet observed     |
| Analytics destination                    | UNKNOWN: `NEXT_PUBLIC_ANALYTICS_ENDPOINT` does not identify a provider/dataset                                                      | Blocker              |
| PII-free telemetry TTL                   | Separate fail-closed preflight requires a fresh operator attestation for exactly 365 days (12 months, DPIA V2 §A ruling 2026-08-20) | Blocker              |

The scheduler manifest remains dry-run because it has not been staged or
approved. Analytics TTL is a separate product ENFORCE gate: it must never
block a due decision/idempotency purge, because that would retain personal
data beyond the approved policy.

The dedicated retention login needs `SELECT` only on the non-PII
`visa_decision_retention_policies` authority plus EXECUTE on the bounded
purge/evidence functions. Any other governed-table privilege fails the
read-only operational preflight, including PostgreSQL 17 `MAINTAIN`.

## Files and boundaries

- `infra/launchagents/com.nuzantara.visa-oracle-retention.15min.plist.example`
  is a one-shot 900-second schedule with `KeepAlive=false` and apply disabled.
- `infra/launchagents/wrappers/visa-oracle-retention-run.sh` invokes the real
  backend worker. It does not implement deletion, locking or notification.
- `scripts/visa_oracle_analytics_retention_preflight.py` validates the closed
  shape and freshness of a PII-free operator attestation. It is not invoked by
  the purge payload.
- `apps/cell/cell/sensors/cron_sensor.py` watches
  `~/.agent/decisions/state/visa_oracle_retention.last.json`.

No file stores a DSN, answer, nationality, passport, family fact, request,
response, user/session identifier or raw analytics payload.

## Evidence contract for analytics TTL

The product analytics owner must identify the real destination first. Copy
`infra/launchagents/visa-oracle-analytics-retention-attestation.example.json`
to `~/.config/nuzantara/visa-oracle-analytics-retention-attestation.json`, then
fill it only from a provider read-only policy export and a synthetic probe.
This JSON is an evidence contract/operator attestation, not direct provider
proof; the independent grader must reproduce the export and probe.

Required proof:

- the destination identifier is SHA-256 hashed;
- event scope is exactly `visa_oracle_v2_*`;
- automatic TTL is exactly 365 days (12 months, DPIA V2 §A ruling 2026-08-20);
- a hashed ingestion receipt proves the expired synthetic event was present;
- that same synthetic event is absent after the TTL;
- an unexpired synthetic control remains present;
- no production row was manually deleted;
- the provider export is hashed and the observation is no older than 7 days.

The evidence file must contain no event bodies or user fields. The preflight
rejects duplicate JSON keys and every field outside the exact closed schema.

Verify locally without modifying any dataset:

```bash
cd /Users/nuzantara/nuzantara
python3 scripts/visa_oracle_analytics_retention_preflight.py \
  --attestation "$HOME/.config/nuzantara/visa-oracle-analytics-retention-attestation.json"
```

Exit `0` means the evidence shape, TTL, scope and freshness pass. Exit `2`
keeps apply/ENFORCE blocked. It is not permission to turn on telemetry: the
independent grader must reproduce the provider read-only export/probe.

## Staged activation ceremony

Do not perform these steps in production until migrations, roles, policy,
DPIA and independent review are green.

1. Copy the example plist to a staging LaunchAgents directory; keep
   `VISA_ORACLE_RETENTION_APPLY=false`.
2. Validate with `plutil -lint`; do not load it from a development worktree.
3. Seed the monitored heartbeat by running the complete staging command once
   through `scripts/cron-wrapper.sh visa-oracle-retention ...`; do not invoke
   only the inner payload. It must emit only aggregate counts and lag.
4. Load the staging job through the normal LaunchAgent installation/reconcile
   workflow. Confirm a heartbeat within 15 minutes.
5. Prove the Cell state changes to warning after 30 minutes and critical after
   60 minutes when the job is deliberately disabled in staging.
6. Prove a controlled worker exit `2` reaches the existing notification
   gateway with aggregate evidence only.
7. Install the fresh analytics evidence. Repeat the preflight independently.
8. Independently approve `VISA_ORACLE_RETENTION_APPLY=true` in staging after
   the database retention gates are green. The decision/idempotency purge must
   continue even if the separate analytics attestation becomes stale.

Production installation/loading and `VISA_ORACLE_RETENTION_APPLY=true` require
a separate approved change window. This repository task performs neither.

## PII-free operational evidence

Expected local evidence is limited to:

- job name, host, timestamp, duration, exit status and attempts;
- aggregate deleted/remaining counts;
- aggregate held-expired count and maximum lag seconds;
- hashed destination/export identifiers and policy observation timestamp.

Any raw payload or applicant identifier in the heartbeat, JSONL, log or alert
is a BLOCKER. Disable the job and leave Visa Oracle in SHADOW.
