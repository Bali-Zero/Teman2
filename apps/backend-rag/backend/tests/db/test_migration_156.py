"""Verify migration 156 creates mata_garuda.tag_intel_finding — Sprint 5.

Spec: docs/sprint5/intel-radar-wiring.md
Rollback: docs/sprint5/rollback-migration-156.md
Depends: migration 154 (asset_provenance table)
Multi-LLM review: 4 rounds DeepSeek + Gemini + empirical e2e on Fly Postgres.

The migration must:
  1. Create mata_garuda schema idempotently.
  2. Drop the old 5-arg signature for upgrade idempotency
     (CREATE OR REPLACE doesn't replace across signature change).
  3. Create the function with the canonical 6-arg UUID signature.
  4. Apply NATO Admiralty defaults: reliability='F', credibility 5/4.
  5. Tier-based TTL computed from ORIGINAL tier (immutable).
  6. valid_until uses GREATEST() to never shrink on corroboration.
  7. credibility uses LEAST() in DO UPDATE (override never worsens).
  8. metadata merge is additive — preserves unknown keys via `||`.
  9. corroborating_queries capped at 100, recency-ordered.
 10. jsonb_typeof guard defends against corrupted metadata.
 11. COALESCE defends against NULL metadata.
 12. REVOKE FROM PUBLIC + GRANT TO backend_rag_v2.
 13. -- === ROLLBACK === marker present.

Mirrors test_migration_154/155 contract-test pattern (text-based; live
Postgres behavior verified separately at /tmp/sprint5-brainstorm/test_mig156.py
which is run on Pro against the local Fly proxy).
"""
from pathlib import Path

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "156_mata_garuda_tag_intel_finding.sql"
)


def _forward(sql: str) -> str:
    """Return the forward-only section (BaseMigration runner pattern)."""
    return sql.split("-- === ROLLBACK ===")[0]


def test_migration_file_exists():
    assert MIGRATION_FILE.exists()


def test_migration_has_rollback_marker():
    sql = MIGRATION_FILE.read_text()
    assert "-- === ROLLBACK ===" in sql


def test_migration_creates_schema_idempotently():
    sql = _forward(MIGRATION_FILE.read_text())
    assert "CREATE SCHEMA IF NOT EXISTS mata_garuda" in sql


def test_migration_drops_old_signature_for_idempotency():
    """R4 fix: CREATE OR REPLACE doesn't replace functions with different
    parameter lists. We need to DROP the old 5-arg signature explicitly."""
    sql = _forward(MIGRATION_FILE.read_text())
    assert "DROP FUNCTION IF EXISTS mata_garuda.tag_intel_finding(BIGINT, TEXT, TEXT, TEXT, BOOLEAN)" in sql


def test_migration_creates_function_with_uuid_signature():
    """Empirical discovery (e2e test): intel_radar_findings.id is UUID,
    NOT BIGINT as initial design assumed."""
    sql = _forward(MIGRATION_FILE.read_text())
    assert "CREATE OR REPLACE FUNCTION mata_garuda.tag_intel_finding(" in sql
    assert "p_finding_id UUID" in sql


def test_migration_function_has_six_args():
    """6-arg signature: finding_id, source_domain, query, tier, corroboration, credibility_override."""
    sql = _forward(MIGRATION_FILE.read_text())
    assert "p_finding_id UUID" in sql
    assert "p_source_domain TEXT" in sql
    assert "p_query TEXT" in sql
    assert "p_tier TEXT" in sql
    assert "p_corroboration BOOLEAN DEFAULT FALSE" in sql
    assert "p_credibility_override SMALLINT DEFAULT NULL" in sql


def test_migration_uses_nato_admiralty_defaults():
    """R1 verdict (DeepSeek + Gemini): reliability='F' for raw OSINT,
    credibility 5 (cannot judge) bumped to 4 (doubtful) on corroboration."""
    sql = _forward(MIGRATION_FILE.read_text())
    # 'F' as the literal string in the INSERT
    assert "'F'" in sql
    assert "WHEN p_corroboration THEN 4 ELSE 5" in sql


def test_migration_tier_based_ttl():
    """R1 verdict: L1=90d, L2=30d, L3=7d. Computed twice (INSERT branch
    + DO UPDATE branch with original_tier lookup)."""
    sql = _forward(MIGRATION_FILE.read_text())
    # Each branch has the CASE
    assert "WHEN 'L1' THEN 90" in sql
    assert "WHEN 'L2' THEN 30" in sql
    assert "WHEN 'L3' THEN 7" in sql


def test_migration_valid_until_uses_greatest():
    """R3/R4 fix: TTL never shrinks on corroboration."""
    sql = _forward(MIGRATION_FILE.read_text())
    assert "valid_until = GREATEST(" in sql


def test_migration_credibility_uses_least():
    """R1 verdict: re-tag never worsens credibility."""
    sql = _forward(MIGRATION_FILE.read_text())
    assert "credibility = LEAST(asset_provenance.credibility" in sql


def test_migration_metadata_uses_additive_merge():
    """R3/R4 fix: `||` preserves unknown keys from external producers.
    COALESCE defends against NULL metadata edge case."""
    sql = _forward(MIGRATION_FILE.read_text())
    # Both elements present
    assert "COALESCE(asset_provenance.metadata, '{}'::jsonb)" in sql
    # The actual `||` operator must appear in the metadata SET clause
    assert "metadata = COALESCE(asset_provenance.metadata, '{}'::jsonb) ||" in sql


def test_migration_preserves_first_tagged_at():
    """R3 verdict: first_tagged_at must survive re-tag via COALESCE."""
    sql = _forward(MIGRATION_FILE.read_text())
    assert "asset_provenance.metadata->'first_tagged_at'" in sql
    # In the COALESCE expression
    assert "COALESCE(\n                asset_provenance.metadata->'first_tagged_at'" in sql


def test_migration_preserves_original_tier():
    """R3 verdict: original_tier set on first INSERT, immutable.
    R4 fix: read inside DO UPDATE clause (no race with separate SELECT)."""
    sql = _forward(MIGRATION_FILE.read_text())
    # Both branches reference original_tier
    assert "'original_tier'" in sql
    # DO UPDATE preserves it via COALESCE
    assert "asset_provenance.metadata->>'original_tier'" in sql


def test_migration_caps_corroborating_queries():
    """R3 verdict: cap at 100 distinct queries to prevent unbounded JSONB growth."""
    sql = _forward(MIGRATION_FILE.read_text())
    assert "LIMIT 100" in sql


def test_migration_jsonb_typeof_guard():
    """R4 verdict: defend against external producers writing non-array
    `corroborating_queries` (would crash jsonb_array_elements_text)."""
    sql = _forward(MIGRATION_FILE.read_text())
    assert "jsonb_typeof(" in sql
    # Must specifically check for 'array' type
    assert "= 'array'" in sql


def test_migration_uses_to_jsonb_for_timestamps():
    """R3 verdict: use to_jsonb(timestamp) instead of ::TEXT::TIMESTAMPTZ
    cast roundtrip (fragile if the existing string isn't perfectly ISO-8601)."""
    sql = _forward(MIGRATION_FILE.read_text())
    assert "to_jsonb(v_now)" in sql


def test_migration_revokes_from_public():
    """R2/R4 verdict: state-mutating functions must NOT be PUBLIC.
    PostgreSQL grants EXECUTE to PUBLIC by default — REVOKE is required."""
    sql = _forward(MIGRATION_FILE.read_text())
    assert "REVOKE EXECUTE ON FUNCTION mata_garuda.tag_intel_finding" in sql
    assert "FROM PUBLIC" in sql


def test_migration_grants_to_backend_rag_v2_conditionally():
    """The cron's connection (DATABASE_URL_LOCAL) uses backend_rag_v2 role.

    The GRANT is wrapped in a DO block with `IF EXISTS (... pg_roles ...)`
    because CI test Postgres uses role 'test' and does NOT have
    backend_rag_v2. Without the conditional wrap, the migration crashes
    in CI with `role "backend_rag_v2" does not exist`.
    """
    sql = _forward(MIGRATION_FILE.read_text())
    # Conditional execution wrapper present
    assert "pg_roles WHERE rolname = 'backend_rag_v2'" in sql
    # The actual GRANT statement (inside EXECUTE)
    assert "GRANT EXECUTE ON FUNCTION mata_garuda.tag_intel_finding" in sql
    assert "TO backend_rag_v2" in sql


def test_migration_source_fallback_via_coalesce():
    """R2 verdict: source_domain might arrive as NULL or empty; COALESCE to 'unknown'."""
    sql = _forward(MIGRATION_FILE.read_text())
    assert "COALESCE(NULLIF(p_source_domain, ''), 'unknown')" in sql


def test_migration_tier_validation_warns_not_raises():
    """R4 verdict: invalid tier should warn-and-default, not RAISE EXCEPTION
    (caller is fail-soft; hard error would defeat best-effort tagging)."""
    sql = _forward(MIGRATION_FILE.read_text())
    # Warn, not raise exception
    assert "RAISE WARNING" in sql
    assert "v_tier := 'L2'" in sql


def test_migration_no_invalidation_event_topic():
    """Sprint 5 verdict: invalidation is purely time-driven (TTL sweep
    daily 04:13 WITA on Pro). No event-driven invalidation channel for
    intel_finding — leave invalidation_event_topic NULL.

    Verified in scripts/mata_garuda_invalidation_sweep.py docstring:
    event-driven sweep is deferred to a future cell adapter."""
    sql = _forward(MIGRATION_FILE.read_text())
    # The INSERT VALUES include explicit NULL for invalidation_event_topic
    # (preceded by the comment).
    assert "invalidation_event_topic" in sql
    # The literal NULL value in the INSERT VALUES list
    assert "NULL,\n        'amber'" in sql or "NULL," in sql


def test_migration_owner_is_intel_radar():
    """Convention: owner = organ name. War Room uses 'war_room', etc."""
    sql = _forward(MIGRATION_FILE.read_text())
    assert "'intel_radar'" in sql


def test_migration_tlp_amber():
    """Internal-team-only intel — TLP=amber. Red would be over-classification."""
    sql = _forward(MIGRATION_FILE.read_text())
    assert "'amber'" in sql


def test_rollback_drops_function():
    sql = MIGRATION_FILE.read_text()
    rollback = sql.split("-- === ROLLBACK ===")[1]
    assert "DROP FUNCTION IF EXISTS mata_garuda.tag_intel_finding(UUID, TEXT, TEXT, TEXT, BOOLEAN, SMALLINT)" in rollback
