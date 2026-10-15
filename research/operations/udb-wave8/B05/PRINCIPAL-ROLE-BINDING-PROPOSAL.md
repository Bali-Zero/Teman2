---
adversarial_review: codex
reviewed_source_sha256: "0bc4713b55ff3032255579947536a5aac447f3788cdc9d4b571242e883e2350f"
review_disposition: BLOCK_FOR_IMPLEMENTATION
---

> BLOCKED FOR IMPLEMENTATION: do not execute this proposed design. Independent review found name-only relation hashes, obsolete16-target accounting, nonexistent delivered schema fields, optional/unbound effective-role observation and unrestricted application_name output. Current artifacts contain23contracts and8database/schema/relation joins. Runtime principal-to-role bindings remain UNKNOWN; no new probe or application change is admitted by this archived proposal.

# B05 Proposal: Evidencing Runtime Principal-to-DB-Role Bindings

- **Campaign:** `universal-db-wave8-20261015`
- **Block:** `B05` — Effective operation contracts
- **Addresses:** `ADVERSARY-FINDINGS.md` (`X7`, `B05-F1`, `B05-F6`) and `DUX-NOTE-SYNTHESIS.md:36-37`
- **Status:** Concrete reviewable specification (no changes outside `research/operations/udb-wave8/B05/**`)

---

## 1. Problem Statement & Observed Blind Spot

1. **Live Catalog Grants Are Present (`LIVE-DB-METADATA.json`):**
   - `LIVE-DB-METADATA.json` (`sha256: 2bb691c347efd556eb106877e4a84b5c566f765edaa597a1c12ca73820dd56e6`) records `557` relations, `13` actors (`pg_roles`), and `4,628` `role_relation_grants` using unsalted MD5 hashes of PostgreSQL identifiers (`role_id = md5(rolname)`, `relation_id = md5(relname)`).
   - Every target relation referenced by B05's 23 operation contracts (`conversations`, `schema_migrations`, `alembic_version`, `kg_nodes`, `kg_edges`, `clients`, `practices`, `tax_obligations`, `ConversationHistory`, `cell_pulses`, `SharedMemory`, `audit_events`, `pipeline_runs`, `articles`, `social_posts`, `publishing_metrics`) resolves deterministically in `LIVE-DB-METADATA.json`, with `owner_id = 7457cee812eeb67564c33b7acf10e393` (`md5("backend_rag_v2")`) and `row_security = false`.
2. **Runtime Principal-to-Role Binding Is Unobserved (`POOL-FACTORY-SOURCE.json`):**
   - `POOL-FACTORY-SOURCE.json` (`sha256: d93668cbd3bbc1e40352a333e3fd28ffa192909e4de7b9cc0f12dbfa9fb044b8`) records 10 pool/connection factory sites across the repository, every one of which reports `"target_role": "UNOBSERVED"`, `"activation": "UNOBSERVED"`, and `"receiver_driver_identity": "UNRESOLVED"`.
   - `LIVE-DB-METADATA.json`'s `native_metadata.activity` array contains only 2 aggregate entries (`role_id = 7457cee812eeb67564c33b7acf10e393` with `13` sessions and `role_id = b33d4ce8083927697e8e21466f46987f` with `1` session), both with `"state": "UNOBSERVED"` and no mapping back to which application service or pool factory opened each session.
3. **Why Static Inference Is Forbidden (`X7`, `B05-F1`):**
   - Even when `role_relation_grants` shows that `backend_rag_v2` (`7457cee812eeb67564c33b7acf10e393`) and `postgres` (`e8a48653851e28c69d0506508fb27fc5`) hold `SELECT`/`INSERT`/`UPDATE`/`DELETE` privileges on a relation, B05 cannot prove that a specific runtime consumer (`apps/backend-rag`, `apps/federation`, `apps/zantara-media`, `packages/cell-core`, `scripts/migrate.py`) connects as `backend_rag_v2` rather than a read-only or restricted role (`nuzantara_readonly` or an ungranted role).
   - Accordingly, all 21 SQL-executing operation contracts in B05 are capped at `grant_evidence_status = "CATALOG_JOINED_ROLE_UNBOUND"` (`verification_status = "PARTIAL_STATIC_AND_CATALOG"`) until runtime principal-to-role binding is observed.

---

## 2. Security & Governance Constraints

Any mechanism that resolves `consumer_id -> role_id` must obey four hard invariants:
1. **Zero Secret / DSN Exposure (Builder Contract 3):** Never read `.env*`, Fly secrets, or `/proc/<pid>/environ`, and never print or log `DATABASE_URL` or passwords.
2. **Zero PII / Client Data Exposure (Builder Contract 4):** Query only `pg_catalog` / `pg_stat_activity` system views and session settings; never touch user tables.
3. **Identifier Hash Parity with `LIVE-DB-METADATA.json`:** Emit role identifiers as `md5(rolname::text)` so the output joins 1:1 with `LIVE-DB-METADATA.json -> native_metadata.actors[].role_id` and `role_relation_grants[].role_id`.
4. **Fail-Closed Verification:** Any factory whose runtime session is not actively observed during the probe remains `"target_role": "UNOBSERVED"` (`CATALOG_JOINED_ROLE_UNBOUND`).

---

## 3. Proposed Two-Stage Binding Mechanism

### Stage A — Deterministic `application_name` Tagging at Pool Factory Initialization (Shared-Code Follow-Up)

Each of the 10 pool/connection factories enumerated in `POOL-FACTORY-SOURCE.json` sets a structured, non-secret PostgreSQL `application_name` of the form:

```text
nuzantara:<service_scope>:<factory_id>
```

| Factory File (`POOL-FACTORY-SOURCE.json`) | Line | Driver | Proposed `application_name` Tag |
|---|---:|---|---|
| `apps/backend-rag/backend/app/metrics/db_pool_collector.py` | 48 | `asyncpg` | `nuzantara:backend-rag:db_pool_collector` |
| `apps/backend-rag/backend/db/migration_manager.py` | 159 | `asyncpg` | `nuzantara:backend-rag:migration_manager` |
| `apps/backend-rag/backend/services/database/connection_pool.py` | 109 | `asyncpg` | `nuzantara:backend-rag:connection_pool` |
| `apps/bali-intel-scraper/scripts/backfill_regulation_vectors.py` | 177 | `asyncpg` | `nuzantara:bali-intel-scraper:backfill_regulation_vectors` |
| `apps/federation/db.py` | 73 | `asyncpg` | `nuzantara:federation:db_pool` |
| `apps/mouth/scripts/populate_articles_db.ts` | 145 | `pg.Pool` | `nuzantara:mouth:populate_articles_db` |
| `apps/zantara-media/backend/app/db/database.py` | 53 | `asyncpg` | `nuzantara:zantara-media:database` |
| `packages/cell-core/cell_core/Bootstrap.py` | 64 | `asyncpg` | `nuzantara:cell-core:bootstrap` |
| `packages/cell-core/cell_core/pulse.py` | 67 | `psycopg2` | `nuzantara:cell-core:pulse` |
| `scripts/migrations/import_crm_Destructive.py` | 36 | `psycopg2` | `nuzantara:scripts:import_crm_destructive` |

- **For `asyncpg.create_pool` / `asyncpg.connect`:** merge `"application_name": "nuzantara:<service_scope>:<factory_id>"` into `server_settings={...}`.
- **For `psycopg2.connect`:** pass `application_name="nuzantara:<service_scope>:<factory_id>"` (or `options="-c application_name=..."`).
- **For `pg.Pool` (Node):** pass `application_name: "nuzantara:mouth:populate_articles_db"` in `PoolConfig`.

### Stage B — Read-Only Catalog & Session Binding Probe (Dux Native Probe)

Once Stage A is active (or immediately in read-only mode to capture existing `application_name` / `client_addr` / session GUC bindings), the BLUE Dux executes a single read-only query against PostgreSQL and writes `.agent-receipts/udb-wave8-inputs/PRINCIPAL-ROLE-BINDINGS.json`:

```sql
SELECT
    COALESCE(NULLIF(sa.application_name, ''), 'UNSET') AS application_name,
    sa.backend_type,
    COALESCE(sa.state, 'UNOBSERVED') AS session_state,
    md5(sa.usename::text) AS session_role_id,
    r.rolsuper AS is_superuser,
    r.rolbypassrls AS bypass_rls,
    COUNT(*)::int AS active_sessions
FROM pg_catalog.pg_stat_activity AS sa
JOIN pg_catalog.pg_roles AS r
  ON r.oid = sa.usesysid
WHERE sa.datname = current_database()
  AND sa.usename IS NOT NULL
GROUP BY
    COALESCE(NULLIF(sa.application_name, ''), 'UNSET'),
    sa.backend_type,
    COALESCE(sa.state, 'UNOBSERVED'),
    md5(sa.usename::text),
    r.rolsuper,
    r.rolbypassrls
ORDER BY application_name, session_role_id;
```

In addition, each pool factory's healthcheck or startup probe can emit a one-shot non-secret self-attestation row from its own connection:

```sql
SELECT
    current_setting('application_name', true) AS application_name,
    md5(session_user::text) AS session_user_role_id,
    md5(current_user::text) AS current_user_role_id,
    current_setting('transaction_isolation', true) AS transaction_isolation,
    current_setting('statement_timeout', true) AS statement_timeout,
    current_setting('lock_timeout', true) AS lock_timeout,
    current_setting('idle_in_transaction_session_timeout', true) AS idle_in_transaction_session_timeout;
```

---

## 4. Target Output Contract (`PRINCIPAL-ROLE-BINDINGS.json`)

```json
{
  "schema_version": "1.0.0",
  "observed_at": "2026-10-15T00:00:00Z",
  "bindings": [
    {
      "factory_file": "apps/backend-rag/backend/services/database/connection_pool.py",
      "factory_line": 109,
      "application_name": "nuzantara:backend-rag:connection_pool",
      "session_user_role_id": "7457cee812eeb67564c33b7acf10e393",
      "current_user_role_id": "7457cee812eeb67564c33b7acf10e393",
      "transaction_isolation": "read committed",
      "statement_timeout": "60s",
      "lock_timeout": "0",
      "idle_in_transaction_session_timeout": "0",
      "binding_status": "RUNTIME_OBSERVED"
    }
  ]
}
```

---

## 5. How B05 Validator Consumes `PRINCIPAL-ROLE-BINDINGS.json`

`b05_contracts_validator.py` already computes per-relation grant matrices from `LIVE-DB-METADATA.json` (`join_live_db_metadata_md5`). When `PRINCIPAL-ROLE-BINDINGS.json` is supplied:
1. For each operation contract `c`, resolve `c["caller_chain"]` → `factory_file` → `current_user_role_id`.
2. Look up `(current_user_role_id, md5(relation_name))` in `LIVE-DB-METADATA.json -> native_metadata.role_relation_grants` for every relation in `c["target_relations"]` and every required SQL privilege (`SELECT`, `INSERT`, `UPDATE`, `DELETE`).
3. Transition `c["grant_evidence_status"]`:
   - If `binding_status == "RUNTIME_OBSERVED"` and all required privileges are `true` (or `rolsuper == true`): promote `CATALOG_JOINED_ROLE_UNBOUND` → `RUNTIME_ROLE_VERIFIED`.
   - If `binding_status == "RUNTIME_OBSERVED"` and any required privilege is `false`: transition to `RUNTIME_ROLE_DENIED` (hard contract violation).
   - If `binding_status != "RUNTIME_OBSERVED"`: remain `CATALOG_JOINED_ROLE_UNBOUND`.


## Adversarial review

Independent Codex document review: `BLOCK_FOR_IMPLEMENTATION`. The reviewed original bytes have SHA256 `0bc4713b55ff3032255579947536a5aac447f3788cdc9d4b571242e883e2350f` at candidate `3cd10ccec8f6c47ab19629bf9c48cc0e5eb9ed7e`. See [the source-pinned review receipt](R1-DOCUMENT-REVIEW.json) for findings and limitations. The requested reviewer seat was Astra6/xhigh; its effective runtime identity was not separately echoed. This attribution records review with the stated blockers; it does not approve implementation of historical proposals, prove live role bindings, close B05, or replace the fresh BLUE exact-head Opus gate.
