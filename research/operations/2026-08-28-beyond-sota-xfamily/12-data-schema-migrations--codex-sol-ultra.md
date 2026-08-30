---
panel: beyond-sota-xfamily
lane: 12-data-schema-migrations
seat: codex-sol-ultra
model: "gpt-5.6-sol · reasoning_effort=ultra · Codex CLI read-only sandbox · web search on"
started: 2026-08-28T19:11:45Z
finished: 2026-08-28T19:19:47Z
duration_s: 482
exit: 0
words: 5912
prompt_sha256_16: bcaa8341aaebf08d
prompt_chars: 18665
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 12/13 — Data, schema & migration engineering
model: OpenAI GPT-5.6 sol at reasoning effort ULTRA (pinned lane)
sources: 14
repo_files_verified: 30
status: complete
---

## 0. TL;DR

- **Position:** Nuzantara is ahead of typical solo-owner systems in invariant tripwires and scar-driven controls, but behind database SOTA in role-faithful migration testing, online schema evolution, and restore proof.
- **Biggest gap:** CI proves that SQL works in an empty database owned by the test role; production failures arise from the real ownership, membership, codec, and historical-data topology that CI does not reproduce.
- **Move 1:** Build a role-topology migration twin that applies every migration as the production runtime/migrator identity against catalog state with production-shaped owners and grants.
- **Move 2:** Require a migration evidence envelope: immutable checksum, risk class, timeouts, pre/postconditions, ownership expectations, and explicit rollback semantics.
- **Move 3:** Turn backup existence into a weekly Postgres-plus-Qdrant restore proof with measured RPO/RTO and catalog/data verification.
- Preserve the frozen `text-embedding-3-small`/1536 contract; introduce versioned Qdrant collections and atomic aliases before any future embedding migration.
- Do not weaken least privilege to make migrations pass; separate runtime, migrator, object-owner, retention, and inspection capabilities.
- The named `MEM:` files were unavailable under this lane’s access contract and were not read; repository migrations, scars, runbooks, and research copies were used instead.

## 1. How Nuzantara does it today

### 1.1 Migration estate and runner

The v2 migration directory contains **174 SQL migrations plus one README**, with numeric prefixes reaching `296`. Exact rollback markers exist in **170/174 SQL files (97.7%)**. Migration-path commit activity is high: the repository history shows 1, 9, 10, 30, 70, 42, 21, and 18 migration-directory-touching commits from January through August 2026 respectively. This is a throughput proxy, not a count of distinct migrations added. The directory also acknowledges unfinished promotion work: CI still bootstraps parts of the schema through SQLModel and raw DDL, while some production-created tables lack a canonical v2 migration. `apps/backend-rag/backend/db/migrations_v2/LEGACY_PROMOTION_README.md`

The custom runner discovers numbered files, executes forward SQL transactionally, records checksums and rollback SQL, and deletes the ledger row after a rollback. However, it takes its connection from `settings.database_url`: the **runtime DSN is also the migration identity**. The stored checksum is useful evidence, but the W130 scar records that rediscovery does not reject an already-applied migration whose file changed. Consequently, “checksum stored” is not yet “migration immutability enforced.” `apps/backend-rag/backend/db/migration_manager.py`; `apps/backend-rag/backend/db/migration_base.py`; `.claude/rules/cicatrix-scars.md`

Migration `289` is an unusually candid encoding of the resulting problem. Two Visa retention functions were owned by `visa_ledger_owner`; the runtime role could not replace them. The migration uses guarded dynamic DDL plus a preflight that inspects the live function body. It also warns that a guard can decline to execute while the runner still records the file as applied unless the postcondition is made loud. Its rollback has the mirror-image risk: the guard can decline while the ledger entry is removed. `apps/backend-rag/backend/db/migrations_v2/289_visa_retention_binders_scope_to_visa_decision.sql`

Migration `296` replaces a historical global uniqueness rule with a live-state partial unique index. Its rollback deliberately aborts if historical duplicates make restoration impossible instead of deleting audit history. That is the correct integrity bias: “irreversible without loss” is represented as a loud failure, not a fictional rollback. `apps/backend-rag/backend/db/migrations_v2/296_wa_broker_jobs_live_only_unique.sql`

A literal scan finds **53 `SECURITY DEFINER` occurrences** and one literal `OWNER TO visa_ledger_owner`. This materially understates the ownership surface because some ownership is inherited from earlier catalog state or expressed through dynamic SQL. W130’s production catalog inspection found **22 tables not owned by the runtime role**: 11 owned by `visa_ledger_owner`, nine by another application owner—including the write-dead `conversations` surface—and one each by infrastructure roles. `.claude/rules/cicatrix-scars.md`

### 1.2 Migration CI

There are three useful migration-specific controls:

- Squawk lint runs on changed SQL.
- Numeric-prefix lint rejects duplicate migration numbers.
- Rollback lint enforces the rollback contract.

`.github/workflows/migration-lint.yml`; `.github/workflows/lint-migration-numbers.yml`; `.github/workflows/lint-migration-rollback.yml`

The implementation has four important gaps:

1. Squawk is installed as `squawk-cli@latest`, so the safety policy can change without a repository commit.
2. It lints as PostgreSQL **15.0**, while the documented production cluster is PostgreSQL **17.7**.
3. Rules covering concurrent index operations, timeouts, destructive DDL, robust statements, and `NOT VALID` constraints are substantially excluded.
4. The inspected workflows do not declare a `merge_group` trigger, leaving a potential merge-queue execution gap.

Squawk itself states that lint success does not make a migration safe: a short `lock_timeout`, normally a `statement_timeout`, and operational retries are still required. Nuzantara’s current workflow excludes the very rules that enforce part of that runtime contract. [Squawk safe-migration guidance](https://github.com/sbdchd/squawk/blob/master/docs/docs/safe_migrations.md)

### 1.3 Production-shaped tests—and where the shape stops

The test harness has a sophisticated xdist strategy: it builds a pristine, connectionless template, serializes its creation with an advisory lock, and clones a database per worker. This fixes W131, where the same `TEST_DATABASE_URL` represented both the test namespace and the source of truth, allowing one worker’s state to contaminate another. `apps/backend-rag/backend/tests/conftest.py`; `.claude/rules/cicatrix-scars.md`

That topology is production-shaped for schema and data isolation, but not for **authority**. W130 documents why the migration suite stayed green: the ephemeral test role owned the objects it modified. Production had heterogeneous owners, `NOSUPERUSER` runtime execution, missing role membership, and missing `REFERENCES`/ownership rights. A clean database cannot reveal that class of defect unless CI reconstructs the role graph and runs the migration with the same effective identity. `.claude/rules/cicatrix-scars.md`

### 1.4 JSONB boundary

The connection initializer registers asyncpg JSON/JSONB codecs using `json.dumps`/`json.loads`. Passing a Python `dict` or `list` is correct; passing an already serialized string through `$N::jsonb` causes the codec to serialize it again, producing a JSON string scalar. A cast to `jsonb` does not bypass the client codec. `apps/backend-rag/backend/app/setup/service_initializer.py`

Nuzantara now has an AST guard covering a registry of JSONB columns and accepting two explicit patterns: bind the structured Python value directly, or send serialized text through `$N::text::jsonb`. The guard is strong static prevention, but it is best-effort rather than a live protocol test. A repository audit records the observed consequence of this defect class: an outbox payload was decoded as a string instead of an object, producing 64,721 errors and approximately 47 MB of error output while cursor progress stopped. `apps/backend-rag/backend/tests/db/test_jsonb_double_encoding_class_guard.py`; `research/operations/2026-05-21-nb-automations-audit.md`

### 1.5 Invariants and abstention contracts

The repository explicitly separates two superficially similar KBLI shapes:

- Qdrant KBLI payloads are flat: business fields such as `code`, titles, description, category, and section are top-level.
- PostgreSQL `kbli_documents` stores business metadata inside its `metadata` JSONB column.

A tripwire inspects query code to prevent treating PostgreSQL as though it shared Qdrant’s flat shape. `CLAUDE.md`; `apps/backend-rag/backend/tests/test_data_invariant_tripwires.py`

The embedding contract is frozen at `text-embedding-3-small`, **1536 dimensions**. The same tripwire records that changing it would invalidate 93,283 indexed vectors in its reference snapshot. `CLAUDE.md`; `apps/backend-rag/backend/tests/test_data_invariant_tripwires.py`

The abstention policy names five independent thresholds rather than collapsing them into one accidental constant:

- generation support minimum;
- domain label threshold;
- low-confidence boundary;
- high-confidence boundary;
- context-quality minimum.

Domain label thresholds deliberately vary, including a stricter KBLI threshold. The policy is an immutable dataclass and the divergence is documented as intentional. `apps/backend-rag/backend/services/rag/agentic/_abstain_policy.py`; `CLAUDE.md`

### 1.6 Outbox durability

SYMBIOSIS Legge 3/4 gives the Postgres event channels transactional durability through `events_outbox`: domain mutation and outbox insertion share a transaction, and events within a listener-disconnect window are replayed on reconnect. The documented replay horizon is 60 minutes. Tests exist for replay, call-site integration, channel parity, and stale-entry handling. `SYMBIOSIS.md`; `apps/backend-rag/backend/tests/services/events/`

The remaining semantic gap is explicit: acknowledgement is dispatcher-level rather than handler-level. A handler can fail after the dispatcher considers the event consumed. The contract is therefore stronger than best-effort notification but weaker than per-consumer proven delivery. `SYMBIOSIS.md`

### 1.7 Qdrant, retention, and inspection

The July 5 estate runbook recorded **14 live collections and 113,818 points**, while only six of 20 declared definitions matched a live collection; 14 definitions were dead and eight live collections were undocumented. These are dated measurements, not a claim about August 29 live state, but they prove that collection declarations and reality had materially diverged. `docs/runbooks/qdrant-estate-reconciliation.md`

Postgres MCP inspection is intentionally read-only. The documented `nuzantara_readonly` role had 255 selectable relations and zero write privileges at verification time. W87 shows why a configured MCP is not proof: the endpoint/identity combination must execute a real authorization query. `CLAUDE.md`; `.claude/rules/cicatrix-scars.md`

Visa retention is designed around narrowly executable binder functions, dry-run evidence, legal holds, and a dedicated capability role. The runbooks’ last verified states were nevertheless “repo-ready/unarmed” and “NO-GO” pending role, policy, DPIA, and operational gates. `docs/runbooks/visa-oracle-retention-operations.md`; `docs/runbooks/visa-oracle-privacy-enforce-gate.md`

The canonical external-memory decision body for five-year conversation retention was unavailable. Two repository Research OS artifacts reference an established five-year conversation-retention floor and explicitly warn not to inherit it into unrelated claim data. That establishes the existence of the doctrine, but not enough detail to reconstruct its legal rationale. `research/operations/execution/research-os-v1.0.0/evidence/p06/ros-v1-p06-naga-prep-b01/02-p04-adapter-mapping.md`; `research/operations/execution/research-os-v1.0.0/evidence/p06/ros-v1-p06-naga-prep-b01/07-open-questions-and-corrections.md`

### 1.8 Backup and restore

Repository doctrine says production runs PostgreSQL 17.7 with repmgr HA, daily Tigris backup, and WAL archiving restored after a legacy override had disabled it. This history proves an important distinction: a backup job reporting “DONE” did not prove restorability. `CLAUDE.md`

The restore workflow is scheduled monthly. It downloads a recent compressed dump, requires it to exceed 1 MB, restores into PostGIS 17, and performs coarse sanity queries. However:

- the workflow records that required Tigris secrets were absent as of 2026-06-05;
- restore uses `ON_ERROR_STOP=0` and `|| true`;
- proof is limited to table count and basic relation queries;
- it does not verify owners, grants, RLS, function security properties, constraints, checksums, WAL target recovery, Qdrant aliases, RPO, or RTO.

`.github/workflows/restore-drill.yml`

A live `gh run list` check could not be completed because the snapshot has no remote recognizable by the GitHub CLI. Therefore, **monthly cadence is configured, but the last proven successful restore is unknown from available evidence**.

## 2. Scars & ledger evidence in this area

The dominant superscar is **#9: state-schema mutation drift**—a producer, schema, state machine, or storage representation changes without all consumers and operational identities changing with it. The second recurring family is **#2: exists/configured does not mean armed or usable**. `.claude/rules/cicatrix-superscar.md`

| Evidence | What actually happened | Recurrence signal | Present cure/status |
|---|---|---|---|
| W38 | Demoting the runtime role to `NOSUPERUSER` exposed missing privileges; later catalog evidence included a write-dead `conversations` surface. | Least privilege was applied after objects had accumulated heterogeneous owners. | Demotion was correct; role-isomorphic migration CI remains absent. `.claude/rules/cicatrix-scars-archive.md`; `.claude/rules/cicatrix-scars.md` |
| W40 | Two parallel agents chose migration number 194 within approximately five minutes. | Shared monotonic counters are unsafe under parallel writers. | Numeric collision lint added. `.claude/rules/cicatrix-scars-archive.md`; `.github/workflows/lint-migration-numbers.yml` |
| W128 | Counter reservation recurred because current `main` did not include open-PR allocations. | Static repository state is not a distributed lease. | Collision lint catches committed duplicates, but reservation across open branches remains a coordination problem. `.claude/rules/cicatrix-scars.md` |
| W53 | A terminal/DLQ state did not suppress further processing. | State addition without total consumer review. | Incorporated into superscar #9. `.claude/rules/cicatrix-superscar.md` |
| W54 | A timestamp representation change crashed a consumer. | Type compatibility was assumed instead of proved. | Incorporated into superscar #9. `.claude/rules/cicatrix-superscar.md` |
| W61 | Re-adding an existing state discarded attempt metadata, causing a four-job storm and 4,676 escalations. | “Same logical state” was not the same stored state. | Incorporated into superscar #9. `.claude/rules/cicatrix-superscar.md` |
| W87 | MCP was listed as connected, but the endpoint/role combination could not authenticate an actual query. | Handshake was used as a proxy for authorization. | Read-only role plus real query verification. `.claude/rules/cicatrix-scars.md` |
| W130 | A Fly release aborted because the runtime DSN attempted owner-only and privilege-sensitive DDL. CI owned every test object and stayed green. | Direct recurrence of W38 at deploy time; 22 mismatched table owners were measured. | Static guard added; the underlying role-topology mismatch remains. `.claude/rules/cicatrix-scars.md` |
| W131 | Parallel test workers cloned from a mutable worker database and contaminated one another. | “Test DB” carried two incompatible meanings. | Connectionless pristine template plus per-worker clones. `apps/backend-rag/backend/tests/conftest.py`; `.claude/rules/cicatrix-scars.md` |
| JSONB incident | A serialized object was serialized again by the asyncpg codec, yielding a scalar and halting cursor progress. | Same shape appeared valid in source and SQL text but changed on the wire. | AST guard and codec documentation; live round-trip proof is still needed. `apps/backend-rag/backend/tests/db/test_jsonb_double_encoding_class_guard.py`; `research/operations/2026-05-21-nb-automations-audit.md` |

The ledger adds operational evidence:

- A KBLI repair had passed a 73/73 dry run while live rows remained stale—proof of computation was mistaken for proof of application.
- Visa activation was held on capability-role/`SECURITY DEFINER` ownership mismatch.
- Four red cross-family reviews on a role-sensitive migration raised the unresolved governance question of whether red database/security review is blocking.
- Qdrant reconciliation required an explicit activation decision.
- JSONB citation elements lacked full source-record validation.

`.claude/skills/modus/PENDING-ARMS.md`

The relevant AMENDMENTS entry records another shape mismatch: nine implementers launched full suites against the same test database, producing 7–18 concurrent runs and spurious database failures before suite serialization was introduced. `.claude/skills/modus/AMENDMENTS.md`

The pattern is not one isolated migration mistake. At least eight named scars directly involve schema, storage state, identity, migration numbering, test topology, or durable consumption. Four canonical members—W53, W54, W61, W88—already form superscar #9. The organism is strong at turning failures into controls; it is weaker at replacing incident-specific guards with one executable model of the production data plane.

## 3. World SOTA survey

| System/practice | Primary source | Mechanism | Measured effect | Transferability |
|---|---|---|---|---|
| Stripe online migrations | [Stripe, 2017](https://stripe.com/blog/online-migrations) | Dual-write, lazy backfill, read cutover, write cutover, cleanup; gradual traffic ramp. | Migrated hundreds of millions of objects while services remained at 100% operation; incident-rate reduction not published. | High for large table/representation changes; requires explicit invariants and idempotent backfill. |
| pgroll | [Xata/pgroll](https://github.com/xataio/pgroll) | Expand/contract via versioned schemas and views; dual columns and synchronization triggers; instant pre-completion rollback. | Benchmarks run across PostgreSQL 14–18 and 10k–300k rows, but no universal improvement figure is published. | Medium-high. Pilot only on high-risk migrations; RLS and security-invoker semantics require scrutiny. |
| Squawk | [Safe migrations](https://github.com/sbdchd/squawk/blob/master/docs/docs/safe_migrations.md) | Static unsafe-DDL detection plus required lock and statement timeouts. | No published operational effect. | Immediate: pin version, target PG17, reduce exclusions, enforce timeouts. |
| PostgreSQL least privilege | [CREATE FUNCTION](https://www.postgresql.org/docs/current/sql-createfunction.html) | Owner-only replacement; secured `search_path`; revoke default `PUBLIC` execute; selective grants in one transaction. | Normative safety mechanism, not an experiment. | Direct. Nuzantara has 53 SECDEF occurrences and repeated owner failures. |
| PostgreSQL RLS | [Row security policies](https://www.postgresql.org/docs/17/ddl-rowsecurity.html) | Default-deny when enabled without policy; policies scoped by command and role; owners/BYPASSRLS treated explicitly. | Normative. | High for retention and capability boundaries, provided CI tests owner and non-owner paths. |
| GitHub gh-ost | [GitHub/gh-ost](https://github.com/github/gh-ost) | Replica rehearsal, checksums, throttling, pausing, delayed cutover, workload-aware control. | GitHub continuously migrates and checksums its production-table fleet on replicas; numeric failure reduction is not published. | Mechanism transfers even though gh-ost is MySQL-specific: rehearsal, throttle, checksum, controllable cutover. |
| pgTAP | [pgTAP documentation](https://pgtap.org/documentation.html) | SQL-native schema, privilege, function, trigger, and data assertions inside transactions. | Documentation example executes 216 tests in roughly one wall-clock second; not a production benchmark. | High for catalog and role assertions; no cloud API required. |
| Debezium outbox router | [Debezium documentation](https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html) | Transactional outbox plus CDC and aggregate-key routing avoids application/database dual writes. | No general effect published. | Architectural reference for delivery semantics; Nuzantara may retain local Postgres dispatch rather than add Kafka. |
| PostgreSQL PITR | [Continuous archiving/PITR](https://www.postgresql.org/docs/17/continuous-archiving.html) | Base backup plus an unbroken WAL sequence permits recovery to a selected point. | Normative; effect is recoverability to available WAL granularity. | Direct and already doctrinally intended. Must be proved through restoration. |
| Fly backup/restore | [Fly documentation](https://fly.io/docs/postgres/managing/backup-and-restore/) | Restore snapshots into a new database app, verify, then reconnect applications. | No RTO/RPO guarantee published for unmanaged clusters. | High. Fly explicitly leaves unmanaged Postgres recovery responsibility with the operator. |
| Qdrant snapshots | [Qdrant snapshots](https://qdrant.tech/documentation/snapshots/) | Per-collection snapshots preserve points, payloads, and index configuration; aliases are separate state. | No fixed time; avoids rebuilding the stored index. | Direct. Alias state must be backed up and tested separately. |
| Qdrant migration strategies | [Qdrant migration and recovery](https://qdrant.tech/documentation/migration-recovery-options/) | Select snapshots, streaming migration, or cluster backup according to topology change. | Snapshot restore can save hours; streaming migration may require about 2× source RAM and disk. | High for versioned embedding/index migration capacity planning. |
| Database-access bug study | [Chen et al., 2024](https://arxiv.org/abs/2405.15008) | Empirical taxonomy of database access defects. | 423 bugs across seven large Java systems; causes span SQL, schema, API, configuration, and result handling. | Strong support for testing the full driver/config/schema boundary, not SQL alone. |
| Semantic schema evolution | [FGCS, 2025](https://doi.org/10.1016/j.future.2025.108257) | Query rewriting and physical evolution preserve meaning across historical schema states. | Evaluated on six million records and 170 evolution events from a 30-year dataset. | Relevant to long-lived conversations, retention, and KBLI history: semantic meaning must be versioned, not only column types. |

Four practices matter most here.

First, **expand/contract is a compatibility protocol, not a SQL style**. Stripe and pgroll preserve old and new readers concurrently, while Nuzantara normally executes a transactional file and then deploys the application. Transactions protect atomicity; they do not protect old application instances from a newly incompatible schema.

Second, **production identity is part of schema shape**. PostgreSQL ownership, memberships, `search_path`, default privileges, RLS, and `SECURITY DEFINER` properties are executable semantics. A test database with the right columns but the wrong owner is not production-shaped.

Third, **rehearsal must include historical data and cutover control**. gh-ost’s reusable contribution is not its MySQL implementation but replica rehearsal, checksums, load throttling, pause, and postponed cutover. Nuzantara’s high-risk migrations need the same controls against an isolated restored database.

Fourth, **a backup is an input; a restore proof is the product**. PostgreSQL requires a continuous WAL chain, Fly delegates recovery of unmanaged clusters to the operator, and Qdrant snapshots omit aliases. A credible proof must reconstruct relational data, authority, vector configuration, and alias routing together.

## 4. Position vs SOTA

| Sub-dimension | Position | Evidence |
|---|---|---|
| Migration numbering and rollback hygiene | **AT** | Duplicate-number and rollback lints exist; 170/174 SQL files have the exact rollback marker. `.github/workflows/lint-migration-numbers.yml`; `.github/workflows/lint-migration-rollback.yml` |
| Migration immutability | **BEHIND** | Checksums are stored but W130 says applied-file drift is not rejected. `apps/backend-rag/backend/db/migration_base.py`; `.claude/rules/cicatrix-scars.md` |
| Online/zero-downtime evolution | **BEHIND** | No general expand/contract or versioned-schema protocol; Squawk suppresses several core operational rules. `.github/workflows/migration-lint.yml` |
| Least-privilege ownership engineering | **BEHIND** | Runtime DSN executes migrations; W38/W130 and migration 289 expose recurring owner and membership failures. `apps/backend-rag/backend/db/migration_manager.py`; `apps/backend-rag/backend/db/migrations_v2/289_visa_retention_binders_scope_to_visa_decision.sql` |
| Prod-shaped test data | **AT** | Connectionless template and isolated worker clones are strong. `apps/backend-rag/backend/tests/conftest.py` |
| Prod-shaped authority and history | **BEHIND** | Empty CI database owns everything; production contained 22 differently owned tables. `.claude/rules/cicatrix-scars.md` |
| JSONB codec defense | **AT in mechanism; BEHIND in closure** | Static class guard is unusually strong, but a recent double-encoding incident reached operational scale and there is no universal driver round-trip contract. `apps/backend-rag/backend/tests/db/test_jsonb_double_encoding_class_guard.py` |
| Domain invariants | **AHEAD** | KBLI store-shape separation, frozen embedding/dimension, and five named abstention thresholds are executable tripwires designed for agent-generated changes. `apps/backend-rag/backend/tests/test_data_invariant_tripwires.py`; `apps/backend-rag/backend/services/rag/agentic/_abstain_policy.py` |
| Outbox atomicity | **AT** | Domain/outbox transaction and replay tests meet the standard transactional-outbox baseline. `SYMBIOSIS.md`; `apps/backend-rag/backend/tests/services/events/` |
| End-to-end delivery proof | **BEHIND** | Dispatcher acknowledgement can precede successful handling; replay horizon is 60 minutes. `SYMBIOSIS.md` |
| Qdrant lifecycle/versioning | **BEHIND** | Dated audit showed six of 20 definitions aligned, eight undocumented live collections, and aliases outside snapshot payload. `docs/runbooks/qdrant-estate-reconciliation.md` |
| Retention policy design | **AHEAD** | Bounded binder functions, legal-hold gates, dry runs, and evidence manifests exceed common cron-deletion practice. `docs/runbooks/visa-oracle-retention-operations.md` |
| Retention operation | **BEHIND** | Runbooks were unarmed/NO-GO at their last verification; current live proof is unavailable. `docs/runbooks/visa-oracle-privacy-enforce-gate.md` |
| Read-only inspection | **AHEAD** | Explicit 255-SELECT/zero-write MCP role and a scar requiring a real query, not connection status. `CLAUDE.md`; `.claude/rules/cicatrix-scars.md` |
| Backup/restore proof | **BEHIND** | Monthly workflow exists, but uses error-tolerant restore and coarse checks; last successful drill is not established. `.github/workflows/restore-drill.yml` |

## 5. Beyond-SOTA recommendations

Ranking uses `(impact × confidence) / implementation cost`. Every design uses local execution or existing flat-subscription CLI seats; none requires a paid Anthropic API or automatic Fable routing.

### 1. Production Authority Digital Twin — score 9.4

**What:** Export a PII-free catalog manifest containing PostgreSQL version, extensions, roles, memberships, owners, grants, default privileges, RLS flags/policies, function owners, security mode, fixed `search_path`, triggers, and constraints. Reconstruct this topology in CI, load a scrubbed structural baseline, and apply migrations using the exact effective runtime or dedicated migrator role.

**Why it beats SOTA:** Prod-shaped test databases are common; privilege lint is common. The composition that is novel here is a **scar-derived authority twin** whose mutation suite specifically replays W38, W87, W130, and W131 and whose gear is raised automatically when a migration touches an owner-sensitive catalog object.

**Cost:** 20–28 engineering hours; two cross-family CLI review passes; negligible recurring flat-sub tokens.

**Gear:** 3.

**Risk/scar family:** #2 and #9. A stale manifest could become another false proxy.

**Metric:** Before: 22 production ownership mismatches and at least two owner-related deploy incidents. After: 100% of migrations executed under intended identity; zero undetected owner/grant mutations; manifest age under seven days. Measure via catalog diff artifact per PR.

**Kill criterion:** Retire or simplify if it adds over 12 minutes to migration CI or blocks over 5% of 20 consecutive migration PRs for non-production-relevant differences.

**First PR:** Add a catalog-manifest schema, an offline validator, and W130 fixtures; ≤350 net lines across a new `scripts/postgres_authority_manifest.py` and `apps/backend-rag/backend/tests/db/test_postgres_authority_manifest.py`.

### 2. Migration Evidence Envelope — score 9.1

**What:** Every new migration declares or generates:

- immutable content checksum;
- PostgreSQL version;
- risk class;
- required executing role/memberships;
- touched owners and SECDEF functions;
- lock and statement timeouts;
- forward precondition and postcondition;
- rollback class: exact, compensating, or irreversible;
- estimated/backfilled row scope;
- expand/contract phase where applicable.

The runner must never record `APPLIED` without a true postcondition and must reject checksum drift.

**Why it beats SOTA:** Tools generally lint SQL or orchestrate migration state. This envelope unifies lint, authority, runtime proof, rollback honesty, scar-triggered gear, and ledger immutability in one content-addressed artifact consumable by autonomous agents.

**Cost:** 12–18 hours; one standard and one adversarial CLI review.

**Gear:** 3 for runner changes, 2 for migration metadata.

**Risk/scar family:** #9; overly rigid metadata could encourage meaningless checkbox values.

**Metric:** Before: 170/174 exact rollback markers, but zero enforced rollback classifications and checksum drift not rejected. After: 100% of new migrations classified; zero “declined but applied”; checksum drift caught in one CI cycle.

**Kill criterion:** Redesign if authors can satisfy the envelope without executable predicates or if median authoring time exceeds 20 minutes after ten migrations.

**First PR:** Enforce checksum comparison and a mandatory postcondition for guarded DDL in `apps/backend-rag/backend/db/migration_base.py`, `apps/backend-rag/backend/db/migration_manager.py`, and a new focused test; ≤300 lines.

### 3. Unified Restore Proof Organ — score 8.8

**What:** Weekly, restore a randomly selected recent Postgres base/dump plus WAL target into an isolated Pro/Mini database; restore one rotating Qdrant collection and its aliases; then verify schema checksum, constraints, owners, grants, RLS, SECDEF/search paths, representative row-count bands, outbox replay, embedding dimension, collection configuration, and frozen-model identity. Emit a signed, PII-free evidence manifest with measured RPO/RTO.

**Why it beats SOTA:** Restore testing is established practice. The novel composition is one proof spanning PostgreSQL authority, outbox semantics, Qdrant index state, aliases, and agent-consumed invariants—using the always-on local fleet and scar corpus.

**Cost:** 20–30 hours plus local disk; no per-token API cost.

**Gear:** 3.

**Risk/scar family:** #2 and #9; a restore can pass while consumers remain incompatible unless consumer probes are included.

**Metric:** Before: monthly configured cadence, last proven success unknown, no RPO/RTO. After: ≥12 consecutive weekly proofs, RPO ≤5 minutes where WAL permits, RTO ≤30 minutes for the defined recovery unit, 100% catalog assertions green.

**Kill criterion:** Split the proof if median runtime exceeds 90 minutes or local storage exceeds the approved cap for four weeks.

**First PR:** Make `.github/workflows/restore-drill.yml` fail on restore errors and add catalog/constraint assertions in a new `scripts/verify_restored_database.py`; ≤380 lines.

### 4. Typed JSONB Wire Contract — score 8.4

**What:** Introduce explicit `JsonbStructured` and `JsonbText` adapter types at database boundaries. Add driver-level round-trip tests with the production codec, property-based values for object/array/scalar/null, and mutations that remove `::text` or pre-serialize structured inputs. Gradually replace registry-based AST inference with typed calls.

**Why it beats SOTA:** Static lint and runtime type adapters each exist elsewhere. Here they become a three-layer contract—type, AST, and real asyncpg round trip—seeded by the exact double-encoding scar and measured against protected call sites.

**Cost:** 12–20 hours across incremental PRs.

**Gear:** 2; Gear 3 for global codec changes.

**Risk/scar family:** #9. A flag-day adapter conversion would create broad regression risk.

**Metric:** Before: one incident produced 64,721 errors; protected surfaces are maintained manually. After: 100% of protected writes pass round-trip mutation tests; zero JSONB scalar/object mismatches for 90 days.

**Kill criterion:** Stop type rollout if it requires changing more than 15% of call sites without reducing the manual registry.

**First PR:** Add a real-codec round-trip test and adapter for one outbox call site, leaving global registration untouched; ≤250 lines in the JSONB guard test surface and a new adapter module.

### 5. Per-handler Durability Receipts — score 7.8

**What:** Extend outbox delivery from dispatcher acknowledgement to a receipt keyed by `(outbox_id, handler_id, handler_version)`, with idempotency, retry state, poison quarantine, and reconciliation. Keep domain/outbox insertion atomic. Make retention of receipts policy-driven rather than deleting them on a generic clock.

**Why it beats SOTA:** Transactional outbox and CDC are standard. The additional proof chain—domain commit → outbox row → each handler/version → side-effect receipt—fits Nuzantara’s multi-organ local architecture and makes durability claims mechanically auditable without installing a central cloud broker.

**Cost:** 24–36 hours and one migration; flat-sub review only.

**Gear:** 3.

**Risk/scar family:** #9; a malformed state transition could reproduce W53/W61 storms.

**Metric:** Before: dispatcher-level acknowledgement and 60-minute replay. After: zero silently unhandled events in fault injection; 100% receipt reconciliation; recovery horizon explicitly measured rather than inferred.

**Kill criterion:** Reject the design if steady-state write amplification exceeds 20% or receipt reconciliation cannot remain bounded without polling.

**First PR:** Add the receipt schema and failure-state model plus tests, without changing dispatch; ≤400 net lines in one migration and `apps/backend-rag/backend/tests/services/events/`.

### 6. Cross-store Versioned Cutover Cell — score 7.2

**What:** For high-risk changes only, couple relational expand/contract with versioned Qdrant collection names, immutable embedding/index manifests, dual population, shadow reads, quality comparison, and one atomic alias cutover. Old schema and old vector alias remain available through the observation window.

**Why it beats SOTA:** pgroll versions relational schemas; Qdrant supports aliases and snapshots. The beyond-SOTA element is a single cutover contract across SQL semantics, embedding version, payload schema, retrieval thresholds, and rollback evidence.

**Cost:** 28–40 hours plus temporary Qdrant capacity approaching 2× for selected collections.

**Gear:** 3.

**Risk/scar family:** #2 and #9. Two live versions can become permanent drift if completion is not enforced.

**Metric:** Before: dated estate audit found six of 20 definitions aligned. After: 100% of live collections mapped to an immutable manifest and alias; shadow-result agreement ≥99% on frozen evaluation queries; alias rollback under 60 seconds.

**Kill criterion:** Do not generalize beyond pilot if temporary capacity exceeds 2.2× or shadow traffic adds over 15% p95 latency.

**First PR:** Add a read-only collection-manifest and alias-drift checker, with no cutover capability; ≤300 lines plus tests.

### 7. Retention Policy Compiler — score 6.8

**What:** Compile each approved retention decision into a versioned policy artifact containing purpose, scope, authority, duration/floor, legal hold, erasure mode, binder function, dry-run query, expected affected-row bounds, and evidence retention. Generate catalog assertions and tests; do not let a generic retention worker infer policy from table names.

**Why it beats SOTA:** Policy-as-code exists, but this composition binds legal ruling, role capability, database predicate, dry-run evidence, and post-execution proof while preventing one scope—such as the five-year conversation floor—from leaking into another.

**Cost:** 18–28 hours after policy rulings.

**Gear:** 3.

**Risk/scar family:** #2 and #9. A technically valid compiler can encode a wrong business/legal ruling perfectly.

**Metric:** Before: Visa runbooks unarmed/NO-GO at last verification. After: 100% of deletable scopes have approved artifacts and mutation tests; zero out-of-scope rows affected; dry-run/apply count delta is zero.

**Kill criterion:** Halt activation on any unexplained dry-run/apply delta or if policy scope cannot be reviewed without exposing PII.

**First PR:** Add a schema-only policy validator for existing Visa artifacts; no deletion or activation; ≤300 lines.

## 6. 90-day roadmap + first PRs

### Wave 1 — Days 0–30: make false-green migrations impossible

1. Pin Squawk, target PostgreSQL 17.7, restore timeout rules, and add `merge_group`.
2. Enforce applied-migration checksum immutability and postconditions.
3. Add a production-codec JSONB round-trip test.
4. Define the PII-free authority-manifest schema.
5. Make restore SQL errors fatal.

Acceptance at day 30: no migration can be marked applied after a declined guard; PG17 is the lint target; JSONB object/array round trips are proven; restore stops on the first SQL error.

### Wave 2 — Days 31–60: reproduce production authority and recovery

1. Build the minimal authority twin with W38/W130 fixtures.
2. Execute new migrations as the intended runtime/migrator role.
3. Verify owners, grants, RLS, SECDEF properties, and constraints after restore.
4. Run the first Postgres restore proof and record actual RPO/RTO.
5. Add a read-only Qdrant manifest/alias drift report.

Acceptance at day 60: all new migrations pass under role-faithful execution; zero unexplained catalog deltas; one independently inspectable restore manifest exists; every live Qdrant collection observed by the checker is classified.

### Wave 3 — Days 61–90: versioned cutovers and end-to-end durability

1. Pilot expand/contract on one non-critical relational change.
2. Pilot versioned Qdrant alias cutover on one bounded collection.
3. Add outbox receipt schema and fault-injection tests without immediately switching production dispatch.
4. Compile one approved retention scope into an executable policy artifact.
5. Require the evidence envelope for all new migrations.

Acceptance at day 90: one relational and one vector cutover can roll back inside 60 seconds; fault injection produces no silent handler loss; restore proofs meet approved RPO/RTO for four consecutive weeks.

### First PR register

| PR title | Files | Net-line cap | Gear | Acceptance test |
|---|---|---:|---:|---|
| `fix(migrations): reject applied checksum drift` | `apps/backend-rag/backend/db/migration_base.py`; `apps/backend-rag/backend/db/migration_manager.py`; focused DB tests | 300 | 3 | Editing an applied fixture makes discovery fail before SQL execution. |
| `ci(migrations): pin squawk and lint postgres 17` | `.github/workflows/migration-lint.yml` | 120 | 2 | Workflow uses a fixed Squawk version, PG17 target, timeouts, and runs on `merge_group`. |
| `test(db): prove jsonb codec round trips` | `apps/backend-rag/backend/tests/db/test_jsonb_double_encoding_class_guard.py`; new round-trip test | 250 | 2 | Dict/list remain object/array; serialized text follows the explicit text path; mutation fails. |
| `feat(db): validate authority manifest` | new `scripts/postgres_authority_manifest.py`; new DB test | 350 | 3 | W130 owner/membership fixture fails under runtime identity and passes only under declared capability. |
| `fix(backup): make restore drill evidentiary` | `.github/workflows/restore-drill.yml`; new `scripts/verify_restored_database.py` | 380 | 3 | Injected restore error fails; catalog owner/grant/constraint mismatch fails. |
| `feat(qdrant): report manifest and alias drift` | new read-only checker; `docs/runbooks/qdrant-estate-reconciliation.md` | 300 | 2 | Fixture detects undocumented live collection, dead declaration, dimension mismatch, and missing alias. |
| `feat(events): model per-handler receipts` | one new `migrations_v2` SQL file; `apps/backend-rag/backend/tests/services/events/` | 400 | 3 | Handler crash leaves an actionable receipt; retry is idempotent; poison state cannot storm. |
| `feat(retention): validate policy artifact` | new validator; existing Visa retention runbook fixtures | 300 | 3 | Missing authority, legal hold, scope, or dry-run bound fails closed; no data is deleted. |

## 7. Needs-ruling

1. **`needs-ruling` — Production role topology:** approve creation or normalization of a dedicated migrator capability separate from the runtime role, including which NOLOGIN role owns application objects and which memberships exist only for deploy duration.

2. **`needs-ruling` — Retention authority:** confirm the legal/business basis, legal-hold behavior, and erasure mechanism for each data class. The five-year conversation doctrine must not be inherited into Visa, claims, analytics, or outbox receipts without an explicit ruling.

3. **`needs-ruling` — Restore objectives:** set acceptable Postgres/Qdrant RPO, RTO, evidence-retention period, and local storage budget. Without those numbers, a restore drill can pass technically while failing the business need.

4. **`needs-ruling` — Restore credentials/GUI action:** provision or approve the required Tigris/Fly credentials for the restore workflow. This lane did not inspect secrets and could not establish the last successful run.

5. **`needs-ruling` — High-risk cutover authority:** decide whether Gear-3 relational/vector cutovers require an attended release window and explicit Zero approval before contract/drop or alias switch.

6. **`needs-ruling` — Temporary vector capacity:** approve the storage/RAM envelope for dual collections during the Qdrant migration pilot.

## 8. §Meta-pattern

The single defective belief is:

> **“If the SQL is valid against the expected schema, the data change is valid.”**

Every major finding is a variation of its falsity:

- W38/W130: columns were correct; execution identity was wrong.
- W131: schema was correct; clone lineage was wrong.
- JSONB: Python and SQL shapes looked correct; wire encoding changed the value.
- Migration 289: SQL could decline safely; the ledger could still lie.
- Migration 296: inverse SQL existed; historical data made rollback destructive.
- Qdrant: declarations existed; live collections and aliases diverged.
- Retention: policy code existed; authority and activation did not.
- Backup: artifacts existed; restorability was unproved.
- Outbox: dispatch completed; a handler could still fail.

The replacement belief should be executable:

> **A data change exists only when it has run under the production authority and historical topology, satisfied explicit invariants, preserved compatible consumers, and emitted replayable proof of forward state, rollback class, and restoreability.**

That doctrine collapses many incident-specific guards into one lifecycle: **model authority → rehearse history → execute compatibly → verify catalog and semantics → retain proof → restore it elsewhere**.

## 9. Sources

1. [Stripe — “Online migrations at scale”](https://stripe.com/blog/online-migrations), 2017-02-02; accessed 2026-08-29. Primary engineering account of a hundreds-of-millions-object online migration.

2. [Xata — pgroll](https://github.com/xataio/pgroll), continuously maintained; accessed 2026-08-29. Primary implementation and documentation for PostgreSQL versioned-schema expand/contract migrations.

3. [Squawk — “Applying migrations safely”](https://github.com/sbdchd/squawk/blob/master/docs/docs/safe_migrations.md), continuously maintained; accessed 2026-08-29. Primary safety requirements from the migration linter used by the repository.

4. [PostgreSQL — `CREATE FUNCTION`](https://www.postgresql.org/docs/current/sql-createfunction.html), current documentation; accessed 2026-08-29. Normative source for ownership and safe `SECURITY DEFINER` construction.

5. [PostgreSQL 17 — Row Security Policies](https://www.postgresql.org/docs/17/ddl-rowsecurity.html), PostgreSQL 17 documentation; accessed 2026-08-29. Normative RLS/default-deny and owner-bypass behavior.

6. [GitHub — gh-ost](https://github.com/github/gh-ost), continuously maintained; accessed 2026-08-29. Primary implementation documenting replica rehearsal, throttling, checksums, and delayed cutover.

7. [pgTAP documentation](https://pgtap.org/documentation.html), version 1.3.4 documentation; accessed 2026-08-29. Primary SQL-native database testing reference.

8. [Debezium — Outbox Event Router](https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html), stable documentation; accessed 2026-08-29. Primary implementation reference for transactional outbox plus CDC routing.

9. [PostgreSQL 17 — Continuous Archiving and PITR](https://www.postgresql.org/docs/17/continuous-archiving.html), PostgreSQL 17 documentation; accessed 2026-08-29. Normative source for base-backup and continuous-WAL recovery requirements.

10. [Fly.io — Backup, Restores, & Snapshots](https://fly.io/docs/postgres/managing/backup-and-restore/), current documentation; accessed 2026-08-29. Primary platform guidance clarifying operator responsibility for unmanaged Postgres recovery.

11. [Qdrant — Snapshots](https://qdrant.tech/documentation/snapshots/), current documentation; accessed 2026-08-29. Primary source for collection snapshot contents and the exclusion of aliases.

12. [Qdrant — Migration and Recovery Options](https://qdrant.tech/documentation/migration-recovery-options/), current documentation; accessed 2026-08-29. Primary comparison of streaming migration, snapshots, backups, and capacity requirements.

13. [Chen et al. — “An Empirical Study on the Characteristics of Database Access Bugs in Java Applications”](https://arxiv.org/abs/2405.15008), 2024. Empirical study of 423 database-access bugs across seven systems.

14. [“Managing semantic evolution in databases: From theory to implementation”](https://doi.org/10.1016/j.future.2025.108257), 2025. Peer-reviewed evaluation over six million records and 170 semantic-evolution events.