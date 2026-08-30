---
date: 2026-08-28
domain: operations
part: B7 data-platform-reliability-security
scope: Postgres 17.7 on Fly (repmgr HA, Tigris backups, WAL), migrations_v2 runner, role model, Redis, Sentry, health/observability/self-healing routers, middleware/workers/jobs, Fly.io runtime, application security.
sources:
  - https://sre.google/workbook/alerting-on-slos/
  - https://sre.google/workbook/error-budget-policy/
  - https://sre.google/workbook/implementing-slos/
  - https://fly.io/docs/reference/postgres-whats-next/
  - https://adriano.fyi/posts/fly-dot-io-postgres-failover-fix/
  - https://tomasz-gintowt.medium.com/postgresql-high-availability-repmgr-vs-patroni-vs-pg-auto-failover-a16fd0bfbc1e
  - https://pgbackrest.org/user-guide.html
  - https://severalnines.com/blog/automating-backups-and-disaster-recovery-in-postgresql-at-scale-pgbackrest-vs-barman/
  - https://about.gitlab.com/blog/postmortem-of-database-outage-of-january-31/
  - https://litestream.io/how-it-works/
  - https://pyrra.dev/
  - https://sloth.dev/introduction/architecture/
  - https://owasp.org/www-project-application-security-verification-standard/
  - https://github.com/OWASP/ASVS
  - https://tailscale.com/use-cases/zero-trust-networking
  - https://www.gremlin.com/docs/fault-injection-gamedays
  - https://grafana.com/observability-survey/2025/
status: DONE
adversarial_review: kimi-k3
---

> ## ⚠️ Read this before acting on anything below
>
> **These findings are pinned to `11a3c89a2e` (2026-08-28). `origin/main` was 123 commits ahead
> when this file was published on 2026-08-30.** A verdict in here is a **LEAD, not a fact**: it
> was true of a tree that no longer exists. Re-measure before you build on it.
>
> **Defects presented below as current that were already CURED before publication** — each fix
> verified as a descendant of the pin with `git merge-base --is-ancestor 11a3c89a2e <sha>`:
>
> | Presented as a live defect | Actually cured by | Verified |
> |---|---|---|
> | R9 harness time-bomb dated 2026-09-02 (X1) | #5190 | ancestor check |
> | Phantom DeepSeek voter (B8) | #5211 / #5207 (`cc82ed62e4`, `0cccbbc925`) | ancestor check |
> | Auth split-brain across the portals (F3, F4) | #5181 (`d6556a75bf`) | ancestor check |
> | Magic-link `result_id` ownership — which F2 calls "replay-safe" (F2) | #5298 (`3861567e52`) | ancestor check |
> | Meta webhook signature unenforced in prod (B3) | fail-closed by default since 2026-08-26; `WHATSAPP_APP_SECRET` deployed | live probe: unsigned `POST /webhook/whatsapp` → **401 `Invalid signature`** (2026-08-30) |
>
> **Counts that were re-measured and found WRONG** (they were not corrected in the text, so that
> the reports stay the artefact the panel actually produced rather than a quietly-improved one):
> `X3:31` reads 10 directories + 6 symlinks, measured 11 + 5. `X3:45` reads 162 `@mcp.tool`,
> measured 153. Other counts flagged by the review but NOT settled either way are listed in this
> PR's evidence pack under `dissent`, marked PLAUSIBLE — treat every number in these files as
> unverified unless you have just re-run it.
>
> **Known internal contradiction, left standing:** `B4` states that OCR of identity documents
> never leaves the machine, and then, two paragraphs later, that OCR'd passport/NPWP/akta text is
> shipped to Gemini by CRM-Guardian. The second statement is the accurate one. It is ledgered.
>
> **Two things were withheld from this publication rather than edited quietly:** the panel's own
> mandate file (self-labelled `IN-PROGRESS` / `internal`), and the location of a live DNS-write
> credential named in `B5`. Both omissions are declared here because a silently-sanitised audit is
> worth less than an audit that says what it removed.
>
> The reports' own thesis is that a written artefact gets presumed to be in force. This header
> exists because that thesis applies, first, to the reports themselves.


# B7 — Data Platform, Reliability & Security

## Anatomy (as measured)

All paths relative to `apps/backend-rag/backend/` unless noted; measured at pin `11a3c89a2e`.

### Migrations & schema discipline

- **174 SQL migrations** in `db/migrations_v2/` (the mandate said 162; the tree at this pin holds 174 — `ls db/migrations_v2/*.sql | wc -l`). Numbering has 10 deliberate gaps (092→107, 110→114, … 291→296) from the legacy-promotion process (`db/migrations_v2/LEGACY_PROMOTION_README.md`); no duplicate numbers at this pin (the W40/W128 numbering-collision scar class is currently clean).
- The runner is custom, not Alembic: `db/migrate.py` (189 lines, CLI), `db/migration_manager.py` (524 lines), `db/migration_base.py` (577 lines). Real engineering is present:
  - **Session-scoped advisory lock** serialises concurrent runs during rolling deploys (`db/migration_manager.py:328-396`, `pg_try_advisory_lock`, with a written rejection of `pg_advisory_xact_lock` and why).
  - **Ledger table `_schema_versions`** with per-file checksum (`db/migration_manager.py:147-152`).
  - **`-- === ROLLBACK ===` marker split** (`split_migration_sql`) — born of the 2026-04-19 scar where the runner executed the rollback section in-transaction and tables vanished after "applied successfully" (documented in `apps/backend-rag/CLAUDE.md`).
- **Migrations run at deploy, gated**: `apps/backend-rag/fly.toml` `[deploy]` sets `release_command = "python -m backend.db.migrate apply-all && python -m backend.db.schema_audit"` — a failed structural audit **blocks promotion**. `db/schema_audit.py` (440 lines) checks migration tracking, required tables, and client-email uniqueness; exit 1 on any failure.
- Migration PRs get Squawk lint plus server-side gating (`hot-zone-pr-gate.yml`) — CI itself is X1's scope; noted only as the migration surface's outer wall.
- **Caveat measured elsewhere** (operator memory, 2026-08-27): the release_command runs with the **runtime role's DSN**, so a DDL touching an object owned by `visa_ledger_owner` aborts the deploy, and CI cannot see it — the runner's privilege model is weaker than its lock/audit model.

### HA topology & backup path

- `nuzantara-postgres` is Fly postgres-flex 17.7 with **repmgr HA** (2 machines, primary + replica). The repo knows this (`docs/connectome/edges/http-webhooks.yaml:159`; `scripts/nuz_db_refresh.sh:267` resolves the repmgr primary), **but `scripts/fly-pg-backup.sh:119` still says "the app is Stolon HA"** — a stale comment surviving the 17.2→17.7 repmgr migration of 2026-08-09. Cosmetic, but it is exactly the drift class `scripts/lint_retracted_claims.py:463` exists to catch (it guards the "postgres-flex 17.2" phrasing, not this one).
- **Nightly logical backup** `scripts/fly-pg-backup.sh` (352 lines) is scar-hardened to a degree rare in small shops: primary resolved dynamically by health-check role, never "whichever machine ssh picks" (lines 139-174); pg_dump runs **inside** the primary via loopback as superuser (W38 demoted the DSN role below dump-capability, lines 126-130) and travels by SFTP, not the console stream that silently truncated >350MB dumps (lines 108-137); gzip integrity **plus pg_dump header check** (lines 240-251); Tigris upload with credential preflight; and — the crown — **`OFFSITE_OK` is set only by a remote listing that shows tonight's object** (lines 98-101, 296-311), writing a receipt (`.offsite-verified.json`) for the backup sensor and exiting non-zero on any local-only night (lines 345-351). The header narrates five distinct silent-failure incidents (2026-05-27, 06-03, 07-15, 07-26, 07-27), each of which produced a structural fix.
- **Monthly restore drill** `scripts/pg-restore-drill.sh` (177 lines): pulls the latest Tigris dump, restores into an ephemeral `postgres:17` Docker container, runs sanity queries (≥50 tables, `clients`/`practices` queryable), compares row counts against prod with a 10% drift tolerance, pages Telegram, and uses distinct exit codes 1-4 per failure class. "A backup that has never been restored is not a backup" is in the header. Also scheduled in CI (`.github/workflows/restore-drill.yml`, X1 scope).
- **WAL archiving**: re-enabled 2026-08-09 after a legacy override had disabled it while backups reported DONE (root `CLAUDE.md` §11; `docs/audits/2026-08-20-visa-oracle-dpia-v2.md:195`). No PITR tooling (pgBackRest/WAL-G) exists in the repo — operator-controlled recovery granularity is the nightly dump; anything finer depends on Fly-side snapshots/WAL the repo neither drives nor probes.
- Qdrant has a parallel path: `scripts/fly-qdrant-backup.sh`, `scripts/qdrant-snapshot.sh`, and `scripts/test_offsite_verify.sh` exercising the shared `scripts/lib/offsite_verify.sh`.

### Role model

- W38: `ALTER ROLE backend_rag_v2 NOSUPERUSER` (`docs/runbooks/2026-06-03-residual-ops-hub.md:99`) — deliberate hardening. Known aftermath recorded in operator memory: the `conversations` table is **write-dead** for the runtime role, making UU PDP erasure non-honorable by code path (unverified on disk in this pass; the runbook records the demotion, the write-dead consequence lives in the 2026-08-08 memory).
- Read-side defense-in-depth: `nuzantara_readonly` MCP role, 255 SELECT grants, zero DML (root `CLAUDE.md` §10).

### Middleware & auth stack (8 files, 2,151 lines)

- `middleware/hybrid_auth.py` (609 lines): API-Key → Bearer JWT → cookie JWT priority, **fail-closed by policy** (header comment plus `RevocationStoreUnavailable` handling); CSRF validation for cookie auth; public endpoints centralised in `app/auth/public_endpoints.py` (833 lines, ~95 registered paths — a large public surface that is at least *enumerated* in one place).
- `services/security/token_revocation.py`: Redis SETEX revocation, **fail-closed** (Redis down ⇒ auth denied). `services/security/brute_force.py`: IP+email pair, 5 failures/5 min ⇒ 429, **fail-open by design** — and its header documents the scar where the disarmed state was silent (`get_async_client()` returns None, never raises; `report_armed_state()` now announces the transition once). Two opposite failure policies, each argued in place — deliberate, not accidental.
- `middleware/pii_scanner.py` (330 lines): Presidio-based output scanner with custom Indonesian recognizers (KTP 16-digit, NPWP 15/16, passport, +62 phone), UU PDP Art. 35/36/38 cited; violations hashed (`hash_subject`) before storage.
- `middleware/rate_limiter.py` (370 lines): sliding window, Redis-primary with in-memory fallback at **half** the configured limit, self-healing reconnect on a 10s cooldown, metrics exposed via an admin endpoint. `core/redis_manager.py`: singleton pool, per-prefix TTL table, exponential-backoff auto-reconnect (30s→300s).
- Correlation IDs (`middleware/correlation.py`), request tracing, error monitoring, and activity logging complete the stack.

### Health, observability, self-healing

- `app/routers/health.py` (1,242 lines): `/health` (warmup/startup-failure detection), `/health/ready` (K8s-style readiness, line 764), `/live`, `/detailed`, plus per-organ probes — `/db`, `/redis`, `/collections`, `/metrics/qdrant`, `/kg-stats`, `/metrics/summary` — and a **Prometheus exposition endpoint** (`/metrics/prometheus`, line 1232). Fly checks hit `/health/ready` every 30s (fly.toml). **No Prometheus scrape config or infra/SLO dashboard exists in the repo** — `infra/grafana/` holds one social-metrics dashboard (`social-sota-dashboard.json`), nothing for the platform; the exposition endpoint has no in-repo consumer (off-repo consumer unverified).
- **Sentry**: `app/setup/sentry_config.py` — the `_before_send` PII scrubber is load-bearing (key-substring + exact-key + shape/label-anchored free-text tiers; the module docstring admits the pre-2026-08-02 version was "true of dicts and false of sentences"). `traces_sample_rate` defaults to 0.0 in prod; free tier is 5k events/month. `scripts/sentry-quota-check.sh` is the honest twin: until 2026-08-28 it linted config while the org error bucket was **already exhausted and dropping real errors** (the ~28% drop in operator memory); it now sends one probe event and reads the 429 `x-sentry-rate-limits` answer — detecting real exhaustion, not just config drift.
- **LLM cost ledger**: `services/observability/llm_cost_recorder.py` triple-writes (Prometheus counters + `llm_cost_events` m117 + logs); `cost_advisor.py` mines it weekly into `llm_cost_recommendations` (m118). Langfuse tracing exists but is **dormant** unless keys are set (PII-hidden defaults).
- **Hardening services** (`services/hardening/`, 9 files): `token_watchdog` (60-day expiry alerting, "we don't cry wolf" on unknown expiry), `llm_credit_sentinel` (born of a 34-hour silent Gemini-credit outage on 2026-07-28 that muted the WhatsApp bot), `missed_runs_alerter`, `quota_monitor` (soft spend caps), `failover_detector` (Pro-down via heartbeat).
- **Self-healing** (`backend/self_healing/`, 711 lines total): a real but small loop — checks (db, cache, http_api, system) × circuit breakers (threshold 3, cooldown 60s) × actions (gc, reconnect_cache, restart_service), ticked every 5 min by the autonomous scheduler, admin endpoint `admin_self_healing.py`. Honest sizing: it can reconnect a cache and collect garbage; it does not restart Fly machines or fail over Postgres. `services/self_healing/` — the path doctrine names — is an **empty directory**; the real code lives one level up.

### Workers, jobs, runtime

- `workers/drive_poll_worker.py`: Drive polling isolated in its own Fly process/machine (1GB) so OCR/import chains cannot starve the API — SIGTERM handling, jitter, `--once` mode. `jobs/`: `auto_practice_creator.py` (T-60 visa renewals), `conversation_cleanup.py`.
- `apps/backend-rag/fly.toml` encodes incident history as config: api single-worker (duplicate-scheduler incident), `--timeout-worker-healthcheck 600` for the 7-minute torch import chain, memory 3GB after an OOM loop (W60), `auto_stop_machines='off'`, rag process on private 6PN IPv6 with no public service block. Everything runs in **one region (`sin`)**.
- Zero-trust groundwork exists: `infra/tailscale/policy.hujson` (ACL policy in-repo, version-controlled) plus an enrollment runbook.

## Honest state vs. SOTA

**Genuinely strong — at or above small-team SOTA:**
1. **Backup verification culture.** The 2017 GitLab postmortem's core lesson — five backup mechanisms, all silently dead, discovered during the disaster — is *structurally* internalized here: the nightly job's verdict is a remote listing, not its own exit path; a receipt file is the sensor's ground truth; a monthly drill restores into a real container and compares row counts. Most funded startups do less.
2. **Migration runner.** Advisory-locked, checksummed, deploy-gated by a structural audit, with rollback-section extraction born of a real scar. This is Alembic-grade discipline without Alembic.
3. **Postmortem culture.** The cicatrix system (99+ scars, 10 families, executable antidotes like `lint_home_fork.py`, `lint_plist_keepalive.py`, `lint_retracted_claims.py`) is a *blameless postmortem practice compiled into linters* — beyond what the Google SRE workbook asks of postmortems, which usually stop at documents.

**Theater or dead:**
- `services/self_healing/` is an empty directory while doctrine names it; the real (modest) loop lives in `backend/self_healing/`.
- `fly-pg-backup.sh:119` claims Stolon HA; the cluster is repmgr — a retracted-claim that its own lint class misses.
- The Prometheus exposition endpoint emits metrics nobody scrapes (no in-repo consumer): observability theater until a scraper exists.
- Sentry's quota checker ran green for weeks while Sentry dropped ~28% of real errors — cured 2026-08-28, but the pattern (probe the config, not the outcome) is family #2's signature and should be assumed present elsewhere.

**Broken / structural gaps:** no SLOs or error budgets anywhere; no operator-controlled PITR (RPO up to ~24h against the off-site copy); single region, single storage provider for off-site copies (Tigris is Fly-adjacent — a Fly-account-level event could touch both); `conversations` write-dead blocks the UU PDP erasure path; alerting is single-channel Telegram with no dedup/escalation/on-call semantics.

## Deep research: the world's best

**SLOs and error budgets (Google SRE Workbook).** The workbook's implementable core is small enough for one person: pick 2-4 user-journey SLIs (availability and latency of the request path users actually feel), set targets from measured history rather than aspiration, and adopt an **error budget policy** — a pre-agreed rule such as "if the budget for the 4-week window is spent, releases halt except P0/security until back within SLO," and "an incident consuming >20% of the 4-week budget requires a postmortem with at least one P0 action item" ([error budget policy](https://sre.google/workbook/error-budget-policy/), [implementing SLOs](https://sre.google/workbook/implementing-slos/)). Alerting is **multiwindow multi-burn-rate**: page at 14.4× burn over 1h (with 5m confirmation window), page at 6× over 6h, ticket at 1× over 3 days ([alerting on SLOs](https://sre.google/workbook/alerting-on-slos/)). Crucially for Nuzantara's traffic scale, the same chapter addresses **low-traffic services**: synthesize traffic ("a system can synthesize user activity to check for potential errors and high-latency requests"), aggregate related services into one monitored group, or lower the objective. Nuzantara already builds synthetic purchase probes into product doctrine (ASSEMBLY-LINE), so the SRE-blessed low-traffic technique is culturally native — it just isn't wired to any budget arithmetic. Tooling exists to avoid hand-writing the PromQL: **Sloth** generates the multiwindow rules from a spec ([sloth.dev](https://sloth.dev/introduction/architecture/)), and **Pyrra** runs outside Kubernetes with filesystem-based SLO configs, generating recording rules for a plain Prometheus ([pyrra.dev](https://pyrra.dev/)) — both solo-operator sized.

**Postgres HA and the Fly reality.** Fly's own documentation is explicit that Fly Postgres is unmanaged: "you have to restore from [snapshots] when needed," "we won't upgrade your cluster automatically," "we collect and expose prometheus metrics but you have to set up Grafana or the likes," and OOM/disk-full recovery is yours ([postgres-whats-next](https://fly.io/docs/reference/postgres-whats-next/)). Community experience documents repmgr failovers that hang or mask ssh errors ([Caloiaro](https://adriano.fyi/posts/fly-dot-io-postgres-failover-fix/)). The HA-framework literature is consistent: **repmgr** is the lightweight choice (no external DCS) but leaves fencing and config drift to you; **Patroni** with etcd/Consul gives true automated failover (~30-45s) at the cost of running a consensus store ([Gintowt](https://tomasz-gintowt.medium.com/postgresql-high-availability-repmgr-vs-patroni-vs-pg-auto-failover-a16fd0bfbc1e)). For a solo operator the honest options are: keep repmgr and *drill the failover*, or exit to managed Postgres (a spend decision, §Solo-operatore). Running Patroni-on-Fly yourself is the worst of both worlds at this scale.

**Backups are restores; PITR.** The canonical failure remains GitLab 2017: five backup layers, S3 uploads empty, snapshots untested, webhook data gone; recovery came from an accidental 6-hour-old manual copy ([GitLab postmortem](https://about.gitlab.com/blog/postmortem-of-database-outage-of-january-31/)). The modern standard is **pgBackRest**: full/differential/incremental base backups, WAL archiving with retention, and — the detail that matters most — **`pgbackrest check`**, which forces a WAL switch and confirms the segment landed in the repository, because "if archiving silently fails, your PITR window starts accumulating gaps immediately" ([pgBackRest user guide](https://pgbackrest.org/user-guide.html); [Severalnines comparison](https://severalnines.com/blog/automating-backups-and-disaster-recovery-in-postgresql-at-scale-pgbackrest-vs-barman/)). Nuzantara's nightly-dump verification is exemplary, but the *granularity* is a day: WAL-level continuity has no operator-owned probe — precisely the gap that hid the pre-2026-08-09 dead WAL archiving. The 3-2-1 rule (3 copies, 2 media, 1 truly off-provider) is not met: local + Tigris are two copies, but Tigris rides the same Fly account. For the SQLite organs on Fly volumes (`/data/experience.db`, `/data/organism_metrics.db` — currently in **no backup path found in-repo**), **Litestream** streams WAL pages to any S3-compatible target with no code changes and ~1s RPO ([litestream.io](https://litestream.io/how-it-works/)).

**Observability for small teams.** The 2025 Grafana survey has 71% of orgs running Prometheus + OpenTelemetry together ([survey](https://grafana.com/observability-survey/2025/)); the small-team pattern is: instrument once (the app already exposes Prometheus metrics), scrape with one agent (Alloy or plain Prometheus on an always-on machine), alert via burn rates, and defer full OTel tracing until a concrete debugging need exists. Sentry-class error tracking at free-tier quota is a known trap; the standard answers are quota partitioning, paid tier, or self-hosted compatibles (GlitchTip/Bugsink speak the Sentry DSN protocol) — a spend-vs-sovereignty call.

**AppSec baseline.** **OWASP ASVS 5.0** (May 2025, ~350 requirements, 17 chapters) restructured Level 1 to be adoptable by small teams, with many L1/L2 controls verifiable by static analysis and configuration review ([owasp.org](https://owasp.org/www-project-application-security-verification-standard/), [GitHub](https://github.com/OWASP/ASVS)). Levels can be mixed per component — public API at L2, admin/identity surfaces at L3. Nuzantara's middleware already *implements* much of L1/L2 (fail-closed auth, revocation, brute-force, CSRF, output PII scanning); what's missing is the *mapping* — nobody can say which requirements are met, so regressions are invisible. **Tailscale** ACLs-as-code replace bastion/VPN patterns with identity-based, version-controlled access ([tailscale.com](https://tailscale.com/use-cases/zero-trust-networking)) — Nuzantara already has `policy.hujson` in-repo and a phased team-expansion plan gated on deny-by-default.

**Chaos-lite and gamedays.** The accessible form is the **gameday**: a scheduled, scoped fault-injection exercise validating both the system and the response process ([Gremlin gamedays](https://www.gremlin.com/docs/fault-injection-gamedays)). For one operator plus an agent fleet, the highest-value experiments are exactly the ones already half-built: kill Redis and watch the fail-open/fail-closed seams behave as documented; kill the LLM credit; fail over Postgres on purpose. The restore drill proves the artifact; the gameday proves the *organism*.

## Gap table

| Dimension | SOTA reference | Nuzantara today | Gap |
|---|---|---|---|
| Backup verification | GitLab-lesson: verify restores, own the outcome | Off-site listing = verdict; receipt file; monthly containerized drill w/ row-count diff | **None — at/above SOTA** |
| PITR / RPO | pgBackRest WAL archiving + `check` probe; minutes RPO | Nightly dump (RPO ≤24h); WAL Fly-side, unprobed by operator | **Large** |
| 3-2-1 off-provider copy | 1 copy outside the primary provider's blast radius | Local + Tigris (Fly-adjacent) | **Medium** |
| HA / failover | Patroni auto-failover or *drilled* repmgr; documented RTO | repmgr 2-node, never deliberately failed over (no drill artifact in repo); single region | **Medium-large** |
| SLOs / error budgets | 2-4 SLIs, budget policy, multiwindow burn-rate alerts | None; rich health endpoints, no SLI arithmetic | **Large** |
| Metrics pipeline | Prometheus scrape → dashboard → burn-rate alerts | Exposition endpoint with no scraper found in-repo | **Large** |
| Error tracking | Zero silent drops; quota headroom monitored | 5k/mo free tier; ~28% drop (memory); probe-based exhaustion detection since 2026-08-28 | **Medium (detection cured, capacity not)** |
| Alerting | Dedup, severity routing, escalation | Telegram push, per-script; missed-runs alerter exists | **Medium** |
| AppSec baseline | ASVS 5.0 L1/L2 mapped and tracked | Strong controls implemented; zero mapping | **Medium** |
| Secrets | sops/age encrypted-at-rest, rotation runbooks | 0600 env files + Fly secrets + Keychain; family-#4 scars + audit script | **Small-medium** |
| Zero-trust access | Tailscale ACLs deny-by-default | `policy.hujson` in-repo; team expansion gated on ACL phase | **Small** |
| Chaos / drills | Quarterly gamedays | Restore drill only | **Medium** |
| Incident learning | Blameless postmortems | Cicatrix: postmortems compiled to linters | **None — beyond SOTA** |
| SQLite organs backup | Litestream streaming replication | No in-repo backup path for `/data/*.db` | **Large (small blast radius)** |

## Recommendations — reach SOTA

Each sized for one operator + agent fleet; priority / falsifiable acceptance metric.

1. **P0 — Operator-owned WAL continuity probe (the `pgbackrest check` equivalent).** Nightly, from the Pro/Mini cron: force a WAL switch on the primary (`SELECT pg_switch_wal()`), then verify within N minutes that the archived segment is visible wherever Fly archives it (or, if unreachable, that `pg_stat_archiver.last_archived_time` advanced and `failed_count` did not). Alert red on stall. *Accept:* deliberately break archiving in a drill; the alert fires within 30 min. This is the exact probe whose absence hid the pre-2026-08-09 dead WAL archiving for months.
2. **P0 — Stand up the metrics pipeline and 3 SLOs.** One Prometheus (or Alloy) instance on the Mini scraping `/health/metrics/prometheus`; define SLOs for (a) API availability, (b) API p95 latency, (c) WhatsApp outbox delivery success, using Pyrra filesystem mode or Sloth-generated rules; wire the two page-severity burn-rate alerts to Telegram. *Accept:* an injected 5xx storm (staging) pages within 5 min at 14.4× burn; a one-page `SLO.md` in-repo states targets and the budget policy.
3. **P0 — Second off-site provider (true 3-2-1).** Weekly copy of the latest verified dump to a non-Fly S3 target (Backblaze B2 / Cloudflare R2), with the same "verdict = remote listing" pattern, plus a weekly cross-provider listing probe. *Accept:* probe shows ≤7-day-old object on the second provider every week for a month.
4. **P1 — Failover drill for repmgr.** Quarterly scheduled `fly pg failover` in a low-traffic window with a written expected-behavior card (who becomes primary, app reconnect time, alert expected); record measured RTO in the runbook. *Accept:* one completed drill artifact with measured RTO ≤ target; app recovers with no manual intervention.
5. **P1 — Cure the `conversations` write-dead path (W38 aftermath).** Grant the runtime role the minimal DML it needs (or route erasure through a SECURITY DEFINER function owned by the table owner), then prove a UU PDP erasure end-to-end in the restore-drill container. *Accept:* erasure request executes in drill; `test_data_invariant_tripwires`-style test pins the grant.
6. **P1 — Sentry capacity decision + drop-rate metric.** Track the probe script's 429 answers as a time series; either partition quota per project, pay one tier, or self-host a DSN-compatible (GlitchTip) on the Mini. *Accept:* 0 quota-dropped errors over 30 consecutive days, measured by the probe, not assumed.
7. **P1 — ASVS 5.0 L1 self-assessment mapped to the 95 public endpoints.** One markdown matrix (requirement → evidence file:line → status), agent-maintained; L2 for auth/admin surfaces. *Accept:* ≥90% of L1 requirements carry an evidence pointer; CI fails if a public endpoint is added without a matrix row.
8. **P1 — Litestream for the SQLite organs.** `/data/experience.db` and `/data/organism_metrics.db` replicate to the backup bucket. *Accept:* restore drill recovers both to within 60s of a known write.
9. **P2 — sops/age for repo-adjacent secrets files** (`~/.nuzantara-secrets.env` class), with `secrets_permissions_audit.py` extended to fail on unencrypted-at-rest. *Accept:* audit exits 2 on a planted cleartext file; real files pass encrypted.
10. **P2 — Fix the Stolon comment and extend `lint_retracted_claims.py`** to guard "Stolon" the way it guards "postgres-flex 17.2". *Accept:* the lint goes red on the current `fly-pg-backup.sh:119`, green after the one-line fix.

## Recommendations — beyond SOTA

1. **Error-budget-gated agent autonomy.** Google halts *human* releases when the budget is spent; Nuzantara can do better — wire the SLO budget into the fleet's dispatch layer, so a spent budget automatically re-routes agent lanes from feature mandates to reliability mandates (the PENDING-ARMS ledger is the natural queue). No human enforcement needed, which is exactly why it can actually hold here. *Accept:* a simulated budget exhaustion flips the conductor's lane selection within one session; the flip is logged.
2. **Restore-drill-as-staging chaos.** The monthly drill already produces a faithful prod clone in a container. Extend it: after sanity checks pass, run the *gameday* against the clone — kill Redis mid-request, exhaust the LLM credit stub, inject 5xx — and assert the documented fail-open/fail-closed seams (`brute_force` open, `token_revocation` closed, rate-limiter half-limits) behave as written. One artifact proves backups, failure modes, and doctrine accuracy in the same hour. *Accept:* drill report gains a chaos section with pass/fail per seam.
3. **Receipt-pattern generalization (W120 antidote as architecture).** `.offsite-verified.json` — a receipt written only on remotely-verified success, consumed by an independent sensor — is the strongest local pattern. Promote it to a convention: every green-claiming cron writes a receipt with the *outcome key the prober reads*; `pending_arms_report.py`-style tooling alarms on any sensor reading its producer's absence. *Accept:* top-5 crons emit receipts; a planted "green exit, no receipt" run alarms within 24h.
4. **Scar-to-probe compiler discipline.** The cicatrix families each name an executable antidote; several members still have none. Close the loop as policy: no new scar body is accepted without either a probe/lint or an explicit "unprobeable because X" line. This turns the postmortem archive into a growing immune system rather than a memoir. *Accept:* `test_superscar_budget.py`-style CI check counts antidote coverage per family and ratchets (never decreases).
5. **DPIA-linked data-platform evidence.** The DPIA (`docs/audits/2026-08-20-visa-oracle-dpia-v2.md`) already cites backup state with an OPEN owner. Auto-feed it: the restore-drill and WAL-probe receipts become machine-checked citations in the DPIA table, so the compliance document's claims are probed, not asserted — a UU PDP posture almost no SME can show. *Accept:* DPIA row cites the latest receipt timestamp, CI-verified fresh ≤35 days.

## §Meta-pattern

The single disease this part exhibits — and the repo names it as family #2, *esiste ≠ armato* — is **verification pointed at the wrong object**: the backup script judged its own last line instead of the bucket (until 2026-07-27); the Sentry check judged config instead of the quota (until 2026-08-28); the Prometheus endpoint emits what nothing scrapes; doctrine names `services/self_healing/` while the code lives elsewhere; a comment says Stolon while the cluster runs repmgr. The system's *strongest* artifacts are precisely the ones that internalized the cure — verdict-from-the-remote, receipt files, probe events — and its remaining gaps (WAL continuity, SLOs, failover) are all places where no probe yet reads the outcome. The meta-recommendation is therefore one sentence: **every green claim must be produced by a reader of the outcome, never by the writer of the attempt** — and the beyond-SOTA items above are that sentence applied to budget, chaos, receipts, scars, and compliance.

## §Solo-operatore

Decisions only Zero can take (business, spend, risk):

1. **Managed Postgres exit or stay.** Fly states plainly the DB is unmanaged; repmgr failover has never been drilled here. Options: (a) stay + fund the drills above (€0, operator time), (b) migrate to managed Postgres (Neon/Supabase/Crunchy — monthly spend, provider trust, UU PDP transfer analysis required for client PII). Recommendation: decide *after* the first failover drill measures actual RTO — data beats preference.
2. **Sentry spend vs. self-host.** ~28% error drop is a real observability hole. Paid tier (≈$26+/mo) vs. GlitchTip on the Mini ($0, more operator surface, aligns with Law 6 sovereignty). Needs an explicit yes either way — status quo is silent data loss.
3. **Second storage provider spend** (B2/R2, likely <$1/mo at current dump sizes) — trivially cheap, but it is a new external account = a credential + Art. 56 transfer surface only Zero can open.
4. **Error-budget policy ratification.** "Budget spent ⇒ feature lanes halt" is a Legge 5 business rule about what the fleet works on; only Zero can ratify it, or it will be overridden the first week it binds.
5. **RTO/RPO targets.** Today's implicit posture is RPO ≤24h, RTO unmeasured. Naming targets (e.g. RPO 15 min, RTO 1h) is a risk-appetite call that prices the PITR and failover work above.
6. **Single-region acceptance.** `sin`-only is a conscious availability trade; a read replica in another region is spend + complexity. Explicitly accepting the risk in writing is also a valid outcome.

## Sources

1. Google SRE Workbook — Alerting on SLOs (multiwindow multi-burn-rate; low-traffic guidance): https://sre.google/workbook/alerting-on-slos/
2. Google SRE Workbook — Error Budget Policy: https://sre.google/workbook/error-budget-policy/
3. Google SRE Workbook — Implementing SLOs: https://sre.google/workbook/implementing-slos/
4. Fly.io — "You've deployed Fly Postgres. Now what?" (operator responsibilities): https://fly.io/docs/reference/postgres-whats-next/
5. Adriano Caloiaro — Fly.io Postgres failover fix (repmgr failure modes): https://adriano.fyi/posts/fly-dot-io-postgres-failover-fix/
6. T. Gintowt — PostgreSQL HA: repmgr vs Patroni vs pg_auto_failover: https://tomasz-gintowt.medium.com/postgresql-high-availability-repmgr-vs-patroni-vs-pg-auto-failover-a16fd0bfbc1e
7. pgBackRest User Guide (WAL archiving, `check` command, PITR): https://pgbackrest.org/user-guide.html
8. Severalnines — pgBackRest vs Barman (DR automation patterns): https://severalnines.com/blog/automating-backups-and-disaster-recovery-in-postgresql-at-scale-pgbackrest-vs-barman/
9. GitLab — Postmortem of database outage of January 31, 2017: https://about.gitlab.com/blog/postmortem-of-database-outage-of-january-31/
10. Litestream — How it works (SQLite WAL streaming): https://litestream.io/how-it-works/
11. Pyrra — SLO monitoring for Prometheus: https://pyrra.dev/
12. Sloth — SLO generator architecture: https://sloth.dev/introduction/architecture/
13. OWASP ASVS project page (5.0): https://owasp.org/www-project-application-security-verification-standard/
14. OWASP ASVS GitHub: https://github.com/OWASP/ASVS
15. Tailscale — Zero Trust Networking: https://tailscale.com/use-cases/zero-trust-networking
16. Gremlin — Fault Injection > GameDays: https://www.gremlin.com/docs/fault-injection-gamedays
17. Grafana Labs — Observability Survey 2025: https://grafana.com/observability-survey/2025/

## Adversarial review

**Reviewer: `kimi-k3` (Moonshot K3) and `codex` (OpenAI gpt-5.6-sol at xhigh effort), 2026-08-30 — cross-family, generator ≠ grader.** Neither seat wrote any part of this panel. Both read all 18 files of the set in full and were asked the *publication* question rather than a proof-reading one: what in this diff creates real incremental risk beyond what the repository already discloses, whether "it is already public elsewhere" is a sound argument or a rationalisation, whether the sequencing is wrong, and what is simply FALSE. Every concrete file claim either seat made was then re-derived independently with `grep`/`git` before being recorded, and objections that measurement falsified are kept as RETRACTED rather than quietly dropped. The full journal and the complete objection list, with per-objection status, are in this PR's evidence pack (`council-journal.jsonl` and the pack's `dissent` block).

**Limits of this review, stated so it is not read as more than it was.** It happened at PUBLICATION time, not at authoring time: no seat re-derived this lane's technical findings against the codebase, so it is not a correctness review of the analysis. Nine numeric objections across the set were recorded PLAUSIBLE because the fact-checking pass ran out of time, not because they were investigated and cleared — an open list, not an all-clear.

**Finding for this file:** Flagged for publishing private operational state (live row counts, an error-drop percentage repeated without re-measurement) and for a written admission of non-compliance that is not derivable from the public code. Not blocking; named so the reader knows what this lane discloses.
