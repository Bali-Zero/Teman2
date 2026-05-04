"""Verify migration 154 creates asset_provenance table — Sprint 3 W2.

Spec: docs/sprint3/mata-garuda-cell-design.md
Decision: docs/sprint3/review-synthesis-2026-05-04.md (M1 rejected, M2/X5 shipped)

The migration must:
  1. Create asset_provenance table — single-table polymorphic (M1 3-layer
     pivot was REJECTED 2026-05-04 because 8/12 asset_kinds lack PG target
     tables; FK is impossible).
  2. Constrain asset_kind to the 12 canonical Bali-Zero values.
  3. Use M2 admiralty 2-axis confidence (reliability A-F + credibility 1-6).
  4. Use 3 typed columns for invalidation (X5: replaced custom DSL):
     valid_until + invalidation_event_topic + invalidation_mode enum.
  5. UNIQUE (asset_kind, asset_id) — one provenance row per asset, UPDATE
     in place.
  6. tlp column with 'red' default (safe default, not DDL enforcement).
  7. Be idempotent on re-run.
  8. Have a -- === ROLLBACK === section.

Mirrors test_migration_152.py contract-test pattern.
"""
from pathlib import Path

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "154_asset_provenance.sql"
)


def test_migration_file_exists():
    assert MIGRATION_FILE.exists()


def test_migration_has_rollback_marker():
    sql = MIGRATION_FILE.read_text()
    assert "-- === ROLLBACK ===" in sql


def test_migration_creates_asset_provenance_table():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "CREATE TABLE IF NOT EXISTS asset_provenance" in forward_section


def test_asset_kind_enum_pinned_to_12_canonical_values():
    """The asset_kind CHECK enum must contain exactly the 12
    Bali-Zero-domain values from W1.3 § "AUTHORITATIVE SET". Adding new
    values requires an ALTER TYPE migration AND updated cell adapter."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    canonical = {
        "war_room_draft", "war_room_post", "intel_finding",
        "research_dossier", "cross_dossier_thesis", "weekly_strategic_brief",
        "ultra_move", "kg_entity", "kg_proposal", "crm_enrichment_lookup",
        "compliance_alert", "measurer_metric",
    }
    for value in canonical:
        assert f"'{value}'" in forward_section, (
            f"Canonical asset_kind value '{value}' missing from CHECK enum"
        )
    # Forbidden values from the alternate "OSINT-generic" handover list
    forbidden = {
        "news_article", "regulation", "kbli_code", "telegram_post",
        "kg_node", "kg_edge", "contradiction", "entity_link",
        "document_hash", "visa_type", "query_result",
    }
    for value in forbidden:
        assert f"'{value}'" not in forward_section, (
            f"Non-authoritative asset_kind value '{value}' must NOT appear "
            f"(see B3 review finding 2026-05-04)"
        )


def test_admiralty_2_axis_confidence_columns():
    """M2: replace single 0-1 confidence with reliability A-F + credibility 1-6."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    # Reliability A-F
    assert "reliability  CHAR(1)  NOT NULL" in forward_section or \
           "reliability CHAR(1) NOT NULL" in forward_section
    assert "reliability IN ('A','B','C','D','E','F')" in forward_section
    # Credibility 1-6
    assert "credibility  SMALLINT NOT NULL" in forward_section or \
           "credibility SMALLINT NOT NULL" in forward_section
    assert "credibility BETWEEN 1 AND 6" in forward_section
    # Original confidence column SHOULD NOT exist
    assert "confidence DOUBLE PRECISION" not in forward_section, (
        "Original confidence column should be replaced by admiralty 2-axis "
        "(M2 review finding 2026-05-04)"
    )


def test_invalidation_uses_3_typed_columns_not_dsl():
    """X5: replaced custom 'invalidation_path TEXT' DSL with 3 typed columns."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "valid_until TIMESTAMPTZ" in forward_section
    assert "invalidation_event_topic VARCHAR(64)" in forward_section
    assert "invalidation_mode VARCHAR(8)" in forward_section
    assert "invalidation_mode IN ('auto', 'manual', 'never')" in forward_section
    # Original DSL column SHOULD NOT exist as a column declaration. We can't
    # filter "invalidation_path TEXT" verbatim because it appears in
    # explanatory comments referencing the rejected design — strip comments
    # before asserting.
    code_only = "\n".join(
        line for line in forward_section.splitlines()
        if not line.strip().startswith("--")
    )
    # The rejected pattern was a NOT NULL column on its own line. Make sure
    # no such column declaration survived.
    assert "invalidation_path TEXT NOT NULL" not in code_only, (
        "Original invalidation_path DSL column should be replaced by 3 typed "
        "columns (X5 review finding 2026-05-04)"
    )
    # Defensive: also no nullable variant
    assert "invalidation_path TEXT," not in code_only


def test_tlp_column_with_red_default():
    """M2: TLP column with 'red' safe default. CHECK constraint enforces
    valid TLP values; default protects against forgetful cell adapters but
    is NOT DDL-level Symbiosis Law 2 enforcement."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "tlp VARCHAR(8) NOT NULL DEFAULT 'red'" in forward_section
    assert "tlp IN ('white','green','amber','red','black')" in forward_section


def test_unique_asset_kind_asset_id_constraint():
    """One provenance row per (asset_kind, asset_id) pair — UPDATE in place."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "UNIQUE (asset_kind, asset_id)" in forward_section


def test_migration_is_idempotent():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "CREATE TABLE IF NOT EXISTS asset_provenance" in forward_section
    assert "CREATE INDEX IF NOT EXISTS ix_asset_provenance_owner" in forward_section
    assert "CREATE INDEX IF NOT EXISTS ix_asset_provenance_valid_until" in forward_section
    assert "CREATE INDEX IF NOT EXISTS ix_asset_provenance_event_topic" in forward_section
    assert "CREATE INDEX IF NOT EXISTS ix_asset_provenance_admiralty" in forward_section


def test_admiralty_index_on_both_axes():
    """I3: composite index on (reliability, credibility) WHERE invalidated_at
    IS NULL for OSINT-style queries 'show grade-A confirmed sources'."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "ix_asset_provenance_admiralty" in forward_section
    assert "(reliability, credibility)" in forward_section
    assert "WHERE invalidated_at IS NULL" in forward_section


def test_partial_index_on_valid_until_excludes_invalidated():
    """TTL sweep index must skip already-invalidated rows for efficiency."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    # Find the valid_until index block
    assert "ix_asset_provenance_valid_until" in forward_section
    # The partial-index WHERE clause must require both:
    # valid_until IS NOT NULL AND invalidated_at IS NULL
    idx_block_start = forward_section.find("ix_asset_provenance_valid_until")
    idx_block = forward_section[idx_block_start:idx_block_start + 300]
    assert "valid_until IS NOT NULL" in idx_block
    assert "invalidated_at IS NULL" in idx_block


def test_rollback_drops_indexes_then_table():
    """Rollback: indexes can be dropped before or with the table (PG drops
    indexes automatically on DROP TABLE), but explicit DROP INDEX provides
    error-isolation if the table drop fails."""
    sql = MIGRATION_FILE.read_text()
    rollback_section = sql.split("-- === ROLLBACK ===")[1]
    drop_idx_pos = rollback_section.find("DROP INDEX IF EXISTS ix_asset_provenance_admiralty")
    drop_table_pos = rollback_section.find("DROP TABLE IF EXISTS asset_provenance")
    assert drop_idx_pos != -1
    assert drop_table_pos != -1
    assert drop_idx_pos < drop_table_pos


def test_pg_channel_map_registers_asset_provenance():
    """Although the trigger ships in mig 155, PG_CHANNEL_MAP registration
    happens once (in the same PR as mig 153/154/155). Assert it's present."""
    event_bus_path = (
        Path(__file__).resolve().parents[2]
        / "services"
        / "events"
        / "event_bus.py"
    )
    src = event_bus_path.read_text()
    assert '"asset_provenance": "mata_garuda.asset_provenance"' in src


def test_migration_creates_set_updated_at_trigger():
    """Sprint 3 W2 review I3 fix: BEFORE UPDATE trigger bumps
    asset_provenance.updated_at on every UPDATE so the mig 155 trigger
    payload's 'occurred_at': NEW.updated_at always reflects the actual
    change time. Without this, direct SQL UPDATE (e.g. from psql) would
    leave updated_at stale.
    """
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "CREATE OR REPLACE FUNCTION set_updated_at_asset_provenance()" in forward_section
    assert "BEFORE UPDATE ON asset_provenance" in forward_section
    assert "asset_provenance_set_updated_at" in forward_section
    # Function must set NEW.updated_at = NOW()
    assert "NEW.updated_at = NOW()" in forward_section


def test_rollback_drops_set_updated_at_trigger_and_function():
    """Rollback ordering: trigger → function (DROP FUNCTION fails if a
    trigger still depends on it without CASCADE)."""
    sql = MIGRATION_FILE.read_text()
    rollback_section = sql.split("-- === ROLLBACK ===")[1]
    drop_trigger_pos = rollback_section.find(
        "DROP TRIGGER IF EXISTS asset_provenance_set_updated_at"
    )
    drop_function_pos = rollback_section.find(
        "DROP FUNCTION IF EXISTS set_updated_at_asset_provenance"
    )
    assert drop_trigger_pos != -1
    assert drop_function_pos != -1
    assert drop_trigger_pos < drop_function_pos
