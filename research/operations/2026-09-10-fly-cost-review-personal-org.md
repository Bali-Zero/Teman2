---
date: 2026-09-10
domain: operations
client_case: none — Fly.io cost review of org `personal` (nuzantara-rag, nuzantara-postgres); no client data touched, no PII in any measurement
adversarial_review: codex
sources:
  - https://fly.io/docs/about/pricing/ (fetched 2026-09-10 — shared-cpu-1x 512MB $3.32 / 1GB $5.92, shared-cpu-2x 2GB $11.83 / 4GB $22.22, volumes $0.15/GB/mo, stopped rootfs $0.15/GB/mo, dedicated IPv4 $2/mo)
  - https://fly.io/docs/volumes/volume-manage/ ("you can extend (increase) a volume's size, but you can't make a volume smaller")
  - fly-apps/postgres-flex `internal/flypg/zombie.go` + `node.go` at main, read via `gh api` 2026-09-10 (quorum + Quarantine)
  - Fly Prometheus `https://api.fly.io/prometheus/personal/api/v1/query` (header `Authorization: FlyV1 <token>`), 2026-09-09 16:00-16:50Z
  - `fly machine list / volumes list / ips list / checks list / image show / logs` on both apps, 2026-09-09 16:00-16:20Z
  - `psql` on the Postgres nodes via `fly ssh console` (pg_database, pg_stat_user_tables, pg_stat_activity with literals stripped, pg_indexes), 2026-09-09 16:10-16:25Z
  - `gh run list / gh run view --json jobs / --log` for the last 40 `fly-deploy.yml` runs (2026-09-01 → 2026-09-09)
  - Pro: `crontab -l`, `~/Library/LaunchAgents/com.balizero.wa-mirror-auto-promote.plist`, `~/logs/fly-backup-2026090[23].log`, `~/logs/wa-mirror-auto-promote.out.log` (JSON summaries only)
---

# Fly.io cost review — org `personal` (nuzantara-rag, nuzantara-postgres) — 2026-09-10

> Session: Fable 5.1 on Pro, owner mandate 2026-09-10 (autonomous L2, read-only on Fly). Every
> number below was measured in-session; nothing is carried over from the 2026-09-09 M5 estimate
> except as a cross-check. Corrections from the adversarial review (last section) are applied
> in place and marked `[AR-n]`.

## 1. Footprint and cost, before / after the proposed cuts

| App / machine                         | Size                            | State   | $/mo now                             | Proposal                                                                                    | $/mo after      | Δ                          |
| ------------------------------------- | ------------------------------- | ------- | ------------------------------------ | ------------------------------------------------------------------------------------------- | --------------- | -------------------------- |
| rag · `api` 7817d92c4117d8            | shared-cpu-2x 3 GB + 1 GB vol   | 24/7    | ≈ 17.2 (3 GB interpolated 2↔4 GB)    | keep (mandate) — 30d peak 1350 MB                                                           | 17.2            | 0                          |
| rag · `rag` 1781e5eda03438            | shared-cpu-2x 2 GB + 1 GB vol   | 24/7    | 12.0                                 | **keep 2 GB** — 7d peak 939 MB, 30d peak 1128 MB, avg 849 MB (owner's 700 MB gate not met)  | 12.0            | 0                          |
| rag · `drive` 2874974fe6e158          | shared-cpu-1x 1 GB              | 24/7    | 5.9                                  | **not now** — 512 MB ($3.32) is feasible on the numbers but the worker crashed today `[AR-31]` | 5.9 (3.3 later) | 0 (−2.6 later)             |
| rag · `drive` standby 48ee717b736948  | shared-cpu-1x 1 GB              | stopped | rootfs only, size not measured `[AR-10]` | keep (Fly standby, wakes only on host loss)                                             | same            | 0                          |
| pg · primary 0801696b541568           | shared-cpu-2x 2 GB + 25 GB vol  | 24/7    | 15.6                                 | volume 25→10 GB after the sweep (owner, §2)                                                 | 13.3            | −2.25                      |
| pg · replica 5683e090f3d228           | shared-cpu-2x 2 GB + 25 GB vol  | 24/7    | 15.6                                 | volume 25→10 GB (owner)                                                                     | 13.3            | −2.25                      |
| pg · replica 78113d4f67d938           | shared-cpu-2x 2 GB + 25 GB vol  | 24/7    | 15.6                                 | **owner decision** (§3): keep at 10 GB → 13.3 (−2.25); remove → 0 (−15.6) `[AR-13]`         | 13.3 or 0       | −2.25 or −15.6             |
| **Total (excl. standby rootfs)**      |                                 |         | **≈ 82**                             |                                                                                             | **≈ 59 … 72**   | **−9.4 … −22.7** `[AR-11]` |

Plan that meets the ≥ $20/mo criterion: Postgres 3→2 nodes **and** 25→10 GB volumes on the two
survivors (−$20.1/mo) — with the availability cost in §3. Plan that keeps HA intact: 3 nodes at
10 GB (−$6.75) plus, once the drive crash is explained, drive 512 MB (−$2.6). The CPU cure in §4
has no invoice line; it removes the pressure to buy CPU for the primary (price of a performance
tier not measured here `[AR-14]`).

## 2. Postgres disks (item 1)

| Node         | `df /data`        | Of which stale dumps                                                | Real use     |
| ------------ | ----------------- | ------------------------------------------------------------------- | ------------ |
| primary      | 11 G / 25 G (45%) | 6.6 GB — 18 × `nuz-backup-*.sql.gz` (2026-06-06 … 08-29) + `.err`   | 4.4 GB (18%) |
| replica 5683 | 3.8 G (17%)       | —                                                                   | 15%          |
| replica 7811 | 3.7 G (16%)       | —                                                                   | 15%          |

`\l+`: `nuzantara_rag` 3370 MB, everything else < 20 MB; `pg_wal` 497 MB. Growth 2749 MB
(2026-07-26, from the backup script's own note) → 3370 MB (2026-09-10) ≈ 0.4 GB/month, of which
`api_audit_trail` is 979 MB / 4.2 M rows (no retention). The stale dumps are retry leftovers of
runs killed before their own cleanup (backup script step 1c). PR #6045 adds a pre-run sweep of
`/data/nuz-backup-*` older than one day **on the database's own disk only** — it never touches
the local (`~/backups/fly-postgres`, keep 7) or Tigris (keep 30) copies, which are the backup
tiers; the June/July files on `/data` are past both windows by design `[AR-2]`. Unarmed: the
one-shot delete is the owner's call.

**Volume resize.** Fly volumes cannot shrink. Procedure, replica by replica, never the primary
first, old volume kept as physical rollback until the new node is proven `[AR-1, AR-3]`:

```
fly volumes create pg_data -s 10 -r sin -a nuzantara-postgres            # new, smaller
fly machine clone <replica-id> --attach-volume <new-vol-id>:/data -r sin -a nuzantara-postgres
# prove the new node BEFORE touching the old one:
fly checks list -a nuzantara-postgres                     # new node: pg 3/3, role=replica
fly ssh console -a nuzantara-postgres --machine <new> -C "psql -U postgres -h /run/postgresql -p 5433 -Atc 'SELECT pg_is_in_recovery()'"          # t
fly ssh console -a nuzantara-postgres --machine <primary> -C "psql -U postgres -h /run/postgresql -p 5433 -Atc 'SELECT application_name, state, replay_lag FROM pg_stat_replication'"   # new node streaming, lag ~0
fly ssh console -a nuzantara-postgres --machine <new> -C "repmgr -f /data/repmgr.conf cluster show"   # all members, no stale row
fly machine stop <old-replica-id> -a nuzantara-postgres    # stop, do NOT destroy yet
# observe ≥ 24 h + one verified nightly backup, then:
fly machine destroy <old-replica-id> -a nuzantara-postgres
fly volumes destroy <old-vol-id> -a nuzantara-postgres
# repeat for the second replica; then move the primary:
fly postgres failover -a nuzantara-postgres   # needs 3 healthy nodes → promotes a 10 GB replica
# the old primary is now a replica: replace it the same way
```

Headroom at 0.4 GB/month before Fly's 90 % read-only threshold: 10 GB → 4.6 GB free ≈ **11
months**; 15 GB → 9.1 GB free ≈ **23 months** `[AR-8, AR-9]`. Both ignore WAL bursts and bloat;
the `api_audit_trail` retention decision moves either number.

## 3. Topology 3 → 2 nodes (item 2) — owner decision

postgres-flex fences a primary by quorum: `quorum = totalMembers/2 + 1`; `totalActive < quorum →
ErrZombieDiagnosisUndecided → Quarantine` (read-only lock) — `internal/flypg/zombie.go` +
`node.go`, main, 2026-09-10. With two members quorum is 2, so **any** single-node absence
leaves the surviving node at 1 < 2.

| Nodes   | Quorum | Lose one replica                                                          | Lose the primary                                                                                             | `fly pg failover`         | Cost Δ                            |
| ------- | ------ | ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------- | --------------------------------- |
| 3 (now) | 2      | fine, 2/3 active                                                          | repmgr promotes a replica; the new primary sees 2/3 active                                                   | works (needs ≥ 3)         | 0                                 |
| 2       | 2      | **primary goes read-only** until the replica is back                      | **write outage too**: the promoted standby sees 1 < 2 and quarantines itself `[AR-4]`                        | **refused** (< 3 servers) | −$15.6 (−$20.1 with 10 GB volumes) |
| 1       | —      | n/a                                                                       | outage; restore from the nightly Tigris dump — RPO ≤ 24 h **only if** a restore test proves it `[AR-33]`      | n/a                       | −$31.2                            |

So 2 nodes is not "one failure domain": it is **no automatic recovery** — every single-node
event (host, deploy, image update, volume, network) becomes a write outage until an operator
intervenes or the node returns. No SLA for that return is documented `[AR-7]`. The split-brain
wording used earlier was wrong: the fencing makes it an availability loss, not a divergence
`[AR-6]`. Removing the third member also needs its own procedure — `fly machine destroy`, then
`repmgr cluster show` on the primary and `repmgr primary unregister --node-id <id>` if a stale
row remains, then confirm `totalMembers` = 2 in the flypg logs `[AR-5]`. Recommendation: stay at
3 nodes and take the volume cut; go to 2 only as an explicit trade of HA for $15.6/mo.

## 4. The "1 critical" check on the primary (item 3) — diagnosis + cure

`fly checks list`: `vm` critical on the primary only — `[✗] cpu: system spent 2.21s of the last
10 seconds waiting on cpu`; `pg` and `role` passing. Not a health-check configuration fault, not
a data-integrity fault: **CPU quota throttling** of the shared-cpu-2x primary `[AR-18]`.

| Metric (Fly Prometheus, 2026-09-10)          | primary                                          | replica 5683 | replica 7811 |
| -------------------------------------------- | ------------------------------------------------ | ------------ | ------------ |
| `fly_instance_cpu_balance` (burst credits)   | **234** (7d min 1)                               | 100000       | 99993        |
| `fly_instance_cpu_throttle` rate, 24h        | **87.7**                                         | 0            | 0            |
| steal rate, 24h                              | 43.7                                             | 0.05         | 1.2          |
| `top` on the node (one sample)               | **82% st**, load 3.0 on 2 vCPU, PSI some avg10 52% | —            | PSI 1%       |

Dominant load, measured on the node with **60-second deltas**, not lifetime counters `[AR-15,
AR-16]`: `pg_stat_user_tables` for `clients` (12 218 rows, 50 MB) went from 2 540 682 to
2 540 720 seq scans in 60 s (**0.63 scans/s**, 7 738 tuples/s), lifetime 2.54 M scans / 30.6 G
tuples; `pg_stat_activity` sampled 6× at 1 s (literals stripped) showed the same statement
active in 5 of 6 samples: `UPSERT_MATCH_SQL` in `backend/app/routers/crm_clients.py` — three
`CASE … regexp_replace(...)` expressions in the WHERE, so no index on `phone`,
`phone_normalized`, `whatsapp` can serve it (`pg_indexes` lists 37 indexes on the table, none
on those expressions). Caller: launchd `com.balizero.wa-mirror-auto-promote` on Pro
(`StartInterval` 300 s); its JSON summaries show **345** candidates POSTed to `upsert-by-phone`
per run with `inserted_new: 0`, and consecutive summaries **12–13 min apart** (launchd does not
overlap a running job, so the loop is back-to-back) `[AR-17]`. Attribution to this one statement
is the strongest candidate, not a proof: `pg_stat_statements` is not loaded on the cluster. The
decisive A/B is `launchctl unload` of that agent for 30 min while watching
`fly_instance_cpu_balance{instance="0801696b541568"}` — owner action.

Cures (proposed, none executed in-session):

- PR #6048 — migration 308: three expression indexes copied verbatim from the query (parity
  test pins them). Additive; plain `CREATE INDEX` inside the migration transaction takes a
  SHARE lock on `clients` for the build (50 MB → well under a second) `[AR-19]`. Bites in the
  PR: `EXPLAIN` of the statement before/after, `idx_scan` on the new indexes growing while
  `seq_scan` on `clients` stops.
- Operator/next PR: make the promoter skip already-promoted candidates before calling the API
  (345 → ~0 per cycle).
- The nightly backup runs **twice** (Pro crontab 03:00 UTC `fly-backup.sh` → `fly-pg-backup.sh`,
  and 03:20 UTC `cron-wrapper fly-pg-backup` → the same `fly-pg-backup.sh`, `cmp` SAME through
  the `~/scripts` symlink — same destination, same retention) — each `pg_dump` ≈ 25 min on the
  throttled node, overlapping. Drop crontab line 191 (the 03:20 one; 03:00 also runs Qdrant)
  and keep one verified backup in the log before calling it done `[AR-20]`.

Image: `flyio/postgres-flex:17.7 v0.2.0` → `v0.2.1` available. **Only at 3 nodes**, replica
first, after a verified backup — a member restart at 2 nodes is a write outage (§3) `[AR-36]`.

## 5. Cost guard (item 4)

`cron-fly-cost-alert.yml` had thresholds 6 machines / 60 GB / 1 IPv4 against 7 / 77 / 0 real
and **never failed** (only `::warning::`): 8/8 recent runs "success". PR #6044: logic extracted
to `scripts/fly_cost_guard.py`, exit 1 on findings, ceilings at today's footprint (7 machines,
6 started, 12288 MB started RAM, 77 GB, 0 paid IPv4), guilt + innocence tests on the live
inventory captured 2026-09-10, live run on Pro → `within limits`, exit 0. Two follow-ups the
review is right about `[AR-21, AR-22]`: the ceilings must be lowered in the same PR as each
cut (a guard at the old footprint would let it grow back silently), and the inventory should
carry `cpu_kind` so a shared→performance change trips it — neither is in #6044. Bites is
observed, not promised: a `workflow_dispatch` run on `main` after merge must print
`(limit 6/7)` / `(limit 77)` and conclude success `[AR-23]`.

## 6. Deploy (item 5)

Last 40 `fly-deploy.yml` runs (2026-09-01 → 09-09), per job, minutes:

| Job                              | avg      | median | max                                  |
| -------------------------------- | -------- | ------ | ------------------------------------ |
| Pre-deploy validation (gate)     | 3.9      | 3.8    | 5.4 — of which `pip install` 2.4     |
| Run DB migrations (ssh)          | 0.2      | 0.2    | 0.7                                  |
| **Fly.io rolling deploy**        | **6.7**  | 6.6    | 9.0                                  |
| Re-run SQL v2 post-deploy        | 0.2      | 0.2    | 0.3                                  |
| Python-idiom migrations          | 1.1      | 0.4    | 20.3 (one hang → cancelled run)      |
| whole workflow                   | 13.5     | 12.2   | 31.2                                 |

Inside the deploy step (run 34305951242): Depot builder ready 27 s → build 2 m 07 s (image
600 MB) → `release_command` 45 s → rolling update 3 m 10 s, of which the `api` machine alone
2 m 30 s (cold start, ML imports) — `drive` 50 s, `rag` 65 s, stopped standby 33 s.

- **Builder: Depot-hosted in all 40 runs** (`==> Building image with Depot`); no `fly-builder-*`
  app exists in the org. **`--depot=false` fallback: 0/40**; lease retry: 0/40.
- **The long runs are not slow builds** `[AR-28]`: 34018415917 (23.4 min), 33550287707 (24.1)
  and 33868044859 (18.3) each started ≤ 1 min after another push and waited in the
  `concurrency: fly-deploy` group (`cancel-in-progress: false`); 33860948592 (31.2) is the
  Python-migration hang (20 min) then timeout.
- Cure to approach < 10 min average (proposal, not a PR; every number below the line is an
  estimate to be measured in the PR that lands it `[AR-26, AR-27]`):
  1. build in parallel with the gate: a `build` job runs `flyctl deploy --build-only --push
     --image-label sha-${GITHUB_SHA}` on Depot; `deploy` has `needs: [pre-deploy-gate,
     run-migrations, build]` (fail-closed: any non-success skips it) and runs `flyctl deploy
     --image registry.fly.io/nuzantara-rag:sha-${GITHUB_SHA}` — an immutable, commit-bound label,
     not a mutable tag `[AR-24, AR-25]`; the image is built before the gate approves the commit
     but cannot be deployed without it. Removes ≈ 2.6 min from the critical path.
  2. gate: pinned `uv` with its cache action instead of `pip install` (2.4 min today) —
     expected gain up to ≈ 1.5 min, to be measured, and the resolved environment diffed against
     pip's before switching.
  3. keep the depot fallback as is (never fired; cheap insurance).
  Expected order of magnitude: 13.5 → ≈ 10 min average once the gate is no longer the critical
  path; the overlap outliers remain by design (serialised deploys).

## 7. Worker memory (item 6)

Fly Prometheus per instance; two views because one aggregate cannot size an OOM limit `[AR-32]`:

| Machine                            | used 7d max (total − available) | used 30d max | used 7d avg | RSS-like 7d max (total − free − cached) | Verdict                                                                                                        |
| ---------------------------------- | ------------------------------- | ------------ | ----------- | --------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `rag` 1781e5eda03438 (2 GB)        | 939 MB                          | 1128 MB      | 849 MB      | 841 MB                                  | keep 2 GB — the owner's gate for 1 GB was "peak < 700 MB" and it is not met                                    |
| `drive` 2874974fe6e158 (1 GB)      | 334 MB                          | 334 MB       | 302 MB      | 217 MB                                  | 512 MB feasible on the numbers, **not recommended now**: exit-1 restart today 16:57 WITA, cause unknown `[AR-30, AR-31]` |
| `api` 7817d92c4117d8 (3 GB)        | 1350 MB                         | 1350 MB      | 940 MB      | 1304 MB                                 | not in scope                                                                                                   |

Proposed fly.toml diff, to apply only after the drive crash is explained (owner applies):

```diff
 [[vm]]
   # Separate Machine so Drive polling cannot OOM or starve the API process.
-  memory = '1gb'
+  memory = '512mb'  # 2026-09-10: 30d peak 334 MB, avg 302 MB (Fly Prometheus)
   cpu_kind = 'shared'
   cpus = 1
   processes = ['drive']
```

## 8. Dead fly.toml (item 7)

`fly apps list` (the only org, `personal`): `nuzantara-rag` and `nuzantara-postgres`.
`apps/bali-intel-scraper/fly.toml` (`app = "bali-intel-scraper"`) and
`apps/admin-dashboard/fly.toml` (`app = 'nuzantara-admin'`) match no app; a repo-wide grep finds
no workflow, script or doc that reads them (one research JSON mentions the first as archaeology)
`[AR-35]`. The pre-commit off-limits gate blocks `git rm fly.toml`; its only bypass is
`--no-verify`, which the global rules forbid for agents and which skips every other hook too
`[AR-34]`. Two honest paths, both the owner's: run the two-line removal by hand under the
hook's own "intentional change" clause, or first give the gate a sanctioned allowlist (e.g.
`OFFLIMITS_DELETE_OK=<path>` checked by the hook) so an agent can ship it with hooks on.

## Decisions that stay with the owner

1. Postgres nodes: 3 (HA intact, recommended) or 2 (−$15.6 — every single-node event becomes a write outage, §3).
2. Volume cut 25→10 GB (−$2.25/node) — procedure §2, after the stale-dump sweep; lower the guard's `MAX_TOTAL_VOLUME_GB` in the same PR.
3. `go sweep` on PR #6045 (deletes 6.6 GB of stale dumps on the primary's disk at the next 03:00 UTC).
4. `go 308` on PR #6048 (expression indexes; merge = deploy).
5. Pro crontab line 191 (duplicate 03:20 UTC backup) — drop; A/B on the promoter (§4).
6. fly.toml: `drive` 512 MB only after the crash is explained; dead fly.toml removal (§8).
7. `fly image update -a nuzantara-postgres` (v0.2.0 → v0.2.1): only at 3 nodes, replica first.

## Adversarial review

**Seat:** Codex CLI 0.153.4 (`gpt-5.6-sol`, reasoning `xhigh`, `codex exec --sandbox
read-only`), 2026-09-09 16:50Z, given the full first draft and told to refute the arithmetic,
the procedures, the causal claims, the deploy proposal and the memory verdicts. It returned 36
findings (10 BLOCKER, 21 MAJOR, 5 MINOR). Each was checked against the measurements in this
session, not against the draft; dispositions below, applied in place where accepted.

| #       | Codex finding (severity)                                                      | Disposition                                                                                                                                                                                                                                                             |
| ------- | ----------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1, 3    | BLOCKER — destroying the old replica/volume right after clone; `checks list` alone is no proof of sync | **ACCEPTED.** §2 now stops (not destroys) the old machine, proves `pg_is_in_recovery`, `pg_stat_replication` lag and `repmgr cluster show`, waits 24 h + one verified backup, then destroys.                                                                     |
| 2       | BLOCKER — sweep may delete the last copies before the next backup is proven    | **REFUTED, narrowed.** The sweep touches only `/data/nuz-backup-*` older than one day on the database's own disk; local and Tigris tiers are untouched and the June/July files are past both retention windows by design. The PR stays unarmed for the owner regardless. |
| 4       | BLOCKER — at 2 nodes "standby promotes" contradicts the quorum rule            | **ACCEPTED.** The promoted standby sees 1 < 2 and quarantines: losing the primary is a write outage too. Table in §3 corrected.                                                                                                                                         |
| 5       | BLOCKER — no procedure to remove the third member                              | **ACCEPTED.** Added: destroy, `repmgr cluster show`, `repmgr primary unregister` if stale, confirm member count.                                                                                                                                                       |
| 6, 7    | MAJOR — "split-brain-prone" and "restart within minutes" unsupported           | **ACCEPTED.** Reworded as availability loss with no documented return SLA.                                                                                                                                                                                             |
| 8, 9    | MAJOR — 13 months and 2.5 years are wrong                                      | **ACCEPTED.** 4.6 GB / 0.4 ≈ 11 months; 9.1 GB / 0.4 ≈ 23 months.                                                                                                                                                                                                       |
| 10      | MAJOR — standby rootfs cost asserted without its size                          | **ACCEPTED.** Marked as not measured and excluded from the total.                                                                                                                                                                                                       |
| 11, 13  | MINOR — total range and the reversed extremes                                  | **ACCEPTED.** $59 … 72; the replica cell now pairs each outcome with its own Δ.                                                                                                                                                                                         |
| 12      | MAJOR — no price for shared-cpu-1x 512 MB                                      | **REFUTED.** The pricing page fetched in-session lists shared-cpu-1x 512 MB at $3.32; added to the frontmatter sources.                                                                                                                                                 |
| 14      | MAJOR — performance-1x +$31 is unproven                                        | **ACCEPTED.** Number removed; the avoided upgrade is stated without a price.                                                                                                                                                                                            |
| 15, 16  | MAJOR — cumulative counters cannot give a sustained rate; attribution unproven | **PARTLY REFUTED.** The 0.6/s came from a 60 s delta of `pg_stat_user_tables` (38 scans) plus 6 activity samples — now stated with the numbers. Attribution is downgraded to "strongest candidate" with the A/B (`launchctl unload` 30 min) named as the proof.          |
| 17      | MAJOR — 345 × 1–2 s does not make 12 min; overlap not shown                    | **ACCEPTED, narrowed.** The 12–13 min is the measured gap between consecutive run summaries; launchd serialises, so "back-to-back", not "overlapping".                                                                                                                  |
| 18      | MAJOR — "not configuration" is too broad                                       | **ACCEPTED.** Reworded: not a health-check configuration fault, not data integrity.                                                                                                                                                                                     |
| 19      | MAJOR — textual parity ≠ planner use; CREATE INDEX blocks writes               | **ACCEPTED.** EXPLAIN before/after added to the PR's Bites; the SHARE lock for a sub-second build on 50 MB is stated, not hidden.                                                                                                                                       |
| 20      | MAJOR — the two cron jobs may not be equivalent                                | **REFUTED.** Both invoke the same `fly-pg-backup.sh` (`cmp` SAME through the symlink), same bucket, same retention; the 03:00 wrapper also runs Qdrant, so the 03:20 line is the one to drop, after one verified nightly.                                              |
| 21, 22  | MAJOR — ceilings at today's footprint let it grow back; guard blind to CPU SKU | **ACCEPTED** as follow-ups: lower ceilings with each cut; add `cpu_kind` to the inventory (not in #6044).                                                                                                                                                                |
| 23      | MINOR — Bites is a promise                                                     | **ACCEPTED.** A `workflow_dispatch` run on `main` after merge is the observation.                                                                                                                                                                                       |
| 24, 25  | MAJOR — build-only proposal lacks fail-closed deps and an immutable image ref  | **ACCEPTED.** Proposal now uses `--image-label sha-${GITHUB_SHA}` and `needs:` on gate + migrations + build.                                                                                                                                                             |
| 26, 27  | MAJOR — uv gain and the 9.5 min average are unmeasured                         | **ACCEPTED.** Marked as estimates to be measured in the landing PR.                                                                                                                                                                                                     |
| 28      | MINOR — 18.3 min run is outside "23–31"                                        | **ACCEPTED.** Wording fixed.                                                                                                                                                                                                                                            |
| 29      | MAJOR — the 700 MB gate has no technical derivation                            | **REFUTED as scope.** It is the owner's stated criterion for proposing 1 GB; the verdict records that it is not met.                                                                                                                                                    |
| 30, 31  | BLOCKER/MAJOR — 512 MB for drive after an unexplained crash the same day       | **ACCEPTED.** Recommendation changed to "not now"; savings moved out of the plan until the crash is explained.                                                                                                                                                          |
| 32      | MAJOR — one memory aggregate cannot size an OOM limit                          | **ACCEPTED.** RSS-like series (total − free − cached) added alongside.                                                                                                                                                                                                  |
| 33      | MAJOR — RPO ≤ 24 h unproven without a restore test                             | **ACCEPTED.** Conditioned on a restore test.                                                                                                                                                                                                                            |
| 34      | BLOCKER — `--no-verify` bypasses every hook and the global rule                | **ACCEPTED.** The recipe is no longer presented as the way; §8 names the two honest paths (owner by hand under the hook's own clause, or a sanctioned allowlist first).                                                                                                 |
| 35      | MINOR — absence from the org does not prove the files are unused               | **REFUTED, with the evidence added.** Repo-wide grep: no workflow/script/doc consumer; `fly orgs list` shows a single org.                                                                                                                                             |
| 36      | BLOCKER — image update ordering vs the 2-node move                             | **ACCEPTED.** Constrained to 3 nodes, replica first, after a verified backup.                                                                                                                                                                                           |
