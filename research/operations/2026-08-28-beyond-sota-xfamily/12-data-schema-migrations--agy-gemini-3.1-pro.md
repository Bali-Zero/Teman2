---
panel: beyond-sota-xfamily
lane: 12-data-schema-migrations
seat: agy-gemini-3.1-pro
model: "gemini-3.1-pro · effort=high (deepest agy setting) · Antigravity CLI print mode"
started: 2026-08-28T18:44:41Z
finished: 2026-08-28T18:50:05Z
duration_s: 324
exit: 0
words: 2189
prompt_sha256_16: 01da35484b8aa25f
prompt_chars: 18669
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

```markdown
---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 12/13 — Data, schema & migration engineering
model: Gemini 3.1 Pro (pinned lane)
sources: 10
repo_files_verified: 15
---

## 0. TL;DR

Nuzantara is AHEAD in invariant safety (named abstain thresholds, Qdrant payload rules) but BEHIND state-of-the-art in database CI fidelity, relying on single-owner test DBs and mocked connection pools that mask production role constraints and driver-level serialization faults. The top three moves are: 1) Bootstrap CI schemas with exact production roles and `runtime_DSN` to catch W128 blind-deploy aborts natively; 2) Replace `mock_db_pool` with ephemeral Testcontainer DBs to eliminate the `jsonb` double-encoding trap; 3) Implement Crypto-Shredding to reconcile GDPR Right-to-Erasure with the immutable `events_outbox` and Tigris backup architecture.

## 1. How Nuzantara does it today

Nuzantara runs a custom `backend.db.migration_manager.py` Python runner executing `.sql` files out of `apps/backend-rag/backend/db/migrations_v2/`.
- **Migrations**: The corpus holds 175 migrations, running at a velocity of ~39 per month (dating back to April 2026). Exactly 57 (32.5%) declare `-- === ROLLBACK ===` inline, structurally enforced by `.github/workflows/lint-migration-rollback.yml`. Safety relies on Squawk linting (`migration-lint.yml`) to block destructive `DROP/ALTER` DDL without `CONCURRENTLY` or `IF EXISTS`, and uniqueness checks (`lint-migration-numbers.yml`) to prevent filesystem glob collisions.
- **Roles & Ownership**: Production enforces strict least-privilege boundaries. For instance, the `visa_ledger_owner` owns 22 tables. Migrations manage privilege boundaries extensively, invoking `SECURITY DEFINER` 53 times and assigning `OWNER TO visa_ledger_owner` directly (e.g., in `289_visa_retention_binders_scope_to_visa_decision.sql`, which correctly locks down the `search_path` to avoid hijack).
- **Testing Environment**: The integration tests rely on `apps/backend-rag/backend/tests/conftest.py` which provisions a `mock_db_pool()` yielding `MagicMock` instances of `asyncpg` connections rather than a real PostgreSQL backend. CI deployments (`fly-deploy.yml:50`) validate migrations against an ephemeral test Postgres where the generic `test` user creates and owns all tables. 
- **Data Invariants**: The organism uses explicit static analysis tripwires (9 tests in `test_data_invariant_tripwires.py`). For instance, `test_kbli_documents_queries_read_metadata_not_flat_business_columns` greps the router AST to ensure the `kbli_documents` table query correctly unrolls `jsonb` metadata rather than expecting the flat structure of the Qdrant payload. The system relies on exactly 5 NAMED evidence thresholds unified in `apps/backend-rag/backend/services/rag/agentic/_abstain_policy.py`, structurally preventing drift across the `GENERATION`, `LABEL`, and `CONFIDENCE` gates.
- **Durability & Retention**: `SYMBIOSIS.md` Law 4 enforces an `events_outbox` durability contract, guaranteeing up to 60 minutes of replay for disconnected listeners. The Fly Postgres cluster (`repmgr` HA, upgraded to 17.7 on 2026-08-09) performs daily backups to Tigris. This is validated by a monthly drill (`restore-drill.yml`, cron `0 4 1 * *`) with the last true isolated restore proven on 2026-08-09.

## 2. Scars & ledger evidence in this area

The most critical database traumas stem from the dissonance between test-environment assertions and production realities:
- **W128 / Scar 1461 (The Blind Deploy Trap)**: Migrations execute using the `runtime DSN` without a superuser `SET ROLE`. In production, a migration (`281`) failed because it attempted an `ALTER TABLE` on tables owned by `visa_ledger_owner` while executing as the `backend_rag_v2` runtime user. The pre-deploy CI gate missed this entirely because it tests against an ephemeral DB where the `test` user creates and inherently owns all tables. The deployment aborted midway via a Fly SIGINT (`130`), severing the process. 
- **W38 & W87 (The Write-Dead Demotion)**: A `NOSUPERUSER` demotion left the `conversations` table write-dead because 9 tables were owned by `zantara_rag_user`. A later fix required a temporary `GRANT` to resolve a 5th `policy_scope` issue (memory: `discovery_widening_..._2026_08_28.md`).
- **W40 (Migration Number Collision)**: Duplicate migration prefixes caused the glob parser to swallow one silently. It sparked the `lint-migration-numbers.yml` CI check (orphan family).
- **The jsonb Double-Encoding Trap**: Documented in `discovery_jsonb_codec_double_encodes_and_test_pools_hide_it...`, a serialization flaw caused Python dictionaries to be serialized twice before hitting Postgres. The `mock_db_pool` in `conftest.py` completely masked this because it accepts and returns native Python dicts, bypassing the actual `asyncpg` wire-level `set_type_codec` execution that would have triggered the failure.
- **Qdrant Estate Divergence**: Runbook `docs/runbooks/qdrant-estate-reconciliation.md` shows massive drift in the vector database: 14 collection definitions point at nothing, and 8 live collections (e.g., `tax_genius_hybrid`) operate completely undocumented. 

## 3. World SOTA survey

| System/Practice | Source | Mechanism | Measured Effect | Transferability |
|---|---|---|---|---|
| **Expand & Contract (pgroll / Xata)** | Xata.io / pgroll OSS (2025) | Manages multiple schema versions concurrently using PostgreSQL Views, decoupling database changes from app deploys. | True zero-downtime, safe rollbacks without `ACCESS EXCLUSIVE` queues. | LOW. Requires a paradigm shift away from `migration_manager.py` to view-based routing. |
| **Squawk DDL Linting** | sbdchd/squawk | Analyzes SQL AST for dangerous DDL operations that acquire table locks without explicit `lock_timeout`. | Prevents migration scripts from cascading into database-wide queuing outages. | HIGH. We already use it, but should enforce `lock_timeout` locally. |
| **Testcontainers CI** | Testcontainers.com | Boots ephemeral, production-shaped Docker databases for integration tests rather than mocking connection pools. | Eradicates driver-level bugs (like `jsonb` double-encoding) by forcing real I/O. | HIGH. Complements our always-on local compute nodes (Pro/Mini). |
| **Crypto-Shredding** | EDPB Guidelines 02/2025 | Encrypts PII using per-user Data Encryption Keys (DEKs). Erasure destroys the key, rendering data mathematically inert. | Reconciles GDPR Right-to-Erasure with immutable/WORM backups (like Tigris). | HIGH. Bypasses the impossibility of physically deleting users from archived WAL logs. |
| **PGAudit & RLS** | PostgreSQL 17 Docs | Extends least-privilege with Row-Level Security (RLS) tenant boundaries and forensic statement logging. | Cryptographically verifiable audit trails of PII access. | MODERATE. Adds overhead, requires careful `search_path` and policy definition. |

**Synthesis of the SOTA:**
The industry standard for schema transitions has abandoned "one-step" destructive migrations in favor of the **Expand-and-Contract** pattern, heavily relying on tools like `pgroll` to maintain backward compatibility via Views. Nuzantara is protected from lock-based outages by Squawk, but lacks a zero-downtime column-drop framework. More critically, SOTA testing architectures uniformly reject mock connection pools (`MagicMock` over `asyncpg`). They use **Testcontainers** to ensure tests exercise the exact wire protocols, catching serialization bugs natively. For data retention, **Crypto-Shredding** is the SOTA answer to the physical impossibility of erasing data across high-availability replicas and immutable WAL archives (Tigris). By destroying a user's encryption key, compliance is mathematically achieved without fighting the replication pipeline.

## 4. Position vs SOTA

*   **Data Ownership & Roles**: **BEHIND**. Nuzantara applies the principle of least privilege brilliantly in production (22 specific table owners, strict `SECURITY DEFINER` procedures). However, the CI architecture is entirely blind to it. Validating migrations on an ephemeral test DB where the `test` user creates and owns everything (W128) defeats the purpose of CI, guaranteeing that role-mismatch bugs only surface as deployment aborts.
*   **Testing Fidelity (jsonb & driver)**: **BEHIND**. Using `mock_db_pool` in `conftest.py` is a critical vulnerability. It bypasses `asyncpg` serialization (`set_type_codec`), directly masking the `jsonb` double-encoding bug. Mocks at the database-driver level create a false sense of security.
*   **Migration Safety**: **AT**. We have comprehensive Squawk linting (`migration-lint.yml`), number collision guards, and strict inline `-- === ROLLBACK ===` checks on 32% of our schema evolution. While we lack automated Expand-and-Contract (pgroll), our current CLI-driven runner is robust for our scale.
*   **Data Invariants**: **AHEAD**. The static analysis tripwires (`test_data_invariant_tripwires.py`) governing `kbli_documents` payloads and the unified `_abstain_policy.py` gates are structurally superior to standard runtime assertion testing, physically preventing architectural drift before a test suite even executes.
*   **Retention & Durability**: **AT/BEHIND**. The `events_outbox` 60-minute replay contract and monthly Tigris restore drills are excellent. However, we have a GDPR compliance gap: 5-year retention binders on the Visa Oracle combined with immutable Tigris backups mean physical erasure is impossible. We lack the SOTA Crypto-Shredding layer.
*   **Qdrant Observability**: **BEHIND**. 8 undocumented live collections and 14 dead definitions indicate our vector store is managed out-of-band and lacks the CI validation that our Postgres schema enjoys.

## 5. Beyond-SOTA recommendations

1. **Role-Aware, Prod-Shaped Test DBs for CI**
   *   **What**: Modify the CI bootstrapping sequence (`fly-deploy.yml`) to restore a `pg_dump --schema-only` snapshot of production, preserving exact ownerships (`visa_ledger_owner`, `zantara_rag_user`). Run `migration_manager.py` using the restricted `backend_rag_v2` runtime DSN.
   *   **Why it beats SOTA**: It weaponizes our strict ownership model. Standard CI spins up blank, superuser-owned DBs. By enforcing production role geometry in CI, we structurally prevent W128 blind-deploy aborts.
   *   **Cost**: Low (2-3 hours).
   *   **Gear**: 2
   *   **Risk**: Potential friction in CI bootstrap scripts. False safety (Family #2) if the dumped schema is allowed to drift.
   *   **Metric**: 0 deployment aborts due to missing `ALTER TABLE` privileges.
   *   **Kill criterion**: If CI setup time degrades by >2 minutes, revert.

2. **Kill `mock_db_pool` — Ephemeral Postgres Integration Tests**
   *   **What**: Replace `mock_db_pool` in `conftest.py` with an ephemeral local Postgres instance (leveraging local `m5-local-postgres.md` architecture) for all tests touching `jsonb`, serialization, or complex driver interactions.
   *   **Why it beats SOTA**: Exploits our always-on local compute nodes (Pro 48GB, Mini-Pro2) to run I/O-heavy integration tests without cloud CI constraints, natively catching wire-protocol bugs like `jsonb` double-encoding that mocks hide.
   *   **Cost**: Medium (3-5 hours).
   *   **Gear**: 3
   *   **Risk**: Test suite execution time increases slightly.
   *   **Metric**: 100% of `jsonb` serialization paths covered by real driver I/O.
   *   **Kill criterion**: Total test suite execution exceeds 3 minutes locally.

3. **Crypto-Shredding for PII Erasure Compliance**
   *   **What**: Introduce an envelope encryption layer (DEK) for PII fields inside `jsonb` or text columns. A user deletion request physically destroys the DEK in the KMS, leaving the ciphertext mathematically inert in the active DB and Tigris backups.
   *   **Why it beats SOTA**: Decouples GDPR/PDP compliance from Fly.io HA replication and WORM backups. We stop attempting impossible physical deletes across WAL archives and simply drop the key.
   *   **Cost**: High (implementation + compute overhead).
   *   **Gear**: 3
   *   **Risk**: Master Key loss equals total system PII loss.
   *   **Metric**: Erasure request execution time < 1 second.
   *   **Kill criterion**: Cryptographic latency overhead > 50ms per query.

4. **Qdrant Estate Manifest Tripwire**
   *   **What**: Write a static tripwire in `test_data_invariant_tripwires.py` that hits `GET /collections` on the live Fly instances and asserts it matches the dictionary in `collection_manager.py`, failing CI on undocumented drift.
   *   **Why it beats SOTA**: Extends our exceptional Postgres schema governance to the vector DB, instantly solving the 8-undocumented / 14-dead drift logged in `qdrant-estate-reconciliation.md`.
   *   **Cost**: Low (< 1 hour).
   *   **Gear**: 1
   *   **Risk**: Low.
   *   **Metric**: 0 undocumented live vector collections.

## 6. 90-day roadmap + first PRs

**Wave 1 (Days 1-30): Eradicating the Mocks**
*   **PR 1**: Replace `mock_db_pool` with ephemeral local Postgres in `conftest.py`.
*   **PR 2**: Overhaul `fly-deploy.yml` to run CI migrations against a prod-shaped schema under the limited `backend_rag_v2` role.
*   **PR 3**: Qdrant Estate drift tripwire (see below).

**Wave 2 (Days 31-60): Crypto-Shredding Foundation**
*   Secure KMS provider ruling.
*   Identify specific PII boundaries within `conversations` and `clients` tables.
*   Implement `jsonb` transparent field-level encryption/decryption at the repository layer.

**Wave 3 (Days 61-90): Zero-Downtime Pipeline**
*   Inject explicit `lock_timeout` into `migration_manager.py` connection initialization.
*   Establish Expand-and-Contract View patterns for future destructive column drops.

### First PR: Qdrant Estate Manifest Tripwire
*   **Title**: `test(qdrant): add tripwire to prevent collection manifest drift`
*   **Files**: `apps/backend-rag/backend/tests/test_data_invariant_tripwires.py` (append ~40 lines).
*   **Gear**: 1
*   **Acceptance test**: Running `pytest -k test_qdrant_estate_manifest` locally **fails** immediately due to the 8 existing undocumented collections, forcing the developer to reconcile `collection_manager.py` before the PR can merge.

## 7. Needs-ruling

*   **Crypto-Shredding KMS Provider**: We require a business decision (Zero via Telegram) on the root of trust for the Master Key. Options are Fly.io native secrets, HashiCorp Vault, or an external cloud KMS.
*   **PII Boundary Definition**: Formal legal/business sign-off on exactly which `jsonb` keys constitute PII under PDP to limit the encryption performance penalty and development scope.

## 8. §Meta-pattern

**Defective Belief:** *"Mocking the environment is a sufficient proxy for production safety."*

This single defective belief generates the entire cluster of our recent database traumas. It caused W128, because we believed testing against an ephemeral DB where `test` owned everything was a sufficient proxy for our complex production roles. It caused the `jsonb` double-encoding trap, because we believed `MagicMock` acting on `asyncpg` was a sufficient proxy for wire-level serialization. It caused the Qdrant drift, because we believed a static python dictionary was a sufficient proxy for the live vector estate. The organism trusts its tests, but the mock boundaries lie to it. The structural cure is absolute fidelity: CI and unit tests must execute against the real driver, the real roles, and the real external state.

## 9. Sources

1. **pgroll (Xata)**: https://github.com/xataio/pgroll (Accessed 2026-08-28). SOTA reference for zero-downtime, expand-and-contract migrations using PostgreSQL views.
2. **Squawk**: https://github.com/sbdchd/squawk (Accessed 2026-08-28). The established OSS PostgreSQL linter preventing un-timeout'd DDL locks.
3. **Testcontainers**: https://testcontainers.com/ (Accessed 2026-08-28). Industry standard for integration testing with ephemeral real DB instances, killing driver mock vulnerabilities.
4. **EDPB Guidelines 02/2025**: https://edpb.europa.eu/our-work-tools/general-guidance/guidelines_en (Accessed 2026-08-28). European Data Protection Board validation of crypto-shredding for Right-to-Erasure compliance.
5. **Fly.io Managed Postgres**: https://fly.io/docs/postgres/ (Accessed 2026-08-28). Documentation detailing HA realities and physical deletion limitations across replicas.
6. **PostgreSQL RLS**: https://www.postgresql.org/docs/current/rowsecurity.html (Accessed 2026-08-28). Core documentation on Row-Level Security isolation.
7. **PGAudit**: https://github.com/pgaudit/pgaudit (Accessed 2026-08-28). PostgreSQL Audit Extension standard for verifiable compliance logging.
8. **Bytebase**: https://bytebase.com/ (Accessed 2026-08-28). SOTA schema governance platform demonstrating the industry shift toward declarative Database CI/CD.
9. **Stripe Engineering**: https://stripe.com/blog (Accessed 2026-08-28). High availability data movement and expand/contract patterns at massive scale.
10. **Crypto-shredding Mechanics**: https://www.confluent.io/blog/crypto-shredding-and-gdpr/ (Accessed 2026-08-28). Technical mechanism for applying cryptographic erasure to immutable logs.

status: complete
```
