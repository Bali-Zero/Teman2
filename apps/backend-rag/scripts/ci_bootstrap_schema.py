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
    SQLModel.metadata.create_all(engine)
    print(f"[bootstrap] create_all done against {db_url.split('@')[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
