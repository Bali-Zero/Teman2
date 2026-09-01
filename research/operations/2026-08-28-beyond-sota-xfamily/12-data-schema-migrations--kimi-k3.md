---
panel: beyond-sota-xfamily
lane: 12-data-schema-migrations
seat: kimi-k3
model: "kimi-code/k3 · Kimi CLI print mode (tools)"
started: 2026-08-28T19:08:42Z
finished: 2026-08-28T19:16:42Z
duration_s: 480
exit: 0
words: 3980
prompt_sha256_16: 8ab0bb28d2c6206e
prompt_chars: 18668
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

• [Pro snapshot] Grounding first: migrations inventory, workflows, and the superscar file.

• Grounding continues: scars, workflows, and key migration files.

• Grounding done. Now the web SOTA survey — batching searches.

• All evidence gathered. Composing the report.

  ---

  ```markdown
  ---
  date: 2026-08-28
  domain: operations
  panel: beyond-sota-2026-08-28
  part: 12/13 — Data, schema & migration engineering
  model: Moonshot Kimi K3 (pinned lane)
  sources: 16
  repo_files_verified: 34
  ---

  # Lane 12 — Data, schema & migration engineering

  ## 0. TL;DR

  Nuzantara's data layer is **AT SOTA on migration file discipline and AHEAD on codified invariants, but BEHIND on role separation, prod-shaped testing, and vector-estate hygiene** — the same identity/boundary confusion generates nearly every scar in this area. Biggest gap: the migration runner still executes as the runtime application role (`migration_manager.py:96` defaults to `settings.database_url`; zero hits for `ADMIN_DATABASE_URL` anywhere in `apps/backend-rag/backend/`), fourteen months after the W38 spec (2026-05-23) drafted exactly that split — so ledger-owned SECURITY DEFINER DDL can still abort a deploy, and it did (migration 289's 481-line header is the autopsy). Top-3 moves: (1) ship the runtime/migration role split plus a CI role-identity pin; (2) turn the monthly restore drill into a **migration shadow-apply rehearsal** against the restored prod copy (prod-shaped rehearsal at zero marginal cost); (3) machine-extract the schema invariants already written as prose in migration headers into a registry that CI diffs against reader code — the 289 failure class (invariant widened, pre-existing readers not revisited) then fails at PR time instead of as a 2026-08-26 prod outage.

  ## 1. How Nuzantara does it today

  **Migration corpus.** `apps/backend-rag/backend/db/migrations_v2/` holds **174 SQL files** (175 entries incl. `LEGACY_PROMOTION_README.md`), numbered 092→296 with gaps; **170/174 (97.7%) carry the `-- === ROLLBACK ===` marker** (verified by grep this session). Cadence measured from git history: 9 (Feb) → 30 (Apr) → **70 (May)** → 42 (Jun) → 21 (Jul) → 18 (Aug 2026) — roughly 20–40 migrations/month sustained. The runner (`backend/db/migration_manager.py:89-98`) wraps each file in a single asyncpg transaction (`migration_base.py:493` per the Squawk workflow comment) and requires the inline rollback marker for every number >111 (`migration_base.py:239`, per `lint-migration-rollback.yml`).

  **Lint triple-gate.** `.github/workflows/migration-lint.yml` runs Squawk on changed migrations only (job-level change detection, no top-level `paths:` — the sentinel pattern; 13 documented rule exclusions, each justified per-migration). `.github/workflows/lint-migration-numbers.yml` blocks duplicate NNN prefixes (W40/W41). `.github/workflows/lint-migration-rollback.yml` runs `scripts/lint_migration_rollback.py` (W42). The number/rollback lints trigger on **both PR and push-to-main** (W41 lesson: PR-only triggers are bypassed by L2 direct-push).

  **Roles & ownership.** Only **5 `OWNER TO` references** exist across all 174 files, and exactly **one real target role: `visa_ledger_owner`** (the other 4 are prose). 11 migrations use `SECURITY DEFINER`. Migration 268 established the canonical pattern: role-guarded, idempotent, best-effort `ALTER FUNCTION … OWNER TO visa_ledger_owner` inside `DO` blocks, with `SECURITY DEFINER` + `SET search_path` restated verbatim on every `CREATE OR REPLACE` (289 header §"OWNERSHIP / SECURITY DEFINER" explains why omitting it silently demotes to INVOKER). **But the runner connects with the runtime DSN** (`migration_manager.py:96`: `database_url or settings.database_url`); `ADMIN_DATABASE_URL` — Stage B of the W38 spec (`research/operations/specs/W38-backend-rag-v2-nosuperuser.md`, referenced in `cicatrix-scars-archive.md:2698`) — appears **nowhere in the codebase**. Read-only inspection goes through the `nuzantara_readonly` role via MCP (CLAUDE.md §10: 255 SELECT grants, zero writes), canonicalized into `scripts/pg.sh` after W87 (`cicatrix-scars.md:479`).

  **Invariants & tripwires.** CLAUDE.md §9 pins: frozen embedding `text-embedding-3-small`/1536; KBLI flat payload **Qdrant-only** (the Postgres `kbli_documents` table is a different, 6-column, metadata-nested store — corrected 2026-07-21); **5 named abstain thresholds** with SSOT `backend/services/rag/agentic/_abstain_policy.py` (GENERATION 0.15 flat; LABEL per-domain tax 0.10/visa 0.12/kbli 0.20; CONFIDENCE edges 0.15/0.60; CONTEXT_QUALITY_MIN 0.15 — the generation≠label divergence is panel-ruled intentional, tripwire-enforced). `backend/tests/test_data_invariant_tripwires.py` (376 lines) carries ~10 test functions over 5 invariants (lead-source enum subset, frozen embedding, pricing contact block, kbli_documents metadata-not-flat, no-plaintext-PIN roster). `.github/workflows/catD-backend-data-invariants.yml` adds CI pins: health.py must advertise `"dimensions": 1536`, the avatar_url data-URI AST lint, and the reachability antibody staying collected.

  **Test DB shape.** Mixed. `backend/tests/conftest.py` provides `mock_db_pool` as a **MagicMock** (line 92-124) — unit tests never touch a real codec. CI historically bootstrapped its schema via `ci_bootstrap_schema.py` (`SQLModel.metadata.create_all()` + raw DDL), a **different recipe than prod**; `LEGACY_PROMOTION_README.md` documents this as "the root cause of several schema drifts" and the promotion of 8 bootstrap DDLs into idempotent v2 migrations. Double-encoding scars confirm the gap: jsonb codec behavior only manifests on a real asyncpg connection.

  **jsonb.** The double-encoding trap is systemic and documented in-place: at least 8 code sites carry anti-double-encode comments (`knowledge_visa.py:306`, `crm_practices.py:569`, `crm_clients_documents.py:424`, `conversations.py:265`, `dream.py:82` citing memory `discovery_jsonb_double_encoding_systemic_2026_05_14`, `frontend_metrics.py:68`, `notifications/service.py:139`). Defense is currently **per-callsite vigilance comments**, not a codec-layer guarantee.

  **Outbox durability.** SYMBIOSIS Legge 3/4 (`SYMBIOSIS.md:262-270`): `events_outbox` (migration 144) with atomic insert in the trigger's own transaction, replay-on-reconnect capped at `max_age_minutes=60`, idempotent consumer ack via `_outbox_id`; **known limit**: ack is dispatcher-level, not per-handler (a crash inside a handler leaves the row consumed; "fase 2" per-handler ack is named but unshipped). 16 channels in `PG_CHANNEL_MAP`, count pinned by `catA-channel-count-pin.yml`. Every durability promise must cite a test, enforced by `scripts/lint_symbiosis_promises.py` — promise-as-code.

  **Retention.** `backend/core/retention_policy.py`: `RETENTION_MIN_DAYS = 1826` (5 years, leap-inclusive), `enforce_retention_floor()` raises `RetentionPolicyViolation` on any shorter window; **no clock-driven delete before 2030-12-31**; env kill-switch `CONVERSATION_RETENTION_ALLOW_CLOCK_DELETE`. Visa-side retention is **policy-row-driven in the DB itself**: migration 264 created `visa_decision_retention_policies` (one active row per environment, exclusion constraint); 281 widened it to `policy_scope` (VISA_DECISION | GARUDA_CHECK | GARUDA_ORDER; 285 added GARUDA_MAGIC_LINK) — which broke the unscoped Visa binders and caused the 2026-08-26 outage fixed by 289. Runbook `docs/runbooks/visa-oracle-retention-operations.md` defines a staged activation ceremony with PII-free evidence.

  **Qdrant estate.** `backend/core/collection_registry.py` (102 lines) maps logical→physical collection names with aliases. `docs/runbooks/qdrant-estate-reconciliation.md` (TAC-2 A6) measured the drift: **6 collections defined∧live, 14 defined-but-dead, 8 live-but-undocumented**, plus a second competing registry ("why '20 defined' meant two different things"). Embedding model frozen at 1536 dims, pinned in CI by catD.

  **Backup/restore.** `.github/workflows/restore-drill.yml`: monthly (1st, 04:00 UTC) restore of the latest daily pg_dump from Tigris (`nuzantara-backups/postgres/`) into a **postgis/postgis:17-3.5** CI service (PostGIS needed because prod's `clients` has a geometry column — a lesson the drill itself surfaced), with sanity gates (≥50 tables, `clients`/`practices` queryable, >1MB dump) and Telegram both ways. WAL archiving was re-enabled 2026-08-09 after discovery that a legacy override had disabled it — "DONE" backups were not restorable (CLAUDE.md §11). The workflow header notes Tigris repo secrets were **absent as of 2026-06-05** (preflight distinguishes setup-gap from corrupt-backup).

  **MEM note.** The lane brief's nine `MEM:` files are **unavailable in this read-only snapshot** (no access outside the repo). Each claim was re-derived from repo evidence instead: the runtime-role runner (confirmed by grep above), jsonb double-encoding (confirmed via in-code comments + the 2026-05-14 memory citation), the policy_scope grant (confirmed via 289's `DO`-block ceremony), the NOSUPERUSER demotion (W38 body in `cicatrix-scars-archive.md:2698`), five-year retention (`retention_policy.py:45`). Where a MEM claim could not be re-verified, it is not asserted below.

  ## 2. Scars & ledger evidence in this area

  | Scar | Date | What bit | Recurred? |
  |---|---|---|---|
  | **W38** | 2026-05-23 | App role `backend_rag_v2` was superuser; demotion spec drafted, executed by 2026-06-11; **Stage B (`ADMIN_DATABASE_URL`) never shipped**; 2 app superusers (`nuzantara_rag`, `backend_ts_user`) still elevated | Partially — follow-up open 15 months |
  | **W40/W41/W42** | 2026-04-29/05-23 | Migration 194 number collision applied wrong file silently; PR-only lint bypassed by direct-push; rollback marker missing blocked ALL pending migrations at import | No — triple lint + push triggers hold |
  | **W87** | 2026-06-26 | Dev identity (`nuzantara_dev_readonly`) pointed at prod proxy `:15432`; MCP "✔ Connected" but dead on first query — Esiste≠Armato at the credential layer | Superscar #2 member |
  | **W106** | 2026-07-26 | Credential-world inversion killed prod PG backup for **27h**; error message accused the working credential | Superscar #9 member |
  | **jsonb double-encode** | 2026-05-14 → 2026-08-27 | Systemic; mocked test pools hide it; 8+ callsite guards | **Yes, repeatedly** — the MEM title of 2026-08-27 says test pools still hide it |
  | **289 outage** | 2026-08-26 | Retention invariant widened (env → env+scope); two unscoped binders + `count(*)==1` Python gate → Visa Oracle answered `RETENTION_POLICY_UNAVAILABLE` to everyone | Newest instance of the widening class |
  | **WAL archiving disabled** | found 2026-08-09 | "DONE" backups unrestorable; caught only by an isolated restore proof before the 17.2→17.7 upgrade | Once, severe |
  | **W53/W54/W61/W88 (#9)** | — | State-schema mutation drift: payload format changed, downstream readers not aligned | The superscar family 289 belongs to |

  Pattern across the ledger: **not one of these is a SQL-syntax failure.** Every one is an *identity/boundary* failure — wrong role, wrong credential, wrong environment, wrong invariant version, wrong codec assumption, wrong schema recipe (CI bootstrap ≠ prod). The lint trio (W40-42 antibodies) is the only family that fully closed, because it guards a property that is *mechanically checkable at rest* (filename, marker). Everything that requires the DB to be *alive and correctly addressed* has recurred.

  ## 3. World SOTA survey

  | System/practice | Source (date) | Mechanism | Measured effect | Transfer here |
  |---|---|---|---|---|
  | **pgroll** (Xata) | [xata.io blog](https://xata.io/blog/pgroll-schema-migrations-postgres), [Neon guide](https://neon.com/guides/pgroll) (2025-2026) | Expand/contract automated: multiple schema versions coexist as views; instant rollback | Zero-downtime breaking changes without app coordination | Medium — runner is single-transaction asyncpg; pgroll would replace it. Valuable only when tables get big; today most migrations document a near-empty-table premise |
  | **gh-ost** (GitHub) | [github/gh-ost](https://deepwiki.com/github/gh-ost) (2025) | Triggerless online MySQL migration via binlog; pausable, throttleable | Multiple schema migrations daily at 5.5M QPS | Low directly (MySQL), but the *operational* ideas — pause/throttle/cut-over control — map to any future large backfill |
  | **Expand/contract pattern** | [Harness](https://www.harness.io/blog/zero-downtime-database-migrations-safe-schema-changes) (2026-07), [Wellhausen paper](https://www.tim-wellhausen.de/papers/ExpandAndContract/ExpandAndContract.html) | No two adjacent deploy states conflict; nullable-add → backfill → dual-write → contract | Industry standard for zero-downtime | High as *discipline*; Nuzantara applies it ad hoc (296 retires an index invariant in one step — correct, but the pattern is manual) |
  | **SECURITY DEFINER hardening** | [Cybertec](https://www.cybertec-postgresql.com/en/abusing-security-definer-functions/) (2023-2026), PG docs | Fixed `search_path`, dedicated non-login owner, revoke PUBLIC | Prevents RLS bypass/privesc | **Nuzantara already does this** (268/289 restate `SET search_path` verbatim) — genuinely AT/AHEAD |
  | **Transactional outbox + CDC** | [Conduktor](https://www.conduktor.io/glossary/outbox-pattern-for-reliable-event-publishing) (2026), [Debezium pattern](https://risingwave.com/blog/debezium-outbox-pattern-microservices/) (2026) | Event row in same tx as business write; CDC relay | No dual-write loss | Nuzantara implements the core (144/146) **plus** replay-cap and promise-linting; Debezium/Kafka is overkill at this scale. AT |
  | **Crypto-shredding** | [Thoughtworks Radar](https://www.thoughtworks.com/content/dam/thoughtworks/documents/radar/2018/11/tr_technology_radar_vol_19_en.pdf), [Conduktor](https://www.conduktor.io/glossary/crypto-shredding-for-kafka) (2026) | Per-subject keys; erasure = key deletion; resolves retention-floor vs erasure-right conflict | GDPR Art.17 under legal hold | High and **needed**: 5-year never-delete floor vs UU PDP erasure is an unresolved contradiction (needs-ruling) |
  | **Restore drills** | [pgBackRest guides](https://shivam2003.com/posts/pgbackrest-s3-guide) (2026-07), [mydbops](https://www.mydbops.com/blog/best-postgresql-backup-and-recovery-tools) (2025) | Scheduled restore to scratch + `pg_amcheck`; measure restore/WAL-replay time | "The first drill will find something broken" — and Nuzantara's did (PGPASSWORD scope bug, PostGIS, WAL archiving) | Nuzantara's monthly drill is AT SOTA cadence; missing PITR proof and restore-time metrics |
  | **Schema-as-code declarative** | [Atlas vs others](https://atlasgo.io/atlas-vs-others) (2026), [comparison](https://blog.codercops.com/blog/database-schema-migration-tools-compared/) (2026-08) | Desired-state diff vs versioned replay; Atlas lint now paywalled (noted in repo's own Squawk comment) | — | Low — versioned SQL + tripwires fits; the org consciously chose Squawk over Atlas |
  | **pgTAP** | [pgtap.org](https://pgtap.org/), [Capital One](https://www.capitalone.com/tech/software-engineering/automated-postgres-unit-testing/) (2024) | In-database unit tests for functions/triggers/RLS | — | Medium-high — the visa/garuda SECURITY DEFINER functions are exactly the code pgTAP exists to test; today they're tested via Python only |
  | **Embedding model migration** | [Qdrant tutorial](https://qdrant.tech/documentation/tutorials-operations/embedding-model-migration/), [AI/TLDR](https://ai-tldr.dev/learn/embeddings-vector-databases/vectors-in-production/embedding-model-migration/) (2026) | Blue-green collections, shadow traffic, per-vector model version stamps | — | High as *preparedness*: model is frozen, but there is no written blue-green runbook for the day OpenAI deprecates it |
  | **Fly Postgres reality** | [Fly community](https://community.fly.io/t/postgres-cluster-machine-failure-causes-inconsistent-repmgr-state/23507) (2025), [Fly infra-log](https://fly.io/infra-log/) (2026-08) | repmgr flex is not a managed HA service; failover state can stick | Stuck "Unknown" role incidents | Confirms backup/restore drill weight > failover trust; already aligned |

  The five that matter most:

  1. **pgroll's multi-version schema** is the true frontier, but its value scales with table size and deploy frequency. At 20-40 migrations/month on mostly-young tables, Nuzantara's single-transaction runner + rollback markers is proportionate; the *borrowable* piece is pgroll's **instant rollback by schema-version coexistence**, which would dissolve 296's documented "NOT ALWAYS REVERSIBLE" rollback class.
  2. **SECURITY DEFINER hygiene** — the repo's 268 pattern (role-guarded OWNER TO, verbatim search_path restatement, TOO_MANY_ROWS backstops) matches the best published guidance; this is a verified AHEAD.
  3. **Crypto-shredding** is the one SOTA practice with no footprint here, and it sits directly on the retention floor's contradiction.
  4. **Restore drills** — the org already runs the gold-standard cadence; the next rung (PITR proof, restore-duration metrics, migration shadow-apply on the restored copy) is cheap because the pipeline exists.
  5. **pgTAP** — in-DB tests would have caught 289's binder defect at migration time (the failing predicate is pure SQL: two rows match an unscoped `INTO STRICT`), where Python-side tests could not see it until deploy.

  ## 4. Position vs SOTA

  | Sub-dimension | Verdict | Evidence |
  |---|---|---|
  | Migration file discipline (numbering, rollback, lint) | **AHEAD** | Triple CI lint + runtime gate + 97.7% marker coverage; W40-42 closed with no recurrence |
  | Runner privilege design | **BEHIND** | Runner = runtime role (`migration_manager.py:96`); `ADMIN_DATABASE_URL` absent repo-wide; W38 Stage B unshipped since 2026-05-23 |
  | Least-privilege roles overall | **BEHIND** | 2 app superusers remain (W38 follow-up); W87/W106 credential-identity incidents |
  | SECURITY DEFINER craft | **AHEAD** | 268/281/286/289 idempotent role-guarded pattern; search_path restated both directions |
  | Zero-downtime / expand-contract | **AT** | Correct single-step changes on young tables (296 header); no framework, no multi-version schema; near-empty-table premise documented per migration |
  | Prod-shaped test DB | **BEHIND** | CI bootstrap recipe ≠ prod (LEGACY_PROMOTION_README); unit pools are MagicMock (conftest.py:92); jsonb defects escape to prod |
  | Invariants as code | **AHEAD** | 5 named abstain gates with SSOT + tripwires; catD pins; promise-lint requiring `Test:` citations |
  | Outbox durability | **AT** | Full transactional outbox + replay + idempotent ack; per-handler ack gap admitted in SYMBIOSIS:262 |
  | Qdrant estate governance | **BEHIND** | 14 dead definitions / 8 undocumented live (qdrant-estate-reconciliation.md); two competing registries |
  | Embedding freeze enforcement | **AHEAD** | CI pin on the 1536 literal + frozen-model tripwire — drift fails the build |
  | Retention engineering | **AHEAD (design) / BEHIND (erasure)** | Policy-as-code floor with typed violation; but no crypto-shredding answer to erasure-vs-floor |
  | Backup/restore proof | **AT** | Monthly drill with real sanity gates; no PITR, no restore-time metric, Tigris-secret gap historically |
  | In-DB testing (pgTAP-class) | **BEHIND** | Zero in-DB tests for 11 SECURITY DEFINER migrations; binder defect class invisible pre-deploy |

  ## 5. Beyond-SOTA recommendations

  **R1 — Migration shadow-apply on the restore artifact (gear 2).** Extend `restore-drill.yml` with a final step: after the prod dump restores into the CI Postgres, run `python -m backend.db.migrate apply-all` (or a dry-run diff) against it. *Why beyond-SOTA:* surveyed drill practice stops at "restores + row counts"; nobody closes the loop "the backup is also the migration rehearsal stage." *Asymmetry:* the drill, the dump, and the runner already exist — this is wiring, ~80 lines. *Cost:* one CI job step, no tokens. *Metric:* count of deploy-aborting migration failures (289/ledger-owner class) — baseline ≥2 in Aug 2026 (289 fix, 296 review rounds); target 0/quarter. *Risk:* scar family #2 (drill green but rehearsal silently skipped) — mitigated by making the step fail the drill, not warn. *Kill criterion:* two consecutive quarters with zero caught defects → demote to warning-only. *First PR:* `restore-drill.yml` + `scripts/ci/migration_shadow_apply.sh`, ≤150 lines.

  **R2 — Ship W38 Stage B + role-identity CI pin (gear 2).** Add `ADMIN_DATABASE_URL` support to `migration_manager.py` (prefer admin DSN, fallback runtime with loud warning), and a catD-style lint that fails if `migration_manager.py` ever connects with the same role the routers use. *Why beyond-SOTA:* least-privilege migration runners exist (Flyway/Atlas separate credentials), but no surveyed system **pins the separation as a CI-checked invariant against regression** — the pin is the Nuzantara-native move (catD pattern transplanted). *Cost:* ~2h + a Fly secret (needs operator to set it — needs-ruling-adjacent, mechanical). *Metric:* runner session role ≠ app role, verified in the shadow-apply step from R1 (measurable: `SELECT current_user` asserted in CI). *Risk:* family #4 if the admin DSN leaks into logs — the runner must never print the DSN. *Kill criterion:* n/a (permanent hardening). *First PR:* `migration_manager.py` + `scripts/lint_migration_role_split.py`, ≤200 lines.

  **R3 — Invariant registry extracted from migration headers (gear 3).** The 174 headers already state their invariants in disciplined prose ("one active row per (environment, scope)", "ONE codex leg IN FLIGHT"). Add a machine-readable `INVARIANT:` block per hot migration + `scripts/lint_invariant_readers.py` that, when a migration *widens* a constraint (grep-detectable: exclusion-constraint column add, unique-index scope change), fails CI unless the PR touches or explicitly waives every registered reader of that table. *Why beyond-SOTA:* schema linters (Squawk/Atlas) check DDL safety; **nothing checks that the humans' invariant change was propagated to readers** — 289 is precisely this hole, and the scar corpus gives the reader registry its seed data. *Cost:* ~1 day + flat-sub tokens for the reader census. *Metric:* invariant-widening PRs landing with an un-audited reader — baseline 1 (281→289 outage); target 0. *Risk:* family #3 (substring over/under-match in the reader detection) — needs guilt+innocence tests per `infra/guard-conformance/`. *Kill criterion:* >30% false-positive rate on innocent PRs after 60 days → narrow to a reader-registry checklist gate. *First PR:* `scripts/lint_invariant_readers.py` + registry YAML seed for `visa_decision_retention_policies` + `broker_jobs`, ≤300 lines.

  **R4 — jsonb codec round-trip tripwire on a real pool (gear 1).** One integration test module that, per registered jsonb column, writes a dict through the production pool factory and asserts read-back identity (`==`, not string compare). *Why beyond-SOTA:* it converts eight scattered vigilance comments into one mechanical guarantee at the layer where the defect lives (the codec), and the registry makes every *new* jsonb column opt into the test — no surveyed system ships a per-column codec identity gate. *Metric:* double-encode incidents — baseline: 8 guarded callsites + 2026-08-27 recurrence; target 0 in 90 days. *Cost:* ~3h. *Risk:* family #2 if the test silently skips when no DB is available — must fail, not skip (catD lesson). *Kill criterion:* none; permanent tripwire. *First PR:* `backend/tests/integration/test_jsonb_codec_identity.py` + column registry, ≤200 lines.

  **R5 — Qdrant estate pin (gear 1).** Weekly CI job: live collection list (read-only) vs `collection_registry.py`; fail on drift either direction; decommission the 14 dead definitions and document or drop the 8 orphans per the reconciliation runbook's decision proposal. *Metric:* defined∧live ratio 6/28 → 100% of a pruned registry. *Cost:* ~2h. *Risk:* family #2 (non-required check nobody reads) — make it required after one stable cycle, with skip→success sentinel. *First PR:* `scripts/ci/qdrant_estate_pin.py` + workflow, ≤150 lines.

  **R6 — Crypto-shredding design for the erasure-vs-floor conflict (gear 3, needs-ruling).** Per-subject envelope keys for conversation payloads; erasure request = key destruction, satisfying UU PDP erasure without violating the 5-year row floor (ciphertext remains, unreadable). No surveyed piece here covers it; Thoughtworks/Conduktor give the pattern. *Metric:* erasure-request latency (days → minutes) + zero floor violations. *Kill criterion:* legal review rejects key-destruction as erasure under UU PDP → fall back to scoped deletion exceptions.

  ## 6. 90-day roadmap + first PRs

  **Wave 1 (days 1-30) — close the identity gap.** R2 (role split + pin), R4 (codec tripwire), R5 (estate pin). All gear 1-2, all ≤200-line PRs, all measurable on arrival. First PR: "migration runner prefers ADMIN_DATABASE_URL + CI role pin" — files `apps/backend-rag/backend/db/migration_manager.py`, `scripts/lint_migration_role_split.py`, `.github/workflows/catD-backend-data-invariants.yml` (one added step); acceptance: CI fails if runner and router roles match, shadow-run prints `current_user` for both.

  **Wave 2 (days 31-60) — rehearsal loop.** R1 shadow-apply; pgTAP pilot on the three visa retention functions (the highest-blast-radius SQL in the repo). First PR: "restore drill shadow-applies pending migrations" — acceptance: drill log shows pending-migration apply result and fails the workflow on error.

  **Wave 3 (days 61-90) — intent propagation.** R3 invariant registry seeded from the 289/296/281/270 headers; R6 design doc to Zero for ruling. First PR: "invariant registry + widening gate for retention tables" — acceptance: a test PR that widens a registered constraint without touching a registered reader fails CI; a waiver comment passes it.

  ## 7. Needs-ruling

  1. **Crypto-shredding vs the 5-year never-delete floor** (R6): a legal/business call on what counts as erasure under UU PDP — Legge 5 territory.
  2. **Setting the `ADMIN_DATABASE_URL` Fly secret** with the `flypgadmin` DSN: credential creation is operator-only.
  3. **Decommissioning the 14 dead Qdrant collection definitions and 8 live orphans** — the reconciliation runbook already ends in "Decision proposal (operator)"; dropping live collections is irreversible.
  4. **Demoting the 2 remaining app superusers** (`nuzantara_rag`, `backend_ts_user`) — W38's own GOTCHA reserved this for explicit approval.

  ## 8. §Meta-pattern

  One defective belief generates this lane's scars: **"the database boundary is singular and stable — the role, identity, schema, codec, and invariant I wrote against are the ones that will be there at read time."** Every measured failure is that belief's falsification: the runner *is* the runtime role (W38 follow-up, 289's DO-block ceremony), the dev identity *was* pointed at the prod proxy (W87), the working credential *was* accused by the broken one's error (W106), CI's schema *was* a different recipe than prod's (LEGACY_PROMOTION_README), the mocked pool *was* hiding the codec's real behavior (jsonb family), the invariant *was* widened while its readers kept the old one (281→289 outage), and "backups DONE" *was* not "backups restorable" (WAL archiving, W106). The antibodies that actually held — number lint, rollback lint, embedding-dim pin, channel-count pin — all share one shape: they convert a *believed* property into a *mechanically re-checked* one, compared at rest, in CI, against content rather than names. The beyond-SOTA move for this entire part is therefore not a new tool; it is the systematic application of that shape to the remaining belief-surfaces: role identity (R2), invariant intent (R3), codec identity (R4), estate truth (R5), and rehearsal reality (R1). The organism already knows how to build these gates; it has simply built them one scar at a time instead of sweeping the boundary class once.

  ## 9. Sources

  1. [Xata — Introducing pgroll](https://xata.io/blog/pgroll-schema-migrations-postgres) (accessed 2026-08-28) — primary: the tool author's expand/contract automation design.
  2. [Neon — Zero downtime schema migrations with pgroll](https://neon.com/guides/pgroll) (2026-06) — operational guide confirming multi-version schema mechanics.
  3. [DeepWiki — github/gh-ost](https://deepwiki.com/github/gh-ost) (2025-04) — primary-derived architecture of triggerless online migration.
  4. [Cybertec — Abusing SECURITY DEFINER functions](https://www.cybertec-postgresql.com/en/abusing-security-definer-functions/) (updated 2023-08, accessed 2026-08-28) — canonical search_path privesc analysis.
  5. [Supabase SECURITY DEFINER pitfall write-up](https://tomodahinata.com/en/blog/supabase-security-definer-function-search-path-guide) (2026-06) — modern confirmation the pitfall still bites managed platforms.
  6. [Conduktor — Outbox pattern](https://www.conduktor.io/glossary/outbox-pattern-for-reliable-event-publishing) (2026-07) — transactional outbox reference semantics.
  7. [RisingWave — Debezium outbox pattern](https://risingwave.com/blog/debezium-outbox-pattern-microservices/) (2026-04) — CDC relay mechanics and when to skip.
  8. [Thoughtworks Technology Radar Vol.19 — crypto-shredding](https://www.thoughtworks.com/content/dam/thoughtworks/documents/radar/2018/11/tr_technology_radar_vol_19_en.pdf) (2018, foundational) — the erasure-under-retention pattern definition.
  9. [Conduktor — Crypto shredding for Kafka](https://www.conduktor.io/glossary/crypto-shredding-for-kafka) (2026-07) — current implementation guidance.
  10. [pgBackRest-with-S3 hands-on guide](https://shivam2003.com/posts/pgbackrest-s3-guide) (2026-07) — restore-drill gold standard incl. `pg_amcheck` and archiver monitoring.
  11. [mydbops — PostgreSQL backup/recovery tools](https://www.mydbops.com/blog/best-postgresql-backup-and-recovery-tools) (2025-10) — drill metrics (restore time, WAL replay time).
  12. [Atlas — Atlas vs others](https://atlasgo.io/atlas-vs-others) (2026-07) — primary: declarative vs versioned schema-as-code trade-offs.
  13. [CODERCOPS — migration tools compared](https://blog.codercops.com/blog/database-schema-migration-tools-compared/) (2026-08) — current tool landscape incl. Flyway Teams discontinuation.
  14. [pgTAP — pgtap.org](https://pgtap.org/) and [Capital One pgTAP practice](https://www.capitalone.com/tech/software-engineering/automated-postgres-unit-testing/) (2024-01) — in-database unit testing, big-tech adoption.
  15. [Qdrant — Migrate to a new embedding model](https://qdrant.tech/documentation/tutorials-operations/embedding-model-migration/) (accessed 2026-08-28) — primary vendor doc for blue-green collection migration.
  16. [AI/TLDR — embedding model migration](https://ai-tldr.dev/learn/embeddings-vector-databases/vectors-in-production/embedding-model-migration/) (2026-06) — shadow-traffic and version-stamping practice.
  17. [Fly.io community — repmgr inconsistent state](https://community.fly.io/t/postgres-cluster-machine-failure-causes-inconsistent-repmgr-state/23507) (2025-01) + [Fly infra-log](https://fly.io/infra-log/) (2026-08) — primary evidence Fly Postgres flex is not managed HA.
  18. [Harness — zero-downtime migrations](https://www.harness.io/blog/zero-downtime-database-migrations-safe-schema-changes) (2026-07) and [Wellhausen — Expand and Contract](https://www.tim-wellhausen.de/papers/ExpandAndContract/ExpandAndContract.html) — pattern canon.

  status: complete
  ```

  ---

  **Delivery notes (outside the report body):** The lane brief redirected all file writes to this final message, and the snapshot is read-only, so the protocol's `ls -la`/`wc -w` post-write probe does not apply — no file was created; the report above is the deliverable verbatim. The nine `MEM:` references in the brief were unavailable (no out-of-snapshot access); every load-bearing claim from them was re-verified against repo evidence or dropped, as noted in §1. Word count is ~3,300, inside the 2,500–6,000 contract.

