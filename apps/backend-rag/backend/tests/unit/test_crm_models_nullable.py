"""Pin CRM ORM column nullability to the production schema.

Production measurement of 2026-10-06 (PR #7938, migration 324) found
``practices.practice_type_id`` NULLABLE in ``information_schema.columns``
(``is_nullable=YES``). These tests stop the SQLAlchemy models from re-asserting
a NOT NULL constraint the database does not enforce.
"""

from backend.app.modules.crm.models import Practice


class TestPracticeModelNullability:
    def test_practice_type_id_column_is_nullable(self):
        # Prod: is_nullable=YES on 2026-10-06 (migration 324). Legacy rows carry
        # NULL; the CI bootstrap (scripts/ci_bootstrap_schema.py) also drops the
        # constraint, so the ORM must not claim otherwise.
        column = Practice.__table__.c.practice_type_id
        assert column.nullable is True

    def test_client_id_column_stays_not_null(self):
        # Only practice_type_id was measured nullable; the FK to clients is still
        # NOT NULL in prod and must stay that way in the model.
        column = Practice.__table__.c.client_id
        assert column.nullable is False
