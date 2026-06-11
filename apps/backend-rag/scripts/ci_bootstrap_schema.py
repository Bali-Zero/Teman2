#!/usr/bin/env python3
"""CI-only schema bootstrap.

The backend tables come from two sources:

1. Alembic-style migration files under backend/migrations/ that ALTER
   existing tables or add new indexes / triggers. `python -m backend.db.migrate
   apply-all` runs these.
2. SQLModel classes (table=True) in backend/app/models/, backend/app/modules/,
   and backend/services/memory/models.py. In production and dev the tables
   they describe were historically created by hand or by an old bootstrap
   script; no migration file creates them. Running apply-all against an empty
   CI database therefore crashes on migration 114 (cognitive_layer) because it
   references `clients`, which SQLModel owns.

This script closes that gap for CI only: it imports every module that
declares a `table=True` SQLModel class, then calls
`SQLModel.metadata.create_all(engine)` against the CI Postgres instance.
After it finishes, `python -m backend.db.migrate apply-all` can run all
Alembic migrations without a missing-table error.

NOT for prod: prod already has the tables; running `create_all` there is
harmless because SQLAlchemy emits `CREATE TABLE IF NOT EXISTS`, but there's
no reason to add startup cost when the intended path is via migrations.

Exit 0 on success, 1 otherwise.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Put the backend module root on sys.path regardless of where this script is
# invoked from.
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def main() -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        return 1

    # sqlalchemy's sync engine wants plain postgresql:// (not postgresql+asyncpg).
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = "postgresql://" + db_url[len("postgresql+asyncpg://"):]

    # Import every module that registers a SQLModel table=True class.
    # The act of importing each module is what binds the table metadata into
    # SQLModel.metadata — without these imports create_all() sees an empty
    # registry.
    print("[bootstrap] importing SQLModel modules...")
    from sqlalchemy import create_engine
    from sqlmodel import SQLModel

    import backend.app.models.feedback
    import backend.app.models.openclaw_message
    import backend.app.modules.crm.company_models
    import backend.app.modules.crm.models
    import backend.app.modules.identity.models
    import backend.services.memory.models  # noqa: F401  (import-for-side-effect: registers SQLModel tables)

    table_names = sorted(SQLModel.metadata.tables.keys())
    print(f"[bootstrap] {len(table_names)} tables registered: {', '.join(table_names)}")

    engine = create_engine(db_url, echo=False, future=True)

    # Legacy non-SQLModel tables that SQLModel tables hold FKs into.
    # `conversation_ratings.user_id` points at `user_profiles(id)` — the table
    # predates the numbered migration files (old migration 023). Two things
    # are needed:
    #   1. The table has to exist in the DB so downstream inserts work.
    #   2. The table has to be in SQLModel.metadata so create_all() can
    #      resolve the FK target. SQLAlchemy validates FKs against its own
    #      metadata registry, not the live database.
    # We do both by CREATE-ing it via raw DDL *and* registering a stub
    # `Table` object in SQLModel.metadata. Definition mirrors
    # tests/integration/conftest.py so the CI schema stays consistent with
    # the existing integration fixtures.
    # Kept minimal — only tables that are FK targets for SQLModel tables.
    # Other legacy tables (team_access, messaging_users, etc.) are created
    # by migration files that ALTER/add-column them, so the migrate step
    # handles them downstream.
    from sqlalchemy import Column, DateTime, Integer, String, Table, Text, text
    from sqlalchemy.dialects.postgresql import UUID
    from sqlalchemy.sql import func

    # Run DDL first so the tables physically exist, then register stub Table
    # objects so SQLAlchemy's FK resolver (which reads from
    # SQLModel.metadata, not the live DB) can find them during create_all().
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS user_profiles (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email VARCHAR(255) UNIQUE NOT NULL,
                full_name VARCHAR(255),
                phone VARCHAR(50),
                user_type VARCHAR(20) NOT NULL DEFAULT 'client',
                status VARCHAR(20) DEFAULT 'active',
                synthesis TEXT,
                language_pref VARCHAR(10) DEFAULT 'id',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """,
        ))
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL,
                messages TEXT NOT NULL DEFAULT '[]',
                session_id VARCHAR(255),
                rating INTEGER,
                feedback TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
            """,
        ))
        # lkpm_reports: created by old-style migration_063 (backend/migrations/
        # *.py), which the modern runner (db/migrations_v2/*.sql) does not
        # discover. Without this stub every test touching the table fails
        # with UndefinedColumnError for any column beyond id/client_id.
        # Full schema mirrored from migration_063_lkpm_reports.py so that
        # tests inserting realized_equipment_* / cumulative_* / etc. work.
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS lkpm_reports (
                id SERIAL PRIMARY KEY,
                client_id INTEGER NOT NULL,
                quarter TEXT NOT NULL,
                year INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                lkpm_assigned_to TEXT,

                realized_equipment_domestic BIGINT NOT NULL DEFAULT 0,
                realized_equipment_import BIGINT NOT NULL DEFAULT 0,
                realized_building_domestic BIGINT NOT NULL DEFAULT 0,
                realized_building_import BIGINT NOT NULL DEFAULT 0,
                realized_vehicle_domestic BIGINT NOT NULL DEFAULT 0,
                realized_vehicle_import BIGINT NOT NULL DEFAULT 0,
                realized_land BIGINT NOT NULL DEFAULT 0,
                realized_working_capital BIGINT NOT NULL DEFAULT 0,
                realized_other BIGINT NOT NULL DEFAULT 0,

                cumulative_equipment_domestic BIGINT NOT NULL DEFAULT 0,
                cumulative_equipment_import BIGINT NOT NULL DEFAULT 0,
                cumulative_building_domestic BIGINT NOT NULL DEFAULT 0,
                cumulative_building_import BIGINT NOT NULL DEFAULT 0,
                cumulative_vehicle_domestic BIGINT NOT NULL DEFAULT 0,
                cumulative_vehicle_import BIGINT NOT NULL DEFAULT 0,
                cumulative_land BIGINT NOT NULL DEFAULT 0,
                cumulative_working_capital BIGINT NOT NULL DEFAULT 0,
                cumulative_other BIGINT NOT NULL DEFAULT 0,

                current_tki INTEGER NOT NULL DEFAULT 0,
                current_tka INTEGER NOT NULL DEFAULT 0,

                quarterly_revenue BIGINT NOT NULL DEFAULT 0,
                annual_revenue BIGINT NOT NULL DEFAULT 0,

                narrative_obstacles TEXT,
                narrative_plans TEXT,

                validation_status TEXT NOT NULL DEFAULT 'pending',
                validation_alerts JSONB NOT NULL DEFAULT '[]',
                validated_at TIMESTAMPTZ,
                validated_by TEXT,

                client_approved BOOLEAN NOT NULL DEFAULT FALSE,
                client_approved_at TIMESTAMPTZ,

                oss_submitted BOOLEAN NOT NULL DEFAULT FALSE,
                oss_submitted_at TIMESTAMPTZ,
                oss_submitted_by TEXT,
                oss_receipt_number TEXT,
                oss_receipt_file_url TEXT,

                data_source TEXT NOT NULL DEFAULT 'manual',
                has_ai_categorized_items BOOLEAN NOT NULL DEFAULT FALSE,
                ai_categorized_count INTEGER NOT NULL DEFAULT 0,

                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
        ))
        # lkpm_reports prod divergence.
        #
        # 1. company_id — added by backend/migrations/migration_100a_lkpm_company_id.py
        #    (old-style Python migration not seen by the v2 runner). Production
        #    lkpm_ready_pack code joins lkpm_reports r ↔ lkpm_client_config cfg
        #    on COALESCE(r.company_id, 0) = COALESCE(cfg.company_id, 0), so the
        #    column has to exist on r even when NULL.
        # 2. realized_*/cumulative_* NULLability — the bootstrap CREATE above
        #    mirrors migration_063 which declared them NOT NULL DEFAULT 0, but
        #    prod/dev DBs relaxed them to nullable (the NOT NULL was dropped
        #    by a subsequent hand-run ALTER that never became a tracked
        #    migration). test_lkpm_ready_pack_automation intentionally
        #    INSERTs NULLs to exercise the validator; must match prod.
        for stmt in (
            "ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS company_id INTEGER",
            "ALTER TABLE lkpm_reports ALTER COLUMN realized_equipment_domestic DROP NOT NULL",
            "ALTER TABLE lkpm_reports ALTER COLUMN realized_equipment_import   DROP NOT NULL",
            "ALTER TABLE lkpm_reports ALTER COLUMN realized_building_domestic  DROP NOT NULL",
            "ALTER TABLE lkpm_reports ALTER COLUMN realized_building_import    DROP NOT NULL",
            "ALTER TABLE lkpm_reports ALTER COLUMN realized_vehicle_domestic   DROP NOT NULL",
            "ALTER TABLE lkpm_reports ALTER COLUMN realized_vehicle_import     DROP NOT NULL",
            "ALTER TABLE lkpm_reports ALTER COLUMN realized_land               DROP NOT NULL",
            "ALTER TABLE lkpm_reports ALTER COLUMN realized_working_capital    DROP NOT NULL",
            "ALTER TABLE lkpm_reports ALTER COLUMN realized_other              DROP NOT NULL",
            "ALTER TABLE lkpm_reports ALTER COLUMN cumulative_equipment_domestic DROP NOT NULL",
            "ALTER TABLE lkpm_reports ALTER COLUMN cumulative_equipment_import   DROP NOT NULL",
            "ALTER TABLE lkpm_reports ALTER COLUMN cumulative_building_domestic  DROP NOT NULL",
            "ALTER TABLE lkpm_reports ALTER COLUMN cumulative_building_import    DROP NOT NULL",
            "ALTER TABLE lkpm_reports ALTER COLUMN cumulative_vehicle_domestic   DROP NOT NULL",
            "ALTER TABLE lkpm_reports ALTER COLUMN cumulative_vehicle_import     DROP NOT NULL",
            "ALTER TABLE lkpm_reports ALTER COLUMN cumulative_land               DROP NOT NULL",
            "ALTER TABLE lkpm_reports ALTER COLUMN cumulative_working_capital    DROP NOT NULL",
            "ALTER TABLE lkpm_reports ALTER COLUMN cumulative_other              DROP NOT NULL",
        ):
            conn.execute(text(stmt))
        # system_settings: key/value store originally created by
        # backend/migrations/migration_062_client_drive_subfolders.sql (old
        # numbered series), which the modern runner (db/migrations_v2/*.sql)
        # does not discover. migrations_v2/114_compliance_alerts.sql reads
        # the table via a DO block guarded with an information_schema check,
        # so migrations still apply cleanly on a fresh CI DB — but the
        # compliance_alerts router tests (autotune gate) expect the table
        # to exist for INSERT/UPDATE. Mirroring the legacy schema verbatim.
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS system_settings (
                key VARCHAR(100) PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """,
        ))
        # notification_log: created by backend/migrations/migration_111_notification_log.py
        # notification_prefs: created by backend/migrations/migration_110_notification_prefs.py
        # Both are old-style Python migrations; the modern runner only discovers
        # backend/db/migrations_v2/*.sql so migrations 110 and 111 never run in
        # CI. alert_dispatcher (backend/services/compliance/alert_dispatcher.py)
        # reads notification_prefs and INSERTs into notification_log for every
        # dispatch — without the tables, test_alert_dispatcher.py fails with
        # UndefinedTableError. Schemas mirrored from the Python migrations
        # verbatim.
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS notification_log (
                id      BIGSERIAL PRIMARY KEY,
                user_id UUID NOT NULL,
                channel VARCHAR(20) NOT NULL,
                ref     VARCHAR(128) NOT NULL,
                sent_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )
            """,
        ))
        conn.execute(text(
            """
            CREATE INDEX IF NOT EXISTS idx_notification_log_lookup
                ON notification_log (user_id, channel, ref, sent_at DESC)
            """,
        ))
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS notification_prefs (
                user_id       UUID PRIMARY KEY,
                email_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                wa_enabled    BOOLEAN NOT NULL DEFAULT FALSE,
                wa_phone      VARCHAR(20),
                updated_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
            """,
        ))
        # war_room_drafts: created by backend/migrations/migration_112_war_room_tables.py.
        # Migration 127 (db/migrations_v2/127_war_room_canva_url.sql) ALTERs
        # this table; without it CI fails with "relation war_room_drafts does
        # not exist". The full set of war_room_* tables (posts, metrics, leads,
        # rejections, missed_runs, costs) is created by migration 112 in prod;
        # CI only needs `war_room_drafts` to satisfy the v2 ALTERs that follow.
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS war_room_drafts (
                id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                topic                 TEXT NOT NULL,
                register              TEXT,
                status                TEXT NOT NULL DEFAULT 'briefed',
                brief_json            JSONB,
                research_json         JSONB,
                council_debate_json   JSONB,
                slides_json           JSONB,
                drafts_json           JSONB,
                rejection_reason      TEXT,
                created_at            TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at            TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                approved_by           TEXT,
                approved_at           TIMESTAMP WITH TIME ZONE
            )
            """,
        ))
        # bridge_outbox: created by legacy Python migration 107.
        # Required by db/migrations_v2/192_bridge_outbox_jsonb_double_encoding_repair.sql
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS bridge_outbox (
                id         BIGSERIAL PRIMARY KEY,
                type       VARCHAR(100) NOT NULL,
                payload    JSONB NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )
            """,
        ))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_outbox_id ON bridge_outbox (id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_outbox_type ON bridge_outbox (type)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_outbox_created_at ON bridge_outbox (created_at)"))

    print("[bootstrap] legacy tables ensured in DB (user_profiles, conversations, lkpm_reports, system_settings, notification_log, notification_prefs, war_room_drafts, bridge_outbox)")

    # Register stub Tables so SQLAlchemy's FK resolver finds the targets.
    # Must live in the SAME MetaData the SQLModel classes use, otherwise
    # create_all() still raises NoReferencedTableError.
    if "user_profiles" not in SQLModel.metadata.tables:
        Table(
            "user_profiles",
            SQLModel.metadata,
            Column("id", UUID(as_uuid=True), primary_key=True),
            Column("email", String(255), unique=True, nullable=False),
            Column("full_name", String(255)),
            Column("phone", String(50)),
            Column("user_type", String(20), nullable=False),
            Column("status", String(20)),
            Column("synthesis", String),
            Column("language_pref", String(10)),
            Column("created_at", DateTime(timezone=True), server_default=func.now()),
            Column("updated_at", DateTime(timezone=True), server_default=func.now()),
        )
    if "conversations" not in SQLModel.metadata.tables:
        Table(
            "conversations",
            SQLModel.metadata,
            Column("id", Integer, primary_key=True),
            Column("user_id", String(255), nullable=False),
            Column("messages", Text, nullable=False),
            Column("session_id", String(255)),
            Column("rating", Integer),
            Column("feedback", Text),
            Column("created_at", DateTime(timezone=True), server_default=func.now()),
            Column("updated_at", DateTime(timezone=True), server_default=func.now()),
        )
    print("[bootstrap] user_profiles + conversations stubs registered in SQLModel.metadata")

    SQLModel.metadata.create_all(engine)
    print(f"[bootstrap] create_all done against {db_url.split('@')[-1]}")

    # Prod-only columns added by hand over time that never made it into a
    # migration file. The SQLModel `Client` class in
    # app/modules/crm/models.py doesn't declare them, so create_all()
    # doesn't include them either — but router code (CRM, drive poll,
    # lkpm ready-pack, invoicing, portal) reads/writes them via raw SQL.
    # Add them here so CI's fresh DB matches prod's shape.
    #
    # Grep sources:
    #   rg -n "FROM clients|SELECT\\s*\\S+\\s*clients\\." apps/backend-rag/backend
    #
    # Columns not yet promoted to a migration file:
    #   google_drive_folder_id  — drive root folder per client
    #   drive_folder_id         — legacy drive folder id (portal + events)
    #   drive_folder_url        — legacy drive folder url (documents)
    #   deleted_at              — soft-delete marker (portal, several routers)
    with engine.begin() as conn:
        for stmt in (
            "ALTER TABLE clients ADD COLUMN IF NOT EXISTS google_drive_folder_id VARCHAR(100)",
            "ALTER TABLE clients ADD COLUMN IF NOT EXISTS drive_folder_id VARCHAR(100)",
            "ALTER TABLE clients ADD COLUMN IF NOT EXISTS drive_folder_url TEXT",
            "ALTER TABLE clients ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ",
            # SQLModel's Client declares created_at/updated_at with a
            # Python-side default_factory=datetime.utcnow but no DB
            # server_default, so create_all() emits NOT NULL columns with
            # no DEFAULT. Legacy tests (several conftests + a few router
            # integration tests) INSERT without touching these columns and
            # crash with NotNullViolationError. Prod has a DEFAULT NOW()
            # applied by an old hand-run ALTER; replicate it here so CI
            # matches prod behaviour without having to patch every test.
            "ALTER TABLE clients ALTER COLUMN created_at SET DEFAULT NOW()",
            "ALTER TABLE clients ALTER COLUMN updated_at SET DEFAULT NOW()",
        ):
            conn.execute(text(stmt))
    print("[bootstrap] clients prod-only columns ensured (drive + deleted_at + timestamp defaults)")

    # documents: prod-only legacy table, hand-created (no SQLModel class, no
    # migration file creates it). Router code (CRM enhanced documents,
    # drive poll, document-intake writer) and migration 217
    # (217_intake_commit_audit.sql) ALTER it — migration 217 is the FIRST
    # numbered migration to touch `documents`, so without this CREATE the
    # migrate step dies with `relation "documents" does not exist`. DDL
    # mirrors tests/integration/app/routers/test_crm_enhanced_integration.py
    # (the canonical hand-bootstrap shape used by the integration fixtures).
    # FK on clients(id) — must run AFTER create_all() materialised `clients`.
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id            SERIAL PRIMARY KEY,
                client_id     INTEGER REFERENCES clients(id) ON DELETE CASCADE,
                document_type VARCHAR(100),
                file_name     VARCHAR(255),
                file_path     VARCHAR(500),
                status        VARCHAR(50) DEFAULT 'active',
                uploaded_by   VARCHAR(255),
                created_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
            """,
        ))
    print("[bootstrap] documents prod-only legacy table ensured (FK clients, for migration 217 + intake writer)")

    # team_members prod-only divergence.
    #
    # The SQLModel `User` in `backend/app/modules/identity/models.py` maps the
    # Python attribute `name` to DB column `full_name` via `sa_column`. Against
    # a freshly-bootstrapped CI schema (SQLModel.metadata.create_all()) only
    # `full_name` exists and is NOT NULL. Prod/dev DBs however have the inverse
    # historical shape: a legacy `name` column (NOT NULL, no default, left
    # over from the pre-CATA-5 Node.js schema) alongside a nullable `full_name`.
    # The partner test factories (tests/services/crm/partners/conftest.py,
    # tests/services/crm/partners/test_repository.py) INSERT with `name` only
    # and rely on prod DEFAULTs on timestamp/bool columns and on a nullable
    # `full_name`. Rather than patch every INSERT site, mirror the prod shape
    # here.
    #
    # Operations:
    #   name                     — ADD legacy column so test INSERTs that
    #                              reference it resolve (prod has it NOT NULL,
    #                              we leave it nullable in CI because test rows
    #                              always provide it anyway)
    #   full_name                — drop NOT NULL to mirror prod nullability
    #   personalized_response    — SQLModel Python-default only; add DB default
    #   failed_attempts          — SQLModel Python-default only; add DB default
    #   active                   — SQLModel Python-default only; add DB default
    #   created_at / updated_at  — SQLModel default_factory; add DB default
    with engine.begin() as conn:
        for stmt in (
            "ALTER TABLE team_members ADD COLUMN IF NOT EXISTS name VARCHAR(255)",
            "ALTER TABLE team_members ALTER COLUMN full_name DROP NOT NULL",
            "ALTER TABLE team_members ALTER COLUMN personalized_response SET DEFAULT FALSE",
            "ALTER TABLE team_members ALTER COLUMN failed_attempts SET DEFAULT 0",
            "ALTER TABLE team_members ALTER COLUMN active SET DEFAULT TRUE",
            "ALTER TABLE team_members ALTER COLUMN created_at SET DEFAULT NOW()",
            "ALTER TABLE team_members ALTER COLUMN updated_at SET DEFAULT NOW()",
        ):
            conn.execute(text(stmt))
    print("[bootstrap] team_members prod-only columns + defaults ensured")

    # practice_types prod-only divergence.
    #
    # The SQLModel `PracticeType` in `backend/app/modules/crm/models.py` declares
    # `duration_days: int | None` and `active: bool` (Python-side names). Prod
    # however has historical column names `typical_duration_days` and `is_active`
    # (verified via \d practice_types and used by every existing seed migration:
    # migration_044_seed_practice_types.py, migration_066_populate_practice_types_from_pricing.py,
    # migration_122_practice_types_visa_d1_5yr.py, plus the catalog endpoint
    # crm_practices.py:855-857 which selects `is_active` and `typical_duration_days`).
    #
    # SQL v2 migration 148_practice_types_bridging_visa.sql writes against the
    # prod column names. To keep CI green without rewriting the prod schema or
    # the catalog endpoint, mirror prod by ensuring both sets of columns exist
    # in CI. The SQLModel-emitted `duration_days`/`active` stay (so ORM reads
    # work), the prod-shape `typical_duration_days`/`is_active` get added so
    # raw-SQL writes from the seed migrations resolve.
    with engine.begin() as conn:
        for stmt in (
            "ALTER TABLE practice_types ADD COLUMN IF NOT EXISTS typical_duration_days INTEGER",
            "ALTER TABLE practice_types ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
            "ALTER TABLE practice_types ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",
            # SQLModel emits `active` as NOT NULL with Python-side default only.
            # The seed migrations write `is_active=true` and leave `active` to
            # the DB default — give it one so raw-SQL inserts don't trip the
            # NOT NULL constraint. Same shape as team_members.active above.
            "ALTER TABLE practice_types ALTER COLUMN active SET DEFAULT TRUE",
            # SQLModel `created_at` uses Python `default_factory=datetime.utcnow`
            # (no DB server_default). Raw-SQL seed inserts that don't list
            # created_at trip NOT NULL. Same fix as clients/team_members.
            "ALTER TABLE practice_types ALTER COLUMN created_at SET DEFAULT NOW()",
        ):
            conn.execute(text(stmt))
    print("[bootstrap] practice_types prod-only columns ensured (typical_duration_days + is_active + updated_at + active default + created_at default)")

    # companies prod-only divergence.
    #
    # SQLModel ``Company`` (backend/app/modules/crm/company_models.py) declares
    # ``setup_progress: int = Field(default=0)`` and ``created_at``/``updated_at``
    # via ``default_factory=datetime.utcnow`` -- all Python-side defaults only, so
    # create_all() emits them as NOT NULL with NO server default. Raw-SQL inserts
    # (e.g. the FASE-4 routing tests seeding synthetic companies) that don't list
    # these columns trip the NOT NULL constraint in CI even though prod, which was
    # hand-bootstrapped, carries server defaults. Mirror prod by giving them DB
    # defaults. Same fix class as clients/team_members/practice_types above.
    with engine.begin() as conn:
        for stmt in (
            "ALTER TABLE companies ALTER COLUMN setup_progress SET DEFAULT 0",
            "ALTER TABLE companies ALTER COLUMN created_at SET DEFAULT NOW()",
            "ALTER TABLE companies ALTER COLUMN updated_at SET DEFAULT NOW()",
        ):
            conn.execute(text(stmt))
    print("[bootstrap] companies prod-only columns ensured (setup_progress + created_at + updated_at defaults)")

    # practices prod-only divergence.
    #
    # Prod ``practices`` carries hand-added columns ``practice_type_code`` (text FK
    # mirror of ``practice_type_id``) and ``title`` that no migration creates -- SQL
    # v2 migration 157 even guards their use with an IF-EXISTS check. The intake
    # routing code (backend/services/intake/routing.py) SELECTs ``practice_type_code``
    # and the FASE-4 routing tests INSERT ``practice_type_code``/``title``. Mirror prod
    # so both the production query path and the raw-SQL test seeds resolve in CI.
    # Also give the Python-side-default timestamp/inquiry columns DB defaults so
    # raw-SQL inserts that omit them don't trip NOT NULL.
    with engine.begin() as conn:
        for stmt in (
            "ALTER TABLE practices ADD COLUMN IF NOT EXISTS practice_type_code VARCHAR(100)",
            "ALTER TABLE practices ADD COLUMN IF NOT EXISTS title VARCHAR(500)",
            "ALTER TABLE practices ALTER COLUMN inquiry_date SET DEFAULT NOW()",
            "ALTER TABLE practices ALTER COLUMN created_at SET DEFAULT NOW()",
            "ALTER TABLE practices ALTER COLUMN updated_at SET DEFAULT NOW()",
            "ALTER TABLE practices ALTER COLUMN practice_type_id DROP NOT NULL",
        ):
            conn.execute(text(stmt))
    print("[bootstrap] practices prod-only columns ensured (practice_type_code + title + inquiry/created/updated defaults + practice_type_id nullable)")

    # client_company_links prod-only divergence.
    #
    # SQLModel ``ClientCompanyLink`` (backend/app/modules/crm/company_models.py)
    # declares ``created_at``/``updated_at`` via ``default_factory=datetime.utcnow``
    # -- Python-side only, so create_all() emits them NOT NULL with no server
    # default. The FASE-4 routing fixture INSERTs links listing only
    # (client_id, company_id, role, is_primary), tripping NOT NULL on the
    # timestamps in CI. Mirror prod by giving them DB defaults.
    with engine.begin() as conn:
        for stmt in (
            "ALTER TABLE client_company_links ALTER COLUMN created_at SET DEFAULT NOW()",
            "ALTER TABLE client_company_links ALTER COLUMN updated_at SET DEFAULT NOW()",
        ):
            conn.execute(text(stmt))
    print("[bootstrap] client_company_links prod-only columns ensured (created_at + updated_at defaults)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
