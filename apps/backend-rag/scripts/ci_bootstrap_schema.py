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

    import backend.app.models.feedback  # noqa: F401
    import backend.app.models.openclaw_message  # noqa: F401
    import backend.app.modules.crm.company_models  # noqa: F401
    import backend.app.modules.crm.models  # noqa: F401
    import backend.app.modules.identity.models  # noqa: F401
    import backend.services.memory.models  # noqa: F401

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
    from sqlalchemy import Column, DateTime, String, Table, text
    from sqlalchemy.dialects.postgresql import UUID
    from sqlalchemy.sql import func

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
    print("[bootstrap] legacy user_profiles table ensured in DB")

    # Register a stub Table so SQLAlchemy's FK resolver finds the target.
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
        print("[bootstrap] user_profiles stub registered in SQLModel.metadata")

    SQLModel.metadata.create_all(engine)
    print(f"[bootstrap] create_all done against {db_url.split('@')[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
