"""Tests for migration_100_olympus_tables.py — DDL structure validation."""

from backend.migrations.migration_100_olympus_tables import (
    DOWN_SQL,
    MIGRATION_ID,
    UP_SQL,
)


class TestMigration100Structure:
    """Verify migration metadata and DDL content."""

    def test_migration_id_is_correct(self) -> None:
        assert MIGRATION_ID == "100_olympus_tables"

    def test_up_sql_contains_all_tables(self) -> None:
        expected_tables = [
            "olympus_heartbeats",
            "olympus_actions",
            "olympus_rules",
            "olympus_insights",
            "olympus_skills",
        ]
        for table in expected_tables:
            assert table in UP_SQL, f"UP_SQL missing table: {table}"

    def test_up_sql_contains_partitions(self) -> None:
        expected_partitions = [
            "olympus_heartbeats_2026_04",
            "olympus_heartbeats_2026_05",
            "olympus_heartbeats_2026_06",
            "olympus_heartbeats_default",
        ]
        for partition in expected_partitions:
            assert partition in UP_SQL, f"UP_SQL missing partition: {partition}"

    def test_up_sql_uses_brin_index(self) -> None:
        assert "USING BRIN" in UP_SQL

    def test_up_sql_seeds_rules(self) -> None:
        expected_rules = [
            "vacuum_dead_pct_threshold",
            "audit_retention_days",
            "heartbeat_interval_seconds",
            "pulse_interval_hours",
            "connection_alert_pct",
            "pool_alert_pct",
            "long_query_threshold_seconds",
            "growth_anomaly_pct",
            "partition_suggest_threshold",
            "mv_refresh_interval_seconds",
        ]
        for rule in expected_rules:
            assert rule in UP_SQL, f"UP_SQL missing seed rule: {rule}"

    def test_up_sql_uses_on_conflict_do_nothing(self) -> None:
        assert "ON CONFLICT" in UP_SQL
        assert "DO NOTHING" in UP_SQL

    def test_down_sql_drops_all_tables(self) -> None:
        expected_drops = [
            "olympus_heartbeats",
            "olympus_actions",
            "olympus_rules",
            "olympus_insights",
            "olympus_skills",
        ]
        for table in expected_drops:
            assert table in DOWN_SQL, f"DOWN_SQL missing drop for: {table}"

    def test_down_sql_drops_partitions(self) -> None:
        expected_partitions = [
            "olympus_heartbeats_2026_04",
            "olympus_heartbeats_2026_05",
            "olympus_heartbeats_2026_06",
            "olympus_heartbeats_default",
        ]
        for partition in expected_partitions:
            assert partition in DOWN_SQL, f"DOWN_SQL missing drop for: {partition}"

    def test_up_sql_check_constraints(self) -> None:
        # rhythm check
        assert "'heartbeat'" in UP_SQL
        assert "'pulse'" in UP_SQL
        assert "'metacognition'" in UP_SQL
        assert "'council'" in UP_SQL
        # outcome check
        assert "'success'" in UP_SQL
        assert "'failure'" in UP_SQL
        assert "'skipped'" in UP_SQL
        assert "'proposed'" in UP_SQL
        # category check
        assert "'threshold'" in UP_SQL
        assert "'schedule'" in UP_SQL
        assert "'policy'" in UP_SQL
        assert "'skill'" in UP_SQL
        # insight_type check
        assert "'pattern'" in UP_SQL
        assert "'correlation'" in UP_SQL
        assert "'anomaly'" in UP_SQL
        assert "'recommendation'" in UP_SQL

    def test_up_sql_gin_index(self) -> None:
        assert "USING GIN" in UP_SQL

    def test_up_sql_partition_by_range(self) -> None:
        assert "PARTITION BY RANGE" in UP_SQL
