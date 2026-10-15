"""Pytest invariant suite for B07 Maintenance and Migration Lineage (D02, D11, D13).

Pure stdlib + pytest; zero live store connections, zero network calls, zero PII.
Verifies:
1. Negative case (ADVERSARY-FINDINGS.md B07-F2): flagging a migration whose file SHA-256
   differs from the recorded ledger checksum.
2. CONTRACT-CONVENTIONS.md compliance (X1..X5, X10, B07-F4): 19-key operation-instance
   shape, x_ extension prefix, status vocabulary, store_id grammar, and strict
   consumer_id membership in consumer-matrix.csv.
3. DR-B07-01 and DR-B07-05.pro.out receipt invariants (including B07-F1 refutation of CE-09).
4. Static source invariants CE-01..CE-08 and PII-safety of b07_ledger_boolean_probe.py (B07-F3).
"""

from __future__ import annotations

import ast
import json
import hashlib
import importlib.util
from pathlib import Path

import pytest

B07_DIR = Path(__file__).resolve().parent
REPO_ROOT = B07_DIR.parents[3]


def _load_b07_module(module_filename: str, module_name: str):
    spec = importlib.util.spec_from_file_location(
        module_name, B07_DIR / module_filename
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


adapter = _load_b07_module("b07_lineage_adapter.py", "b07_lineage_adapter")


def test_negative_case_migration_file_sha256_differs_from_ledger_checksum() -> None:
    """Required negative case (ADVERSARY-FINDINGS.md:281): flag SHA-256 drift between file and ledger."""
    dr01 = adapter.load_dr01_manifest(B07_DIR / "dux-requests" / "DR-B07-01.out")
    actual_row = dr01["migrations_v2"][0]
    mig_107 = dict(actual_row, num=int(actual_row["file"].split("_", 1)[0]))

    # Case 1: Ledger checksum is an outdated/tampered SHA-256 different from disk
    stale_sha = "0" * 64
    assert stale_sha != mig_107["full_sha256"]
    result_drift = adapter.reconcile_migration_checksums(
        mig_107,
        schema_versions_row={"checksum": stale_sha},
        schema_migrations_row={"checksum": stale_sha},
    )
    assert result_drift["status"] == "CONFLICT"
    assert "CHECKSUM_DRIFT_FILE_VS_LEDGER" in result_drift["anomalies"]
    assert result_drift["matches_full_sha256"] is False

    # Case 2: Independent synthetic rollback-bearing fixture; no historical 025 claim.
    synthetic_forward = "CREATE TABLE synthetic_fixture(id integer);"
    synthetic_full = synthetic_forward + "\n-- ROLLBACK:\nDROP TABLE synthetic_fixture;"
    mig_025 = {"num": 987654, "has_rollback": True,
               "full_sha256": hashlib.sha256(synthetic_full.encode()).hexdigest(),
               "forward_sha256": hashlib.sha256(synthetic_forward.encode()).hexdigest()}
    assert mig_025["has_rollback"] is True
    assert mig_025["full_sha256"] != mig_025["forward_sha256"]
    result_fwd = adapter.reconcile_migration_checksums(
        mig_025,
        schema_versions_row={"checksum": mig_025["forward_sha256"]},
        schema_migrations_row={"checksum": mig_025["forward_sha256"]},
    )
    assert result_fwd["status"] == "CONFLICT"
    assert "FORWARD_VS_FULL_HASH_MISMATCH" in result_fwd["anomalies"]
    assert "CHECKSUM_DRIFT_FILE_VS_LEDGER" in result_fwd["anomalies"]
    assert result_fwd["matches_full_sha256"] is False
    assert result_fwd["matches_forward_sha256"] is True

    # Case 3: Manual apply sentinel bypass ('manual_apply')
    result_sentinel = adapter.reconcile_migration_checksums(
        mig_107,
        schema_versions_row={"checksum": "manual_apply"},
        schema_migrations_row={"checksum": "manual_apply"},
    )
    assert result_sentinel["status"] == "CONFLICT"
    assert "MANUAL_APPLY_SENTINEL_BYPASS" in result_sentinel["anomalies"]

    # Case 4: Dual-ledger split-brain (present in _schema_versions, missing in schema_migrations)
    result_split = adapter.reconcile_migration_checksums(
        mig_107,
        schema_versions_row={"checksum": mig_107["full_sha256"]},
        schema_migrations_row=None,
    )
    assert result_split["status"] == "CONFLICT"
    assert "DUAL_LEDGER_SPLIT_BRAIN" in result_split["anomalies"]

    # Case 5: Positive control — both ledgers match on-disk full_sha256
    result_ok = adapter.reconcile_migration_checksums(
        mig_107,
        schema_versions_row={"checksum": mig_107["full_sha256"]},
        schema_migrations_row={"checksum": mig_107["full_sha256"]},
    )
    assert result_ok["status"] == "EVIDENCED"
    assert result_ok["anomalies"] == []
    assert result_ok["matches_full_sha256"] is True


def test_operation_instances_conform_to_contract_conventions_and_matrix_membership() -> None:
    """Verify X1..X5, X10, and B07-F4 across all emitted B07 operation instances."""
    csv_path = REPO_ROOT / ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv"
    valid_cids, _ = adapter.load_consumer_matrix_index(csv_path)
    assert len(valid_cids) >= 6000

    instances = adapter.build_b07_operation_instances(REPO_ROOT)
    assert len(instances) == 16

    seen_cids = set()
    for inst in instances:
        adapter.validate_operation_instance(inst, valid_cids)
        seen_cids.add(inst["consumer_id"])
        assert inst["store_id"] == "pg:fly:nuzantara-postgres/public"
        assert inst["operation_id"] == "UNASSIGNED_B05"
        assert inst["source_version"] == "8061c88e0c43dd42e735fd012f9ed072df3ef3d6"
        assert "OPERATION_ID_PENDING_B05" in inst["unknowns"]

    # Reject unverified consumer_ids flagged by B07-F4
    for bad_cid in ("entry_a14536f32ddbc648", "src_8a84056e9c7f8187", "invented_id"):
        assert bad_cid not in valid_cids
        bad_record = dict(instances[0], consumer_id=bad_cid)
        with pytest.raises(ValueError, match="not found in consumer-matrix.csv"):
            adapter.validate_operation_instance(bad_record, valid_cids)

    # Reject unprefixed extension keys (X4)
    bad_ext = dict(instances[0], unprefixed_extra="forbidden")
    with pytest.raises(ValueError, match="must be prefixed with 'x_'"):
        adapter.validate_operation_instance(bad_ext, valid_cids)


def test_dux_receipts_dr01_and_dr05_pro_invariants() -> None:
    """Verify the admitted producer schema and actual on-disk source hashes."""
    dr01 = adapter.load_dr01_manifest(B07_DIR / "dux-requests/DR-B07-01.out")
    assert set(dr01) == {"migrations_v2", "py_migrations"}
    assert len(dr01["migrations_v2"]) == 199
    assert len(dr01["py_migrations"]) == 138
    numbers = set()
    for row in dr01["migrations_v2"]:
        number = int(row["file"].split("_", 1)[0])
        assert number not in numbers
        numbers.add(number)
        source = REPO_ROOT / "apps/backend-rag/backend/db/migrations_v2" / row["file"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == row["full_sha256"]
    # Actual rollback-bearing files exist; synthetic hash-format counterexamples
    # remain tested separately, without inventing a historical four-file set.
    assert any(row["has_rollback"] and row["full_sha256"] != row["forward_sha256"] for row in dr01["migrations_v2"])
    for row in dr01["py_migrations"]:
        assert "num" not in row
        source = REPO_ROOT / "apps/backend-rag/backend/migrations" / row["file"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == row["sha256"]
    dr05_pro = adapter.parse_dr05_pro_kv(B07_DIR / "dux-requests/DR-B07-05.pro.out")
    assert dr05_pro["host"] == "Nuzantara"
    assert dr05_pro["observed_at"] == "2026-10-15T08:55:09Z"
    assert dr05_pro["home_nuzantara_exists"] == "DIRECTORY"
    assert dr05_pro["desktop_nuzantara_exists"].startswith("SYMLINK -> ")
    assert dr05_pro["crontab_lines_referencing_retention_worker"] == "0"
    assert dr05_pro["launchagent_plists_referencing_retention_worker"] == "0"
    assert dr05_pro["launchagent_plists_referencing_outbox_prune"] == "2"


def test_static_counterexample_invariants_ce01_to_ce08() -> None:
    """Keep counterexamples distinct from source facts that can actually be proved."""
    migrate_src = (REPO_ROOT / "apps/backend-rag/backend/db/migrate.py").read_text()
    manager_src = (REPO_ROOT / "apps/backend-rag/backend/db/migration_manager.py").read_text()
    base_src = (REPO_ROOT / "apps/backend-rag/backend/db/migration_base.py").read_text()
    assert "manager.apply_all_pending" in migrate_src
    assert "sql_file.read_bytes()" not in migrate_src
    assert "migrations_v2" in manager_src
    assert 'sql = self.sql_file.read_text(encoding="utf-8")' in base_src
    assert "self._log_migration(conn, sql," in base_src
    assert "checksum = self._calculate_checksum(sql)" in base_src
    assert 'hashlib.sha256(sql.encode("utf-8"))' in base_src
    for name in ("165_reconcile_schema_migrations_duplicates.sql", "184_reconcile_182_tracking_divergence.sql", "194_reconcile_107_bridge_outbox_tracking.sql"):
        text = (REPO_ROOT / "apps/backend-rag/backend/db/migrations_v2" / name).read_text()
        assert "checksum" in text
        assert "'manual_apply'" not in text
    bridge = (REPO_ROOT / "apps/backend-rag/backend/db/migrations_v2/194_reconcile_107_bridge_outbox_tracking.sql").read_text()
    assert "COALESCE(NULLIF(sv.checksum, ''), 'legacy-107-bridge-outbox')" in bridge
    guardian_src = (REPO_ROOT / "apps/backend-rag/backend/services/olympus/guardian.py").read_text()
    tree = ast.parse(guardian_src)
    stop = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == "stop")
    stop_text = ast.get_source_segment(guardian_src, stop)
    assert "self._running = False" in stop_text
    assert "task.cancel()" in stop_text
    assert not any(isinstance(n, ast.Await) for n in ast.walk(stop))
    # The shell delegates; the actual deletion predicate belongs to prune_consumed.
    shell = (REPO_ROOT / "scripts/outbox-prune.sh").read_text()
    outbox = (REPO_ROOT / "apps/backend-rag/backend/services/events/outbox.py").read_text()
    assert "from backend.services.events.outbox import prune_consumed" in shell
    assert "await prune_consumed(" in shell
    function = next(n for n in ast.parse(outbox).body if isinstance(n, ast.AsyncFunctionDef) and n.name == "prune_consumed")
    body = ast.get_source_segment(outbox, function)
    assert "DELETE FROM events_outbox" in body and "consumed_at IS NOT NULL" in body
    assert "dead_letter" not in body
    # Historical absence is explicit, never filled with a successor's contents.
    assert not (REPO_ROOT / "scripts/pg-restore-drill.sh").exists()
    historical = next(r for r in adapter.build_b07_operation_instances(REPO_ROOT) if r["consumer_id"] == "src_def7a4c288a552af")
    assert historical["x_entry_point"] == "scripts/pg-restore-drill.sh"
    assert historical["status"] == "BLOCKED"
    assert historical["x_successor_lineage_status"] == "UNPROVEN"
    fly = (REPO_ROOT / ".github/workflows/fly-deploy.yml").read_text()
    pre_deploy = fly.split("  run-migrations:", 1)[1].split("  deploy:", 1)[0]
    assert "name: Run DB migrations via flyctl console" in pre_deploy
    assert "backend.db.migrate apply-all" in pre_deploy
    assert "continue-on-error" not in pre_deploy
    assert "needs: run-migrations" in fly
    assert "continue-on-error: true" in fly  # unrelated lint step only, not migration proof


def test_b07_ledger_boolean_probe_is_readonly_and_pii_free() -> None:
    """Verify B07-F3: b07_ledger_boolean_probe.py uses readonly=True and exports no actor strings."""
    probe_path = B07_DIR / "b07_ledger_boolean_probe.py"
    probe_src = probe_path.read_text(encoding="utf-8")
    tree = ast.parse(probe_src, filename=str(probe_path))
    assert tree is not None
    assert "conn.transaction(readonly=True)" in probe_src
    assert '"pii_or_actor_strings_exported": False' in probe_src
    # Ensure per_migration_booleans dictionary keys are strictly numeric/boolean metadata
    for forbidden_output_key in ('"applied_by":', '"applied_as":', '"rolname":', '"rule_name":'):
        assert forbidden_output_key not in probe_src


def test_actual_dr01_rejects_invented_numbered_schema(tmp_path: Path) -> None:
    path = tmp_path / "invented.json"
    path.write_text(json.dumps({"sql_v2": [{"num": 25}], "sql_v2_count": 277, "py_migrations_count": 42}))
    with pytest.raises(ValueError, match="actual migrations_v2"):
        adapter.load_dr01_manifest(path)


def test_actual_dr05_does_not_invent_unobserved_filesystem_facts(tmp_path: Path) -> None:
    path = tmp_path / "minimal.out"
    path.write_text("host=sample observed_at=2026-10-15T00:00:00Z\nlaunchagent_plists_referencing_outbox_prune=0\n")
    result = adapter.parse_dr05_pro_kv(path)
    assert result["host"] == "sample"
    assert "home_nuzantara_exists" not in result
    assert "desktop_nuzantara_exists" not in result


def test_historical_restore_fields_are_unknown_despite_current_successor() -> None:
    assert (REPO_ROOT / "scripts/restore_drill/run_drill.sh").is_file()
    records = adapter.build_b07_operation_instances(REPO_ROOT)
    row = next(r for r in records if r["consumer_id"] == "src_def7a4c288a552af")
    assert row["x_historical_source_available"] is False
    assert "SUCCESSOR_LINEAGE_UNPROVEN" in row["unknowns"]
    assert all(row[k]["status"] == "UNKNOWN" and row[k]["value"] == "UNKNOWN" for k in adapter.INSTANCE_11_KEYS)


def test_probe_normalizes_actual_sql_filenames_without_inventing_python_versions() -> None:
    probe = _load_b07_module("b07_ledger_boolean_probe.py", "b07_manifest_probe")
    rows = probe.load_sql_manifest(B07_DIR / "dux-requests/DR-B07-01.out")
    assert len(rows) == 199
    assert all(isinstance(number, int) and entry["num"] == number and entry["file"].endswith(".sql") for number, entry in rows.items())


def test_probe_rejects_wrong_or_duplicate_manifest_before_database_connection(tmp_path: Path) -> None:
    probe = _load_b07_module("b07_ledger_boolean_probe.py", "b07_manifest_probe_negative")
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"sql_v2": []}))
    with pytest.raises(ValueError):
        probe.load_sql_manifest(path)
    row = {"file": "001_a.sql", "full_sha256": "a" * 64, "forward_sha256": "b" * 64}
    path.write_text(json.dumps({"migrations_v2": [row, dict(row, file="001_b.sql")], "py_migrations": []}))
    with pytest.raises(ValueError, match="Duplicate"):
        probe.load_sql_manifest(path)


def test_store_id_vocabulary_rejects_legacy_engine_and_platform_aliases() -> None:
    ids, _ = adapter.load_consumer_matrix_index(REPO_ROOT / ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv")
    original = adapter.build_b07_operation_instances(REPO_ROOT)[0]
    for invalid in ("fs:pro:store", "pg:external:store", "object:external:cloudflare-r2"):
        with pytest.raises(ValueError, match="store_id"):
            adapter.validate_operation_instance(dict(original, store_id=invalid), ids)
    adapter.validate_operation_instance(dict(original, store_id="object:unknown:cloudflare-r2"), ids)
    with pytest.raises(ValueError, match="STORE_ID_PROPOSED"):
        adapter.validate_operation_instance(dict(original, store_id="unknown:unknown:unknown"), ids)


def test_static_source_never_proves_live_role_or_tenant_binding() -> None:
    for record in adapter.build_b07_operation_instances(REPO_ROOT):
        for field in ("role", "tenant", "authorization"):
            assert record[field]["status"] == "UNKNOWN"
        assert "RUNTIME_PRINCIPAL_ROLE_TENANT_BINDING_UNOBSERVED" in record["unknowns"]
