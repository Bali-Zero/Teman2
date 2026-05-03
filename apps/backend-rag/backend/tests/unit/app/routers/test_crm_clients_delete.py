"""
Tests for soft-delete correctness in crm_clients.py DELETE endpoint.

The list endpoint filters with WHERE deleted_at IS NULL, so the DELETE
endpoint MUST set deleted_at = NOW() — otherwise soft-deleted clients
keep appearing in listings.
"""

import pathlib

ROUTER_PATH = (
    pathlib.Path(__file__).parent.parent.parent.parent.parent.parent
    / "backend"
    / "app"
    / "routers"
    / "crm_clients.py"
)


def _get_delete_sql_block() -> str:
    """Extract the UPDATE SQL block from the delete_client function."""
    source = ROUTER_PATH.read_text(encoding="utf-8")

    # Locate the delete_client function
    func_start = source.find("async def delete_client(")
    assert func_start != -1, "Could not find delete_client function in crm_clients.py"

    # Grab enough context after the function start to capture the SQL
    func_body = source[func_start : func_start + 1500]
    return func_body


class TestSoftDeleteSql:
    """Verify the SQL in the soft-delete endpoint is complete and correct."""

    def test_sets_deleted_at_now(self) -> None:
        """The UPDATE must include deleted_at = NOW() so the row is truly soft-deleted."""
        sql_block = _get_delete_sql_block()
        assert "deleted_at = NOW()" in sql_block, (
            "DELETE endpoint does not set deleted_at = NOW(). "
            "Clients will keep appearing in lists because the list query filters on "
            "WHERE deleted_at IS NULL."
        )

    def test_sets_status_inactive(self) -> None:
        """The UPDATE must still set status = 'inactive' for legacy compatibility."""
        sql_block = _get_delete_sql_block()
        assert "status = 'inactive'" in sql_block, (
            "DELETE endpoint does not set status = 'inactive'. "
            "Both fields should be updated together."
        )

    def test_where_clause_excludes_already_deleted(self) -> None:
        """The WHERE clause must include AND deleted_at IS NULL to be idempotent."""
        sql_block = _get_delete_sql_block()
        assert "deleted_at IS NULL" in sql_block, (
            "DELETE endpoint WHERE clause does not guard against re-deleting an "
            "already-deleted client. Add AND deleted_at IS NULL to the WHERE clause."
        )

    def test_update_contains_all_three_required_pieces(self) -> None:
        """Single combined assertion: all three SQL pieces must be present."""
        sql_block = _get_delete_sql_block()
        missing = []
        for required in ("deleted_at = NOW()", "status = 'inactive'", "deleted_at IS NULL"):
            if required not in sql_block:
                missing.append(required)
        assert not missing, (
            f"Soft-delete SQL is missing required clause(s): {missing}"
        )
